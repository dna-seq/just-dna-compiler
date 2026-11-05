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
tests in 7 files asking ClinGen, Ensembl REST, eutils and the seqrepo proxy, every one of them still
passing, because each client turned the refused connection into its own "unreachable" answer and the
test was content with that. A suite whose green depends on what a remote service says that day is not
a gate.

So the fence is here, at the transport, rather than per client: `socket.getaddrinfo`,
`socket.socket.connect` and `connect_ex` refuse any host that is not this machine, and so do gRPC's
channel constructors (`grpc` and `grpc.aio`, every target form gRPC names), because gRPC's C core
opens its own sockets where no Python patch can see them.
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
  that already failed (or xfailed) is not failed a second time, so one reach is one red line. Each
  reach is filed under the test that made it, so one no teardown can claim (a module fixture's
  finalizer runs after its last test's) fails the run at session end under its own name instead of
  failing whichever test runs next.
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


def network_opted_in() -> bool:
    """The opt-in, read one way everywhere: exactly `1`. `JUST_DNA_NETWORK_TESTS=0` or `=false` opts
    nobody in, where a truthiness check read either as yes and let a live test run unfenced (RM391).

    The fence asks it, and so does the `network` marker every live test carries, so a test cannot skip
    on a different reading from the one the fence refuses on."""
    return os.environ.get(NETWORK_OPT_IN) == "1"


class NetworkReachedInTests(RuntimeError):
    """A test asked a host that is not this machine without `JUST_DNA_NETWORK_TESTS=1`."""


#: Every refusal not yet reported, as (the test's node id, "<host> via <what>").
_REACHES: list[tuple[str, str]] = []

_REAL_GETADDRINFO = socket.getaddrinfo
_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
#: gRPC's channel constructors, sync and asyncio, by (module, name): its C core opens its own sockets.
_REAL_GRPC_CHANNELS = (
    {}
    if grpc is None
    else {
        (module, name): getattr(module, name)
        for module in (grpc, grpc.aio)
        for name in ("secure_channel", "insecure_channel")
    }
)
#: gRPC's target schemes that name addresses rather than a `host:port` (its naming doc).
_GRPC_ADDRESS_SCHEMES = ("ipv4:", "ipv6:")


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
    if network_opted_in() or _is_local(host):
        return
    if isinstance(host, bytes):  # asyncio resolves through `getaddrinfo(b"host", ...)`
        host = host.decode("idna")
    reach = f"{host} via {via}"
    running = os.environ.get("PYTEST_CURRENT_TEST")
    test = running or "collection (outside any test)"
    if running:
        _REACHES.append((running.rsplit(" (", 1)[0], reach))
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


def _host_of(address: str) -> str:
    """`h`, from `h`, `h:p`, `[v6]` or `[v6]:p`; a bare IPv6 address is returned whole."""
    if address.startswith("["):
        return address[1:].split("]", 1)[0]
    return address.rsplit(":", 1)[0] if address.count(":") == 1 else address


def _grpc_hosts(target: str) -> list[object]:
    """Every host a gRPC target names; `[None]` (local) for a Unix socket.

    The forms gRPC's naming document gives: `h:p`, `dns:h:p`, `dns:///h:p`, `dns://authority/h:p`,
    `ipv4:a:p,b:p`, `ipv6:[a]:p,...`, `unix:path`, `unix-abstract:name`.
    """
    if target.startswith(("unix:", "unix-abstract:")):
        return [None]
    if target.startswith(_GRPC_ADDRESS_SCHEMES):
        return [_host_of(address) for address in target.split(":", 1)[1].split(",")]
    rest = target.removeprefix("dns:")
    if rest.startswith("//"):
        rest = rest[2:].split("/", 1)[1]
    return [_host_of(rest)]


def _fenced_grpc(module, name: str):
    real = _REAL_GRPC_CHANNELS[(module, name)]

    def fenced(target, *args, **kwargs):
        for host in _grpc_hosts(target):
            _guard(host, f"{module.__name__}.{name}")
        return real(target, *args, **kwargs)

    return fenced


socket.getaddrinfo = _fenced_getaddrinfo
socket.socket.connect = _fenced_connect
socket.socket.connect_ex = _fenced_connect_ex
for _module, _name in _REAL_GRPC_CHANNELS:
    setattr(_module, _name, _fenced_grpc(_module, _name))


class NetworkFence:
    """The fence as a test sees it: the error type it raises, and the reaches it has recorded."""

    error = NetworkReachedInTests

    def take(self, test: str | None = None) -> list[str]:
        """The reaches recorded (by `test` only, when named), removed: whoever takes them reports them.

        A test that provokes the fence on purpose takes its own; `_fenced_network` takes the reaches of
        the test it closes and leaves another's, which is how a late reach (a module fixture's
        finalizer, a thread outliving its test) is reported under its own name at session end rather
        than blamed on whichever test happens to run next.
        """
        taken = [entry for entry in _REACHES if test is None or entry[0] == test]
        _REACHES[:] = [entry for entry in _REACHES if entry not in taken]
        return [reach for _test, reach in taken]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", f"network: a live test; skipped unless {NETWORK_OPT_IN}=1 (`network_opted_in`, RM391)"
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a `network`-marked test unless the opt-in is set, read by the fence's own `network_opted_in`."""
    if item.get_closest_marker("network") is not None and not network_opted_in():
        pytest.skip(f"a live test: set {NETWORK_OPT_IN}=1 to run it")


@pytest.fixture
def network_fence() -> NetworkFence:
    """The fence's handle, for the test that proves it (`importlib` mode cannot import a conftest)."""
    return NetworkFence()


#: Set on a test item whose setup or call already failed (or xfailed), so a reach is reported once.
_ALREADY_REPORTED = pytest.StashKey[bool]()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when in ("setup", "call") and (report.failed or hasattr(report, "wasxfail")):
        item.stash[_ALREADY_REPORTED] = True


@pytest.fixture(autouse=True)
def _fenced_network(request: pytest.FixtureRequest):
    """Fail the test at teardown when it reached the network and still passed: something swallowed the
    raise. A test that already failed (or xfailed) has been reported and is not reported twice."""
    yield
    reached = NetworkFence().take(request.node.nodeid)
    if reached and not request.node.stash.get(_ALREADY_REPORTED, False):
        pytest.fail(
            f"reached the network without {NETWORK_OPT_IN}=1 (RM391): " + "; ".join(sorted(set(reached))),
            pytrace=False,
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """A reach no test's teardown could claim fails the run, under the name of the test that made it."""
    late = list(_REACHES)
    _REACHES.clear()
    if not late:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep(
            "=", f"reached the network after its test's teardown, without {NETWORK_OPT_IN}=1 (RM391)"
        )
        for test, reach in late:
            reporter.write_line(f"{test}: {reach}")
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
