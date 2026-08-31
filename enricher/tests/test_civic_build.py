"""The CIViC snapshot builder (RM152) — identity, the drop registry, and the withheld direction.

The fixture under `assets/civic_slice/` is a real slice of the `01-Aug-2026` release, chosen so that
every identity route and every drop reason has at least one row. Two rows in it are constructed rather
than harvested, and both are marked here, because upstream has no example: a germline direction row on
a combination profile, and a `Does Not Support` row on a variant that carries identity. Everything
else is upstream bytes.
"""

import csv
import json
from pathlib import Path

import polars as pl
import pytest

from just_dna_enricher.civic_build import (
    CIVIC_COLUMNS,
    CIVIC_DIRECTION_MAP,
    CIVIC_DROP_REASONS,
    CIVIC_IDENTITY_DERIVATIONS,
    CivicBuildError,
    assert_registry_closes,
    build_snapshot,
    has_unparsable_grch38,
    parse_grch38_substitution,
    parse_rsids,
)
from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME

SLICE = Path(__file__).resolve().parents[2] / "assets" / "civic_slice"
EVIDENCE = SLICE / "ClinicalEvidenceSummaries.tsv"
VARIANTS = SLICE / "VariantSummaries.tsv"
PROFILES = SLICE / "MolecularProfileSummaries.tsv"


@pytest.fixture
def built(tmp_path):
    return build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "snap", release="01-Aug-2026")


def _frame(result) -> pl.DataFrame:
    return pl.read_parquet(result.parquet_file)


# ── identity, which is the whole reason this source is buildable at all ────────────────────────────


def test_grch38_accession_is_scored_per_chromosome_not_by_version():
    """`NC_000001.11` is GRCh38 and `NC_000002.11` is GRCh37, and a version test conflates them.

    This is the bug that made a first pass report 208 reachable variants where the real figure was
    40, so it is pinned on both members of the confusable pair rather than on one example.
    """
    assert parse_grch38_substitution("NC_000001.11:g.100C>T") == ("1", 100, "C", "T")
    assert parse_grch38_substitution("NC_000002.11:g.29432664C>T") is None
    assert parse_grch38_substitution("NC_000002.12:g.29209798C>T") == ("2", 29209798, "C", "T")
    assert parse_grch38_substitution("NC_000001.10:g.100C>T") is None


def test_a_grch38_accession_we_cannot_parse_is_not_reported_as_absent():
    """"The source said nothing" and "the source said something we cannot hold" are two findings.

    A `del` on a GRCh38 accession needs a reference base the TSV does not carry, so it is withheld —
    but it must be counted separately from a record that has no GRCh38 accession at all.
    """
    assert parse_grch38_substitution("NC_000017.11:g.7674220del") is None
    assert has_unparsable_grch38("NC_000017.11:g.7674220del") is True
    assert has_unparsable_grch38("NC_000017.10:g.7577538del") is False, "GRCh37 is not unparsable-38"
    assert has_unparsable_grch38("") is False
    assert has_unparsable_grch38("NC_000002.12:g.29209798C>T") is False, "parsed, so not unparsable"


def test_rsids_are_selected_by_shape_and_normalized():
    """`variant_aliases` mixes rs-numbers with protein names, so they are picked by shape."""
    assert parse_rsids("R1275Q, rs113994087, RS12345, rs113994087") == ["rs113994087", "rs12345"]
    assert parse_rsids("") == []
    assert parse_rsids("rsSOMETHING, rs, 12345") == [], "an rs-shaped prefix is not an rs-number"


def test_every_kept_row_carries_an_identity_and_names_which_one(built):
    frame = _frame(built)
    assert frame.height == built.record_count
    for row in frame.iter_rows(named=True):
        assert row["identity_derivation"] in CIVIC_IDENTITY_DERIVATIONS
        has_rsid = row["rsid"] is not None
        has_coords = row["chrom"] is not None and row["start"] is not None
        assert has_rsid or has_coords, "a kept row with no identity is what the drop reason is for"
        # The stamp is not decoration: it must agree with what the row actually carries.
        assert row["identity_derivation"] == (
            "both" if has_rsid and has_coords else "rsid" if has_rsid else "grch38_hgvs"
        )


def test_civic_grch37_coordinates_are_provenance_and_never_the_emitted_position(built):
    """The snapshot's `chrom`/`start` are GRCh38; CIViC's own GRCh37 pair rides along separately.

    Where both are present they must differ — if a builder ever emitted the GRCh37 position as the
    identity, this is the assertion that would catch it.
    """
    frame = _frame(built)
    both = frame.filter(
        pl.col("start").is_not_null() & pl.col("civic_grch37_start").is_not_null()
    )
    assert both.height > 0, "the fixture must exercise a row carrying both builds"
    assert (both["start"] != both["civic_grch37_start"]).all()


def test_a_partial_grch37_coordinate_is_withheld_whole(tmp_path):
    """CIViC id 1770 has a build and a start and no chromosome — `@identity-whole-or-none`.

    A coordinate missing its contig is not a position, and carrying the half of it that exists would
    put a number in a column nothing can place. Both provenance cells go, or neither.
    """
    kept_ids = set(_frame(build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "ref"))["variant_id"])
    rows = list(csv.DictReader(VARIANTS.open(newline="", encoding="utf-8"), delimiter="\t"))
    target = next(r for r in rows if int(r["variant_id"]) in kept_ids and parse_rsids(r["variant_aliases"]))
    maimed = dict(target, chromosome="", reference_build="GRCh37", start="10188305")
    variants = tmp_path / "VariantSummaries.tsv"
    with variants.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows([maimed if r is target else r for r in rows])
    result = build_snapshot(EVIDENCE, variants, PROFILES, tmp_path / "snap")
    frame = _frame(result).filter(pl.col("variant_id") == int(maimed["variant_id"]))
    assert frame.height > 0, "the maimed variant must still be reached, or this proves nothing"
    assert frame["civic_grch37_chrom"].is_null().all()
    assert frame["civic_grch37_start"].is_null().all(), "a start with no contig is not a position"


# ── the drop registry, which must account for every input row ──────────────────────────────────────


def test_the_drop_registry_accounts_for_every_input_row(built):
    """An equality over the walked registry, never a floor (`@registry-completeness`).

    Silent truncation reads as full coverage, so the sum is the property under test rather than the
    individual counts.
    """
    assert set(built.dropped) == set(CIVIC_DROP_REASONS), "every reason present, so a zero is measured"
    assert built.record_count + sum(built.dropped.values()) == built.input_rows


def test_a_row_filtered_without_a_counter_beside_it_is_refused():
    """The equality is enforced in the build, not only asserted here.

    Exercised directly rather than by contriving a broken build: a filter added without a counter is
    arithmetic the guard can be shown to catch, and a test that has to break the builder to reach a
    guard usually ends up proving something else.
    """
    assert_registry_closes(10, 4, {"a": 6})
    assert_registry_closes(0, 0, {"a": 0}), "an empty release closes too"
    with pytest.raises(CivicBuildError, match="does not account for every input row"):
        assert_registry_closes(10, 4, {"a": 5})
    with pytest.raises(CivicBuildError, match="@registry-completeness"):
        assert_registry_closes(10, 4, {"a": 7}), "over-counting is as wrong as under-counting"


def test_somatic_rows_are_dropped_by_count_not_silently(built):
    """The 73% somatic drop is the objection this snapshot was designed against.

    The number belongs in the result, never only in a docstring, so it is asserted as a published
    count rather than as an absence from the output.
    """
    assert built.dropped["non_germline_origin"] > 0
    frame = _frame(built)
    assert set(frame["variant_origin"].unique()) <= {"Rare Germline", "Common Germline"}


def test_a_combination_profile_is_distinguished_from_a_dangling_one(built, tmp_path):
    """Two different facts, and inferring both from one failed join would blur them.

    The combination row in the fixture is constructed, because upstream has no germline example — 209
    multi-variant profiles carry 547 accepted rows and not one of them is germline.
    """
    assert built.dropped["combination_profile"] == 1
    assert built.dropped["no_variant_record"] == 0

    rows = list(csv.DictReader(EVIDENCE.open(newline="", encoding="utf-8"), delimiter="\t"))
    dangling = dict(
        rows[0], evidence_id="9999903", molecular_profile_id="99999999",
        variant_origin="Rare Germline", significance="Predisposition", evidence_direction="Supports",
    )
    evidence = tmp_path / "ClinicalEvidenceSummaries.tsv"
    with evidence.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows + [dangling])
    result = build_snapshot(evidence, VARIANTS, PROFILES, tmp_path / "snap")
    assert result.dropped["no_variant_record"] == 1, "a profile nothing knows is not a combination"
    assert result.dropped["combination_profile"] == built.dropped["combination_profile"]


def test_a_dropped_record_that_carries_a_caid_is_counted_so_the_class_stays_addressable(built):
    """`unresolvable_identity` is not the end of those records — 235 of 290 carry a ClinGen CAID."""
    assert built.dropped["unresolvable_identity"] > 0
    assert 0 < built.unresolvable_with_caid <= built.dropped["unresolvable_identity"]


# ── the direction axis, and the withhold that is the point of it ───────────────────────────────────


def test_does_not_support_withholds_direction_rather_than_flipping_it(built):
    """Refuting predisposition does not establish protectiveness — the three-valued rule.

    `None` is never `False`. Writing `protective` where the source only refuted a risk claim would be
    an unknown recorded as its negation, which is the single most-repeated defect in this workspace.
    """
    assert CIVIC_DIRECTION_MAP[("Predisposition", "Does Not Support")] is None
    assert CIVIC_DIRECTION_MAP[("Protectiveness", "Does Not Support")] is None
    assert CIVIC_DIRECTION_MAP[("Predisposition", "Supports")] == "risk"
    assert CIVIC_DIRECTION_MAP[("Protectiveness", "Supports")] == "protective"

    frame = _frame(built)
    refuting = frame.filter(pl.col("evidence_direction_raw") == "Does Not Support")
    assert refuting.height == built.withheld_direction > 0
    assert refuting["direction"].is_null().all(), "a refutation states no direction"
    # And the row is KEPT, with the source's own words intact — withheld is not dropped.
    assert set(refuting["significance_raw"].unique()) <= {"Predisposition", "Protectiveness"}


def test_the_direction_map_covers_exactly_the_pairs_the_filter_admits(built):
    """The map and the significance filter are one decision; a pair in neither is a silent drop."""
    frame = _frame(built)
    for row in frame.iter_rows(named=True):
        pair = (row["significance_raw"], row["evidence_direction_raw"])
        assert pair in CIVIC_DIRECTION_MAP
        assert row["direction"] == CIVIC_DIRECTION_MAP[pair]


def test_a_variant_with_both_camps_is_counted_and_never_collapsed(tmp_path):
    """Contested is a finding, not a mess to tidy — choosing a winner is `mode()` over a group.

    Constructed, because no accepted CIViC variant carries both camps: under `ACCEPTED` the contested
    count over the whole database is zero.
    """
    rows = list(csv.DictReader(EVIDENCE.open(newline="", encoding="utf-8"), delimiter="\t"))
    risk = next(
        r for r in rows
        if r["significance"] == "Predisposition" and r["evidence_direction"] == "Supports"
    )
    protective = dict(
        risk, evidence_id="9999904", significance="Protectiveness", evidence_direction="Supports"
    )
    evidence = tmp_path / "ClinicalEvidenceSummaries.tsv"
    with evidence.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows + [protective])
    result = build_snapshot(evidence, VARIANTS, PROFILES, tmp_path / "snap")
    assert result.contested_variants == 1
    frame = _frame(result).filter(pl.col("evidence_id").is_in([int(risk["evidence_id"]), 9999904]))
    assert set(frame["direction"]) == {"risk", "protective"}, "both rows survive; neither wins"


# ── reproducibility and provenance ─────────────────────────────────────────────────────────────────


def test_a_rebuild_is_byte_identical(tmp_path):
    """Principle 7. A parquet has no inherent row order, so the sort is what makes this true."""
    first = build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "a", release="01-Aug-2026")
    second = build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "b", release="01-Aug-2026")
    assert first.parquet_file.read_bytes() == second.parquet_file.read_bytes()


def test_column_order_is_fixed_rather_than_whatever_the_dict_produced(built):
    assert _frame(built).columns == list(CIVIC_COLUMNS)


def test_release_json_records_the_status_basis_and_the_licence(built):
    """The bulk file is `accepted`-only and the API default is not, so the basis must be stated.

    Two published surfaces of one source differ 2.35x; a count that does not name its basis is a
    count nothing can compare.
    """
    release = json.loads((built.out_dir / RELEASE_FILENAME).read_text())
    assert release["status_basis"] == "accepted"
    assert release["genome_build"] == "GRCh38"
    assert release["licence"] == "CC0-1.0"
    assert release["redistributable"] is True, "CC0 — the first snapshot here that may be published"
    assert release["dataset"] == "civic_01-Aug-2026"
    assert set(release["dropped"]) == set(CIVIC_DROP_REASONS)
    assert release["record_count"] + sum(release["dropped"].values()) == release["input_rows"]
    assert "NON_REJECTED" in release["notice"], "the reader is told which basis is not this one"


def test_a_build_with_no_release_named_records_an_unknown_dataset_not_a_guess(tmp_path):
    result = build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "snap")
    assert result.dataset is None
    assert json.loads((result.out_dir / RELEASE_FILENAME).read_text())["dataset"] is None


def test_a_missing_column_fails_the_build_rather_than_the_row(tmp_path):
    """CIViC changing its release layout is a build-shaped failure, caught before any output."""
    rows = list(csv.DictReader(VARIANTS.open(newline="", encoding="utf-8"), delimiter="\t"))
    fields = [f for f in rows[0] if f != "allele_registry_id"]
    variants = tmp_path / "VariantSummaries.tsv"
    with variants.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(CivicBuildError, match="allele_registry_id"):
        build_snapshot(EVIDENCE, variants, PROFILES, tmp_path / "snap")
    assert not (tmp_path / "snap" / SNAPSHOT_DATA_DIRNAME).exists(), "no partial snapshot left behind"


def test_a_pmid_is_only_read_where_the_source_really_is_pubmed(built):
    """`citation_id` is namespaced by `source_type`; an ASCO abstract id lives in the same column."""
    rows = list(csv.DictReader(EVIDENCE.open(newline="", encoding="utf-8"), delimiter="\t"))
    by_id = {int(r["evidence_id"]): r for r in rows}
    for row in _frame(built).iter_rows(named=True):
        source = by_id[row["evidence_id"]]
        if (source["source_type"] or "").upper() == "PUBMED":
            assert row["pmid"] == source["citation_id"]
        else:
            assert row["pmid"] is None, "an abstract id filed as a PMID is the @pmid-vs-pmcid class"
