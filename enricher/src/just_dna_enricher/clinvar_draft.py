"""Draft a gene panel's `variants.csv` rows from the ClinVar snapshot (0.5.1, RM26).

The provider that RM4 has been waiting for, in the shape the charter allows: it **drafts rows a human
then owns**, with no compile-time reference materialization and no injected reference in the compile
path. Inject-only — `snapshot` is a path this function reads, never downloads.

**Why these rows are partial, and why that is the honest answer rather than a limitation.**
`VariantRow.genotype` is required and ClinVar publishes **alleles, not genotypes**. Whether carrying a
pathogenic allele once is informative — a carrier, an affected proband, neither — is *zygosity
interpretation*, and it follows from the condition's inheritance mode, not from the allele. ClinVar
cannot supply it and this provider must not invent it: writing `A/G` because the alt is `G` would be
a clinical claim the source never made. `reference_examples/pathogenic_clinvar/` is a human having
made exactly that call, by hand, per row.

So `genotype` is left carrying `vocab.TEMPLATE_PLACEHOLDER`, which no mode compiles: the file is
authored, in place, in the right order, and loudly incomplete until a human has decided. Rows are
placed into their **gene's block** (`group_by=("gene",)`), because a panel is read gene by gene and
stubs stranded at the end of a 500-row file are what made this unpleasant enough to look like a
blocker.

**Identity is filled whole or not at all.** With an rsID, only the rsID goes in; without one, the full
`chrom`/`start`/`ref`/`alts`. Never a subset — a lone `alts` on a position-only row makes
`derive_variant_key` mint a VRS `ga4gh:VA.…` id instead of `chrom:start:ref`, so a partial coordinate
silently changes which variant the row *is*.

**What it will not fill**, each a rule rather than an omission:

* `weight`, `direction`, `effect_size`, `effect_measure`, `effect_allele` — ClinVar publishes no
  effect statistic, and a weight is the author's model of the finding.
* `trait_efo_id` — ClinVar's `condition` is free text and MedGen, not EFO. Mapping it is inference.
* `acmg_sf` — a different list this package deliberately does not hold (see the roadmap).
* `curator`, `method` — the spec's `defaults:` block owns those.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows
from just_dna_format.spec import VariantRow

from just_dna_enricher.clinvar import select_by_gene
from just_dna_enricher.licensing import CLINVAR_TERMS, check_declared_use, merge_sources_file

logger = logging.getLogger(__name__)


class ClinVarDraftError(RuntimeError):
    """A gene-panel draft could not be completed."""


#: The clinical calls a risk panel is usually drawn from. Overridable; not a judgement baked in.
DEFAULT_CLIN_SIG: frozenset[str] = frozenset({"pathogenic", "likely_pathogenic"})

#: `clin_sig` → the required `state`. A **fold of the source's own call**, not an interpretation:
#: `state` is the legacy axis every row must carry, and `direction`/`clin_sig` are the orthogonal
#: ones. Anything outside this map leaves `state` to the human rather than guessing a default.
_STATE_BY_CLIN_SIG: dict[str, str] = {
    "pathogenic": "risk",
    "likely_pathogenic": "risk",
    "benign": "neutral",
    "likely_benign": "neutral",
}


@dataclass
class ClinVarDraftResult:
    """What a panel draft did."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def added(self) -> int:
        return sum(len(r.added) for r in self.reports)

    @property
    def already_present(self) -> int:
        return sum(len(r.already_present) for r in self.reports)

    @property
    def invalid(self) -> int:
        return sum(len(r.invalid) for r in self.reports)


def _identity_cells(record: dict) -> Optional[dict]:
    """The identity half of a row: the rsID, else the whole coordinate. Never a mixture.

    Returns `None` when the record carries neither, which the caller reports rather than writing a
    row that cannot be keyed."""
    rsid = (record.get("rsid") or "").strip()
    if rsid:
        return {"rsid": rsid}
    chrom, start = record.get("chrom"), record.get("start")
    ref, alt = (record.get("ref") or "").strip(), (record.get("alt") or "").strip()
    if chrom and start is not None and ref and alt:
        return {"chrom": str(chrom), "start": int(start), "ref": ref, "alts": alt}
    return None


def _row_cells(record: dict) -> Optional[dict]:
    """One ClinVar record → the authored cells this provider is willing to state."""
    identity = _identity_cells(record)
    if identity is None:
        return None
    clin_sig = (record.get("clin_sig") or "").strip() or None
    condition = (record.get("condition") or "").strip() or None
    stars = record.get("review_stars")
    cells: dict = {
        **identity,
        "gene": (record.get("gene") or "").strip() or None,
        "clin_sig": clin_sig,
        "clinvar": True,
        "phenotype": condition,
        # A transcription of the published record, not a reading of it — the shape `pgx_draft` set.
        "conclusion": (
            f"ClinVar: {clin_sig or 'no call'}"
            f"{f' ({stars}★)' if stars is not None else ''}"
            f"{f' — {condition}' if condition else ''}"
        ),
    }
    state = _STATE_BY_CLIN_SIG.get(clin_sig or "")
    if state is not None:
        cells["state"] = state
    # The 0.3 booleans stay authoritative and are folded from the same call, never independently.
    if clin_sig in ("pathogenic", "likely_pathogenic"):
        cells["pathogenic"] = True
    elif clin_sig in ("benign", "likely_benign"):
        cells["benign"] = True
    return cells


def draft_gene_panel(
    spec_dir: Path,
    genes: Sequence[str],
    *,
    snapshot: Path,
    clin_sig: frozenset[str] = DEFAULT_CLIN_SIG,
    min_review_stars: int = 2,
    declared_use: str = "unstated",
    dry_run: bool = False,
) -> ClinVarDraftResult:
    """Draft `variants.csv` rows for one or more genes, leaving `genotype` for the human.

    Re-runnable and additive: run it per gene as a panel grows. A variant already in the file — stub
    or filled — is reported, never re-added, because a partial row keys on the identity columns rather
    than on a key that runs through the placeholder.

    `min_review_stars` defaults to 2 (multiple submitters, no conflicts). A panel that silently mixes
    a 0-star "no assertion criteria" submission with a 3-star expert-panel review is worse than one
    that says which floor it drew from, and the floor belongs in the author's hands.
    """
    skip_reason = check_declared_use(CLINVAR_TERMS, declared_use)
    if skip_reason:
        return ClinVarDraftResult(warnings=[skip_reason], skipped=True)

    records = select_by_gene(
        Path(snapshot), list(genes), clin_sig=clin_sig, min_review_stars=min_review_stars
    )
    warnings: list[str] = []
    partials: list[PartialRow] = []
    unkeyable = 0
    for record in records:
        cells = _row_cells(record)
        if cells is None:
            unkeyable += 1
            continue
        partials.append(
            PartialRow(
                model=VariantRow,
                cells=cells,
                stubbed=("genotype",),
                # Identity, not the natural key: the key runs through `genotype`, which is the stub.
                # Matching here means "this variant is already in the panel, however it was written".
                match_on=("rsid", "chrom", "start", "ref"),
            )
        )
    if unkeyable:
        warnings.append(
            f"{unkeyable} ClinVar record(s) skipped: neither an rsID nor a complete coordinate, so "
            f"nothing this format can key on."
        )
    if not partials:
        return ClinVarDraftResult(warnings=warnings + ["nothing matched; no rows drafted"])

    report = append_partial_rows(
        spec_dir, "variants.csv", partials, group_by=("gene",), dry_run=dry_run
    )
    warnings.extend(f"row not drafted — {o.differences['errors'][1]}" for o in report.invalid)
    if report.added:
        warnings.append(
            f"{len(report.added)} row(s) carry an unreplaced genotype placeholder and will not "
            f"compile until you decide the zygosity each finding is about."
        )
    if not dry_run:
        # A source that rows were copied out of must be recorded, permissive terms or not: the compile
        # gate and `manifest.sources` read sources.csv and nothing else.
        merge_sources_file(
            [CLINVAR_TERMS.row("annotation", declared_use=declared_use)],
            spec_dir / "sources.csv",
            error=ClinVarDraftError,
        )
    return ClinVarDraftResult(reports=[report], warnings=warnings)
