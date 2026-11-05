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
import re
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import just_dna_enricher
import pytest
from just_dna_enricher import cpic_build, literature
from just_dna_enricher.acmg import AcmgListUnavailable, fetch_acmg_page
from just_dna_enricher.civic_api import CivicApiClient
from just_dna_enricher.civic_citations import check_evidence_status_currency, read_studies
from just_dna_enricher.clingen import ClinGenUnavailable, fetch_curation_list, parse_curation_list
from just_dna_enricher.clingen_allele import ClingenAlleleClient
from just_dna_enricher.clingen_allele import _parse as _car_parse
from just_dna_enricher.clinpgx_build import probe_archive_dates
from just_dna_enricher.clinvar_gkm import ClinVarGkmClient, lane_currency
from just_dna_enricher.cpic import CpicClient
from just_dna_enricher.cpic_build import CpicBuildError
from just_dna_enricher.ensembl import EnsemblResolver, EnsemblSettings
from just_dna_enricher.eutils import EutilsClient, EutilsError, EutilsSettings, is_missing
from just_dna_enricher.frequencies import FrequencyUnavailable, enrich_frequencies
from just_dna_enricher.gene_validity import GeneValidityUnavailable, fetch_validity_export
from just_dna_enricher.gnomad import GnomadClient, GnomadSettings
from just_dna_enricher.grch37 import Grch37Client
from just_dna_enricher.identifiers import IdentifierUnavailable, OntologyClient
from just_dna_enricher.literature import (
    CrossrefClient,
    EuropePmcClient,
    FulltextRetired,
    FulltextUnavailable,
    PmcBiocClient,
    PmcIdConverterClient,
    enrich_literature,
)
from just_dna_enricher.mane_build import ManeUnavailable, discover_current_release
from just_dna_enricher.net import (
    RETIRED,
    UNREACHABLE,
    EndpointRetired,
    PacingGate,
    Withholding,
    aggregate_reason,
    could_not_ask_reason,
    release_dataset,
    stream_to_file,
    withheld_reason,
)
from just_dna_enricher.sequences import SequenceProxy, verify_reference_alleles
from just_dna_format.resolution import ResolutionRow

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
    """The set of `*Retired` exception classes equals the set marked `EndpointRetired`, both walked.

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
            if name.endswith("Retired") and obj is not EndpointRetired:
                named.add(f"{module.__name__}.{name}")
            if issubclass(obj, EndpointRetired) and obj is not EndpointRetired:
                marked.add(f"{module.__name__}.{name}")
    assert named, "the walk found no *Retired class at all"
    assert named == marked, sorted(named ^ marked)


def _writes_unreachable(node: ast.AST) -> bool:
    """`node` spells the outage reason: the literal, a `*_unreachable` name, the constant, or an
    f-string that opens with the word.

    The f-string arm is the 2026-11-05 widening (audit round 2): `clinvar_gkm.lane_currency` wrote
    `f"unreachable ({exc})"`, a `JoinedStr` whose constant piece is `"unreachable ("`, which an
    equality on `ast.Constant` never matched, so the walk passed over a handler recording a 410 as an
    outage.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value == UNREACHABLE or node.value.endswith("_unreachable")
    if isinstance(node, ast.Name):
        return node.id == "UNREACHABLE"
    if isinstance(node, ast.JoinedStr) and node.values:
        lead = node.values[0]
        return (
            isinstance(lead, ast.Constant)
            and isinstance(lead.value, str)
            and re.match(rf"{UNREACHABLE}\b", lead.value) is not None
        )
    return False


def _handler_violations() -> list[str]:
    """Every `except` arm that writes an `unreachable` reason without asking `could_not_ask_reason`.

    A handler holds the exception, so it is the one place the reason can be read off it; a literal
    `"unreachable"` (or a `*_unreachable` spelling, or the `UNREACHABLE` constant, or an f-string
    opening with the word) written there without the helper records a 410 as an outage — the RM354
    shape eight handlers had.
    """
    found: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for handler in (n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)):
            nodes = [n for stmt in handler.body for n in ast.walk(stmt)]
            writes = any(_writes_unreachable(n) for n in nodes)
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


@pytest.mark.parametrize(
    "written",
    ["'unreachable'", "f'unreachable ({exc})'", "UNREACHABLE", "'pgs_unreachable'"],
    ids=["literal", "f-string", "constant", "suffix"],
)
def test_the_handler_walk_sees_a_handler_that_ignores_the_exception(written: str) -> None:
    """The walk is not vacuous: every spelling a pre-RM361 handler used is caught, through the same
    predicate the walk applies — the f-string is the one `clinvar_gkm` slipped through on."""
    source = (
        "def f(client):\n"
        "    try:\n"
        "        client.ask()\n"
        "    except RuntimeError as exc:\n"
        f"        return {written}\n"
    )
    handler = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ExceptHandler))
    assert any(_writes_unreachable(n) for s in handler.body for n in ast.walk(s))


def test_an_f_string_that_only_mentions_the_word_is_not_a_reason() -> None:
    """The f-string arm keys on the reason opening the string, so a sentence naming an outage in its
    middle (a log line) is not read as a recorded reason."""
    node = ast.parse("f'the host was unreachable ({exc})'", mode="eval").body
    assert not _writes_unreachable(node)


def test_a_group_of_unanswered_requests_leads_with_the_retired_one() -> None:
    assert aggregate_reason([UNREACHABLE, RETIRED, UNREACHABLE]) == RETIRED
    assert aggregate_reason([UNREACHABLE]) == UNREACHABLE
    assert aggregate_reason([]) == UNREACHABLE


# ── every owner of a transport names its 410, a function as much as a class (audit round 2) ──────────
#
# RM361's guards reached a 410 through the client roster, and that roster walks *classes*. Every
# instance the 0.8 audit's second round found sat in a module-level function that calls `httpx` itself:
# the shared bulk downloader (`net.stream_to_file`, behind every bulk-download lane), ClinGen's curation list,
# the gene-validity exports, MANE's release discovery, ACMG's page. Each raised its lane's outage type
# for a 410, so the message said "could not fetch" about a source that had moved. The walk below finds
# the owners by what they call, never by a name (`@client-exception-contract`).

#: The `httpx` entry points that open a connection: owning one of these is the criterion.
_TRANSPORT_CALLS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "request", "stream", "Client", "AsyncClient"}
)


def _opens_a_transport(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in _TRANSPORT_CALLS
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "httpx"
        for n in ast.walk(node)
    )


def _package_trees() -> list[tuple[str, ast.Module]]:
    """`(dotted module name, parsed tree)` for every source file; `generated/` is protoc output."""
    out = []
    for path in sorted(p for p in _SRC.rglob("*.py") if "generated" not in p.relative_to(_SRC).parts):
        parts = path.relative_to(_SRC).with_suffix("").parts
        name = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        out.append((name, ast.parse(path.read_text(encoding="utf-8"))))
    return out


def _import(module_name: str):
    """The module a `_package_trees` name is, the package root's `__init__` (named `""`) included."""
    return importlib.import_module(f"just_dna_enricher.{module_name}" if module_name else "just_dna_enricher")


def _transport_owners() -> tuple[set[str], set[str]]:
    """Every module-level class and every module-level function that calls an `httpx` transport."""
    classes: set[str] = set()
    functions: set[str] = set()
    for module, tree in _package_trees():
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and _opens_a_transport(node):
                classes.add(f"{module}.{node.name}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _opens_a_transport(node):
                functions.add(f"{module}.{node.name}")
    return classes, functions


def test_every_class_owning_a_transport_names_its_410() -> None:
    """A class that opens a connection either withholds (and says `retired` through `Withholding`) or
    raises, and then its module declares the `*Retired` it raises. The behaviour of each raising client
    is `test_client_exception_contract.py`'s; this is the half that walks by transport, not by roster."""
    classes, _ = _transport_owners()
    assert classes, "the walk found no class owning a transport"
    unnamed = []
    for label in sorted(classes):
        module_name, name = label.rsplit(".", 1)
        module = _import(module_name)
        if issubclass(getattr(module, name), Withholding):
            continue
        if not any(
            inspect.isclass(obj) and issubclass(obj, EndpointRetired) and obj.__module__ == module.__name__
            for obj in vars(module).values()
        ):
            unnamed.append(label)
    assert unnamed == []


_GONE_BODY = "This file moved; see the v2 guide."
_URL = "https://example.invalid/list.txt"


class _LaneUnavailable(RuntimeError):
    """A lane's could-not-ask type, standing in for every `stream_to_file` caller's."""


class _LaneRetired(_LaneUnavailable, EndpointRetired):
    """Its `*Retired`, as each lane declares one beside its `*Unavailable`."""


def _download(tmp_path: Path) -> object:
    return stream_to_file(
        tmp_path / "f.bin", _URL, error_cls=_LaneUnavailable, retired=_LaneRetired, what="a file"
    )


#: `label -> (the call, the could-not-ask type its callers catch)`: every module-level function that
#: opens a transport and raises. Asserted equal to the walk, so a new one cannot ship without a row.
FETCHERS: dict[str, tuple[Callable[[Path], object], type[Exception]]] = {
    "net.stream_to_file": (_download, _LaneUnavailable),
    "clingen.fetch_curation_list": (lambda _tmp: fetch_curation_list(_URL), ClinGenUnavailable),
    "gene_validity.fetch_validity_export": (
        lambda _tmp: fetch_validity_export(_URL),
        GeneValidityUnavailable,
    ),
    "mane_build.discover_current_release": (lambda _tmp: discover_current_release(), ManeUnavailable),
    "acmg.fetch_acmg_page": (lambda _tmp: fetch_acmg_page(_URL), AcmgListUnavailable),
}

#: The one module-level owner whose contract is a withheld value: the ClinPGx archive probe answers
#: `None` for an archive it could not date, whatever the failure, because it gates nothing (RM283).
#: A 410 there is one more could-not-date; pinned below as the value.
FETCHERS_THAT_WITHHOLD = {"clinpgx_build.probe_archive_dates"}


def test_every_function_owning_a_transport_is_walked() -> None:
    _, functions = _transport_owners()
    assert functions == set(FETCHERS) | FETCHERS_THAT_WITHHOLD, sorted(
        functions ^ (set(FETCHERS) | FETCHERS_THAT_WITHHOLD)
    )


def _serve(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    """Route the module-level `httpx.get` and `httpx.stream` through a mock transport."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "get", lambda url, **kw: client.get(url, **kw))
    monkeypatch.setattr(httpx, "stream", lambda method, url, **kw: client.stream(method, url, **kw))


def _refuse_connection(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


@pytest.mark.parametrize("label", sorted(FETCHERS))
def test_a_410_from_a_function_owning_a_transport_is_its_lanes_retired(
    label: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The type, not only the reason: `could_not_ask_reason` reads a bare 410 through `__cause__`, so
    a reason-only check passed on every one of these while the message said "could not fetch"."""
    call, unavailable = FETCHERS[label]
    _serve(monkeypatch, lambda request: httpx.Response(410, text=_GONE_BODY))
    with pytest.raises(unavailable) as caught:
        call(tmp_path)
    assert isinstance(caught.value, EndpointRetired), f"{label}: {type(caught.value).__name__}"
    assert could_not_ask_reason(caught.value) == RETIRED
    assert "HTTP 410" in str(caught.value) and "v2 guide" in str(caught.value), str(caught.value)
    assert list(tmp_path.iterdir()) == [], "a retired download left a partial behind"


@pytest.mark.parametrize("leg", ["503", "transport"])
@pytest.mark.parametrize("label", sorted(FETCHERS))
def test_an_outage_from_a_function_owning_a_transport_stays_its_lanes_could_not_ask(
    label: str, leg: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call, unavailable = FETCHERS[label]
    handler = _refuse_connection if leg == "transport" else (lambda request: httpx.Response(503))
    _serve(monkeypatch, handler)
    with pytest.raises(unavailable) as caught:
        call(tmp_path)
    assert not isinstance(caught.value, EndpointRetired), f"{label} named a {leg} retired"
    assert could_not_ask_reason(caught.value) == UNREACHABLE


def test_a_retired_download_keeps_the_lanes_remedy_and_names_the_host_that_answered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 410 may be the operator's pick (a release, a URL) rather than the enricher's, so the lane's own
    remedy stays in the message; and after a redirect the host that answered is the one named."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.invalid":
            return httpx.Response(303, headers={"Location": "https://bucket.example.test/f"})
        return httpx.Response(410, text=_GONE_BODY)

    _serve(monkeypatch, handler)
    with pytest.raises(_LaneRetired) as caught:
        stream_to_file(
            tmp_path / "f.bin",
            _URL,
            error_cls=_LaneUnavailable,
            retired=_LaneRetired,
            what="the release file",
            remedy="Pass --source with a copy you already hold.",
        )
    message = str(caught.value)
    assert message.startswith("bucket.example.test retired"), message
    assert "the release file" in message and "--source" in message, message


def test_the_archive_probe_withholds_a_410_like_any_failed_head() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(410, text=_GONE_BODY)))
    dates = probe_archive_dates(client)
    assert dates.dates and all(stamp is None for stamp in dates.dates.values())


def test_every_bulk_download_names_its_lanes_retired_type() -> None:
    """Each `stream_to_file` call passes a `retired=` that is its `error_cls`'s `*Retired`.

    Resolved from the calling module's own names, so a lane cannot pass a type of another family (a
    caller's `except` would then miss it) or one without the marker (`could_not_ask_reason` would still
    read the cause, but the message and the type would say outage).
    """
    calls = 0
    wrong: list[str] = []
    for module_name, tree in _package_trees():
        module = _import(module_name)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "stream_to_file"):
                continue
            calls += 1
            keywords = {k.arg: k.value for k in node.keywords}
            error, retired = keywords.get("error_cls"), keywords.get("retired")
            if not (isinstance(error, ast.Name) and isinstance(retired, ast.Name)):
                wrong.append(f"{module_name}:{node.lineno} names no retired type")
                continue
            error_cls, retired_cls = getattr(module, error.id), getattr(module, retired.id)
            if not (issubclass(retired_cls, error_cls) and issubclass(retired_cls, EndpointRetired)):
                wrong.append(f"{module_name}:{node.lineno} {retired.id} is not {error.id}'s *Retired")
    assert calls, "the walk found no bulk download"
    assert wrong == []


def test_a_retired_clinvar_gkm_manifest_leaves_currency_unchecked_as_retired(tmp_path: Path) -> None:
    """`lane_currency` wrote `unreachable (…)` for every `ClinVarGkmUnavailable`, its `*Retired` too."""

    def serve(status: int) -> ClinVarGkmClient:
        transport = httpx.MockTransport(lambda request: httpx.Response(status, text=_GONE_BODY))
        return ClinVarGkmClient(client=httpx.Client(transport=transport), gate=_gate())

    retired = lane_currency(tmp_path, client=serve(410))
    assert retired.unchecked is not None and retired.unchecked.startswith(f"{RETIRED} ("), retired.unchecked
    assert retired.behind is None
    outage = lane_currency(tmp_path, client=serve(503))
    assert outage.unchecked is not None and outage.unchecked.startswith(f"{UNREACHABLE} ("), outage.unchecked


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
    # A generous bound: a loaded machine must not turn this decided regex into an undecided one.
    [row] = _run(spec, lambda request: httpx.Response(200, json=_BIOC_CLINVAR), regex_timeout=120.0).rows
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


# ── two clients whose "no record" answer had grown to cover failures (found by the RM361 hunt) ──────


@pytest.mark.parametrize("status", [400, 403, 404, 410, 429, 503])
def test_ensembl_rest_reads_only_its_400_as_no_record(status: int) -> None:
    """A 400 naming the rsID is Ensembl's "no such variation"; every other status answered nothing.

    Before RM361 every 4xx was the empty answer, which `enrich` writes as `not_found` — the fingerprint
    of a fabricated rsID — for a live one asked during a throttle.
    """
    resolver = EnsemblResolver(settings=EnsemblSettings())
    resolver._client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    expected = ([], "ensembl-rest") if status == 400 else (None, None)
    assert resolver.resolve_rsid("rs334") == expected


@pytest.mark.parametrize(
    "payload",
    [{"error": "API rate limit exceeded"}, {"esummaryresult": ["Something went wrong"]}, {"result": {}}],
    ids=["error-envelope", "other-shape", "no-uids"],
)
def test_an_esummary_with_no_summary_block_is_could_not_ask(payload: dict) -> None:
    """A 200 JSON that is not a summary answered nothing about any uid. Before RM361 every uid in the
    batch became NCBI's "no such document", so live rsIDs read `absent` and real PMIDs `not_found`."""
    client = EutilsClient(settings=EutilsSettings(email=None), gate=_gate())
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    with pytest.raises(EutilsError):
        client.esummary("snp", ["334"])


def test_an_esummary_uid_missing_from_a_real_summary_is_still_no_document() -> None:
    """The answered absence is kept: a summary block that lists the batch and omits one uid."""
    client = EutilsClient(settings=EutilsSettings(email=None), gate=_gate())
    body = {"result": {"uids": ["1"], "1": {"uid": "1"}}}
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    assert is_missing(client.esummary("pubmed", ["1", "2"])["2"])


@pytest.mark.parametrize(
    "flag, read", [("Y", True), ("N", False), ("y", True), (None, None), ("", None), ("?", None)]
)
def test_a_europe_pmc_flag_it_did_not_state_is_unknown(flag, read) -> None:
    """A record silent about `isOpenAccess` was written as closed (`False`) before RM361."""
    payload = json.loads(json.dumps(_EPMC_SEARCH))
    record = next(r for r in payload["resultList"]["result"] if r.get("pmid") == _REAL)
    record.pop("isOpenAccess", None)
    if flag is not None:
        record["isOpenAccess"] = flag
    client = EuropePmcClient(gate=_gate())
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    )
    assert client.lookup([_REAL])[_REAL]["is_open_access"] is read


# ── a guard that cannot run is not a guard that passed ──────────────────────────────────────────────


@pytest.mark.parametrize("content_range", [None, "0-0/*", "garbage"], ids=["absent", "star", "garbage"])
def test_a_cpic_table_whose_count_is_unstated_refuses_rather_than_writes(content_range: str | None) -> None:
    """Before RM361 a missing `Content-Range` skipped the short-read guard, so a truncated table was
    written as a complete snapshot."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Prefer") == "count=exact":
            headers = {"Content-Range": content_range} if content_range else {}
            return httpx.Response(200, json=[], headers=headers)
        return httpx.Response(200, json=[{"genesymbol": "CYP2C19"}])

    client = CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(CpicBuildError, match="no count"):
        cpic_build._fetch_all(client, "gene", "*")


def test_a_cpic_table_whose_count_agrees_is_read() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Prefer") == "count=exact":
            return httpx.Response(200, json=[], headers={"Content-Range": "0-0/1"})
        return httpx.Response(200, json=[{"genesymbol": "CYP2C19"}])

    client = CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert cpic_build._fetch_all(client, "gene", "*") == [{"genesymbol": "CYP2C19"}]


# ── the rest of the class: every site the RM361 hunt found, each with the leg that broke it ─────────


def test_a_gnomad_alias_answered_with_an_error_is_unanswered_never_not_found(tmp_path: Path) -> None:
    """A per-alias error (a timeout, an internal error) left a null node, and the pass wrote a
    `not_found` row, which its own comment calls a fact. Now: no row, named as unanswered."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {"v0": None}, "errors": [{"message": "Timeout", "path": ["v0"]}]}
        )

    client = GnomadClient(settings=GnomadSettings(), gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs1801133,G/A,risk,c\n", encoding="utf-8"
    )
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "rs1801133,rs1801133,1,11796321,G,A,GRCh38,0,ensembl-rest,resolved\n",
        encoding="utf-8",
    )
    result = enrich_frequencies(spec, client=client, write=False)
    assert len(result.unanswered) == 1 and result.covered == []
    assert result.missing == [] and not [r for r in result.rows if r.status == "not_found"]
    with pytest.raises(FrequencyUnavailable):
        enrich_frequencies(spec, client=client, write=False, mode="strict")


def test_a_gnomad_absence_is_still_an_absence() -> None:
    """The pathless "Variant not found" is gnomAD's answer and stays one."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"v0": None}, "errors": [{"message": "Variant not found"}]})

    client = GnomadClient(settings=GnomadSettings(), gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    assert client.fetch_frequencies(["9-1-A-G"]) == {} and client.unanswered == {}


def test_a_short_civic_read_withholds_the_withdrawn_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    """CIViC states its own total; a read short of it cannot say a recorded paper is gone."""
    api = CivicApiClient(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    page = {"evidenceItems": {"totalCount": 2, "nodes": [], "pageInfo": {"hasNextPage": False}}}
    monkeypatch.setattr(api, "_post", lambda variables: page)
    assert api.evidence_items(12) == [] and 12 in api.short_reads


def test_an_unreadable_studies_table_is_not_nothing_to_check(tmp_path: Path) -> None:
    (tmp_path / "studies.csv").write_text("rsid,pmid,start\nrs1,123,not-a-number\n", encoding="utf-8")
    assert read_studies(tmp_path) is None
    check = check_evidence_status_currency([], [], None, reference=None)
    assert check.skip != "nothing_to_check" and "could not be read" in check.detail()


@pytest.mark.parametrize("released, label", [("2026-08-01", "lane_2026-08-01"), (None, "lane"), ("", "lane")])
def test_a_release_the_file_did_not_state_is_withheld_from_the_label(released, label) -> None:
    assert release_dataset("lane", released) == label


def test_a_clingen_list_with_no_release_line_states_none() -> None:
    _ratings, released = parse_curation_list("#Gene Symbol\tGene ID\nBRCA1\t672\n")
    assert released is None


def test_a_reference_read_that_fails_is_not_a_clean_check() -> None:
    """Every read failing was `ran(subjects=0)` and a build record saying no ref disagreed."""

    class _Failing(SequenceProxy):
        def proxy(self):
            return object()

        def subsequence(self, accession, start, end):
            return None

    rows = [
        ResolutionRow(variant_key="rs1", rsid="rs1", chrom="1", start=11796321, ref="G", status="resolved")
    ]
    check = verify_reference_alleles(rows, sequences=_Failing())
    assert (check.not_checked, check.subjects, check.unread) == ("unreachable", 0, 1)


def _ontology(body: dict) -> OntologyClient:
    client = OntologyClient(gate=_gate())
    client._client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    return client


@pytest.mark.parametrize("body", [{"error": "x"}, {"_embedded": "nope"}], ids=["no-terms", "wrong-type"])
def test_an_ols4_body_of_another_shape_is_could_not_ask(body: dict) -> None:
    with pytest.raises(IdentifierUnavailable):
        _ontology(body).trait("EFO:0001645")


def test_an_ols4_empty_page_is_still_absent() -> None:
    assert _ontology({"page": {"totalElements": 0}}).trait("EFO:0001645").state == "absent"


def test_an_hgnc_body_of_another_shape_is_could_not_ask() -> None:
    with pytest.raises(IdentifierUnavailable):
        _ontology({"error": "x"}).gene("BRCA1")
    assert _ontology({"response": {"numFound": 0, "docs": []}}).gene("NOTAGENE").state == "unknown"


def test_a_registry_body_of_another_shape_is_unchecked() -> None:
    assert _car_parse("CA1", {"errorType": "x"}).outcome == "unchecked"
    assert _car_parse("CA1", {"genomicAlleles": [], "externalRecords": {}}).outcome == "no_identity"


# ── a withholding client says `retired` without raising ─────────────────────────────────────────────


#: `(label, client factory, the call)`: every class that mixes in `Withholding`, walked below.
WITHHOLDING = {
    "literature.CrossrefClient": (lambda: CrossrefClient(gate=_gate()), lambda c: c.exists("10.1038/ng826")),
    "literature.PmcIdConverterClient": (
        lambda: PmcIdConverterClient(gate=_gate()),
        lambda c: c.resolve(["PMC1"]),
    ),
    "literature.PmcBiocClient": (lambda: PmcBiocClient(gate=_gate()), lambda c: c.fulltext("PMC1")),
    "grch37.Grch37Client": (lambda: Grch37Client(gate=_gate()), lambda c: c.variants_at("6", 26093141)),
    "ensembl.EnsemblResolver": (
        lambda: EnsemblResolver(settings=EnsemblSettings()),
        lambda c: c.resolve_rsid("rs334"),
    ),
    "clingen_allele.ClingenAlleleClient": (lambda: ClingenAlleleClient(), lambda c: c.resolve("CA341482")),
}


def test_every_withholding_client_is_walked() -> None:
    found = {
        f"{module.__name__.removeprefix('just_dna_enricher.')}.{name}"
        for module in _modules()
        for name, obj in vars(module).items()
        if inspect.isclass(obj)
        and issubclass(obj, Withholding)
        and obj is not Withholding
        and obj.__module__ == module.__name__
    }
    assert found == set(WITHHOLDING)


@pytest.mark.parametrize("label", sorted(WITHHOLDING))
def test_a_withholding_client_names_a_410_and_still_withholds(label: str) -> None:
    factory, call = WITHHOLDING[label]
    for status, reason in ((410, RETIRED), (503, UNREACHABLE)):
        client = factory()
        if hasattr(client, "gate"):
            client.gate = _gate()
        client._client = httpx.Client(
            transport=httpx.MockTransport(lambda r, s=status: httpx.Response(s, text="gone"))
        )
        call(client)  # never raises: the contract is a withheld value
        assert withheld_reason(client) == reason, f"{label} after a {status}"


# ── the review's cases: an answer stays an answer ───────────────────────────────────────────────────


def test_a_gnomad_alias_not_found_is_an_absence_and_an_earlier_error_does_not_stick() -> None:
    answers = iter(
        [
            {"data": {"v0": None}, "errors": [{"message": "Timeout", "path": ["v0"]}]},
            {"data": {"v0": None}, "errors": [{"message": "Gene not found", "path": ["v0"]}]},
        ]
    )
    client = GnomadClient(settings=GnomadSettings(), gate=_gate())
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=next(answers)))
    )
    client.fetch_gene_constraint(["NOTAGENE"])
    assert set(client.unanswered) == {"NOTAGENE"}
    client.fetch_gene_constraint(["NOTAGENE"])
    assert client.unanswered == {}, "gnomAD's later 'not found' is its answer"


def test_an_esummary_naming_only_invalid_uids_is_no_such_document() -> None:
    client = EutilsClient(settings=EutilsSettings(email=None), gate=_gate())
    body = {"esummaryresult": ["Invalid uid 99999999999 at position=0"]}
    client._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    assert is_missing(client.esummary("pubmed", ["99999999999"])["99999999999"])


def test_a_gated_or_refused_hub_is_not_nothing_published() -> None:
    from just_dna_enricher.download import _hub_says_absent

    class RepositoryNotFoundError(Exception):
        pass

    class GatedRepoError(RepositoryNotFoundError):
        pass

    refused = RepositoryNotFoundError("401")
    refused.response = httpx.Response(401)  # type: ignore[attr-defined]
    assert _hub_says_absent(RepositoryNotFoundError("404"))
    assert not _hub_says_absent(GatedRepoError("gated"))
    assert not _hub_says_absent(refused)
