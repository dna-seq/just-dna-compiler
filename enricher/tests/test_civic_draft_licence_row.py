"""The CIViC drafter's licence row: written only when it drafted, and carrying its release (RM222).

Two halves of `@write-the-sourcerow`, and this provider had the first one as a comment and the second
not at all.

**"One that contributed nothing writes none."** The gate was `if not dry_run:` and nothing else, with
that exact sentence in the comment above it — so a `--gene` filter matching nothing still wrote a
`civic` row into `licensing.csv`, a licence row claiming a module uses CIViC when it does not. Both
sibling drafters implement the rule (`strchive_draft`, `mitomap_draft`) and `test_strchive_draft.py`
refuses this shape on that path, so the predicate was written down twice already and missing here.

**And `dataset` was computed and dropped.** `civic_dataset_label(...)` reaches every drafted row's
`conclusion`, but `record_source_terms` had no parameter to carry one, so the licence row read
`dataset=''`. That is not cosmetic: `SourceRow.dataset` is what `--verify-datasets` compares and what
`withdraw_stale_dataset` withdraws, so a CIViC-drafted module sat **outside the currency check** every
other drafted module is inside.

The fixture drafts from the checked-in CIViC slice, so "drafted something" and "drafted nothing" are
both real runs of the real provider rather than a stubbed report.
"""

import csv
from pathlib import Path

import pytest
from just_dna_enricher.civic_build import build_snapshot
from just_dna_enricher.civic_draft import CIVIC_SOURCE, draft_panel_from_civic

SLICE = Path(__file__).resolve().parents[2] / "assets" / "civic_slice"
_RELEASE = "01-Aug-2026"


@pytest.fixture
def snapshot(tmp_path):
    return build_snapshot(
        SLICE / "ClinicalEvidenceSummaries.tsv",
        SLICE / "VariantSummaries.tsv",
        SLICE / "MolecularProfileSummaries.tsv",
        tmp_path / "snap",
        release=_RELEASE,
    ).out_dir


@pytest.fixture
def spec(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "module_spec.yaml").write_text(
        "schema_version: '0.7'\nid: civic-probe\nname: CIViC probe\nversion: 1\n"
        "genome_build: GRCh38\ndescription: a probe\n",
        encoding="utf-8",
    )
    return spec_dir


def _licence_rows(spec_dir: Path) -> list[dict]:
    for name in ("licensing.csv", "sources.csv"):
        path = spec_dir / name
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as handle:
                return list(csv.DictReader(handle))
    return []


def test_a_gene_that_drafts_nothing_writes_no_licence_row(spec, snapshot):
    """A licence row is a claim about the module; a module with no CIViC rows must not carry one."""
    result = draft_panel_from_civic(spec, genes=["NOTAREALGENESYMBOL"], snapshot=snapshot)

    assert not any(outcome.status == "added" for r in result.reports for outcome in r.outcomes)
    assert [row for row in _licence_rows(spec) if row["source"] == CIVIC_SOURCE] == []


def test_a_run_that_drafts_writes_one_carrying_the_release(spec, snapshot):
    """The other direction, and the half that was silently empty.

    Unfiltered rather than `genes=[...]`: the checked-in slice is a handful of variants and naming one
    couples this test to which genes happen to be in it. What the case needs is *a run that drafted*.
    """
    result = draft_panel_from_civic(spec, snapshot=snapshot)

    assert any(outcome.status == "added" for r in result.reports for outcome in r.outcomes), (
        "the fixture must draft something or nothing below is tested"
    )
    (row,) = [r for r in _licence_rows(spec) if r["source"] == CIVIC_SOURCE]
    assert row["dataset"], "the licence row carries no dataset, so the currency check cannot see it"
    assert row["dataset"] == result.dataset


def test_the_dataset_is_the_snapshots_own_release(spec, snapshot):
    """Derived from the snapshot rather than asserted as a literal, so a re-cut fixture moves with it."""
    result = draft_panel_from_civic(spec, snapshot=snapshot)

    assert _RELEASE in (result.dataset or ""), result.dataset


def test_a_dry_run_writes_nothing_either(spec, snapshot):
    """Unchanged, and worth pinning beside the new gate: two independent reasons not to write."""
    draft_panel_from_civic(spec, snapshot=snapshot, dry_run=True)

    assert _licence_rows(spec) == []
