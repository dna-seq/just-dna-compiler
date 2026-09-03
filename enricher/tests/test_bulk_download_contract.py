"""Every bulk download is translated, retried and atomic — one body, guarded by a walk (RM187).

Eleven builders stream one file from a source's bulk endpoint. Four of them raised `httpx`'s own
exception at their callers, and `caches._rebuild_*` catches each lane's own error type — so a
truncated download was a **traceback rather than an outcome**, and it escaped `rebuild_lane` too,
which in a full `cache rebuild` takes every later lane with it. None of the eleven retried, on the
largest requests this tier makes.

**The incident, so the retry is not speculative.** On 2026-09-03 NCBI closed the connection
180,927,542 bytes into a 193,427,450-byte ClinVar VCF and the run died with
`httpx.RemoteProtocolError`. `RemoteProtocolError` subclasses `TransportError`, which is exactly what
a second attempt fixes — asserted below rather than assumed, because the whole retry predicate rests
on that relationship.

**Third occurrence of `@client-exception-contract`**: RM97 found it in the clients, RM101 one layer
up in the passes, and the builder downloads were never swept. RM101's own coverage guard hand-kept
eight module names and missed `identifiers`, leaving `OntologyClient` leaking for a release — so the
guard here **walks the package** and cannot go stale that way.

No sockets: `httpx.stream` is replaced with a fake that serves bytes, truncates, or raises.
"""

import ast
import hashlib
import pathlib
from contextlib import contextmanager

import httpx
import pytest

from just_dna_enricher import net
from just_dna_enricher.net import RETRY_ATTEMPTS_ENV, StreamedFile, stream_to_file

_SRC = pathlib.Path(net.__file__).parent


class _Boom(RuntimeError):
    """A lane's own error type, standing in for the eleven real ones."""


# ── the walk: no builder may open a stream of its own ────────────────────────────────────────────


def _download_functions() -> dict[str, ast.FunctionDef]:
    """Every `download_*` function in the package, found by parsing rather than by importing.

    Parsed, so a module with a `[dev]`-only dependency (`polars`, `openpyxl`) is walked on a plain
    install too — an import-based walk quietly skips exactly the builder modules this guards.
    """
    found: dict[str, ast.FunctionDef] = {}
    for path in sorted(_SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("download_"):
                found[f"{path.name}::{node.name}"] = node
    return found


def test_the_walk_finds_the_downloads_it_is_supposed_to_guard() -> None:
    """A guard over an empty set passes vacuously, which is how a walk stops guarding anything.

    Named lanes rather than a count: `assert len(...) >= 11` would survive a builder being renamed
    out of the walk's reach, and a count has to be edited every time the tier grows a source
    correctly (`@registry-completeness`).
    """
    found = _download_functions()
    for expected in (
        "clinvar_build.py::download_clinvar_vcf",
        "clinvar_build.py::download_var_citations",
        "constraint_build.py::download_constraint_tsv",
        "clinpgx_build.py::download_clinpgx_zip",
        "drug_labels_build.py::download_drug_labels_zip",
        "mane_build.py::download_mane_file",
        "civic_build.py::download_civic_file",
        "pubmind_build.py::download_pubmind_table",
        "mitomap_build.py::download_mitomap_dump",
        "strchive_build.py::download_catalogue",
    ):
        assert expected in found, f"the walk no longer reaches {expected}"


def test_no_download_opens_its_own_stream() -> None:
    """The property the shared body exists to hold, over every `download_*` in the package.

    A function that streams for itself is a function that decides for itself whether to retry and
    what to raise — which is how four of eleven came to leak and eleven of eleven came to have no
    retry. `net.stream_to_file` is the only place `httpx.stream` may be called.
    """
    offenders = []
    for label, node in _download_functions().items():
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            target = inner.func
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "stream"
                and isinstance(target.value, ast.Name)
                and target.value.id == "httpx"
            ):
                offenders.append(label)
    assert offenders == [], (
        f"these downloads open a raw httpx stream instead of calling net.stream_to_file: {offenders}"
    )


def test_the_only_raw_stream_in_the_package_is_the_shared_one() -> None:
    """Stated over the whole package, not only over `download_*`-named functions.

    The narrow walk above is keyed on a naming convention, and a new bulk fetch called
    `fetch_dump` or `_pull` would satisfy it by not matching. This one cannot be evaded by naming.
    """
    streaming = set()
    for path in sorted(_SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "stream"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "httpx"
            ):
                streaming.add(path.name)
    assert streaming == {"net.py"}, f"httpx.stream is called outside net.py: {sorted(streaming)}"


# ── the behaviour, on a fake transport ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries without the backoff, so these run in milliseconds rather than seconds."""
    monkeypatch.setattr(net, "wait_exponential_jitter", lambda **kw: (lambda _state: 0))


def _fake_stream(script: list):
    """A stand-in for `httpx.stream` that plays `script`, one entry per attempt.

    An entry is either `bytes` (serve them and close cleanly) or an exception instance (raise it
    mid-body, after some bytes have been written — which is what a real truncation looks like and
    the reason the hasher has to be reset per attempt).
    """
    attempts = {"n": 0}

    @contextmanager
    def factory(_method, _url, **_kwargs):
        index = min(attempts["n"], len(script) - 1)
        attempts["n"] += 1
        entry = script[index]

        class _Response:
            headers = {"ETag": '"abc"', "Last-Modified": "Wed, 03 Sep 2026 00:00:00 GMT"}

            def raise_for_status(self):
                if isinstance(entry, httpx.HTTPStatusError):
                    raise entry

            def iter_bytes(self):
                if isinstance(entry, Exception):
                    yield b"partial"
                    raise entry
                yield entry

        yield _Response()

    factory.attempts = attempts
    return factory


def test_a_truncated_body_is_retried_and_the_second_attempt_wins(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The incident, reproduced: a connection cut mid-body, then a clean retry.

    `RemoteProtocolError` is raised *after* bytes have been written, so this also proves the retry
    restarts from zero — a retry that appended would leave `payload` prefixed with `partial` and the
    digest below would not match.
    """
    stream = _fake_stream([httpx.RemoteProtocolError("peer closed"), b"payload"])
    monkeypatch.setattr(net.httpx, "stream", stream)

    result = stream_to_file(
        tmp_path / "f.bin", "https://example.invalid/f.bin", error_cls=_Boom, what="a file",
    )
    assert stream.attempts["n"] == 2
    assert result.path.read_bytes() == b"payload"
    assert result.sha256 == hashlib.sha256(b"payload").hexdigest()
    assert not list(tmp_path.glob("*.part"))


def test_the_failure_that_motivated_this_is_the_one_the_predicate_retries() -> None:
    """The retry rests on `RemoteProtocolError` being a `TransportError`; assert it, don't assume it.

    If httpx ever re-parents it, the retry silently stops covering the incident that produced this
    item — and nothing else in the suite would notice.
    """
    assert issubclass(httpx.RemoteProtocolError, httpx.TransportError)
    assert issubclass(httpx.TransportError, httpx.HTTPError)


def test_a_status_error_is_not_retried(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 404 from a mistyped release tag is the same 404 four times over.

    Retrying it costs the caller three backoffs to learn what the first response already said, which
    is why the predicate is transport-only rather than `HTTPError`-wide.
    """
    status = httpx.HTTPStatusError(
        "404", request=httpx.Request("GET", "https://example.invalid/f"),
        response=httpx.Response(404),
    )
    stream = _fake_stream([status])
    monkeypatch.setattr(net.httpx, "stream", stream)

    with pytest.raises(_Boom):
        stream_to_file(tmp_path / "f.bin", "https://example.invalid/f", error_cls=_Boom, what="a file")
    assert stream.attempts["n"] == 1, "a status error was retried"


def test_a_persistent_transport_failure_is_translated_not_leaked(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the attempts are spent the caller gets ITS type — never httpx's.

    This is the property the lane adapters depend on: they catch their own builder's error, so a
    leaked `httpx` type means a lane that cannot report `built=False`.
    """
    monkeypatch.setattr(
        net.httpx, "stream", _fake_stream([httpx.ConnectError("no route")]),
    )
    with pytest.raises(_Boom) as caught:
        stream_to_file(
            tmp_path / "f.bin", "https://example.invalid/f", error_cls=_Boom, what="a thing",
            remedy="Pass a local copy instead.",
        )
    assert isinstance(caught.value.__cause__, httpx.HTTPError), "the cause is kept for a debugger"
    assert "a thing" in str(caught.value)
    assert "Pass a local copy instead." in str(caught.value)


def test_a_failed_fetch_leaves_the_directory_as_it_found_it(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neither a `.part` nor a truncated file under the real name (`@a-failed-fetch-is-not-a-no-op`).

    The pre-existing good file matters: `.part` staging is what keeps a failed re-fetch from
    truncating a copy that was already usable, which is how today's ClinVar rebuild survived the
    incident at all.
    """
    dest = tmp_path / "f.bin"
    dest.write_bytes(b"the good copy")
    monkeypatch.setattr(net.httpx, "stream", _fake_stream([httpx.ConnectError("nope")]))

    with pytest.raises(_Boom):
        stream_to_file(dest, "https://example.invalid/f", error_cls=_Boom, what="a file")
    assert dest.read_bytes() == b"the good copy"
    assert not list(tmp_path.glob("*.part"))


def test_the_digest_is_returned_rather_than_only_logged(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four of the eleven computed a sha256 and threw it away (`@dont-discard-computed`).

    A caller recording the provenance of bytes it has just fetched had to hash the file again; two
    lanes grew a `tuple[Path, str]` return for that reason, one at a time.
    """
    monkeypatch.setattr(net.httpx, "stream", _fake_stream([b"abc"]))
    result = stream_to_file(
        tmp_path / "f.bin", "https://example.invalid/f", error_cls=_Boom, what="a file",
    )
    assert isinstance(result, StreamedFile)
    assert result.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert result.etag == '"abc"'
    assert result.last_modified == "Wed, 03 Sep 2026 00:00:00 GMT"
    assert result.path == tmp_path / "f.bin", "the path is the destination, not the staging file"


def test_the_retry_floor_is_the_tiers_own_knob(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`$JUST_DNA_HTTP_RETRY_ATTEMPTS` raises this the way it raises every client's (RM42).

    Read at retry time rather than at import, which is the point of `attempt_floor` — a deployment
    on a flaky link can raise the floor without touching code, and this proves the new call site
    honours it rather than hard-coding three.
    """
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "5")
    stream = _fake_stream([httpx.ConnectError("flaky")])
    monkeypatch.setattr(net.httpx, "stream", stream)

    with pytest.raises(_Boom):
        stream_to_file(tmp_path / "f.bin", "https://example.invalid/f", error_cls=_Boom, what="x")
    assert stream.attempts["n"] == 5


# ── the lane, which is where the defect was actually felt ───────────────────────────────────────


def test_a_flaky_download_is_a_failed_lane_rather_than_a_traceback(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect end to end: a transport failure must reach `rebuild_lane` as an outcome.

    This is the assertion the item exists for. `RebuildOutcome` is tri-state and every adapter
    catches its own lane's error type — so a leaked `httpx` exception did not merely print badly, it
    escaped `rebuild_lane` entirely, and in a full `cache rebuild` loop that aborts every lane after
    the flaky one. Run through `rebuild_lane` rather than the adapter, because escaping *it* is the
    consequence that hurt.
    """
    from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest, rebuild_lane

    monkeypatch.setattr(net.httpx, "stream", _fake_stream([httpx.RemoteProtocolError("cut")]))
    outcome = rebuild_lane(
        LANES_BY_NAME["clinvar"], RebuildRequest(out_dir=tmp_path / "clinvar"),
    )
    assert outcome.built is False, "a flaky download must be a failed lane, not an exception"
    assert "ClinVar VCF" in outcome.detail


def test_without_the_translation_it_really_did_escape_the_lane(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The old behaviour demonstrated on the old arrangement, not asserted about the new one.

    `download_clinvar_vcf` is restored to raising the transport type, which is what it did before
    RM187 — and the exception comes straight back out of `rebuild_lane`. Without this the claim that
    the repair fixes something is a claim about code nobody ran.
    """
    from just_dna_enricher import caches, clinvar_build
    from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest, rebuild_lane

    def leaking(_dest, url=""):
        raise httpx.RemoteProtocolError("peer closed connection")

    monkeypatch.setattr(clinvar_build, "download_clinvar_vcf", leaking)
    monkeypatch.setattr(caches.clinvar_build, "download_clinvar_vcf", leaking)
    with pytest.raises(httpx.RemoteProtocolError):
        rebuild_lane(LANES_BY_NAME["clinvar"], RebuildRequest(out_dir=tmp_path / "clinvar"))
