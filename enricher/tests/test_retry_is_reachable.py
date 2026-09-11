"""A `@retry` whose own body swallows what it retries is a decorator that does nothing (RM208).

`CrossrefClient.exists` carried `@retry(stop=attempt_floor(3), retry=retry_if_exception_type((
httpx.TransportError, httpx.TimeoutException)))` and caught `httpx.HTTPError` inside — the
**superclass of both**. So a `ConnectError` became `None` before tenacity could see it, the client
made **one** upstream request where three were asked for, and `attempt_floor` — the knob
`@retry-attempt-floor` exists so a deployment can raise — moved nothing at all.

**Why a static guard and not three more behavioural cases.** The defect is not "Crossref is wrong",
it is a *shape*: an `except` inside a retried body naming an ancestor of a retried type. Nothing about
it is visible in a passing test, in a type checker, or in review — the decorator and the `except` are
forty lines apart and each is individually correct. `test_client_exception_contract.py` could not see
it either, because `literature.CrossrefClient` sits in that file's named `exempt` set; a guard that
walks only the roster inherits the roster's exemptions, which is the RM101 blind spot one file over.
This one walks the **package**, so an exemption cannot hide a client from it and a new client is
covered the day it is written.

The rule it enforces is the split the tier already uses everywhere else — `eutils._request` /
`_get`, `cpic._request`, `gnomad._request`: **the retrying half is its own function and the
translation sits outside it** (`@client-exception-contract`: retry, then translate, both legs).
Crossref was the one client that never got the split.

`reraise=True` is what makes the split safe for a three-valued contract: after the attempts are spent
the original exception arrives back at the caller's `except`, so `exists` still answers `None` for
"could not be asked" rather than propagating. The behavioural test below pins both halves — the
attempt count *and* the answer — because fixing one by breaking the other would be a worse bug.
"""

import ast
import importlib
import inspect
import pkgutil
from pathlib import Path

import httpx
import just_dna_enricher
from just_dna_enricher.literature import CrossrefClient
from just_dna_enricher.net import PacingGate, retry_attempts


def _retried_types(decorator: ast.Call) -> list[type]:
    """The exception classes a `@retry(...)` decorator names in `retry_if_exception_type(...)`."""
    found: list[type] = []
    for node in ast.walk(decorator):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "retry_if_exception_type"):
            continue
        for arg in node.args:
            members = arg.elts if isinstance(arg, ast.Tuple) else [arg]
            for member in members:
                # Only `httpx.X` is resolvable without importing the module under test; a tier-local
                # error type cannot be an ancestor of an httpx one, so skipping it loses nothing.
                if isinstance(member, ast.Attribute) and getattr(member.value, "id", None) == "httpx":
                    resolved = getattr(httpx, member.attr, None)
                    if isinstance(resolved, type):
                        found.append(resolved)
    return found


def _caught_types(func: ast.FunctionDef) -> list[type]:
    """The `httpx.*` classes any `except` in this function's own body names."""
    caught: list[type] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        # A handler whose whole body is `raise` swallows nothing — it exists so the decorator can
        # match the type, which is the correct shape and not the defect. `gwas._get` had exactly one
        # of these and was a true negative here; its real defect was the opposite, a leg nothing
        # translated once the attempts were spent, and that is pinned in the contract suite instead.
        if all(isinstance(stmt, ast.Raise) and stmt.exc is None for stmt in node.body):
            continue
        members = node.type.elts if isinstance(node.type, ast.Tuple) else [node.type]
        for member in members:
            if isinstance(member, ast.Attribute) and getattr(member.value, "id", None) == "httpx":
                resolved = getattr(httpx, member.attr, None)
                if isinstance(resolved, type):
                    caught.append(resolved)
    return caught


def _retried_functions() -> list[tuple[str, ast.FunctionDef, list[type]]]:
    """Every `@retry`-decorated function in the package, with the httpx types it retries on."""
    out: list[tuple[str, ast.FunctionDef, list[type]]] = []
    for info in pkgutil.iter_modules(list(just_dna_enricher.__path__)):
        module = importlib.import_module(f"just_dna_enricher.{info.name}")
        source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and getattr(decorator.func, "id", None) == "retry":
                    retried = _retried_types(decorator)
                    if retried:
                        out.append((f"{info.name}.{node.name}", node, retried))
    return out


def test_the_walk_finds_the_retrying_functions_it_claims_to() -> None:
    """A guard that discovers nothing passes silently, which is the failure this one is about."""
    found = {name for name, _node, _types in _retried_functions()}
    assert len(found) >= 8, sorted(found)
    assert any(name.startswith("literature.") for name in found), sorted(found)


def test_no_retried_body_swallows_what_its_decorator_retries() -> None:
    """The shape, across the package: an `except` naming an ancestor of a retried type.

    Equality against an empty set rather than a count, so a new client joins the guard by existing
    rather than by somebody remembering to list it.
    """
    offenders: list[str] = []
    for name, node, retried in _retried_functions():
        for caught in _caught_types(node):
            swallowed = [exc for exc in retried if issubclass(exc, caught)]
            if swallowed:
                offenders.append(
                    f"{name}: `except {caught.__name__}` swallows "
                    f"{', '.join(exc.__name__ for exc in swallowed)}, which its own @retry asks to retry"
                )
    assert offenders == [], offenders


def _counting_client(handler) -> tuple[CrossrefClient, dict[str, int]]:
    calls = {"n": 0}

    def counted(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return handler(request)

    client = CrossrefClient(gate=PacingGate(interval=0.0))
    client._client = httpx.Client(transport=httpx.MockTransport(counted))
    return client, calls


def test_a_transport_failure_is_retried_and_then_withheld() -> None:
    """Both halves at once: the attempts actually happen, and the answer is still the withhold.

    The attempt count is derived from the decorator rather than written as `3`, so raising
    `attempt_floor` moves this test with it instead of against it.
    """

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client, calls = _counting_client(refuse)
    answer = client.exists("10.1000/xyz")

    assert answer is None, "a transport failure is could-not-ask, never a finding against the module"
    assert calls["n"] == retry_attempts(CrossrefClient._request.retry.stop.default)


def test_a_definite_answer_is_not_retried() -> None:
    """404 is Crossref answering. Retrying it would spend the budget on a settled question."""
    client, calls = _counting_client(lambda request: httpx.Response(404))

    assert client.exists("10.1000/no-such-doi") is False
    assert calls["n"] == 1


def test_an_unexpected_status_withholds_without_retrying() -> None:
    """A 500 is not in the retry predicate — it withholds on the first answer, as it always did."""
    client, calls = _counting_client(lambda request: httpx.Response(500))

    assert client.exists("10.1000/xyz") is None
    assert calls["n"] == 1
