"""longevitymap v2's own study rows, in the final 0.8 shape, compile (PT2 §6 `longevity_studies`).

`docs/probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` Appendix 2 writes v2's evidence as full `studies.csv` rows
against the columns the 0.8 `StudyRow` batch was decided to have: examples 5 (one paper, three classes),
6 (one class, two analyses; a parent-sex stratum), 7 (lives against individuals), 8 (three age bands,
the top one open), 9 (a study measured on an LD proxy) and 11 (a preprint cited by DOI). The first
run's example 13 (one estimate in one stratum) is the stratum case Appendix 2 folded into prose. Each is
its own module, verbatim but for the one adaptation the final names need (the appendix's `# comment`
lines are dropped), enriched offline from the leads' and the proxy's real snapshot rows — it lives in the
enricher's suite because `--strict` needs the `resolution.csv` only `enrich` writes — and each must:

* validate under `--strict` and compile with no `duplicate_study_citation`;
* carry every authored cell into `studies.parquet`;
* survive `compile → reverse → compile` to the same `artifact.digest` and `content_signature`.

The locus columns each example exists to feed are asserted on `weights.parquet` beside it. Example 11's
second row — a DOI written into `pmid` — is the appendix's own refusal, asserted as one.
"""

import csv
import io
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, content_signature, reverse_module, validate_spec
from just_dna_enricher.enrich import enrich

_MODULE = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: longevity_studies\n"
    "  title: longevity studies\n"
    "  description: longevitymap v2 study rows in the 0.8 shape\n"
    "  report_title: longevity studies\n"
    "genome_build: GRCh38\n"
)

#: One `variants.csv` row per lead the examples cite, so no study row is an orphan.
_VARIANTS = (
    "rsid,genotype,state,conclusion\n"
    "rs10455872,A/G,protective,carrier of the LPA allele\n"
    "rs7412,C/T,protective,APOE e2 carrier\n"
    "rs74444983,C/T,neutral,carrier\n"
    "rs646776,G/G,protective,CELSR2/PSRC1 locus\n"
    "rs75571981,C/T,neutral,EYS carrier\n"
    "rs2802292,G/T,protective,FOXO3 carrier\n"
)

#: The examples' CSV blocks, as Appendix 2 prints them.
_EXAMPLES: dict[str, str] = {
    "5_two_classes_one_paper": """\
rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,p_value,sample_size,sample_unit,statistical_test
rs10455872,32678081,EXTREME_SURVIVAL_CC,A,0.124,log(OR),log-odds per allele,7e-03,,,longevity component of MANOVA
rs10455872,32678081,PARENTAL_LIFESPAN,A,0.076,beta,-ln HR per allele,9e-25,1012240,lives,parental lifespan component
rs10455872,32678081,HEALTHSPAN,A,0.057,beta,-ln HR per allele,1e-10,300447,individuals,healthspan component
""",
    "6_analyses_and_parent_sex": """\
rsid,pmid,phenotype_class,effect_size,effect_measure,n_cases,sample_size,sample_unit,age_of,stratum,stratum_level,statistical_test
rs7412,31413261,EXTREME_SURVIVAL_CC,1.28,OR,11262,36745,individuals,participant,,,">=90th percentile vs <=60th"
rs7412,31413261,EXTREME_SURVIVAL_CC,1.47,OR,3484,28967,individuals,participant,,,">=99th percentile vs <=60th"
rs74444983,29227965,PARENTAL_LIFESPAN,-0.0143,beta,,389166,individuals,parent,parent_sex,father,"BOLT-LMM fathers_attained"
""",
    "7_lives_and_individuals": """\
rsid,pmid,phenotype_class,sample_size,sample_unit
rs10455872,30642433,PARENTAL_LIFESPAN,1012240,lives
rs74444983,29227965,PARENTAL_LIFESPAN,389166,individuals
""",
    "8_age_bands": """\
rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.1089,beta,log protection ratio per allele,40,60,parent
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.0778,beta,log protection ratio per allele,60,80,parent
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.0530,beta,log protection ratio per allele,80,,parent
""",
    "9_ld_proxy": """\
rsid,pmid,proxy_rsid,ancestry,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of
rs646776,30642433,rs4970836,EUR,G,0.2234,beta,years of parental lifespan per allele,,,parent
""",
    "11_preprint_by_doi": """\
rsid,pmid,doi,phenotype_class,effect_size,effect_measure
rs75571981,NONE,10.21203/rs.3.rs-6869504/v1,EXTREME_SURVIVAL_CC,,NR
""",
    "13_one_stratum": """\
rsid,pmid,ancestry,stratum,stratum_level,effect_measure,statistical_test
rs2802292,41837379,EUR,sex,male,NR,"men with hypertension/diabetes/angina"
""",
}


#: The leads and the one proxy exactly as the provisioned Ensembl snapshot carries them (GRCh38, `alt`
#: pipe-joined as the snapshot writes it), read off it on 2026-11-04. Domain constants, so the run is
#: offline and deterministic; `enrich` turns them into the module's `resolution.csv` by its real path.
_SNAPSHOT = {
    "id": ["rs646776", "rs4970836", "rs7412", "rs74444983", "rs75571981", "rs2802292", "rs10455872"],
    "chrom": ["1", "1", "19", "19", "6", "6", "6"],
    "start": [109275908, 109279175, 44908822, 45242349, 63910997, 108587315, 160589086],
    "ref": ["C", "G", "C", "T", "T", "G", "A"],
    "alt": ["G|T", "A|C", "T", "C|G", "C", "T", "G"],
}


def _module(tmp_path: Path, name: str, studies: str, *, enriched: bool = True) -> Path:
    """The example as a module, enriched from the snapshot rows so `--strict` has its coordinates."""
    spec = tmp_path / name
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_MODULE)
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(studies)
    if not enriched:
        return spec
    cache = tmp_path / f"{name}_cache"
    (cache / "data").mkdir(parents=True)
    pl.DataFrame(_SNAPSHOT).write_parquet(cache / "data" / "snapshot.parquet")
    enrich(spec, offline=True, ensembl_cache=cache, clinvar_cache=tmp_path, mint_vrs=False)
    return spec


def _authored(studies: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(studies)))


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _same(authored: str, stored: str) -> bool:
    """One cell, compared on its value: `0.0530` is stored as `0.053`, `40` as `40.0`."""
    if authored == stored:
        return True
    try:
        return float(authored) == float(stored)
    except ValueError:
        return False


@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_each_example_validates_strictly_and_compiles_without_a_duplicate(tmp_path: Path, name: str) -> None:
    spec = _module(tmp_path, name, _EXAMPLES[name])
    validation = validate_spec(spec, strict=True)
    assert validation.valid, validation.errors
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    summary = result.manifest.compilation.warnings_summary
    assert "duplicate_study_citation" not in summary
    assert "phenotype_class_unrecognized" not in summary


@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_every_authored_cell_reaches_studies_parquet(tmp_path: Path, name: str) -> None:
    spec = _module(tmp_path, name, _EXAMPLES[name])
    assert compile_module(spec, tmp_path / "out").success
    stored = pl.read_parquet(tmp_path / "out" / "studies.parquet").to_dicts()
    authored = _authored(_EXAMPLES[name])
    assert len(stored) == len(authored)
    for row, parquet_row in zip(authored, stored, strict=True):
        for column, value in row.items():
            assert _same(value, _cell(parquet_row[column])), (column, value, parquet_row[column])


@pytest.mark.parametrize("name", sorted(_EXAMPLES))
def test_each_example_round_trips_to_a_fixed_point(tmp_path: Path, name: str) -> None:
    spec = _module(tmp_path, name, _EXAMPLES[name])
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2")
    assert second.success, second.errors
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "rev") == content_signature(spec)


def _locus(tmp_path: Path, name: str, rsid: str) -> dict[str, object]:
    spec = _module(tmp_path, name, _EXAMPLES[name])
    assert compile_module(spec, tmp_path / "w").success
    rows = pl.read_parquet(tmp_path / "w" / "weights.parquet").filter(pl.col("rsid") == rsid).to_dicts()
    assert rows
    return rows[0]


def test_example_5_fills_all_three_outcome_cells_and_withholds_the_unit(tmp_path: Path) -> None:
    """Three classes from one paper studied all three outcomes; two units disagree, so no unit joins."""
    row = _locus(tmp_path, "5_two_classes_one_paper", "rs10455872")
    assert (row["outcome_healthspan"], row["outcome_lifespan"], row["outcome_exceptional"]) == (
        True,
        True,
        True,
    )
    assert row["effect_unit"] is None
    # No row states an ancestry, so whether the evidence is European-only is unknown.
    assert row["eur_only_evidence"] is None


def test_example_8_joins_the_one_unit_its_bands_share(tmp_path: Path) -> None:
    row = _locus(tmp_path, "8_age_bands", "rs10455872")
    assert row["effect_unit"] == "log protection ratio per allele"
    assert (row["outcome_lifespan"], row["outcome_healthspan"], row["outcome_exceptional"]) == (
        True,
        None,
        None,
    )


def test_example_9_is_european_only_evidence(tmp_path: Path) -> None:
    row = _locus(tmp_path, "9_ld_proxy", "rs646776")
    assert row["eur_only_evidence"] is True
    assert row["effect_unit"] == "years of parental lifespan per allele"


def test_example_11s_doi_in_pmid_is_refused(tmp_path: Path) -> None:
    """The appendix's second row: a DOI written into `pmid` instead of `NONE` + `doi`."""
    spec = _module(
        tmp_path,
        "11_refused",
        "rsid,pmid,doi,phenotype_class,effect_size,effect_measure\n"
        "rs75571981,10.21203/rs.3.rs-6869504/v1,,EXTREME_SURVIVAL_CC,,NR\n",
        # `enrich` reads studies.csv for proxies since 0.8 and refuses the same row first; the compile
        # is the refusal the appendix names.
        enriched=False,
    )
    result = compile_module(spec, tmp_path / "out")
    assert not result.success
    assert any("10.21203/rs.3.rs-6869504/v1" in e for e in result.errors), result.errors


def test_examples_7_and_8_together_flag_the_unbanded_estimate(tmp_path: Path) -> None:
    """Written into one module, example 7's whole-sample row and example 8's bands share a key.

    The whole-sample row states no band and no analysis, so nothing establishes that it is a separate
    claim from a banded one: it warns, by the Kleene rule, until its `statistical_test` says what it is.
    """
    banded = _EXAMPLES["8_age_bands"].splitlines()
    whole = "rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of"
    assert banded[0] == whole
    rows = [whole, "rs10455872,30642433,PARENTAL_LIFESPAN,,,,,,,", *banded[1:]]
    spec = _module(tmp_path, "7_and_8", "\n".join(rows) + "\n")
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert result.manifest.compilation.warnings_summary.get("duplicate_study_citation") == 3
