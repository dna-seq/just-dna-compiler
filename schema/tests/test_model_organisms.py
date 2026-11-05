"""`ModelOrganismRow` (0.8, RM335): the model-organism evidence table's row model.

The audit's two rows (longevitymap v2 shape audit, appendix example 12) are the fixtures: a PPARG
knock-in on a high-fat diet, cited, and an IGF1R heterozygous knockout in females, uncited.
"""

import pytest
from just_dna_format.model_organisms import VALID_MODEL_ORGANISM_CONCORDANCE, ModelOrganismRow
from just_dna_format.spec import CitationPair
from pydantic import ValidationError

_PPARG = {
    "gene": "PPARG",
    "orthologue": "Pparg",
    "species": "Mus musculus",
    "model_type": "knock-in Pro12Ala",
    "diet": "high-fat",
    "lifespan_effect": "benefit lost on high-fat diet",
    "concordance": "nonmonotone",
    "pmid": "19117549",
}
_IGF1R = {
    "gene": "IGF1R",
    "orthologue": "Igf1r",
    "species": "Mus musculus",
    "model_type": "heterozygous knockout",
    "sex": "female",
    "lifespan_effect": "+33% (female)",
    "concordance": "concordant",
}


def test_the_audit_rows_validate() -> None:
    assert ModelOrganismRow(**_PPARG).concordance == "nonmonotone"
    uncited = ModelOrganismRow(**_IGF1R)
    assert uncited.pmid is None and uncited.doi is None


def test_gene_is_the_one_required_column() -> None:
    required = {name for name, f in ModelOrganismRow.model_fields.items() if f.is_required()}
    assert required == {"gene"}
    with pytest.raises(ValidationError, match="gene"):
        ModelOrganismRow(species="Mus musculus")


def test_the_key_is_every_column_but_the_findings_two() -> None:
    assert set(ModelOrganismRow._KEY_FIELDS) == set(ModelOrganismRow.model_fields) - {
        "lifespan_effect",
        "concordance",
    }


def test_concordance_is_closed_and_empty_is_unstated() -> None:
    assert VALID_MODEL_ORGANISM_CONCORDANCE == frozenset({"concordant", "discordant", "nonmonotone"})
    with pytest.raises(ValidationError, match="concordance must be one of"):
        ModelOrganismRow(**{**_IGF1R, "concordance": "unclear"})
    assert ModelOrganismRow(**{**_IGF1R, "concordance": None}).concordance is None


def test_it_carries_the_citation_pair() -> None:
    assert issubclass(ModelOrganismRow, CitationPair)
    with pytest.raises(ValidationError, match="doi"):
        ModelOrganismRow(**{**_IGF1R, "pmid": "NONE"})
    assert ModelOrganismRow(**{**_IGF1R, "pmid": "NONE", "doi": "10.1101/2025.03.01.640000"}).pmid == "NONE"
    with pytest.raises(ValidationError):
        ModelOrganismRow(**{**_IGF1R, "pmid": "10.1101/2025.03.01.640000"})


def test_sex_is_free_text_not_the_karyotype_vocabulary() -> None:
    # The animals' sex is descriptive (P5): `meta.csv`'s closed `sex` is a different axis.
    assert ModelOrganismRow(**{**_IGF1R, "sex": "hermaphrodite"}).sex == "hermaphrodite"
    assert "vocabulary" not in (ModelOrganismRow.model_fields["sex"].json_schema_extra or {})
