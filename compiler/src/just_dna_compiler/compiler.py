"""
Module spec compiler: validates a spec directory and compiles it to a composed multi-parquet
artifact plus a `manifest.json`. A module composes from optional table kinds (RM2): the three-parquet
SNP core (weights, annotations, studies) when it carries variants, plus one parquet per 0.4 table
kind it includes (diplotypes, pharm_variants, pgs, the binning kinds, …) — up to twelve in all.

Public API:
    validate_spec(spec_dir) -> ValidationResult
    compile_module(spec_dir, output_dir, ...) -> CompilationResult   (emits manifest.json)
    reverse_module(parquet_dir, output_dir, ...) -> Path

The DSL/manifest schema comes from `just-dna-format`; this package is the transform between them.
"""

import csv
import difflib
import logging
import math
import re
import shutil
import types
import warnings
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, NamedTuple, Union, get_args, get_origin

import polars as pl
import yaml
from just_dna_format.alleles import (
    RECOMMENDED_SYMBOLIC_SUBTYPES,
    SYMBOLIC_ALLELE_TYPES,
    is_symbolic_allele,
    is_unobservable_allele,
    non_nucleotide_reason,
    symbolic_allele_defect,
)
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import (
    DEFAULT_GENOME_BUILD,
    IDENTITY_FIELDS,
    AuthoredModel,
    authored_field_names,
    derive_variant_key,
)
from just_dna_format.binning import (
    ActivityPhenotypeRow,
    CopyNumberRow,
    HeteroplasmyRow,
    MeasureBinRow,
    RepeatAlleleRow,
    measurement_shape_warnings,
    validate_bins,
)
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.identity import is_valid_version
from just_dna_format.layout import (
    DERIVED_SUBDIR,
    SOURCES_CSV,
    VERIFICATION_JSON,
    SidecarCollision,
    deprecation_notice,
    resolve_sidecar,
    sidecar_relative_names,
    sidecar_spellings,
    sidecar_write_path,
)
from just_dna_format.integrity import (
    build_artifact,
    file_entries,
    file_entry,
    sha256_file,
)
from just_dna_format.integrity import (
    content_signature as _content_signature,
)
from just_dna_format.integrity import (
    frequency_signature as _frequency_signature,
)
from just_dna_format.integrity import (
    clinical_assertion_signature as _clinical_assertion_signature,
)
from just_dna_format.integrity import (
    gene_metrics_signature as _gene_metrics_signature,
)
from just_dna_format.integrity import (
    gene_validity_signature as _gene_validity_signature,
)
from just_dna_format.integrity import (
    literature_signature as _literature_signature,
)
from just_dna_format.integrity import (
    resolution_signature as _resolution_signature,
)
from just_dna_format.integrity import (
    source_signature as _source_signature,
)
from just_dna_format.literature import LiteratureRow
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    README_CANDIDATES,
    README_EXTENSIONS,
    ClinicalAssertions,
    Compilation,
    Display,
    FileEntry,
    Frequency,
    GeneMetrics,
    GeneValidity,
    Identity,
    Literature,
    ModuleManifest,
    Provenance,
    ProvenanceDoc,
    Sources,
    Stats,
    Verification,
    read_manifest,
    write_manifest,
)
from just_dna_format.normalize import now_utc_iso, parse_p_value, strip_authority_keys
from just_dna_format.pgs import PgsRow
from just_dna_format.pgx import (
    AlleleFunctionRow,
    DiplotypeRow,
    HaplotypeRow,
    PharmVariantRow,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow, taints_commercial_use, taints_redistribution
from just_dna_format.verification import (
    attestation_failure,
    module_binding,
    read_verification,
    verification_block,
)
from just_dna_format.spec import (
    RESERVED_FLAGS,
    Defaults,
    ModuleSpecConfig,
    StudyRow,
    VariantRow,
    extract_pmids,
)
from just_dna_format.vocab import (
    VALID_ELEMENT_RULES,
    VCF_COLLIDING_KEYS,
    VCF_COLLISION_REASONS,
    VCF_NUMBER_MEANINGS,
    VCF_POINTER_COMPANIONS,
    VCF_POINTER_FIELDS,
    is_multi_valued_number,
    population_sort_key,
    split_field_pointer,
    vcf_field_number,
)
from just_dna_format.vrs import (
    UnsupportedBuildError,
    builds_containing_position,
    contig_length,
    derive_vrs_allele_id,
    in_pseudoautosomal_region,
    is_substitution,
    sole_build_naming_contig,
    split_vrs_ids,
)
from pydantic import BaseModel, ValidationError

from just_dna_compiler.models import CompilationResult, ValidationResult
from just_dna_compiler.resolution import (
    hosting_verdict,
    resolve_from_table,
    resolve_positional_rows,
)

# `validate_spec`/`compile_module` return their findings on a result object, which is the right shape
# for anything a caller must act on. `reverse_module` returns a bare `Path` and has none, so the one
# thing it needs to say — that an attestation is being dropped — goes here (CLAUDE.md: stdlib
# `logging`, never `print`). Unconfigured, this still reaches stderr through logging's last-resort
# handler, so a CLI that sets nothing up does not swallow it.
logger = logging.getLogger(__name__)

# Genotype allele separators: `/` (unphased), `|` (phased). See ROADMAP 0.3 item 5b. Splitting on
# both yields the allele list; this function discards the `|` vs `/` distinction. Phase itself is
# preserved separately via the `phased` column (materialized in `_build_weights`, re-emitted in
# `reverse_module`), so the round-trip is lossless — see docs/COMPILER.md and CONSTITUTION Principle 7.
_GENOTYPE_SEP: re.Pattern[str] = re.compile(r"[/|]")


def _split_genotype(genotype: str) -> list[str]:
    """Split a genotype string into its alleles, accepting single-allele (hemizygous),
    slash-separated (unphased), and pipe-separated (phased) forms."""
    return [allele for allele in _GENOTYPE_SEP.split(genotype) if allele]


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
_TABLE_DUPE_KEYS: dict[type[BaseModel], Callable[[Any], tuple]] = {
    # `r.variant_key` since 0.6 (RM43): the same expression this used to recompute, but stamped at
    # load from the *authored* columns — so the duplicate check keys on what the author wrote rather
    # than on whatever the resolution fill has since put in the cells.
    HaplotypeRow: lambda r: (r.haplotype_name, r.variant_key, r.allele),
    AlleleFunctionRow: lambda r: (r.gene, r.allele),
    # `clinical_context` joined the key in 0.5.1 (RM29b): CPIC scopes one gene/drug pair to several
    # settings whose recommendations disagree, so without it the three clopidogrel rows are duplicates
    # of each other and only one survives — the collision that made `draft --drug` refuse.
    DiplotypeRow: lambda r: (
        r.gene, r.haplotype_a, r.haplotype_b, r.trait_efo_id, r.drug, r.clinical_context,
    ),
    PgsRow: lambda r: (r.pgs_id, r.trait_efo_id),
    PharmVariantRow: lambda r: (
        r.variant_key, r.drug, r.genotype, r.phenotype_category, r.annotation_id,
    ),
}

_INPUT_FILES: tuple[str, ...] = (
    "module_spec.yaml",
    "variants.csv",
    "studies.csv",
    *_TABLE_KIND_CSVS,
)
_OUTPUT_FILES: tuple[str, ...] = (
    "weights.parquet",
    "annotations.parquet",
    "studies.parquet",
    *(parquet for _, parquet, _ in _TABLE_KINDS),
    # The 0.5 derived-fact tables. In `_OUTPUT_FILES` (so a module that carries them has a different
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
    "sources.parquet",
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
    ("sources.csv", "sources.parquet", SourceRow),
)
# Optional structured-provenance document authored beside the spec (ROADMAP item 1). Hashed and
# shipped like logs, kept OUT of `artifact.digest` (it is not in `_OUTPUT_FILES`).
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


def authored_input_entries(spec_dir: Path) -> list[FileEntry]:
    """The authored files a module is made of, hashed — `manifest.inputs`, and the verification binding.

    Public because **two tiers must agree on it byte for byte** (the RM41 lesson): the compiler hashes
    these into `manifest.inputs`, and the enricher hashes the identical set into the attestation's
    `module_hash` so a later compile can tell whether the spec has been edited since the checks ran. A
    private symbol here would leave the enricher choosing between reaching into a private name and
    re-implementing the list, and a re-implementation is a place for the two to drift — at which point
    every attestation this workspace writes reads as stale to its own compiler.

    **Authored files only**, which is the boundary `just_dna_format.verification` argues at length:
    the derived sidecars carry per-run noise (`fetched_at`) that would invalidate an attestation on a
    re-enrichment that changed nothing anyone claimed.
    """
    return file_entries(Path(spec_dir), list(_INPUT_FILES))


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
    return path, ([notice] if notice else []), []


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
        name
        for name, f in model.model_fields.items()
        if get_origin(_strip_optional(f.annotation)) is list
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
        {"module": module_name, **{name: getattr(row, name) for name in model.model_fields}}
        for row in rows
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
            blanked = (
                identity_columns - set(authored) if authored is not None else set()
            )
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


def _compiler_version() -> str:
    try:
        return f"just-dna-compiler {version('just-dna-compiler')}"
    except PackageNotFoundError:
        return "just-dna-compiler unknown"


def _now_iso() -> str:
    """The manifest's stamp, from the format tier's single producer (`normalize.now_utc_iso`).

    Already this spelling before it moved — kept as a thin alias so there is exactly one place
    that decides what a timestamp looks like across all three tiers."""
    return now_utc_iso()


def _collect_logs(
    spec_dir: Path, output_dir: Path, explicit: list[Path] | None
) -> list[FileEntry]:
    """Gather optional run/provenance logs into the module dir and hash them.

    Auto-discovers a top-level aggregate log (`*.log` in `spec_dir`) plus per-role files under a
    `spec_dir/logs/` folder, preserving each file's path relative to the module. An explicit
    `log_files` list overrides discovery. Files are copied into `output_dir` (so they ship with the
    module) and returned as hashed `FileEntry` rows. No logs → empty list (a valid module).
    """
    pairs: list[tuple[str, Path]] = []  # (relative name in module dir, source file)
    if explicit is not None:
        for path in map(Path, explicit):
            try:
                rel = path.relative_to(spec_dir).as_posix()
            except ValueError:
                rel = path.name
            pairs.append((rel, path))
    else:
        for path in sorted(spec_dir.glob("*.log")):
            pairs.append((path.name, path))
        logs_dir = spec_dir / "logs"
        if logs_dir.is_dir():
            for path in sorted(logs_dir.rglob("*.log")):
                pairs.append((path.relative_to(spec_dir).as_posix(), path))

    seen: set[str] = set()
    names: list[str] = []
    for rel, src in pairs:
        if rel in seen or not src.is_file():
            continue
        seen.add(rel)
        dest = output_dir / rel
        if dest.resolve() != src.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        names.append(rel)
    return file_entries(output_dir, names)


def _collect_provenance(
    spec_dir: Path, output_dir: Path, explicit: Path | None
) -> Provenance | None:
    """Discover an optional `provenance.json`, validate it, ship it, and summarize it.

    Auto-discovers `spec_dir/provenance.json` (or uses an explicit path). The full per-variant
    items stay in the file (copied into the module dir, hashed like logs, and kept out of
    `artifact.digest`); the returned `Provenance` is the lean summary that rides in the manifest.
    Absent provenance → `None` (a valid module).
    """
    src = Path(explicit) if explicit is not None else spec_dir / _PROVENANCE_FILE
    if not src.is_file():
        return None
    doc = ProvenanceDoc.model_validate_json(src.read_text(encoding="utf-8"))
    dest = output_dir / _PROVENANCE_FILE
    if dest.resolve() != src.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return Provenance(
        generator=doc.generator,
        model=doc.model,
        agent_version=doc.agent_version,
        item_count=len(doc.items),
        file=_PROVENANCE_FILE,
        sha256=sha256_file(dest),
    )


def _collect_logo(
    spec_dir: Path, output_dir: Path, explicit: Path | None
) -> FileEntry | None:
    """Discover an optional module logo (`logo.png`/`.jpg`/`.jpeg`), ship it, and hash it.

    Uses an explicit path if given, else the first `logo.<ext>` (in `LOGO_EXTENSIONS` order) found
    beside the spec. The logo is copied into the module dir and returned as a hashed `FileEntry`
    kept OUT of `artifact.digest` (a logo swap is a PATCH, not a new content identity). Absent
    logo → `None`. Raises `ValueError` on an unsupported extension.
    """
    if explicit is not None:
        src: Path | None = Path(explicit)
    else:
        src = next(
            (spec_dir / f"logo.{ext}" for ext in sorted(LOGO_EXTENSIONS)
             if (spec_dir / f"logo.{ext}").is_file()),
            None,
        )
    if src is None or not src.is_file():
        return None
    ext = src.suffix.lower().lstrip(".")
    if ext not in LOGO_EXTENSIONS:
        raise ValueError(f"logo must be one of {sorted(LOGO_EXTENSIONS)}, got: {src.name!r}")
    dest = output_dir / src.name
    if dest.resolve() != src.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return file_entry(output_dir, src.name)


def _collect_readme(
    spec_dir: Path, output_dir: Path, explicit: Path | None
) -> FileEntry | None:
    """Discover an optional module readme, ship it, and hash it — the `_collect_logo` shape exactly.

    Uses an explicit path if given, else the first of `manifest.README_CANDIDATES` found beside the
    spec (`README.md` first). The file is copied into the module dir and returned as a hashed
    `FileEntry` kept OUT of `artifact.digest` *and* out of `content_signature`, so correcting a
    sentence is a PATCH rather than a new identity. Absent readme → `None`. Raises `ValueError` on an
    unsupported extension.

    **The exclusion is the point, not an oversight.** A readme is prose about the module, and the
    alternative of putting it in `artifact.files` was rejected by the consumer who asked for this
    (S25): on an immutable registry a fixed typo in a caveat would then cost a version number, and the
    corrected module would collide with its own predecessor under a content-dedup check. Nothing here
    reads the markup — the extension travels in the name for whoever renders it."""
    if explicit is not None:
        src: Path | None = Path(explicit)
    else:
        src = next(
            (spec_dir / name for name in README_CANDIDATES if (spec_dir / name).is_file()),
            None,
        )
    if src is None or not src.is_file():
        return None
    ext = src.suffix.lower().lstrip(".")
    if ext not in README_EXTENSIONS:
        raise ValueError(
            f"readme must be one of {sorted(README_EXTENSIONS)}, got: {src.name!r}"
        )
    dest = output_dir / src.name
    if dest.resolve() != src.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return file_entry(output_dir, src.name)


# ── File loading helpers ───────────────────────────────────────────────────────


def _load_yaml(
    path: Path, authority_keys: Iterable[str] | None = None
) -> tuple[ModuleSpecConfig | None, list[str], list[str]]:
    """Load and validate module_spec.yaml. Returns (config, errors, dropped_authority_keys).

    When `authority_keys` is given, the format's reference stripper removes those consumer/registry-
    owned identity keys from the `module:` block *before* validation (inject-only — the caller supplies
    the set, e.g. `just_dna_format.normalize.IDENTITY_AUTHORITY_KEYS`). The validator itself stays
    strict: any key NOT in the injected set still trips `extra="forbid"`. `dropped` is the sorted list
    of keys actually removed, for the caller to surface as INFO."""
    if not path.exists():
        return None, [f"module_spec.yaml not found at {path}"], []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        # A syntax error is the most likely mistake in a hand-written file, and it used to come out as
        # an unhandled `yaml.parser.ParserError` traceback from inside `validate` — for the one command
        # whose whole job is to report problems in a form an author can act on. pyyaml's own message
        # locates the line and column, so it is kept verbatim and merely labelled.
        return None, [f"module_spec.yaml is not valid YAML: {exc}"], []
    if raw is None:
        return None, ["module_spec.yaml is empty"], []
    if not isinstance(raw, dict):
        # A scalar or a list parses fine and then dies in `model_validate` with a pydantic message
        # about the wrong input type, which does not name the actual problem.
        return None, [
            f"module_spec.yaml must be a mapping of top-level keys (module:, defaults:, …), not "
            f"{type(raw).__name__}"
        ], []
    dropped: list[str] = []
    if authority_keys and isinstance(raw, dict) and isinstance(raw.get("module"), dict):
        raw["module"], dropped = strip_authority_keys(raw["module"], authority_keys)
    try:
        return ModuleSpecConfig.model_validate(raw), [], dropped
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = " → ".join(str(x) for x in err["loc"])
            errors.append(f"module_spec.yaml [{loc}]: {err['msg']}")
        return None, errors, dropped


def load_csv_rows(
    path: Path, row_model: type, file_label: str, genome_build: str = DEFAULT_GENOME_BUILD
) -> tuple[list[Any], list[str], list[str]]:
    """Load a CSV and validate each row against a Pydantic model. Returns (rows, errors, warnings).

    **Public as of 0.5.1 (RM41), and it was public in practice long before.** This is the only correct
    way to turn an authored CSV into row models, `just-dna-enricher` consumes it across a package
    boundary in a dozen places, and a downstream consumer wiring the pipeline server-side had the
    choice of reaching for a private symbol or re-implementing it. Re-implementing is a trap rather
    than a chore, because it is not `csv.DictReader` plus `Model(**row)` — it carries the two rules
    below, each of which this workspace has already had to fix once:

    * **an empty cell becomes `None`, and the key is kept.** `MeasureBinRow.measure_kind` has a
      default, so `is_required()` is `False`, but the model then receives `None` rather than its
      default and fails on type. A `""` where this would have put `None` is a different failure again.
    * **`genome_build` is told to each row** (below), so a loader that omits it mints GRCh38
      identities for a GRCh37 module.

    `_load_csv_rows` remains as an alias so no caller breaks.

    `genome_build` is **told to each row**, not read from it. A coordinate is not absolute, so a row
    deriving an identity from one needs the module's assembly — and a pydantic model built from a CSV
    dict has no `module_spec.yaml` in scope. Injecting it here keeps the build declared exactly once
    (the yaml) while reaching every row: it is a private attribute, so it is not a column, reaches no
    parquet, and moves no digest. See `AuthoredModel._genome_build` for why per-row or per-CSV
    declaration was rejected. Callers that load a build-independent table — the resolution and fact
    sidecars, which carry their own `genome_build` column — leave it at the default and are unaffected.
    """
    errors: list[str] = []
    rows: list[Any] = []
    if not path.exists():
        return [], [f"{file_label} not found at {path}"], []

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [], [f"{file_label} has no header row"], []
        for line_num, raw_row in enumerate(reader, start=2):
            # DictReader buckets any cells past the header under the `None` key (a list). Silently
            # dropping them would let a shifted/surplus column slip past `extra="forbid"` — a real
            # authoring error (a misaligned row) reported as valid. Flag a non-empty surplus instead.
            surplus = [s for s in (raw_row.get(None) or []) if isinstance(s, str) and s.strip()]
            if surplus:
                errors.append(
                    f"{file_label} line {line_num}: more values than header columns "
                    f"(surplus: {surplus}) — check for a shifted or extra column"
                )
                continue
            cleaned = {
                k.strip(): (v.strip() if isinstance(v, str) and v.strip() != "" else None)
                for k, v in raw_row.items()
                if k is not None
            }
            try:
                row = row_model.model_validate(cleaned)
                if isinstance(row, AuthoredModel):
                    row.with_genome_build(genome_build)
                rows.append(row)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors.append(f"{file_label} line {line_num} [{loc}]: {err['msg']}")
    return rows, errors, []


#: The pre-0.5.1 spelling. Kept because it is imported across a package boundary and by consumers
#: outside this workspace; a rename that breaks them buys nothing. Not deprecated — same function,
#: two names, one of which no longer lies about being internal.
_load_csv_rows = load_csv_rows


def load_spec_variants(spec_dir: Path) -> tuple[list[VariantRow], list[str], list[str]]:
    """A spec directory's `variants.csv`, loaded and re-stamped for the build the module declares.

    The other half of RM41. Two enricher checks take rows rather than a `spec_dir` —
    `acmg.verify_acmg_sf` and `identifiers.check_identifiers` — unlike every other pass, so a caller
    has to do this itself, and doing it *right* means three steps rather than one: read the declared
    build out of `module_spec.yaml`, inject it into every row, and then re-stamp the identities, since
    `VariantRow._freeze_identity` runs at construction where the yaml is not in scope.

    Missing or unreadable yaml falls back to `DEFAULT_GENOME_BUILD`, matching what compiling that
    directory would assume — this is a read-only check helper, not the enrichment path, which refuses
    rather than choose a build for a module whose declaration cannot be read (it writes facts back).

    Returns `(variants, errors, warnings)`; an absent `variants.csv` is an empty list and one error,
    exactly as `load_csv_rows` reports it.
    """
    spec_dir = Path(spec_dir)
    config = None
    if (spec_dir / "module_spec.yaml").exists():
        config, _, _ = _load_yaml(spec_dir / "module_spec.yaml")
    build = config.genome_build if config else DEFAULT_GENOME_BUILD
    variants, errors, warnings = load_csv_rows(
        spec_dir / "variants.csv", VariantRow, "variants.csv", genome_build=build
    )
    warnings.extend(_restamp_for_build(variants, build))
    return variants, errors, warnings


# ── Cross-row validation ───────────────────────────────────────────────────────


def _cross_validate_variants(variants: list[VariantRow]) -> tuple[list[str], list[str]]:
    """Validate consistency across variant rows. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    # Only compare rows that actually carry a position. A key seen once with a position and again
    # without one (e.g. an rsid authored with coords on the het row but not the hom row, or a row
    # awaiting resolution) is NOT a conflict — comparing `(None, None)` against a real position was a
    # false positive. Two *positioned* rows for one key that disagree are still an error.
    key_positions: dict[str, tuple[str, int]] = {}
    # `ref` is checked separately from the position because a VA-derived key (0.5) addresses the
    # *place and the alt* — the reference base at a position is a fact of the genome, so VRS does not
    # encode it. That is correct VRS semantics but it drops a guarantee the old `chrom:start:ref:alts`
    # key gave for free: two rows at one position claiming different reference bases used to be two
    # keys, and now they are one. Exactly one of them can be right, so catching it here keeps the
    # authored-typo diagnosis the switch would otherwise have lost.
    key_refs: dict[str, str] = {}
    for row in variants:
        if row.chrom is None or row.start is None:
            continue
        key = row.variant_key
        pos = (row.chrom, row.start)
        if key in key_positions:
            if key_positions[key] != pos:
                errors.append(f"Inconsistent positions for {key}: {key_positions[key]} vs {pos}")
        else:
            key_positions[key] = pos
        if row.ref is not None:
            if key in key_refs:
                if key_refs[key] != row.ref:
                    errors.append(
                        f"Inconsistent reference allele for {key}: {key_refs[key]!r} vs {row.ref!r} "
                        f"at {row.chrom}:{row.start} — the reference base at a position is a single "
                        f"fact, so at most one of these is correct"
                    )
            else:
                key_refs[key] = row.ref

    seen_keys: set[tuple[str, str]] = set()
    for row in variants:
        key = (row.variant_key, row.genotype)
        if key in seen_keys:
            errors.append(f"Duplicate (variant, genotype): ({row.variant_key}, {row.genotype})")
        seen_keys.add(key)

    for row in variants:
        # `state`/`weight` sign consistency (legacy), plus the same check on the new `direction`.
        if row.weight is not None:
            if row.state == "risk" and row.weight > 0:
                warnings.append(
                    f"{row.variant_key} genotype {row.genotype}: state='risk' but weight={row.weight} > 0"
                )
            if row.state == "protective" and row.weight < 0:
                warnings.append(
                    f"{row.variant_key} genotype {row.genotype}: state='protective' but weight={row.weight} < 0"
                )
            if row.direction == "risk" and row.weight > 0:
                warnings.append(
                    f"{row.variant_key} genotype {row.genotype}: direction='risk' but weight={row.weight} > 0"
                )
            if row.direction == "protective" and row.weight < 0:
                warnings.append(
                    f"{row.variant_key} genotype {row.genotype}: direction='protective' but weight={row.weight} < 0"
                )
    return errors, warnings


def _restamp_for_build(variants: list[VariantRow], genome_build: str) -> list[str]:
    """Re-derive `variant_key` against the module's declared build. Returns warnings.

    **The guard existed, was correct, and was never reached.** `derive_variant_key` takes a `build`
    and documents that "any other build falls through to case 3 rather than minting an id that would
    claim the wrong sequence" — but `VariantRow._freeze_identity` runs at row construction, where
    there is no module and therefore no declared build, so it always called the GRCh38 default. A
    module declaring `genome_build: GRCh37` therefore minted GRCh38 VRS allele ids for GRCh37
    coordinates, silently, with no warning anywhere.

    That is an identity corruption, not a cosmetic one, and it goes both ways. `vrs.py` opens by
    promising the opposite — "GRCh38 and GRCh37 mint distinct, correctly non-colliding ids instead of
    silently baking one build into the key". Probed on a real pair: HFE C282Y sits at 6:26092913 on
    GRCh38 and 6:26093141 on GRCh37, and a GRCh37 module at 26093141 minted
    `ga4gh:VA.TWxWV6SkC5-…` — byte-identical to the id a *GRCh38* module claiming that coordinate
    gets, which is a different place in the genome 228 bp away. Two modules about different loci
    shared one content-addressed identity.

    The compiler is where this can be fixed because it is the only tier holding both the row and the
    spec. Re-stamping is not a new concept here — the resolver already re-keys on one-to-many
    expansion — and it is a no-op on GRCh38, which is every module today.
    """
    if genome_build == "GRCh38":
        return []
    restamped = 0
    for row in variants:
        key = derive_variant_key(
            row.rsid, row.chrom, row.start, row.ref, row.alts, build=genome_build
        )
        if key != row.variant_key:
            row.variant_key = key
            restamped += 1
    if not restamped:
        return []
    return [
        f"genome_build is {genome_build!r}: GA4GH VRS allele identity is GRCh38-only (RM15), so "
        f"{restamped} variant(s) are keyed by coordinate instead. A coordinate key is "
        f"**build-relative** — it will not join against GRCh38-keyed data, and the same key means a "
        f"different locus on another build. Publish GRCh38 coordinates if the module is meant to "
        f"join against gnomAD, ClinVar or ClinGen."
    ]


def _check_contig_ploidy(variants: list[VariantRow], genome_build: str = "GRCh38") -> list[str]:
    """Non-diploid guardrail (ROADMAP 0.3 item 5b): MT and Y against a two-allele genotype.

    **Run where `chrom` is final — after resolution, not before.** It used to live inside
    `_cross_validate_variants`, which is called twice: once on the authored rows and once on the
    resolved ones, the second time taking *errors only* ("warnings were already surfaced"). That is
    correct for a warning computed from authored cells and wrong for this one, whose entire input —
    `chrom` — is the thing resolution fills. The result was a check whose coverage depended on
    authoring style rather than on the data: `MT,3243,A/G` written by hand warned, while
    `rs199474657` with genotype `A/G` — the same MELAS variant, the same fake-diploid error, and the
    shape *every drafting provider emits* — was silently unchecked.

    **X is excluded**, as before: it is diploid in XX samples, so a two-allele X row is legitimate and
    warning on it would be pure noise.

    **Y is not the false-positive-free half it was documented to be.** PAR1 and PAR2 recombine with X
    and are diploid in every karyotype, so a two-allele genotype at `Y:359845` is *correct* and the
    old advice ("use a single-allele genotype") would have made the annotation wrong. Real instance:
    `rs6603251` maps to X:359845 **and** Y:359845, and a one-to-many expansion produces the Y row on
    its own — the author never chose it. The premise that "PAR vs non-PAR needs coordinates the format
    does not resolve" was the error: `resolution.csv` resolves exactly that, and the PAR intervals are
    assembly constants of the same class as `vrs.REFGET_GRCh38`.

    So the answer is three-valued (`vrs.in_pseudoautosomal_region`), and the uncertain case is
    reported rather than either asserted or swallowed — the same shape as the `absent` rsID message,
    which names both readings and commits to neither.
    """
    warnings: list[str] = []
    for row in variants:
        if row.chrom not in {"MT", "Y"} or not ("/" in row.genotype or "|" in row.genotype):
            continue
        # MT has no pseudoautosomal region at all, so its verdict never depends on a coordinate.
        par = False if row.chrom == "MT" else in_pseudoautosomal_region(
            row.chrom, row.start, build=genome_build
        )
        if par is True:
            continue
        if par is None:
            # Reachable in practice only for a build with no PAR table: `VariantRow` already refuses
            # `chrom` without `start`, so a Y row always has a position, and an unresolved row has no
            # `chrom` at all and never reaches here. The message therefore names the *build* rather
            # than inventing a missing coordinate, and asserts neither reading — the same shape the
            # `absent` rsID message uses.
            warnings.append(
                f"{row.variant_key} genotype {row.genotype}: chrom=Y with two alleles on build "
                f"{genome_build!r}, which has no pseudoautosomal table here — so whether this locus "
                f"is diploid could not be decided. Outside PAR1/PAR2 Y is hemizygous and this should "
                f"be a single allele (e.g. 'G'); inside them the genotype is right."
            )
            continue
        warnings.append(
            f"{row.variant_key} genotype {row.genotype}: chrom={row.chrom} is not diploid here — use "
            f"a single-allele genotype (e.g. 'G') for a homoplasmic/hemizygous call"
        )
    return warnings


def _coordinate_label(row: Any) -> str:
    """How one offending row is named in a grouped message: its coordinate, and its rsid if it has one.

    Not `variant_key`: for exactly the rows this reports, the key *is* the coordinate (an impossible
    position mints no VRS id), so naming both would print the same numbers twice. The rsid is the one
    thing worth adding, because it is what the author will search their CSV for.
    """
    rsid = getattr(row, "rsid", None)
    return f"{row.chrom}:{row.start}" + (f" ({rsid})" if rsid else "")


class _CoordinateTable(NamedTuple):
    """One table's rows, the build they are recorded under, and who wrote them.

    `authored` decides the **remedy**, not the verdict. "Declare `genome_build: GRCh37`" is sound
    advice about a table a human typed and nonsense about `resolution.csv`, whose build is a per-row
    column on a machine-written sidecar: a GRCh37 module can carry a stale row stamped `GRCh38`, and
    telling its author to declare the build they already declared sends them to the wrong file. The
    fix there is to delete the sidecar and re-run the enricher.
    """

    label: str
    build: str
    authored: bool
    rows: Iterable[Any]


def _check_build_coordinates(tables: Iterable[_CoordinateTable]) -> list[str]:
    """Coordinates that cannot exist in the build they are recorded under (RM48). Errors, both modes.

    An author curating from older literature has hg19/GRCh37 coordinates and the module must be
    GRCh38. Nothing in these packages converts, so the conversion happens off-tool and lands as an
    ordinary authored coordinate carrying no provenance at all — and the two shapes below are the ones
    that are **provably** wrong with no sequence, no network and no provisioned asset, which is what
    puts them in the compiler rather than the enricher:

    - **a position past the end of its contig.** GRCh38's chromosome 1 ends at 248,956,422 and
      GRCh37's runs to 249,250,621, so an un-lifted coordinate in that 294 kb tail is a claim about a
      base that does not exist. When the position *is* inside another tabled build's contig the
      message says which — that is the whole diagnosis, and it costs one dict lookup.
    - **a contig named by only one build.** The 25 primary contigs are spelled identically in both, so
      this is entirely about unplaced scaffolds: `GL000209.1` is GRCh37's and `KI270728.1` is
      GRCh38's, and neither exists in the other. A shared scaffold, a patch, an alt locus or an
      unversioned accession settles nothing and is left alone (`vrs.sole_build_naming_contig`).

    **Error in both modes**, which is the `_cross_validate_variants` inconsistent-reference-allele
    class rather than a mode ladder: `strict` means *reproducible artifact*, and these rows are not
    unreproducible, they are false. Nothing downstream can catch them either — a VRS id minted at an
    impossible position is a correct digest of the wrong input, exactly as the 3,038-row off-by-one
    was.

    Findings are grouped by **reason** (table, contig, and which other build explains it) rather than
    by row, because a wrong-build panel produces one of these per variant: 2,400 rows disagreeing one
    by one reads as hopeless, while "2,400 rows carry GRCh37 coordinates" is a one-line fix. The
    `summarize_ref_mismatches` shape, on the offline half.

    Each table arrives as a `_CoordinateTable` — the build travels *per table* because
    `resolution.csv` records its own on every row and a module's yaml speaks only for the authored
    ones; comparing a resolution row against the module's declared build would be the wrong question
    for a row that says which build it is in. `authored` picks the remedy for the same reason.
    """
    beyond: dict[tuple[str, str, bool, str, tuple[str, ...]], list[str]] = {}
    misnamed: dict[tuple[str, str, bool, str, str], list[str]] = {}
    for label, build, authored, rows in tables:
        for row in rows:
            chrom, start = getattr(row, "chrom", None), getattr(row, "start", None)
            if chrom is None:
                continue
            elsewhere = sole_build_naming_contig(chrom)
            if elsewhere is not None and elsewhere != build:
                misnamed.setdefault(
                    (label, build, authored, str(chrom), elsewhere), []
                ).append(_coordinate_label(row))
                continue
            length = contig_length(chrom, build)
            if start is None or length is None or start <= length:
                continue
            others = tuple(b for b in builds_containing_position(chrom, start) if b != build)
            beyond.setdefault((label, build, authored, str(chrom), others), []).append(
                _coordinate_label(row)
            )

    errors: list[str] = []
    for (label, build, authored, chrom, others), found in beyond.items():
        length = contig_length(chrom, build)
        if others:
            elsewhere = others[0]
            explanation = (
                f"every one of those positions is inside {elsewhere}'s {chrom} "
                f"({contig_length(chrom, elsewhere):,} bp), so this reads as an un-lifted "
                f"{elsewhere} coordinate under a {build} heading. Recover the rs-numbers with "
                f"`just-dna-enricher hint recover --chrom {chrom} --start …` and author those "
                f"instead — an rs-number resolves into a coordinate the compiler can cross-examine, "
                f"where a converted position is its own only witness. Or "
                + _build_remedy(authored, elsewhere)
            )
        else:
            explanation = (
                f"no build this compiler knows has a contig {chrom} that long, so the position is "
                f"wrong in every frame — check the contig and the position together"
            )
        errors.append(
            f"{label}: {len(found)} row(s) place a variant past the end of {chrom} on {build} "
            f"({length:,} bp) — {explanation} ({_examples(found)})"
        )
    for (label, build, authored, chrom, elsewhere), found in misnamed.items():
        errors.append(
            f"{label}: {len(found)} row(s) name contig {chrom}, which is a top-level sequence of "
            f"{elsewhere} and of no other build this compiler knows, while the rows are recorded as "
            f"{build}. A coordinate on it means nothing here: fix the contig, or "
            + _build_remedy(authored, elsewhere)
            + f" ({_examples(found)})"
        )
    return errors


def _build_remedy(authored: bool, elsewhere: str) -> str:
    """Where the build is actually declared for this table — which is not the same file for both."""
    if authored:
        return f"declare `genome_build: {elsewhere}` if the whole module is on that assembly."
    return (
        f"delete the sidecar and re-run `just-dna-enricher enrich` if these rows are stale — the "
        f"build is a per-row column here, not the module's declaration, so a module already "
        f"declaring {elsewhere} can still carry rows stamped otherwise."
    )


#: The 0.4 table kinds that can name a locus, derived from the models rather than listed: a table is
#: positional exactly when it declares both `chrom` and `start`. Today that is `heteroplasmy.csv`,
#: `haplotypes.csv` and `pharm_variants.csv`. Hand-keeping this would be the `SOURCES_FIELDNAMES`
#: mistake again — a list that silently loses a member.
#:
#: **What the rest of the kinds are is two different things, and this comment used to call them one
#: (RM65).** It read "the rest are gene- or score-keyed and are not joinable by position at all, which
#: is a property of what they describe rather than a gap". True of `allele_function.csv` and `pgs.csv`,
#: which describe an allele's function and a score — neither has a place on a contig. **False of
#: `repeat_alleles.csv` and `copynumbers.csv`**, and the spec says so: VCF 4.4 §5.6 has POS and INFO
#: SVLEN specify the genomic interval a copy number is defined over, and §5.7 says a `<CNV:TR>`
#: record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based
#: callers"*. A tandem repeat and a copy-number segment are loci with coordinates, emitted at fixed
#: published positions — so their non-joinability is a **gap in this schema**, not a property of the
#: thing described, and a consumer holding an ExpansionHunter or `<CNV:TR>` VCF has to annotate a gene
#: symbol for themselves to reach our HTT row. The columns that would close it wait for 0.7+, gated on
#: a real repeat-caller sample; what is corrected here is the claim, because a claim the spec
#: contradicts is a defect in its own right whatever release fixes the underlying gap.
_POSITIONAL_TABLE_KINDS: tuple[tuple[str, type[BaseModel]], ...] = tuple(
    (csv_name, model)
    for csv_name, _parquet, model in _TABLE_KINDS
    if {"chrom", "start"} <= set(model.model_fields)
)


def _apply_positional_resolution(
    rows_by_csv: dict[str, list[Any]],
    resolution_table: dict[str, list[ResolutionRow]],
    genome_build: str = DEFAULT_GENOME_BUILD,
    *,
    resolve: bool = True,
) -> tuple[list[str], bool]:
    """Join the injected `resolution.csv` onto every positional 0.4-family table (RM43).

    Returns `(warnings, applied)`. **`applied` is load-bearing, not bookkeeping**: it is what lets
    `_check_positional_joinability` say *why* a row is still unplaced without asserting a reason the
    join never reached. Every gate below turns it off, and each is a different situation — no table to
    consult, no positional rows, a non-GRCh38 module, a caller that asked for no resolution — but they
    share the one consequence that matters downstream, which is that nothing was looked up.

    The compiler-side half of `resolution.resolve_positional_rows` — it picks the tables, handles the
    build gate, and collapses the per-row findings into one line per table. Rows are filled **in
    place**, so a caller that holds the lists gets the resolved rows back; run it before `_build_table`
    materializes them, and before `_check_positional_joinability`.

    Runs in `validate_spec` as well as `compile_module`, and it must: the joinability warning is
    computed from these rows in both, so filling on one side only would leave the pre-flight reporting
    a gap the compile had already closed — and that sentence carries `UNJOINABLE_PHRASE`, which a
    catalog reads as a trust signal (RM44). `resolve` is threaded from `resolve_with_ensembl` for the
    same reason: it is the master switch for resolution of every kind, so a pre-flight that ignored it
    would be the more *optimistic* of the two commands, which is the disagreement direction this
    repo's parity rule exists to prevent. Pure computation over injected bytes with no `output_dir`,
    which is the standing test for what belongs in both.

    **Skipped, with a warning, for a non-GRCh38 module**, exactly as `resolve_from_table` skips: the
    identity minting behind these keys is GRCh38-only (RM15), so joining a table the compiler cannot
    re-derive a key for would place rows against loci it has no way to check.
    """
    positional = [
        (csv_name, rows_by_csv.get(csv_name) or []) for csv_name, _model in _POSITIONAL_TABLE_KINDS
    ]
    if not resolve or not resolution_table or not any(rows for _csv, rows in positional):
        return [], False
    if genome_build != DEFAULT_GENOME_BUILD:
        return [
            f"Positional-table fill skipped: the compiler is GRCh38-bound and this module's "
            f"genome_build is {genome_build!r}, so the injected resolution table is not joined onto "
            f"{', '.join(name for name, rows in positional if rows)} (RM15). Those rows keep the "
            f"coordinates their author typed."
        ], False
    warnings: list[str] = []
    for csv_name, rows in positional:
        if not rows:
            continue
        report = resolve_positional_rows(rows, resolution_table, genome_build)
        if report.contradicted:
            warnings.append(
                f"{csv_name}: {len(report.contradicted)} row(s) authored an identity the resolution "
                f"table disagrees with, and are left exactly as authored — "
                f"{_examples(report.contradicted)}"
            )
    return warnings, True


#: **A downstream trust badge substring-matches this phrase, so it is a contract, not prose (S13).**
#: `compile_module` copies its warnings into `manifest.compilation.warnings`, which ships inside
#: `manifest.json` — and a catalog reindexing from a published manifest has no spec directory left to
#: re-derive anything from, so the *sentence* is the only surviving record that a table joins to
#: nothing. `just-dna-registry` 0.11.3 pins `UNJOINABLE_MARKER = "have no chrom+start"` in its facet
#: builder against exactly this, after the vacuous `fully_resolved` granted trust to modules that
#: annotate nothing. Rewording the phrase silently re-grants that trust.
#:
#: So it is named here rather than inlined: the rest of the sentence is free to improve, this fragment
#: is not, and a change to it is a deliberate act with a consumer to tell. The real repair is a
#: structured field a consumer can read instead of prose — RM44 — after which this can move again.
UNJOINABLE_PHRASE = "have no chrom+start"


def _table_row_key(row: Any, genome_build: str) -> str | None:
    """The `variant_key` a 0.4-family row resolves under, exactly as the enricher derives it.

    All three positional models stamp the column since 0.6 (RM43) — `HaplotypeRow` had none at all
    before, and `enrich._collect_subjects` derived one inline with
    `derive_variant_key(rsid, chrom, start, ref)`, *without* `alts`, because a haplotype's defining
    allele is not the row's identity. The stamped key is that same expression, frozen at load from the
    authored columns, so this keeps agreeing with the table it reads. The fallback stays for a row
    built outside the loader and for a caller passing something older.
    """
    key = getattr(row, "variant_key", None)
    if key:
        return str(key)
    return derive_variant_key(
        getattr(row, "rsid", None), row.chrom, row.start, getattr(row, "ref", None),
        build=genome_build,
    )


def _check_positional_joinability(
    rows_by_csv: dict[str, list[Any]],
    resolution_table: dict[str, list[ResolutionRow]],
    genome_build: str = DEFAULT_GENOME_BUILD,
    *,
    fill_applied: bool = True,
) -> list[str]:
    """Which 0.4-family rows a consumer cannot join to a VCF by position, and why the fill left them.

    **Run AFTER `_apply_positional_resolution`, in both `validate_spec` and `compile_module`.** Until
    0.6 this reported the whole gap — resolution was SNP-core-scoped, so an rsid-authored PGx module
    compiled clean, validated, published, and had a null `chrom`/`start` on every row; the consumer
    who reported it had a 1,482-row module in that state and found out by reading parquet. RM43 closed
    that, and what is left for this check is the residue: rows the injected table does not place, or
    places at more than one locus.

    Reported as **counts per table, never a line per row**, and the second half is the interesting
    one — *why* a row is still unplaced. Three readings, and the author's next move differs:

    * the table names the key at **several** loci (or at loci the row's own allele contradicts), so
      the compiler leaves it rather than picking one — the same refusal `resolve_from_table` makes,
      and not something an enrich re-run fixes;
    * **nothing** in the table names the key at all, which an enrich run does fix;
    * the fill **never ran** (`fill_applied=False` — `--no-resolve`, a non-GRCh38 module), in which
      case the coordinates may well be right there and untried. That third branch is why the flag is a
      parameter rather than something inferred from `placeable`: the reason sentence lands in
      `manifest.compilation.warnings` beside `UNJOINABLE_PHRASE`, which is a published consumer
      surface (RM44), and asserting "the compiler looked and would not pick" about a lookup that never
      happened is a fabricated diagnosis in a document a catalog reads.

    A **partial** coordinate is counted apart because it is the more deceptive shape: `haplotypes.csv`
    drafted from CPIC carries a `start` with no `chrom` (CPIC publishes a position on
    `sequence_location` and the chromosome on `gene`), which reads as a coordinate and joins to nothing.

    **A warning in both modes, and deliberately never a `strict` error.** Rsid-only identity is legal
    by these models' own rule (`rsid`, *or* `chrom`+`start`), so escalating would make `--strict` mean
    "author coordinates into your PGx tables" — the format tightening a field it deliberately left
    open. And what remains after the fill is, by construction, something no authored edit to *this*
    table clears: it is the `not_covered` / VRS-coverage class, where refusing would make a correct
    module uncompilable for a reason its author cannot act on.
    """
    warnings: list[str] = []
    for csv_name, _model in _POSITIONAL_TABLE_KINDS:
        rows = rows_by_csv.get(csv_name) or []
        unplaced = [row for row in rows if row.chrom is None or row.start is None]
        if not unplaced:
            continue
        partial = [row for row in unplaced if row.chrom is not None or row.start is not None]
        placeable = [
            row
            for row in unplaced
            if any(
                r.chrom is not None and r.start is not None
                for r in resolution_table.get(_table_row_key(row, genome_build) or "", [])
            )
        ]
        # **`fill_applied` is tested FIRST, and the order is the whole point.** It used to sit in the
        # `elif`, behind `if not placeable`, which made the third reading unreachable on exactly the
        # modules it describes: when the fill never runs, `resolution.csv` is whatever the enricher
        # left, and on a non-GRCh38 module the enricher declines to resolve, so it holds only the
        # coordinates the author typed — meaning `placeable` is empty for precisely the rsid-only
        # rows, and the author was told "no resolution.csv row places them — run enrich first" one
        # line below a warning explaining that the fill was skipped because their module is GRCh37.
        # They had just run enrich, and on that build it can never place those rows. A remedy that
        # cannot work is worse than no remedy: it sends an author to re-run a command whose own
        # output already told them why it would not help.
        # `fill_applied` is False for four different situations and only some of them are "the table
        # was not consulted": no table at all, no positional rows, a non-GRCh38 module, and
        # `--no-resolve`. So it is conjoined with *a table being present* — with none, "run enrich"
        # is exactly the right advice and the branch below keeps it.
        if not fill_applied and resolution_table:
            named = (
                f"resolution.csv names {len(placeable)} of them and was"
                if placeable
                else "the resolution table was"
            )
            detail = f"{named} not consulted for this table — see the skip reported above"
        elif not placeable:
            detail = "no resolution.csv row places them — run `just-dna-enricher enrich` first"
        else:
            detail = (
                f"resolution.csv names {len(placeable)} of them, but at more than one locus or at "
                f"one the row's own allele contradicts, so the compiler leaves them unplaced rather "
                f"than picking"
            )
        partial_note = (
            f" {len(partial)} carr{'ies' if len(partial) == 1 else 'y'} one half of a coordinate "
            f"(a start with no chrom, or the reverse), which reads as a position and is not one."
            if partial
            else ""
        )
        warnings.append(
            f"{csv_name}: {len(unplaced)} of {len(rows)} row(s) {UNJOINABLE_PHRASE}, so this table "
            f"joins by rsID only — a VCF whose ID column is empty matches none of them. {detail}."
            f"{partial_note}"
        )
    return warnings


#: The binning table kinds, derived from the models for the same reason `_POSITIONAL_TABLE_KINDS` is:
#: a kind is a binning kind exactly when its model is a `MeasureBinRow`, and a hand-kept list of the
#: four would silently lose the fifth.
_BINNING_TABLE_KINDS: tuple[tuple[str, type[BaseModel]], ...] = tuple(
    (csv_name, model)
    for csv_name, _parquet, model in _TABLE_KINDS
    if isinstance(model, type) and issubclass(model, MeasureBinRow)
)


def _check_binning_grounding(
    rows_by_csv: dict[str, list[Any]], studies: list[StudyRow]
) -> list[str]:
    """A binning table asserting thresholds with no evidence recorded anywhere in the module (S19).

    **Grounding is enforced where it is most often automatic and silent where it is most
    interpretive.** `studies.csv` is required iff `variants.csv` is present, and a `variants.csv` row
    is frequently drafted from ClinVar with citations already attached. A bin *boundary* is the
    opposite: where 36 rather than 35 CAG becomes "reduced penetrance" is a clinical judgement drawn
    from a specific literature, it is exactly the number a reader would want to check, and until this
    check the format asked for nothing and said nothing. `reference_examples/htt_repeat_expansion`
    compiled green under `--strict` stating four thresholds with no citation anywhere, and its own
    README says "a module making a novel claim should carry its evidence" — advice the schema had no
    place to take.

    **The remedy became sayable in 0.6 (RM47).** Until then this could report an absence and never a
    *link*: `studies.csv` identified its subject by rsid or `chrom`, and an `activity_phenotype.csv` /
    `copynumbers.csv` / `repeat_alleles.csv` row is keyed `(gene, …)`, so a study row grounded the
    module and no rule could tie it to a bound. `MeasureBinRow.pmid` is now the tie — a pointer on the
    row that states the threshold — and `StudyRow`'s subject requirement was relaxed in the same
    release so the citation row describing that paper need not invent a variant to hang off. So the
    message names one remedy for every kind, and the `heteroplasmy.csv`-only branch (whose rows can
    also be pointed at by identity, which is what `reference_examples/mt_heteroplasmy` does) is now an
    *additional* route rather than the only actionable one.

    **A bin that carries a `pmid` is grounded and is not counted**, derived from the row rather than
    the table. Fires only when the module records **no** study rows at all *and* some bin cites
    nothing: once an author has written a `studies.csv`, saying more would be nagging, and on a module
    carrying `variants.csv` the missing table is already a hard error, so this never doubles it.
    A warning in both modes: the remedy is an authored edit, but `strict` means *reproducible
    artifact*, an unrelated axis (P5), and a module that cites nothing still reproduces exactly.

    **A variant identity is not evidence, and treating it as one here was vacuous (D1-3).** A second
    exemption used to sit beside the `pmid` one: a bin naming a variant was counted as grounded,
    because a study row can name that variant back. Inside this function there is no study row — the
    early return has just established that the module records none — so the exemption cleared a bin
    against a citation that does not exist, and a `heteroplasmy.csv` module stating four thresholds
    and citing nothing was green and silent while the identical module on `repeat_alleles.csv` was
    warned. That is the S19 gap, reopened for the one binning kind a real MELAS/NARP module uses.
    Identity survives as the reason `heteroplasmy.csv` is offered a **second remedy** — a study row
    really can point at those bins — never as a reason to say nothing.
    """
    if studies:
        return []
    warnings: list[str] = []
    for csv_name, model in _BINNING_TABLE_KINDS:
        rows = [r for r in rows_by_csv.get(csv_name) or [] if not r.unresolved]
        # One way a bin is grounded in a module with no studies.csv, read off the row and never off
        # the table name: its own `pmid` (RM47, every kind). A variant identity is not a second way —
        # see the D1-3 paragraph above — it only decides which remedies this kind can be offered.
        ungrounded = [r for r in rows if r.pmid is None]
        if not ungrounded:
            continue
        remedy = (
            "cite the boundary itself: put the PubMed id on the bin row (`pmid`), and describe the "
            "paper in a studies.csv row, which since 0.6 need not name a variant"
        )
        # Read off `model_fields`, **not `hasattr`**: `variant_key` became a *stamped field* in 0.6
        # (RM43) and a field is not a class attribute, so `hasattr` silently answers `False` and every
        # heteroplasmy module gets the message written for a gene-keyed table. Two lanes of this same
        # release wrote these two lines — the `pmid` route and the `model_fields` repair — and the
        # `hasattr` spelling arrived with the first because RM43 had not landed under it yet.
        if "variant_key" in model.model_fields:
            remedy += (
                "; alternatively, a studies.csv row naming the variant these bins are about grounds "
                "them — this kind carries rsid/chrom+start, so fill those in if they are empty"
            )
        else:
            # Deliberately does NOT restate the pre-RM47 claim that nothing can point at these bins.
            # It was true and it is now retired: `pmid` on the bin is exactly the route that claim said
            # did not exist, and repeating it would leave an author reading a finding no edit can clear
            # — the defect this codebase treats as a defect everywhere else. Say which route applies to
            # a gene-keyed kind, and say it in the affirmative.
            key = ", ".join(f for f in model._KEY_FIELDS if f != "variant_key")
            remedy += (
                f"; for a ({key}) row the bin's own pmid is the route, because a study row can only "
                f"name a variant as its subject and never a bin, so it grounds the module while the "
                f"bin pointer grounds this threshold"
            )
        warnings.append(
            f"{csv_name}: {len(ungrounded)} of {len(rows)} bin(s) state a threshold and the module "
            f"records no grounding evidence at all (no studies.csv rows, no bin pmid). {remedy}."
        )
    return warnings


def _check_measure_shape(rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """Per binning table: what its integer tiling cannot express about its source measurement.

    A thin loop over `binning.measurement_shape_warnings`, which owns both findings (RM55, RM56) because
    it owns `_INTEGER_KINDS` — the set whose premise VCF 4.4 withdrew. The kinds are derived from the
    models via `_BINNING_TABLE_KINDS` for the same reason that tuple exists, so a sixth binning kind
    cannot silently escape the check.
    """
    warnings: list[str] = []
    for csv_name, _model in _BINNING_TABLE_KINDS:
        rows = rows_by_csv.get(csv_name) or []
        warnings.extend(f"{csv_name}: {w}" for w in measurement_shape_warnings(rows))
    return warnings


#: The fragment of the RM57 warning that names the finding, for the same reason the two phrases in
#: `binning` are named: a manifest carries the prose and no field.
QUAL_INVERSION_PHRASE = "QUAL means the opposite thing on the record this row is read from"

#: The one VCF column whose Phred-scaled assertion changes sign with the record (§1.6.1.6). Matched on
#: the bare token: a `quality_from` cell is `|`-alternated and may carry an `INFO/`-style namespace,
#: neither of which changes which field is named.
_INVERTING_QUALITY_FIELD = "QUAL"


def _quality_fields(pointer: str | None) -> list[str]:
    """The field tokens a pointer cell names, upper-cased and with any namespace stripped.

    A pointer is `|`-alternated, so `DP|QUAL` names two fields and both must be looked at; and a
    qualified spelling (`INFO/DP`) names the same field as its bare form, which is what the trailing
    `rsplit` is for. Case is folded because this feeds a *warning* — being generous about the spelling
    of the thing being warned about is the right direction to be wrong in.
    """
    if not pointer:
        return []
    return [part.rsplit("/", 1)[-1].strip().upper() for part in pointer.split("|") if part.strip()]


def _check_quality_inversion(variants: list[VariantRow]) -> list[str]:
    """A `requires_callable` row whose quality floor is stated against `QUAL` (RM57).

    §1.6.1.6 defines QUAL as *"−10log10 prob(variant)"* where ALT is `.` and *"−10log10 prob(no
    variant)"* otherwise — **the sign of the assertion flips with the record**. A QUAL of 60 on a variant
    record means the variant is almost certainly real; the same 60 on a monomorphic reference record
    means the position is almost certainly *variant*, which is the opposite of a clean reference call.

    `requires_callable` marks the rows where the *absence* of the variant is the informative call, and a
    consumer evaluating one reads the reference record — a gVCF `<*>` block (§5.5) or a monomorphic
    `ALT=.` record — which is exactly where QUAL is inverted. So `requires_callable=true,
    quality_from=QUAL, min_quality=30` asks the consumer to require evidence that the position *is*
    variant before asserting that it is not, and raising the floor makes the answer more confidently
    wrong rather than safer. `min_quality` is monotone in one direction only, so nothing else catches it.

    **A warning in both modes, and refusing the combination was considered and rejected.** A validator
    here would encode one reading of a field whose meaning depends on a record this tier will never see,
    and it would refuse the legitimate case — the same row read against a *variant* record elsewhere in
    the same file, where the floor means what its author intended. Aggregated to one line with examples,
    because a gene panel can carry hundreds of `requires_callable` rows and a line each would bury every
    other finding the run produces.
    """
    offenders = [
        v
        for v in variants
        if v.requires_callable is True
        and _INVERTING_QUALITY_FIELD in _quality_fields(v.quality_from)
    ]
    if not offenders:
        return []
    shown = ", ".join(str(v.variant_key) for v in offenders[:3])
    rest = f" (+{len(offenders) - 3} more)" if len(offenders) > 3 else ""
    return [
        f"variants.csv: {len(offenders)} row(s) set requires_callable=true and state their min_quality "
        f"floor against QUAL. {QUAL_INVERSION_PHRASE}: VCF §1.6.1.6 makes QUAL -10log10 prob(no "
        f"variant) on a variant record but -10log10 prob(variant) where ALT is '.', so on the reference "
        f"record a consumer must read to prove this absence, a HIGH QUAL says the position is probably "
        f"variant — and the higher the floor, the more confidently wrong the result. State the floor "
        f"against a per-sample confidence field instead (GQ), or against the reference block's MIN_DP. "
        f"e.g. {shown}{rest}."
    ]


#: The fragment of the RM58 warning that names the finding. Same reason as the phrases above.
MISSING_ALLELE_PHRASE = "is VCF's MISSING marker, not an allele"

#: Every authored table that declares an `alts` column, derived from the models rather than named: the
#: SNP core plus whichever table kinds carry one. A name list here would lose a kind the way
#: `SOURCES_FIELDNAMES` lost a column.
_ALTS_BEARING_KINDS: tuple[str, ...] = tuple(
    csv_name for csv_name, _parquet, model in _TABLE_KINDS if "alts" in model.model_fields
)


def _check_missing_allele_marker(
    variants: list[VariantRow],
    rows_by_csv: dict[str, list[Any]],
    genome_build: str = DEFAULT_GENOME_BUILD,
) -> list[str]:
    """An `alts` cell spelling VCF's MISSING marker, which splits the row's identity (RM58).

    `.` in ALT means *there are no alternate alleles* — a monomorphic reference record, which §1.1's own
    first worked example carries. No `ref`/`alts` column has a nucleotide grammar (deliberately: adding
    one would tighten the field RM5 exists to widen and would stop existing modules validating), so the
    cell loads, and `derive_variant_key` then folds it in as though it named an allele. The result is
    that a row writing `alts=.` and a row leaving the cell empty describe **one site under two keys** —
    `1:1:A:.` and `1:1:A` — with different `content_signature`s and no dedup between them. That is the
    only VCF-conformance finding in this batch that reaches identity, and until now nothing said a word
    about it: `alleles.non_nucleotide_reason` filed `.` under `"notation"` beside `<DEL>`, and the sites
    that consult it only run when a hosting verdict has already failed, which a monomorphic row never
    reaches.

    **A diagnosis, not a grammar** — the value is still accepted, exactly as `<DEL>` and `N` are. The
    remedy is an authored edit and an unambiguous one (leave the cell empty), which is what separates
    this from RM55/RM56 next door; it is still a warning in both modes, because `strict` means
    *reproducible artifact* and a module spelling `.` reproduces perfectly. Reported per table with a
    count and, where the split is real, the two keys side by side: on an rsid-authored row both keys are
    the rsid, so the cell is wrong without the identity consequence following, and claiming otherwise
    would be a false statement about that row.
    """
    warnings: list[str] = []
    tables: list[tuple[str, list[Any]]] = [("variants.csv", list(variants))]
    tables.extend((csv_name, rows_by_csv.get(csv_name) or []) for csv_name in _ALTS_BEARING_KINDS)
    for csv_name, rows in tables:
        offenders = [
            row
            for row in rows
            if any(
                non_nucleotide_reason(a) == "missing"
                for a in (getattr(row, "alts", None) or "").split(",")
            )
        ]
        if not offenders:
            continue
        # The identity split needs a coordinate, and **a row with no identity at all is not a split**.
        # Two shapes reach here without one and both must take the no-split branch. An rsid
        # short-circuits `derive_variant_key`, so both spellings of such a row key identically. And a
        # gene-only `heteroplasmy.csv` row — the pre-0.5 shape, still legal — has `variant_key is None`
        # while `derive_variant_key(None, None, None, None)` returns the *string* `'None:None:None'`, so
        # comparing the two always differs and the message read "e.g. None rather than None:None:None"
        # about a row that names no variant. Guard on the identity, never on the comparison.
        split: list[tuple[Any, str]] = []
        for row in offenders:
            key = getattr(row, "variant_key", None)
            if key is None:
                continue
            without = derive_variant_key(
                getattr(row, "rsid", None),
                getattr(row, "chrom", None),
                getattr(row, "start", None),
                getattr(row, "ref", None),
                build=genome_build,
            )
            if key != without:
                split.append((row, str(without)))
        if split:
            row, without = split[0]
            detail = (
                f"{len(split)} of them key differently from the same row with an empty cell (e.g. "
                f"{row.variant_key} rather than {without}), so this module and one authoring the same "
                f"site with the cell left empty carry two identities for one site, and neither "
                f"content_signature dedups against the other"
            )
        else:
            detail = (
                "no row's identity is affected — an rsid-keyed row keys the same either way, and a "
                "gene-keyed row names no variant at all — so the cell is simply claiming an allele "
                "that does not exist"
            )
        warnings.append(
            f"{csv_name}: {len(offenders)} row(s) write '.' in alts, which {MISSING_ALLELE_PHRASE} — "
            f"it states that the record has no alternate allele (VCF §1.6.1.5), so it is not the same "
            f"kind of thing as a symbolic allele like <DEL>. {detail}. Leave the cell empty instead."
        )
    return warnings


def _check_vcf_pointers(
    variants: list[VariantRow], rows_by_csv: dict[str, list[Any]]
) -> list[str]:
    """A VCF pointer that does not identify the field it points at (RM53), or that points at a list
    without saying which element (RM54).

    **A VCF field is not identified by its name.** It is identified by *namespace* — INFO and FORMAT
    are two reserved-key tables that collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and, since 4.4,
    `CN` — and described by *cardinality* (`Number`, which says how many values come back and what
    each one is of). Both readings of a colliding key are usually type-compatible, so nothing detects
    the confusion: a consumer reads a well-formed number of the wrong kind and bins it without error.
    `reference_examples/mt_heteroplasmy` shipped `source_field=AF` meaning this person's heteroplasmy
    fraction, where the spec's `AF` is the cohort frequency of the same ALT — one of those tells a
    carrier they are asymptomatic on the strength of how rare the variant is in a reference panel.

    **Two findings, both warnings in both modes.** The pointer grammar was widened rather than
    replaced, so a bare key is still legal and still means *unqualified* (P3); escalating under
    `strict` would refuse modules that compile today, and `strict` means *reproducible artifact*
    anyway — an unqualified pointer reproduces perfectly, it is only ambiguous (P5). The remedy for
    both is a one-cell authored edit, which is what separates them from the `not_covered` class.

    **What it declines to say.** The cardinality half reads `vocab.VCF_FIELD_NUMBER`, a transcription
    of the spec's own reserved-key tables, and answers `None` for anything not in them — a caller's
    private key (`REPCN` is ExpansionHunter's, not the spec's) has no cardinality this tier is
    entitled to assert, and asserting one would be a source convention wearing a fact (P2). Unknown
    withholds. It also answers `None` for a *bare* key whose two namespaces disagree (`CN` is `A`
    under INFO and `1` under FORMAT), which is exactly the case the collision half already names.

    **The mirror case — an element rule on a field the spec calls single-valued — is deliberately
    *not* reported.** It looks like the obvious second half of the cardinality check and it would fire
    on the correct authoring of the flagship case: a caller that packs several values into one cell
    declares that cell `Number=1, Type=String`, which is exactly what ExpansionHunter's `REPCN`
    (`17/42`) is. Separating "one value" from "several values in one string" turns on `Type`, which
    this tier does not model and which no `Number` can answer. Where it cannot decide, it withholds
    rather than accusing a correct row.

    **The two halves quantify over different column sets, and that is not an oversight.** The
    namespace question belongs to every pointer column (`VCF_POINTER_FIELDS`) — the decision names
    `callable_from=DP` as the same error `source_field=AF` is, one column over. The cardinality
    question is only askable where a column exists to answer it, and 0.6 built one companion
    (`VCF_POINTER_COMPANIONS`); telling an author to fill a column the schema does not have would be
    a finding no edit could clear, which this codebase treats as a defect wherever else it appears.

    Aggregated by reason rather than by row: a panel pointing every bin at one field would otherwise
    print the same sentence hundreds of times, and two reasons under one message is the other half of
    that mistake."""
    tables: list[tuple[str, list[Any]]] = [("variants.csv", variants)]
    tables.extend(
        (csv_name, rows_by_csv.get(csv_name) or []) for csv_name, _model in _BINNING_TABLE_KINDS
    )
    # (csv, pointer column, bare key) -> rows, and (csv, element column, atom, Number) -> rows.
    collisions: dict[tuple[str, str, str], int] = {}
    unselected: dict[tuple[str, str, str, str], int] = {}
    for csv_name, rows in tables:
        for row in rows:
            declared = type(row).model_fields
            for pointer_field in VCF_POINTER_FIELDS:
                if pointer_field not in declared:
                    continue
                pointer = getattr(row, pointer_field, None)
                if not pointer:
                    continue
                companions = [
                    element
                    for element, target in VCF_POINTER_COMPANIONS.items()
                    if target == pointer_field and element in declared
                ]
                selected = any(getattr(row, element, None) is not None for element in companions)
                for namespace, key in split_field_pointer(pointer):
                    if namespace is None and key in VCF_COLLIDING_KEYS:
                        seat = (csv_name, pointer_field, key)
                        collisions[seat] = collisions.get(seat, 0) + 1
                    if selected or not companions:
                        continue
                    number = vcf_field_number(namespace, key)
                    if is_multi_valued_number(number):
                        atom = key if namespace is None else f"{namespace}/{key}"
                        slot = (csv_name, companions[0], atom, number or "")
                        unselected[slot] = unselected.get(slot, 0) + 1
    warnings: list[str] = []
    if collisions:
        where = "; ".join(
            f"{csv_name} {pointer_field}={key} ({n} row(s))"
            for (csv_name, pointer_field, key), n in sorted(collisions.items())
        )
        keys = sorted({key for _csv, _field, key in collisions})
        reasons = " ".join(f"{key}: {VCF_COLLISION_REASONS[key]}." for key in keys)
        warnings.append(
            f"{sum(collisions.values())} VCF pointer cell(s) name a key that INFO and FORMAT both "
            f"define, so the pointer does not say which field it means: {where}. {reasons} Qualify "
            f"the pointer — INFO/{keys[0]} or FORMAT/{keys[0]} — a bare key stays legal and keeps "
            f"meaning unqualified, which is why this is a warning and not a refusal."
        )
    if unselected:
        where = "; ".join(
            f"{csv_name} {VCF_POINTER_COMPANIONS[element_field]}={atom} (Number={number}, "
            f"{VCF_NUMBER_MEANINGS.get(number, 'a value list')}; {n} row(s), {element_field} empty)"
            for (csv_name, element_field, atom, number), n in sorted(unselected.items())
        )
        warnings.append(
            f"{sum(unselected.values())} VCF pointer cell(s) point at a field the spec defines as "
            f"multi-valued and state no element rule, so the pointer names a list rather than a "
            f"number: {where}. Set the companion column to one of "
            f"{sorted(VALID_ELEMENT_RULES)} — on a Number=R field the reference is element zero, "
            f"which is why each ranging rule comes in a pair (largest counts it, largest_alt does "
            f"not)."
        )
    return warnings


def load_binning_rows(spec_dir: Path) -> dict[str, list[MeasureBinRow]]:
    """Every binning table present beside a spec, keyed by CSV name — the citations a module's
    *thresholds* carry (`MeasureBinRow.pmid`, RM47).

    Public because a second tier needs it: the enricher's literature pass has to check the bin
    pointers alongside `studies.csv`, and its two alternatives were importing a private symbol or
    hand-keeping a parallel list of the binning kinds — the RM40/RM41 shape exactly, and the list
    would go stale on the fifth kind. Row errors are raised rather than returned: a caller wanting the
    per-row diagnosis has `validate_spec`, and a pass reading citations out of a table it could not
    parse would silently under-report.
    """
    spec_dir = Path(spec_dir)
    config, _, _ = _load_yaml(spec_dir / "module_spec.yaml")
    declared_build = config.genome_build if config else DEFAULT_GENOME_BUILD
    out: dict[str, list[MeasureBinRow]] = {}
    for csv_name, model in _BINNING_TABLE_KINDS:
        # `spec_dir / csv_name`, never `_locate_sidecar`: that resolver is scoped to the
        # machine-written sidecars, and an authored table has exactly one legal name in exactly one
        # legal place (RM49/RM51). Both compile-side load loops read authored kinds this way, and a
        # reader that resolved them differently would find a table the compiler does not — which for
        # this function would mean the enricher writing `literature.csv` rows for citations
        # `_cross_check_literature` then reports as orphans.
        path = spec_dir / csv_name
        if not path.is_file():
            continue
        rows, errors, _ = _load_csv_rows(path, model, csv_name, genome_build=declared_build)
        if errors:
            raise ValueError(f"{csv_name} is invalid: {errors[0]}")
        out[csv_name] = rows
    return out


def binning_citations(rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """Digit-only PMIDs the binning tables cite (`MeasureBinRow.pmid`), de-duplicated.

    Takes the whole table-kind map a caller already holds and reads only the binning kinds out of it,
    so a caller cannot accidentally hand over a `haplotypes.csv` (no `pmid` column) and get an
    attribute error. The kind set is derived from the models, never hand-listed.

    First-occurrence order rather than sorted, because it feeds emission order downstream (P7), and
    normalization goes through `extract_pmids` so the bin pointer and `studies.csv` cannot drift into
    two spellings of one citation.
    """
    seen: dict[str, None] = {}
    for csv_name, _model in _BINNING_TABLE_KINDS:
        for row in rows_by_csv.get(csv_name) or []:
            if row.pmid:
                for pmid in extract_pmids(row.pmid):
                    seen.setdefault(pmid, None)
    return list(seen)


def _allowed_alleles(
    variant: VariantRow, resolution_table: dict[str, list[ResolutionRow]]
) -> tuple[set[str] | None, str]:
    """`(allele set, provenance)` for one variant — `(None, "unknown")` when nothing is comparable.

    The provenance shapes the diagnosis — it says where to go and look — but deliberately **not** the
    severity; `_check_allele_membership` explains why the obvious escalation is unsafe.

    - **authored** — the row itself carries `ref` *and* `alts`, so it contradicts itself. Note this
      does not mean a human wrote them: `reverse_module` emits both columns too.
    - **resolved** — the alleles come from `resolution.csv`, i.e. from whichever link won the variant.
      ClinVar carries only its *submitted* alleles while Ensembl carries every allele dbSNP knows, so a
      short alt list is a gap in the source at least as often as it is a defect in the module.

    `ref` without `alts` yields `None` deliberately: `{ref}` alone would flag every heterozygous
    genotype in the module, which is the normal shape of the data and not a finding.

    The resolved set is the **union over every locus** the key resolves to. A one-to-many rsid keeps one
    authored genotype while expanding to several loci, so exactly one locus can match and the others
    cannot; unioning is the only reading that does not manufacture a finding out of the expansion. (This
    is not hypothetical — `rs281864532`, `rs267607291` and `rs613985` in
    `reference_examples/pathogenic_clinvar/` are exactly that shape.)
    """
    if variant.ref and variant.alts:
        alleles = {variant.ref.upper()}
        alleles.update(a.strip().upper() for a in variant.alts.split(",") if a.strip())
        return alleles, "authored"
    resolved: set[str] = set()
    for row in resolution_table.get(variant.variant_key or "", []):
        if not row.ref or not row.alts:
            continue
        resolved.add(row.ref.upper())
        resolved.update(a.strip().upper() for a in row.alts.split(",") if a.strip())
    if resolved:
        return resolved, "resolved"
    return None, "unknown"


def _allele_verdict(
    call: str, variant: VariantRow, resolution_table: dict[str, list[ResolutionRow]]
) -> bool | None:
    """Can any locus this row is about host `call`? The shared tri-state predicate, Kleene-OR'd.

    **This must be the same question resolution asked, or the compiler contradicts itself.** The two
    checks are string comparisons of the same kind, and while membership did its own exact-set difference
    the halves disagreed the moment one indel was spelled two ways: `resolve_from_table` reconciled
    ClinVar's `C/CAG` with Ensembl's `AGAG>AG` and expanded onto the locus, and then membership refused
    the compile in `strict` because the literal strings `C` and `CAG` were not in the resolved set. Found
    by adding the case to `test_resolution_matrix.py`, which is what that file is for.

    Kleene semantics over the loci, matching `_allowed_alleles`' union reading: one locus that *can* host
    it settles the question (a one-to-many rsid carries one genotype onto N loci, and exactly one is
    expected to match), an undecidable spelling anywhere withholds, and only all-False is a finding.
    """
    if variant.ref and variant.alts:
        return hosting_verdict(call, variant.ref, variant.alts)
    verdicts = [
        hosting_verdict(call, row.ref, row.alts)
        for row in resolution_table.get(variant.variant_key or "", [])
        if row.ref and row.alts
    ]
    if not verdicts:
        return None
    if any(verdict is True for verdict in verdicts):
        return True
    return None if any(verdict is None for verdict in verdicts) else False


def _spelling_because(allowed: set[str]) -> str | None:
    """The explanation to use when the locus's own alleles are not nucleotides, else `None`.

    Takes the allele *set* rather than a `ref`/`alts` pair because `_allowed_alleles` has already
    unioned across every locus the key resolves to, and the finding is stated against that union — a
    caveat derived from anything narrower could name an allele the message does not.

    **`*` is excluded, and this caveat is the one place that is unconditional (RM59).** The sentence
    exists to say *the genotype is not the problem, the locus is spelled oddly* — and since
    `hosting_verdict` now strips `*` from both sides before comparing, a `*` can no longer contribute to
    the `False` this explains. Leaving it in produced the exact inversion the caveat exists to prevent:
    `genotype=C/G` at `ref=A alts="T,*"` is a real genotype error, and the module was told the genotype
    was not the problem and to "replace it with the alleles the locus actually has".
    """
    offenders = {a: non_nucleotide_reason(a) for a in sorted(allowed)}
    offenders = {
        a: reason
        for a, reason in offenders.items()
        if reason is not None and not is_unobservable_allele(a)
    }
    if not offenders:
        return None
    return (
        "the genotype is not the problem: "
        + _spelling_clauses(offenders)
        + " — replace it with the alleles the locus actually has"
    )


def _spelling_clauses(offenders: dict[str, str]) -> str:
    """One clause per reason present, and **only** per reason present.

    The consequence sentence belongs *inside* the branch it is true of. The first cut appended "an
    ambiguity code is an uncertainty and is never expanded…" to every finding, so a `<DEL>` locus was
    told about ambiguity codes — the identical conflation `cpic.unusable_allele_reason` was repaired to
    stop making, reintroduced in the message that repair paid for. Four reasons, four consequences: an
    uncertainty is permanent, a symbolic allele is held by the grammar and simply not comparable here,
    a `*` is a fact about the sample's *coverage* and not about the variant at all, and a grammar gap is
    what is left.

    The fourth arm arrived with RM59 for the same reason the third did: `*` used to answer `"notation"`,
    so a locus whose ALT list carries one — which is what a joint-called VCF writes, and `alts` has no
    grammar to stop it — was told it had hit a gap a future release may widen. Nothing can widen to hold
    `*`, because there is no sequence there to hold.

    The `"notation"` clause used to say a `<DEL>` is "a grammar gap (RM5) … a future release may widen
    to hold it". RM5 shipped in 0.6, so that reading became false for the five structural types, and
    `alleles.non_nucleotide_reason` now separates them — which is why this clause list grew a third arm
    rather than reworded the second.
    """
    ambiguity = [a for a, reason in offenders.items() if reason == "ambiguity"]
    symbolic = [a for a, reason in offenders.items() if reason == "symbolic"]
    unobservable = [a for a, reason in offenders.items() if reason == "unobservable"]
    notation = [a for a, reason in offenders.items() if reason == "notation"]
    missing = [a for a, reason in offenders.items() if reason == "missing"]
    parts: list[str] = []
    if ambiguity:
        parts.append(
            f"{', '.join(repr(a) for a in ambiguity)} is an IUPAC ambiguity code rather than a definite "
            f"nucleotide (`Y` is C-or-T) — an uncertainty, so it is never expanded into the alleles it "
            f"could stand for and can match no genotype"
        )
    if symbolic:
        parts.append(
            f"{', '.join(repr(a) for a in symbolic)} is a symbolic/structural allele, which the grammar "
            f"holds (RM5) — it names a variant whose sequence is deliberately unspelled, so comparing it "
            f"against a spelled allele is undecided rather than a mismatch"
        )
    if unobservable:
        parts.append(
            f"{', '.join(repr(a) for a in unobservable)} is VCF's allele-missing-due-to-overlapping-"
            f"deletion marker (RM59) — it records that a call could not observe this position, so it "
            f"names no allele for anything to match, and it is a fact about a sample rather than a "
            f"grammar gap a release could close"
        )
    if notation:
        parts.append(
            f"{', '.join(repr(a) for a in notation)} is neither a nucleotide string nor a symbolic "
            f"allele the format holds (a repeat notation like `AAAGGGGCG(2)`, a deletion spelling like "
            f"`DELTCT`, or a typo) — a grammar gap rather than a genotype error"
        )
    if missing:
        # Third reason, third consequence (RM58), and the one that must NOT borrow either sentence
        # above: `.` is VCF's MISSING marker, so the locus is asserting that it has no alternate
        # allele. That is not an uncertainty and not a grammar gap — there is nothing to widen.
        parts.append(
            f"{', '.join(repr(a) for a in missing)} is VCF's MISSING marker rather than an allele — the "
            f"locus states that it has no alternate allele, so no genotype can match it; leave the cell "
            f"empty instead"
        )
    return "; and ".join(parts)


def _check_allele_membership(
    variants: list[VariantRow],
    resolution_table: dict[str, list[ResolutionRow]],
    *,
    strict: bool,
) -> tuple[list[str], list[str]]:
    """Every `genotype` allele and every `effect_allele` must be an allele the locus actually has.

    Validate-by-redundancy, and the cheapest high-value pair in the tier: a genotype `A/G` at a `C>T`
    locus, and an `effect_allele` naming an allele that is not there, both compile clean without this.
    The second is the more dangerous of the two — `direction`, `weight` and `effect_size` are all
    *relative to* `effect_allele`, so naming the wrong one silently inverts the module's conclusion
    rather than corrupting it visibly.

    **Run this on the authored rows, before resolution expands them.** After `resolve_from_table` a
    one-to-many rsid has become N rows that share the authored genotype and carry N *different* allele
    sets, so at most one of them can match and the rest would be reported as findings. See
    `_allowed_alleles` for the union semantics this relies on.

    **Severity is the mode ladder in every case — warning in `best_effort`, error in `strict`** — the
    same one the VRS *unverifiable* outcome uses. Provenance shapes the *message*, because it changes
    what the author should go and look at, but it cannot decide severity, and the reason is worth
    recording so it is not "simplified" back:

    - a **resolved** mismatch may be an incomplete source rather than a bad row (ClinVar carries only
      its submitted alleles), so failing by default would let a source's gap sink a correct module;
    - an **authored** mismatch looks decidable, and is not, because `ref`/`alts` in `variants.csv` are
      not necessarily *human*-authored. `reverse_module` writes them, and a one-to-many rsid reverses
      into N rows that each carry their own locus's alleles beside the *one* genotype the author wrote.
      Exactly one of those rows can match. Making that an unconditional error would mean any module
      with a one-to-many rsid stops recompiling after a round-trip — Principle 7's fixed point, broken
      by a lint. (Verified against `rs999`'s two loci in `test_resolution_table.py`, and the same shape
      occurs eleven times in `reference_examples/pathogenic_clinvar/`.)

    A row with neither allele set known is skipped: nothing to compare is not the same as nothing wrong.
    """
    errors: list[str] = []
    warnings_out: list[str] = []
    for variant in variants:
        allowed, provenance = _allowed_alleles(variant, resolution_table)
        if allowed is None:
            continue
        shown = "/".join(sorted(allowed))
        # A locus spelled with a non-nucleotide replaces the explanation rather than decorating it: both
        # stories below are *false* for that row. "The row contradicts itself" and "the source's allele
        # list is incomplete" each send the author to re-examine a genotype that was correct, when the
        # defect is one cell of the allele column. Checked against `allowed` (the union the verdict was
        # taken over), so it describes the same alleles the finding names.
        spelling = _spelling_because(allowed)
        if spelling is not None:
            because = spelling
        elif provenance == "authored":
            because = (
                "the row carries both `ref` and `alts`, so it contradicts itself — either the genotype "
                "or the alleles is wrong, or this row is one locus of a one-to-many rsid whose genotype "
                "belongs to a sibling locus (reverse writes the alleles per locus but copies the single "
                "authored genotype to all of them)"
            )
        else:
            because = (
                "these alleles come from resolution.csv, so either the genotype is wrong or the "
                "resolving source's allele list is incomplete (ClinVar carries only its submitted "
                "alleles, while Ensembl carries every allele dbSNP knows) — check which before editing"
            )
        findings: list[str] = []
        # The message must name exactly what `_allele_verdict` judged, and that predicate abstains on
        # a `*` (RM59): it records what the call could not observe, so it is never one of the alleles
        # "missing" from a locus. Listing it anyway pointed the author at a correct transcription — a
        # false accusation in the one sentence that is supposed to say which cell is wrong.
        missing = sorted(
            {
                a.upper()
                for a in _split_genotype(variant.genotype)
                if not is_unobservable_allele(a)
            }
            - allowed
        )
        if _allele_verdict(variant.genotype, variant, resolution_table) is False:
            findings.append(
                f"{variant.variant_key} genotype {variant.genotype}: allele(s) "
                f"{', '.join(missing)} are not among the {provenance} alleles at this locus "
                f"({shown}) — {because}"
            )
        if (
            variant.effect_allele
            and _allele_verdict(variant.effect_allele, variant, resolution_table) is False
        ):
            findings.append(
                f"{variant.variant_key} genotype {variant.genotype}: effect_allele "
                f"{variant.effect_allele!r} is not among the {provenance} alleles at this locus "
                f"({shown}) — direction/weight/effect_size are all stated relative to it, so a wrong "
                f"effect allele inverts the conclusion rather than breaking it; {because}"
            )
        if not findings:
            continue
        (errors if strict else warnings_out).extend(findings)
    return errors, warnings_out


# ── Symbolic / structural alleles (RM5) ─────────────────────────────────────────────────────────
#
# Which authored tables the symbolic-allele check may **drop a row from**, and which it must refuse on
# instead. The line is whether a row stands alone as a rule.
#
# `variants.csv` and `pharm_variants.csv` are one self-contained rule per row: dropping one removes a
# claim and removes nothing else, which is exactly the decided `best_effort` behaviour — a module is a
# declarative rulebook, and an unusable rule is worse than an absent one.
#
# `haplotypes.csv` and `heteroplasmy.csv` rows are *parts of a composite*. Dropping a haplotype's
# defining variant silently redefines the haplotype — the module would go on naming `*5` while
# describing something else — and dropping a bin punches a hole in a tiling `_validate_table_kind`
# just checked. Neither is a smaller module; both are a **different** one, asserted quietly. So the
# finding is fatal in both modes there, and the message says why the `best_effort` escape is not on
# offer. It is clearable by an authored edit (state the length), which is what separates it from the
# findings P5 keeps out of `strict`.
_SYMBOLIC_DROPPABLE_TABLES: frozenset[str] = frozenset({"variants.csv", "pharm_variants.csv"})

#: Splits a cell into the alleles it names: `/` and `|` for a genotype, `,` for a multi-allelic `alts`.
#: One splitter for every allele column — no allele column uses these characters within a token.
_ALLELE_CELL_SEP: re.Pattern[str] = re.compile(r"[,/|]")


@dataclass(frozen=True)
class _SymbolicFinding:
    """One unusable symbolic allele, located well enough for an author to go and fix it.

    **Located by the row's own identity, not by its position in the file.** A row index looks more
    precise and is not: `load_csv_rows` prints a *header-inclusive line number*, so a bare "row 2"
    would be a third coordinate convention beside that and `hints.Finding.row` (0-based); and it is
    computed over the rows that survived model validation, so any earlier load error silently shifts
    it. Every other row-level finding in this module names `variant_key`, and so does this one.
    """

    table: str
    index: int  # position among the loaded rows — for stable ordering only, never printed
    label: str  # the row's identity: variant_key, else haplotype_name
    column: str
    allele: str
    reason: str  # "no_length" | "unknown_type" | "reference_allele"


#: Reason → (what is wrong, what to do). Written out rather than composed, because the three are
#: different findings with different fixes and running them together is the conflation this codebase
#: has unwound twice (`cpic.unusable_allele_reason`, `_spelling_clauses`).
#:
#: **The prose names no allele type, and the reason is the aggregation** (D3-1). This dict is keyed by
#: reason because the messages are grouped by reason — one line per (table, reason), never one per row
#: — so a sentence that opened "A <DEL> that does not say how long it is" was a claim about *the*
#: offending allele made where several are being reported at once, and it read as a false one the
#: moment the author had written `<DUP:TANDEM>`. Interpolating the authored type would make each
#: sentence exactly right and turn one constant into N messages, which is the per-row prose that
#: printed forty lines each naming a different indel in the VRS pass. The example clause that
#: `_symbolic_allele_messages` appends already names the real cells, so the specific case is not lost.
#: `<DEL:1500>` survives below as the *spelling to use*, which is what an author actually needs.
_SYMBOLIC_REASONS: dict[str, str] = {
    "no_length": (
        "a symbolic allele with no usable length. An allele that names an event without saying how "
        "long it is cannot be sized, matched against a call, or told apart from any other event of "
        "the same type at that position, so the rule states nothing a consumer can apply. Spell the "
        "length into the allele — <DEL:1500>, <CNV:TR:30> — or, when the sequence is actually known, "
        "spell the bases out instead (VCF 4.4 says to: symbolic notation is for imprecision)"
    ),
    "unknown_type": (
        "an allele that is angle-bracketed but not one this format holds. The first level is the closed "
        f"five {'/'.join(sorted(SYMBOLIC_ALLELE_TYPES))} and subtypes are free-form — VCF recommends "
        f"{', '.join(f'<{s}>' for s in RECOMMENDED_SYMBOLIC_SUBTYPES)} — but there is no declaration "
        "mechanism for arbitrary names, deliberately. VCF's <*> is not one of them either: it makes a "
        "claim about what could be *observed*, which is a different axis from what the variant *is*"
    ),
    "reference_allele": (
        "a symbolic allele in a reference-allele column. REF is always a sequence — the padding base "
        "and whatever follows it — and a structural allele names an ALT; a locus whose own reference "
        "is unspelled anchors nothing"
    ),
}


def _symbolic_findings(rows_by_table: dict[str, list[Any]]) -> list[_SymbolicFinding]:
    """Every unusable symbolic allele in the authored rows, in a deterministic order.

    Which columns hold an allele comes from the **model** (`AuthoredModel.ALLELE_COLUMNS`), never from
    a list kept here: a compiler-side copy of a model's column names is the drift `SOURCES_FIELDNAMES`
    already demonstrated, and this check would go quietly blind the day a model gained a column.

    Sorted by `(table, reason, index, column)` so the messages built from it are byte-stable — findings
    reach `manifest.compilation.warnings`, so their order is artifact-visible.
    """
    found: list[_SymbolicFinding] = []
    for table, rows in rows_by_table.items():
        for index, row in enumerate(rows):
            label = getattr(row, "variant_key", None) or getattr(row, "haplotype_name", None)
            for column in getattr(type(row), "ALLELE_COLUMNS", ()):
                cell = getattr(row, column, None)
                if not isinstance(cell, str):
                    continue
                for token in _ALLELE_CELL_SEP.split(cell):
                    allele = token.strip()
                    if not is_symbolic_allele(allele):
                        continue
                    reason = (
                        "reference_allele" if column == "ref"
                        else symbolic_allele_defect(allele)
                    )
                    if reason is not None:
                        found.append(
                            _SymbolicFinding(
                                table, index, str(label or f"the {_ordinal(index)} row"),
                                column, allele, reason,
                            )
                        )
    return sorted(found, key=lambda f: (f.table, f.reason, f.index, f.column))


def _ordinal(index: int) -> str:
    """`0` → `1st`. The last-resort label for a row carrying no identity of its own — no model in
    `ALLELE_COLUMNS` is in that state today, and a bare integer would read as a file line number."""
    n = index + 1
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _symbolic_allele_messages(findings: list[_SymbolicFinding]) -> list[str]:
    """One aggregated line per (table, reason) — never one per row.

    A structural panel drafted from a caller's VCF hits this per locus, and a line each buries every
    other finding in the run. The grouping is by **reason** rather than by row for the other half of
    the same rule: two reasons under one message is the mistake that took four rounds to stop making
    in the CPIC provider.

    The wording is identical in `validate_spec` and `compile_module` on purpose. `compile_module` runs
    `validate_spec` first, in `best_effort` whatever its own mode, so a check living in both places
    emits its sentence twice and the compile side de-duplicates **on the message**.
    """
    messages: list[str] = []
    grouped: dict[tuple[str, str], list[_SymbolicFinding]] = {}
    for finding in findings:  # already sorted, so insertion order is deterministic
        grouped.setdefault((finding.table, finding.reason), []).append(finding)
    for (table, reason), entries in grouped.items():
        # Rows, not findings. One row routinely carries the same unusable allele in three columns
        # (`alts`, `genotype`, `effect_allele`), and the sentence says "row(s)" — counting findings
        # there would report three rows dropped where one is.
        affected = len({e.index for e in entries})
        shown = ", ".join(f"{e.label} {e.column}={e.allele!r}" for e in entries[:3])
        rest = f" (+{len(entries) - 3} more)" if len(entries) > 3 else ""
        fate = (
            "Those row(s) are DROPPED from the compiled artifact — reverse will not re-emit them — "
            "and --strict refuses instead."
            if table in _SYMBOLIC_DROPPABLE_TABLES
            else (
                f"This is fatal in both modes: a {table} row is part of a composite (a haplotype's "
                f"definition, a bin tiling), so dropping it would not make a smaller module but a "
                f"quietly different one."
            )
        )
        messages.append(
            f"{table}: {affected} row(s) carry {_SYMBOLIC_REASONS[reason]}. {fate} "
            f"e.g. {shown}{rest}."
        )
    return messages


def _check_symbolic_alleles(
    rows_by_table: dict[str, list[Any]], *, strict: bool
) -> tuple[list[str], list[str], dict[str, set[int]]]:
    """`(errors, warnings, rows to drop per table)` for unusable symbolic alleles (RM5).

    **The schema accepts what this refuses, and that split is forced rather than chosen.** A model-level
    rejection surfaces through `load_csv_rows` as a load error, which is fatal in *both* modes; the
    decided behaviour is warn-and-drop under `best_effort`. So the grammar says what the DSL can spell
    (`vocab.validate_allele`, `AuthoredModel._validate_genotype`) and this says what makes a usable
    rulebook. Do not "tighten" it back into the models.

    One asymmetry worth expecting: `<FOO>` fails at *load* in `genotype`/`effect_allele`/
    `HaplotypeRow.allele`, because those columns have a grammar, and reaches this check only through
    `ref`/`alts`, which deliberately have none (adding one would reject `N` and break P3). Same
    diagnosis either way; different point of arrival.

    Pure computation over authored bytes with no `output_dir`, so by the standing rule it runs in
    `validate_spec` too — where nothing is dropped and the message is a prediction of what a compile
    will do.
    """
    findings = _symbolic_findings(rows_by_table)
    if not findings:
        return [], [], {}
    fatal = [f for f in findings if f.table not in _SYMBOLIC_DROPPABLE_TABLES]
    droppable = [f for f in findings if f.table in _SYMBOLIC_DROPPABLE_TABLES]
    errors = _symbolic_allele_messages(fatal)
    if strict:
        errors.extend(_symbolic_allele_messages(droppable))
        return errors, [], {}
    drops: dict[str, set[int]] = {}
    for finding in droppable:
        drops.setdefault(finding.table, set()).add(finding.index)
    errors.extend(_emptied_table_errors(rows_by_table, drops))
    return errors, _symbolic_allele_messages(droppable), drops


def _emptied_table_errors(
    rows_by_table: dict[str, list[Any]], drops: dict[str, set[int]]
) -> list[str]:
    """A table the drop would empty outright is an error in **both** modes.

    The drop exists so a module can lose one unusable rule and still say the rest; a table that loses
    *every* row says nothing at all, and says it silently — the surviving artifact is a module that
    annotates nothing, which is precisely the shape the DROPPED warning exists to keep an author from
    believing they still have.

    **Computed here rather than at the point of application, and that placement is the point.**
    `_check_symbolic_alleles` runs in `validate_spec` as well as `compile_module`, so the refusal is
    predicted by the pre-flight; the first cut refused inside the drop, which only `compile_module`
    performs, and produced exactly the green-`validate`-then-failing-`compile` sequence the standing
    parity rule exists to prevent. (An earlier version of this docstring justified the refusal as
    "`validate_spec` already refuses a present-but-empty table". That is true of the `_TABLE_KINDS`
    loop and **false of `variants.csv`**, which validates and compiles header-only — measured. The
    refusal stands on its own reason, above.)
    """
    return [
        f"{table}: every row would be dropped for carrying an unusable symbolic allele, leaving a "
        f"table that states nothing — so the compile would quietly produce a module that annotates "
        f"nothing at all. Refused in both modes. Give the alleles their lengths, or remove the table."
        for table, rows in sorted(rows_by_table.items())
        if rows and len(drops.get(table, ())) == len(rows)
    ]


def _apply_symbolic_drops(rows: list[Any], drop_rows: set[int]) -> list[Any]:
    """The surviving rows. Refusal is `_emptied_table_errors`' job — see there for why it is not here."""
    return [row for index, row in enumerate(rows) if index not in drop_rows]


def _check_p_value_num(
    studies: list[StudyRow], *, strict: bool
) -> tuple[list[str], list[str]]:
    """Does the typed `p_value_num` agree with the free-form `p_value` string beside it?

    Validate-by-redundancy on two encodings of one number, so it is exactly the tier's own kind of
    check: pure computation over injected data, no reference required. A transcription slip between
    the verbatim cell and the queryable one is otherwise invisible — the module compiles, and a
    consumer thresholding on the number silently reads a different p-value than the row displays.

    **A string that does not denote one definite value is skipped in silence.** `"<0.001"`, `"NS"` and
    `"5e-8 (adjusted)"` are all legitimate things to have written in a free-form column, and none of
    them disagrees with anything — see `normalize.parse_p_value`, which is anchored on the whole cell
    rather than reading a leading number out of commentary.

    The comparison is relative, at 1%: the string is the record and the number is a transcription of
    it, so `p_value="5.23e-8"` beside `5.2e-8` is a rounding rather than a contradiction, while a
    wrong digit or a wrong power of ten is neither. Severity is the mode ladder — warning in
    `best_effort`, error in `strict`."""
    errors: list[str] = []
    warnings_out: list[str] = []
    for row in studies:
        if row.p_value_num is None:
            continue
        parsed = parse_p_value(row.p_value)
        if parsed is None or math.isclose(parsed, row.p_value_num, rel_tol=0.01):
            continue
        (errors if strict else warnings_out).append(
            f"{row.variant_key} pmid {row.pmid}: p_value {row.p_value!r} reads as {parsed:g}, but "
            f"p_value_num says {row.p_value_num:g} — two encodings of one number disagree, so one of "
            f"them is a transcription slip (the string is the record; the number is what a consumer "
            f"filters on)."
        )
    return errors, warnings_out


def _verify_vrs_ids(resolution_rows: list[ResolutionRow]) -> tuple[list[str], list[str]]:
    """Recompute every stored `vrs_id` and report disagreements. Returns (errors, warnings).

    Takes no `mode`: every outcome below is the same in `best_effort` and `strict`, which is the point
    of the split. It was a mode ladder until the severity was rethought — see the *unverifiable* bullet.

    The integrity check the whole minting story earns: a `ga4gh:VA.…` is *content-addressed*, so it is
    the one column in the whole artifact that can be checked against itself with no reference, no
    network, and no dependency — `derive_vrs_allele_id` is stdlib, so the compiler tier gains nothing
    to run this (Goal 2). A mismatch means the row was tampered with, or the producer and this
    implementation disagree — either way the id is not usable as an identity.

    Every row lands in exactly one of **three** outcomes, and the distinction between the last two is
    the one that matters:

    - **verified** — recomputed and equal. Silent.
    - **mismatch** — recomputed and *different*. Always an **error**, in both modes: this computation
      is fully deterministic here, so a disagreement can only mean the stored id is corrupt.
    - **unverifiable** — could not be recomputed at all (see `_recompute_vrs_id` for the five reasons).
      Severity follows **whose limit it is**, not the mode alone: `_BLAME_ROW` is an **error** in both
      modes, `_BLAME_TIER` is a **warning** in both.

    The third case is emphatically *not* "an indel mismatch". This tier cannot recompute an indel's id,
    so it can never detect that one disagrees — it can only report that it did not check. Calling that
    a mismatch would claim a verdict that was never reached.

    **Why the tier's own limits do not escalate under `strict`, though they used to.** `strict` means
    *reproducible artifact*, and an enricher-minted indel VA is perfectly reproducible: the bytes are
    injected, the compile is deterministic, and recompiling yields the same digest. What is impossible
    here is the *verification*, not the reproduction — and escalating on that conflates "I could not
    check this" with "this cannot be rebuilt". The cost was not hypothetical: minting indel ids online
    is exactly what `just-dna-enricher` is for, so every ClinVar-derived module acquired ids that
    `compile --strict` then refused, and the two remedies the message offered were *lower your
    guarantee* or *delete a correct identity* — the second being the same abstention the per-ALT fix had
    just finished removing one file away. Two reference examples (`pathogenic_clinvar`, `shox_par1`)
    stopped compiling in the mode their own README documents. The rule this now follows is the one
    `_vrs_coverage_warnings` and `frequencies`' `not_covered` already followed: **a finding no authored
    edit could clear is not a `strict` matter.**

    `_BLAME_ROW` keeps the error, in *both* modes rather than only `strict`. A row asserting a `vrs_id`
    while carrying no coordinate or no ALT is not a limit of this tier — it is a table contradicting
    itself, catchable offline, and it is the same class as the "inconsistent reference allele" error.

    A row with no `vrs_id` is skipped entirely — there is nothing to check, which is not the same as
    something that could not be checked. The same goes for a **hole** in a multi-allelic cell: `vrs_id`
    is positionally aligned with `alts`, so each allele is verified on its own and an empty member is
    the same non-event as an empty cell. That alignment is the second thing this pass now guards —
    `ResolutionRow` refuses a pair of the wrong *length*, and recomputing member by member catches a
    pair of the right length in the wrong *order*, which is the failure mode a parallel array has and a
    scalar column does not.
    """
    errors: list[str] = []
    warnings_out: list[str] = []
    for row in resolution_rows:
        if row.vrs_id is None:
            continue
        stored = split_vrs_ids(row.vrs_id)
        alts = [alt.strip() for alt in row.alts.split(",")] if row.alts else []
        for index, vrs_id in enumerate(stored):
            if vrs_id is None:
                # A hole: this allele has no id to check. Same non-event as a row with no `vrs_id`.
                continue
            alt = alts[index] if index < len(alts) else None
            where = f"{row.variant_key} allele {alt}" if len(stored) > 1 else str(row.variant_key)
            recomputed, reason, blame = _recompute_vrs_id(row, alt)
            if recomputed is None:
                message = f"{where}: vrs_id {vrs_id} could not be verified — {reason}"
                if blame == _BLAME_ROW:
                    errors.append(
                        f"{message}. An id recorded against nothing to check it with is a "
                        f"contradiction in the table, not a limit of this tier: resolve the row, or "
                        f"drop the vrs_id."
                    )
                else:
                    warnings_out.append(f"{message}; carried unverified.")
                continue
            if recomputed != vrs_id:
                errors.append(
                    f"{where}: stored vrs_id {vrs_id} does not match the id recomputed "
                    f"from {row.chrom}:{row.start} {row.ref}>{alt} ({recomputed}) — a substitution's "
                    f"id is deterministic here, so this is corruption, not a difference of opinion."
                )
    return errors, warnings_out


def _vrs_coverage(resolution_rows: list[ResolutionRow]) -> tuple[int, int, dict[str, int]]:
    """`(alleles, identified, gaps_by_reason)` — how much of the table a VA actually names.

    The counterpart to `_verify_vrs_ids`, and the thing that pass structurally cannot see: it verifies
    ids that are *there*, and an absent id is "nothing to check". That was the right severity while a
    VA was a decorative cross-reference. It is the wrong one now that `variant_key` derives from a VA
    for a resolved substitution and the id is headed for primary-key status — an identity scheme
    covering an unstated fraction of the table is not one anything can key on, and *unstated* is the
    defect. So absence is counted and reported; a consumer can then decide.

    The denominator is **alleles, not rows** — one multi-allelic site is several identities — and a row
    with no ALT at all counts as one unnamed slot rather than vanishing from the ratio.

    Gaps are grouped by *why*, because the reasons have completely different remedies and a bare
    "N missing" hides which one you have. The sharpest is the first: an allele this tier could mint
    **right now, offline**, which means nothing minted it, not that anything is hard.
    """
    alleles = identified = 0
    gaps: dict[str, int] = {}
    for row in resolution_rows:
        stored = split_vrs_ids(row.vrs_id)
        alts = [alt.strip() for alt in row.alts.split(",")] if row.alts else [None]
        for index, alt in enumerate(alts):
            alleles += 1
            if index < len(stored) and stored[index] is not None:
                identified += 1
                continue
            reason = _vrs_gap_reason(row, alt)
            gaps[reason] = gaps.get(reason, 0) + 1
    return alleles, identified, gaps


#: The symbolic-allele gap class (RM5, 0.6), as ONE constant string — `_vrs_coverage` groups on it, so
#: interpolating the token would rebuild the per-row wall this bucketing exists to prevent, and a
#: structural module carries several spellings at once (`<DEL:4977>`, `<DUP:16000>`, `<CNV:TR:30>`).
#: It names no remedy, because there is none: this is not the indel class one enricher run away from an
#: id, it is an allele nothing anywhere can mint one for.
_SYMBOLIC_GAP_REASON: str = (
    "a symbolic allele (<DEL:…>, <CNV:TR:…>): it names a structural event rather than a sequence, so "
    "there is nothing for a content-addressed id to be a digest of — no tier can mint one, offline or "
    "online, and no authored edit clears it"
)

#: The unobservable-allele gap class (RM59, 0.6) — a *third* bucket, not a spelling of the one above
#: and emphatically not the indel one (R2-6).
#:
#: 0.6 gave the symbolic class its own permanent reason here and guarded `*` and `.` on the *enricher*
#: side, and these two compiler functions were never told: neither tested `is_unobservable_allele`, so
#: a `*` in `resolution.csv`'s `alts` would have been reported as *"an indel or MNV … re-run it
#: online"* — the same false class D1-2 had just fixed for symbolic alleles, one axis over, with a
#: remedy that could never work.
#:
#: **Filed as having no instantiation, and upgraded when it turned out to have one.** The reasoning
#: was that nothing writes a `*` into that column today; the unit fixing D1-1 then probed
#: `LiteralSequenceExpression`'s pattern — `^[A-Z*\\-]*$` — and found `*` **passes** it, so before the
#: enricher guard an unobservable allele reaching the minter would have been normalized and handed a
#: content-addressed id for a state that is not a sequence. *"Nothing produces it today"* is a fact
#: about the current wiring, never about the function: the same lesson RM38 and
#: `VALID_RSID_STATUS.withdrawn` already carry.
#:
#: Separate from the symbolic bucket because the two answer different questions and P5 keeps them
#: apart everywhere else: `parse_symbolic_allele` asks *which variant is this, unspelled*, while
#: `is_unobservable_allele` asks *whether this sample's call could see the allele at all* — the
#: callability axis. One is a variant with no sequence written down; the other is not a variant.
_UNOBSERVABLE_GAP_REASON: str = (
    "the unobservable-allele marker '*': it records that an overlapping deletion left this position "
    "uncallable in the sample, so it names no allele and there is nothing to digest — no tier mints "
    "one, and this is the callability axis rather than a gap in the identity scheme"
)


def _vrs_gap_reason(row: ResolutionRow, alt: str | None) -> str:
    """Which *class* of gap this is — a bucket, deliberately not `_recompute_vrs_id`'s prose.

    That function names the alleles (`AG>A is not a single-base substitution…`) because it is
    diagnosing one row, and it is right to. Grouping on it produced 40-odd lines that all said the same
    thing about a different indel — a per-row wall wearing an aggregate's clothes. There are six
    reasons an allele has no id here, and a reader needs the six.
    """
    if row.chrom is None or row.start is None:
        return "no coordinate to mint from (an unresolved row)"
    if not alt:
        return "no ALT recorded, and a VRS allele id names exactly one allele"
    # Ahead of both the mint attempt and the `is_substitution` fall-through, in this function and in
    # `_recompute_vrs_id` — the two order their other branches differently, and this one branch must be
    # in the same place in both. A symbolic allele is *also* not a substitution and *also* has no
    # accession on a non-GRCh38 build, and both of those reasons are answerable by someone: the indel
    # class by an online enricher run, the build class by RM15. This one never is, so it is the reason
    # to print. Lenient predicate on purpose (`is_symbolic_allele`, not `parse_symbolic_allele`): a
    # malformed `<FOO>` or an unterminated `<DEL` names no sequence either, so filing it under "indel"
    # would be the same false claim about a different mistake.
    if is_symbolic_allele(alt):
        return _SYMBOLIC_GAP_REASON
    # Beside it, and above the substitution fall-through for the identical reason (R2-6): `*` is also
    # not a substitution, and filing it under the indel class would print a remedy — re-run online —
    # that can never work. The two are disjoint predicates (`*` is one character, a symbolic token is
    # bracketed), so their order relative to each other decides nothing.
    if is_unobservable_allele(alt):
        return _UNOBSERVABLE_GAP_REASON
    try:
        recomputed = derive_vrs_allele_id(row.chrom, row.start, row.ref, alt, build=row.genome_build)
    except UnsupportedBuildError as exc:
        return str(exc)
    if recomputed is not None:
        # The sharp one: nothing was blocking this. Either the mint pass never ran, or it ran before
        # multi-allelic cells were minted per ALT.
        return "no id recorded, though one is computable offline — run `just-dna-enricher vrs mint`"
    if not is_substitution(row.ref, alt):
        return (
            "an indel or MNV: justification needs the reference sequence, so only the enricher can "
            "mint it (re-run it online)"
        )
    return "outside the primary assembly, or past the end of the contig — no refget accession"


def _vrs_coverage_warnings(resolution_rows: list[ResolutionRow]) -> list[str]:
    """One line for the shortfall, one per reason — never one per row.

    A **warning in both modes**, deliberately, and for the same reason `not_covered` sits outside the
    strict gate: the commonest gaps (an indel with no sequence proxy, a build with no refget table)
    are fixable by no authored edit, so refusing would make such a module uncompilable rather than
    telling its author anything. `strict` means "reproducible artifact", which an incomplete identity
    scheme still is. What strict *does* refuse is a stored id it cannot confirm — a claim, not an
    absence.
    """
    if not resolution_rows:
        return []
    alleles, identified, gaps = _vrs_coverage(resolution_rows)
    if not alleles or identified == alleles:
        return []
    findings = [
        f"VRS allele identity covers {identified}/{alleles} allele(s) in resolution.csv "
        f"({identified / alleles:.0%}) — {alleles - identified} carry no ga4gh:VA. id. Anything "
        f"keying on the VA sees only the covered fraction."
    ]
    findings.extend(
        f"  {count} allele(s): {reason}"
        for reason, count in sorted(gaps.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    return findings


#: Whose limit made an allele unverifiable — the classification `_verify_vrs_ids` takes its severity
#: from. `TIER` is *this compiler cannot do it, and no edit to the module would change that*; `ROW` is
#: *the row does not carry what a check needs*, which a producer can fix. See `_recompute_vrs_id`.
#: Two values, not three: a symbolic allele is beyond *every* tier rather than this one, and that is a
#: sharper statement than `TIER` makes — but blame decides severity and nothing else, and a third
#: member mapping to the same severity would be a fourth outcome in all but name. It is said in the
#: reason instead, which is what a reader actually sees.
_BLAME_TIER = "tier"
_BLAME_ROW = "row"


def _recompute_vrs_id(
    row: ResolutionRow, alt: str | None
) -> tuple[str | None, str | None, str | None]:
    """`(recomputed_id, reason, blame)` for ONE allele — either the id is set, or the other two are.

    The five reasons an allele is unverifiable here, split by **whose limit each one is**, because that
    is what decides severity upstream (`_BLAME_TIER` / `_BLAME_ROW`):

    1. **no coordinate** — nothing to recompute from (an unresolved rsid row carrying an external id).
       `_BLAME_ROW`: the row asserts an identity while withholding the coordinate that identity is a
       digest of, so nothing can ever check it — an internal contradiction, catchable offline;
    2. **no ALT** — a position-only row, so there is no allele to name. `_BLAME_ROW`, same shape: a VA
       names exactly one allele and the row names none. This used to also cover *multi-allelic*, on the
       reasoning that "picking one from a comma-joined cell would be inventing data". Nothing is picked
       now: `vrs_id` is positionally aligned with `alts`, so the caller walks the pair and asks about
       allele *i* — and a multi-allelic site of substitutions verifies as completely as a bi-allelic one;
    3. **a symbolic allele** (`<DEL:4977>`, `<CNV:TR:30>` — RM5, 0.6) — it names a structural *event*
       and no sequence, so nothing is being digested and no id exists to recompute. `_BLAME_TIER` by
       severity and by the only thing blame decides, though it understates the case: this is not a
       limit of *this* tier but of every tier, since the enricher cannot mint one either. Checked
       **before** reason 4, which it would otherwise fall into: both statements are true of the row,
       and the one to print is the one no release can answer. **Whether a *stored* id on such a row
       should instead be `_BLAME_ROW` is a real open question, deliberately not answered here.** The
       case for it: nothing mints a VA for a symbolic allele, so a present one names some other,
       sequence-spelled allele, and unlike an indel — which the enricher legitimately mints online —
       deleting the cell clears the finding, which is exactly what takes it out of the P5 class where
       no authored edit helps. The case against acting on that in this pass: it would refuse, in both
       modes, a module that compiles today, and the same judgement has to be made on the minting side
       first (whether the enricher may ever write a non-VA identity into that column). Surfaced, not
       half-mended;
    4. **not a single-base substitution** — an indel or MNV must be justified against the reference
       sequence, which this tier has no access to and will never fetch (Principle 2). `_BLAME_TIER`;
    5. **outside the primary assembly, or a build with no refget table** — no accession to address the
       sequence by. `_BLAME_TIER` for both. The build case is *raised* by `refget_accession` rather than
       returned, deliberately (a caller asking for GRCh37 should hear "not built" rather than get a
       GRCh38-flavoured answer), so it is caught here and turned into a reason. Letting it propagate
       would abort the whole compile over one unverifiable row, which is the wrong severity for
       `best_effort`.
    """
    if row.chrom is None or row.start is None:
        return None, "the row carries no coordinate to recompute from", _BLAME_ROW
    if not alt:
        return (
            None,
            "the row records an id against no ALT (a position-only row), and a VRS allele id "
            "names exactly one allele",
            _BLAME_ROW,
        )
    if is_symbolic_allele(alt):
        # Named per row here (unlike `_vrs_gap_reason`'s constant) for the same reason the indel branch
        # below names its alleles: this diagnoses one row, and the caller has already located it.
        #
        # **`_BLAME_ROW`, and it was `_BLAME_TIER` until R2-5 was settled.** Tier-blame is for a
        # finding **no authored edit could clear** (P5 — the rule that also keeps `not_covered` and the
        # coverage warnings out of the `strict` gate), and this one is cleared by deleting the cell. It
        # belongs with *inconsistent reference allele* and *an id recorded against no ALT*: the row
        # asserts a content-addressed identity for an allele that has no content to address, so the id
        # necessarily names some **other** allele. That is a false claim, catchable offline, and an
        # error in both modes.
        #
        # It was left at tier-blame when first found because escalating needed the minting side
        # answered first — *may a non-VA identity ever be written here?* — and that is now settled in
        # the grammar: `validate_vrs_allele_id` refuses anything but `ga4gh:VA.`, on a probe of 844 ids
        # across the corpus that found no other type. With the column VA-only, a present id on a
        # symbolic row can only be a VA minted for a different allele, and there is nothing left to be
        # unsure about. Note the asymmetry that stays: the *coverage* side (`_vrs_gap_reason`) still
        # reports the same allele as a permanent gap and warns, because an **absent** id there is
        # honest and no edit improves it. Absence is a limit; a claim is a claim.
        return (
            None,
            f"{alt} is a symbolic allele: it names a structural event rather than a sequence, so there "
            f"is nothing for a content-addressed id to be a digest of and no tier mints one — a "
            f"recorded id here names some other allele. Delete the vrs_id cell; the allele keeps its "
            f"identity through variant_key",
            _BLAME_ROW,
        )
    if is_unobservable_allele(alt):
        # The same branch `_vrs_gap_reason` gained in R2-6, in the same place: above the substitution
        # fall-through, because `*` is not one either and the indel message's remedy — re-run the
        # enricher online — is unreachable for a marker that names no allele. `_BLAME_TIER` matches
        # the symbolic branch above, and a *stored* id here raises the identical open question that
        # branch records: nothing mints one, so a present id names something else.
        return (
            None,
            f"{alt} is the unobservable-allele marker, not an allele: it records that an overlapping "
            f"deletion left this position uncallable in the sample, so there is no sequence for a "
            f"content-addressed id to name",
            _BLAME_TIER,
        )
    if not is_substitution(row.ref, alt):
        return (
            None,
            f"{row.ref}>{alt} is not a single-base substitution, so justifying it needs the reference "
            f"sequence — minted upstream by the enricher, not recomputable here",
            _BLAME_TIER,
        )
    try:
        recomputed = derive_vrs_allele_id(
            row.chrom, row.start, row.ref, alt, build=row.genome_build
        )
    except UnsupportedBuildError as exc:
        return None, str(exc), _BLAME_TIER
    if recomputed is None:
        return (
            None,
            f"{row.chrom}:{row.start} is outside the primary assembly (no refget accession for the "
            f"contig, or the position is past its end)",
            _BLAME_TIER,
        )
    return recomputed, None, None


#: The reference star allele. Defined by carrying **none** of a gene's variants, so it can never
#: appear in `haplotypes.csv` and must never be reported as undefined.
_REFERENCE_HAPLOTYPE = "*1"


def _cross_validate_haplotype_definitions(
    haplotypes: list[Any], allele_functions: list[Any], diplotypes: list[Any]
) -> list[str]:
    """Warn when a star allele is *used* but never *defined*. Returns warnings.

    Validate-by-redundancy across the PGx tables: `allele_function.csv` says what an allele does and
    `diplotypes.csv` pairs it, while `haplotypes.csv` says which variants make it. An allele named by
    the first two and absent from the third cannot be called from a VCF at all, so every row about it
    is dead weight — a consumer's star-allele caller will never emit it.

    Only checked when `haplotypes.csv` is **present**: a module may legitimately carry a diplotype
    table alone and lean on the caller's own definitions, and punishing that would be the
    orphan-sidecar mistake (don't fault an author for a file they deliberately did not write).

    Found by drafting CYP2C19 from CPIC: `*36`, `*37` and `*42` were used across 666 diplotype rows,
    two of them declared `no_function`, and nothing defined any of them.
    """
    if not haplotypes:
        return []
    defined = {row.haplotype_name for row in haplotypes}
    used: dict[str, set[str]] = {}
    for row in allele_functions:
        used.setdefault(row.allele, set()).add("allele_function.csv")
    for row in diplotypes:
        for allele in (row.haplotype_a, row.haplotype_b):
            used.setdefault(allele, set()).add("diplotypes.csv")
    undefined = sorted(
        allele
        for allele in used
        if allele not in defined and allele != _REFERENCE_HAPLOTYPE
    )
    if not undefined:
        return []
    return [
        f"Star allele(s) used but not defined in haplotypes.csv: {undefined}. A consumer's caller "
        f"cannot emit an allele nothing defines, so rows about it can never match."
    ]


#: An allele a haplotype does not mention — or mentions as its own reference base. The letter never
#: has to be known: "unmentioned" means the same thing for every haplotype at a given variant, so two
#: haplotype sets can be compared without a reference sequence anywhere in the compiler (P2).
_IMPLIED_REFERENCE = "\0ref"


def _unphased_signature(
    pair: tuple[str, str], definitions: dict[str, dict[tuple, str]], variants: list[tuple]
) -> tuple:
    """The genotype a consumer *observes* for a diplotype, with phase discarded.

    Per variant, the **sorted pair** of alleles the two haplotypes contribute — sorted because that
    is precisely what losing phase does: it tells you which two alleles are present and not which
    chromosome each sits on.
    """
    return tuple(
        tuple(sorted((
            definitions.get(pair[0], {}).get(variant, _IMPLIED_REFERENCE),
            definitions.get(pair[1], {}).get(variant, _IMPLIED_REFERENCE),
        )))
        for variant in variants
    )


def _cross_validate_phase_ambiguity(haplotypes: list[Any], diplotypes: list[Any]) -> list[str]:
    """Warn when two diplotype rows are indistinguishable without phase and disagree. Warnings only.

    **The narrow, real residue of RM28's cis/trans motivation.** Compound heterozygosity is the case
    that most justified a predicate language, and it turns out to need none: `haplotypes.csv` is a
    junction table so a haplotype is same-strand conjunction, and a *diplotype* is a statement about
    two homologs — so cis and trans are already two rows. `reference_examples/hfe_compound_het/`
    writes exactly that, with the bricks that shipped in 0.4.

    What no table can say is that the two rows **cannot be told apart from unphased data**. HFE
    `C282Y/H63D` (in trans, no wild-type protein on either chromosome, an at-risk genotype) and
    `C282Y-H63D` + `wt` (both variants on one chromosome, one intact copy, a carrier) present the
    identical unphased genotype — rs1800562 G/A and rs1799945 C/G — and carry opposite conclusions.
    A consumer with unphased calls that silently picks the first would manufacture a finding; picking
    the second would suppress one.

    It is a **check** rather than a column because it is derivable: the compiler already holds both
    tables and the computation is pure and offline, which is the validate-by-redundancy class this
    tier exists for. Adding a `requires_phase` column instead would make an author restate something
    the data already determines, and it would go stale the moment a haplotype is edited.

    **Closed-world, and deliberately so.** It compares the rows a module states, never the rows it
    omits. APOE is the standing illustration: ε2/ε4 and ε1/ε3 are the textbook unphased collision, and
    `reference_examples/apoe_epsilon/` carries no ε1, so nothing here fires. That is correct — the
    module makes no claim about ε1 — and the neighbouring "used but not defined" check is what covers
    an allele a caller might emit that the module never describes.

    A haplotype that does not mention a variant is treated as carrying the reference there, and an
    allele explicitly equal to the row's own `ref` normalizes to the same sentinel. Neither needs the
    reference *sequence*: only that "unmentioned" means one thing. That is what lets this run on a
    CPIC-drafted table, where haplotypes are sparse and `ref` is absent entirely — and on such a table
    it correctly finds nothing, because sparse definitions genuinely do not collide.
    """
    if not haplotypes or not diplotypes:
        return []

    definitions: dict[str, dict[tuple, str]] = {}
    variants: list[tuple] = []
    for row in haplotypes:
        # Position-level, and *without* `alts`: a haplotype names one allele at a locus, so the key
        # must be the place. Passing `alts` would mint a per-allele VRS id and put each haplotype's
        # own allele in a different bucket, which is the mixing-up `derive_variant_key` warns about.
        variant = derive_variant_key(row.rsid, row.chrom, row.start, row.ref)
        if variant is None:
            continue
        if variant not in definitions.get(row.haplotype_name, {}) and variant not in variants:
            variants.append(variant)
        allele = _IMPLIED_REFERENCE if row.ref is not None and row.allele == row.ref else row.allele
        definitions.setdefault(row.haplotype_name, {})[variant] = allele

    # A diplotype naming a haplotype `haplotypes.csv` never defines has no signature to compute —
    # every one of its variants would read as reference, which is a claim rather than a computation.
    # That case already has its own warning; here it is simply skipped.
    by_signature: dict[tuple, list[Any]] = {}
    for row in diplotypes:
        pair = (row.haplotype_a, row.haplotype_b)
        if not all(name in definitions for name in pair):
            continue
        by_signature.setdefault(
            (row.gene, _unphased_signature(pair, definitions, variants)), []
        ).append(row)

    warnings: list[str] = []
    undistinguished: dict[str, list[str]] = {}
    unphased: dict[str, list[str]] = {}
    for (gene, _signature), rows in by_signature.items():
        # **Distinct haplotype PAIRS, not distinct rows** — the bug the first draft shipped, caught by
        # compiling the real CYP2C19 example. One pair legitimately carries many rows: the dedup key
        # is (gene, a, b, trait_efo_id, drug, clinical_context), so `*10/*10` has a row per drug and
        # per clinical context, all with the same signature by construction and different conclusions
        # by design. Flagging those reported 595 phase ambiguities in a module that has none, and the
        # message named the same pair twice, which is what gave it away.
        pairs = sorted({(row.haplotype_a, row.haplotype_b) for row in rows})
        if len(pairs) < 2:
            continue
        # Two *different* pairs that state the same thing are harmless — a consumer reporting either
        # is right. Only a disagreement is a finding.
        if len({(row.conclusion, row.phenotype, row.direction, row.clin_sig) for row in rows}) < 2:
            continue

        # **Phase does not always resolve it, and saying so was overclaiming.** Caught by compiling a
        # real 16,290-row CYP2D6 draft: `*10/*8`, `*100/*8`, `*101/*8` and `*147/*8` collide because
        # `*10`, `*100`, `*101` and `*147` carry *identical defining-variant sets* (rs1058164 G,
        # rs1065852 A, rs1135840 G — CPIC's core definitions do not separate these suballeles). Those
        # pairs are indistinguishable **at all**, phased or not, so telling an author "a phased
        # consumer resolves it" would send them to buy phasing that cannot help. Grouping the pairs by
        # their *phase-preserving* signature separates the two cases exactly: same multiset of
        # haplotype definitions → nothing distinguishes them; different → phase does.
        by_definition: dict[tuple, list[tuple[str, str]]] = {}
        for pair in pairs:
            key = tuple(sorted(
                tuple(sorted(definitions[name].items())) for name in pair
            ))
            by_definition.setdefault(key, []).append(pair)

        for identical in by_definition.values():
            if len(identical) > 1:
                undistinguished.setdefault(gene, []).append(
                    ", ".join(f"{a}/{b}" for a, b in identical)
                )
        distinct = [same[0] for same in by_definition.values()]
        if len(distinct) > 1:
            unphased.setdefault(gene, []).append(
                ", ".join(f"{a}/{b}" for a, b in sorted(distinct))
            )

    # One warning per gene per class, with examples and a count — the aggregation rule CPIC taught and
    # this check had to relearn: the real CYP2D6 draft produces 378 identically-defined groups and 20
    # phase-ambiguous ones, and 398 lines bury every other finding a compile emits. Deterministic
    # order (first-occurrence per gene, P7), and the count is always stated so nothing is silently
    # capped.
    for gene, groups in undistinguished.items():
        warnings.append(
            f"{gene}: {len(groups)} group(s) of diplotype rows name haplotypes this module defines "
            f"identically, so nothing in it can tell them apart — phase does not help. A consumer's "
            f"caller may still emit each name and the rows disagree, so at most one can be right: "
            f"either the defining variants are incomplete or the rows describe one allele under "
            f"several names. {_examples(groups)}"
        )
    for gene, groups in unphased.items():
        warnings.append(
            f"{gene}: {len(groups)} group(s) of diplotype rows are indistinguishable without phase — "
            f"same unphased genotype, different conclusions. A consumer with unphased calls must "
            f"withhold rather than pick one; a phased consumer resolves it. {_examples(groups)}"
        )
    return warnings


def _examples(groups: list[str], limit: int = 3) -> str:
    """`e.g. A, B, C (+N more)` — the shape `pgx_draft` already uses for a repeated finding."""
    shown = "; ".join(groups[:limit])
    extra = len(groups) - limit
    return f"e.g. {shown}" + (f" (+{extra} more)" if extra > 0 else "")


def _cross_validate_studies(
    studies: list[StudyRow], variants: list[VariantRow]
) -> tuple[list[str], list[str]]:
    """Validate study rows against the variants. Returns (errors, warnings).

    A study matches a variant on **any shared identifier** — same rsid or same `chrom:start:ref` —
    not on frozen-key equality. Keying strictly on `variant_key` would false-orphan a study that
    references a variant by a different (but co-identifying) handle than the one the variant froze its
    key to (e.g. a coord-keyed variant referenced by rsid).

    **A row that names no variant is not an orphan** (RM47): since 0.6 a citation row may ground the
    module or a binning bound rather than a locus, and a row referencing nothing cannot reference
    something missing. Its dedup key is `(None, pmid)`, so two subject-less rows citing one paper are
    still a duplicate — deliberately: they are the same claim written twice, and the whole point of
    the relaxation is that one such row is enough."""
    warnings: list[str] = []
    variant_rsids = {v.rsid for v in variants if v.rsid is not None}
    variant_coords = {
        derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None
    }
    orphans: list[str] = []
    for row in studies:
        if row.variant_key is None:
            continue
        by_rsid = row.rsid is not None and row.rsid in variant_rsids
        by_coord = (
            row.chrom is not None
            and derive_variant_key(None, row.chrom, row.start, row.ref) in variant_coords
        )
        if not by_rsid and not by_coord:
            orphans.append(row.variant_key)
    if orphans:
        warnings.append(
            f"Studies reference variants not in variants.csv: {sorted(set(orphans))}"
        )
    seen: set[tuple[str | None, str]] = set()
    for row in studies:
        key = (row.variant_key, row.pmid)
        if key in seen:
            warnings.append(f"Duplicate (variant, pmid): ({row.variant_key}, {row.pmid})")
        seen.add(key)
    return [], warnings


def _validate_table_kind(
    csv_name: str, model: type[BaseModel], rows: list[Any]
) -> tuple[list[str], list[str]]:
    """Table-level coherence for one 0.4 table kind, after per-row validation has passed.

    Returns (errors, warnings). Two families of check:

    - **Binning tables** (`MeasureBinRow` subclasses) run `validate_bins` — overlapping resolved bins
      are an **error** (a measurement would select two phenotypes), interior coverage gaps a
      **warning**. Plus: at most one `unresolved` sentinel per key group (a consumer selects one when
      the measurement is absent, so two is ambiguous) — an error.
    - **All keyed kinds** get duplicate-row detection via `_TABLE_DUPE_KEYS` — an error, mirroring the
      SNP core's duplicate-(variant, genotype) rule.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if issubclass(model, MeasureBinRow):
        try:
            for w in validate_bins(rows):
                warnings.append(f"{csv_name}: {w}")
        except ValueError as exc:
            errors.append(f"{csv_name}: {exc}")
        sentinels: dict[tuple, int] = defaultdict(int)
        for r in rows:
            if r.unresolved:
                group = tuple(getattr(r, f, None) for f in r._KEY_FIELDS) + (r.trait_efo_id,)
                sentinels[group] += 1
        for group, count in sentinels.items():
            if count > 1:
                errors.append(
                    f"{csv_name}: {count} unresolved sentinel rows for key {group} — a consumer "
                    f"selects one when a measurement is absent, so at most one is allowed"
                )

    keyfn = _TABLE_DUPE_KEYS.get(model)
    if keyfn is not None:
        seen: set[tuple] = set()
        for r in rows:
            key = keyfn(r)
            if key in seen:
                errors.append(f"{csv_name}: duplicate row for key {key}")
            seen.add(key)

    return errors, warnings


# ── Public API ─────────────────────────────────────────────────────────────────


# Every filename the spec directory has a meaning for. Derived from the table registries rather than
# listed, so a new table kind cannot be missed here. Used only to recognise a *near miss* — a spec
# directory may carry anything else it likes (see `_check_misspelled_tables`).
_KNOWN_SPEC_FILES: frozenset[str] = frozenset(
    {"module_spec.yaml", "variants.csv", "studies.csv", _PROVENANCE_FILE, VERIFICATION_JSON}
    | set(_TABLE_KIND_CSVS)
    # Every accepted spelling, not just the one the registries name — a sidecar the compiler happily
    # reads under an alias must not also be reported as a near-miss stray file in the same run (RM51).
    | {name for csv, _, _ in _FACT_TABLES for name in sidecar_spellings(csv)}
    | set(sidecar_spellings("resolution.csv"))
)


#: Extensions the near-miss guard inspects **at the spec root**. `.json` joined `.csv` when
#: `verification.json` landed (RM45); `derived/` deliberately stays `.csv`-only, and the reason the two
#: differ is argued at the loop in `_check_misspelled_tables`. The guard's precision comes from the
#: near-miss cutoff rather than from the extension, which is what lets it warn about a typo without
#: warning about the curation notes beside it.
_ROOT_NEAR_MISS_SUFFIXES: frozenset[str] = frozenset({".csv", ".json"})


def _check_misspelled_tables(spec_dir: Path) -> list[str]:
    """Warn when an unknown `.csv` is one small edit from a table name the compiler knows.

    **Unknown files are ignored on purpose and that is a contract** (S16): a module may carry curation
    notes or a publisher's receipt, neither of which is in `artifact.files` and so neither of which
    moves the digest. The hazard is the narrow case where "ignored" is the wrong answer — a *mistyped
    table name*. `varaints.csv` is silently not a table, so the author's rows are dropped and the
    compile is green, which is the silent-success shape this codebase treats as the worst kind of
    mistake. Probed on a real spec: three extra files, including that typo, produced no message and an
    unchanged digest.

    A `README.md` was the headline example of a tolerated file until S25 gave it a manifest field, and
    it is now *collected* — copied into the module dir and hashed into `manifest.readme`. That changes
    nothing here (the check reads only `.csv` names) but the two claims are no longer the same claim:
    a readme is read and hashed, and still moves no digest, because `manifest.readme` sits outside
    `artifact.files` exactly as `logo` does.

    Deliberately keyed on **near miss** rather than on "unknown csv": warning about every unrecognised
    file would fire on the legitimate sidecars the contract exists to permit, so the check has to be
    high-precision or it undoes the tolerance. `difflib` at a 0.8 cutoff catches a transposition, a
    doubled or dropped letter, and a singular/plural slip, and stays quiet on an unrelated name.

    **`derived/` is scanned too, and it takes TWO tests rather than one (RM49).** Tolerating a second
    input location without teaching this check about it would put a typo'd `derived/varaints.csv`
    exactly where the guard cannot see it — re-opening the hole S16 closed, as the price of a
    convenience. That is also the argument against "search any subdirectory": one fixed name is the
    only version where the guard can follow.

    What is *legal* there is the derived files alone, but that smaller set is the wrong thing to
    fuzzy-match against, and matching against it was measured to catch neither case: at a 0.8 cutoff
    `variants.csv`, `studies.csv` and `repeat_alleles.csv` are **no** near miss of any sidecar name,
    and neither is `varaints.csv` — the very file this check exists for. So the two mistakes are
    separated. An **authored table name under `derived/` is an exact match against the wrong name
    set**, which is a sharper test than any fuzzy one and is reported as a misplaced table: those rows
    are read from nowhere, and a module that keeps another table at the root compiles green without
    them. Anything else there is fuzzy-matched against the **full** known set, so a typo'd authored
    name lands too. The mirror case stays silent by construction — a derived sidecar at the spec root
    is a legal place for it, so the root's own legal set already accepts it."""
    if not spec_dir.is_dir():
        return []
    derived_names = frozenset(
        name for csv in _DERIVED_FILES for name in sidecar_spellings(csv)
    )
    # The authored DSL: one legal name in one legal place, so any of these under `derived/` is
    # misplaced. Derived by subtraction rather than listed — a new table kind joins it for free.
    authored_names = _KNOWN_SPEC_FILES - derived_names
    warnings: list[str] = []
    # The suffix set is **per directory**, and the asymmetry is the point rather than an oversight.
    #
    # Under `derived/`, both branches below are about a **table** whose rows are being dropped, so both
    # stay behind the `.csv` filter. `derived/provenance.json` and `derived/module_spec.yaml` are
    # therefore ordinary tolerated strays: neither has rows to lose, a misplaced `module_spec.yaml`
    # cannot hide (the root one is required and its absence is an error), and `provenance.json` is
    # exactly the machine-written document a registry splitting a tree might reasonably put there.
    # Widening *that* branch would actively misreport it — `provenance.json` is in the authored set by
    # subtraction, so it would be named as an authored table in the wrong place, which it is not.
    #
    # At the **root** the near-miss branch reads `.json` too (RM45). What is lost there is not rows but
    # a whole document: a typo'd `verifcation.json` silently is not an attestation, so the module reads
    # as *nothing verified* while its author believes the checks are recorded — the same silent-success
    # shape, one file kind over. It retroactively covers `provenance.json`, which had been in the
    # known-name set since 0.4 with no suffix that could reach it. Neither `published.json` nor any
    # other registry receipt is within one edit of a known name, which is the property that keeps the
    # tolerance beside it intact (measured, not assumed).
    scans = (
        (spec_dir, _KNOWN_SPEC_FILES, _ROOT_NEAR_MISS_SUFFIXES),
        (spec_dir / DERIVED_SUBDIR, derived_names, frozenset({".csv"})),
    )
    for directory, legal, suffixes in scans:
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.name in legal or path.suffix not in suffixes:
                continue
            shown = path.relative_to(spec_dir)
            if path.name in authored_names:
                warnings.append(
                    f"{shown} is an authored table sitting in {DERIVED_SUBDIR}/, which holds only the "
                    f"machine-written sidecars — every row in it is being silently ignored. Move it to "
                    f"the spec root. Only resolution.csv and the fact tables have a second legal home."
                )
                continue
            close = difflib.get_close_matches(
                path.name, sorted(_KNOWN_SPEC_FILES), n=1, cutoff=0.8
            )
            if close:
                warnings.append(
                    f"{shown} is not a table this compiler reads, and it is one small edit from "
                    f"{close[0]!r} — if that is a typo, every row in it is being silently ignored. "
                    f"Unknown files are otherwise tolerated (curation notes or a publisher's receipt "
                    f"are fine): nothing outside the known table set reaches artifact.digest."
                )
    return warnings


def validate_spec(
    spec_dir: Path,
    authority_keys: Iterable[str] | None = None,
    *,
    strict: bool = False,
    resolve_with_ensembl: bool = True,
) -> ValidationResult:
    """Validate a module spec directory without producing output.

    `authority_keys` (inject-only) is the set of consumer/registry-owned identity keys to strip from
    the authored `module:` block before validation — pass `just_dna_format.normalize.
    IDENTITY_AUTHORITY_KEYS` (or your own set) so a legacy spec carrying `namespace:`/`owner:`/
    `canonical_id:` validates; the format applies none by default. Stripped keys are surfaced on
    `.info`. Everything else still trips `extra="forbid"`.

    `strict` mirrors `compile_module`'s flag and exists for one reason: several checks are a **mode
    ladder** (warning in `best_effort`, error in `strict`), so without a mode here the pre-flight
    could not answer the question the author actually asked — the documented order is `validate` then
    `compile --strict`, and a modeless `validate` is a pre-flight for the *other* compile. It changes
    severity only; it never adds or removes a finding, which is what keeps the two commands one
    contract rather than two.

    `resolve_with_ensembl` mirrors it for the same reason and is passed through by `compile_module`.
    The pre-flight applies the injected table to the positional 0.4 tables (RM43), and that decides
    whether their rows are reported as unjoinable — so a `validate` that ignored the master resolution
    switch would be *more optimistic* than the compile it precedes, which is the disagreement
    direction the parity rule exists to prevent.

    Stats include `genes`/`categories` as lists (filtering None) plus `variant_count`,
    `gene_count`, `study_count`, and the ClinVar quality counts
    (`clinvar_count`/`pathogenic_count`/`benign_count`) — the fields the manifest needs. See
    `ValidationResult.stats` for the full key contract.
    """
    spec_dir = Path(spec_dir)
    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_info: list[str] = []

    if not spec_dir.is_dir():
        return ValidationResult(valid=False, errors=[f"Spec directory does not exist: {spec_dir}"])

    all_warnings.extend(_check_misspelled_tables(spec_dir))

    config, yaml_errors, dropped_authority = _load_yaml(
        spec_dir / "module_spec.yaml", authority_keys
    )
    all_errors.extend(yaml_errors)
    if dropped_authority:
        all_info.append(
            f"dropped injected authority keys from module: block (registry-stamped, not authored): "
            f"{dropped_authority}"
        )
    # The `panel:` block lost its last reader in 0.6 (RM4) and is removed at 1.0. Warn-only, and the
    # block still compiles and still reaches `manifest.panel` exactly as before — the charter's
    # cadence is deprecate in a minor, remove at the next major, and the deprecation is *actionable*
    # here because the thing that replaced it needs nothing from the author: the enricher records the
    # drafted-from release into the licence row's `dataset` column itself.
    if config is not None and config.panel is not None:
        all_warnings.append(
            "module_spec.yaml declares a `panel:` block. It is deprecated in 0.6 and removed at 1.0: "
            "the compiler never materialized rows from it, and the one thing that did read it — the "
            "enricher's ClinVar clin_sig cross-check, deciding whether a drafted module is being "
            "compared against its own source — now reads the `dataset` column of the module's "
            "licence row, which `just-dna-enricher draft-panel` writes itself. Delete the block; the "
            "rows it describes are the authored variants.csv rows, and nothing else is lost."
        )

    # `module.version` is advisory (the registry stamps the canonical Identity.version) and is COERCED
    # to SemVer by `ModuleInfo` since 0.5 (RM17). Report the rewrite rather than performing it here:
    # the model already did it, and `version_coerced_from` is how it says so. A clean
    # MAJOR.MINOR.PATCH coerces to itself and stays silent.
    if config is not None and config.module.version_coerced_from:
        all_warnings.append(
            f"module.version {config.module.version_coerced_from!r} was read as SemVer "
            f"{config.module.version!r}. It is advisory either way — the registry stamps the "
            f"canonical version on publish — but the module now compiles under the coerced value."
        )

    # The build every authored row below is loaded as being on. `config` is None when the yaml itself
    # failed to load, and the format's own default is the honest answer there — `validate` reports every
    # problem it can rather than stopping at the first, so the rows still have to be loaded somehow.
    declared_build = config.genome_build if config else DEFAULT_GENOME_BUILD

    # A module composes from optional table kinds (RM2): variants.csv is no longer mandatory — a PGx /
    # PharmGKB / PRS module carries only its own table(s). Load whatever is present.
    variants_path = spec_dir / "variants.csv"
    has_variants = variants_path.exists()
    variants: list[VariantRow] = []
    if has_variants:
        variants, var_errors, var_warnings = _load_csv_rows(
            variants_path, VariantRow, "variants.csv", genome_build=declared_build
        )
        all_errors.extend(var_errors)
        all_warnings.extend(var_warnings)
        # Before anything reads `variant_key`: a row is stamped at construction, where the module's
        # declared build is not knowable, so a non-GRCh38 module arrives carrying GRCh38-flavoured
        # ids. Fix the identity here, where both the row and the spec are in hand.
        all_warnings.extend(
            _restamp_for_build(variants, config.genome_build if config else "GRCh38")
        )

    # Validate each present 0.4 table kind against its model.
    kind_row_counts: dict[str, int] = {}
    loaded_kinds: dict[str, list[Any]] = {}
    for csv_name, _parquet, model in _TABLE_KINDS:
        kind_path = spec_dir / csv_name
        if not kind_path.exists():
            continue
        rows, kind_errors, kind_warnings = _load_csv_rows(
            kind_path, model, csv_name, genome_build=declared_build
        )
        all_errors.extend(kind_errors)
        all_warnings.extend(kind_warnings)
        kind_row_counts[csv_name] = len(rows)
        loaded_kinds[csv_name] = rows
        if not rows:
            if not kind_errors:
                all_errors.append(f"{csv_name} is present but has no rows.")
        elif not kind_errors:
            # Table-level coherence (bin overlap/gap, single sentinel, duplicate keys) — only when
            # every row validated, so the checks run on a complete, trustworthy set.
            tbl_errors, tbl_warnings = _validate_table_kind(csv_name, model, rows)
            all_errors.extend(tbl_errors)
            all_warnings.extend(tbl_warnings)

    # Cross-table PGx coherence: an allele used by the function/diplotype tables that the definition
    # table never defines can never be called. Runs after the loop so every kind is in hand.
    all_warnings.extend(
        _cross_validate_haplotype_definitions(
            loaded_kinds.get("haplotypes.csv", []),
            loaded_kinds.get("allele_function.csv", []),
            loaded_kinds.get("diplotypes.csv", []),
        )
    )
    all_warnings.extend(
        _cross_validate_phase_ambiguity(
            loaded_kinds.get("haplotypes.csv", []),
            loaded_kinds.get("diplotypes.csv", []),
        )
    )

    # Filled from `resolution.csv` below when it is present, and deliberately usable empty: allele
    # membership needs it only for a row that did not author its own `ref`/`alts`.
    membership_table: dict[str, list[ResolutionRow]] = {}
    # Injected resolution rows, grouped by the build each one records rather than by the module's:
    # `ResolutionRow.genome_build` is a column, so a row states which frame its numbers are in and
    # that is the frame its coordinate has to be possible in (RM48).
    resolution_by_build: dict[str, list[ResolutionRow]] = {}
    # Filled from `literature.csv` below; cross-checked once `studies.csv` is loaded further down.
    literature_rows: list[LiteratureRow] = []

    # The injected tables: `resolution.csv` and the four 0.5 fact sidecars. They are not
    # `_TABLE_KINDS` — they are machine-produced and fact-hashed rather than authored DSL — but they
    # live in the spec directory and `compile_module` **refuses** on a bad row in any of them, so
    # leaving them out here made `validate` report `valid` for a directory `compile` then rejected.
    # That is the one thing this command must never do: the documented authoring order puts `validate`
    # immediately before `compile`, so it is the author's pre-flight, and a green pre-flight followed by
    # a refusal sends them looking for a change they did not make. Row-level validation, plus the
    # *self*-checks below — what stays compile-only is a check that needs **resolved** rows, which is a
    # narrower exemption than "a cross-check": `_verify_vrs_ids` compares a `resolution.csv` row against
    # its own content-addressed id and consults nothing else, so being a sidecar check never made it a
    # cross-check. Lumping the two together is how it stayed compile-only.
    for csv_name, model in (
        ("resolution.csv", ResolutionRow),
        *((name, model) for name, _parquet, model in _FACT_TABLES),
    ):
        injected_path, spelling_warnings, spelling_errors = _locate_sidecar(spec_dir, csv_name)
        all_warnings.extend(spelling_warnings)
        all_errors.extend(spelling_errors)
        if injected_path is None:
            continue
        injected_rows, injected_errors, injected_warnings = _load_csv_rows(
            injected_path, model, injected_path.name
        )
        all_errors.extend(injected_errors)
        all_warnings.extend(injected_warnings)
        if model is ResolutionRow and not injected_errors:
            for injected_row in injected_rows:
                membership_table.setdefault(injected_row.variant_key, []).append(injected_row)
                resolution_by_build.setdefault(
                    injected_row.genome_build, []
                ).append(injected_row)
            # A `ga4gh:VA.…` is the one column checkable with no reference, no network and no
            # dependency, so there is nothing about it that needs an `output_dir`. A **mismatch** is an
            # error in *both* modes, which is why this gap was reachable without `--strict` at all:
            # `validate` reported `valid` for a module a plain `compile` then refused as corrupt.
            # Gated on `not injected_errors` for the same reason `compile_module` is — a row that
            # failed to load cannot be re-derived from.
            vrs_errors, vrs_warnings = _verify_vrs_ids(injected_rows)
            all_errors.extend(vrs_errors)
            all_warnings.extend(vrs_warnings)
            # Coverage rides along for the same reason: counting absent ids reads injected bytes and
            # nothing else. It reports here too so an author sees the shortfall at pre-flight, where
            # the remedy (re-run the mint pass) is still cheap.
            all_warnings.extend(_vrs_coverage_warnings(injected_rows))
        if model is LiteratureRow and not injected_errors:
            # Stashed rather than checked here: the citation sites (`studies.csv`, and since 0.6 the
            # binning tables' `pmid`) are loaded further down, so the cross-check runs once both are
            # in hand. Parity by CHECK, not by table — this is pure computation over injected and
            # authored bytes with no `output_dir`, so it belongs to the pre-flight, and it was
            # compile-only for the same reason `_check_allele_membership` was: nobody asked.
            literature_rows = injected_rows
        if model is SourceRow and not injected_errors:
            # The licence gate, run here for the same reason. It refuses in **both** modes and is pure
            # computation over injected bytes (the compiler holds no source→licence map, P2), so there
            # is nothing about it that needs an output directory — it was simply only wired into
            # `compile_module`. It is also the refusal most expensive to discover late: a module drafted
            # entirely from a no-sale source compiles right up to the gate.
            all_errors.extend(_check_license_gate(injected_rows))

    # The verification attestation (RM45). Read here as well as in `compile_module` under the standing
    # rule — pure computation over injected bytes with no `output_dir` belongs in the pre-flight too —
    # and the two runs are safe to double precisely because this check is **not** a mode ladder and
    # its input does not differ between them: the binding is over the authored files, which no compile
    # step touches, so both passes reach the identical sentence and the dedup on the message below
    # collapses them. The block itself is discarded here; only the staleness warning is wanted, at the
    # point where an author can still re-run the checks before publishing.
    _, verification_warnings = _verification_block(spec_dir)
    all_warnings.extend(w for w in verification_warnings if w not in all_warnings)

    # The positional fill (RM43), and then the report of what it could not place. Both run here for
    # the same reason: pure computation over authored + injected bytes with no `output_dir`. The order
    # matters — filling first is what makes the joinability line describe the residue rather than the
    # whole table, and running the fill on one side only would have the pre-flight name a gap the
    # compile has already closed.
    #
    # **Over the rows a compile would keep, not every row loaded.** `compile_module` drops a row
    # carrying an unusable symbolic allele (RM5) *before* it resolves anything, so a pre-flight
    # filling and then counting the full set would report a coordinate gap over rows the artifact will
    # not contain. `_check_symbolic_alleles` is pure, so asking it for the drop set here costs a second
    # pass and nothing else; its **messages** are deliberately not taken — they belong to the block
    # further down that owns this check, and emitting them twice is the duplication the standing rule
    # about running a check in both commands exists to avoid. Under `strict` it reports rather than
    # drops, so the set is empty and nothing is filtered — which is also what the compile does there.
    _, _, would_drop = _check_symbolic_alleles({"variants.csv": variants, **loaded_kinds}, strict=strict)
    survivors = {
        csv_name: _apply_symbolic_drops(rows, would_drop.get(csv_name, set()))
        for csv_name, rows in loaded_kinds.items()
    }
    fill_warnings, fill_applied = _apply_positional_resolution(
        survivors, membership_table, declared_build, resolve=resolve_with_ensembl
    )
    all_warnings.extend(fill_warnings)
    all_warnings.extend(
        _check_positional_joinability(
            survivors, membership_table, declared_build, fill_applied=fill_applied
        )
    )

    # Composition: a module must carry at least one recognized table kind.
    if not has_variants and not kind_row_counts:
        all_errors.append(
            "module has no recognized table: add variants.csv or a 0.4 table "
            "(e.g. pharm_variants.csv, diplotypes.csv, pgs.csv)."
        )

    # Grounding (studies) is mandatory for *variant* annotations, so it is required iff variants.csv
    # is present. The 0.4 tables are exempt — but not, as this comment used to claim, because "they
    # carry their own evidence (e.g. evidence_level)". Two of the nine do: `DiplotypeRow` and
    # `PharmVariantRow`. `PgsRow` carries a catalog accession, which is a provenance and not a
    # citation, and the four binning kinds plus `HaplotypeRow`/`AlleleFunctionRow` carry nothing of the
    # sort. The real reason is that `StudyRow` can only name a variant, so for a gene-keyed table the
    # requirement would be unsatisfiable rather than merely unmet — which is S19/RM47, and is why
    # `_check_binning_grounding` below reports the absence instead of demanding the table.
    studies_path = spec_dir / "studies.csv"
    studies: list[StudyRow] = []
    if studies_path.exists():
        studies, study_errors, study_warnings = _load_csv_rows(
            studies_path, StudyRow, "studies.csv", genome_build=declared_build
        )
        all_errors.extend(study_errors)
        all_warnings.extend(study_warnings)
        if not studies and not study_errors:
            all_errors.append(
                "studies.csv is present but has no study rows. Grounding evidence is mandatory."
            )
        # Two encodings of one p-value, compared against each other — authored bytes only, no
        # resolution and no reference, so this belongs to the pre-flight as much as to the compile.
        # It is a pure mode ladder, which is what `strict` above is for.
        p_value_errors, p_value_warnings = _check_p_value_num(studies, strict=strict)
        all_errors.extend(p_value_errors)
        all_warnings.extend(p_value_warnings)
    elif has_variants:
        all_errors.append(
            "studies.csv is missing. Grounding evidence is mandatory; add study rows with PMIDs."
        )

    # The other half of the same rule: a binning table states clinical thresholds and is exempt from
    # the requirement above, so nothing used to report a module that grounds none of them. Pure
    # computation over authored bytes with no `output_dir`, so it belongs to the pre-flight.
    all_warnings.extend(_check_binning_grounding(loaded_kinds, studies))
    # And the other defect those same tables carry: an integer tiling for a measurement VCF 4.4 makes
    # fractional and interval-valued (RM55/RM56). Same rule for why it is here — pure computation over
    # authored bytes, no `output_dir`.
    all_warnings.extend(_check_measure_shape(loaded_kinds))
    # `.` in an alts cell, on every table that has one (RM58). Also pure, also authored-only, and it
    # reads `loaded_kinds` plus `variants` rather than a table name, so a future kind with an `alts`
    # column joins the check by declaring the column.
    all_warnings.extend(_check_missing_allele_marker(variants, loaded_kinds, declared_build))

    # Symbolic/structural alleles the module cannot actually apply (RM5). Pure computation over
    # authored bytes and a **mode ladder** on the droppable tables, so it belongs here by the standing
    # rule — the same one `_check_allele_membership` was moved here under. Nothing is dropped in this
    # command; the message states what a compile will do, which is what a pre-flight is for.
    symbolic_errors, symbolic_warnings, _ = _check_symbolic_alleles(
        {"variants.csv": variants, **loaded_kinds}, strict=strict
    )
    all_errors.extend(symbolic_errors)
    all_warnings.extend(symbolic_warnings)

    # Coordinates that cannot exist in the build they are recorded under (RM48) — pure arithmetic over
    # authored and injected bytes with no `output_dir`, so it belongs to the pre-flight by the standing
    # rule, and it is the finding an author most wants *before* a compile: a wrong-build coordinate is
    # cheap to fix and impossible to notice once it is a published digest.
    #
    # `resolution.csv` is in scope on purpose. Leaving it out would recreate the parity defect this
    # check exists beside: an rsid-only authored row carries no coordinate here, so `validate` would
    # see nothing while `compile` fills the position from the injected table and refuses — a green
    # pre-flight followed by a refusal for a change the author did not make. Each resolution row is
    # judged against **its own** `genome_build`, which is what that column is for.
    all_errors.extend(
        _check_build_coordinates(
            [
                _CoordinateTable("variants.csv", declared_build, True, variants),
                _CoordinateTable("studies.csv", declared_build, True, studies),
                *(
                    _CoordinateTable(
                        csv_name, declared_build, True, loaded_kinds.get(csv_name) or []
                    )
                    for csv_name, _model in _POSITIONAL_TABLE_KINDS
                ),
                *(
                    _CoordinateTable("resolution.csv", build, False, rows)
                    for build, rows in sorted(resolution_by_build.items())
                ),
            ]
        )
    )

    # Same rule about where a check belongs: the VCF pointer columns are authored cells read against
    # two spec-derived constants, with no resolution step and no `output_dir` in sight, so the
    # pre-flight is exactly where an author should hear about them.
    all_warnings.extend(_check_vcf_pointers(variants, loaded_kinds))

    # The injected citation sidecar against BOTH citation sites, now that studies are loaded.
    all_warnings.extend(_cross_check_literature(literature_rows, studies, loaded_kinds))

    if variants:
        cross_errors, cross_warnings = _cross_validate_variants(variants)
        all_errors.extend(cross_errors)
        all_warnings.extend(cross_warnings)
        # The quality floor that inverts on the record it is read from (RM57). Authored cells only —
        # resolution fills neither `requires_callable` nor `quality_from` — so the pre-flight sees
        # exactly what the compile will.
        all_warnings.extend(_check_quality_inversion(variants))
        # Allele membership, which was compile-only and should never have been. It is pure computation
        # over authored rows plus the injected table, needs no `output_dir` — the standing rule for what
        # belongs here — and it is a **mode ladder**, so `validate --strict` reported `valid` for a
        # module `compile --strict` then refused. The same defect the 2026-08-07 audit fixed for
        # `_verify_vrs_ids` and `_check_p_value_num`; this one sat beside them and was missed because
        # that pass went table by table rather than check by check. Its docstring already says it runs
        # on the AUTHORED rows *before* resolution expands them, which is exactly what makes it
        # computable here, where there is no resolution step at all. `membership_table` is empty when
        # the module carries no `resolution.csv`, and that is a working input: a row authoring its own
        # `ref`/`alts` is judged against those, and a row with neither is skipped either way.
        membership_errors, membership_warnings = _check_allele_membership(
            variants, membership_table, strict=strict
        )
        all_errors.extend(membership_errors)
        all_warnings.extend(membership_warnings)
        # Ploidy runs here *and* post-resolution in `compile_module`, because the two passes see
        # different rows. Here it catches a hand-written `MT,3243,A/G` on the standalone `validate`
        # command, where there is no resolution step at all; there it catches the rsID-authored form,
        # whose `chrom` does not exist until the table has been consulted. A row that both passes can
        # see produces the same string twice, which compile de-duplicates.
        # `config` is None when the spec itself failed to load; default rather than crash, since
        # the point of `validate` is to report every problem it can, not to stop at the first.
        all_warnings.extend(
            _check_contig_ploidy(variants, config.genome_build if config else "GRCh38")
        )
        if studies:
            _, study_warnings = _cross_validate_studies(studies, variants)
            all_warnings.extend(study_warnings)
        # `flags` is an open vocabulary — surface non-reserved tags as INFO (not a warning; nothing
        # is wrong). ROADMAP 0.3 item 4.
        unknown_flags = sorted(
            {tag for v in variants if v.flags for tag in v.flags if tag not in RESERVED_FLAGS}
        )
        if unknown_flags:
            all_info.append(
                f"Non-reserved flags in use (allowed; reserved tags are "
                f"{sorted(RESERVED_FLAGS)}): {unknown_flags}"
            )

    stats: dict[str, Any] = {"study_count": len(studies)}
    if config:
        stats["module_name"] = config.module.name
    if kind_row_counts:
        stats["table_rows"] = kind_row_counts
    if variants:
        stats.update(variant_stats(variants))

    return ValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings,
        info=all_info,
        stats=stats,
    )


def variant_stats(variants: list[VariantRow]) -> dict[str, Any]:
    """The `variants.csv`-derived facets of `ValidationResult.stats` / `manifest.stats`.

    Its own function because it now has **two** callers, and the second is why: `compile_module` may
    discard a row for carrying an unusable symbolic allele (RM5), and the stats were computed by
    `validate_spec` before that happened. `weights_rows` counts the parquet and so is post-drop, so a
    published manifest claimed a `variant_count` one higher than the artifact contained — the RM44
    class of defect exactly, a manifest number a catalog keys on and cannot check.
    """
    genes = sorted({v.gene for v in variants if v.gene})
    return {
        "variant_count": len({v.variant_key for v in variants}),
        "unique_rsids": len({v.rsid for v in variants if v.rsid is not None}),
        "gene_count": len(genes),
        "genes": genes,
        "categories": sorted({v.category for v in variants if v.category}),
        # ClinVar/quality flag counts over variant rows (ROADMAP item 5).
        "clinvar_count": sum(1 for v in variants if v.clinvar),
        "pathogenic_count": sum(1 for v in variants if v.pathogenic),
        "benign_count": sum(1 for v in variants if v.benign),
    }


#: The `Defaults` fields a `VariantRow` may also carry on the row, resolved before hashing (RM37).
_DEFAULTED_VARIANT_FIELDS: tuple[str, ...] = ("curator", "method", "priority")


def _resolve_spec_defaults(rows: list[Any], defaults: Defaults) -> None:
    """Replace each row's `curator`/`method`/`priority` with its **effective** value, in place (RM37).

    `defaults:` in `module_spec.yaml` and the cell on the row are two spellings of one value, and
    which one a module uses is a matter of where the author typed it. Hashing the cell alone made the
    two spellings different content — so `compile → reverse → compile` moved `content_signature` for
    any module that wrote the value per row, because `reverse_module` re-emits it in the other place
    (it infers the module default from the commonest value and blanks the matching cells). The data
    was never lost: `artifact.digest` was byte-identical, because the *compile* side has always
    resolved the same `row value or default`. Only the pre-resolution identity disagreed with itself.

    Resolving here makes the signature a function of what the module *means* rather than of where it
    was written, which is the property a content-dedup key needs.

    **A value equal to the `Defaults` model's own default is written back as `None`, not as itself.**
    That is not a special case — it is the same normalization `integrity.content_signature` already
    applies to `genome_build` and to every unset optional column (`exclude_none=True`), and it is what
    keeps the change targeted: a module that never mentions `curator`/`method`, or names the built-in
    values, keeps its existing signature byte for byte. What moves is a module that states something
    else, which is exactly the module whose two spellings were being hashed apart.
    """
    model_defaults = {name: Defaults.model_fields[name].default for name in _DEFAULTED_VARIANT_FIELDS}
    for row in rows:
        for name, model_default in model_defaults.items():
            authored = getattr(row, name)
            effective = authored if authored is not None else getattr(defaults, name)
            setattr(row, name, None if effective == model_default else effective)


def content_signature(spec_dir: Path) -> str:
    """Stable content identity over the raw authored data CSVs — name- and Ensembl-independent.

    Reads `variants.csv`, `studies.csv`, and any present 0.4 table CSVs, validates each row, and
    hashes the normalized + deterministically-sorted rows via
    `just_dna_format.integrity.content_signature`. The data is read **as authored** (no Ensembl
    resolution, no parquet build), so this is cheap and reference-independent — a client can compute
    it without recompiling and dedup against a registry, surviving both metadata-strip and a recompile
    against a different reference. Raises `ValueError` if a present data CSV fails validation.

    "As authored" means the *rows*, not the *spelling*: `module_spec.yaml`'s `defaults:` block is
    folded into each variant row first (`_resolve_spec_defaults`, RM37), because a value written once
    under `defaults:` and the same value written on every row are the same content.
    """
    spec_dir = Path(spec_dir)
    # The declared build is part of the content, not metadata about it: identical coordinate rows on
    # two assemblies describe two different loci. A spec whose yaml will not load falls back to the
    # format default — this function raises on an invalid *data* CSV, and an unreadable yaml is
    # `validate_spec`'s finding to report, not this one's.
    config, _, _ = _load_yaml(spec_dir / "module_spec.yaml")
    declared_build = config.genome_build if config else DEFAULT_GENOME_BUILD
    kinds: list[tuple[str, type[BaseModel]]] = [
        ("variants.csv", VariantRow),
        ("studies.csv", StudyRow),
        *((csv_name, model) for csv_name, _parquet, model in _TABLE_KINDS),
    ]
    tables: dict[str, list[Any]] = {}
    for csv_name, model in kinds:
        path = spec_dir / csv_name
        if not path.is_file():
            continue
        rows, errors, _ = _load_csv_rows(path, model, csv_name, genome_build=declared_build)
        if errors:
            raise ValueError(f"cannot compute content_signature: {csv_name} is invalid: {errors[0]}")
        if model is VariantRow:
            # The only model carrying `Defaults`' fields. Safe to mutate: these rows were loaded here
            # and go nowhere else — the compile path loads its own copy.
            _resolve_spec_defaults(rows, config.defaults if config else Defaults())
        tables[csv_name] = rows
    return _content_signature(tables, declared_build)


def compile_module(
    spec_dir: Path,
    output_dir: Path,
    compression: str = "zstd",
    resolve_with_ensembl: bool = True,
    ensembl_cache: Path | None = None,
    compiled_by: str | None = None,
    ensembl_reference: str | None = None,
    log_files: list[Path] | None = None,
    provenance_file: Path | None = None,
    logo_file: Path | None = None,
    readme_file: Path | None = None,
    authority_keys: Iterable[str] | None = None,
    strict: bool = False,
    ba1_threshold: float = BA1_ALLELE_FREQUENCY_THRESHOLD,
) -> CompilationResult:
    """Compile a module spec directory into parquet files plus a `manifest.json`.

    Args:
        spec_dir: Path to the module spec directory.
        output_dir: Directory for output parquet files + manifest.json.
        compression: Parquet compression codec.
        resolve_with_ensembl: Master switch for resolution — of **every** kind, despite the name.
            With a `resolution.csv` present it drives the preferred, source-independent table path;
            `ensembl_cache` is the deprecated fallback. Setting it False with a `resolution.csv`
            present disables that table too, and warns, because the compile then succeeds with no
            resolved position on any row.
        ensembl_cache: **Deprecated (removed at 1.0).** Path to a prebuilt Ensembl DuckDB or parquet
            cache dir. In-compiler DuckDB resolution has moved to `just-dna-enricher`; when given, this
            emits a `DeprecationWarning` and routes to the enricher (which must be installed). Prefer
            producing a `resolution.csv` (`just-dna-enricher enrich`) — the compiler then resolves with
            no reference and no network.
        compiled_by: Provenance tag for the manifest (the marketplace passes "marketplace-server";
            a local compile leaves it None, so downloaders treat it as untrusted).
        ensembl_reference: Pinned reference id recorded in the manifest for reproducibility.
        log_files: Explicit run/provenance log files to record. If None, auto-discovers a top-level
            `*.log` plus per-role files under `spec_dir/logs/`. Logs are optional.
        provenance_file: Explicit structured-provenance document. If None, auto-discovers
            `spec_dir/provenance.json`. Optional; summarized into `manifest.provenance`.
        logo_file: Explicit module logo image. If None, auto-discovers `spec_dir/logo.{png,jpg,jpeg}`.
            Optional; hashed into `manifest.logo`, kept out of `artifact.digest`.
        readme_file: Explicit module readme. If None, auto-discovers the first of
            `manifest.README_CANDIDATES` (`README.md` first) beside the spec. Optional; hashed into
            `manifest.readme`, kept out of `artifact.digest` and `content_signature` — prose about the
            module is not part of its identity, so fixing a caveat is a patch (S25).
        authority_keys: Inject-only set of consumer/registry-owned identity keys to strip from the
            authored `module:` block before validation (e.g. `just_dna_format.normalize.
            IDENTITY_AUTHORITY_KEYS`). None strips nothing.
        strict: All-or-nothing compile. When True, fail (rather than emit a partial artifact) if any
            variant still lacks a resolved genomic position (`chrom`+`start`) after resolution — an
            unresolved position means the injected reference was incomplete/absent and the parquet
            bytes (hence `artifact.digest`) would not be reproducible. Default False keeps the
            best-effort behavior (positions left unset, surfaced as warnings).
        ba1_threshold: Allele frequency above which a `pathogenic` variant draws the ACMG BA1 warning
            (`_check_ba1_lint`). Defaults to ACMG's 5%. Raise it for a module curating a common
            recessive carrier allele, where the default fires on correct data. Warning-only in both
            modes, so this tunes noise, never whether the compile succeeds.
    """
    spec_dir = Path(spec_dir)
    output_dir = Path(output_dir)

    # `strict` is deliberately NOT passed (the pre-flight runs in best_effort whatever this compile's
    # mode, which is why every mode-ladder check re-runs below); `resolve_with_ensembl` is, because it
    # is not a severity — it decides whether the injected table is consulted at all, and a pre-flight
    # answering that differently would seed `all_warnings` with a finding this compile contradicts.
    validation = validate_spec(spec_dir, authority_keys, resolve_with_ensembl=resolve_with_ensembl)
    if not validation.valid:
        return CompilationResult(
            success=False, errors=validation.errors, warnings=validation.warnings
        )

    config, _, _ = _load_yaml(spec_dir / "module_spec.yaml", authority_keys)
    assert config is not None
    module_name = config.module.name

    # A module composes from optional table kinds (RM2): load whatever is present.
    variants: list[VariantRow] = []
    if (spec_dir / "variants.csv").exists():
        variants, _, _ = _load_csv_rows(
            spec_dir / "variants.csv", VariantRow, "variants.csv",
            genome_build=config.genome_build,
        )
        # Same re-stamp as in `validate_spec`; this function re-loads its own rows, so the fix has to
        # happen on both copies or the artifact would carry the un-corrected keys.
        _restamp_for_build(variants, config.genome_build)
    studies: list[StudyRow] = []
    if (spec_dir / "studies.csv").exists():
        studies, _, _ = _load_csv_rows(
            spec_dir / "studies.csv", StudyRow, "studies.csv", genome_build=config.genome_build
        )
    # The 0.4 table kinds, loaded here rather than at materialization time. Two reasons, and the
    # second is the load-bearing one: the symbolic-allele check below has to reach them, and a check
    # that can refuse must do so **before** `output_dir.mkdir()` — the placement the licence gate
    # already has, for the same reason. (It also removes a second load of every table kind.)
    kind_rows: dict[str, list[Any]] = {}
    for csv_name, _parquet_name, model in _TABLE_KINDS:
        if (spec_dir / csv_name).exists():
            kind_rows[csv_name], _, _ = _load_csv_rows(
                spec_dir / csv_name, model, csv_name, genome_build=config.genome_build
            )

    all_warnings = list(validation.warnings)

    # Symbolic/structural alleles the module cannot apply (RM5). Runs before anything is written, and
    # before resolution, because it decides which rows exist: under `best_effort` a row stating an
    # unusable rule is **dropped** (the warning says so — `reverse` will not re-emit it), under
    # `strict` the compile refuses. Re-run here rather than trusted from `validate_spec`, which ran in
    # `best_effort` whatever this compile's mode; the warnings it already produced are de-duplicated
    # on the message, the way ploidy's and allele-membership's are.
    symbolic_errors, symbolic_warnings, symbolic_drops = _check_symbolic_alleles(
        {"variants.csv": variants, **kind_rows}, strict=strict
    )
    all_warnings.extend(w for w in symbolic_warnings if w not in all_warnings)
    if symbolic_errors:
        return CompilationResult(success=False, errors=symbolic_errors, warnings=all_warnings)
    for table, drop_rows in symbolic_drops.items():
        if table == "variants.csv":
            variants = _apply_symbolic_drops(variants, drop_rows)
            # Re-derive the variant facets over what survived. `validate_spec` computed them from the
            # full set, and `weights_rows` counts the parquet, so leaving them would publish a
            # `variant_count` higher than the artifact holds (the RM44 class: a manifest number a
            # catalog keys on and cannot check).
            validation.stats.update(variant_stats(variants))
        else:
            kind_rows[table] = _apply_symbolic_drops(kind_rows[table], drop_rows)

    # The source-independent resolution table (0.5), if authored/produced beside the spec. When
    # present it is the *preferred* resolution path: the compiler consumes already-resolved facts and
    # owns no source convention (Ensembl/DuckDB/provisioning) — the strict inject-only end state
    # (Principle 2). An injected `ensembl_cache` (the DuckDB path) is the superseded fallback (P3).
    resolution_rows: list[ResolutionRow] = []
    resolution_table: dict[str, list[ResolutionRow]] = {}
    resolution_sources: list[str] = []
    resolution_sig: str | None = None
    # 0/0 for a module with no resolution table: no allele identities were attempted, which is a
    # different statement from "none were achieved" and is what the manifest should carry.
    vrs_alleles = vrs_identified = 0
    resolution_path, res_spelling_warnings, res_spelling_errors = _locate_sidecar(
        spec_dir, "resolution.csv"
    )
    if res_spelling_errors:
        return CompilationResult(success=False, errors=res_spelling_errors, warnings=all_warnings)
    all_warnings.extend(w for w in res_spelling_warnings if w not in all_warnings)
    if resolution_path is not None:
        resolution_rows, res_errors, _ = _load_csv_rows(
            resolution_path, ResolutionRow, resolution_path.name
        )
        if res_errors:
            return CompilationResult(success=False, errors=res_errors, warnings=all_warnings)
        for row in resolution_rows:
            resolution_table.setdefault(row.variant_key, []).append(row)
        # Content-addressed identities are checkable against themselves — do it before anything is
        # written, so a tampered id never reaches an artifact. Dep-free (stdlib), see `_verify_vrs_ids`.
        # De-duplicated on the message, the same way ploidy and allele-membership are: `validate_spec`
        # ran this pass over the same injected rows and `all_warnings` was seeded from its result, so
        # every finding is already in the list once. Harmless while these were strict-mode *errors*
        # (which return early) and merely untidy for the coverage line (one per module); now that an
        # unverifiable allele warns in every mode it is one duplicated line per allele, and
        # `pathogenic_clinvar` alone would print 185 of them twice.
        vrs_errors, vrs_warnings = _verify_vrs_ids(resolution_rows)
        all_warnings.extend(w for w in vrs_warnings if w not in all_warnings)
        if vrs_errors:
            return CompilationResult(success=False, errors=vrs_errors, warnings=all_warnings)
        all_warnings.extend(
            w for w in _vrs_coverage_warnings(resolution_rows) if w not in all_warnings
        )
        vrs_alleles, vrs_identified, _gaps = _vrs_coverage(resolution_rows)
        # The table's identity is stamped **here**, where the table was read, rather than inside the
        # `variants`-gated resolution block below — which is where it used to sit, and which meant a
        # module with no `variants.csv` published `resolution_signature: null` while carrying a
        # perfectly good `resolution.csv` beside its spec. Four of the eleven reference examples are
        # exactly that shape, so a consumer holding a PGx manifest could not tell a module resolved
        # from one that never was, on the one field that answers it.
        #
        # It was gated that way for a real reason that RM43 removed: until 0.6 `reverse_module` rebuilt
        # this table from `weights.parquet` alone, so a table-only module round-tripped to a spec with
        # no `resolution.csv` and stamping the signature would have published an identity the next
        # compile could not reproduce (P7). Reverse now rebuilds it from the positional parquets too.
        #
        # **The residual, measured rather than assumed.** The signature reproduces exactly when the
        # artifact consumed the whole table — all eleven reference examples, and every clean row of
        # `test_resolution_matrix.py`. It does **not** reproduce when the table says more than the
        # module uses: a row about a variant the module does not carry, an unplaced one-to-many, a
        # coordinate the author overrode. Reverse rebuilds the table from the artifact, so a fact the
        # artifact never held has nowhere to come back from — the same structural reason
        # `rsid_alternates` is unrecoverable. That is **not new and not positional**: a plain SNP
        # module with one unused injected row has always behaved this way, and it is pinned in the
        # matrix now (`Case.table_says_more`) because stamping here is what first made it visible.
        # `artifact.digest` is reproducible throughout, which is why `strict` has nothing to refuse.
        #
        # Still gated on `resolve_with_ensembl`: under `--no-resolve` the table is deliberately not
        # consulted (the warning above says so), and a signature naming a table that shaped nothing
        # would claim the artifact was built from it.
        #
        # And gated on the table having ROWS, not merely existing. A header-only `resolution.csv`
        # hashes to the empty-set digest, which is a perfectly valid signature of nothing — publishing
        # it costs `resolution_signature is not None` its meaning ("this module was resolved"). The
        # deprecated `ensembl_cache` branch makes it worse than cosmetic: an empty `resolution_table`
        # is falsy there, so the DuckDB path runs and the manifest would name an injected table that
        # shaped none of the bytes — the same false claim the `--no-resolve` warning refuses to make.
        if resolve_with_ensembl and resolution_rows:
            resolution_sources = sorted({row.source for row in resolution_rows if row.source})
            resolution_sig = _resolution_signature(resolution_rows)

    # Do the alleles the module *states* exist at the loci it points at? Runs here, on the AUTHORED
    # rows, because resolution may expand one rsid into several loci that share this genotype — after
    # that expansion the check reports the siblings it was never about. See `_check_allele_membership`.
    allele_errors, allele_warnings = _check_allele_membership(
        variants, resolution_table, strict=strict
    )
    # De-duplicated on the message, the same way `_check_contig_ploidy` below is and for the same
    # reason: `compile_module` runs `validate_spec` first, in **best_effort** regardless of this
    # compile's mode, so a check living in both places emits its warning twice. Re-running it here is
    # not redundant — it is how a mode ladder reaches its real severity, since the inner pass cannot
    # know `strict`. What is redundant is printing the identical sentence a second time.
    all_warnings.extend(w for w in allele_warnings if w not in all_warnings)
    if allele_errors:
        return CompilationResult(success=False, errors=allele_errors, warnings=all_warnings)

    p_value_errors, p_value_warnings = _check_p_value_num(studies, strict=strict)
    all_warnings.extend(p_value_warnings)
    if p_value_errors:
        return CompilationResult(success=False, errors=p_value_errors, warnings=all_warnings)

    resolution_mode: str | None = None
    # The flag reads as "do not use Ensembl", and since 0.5 made the compiler inject-only that is
    # exactly what a consumer migrating to `resolution.csv` expects it to mean. It is actually the
    # master switch for resolution *of any kind*, so turning it off with a complete, correct table
    # sitting beside the spec compiles **successfully** with `chrom=None` on every weight row — rows
    # that can never match a VCF. A silent success is the worst shape a mistake can take, so the
    # combination that cannot be intended says so. (Renaming it is a 1.0 conversation: the parameter
    # is part of a published signature.)
    if not resolve_with_ensembl and resolution_table:
        # The unread row count is in the message because a warning that quantifies over a table should
        # publish the size of what it skipped — the same reason `vrs_alleles` ships beside
        # `vrs_alleles_identified`. Rows, not keys: a one-to-many rsid contributes several.
        unread = sum(len(rows) for rows in resolution_table.values())
        all_warnings.append(
            f"--no-resolve (resolve_with_ensembl=False) switches off resolution entirely, including "
            f"the injected resolution.csv beside this spec ({unread} row(s), covering "
            f"{len(resolution_table)} variant key(s)), which was not read — every variant will compile "
            f"with no chrom/start and match no VCF. The flag names Ensembl but is the master switch; "
            f"drop it to use the injected table. There is no flag for 'do not reach the network' "
            f"because the compiler never does (CONSTITUTION P2) — omitting this one is that request."
        )
    if resolve_with_ensembl and variants:
        resolution_mode = "strict" if strict else "best_effort"
        resolve_warnings: list[str] = []
        resolve_strict_errors: list[str] = []
        if resolution_table:
            outcome = resolve_from_table(
                variants, resolution_table, genome_build=config.genome_build
            )
            variants = outcome.variants
            resolve_warnings = outcome.warnings
            resolve_strict_errors = outcome.strict_errors
            if outcome.errors:
                # Fatal in both modes — today only a curator-recorded `withdrawn` rsID. See
                # `ResolutionOutcome`.
                return CompilationResult(
                    success=False,
                    errors=[f"resolution: {e}" for e in outcome.errors],
                    warnings=all_warnings + resolve_warnings,
                )
            # `resolution_sources` / `resolution_sig` are stamped where the table is READ, several
            # blocks up — not here. This branch is about applying the table to `variants.csv`, and
            # tying the table's identity to that application is what left every table-only module
            # unstamped.
        elif ensembl_cache is not None:
            # DEPRECATED (removed at 1.0): the in-compiler DuckDB-reference path. Resolution now belongs
            # to the source-independent `resolution.csv` (produce it with `just-dna-enricher enrich`); the
            # compiler owns no source/DuckDB logic. This surface is kept working by routing to the
            # enricher — additive-within-a-major binds the wire/artifact *contract*, not this internal
            # call, so the legacy path can retire at the next major. Guarded optional import (CLAUDE.md).
            warnings.warn(
                "compile_module(ensembl_cache=...) / in-compiler DuckDB resolution is deprecated and "
                "will be removed at 1.0. Produce a resolution.csv (e.g. `just-dna-enricher enrich`) and "
                "the compiler consumes it with no reference and no network.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                from just_dna_enricher.resolver import resolve_variants as _legacy_resolve
            except ImportError:
                return CompilationResult(
                    success=False,
                    errors=[
                        "ensembl_cache resolution now lives in just-dna-enricher (the network tier). "
                        "Install just-dna-enricher, or precompute resolution.csv and recompile without "
                        "ensembl_cache."
                    ],
                    warnings=all_warnings,
                )
            variants, resolve_warnings = _legacy_resolve(
                variants, ensembl_cache, genome_build=config.genome_build
            )
        elif any(v.chrom is None or v.start is None for v in variants):
            # Nothing injected: the compiler no longer auto-discovers or fetches a reference (P2,
            # tightened in 0.5). Variants lacking a position are left unresolved with a pointer.
            resolve_warnings = [
                "No resolution.csv and no ensembl_cache injected; variants lacking a genomic position "
                "are left unresolved. Produce a resolution.csv with just-dna-enricher."
            ]
        all_warnings.extend(resolve_warnings)
        # The round-trip contract. `strict` promises a *reproducible* artifact, and these are the
        # conditions under which `compile → reverse → compile` cannot reproduce the resolution table
        # it started from (a dropped locus, an authored coordinate contradicting the table), plus the
        # one that is reproducible but rests on a guessed label (`ambiguous`). `best_effort` already
        # carries them as warnings above. See COMPILER.md § Resolution.
        if strict and resolve_strict_errors:
            return CompilationResult(
                success=False,
                errors=[f"strict resolution: {e}" for e in resolve_strict_errors],
                warnings=all_warnings,
            )
        # Resolution is an enrichment that can *change identity*: filling a coordinate or expanding a
        # one-to-many rsid into coord-keyed rows may collide with an already-authored row. validate_spec
        # ran on the pre-resolution set, so re-run the identity checks on the resolved set — a duplicate
        # (variant_key, genotype) or an inconsistent position must fail the compile, not silently land in
        # weights.parquet. Only errors are taken (warnings were already surfaced pre-resolution).
        post_errors, _ = _cross_validate_variants(variants)
        if post_errors:
            return CompilationResult(
                success=False,
                errors=[f"post-resolution: {e}" for e in post_errors],
                warnings=all_warnings,
            )

    # The non-diploid guardrail runs **here**, once, because this is the first point at which `chrom`
    # is final for every row — resolution has either run and filled it or was skipped. Inside
    # `_cross_validate_variants` it was emitted from the pre-resolution pass only (the post-resolution
    # call takes errors alone), so an rsID-authored MT or Y row — the shape every drafting provider
    # writes — was never checked at all.
    all_warnings.extend(
        w for w in _check_contig_ploidy(variants, config.genome_build) if w not in all_warnings
    )

    # Wrong-build coordinates, re-run **here** for the same reason ploidy is: this is the first point
    # at which `chrom`/`start` are final. `validate_spec` sees an rsid-only row with no coordinate at
    # all; resolution has since filled one, and the deprecated `ensembl_cache` path fills it from a
    # reference `validate_spec` never opened. Unlike ploidy this needs no de-duplication: it returns
    # errors, `compile_module` returns early on any validation error, so anything reaching here is a
    # coordinate the pre-flight could not have seen.
    build_errors = _check_build_coordinates(
        [_CoordinateTable("variants.csv", config.genome_build, True, variants)]
    )
    if build_errors:
        return CompilationResult(
            success=False,
            errors=[f"post-resolution: {e}" for e in build_errors],
            warnings=all_warnings,
        )

    # Outcome axis (orthogonal to the requested `resolution_mode` policy, Principle 5): did every
    # in-scope variant resolve to a genomic position? Vacuously true for a table-kind-only module —
    # which is why the denominator travels beside it into the manifest (RM44). Both come from the same
    # list, so the flag can never be published without the count that says what it quantified over.
    fully_resolved = all(v.chrom is not None and v.start is not None for v in variants)
    resolution_subjects = len(variants)

    # Strict (all-or-nothing): refuse to write a partial artifact. A variant still missing its
    # genomic position after resolution means the injected reference was incomplete or absent, so the
    # coordinate-anchored parquet bytes (and `artifact.digest`) would not be reproducible — the
    # failure mode behind "local hash differs from published". Best-effort (strict=False) leaves such
    # rows unset with a warning instead. Scope is the SNP-core VariantRow; the 0.4 table kinds carry
    # no positions.
    if strict and variants:
        unresolved = sorted(
            v.rsid or v.variant_key for v in variants if v.chrom is None or v.start is None
        )
        if unresolved:
            return CompilationResult(
                success=False,
                errors=[
                    f"strict compile: {len(unresolved)} variant(s) have unresolved genomic "
                    f"positions after resolution: {unresolved}. A partial artifact would not be "
                    f"byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or "
                    f"compile without strict."
                ],
                warnings=all_warnings,
            )

    # Licensing gate. Loaded here rather than with the other fact tables because those are read
    # *after* `output_dir.mkdir()`, and a refusal must leave nothing written — this is the last point
    # at which that is still true. Purely computation over injected data: the compiler holds no
    # source→licence map (Principle 2 — it owns no source convention) and only reads what the
    # enricher recorded.
    sources_path, gate_spelling_warnings, gate_spelling_errors = _locate_sidecar(
        spec_dir, SOURCES_CSV
    )
    if gate_spelling_errors:
        return CompilationResult(success=False, errors=gate_spelling_errors, warnings=all_warnings)
    all_warnings.extend(w for w in gate_spelling_warnings if w not in all_warnings)
    if sources_path is not None:
        gate_rows, gate_load_errors, _ = _load_csv_rows(sources_path, SourceRow, sources_path.name)
        if gate_load_errors:
            return CompilationResult(
                success=False, errors=gate_load_errors, warnings=all_warnings
            )
        gate_errors = _check_license_gate(gate_rows)
        if gate_errors:
            return CompilationResult(success=False, errors=gate_errors, warnings=all_warnings)

    output_dir.mkdir(parents=True, exist_ok=True)

    # SNP core: weights/annotations only when the module actually has variants.
    weights_df = _build_weights(variants, config) if variants else None
    annotations_df = _build_annotations(variants, module_name) if variants else None
    studies_df = _build_studies(studies, module_name) if studies else None
    if weights_df is not None:
        weights_df.write_parquet(output_dir / "weights.parquet", compression=compression)
    if annotations_df is not None:
        annotations_df.write_parquet(output_dir / "annotations.parquet", compression=compression)
    if studies_df is not None:
        studies_df.write_parquet(output_dir / "studies.parquet", compression=compression)

    # The positional fill (RM43), on the rows that survive. It runs **after** the symbolic-allele
    # ladder (RM5) and before `_build_table`, and that order is the only correct one: the drop decides
    # which rows exist, so filling first would resolve a coordinate onto a row about to be discarded
    # and — worse — leave the joinability report below counting rows the artifact does not contain.
    # The two never disagree because the drop happens up at load time, long before the resolution
    # table is even read; this comment is here so the distance between them does not read as accident.
    # Gated on `resolve_with_ensembl` like every other resolution, so `--no-resolve` consults nothing.
    fill_warnings, fill_applied = _apply_positional_resolution(
        kind_rows, resolution_table, config.genome_build, resolve=resolve_with_ensembl
    )
    all_warnings.extend(w for w in fill_warnings if w not in all_warnings)

    # 0.4 table kinds (RM1): materialize each present CSV via the generic materializer. The rows were
    # loaded above, before `mkdir`, so the symbolic-allele check could refuse without leaving a
    # half-written directory behind — and so a row it dropped is absent from the parquet here.
    table_rows: dict[str, int] = {}
    for csv_name, parquet_name, model in _TABLE_KINDS:
        rows = kind_rows.get(csv_name)
        if rows is None:
            continue
        table_df = _build_table(rows, model, module_name)
        table_df.write_parquet(output_dir / parquet_name, compression=compression)
        table_rows[parquet_name] = table_df.height

    # Re-run here so the finding reaches a caller who compiles without validating first, and
    # de-duplicated on the message the way `_check_contig_ploidy` is: `compile_module` runs
    # `validate_spec` itself, so a check living in both places otherwise prints its sentence twice.
    all_warnings.extend(
        w
        for w in _check_positional_joinability(
            kind_rows, resolution_table, config.genome_build, fill_applied=fill_applied
        )
        if w not in all_warnings
    )
    all_warnings.extend(
        w for w in _check_binning_grounding(kind_rows, studies) if w not in all_warnings
    )
    # `kind_rows` is freshly loaded and never resolved, so re-running the binning check here produces
    # the identical sentence and the message-dedup above does its job.
    all_warnings.extend(w for w in _check_measure_shape(kind_rows) if w not in all_warnings)

    # **THREE checks of this round are deliberately NOT re-run here, and that is the fix rather than an
    # omission.** `_check_missing_allele_marker`, `_check_quality_inversion` and `_check_vcf_pointers`
    # all read authored cells (`alts`, `requires_callable` + `quality_from`, the pointer columns) that
    # resolution never fills, so `validate_spec`'s pass — which runs before any expansion — already has
    # the right answer, and it reaches this list through `all_warnings = list(validation.warnings)`
    # above. Running any of them again on `variants` would count the *expanded* rows: by this point
    # `variants` is `outcome.variants`, one row per resolved locus, so a one-to-many rsid becomes N rows
    # carrying one authored genotype and the same finding is reported with a different count and
    # different example keys. The de-duplication above keys on the **message**, so two sentences
    # differing only in their count can never collapse, and both are published into
    # `manifest.compilation.warnings` — a surface RM44 established that consumers parse. Measured twice,
    # independently, on the way in: an rsid-only `requires_callable` row over a two-locus
    # `resolution.csv` emitted "1 row(s) …" beside "2 row(s) …", and the pointer check emitted 328
    # beside 337 on `pathogenic_clinvar`.
    #
    # Nothing is lost by staying behind resolution: all three are warning-only in both modes, so there
    # is no severity for a re-run to recover — which is the whole reason the *mode-ladder* checks re-run
    # at all. This is the mirror of the `_check_contig_ploidy` lesson rather than a contradiction of it:
    # that warning had to **move** here because resolution fills its input; these three must stay behind
    # it because resolution fills nothing they read. The rule that covers both: re-run a check after
    # resolution exactly when resolution changes its input, and never when the message embeds a count.

    # 0.5 derived-fact sidecars: materialize each present CSV, and cross-check it against what the
    # module actually contains. A row describing something the module never mentions is a warning, not
    # an error — an over-broad sidecar is harmless (a stale gene left in after a variant was removed),
    # while failing the compile over it would punish the author for the enricher's generosity.
    # One branch per sidecar, keyed by model. A two-way `if/else` was fine for two tables and stops
    # being readable at three, so each entry states its own checks and its own builder; the loop below
    # stays generic. Errors are fatal, warnings accumulate — the same contract the SNP core uses.
    def _frequency_checks(rows: list) -> tuple[list[str], list[str]]:
        errors, warns = _check_frequency_arithmetic(rows)
        warns = list(warns)
        warns.extend(_cross_check_frequencies(rows, variants))
        warns.extend(_check_ba1_lint(rows, variants, threshold=ba1_threshold))
        return errors, warns

    def _gene_metrics_checks(rows: list) -> tuple[list[str], list[str]]:
        warns = list(_check_gene_metrics_arithmetic(rows))
        warns.extend(_cross_check_gene_metrics(rows, variants))
        return [], warns

    def _literature_checks(rows: list) -> tuple[list[str], list[str]]:
        # De-duplicated on the message: `compile_module` runs `validate_spec`, which runs this same
        # check, so a finding living in both places would otherwise print twice (the
        # `_check_contig_ploidy` idiom).
        return [], [
            w for w in _cross_check_literature(rows, studies, kind_rows) if w not in all_warnings
        ]

    def _gene_validity_checks(rows: list) -> tuple[list[str], list[str]]:
        return [], list(_cross_check_gene_validity(rows, variants))

    def _clinical_assertion_checks(rows: list) -> tuple[list[str], list[str]]:
        return [], list(_cross_check_clinical_assertions(rows, variants))

    def _sources_checks(rows: list) -> tuple[list[str], list[str]]:
        # `sources.csv` is last in `_FACT_TABLES`, so the other sidecars are already parsed into
        # `fact_rows` and their `source` values can be cross-checked here. Warnings only — the gate
        # that can actually refuse already ran, before anything was written.
        #
        # `SourceRow` is excluded from the "used" set: the loop stores each model's rows into
        # `fact_rows` *before* calling its check, so including it would let sources.csv vouch for
        # itself and no orphan could ever be reported.
        # Resolution contributes its **authority**, not its `source`: that column names which *link*
        # answered (`ensembl-rest`, `cache`) while every other table's names a licensed source, so
        # comparing them by string made every enriched module warn that `ensembl-rest` has no terms
        # recorded (RM33). A row with no authority contributes nothing — `authored`/`reversed` have no
        # external source to declare, and an older `resolution.csv` written before the column existed
        # simply says nothing rather than saying the wrong thing.
        used = {r.authority for r in resolution_rows if r.authority}
        for model, parsed in fact_rows.items():
            if model in (SourceRow, LiteratureRow):
                continue
            used |= {getattr(r, "source", None) for r in parsed if getattr(r, "source", None)}
        warns = _source_checks(rows, {s for s in used if s})
        warns.extend(_check_declared_license_agrees(rows, config.license if config else None))
        return [], warns

    _FACT_HANDLERS: dict[type, tuple[Callable, Callable]] = {
        FrequencyRow: (_frequency_checks, lambda rows: _build_frequencies(rows, module_name)),
        GeneMetricsRow: (_gene_metrics_checks, lambda rows: _build_table(rows, GeneMetricsRow, module_name)),
        LiteratureRow: (_literature_checks, lambda rows: _build_table(rows, LiteratureRow, module_name)),
        GeneValidityRow: (
            _gene_validity_checks, lambda rows: _build_table(rows, GeneValidityRow, module_name),
        ),
        ClinicalAssertionRow: (
            _clinical_assertion_checks,
            lambda rows: _build_table(rows, ClinicalAssertionRow, module_name),
        ),
        SourceRow: (_sources_checks, lambda rows: _build_table(rows, SourceRow, module_name)),
    }

    fact_rows: dict[type, list] = {}
    for csv_name, parquet_name, model in _FACT_TABLES:
        # Spelling collisions and the deprecation notice were both already surfaced by the licence
        # gate above (for `sources.csv`) or are surfaced here for the first time; either way the
        # notices de-duplicate, the way ploidy's and the VRS pass's already do.
        fact_path, fact_spelling_warnings, fact_spelling_errors = _locate_sidecar(spec_dir, csv_name)
        if fact_spelling_errors:
            return CompilationResult(
                success=False, errors=fact_spelling_errors, warnings=all_warnings
            )
        all_warnings.extend(w for w in fact_spelling_warnings if w not in all_warnings)
        if fact_path is None:
            continue
        rows, fact_errors, _ = _load_csv_rows(fact_path, model, fact_path.name)
        if fact_errors:
            return CompilationResult(success=False, errors=fact_errors, warnings=all_warnings)
        fact_rows[model] = rows
        check, build = _FACT_HANDLERS[model]
        check_errors, check_warnings = check(rows)
        if check_errors:
            return CompilationResult(success=False, errors=check_errors, warnings=all_warnings)
        all_warnings.extend(check_warnings)
        fact_df = build(rows)
        fact_df.write_parquet(output_dir / parquet_name, compression=compression)
        table_rows[parquet_name] = fact_df.height

    frequency_rows: list[FrequencyRow] = fact_rows.get(FrequencyRow, [])
    gene_metrics_rows: list[GeneMetricsRow] = fact_rows.get(GeneMetricsRow, [])
    literature_rows: list[LiteratureRow] = fact_rows.get(LiteratureRow, [])
    gene_validity_rows: list[GeneValidityRow] = fact_rows.get(GeneValidityRow, [])
    clinical_assertion_rows: list[ClinicalAssertionRow] = fact_rows.get(ClinicalAssertionRow, [])
    source_rows: list[SourceRow] = fact_rows.get(SourceRow, [])

    logs = _collect_logs(spec_dir, output_dir, log_files)
    # Authored side-car assets are validated here (validate_spec does not read them). Surface a
    # malformed one as a compile error instead of letting the exception escape mid-compile.
    try:
        provenance = _collect_provenance(spec_dir, output_dir, provenance_file)
    except ValidationError as exc:
        return CompilationResult(
            success=False, errors=[f"provenance.json is invalid: {exc}"], warnings=all_warnings
        )
    try:
        logo = _collect_logo(spec_dir, output_dir, logo_file)
    except ValueError as exc:
        return CompilationResult(success=False, errors=[str(exc)], warnings=all_warnings)
    try:
        readme = _collect_readme(spec_dir, output_dir, readme_file)
    except ValueError as exc:
        return CompilationResult(success=False, errors=[str(exc)], warnings=all_warnings)
    # The attestation, re-read here because the block is what gets stamped (`validate_spec` ran the
    # same call for its warning and threw the block away). De-duplicated on the message for the
    # standard reason: the pre-flight already emitted the identical sentence.
    verification, verification_warnings = _verification_block(spec_dir)
    all_warnings.extend(w for w in verification_warnings if w not in all_warnings)

    # Content identity over the RAW authored data (re-read from disk, so pre-resolution and
    # reference-independent — the in-scope `variants` here are already resolved). Out of
    # `artifact.digest`; lets a registry dedup across recompile/metadata-strip.
    manifest = _build_manifest(
        config=config,
        spec_dir=spec_dir,
        output_dir=output_dir,
        validation=validation,
        weights_rows=weights_df.height if weights_df is not None else 0,
        warnings=all_warnings,
        compiled_by=compiled_by,
        ensembl_reference=ensembl_reference,
        logs=logs,
        provenance=provenance,
        logo=logo,
        readme=readme,
        content_sig=content_signature(spec_dir),
        resolution_mode=resolution_mode,
        fully_resolved=fully_resolved,
        resolution_subjects=resolution_subjects,
        vrs_alleles=vrs_alleles,
        vrs_alleles_identified=vrs_identified,
        resolution_sig=resolution_sig,
        resolution_sources=resolution_sources,
        frequency=_frequency_block(frequency_rows),
        gene_metrics=_gene_metrics_block(gene_metrics_rows),
        gene_validity=_gene_validity_block(gene_validity_rows),
        clinical_assertions=_clinical_assertions_block(clinical_assertion_rows),
        literature=_literature_block(literature_rows),
        sources=_sources_block(source_rows),
        verification=verification,
    )
    write_manifest(manifest, output_dir / "manifest.json")

    stats: dict[str, Any] = {
        "module_name": module_name,
        "weights_rows": weights_df.height if weights_df is not None else 0,
        "annotations_rows": annotations_df.height if annotations_df is not None else 0,
        "studies_rows": studies_df.height if studies_df is not None else 0,
        "table_rows": table_rows,
    }
    return CompilationResult(
        success=True,
        output_dir=output_dir,
        errors=[],
        warnings=all_warnings,
        stats=stats,
        manifest=manifest,
    )


def _frequency_block(rows: list[FrequencyRow]) -> Frequency | None:
    """The manifest's `frequency` summary, or `None` when the module carries no frequency sidecar.

    `populations` is emitted in the canonical order rather than sorted alphabetically, so it reads the
    way the table reads (`global` first). Every other list is sorted — they are set-like facets, and a
    sorted list is the only order that cannot drift.
    """
    if not rows:
        return None
    populations = sorted({r.population for r in rows}, key=population_sort_key)
    return Frequency(
        signature=_frequency_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        populations=populations,
        row_count=len(rows),
        variant_count=len({r.variant_key for r in rows}),
    )


def _gene_metrics_block(rows: list[GeneMetricsRow]) -> GeneMetrics | None:
    """The manifest's `gene_metrics` summary, or `None` when the module carries no such sidecar."""
    if not rows:
        return None
    return GeneMetrics(
        signature=_gene_metrics_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        genes=sorted({r.gene for r in rows}),
    )


def _gene_validity_block(rows: list[GeneValidityRow]) -> GeneValidity | None:
    """The manifest's `gene_validity` summary, or `None` when the module carries no such sidecar.

    Every facet is a sorted set, including `classifications` — the strength ladder is published once,
    as `vocab.ORDERED_GENE_VALIDITY`, so this block does not encode a second copy of it that could
    drift. `diseases` is here because indexing a module by condition is the reason a catalog would
    read this block instead of the parquet.
    """
    if not rows:
        return None
    return GeneValidity(
        signature=_gene_validity_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        genes=sorted({r.gene for r in rows}),
        diseases=sorted({r.disease_id for r in rows if r.disease_id}),
        classifications=sorted({r.classification for r in rows if r.classification}),
        submitters=sorted({r.submitter for r in rows if r.submitter}),
    )


def _clinical_assertions_block(rows: list[ClinicalAssertionRow]) -> ClinicalAssertions | None:
    """The manifest's `clinical_assertions` summary, or `None` when the module carries no such sidecar.

    The star range is `min`/`max` over the rows that state one, and `None` when none does — never a
    zero. That is the same rule `Literature.quotes_found` follows and it matters more here: 0 is a real
    rating ("no assertion criteria provided"), so collapsing "nothing was rated" into it would report
    the module's evidence as the worst kind available rather than as unstated. `unrated_count` carries
    the size of that gap, because a range over an unstated fraction is not something a catalog can
    filter on.
    """
    if not rows:
        return None
    rated = [r.review_stars for r in rows if r.review_stars is not None]
    return ClinicalAssertions(
        signature=_clinical_assertion_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        variant_count=len({r.variant_key for r in rows}),
        clin_sigs=sorted({r.clin_sig for r in rows if r.clin_sig}),
        min_review_stars=min(rated) if rated else None,
        max_review_stars=max(rated) if rated else None,
        unrated_count=sum(1 for r in rows if r.review_stars is None),
        not_found_count=sum(1 for r in rows if r.status == "not_found"),
    )


def _check_license_gate(rows: list[SourceRow]) -> list[str]:
    """Refuse to compile a module whose sources forbid sale and that records no matching declaration.

    The refusal fires in **both** modes. `strict`'s single meaning is "produce a reproducible
    artifact"; whether the terms were accepted is unrelated to reproducibility, and overloading the
    flag with a second axis is exactly the orthogonality Principle 5 protects.

    It is keyed on **data carried by the module**, never on a CLI flag. That is what keeps
    `compile → reverse → compile` a fixed point (Principle 7): `reverse_module` rebuilds
    `module_spec.yaml` from parquet alone and could never re-emit a flag, so a flag-gated compile
    would refuse on the third step. `sources.csv` round-trips, so the declaration travels with the
    module and the cycle reproduces.

    Most-restrictive-wins, module-wide: one tainting row refuses the whole compile. Mixing a
    permissive source into a restricted one cannot launder it, which is why the verdict is not
    computed per row or per layer.
    """
    tainted = [r for r in rows if taints_commercial_use(r)]
    if not tainted:
        return []
    # A single declaration governs the module, so any tainted row lacking one refuses. `unstated` is
    # not a loophole: it is the absence of a declaration, which is precisely what this gate wants.
    undeclared = sorted(
        {r.source for r in tainted if r.declared_use != "non_commercial"}
    )
    if not undeclared:
        return []
    return [
        f"licensing: {undeclared} contribute annotation-layer content under terms that forbid sale, "
        f"and this module records no non-commercial declaration for them. Re-run the enricher with "
        f"a declared use (`--use non-commercial`) to record one, or remove the affected content. "
        f"Declaring it is an assertion about how the module will be used — the compiler records that "
        f"assertion, it does not verify it."
    ]


#: The `sources.csv` layers no fact table's `source` column can ever corroborate, so a declaration at
#: one of them is uncorroborable rather than stale. See `_source_checks` for why each is here.
_UNCORROBORABLE_LAYERS: frozenset[str] = frozenset({"annotation", "literature"})


def _source_checks(rows: list[SourceRow], used_sources: set[str]) -> list[str]:
    """Warning-only coherence for `sources.csv`. Never escalates under `strict`.

    Two findings, both mirroring the existing orphan-sidecar precedent (don't punish the author for
    the enricher's generosity):

    - a declared source that no fact table actually used — over-declaration, harmless but probably
      stale; and
    - a source used by a fact table with no `sources.csv` row — under-declaration, which matters more
      but still cannot be an error, because the compiler cannot know whether the omission is an
      oversight or a source with no terms worth recording.

    The second is emitted **only when `sources.csv` exists at all**, so a module without one warns
    exactly as it does today (Principle 3).

    **`annotation`-layer rows are exempt from the orphan half, and that is structural rather than a
    softening.** "No table used it" is decided by reading the fact tables' `source` columns, and the
    annotation layer *is* `variants.csv`/`diplotypes.csv`/…, which carry no such column by design (a
    curated annotation's provenance is the module's, not a per-row link). So an annotation-layer row can
    never be corroborated and was reported as stale on **every** drafted module — `clinvar_draft` and
    `pgx_draft` both write exactly one such row, and it is the row that makes the licence gate work.
    Warning that the load-bearing row looks unused is the opposite of useful.

    **`literature` joins that exemption, and since 0.6 it joins it unconditionally (S23, then RM46).**
    The same argument, reached by the same route: `studies.csv` is the hand-curated literature table
    and carries no `source` column *by the design the annotation exemption cites*, so a module citing
    a PMID through it can never corroborate the service the curator read the record through. That left
    `literature.csv` — enricher-written, with a `source` column — as the only possible corroborator,
    which is why the exemption used to be conditional on the module having no study rows.

    RM46 removed that last joinable value, and the reason is the point rather than a simplification.
    `literature.csv`'s `source` names the **bibliographic registry that answered** (`pubmed`), not a
    licensed source, and the tier has no terms constant for it *because a literature source's terms
    are per article, not per source*: PubMed's metadata is one thing and the publisher's article is
    another, and Europe PMC's open subset spans CC-BY, CC-BY-NC and bronze. So the article's terms are
    recorded on the literature row itself (`license`/`share_alike`/`commercial_use`/`redistribution`)
    and its `source` is excluded from `used_sources` by the caller. A single `pubmed` row in
    `sources.csv` would be wrong in the dangerous direction — right for a module citing only ids, and
    a false all-clear for one carrying a `provenance_quote` lifted from a CC-BY-NC article. Nothing
    can therefore corroborate a literature-layer declaration, `studies.csv` or no, so the conditional
    could no longer distinguish anything.

    Note which way the old behaviour pushed an author, because that is what makes the exemption worth
    keeping: `vocab.MISPLACED_COLUMN_REASONS['source']` tells an author to declare a hand-read source
    by adding a row to `sources.csv`, and doing so earned a warning that the row is unused, while
    deleting it — and shipping with the provenance unrecorded — was silent. Compliance warned,
    omission quiet. An over-declaration here is the cheap error; an author talked out of recording
    their terms is not. `frequency` still warns, because `frequencies.csv` *is* machine-written with a
    `source` column naming a licensed source, so a frequency declaration in a module with no
    frequencies really is stale.
    """
    warnings: list[str] = []
    declared = {r.source for r in rows}
    corroborable = {r.source for r in rows if r.layer not in _UNCORROBORABLE_LAYERS}
    orphans = sorted(corroborable - used_sources)
    if orphans:
        warnings.append(
            f"sources.csv declares {len(orphans)} source(s) no table in this module uses: {orphans}"
        )
    undeclared = sorted(used_sources - declared)
    if undeclared:
        warnings.append(
            f"sources.csv has no row for {len(undeclared)} source(s) the module's fact tables cite: "
            f"{undeclared} — their terms are unrecorded."
        )
    return warnings


def _check_declared_license_agrees(
    rows: list[SourceRow], declared_license: str | None
) -> list[str]:
    """Warn when `module_spec.yaml`'s `license:` contradicts an annotation-layer source's.

    Warning in **both** modes, deliberately — the second such exception after the ClinVar `clin_sig`
    cross-check, and for the same reason. Every other compiler check compares an authored value
    against a *fact*; this compares two claims about a legal position, and failing the compile would
    make the format arbitrate a licensing dispute. String equality only: an SPDX compatibility matrix
    is world-knowledge that would go stale, and the compiler is not the tier that should hold it.
    """
    if not declared_license:
        return []
    conflicting = sorted(
        {
            r.license
            for r in rows
            if r.layer == "annotation" and r.license and r.license != declared_license
        }
    )
    if not conflicting:
        return []
    return [
        f"module declares license {declared_license!r} but annotation-layer sources report "
        f"{conflicting}. Not adjudicated here — a compatible pair is legitimate, an incompatible "
        f"one is a real problem, and only a human can tell which."
    ]


def _sources_block(rows: list[SourceRow]) -> Sources | None:
    """The manifest's `sources` summary, or `None` when the module carries no licensing sidecar.

    The per-layer facets stay lists (see `Sources`); only `commercial_use` collapses, because it is
    the one question with a single module-wide answer. Its ladder is most-restrictive-first: a
    forbidding source makes it `False`; failing that, an unknown makes it `None` (undetermined, never
    permitted); only an all-known, none-forbidding set makes it `True`.
    """
    if not rows:
        return None
    def _verdict(taints, is_unknown) -> bool | None:
        # Most-restrictive-first: a forbidding source makes it False; failing that, an unknown makes
        # it None (undetermined, never permitted); only an all-known, none-forbidding set makes True.
        if any(taints(r) for r in rows):
            return False
        return None if any(is_unknown(r) for r in rows) else True

    unknown = sorted({r.source for r in rows if r.commercial_use is None})
    verdict = _verdict(taints_commercial_use, lambda r: r.commercial_use is None)
    redistribution_verdict = _verdict(taints_redistribution, lambda r: r.redistribution is None)
    return Sources(
        signature=_source_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        layers=sorted({r.layer for r in rows if r.layer}),
        licenses=sorted({r.license for r in rows if r.license}),
        attributions=sorted({r.attribution for r in rows if r.attribution}),
        notices=sorted({r.notice for r in rows if r.notice}),
        share_alike_layers=sorted({r.layer for r in rows if r.share_alike}),
        noncommercial_layers=sorted({r.layer for r in rows if r.commercial_use is False}),
        nonredistributable_layers=sorted({r.layer for r in rows if r.redistribution is False}),
        unknown_terms_sources=unknown,
        declared_uses=sorted({r.declared_use for r in rows if r.declared_use}),
        commercial_use=verdict,
        redistribution=redistribution_verdict,
        row_count=len(rows),
    )


def _verification_block(spec_dir: Path) -> tuple[Verification | None, list[str]]:
    """The manifest's `verification` block, or `None` plus the reason it is not being published (RM45).

    Returns `(block, warnings)` and **never errors**. Three outcomes, and the middle one is the whole
    point of the item:

    * no `verification.json` → `(None, [])`. Nothing was attested and nothing is said, silently: an
      unverified module is the ordinary case and warning about it would fire on every module in this
      repository.
    * an attestation that no longer matches these bytes, or one that cannot be read → `(None, [why])`.
      **Warn and drop.** Making a mismatch fatal was considered — a record asserting a check over
      bytes that are not these bytes is arguably the inconsistent-reference-allele class — and
      rejected: the goal is that a stale record never becomes a *published claim*, not that it be
      impossible to write, and dropping the block achieves that without stopping an author mid-edit.
      The manifest then carries no verification, which reads correctly as *says nothing* rather than
      as a pass.
    * an attestation that holds → `(block, [])`.

    The binding is recomputed from `authored_input_entries`, the same function that fills
    `manifest.inputs`, so "the spec was edited" and "the inputs listing changed" are one fact rather
    than two that can disagree.
    """
    path, spelling_warnings, spelling_errors = _locate_sidecar(spec_dir, VERIFICATION_JSON)
    # A collision (root *and* `derived/`) is reported rather than raised, and it lands as a warning
    # here where the same collision on a fact table is an error, because the outcome is already the
    # weaker one: two attestations are two claims, neither may be preferred, so nothing is published.
    if spelling_errors:
        return None, spelling_errors + spelling_warnings
    if path is None:
        return None, list(spelling_warnings)
    shown = path.relative_to(spec_dir)
    try:
        doc = read_verification(path)
    except (OSError, ValueError) as exc:
        return None, [
            *spelling_warnings,
            f"{shown} could not be read as a verification attestation ({exc}); this compile records "
            f"no verification. Re-run the checks (just-dna-enricher) to rewrite it.",
        ]
    failure = attestation_failure(doc, _module_binding(spec_dir))
    if failure is not None:
        return None, [
            *spelling_warnings,
            f"{shown} is stale: {failure}. The manifest records no verification for this compile, "
            f"which says nothing rather than claiming a pass. Re-run the checks to attest these bytes.",
        ]
    return verification_block(doc), list(spelling_warnings)


def _module_binding(spec_dir: Path) -> str:
    """The hash an attestation beside `spec_dir` must be bound to."""
    return module_binding(authored_input_entries(spec_dir))


def _literature_block(rows: list[LiteratureRow]) -> Literature | None:
    """The manifest's `literature` summary, or `None` when the module carries no citation sidecar.

    The counters are summed rather than recomputed so the manifest cannot claim more coverage than the
    sidecar recorded. `quotes_found` counts only rows where it is non-null: a null there means "no
    fulltext was retrievable", and folding that into zero would report an unchecked quote as a missing
    one — the single most misleading thing this block could say.
    """
    if not rows:
        return None
    return Literature(
        signature=_literature_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        row_count=len(rows),
        resolved_count=sum(1 for r in rows if r.exists is True),
        missing_count=sum(1 for r in rows if r.exists is False),
        open_access_count=sum(1 for r in rows if r.is_open_access is True),
        abstract_only_count=sum(1 for r in rows if r.quote_source == "abstract"),
        quotes_authored=sum(r.quotes_authored or 0 for r in rows),
        quotes_found=sum(r.quotes_found for r in rows if r.quotes_found is not None),
    )


def _build_manifest(
    *,
    config: ModuleSpecConfig,
    spec_dir: Path,
    output_dir: Path,
    validation: ValidationResult,
    weights_rows: int,
    warnings: list[str],
    compiled_by: str | None,
    ensembl_reference: str | None,
    logs: list[FileEntry],
    provenance: Provenance | None,
    logo: FileEntry | None,
    readme: FileEntry | None = None,
    content_sig: str | None = None,
    resolution_mode: str | None = None,
    fully_resolved: bool = False,
    resolution_subjects: int = 0,
    resolution_sig: str | None = None,
    resolution_sources: list[str] | None = None,
    vrs_alleles: int = 0,
    vrs_alleles_identified: int = 0,
    frequency: Frequency | None = None,
    gene_metrics: GeneMetrics | None = None,
    gene_validity: GeneValidity | None = None,
    clinical_assertions: ClinicalAssertions | None = None,
    literature: Literature | None = None,
    sources: Sources | None = None,
    verification: Verification | None = None,
) -> ModuleManifest:
    """Assemble the manifest from the spec, validation stats, and hashed input/output/log files."""
    module = config.module
    vstats = validation.stats
    # Pass an authored version into Identity only when it is already canonical SemVer — a freeform
    # advisory value (`v2`/`3`) stays None here (the registry stamps the canonical version on publish,
    # and Identity.version is SemVer-validated). Out of `artifact.digest` either way.
    authored_version = (
        module.version if module.version and is_valid_version(module.version) else None
    )
    return ModuleManifest(
        identity=Identity(name=module.name, version=authored_version),
        display=Display(
            title=module.title,
            description=module.description,
            report_title=module.report_title,
            icon=module.icon,
            icon_set=module.icon_set,
            color=module.color,
        ),
        genome_build=config.genome_build,
        curator=config.defaults.curator,
        method=config.defaults.method,
        stats=Stats(
            variant_count=vstats.get("variant_count", 0),
            weights_rows=weights_rows,
            study_count=vstats.get("study_count", 0),
            gene_count=vstats.get("gene_count", 0),
            genes=vstats.get("genes", []),
            categories=vstats.get("categories", []),
            clinvar_count=vstats.get("clinvar_count", 0),
            pathogenic_count=vstats.get("pathogenic_count", 0),
            benign_count=vstats.get("benign_count", 0),
        ),
        compilation=Compilation(
            compile_success=True,
            compiled_by=compiled_by,
            compiler_version=_compiler_version(),
            ensembl_reference=ensembl_reference,
            compiled_at=_now_iso(),
            warnings=warnings,
            resolution_mode=resolution_mode,
            fully_resolved=fully_resolved,
            resolution_subjects=resolution_subjects,
            resolution_signature=resolution_sig,
            resolution_sources=resolution_sources or [],
            vrs_alleles=vrs_alleles,
            vrs_alleles_identified=vrs_alleles_identified,
        ),
        frequency=frequency,
        gene_metrics=gene_metrics,
        gene_validity=gene_validity,
        clinical_assertions=clinical_assertions,
        literature=literature,
        sources=sources,
        verification=verification,
        # Author-declared and registry-overridable, the same advisory pattern as module.version.
        license=config.license,
        inputs=file_entries(spec_dir, list(_INPUT_FILES)),
        # `file_entries` skips what is absent, so a module carrying no sidecars gets an empty list
        # rather than a fabricated one — and a new optional sidecar cannot move an existing module's
        # manifest by appearing here.
        # Every accepted spelling *and* location is offered; `file_entries` skips the ones that are
        # not there, so the block records whichever the module actually carries (RM51/RM49) — and
        # `FileEntry.name` then carries `derived/…` for a split tree, which is what a registry
        # re-splitting a download needs. A module cannot carry two: `_locate_sidecar` refused before
        # anything was written.
        derived=file_entries(
            spec_dir, [name for csv in _DERIVED_FILES for name in sidecar_relative_names(csv)]
        ),
        content_signature=content_sig,
        artifact=build_artifact(output_dir, list(_OUTPUT_FILES)),
        logs=logs,
        provenance=provenance,
        panel=config.panel,
        authorship=config.authorship,
        logo=logo,
        readme=readme,
    )


# ── Parquet builders ───────────────────────────────────────────────────────────


def _build_weights(variants: list[VariantRow], config: ModuleSpecConfig) -> pl.DataFrame:
    """Build the weights.parquet DataFrame from validated variant rows."""
    defaults = config.defaults
    module_name = config.module.name
    records: list[dict[str, Any]] = []
    for v in variants:
        priority = v.priority if v.priority is not None else defaults.priority
        records.append(
            {
                "rsid": v.rsid,
                # Frozen machine identity (base.derive_variant_key), stamped at load and reassigned
                # only on resolver expansion. Carried so reverse_module can tell an authored rsid from
                # a resolved one and restore the authored shape without re-keying (Principle 7).
                "variant_key": v.variant_key,
                # Which identity columns the AUTHOR wrote. Reverse re-emits exactly these, so an
                # rsid-only row comes back rsid-only instead of carrying whatever coordinate
                # resolution filled in, and an expanded one-to-many rsid collapses back to the single
                # row it was written as. Without it `content_signature` moved on every round-trip of
                # an rsid-authored module. See COMPILER.md § Resolution.
                "authored_ident": v.authored_ident,
                "genotype": _split_genotype(v.genotype),
                # Phase bit: `genotype` is stored as an allele *list*, which cannot itself
                # distinguish a phased A|G from an unphased (sorted) A/G — both split to ["A","G"].
                # This flag preserves the distinction so the round-trip is lossless (ROADMAP 0.3 5b).
                "phased": "|" in v.genotype,
                "module": module_name,
                "weight": v.weight,
                "state": v.state,
                "priority": priority,
                "conclusion": v.conclusion,
                "negatives": v.negatives,
                "curator": v.curator or defaults.curator,
                "method": v.method or defaults.method,
                "chrom": v.chrom,
                "start": v.start,
                "end": v.start,
                "ref": v.ref,
                "alts": v.alts.split(",") if v.alts else None,
                # Tri-state: keep None distinct from False (nullable pl.Boolean). Collapsing
                # None→False lost the difference between "curator stated not-pathogenic" (False) and
                # "unstated" (None) — an authored False did not survive the round-trip, and
                # `effective_pathogenic` flipped False→None on reload (Principle 7). Matches the
                # tri-state 0.4 axes (`requires_callable`/`acmg_sf`).
                "clinvar": v.clinvar,
                "pathogenic": v.pathogenic,
                "benign": v.benign,
                "likely_pathogenic": False,
                "likely_benign": False,
                # ── 0.3 additive columns (materialized passthrough; derivations are NOT computed
                # here — see docs/COMPILER.md). ──
                "direction": v.direction,
                "stat_significance": v.stat_significance,
                "effect_size": v.effect_size,
                "effect_measure": v.effect_measure,
                "effect_allele": v.effect_allele,
                "flags": v.flags,
                "trait_efo_id": v.trait_efo_id,
                "clin_sig": v.clin_sig,
                # ── 0.4 general annotation axes (materialized passthrough). ──
                "requires_callable": v.requires_callable,
                # 0.5 (RM6): where a consumer proves callability — the pointer half of the flag above.
                "callable_from": v.callable_from,
                "acmg_sf": v.acmg_sf,
                "actionability": v.actionability,
                # 0.5.1 (RM29a): the call-confidence cofactor — where the floor is measured, and the
                # floor. Both-or-neither is a model rule, so the pair is always whole here.
                "quality_from": v.quality_from,
                "min_quality": v.min_quality,
            }
        )
    schema = {
        "rsid": pl.Utf8,
        "authored_ident": pl.List(pl.Utf8),
        "variant_key": pl.Utf8,
        "genotype": pl.List(pl.Utf8),
        "phased": pl.Boolean,
        "module": pl.Utf8,
        "weight": pl.Float64,
        "state": pl.Utf8,
        "priority": pl.Utf8,
        "conclusion": pl.Utf8,
        "negatives": pl.Utf8,
        "curator": pl.Utf8,
        "method": pl.Utf8,
        "chrom": pl.Utf8,
        "start": pl.UInt32,
        "end": pl.UInt32,
        "ref": pl.Utf8,
        "alts": pl.List(pl.Utf8),
        "clinvar": pl.Boolean,
        "pathogenic": pl.Boolean,
        "benign": pl.Boolean,
        "likely_pathogenic": pl.Boolean,
        "likely_benign": pl.Boolean,
        "direction": pl.Utf8,
        "stat_significance": pl.Utf8,
        "effect_size": pl.Float64,
        "effect_measure": pl.Utf8,
        "effect_allele": pl.Utf8,
        "flags": pl.List(pl.Utf8),
        "trait_efo_id": pl.Utf8,
        "clin_sig": pl.Utf8,
        "requires_callable": pl.Boolean,
        "callable_from": pl.Utf8,
        "acmg_sf": pl.Boolean,
        "actionability": pl.Utf8,
        "quality_from": pl.Utf8,
        "min_quality": pl.Float64,
    }
    return pl.DataFrame(records, schema=schema)


def _build_frequencies(rows: list[FrequencyRow], module_name: str) -> pl.DataFrame:
    """`frequencies.csv` → `frequencies.parquet`, materializing the derived `allele_frequency`.

    The one place this differs from the generic `_build_table`: the CSV stores AC and AN as integers
    (exact through a text round-trip) and *no* frequency, while the parquet carries a real `Float64`
    `allele_frequency` so a consumer never does the division itself. Deriving on write rather than
    storing on both sides keeps one fact in one place in the human-authorable artifact, and gives the
    machine artifact the column it wants — the same "parquet absorbs the precision, the DSL keeps the
    human shape" split the format applies everywhere else.
    """
    schema: dict[str, Any] = {"module": pl.Utf8}
    for name, f in FrequencyRow.model_fields.items():
        schema[name] = _polars_type(f.annotation)
    schema["allele_frequency"] = pl.Float64
    records = [
        {"module": module_name, **row.model_dump(), "allele_frequency": row.allele_frequency}
        for row in rows
    ]
    return pl.DataFrame(records, schema=schema)


# Relative tolerance for the float redundancy checks. These are published numbers rendered through a
# CSV, so exact equality is the wrong test; anything looser than this would stop catching real slips.
_REDUNDANCY_TOLERANCE: float = 1e-6


def _close(left: float, right: float, tolerance: float = _REDUNDANCY_TOLERANCE) -> bool:
    """Relative comparison that behaves at zero (where a relative test alone is meaningless)."""
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def _check_frequency_arithmetic(rows: list[FrequencyRow]) -> tuple[list[str], list[str]]:
    """Validate-by-redundancy over the frequency table's own numbers. Returns (errors, warnings).

    These columns are not independent — they constrain each other — so a violation is detectable with
    no reference at all, which is exactly the class of check a no-network tier can own. The compiler
    cannot know whether an allele count is *right*; it can know when a set of counts is *impossible*.

    Integer impossibilities are **errors** (exact arithmetic, so there is no tolerance argument to
    have, and a violation is corruption). Float relations are **warnings**: they hold on real data
    (verified against the recorded gnomAD payload), but they compare numbers a source computed on
    possibly-different denominators, and failing a good module over a rounding difference would be
    worse than the miss.
    """
    errors: list[str] = []
    warnings_out: list[str] = []
    for row in rows:
        where = f"frequencies.csv [{row.variant_key} / {row.population}]"
        ac, an, hom = row.allele_count, row.allele_number, row.homozygote_count
        if ac is not None and an is not None and ac > an:
            errors.append(
                f"{where}: allele_count {ac} exceeds allele_number {an} — a count cannot be larger "
                f"than its own denominator"
            )
        if ac is not None and hom is not None and 2 * hom > ac:
            errors.append(
                f"{where}: homozygote_count {hom} implies at least {2 * hom} alleles, but "
                f"allele_count is {ac} — each homozygote contributes two"
            )
        frequency = row.allele_frequency
        if row.faf95 is not None and frequency is not None and row.faf95 > frequency:  # noqa: SIM102
            # Separate layer on purpose: the outer asks whether it is above, this asks whether it is
            # above by more than float tolerance.
            if not _close(row.faf95, frequency):
                warnings_out.append(
                    f"{where}: faf95 {row.faf95} exceeds the group's own allele frequency "
                    f"{frequency:.6g} — a 95% CI *lower bound* should sit at or below the point "
                    f"estimate, so these two numbers may not describe the same denominator"
                )
    return errors, warnings_out


def _check_gene_metrics_arithmetic(rows: list[GeneMetricsRow]) -> list[str]:
    """Validate-by-redundancy over the constraint table. Returns warnings.

    Two relations hold by definition and are therefore checkable without a reference: the observed/
    expected ratio must sit inside its own confidence interval, and it must equal `obs / exp` (on the
    recorded gnomAD payload it agrees to six decimal places for both BRCA1 and MYH7). Warnings rather
    than errors throughout: every value here is a float that has been through a CSV, and a constraint
    score is advisory to begin with.
    """
    warnings_out: list[str] = []
    for row in rows:
        where = f"gene_metrics.csv [{row.gene}]"
        lower, point, upper = row.oe_lof_lower, row.oe_lof, row.loeuf
        if None not in (lower, point, upper) and not lower <= point <= upper:
            warnings_out.append(
                f"{where}: oe_lof {point} lies outside its own interval [{lower}, {upper}] — the "
                f"point estimate and the bounds may have come from different releases or columns"
            )
        if row.obs_lof is not None and row.exp_lof and point is not None:
            derived = row.obs_lof / row.exp_lof
            if not _close(derived, point, 1e-4):
                warnings_out.append(
                    f"{where}: obs_lof/exp_lof is {derived:.6g} but oe_lof is {point} — these are the "
                    f"same quantity, so a disagreement means one of the three columns is mismapped"
                )
    return warnings_out


def _cross_check_frequencies(
    rows: list[FrequencyRow], variants: list[VariantRow]
) -> list[str]:
    """Warn when a frequency row describes a coordinate no variant in the module sits at.

    Matched at *position* level (`chrom:start:ref`, no alt) rather than on `variant_key` equality: the
    sidecar is keyed per-allele while a module row may be position-only or multi-allelic, so key
    equality would false-alarm on rows that are in fact about the same locus. The same reasoning the
    study/variant orphan check already uses.
    """
    if not variants:
        return []
    positions = {
        derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None
    }
    if not positions:
        return []
    orphans = sorted(
        {
            f"{r.chrom}:{r.start}:{r.ref}"
            for r in rows
            if r.chrom is not None
            and derive_variant_key(None, r.chrom, r.start, r.ref) not in positions
        }
    )
    if not orphans:
        return []
    return [
        f"frequencies.csv describes {len(orphans)} coordinate(s) no variant in this module sits at: "
        f"{orphans}"
    ]


def _cross_check_literature(
    rows: list[LiteratureRow],
    studies: list[StudyRow],
    bin_rows: dict[str, list[MeasureBinRow]] | None = None,
) -> list[str]:
    """Two orphan directions, one finding that is not an orphan at all, and one licensing notice.

    * a literature row for a PMID **nothing in the module cites** — the sidecar is stale or over-broad
      (warning, the same reasoning as the frequency/gene-metrics orphan checks: an extra row is
      harmless);
    * a **nonexistent citation** (`exists is False`) — not an orphan but a defect in the module, and
      the compiler can surface it offline because the enricher already recorded the verdict as a fact;
    * a **quote lifted from an article whose licence forbids commercial reuse** (RM46).

    **There are two citation sites since 0.6, and both count** (RM47). `studies.csv` was the only one
    until binning rows gained a `pmid`, and reading only the first would have made every
    threshold-grounding citation look like an orphan — shipping evidence the compiler then reported as
    stale, which is worse than the honest gap the column replaced.

    Matched on digit-only PMIDs, since both `StudyRow.pmid` and `MeasureBinRow.pmid` are free-form and
    may carry several ids or a `[PMID: N]` wrapper — `extract_pmids` is the same normalizer the
    enricher pass uses, so the sides cannot drift apart.

    **The non-commercial notice warns in both modes and gates nothing.** It is the third such
    exception, after the ClinVar `clin_sig` cross-check and `_check_declared_license_agrees`, and for
    the same reason: refusing would make the format arbitrate a copyright question. What it can
    honestly do is make the tension visible, because a `provenance_quote` is publisher text sitting in
    the module's own *annotation* layer — precisely where the licence gate bites — while the article's
    terms are recorded per article here and never as a `sources.csv` row. Grouped by licence rather
    than one line per citation, since a panel cites in the hundreds.
    """
    if not rows:
        return []
    findings: list[str] = []
    cited: set[str] = set()
    for study in studies:
        cited.update(extract_pmids(study.pmid))
    cited.update(binning_citations(bin_rows or {}))

    missing = sorted({r.pmid for r in rows if r.exists is False})
    if missing:
        findings.append(
            f"literature.csv records {len(missing)} citation(s) PubMed has no record of: "
            f"{missing} — either the id is a typo or the article was retracted from the index; "
            f"the annotation resting on it should be re-examined either way"
        )
    if cited:
        orphans = sorted({r.pmid for r in rows if r.pmid not in cited})
        if orphans:
            findings.append(
                f"literature.csv describes {len(orphans)} citation(s) no study in this module cites: "
                f"{orphans}"
            )
    findings.extend(_check_quoted_article_licenses(rows, studies))
    return findings


def _check_quoted_article_licenses(
    rows: list[LiteratureRow], studies: list[StudyRow]
) -> list[str]:
    """Quotes taken from articles whose licence forbids commercial reuse (RM46). Warning-only.

    Keyed on the *quote*, not on the citation: naming a PMID costs nothing under any licence, while a
    `provenance_quote` / `provenance_regex` copies the publisher's own words into `studies.csv`, which
    is authored content the module ships. `commercial_use is False` is a recorded fact the enricher
    read off the article's licence; `None` is unknown and withholds, as everywhere else.

    Aggregated by licence string, one line per licence, because a repeated per-row warning buries
    every other finding a compile produces (the lesson CPIC taught four times).
    """
    quoted = {
        pmid
        for study in studies
        if study.provenance_quote or study.provenance_regex
        for pmid in extract_pmids(study.pmid)
    }
    if not quoted:
        return []
    by_license: dict[str, list[str]] = {}
    for row in rows:
        if row.commercial_use is False and row.pmid in quoted:
            by_license.setdefault(row.license or "an unnamed non-commercial licence", []).append(
                row.pmid
            )
    return [
        f"{len(pmids)} study quote(s) come from article(s) licensed {license_name!r}, which forbids "
        f"commercial reuse: {sorted(pmids)}. Not adjudicated here — quoting for comment or research "
        f"is often fine and the format is not the tier that decides — but the passage is publisher "
        f"text in this module's annotation layer, so a commercial distribution has to answer for it"
        for license_name, pmids in sorted(by_license.items())
    ]


def _check_ba1_lint(
    rows: list[FrequencyRow],
    variants: list[VariantRow],
    *,
    threshold: float = BA1_ALLELE_FREQUENCY_THRESHOLD,
) -> list[str]:
    """Warn when a variant the module calls pathogenic is common in a general population.

    ACMG's **BA1** rule: an allele frequency above a threshold in a general population is *stand-alone*
    evidence that a variant is benign. Newly checkable only because `frequencies.csv` exists — before
    0.5 the compiler held no frequency to compare a `clin_sig` against.

    **Warning only, in both modes, and the threshold is overridable.** The 5% default is ACMG's, not a
    constant of nature: the right cutoff is disease-specific, and a common recessive carrier allele
    (sickle-cell's `rs334` sits around 4-5% in African-ancestry groups) legitimately lives near or above
    it. Failing a compile over that would be the format arbitrating a clinical judgement, which the
    data-agnostic charter forbids. What it *can* honestly do is make the tension visible.

    Which number: `faf95` when the sidecar carries one — that is the filtering allele frequency an ACMG
    filter actually uses, a 95% CI lower bound on the group with the highest frequency, and it is
    deliberately conservative. Otherwise the maximum per-group `allele_frequency`, which is the same
    quantity without the confidence discount. Matched at position level, like `_cross_check_frequencies`.
    """
    if not rows or not variants:
        return []
    pathogenic_at: dict[str, list[VariantRow]] = {}
    for variant in variants:
        if variant.chrom is None or not variant.effective_pathogenic:
            continue
        key = derive_variant_key(None, variant.chrom, variant.start, variant.ref)
        pathogenic_at.setdefault(key, []).append(variant)
    if not pathogenic_at:
        return []

    # Per allele, the strongest frequency evidence and where it came from.
    strongest: dict[tuple[str, str], tuple[float, str, str]] = {}
    for row in rows:
        if row.chrom is None or row.status == "not_found":
            continue
        key = derive_variant_key(None, row.chrom, row.start, row.ref)
        if key not in pathogenic_at:
            continue
        if row.faf95 is not None:
            candidate = (row.faf95, "faf95", row.population)
        elif row.allele_frequency is not None:
            candidate = (row.allele_frequency, "allele frequency", row.population)
        else:
            continue
        slot = (key, row.alt or "")
        # faf95 wins over a raw AF regardless of magnitude (it is the rule's own statistic); among
        # like measures the larger one is the one BA1 would be evaluated on.
        held = strongest.get(slot)
        if held is None or (candidate[1] == "faf95" and held[1] != "faf95") or (
            candidate[1] == held[1] and candidate[0] > held[0]
        ):
            strongest[slot] = candidate

    findings: list[str] = []
    for (key, alt), (value, measure, population) in sorted(strongest.items()):
        if value <= threshold:
            continue
        for variant in pathogenic_at[key]:
            findings.append(
                f"{variant.variant_key} genotype {variant.genotype}: clin_sig "
                f"{variant.effective_clin_sig!r} but the {measure} of ALT {alt!r} in "
                f"{population!r} is {value:.4g}, above the ACMG BA1 threshold of {threshold:.4g} — "
                f"BA1 treats that as stand-alone evidence of benign impact. The threshold is "
                f"disease-specific (a common recessive carrier allele sits above it legitimately), so "
                f"this is a prompt to check, not a verdict."
            )
    return findings


def _cross_check_gene_metrics(
    rows: list[GeneMetricsRow], variants: list[VariantRow]
) -> list[str]:
    """Warn when a gene-metrics row names a gene the module never mentions."""
    if not variants:
        return []
    genes = {v.gene for v in variants if v.gene}
    if not genes:
        return []
    orphans = sorted({r.gene for r in rows if r.gene not in genes})
    if not orphans:
        return []
    return [
        f"gene_metrics.csv names {len(orphans)} gene(s) this module never mentions: {orphans}"
    ]


def _cross_check_gene_validity(
    rows: list[GeneValidityRow], variants: list[VariantRow]
) -> list[str]:
    """Warn when a gene-validity row names a gene the module never mentions (RM24).

    The gene-metrics orphan check with one table swapped, deliberately: the two sidecars answer
    different questions about the same key, so an over-broad table fails the same way and a reader
    should see the same sentence. Warning-only for the same reason — an extra row is harmless, and the
    compiler cannot tell a stale row from a curator's deliberate context.
    """
    if not variants:
        return []
    genes = {v.gene for v in variants if v.gene}
    if not genes:
        return []
    orphans = sorted({r.gene for r in rows if r.gene not in genes})
    if not orphans:
        return []
    return [
        f"gene_validity.csv names {len(orphans)} gene(s) this module never mentions: {orphans}"
    ]


def _cross_check_clinical_assertions(
    rows: list[ClinicalAssertionRow], variants: list[VariantRow]
) -> list[str]:
    """Warn when a clinical-assertion row describes a coordinate no variant in the module sits at.

    Matched at *position* level (`chrom:start:ref`, no alt), exactly as `_cross_check_frequencies`
    does and for its reason: the sidecar is per-allele while a module row may be position-only or
    multi-allelic, so comparing `variant_key` for equality would false-alarm on rows that are about
    the same locus.

    **It does not compare the calls.** Whether the module's own `clin_sig` agrees with the archive's
    is `enricher.clinical.verify_clin_sig`'s question, it needs a reference the compiler is barred
    from holding, and it warns in both modes on purpose because failing would make the format
    arbitrate a clinical dispute. Recording the archive's side in a table does not move that line, and
    a coherence check here must not quietly become the escalation that was parked.
    """
    if not variants:
        return []
    positions = {
        derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None
    }
    if not positions:
        return []
    orphans = sorted(
        {
            f"{r.chrom}:{r.start}:{r.ref}"
            for r in rows
            if r.chrom is not None
            and derive_variant_key(None, r.chrom, r.start, r.ref) not in positions
        }
    )
    if not orphans:
        return []
    return [
        f"clinical_assertions.csv describes {len(orphans)} coordinate(s) no variant in this module "
        f"sits at: {orphans}"
    ]


def _build_annotations(variants: list[VariantRow], module_name: str) -> pl.DataFrame:
    """Build annotations.parquet, deduplicated by the genuine **variant-effect pair**
    `(variant_key, conclusion, negatives)` (first occurrence wins).

    Keying on `variant_key` alone collapsed a genuine *poly-effect* variant — the same locus
    carrying two distinct annotations (different `conclusion`/`category`, as embryo-level / neural
    findings routinely do when `category` does not subsume the effect) — onto its first row, so the
    second row's `gene`/`phenotype`/`category` were silently overwritten on reverse (a Principle 7
    round-trip loss introduced with the `variant_key` column). The effect (`conclusion` + `negatives`)
    is part of the identity, so a row per (variant, effect) is kept.

    Carries `variant_key`/`conclusion`/`negatives` so the table is **self-joinable** back to
    `weights.parquet` on reverse (each weights row rebuilds the same triple), and an explicit
    `variant_key` (rsid, else `chrom:start:ref`) so a **position-only** variant's annotation survives
    (rsid is null for such a row)."""
    seen_keys: set[tuple[str, str | None, str | None]] = set()
    records: list[dict[str, str | None]] = []
    for v in variants:
        key = (v.variant_key, v.conclusion, v.negatives)
        if key not in seen_keys:
            records.append(
                {
                    "rsid": v.rsid,
                    "variant_key": v.variant_key,
                    "conclusion": v.conclusion,
                    "negatives": v.negatives,
                    "module": module_name,
                    "gene": v.gene or "",
                    "phenotype": v.phenotype or "",
                    "category": v.category or "",
                }
            )
            seen_keys.add(key)
    schema = {
        "rsid": pl.Utf8,
        "variant_key": pl.Utf8,
        "conclusion": pl.Utf8,
        "negatives": pl.Utf8,
        "module": pl.Utf8,
        "gene": pl.Utf8,
        "phenotype": pl.Utf8,
        "category": pl.Utf8,
    }
    return pl.DataFrame(records, schema=schema)


def _build_studies(studies: list[StudyRow], module_name: str) -> pl.DataFrame:
    """Build the studies.parquet DataFrame from validated study rows."""
    records: list[dict[str, Any]] = []
    for s in studies:
        records.append(
            {
                "rsid": s.rsid,
                # Position columns (RM2): a StudyRow may be position-only (rsid null, chrom+start
                # set) — its variant_key is chrom:start:ref. Carrying them keeps such a row lossless
                # through compile → reverse → recompile (Principle 7); dropping them made the reversed
                # row identifier-less, so recompile failed validation.
                "chrom": s.chrom,
                "start": s.start,
                "ref": s.ref,
                "module": module_name,
                "pmid": s.pmid,
                "population": s.population,
                "p_value": s.p_value,
                "conclusion": s.conclusion,
                "study_design": s.study_design,
                # ── 0.3 additive columns (materialized passthrough). ──
                "stat_significance": s.stat_significance,
                "effect_size": s.effect_size,
                "effect_measure": s.effect_measure,
                "trait_efo_id": s.trait_efo_id,
                # ── 0.4 provenance columns (RM11/RM12, from the 0.5 scope; docs/USE_CASES.md §4a). ──
                "doi": s.doi,
                "provenance_quote": s.provenance_quote,
                "provenance_regex": s.provenance_regex,
                # ── 0.5: the queryable p-value. The authored number passes through; `neg_log10_p` is
                # DERIVED on write and absent from `StudyRow`'s fields, so `_write_studies_csv` cannot
                # emit it and the next compile re-derives the identical column (the `allele_frequency`
                # pattern — see `_build_frequencies`).
                "p_value_num": s.p_value_num,
                "neg_log10_p": s.neg_log10_p,
            }
        )
    schema = {
        "rsid": pl.Utf8,
        "chrom": pl.Utf8,
        "start": pl.UInt32,
        "ref": pl.Utf8,
        "module": pl.Utf8,
        "pmid": pl.Utf8,
        "population": pl.Utf8,
        "p_value": pl.Utf8,
        "conclusion": pl.Utf8,
        "study_design": pl.Utf8,
        "stat_significance": pl.Utf8,
        "effect_size": pl.Float64,
        "effect_measure": pl.Utf8,
        "trait_efo_id": pl.Utf8,
        "doi": pl.Utf8,
        "provenance_quote": pl.Utf8,
        "provenance_regex": pl.Utf8,
        "p_value_num": pl.Float64,
        "neg_log10_p": pl.Float64,
    }
    return pl.DataFrame(records, schema=schema)


# ── Reverse engineering ────────────────────────────────────────────────────────


def _module_name_from_parquets(parquet_dir: Path) -> str | None:
    """Recover the module name from the `module` column of the first present parquet — so a module
    with no `weights.parquet` (a PGx/PharmGKB/PRS-only module) still reverses (RM2)."""
    for name in ("weights.parquet", "annotations.parquet", "studies.parquet", *(
        parquet for _, parquet, _ in _TABLE_KINDS
    )):
        path = parquet_dir / name
        if path.is_file():
            df = pl.read_parquet(path)
            if "module" in df.columns:
                values = df["module"].drop_nulls().unique().to_list()
                if values:
                    # polars `unique()` order is unstable; `min` is the deterministic pick (a
                    # well-formed module has one value here, so this only matters defensively).
                    return min(values)
    return None


def _genome_build_from_artifact(parquet_dir: Path) -> str | None:
    """Recover the module's declared `genome_build` from the artifact's own `manifest.json`.

    `genome_build` is authored `module_spec.yaml` metadata that reaches the artifact through the
    manifest and **no parquet column**, so this is the only place it survives a compile. Reverse has
    to consult it: unlike `title`, getting the build wrong is not cosmetic — a coordinate is not
    absolute, so re-emitting a GRCh37 module as GRCh38 makes the next compile mint a GRCh38 VRS allele
    id for a GRCh37 position, which is a *false content-addressed claim* rather than a lost label.

    Returns `None` for a bare parquet directory with no manifest, or a manifest this compiler cannot
    parse — the same "recover it from the artifact, else fall back" shape as
    `_module_name_from_parquets`. A provenance failure must not stop a reverse, so the read is
    tolerant; what it must not do is *invent* a build, which is why the caller's fallback is explicit.
    """
    path = parquet_dir / "manifest.json"
    if not path.is_file():
        return None
    try:
        return read_manifest(path).genome_build
    except (OSError, ValueError):
        return None


def _artifact_records_verification(parquet_dir: Path) -> bool:
    """Did this artifact's manifest carry a verification block — i.e. is reverse about to drop one?

    Tolerant in the same way and for the same reason as the build recovery above: an unreadable
    manifest is a provenance failure, and a provenance failure must not stop a reverse. A `False`
    here only ever costs the warning.
    """
    path = parquet_dir / "manifest.json"
    if not path.is_file():
        return False
    try:
        return read_manifest(path).verification is not None
    except (OSError, ValueError):
        return False


def reverse_module(
    parquet_dir: Path,
    output_dir: Path,
    module_name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    report_title: str | None = None,
    icon: str = "database",
    color: str = "#6435c9",
    version: str | None = None,
    write_resolution: bool = True,
    genome_build: str | None = None,
) -> Path:
    """Reverse-engineer a parquet module back into the spec DSL (yaml + csv). Returns output_dir.

    `version` (like `title`/`description`) is authored `module:` metadata, out of `artifact.digest`
    and so not materialized into any parquet — a caller that wants it in the re-emitted spec supplies
    it (e.g. from the manifest's `identity.version`); when omitted it is left out of the block.

    `genome_build` is **not** in that class, even though it reaches the artifact the same way (the
    manifest, never a parquet column). A wrong title is cosmetic; a wrong build relocates every
    coordinate in the module. This used to be hardcoded `"GRCh38"`, so
    `compile → reverse → compile` on a `genome_build: GRCh37` module re-emitted it as GRCh38 and the
    recompile minted `ga4gh:VA.…` ids — GRCh38 allele identities for GRCh37 positions — moving
    `artifact.digest` and asserting a variant at a base the module never named. Resolution order is
    therefore: this argument, else the artifact's own `manifest.json`, else `"GRCh38"` for a bare
    parquet directory that records nothing.

    `write_resolution` (default True) also emits `resolution.csv` — the resolved facts recovered from
    the artifact — so `reverse → compile` reproduces the identical `artifact.digest` with **no network
    and no Ensembl reference** (Principle 7 hardened from reference-dependent to self-contained). A
    coord-keyed row's resolved rsid, dropped from `variants.csv`, is carried here and restored on
    recompile via `resolution.resolve_from_table`.

    The authored tables are written under their one legal name at the root. The machine-written
    sidecars go through `layout.sidecar_write_path`, so a fresh tree gets the **preferred** spelling
    (`licensing.csv`, not the deprecated `sources.csv` `_FACT_TABLES` still names for its parquet) and
    an output directory that already carries a copy has that copy overwritten rather than joined by a
    second one. Reversing into a directory that already holds two copies of one sidecar raises
    `layout.SidecarCollision`: which of two hand-editable claims to overwrite is not something this
    function may decide silently."""
    parquet_dir = Path(parquet_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # SNP core is optional (RM2): a module may have no weights.parquet.
    weights_path = parquet_dir / "weights.parquet"
    weights_df = pl.read_parquet(weights_path) if weights_path.is_file() else None

    # Every sidecar destination is resolved BEFORE the first write, and only for the tables this
    # artifact will actually produce. `sidecar_write_path` raises on an output directory that already
    # holds two copies of one table, and resolving late would raise it *after* `module_spec.yaml` and
    # the authored CSVs had been rewritten — a refusal that leaves a half-rebuilt spec behind. The
    # collision is refused with nothing touched instead, which is what the rest of this layout does.
    sidecar_paths: dict[str, Path] = {
        csv_name: sidecar_write_path(output_dir, csv_name)
        for csv_name, parquet_name, _ in _FACT_TABLES
        if (parquet_dir / parquet_name).is_file()
    }
    # Not `and weights_df is not None`: since RM43 the lookup table is rebuilt from the positional
    # parquets too, so a table-only module emits one and needs its path resolved the same way. The
    # writer itself returns before creating a file when there is nothing to write, so resolving the
    # path unconditionally cannot leave an empty `resolution.csv` behind.
    if write_resolution:
        sidecar_paths["resolution.csv"] = sidecar_write_path(output_dir, "resolution.csv")

    if module_name is None:
        module_name = _module_name_from_parquets(parquet_dir) or parquet_dir.name
    if genome_build is None:
        genome_build = _genome_build_from_artifact(parquet_dir) or "GRCh38"

    # **The attestation cannot be carried, and the silence about that was the defect (RM45).**
    # `verification.json` records checks the *enricher* put against sources this tier cannot reach,
    # and it is bound to the authored bytes by a hash — so reverse has nothing to rebuild it from and
    # must not invent one. What it can do is say so: without this line a module round-trips into a
    # spec that recompiles to a manifest with no `verification` block at all, and
    # `manifest.compilation.warnings` — a surface consumers parse (RM44) — differs between a module
    # and its own round trip with nothing edited. Losing a record of what was checked is acceptable;
    # losing it invisibly is the S16 silent-success shape.
    if _artifact_records_verification(parquet_dir):
        logger.warning(
            "The source artifact carries a verification attestation (RM45) and the reversed spec "
            "will not: the checks were put by the enricher, against sources this tier does not "
            "reach, and the record is bound to authored bytes reverse is re-emitting. Re-run the "
            "enricher on %s to re-attest; recompiling as-is produces a manifest with no "
            "`verification` block.",
            output_dir,
        )

    default_curator = "unknown"
    default_method = "unknown"
    # `priority` is intentionally NOT defaulted. It is Optional with no `Defaults.priority` fallback
    # ('ai-module-creator'/'literature-review' back curator/method, but priority defaults to None),
    # so a null priority is *authored-absent*. Inferring a default from the mode would fabricate a
    # value for rows that never set one — turning weights `['high', None]` into `['high', 'high']`
    # on recompile (a Principle 7 idempotency break). It is written verbatim, per row, instead.
    default_priority: str | None = None
    if weights_df is not None:
        default_curator = _most_common(weights_df, "curator") or "unknown"
        default_method = _most_common(weights_df, "method") or "unknown"

    defaults_dict: dict[str, Any] = {"curator": default_curator, "method": default_method}

    module_block: dict[str, Any] = {
        "name": module_name,
        "title": title or module_name.replace("_", " ").title(),
        "description": description or f"Annotation module: {module_name}",
        "report_title": report_title or module_name.replace("_", " ").title(),
        "icon": icon,
        "color": color,
    }
    if version is not None:
        module_block["version"] = version
    spec = {
        "schema_version": "1.0",
        "module": module_block,
        "defaults": defaults_dict,
        "genome_build": genome_build,
    }
    (output_dir / "module_spec.yaml").write_text(
        yaml.dump(spec, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )

    # variants.csv + studies.csv only when the module has them.
    if weights_df is not None:
        ann_lookup: dict[tuple, dict[str, str]] = {}
        ann_keyed_by_effect = False
        ann_path = parquet_dir / "annotations.parquet"
        if ann_path.exists():
            ann_df = pl.read_parquet(ann_path)
            # An artifact whose annotations carry `conclusion` is keyed on the variant-effect pair;
            # an older one (pre-effect-key) is keyed on variant_key alone. Detect once and key both
            # the lookup and the weights-side probe the same way.
            ann_keyed_by_effect = "conclusion" in ann_df.columns
            for row in ann_df.iter_rows(named=True):
                # variant_key so position-only variants (rsid null) match; fall back to rsid for an
                # older artifact compiled before the variant_key column existed.
                base = row.get("variant_key") or row.get("rsid")
                if base is None:
                    continue
                key = (
                    (base, row.get("conclusion"), row.get("negatives"))
                    if ann_keyed_by_effect
                    else (base,)
                )
                ann_lookup[key] = {
                    "gene": row.get("gene", ""),
                    "phenotype": row.get("phenotype", ""),
                    "category": row.get("category", ""),
                }
        _write_variants_csv(
            weights_df, ann_lookup, ann_keyed_by_effect, default_curator, default_method,
            default_priority, output_dir / "variants.csv", genome_build=genome_build,
        )
    studies_path = parquet_dir / "studies.parquet"
    if studies_path.exists():
        _write_studies_csv(pl.read_parquet(studies_path), output_dir / "studies.csv")

    # 0.4 table kinds (RM1): each present parquet → its authored CSV.
    positional_frames: list[tuple[str, pl.DataFrame]] = []
    for csv_name, parquet_name, model in _TABLE_KINDS:
        kind_path = parquet_dir / parquet_name
        if kind_path.is_file():
            kind_df = pl.read_parquet(kind_path)
            _write_table_csv(kind_df, model, output_dir / csv_name)
            if csv_name in {name for name, _model in _POSITIONAL_TABLE_KINDS}:
                positional_frames.append((csv_name, kind_df))

    # `resolution.csv` last, because it is rebuilt from everything above. It is written from the SNP
    # core **and** the positional tables since 0.6 (RM43): once the compiler fills a resolved
    # coordinate into `pharm_variants`/`haplotypes`/`heteroplasmy`, a reverse that dropped the lookup
    # table would emit a spec whose recompile leaves those parquets unfilled — so `compile → reverse →
    # compile` would stop reproducing the artifact, which is Principle 7.
    # Through `sidecar_paths`, never `output_dir / "resolution.csv"` — the literal join RM51 abolishes.
    # Worth spelling out because the two halves of this arrived in different lanes and nearly cancelled:
    # RM43 *moved* this call out of the `weights_df is not None` block so a table-only module emits one,
    # while RM51's repair was applied to the call site at its old address. Taking either side of that
    # merge alone loses the other.
    if write_resolution:
        _write_resolution_csv(
            weights_df, positional_frames, sidecar_paths["resolution.csv"],
            genome_build=genome_build,
        )

    # 0.5 derived-fact sidecars: same round-trip, minus the columns that are recomputed rather than
    # stored. `_write_table_csv` drops any parquet column the model does not declare, so
    # `allele_frequency` (derived on write, absent from `FrequencyRow`'s fields) falls away by
    # construction rather than by a special case — re-deriving it on the next compile reproduces the
    # identical parquet.
    #
    # The filename comes from `sidecar_paths` (resolved above), not `output_dir / csv_name`: `_FACT_TABLES`
    # names the licence table by its *deprecated* spelling (the parquet and the manifest key keep it,
    # since only a major may rename those), so joining that name on by hand emitted `sources.csv` and
    # made `compile → reverse → compile` deprecation-warn on a module whose own compile is silent —
    # and `manifest.compilation.warnings` is a published field (RM44), so the module and its own round
    # trip disagreed on it. This is the same "write to the file you read" rule every other writer
    # follows rather than an exception to it: reverse builds a spec tree from an artifact, so on a
    # fresh directory there is nothing to follow and the rule yields the preferred spelling, while
    # reversing over a tree that already carries the old name (or a `derived/` split) overwrites that
    # copy instead of leaving a second one behind — which is the collision the rule exists to prevent.
    for csv_name, parquet_name, model in _FACT_TABLES:
        fact_path = parquet_dir / parquet_name
        if fact_path.is_file():
            _write_table_csv(pl.read_parquet(fact_path), model, sidecar_paths[csv_name])

    return output_dir


def _write_resolution_csv(
    weights_df: pl.DataFrame | None,
    positional: list[tuple[str, pl.DataFrame]],
    output_path: Path,
    genome_build: str = "GRCh38",
) -> None:
    """Emit `resolution.csv` from the compiled artifact — the resolved facts, so `reverse → compile`
    is fully offline (no Ensembl reference, no network).

    Each *positioned* weights row yields one `ResolutionRow` keyed by its frozen `variant_key`,
    carrying the resolved rsid (which `variants.csv` drops on a coord-keyed row). On recompile,
    `resolution.resolve_from_table` restores that rsid and reproduces the identical `artifact.digest`.
    Rows without a resolved position (a best-effort partial) carry no fact and are skipped. Emitted in
    the weights' authored order; `resolution_signature` is order-independent regardless. `fetched_at`
    is left blank (no wall-clock is read here, keeping the emit deterministic).

    **The positional tables are a second source, and that is forced rather than chosen (RM43).** Since
    0.6 the compiler fills a resolved coordinate into `pharm_variants`/`haplotypes`/`heteroplasmy`, so
    a reverse that rebuilt this table from `weights.parquet` alone would hand back a spec whose
    recompile leaves those parquets unfilled — `compile → reverse → compile` would stop reproducing
    the artifact, breaking Principle 7. A PGx module carries no `weights.parquet` at all, and it is
    exactly the module this matters most for.

    Two ordering rules hold the two sources together, both borrowed from `enrich._collect_subjects`
    rather than invented here:

    * **weights first, and a key it emitted is never re-emitted.** `variants.csv` is the only table
      carrying `alts` as an authored fact, so letting a PGx row win would change what the table says
      about an allele — the same hazard that ordering exists to avoid one tier up.
    * **one row per key from the positional side.** These tables are never expanded, so a key names
      exactly one locus there; emitting a second row under one key would read back as a one-to-many
      rsID and send the next compile into the expansion path.

    **Reverse emits facts and discards provenance, deliberately and completely.** `source` becomes
    `reversed`, `status` becomes `resolved`, `fetched_at` empties — and the provenance-only columns
    (`rsid_alternates`, `rsid_current`, `rsid_status`, `vrs_id`, `caid`) are simply not written. This
    was once filed as a bug about `rsid_alternates` specifically; it is not one, and it is not fixable
    here. Those columns are **outside** the fact set precisely so they stay out of `weights.parquet`,
    so the information does not exist in the artifact this function reads — emitting the column names
    would produce a header with permanently empty cells and change nothing. Recovering an ambiguous
    candidate list after a round-trip means re-running the enricher, which is the correct place for it:
    the candidate list is a statement about a reference at a moment, not a property of the module.

    `authority` (RM33) joins that list for the same reason and one of its own: `source` is `reversed`
    here, and a reversed table's facts came out of parquet rather than from any licensed source, so
    there is no authority to name. The column is absent, loads as `None`, and contributes nothing to the
    compiler's `sources.csv` coherence check — which is the accurate statement.

    `genome_build` is the module's, and it reaches **both** the column and `derive_variant_key`. Getting
    only the column right is not enough and was the first shape of this fix: the key is minted from
    `(chrom, start, ref, alts)`, so on a GRCh37 module the default build produced a `ga4gh:VA.…` — a
    GRCh38 allele identity — on a row whose own `genome_build` cell said `GRCh37`. The row contradicted
    itself, and since `resolve_from_table` joins on `variant_key`, it also silently matched nothing on
    recompile."""
    fieldnames = [
        "variant_key", "rsid", "chrom", "start", "ref", "alts",
        "genome_build", "locus_index", "source", "status", "fetched_at",
    ]
    # A one-to-many rsid contributes N rows under ONE authored key, so `locus_index` counts within
    # that key — matching what the enricher writes and what `resolve_from_table` expects to read back.
    # Keying these on the per-locus `variant_key` instead (as this writer used to) left the re-emitted
    # table unjoinable to the collapsed authored row, and `resolution_signature` moved across the
    # round-trip.
    seen_rows: set[tuple] = set()
    locus_counter: dict[str, int] = {}
    emitted: list[dict[str, object]] = []

    for row in (weights_df.iter_rows(named=True) if weights_df is not None else ()):
        chrom, start = row.get("chrom"), row.get("start")
        if chrom is None or start is None:
            continue
        alts_list = row.get("alts")
        alts_cell = ",".join(alts_list) if alts_list else None
        resolution_key = _resolution_key(row, chrom, start, alts_cell, genome_build)
        # One authored row may appear several times in weights (one per genotype); the resolved
        # fact is the same each time, so emit it once.
        fact = (resolution_key, row.get("rsid"), chrom, start, row.get("ref"), alts_cell)
        if fact in seen_rows:
            continue
        seen_rows.add(fact)
        index = locus_counter.get(resolution_key, 0)
        locus_counter[resolution_key] = index + 1
        emitted.append(
            _resolution_record(row, resolution_key, chrom, start, alts_cell, index, genome_build)
        )

    for _csv_name, table_df in positional:
        for row in table_df.iter_rows(named=True):
            chrom, start = row.get("chrom"), row.get("start")
            if chrom is None or start is None:
                continue
            alts_cell = row.get("alts") or None
            # The **stored** key here, unlike the weights pass above, and the difference is not a
            # shortcut. These tables are never expanded, so the stamped column already *is* the
            # authored-subset key — and it is the only place the model's own alts policy lives:
            # `PharmVariantRow`/`HaplotypeRow` key without `alts` while `HeteroplasmyRow` keys with
            # it, which no recomputation here can know. Recomputing filed a coordinate-authored pharm
            # fact under a `ga4gh:VA.…` the fill then never looked up, so the recompile left the row
            # unfilled and `resolution_signature` moved. The fallback covers a pre-0.6 parquet.
            resolution_key = row.get("variant_key") or _resolution_key(
                row, chrom, start, alts_cell, genome_build
            )
            if resolution_key in locus_counter:
                continue
            locus_counter[resolution_key] = 1
            emitted.append(
                _resolution_record(row, resolution_key, chrom, start, alts_cell, 0, genome_build)
            )

    # A module that resolved nothing anywhere gets no file — writing a header-only `resolution.csv`
    # into a reversed spec that never had one would invent a derived sidecar (and a `manifest.derived`
    # entry) out of an absence. A module with a `weights.parquet` keeps the pre-0.6 behaviour of
    # always writing, so nothing that already round-trips changes shape.
    if weights_df is None and not emitted:
        return
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in emitted:
            writer.writerow(record)


def _resolution_key(
    row: dict[str, Any],
    chrom: str,
    start: int,
    alts_cell: str | None,
    genome_build: str,
) -> str:
    """The key a reversed `resolution.csv` row is filed under: the identity the AUTHOR wrote.

    Recomputed from `authored_ident` rather than read off the parquet's own `variant_key`, because on
    the weights side those two differ exactly where it matters: a one-to-many rsID expansion re-keys
    each emitted row onto its own locus, so the stored key names a locus while the injected table
    named the rsID. Reading the stored column there would file N rows under N keys and leave the
    collapsed authored row joining to none of them.

    Falls back to the stored key, then to a fresh derivation, for an artifact compiled before
    `authored_ident` existed.
    """
    if (authored := row.get("authored_ident")) is not None:
        authored_set = set(authored)
        return derive_variant_key(
            row.get("rsid") if "rsid" in authored_set else None,
            chrom if "chrom" in authored_set else None,
            start if "start" in authored_set else None,
            row.get("ref") if "ref" in authored_set else None,
            alts_cell if "alts" in authored_set else None,
            build=genome_build,
        )
    return row.get("variant_key") or derive_variant_key(
        row.get("rsid"), chrom, start, row.get("ref"), alts_cell, build=genome_build
    )


def _resolution_record(
    row: dict[str, Any],
    resolution_key: str,
    chrom: str,
    start: int,
    alts_cell: str | None,
    locus_index: int,
    genome_build: str,
) -> dict[str, object]:
    """One re-emitted `resolution.csv` row. Shared by the weights and positional passes so the two
    sources cannot render the same fact two ways."""
    return {
        "variant_key": resolution_key,
        "rsid": _scalar_cell(row.get("rsid")),
        "chrom": _scalar_cell(chrom),
        "start": _scalar_cell(start),
        "ref": _scalar_cell(row.get("ref")),
        "alts": alts_cell or "",
        # The module's own declared build, not a constant. A GRCh37 module's facts were being
        # written out labelled GRCh38 — a coordinate relabelled onto an assembly where it names a
        # different base. `resolve_from_table` filters rows on this column, so the wrong label also
        # made a reversed table unjoinable.
        "genome_build": genome_build,
        "locus_index": locus_index,
        "source": "reversed",
        "status": "resolved",
        "fetched_at": "",
    }


def _most_common(df: pl.DataFrame, col: str) -> str | None:
    """Return the most common non-null value in a column, or None.

    On a tie, polars `mode()` gives no ordering guarantee (its result order is unstable even
    call-to-call), so the smallest value is picked deterministically — otherwise `reverse_module`'s
    inferred curator/method default (hence which rows emit a blank vs an explicit value) would vary
    run-to-run for the same artifact."""
    if col not in df.columns:
        return None
    non_null = df[col].drop_nulls()
    if non_null.len() == 0:
        return None
    return min(non_null.mode().to_list())


def _write_variants_csv(
    weights_df: pl.DataFrame,
    ann_lookup: dict[tuple, dict[str, str]],
    ann_keyed_by_effect: bool,
    default_curator: str,
    default_method: str,
    default_priority: str | None,
    output_path: Path,
    genome_build: str = "GRCh38",
) -> None:
    """Write variants.csv from weights parquet + annotations lookup.

    `genome_build` reaches `derive_variant_key` below for the same reason it does in
    `_write_resolution_csv`: the key is minted from the coordinate, so the default would mint a GRCh38
    `ga4gh:VA.…` for a row on another assembly. Here it decides only which artifact rows collapse into
    one authored row, so a wrong build mis-groups rather than mislabels — still wrong, and wrong in a
    way that shows up as a lost or duplicated row rather than as a bad cell."""
    fieldnames = [
        "rsid", "chrom", "start", "ref", "alts", "genotype", "weight", "state", "conclusion",
        "negatives", "priority", "gene", "phenotype", "category", "clinvar", "pathogenic", "benign",
        "curator", "method",
        # 0.3 additive columns
        "direction", "stat_significance", "effect_size", "effect_measure", "effect_allele",
        "flags", "trait_efo_id", "clin_sig",
        # 0.4 general annotation axes
        "requires_callable", "acmg_sf", "actionability",
        # 0.5 general annotation axis
        "callable_from",
        # 0.5.1 general annotation axes (RM29a)
        "quality_from", "min_quality",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        emitted_authored_keys: set[str] = set()
        for row in weights_df.iter_rows(named=True):
            raw_rsid = row.get("rsid")
            variant_key = row.get("variant_key")
            # `authored_ident` records which identity columns the author actually wrote, so reverse
            # re-emits that exact shape rather than whatever resolution filled in. This is what keeps
            # `content_signature` stable across a round-trip, and it is only safe because the key is
            # canonical: a VRS allele id identifies the row without the coordinate having to be
            # written into `variants.csv`, so dropping the resolved coordinate loses nothing.
            authored = row.get("authored_ident")
            if variant_key is None:
                # Pre-0.4 artifact with no frozen-key column: recompute it so the annotation lookup
                # below still joins. Independent of `authored_ident` — an artifact can carry one
                # without the other, and losing the join silently blanked every annotation column.
                variant_key = derive_variant_key(
                    raw_rsid, row.get("chrom"), row.get("start"), row.get("ref")
                )
            if authored is not None:
                authored_set = set(authored)
                # An expanded one-to-many rsid is N artifact rows sharing ONE authored row. Emit it
                # once — writing N rows would fabricate per-locus annotations the author never made,
                # and the genotype can only be true of one of them.
                authored_key = derive_variant_key(
                    raw_rsid if "rsid" in authored_set else None,
                    row.get("chrom") if "chrom" in authored_set else None,
                    row.get("start") if "start" in authored_set else None,
                    row.get("ref") if "ref" in authored_set else None,
                    ",".join(row.get("alts") or []) if "alts" in authored_set else None,
                    build=genome_build,
                )
                dedupe_key = (authored_key, row.get("conclusion"), row.get("negatives"),
                              tuple(row.get("genotype") or ()))
                if dedupe_key in emitted_authored_keys:
                    continue
                emitted_authored_keys.add(dedupe_key)
            elif row.get("variant_key") is None:
                # No shape recorded and no frozen key: the prior (non-restoring) behaviour is the only
                # safe read — emit whatever the artifact holds.
                authored_set = {"rsid", "chrom", "start", "ref", "alts"} if raw_rsid else {
                    "chrom", "start", "ref", "alts"
                }
            else:
                # 0.5 artifact predating `authored_ident`: the frozen key is the only signal, so keep
                # the previous rule (rsid-keyed → rsid authored; anything else → position-only).
                authored_set = (
                    {"rsid"} if (raw_rsid is not None and variant_key == raw_rsid)
                    else {"chrom", "start", "ref", "alts"}
                )
            emit_rsid = raw_rsid or "" if "rsid" in authored_set else ""
            # Probe the annotation on the same key the table was built with: the variant-effect pair
            # (variant_key, conclusion, negatives) when the artifact carries it, else variant_key.
            ann_key = (
                (variant_key, row.get("conclusion"), row.get("negatives"))
                if ann_keyed_by_effect
                else (variant_key,)
            )
            ann = ann_lookup.get(ann_key, {})
            genotype_list = row.get("genotype", [])
            curator = row.get("curator", "")
            method = row.get("method", "")
            priority = row.get("priority")
            # Reconstruct the genotype string. The `phased` bit (materialized alongside the allele
            # list) tells us which separator to re-emit: a phased pair keeps its order and joins with
            # '|'; an unphased pair is re-emitted alphabetically sorted with '/'; a single allele
            # (hemizygous / homoplasmic) passes through. Lossless round-trip (ROADMAP 0.3 item 5b).
            if genotype_list and len(genotype_list) == 2:
                if row.get("phased"):
                    genotype_str = "|".join(genotype_list)
                else:
                    genotype_str = "/".join(sorted(genotype_list))
            else:
                genotype_str = "/".join(genotype_list) if genotype_list else ""
            alts_list = row.get("alts")
            writer.writerow(
                {
                    # Each identity column is emitted only if the author wrote it. A resolved
                    # coordinate belongs in `resolution.csv`, not in `variants.csv` — putting it back
                    # here is what used to move `content_signature` on every rsid-authored module.
                    "rsid": emit_rsid,
                    "chrom": _scalar_cell(row.get("chrom")) if "chrom" in authored_set else "",
                    "start": _scalar_cell(row.get("start")) if "start" in authored_set else "",
                    "ref": _scalar_cell(row.get("ref")) if "ref" in authored_set else "",
                    "alts": (
                        ",".join(alts_list) if alts_list and "alts" in authored_set else ""
                    ),
                    "genotype": genotype_str,
                    "weight": _scalar_cell(row.get("weight")),
                    "state": _scalar_cell(row.get("state")),
                    "conclusion": _scalar_cell(row.get("conclusion")),
                    "negatives": _scalar_cell(row.get("negatives")),
                    # priority/curator/method: blank when equal to the inferred default (so a
                    # recompile re-applies the default), else the explicit value.
                    "priority": priority if priority != default_priority else "",
                    "gene": ann.get("gene", ""),
                    "phenotype": ann.get("phenotype", ""),
                    "category": ann.get("category", ""),
                    # Tri-state (True/False/None → true/false/empty), so an authored False survives.
                    "clinvar": _scalar_cell(row.get("clinvar")),
                    "pathogenic": _scalar_cell(row.get("pathogenic")),
                    "benign": _scalar_cell(row.get("benign")),
                    "curator": curator if curator != default_curator else "",
                    "method": method if method != default_method else "",
                    "direction": _scalar_cell(row.get("direction")),
                    "stat_significance": _scalar_cell(row.get("stat_significance")),
                    "effect_size": _scalar_cell(row.get("effect_size")),
                    "effect_measure": _scalar_cell(row.get("effect_measure")),
                    "effect_allele": _scalar_cell(row.get("effect_allele")),
                    "flags": _list_cell(row.get("flags")),
                    "trait_efo_id": _scalar_cell(row.get("trait_efo_id")),
                    "clin_sig": _scalar_cell(row.get("clin_sig")),
                    # 0.4 axes: Optional bools are tri-state (True/False/None → true/false/empty).
                    "requires_callable": _scalar_cell(row.get("requires_callable")),
                    "acmg_sf": _scalar_cell(row.get("acmg_sf")),
                    "actionability": _scalar_cell(row.get("actionability")),
                    "callable_from": _scalar_cell(row.get("callable_from")),
                    "quality_from": _scalar_cell(row.get("quality_from")),
                    "min_quality": _scalar_cell(row.get("min_quality")),
                }
            )


def _write_studies_csv(studies_df: pl.DataFrame, output_path: Path) -> None:
    """Write studies.csv from studies parquet."""
    fieldnames = [
        "rsid", "chrom", "start", "ref", "pmid", "population", "p_value", "conclusion",
        "study_design",
        # 0.3 additive columns
        "stat_significance", "effect_size", "effect_measure", "trait_efo_id",
        # 0.4 provenance columns (RM11/RM12, from the 0.5 scope)
        "doi", "provenance_quote", "provenance_regex",
        # 0.5: the authored numeric p-value. `neg_log10_p` is deliberately absent — it is derived on
        # write, so re-emitting it would author a value the next compile recomputes anyway.
        "p_value_num",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in studies_df.iter_rows(named=True):
            pmid = row.get("pmid")
            if pmid is None or str(pmid).strip() == "":
                continue
            writer.writerow(
                {
                    "rsid": _scalar_cell(row.get("rsid")),
                    # Position columns so a position-only study row (rsid null) keeps an identifier.
                    "chrom": _scalar_cell(row.get("chrom")),
                    "start": _scalar_cell(row.get("start")),
                    "ref": _scalar_cell(row.get("ref")),
                    "pmid": str(pmid).strip(),
                    "population": _scalar_cell(row.get("population")),
                    "p_value": _scalar_cell(row.get("p_value")),
                    "conclusion": _scalar_cell(row.get("conclusion")),
                    "study_design": _scalar_cell(row.get("study_design")),
                    "stat_significance": _scalar_cell(row.get("stat_significance")),
                    "effect_size": _scalar_cell(row.get("effect_size")),
                    "effect_measure": _scalar_cell(row.get("effect_measure")),
                    "trait_efo_id": _scalar_cell(row.get("trait_efo_id")),
                    "doi": _scalar_cell(row.get("doi")),
                    "provenance_quote": _scalar_cell(row.get("provenance_quote")),
                    "provenance_regex": _scalar_cell(row.get("provenance_regex")),
                    "p_value_num": _scalar_cell(row.get("p_value_num")),
                }
            )
