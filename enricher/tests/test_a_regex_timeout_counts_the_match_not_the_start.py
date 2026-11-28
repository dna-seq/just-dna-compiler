"""A `provenance_regex` timeout counts the match, never the matching process's start-up (RM471).

`regex_matches` runs the match in a child process so a runaway pattern can be killed
(`@regex-timeout-process`). Its timeout was a `join` on that child, so it counted the child's start-up
too: under `forkserver` an interpreter importing `just_dna_enricher.literature`, measured at 2 to 4 s per
call at a load average of 69 on 16 threads. A trivial pattern then read as having exceeded its 5 s bound
(`test_a_regex_locator_matches_the_fulltext` failed so at a load of 40 to 57), and the catastrophic-pattern
test's 0.25 s could run out before the pattern ever started, so it passed whether the bound worked or not.

The child now says it is ready before it matches. The start-up has its own allowance and its own
warning, and the timeout starts at the ready signal.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

import pytest
from just_dna_enricher import literature
from just_dna_enricher.literature import regex_matches

EXCEEDED = "exceeded"
DID_NOT_START = "the matching process did not start"


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == literature.logger.name]


def test_a_slow_start_is_not_charged_to_the_match(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # A start-up slower than the timeout, made so in the parent: the wait for the ready signal returns
    # 1.5 s late, and the match is given 1.0 s. Charged to the match, the start alone would exceed it.
    real_wait: Callable[..., Any] = literature.wait_for

    def _late_wait(*args: Any, **kwargs: Any) -> Any:
        time.sleep(1.5)
        return real_wait(*args, **kwargs)

    monkeypatch.setattr(literature, "wait_for", _late_wait)
    caplog.set_level(logging.WARNING, logger=literature.logger.name)
    assert regex_matches(r"variant\s+interpretations", "the variant interpretations we support", timeout=1.0)
    assert _warnings(caplog) == []


def test_a_catastrophic_pattern_is_stopped_after_it_started(caplog: pytest.LogCaptureFixture) -> None:
    # The "exceeded" warning is written only after the ready signal, so it says the pattern ran.
    caplog.set_level(logging.WARNING, logger=literature.logger.name)
    assert regex_matches(r"(a+)+$", "a" * 40 + "!", timeout=0.25) is None
    [message] = _warnings(caplog)
    assert EXCEEDED in message and DID_NOT_START not in message


def test_a_process_that_does_not_start_in_time_is_its_own_finding(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # No interpreter starts and imports the enricher in no time, so an allowance of 0 always runs out.
    monkeypatch.setattr(literature, "_REGEX_STARTUP_ALLOWANCE", 0.0)
    caplog.set_level(logging.WARNING, logger=literature.logger.name)
    assert regex_matches(r"variant", "variant", timeout=60.0) is None
    [message] = _warnings(caplog)
    assert DID_NOT_START in message and EXCEEDED not in message
    assert "NOT CHECKED (never as not-found)" in message
