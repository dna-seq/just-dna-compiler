"""The split Ensembl release's optional `groups/` are pulled by the lane's own provisioner (RM437).

prepare-annotations' split repo moved every annotation value (consequence, clinical flags,
frequencies, CADD) out of the core and into column groups under `groups/<name>/`, each joining the core
on `(chrom, row_idx)`, which holds within one `release_id` only. So the only safe writer of a group is
the pull that took the core: it checks each group file against the same manifest, records the group's
release in the pull record, and re-pulls it when the core's release moves. Each test pins one promise
against the real provisioner over a fake hub serving real parquet bytes:

- a group is selected by name from the manifest's own `groups`, `core` and unknown names refused before
  any download;
- a group is gated per its licensor's terms, read off the manifest's `licence` (CADD forbids sale,
  Ensembl's data is unrestricted, an unknown licensor is unknown terms);
- `ensembl_group_dir` is the only path to a group, and refuses one that is not the core's release;
- the selection is sticky: a later `ensure`, named groups or not, re-pulls it when the core moves.

The licence sentences in the fake manifest are the ones the real split manifest states (measured
2026-11-17 off `ensembl-variation-2026_07_13-vep116.0`).
"""

import hashlib
import io
import json
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
from just_dna_enricher import download as dl
from just_dna_enricher.licensing import (
    CADD_TERMS,
    ENSEMBL_TERMS,
    LicenseRefusal,
    check_declared_use,
    snapshot_group_terms,
)
from just_dna_enricher.locations import (
    CORE_IS_NOT_A_GROUP,
    PULL_RECORD_FILENAME,
    PULL_RECORD_GROUPS_KEY,
    SNAPSHOT_MANIFEST_FILENAME,
    SNAPSHOT_REPO_IDS,
    EnsemblGroupReleaseError,
    SnapshotManifest,
    ensembl_group_dir,
    ensembl_release_label,
    pulled_groups,
)

_ROOT = f"datasets/{SNAPSHOT_REPO_IDS['ensembl']}"
_OLD = "ensembl-variation-2026_07_13-vep116.0"
_NEW = "ensembl-variation-2026_10_01-vep117.0"
_ENSEMBL_LICENCE = "Ensembl data: no restrictions (https://www.ensembl.org/info/about/legal/)"
_CADD_LICENCE = "CADD: free for non-commercial use only (https://cadd.gs.washington.edu/)"
_MYSTERY_LICENCE = "Mystery Lab: ask us first (https://example.invalid/terms)"
_CHROMS = ("21", "MT")


def _parquet(frame: pl.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.write_parquet(buf)
    return buf.getvalue()


def _release(tag: int, chroms: tuple[str, ...] = _CHROMS, cadd_chroms: tuple[str, ...] | None = None) -> dict:
    """One release's files, `{path under the repo root: bytes}`; `tag` makes every byte differ by release."""
    files: dict[str, bytes] = {}
    for chrom in chroms:
        name = f"homo_sapiens-chr{chrom}.parquet"
        files[f"data/{name}"] = _parquet(
            pl.DataFrame(
                {
                    "chrom": [chrom],
                    "start": [100 + tag],
                    "ref": ["G"],
                    "alt": ["A"],
                    "id": ["rs1"],
                    "row_idx": [0],
                }
            )
        )
        files[f"groups/consequence/{name}"] = _parquet(
            pl.DataFrame({"chrom": [chrom], "row_idx": [0], "consequence": [f"missense_{tag}"]})
        )
        files[f"groups/mystery/{name}"] = _parquet(
            pl.DataFrame({"chrom": [chrom], "row_idx": [0], "x": [tag]})
        )
    for chrom in cadd_chroms if cadd_chroms is not None else chroms:
        name = f"homo_sapiens-chr{chrom}.parquet"
        files[f"groups/cadd/{name}"] = _parquet(
            pl.DataFrame({"chrom": [chrom], "row_idx": [0], "cadd_phred": [float(20 + tag)]})
        )
    return files


def _manifest(files: dict[str, bytes], release_id: str, *, groups: dict[str, str] | None = None) -> str:
    groups = (
        groups
        if groups is not None
        else {
            "consequence": _ENSEMBL_LICENCE,
            "cadd": _CADD_LICENCE,
            "mystery": _MYSTERY_LICENCE,
        }
    )
    return json.dumps(
        {
            "release_id": release_id,
            "layout_version": 1,
            "core_columns": ["chrom", "start", "ref", "alt", "id", "row_idx"],
            "groups": {
                name: {"name": name, "description": f"the {name} group", "licence": licence, "default": False}
                for name, licence in groups.items()
            },
            "files": [
                {
                    "path": path,
                    "group": path.split("/")[1] if path.startswith("groups/") else "core",
                    "chrom": path.rsplit("chr", 1)[-1].removesuffix(".parquet"),
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
                for path, body in sorted(files.items())
                if path.endswith(".parquet")
            ],
        }
    )


class _Hub:
    """A fake `HfFileSystem` over the split repo's tree. A fetch opens the destination first, as the real one does."""

    def __init__(self, files: dict[str, bytes | str], failing: dict[str, Exception] | None = None) -> None:
        self.files = {k: v.encode() if isinstance(v, str) else v for k, v in files.items()}
        self.failing = failing or {}
        self.listed: list[str] = []
        self.fetched: list[str] = []

    def ls(self, prefix: str, detail: bool = True):
        self.listed.append(prefix)
        directory = prefix.removeprefix(f"{_ROOT}/").rstrip("/")
        names = [k for k in self.files if k.rsplit("/", 1)[0] == directory and "/" in k]
        if not names:
            raise FileNotFoundError(prefix)
        if not detail:
            return [f"{_ROOT}/{k}" for k in names]
        return [{"name": f"{_ROOT}/{k}", "size": len(self.files[k]), "type": "file"} for k in names]

    def get(self, remote: str, local: str) -> None:
        relative = remote.removeprefix(f"{_ROOT}/")
        Path(local).write_bytes(b"")
        if relative in self.failing:
            raise self.failing[relative]
        if relative not in self.files:
            raise FileNotFoundError(remote)
        self.fetched.append(relative)
        Path(local).write_bytes(self.files[relative])

    def parquet_fetched(self) -> list[str]:
        return sorted(f for f in self.fetched if f.endswith(".parquet"))


@pytest.fixture
def install_hub(monkeypatch):
    def install(files: dict[str, bytes | str], **kwargs) -> _Hub:
        hub = _Hub(files, **kwargs)
        monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: hub)
        monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
        return hub

    return install


def _published(tag: int, release_id: str, **kwargs) -> dict[str, bytes | str]:
    files: dict[str, bytes | str] = dict(_release(tag, **kwargs))
    files[SNAPSHOT_MANIFEST_FILENAME] = _manifest(files, release_id)  # type: ignore[arg-type]
    return files


def _explode(token=None):
    raise AssertionError("the hub was read")


def _record(cache: Path) -> dict:
    return json.loads((cache / PULL_RECORD_FILENAME).read_text(encoding="utf-8"))


# ── the licence of a group, by its licensor ──────────────────────────────────────────────────────


def test_a_group_licence_maps_to_terms_by_its_licensor() -> None:
    assert snapshot_group_terms("consequence", _ENSEMBL_LICENCE) is ENSEMBL_TERMS
    assert snapshot_group_terms("cadd", _CADD_LICENCE) is CADD_TERMS
    unknown = snapshot_group_terms("mystery", _MYSTERY_LICENCE)
    assert unknown.commercial_use is None and unknown.share_alike is None and unknown.redistribution is None


def test_cadd_downloads_under_research_use_is_refused_commercially_and_skipped_unstated() -> None:
    assert check_declared_use(CADD_TERMS, "non_commercial") is None
    with pytest.raises(LicenseRefusal, match="forbid offering the data for sale"):
        check_declared_use(CADD_TERMS, "commercial")
    assert "forbids sale and no use was declared" in (check_declared_use(CADD_TERMS, "unstated") or "")
    assert check_declared_use(ENSEMBL_TERMS, "commercial") is None


@pytest.mark.parametrize("use", ["unstated", "non_commercial", "commercial"])
def test_an_unknown_licensor_is_skipped_under_every_use_quoting_the_licence(use: str) -> None:
    reason = check_declared_use(snapshot_group_terms("mystery", _MYSTERY_LICENCE), use)
    assert reason is not None and "terms could not be established" in reason
    assert repr(_MYSTERY_LICENCE) in reason and "'Mystery Lab'" in reason


def test_a_group_stating_no_licence_is_unknown_terms_and_says_so() -> None:
    reason = check_declared_use(snapshot_group_terms("bare", None), "non_commercial")
    assert reason is not None and "states no licence for the bare group" in reason


def test_the_manifest_types_its_groups_with_their_licence() -> None:
    files = _release(0)
    manifest = SnapshotManifest.model_validate_json(_manifest(files, _OLD))
    assert set(manifest.groups or {}) == {"consequence", "cadd", "mystery"}
    assert manifest.groups["cadd"].licence == _CADD_LICENCE
    assert [f.path for f in manifest.group_files("cadd")] == sorted(
        p for p in files if p.startswith("groups/cadd/")
    )


# ── selecting, gating and pulling a group ───────────────────────────────────────────────────────


def test_a_named_group_is_pulled_attested_and_recorded_beside_the_core(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    published = _published(0, _OLD)
    hub = install_hub(published)

    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")

    cadd = sorted(p for p in published if p.startswith("groups/cadd/"))
    core = sorted(p for p in published if p.startswith("data/"))
    assert hub.parquet_fetched() == sorted(cadd + core)
    for path in cadd:
        assert (cache / path).read_bytes() == published[path]
    entry = pulled_groups(cache)["cadd"]
    assert entry == {"release_id": _OLD, "files": cadd, "declared_use": "non_commercial"}
    assert _record(cache)["files"] == core  # the core's own list carries no group file
    assert ensembl_group_dir(cache, "cadd") == cache / "groups" / "cadd"
    assert not (cache / "groups" / "consequence").exists()


def test_a_commercial_use_refuses_cadd_before_any_download(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    hub = install_hub(_published(0, _OLD))
    with pytest.raises(LicenseRefusal, match="nothing was fetched"):
        dl.ensure_snapshot(cache, groups=["cadd"], declared_use="commercial")
    assert hub.parquet_fetched() == []
    assert not cache.exists()


def test_an_unstated_use_pulls_the_core_and_skips_cadd_with_the_reason(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    hub = install_hub(_published(0, _OLD))
    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, groups=["cadd"], _follow_hub=follow)
    assert not any(f.startswith("groups/") for f in hub.parquet_fetched())
    assert follow.groups["cadd"].startswith("skipped — cadd forbids sale and no use was declared")
    assert "cadd" not in pulled_groups(cache)
    with pytest.raises(EnsemblGroupReleaseError, match="names no such group"):
        ensembl_group_dir(cache, "cadd")


def test_an_unknown_licensor_skips_its_group_even_under_a_research_use(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, groups=["mystery"], declared_use="non_commercial", _follow_hub=follow)
    assert repr(_MYSTERY_LICENCE) in follow.groups["mystery"]
    assert not (cache / "groups" / "mystery").exists()


def test_an_ensembl_group_downloads_under_a_commercial_use(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"], declared_use="commercial")
    assert ensembl_group_dir(cache, "consequence").is_dir()


def test_core_is_not_a_group_and_is_refused_before_the_hub_is_read(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", _explode)
    with pytest.raises(ValueError) as caught:
        dl.ensure_snapshot(tmp_path / "ensembl", groups=["core"])
    assert str(caught.value) == CORE_IS_NOT_A_GROUP
    with pytest.raises(ValueError, match="core. is not a group name"):
        ensembl_group_dir(tmp_path / "ensembl", "core")


def test_an_unknown_group_name_is_refused_before_any_download(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    hub = install_hub(_published(0, _OLD))
    with pytest.raises(
        ValueError, match="publishes no group 'frequencies'; its groups are cadd, consequence, mystery"
    ):
        dl.ensure_snapshot(cache, groups=["frequencies"], declared_use="non_commercial")
    assert hub.parquet_fetched() == [] and not cache.exists()


def test_a_group_file_the_manifest_does_not_attest_is_never_placed(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    published = _published(0, _OLD)
    published["groups/cadd/homo_sapiens-chr21.parquet"] = _release(9)[
        "groups/cadd/homo_sapiens-chr21.parquet"
    ]
    install_hub(published)
    with pytest.raises(dl.EnsemblReferenceError, match="does not match the size and sha256"):
        dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    assert not (cache / "groups/cadd/homo_sapiens-chr21.parquet").exists()
    with pytest.raises(EnsemblGroupReleaseError, match="a pull that did not finish"):
        ensembl_group_dir(cache, "cadd")


def test_a_manifest_placing_a_group_file_outside_its_directory_is_refused(
    install_hub, tmp_path: Path
) -> None:
    cache = tmp_path / "ensembl"
    files = dict(_release(0))
    files["groups/cadd/../../escape.parquet"] = files.pop("groups/cadd/homo_sapiens-chrMT.parquet")
    manifest = json.loads(_manifest(files, _OLD))
    for entry in manifest["files"]:
        if entry["path"].endswith("escape.parquet"):
            entry["group"] = "cadd"
    published: dict[str, bytes | str] = dict(files)
    published[SNAPSHOT_MANIFEST_FILENAME] = json.dumps(manifest)
    install_hub(published)
    with pytest.raises(dl.EnsemblReferenceError, match="outside groups/cadd/"):
        dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    assert not (tmp_path / "escape.parquet").exists()


# ── the guard: `ensembl_group_dir` ──────────────────────────────────────────────────────────────


def test_a_hand_placed_group_is_refused_as_unrecorded(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    published = _published(0, _OLD)
    install_hub(published)
    dl.ensure_snapshot(cache)
    (cache / "groups" / "cadd").mkdir(parents=True)
    (cache / "groups/cadd/homo_sapiens-chr21.parquet").write_bytes(
        published["groups/cadd/homo_sapiens-chr21.parquet"]
    )
    with pytest.raises(EnsemblGroupReleaseError, match="was not taken by a pull of this cache"):
        ensembl_group_dir(cache, "cadd")


def test_a_group_of_another_release_than_the_core_is_refused(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"])
    (cache / SNAPSHOT_MANIFEST_FILENAME).write_text(_manifest(_release(1), _NEW), encoding="utf-8")
    with pytest.raises(EnsemblGroupReleaseError) as caught:
        ensembl_group_dir(cache, "consequence")
    assert f"is release {_OLD} and the core beside it is {_NEW}" in str(caught.value)
    assert "holds within one release only" in str(caught.value)


def test_a_core_stating_no_release_cannot_vouch_for_a_group(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"])
    (cache / SNAPSHOT_MANIFEST_FILENAME).unlink()
    with pytest.raises(EnsemblGroupReleaseError, match="states no release in its manifest.json"):
        ensembl_group_dir(cache, "consequence")


# ── the selection is sticky ─────────────────────────────────────────────────────────────────────


def test_a_warm_cache_with_current_groups_reads_no_hub(install_hub, monkeypatch, tmp_path: Path) -> None:
    """`enrich`'s promise: a whole cache serves offline, groups included."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", _explode)
    dl.ensure_snapshot(cache)
    dl.ensure_snapshot(cache, groups=["cadd"])  # named and current: nothing is taken, nothing is read
    assert ensembl_group_dir(cache, "cadd").is_dir()


def test_a_moved_core_re_pulls_the_recorded_groups_without_naming_them(install_hub, tmp_path: Path) -> None:
    """`cache pull` with no `--groups`, unstated: the CADD group comes back under its recorded declaration."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd", "consequence"], declared_use="non_commercial")
    new = _published(1, _NEW, cadd_chroms=("21",))
    hub = install_hub(new)

    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, _follow_hub=follow)

    assert follow.outcome == "refreshed"
    assert follow.groups == {"cadd": "pulled", "consequence": "pulled"}
    for group in ("cadd", "consequence"):
        directory = ensembl_group_dir(cache, group)
        assert {p.name for p in directory.glob("*.parquet")} == {
            p.rsplit("/", 1)[-1] for p in new if p.startswith(f"groups/{group}/")
        }
        for path in directory.glob("*.parquet"):
            assert path.read_bytes() == new[f"groups/{group}/{path.name}"]
    assert pulled_groups(cache)["cadd"]["declared_use"] == "non_commercial"
    assert "groups/cadd/homo_sapiens-chrMT.parquet" not in hub.fetched  # the new release has none
    assert not (cache / "groups/cadd/homo_sapiens-chrMT.parquet").exists()  # the old one's was ours


def test_an_explicit_commercial_use_outranks_the_recorded_declaration(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    install_hub(_published(1, _NEW))
    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, declared_use="commercial", _follow_hub=follow)  # did not name cadd: no raise
    assert follow.groups["cadd"].startswith("not re-pulled — cadd is CADD terms of use")
    with pytest.raises(EnsemblGroupReleaseError, match=f"is release {_OLD} and the core beside it is {_NEW}"):
        ensembl_group_dir(cache, "cadd")


def test_a_core_refresh_keeps_a_group_at_its_old_release_until_that_group_is_pulled(
    install_hub, tmp_path: Path
) -> None:
    """Both record writers carry the selection over; only the group's own pull moves its release."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"])
    files = dict(_release(1))
    published: dict[str, bytes | str] = dict(files)
    published[SNAPSHOT_MANIFEST_FILENAME] = _manifest(files, _NEW, groups={"cadd": _CADD_LICENCE})
    install_hub(published)  # the new release no longer publishes `consequence`

    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, _follow_hub=follow)

    assert follow.outcome == "refreshed"
    assert follow.groups["consequence"].startswith("not re-pulled — the Ensembl release")
    assert _record(cache)[PULL_RECORD_GROUPS_KEY]["consequence"]["release_id"] == _OLD
    with pytest.raises(EnsemblGroupReleaseError, match="and the core beside it is"):
        ensembl_group_dir(cache, "consequence")


def test_a_sticky_group_that_cannot_be_fetched_does_not_sink_the_core(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"])
    install_hub(
        _published(1, _NEW),
        failing={"groups/consequence/homo_sapiens-chr21.parquet": ConnectionError("reset by peer")},
    )

    dl.ensure_snapshot(cache, _follow_hub=dl._FollowHub(ensembl_release_label))  # no raise

    assert ensembl_release_label(cache) == _NEW
    assert not (cache / "groups/consequence/homo_sapiens-chr21.part").exists()
    with pytest.raises(EnsemblGroupReleaseError, match="a pull that did not finish"):
        ensembl_group_dir(cache, "consequence")
    # Named, the same failure is the caller's to see.
    with pytest.raises(
        dl.EnsemblReferenceError, match="could not be fetched .ConnectionError: reset by peer"
    ):
        dl.ensure_snapshot(cache, groups=["consequence"])
