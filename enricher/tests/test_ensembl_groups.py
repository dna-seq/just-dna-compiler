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

import dataclasses
import hashlib
import io
import json
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
from just_dna_enricher import caches, locations
from just_dna_enricher import download as dl
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.cli import app as enricher_app
from just_dna_enricher.cli import cache_commands
from just_dna_enricher.cli.cache_commands import GROUPS_NEED_ENSEMBL_ONLY
from just_dna_enricher.licensing import (
    CADD_TERMS,
    ENSEMBL_TERMS,
    LicenseRefusal,
    check_declared_use,
    snapshot_group_terms,
)
from just_dna_enricher.locations import (
    CACHE_BASE_VAR,
    CORE_IS_NOT_A_GROUP,
    PULL_RECORD_FILENAME,
    PULL_RECORD_GROUPS_KEY,
    SNAPSHOT_MANIFEST_FILENAME,
    SNAPSHOT_REPO_IDS,
    EnsemblGroupReleaseError,
    SnapshotManifest,
    SnapshotManifestGroup,
    ensembl_group_dir,
    ensembl_release_label,
    pulled_groups,
)
from typer.testing import CliRunner

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
        self.listing_down = False

    def ls(self, prefix: str, detail: bool = True):
        self.listed.append(prefix)
        if self.listing_down:
            raise ConnectionError("the listing timed out")
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


# ── a record present but unreadable is refused, never read as absent (review round 1, item 3) ───────────


#: Pull records that are there and cannot be read, by what is wrong with them.
_UNREADABLE_RECORDS: dict[str, bytes] = {
    "not utf-8": b"\xff\xfe{",
    "not json": b'{"repo": "x", "groups": ',
    "not an object": b'["cadd"]',
    "groups not an object": json.dumps({"repo": "x", PULL_RECORD_GROUPS_KEY: ["cadd"]}).encode(),
    "a group entry not an object": json.dumps(
        {"repo": "x", PULL_RECORD_GROUPS_KEY: {"cadd": "pulled"}}
    ).encode(),
}


def test_an_absent_pull_record_names_no_group_and_a_readable_one_names_its_own(tmp_path: Path) -> None:
    assert pulled_groups(tmp_path) == {}
    duckdb_file = tmp_path / "ensembl_variations.duckdb"
    duckdb_file.write_bytes(b"")
    assert pulled_groups(duckdb_file) == {}, (
        "a cache handed as one file holds no pull record, which is no refusal"
    )
    (tmp_path / PULL_RECORD_FILENAME).write_text(json.dumps({"repo": "x"}), encoding="utf-8")
    assert pulled_groups(tmp_path) == {}
    entry = {"release_id": _OLD, "files": [], "declared_use": "unstated"}
    (tmp_path / PULL_RECORD_FILENAME).write_text(
        json.dumps({"repo": "x", PULL_RECORD_GROUPS_KEY: {"cadd": entry}}), encoding="utf-8"
    )
    assert pulled_groups(tmp_path) == {"cadd": entry}


@pytest.mark.parametrize("fault", sorted(_UNREADABLE_RECORDS))
def test_a_pull_record_that_is_there_and_unreadable_is_refused_by_the_reader_and_the_guard(
    tmp_path: Path, fault: str
) -> None:
    """Read as no groups, it ended a sticky selection silently and the guard blamed "not taken by a pull";
    a record that was not UTF-8 raised `UnicodeDecodeError` past the documented type."""
    (tmp_path / PULL_RECORD_FILENAME).write_bytes(_UNREADABLE_RECORDS[fault])
    for read in (lambda: pulled_groups(tmp_path), lambda: ensembl_group_dir(tmp_path, "cadd")):
        with pytest.raises(EnsemblGroupReleaseError) as refused:
            read()
        assert str(refused.value).startswith(
            f"The pull record at {tmp_path / PULL_RECORD_FILENAME} is there and could not be read ("
        )


def test_ensure_refuses_an_unreadable_pull_record_before_anything_is_fetched_or_rewritten(
    install_hub, tmp_path: Path
) -> None:
    """A moved core used to be re-pulled over it, and the rewritten record carried no group: the selection was
    lost with nothing said. Now nothing is fetched and the record is left as it was, for the operator."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    broken = (cache / PULL_RECORD_FILENAME).read_bytes()[:-20]
    (cache / PULL_RECORD_FILENAME).write_bytes(broken)
    hub = install_hub(_published(1, _NEW))
    with pytest.raises(EnsemblGroupReleaseError, match="could not be read"):
        dl.ensure_snapshot(cache)
    assert hub.fetched == [], "nothing was downloaded"
    assert (cache / PULL_RECORD_FILENAME).read_bytes() == broken, "the record was not rewritten"


def test_a_group_record_is_read_member_by_member_so_a_later_field_costs_no_core_pin(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A group field of a kind this reader does not type used to fail the whole manifest: the core's release,
    coverage and pin went with it. Now that field alone reads as unstated, said in a warning, and a group
    record that is not an object keeps its name with nothing stated, so it is never "no such group" and never
    terms that admit."""
    files = _release(0)
    raw = json.loads(_manifest(files, _OLD))
    raw["groups"]["cadd"]["default"] = "auto"
    raw["groups"]["cadd"]["licence"] = {"text": _CADD_LICENCE}
    raw["groups"]["mystery"] = "see the README"
    monkeypatch.setattr(locations, "_SAID", set())
    with caplog.at_level("WARNING", logger="just_dna_enricher.locations"):
        manifest = SnapshotManifest.model_validate_json(json.dumps(raw))
        assert SnapshotManifest.model_validate_json(json.dumps(raw)) == manifest
    assert manifest.release_id == _OLD and manifest.files, "the core is still read"
    assert set(manifest.groups or {}) == {"consequence", "cadd", "mystery"}
    assert (manifest.groups["cadd"].licence, manifest.groups["cadd"].default) == (None, None)
    assert manifest.groups["cadd"].name == "cadd"
    assert manifest.groups["mystery"] == SnapshotManifestGroup()
    assert manifest.groups["consequence"].licence == _ENSEMBL_LICENCE
    said = [r.getMessage() for r in caplog.records]
    assert (
        said.count("The snapshot manifest's cadd group: default, licence do not fit; read as unstated.") == 1
    ), "a manifest is read many times per lookup, and one unread field is said once"
    assert (
        said.count("The snapshot manifest's mystery group is not an object; read with nothing stated.") == 1
    )
    reason = check_declared_use(
        snapshot_group_terms("cadd", manifest.groups["cadd"].licence), "non_commercial"
    )
    assert reason is not None, "an unread licence never admits"


def test_groups_that_are_not_a_map_are_unstated_and_the_core_is_still_read(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(locations, "_SAID", set())
    raw = json.loads(_manifest(_release(0), _OLD))
    raw["groups"] = ["cadd"]
    with caplog.at_level("WARNING", logger="just_dna_enricher.locations"):
        manifest = SnapshotManifest.model_validate_json(json.dumps(raw))
    assert manifest.release_id == _OLD and manifest.files and manifest.groups is None
    assert "The snapshot manifest's groups are not a map of name to record; read as unstated." in [
        r.getMessage() for r in caplog.records
    ]


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
    declared_at = entry.pop("declared_at")
    assert entry == {"release_id": _OLD, "files": cadd, "declared_use": "non_commercial"}
    assert isinstance(declared_at, str) and declared_at.endswith("Z"), "when the use was declared, in UTC"
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


def test_a_moved_core_re_pulls_the_recorded_groups_without_naming_them(
    install_hub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`cache pull` with no `--groups`, unstated: the CADD group comes back under its recorded declaration."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd", "consequence"], declared_use="non_commercial")
    new = _published(1, _NEW, cadd_chroms=("21",))
    hub = install_hub(new)

    follow = dl._FollowHub(ensembl_release_label)
    with caplog.at_level("INFO", logger="just_dna_enricher.download"):
        dl.ensure_snapshot(cache, _follow_hub=follow)
    said = [r.getMessage() for r in caplog.records if r.name == "just_dna_enricher.download"]
    assert any(
        m.startswith(f"Pulling the Ensembl cadd group (1 file(s)) for {_NEW} under the use") for m in said
    )
    assert (
        f"Removed groups/cadd/homo_sapiens-chrMT.parquet: an earlier release's cadd file the release {_NEW} "
        "does not name."
    ) in said

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


def test_a_re_pull_under_the_recorded_use_names_that_use_and_when_it_was_declared(
    install_hub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The pm's RM437 reading 1: an operator whose use changed sees which declaration admitted the new release."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    declared_at = pulled_groups(cache)["cadd"]["declared_at"]
    install_hub(_published(1, _NEW))
    with caplog.at_level("INFO", logger="just_dna_enricher.download"):
        dl.ensure_snapshot(cache, _follow_hub=dl._FollowHub(ensembl_release_label))
    assert (
        f"under the use recorded for it, non_commercial, declared {declared_at}; this call states none"
        in caplog.text
    )
    assert pulled_groups(cache)["cadd"]["declared_at"] == declared_at, (
        "a re-pull under it does not re-declare"
    )


def test_a_re_pull_under_the_calls_own_use_records_a_new_declaration_and_says_nothing_of_the_old(
    install_hub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    first = pulled_groups(cache)["cadd"]["declared_at"]
    install_hub(_published(1, _NEW))
    with caplog.at_level("INFO", logger="just_dna_enricher.download"):
        dl.ensure_snapshot(
            cache, declared_use="non_commercial", _follow_hub=dl._FollowHub(ensembl_release_label)
        )
    assert "recorded for it" not in caplog.text
    entry = pulled_groups(cache)["cadd"]
    assert entry["release_id"] == _NEW and entry["declared_at"] >= first


def test_a_recorded_use_with_no_time_says_the_time_is_not_recorded(
    install_hub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A pull record written before 0.9's follow-up states the use and no time: the time is never invented."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    record = _record(cache)
    del record["groups"]["cadd"]["declared_at"]
    (cache / PULL_RECORD_FILENAME).write_text(json.dumps(record))
    install_hub(_published(1, _NEW))
    with caplog.at_level("INFO", logger="just_dna_enricher.download"):
        dl.ensure_snapshot(cache, _follow_hub=dl._FollowHub(ensembl_release_label))
    assert (
        "under the use recorded for it, non_commercial, declared at a time the pull record does not state"
        in caplog.text
    )
    assert "declared_at" not in pulled_groups(cache)["cadd"], "no time is written for a declaration not seen"


def test_a_group_admitted_under_no_declared_use_records_no_declaration_time(
    install_hub, tmp_path: Path
) -> None:
    """`unstated` is no declaration: the Ensembl-licensed group is pulled under it, and no time is invented."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"])
    entry = pulled_groups(cache)["consequence"]
    assert entry["declared_use"] == "unstated"
    assert "declared_at" not in entry


def test_a_skip_under_the_recorded_use_names_it_too(
    install_hub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    record = _record(cache)
    record["groups"]["cadd"]["declared_use"] = "unstated"
    record["groups"]["cadd"]["declared_at"] = "2026-11-01T00:00:00Z"
    (cache / PULL_RECORD_FILENAME).write_text(json.dumps(record))
    install_hub(_published(1, _NEW))
    with caplog.at_level("INFO", logger="just_dna_enricher.download"):
        dl.ensure_snapshot(cache, _follow_hub=dl._FollowHub(ensembl_release_label))
    assert "Ensembl group cadd: skipped — " in caplog.text
    assert "under the use recorded for it, unstated, declared 2026-11-01T00:00:00Z" in caplog.text


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


def test_a_sticky_group_that_cannot_be_fetched_does_not_sink_the_core(
    install_hub, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["consequence"])
    install_hub(
        _published(1, _NEW),
        failing={"groups/consequence/homo_sapiens-chr21.parquet": ConnectionError("reset by peer")},
    )

    with caplog.at_level("WARNING", logger="just_dna_enricher.download"):
        dl.ensure_snapshot(cache, _follow_hub=dl._FollowHub(ensembl_release_label))  # no raise

    assert ensembl_release_label(cache) == _NEW
    (said,) = [r.getMessage() for r in caplog.records if "was not re-pulled" in r.getMessage()]
    assert said.startswith(
        f"Ensembl cache at {cache}: the consequence group, selected by an earlier pull, was not re-pulled ("
    )
    assert said.endswith("); it is refused to readers until a pull succeeds.")
    assert not (cache / "groups/consequence/homo_sapiens-chr21.part").exists()
    with pytest.raises(EnsemblGroupReleaseError, match="a pull that did not finish"):
        ensembl_group_dir(cache, "consequence")
    # Named, the same failure is the caller's to see.
    with pytest.raises(
        dl.EnsemblReferenceError, match="could not be fetched .ConnectionError: reset by peer"
    ):
        dl.ensure_snapshot(cache, groups=["consequence"])


def test_an_interrupted_re_pull_still_removes_the_earlier_releases_files(install_hub, tmp_path: Path) -> None:
    """The record keeps naming the old release's files while the new pull is under way, so a resume finds them."""
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd"], declared_use="non_commercial")
    new = _published(1, _NEW, cadd_chroms=("21",))
    install_hub(new, failing={"groups/cadd/homo_sapiens-chr21.parquet": ConnectionError("reset by peer")})
    dl.ensure_snapshot(cache, _follow_hub=dl._FollowHub(ensembl_release_label))  # the group's pull breaks
    assert (cache / "groups/cadd/homo_sapiens-chrMT.parquet").exists()

    install_hub(new)
    dl.ensure_snapshot(cache)

    assert sorted(p.name for p in ensembl_group_dir(cache, "cadd").glob("*.parquet")) == [
        "homo_sapiens-chr21.parquet"
    ]
    assert pulled_groups(cache)["cadd"]["files"] == ["groups/cadd/homo_sapiens-chr21.parquet"]


def test_a_group_directory_the_manifest_does_not_attest_is_withheld_whole(
    install_hub, tmp_path: Path
) -> None:
    cache = tmp_path / "ensembl"
    published = _published(0, _OLD)
    install_hub(published)
    dl.ensure_snapshot(cache, groups=["consequence"])
    stray = cache / "groups/consequence/homo_sapiens-chr1.parquet"
    stray.write_bytes(published["groups/consequence/homo_sapiens-chr21.parquet"])
    with pytest.raises(EnsemblGroupReleaseError) as caught:
        ensembl_group_dir(cache, "consequence")
    assert "holds 1 parquet file(s) its manifest.json does not name for the group" in str(caught.value)
    assert "groups/consequence/homo_sapiens-chr1.parquet" in str(caught.value) and "move them aside" in str(
        caught.value
    )
    # The pull does not call that directory current: it is no pull's to clean, and the reader refuses it.
    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, _follow_hub=follow)
    assert follow.groups["consequence"].startswith("current, but ")
    assert "readers refuse the group until they are moved aside" in follow.groups["consequence"]
    assert stray.exists()
    stray.unlink()
    (cache / "groups/consequence/homo_sapiens-chrMT.parquet").unlink()
    with pytest.raises(EnsemblGroupReleaseError) as caught:
        ensembl_group_dir(cache, "consequence")
    assert "1 file(s) its manifest.json attests are missing there or of another size" in str(caught.value)
    assert "homo_sapiens-chrMT.parquet" in str(caught.value)


def test_a_group_the_cache_release_lacks_is_checked_against_the_hubs(install_hub, tmp_path: Path) -> None:
    """A newer published release may add a group; the refusal is only the cache's when the hub cannot say."""
    cache = tmp_path / "ensembl"
    files = dict(_release(0))
    old: dict[str, bytes | str] = dict(files)
    old[SNAPSHOT_MANIFEST_FILENAME] = _manifest(files, _OLD, groups={"cadd": _CADD_LICENCE})
    install_hub(old)
    dl.ensure_snapshot(cache)
    install_hub(_published(1, _NEW))  # publishes `consequence` too

    follow = dl._FollowHub(ensembl_release_label)
    dl.ensure_snapshot(cache, groups=["consequence"], _follow_hub=follow)

    assert follow.groups == {"consequence": "pulled"}
    assert ensembl_group_dir(cache, "consequence").is_dir()


def test_a_named_groups_failure_leaves_the_other_groups_pulled_and_reported(
    install_hub, tmp_path: Path
) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd", "consequence"], declared_use="non_commercial")
    install_hub(
        _published(1, _NEW),
        failing={"groups/consequence/homo_sapiens-chr21.parquet": ConnectionError("reset by peer")},
    )
    follow = dl._FollowHub(ensembl_release_label)
    with pytest.raises(dl.EnsemblReferenceError, match="reset by peer"):
        dl.ensure_snapshot(cache, groups=["consequence"], _follow_hub=follow)
    assert follow.groups["cadd"] == "pulled"
    assert follow.groups["consequence"].startswith("FAILED — ")
    assert ensembl_group_dir(cache, "cadd").is_dir()


def test_no_group_is_pulled_beside_a_core_nothing_attests_is_finished(install_hub, tmp_path: Path) -> None:
    cache = tmp_path / "ensembl"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache)
    (cache / PULL_RECORD_FILENAME).unlink()  # pulled before the record, say
    hub = install_hub(_published(0, _OLD))
    hub.listing_down = True  # the core is served as it is, unverified
    with pytest.raises(
        dl.EnsemblReferenceError, match="is not a finished pull its manifest.json attests whole"
    ):
        dl.ensure_snapshot(cache, groups=["consequence"])
    assert not (cache / "groups").exists()


def test_cache_prepare_re_pulls_a_recorded_group_under_its_own_declaration(install_hub, base: Path) -> None:
    """`cache prepare --use commercial` may not take CADD under the research use recorded beside it."""
    cache = base / "ensembl_variations"
    install_hub(_published(0, _OLD))
    dl.ensure_snapshot(cache, groups=["cadd", "consequence"], declared_use="non_commercial")
    install_hub(_published(1, _NEW))

    caches.prepare_caches([LANES_BY_NAME["ensembl"]], declared_use="commercial")

    assert ensembl_group_dir(cache, "consequence").is_dir()
    with pytest.raises(EnsemblGroupReleaseError, match=f"is release {_OLD} and the core beside it is {_NEW}"):
        ensembl_group_dir(cache, "cadd")


# ── `cache pull --groups` ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def base(monkeypatch, tmp_path: Path) -> Path:
    """A cache base of the test's own, with every lane resolving to its default directory under it."""
    root = tmp_path / "cache-base"
    monkeypatch.setenv(CACHE_BASE_VAR, str(root))
    for lane in caches.CACHE_LANES:
        monkeypatch.setenv(lane.env_var, "")  # set, never deleted (`@test-no-credential`)
    return root


def _pull(*args: str):
    return CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "ensembl", *args])


def test_cache_pull_refuses_cadd_under_a_commercial_use(install_hub, base: Path, cli_text) -> None:
    hub = install_hub(_published(0, _OLD))
    result = _pull("--groups", "cadd", "--use", "commercial")
    assert result.exit_code == 1, cli_text(result)
    assert "ensembl: REFUSED — cadd is CADD terms of use (University of Washington) and its terms forbid" in (
        cli_text(result)
    )
    assert hub.parquet_fetched() == [] and not (base / "ensembl_variations").exists()


def test_cache_pull_takes_cadd_under_a_research_use(install_hub, base: Path, cli_text) -> None:
    install_hub(_published(0, _OLD))
    result = _pull("--groups", "cadd,consequence", "--use", "non-commercial")
    assert result.exit_code == 0, cli_text(result)
    assert "ensembl group cadd: pulled" in cli_text(result)
    assert "ensembl group consequence: pulled" in cli_text(result)
    cache = base / "ensembl_variations"
    assert ensembl_group_dir(cache, "cadd").is_dir() and ensembl_group_dir(cache, "consequence").is_dir()
    assert pulled_groups(cache)["cadd"]["declared_use"] == "non_commercial"


def test_cache_pull_skips_cadd_when_no_use_is_declared(install_hub, base: Path, cli_text) -> None:
    install_hub(_published(0, _OLD))
    result = _pull("--groups", "cadd")
    assert result.exit_code == 0, cli_text(result)
    assert "ensembl group cadd: skipped — cadd forbids sale and no use was declared" in cli_text(result)
    assert not (base / "ensembl_variations" / "groups").exists()


def test_a_plain_cache_pull_reports_the_recorded_groups_it_re_pulled(
    install_hub, base: Path, cli_text
) -> None:
    install_hub(_published(0, _OLD))
    assert _pull("--groups", "cadd", "--use", "non-commercial").exit_code == 0
    install_hub(_published(1, _NEW))
    result = _pull()
    assert result.exit_code == 0, cli_text(result)
    assert "ensembl group cadd: pulled" in cli_text(result)
    assert ensembl_group_dir(base / "ensembl_variations", "cadd").is_dir()


def test_cache_pull_reports_every_group_when_a_named_one_fails(install_hub, base: Path, cli_text) -> None:
    install_hub(_published(0, _OLD))
    assert _pull("--groups", "cadd,consequence", "--use", "non-commercial").exit_code == 0
    install_hub(
        _published(1, _NEW),
        failing={"groups/consequence/homo_sapiens-chr21.parquet": ConnectionError("reset by peer")},
    )
    result = _pull("--groups", "consequence")
    assert result.exit_code == 1, cli_text(result)
    assert "ensembl: FAILED — " in cli_text(result)
    assert "ensembl group consequence: FAILED — " in cli_text(result)
    assert "ensembl group cadd: pulled" in cli_text(result)


@pytest.mark.parametrize(
    ("args", "refusal"),
    [
        (["--only", "ensembl", "--groups", "core"], CORE_IS_NOT_A_GROUP),
        (["--only", "ensembl", "--groups", "cadd,core"], CORE_IS_NOT_A_GROUP),
        (["--only", "clinvar", "--groups", "cadd"], GROUPS_NEED_ENSEMBL_ONLY),
        (["--only", "ensembl", "--only", "clinvar", "--groups", "cadd"], GROUPS_NEED_ENSEMBL_ONLY),
        (["--groups", "cadd"], GROUPS_NEED_ENSEMBL_ONLY),
    ],
)
def test_cache_pull_refuses_a_group_selection_before_any_lane_runs(
    monkeypatch, base: Path, cli_text, args: list[str], refusal: str
) -> None:
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", _explode)
    exploding = [
        dataclasses.replace(lane, ensure=lambda **_: pytest.fail("a lane ran")) if lane.ensure else lane
        for lane in caches.CACHE_LANES
    ]
    monkeypatch.setattr(cache_commands, "CACHE_LANES", exploding)
    result = CliRunner().invoke(enricher_app, ["cache", "pull", *args])
    assert result.exit_code == 2, cli_text(result)
    assert refusal in cli_text(result)
    assert not base.exists()
