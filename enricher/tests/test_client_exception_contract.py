"""A client's exception type is part of its contract, and every one of them must honour it (RM97).

`@client-exception-contract`: **retry, then translate, both legs.** A caller writes
`except GnomadError` / `except CpicError` because that is what the client documents, and a client
that lets `httpx` types out has no contract at all — the handler was written for exactly the case it
cannot see.

The reason this file walks the clients rather than testing one of them is the shape of the defect it
was written for. `cpic.py` and `pharmvar.py` carried the repair *and* the narrative of why it was
needed (R2-13) for a whole release while `gnomad._post` and `eutils._get` kept the unrepaired shape:
`raise_for_status()` outside the `try`, `httpx.HTTPStatusError` in neither retry list, so a 5xx
escaped raw and unretried. Two live consequences — `enrich()` catches `GnomadError` under the comment
"a last-resort link must not sink the whole enrichment" and a 502 sank it anyway, and the
`check_rsids` call has no handler at all, so a dbSNP 5xx aborted a run with a traceback the CLI
cannot render. A per-client test would have passed on two clients and never been written for the
other two, which is how the gap lasted.

Both legs are exercised because the two escaped by different routes: the status leg was never
retried, and the transport leg *was* retried and then re-raised bare once `reraise=True` exhausted
the attempts.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx
import pytest
from just_dna_enricher.cpic import CpicClient, CpicError
from just_dna_enricher.eutils import EutilsClient, EutilsError, EutilsSettings
from just_dna_enricher.gnomad import GnomadClient, GnomadError, GnomadSettings
from just_dna_enricher.identifiers import IdentifierUnavailable, OntologyClient
from just_dna_enricher.net import PacingGate
from just_dna_enricher.pharmvar import PharmVarClient, PharmVarError


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize tenacity's backoff — the retry *count* is the contract here, not the wall-clock.

    Every case below exhausts a client's attempts on purpose, and the exponential jitter these
    clients are tuned with (gnomAD waits up to 30s) turned this file into two minutes of sleeping.
    `retry_attempts` deliberately offers no way to ask for *fewer* attempts (it is a floor, never a
    flat setting), so the wait is the right thing to remove and the persistence is not.
    """
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


#: A gate that never sleeps, so a retrying test costs no wall-clock either.
def _instant_gate() -> PacingGate:
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


def _serve(status: int) -> Callable[[httpx.Request], httpx.Response]:
    return lambda request: httpx.Response(status, json={"detail": "upstream is unwell"})


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def _gnomad(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    client = GnomadClient(settings=GnomadSettings(), gate=_instant_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lambda: client._post("query { x }")


def _eutils(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    client = EutilsClient(settings=EutilsSettings(), gate=_instant_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lambda: client._get("esummary.fcgi", {"db": "snp", "id": "334"})


def _cpic(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    client = CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    return lambda: client._get("allele", {"select": "*"})


def _cpic_row_count(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    """`row_count` is listed as its own client here on purpose: it bypassed `_get` entirely, so it
    was the one method with no retry and no translation — and the one the snapshot builder uses to
    refuse a short read."""
    client = CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    return lambda: client.row_count("allele")


def _ontology(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    """OLS4/HGNC. RM97 left this one behind, and the guard below is why nobody noticed (RM101)."""
    client = OntologyClient(gate=_instant_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lambda: client.trait("HP:0000118")


def _pharmvar(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    client = PharmVarClient(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        gate=_instant_gate(),
    )
    return lambda: client._get("alleles", {"geneSymbol": "CYP2C9"})


#: `(label, builder, the error type this client's callers are told to catch)`.
CLIENTS = [
    ("gnomad", _gnomad, GnomadError),
    ("eutils", _eutils, EutilsError),
    ("cpic", _cpic, CpicError),
    ("cpic.row_count", _cpic_row_count, CpicError),
    ("pharmvar", _pharmvar, PharmVarError),
    # `IdentifierUnavailable` rather than its parent on purpose: it is strictly the stronger
    # assertion, since passing it also proves an `except IdentifierCheckError` still fires.
    ("identifiers", _ontology, IdentifierUnavailable),
]


def test_every_network_client_in_the_tier_is_covered() -> None:
    """Guard the premise: a new client must not be able to ship without joining this file.

    **This guard was itself the RM101 defect.** It read a hand-written tuple of eight modules, and
    `identifiers` was not one of them — so `OntologyClient` was invisible here for RM97's whole
    release while leaking a raw `httpx.HTTPStatusError` from both of its methods. A registry-iterating
    guard is only as complete as its registry (`@registry-completeness`), and a list of modules
    someone has to remember to extend is not a registry. It now walks the package.

    The criterion is the one this docstring always claimed: a class that owns an `httpx` transport.
    That is what separates a network client from `CpicSnapshotClient` / `PharmVarSnapshotClient`,
    which answer the same questions from a built snapshot and never open a socket — so they are absent
    by construction rather than by exemption, and no longer need naming below.
    """
    import importlib
    import inspect
    import pkgutil

    import just_dna_enricher

    discovered: set[str] = set()
    for module_info in pkgutil.iter_modules(list(just_dna_enricher.__path__)):
        module = importlib.import_module(f"just_dna_enricher.{module_info.name}")
        for name, obj in vars(module).items():
            if not (inspect.isclass(obj) and obj.__module__ == module.__name__):
                continue
            if not name.endswith("Client"):
                continue
            if "httpx" not in inspect.getsource(obj):
                continue  # a snapshot reader, not a network client
            discovered.add(f"{module_info.name}.{name}")

    covered = {label.split(".")[0] for label, _builder, _error in CLIENTS}
    #: Named rather than silently skipped, so each exemption is a decision a reader can dispute.
    exempt = {
        # These three share a base whose retry story differs, and are exercised by their own suite
        # against real recorded payloads. Extending the contract to them is worth doing and is wider
        # than this item. `EuropePmcClient.fulltext` is deliberately *not* a leak: it catches httpx
        # and returns `None`, the tri-state withhold this tier uses for "could not be retrieved".
        "literature.CrossrefClient",
        "literature.EuropePmcClient",
        "literature.PmcIdConverterClient",
        # Same reason, plus: `GwasError` is both the client's and the pass's type, so there is no
        # cross-module mismatch here for a caller to fall through.
        "gwas.GwasCatalogClient",
        # Raises nothing at all: every httpx path returns `None` or `[]`, which is the withhold. A
        # contract test asserting an error type would be asserting the wrong contract.
        "grch37.Grch37Client",
    }
    uncovered = {name for name in discovered if name.split(".")[0] not in covered}
    assert uncovered == exempt, sorted(uncovered.symmetric_difference(exempt))


@pytest.mark.parametrize("label,builder,error", CLIENTS, ids=[c[0] for c in CLIENTS])
def test_a_server_error_surfaces_as_the_tiers_own_error(label, builder, error) -> None:
    """A persistent 5xx must arrive as this tier's error type, never as `httpx.HTTPStatusError`."""
    call = builder(_serve(503))
    with pytest.raises(error) as caught:
        call()
    assert not isinstance(caught.value, httpx.HTTPError), (
        f"{label} leaked an httpx exception through its own error type"
    )


@pytest.mark.parametrize("label,builder,error", CLIENTS, ids=[c[0] for c in CLIENTS])
def test_an_exhausted_transport_failure_surfaces_as_the_tiers_own_error(
    label, builder, error
) -> None:
    """The other leg, and the one that is easy to miss.

    A transport error is deliberately re-raised bare inside the retried half so the decorator can
    match it — which is correct, and means the translation has to happen in the *outer* method or the
    exception escapes raw the moment the attempts run out. `reraise=True` on every one of these
    clients makes that certain rather than unlikely.
    """
    call = builder(_refuse)
    with pytest.raises(error):
        call()


#: Clients for which a 404 is a real answer rather than a failure, with what it answers.
#:
#: This is a per-client fact and not a tier-wide one, which the RM101 pass found by adding a client
#: that disagreed. OLS4 and HGNC answer 404 for "no such term / no such symbol", and both callers
#: read it as `absent` — so raising there would convert an answered question into an unasked one,
#: the collapse this tier refuses everywhere else. Keeping the case in the table rather than dropping
#: the client from it means the *semantics* are asserted either way, and a client that silently
#: changed its mind about 404 fails one of these two tests.
FOUR_OH_FOUR_IS_AN_ANSWER = {"identifiers"}


@pytest.mark.parametrize("label,builder,error", CLIENTS, ids=[c[0] for c in CLIENTS])
def test_a_client_error_is_not_swallowed_into_a_wrong_answer(label, builder, error) -> None:
    """A 404 is a failure, not an empty result — except where it is the source's way of saying absent.

    `row_count` is why this is here: before the repair a 5xx made it return `None`, which the
    snapshot builder reads as "CPIC does not report a count" — a wrong answer rather than an error,
    and the one failure mode a `pytest.raises` on the happy path would never surface.
    """
    call = builder(_serve(404))
    if label in FOUR_OH_FOUR_IS_AN_ANSWER:
        result = call()  # must not raise, and must not be mistaken for an error either
        assert result is not None
        return
    with pytest.raises(error):
        call()
