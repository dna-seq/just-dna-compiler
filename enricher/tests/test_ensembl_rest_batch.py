"""Live Ensembl asks many rsIDs per request, and each gets exactly the answer its GET would (RM401, S133).

Before RM401 the live link and the placement witness sent one GET per rsID, and a re-derivation spent 599
of one module's 672 s on 59 cold GETs. `POST /variation/:species` takes up to 200 ids. Its 200 answer was
probed on 2026-11-07 before anything was built (`@probe-the-real-file`), and the mock below answers in
the shapes the probe saw:

* an rsID with a record is a key of the answer;
* a **merged** rsID is not: its record is keyed by the current id and lists the asked one in `synonyms`
  (`rs8192284` came back as `rs2228145`), while its GET answers 200 with that same record;
* an rsID with **no record is left out**, with no failure field (a batch of only such ids is `200 {}`),
  while its GET answers 400, RM361's no-record arm.

So an omission is never read as "no record" (`@unreachable-not-absent`): the rsID is asked by GET. A
failed batch, a POST 400 included, is could-not-ask for every rsID in it, never a negative. `batch_size=1`
is the off-switch (`@off-switch-needs-a-probe`), and it reproduces the one-GET-per-rsID pattern exactly.
"""

import json
import logging
from pathlib import Path

import httpx
import pytest
from just_dna_enricher.enrich import enrich
from just_dna_enricher.ensembl import (
    REST_BATCH_CEILING,
    BatchResolver,
    EnsemblResolver,
    EnsemblSettings,
    RestBatchWitness,
    _batch_records,
)
from just_dna_enricher.net import RETRY_ATTEMPTS_ENV, PacingGate


def _mapping(chrom: str, start: int, allele_string: str) -> dict:
    return {
        "assembly_name": "GRCh38",
        "seq_region_name": chrom,
        "start": start,
        "end": start,
        "allele_string": allele_string,
    }


#: Ensembl's records by current name, with the merged ids each lists as synonyms.
_RECORDS = {
    "rs1801133": {"name": "rs1801133", "mappings": [_mapping("1", 11796321, "G/A")], "synonyms": []},
    "rs2228145": {
        "name": "rs2228145",
        "mappings": [_mapping("1", 154454494, "A/C")],
        "synonyms": ["rs8192284"],
    },
    "rs429358": {"name": "rs429358", "mappings": [_mapping("19", 44908684, "T/C")], "synonyms": []},
    # RM400 and RM271 inside a batch: a patch-contig mapping and a no-variation one are not loci.
    "rs5": {
        "name": "rs5",
        "mappings": [_mapping("17", 100, "C/T"), _mapping("HSCHR17_1_CTG5", 9, "C/T")],
        "synonyms": [],
    },
    "rs6": {"name": "rs6", "mappings": [_mapping("1", 200, "dbSNP_novariation")], "synonyms": []},
}


def _record_for(rsid: str) -> dict | None:
    if rsid in _RECORDS:
        return _RECORDS[rsid]
    return next((r for r in _RECORDS.values() if rsid in r["synonyms"]), None)


class _Ensembl:
    """REST's two shapes, as probed. `post_status` fails every POST with that status."""

    def __init__(self, post_status: int = 200) -> None:
        self.post_status = post_status
        self.requests: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            ids = json.loads(request.content)["ids"]
            self.requests.append(f"POST {len(ids)}")
            if self.post_status != 200:
                return httpx.Response(self.post_status, text="No server is available to handle this request.")
            found = {rsid: _record_for(rsid) for rsid in ids}
            return httpx.Response(200, json={r["name"]: r for r in found.values() if r is not None})
        rsid = request.url.path.rsplit("/", 1)[-1]
        self.requests.append(f"GET {rsid}")
        record = _record_for(rsid)
        if record is None:
            return httpx.Response(400, json={"error": f"No variation found for ID '{rsid}'"})
        return httpx.Response(200, json=record)


def _resolver(server: _Ensembl, **settings: object) -> EnsemblResolver:
    resolver = EnsemblResolver(settings=EnsemblSettings(**settings), gate=PacingGate(interval=0.0))
    resolver._client = httpx.Client(transport=httpx.MockTransport(server))
    resolver._read_base = lambda _chrom, _pos: None
    return resolver


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)  # tenacity's backoff
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "")  # set, not deleted: a `.env` value would raise the floor


_ASKED = ["rs1801133", "rs8192284", "rs99999999999", "rs429358", "rs5", "rs6"]


def test_a_batch_answers_each_rsid_as_its_get_would() -> None:
    batched_server, single_server = _Ensembl(), _Ensembl()
    batched = dict(_resolver(batched_server).resolve_rsids_rest(_ASKED))
    single = dict(_resolver(single_server, batch_size=1).resolve_rsids_rest(_ASKED))
    assert batched == single
    assert batched["rs8192284"] == (
        [{"chrom": "1", "start": 154454494, "ref": "A", "alts": "C"}],
        "ensembl-rest",
    )
    assert batched["rs99999999999"] == ([], "ensembl-rest")  # the GET's 400, never the omission
    assert batched["rs5"] == ([{"chrom": "17", "start": 100, "ref": "C", "alts": "T"}], "ensembl-rest")
    assert batched["rs6"] == ([], "ensembl-rest")
    # One POST, and one GET for the one rsID the batch left out; the off-switch is a GET per rsID.
    assert batched_server.requests == ["POST 6", "GET rs99999999999"]
    assert single_server.requests == [f"GET {rsid}" for rsid in _ASKED]


def test_an_rsid_a_batch_leaves_out_is_asked_by_get_never_written_as_no_record() -> None:
    """The omission does not say why. Here the batch leaves out an rsID its GET answers: reading the
    omission as "no record" would write `[]` (a `not_found` row) for a placed variant."""

    class _Omitting(_Ensembl):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if request.method == "POST":
                body = {k: v for k, v in json.loads(response.content).items() if k != "rs429358"}
                return httpx.Response(200, json=body)
            return response

    server = _Omitting()
    answers = dict(_resolver(server).resolve_rsids_rest(["rs1801133", "rs429358"]))
    assert answers["rs429358"] == (
        [{"chrom": "19", "start": 44908684, "ref": "T", "alts": "C"}],
        "ensembl-rest",
    )
    assert server.requests == ["POST 2", "GET rs429358"]


def test_the_answers_come_back_in_the_order_asked_with_the_asked_rsid_as_the_key() -> None:
    answers = list(_resolver(_Ensembl()).resolve_rsids_rest(_ASKED))
    assert [rsid for rsid, _answer in answers] == _ASKED  # rs8192284 is never renamed rs2228145


def test_the_no_variation_rsid_is_collected_as_its_get_collects_it() -> None:
    resolver = _resolver(_Ensembl())
    dict(resolver.resolve_rsids_rest(_ASKED))
    assert resolver.non_nucleotide_rsids == {"rs6"}


def test_two_records_naming_an_rsid_send_it_to_the_get() -> None:
    payload = {
        "rs10": {"name": "rs10", "synonyms": ["rs7"]},
        "rs11": {"name": "rs11", "synonyms": ["rs7"]},
        "rs12": {"name": "rs12", "synonyms": ["rs8"]},
        "rs13": ["not a record"],
    }
    assert _batch_records(payload, ["rs7", "rs8", "rs10", "rs13", "rs14"]) == {
        "rs8": payload["rs12"],
        "rs10": payload["rs10"],
    }


@pytest.mark.parametrize("status", [503, 400, 429])
def test_a_failed_batch_is_could_not_ask_for_every_rsid_never_a_negative(
    status: int, caplog: pytest.LogCaptureFixture
) -> None:
    """A POST 400 is not the GET's 400: it says nothing about any one rsID, so nobody was answered."""
    server = _Ensembl(post_status=status)
    with caplog.at_level(logging.WARNING):
        answers = dict(_resolver(server).resolve_rsids_rest(_ASKED))
    assert answers == dict.fromkeys(_ASKED, (None, None))
    assert all(request.startswith("POST") for request in server.requests)  # no GET fallback in an outage
    assert any("V1 REST batch of 6 rsID(s) failed" in r.getMessage() for r in caplog.records)


def test_a_transport_failure_is_could_not_ask_for_every_rsid() -> None:
    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("The read operation timed out", request=request)

    resolver = EnsemblResolver(gate=PacingGate(interval=0.0))
    resolver._client = httpx.Client(transport=httpx.MockTransport(dead))
    assert dict(resolver.resolve_rsids_rest(["rs1", "rs2"])) == {"rs1": (None, None), "rs2": (None, None)}


def test_batches_are_cut_at_the_setting_and_capped_at_ensembls_ceiling() -> None:
    server = _Ensembl()
    asked = [f"rs{n}" for n in range(1000, 1045)]
    dict(_resolver(server, batch_size=20).resolve_rsids_rest(asked))
    posts = [r for r in server.requests if r.startswith("POST")]
    assert posts == ["POST 20", "POST 20", "POST 5"]
    server = _Ensembl()
    dict(_resolver(server, batch_size=10_000).resolve_rsids_rest([f"rs{n}" for n in range(1000, 1250)]))
    assert [r for r in server.requests if r.startswith("POST")] == [f"POST {REST_BATCH_CEILING}", "POST 50"]


def test_the_next_batch_waits_until_every_answer_of_the_one_before_is_taken() -> None:
    """What lets the live link journal each answer before the next request (minute 29 recoverable)."""
    server = _Ensembl()
    answers = _resolver(server, batch_size=2).resolve_rsids_rest(["rs1801133", "rs429358", "rs2228145"])
    next(answers)
    assert server.requests == ["POST 2"]
    next(answers)
    assert server.requests == ["POST 2"]
    next(answers)
    assert server.requests == ["POST 2", "POST 1"]


def test_a_throttle_past_the_ceiling_holds_the_batches_after_it() -> None:
    server = _Ensembl()

    def throttled(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and not server.requests:
            server.requests.append("POST throttled")
            return httpx.Response(429, headers={"Retry-After": "3600"})
        return server(request)

    resolver = EnsemblResolver(settings=EnsemblSettings(batch_size=2), gate=PacingGate(interval=0.0))
    resolver._client = httpx.Client(transport=httpx.MockTransport(throttled))
    answers = dict(resolver.resolve_rsids_rest(["rs1801133", "rs429358", "rs2228145"]))
    assert answers == dict.fromkeys(["rs1801133", "rs429358", "rs2228145"], (None, None))
    assert server.requests == ["POST throttled"]  # the second batch was never sent


def test_the_resolver_offers_both_batch_capabilities_and_a_post_timeout_of_its_own() -> None:
    resolver = EnsemblResolver()
    assert isinstance(resolver, BatchResolver) and isinstance(resolver, RestBatchWitness)
    seen: list[httpx.Timeout] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(httpx.Timeout(**request.extensions["timeout"]))
        return httpx.Response(200, json={})

    resolver = EnsemblResolver(settings=EnsemblSettings(batch_timeout=90.0), gate=PacingGate(interval=0.0))
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    next(resolver.resolve_rsids_rest(["rs1", "rs2"]))
    assert seen[0].read == 90.0 and seen[0].connect == resolver.settings.timeout


_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


class _OneAtATime:
    """A host's resolver written before RM401: `resolve_rsid` alone, no batch capability."""

    def __init__(self, inner: EnsemblResolver) -> None:
        self.inner = inner

    def resolve_rsid(self, rsid: str):
        return self.inner.resolve_rsid(rsid)


@pytest.mark.usefixtures("no_ambient_caches")
@pytest.mark.parametrize("batching", [True, False])
def test_the_live_link_asks_its_misses_in_one_batch_and_a_host_resolver_one_at_a_time(
    tmp_path: Path, batching: bool
) -> None:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\nrs8192284,A/C,risk,c\nrs99999999999,A/G,risk,c\n",
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,9545397\n", encoding="utf-8")
    server = _Ensembl()
    ours = _resolver(server)
    result = enrich(
        spec,
        ensembl_cache=tmp_path / "no-snapshot",
        clinvar_cache=tmp_path / "no-snapshot",
        resolver=ours if batching else _OneAtATime(ours),
        use_gnomad=False,
        download=False,
        verify_ref=False,
        verify_rsids=False,
        verify_clinsig=False,
        verify_datasets=False,
    )
    asked = [r for r in server.requests if r != "GET data"]  # `/info/data`, the release label
    if batching:
        assert asked == ["POST 3", "GET rs99999999999"]
    else:
        assert asked == ["GET rs1801133", "GET rs8192284", "GET rs99999999999"]
    placed = {row.rsid: (row.chrom, row.start) for row in result.rows if row.status != "not_found"}
    assert placed == {"rs1801133": ("1", 11796321), "rs8192284": ("1", 154454494)}
    assert result.unreachable_rsids == []
