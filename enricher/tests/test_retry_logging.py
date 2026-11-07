"""Every retry says so while it waits, and every give-up says how many attempts and how long (RM403, S133).

Before RM403 no tenacity policy in the enricher set `before_sleep`, and httpx logs responses only, so an
attempt that timed out wrote nothing at all. A registry sweep met 26 `ReadTimeout`s at 15.2 s and five
rsIDs that spent all three attempts, about 48 s each, and its log said only the final error, once. An
operator could not tell attempts timing out from a slow server.

The fix is two shared hooks in `net` (`_log_retry`, `_log_give_up`) that every `@retry` names. **Why a
static walk** beside the behaviour: a new client is written by copying an old decorator, and a copy that
drops a keyword is silent in every test that does not time it out. The walk reads the package's source,
so the client is covered the day it is written, the same reasoning as `test_retry_wait_keywords.py`.

The give-up hook replaces tenacity's own raise, so the behaviour half pins that the raise did not move:
`reraise=True` still hands the attempt's own exception to the caller's `except`
(`@client-exception-contract`), a policy without it still raises `RetryError`, and an error the policy
does not retry still goes straight through with no give-up line.
"""

import ast
import logging
from pathlib import Path

import httpx
import just_dna_enricher
import pytest
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.net import (
    RETRY_ATTEMPTS_ENV,
    PacingGate,
    _log_give_up,
    _log_retry,
    attempt_floor,
)
from tenacity import RetryError, retry, retry_if_exception_type, wait_none

_PACKAGE = Path(just_dna_enricher.__file__).parent
_HOOKS = {"before_sleep": "_log_retry", "retry_error_callback": "_log_give_up"}


def _retry_calls() -> list[tuple[str, ast.Call]]:
    found: list[tuple[str, ast.Call]] = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name in {"retry", "Retrying", "AsyncRetrying"}:
                found.append((f"{path.relative_to(_PACKAGE)}:{node.lineno}", node))
    return found


def test_every_retry_policy_names_the_shared_logging_hooks() -> None:
    calls = _retry_calls()
    # An empty walk passes for any source; the package has retried clients, so empty means broken.
    assert calls, "found no retry( call under the enricher package"
    silent = []
    for site, call in calls:
        named = {k.arg: getattr(k.value, "id", None) for k in call.keywords}
        missing = [f"{key}={hook}" for key, hook in _HOOKS.items() if named.get(key) != hook]
        if missing:
            silent.append(f"{site} lacks {', '.join(missing)}")
    assert silent == [], (
        f"a retry policy that does not name net's hooks retries and gives up without a line (RM403): {silent}"
    )


@pytest.fixture
def _no_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set, not deleted: a `.env` value would otherwise raise the ceiling and the line's "of 3" (RM42).
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "")


def test_a_real_client_logs_each_retry_and_its_give_up(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, _no_floor: None
) -> None:
    """S133's case on the REST route itself: every attempt times out, and the caller withholds."""
    monkeypatch.setattr("time.sleep", lambda _seconds: None)  # tenacity's backoff

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("The read operation timed out", request=request)

    resolver = EnsemblResolver(gate=PacingGate(interval=0.0))
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.net"):
        # Could-not-ask, the contract the caller keeps: the attempt's own exception reached its except.
        assert resolver.resolve_rsid_rest("rs1801133") == (None, None)
    lines = [r.getMessage() for r in caplog.records if r.name == "just_dna_enricher.net"]
    subject = "EnsemblResolver._rest_rsid(rs1801133)"
    retries = [line for line in lines if "retrying in" in line]
    assert [line.split(" failed")[0] for line in retries] == [
        f"{subject}: attempt 1 of 3",
        f"{subject}: attempt 2 of 3",
    ]
    assert all("ReadTimeout: The read operation timed out" in line for line in retries)
    (give_up,) = [line for line in lines if "gave up" in line]
    assert give_up.startswith(f"{subject}: gave up after 3 attempt(s) over ")
    assert give_up.endswith("s (ReadTimeout: The read operation timed out)")


def test_a_raised_floor_is_the_ceiling_the_line_names(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "5")
    calls = []

    @retry(
        before_sleep=_log_retry,
        retry_error_callback=_log_give_up,
        stop=attempt_floor(3),
        wait=wait_none(),
        retry=retry_if_exception_type(httpx.ConnectError),
        reraise=True,
    )
    def ask(rsid: str) -> None:
        calls.append(rsid)
        raise httpx.ConnectError("")

    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.net"), pytest.raises(httpx.ConnectError):
        ask("rs1")
    lines = [r.getMessage() for r in caplog.records if r.name == "just_dna_enricher.net"]
    assert len(calls) == 5
    # A bare ConnectError stringifies to nothing; the type is still named.
    assert lines[0].endswith("attempt 1 of 5 failed (ConnectError); retrying in 0.0 s")
    assert "gave up after 5 attempt(s)" in lines[-1]


def test_the_give_up_hook_raises_as_tenacity_would(caplog: pytest.LogCaptureFixture, _no_floor: None) -> None:
    def policy(reraise: bool):
        return retry(
            before_sleep=_log_retry,
            retry_error_callback=_log_give_up,
            stop=attempt_floor(2),
            wait=wait_none(),
            retry=retry_if_exception_type(httpx.ReadTimeout),
            reraise=reraise,
        )

    @policy(reraise=False)
    def wrapped() -> None:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(RetryError) as caught:
        wrapped()
    assert isinstance(caught.value.last_attempt.exception(), httpx.ReadTimeout)
    assert isinstance(caught.value.__cause__, httpx.ReadTimeout)

    @policy(reraise=True)
    def not_retried(gene: str) -> None:
        raise ValueError("a 400 is an answer, not an outage")

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.net"), pytest.raises(ValueError):
        not_retried("CYP2C9")
    # An error the policy does not retry is no give-up: tenacity raises it from the attempt, no line.
    assert [r for r in caplog.records if r.name == "just_dna_enricher.net"] == []
