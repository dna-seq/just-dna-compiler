"""RM170 — an authored direction beside a refutation the same source published.

Every snapshot here is the **real** builder run over `assets/civic_slice/`, and every expected value
is derived from that build at runtime. Where a case does not exist in the slice — a refutation with no
claim beside it, and one refutation over two variants — the snapshot is *filtered or fanned out* from
those same real rows rather than invented, so the shapes under test are the shapes the builder emits.
Both of those exist upstream and are measured in `docs/probes/CONTRADICTION_CORPORA.md`: CHEK2 788 and
TP53 4968 are refutation-only, and EID 8721 is one statement about a two-variant genotype.
"""

import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.civic_build import build_snapshot
from just_dna_enricher.civic_refutation import (
    CIVIC_REFUTES,
    REFUTATION_BESIDE_CLAIM,
    REFUTATION_WITHOUT_CLAIM,
    compare_refutations,
)
from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_DATA_DIRNAME
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

SLICE = Path(__file__).resolve().parents[2] / "assets" / "civic_slice"
EVIDENCE = SLICE / "ClinicalEvidenceSummaries.tsv"
VARIANTS = SLICE / "VariantSummaries.tsv"
PROFILES = SLICE / "MolecularProfileSummaries.tsv"
VCF = SLICE / "civic_accepted_and_submitted.vcf"


@pytest.fixture
def snapshot(tmp_path) -> Path:
    """The wider basis, which is the only one this class can appear on."""
    result = build_snapshot(
        EVIDENCE, VARIANTS, PROFILES, tmp_path / "snap", release="01-Aug-2026", vcf=VCF
    )
    return result.out_dir


def _frame(snapshot: Path) -> pl.DataFrame:
    return pl.read_parquet(snapshot / SNAPSHOT_DATA_DIRNAME / "civic.parquet")


def _rewrite(snapshot: Path, frame: pl.DataFrame, dest: Path) -> Path:
    """A snapshot with the same `release.json` and a rewritten parquet — real rows, filtered."""
    (dest / SNAPSHOT_DATA_DIRNAME).mkdir(parents=True)
    frame.write_parquet(dest / SNAPSHOT_DATA_DIRNAME / "civic.parquet")
    (dest / RELEASE_FILENAME).write_text(
        (snapshot / RELEASE_FILENAME).read_text(encoding="utf-8"), encoding="utf-8"
    )
    return dest


def _refuted_locus(snapshot: Path) -> dict:
    """The one locus in the slice that carries a refutation, read off the built snapshot."""
    frame = _frame(snapshot)
    refuting = frame.filter(pl.col("evidence_direction_raw") == CIVIC_REFUTES)
    assert refuting.height, "the slice must carry a refutation for this module to be testable"
    return refuting.row(0, named=True)


def _authored(locus: dict, *, direction: str | None) -> tuple[VariantRow, ResolutionRow]:
    """One authored row on that locus, plus the resolution row that places it."""
    key = f"{locus['chrom']}:{locus['start']}:{locus['ref']}:{locus['alt']}"
    variant = VariantRow(
        variant_key=key,
        chrom=locus["chrom"],
        start=locus["start"],
        ref=locus["ref"],
        genotype=f"{locus['alt']}{locus['alt']}",
        state="risk",
        direction=direction,
        conclusion="authored for this test",
    )
    # Keyed off the row's OWN `variant_key`, which the model derives (position-level, no alt) rather
    # than taking the one handed in — the same key `enrich` resolves against.
    resolution = ResolutionRow(
        variant_key=variant.variant_key,
        chrom=locus["chrom"],
        start=locus["start"],
        ref=locus["ref"],
        alts=locus["alt"],
        status="resolved",
    )
    return variant, resolution


def test_an_authored_direction_beside_a_refutation_is_a_finding(snapshot):
    """The RM170 case: the source supports this sign and also rebuts it, and nothing said so."""
    locus = _refuted_locus(snapshot)
    variant, resolution = _authored(locus, direction="risk")

    comparison = compare_refutations([variant], [resolution], reference=snapshot)

    assert comparison is not None and comparison.subjects == 1
    assert [f.code for f in comparison.findings] == [REFUTATION_BESIDE_CLAIM]
    finding = comparison.findings[0]
    assert [s.variant_key for s in finding.subjects] == [variant.variant_key]
    # Both sides quoted with their statuses, because which side an editor signed off is the thing an
    # author weighs — and the basis, because on the narrow one this class is empty by construction.
    frame = _frame(snapshot)
    at_locus = frame.filter(
        (pl.col("chrom") == locus["chrom"]) & (pl.col("start") == locus["start"])
    )
    expected_refuting = set(
        at_locus.filter(pl.col("evidence_direction_raw") == CIVIC_REFUTES)["evidence_id"]
        .cast(pl.Utf8)
        .to_list()
    )
    assert {ref.evidence_id for ref in finding.refuting} == expected_refuting
    assert finding.supporting, "the claim side must be quoted too, or the pair is not legible"
    assert finding.status_basis == json.loads(
        (snapshot / RELEASE_FILENAME).read_text(encoding="utf-8")
    )["status_basis"]
    assert finding.status_basis in finding.restate()


def test_a_row_that_claims_nothing_on_this_axis_is_not_a_subject(snapshot):
    """No authored `direction`, no claim for a refutation to sit beside. Not a finding, not a subject.

    The distinction is the point: `subjects=0` and `findings=0` say the module put no claim on this
    axis, where `subjects=1, findings=0` would say it did and the source did not rebut it.
    """
    locus = _refuted_locus(snapshot)
    variant, resolution = _authored(locus, direction=None)

    comparison = compare_refutations([variant], [resolution], reference=snapshot)

    assert comparison is not None
    assert comparison.subjects == 0 and comparison.findings == []


def test_a_refutation_with_no_claim_beside_it_is_the_other_code(snapshot, tmp_path):
    """CHEK2 788's shape: the source has only ever rebutted, and the module asserts a sign anyway.

    A different sentence with a different subject — author-versus-refutation rather than
    source-versus-itself — so a different code. One count over both would mix the two, and an author
    reading "3 findings" could not tell which of the two things happened.
    """
    locus = _refuted_locus(snapshot)
    frame = _frame(snapshot)
    # Drop the supporting rows at that locus. Every remaining row is upstream bytes.
    claimless = frame.filter(
        ~(
            (pl.col("chrom") == locus["chrom"])
            & (pl.col("start") == locus["start"])
            & pl.col("direction").is_not_null()
        )
    )
    reference = _rewrite(snapshot, claimless, tmp_path / "claimless")
    variant, resolution = _authored(locus, direction="risk")

    comparison = compare_refutations([variant], [resolution], reference=reference)

    assert [f.code for f in comparison.findings] == [REFUTATION_WITHOUT_CLAIM]
    assert comparison.findings[0].supporting == ()
    assert "only ever denied" in comparison.findings[0].restate()


def test_one_refutation_over_two_variants_is_one_finding(snapshot, tmp_path):
    """EID 8721's shape: one statement about a two-variant genotype, written as two rows.

    The snapshot cannot say so — `_submitted_evidence_row` stamps the variant's own profile over the
    evidence item's (RM174) — so the check must not read it as two independent rebuttals. Keying the
    finding on the refuting evidence id makes it one finding with two subjects, which stays true
    whichever way RM174 is repaired.
    """
    locus = _refuted_locus(snapshot)
    frame = _frame(snapshot)
    at_locus = frame.filter(
        (pl.col("chrom") == locus["chrom"]) & (pl.col("start") == locus["start"])
    )
    # The same evidence ids, fanned onto a second locus — exactly what the builder does today for a
    # combination profile, and the reason the parquet cannot distinguish the two cases itself.
    second = at_locus.with_columns(
        pl.col("start") + 1000,
        pl.lit(locus["variant_id"] + 1, dtype=pl.Int64).alias("variant_id"),
        pl.lit("SECOND VARIANT OF THE COMBINATION").alias("variant_name"),
    )
    reference = _rewrite(snapshot, pl.concat([frame, second]), tmp_path / "combination")

    first_variant, first_resolution = _authored(locus, direction="risk")
    other = dict(locus, start=locus["start"] + 1000)
    second_variant, second_resolution = _authored(other, direction="risk")

    comparison = compare_refutations(
        [first_variant, second_variant], [first_resolution, second_resolution], reference=reference
    )

    assert comparison.subjects == 2
    assert len(comparison.findings) == 1, "one statement is one finding, however many rows carry it"
    finding = comparison.findings[0]
    assert finding.combination and len(finding.subjects) == 2
    assert "combination genotype" in finding.restate()


def test_no_snapshot_is_not_a_pass(snapshot):
    """A check that could not run is not a check that found nothing (`@unreachable-not-absent`)."""
    locus = _refuted_locus(snapshot)
    variant, resolution = _authored(locus, direction="risk")

    assert compare_refutations([variant], [resolution], reference=None) is None


def test_an_unreadable_snapshot_is_not_a_pass_either(tmp_path):
    """A located-but-empty snapshot degrades the same way, rather than reporting a clean run."""
    empty = tmp_path / "empty"
    (empty / SNAPSHOT_DATA_DIRNAME).mkdir(parents=True)

    assert compare_refutations([], [], reference=empty) is None


def test_an_authored_row_the_snapshot_does_not_carry_is_counted_apart(snapshot):
    """Asked and unanswerable is not asked and answered — the count that would otherwise vanish."""
    absent = VariantRow(
        variant_key="1:1000:A:G", chrom="1", start=1000, ref="A", genotype="GG", state="risk",
        direction="risk", conclusion="not in the snapshot"
    )
    resolution = ResolutionRow(
        variant_key=absent.variant_key, chrom="1", start=1000, ref="A", alts="G", status="resolved"
    )

    comparison = compare_refutations([absent], [resolution], reference=snapshot)

    assert comparison.subjects == 0 and comparison.unmatched == 1


# ── the record, which is what a hand-author who never drafted ever sees ─────────────────────────────


def test_the_record_names_its_basis_even_when_it_found_nothing(snapshot):
    """`findings: 0` is only honest beside the basis it looked on.

    On the `accepted` basis this class is empty **by construction** — every refutation in CIViC that
    stands against a claim is submitted content — so a bare zero would read as clear water when what
    happened was a look in the half where it cannot appear.
    """
    from just_dna_enricher.enrich import _refutation_detail

    assert "basis accepted" in _refutation_detail([], "accepted")
    assert "no authored direction" in _refutation_detail([], "accepted")
    assert "basis unstated" in _refutation_detail([], None)


def test_the_record_groups_the_two_codes_rather_than_summing_them(snapshot, tmp_path):
    """Two sentences, two counts. A total would tell an author nothing about what to read."""
    from just_dna_enricher.enrich import _refutation_detail

    locus = _refuted_locus(snapshot)
    variant, resolution = _authored(locus, direction="risk")
    comparison = compare_refutations([variant], [resolution], reference=snapshot)

    detail = _refutation_detail(comparison.findings, comparison.status_basis)
    assert f"1 {REFUTATION_BESIDE_CLAIM}" in detail
    assert REFUTATION_WITHOUT_CLAIM not in detail, "a class with nothing in it says nothing"
    assert variant.variant_key in detail, "a count with no names is not actionable (S70)"


def test_the_drafter_names_the_variant_it_wrote_a_refuted_direction_for(snapshot, tmp_path):
    """Stage 2: the row IS written, and the author is told the same snapshot also rebuts it.

    The pre-existing line counted refuting rows the drafter withheld — a different fact, and one that
    never mentioned the rows it went on to write. A `risk` row over one of these could be authored
    with every gate green, which is the whole of RM170.
    """
    from just_dna_enricher.civic_draft import draft_panel_from_civic

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "name: refuted\nversion: 1\nformat_version: 0.7\ngenome_build: GRCh38\n", encoding="utf-8"
    )
    locus = _refuted_locus(snapshot)

    result = draft_panel_from_civic(spec, genes=[locus["gene"]], snapshot=snapshot, offline=True)

    assert result.refuted_beside_claim, "the slice's refuted variant must reach the report"
    named = {name for name, _supporting, _refuting in result.refuted_beside_claim}
    assert locus["variant_name"] in named
    line = next(w for w in result.warnings if "also REFUTES" in w)
    assert locus["variant_name"] in line and "EID" in line
    assert result.refutation_basis and result.refutation_basis in line
