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

from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows, append_rows
from just_dna_format.spec import StudyRow, VariantRow

from just_dna_enricher.clinvar import citations_for, select_by_gene
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
        """Rows added across **every** table this run wrote — variants *and* their studies.

        Ask `added_for` when you mean one of them: since the provider began drafting grounding
        evidence too, a bare total no longer answers "how many variants did I get"."""
        return sum(len(r.added) for r in self.reports)

    def added_for(self, csv_name: str) -> int:
        """Rows added to one table."""
        return sum(len(r.added) for r in self.reports if r.csv_name == csv_name)

    @property
    def already_present(self) -> int:
        return sum(len(r.already_present) for r in self.reports)

    @property
    def invalid(self) -> int:
        return sum(len(r.invalid) for r in self.reports)


def multi_allelic_rsids(records: Sequence[dict]) -> set[str]:
    """rsIDs that name more than one alt at one position in this selection.

    An rsID is a **position/multi-allelic-level** tag, not a per-allele one: ClinVar lists
    `rs773443949` in HFE as both `G>A` and `G>T`. An rsid-only row cannot say which, so drafting one
    row per record would write two identical rows — and de-duplicating them would silently drop a real
    allele. Found by drafting an actual panel; these records take the coordinate identity instead."""
    alts_by_site: dict[tuple, set[str]] = {}
    for record in records:
        rsid = (record.get("rsid") or "").strip()
        if not rsid:
            continue
        site = (rsid, record.get("chrom"), record.get("start"), record.get("ref"))
        alts_by_site.setdefault(site, set()).add((record.get("alt") or "").strip())
    return {site[0] for site, alts in alts_by_site.items() if len(alts) > 1}


def _identity_cells(record: dict, *, force_coordinate: bool = False) -> Optional[dict]:
    """The identity half of a row: the rsID, else the whole coordinate. Never a mixture.

    `force_coordinate` is set for an rsID that names several alts here — the rsID is true of the row
    but cannot *identify* it, and an identity that does not identify is worse than a longer one.

    Returns `None` when the record carries neither, which the caller reports rather than writing a
    row that cannot be keyed."""
    rsid = (record.get("rsid") or "").strip()
    if rsid and not force_coordinate:
        return {"rsid": rsid}
    chrom, start = record.get("chrom"), record.get("start")
    ref, alt = (record.get("ref") or "").strip(), (record.get("alt") or "").strip()
    if chrom and start is not None and ref and alt:
        return {"chrom": str(chrom), "start": int(start), "ref": ref, "alts": alt}
    return None


def _genotype_worklist(records: Sequence[dict]) -> list[str]:
    """The alleles each stubbed row's pending genotype must be written from.

    **The provider was asking for a decision and withholding its inputs.** A `genotype` is nucleotides
    drawn from `{ref} ∪ alts`, and a row identified by its rsID carries neither — `_identity_cells`
    prefers the rsID, correctly (it is the stabler, more legible identity, and the model forbids
    `ref`/`alts` without a coordinate anyway), so the author was left with `rs201157428` and
    `<<REPLACE>>` and nothing to write from. Worse, the obvious next move does not work: `enrich`
    would resolve the alleles, and it *refuses* to load a file containing a placeholder — which is
    right, because forward resolution is allele-aware (`genotype_fits`) and a placeholder genotype
    would silently skip that filter on exactly the one-to-many rsIDs that need it.

    So the alleles are **reported**, never written. Writing them would need the whole coordinate
    (identity is filled whole or not at all), which would discard the rsID identity the provider
    deliberately chose; and `alts` is redundancy-bearing — the compiler's allele-membership check
    compares the human's genotype against it, and that check keeps its force precisely because the two
    were authored independently.

    One line per stubbed row, uncapped: each is a task the author must do, and a task list that
    silently drops entries is worse than a long one.
    """
    lines: list[str] = []
    for record in records:
        ref, alt = (record.get("ref") or "").strip(), (record.get("alt") or "").strip()
        if not (ref and alt):
            continue
        label = (record.get("rsid") or "").strip() or f"{record.get('chrom')}:{record.get('start')}"
        alleles = ", ".join(sorted({ref, alt}))
        lines.append(f"  genotype for {label}: ClinVar publishes {ref}>{alt} — an allele pair from {{{alleles}}}")
    return lines


def _row_cells(record: dict, *, force_coordinate: bool = False) -> Optional[dict]:
    """One ClinVar record → the authored cells this provider is willing to state."""
    identity = _identity_cells(record, force_coordinate=force_coordinate)
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


#: How many of a variant's ClinVar-linked papers to draft. `rs1800562` alone carries 84 — a panel
#: does not need them all, and an author drowning in study rows will not read any. Capped rather than
#: sampled, and the number dropped is always reported: a silent cap reads as "this is everything".
DEFAULT_MAX_CITATIONS = 3


def _study_rows(
    records: Sequence[dict],
    links: dict[str, list[str]],
    limit: int,
    coordinate_only: set[str],
) -> tuple[list[StudyRow], int]:
    """ClinVar's own literature links → `studies.csv` rows, deduplicated per (variant, pmid).

    These are **real** rows, not partial ones: `StudyRow` needs a PMID and an identifier, and ClinVar
    supplies both. That is the difference from `variants.csv`, where the missing piece — zygosity —
    is a judgement rather than a datum.
    """
    rows: list[StudyRow] = []
    seen: set[tuple] = set()
    dropped = 0
    for record in records:
        pmids = links.get(str(record.get("variation_id") or ""), [])
        if not pmids:
            continue
        # A study must carry the SAME identity its variant row got, or it is an orphan. When the
        # variant was written with a coordinate because its rsID names several alleles, the study has
        # to be too — the compiler's orphan check found this the first time a real panel was drafted.
        rsid = (record.get("rsid") or "").strip() or None
        if rsid in coordinate_only:
            rsid = None
        coordinate = (
            {}
            if rsid
            else {
                "chrom": str(record.get("chrom") or "") or None,
                "start": record.get("start"),
                "ref": (record.get("ref") or "").strip() or None,
            }
        )
        for pmid in pmids[:limit]:
            key = (rsid, coordinate.get("chrom"), coordinate.get("start"), pmid)
            if key in seen:
                continue
            seen.add(key)
            rows.append(StudyRow(rsid=rsid, pmid=pmid, **coordinate))
        dropped += max(0, len(pmids) - limit)
    return rows, dropped


def draft_gene_panel(
    spec_dir: Path,
    genes: Sequence[str],
    *,
    snapshot: Path,
    clin_sig: frozenset[str] = DEFAULT_CLIN_SIG,
    min_review_stars: int = 2,
    max_citations: int = DEFAULT_MAX_CITATIONS,
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
    ambiguous = multi_allelic_rsids(records)
    if ambiguous:
        warnings.append(
            f"{len(ambiguous)} rsID(s) name more than one allele here "
            f"({', '.join(sorted(ambiguous))}) — written with their full coordinate, since an rsID "
            f"alone cannot say which allele the row is about."
        )
    for record in records:
        cells = _row_cells(record, force_coordinate=(record.get("rsid") or "").strip() in ambiguous)
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
                # `alts` is in the set because without it two rows of a multi-allelic site collapse
                # into one and a real allele is lost — which is exactly what drafting HFE did.
                match_on=("rsid", "chrom", "start", "ref", "alts"),
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
    reports = [report]

    # Grounding evidence, from ClinVar's own literature links. Without this a drafted panel could not
    # compile at all — `studies.csv` is mandatory and the VCF carries no PMIDs — so the provider
    # produced a module that needed evidence nobody could supply. Build it with `clinvar citations`.
    links = citations_for(Path(snapshot), [str(r.get("variation_id") or "") for r in records])
    if not links:
        warnings.append(
            "no citations table in the snapshot, so no studies.csv rows were drafted — grounding "
            "evidence is mandatory, so add it by hand or run `just-dna-enricher clinvar citations`."
        )
    else:
        studies, dropped = _study_rows(records, links, max_citations, ambiguous)
        if studies:
            reports.append(
                append_rows(spec_dir, "studies.csv", studies, group_by=("rsid",), dry_run=dry_run)
            )
        if dropped:
            warnings.append(
                f"{dropped} further ClinVar citation(s) not drafted (--max-citations {max_citations})."
            )
    warnings.extend(f"row not drafted — {o.differences['errors'][1]}" for o in report.invalid)
    if report.added:
        warnings.append(
            f"{len(report.added)} row(s) carry an unreplaced genotype placeholder and will not "
            f"compile until you decide the zygosity each finding is about."
        )
        warnings.extend(_genotype_worklist(records))
    if not dry_run:
        # A source that rows were copied out of must be recorded, permissive terms or not: the compile
        # gate and `manifest.sources` read sources.csv and nothing else.
        merge_sources_file(
            [CLINVAR_TERMS.row("annotation", declared_use=declared_use)],
            spec_dir / "sources.csv",
            error=ClinVarDraftError,
        )
    return ClinVarDraftResult(reports=reports, warnings=warnings)
