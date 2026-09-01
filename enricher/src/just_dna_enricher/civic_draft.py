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

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import DraftReport, PartialRow, append_partial_rows
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.vrs import UnsupportedBuildError, refget_accession

from just_dna_enricher.civic_build import CIVIC_PARQUET
from just_dna_enricher.civic_refutation import CIVIC_REFUTES
from just_dna_enricher.clingen_allele import ClingenAlleleClient, anchor_indel
from just_dna_enricher.licensing import (
    CIVIC_TERMS,
    CLINGEN_ALLELE_REGISTRY_TERMS,
    record_source_terms,
)
from just_dna_enricher.locations import RELEASE_FILENAME, resolve_civic_reference
from just_dna_enricher.sequences import SequenceProxy
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
    # The registry states a one-sided indel and the reference base that would anchor it could not be
    # read (offline, or the sequence service was unreachable). Nobody-asked about the ANCHOR, not
    # about the allele: the registry answered, and a later run with sequence access places the row.
    "anchor_base_unreadable",
    # The row's only route to an identity is a ClinGen CAID and the registry was not consulted —
    # `--offline`, or a lookup that failed. **Nobody-asked, never an absence**: the variant is not
    # unplaceable, it is unplaced, and next run may place it.
    "caid_unresolved",
    # The registry answered and holds no rs-number and no GRCh38 substitution for this CAID. An
    # established absence, and a different fact from the one above.
    "caid_no_identity",
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
    #: CAID-only rows the registry placed, and how — the recovery this pass exists for.
    caid_resolved_by_rsid: int = 0
    caid_resolved_by_coordinate: int = 0
    #: One-sided indels the registry stated and a reference base placed, VCF/Picard left-aligned.
    caid_anchored_indels: int = 0
    dataset: str | None = None
    skipped: bool = False
    #: RM170 — rows this run **wrote** whose variant the same snapshot also refutes, as
    #: `(variant name, supporting EIDs, refuting EIDs with their statuses)`. Not a `withheld` member:
    #: nothing was withheld, and the accounting equality over `withheld` counts rows that were not
    #: written. The author is told, and the row stands.
    refuted_beside_claim: list[tuple[str, str, str]] = field(default_factory=list)
    #: The basis the snapshot was built on. Part of the warning rather than beside it: every
    #: assert-and-refute pair in CIViC rests on submitted content, so on the `accepted` basis this list
    #: is empty by construction and a silent run would read as clear water.
    refutation_basis: str | None = None

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


def _release_payload(reference: Path | None) -> dict:
    """A snapshot's own `release.json`, or `{}` when there is none or it cannot be read.

    One reader for both keys this module wants — `dataset` and `status_basis` — because the path rule
    (a directory means the snapshot root, a file means the parquet two levels down) is the sort of
    thing that gets copied and then diverges.
    """
    if reference is None:
        return {}
    release = (
        reference / RELEASE_FILENAME if reference.is_dir()
        else reference.parent.parent / RELEASE_FILENAME
    )
    if not release.exists():
        return {}
    try:
        payload = json.loads(release.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def civic_dataset_label(reference: Path | None) -> str | None:
    """The snapshot's `dataset`, or `None` when there is no snapshot or it names none.

    `None` is an unknown release, never a fabricated one — the same answer the sibling labels give.
    """
    return _release_payload(reference).get("dataset")


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


def trait_curie(doid: str | None) -> str | None:
    """CIViC's bare Disease Ontology number as an ontology CURIE, or `None`.

    **`trait_efo_id` is not an EFO-only column**, and reading the name as though it were is a mistake
    this provider made once. The field takes any ontology CURIE — its own description says
    "EFO/MONDO/OBA/HP", the validator accepts any `PREFIX:LOCAL` token, and cells are multi-valued —
    so `DOID:1612` belongs in it. The first version of this provider put the DOID in `conclusion`
    prose instead, reasoning that a DOID in an EFO column would be a wrong identifier; the premise was
    false, and the effect was to bury a structured id nothing could join on. Every CIViC germline
    direction row carries a DOID, so the cost was the whole column.

    CIViC publishes the number bare (`1612`), which is not a CURIE; the prefix is added here rather
    than stored upstream, because a bare integer in this column would fail the validator and a reader
    cannot tell which ontology it came from.
    """
    doid = (doid or "").strip()
    return f"DOID:{doid}" if doid else None


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
        "phenotype": row["disease"],
        "trait_efo_id": trait_curie(row["doid"]),
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
    cells = {
        "rsid": row["rsid"],
        "pmid": row["pmid"],
        "trait_efo_id": trait_curie(row["doid"]),
        "conclusion": (
            f"{CIVIC_LABEL} evidence {row['evidence_id']}: {row['significance_raw']} / "
            f"{row['evidence_direction_raw']}, level {row['evidence_level']}"
            f"{'; ' + row['disease'] if row['disease'] else ''}"
        ),
    }
    return PartialRow(
        model=StudyRow,
        cells={k: v for k, v in cells.items() if v is not None},
        stubbed=(),
        match_on=("rsid", "pmid"),
    )


def _snapshot_status_basis(reference: Path) -> str | None:
    """`status_basis` from the snapshot's own `release.json`, or `None` when it states none."""
    return _release_payload(reference).get("status_basis")


def _note_refuted(
    result: "CivicDraftResult", row: dict, refuting: dict[int, list[str]]
) -> None:
    """Record a written row whose variant this snapshot also refutes, once per variant.

    Once per variant rather than once per row: a variant with three supporting items and one
    refutation is one thing an author has to weigh, not three.
    """
    name = str(row["variant_name"] or row["variant_id"])
    if any(existing[0] == name for existing in result.refuted_beside_claim):
        return
    result.refuted_beside_claim.append(
        (name, f"EID {row['evidence_id']}", ", ".join(refuting[int(row["variant_id"])]))
    )


def _refuted_warning(
    refuted: Sequence[tuple[str, str, str]], basis: str | None
) -> list[str]:
    """The RM170 sign: rows this run WROTE whose variant the same snapshot also rebuts.

    Not a withholding line, which is why it is not in `_withheld_warnings`: every row it names was
    drafted, and drafting them is correct — the source supports the direction and this provider writes
    what the source said. What was missing was that nothing then told the author the same source also
    published a rebuttal, so a `risk` row could be authored over one of these with every gate green.

    Named subjects rather than a bare count, the treatment `contested_variant` already gets: a count
    with no names is not actionable, and the author's next move is to read two specific papers.
    `examples` caps the list so a wide draft cannot turn this into a per-row dump (the CPIC lesson).

    The basis rides in the sentence because it decides what the sentence means. Every assert-and-refute
    pair in CIViC rests on a submitted rebuttal, so on the `accepted` basis this line never appears —
    and its absence there is not evidence that the water is clear.
    """
    if not refuted:
        return []
    named = examples([
        f"{name} (supporting {supporting} vs {refuting})" for name, supporting, refuting in refuted
    ])
    stated = f" Snapshot basis `{basis}`." if basis else ""
    return [
        f"{len(refuted)} variant(s) were drafted with a direction the same snapshot also REFUTES, "
        f"and the rows were written: {named}. A refutation withholds a claim rather than "
        f"establishing its opposite, so nothing here says the direction is wrong — it says the "
        f"source both asserts and rebuts it, and only a reader of both can weigh that. Keep the row "
        f"or drop it; either way the choice is now yours rather than invisible.{stated}"
    ]


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
    if withheld["anchor_base_unreadable"]:
        lines.append(
            f"{withheld['anchor_base_unreadable']} CIViC row(s) name an insertion or deletion the "
            f"ClinGen registry states, but the GRCh38 reference base needed to write it VCF-style "
            f"could not be read. The allele is known; the anchor is not, and it is withheld rather "
            f"than guessed — a guessed anchor is a wrong `ref` on a right position."
        )
    if withheld["caid_no_identity"]:
        lines.append(
            f"{withheld['caid_no_identity']} CIViC row(s) name a ClinGen allele id the registry has "
            f"no rs-number and no GRCh38 substitution for — typically an indel it does not express as "
            f"one. The registry answered; this is an absence rather than a failure to ask."
        )
    if withheld["caid_unresolved"]:
        lines.append(
            f"{withheld['caid_unresolved']} CIViC row(s) could only be placed through the ClinGen "
            f"Allele Registry and it was not consulted (offline, or the lookup failed). Those "
            f"variants are unplaced, NOT unplaceable — re-run online and they may draft."
        )
    if withheld["identity_refused_by_model"]:
        lines.append(
            f"{withheld['identity_refused_by_model']} CIViC row(s) publish identity cells that "
            f"variants.csv will not accept — typically a coordinate missing its chromosome. The "
            f"rows are real; what CIViC states about their position is not a position."
        )
    return lines



def _needs_the_registry(row: dict) -> bool:
    """Whether this row's only route to an identity is its CAID.

    Asked of the **cells**, not of `identity_derivation`. That column answers a different question:
    since RM169 a CSQ-sourced row is stamped `vcf_csq` — which names the *file* the row was read
    from — ahead of the routes naming which identifier answered, so a variant whose sole identity is
    a registry id arrives labelled `vcf_csq` and never `caid`. Dispatching on the label therefore
    sent every one of those straight past the registry into `_variant_row`, which strips the empty
    identity cells and refuses the row as `identity_refused_by_model` — a warning whose text blames
    "a coordinate missing its chromosome", which is not what happened. Measured by `civic_vcf`'s own
    docstring at 57 of the 112 CSQ-sourced variants on the 01-Aug-2026 release, withheld with zero
    lookups.

    The general shape: **a provenance label is not a dispatch key.** `identity_derivation` is
    published for a consumer to read, and a second axis landing in it (which file, beside which
    identifier) is legal precisely because nothing was supposed to branch on it.
    """
    if not (row.get("allele_registry_id") or "").strip():
        return False
    return not (row.get("rsid") or "").strip() and row.get("chrom") is None


def draft_panel_from_civic(
    spec_dir: Path,
    genes: Sequence[str] = (),
    *,
    snapshot: Path | None = None,
    declared_use: str = "unstated",
    offline: bool = False,
    registry: ClingenAlleleClient | None = None,
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

    # RM170 — the same group-first rule, one slot over. A refutation is **not** a camp: it withholds a
    # claim rather than making the opposite one, so it never enters `camps` and `contested_ids` is
    # correctly blind to it. What an author still needs to know is that the variant they are about to
    # be handed a `risk` row for is one the same snapshot also rebuts, so the pair is computed here,
    # over the whole admitted group, before any per-row filter can remove either side of it.
    refuting_evidence: dict[int, list[str]] = {}
    for row in admitted:
        if row["evidence_direction_raw"] == CIVIC_REFUTES:
            status = row.get("evidence_status")
            refuting_evidence.setdefault(int(row["variant_id"]), []).append(
                f"EID {row['evidence_id']}" + (f" ({status})" if status else "")
            )
    claimed_ids = {int(row["variant_id"]) for row in admitted if row["direction"] is not None}
    refuted_beside_claim = set(refuting_evidence) & claimed_ids
    result.refutation_basis = _snapshot_status_basis(Path(reference))

    # One client for the run, so its cache and its pacing gate are shared: a CAID appearing on several
    # evidence rows is looked up once, and the registry sees one paced stream rather than N.
    registry = registry if registry is not None else ClingenAlleleClient(offline=offline)
    consulted_registry = False

    # The anchor reader, built once per run so its cache is shared. `SequenceProxy` degrades to
    # `None` offline and on an unreachable service, which is what makes `anchor_base_unreadable` a
    # real outcome rather than a crash.
    sequences = SequenceProxy(offline=offline)

    def read_base(chrom: str, pos: int) -> str | None:
        """One GRCh38 reference base at a 1-based position, or `None`."""
        try:
            accession = refget_accession(chrom)
        except UnsupportedBuildError:  # pragma: no cover - GRCh38 is this snapshot's only build
            return None
        if accession is None:
            return None
        return sequences.subsequence(accession, pos - 1, pos)

    variant_partials: list[PartialRow] = []
    study_partials: list[PartialRow] = []
    for row in admitted:
        if int(row["variant_id"]) in contested_ids:
            result.withheld["contested_variant"] += 1
            continue
        if row["direction"] is None:
            result.withheld["refutation_states_no_direction"] += 1
            continue
        if int(row["variant_id"]) in refuted_beside_claim:
            # The row IS drafted — the source supports this direction and the drafter writes what the
            # source said. Recorded, not withheld: withholding would be the tier choosing a winner
            # between two of the source's own statements, and the accounting equality over `withheld`
            # counts rows that were not written.
            _note_refuted(result, row, refuting_evidence)
        if _needs_the_registry(row):
            # The snapshot kept this row because it has a *route* to an identity rather than one.
            # Walking that route is what turns it into a drafted row, and the three outcomes stay
            # three: placed, established-absence, and nobody-asked.
            consulted_registry = True
            found = registry.resolve(row["allele_registry_id"])
            if found.outcome == "needs_anchor" and found.unanchored is not None:
                # An insertion or a deletion, which the registry states with one side empty. One
                # reference base turns it into a row; without one it stays withheld rather than
                # becoming a half-written coordinate.
                placed = anchor_indel(found.unanchored, read_base)
                if placed is None:
                    result.withheld["anchor_base_unreadable"] += 1
                    continue
                row = dict(row)
                row["chrom"], row["start"], row["ref"], row["alt"] = placed
                result.caid_anchored_indels += 1
                partial = _variant_row(row, dataset=result.dataset)
                if identity_refused_by_model(partial.cells) is not None:
                    result.withheld["identity_refused_by_model"] += 1
                    continue
                variant_partials.append(partial)
                study = _study_row(row)
                if study is not None:
                    study_partials.append(study)
                continue
            if not found.placeable:
                key = "caid_no_identity" if found.outcome == "no_identity" else "caid_unresolved"
                result.withheld[key] += 1
                continue
            row = dict(row)
            if found.rsid:
                row["rsid"] = found.rsid
                result.caid_resolved_by_rsid += 1
            elif found.coordinate:
                row["chrom"], row["start"], row["ref"], row["alt"] = found.coordinate
                result.caid_resolved_by_coordinate += 1
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
    result.warnings.extend(_refuted_warning(result.refuted_beside_claim, result.refutation_basis))

    # A pass that consults a source writes its `SourceRow`, and this one consulted CIViC even where it
    # drafted nothing from it — the gate and `manifest.sources` read `sources.csv` and nothing else
    # (`@write-the-sourcerow`). Not written on a run that never reached the snapshot: a pass that
    # contributed nothing writes none.
    if not dry_run:
        # A pass that consults a source writes its row; one that contributed nothing writes none. The
        # registry is listed only where it was actually asked, which is why the flag is set at the
        # lookup rather than derived from the snapshot's contents.
        consulted = [CIVIC_SOURCE] + ([CLINGEN_ALLELE_REGISTRY_TERMS.source] if consulted_registry else [])
        record_source_terms(
            consulted, "annotation", spec_dir,
            error=CivicDraftError, declared_use=declared_use,
        )
    return result
