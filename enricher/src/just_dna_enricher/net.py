"""Shared HTTP-politeness primitives for the network tier.

Extracted from `gnomad.py` when a second and third rate-limited service arrived (NCBI eutils, the PMC
ID converter, Europe PMC, OLS4, HGNC). Nothing here knows about any particular API — it is the pacing,
batching and ordering discipline every client in this package has to obey, in one place so the rule
cannot drift between them.

Two of these look trivial and are not:

* `PacingGate` takes its clock and its sleep as parameters, so a test can prove a six-second interval
  is honoured without a suite that really sleeps six seconds per request.
* `dedupe` preserves first-occurrence order rather than going through a `set`, because the order
  requests are made in decides the order rows are emitted in, and emitted order is part of
  `artifact.digest` (Principle 7).
"""

import dataclasses
import datetime
import email.utils
import hashlib
import itertools
import logging
import math
import os
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    wait_exponential_jitter,
)
from tenacity.retry import retry_base
from tenacity.stop import stop_base
from tenacity.wait import wait_base

logger = logging.getLogger(__name__)


@dataclass
class PacingGate:
    """Enforce a minimum interval between requests, on an injectable clock.

    The clock and the sleep are parameters rather than direct `time` calls so a test can prove the gate
    honours the interval *without* a suite that really sleeps six seconds per request. Monotonic by
    default, so a wall-clock adjustment mid-run cannot collapse the interval to zero.

    **One gate is safe to share across threads, and it had to become so** (S15). `LookupClients`'
    docstring tells callers to hold a client and reuse it — precisely because a fresh one per question
    would discard this state — so a server running its blocking work through a thread pool shares one
    gate by following our own advice. The unsynchronized version read `last`, slept, then wrote it, so
    two threads could both find the interval elapsed, both skip the sleep, and turn a published 3/s
    budget into 6/s. That budget is a courtesy someone else enforces by blocking the operator's IP, so
    "single-threaded callers only" was not a contract worth keeping unstated *or* worth keeping.

    **The lock covers the bookkeeping, not the sleep.** Each caller reserves the next free slot and then
    waits for it alone, so N callers get N slots spaced `interval` apart rather than serializing behind
    one lock held across a sleep — same guarantee, and no thread is blocked by another's wait. Behaviour
    on a single thread is unchanged.

    **`spent` is what the gate admitted, and the one number a host cannot otherwise get** (S95). A
    proxy metering egress per upstream had to charge by the *shape* of a request — an upper bound,
    because nothing downstream reported the calls actually made. Every egressing client waits on its
    gate once per attempt, inside its retry loop (`gnomad._post`, `eutils._request`), so one increment
    is one upstream attempt: a 429 retried three times counts three, and a snapshot hit that never
    reached the gate counts nothing. Monotonic, bumped under the same lock as the slot, and never
    reset — a reader that wants a rate takes two readings."""

    interval: float
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    last: float | None = None
    #: Admissions so far — one per `wait()` that returned, which is one upstream attempt.
    spent: int = 0
    # Not part of the value: two gates with the same interval are the same gate, and a lock has no
    # useful repr. `default_factory` so every instance gets its own.
    _lock: threading.Lock = dataclasses.field(default_factory=threading.Lock, repr=False, compare=False)

    def wait(self) -> None:
        with self._lock:
            now = self.clock()
            # The slot this caller has claimed: now, or one full interval after the last claim.
            slot = now if self.last is None else max(now, self.last + self.interval)
            self.last = slot
            self.spent += 1
        remaining = slot - self.clock()
        if remaining > 0:
            self.sleeper(remaining)


#: The process's gates, one per (service, interval) (RM418). A service limits requests per key or per
#: address, never per client, so two clients that each built a gate paced to the full rate apiece and
#: together exceeded it. The service is part of the key because two unrelated budgets can share an
#: interval (keyed NCBI and Ensembl's LD endpoint both pace at 0.1 s). The enricher's test conftest
#: resets this per test, so no test waits on a slot another one claimed.
_SERVICE_GATES: dict[tuple[str, float], PacingGate] = {}
_SERVICE_GATES_LOCK = threading.Lock()


def _service_gate(service: str, interval: float) -> PacingGate:
    """The gate every client of `service` at `interval` shares in this process, made on first use.

    Only for a client that was not handed a gate: a gate handed in is the caller's decision and is used
    as handed. One shared gate is safe across threads (`PacingGate`'s lock covers the bookkeeping, not
    the sleep), and its `spent` counts every default-built client's attempts against that service."""
    with _SERVICE_GATES_LOCK:
        gate = _SERVICE_GATES.get((service, interval))
        if gate is None:
            gate = _SERVICE_GATES[(service, interval)] = PacingGate(interval)
        return gate


def batched[T](items: list[T], size: int) -> Iterator[list[T]]:
    """Split into batches of at most `size`, preserving order (so emission stays deterministic)."""
    iterator = iter(items)
    while batch := list(itertools.islice(iterator, size)):
        yield batch


def dedupe[T](items: Iterable[T]) -> list[T]:
    """First-occurrence-order de-duplication (Principle 7: never `set` iteration for emitted order)."""
    seen: set[T] = set()
    out: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


#: Raise every client's retry ceiling to at least this many attempts (RM42).
#:
#: Read at retry time rather than at import, which is the whole point: every retry policy in this tier
#: is a `@retry(stop=…)` decorator argument evaluated when the module loads, so without this there is no
#: moment at which a caller could influence them — a consumer's only route was to walk the package and
#: reassign `policy.stop`, which is reaching into another package's decorator state.
RETRY_ATTEMPTS_ENV = "JUST_DNA_HTTP_RETRY_ATTEMPTS"

#: `.env` is walked for at most once per process. The lookup below runs inside a retry decision, which
#: is rare and already about to sleep for seconds — but a filesystem walk per attempt would still be
#: silly, and a module-level read would make importing `net` touch the disk. Only the file's value is
#: memoized: an exported variable is re-read every call and still wins. Nothing is exported (RM301).
_env_loaded = False
_file_attempts: str | None = None


def retry_attempts(default: int) -> int:
    """How many attempts this client may make: its own default, **raised** to the configured floor.

    **A floor, never a flat setting.** The per-client numbers are deliberate — gnomAD and eutils sit at
    4 because their budgets are the tightest — so a single value that *set* every client would flatten
    tuning that was chosen on purpose, while one that *raises* preserves it. Below the default it is a
    no-op rather than a way to make a client give up sooner; there is no deployment that wants less
    persistence than an author at a terminal, and allowing it would turn one variable into a footgun.

    Why a knob exists at all: three attempts is right for the audience the CLI was written for — a
    person who would rather see a failure in ten seconds than wait out a flapping upstream. It is wrong
    for the other shape the 0.5 tiering created, a **server** running `enrich()` inside an unattended
    publish, where giving up on a transient 502 does not cost ten seconds, it costs the publisher a
    whole re-upload of a module the server had already accepted and validated. Two callers wanting
    opposite things from one constant is the definition of a knob.

    Safe to raise because every gated client with a published rate budget **paces before it retries**:
    an extra attempt spends a slot of that budget rather than bursting past it. The AlphaGenome Atlas
    client's gate has a zero interval, because the Atlas publishes no budget and none was found up to
    21 calls/s (RM307); it still counts every attempt.
    """
    global _env_loaded, _file_attempts
    if not _env_loaded:
        # Imported here rather than at module scope: `locations` is a leaf and `net` is a leaf, and
        # making one import the other for one call would couple them permanently. This is the guarded
        # exception the house rule allows for exactly this shape.
        from just_dna_enricher.locations import env_value

        _file_attempts = env_value(RETRY_ATTEMPTS_ENV)
        _env_loaded = True
    stated = os.environ.get(RETRY_ATTEMPTS_ENV, _file_attempts)
    raw = (stated or "").strip()
    if not raw:
        return default
    try:
        configured = int(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; using this client's own %d attempt(s).",
            RETRY_ATTEMPTS_ENV,
            raw,
            default,
        )
        return default
    return max(default, configured)


class attempt_floor(stop_base):
    """`stop_after_attempt(default)`, resolved per call so a deployment can raise it (RM42).

    Drop-in for the `stop_after_attempt(n)` it replaces, and deliberately **only** for a bare one: a
    composed policy (`stop_after_attempt(3) | stop_after_delay(60)`) means *both*, and raising one term
    silently changes something whose author meant the conjunction. None of this tier's policies is
    composed today; the rule matters the day one is.

    **Deliberately no count in this prose.** It read "the nine policies" in two places while the tree
    carried twelve, and nobody noticed because the guard was a floor (`len(found) >= 9`) walking seven
    of the nine modules that own one -- so three new policies and two whole unwalked modules were both
    invisible. `@registry-completeness`, the same shape as RM96's `_ALL_MODELS` hole: a number in prose
    is a registry nothing iterates. `test_gated_snapshots.py` now discovers the modules instead of
    listing them and asserts an equality over what it walked, which is a claim that cannot go stale.
    """

    def __init__(self, default: int) -> None:
        self.default = default

    def __repr__(self) -> str:
        return f"{type(self).__name__}(default={self.default})"

    def __call__(self, retry_state) -> bool:
        return retry_state.attempt_number >= retry_attempts(self.default)


# ── what a retry says while it waits, and what a give-up says when it stops (RM403) ─────────────
#
# Before RM403 no policy here set `before_sleep` and httpx logs responses only, so an attempt that timed
# out wrote nothing, and a give-up named the error alone. An operator watching a slow sweep could not
# tell attempts timing out from a slow server (S133: 26 `ReadTimeout`s at 15.2 s, five rsIDs spending
# all three attempts, about 48 s each, and not one line said so). Every `@retry` in this tier names both
# hooks below, and `test_retry_logging.py` walks the package to keep it so. WARNING, not INFO: nothing in
# these tiers configures logging, so Python's last-resort handler shows WARNING and above only, and a
# line at INFO is a line nobody watching a sweep sees.


def _retry_subject(retry_state: RetryCallState) -> str:
    """`Client.method(subject)`: the call being retried, and the first argument that names its subject.

    The subject is the first positional or keyword argument that is a string or a number (an rsID, a
    URL, a gene), or the size of the first collection (a batch). `self` and other objects are skipped,
    so a method and a plain function read alike. A long one is cut, since a request body may be a query.
    """
    name = getattr(retry_state.fn, "__qualname__", None) or repr(retry_state.fn)
    for value in (*retry_state.args, *retry_state.kwargs.values()):
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            text = str(value)
            return f"{name}({text if len(text) <= 80 else text[:77] + '...'})"
        if isinstance(value, (list, tuple, set, frozenset, dict)):
            return f"{name}({len(value)} item(s))"
    return name


def _attempt_ceiling(retry_state: RetryCallState) -> int | None:
    """The attempts this policy allows, read the way its stop reads them, or `None` when it cannot say."""
    stop = getattr(retry_state.retry_object, "stop", None)
    if isinstance(stop, attempt_floor):
        return retry_attempts(stop.default)
    return getattr(stop, "max_attempt_number", None)


def _failure(retry_state: RetryCallState) -> str:
    """The attempt's error as `Type: message`. A bare `ReadTimeout` stringifies to nothing, so the type
    is always named."""
    outcome = retry_state.outcome
    if outcome is None or not outcome.failed:
        return "no error recorded"
    exc = outcome.exception()
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _log_retry(retry_state: RetryCallState) -> None:
    """`before_sleep` for every policy here: one line per attempt about to be retried (RM403).

    Client and subject, attempt n of m, the error and the wait, so a timeout reads as a timeout.
    """
    ceiling = _attempt_ceiling(retry_state)
    of = f" of {ceiling}" if ceiling is not None else ""
    wait = retry_state.next_action.sleep if retry_state.next_action is not None else 0.0
    logger.warning(
        "%s: attempt %d%s failed (%s); retrying in %.1f s",
        _retry_subject(retry_state),
        retry_state.attempt_number,
        of,
        _failure(retry_state),
        wait,
    )


def _log_give_up(retry_state: RetryCallState) -> NoReturn:
    """`retry_error_callback` for every policy here: the give-up line, then exactly tenacity's own raise.

    Tenacity calls this in place of raising once the stop says so, and only then: an error the policy
    does not retry is raised from the attempt, never through here. The line carries the attempts made and
    the seconds spent, which the caller's own warning (it names the error) cannot know. The raise is
    tenacity's, read off the policy, so `reraise=True` still re-raises the attempt's own exception (the
    contract every caller's `except` is written against, `@client-exception-contract`) and a policy
    without it still raises `RetryError` from it.
    """
    logger.warning(
        "%s: gave up after %d attempt(s) over %.1f s (%s)",
        _retry_subject(retry_state),
        retry_state.attempt_number,
        retry_state.seconds_since_start or 0.0,
        _failure(retry_state),
    )
    policy = retry_state.retry_object
    outcome = retry_state.outcome
    assert outcome is not None, "tenacity calls retry_error_callback only after an attempt"
    error = policy.retry_error_cls(outcome)
    if policy.reraise:
        error.reraise()
    raise error from outcome.exception()


# ── a status a retry can change, and one that says the source moved (RM354) ────────────────────
#
# Six clients retried every `httpx.HTTPStatusError`, so a 400, a 404 and a 410 were each asked three
# or four times before the client gave up — measured, not read off the decorators. A permanent 4xx
# answers the same on every attempt; retrying it spends somebody else's budget to learn nothing, and
# for a 410 it delays the one message that matters. The other clients already retried transport only.
#
# And a 410 Gone is the source retiring the endpoint. Filed under the same type an outage raises, the
# GWAS Catalog's retired legacy API read as a source that was down rather than one that had moved, so
# every client now names it with its own `*Retired` subclass of its could-not-ask type: every
# existing handler still catches it, and the message says what happened.

#: The statuses a retry can change: the server's own trouble, and a throttle.
TRANSIENT_STATUS_FLOOR = 500
THROTTLED = 429
#: The source retired the endpoint. Permanent, and a fact about the source rather than an outage.
GONE = 410
#: How much of a 410's body a `*Retired` message quotes. Enough for a "moved to" sentence; a
#: maintenance page served as HTML would otherwise land whole in a log line.
RETIRED_QUOTE_CHARS = 400


def is_transient_status(exc: BaseException) -> bool:
    """Whether `exc` is an HTTP status a second attempt could change (a 5xx or a 429)."""
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    status = exc.response.status_code
    return status >= TRANSIENT_STATUS_FLOOR or status == THROTTLED


def retry_if_transient(*also: type[BaseException]) -> retry_base:
    """Retry a transport failure, a timeout, a 5xx or a 429 — never a permanent 4xx (RM354).

    `also` adds a client's own retried type, such as the rate-limit error `gnomad` and `eutils` raise
    on a 429 before `raise_for_status()`.
    """
    return retry_if_exception_type(
        (httpx.TransportError, httpx.TimeoutException, *also)
    ) | retry_if_exception(is_transient_status)


def _body_text(response: httpx.Response) -> str:
    """The body a status error carried, or a marker when it was streamed and never read."""
    try:
        return response.text
    except httpx.ResponseNotRead:
        return "(body not read: a streamed response)"


def retired_message(source: str, response: httpx.Response) -> str:
    """What a client's `*Retired` error says: the URL, the 410, and the source's own text.

    For a client that reads the status itself rather than raising on it; `raise_if_retired` is the
    same message for one that translates an `HTTPStatusError`.
    """
    said = " ".join(_body_text(response).split())[:RETIRED_QUOTE_CHARS] or "(no body)"
    return (
        f"{source} retired the endpoint {response.request.url} (HTTP 410): {said} — this enricher "
        f"reads an API the source no longer serves; upgrade just-dna-enricher"
    )


def raise_if_retired(exc: BaseException, error: type[Exception], source: str) -> None:
    """Raise `error` — a client's `*Retired` type — when `exc` is a 410; otherwise return.

    Called first in a client's status-translating `except` arm, so the arm keeps translating every
    other status the way it did.
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == GONE:
        raise error(retired_message(source, exc.response)) from exc


# ── the reason a question went unanswered (RM361) ───────────────────────────────────────────────
#
# A `*Retired` error is a subclass of its client's could-not-ask type (RM354), so every handler that
# records could-not-ask caught it — and wrote `unreachable`, the reason for an outage, about a source
# that had moved. An outage clears on a re-run; a retired endpoint clears only on an upgrade, so the
# two are different reasons and the record says which. The marker below is the one thing every
# `*Retired` class shares, and `could_not_ask_reason` is the one place a handler turns the exception
# it caught into the reason it records. `test_could_not_ask.py` walks the tier for both.

#: The reason a record carries when the source answered 410: a `VALID_VERIFICATION_SKIPS` member, and
#: a `VALID_FULLTEXT_STATUS` one. Never `unreachable`, which is the reason for an outage.
RETIRED: str = "retired"
#: The reason for a question asked and never answered: a failed request, not a no.
UNREACHABLE: str = "unreachable"


class EndpointRetired(Exception):
    """Mixed into every client's `*Retired` error: the source answered HTTP 410 (RM361).

    A marker, not a catchable family of its own: handlers keep catching their client's could-not-ask
    type, and read the reason off the exception with `could_not_ask_reason`.
    """


def could_not_ask_reason(exc: BaseException) -> str:
    """`retired` when `exc` says the source retired the endpoint, else `unreachable` (RM361).

    For a handler that caught a client's could-not-ask type and is about to record why the question
    went unanswered. A retired endpoint is a fact about the source and is cleared by an upgrade; an
    outage is cleared by a re-run; writing the second about the first sends the reader to the wrong
    remedy. The exception's causes are read too, so a client that translates a 410 into its plain
    could-not-ask type (`raise XUnavailable(...) from exc`) is still read as retired.
    """
    seen: BaseException | None = exc
    while seen is not None:
        if isinstance(seen, EndpointRetired) or (
            isinstance(seen, httpx.HTTPStatusError) and seen.response.status_code == GONE
        ):
            return RETIRED
        seen = seen.__cause__
    return UNREACHABLE


def aggregate_reason(reasons: Iterable[str | None]) -> str:
    """The reason a group of unanswered questions is recorded under: `retired` if any one was (RM361).

    For a record that aggregates several requests: one retired endpoint means the run needs an upgrade
    whatever else happened, which is the remedy the record must lead with. Otherwise `unreachable`.
    """
    return RETIRED if RETIRED in set(reasons) else UNREACHABLE


class Withholding:
    """Mixed into every client whose contract is a withheld value rather than an exception (RM361).

    Such a client answers a failed request with `None` (or its outcome's could-not-ask arm), so a 410
    reached its caller as an outage. `retired` is how it says otherwise without raising: the
    `retired_message` of the first 410 the client met, `None` until then. Sticky for the client's
    life, because a retired route is a fact about the source rather than about one request; a caller
    recording why a question went unanswered reads it with `withheld_reason`.
    """

    retired: str | None = None

    def note_retired(self, source: str, failure: BaseException | httpx.Response) -> bool:
        """Record a 410 from `failure` (an exception or a response); `True` when it was one."""
        response = failure.response if isinstance(failure, httpx.HTTPStatusError) else failure
        if not isinstance(response, httpx.Response) or response.status_code != GONE:
            return False
        if self.retired is None:
            self.retired = retired_message(source, response)
            logger.warning("%s", self.retired)
        return True


def withheld_reason(withholder: object) -> str:
    """`retired` when a withholding client met a 410, else `unreachable` (RM361)."""
    return RETIRED if getattr(withholder, "retired", None) else UNREACHABLE


def release_dataset(lane: str, released: str | None) -> str:
    """A `dataset` label, `<lane>_<release>`, or the bare lane when the source stated no release (RM361).

    The label is a merge-key member and a `sources.csv` cell; a release the file did not state is
    withheld from it, never spelled `unknown` (a release of that name) or `None`.
    """
    return f"{lane}_{released}" if released else lane


def stated_release(dataset: str | None, *lanes: str) -> str | None:
    """The release a `dataset` label states, or `None` when it states none (RM373).

    The inverse of `release_dataset` for a reader: a blank cell, and the bare lane that label writes when
    the source stated no release, are both no release. What a licence row's `dataset` is computed from,
    so a table whose rows say `gwas_catalog` names no release rather than one called `gwas_catalog`.
    """
    label = (dataset or "").strip()
    return None if not label or label in lanes else label


# ── bulk file downloads: one body, translated and retried (RM187) ───────────────────────────────
#
# Eleven builders stream one file from a source's FTP or bulk endpoint, and until RM187 each carried
# its own copy of the same fifteen lines. The copies had drifted in exactly the way copies do, and
# the drift was invisible because every one of them *worked*:
#
# * **Four leaked `httpx`.** `clinvar_build`'s two, `constraint_build`'s and `clinpgx_build`'s raised
#   the transport library's own exception at their callers, and `caches._rebuild_*` catches each
#   lane's own error type. So a truncated download was a **traceback rather than an outcome** — it
#   escaped `rebuild_lane` too, which means one flaky download aborted every lane after it in a
#   `cache rebuild`. Measured, not hypothesised: NCBI closed the connection 180,927,542 bytes into a
#   193,427,450-byte VCF on 2026-09-03 and took the run with it.
# * **None of the eleven retried.** A ~190 MB download over a public FTP mirror is exactly the
#   request most likely to be cut short, and it was the one request in this tier with no second
#   attempt — while every live *client* (`gnomad`, `ensembl`, `literature`, `pgs`, `civic_api`) has
#   had `attempt_floor` since RM42.
#
# This is `@client-exception-contract`'s third appearance. RM97 found it in the clients, RM101 one
# layer up in the passes, and the builder downloads were never swept — the same shape three times,
# which is why the guard for it walks the package rather than a list of module names (RM101's own
# guard hand-kept eight and missed `identifiers`).
#
# It lives here because that is what this module is for: pacing, batching and ordering discipline
# every client has to obey, in one place so the rule cannot drift between them. A bulk download is
# the same kind of rule.


@dataclass(frozen=True)
class StreamedFile:
    """What one bulk download established: where it landed, its digest, and the source's own labels.

    **The digest is returned rather than logged.** Four of the eleven copies computed a sha256 while
    streaming and then only wrote it to the log, so a caller that needed to record the provenance of
    the bytes it had just fetched had to hash the file again (`@dont-discard-computed`). Two of them
    later grew a `tuple[Path, str]` return for exactly that reason, one lane at a time.

    `etag` and `last_modified` are the source's, `None` when it sends neither. They are how a lane
    can later ask *has this file changed* without downloading it again — MANE, CIViC and PubMind
    record them today, and the rest get them for free rather than growing their own copy later.
    """

    path: Path
    sha256: str
    etag: str | None = None
    last_modified: str | None = None


#: `stream_to_file`'s timeout when a caller names none (RM421): the 120 s three builders already passed,
#: generous because it bounds the gap between chunks on a slow mirror, not the whole download. A constant,
#: not a knob (`@retry-attempt-floor`): no deployment has asked for another value.
_BULK_TIMEOUT: float = 120.0


class _StreamStopped(BaseException):
    """A download stopped because its caller set the `_stop` it passed (RM409); never seen past a pool.

    Raised in a worker thread, and the caller that set the flag is already raising its own exception
    (the user's `KeyboardInterrupt`, or the first part that failed), so nothing ever reports this one.
    It is not a transport error, so the retry does not take it for one, and not `httpx`'s, so the
    `except BaseException` arm removes the `.part` and lets it through untranslated.

    A `BaseException`, like `GeneratorExit`: it is a stop, not an error a caller handles, so no
    `except Exception` on the way out may take it for a failed download, and it stays off the error
    roster ENRICHER.md keeps of what a caller catches.
    """


def stream_to_file(
    dest: "Path",
    url: str,
    *,
    error_cls: type[Exception],
    retired: type[Exception],
    what: str,
    timeout: float | None = _BULK_TIMEOUT,
    remedy: str = "",
    _stop: threading.Event | None = None,
) -> StreamedFile:
    """Stream `url` to `dest` atomically, hashing as it goes; retry the transport, translate the rest.

    The one body every `download_*` in this package calls. Four properties, and each is a defect that
    reached a user before it was one:

    **Atomic.** The bytes go to `<dest>.part` and are renamed only once the stream finished, so a
    failed fetch leaves the directory as it found it rather than truncating a good file already there
    (`@a-failed-fetch-is-not-a-no-op`). The partial is removed on failure — a `.part` left behind is
    the one residue a re-run would have to reason about.

    **Retried, but only where retrying is honest.** `httpx.TransportError` covers a connection cut
    mid-body — `RemoteProtocolError` subclasses it, which is the failure that motivated this — and a
    second attempt genuinely fixes it. A **status** error is not retried: a 404 from a mistyped
    release tag is the same 404 four times over, and the caller wants it now rather than after three
    backoffs. `attempt_floor` reads `$JUST_DNA_HTTP_RETRY_ATTEMPTS` at retry time like every other
    policy here, so a deployment can raise the floor without touching code (RM42).

    **Translated.** `httpx`'s exceptions do not leave this function. A caller of this package may not
    be made to depend on the transport library's exception tree to know that a fetch failed, and the
    lane adapters catch their own builder's type — so a leak is not merely untidy, it is a lane that
    cannot report `built=False` (`@client-exception-contract`).

    **Restarted from zero on each attempt.** The hasher and the output file are created inside the
    attempt, not outside it: a retry that appended to a partial body would produce a file whose
    digest is real and whose contents are nonsense, which no footer check and no `raise_for_status`
    would catch.

    **A 410 is the lane's `retired`, never its `error_cls`** (RM361, audit round 2). A source that
    retired the file moved it, and the remedy is an upgrade rather than a re-run; `retired` is the
    lane's `*Retired` (a subclass of `error_cls` marked `EndpointRetired`), required so no lane can
    forget it, and the message is `retired_message`'s (the host that answered, the source's own body
    quoted), followed by `what` and the lane's `remedy`.

    **Stoppable between chunks, for a caller on a thread pool** (RM409). `_stop` is checked before the
    request opens and before each chunk is written, and a retry's backoff waits on it rather than
    sleeping; once it is set the download raises, the `.part` is removed, and nothing lands under `dest`. A `KeyboardInterrupt` reaches only the main thread, so a
    pool that fetches parts in workers sets the flag on interrupt before it joins them; without it the
    join waited for every in-flight part to stream to its end, and a 22 GB mirror ignored two Ctrl-C.

    **Bounded, by default** (RM421). `timeout` is 120 s unless the caller names its own, and httpx
    applies it to connect, read, write and pool alike. The read half bounds the gap between two chunks,
    not the whole download, so a slow mirror that keeps sending is never cut off, while a server that
    accepts the connection and then sends nothing raises `httpx.ReadTimeout`, which is retried as a
    transport error above and translated to `error_cls` on giving up. The default was once `None`, which
    httpx reads as no timeout at all: eleven of fourteen callers named none, so such a stall blocked
    forever, no retry fired, and a pool worker stuck in the read never reached the `_stop` check. An
    explicit `timeout=None` still means no timeout; no caller in this package passes it, and a walk over
    the call sites keeps it that way.

    `what` names the thing being fetched for the message ("the ClinVar VCF"); `remedy` is an optional
    sentence saying what the caller can do instead, for the lanes that accept a local file.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")

    def _stopped() -> None:
        if _stop is not None and _stop.is_set():
            raise _StreamStopped(f"stopped downloading {what}")

    # A stoppable download's backoff waits on the flag instead of sleeping, so a stop that lands
    # between attempts is not held for up to thirty seconds of backoff before the next one notices it.
    nap = {"sleep": _stop.wait} if _stop is not None else {}

    @retry(
        before_sleep=_log_retry,
        retry_error_callback=_log_give_up,
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(multiplier=2.0, max=30.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
        **nap,
    )
    def _attempt() -> StreamedFile:
        hasher = hashlib.sha256()
        _stopped()
        with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as response:
            if response.status_code == GONE:
                response.read()  # a 410's body is the source's own word on where the file went
            response.raise_for_status()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    _stopped()
                    handle.write(chunk)
                    hasher.update(chunk)
        return StreamedFile(tmp, hasher.hexdigest(), etag, last_modified)

    logger.info("Downloading %s from %s ...", what, url)
    try:
        streamed = _attempt()
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == GONE:
            # The host that answered retired it (a redirect may have moved the request), and the lane's
            # own remedy still applies: a release the operator picked, or a file they already hold.
            gone = retired_message(exc.response.request.url.host, exc.response)
            raise retired(
                f"{gone} (fetching {what}). {remedy}" if remedy else f"{gone} (fetching {what})"
            ) from exc
        message = f"could not download {what} from {url}: {exc}"
        raise error_cls(f"{message}. {remedy}" if remedy else message) from exc
    except BaseException:
        # Not only the transport: a disk that fills or a mount that turns read-only raises `OSError`
        # from `handle.write`, and the partial was left behind on exactly that leg while the
        # docstring promised none. The type is the caller's (the lane adapters catch `OSError`),
        # so it is not translated — only the residue is removed.
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(dest)
    logger.info("Downloaded %s (sha256 %s)", dest, streamed.sha256)
    return dataclasses.replace(streamed, path=dest)


# ── a throttle that says when to come back (RM267) ──────────────────────────────────────────────
#
# A 429 (or a 503) may carry `Retry-After`: the server's own statement of when a request may be made
# again, in seconds or as an HTTP-date. Every retried client here waited on tenacity's backoff instead,
# which starts at half a second, so a throttled client asked again before it was allowed to. Ensembl
# REST was the first client found doing it; it was also unpaced.

#: The longest `Retry-After` a retry sleeps through: about the longest backoff a retry here already
#: waits (8 s). Ensembl's per-second budget asks for a fraction of a second; its hourly one answers
#: with the time to its reset, which can be most of an hour, and a maintenance 503 may ask for minutes.
#: Past this the request is not retried, and a client that honours the header asks nothing until the
#: time passes — so a long ask costs a batch one request, not two long sleeps per subject.
RETRY_AFTER_CEILING: float = 10.0


def retry_after_seconds(exc: BaseException | None, *, now: Callable[[], float] = time.time) -> float | None:
    """How long a throttled answer asked the client to wait, or `None` when it did not say.

    Read only off a status a retry can change (`is_transient_status`: a 5xx or a 429), in either of
    RFC 9110's forms — delta-seconds (Ensembl sends a fraction, `40.0`) or an HTTP-date, measured
    against `now` (wall clock, since the date is one). A date already past is `0.0`. No header, an
    unreadable one, or any other exception is `None`: unknown, never a wait of zero.
    """
    if not isinstance(exc, httpx.HTTPStatusError) or not is_transient_status(exc):
        return None
    raw = (exc.response.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            # `-0000` parses naive; an HTTP-date is GMT by definition, never the host's local time.
            when = when.replace(tzinfo=datetime.UTC)
        seconds = when.timestamp() - now()
    if not math.isfinite(seconds):
        return None
    return max(seconds, 0.0)


def asks_past_ceiling(exc: BaseException | None, ceiling: float = RETRY_AFTER_CEILING) -> bool:
    """Whether `exc` asked for a wait longer than `ceiling` — a request not to retry now."""
    asked = retry_after_seconds(exc)
    return asked is not None and asked > ceiling


def retry_if_transient_within(*also: type[BaseException], ceiling: float = RETRY_AFTER_CEILING) -> retry_base:
    """`retry_if_transient`, except a throttle whose `Retry-After` exceeds `ceiling` is not retried."""
    return retry_if_transient(*also) & retry_if_exception(lambda exc: not asks_past_ceiling(exc, ceiling))


class wait_retry_after(wait_base):
    """A tenacity wait that is at least what the server's `Retry-After` asked for, else `fallback`'s.

    Never shorter than the fallback, so a server asking for less than the backoff does not shorten it;
    capped at `ceiling`, which `retry_if_transient_within` keeps a retry from ever reaching.
    """

    def __init__(self, fallback: wait_base, ceiling: float = RETRY_AFTER_CEILING) -> None:
        self.fallback = fallback
        self.ceiling = ceiling

    def __call__(self, retry_state: RetryCallState) -> float:
        backoff = self.fallback(retry_state)
        outcome = retry_state.outcome
        asked = retry_after_seconds(outcome.exception() if outcome is not None and outcome.failed else None)
        if asked is None:
            return backoff
        return max(backoff, min(asked, self.ceiling))
