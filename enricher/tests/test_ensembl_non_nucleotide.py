"""RM271: neither Ensembl rung serves an allele that is not bases as a locus.

The strings are what the two rungs served on 2026-09-27: live REST answered `rs2100212723` with a chr1
mapping whose `allele_string` is the literal `dbSNP_novariation` and a patch-contig mapping `C/T`, and
`rs2101156061` with `G/TTTTTTTTTTTNNNNNNNNNNN`. The Ensembl VCF-dump snapshot holds the same class as
an empty alt (`rs2100212723`, `T`), `<.>` (`rs1553186440`), an IUPAC placeholder beside real alleles
(`rs33946775`, HBB, `CT` → `CA|CC|CG|<R>`), an `N` in one alt (`rs3838485`, `GGG|GGGN`) and an
`N`-masked chrY `ref` (`rs1603142144`). Domain constants, not counts.
"""

from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_enricher.ensembl import EnsemblResolver, _loci_from_graphql, _loci_from_rest, _placeable_alleles
from just_dna_enricher.resolver import lookup_loci


def _never_read(chrom: str, pos: int) -> str | None:
    raise AssertionError(f"read an anchor base for a two-sided allele string at {chrom}:{pos}")


def _mapping(chrom: str, start: int, allele_string: str) -> dict:
    return {
        "assembly_name": "GRCh38",
        "seq_region_name": chrom,
        "start": start,
        "end": start,
        "allele_string": allele_string,
    }


@pytest.mark.parametrize(
    ("ref", "alts", "expected"),
    [
        ("dbSNP_novariation", [], None),  # REST: dbSNP records no variation at this mapping
        ("T", [""], None),  # snapshot: the same, as an empty alt
        ("AAAGAA", ["<.>"], None),  # snapshot: the same, as a lengthless symbolic alt
        ("CT", ["CA", "CC", "CG", "<R>"], ("CT", ["CA", "CC", "CG"])),  # the placeholder goes, the rest stay
        ("G", ["GGG", "GGGN"], ("G", ["GGG"])),  # an allele of unknown sequence goes
        ("G", ["TTTTTTTTTTTNNNNNNNNNNN"], None),  # nothing but unknown sequence: no locus
        ("CNNNNNNNNNN", ["CCC"], None),  # an N-masked reference is not a place to write a ref
        ("<Y>", ["TC", "TT"], None),
        ("G", ["A"], ("G", ["A"])),  # an ordinary SNV is untouched
    ],
)
def test_the_predicate_keeps_only_the_nucleotide_half(ref: str, alts: list[str], expected: object) -> None:
    assert _placeable_alleles(ref, alts) == expected


def test_rest_withholds_novariation_and_counts_it_apart_from_an_unreadable_anchor() -> None:
    payload = {
        "mappings": [_mapping("1", 2651767, "dbSNP_novariation"), _mapping("HSCHR1_1_CTG3", 212341, "C/T")]
    }
    loci, anchor_withheld, unplaceable = _loci_from_rest(payload, _never_read)
    assert loci == [{"chrom": "HSCHR1_1_CTG3", "start": 212341, "ref": "C", "alts": "T"}]
    assert (anchor_withheld, unplaceable) == (0, 1)


def _rest_only(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(200, json={"data": {"variant": None}})
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def test_an_rsid_with_no_placeable_mapping_is_an_answered_empty() -> None:
    """Permanent, unlike RM268's unreadable anchor, so it is the existing `[]` rather than `None`."""
    resolver = EnsemblResolver()
    resolver._client = httpx.Client(
        transport=_rest_only({"mappings": [_mapping("1", 94108691, "G/TTTTTTTTTTTNNNNNNNNNNN")]})
    )
    assert resolver.resolve_rsid("rs2101156061") == ([], "ensembl-rest")


def test_a_graphql_node_with_no_nucleotide_alt_is_handed_to_rest() -> None:
    node = {
        "alleles": [
            {"allele_type": {"value": "reference"}, "reference_sequence": "G"},
            {"allele_type": {"value": "alt"}, "reference_sequence": "TTTTTNNNN"},
        ],
        "slice": {"location": {"region_name": "1", "start": 94108691}},
    }
    assert _loci_from_graphql(node) == []


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    data = tmp_path / "ensembl" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "chrom": ["1", "1", "11", "1", "Y", "X"],
            "start": [2651767, 13191002, 5225642, 153985723, 10277, 10277],
            "id": ["rs2100212723", "rs1553186440", "rs33946775", "rs3838485", "rs1603142144", "rs1603142144"],
            "ref": ["T", "AAAGAA", "CT", "G", "C" + "N" * 40, "C"],
            "alt": ["", "<.>", "CA|CC|CG|<R>", "GGG|GGGN", "CCC", "CCC"],
        }
    ).write_parquet(data / "homo_sapiens-chr1.parquet")
    return tmp_path / "ensembl"


def test_the_snapshot_serves_only_nucleotide_loci(snapshot: Path, caplog: pytest.LogCaptureFixture) -> None:
    rsids = ["rs2100212723", "rs1553186440", "rs33946775", "rs3838485", "rs1603142144"]
    loci, _, warnings = lookup_loci(snapshot, rsids, [])
    assert loci == {
        "rs33946775": [{"chrom": "11", "start": 5225642, "ref": "CT", "alts": "CA,CC,CG"}],
        "rs3838485": [{"chrom": "1", "start": 153985723, "ref": "G", "alts": "GGG"}],
        "rs1603142144": [{"chrom": "X", "start": 10277, "ref": "C", "alts": "CCC"}],
    }
    # In the snapshot, so the "not in the injected snapshot" warning would be false for them.
    assert not [w for w in warnings if "rs2100212723" in str(w) or "rs1553186440" in str(w)]
    named = [r.getMessage() for r in caplog.records if "no nucleotide allele" in r.getMessage()]
    assert len(named) == 1 and "rs1553186440, rs2100212723" in named[0]


def test_a_position_backfill_never_takes_an_rsid_from_a_novariation_row(snapshot: Path) -> None:
    _, candidates, _ = lookup_loci(snapshot, [], [("1", 2651767, "T", None), ("11", 5225642, "CT", "CA")])
    assert candidates == {("1", 2651767, "T", None): [], ("11", 5225642, "CT", "CA"): ["rs33946775"]}
