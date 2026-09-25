"""The table registry: which CSV kinds a module may author, their dedup keys, the parquet roster,
the authored/derived input files, and the model-driven helpers that turn rows into polars frames and back
into CSV cells.
"""

import csv
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import polars as pl
from just_dna_format.alleles import split_genotype
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import IDENTITY_FIELDS, authored_field_names
from just_dna_format.binning import ActivityPhenotypeRow, CopyNumberRow, HeteroplasmyRow, RepeatAlleleRow
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.expression import ExpressionEffectRow
from just_dna_format.findings import CodedWarning
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.integrity import newline_normalized_file_entries
from just_dna_format.layout import VERIFICATION_JSON, SidecarCollision, deprecation_notice, resolve_sidecar
from just_dna_format.literature import LiteratureRow
from just_dna_format.manifest import FileEntry
from just_dna_format.overrides import OverrideRow
from just_dna_format.pgs import PgsRow
from just_dna_format.pgx import AlleleFunctionRow, DiplotypeRow, HaplotypeRow, PharmVariantRow
from just_dna_format.sources import SourceRow
from pydantic import BaseModel

# Genotype allele separators: `/` (unphased), `|` (phased). See ROADMAP 0.3 item 5b. The split
# discards the `|` vs `/` distinction; phase itself is preserved separately via the `phased` column
# (materialized in `_build_weights`, re-emitted in `reverse_module`), so the round-trip is lossless —
# see docs/COMPILER.md and CONSTITUTION Principle 7.
#
# **Imported, not re-implemented (S30).** This was a private copy here, which left every consumer of
# `weights.parquet` re-deriving the rule from prose — and one of them got it wrong twice, in opposite
# directions, with nothing failing either time to say which was right. One function serving writer and
# reader is the `clinvar_dataset_label` rule: two that agree today do not fail when they drift, they
# just stop matching. The alias keeps this module's call sites reading as they did.
_split_genotype = split_genotype


# ACMG's BA1 default: an allele above 5% in a general population is stand-alone evidence of benign
# impact. PUBLIC and overridable (`compile_module(ba1_threshold=…)`) because the honest cutoff is
# disease-specific — a common recessive carrier allele lives above it legitimately — which is also why
# the finding it drives is a warning in both modes. See `_check_ba1_lint`.
BA1_ALLELE_FREQUENCY_THRESHOLD: float = 0.05


# The 0.4 table kinds (RM1): (authored CSV, compiled parquet, row model). Each is optional — a module
# includes only the kinds it uses (RM2 composition). `file_entries`/`build_artifact` skip absent files,
# so listing every kind in the file tuples below hashes exactly those a module actually has.
_TABLE_KINDS: tuple[tuple[str, str, type[BaseModel]], ...] = (
    ("activity_phenotype.csv", "activity_phenotype.parquet", ActivityPhenotypeRow),
    ("copynumbers.csv", "copynumbers.parquet", CopyNumberRow),
    ("repeat_alleles.csv", "repeat_alleles.parquet", RepeatAlleleRow),
    ("heteroplasmy.csv", "heteroplasmy.parquet", HeteroplasmyRow),
    ("haplotypes.csv", "haplotypes.parquet", HaplotypeRow),
    ("allele_function.csv", "allele_function.parquet", AlleleFunctionRow),
    ("diplotypes.csv", "diplotypes.parquet", DiplotypeRow),
    ("pgs.csv", "pgs.parquet", PgsRow),
    ("pharm_variants.csv", "pharm_variants.parquet", PharmVariantRow),
)


_TABLE_KIND_CSVS: tuple[str, ...] = tuple(csv for csv, _, _ in _TABLE_KINDS)


# Natural identity key per table kind, for duplicate-row detection (the 0.4 analog of the SNP core's
# duplicate-(variant, genotype) check). Binning kinds are omitted: an exact-duplicate *resolved* bin
# is caught as an overlap by `validate_bins`, and duplicate *unresolved* sentinels are caught
# separately in `_validate_table_kind`. A `HaplotypeRow`'s identity is (allele, defining variant); a
# `PgsRow`/`DiplotypeRow`/`PharmVariantRow` key includes `trait_efo_id`/`drug` so a legitimately
# pleiotropic or multi-drug row is not a false duplicate. `PharmVariantRow` additionally keys on
# `genotype`, `phenotype_category` and `annotation_id` (0.5) — each earned by real ClinPGx data.
# PharmGKB publishes one annotation *per genotype*, so (variant, drug) alone rejected the corpus
# outright. One variant+drug then carries several *distinct* annotations: 1,199 of 17,380
# (variant, drug, genotype) triples map to more than one, 839 of them differing by category
# (rs4149056+simvastatin is Metabolism/PK, Efficacy AND Toxicity). `annotation_id` is the
# last-resort tie-break for the 283 that differ by neither — a source accession as identity, the
# same shape as `PgsRow.pgs_id`.
#
# **Derived from each model's own `_KEY_FIELDS`, not restated here as a lambda (S48).** The columns
# and the key were two statements of one fact for four releases, and a consumer wanting the *column
# names* could get nothing out of `lambda r: (r.gene, r.allele)` without reading our source — which
# is what the reporting consumer ended up doing, and then hand-kept a string that went stale the day
# 0.6 deprecated a column in it. Each model now declares its key and this dict reads it, so
# `hints.key_fields` can name the columns and cannot disagree with the check.
#
# The per-key reasoning stays with the declarations: `HaplotypeRow` keys on the *stamped*
# `variant_key` (RM43), `DiplotypeRow` carries `clinical_context` since 0.5.1 (RM29b), and
# `PharmVariantRow` carries the full ClinPGx key.
def _key_of(row: Any) -> tuple:
    """A keyed row's identity tuple, read off the model's declared `_KEY_FIELDS`."""
    return tuple(getattr(row, name) for name in row._KEY_FIELDS)


# `SourceRow` joined the map with RM107, and it is the one member that is not a `_TABLE_KINDS` entry:
# `sources.csv`/`licensing.csv` is a fact table, so the `_TABLE_KINDS` loop never reached it and a
# duplicate `(source, layer)` row compiled green under `--strict` — no warning, a moved
# `source_signature`, and a pair free to carry *opposite* `commercial_use` in the one file the compile
# gate keys on. Drafting has refused to append over that key since S48 and `licensing.merge_sources_csv`
# merges on it, so the compiler was the only writer in the ecosystem not treating it as a key. The
# fact-table loop in `validate_spec` now runs `_validate_table_kind` too, which is what gives the
# entry below its effect; registering the model alone would have done nothing.
_TABLE_DUPE_KEYS: dict[type[BaseModel], Callable[[Any], tuple]] = dict.fromkeys(
    (
        HaplotypeRow,
        AlleleFunctionRow,
        DiplotypeRow,
        PgsRow,
        PharmVariantRow,
        SourceRow,
        # The concordance record and its paired detail table (RM130). The parent keys on
        # `(variant_key, genotype)` and the detail on `(variant_key, genotype, authority)`, and both
        # are registered for the reason `SourceRow` was: a duplicate under the key is two answers to
        # one question with no order between them, and here it would be two verdicts about one
        # contested subject — which is what an overlay row is written against, so the author would
        # be answering a question the module states twice.
        ClinSigConcordanceRow,
        ClinSigAuthorityCallRow,
        # `OverrideRow` keys on `(table, subject, member, field)` — the overlay's own key. Two rows
        # under it are two answers to one question with no defined order between them, which is the
        # `SourceRow` failure one table over: a pair free to carry opposite values in the file a
        # later stage keys on.
        OverrideRow,
    ),
    _key_of,
)


#: The authored overlay (RM124). A **third category**, registered nowhere else on purpose.
#:
#: Not a `_TABLE_KINDS` entry: those are the module's own annotation tables, so one of them satisfies
#: the "a module must carry at least one recognized table" check and each is a `LEAD_PARQUETS` member
#: the reference consumer's discovery probes on. A directory carrying only corrections is not a
#: module, and an overlay states nothing about a genotype.
#:
#: Not a `_FACT_TABLES` entry either, and so **not** in `_DERIVED_FILES`: those are machine-produced,
#: fact-hashed and byte-hashed into `manifest.derived`. Every row of this one is written by a human,
#: which is what puts it in `_INPUT_FILES` (raw-byte hashed into `manifest.inputs`, and so inside the
#: verification binding — editing a correction un-closes a module, correctly) and inside
#: `content_signature`.
#:
#: It carries a parquet regardless, and that is forced rather than chosen: `reverse_module` rebuilds a
#: spec from the artifact and has nothing else to read the overlay back from, so without one
#: `compile → reverse → compile` would silently drop every correction and move `content_signature` —
#: Principle 7. The entry sits **last** in `ARTIFACT_PARQUETS`, where a module that carries no overlay
#: keeps the digest it already had.
#: **PUBLIC**, both of them, for the reason `ARTIFACT_PARQUETS` is: a downstream repo rebuilding a
#: spec directory keeps a hand-written mirror of these names, and a name missing from it is a file
#: silently dropped on the next re-publish. `draft.DRAFTABLE` reads the CSV name from here too.
OVERRIDES_CSV: str = "overrides.csv"


OVERRIDES_PARQUET: str = "overrides.parquet"


_INPUT_FILES: tuple[str, ...] = (
    "module_spec.yaml",
    "variants.csv",
    "studies.csv",
    *_TABLE_KIND_CSVS,
    OVERRIDES_CSV,
)


# PUBLIC, and the reason is a defect this list caused while it was private (S35). Every parquet a
# compiled artifact may carry, in `manifest.artifact.files` LISTING order — which is what this tuple
# governs. It is NOT `artifact.digest` order: `integrity.artifact_digest` sorts the listing by name
# before hashing, so a member's position here is invisible to the digest and its NAME is what places
# it. Said twice in this file because the false version stood in five documents for a release and was
# corrected there while these comments were not. `just_dna_enricher.upload` derives its allow-patterns from this
# tuple instead of hand-keeping a parallel one; **at the time that bug was found** the hand-kept copy
# covered three of the sixteen names the tuple then held and silently dropped the rest at publish,
# which is `@fieldnames-from-model` one tier out. The sixteen is history and not the current size —
# spelled out because a bare number beside a registry reads as the registry's (RM218).
#: The SNP core's `csv -> parquet(s)` binding, the one part of the artifact map that was spelled
#: per-call. `_TABLE_KINDS` and `_FACT_TABLES` each carry their own binding, and `OVERRIDES_PARQUET`
#: names the overlay's, but the three core parquets were three literals at the write site and three more
#: in `ARTIFACT_PARQUETS` — so nothing could answer *"which parquet does `variants.csv` become"* without
#: a human reading `_write_*`. That question has two callers now: `ARTIFACT_PARQUETS` below, and the
#: docs site's generated per-table reference, which must not hand-keep a fourth copy
#: (`@fieldnames-from-model`, one layer out again).
#:
#: `variants.csv` maps to **two** parquets and that asymmetry is the reason this is a tuple per CSV
#: rather than a flat pair: `weights` gets the authored surface minus `gene`/`phenotype`/`category`,
#: `annotations` gets nine columns including those three, so a consumer reading one cannot see what the
#: other holds. A single-parquet spelling would have to pick one and lie about the other.
SNP_CORE_PARQUETS: dict[str, tuple[str, ...]] = {
    "variants.csv": ("weights.parquet", "annotations.parquet"),
    "studies.csv": ("studies.parquet",),
}


ARTIFACT_PARQUETS: tuple[str, ...] = (
    *(pq for parquets in SNP_CORE_PARQUETS.values() for pq in parquets),
    *(parquet for _, parquet, _ in _TABLE_KINDS),
    # The 0.5 derived-fact tables. In `ARTIFACT_PARQUETS` (so a module that carries them has a different
    # content identity — correct: different content, different artifact) but deliberately NOT in
    # `_INPUT_FILES`: like `resolution.csv`, their authored CSVs are multi-producer and are hashed by
    # FACTS (`integrity.frequency_signature` / `gene_metrics_signature`) rather than raw bytes, so a
    # reverse→recompile cycle does not "change the hash" over column order and timestamps.
    "frequencies.parquet",
    "gene_metrics.parquet",
    "literature.parquet",
    # The 0.6 pair (RM24/RM25), on the same terms as the four above. This tuple is hand-listed where
    # `_DERIVED_FILES` is derived, so a new fact table has to be added here and only here.
    "gene_validity.parquet",
    "clinical_assertions.parquet",
    # RM90 (0.6), on the same terms as the six above. Append rather than insert mid-tuple — but the
    # reason is the `artifact.files` listing a consumer iterates, NOT the digest, which name-sorts and
    # cannot see this position at all. What keeps an already-published module's digest still is that it
    # carries no such file. `test_overrides_overlay.py` proves the sort by construction.
    "gwas_effects.parquet",
    # RM130 (0.7), on the same terms as the seven above and in the same place for the same reason —
    # beside its siblings, so `manifest.artifact.files` reads in family order. The pair is two
    # parquets because it is two tables: the agreement state belongs to the subject and each
    # authority's own words belong to the authority, and one of them keys on `authority` while the
    # other must not.
    "clin_sig_concordance.parquet",
    "clin_sig_authority_calls.parquet",
    # RM194/RM200 (0.7), on the same terms as the eight above and in the same place for the same
    # reason — beside its siblings, so `manifest.artifact.files` reads in family order.
    "expression_effects.parquet",
    "sources.parquet",
    # RM124 (0.7), last — and **not for the digest reason the entries above give**, which does not
    # reach it. `integrity.artifact_digest` sorts the listing by name before hashing, so a member's
    # position in this tuple is invisible to the digest; what protects every already-published module
    # is that they carry no `overrides.csv`, so the file is absent and contributes nothing. (The
    # position rule two entries up is about `manifest.artifact.files` and the emission order a reader
    # sees, which is a real thing and a different one.) Last is simply where a new member belongs.
    # It is also the only member here that is not derived from a source — see `OVERRIDES_CSV` for why
    # it needs a parquet at all.
    OVERRIDES_PARQUET,
)


# The **lead** parquets: the ten that carry a module's own annotation rows, one per authored table
# family. Everything else in `ARTIFACT_PARQUETS` is a side table — `annotations`/`studies`, the seven
# derived-fact tables — which describes or cites the rows rather than being them. The distinction is
# not ours: it is what the reference consumer's discovery probes to decide "is this directory a
# module" (S35), and RM2 made it the honest publish gate too, since a module carries only the kinds it
# uses and `weights.parquet` has been optional for four releases.
LEAD_PARQUETS: tuple[str, ...] = (
    "weights.parquet",
    *(parquet for _, parquet, _ in _TABLE_KINDS),
)


# The 0.5 derived-fact sidecars: (authored CSV, compiled parquet, row model). Deliberately NOT
# registered in `_TABLE_KINDS`: those are authored DSL tables with `AuthoredModel` semantics, the
# reserved-namespace guard, duplicate-key checks and raw-byte input hashing. A machine-produced
# reference-fact table is a third category — injected, fact-hashed, human-overridable — and folding it
# into the table kinds would blur exactly the line the 0.5 rework drew.
#
# **`sources.csv` stays last, and that is load-bearing.** The compile loop stores each model's parsed
# rows into `fact_rows` *before* calling that model's check, and `_sources_checks` reads `fact_rows`
# to decide which declared sources a table actually used. A new fact table added after it would have
# its `source` column invisible to that check, so every module carrying one would be told its own
# licence row is an orphan. Add before `sources.csv`, never after.
_FACT_TABLES: tuple[tuple[str, str, type[BaseModel]], ...] = (
    ("frequencies.csv", "frequencies.parquet", FrequencyRow),
    ("gene_metrics.csv", "gene_metrics.parquet", GeneMetricsRow),
    ("literature.csv", "literature.parquet", LiteratureRow),
    ("gene_validity.csv", "gene_validity.parquet", GeneValidityRow),
    ("clinical_assertions.csv", "clinical_assertions.parquet", ClinicalAssertionRow),
    ("gwas_effects.csv", "gwas_effects.parquet", GwasEffectRow),
    ("clin_sig_concordance.csv", "clin_sig_concordance.parquet", ClinSigConcordanceRow),
    ("clin_sig_authority_calls.csv", "clin_sig_authority_calls.parquet", ClinSigAuthorityCallRow),
    ("expression_effects.csv", "expression_effects.parquet", ExpressionEffectRow),
    ("sources.csv", "sources.parquet", SourceRow),
)


# Optional structured-provenance document authored beside the spec (ROADMAP item 1). Hashed and
# shipped like logs, kept OUT of `artifact.digest` (it is not in `ARTIFACT_PARQUETS`).
_PROVENANCE_FILE: str = "provenance.json"


# The sidecar CSVs byte-hashed into `manifest.derived` (S26): `resolution.csv` plus every fact table.
# **Derived from `_FACT_TABLES`, never hand-listed** — a hand-kept parallel list is how
# `SOURCES_FIELDNAMES` lost a column, and this one would go stale the moment a fifth sidecar lands.
#
# Two properties that must hold together. They are hashed **where they are authored** (the spec dir)
# and NOT copied into the module dir, like `_INPUT_FILES` and unlike logs/logo/readme: each is the
# same content as its own parquet in another encoding, so shipping both would double a panel's
# frequency table for nothing. And the byte hash is **transport only** — the identity of these tables
# is the FACT hash beside it, which is the whole reason they are excluded from `_INPUT_FILES`; a
# consumer that reads this one as identity will see a reverse→recompile cycle as tampering, which is
# exactly the mistake the fact hashes exist to prevent.
#
# `verification.json` (RM45) joins the two explicit entries for the same transport reason and is not a
# fact table: it is the attestation document, so it has no parquet, no `_FACT_TABLES` row, and nothing
# in `artifact.digest`. Listing it here is what makes a registry re-splitting a downloaded tree carry
# it back beside the spec — without which the attestation would survive publication and not survive a
# download, which is the silent-layout failure `layout` exists to prevent.
_DERIVED_FILES: tuple[str, ...] = (
    "resolution.csv",
    VERIFICATION_JSON,
    *(csv for csv, _, _ in _FACT_TABLES),
)


def table_bindings() -> dict[str, tuple[str, ...]]:
    """`csv -> the parquet(s) it becomes`, assembled from the registries and never named by hand.

    Public because two surfaces outside this module need it and both would otherwise keep a copy: the
    docs site's generated per-table reference, and `test_artifact_parquet_bindings.py`, which asserts the
    union of the values is exactly `ARTIFACT_PARQUETS`. That equality is what makes the map **total** — a
    new table kind whose parquet is written by a literal at its own write site fails the test instead of
    quietly missing a reference page.

    Four registries, each owning its own slice: `SNP_CORE_PARQUETS` (the core, where `variants.csv`
    fans out to two), `_TABLE_KINDS` (the optional authored kinds), `_FACT_TABLES` (the derived facts)
    and `OVERRIDES_PARQUET` (the overlay, whose CSV is authored but is not a table kind).
    """
    bound: dict[str, tuple[str, ...]] = dict(SNP_CORE_PARQUETS)
    for csv_name, parquet, _model in _TABLE_KINDS:
        bound[csv_name] = (parquet,)
    for csv_name, parquet, _model in _FACT_TABLES:
        bound[csv_name] = (parquet,)
    bound[OVERRIDES_CSV] = (OVERRIDES_PARQUET,)
    return bound


def authored_input_entries(spec_dir: Path) -> list[FileEntry]:
    """The authored files a module is made of, hashed for the verification binding.

    Public because **two tiers must agree on it byte for byte** (the RM41 lesson): the compiler
    recomputes the binding from this set when it decides whether to publish `manifest.verification`,
    and the enricher hashes the identical set into the attestation's `module_hash` so a later compile
    can tell whether the spec has been edited since the checks ran. A private symbol here would leave
    the enricher choosing between reaching into a private name and re-implementing the list, and a
    re-implementation is a place for the two to drift — at which point every attestation this
    workspace writes reads as stale to its own compiler.

    **Authored files only**, which is the boundary `just_dna_format.verification` argues at length:
    the derived sidecars carry per-run noise (`fetched_at`) that would invalidate an attestation on a
    re-enrichment that changed nothing anyone claimed.

    **The bytes are newline-normalized, and `manifest.inputs[]` is deliberately not (RM82).** This
    docstring said the compiler hashes *these* into `manifest.inputs`; it never did — that field is
    filled independently, by `file_entries(spec_dir, _INPUT_FILES)` over the raw bytes, and the two
    were only ever equal by coincidence of computing the same thing. Since 0.6 they are two different
    questions asked of one file set. `manifest.inputs[]` and `artifact.digest` answer *are these the
    exact bytes*, so they follow every byte, line endings included. The binding answers *is this still
    the module those checks were put against*, and an editor rewriting `\\r\\n` as `\\n` changes no
    value, so it must not un-close a module. The asymmetry is the decision, not an inconsistency to
    tidy: see `integrity.newline_normalized_file_entry` for the transform and where it stops.
    """
    return newline_normalized_file_entries(Path(spec_dir), list(_INPUT_FILES))


def _locate_sidecar(spec_dir: Path, csv_name: str) -> tuple[Path | None, list[str], list[str]]:
    """Find a machine-written sidecar under any spelling it may legally carry (RM51).

    Returns `(path_or_None, warnings, errors)` and never raises, because every caller is inside a
    function that answers with a `CompilationResult`/`ValidationResult` and an escaping exception
    there is a traceback where a diagnosis belongs.

    Sits **above** `_FACT_TABLES` on purpose: `_DERIVED_FILES`, `_KNOWN_SPEC_FILES` and both load loops
    are all derived from that tuple, so a spelling that only some of them knew about would be read by
    the compiler and reported as a stray file by the near-miss guard in the same run.
    """
    try:
        path = resolve_sidecar(spec_dir, csv_name)
    except SidecarCollision as exc:
        return None, [], [str(exc)]
    if path is None:
        return None, [], []
    notice = deprecation_notice(path, csv_name, shown_as=str(path.relative_to(spec_dir)))
    return path, ([CodedWarning("sidecar_spelling_deprecated", notice)] if notice else []), []


# ── Generic model-driven materializer (RM1) ────────────────────────────────────────────────────
# The 0.4 tables are flat (scalars + one list[str]), so one materializer driven by the model's
# `model_fields` covers all nine kinds — mirroring the `_build_studies`/`_write_studies_csv` shape.
# VariantRow's genotype/phase complexity keeps its bespoke path.
def _strip_optional(annotation: Any) -> Any:
    """`Optional[X]` / `X | None` → `X`; other annotations unchanged."""
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _polars_type(annotation: Any) -> pl.DataType:
    """Map a (possibly Optional) model-field annotation to a polars dtype. `bool` before `int`
    because `bool` is an `int` subclass."""
    base = _strip_optional(annotation)
    if base is bool:
        return pl.Boolean
    if base is int:
        return pl.Int64
    if base is float:
        return pl.Float64
    if get_origin(base) is list:
        return pl.List(pl.Utf8)
    return pl.Utf8


def _list_fields(model: type[BaseModel]) -> set[str]:
    """Field names whose (stripped) annotation is a `list[...]` — rendered join-separated in CSV."""
    return {
        name for name, f in model.model_fields.items() if get_origin(_strip_optional(f.annotation)) is list
    }


def _build_table(rows: list[Any], model: type[BaseModel], module_name: str) -> pl.DataFrame:
    """A binning/PGx/PGS table → parquet. Carries a `module` column (like weights/studies) so
    `reverse_module` can recover the module name from any present parquet.

    Reads each field off the row rather than through `model_dump()`, which is not a stylistic choice:
    a stamped positional column (`variant_key`, `authored_ident`, the filled `alts` — RM43) is
    declared `exclude=True` so it stays out of `content_signature`, and `model_dump()` honours that.
    The parquet is the materialized shape and wants every field, so it asks the row directly. These
    models are flat scalars plus one `list[str]`, so this is exactly what `model_dump()` returned
    before, minus the exclusions."""
    schema: dict[str, Any] = {"module": pl.Utf8}
    for name, f in model.model_fields.items():
        schema[name] = _polars_type(f.annotation)
    records = [
        {"module": module_name, **{name: getattr(row, name) for name in model.model_fields}} for row in rows
    ]
    return pl.DataFrame(records, schema=schema)


def _scalar_cell(value: Any) -> str:
    """Render a scalar parquet value to a CSV cell — the shared cell logic every reverse writer uses:

    - ``None`` → ``""`` (absent);
    - ``bool`` → ``"true"``/``"false"`` (tri-state fidelity — an authored ``False`` survives distinct
      from an unset ``None``);
    - an **integer-valued float** → a bare int (a copy number / repeat count stored as a float
      `measure_min/max`, or an integer weight, renders as ``40`` not ``40.0``, keeping the reversed
      CSV human-authorable — value-preserving, ``"40"`` reloads to ``40.0``);
    - everything else → ``str(value)``.

    (`bool` is checked before the float branch because `bool` is an `int`, not a `float`.)"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _list_cell(value: list | None) -> str:
    """Render a list column to a pipe-joined CSV cell (empty/None → "")."""
    return "|".join(value) if value else ""


def _write_table_csv(df: pl.DataFrame, model: type[BaseModel], path: Path) -> None:
    """Reverse of `_build_table`: parquet → the authored CSV. Drops the injected `module` column
    (not authored); renders each cell via `_scalar_cell`/`_list_cell` (None→"", list→pipe-joined,
    bool→"true"/"false", integer-valued float→bare int).

    **A positional table re-emits the identity the author wrote, not the one the compiler filled**
    (RM43). Since 0.6 the compiler joins `resolution.csv` onto `pharm_variants`/`haplotypes`/
    `heteroplasmy` and materializes the resolved coordinate, so a straight passthrough here would
    hand a machine-derived `chrom`/`start`/`ref`/`alts` back as *authored* data — moving
    `content_signature` on every rsid-authored module, which is the exact failure `authored_ident`
    exists to prevent. Any identity column the row's `authored_ident` does not name is written empty;
    the fact itself is not lost, it goes to `resolution.csv` (see `_write_resolution_csv`).

    A parquet with no `authored_ident` column — anything compiled before 0.6 — blanks nothing and
    reverses exactly as it used to."""
    # `authored_field_names`, not `model_fields`: this is what keeps the stamped columns (RM43's
    # `variant_key`/`authored_ident`, and `alts` on the two PGx tables) out of the re-emitted CSV. The
    # two hand-kept exclusion lists that preceded the marker both drifted, and a reverse writer that
    # offered a stamped column would emit a CSV the compiler then refused to reload.
    fieldnames = authored_field_names(model)
    list_fields = _list_fields(model)
    identity_columns = {name for name in IDENTITY_FIELDS if name in fieldnames}
    stamps_identity = "authored_ident" in model.model_fields
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in df.iter_rows(named=True):
            authored = row.get("authored_ident") if stamps_identity else None
            blanked = identity_columns - set(authored) if authored is not None else set()
            out = {
                name: (
                    ""
                    if name in blanked
                    else _list_cell(row.get(name))
                    if name in list_fields
                    else _scalar_cell(row.get(name))
                )
                for name in fieldnames
            }
            writer.writerow(out)
