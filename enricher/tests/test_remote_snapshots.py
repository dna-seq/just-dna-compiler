"""`RemoteSnapshots`: the registry's proxy, then Hugging Face, for a box with no local snapshot (RM430).

Hugging Face is a `LoopbackHub` (the enricher conftest): the Hub's revision API and `resolve` route with
HTTP range requests on 127.0.0.1, serving real snapshot bytes: ClinVar built by the real builder from
`assets/clinvar_GRCh38_slice.vcf.gz`, and Ensembl's split release from the RM381 slice of published rows,
laid out one file per chromosome under a `manifest.json` as the published repo is. The proxy is an
`httpx.MockTransport` answering with the registry's semantics over the same files, read with polars as
the registry reads them, so the two routes are two independent readers of one snapshot.
"""

import hashlib
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb
import httpx
import polars as pl
import pytest
from just_dna_enricher import remote
from just_dna_enricher.caches import CACHE_LANES, LANES_BY_NAME
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS
from just_dna_enricher.net import could_not_ask_reason
from just_dna_enricher.remote import (
    REMOTE_LANES,
    RemoteAnswer,
    RemoteRoute,
    RemoteSnapshots,
    SnapshotRouteUnavailable,
)

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
#: The release the RM381 slice was copied from (its README), stated by the fixture's manifest.
ENSEMBL_RELEASE = "ensembl-variation-2026_07_13-vep116.0"
#: A loopback proxy URL: never contacted, the `MockTransport` answers, and the fence lets it through.
PROXY = "http://127.0.0.1:9"
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


@pytest.fixture(autouse=True)
def _no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's `.env` may name a proxy; set empty rather than deleted, so it cannot refill it."""
    monkeypatch.setenv(remote.PROXY_URL_VAR, "")
    monkeypatch.setenv(remote.PROXY_TOKEN_VAR, "")


@pytest.fixture(scope="module")
def clinvar_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("remote") / "clinvar"
    build_snapshot(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", root)
    return root


@pytest.fixture(scope="module")
def ensembl_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The split slice, one file per chromosome, attested by a manifest as the published repo is."""
    root = tmp_path_factory.mktemp("remote") / "ensembl"
    (root / "data").mkdir(parents=True)
    source = _ASSETS / "ensembl_split_multialt" / "split" / "data" / "homo_sapiens-split.parquet"
    con = duckdb.connect()
    chroms = [
        c
        for (c,) in con.execute(f"SELECT DISTINCT chrom FROM read_parquet('{source}') ORDER BY 1").fetchall()
    ]
    files = []
    for chrom in chroms:
        target = root / "data" / f"homo_sapiens-chr{chrom}.parquet"
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{source}') WHERE chrom = '{chrom}' ORDER BY row_idx) "
            f"TO '{target}' (FORMAT parquet)"
        )
        data = target.read_bytes()
        files.append(
            {
                "path": f"data/{target.name}",
                "group": "core",
                "chrom": chrom,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    con.close()
    (root / "manifest.json").write_text(json.dumps({"release_id": ENSEMBL_RELEASE, "files": files}))
    return root


def _published(hub: Any, clinvar_root: Path, ensembl_root: Path) -> None:
    hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    hub.publish(SNAPSHOT_REPO_IDS["ensembl"], ensembl_root, COMMIT_A)


def _registry_rows(root: Path, keys: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """The registry's lane filter (its `services/lanes.py`), over the same files, with polars."""
    frame = pl.scan_parquet(sorted(str(p) for p in (root / "data").glob("*.parquet")))
    condition = None
    if "chrom" in keys and len(keys["chrom"]) == len(keys["start"]) > 1:
        condition = pl.any_horizontal(
            [
                pl.col("chrom")
                .cast(pl.String)
                .is_in([str(c).removeprefix("chr"), f"chr{str(c).removeprefix('chr')}"])
                & (pl.col("start") == int(s))
                for c, s in zip(keys["chrom"], keys["start"], strict=True)
            ]
        )
        keys = {k: v for k, v in keys.items() if k not in ("chrom", "start")}
    for column, values in keys.items():
        if column == "chrom":
            clause = pl.col("chrom").cast(pl.String).is_in([f for v in values for f in (str(v), f"chr{v}")])
        elif column == "start":
            clause = pl.col("start").is_in([int(v) for v in values])
        else:
            clause = pl.col(column).cast(pl.String).is_in([str(v) for v in values])
        condition = clause if condition is None else condition & clause
    return json.loads(frame.filter(condition).collect().write_json())


class _Proxy:
    """A `MockTransport` registry: it answers each lane from a directory, and records each request."""

    def __init__(self, roots: dict[str, Path], *, max_rows: int = 1000, release: str | None = None) -> None:
        self.roots = roots
        self.max_rows = max_rows
        self.release = release
        self.asked: list[tuple[str, dict[str, list[Any]]]] = []
        self.status: Callable[[httpx.Request], httpx.Response | None] = lambda request: None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        staged = self.status(request)
        if staged is not None:
            return staged
        lane, table = request.url.path.split("/")[-2:]
        keys = json.loads(request.content)["keys"]
        self.asked.append((lane, keys))
        assert sum(len(v) for v in keys.values()) <= remote.PROXY_MAX_KEY_VALUES
        rows = _registry_rows(self.roots[lane], keys)
        reply = {
            "lane": lane,
            "table": table,
            "served_from": "local",
            "rows": rows[: self.max_rows],
            "truncated": len(rows) > self.max_rows,
            "terms": None,
            "unpublished": None,
        }
        if self.release is not None:
            reply["release"] = self.release
        return httpx.Response(200, json=reply)


def _with_proxy(holder: RemoteSnapshots, proxy: Callable[[httpx.Request], httpx.Response]) -> RemoteSnapshots:
    holder._proxy = httpx.Client(transport=httpx.MockTransport(proxy))
    return holder


# ── the registration ────────────────────────────────────────────────────────────────────────────


def test_every_remote_lane_is_a_published_lane_and_the_excluded_ones_are_not_remote() -> None:
    assert set(REMOTE_LANES) <= set(SNAPSHOT_REPO_IDS) & set(LANES_BY_NAME)
    assert set(REMOTE_LANES) == {"ensembl", "clinvar", "constraint", "clinpgx", "cpic", "drug_labels"}
    assert not set(REMOTE_LANES) & {"mitomap", "strchive", "alphagenome_avi", "pharmvar", "pubmind"}
    assert [name for name, lane in REMOTE_LANES.items() if lane.needs_position] == ["ensembl"]
    assert {lane.name for lane in CACHE_LANES} >= set(REMOTE_LANES)


def test_table_names_collapse_the_shard_suffix_as_the_registry_does() -> None:
    assert remote.table_name("data/homo_sapiens-chr19.parquet") == "homo_sapiens"
    assert remote.table_name("data/clinvar-chrX.parquet") == "clinvar"
    assert remote.table_name("data/credible_set_members-00000.parquet") == "credible_set_members"
    assert remote.table_name("data/gnomad_constraint.parquet") == "gnomad_constraint"


# ── Hugging Face, over loopback ────────────────────────────────────────────────────────────────


def test_hf_answers_clinvar_by_rsid_with_the_rows_the_local_snapshot_holds(
    httpfs, loopback_hub, clinvar_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    expected = _registry_rows(clinvar_root, {"rsid": ["rs334"]})
    assert expected  # the slice holds rs334, so an empty answer cannot pass
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    release = json.loads((clinvar_root / "release.json").read_text())["dataset"]
    assert answer.rows == remote._stable(expected)
    assert (answer.route, answer.release, answer.served_from, answer.revision) == (
        "hf",
        release,
        None,
        COMMIT_A,
    )
    assert answer.provenance() == RemoteRoute("hf", release, None, COMMIT_A)


def test_hf_opens_only_the_chromosome_file_the_manifest_attests_for_ensembl(
    httpfs, loopback_hub, ensembl_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["ensembl"], ensembl_root, COMMIT_A)
    expected = _registry_rows(ensembl_root, {"chrom": ["16"], "start": [23635706]})
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup("ensembl", "homo_sapiens", {"chrom": ["chr16"], "start": [23635706]})
    assert answer.rows and answer.rows == remote._stable(expected)
    assert answer.release == ENSEMBL_RELEASE and answer.revision == COMMIT_A
    parquet = {path.rsplit("/", 1)[-1] for path in loopback_hub.paths() if path.endswith(".parquet")}
    assert parquet == {"homo_sapiens-chr16.parquet"}


def test_an_ensembl_key_without_a_position_is_never_sent(loopback_hub, ensembl_root: Path) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["ensembl"], ensembl_root, COMMIT_A)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder, pytest.raises(ValueError) as refused:
        holder.lookup("ensembl", "homo_sapiens", {"id": ["rs1555461597"]})
    assert "answers remotely by chrom + start only" in str(refused.value)
    assert loopback_hub.requests == []


def test_a_holder_stays_on_the_commit_it_pinned_and_a_new_holder_reads_the_new_one(
    httpfs, loopback_hub, clinvar_root: Path, tmp_path: Path
) -> None:
    """One release per route per holder: `main` moving mid-session does not move the session."""
    hub_repo = SNAPSHOT_REPO_IDS["clinvar"]
    loopback_hub.publish(hub_repo, clinvar_root, COMMIT_A)
    moved = tmp_path / "moved"
    build_snapshot(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", moved)
    record = json.loads((moved / "release.json").read_text())
    record["dataset"] = "clinvar_next"
    (moved / "release.json").write_text(json.dumps(record))
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        first = holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
        loopback_hub.publish(hub_repo, moved, COMMIT_B)
        second = holder.lookup("clinvar", "clinvar", {"chrom": ["11"], "start": [5227002]})
    assert (first.revision, second.revision) == (COMMIT_A, COMMIT_A)
    assert first.release == second.release != "clinvar_next"
    revision_reads = [p for p in loopback_hub.paths() if "/revision/" in p]
    assert len(revision_reads) == 1
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as fresh:
        third = fresh.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert (third.revision, third.release) == (COMMIT_B, "clinvar_next")


def test_threads_share_one_pin_and_each_query_gets_its_own_cursor(
    httpfs, loopback_hub, clinvar_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    rsids = ["rs334", "rs368250686", "rs1291411884", "rs761341010"]
    answers: dict[str, RemoteAnswer] = {}
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        threads = [
            threading.Thread(
                target=lambda r=r: answers.__setitem__(r, holder.lookup("clinvar", "clinvar", {"rsid": [r]}))
            )
            for r in rsids
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(holder._pins) == 1
    for rsid in rsids:
        assert answers[rsid].rows == remote._stable(_registry_rows(clinvar_root, {"rsid": [rsid]})), rsid
        assert {row["rsid"] for row in answers[rsid].rows} == {rsid}
    assert len([p for p in loopback_hub.paths() if "/revision/" in p]) == 1


def test_a_hub_429_is_could_not_ask_naming_the_quota_window(httpfs, loopback_hub, clinvar_root: Path) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    loopback_hub.fail["clinvar-chr11.parquet"] = 429
    with (
        RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder,
        pytest.raises(SnapshotRouteUnavailable) as failed,
    ):
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert (failed.value.lane, failed.value.route) == ("clinvar", "hf")
    assert remote.HF_QUOTA_WINDOW in str(failed.value)
    assert isinstance(failed.value.__cause__, duckdb.HTTPException)
    assert not isinstance(failed.value, (duckdb.Error, httpx.HTTPError))


@pytest.mark.parametrize(
    "stage",
    ["revision_503", "file_404", "not_parquet", "closed_port", "httpfs_missing"],
)
def test_every_hub_leg_is_could_not_ask(
    stage: str, httpfs, loopback_hub, clinvar_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = SNAPSHOT_REPO_IDS["clinvar"]
    base = loopback_hub.base_url
    if stage == "revision_503":
        loopback_hub.publish(repo, clinvar_root, COMMIT_A)
        loopback_hub.fail["/revision/"] = 503
    elif stage == "file_404":
        loopback_hub.publish(repo, clinvar_root, COMMIT_A)
        loopback_hub.fail["clinvar-chr1.parquet"] = 404
    elif stage == "not_parquet":
        broken = tmp_path / "broken"
        (broken / "data").mkdir(parents=True)
        (broken / "data" / "clinvar-chr1.parquet").write_text("<html>maintenance</html>")
        loopback_hub.publish(repo, broken, COMMIT_A)
    elif stage == "closed_port":
        base = "http://127.0.0.1:9"
    else:
        real = duckdb.connect
        monkeypatch.setattr(
            remote.duckdb, "connect", lambda *a, **k: real(*a, config={"extension_directory": str(tmp_path)})
        )
        loopback_hub.publish(repo, clinvar_root, COMMIT_A)
    with RemoteSnapshots(hf_base_url=base) as holder, pytest.raises(SnapshotRouteUnavailable) as failed:
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert failed.value.route == "hf" and failed.value.lane == "clinvar"
    if stage == "httpfs_missing":
        assert "httpfs extension is not installed here" in str(failed.value)


def test_an_unknown_table_or_column_is_a_wrong_request(httpfs, loopback_hub, clinvar_root: Path) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        with pytest.raises(ValueError, match="has no table 'variants'"):
            holder.lookup("clinvar", "variants", {"rsid": ["rs334"]})
        with pytest.raises(ValueError, match="has no column symbol"):
            holder.lookup("clinvar", "clinvar", {"symbol": ["HBB"]})
        with pytest.raises(ValueError, match="not a key column: clin_sig"):
            holder.lookup("clinvar", "clinvar", {"clin_sig": ["pathogenic"]})
        with pytest.raises(ValueError, match="chrom and start together"):
            holder.lookup("clinvar", "clinvar", {"chrom": ["11"]})
        with pytest.raises(ValueError, match="is not read remotely"):
            holder.lookup("mitomap", "mitomap", {"gene": ["MT-ND1"]})


def test_a_closed_holder_refuses(loopback_hub) -> None:
    holder = RemoteSnapshots(hf_base_url=loopback_hub.base_url)
    holder.close()
    with pytest.raises(ValueError, match="closed"):
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})


# ── the proxy ───────────────────────────────────────────────────────────────────────────────


def test_proxy_and_hf_answer_the_same_rows_for_the_same_keys(
    httpfs, loopback_hub, clinvar_root: Path, ensembl_root: Path
) -> None:
    """Two independent readers of one snapshot, polars on the proxy and duckdb on the Hub, agree."""
    _published(loopback_hub, clinvar_root, ensembl_root)
    proxy = _Proxy({"clinvar": clinvar_root, "ensembl": ensembl_root})
    asked = [
        ("clinvar", "clinvar", {"rsid": ["rs334", "rs761341010"]}),
        ("clinvar", "clinvar", {"chrom": ["1", "11"], "start": [943234, 5227002]}),
        ("ensembl", "homo_sapiens", {"chrom": ["11", "X"], "start": [5226773, 634689]}),
    ]
    with _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), proxy) as by_proxy:
        proxied = [by_proxy.lookup(*a) for a in asked]
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as by_hub:
        hubbed = [by_hub.lookup(*a) for a in asked]
    for via_proxy, via_hub in zip(proxied, hubbed, strict=True):
        assert via_proxy.rows and via_proxy.rows == via_hub.rows
        assert (via_proxy.route, via_proxy.served_from, via_proxy.release) == ("proxy", "local", None)
    # Paired positions: 1:943234 and 11:5227002 only, never the cross product's 1:5227002.
    assert {(r["chrom"], r["start"]) for r in proxied[1].rows} == {("1", 943234), ("11", 5227002)}


def test_a_proxy_reply_that_states_its_release_carries_it(clinvar_root: Path) -> None:
    proxy = _Proxy({"clinvar": clinvar_root}, release="clinvar_2026-11-01")
    with _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), proxy) as holder:
        answer = holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert (answer.route, answer.release, answer.revision) == ("proxy", "clinvar_2026-11-01", None)


def test_a_lookup_is_cut_to_the_proxys_key_limit_one_chromosome_per_request(clinvar_root: Path) -> None:
    proxy = _Proxy({"clinvar": clinvar_root})
    starts = list(range(1_000_000, 1_000_250))
    with _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), proxy) as holder:
        holder.lookup("clinvar", "clinvar", {"chrom": ["1", "11"], "start": [943234, 5227002]})
        holder.lookup("clinvar", "clinvar", {"chrom": ["1"], "start": starts})
        holder.lookup("clinvar", "clinvar", {"rsid": [f"rs{i}" for i in range(1, 151)]})
    assert [keys["chrom"] for _lane, keys in proxy.asked[:2]] == [["1"], ["11"]]
    position_batches = [keys["start"] for _lane, keys in proxy.asked[2:5]]
    assert [len(b) for b in position_batches] == [99, 99, 52]
    assert [x for b in position_batches for x in b] == starts
    rsid_batches = [keys["rsid"] for _lane, keys in proxy.asked[5:]]
    assert [len(b) for b in rsid_batches] == [100, 50]


def test_a_truncated_reply_is_halved_until_it_fits(clinvar_root: Path) -> None:
    rsids = ["rs334", "rs368250686", "rs1291411884", "rs761341010"]
    whole = _registry_rows(clinvar_root, {"rsid": rsids})
    most_for_one = max(len(_registry_rows(clinvar_root, {"rsid": [r]})) for r in rsids)
    proxy = _Proxy({"clinvar": clinvar_root}, max_rows=most_for_one)
    assert len(whole) > most_for_one  # the first request really is truncated
    with _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), proxy) as holder:
        answer = holder.lookup("clinvar", "clinvar", {"rsid": rsids})
    assert answer.rows == remote._stable(whole)
    assert len(proxy.asked) > 1


def test_one_key_still_truncated_is_could_not_ask_never_absent(clinvar_root: Path) -> None:
    rows = _registry_rows(clinvar_root, {"rsid": ["rs334"]})
    assert len(rows) > 1
    proxy = _Proxy({"clinvar": clinvar_root}, max_rows=1)
    holder = _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), proxy)
    with holder, pytest.raises(SnapshotRouteUnavailable) as failed:
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert failed.value.route == "proxy"
    assert "truncated its answer for one key (rsid='rs334')" in str(failed.value)
    assert "unchecked, not absent" in str(failed.value)


def _staged(status: int, error: str | None = None) -> Callable[[httpx.Request], httpx.Response]:
    body = {"detail": {"error": error, "errors": ["staged by the test"]}} if error else {"detail": "staged"}
    return lambda request: httpx.Response(
        status, json=body, headers={"Retry-After": "30"} if status == 429 else {}
    )


def _transport_failure(kind: type[httpx.TransportError]) -> Callable[[httpx.Request], httpx.Response]:
    def fail(request: httpx.Request) -> httpx.Response:
        raise kind("staged by the test", request=request)

    return fail


FALL_THROUGH = {
    "429": _staged(429),
    "503": _staged(503),
    "504": _staged(504),
    "404 lane_not_available": _staged(404, "lane_not_available"),
    "timeout": _transport_failure(httpx.ReadTimeout),
    "connect": _transport_failure(httpx.ConnectError),
}


@pytest.mark.parametrize("stage", sorted(FALL_THROUGH))
def test_the_proxy_falls_through_to_hf_exactly_on_the_registrys_list(
    stage: str, httpfs, loopback_hub, clinvar_root: Path
) -> None:
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    with _with_proxy(
        RemoteSnapshots(proxy_url=PROXY, hf_base_url=loopback_hub.base_url), FALL_THROUGH[stage]
    ) as holder:
        answer = holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert answer.route == "hf" and answer.revision == COMMIT_A
    assert answer.rows == remote._stable(_registry_rows(clinvar_root, {"rsid": ["rs334"]}))


@pytest.mark.parametrize("stage", sorted(FALL_THROUGH))
def test_with_hf_off_a_fall_through_is_could_not_ask_on_the_proxy(stage: str) -> None:
    holder = _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), FALL_THROUGH[stage])
    with holder, pytest.raises(SnapshotRouteUnavailable) as failed:
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert failed.value.route == "proxy" and "Hugging Face is off" in str(failed.value)


@pytest.mark.parametrize(
    "status,error", [(422, "unknown_key"), (422, "remote_needs_position"), (404, "unknown_table")]
)
def test_a_wrong_request_raises_and_hf_is_not_asked(status: int, error: str, loopback_hub) -> None:
    with (
        _with_proxy(
            RemoteSnapshots(proxy_url=PROXY, hf_base_url=loopback_hub.base_url), _staged(status, error)
        ) as holder,
        pytest.raises(ValueError) as refused,
    ):
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert f"({status} {error})" in str(refused.value)
    assert loopback_hub.requests == []


@pytest.mark.parametrize("status", [500, 502, 410, 401])
def test_a_status_off_the_list_is_could_not_ask_on_the_proxy_without_falling_through(
    status: int, loopback_hub
) -> None:
    with (
        _with_proxy(
            RemoteSnapshots(proxy_url=PROXY, hf_base_url=loopback_hub.base_url), _staged(status)
        ) as holder,
        pytest.raises(SnapshotRouteUnavailable) as failed,
    ):
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert failed.value.route == "proxy" and f"HTTP {status}" in str(failed.value)
    assert loopback_hub.requests == []
    assert could_not_ask_reason(failed.value) == ("retired" if status == 410 else "unreachable")


def test_no_route_configured_is_could_not_ask_and_asks_nothing() -> None:
    with RemoteSnapshots(huggingface=False) as holder, pytest.raises(SnapshotRouteUnavailable) as failed:
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert failed.value.route is None
    assert (
        str(failed.value)
        == "clinvar: no remote route was asked: no proxy is configured and Hugging Face is off"
    )


def test_the_proxy_is_read_from_the_environment_only_when_not_given(monkeypatch: pytest.MonkeyPatch) -> None:
    assert RemoteSnapshots().proxy_url is None
    monkeypatch.setenv(remote.PROXY_URL_VAR, "http://127.0.0.1:8")
    with RemoteSnapshots() as from_env, RemoteSnapshots(proxy_url="http://127.0.0.1:7") as given:
        assert (from_env.proxy_url, given.proxy_url) == ("http://127.0.0.1:8", "http://127.0.0.1:7")


def test_a_proxy_token_is_sent_as_a_bearer_and_a_hub_token_never_leaves_for_another_host(
    monkeypatch: pytest.MonkeyPatch, clinvar_root: Path, loopback_hub
) -> None:
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    seen: list[str | None] = []

    def proxy(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return _Proxy({"clinvar": clinvar_root})(request)

    holder = RemoteSnapshots(proxy_url=PROXY, proxy_token="p-token", hf_base_url=loopback_hub.base_url)
    holder._proxy.close()
    holder._proxy = httpx.Client(transport=httpx.MockTransport(proxy), headers=holder._proxy.headers)
    with holder:
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
        assert holder._hf_token is None and "Authorization" not in holder._hub.headers
    assert seen == ["Bearer p-token"]
    with RemoteSnapshots() as default_hub:
        assert default_hub._hf_token == "hf_secret"


# ── the licence gate ───────────────────────────────────────────────────────────────────────────


def test_a_gated_lane_is_skipped_under_an_unstated_use_and_nothing_is_asked(loopback_hub) -> None:
    asked: list[httpx.Request] = []
    with (
        _with_proxy(
            RemoteSnapshots(proxy_url=PROXY, hf_base_url=loopback_hub.base_url),
            lambda request: asked.append(request) or httpx.Response(200, json={"rows": []}),
        ) as holder,
        pytest.raises(SnapshotRouteUnavailable) as skipped,
    ):
        holder.lookup("clinpgx", "annotations", {"rsid": ["rs4244285"]})
    assert skipped.value.route is None and "forbids sale and no use was declared" in skipped.value.cause
    assert asked == [] and loopback_hub.requests == []


def test_a_commercial_use_against_a_no_sale_lane_is_refused(loopback_hub) -> None:
    holder = RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="commercial")
    with holder, pytest.raises(LicenseRefusal):
        holder.lookup("cpic", "genes", {"gene": ["CYP2C19"]})
    assert loopback_hub.requests == []


def test_a_declared_non_commercial_use_reads_a_gated_lane(httpfs, loopback_hub, tmp_path: Path) -> None:
    root = tmp_path / "cpic"
    (root / "data").mkdir(parents=True)
    pl.DataFrame({"gene": ["CYP2C19", "CYP2D6"], "chrom": ["10", "22"]}).write_parquet(
        root / "data" / "genes.parquet"
    )
    loopback_hub.publish(SNAPSHOT_REPO_IDS["cpic"], root, COMMIT_A)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url, declared_use="non_commercial") as holder:
        answer = holder.lookup("cpic", "genes", {"gene": ["CYP2C19"]})
    assert answer.rows == [{"gene": "CYP2C19", "chrom": "10"}] and answer.release is None


def test_a_lane_whose_registry_entry_states_no_terms_is_not_gated() -> None:
    """The rebuild gate's reading of `terms=None`, so ClinVar reads under an unstated use."""
    assert LANES_BY_NAME["clinvar"].terms is None
    with RemoteSnapshots(huggingface=False) as holder, pytest.raises(SnapshotRouteUnavailable) as failed:
        holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]})
    assert "Hugging Face is off" in str(failed.value)  # past the gate: it was the routes that were missing
