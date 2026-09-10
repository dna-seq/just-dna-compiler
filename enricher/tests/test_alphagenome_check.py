"""RM193: the Atlas as a resolver — three states, an offline scope, and a refusal.

The pass is mostly offline. What it asks the network is decided from 466 KB of knots **before any
request is spent**, and the tests below are built around that: a fake stub supplies each arm of the
error contract, and the local half runs against a real snapshot built from the committed slice.
"""

import json
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import alphagenome_avi_build as ab
from just_dna_enricher import alphagenome_check as ac
from just_dna_enricher.atlas_client import (
    AtlasNotScored,
    AtlasRefMismatch,
    AtlasRefused,
    AtlasUnavailable,
)
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.verification import read_verification

_ROOT = Path(__file__).resolve().parents[2]
_SLICE = _ROOT / "assets" / "alphagenome" / "avi_chr22_slice.tsv.gz"
_TERMS = _ROOT / "docs" / "vendor" / "alphagenome_output_terms.txt"

#: The straddling knot, and the one threshold in the genome it makes undecidable.
STRADDLED_THRESHOLD = 3.0

pytestmark = pytest.mark.skipif(not _SLICE.is_file(), reason="the committed AVI slice is missing")


def _tabix() -> bool:
    try:
        subprocess.run(["tabix", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):  # pragma: no cover
        return False
    return True


needs_tabix = pytest.mark.skipif(not _tabix(), reason="tabix is not on PATH")


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory) -> Path:
    if not _tabix():  # pragma: no cover
        pytest.skip("tabix is not on PATH")
    out = tmp_path_factory.mktemp("avi_snapshot")
    ab.build_snapshot(_SLICE, out, workers=1, hash_source=False, terms_file=_TERMS)
    return out


def _rows_at(snapshot: Path, *, straddling: bool) -> list[dict]:
    """Real rows from the built snapshot, on or off the one straddling knot.

    Read out of the artifact rather than hardcoded, so the fixture and the module under test cannot
    drift apart silently — and so a re-cut slice fails loudly instead of testing nothing.
    """
    data = ab.to_long(pl.read_parquet(snapshot / "data" / "alphagenome_avi-chr22.parquet"))
    knots = pl.read_parquet(snapshot / ab.KNOT_FILENAME)
    spans = (pl.col("phred_lo") < STRADDLED_THRESHOLD) & (pl.col("phred_hi") > STRADDLED_THRESHOLD)
    keys = knots.filter(spans if straddling else ~spans)["raw_score_e5"]
    picked = data.filter(pl.col("raw_score_e5").is_in(keys.implode())).head(5)
    return picked.with_columns(
        pl.col("chrom").cast(pl.String), pl.col("ref").cast(pl.String), pl.col("alt").cast(pl.String)
    ).to_dicts()


def _module(tmp_path: Path, rows: list[dict], name: str = "m") -> Path:
    """A minimal spec directory carrying just the variants under test."""
    spec = tmp_path / name
    spec.mkdir(parents=True, exist_ok=True)
    # The columns `VariantRow` actually requires, taken from the model rather than guessed: a
    # genotype and a state are not optional, and the genotype's alleles must be alphabetically
    # sorted when unphased. Sorted here rather than written `ref/alt`, because the model refuses the
    # other order — which is the model being right about a real convention, not the fixture being
    # awkward.
    lines = ["chrom,start,ref,alts,genotype,state,conclusion,gene"]
    for i, row in enumerate(rows):
        lines.append(
            f"{row['chrom']},{row['pos']},{row['ref']},{row['alt']},"
            f"{'/'.join(sorted((row['ref'], row['alt'])))},risk,"
            f"a test row for the AlphaGenome variant-impact check,GENE{i}"
        )
    (spec / "variants.csv").write_text("\n".join(lines) + "\n")
    return spec


class _Stub:
    """An Atlas that answers however the test needs it to, one canned reply per call."""

    def __init__(self, *replies):
        self._replies = list(replies)
        self.calls: list[tuple] = []

    def score_variant(self, chrom, position, ref, alt, *, scorers=()):
        self.calls.append((chrom, position, ref, alt))
        reply = self._replies.pop(0) if self._replies else []
        if isinstance(reply, Exception):
            raise reply
        return reply


class _Block:
    def __init__(self, phred: float | None, scorer: str = ac.AVI_SCORER):
        self.scorer, self.phred = scorer, phred


# ── the offline half ─────────────────────────────────────────────────────────────────────────────


@needs_tabix
def test_a_module_with_no_variants_asks_nothing_and_attests_nothing(tmp_path: Path) -> None:
    """The check does not *apply*, which is not the same as passing.

    Attesting here would mine a nonce and publish a `manifest.verification` block about a question
    the module never posed — the rule `check_repeat_bands` and `enrich_pgx` already follow.
    """
    spec = tmp_path / "empty"
    spec.mkdir()
    result = ac.check_variant_impact(spec, reference=None)
    assert result.subjects == 0 and not result.findings
    assert not (spec / VERIFICATION_JSON).exists()


@needs_tabix
def test_without_a_threshold_the_pass_never_reaches_the_network(
    snapshot: Path, tmp_path: Path
) -> None:
    """No threshold means no question the local artifact cannot answer, so no request is made.

    Asserted on the stub's call log rather than on a mock's `assert_not_called`, because what is
    being pinned is that the *scope* is empty, not that a particular method was skipped.
    """
    rows = _rows_at(snapshot, straddling=False)
    spec = _module(tmp_path, rows)
    stub = _Stub()

    result = ac.check_variant_impact(spec, reference=snapshot, client=stub)

    assert stub.calls == []
    assert len(result.decided) == len(rows)
    assert not result.straddling and not result.unanswered


@needs_tabix
def test_the_straddling_scope_is_computed_from_the_knots_before_any_request(
    snapshot: Path, tmp_path: Path
) -> None:
    """The candidate set comes out of 466 KB, offline. That is what makes the refusal decidable.

    Both directions: a variant on the one straddling knot is in scope at 3.0, and the same variant
    is out of scope at a threshold no knot spans — so the scope tracks the *threshold*, not the row.
    """
    straddling = _rows_at(snapshot, straddling=True)
    assert straddling, "the fixture no longer carries the straddling knot"
    spec = _module(tmp_path, straddling)

    in_scope = ac.check_variant_impact(
        spec, reference=snapshot, client=_Stub(*[[] for _ in straddling]),
        threshold=STRADDLED_THRESHOLD,
    )
    assert len(in_scope.straddling) == len(straddling)

    out_of_scope = ac.check_variant_impact(
        spec, reference=snapshot, client=_Stub(), threshold=20.0
    )
    assert out_of_scope.straddling == []


@needs_tabix
def test_threshold_safety_is_answerable_from_the_knot_table_alone(snapshot: Path) -> None:
    """The question a caller should ask first, and it costs no network and no data read.

    Genome-wide the answer is "safe" at every integer threshold from 1 to 50 except 3. On this slice
    the same holds, which is the property the artifact publishes the interval for.
    """
    safe, affected = ac.threshold_is_safe(snapshot, STRADDLED_THRESHOLD)
    assert safe is False and affected > 0

    for threshold in (1.0, 2.0, 4.0, 5.0, 10.0, 20.0, 50.0):
        safe, affected = ac.threshold_is_safe(snapshot, threshold)
        assert safe is True and affected == 0, threshold


def test_a_score_converts_to_the_integer_domain_rather_than_being_divided_back() -> None:
    """The helper exists because the obvious alternative is measurably wrong on 53% of rows."""
    assert ac.score_to_threshold(0.1) == 10_000
    assert ac.score_to_threshold(-0.03868) == -3868
    assert ac.score_to_threshold(0.00076) == 76


# ── the refusal ──────────────────────────────────────────────────────────────────────────────────


@needs_tabix
def test_an_unbounded_refinement_is_refused_and_names_the_cheaper_answer(
    snapshot: Path, tmp_path: Path
) -> None:
    """Rebuilding the column by RPC is 272 days; a check that could start down that road must refuse.

    The refusal fires **before any request**, and it names the knot table — because the thing the
    caller actually wants (which rows are affected, and by how much) is already on their disk.
    """
    straddling = _rows_at(snapshot, straddling=True)
    spec = _module(tmp_path, straddling)
    stub = _Stub()

    with pytest.raises(ac.VariantImpactError, match="over the cap"):
        ac.check_variant_impact(
            spec, reference=snapshot, client=stub,
            threshold=STRADDLED_THRESHOLD, refinement_cap=1,
        )
    assert stub.calls == [], "the refusal must cost nothing"


@needs_tabix
def test_a_missing_knot_table_is_refused_rather_than_read_around(
    snapshot: Path, tmp_path: Path
) -> None:
    """The curve and the scores are two halves of one artifact.

    Without the knots a `PHRED` cannot be reconstructed at all, so a snapshot that lost them can
    still answer "what is the raw score" and can no longer answer any question this pass exists for.
    Refused with that named, rather than degrading to a threshold check on the raw value.
    """
    import shutil

    crippled = tmp_path / "no_knots"
    shutil.copytree(snapshot, crippled)
    (crippled / ab.KNOT_FILENAME).unlink()
    spec = _module(tmp_path, _rows_at(snapshot, straddling=False))

    with pytest.raises(ac.VariantImpactError, match="two halves"):
        ac.check_variant_impact(spec, reference=crippled)


# ── the three states ─────────────────────────────────────────────────────────────────────────────


@needs_tabix
def test_offline_is_nobody_asked_and_not_a_decision(snapshot: Path, tmp_path: Path) -> None:
    """`--offline` must record the third state, not a silent skip and never a zero.

    Nobody-asked, asked-and-absent and scored-zero are three different things
    (`@unreachable-not-absent`), and this is the one that is easiest to lose — the run completes,
    the rows look handled, and nothing says they were never put to the service.
    """
    straddling = _rows_at(snapshot, straddling=True)
    spec = _module(tmp_path, straddling)

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=_Stub(), threshold=STRADDLED_THRESHOLD, offline=True
    )

    reasons = {reason for _, reason in result.unanswered}
    assert reasons == {"offline"}
    assert len(result.unanswered) == len(straddling)
    assert result.refined == []

    record = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[ac.CHECK]
    assert record.skipped == "offline", "the attestation has to carry the reason, not just the fact"


@needs_tabix
def test_an_indel_is_recorded_as_no_answer_rather_than_a_low_score(
    snapshot: Path, tmp_path: Path
) -> None:
    """`UNIMPLEMENTED` is the third state: the request was legal and the answer does not exist.

    A caller that stored zero here would be asserting AlphaGenome scored the variant as harmless,
    which it never claimed. The finding says so in as many words.
    """
    straddling = _rows_at(snapshot, straddling=True)[:1]
    spec = _module(tmp_path, straddling)
    stub = _Stub(AtlasNotScored("chr22:1 AC>A is not in the precomputed Atlas (indels are not scored)"))

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=stub, threshold=STRADDLED_THRESHOLD
    )

    assert [reason for _, reason in result.unanswered] == ["not_scored"]
    assert result.refined == []
    (finding,) = result.findings
    assert finding.kind == "not_scored"
    assert "Not a zero" in finding.detail


@needs_tabix
def test_a_ref_mismatch_becomes_a_finding_carrying_the_base_the_server_named(
    snapshot: Path, tmp_path: Path
) -> None:
    """The one finding a local lookup provably cannot produce.

    A file lookup on a wrong `REF` simply misses, and a miss is indistinguishable from an unscored
    position — `@va-omits-ref` says a VA does not encode `ref`, so only something holding the
    assembly can tell the caller what is really there. The Atlas does, and the base survives into
    the finding rather than being reduced to "mismatch".
    """
    straddling = _rows_at(snapshot, straddling=True)[:1]
    spec = _module(tmp_path, straddling)
    stub = _Stub(
        AtlasRefMismatch(
            "chr22:36200000 A>T: Variant: chr22:36200000:A>T reference base does not match the "
            "expected reference base: G."
        )
    )

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=stub, threshold=STRADDLED_THRESHOLD
    )

    (finding,) = result.findings
    assert finding.kind == "ref_mismatch"
    assert finding.observed_ref == "G", "the server named the base and the finding must carry it"
    assert "G" in str(finding)
    assert [reason for _, reason in result.unanswered] == ["ref_mismatch"]


@needs_tabix
def test_an_unreachable_service_is_neither_a_finding_nor_an_answer(
    snapshot: Path, tmp_path: Path
) -> None:
    """A transport failure says nothing about the variant, so it produces no finding at all.

    This is the arm most likely to be collapsed into the others, and it is the one that must not be:
    a finding here would put a claim about the caller's data on the record because Google had a bad
    minute.
    """
    straddling = _rows_at(snapshot, straddling=True)[:1]
    spec = _module(tmp_path, straddling)
    stub = _Stub(AtlasUnavailable("UNAVAILABLE: connection refused"))

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=stub, threshold=STRADDLED_THRESHOLD
    )

    assert result.findings == []
    assert [reason for _, reason in result.unanswered] == ["unreachable"]


@needs_tabix
def test_the_four_no_answer_reasons_stay_apart(snapshot: Path, tmp_path: Path) -> None:
    """Four histories, four remedies, and a verdict function owes a reason function with four arms.

    `@answered-is-not-absent`: collapsing any two of these into "unknown" would leave a reader unable
    to tell "fix your REF" from "retry later" from "there is no such score" from "you never asked".
    """
    straddling = _rows_at(snapshot, straddling=True)
    assert len(straddling) >= 4, "this test needs four straddling rows to hand the stub"
    spec = _module(tmp_path, straddling[:4])
    stub = _Stub(
        AtlasRefMismatch("x: reference base does not match the expected reference base: G."),
        AtlasNotScored("x: indels are not scored"),
        AtlasUnavailable("x: UNAVAILABLE"),
        AtlasRefused("x: PERMISSION_DENIED: bad key"),
    )

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=stub, threshold=STRADDLED_THRESHOLD
    )

    assert sorted(reason for _, reason in result.unanswered) == [
        "not_scored", "ref_mismatch", "refused", "unreachable",
    ]


@needs_tabix
def test_a_refined_answer_is_recorded_as_refined_rather_than_as_locally_decided(
    snapshot: Path, tmp_path: Path
) -> None:
    """The denominator has to say which rows the network settled, or the attestation overstates it."""
    straddling = _rows_at(snapshot, straddling=True)[:1]
    spec = _module(tmp_path, straddling)
    stub = _Stub([_Block(3.00019)])

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=stub, threshold=STRADDLED_THRESHOLD
    )

    assert len(result.refined) == 1
    assert result.unanswered == []
    record = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[ac.CHECK]
    assert record.subjects == result.subjects


@needs_tabix
def test_a_saturated_quantile_is_no_answer_rather_than_a_ceiling(
    snapshot: Path, tmp_path: Path
) -> None:
    """Where the API runs out before the data does, the file is the better source and unknown is honest.

    `calibrated_scores` is a `float32`, capping a derived `PHRED` at 72.247 while the published
    artifact reaches 89.451 — about 1,300 rows genome-wide, and they are the highest-impact ones. A
    clamped 72.247 would be a number the service never reported.
    """
    straddling = _rows_at(snapshot, straddling=True)[:1]
    spec = _module(tmp_path, straddling)
    stub = _Stub([_Block(None)])  # `VariantScore.phred` withholds on saturation

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=stub, threshold=STRADDLED_THRESHOLD
    )

    assert result.refined == []
    assert [reason for _, reason in result.unanswered] == ["not_scored"]


@needs_tabix
def test_a_variant_the_snapshot_does_not_carry_is_its_own_reason(
    snapshot: Path, tmp_path: Path
) -> None:
    """Absent from the artifact is not "not scored" and is certainly not zero.

    AVI covers ~95% of the assembly. A position outside the snapshot may be uncovered, may be an
    indel, or may simply be on a contig this build did not include — and only the Atlas can tell
    those apart, which is why the local pass records the absence under its own name.
    """
    spec = _module(tmp_path, [{"chrom": "chr22", "pos": 1, "ref": "A", "alt": "T"}])
    result = ac.check_variant_impact(spec, reference=snapshot)

    assert result.decided == []
    assert [reason for _, reason in result.unanswered] == ["absent_from_snapshot"]


# ── the dependency floor ─────────────────────────────────────────────────────────────────────────


def test_the_offline_half_runs_without_the_atlas_extra() -> None:
    """`grpcio` must not become a requirement of the whole CLI by the back door.

    A subprocess with `grpc` blocked at import, because in *this* environment the extra is installed
    and any in-process check would pass for the wrong reason — the same trap
    `test_imports_stay_within_the_declared_floor` avoids with an AST walk. What is asserted is the
    property that matters: the CLI imports, the check module imports, and the offline path is
    reachable with no client available.
    """
    program = (
        "import sys\n"
        "class Block:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'grpc' or name.startswith('grpc.'):\n"
        "            raise ImportError('grpc is blocked for this test')\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        return self.find_module(name, path)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import just_dna_enricher.cli\n"
        "from just_dna_enricher import alphagenome_check as ac\n"
        "assert ac.ATLAS_CLIENT_AVAILABLE is False\n"
        "assert ac.score_to_threshold(0.1) == 10000\n"
        "print('ok')\n"
    )
    proc = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


@needs_tabix
def test_the_check_names_its_own_member_rather_than_reusing_reference_allele(
    snapshot: Path, tmp_path: Path
) -> None:
    """Two registries answering an overlapping question get two checks.

    The Atlas validates `REF` too, but `reference_allele` belongs to `enrich` and compares against
    the reference *sequence*. Emitting it from here would let an Atlas outage write a skip against a
    question a different source answers — `@one-registrys-outage-may-not-speak-for-another`, which
    is exactly the defect that rule was written for.
    """
    from just_dna_format.vocab import VALID_VERIFICATION_CHECKS

    assert ac.CHECK in VALID_VERIFICATION_CHECKS
    assert ac.CHECK != "reference_allele"

    spec = _module(tmp_path, _rows_at(snapshot, straddling=False))
    ac.check_variant_impact(spec, reference=snapshot)
    written = {r.check for r in read_verification(spec / VERIFICATION_JSON).records}
    assert written == {ac.CHECK}, "this pass must attest its own check and nobody else's"


@needs_tabix
def test_an_absent_snapshot_is_a_skip_with_a_reason_not_an_empty_result(tmp_path: Path) -> None:
    """Nobody-asked again, one level up: no snapshot means the question was never put.

    The reason has to reach the attestation, because "no rows disagreed" and "there was nothing to
    disagree with" are the same empty result and opposite facts.
    """
    spec = _module(tmp_path, [{"chrom": "chr22", "pos": 20000000, "ref": "G", "alt": "A"}])
    result = ac.check_variant_impact(spec, reference=None)

    assert result.warnings and "never fetched" in result.warnings[0]
    record = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[ac.CHECK]
    assert record.skipped == "no_reference"
    assert json.loads((spec / VERIFICATION_JSON).read_text())["records"]


@needs_tabix
def test_the_two_contig_spellings_are_reconciled_at_the_boundary(
    snapshot: Path, tmp_path: Path
) -> None:
    """`22` and `chr22` are the same contig, and getting this wrong is silent rather than loud.

    `VariantRow` normalizes through `vrs.normalize_chrom` and stores `22`; AlphaGenome ships
    UCSC-style `chr22` and indexes it that way. Joining one onto the other matches **nothing** — and
    the result is not an error, it is every variant reported as `absent_from_snapshot`, which reads
    exactly like an artifact that does not cover them. It was a real defect here, found only because
    a test asserted a positive count rather than the absence of a crash.

    Both spellings, one answer, asserted as equality between the two runs rather than as "neither is
    empty": a conversion applied twice, or in the wrong direction, would leave one of them empty and
    a floor would not see it.
    """
    rows = _rows_at(snapshot, straddling=False)
    plain = _module(tmp_path, [{**row, "chrom": row["chrom"].removeprefix("chr")} for row in rows], name="plain")
    prefixed = _module(tmp_path, rows, name="prefixed")

    a = ac.check_variant_impact(plain, reference=snapshot)
    b = ac.check_variant_impact(prefixed, reference=snapshot)

    assert len(a.decided) == len(rows), "the module's own spelling must reach the snapshot"
    assert len(a.decided) == len(b.decided)
    assert a.unanswered == b.unanswered == []
    assert ac.artifact_contig("22") == ac.artifact_contig("chr22") == "chr22"


@needs_tabix
def test_the_denominator_counts_variants_and_not_verdicts(snapshot: Path, tmp_path: Path) -> None:
    """A variant the snapshot decided AND the threshold left unresolved is one subject, not two.

    Found on the real artifact: a three-variant module reported four subjects, because a straddling
    row is legitimately in `decided` (the snapshot has a score for it) and in `unanswered` (the
    threshold falls inside its knot and nothing refined it). An attestation whose denominator
    exceeds the rows it ran over reads as coverage nobody had, which is the opposite of what the
    record is for.
    """
    straddling = _rows_at(snapshot, straddling=True)[:2]
    spec = _module(tmp_path, straddling)

    result = ac.check_variant_impact(
        spec, reference=snapshot, client=_Stub(), threshold=STRADDLED_THRESHOLD, offline=True
    )

    assert len(result.decided) == len(straddling), "the snapshot really did decide these"
    assert len(result.unanswered) == len(straddling), "and the threshold really did unresolve them"
    assert result.subjects == len(straddling), "but there are only this many variants"

    record = {r.check: r for r in read_verification(spec / VERIFICATION_JSON).records}[ac.CHECK]
    assert record.skipped == "offline"
