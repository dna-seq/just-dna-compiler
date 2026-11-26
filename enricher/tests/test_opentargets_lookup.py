"""Open Targets' keyed functions (0.9, RM431 ask 6): `lookup_variants` by chrom + position, then
`lookup_consequences` by the ids it found, over the real 26.09 slice (`assets/opentargets_slice/`).

Every expected row is read from the slice's own parquet with polars at run time, so the duckdb reader is
checked against a second reader of the same bytes, never against numbers copied from them.
"""

import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import opentargets
from just_dna_enricher.opentargets import OpenTargetsError, lookup_consequences, lookup_variants

SLICE = Path(__file__).resolve().parents[2] / "assets" / "opentargets_slice"

#: HFE C282Y (rs1800562), a position the release states one allele at; rs35589214's site, where it states
#: two; and a position the release holds nothing at.
C282Y = ("6", 26092913)
TWO_ALLELES = ("8", 78193100)
NOTHING_THERE = ("6", 1)


def _allele_table() -> pl.DataFrame:
    return pl.read_parquet(SLICE / "data" / "variants.parquet")


def _expected_variants(chrom: str, position: int) -> list[dict]:
    frame = _allele_table().filter((pl.col("chrom") == chrom) & (pl.col("position") == position))
    return frame.sort("chrom", "position", "ref", "alt", "variant_id").to_dicts()


def test_a_position_answers_every_allele_the_release_states_there_keyed_as_asked() -> None:
    asked = [C282Y, ("chr8", TWO_ALLELES[1]), NOTHING_THERE]
    answer = lookup_variants(SLICE, asked)
    assert set(answer) == {C282Y, ("chr8", TWO_ALLELES[1])}, "a position with no allele is not a key"
    assert answer[C282Y] == _expected_variants(*C282Y)
    assert answer[("chr8", TWO_ALLELES[1])] == _expected_variants(*TWO_ALLELES)
    assert len(answer[("chr8", TWO_ALLELES[1])]) > 1, "the slice states two alleles at rs35589214's site"
    assert answer[C282Y][0]["rs_ids"] == ["rs1800562"], "the release's own rsIDs ride along as a list"


def test_no_position_asks_nothing() -> None:
    assert lookup_variants(SLICE, []) == {}


def test_the_ids_found_answer_their_consequences_and_their_credible_set_memberships() -> None:
    found = lookup_variants(SLICE, [C282Y, TWO_ALLELES])
    ids = sorted({row["variant_id"] for rows in found.values() for row in rows})
    answer = lookup_consequences(SLICE, [*ids, "1_1_A_C"])
    consequences = pl.read_parquet(SLICE / "data" / "consequences-00000.parquet")
    members = pl.read_parquet(SLICE / "data" / "credible_set_members-00000.parquet")
    expected: dict[str, list[dict]] = {}
    for variant_id in ids:
        rows = [
            {"table": "consequences", **row}
            for row in consequences.filter(pl.col("variant_id") == variant_id).sort("transcript").to_dicts()
        ] + [
            {"table": "credible_set_members", **row}
            for row in members.filter(pl.col("variant_id") == variant_id)
            .sort("study_locus_id", "posterior_probability")
            .to_dicts()
        ]
        if rows:
            expected[variant_id] = rows
    assert answer == expected
    assert "1_1_A_C" not in answer, "an id the release does not hold is not a key"
    c282y = found[C282Y][0]["variant_id"]
    tables = {row["table"] for row in answer[c282y]}
    assert tables == {"consequences", "credible_set_members"}, "C282Y has transcripts and sits in sets"


def test_a_snapshot_missing_its_allele_table_is_refused_naming_it(tmp_path: Path) -> None:
    broken = tmp_path / "opentargets"
    shutil.copytree(SLICE, broken)
    (broken / "data" / "variants.parquet").unlink()
    with pytest.raises(OpenTargetsError, match="variants.parquet"):
        lookup_variants(broken, [C282Y])


def test_no_snapshot_is_refused_never_an_empty_answer(tmp_path: Path) -> None:
    with pytest.raises(OpenTargetsError):
        lookup_consequences(tmp_path / "absent", ["6_26092913_G_A"])


def test_the_holder_keys_pair_each_chromosome_with_its_position() -> None:
    keys = opentargets._variant_keys([("chr6", 26092913), ("6", 26092913), ("chrM", 73)])
    assert keys == {"chrom": ["6", "MT"], "start": [26092913, 73]}
