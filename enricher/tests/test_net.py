"""Unit tests for the shared HTTP-politeness primitives (`just_dna_enricher.net`).

Everything here runs on an **injected clock and an injected sleeper**, so a six-second courtesy budget
is proven without a suite that really sleeps. Nothing touches the network.
"""

import threading

import pytest
from just_dna_enricher.net import PacingGate, batched, dedupe


class _FakeClock:
    """A clock that only moves when a test says so, plus a sleeper that records instead of sleeping.

    Deliberately *not* advanced by `sleep`: the point of every test below is what the gate decides
    while no time passes, which is the state a real thread pool reaches on a fast machine."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []
        self._lock = threading.Lock()

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.slept.append(seconds)


def test_a_single_caller_waits_exactly_the_interval() -> None:
    clock = _FakeClock()
    gate = PacingGate(interval=6.0, clock=clock, sleeper=clock.sleep)

    gate.wait()
    assert clock.slept == [], "the first request has nothing to wait for"

    gate.wait()
    assert clock.slept == [6.0], "the second waits the full interval on a frozen clock"


def test_time_already_elapsed_is_credited() -> None:
    clock = _FakeClock()
    gate = PacingGate(interval=6.0, clock=clock, sleeper=clock.sleep)
    gate.wait()
    clock.now += 4.0
    gate.wait()
    assert clock.slept == [pytest.approx(2.0)], "only the remaining 2s is waited"


def test_a_gate_shared_across_threads_still_honours_the_budget() -> None:
    """The S15 race, demonstrated by its consequence rather than by inspecting the lock.

    Four threads enter `wait()` on one gate while the clock is frozen, so the interval provably has
    **not** elapsed for any of them. The budget's guarantee is that the times they are cleared to
    proceed are spaced at least `interval` apart. Unsynchronized, all four read the same `last`,
    computed the same remaining wait and were cleared at the same instant — one interval's grace for
    four requests, which is how a published 3/s budget becomes 12/s.
    """
    clock = _FakeClock()
    interval = 6.0
    gate = PacingGate(interval=interval, clock=clock, sleeper=clock.sleep)
    workers = 4
    start = threading.Barrier(workers)

    def call() -> None:
        start.wait()          # every thread inside `wait()` at once, which is the whole point
        gate.wait()

    threads = [threading.Thread(target=call) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # The slot each caller was cleared for, read from what it was told to wait rather than from
    # `gate.last` — which another thread may already have advanced, so observing it after the fact
    # would be the same race the test is about.
    slots = sorted([0.0] + clock.slept)          # one caller proceeds at once, the rest wait
    assert len(slots) == workers
    gaps = [round(later - earlier, 6) for earlier, later in zip(slots, slots[1:], strict=False)]
    assert gaps == [interval] * (workers - 1), f"slots must be spaced by the interval, got {gaps}"
    assert len(set(slots)) == workers, "no two callers may be cleared at the same instant"
    # Each caller waits for its own slot only — the gate never makes one thread wait out another's
    # sleep, which is what holding the lock across the sleep would have cost.
    assert sorted(clock.slept) == [interval * n for n in range(1, workers)]


def test_the_first_caller_never_waits_however_many_are_racing() -> None:
    """A cold gate must not manufacture a delay: exactly one of N racing callers proceeds at once."""
    clock = _FakeClock()
    gate = PacingGate(interval=2.0, clock=clock, sleeper=clock.sleep)
    workers = 5
    start = threading.Barrier(workers)

    def call() -> None:
        start.wait()
        gate.wait()

    threads = [threading.Thread(target=call) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(clock.slept) == workers - 1, "one caller proceeds immediately, the rest are paced"


def test_a_zero_interval_gate_never_sleeps() -> None:
    """The shape the whole test suite injects to disable pacing must stay free."""
    clock = _FakeClock()
    gate = PacingGate(interval=0.0, clock=clock, sleeper=clock.sleep)
    for _ in range(3):
        gate.wait()
    assert clock.slept == []


def test_batched_preserves_order_and_never_exceeds_the_size() -> None:
    items = list(range(7))
    batches = list(batched(items, 3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6]]
    assert [item for batch in batches for item in batch] == items


def test_dedupe_keeps_first_occurrence_order() -> None:
    # Emission order reaches artifact.digest (Principle 7), so this may never go through a set.
    assert dedupe(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]
