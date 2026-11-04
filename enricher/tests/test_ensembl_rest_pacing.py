"""The live Ensembl REST rung is paced under Ensembl's published budget and honours `Retry-After`.

Ensembl publishes 15 requests/second per IP and about 55,000 per rolling hour (`x-ratelimit-limit 55000`,
`x-ratelimit-period 3600` on a 2026-11-04 `/info/ping`), and answers a request over either with a 429 that
says in `Retry-After` how long to wait. Until 2026-11-04 the REST rung had no `PacingGate` and retried a
429 on tenacity's own backoff, so a throttled run asked again before the server said it could, and a run
past the hourly budget asked again for every remaining rsID.

Every request here goes through `httpx.MockTransport`; the gate runs on a fake clock and a recording
sleeper, so nothing waits for real and every wait is observed.
"""

import email.utils
import os

import httpx
import pytest
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.net import RETRY_AFTER_CEILING, PacingGate, retry_after_seconds

_MAPPING = {"seq_region_name": "1", "start": 11856377, "allele_string": "G/A", "assembly_name": "GRCh38"}
_LOCI = [{"chrom": "1", "start": 11856377, "ref": "G", "alts": "A"}]

#: Ensembl's published per-second budget (domain constant).
ENSEMBL_REQUESTS_PER_SECOND = 15


class _Clock:
    """A monotonic clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _status_error(status: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://rest.ensembl.org/variation/human/rs1")
    response = httpx.Response(status, headers=headers or {}, request=request)
    return httpx.HTTPStatusError("throttled", request=request, response=response)


def test_retry_after_reads_seconds_and_an_http_date_and_nothing_else() -> None:
    assert retry_after_seconds(_status_error(429, {"Retry-After": "2"})) == 2.0
    # Ensembl sends a fractional delta (its docs show `Retry-After: 40.0`).
    assert retry_after_seconds(_status_error(429, {"Retry-After": "0.5"})) == 0.5
    when = email.utils.formatdate(1_000_030, usegmt=True)
    assert retry_after_seconds(_status_error(429, {"Retry-After": when}), now=lambda: 1_000_000) == 30.0
    # A date already past asks for no wait, never a negative one.
    assert retry_after_seconds(_status_error(429, {"Retry-After": when}), now=lambda: 1_000_100) == 0.0
    # RFC 9110 allows it on a 503 too.
    assert retry_after_seconds(_status_error(503, {"Retry-After": "5"})) == 5.0
    # Unknown, not zero: no header, an unreadable one, a status a retry cannot change, not an HTTP error.
    assert retry_after_seconds(_status_error(429)) is None
    assert retry_after_seconds(_status_error(429, {"Retry-After": "soon"})) is None
    assert retry_after_seconds(_status_error(429, {"Retry-After": "nan"})) is None
    assert retry_after_seconds(_status_error(404, {"Retry-After": "5"})) is None
    assert retry_after_seconds(httpx.ConnectError("down")) is None
    assert retry_after_seconds(None) is None


def _resolver(handler, clock: _Clock) -> EnsemblResolver:
    resolver = EnsemblResolver(gate=PacingGate(interval=0.1, clock=clock, sleeper=clock.sleep))
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    return resolver


def test_the_default_gate_keeps_inside_ensembls_published_budget() -> None:
    resolver = EnsemblResolver()
    assert resolver.gate is not None
    assert resolver.gate.interval >= 1 / ENSEMBL_REQUESTS_PER_SECOND


def test_every_rest_attempt_waits_on_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)  # tenacity's backoff
    clock = _Clock()
    requests: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(clock.now)
        if len(requests) == 2:
            return httpx.Response(503, text="No server is available to handle this request.")
        return httpx.Response(200, json={"mappings": [_MAPPING]})

    resolver = _resolver(handler, clock)
    assert resolver.resolve_rsid("rs1801133") == (_LOCI, "ensembl-rest")
    assert resolver.resolve_rsid("rs1801133") == (_LOCI, "ensembl-rest")  # a 503, retried, then 200
    # One admission per upstream attempt, the retry included, and no two requests closer than the gate.
    assert resolver.gate is not None and resolver.gate.spent == len(requests) == 3
    assert all(later - earlier >= 0.1 for earlier, later in zip(requests, requests[1:], strict=False))


def test_a_429_is_retried_after_the_wait_it_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)  # tenacity's wait, recorded rather than slept
    clock = _Clock()
    answers = iter(
        [
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json={"mappings": [_MAPPING]}),
        ]
    )
    resolver = _resolver(lambda _request: next(answers), clock)
    assert resolver.resolve_rsid("rs1801133") == (_LOCI, "ensembl-rest")
    # Tenacity's own backoff starts at 0.5 s; the server asked for 2, so the retry waited at least that.
    assert len(waits) == 1 and waits[0] >= 2.0


def test_a_wait_past_the_ceiling_is_not_slept_and_nothing_is_asked_until_it_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensembl's hourly budget answers with the time to its reset, which can be most of an hour. That
    request is not retried, the rsID is not asked (could-not-ask, never "no record"), and neither is any
    other until the time the server named — then the resolver asks again."""
    waits: list[float] = []
    monkeypatch.setattr("time.sleep", waits.append)
    clock = _Clock()
    held = RETRY_AFTER_CEILING * 10
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path.rsplit("/", 1)[-1])
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": str(held)})
        return httpx.Response(200, json={"mappings": [_MAPPING]})

    resolver = _resolver(handler, clock)
    assert resolver.resolve_rsid("rs1") == (None, None)
    assert resolver.resolve_rsid_rest("rs2") == (None, None)
    assert requests == ["rs1"] and waits == []
    clock.now += held
    assert resolver.resolve_rsid("rs3") == (_LOCI, "ensembl-rest")
    assert requests == ["rs1", "rs3"]


@pytest.mark.skipif(os.environ.get("JUST_DNA_NETWORK_TESTS") != "1", reason="set JUST_DNA_NETWORK_TESTS=1")
def test_live_rest_is_asked_through_its_gate() -> None:
    resolver = EnsemblResolver()
    try:
        loci, source = resolver.resolve_rsid_rest("rs1801133")
    finally:
        resolver.close()
    assert source == "ensembl-rest" and loci == _LOCI
    assert resolver.gate is not None and resolver.gate.spent >= 1
