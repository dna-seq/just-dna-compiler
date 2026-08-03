"""Draft `pharm_variants.csv` rows from the ClinPGx snapshot (0.5, RM26) — the second provider.

The clean contrast to `pgx_draft`: every column `PharmVariantRow` requires is *published*, so this
provider builds real rows and hands them to `draft.append_rows` unchanged. Nothing is stubbed and
nothing is invented. Where `pgx_draft` had to skip what CPIC's grammar could not express, the work
here is almost entirely re-spelling.

**What it fills, and what it deliberately does not.** It fills `rsid`, `genotype`, `drug`,
`phenotype_category`, `annotation_id`, `evidence_level` and a transcribed `conclusion`. It does
**not** fill `chrom`/`start`/`ref`: the snapshot carries no coordinate, and even if it did, a
coordinate authored here would be compared by `resolution._verify` against the table that supplied
it. Resolution puts coordinates in `resolution.csv`, which is where they belong — and
`PharmVariantRow.variant_key` is a `@property` over them, so filling them would make a row's identity
depend on the enricher.

**The key is all five parts.** `(variant_key, drug, genotype, phenotype_category, annotation_id)`,
which is `draft.natural_key`'s own answer for this model, so a re-run can never append a row the
compiler would then reject. Indexing ClinPGx by the bare `(variant, drug)` triple is a real bug that
has already been made once in this package.

**One annotation names several drugs.** `drugs` is `;`-joined (`antidepressants;citalopram;paroxetine`
is one annotation), and `drug` is singular, so one snapshot record becomes one row per drug. They
share an `annotation_id` and key distinctly, which is correct: PharmGKB really is saying the same
thing about three drugs.

Skipped, with a warning rather than a coercion: haplotype-keyed genotypes (`*1`, `*1/*1`) belong on
`DiplotypeRow`, and symbolic alleles (`del/del`) are RM5. Both are the policy `pgx_draft` already set.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from just_dna_compiler.draft import DraftReport, append_rows
from just_dna_format.pgx import PharmVariantRow

from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, _normalize_category, load_snapshot
from just_dna_enricher.licensing import CLINPGX_TERMS, check_declared_use, merge_sources_file

logger = logging.getLogger(__name__)

#: A diploid nucleotide call as ClinPGx writes it: two bases, unseparated (`CC`, `CT`).
_TWO_BASE = re.compile(r"^[ACGT]{2}$")

#: ClinPGx joins the drugs one annotation covers with `;`.
_DRUG_SEP = ";"


@dataclass
class ClinPgxDraftResult:
    """What a draft run did."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def added(self) -> int:
        return sum(len(r.added) for r in self.reports)

    @property
    def differs(self) -> int:
        return sum(len(r.differs) for r in self.reports)


def _authored_genotype(raw: Optional[str]) -> Optional[str]:
    """`CC` → `C/C`. Only an unambiguous two-base call; anything else is the caller's to skip.

    Splitting is safe *here* precisely because the cell is two single bases: `CT` can only be `C/T`.
    The general case needs the resolved ref/alt to disambiguate, which this pass does not have — so
    it does not guess, it declines. Sorted, because the authored grammar wants an unphased call
    alphabetical."""
    if not raw or not _TWO_BASE.match(raw.strip().upper()):
        return None
    first, second = sorted(raw.strip().upper())
    return f"{first}/{second}"


def _rows_from_snapshot(
    records: Sequence[dict],
    *,
    genes: Sequence[str],
    drugs: Sequence[str],
    min_evidence_level: Optional[str],
) -> tuple[list[PharmVariantRow], list[str]]:
    """Snapshot records → `PharmVariantRow`s, reporting everything the grammar cannot hold."""
    wanted_drugs = {d.strip().lower() for d in drugs if d.strip()}
    rows: list[PharmVariantRow] = []
    warnings: list[str] = []
    skipped_haplotype = skipped_symbolic = skipped_unidentified = 0

    for record in records:
        rsid = (record.get("rsid") or "").strip()
        if not rsid:
            skipped_unidentified += 1
            continue
        raw_genotype = (record.get("genotype") or "").strip()
        genotype = _authored_genotype(raw_genotype)
        if genotype is None:
            if raw_genotype.startswith("*"):
                skipped_haplotype += 1
            else:
                skipped_symbolic += 1
            continue
        if min_evidence_level and not _meets_level(record.get("evidence_level"), min_evidence_level):
            continue
        category = _normalize_category(record.get("phenotype_category"))
        annotation_id = (record.get("annotation_id") or "").strip() or None
        for drug in _split_drugs(record.get("drugs")):
            if wanted_drugs and drug.lower() not in wanted_drugs:
                continue
            rows.append(
                PharmVariantRow(
                    rsid=rsid,
                    genotype=genotype,
                    drug=drug,
                    phenotype_category=category,
                    annotation_id=annotation_id,
                    evidence_level=(record.get("evidence_level") or None),
                    # A transcription of the published parts, not an interpretation — the same shape
                    # `pgx_draft` uses. The human owns what the module actually claims.
                    conclusion=(
                        f"ClinPGx {annotation_id or '(no id)'}: {genotype} and {drug}"
                        f"{f' — {category}' if category else ''}"
                    ),
                )
            )
    if genes:
        warnings.append(
            "--gene was given but the ClinPGx annotation snapshot carries no gene column; the "
            "filter was not applied. Filter by --drug, or narrow the file afterwards."
        )
    for count, what in (
        (skipped_haplotype, "haplotype-keyed (a star allele belongs on diplotypes.csv)"),
        (skipped_symbolic, "symbolic or non-nucleotide (RM5)"),
        (skipped_unidentified, "carrying no rsID, so nothing this format can key on"),
    ):
        if count:
            warnings.append(f"{count} annotation(s) skipped: {what}.")
    return rows, warnings


def _split_drugs(raw: Optional[str]) -> list[str]:
    """The `;`-joined drug list, de-duplicated, first-occurrence order (emitted order is digest-visible)."""
    if not raw:
        return []
    seen: dict[str, None] = {}
    for token in str(raw).split(_DRUG_SEP):
        cleaned = token.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


#: PharmGKB's levels, strongest first. Ordering them is a *presentation* of a published ranking, not
#: a re-encoding: unlike ClinGen's dosage codes, these sort correctly as strings only by accident
#: (`1A` < `1B` < `2A` … but `4` > `2A`), so the order is written out.
_LEVEL_ORDER: tuple[str, ...] = ("1A", "1B", "2A", "2B", "3", "4")


def _meets_level(level: Optional[str], floor: str) -> bool:
    """Is `level` at least as strong as `floor`? An unknown level is kept, never silently dropped."""
    if not level:
        return True
    try:
        return _LEVEL_ORDER.index(level) <= _LEVEL_ORDER.index(floor)
    except ValueError:
        return True


def draft_pharm_variants(
    spec_dir: Path,
    *,
    snapshot: Path,
    genes: Sequence[str] = (),
    drugs: Sequence[str] = (),
    min_evidence_level: Optional[str] = None,
    declared_use: str = "unstated",
    dry_run: bool = False,
) -> ClinPgxDraftResult:
    """Append ClinPGx annotations into `pharm_variants.csv`, never rewriting a row that is there.

    Inject-only: `snapshot` is a path this function reads, never downloads (build it with
    `just-dna-enricher clinpgx build`). Re-runnable — narrow by `--drug` and run again as a module
    grows; a row already present is reported, not replaced.
    """
    skip_reason = check_declared_use(CLINPGX_TERMS, declared_use)
    if skip_reason:
        # Acquisition-time refusal: the terms are accepted by taking the data, so nothing is read.
        return ClinPgxDraftResult(warnings=[skip_reason], skipped=True)

    records, release = load_snapshot(snapshot)
    rows, warnings = _rows_from_snapshot(
        records, genes=genes, drugs=drugs, min_evidence_level=min_evidence_level
    )
    if not rows:
        return ClinPgxDraftResult(warnings=warnings + ["nothing matched; no rows drafted"])

    reports = [append_rows(spec_dir, "pharm_variants.csv", rows, dry_run=dry_run)]
    if not dry_run:
        # A pass that consults a source must WRITE its SourceRow: the compile gate and
        # `manifest.sources` read sources.csv and nothing else, so a row that is only returned is a
        # source the module cannot account for.
        merge_sources_file(
            [
                CLINPGX_TERMS.row(
                    "annotation",
                    declared_use=declared_use,
                    dataset=release.get("dataset"),
                )
            ],
            spec_dir / "sources.csv",
            error=ClinPgxEnrichmentError,
        )
    return ClinPgxDraftResult(reports=reports, warnings=warnings)
