"""`model_organisms.csv` through the real validate, compile and reverse paths (0.8, RM335).

The table is annotation only: it compiles to `model_organisms.parquet`, survives the round trip, is inside
`content_signature`, is keyed and refuses a duplicate, and is not a lead table, so a module carrying only
this file is refused. An uncited row draws no warning (PT2 §3 item 23).

The two model-organism rows are the longevitymap v2 shape audit's (appendix example 12). Every expected
value is read off the fixture the test writes.
"""

import csv
import io
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import (
    ARTIFACT_PARQUETS,
    LEAD_PARQUETS,
    compile_module,
    content_signature,
    load_citing_rows,
    reverse_module,
    table_citations,
    validate_spec,
)
from just_dna_format.meta import META_MEMBER_TABLES

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: model_organism_probe\n"
    "  title: Model organism probe\n"
    "  description: PPARG Pro12Ala with the mouse evidence beside it\n"
    "  report_title: Model organism probe\n"
    "genome_build: GRCh38\n"
)

# Coordinate-authored, so the row has a position with no resolution table injected.
_VARIANTS = """rsid,chrom,start,ref,alts,genotype,state,conclusion,gene
rs1801282,3,12351626,C,G,C/G,protective,One Ala12 allele.,PPARG
rs1801282,3,12351626,C,G,G/G,protective,Two Ala12 alleles.,PPARG
"""
_STUDIES = "rsid,pmid\nrs1801282,10973253\n"

_HEADER = "gene,orthologue,species,model_type,sex,diet,lifespan_effect,concordance,pmid,doi\n"
_PPARG = "PPARG,Pparg,Mus musculus,knock-in Pro12Ala,,high-fat,benefit lost on high-fat diet,nonmonotone,19117549,\n"
_IGF1R = "IGF1R,Igf1r,Mus musculus,heterozygous knockout,female,,+33% (female),concordant,,\n"
_ROWS = _HEADER + _PPARG + _IGF1R


def _module(directory: Path, model_organisms: str | None = _ROWS, *, core: bool = True) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    if core:
        (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
        (directory / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    if model_organisms is not None:
        (directory / "model_organisms.csv").write_text(model_organisms, encoding="utf-8")
    return directory


def _compile(spec: Path, out: Path, **kwargs):
    result = compile_module(spec, out, **kwargs)
    assert result.success, result.errors
    return result


def _csv_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def test_the_audit_rows_compile_to_their_parquet_in_authored_order(tmp_path: Path) -> None:
    spec = _module(tmp_path / "spec")
    result = _compile(spec, tmp_path / "out")
    frame = pl.read_parquet(tmp_path / "out" / "model_organisms.parquet")
    authored = _csv_rows(spec / "model_organisms.csv")
    assert frame["gene"].to_list() == [row["gene"] for row in authored]
    assert frame["concordance"].to_list() == [row["concordance"] for row in authored]
    assert frame["pmid"].to_list() == [row["pmid"] or None for row in authored]
    assert "model_organisms.parquet" in {entry.name for entry in result.manifest.artifact.files}


def test_compile_reverse_compile_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _module(tmp_path / "spec")
    first = _compile(spec, tmp_path / "out1")
    reverse_module(tmp_path / "out1", tmp_path / "reversed")
    assert _csv_rows(tmp_path / "reversed" / "model_organisms.csv") == _csv_rows(spec / "model_organisms.csv")
    second = _compile(tmp_path / "reversed", tmp_path / "out2")
    assert second.manifest.artifact.digest == first.manifest.artifact.digest
    assert second.manifest.content_signature == first.manifest.content_signature
    assert content_signature(tmp_path / "reversed") == content_signature(spec)


def test_the_rows_are_inside_content_signature(tmp_path: Path) -> None:
    # Closes the vacuous reading of the fixed point above: a table the signature never read would also
    # compare equal across laps.
    base = content_signature(_module(tmp_path / "a"))
    edited = content_signature(_module(tmp_path / "b", _ROWS.replace("+33% (female)", "+26% (female)")))
    assert base != edited
    assert content_signature(_module(tmp_path / "c", None)) != base


def test_two_compiles_are_byte_identical(tmp_path: Path) -> None:
    spec = _module(tmp_path / "spec")
    first = _compile(spec, tmp_path / "out1")
    second = _compile(spec, tmp_path / "out2")
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert (tmp_path / "out1" / "model_organisms.parquet").read_bytes() == (
        tmp_path / "out2" / "model_organisms.parquet"
    ).read_bytes()


def test_the_same_experiment_twice_is_a_duplicate_key(tmp_path: Path) -> None:
    contradicting = _IGF1R.replace("+33% (female)", "no change").replace("concordant", "discordant")
    spec = _module(tmp_path / "spec", _ROWS + contradicting)
    result = validate_spec(spec)
    duplicate = [e for e in result.errors if "model_organisms.csv" in e and "uplicate" in e]
    assert duplicate, result.errors
    assert not compile_module(spec, tmp_path / "out").success


def test_a_male_cohort_beside_a_female_one_is_two_rows(tmp_path: Path) -> None:
    male = _IGF1R.replace(",female,", ",male,").replace("+33% (female)", "no change")
    result = validate_spec(_module(tmp_path / "spec", _ROWS + male))
    assert not result.errors, result.errors


def test_a_concordance_outside_the_vocabulary_is_refused(tmp_path: Path) -> None:
    result = validate_spec(_module(tmp_path / "spec", _ROWS.replace("concordant", "unclear")))
    assert any("model_organisms.csv" in e and "concordance must be one of" in e for e in result.errors), (
        result.errors
    )


def test_an_uncited_row_draws_no_warning(tmp_path: Path) -> None:
    # The IGF1R row has neither pmid nor doi. Equality against the same module without the table, so the
    # assertion is "the table adds nothing to the warnings", not "no warning happens to mention it".
    uncited_only = _HEADER + _IGF1R
    with_table = _compile(_module(tmp_path / "with", uncited_only), tmp_path / "out_with")
    without = _compile(_module(tmp_path / "without", None), tmp_path / "out_without")
    assert sorted(with_table.warnings) == sorted(without.warnings)
    assert sorted(validate_spec(tmp_path / "with").warnings) == sorted(
        validate_spec(tmp_path / "without").warnings
    )


def test_a_cited_rows_pmid_is_a_citation_site(tmp_path: Path) -> None:
    spec = _module(tmp_path / "spec")
    citing = load_citing_rows(spec)
    assert [row.gene for row in citing["model_organisms.csv"]] == ["PPARG", "IGF1R"]
    assert "19117549" in table_citations(citing)


def test_model_organisms_alone_is_not_a_module(tmp_path: Path) -> None:
    result = validate_spec(_module(tmp_path / "spec", core=False))
    assert any("module has no recognized table" in e for e in result.errors), result.errors


def test_a_present_but_empty_table_is_refused(tmp_path: Path) -> None:
    result = validate_spec(_module(tmp_path / "spec", _HEADER))
    assert any("model_organisms.csv is present but has no rows" in e for e in result.errors), result.errors


def test_it_never_reaches_a_lead_table_a_meta_member_or_the_gene_facet(tmp_path: Path) -> None:
    assert "model_organisms.parquet" in ARTIFACT_PARQUETS
    assert "model_organisms.parquet" not in LEAD_PARQUETS
    assert "model_organisms" not in META_MEMBER_TABLES
    result = _compile(_module(tmp_path / "spec"), tmp_path / "out")
    # IGF1R is named only by the model-organism table: evidence beside the findings, not a gene the
    # module's findings are about.
    assert "IGF1R" not in result.manifest.stats.genes
