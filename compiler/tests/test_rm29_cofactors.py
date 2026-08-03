"""RM29 cofactor columns (0.5.1) — a quality floor on `VariantRow`, a clinical context on `DiplotypeRow`.

Both are cofactors carried as **columns**, because a row's columns already conjoin: no predicate
language, no evaluator, nothing to sandbox (P1). The two halves answer different questions and are
tested against different failure modes — the floor against half-stated gates, the context against the
duplicate-row collision that made `draft --drug` refuse.
"""

from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from just_dna_compiler.compiler import (
    _TABLE_DUPE_KEYS,
    _load_csv_rows,
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_format.pgx import DiplotypeRow
from just_dna_format.spec import VariantRow

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: cofactors\n"
    "  title: Cofactors\n"
    "  description: RM29 cofactor columns\n"
    "  report_title: Cofactors\n"
)
# A real annotation that genuinely wants a floor: HFE C282Y homozygosity is the one genotype ACMG
# lists HFE for, and it is exactly the call an array with a poor GQ should not be reported from.
_VARIANTS = (
    "rsid,genotype,state,conclusion,gene,requires_callable,callable_from,quality_from,min_quality\n"
    "rs1800562,A/A,risk,HFE C282Y homozygote,HFE,,,GQ,20\n"
    "rs1799945,C/G,risk,HFE H63D heterozygote,HFE,true,DP,,\n"
)
_STUDIES = "rsid,pmid\nrs1800562,10453733\n"
# The clopidogrel case RM29b exists for: one gene, one drug, one phenotype, three settings that
# disagree about how firmly to act.
_DIPLOTYPES = (
    "gene,haplotype_a,haplotype_b,phenotype,conclusion,drug,recommendation_strength,clinical_context\n"
    "CYP2C19,*2,*2,Poor Metabolizer,Avoid standard dose,clopidogrel,strong,CVI ACS PCI\n"
    "CYP2C19,*2,*2,Poor Metabolizer,Consider alternative,clopidogrel,moderate,CVI non-ACS non-PCI\n"
    "CYP2C19,*2,*2,Poor Metabolizer,Avoid standard dose,clopidogrel,strong,NVI\n"
)


def _write(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    (d / "diplotypes.csv").write_text(_DIPLOTYPES, encoding="utf-8")
    return d


# ── RM29(a): the quality floor ─────────────────────────────────────────────────────────────────


def _variant(**kwargs) -> VariantRow:
    base = dict(rsid="rs1800562", genotype="A/A", state="risk", conclusion="c")
    return VariantRow(**{**base, **kwargs})


def test_a_floor_needs_both_halves_or_neither() -> None:
    assert _variant().min_quality is None
    assert _variant(quality_from="GQ", min_quality=20).min_quality == 20

    with pytest.raises(ValidationError, match="min_quality is empty"):
        _variant(quality_from="GQ")
    with pytest.raises(ValidationError, match="quality_from is empty"):
        _variant(min_quality=20)


def test_the_pointer_uses_the_shared_grammar_not_a_new_one() -> None:
    """`quality_from` joins `source_field`/`callable_from` on `AuthoredModel`, so a bad token is
    rejected the same way in all three rather than by a third private rule."""
    assert _variant(quality_from="GQ|DP", min_quality=20).quality_from == "GQ|DP"
    with pytest.raises(ValidationError):
        _variant(quality_from="GQ >= 20", min_quality=20)  # an expression, not a pointer


def test_a_floor_must_be_a_real_number() -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            _variant(quality_from="GQ", min_quality=bad)


def test_the_floor_is_not_the_dropped_caller_names() -> None:
    """RM29 distinguishes them explicitly, and the reserved-namespace guard still holds the line."""
    with pytest.raises(ValidationError):
        _variant(caller="gatk")


def test_the_floor_materializes_and_round_trips(tmp_path: Path) -> None:
    spec = _write(tmp_path / "spec")
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors

    weights = pl.read_parquet(tmp_path / "out" / "weights.parquet")
    floored = weights.filter(pl.col("rsid") == "rs1800562").row(0, named=True)
    assert floored["quality_from"] == "GQ" and floored["min_quality"] == 20.0
    # The other row states no floor, and an absent floor is null rather than zero — a zero floor
    # would be a gate that everything clears, which is a different statement from "no gate".
    unfloored = weights.filter(pl.col("rsid") == "rs1799945").row(0, named=True)
    assert unfloored["quality_from"] is None and unfloored["min_quality"] is None
    assert unfloored["callable_from"] == "DP"

    reverse_module(tmp_path / "out", tmp_path / "rev")
    emitted = (tmp_path / "rev" / "variants.csv").read_text(encoding="utf-8")
    assert "quality_from" in emitted.splitlines()[0] and "min_quality" in emitted.splitlines()[0]
    rows, errors, _ = _load_csv_rows(tmp_path / "rev" / "variants.csv", VariantRow, "variants.csv")
    assert not errors, errors
    assert [(r.quality_from, r.min_quality) for r in rows] == [("GQ", 20.0), (None, None)]


# ── RM29(b): the clinical context ──────────────────────────────────────────────────────────────


def test_cpics_trailing_whitespace_would_otherwise_split_one_setting_in_two() -> None:
    """Three of CPIC's sixteen live values carry trailing whitespace, and the column is in the key."""
    padded = DiplotypeRow(
        gene="CYP2C19", haplotype_a="*2", haplotype_b="*2", conclusion="c",
        drug="clopidogrel", clinical_context="CVI ACS PCI ",
    )
    clean = DiplotypeRow(
        gene="CYP2C19", haplotype_a="*2", haplotype_b="*2", conclusion="c",
        drug="clopidogrel", clinical_context="CVI ACS PCI",
    )
    key = _TABLE_DUPE_KEYS[DiplotypeRow]
    assert padded.clinical_context == "CVI ACS PCI"
    assert key(padded) == key(clean)
    # An all-whitespace cell is an absence, not a context named " ".
    assert DiplotypeRow(
        gene="G", haplotype_a="*1", haplotype_b="*1", conclusion="c", clinical_context="   ",
    ).clinical_context is None


def test_the_context_is_not_the_ancestry_population_column() -> None:
    """`FrequencyRow.population` is an ancestry group with a validated vocabulary; this is not that,
    and giving the two one name across two tables is the overloaded-axis mistake (P5)."""
    from just_dna_format.frequency import FrequencyRow

    assert "population" not in DiplotypeRow.model_fields
    assert "clinical_context" not in FrequencyRow.model_fields
    # And unlike the ancestry column, this one is open: CPIC's real values are indications, age bands,
    # prior-treatment status and dose bands, and the next guideline body will scope differently.
    assert DiplotypeRow.model_fields["clinical_context"].json_schema_extra is None


def test_three_disagreeing_contexts_survive_the_compile_as_three_rows(tmp_path: Path) -> None:
    spec = _write(tmp_path / "spec")
    assert validate_spec(spec).valid, validate_spec(spec).errors
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors

    diplotypes = pl.read_parquet(tmp_path / "out" / "diplotypes.parquet")
    assert diplotypes.height == 3
    assert set(diplotypes["clinical_context"]) == {"CVI ACS PCI", "CVI non-ACS non-PCI", "NVI"}
    # They really disagree — which is what collapsing them would have destroyed.
    assert set(diplotypes["recommendation_strength"]) == {"strong", "moderate"}


def test_without_the_context_the_same_three_rows_are_duplicates(tmp_path: Path) -> None:
    """The failure RM29b removes, demonstrated rather than asserted: strip the column and the
    compiler rejects the very rows CPIC publishes."""
    spec = _write(tmp_path / "spec")
    stripped = "\n".join(
        line.rsplit(",", 1)[0] for line in _DIPLOTYPES.strip().splitlines()
    ) + "\n"
    (spec / "diplotypes.csv").write_text(stripped, encoding="utf-8")
    result = compile_module(spec, tmp_path / "out2", resolve_with_ensembl=False)
    assert not result.success
    assert any("duplicate" in e.lower() for e in result.errors), result.errors


def test_the_context_round_trips_and_the_signature_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _write(tmp_path / "spec")
    first = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert first.success, first.errors

    reverse_module(tmp_path / "out", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "out2", resolve_with_ensembl=False)
    assert second.success, second.errors

    assert content_signature(tmp_path / "out") == content_signature(tmp_path / "out2")
    emitted = pl.read_parquet(tmp_path / "out2" / "diplotypes.parquet")
    assert set(emitted["clinical_context"]) == {"CVI ACS PCI", "CVI non-ACS non-PCI", "NVI"}


# ── both: the authoring surface must offer them ────────────────────────────────────────────────


def test_the_new_columns_reach_a_blank_template_and_the_authoring_reference() -> None:
    from just_dna_compiler.draft import blank_template
    from just_dna_format.reference import authoring_reference

    header = blank_template("variants.csv").splitlines()[0].split(",")
    assert {"quality_from", "min_quality"} <= set(header)
    assert "variant_key" not in header and "authored_ident" not in header

    assert "clinical_context" in blank_template("diplotypes.csv").splitlines()[0].split(",")

    models = authoring_reference()["models"]
    named = {model: {f["name"] for f in fields} for model, fields in models.items()}
    assert {"quality_from", "min_quality"} <= named["VariantRow"]
    assert "clinical_context" in named["DiplotypeRow"]
