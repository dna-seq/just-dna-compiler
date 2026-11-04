"""An unknown or failed answer is never recorded as a definite one (RM361).

The house algebra is three-valued, and every guard here is about the third value surviving a boundary:
a 410 that a handler records as an outage, a 429 or a maintenance page that a fulltext client records
as "no copy", a regex that timed out and was counted as a quote missing from the paper. Each was a
separate defect in a separate module, and each is the same one, so the guards below walk the tier
rather than pin one site: the `*Retired` errors by class, the handlers by AST, the quote tallies by
their callers. The client-by-client half (every client's 410 and 503, read through
`could_not_ask_reason`) is in `test_client_exception_contract.py`, beside the roster it walks.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import pkgutil
import time
from pathlib import Path

import httpx
import just_dna_enricher
import pytest
from just_dna_enricher import literature
from just_dna_enricher.eutils import EutilsClient, EutilsSettings
from just_dna_enricher.literature import (
    CrossrefClient,
    EuropePmcClient,
    FulltextRetired,
    FulltextUnavailable,
    PmcBiocClient,
    enrich_literature,
)
from just_dna_enricher.net import RETIRED, UNREACHABLE, PacingGate, RetiredEndpoint, aggregate_reason

_SRC = Path(just_dna_enricher.__file__).resolve().parent
_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_ESUMMARY = json.loads((_ASSETS / "pubmed_esummary_payload.json").read_text())
_EPMC_SEARCH = json.loads((_ASSETS / "europepmc_search_payload.json").read_text())
_BIOC_CLINVAR = json.loads((_ASSETS / "pmc_bioc_PMC5753237.json").read_text())
_BIOC_NO_RESULT = (_ASSETS / "pmc_bioc_no_result.txt").read_text()
_REAL = "29165669"  # the ClinVar paper, in PMC as PMC5753237
_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_MAINTENANCE = "<html><body>Scheduled maintenance</body></html>"


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def _modules() -> list:
    """Every module of the package, the `cli` and `enrich` subpackages included."""
    infos = [
        *pkgutil.iter_modules(list(just_dna_enricher.__path__)),
        *pkgutil.iter_modules(list(importlib.import_module("just_dna_enricher.cli").__path__), prefix="cli."),
        *pkgutil.iter_modules(
            list(importlib.import_module("just_dna_enricher.enrich").__path__), prefix="enrich."
        ),
    ]
    return [importlib.import_module(f"just_dna_enricher.{info.name}") for info in infos]


# ── a 410 is named, and read as `retired` ──────────────────────────────────────────────────────────


def test_every_retired_error_carries_the_marker() -> None:
    """The set of `*Retired` exception classes equals the set marked `RetiredEndpoint`, both walked.

    `could_not_ask_reason` reads the marker; a `*Retired` class without it would be recorded as an
    outage again, and a marked class not named `*Retired` would be one a reader cannot find.
    """
    named: set[str] = set()
    marked: set[str] = set()
    for module in _modules():
        for name, obj in vars(module).items():
            if not (
                inspect.isclass(obj) and issubclass(obj, BaseException) and obj.__module__ == module.__name__
            ):
                continue
            if name.endswith("Retired"):
                named.add(f"{module.__name__}.{name}")
            if issubclass(obj, RetiredEndpoint) and obj is not RetiredEndpoint:
                marked.add(f"{module.__name__}.{name}")
    assert named, "the walk found no *Retired class at all"
    assert named == marked, sorted(named ^ marked)


def _handler_violations() -> list[str]:
    """Every `except` arm that writes an `unreachable` reason without asking `could_not_ask_reason`.

    A handler holds the exception, so it is the one place the reason can be read off it; a literal
    `"unreachable"` (or a `*_unreachable` spelling, or the `UNREACHABLE` constant) written there
    without the helper records a 410 as an outage — the RM354 shape eight handlers had.
    """
    found: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for handler in (n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)):
            nodes = [n for stmt in handler.body for n in ast.walk(stmt)]
            writes = any(
                (isinstance(n, ast.Constant) and isinstance(n.value, str))
                and (n.value == UNREACHABLE or n.value.endswith("_unreachable"))
                or (isinstance(n, ast.Name) and n.id == "UNREACHABLE")
                for n in nodes
            )
            asks = any(
                isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", None)) == "could_not_ask_reason"
                for n in nodes
            )
            if writes and not asks:
                found.append(f"{path.relative_to(_SRC)}:{handler.lineno}")
    return found


def test_no_handler_records_unreachable_without_reading_the_exception() -> None:
    assert _handler_violations() == []


def test_the_handler_walk_sees_a_handler_that_ignores_the_exception(tmp_path: Path) -> None:
    """The walk is not vacuous: the shape every pre-RM361 handler had is caught."""
    source = (
        "def f(client):\n"
        "    try:\n"
        "        client.ask()\n"
        "    except RuntimeError:\n"
        "        return 'unreachable'\n"
    )
    handler = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ExceptHandler))
    assert any(
        isinstance(n, ast.Constant) and n.value == UNREACHABLE for s in handler.body for n in ast.walk(s)
    )


def test_a_group_of_unanswered_requests_leads_with_the_retired_one() -> None:
    assert aggregate_reason([UNREACHABLE, RETIRED, UNREACHABLE]) == RETIRED
    assert aggregate_reason([UNREACHABLE]) == UNREACHABLE
    assert aggregate_reason([]) == UNREACHABLE


# ── the fulltext routes: only a 404 and BioC's recorded body are "no copy" ──────────────────────────


def _gate() -> PacingGate:
    return PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)


def _respond(status: int, body: str | None) -> httpx.Response:
    if body is None:
        return httpx.Response(status)
    return httpx.Response(status, text=body, headers={"content-type": "text/html"})


def _epmc_fulltext(status: int, body: str | None, asked: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return _respond(status, body)

    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lambda: client.fetch_fulltext("PMC5753237")


def _bioc_fulltext(status: int, body: str | None, asked: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return _respond(status, body)

    client = PmcBiocClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lambda: client.fetch_fulltext("PMC5753237")


def _preprint_fulltext(status: int, body: str | None, asked: list[str]):
    """The repository's file list answers; the JATS file is the leg under test."""

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.params.get("type") == "METADATA":
            return httpx.Response(200, json={"files": [{"type": "xml", "filename": "EMS1.nxml"}]})
        return _respond(status, body)

    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    return lambda: client.fetch_preprint_fulltext("PPR1129025")


#: Every route whose answer is three-valued: text, `None` for no copy, or an exception.
FULLTEXT_ROUTES = {
    "europepmc": _epmc_fulltext,
    "bioc": _bioc_fulltext,
    "preprint": _preprint_fulltext,
}

#: `(leg, status, body, outcome)`. `None` is the route's "no copy"; a type is what it must raise.
LEGS = [
    ("404", 404, None, None),
    ("410", 410, "This route is retired; see the v2 guide.", FulltextRetired),
    ("429", 429, None, FulltextUnavailable),
    ("403", 403, None, FulltextUnavailable),
    ("503", 503, None, FulltextUnavailable),
    ("html-200", 200, _MAINTENANCE, FulltextUnavailable),
    ("unparsable-200", 200, "<article><unclosed>", FulltextUnavailable),
]


def test_every_route_with_a_three_valued_fulltext_is_walked() -> None:
    """The routes above are every `fetch_*fulltext` method in the module, walked."""
    walked = {
        f"{cls.__name__}.{name}"
        for cls in (EuropePmcClient, PmcBiocClient, CrossrefClient)
        for name in vars(cls)
        if name.startswith("fetch_") and name.endswith("fulltext")
    }
    assert walked == {
        "EuropePmcClient.fetch_fulltext",
        "PmcBiocClient.fetch_fulltext",
        "EuropePmcClient.fetch_preprint_fulltext",
    }
    assert len(FULLTEXT_ROUTES) == len(walked)


@pytest.mark.parametrize("leg,status,body,outcome", LEGS, ids=[leg[0] for leg in LEGS])
@pytest.mark.parametrize("route", sorted(FULLTEXT_ROUTES))
def test_a_fulltext_route_answers_no_copy_only_when_the_service_said_so(
    route, leg, status, body, outcome
) -> None:
    """Before RM361 every status below 500 was "no copy", which the pass records as permanent."""
    asked: list[str] = []
    call = FULLTEXT_ROUTES[route](status, body, asked)
    if outcome is None:
        assert call() is None
        return
    with pytest.raises(outcome) as caught:
        call()
    if outcome is FulltextUnavailable:
        assert not isinstance(caught.value, FulltextRetired), f"{route} named a {leg} retired"
    if status in (429, 503):
        assert len([u for u in asked if "METADATA" not in u]) > 1, f"{route} did not retry a {status}"


def test_biocs_recorded_no_result_body_is_its_only_200_no_copy() -> None:
    asked: list[str] = []
    assert _bioc_fulltext(200, _BIOC_NO_RESULT, asked)() is None


# ── the pass records the reason, and asks again ─────────────────────────────────────────────────────


def _spec(directory: Path, studies: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n", encoding="utf-8"
    )
    (directory / "studies.csv").write_text(studies, encoding="utf-8")
    return directory


def _run(spec: Path, bioc_handler, **kw):
    def esummary(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ESUMMARY)

    def epmc(request: httpx.Request) -> httpx.Response:
        payload = json.loads(json.dumps(_EPMC_SEARCH))
        for record in payload["resultList"]["result"]:
            record["isOpenAccess"] = "N"  # BioC is the only fulltext rung
        return httpx.Response(200, json=payload)

    eutils = EutilsClient(settings=EutilsSettings(email=None), gate=_gate())
    eutils._client = httpx.Client(transport=httpx.MockTransport(esummary))
    europepmc = EuropePmcClient(gate=_gate())
    europepmc._client = httpx.Client(transport=httpx.MockTransport(epmc))
    bioc = PmcBiocClient(gate=_gate())
    bioc._client = httpx.Client(transport=httpx.MockTransport(bioc_handler))
    crossref = CrossrefClient(contact_email=None, gate=_gate())
    crossref._client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    return enrich_literature(spec, eutils=eutils, europepmc=europepmc, crossref=crossref, bioc=bioc, **kw)


@pytest.mark.parametrize(
    "response, recorded",
    [
        (lambda: httpx.Response(410, text="retired"), RETIRED),
        (lambda: httpx.Response(429), UNREACHABLE),
        (lambda: httpx.Response(200, text=_MAINTENANCE), UNREACHABLE),
    ],
    ids=["410", "429", "html-200"],
)
def test_an_unanswered_fulltext_is_recorded_as_such_and_asked_again(
    tmp_path: Path, response, recorded
) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid,provenance_quote\nrs334,{_REAL},anything\n")
    first = _run(spec, lambda request: response())
    [row] = first.rows
    assert row.fulltext_status == recorded
    asked: list[str] = []

    def healed(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(200, json=_BIOC_CLINVAR)

    [again] = _run(spec, healed).rows
    assert asked, "a row whose question went unanswered was never asked again"
    assert again.fulltext_status == "retrieved"


# ── a regex that could not be evaluated is not a quote missing from the paper ───────────────────────


def test_an_undecided_regex_leaves_the_count_unsettled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the text in hand, a regex whose match could not be completed withholds `quotes_found`.

    Before RM361 it was counted not-found, and `quote_source="fulltext"` settles every quote on the
    row, so the record published a quote checked against the paper and missing from it.
    """
    monkeypatch.setattr(literature, "regex_matches", lambda *_a, **_k: None)
    spec = _spec(tmp_path / "s", f"rsid,pmid,provenance_regex\nrs334,{_REAL},variant\\s+interpretations\n")
    result = _run(spec, lambda request: httpx.Response(200, json=_BIOC_CLINVAR))
    [row] = result.rows
    assert row.quote_source == "fulltext"
    assert row.quotes_found is None
    assert row.quotes_checked() == 0
    assert (result.quotes_checked, result.quotes_unchecked) == (0, 1)


def test_a_decided_regex_still_settles(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "s", f"rsid,pmid,provenance_regex\nrs334,{_REAL},zzz-not-here-zzz\n")
    [row] = _run(spec, lambda request: httpx.Response(200, json=_BIOC_CLINVAR)).rows
    assert (row.quote_source, row.quotes_found, row.quotes_checked()) == ("fulltext", 0, 1)


def test_every_quote_tally_goes_through_the_one_count() -> None:
    """`_study_quote_found` is called by `_quotes_found` alone, so no tally can fold its `None` again.

    Three sites summed it by hand before RM361 (a fresh row, a re-asked one, a DOI-only citation).
    """
    tree = ast.parse((_SRC / "literature.py").read_text(encoding="utf-8"))
    callers = {
        func.name
        for func in ast.walk(tree)
        if isinstance(func, ast.FunctionDef)
        for node in ast.walk(func)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_study_quote_found"
    }
    assert callers == {"_quotes_found"}
