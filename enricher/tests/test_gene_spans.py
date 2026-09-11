"""`gene_spans`: a symbol to a GRCh38 interval, and the three ways there is no answer.

RM194. The span this module produces is a **query hint** — AlphaGenome names the gene on every
record it returns, so the interval only decides what to ask about — which is why the union rule below
is safe and why nothing here may be used to *assign* a gene to a variant.

Every case runs against a real `summary.parquet` built in the test, with the schema the MANE builder
writes: `grch38_chr` holding the RefSeq accession verbatim, and `chr_start`/`chr_end` as `Int64`.
"""

from pathlib import Path

import pytest
from just_dna_enricher.gene_spans import (
    ATTRIBUTION_HORIZON_BP,
    SPAN_REASONS,
    GeneSpanError,
    SpanLookup,
    gene_span,
)

pl = pytest.importorskip("polars", reason="writing the fixture snapshot needs the [dev] extra")


def _snapshot(tmp_path: Path, rows: list[dict]) -> Path:
    """A MANE snapshot directory holding just the table this module reads."""
    out = tmp_path / "mane"
    # Under `data/`, which is where the builder writes and where `locations` says to look. The
    # fixture put it at the snapshot root until a real lane proved otherwise — a fixture that
    # invents a layout agrees with any code that invents the same one.
    (out / "data").mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        rows,
        schema={
            "symbol": pl.Utf8,
            "grch38_chr": pl.Utf8,
            "chr_start": pl.Int64,
            "chr_end": pl.Int64,
            "mane_status": pl.Utf8,
        },
    ).write_parquet(out / "data" / "summary.parquet")
    return out


_HFE = {
    "symbol": "HFE",
    "grch38_chr": "NC_000006.12",
    "chr_start": 26087281,
    "chr_end": 26098343,
    "mane_status": "MANE Select",
}


def test_a_symbol_resolves_to_the_span_mane_places_it_at(tmp_path: Path) -> None:
    found = gene_span("HFE", mane_cache=_snapshot(tmp_path, [_HFE]))
    assert found.reason is None
    assert (found.span.chrom, found.span.start, found.span.end) == ("6", 26087281, 26098343)
    assert found.span.mane_status == ("MANE Select",)


def test_two_rows_for_one_symbol_are_unioned_rather_than_chosen_between(tmp_path: Path) -> None:
    """MANE Select plus MANE Plus Clinical are two transcripts of one gene.

    Picking one would choose a transcript on the caller's behalf for a value that is not about
    transcripts. The union is the widest window, and the costs are asymmetric: too wide spends query
    time, too narrow drops the distal variants the item exists to find.
    """
    plus = {**_HFE, "chr_start": 26080000, "chr_end": 26099999, "mane_status": "MANE Plus Clinical"}
    found = gene_span("HFE", mane_cache=_snapshot(tmp_path, [_HFE, plus]))
    assert (found.span.start, found.span.end) == (26080000, 26099999)
    assert found.span.mane_status == ("MANE Plus Clinical", "MANE Select")


def test_the_horizon_is_added_either_side_and_clamps_at_one(tmp_path: Path) -> None:
    """512 kb is the model's measured half-window, and `start` is 1-based everywhere here."""
    found = gene_span("HFE", mane_cache=_snapshot(tmp_path, [_HFE]))
    chrom, start, end = found.span.widened()
    assert chrom == "6"
    assert start == 26087281 - ATTRIBUTION_HORIZON_BP
    assert end == 26098343 + ATTRIBUTION_HORIZON_BP

    near_the_start = {**_HFE, "symbol": "TINY", "chr_start": 1000, "chr_end": 2000}
    tiny = gene_span("TINY", mane_cache=_snapshot(tmp_path / "b", [near_the_start]))
    assert tiny.span.widened()[1] == 1, "a 1-based coordinate never goes below 1"


def test_no_snapshot_is_nobody_asked_and_says_which_command_builds_one(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """The ordinary case, since the MANE lane is operator-built and nothing publishes one.

    `no_ambient_caches` is requested so this reads the same on a developer machine that happens to
    have the lane — the failure ten tests hit the day the base gained every snapshot.
    """
    absent = gene_span("HFE")
    assert absent.span is None
    assert absent.reason == "no_snapshot"
    assert "mane build" in SPAN_REASONS[absent.reason]


def test_a_provisioned_snapshot_that_lacks_the_symbol_is_a_different_answer(tmp_path: Path) -> None:
    """`@unreachable-not-absent`: asked-and-absent is not nobody-asked, and the remedies differ.

    One says build a cache lane; the other says check a spelling. A caller collapsing both to `None`
    has thrown that away, which is the whole reason `SpanLookup` carries a token.
    """
    missing = gene_span("NOTAGENE", mane_cache=_snapshot(tmp_path, [_HFE]))
    assert missing.reason == "not_in_mane"
    assert SPAN_REASONS["not_in_mane"] != SPAN_REASONS["no_snapshot"]


def test_a_contig_refseq_does_not_number_is_its_own_third_answer(tmp_path: Path) -> None:
    """Returning a coordinate space we cannot name would be worse than saying we cannot."""
    unplaced = {**_HFE, "symbol": "SCAFF", "grch38_chr": "NC_012920.1"}
    found = gene_span("SCAFF", mane_cache=_snapshot(tmp_path, [unplaced]))
    assert found.reason == "unplaced_contig"


def test_one_symbol_on_two_contigs_refuses_rather_than_spanning_both(tmp_path: Path) -> None:
    """Not a wider gene — two genes wearing one symbol, and a span covering both contains neither."""
    elsewhere = {**_HFE, "grch38_chr": "NC_000007.14", "mane_status": "MANE Plus Clinical"}
    found = gene_span("HFE", mane_cache=_snapshot(tmp_path, [_HFE, elsewhere]))
    assert found.reason == "contig_disagreement"


def test_every_reason_the_lookup_can_return_has_its_own_sentence() -> None:
    """A verdict function with several arms owes a reason function with the same arms, pairwise
    distinct (`@answered-is-not-absent`). Asserted as an equality over the reasons the code can
    actually produce, not as a floor."""
    import re

    source = Path(__import__("just_dna_enricher.gene_spans", fromlist=["x"]).__file__).read_text()
    produced = set(re.findall(r'SpanLookup\(reason="(\w+)"\)', source))
    assert produced == set(SPAN_REASONS), f"reason map drifted: {produced ^ set(SPAN_REASONS)}"
    assert len(set(SPAN_REASONS.values())) == len(SPAN_REASONS), "two reasons share a sentence"


def test_a_lookup_that_answers_nothing_without_saying_why_is_refused() -> None:
    """The invariant the type exists for, in both directions."""
    with pytest.raises(GeneSpanError):
        SpanLookup()
    with pytest.raises(GeneSpanError):
        SpanLookup(span=object(), reason="not_in_mane")
