"""The Atlas client's contract — the dependency floor, the decode, and the three refusals (RM192).

Moved into the suite from `docs/probes/alphagenome_poc/`, where it was written to make one claim
falsifiable before anything was adopted: **the Atlas is reachable without the `alphagenome` wheel**.
`test_imports_stay_within_the_declared_floor` is the test that actually pins it; the rest keep the
decode and the error contract honest.

Most of it is offline. The live tests need `ALPHAGENOME_API_KEY` **and** the repo's opt-in network
switch, `JUST_DNA_NETWORK_TESTS=1` (`@network-tests-optin`), and they are the only ones that touch
Google's service.

The bindings are a build product: `generated/` is git-ignored, so this module generates them on
first run if they are absent, exactly as a developer would. That needs `grpcio-tools`, which is in
the `[dev]` group.
"""

import ast
import math
import os
import struct
import sys
from pathlib import Path

import just_dna_enricher
import pytest
from just_dna_enricher import atlas_protos

#: The tests read the client's own source for the AST walk, so they need where it lives — asked of
#: the package rather than composed from this file's location, which would break if either moved.
CLIENT_SOURCE = Path(just_dna_enricher.__file__).resolve().parent / "atlas_client.py"

pytest.importorskip("grpc", reason="the [atlas] extra is what makes the Atlas reachable")
import grpc  # noqa: E402

if not (atlas_protos.OUT_DIR / atlas_protos.STAGE_PREFIX).exists():  # pragma: no cover - first run
    pytest.importorskip("grpc_tools", reason="run `just-dna-enricher atlas generate`, or install grpcio-tools")
    atlas_protos.generate()

from just_dna_enricher import atlas_client as ac  # noqa: E402
from just_dna_enricher.generated._alphagenome_atlas_protos import (  # noqa: E402
    atlas_service_pb2,
    dna_model_pb2,
)

NETWORK = os.environ.get("JUST_DNA_NETWORK_TESTS") == "1"
API_KEY = os.environ.get("ALPHAGENOME_API_KEY") or ""
live = pytest.mark.skipif(
    not (NETWORK and API_KEY),
    reason="set JUST_DNA_NETWORK_TESTS=1 and ALPHAGENOME_API_KEY to run the live leg",
)

# Two rows read from the published AVI artifact,
# `alphagenome_variant_impact_score_snvs.tsv.gz` (2026-08-27). Domain constants, not counts read
# off a dump — they are what the file says, and the point of quoting them is that the API and the
# download must agree.
BULK_AVI = {
    ("chr1", 10001, "T", "A"): (-0.03868, 1.06466),
    ("chr1", 10001, "T", "C"): (-0.03200, 1.31140),
}


# ── the dependency claim ────────────────────────────────────────────────────────────────────────


def test_imports_stay_within_the_declared_floor():
    """The client must import nothing beyond the standard library, `grpc`, and the generated protos.

    An AST walk rather than a runtime check on `sys.modules`, because by the time the module is
    imported a heavier package pulled in by some other test would already be resident and the
    assertion would pass for the wrong reason. This is the test that makes "22 MB, not 255 MB" a
    property of the code instead of a claim in prose.
    """
    tree = ast.parse(CLIENT_SOURCE.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    third_party = roots - set(sys.stdlib_module_names)
    assert third_party == {"grpc", "just_dna_enricher"}, (
        f"the Atlas client's dependency floor moved: {sorted(third_party)}. "
        "`just_dna_enricher` is this package (the generated protos and the generator); anything "
        "else is a new runtime dependency and moves the [atlas] extra off two packages."
    )


def test_the_vendored_protos_are_exactly_what_the_atlas_surface_needs():
    """Three of upstream's four, and the fourth is absent rather than unused.

    Equality over the walked directory, not a floor: a vendored file nobody needs is a file nobody
    re-vendors when it changes, and one that is needed but missing fails the build far from here.
    """
    vendored = {p.name for p in atlas_protos.PROTO_DIR.glob("*.proto")}
    assert vendored == set(atlas_protos.PROTOS), vendored
    assert "dna_model_service.proto" not in vendored, "that one drives the model service, not Atlas"


def test_the_generated_bindings_do_not_shadow_the_upstream_package():
    """The staged prefix must not be `alphagenome`, or having both installed breaks one of them.

    protoc bakes the staged path into every cross-import, so this is decided at generation time and
    is invisible until someone installs the real wheel alongside. Pinned here rather than left as a
    comment.
    """
    assert atlas_protos.STAGE_PREFIX != "alphagenome"
    assert not (atlas_protos.OUT_DIR / "alphagenome").exists()
    binding = (atlas_protos.OUT_DIR / atlas_protos.STAGE_PREFIX / "atlas_service_pb2.py").read_text()
    assert "from alphagenome.protos import" not in binding
    # The cross-import is fully qualified from `enricher/src`, which is both why it cannot shadow
    # the wheel and why the client imports it without touching `sys.path`.
    assert "from just_dna_enricher.generated._alphagenome_atlas_protos import" in binding


def test_the_vendored_sources_are_byte_identical_to_what_protoc_was_given_minus_the_prefix():
    """The rewrite happens on the staged copy; the committed `.proto` keeps upstream's own text.

    That asymmetry is what makes re-vendoring a newer release a diff rather than a merge, so it is
    worth a test rather than a promise in a docstring.
    """
    for name in atlas_protos.PROTOS:
        committed = (atlas_protos.PROTO_DIR / name).read_text()
        staged = (atlas_protos.OUT_DIR / atlas_protos.STAGE_PREFIX / name).read_text()
        assert staged == committed.replace(
            'import "alphagenome/protos/',
            'import "just_dna_enricher/generated/_alphagenome_atlas_protos/',
        )
        assert 'package google.gdm.gdmscience.alphagenome' in staged, (
            "the protobuf package must not move — descriptor names are the wire format"
        )


def test_bindings_regenerate_from_the_vendored_sources(tmp_path):
    """The committed `.proto` files, not a wheel, are what the bindings come from.

    Regenerating into a scratch directory proves the repository carries a reproducible input —
    which is the difference between vendoring sources and vendoring generated code.
    """
    pytest.importorskip("grpc_tools")
    out = atlas_protos.generate(tmp_path / "generated", include_root=tmp_path)
    produced = {p.name for p in (out / atlas_protos.STAGE_PREFIX).glob("*_pb2*.py")}
    expected = {
        f"{stem}_pb2{suffix}.py"
        for stem in ("atlas_service", "dna_model", "tensor")
        for suffix in ("", "_grpc")
    }
    assert produced == expected, produced


# ── decode and the Phred transform ──────────────────────────────────────────────────────────────


def test_unpack_float32_round_trips_and_distinguishes_absent_from_empty():
    values = (-0.03868196, 0.21739846, 5.799)
    packed = struct.pack(f"<{len(values)}f", *values)
    decoded = ac.unpack_float32(packed)
    assert decoded is not None
    assert all(math.isclose(a, b, rel_tol=1e-6) for a, b in zip(decoded, values, strict=True))
    # An absent field is `None`, never `()` — the tri-state rule at the smallest possible scale.
    assert ac.unpack_float32(b"") is None
    with pytest.raises(ac.AtlasError):
        ac.unpack_float32(b"\x00\x00\x00")


@pytest.mark.parametrize(("key", "expected"), sorted(BULK_AVI.items()))
def test_phred_transform_reproduces_the_published_column(key, expected):
    """`PHRED = -10 log10(1 - quantile)` against the bytes the download actually contains.

    The quantile is recomputed from the file's own Phred rather than hardcoded, so the test pins
    the *relationship* the two published columns stand in — which is the finding — instead of
    re-asserting a number copied from an API response.
    """
    _, phred = expected
    quantile = 1.0 - 10.0 ** (-phred / 10.0)
    assert ac.phred_from_quantile(quantile) == pytest.approx(phred, abs=1e-4)


def test_a_saturated_quantile_refuses_rather_than_inventing_a_ceiling():
    """The wire format runs out before the data does, and the client says so.

    An earlier version clamped at the FAQ's 0.999990 / Phred 50. The published AVI artifact reaches
    **89.451**, so that clamp would have rewritten real values as 50 — a bound taken from prose
    about a different scorer, silently applied to data that exceeds it. What actually bounds the
    API is `float32`: the largest representable quantile below 1.0 caps a derived Phred at 72.247,
    and above that the API returns exactly 1.0. That is unknown, not fifty.
    """
    assert ac.MAX_REPRESENTABLE_PHRED == pytest.approx(72.247, abs=1e-3)
    assert ac.phred_from_quantile(ac.MAX_FLOAT32_QUANTILE) == pytest.approx(
        ac.MAX_REPRESENTABLE_PHRED, abs=1e-6
    )
    assert ac.phred_from_quantile(0.0) == 0.0
    # Saturation is an absence of information, so it raises the "unknown" type, not ValueError.
    with pytest.raises(ac.AtlasNotScored):
        ac.phred_from_quantile(1.0)
    with pytest.raises(ValueError):
        ac.phred_from_quantile(1.5)
    # 50 must not be reachable as a magic clamp any more.
    assert ac.phred_from_quantile(0.99999) == pytest.approx(50.0, abs=1e-6), (
        "0.99999 really is Phred 50 — the point is that nothing *above* it is also 50"
    )
    assert ac.phred_from_quantile(0.999999) == pytest.approx(60.0, abs=1e-6)


def test_the_property_withholds_where_the_function_refuses():
    """`VariantScore.phred` returns `None` on saturation instead of propagating the refusal.

    A verdict function with several arms owes a reason function with the same arms
    (`@answered-is-not-absent`): the property is the verdict and returns the third state, while
    `phred_from_quantile` is the reason and says why.
    """
    saturated = ac.VariantScore("AVI_SCORE", raw=(4.626,), quantile=(1.0,), shape=(1, 1))
    assert saturated.phred is None


def test_variant_score_withholds_phred_for_a_multi_valued_block():
    """367 splice-track values have no single Phred, and `None` says so rather than picking one."""
    scalar = ac.VariantScore("AVI_SCORE", raw=(-0.038,), quantile=(0.2174,), shape=(1, 1))
    assert scalar.phred == pytest.approx(1.0646, abs=1e-3)
    wide = ac.VariantScore("CHIP_TF", raw=(0.1, 0.2), quantile=(0.5, 0.6), shape=(1, 2))
    assert wide.phred is None
    unscored = ac.VariantScore("AVI_SCORE", raw=(-0.038,), quantile=None, shape=(1, 1))
    assert unscored.phred is None


def test_scorer_filter_builds_the_aip160_string():
    assert ac.scorer_filter() == ""
    assert ac.scorer_filter("AVI_SCORE") == 'scores.variant_scorer.name = "AVI_SCORE"'
    assert ac.scorer_filter("AVI_SCORE", "CHIP_TF") == (
        'scores.variant_scorer.name = "AVI_SCORE" OR scores.variant_scorer.name = "CHIP_TF"'
    )


# ── the error contract ──────────────────────────────────────────────────────────────────────────


class _RpcError(grpc.RpcError):
    def __init__(self, code, details):
        self._code, self._details = code, details

    def code(self):
        return self._code

    def details(self):
        return self._details


class _RaisingStub:
    def __init__(self, error):
        self._error = error

    def GetDenseVariantScores(self, request, metadata=None):  # noqa: N802 - the proto's name
        raise self._error

    def ListVariantScoresMetadata(self, request, metadata=None):  # noqa: N802
        raise self._error


@pytest.mark.parametrize(
    ("code", "details", "expected"),
    [
        (grpc.StatusCode.UNIMPLEMENTED, "Operation is not implemented", ac.AtlasNotScored),
        (
            grpc.StatusCode.INVALID_ARGUMENT,
            "reference base does not match the expected reference base: G.",
            ac.AtlasRefMismatch,
        ),
        (grpc.StatusCode.INVALID_ARGUMENT, "Request contains an invalid argument.", ac.AtlasRefused),
        (grpc.StatusCode.UNAVAILABLE, "connection refused", ac.AtlasUnavailable),
        (grpc.StatusCode.DEADLINE_EXCEEDED, "", ac.AtlasUnavailable),
        (grpc.StatusCode.RESOURCE_EXHAUSTED, "quota", ac.AtlasUnavailable),
        (grpc.StatusCode.PERMISSION_DENIED, "bad key", ac.AtlasRefused),
    ],
)
def test_every_transport_error_becomes_this_modules_contract(code, details, expected):
    """No `grpc.RpcError` reaches a caller, and each arm lands on the type its remedy needs.

    The three remedies are genuinely different — retry, fix the request, or accept that the answer
    does not exist — so collapsing them into one exception type would make the client's word
    useless (`@client-exception-contract`).
    """
    client = ac.AtlasClient(_RaisingStub(_RpcError(code, details)), api_key="x")
    with pytest.raises(expected) as caught:
        client.score_variant("chr1", 10001, "T", "A", scorers=("AVI_SCORE",))
    assert not isinstance(caught.value, grpc.RpcError)
    if details:
        assert details.split(":")[0][:20] in str(caught.value), "the server's own words are dropped"


def test_not_scored_is_not_a_refusal():
    """An indel is unknown, not rejected — the two must not share a handler.

    `AtlasNotScored` deriving from `AtlasRefused` would let `except AtlasRefused` swallow it, and a
    caller would then record "no score" for a variant the service never claimed to have scored.
    """
    assert not issubclass(ac.AtlasNotScored, ac.AtlasRefused)
    assert issubclass(ac.AtlasRefMismatch, ac.AtlasRefused)
    assert issubclass(ac.AtlasNotScored, ac.AtlasError)


def test_handler_order_is_not_load_bearing_by_accident():
    """`AtlasRefMismatch` is a subclass, so an `except` ladder that catches its parent first hides it.

    Enumerated here rather than left to a reviewer, because a subclass makes a caller's handler
    *order* load-bearing (`@client-exception-contract`), and this is the one place the shape is
    documented.
    """
    ladder = (ac.AtlasRefMismatch, ac.AtlasRefused, ac.AtlasNotScored, ac.AtlasUnavailable)
    for i, earlier in enumerate(ladder):
        for later in ladder[i + 1 :]:
            # A later arm that is a *subclass* of an earlier one can never be reached: the earlier
            # `except` swallows it. The reverse — an earlier arm being the subclass — is exactly
            # what a correct ladder looks like, which is why this is one-directional.
            assert not issubclass(later, earlier), (
                f"{later.__name__} is unreachable: {earlier.__name__} catches it first"
            )


# ── the live leg ────────────────────────────────────────────────────────────────────────────────


@live
def test_the_api_reproduces_the_downloaded_file():
    """The 88.5 GB artifact is the API's float32 printed to five decimals — the § 6.3 finding.

    If this ever fails, the two surfaces have diverged and every claim in § 6.4 about them being
    one source needs re-measuring.
    """
    client = ac.connect(API_KEY)
    for (chrom, pos, ref, alt), (raw, phred) in BULK_AVI.items():
        (block,) = client.score_variant(chrom, pos, ref, alt, scorers=("AVI_SCORE",))
        assert block.scorer == "AVI_SCORE"
        assert block.raw is not None and block.raw[0] == pytest.approx(raw, abs=5e-6)
        assert block.phred == pytest.approx(phred, abs=1e-4)


@live
def test_an_indel_is_unknown_and_a_wrong_ref_is_a_finding():
    """The two refusals that separate the Atlas from a local file lookup.

    A file simply misses on both; the service distinguishes "not scored" from "your REF is wrong"
    and names the real base for the second.
    """
    client = ac.connect(API_KEY)
    with pytest.raises(ac.AtlasNotScored):
        client.score_variant("chr22", 36201698, "AC", "A", scorers=("AVI_SCORE",))
    with pytest.raises(ac.AtlasRefMismatch, match="G"):
        client.score_variant("chr22", 36200000, "A", "T", scorers=("AVI_SCORE",))


@live
def test_the_api_saturates_where_the_download_still_has_a_value():
    """The one place the two surfaces are **not** one source — measured, not assumed.

    `chr22:30339156 C>A` is `PHRED 84.10132` in the published artifact. `calibrated_scores` is a
    float32, so the API returns exactly 1.0 and the rank is gone; `raw_score` still agrees. About
    1,300 rows genome-wide, and they are the highest-impact ones, which is why this is a test and
    not a footnote.
    """
    client = ac.connect(API_KEY)
    (block,) = client.score_variant("chr22", 30339156, "C", "A", scorers=("AVI_SCORE",))
    assert block.raw is not None and block.raw[0] == pytest.approx(4.626, abs=1e-3)
    assert block.quantile == (1.0,), "if this stops saturating, the wire format widened"
    assert block.phred is None, "a saturated quantile has no Phred to report"


@live
def test_the_scorer_roster_is_a_superset_of_what_is_downloadable():
    """Every published artifact corresponds to a scorer, and the roster carries more than three.

    Asserted as a subset relation rather than a count: a count would break on the next scorer they
    add, which is not a regression (`@registry-completeness` — equality over a walked set where one
    is owed, a relation where the roster is someone else's).
    """
    names = set(ac.connect(API_KEY).scorer_names())
    downloadable = {"AVI_SCORE", "AVI_SCORE_FEATURE_IMPORTANCE"}
    assert downloadable <= names
    assert {"CHIP_TF", "SPLICE_SITES", "SPLICE_SITE_USAGE", "SPLICE_JUNCTIONS"} <= names
    assert len(names) > len(downloadable), "the API would add nothing over the files"


# ── the interval RPC (RM194's blocker, cleared) ─────────────────────────────────────────────────


def test_the_interval_filter_builds_both_clauses_and_ands_them():
    """Scorers and genes are two ORs joined by an AND, and the parentheses matter.

    The filter is a *string*, so it is the one piece of an interval request a hand-built client has
    to know rather than derive from the protos — which makes it worth pinning here rather than
    discovering against the live service.
    """
    assert ac.interval_filter(scorers=("AVI_SCORE",)) == '(scores.variant_scorer.name = "AVI_SCORE")'
    assert ac.interval_filter(gene_names=("HFE",)) == (
        '(scores.metadata.gene_scorers.metadata.name = "HFE")'
    )
    both = ac.interval_filter(scorers=("RNA_SEQ",), gene_names=("HFE", "TFR2"))
    assert both == (
        '(scores.variant_scorer.name = "RNA_SEQ") AND '
        '(scores.metadata.gene_scorers.metadata.name = "HFE" OR '
        'scores.metadata.gene_scorers.metadata.name = "TFR2")'
    )
    assert ac.interval_filter() == ""


def test_an_unfiltered_interval_is_refused_before_it_is_sent():
    """Unfiltered is not slow, it fails — 43 MB for 32 bp against a 4 MB receive limit.

    Refused locally so the caller gets the knob to turn rather than a transport error about a
    message size, which is `RESOURCE_EXHAUSTED` and reads like a quota problem.
    """
    client = ac.AtlasClient(_RaisingStub(_RpcError(grpc.StatusCode.UNKNOWN, "")), api_key="x")
    with pytest.raises(ac.AtlasRefused, match="needs a filter"):
        client.score_interval("chr22", 20002001, 20002033)


def test_the_interval_carries_a_real_strand_member_rather_than_the_proto_default():
    """`Strand` has no zero member, and that single fact is what made this RPC look unreachable.

    `STRAND_UNSPECIFIED = 0` is the proto3 default, so an `Interval` that omits `strand` goes on the
    wire with a value the server rejects — as a bare `INVALID_ARGUMENT` naming no field. The
    blueprint attributed the failure to the missing `x-goog-fieldmask` and to 32 bp chunking;
    measurement refuted both. Asserted on the constructed message rather than against the service,
    so the regression is caught offline.
    """
    interval = ac._interval("chr22", 20002000, 20002032)
    assert interval.strand != 0, "the proto3 default is STRAND_UNSPECIFIED and the server refuses it"
    assert interval.strand == dna_model_pb2.STRAND_UNSTRANDED
    assert (interval.start, interval.end) == (20002000, 20002032)


def test_the_interval_request_converts_from_one_based_to_the_protos_zero_based_start():
    """Two coordinate conventions in one proto file, reconciled at this boundary.

    `Variant.position` is the 1-based VCF position; `Interval.start` is 0-based. A caller passing VCF
    positions throughout is what `@start-1based` asks for, so the `-1` lives here and exactly here —
    and a single-base interval cannot reveal an off-by-one, which is why this asserts on a width.
    """
    captured = {}

    class _Recorder:
        def ListDenseVariantScores(self, request, metadata=None):  # noqa: N802
            captured["interval"] = request.interval
            captured["filter"] = request.filter
            return atlas_service_pb2.ListDenseVariantScoresResponse()

    client = ac.AtlasClient(_Recorder(), api_key="x")
    assert client.score_interval("chr22", 20002001, 20002032, scorers=("AVI_SCORE",)) == ()
    assert captured["interval"].start == 20002000, "1-based 20002001 is 0-based 20002000"
    assert captured["interval"].end == 20002032
    assert captured["filter"] == '(scores.variant_scorer.name = "AVI_SCORE")'


def test_pagination_follows_the_token_rather_than_assuming_a_page_size():
    """A 1,024 bp interval comes back as 512 scores plus a token, and the token is what decides.

    Pinned against a fake that hands out two pages, because the alternative — stopping at
    `OBSERVED_PAGE_SIZE` — would silently truncate the day the server changed its page size, and a
    truncated interval is indistinguishable from a sparsely-scored one.
    """

    def _entry(position: int):
        entry = atlas_service_pb2.DenseVariantScores()
        entry.variant.chromosome = "chr22"
        entry.variant.position = position
        entry.variant.reference_bases = "A"
        entry.variant.alternate_bases = "T"
        block = entry.scores.add()
        block.variant_scorer.name = "AVI_SCORE"
        block.scores = struct.pack("<f", 0.5)
        block.calibrated_scores = struct.pack("<f", 0.75)
        return entry

    class _Paged:
        def __init__(self):
            self.tokens = []

        def ListDenseVariantScores(self, request, metadata=None):  # noqa: N802
            self.tokens.append(request.page_token)
            response = atlas_service_pb2.ListDenseVariantScoresResponse()
            if not request.page_token:
                response.variant_scores.append(_entry(1))
                response.next_page_token = "more"
            else:
                response.variant_scores.append(_entry(2))
            return response

    stub = _Paged()
    out = ac.AtlasClient(stub, api_key="x").score_interval(
        "chr22", 1, 33, scorers=("AVI_SCORE",)
    )
    assert stub.tokens == ["", "more"], "the second call must carry the token from the first"
    assert [s.position for s in out] == [1, 2]
    assert out[0].scores[0].raw == pytest.approx((0.5,))
    assert out[0].scores[0].phred == pytest.approx(6.0206, abs=1e-3)


@live
def test_the_interval_rpc_answers_on_the_two_package_tier():
    """The claim RM194 needed and the blueprint could not make: this RPC is reachable hand-built.

    32 bp of chr22 is 96 variants — three ALTs at each of 32 positions — and the count is derived
    from the width rather than quoted, so a re-run against a different window still checks the
    relationship instead of a number.
    """
    client = ac.connect(API_KEY)
    width = 32
    scores = client.score_interval(
        "chr22", 20002001, 20002000 + width, scorers=("AVI_SCORE",)
    )
    assert len(scores) == width * 3, "three ALTs per position"
    assert {s.chrom for s in scores} == {"chr22"}
    assert min(s.position for s in scores) == 20002001, "the 0-based conversion is off by one"
    assert all(s.scores and s.scores[0].scorer == "AVI_SCORE" for s in scores)


@live
def test_the_field_mask_is_a_bandwidth_choice_and_not_a_requirement():
    """Measured rather than assumed: the same interval answers identically with and without it.

    The blueprint recorded the mask as one of two reasons hand-built requests failed. It is neither
    — asserted as **equality of the answers**, because "both succeeded" would pass even if the
    unmasked call quietly returned less.
    """
    client = ac.connect(API_KEY)
    masked = client.score_interval("chr22", 20002001, 20002032, scorers=("AVI_SCORE",))
    plain = client.score_interval(
        "chr22", 20002001, 20002032, scorers=("AVI_SCORE",), field_mask=False
    )
    assert [(s.position, s.ref, s.alt) for s in masked] == [
        (s.position, s.ref, s.alt) for s in plain
    ]


@live
def test_an_interval_wider_than_one_page_is_followed_to_the_end():
    """1,024 bp is 3,072 variants and the server pages at 512 — so the token has to be followed.

    The other half of the chunking claim: 32 bp sub-intervals are the SDK's parallelism strategy,
    not a protocol requirement. A 1,024 bp request is legal and simply arrives in pages.
    """
    client = ac.connect(API_KEY)
    width = 1024
    scores = client.score_interval(
        "chr22", 20002001, 20002000 + width, scorers=("AVI_SCORE",)
    )
    assert len(scores) > ac.OBSERVED_PAGE_SIZE, "this interval must span more than one page"
    assert len(scores) == width * 3
    assert len({(s.position, s.alt) for s in scores}) == len(scores), "a page was repeated"


def test_a_token_on_an_exactly_full_final_page_does_not_send_a_seventh_request():
    """The upstream AIP-158 bug, pinned offline so it cannot come back as a live-only surprise.

    Measured against the real service on 2026-09-10: a 1,000 bp interval (3,000 variants, a short
    last page) correctly omits the token, while 1,024 bp (3,072 — exactly six pages of 512) carries
    one on the **last** page, and the seventh request comes back `INVALID_ARGUMENT`. The SDK's loop
    has the same shape and never trips only because it sends 32 bp sub-intervals, which cannot fill
    a page.

    The fake here reproduces exactly that: a full page, covering the whole requested interval, plus
    a token. A client that trusts the token alone makes a second call — which is the assertion.
    """

    class _LyingServer:
        def __init__(self):
            self.calls = 0

        def ListDenseVariantScores(self, request, metadata=None):  # noqa: N802
            self.calls += 1
            response = atlas_service_pb2.ListDenseVariantScoresResponse()
            if self.calls == 1:
                # The whole interval, in one page, and a token that should not be here.
                for position in range(1, 5):
                    entry = response.variant_scores.add()
                    entry.variant.chromosome = "chr22"
                    entry.variant.position = position
                    entry.variant.reference_bases = "A"
                    entry.variant.alternate_bases = "T"
                response.next_page_token = "this token is a lie"
            return response

    stub = _LyingServer()
    out = ac.AtlasClient(stub, api_key="x").score_interval("chr22", 1, 4, scorers=("AVI_SCORE",))

    assert stub.calls == 1, "the walk must stop once the requested interval is covered"
    assert [s.position for s in out] == [1, 2, 3, 4]
