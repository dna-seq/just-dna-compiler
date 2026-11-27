"""RM435 shares the GWAS direction vocabulary and classifies the open measure vocabulary."""

import pytest
from just_dna_format import vocab
from just_dna_format.base import field_first_seen, field_vocabularies
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.spec import StudyRow
from pydantic import ValidationError


def test_study_direction_has_the_gwas_vocabulary_and_its_own_first_release() -> None:
    assert (
        field_vocabularies(StudyRow)["effect_direction"]
        == field_vocabularies(GwasEffectRow)["effect_direction"]
    )
    assert field_first_seen(StudyRow)["effect_direction"] == "0.10.0"
    assert StudyRow(pmid="32678081").effect_direction is None


@pytest.mark.parametrize("direction", sorted(vocab.VALID_EFFECT_DIRECTIONS))
def test_study_accepts_each_effect_direction(direction: str) -> None:
    assert StudyRow(pmid="32678081", effect_direction=direction).effect_direction == direction


@pytest.mark.parametrize("direction", ["risk", "in-crease", "in_crease"])
def test_clinical_direction_and_an_inserted_separator_are_unknown(direction: str) -> None:
    # check_vocab swaps existing separators. Neither spelling of 'increase' contains one.
    with pytest.raises(ValidationError, match="effect_direction must be one of"):
        StudyRow(pmid="32678081", effect_direction=direction)


def test_every_recommended_measure_has_a_direction_class() -> None:
    assert set(vocab.EFFECT_MEASURE_NULLS) == vocab.RECOMMENDED_EFFECT_MEASURES
    assert {m for m, n in vocab.EFFECT_MEASURE_NULLS.items() if n == 0} == {"beta", "log(OR)", "log(HR)"}
    assert {m for m, n in vocab.EFFECT_MEASURE_NULLS.items() if n == 1} == {"OR", "HR", "RR"}
    assert {m for m, n in vocab.EFFECT_MEASURE_NULLS.items() if n is None} == {"NR"}
