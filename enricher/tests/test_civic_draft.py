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
from just_dna_enricher.clingen_allele import AlleleIdentity
from just_dna_format.vocab import validate_trait_ids

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


def test_the_disease_id_lands_in_the_column_and_not_in_prose(spec, snapshot):
    """`trait_efo_id` takes any ontology CURIE, so a DOID belongs in it — not in `conclusion`.

    This test previously asserted the opposite, on the premise that the column is EFO-only. It is not:
    its own description says "EFO/MONDO/OBA/HP", the validator accepts any `PREFIX:LOCAL` token, and
    every CIViC germline direction row carries a DOID — so the earlier behaviour buried a structured
    id nothing could join on, on every row.
    """
    draft_panel_from_civic(spec, snapshot=snapshot)
    for csv_name in ("studies.csv", "variants.csv"):
        rows = _rows(spec / csv_name)
        assert rows, f"{csv_name} must be drafted or this proves nothing"
        assert any(r["trait_efo_id"].startswith("DOID:") for r in rows)
        assert all(
            not r["trait_efo_id"] or validate_trait_ids(r["trait_efo_id"]) for r in rows
        ), "whatever is written must survive the column's own validator"
        assert not any("DOID:" in r["conclusion"] for r in rows), "not duplicated into prose"


def test_the_study_row_carries_a_real_pmid(spec, snapshot):
    """Per-record provenance to PubMed is CIViC's strongest feature and the shape studies.csv wants."""
    draft_panel_from_civic(spec, snapshot=snapshot)
    rows = _rows(spec / "studies.csv")
    assert rows
    assert all(r["pmid"].isdigit() for r in rows)


def test_the_variant_row_carries_the_disease_name_beside_its_id(spec, snapshot):
    """`phenotype` is the label, `trait_efo_id` the id — two columns, and CIViC supplies both."""
    draft_panel_from_civic(spec, snapshot=snapshot)
    rows = _rows(spec / "variants.csv")
    named = [r for r in rows if r["trait_efo_id"]]
    assert named, "the fixture must carry at least one disease-bearing row"
    assert all(r["phenotype"] for r in named), "an id with no label beside it is hard to read"


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


# ── the ClinGen CAID pass (RM153) ─────────────────────────────────────────────────────────────────


class _StubRegistry:
    """A registry whose answer per CAID is scripted, so the drafter's branches are testable offline."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def resolve(self, caid):
        self.asked.append(caid)
        return self.answers.get(caid, AlleleIdentity(caid=caid, outcome="no_identity"))


def _caid_rows(snapshot):
    import polars as pl

    frame = pl.read_parquet(snapshot / "data" / "civic.parquet")
    return frame.filter(pl.col("identity_derivation") == "caid")


def test_a_caid_row_is_kept_by_the_builder_rather_than_dropped(snapshot):
    """It has a route to an identity, not an identity — dropping it would hide the recovery."""
    rows = _caid_rows(snapshot)
    assert rows.height > 0, "the fixture must carry a CAID-only row"
    assert rows["rsid"].is_null().all() and rows["chrom"].is_null().all()
    assert rows["allele_registry_id"].is_not_null().all()


def test_offline_withholds_a_caid_row_as_unplaced_and_never_as_unplaceable(spec, snapshot):
    """Nobody-asked is the third state, and `--offline` is where it bites."""
    result = draft_panel_from_civic(spec, snapshot=snapshot, offline=True)
    assert result.withheld["caid_unresolved"] == _caid_rows(snapshot).height
    assert result.withheld["caid_no_identity"] == 0, "not asking is not an absence"
    assert any("unplaced, NOT unplaceable" in w for w in result.warnings)
    assert result.accounts_for_every_candidate()


def test_a_resolved_caid_prefers_the_rsid_over_the_coordinate(spec, snapshot):
    """An rsID is build-independent and is verified downstream by a DIFFERENT authority.

    ClinGen supplies it and Ensembl checks it, so the check is real — which is exactly the property a
    lifted coordinate lacks, and the reason RM48 refused one.
    """
    caid = _caid_rows(snapshot)["allele_registry_id"][0]
    registry = _StubRegistry({
        caid: AlleleIdentity(caid=caid, outcome="resolved", rsid="rs9999999",
                             coordinate=("3", 1234, "A", "G")),
    })
    result = draft_panel_from_civic(spec, snapshot=snapshot, registry=registry)
    assert result.caid_resolved_by_rsid >= 1
    assert result.caid_resolved_by_coordinate == 0, "the rsID wins where both are offered"
    rows = [r for r in _rows(spec / "variants.csv") if r["rsid"] == "rs9999999"]
    assert rows and all(not r["chrom"] for r in rows), "the coordinate is not also written"


def test_a_caid_that_resolves_to_a_coordinate_only_is_placed_by_it(spec, snapshot):
    caid = _caid_rows(snapshot)["allele_registry_id"][0]
    registry = _StubRegistry({
        caid: AlleleIdentity(caid=caid, outcome="resolved", coordinate=("3", 10188320, "A", "G")),
    })
    result = draft_panel_from_civic(spec, snapshot=snapshot, registry=registry)
    assert result.caid_resolved_by_coordinate >= 1
    placed = [r for r in _rows(spec / "variants.csv") if r["start"] == "10188320"]
    assert placed and all(r["chrom"] == "3" for r in placed)


def test_an_established_absence_is_reported_apart_from_a_failure_to_ask(spec, snapshot):
    """Two different facts, and a drafter that blurred them would make a blip look permanent."""
    caid = _caid_rows(snapshot)["allele_registry_id"][0]
    registry = _StubRegistry({caid: AlleleIdentity(caid=caid, outcome="no_identity")})
    result = draft_panel_from_civic(spec, snapshot=snapshot, registry=registry)
    assert result.withheld["caid_no_identity"] >= 1
    assert result.withheld["caid_unresolved"] == 0
    assert any("registry answered" in w for w in result.warnings)


def test_the_registry_gets_its_own_source_row_only_where_it_was_consulted(spec, snapshot, tmp_path):
    """A pass that consults a source writes its row; one that contributed nothing writes none."""
    draft_panel_from_civic(spec, snapshot=snapshot, offline=True)
    sources = next(p for p in (spec / "sources.csv", spec / "licensing.csv") if p.exists())
    consulted = {r["source"] for r in _rows(sources)}
    assert "civic" in consulted
    assert "clingen_allele_registry" in consulted, (
        "offline still ASKS the client, which answers skipped_offline — the source was consulted"
    )


def test_the_caid_pass_leaves_the_accounting_closed(spec, snapshot):
    caid = _caid_rows(snapshot)["allele_registry_id"][0]
    registry = _StubRegistry({
        caid: AlleleIdentity(caid=caid, outcome="resolved", rsid="rs9999999"),
    })
    result = draft_panel_from_civic(spec, snapshot=snapshot, registry=registry)
    assert result.accounts_for_every_candidate()


def test_a_one_sided_indel_is_anchored_into_a_vcf_row(spec, snapshot, monkeypatch):
    """The Picard-style recovery: one reference base turns a stated indel into a drafted row."""
    caid = _caid_rows(snapshot)["allele_registry_id"][0]
    registry = _StubRegistry({
        caid: AlleleIdentity(caid=caid, outcome="needs_anchor", unanchored=("3", 10142013, "", "G")),
    })
    monkeypatch.setattr(
        "just_dna_enricher.civic_draft.SequenceProxy",
        lambda **kw: type("_S", (), {"subsequence": lambda self, a, s, e: "G"})(),
    )
    result = draft_panel_from_civic(spec, snapshot=snapshot, registry=registry)
    assert result.caid_anchored_indels >= 1
    placed = [r for r in _rows(spec / "variants.csv") if r["start"] == "10142013"]
    assert placed and all(r["ref"] == "G" and r["alts"] == "GG" for r in placed)
    assert result.accounts_for_every_candidate()


def test_an_unreadable_anchor_withholds_the_row_and_names_the_reason(spec, snapshot, monkeypatch):
    """The allele is known and the anchor is not — a fourth outcome, not an absence."""
    caid = _caid_rows(snapshot)["allele_registry_id"][0]
    registry = _StubRegistry({
        caid: AlleleIdentity(caid=caid, outcome="needs_anchor", unanchored=("3", 10142013, "A", "")),
    })
    monkeypatch.setattr(
        "just_dna_enricher.civic_draft.SequenceProxy",
        lambda **kw: type("_S", (), {"subsequence": lambda self, a, s, e: None})(),
    )
    result = draft_panel_from_civic(spec, snapshot=snapshot, registry=registry)
    assert result.withheld["anchor_base_unreadable"] >= 1
    assert result.withheld["caid_no_identity"] == 0, "the registry answered; only the anchor failed"
    assert any("withheld rather than guessed" in w for w in result.warnings)
    assert result.accounts_for_every_candidate()


def test_a_curated_identity_drafts_like_a_published_one(spec, snapshot):
    """The curated class must reach `variants.csv`, not fall into a withheld bucket.

    Variant 3184 carries no identifier CIViC publishes and is placed from the curated name table, so
    this is the whole curated path end to end: build reads the table, drafter writes the row.
    """
    result = draft_panel_from_civic(spec, snapshot=snapshot)
    assert result.accounts_for_every_candidate()
    rows = _rows(spec / "variants.csv")
    drafted = [r for r in rows if r.get("rsid") == "rs730882037"]
    assert len(drafted) == 1, "the curated row did not reach variants.csv"
    assert drafted[0]["direction"] == "risk"


def test_an_unplaced_row_goes_to_the_registry_whatever_its_derivation_says(snapshot):
    """The invariant restated over the CELLS, because the label stopped answering the question.

    This test used to read: every derivation but `caid` arrives placed, and `caid` arrives unplaced.
    Both halves were true when `identity_derivation` named which *identifier* answered. RM169 added
    `vcf_csq`, which names which **file** the row was read from and is stamped ahead of the identifier
    routes — so a CSQ-sourced variant whose only identity is a registry id arrives labelled `vcf_csq`
    and unplaced, and the old assertion's `else` branch would have failed on it. It did not fail,
    because the fixture built without a VCF and no `vcf_csq` row ever reached it: the test asserting
    exactly the violated property could not see the violation.

    What actually matters is not the label but the routing: **an unplaced row carrying a CAID must
    reach the registry, and nothing else may.** Asserted over the vocabulary so a new member is
    covered on arrival, and over a snapshot that really does carry the CSQ tier.
    """
    import polars as pl
    from just_dna_enricher.civic_build import CIVIC_IDENTITY_DERIVATIONS, CIVIC_PARQUET
    from just_dna_enricher.civic_draft import _needs_the_registry
    from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME

    frame = pl.read_parquet(snapshot / SNAPSHOT_DATA_DIRNAME / CIVIC_PARQUET)
    assert set(frame["identity_derivation"].unique().to_list()) <= CIVIC_IDENTITY_DERIVATIONS
    for row in frame.iter_rows(named=True):
        placed = row["rsid"] is not None or row["chrom"] is not None
        has_caid = bool((row["allele_registry_id"] or "").strip())
        # Three states, and the predicate must agree with all three: placed rows are drafted as they
        # stand, unplaced rows with a CAID are the registry's, and an unplaced row with neither is
        # not in the snapshot at all (`unresolvable_identity` drops it at build time).
        assert placed or has_caid, "a row with no identity and no route should never be emitted"
        assert _needs_the_registry(row) == (not placed and has_caid), (
            f"{row['identity_derivation']} row routed on its label rather than its cells"
        )


def test_a_caid_only_csq_row_reaches_the_registry_rather_than_being_refused(tmp_path, spec):
    """The regression: a `vcf_csq` row whose sole identity is a CAID must not be withheld.

    Before the dispatch moved off `identity_derivation`, this row fell through to `_variant_row`,
    which drops every `None` cell and then refuses what is left as `identity_refused_by_model` —
    a warning that blames "a coordinate missing its chromosome", which is not what happened. Measured
    on the real release by `civic_vcf`'s own docstring: 57 of 112 CSQ-sourced variants are placed by
    ClinGen CAID, and every one of them was withheld with zero lookups.

    Built by appending one synthetic CSQ entry carrying a CAID and nothing else, because the shipped
    four-line fixture VCF has no such row — which is the same reason this went unnoticed.
    """
    import polars as pl
    from just_dna_enricher.civic_build import CIVIC_PARQUET, build_snapshot
    from just_dna_enricher.civic_draft import _needs_the_registry
    from just_dna_enricher.civic_vcf import parse_csq_format
    from just_dna_enricher.locations import SNAPSHOT_DATA_DIRNAME

    lines = [line for line in
             (SLICE / "civic_accepted_and_submitted.vcf").read_text().splitlines() if line.strip()]
    fields = parse_csq_format(next(line for line in lines if "ID=CSQ" in line))
    template = next(line for line in lines if not line.startswith("#"))
    columns = template.split("\t")

    # Built from the file's OWN declared field order rather than a hand-written pipe string: the
    # block has 28 fields and the reader checks the header's order rather than assuming one, so a
    # positional guess produces a row that silently parses wrong.
    example = dict(zip(fields, columns[7].split("CSQ=")[1].split("|"), strict=False))
    entry = dict.fromkeys(fields, "")
    entry.update(example)
    entry.update({
        "CIViC Variant ID": "999901",          # a variant id the TSV pair does not describe
        "CIViC Entity ID": "999902",           # ... and an evidence id it does not either
        # The CSQ synthesis runs on SUBMITTED items only — an accepted one is expected in the TSV
        # pair, and a row naming a variant that is not there is dropped as `unresolvable_identity`
        # rather than built from the block. So the tier this test is about is reachable only through
        # the wider basis, which is the same reason the shipped fixture has no such row.
        "CIViC Entity Status": "submitted",
        "Allele Registry ID": "CA9999999",     # the row's only identity
        "CIViC Variant Aliases": "",           # no rsID alias, so the rsID route finds nothing
        "CIViC HGVS": "",                      # and no g. HGVS, so the coordinate route finds none
        "CIViC Variant Name": "P71fs (c.211insT)",
    })
    columns[2] = "999901"
    columns[7] = "GN=VHL;CSQ=" + "|".join(entry[name] for name in fields)

    vcf = tmp_path / "with_caid_only.vcf"
    vcf.write_text("\n".join([*lines, "\t".join(columns)]) + "\n")

    out = build_snapshot(
        SLICE / "ClinicalEvidenceSummaries.tsv",
        SLICE / "VariantSummaries.tsv",
        SLICE / "MolecularProfileSummaries.tsv",
        tmp_path / "snap_vcf",
        release="01-Aug-2026",
        vcf=vcf,
    ).out_dir

    frame = pl.read_parquet(out / SNAPSHOT_DATA_DIRNAME / CIVIC_PARQUET)
    caid_only = [
        row
        for row in frame.iter_rows(named=True)
        if (row["allele_registry_id"] or "").strip() == "CA9999999"
    ]
    assert caid_only, "the synthetic CSQ row did not survive the build"
    for row in caid_only:
        assert row["rsid"] is None and row["chrom"] is None, "the fixture row must be unplaced"
        assert _needs_the_registry(row), (
            f"a CAID-only row stamped {row['identity_derivation']!r} was routed past the registry"
        )
