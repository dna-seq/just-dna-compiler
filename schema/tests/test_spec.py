"""DSL spec model tests — validation mirrors the authored module_spec.yaml / CSV rules."""

import pytest
from pydantic import ValidationError

from just_dna_format.spec import ModuleInfo, ModuleSpecConfig, StudyRow, VariantRow


def test_module_info_reuses_name_and_color_rules() -> None:
    ModuleInfo(name="coronary", title="T", description="d", report_title="R", color="#21ba45")
    with pytest.raises(ValidationError):
        ModuleInfo(name="Bad Name", title="T", description="d", report_title="R")
    with pytest.raises(ValidationError):
        ModuleInfo(name="ok", title="T", description="d", report_title="R", color="red")


def test_variant_requires_an_identifier() -> None:
    with pytest.raises(ValidationError):
        VariantRow(genotype="A/G", state="risk", conclusion="c")  # no rsid, no position


def test_variant_key_and_genotype_rules() -> None:
    v = VariantRow(rsid="rs1801133", genotype="A/G", state="risk", conclusion="c")
    assert v.variant_key == "rs1801133"
    with pytest.raises(ValidationError):
        VariantRow(rsid="rs1", genotype="G/A", state="risk", conclusion="c")  # not sorted
    with pytest.raises(ValidationError):
        VariantRow(rsid="bad", genotype="A/G", state="risk", conclusion="c")  # rsid pattern


def test_spec_config_rejects_unknown_schema_version() -> None:
    module = {"name": "m", "title": "T", "description": "d", "report_title": "R"}
    ModuleSpecConfig(module=module)  # default schema_version ok
    with pytest.raises(ValidationError):
        ModuleSpecConfig(schema_version="9.9", module=module)


def test_config_models_reject_unknown_keys() -> None:
    """The `module_spec.yaml` container models forbid extras, so an authored typo is a hard error
    rather than a silently dropped key. The `genome_build` case is safety-relevant: a typo'd key
    would otherwise leave the build at its GRCh38 default (wrong-assembly resolution)."""
    module = {"name": "m", "title": "T", "description": "d", "report_title": "R"}
    with pytest.raises(ValidationError):
        ModuleSpecConfig(module=module, genome_bild="GRCh37")  # top-level typo
    with pytest.raises(ValidationError):
        ModuleSpecConfig(module=module, defaults={"currator": "bob"})  # defaults typo
    with pytest.raises(ValidationError):
        ModuleInfo(name="m", title="T", description="d", report_title="R", colour="#21ba45")


def test_study_requires_pmid_and_identifier() -> None:
    StudyRow(rsid="rs1", pmid="12345")
    with pytest.raises(ValidationError):
        StudyRow(pmid="")  # empty pmid and no identifier


def test_start_position_must_be_non_negative() -> None:
    # start is materialized as an unsigned parquet column; a negative position is a clean
    # validation error rather than a downstream polars overflow.
    VariantRow(chrom="1", start=0, genotype="A/G", state="risk", conclusion="c")
    with pytest.raises(ValidationError):
        VariantRow(chrom="1", start=-1, genotype="A/G", state="risk", conclusion="c")
    with pytest.raises(ValidationError):
        StudyRow(chrom="1", start=-1, pmid="12345")


def test_p_value_num_must_be_a_probability() -> None:
    StudyRow(rsid="rs1", pmid="12345", p_value_num=1.0)      # p == 1 is legal
    StudyRow(rsid="rs1", pmid="12345", p_value_num=5e-8)
    for bad in (0.0, -1e-8, 1.5):
        with pytest.raises(ValidationError):
            StudyRow(rsid="rs1", pmid="12345", p_value_num=bad)


def test_neg_log10_p_is_derived_and_ordered() -> None:
    def study(p: float) -> StudyRow:
        return StudyRow(rsid="rs1", pmid="12345", p_value_num=p)

    assert StudyRow(rsid="rs1", pmid="12345").neg_log10_p is None
    assert study(1.0).neg_log10_p == 0.0     # p == 1 → 0, and not the -0.0 of a bare negation
    assert study(1e-8).neg_log10_p == 8.0    # exact on a power of ten
    # Monotone decreasing in p: a smaller p-value is a larger -log10, so ordering by the derived
    # column ascending reproduces the p-values descending.
    ps = [0.05, 5e-8, 1e-30]
    assert ps == sorted(ps, key=lambda p: study(p).neg_log10_p)
    assert study(1e-30).neg_log10_p > study(5e-8).neg_log10_p > study(0.05).neg_log10_p


def test_non_finite_floats_rejected() -> None:
    # NaN/inf break round-trip equality (needs_upgrade oscillation) and serialize to non-reloadable
    # cells; an authored numeric field is always finite.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            VariantRow(rsid="rs1", genotype="A/G", state="risk", conclusion="c", weight=bad)
        with pytest.raises(ValidationError):
            VariantRow(rsid="rs1", genotype="A/G", state="risk", conclusion="c", effect_size=bad)
        with pytest.raises(ValidationError):
            StudyRow(rsid="rs1", pmid="12345", effect_size=bad)
