"""What the `--rederive` migration tells its operator: one sentence per case, in one place (RM394).

0.8 tells every consumer to run `enrich --rederive` after the snapshot switch, and the operator acts on
what the run prints. Three of its reports had fewer arms than the cases they describe, so the words
named a cause that had not happened and a remedy that did not apply:

* the drift label had respelled / moved / undecided, so an allele the source **added** (A → A,T, 94
  subjects across the reference examples) and an rsID it **newly named** both read "moved: the source
  names a different event";
* the derived-layer currency line always said `enrich --rederive`, and when the release that is behind
  is the **local snapshot**, a re-derivation reads the same snapshot and prints the same line again;
* the carry-forward said "no source could be asked" about every subject it kept, including ones a link
  answered and the hosting filter rejected.

Each report is a closed vocabulary of cases (`frozenset`, P6's idiom) and a map from case to sentence,
and a test walks every case: the sentences are pairwise distinct, each case is reachable from the real
decision, and each sentence names the remedy its case needs (`@answered-is-not-absent`: a verdict with
several arms owes a reason with the same arms, pairwise distinct; `@warning-text-is-api`: the phrases are
pinned there).
"""

from collections.abc import Mapping

# ── the drift label: what changed between the recorded answer and the fresh one ──────────────────────

#: Every way a re-asked subject's facts can move. `respelled`: the same events, spelled another way.
#: `gained_allele` / `lost_allele`: every event on one side is on the other, which names one more.
#: `gained_rsid` / `renamed`: the same events, the rsID newly named, or changed or dropped. `moved`: an
#: event on each side the other does not name, or another build. `undecided`: nothing this run held
#: could tell (no id and no reference read, or an indel ALT one table keeps), which is never `moved`.
DRIFT_CASES: frozenset[str] = frozenset(
    {"respelled", "gained_allele", "lost_allele", "gained_rsid", "renamed", "moved", "undecided"}
)

#: The phrase each case prints after a subject's before → after. Read by `SubjectDrift.__str__` only.
DRIFT_PHRASES: dict[str, str] = {
    "respelled": "respelled: the same events, spelled another way",
    "gained_allele": "gained an allele: every recorded event is still answered, and the source names one more",
    "lost_allele": "lost an allele: every event answered now was recorded, and the source no longer names one",
    "gained_rsid": "gained an rsID: the same events, and the source now names their rsID",
    "renamed": "renamed: the same events, under another rsID or none",
    "moved": "moved: the source names a different event",
    "undecided": "undecided whether respelled or moved: no VRS id and no reference read, or an indel ALT "
    "only one table keeps",
}

#: `SubjectDrift.respelled`, the 0.8 tri-state, read off the case: `True` respelled, `None` undecided,
#: `False` every case where the source's answer changed. So a caller testing `is True` / `is False`
#: (INTEGRATION_0_8 § 1.31) reads exactly what it read before the arms were split.
RESPELLED_BY_CASE: dict[str, bool | None] = {
    case: True if case == "respelled" else None if case == "undecided" else False for case in DRIFT_CASES
}


def drift_case(
    *,
    same_build: bool,
    rsids_before: frozenset[str | None],
    rsids_after: frozenset[str | None],
    kept: bool | None,
    nothing_new: bool | None,
) -> str:
    """The `DRIFT_CASES` member for one subject, from what the run judged about its two answers.

    `kept` is whether every recorded allele is the same event as a fresh one, and `nothing_new` the same
    the other way (`events.covers`, three-valued each). Another build is another answer. An unknown in
    the direction that decides the arm is `undecided`, never a guessed arm; Kleene, so a `False` either
    way still decides a move where the other direction is unknown.
    """
    if not same_build:
        return "moved"
    events = False if False in (kept, nothing_new) else None if None in (kept, nothing_new) else True
    if rsids_before != rsids_after:
        if events is not True:
            return "undecided" if events is None else "moved"
        return "gained_rsid" if rsids_before == frozenset({None}) else "renamed"
    if events is True:
        return "respelled"
    if kept is True and nothing_new is False:
        return "gained_allele"
    if kept is False and nothing_new is True:
        return "lost_allele"
    return "undecided" if events is None else "moved"


# ── the carry-forward: why a recorded subject was kept rather than re-derived ────────────────────────

#: Why a subject has no fresh row, so the carry-forward keeps its recorded one. `not_asked`: no link
#: could be asked (offline, with no snapshot). `off_build`: the module's build is one no link serves
#: (every link answers GRCh38 only), so nothing can re-ask it. `no_reverse_map`: a
#: coordinate-only subject, and no position→rsID map was read (RM393). `unreachable`: asked, and no usable
#: answer came back (the request failed, or an indel's anchor base could not be read). `rejected`: asked,
#: and every link's answer sat where the authored genotype cannot (RM382), so the recorded placement
#: stands. `not_re_answered`: a subject no branch declared a reason for, said without claiming one.
CARRY_REASONS: frozenset[str] = frozenset(
    {"not_asked", "off_build", "no_reverse_map", "unreachable", "rejected", "not_re_answered"}
)

#: Each reason's sentence, remedy included, read by `carry_sentence` only.
CARRY_SENTENCES: dict[str, str] = {
    "not_asked": "no source could be asked about them this run (offline, with no Ensembl and no ClinVar "
    "snapshot); pull the snapshots with `just-dna-enricher cache pull`, or re-run without --offline",
    "off_build": "on a build no link serves (every link answers GRCh38 only), so nothing re-asks them; "
    "their recorded rows are the table's answer until the module moves build",
    "no_reverse_map": "coordinate-only, and no position→rsID map was read (no Ensembl and no ClinVar "
    "snapshot), so their back-filled rsIDs were not re-asked; pull the Ensembl snapshot with `just-dna-enricher "
    "cache pull --only ensembl`",
    "unreachable": "a link was asked and no usable answer came back (the request failed, or an indel's "
    "anchor base could not be read); re-run when the link answers",
    "rejected": "every link answered, at a place the authored genotype cannot sit, so the recorded "
    "placement stands (the allele-mismatch finding names the answers); check the genotype against them",
    "not_re_answered": "not re-answered this run, for a reason the run did not record; re-run to re-ask them",
}


def carry_sentence(reason: str, count: int, examples: str) -> str:
    """One carried group: its count, its reason's sentence, and the subjects it names."""
    return f"{count} subject(s): {CARRY_SENTENCES[reason]} ({examples})"


# ── the derived-layer currency line: which release is behind, and what moves it ─────────────────────

#: Where a derived layer's superseded release sits, relative to the local snapshot this run read.
#: `table_behind_snapshot`: the snapshot is current, the table recorded an older one. `snapshot_behind`:
#: the snapshot is the release the table recorded, and the source has published since. `both_behind`:
#: the snapshot is newer than the table and still not the source's current release. `snapshot_unread`:
#: this run read no snapshot of the source, or one whose label cannot be compared, so which is behind is
#: unknown and both remedies are named.
CURRENCY_CASES: frozenset[str] = frozenset(
    {"table_behind_snapshot", "snapshot_behind", "both_behind", "snapshot_unread"}
)

#: The remedy each case needs. `{lane}` is the source's cache lane, `{local}` the snapshot's label. A
#: re-derivation reads the local snapshot, so it alone cannot move a label the snapshot is behind on.
CURRENCY_REMEDIES: dict[str, str] = {
    "table_behind_snapshot": "The local snapshot ({local}) is current and the table is behind it: "
    "`enrich --rederive` re-answers the table from it",
    "snapshot_behind": "The local snapshot ({local}) is the release the table recorded, so a "
    "re-derivation repeats this line: bring the snapshot forward with `just-dna-enricher cache pull "
    "--only {lane}` (or `cache rebuild --only {lane}`), then re-derive",
    "both_behind": "The local snapshot ({local}) is newer than the table and older than the source: "
    "`just-dna-enricher cache pull --only {lane}` (or `cache rebuild --only {lane}`), then `enrich "
    "--rederive`",
    "snapshot_unread": "This run read no comparable local snapshot of it, so which is behind is unknown: "
    "`just-dna-enricher cache status` shows the snapshot's release; if it is the old one, `cache pull "
    "--only {lane}` (or `cache rebuild`), then `enrich --rederive`",
}


def currency_case(recorded: str, current: str, local: str | None, comparable: bool) -> str:
    """The `CURRENCY_CASES` member for a superseded derived leg (`recorded != current`).

    `local` is the label of the snapshot this run read for the source, `None` when it read none, and
    `comparable` whether that label is in the form `current` is written in. Unknown is never guessed
    into an arm: it names both remedies.
    """
    if local is None or not comparable:
        return "snapshot_unread"
    if local == current:
        return "table_behind_snapshot"
    if local == recorded:
        return "snapshot_behind"
    return "both_behind"


def currency_remedy(case: str, *, lane: str, local: str | None) -> str:
    """The sentence for one case, with the lane and the snapshot's label filled in."""
    return CURRENCY_REMEDIES[case].format(lane=lane, local=local or "none read")


def by_case(cases: Mapping[str, str]) -> dict[str, list[str]]:
    """`case -> [subject, …]` in the registry's sorted order, each list in the order given."""
    grouped: dict[str, list[str]] = {}
    for subject, case in cases.items():
        grouped.setdefault(case, []).append(subject)
    return {case: grouped[case] for case in sorted(grouped)}
