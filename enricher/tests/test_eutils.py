"""The shared eutils transport: rate budget, batching, and the per-record absence signal.

The pacing gate is exercised on a fake clock (no test really sleeps), and the "missing record" shape
is the one NCBI actually returns — a normal-looking entry carrying an `error` key — because that is
the whole basis of the existence checks built on top of this.
"""

import httpx
import pytest
from just_dna_enricher.eutils import (
    NO_SUMMARY,
    EutilsClient,
    EutilsError,
    EutilsRateLimitedError,
    EutilsSettings,
    is_missing,
)
from just_dna_enricher.net import PacingGate


class _Recorder:
    """A MockTransport that records every request and replays scripted JSON bodies."""

    def __init__(self, bodies: list[dict] | dict, status: int = 200) -> None:
        self.bodies = bodies if isinstance(bodies, list) else [bodies]
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = self.bodies[min(len(self.requests) - 1, len(self.bodies) - 1)]
        return httpx.Response(self.status, json=body)


def _client(recorder: _Recorder, **settings) -> EutilsClient:
    client = EutilsClient(settings=EutilsSettings(**settings))
    client._client = httpx.Client(transport=httpx.MockTransport(recorder))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def _summary(**uids) -> dict:
    return {"result": {"uids": list(uids), **uids}}


# ── the rate budget, on a fake clock ────────────────────────────────────────────────────────────


def test_the_gate_honours_the_interval_without_really_sleeping() -> None:
    now = [0.0]
    slept: list[float] = []

    def sleeper(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    gate = PacingGate(interval=1 / 3, clock=lambda: now[0], sleeper=sleeper)
    gate.wait()                       # first call is free
    assert slept == []
    gate.wait()                       # immediately after → waits the whole interval
    assert slept == [pytest.approx(1 / 3)]
    now[0] += 10.0
    gate.wait()                       # long past the interval → no wait
    assert len(slept) == 1


def test_the_interval_follows_whether_an_api_key_is_available(monkeypatch) -> None:
    """NCBI allows 3/s unkeyed and 10/s keyed; claiming the keyed rate without a key is abuse.

    `setenv(VAR, "")`, never `delenv` (`@test-no-credential`, and `test_literature_terms.py` states
    the same rule beside its own fixture). This test used `delenv` and passed only because nothing
    had loaded `.env` yet -- RM100 made `EutilsSettings` load it where the key is read, so a developer
    with a real key in `.env` saw the unkeyed assertion fail. `load_dotenv` skips a variable that is
    merely present, and every reader here treats empty as absent, so an empty string is the only
    spelling of "no credential" that actually holds.
    """
    monkeypatch.setenv("NCBI_API_KEY", "")
    assert EutilsSettings().min_request_interval == pytest.approx(1 / 3)

    monkeypatch.setenv("NCBI_API_KEY", "not-a-real-key")
    keyed = EutilsSettings()
    assert keyed.min_request_interval == pytest.approx(1 / 10)
    assert keyed.identity_params()["api_key"] == "not-a-real-key"


def test_no_email_is_sent_when_none_is_configured(monkeypatch) -> None:
    """An invented address would misattribute the traffic to a real person."""
    monkeypatch.setenv("JUST_DNA_CONTACT_EMAIL", "")  # never `delenv` — see the test above
    params = EutilsSettings().identity_params()
    assert "email" not in params
    assert params["tool"] == "just-dna-enricher"


# ── batching and ordering ───────────────────────────────────────────────────────────────────────


def test_ids_are_batched_and_deduplicated_in_first_occurrence_order() -> None:
    recorder = _Recorder(_summary())
    client = _client(recorder, batch_size=2)
    ids = ["3", "1", "3", "2", "1", "4", "5"]      # 5 distinct → 3 batches of at most 2

    client.esummary("pubmed", ids)

    sent = [r.url.params["id"] for r in recorder.requests]
    assert sent == ["3,1", "2,4", "5"], "batches must preserve first-occurrence order"


# ── the absence signal, which is the point of the whole client ──────────────────────────────────


def test_a_missing_record_is_kept_rather_than_dropped() -> None:
    """"NCBI has no summary for this uid" is the answer callers came for, not a failure to hide."""
    recorder = _Recorder(_summary(
        **{
            "29165669": {"uid": "29165669", "title": "A real paper"},
            "999999999": {"uid": "999999999", "error": "cannot get document summary"},
        }
    ))
    records = _client(recorder).esummary("pubmed", ["29165669", "999999999"])

    assert set(records) == {"29165669", "999999999"}
    assert not is_missing(records["29165669"])
    assert is_missing(records["999999999"])


def test_a_uid_absent_from_the_result_is_normalized_to_the_same_shape() -> None:
    """Two spellings of "not there" must not become two different outcomes for a caller."""
    recorder = _Recorder(_summary(**{"1": {"uid": "1", "title": "here"}}))
    records = _client(recorder).esummary("pubmed", ["1", "2"])

    assert is_missing(records["2"])
    assert NO_SUMMARY in records["2"]["error"]


# ── transport failures ──────────────────────────────────────────────────────────────────────────


def test_http_429_is_raised_as_a_rate_limit_after_retries() -> None:
    recorder = _Recorder({}, status=429)
    with pytest.raises(EutilsRateLimitedError):
        _client(recorder).esummary("snp", ["rs334"])
    assert len(recorder.requests) == 4, "tenacity should have retried three times"


def test_a_non_json_body_is_a_clear_error() -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    client = EutilsClient()
    client._client = httpx.Client(transport=httpx.MockTransport(transport))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    with pytest.raises(EutilsError, match="non-JSON"):
        client.esummary("pubmed", ["1"])
