"""RM366: a field meaningless without its companion is never accepted half-stated.

The class: a value whose meaning is another column — a statistic and the method that computed it, a
witness and its verdict, a magnitude and its instrument, a qualifier and what it qualifies. Each pair
used to be either unchecked or checked by a validator written by hand on its own model, so the rule
lived in eight places and was missing wherever nobody had written one. It is now one declaration per model
(`_PAIRED_FIELDS`, `base.Companion`) read by one shared validator, and these tests walk every model's
declaration rather than the instances the audit happened to find.
"""

import pytest
from just_dna_format.base import (
    AuthoredModel,
    Companion,
    PairedFields,
    field_first_seen,
    half_stated,
    paired_fields,
)
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.locus_genes import ColocalisationRow
from just_dna_format.reference import _ALL_MODELS
from just_dna_format.resolution import ResolutionRow
from pydantic import BaseModel, ValidationError

# ── the audit's instances, constructed exactly as the audit did ─────────────────────────────────────


def _gwas(**cells: object) -> GwasEffectRow:
    return GwasEffectRow(association_id="1", variant_key="rs1", dataset="gwas_catalog_2026-08-01", **cells)


def _coloc(**cells: object) -> ColocalisationRow:
    return ColocalisationRow(
        study_locus_id="left",
        right_study_locus_id="right",
        variant_key="rs1",
        dataset="opentargets_26.09",
        **cells,
    )


@pytest.mark.parametrize(
    ("build", "cells", "named"),
    [
        (_gwas, {"posterior_probability": 0.42}, "fine_mapping_method"),
        (_gwas, {"fine_mapping_method": "SuSiE-inf"}, "posterior_probability"),
        (_coloc, {"h4": 0.9}, "method"),
        (_coloc, {"clpp": 0.2}, "method"),
        (
            lambda **c: ResolutionRow(variant_key="rs1", **c),
            {"placement_witness": "clinvar"},
            "placement_verdict",
        ),
        (
            lambda **c: ResolutionRow(variant_key="rs1", **c),
            {"placement_verdict": "same_event"},
            "placement_witness",
        ),
    ],
    ids=[
        "posterior-without-method",
        "method-without-posterior",
        "h4-without-method",
        "clpp-without-method",
        "witness-without-verdict",
        "verdict-without-witness",
    ],
)
def test_the_audits_half_pairs_are_refused(build, cells: dict, named: str) -> None:
    with pytest.raises(ValidationError, match=named):
        build(**cells)


def test_a_statistic_with_its_method_still_loads() -> None:
    """The refusal is about the half, not the pair: both halves together are the ordinary row."""
    assert (
        _gwas(posterior_probability=0.42, fine_mapping_method="SuSiE-inf").fine_mapping_method == "SuSiE-inf"
    )
    assert _coloc(method="COLOC_PIP_ECAVIAR", h4=0.9, clpp=0.2).h4 == 0.9
    # A method with no statistic is a pair the source reported without numbers — harmless, kept.
    assert _coloc(method="COLOC_PIP_ECAVIAR").method == "COLOC_PIP_ECAVIAR"
    row = ResolutionRow(variant_key="rs1", placement_witness="clinvar", placement_verdict="unplaced")
    assert row.placement_verdict == "unplaced"


# ── the class, walked over every model's declaration ────────────────────────────────────────────────

#: A minimal valid row per model that declares a companion — and only those, asserted below as an
#: equality, so a model gaining its first pair cannot go untested.
_BASE_ROWS: dict[str, dict[str, object]] = {
    "VariantRow": {"rsid": "rs1801133", "genotype": "C/T", "state": "risk", "conclusion": "x"},
    "StudyRow": {"rsid": "rs1801133", "pmid": "12345"},
    "MetaRow": {"members": "variants[rsid=rs1801133]", "conclusion": "x"},
    "MeasureBinRow": {"measure_kind": "repeat_count", "measure_min": 40, "conclusion": "x"},
    "ActivityPhenotypeRow": {"gene": "CYP2D6", "measure_min": 0, "measure_max": 0, "conclusion": "x"},
    "CopyNumberRow": {"gene": "SMN1", "measure_min": 0, "measure_max": 0, "conclusion": "x"},
    "RepeatAlleleRow": {"gene": "HTT", "repeat_unit": "CAG", "measure_min": 40, "conclusion": "x"},
    "HeteroplasmyRow": {"gene": "MT-TL1", "reference_sequence": "rCRS", "measure_min": 0, "conclusion": "x"},
    "GwasEffectRow": {"association_id": "1", "variant_key": "rs1", "dataset": "gwas_catalog_2026-08-01"},
    "ColocalisationRow": {
        "study_locus_id": "left",
        "right_study_locus_id": "right",
        "variant_key": "rs1",
        "dataset": "opentargets_26.09",
    },
    "ResolutionRow": {"variant_key": "rs1"},
    "ClinSigAuthorityCallRow": {
        "variant_key": "rs1",
        "genotype": "C/T",
        "authority": "clinvar",
        "status": "no_record",
    },
}

#: A legal value for every column any companion rule names, keyed by column. Equality again: a rule
#: naming a column with no value here fails, so the walk cannot skip a pair it has no value for.
_SAMPLE: dict[str, object] = {
    "quality_from": "FORMAT/GQ",
    "min_quality": 20.0,
    "effect_size": 1.3,
    "effect_measure": "OR",
    "confidence": "accepted",
    "confidence_unit": "civic_evidence_status",
    "sample_size": 1000,
    "sample_unit": "individuals",
    "stratum": "sex",
    "stratum_level": "male",
    "trait_role": "mediator",
    "trait_efo_id": "EFO_0004611",
    "source_element": "largest",
    "source_field": "FORMAT/REPCN",
    "modifier_gene": "SMN2",
    "modifier_copy_number": 2.0,
    "modifier_cn": 2,
    "posterior_probability": 0.42,
    "fine_mapping_method": "SuSiE-inf",
    "h4": 0.9,
    "clpp": 0.1,
    "method": "COLOC_PIP_ECAVIAR",
    "placement_witness": "clinvar",
    "placement_verdict": "same_event",
}

_PAIRED_MODELS: dict[str, type[BaseModel]] = {
    name: model for name, model in _ALL_MODELS.items() if paired_fields(model)
}
_RULES: list[tuple[str, Companion]] = [
    (name, rule) for name, model in _PAIRED_MODELS.items() for rule in paired_fields(model)
]


def test_every_model_with_a_pair_has_a_base_row_and_every_column_a_sample() -> None:
    assert set(_PAIRED_MODELS) == set(_BASE_ROWS)
    assert {col for _, rule in _RULES for col in (rule.field, *rule.needs)} == set(_SAMPLE)


def test_every_model_declaring_a_pair_runs_the_validator() -> None:
    """A declaration on a model outside `PairedFields` is inert — the shape the class shipped in."""
    inert = {name for name, model in _PAIRED_MODELS.items() if not issubclass(model, PairedFields)}
    assert inert == set()


def test_every_rule_names_columns_the_model_has() -> None:
    missing = {
        (name, col)
        for name, rule in _RULES
        for col in (rule.field, *rule.needs)
        if col not in _PAIRED_MODELS[name].model_fields
    }
    assert missing == set()


@pytest.mark.parametrize(("name", "rule"), _RULES, ids=[f"{n}.{r.field}" for n, r in _RULES])
def test_a_half_stated_pair_is_refused_or_reported_and_the_whole_pair_loads(
    name: str, rule: Companion
) -> None:
    model = _PAIRED_MODELS[name]
    half = {**_BASE_ROWS[name], rule.field: _SAMPLE[rule.field]}
    whole = {**half, rule.needs[0]: _SAMPLE[rule.needs[0]]}
    if rule.refuse:
        with pytest.raises(ValidationError) as caught:
            model(**half)
        assert f"is set and {' or '.join(rule.needs)} is empty" in str(caught.value)
        assert f"{rule.field}=" in str(caught.value)
    else:
        # Reported, never refused: the row loads and the broken rule is what `half_stated` names.
        assert rule in half_stated(model(**half))
    assert rule not in half_stated(model(**whole))


#: The refusing rules on AUTHORED models whose columns are not all new in 0.8 — each one refused
#: before RM366 declared it, so declaring it changed nothing a published module sees. A new entry
#: here is a new refusal on a column a published module may hold half-stated, which P3/P8 forbid
#: inside a major: declare it `refuse=False` instead, and the compiler reports it.
_REFUSING_SINCE_BEFORE_0_8: set[tuple[str, str, tuple[str, ...]]] = {
    ("VariantRow", "quality_from", ("min_quality",)),  # 0.5
    ("VariantRow", "min_quality", ("quality_from",)),  # 0.5
    ("StudyRow", "confidence", ("confidence_unit",)),  # 0.7, RM160
    ("CopyNumberRow", "modifier_gene", ("modifier_copy_number", "modifier_cn")),  # 0.4, both spellings 0.6
    ("CopyNumberRow", "modifier_copy_number", ("modifier_gene",)),  # 0.6
    ("CopyNumberRow", "modifier_cn", ("modifier_gene",)),  # 0.4
    *{
        (kind, "source_element", ("source_field",))
        for kind in (
            "MeasureBinRow",
            "ActivityPhenotypeRow",
            "CopyNumberRow",
            "RepeatAlleleRow",
            "HeteroplasmyRow",
        )
    },  # 0.6, RM54
}


def test_no_new_refusal_lands_on_a_published_authored_column() -> None:
    published = {
        (name, rule.field, rule.needs)
        for name, rule in _RULES
        if rule.refuse
        and issubclass(_PAIRED_MODELS[name], AuthoredModel)
        and any(
            field_first_seen(_PAIRED_MODELS[name]).get(col) != "0.8.0" for col in (rule.field, *rule.needs)
        )
    }
    assert published == _REFUSING_SINCE_BEFORE_0_8


#: The refusing rules on MACHINE-WRITTEN rows whose columns are not all new in 0.8. The audit's brief
#: allows a refusal on a derived table (a pass writes it, and writes both halves or neither); listed
#: here as an equality so that each one is a visible decision rather than a gap in the guard above.
_FACT_REFUSALS_ON_OLDER_COLUMNS: set[tuple[str, str, tuple[str, ...]]] = {
    ("ClinSigAuthorityCallRow", "confidence", ("confidence_unit",)),  # refused since 0.7
}


def test_every_refusal_on_an_older_fact_column_is_a_listed_decision() -> None:
    older = {
        (name, rule.field, rule.needs)
        for name, rule in _RULES
        if rule.refuse
        and not issubclass(_PAIRED_MODELS[name], AuthoredModel)
        and any(
            field_first_seen(_PAIRED_MODELS[name]).get(col) != "0.8.0" for col in (rule.field, *rule.needs)
        )
    }
    assert older == _FACT_REFUSALS_ON_OLDER_COLUMNS


def test_a_reported_pair_is_on_a_table_the_compiler_reports() -> None:
    """`refuse=False` is reported by the pre-flight, which reads the authored tables only — so a
    reported rule on a machine-written row would be reported nowhere."""
    silent = {
        (name, rule.field)
        for name, rule in _RULES
        if not rule.refuse and not issubclass(_PAIRED_MODELS[name], AuthoredModel)
    }
    assert silent == set()
