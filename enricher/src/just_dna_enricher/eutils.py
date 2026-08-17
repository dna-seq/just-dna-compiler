"""NCBI E-utilities client — batched, paced, and honest about the shape of a missing record.

Two callers with nothing else in common share this: the literature pass asks `db=pubmed` whether a
cited PMID exists, and the identifier-hygiene pass asks `db=snp` whether an rsID is live, merged or
gone. Both want the same three things — many ids per request, a rate limit obeyed, and a per-record
failure that does not sink its batch — so the transport lives here and the interpretation lives with
each caller.

**The per-record error shape is the interesting part.** Unlike the GraphQL services, eutils reports a
missing record *inside* the result, as a normal-looking entry carrying an `error` key:

    {"uid": "999999999", "error": "cannot get document summary"}

That is a clean, documented signal, and it is why existence-checking works at all. It also means a
parser that only looks for HTTP failures would read "this id does not exist" as "this id is fine".

**Rate limit.** NCBI allows 3 requests/second without an API key and 10 with one, so the gate is
`1/3 s` by default and tightens to `1/10 s` when `NCBI_API_KEY` is present in the environment. NCBI
also asks callers to identify themselves with `tool` and `email`; both are sent when known. `email` is
read from the environment and simply omitted when unset — inventing a plausible-looking address would
be worse than sending none, because it would misattribute the traffic to someone.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential_jitter,
)

from just_dna_enricher.locations import load_env
from just_dna_enricher.net import PacingGate, attempt_floor, batched, dedupe

logger = logging.getLogger(__name__)

DEFAULT_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_TOOL = "just-dna-enricher"

# NCBI's published budgets. The keyed rate is only claimed when a key is actually present.
_UNKEYED_INTERVAL = 1.0 / 3.0
_KEYED_INTERVAL = 1.0 / 10.0

#: The message eutils puts in a record's `error` field when the uid has no document summary. Matched
#: as a substring rather than compared exactly, because the surrounding wording has drifted before.
NO_SUMMARY = "cannot get document summary"


class EutilsError(RuntimeError):
    """An eutils request failed outright (transport, HTTP status, or an unparseable body)."""


class EutilsRateLimitedError(EutilsError):
    """NCBI answered HTTP 429. Retried with backoff; the pacing gate should normally prevent it."""


@dataclass
class EutilsSettings:
    base_url: str = DEFAULT_EUTILS_BASE
    tool: str = DEFAULT_TOOL
    email: str | None = None
    api_key: str | None = None
    #: ids per request. NCBI accepts a few hundred for esummary; 200 is comfortably inside that and
    #: keeps a failed request from costing much.
    batch_size: int = 200
    #: Seconds between requests. Left None to be derived from whether an API key is available.
    min_request_interval: float | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        # `.env` is where a developer actually keeps the NCBI key, and until 0.6.1 it only reached
        # `os.environ` as a side effect of some *other* call resolving a cache path (RM100).
        # `@credential-where-read`: load it where it is read, so the credential path does not depend
        # on call order. `PharmVarClient` carries the same call with a comment describing the same
        # failure -- it was fixed there and not here. The live effect was silent: with a `.env`-only
        # key the rate gate below stayed at 1 request / 3 s instead of 10 / s, three times slower,
        # for a reason nothing reported.
        #
        # `override=False`, so a real environment variable and a test's neutralizing `""` both win.
        load_env()
        if self.api_key is None:
            self.api_key = os.environ.get("NCBI_API_KEY") or None
        if self.email is None:
            self.email = os.environ.get("JUST_DNA_CONTACT_EMAIL") or None
        if self.min_request_interval is None:
            self.min_request_interval = _KEYED_INTERVAL if self.api_key else _UNKEYED_INTERVAL

    def identity_params(self) -> dict[str, str]:
        """`tool`/`email`/`api_key`, omitting whatever is genuinely unknown."""
        params = {"tool": self.tool}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params


@dataclass
class EutilsClient:
    """Batched, paced esummary access. Reused across a pass, so one gate covers every request."""

    settings: EutilsSettings = field(default_factory=EutilsSettings)
    gate: PacingGate | None = None
    _client: httpx.Client | None = None

    def __post_init__(self) -> None:
        if self.gate is None:
            assert self.settings.min_request_interval is not None
            self.gate = PacingGate(self.settings.min_request_interval)

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.timeout, follow_redirects=True)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "EutilsClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @retry(
        stop=attempt_floor(4),
        wait=wait_exponential_jitter(initial=1.0, max=20.0),
        retry=retry_if_exception_type(
            (
                EutilsRateLimitedError,
                httpx.TransportError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
            )
        ),
        reraise=True,
    )
    def _request(self, path: str, params: dict[str, str]) -> dict:
        """The retrying half, kept separate so the translation below sits *outside* the retry.

        Same split as `cpic._request` and `gnomad._request`, and for the same reason: the predicate
        above tests `httpx.HTTPStatusError`, so translating in here would make every failure a
        first-and-final attempt.

        A 429 is retried on top of the gate — the gate is what should normally prevent it, so one
        getting through means another process shares this IP or NCBI is stricter than advertised, and
        backing off is the only correct response. That branch stays **inside** this method and
        **before** `raise_for_status()`, since `EutilsRateLimitedError` is what the predicate matches.
        """
        assert self.gate is not None
        self.gate.wait()
        url = f"{self.settings.base_url.rstrip('/')}/{path}"
        response = self._http().get(url, params={**self.settings.identity_params(), **params})
        if response.status_code == 429:
            raise EutilsRateLimitedError("NCBI returned HTTP 429 (rate limited)")
        response.raise_for_status()
        return response.json()

    def _get(self, path: str, params: dict[str, str]) -> dict:
        """Every way this client can fail, spelled as `EutilsError` (RM97).

        `@client-exception-contract`: retry, then translate, **both legs**. Only one leg was
        translated before — `raise_for_status()` sat between the two `try` blocks, so a body that
        would not parse became an `EutilsError` while a 5xx did not, and `HTTPStatusError` was in no
        retry list either. The transport leg was re-raised bare for the decorator and escaped raw
        once the attempts ran out.

        The live cost was the sharper of the two in this repair: `enrich()`'s `check_rsids` call has
        no handler at all, and `identifiers.check_rsids` only wraps a `finally: eutils.close()`, so a
        persistent dbSNP 5xx aborted the whole run with an httpx traceback the CLI cannot render —
        after every other pass had finished and before `resolution.csv` was written.
        """
        try:
            return self._request(path, params)
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            raise EutilsError(f"eutils request failed: {exc}") from exc
        except ValueError as exc:
            raise EutilsError(f"eutils returned a non-JSON body for {path}: {exc}") from exc

    def esummary(self, db: str, ids: list[str]) -> dict[str, dict[str, Any]]:
        """`uid -> record` across as many batches as `ids` needs, in first-occurrence order.

        Records carrying an `error` key are **kept, not dropped**: "NCBI has no summary for this uid"
        is the answer both callers came for, and discarding it would turn a detectable absence into an
        indistinguishable silence. Use `is_missing` to read it.
        """
        wanted = dedupe(i for i in ids if i)
        out: dict[str, dict[str, Any]] = {}
        for batch in batched(wanted, self.settings.batch_size):
            payload = self._get(
                "esummary.fcgi", {"db": db, "id": ",".join(batch), "retmode": "json"}
            )
            result = payload.get("result") or {}
            for uid in batch:
                record = result.get(uid)
                if isinstance(record, dict):
                    out[uid] = record
                else:
                    # Absent from `result` entirely — rarer than the `error` record, and it means the
                    # same thing to a caller, so it is normalized into the same shape rather than
                    # silently omitted.
                    out[uid] = {"uid": uid, "error": NO_SUMMARY}
        return out


def is_missing(record: dict[str, Any]) -> bool:
    """Whether an esummary record is NCBI's "no such document" answer rather than real data."""
    error = record.get("error")
    return bool(error) and NO_SUMMARY in str(error).lower()
