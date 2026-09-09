"""A minimal AlphaGenome Atlas client — the blueprint measured in ALPHAGENOME_ATLAS.md § 6.2.

**This is a proof of concept, not a shipped surface.** Nothing in `just-dna-enricher` imports it,
it is outside `testpaths`, and no `RMn` adopts it. It exists to make one claim testable: that the
Atlas service is reachable on `grpcio` + `protobuf` alone, without the `alphagenome` wheel and the
twenty flat dependencies it declares.

What it costs, measured: **22 MB** of runtime dependencies against 255 MB for `uv add alphagenome`,
and 28 KB of vendored Apache-2.0 `.proto` sources in `docs/vendor/alphagenome_protos/` whose
bindings `generate.py` builds. Score payloads are plain `bytes`, so `struct.unpack` from the
standard library decodes them — numpy is not needed either.

Three house rules shape the code rather than the wire format:

* **A client leaking its transport library's exception has no contract** (`@client-exception-contract`).
  Every `grpc.RpcError` is translated at the boundary into an `AtlasError` subclass, and the
  distinction that matters is *which kind of no*: a transport failure is retryable, a refusal is
  not, and "this variant is not in the precomputed set" is neither — it is an answer.
* **The house algebra is three-valued** and `None` is never `False`. An indel is not scored zero,
  it is not scored at all, and `score_variant` says so by raising rather than returning a number.
* **A verdict function with several arms owes a reason function with the same arms**
  (`@answered-is-not-absent`), which is why every refusal carries the server's own words.
"""

import math
import struct
from dataclasses import dataclass
from pathlib import Path

import grpc

from docs.probes.alphagenome_poc.generated._alphagenome_atlas_protos import (
    atlas_service_pb2,
    atlas_service_pb2_grpc,
    dna_model_pb2,
)

#: The service. Named here rather than inline so a test can point at a fake.
DEFAULT_ADDRESS = "dns:///gdmscience.googleapis.com:443"

#: Retry/backoff policy, taken verbatim from upstream beside the protos it belongs to.
SERVICE_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "vendor" / "alphagenome_protos" / "grpc_service_config.json"
)

#: The quantile cap the upstream FAQ states, from the ~300 K common variants the background was
#: estimated on. It bounds `phred_from_quantile` at 50 — a value at the cap means "at least this
#: extreme", never "exactly this extreme", so the ceiling is worth naming rather than discovering.
QUANTILE_CAP = 0.999990
PHRED_CEILING = 50.0


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
        return phred_from_quantile(self.quantile[0])


def phred_from_quantile(quantile: float) -> float:
    """`-10 log10(1 - q)`, the transform the published AVI file's `PHRED` column is.

    Clamped at `PHRED_CEILING` rather than allowed to run to infinity: the background distribution
    is capped at `QUANTILE_CAP`, so a larger value would be an artefact of float error and not a
    stronger claim.
    """
    if not 0.0 <= quantile < 1.0:
        raise ValueError(f"quantile must be in [0, 1), got {quantile!r}")
    if quantile >= QUANTILE_CAP:
        return PHRED_CEILING
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
