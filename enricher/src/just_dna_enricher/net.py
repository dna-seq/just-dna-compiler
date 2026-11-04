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
import hashlib
import itertools
import logging
import os
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception, retry_if_exception_type, wait_exponential_jitter
from tenacity.retry import retry_base
from tenacity.stop import stop_base

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


class RetiredEndpoint(Exception):
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
        if isinstance(seen, RetiredEndpoint) or (
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


def withheld_reason(client: object) -> str:
    """`retired` when a withholding client met a 410, else `unreachable` (RM361)."""
    return RETIRED if getattr(client, "retired", None) else UNREACHABLE


def release_dataset(lane: str, released: str | None) -> str:
    """A `dataset` label, `<lane>_<release>`, or the bare lane when the source stated no release (RM361).

    The label is a merge-key member and a `sources.csv` cell; a release the file did not state is
    withheld from it, never spelled `unknown` (a release of that name) or `None`.
    """
    return f"{lane}_{released}" if released else lane


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


def stream_to_file(
    dest: "Path",
    url: str,
    *,
    error_cls: type[Exception],
    what: str,
    timeout: float | None = None,
    remedy: str = "",
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

    `what` names the thing being fetched for the message ("the ClinVar VCF"); `remedy` is an optional
    sentence saying what the caller can do instead, for the lanes that accept a local file.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")

    @retry(
        stop=attempt_floor(3),
        wait=wait_exponential_jitter(initial=2.0, max=30.0),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    def _attempt() -> StreamedFile:
        hasher = hashlib.sha256()
        with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as response:
            response.raise_for_status()
            etag = response.headers.get("ETag")
            last_modified = response.headers.get("Last-Modified")
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
                    hasher.update(chunk)
        return StreamedFile(tmp, hasher.hexdigest(), etag, last_modified)

    logger.info("Downloading %s from %s ...", what, url)
    try:
        streamed = _attempt()
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
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
