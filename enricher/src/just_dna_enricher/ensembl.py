"""Live Ensembl resolution — for the rare rsIDs the frozen snapshot slice misses.

Two backends, tried in order with a fallback the user asked for:

  V2 — the beta **GraphQL** variation API (endpoint + query shape leeched from ensembl-mcp, with
       `fastmcp`/`eliot` dropped and stdlib `logging` in their place); and
  V1 — the legacy **REST** variation API (rest.ensembl.org), which is the workhorse for a *bare*
       rsID → coordinate (the beta GraphQL variant lookup needs a composite `region:pos:rsid` id, so
       a bare rsID falls through to REST). V1 also serves as the explicit **fallback on 500/503** from
       V2.

`tenacity` retries each backend on transient transport/timeout errors; a 5xx is not retried but
triggers the V2→V1 fallback. All network lives here (never in format/compiler). GRCh38 only.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from just_dna_format.vrs import refget_accession
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.clingen_allele import anchor_indel
from just_dna_enricher.net import attempt_floor
from just_dna_enricher.sequences import SequenceProxy

logger = logging.getLogger(__name__)

# Endpoints leeched from ensembl-mcp's config (the human GRCh38 genome id is beta's fixed UUID).
DEFAULT_GRAPHQL_ENDPOINT = "https://beta.ensembl.org/api/graphql/variation"
DEFAULT_REST_ENDPOINT = "https://rest.ensembl.org"
_FALLBACK_STATUS = frozenset({500, 502, 503, 504})
_ASSEMBLY = "GRCh38"

# Minimal variant query (ensembl-mcp's variation backend shape, trimmed to the location fields we
# need). Bare-rsID lookup needs a composite id, so this is a best-effort V2 attempt that gracefully
# yields to the REST fallback when beta rejects it.
_VARIANT_QUERY = """
query Variant($genomeId: String!, $variantId: String!) {
  variant(by_id: {genome_id: $genomeId, variant_id: $variantId}) {
    name
    alleles { allele_type { value } reference_sequence }
    slice { location { region_name start } }
  }
}
"""


@dataclass
class EnsemblSettings:
    graphql_endpoint: str = DEFAULT_GRAPHQL_ENDPOINT
    rest_endpoint: str = DEFAULT_REST_ENDPOINT
    human_genome_id: str = "a7335667-93e7-11ec-a39d-005056b38ce3"
    species: str = "human"
    timeout: float = 15.0


class EnsemblError(RuntimeError):
    """A live Ensembl query failed on all backends (after retries + fallback)."""


@dataclass
class EnsemblResolver:
    """Resolve a bare rsID to its GRCh38 loci via live Ensembl (V2 GraphQL → V1 REST fallback)."""

    settings: EnsemblSettings = field(default_factory=EnsemblSettings)
    _client: httpx.Client | None = None
    # One GRCh38 base at a 1-based position, or `None` — what anchors a one-sided REST indel (RM268).
    # Private like `_client`, so a patch adds no constructor surface; a test sets it the same way.
    _read_base: Callable[[str, int], str | None] | None = None

    def _base_reader(self) -> Callable[[str, int], str | None]:
        if self._read_base is None:
            self._read_base = _grch38_base_reader(SequenceProxy())
        return self._read_base

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        """Return `([{chrom, start, ref, alts}, ...], source)` for a bare rsID.

        Tries V2 GraphQL, then falls back to V1 REST on a 5xx (or when V2 yields nothing). `source` is
        `ensembl-graphql` or `ensembl-rest` — recorded per row so the manifest can report provenance.

        **Three outcomes, because two of them used to be one (S20).** A non-empty list is an answer;
        `[]` is *also* an answer — Ensembl was reached and has no GRCh38 locus for this rsID — and
        **`None` means Ensembl could not be asked at all**, so its answer is unchecked rather than
        empty. Fusing the last two into `([], None)` made a failed request read as a definite negative,
        and `loci: []` plus "Ensembl has no locus" is exactly the fingerprint of a fabricated rsID: a
        consumer checking which ids in a machine-written document were real put two published variants
        in the fabricated pile on a flaky run. This is the tri-state rule the rest of the tree keeps —
        an unreachable source reports unknown, never the negative.

        A **4xx is an answer**, not a failure: Ensembl 400s on rsIDs it cannot resolve (`rs3216883`,
        which dbSNP reports as merged), so only a 5xx, a transport error or a timeout — the cases where
        nothing came back at all — return `None`. An empty answer now carries its source too, so a
        caller can record *which* link said nothing; that omission was the only trace the old code
        left, and it was a missing element in a set nobody diffs.

        **`None` with a source is the fourth outcome (RM268): Ensembl answered, and nothing it said
        could be placed.** REST spells an insertion or a deletion with one side `-` at an interbase
        `start`, and such a locus is written only once the reference base before the event has been
        read and prefixed to every allele. When that base cannot be read, the locus is withheld, and an
        answer whose every locus was withheld is unchecked rather than empty, exactly like a request
        that failed; the source is returned so a caller can say which of the two happened.
        """
        try:
            loci = self._graphql_rsid(rsid)
            if loci:
                return loci, "ensembl-graphql"
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _FALLBACK_STATUS:
                logger.warning("V2 GraphQL for %s failed (%s); trying REST", rsid, exc)
        except (EnsemblError, httpx.TransportError, httpx.TimeoutException) as exc:
            logger.warning("V2 GraphQL for %s errored (%s); trying REST", rsid, exc)

        try:
            loci, withheld = self._rest_rsid(rsid)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _FALLBACK_STATUS:
                logger.warning("V1 REST for %s failed: %s", rsid, exc)
                return None, None
            logger.info("V1 REST has no record for %s (%s)", rsid, exc)
            return [], "ensembl-rest"
        except (httpx.HTTPError, EnsemblError) as exc:
            logger.warning("V1 REST for %s could not be reached: %s", rsid, exc)
            return None, None
        if withheld:
            logger.info(
                "V1 REST for %s: %d one-sided indel locus/loci withheld, the anchor base could not be "
                "read (RM268)",
                rsid,
                withheld,
            )
            if not loci:
                return None, "ensembl-rest"
        return loci, "ensembl-rest"

    # ── V2: beta GraphQL ──────────────────────────────────────────────────────────────────────
    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _graphql_rsid(self, rsid: str) -> list[dict]:
        resp = self._http().post(
            self.settings.graphql_endpoint,
            json={
                "query": _VARIANT_QUERY,
                "variables": {"genomeId": self.settings.human_genome_id, "variantId": rsid},
            },
        )
        resp.raise_for_status()
        payload = _json(resp)
        if payload.get("errors"):
            raise EnsemblError(f"GraphQL errors for {rsid}: {payload['errors']}")
        variant = (payload.get("data") or {}).get("variant")
        return _loci_from_graphql(variant)

    # ── V1: legacy REST ───────────────────────────────────────────────────────────────────────
    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=0.5, max=8.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    def _rest_rsid(self, rsid: str) -> tuple[list[dict], int]:
        resp = self._http().get(
            f"{self.settings.rest_endpoint}/variation/{self.settings.species}/{rsid}",
            params={"content-type": "application/json"},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return _loci_from_rest(_json(resp), self._base_reader())


def _grch38_base_reader(sequences: SequenceProxy) -> Callable[[str, int], str | None]:
    """A `read_base` for `anchor_indel`: `None` off the refget table (a patch contig) or when unreadable."""

    def read_base(chrom: str, pos: int) -> str | None:
        accession = refget_accession(chrom)
        if accession is None or pos < 1:
            return None
        return sequences.subsequence(accession, pos - 1, pos)

    return read_base


def _json(response: httpx.Response) -> dict:
    """The body as JSON, or `EnsemblError` — so `resolve_rsid` can treat it as a leg that failed.

    A 200 carrying HTML (Ensembl's maintenance page, a proxy interstitial) raised a bare
    `json.JSONDecodeError` here, and `resolve_rsid`'s first `try` catches only `httpx` types and
    `EnsemblError`: the GraphQL leg answering HTML never fell through to the REST leg the method
    exists to provide, and `enrich` — which wraps the call in `try/finally` with no `except` — aborted
    mid-loop instead of recording the subject as unreachable. Typed, both legs now withhold.
    """
    try:
        payload = response.json()
    except ValueError as exc:
        raise EnsemblError(f"{response.url} did not answer JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EnsemblError(f"{response.url} answered {type(payload).__name__}, not an object")
    return payload


def _loci_from_rest(payload: dict, read_base: Callable[[str, int], str | None]) -> tuple[list[dict], int]:
    """Parse Ensembl REST /variation mappings into GRCh38 loci, deterministically ordered.

    Returns the loci and the number of mappings withheld because a one-sided indel could not be
    anchored (RM268). REST states an insertion as `-/C` with `start = end + 1` and a deletion as
    `AGTAAG/-` over `[start, end]`; in both the base before the event sits at `start - 1`, which is
    `anchor_indel`'s convention (the interbase point is the preceding base). Every allele is prefixed
    with that base, so a mixed string such as `-/G/GT` anchors whole; a string with no `-`
    (`ATCATC/ATC`, `TCTT/T/TCTTCTT`) is already anchored and passes through untouched.
    """
    loci: list[dict] = []
    withheld = 0
    for m in payload.get("mappings", []):
        if m.get("assembly_name") != _ASSEMBLY:
            continue
        alleles = str(m.get("allele_string", "")).split("/")
        chrom = m.get("seq_region_name")
        start = m.get("start")
        if chrom is None or start is None or not alleles or not alleles[0]:
            continue
        chrom, start = str(chrom), int(start)
        if "-" in alleles:
            anchored = _anchor_rest_alleles(chrom, start, alleles, read_base)
            if anchored is None:
                withheld += 1
                continue
            start, alleles = anchored
        ref = alleles[0]
        alts = ",".join(alleles[1:]) if len(alleles) > 1 else None
        loci.append({"chrom": chrom, "start": start, "ref": ref, "alts": alts})
    return sorted(loci, key=lambda locus: (locus["chrom"], locus["start"], locus["ref"])), withheld


def _anchor_rest_alleles(
    chrom: str, start: int, alleles: list[str], read_base: Callable[[str, int], str | None]
) -> tuple[int, list[str]] | None:
    """A one-sided REST allele list → `(anchor position, anchored alleles)`, or `None` when unreadable."""
    sides = ["" if allele == "-" else allele for allele in alleles]
    anchored: list[str] = []
    for side in sides:
        # The first side is the reference itself, so its anchored form is the anchored `ref`.
        placed = anchor_indel((chrom, start - 1, sides[0], side), read_base)
        if placed is None:
            return None
        anchored.append(placed[3])
    return start - 1, anchored


def _loci_from_graphql(variant: dict | None) -> list[dict]:
    """Parse a beta GraphQL variant node into GRCh38 loci (best-effort; shape mirrors ensembl-mcp)."""
    if not variant:
        return []
    loc = ((variant.get("slice") or {}).get("location")) or {}
    chrom, start = loc.get("region_name"), loc.get("start")
    if chrom is None or start is None:
        return []
    ref = next(
        (
            a.get("reference_sequence")
            for a in variant.get("alleles", [])
            if (a.get("allele_type") or {}).get("value") == "reference"
        ),
        None,
    )
    if ref is None:
        return []
    alts = ",".join(
        a.get("reference_sequence", "")
        for a in variant.get("alleles", [])
        if (a.get("allele_type") or {}).get("value") != "reference" and a.get("reference_sequence")
    )
    if ref in ("", "-") or "-" in (alts or "").split(","):
        # A one-sided indel. REST's coordinate convention for it was probed (RM268) and this node's
        # was not — the beta endpoint answers no bare rsID today — so it is withheld rather than
        # anchored on a guess. `[]` hands the rsID to the REST leg, which anchors it.
        return []
    return [{"chrom": str(chrom), "start": int(start), "ref": str(ref), "alts": alts or None}]
