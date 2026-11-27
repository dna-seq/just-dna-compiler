"""Release-keyed answers at the network boundary (RM468)."""

import json
import os
import sqlite3
import subprocess
import sys
import threading
import weakref
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.answer_store import AnswerRun, answer_run
from just_dna_enricher.cli import app
from just_dna_enricher.eutils import EutilsClient, EutilsError, is_missing
from just_dna_enricher.grch37 import Grch37Client
from just_dna_enricher.locations import CACHE_BASE_VAR
from just_dna_enricher.net import RETRY_ATTEMPTS_ENV, PacingGate
from just_dna_enricher.sequences import DEFAULT_SEQREPO_URI, SequenceProxy
from just_dna_format.vrs import refget_accession
from typer.testing import CliRunner

_BUILD = {
    "snp": ("Build250306-1408.1", "2025/03/11 08:22"),
    "clinvar": ("Build261123-1425.2", "2026/11/24 09:36"),
    "pubmed": ("Build-2026.11.26.06.20", None),
}


_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_SUMMARIES = {
    db: json.loads((_ASSETS / filename).read_text())["result"]
    for db, filename in (("snp", "dbsnp_esummary_payload.json"), ("pubmed", "pubmed_esummary_payload.json"))
}


class Eutils:
    def __init__(self) -> None:
        self.builds: dict[str, tuple[object, str | None]] = dict(_BUILD)
        self.asked: list[tuple[str, str, str]] = []
        self.reply: Callable[[httpx.Request], httpx.Response] = self.summary

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        db = params["db"]
        path = request.url.path.split("/")[-1]
        self.asked.append((path, db, params.get("id", "")))
        assert params["retmode"] == "json"
        if path == "einfo.fcgi":
            build, updated = self.builds[db]
            info = {"dbbuild": build} if build is not None else {}
            if updated is not None:
                info["lastupdate"] = updated
            return httpx.Response(200, json={"einforesult": {"dbinfo": [info]}})
        return self.reply(request)

    def summary(self, request: httpx.Request) -> httpx.Response:
        ids = request.url.params["id"].split(",")
        fixture = _SUMMARIES.get(request.url.params["db"], {})
        records = {uid: fixture[uid] for uid in ids if uid in fixture}
        if not records:
            return httpx.Response(200, json={"esummaryresult": [f"Invalid uid {uid}" for uid in ids]})
        return httpx.Response(200, json={"result": {"uids": list(records), **records}})

    def client(self) -> EutilsClient:
        return EutilsClient(gate=PacingGate(0), _client=httpx.Client(transport=httpx.MockTransport(self)))


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "answers.db"
    monkeypatch.setenv("JUST_DNA_ANSWER_STORE", str(path))
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "")
    monkeypatch.setattr("time.sleep", lambda _: None)
    return path


def test_default_directory_and_test_fence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = Eutils()
    monkeypatch.setenv(CACHE_BASE_VAR, str(tmp_path))
    assert os.environ.get("JUST_DNA_ANSWER_STORE") == ""
    for _ in range(2):
        server.client().esummary("snp", ["334"])
    assert not list(tmp_path.iterdir())
    assert [p for p, _, _ in server.asked] == ["esummary.fcgi"] * 2
    monkeypatch.delenv("JUST_DNA_ANSWER_STORE")
    monkeypatch.chdir(tmp_path)
    first = server.client().esummary("snp", ["334"])
    (file,) = tmp_path.iterdir()
    assert file.is_file()
    monkeypatch.setenv("JUST_DNA_ANSWER_STORE", str(tmp_path))
    server.asked.clear()
    assert server.client().esummary("snp", ["334"]) == first
    assert server.asked == [("einfo.fcgi", "snp", "")]


def test_builds_isolate_databases_and_only_misses_go_in_batch(store: Path) -> None:
    server = Eutils()
    uid = "334"
    client = server.client()
    answers = {db: client.esummary(db, [uid]) for db in _BUILD}
    assert server.asked == [
        call for db in _BUILD for call in [("einfo.fcgi", db, ""), ("esummary.fcgi", db, uid)]
    ]
    server.asked.clear()
    server.builds["snp"] = ("new-build", None)
    client = server.client()
    for db, old in answers.items():
        assert client.esummary(db, [uid]) == old
        assert list(client.esummary(db, ["3216883", uid])) == ["3216883", uid]
    expected = [
        call
        for db in _BUILD
        for call in (
            [("einfo.fcgi", db, "")]
            + ([("esummary.fcgi", db, uid)] if db == "snp" else [])
            + [("einfo.fcgi", db, ""), ("esummary.fcgi", db, "3216883")]
        )
    ]
    assert server.asked == expected


@pytest.mark.parametrize("build", [None, "", "  ", 116])
def test_no_dbbuild_bypasses_existing_rows(
    store: Path, build: object, caplog: pytest.LogCaptureFixture
) -> None:
    server = Eutils()
    server.client().esummary("snp", ["334"])
    server.asked.clear()
    server.builds["snp"] = (build, "2026/11/24 09:36")
    client = server.client()
    with answer_run():
        for _ in range(2):
            client.esummary("snp", ["334"])
    assert [p for p, _, _ in server.asked] == ["einfo.fcgi", "esummary.fcgi", "esummary.fcgi"]
    assert sum("answer store" in r.message.lower() for r in caplog.records) == 1


@pytest.mark.parametrize("failure", ["timeout", 503, 429, 403, "refusal", "record error", "empty record"])
def test_failures_are_asked_again(store: Path, failure: str | int) -> None:
    server = Eutils()
    uid = "334"

    def fail(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if isinstance(failure, int):
            return httpx.Response(failure)
        if failure == "refusal":
            return httpx.Response(200, json={"error": "API key invalid"})
        record = {"error": "service busy"} if failure == "record error" else {}
        return httpx.Response(200, json={"result": {"uids": [uid], uid: record}})

    server.reply = fail
    if failure in ("record error", "empty record"):
        server.client().esummary("snp", [uid])
    else:
        with pytest.raises(EutilsError):
            server.client().esummary("snp", [uid])
    assert len([p for p, _, _ in server.asked if p == "esummary.fcgi"]) == (
        4 if failure in ("timeout", 503, 429) else 1
    )
    server.reply = server.summary
    server.asked.clear()
    assert server.client().esummary("snp", [uid])[uid]["uid"] == uid
    assert [p for p, _, _ in server.asked] == ["einfo.fcgi", "esummary.fcgi"]


def test_answered_absence_and_wal(store: Path) -> None:
    server = Eutils()
    uid = "99999999999"
    server.reply = lambda _: httpx.Response(200, json={"esummaryresult": [f"Invalid uid {uid}"]})
    first = server.client().esummary("snp", [uid])
    assert is_missing(first[uid])
    server.asked.clear()
    assert server.client().esummary("snp", [uid]) == first
    assert server.asked == [("einfo.fcgi", "snp", "")]
    with closing(sqlite3.connect(store)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connection.execute("SELECT release, absent FROM answers").fetchall() == [(_BUILD["snp"][0], 1)]


def test_corrupt_store_warns_once_and_completes_live(store: Path, caplog: pytest.LogCaptureFixture) -> None:
    store.write_bytes(b"unreadable as sqlite")
    server = Eutils()
    client = server.client()
    with answer_run():
        for uid in ["334", "3216883"]:
            assert client.esummary("snp", [uid])[uid]["uid"] == uid
    assert sum("answer store" in r.message.lower() for r in caplog.records) == 1
    assert store.read_bytes() == b"unreadable as sqlite"


def test_two_threads_one_client_and_store(store: Path) -> None:
    server = Eutils()
    client = server.client()
    ids = ["334", "3216883"]
    both_live = threading.Barrier(2)

    def together(request: httpx.Request) -> httpx.Response:
        both_live.wait(timeout=30)
        return server.summary(request)

    server.reply = together
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda uid: client.esummary("snp", [uid]), ids))
    assert server.asked.count(("einfo.fcgi", "snp", "")) == len(ids)
    server.reply = server.summary
    server.asked.clear()
    assert server.client().esummary("snp", ids) == {uid: row[uid] for uid, row in zip(ids, rows, strict=True)}
    assert server.asked == [("einfo.fcgi", "snp", "")]


def test_seqrepo_remote_reads_only(store: Path) -> None:
    accession = refget_accession("1")
    assert accession is not None
    calls: list[tuple[str, int, int]] = []

    class Proxy:
        def get_sequence(self, name: str, start: int, end: int) -> str:
            calls.append((name, start, end))
            return "a" if start == 0 else ""

    for uri in [DEFAULT_SEQREPO_URI] * 2 + ["seqrepo+file:///local"] * 2:
        proxy = SequenceProxy(uri=uri, _proxy=Proxy())
        assert proxy.subsequence(accession, 0, 1) == "A"
        assert proxy.subsequence(accession, 1, 2) is None
    assert calls.count((f"ga4gh:{accession}", 0, 1)) == 3
    assert calls.count((f"ga4gh:{accession}", 1, 2)) == 4


def test_cli_off_reaches_live_client(store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(
        Grch37Client, "_http", lambda self: httpx.Client(transport=httpx.MockTransport(handle))
    )
    for _ in range(2):
        result = CliRunner().invoke(
            app, ["--no-answer-store", "hint", "recover", "--chrom", "7", "--start", "140453136"]
        )
        assert result.exit_code == 0, result.output
    assert calls == ["/overlap/region/human/7:140453136-140453136"] * 2
    assert not store.exists()


def test_grch37_uses_its_own_server_for_release_and_distinguishes_empty_body(store: Path) -> None:
    seen: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.url.path))
        if request.url.path == "/info/data":
            return httpx.Response(200, json={"releases": [116]})
        if "sequence" in request.url.path:
            return httpx.Response(200, text="")
        return httpx.Response(200, json=[])

    hosts = ["grch37.rest.ensembl.org", "grch37.rest.ensembl.org", "mirror.test"]
    for host in hosts:
        client = Grch37Client(gate=PacingGate(0), _client=httpx.Client(transport=httpx.MockTransport(handle)))
        client.settings.endpoint = f"https://{host}"
        assert client.variants_at("7", 140453136) == []
        assert client.reference_bases("7", 140453136, 140453136) == ""
    overlap = "/overlap/region/human/7:140453136-140453136"
    assert seen.count(("grch37.rest.ensembl.org", overlap)) == 1
    assert ("mirror.test", overlap) in seen
    assert [h for h, p in seen if p == "/info/data"] == [host for host in hosts for _ in range(2)]
    assert len([p for _, p in seen if "sequence" in p]) == 3


def test_einfo_outage_is_retried_then_bypassed_once(store: Path) -> None:
    server = Eutils()
    calls: list[str] = []

    def outage(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path.split("/")[-1])
        if calls[-1] == "einfo.fcgi":
            return httpx.Response(503)
        return server.summary(request)

    client = EutilsClient(gate=PacingGate(0), _client=httpx.Client(transport=httpx.MockTransport(outage)))
    with answer_run():
        for _ in range(2):
            assert client.esummary("snp", ["334"])["334"]["uid"] == "334"
    assert calls == ["einfo.fcgi"] * 4 + ["esummary.fcgi"] * 2
    assert not store.exists()


def test_fence_leaves_an_existing_default_store_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(CACHE_BASE_VAR, str(tmp_path))
    monkeypatch.chdir(tmp_path)
    server = Eutils()
    with monkeypatch.context() as seed:
        seed.delenv("JUST_DNA_ANSWER_STORE", raising=False)
        server.client().esummary("snp", ["334"])
    (existing,) = tmp_path.iterdir()
    before = existing.read_bytes()
    server.asked.clear()
    ids = ["334", "3216883"]
    assert list(server.client().esummary("snp", ids)) == ids
    assert server.asked == [("esummary.fcgi", "snp", ",".join(ids))]
    assert existing.read_bytes() == before and list(tmp_path.iterdir()) == [existing]


def test_two_processes_can_initialize_and_write_one_file(store: Path) -> None:
    # Each interpreter owns its connection and waits at stdin just before its first write.
    script = """
import sys
from pathlib import Path
from just_dna_enricher.answer_store import AnswerStore

store = AnswerStore(Path(sys.argv[1]))
subject = sys.argv[2]
sys.stdout.write("ready\\n")
sys.stdout.flush()
sys.stdin.readline()
store.write("https://rest.ensembl.org", "ensembl_116", {subject: ({"name": subject}, False)})
"""
    subjects = ["rs1801133", "rs429358"]
    with ExitStack() as stack:
        children = [
            stack.enter_context(
                subprocess.Popen(
                    [sys.executable, "-c", script, str(store), subject],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                )
            )
            for subject in subjects
        ]
        for child in children:
            assert child.stdout is not None
            assert child.stdout.readline() == "ready\n"
        for child in children:
            assert child.stdin is not None
            child.stdin.write("\n")
            child.stdin.flush()
        for child in children:
            assert child.wait(timeout=30) == 0
    with closing(sqlite3.connect(store)) as db:
        assert {key for (key,) in db.execute("SELECT request_key FROM answers")} == set(subjects)


@pytest.mark.parametrize(
    "status,body,storable",
    [
        (400, {"error": "no such region"}, True),
        (400, {"error": "request refused"}, False),
    ],
)
def test_grch37_persists_only_explicit_absence(store: Path, status: int, body: dict, storable: bool) -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/info/data":
            return httpx.Response(200, json={"releases": [116]})
        return httpx.Response(status, json=body)

    for _ in range(2):
        client = Grch37Client(gate=PacingGate(0), _client=httpx.Client(transport=httpx.MockTransport(handle)))
        assert client.reference_bases("20", 63500000, 63500000) == ""
    assert calls.count("/info/data") == 2
    assert calls.count("/sequence/region/human/20:63500000..63500000") == (1 if storable else 2)


def test_mid_batch_write_failure_rolls_back_and_the_live_answer_survives(
    store: Path, caplog: pytest.LogCaptureFixture
) -> None:
    server = Eutils()
    client = server.client()
    fixture = _SUMMARIES["snp"]
    seed, *batch = fixture["uids"]
    client.esummary("snp", [seed])
    with closing(sqlite3.connect(store)) as db:
        db.execute("""CREATE TRIGGER fail_second BEFORE INSERT ON answers
                      WHEN (SELECT count(*) FROM answers) > 1
                      BEGIN SELECT RAISE(ABORT, 'simulated write failure'); END""")
    assert client.esummary("snp", batch) == {uid: fixture[uid] for uid in batch}
    with closing(sqlite3.connect(store)) as db:
        assert {key for (key,) in db.execute("SELECT request_key FROM answers")} == {seed}
    assert sum("answer store" in row.message.lower() for row in caplog.records) == 1


def test_seqrepo_does_not_store_a_refusal_body_or_a_truncated_interval(store: Path) -> None:
    accession = refget_accession("19")
    assert accession is not None
    replies = iter(["Access denied", "A", "AC", "unexpected extra call"])

    class Proxy:
        def get_sequence(self, name: str, start: int, end: int) -> str:
            return next(replies)

    reads = [SequenceProxy(_proxy=Proxy()).subsequence(accession, 0, 2) for _ in range(4)]
    assert reads[-2:] == ["AC", "AC"]
    assert next(replies) == "unexpected extra call"


@pytest.mark.parametrize("source", ["eutils", "seqrepo"])
def test_client_releases_the_run_after_each_of_100_calls(
    source: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    counted: weakref.WeakSet[AnswerRun] = weakref.WeakSet()
    count = AnswerRun.count

    def observe(run: AnswerRun, source: str, release: str | None, *, stored: int = 0, live: int = 0) -> None:
        counted.add(run)
        count(run, source, release, stored=stored, live=live)

    monkeypatch.setattr(AnswerRun, "count", observe)
    calls = range(100)
    if source == "eutils":
        server = Eutils()
        client = server.client()
        uid = _SUMMARIES["snp"]["uids"][0]
        for _ in calls:
            assert client.esummary("snp", [uid])[uid] == _SUMMARIES["snp"][uid]
        assert server.asked == [("esummary.fcgi", "snp", uid)] * len(calls)
    else:
        intervals: list[tuple[str, int, int]] = []

        class Proxy:
            def get_sequence(self, name: str, start: int, end: int) -> str:
                intervals.append((name, start, end))
                return "A"

        accession = refget_accession("1")
        assert accession is not None
        proxy = SequenceProxy(_proxy=Proxy())
        for start in calls:
            assert proxy.subsequence(accession, start, start + 1) == "A"
        assert intervals == [(f"ga4gh:{accession}", start, start + 1) for start in calls]
    assert not list(counted), [run.report() for run in counted]


def test_nested_answer_run_uses_the_host_run(store: Path) -> None:
    with answer_run(store) as host, answer_run(False) as nested:
        assert nested is host
