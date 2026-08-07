"""The gnomAD constraint snapshot builder, against a real slice of the v4.1 TSV.

The fixture (`assets/gnomad_v4.1_constraint_slice.tsv`) is cut from the actual 95.5 MB release file,
which matters because the property under test only exists in real data: for A1BG, BRCA1 and MYH7 alike
the file carries **two rows claiming `mane_select=true`** — one RefSeq (with a bare NCBI `gene_id`) and
one Ensembl. A hand-written fixture would almost certainly have had one, and the test would then have
passed against the naive "first mane_select row wins" implementation it is meant to catch.
"""

import csv
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.constraint_build import _pick_row, build_snapshot

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "gnomad_v4.1_constraint_slice.tsv"


def _rows(gene: str) -> list[dict]:
    with _SLICE.open(encoding="utf-8", newline="") as handle:
        return [r for r in csv.DictReader(handle, delimiter="\t") if r["gene"] == gene]


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("constraint")
    result = build_snapshot(_SLICE, out)
    return result, pl.read_parquet(result.parquet_file)


# ── the fixture really does contain the ambiguity ───────────────────────────────────────────────


@pytest.mark.parametrize("gene", ["A1BG", "BRCA1", "MYH7"])
def test_source_really_has_two_mane_select_rows(gene: str) -> None:
    mane = [r for r in _rows(gene) if r["mane_select"] == "true"]
    assert len(mane) == 2, "the whole point of the pick rule is that this is ambiguous"
    assert {r["gene_id"].startswith("ENSG") for r in mane} == {True, False}


# ── the pick ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("gene", ["A1BG", "BRCA1", "MYH7"])
def test_pick_is_independent_of_row_order(gene: str) -> None:
    """Feed the same rows in both orders and demand the same answer.

    This is the test the naive implementation fails: with "first `mane_select` wins", forward order
    yields the RefSeq row and reversed order yields the Ensembl one.
    """
    rows = _rows(gene)
    forward = _pick_row(rows)
    backward = _pick_row(list(reversed(rows)))
    assert forward == backward
    assert forward["gene_id"].startswith("ENSG")
    assert forward["mane_select"] == "true"


def test_pick_falls_back_to_canonical_then_gives_up() -> None:
    ensembl_canonical = {
        "gene_id": "ENSG00000000001", "transcript": "ENST1", "mane_select": "false",
        "canonical": "true",
    }
    other = {"gene_id": "ENSG00000000001", "transcript": "ENST2", "mane_select": "false",
             "canonical": "false"}
    assert _pick_row([other, ensembl_canonical]) == ensembl_canonical
    # Only RefSeq rows: there is no ENSG identity to carry, so the honest answer is "none".
    assert _pick_row([{"gene_id": "672", "transcript": "NM_1", "mane_select": "true",
                       "canonical": "true"}]) is None
    assert _pick_row([]) is None


# ── the built snapshot ──────────────────────────────────────────────────────────────────────────


def test_snapshot_is_one_row_per_gene_on_the_ensembl_transcript(snapshot) -> None:
    result, frame = snapshot
    assert result.gene_count == frame.height
    assert frame["gene"].to_list() == sorted({r["gene"] for r in _all_rows()})
    assert frame["gene"].n_unique() == frame.height          # one row per gene
    assert all(g.startswith("ENSG") for g in frame["gene_id"].to_list())
    assert all(t.startswith("ENST") for t in frame["transcript"].to_list())
    assert result.source_rows > frame.height                 # many transcripts reduced to few genes


def test_metric_values_match_the_source_row(snapshot) -> None:
    """Spot-check the column mapping against the picked source row, not against pasted numbers."""
    _result, frame = snapshot
    for gene in ("BRCA1", "MYH7"):
        source = _pick_row(_rows(gene))
        built = frame.filter(pl.col("gene") == gene).to_dicts()[0]
        assert built["loeuf"] == pytest.approx(float(source["lof.oe_ci.upper"]))
        assert built["pli"] == pytest.approx(float(source["lof.pLI"]))
        assert built["mis_z"] == pytest.approx(float(source["mis.z_score"]))
        assert built["obs_lof"] == int(float(source["lof.obs"]))
        # The interval must bracket the point estimate — a column-mapping slip would break this.
        assert built["oe_lof_lower"] <= built["oe_lof"] <= built["loeuf"]


def test_rebuild_is_byte_identical(tmp_path: Path) -> None:
    """Principle 7: the parquet is reproducible; only release.json's `built_at` varies per run."""
    first = build_snapshot(_SLICE, tmp_path / "a")
    second = build_snapshot(_SLICE, tmp_path / "b")
    assert first.parquet_file.read_bytes() == second.parquet_file.read_bytes()

    release_a = json.loads((tmp_path / "a" / "release.json").read_text())
    release_b = json.loads((tmp_path / "b" / "release.json").read_text())
    assert release_a.pop("built_at") != "" and release_b.pop("built_at") != ""
    assert release_a == release_b
    assert release_a["source_sha256"] == first.source_sha256
    assert release_a["dataset"] == "gnomad_v4.1_constraint"


def test_missing_cells_become_null_not_zero(tmp_path: Path) -> None:
    """gnomAD writes an absent metric as `NA`; reading that as 0.0 would invent a constrained gene."""
    header = "gene\tgene_id\ttranscript\tcanonical\tmane_select\tlof.pLI\tlof.oe_ci.upper\tlof.obs"
    body = "TESTG\tENSG00000000002\tENST9\ttrue\ttrue\tNA\t\t12"
    path = tmp_path / "tiny.tsv"
    path.write_text(f"{header}\n{body}\n")
    frame = pl.read_parquet(build_snapshot(path, tmp_path / "out").parquet_file)
    row = frame.to_dicts()[0]
    assert row["pli"] is None
    assert row["loeuf"] is None
    assert row["obs_lof"] == 12


def _all_rows() -> list[dict]:
    with _SLICE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))
