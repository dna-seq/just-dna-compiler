"""Two things every test in the workspace gets: no colour in rendered CLI output, and no network.

**No colour (RM233, half of it).** `main` was red at `2001215` on both Python jobs while every local
run was green. Two tests match a string inside Typer's `--help` or its error box, and Typer renders
through rich, which decides colour from the environment: a GitHub runner got it, this developer's
non-tty did not. With colour on, `--use` is emitted as `\x1b[1;36m-\x1b[0m\x1b[1;36m-use\x1b[0m` — rich
styles the two dashes as their own span — so `"--use" in result.output` is false for a flag that is
right there, and the failure accuses the command of missing a flag.

The pin is here rather than in the two tests because the class is wider than the instances. 491
tests across 18 files invoke a CLI; two happen to match a token rich splits, and the other 489 pass on
the luck of what they match. Stripping escapes per call site fixes those two and leaves the next one to
be found by a red `main` again.

`TERM=dumb` is what does it, measured against the two failing tests: `NO_COLOR=1` alone fixes only one
of them and `FORCE_COLOR` outranks it anyway. Set in the root `conftest.py`, which pytest loads before
collecting any test module, and read later because every rich `Console` in a Typer app is constructed
per invocation. A test that wants colour can put it back with `monkeypatch.setenv`; none does, and
`enricher/tests/test_cli_rendering.py` fails if this stops working.

`COLUMNS` is deliberately NOT set here, and that is the other half of RM233. Click's `CliRunner`
pins its own terminal width inside `invoke()`, so the environment cannot widen the box: a long
diagnostic still wraps mid-sentence at 80 columns, which is why `nothing will fetch it` was the second
failure. Setting `COLUMNS` here looks like it addresses that and does nothing — it was in the first
draft of this file for exactly that reason. Phrase matching goes through `cli_text()` in
`enricher/tests/conftest.py` instead.

**No network (RM391, `@network-tests-optin`).** Network tests are opt-in with
`JUST_DNA_NETWORK_TESTS=1`, and until RM391 nothing enforced it: the only fence was RM372's, over the
HuggingFace hub. The 0.8 audit (round 2) ran the suite with sockets and DNS refused and found 31
tests in 8 files asking ClinGen, Ensembl REST, eutils and the seqrepo proxy, every one of them still
passing, because each client turned the refused connection into its own "unreachable" answer and the
test was content with that. A suite whose green depends on what a remote service says that day is not
a gate.

So the fence is here, at the transport, rather than per client: `socket.getaddrinfo`,
`socket.socket.connect` and `connect_ex` refuse any host that is not this machine, and so do gRPC's
channel constructors, because gRPC's C core opens its own sockets where no Python patch can see them.
That covers httpx (sync and async), requests (through which `ga4gh.vrs`'s seqrepo proxy speaks),
`urllib`, `huggingface_hub` and gRPC in one place; `enricher/tests/test_the_network_is_fenced.py`
drives each of them into it, and asserts the enricher imports no network library it does not drive.

Three choices in it are load-bearing:

- **It raises `NetworkReachedInTests`, a `RuntimeError`, never an `OSError`.** A refused connection
  is exactly what every client is written to absorb, which is how the 31 passed under the audit's
  `ConnectionRefusedError`. An exception no transport maps keeps the reach from being translated into
  "unreachable".
- **It also records the reach, and `_fenced_network` fails the test at teardown when one was
  recorded and the test still passed.** A pass that catches broadly (`@incidental-call-isolated`)
  could still swallow the raise, and a fence a test can swallow is the audit's finding again. A test
  that already failed is not failed a second time, so one reach is one red line.
- **It is active from the moment this file is imported**, collection included, and names the test
  when one is running (`PYTEST_CURRENT_TEST`). The one reach the audit saw outside a test was
  `atlas_protos.fetch_protos` at import, in a copy of the tree that had never generated the Atlas
  stubs; `uv sync` generates them at build time (RM196), so a synced checkout collects offline, and an
  unsynced one now says so at collection instead of fetching.

Loopback and Unix sockets stay open: several tests serve real HTTP on `127.0.0.1` on purpose. Set
`JUST_DNA_NETWORK_GUARD_LOG` to a file to have every refusal append `test<TAB>host<TAB>via` there,
which is how the reaching tests were enumerated.
"""

import ipaddress
import os
import socket
from pathlib import Path

import pytest

try:
    import grpc
except ImportError:  # the enricher's optional AlphaGenome extra; the other tiers never install it
    grpc = None

os.environ["TERM"] = "dumb"

#: The opt-in `@network-tests-optin` names.
NETWORK_OPT_IN = "JUST_DNA_NETWORK_TESTS"
#: Where every refusal is appended, when set — the enumeration aid.
NETWORK_GUARD_LOG = "JUST_DNA_NETWORK_GUARD_LOG"


class NetworkReachedInTests(RuntimeError):
    """A test asked a host that is not this machine without `JUST_DNA_NETWORK_TESTS=1`."""


#: Every refusal since the last test's teardown, as "<host> via <what>". `_fenced_network` empties it.
_REACHES: list[str] = []

_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_REAL_GRPC_CHANNELS = (
    {} if grpc is None else {"secure_channel": grpc.secure_channel, "insecure_channel": grpc.insecure_channel}
)


def _is_local(host: object) -> bool:
    """True for this machine: no host (a bind), `localhost`, a loopback or unspecified address."""
    if host is None:
        return True
    name = host.decode() if isinstance(host, bytes) else str(host)
    name = name.strip("[]").split("%", 1)[0]
    if name in ("", "localhost") or name.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def _guard(host: object, via: str) -> None:
    """Refuse `host` unless the opt-in is set or the host is this machine; record it inside a test."""
    if os.environ.get(NETWORK_OPT_IN) == "1" or _is_local(host):
        return
    if isinstance(host, bytes):  # asyncio resolves through `getaddrinfo(b"host", ...)`
        host = host.decode("idna")
    reach = f"{host} via {via}"
    running = os.environ.get("PYTEST_CURRENT_TEST")
    test = running or "collection (outside any test)"
    if running:
        _REACHES.append(reach)
    log = os.environ.get(NETWORK_GUARD_LOG)
    if log:
        with Path(log).open("a", encoding="utf-8") as handle:
            handle.write(f"{test}\t{host}\t{via}\n")
    raise NetworkReachedInTests(
        f"{test} reached {reach} without {NETWORK_OPT_IN}=1 (RM391). Inject a fake client, a cached "
        f"fixture or a resolver, pass offline=True, or gate the test on {NETWORK_OPT_IN}=1 when the live "
        "call is its point."
    )


def _fenced_getaddrinfo(host, *args, **kwargs):
    _guard(host, "DNS (socket.getaddrinfo)")
    return _REAL_GETADDRINFO(host, *args, **kwargs)


def _inet_host(sock: socket.socket, address: object) -> object:
    """The host an inet connect names; `None` (local) for a Unix socket or any other family."""
    if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
        return address[0]
    return None


def _fenced_connect(self, address):
    _guard(_inet_host(self, address), "socket.connect")
    return _REAL_CONNECT(self, address)


def _fenced_connect_ex(self, address):
    _guard(_inet_host(self, address), "socket.connect_ex")
    return _REAL_CONNECT_EX(self, address)


def _grpc_host(target: str) -> object:
    """The host a gRPC target names: `dns:///h:p`, `h:p`, `[v6]:p`; `None` for a `unix:` socket."""
    if target.startswith(("unix:", "unix-abstract:")):
        return None
    authority = target.split("///", 1)[1] if "///" in target else target
    if authority.startswith("["):
        return authority[1:].split("]", 1)[0]
    return authority.rsplit(":", 1)[0] if authority.count(":") == 1 else authority


def _fenced_grpc(name: str):
    real = _REAL_GRPC_CHANNELS[name]

    def fenced(target, *args, **kwargs):
        _guard(_grpc_host(target), f"grpc.{name}")
        return real(target, *args, **kwargs)

    return fenced


socket.getaddrinfo = _fenced_getaddrinfo
socket.socket.connect = _fenced_connect
socket.socket.connect_ex = _fenced_connect_ex
for _name in _REAL_GRPC_CHANNELS:
    setattr(grpc, _name, _fenced_grpc(_name))


class NetworkFence:
    """The fence as a test sees it: the error type it raises, and the reaches it has recorded."""

    error = NetworkReachedInTests

    def take(self) -> list[str]:
        """The reaches recorded so far, removed — a test that provokes the fence on purpose owns them."""
        taken = list(_REACHES)
        _REACHES.clear()
        return taken


@pytest.fixture
def network_fence() -> NetworkFence:
    """The fence's handle, for the test that proves it (`importlib` mode cannot import a conftest)."""
    return NetworkFence()


#: Set on a test item whose setup or call already failed, so a reach that raised is reported once.
_ALREADY_FAILED = pytest.StashKey[bool]()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when in ("setup", "call") and report.failed:
        item.stash[_ALREADY_FAILED] = True


@pytest.fixture(autouse=True)
def _fenced_network(request: pytest.FixtureRequest):
    """Fail the test at teardown when it reached the network and still passed: something swallowed the
    raise. A test that already failed has been reported, by the raise or otherwise, and is not reported
    twice."""
    yield
    reached = NetworkFence().take()
    if reached and not request.node.stash.get(_ALREADY_FAILED, False):
        pytest.fail(
            f"reached the network without {NETWORK_OPT_IN}=1 (RM391): " + "; ".join(sorted(set(reached))),
            pytrace=False,
        )
