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
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass


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
