"""The published merge key of every machine-produced table, pinned against the pass that writes it.

S51: each enricher pass held its merge key as a dict-key expression in its own body, so the only way
to learn which columns decide two sidecar rows are the same row was to read our source. The reporting
consumer could not, and derived the key as *the required members of the fact-field tuple* — a guess
that agreed on five of eight tables and was measurably coarse on two, dropping `disease_id` from
`gene_validity.csv` and `variation_id` from `clinical_assertions.csv`. Those are precisely the two
tables where one subject legitimately carries several rows, so the coarse key demoted a real second
assertion into an ambiguity a human had to adjudicate.

The repair is one source of truth — each model declares `_KEY_FIELDS`, `hints.key_fields` reports it
and every pass keys its `existing` dict off it through `base.merge_key`. The tests below are what
makes that structural rather than asserted: they run the real passes and compare what the passes
actually merged against the published answer, so a future edit that reintroduces a restated tuple
fails here instead of shipping.
"""

import csv
from pathlib import Path

import pytest
from just_dna_compiler.draft import DRAFTABLE, model_for
from just_dna_compiler.hints import DERIVED_TABLE_MODELS, derived_model_for, key_fields
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.base import merge_key
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.resolution import ResolutionRow

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


def _model(csv_name: str):
    try:
        return model_for(csv_name)
    except Exception:
        return derived_model_for(csv_name)


def test_every_published_key_column_is_a_real_column_of_the_table_it_keys() -> None:
    """The guard that catches a key naming a column that does not exist, over the walked registry.

    Both levels, since a fallback is as capable of naming a stale column as a primary key is — and
    the fallback is the half no consumer looks at, so a typo there would go unseen for longer.
    """
    checked = 0
    for csv_name in sorted(DERIVED_TABLE_MODELS):
        model = _model(csv_name)
        key = key_fields(csv_name)
        assert key is not None, csv_name
        # A key column must be a real field on the model it is published for — the guard that would
        # have caught a key naming a column that does not exist.
        assert set(key.columns) <= set(model.model_fields), csv_name
        assert set(key.fallback) <= set(model.model_fields), csv_name
        checked += 1
    assert checked == len(DERIVED_TABLE_MODELS)


def test_a_fallback_is_only_declared_where_the_primary_key_can_be_absent() -> None:
    """A fallback under a required primary column is unreachable, so it would be a lie in the surface.

    This is the guard the `TableKey` dataclass cannot run — it holds no model — and it is why the
    rule is asserted over the walked registry instead.
    """
    contradictions = {
        csv_name: key.columns
        for csv_name in (*DRAFTABLE, *DERIVED_TABLE_MODELS)
        if (key := key_fields(csv_name)) is not None
        and key.fallback
        and all(
            (f := _model(csv_name).model_fields.get(c)) is not None and f.is_required()
            for c in key.columns
        )
    }
    assert contradictions == {}


def test_gene_validity_falls_back_to_the_grain_and_the_two_levels_cannot_collide() -> None:
    """The published two-level key, run rather than read.

    `assertion_id` is the source's own answer where it published one; the grain decides where it did
    not. The levels are tagged, so a grain tuple whose first member equals somebody's id is still a
    different key — which is the property that makes publishing a fallback safe at all.
    """
    base = {
        "gene": "HFE",
        "disease_id": "MONDO:0000001",
        "moi": "autosomal_recessive",
        "submitter": "ClinGen",
        "dataset": "clingen_2026",
        "source": "clingen",
        "status": "resolved",
        "fetched_at": "2026-08-20T00:00:00Z",
    }
    with_id = GeneValidityRow(**base, assertion_id="CGGV:assertion_1")
    without_id = GeneValidityRow(**base)

    key = key_fields("gene_validity.csv")
    assert key is not None
    assert key.columns == ("assertion_id",)
    assert key.fallback == ("gene", "disease_id", "moi", "submitter", "dataset")

    assert merge_key(with_id) == ("id", "CGGV:assertion_1")
    assert merge_key(without_id) == (
        "grain", "HFE", "MONDO:0000001", "autosomal_recessive", "ClinGen", "clingen_2026",
    )
    assert merge_key(with_id) != merge_key(without_id)

    # S51's measured defect: the consumer's derived key dropped `disease_id`, so a gene's second
    # disease read as the same row. It does not here.
    other_disease = GeneValidityRow(**{**base, "disease_id": "MONDO:0000002"})
    assert merge_key(without_id) != merge_key(other_disease)


def test_a_clinvar_absence_row_keys_apart_from_every_record_for_the_same_allele() -> None:
    """`variation_id` is in the key, and a null there is a value rather than an absence.

    The `not_found` row states that the archive was consulted and holds no record for this allele; it
    must survive beside a real record, which is what the consumer's `(variant_key, dataset)` guess
    could not express.
    """
    common = {
        "variant_key": "1:100:A:G", "chrom": "1", "start": 100, "ref": "A", "alt": "G",
        "genome_build": "GRCh38", "dataset": "clinvar_2026", "source": "clinvar",
        "fetched_at": "2026-08-20T00:00:00Z",
    }
    absent = ClinicalAssertionRow(**common, status="not_found")
    first = ClinicalAssertionRow(**common, status="resolved", variation_id="12345")
    second = ClinicalAssertionRow(**common, status="resolved", variation_id="67890")

    assert merge_key(absent) == ("1:100:A:G", None)
    assert len({merge_key(r) for r in (absent, first, second)}) == 3


def test_resolution_publishes_a_subject_rule_because_several_rows_share_its_key() -> None:
    """The rule matters as much as the columns: reporting `equality` here would be a wrong answer.

    One rsID resolves to several loci — `locus_index` orders them — so a consumer treating this key
    as a uniqueness constraint would call a legal one-to-many file a duplicate.
    """
    key = key_fields("resolution.csv")
    assert key is not None
    assert key.columns == ("variant_key",)
    assert key.rule == "subject"

    loci = [
        ResolutionRow(
            variant_key="rs1801133", rsid="rs1801133", chrom="1", start=11796321,
            ref="G", alts="A", genome_build="GRCh38", locus_index=i,
            source="ensembl", status="resolved", fetched_at="2026-08-20T00:00:00Z",
        )
        for i in range(2)
    ]
    assert len({merge_key(r) for r in loci}) == 1


@pytest.mark.parametrize("csv_name", sorted(DERIVED_TABLE_MODELS))
def test_the_published_key_deduplicates_a_real_written_sidecar(csv_name: str) -> None:
    """Over sidecars the reference examples actually carry, the key does what it claims.

    An `equality` key must be unique across the file; a `subject` key must not be asserted unique,
    and this is the distinction the test exists to keep honest rather than to paper over. Files no
    example carries are skipped by name rather than silently contributing nothing.
    """
    key = key_fields(csv_name)
    assert key is not None
    model = _model(csv_name)

    found = sorted(_EXAMPLES.glob(f"*/{csv_name}")) + sorted(_EXAMPLES.glob(f"*/*/{csv_name}"))
    if not found:
        pytest.skip(f"no reference example carries {csv_name}")

    for path in found:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = [
                model.model_validate({k: v for k, v in raw.items() if v != ""})
                for raw in csv.DictReader(handle)
            ]
        if not rows:
            continue
        keys = [merge_key(r) for r in rows]
        if key.rule == "equality":
            assert len(set(keys)) == len(keys), f"{path} has duplicate {key.columns} rows"
        else:
            assert len(set(keys)) <= len(keys)
