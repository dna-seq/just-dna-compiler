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

import duckdb
import pytest
from just_dna_enricher import download as dl
from just_dna_enricher.locations import CITATIONS_DIRNAME, RELEASE_FILENAME


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
    """Minimal `HfFileSystem` over a repo *tree*: `{dirname: {filename: column}}`.

    Modelling directories rather than one flat listing is what lets the sidecar (`citations/`) be tested
    at all — and listing or fetching a path the repo does not have **raises**, as the real one does,
    which is what makes "an older repo has no `citations/` and no `release.json`" a real case here.
    """

    def __init__(self, tree: dict[str, dict[str, str]], release: str | None = None) -> None:
        self.tree = tree                     # dirname -> {filename: column name (its schema)}
        self.release = release               # the repo-root release.json body, or None
        self.fetched: list[str] = []

    def ls(self, prefix: str, detail: bool = True):
        dirname = prefix.rstrip("/").rsplit("/", 1)[-1]
        if dirname not in self.tree:
            raise FileNotFoundError(prefix)
        return [f"{prefix}/{name}" for name in self.tree[dirname]]

    def get(self, remote_path: str, local_path: str) -> None:
        parts = remote_path.rstrip("/").split("/")
        name = parts[-1]
        if name == RELEASE_FILENAME:
            if self.release is None:
                raise FileNotFoundError(remote_path)
            self.fetched.append(name)
            Path(local_path).write_text(self.release, encoding="utf-8")
            return
        dirname = parts[-2]
        if name not in self.tree.get(dirname, {}):
            raise FileNotFoundError(remote_path)
        self.fetched.append(f"{dirname}/{name}")
        _write_parquet(Path(local_path), self.tree[dirname][name])


@pytest.fixture
def fake_hub(monkeypatch, tmp_path: Path):
    """Install a fake `HfFileSystem`/`get_token` and hand the test the instance."""
    import huggingface_hub

    holder: dict[str, _FakeFS] = {}

    def factory(
        data: dict[str, str],
        release: str | None = None,
        citations: dict[str, str] | None = None,
    ) -> _FakeFS:
        tree = {"data": data}
        if citations is not None:
            tree[CITATIONS_DIRNAME] = citations
        fs = _FakeFS(tree, release)
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
        "data/clinvar-chr1.parquet", "data/clinvar-chr2.parquet",
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
        assert [f for f in fs.fetched if f.endswith(".parquet")] == [f"data/{expected}"]


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
    assert [f for f in fs.fetched if f.endswith(".parquet")] == ["data/clinvar-chr1.parquet"]
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


# ── the sidecar: ClinVar's citations table ──────────────────────────────────────────────────────


def test_citations_are_provisioned_into_their_own_directory(fake_hub, tmp_path: Path) -> None:
    """The gap this closes: `citations/` was built and published-nowhere, so anyone who *downloaded* the
    snapshot had no PMIDs — and `draft-panel` cannot produce a compilable module without them, because
    `studies.csv` is mandatory.

    It must land in `citations/`, never in `data/`: the readers glob `data/*.parquet`, so a two-column
    citations table there is the same poisoning that the stale `clinvar.parquet` causes.
    """
    fs = fake_hub(
        {"clinvar-chr1.parquet": "clin_sig"},
        citations={"citations.parquet": "variation_id"},
    )
    cache = tmp_path / "cv"
    dl.ensure_clinvar_snapshot(cache)

    assert "citations/citations.parquet" in fs.fetched
    assert (cache / CITATIONS_DIRNAME / "citations.parquet").is_file()
    assert not (cache / "data" / "citations.parquet").exists()
    # The records view still binds — one schema under the glob, which is the invariant at stake.
    con = duckdb.connect(":memory:")
    try:
        assert con.sql(f"SELECT * FROM read_parquet('{cache}/data/*.parquet')").columns == ["clin_sig"]
    finally:
        con.close()


def test_a_repo_without_citations_still_provisions(fake_hub, tmp_path: Path) -> None:
    """Ensembl and constraint have no sidecar, and a ClinVar snapshot built without running
    `clinvar citations` has none either. Absence is normal, not an error — `citations_for` already
    reads it as "no citations available" rather than "no literature exists"."""
    fake_hub({"clinvar-chr1.parquet": "clin_sig"})          # no citations dir
    cache = tmp_path / "cv"
    dl.ensure_clinvar_snapshot(cache)
    assert (cache / "data" / "clinvar-chr1.parquet").is_file()
    assert not (cache / CITATIONS_DIRNAME).exists()


def test_a_present_citations_file_is_not_refetched(fake_hub, tmp_path: Path) -> None:
    """Same footer-checked skip the data files get: re-provisioning costs nothing."""
    fs = fake_hub(
        {"clinvar-chr1.parquet": "clin_sig"},
        citations={"citations.parquet": "variation_id"},
    )
    cache = tmp_path / "cv"
    _write_parquet(cache / CITATIONS_DIRNAME / "citations.parquet", "variation_id")
    dl.ensure_clinvar_snapshot(cache)                        # data/ is empty, so it does provision
    assert "citations/citations.parquet" not in fs.fetched
