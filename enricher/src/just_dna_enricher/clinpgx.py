"""`enrich-clinpgx` — cross-check drug-response annotations against the ClinPGx snapshot (0.5).

Pass 6, and the offline-capable half of the pharmacogenomics work. `pgx.py` asks the two nomenclature
authorities about star alleles over the network; this one asks ClinPGx about *clinical annotations* —
which variant, which drug, at what evidence level — from a local snapshot, exactly as the ClinVar
cross-check does.

**The licence comes out of the snapshot, not out of a table.** `clinpgx_build` extracts the
`LICENSE.txt` ClinPGx bundles inside `clinicalAnnotations.zip` and records its sha256 in
`release.json`; this pass stamps that hash onto the `SourceRow` it emits. The recorded terms are
therefore provably the ones shipped with the recorded data, which is the property a static
source→licence map cannot offer — and two halves of such a map went stale inside one release.

**What it checks, and what it deliberately does not.** It compares the authored `evidence_level`
against ClinPGx's current one for the same (variant, drug, genotype). That is a *currency* check, not
an opinion: an evidence level is ClinPGx's own metadata about its own annotation, so ClinPGx is
definitionally right about it and the severity follows the mode ladder. This is unlike the
`clin_sig` and allele-function checks, which compare two expert judgements and therefore warn in both
modes — here a disagreement means the module is stale, not that two panels differ.

It does **not** check the annotation text, and it does not write `pharm_variants.csv`. Those tables
are authored `_TABLE_KINDS`; a network pass filling them would blur the authored/derived line.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import _load_csv_rows
from just_dna_format.pgx import PharmVariantRow
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import MULTI_SEP, validate_phenotype_categories

from just_dna_enricher.clinpgx_build import RELEASE_FILENAME
from just_dna_enricher.licensing import CLINPGX_TERMS, check_declared_use, merge_sources_csv

try:  # polars reads the snapshot; the builder-only import stays optional
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class ClinPgxEnrichmentError(RuntimeError):
    """Raised in strict mode when an authored annotation disagrees with the snapshot."""


@dataclass
class EvidenceConflict:
    """An authored evidence level ClinPGx's own record does not support."""

    rsid: Optional[str]
    drug: str
    genotype: Optional[str]
    authored: str
    reported: str

    def __str__(self) -> str:
        where = f"{self.rsid or '?'} + {self.drug}"
        if self.genotype:
            where += f" [{self.genotype}]"
        return f"{where}: module says level {self.authored}, ClinPGx says {self.reported}"


@dataclass
class ClinPgxResult:
    rows: list[SourceRow] = field(default_factory=list)
    conflicts: list[EvidenceConflict] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dataset: Optional[str] = None
    mode: str = "best_effort"
    declared_use: str = "unstated"


def _normalize_genotype(value: Optional[str]) -> Optional[str]:
    """`C/T` (ours) and `CT` (ClinPGx's) name the same call — compare them on a common form.

    ClinPGx writes a diploid genotype concatenated; this workspace's canonical form is sorted and
    slash-separated, because `CT` alone would parse as a single two-base allele. Comparing sorted
    characters is enough here and avoids re-deriving the split from the resolved alleles, which this
    pass does not have.
    """
    if not value:
        return None
    stripped = value.replace("/", "").replace("|", "").strip().upper()
    return "".join(sorted(stripped)) if stripped else None


def _normalize_category(value: Optional[str]) -> Optional[str]:
    """ClinPGx's `Metabolism/PK` and the authored `metabolism_pk` are the same category.

    Both sides go through the schema's own normalizer so the comparison cannot drift from the
    vocabulary. An unrecognised upstream category yields None rather than raising: the snapshot is
    not ours to validate, and a category we do not know simply cannot be matched on.
    """
    if not value:
        return None
    try:
        return validate_phenotype_categories(value)
    except ValueError:
        return None


def load_snapshot(reference: Path):
    """Read the snapshot parquet + its `release.json`. Returns `(frame, release)`."""
    if pl is None:  # pragma: no cover
        raise ClinPgxEnrichmentError("polars is required to read the ClinPGx snapshot")
    reference = Path(reference)
    parquet = reference / "data" / "annotations.parquet"
    if not parquet.is_file():
        raise ClinPgxEnrichmentError(f"no ClinPGx snapshot at {parquet}")
    release_path = reference / RELEASE_FILENAME
    release = json.loads(release_path.read_text()) if release_path.is_file() else {}
    return pl.read_parquet(parquet), release


def enrich_clinpgx(
    spec_dir: Path,
    *,
    mode: str = "best_effort",
    declared_use: str = "unstated",
    snapshot: Optional[Path] = None,
    write: bool = True,
) -> ClinPgxResult:
    """Cross-check `pharm_variants.csv` against the ClinPGx snapshot and record the terms.

    Offline-capable by design: the snapshot is local, so unlike `pgx.py` this pass needs no network
    and `--offline` does not disable it. What it still honours is the declared-use gate — the terms
    were accepted when the snapshot was *built*, and using it without a declaration is the same act.
    """
    spec_dir = Path(spec_dir)
    result = ClinPgxResult(mode=mode, declared_use=declared_use)

    pharm_path = spec_dir / "pharm_variants.csv"
    if not pharm_path.exists():
        result.warnings.append(
            "ClinPGx cross-check skipped: the module carries no pharm_variants.csv."
        )
        return result
    authored, errors, _ = _load_csv_rows(pharm_path, PharmVariantRow, "pharm_variants.csv")
    if errors:
        raise ClinPgxEnrichmentError(f"pharm_variants.csv is invalid: {errors[0]}")

    reason = check_declared_use(CLINPGX_TERMS, declared_use)  # raises on `commercial`
    if reason is not None:
        result.warnings.append(reason)
        logger.warning("%s", reason)
        return result

    if snapshot is None:
        result.warnings.append(
            "ClinPGx cross-check skipped: no snapshot provisioned. Build one with "
            "`just-dna-enricher clinpgx build`."
        )
        return result

    frame, release = load_snapshot(snapshot)
    result.dataset = release.get("dataset")

    # Index the snapshot. Drugs are `;`-separated upstream, so the cell is exploded — a row about
    # "simvastatin;simvastatin acid" is about both.
    #
    # **(rsid, drug, genotype) is NOT unique and keying on it alone produces false conflicts.** One
    # variant and one drug carry several distinct annotations: rs4149056 + simvastatin is
    # Metabolism/PK at 1A, Efficacy at 3 *and* Toxicity at 1A, each with the same three genotypes.
    # Comparing an authored Efficacy row against whichever annotation happened to be indexed first
    # reported all three of this example's correctly-authored levels as stale. So the annotation id
    # is the primary key, the category is the secondary one, and the bare triple is a last resort
    # that reports ambiguity instead of guessing.
    by_annotation: dict[tuple[str, Optional[str]], str] = {}
    by_category: dict[tuple[str, str, Optional[str], Optional[str]], str] = {}
    by_triple: dict[tuple[str, str, Optional[str]], set[str]] = {}
    for row in frame.iter_rows(named=True):
        rsid, level = row["rsid"], row["evidence_level"]
        if not rsid or not level:
            continue
        genotype = _normalize_genotype(row["genotype"])
        category = _normalize_category(row["phenotype_category"])
        by_annotation.setdefault((row["annotation_id"], genotype), level)
        for drug in MULTI_SEP.split(row["drugs"] or ""):
            drug = drug.strip().lower()
            if not drug:
                continue
            by_category.setdefault((rsid, drug, genotype, category), level)
            by_triple.setdefault((rsid, drug, genotype), set()).add(level)

    for row in authored:
        if not row.rsid or not row.evidence_level:
            continue
        drug, genotype = row.drug.strip().lower(), _normalize_genotype(row.genotype)
        category = _normalize_category(row.phenotype_category)
        reported: Optional[str] = None
        if row.annotation_id:
            reported = by_annotation.get((row.annotation_id, genotype))
        if reported is None and category is not None:
            reported = by_category.get((row.rsid, drug, genotype, category))
        if reported is None:
            levels = by_triple.get((row.rsid, drug, genotype), set())
            if len(levels) > 1:
                # Several annotations, no way to tell which this row is about. Saying "stale" here
                # would be a coin flip; say what is actually known instead.
                result.warnings.append(
                    f"{row.rsid} + {row.drug} [{row.genotype}]: ClinPGx has {len(levels)} "
                    f"annotations at levels {sorted(levels)} and this row names no "
                    f"phenotype_category or annotation_id, so its level was not checked."
                )
                continue
            reported = next(iter(levels), None)
        if reported is None:
            result.unmatched.append(f"{row.rsid} + {row.drug}")
            continue
        if reported != row.evidence_level:
            result.conflicts.append(
                EvidenceConflict(row.rsid, row.drug, row.genotype, row.evidence_level, reported)
            )

    for conflict in result.conflicts:
        logger.warning("ClinPGx evidence-level difference — %s", conflict)
    if result.unmatched:
        result.warnings.append(
            f"{len(result.unmatched)} authored annotation(s) have no matching ClinPGx record: "
            f"{sorted(set(result.unmatched))[:5]}. A miss is not a defect — the snapshot is a "
            f"point-in-time slice and a curator may annotate what ClinPGx has not."
        )

    # Strict refuses a *stale* level, because that is a currency fact rather than an opinion.
    if mode == "strict" and result.conflicts:
        raise ClinPgxEnrichmentError(
            f"strict: {len(result.conflicts)} authored evidence level(s) disagree with ClinPGx "
            f"({result.conflicts[0]}). An evidence level is ClinPGx's own metadata about its own "
            f"annotation, so a difference means the module is stale."
        )

    # The licence hash comes from the snapshot's release.json, which the builder took from the
    # LICENSE.txt inside the very archive the data came from.
    row = CLINPGX_TERMS.row(
        "annotation", declared_use=declared_use, dataset=result.dataset
    )
    recorded_hash = release.get("license_sha256")
    if recorded_hash:
        row = row.model_copy(update={"license_sha256": recorded_hash})
    result.rows = [row]

    if write:
        _merge_sources_csv(result.rows, spec_dir / "sources.csv")
    return result


def _merge_sources_csv(rows: list[SourceRow], path: Path) -> None:
    """Merge into an existing `sources.csv`, never clobbering a row already there."""
    existing: list[SourceRow] = []
    if path.exists():
        parsed, errors, _ = _load_csv_rows(path, SourceRow, "sources.csv")
        if errors:
            raise ClinPgxEnrichmentError(f"existing sources.csv is invalid: {errors[0]}")
        existing = parsed
    merge_sources_csv(rows, path, existing)
