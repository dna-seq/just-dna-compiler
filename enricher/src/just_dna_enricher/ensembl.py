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
from dataclasses import dataclass, field

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.net import attempt_floor

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

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def resolve_rsid(self, rsid: str) -> tuple[list[dict], str | None]:
        """Return `([{chrom, start, ref, alts}, ...], source)` for a bare rsID, or `([], None)`.

        Tries V2 GraphQL, then falls back to V1 REST on a 5xx (or when V2 yields nothing). `source` is
        `ensembl-graphql` or `ensembl-rest` — recorded per row so the manifest can report provenance.
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
            loci = self._rest_rsid(rsid)
            return (loci, "ensembl-rest") if loci else ([], None)
        except (httpx.HTTPError, EnsemblError) as exc:
            logger.warning("V1 REST for %s failed: %s", rsid, exc)
            return [], None

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
        payload = resp.json()
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
    def _rest_rsid(self, rsid: str) -> list[dict]:
        resp = self._http().get(
            f"{self.settings.rest_endpoint}/variation/{self.settings.species}/{rsid}",
            params={"content-type": "application/json"},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return _loci_from_rest(resp.json())


def _loci_from_rest(payload: dict) -> list[dict]:
    """Parse Ensembl REST /variation mappings into GRCh38 loci, deterministically ordered."""
    loci: list[dict] = []
    for m in payload.get("mappings", []):
        if m.get("assembly_name") != _ASSEMBLY:
            continue
        alleles = str(m.get("allele_string", "")).split("/")
        ref = alleles[0] if alleles and alleles[0] else None
        alts = ",".join(alleles[1:]) if len(alleles) > 1 else None
        chrom = m.get("seq_region_name")
        start = m.get("start")
        if chrom is None or start is None or ref is None:
            continue
        loci.append({"chrom": str(chrom), "start": int(start), "ref": str(ref), "alts": alts})
    return sorted(loci, key=lambda locus: (locus["chrom"], locus["start"], locus["ref"]))


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
    return [{"chrom": str(chrom), "start": int(start), "ref": str(ref), "alts": alts or None}]
