"""One value, one normalizer, on the real compile path (RM363, `@one-normalizer-two-spellings`).

Each test writes one value two ways in one module and asserts the compile reaches the answer it reaches
when the value is written one way. Expected values come from the single-spelling compile of the same
module at run time, never from a count read off a dump.
"""

import csv
import io
import shutil
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import (
    _cross_validate_phase_ambiguity,
    compile_module,
    reverse_module,
    validate_spec,
)
from just_dna_format.pgx import DiplotypeRow, HaplotypeRow
from just_dna_format.spelling import drug_key, gene_key

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_APOE = _EXAMPLES / "apoe_klvs_meta"

_SPEC_YAML = """schema_version: '1.0'
module:
  name: spelling_probe
  title: Spelling probe
  description: One value written two ways.
  report_title: Spelling probe
  icon: heartbeat
  icon_set: fomantic
  color: '#21ba45'
defaults:
  curator: ai-module-creator
  method: literature-review
genome_build: GRCh38
"""


def _write(spec: Path, files: dict[str, str]) -> Path:
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_SPEC_YAML, encoding="utf-8")
    for name, text in files.items():
        (spec / name).write_text(text, encoding="utf-8")
    return spec


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(out.getvalue(), encoding="utf-8")


def _codes(result) -> dict[str, int]:
    return dict(result.warnings_summary)


# ── gene ────────────────────────────────────────────────────────────────────────────────────────────


def _respell_one_apoe_diplotype(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """`apoe_klvs_meta` with its ε3/ε4 diplotype's gene written `Apoe` — the audit's probe."""
    spec = tmp_path / "respelled"
    shutil.copytree(_APOE, spec)
    rows = _rows(spec / "diplotypes.csv")
    target = next(r for r in rows if (r["gene"], r["haplotype_a"], r["haplotype_b"]) == ("APOE", "ε3", "ε4"))
    target["gene"] = "Apoe"
    _write_rows(spec / "diplotypes.csv", rows)
    return spec, target


def _reached_diplotypes(out: Path) -> dict[tuple, tuple]:
    frame = pl.read_parquet(out / "meta_resolved.parquet").filter(pl.col("table") == "diplotypes")
    return {
        (gene_key(r["key"][0]), *r["key"][1:], r["sex"], r["drug"]): (r["tier"], r["age_of_action"])
        for r in frame.iter_rows(named=True)
    }


def test_an_allele_reaches_its_diplotype_whatever_case_the_gene_is_written_in(tmp_path: Path) -> None:
    base = compile_module(_APOE, tmp_path / "base", strict=True)
    assert base.success, base.errors
    spec, target = _respell_one_apoe_diplotype(tmp_path)
    respelled = compile_module(spec, tmp_path / "out", strict=True)
    assert respelled.success, respelled.errors
    expected = _reached_diplotypes(tmp_path / "base")
    assert (gene_key(target["gene"]), "ε3", "ε4") in {k[:3] for k in expected}
    assert _reached_diplotypes(tmp_path / "out") == expected


def test_a_meta_selector_names_a_gene_in_any_case(tmp_path: Path) -> None:
    spec = tmp_path / "selector"
    shutil.copytree(_APOE, spec)
    rows = _rows(spec / "meta.csv")
    for row in rows:
        row["members"] = row["members"].replace("gene=APOE", "gene=apoe")
    _write_rows(spec / "meta.csv", rows)
    base = compile_module(_APOE, tmp_path / "base", strict=True)
    folded = compile_module(spec, tmp_path / "out", strict=True)
    assert folded.success, folded.errors
    assert "meta_selector_matches_nothing" not in _codes(folded)
    assert [c.matches for c in folded.manifest.meta_selectors] == [
        c.matches for c in base.manifest.meta_selectors
    ]


def test_a_phase_ambiguity_is_found_across_two_spellings_of_its_gene() -> None:
    sites = (("rs1800562", "6", 26092913, "G"), ("rs1799945", "6", 26090951, "C"))

    def hap(name: str, a: str, b: str) -> list[HaplotypeRow]:
        return [
            HaplotypeRow(haplotype_name=name, rsid=r, chrom=c, start=s, ref=f, allele=x, gene="HFE")
            for (r, c, s, f), x in zip(sites, (a, b), strict=True)
        ]

    haplotypes = [
        *hap("wt", "G", "C"),
        *hap("C282Y", "A", "C"),
        *hap("H63D", "G", "G"),
        *hap("C282Y-H63D", "A", "G"),
    ]

    def dips(second_gene: str) -> list[DiplotypeRow]:
        return [
            DiplotypeRow(
                gene="HFE", haplotype_a="C282Y", haplotype_b="H63D", conclusion="compound heterozygous"
            ),
            DiplotypeRow(
                gene=second_gene, haplotype_a="C282Y-H63D", haplotype_b="wt", conclusion="both in cis"
            ),
        ]

    expected = _cross_validate_phase_ambiguity(haplotypes, dips("HFE"))
    assert expected, "the single-spelling fixture must be ambiguous, or this test proves nothing"
    assert _cross_validate_phase_ambiguity(haplotypes, dips("Hfe")) == expected


def test_stats_genes_counts_one_gene_once(tmp_path: Path) -> None:
    spec, _ = _respell_one_apoe_diplotype(tmp_path)
    base = compile_module(_APOE, tmp_path / "base", strict=True)
    respelled = compile_module(spec, tmp_path / "out", strict=True)
    assert respelled.manifest.stats.genes == base.manifest.stats.genes
    assert respelled.manifest.stats.gene_count == base.manifest.stats.gene_count


# ── chromosome ──────────────────────────────────────────────────────────────────────────────────────

_VARIANT = (
    "chrom,start,ref,alts,genotype,state,conclusion\n{c},111446804,C,T,C/C,neutral,Two reference alleles.\n"
)
_STUDY = "chrom,start,ref,pmid\n{c},111446804,C,30642433\n"


def test_a_coordinate_study_meets_its_variant_whatever_the_contig_prefix(tmp_path: Path) -> None:
    for variant_chrom, study_chrom in (("12", "12"), ("chr12", "chr12"), ("12", "chr12"), ("chr12", "12")):
        spec = _write(
            tmp_path / f"{variant_chrom}-{study_chrom}",
            {"variants.csv": _VARIANT.format(c=variant_chrom), "studies.csv": _STUDY.format(c=study_chrom)},
        )
        result = validate_spec(spec, resolve_with_ensembl=False)
        assert not [w for w in result.warnings if "Studies reference variants not in" in w], (
            variant_chrom,
            study_chrom,
        )


# ── citation: DOI and PMID ──────────────────────────────────────────────────────────────────────────


def _study_dupes(tmp_path: Path, name: str, studies: str) -> int:
    spec = _write(tmp_path / name, {"variants.csv": _VARIANT.format(c="12"), "studies.csv": studies})
    return _codes(validate_spec(spec, resolve_with_ensembl=False)).get("duplicate_study_citation", 0)


def test_one_doi_written_with_and_without_trailing_punctuation_is_one_citation(tmp_path: Path) -> None:
    once = "chrom,start,ref,pmid,doi\n12,111446804,C,NONE,10.1101/2024.01.01.123456\n"
    twice = once + "12,111446804,C,NONE,https://doi.org/10.1101/2024.01.01.123456.\n"
    assert _study_dupes(tmp_path, "once", once) == 0
    assert _study_dupes(tmp_path, "twice", twice) == 1


def test_one_pmid_written_two_ways_is_one_citation(tmp_path: Path) -> None:
    once = "chrom,start,ref,pmid\n12,111446804,C,30642433\n"
    twice = once + "12,111446804,C,[PMID: 30642433]\n"
    assert _study_dupes(tmp_path, "once", once) == 0
    assert _study_dupes(tmp_path, "twice", twice) == 1


# ── drug ────────────────────────────────────────────────────────────────────────────────────────────

_HAPLOTYPES = "gene,haplotype_name,rsid,allele\nTPMT,*1,rs1800460,C\nTPMT,*3B,rs1800460,T\n"
_DIPLOTYPES = (
    "gene,haplotype_a,haplotype_b,phenotype,drug,conclusion\n"
    "TPMT,*1,*1,Normal Metabolizer,azathioprine,Standard dose.\n"
    "TPMT,*1,*3B,Intermediate Metabolizer,azathioprine,Reduced dose.\n"
)


def _drug_module(tmp_path: Path, name: str, meta: str) -> Path:
    return _write(
        tmp_path / name, {"haplotypes.csv": _HAPLOTYPES, "diplotypes.csv": _DIPLOTYPES, "meta.csv": meta}
    )


_META_HEADER = "members,tier,age_of_action,drug\n"


def test_a_meta_row_whose_drug_disagrees_with_its_member_rows_warns(tmp_path: Path) -> None:
    agree = _drug_module(
        tmp_path, "agree", _META_HEADER + '"diplotypes[gene=TPMT, haplotype_b=*3B]",,ADULT,Azathioprine\n'
    )
    differ = _drug_module(
        tmp_path, "differ", _META_HEADER + '"diplotypes[gene=TPMT, haplotype_b=*3B]",,ADULT,mercaptopurine\n'
    )
    assert "meta_member_drug_disagrees" not in _codes(validate_spec(agree, resolve_with_ensembl=False))
    differs = validate_spec(differ, resolve_with_ensembl=False)
    assert _codes(differs).get("meta_member_drug_disagrees") == 1
    (warning,) = [w for w in differs.warnings if "mercaptopurine" in w and "azathioprine" in w]
    assert "line 2" in warning


def test_an_allele_row_scoped_to_a_drug_is_checked_against_the_diplotypes_it_reaches(tmp_path: Path) -> None:
    """The contained reach attaches a one-member allele row's facts to its diplotypes, so those count."""
    meta = _META_HEADER + '"allele_function[gene=TPMT, allele=*3B]",,ADULT,{drug}\n'
    for drug, expected in (("azathioprine", 0), ("mercaptopurine", 1)):
        spec = _drug_module(tmp_path, drug, meta.format(drug=drug))
        (spec / "allele_function.csv").write_text(
            "gene,allele,function_status\nTPMT,*3B,no_function\n", encoding="utf-8"
        )
        result = validate_spec(spec, resolve_with_ensembl=False)
        assert _codes(result).get("meta_member_drug_disagrees", 0) == expected, drug


def test_one_drug_written_two_ways_is_one_scope(tmp_path: Path) -> None:
    """Two rows on two scopes that share a drug written two ways: the drug axis holds one value, named
    in its first spelling, and the narrower `(male, drug)` row outranks the `(none, drug)` one there."""
    member = '"diplotypes[gene=TPMT, haplotype_b=*3B]"'
    meta = (
        "members,tier,age_of_action,sex,drug\n"
        + f"{member},,ADULT,,azathioprine\n{member},,CHILD,male,Azathioprine\n"
    )
    spec = _drug_module(tmp_path, "scope", meta)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    frame = pl.read_parquet(tmp_path / "out" / "meta_resolved.parquet")
    scoped = {(r["sex"], r["drug"]): r["age_of_action"] for r in frame.iter_rows(named=True) if r["drug"]}
    assert scoped == {(None, "azathioprine"): "ADULT", ("male", "azathioprine"): "CHILD"}
    assert {drug_key(drug) for _sex, drug in scoped} == {"azathioprine"}


def test_a_table_new_in_0_8_refuses_a_duplicate_written_two_ways_and_an_older_one_does_not(
    tmp_path: Path,
) -> None:
    """`meta.csv` is held by no published module, so its key compares through the keys; `diplotypes.csv`
    is, so its refusal stays on the stored cell (Principle 3) and two case spellings stay two rows."""
    member = '"diplotypes[gene=TPMT, haplotype_b=*3B]"'
    meta = _write(
        tmp_path / "meta",
        {
            "haplotypes.csv": _HAPLOTYPES,
            "diplotypes.csv": _DIPLOTYPES,
            "meta.csv": _META_HEADER + f"{member},,ADULT,azathioprine\n{member},,CHILD,Azathioprine\n",
        },
    )
    refused = validate_spec(meta, resolve_with_ensembl=False)
    assert [e for e in refused.errors if "meta.csv: duplicate row for key" in e], refused.errors
    dips = _DIPLOTYPES + "Tpmt,*1,*3B,Intermediate Metabolizer,Azathioprine,Reduced dose.\n"
    older = _write(tmp_path / "older", {"haplotypes.csv": _HAPLOTYPES, "diplotypes.csv": dips})
    assert not [e for e in validate_spec(older, resolve_with_ensembl=False).errors if "duplicate row" in e]


def test_a_meta_selector_names_a_drug_in_any_case(tmp_path: Path) -> None:
    spec = _drug_module(
        tmp_path, "selector", _META_HEADER + '"diplotypes[drug=Azathioprine, haplotype_b=*3B]",,ADULT,\n'
    )
    result = validate_spec(spec, resolve_with_ensembl=False)
    assert "meta_selector_matches_nothing" not in _codes(result)


# ── round trip: two spellings of each kind survive compile → reverse → compile ─────────────────────


def test_two_spellings_of_every_kind_round_trip_to_a_fixed_point(tmp_path: Path) -> None:
    spec = _drug_module(
        tmp_path,
        "rt",
        _META_HEADER + '"diplotypes[gene=tpmt, haplotype_b=*3B]",,ADULT,Azathioprine\n',
    )
    rows = _rows(spec / "diplotypes.csv")
    rows[1]["gene"], rows[1]["drug"] = "Tpmt", "Azathioprine"
    _write_rows(spec / "diplotypes.csv", rows)
    (spec / "variants.csv").write_text(_VARIANT.format(c="chr12"), encoding="utf-8")
    (spec / "studies.csv").write_text(
        "chrom,start,ref,pmid,doi\nchr12,111446804,C,NONE,10.1101/2024.01.01.123456.\n", encoding="utf-8"
    )
    first = compile_module(spec, tmp_path / "a1", resolve_with_ensembl=False)
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2", resolve_with_ensembl=False)
    assert second.success, second.errors
    assert (second.manifest.artifact.digest, second.manifest.content_signature) == (
        first.manifest.artifact.digest,
        first.manifest.content_signature,
    )
    studies = pl.read_parquet(tmp_path / "a1" / "studies.parquet")
    assert studies["chrom"].to_list() == ["12"]
    diplotypes = pl.read_parquet(tmp_path / "a1" / "diplotypes.parquet")
    assert sorted(diplotypes["gene"].to_list()) == ["TPMT", "Tpmt"]  # stored verbatim
