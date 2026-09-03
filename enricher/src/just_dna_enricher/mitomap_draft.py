"""Draft `variants.csv` + `studies.csv` rows from the MITOMAP-miss increment (RM171).

**Only the rated misses are written**, and each of the other three buckets is refused for its own
reason rather than filtered out silently:

* a **photocopy** is an allele ClinVar already publishes, and on the measured vintage every matched
  bracketed row carried `reviewed_by_expert_panel`. Drafting it would attribute the ClinGen mtDNA
  VCEP's call to the wrong publisher, and it would give a ClinVar concordance check a copy of ClinVar
  to disagree with — a check that cannot fail (`@tautology-zero`).
* an **unrated miss** is a real identity increment with no class this tier may map: no bracket at
  all, a bare confirmation token, or `[VUS*]`. Counted, and no class is invented for it.
* an **unmintable** row publishes no VCF-spellable allele. Counted, with the reason.

**`genotype` is stubbed, and the reason is not the one the contig would give.** ClinVar's drafter
fills the ALT on chrMT through `sole_expressible_genotype`, on the argument that a haploid contig
leaves no zygosity open — a correct argument about ClinVar, whose record is a claim about an allele.
It is not called here, because MITOMAP's row is a claim about a *literature corpus*: its `homo` and
`hetero` columns say the variant has been reported homoplasmic, heteroplasmic, or not recorded, and a
large share of these rows are reported only heteroplasmically. Writing `genotype=<ALT>` on one of
those states the homoplasmic reading — which is precisely the claim `reference_examples/mt_heteroplasmy`
keeps in `variants.csv` and separates from its `heteroplasmy.csv` bins. So the cell is left for the
author, and the flags MITOMAP *did* publish are put in front of them, per row, as the worklist.

`state` and `conclusion` are required too. `state` is folded from `clin_sig` through the shared
`STATE_BY_CLIN_SIG` wherever that fold exists and stubbed where it does not; `conclusion` is always
stubbed, because it is the sentence a reader is shown when a measurement lands here and MITOMAP
publishes a disease *name*, which is a different claim at a different grain.

**Appends, never mutates** (`@draft-appends`), matched on the coordinate identity — MITOMAP publishes
no rsID column at all, so there is no second identity for a row to arrive under.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import (
    DraftReport,
    PartialRow,
    append_partial_rows,
    append_rows,
)
from just_dna_format.spec import StudyRow, VariantRow
from pydantic import ValidationError

from just_dna_enricher.clin_sig import STATE_BY_CLIN_SIG
from just_dna_enricher.licensing import (
    MITOMAP_TERMS,
    check_declared_use,
    merge_sources_file,
    withdraw_stale_dataset,
)
from just_dna_enricher.locations import resolve_mitomap_miss_reference
from just_dna_enricher.mitomap import SOURCE_NAME, indefinite_length
from just_dna_enricher.mitomap_miss_build import (
    CITATIONS_PARQUET,
    CONTIG,
    MISS_PARQUET,
    miss_dataset_label,
    read_miss_release,
    stale_parents,
)
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)

VARIANTS_CSV = "variants.csv"
STUDIES_CSV = "studies.csv"

#: The `--source` member. Spelled with a hyphen because that is how the design note and every
#: operator writes it; the cache lane it reads is `mitomap_miss`, and `caches.lane_name` folds
#: between the two.
SOURCE_LABEL = "mitomap-miss"

#: What decides whether a drafted row is the row already in the table. **One tuple for the whole
#: batch** (`@match-on-is-per-batch`), and no `rsid` in it because MITOMAP publishes no rsID column —
#: an identity slot the source never fills is not part of this provider's key.
_MATCH_ON: tuple[str, ...] = ("chrom", "start", "ref", "alts")

#: The cells a human must write before the module can compile. `genotype` for the reason in the module
#: docstring; `conclusion` because MITOMAP publishes a disease name and not the sentence a reader is
#: shown. `state` is stubbed *per row*, only where the fold has no answer, so it is not in here.
_STUBBED: tuple[str, ...] = ("genotype", "conclusion")

@dataclass
class MitomapDraftResult:
    """What was drafted, and an account of every row in the increment that was not."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False
    #: Rows in the miss snapshot that passed the `--gene` filter — the denominator below.
    candidates: int = 0
    #: `reason -> count` for a row this provider would not write. Every candidate is either offered
    #: as a partial row or in here; `accounts_for_every_candidate` asserts it.
    withheld: dict[str, int] = field(default_factory=dict)
    #: `bracket -> count` over the *missing* rows whose only rating is one this tier will not map.
    #: Carried separately from `withheld` because it is the answer to a different question: not
    #: "why was nothing written" but "how much of the increment is undocumented rather than absent".
    withheld_brackets: dict[str, int] = field(default_factory=dict)
    #: Rated misses whose key is an indel, and the parents that have moved since the child was built.
    indel_keys: int = 0
    #: Drafted rows whose `allele` NAME states a variable-length event (`C(n)ins`) that the allele
    #: columns flatten to one definite pair. The source disagreeing with itself, reported not repaired.
    indefinite_alleles: list[str] = field(default_factory=list)
    stale: dict[str, tuple[dict, dict]] = field(default_factory=dict)
    dataset: str | None = None

    @property
    def added(self) -> int:
        return sum(len(report.added) for report in self.reports)

    def accounts_for_every_candidate(self) -> bool:
        offered = len(self.reports[0].outcomes) if self.reports else 0
        return offered + sum(self.withheld.values()) == self.candidates


class MitomapDraftError(RuntimeError):
    """A draft could not be attempted — no miss snapshot, or an unwritable spec directory."""


def _snapshot_rows(reference: Path, name: str) -> list[dict]:
    """One parquet of the miss snapshot as plain dicts, or `[]` when the snapshot has no such file.

    Neither polars nor pyarrow at module scope: a *reader* of a built snapshot must not drag the
    builder's `[dev]` extra in behind it. The increment is a thousand rows, so nothing is streamed.
    """
    parquet = reference / "data" / name if reference.is_dir() else reference
    if not parquet.exists():
        return []
    try:
        import polars as pl

        return pl.read_parquet(parquet).to_dicts()
    except ImportError:  # pragma: no cover - polars is present in this workspace's dev extra
        import pyarrow.parquet as pq

        return pq.read_table(parquet).to_pylist()


def _cells(row: dict) -> dict:
    """One rated-miss row → the authored cells this provider is willing to state.

    Identity as MITOMAP published it, the gene where `locus` names exactly one, the disease string
    verbatim as `phenotype`, and the VCEP class the bracket already carries. Everything interpretive —
    `weight`, `direction`, `priority`, `curator` — is left alone: those are the cells only a pilot
    settles, and a drafter filling them would be writing the module rather than starting it.
    """
    clin_sig = (row.get("clin_sig") or "").strip() or None
    cells: dict = {
        "chrom": CONTIG,
        "start": row.get("start"),
        "ref": row.get("ref"),
        "alts": row.get("alt"),
        "gene": (row.get("gene") or "").strip() or None,
        "phenotype": (row.get("disease") or "").strip() or None,
        "clin_sig": clin_sig,
    }
    state = STATE_BY_CLIN_SIG.get(clin_sig or "")
    if state is not None:
        cells["state"] = state
    # The 0.3 booleans are folded from the same call, never decided independently.
    if clin_sig in ("pathogenic", "likely_pathogenic"):
        cells["pathogenic"] = True
    elif clin_sig in ("benign", "likely_benign"):
        cells["benign"] = True
    return {name: value for name, value in cells.items() if value is not None}


def _study_rows(rows: Sequence[dict], citations: Sequence[dict]) -> tuple[list[StudyRow], int]:
    """MITOMAP's own citation links → `studies.csv` rows for the variants this run drafts.

    Real rows rather than partial ones: `StudyRow` needs a PMID and an identifier and MITOMAP supplies
    both, so nothing here is a judgement a human has to make. The identity is the **position**
    (`chrom`, `start`, `ref`) rather than the allele, which is the convention `clinvar_draft` follows
    and the compiler's orphan check expects — a study is evidence about a locus.

    A row the model refuses is counted, never raised: one unusable citation must not lose a run.
    """
    wanted = {(str(row["table"]), str(row["record_id"])) for row in rows}
    by_record: dict[tuple[str, str], list[str]] = {}
    for link in citations:
        key = (str(link.get("table")), str(link.get("record_id")))
        if key in wanted and link.get("pmid"):
            by_record.setdefault(key, []).append(str(link["pmid"]))
    out: list[StudyRow] = []
    seen: set[tuple] = set()
    unusable = 0
    for row in rows:
        for pmid in sorted(set(by_record.get((str(row["table"]), str(row["record_id"])), []))):
            key = (row.get("start"), row.get("ref"), pmid)
            if key in seen:
                continue
            seen.add(key)
            try:
                out.append(
                    StudyRow(chrom=CONTIG, start=row.get("start"), ref=row.get("ref"), pmid=pmid)
                )
            except ValidationError:
                unusable += 1
    return out, unusable


def _resolve_snapshot(snapshot: Path | None) -> Path:
    reference = snapshot or resolve_mitomap_miss_reference()
    if reference is None:
        raise MitomapDraftError(
            "no MITOMAP-miss snapshot. It is derived rather than downloaded — build it with "
            "`just-dna-enricher mitomap miss` once the mitomap and clinvar caches are on disk, or "
            "point at one with $JUST_DNA_MITOMAP_MISS_CACHE. Nobody-asked is not the same as "
            "MITOMAP having nothing ClinVar lacks."
        )
    return Path(reference)


def draft_panel_from_mitomap_miss(
    spec_dir: Path,
    genes: Sequence[str] = (),
    *,
    snapshot: Path | None = None,
    declared_use: str = "unstated",
    dry_run: bool = False,
) -> MitomapDraftResult:
    """Append the rated half of the MITOMAP increment into a module's `variants.csv`/`studies.csv`.

    `genes` filters on the gene MITOMAP's `locus` names, and the filter runs **first**: "the increment
    has nothing for this gene" and "it has something and this provider would not write it" are
    different answers and are counted apart. A locus naming two genes, or the control region, carries
    no gene and is therefore never selected by a filter — which is the honest consequence of
    withholding the attribution rather than guessing it.
    """
    spec_dir = Path(spec_dir)
    result = MitomapDraftResult(withheld=dict.fromkeys(
        ("photocopy", "unrated_miss", "unmintable", "gene_not_requested", "incomplete_row"), 0
    ))

    # CC BY 3.0 states commercial and clinical use free, so this always answers `None`. Kept because
    # the gate is per source and a reader of this file should see which answer it gives.
    refusal = check_declared_use(MITOMAP_TERMS, declared_use)
    if refusal is not None:  # pragma: no cover - unreachable while the terms stay permissive
        raise MitomapDraftError(refusal)

    reference = _resolve_snapshot(snapshot)
    rows = _snapshot_rows(reference, MISS_PARQUET)
    if not rows:
        raise MitomapDraftError(
            f"the MITOMAP-miss snapshot at {reference} holds no rows. Rebuild it with "
            f"`just-dna-enricher mitomap miss` — an empty increment and an unbuilt one are "
            f"different answers and this one cannot tell you which it is."
        )
    release = read_miss_release(reference)
    result.dataset = miss_dataset_label(release)
    result.stale = stale_parents(reference)

    wanted = {gene.strip().upper() for gene in genes if gene.strip()}
    admitted: list[dict] = []
    for row in rows:
        gene = (row.get("gene") or "").strip()
        if wanted and gene.upper() not in wanted:
            # Counted outside `candidates`, like every other provider's gene filter: a gene the
            # caller did not ask for is not something this provider withheld.
            result.withheld["gene_not_requested"] += 1
            continue
        admitted.append(row)
    result.candidates = len(admitted)

    drafted: list[dict] = []
    partials: list[PartialRow] = []
    incomplete: list[str] = []
    for row in admitted:
        bucket = str(row.get("bucket") or "")
        if bucket != "rated_miss":
            result.withheld[bucket if bucket in result.withheld else "unmintable"] += 1
            if bucket == "unrated_miss" and row.get("withheld_bracket"):
                result.withheld_brackets[str(row["withheld_bracket"])] = (
                    result.withheld_brackets.get(str(row["withheld_bracket"]), 0) + 1
                )
            continue
        cells = _cells(row)
        missing = [
            name for name in ("chrom", "start", "ref", "alts", "clin_sig") if name not in cells
        ]
        if missing:
            # Not reachable from a well-formed miss snapshot — a rated miss has all five by
            # construction — and guarded anyway, because the alternative is a raw ValidationError
            # naming a column the author never wrote (`@specific-rejection`).
            result.withheld["incomplete_row"] += 1
            incomplete.append(f"{row.get('table')}/{row.get('record_id')} ({', '.join(missing)})")
            continue
        stubbed = tuple(name for name in (*_STUBBED, "state") if name not in cells)
        partials.append(
            PartialRow(model=VariantRow, cells=cells, stubbed=stubbed, match_on=_MATCH_ON)
        )
        drafted.append(row)
        if str(row.get("key_shape")) == "indel":
            result.indel_keys += 1
        if indefinite_length(row.get("allele")):
            result.indefinite_alleles.append(
                f"{CONTIG}:{row.get('start')} {row.get('ref')}>{row.get('alt')} "
                f"(MITOMAP calls it {row.get('allele')!r})"
            )

    if partials:
        result.reports.append(
            append_partial_rows(spec_dir, VARIANTS_CSV, partials, dry_run=dry_run)
        )
        studies, unusable = _study_rows(drafted, _snapshot_rows(reference, CITATIONS_PARQUET))
        if studies:
            result.reports.append(append_rows(spec_dir, STUDIES_CSV, studies, dry_run=dry_run))
        if unusable:
            result.warnings.append(
                f"{unusable} MITOMAP citation(s) were refused by studies.csv's own model and were "
                f"not written."
            )

    result.warnings.extend(_notes(result, drafted, incomplete))

    covered = bool(result.reports) and any(
        outcome.status in {"added", "already_present"} for outcome in result.reports[0].outcomes
    )
    if not dry_run and covered:
        # **The licensed source is `mitomap`, not the derived lane.** The increment is a computation
        # this repository performs; the *content* in the drafted rows is MITOMAP's, and it is MITOMAP's
        # attribution duty a published module has to carry (`@source-vs-authority`). The ClinVar half
        # of the pin rides in `dataset`, because the increment's identity really is both parents.
        merge_sources_file(
            [MITOMAP_TERMS.row("annotation", declared_use=declared_use, dataset=result.dataset)],
            spec_dir,
            error=MitomapDraftError,
        )
        if result.added:
            superseded = withdraw_stale_dataset(
                spec_dir, SOURCE_NAME, "annotation", result.dataset, error=MitomapDraftError,
            )
            if superseded is not None:
                result.warnings.append(
                    f"the licence row recorded {superseded} and this run drafted from "
                    f"{result.dataset or 'an unlabelled increment'}, so the release label was "
                    f"withdrawn rather than re-labelled: one column cannot name two releases."
                )
    return result


def _notes(
    result: MitomapDraftResult, drafted: Sequence[dict], incomplete: Sequence[str]
) -> list[str]:
    """Aggregated notes — one sentence per reason, never one per row, plus the per-row worklist.

    The worklist is the exception and is uncapped on purpose: each line is a decision the author has
    to make before the module compiles, and a truncated task list is a task list that loses tasks.
    """
    notes: list[str] = []
    if result.stale:
        for name, (pinned, current) in sorted(result.stale.items()):
            notes.append(
                f"the {name} parent has moved since this increment was built "
                f"(pinned {pinned.get('dataset') or pinned.get('clinvar_file_date') or 'unlabelled'}, "
                f"now {current.get('dataset') or current.get('clinvar_file_date') or 'unlabelled'}). "
                f"Rows drafted now are the increment against the OLDER parent — rebuild with "
                f"`just-dna-enricher mitomap miss` and re-run to draft against today's."
            )
    if result.withheld.get("photocopy"):
        notes.append(
            f"{result.withheld['photocopy']} MITOMAP row(s) publish an allele ClinVar already "
            f"carries and were not drafted. That call reaches this repository through ClinVar with "
            f"ClinVar's own provenance; drafting a second copy would attribute it to the wrong "
            f"publisher and would give a concordance check a copy of ClinVar to agree with."
        )
    if result.withheld.get("unrated_miss"):
        brackets = (
            " " + ", ".join(f"{token} {count}" for token, count in sorted(result.withheld_brackets.items()))
            if result.withheld_brackets else ""
        )
        notes.append(
            f"{result.withheld['unrated_miss']} MITOMAP row(s) are absent from ClinVar and carry no "
            f"class this tier may map — no bracket, a bare confirmation token, or an undocumented "
            f"one{f' ({brackets.strip()})' if brackets else ''}. They are a real identity increment "
            f"and no clinical significance was invented for them. MITOMAP's confirmation token counts "
            f"literature reports and is explicitly not an assignment of pathogenicity."
        )
    if result.withheld.get("unmintable"):
        notes.append(
            f"{result.withheld['unmintable']} MITOMAP row(s) publish no allele pair this schema can "
            f"spell — a deletion written right-anchored as `:` needs the rCRS base at position-1, and "
            f"nothing in the format or compiler tiers may fetch a reference sequence. They are "
            f"neither misses nor photocopies: the join has no key to ask the question with."
        )
    if incomplete:
        notes.append(
            f"{len(incomplete)} row(s) in the increment carry no complete identity for "
            f"{VARIANTS_CSV}: {examples(incomplete)}"
        )
    if result.indel_keys:
        notes.append(
            f"{result.indel_keys} of the drafted row(s) key on an indel. The join is exact and "
            f"neither side is left-aligned, so one of those is an allele ClinVar does not carry or "
            f"one it carries at another anchor — this pass cannot tell you which, and the drafted "
            f"row states MITOMAP's spelling."
        )
    if result.indefinite_alleles:
        notes.append(
            f"{len(result.indefinite_alleles)} drafted row(s) carry an allele NAME stating a "
            f"variable number of copies while the allele columns state one definite pair — the "
            f"source disagreeing with itself: {examples(result.indefinite_alleles)}. The row keeps "
            f"MITOMAP's own ref/alt, because dropping it would discard a published call and "
            f"rewriting it would need a rule for what `(n)` means that MITOMAP has not given. "
            f"Decide it by hand along with the genotype."
        )
    worklist = _genotype_worklist(drafted)
    if worklist:
        notes.append(
            f"{len(worklist)} drafted row(s) carry a genotype placeholder you must replace. MITOMAP "
            f"publishes no called genotype — `homo` and `hetero` are presence flags over a "
            f"literature corpus, not a call — so each line below gives the alleles and what MITOMAP "
            f"recorded about the state it has been reported in. A variant reported only "
            f"heteroplasmically is an argument for a heteroplasmy.csv row rather than a homoplasmic "
            f"variants.csv genotype:\n  " + "\n  ".join(worklist)
        )
    return notes


def _genotype_worklist(drafted: Sequence[dict]) -> list[str]:
    """One line per stubbed row: the alleles to choose between, and MITOMAP's own presence flags.

    Derived from the rows this run offered rather than from the file, so the alleles a placeholder
    must be written from are stated beside the placeholder that needs them.
    """
    lines: list[str] = []
    for row in drafted:
        reported = ", ".join(
            f"{label} {row.get(column) or 'not stated'}"
            for label, column in (("homoplasmic", "homoplasmy"), ("heteroplasmic", "heteroplasmy"))
        )
        lines.append(
            f"{CONTIG}:{row.get('start')} {row.get('ref')}>{row.get('alt')} "
            f"({row.get('gene') or row.get('locus')}, MITOMAP {row.get('status')}) — "
            f"alleles {row.get('ref')} / {row.get('alt')}; reported {reported}"
        )
    return lines
