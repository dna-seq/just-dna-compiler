"""ClinVar-GKM's keyed functions (0.9, RM431 ask 5): `lookup_variants` by chrom + position and
`lookup_rsids`, in duckdb, over the witness built from `assets/clinvar_gkm_slice/` in-test.

The loader `ClinVarGkmWitness.load` reads the same slice with polars, so it is the second reader the
keyed functions are checked against: the same placements, as plain dicts.
"""

import dataclasses
import hashlib
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import clinvar_gkm, clinvar_gkm_build
from just_dna_enricher.clinvar_gkm import (
    ALLELE_FILE,
    VARIATION_FILE,
    WITNESS_PARQUET,
    ClinVarGkmError,
    ClinVarGkmWitness,
    lookup_rsids,
    lookup_variants,
    parse_manifest,
)
from just_dna_enricher.clinvar_gkm_build import build_snapshot

SLICE = Path(__file__).resolve().parents[2] / "assets" / "clinvar_gkm_slice"

#: rs72613567's insertion (HSD17B13), as LANES_0_8.md §3.5 records it (a domain constant).
HSD17B13 = ("4", 87310240)


def _slice_manifest_text() -> str:
    """The real manifest, with the two input entries rewritten to the slice's own size and digest."""
    raw = json.loads((SLICE / "manifest.json").read_text(encoding="utf-8"))
    for entry in raw["files"]:
        path = {ALLELE_FILE: SLICE / ALLELE_FILE, VARIATION_FILE: SLICE / VARIATION_FILE}.get(entry["name"])
        if path is not None:
            entry["size"] = path.stat().st_size
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.dumps(raw)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("clinvar_gkm")
    build_snapshot(
        SLICE / ALLELE_FILE, SLICE / VARIATION_FILE, out, manifest=parse_manifest(_slice_manifest_text())
    )
    return out


def _ordered(rows: list) -> list[dict]:
    frame = pl.DataFrame(
        [dataclasses.asdict(row) for row in rows], schema=clinvar_gkm_build._witness_schema()
    )
    return frame.sort(frame.columns, nulls_last=True).to_dicts()


def test_the_columns_a_remote_answer_is_typed_by_are_the_builders_schema() -> None:
    types = {pl.Utf8: "VARCHAR", pl.Int64: "BIGINT"}
    assert clinvar_gkm._WITNESS_COLUMNS == tuple(
        (name, types[dtype]) for name, dtype in clinvar_gkm_build._witness_schema().items()
    )


def test_a_position_answers_every_placement_the_witness_holds_there_keyed_as_asked(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    expected = _ordered(witness._rows((pl.col("chrom") == "4") & (pl.col("pos") == HSD17B13[1])))
    assert expected, "rs72613567's insertion is in the slice"
    asked = [HSD17B13, ("chr4", HSD17B13[1]), ("4", 1)]
    answer = lookup_variants(built, asked)
    assert answer == {HSD17B13: expected, ("chr4", HSD17B13[1]): expected}


def test_an_rsid_answers_as_the_loader_does_both_alleles_of_a_multi_allelic_one(built: Path) -> None:
    witness = ClinVarGkmWitness.load(built)
    asked = ["rs1003713657", "RS72613567", "rs8176719"]
    answer = lookup_rsids(built, asked)
    assert answer == {
        "rs1003713657": _ordered(witness.by_rsid("rs1003713657")),
        "RS72613567": _ordered(witness.by_rsid("rs72613567")),
    }
    assert len({row["vrs_id"] for row in answer["rs1003713657"]}) == 2, "two alleles, neither picked"
    assert "rs8176719" not in answer, "not witnessed is not a key (LANES §3.5)"


def test_no_snapshot_is_refused_never_an_empty_answer(tmp_path: Path) -> None:
    with pytest.raises(ClinVarGkmError, match=WITNESS_PARQUET):
        lookup_rsids(tmp_path, ["rs72613567"])
    assert lookup_variants(tmp_path, []) == {}, "no key asks nothing, so nothing is read"


def test_the_holder_keys_are_the_witness_spelling(built: Path) -> None:
    assert clinvar_gkm._variant_keys([("chrM", 73), ("4", HSD17B13[1])]) == {
        "chrom": ["MT", "4"],
        "start": [73, HSD17B13[1]],
    }
    assert clinvar_gkm._RSID.parameter(["RS72613567", "72613567"]) == ["rs72613567"]
