"""`constraint_flags`, which gnomAD spells two ways and this tier stores one way (RM110).

The column has two producers. The live GraphQL route returns `flags` as a JSON array, which arrives
as a Python `list`; the bulk v4.1 TSV writes the array **literal** into the cell, so the snapshot
route stored `"[]"` for an unflagged gene and `'["outlier_mis","outlier_syn"]'` for a flagged one.
`constraint_flags` is inside `GENE_METRICS_FACT_FIELDS`, so one gene fetched two ways carried two
`gene_metrics.signature` values.

**Both sides' raw tokens are tested here, which is the point** (`@one-normalizer-two-spellings`): a
test over the live producer alone is what let this survive — `test_gnomad.py` has pinned
`constraint_flags is None` on the live leg since 0.5, so the contract existed, was tested, and the
snapshot producer simply never implemented it.
"""

import csv
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.constraint_build import build_snapshot
from just_dna_enricher.gene_metrics import lookup_snapshot
from just_dna_format.gene_metrics import GeneMetricsRow, normalize_constraint_flags

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_SLICE = _ASSETS / "gnomad_v4.1_constraint_slice.tsv"

#: Every distinct shape the **published** v4.1 snapshot's `constraint_flags` column takes, read off
#: the real parquet rather than imagined. Domain constants: these are gnomAD's encodings, not counts
#: copied from a data dump. The empty literal is the overwhelming majority of that file and the
#: multi-token ones are why "empty → null" alone was not the fix — a consumer splitting a two-flag
#: cell on `|` got one bogus token rather than two flags.
_PUBLISHED_CELLS: dict[str, str | None] = {
    "[]": None,
    '["no_exp_lof"]': "no_exp_lof",
    '["outlier_mis"]': "outlier_mis",
    '["outlier_syn"]': "outlier_syn",
    '["outlier_lof"]': "outlier_lof",
    '["no_variants"]': "no_variants",
    '["no_exp_syn"]': "no_exp_syn",
    '["outlier_mis","outlier_syn"]': "outlier_mis|outlier_syn",
    '["no_exp_mis","no_exp_syn"]': "no_exp_mis|no_exp_syn",
    '["no_exp_lof","outlier_mis"]': "no_exp_lof|outlier_mis",
    '["no_exp_lof","no_variants"]': "no_exp_lof|no_variants",
    '["no_exp_lof","outlier_mis","outlier_syn"]': "no_exp_lof|outlier_mis|outlier_syn",
    '["outlier_lof","outlier_mis","outlier_syn"]': "outlier_lof|outlier_mis|outlier_syn",
    '["no_exp_lof","no_exp_syn","no_variants"]': "no_exp_lof|no_exp_syn|no_variants",
    '["no_exp_lof","no_exp_mis","no_exp_syn","no_variants"]':
        "no_exp_lof|no_exp_mis|no_exp_syn|no_variants",
}


# ── the raw file really does carry the shape the fix is about ───────────────────────────────────


def test_the_real_tsv_writes_an_array_literal_rather_than_a_flag_list() -> None:
    """Grounding, in the shape `test_constraint_build` uses: the defect is a property of real data.

    A hand-written fixture would have carried `no_exp_lof` or an empty cell, and the naive reader
    would have passed against it. Both shapes are asserted present, so this cannot pass on a slice
    that lost one of them.
    """
    with _SLICE.open(encoding="utf-8", newline="") as handle:
        cells = {row["constraint_flags"] for row in csv.DictReader(handle, delimiter="\t")}
    assert "[]" in cells, "the empty case is 96% of the published snapshot"
    assert any(c.startswith('["') for c in cells), "and the non-empty case is a literal too"
    # Neither spelling is what the column documents, which is the whole finding.
    assert not any("|" in c for c in cells)
    for cell in cells:
        assert json.loads(cell) == [] or isinstance(json.loads(cell), list)


# ── the normalizer, over both producers' raw tokens ─────────────────────────────────────────────


@pytest.mark.parametrize("cell,expected", sorted(_PUBLISHED_CELLS.items()))
def test_every_published_snapshot_spelling_normalizes(cell: str, expected: str | None) -> None:
    assert normalize_constraint_flags(cell) == expected


def test_the_live_producers_list_reaches_the_same_answer_as_the_snapshots_literal() -> None:
    """The property the whole item is about: one fact, two encodings, one stored cell.

    Computed by pairing each literal with the Python list the GraphQL route would hand over for the
    same flags, rather than by restating the expected string a second time.
    """
    for cell, expected in _PUBLISHED_CELLS.items():
        as_list = json.loads(cell)
        assert normalize_constraint_flags(as_list) == normalize_constraint_flags(cell) == expected


def test_absence_is_none_and_never_an_empty_string() -> None:
    """`if row.constraint_flags:` has to be the right test, which is the consumer-visible ask.

    `""` would be a value where there is none, and the house algebra has no reading for it.
    """
    for empty in (None, [], (), "", "[]", "NA", "na", "null", "None", "  "):
        assert normalize_constraint_flags(empty) is None


def test_normalizing_is_idempotent_and_order_free() -> None:
    """It runs on both legs and on a snapshot rebuilt after this shipped, so it must be a fixed point.

    Order-free because the live producer has always sorted: a signature must not depend on which
    route filled the cell, and gnomAD's own array order is not a fact about the gene.
    """
    once = normalize_constraint_flags('["outlier_syn","outlier_mis"]')
    assert once == "outlier_mis|outlier_syn"
    assert normalize_constraint_flags(once) == once
    assert normalize_constraint_flags(["outlier_syn", "outlier_mis"]) == once


def test_an_unparseable_bracketed_cell_is_kept_rather_than_dropped_or_guessed() -> None:
    """The tier normalizes an encoding it recognises and invents no reading for one it does not.

    Dropping it would destroy evidence of an upstream change; guessing would publish a flag list
    gnomAD never wrote. Surviving verbatim is what makes it visible to whoever reads the table.
    """
    assert normalize_constraint_flags("[not json") == "[not json"
    assert normalize_constraint_flags('{"a": 1}') == '{"a": 1}'


# ── the two fix sites ───────────────────────────────────────────────────────────────────────────


def test_a_snapshot_built_from_here_on_carries_no_array_literal(tmp_path: Path) -> None:
    """`constraint_build` — the leg that cleans FUTURE snapshots."""
    result = build_snapshot(_SLICE, tmp_path)
    cells = pl.read_parquet(result.parquet_file)["constraint_flags"].to_list()
    assert cells, "the slice resolves at least one gene"
    assert all(c is None or ("[" not in c and "]" not in c) for c in cells)
    assert all(c != "" for c in cells)


def test_the_already_published_snapshot_is_normalized_on_READ(tmp_path: Path) -> None:
    """`lookup_snapshot` — the leg that matters most, because the published snapshot is immutable.

    Fixing the builder alone cleans a snapshot nobody has yet. This writes a parquet in the shape the
    *published* v4.1 file really has — the raw literals above — and asserts the pass reading it gets
    the documented column back. Without the read-side normalization every module compiled against the
    snapshot that exists keeps carrying divergent cells forever.
    """
    data = tmp_path / "data"
    data.mkdir()
    genes = [f"G{i}" for i in range(len(_PUBLISHED_CELLS))]
    raw = list(_PUBLISHED_CELLS)
    pl.DataFrame({"gene": genes, "constraint_flags": raw}).write_parquet(data / "x.parquet")

    found = lookup_snapshot(tmp_path, genes)

    assert set(found) == set(genes)
    for gene, cell in zip(genes, raw, strict=True):
        assert found[gene]["constraint_flags"] == _PUBLISHED_CELLS[cell]
    # The consumer-visible restatement of the same thing: the truthful flagged fraction, not 100%.
    flagged = [g for g in genes if found[g]["constraint_flags"]]
    assert len(flagged) == sum(1 for v in _PUBLISHED_CELLS.values() if v is not None)


def test_a_flagged_gene_survives_as_its_own_tokens(tmp_path: Path) -> None:
    """Normalizing the container must not fold the warning away — the flags are still the source's.

    The rejected reading of this fix is "empty → null", which would have left the 708 genuinely
    flagged rows in the published snapshot still unreadable.
    """
    data = tmp_path / "data"
    data.mkdir()
    pl.DataFrame(
        {"gene": ["X"], "constraint_flags": ['["no_exp_lof","outlier_mis","outlier_syn"]']}
    ).write_parquet(data / "x.parquet")

    cell = lookup_snapshot(tmp_path, ["X"])["X"]["constraint_flags"]

    assert cell.split("|") == ["no_exp_lof", "outlier_mis", "outlier_syn"]


# ── the cell itself, which is where the decision put the normalization ───────────────────────────


def _row(cell: object) -> GeneMetricsRow:
    """A minimal valid row carrying `cell`, so the assertions are about that column alone."""
    return GeneMetricsRow(
        gene="X", dataset="gnomad_v4.1_constraint", source="gnomad", status="resolved",
        constraint_flags=cell,
    )


@pytest.mark.parametrize("cell,expected", sorted(_PUBLISHED_CELLS.items()))
def test_the_model_stores_the_documented_shape_whoever_wrote_the_cell(
    cell: str, expected: str | None
) -> None:
    """The half a producer-side fix cannot reach: a `gene_metrics.csv` written before 0.7.

    Every module compiled from the published v4.1 snapshot carries these literals on disk today. The
    validator is what makes `gene_metrics.signature` agree with a module that fetched the same gene
    live, rather than only making new tables agree with each other.
    """
    assert _row(cell).constraint_flags == expected


def test_the_two_routes_hash_the_same_gene_identically() -> None:
    """The consequence the item is actually about: `constraint_flags` is inside the fact set.

    Built from the two encodings of one fact rather than from two hand-written cells, so the test
    fails if either leg stops normalizing.
    """
    from just_dna_format.integrity import gene_metrics_signature

    flags = ["outlier_mis", "outlier_syn"]
    from_snapshot = _row(json.dumps(flags, separators=(",", ":")))
    from_live = _row(flags)
    assert from_snapshot.constraint_flags == from_live.constraint_flags
    assert gene_metrics_signature([from_snapshot]) == gene_metrics_signature([from_live])
