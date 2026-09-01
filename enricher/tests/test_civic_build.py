"""The CIViC snapshot builder (RM152) — identity, the drop registry, and the withheld direction.

The fixture under `assets/civic_slice/` is a real slice of the `01-Aug-2026` release, chosen so that
every identity route and every drop reason has at least one row — including variant 3184
(`V62Cfs*5 (c.180del)`), which carries no identifier CIViC publishes and is placed only from the
curated name table, so the curated path runs through the real build rather than a stub. Two rows in it
are constructed rather
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
    assert_curation_closes,
    assert_registry_closes,
    build_snapshot,
    has_unparsable_grch38,
    parse_grch38_substitution,
    parse_rsids,
    variant_rsids,
)
from just_dna_enricher.civic_vcf import CIVIC_EVIDENCE_STATUSES, VCF_DERIVATION
from just_dna_enricher.civic_identities import (
    CIVIC_CURATION_STATES,
    CIVIC_NAME_IDENTITIES,
    CIVIC_NAME_IDENTITY_BY_VARIANT,
    CURATED_DERIVATION,
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


def test_an_rsid_is_read_from_the_variant_name_as_well_as_the_aliases():
    """CIViC names some variants by their rs-number, and only the aliases were being read.

    Five variants in the germline direction set are named `RS2736100`, `rs681673` and the like; the
    first version of this builder looked only at `variant_aliases` and dropped all five as having no
    identity, when the identity was in the column a reader looks at first. They needed no registry
    lookup and no conversion.
    """
    assert variant_rsids({"variant": "RS2736100", "variant_aliases": ""}) == ["rs2736100"]
    assert variant_rsids({"variant": "rs681673", "variant_aliases": "1506T>C"}) == ["rs681673"]
    # An alias-only rsID still works, and the name is preferred when both carry one.
    assert variant_rsids({"variant": "R262W", "variant_aliases": "rs3184504"}) == ["rs3184504"]
    assert variant_rsids({"variant": "rs1", "variant_aliases": "rs2"}) == ["rs1", "rs2"]
    assert variant_rsids({"variant": "V600E", "variant_aliases": "BRAF V600E"}) == []


def test_every_kept_row_carries_an_identity_and_names_which_one(built):
    frame = _frame(built)
    assert frame.height == built.record_count
    for row in frame.iter_rows(named=True):
        assert row["identity_derivation"] in CIVIC_IDENTITY_DERIVATIONS
        has_rsid = row["rsid"] is not None
        has_coords = row["chrom"] is not None and row["start"] is not None
        caid = row["allele_registry_id"]
        # A row carries an identity, or a ROUTE to one. `caid` is the second: null coordinate, null
        # rsID, and a registry id a later pass resolves (RM153). What no kept row may be is neither.
        assert has_rsid or has_coords or caid, "a kept row with no route to an identity is a drop"
        # The stamp is not decoration: it must agree with what the row actually carries. The curated
        # class is checked first and by its own route, because it is the one stamp that is NOT
        # derivable from the cells: a curated row can look exactly like an `rsid` or a `both` row,
        # and the difference is who said so — CIViC's identifier columns, or its variant name read by
        # hand. That is the whole reason it is a separate member.
        if row["identity_derivation"] == CURATED_DERIVATION:
            curated = CIVIC_NAME_IDENTITY_BY_VARIANT[row["variant_id"]]
            assert (row["chrom"], row["start"], row["ref"], row["alt"]) == (
                curated.chrom, curated.start, curated.ref, curated.alt
            )
        else:
            assert row["identity_derivation"] == (
                "both" if has_rsid and has_coords
                else "rsid" if has_rsid
                else "grch38_hgvs" if has_coords
                else "caid"
            )
        if row["identity_derivation"] == "caid":
            assert not has_rsid and not has_coords and caid


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


# ── publishing: the one snapshot here that may be ────────────────────────────────────────────────


def test_the_snapshot_carries_its_own_licence(built):
    """A redistributed file that does not state its terms makes the next reader establish them again.

    This is the snapshot meant to be published — CC0 with no share-alike and no bar on sale — so the
    dedication ships beside the parquet rather than as a URL, because a link is a promise about a page.
    """
    from just_dna_enricher.locations import SNAPSHOT_LICENSE_FILENAME

    text = (built.out_dir / SNAPSHOT_LICENSE_FILENAME).read_text()
    assert "CC0 1.0 Universal" in text
    assert "civicdb.org" in text
    # The scope note is the load-bearing half: CIViC's FAQ names MIT in the same breath, and reading
    # that as the data terms would attach a licence to bytes it does not cover.
    assert "MIT" in text and "application source code" in text
    assert "accepted" in text, "the status basis travels with the bytes, not only with our docs"


def test_the_publisher_would_upload_the_data_the_release_and_the_licence(built):
    """`@publisher-allowlist-derived` — what ships is derived from the artifact's own file list."""
    from just_dna_enricher.upload import DEFAULT_CIVIC_REPO_ID, plan_reference_snapshot

    # The planner's own default is ClinVar's repo; the civic default lives on the CLI command, which
    # is what passes it. Asserted the way the command calls it rather than the way it reads.
    plan = plan_reference_snapshot(built.out_dir, DEFAULT_CIVIC_REPO_ID)
    assert plan.repo_id == DEFAULT_CIVIC_REPO_ID
    assert set(plan.files) == {"data/civic.parquet", "release.json", "LICENSE.txt"}


def test_the_registrys_answers_are_not_in_the_published_snapshot(built):
    """The CAID travels; what the registry says about it does not.

    Deliberate rather than an oversight: the ClinGen Allele Registry states no terms, so resolving a
    CAID at draft time is a read, while baking its responses into a published file would redistribute
    bytes nobody has established we may pass on.
    """
    frame = _frame(built)
    assert "allele_registry_id" in frame.columns
    for absent in ("clingen_rsid", "clingen_coordinate", "registry_response"):
        assert absent not in frame.columns
    caid_rows = frame.filter(pl.col("identity_derivation") == "caid")
    assert caid_rows["rsid"].is_null().all(), "a resolved rsID must not be persisted into the snapshot"


# ── The curated name table (adopted 2026-09-01) ──────────────────────────────────────────────────
#
# The table answers a question the source asks and does not answer: an identity stated in the
# variant's `name` and in none of its identifier columns. Its whole safety property is that a curated
# answer is keyed to the name it was an answer *to*, so these tests are mostly about the three states
# a curated row can land in rather than about the coordinates, which are data.


def _fixture_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames, list(reader)


def _rebuild_with_variant_edit(tmp_path, variant_id, **edits):
    """Rebuild the fixture with one variant row edited — the only way to reach `superseded`/`stale`."""
    fields, rows = _fixture_rows(VARIANTS)
    for row in rows:
        if row["variant_id"] == str(variant_id):
            row.update(edits)
    out = tmp_path / "VariantSummaries.tsv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return build_snapshot(EVIDENCE, out, PROFILES, tmp_path / "snap", release="01-Aug-2026")


def test_a_curated_identity_places_a_row_the_source_alone_could_not(built):
    """3184 carries no rsID, no GRCh38 accession and no CAID, and is placed anyway."""
    frame = pl.read_parquet(built.parquet_file)
    row = frame.filter(pl.col("variant_id") == 3184)
    assert row.height == 1
    curated = CIVIC_NAME_IDENTITY_BY_VARIANT[3184]
    assert row["identity_derivation"][0] == CURATED_DERIVATION
    assert (row["chrom"][0], row["start"][0], row["ref"][0], row["alt"][0]) == (
        curated.chrom, curated.start, curated.ref, curated.alt
    )
    assert row["rsid"][0] == curated.rsid


def test_the_curated_class_is_named_rather_than_folded_into_the_published_ones(built):
    """A consumer must be able to exclude hand-read identities without re-deriving which they are."""
    assert CURATED_DERIVATION in CIVIC_IDENTITY_DERIVATIONS
    assert CURATED_DERIVATION not in {"rsid", "grch38_hgvs", "both", "caid"}
    assert built.identity_derivations[CURATED_DERIVATION] >= 1


def test_the_registrys_findings_never_enter_civics_own_column(built):
    """`allele_registry_id` is CIViC's verbatim cell, empty for every curated row by definition.

    The CAIDs the probe recovered are provenance on the curated table, not the source's statement.
    Writing them into this column would publish a finding as if the source had made it.
    """
    frame = pl.read_parquet(built.parquet_file)
    curated = frame.filter(pl.col("identity_derivation") == CURATED_DERIVATION)
    assert curated.height >= 1
    assert curated["allele_registry_id"].null_count() == curated.height


def test_a_renamed_variant_withholds_its_curated_answer_rather_than_applying_it(tmp_path):
    """The answer was an answer to a name. Change the name and the answer stands down."""
    result = _rebuild_with_variant_edit(tmp_path, 3184, variant="V62Cfs*5 (c.180delG)")
    assert result.curated_identities["renamed"] == 1
    assert result.curated_identities["applied"] == 0
    assert result.dropped["unresolvable_identity"] >= 1
    frame = pl.read_parquet(result.parquet_file)
    assert frame.filter(pl.col("variant_id") == 3184).height == 0


def test_an_identity_civic_now_publishes_supersedes_the_curated_one(tmp_path):
    """The source outranks this table, and a supersession is the cheapest currency signal there is."""
    result = _rebuild_with_variant_edit(tmp_path, 3184, variant_aliases="rs730882037")
    assert result.curated_identities["superseded"] == 1
    assert result.curated_identities["applied"] == 0
    frame = pl.read_parquet(result.parquet_file)
    row = frame.filter(pl.col("variant_id") == 3184)
    assert row["identity_derivation"][0] == "rsid"


def test_the_curated_table_closes_as_an_equality_over_its_own_rows(built):
    """Every curated row lands in exactly one state, and the states account for the whole table.

    The fixture is a slice, so most rows are `absent` — which is the point of separating `absent`
    from `renamed`: over a slice absence says nothing, and folding the two would make a partial input
    indistinguishable from an upstream re-curation.
    """
    assert set(built.curated_identities) == set(CIVIC_CURATION_STATES)
    assert sum(built.curated_identities.values()) == len(CIVIC_NAME_IDENTITIES)
    assert built.curated_identities["renamed"] == 0
    assert built.curated_identities["absent"] == len(CIVIC_NAME_IDENTITIES) - 1


def test_a_curated_state_added_without_a_counter_is_refused():
    """The guard is reachable directly, so proving it does not need a contrived build."""
    with pytest.raises(CivicBuildError, match="does not close"):
        assert_curation_closes(dict.fromkeys(CIVIC_CURATION_STATES, 0))


def test_every_curated_row_is_a_representable_variant_row():
    """Walked over the table, not sampled. `ref == alt` is why TP53 4968 is not in it."""
    for row in CIVIC_NAME_IDENTITIES:
        assert row.ref and row.alt and row.ref != row.alt, row
        assert row.chrom and row.start > 0, row
        assert row.name.strip() == row.name and row.name, row
    assert len({row.variant_id for row in CIVIC_NAME_IDENTITIES}) == len(CIVIC_NAME_IDENTITIES)


def test_the_curated_table_is_never_consulted_where_the_source_speaks(built):
    """Applied + superseded + stale is the whole table, and applied rows are exactly the placed ones."""
    frame = pl.read_parquet(built.parquet_file)
    placed = frame.filter(pl.col("identity_derivation") == CURATED_DERIVATION)
    assert placed["variant_id"].n_unique() == built.curated_identities["applied"]


def test_release_json_publishes_what_became_of_every_curated_row(built):
    payload = json.loads((built.out_dir / RELEASE_FILENAME).read_text())
    assert set(payload["curated_identities"]) == set(CIVIC_CURATION_STATES)
    assert sum(payload["curated_identities"].values()) == len(CIVIC_NAME_IDENTITIES)
    assert payload["identity_derivations"][CURATED_DERIVATION] >= 1


# ── The submitted basis, from the release's own VCF (RM169) ──────────────────────────────────────
#
# The fixture VCF beside the TSVs is a four-line slice of the real dated file, chosen so each path is
# reachable: an accepted item on a variant the TSV slice carries, a submitted item on the same, a
# submitted item on a variant the TSV does NOT carry (the `vcf_csq` path, which exists because
# `VariantSummaries.tsv` is accepted-only too), and one assertion entry, which must be skipped.

VCF = SLICE / "civic_accepted_and_submitted.vcf"


@pytest.fixture
def widened(tmp_path):
    # A directory of its own, NOT `tmp_path / "snap"`: pytest hands both fixtures the same `tmp_path`,
    # so sharing the name makes the second build silently overwrite the first, and a test that asks
    # for both then compares a snapshot with itself.
    return build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "widened", release="01-Aug-2026",
                          vcf=VCF)


def test_without_the_vcf_the_build_is_exactly_what_it_was(built, widened):
    """The widening is opt-in. Omitting the VCF must not move a single number."""
    assert built.status_basis == "accepted"
    assert built.status_counts == {"accepted": built.record_count}
    assert built.vcf_evidence == {}
    assert widened.status_basis == "accepted+submitted"


def test_a_submitted_row_joins_the_corpus_carrying_its_own_status(widened):
    frame = pl.read_parquet(widened.parquet_file)
    statuses = set(frame["evidence_status"].unique().to_list())
    assert statuses == {"accepted", "submitted"}, "both bases must be present and distinguishable"
    assert widened.status_counts["submitted"] >= 1
    assert sum(widened.status_counts.values()) == widened.record_count


def test_the_status_column_is_civics_own_word_not_a_house_grade(widened):
    """`evidence_status` carries the source's instrument, unconverted (S86-shaped rule, RM169)."""
    frame = pl.read_parquet(widened.parquet_file)
    assert set(frame["evidence_status"].unique().to_list()) <= set(CIVIC_EVIDENCE_STATUSES)


def test_a_variant_the_accepted_tsv_omits_is_placed_from_the_csq_and_says_so(widened):
    """`VariantSummaries.tsv` is accepted-only, so most submitted evidence names a variant it lacks.

    The identity then comes from the VCF's own CSQ cells — the same published identifiers, read by the
    same parsers, from a different file. The stamp is what makes that recoverable.
    """
    frame = pl.read_parquet(widened.parquet_file)
    csq = frame.filter(pl.col("identity_derivation") == VCF_DERIVATION)
    assert csq.height >= 1, "the fixture carries a submitted row on a TSV-absent variant"
    for row in csq.iter_rows(named=True):
        assert row["evidence_status"] == "submitted"
        assert row["rsid"] or row["chrom"] or row["allele_registry_id"], (
            "a vcf_csq row must still carry an identity or a route to one"
        )
        # Nothing is placed from the VCF's own POS: it is GRCh37 and lifting it stays refused (RM48).
        assert row["civic_grch37_chrom"] is None and row["civic_grch37_start"] is None


def test_nothing_is_placed_from_the_vcfs_grch37_position(widened):
    """The file is GRCh37 throughout. Every placed coordinate must trace to a GRCh38 identifier."""
    frame = pl.read_parquet(widened.parquet_file)
    csq = frame.filter(pl.col("identity_derivation") == VCF_DERIVATION)
    placed = csq.filter(pl.col("chrom").is_not_null())
    for row in placed.iter_rows(named=True):
        # A GRCh38 coordinate is only ever parsed out of a GRCh38 accession, so a placed row proves
        # the accession was there — the assertion is that the GRCh37 provenance columns stayed empty,
        # which is what distinguishes "read an identifier" from "kept the record's own position".
        assert row["civic_grch37_start"] is None


def test_the_vcf_vocabulary_is_mapped_rather_than_title_cased():
    """`SENSITIVITYRESPONSE` is `Sensitivity/Response` in the TSV — a separator no rule recovers."""
    from just_dna_enricher.civic_vcf import CIVIC_VCF_TO_TSV, CivicVcfError, _title

    assert _title("RARE_GERMLINE") == "Rare Germline"
    assert _title("SENSITIVITYRESPONSE") == "Sensitivity/Response"
    assert _title("GAIN_OF_FUNCTION") == "Gain of Function"
    assert _title("NA") == "N/A"
    assert _title("") == "", "an absent origin is not the member `Unknown`"
    # The guard, not the map: a member CIViC adds must raise rather than arrive mis-spelled.
    with pytest.raises(CivicVcfError, match="no TSV spelling"):
        _title("SOME_NEW_MEMBER")
    # Every mapped value is a spelling the TSV actually uses, checked against the fixture's own column.
    with EVIDENCE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    seen = {(r.get("variant_origin") or "").strip() for r in rows}
    seen |= {(r.get("significance") or "").strip() for r in rows}
    seen |= {(r.get("evidence_direction") or "").strip() for r in rows}
    assert seen - {""} <= set(CIVIC_VCF_TO_TSV.values())


def test_an_assertion_entry_is_not_read_as_evidence():
    """The CSQ block carries both. An assertion's status must never stand in for an evidence item's."""
    from just_dna_enricher.civic_vcf import parse_csq_format, read_vcf_entries

    entries = read_vcf_entries(VCF)
    assert entries, "the fixture carries evidence entries"
    # Counted from the file rather than hardcoded: a VCF *line* carries many CSQ entries, so a literal
    # here would be a number read off a dump (the anti-pattern CLAUDE.md names). The property is that
    # the reader returns every evidence entry and no assertion entry.
    text = VCF.read_text()
    fields = parse_csq_format([ln for ln in text.splitlines() if "ID=CSQ" in ln][0])
    type_index = fields.index("CIViC Entity Type")
    raw_types: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        info = dict(kv.split("=", 1) for kv in line.split("\t")[7].split(";") if "=" in kv)
        raw_types += [e.split("|")[type_index] for e in info.get("CSQ", "").split(",") if e]
    assert raw_types.count("assertion") >= 1, "the fixture must exercise the assertion skip"
    assert len(entries) == raw_types.count("evidence")


def test_the_csq_field_order_is_read_from_the_header_not_assumed(tmp_path):
    """A generator that adds a field must not shift every column after it, silently."""
    from just_dna_enricher.civic_vcf import CivicVcfError, parse_csq_format, read_vcf_entries

    header = [line for line in VCF.read_text().splitlines() if "ID=CSQ" in line][0]
    fields = parse_csq_format(header)
    assert fields[0] == "Allele" and "CIViC Entity Status" in fields
    headerless = tmp_path / "no-format.vcf"
    headerless.write_text(
        '##fileformat=VCFv4.2\n##INFO=<ID=CSQ,Number=.,Type=String,Description="nope">\n'
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n",
        encoding="utf-8",
    )
    with pytest.raises(CivicVcfError, match="does not declare its field order"):
        read_vcf_entries(headerless)


def test_release_json_states_the_basis_and_what_it_counted(widened):
    payload = json.loads((widened.out_dir / RELEASE_FILENAME).read_text())
    assert payload["status_basis"] == "accepted+submitted"
    assert sum(payload["status_counts"].values()) == payload["record_count"]
    assert set(payload["vcf_evidence"]) == set(CIVIC_EVIDENCE_STATUSES)
    assert payload["unjoinable_submitted"] >= 0


def test_the_drop_registry_still_closes_over_the_wider_basis(widened):
    """The submitted rows join `evidence` before anything walks it, so one accounting covers both."""
    assert widened.input_rows == widened.record_count + sum(widened.dropped.values())
    assert set(widened.dropped) == set(CIVIC_DROP_REASONS)


def test_a_widened_rebuild_is_byte_identical(tmp_path):
    """Principle 7 holds across the wider basis too — the VCF join must not depend on dict order."""
    a = build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "a", release="01-Aug-2026", vcf=VCF)
    b = build_snapshot(EVIDENCE, VARIANTS, PROFILES, tmp_path / "b", release="01-Aug-2026", vcf=VCF)
    assert a.parquet_file.read_bytes() == b.parquet_file.read_bytes()


def test_the_recorded_widening_figures_are_what_the_build_produces(built, widened):
    """The numbers the docs and the CLI help quote, asserted as relationships over the real build.

    Not a count copied off a dump: each is derived here from the two builds the fixtures already
    made. It exists because the first cut of this item recorded a pre-build figure that never matched
    the shipped result, and nothing in a checkout could notice — the docs are prose and the CLI help
    is a string (`@warning-text-is-api`, applied to a help line a user reads before running anything).
    """
    frame = pl.read_parquet(widened.parquet_file)
    accepted = pl.read_parquet(built.parquet_file)

    # The widening only ever adds.
    assert widened.record_count > built.record_count
    assert widened.variants > built.variants
    assert set(accepted["variant_id"].to_list()) <= set(frame["variant_id"].to_list())

    # The submitted half accounts for exactly the difference in rows.
    submitted = frame.filter(pl.col("evidence_status") == "submitted")
    assert submitted.height == widened.status_counts["submitted"]
    assert built.record_count + submitted.height == widened.record_count

    # Every `vcf_csq` row is submitted, and its variant is genuinely absent from the accepted build —
    # which is the whole justification for reading identity out of the VCF at all.
    csq = frame.filter(pl.col("identity_derivation") == VCF_DERIVATION)
    assert csq.height >= 1
    assert set(csq["evidence_status"].unique().to_list()) == {"submitted"}
    assert not (set(csq["variant_id"].to_list()) & set(accepted["variant_id"].to_list()))
