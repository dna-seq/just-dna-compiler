"""The clinical-assertion pass (0.6, RM25): resolved coordinates in, review tier preserved.

The fixture is a real ClinVar snapshot in miniature — the same parquet columns `clinvar_build` writes,
read through the same `clinvar._connect` view the resolver link and the cross-check use, so nothing
here mocks the transformation it is testing. Two records sit on one allele at two review tiers,
because that is the distinction the table exists to keep and a single-record fixture could not show it.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.assertions import (
    ASSERTION_GENOME_BUILD,
    ClinicalAssertionError,
    enrich_clinical_assertions,
    snapshot_dataset,
)
from just_dna_enricher.clinvar_build import review_stars
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.sources import SourceRow
from just_dna_format.vrs import derive_vrs_allele_id

_LICENCE_CSV = preferred_spelling(SOURCES_CSV)

_RYR1_KEY = derive_vrs_allele_id("19", 38449938, "C", "T")
_SICKLE_KEY = derive_vrs_allele_id("11", 5227002, "T", "A")

_YAML = """\
schema_version: "1.0"
module:
  name: assertion_demo
  title: Assertions
  description: fixture
  report_title: Report
genome_build: {build}
"""

# Real ClinVar values: rs118192172 (RYR1) carries a 4-star practice-guideline record and a 1-star
# single-submitter record under a different condition; rs334 (HBB) is 2-star.
_RECORDS = [
    {
        "chrom": "19", "start": 38449938, "ref": "C", "alt": "T", "rsid": "rs118192172",
        "variation_id": "133", "allele_id": "1", "gene": "RYR1", "genes": "RYR1",
        "clin_sig": "pathogenic", "clin_sig_raw": "Pathogenic",
        "review_status": "practice_guideline", "review_stars": 4,
        "condition": "Malignant hyperthermia susceptibility",
        "molecular_consequence": None, "variant_type": None, "origin": None,
    },
    {
        "chrom": "19", "start": 38449938, "ref": "C", "alt": "T", "rsid": "rs118192172",
        "variation_id": "134", "allele_id": "2", "gene": "RYR1", "genes": "RYR1",
        "clin_sig": "uncertain_significance", "clin_sig_raw": "Uncertain_significance",
        "review_status": "criteria_provided,_single_submitter", "review_stars": 1,
        "condition": "Central core disease",
        "molecular_consequence": None, "variant_type": None, "origin": None,
    },
    {
        "chrom": "11", "start": 5227002, "ref": "T", "alt": "A", "rsid": "rs334",
        "variation_id": "15333", "allele_id": "3", "gene": "HBB", "genes": "HBB",
        "clin_sig": "pathogenic", "clin_sig_raw": "Pathogenic",
        "review_status": "criteria_provided,_multiple_submitters,_no_conflicts", "review_stars": 2,
        "condition": "Sickle cell anemia",
        "molecular_consequence": None, "variant_type": None, "origin": None,
    },
]


def _snapshot(tmp_path: Path, *, release: str | None = "2026-06-27") -> Path:
    """A ClinVar snapshot in the real on-disk layout: `data/*.parquet` plus a `release.json`."""
    root = tmp_path / "clinvar"
    (root / "data").mkdir(parents=True)
    pl.DataFrame(_RECORDS).write_parquet(root / "data" / "chr.parquet")
    if release is not None:
        (root / "release.json").write_text(
            f'{{"clinvar_file_date": "{release}", "record_count": {len(_RECORDS)}}}',
            encoding="utf-8",
        )
    return root


def _spec(tmp_path: Path, *, build: str = "GRCh38", resolution: str | None = None) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML.format(build=build), encoding="utf-8")
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
        "19,38449938,C,T,C/T,risk,Malignant hyperthermia susceptibility,RYR1\n"
        "11,5227002,T,A,A/T,risk,Sickle-cell carrier,HBB\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text(
        "chrom,start,ref,pmid,conclusion\n"
        "19,38449938,C,12345678,RYR1 and malignant hyperthermia\n",
        encoding="utf-8",
    )
    (spec / "resolution.csv").write_text(
        resolution
        or (
            "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
            f"{_RYR1_KEY},rs118192172,19,38449938,C,T,{build},0,ensembl,resolved,\n"
            f"{_SICKLE_KEY},rs334,11,5227002,T,A,{build},0,ensembl,resolved,\n"
        ),
        encoding="utf-8",
    )
    return spec


# ── the review-status mapping ───────────────────────────────────────────────────────────────────


def test_the_star_mapping_is_tri_state_and_zero_is_a_rating() -> None:
    """`None` (nothing to rate) and `0` (rated as having no criteria) are different answers.

    Before RM25 this returned `0` for both, which reports an unread record as the weakest evidence
    available — a claim nobody made. It is also why the schema tier stores the column rather than
    deriving it: this mapping is a ClinVar convention, and Principle 2 bars those from that tier.
    """
    assert review_stars("practice_guideline") == 4
    assert review_stars("no_assertion_criteria_provided") == 0
    assert review_stars(None) is None
    assert review_stars("") is None
    assert review_stars("something ClinVar has not published") is None


# ── the pass ────────────────────────────────────────────────────────────────────────────────────


def test_both_records_on_one_allele_are_kept(tmp_path: Path) -> None:
    """The grain is (allele, archive record), not one row per variant.

    ClinVar holds several records per allele under different conditions at different review levels;
    collapsing them would pick a condition on the author's behalf.
    """
    spec = _spec(tmp_path)
    result = enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))

    assert not result.skipped_no_snapshot
    ryr1 = [r for r in result.rows if r.variant_key == _RYR1_KEY]
    assert {(r.variation_id, r.review_stars) for r in ryr1} == {("133", 4), ("134", 1)}
    assert {r.clin_sig for r in ryr1} == {"pathogenic", "uncertain_significance"}
    assert result.covered == sorted({_RYR1_KEY, _SICKLE_KEY})


def test_the_written_table_reloads_through_the_model(tmp_path: Path) -> None:
    """The compiler is the reader, so the pass's own output has to load the way it will be loaded —
    including ClinVar's comma-bearing review wording, which an unquoted writer would shred."""
    spec = _spec(tmp_path)
    enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))
    rows, errors, _ = load_csv_rows(
        spec / "clinical_assertions.csv", ClinicalAssertionRow, "clinical_assertions.csv"
    )
    assert errors == []
    statuses = {r.review_status for r in rows}
    assert "criteria_provided,_multiple_submitters,_no_conflicts" in statuses


def test_the_dataset_is_the_snapshots_own_release(tmp_path: Path) -> None:
    """A snapshot stamps its release into the row (the RM38 rule), so a consumer can tell a pinned
    file from whatever happened to be current — and a re-review from a re-read."""
    spec = _spec(tmp_path)
    result = enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))
    assert result.dataset == "clinvar_2026-06-27"
    assert {r.dataset for r in result.rows} == {"clinvar_2026-06-27"}


def test_a_snapshot_that_cannot_state_its_release_says_unknown_rather_than_inventing_one(
    tmp_path: Path,
) -> None:
    assert snapshot_dataset(_snapshot(tmp_path, release=None)) == "clinvar_unknown"


def test_an_allele_clinvar_has_no_record_for_gets_a_not_found_row(tmp_path: Path) -> None:
    """Asked and absent is a FACT about ClinVar, unlike a gene-curation body's silence — the two
    passes differ here on purpose, because the sources differ."""
    spec = _spec(
        tmp_path,
        resolution=(
            "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
            "1:999999:A,rs1,1,999999,A,G,GRCh38,0,ensembl,resolved,\n"
        ),
    )
    result = enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))
    assert result.missing and result.covered == []
    absent = result.rows[0]
    assert absent.status == "not_found" and absent.clin_sig is None
    assert absent.review_stars is None


def test_a_coordinate_on_another_build_is_never_queried(tmp_path: Path) -> None:
    """The fourth build confusion, refused before it can happen.

    The snapshot's lookup key is (chrom, start, ref, alt) and carries no assembly, so a GRCh37
    coordinate is a well-formed query returning a *different variant's* clinical call under this
    module's key. Skipped rows are reported apart from `missing`, because nobody asked about them.
    """
    spec = _spec(tmp_path, build="GRCh37")
    result = enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))
    assert result.off_build == sorted({_RYR1_KEY, _SICKLE_KEY})
    assert result.missing == [] and result.rows == []
    assert ASSERTION_GENOME_BUILD == "GRCh38"


def test_the_pass_records_clinvars_terms_at_its_own_layer(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))
    rows, errors, _ = load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert errors == []
    assert ("clinvar", "clinical_assertion") in {(r.source, r.layer) for r in rows}


def test_a_rerun_merges_rather_than_duplicating(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    snapshot = _snapshot(tmp_path)
    first = enrich_clinical_assertions(spec, clinvar_cache=snapshot)
    second = enrich_clinical_assertions(spec, clinvar_cache=snapshot)
    assert len(second.rows) == len(first.rows)
    assert {(r.variant_key, r.variation_id) for r in second.rows} == {
        (r.variant_key, r.variation_id) for r in first.rows
    }


def test_the_emitted_order_is_deterministic_and_independent_of_the_resolution_order(
    tmp_path: Path,
) -> None:
    """Parquet bytes depend on row order (Principle 7), so the writer sorts rather than inheriting."""
    forward = (
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
        f"{_RYR1_KEY},rs118192172,19,38449938,C,T,GRCh38,0,ensembl,resolved,\n"
        f"{_SICKLE_KEY},rs334,11,5227002,T,A,GRCh38,0,ensembl,resolved,\n"
    )
    reversed_lines = forward.splitlines()
    backward = "\n".join([reversed_lines[0], reversed_lines[2], reversed_lines[1]]) + "\n"
    snapshot = _snapshot(tmp_path)
    a = enrich_clinical_assertions(_spec(tmp_path / "a", resolution=forward), clinvar_cache=snapshot)
    b = enrich_clinical_assertions(_spec(tmp_path / "b", resolution=backward), clinvar_cache=snapshot)
    identity = [(r.variant_key, r.variation_id) for r in a.rows]
    assert identity == [(r.variant_key, r.variation_id) for r in b.rows]
    # ...and the order is the writer's own (by locus), not whichever the resolution table happened to
    # list — which is what makes the two runs above agree in the first place.
    assert [(r.chrom, r.start, r.variation_id) for r in a.rows] == [
        ("11", 5227002, "15333"), ("19", 38449938, "133"), ("19", 38449938, "134"),
    ]


def test_no_snapshot_is_a_no_op_with_a_warning_not_a_failure(tmp_path: Path) -> None:
    """`--offline` with nothing provisioned leaves any existing table as the pin, and says so."""
    spec = _spec(tmp_path)
    result = enrich_clinical_assertions(spec, offline=True, clinvar_cache=tmp_path / "nothing-here")
    assert result.skipped_no_snapshot and result.rows == []
    assert not (spec / "clinical_assertions.csv").exists()


def test_a_missing_resolution_table_refuses_and_says_which_pass_to_run(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    (spec / "resolution.csv").unlink()
    with pytest.raises(ClinicalAssertionError, match="enrich"):
        enrich_clinical_assertions(spec, clinvar_cache=_snapshot(tmp_path))


def test_strict_reports_the_alleles_clinvar_does_not_have(tmp_path: Path) -> None:
    spec = _spec(
        tmp_path,
        resolution=(
            "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status,fetched_at\n"
            "1:999999:A,rs1,1,999999,A,G,GRCh38,0,ensembl,resolved,\n"
        ),
    )
    with pytest.raises(ClinicalAssertionError, match="no ClinVar record"):
        enrich_clinical_assertions(spec, mode="strict", clinvar_cache=_snapshot(tmp_path))


def test_an_off_build_row_does_not_make_strict_refuse(tmp_path: Path) -> None:
    """`strict` means "a reproducible artifact", and a coordinate on another assembly is reproducibly
    out of this snapshot's reach — no authored edit could clear it, so it is not a strict matter."""
    spec = _spec(tmp_path, build="GRCh37")
    result = enrich_clinical_assertions(spec, mode="strict", clinvar_cache=_snapshot(tmp_path))
    assert result.off_build and result.missing == []
