"""RM449: an rsID row's indel genotype hosted by an insertion and a deletion at one position names one of them.

S158 (the registry, 2026-11-17): `C/CT` is one inserted T on `C>CT` and one deleted T on `CT>C`, so the
string hosting rule accepted both, and the fill put the insertion's claim on the deletion too: silent for an
rsID row alone, a strict `Duplicate (variant, genotype)` beside an authored coordinate row. The rows below are
the measured ones: S158's `rs1057516393` (ClinVar files the insertion under the rsID, VCV 370313, and the
deletion without one, VCV 3653980), and the registry's published `superhuman@2.4.1` `rs766212849`, where
`A/A` was compiled onto `A>AAACTT` (no insertion) and `AAACTT>A` (a homozygous deletion, the witnessed one).
"""

import csv
import io
import shutil
from collections import Counter
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.reverse import reconstructed_projection
from just_dna_compiler.compiler.validate import _validate_spec
from just_dna_compiler.models import CompilationResult
from just_dna_format.findings import CodedWarning

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: rm449\n  title: RM449\n  description: d\n  report_title: RM449\n"
)
_RES_HEADER = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status,"
    "placement_witness,placement_verdict\n"
)
_PHRASE = "opposite events spelled with the same strings"


def _locus(rsid: str, index: int, start: int, ref: str, alt: str, verdict: str, chrom: str = "11") -> str:
    witness = "clinvar" if verdict else ""  # who was asked and what they answered are written together
    return f"{rsid},{rsid},{chrom},{start},{ref},{alt},GRCh38,{index},cache,ensembl,resolved,{witness},{verdict}\n"


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
_S158_UNASKED_LOCI = _locus("rs1057516393", 0, 108256251, "C", "CT", "") + _locus(
    "rs1057516393", 1, 108256251, "CT", "C", ""
)
_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"
_RSID_ROW = "rs1057516393,,,,,C/CT,risk,ins,ATM\n"


def _assert_finding(
    spec: Path, result: CompilationResult, sentence: str, code: str = "rsid_genotype_reads_as_two_events"
) -> None:
    """Check the code before pydantic strips it, then the text and the whole summary after publication."""
    assert result.manifest is not None, result.errors
    compilation = result.manifest.compilation
    _, findings = _validate_spec(spec, strict=compilation.resolution_mode == "strict")
    (finding,) = [w for w in findings if w == sentence]
    assert isinstance(finding, CodedWarning)
    assert sentence in compilation.warnings
    assert (sentence in compilation.carried) == (code == "rsid_genotype_reads_as_two_events")
    coded = [w for w in findings if isinstance(w, CodedWarning)]
    expected = Counter(code if w == sentence else w.code for w in coded)
    assert compilation.warnings_summary == expected
    assert finding.code == code
    assert all(w.code == "rsid_expanded_to_multiple_loci" for w in coded if "; expanded to " in w)


def test_the_rsid_row_alone_lands_on_the_witnessed_spelling_only(tmp_path: Path) -> None:
    """The silent case: before RM449 a strict compile succeeded with the insertion's claim on both events."""
    spec = _spec(tmp_path, _HEADER + _RSID_ROW, _S158_LOCI, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert _placed(tmp_path / "out") == [("rs1057516393", 108256251, "C", ("CT",), "ins")]
    _assert_finding(
        spec,
        result,
        "rs1057516393: the genotype C/CT reads as an insertion and as a deletion at 11:108256251 "
        "(C>CT, CT>C), opposite events spelled with the same strings, so which one the row means "
        "could not be decided from its genotype; the placement a second source witnessed as the "
        "same event, C>CT, is filled and CT>C is not (RM449)",
    )


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


def test_a_witness_that_placed_neither_spelling_leaves_both_filled_and_says_so(tmp_path: Path) -> None:
    """RM453: `unplaced` on every spelling is no evidence for either (a witness holding no counterpart under
    the rsID), so the expansion stays as the not-asked and undecided arms leave it; it no longer refuses."""
    loci = _locus("rs1057516393", 0, 108256251, "C", "CT", "unplaced") + _locus(
        "rs1057516393", 1, 108256251, "CT", "C", "unplaced"
    )
    spec = _spec(tmp_path, _HEADER + _RSID_ROW, loci, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert len(_placed(tmp_path / "out")) == 2
    _assert_finding(
        spec,
        result,
        "rs1057516393: its row's genotype reads as an insertion and as a deletion at 11:108256251 "
        "(C>CT, CT>C), and the second source asked placed neither as the same event (`placement_verdict` is "
        "`unplaced`: it holds no counterpart under this rsID), so both are filled as before (RM453). "
        "If the row is about one of them, replace it with a row authoring that event's coordinate and "
        "re-run the enricher so the table files it",
    )


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
    _assert_finding(
        spec,
        result,
        "rs281864532: its row's genotype reads as an insertion and as a deletion at 11:5225481 "
        "(G>GT, GT>G), and a second source places both under this rsID, so the row's one claim is filled on two "
        "opposite events (RM449). If it is about one of them, replace the rsID row with a row "
        "authoring that event's coordinate, and re-run the enricher so the table files it",
    )
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


def test_a_site_no_second_source_was_asked_about_keeps_the_expansion_and_says_so(tmp_path: Path) -> None:
    """Not asked is not witnessed-neither: an offline run, a ClinVar fill and a pre-0.8 table record no verdict.

    `test_clinvar`'s `rs777`, a ClinVar fill offline, compiled under strict before RM449 and must still.
    """
    spec = _spec(tmp_path, _HEADER + _RSID_ROW, _S158_UNASKED_LOCI, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert len(_placed(tmp_path / "out")) == 2
    (said,) = [w for w in result.warnings if "no second source was asked" in w]
    assert "so both are filled as before (RM449)" in said
    _assert_finding(spec, result, said)


def test_an_authored_coordinate_row_wins_over_an_unwitnessed_expansion_onto_its_key(tmp_path: Path) -> None:
    """RM449's own remedy, where no witness was asked: the coordinate row picks its event, and the rsID row's
    expansion onto that exact (variant_key, genotype) is dropped and named, never a strict duplicate."""
    rows = _HEADER + _RSID_ROW + ",11,108256251,CT,C,C/CT,risk,del,ATM\n"
    spec = _spec(tmp_path, rows, _S158_UNASKED_LOCI, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert _placed(tmp_path / "out") == [
        (None, 108256251, "CT", ("C",), "del"),
        ("rs1057516393", 108256251, "C", ("CT",), "ins"),
    ]
    (said,) = [w for w in result.warnings if "which picks that event (RM449)" in w]
    assert "11:108256251:CT:C" in said
    _assert_finding(spec, result, said)


def test_all_spellings_claimed_counts_the_unpositioned_rsid_row(tmp_path: Path) -> None:
    rows = _HEADER + _RSID_ROW + ",11,108256251,CT,C,C/CT,risk,del,ATM\n"
    rows += ",11,108256251,C,CT,C/CT,risk,ins,ATM\n"
    spec = _spec(tmp_path, rows, _S158_UNASKED_LOCI, "rs1057516393")
    out = tmp_path / "out"
    result = compile_module(spec, out, strict=False)
    assert result.success, result.errors
    weights = pl.read_parquet(out / "weights.parquet")
    assert weights.filter(pl.col("rsid") == "rs1057516393").select("chrom", "start").rows() == [(None, None)]
    _assert_finding(
        spec,
        result,
        "rs1057516393: its row's genotype C/CT is not filled on 11:108256251:C:CT, 11:108256251:CT:C, "
        "because the module authors that coordinate row with the same genotype, which picks that event (RM449)",
        code="rsid_no_hosting_locus",
    )


_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "pathogenic_clinvar"


@pytest.mark.skipif(not _EXAMPLE.is_dir(), reason="the pathogenic_clinvar example is not in this checkout")
def test_pathogenic_clinvar_with_its_placement_verdicts_stripped_compiles_strict_and_laps(
    tmp_path: Path,
) -> None:
    """The table an older enricher or an offline run writes: no witness, no verdict. The restored coordinate
    row `11:5226762 C>CAAAG` still picks its event over `rs80356821`'s expansion, and the lap holds."""
    spec = tmp_path / "pathogenic_clinvar"
    shutil.copytree(_EXAMPLE, spec)
    data = (spec / "resolution.csv").read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    header, *body = data.split(newline)
    columns = header.split(b",")
    blank = {columns.index(b"placement_witness"), columns.index(b"placement_verdict")}
    out = [header]
    for line in body:
        if not line:
            out.append(line)
            continue
        cells = next(csv.reader(io.StringIO(line.decode("utf-8"))))
        cells = ["" if k in blank else cell for k, cell in enumerate(cells)]
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="").writerow(cells)
        out.append(buffer.getvalue().encode("utf-8"))
    (spec / "resolution.csv").write_bytes(newline.join(out))
    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert reconstructed_projection(first.manifest) == reconstructed_projection(second.manifest)


# ── a recorded `undecided` is not a witness (the pm, 2026-11-18, before the 0.8.9 cut) ─────────────────
_UNDECIDED_PHRASE = "could not decide whether either is the same event"


def test_a_site_judged_undecided_both_ways_keeps_the_expansion_and_says_so(tmp_path: Path) -> None:
    """`undecided` is what a run with no reference sequence writes: the witness could not judge, which is not
    witnessed-neither (`@unreachable-not-absent`). Before the fix the row was left unpositioned and strict refused."""
    loci = _locus("rs1057516393", 0, 108256251, "C", "CT", "undecided") + _locus(
        "rs1057516393", 1, 108256251, "CT", "C", "undecided"
    )
    spec = _spec(tmp_path, _HEADER + _RSID_ROW, loci, "rs1057516393")
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert len(_placed(tmp_path / "out")) == 2
    (said,) = [w for w in result.warnings if _UNDECIDED_PHRASE in w]
    assert "so both are filled as before (RM449)" in said and "108256251" in said
    _assert_finding(spec, result, said)
    # Its own sentence: the not-asked one says `placement_verdict` is empty, which this table contradicts.
    assert not [w for w in result.warnings if "no second source was asked" in w]


def test_undecided_beside_unplaced_reads_as_unplaced_beside_nothing(tmp_path: Path) -> None:
    """`undecided` reads as an empty cell, nothing more: beside an `unplaced` spelling the site was asked and no
    spelling was witnessed as the same event, so both stay filled (RM453), exactly as for an empty cell there."""
    for verdict in ("undecided", ""):
        loci = _locus("rs1057516393", 0, 108256251, "C", "CT", verdict) + _locus(
            "rs1057516393", 1, 108256251, "CT", "C", "unplaced"
        )
        spec = _spec(tmp_path / (verdict or "empty"), _HEADER + _RSID_ROW, loci, "rs1057516393")
        result = compile_module(spec, tmp_path / (verdict or "empty") / "out", strict=True)
        assert result.success, result.errors
        assert len(_placed(tmp_path / (verdict or "empty") / "out")) == 2
        (sentence,) = [w for w in result.warnings if "placed neither as the same event" in w]
        assert "so both are filled as before (RM453)" in sentence


def _rewrite_mirrored_verdicts(spec: Path, verdict: str) -> int:
    """Set `placement_verdict` to `verdict` on both spellings of every mirrored site, keeping the bytes else.

    A mirrored site is an rsID's insertion and deletion at one position, read off the table itself.
    """
    data = (spec / "resolution.csv").read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    header, *body = data.split(newline)
    columns = header.decode("utf-8").split(",")
    at = {
        name: columns.index(name)
        for name in ("variant_key", "chrom", "start", "ref", "alts", "placement_verdict")
    }
    parsed = [next(csv.reader(io.StringIO(line.decode("utf-8")))) if line else None for line in body]
    kinds: dict[tuple[str, str, str], set[str]] = {}
    for cells in parsed:
        if cells is None:
            continue
        ref, alts = cells[at["ref"]], cells[at["alts"]]
        if ref and alts and "," not in alts and len(ref) != len(alts):
            kind = "insertion" if len(alts) > len(ref) else "deletion"
            kinds.setdefault((cells[at["variant_key"]], cells[at["chrom"]], cells[at["start"]]), set()).add(
                kind
            )
    mirrored = {site for site, seen in kinds.items() if seen == {"insertion", "deletion"}}
    out, changed = [header], 0
    for line, cells in zip(body, parsed, strict=True):
        if (
            cells is None
            or (cells[at["variant_key"]], cells[at["chrom"]], cells[at["start"]]) not in mirrored
        ):
            out.append(line)
            continue
        cells[at["placement_verdict"]] = verdict
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="").writerow(cells)
        out.append(buffer.getvalue().encode("utf-8"))
        changed += 1
    (spec / "resolution.csv").write_bytes(newline.join(out))
    return changed


_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


@pytest.mark.parametrize("example", ["pathogenic_clinvar", "hboc_palb2"])
def test_an_example_judged_undecided_at_every_mirrored_site_compiles_strict_and_laps(
    example: str, tmp_path: Path
) -> None:
    """The pm's fixture: the example as a run with no reference sequence leaves it, `undecided` on both spellings
    of every mirrored site, compiled strict. Every such site keeps its expansion (the restored `11:5226762
    C>CAAAG` coordinate row in `pathogenic_clinvar` still picks its event over `rs80356821`'s), and the lap holds."""
    if not (_EXAMPLES / example).is_dir():
        pytest.skip(f"the {example} example is not in this checkout")
    spec = tmp_path / example
    shutil.copytree(_EXAMPLES / example, spec)
    assert _rewrite_mirrored_verdicts(spec, "undecided") > 0
    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    assert [w for w in first.warnings if _UNDECIDED_PHRASE in w]
    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert reconstructed_projection(first.manifest) == reconstructed_projection(second.manifest)


@pytest.mark.skipif(not _EXAMPLE.is_dir(), reason="the pathogenic_clinvar example is not in this checkout")
def test_pathogenic_clinvar_as_an_offline_enrich_writes_it_compiles_strict(tmp_path: Path) -> None:
    """RM453's case: offline, ClinVar files `rs80356821`'s deletion under the retired `rs281864900`, so the
    witness writes `unplaced` on both spellings at 11:5226762. Those two cells, as an offline run writes them."""
    spec = tmp_path / "pathogenic_clinvar"
    shutil.copytree(_EXAMPLE, spec)
    data = (spec / "resolution.csv").read_bytes()
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    header, *body = data.split(newline)
    columns = header.split(b",")
    verdict = columns.index(b"placement_verdict")
    out, changed = [header], 0
    for line in body:
        if line.startswith(b"rs80356821,"):
            cells = next(csv.reader(io.StringIO(line.decode("utf-8"))))
            cells[verdict] = "unplaced"
            buffer = io.StringIO()
            csv.writer(buffer, lineterminator="").writerow(cells)
            line, changed = buffer.getvalue().encode("utf-8"), changed + 1
        out.append(line)
    assert changed == 2, "the example's table files rs80356821 at both spellings"
    (spec / "resolution.csv").write_bytes(newline.join(out))
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert any("rs80356821" in w and "(RM453)" in w for w in result.warnings)
