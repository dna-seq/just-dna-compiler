"""`RemoteSnapshots`: the registry's proxy, then Hugging Face, for a box with no local snapshot (RM430).

Hugging Face is a `LoopbackHub` (the enricher conftest): the Hub's revision API and `resolve` route with
HTTP range requests on 127.0.0.1, serving real snapshot bytes: ClinVar built by the real builder from
`assets/clinvar_GRCh38_slice.vcf.gz`, and Ensembl's split release from the RM381 slice of published rows,
laid out one file per chromosome under a `manifest.json` as the published repo is. The proxy is an
`httpx.MockTransport` answering with the registry's semantics over the same files, read with polars as
the registry reads them, so the two routes are two independent readers of one snapshot.
"""

import ast
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
from just_dna_enricher import clinvar, remote, resolver
from just_dna_enricher import lookup as lookup_module
from just_dna_enricher.caches import CACHE_LANES, LANES_BY_NAME
from just_dna_enricher.clients import LookupClients
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS
from just_dna_enricher.lookup import lookup_variant
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
    assert set(REMOTE_LANES) == {
        "ensembl",
        "clinvar",
        "constraint",
        "clinpgx",
        "cpic",
        "drug_labels",
        "opentargets",
    }
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


def test_an_attested_chromosome_file_answers_only_for_its_chromosome(
    httpfs, loopback_hub, ensembl_root: Path, tmp_path: Path
) -> None:
    """The scan of an attested file filters by position alone; the chromosome is checked on the rows."""
    root = tmp_path / "mislabelled"
    (root / "data").mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM read_parquet('{ensembl_root}/data/*.parquet')) "
        f"TO '{root / 'data' / 'homo_sapiens-chr16.parquet'}' (FORMAT parquet)"
    )
    con.close()
    manifest = {
        "release_id": ENSEMBL_RELEASE,
        "files": [{"path": "data/homo_sapiens-chr16.parquet", "chrom": "16"}],
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    loopback_hub.publish(SNAPSHOT_REPO_IDS["ensembl"], root, COMMIT_A)
    in_the_file = _registry_rows(root, {"start": [5226773]})
    assert {row["chrom"] for row in in_the_file} == {"11"}  # the file holds a row of another chromosome there
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup("ensembl", "homo_sapiens", {"chrom": ["16"], "start": [5226773]})
    assert answer.rows == []


def test_a_chromosome_the_manifest_attests_no_file_for_reads_the_whole_table(
    httpfs, loopback_hub, ensembl_root: Path, tmp_path: Path
) -> None:
    """Never an empty answer for a table nobody read: an unattested contig falls back to every file."""
    root = tmp_path / "partial"
    (root / "data").mkdir(parents=True)
    for parquet in (ensembl_root / "data").glob("*.parquet"):
        (root / "data" / parquet.name).write_bytes(parquet.read_bytes())
    manifest = json.loads((ensembl_root / "manifest.json").read_text())
    manifest["files"] = [f for f in manifest["files"] if f["chrom"] != "X"]
    (root / "manifest.json").write_text(json.dumps(manifest))
    loopback_hub.publish(SNAPSHOT_REPO_IDS["ensembl"], root, COMMIT_A)
    expected = _registry_rows(ensembl_root, {"chrom": ["X"], "start": [634689]})
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup("ensembl", "homo_sapiens", {"chrom": ["chrX"], "start": [634689]})
    assert answer.rows and answer.rows == remote._stable(expected)


def test_a_chromosome_is_grouped_as_normalize_chrom_spells_it() -> None:
    assert remote._chrom_forms("chrM") == ("MT", "chrMT", "M", "chrM")
    assert remote._chrom_forms("x") == ("X", "chrX")
    keys = remote._read_keys(REMOTE_LANES["clinvar"], {"chrom": ["chr1", "1", "M"], "start": [5, 5, 7]})
    assert keys.positions == {"1": [5], "MT": [7]}


def test_a_position_prunes_row_groups_rather_than_reading_the_chromosome(
    httpfs, loopback_hub, tmp_path: Path
) -> None:
    """One position reads the footer and the row group holding it, however many row groups the file has.

    Bound integer parameters prune nothing in duckdb (measured: the whole chr19 file, 65 MB, for one
    position), so the holder renders positions as literals; this file has many row groups.
    """
    root = tmp_path / "many"
    (root / "data").mkdir(parents=True)
    target = root / "data" / "homo_sapiens-chr16.parquet"
    con = duckdb.connect()
    con.execute(
        "COPY (SELECT '16' AS chrom, (range * 10 + 1)::UINTEGER AS start, 'A' AS ref, 'G' AS alt, "
        "'rs' || range AS id FROM range(40000)) "
        f"TO '{target}' (FORMAT parquet, ROW_GROUP_SIZE 1000)"
    )
    groups = con.execute(f"SELECT count(DISTINCT row_group_id) FROM parquet_metadata('{target}')").fetchone()[
        0
    ]
    con.close()
    manifest = {"release_id": ENSEMBL_RELEASE, "files": [{"path": f"data/{target.name}", "chrom": "16"}]}
    (root / "manifest.json").write_text(json.dumps(manifest))
    loopback_hub.publish(SNAPSHOT_REPO_IDS["ensembl"], root, COMMIT_A)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        answer = holder.lookup("ensembl", "homo_sapiens", {"chrom": ["16"], "start": [123451]})
    assert [row["id"] for row in answer.rows] == ["rs12345"]
    ranged = [r for m, p, r in loopback_hub.requests if m == "GET" and r and p.endswith(".parquet")]
    assert groups >= 10 and len(ranged) <= 4, (groups, ranged)


def test_a_hub_token_reaches_the_hub_and_nowhere_else(
    httpfs, loopback_hub, clinvar_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sent on the API reads and on duckdb's file reads alike, when the Hub is the one the token is for."""
    monkeypatch.setenv("HF_TOKEN", "hf_loopback_token")
    monkeypatch.setattr(remote, "HF_BASE_URL", loopback_hub.base_url)
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], clinvar_root, COMMIT_A)
    with RemoteSnapshots() as holder:
        assert holder.lookup("clinvar", "clinvar", {"rsid": ["rs334"]}).rows
    assert loopback_hub.authorization and set(loopback_hub.authorization) == {"Bearer hf_loopback_token"}


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
        assert loopback_hub.requests == []  # the extension is checked before any Hub quota is spent


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


# ── `lookup_variant` with a holder ─────────────────────────────────────────────────────────────


class _Eutils:
    """dbSNP that knows nothing: the currency leg runs and asks no network."""

    def esummary(self, db: str, ids: list[str]) -> dict:
        return {}

    def close(self) -> None:
        pass


class _Ensembl:
    """Live Ensembl REST, recording what it was asked, answering nothing."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        self.asked.append(rsid)
        return [], "ensembl-rest"

    def close(self) -> None:
        pass


def _ask(tmp_path: Path, holder: RemoteSnapshots | None, **question: Any):
    """`lookup_variant` on a box with no local snapshot, live legs stubbed, `holder` as `snapshots`."""
    nowhere = tmp_path / "no-snapshot-here"
    ensembl = _Ensembl()
    clients = LookupClients(eutils=_Eutils(), ensembl=ensembl, snapshots=holder)
    hint = lookup_variant(ensembl_cache=nowhere, clinvar_cache=nowhere, clients=clients, **question)
    return hint, ensembl


def test_without_a_holder_nothing_is_read_remotely(no_ambient_caches, loopback_hub, tmp_path: Path) -> None:
    hint, _ensembl = _ask(tmp_path, None, rsid="rs334", chrom="11", start=5227002)
    assert hint.routes is None and loopback_hub.requests == []
    assert LookupClients().snapshots is None


def test_offline_with_a_holder_reads_nothing_remotely(
    no_ambient_caches, loopback_hub, tmp_path: Path
) -> None:
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        hint = lookup_variant(
            rsid="rs334",
            chrom="11",
            start=5227002,
            offline=True,
            ensembl_cache=tmp_path / "none",
            clinvar_cache=tmp_path / "none",
            clients=LookupClients(snapshots=holder),
        )
    assert hint.routes is None and loopback_hub.requests == []


def test_a_position_is_answered_from_hf_as_the_local_snapshots_answer_it(
    httpfs, no_ambient_caches, loopback_hub, clinvar_root: Path, ensembl_root: Path, tmp_path: Path
) -> None:
    """Same rows, same reader SQL: the remote answer is the local reader's answer, and says its route."""
    _published(loopback_hub, clinvar_root, ensembl_root)
    position = ("16", 23635706, None, None)
    local = resolver.lookup_loci(ensembl_root, [], [position])[1]
    assert local[position]  # the slice holds rsIDs there, so an empty answer cannot pass
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        hint, _ensembl = _ask(tmp_path, holder, chrom="16", start=23635706)
    assert hint.rsid_candidates == local[position]
    assert hint.routes["ensembl"] == RemoteRoute("hf", ENSEMBL_RELEASE, None, COMMIT_A)
    assert "ensembl" in hint.checked and "ensembl" not in hint.snapshots


def test_an_rsid_is_answered_by_clinvar_remotely_with_its_clinical_calls_and_live_ensembl_is_not_asked(
    httpfs, no_ambient_caches, loopback_hub, clinvar_root: Path, ensembl_root: Path, tmp_path: Path
) -> None:
    _published(loopback_hub, clinvar_root, ensembl_root)
    local_loci = clinvar.lookup_loci(clinvar_root, ["rs334"], [])[0]["rs334"]
    alleles = [
        (lo["chrom"], int(lo["start"]), lo["ref"], a) for lo in local_loci for a in lo["alts"].split(",")
    ]
    local_calls = [
        record for records in clinvar.lookup_clin_sig(clinvar_root, alleles).values() for record in records
    ]
    assert local_loci and local_calls
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        hint, ensembl = _ask(tmp_path, holder, rsid="rs334")
    assert hint.loci == local_loci and hint.clin_sig == local_calls
    assert ensembl.asked == []  # the remote snapshot answered, so live REST was not needed
    release = json.loads((clinvar_root / "release.json").read_text())["dataset"]
    assert hint.routes == {"clinvar": RemoteRoute("hf", release, None, COMMIT_A)}
    messages = [f.message for f in hint.findings]
    assert (
        "ensembl: no local snapshot, and an rsID alone is never asked remotely (it needs chrom + start)"
        in messages
    )


def test_an_rsid_the_remote_snapshot_lacks_is_named_as_that_snapshots_miss(
    httpfs, no_ambient_caches, loopback_hub, clinvar_root: Path, ensembl_root: Path, tmp_path: Path
) -> None:
    _published(loopback_hub, clinvar_root, ensembl_root)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        hint, ensembl = _ask(tmp_path, holder, rsid="rs999999999")
    release = json.loads((clinvar_root / "release.json").read_text())["dataset"]
    assert f"rs999999999: not in the ClinVar snapshot read over hf (release {release})" in [
        f.message for f in hint.findings
    ]
    assert ensembl.asked == [
        "rs999999999"
    ]  # the remote miss falls through to live REST, as a local miss does


def test_the_proxy_answers_a_lookup_and_its_route_says_so(
    no_ambient_caches, clinvar_root: Path, ensembl_root: Path, tmp_path: Path
) -> None:
    proxy = _Proxy({"clinvar": clinvar_root, "ensembl": ensembl_root})
    with _with_proxy(RemoteSnapshots(proxy_url=PROXY, huggingface=False), proxy) as holder:
        hint, _ensembl = _ask(tmp_path, holder, rsid="rs334")
    assert hint.loci == clinvar.lookup_loci(clinvar_root, ["rs334"], [])[0]["rs334"]
    assert hint.routes == {"clinvar": RemoteRoute("proxy", None, "local", None)}


def test_two_routes_in_one_lookup_are_both_said(
    httpfs, no_ambient_caches, loopback_hub, clinvar_root: Path, ensembl_root: Path, tmp_path: Path
) -> None:
    """A 429 after the first request sends the rest of the lookup to Hugging Face: each answer keeps its route."""
    _published(loopback_hub, clinvar_root, ensembl_root)
    proxy = _Proxy({"clinvar": clinvar_root, "ensembl": ensembl_root})
    proxy.status = lambda request: _staged(429)(request) if len(proxy.asked) >= 1 else None
    with _with_proxy(RemoteSnapshots(proxy_url=PROXY, hf_base_url=loopback_hub.base_url), proxy) as holder:
        hint, _ensembl = _ask(tmp_path, holder, rsid="rs334")
    assert hint.routes["clinvar"].route == "proxy"
    said = [f.message for f in hint.findings if "answered over two routes" in f.message]
    assert said == [
        f"clinvar answered over two routes in one lookup: {hint.routes['clinvar']} and "
        f"{RemoteRoute('hf', json.loads((clinvar_root / 'release.json').read_text())['dataset'], None, COMMIT_A)}"
    ]


def test_a_remote_snapshot_that_could_not_be_asked_is_unchecked_never_empty(
    httpfs, no_ambient_caches, loopback_hub, clinvar_root: Path, ensembl_root: Path, tmp_path: Path
) -> None:
    _published(loopback_hub, clinvar_root, ensembl_root)
    loopback_hub.fail["/revision/"] = 503
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        hint, ensembl = _ask(tmp_path, holder, chrom="16", start=23635706)
    unchecked = [f for f in hint.findings if "could not be asked remotely" in f.message]
    assert {f.message.split(":", 1)[0] for f in unchecked} == {"ensembl", "clinvar"}
    assert all(f.level == "warning" and "unchecked rather than empty" in f.message for f in unchecked)
    assert hint.routes is None and hint.rsid_candidates == []


def test_a_request_a_route_refuses_is_unchecked_in_a_lookup_not_a_traceback(
    httpfs, no_ambient_caches, loopback_hub, tmp_path: Path
) -> None:
    """A repo whose payload no longer has the table the link asks for: a finding, as a local fault is."""
    root = tmp_path / "renamed"
    (root / "data").mkdir(parents=True)
    pl.DataFrame({"chrom": ["16"], "start": [1], "id": ["rs1"]}).write_parquet(
        root / "data" / "variants.parquet"
    )
    loopback_hub.publish(SNAPSHOT_REPO_IDS["ensembl"], root, COMMIT_A)
    loopback_hub.publish(SNAPSHOT_REPO_IDS["clinvar"], root, COMMIT_A)
    with RemoteSnapshots(hf_base_url=loopback_hub.base_url) as holder:
        hint, _ensembl = _ask(tmp_path, holder, chrom="16", start=23635706)
    refused = [f for f in hint.findings if "refused as wrong" in f.message]
    assert {f.message.split(":", 1)[0] for f in refused} == {"ensembl", "clinvar"}
    assert all(f.level == "warning" and "has no table" in f.message for f in refused)


#: The two `try` blocks in `lookup.py` that read a snapshot locally or remotely, by enclosing function.
_SNAPSHOT_READING_TRIES = {"_lookup_from_cache", "_lookup_clin_sig"}


def _handler_order_faults(source: str) -> tuple[set[str], list[str]]:
    """Every function holding a `try` that catches both types, and each one where `duckdb.Error` comes first."""
    seen: set[str] = set()
    faults: list[str] = []
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Try):
                continue
            names = [ast.unparse(handler.type) for handler in node.handlers if handler.type is not None]
            if "SnapshotRouteUnavailable" in names and "duckdb.Error" in names:
                seen.add(function.name)
                if names.index("duckdb.Error") < names.index("SnapshotRouteUnavailable"):
                    faults.append(function.name)
    return seen, faults


def test_lookup_catches_a_remote_route_before_a_duckdb_error() -> None:
    """`@client-exception-contract`: the could-not-ask arm sits first wherever both are caught."""
    seen, faults = _handler_order_faults(Path(lookup_module.__file__).read_text(encoding="utf-8"))
    assert seen == _SNAPSHOT_READING_TRIES and faults == []
    reversed_order = (
        "def _leg():\n    try:\n        pass\n    except duckdb.Error:\n        pass\n"
        "    except SnapshotRouteUnavailable:\n        pass\n"
    )
    assert _handler_order_faults(reversed_order) == ({"_leg"}, ["_leg"])


def test_nothing_in_the_package_builds_a_holder_lazily() -> None:
    """No leg fills `snapshots` through `ensure`: a holder built behind the caller's back is remote reads turned on."""
    package = Path(lookup_module.__file__).resolve().parent
    lazily = [
        f"{path.name}:{node.lineno}"
        for path in sorted(package.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "ensure"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "snapshots"
    ]
    assert lazily == []
