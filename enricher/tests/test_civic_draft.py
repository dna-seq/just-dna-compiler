"""`draft-panel --source civic` (RM152) — the direction axis, and everything it refuses to write.

The provider is exercised against a snapshot built from `assets/civic_slice/` in-test, so the drafting
behaviour and the builder that feeds it never drift apart: a fixture parquet checked in beside them
would be a second thing to update.
"""

import csv
from pathlib import Path

import pytest

from just_dna_enricher.civic_build import build_snapshot
from just_dna_enricher.civic_draft import (
    CIVIC_WITHHELD_REASONS,
    draft_panel_from_civic,
    identity_refused_by_model,
)

SLICE = Path(__file__).resolve().parents[2] / "assets" / "civic_slice"


@pytest.fixture
def snapshot(tmp_path):
    return build_snapshot(
        SLICE / "ClinicalEvidenceSummaries.tsv",
        SLICE / "VariantSummaries.tsv",
        SLICE / "MolecularProfileSummaries.tsv",
        tmp_path / "snap",
        release="01-Aug-2026",
    ).out_dir


@pytest.fixture
def spec(tmp_path):
    spec_dir = tmp_path / "spec"
    spec_dir.mkdir()
    (spec_dir / "module_spec.yaml").write_text(
        "schema_version: '0.7'\nid: civic-probe\nname: CIViC probe\nversion: 1\n"
        "genome_build: GRCh38\ndescription: a probe\n",
        encoding="utf-8",
    )
    return spec_dir


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(newline="", encoding="utf-8")))


# ── the guard that is derived rather than restated ────────────────────────────────────────────────


def test_the_identity_guard_asks_the_model_rather_than_paraphrasing_its_rule():
    """`pgx_draft` restated "rsID or position" and `draft --gene CYP2C9` died on a pydantic error.

    Every clause is checked against `VariantRow` itself, including the one CIViC actually produces:
    variant 1770 carries a build, a `start` and a `referenceBases` with **no chromosome**, which
    passes any "does it have a position?" paraphrase and is not a position.
    """
    assert identity_refused_by_model({"chrom": "13", "start": 100, "ref": "A", "alts": "G"}) is None
    assert identity_refused_by_model({"rsid": "rs1042522"}) is None, "an rsID alone is an identity"

    # CIViC id 1770's exact shape.
    refused = identity_refused_by_model({"start": 10188305, "ref": "A"})
    assert refused is not None and "chrom" in refused
    assert identity_refused_by_model({"chrom": "13"}) is not None, "a contig is not a position"
    assert identity_refused_by_model({}) is not None, "no identifier at all"


def test_a_row_the_model_refuses_is_withheld_by_name_rather_than_crashing(spec, snapshot, tmp_path):
    """The failure mode being guarded against is an unhandled pydantic error mid-draft."""
    result = draft_panel_from_civic(spec, snapshot=snapshot)
    assert set(result.withheld) == set(CIVIC_WITHHELD_REASONS)
    assert result.accounts_for_every_candidate()


# ── the axis, and the withhold that defines it ────────────────────────────────────────────────────


def test_it_writes_direction_and_never_clin_sig(spec, snapshot):
    """The axis is the whole point: CIViC's germline clin_sig is 5 calls with none benign-class."""
    draft_panel_from_civic(spec, snapshot=snapshot)
    rows = _rows(spec / "variants.csv")
    assert rows, "the fixture must draft something or nothing below is tested"
    assert all(r["direction"] in {"risk", "protective"} for r in rows)
    assert all(not r["clin_sig"] for r in rows), (
        "clin_sig is the axis the measurement refused; writing it would re-make the rejected claim"
    )


def test_a_refutation_is_withheld_rather_than_written_as_the_opposite(spec, snapshot):
    """"Does not support predisposition" is not "protective" — `None` is never `False`.

    The fixture carries two constructed refutation rows, because both of CIViC's real ones are
    unidentifiable in the bulk release and would be dropped before this decision is reached.
    """
    result = draft_panel_from_civic(spec, snapshot=snapshot)
    assert result.withheld["refutation_states_no_direction"] == 2
    assert any("does not establish" in w for w in result.warnings)
    rows = _rows(spec / "variants.csv")
    assert not any("Does Not Support" in r["conclusion"] for r in rows)


def test_a_contested_variant_is_withheld_and_named_never_resolved(spec, snapshot, tmp_path):
    """Choosing between two camps is `mode()` over an unsorted group, which the ordering rule bans."""
    import polars as pl

    parquet = snapshot / "data" / "civic.parquet"
    frame = pl.read_parquet(parquet)
    risk = frame.filter(pl.col("direction") == "risk").head(1)
    flipped = risk.with_columns(
        pl.lit("protective").alias("direction"),
        pl.lit(9999905, dtype=pl.Int64).alias("evidence_id"),
        pl.lit("Protectiveness").alias("significance_raw"),
    )
    pl.concat([frame, flipped]).write_parquet(parquet)

    result = draft_panel_from_civic(spec, snapshot=snapshot)
    assert result.withheld["contested_variant"] == 2, "both of the variant's rows are withheld"
    assert any("BOTH directions" in w for w in result.warnings)
    named = risk["variant_name"][0]
    assert any(str(named) in w for w in result.warnings), "the author is told which variant"


def test_contestation_is_decided_before_any_filter_runs(spec, snapshot):
    """A filter that removed the dissenting row would have picked the winner.

    Asserted through the gene filter, which is the one dial this provider has: a variant contested
    across the whole snapshot must still read as contested when only its own gene is requested, and
    must not become uncontested because a sibling row was filtered away first.
    """
    import polars as pl

    parquet = snapshot / "data" / "civic.parquet"
    frame = pl.read_parquet(parquet)
    risk = frame.filter(pl.col("direction") == "risk").head(1)
    gene = risk["gene"][0]
    flipped = risk.with_columns(
        pl.lit("protective").alias("direction"),
        pl.lit(9999906, dtype=pl.Int64).alias("evidence_id"),
    )
    pl.concat([frame, flipped]).write_parquet(parquet)

    result = draft_panel_from_civic(spec, [gene], snapshot=snapshot)
    assert result.withheld["contested_variant"] == 2
    assert result.withheld["gene_not_requested"] > 0, "the filter really did exclude other genes"


# ── accounting, which is the objection the drafter was rejected on ────────────────────────────────


def test_every_admitted_row_is_accounted_for(spec, snapshot):
    """The excluded count belongs in the RESULT, not in a docstring — S84's own objection."""
    result = draft_panel_from_civic(spec, snapshot=snapshot)
    assert result.candidates > 0
    assert result.accounts_for_every_candidate(), (
        f"{result.candidates} admitted, "
        f"{result.outcome_for('variants.csv', 'added')} added, withheld {result.withheld}"
    )


def test_the_gene_filter_is_counted_apart_from_the_withholding(spec, snapshot):
    """"CIViC has nothing for this gene" and "we would not write what it has" are different answers."""
    everything = draft_panel_from_civic(spec, snapshot=snapshot, dry_run=True)
    assert everything.withheld["gene_not_requested"] == 0
    filtered = draft_panel_from_civic(spec, ["VHL"], snapshot=snapshot, dry_run=True)
    assert filtered.withheld["gene_not_requested"] > 0
    assert filtered.candidates < everything.candidates


def test_a_class_that_withheld_nothing_says_nothing(spec, snapshot):
    """A check that cannot fail must not report a zero (`@tautology-zero`)."""
    result = draft_panel_from_civic(spec, snapshot=snapshot)
    assert result.withheld["contested_variant"] == 0
    assert not any("BOTH directions" in w for w in result.warnings)


# ── provenance and the source row ─────────────────────────────────────────────────────────────────


def test_the_pass_writes_its_source_row(spec, snapshot):
    """A source that is only *used* is one the compile gate cannot account for."""
    draft_panel_from_civic(spec, snapshot=snapshot)
    sources = next(
        (spec / name for name in ("sources.csv", "licensing.csv") if (spec / name).exists()), None
    )
    assert sources is not None, "@write-the-sourcerow — the gate reads this file and nothing else"
    assert any(r["source"] == "civic" for r in _rows(sources))


def test_a_run_that_found_no_snapshot_writes_nothing_and_says_nobody_asked(spec, tmp_path, monkeypatch):
    """Nobody-asked is a third state beside asked-and-absent (`@unreachable-not-absent`)."""
    monkeypatch.setattr(
        "just_dna_enricher.civic_draft.resolve_civic_reference", lambda *a, **k: None
    )
    result = draft_panel_from_civic(spec, snapshot=None)
    assert result.skipped is True
    assert result.added == 0
    assert any("Nobody-asked" in w for w in result.warnings)
    assert not (spec / "variants.csv").exists(), "a pass contributing nothing writes no SourceRow"


def test_the_study_row_carries_the_pmid_and_never_a_doid_in_the_efo_column(spec, snapshot):
    """CIViC names diseases with a DOID; `trait_efo_id` is EFO. A wrong id is worse than none."""
    draft_panel_from_civic(spec, snapshot=snapshot)
    rows = _rows(spec / "studies.csv")
    assert rows, "every germline direction row cites a real PMID; that is CIViC's best feature"
    assert all(r["pmid"].isdigit() for r in rows)
    assert all(not r["trait_efo_id"] for r in rows)
    assert any("DOID:" in r["conclusion"] for r in rows), "the DOID is kept, in prose, where it is safe"


def test_the_genotype_is_stubbed_so_the_module_cannot_compile_until_a_human_decides(spec, snapshot):
    """A generated stub must be unable to compile (`@stub-cannot-compile`).

    CIViC states which way a variant runs, never which genotype a module annotates, and filling one
    would be the provider answering a question only the author can.
    """
    draft_panel_from_civic(spec, snapshot=snapshot)
    rows = _rows(spec / "variants.csv")
    assert all(r["genotype"] == "<<REPLACE>>" for r in rows)


def test_a_redraft_reports_rows_already_there_rather_than_appending_them_twice(spec, snapshot):
    """Drafting appends and never rewrites; a second lap must be a no-op (`@draft-appends`)."""
    first = draft_panel_from_civic(spec, snapshot=snapshot)
    before = (spec / "variants.csv").read_bytes()
    second = draft_panel_from_civic(spec, snapshot=snapshot)
    assert second.outcome_for("variants.csv", "added") == 0
    assert second.outcome_for("variants.csv", "already_present") == first.candidates - sum(
        v for k, v in first.withheld.items() if k != "gene_not_requested"
    )
    assert (spec / "variants.csv").read_bytes() == before, "a second lap changed the file"
