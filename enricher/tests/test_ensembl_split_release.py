"""The Ensembl snapshot moved to `just-dna-seq/ensembl_variations_split` (RM372).

prepare-annotations published dbSNP 157 / VEP 116 as a **separate** repo, with the same file names
as the old one (`data/homo_sapiens-chr*.parquet`), one row per ALT, and a `manifest.json` stating
the release id and every file's size and sha256 in place of a `release.json`. Three things follow,
and each test below pins one of them against the real provisioner and the real resolver:

- **A warm cache from the old repo is not this snapshot.** The names are identical, so a cache whose
  pull record names the old repo used to be returned untouched by a switched prefix, and a re-pull
  kept every file because each one was whole. A record naming another repo sends the cache down the
  pull route, and a kept file is one the manifest attests by sha256.
- **A cache mixing releases is withheld.** Old chrMT beside new chr21 answered rsIDs and nothing
  complained. With a manifest present, a `data/` file it does not attest withholds the whole
  directory: per-file exclusion would make the excluded chromosome's rsIDs read as asked-and-absent
  under `--offline`. Read time compares the manifest's `bytes` (a 14.5 GB hash per enrich is not a
  read); pull time compares the sha256.
- **The release has a label.** `cache status` and the `rsid_coordinate_agreement` record read the
  manifest's `release_id`, since the snapshot carries no `release.json`.

The fake hub serves real parquet bytes, and the manifest it serves is computed from those bytes, so
an attested file is attested by the same arithmetic the real one is.
"""

import dataclasses
import hashlib
import io
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import caches
from just_dna_enricher import download as dl
from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest
from just_dna_enricher.locations import (
    DUCKDB_NAME,
    PULL_RECORD_FILENAME,
    SNAPSHOT_MANIFEST_FILENAME,
    ManifestCoverage,
    ensembl_release_label,
    manifest_coverage,
    pull_record_repo,
    resolve_ensembl_reference,
)

_NEW = dl.SNAPSHOT_REPO_PREFIXES["ensembl"]
_OLD = "datasets/just-dna-seq/ensembl_variations/data"
_RELEASE = "ensembl-variation-2026_07_13-vep116.0"
_WHOLE = ManifestCoverage((), ())


def _parquet(frame: pl.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.write_parquet(buf)
    return buf.getvalue()


def _old_rows(chrom: str) -> bytes:
    """The old repo's shape: one row per site, a multi-allelic `alt` pipe-joined."""
    return _parquet(
        pl.DataFrame({"chrom": [chrom], "start": [100], "ref": ["G"], "alt": ["A|T"], "id": ["rs1"]})
    )


def _new_rows(chrom: str) -> bytes:
    """The new repo's shape: one row per ALT, and a `row_idx`."""
    return _parquet(
        pl.DataFrame(
            {
                "chrom": [chrom, chrom],
                "start": [100, 100],
                "ref": ["G", "G"],
                "alt": ["A", "T"],
                "id": ["rs1", "rs1"],
                "row_idx": [0, 1],
            }
        )
    )


def _manifest(files: dict[str, bytes], release_id: str = _RELEASE) -> str:
    return json.dumps(
        {
            "release_id": release_id,
            "layout_version": 1,
            "files": [
                {
                    "path": f"data/{name}",
                    "group": "core",
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
                for name, body in sorted(files.items())
            ],
        }
    )


class _Hub:
    """A fake `HfFileSystem` over one repo: `data/` bytes, an optional root `manifest.json`."""

    def __init__(self, prefix: str, data: dict[str, bytes], manifest: str | None) -> None:
        self.prefix = prefix
        self.data = data
        self.manifest = manifest
        self.fetched: list[str] = []
        self.listed: list[str] = []

    def ls(self, prefix: str, detail: bool = True):
        self.listed.append(prefix)
        if prefix != self.prefix:
            raise FileNotFoundError(prefix)
        return [f"{prefix}/{name}" for name in self.data]

    def get(self, remote_path: str, local_path: str) -> None:
        root = self.prefix.rsplit("/", 1)[0]
        name = remote_path.rsplit("/", 1)[-1]
        if remote_path == f"{root}/{SNAPSHOT_MANIFEST_FILENAME}" and self.manifest is not None:
            self.fetched.append(name)
            Path(local_path).write_text(self.manifest, encoding="utf-8")
            return
        if remote_path == f"{self.prefix}/{name}" and name in self.data:
            self.fetched.append(f"data/{name}")
            Path(local_path).write_bytes(self.data[name])
            return
        raise FileNotFoundError(remote_path)


@pytest.fixture
def hub(monkeypatch):
    import huggingface_hub

    def install(prefix: str, data: dict[str, bytes], manifest: str | None) -> _Hub:
        fs = _Hub(prefix, data, manifest)
        monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
        monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
        return fs

    return install


_NAMES = ("homo_sapiens-chr21.parquet", "homo_sapiens-chrMT.parquet")


def _new_release() -> dict[str, bytes]:
    return {name: _new_rows(name.split("chr")[-1].removesuffix(".parquet")) for name in _NAMES}


def _old_release() -> dict[str, bytes]:
    return {name: _old_rows(name.split("chr")[-1].removesuffix(".parquet")) for name in _NAMES}


def _pull_old(hub, cache: Path) -> None:
    """A cache pulled from the old repo by the provisioner as it stood: a record naming that repo."""
    hub(_OLD, _old_release(), None)
    dl._provision_snapshot(
        cache,
        _OLD,
        label="Ensembl",
        error_cls=dl.EnsemblReferenceError,
        filename_glob="homo_sapiens-*.parquet",
    )
    assert pull_record_repo(cache) == _OLD


# ── the prefix ──────────────────────────────────────────────────────────────────────────────────


def test_the_ensembl_lane_reads_the_split_repo() -> None:
    assert _NEW == "datasets/just-dna-seq/ensembl_variations_split/data"


def test_every_provisioned_lane_states_its_repo() -> None:
    """The prefixes are a registry beside the globs: the same lanes, so neither can lose one."""
    assert set(dl.SNAPSHOT_REPO_PREFIXES) == set(dl.SNAPSHOT_FILE_GLOBS)


# ── 1. a warm cache from the old repo is not this snapshot ─────────────────────────────────────


def test_a_cache_pulled_from_the_old_repo_is_repulled_from_the_new_one(hub, tmp_path: Path) -> None:
    """The reported hole: identical names, a complete record, and the switched prefix kept the old bytes."""
    cache = tmp_path / "ensembl"
    _pull_old(hub, cache)
    new = _new_release()
    fs = hub(_NEW, new, _manifest(new))

    dl.ensure_snapshot(cache)

    assert sorted(f for f in fs.fetched if f.startswith("data/")) == [f"data/{n}" for n in sorted(_NAMES)]
    for name in _NAMES:
        assert (cache / "data" / name).read_bytes() == new[name]
    assert pull_record_repo(cache) == _NEW
    assert manifest_coverage(cache) == _WHOLE


def test_a_new_repo_pull_is_trusted_warm_and_never_listed_again(hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    new = _new_release()
    hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    fs = hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    assert fs.listed == [] and fs.fetched == []


def test_an_unrecorded_cache_of_old_bytes_is_not_recorded_as_the_new_release(hub, tmp_path: Path) -> None:
    """just-dna-lite's downloader writes the same names and no pull record: whole files, the old release.

    Before RM372 the provisioner compared an unrecorded cache with the listing by name, found every
    file present and whole, and wrote a record naming the new repo over the old bytes.
    """
    cache = tmp_path / "ensembl"
    for name, body in _old_release().items():
        (cache / "data").mkdir(parents=True, exist_ok=True)
        (cache / "data" / name).write_bytes(body)
    new = _new_release()
    fs = hub(_NEW, new, _manifest(new))

    dl.ensure_snapshot(cache)

    assert sorted(f for f in fs.fetched if f.startswith("data/")) == [f"data/{n}" for n in sorted(_NAMES)]
    assert manifest_coverage(cache) == _WHOLE


def test_an_unrecorded_cache_the_manifest_attests_is_kept(hub, tmp_path: Path) -> None:
    """Attested by sha256, so nothing is downloaded: the check is a hash, not a refetch of everything."""
    cache = tmp_path / "ensembl"
    new = _new_release()
    for name, body in new.items():
        (cache / "data").mkdir(parents=True, exist_ok=True)
        (cache / "data" / name).write_bytes(body)
    fs = hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    assert [f for f in fs.fetched if f.startswith("data/")] == []
    assert pull_record_repo(cache) == _NEW


def test_a_download_the_manifest_does_not_attest_is_refused(hub, tmp_path: Path) -> None:
    """A file whose bytes hash to something else is never renamed into the cache."""
    cache = tmp_path / "ensembl"
    new = _new_release()
    lying = _manifest({**new, "homo_sapiens-chr21.parquet": _old_rows("21")})
    hub(_NEW, new, lying)
    with pytest.raises(dl.EnsemblReferenceError, match="sha256"):
        dl.ensure_snapshot(cache)
    assert not (cache / "data" / "homo_sapiens-chr21.parquet").exists()
    assert not list((cache / "data").glob("*.part"))


def test_a_published_file_the_manifest_does_not_name_is_refused_before_any_download(
    hub, tmp_path: Path
) -> None:
    cache = tmp_path / "ensembl"
    new = _new_release()
    fs = hub(_NEW, new, _manifest({"homo_sapiens-chr21.parquet": new["homo_sapiens-chr21.parquet"]}))
    with pytest.raises(dl.EnsemblReferenceError, match="homo_sapiens-chrMT.parquet"):
        dl.ensure_snapshot(cache)
    assert [f for f in fs.fetched if f.startswith("data/")] == []


def test_an_interrupted_switch_is_still_the_old_repos_cache(hub, tmp_path: Path) -> None:
    """The record names the new repo from the first byte, so it also says what it is replacing.

    Without the `replacing` key an interrupted switch left new chr21 beside old chrMT under a record
    naming the new repo, every file whole, and the next call returned it as finished. The manifest is
    placed before the first byte for the same reason: the resolver withholds the mixture meanwhile.
    """
    cache = tmp_path / "ensembl"
    _pull_old(hub, cache)
    new = _new_release()
    fs = hub(_NEW, new, _manifest(new))
    real_get = fs.get

    def get(remote_path: str, local_path: str) -> None:
        if remote_path.endswith("homo_sapiens-chrMT.parquet"):
            raise KeyboardInterrupt  # killed after chr21
        real_get(remote_path, local_path)

    fs.get = get
    with pytest.raises(KeyboardInterrupt):
        dl.ensure_snapshot(cache)
    assert pull_record_repo(cache) == _OLD, "an unfinished switch is still the old repo's cache"
    assert manifest_coverage(cache) == ManifestCoverage(("data/homo_sapiens-chrMT.parquet",), ())
    assert resolve_ensembl_reference(cache, load_dotenv_file=False) is None

    fs = hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    assert [f for f in fs.fetched if f.startswith("data/")] == ["data/homo_sapiens-chrMT.parquet"]
    assert pull_record_repo(cache) == _NEW
    assert resolve_ensembl_reference(cache, load_dotenv_file=False) == cache


def test_an_interrupted_switch_with_no_manifest_still_refetches_the_old_files(hub, tmp_path: Path) -> None:
    """Where the new repo publishes no manifest, the record's `replacing` is the only witness.

    Without it the second call read a record naming the new repo, kept every whole file, and served
    the old chrMT as the new repo's.
    """
    cache = tmp_path / "ensembl"
    _pull_old(hub, cache)
    new = _new_release()
    fs = hub(_NEW, new, None)
    real_get = fs.get

    def get(remote_path: str, local_path: str) -> None:
        if remote_path.endswith("homo_sapiens-chrMT.parquet"):
            raise KeyboardInterrupt
        real_get(remote_path, local_path)

    fs.get = get
    with pytest.raises(KeyboardInterrupt):
        dl.ensure_snapshot(cache)
    assert pull_record_repo(cache) == _OLD

    fs = hub(_NEW, new, None)
    dl.ensure_snapshot(cache)
    assert (cache / "data" / "homo_sapiens-chrMT.parquet").read_bytes() == new["homo_sapiens-chrMT.parquet"]
    assert pull_record_repo(cache) == _NEW


def test_a_pull_is_completed_without_rehashing_what_it_placed(hub, tmp_path: Path, monkeypatch) -> None:
    """A file this repo's pull placed was hashed on its way in; finishing the pull compares sizes only."""
    cache = tmp_path / "ensembl"
    new = _new_release()
    hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    (cache / "data" / "homo_sapiens-chrMT.parquet").unlink()
    hashed: list[str] = []
    real = dl.manifest_attests
    monkeypatch.setattr(
        dl, "manifest_attests", lambda m, rel, local: hashed.append(rel) or real(m, rel, local)
    )
    fs = hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    assert [f for f in fs.fetched if f.startswith("data/")] == ["data/homo_sapiens-chrMT.parquet"]
    assert hashed == ["data/homo_sapiens-chrMT.parquet"], "only the download is hashed"


def test_a_switched_cache_is_served_when_the_listing_cannot_be_read(hub, tmp_path: Path, caplog) -> None:
    """Could-not-ask is not nothing-published: the old release stays usable through an outage."""
    cache = tmp_path / "ensembl"
    _pull_old(hub, cache)
    fs = hub(_NEW, {}, None)
    fs.prefix = "elsewhere"  # every listing raises
    with caplog.at_level("WARNING"):
        assert dl.ensure_snapshot(cache) == cache
    assert "unknown" in caplog.text
    assert pull_record_repo(cache) == _OLD


def test_a_switch_removes_the_old_repos_root_files_the_new_repo_lacks(hub, tmp_path: Path) -> None:
    """An old `release.json` left beside new bytes would label them with the old release."""
    cache = tmp_path / "ensembl"
    _pull_old(hub, cache)
    (cache / "release.json").write_text(json.dumps({"dataset": "ensembl_old"}), encoding="utf-8")
    new = _new_release()
    hub(_NEW, new, _manifest(new))
    dl.ensure_snapshot(cache)
    assert not (cache / "release.json").exists()
    assert ensembl_release_label(cache) == _RELEASE


def test_cache_pull_sends_an_old_repo_cache_down_the_pull_route(tmp_path: Path) -> None:
    """`prepare_lane` left every resolving cache with a record alone; one naming another repo is not."""
    cache = tmp_path / "ensembl"
    (cache / "data").mkdir(parents=True)
    for name, body in _old_release().items():
        (cache / "data" / name).write_bytes(body)
    (cache / PULL_RECORD_FILENAME).write_text(
        json.dumps({"repo": _OLD, "files": [f"data/{n}" for n in _NAMES]}), encoding="utf-8"
    )
    pulled: list[str] = []

    def ensure() -> Path:
        pulled.append("pulled")
        return cache

    lane = dataclasses.replace(
        LANES_BY_NAME["ensembl"], resolve=lambda: cache, ensure=ensure, default_dir=lambda: cache
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=tmp_path))
    assert pulled == ["pulled"]
    assert (outcome.ready, outcome.route) == (True, "pulled")
    assert _OLD in outcome.detail

    # …and one whose record names this lane's repo is still present, untouched.
    (cache / PULL_RECORD_FILENAME).write_text(
        json.dumps({"repo": _NEW, "files": [f"data/{n}" for n in _NAMES]}), encoding="utf-8"
    )
    pulled.clear()
    assert caches.prepare_lane(lane, RebuildRequest(out_dir=tmp_path)).route == "present"
    assert pulled == []


# ── 2. a cache mixing releases is withheld ─────────────────────────────────────────────────────


def _cache_with(tmp_path: Path, files: dict[str, bytes], manifest: str | None) -> Path:
    cache = tmp_path / "ensembl"
    (cache / "data").mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (cache / "data" / name).write_bytes(body)
    if manifest is not None:
        (cache / SNAPSHOT_MANIFEST_FILENAME).write_text(manifest, encoding="utf-8")
    return cache


def test_old_chrmt_beside_new_chr21_is_withheld(tmp_path: Path, caplog) -> None:
    """The measured case: the two releases answered together and nothing said so."""
    new = _new_release()
    mixed = {**new, "homo_sapiens-chrMT.parquet": _old_rows("MT")}
    cache = _cache_with(tmp_path, mixed, _manifest(new))
    assert manifest_coverage(cache) == ManifestCoverage(("data/homo_sapiens-chrMT.parquet",), ())
    with caplog.at_level("WARNING"):
        assert resolve_ensembl_reference(cache, load_dotenv_file=False) is None
    assert "homo_sapiens-chrMT.parquet" in caplog.text and "cache pull" in caplog.text


def test_a_cache_lacking_files_its_manifest_attests_is_withheld_as_incomplete(tmp_path: Path, caplog) -> None:
    """The converse of a mixed cache, measured by the migration probe on cc1fea4f: NEW's manifest with
    12 of its 25 attested files and no pull record was served with no warning. Every file present was
    attested, so a check that only asks about the files present could not fail.
    """
    new = _new_release()
    present = {"homo_sapiens-chr21.parquet": new["homo_sapiens-chr21.parquet"]}
    cache = _cache_with(tmp_path, present, _manifest(new))
    assert manifest_coverage(cache) == ManifestCoverage((), ("data/homo_sapiens-chrMT.parquet",))
    with caplog.at_level("WARNING"):
        assert resolve_ensembl_reference(cache, load_dotenv_file=False) is None
    assert "homo_sapiens-chrMT.parquet" in caplog.text
    assert "the snapshot is incomplete" in caplog.text and "mixes releases" not in caplog.text


def test_incomplete_and_mixed_are_two_reasons(tmp_path: Path, caplog) -> None:
    """Pairwise distinct: fetch what is missing is not the same remedy as drop the other release."""
    new = _new_release()
    mixed = _cache_with(
        tmp_path / "mixed", {**new, "homo_sapiens-chrMT.parquet": _old_rows("MT")}, _manifest(new)
    )
    with caplog.at_level("WARNING"):
        resolve_ensembl_reference(mixed, load_dotenv_file=False)
    assert "mixes releases" in caplog.text and "the snapshot is incomplete" not in caplog.text


def test_a_prebuilt_duckdb_does_not_bypass_the_check(tmp_path: Path) -> None:
    """This machine's `ensembl_variations.duckdb` is a view over the same `data/*.parquet` glob."""
    new = _new_release()
    cache = _cache_with(tmp_path, {**new, "homo_sapiens-chrMT.parquet": _old_rows("MT")}, _manifest(new))
    (cache / DUCKDB_NAME).write_bytes(b"")
    assert resolve_ensembl_reference(cache, load_dotenv_file=False) is None


def test_a_file_the_manifest_does_not_name_is_withheld(tmp_path: Path) -> None:
    new = _new_release()
    cache = _cache_with(tmp_path, {**new, "homo_sapiens-chr22.parquet": _new_rows("22")}, _manifest(new))
    assert manifest_coverage(cache) == ManifestCoverage(("data/homo_sapiens-chr22.parquet",), ())
    assert resolve_ensembl_reference(cache, load_dotenv_file=False) is None


def test_an_unreadable_manifest_attests_nothing(tmp_path: Path) -> None:
    """Present and unreadable is the refusal, never the unknown arm (it is not an absent manifest)."""
    cache = _cache_with(tmp_path, _new_release(), "{not json")
    assert manifest_coverage(cache) == ManifestCoverage(tuple(f"data/{n}" for n in sorted(_NAMES)), ())
    assert resolve_ensembl_reference(cache, load_dotenv_file=False) is None


def test_an_attested_cache_and_a_cache_with_no_manifest_both_serve(tmp_path: Path) -> None:
    """No manifest is the old repo's snapshot, an unknown release: served as it always was."""
    new = _new_release()
    attested = _cache_with(tmp_path / "a", new, _manifest(new))
    assert manifest_coverage(attested) == _WHOLE
    assert resolve_ensembl_reference(attested, load_dotenv_file=False) == attested
    bare = _cache_with(tmp_path / "b", _old_release(), None)
    assert manifest_coverage(bare) is None
    assert resolve_ensembl_reference(bare, load_dotenv_file=False) == bare


# ── 3. the release has a label ─────────────────────────────────────────────────────────────────


def test_the_label_is_the_manifests_release_id(tmp_path: Path) -> None:
    new = _new_release()
    cache = _cache_with(tmp_path, new, _manifest(new))
    assert ensembl_release_label(cache) == _RELEASE
    assert LANES_BY_NAME["ensembl"].release_label(cache) == _RELEASE


def test_a_snapshot_that_states_no_release_has_no_label(tmp_path: Path) -> None:
    """The old repo has neither file: unknown, withheld, never a guess."""
    assert ensembl_release_label(_cache_with(tmp_path / "a", _old_release(), None)) is None
    blank = _cache_with(tmp_path / "b", _new_release(), json.dumps({"release_id": "  ", "files": []}))
    assert ensembl_release_label(blank) is None
