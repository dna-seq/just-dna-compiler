"""Which release answered each `resolution.csv` row, and what the committed table may say about it (RM373).

The 0.8 Ensembl migration probe found that nothing a module records tells an old-release answer from a
new one: a row named the link (`cache`, `ensembl-rest`) and never the release, the licence rows were
written with a blank `dataset`, and RM372's `rsid_coordinate_agreement.release` stated the *run's*
snapshot over a table every row of which an older release had answered. Three pieces, one rule each:

- `LinkReleases` stamps a row this run answers with the release of the link that answered it, and
  stamps nothing else: a row this run did not answer keeps the release it was written with, and a row
  written before 0.8 keeps none (`@sidecar-authoritative`, `@rederive-never-shortens`).
- `table_releases` is what each licence row's `dataset` is computed from: every committed row's
  release, by the source it names, so the label describes the table rather than the run.
- `run_label` lets the run's own record carry its snapshot's label only when that label speaks for
  every row the snapshot's source answered; otherwise it is withheld, with the count behind it.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from just_dna_format.resolution import ResolutionRow


@dataclass(frozen=True)
class LinkReleases:
    """The release each resolution link answered from this run, by the link name `source` records.

    A link missing from `by_link` (`authored`, `manual`, `reversed`, `ensembl-graphql`, which states
    no release) answers `None`. `staged` are rsIDs seeded from an interrupted run's journal: that run
    asked, and its release was never written down, so this run's label would be a guess about it.
    """

    by_link: Mapping[str, str | None]
    staged: frozenset[str] = frozenset()

    def of(self, link: str | None, rsid: str | None = None) -> str | None:
        """The release `link` answered `rsid` from this run, or `None` when it is not known."""
        if rsid is not None and rsid in self.staged:
            return None
        return self.by_link.get(link or "")


def table_releases(
    rows: Iterable[ResolutionRow],
    *,
    carried: set[int],
    witness_release: Mapping[str, str | None],
    recorded: Mapping[str, str | None],
) -> dict[str, list[str | None]]:
    """Every source the committed table names, with the release each row naming it was answered from.

    A row's **authority** contributes its own `source_release`. A **placement witness** has no column of
    its own, so a row this run wrote contributes the witness's release this run, and a row carried
    forward (`carried`, by identity) contributes what the licence row recorded before this run: that
    label was computed over every row then in the table, which includes every row carried now. A witness
    nobody recorded a release for contributes `None`, and the table's label for it is withheld.
    """
    releases: dict[str, list[str | None]] = {}
    for row in rows:
        if row.authority:
            releases.setdefault(row.authority, []).append(row.source_release)
        for witness in filter(None, (row.placement_witness or "").split("+")):
            stated = recorded.get(witness) if id(row) in carried else witness_release.get(witness)
            releases.setdefault(witness, []).append(stated)
    return releases


def run_label(label: str | None, rows: Iterable[ResolutionRow], link: str) -> tuple[str | None, str | None]:
    """`(label, withheld)`: a snapshot's label when it speaks for every row its `link` answered, else a reason.

    A row the snapshot's link answered from another release, or recording none, means this run's
    snapshot does not describe the table, so the label is withheld (`None`) and the reason counts both
    kinds. Rows another link answered (live REST, ClinVar) carry their own release and are not the
    snapshot's to speak for: REST spells Ensembl's release `ensembl_116` where the snapshot spells it
    `…vep116.0`, and nothing here can equate the two. With no label, or no row the link answered,
    nothing is said.
    """
    answered = [row for row in rows if row.source == link]
    if label is None or not answered:
        return label, None
    other = sum(1 for row in answered if row.source_release is not None and row.source_release != label)
    unrecorded = sum(1 for row in answered if row.source_release is None)
    if not other and not unrecorded:
        return label, None
    return None, (
        f"release withheld: {other + unrecorded} of {len(answered)} snapshot-answered row(s) "
        f"in resolution.csv were not answered by this run's snapshot ({label}): {other} answered by another "
        f"release, {unrecorded} recording none. `enrich --rederive` re-answers them (RM373)."
    )
