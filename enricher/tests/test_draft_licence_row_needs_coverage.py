"""A drafting run that covered nothing writes no licence row — the last two providers (RM230).

RM222 established this for `civic_draft`: the `SourceRow` a drafter writes travels to the registry
meaning *this module uses this source*, so a `--gene` filter that matched nothing must leave the
module untouched. Writing the row anyway is a claim about a module that does not carry a single row
from that source, and the compile gate plus `manifest.sources` read `sources.csv` and nothing else.

`strchive_draft` and `mitomap_draft` gate on an outcome; `civic_draft` was fixed by RM222.
`clinvar_draft` and `pubmind_draft` write the row on any non-dry run, and RM228 recorded that as a
defect owed. **It is not one, and this file is what established that.** Both return early — "nothing
matched; no rows drafted" — *before* the licence write is reached, so the unconditional-looking gate
is guarded upstream and `covered=True` is the correct argument for both.

So these tests pin the **early return**, which is the thing actually doing the work and which nothing
else asserts. If someone later removes it as redundant, or reorders the licence write above it, the
first test here fails and the RM222 defect arrives in two more providers. That is a better guard than
the fix I was about to write, and RM228's entry is corrected rather than left claiming a debt that
does not exist.

The predicate is the one the other four already use: a row is in the module's table because of this
provider, either `added` now or recognised as `already_present` from an earlier run. `already_present`
counts because a re-draft of a module this provider genuinely populated has still established the
source; what does not count is a run that touched nothing.
"""

import csv
from pathlib import Path

import pytest
from just_dna_format.layout import SOURCES_CSV, preferred_spelling, resolve_sidecar

from just_dna_enricher.clinvar_draft import draft_gene_panel

_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "interim" / "clinvar"
_needs_snapshot = pytest.mark.skipif(
    not (_SNAPSHOT / "data").is_dir(),
    reason="no local ClinVar snapshot (build it with `just-dna-enricher clinvar build`)",
)
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)


def _licence_sources(spec: Path) -> list[str]:
    path = resolve_sidecar(spec, SOURCES_CSV)
    if path is None:
        return []
    with path.open(encoding="utf-8") as handle:
        return [row["source"] for row in csv.DictReader(handle)]


@_needs_snapshot
def test_a_clinvar_run_that_matched_no_gene_writes_no_licence_row(tmp_path: Path) -> None:
    """The property, held today by an early return rather than by the licence gate.

    Measured: the run ends at "nothing matched; no rows drafted" with `reports == []` and nothing
    written. Passing before any change is the finding — it is why RM228's "recorded, not fixed" note
    was wrong and has been corrected.
    """
    result = draft_gene_panel(tmp_path, ["NOTAREALGENESYMBOL"], snapshot=_SNAPSHOT)

    assert not any(report.added for report in result.reports), result.reports
    assert "clinvar" not in _licence_sources(tmp_path), (
        "a run that drafted no row wrote a licence row claiming the module uses ClinVar — the "
        "compile gate and manifest.sources read this file and nothing else (RM222's rule, RM230)"
    )


@_needs_snapshot
def test_a_clinvar_run_that_drafts_still_writes_its_row(tmp_path: Path) -> None:
    """The control, and the half that must not regress: a real draft still records the source."""
    result = draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)

    assert any(report.added for report in result.reports), result.reports
    assert "clinvar" in _licence_sources(tmp_path)


@_needs_snapshot
def test_a_second_draft_of_the_same_gene_keeps_the_row(tmp_path: Path) -> None:
    """`already_present` counts as covered.

    A re-run over a module this provider genuinely populated has still established the source, so the
    row must survive — gating on `added` alone would drop it on every idempotent second lap, which is
    the failure mode the four providers that already do this were careful about.
    """
    draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)
    draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT)

    assert "clinvar" in _licence_sources(tmp_path)


@_needs_snapshot
def test_a_dry_run_writes_nothing_either(tmp_path: Path) -> None:
    """Unchanged by this item, asserted so the new gate cannot be mistaken for the dry-run one."""
    draft_gene_panel(tmp_path, ["MTHFR"], snapshot=_SNAPSHOT, dry_run=True)

    assert not (tmp_path / _LICENCE_CSV).exists()
