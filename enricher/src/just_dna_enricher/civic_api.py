"""CIViC's GraphQL API — the one surface that publishes evidence the dated files cannot carry (RM160).

`civic build` reads a dated bulk release, and RM169 widened it as far as a dated file goes: the TSV
pair is `accepted`-only, and `<date>-civic_accepted_and_submitted.vcf` carries the submitted half
beside it, pinnable and byte-reproducible. **A VCF record needs a POS.** So an evidence item attached
to a variant CIViC publishes no GRCh37 coordinate for is published on exactly one surface — this one.
That is the whole of what this client is for, and it is a narrow claim: nothing else about the API is
richer than the files, and the three bulk summaries the builder does not read are not evidence tables.

**Why it is not in the builder, and why that is not an omission.** `civic build` is byte-reproducible
because its input is a pinned dated file pair, and `civic reproduce` proves it by building twice. An
API read has nothing to pin. RM160 was decided as shape 3 — read `SUBMITTED` at enrich time, where
network reads already live and reproducibility is never claimed — over the two shapes that would have
moved it into the build: hashing a capture as an input (reproducible against the capture rather than
against CIViC) and a second API-built parquet. **The read is per variant by construction**: the
`evidenceItems` query takes one `variantId`, so a corpus-wide read would be one request per variant of
the whole database. Batching it into `civic build` is the first repair anyone proposes and it is
exactly the bargain shape 3 refused.

**CC0, so `check_declared_use` does not gate this** (`@acquisition-gate-is-not-a-read-gate`): CIViC
permits sale and redistribution on every axis, so a use gate here would permit every call
unconditionally, and a flag feeding a gate that never gates is a flag that does nothing. `--offline`
does gate it, and it is a real refusal rather than an empty answer — a variant nobody asked about and
a variant the API says has nothing more are different facts (`@unreachable-not-absent`).

**Three outcomes, never two.** Items returned; the API answered and holds none (an empty list); and
the question could not be put at all (`CivicApiUnavailable`). The middle one is a return value and the
last one is an exception, the same split `litvar` draws, because a caller that flattens them turns an
outage into a permanent negative about a variant.

**Statuses are CIViC's own words, lower-cased and not otherwise touched.** The API serves `ACCEPTED`,
`SUBMITTED` and `REJECTED`; `civic_vcf` writes the first two lower-cased, and one vocabulary spelled
two ways by two surfaces of one source gets one normalizer (`@one-normalizer-two-spellings`), never a
translation into a house grade. A status outside the three raises rather than defaulting: the file
reader refuses the same way, because every count keyed on the vocabulary is wrong the moment a member
is silently absorbed (`@lookup-with-a-default-hides-a-new-member`).

**The listing paginates and states its own total.** `evidenceItems` served 37 items for variant 844 on
2026-09-03 in pages, and a reader taking the first page would have reported a variant with 34 hidden
citations as having four. `totalCount` sits in the same payload as the nodes, so the two are compared
and a short read warns rather than passing silently — the check is in the response, exactly as
LitVar's `pmids_count` is.
"""

import json
import logging
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception_type, wait_exponential_jitter

from just_dna_enricher.net import PacingGate, attempt_floor

logger = logging.getLogger(__name__)

#: The endpoint. One URL, one POST body; there is no REST route that answers this question.
CIVIC_API_URL = "https://civicdb.org/api/graphql"

#: The source name every row and record written off this client carries. The **same** name the
#: snapshot lane uses, deliberately: a route is not a source (`@source-vs-authority`), and `civic_api`
#: as a `sources.csv` source would publish a transport as a licensed body. Which surface answered
#: lives in `dataset` and in the layer, where the rest of this tier already puts it.
CIVIC_SOURCE = "civic"

#: What the API calls a curation state, lower-cased to the spelling `civic_vcf` already writes. Closed
#: (Principle 6), and wider than the file's pair by exactly one member: a VCF holding accepted and
#: submitted evidence has no reason to carry a rejected item, and this surface does.
CIVIC_API_STATUSES: frozenset[str] = frozenset({"accepted", "submitted", "rejected"})

#: The instrument name that travels with a status into `StudyRow.confidence_unit`. A magnitude has to
#: name the ladder it is on, and this is CIViC's ladder rather than a house grade.
CIVIC_STATUS_UNIT = "civic_evidence_status"

#: CIViC's own word for a PubMed-sourced citation. Every other `sourceType` (ASCO and ASH abstracts,
#: for two) carries a `citationId` that is **not** a PMID, and reading one as a PubMed id is
#: `@pmid-vs-pmcid` with a different pair of registries — so nothing here treats a non-PubMed source
#: as a citation this format can key on.
CIVIC_PUBMED_SOURCE_TYPE = "PUBMED"

#: How many evidence items to ask for per page. CIViC publishes no page-size limit; 50 is what the
#: probe ran at and it keeps the 37-item variant to one request.
_PAGE_SIZE = 50

#: A courtesy interval, not a published budget — CIViC states no rate limit anywhere this workspace
#: could find, so this is the same third of a second the NCBI clients in this tier pace at, chosen as
#: a floor rather than read off a number the source published.
_REQUEST_INTERVAL = 0.34

#: The one query. `status: ALL` is the whole point: the default is `NON_REJECTED` and the bulk files
#: are `accepted`-only, so anything narrower here would be a second copy of a basis the dated release
#: already carries. `evidenceRating` and `molecularProfile` ride along because they cost nothing extra
#: on a request that is already being made and a caller reporting a recovered citation needs to say
#: which profile it belongs to (RM174's column, one surface over).
_EVIDENCE_QUERY = """
query($id: Int!, $after: String, $n: Int!) {
  evidenceItems(variantId: $id, status: ALL, first: $n, after: $after) {
    totalCount
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      status
      evidenceType
      evidenceDirection
      evidenceLevel
      evidenceRating
      significance
      variantOrigin
      source { id citationId sourceType title citation publicationYear }
      molecularProfile { id name }
    }
  }
}
"""


class CivicApiError(RuntimeError):
    """CIViC could not be consulted in a way the caller must handle."""


class CivicApiUnavailable(CivicApiError):
    """The service was not reachable, so the question was never put.

    A subclass rather than a second exception, so every existing `except CivicApiError` still fires
    while a caller that must separate *CIViC has nothing here* from *CIViC never answered* can do it
    by type rather than by reading `__cause__` (`@client-exception-contract`). Only this one means
    nobody was asked — a payload this client cannot read is a `CivicApiError`, because the service did
    answer and the defect is in the reading.
    """


@dataclass(frozen=True)
class CivicEvidenceItem:
    """One evidence item as this lane needs to quote it.

    Every field is what CIViC published, coerced and never converted. `status` is lower-cased and
    nothing else; `citation_id` is echoed verbatim and `pmid` withholds unless the source really is a
    PubMed record.
    """

    evidence_id: int
    variant_id: int
    status: str
    evidence_type: str | None = None
    evidence_direction: str | None = None
    evidence_level: str | None = None
    evidence_rating: int | None = None
    significance: str | None = None
    variant_origin: str | None = None
    source_id: int | None = None
    source_type: str | None = None
    citation_id: str | None = None
    title: str | None = None
    citation: str | None = None
    publication_year: int | None = None
    molecular_profile_id: int | None = None
    molecular_profile_name: str | None = None

    @property
    def pmid(self) -> str | None:
        """The PubMed id, or `None` where this item's source is not a PubMed record.

        Withheld rather than guessed: an ASCO or ASH abstract carries a `citationId` that is a real
        identifier in a different namespace, and writing one into a `pmid` column would state a
        PubMed record that does not exist. A `citationId` that is not digits is refused for the same
        reason — CIViC's PubMed ids are bare numbers.
        """
        if (self.source_type or "").upper() != CIVIC_PUBMED_SOURCE_TYPE:
            return None
        token = (self.citation_id or "").strip()
        return token if token.isdigit() else None

    def restate(self) -> str:
        """`EID 9969 (submitted, PMID 12202531)` — what a warning line puts in front of an author."""
        parts = [self.status]
        if self.pmid:
            parts.append(f"PMID {self.pmid}")
        return f"EID {self.evidence_id} ({', '.join(parts)})"


def normalize_status(raw: object, evidence_id: object) -> str:
    """CIViC's `ACCEPTED`/`SUBMITTED`/`REJECTED` as this workspace spells it, or this tier's error.

    Case is the only thing that moves. A member outside the three raises rather than being absorbed
    into a default, because the vocabulary is the instrument every count in this lane is keyed on —
    the file reader refuses an unknown status for the identical reason, and the two must not disagree
    about what a status is.
    """
    token = str(raw or "").strip().lower()
    if token not in CIVIC_API_STATUSES:
        raise CivicApiError(
            f"CIViC evidence {evidence_id} carries status {raw!r}, which is not one of "
            f"{sorted(CIVIC_API_STATUSES)}. The status vocabulary moved and every count keyed on it "
            f"is now wrong (`@lookup-with-a-default-hides-a-new-member`)."
        )
    return token


class CivicApiClient:
    """The one CIViC GraphQL call this lane needs, paced, retried, paginated and translated.

    Hold one per run: the per-variant answers are cached on the instance, so a variant reached from
    two authored tables is one request, and the pacing gate is shared across every call the run makes
    rather than reset per question (`@shared-pacing-gate`).

    `offline=True` is a **refusal**, not an empty answer: every call raises `CivicApiUnavailable`
    before any transport is touched. A caller that wants "nobody asked" recorded gets it from the
    exception; a caller that reads an empty list as "CIViC has nothing" would otherwise write a
    permanent negative out of a run that had no egress.
    """

    def __init__(
        self,
        *,
        url: str = CIVIC_API_URL,
        client: httpx.Client | None = None,
        gate: PacingGate | None = None,
        offline: bool = False,
    ) -> None:
        self._url = url
        self._client = client
        self._gate = gate or PacingGate(_REQUEST_INTERVAL)
        self._offline = offline
        self._items: dict[int, list[CivicEvidenceItem]] = {}

    @property
    def offline(self) -> bool:
        """Whether this client will refuse rather than fetch. Read by a caller writing its skip."""
        return self._offline

    def evidence_items(self, variant_id: int) -> list[CivicEvidenceItem]:
        """Every evidence item CIViC holds for one variant, at any curation status.

        An empty list is an **answer** — CIViC was asked and holds nothing for this variant — and a
        `CivicApiUnavailable` is the third outcome, the question that was never put. The caller must
        keep them apart; that is the whole reason the absence is a value and the failure is a type.

        One variant per call by construction, which is why this lane lives at enrich time: the query
        takes a single `variantId`, so there is no shape of it that a snapshot builder could pin.
        """
        if variant_id not in self._items:
            self._items[variant_id] = self._fetch_all(variant_id)
        return list(self._items[variant_id])

    # ── transport ───────────────────────────────────────────────────────────────────────────────

    def _fetch_all(self, variant_id: int) -> list[CivicEvidenceItem]:
        """Every page of one variant's evidence, with the payload's own total checked against it."""
        items: list[CivicEvidenceItem] = []
        after: str | None = None
        stated: int | None = None
        while True:
            payload = self._post(
                {"id": int(variant_id), "after": after, "n": _PAGE_SIZE}
            )
            listing = payload.get("evidenceItems")
            if not isinstance(listing, dict):
                raise CivicApiError(
                    f"CIViC answered for variant {variant_id} without an `evidenceItems` block, so "
                    f"there is nothing to read"
                )
            total = listing.get("totalCount")
            if isinstance(total, int):
                stated = total
            for node in listing.get("nodes") or []:
                if isinstance(node, dict):
                    items.append(_parse_item(node, variant_id))
            page = listing.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
            if not cursor:
                # `hasNextPage` with no cursor is a payload this client cannot page through. Raising
                # keeps a short read from being reported as the variant's whole evidence.
                raise CivicApiError(
                    f"CIViC says variant {variant_id} has another page of evidence and gave no "
                    f"cursor to reach it"
                )
            after = str(cursor)
        if stated is not None and stated != len(items):
            # The response carries its own denominator, so a truncated read is checkable without a
            # second request (`@dont-discard-computed`). A warning rather than a refusal: the items
            # really were served, and discarding them would turn a partial answer into no answer.
            logger.warning(
                "CIViC says variant %s has %d evidence item(s) and served %d — the citations "
                "recovered for it are the served set, and it is short of what the API claims.",
                variant_id, stated, len(items),
            )
        return items

    def _post(self, variables: dict) -> dict:
        """The `data` block of one GraphQL response, with every failure translated at this boundary.

        A GraphQL `errors` block is a `CivicApiError` and **not** the unavailability subclass: the
        service answered, and what failed is this client's query or a schema that moved under it. Only
        a transport failure or an HTTP status means the question was never put.
        """
        if self._offline:
            raise CivicApiUnavailable(
                "--offline, so CIViC's API was not asked. A variant nobody asked about is not a "
                "variant the source has nothing for."
            )
        try:
            response = self._request(variables)
        except httpx.HTTPStatusError as exc:
            raise CivicApiUnavailable(
                f"CIViC answered {exc.response.status_code} for the evidence query"
            ) from exc
        except httpx.HTTPError as exc:
            raise CivicApiUnavailable(f"CIViC could not be reached ({exc})") from exc
        try:
            body = json.loads(response.text)
        except ValueError as exc:
            # A 200 carrying a maintenance page or a truncated body is a real thing a Rails app
            # serves, and `json.JSONDecodeError` is not this tier's type — the identical leak
            # `litvar._read_json` exists to close.
            raise CivicApiError(f"CIViC answered with something that is not JSON ({exc})") from exc
        if not isinstance(body, dict):
            raise CivicApiError("expected a JSON object from CIViC")
        errors = body.get("errors")
        if errors:
            raise CivicApiError(f"CIViC refused the evidence query: {json.dumps(errors)[:400]}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise CivicApiError("CIViC answered with no `data` block")
        return data

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        wait=wait_exponential_jitter(initial=0.5, max=8),
        stop=attempt_floor(3),
        reraise=True,
    )
    def _request(self, variables: dict) -> httpx.Response:
        # The gate is the first statement, so a retried attempt spends a slot of the budget instead
        # of bursting past it (`@shared-pacing-gate`).
        self._gate.wait()
        client = self._client or httpx
        response = client.post(
            self._url,
            json={"query": _EVIDENCE_QUERY, "variables": variables},
            timeout=90.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response


def _parse_item(node: dict, variant_id: int) -> CivicEvidenceItem:
    """One `evidenceItems.nodes` record → an item, or this tier's error when it is not one.

    Every field is coerced rather than trusted: a record with no `id` used to be the shape that
    escapes a per-variant handler as a bare `KeyError`, and a payload this client cannot read is a
    defect in the response rather than in one citation.
    """
    evidence_id = node.get("id")
    if evidence_id is None:
        raise CivicApiError("a CIViC evidence record carries no `id`, so it names no item")
    source = node.get("source") or {}
    profile = node.get("molecularProfile") or {}
    return CivicEvidenceItem(
        evidence_id=int(evidence_id),
        variant_id=int(variant_id),
        status=normalize_status(node.get("status"), evidence_id),
        evidence_type=_text(node.get("evidenceType")),
        evidence_direction=_text(node.get("evidenceDirection")),
        evidence_level=_text(node.get("evidenceLevel")),
        evidence_rating=_number(node.get("evidenceRating")),
        significance=_text(node.get("significance")),
        variant_origin=_text(node.get("variantOrigin")),
        source_id=_number(source.get("id")),
        source_type=_text(source.get("sourceType")),
        citation_id=_text(source.get("citationId")),
        title=_text(source.get("title")),
        citation=_text(source.get("citation")),
        publication_year=_number(source.get("publicationYear")),
        molecular_profile_id=_number(profile.get("id")),
        molecular_profile_name=_text(profile.get("name")),
    )


def _text(value: object) -> str | None:
    """A payload cell as a non-empty string, or `None`. Never the string `"None"`."""
    if value is None:
        return None
    token = str(value).strip()
    return token or None


def _number(value: object) -> int | None:
    """A payload cell as an integer, or `None` where it is not one.

    `bool` is excluded because it is an `int` in Python and a `True` reaching a rating would render
    as `1` — a magnitude invented out of a flag.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    token = str(value).strip()
    return int(token) if token.isdigit() else None
