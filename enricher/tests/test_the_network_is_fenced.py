"""No test reaches the network without `JUST_DNA_NETWORK_TESTS=1`, through any client (RM391).

The fence is the root `conftest.py`'s: `socket.getaddrinfo`, `socket.socket.connect`/`connect_ex` and
gRPC's channel constructors refuse every host that is not this machine while a test runs, and
`_fenced_network` fails a test at teardown when it reached one, even if something swallowed the raise.
Before it, 31 tests in 8 files asked ClinGen, Ensembl REST, eutils and the seqrepo proxy and passed
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
}
#: Driven above although no source file imports it, with the dependency that speaks it.
_DRIVEN_FOR_A_DEPENDENCY = {
    "requests": "`ga4gh.vrs`'s seqrepo REST proxy (`sequences.SequenceProxy`) speaks requests",
}
#: Import roots that can open a connection. A source import under one of these is a transport the
#: fence must be shown to cover; `urllib.parse` and `urllib.error` open nothing and are not here.
_TRANSPORT_ROOTS = (
    "aiohttp",
    "ftplib",
    "grpc",
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


def test_a_swallowed_reach_fails_the_test_at_teardown(tmp_path: Path) -> None:
    """End to end, in a child pytest carrying the real root conftest: green body, red teardown."""
    (tmp_path / "conftest.py").write_text(
        (_ROOT / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_swallow.py").write_text(
        "import httpx\n\n"
        "def test_swallows():\n"
        "    try:\n"
        f"        httpx.get('https://{_HOST}/', timeout=5)\n"
        "    except Exception:\n"
        "        pass\n\n"
        "def test_reports_its_own_reach():\n"
        f"    httpx.get('https://{_HOST}/', timeout=5)\n",
        encoding="utf-8",
    )
    env = {**os.environ, "JUST_DNA_NETWORK_TESTS": ""}
    env.pop("PYTEST_CURRENT_TEST", None)
    child = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rA", str(tmp_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = child.stdout
    assert child.returncode == 1, out
    # The swallowed reach: the body passed, the teardown is the error.
    assert "PASSED test_swallow.py::test_swallows" in out, out
    assert "ERROR test_swallow.py::test_swallows" in out, out
    # The reach that raised fails once, in the call, not a second time at teardown.
    assert "FAILED test_swallow.py::test_reports_its_own_reach" in out, out
    assert "ERROR test_swallow.py::test_reports_its_own_reach" not in out, out


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
    assert network_fence.take() == []


def test_the_opt_in_opens_it(network_fence, monkeypatch: pytest.MonkeyPatch) -> None:
    """With the opt-in, the fence steps aside. A gRPC channel is lazy, so this sends nothing."""
    monkeypatch.setenv("JUST_DNA_NETWORK_TESTS", "1")
    grpc.insecure_channel(f"{_HOST}:443").close()
    assert network_fence.take() == []


def test_every_transport_the_enricher_imports_is_driven_into_the_fence() -> None:
    driven = {_root(label) for label in _CLIENTS}
    assert set(_DRIVEN_FOR_A_DEPENDENCY) <= driven
    assert _transports_imported_by(_ROOT / "enricher" / "src") == driven - set(_DRIVEN_FOR_A_DEPENDENCY)


def test_the_format_and_compiler_tiers_import_no_transport() -> None:
    """Principle 2, as an import walk: the fence has nothing to cover there because nothing is there."""
    assert _transports_imported_by(_ROOT / "schema" / "src") == set()
    assert _transports_imported_by(_ROOT / "compiler" / "src") == set()
