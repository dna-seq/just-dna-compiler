"""Every fact-sidecar model enforces what its own description says it enforces (RM96).

Three small holes with one shape: a rule stated in one place and enforced in another, or not at all.
The shape is what makes them worth a file rather than three scattered asserts —
`GeneMetricsRow.status` named the `ResolutionRow` vocabulary in its description and accepted any
string, and the reason nobody noticed is that the model sat outside `reference._ALL_MODELS`, where
the guard that discovers an unenforced vocabulary by iteration could not reach it.
`@registry-completeness`, read from the other side: the audit was only as complete as its registry.

So the tests below are deliberately **not** a list of three cases. They walk the fact models and ask
the question of each, which is the only version of this test that could have failed before it was
written.
"""

from __future__ import annotations

import math

import pytest
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import field_vocabularies
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import VALID_RESOLUTION_STATUS

#: A minimal valid row per model — the required fields and nothing else.
_MINIMAL: dict[type, dict] = {
    ResolutionRow: {"variant_key": "rs1800562"},
    FrequencyRow: {"variant_key": "rs1800562", "population": "global", "dataset": "gnomad_v4.1"},
    GeneMetricsRow: {"gene": "HFE", "dataset": "gnomad_v4.1_constraint"},
    LiteratureRow: {"pmid": "8696333"},
    GeneValidityRow: {"gene": "HFE", "dataset": "clingen_2026-06"},
    ClinicalAssertionRow: {"variant_key": "rs1800562", "dataset": "clinvar_2026-06-27"},
    GwasEffectRow: {
        "association_id": "GCST000001",
        "variant_key": "rs1800562",
        "dataset": "gwas_catalog_2026-06",
    },
    ClinSigConcordanceRow: {
        "variant_key": "rs1800562",
        "genotype": "A/G",
        "authority_concordance": "single",
        "authored_position": "matches_none",
    },
    ClinSigAuthorityCallRow: {
        "variant_key": "rs1800562",
        "genotype": "A/G",
        "authority": "clinvar",
        "status": "no_record",
    },
}

#: Models whose `status` column is **not** the `ResolutionRow` vocabulary, with the member the guard
#: below feeds them instead. Keyed rather than special-cased in the test body, so a third such model
#: is a line here rather than an `if` nobody reads.
#:
#: `ClinSigAuthorityCallRow` is the first: its column answers *what happened when this authority was
#: consulted* — recorded, asked-and-absent, or never asked at all — which is a different question
#: from whether a lookup resolved, and borrowing `resolved` for it would have made "the archive
#: classified this variant" and "the lookup succeeded" the same word. `no_record` rather than
#: `recorded`, because the model refuses a recorded call that names no classification — the roster
#: feeds a row that stands on its own, and the vocabulary is what this guard is asking about.
_STATUS_MEMBER: dict[type, str] = {ClinSigAuthorityCallRow: "no_record"}


def test_the_roster_covers_every_fact_model_on_the_authoring_reference() -> None:
    """Guard the premise: this file must not fall behind the registry the way the registry fell
    behind the models. Derived from `_FACT_MODELS` rather than compared against a second list."""
    from just_dna_format.reference import _FACT_MODELS

    #: `SourceRow` has no `status`; `VerificationRecord` is an attestation, not a sidecar row.
    exempt = {"SourceRow", "VerificationRecord"}
    registry = {name for name in _FACT_MODELS if name not in exempt}
    covered = {model.__name__ for model in _MINIMAL}
    assert registry == covered, f"roster drifted: {registry ^ covered}"


@pytest.mark.parametrize(
    "model", sorted(_MINIMAL, key=lambda m: m.__name__), ids=lambda m: m.__name__
)
def test_a_fact_rows_status_is_a_closed_vocabulary(model: type) -> None:
    """Every fact sidecar carrying a `status` refuses a value outside the vocabulary.

    `GeneMetricsRow` was the one that did not: its description read "Outcome: resolved|not_found (the
    ResolutionRow vocabulary)" and `status="totally-made-up"` validated, so the sidecar could carry a
    state no consumer has a branch for while advertising one it does.
    """
    if "status" not in model.model_fields:
        pytest.skip(f"{model.__name__} has no status column")

    member = _STATUS_MEMBER.get(model, "resolved")
    # Read off the field's own vocabulary marker rather than trusted: a model whose status column
    # stopped carrying the member this roster feeds it would otherwise pass by accepting a value the
    # published vocabulary no longer has.
    assert member in field_vocabularies(model)["status"]["options"]
    fields = {**_MINIMAL[model], "status": member}
    accepted = model(**fields)
    assert accepted.status == member

    with pytest.raises(ValueError) as caught:
        model(**{**fields, "status": "totally-made-up"})
    assert "status" in str(caught.value)


def test_the_status_vocabularies_are_the_ones_the_descriptions_name() -> None:
    """The description is the authoring contract (`test_printed_contract.py`'s premise), so a field
    naming `resolved|not_found` must actually accept those two and not some private set."""
    for model in (ResolutionRow, GeneMetricsRow, LiteratureRow, GeneValidityRow):
        for member in ("resolved", "not_found"):
            assert member in VALID_RESOLUTION_STATUS
            assert model(**_MINIMAL[model], status=member).status == member


def test_a_non_finite_standard_error_is_blamed_on_standard_error() -> None:
    """`GwasEffectRow._check_finite` guards two fields and hardcoded one name (RM96).

    An error message that names the wrong column sends an author to a cell that is fine. This is not
    cosmetic in a table whose two numeric columns are read together: `effect_size` and its
    `standard_error` are the pair a consumer weights with, so "which one is broken" is the whole
    content of the report.
    """
    with pytest.raises(ValueError) as caught:
        GwasEffectRow(**_MINIMAL[GwasEffectRow], standard_error=math.inf)
    assert "standard_error must be a finite number" in str(caught.value)

    with pytest.raises(ValueError) as caught:
        GwasEffectRow(**_MINIMAL[GwasEffectRow], effect_size=math.nan)
    assert "effect_size must be a finite number" in str(caught.value)


def test_a_finite_pair_is_accepted() -> None:
    """Negative control: the guard must not refuse ordinary numbers."""
    row = GwasEffectRow(**_MINIMAL[GwasEffectRow], effect_size=0.12, standard_error=0.03)
    assert (row.effect_size, row.standard_error) == (0.12, 0.03)
