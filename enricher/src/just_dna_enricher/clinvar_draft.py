"""Draft a gene panel's `variants.csv` rows from the ClinVar snapshot (0.5.1, RM26).

The provider that RM4 has been waiting for, in the shape the charter allows: it **drafts rows a human
then owns**, with no compile-time reference materialization and no injected reference in the compile
path. The *compiler* stays inject-only; this is the network tier, so the snapshot it reads is found on
the usual cache ladder and provisioned from HuggingFace when absent (`--offline` forbids that, and an
explicit `--snapshot` is taken as given). It used to be a required argument, which meant the published
snapshot could not reach an author at all: they had to build 4.4M records from a 200 MB VCF first.

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

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows, append_rows
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from just_dna_format.vrs import in_pseudoautosomal_region, normalize_chrom
from pydantic import ValidationError

from just_dna_enricher.clinvar import citations_for, clinvar_dataset_label, select_by_gene
from just_dna_enricher.download import ensure_clinvar_snapshot
from just_dna_enricher.enrich import source_build_mismatch
from just_dna_enricher.licensing import (
    CLINVAR_TERMS,
    check_declared_use,
    merge_sources_file,
    withdraw_stale_dataset,
)
from just_dna_enricher.locations import resolve_clinvar_reference
from just_dna_enricher.provenance import stamp_draft_digest
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)


class ClinVarDraftError(RuntimeError):
    """A gene-panel draft could not be completed."""


#: The clinical calls a risk panel is usually drawn from. Overridable; not a judgement baked in.
DEFAULT_CLIN_SIG: frozenset[str] = frozenset({"pathogenic", "likely_pathogenic"})

#: The assembly the snapshot's coordinates are on. `clinvar_build` reads NCBI's `vcf_GRCh38/` file, so
#: this is a property of what we build rather than a guess — named for the same reason
#: `gnomad.FREQUENCY_GENOME_BUILD` is, since every build confusion in this package began as a literal.
CLINVAR_GENOME_BUILD = "GRCh38"

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
    """rsIDs that name more than one distinct **allele event** in this selection.

    An rsID is a **position/multi-allelic-level** tag, not a per-allele one: ClinVar lists
    `rs773443949` in HFE as both `G>A` and `G>T`. An rsid-only row cannot say which, so drafting one
    row per record would write two identical rows — and de-duplicating them would silently drop a real
    allele. Found by drafting an actual panel; these records take the coordinate identity instead.

    **The event is `(chrom, start, ref, alt)`, and keying the *site* on `ref` was the bug (S41).**
    The predicate used to group by `(rsid, chrom, start, ref)` and fire on >1 alt inside that group,
    which reads as "more than one alt at one position" and is not: an ordinary ClinVar dup/del mirror
    pair — `A>AT` beside `ATT>A` at one position, the same event written from either side — lands in
    two groups of one alt each, so the rsID was never flagged, both records reduced to the same rsid
    signature, and `append_partial_rows` dropped the second as `already_present`. A differing `ref`
    breaks an rsid-only identity exactly as thoroughly as a differing `alt`; the docstring's own claim
    was the correct rule and the code was narrower than it. Measured on the `2026-06-27` snapshot over
    BRCA1/BRCA2/ATM/MLH1/MSH2: 942 rsIDs flagged before, 1,589 after, and the 647 newly flagged are
    exactly the 647 identities that were collapsing — 725 records, of which 187 dropped a
    *better-reviewed* record than the one kept, since `select_by_gene` orders by `ref` before
    `review_stars DESC` and the survivor is therefore an artifact of allele spelling.

    Distinctness is over the whole event rather than over records, deliberately: two rows of the same
    allele (a re-submission under a second `variation_id`) are one claim written twice and collapsing
    them loses nothing, while coordinate identity would not separate them anyway. On that measurement
    the two readings coincide — every multi-record rsID is also multi-allele — but only this one is
    true by construction, and the other would flag rsIDs whose collapse the fix cannot repair."""
    events_by_rsid: dict[str, set[tuple]] = {}
    for record in records:
        rsid = (record.get("rsid") or "").strip()
        if not rsid:
            continue
        event = (
            record.get("chrom"),
            record.get("start"),
            (record.get("ref") or "").strip(),
            (record.get("alt") or "").strip(),
        )
        events_by_rsid.setdefault(rsid, set()).add(event)
    return {rsid for rsid, events in events_by_rsid.items() if len(events) > 1}


def _identity_cells(record: dict, *, force_coordinate: bool = False) -> dict | None:
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


#: The identity columns a partial row matches on — see the `PartialRow` call site for why the natural
#: key cannot be used. Shared so the signature a row is keyed by and the one used to look its source
#: record back up cannot drift apart.
_MATCH_ON: tuple[str, ...] = ("rsid", "chrom", "start", "ref", "alts")


def sole_expressible_genotype(record: dict) -> str | None:
    """The one genotype a caller can emit at this locus, or `None` where zygosity is a real decision.

    **The placeholder exists to protect a judgement, and on a non-diploid contig there is none to
    protect** (S6). Carrying a pathogenic allele is a carrier state or an affected one depending on
    the condition's inheritance mode, which ClinVar does not state — that is why `genotype` is stubbed
    at all. But the mitochondrial genome is haploid and chrY outside the pseudoautosomal regions is
    hemizygous: exactly one genotype is expressible per allele there, so the decision the stub is
    holding open does not exist, and every consumer of `draft_gene_panel` was left to rediscover
    independently that its natural "write both zygosities" fill is wrong for those rows. One did, at
    264 mitochondrial loci in a genome-wide panel and 260 in a cardiac one, each asserting a second
    copy that is not there.

    Y is decided **per locus**, three-valued, through the same predicate the compiler's ploidy check
    uses: PAR1 and PAR2 recombine with X and are diploid in every karyotype, and `XG` and `SPRY3`
    straddle a boundary, so a gene- or contig-wide verdict is wrong for half of either. `True`
    (diploid) and `None` (no PAR table for this build) both keep the placeholder — an undecided
    question is not an answer, and the author still has one to make.

    The allele written is the **ALT**: a variant row is an annotation about carrying the finding, and
    on a haploid contig carrying it is spelled with one allele. The heteroplasmy axis is a different
    question with its own table kind, which is why the aggregated notice at the draft's end says so
    rather than leaving the reading implicit.
    """
    chrom = normalize_chrom(str(record.get("chrom") or ""))
    alt = (record.get("alt") or "").strip()
    start = record.get("start")
    if not alt or "," in alt or chrom not in ("MT", "Y"):
        return None
    if chrom == "Y" and (
        start is None or in_pseudoautosomal_region("Y", int(start)) is not False
    ):
        return None
    return alt


def _signature(cells: dict) -> tuple[str, ...]:
    """The `_MATCH_ON` signature of a row, spelled exactly as `append_partial_rows` spells it."""
    return tuple(str(cells.get(column) or "").strip() for column in _MATCH_ON)


def _label(record: dict) -> str:
    """How to name one ClinVar record to a human: its rsID, else its coordinate.

    Takes an authored CSV row just as happily as a snapshot record — both spell `rsid`, `chrom` and
    `start` the same way — which is what lets the reports below name a row they read back out of the
    file in the same words they name a record this run selected.
    """
    return (record.get("rsid") or "").strip() or f"{record.get('chrom')}:{record.get('start')}"


def _publishes_alleles(record: dict) -> bool:
    """Whether the source stated both alleles for this record: the worklist's own precondition.

    Named once because two callers need it and a second copy is the one about to be wrong — the
    worklist skips a record it cannot describe, and the count of what was skipped is reported
    separately, so both have to agree on what "cannot describe" means.
    """
    return bool((record.get("ref") or "").strip() and (record.get("alt") or "").strip())


def _placeholder_rows(path: Path, column: str) -> list[dict[str, str]]:
    """Rows already in the authored file whose `column` is still the drafting placeholder.

    **The scope of everything this provider reports as open work (RM71).** It used to be the rows a
    single run *added*, which is a correct answer to a different question: a re-run of the command
    adds nothing, so it reported nothing, and the alleles a stubbed `genotype` must be written from
    were stated exactly once in a stream the author had no way to ask again. Every place those
    alleles could legally be *written* is the wrong place — the identity is filled whole or not at
    all, `alts` is redundancy-bearing, and an unread sidecar becomes a permanent resident — so the
    repair is that the stream can be re-requested rather than that a file gains a column.

    Reading the file back also keeps the earlier repair's benefit, and for a better reason than
    scoping did: a row the model refused is not in the file at all, and a row the human has settled
    no longer carries the placeholder.

    **A row whose identity is itself a placeholder is not a variant yet, and is skipped.** That is
    the scaffolded template row — `<<REPLACE>>` in `rsid` as well as in `genotype` — which is the
    documented state of a spec directory *before* anything is drafted into it. It has no identity to
    match, so nothing can ever hold its alleles, and reporting it here would put a row no draft
    produced into a list of drafting work with the sentinel as its name. The compiler already refuses
    it by name, which is where that row's notice belongs.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if (row.get(column) or "").strip() == TEMPLATE_PLACEHOLDER
            and TEMPLATE_PLACEHOLDER not in _signature(row)
        ]


def _open_stubs(
    report: DraftReport,
    column: str,
    stubbed_by_signature: dict[tuple[str, ...], tuple[str, ...]],
) -> list[tuple[tuple[str, ...], dict[str, str] | None]]:
    """Every row with an open `column` stub: the file's, plus the ones a dry run would have written.

    One path and no `dry_run` branch, because the union is what makes the two agree. After a real run
    the added rows are in the file already, so they contribute nothing and the union is idempotent;
    under `dry_run` the file has not moved, so `report.added` is the only place they exist. A dry run
    that reported an empty worklist on a fresh spec directory would be exactly the once-only defect
    again, one flag over.

    Which columns a would-add row leaves open is **read back from the decision that made the row**
    (`stubbed_by_signature`, the same tuple handed to `PartialRow`), never restated here: a provider
    that can fill `genotype` on a haploid contig fills it, and a second copy of that rule is the one
    that goes stale.

    Returns `(signature, authored row or None)` in file order, then would-add order. The row is
    carried because it is the only thing that can name a stub this run holds no record for.
    """
    tasks: list[tuple[tuple[str, ...], dict[str, str] | None]] = []
    covered: set[tuple[str, ...]] = set()
    for row in _placeholder_rows(report.path, column):
        signature = _signature(row)
        covered.add(signature)
        tasks.append((signature, row))
    for outcome in report.added:
        signature = outcome.key
        if signature is None or signature in covered:
            continue
        if column not in stubbed_by_signature.get(signature, ()):
            continue
        covered.add(signature)
        tasks.append((signature, None))
    return tasks


def _refusal_summary(invalid: Sequence) -> list[str]:
    """Rows the model refused, **grouped by reason with a count** — never one line per row.

    A per-row line here is the failure mode this repo has hit five times in the drafting providers: a
    two-gene panel produced twenty-six identical `state: Field required` lines, which buries every other
    finding a run reports and tells the author nothing they can act on. Group by the message, count, and
    name the rows — and cap the naming, because the list is context for a diagnosis rather than a
    worklist the author must work through (unlike `_genotype_worklist`, which is uncapped for exactly
    the opposite reason).

    This is the generic net. A cause this provider can *diagnose* should be caught before validation and
    explained in its own words, the way an undecided clinical call now is — a raw pydantic message
    reaching the author as the whole explanation is a misdiagnosis, not a report.
    """
    by_reason: dict[str, list[str]] = {}
    for outcome in invalid:
        reason = outcome.differences.get("errors", (None, "unknown"))[1]
        label = "/".join(part for part in (outcome.key or ()) if part) or "?"
        by_reason.setdefault(reason, []).append(label)
    lines = []
    for reason, labels in by_reason.items():
        shown = ", ".join(labels[:6]) + (f", … and {len(labels) - 6} more" if len(labels) > 6 else "")
        lines.append(f"{len(labels)} row(s) not drafted — {reason}. Affected: {shown}")
    return lines


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

    **Pass the records whose rows are still open** — `_open_stubs` decides which those are, off the
    file rather than off this run. It used to be given every candidate record, so the list covered
    rows the model had refused and rows already in the file: a "3 row(s) carry a placeholder" header
    followed by twenty-seven lines. A worklist naming work that does not exist is worse than no
    worklist, and that repair stands. What it also did, though, was make the list a property of a
    single run — so a second `draft-panel` added nothing and therefore said nothing, and the alleles
    could not be re-requested from the command that stated them (RM71). Scoping to the file's current
    placeholder rows keeps both: refused rows were never written, settled rows no longer carry the
    stub, and the answer survives the run that produced it.

    **A record whose alleles the source did not state gets no line, and the caller counts it.** That
    is `_publishes_alleles`, shared rather than repeated, because a row silently absent from a
    worklist is the same defect as a row wrongly in one.

    **A pair is the wrong instruction on a contig that cannot host one.** Where the ploidy is
    undecidable rather than diploid — chrY on a build with no pseudoautosomal table — the author still
    has the decision, but "an allele pair from {A, G}" tells them to make it wrongly if the locus turns
    out to be hemizygous. Those rows say what is actually open. (A locus where only one genotype is
    expressible does not reach here at all: `sole_expressible_genotype` wrote it.)
    """
    lines: list[str] = []
    for record in records:
        if not _publishes_alleles(record):
            continue
        ref, alt = (record.get("ref") or "").strip(), (record.get("alt") or "").strip()
        chrom = normalize_chrom(str(record.get("chrom") or ""))
        if chrom == "Y":
            lines.append(
                f"  genotype for {_label(record)}: ClinVar publishes {ref}>{alt} — chrY, so a single "
                f"allele ('{alt}') outside the pseudoautosomal regions and a pair inside them; this "
                f"build has no PAR table, so which one is yours to establish"
            )
            continue
        alleles = ", ".join(sorted({ref, alt}))
        lines.append(
            f"  genotype for {_label(record)}: ClinVar publishes {ref}>{alt} — "
            f"an allele pair from {{{alleles}}}"
        )
    return lines


def _row_cells(record: dict, *, force_coordinate: bool = False) -> dict | None:
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
    # The one cell this provider *can* decide where the contig leaves no zygosity open. See
    # `sole_expressible_genotype`: it returns None wherever a human still has a call to make.
    genotype = sole_expressible_genotype(record)
    if genotype is not None:
        cells["genotype"] = genotype
    state = _STATE_BY_CLIN_SIG.get(clin_sig or "")
    if state is not None:
        cells["state"] = state
    # The 0.3 booleans stay authoritative and are folded from the same call, never independently.
    if clin_sig in ("pathogenic", "likely_pathogenic"):
        cells["pathogenic"] = True
    elif clin_sig in ("benign", "likely_benign"):
        cells["benign"] = True
    return cells


def _superseded_rsid_rows(path: Path, ambiguous: set[str]) -> list[str]:
    """Rsid-only rows already in the file whose rsID this run writes with a full coordinate.

    **A re-draft is additive, so it repairs S41's omission and cannot retract S41's collapse (S45).**
    A module drafted before the predicate was widened holds one rsid-only row where two records
    belonged; re-running the fixed drafter adds both coordinate-keyed rows and leaves that row in
    place, because drafting appends and never mutates. The module then states the right answer *and*
    the wrong one for the same locus — and the wrong one is the row carrying the mislabelled
    expansion, since resolution pairs its authored genotype with every locus the rsID resolves to.

    Nothing in the file distinguishes them: `_row_cells` writes no `rsid` on a coordinate-identity
    row, so "an rsid-only row whose rsID also appears on a coordinate row" finds **0 of 31** on the
    reporter's `MLH1` measurement, reproduced here. What *can* see it is this pass, which holds
    `ambiguous` — the set of rsIDs it is deliberately not writing by rsID this run. An rsid-only row
    carrying one of those is a row no current draft would produce.

    **Reported, never removed**, and that is the reporter's own preference for the reason they give:
    a drafted row is authored material by the time a re-draft runs, a human may have curated its
    `genotype`, `state` and `conclusion`, and deleting curated work to repair a drafting defect is a
    trade only the author can make. The rule one file over is the same — drafting appends, it never
    mutates — so a provider that started deleting rows would be the exception to it.
    """
    if not ambiguous or not path.is_file():
        return []
    stale: list[str] = []
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rsid = (row.get("rsid") or "").strip()
            if not rsid or rsid not in ambiguous:
                continue
            # An authored row that carries both is not the shape this is about: it identifies by
            # coordinate already, and the rsID beside it is descriptive.
            if (row.get("chrom") or "").strip():
                continue
            stale.append(rsid)
    if not stale:
        return []
    return [
        f"{len(stale)} row(s) already in {path.name} identify by rsID alone "
        f"({examples(sorted(set(stale)))}) — but this run writes those rsIDs with their full "
        f"coordinate, because each names more than one allele here. They were most likely drafted "
        f"before that check was widened (0.6.3), when two ClinVar records collapsed onto one such "
        f"row. This run has ADDED the coordinate-keyed rows beside them and has removed nothing: "
        f"drafting never deletes an authored row, and yours may have been curated since. Review "
        f"each and delete it once its records are covered by the coordinate rows — until then the "
        f"module carries both the row and its replacements."
    ]


#: How many of a variant's ClinVar-linked papers to draft. `rs1800562` alone carries 84 — a panel
#: does not need them all, and an author drowning in study rows will not read any. Capped rather than
#: sampled, and the number dropped is always reported: a silent cap reads as "this is everything".
DEFAULT_MAX_CITATIONS = 3


def _study_rows(
    records: Sequence[dict],
    links: dict[str, list[str]],
    limit: int,
    coordinate_only: set[str],
) -> tuple[list[StudyRow], int, int]:
    """ClinVar's own literature links → `studies.csv` rows, deduplicated per (variant, pmid).

    These are **real** rows, not partial ones: `StudyRow` needs a PMID and an identifier, and ClinVar
    supplies both. That is the difference from `variants.csv`, where the missing piece — zygosity —
    is a judgement rather than a datum.

    **A citation the model refuses is skipped and counted, never raised.** ClinVar files a few
    hundred ids under `PubMed` that are not PMIDs (nine digits, where PubMed is at eight), so
    `StudyRow` rightly refuses them — and one such record in one gene used to abort a 297-gene panel
    with an unhandled `ValidationError`, which is the drafting equivalent of a whole run lost to a
    single bad row. The builder now drops them at the snapshot boundary, but every snapshot already
    published carries them, so the drafter must survive one too. Returns the counts so the caller can
    report both reasons apart: a citation over the `--max-citations` cap is a choice, an unusable one
    is a defect in the source.
    """
    rows: list[StudyRow] = []
    seen: set[tuple] = set()
    dropped = 0
    unusable = 0
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
            try:
                rows.append(StudyRow(rsid=rsid, pmid=pmid, **coordinate))
            except ValidationError:
                unusable += 1
        dropped += max(0, len(pmids) - limit)
    return rows, dropped, unusable


def _resolve_snapshot(
    snapshot: Path | None, *, offline: bool, download: bool
) -> tuple[Path, list[str]]:
    """Find a ClinVar snapshot to draft from, provisioning the published one if there is none.

    The ladder `enrich()` already uses — explicit path → the cache locations → HuggingFace — so an
    author does not have to build 4.4M records from a 200 MB VCF before they can draft a panel. An
    explicit `snapshot` is taken as given and never second-guessed (it is the inject-only escape hatch,
    and it is what a test or an air-gapped run passes).

    Returns `(reference, warnings)`; raises `ClinVarDraftError` when there is nothing to read, because
    drafting from no snapshot is not a degraded result, it is no result.
    """
    if snapshot is not None:
        return Path(snapshot), []
    warnings: list[str] = []
    reference = resolve_clinvar_reference()
    if reference is None and not offline and download:
        try:
            reference = ensure_clinvar_snapshot()
        except Exception as exc:
            warnings.append(
                f"could not provision the published ClinVar snapshot ({exc}); pass --snapshot with a "
                f"locally built one, or build it with `just-dna-enricher clinvar build`."
            )
    if reference is None:
        # Name the switch that actually stopped it, or none. `--offline` and `--no-download` both
        # close this path and the older message named only the first, so an author who passed the
        # second was told to drop a flag they had not used — and after a *failed* provisioning
        # attempt, where neither is set, it named a flag nobody could drop.
        blocked = "--offline" if offline else ("--no-download" if not download else "")
        raise ClinVarDraftError(
            "no ClinVar snapshot found. "
            + (f"Drop {blocked} to download the published one, or pass " if blocked else "Pass ")
            + "--snapshot PATH, or build it yourself with `just-dna-enricher clinvar build "
            "--download`."
            + (f" ({warnings[0]})" if warnings else "")
        )
    return Path(reference), warnings


def draft_gene_panel(
    spec_dir: Path,
    genes: Sequence[str],
    *,
    snapshot: Path | None = None,
    clin_sig: frozenset[str] = DEFAULT_CLIN_SIG,
    min_review_stars: int = 2,
    max_citations: int = DEFAULT_MAX_CITATIONS,
    declared_use: str = "unstated",
    offline: bool = False,
    download: bool = True,
    dry_run: bool = False,
) -> ClinVarDraftResult:
    """Draft `variants.csv` rows for one or more genes, leaving `genotype` for the human.

    Re-runnable and additive: run it per gene as a panel grows. A variant already in the file — stub
    or filled — is reported, never re-added, because a partial row keys on the identity columns rather
    than on a key that runs through the placeholder.

    `min_review_stars` defaults to 2 (multiple submitters, no conflicts). A panel that silently mixes
    a 0-star "no assertion criteria" submission with a 3-star expert-panel review is worse than one
    that says which floor it drew from, and the floor belongs in the author's hands.

    **The snapshot is found, then provisioned — it used to be a required argument.** `snapshot=None`
    resolves the usual cache ladder and, unless `offline`, downloads the published one
    (`download.ensure_clinvar_snapshot`), the same shape `enrich()` and the gene-metrics pass use. Before
    this, the published snapshot could not reach an author: they had to build 4.4M records from a 200 MB
    VCF themselves, or already know the cache path. That matters most for the *citations*, which are what
    make a drafted panel compilable at all (`studies.csv` is mandatory and the VCF carries no PMIDs) and
    which now travel with the published snapshot.
    """
    skip_reason = check_declared_use(CLINVAR_TERMS, declared_use)
    if skip_reason:
        return ClinVarDraftResult(warnings=[skip_reason], skipped=True)

    # **Before the snapshot, not after it** (R2-2). `source_build_mismatch` raises `EnrichmentError`
    # on a present-but-unreadable `module_spec.yaml` — correctly, since a module whose declaration
    # cannot be read has no build to draft against — and asking it below meant a spec carrying only
    # `name:` failed *after* `_resolve_snapshot` had provisioned a published snapshot. It reads one
    # file beside the spec, so it costs nothing here. The warning is still appended in its old place.
    build_warning = source_build_mismatch(spec_dir, "the ClinVar snapshot", CLINVAR_GENOME_BUILD)

    reference, provisioning_warnings = _resolve_snapshot(snapshot, offline=offline, download=download)
    records = select_by_gene(
        reference, list(genes), clin_sig=clin_sig, min_review_stars=min_review_stars
    )
    warnings: list[str] = list(provisioning_warnings)
    # The snapshot is built from NCBI's `vcf_GRCh38/clinvar.vcf.gz`, and `_row_cells` writes the full
    # coordinate for any record this pass cannot key by rsID — so a module on another build is about
    # to record GRCh38 positions under its own declaration. See `enrich.source_build_mismatch`;
    # computed above, before the snapshot is resolved.
    if build_warning:
        warnings.append(build_warning)
    partials: list[PartialRow] = []
    unkeyable = 0
    ambiguous = multi_allelic_rsids(records)
    if ambiguous:
        # The list used to be printed whole, which was right at the one rsID that motivated it and is
        # not at the 1,589 a real cancer panel produces (S41 widened the predicate). `examples` is the
        # house aggregation, shared so this cannot drift from the other callers'.
        warnings.append(
            f"{len(ambiguous)} rsID(s) name more than one allele here "
            f"({examples(sorted(ambiguous))}) — written with their full coordinate, since an rsID "
            f"alone cannot say which allele the row is about."
        )
    record_by_signature: dict[tuple[str, ...], dict] = {}
    # signature -> the columns this run left for a human, so the reports below read the *decision*
    # `PartialRow` was given rather than restating which columns a stub can land in.
    stubbed_by_signature: dict[tuple[str, ...], tuple[str, ...]] = {}
    for record in records:
        cells = _row_cells(record, force_coordinate=(record.get("rsid") or "").strip() in ambiguous)
        if cells is None:
            unkeyable += 1
            continue
        # `state` is required and has no honest value for an undecided clinical call, so it is stubbed
        # for the same reason `genotype` usually is: the source did not say, and only a human can. See
        # `_STATE_BY_CLIN_SIG` — `VALID_STATES` offers no "uncertain" member, and every candidate
        # asserts something ClinVar declined to (`neutral` says benign, `risk` says a direction).
        # Skipping the row instead would throw away the conclusion, phenotype, clin_sig and citations
        # already assembled for it.
        #
        # Derived from the cells rather than listed: `_row_cells` decides what it can state, and a
        # column it filled is not a column to stub. A row on a haploid contig therefore arrives
        # complete (`stubbed=()`), which `PartialRow` handles as the degenerate case — it validates
        # every cell and matches on the same identity columns.
        stubbed = tuple(column for column in ("genotype", "state") if column not in cells)
        signature = _signature(cells)
        record_by_signature[signature] = record
        stubbed_by_signature[signature] = stubbed
        partials.append(
            PartialRow(
                model=VariantRow,
                cells=cells,
                stubbed=stubbed,
                # Identity, not the natural key: the key runs through `genotype`, which is the stub.
                # Matching here means "this variant is already in the panel, however it was written".
                # `alts` is in the set because without it two rows of a multi-allelic site collapse
                # into one and a real allele is lost — which is exactly what drafting HFE did.
                match_on=_MATCH_ON,
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
    warnings.extend(_superseded_rsid_rows(report.path, ambiguous))

    # Grounding evidence, from ClinVar's own literature links. Without this a drafted panel could not
    # compile at all — `studies.csv` is mandatory and the VCF carries no PMIDs — so the provider
    # produced a module that needed evidence nobody could supply. Build it with `clinvar citations`.
    links = citations_for(reference, [str(r.get("variation_id") or "") for r in records])
    if not links:
        warnings.append(
            "no citations table in the snapshot, so no studies.csv rows were drafted — grounding "
            "evidence is mandatory, so add it by hand, or run `just-dna-enricher clinvar citations` "
            "(a published snapshot now carries the table, so re-provisioning an empty cache also gets it)."
        )
    else:
        studies, dropped, unusable = _study_rows(records, links, max_citations, ambiguous)
        if studies:
            reports.append(
                append_rows(spec_dir, "studies.csv", studies, group_by=("rsid",), dry_run=dry_run)
            )
        if dropped:
            warnings.append(
                f"{dropped} further ClinVar citation(s) not drafted (--max-citations {max_citations})."
            )
        # Kept apart from the cap above: one is a choice this run made, the other is ClinVar filing a
        # non-PMID under PubMed. Reporting them together would read as "you asked for fewer".
        if unusable:
            warnings.append(
                f"{unusable} ClinVar citation(s) skipped: the id ClinVar filed under PubMed is not a "
                f"PMID (nine digits, where PubMed is at eight). Rebuilding the snapshot with a current "
                f"`clinvar citations` drops them at the source."
            )
    warnings.extend(_refusal_summary(report.invalid))

    # ── What is still open, scoped to the FILE rather than to this run (RM71) ────────────────────
    #
    # Both stub reports below hang off `_open_stubs`, so a re-run of the command answers the question
    # it answered the first time and `--dry-run` answers it without appending. They have to move
    # together: the `state` line reads as "these rows *also*", so a file-wide genotype denominator
    # beside a run-scoped `state` one would name two different sets in consecutive lines.
    genotype_stubs = _open_stubs(report, "genotype", stubbed_by_signature)
    if genotype_stubs:
        warnings.append(
            f"{len(genotype_stubs)} row(s) carry an unreplaced genotype placeholder and will not "
            f"compile until you decide the zygosity each finding is about."
        )
        warnings.extend(
            _genotype_worklist(
                [
                    record_by_signature[signature]
                    for signature, _ in genotype_stubs
                    if signature in record_by_signature
                ]
            )
        )
        # The rows this run cannot describe: drafted for another gene, or under a filter this run did
        # not use, so nothing here holds their alleles. Counted and their genes named — an unknown is
        # withheld, never guessed, and never silently dropped from a count the file can see.
        withheld = [
            (row or {}).get("gene") or ""
            for signature, row in genotype_stubs
            if signature not in record_by_signature
            or not _publishes_alleles(record_by_signature[signature])
        ]
        if withheld:
            genes = examples(sorted({gene.strip() for gene in withheld if gene.strip()}))
            # States what it knows and stops. It does NOT say *why* this run holds no record — the
            # usual reason is another gene or a tighter --clin-sig/--min-review-stars, but a record
            # that publishes no alleles lands here too, and naming a cause the pass did not establish
            # would be a guess dressed as a finding.
            warnings.append(
                f"{len(withheld)} row(s) of that list carry alleles this run cannot state, because "
                f"nothing it selected covers them "
                f"(gene: {genes or 'none recorded'}). The alleles are withheld rather than guessed: "
                f"draft-panel for the gene each row records, or `hint variant`, will state them."
            )

    # One line per clinical CALL, not per row: which call carries no direction is the thing the author
    # needs to know, and the answer is identical for every row carrying it.
    #
    # The record wins over the authored row for the *label*, so this list and the worklist above name
    # the same row the same way. They diverge otherwise: a row written by coordinate because its rsID
    # names several alleles carries no `rsid` cell, so the file would call it `16:23603601` while the
    # worklist two lines up calls it `rs118203998`, and the author could not cross-reference the two.
    by_call: dict[str, list[str]] = {}
    for signature, row in _open_stubs(report, "state", stubbed_by_signature):
        source = record_by_signature.get(signature) or row or {}
        by_call.setdefault(
            (source.get("clin_sig") or "").strip() or "no call", []
        ).append(_label(source))
    for call, labels in sorted(by_call.items()):
        shown = ", ".join(labels[:6]) + (f", … and {len(labels) - 6} more" if len(labels) > 6 else "")
        warnings.append(
            f"{len(labels)} row(s) also carry a `state` placeholder, all with clin_sig={call!r}: "
            f"ClinVar states no direction for that call, and VALID_STATES has no member meaning "
            f"'undecided' — `neutral` would assert the variant is benign, `risk` would assert a "
            f"direction the submitters did not. So `state` is yours to decide too, per row. "
            f"Affected: {shown}."
        )

    # The non-diploid notice stays scoped to what this run WROTE, deliberately: it reports a reading
    # the provider committed to on rows it just filled, not work anybody has left to do. One line, not
    # one per row — at panel scale this is hundreds of loci and the reading is identical for all.
    written_records = [
        record_by_signature[o.key]
        for o in report.added
        if o.key in record_by_signature and "genotype" not in stubbed_by_signature.get(o.key, ())
    ]
    if written_records:
        contigs = ", ".join(
            sorted({normalize_chrom(str(r.get("chrom") or "")) for r in written_records})
        )
        warnings.append(
            f"{len(written_records)} row(s) on non-diploid contigs ({contigs}) were written with "
            f"a single-allele genotype: exactly one is expressible there, so no zygosity decision "
            f"was pre-empted. They read as homoplasmic/hemizygous — a heteroplasmic level is a "
            f"different question and belongs in heteroplasmy.csv."
        )
    # WHICH release the rows were copied out of, in the column that exists to say so (RM4). The draft
    # was machined, so the marker is machined too: `clinical.tautology_reason` reads this back and can
    # then skip a check that a drafted module makes structurally unfailable, without the author having
    # to maintain a `panel:` block by hand for the sole benefit of one check. A snapshot that cannot
    # state its release leaves the cell empty rather than carrying a guess — and says so, because the
    # consequence is invisible otherwise.
    dataset = clinvar_dataset_label(reference)
    if dataset is None:
        warnings.append(
            "this snapshot does not say which ClinVar release it carries (no readable release.json), "
            "so the licence row records no dataset: nothing downstream can tell these rows were copied "
            "out of it, and the clin_sig cross-check will compare every one of them against it in full. "
            "That is the conservative outcome rather than a defect in the module. Build the snapshot "
            "with `just-dna-enricher clinvar build`, which writes the release.json this reads."
        )
    if not dry_run:
        # A source that rows were copied out of must be recorded, permissive terms or not: the compile
        # gate and `manifest.sources` read the licence table and nothing else.
        merge_sources_file(
            [CLINVAR_TERMS.row("annotation", declared_use=declared_use, dataset=dataset)],
            spec_dir,
            error=ClinVarDraftError,
        )
        # Widening a panel from a NEWER snapshot leaves the row naming the older release, because the
        # merge above is never-clobber (a curator's terms must survive a re-run). For `dataset` that
        # protection produces a false claim, so the stale label is withdrawn — never re-labelled: the
        # module now carries rows from two releases and one column cannot name both. Gated on rows
        # actually being added, since a re-draft that added none changed nothing to be honest about.
        # What the release label cannot see: which of these rows a human has edited since (RM73).
        # `merge_sources_file` is never-clobber, so the digest has to be restamped explicitly or a
        # second draft's would be silently dropped — see `stamp_draft_digest`. Unconditional: a run
        # that appended nothing leaves the projection unchanged, so this is then a no-op.
        stamp_draft_digest(spec_dir, CLINVAR_TERMS.source, "annotation", error=ClinVarDraftError)
        if report.added:
            superseded = withdraw_stale_dataset(
                spec_dir, CLINVAR_TERMS.source, "annotation", dataset, error=ClinVarDraftError
            )
            if superseded is not None:
                warnings.append(
                    f"this module already recorded rows drafted from {superseded}, and these came from "
                    f"{dataset or 'a snapshot that does not state its release'} — so the licence row's "
                    f"dataset has been cleared rather than re-labelled: it cannot name two releases, "
                    f"and naming one would be a claim about rows that did not come from it. The "
                    f"consequence is that the clin_sig cross-check now runs over the whole table again."
                )
    return ClinVarDraftResult(reports=reports, warnings=warnings)
