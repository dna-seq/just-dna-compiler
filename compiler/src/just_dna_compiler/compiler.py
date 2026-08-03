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
import math
import re
import shutil
import types
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Union, get_args, get_origin

import polars as pl
import yaml
from just_dna_format.base import authored_field_names, derive_variant_key
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.identity import is_valid_version
from just_dna_format.integrity import (
    build_artifact,
    content_signature as _content_signature,
    file_entries,
    file_entry,
    frequency_signature as _frequency_signature,
    gene_metrics_signature as _gene_metrics_signature,
    literature_signature as _literature_signature,
    resolution_signature as _resolution_signature,
    sha256_file,
    source_signature as _source_signature,
)
from just_dna_format.literature import LiteratureRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow, taints_commercial_use, taints_redistribution
from just_dna_format.normalize import parse_p_value, strip_authority_keys
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    Compilation,
    Display,
    FileEntry,
    Frequency,
    GeneMetrics,
    Identity,
    Literature,
    ModuleManifest,
    Provenance,
    ProvenanceDoc,
    Sources,
    Stats,
    write_manifest,
)
from just_dna_format.binning import (
    ActivityPhenotypeRow,
    CopyNumberRow,
    HeteroplasmyRow,
    MeasureBinRow,
    RepeatAlleleRow,
    validate_bins,
)
from just_dna_format.pgs import PgsRow
from just_dna_format.pgx import (
    AlleleFunctionRow,
    DiplotypeRow,
    HaplotypeRow,
    PharmVariantRow,
)
from just_dna_format.spec import (
    RESERVED_FLAGS,
    ModuleSpecConfig,
    StudyRow,
    VariantRow,
    extract_pmids,
)
from just_dna_format.vocab import population_sort_key
from just_dna_format.vrs import UnsupportedBuildError, derive_vrs_allele_id, is_substitution
from pydantic import BaseModel, ValidationError

from just_dna_compiler.models import CompilationResult, ValidationResult

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
    HaplotypeRow: lambda r: (
        r.haplotype_name, derive_variant_key(r.rsid, r.chrom, r.start, r.ref), r.allele,
    ),
    AlleleFunctionRow: lambda r: (r.gene, r.allele),
    DiplotypeRow: lambda r: (r.gene, r.haplotype_a, r.haplotype_b, r.trait_efo_id, r.drug),
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
    "sources.parquet",
)

# The 0.5 derived-fact sidecars: (authored CSV, compiled parquet, row model). Deliberately NOT
# registered in `_TABLE_KINDS`: those are authored DSL tables with `AuthoredModel` semantics, the
# reserved-namespace guard, duplicate-key checks and raw-byte input hashing. A machine-produced
# reference-fact table is a third category — injected, fact-hashed, human-overridable — and folding it
# into the table kinds would blur exactly the line the 0.5 rework drew.
_FACT_TABLES: tuple[tuple[str, str, type[BaseModel]], ...] = (
    ("frequencies.csv", "frequencies.parquet", FrequencyRow),
    ("gene_metrics.csv", "gene_metrics.parquet", GeneMetricsRow),
    ("literature.csv", "literature.parquet", LiteratureRow),
    ("sources.csv", "sources.parquet", SourceRow),
)
# Optional structured-provenance document authored beside the spec (ROADMAP item 1). Hashed and
# shipped like logs, kept OUT of `artifact.digest` (it is not in `_OUTPUT_FILES`).
_PROVENANCE_FILE: str = "provenance.json"


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
    `reverse_module` can recover the module name from any present parquet."""
    schema: dict[str, Any] = {"module": pl.Utf8}
    for name, f in model.model_fields.items():
        schema[name] = _polars_type(f.annotation)
    records = [{"module": module_name, **row.model_dump()} for row in rows]
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


def _list_cell(value: Optional[list]) -> str:
    """Render a list column to a pipe-joined CSV cell (empty/None → "")."""
    return "|".join(value) if value else ""


def _write_table_csv(df: pl.DataFrame, model: type[BaseModel], path: Path) -> None:
    """Reverse of `_build_table`: parquet → the authored CSV. Drops the injected `module` column
    (not authored); renders each cell via `_scalar_cell`/`_list_cell` (None→"", list→pipe-joined,
    bool→"true"/"false", integer-valued float→bare int)."""
    # `authored_field_names`, not `model_fields`: identical today (no table-kind model carries a
    # compiler-managed field) but it closes the third place the authored surface is derived. The two
    # that preceded it both drifted, and a reverse writer that offered a stamped column would emit a
    # CSV the compiler then refused to reload — the exact `authored_ident` bug, one tier over.
    fieldnames = authored_field_names(model)
    list_fields = _list_fields(model)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in df.iter_rows(named=True):
            out = {
                name: (_list_cell(row.get(name)) if name in list_fields else _scalar_cell(row.get(name)))
                for name in fieldnames
            }
            writer.writerow(out)


def _compiler_version() -> str:
    try:
        return f"just-dna-compiler {version('just-dna-compiler')}"
    except PackageNotFoundError:
        return "just-dna-compiler unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _collect_logs(
    spec_dir: Path, output_dir: Path, explicit: Optional[list[Path]]
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
    spec_dir: Path, output_dir: Path, explicit: Optional[Path]
) -> Optional[Provenance]:
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
    spec_dir: Path, output_dir: Path, explicit: Optional[Path]
) -> Optional[FileEntry]:
    """Discover an optional module logo (`logo.png`/`.jpg`/`.jpeg`), ship it, and hash it.

    Uses an explicit path if given, else the first `logo.<ext>` (in `LOGO_EXTENSIONS` order) found
    beside the spec. The logo is copied into the module dir and returned as a hashed `FileEntry`
    kept OUT of `artifact.digest` (a logo swap is a PATCH, not a new content identity). Absent
    logo → `None`. Raises `ValueError` on an unsupported extension.
    """
    if explicit is not None:
        src: Optional[Path] = Path(explicit)
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


# ── File loading helpers ───────────────────────────────────────────────────────


def _load_yaml(
    path: Path, authority_keys: Optional[Iterable[str]] = None
) -> tuple[Optional[ModuleSpecConfig], list[str], list[str]]:
    """Load and validate module_spec.yaml. Returns (config, errors, dropped_authority_keys).

    When `authority_keys` is given, the format's reference stripper removes those consumer/registry-
    owned identity keys from the `module:` block *before* validation (inject-only — the caller supplies
    the set, e.g. `just_dna_format.normalize.IDENTITY_AUTHORITY_KEYS`). The validator itself stays
    strict: any key NOT in the injected set still trips `extra="forbid"`. `dropped` is the sorted list
    of keys actually removed, for the caller to surface as INFO."""
    if not path.exists():
        return None, [f"module_spec.yaml not found at {path}"], []
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return None, ["module_spec.yaml is empty"], []
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


def _load_csv_rows(
    path: Path, row_model: type, file_label: str
) -> tuple[list[Any], list[str], list[str]]:
    """Load a CSV and validate each row against a Pydantic model. Returns (rows, errors, warnings)."""
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
                rows.append(row_model.model_validate(cleaned))
            except ValidationError as exc:
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors.append(f"{file_label} line {line_num} [{loc}]: {err['msg']}")
    return rows, errors, []


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
        # Non-diploid guardrail (ROADMAP 0.3 item 5b): MT and Y are never diploid, so a two-allele
        # genotype is almost certainly a "fake diploid" error — a homoplasmic MT call or a hemizygous
        # Y call is a single allele (e.g. 'G'). X is deliberately excluded: it is diploid in XX
        # samples, so a two-allele X row is legitimate (the item-5b dogfood enumerates both a
        # single-allele hemizygous row and the diploid rows at an X-linked locus); warning on X would
        # be pure noise. PAR vs non-PAR needs coordinates the format does not resolve — so Y (never
        # diploid regardless of sex) is the safe, false-positive-free half of "non-PAR X/Y".
        if row.chrom in {"MT", "Y"} and ("/" in row.genotype or "|" in row.genotype):
            warnings.append(
                f"{row.variant_key} genotype {row.genotype}: chrom={row.chrom} is not diploid — use "
                f"a single-allele genotype (e.g. 'G') for a homoplasmic/hemizygous call"
            )
    return errors, warnings


def _allowed_alleles(
    variant: VariantRow, resolution_table: dict[str, list[ResolutionRow]]
) -> tuple[Optional[set[str]], str]:
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
        if provenance == "authored":
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
        missing = sorted(
            {a.upper() for a in _split_genotype(variant.genotype)} - allowed
        )
        if missing:
            findings.append(
                f"{variant.variant_key} genotype {variant.genotype}: allele(s) "
                f"{', '.join(missing)} are not among the {provenance} alleles at this locus "
                f"({shown}) — {because}"
            )
        if variant.effect_allele and variant.effect_allele.upper() not in allowed:
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


def _verify_vrs_ids(
    resolution_rows: list[ResolutionRow], *, strict: bool
) -> tuple[list[str], list[str]]:
    """Recompute every stored `vrs_id` and report disagreements. Returns (errors, warnings).

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
    - **unverifiable** — could not be recomputed at all (see `_recompute_vrs_id` for the four reasons).
      **Warning** in `best_effort`, **error** in `strict`.

    The third case is emphatically *not* "an indel mismatch". This tier cannot recompute an indel's id,
    so it can never detect that one disagrees — it can only report that it did not check. Calling that
    a mismatch would claim a verdict that was never reached; `strict` refuses such a row precisely
    because "unchecked" and "correct" are different things, and its contract is a reproducible artifact.

    A row with no `vrs_id` is skipped entirely — there is nothing to check, which is not the same as
    something that could not be checked.
    """
    errors: list[str] = []
    warnings_out: list[str] = []
    for row in resolution_rows:
        if row.vrs_id is None:
            continue
        recomputed, reason = _recompute_vrs_id(row)
        if recomputed is None:
            message = f"{row.variant_key}: vrs_id {row.vrs_id} could not be verified — {reason}"
            if strict:
                errors.append(
                    f"{message}. A strict compile will not carry an identity it cannot confirm; "
                    f"recompile without strict to keep it as a warning, or drop the vrs_id."
                )
            else:
                warnings_out.append(f"{message}; carried unverified.")
            continue
        if recomputed != row.vrs_id:
            errors.append(
                f"{row.variant_key}: stored vrs_id {row.vrs_id} does not match the id recomputed "
                f"from {row.chrom}:{row.start} {row.ref}>{row.alts} ({recomputed}) — a substitution's "
                f"id is deterministic here, so this is corruption, not a difference of opinion."
            )
    return errors, warnings_out


def _recompute_vrs_id(row: ResolutionRow) -> tuple[Optional[str], Optional[str]]:
    """`(recomputed_id, reason_it_could_not_be)` — exactly one of the two is non-`None`.

    The four reasons a row is unverifiable here, each a genuine limit of a no-network tier rather than
    a defect in the row:

    1. **no coordinate** — nothing to recompute from (an unresolved rsid row carrying an external id);
    2. **no single ALT** — position-only, or multi-allelic; a VRS allele id names exactly one allele,
       and picking one from a comma-joined cell would be inventing data;
    3. **not a single-base substitution** — an indel or MNV must be justified against the reference
       sequence, which this tier has no access to and will never fetch (Principle 2);
    4. **outside the primary assembly, or a build with no refget table** — no accession to address the
       sequence by. The build case is *raised* by `refget_accession` rather than returned, deliberately
       (a caller asking for GRCh37 should hear "not built" rather than get a GRCh38-flavoured answer),
       so it is caught here and turned into a reason. Letting it propagate would abort the whole
       compile over one unverifiable row, which is the wrong severity for `best_effort`.
    """
    if row.chrom is None or row.start is None:
        return None, "the row carries no coordinate to recompute from"
    alt = row.alts if row.alts and "," not in row.alts else None
    if alt is None:
        return None, (
            "the row names no single ALT (position-only, or multi-allelic), and a VRS allele id "
            "names exactly one allele"
        )
    if not is_substitution(row.ref, alt):
        return None, (
            f"{row.ref}>{alt} is not a single-base substitution, so justifying it needs the reference "
            f"sequence — minted upstream by the enricher, not recomputable here"
        )
    try:
        recomputed = derive_vrs_allele_id(
            row.chrom, row.start, row.ref, alt, build=row.genome_build
        )
    except UnsupportedBuildError as exc:
        return None, str(exc)
    if recomputed is None:
        return None, (
            f"{row.chrom}:{row.start} is outside the primary assembly (no refget accession for the "
            f"contig, or the position is past its end)"
        )
    return recomputed, None


def _cross_validate_studies(
    studies: list[StudyRow], variants: list[VariantRow]
) -> tuple[list[str], list[str]]:
    """Validate study rows against the variants. Returns (errors, warnings).

    A study matches a variant on **any shared identifier** — same rsid or same `chrom:start:ref` —
    not on frozen-key equality. Keying strictly on `variant_key` would false-orphan a study that
    references a variant by a different (but co-identifying) handle than the one the variant froze its
    key to (e.g. a coord-keyed variant referenced by rsid)."""
    warnings: list[str] = []
    variant_rsids = {v.rsid for v in variants if v.rsid is not None}
    variant_coords = {
        derive_variant_key(None, v.chrom, v.start, v.ref) for v in variants if v.chrom is not None
    }
    orphans: list[str] = []
    for row in studies:
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
    seen: set[tuple[str, str]] = set()
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


def validate_spec(
    spec_dir: Path, authority_keys: Optional[Iterable[str]] = None
) -> ValidationResult:
    """Validate a module spec directory without producing output.

    `authority_keys` (inject-only) is the set of consumer/registry-owned identity keys to strip from
    the authored `module:` block before validation — pass `just_dna_format.normalize.
    IDENTITY_AUTHORITY_KEYS` (or your own set) so a legacy spec carrying `namespace:`/`owner:`/
    `canonical_id:` validates; the format applies none by default. Stripped keys are surfaced on
    `.info`. Everything else still trips `extra="forbid"`.

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

    config, yaml_errors, dropped_authority = _load_yaml(
        spec_dir / "module_spec.yaml", authority_keys
    )
    all_errors.extend(yaml_errors)
    if dropped_authority:
        all_info.append(
            f"dropped injected authority keys from module: block (registry-stamped, not authored): "
            f"{dropped_authority}"
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

    # A module composes from optional table kinds (RM2): variants.csv is no longer mandatory — a PGx /
    # PharmGKB / PRS module carries only its own table(s). Load whatever is present.
    variants_path = spec_dir / "variants.csv"
    has_variants = variants_path.exists()
    variants: list[VariantRow] = []
    if has_variants:
        variants, var_errors, var_warnings = _load_csv_rows(
            variants_path, VariantRow, "variants.csv"
        )
        all_errors.extend(var_errors)
        all_warnings.extend(var_warnings)

    # Validate each present 0.4 table kind against its model.
    kind_row_counts: dict[str, int] = {}
    for csv_name, _parquet, model in _TABLE_KINDS:
        kind_path = spec_dir / csv_name
        if not kind_path.exists():
            continue
        rows, kind_errors, kind_warnings = _load_csv_rows(kind_path, model, csv_name)
        all_errors.extend(kind_errors)
        all_warnings.extend(kind_warnings)
        kind_row_counts[csv_name] = len(rows)
        if not rows:
            if not kind_errors:
                all_errors.append(f"{csv_name} is present but has no rows.")
        elif not kind_errors:
            # Table-level coherence (bin overlap/gap, single sentinel, duplicate keys) — only when
            # every row validated, so the checks run on a complete, trustworthy set.
            tbl_errors, tbl_warnings = _validate_table_kind(csv_name, model, rows)
            all_errors.extend(tbl_errors)
            all_warnings.extend(tbl_warnings)

    # Composition: a module must carry at least one recognized table kind.
    if not has_variants and not kind_row_counts:
        all_errors.append(
            "module has no recognized table: add variants.csv or a 0.4 table "
            "(e.g. pharm_variants.csv, diplotypes.csv, pgs.csv)."
        )

    # Grounding (studies) is mandatory for *variant* annotations, so it is required iff variants.csv
    # is present. The 0.4 tables carry their own evidence (e.g. evidence_level) and do not require it.
    studies_path = spec_dir / "studies.csv"
    studies: list[StudyRow] = []
    if studies_path.exists():
        studies, study_errors, study_warnings = _load_csv_rows(
            studies_path, StudyRow, "studies.csv"
        )
        all_errors.extend(study_errors)
        all_warnings.extend(study_warnings)
        if not studies and not study_errors:
            all_errors.append(
                "studies.csv is present but has no study rows. Grounding evidence is mandatory."
            )
    elif has_variants:
        all_errors.append(
            "studies.csv is missing. Grounding evidence is mandatory; add study rows with PMIDs."
        )

    if variants:
        cross_errors, cross_warnings = _cross_validate_variants(variants)
        all_errors.extend(cross_errors)
        all_warnings.extend(cross_warnings)
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
        variant_keys_set = {v.variant_key for v in variants}
        genes = sorted({v.gene for v in variants if v.gene})
        categories = sorted({v.category for v in variants if v.category})
        stats.update(
            {
                "variant_count": len(variant_keys_set),
                "unique_rsids": len({v.rsid for v in variants if v.rsid is not None}),
                "gene_count": len(genes),
                "genes": genes,
                "categories": categories,
                # ClinVar/quality flag counts over variant rows (ROADMAP item 5).
                "clinvar_count": sum(1 for v in variants if v.clinvar),
                "pathogenic_count": sum(1 for v in variants if v.pathogenic),
                "benign_count": sum(1 for v in variants if v.benign),
            }
        )

    return ValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings,
        info=all_info,
        stats=stats,
    )


def content_signature(spec_dir: Path) -> str:
    """Stable content identity over the raw authored data CSVs — name- and Ensembl-independent.

    Reads `variants.csv`, `studies.csv`, and any present 0.4 table CSVs, validates each row, and
    hashes the normalized + deterministically-sorted rows via
    `just_dna_format.integrity.content_signature`. The data is read **as authored** (no Ensembl
    resolution, no parquet build), so this is cheap and reference-independent — a client can compute
    it without recompiling and dedup against a registry, surviving both metadata-strip and a recompile
    against a different reference. Raises `ValueError` if a present data CSV fails validation.
    """
    spec_dir = Path(spec_dir)
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
        rows, errors, _ = _load_csv_rows(path, model, csv_name)
        if errors:
            raise ValueError(f"cannot compute content_signature: {csv_name} is invalid: {errors[0]}")
        tables[csv_name] = rows
    return _content_signature(tables)


def compile_module(
    spec_dir: Path,
    output_dir: Path,
    compression: str = "zstd",
    resolve_with_ensembl: bool = True,
    ensembl_cache: Optional[Path] = None,
    compiled_by: Optional[str] = None,
    ensembl_reference: Optional[str] = None,
    log_files: Optional[list[Path]] = None,
    provenance_file: Optional[Path] = None,
    logo_file: Optional[Path] = None,
    authority_keys: Optional[Iterable[str]] = None,
    strict: bool = False,
    ba1_threshold: float = BA1_ALLELE_FREQUENCY_THRESHOLD,
) -> CompilationResult:
    """Compile a module spec directory into parquet files plus a `manifest.json`.

    Args:
        spec_dir: Path to the module spec directory.
        output_dir: Directory for output parquet files + manifest.json.
        compression: Parquet compression codec.
        resolve_with_ensembl: Master switch for resolution. With a `resolution.csv` present it drives
            the preferred, source-independent table path; `ensembl_cache` is the deprecated fallback.
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

    validation = validate_spec(spec_dir, authority_keys)
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
        variants, _, _ = _load_csv_rows(spec_dir / "variants.csv", VariantRow, "variants.csv")
    studies: list[StudyRow] = []
    if (spec_dir / "studies.csv").exists():
        studies, _, _ = _load_csv_rows(spec_dir / "studies.csv", StudyRow, "studies.csv")

    all_warnings = list(validation.warnings)

    # The source-independent resolution table (0.5), if authored/produced beside the spec. When
    # present it is the *preferred* resolution path: the compiler consumes already-resolved facts and
    # owns no source convention (Ensembl/DuckDB/provisioning) — the strict inject-only end state
    # (Principle 2). An injected `ensembl_cache` (the DuckDB path) is the superseded fallback (P3).
    resolution_rows: list[ResolutionRow] = []
    resolution_table: dict[str, list[ResolutionRow]] = {}
    resolution_path = spec_dir / "resolution.csv"
    if resolution_path.exists():
        resolution_rows, res_errors, _ = _load_csv_rows(
            resolution_path, ResolutionRow, "resolution.csv"
        )
        if res_errors:
            return CompilationResult(success=False, errors=res_errors, warnings=all_warnings)
        for row in resolution_rows:
            resolution_table.setdefault(row.variant_key, []).append(row)
        # Content-addressed identities are checkable against themselves — do it before anything is
        # written, so a tampered id never reaches an artifact. Dep-free (stdlib), see `_verify_vrs_ids`.
        vrs_errors, vrs_warnings = _verify_vrs_ids(resolution_rows, strict=strict)
        all_warnings.extend(vrs_warnings)
        if vrs_errors:
            return CompilationResult(success=False, errors=vrs_errors, warnings=all_warnings)

    # Do the alleles the module *states* exist at the loci it points at? Runs here, on the AUTHORED
    # rows, because resolution may expand one rsid into several loci that share this genotype — after
    # that expansion the check reports the siblings it was never about. See `_check_allele_membership`.
    allele_errors, allele_warnings = _check_allele_membership(
        variants, resolution_table, strict=strict
    )
    all_warnings.extend(allele_warnings)
    if allele_errors:
        return CompilationResult(success=False, errors=allele_errors, warnings=all_warnings)

    p_value_errors, p_value_warnings = _check_p_value_num(studies, strict=strict)
    all_warnings.extend(p_value_warnings)
    if p_value_errors:
        return CompilationResult(success=False, errors=p_value_errors, warnings=all_warnings)

    resolution_mode: Optional[str] = None
    resolution_sources: list[str] = []
    resolution_sig: Optional[str] = None
    if resolve_with_ensembl and variants:
        resolution_mode = "strict" if strict else "best_effort"
        resolve_warnings: list[str] = []
        resolve_strict_errors: list[str] = []
        if resolution_table:
            from just_dna_compiler.resolution import resolve_from_table

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
            resolution_sources = sorted(
                {row.source for row in resolution_rows if row.source}
            )
            resolution_sig = _resolution_signature(resolution_rows)
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

    # Outcome axis (orthogonal to the requested `resolution_mode` policy, Principle 5): did every
    # in-scope variant resolve to a genomic position? Vacuously true for a table-kind-only module.
    fully_resolved = all(v.chrom is not None and v.start is not None for v in variants)

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
    sources_path = spec_dir / "sources.csv"
    if sources_path.exists():
        gate_rows, gate_load_errors, _ = _load_csv_rows(sources_path, SourceRow, "sources.csv")
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

    # 0.4 table kinds (RM1): materialize each present CSV via the generic materializer.
    table_rows: dict[str, int] = {}
    for csv_name, parquet_name, model in _TABLE_KINDS:
        kind_path = spec_dir / csv_name
        if not kind_path.exists():
            continue
        rows, _, _ = _load_csv_rows(kind_path, model, csv_name)
        table_df = _build_table(rows, model, module_name)
        table_df.write_parquet(output_dir / parquet_name, compression=compression)
        table_rows[parquet_name] = table_df.height

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
        return [], list(_cross_check_literature(rows, studies))

    def _sources_checks(rows: list) -> tuple[list[str], list[str]]:
        # `sources.csv` is last in `_FACT_TABLES`, so the other sidecars are already parsed into
        # `fact_rows` and their `source` values can be cross-checked here. Warnings only — the gate
        # that can actually refuse already ran, before anything was written.
        #
        # `SourceRow` is excluded from the "used" set: the loop stores each model's rows into
        # `fact_rows` *before* calling its check, so including it would let sources.csv vouch for
        # itself and no orphan could ever be reported.
        used = {r.source for r in resolution_rows if r.source}
        for model, parsed in fact_rows.items():
            if model is SourceRow:
                continue
            used |= {getattr(r, "source", None) for r in parsed if getattr(r, "source", None)}
        warns = _source_checks(rows, {s for s in used if s})
        warns.extend(_check_declared_license_agrees(rows, config.license if config else None))
        return [], warns

    _FACT_HANDLERS: dict[type, tuple[Callable, Callable]] = {
        FrequencyRow: (_frequency_checks, lambda rows: _build_frequencies(rows, module_name)),
        GeneMetricsRow: (_gene_metrics_checks, lambda rows: _build_table(rows, GeneMetricsRow, module_name)),
        LiteratureRow: (_literature_checks, lambda rows: _build_table(rows, LiteratureRow, module_name)),
        SourceRow: (_sources_checks, lambda rows: _build_table(rows, SourceRow, module_name)),
    }

    fact_rows: dict[type, list] = {}
    for csv_name, parquet_name, model in _FACT_TABLES:
        fact_path = spec_dir / csv_name
        if not fact_path.exists():
            continue
        rows, fact_errors, _ = _load_csv_rows(fact_path, model, csv_name)
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
        content_sig=content_signature(spec_dir),
        resolution_mode=resolution_mode,
        fully_resolved=fully_resolved,
        resolution_sig=resolution_sig,
        resolution_sources=resolution_sources,
        frequency=_frequency_block(frequency_rows),
        gene_metrics=_gene_metrics_block(gene_metrics_rows),
        literature=_literature_block(literature_rows),
        sources=_sources_block(source_rows),
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


def _frequency_block(rows: list[FrequencyRow]) -> Optional[Frequency]:
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


def _gene_metrics_block(rows: list[GeneMetricsRow]) -> Optional[GeneMetrics]:
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
    """
    warnings: list[str] = []
    declared = {r.source for r in rows}
    orphans = sorted(declared - used_sources)
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
    rows: list[SourceRow], declared_license: Optional[str]
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


def _sources_block(rows: list[SourceRow]) -> Optional[Sources]:
    """The manifest's `sources` summary, or `None` when the module carries no licensing sidecar.

    The per-layer facets stay lists (see `Sources`); only `commercial_use` collapses, because it is
    the one question with a single module-wide answer. Its ladder is most-restrictive-first: a
    forbidding source makes it `False`; failing that, an unknown makes it `None` (undetermined, never
    permitted); only an all-known, none-forbidding set makes it `True`.
    """
    if not rows:
        return None
    def _verdict(taints, is_unknown) -> Optional[bool]:
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


def _literature_block(rows: list[LiteratureRow]) -> Optional[Literature]:
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
    compiled_by: Optional[str],
    ensembl_reference: Optional[str],
    logs: list[FileEntry],
    provenance: Optional[Provenance],
    logo: Optional[FileEntry],
    content_sig: Optional[str] = None,
    resolution_mode: Optional[str] = None,
    fully_resolved: bool = False,
    resolution_sig: Optional[str] = None,
    resolution_sources: Optional[list[str]] = None,
    frequency: Optional[Frequency] = None,
    gene_metrics: Optional[GeneMetrics] = None,
    literature: Optional[Literature] = None,
    sources: Optional[Sources] = None,
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
            resolution_signature=resolution_sig,
            resolution_sources=resolution_sources or [],
        ),
        frequency=frequency,
        gene_metrics=gene_metrics,
        literature=literature,
        sources=sources,
        # Author-declared and registry-overridable, the same advisory pattern as module.version.
        license=config.license,
        inputs=file_entries(spec_dir, list(_INPUT_FILES)),
        content_signature=content_sig,
        artifact=build_artifact(output_dir, list(_OUTPUT_FILES)),
        logs=logs,
        provenance=provenance,
        panel=config.panel,
        authorship=config.authorship,
        logo=logo,
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
        if row.faf95 is not None and frequency is not None and row.faf95 > frequency:
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
    rows: list[LiteratureRow], studies: list[StudyRow]
) -> list[str]:
    """Two orphan directions, and one finding that is not an orphan at all.

    * a literature row for a PMID no study cites — the sidecar is stale or over-broad (warning, the
      same reasoning as the frequency/gene-metrics orphan checks: an extra row is harmless);
    * a **nonexistent citation** (`exists is False`) — not an orphan but a defect in the module, and
      the compiler can surface it offline because the enricher already recorded the verdict as a fact.

    Matched on digit-only PMIDs, since `StudyRow.pmid` is free-form and may carry several ids or a
    `[PMID: N]` wrapper — `extract_pmids` is the same normalizer the enricher pass uses, so the two
    sides cannot drift apart.
    """
    if not rows:
        return []
    findings: list[str] = []
    cited: set[str] = set()
    for study in studies:
        cited.update(extract_pmids(study.pmid))

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
    return findings


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
    seen_keys: set[tuple[str, Optional[str], Optional[str]]] = set()
    records: list[dict[str, Optional[str]]] = []
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


def _module_name_from_parquets(parquet_dir: Path) -> Optional[str]:
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
                    # polars `unique()` order is unstable; sort for a deterministic pick (a
                    # well-formed module has one value here, so this only matters defensively).
                    return sorted(values)[0]
    return None


def reverse_module(
    parquet_dir: Path,
    output_dir: Path,
    module_name: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    report_title: Optional[str] = None,
    icon: str = "database",
    color: str = "#6435c9",
    version: Optional[str] = None,
    write_resolution: bool = True,
) -> Path:
    """Reverse-engineer a parquet module back into the spec DSL (yaml + csv). Returns output_dir.

    `version` (like `title`/`description`) is authored `module:` metadata, out of `artifact.digest`
    and so not materialized into any parquet — a caller that wants it in the re-emitted spec supplies
    it (e.g. from the manifest's `identity.version`); when omitted it is left out of the block.

    `write_resolution` (default True) also emits `resolution.csv` — the resolved facts recovered from
    the artifact — so `reverse → compile` reproduces the identical `artifact.digest` with **no network
    and no Ensembl reference** (Principle 7 hardened from reference-dependent to self-contained). A
    coord-keyed row's resolved rsid, dropped from `variants.csv`, is carried here and restored on
    recompile via `resolution.resolve_from_table`."""
    parquet_dir = Path(parquet_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # SNP core is optional (RM2): a module may have no weights.parquet.
    weights_path = parquet_dir / "weights.parquet"
    weights_df = pl.read_parquet(weights_path) if weights_path.is_file() else None

    if module_name is None:
        module_name = _module_name_from_parquets(parquet_dir) or parquet_dir.name

    default_curator = "unknown"
    default_method = "unknown"
    # `priority` is intentionally NOT defaulted. It is Optional with no `Defaults.priority` fallback
    # ('ai-module-creator'/'literature-review' back curator/method, but priority defaults to None),
    # so a null priority is *authored-absent*. Inferring a default from the mode would fabricate a
    # value for rows that never set one — turning weights `['high', None]` into `['high', 'high']`
    # on recompile (a Principle 7 idempotency break). It is written verbatim, per row, instead.
    default_priority: Optional[str] = None
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
        "genome_build": "GRCh38",
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
            default_priority, output_dir / "variants.csv",
        )
        if write_resolution:
            _write_resolution_csv(weights_df, output_dir / "resolution.csv")
    studies_path = parquet_dir / "studies.parquet"
    if studies_path.exists():
        _write_studies_csv(pl.read_parquet(studies_path), output_dir / "studies.csv")

    # 0.4 table kinds (RM1): each present parquet → its authored CSV.
    for csv_name, parquet_name, model in _TABLE_KINDS:
        kind_path = parquet_dir / parquet_name
        if kind_path.is_file():
            _write_table_csv(pl.read_parquet(kind_path), model, output_dir / csv_name)

    # 0.5 derived-fact sidecars: same round-trip, minus the columns that are recomputed rather than
    # stored. `_write_table_csv` drops any parquet column the model does not declare, so
    # `allele_frequency` (derived on write, absent from `FrequencyRow`'s fields) falls away by
    # construction rather than by a special case — re-deriving it on the next compile reproduces the
    # identical parquet.
    for csv_name, parquet_name, model in _FACT_TABLES:
        fact_path = parquet_dir / parquet_name
        if fact_path.is_file():
            _write_table_csv(pl.read_parquet(fact_path), model, output_dir / csv_name)

    return output_dir


def _write_resolution_csv(weights_df: pl.DataFrame, output_path: Path) -> None:
    """Emit `resolution.csv` from the compiled weights — the resolved facts, so `reverse → compile`
    is fully offline (no Ensembl reference, no network).

    Each *positioned* weights row yields one `ResolutionRow` keyed by its frozen `variant_key`,
    carrying the resolved rsid (which `variants.csv` drops on a coord-keyed row). On recompile,
    `resolution.resolve_from_table` restores that rsid and reproduces the identical `artifact.digest`.
    Rows without a resolved position (a best-effort partial) carry no fact and are skipped. Emitted in
    the weights' authored order; `resolution_signature` is order-independent regardless. `fetched_at`
    is left blank (no wall-clock is read here, keeping the emit deterministic).

    **Reverse emits facts and discards provenance, deliberately and completely.** `source` becomes
    `reversed`, `status` becomes `resolved`, `fetched_at` empties — and the provenance-only columns
    (`rsid_alternates`, `rsid_current`, `rsid_status`, `vrs_id`, `caid`) are simply not written. This
    was once filed as a bug about `rsid_alternates` specifically; it is not one, and it is not fixable
    here. Those columns are **outside** the fact set precisely so they stay out of `weights.parquet`,
    so the information does not exist in the artifact this function reads — emitting the column names
    would produce a header with permanently empty cells and change nothing. Recovering an ambiguous
    candidate list after a round-trip means re-running the enricher, which is the correct place for it:
    the candidate list is a statement about a reference at a moment, not a property of the module."""
    fieldnames = [
        "variant_key", "rsid", "chrom", "start", "ref", "alts",
        "genome_build", "locus_index", "source", "status", "fetched_at",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # A one-to-many rsid contributes N rows under ONE authored key, so `locus_index` counts
        # within that key — matching what the enricher writes and what `resolve_from_table` expects to
        # read back. Keying these on the per-locus `variant_key` instead (as this writer used to) left
        # the re-emitted table unjoinable to the collapsed authored row, and `resolution_signature`
        # moved across the round-trip.
        seen_rows: set[tuple] = set()
        locus_counter: dict[str, int] = {}
        for row in weights_df.iter_rows(named=True):
            chrom, start = row.get("chrom"), row.get("start")
            if chrom is None or start is None:
                continue
            alts_list = row.get("alts")
            alts_cell = ",".join(alts_list) if alts_list else None
            authored = row.get("authored_ident")
            if authored is not None:
                authored_set = set(authored)
                resolution_key = derive_variant_key(
                    row.get("rsid") if "rsid" in authored_set else None,
                    chrom if "chrom" in authored_set else None,
                    start if "start" in authored_set else None,
                    row.get("ref") if "ref" in authored_set else None,
                    alts_cell if "alts" in authored_set else None,
                )
            else:
                resolution_key = row.get("variant_key") or derive_variant_key(
                    row.get("rsid"), chrom, start, row.get("ref"), alts_cell,
                )
            # One authored row may appear several times in weights (one per genotype); the resolved
            # fact is the same each time, so emit it once.
            fact = (resolution_key, row.get("rsid"), chrom, start, row.get("ref"), alts_cell)
            if fact in seen_rows:
                continue
            seen_rows.add(fact)
            index = locus_counter.get(resolution_key, 0)
            locus_counter[resolution_key] = index + 1
            writer.writerow(
                {
                    "variant_key": resolution_key,
                    "rsid": _scalar_cell(row.get("rsid")),
                    "chrom": _scalar_cell(chrom),
                    "start": _scalar_cell(start),
                    "ref": _scalar_cell(row.get("ref")),
                    "alts": alts_cell or "",
                    "genome_build": "GRCh38",
                    "locus_index": index,
                    "source": "reversed",
                    "status": "resolved",
                    "fetched_at": "",
                }
            )


def _most_common(df: pl.DataFrame, col: str) -> Optional[str]:
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
    default_priority: Optional[str],
    output_path: Path,
) -> None:
    """Write variants.csv from weights parquet + annotations lookup."""
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
