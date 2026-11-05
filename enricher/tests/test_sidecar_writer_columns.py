"""The enricher's hand-kept sidecar headers equal their models' columns (RM380's class, the enricher half).

A pass that rewrites a whole table through a hand-kept column list strips every column the list
lacks (`@fieldnames-from-model`; `SOURCES_FIELDNAMES` lost `redistribution` that way). The resolution
writer is held to `ResolutionRow` in `test_enrich_transaction`; these are the two others.
"""

import pytest
from just_dna_enricher import frequencies, gene_metrics
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow


@pytest.mark.parametrize(
    ("header", "model"),
    [(frequencies._FIELDNAMES, FrequencyRow), (gene_metrics._FIELDNAMES, GeneMetricsRow)],
    ids=["frequencies.csv", "gene_metrics.csv"],
)
def test_a_sidecar_header_names_every_model_column(header: list[str], model: type) -> None:
    assert len(header) == len(set(header))
    assert set(header) == set(model.model_fields)
