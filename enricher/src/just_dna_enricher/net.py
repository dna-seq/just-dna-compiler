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

import itertools
import logging
import os
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from tenacity.stop import stop_base

logger = logging.getLogger(__name__)


@dataclass
class PacingGate:
    """Enforce a minimum interval between requests, on an injectable clock.

    The clock and the sleep are parameters rather than direct `time` calls so a test can prove the gate
    honours the interval *without* a suite that really sleeps six seconds per request. Monotonic by
    default, so a wall-clock adjustment mid-run cannot collapse the interval to zero.
    """

    interval: float
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    last: float | None = None

    def wait(self) -> None:
        now = self.clock()
        if self.last is not None:
            remaining = self.interval - (now - self.last)
            if remaining > 0:
                self.sleeper(remaining)
                now = self.clock()
        self.last = now


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
#: Read at retry time rather than at import, which is the whole point: the nine policies below are
#: `@retry(stop=…)` decorator arguments evaluated when the module loads, so without this there is no
#: moment at which a caller could influence them — a consumer's only route was to walk the package and
#: reassign `policy.stop`, which is reaching into another package's decorator state.
RETRY_ATTEMPTS_ENV = "JUST_DNA_HTTP_RETRY_ATTEMPTS"

#: `.env` is walked for at most once per process. The lookup below runs inside a retry decision, which
#: is rare and already about to sleep for seconds — but a filesystem walk per attempt would still be
#: silly, and a module-level `load_env()` would make importing `net` touch the disk.
_env_loaded = False


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

    Safe to raise because every gated client **paces before it retries**: an extra attempt spends a slot
    of the published budget rather than bursting past it.
    """
    global _env_loaded
    if not _env_loaded:
        # Imported here rather than at module scope: `locations` is a leaf and `net` is a leaf, and
        # making one import the other for one call would couple them permanently. This is the guarded
        # exception the house rule allows for exactly this shape.
        from just_dna_enricher.locations import load_env

        load_env()
        _env_loaded = True
    raw = (os.environ.get(RETRY_ATTEMPTS_ENV) or "").strip()
    if not raw:
        return default
    try:
        configured = int(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not an integer; using this client's own %d attempt(s).",
            RETRY_ATTEMPTS_ENV, raw, default,
        )
        return default
    return max(default, configured)


class attempt_floor(stop_base):  # noqa: N801 - a tenacity `stop_*` object, named like its siblings
    """`stop_after_attempt(default)`, resolved per call so a deployment can raise it (RM42).

    Drop-in for the `stop_after_attempt(n)` it replaces, and deliberately **only** for a bare one: a
    composed policy (`stop_after_attempt(3) | stop_after_delay(60)`) means *both*, and raising one term
    silently changes something whose author meant the conjunction. None of the nine is composed today;
    the rule matters the day one is.
    """

    def __init__(self, default: int) -> None:
        self.default = default

    def __repr__(self) -> str:
        return f"{type(self).__name__}(default={self.default})"

    def __call__(self, retry_state) -> bool:
        return retry_state.attempt_number >= retry_attempts(self.default)
