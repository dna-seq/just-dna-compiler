"""No test reaches the network without `JUST_DNA_NETWORK_TESTS=1`, through any client (RM391).

The fence is the root `conftest.py`'s: `socket.getaddrinfo`, `socket.socket.connect`/`connect_ex` and
gRPC's channel constructors refuse every host that is not this machine while a test runs, and
`_fenced_network` fails a test at teardown when it reached one, even if something swallowed the raise.
Before it, 31 tests in 7 files asked ClinGen, Ensembl REST, eutils and the seqrepo proxy and passed
anyway, because each client translated the refused connection into its own "unreachable".

These tests drive every transport the workspace can open into the fence, and assert that the set they
drive is the set the source trees import, so a client added to the enricher is a client added here.
They live in the enricher's suite because the clients do: the format and compiler tiers import none,
and the last test asserts that too (Principle 2).
"""

import ast
import asyncio
import contextlib
import os
import re
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

import grpc
import httpx
import huggingface_hub
import pytest
import requests
from just_dna_enricher import remote

_ROOT = Path(__file__).resolve().parents[2]
#: The host every client is pointed at. Never contacted: the fence refuses it before a packet leaves.
_HOST = "example.org"


async def _httpx_async() -> None:
    async with httpx.AsyncClient() as client:
        await client.get(f"https://{_HOST}/")


#: Every transport, keyed by the import root a source file would name, with a call that reaches out.
#: `huggingface_hub` goes through `HfApi`, which RM372's name fence does not replace, so the refusal
#: below is the transport's, not that fence's.
_CLIENTS: dict[str, Callable[[], object]] = {
    "httpx": lambda: httpx.get(f"https://{_HOST}/", timeout=5),
    "httpx (async)": lambda: asyncio.run(_httpx_async()),
    "requests": lambda: requests.get(f"https://{_HOST}/", timeout=5),
    "urllib.request": lambda: urllib.request.urlopen(f"https://{_HOST}/", timeout=5),
    "huggingface_hub": lambda: huggingface_hub.HfApi(endpoint=f"https://{_HOST}").model_info("x/y"),
    "grpc (secure)": lambda: grpc.secure_channel(f"{_HOST}:443", grpc.ssl_channel_credentials()),
    "grpc (insecure)": lambda: grpc.insecure_channel(f"dns:///{_HOST}:443"),
    "grpc (an address list)": lambda: grpc.insecure_channel(f"ipv4:127.0.0.1:1,{_HOST}:443"),
    "grpc.aio (secure)": lambda: grpc.aio.secure_channel(f"{_HOST}:443", grpc.ssl_channel_credentials()),
    "grpc.aio (insecure)": lambda: grpc.aio.insecure_channel(f"{_HOST}:443"),
    # duckdb's `httpfs` opens its sockets in C++, past every patch above, so the fence wraps the one
    # function every remote URL is built by (RM430): the refusal comes before duckdb is handed the URL.
    "duckdb (httpfs, through remote.remote_url)": lambda: remote.remote_url(
        f"https://{_HOST}", "datasets/a/b"
    ),
}
#: Driven above although no source file imports it, each with why it is driven anyway.
_DRIVEN_WITHOUT_AN_IMPORT = {
    "requests": "`ga4gh.vrs`'s seqrepo REST proxy (`sequences.SequenceProxy`) speaks requests",
    "grpc.aio": "gRPC's other C-core constructor, fenced before the Atlas client reaches for it",
}
#: Import roots that can open a connection. A source import under one of these is a transport the
#: fence must be shown to cover; `urllib.parse` and `urllib.error` open nothing and are not here.
_TRANSPORT_ROOTS = (
    "aiohttp",
    "duckdb",
    "ftplib",
    "grpc",
    "grpc.aio",
    "http.client",
    "httpx",
    "huggingface_hub",
    "pycurl",
    "requests",
    "smtplib",
    "socket",
    "urllib.request",
    "urllib3",
    "websockets",
)


def _transports_imported_by(package_src: Path) -> set[str]:
    """The transport roots any module under `package_src` imports, however it spells the import."""
    found: set[str] = set()
    for path in package_src.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = {node.module} | {f"{node.module}.{alias.name}" for alias in node.names}
            else:
                continue
            found.update(
                root
                for root in _TRANSPORT_ROOTS
                for name in names
                if name == root or name.startswith(f"{root}.")
            )
    return found


def _root(label: str) -> str:
    return label.split(" ", 1)[0]


@pytest.mark.parametrize("client", sorted(_CLIENTS))
def test_every_client_is_refused_and_the_refusal_names_the_test_and_the_host(
    client: str, network_fence, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "")
    if client == "huggingface_hub":
        # Every hub request first fetches the agent-harness registry (`utils/_detect_agent.py`, in 2.0.0 and 2.4.0),
        # from the global `constants.ENDPOINT` rather than the `endpoint` HfApi was given, at most once a
        # day per `HF_HOME`. Point that endpoint at the same host, so the one reach this test allows is
        # still the only host reached, whether or not today's registry is cached.
        monkeypatch.setattr(huggingface_hub.constants, "ENDPOINT", f"https://{_HOST}")
    with pytest.raises(network_fence.error) as refused:
        _CLIENTS[client]()
    assert _HOST in str(refused.value)
    assert os.environ["PYTEST_CURRENT_TEST"].split(" ")[0] in str(refused.value)
    reached = network_fence.take()
    assert reached and all(entry.startswith(f"{_HOST} via ") for entry in reached)


def test_a_reach_something_swallowed_is_still_recorded(
    network_fence, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The broad `except` a pass may carry (`@incidental-call-isolated`) cannot hide a reach."""
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "")
    with contextlib.suppress(Exception):  # swallowing is the case under test
        httpx.get(f"https://{_HOST}/", timeout=5)
    assert network_fence.take() == [f"{_HOST} via DNS (socket.getaddrinfo)"]


def _child_pytest(directory: Path, files: dict[str, str]) -> str:
    """Run a child pytest over `files` beside a copy of the real root conftest; its `-rA` output."""
    (directory / "conftest.py").write_text(
        (_ROOT / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (directory / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")
    env = {**os.environ, "JUST_DNA_NETWORK_TESTS": ""}
    # The parent's running test, its enumeration log and its options are not the child's.
    for name in ("PYTEST_CURRENT_TEST", "JUST_DNA_NETWORK_GUARD_LOG", "PYTEST_ADDOPTS"):
        env.pop(name, None)
    child = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rA", str(directory)],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert child.returncode == 1, child.stdout
    return child.stdout


_REACH = f"httpx.get('https://{_HOST}/', timeout=5)"


def test_a_swallowed_reach_fails_the_test_at_teardown_and_a_raised_one_fails_it_once(tmp_path: Path) -> None:
    """End to end, in a child pytest carrying the real root conftest."""
    out = _child_pytest(
        tmp_path,
        {
            "test_swallow.py": "import contextlib\n\nimport httpx\nimport pytest\n\n"
            "def test_swallows():\n"
            f"    with contextlib.suppress(Exception):\n        {_REACH}\n\n"
            f"def test_reports_its_own_reach():\n    {_REACH}\n\n"
            f"@pytest.mark.xfail(raises=RuntimeError)\ndef test_xfails():\n    {_REACH}\n",
        },
    )
    # The swallowed reach: the body passed, the teardown is the error.
    assert "PASSED test_swallow.py::test_swallows" in out, out
    assert "ERROR test_swallow.py::test_swallows" in out, out
    # A reach that raised is reported once, by the call, never a second time at teardown; an expected
    # failure stays expected.
    assert "FAILED test_swallow.py::test_reports_its_own_reach" in out, out
    assert "ERROR test_swallow.py::test_reports_its_own_reach" not in out, out
    assert "XFAIL test_swallow.py::test_xfails" in out, out
    assert "ERROR test_swallow.py::test_xfails" not in out, out


def test_a_late_reach_fails_the_run_under_its_own_name_and_never_the_next_test(tmp_path: Path) -> None:
    """A module fixture's finalizer runs after its last test's `_fenced_network`; the next test is innocent."""
    out = _child_pytest(
        tmp_path,
        {
            "test_a_late.py": "import contextlib\n\nimport httpx\nimport pytest\n\n"
            "@pytest.fixture(scope='module')\ndef pinger():\n    yield\n"
            f"    with contextlib.suppress(Exception):\n        {_REACH}\n\n"
            "def test_owner(pinger):\n    pass\n",
            "test_b_innocent.py": "def test_innocent():\n    pass\n",
        },
    )
    assert "PASSED test_b_innocent.py::test_innocent" in out, out
    assert "ERROR test_b_innocent.py::test_innocent" not in out, out
    assert "reached the network after its test's teardown" in out, out
    assert f"test_a_late.py::test_owner: {_HOST} via DNS (socket.getaddrinfo)" in out, out


def test_this_machine_stays_reachable(network_fence, monkeypatch: pytest.MonkeyPatch) -> None:
    """Loopback is open: several tests serve real HTTP on 127.0.0.1 on purpose."""
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "")
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
        with socket.create_connection(("localhost", port), timeout=5):
            pass
    grpc.insecure_channel(f"127.0.0.1:{port}").close()
    grpc.insecure_channel(f"ipv4:127.0.0.1:{port}").close()
    assert network_fence.take() == []


def test_a_loopback_url_is_built_and_the_opt_in_opens_the_rest(
    network_fence, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The duckdb case's two open doors: this machine always, any host with the opt-in (RM430)."""
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "")
    assert remote.remote_url("http://127.0.0.1:9", "/datasets/", "a/b") == "http://127.0.0.1:9/datasets/a/b"
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "1")
    assert remote.remote_url(f"https://{_HOST}/", "x") == f"https://{_HOST}/x"
    assert network_fence.take() == []


def test_the_opt_in_opens_it(network_fence, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the opt-in, the fence steps aside. A gRPC channel is lazy, so this sends nothing."""
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "1")
    grpc.insecure_channel(f"{_HOST}:443").close()
    assert network_fence.take() == []


def test_every_transport_the_enricher_imports_is_driven_into_the_fence() -> None:
    driven = {_root(label) for label in _CLIENTS}
    assert set(_DRIVEN_WITHOUT_AN_IMPORT) <= driven
    assert _transports_imported_by(_ROOT / "enricher" / "src") == driven - set(_DRIVEN_WITHOUT_AN_IMPORT)


def test_the_format_and_compiler_tiers_import_no_transport() -> None:
    """Principle 2, as an import walk: the fence has nothing to cover there because nothing is there."""
    assert _transports_imported_by(_ROOT / "schema" / "src") == set()
    assert _transports_imported_by(_ROOT / "compiler" / "src") == set()


def test_the_opt_in_is_exactly_one(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """The fence's `network_opted_in` reads `1` as yes and nothing else; a truthiness check let `0` in."""
    fence = next(p for p in request.config.pluginmanager.get_plugins() if hasattr(p, "network_opted_in"))
    for value, opted_in in (("1", True), ("0", False), ("true", False), ("", False)):
        monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", value)
        assert fence.network_opted_in() is opted_in, value


#: A read of the opt-in in a test file: the variable's name, read off the environment.
_OPT_IN_READ = re.compile(
    r'(?:getenv|environ\.get|environ\[)\(?\s*"JUST_DNA_NETWORK_TESTS"\s*\)?\]?(?P<rest>[^\n]{0,12})'
)


def test_every_live_test_skips_on_the_fences_reading_of_the_opt_in() -> None:
    """A live test carries `@pytest.mark.network`, whose skip asks the fence's own `network_opted_in`.
    A test reading the variable itself must compare it with `"1"` (the two that also need an API key),
    never test it for truth: a file that did read `JUST_DNA_NETWORK_TESTS=0` as yes and ran its live
    tests into a fence that refuses them (RM391)."""
    truthy = [
        f"{path.relative_to(_ROOT)}:{text[: m.start()].count(chr(10)) + 1}"
        for tree in ("schema/tests", "compiler/tests", "enricher/tests")
        for path in sorted((_ROOT / tree).rglob("*.py"))
        for text in [path.read_text(encoding="utf-8")]
        for m in _OPT_IN_READ.finditer(text)
        if not m.group("rest").lstrip().startswith('== "1"')
    ]
    assert truthy == []


# ── the duckdb case's own guard: only `remote.remote_url` hands duckdb a URL (RM430 follow-up) ──────

#: The duckdb calls that read a file or run SQL that may name one.
_DUCKDB_READS = frozenset(
    {"execute", "sql", "query", "read_parquet", "from_parquet", "read_csv", "read_csv_auto", "read_json"}
)
#: A URL scheme written into a literal: `https://`, `hf://`, `s3://`, any scheme duckdb could open.
_URL_SCHEME = re.compile(r"\b[a-z][a-z0-9+.-]*://", re.IGNORECASE)
#: The module that loads `httpfs` and reads over HTTP, and its one URL builder for duckdb.
_HOLDER_MODULE = "remote.py"
_HOLDER_FILE_URL = "_file_url"


def _literal_text(node: ast.AST) -> str:
    """Every string constant inside `node`, an f-string's literal parts included, joined."""
    return "".join(
        part.value
        for part in ast.walk(node)
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    )


def _is_file_url_call(node: ast.AST) -> bool:
    """`self._file_url(...)`, or a list or list comprehension of nothing else."""
    if isinstance(node, ast.ListComp):
        return _is_file_url_call(node.elt)
    if isinstance(node, ast.List):
        return bool(node.elts) and all(_is_file_url_call(e) for e in node.elts)
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == _HOLDER_FILE_URL
    )


def _duckdb_url_faults(sources: dict[str, str]) -> list[str]:
    """Every place a module could hand duckdb a URL that `remote_url` did not build, by `file:line`.

    Five rules. No duckdb call anywhere carries a URL scheme in a literal. No module but the holder's
    loads `httpfs` (without it duckdb opens no URL). In the holder's module duckdb reads a file only
    through SQL, never a relational `read_parquet(...)`/`from_parquet(...)` method, every `read_parquet`
    binds its files (`read_parquet(?)`), the bound value is `self._file_url(...)`, never a string put
    together on the spot, and no bound list is rewritten in place (`params[0] = …`). And `_file_url`
    returns `remote_url(...)`, the function the fence wraps.
    """
    faults: list[str] = []
    for name, source in sources.items():
        tree = ast.parse(source)
        bound = {
            call.args[1].id
            for call in ast.walk(tree)
            if isinstance(call, ast.Call)
            and len(call.args) > 1
            and isinstance(call.args[1], ast.Name)
            and "read_parquet(" in _literal_text(call.args[0])
        }
        for node in ast.walk(tree):
            if name == _HOLDER_MODULE and isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in bound
                    ):
                        faults.append(f"{name}:{node.lineno}: a bound list rewritten in place")
            if not isinstance(node, ast.Call):
                continue
            attr = node.func.attr if isinstance(node.func, ast.Attribute) else None
            where = f"{name}:{node.lineno}"
            arguments = [*node.args, *(k.value for k in node.keywords)]
            literal = "".join(_literal_text(a) for a in arguments)
            if attr in _DUCKDB_READS and _URL_SCHEME.search(literal):
                faults.append(f"{where}: a URL literal handed to duckdb")
            loads_httpfs = attr in {"install_extension", "load_extension"} and "httpfs" in literal
            if (loads_httpfs or (attr == "execute" and "httpfs" in literal)) and name != _HOLDER_MODULE:
                faults.append(f"{where}: httpfs loaded outside {_HOLDER_MODULE}")
            if name == _HOLDER_MODULE and attr in _DUCKDB_READS - {"execute", "sql", "query"}:
                faults.append(f"{where}: duckdb reads a file past SQL, unbound")
            if name == _HOLDER_MODULE and attr in _DUCKDB_READS and node.args:
                sql = _literal_text(node.args[0])
                if "read_parquet(" in sql:
                    if "read_parquet(?)" not in sql:
                        faults.append(f"{where}: read_parquet's files are not a bound parameter")
                    elif not (
                        len(node.args) > 1
                        and isinstance(node.args[1], ast.List)
                        and node.args[1].elts
                        and _is_file_url_call(node.args[1].elts[0])
                    ) and not (
                        len(node.args) > 1
                        and isinstance(node.args[1], ast.Name)
                        and _bound_to_file_urls(tree, node.args[1].id)
                    ):
                        faults.append(
                            f"{where}: read_parquet(?) is bound to something but {_HOLDER_FILE_URL}"
                        )
        if name == _HOLDER_MODULE:
            builders = [
                f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and f.name == _HOLDER_FILE_URL
            ]
            returns = [r for f in builders for r in ast.walk(f) if isinstance(r, ast.Return)]
            if not returns or not all(
                isinstance(r.value, ast.Call)
                and isinstance(r.value.func, ast.Name)
                and r.value.func.id == "remote_url"
                for r in returns
            ):
                faults.append(f"{name}: {_HOLDER_FILE_URL} does not return remote_url(...)")
    return faults


def _bound_to_file_urls(tree: ast.AST, variable: str) -> bool:
    """Whether every assignment to `variable` is a list whose first element is `self._file_url(...)`."""
    assigned = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and target.id == variable and node.value is not None
    ]
    return bool(assigned) and all(
        isinstance(value, ast.List) and value.elts and _is_file_url_call(value.elts[0]) for value in assigned
    )


def _enricher_sources() -> dict[str, str]:
    package = _ROOT / "enricher" / "src" / "just_dna_enricher"
    return {
        str(path.relative_to(package)): path.read_text(encoding="utf-8")
        for path in sorted(package.rglob("*.py"))
    }


def test_only_remote_url_hands_duckdb_a_url() -> None:
    """The duckdb fence wraps `remote.remote_url` (answer H), so it holds only while nothing else builds
    a URL duckdb opens: duckdb's sockets are C++, where the socket patch cannot see them."""
    sources = _enricher_sources()
    assert _HOLDER_MODULE in sources
    assert _duckdb_url_faults(sources) == []


def test_the_walk_sees_each_way_past_the_url_builder() -> None:
    """Each rule shown failing on the shape it exists for, so a green walk is not a blind one."""
    bound_by_hand = (
        "def q(self, cursor, pin, files):\n"
        "    cursor.execute('SELECT * FROM read_parquet(?)', [[f'{self.base}/{f}' for f in files]])\n"
        "def _file_url(self, pin, path):\n    return remote_url(self.base, path)\n"
    )
    interpolated = (
        "def q(self, cursor, url):\n    cursor.execute(f\"SELECT * FROM read_parquet('{url}')\")\n"
        "def _file_url(self, pin, path):\n    return remote_url(self.base, path)\n"
    )
    builder_by_hand = (
        "def q(self, cursor, pin, path):\n"
        "    cursor.execute('DESCRIBE SELECT * FROM read_parquet(?)', [self._file_url(pin, path)])\n"
        "def _file_url(self, pin, path):\n    return f'{self.base}/{path}'\n"
    )
    elsewhere = (
        "def read(con):\n    con.execute(\"SELECT * FROM read_parquet('https://huggingface.co/x.parquet')\")\n"
        "    con.execute('LOAD httpfs')\n"
    )
    assert _duckdb_url_faults({_HOLDER_MODULE: bound_by_hand}) == [
        f"{_HOLDER_MODULE}:2: read_parquet(?) is bound to something but {_HOLDER_FILE_URL}"
    ]
    assert _duckdb_url_faults({_HOLDER_MODULE: interpolated}) == [
        f"{_HOLDER_MODULE}:2: read_parquet's files are not a bound parameter"
    ]
    assert _duckdb_url_faults({_HOLDER_MODULE: builder_by_hand}) == [
        f"{_HOLDER_MODULE}: {_HOLDER_FILE_URL} does not return remote_url(...)"
    ]
    relational = (
        "def q(self, pin, url):\n    return pin.connection.read_parquet(url)\n"
        + bound_by_hand.split("\n", 2)[2]
    )
    assert _duckdb_url_faults({_HOLDER_MODULE: relational}) == [
        f"{_HOLDER_MODULE}:2: duckdb reads a file past SQL, unbound"
    ]
    rewritten = (
        "def q(self, cursor, pin, files, url):\n"
        "    params = [[self._file_url(pin, f) for f in files]]\n"
        "    params[0] = [url]\n"
        "    cursor.execute('SELECT * FROM read_parquet(?)', params)\n"
        "def _file_url(self, pin, path):\n    return remote_url(self.base, path)\n"
    )
    assert _duckdb_url_faults({_HOLDER_MODULE: rewritten}) == [
        f"{_HOLDER_MODULE}:3: a bound list rewritten in place"
    ]
    assert _duckdb_url_faults({"clinvar.py": elsewhere}) == [
        "clinvar.py:2: a URL literal handed to duckdb",
        f"clinvar.py:3: httpfs loaded outside {_HOLDER_MODULE}",
    ]
