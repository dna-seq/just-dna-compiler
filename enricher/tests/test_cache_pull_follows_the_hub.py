"""`cache pull` and `cache prepare` follow the hub's release over a whole pulled cache (RM420).

Before RM420 a cache whose pull record said the pull finished was returned without reading the hub, so
once a machine had pulled a lane no later release reached it: after gnomAD 4.1.2 was published,
`cache pull --only constraint` left `gnomad_v4.1_constraint` on disk and printed it as provisioned.

Four promises, each a test here:

- a cache that **came from a pull of the lane's repo** follows the hub when the published release
  label differs, keeping a file only where the new manifest attests it;
- a cache **built on this machine** (no pull record, or a builder's record over a stale one) is left
  alone and reported with both labels, because between a build and its upload the local lane is the
  newer one;
- `enrich`'s own `ensure` call never reads the hub for a whole cache: a warm cache serves offline and
  no enrichment downloads a release mid-run;
- a hub that cannot be read serves the cache as it is.

The hub is a fake over one repo's tree that models the real transport's failed fetch honestly: it
creates the destination file and then raises (`@a-failed-fetch-is-not-a-no-op`).
"""

import dataclasses
import hashlib
import io
import json
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
from just_dna_enricher import caches
from just_dna_enricher import download as dl
from just_dna_enricher.caches import LANES_BY_NAME, RebuildRequest
from just_dna_enricher.cli import app as enricher_app
from just_dna_enricher.locations import (
    CACHE_BASE_VAR,
    PULL_RECORD_FILENAME,
    RELEASE_FILENAME,
    SNAPSHOT_MANIFEST_FILENAME,
    SNAPSHOT_REPO_IDS,
    STRCHIVE_CATALOGUE_FILENAME,
    ensembl_release_label,
    pull_record_repo,
)
from just_dna_format.snapshot import SnapshotRelease, begin_snapshot_write
from just_dna_format.snapshot import release_label as snapshot_release_label
from typer.testing import CliRunner

_OLD = "gnomad_v4.1_constraint"
_NEW = "gnomad_v4.1.2_constraint"
_CONSTRAINT = "data/gnomad_constraint.parquet"


def _parquet(genes: list[str]) -> bytes:
    buf = io.BytesIO()
    pl.DataFrame({"gene": genes, "pli": [0.5] * len(genes)}).write_parquet(buf)
    return buf.getvalue()


def _release(dataset: str) -> str:
    return json.dumps({"dataset": dataset, "source": "test"}, indent=2) + "\n"


class _Hub:
    """A fake `HfFileSystem` over one repo: `{path under the repo root: bytes}`.

    `failing` maps a path to the exception its fetch raises after creating the destination, as the
    real client does; a path the repo lacks raises `FileNotFoundError` the same way.
    """

    def __init__(self, root: str, files: dict[str, bytes | str], failing: dict[str, Exception] | None = None):
        self.root = root
        self.files = {k: v.encode() if isinstance(v, str) else v for k, v in files.items()}
        self.failing = failing or {}
        self.listed: list[str] = []
        self.fetched: list[str] = []

    def _relative(self, remote: str) -> str:
        return remote.removeprefix(f"{self.root}/")

    def ls(self, prefix: str, detail: bool = True):
        self.listed.append(prefix)
        directory = self._relative(prefix).rstrip("/")
        names = [k for k in self.files if k.rsplit("/", 1)[0] == directory and "/" in k]
        if not names:
            raise FileNotFoundError(prefix)
        return [f"{self.root}/{k}" for k in names]

    def get(self, remote: str, local: str) -> None:
        relative = self._relative(remote)
        Path(local).write_bytes(b"")  # the real client opens the destination before it asks
        if relative in self.failing:
            raise self.failing[relative]
        if relative not in self.files:
            raise FileNotFoundError(remote)
        self.fetched.append(relative)
        Path(local).write_bytes(self.files[relative])


@pytest.fixture
def install_hub(monkeypatch):
    def install(lane: str, files: dict[str, bytes | str], **kwargs) -> _Hub:
        hub = _Hub(f"datasets/{SNAPSHOT_REPO_IDS[lane]}", files, **kwargs)
        monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: hub)
        monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
        return hub

    return install


@pytest.fixture
def base(monkeypatch, tmp_path: Path) -> Path:
    """A cache base of the test's own, with every lane resolving to its default directory under it."""
    root = tmp_path / "cache-base"
    monkeypatch.setenv(CACHE_BASE_VAR, str(root))
    for lane in caches.CACHE_LANES:
        monkeypatch.setenv(lane.env_var, "")  # set, never deleted (`@test-no-credential`)
    return root


def _explode(token=None):
    raise AssertionError("the hub was read")


def _bytes_of(directory: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(directory)): p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()
    }


def _constraint_hub(install_hub, dataset: str, genes: list[str]) -> _Hub:
    return install_hub("constraint", {_CONSTRAINT: _parquet(genes), RELEASE_FILENAME: _release(dataset)})


def _pulled_at_old(install_hub) -> Path:
    """A constraint cache pulled from the lane's repo at the old release, by the provisioner itself."""
    cache = LANES_BY_NAME["constraint"].default_dir()
    _constraint_hub(install_hub, _OLD, ["OLD1"])
    dl.ensure_constraint_snapshot(cache)
    assert snapshot_release_label(cache) == _OLD and pull_record_repo(cache) is not None
    return cache


def _built_here(cache: Path, dataset: str, genes: list[str]) -> None:
    """A snapshot written the way every builder writes one: withdraw, move the bytes, describe them."""
    write = begin_snapshot_write(cache)
    (cache / "data").mkdir(parents=True, exist_ok=True)
    (cache / _CONSTRAINT).write_bytes(_parquet(genes))
    write.commit(SnapshotRelease.model_validate({"dataset": dataset, "source": "test"}))


# ── a pulled cache follows the hub ─────────────────────────────────────────────────────────────


def test_cache_pull_re_pulls_a_pulled_cache_whose_release_moved(base: Path, install_hub) -> None:
    """The motivating case: 4.1 pulled, 4.1.2 published, and the pull used to print 4.1 as on disk."""
    cache = _pulled_at_old(install_hub)
    hub = _constraint_hub(install_hub, _NEW, ["NEW1", "NEW2"])

    result = CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "constraint"])

    assert result.exit_code == 0, result.output
    assert (cache / _CONSTRAINT).read_bytes() == hub.files[_CONSTRAINT]
    assert snapshot_release_label(cache) == _NEW
    assert pull_record_repo(cache) == dl.SNAPSHOT_REPO_PREFIXES["constraint"]
    assert _OLD in result.output and _NEW in result.output
    # …and the next pull finds it current: nothing is fetched twice.
    hub = _constraint_hub(install_hub, _NEW, ["NEW1", "NEW2"])
    again = CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "constraint"])
    assert again.exit_code == 0, again.output
    assert hub.fetched == [RELEASE_FILENAME], "a current cache costs one small read, never the payload"


def test_cache_prepare_re_pulls_a_pulled_cache_whose_release_moved(base: Path, install_hub) -> None:
    cache = _pulled_at_old(install_hub)
    hub = _constraint_hub(install_hub, _NEW, ["NEW1"])

    outcome = caches.prepare_lane(LANES_BY_NAME["constraint"], RebuildRequest(out_dir=cache))

    assert (outcome.ready, outcome.route) == (True, "pulled"), outcome.detail
    assert _OLD in outcome.detail and _NEW in outcome.detail
    assert (cache / _CONSTRAINT).read_bytes() == hub.files[_CONSTRAINT]
    assert snapshot_release_label(cache) == _NEW


def test_a_two_file_lane_refetches_every_file_when_no_manifest_attests_one(
    tmp_path: Path, install_hub
) -> None:
    """Without a manifest nothing on disk can say which release a whole file is, so none is kept."""
    cache = tmp_path / "clinvar"
    names = ("data/clinvar-chr1.parquet", "data/clinvar-chr2.parquet")
    install_hub(
        "clinvar", {**{n: _parquet(["A"]) for n in names}, RELEASE_FILENAME: _release("clinvar_2026-10-01")}
    )
    dl.ensure_clinvar_snapshot(cache)
    hub = install_hub(
        "clinvar", {**{n: _parquet(["B"]) for n in names}, RELEASE_FILENAME: _release("clinvar_2026-11-01")}
    )

    follow = dl._FollowHub(LANES_BY_NAME["clinvar"].release_label)
    dl.ensure_clinvar_snapshot(cache, _follow_hub=follow)

    assert sorted(f for f in hub.fetched if f.startswith("data/")) == sorted(names)
    assert all((cache / n).read_bytes() == hub.files[n] for n in names)
    assert (follow.local, follow.published, follow.outcome) == (
        "clinvar_2026-10-01",
        "clinvar_2026-11-01",
        "refreshed",
    )


def test_an_interrupted_refresh_is_finished_by_the_next_pull(tmp_path: Path, install_hub) -> None:
    """The record is withdrawn before the first byte moves, so a refresh cut short is not current."""
    cache = tmp_path / "clinvar"
    names = ("data/clinvar-chr1.parquet", "data/clinvar-chr2.parquet")
    install_hub("clinvar", {**{n: _parquet(["A"]) for n in names}, RELEASE_FILENAME: _release("clinvar_old")})
    dl.ensure_clinvar_snapshot(cache)
    new = {**{n: _parquet(["B"]) for n in names}, RELEASE_FILENAME: _release("clinvar_new")}
    install_hub("clinvar", new, failing={names[1]: OSError("connection reset")})

    with pytest.raises(OSError):
        dl.ensure_clinvar_snapshot(cache, _follow_hub=dl._FollowHub(snapshot_release_label))
    assert snapshot_release_label(cache) is None, (
        "old bytes beside new may not stay described as the old release"
    )

    install_hub("clinvar", new)
    dl.ensure_clinvar_snapshot(cache, _follow_hub=dl._FollowHub(snapshot_release_label))
    assert snapshot_release_label(cache) == "clinvar_new"
    assert (cache / names[1]).read_bytes() == _bytes_of_hub(new, names[1])


def test_cache_prepare_reports_a_refresh_cut_short_as_a_failure(base: Path, install_hub) -> None:
    """A re-pull that began and broke is not "already provisioned": `release.json` is withdrawn by then."""
    cache = _pulled_at_old(install_hub)
    install_hub(
        "constraint",
        {_CONSTRAINT: _parquet(["NEW"]), RELEASE_FILENAME: _release(_NEW)},
        failing={_CONSTRAINT: OSError("connection reset")},
    )

    outcome = caches.prepare_lane(LANES_BY_NAME["constraint"], RebuildRequest(out_dir=cache))

    assert (outcome.ready, outcome.route) == (False, "pulled"), outcome.detail
    assert _OLD in outcome.detail and _NEW in outcome.detail


def _bytes_of_hub(files: dict[str, bytes | str], name: str) -> bytes:
    value = files[name]
    return value.encode() if isinstance(value, str) else value


# ── a lane built here survives ─────────────────────────────────────────────────────────────────


def test_a_lane_built_here_survives_cache_pull_and_the_report_names_both_labels(
    base: Path, install_hub
) -> None:
    """The pm's test: built locally, an older label published, `cache pull` twice, every byte unchanged.

    Twice, because the first pull used to write a pull record over the build (RM339's once-only
    comparison), after which nothing on disk could tell the build from a pull.
    """
    cache = LANES_BY_NAME["constraint"].default_dir()
    _built_here(cache, _NEW, ["BUILT"])
    before = _bytes_of(cache)

    for _ in range(2):
        _constraint_hub(install_hub, _OLD, ["PUBLISHED"])
        result = CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "constraint"])
        assert result.exit_code == 0, result.output
        assert _bytes_of(cache) == before
        assert _OLD in result.output and _NEW in result.output
    assert not (cache / PULL_RECORD_FILENAME).exists()


def test_cache_prepare_leaves_a_lane_built_here_alone_and_names_both_labels(base: Path, install_hub) -> None:
    cache = LANES_BY_NAME["constraint"].default_dir()
    _built_here(cache, _NEW, ["BUILT"])
    before = _bytes_of(cache)
    _constraint_hub(install_hub, _OLD, ["PUBLISHED"])

    outcome = caches.prepare_lane(LANES_BY_NAME["constraint"], RebuildRequest(out_dir=cache))

    assert (outcome.ready, outcome.route) == (True, "present"), outcome.detail
    assert _OLD in outcome.detail and _NEW in outcome.detail
    assert _bytes_of(cache) == before


def test_a_build_over_a_pulled_cache_is_not_taken_for_the_pull(base: Path, install_hub) -> None:
    """A builder pointed at the live directory leaves the old pull record behind; the build still wins.

    The record states which `release.json` the pull placed, and a builder's `commit` writes another.
    """
    cache = _pulled_at_old(install_hub)
    _built_here(cache, _NEW, ["BUILT"])
    before = _bytes_of(cache)
    _constraint_hub(install_hub, _OLD, ["PUBLISHED"])

    follow = dl._FollowHub(snapshot_release_label)
    dl.ensure_constraint_snapshot(cache, _follow_hub=follow)

    assert _bytes_of(cache) == before
    assert (follow.local, follow.published, follow.outcome) == (_NEW, _OLD, "kept")


# ── enrich never reads the hub for a whole cache; an unreadable hub serves it ────────────────────


def test_enrichs_ensure_never_reads_the_hub_for_a_whole_pulled_cache(
    base: Path, install_hub, monkeypatch
) -> None:
    cache = _pulled_at_old(install_hub)
    before = _bytes_of(cache)
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", _explode)

    assert dl.ensure_constraint_snapshot(cache) == cache
    assert _bytes_of(cache) == before


@pytest.mark.parametrize(
    "failure", [TimeoutError("read timed out"), PermissionError("401 Unauthorized")], ids=["timeout", "401"]
)
def test_an_unreadable_hub_serves_the_pulled_cache_as_it_is(
    base: Path, install_hub, failure: Exception
) -> None:
    cache = _pulled_at_old(install_hub)
    before = _bytes_of(cache)
    install_hub("constraint", {_CONSTRAINT: _parquet(["NEW"])}, failing={RELEASE_FILENAME: failure})

    result = CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "constraint"])

    assert result.exit_code == 0, result.output
    assert _bytes_of(cache) == before
    assert "could not be read" in result.output


def test_a_hub_that_states_no_release_leaves_the_cache_as_it_is(base: Path, install_hub) -> None:
    """Nothing to compare is not a difference: an unlabelled repo never sends a cache down the pull route."""
    cache = _pulled_at_old(install_hub)
    before = _bytes_of(cache)
    hub = install_hub("constraint", {_CONSTRAINT: _parquet(["NEW"])})

    follow = dl._FollowHub(snapshot_release_label)
    dl.ensure_constraint_snapshot(cache, _follow_hub=follow)

    assert _bytes_of(cache) == before and hub.listed == []
    assert (follow.local, follow.published) == (_OLD, None)


# ── the other two provisioning shapes: Ensembl's manifest label, STRchive's root file ───────────


def _manifest(files: dict[str, bytes], release_id: str) -> str:
    return json.dumps(
        {
            "release_id": release_id,
            "layout_version": 1,
            "files": [
                {
                    "path": name,
                    "group": "core",
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
                for name, body in sorted(files.items())
            ],
        }
    )


def test_the_ensembl_lane_follows_its_manifests_release_id_and_keeps_what_it_attests(
    tmp_path: Path, install_hub
) -> None:
    """Ensembl states its release only in `manifest.json`: the lane's own label, never `release.json`."""
    cache = tmp_path / "ensembl"
    same, moved = "data/homo_sapiens-chr21.parquet", "data/homo_sapiens-chrMT.parquet"
    old = {same: _parquet(["chr21"]), moved: _parquet(["MT-old"])}
    install_hub("ensembl", {**old, SNAPSHOT_MANIFEST_FILENAME: _manifest(old, "ensembl-115")})
    dl.ensure_snapshot(cache)
    assert ensembl_release_label(cache) == "ensembl-115"
    new = {same: old[same], moved: _parquet(["MT-new"])}
    hub = install_hub("ensembl", {**new, SNAPSHOT_MANIFEST_FILENAME: _manifest(new, "ensembl-116")})

    follow = dl._FollowHub(LANES_BY_NAME["ensembl"].release_label)
    dl.ensure_snapshot(cache, _follow_hub=follow)

    assert [f for f in hub.fetched if f.startswith("data/")] == [moved], "an attested file is kept"
    assert (cache / moved).read_bytes() == new[moved]
    assert ensembl_release_label(cache) == "ensembl-116"
    assert (follow.local, follow.published, follow.outcome) == ("ensembl-115", "ensembl-116", "refreshed")


def test_a_pulled_strchive_catalogue_follows_the_hub(base: Path, install_hub) -> None:
    cache = LANES_BY_NAME["strchive"].default_dir()
    install_hub(
        "strchive",
        {STRCHIVE_CATALOGUE_FILENAME: '[{"id": "OLD"}]', RELEASE_FILENAME: _release("strchive_v2.26.0")},
    )
    dl.ensure_strchive_snapshot(cache)
    hub = install_hub(
        "strchive",
        {STRCHIVE_CATALOGUE_FILENAME: '[{"id": "NEW"}]', RELEASE_FILENAME: _release("strchive_v2.28.0")},
    )

    result = CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "strchive"])

    assert result.exit_code == 0, result.output
    assert (cache / STRCHIVE_CATALOGUE_FILENAME).read_bytes() == hub.files[STRCHIVE_CATALOGUE_FILENAME]
    assert snapshot_release_label(cache) == "strchive_v2.28.0"
    assert "strchive_v2.26.0" in result.output and "strchive_v2.28.0" in result.output


def test_a_strchive_catalogue_with_no_pull_record_is_left_alone(base: Path, install_hub) -> None:
    """Every STRchive cache from before RM420 carries no record, so nothing says it was pulled."""
    cache = LANES_BY_NAME["strchive"].default_dir()
    cache.mkdir(parents=True)
    (cache / STRCHIVE_CATALOGUE_FILENAME).write_text('[{"id": "LOCAL"}]', encoding="utf-8")
    (cache / RELEASE_FILENAME).write_text(_release("strchive_v2.26.0"), encoding="utf-8")
    before = _bytes_of(cache)
    install_hub(
        "strchive",
        {STRCHIVE_CATALOGUE_FILENAME: '[{"id": "NEW"}]', RELEASE_FILENAME: _release("strchive_v2.28.0")},
    )

    result = CliRunner().invoke(enricher_app, ["cache", "pull", "--only", "strchive"])

    assert result.exit_code == 0, result.output
    assert _bytes_of(cache) == before
    assert "strchive_v2.26.0" in result.output and "strchive_v2.28.0" in result.output


def test_enrichs_ensure_never_reads_the_hub_for_a_present_catalogue(
    base: Path, install_hub, monkeypatch
) -> None:
    cache = LANES_BY_NAME["strchive"].default_dir()
    install_hub(
        "strchive", {STRCHIVE_CATALOGUE_FILENAME: '[{"id": "OLD"}]', RELEASE_FILENAME: _release("v1")}
    )
    dl.ensure_strchive_snapshot(cache)
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", _explode)
    assert dl.ensure_strchive_snapshot(cache) == cache


def test_the_three_provisioning_call_sites_pass_the_intent() -> None:
    """Only `cache pull` and `cache prepare` follow the hub; every other caller keeps the warm trust.

    Read off the source rather than trusted: a keyword a call site forgets is a pull that silently
    returns to the RM420 behaviour, and nothing else would notice.
    """
    import ast
    import inspect

    from just_dna_enricher.cli import cache_commands

    def ensure_calls(module) -> list[ast.Call]:
        tree = ast.parse(inspect.getsource(module))
        return [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ensure"
        ]

    calls = ensure_calls(caches) + ensure_calls(cache_commands)
    assert len(calls) == 3, [ast.unparse(c) for c in calls]
    assert all(any(k.arg == "_follow_hub" for k in c.keywords) for c in calls), [
        ast.unparse(c) for c in calls
    ]


def test_a_stub_lane_keeps_working(tmp_path: Path) -> None:
    """A lane whose `ensure` is a stub taking the keyword is still routed by `prepare_lane`."""
    cache = tmp_path / "present"
    (cache / "data").mkdir(parents=True)
    seen: list[object] = []

    def ensure(**kwargs) -> Path:
        seen.append(kwargs.get("_follow_hub"))
        return cache

    lane = dataclasses.replace(
        LANES_BY_NAME["clinvar"], resolve=lambda: cache, ensure=ensure, default_dir=lambda: cache
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=cache))
    assert outcome.route == "present"
    assert len(seen) == 1 and isinstance(seen[0], dl._FollowHub)
