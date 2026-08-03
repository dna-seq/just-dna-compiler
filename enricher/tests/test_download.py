"""Snapshot provisioning from HuggingFace — the bulk-fetch side, with no socket opened.

`HfFileSystem` is imported inside `_provision_snapshot` (the one guarded optional import), so a fake
filesystem substituted on the `huggingface_hub` module covers the whole path. The fake writes *real*
parquet bytes, because the provisioner's footer check is the thing that catches a truncated download and
a stub of zeros would pass through untested.

The case these tests exist for is real and live: `just-dna-seq/clinvar/data` carries a 159 MB
`clinvar.parquet` from the single-file era beside today's 25 `clinvar-chr*.parquet`, and the two have
different schemas.
"""

from pathlib import Path
from typing import Optional

import duckdb
import pytest

from just_dna_enricher import download as dl


def _write_parquet(path: Path, column: str) -> None:
    """A one-row parquet with a named column, so a schema difference is observable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        target = str(path).replace("'", "''")
        con.execute(f"COPY (SELECT 1 AS {column}) TO '{target}' (FORMAT PARQUET)")
    finally:
        con.close()


class _FakeFS:
    """Minimal `HfFileSystem`: lists a fixed set of remote names and 'downloads' real parquet.

    `ls` lists the `data/` prefix only, and asking for a file the repo does not have **raises** — both
    of which mirror the real thing, and the second is what makes the optional `release.json` fetch
    testable at all (an older repo simply has none).
    """

    def __init__(self, remote: dict[str, str], release: Optional[str] = None) -> None:
        self.remote = remote                 # filename -> column name (its schema)
        self.release = release               # the repo-root release.json body, or None
        self.fetched: list[str] = []

    def ls(self, prefix: str, detail: bool = True):
        return [f"{prefix}/{name}" for name in self.remote]

    def get(self, remote_path: str, local_path: str) -> None:
        name = remote_path.rsplit("/", 1)[-1]
        if name == "release.json":
            if self.release is None:
                raise FileNotFoundError(remote_path)
            self.fetched.append(name)
            Path(local_path).write_text(self.release, encoding="utf-8")
            return
        if name not in self.remote:
            raise FileNotFoundError(remote_path)
        self.fetched.append(name)
        _write_parquet(Path(local_path), self.remote[name])


@pytest.fixture
def fake_hub(monkeypatch, tmp_path: Path):
    """Install a fake `HfFileSystem`/`get_token` and hand the test the instance."""
    import huggingface_hub

    holder: dict[str, _FakeFS] = {}

    def factory(remote: dict[str, str], release: Optional[str] = None) -> _FakeFS:
        fs = _FakeFS(remote, release)
        holder["fs"] = fs
        monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
        monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
        return fs

    return factory


# ── the live problem: a published snapshot keeps files from every earlier layout ────────────────


def test_a_stale_remote_file_is_not_downloaded(fake_hub, tmp_path: Path) -> None:
    """`clinvar.parquet` (single-file era, raw VCF INFO columns) must not join `clinvar-chr*.parquet`.

    The reader globs `data/*.parquet`, so importing it would put two schemas under one DuckDB relation
    and every query would fail on `Referenced column "clin_sig" not found` — which is exactly how a
    locally-built old snapshot broke the clin_sig cross-check.
    """
    fs = fake_hub({
        "clinvar-chr1.parquet": "clin_sig",
        "clinvar-chr2.parquet": "clin_sig",
        "clinvar.parquet": "clnsig",          # the stale one, still in the published repo
    })
    cache = tmp_path / "cv"
    dl.ensure_clinvar_snapshot(cache)

    assert sorted(f for f in fs.fetched if f.endswith(".parquet")) == [
        "clinvar-chr1.parquet", "clinvar-chr2.parquet",
    ]
    assert not (cache / "data" / "clinvar.parquet").exists()
    # …and the cache is queryable as one relation, which is the property that actually matters.
    con = duckdb.connect(":memory:")
    try:
        columns = con.sql(f"SELECT * FROM read_parquet('{cache}/data/*.parquet')").columns
    finally:
        con.close()
    assert columns == ["clin_sig"]


def test_the_old_unfiltered_behaviour_broke_the_cache(fake_hub, tmp_path: Path) -> None:
    """Demonstrated rather than asserted: fetching every remote parquet is what poisoned the glob."""
    fake_hub({"clinvar-chr1.parquet": "clin_sig", "clinvar.parquet": "clnsig"})
    cache = tmp_path / "unfiltered"
    dl._provision_snapshot(
        cache, "datasets/x/data", label="ClinVar", error_cls=dl.ClinVarReferenceError,
        filename_glob="*.parquet",                      # what the code used to do implicitly
    )
    con = duckdb.connect(":memory:")
    try:
        with pytest.raises(duckdb.Error, match="clin_sig"):
            con.sql(f"SELECT clin_sig FROM read_parquet('{cache}/data/*.parquet')").fetchall()
    finally:
        con.close()


def test_a_repo_with_none_of_this_snapshots_files_is_a_clear_error(fake_hub, tmp_path: Path) -> None:
    """Better than "downloaded 0 files, cache empty": say what was there and what was wanted."""
    fake_hub({"clinvar.parquet": "clnsig"})
    with pytest.raises(dl.ClinVarReferenceError, match=r"no clinvar-\*\.parquet"):
        dl.ensure_clinvar_snapshot(tmp_path / "empty")


def test_each_snapshot_asks_for_its_own_files(fake_hub, tmp_path: Path) -> None:
    """One download body, three snapshots — the glob is the only thing that separates them."""
    remote = {
        "homo_sapiens-chr1.parquet": "rsid",
        "clinvar-chr1.parquet": "clin_sig",
        "gnomad_constraint.parquet": "gene",
    }
    for ensure, expected in (
        (dl.ensure_snapshot, "homo_sapiens-chr1.parquet"),
        (dl.ensure_clinvar_snapshot, "clinvar-chr1.parquet"),
        (dl.ensure_constraint_snapshot, "gnomad_constraint.parquet"),
    ):
        fs = fake_hub(remote)
        ensure(tmp_path / expected)          # a distinct cache dir per snapshot
        assert [f for f in fs.fetched if f.endswith(".parquet")] == [expected]


# ── the cache side ─────────────────────────────────────────────────────────────────────────────


def test_a_populated_cache_is_trusted_without_touching_the_network(fake_hub, tmp_path: Path) -> None:
    fs = fake_hub({"clinvar-chr1.parquet": "clin_sig"})
    cache = tmp_path / "cv"
    _write_parquet(cache / "data" / "clinvar-chr1.parquet", "clin_sig")
    dl.ensure_clinvar_snapshot(cache)
    assert fs.fetched == []


def test_a_foreign_file_already_in_the_cache_is_reported_not_deleted(
    fake_hub, tmp_path: Path, caplog
) -> None:
    """Report, never repair: a file we did not put there is not ours to delete — but it will break the
    reader, so the warning names it and says what to do."""
    fake_hub({"clinvar-chr1.parquet": "clin_sig"})
    cache = tmp_path / "cv"
    _write_parquet(cache / "data" / "clinvar-chr1.parquet", "clin_sig")
    _write_parquet(cache / "data" / "clinvar.parquet", "clnsig")
    with caplog.at_level("WARNING"):
        dl.ensure_clinvar_snapshot(cache)
    assert (cache / "data" / "clinvar.parquet").exists()
    message = "\n".join(r.getMessage() for r in caplog.records)
    assert "clinvar.parquet" in message and "not part of this snapshot" in message


def test_a_truncated_file_is_removed_and_refetched(fake_hub, tmp_path: Path) -> None:
    """The footer check, which is why the fake writes real parquet."""
    fs = fake_hub({"clinvar-chr1.parquet": "clin_sig"})
    cache = tmp_path / "cv"
    (cache / "data").mkdir(parents=True)
    (cache / "data" / "clinvar-chr1.parquet").write_bytes(b"PAR1truncated")
    dl.ensure_clinvar_snapshot(cache)
    assert [f for f in fs.fetched if f.endswith(".parquet")] == ["clinvar-chr1.parquet"]
    assert dl._parquet_footer_ok(cache / "data" / "clinvar-chr1.parquet")


# ── the provenance file ────────────────────────────────────────────────────────────────────────


def test_release_json_is_provisioned_with_the_data(fake_hub, tmp_path: Path) -> None:
    """A *built* snapshot could say which release it was; a *provisioned* one could not, because the
    publisher uploaded `release.json` and this only ever fetched parquet.

    It is what `GenePanelSpec.reference_sha256` pins against (RM4) — a cache that cannot state its
    `source_sha256` is a cache rather than a pinnable reference.
    """
    body = '{"clinvar_file_date": "2026-06-27", "source_sha256": "20f5fbae"}\n'
    fake_hub({"clinvar-chr1.parquet": "clin_sig"}, release=body)
    cache = tmp_path / "cv"
    dl.ensure_clinvar_snapshot(cache)
    assert (cache / "release.json").read_text() == body


def test_a_repo_without_release_json_still_provisions(fake_hub, tmp_path: Path) -> None:
    """Absence is not an error: a repo published before the builder wrote one is still usable."""
    fake_hub({"clinvar-chr1.parquet": "clin_sig"})     # no release
    cache = tmp_path / "cv"
    dl.ensure_clinvar_snapshot(cache)
    assert (cache / "data" / "clinvar-chr1.parquet").is_file()
    assert not (cache / "release.json").exists()
