"""The AlphaGenome Atlas client — precomputed variant scores over gRPC, on two packages (RM192).

**The `[atlas]` extra, not core.** `uv add alphagenome` costs 255 MB and 36 packages against a tier
whose entire runtime list is httpx/tenacity/huggingface-hub, and six of the twenty dependencies that
wheel declares are never imported on any scoring path. The `.proto` sources are Apache-2.0, so
`grpcio` + `protobuf` reach every Atlas RPC — **22 MB**, with score payloads decoding through
`struct.unpack` from the standard library. Measured in
[ALPHAGENOME_ATLAS.md § 6.2](../../../docs/probes/ALPHAGENOME_ATLAS.md), and pinned by
`test_imports_stay_within_the_declared_floor` rather than left as a claim in prose.

The bindings are **generated, not committed**: `just-dna-enricher atlas generate` builds them from
`docs/vendor/alphagenome_protos/` into a git-ignored `generated/` package. So this module's import
is guarded, and a checkout that has not run the generator gets a message naming the command instead
of a traceback from protobuf. An installed wheel cannot run it at all — that is RM196.

Three house rules shape the code rather than the wire format:

* **A client leaking its transport library's exception has no contract** (`@client-exception-contract`).
  Every `grpc.RpcError` is translated at the boundary into an `AtlasError` subclass, and the
  distinction that matters is *which kind of no*: a transport failure is retryable, a refusal is
  not, and "this variant is not in the precomputed set" is neither — it is an answer.
* **The house algebra is three-valued** and `None` is never `False`. An indel is not scored zero,
  it is not scored at all, and `score_variant` says so by raising rather than returning a number.
* **A verdict function with several arms owes a reason function with the same arms**
  (`@answered-is-not-absent`), which is why every refusal carries the server's own words.

What a first cut does not carry, filed rather than improvised: no `tenacity` layer over the vendored
`grpc_service_config.json` (`@retry-attempt-floor`), no shared pacing gate
(`@shared-pacing-gate`), and no interval RPC — `ListDenseVariantScores` needs an
`x-goog-fieldmask` header and 32 bp chunking, which RM194 owes and RM192 does not.
"""

import math
import struct
from dataclasses import dataclass

import grpc

from just_dna_enricher.atlas_protos import OUT_DIR, SERVICE_CONFIG_NAME

# The one guarded module-level import the house rules allow, and the reason it is guarded is that
# the bindings are a build product rather than source: `generated/` is git-ignored, so a fresh
# checkout has none until the generator runs. Re-raised with the command to run, because
# `ModuleNotFoundError: just_dna_enricher.generated…` names a package nobody wrote and sends the
# reader looking for a typo.
try:
    from just_dna_enricher.generated._alphagenome_atlas_protos import (
        atlas_service_pb2,
        atlas_service_pb2_grpc,
        dna_model_pb2,
    )
except ImportError as _exc:  # pragma: no cover - exercised by a subprocess test, not in-process
    raise ImportError(
        "the Atlas gRPC bindings have not been generated. Run `just-dna-enricher atlas generate` "
        "from a checkout of just-dna-format (it needs grpcio-tools, which is in the [dev] group). "
        "An installed package carries no docs/vendor tree and cannot generate them — RM196."
    ) from _exc

#: The service. Named here rather than inline so a test can point at a fake.
DEFAULT_ADDRESS = "dns:///gdmscience.googleapis.com:443"

#: Retry/backoff policy, taken verbatim from upstream. It sits **beside the generated bindings**
#: rather than in `docs/vendor/`, because the channel reads it at connect time and a runtime that
#: has the bindings must have the policy too — one directory the client needs, not two. The
#: generator copies it there.
SERVICE_CONFIG_PATH = OUT_DIR / SERVICE_CONFIG_NAME

#: The largest `float32` strictly below 1.0, and therefore the largest quantile the wire format can
#: carry. It caps a derived Phred at ~72.247 — while the **published AVI artifact reaches 89.451**,
#: so for the most extreme rows the API saturates to exactly 1.0 and the Phred value is
#: unrecoverable from it (ALPHAGENOME_ATLAS.md § 6.3 measures this: about 1,300 rows genome-wide).
#: Named so a caller can tell "off the top of the float32 scale" from "wrong".
#:
#: There is deliberately **no** clamp at the FAQ's 0.999990 / Phred 50. That cap describes the
#: API's `quantile_score` for the recommended per-modality scorers; the AVI column measurably does
#: not obey it, and clamping to a bound the data exceeds would silently rewrite real values.
MAX_FLOAT32_QUANTILE = 1.0 - 2.0**-24
MAX_REPRESENTABLE_PHRED = 72.24719895935549


class AtlasError(RuntimeError):
    """Base for every failure this client reports. No `grpc.RpcError` escapes past it."""


class AtlasUnavailable(AtlasError):
    """The service could not be reached or did not answer. Retryable; says nothing about the variant."""


class AtlasRefused(AtlasError):
    """The service understood the request and declined it. Not retryable."""


class AtlasRefMismatch(AtlasRefused):
    """`REF` does not match the assembly at that position.

    Worth its own type because it is a *finding about the caller's data*, not about the service —
    the Atlas validates against GRCh38 and names the real base, which is the check a local file
    lookup cannot make (`@va-omits-ref`: a VA does not encode `ref`).
    """


class AtlasNotScored(AtlasError):
    """The variant is outside the precomputed set — indels, today.

    Deliberately **not** an `AtlasRefused`: the request was legal and the answer is "unknown",
    which is the third state. Callers that treat this as zero are the bug this type exists to
    prevent (`@unreachable-not-absent`).
    """


@dataclass(frozen=True)
class VariantScore:
    """One scorer's answer for one variant.

    `raw` is the magnitude on the scorer's own scale; `quantile` is its empirical rank against a
    background of common variants (MAF > 0.01 in any gnomAD v3 population). Both are `None` when
    the server returned the block but not that field — absent is not zero here either.
    """

    scorer: str
    raw: tuple[float, ...] | None
    quantile: tuple[float, ...] | None
    shape: tuple[int, ...]

    @property
    def phred(self) -> float | None:
        """The Phred-scaled quantile, or `None` when there is no quantile to scale.

        Reproduces the `PHRED` column of the published AVI artifact from its `calibrated_scores`.
        Scalar scorers only — a multi-valued block has no single Phred value to report.
        """
        if self.quantile is None or len(self.quantile) != 1:
            return None
        if self.quantile[0] >= 1.0:
            return None  # saturated; the property withholds where the function refuses
        return phred_from_quantile(self.quantile[0])


def phred_from_quantile(quantile: float) -> float:
    """`-10 log10(1 - q)`, the transform the published AVI file's `PHRED` column is.

    A saturated quantile — exactly 1.0, which is what the API returns for the most extreme variants
    — raises rather than returning infinity or a clamped stand-in. The honest answer there is "this
    surface cannot tell you", and a number would be a worse answer than a refusal: the file has the
    real value and the API does not (`@unreachable-not-absent`, at the resolution of one float).
    """
    if not 0.0 <= quantile <= 1.0:
        raise ValueError(f"quantile must be in [0, 1], got {quantile!r}")
    if quantile >= 1.0:
        raise AtlasNotScored(
            "quantile saturated at 1.0: the float32 wire format caps a derived Phred at "
            f"{MAX_REPRESENTABLE_PHRED:.3f} and the published artifact goes above it. "
            "Read PHRED from the downloaded file for this variant."
        )
    return -10.0 * math.log10(1.0 - quantile)


def unpack_float32(payload: bytes) -> tuple[float, ...] | None:
    """Decode a score field. `None` for an absent field, never an empty tuple silently.

    The wire format is little-endian `float32`, unpacked with the standard library because the
    whole point of this blueprint is that no array package is required to read a score.
    """
    if not payload:
        return None
    if len(payload) % 4:
        raise AtlasError(f"score payload is not a whole number of float32: {len(payload)} bytes")
    return struct.unpack(f"<{len(payload) // 4}f", payload)


def scorer_filter(*scorers: str) -> str:
    """The AIP-160 filter string selecting one or more scorers.

    A string, not a message — the one piece of the request that does not come from the protos, and
    the reason a hand-built client is possible at all.
    """
    if not scorers:
        return ""
    return " OR ".join(f'scores.variant_scorer.name = "{s}"' for s in scorers)


def _translate(error: grpc.RpcError, *, variant: str) -> AtlasError:
    """One place where a transport exception becomes this module's contract.

    Keyed on the status code, and the server's own text is carried through rather than
    paraphrased: a refusal that cannot quote its reason is a refusal the caller cannot act on.
    """
    code = error.code()
    details = error.details() or ""
    if code is grpc.StatusCode.UNIMPLEMENTED:
        return AtlasNotScored(
            f"{variant} is not in the precomputed Atlas (indels are not scored): {details}"
        )
    if code is grpc.StatusCode.INVALID_ARGUMENT:
        if "reference base" in details:
            return AtlasRefMismatch(f"{variant}: {details}")
        return AtlasRefused(f"{variant}: {details}")
    if code in (
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
        grpc.StatusCode.INTERNAL,
    ):
        return AtlasUnavailable(f"{variant}: {code.name}: {details}")
    return AtlasRefused(f"{variant}: {code.name}: {details}")


class AtlasClient:
    """The three Atlas RPCs, with the transport's exceptions kept inside."""

    def __init__(self, stub, *, api_key: str) -> None:
        self._stub = stub
        self._metadata = (("x-goog-api-key", api_key),)

    def score_variant(
        self, chrom: str, position: int, ref: str, alt: str, *, scorers: tuple[str, ...] = ()
    ) -> tuple[VariantScore, ...]:
        """Precomputed scores for one SNV. Raises rather than inventing a number.

        `position` is the 1-based VCF position, passed through unchanged (`@start-1based`).
        """
        label = f"{chrom}:{position} {ref}>{alt}"
        request = atlas_service_pb2.GetDenseVariantScoresRequest(
            variant=dna_model_pb2.Variant(
                chromosome=chrom,
                position=position,
                reference_bases=ref,
                alternate_bases=alt,
            ),
            organism=dna_model_pb2.ORGANISM_HOMO_SAPIENS,
            filter=scorer_filter(*scorers),
        )
        try:
            response = self._stub.GetDenseVariantScores(request, metadata=self._metadata)
        except grpc.RpcError as exc:
            raise _translate(exc, variant=label) from exc
        return tuple(
            VariantScore(
                scorer=block.variant_scorer.name,
                raw=unpack_float32(block.scores),
                quantile=unpack_float32(block.calibrated_scores),
                shape=tuple(block.shape),
            )
            for block in response.scores
        )

    def scorer_names(self) -> tuple[str, ...]:
        """Every scorer the Atlas serves. 22 of them at the time of writing."""
        request = atlas_service_pb2.ListVariantScoresMetadataRequest(
            organism=dna_model_pb2.ORGANISM_HOMO_SAPIENS
        )
        try:
            response = self._stub.ListVariantScoresMetadata(request, metadata=self._metadata)
        except grpc.RpcError as exc:
            raise _translate(exc, variant="<metadata>") from exc
        return tuple(entry.variant_scorer.name for entry in response.variant_scorer_metadata)


def connect(api_key: str, *, address: str = DEFAULT_ADDRESS, timeout: float = 30.0) -> AtlasClient:
    """Open a channel and hand back a client, translating a failed handshake like any other error."""
    channel = grpc.secure_channel(
        address,
        grpc.ssl_channel_credentials(),
        options=(("grpc.service_config", SERVICE_CONFIG_PATH.read_text()),),
    )
    try:
        grpc.channel_ready_future(channel).result(timeout)
    except grpc.FutureTimeoutError as exc:
        raise AtlasUnavailable(f"channel to {address} not ready within {timeout}s") from exc
    return AtlasClient(atlas_service_pb2_grpc.AtlasServiceStub(channel=channel), api_key=api_key)
