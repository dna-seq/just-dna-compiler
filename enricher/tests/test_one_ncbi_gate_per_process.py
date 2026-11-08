"""Two NCBI clients in one process pace against one budget, not two (RM418).

NCBI limits E-utilities requests per API key, or per address without one, never per client. Every
`EutilsClient` built without a gate made its own, and both callers build one (`identifiers.check_rsids`
and the literature pass), so a host running two enrichments at once paced each to the full rate and
together exceeded it. A client that is not handed a gate now takes the process's gate for its service and
interval; a gate handed in is still used as handed.

The registry is reset before every test by the enricher conftest, so nothing here, or anywhere in the
suite, waits on a slot another test claimed.
"""

import threading

import httpx
import pytest
from just_dna_enricher import net
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.net import PacingGate


class _FrozenClock:
    """Never moves, and records each wait instead of sleeping (the shape `test_net` uses)."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []
        self._lock = threading.Lock()

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.slept.append(seconds)


def _answer(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"result": {"uids": ["1"], "1": {"uid": "1"}}})


def test_two_clients_built_without_a_gate_share_one() -> None:
    """The defect itself: on the previous `main` each of these held a gate of its own."""
    first, second = EutilsClient(), EutilsClient()
    assert first.gate is second.gate


def test_a_gate_handed_in_is_used_as_handed() -> None:
    own = PacingGate(interval=5.0)
    assert EutilsClient(gate=own).gate is own
    assert EutilsClient().gate is not own


def test_keyed_and_unkeyed_clients_do_not_share_a_gate() -> None:
    """Two intervals are two budgets: a key's 10/s is not an address's 3/s."""
    keyed = EutilsClient(settings=EutilsSettings(api_key="k"))
    unkeyed = EutilsClient(settings=EutilsSettings(api_key=""))
    assert keyed.gate is not unkeyed.gate
    assert keyed.gate.interval < unkeyed.gate.interval


def test_another_service_at_the_same_interval_keeps_its_own_gate() -> None:
    """Keyed NCBI and Ensembl's LD endpoint both pace at 0.1 s and are unrelated budgets."""
    assert net._service_gate("ncbi-eutils", 0.1) is net._service_gate("ncbi-eutils", 0.1)
    assert net._service_gate("ncbi-eutils", 0.1) is not net._service_gate("another-service", 0.1)


def test_requests_from_two_clients_on_two_threads_are_spaced_by_the_interval(monkeypatch) -> None:
    """The consequence, on a frozen clock: two clients asking at the same instant are cleared one
    interval apart. Unshared, both were cleared at once, which is how two budgets became one excess."""
    clock = _FrozenClock()
    settings = EutilsSettings(api_key="")
    interval = settings.min_request_interval
    assert interval is not None
    monkeypatch.setattr(
        net,
        "_SERVICE_GATES",
        {("ncbi-eutils", interval): PacingGate(interval=interval, clock=clock, sleeper=clock.sleep)},
    )

    clients = [EutilsClient(settings=settings) for _ in range(2)]
    for client in clients:
        client._client = httpx.Client(transport=httpx.MockTransport(_answer))
    start = threading.Barrier(len(clients))

    def ask(client: EutilsClient) -> None:
        start.wait()
        client.esummary("pubmed", ["1"])

    threads = [threading.Thread(target=ask, args=(client,)) for client in clients]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert clock.slept == [pytest.approx(interval)], (
        "one client proceeds at once, the other waits one interval"
    )
