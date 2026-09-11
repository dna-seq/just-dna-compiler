"""The AlphaGenome Atlas client — precomputed variant scores over gRPC, on two packages (RM192).

**The `[atlas]` extra, not core.** `uv add alphagenome` costs **550 MB and 47 packages** against a tier
whose entire runtime list is httpx/tenacity/huggingface-hub, and six of the twenty dependencies that
wheel declares are never imported on any scoring path. The `.proto` sources are Apache-2.0, so
`grpcio` + `protobuf` reach every Atlas RPC — **19 MB** (`pyproject.toml` carries the measurement;
22 MB was the grpcio release current at the design round), with score payloads decoding through
`struct.unpack` from the standard library. Measured in
[ALPHAGENOME_ATLAS.md § 6.2](../../../docs/probes/ALPHAGENOME_ATLAS.md), and pinned by
`test_imports_stay_within_the_declared_floor` rather than left as a claim in prose.

The bindings are **generated, not committed**, and neither are the sources they come from:
`just-dna-enricher atlas generate` fetches the `.proto` files from `google-deepmind/alphagenome` at
the commit and per-file sha256 `atlas_protos.py` pins, then builds them into a git-ignored
`generated/` package. So this module's import is guarded, and a checkout that has not run the
generator gets a message naming the command instead of a traceback from protobuf. The repository
carries the pin and the distribution carries the files — `hatch_build.py` runs the same fetch at
wheel-build time, which is what made an installed wheel work at all. That is RM196, and
`docs/vendor/alphagenome_protos/README.md` is where the vendored copy used to be.

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
`grpc_service_config.json` (`@retry-attempt-floor`) and no shared pacing gate
(`@shared-pacing-gate`).

`ListDenseVariantScores` **is** here — `score_interval` — and the reason it took a second attempt is
recorded in `_interval`: the blocker was `Interval.strand` having no zero member, not the
`x-goog-fieldmask` header or 32 bp chunking that this docstring blamed for a day.
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


#: The response field mask the SDK sends. **Optional, measured** — the RPC answers without it — so it
#: is a bandwidth choice rather than a protocol requirement: it trims the per-track metadata that a
#: caller reading `scores`/`calibrated_scores` never looks at.
LIST_FIELD_MASK: tuple[str, ...] = (
    "interval",
    "next_page_token",
    "variant_scores.variant",
    "variant_scores.scores.variant_scorer",
    "variant_scores.scores.metadata.gene_scorers",
    "variant_scores.scores.shape",
    "variant_scores.scores.scores",
    "variant_scores.scores.calibrated_scores",
)

#: How many variants one page carries, measured: a 1,024 bp interval comes back as 512 scores plus a
#: `next_page_token`. Named so the pagination loop below is readable, never used as an assumption —
#: the token is what decides whether there is more.
OBSERVED_PAGE_SIZE = 512


def wire_contig(chrom: str) -> str:
    """`22` → `chr22`, and `chr22` unchanged — the spelling the Atlas wire expects.

    **This module already owns one coordinate convention and this is the second.** `_interval`'s
    docstring says the 0-based/1-based conversion happens here so callers pass VCF positions
    throughout; contig spelling is exactly the same class of fact, and leaving it to callers is what
    let a pass send `22` and get back a bare `NOT_FOUND: Chromosome 22 not found` — a live failure
    that no offline test could have produced, because a stub answers whatever it is asked.

    **One normalizer, not two** (`@one-normalizer-two-spellings`). `alphagenome_check` had a private
    `_chr` doing this for the snapshot join, which is the shape where a private name keeps the second
    caller from finding the first: the same conversion was needed at the RPC boundary and nothing
    pointed there. `VariantRow` normalizes through `vrs.normalize_chrom` and stores `22`; AlphaGenome
    is UCSC-style `chr22` on the wire and in its tabix index alike. One direction only, at the
    boundary — the prefixed spelling is the source's, so the conversion belongs to the code crossing
    into it rather than to either model.
    """
    value = str(chrom).strip()
    return value if value.lower().startswith("chr") else f"chr{value}"


def _interval(chrom: str, start: int, end: int):
    """A proto `Interval`, with `strand` set to a real member — and that is the whole trick.

    **`Strand` has no zero member.** `STRAND_UNSPECIFIED = 0` is the proto3 default, so an `Interval`
    that simply omits `strand` goes on the wire with a value the server rejects, and it rejects it as
    a bare `INVALID_ARGUMENT: Request contains an invalid argument.` naming no field. That is what
    made `ListDenseVariantScores` look unreachable from a hand-built client: the blueprint attributed
    it to the missing field mask and to 32 bp chunking, and measurement on 2026-09-10 refuted both —
    the mask is optional and a 128 bp interval answers in one call. Only the strand was wrong.

    `start`/`end` are **0-based**, unlike `Variant.position` next door, which is the 1-based VCF one
    (`@start-1based`). Two coordinate conventions in one proto file, so the conversion happens here
    and callers of this module pass VCF positions throughout.
    """
    return dna_model_pb2.Interval(
        chromosome=chrom,
        start=start,
        end=end,
        strand=dna_model_pb2.STRAND_UNSTRANDED,
    )


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
class GeneRef:
    """One gene a scorer attributed a score to — **the source's own attribution, not ours**.

    `gene_id` is kept **verbatim, version included**. Upstream's proto comment says the field is the
    "ENSEMBL gene identifier without version number, e.g. ENSG00000100342" and the live service
    returns `ENSG00000040608.14`, so the comment is wrong and the bytes are not
    (`@verbatim-except-order`). A caller joining on bare accessions truncates deliberately; one who
    believed the comment would have written a join that silently matches nothing.
    """

    gene_id: str
    name: str | None


def _gene_refs(block) -> tuple[GeneRef, ...]:
    """The `gene_scorers` payload of a block's metadata, or empty for a scorer with no gene axis.

    `DenseVariantScore.metadata` is **repeated** and each entry is a `oneof` — a gene-axis scorer
    comes back carrying both a `gene_scorers` payload matching `shape[0]` and a `tracks` payload
    matching `shape[1]`. Only the first is read here; the track vocabulary is the one RM200 measured
    and refused to rank (`EFO` cancer cell lines, `UBERON` anatomical structures and `CL` cell types
    under one ordering are not one axis).
    """
    out: list[GeneRef] = []
    for entry in block.metadata:
        if entry.WhichOneof("payload") != "gene_scorers":
            continue
        out.extend(GeneRef(gene_id=g.gene_id, name=g.name or None) for g in entry.gene_scorers.metadata)
    return tuple(out)


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
    #: The genes this block is attributed to, in the order `shape[0]` indexes them. Empty for the
    #: twenty-one scorers with no gene axis. `RNA_SEQ` is the only one that fills it, which is
    #: precisely why RM200 adopted that one and refused the rest.
    genes: tuple[GeneRef, ...] = ()

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


@dataclass(frozen=True)
class IntervalScore:
    """One variant inside an interval, with the scorer block that came back for it."""

    chrom: str
    position: int
    ref: str
    alt: str
    scores: tuple[VariantScore, ...]


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


def interval_filter(*, scorers: tuple[str, ...] = (), gene_names: tuple[str, ...] = ()) -> str:
    """The AIP-160 filter an interval query needs, over scorers and/or attributed genes.

    Two clauses ANDed, each an OR over its own members — the shape the SDK builds, reproduced here
    because the filter is a *string* and is therefore the one part of the request a hand-built client
    has to know rather than derive from the protos.

    The gene clause is what makes a gene-scoped slice possible at all: the Atlas attributes a variant
    to genes across the model's whole input window, so filtering by gene name is a server-side
    selection rather than a coordinate range the caller guesses at.
    """
    clauses = []
    if scorers:
        clauses.append(" OR ".join(f'scores.variant_scorer.name = "{s}"' for s in scorers))
    if gene_names:
        clauses.append(" OR ".join(f'scores.metadata.gene_scorers.metadata.name = "{g}"' for g in gene_names))
    return " AND ".join(f"({c})" for c in clauses)


def _translate(error: grpc.RpcError, *, variant: str) -> AtlasError:
    """One place where a transport exception becomes this module's contract.

    Keyed on the status code, and the server's own text is carried through rather than
    paraphrased: a refusal that cannot quote its reason is a refusal the caller cannot act on.
    """
    code = error.code()
    details = error.details() or ""
    if code is grpc.StatusCode.UNIMPLEMENTED:
        return AtlasNotScored(f"{variant} is not in the precomputed Atlas (indels are not scored): {details}")
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
        chrom = wire_contig(chrom)
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
                genes=_gene_refs(block),
            )
            for block in response.scores
        )

    def score_interval(
        self,
        chrom: str,
        start: int,
        end: int,
        *,
        scorers: tuple[str, ...] = (),
        gene_names: tuple[str, ...] = (),
        field_mask: bool = True,
    ) -> tuple[IntervalScore, ...]:
        """Every scored variant in `[start, end)`, following `next_page_token` to the last page.

        `start`/`end` are **1-based VCF positions**, converted to the proto's 0-based interval here
        so this module speaks one coordinate convention throughout (`@start-1based`).

        **A filter is effectively required, and that is a size limit rather than a rule.** Measured:
        an unfiltered 32 bp interval answers with a 43 MB message and dies on the 4 MB client
        default — `RESOURCE_EXHAUSTED: Received message larger than max`. So an unfiltered request is
        not "slower", it fails, and the caller is told which knob to turn rather than left to read
        a transport error.

        Pagination, not chunking, is what bounds a page: a 1,024 bp interval comes back as 512
        scores and a token. The SDK's 32 bp sub-intervals are its *parallelism* strategy, not a
        protocol requirement — a 128 bp interval answers in one call.

        **The token cannot be trusted on its own**, and that is upstream's bug rather than a
        precaution: the server returns one on an *exactly-full final page*, and the next request
        comes back `INVALID_ARGUMENT`. So the walk also stops once the requested interval is
        covered. The loop below has the measurement; a caller reading only this docstring would
        otherwise re-derive the crash.
        """
        if not scorers and not gene_names:
            raise AtlasRefused(
                f"{chrom}:{start}-{end}: an interval query needs a filter. Unfiltered, the Atlas "
                "answers with every scorer for every variant — measured at 43 MB for 32 bp, against "
                "a 4 MB default receive limit. Pass `scorers` and/or `gene_names`."
            )
        chrom = wire_contig(chrom)
        label = f"{chrom}:{start}-{end}"
        metadata = self._metadata
        if field_mask:
            metadata = (*metadata, ("x-goog-fieldmask", ",".join(LIST_FIELD_MASK)))

        request = atlas_service_pb2.ListDenseVariantScoresRequest(
            interval=_interval(chrom, start - 1, end),
            organism=dna_model_pb2.ORGANISM_HOMO_SAPIENS,
            filter=interval_filter(scorers=scorers, gene_names=gene_names),
        )
        out: list[IntervalScore] = []
        while True:
            try:
                response = self._stub.ListDenseVariantScores(request, metadata=metadata)
            except grpc.RpcError as exc:
                raise _translate(exc, variant=label) from exc
            for entry in response.variant_scores:
                out.append(
                    IntervalScore(
                        chrom=entry.variant.chromosome,
                        position=entry.variant.position,
                        ref=entry.variant.reference_bases,
                        alt=entry.variant.alternate_bases,
                        scores=tuple(
                            VariantScore(
                                scorer=block.variant_scorer.name,
                                raw=unpack_float32(block.scores),
                                quantile=unpack_float32(block.calibrated_scores),
                                shape=tuple(block.shape),
                                genes=_gene_refs(block),
                            )
                            for block in entry.scores
                        ),
                    )
                )
            if not response.next_page_token:
                return tuple(out)
            # **The server hands back a token on an exactly-full final page, and following it 400s.**
            # Measured on 2026-09-10: a 1,000 bp interval is 3,000 variants over six pages and the
            # short last page correctly omits the token, while a 1,024 bp interval is 3,072 — exactly
            # six full pages of 512 — and page six carries a token whose seventh request comes back
            # `INVALID_ARGUMENT`. That is AIP-158 violated in the one place a faithful client cannot
            # survive it, and the SDK's own loop has the same shape; it never trips because the SDK
            # only ever sends 32 bp sub-intervals, which cannot fill a page.
            #
            # So the token is followed but not *trusted* as the sole terminator: reaching the last
            # base the caller asked for ends the walk too. Deriving it from the request rather than
            # from a page-size constant keeps it right if the server's page size ever moves.
            if out and max(score.position for score in out) >= end:
                return tuple(out)
            request.page_token = response.next_page_token

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
