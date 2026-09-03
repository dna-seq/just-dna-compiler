"""RM160 — the citations a CIViC variant carries that no dated file can reach, and the canary on them.

`civic build` reads a dated bulk release; RM169 widened that as far as a dated file can go. The one
thing left over is structural: the wider basis comes from a VCF, a VCF record needs a POS, and CIViC
publishes no GRCh37 coordinate for a variant it names as a class of event or as a legacy notation. So
the submitted evidence attached to those variants is published on exactly one surface, the GraphQL
API, and ten records' citations are unreachable from every file the builder reads. Variant 1955 is the
worked case: its only evidence for the numbering convention that would settle its identity is EID
9969 (PMID 12202531, free full text), submitted, in the API and in no file.

**What lands, and where.** A recovered citation is a `studies.csv` row — the authored table that holds
an `(rsid, pmid)` evidence link — and nothing writes `literature.csv` here. That is the pairing the
format already has: `literature.csv` is the *derived* article table, produced by the `literature` pass
from the PMIDs `studies.csv` names, and an article row nothing cites is dropped from the artifact
(`@uncited-literature-dropped`). Writing one here would either duplicate that pass or add a row the
compiler discards; drafting the citing row and letting `literature` fill the article is the shape that
works in both directions.

**Three ways a module row reaches a CIViC variant id, and the third exists because the first two miss
the motivating class.** The snapshot's own coordinate join is the ordinary route, through
`clinical.comparison_plan` so this lane asks about the same alleles the other CIViC leg does. The
curated name-identity table (`civic_identities`) is how a variant whose identity CIViC publishes only
inside its `name` is reachable at all. Neither reaches variant 1955 — it is one of the two records the
identity round could **not** resolve, which is why its citations mattered in the first place — so
`--variant-id` asks about a variant id directly and writes a **module-level** citation row, which
`StudyRow` has permitted since RM47: a row may name no variant and ground the module instead.

**`status` rides as `confidence`/`confidence_unit`, unconverted.** CIViC's own instrument named rather
than translated into a house grade, so an accepted row and a submitted row are not the same row once
both are in the file. Where several evidence items cite one paper and their statuses disagree, the
confidence is **withheld** rather than picked: the value is unknown, and unknown is never written down
as an answer.

**Rejected evidence is not drafted.** `status: ALL` returns items CIViC's editors threw out, and a
citation whose every item is rejected is content the source itself has repudiated — counted with its
own reason, never silently dropped, and never written into a module as though the source stood behind
it. Where a rejected item sits beside a live one for the same paper, the live ones decide the row.

**The pin, and why it is on the `SourceRow`.** Every drafted row records when the API was asked and on
what basis — `fetched_at` and `dataset` on the `(civic, literature)` row — rather than restating a
timestamp inside each `conclusion`. A prose timestamp would put the moment of the read into
`content_signature`, and a moment is not a claim about a variant. The pin records the ask that first
put a recovered citation into this module: `merge_sources_csv` is never-clobber by design, so a later
run adding more rows does not move it. That is a floor on *not asked since*, and
`check_evidence_status_currency` below is what closes the gap — it re-asks and reports what moved.

**The canary never gates.** A source re-curating its own evidence is not an authoring error
(`@a-source-recuring-is-not-a-strict-matter`), so both findings warn in both modes. It is also a
different question from `dataset_currency`, which asks which *release* a table came from; this one
asks whether a per-item judgement has moved, and the two currency findings stay apart.
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import _restamp_for_build, load_csv_rows
from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import StudyRow, VariantRow

from just_dna_enricher.civic_api import (
    CIVIC_STATUS_UNIT,
    CivicApiClient,
    CivicApiError,
    CivicApiUnavailable,
    CivicEvidenceItem,
)
from just_dna_enricher.civic_identities import CIVIC_NAME_IDENTITIES
from just_dna_enricher.civic_refutation import civic_snapshot_rows
from just_dna_enricher.clinical import comparison_plan
from just_dna_enricher.licensing import CIVIC_TERMS, merge_sources_file, sidecar_path

logger = logging.getLogger(__name__)


class CivicCitationsError(RuntimeError):
    """This lane could not do its job — an unreadable licence table, a spec it cannot write into.

    Its own type rather than the client's: a caller of the pass is told to catch this, and letting
    `CivicApiError` out would make an outage and a broken module indistinguishable at the handler
    (`@client-exception-contract`). The API's own failures never reach here — they are recorded per
    subject as `unreachable`, which is the withhold rather than a raise.
    """


#: The layer a recovered citation contributes to. **`literature`, not `annotation`, and not a new
#: source name.** `(civic, annotation)` is `civic_draft`'s slot and a second surface may not claim it
#: (`@write-the-sourcerow`); a `civic_api` source would publish a *route* as a licensed body, which is
#: the overloading `@source-vs-authority` fixed in `gene_metrics.csv`. `literature` is what this pass
#: really supplies and is one of the two layers the compiler's orphan check exempts, so a module that
#: carries `studies.csv` rows does not warn `source_row_unused` for it.
CIVIC_CITATION_LAYER = "literature"

#: What `SourceRow.dataset` records for a row drafted off the API. The API publishes no release to
#: name, so the label names the **surface and the filter** instead — which is the honest answer, and
#: it keeps `dataset_currency` on `unsupported` rather than comparing a basis label against a date
#: (`@currency-asks-the-source-not-the-cache`).
CIVIC_API_DATASET = "civic_api:status=ALL"

#: How a module row reached a CIViC variant id. Closed (Principle 6), and the three are not
#: interchangeable: the first is the snapshot speaking, the second is a curated answer to a *name*,
#: and the third is an operator naming an id this workspace could not reach either way.
VALID_CIVIC_CITATION_ROUTES: frozenset[str] = frozenset(
    {"snapshot_coordinate", "curated_name_identity", "requested"}
)

#: Why a citation CIViC published was not drafted. Counted per reason rather than warned per row, the
#: aggregation rule this tier applies everywhere, and each one is cleared by a different thing.
CIVIC_CITATION_WITHHELD_REASONS: tuple[str, ...] = (
    # The evidence item's source is an ASCO/ASH abstract or another non-PubMed record: its
    # `citationId` is a real identifier in a namespace `pmid` is not (`@pmid-vs-pmcid`).
    "not_a_pubmed_source",
    # Every item citing this paper was rejected by CIViC's editors. The source repudiated it.
    "rejected_by_source",
)

#: One code per sentence, naming the finding rather than the emission site
#: (`@warning-code-names-the-finding`). **Deliberately not members of `VALID_WARNING_CODES`**: that
#: vocabulary is the *compiler's*, and its guard asserts every member is a code some compiler check
#: builds — an enricher finding reaches a compile through the attestation and is restated there.
#: `civic_refutation` carries the same pair of constants for the same reason.
CIVIC_STATUS_MOVED: str = "civic_evidence_status_moved"
CIVIC_CITATION_ADDED: str = "civic_citation_added"

#: The identity columns a recovered citation is matched on. **One constant tuple for the whole batch**
#: — `append_partial_rows` builds its covered-set from the first partial's `match_on` and compares
#: every signature against it, so a batch mixing arities re-adds its rows every lap
#: (`@match-on-is-per-batch`). A module-level row compares as four empty cells plus its PMID, which is
#: exactly right: two module-level rows citing one paper are one citation.
_MATCH_ON: tuple[str, ...] = ("rsid", "chrom", "start", "ref", "pmid")


@dataclass(frozen=True)
class CivicSubject:
    """One CIViC variant this run can ask about, and the module row it was reached from.

    The identity cells are the *authored* row's, not the snapshot's: they are what the drafted
    citation carries, so a re-run matches on the same signature and appends nothing. A `requested`
    subject carries none of them — it grounds the module rather than a variant.
    """

    variant_id: int
    route: str
    rsid: str | None = None
    chrom: str | None = None
    start: int | None = None
    ref: str | None = None
    civic_name: str | None = None

    @property
    def signature(self) -> tuple[str, str, str, str]:
        """The four identity cells as the drafted row spells them — the canary's join key too."""
        return (
            (self.rsid or "").strip(),
            (self.chrom or "").strip(),
            "" if self.start is None else str(self.start),
            (self.ref or "").strip(),
        )

    def restate(self) -> str:
        """`CIViC variant 1955 (VHL P71fs (c.211insT))` — what a line puts in front of an author."""
        return f"CIViC variant {self.variant_id}" + (
            f" ({self.civic_name})" if self.civic_name else ""
        )


@dataclass
class CivicCitationsResult:
    """What one `civic citations` run asked, drafted and withheld."""

    #: CIViC variants this run put a question about.
    subjects: list[CivicSubject] = field(default_factory=list)
    #: Authored rows that resolved to a locus no route mapped onto a CIViC variant. Asked of the
    #: module, answered by nothing — not the same as a variant CIViC has no evidence for.
    unmapped_rows: int = 0
    #: Subjects the API could not be asked about, with the reason. Never folded into "nothing found".
    unreachable: dict[int, str] = field(default_factory=dict)
    #: Distinct PubMed citations the API returned across every subject.
    citations_seen: int = 0
    withheld: dict[str, int] = field(default_factory=dict)
    #: Rows drafted with the confidence cell empty because the live items disagreed about the status.
    confidence_withheld: int = 0
    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sources: list[SourceRow] = field(default_factory=list)
    offline: bool = False

    @property
    def added(self) -> int:
        return sum(len(report.added) for report in self.reports)

    @property
    def asked(self) -> int:
        """Subjects the API really answered about — the denominator any count here is out of."""
        return len([s for s in self.subjects if s.variant_id not in self.unreachable])


# ── mapping a module onto CIViC variant ids ─────────────────────────────────────────────────────


def read_module(
    spec_dir: Path, *, genome_build: str
) -> tuple[list[VariantRow], list[ResolutionRow]]:
    """The two authored/injected tables this lane joins on, loaded the way every other reader does.

    **The build re-stamp is not optional** (`@restamp-for-build`). `VariantRow._freeze_identity` runs
    at construction, where the module's yaml is not in scope, so every row comes back keyed for
    GRCh38; the compiler fixes that after load at both of its sites and `enrich` at its own. A reader
    that skipped it would join a GRCh37 module's rows against a table keyed differently and silently
    match nothing.

    `genome_build` is the caller's, not this function's: `enrich` already holds the module's declared
    build and the CLI reads it with `enrich.spec_genome_build`, and importing that here would make the
    two modules import each other.

    A missing table is an empty list rather than an error: a module with no `resolution.csv` has
    nothing this lane can place, which the caller reports as a subject it could not map.
    """
    spec_dir = Path(spec_dir)
    variants: list[VariantRow] = []
    variants_path = spec_dir / "variants.csv"
    if variants_path.exists():
        variants, errors, _ = load_csv_rows(variants_path, VariantRow, "variants.csv")
        if errors:
            raise CivicCitationsError(f"variants.csv is invalid: {errors[0]}")
        _restamp_for_build(variants, genome_build)
    resolution: list[ResolutionRow] = []
    resolution_path = sidecar_path(spec_dir, "resolution.csv", error=CivicCitationsError)
    if resolution_path.exists():
        resolution, errors, _ = load_csv_rows(resolution_path, ResolutionRow, resolution_path.name)
        if errors:
            raise CivicCitationsError(f"existing {resolution_path.name} is invalid: {errors[0]}")
    return variants, resolution


def read_studies(spec_dir: Path) -> list[StudyRow]:
    """The module's citation table, or `[]` when it carries none — and never fatal.

    A table that will not parse is logged and read as empty rather than raised, because the one caller
    is a **read-only check** folded into a pass that has other work to do: `enrich` would otherwise
    start failing on a module whose `studies.csv` it never used to open, and the compiler is where an
    invalid authored table is diagnosed. `litvar._read_table` takes the same line for the same reason.
    """
    path = Path(spec_dir) / "studies.csv"
    if not path.exists():
        return []
    rows, errors, _ = load_csv_rows(path, StudyRow, "studies.csv")
    if errors:
        logger.warning(
            "studies.csv could not be read (%s), so no recorded CIViC citation was re-asked about; "
            "the compiler reports this table's own errors.", errors[0],
        )
        return []
    return rows



def _snapshot_variant_ids(reference: Path | None) -> dict[tuple[str, int, str, str], tuple[int, str | None]]:
    """`(chrom, start, ref, alt)` → `(civic variant id, name)` from a built snapshot.

    First-seen wins, so the mapping is deterministic in the snapshot's own row order (Principle 7).
    A snapshot row with no coordinate is unreachable from an authored one and is simply absent here.
    """
    out: dict[tuple[str, int, str, str], tuple[int, str | None]] = {}
    if reference is None:
        return out
    for row in civic_snapshot_rows(reference):
        chrom, start, ref, alt = row.get("chrom"), row.get("start"), row.get("ref"), row.get("alt")
        variant_id = row.get("variant_id")
        if chrom and start is not None and ref and alt and variant_id is not None:
            out.setdefault(
                (str(chrom), int(start), str(ref), str(alt)),
                (int(variant_id), row.get("variant_name")),
            )
    return out


def _curated_variant_ids() -> dict[tuple[str, int, str, str], tuple[int, str | None]]:
    """The same mapping from the curated name-identity table, which needs no snapshot at all.

    This is the route that exists *because* the snapshot cannot carry these rows: every identity in
    that table was read out of a CIViC variant's own `name`, for a record CIViC publishes no
    identifier for. Built from the shipped tuple rather than restated, so the two cannot drift.
    """
    return {
        (row.chrom, row.start, row.ref, row.alt): (row.variant_id, row.name)
        for row in CIVIC_NAME_IDENTITIES
    }


def plan_subjects(
    variants: Sequence[VariantRow],
    resolution_rows: Sequence[ResolutionRow],
    *,
    reference: Path | None,
    requested: Iterable[int] = (),
) -> tuple[list[CivicSubject], int]:
    """`(subjects, authored rows that mapped to no CIViC variant)`.

    Matching goes through `comparison_plan`, the same resolved-coordinate route the ClinVar
    cross-check and the CIViC refutation leg use, so every CIViC question in this tier is asked about
    the same alleles — never about an rsID, which is position-level and would ask about a locus rather
    than an allele.

    The snapshot is consulted first and the curated table second, because the snapshot is the source
    speaking for itself and the curated table is this workspace's reading of a name. A row matching
    both gets the snapshot's answer and the route says so.
    """
    from_snapshot = _snapshot_variant_ids(reference)
    curated = _curated_variant_ids()
    subjects: list[CivicSubject] = []
    seen: set[tuple[int, tuple[str, str, str, str]]] = set()
    unmapped = 0
    # Every authored row that resolves to a locus is a candidate: a citation is about the variant, not
    # about any one cell of it, so there is no authored column to cross-examine here.
    plan, _wanted, _no_alt = comparison_plan(
        list(variants), list(resolution_rows), authored=lambda variant: variant.variant_key
    )
    for entry in plan:
        matched = False
        for target in entry.targets:
            for route, mapping in (
                ("snapshot_coordinate", from_snapshot),
                ("curated_name_identity", curated),
            ):
                found = mapping.get(target)
                if found is None:
                    continue
                variant_id, name = found
                subject = CivicSubject(
                    variant_id=variant_id,
                    route=route,
                    rsid=entry.variant.rsid,
                    chrom=entry.variant.chrom,
                    start=entry.variant.start,
                    ref=entry.variant.ref,
                    civic_name=name,
                )
                key = (variant_id, subject.signature)
                if key not in seen:
                    seen.add(key)
                    subjects.append(subject)
                matched = True
                break
        if not matched:
            unmapped += 1
    for variant_id in requested:
        # An operator naming an id directly. It carries no identity cells, so its citations ground the
        # module — the shape `StudyRow` has permitted since RM47, and the only route that reaches a
        # variant neither the snapshot nor the curated table can place.
        subject = CivicSubject(variant_id=int(variant_id), route="requested")
        key = (subject.variant_id, subject.signature)
        if key not in seen:
            seen.add(key)
            subjects.append(subject)
    return subjects, unmapped


# ── drafting ────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecoveredCitation:
    """One PubMed citation a CIViC variant carries, and every live item behind it."""

    subject: CivicSubject
    pmid: str
    items: tuple[CivicEvidenceItem, ...]

    @property
    def status(self) -> str | None:
        """The one status every live item agrees on, or `None` when they do not.

        Withheld rather than resolved. Two items that disagree about whether an editor has signed this
        paper's evidence off state two facts, and picking one would publish a guess in a column whose
        whole purpose is to carry the source's own word.
        """
        statuses = {item.status for item in self.items}
        return statuses.pop() if len(statuses) == 1 else None

    def conclusion(self) -> str:
        """The prose beside the row. Deterministic, and deliberately carrying no timestamp.

        When the API was asked is on the `SourceRow`; putting it here would fold the moment of a read
        into `content_signature`, where only claims belong.
        """
        quoted = ", ".join(
            item.restate() for item in sorted(self.items, key=lambda i: i.evidence_id)
        )
        return (
            f"{self.subject.restate()}: {quoted}. Recovered from CIViC's GraphQL API, which "
            f"publishes evidence at every curation status; the dated bulk release does not carry it."
        )


def _citations(subject: CivicSubject, items: Sequence[CivicEvidenceItem]) -> tuple[
    list[RecoveredCitation], dict[str, int]
]:
    """Group one variant's items into citations, with what was withheld and why.

    Grouped by PMID because that is `studies.csv`'s grain — a `(variant_key, pmid)` pair is one row,
    and five evidence items citing one paper (CIViC 6418-6422 all cite PMID 17661816) are one
    citation with three items behind it, not three rows the compiler would then call duplicates.
    """
    withheld = dict.fromkeys(CIVIC_CITATION_WITHHELD_REASONS, 0)
    by_pmid: dict[str, list[CivicEvidenceItem]] = {}
    for item in items:
        pmid = item.pmid
        if pmid is None:
            withheld["not_a_pubmed_source"] += 1
            continue
        by_pmid.setdefault(pmid, []).append(item)
    citations: list[RecoveredCitation] = []
    for pmid, group in by_pmid.items():
        live = [item for item in group if item.status != "rejected"]
        if not live:
            withheld["rejected_by_source"] += 1
            continue
        citations.append(RecoveredCitation(subject, pmid, tuple(live)))
    return citations, withheld


def _study_partial(citation: RecoveredCitation) -> PartialRow:
    """One recovered citation as the authored cells this pass is willing to state.

    Nothing is stubbed: every cell here is a fact the source published, and the row is complete as it
    stands — a citation row grounds a claim, it does not make one, so there is no decision left for a
    human to fill in.
    """
    subject = citation.subject
    status = citation.status
    cells: dict[str, object] = {
        "rsid": subject.rsid,
        "chrom": subject.chrom,
        "start": subject.start,
        "ref": subject.ref,
        "pmid": citation.pmid,
        "conclusion": citation.conclusion(),
    }
    if status is not None:
        cells["confidence"] = status
        cells["confidence_unit"] = CIVIC_STATUS_UNIT
    return PartialRow(
        model=StudyRow,
        cells={k: v for k, v in cells.items() if v is not None},
        stubbed=(),
        match_on=_MATCH_ON,
    )


def draft_civic_citations(
    spec_dir: Path,
    *,
    variants: Sequence[VariantRow],
    resolution_rows: Sequence[ResolutionRow],
    reference: Path | None,
    requested: Iterable[int] = (),
    client: CivicApiClient | None = None,
    offline: bool = False,
    dry_run: bool = False,
) -> CivicCitationsResult:
    """Append the citations a CIViC variant carries and the local basis does not.

    One request per subject **by construction** — `evidenceItems` takes a single `variantId` — which
    is why this fits `enrich`-time tooling and would not fit `civic build`: a builder batching it
    would be one request per variant of the whole database, and its output could not be pinned to a
    dated release. Batching it into the builder is the first repair anyone proposes and it is the
    bargain RM160's shape 3 refused.

    `--offline` refuses rather than answering empty: every subject is recorded as unreachable with the
    `offline` reason, and no row is written. *Nobody asked* and *the source has nothing more* are
    different facts (`@unreachable-not-absent`).
    """
    spec_dir = Path(spec_dir)
    result = CivicCitationsResult(
        withheld=dict.fromkeys(CIVIC_CITATION_WITHHELD_REASONS, 0), offline=offline
    )
    subjects, unmapped = plan_subjects(
        variants, resolution_rows, reference=reference, requested=requested
    )
    result.subjects = subjects
    result.unmapped_rows = unmapped
    if not subjects:
        result.warnings.append(
            "No authored row maps onto a CIViC variant and no --variant-id was given, so CIViC's API "
            "was not asked. Build a snapshot with `just-dna-enricher civic build --release <date> "
            "--submitted`, or name the variant directly with --variant-id."
        )
        return result

    api = client if client is not None else CivicApiClient(offline=offline)
    partials: list[PartialRow] = []
    for subject in subjects:
        try:
            items = api.evidence_items(subject.variant_id)
        except CivicApiUnavailable as exc:
            # The question was never put. `offline` is the caller's own switch and is named as such,
            # because a re-run with egress clears one of these and not the other.
            result.unreachable[subject.variant_id] = "offline" if api.offline else "unreachable"
            logger.info("CIViC was not asked about variant %s (%s)", subject.variant_id, exc)
            continue
        except CivicApiError as exc:
            # CIViC answered with something this client cannot read. Still nobody-asked as far as this
            # variant's citations go, and it must not read as an absence.
            result.unreachable[subject.variant_id] = "unreadable"
            logger.warning("CIViC's answer for variant %s could not be read (%s)",
                           subject.variant_id, exc)
            continue
        citations, withheld = _citations(subject, items)
        for reason, count in withheld.items():
            result.withheld[reason] += count
        result.citations_seen += len(citations)
        for citation in citations:
            if citation.status is None:
                result.confidence_withheld += 1
                result.warnings.append(
                    f"{subject.restate()} PMID {citation.pmid}: CIViC states "
                    f"{sorted({i.status for i in citation.items})} for the items citing this paper, "
                    f"so the row was written with no confidence rather than with one of them."
                )
            partials.append(_study_partial(citation))

    if partials:
        result.reports.append(
            append_partial_rows(spec_dir, "studies.csv", partials, dry_run=dry_run)
        )
    if result.unreachable:
        result.warnings.append(
            f"{len(result.unreachable)} of {len(subjects)} subject(s) could not be asked "
            f"({sorted(set(result.unreachable.values()))}); their citations are unknown rather than "
            f"absent."
        )
    # A pass that consults a source writes its `SourceRow`; one that contributed nothing writes none
    # (`@write-the-sourcerow`), and the key is **what this run covered** — a run that appended no row
    # added no CIViC citation to this module, and any earlier run's row is already in the file. The
    # pin rides on this row rather than beside each drafted cell: `dataset` says on which basis, and
    # `fetched_at` says when.
    if result.added and not dry_run:
        result.sources = merge_sources_file(
            [
                CIVIC_TERMS.row(
                    CIVIC_CITATION_LAYER,
                    declared_use="unstated",
                    dataset=CIVIC_API_DATASET,
                )
            ],
            spec_dir,
            error=CivicCitationsError,
        )
    return result


# ── the canary ──────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MovedCitation:
    """One recorded citation whose answer at CIViC has moved since it was drafted."""

    code: str
    subject: CivicSubject
    pmid: str
    recorded: str | None
    current: str | None

    def restate(self) -> str:
        if self.code == CIVIC_CITATION_ADDED:
            return (
                f"{self.subject.restate()}: CIViC now carries PMID {self.pmid} "
                f"({self.current}) and this module has no row for it. Re-run "
                f"`civic citations` to append it."
            )
        return (
            f"{self.subject.restate()}: PMID {self.pmid} was recorded as {self.recorded!r} and "
            f"CIViC now says {self.current!r}. The row was not changed — a source re-curating is "
            f"not an authoring error — but the recorded status is no longer what CIViC states."
        )


@dataclass
class EvidenceStatusCheck:
    """What the canary compared, and what it found. Never a stand-in for a check that could not run.

    `skip` is the closed reason this run put no question, or `None` when it did. A dataclass with a
    reason rather than a bare `None` return, because there are four ways not to run here and they are
    cleared by four different things — a verdict with several arms owes a reason with the same arms
    (`@answered-is-not-absent`).
    """

    #: Citations this module records from CIViC's API — the population, before any of it is asked.
    recorded: int = 0
    #: Recorded citations that were re-asked and answered about.
    subjects: int = 0
    findings: list[MovedCitation] = field(default_factory=list)
    #: Rows carrying a CIViC status that this run could not map back to a CIViC variant id — a
    #: module-level row from `--variant-id`, or a module whose snapshot has gone. Named rather than
    #: counted as agreement: a citation nobody re-asked about has not been shown to still hold.
    not_re_askable: int = 0
    #: Subjects the API could not be asked about this run, with the reason.
    unreachable: dict[int, str] = field(default_factory=dict)
    skip: str | None = None

    def detail(self) -> str:
        """The sentence beside the machine key, on every run including the empty one."""
        if self.skip == "nothing_to_check":
            return (
                "this module records no citation drafted from CIViC's API, so there is no recorded "
                "curation status to re-ask about"
            )
        if self.skip == "offline":
            return (
                f"--offline, so none of the {self.recorded} recorded CIViC citation(s) was re-asked"
            )
        if self.skip == "no_reference":
            return (
                f"none of the {self.recorded} recorded CIViC citation(s) could be mapped back to a "
                f"CIViC variant id this run: no snapshot was provisioned, or the rows ground the "
                f"module rather than a variant. A citation nobody re-asked about is not one that "
                f"still holds"
            )
        if self.skip == "unreachable":
            return (
                f"CIViC did not answer for any of the {len(self.unreachable)} variant(s) this run "
                f"asked about, so nothing was compared"
            )
        moved = [f for f in self.findings if f.code == CIVIC_STATUS_MOVED]
        added = [f for f in self.findings if f.code == CIVIC_CITATION_ADDED]
        parts = [
            f"{self.subjects} recorded CIViC citation set(s) re-asked; {len(moved)} status(es) "
            f"moved, {len(added)} citation(s) added since"
        ]
        if self.not_re_askable:
            parts.append(f"{self.not_re_askable} row(s) could not be mapped back to a variant id")
        if self.unreachable:
            parts.append(f"{len(self.unreachable)} variant(s) could not be asked")
        return "; ".join(parts)


def recorded_civic_citations(studies: Sequence[StudyRow]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    """`identity signature` → `{pmid: recorded status}` for every row this lane wrote.

    Keyed on `confidence_unit`, which is the instrument name and therefore the only cell that says a
    status came from CIViC. A row whose confidence was withheld carries no unit and is not a subject:
    there is no recorded judgement to compare against, and inventing one would be the check answering
    its own question.
    """
    out: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in studies:
        if (row.confidence_unit or "") != CIVIC_STATUS_UNIT or not row.confidence:
            continue
        signature = (
            (row.rsid or "").strip(),
            (row.chrom or "").strip(),
            "" if row.start is None else str(row.start),
            (row.ref or "").strip(),
        )
        out.setdefault(signature, {})[row.pmid.strip()] = row.confidence.strip()
    return out


def check_evidence_status_currency(
    variants: Sequence[VariantRow],
    resolution_rows: Sequence[ResolutionRow],
    studies: Sequence[StudyRow],
    *,
    reference: Path | None,
    client: CivicApiClient | None = None,
    offline: bool = False,
) -> EvidenceStatusCheck:
    """Re-ask CIViC about the citations this module recorded from it, and report what has moved.

    Three moves, two codes. An item accepted since the draft and one rejected since are the same
    finding on the status axis with the same remedy — read what CIViC now says about a row already in
    the file — while a citation CIViC has added since is a different sentence with a different remedy,
    which is re-running `civic citations` (`@warning-code-names-the-finding`).

    Reports and repairs nothing (`@enrichment-is-validation`), and never escalates: a source
    re-curating its own evidence is a fact about CIViC, and rewriting an authored cell from a live read
    is the one thing an enricher pass may not do.

    A run that could not put the question says which of four reasons applies rather than reporting a
    comparison of zeros — a check that could not run is not a check that passed.
    """
    recorded = recorded_civic_citations(studies)
    check = EvidenceStatusCheck(recorded=len(recorded))
    if not recorded:
        check.skip = "nothing_to_check"
        return check
    if offline or (client is not None and client.offline):
        # The switch is read before any mapping work: an offline run has nothing to say about which
        # rows *would* have been re-askable, and pretending otherwise would answer a question the run
        # never put (`@unreachable-not-absent`).
        check.skip = "offline"
        return check
    subjects, _unmapped = plan_subjects(variants, resolution_rows, reference=reference)
    by_signature = {subject.signature: subject for subject in subjects}
    askable = {
        signature: by_signature[signature] for signature in recorded if signature in by_signature
    }
    check.not_re_askable = len(recorded) - len(askable)
    if not askable:
        check.skip = "no_reference"
        return check
    api = client if client is not None else CivicApiClient(offline=offline)
    for signature, subject in askable.items():
        try:
            items = api.evidence_items(subject.variant_id)
        except CivicApiUnavailable:
            check.unreachable[subject.variant_id] = "offline" if api.offline else "unreachable"
            continue
        except CivicApiError as exc:
            check.unreachable[subject.variant_id] = "unreadable"
            logger.warning("CIViC's answer for variant %s could not be read (%s)",
                           subject.variant_id, exc)
            continue
        check.subjects += 1
        citations, _withheld = _citations(subject, items)
        current = {citation.pmid: citation for citation in citations}
        held = recorded[signature]
        for pmid, was in held.items():
            citation = current.get(pmid)
            if citation is None:
                # Every item citing this paper is now rejected, or the item is gone. Reported on the
                # status axis rather than as a third code: the remedy is the same one, which is to
                # read what CIViC now says about a row this module already carries.
                check.findings.append(
                    MovedCitation(CIVIC_STATUS_MOVED, subject, pmid, was, "rejected or withdrawn")
                )
                continue
            if citation.status is not None and citation.status != was:
                check.findings.append(
                    MovedCitation(CIVIC_STATUS_MOVED, subject, pmid, was, citation.status)
                )
        for pmid, citation in current.items():
            if pmid not in held:
                check.findings.append(
                    MovedCitation(
                        CIVIC_CITATION_ADDED, subject, pmid, None, citation.status or "unstated"
                    )
                )
    if not check.subjects:
        check.skip = "unreachable"
    return check
