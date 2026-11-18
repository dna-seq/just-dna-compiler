"""RM449: an rsID row's indel genotype hosted by an insertion and a deletion at one position names one of them.

S158 (the registry, 2026-11-17): `C/CT` is one inserted T on `C>CT` and one deleted T on `CT>C`, so the
string hosting rule accepted both, and the fill put the insertion's claim on the deletion too: silent for an
rsID row alone, a strict `Duplicate (variant, genotype)` beside an authored coordinate row. The rows below are
the measured ones: S158's `rs1057516393` (ClinVar files the insertion under the rsID, VCV 370313, and the
deletion without one, VCV 3653980), and the registry's published `superhuman@2.4.1` `rs766212849`, where
`A/A` was compiled onto `A>AAACTT` (no insertion) and `AAACTT>A` (a homozygous deletion, the witnessed one).
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: rm449\n  title: RM449\n  description: d\n  report_title: RM449\n"
)
_RES_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status,"
    "placement_witness,placement_verdict\n"
)
_PHRASE = "opposite events spelled with the same strings"


def _locus(rsid: str, index: int, start: int, ref: str, alt: str, verdict: str, chrom: str = "11") -> str:
    return (
        f"{rsid},{rsid},{chrom},{start},{ref},{alt},GRCh38,{index},cache,ensembl,resolved,clinvar,{verdict}\n"
    )


def _spec(root: Path, variants: str, resolution: str, rsid: str) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(variants, encoding="utf-8")
    (spec / "studies.csv").write_text(f"rsid,pmid\n{rsid},29165669\n", encoding="utf-8")
    (spec / "resolution.csv").write_text(_RES_HEADER + resolution, encoding="utf-8")
    return spec


def _placed(out: Path) -> list[tuple]:
    rows = (
        pl.read_parquet(out / "weights.parquet").select("rsid", "start", "ref", "alts", "conclusion").rows()
    )
    placed = [(rsid, start, ref, tuple(alts), conclusion) for rsid, start, ref, alts, conclusion in rows]
    return sorted(placed, key=lambda row: tuple(str(cell) for cell in row))


_S158_LOCI = _locus("rs1057516393", 0, 108256251, "C", "CT", "same_event") + _locus(
    "rs1057516393", 1, 108256251, "CT", "C", "unplaced"
)
_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
_RSID_ROW = "rs1057516393,,,,,C/CT,risk,ins,ATM\n"


def test_the_rsid_row_alone_lands_on_the_witnessed_spelling_only(tmp_path: Path) -> None:
    """The silent case: before RM449 a strict compile succeeded with the insertion's claim on both events."""
    spec = _spec(tmp_path, _HEADER + _RSID_ROW, _S158_LOCI, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert _placed(tmp_path / "out") == [("rs1057516393", 108256251, "C", ("CT",), "ins")]
    (sentence,) = [w for w in result.warnings if _PHRASE in w]
    assert "C>CT, is filled and CT>C is not (RM449)" in sentence


def test_an_authored_deletion_row_beside_it_no_longer_collides(tmp_path: Path) -> None:
    """The loud case: S158's 21 cardio refusals were this pair."""
    rows = _HEADER + _RSID_ROW + ",11,108256251,CT,C,C/CT,risk,del,ATM\n"
    spec = _spec(tmp_path, rows, _S158_LOCI, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert not [e for e in result.errors if "Duplicate (variant, genotype)" in e]
    # The authored deletion keeps its own coordinate and, with no table row under its key, no rsID label.
    assert _placed(tmp_path / "out") == [
        (None, 108256251, "CT", ("C",), "del"),
        ("rs1057516393", 108256251, "C", ("CT",), "ins"),
    ]


# The registry's two published cases (its lead, 2026-11-18, "of 69 latest versions compiled by 0.8.x, 2 carry a
# claim on a two-locus rsID's other spelling"), at their real places: the split snapshot spells each site
# padded (`AAACTT>A,AAACTTAACTT`; `TC>T,TCC`), which reads per ALT as the deletion and the insertion below,
# and ClinVar files only the deletion under the rsID (VCV 471099; VCV 627374).
_PUBLISHED = {
    "superhuman@2.4.1": (
        "rs766212849",
        "2",
        166278198,
        "A/A",
        ("A", "AAACTT"),
        ("AAACTT", "A"),
    ),
    "thrombophilia@2.0.1": ("rs1572088853", "1", 173909933, "C/CC", ("T", "TC"), ("TC", "T")),
}


@pytest.mark.parametrize("case", sorted(_PUBLISHED))
def test_a_published_case_lands_on_the_witnessed_deletion_only(case: str, tmp_path: Path) -> None:
    """superhuman's `A/A` is no insertion on `A>AAACTT` and a homozygous deletion on `AAACTT>A`; one claim sat on both."""
    rsid, chrom, start, genotype, insertion, deletion = _PUBLISHED[case]
    loci = _locus(rsid, 0, start, *insertion, "unplaced", chrom=chrom) + _locus(
        rsid, 1, start, *deletion, "same_event", chrom=chrom
    )
    spec = _spec(tmp_path, _HEADER + f"{rsid},,,,,{genotype},protective,p,X\n", loci, rsid)
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert _placed(tmp_path / "out") == [(rsid, start, deletion[0], (deletion[1],), "p")]


def test_with_no_witness_neither_spelling_is_filled_and_strict_refuses_it_as_unresolved(
    tmp_path: Path,
) -> None:
    loci = _locus("rs1057516393", 0, 108256251, "C", "CT", "unplaced") + _locus(
        "rs1057516393", 1, 108256251, "CT", "C", "unplaced"
    )
    spec = _spec(tmp_path, _HEADER + _RSID_ROW, loci, "rs1057516393")
    lenient = compile_module(spec, tmp_path / "lenient", strict=False)
    (sentence,) = [w for w in lenient.warnings if _PHRASE in w]
    assert "neither is filled and the position remains unset" in sentence
    strict = compile_module(spec, tmp_path / "strict", strict=True)
    assert not strict.success
    assert any("unresolved genomic positions" in e and "rs1057516393" in e for e in strict.errors)


def test_both_spellings_witnessed_keep_the_expansion(tmp_path: Path) -> None:
    """ClinVar files both HBB frameshifts under one rsID: the rsID names both events, so nothing is dropped."""
    loci = _locus("rs281864532", 0, 5225481, "G", "GT", "same_event") + _locus(
        "rs281864532", 1, 5225481, "GT", "G", "same_event"
    )
    spec = _spec(tmp_path, _HEADER + "rs281864532,,,,,G/GT,risk,p,HBB\n", loci, "rs281864532")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert len(_placed(tmp_path / "out")) == 2
    assert not [w for w in result.warnings if _PHRASE in w]
    # Never silent (the pm, 2026-11-18): one sentence for the rsID, in both modes, never escalated in 0.8.
    (said,) = [w for w in result.warnings if "a second source places both under this rsID" in w]
    assert "rs281864532" in said and "5225481" in said and "authoring that event's coordinate" in said
    lenient = compile_module(spec, tmp_path / "lenient", strict=False)
    assert [w for w in lenient.warnings if "a second source places both under this rsID" in w] == [said]


def test_the_both_ways_sentence_is_one_per_rsid_however_many_rows_carry_it(tmp_path: Path) -> None:
    loci = _locus("rs281864532", 0, 5225481, "G", "GT", "same_event") + _locus(
        "rs281864532", 1, 5225481, "GT", "G", "same_event"
    )
    rows = _HEADER + "rs281864532,,,,,G/GT,risk,p,HBB\nrs281864532,,,,,GT/GT,risk,q,HBB\n"
    result = compile_module(_spec(tmp_path, rows, loci, "rs281864532"), tmp_path / "out", strict=False)
    assert len([w for w in result.warnings if "a second source places both under this rsID" in w]) == 1


def test_the_settled_fill_is_a_fixed_point_of_compile_reverse_compile(tmp_path: Path) -> None:
    """P7: the spelling dropped on lap one must not come back on lap two."""
    rows = _HEADER + _RSID_ROW + ",11,108256251,CT,C,C/CT,risk,del,ATM\n"
    spec = _spec(tmp_path, rows, _S158_LOCI, "rs1057516393")
    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    assert _placed(tmp_path / "a1") == _placed(tmp_path / "a2")
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.content_signature == second.manifest.content_signature
