"""An interrupt stops a bulk build's worker threads within a chunk, not at the end of their work (RM409).

The maintainer interrupted `cache rebuild --only opentargets` about five minutes into a ~22 GB mirror. Two
Ctrl-C did nothing and the run had to be killed with SIGTERM to its process group. The mirror fetches parts
on a thread pool: the `KeyboardInterrupt` landed in the main thread's `future.result()`, and the handler's
`pool.shutdown(wait=True, cancel_futures=True)` cancelled the queued parts but then waited for every part
already streaming, each to its last byte. The AlphaGenome AVI build has the same shape over a whole
contig per worker.

Each test serves a source that is slow on purpose (a local HTTP server for the parts, a stand-in `tabix`
for the contigs) and delivers the interrupt deterministically: the build pool's `future.result()` is
replaced by one that waits until every worker is mid-stream and then raises `KeyboardInterrupt`, exactly
where the real one arrives. The assertions are that the interrupt propagates, that the build returns well inside the time
the in-flight work still needs, and that nothing half-written sits under a final name.
"""

import concurrent.futures
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
from just_dna_enricher import alphagenome_avi_build as ab
from just_dna_enricher import net
from just_dna_enricher import opentargets_build as ot

#: How long one in-flight unit of work keeps streaming: `TICKS` chunks, `TICK` seconds apart. The bound
#: an interrupt must meet is a fraction of it, so the old behaviour (wait for the work to finish) fails
#: by a margin no scheduler jitter closes.
TICKS = 60
TICK = 0.05
BOUND = 1.0
WORKERS = 4


def _interrupt_once_started(
    monkeypatch: pytest.MonkeyPatch, module: object, started: threading.Event
) -> dict[str, float]:
    """Make the pool's `future.result()` the user's Ctrl-C: wait until the workers stream, then raise.

    Only the futures of `module`'s own pool are touched (its `ThreadPoolExecutor` is swapped for one whose
    futures answer this way): tenacity drives every retried attempt through `Future` too, so patching the
    class would interrupt the downloads' own retry machinery rather than the pool's caller. Returns a
    dict the moment of the interrupt is written into, so the test times the stop from there.
    """
    when: dict[str, float] = {}

    def _result(timeout: float | None = None) -> object:
        assert started.wait(10), "the workers never started streaming"
        when.setdefault("interrupt", time.monotonic())
        raise KeyboardInterrupt

    class _Pool(concurrent.futures.ThreadPoolExecutor):
        def submit(self, fn, /, *args, **kwargs):  # type: ignore[no-untyped-def]
            future = super().submit(fn, *args, **kwargs)
            future.result = _result  # type: ignore[method-assign]
            return future

    monkeypatch.setattr(module, "ThreadPoolExecutor", _Pool)
    return when


# ── Open Targets: parts streamed over HTTP ──────────────────────────────────────────────────────────


class _SlowRelease(BaseHTTPRequestHandler):
    """A release on the FTP's layout whose parts trickle: a listing per dataset, one part each."""

    started: threading.Event
    streaming: set[str]
    lock: threading.Lock

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's signature
        return

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path
        if path.endswith("/croissant.json"):
            self._send(b'{"version": "test"}', "application/json")
        elif path.endswith("/"):
            self._send(b'<a href="part-00000.parquet">part</a>', "text/html")
        elif "/part-" in path:
            chunk = b"x" * 4096
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(chunk) * TICKS))
            self.end_headers()
            try:
                for tick in range(TICKS):
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    if tick == 0:
                        with self.lock:
                            self.streaming.add(path)
                            if len(self.streaming) >= WORKERS:
                                self.started.set()
                    time.sleep(TICK)
            except (BrokenPipeError, ConnectionResetError):
                return  # the client stopped reading, which is the point
        else:
            self.send_error(404)


@pytest.fixture
def slow_release():
    started = threading.Event()
    handler = type(
        "_Handler", (_SlowRelease,), {"started": started, "streaming": set(), "lock": threading.Lock()}
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", started
    finally:
        server.shutdown()
        server.server_close()


def test_an_interrupt_stops_the_open_targets_mirror_mid_part(
    slow_release: tuple[str, threading.Event], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl-C during the mirror returns within a chunk and leaves no part under its final name."""
    assert len(ot.OPENTARGETS_DATASETS) > WORKERS, (
        "the pool must have a queued part as well as in-flight ones"
    )
    base_url, started = slow_release
    when = _interrupt_once_started(monkeypatch, ot, started)
    dest = tmp_path / "mirror"

    with pytest.raises(KeyboardInterrupt):
        ot.download_release(dest, release=ot.OPENTARGETS_RELEASE, base_url=base_url, parts=1, workers=WORKERS)
    stopped = time.monotonic() - when["interrupt"]

    assert stopped < BOUND, (
        f"the mirror took {stopped:.2f}s to stop after the interrupt; the in-flight parts needed "
        f"~{TICKS * TICK:.0f}s more, so it waited for them"
    )
    assert sorted(p.relative_to(dest).as_posix() for p in dest.rglob("part-*")) == [], (
        "an interrupted part landed on disk, under its final name or as a `.part`"
    )


def test_a_stop_during_a_retry_backoff_is_not_held_until_the_next_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A part whose connection failed sits in a backoff of two seconds or more; a stop ends it at once.

    The stop is set inside the first attempt, before it fails, so the backoff starts with the flag already
    up: a backoff that sleeps rather than waits on the flag holds the worker for the whole interval.
    """
    stop = threading.Event()
    attempts = {"n": 0}

    def _stream(*_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        attempts["n"] += 1
        stop.set()
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(net.httpx, "stream", _stream)
    monkeypatch.setenv(net.RETRY_ATTEMPTS_ENV, "3")
    began = time.monotonic()
    with pytest.raises(net._StreamStopped):
        net.stream_to_file(
            tmp_path / "part.parquet",
            "http://127.0.0.1:9/part.parquet",
            error_cls=ot.OpenTargetsUnavailable,
            retired=ot.OpenTargetsRetired,
            what="a part",
            _stop=stop,
        )
    assert time.monotonic() - began < BOUND, "the backoff slept through the stop"
    assert attempts["n"] == 1, "a stopped download asked the server again"
    assert sorted(p.name for p in tmp_path.iterdir()) == []


# ── AlphaGenome AVI: contigs streamed out of `tabix` ────────────────────────────────────────────────

#: A stand-in for `tabix`, written to the test's own directory and run with this interpreter: `-l`
#: names the contigs, `tabix <src> <contig>` prints whole three-ALT loci slowly until killed.
_FAKE_TABIX = f"""
import sys, time

if sys.argv[1] == "-l":
    print("chrA\\nchrB\\nchrC\\nchrD\\nchrE")
    sys.exit(0)
contig = sys.argv[2]
pos = 1
for _ in range({TICKS}):
    lines = []
    for _ in range(40):
        for alt in "CGT":
            lines.append(f"{{contig}}\\t{{pos}}\\tA\\t{{alt}}\\t0.00100\\t1.00000\\n")
        pos += 1
    sys.stdout.write("".join(lines))
    sys.stdout.flush()
    time.sleep({TICK})
"""


def test_an_interrupt_stops_the_alphagenome_build_mid_contig(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl-C during the AVI build returns within a block, writes no contig, and leaves no `tabix` running."""
    fake = tmp_path / "fake_tabix.py"
    fake.write_text(_FAKE_TABIX, encoding="utf-8")
    real_popen = subprocess.Popen
    children: list[subprocess.Popen] = []

    class _Popen(real_popen):  # type: ignore[misc, valid-type]
        def __init__(self, args, *rest, **kwargs):  # type: ignore[no-untyped-def]
            if isinstance(args, list) and args and args[0] == "tabix":
                args = [sys.executable, "-I", str(fake), *args[1:]]
            super().__init__(args, *rest, **kwargs)
            children.append(self)

    monkeypatch.setattr(subprocess, "Popen", _Popen)

    contigs = ("chrA", "chrB", "chrC", "chrD", "chrE")
    assert len(contigs) > WORKERS, "the pool must have a queued contig as well as in-flight ones"
    started = threading.Event()
    reading: set[str] = set()
    lock = threading.Lock()
    real_read_block = ab._read_block

    def _read_block(block: bytes):  # type: ignore[no-untyped-def]
        with lock:
            reading.add(block.split(b"\t", 1)[0].decode())
            if len(reading) >= WORKERS:
                started.set()
        return real_read_block(block)

    monkeypatch.setattr(ab, "_read_block", _read_block)
    when = _interrupt_once_started(monkeypatch, ab, started)

    source = tmp_path / "avi.tsv.gz"
    source.write_bytes(b"")
    out = tmp_path / "out"
    with pytest.raises(KeyboardInterrupt):
        ab.build_snapshot(
            source,
            out,
            contigs=contigs,
            workers=WORKERS,
            chunk_bytes=4096,
            hash_source=False,
            terms_file=None,
        )
    stopped = time.monotonic() - when["interrupt"]

    assert stopped < BOUND, (
        f"the build took {stopped:.2f}s to stop after the interrupt; the in-flight contigs needed "
        f"~{TICKS * TICK:.0f}s more, so it waited for them"
    )
    data = out / ab.SNAPSHOT_DATA_DIRNAME
    assert sorted(p.name for p in data.glob("alphagenome_avi-*.parquet")) == [], (
        "an interrupted contig was written under its final name"
    )
    assert [c.args for c in children if c.poll() is None] == [], "a `tabix` outlived the interrupted build"
