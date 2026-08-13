"""`SourceRow` / `source_signature` — the data-source licensing fact table (0.5).

The assertions that matter here are about the **tri-state** permission flags. `None` means the terms
could not be established; `False` means they forbid. Collapsing those is the single most dangerous
simplification available in this design, so the difference is pinned at the model, the signature and
the taint predicate.
"""

import pytest
from just_dna_format.integrity import source_signature
from just_dna_format.sources import (
    SOURCE_FACT_FIELDS,
    SourceRow,
    taints_commercial_use,
    taints_redistribution,
)
from just_dna_format.vocab import VALID_DECLARED_USE, VALID_SOURCE_LAYERS
from pydantic import ValidationError


def _row(**kw) -> SourceRow:
    return SourceRow(**{"source": "clinpgx", "layer": "annotation", **kw})


def test_layer_and_declared_use_are_closed_vocabularies() -> None:
    assert {
        "resolution", "frequency", "gene_metrics", "literature",
        # 0.6 (RM24/RM25) — fact-class like the four above, so neither taints; each is written by the
        # pass that owns the table it names.
        "gene_validity", "clinical_assertion",
        "annotation",
    } == VALID_SOURCE_LAYERS
    assert {"unstated", "non_commercial", "commercial"} == VALID_DECLARED_USE
    with pytest.raises(ValidationError):
        _row(layer="annotations")          # plural typo
    with pytest.raises(ValidationError):
        _row(declared_use="noncommercial")  # missing underscore


def test_typo_column_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _row(licence="CC-BY-SA-4.0")  # British spelling — extra="forbid" must catch it


def test_unknown_terms_are_not_permission() -> None:
    """`None` must stay distinguishable from `False` everywhere it is consumed."""
    unknown = _row(commercial_use=None)
    forbidden = _row(commercial_use=False)
    permitted = _row(commercial_use=True)

    # 1. Different facts, therefore different signatures. This is the assertion that stops a future
    #    refactor "simplifying" the field to `bool = False`.
    assert source_signature([unknown]) != source_signature([forbidden])
    assert source_signature([permitted]) != source_signature([forbidden])

    # 2. Unknown does not taint — "we could not read the terms" is not a finding that they forbid.
    assert taints_commercial_use(forbidden) is True
    assert taints_commercial_use(unknown) is False
    assert taints_commercial_use(permitted) is False


def test_only_the_annotation_layer_taints() -> None:
    """A source consulted for a coordinate contributed a fact Ensembl reports identically."""
    for layer in sorted(VALID_SOURCE_LAYERS - {"annotation"}):
        assert taints_commercial_use(_row(layer=layer, commercial_use=False)) is False
    assert taints_commercial_use(_row(layer="annotation", commercial_use=False)) is True


def test_redistribution_is_a_third_axis_not_a_shade_of_commercial_use() -> None:
    """The two answer different questions, so they must be independently settable and separately
    tainting. CC BY-NC forbids sale while expressly ALLOWING sharing; an academic-use-only source
    (OMIM, dbNSFP) forbids both. Collapsing them would record the second as merely the first."""
    non_commercial = _row(commercial_use=False, redistribution=True)   # CC BY-NC
    academic_only = _row(commercial_use=False, redistribution=False)   # OMIM / dbNSFP class
    assert source_signature([non_commercial]) != source_signature([academic_only])

    assert taints_redistribution(academic_only) is True
    assert taints_redistribution(non_commercial) is False
    # …and the commercial verdict cannot tell them apart, which is exactly why the axis exists.
    assert taints_commercial_use(academic_only) == taints_commercial_use(non_commercial) is True


def test_redistribution_unknown_is_not_permission() -> None:
    assert taints_redistribution(_row(redistribution=None)) is False  # unknown does not taint…
    assert source_signature([_row(redistribution=None)]) != source_signature(
        [_row(redistribution=False)]
    )  # …but it is a different fact from a refusal
    for layer in sorted(VALID_SOURCE_LAYERS - {"annotation"}):
        # Same layer rule as the other axes: a coordinate looked up from a restricted service is
        # still just a coordinate.
        assert taints_redistribution(_row(layer=layer, redistribution=False)) is False


def test_signature_is_producer_independent_but_fact_sensitive() -> None:
    base = {"license": "CC-BY-SA-4.0", "share_alike": True, "commercial_use": False}
    # `fetched_at` is the only excluded column: when the terms were read is producer noise.
    assert "fetched_at" not in SOURCE_FACT_FIELDS
    assert source_signature([_row(**base, fetched_at="2026-08-02T00:00:00Z")]) == source_signature(
        [_row(**base, fetched_at="2019-01-01T00:00:00Z")]
    )
    # Every fact column moves it — spot-check the two that carry legal meaning plus the declaration.
    assert source_signature([_row(**base)]) != source_signature(
        [_row(**{**base, "share_alike": False})]
    )
    assert source_signature([_row(**base)]) != source_signature(
        [_row(**base, declared_use="non_commercial")]
    )


def test_source_is_inside_the_fact_set_unlike_the_other_tables() -> None:
    """Here the source is the row's SUBJECT, not its provenance — drop it and the row loses its key."""
    assert "source" in SOURCE_FACT_FIELDS and "layer" in SOURCE_FACT_FIELDS
    assert source_signature([_row(source="clinpgx")]) != source_signature([_row(source="cpic")])


def test_order_independent() -> None:
    a, b = _row(source="cpic"), _row(source="ensembl", commercial_use=True)
    assert source_signature([a, b]) == source_signature([b, a])
