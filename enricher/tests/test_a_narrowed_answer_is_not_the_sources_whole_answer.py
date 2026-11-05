"""RM387: RM374's placement check read a hosting-narrowed answer as if it were the source's whole answer.

**The class.** A check comparing two sets where one was filtered before it was written and the other was
not. `placement_disagreements` (RM374) takes the rows under an rsID's own key as "every locus the source
placed it at", but the enricher writes those rows AFTER the hosting filter (only the loci the authored
genotype can sit on), while a positional row's rsID is back-filled from the source's unfiltered reverse
map. So for an rsID the source places at two loci, a positional row authored at the locus the rsID-keyed
subject's genotype cannot host read as a second placement: `rsid_placements_disagree`, `compile --strict`
refused a valid module, and `--rederive` wrote the same table again, which left no remedy.

**The repair.** The rsID-keyed rows record the source's whole set of places in `resolution.csv`
`source_loci` wherever it is wider than what they place, and the check compares against the union. A table
written before the column existed reads as before (its rows are the whole answer), so RM374's stale case
still fires and `--rederive` is what clears a sibling recorded the old way.

The fixture follows `test_haplotype_allele_filters_a_one_to_many_rsid`: one rsID at two loci of one
snapshot, each a different substitution, so the strings settle hosting with no reference read.
"""

import csv
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_enricher.enrich import enrich, orchestration
from just_dna_format.manifest import read_manifest
from just_dna_format.resolution import split_source_loci
from just_dna_format.vrs import par_partner

CODE = "rsid_placements_disagree"
_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: rm387\n  title: RM387\n  description: d\n  report_title: RM387\n"
    "genome_build: GRCh38\n"
)
_RSID = "rs999"
#: One rsID, two loci; the rsID-keyed row's `A/T` sits only on the first, the positional row on the second.
_SNAPSHOT = {
    "id": [_RSID, _RSID],
    "chrom": ["5", "6"],
    "start": [500, 600],
    "ref": ["A", "A"],
    "alt": ["T", "C"],
}
_VARIANTS = (
    "rsid,genotype,state,conclusion,chrom,start,ref,alts\n"
    f"{_RSID},A/T,risk,authored by rsID; only 5:500 A>T can host it,,,,\n"
    ",A/C,risk,authored by position at the sibling locus,6,600,A,C\n"
)


def _spec(root: Path) -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_RSID},29165669\n", encoding="utf-8")
    return spec


def _snapshot(root: Path) -> Path:
    data = root / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(_SNAPSHOT).write_parquet(data / "chr.parquet")
    return root / "cache"


def _enrich(spec: Path, cache: Path, **kwargs):
    return enrich(spec, offline=True, ensembl_cache=cache, clinvar_cache=spec.parent / "no-clinvar", **kwargs)


def _table(spec: Path) -> list[dict[str, str]]:
    with (spec / "resolution.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _codes(result) -> dict[str, int]:
    return dict(result.warnings_summary)


def test_a_positional_row_at_the_sibling_locus_compiles_strict_and_round_trips(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    _enrich(spec, _snapshot(tmp_path))
    table = _table(spec)
    by_key = {row["variant_key"]: row for row in table}
    (positional,) = [row for row in table if row["variant_key"] != _RSID]
    # The probe's shape, written by the real enricher: the rsID key holds the hostable locus only, and the
    # positional row's rsID is back-filled from the same snapshot at the locus the filter left out.
    assert (by_key[_RSID]["chrom"], by_key[_RSID]["start"]) == ("5", "500")
    assert (positional["rsid"], positional["chrom"], positional["start"]) == (_RSID, "6", "600")
    # The source's whole answer, recorded beside the narrowed one.
    assert split_source_loci(by_key[_RSID]["source_loci"]) == {("5", 500), ("6", 600)}

    first = compile_module(spec, tmp_path / "out1", strict=True)
    assert first.success, first.errors
    assert CODE not in _codes(first)
    reversed_dir = reverse_module(tmp_path / "out1", tmp_path / "rev")
    # The column comes back with the row, or the second lap reads the narrowed answer and refuses.
    rev_by_key = {row["variant_key"]: row for row in _table(reversed_dir)}
    assert rev_by_key[_RSID]["source_loci"] == by_key[_RSID]["source_loci"]
    second = compile_module(reversed_dir, tmp_path / "out2", strict=True)
    assert second.success, second.errors
    one, two = (
        read_manifest(tmp_path / "out1" / "manifest.json"),
        read_manifest(tmp_path / "out2" / "manifest.json"),
    )
    assert one.artifact.digest == two.artifact.digest
    assert one.content_signature == two.content_signature


def test_a_table_recorded_without_the_column_is_cleared_by_rederive(tmp_path: Path) -> None:
    """A sibling recorded the pre-RM387 way still reads as two placements, and `--rederive` clears it."""
    spec, cache = _spec(tmp_path), _snapshot(tmp_path)
    _enrich(spec, cache)
    rows = _table(spec)
    fields = [f for f in rows[0] if f != "source_loci"]
    with (spec / "resolution.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    refused = compile_module(spec, tmp_path / "old", strict=True)
    assert not refused.success
    assert any(CODE in str(e) or "two placement sets" in str(e) for e in refused.errors)
    # An ordinary re-run carries both subjects (merge-not-clobber), so the stale reading stays.
    _enrich(spec, cache)
    assert not compile_module(spec, tmp_path / "plain", strict=True).success
    # The remedy the refusal names re-asks every subject and writes the whole answer.
    _enrich(spec, cache, rederive=True)
    cleared = compile_module(spec, tmp_path / "rederived", strict=True)
    assert cleared.success, cleared.errors


# ── the class over tables one run writes: a single enrich never reads as two placements ───────────────

#: One rsID at three loci of one snapshot, each a substitution only one of the genotypes below can sit on.
_THREE = {
    "id": [_RSID] * 3,
    "chrom": ["5", "6", "7"],
    "start": [500, 600, 700],
    "ref": ["A", "A", "G"],
    "alt": ["T", "C", "A"],
}
_POSITIONAL = {0: ",A/T,risk,p,5,500,A,T\n", 1: ",A/C,risk,p,6,600,A,C\n", 2: ",A/G,risk,p,7,700,G,A\n"}


@pytest.mark.parametrize("genotype", ["A/T", "A/C", "A/G"])
@pytest.mark.parametrize("authored", [(0,), (1,), (2,), (0, 1, 2)])
def test_one_runs_table_is_one_answer_whatever_the_filter_kept(
    tmp_path: Path, genotype: str, authored: tuple[int, ...]
) -> None:
    """Every table one offline run writes, over which locus the rsID's genotype keeps and which loci are
    authored by position: the check must be silent, since one run asks one release (the audit's property)."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    variants = "rsid,genotype,state,conclusion,chrom,start,ref,alts\n" + f"{_RSID},{genotype},risk,r,,,,\n"
    (spec / "variants.csv").write_text(variants + "".join(_POSITIONAL[i] for i in authored), encoding="utf-8")
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_RSID},29165669\n", encoding="utf-8")
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(_THREE).write_parquet(data / "chr.parquet")
    _enrich(spec, tmp_path / "cache")
    positional = [row for row in _table(spec) if row["variant_key"] != _RSID]
    assert {row["rsid"] for row in positional} == {_RSID}, "every positional row is back-filled"
    validated = validate_spec(spec, strict=True)
    assert CODE not in validated.warnings_summary
    assert not [e for e in validated.errors if "two placement sets" in e]


#: RM382's measured case (`test_a_rejected_answer_is_not_the_chains_last_word`, real bytes): the split
#: Ensembl snapshot places HBB `rs613985` only at `3:159434329 T>G`, which the authored 13 bp deletion
#: cannot sit on, so ClinVar places it at `11:5226724`.
_HBB = "rs613985"
_HBB_ENSEMBL = {"id": [_HBB], "chrom": ["3"], "start": [159434329], "ref": ["T"], "alt": ["G"]}
_HBB_CLINVAR = {"rsid": [_HBB], "chrom": ["11"], "start": [5226724], "ref": ["CATAACAGCATCAG"], "alt": ["C"]}


def test_a_rejected_links_locus_is_part_of_the_whole_answer(tmp_path: Path) -> None:
    """The answer RM382 set aside is still a place a link put the rsID: a positional row there, its rsID
    back-filled from that same snapshot, is the same answer as ClinVar's placement, not a second one."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene,chrom,start,ref,alts\n"
        f"{_HBB},C/CATAACAGCATCAG,risk,c,HBB,,,,\n"
        ",G/T,risk,the snapshot's locus authored by position,,3,159434329,T,G\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(f"rsid,pmid\n{_HBB},29165669\n", encoding="utf-8")
    for name, rows, file in (
        ("ens", _HBB_ENSEMBL, "homo_sapiens-chr3.parquet"),
        ("cv", _HBB_CLINVAR, "c.parquet"),
    ):
        (tmp_path / name / "data").mkdir(parents=True)
        pl.DataFrame(rows).write_parquet(tmp_path / name / "data" / file)
    enrich(spec, offline=True, ensembl_cache=tmp_path / "ens", clinvar_cache=tmp_path / "cv")
    by_key = {row["variant_key"]: row for row in _table(spec)}
    assert (by_key[_HBB]["chrom"], by_key[_HBB]["source"]) == ("11", "clinvar")
    assert split_source_loci(by_key[_HBB]["source_loci"]) == {("3", 159434329), ("11", 5226724)}
    validated = validate_spec(spec, strict=True)
    assert CODE not in validated.warnings_summary, validated.errors


def test_a_twin_or_a_respelling_is_not_a_wider_answer() -> None:
    """Only a place the rows stand for nowhere is recorded: a pseudoautosomal Y twin is its X partner (the
    compiler's fold), and a respelled piece stands for its source locus, so neither moves a byte."""
    x_start = 640_851
    partner = par_partner("X", x_start)
    assert partner is not None
    twin = [{"chrom": "X", "start": x_start}, {"chrom": partner[0], "start": partner[1]}]
    assert orchestration._wider_answer(twin, [twin[0]], "GRCh38") is None
    source, piece = {"chrom": "1", "start": 1000}, {"chrom": "1", "start": 998}
    assert orchestration._wider_answer([source], [piece, source], "GRCh38") is None
    sibling = [{"chrom": "5", "start": 500}, {"chrom": "6", "start": 600}]
    assert orchestration._wider_answer(sibling, [sibling[0]], "GRCh38") == "5:500,6:600"
