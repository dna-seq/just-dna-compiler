"""Draft `direction`-axis rows from the CIViC snapshot (RM152).

**The axis is `direction`, not `clin_sig`, and that is the whole reason this provider exists.** S84
proposed CIViC as a clinical-significance authority and the measurement refused it: of CIViC's 3,103
germline evidence items, five carry an ACMG tier this format can receive and **zero** are benign-class,
so a clinical-significance disagreement is unsayable. What the same measurement found is 1,458 germline
items on `Predisposition`/`Protectiveness` — this format's `direction` (`risk`/`protective`). RM152
rejected a drafter partly because it would "write rows whose significance column is empty"; that is
true of `clin_sig`, where 812 germline items are `NA`, and **false** of `direction`, where the `NA`
count is zero. The rejection was measured on the axis the report aimed at rather than the one that
survives, which is why this provider is that one.

**A flag on the existing command, never a second command** — `draft-panel --source civic`, the shape
`--source pubmind` set. A separate command is for a provider writing *different tables*; this writes
the ones every panel draft writes.

**It reads the snapshot and never the network.** `civic build` pins a dated release; this reads its
parquet. That keeps the acquisition gate where it belongs and means a draft is reproducible from a
named dataset rather than from whatever the API served that afternoon (`@currency-asks-the-source-not-the-cache`).

**The skip guard is derived from `VariantRow`, never restated beside it.** This is a recorded scar:
`pgx_draft` restated the rule as "no rsID *and* no position" while the model wants rsID **or**
chrom+start, and `draft --gene CYP2C9` died on an unhandled pydantic error. CIViC supplies a live
example of the shape that kills a restated guard — variant 1770 carries a build and a `start` and a
`referenceBases` with **no chromosome**, which passes any "has a position?" test and is not a position.
So the guard here asks the model, and the model's refusal is the answer.

**A contested variant is withheld, never resolved.** Where CIViC's own evidence puts a variant in both
camps, picking one is `mode()` over an unsorted group. The rows stay in the snapshot, the variant gets
no drafted row, and the count is reported.

**Every excluded row is counted in the RESULT, not in this docstring.** That was the reporter's own
objection to a drafter and it is correct: a filter whose scope is narrower than its name hides what it
removed. The snapshot already counted the somatic majority; this counts what it withholds on top.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows
from just_dna_format.spec import StudyRow, VariantRow

from just_dna_enricher.civic_build import CIVIC_GENOME_BUILD, CIVIC_PARQUET
from just_dna_enricher.licensing import CIVIC_TERMS, record_source_terms
from just_dna_enricher.locations import RELEASE_FILENAME, resolve_civic_reference
from just_dna_enricher.verification import examples

logger = logging.getLogger(__name__)

CIVIC_SOURCE = CIVIC_TERMS.source
CIVIC_LABEL = "CIViC"


class CivicDraftError(RuntimeError):
    """The draft cannot run: no snapshot, or one that is present and will not answer."""


#: Why a snapshot row got no authored row. Walked, so the accounting equality can be stated over it
#: rather than over a hand-kept sum (`@registry-completeness`).
CIVIC_WITHHELD_REASONS: tuple[str, ...] = (
    # The source refuted a predisposition claim rather than making one. `direction` is withheld in the
    # snapshot for this row, and a row with no axis value is not a row this provider can author.
    "refutation_states_no_direction",
    # CIViC's own evidence puts this variant in both camps. Kept in the snapshot, withheld here:
    # choosing between them is the weighting model this workspace has declined to invent.
    "contested_variant",
    # The cells CIViC published do not satisfy `VariantRow`'s own identification rule. Asked of the
    # model rather than restated — see the module docstring.
    "identity_refused_by_model",
    # The requested gene filter did not name this row's gene.
    "gene_not_requested",
)


@dataclass
class CivicDraftResult:
    """What a CIViC draft did — and, in equal detail, what it did not write."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: Keyed by `CIVIC_WITHHELD_REASONS`, every member present so a zero is a measured zero.
    withheld: dict[str, int] = field(default_factory=dict)
    #: Snapshot rows the gene filter admitted, before any withholding.
    candidates: int = 0
    dataset: str | None = None
    skipped: bool = False

    @property
    def added(self) -> int:
        """Rows added across every table this run wrote — variants *and* their studies."""
        return sum(len(report.added) for report in self.reports)

    def added_for(self, csv_name: str) -> int:
        return sum(len(r.added) for r in self.reports if r.csv_name == csv_name)

    def outcome_for(self, csv_name: str, outcome: str) -> int:
        """How many `variants.csv` rows landed in one outcome — added, already_present, invalid."""
        return sum(
            len(getattr(r, outcome)) for r in self.reports if r.csv_name == csv_name
        )

    def accounts_for_every_candidate(self) -> bool:
        """Every admitted row is either drafted, already there, refused, or withheld by name.

        An equality, not a floor. A provider that quietly drops a row it cannot handle looks exactly
        like one with nothing to say about it, and the difference is the whole of what a drafted
        module's author needs to know. `invalid` is inside the sum rather than outside it: a row the
        table refused is still a row this pass has to account for.
        """
        landed = sum(
            self.outcome_for("variants.csv", outcome)
            for outcome in ("added", "already_present", "differs", "invalid")
        )
        withheld = sum(v for k, v in self.withheld.items() if k != "gene_not_requested")
        return self.candidates == landed + withheld


def _snapshot_rows(reference: Path) -> list[dict]:
    """Every row of the CIViC snapshot parquet, as plain dicts.

    Read with polars where it is available and pyarrow otherwise — but neither is imported at module
    scope, because a *reader* of a built snapshot must not drag the builder's `[dev]` extra in behind
    it. The whole snapshot is small (hundreds of rows), so there is nothing to stream.
    """
    parquet = reference / "data" / CIVIC_PARQUET if reference.is_dir() else reference
    if not parquet.exists():
        raise CivicDraftError(
            f"no CIViC snapshot at {parquet}. Build one with `just-dna-enricher civic build "
            f"--release <date>`, or point at an existing one with $JUST_DNA_CIVIC_CACHE."
        )
    try:
        import polars as pl

        return pl.read_parquet(parquet).to_dicts()
    except ImportError:  # pragma: no cover - polars is present in this workspace's dev extra
        import pyarrow.parquet as pq

        return pq.read_table(parquet).to_pylist()


def civic_dataset_label(reference: Path | None) -> str | None:
    """The snapshot's `dataset`, or `None` when there is no snapshot or it names none.

    `None` is an unknown release, never a fabricated one — the same answer the sibling labels give.
    """
    if reference is None:
        return None
    release = reference / RELEASE_FILENAME if reference.is_dir() else reference.parent.parent / RELEASE_FILENAME
    if not release.exists():
        return None
    import json

    try:
        return json.loads(release.read_text()).get("dataset")
    except (OSError, ValueError):
        return None


def identity_refused_by_model(cells: dict) -> str | None:
    """`None` when `VariantRow` accepts these identity cells, else the model's own complaint.

    **Derived, never restated.** The rule is "rsid, or chrom AND start" with `ref`/`alts` requiring a
    position — three clauses whose conjunctions a provider gets wrong by paraphrase. Asking the model
    means this cannot drift when the model changes, and means a half-written coordinate is refused by
    the same words a compile would refuse it with (`@identity-whole-or-none`).

    The non-identity columns are filled with values known to validate, so the only thing under test is
    the identity clause; anything else raising here is a bug in this function, not a bad row.
    """
    probe = {"genotype": "A/A", "state": "risk", "conclusion": "identity probe", **cells}
    try:
        VariantRow(**probe)
    except Exception as exc:  # pydantic's ValidationError, not depended on by name at this tier
        message = str(exc)
        if "identifier" in message or "positional" in message or "chrom" in message:
            return message.split("\n")[1].strip() if "\n" in message else message
        raise
    return None


#: Matched on the identity columns rather than the natural key, because `genotype` is the placeholder:
#: a re-run after the author fills it must report `already_present`, not append the stub again.
#:
#: **Constant across the batch, and it has to be.** A first version computed it per row from whichever
#: identity cells that row carried, which is wrong in a way that only shows on the second lap:
#: `append_partial_rows` builds its covered-set from the FIRST partial's `match_on` and compares every
#: signature against it, so a batch mixing arities can never match and re-adds those rows every run.
#: The same five columns `clinvar_draft` uses, with empty cells comparing as empty.
_MATCH_ON: tuple[str, ...] = ("rsid", "chrom", "start", "ref", "alts")


def _variant_row(row: dict, *, dataset: str | None) -> PartialRow:
    """One snapshot row → the authored cells this provider is willing to state.

    `genotype` is stubbed, always. CIViC states which way a variant runs, never which genotype an
    author's module is annotating, and inventing one would be the provider deciding a question only
    the author can (`@placeholder-protects-decision`).

    `state` is filled from `direction` because the two are the same claim at different granularity for
    exactly these two members — and it is filled here rather than derived at compile, because
    `@axes-passthrough` bars the compiler from crossing them.
    """
    cells = {
        "rsid": row["rsid"],
        "chrom": row["chrom"],
        "start": row["start"],
        "ref": row["ref"],
        "alts": row["alt"],
        "gene": row["gene"],
        "direction": row["direction"],
        "state": "risk" if row["direction"] == "risk" else "protective",
        "conclusion": (
            f"{CIVIC_LABEL}: {row['significance_raw']} / {row['evidence_direction_raw']} "
            f"(evidence level {row['evidence_level']}, rating {row['rating']}; "
            f"evidence {row['evidence_id']}, variant {row['variant_id']}"
            f"{'; ' + row['disease'] if row['disease'] else ''}) — a curated interpretation "
            f"recorded as stated, on the {dataset or 'unnamed'} release"
        ),
    }
    return PartialRow(
        model=VariantRow,
        cells={k: v for k, v in cells.items() if v is not None},
        stubbed=("genotype",),
        match_on=_MATCH_ON,
    )


def _study_row(row: dict) -> PartialRow | None:
    """The `(rsid, pmid)` evidence link behind one interpretation, where both halves exist.

    CIViC's per-record provenance is the strongest thing it has: every germline direction item cites a
    real PMID, which is already the shape `studies.csv` wants. `None` where the row carries no rsID —
    `StudyRow` grounds on an identifier, and a study row with no subject grounds nothing.
    """
    if not row["rsid"] or not row["pmid"]:
        return None
    #: The disease goes in `conclusion` and **not** in `trait_efo_id`: CIViC names diseases with a
    #: DOID, and EFO and DO are different ontologies. Putting a DOID in a column a consumer reads as
    #: an EFO id would be a wrong identifier rather than a missing one.
    cells = {
        "rsid": row["rsid"],
        "pmid": row["pmid"],
        "conclusion": (
            f"{CIVIC_LABEL} evidence {row['evidence_id']}: {row['significance_raw']} / "
            f"{row['evidence_direction_raw']}, level {row['evidence_level']}"
            f"{'; ' + row['disease'] if row['disease'] else ''}"
            f"{' (DOID:' + row['doid'] + ')' if row['doid'] else ''}"
        ),
    }
    return PartialRow(
        model=StudyRow,
        cells={k: v for k, v in cells.items() if v is not None},
        stubbed=(),
        match_on=("rsid", "pmid"),
    )


def _withheld_warnings(withheld: dict[str, int], contested: Sequence[str]) -> list[str]:
    """One line per class that actually withheld something, grouped by **reason**.

    A class that withheld nothing says nothing: a check that cannot fail must not report a zero, and
    "0 contested variants" on a module with none is exactly that. Every count is still carried on the
    result, where the accounting equality reads it.
    """
    lines: list[str] = []
    if withheld["refutation_states_no_direction"]:
        lines.append(
            f"{withheld['refutation_states_no_direction']} CIViC row(s) refute a predisposition "
            f"claim rather than making one, so they state no direction and none was drafted. "
            f"Refuting a risk claim does not establish that a variant is protective, and this "
            f"provider will not write the opposite of what the source said."
        )
    if withheld["contested_variant"]:
        lines.append(
            f"{withheld['contested_variant']} variant(s) carry CIViC evidence in BOTH directions "
            f"and were withheld rather than resolved: {examples(contested)}. Choosing between them "
            f"needs a weighting model this format does not have. Read the evidence and author the "
            f"row yourself, or record the decision once you have made it."
        )
    if withheld["identity_refused_by_model"]:
        lines.append(
            f"{withheld['identity_refused_by_model']} CIViC row(s) publish identity cells that "
            f"variants.csv will not accept — typically a coordinate missing its chromosome. The "
            f"rows are real; what CIViC states about their position is not a position."
        )
    return lines


def draft_panel_from_civic(
    spec_dir: Path,
    genes: Sequence[str] = (),
    *,
    snapshot: Path | None = None,
    declared_use: str = "unstated",
    dry_run: bool = False,
) -> CivicDraftResult:
    """Append `direction`-axis rows from the CIViC snapshot, with everything withheld accounted for.

    `genes` filters; empty drafts every variant in the snapshot. The gene filter is applied first and
    counted separately from the withholding, because "CIViC has nothing for this gene" and "CIViC has
    something and we would not write it" are different answers an author needs told apart.

    **The counts land on the result, never only in a log line.** The snapshot already recorded the
    somatic majority it dropped; this records what it withheld on top, and
    `accounts_for_every_candidate()` is an equality over both.
    """
    result = CivicDraftResult(withheld=dict.fromkeys(CIVIC_WITHHELD_REASONS, 0))
    reference = snapshot if snapshot is not None else resolve_civic_reference()
    if reference is None:
        result.skipped = True
        result.warnings.append(
            "No CIViC snapshot found, so nothing was drafted from it. Build one with "
            "`just-dna-enricher civic build --release <date>`, or point at one with "
            "$JUST_DNA_CIVIC_CACHE. Nobody-asked is not the same as the source having nothing."
        )
        return result

    rows = _snapshot_rows(Path(reference))
    result.dataset = civic_dataset_label(Path(reference))
    wanted = {g.strip().upper() for g in genes if g.strip()}

    admitted: list[dict] = []
    for row in rows:
        if wanted and (row["gene"] or "").upper() not in wanted:
            result.withheld["gene_not_requested"] += 1
            continue
        admitted.append(row)
    result.candidates = len(admitted)

    # Contested is decided over the WHOLE admitted group, before any per-row filter runs: a variant
    # whose dissenting row a filter removed would read as uncontested, and the filter would have
    # picked the winner (`@filter-before-the-group-picks-a-winner`).
    camps: dict[int, set[str]] = {}
    for row in admitted:
        if row["direction"] is not None:
            camps.setdefault(int(row["variant_id"]), set()).add(str(row["direction"]))
    contested_ids = {vid for vid, seen in camps.items() if len(seen) > 1}
    contested_names = sorted(
        {str(r["variant_name"] or r["variant_id"]) for r in admitted
         if int(r["variant_id"]) in contested_ids}
    )

    variant_partials: list[PartialRow] = []
    study_partials: list[PartialRow] = []
    for row in admitted:
        if int(row["variant_id"]) in contested_ids:
            result.withheld["contested_variant"] += 1
            continue
        if row["direction"] is None:
            result.withheld["refutation_states_no_direction"] += 1
            continue
        partial = _variant_row(row, dataset=result.dataset)
        if identity_refused_by_model(partial.cells) is not None:
            result.withheld["identity_refused_by_model"] += 1
            continue
        variant_partials.append(partial)
        study = _study_row(row)
        if study is not None:
            study_partials.append(study)

    if variant_partials:
        result.reports.append(
            append_partial_rows(spec_dir, "variants.csv", variant_partials, dry_run=dry_run)
        )
    if study_partials:
        result.reports.append(
            append_partial_rows(spec_dir, "studies.csv", study_partials, dry_run=dry_run)
        )
    result.warnings.extend(_withheld_warnings(result.withheld, contested_names))

    # A pass that consults a source writes its `SourceRow`, and this one consulted CIViC even where it
    # drafted nothing from it — the gate and `manifest.sources` read `sources.csv` and nothing else
    # (`@write-the-sourcerow`). Not written on a run that never reached the snapshot: a pass that
    # contributed nothing writes none.
    if not dry_run:
        record_source_terms(
            [CIVIC_SOURCE], "annotation", spec_dir,
            error=CivicDraftError, declared_use=declared_use,
        )
    return result
