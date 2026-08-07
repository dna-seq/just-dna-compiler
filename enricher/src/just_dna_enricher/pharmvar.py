"""Live PharmVar queries — star-allele definitions and allele function (0.5).

PharmVar is the naming authority for the CYP star alleles, and the only PGx source here that is not
part of the ClinPGx merger. It supplies two things this workspace has no other route to:
`haplotypes.csv` material (which variants define `*2`) and `allele_function.csv` material (what that
allele does), both with GRCh38 genomic coordinates and dbSNP ids already attached.

**Access changed under us and the failure mode is silent.** The API now requires a key, and every
endpoint returns the same `401 {"errorMessage": "API Key is invalid or missing"}` whether the key is
absent, malformed, or passed under the wrong parameter name — so a wrong header looks exactly like a
bad key. The parameter is **`Api-Key`**, a plain header with no `X-` prefix, documented per-endpoint
in the service's own OpenAPI document (`docs/pharmvar_api_docs.json`) rather than in a
`securityDefinitions` block, which is why it is easy to miss.

**The key is personal.** PharmVar's terms §2 make an account non-transferable, so the key is read
from the environment and never written anywhere: not into a module, a recorded fixture, a log line,
or a snapshot. `PharmVarClient` keeps it in the header only.

**Rate limit: 2 requests/second.** Low enough that per-allele fetching is hopeless and coarse
endpoints are the only sane shape — `/variants/gene/{symbol}` returns a gene's whole variant set in
one call. The unfiltered `/alleles` collection is ~25 MB and ignores a `geneSymbol` query parameter it
does not define, so it is never used here; `reference-sequence` filtering is applied server-side
instead.

Coordinates arrive as HGVS `g.` strings against several reference sequences at once — a transcript
(`NM_…:c.`), a gene region (`NG_…:g.`) and the chromosome (`NC_…:g.`). Only the `NC_` form is a
genomic coordinate, and it is **1-based**, which matches what this pipeline already stores (see the
resolution table): the instinctive conversion to 0-based would introduce an off-by-one.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from just_dna_enricher.net import PacingGate

logger = logging.getLogger(__name__)

DEFAULT_PHARMVAR_ENDPOINT = "https://www.pharmvar.org/api-service"
# The documented header name. Not `X-API-KEY` — that returns the same 401 as no key at all.
API_KEY_HEADER = "Api-Key"
API_KEY_ENV = "PHARMVAR_API_KEY"
# 2 requests/second, so 0.5s between them. Injectable clock, as everywhere in this package.
PHARMVAR_MIN_INTERVAL = 0.5
# The `dataset` FACT: which release the definitions came from. PharmVar publishes a version per gene
# rather than one global release id, so the pass stamps what the payload reports.
PHARMVAR_SOURCE = "pharmvar"

# `NC_000010.11:g.94781859G>A` → chromosome accession, 1-based position, ref, alt. Only the NC_ form
# is genomic; NM_/NG_ are transcript- and gene-relative and are deliberately not parsed as positions.
_NC_HGVS = re.compile(
    r"^(?P<accession>NC_(?P<num>\d+)\.\d+):g\.(?P<pos>\d+)(?P<ref>[ACGT]+)>(?P<alt>[ACGT]+)$"
)


class PharmVarError(RuntimeError):
    """A PharmVar request failed in a way the caller must see (auth, or a broken query)."""


def chrom_from_accession(num: str) -> str | None:
    """`NC_000010` → `10`, `NC_000023` → `X`. None for anything off the primary assembly.

    RefSeq numbers the chromosomes 1–22 then X (23), Y (24), MT (12920 as a special case). Returning
    None rather than guessing keeps an unplaced contig out of the coordinate space entirely.
    """
    index = int(num)
    if 1 <= index <= 22:
        return str(index)
    return {23: "X", 24: "Y"}.get(index)


@dataclass
class PharmVarVariant:
    """One defining variant of a star allele, at a genomic coordinate."""

    rsid: str | None
    chrom: str | None
    start: int | None
    ref: str | None
    alt: str | None

    @property
    def usable(self) -> bool:
        """Whether this carries a genomic coordinate we can key on."""
        return self.chrom is not None and self.start is not None


@dataclass
class PharmVarAllele:
    """One star allele: its identity, its function, and the variants that define it."""

    gene: str
    allele: str
    function: str | None = None
    activity_value: float | None = None
    evidence_level: str | None = None
    is_core: bool = True
    variants: list[PharmVarVariant] = field(default_factory=list)


def parse_genomic_variant(payload: dict[str, Any]) -> PharmVarVariant:
    """One `variants[]` entry → a coordinate, when it names one.

    A variant appears several times per allele, once per reference sequence. Only the `NC_` genomic
    row yields a position; the transcript rows still carry the rsID, so the caller merges by rsID
    rather than discarding them.
    """
    rsid = payload.get("rsId") or None
    match = _NC_HGVS.match(str(payload.get("hgvs") or payload.get("position") or ""))
    if match is None:
        return PharmVarVariant(rsid=rsid, chrom=None, start=None, ref=None, alt=None)
    return PharmVarVariant(
        rsid=rsid,
        chrom=chrom_from_accession(match.group("num")),
        # 1-based, matching Ensembl and what resolution.csv stores. Do NOT subtract one.
        start=int(match.group("pos")),
        ref=match.group("ref"),
        alt=match.group("alt"),
    )


def _merge_variants(entries: list[dict[str, Any]]) -> list[PharmVarVariant]:
    """Collapse an allele's per-reference-sequence rows to one entry per variant.

    Keyed by rsID where there is one, else by the coordinate; a genomic row supersedes a
    transcript-only row for the same variant, so the merged entry has both the id and the position.
    First-occurrence order is preserved — emitted order feeds `artifact.digest` (Principle 7).
    """
    merged: dict[str, PharmVarVariant] = {}
    for entry in entries:
        parsed = parse_genomic_variant(entry)
        key = parsed.rsid or f"{parsed.chrom}:{parsed.start}:{parsed.ref}"
        existing = merged.get(key)
        if existing is None or not existing.usable and parsed.usable:
            merged[key] = parsed
    return list(merged.values())


def parse_allele(payload: dict[str, Any]) -> PharmVarAllele:
    """One `/alleles` entry → a `PharmVarAllele`.

    `activityScore` is absent for most alleles and non-numeric for some ("n/a"), so it is parsed
    defensively rather than trusted — a non-numeric score becomes None instead of failing the allele.
    """
    raw_score = payload.get("activityScore")
    try:
        activity = float(raw_score) if raw_score not in (None, "", "n/a") else None
    except (TypeError, ValueError):
        activity = None
    return PharmVarAllele(
        gene=str(payload.get("geneSymbol") or ""),
        allele=str(payload.get("alleleName") or ""),
        function=payload.get("function") or None,
        activity_value=activity,
        evidence_level=payload.get("evidenceLevel") or None,
        is_core=(payload.get("alleleType") or "").lower() != "sub",
        variants=_merge_variants(list(payload.get("variants") or [])),
    )


class PharmVarClient:
    """Paced PharmVar REST client. The API key comes from the environment and is never persisted."""

    def __init__(
        self,
        endpoint: str = DEFAULT_PHARMVAR_ENDPOINT,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        gate: PacingGate | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._api_key = api_key or os.environ.get(API_KEY_ENV)
        self._client = client or httpx.Client(timeout=timeout)
        self._owned = client is None
        self._gate = gate or PacingGate(interval=PHARMVAR_MIN_INTERVAL)

    @property
    def configured(self) -> bool:
        """Whether a key is available. Absent is a *skip*, not an error — the pass degrades."""
        return bool(self._api_key)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        # Pace before retry, as in gnomad.py: retrying spends the same budget that caused the throttle.
        self._gate.wait()
        response = self._client.get(
            f"{self.endpoint}/{path.lstrip('/')}",
            params=params or {},
            headers={API_KEY_HEADER: self._api_key or ""},
        )
        if response.status_code == 401:
            # Do not retry an auth failure, and never echo the key. The message names the two causes
            # the service cannot distinguish, because its 401 is identical for both.
            raise PharmVarError(
                "PharmVar rejected the API key (HTTP 401). The service returns the same response for "
                f"an absent, malformed and unrecognised key; check that {API_KEY_ENV} is set to a "
                f"verified key and that it is sent as the {API_KEY_HEADER!r} header."
            )
        response.raise_for_status()
        return response.json()

    def alleles_for_gene(self, gene: str, *, include_sub_alleles: bool = False) -> list[PharmVarAllele]:
        """Every allele PharmVar defines for one gene, with its defining variants.

        Sub-alleles (`*2.001`) are excluded by default: the core star is the identity this workspace
        keys on (`AlleleFunctionRow.allele`), and including them multiplies the table roughly threefold
        without changing any lookup.
        """
        payload = self._get(
            f"genes/{gene}",
            params={"exclude-sub-alleles": "true"} if not include_sub_alleles else {},
        )
        raw = payload.get("alleles") if isinstance(payload, dict) else payload
        alleles = [parse_allele(entry) for entry in (raw or [])]
        if not include_sub_alleles:
            alleles = [a for a in alleles if a.is_core]
        return alleles
