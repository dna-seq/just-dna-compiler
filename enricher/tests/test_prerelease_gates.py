"""The prerelease gates over the cache lanes: stage parity, idempotency, and the published release (RM413).

The maintainer, 2026-11-07, after 0.8.0 shipped the Open Targets lane with a builder and no repository:
"Add a prerelease checks: idempotency check (on the interfaces expected to be such) and cli-parity for all
these build/publish/download. ... No hf publish thus blocks release."

Three gates, each walked over the registry or the Typer tree rather than a list:

- **Parity**: a lane this tier publishes can be pulled, a lane that can be pulled is published by
  someone, and a lane that publishes nothing names what bars it. "No repository yet" is not a bar, and
  that sentence is what Open Targets' `unpublished` said for a whole release.
- **Idempotency**: the commands that promise to change nothing (`cache status`, `cache rebuild
  --dry-run`, every `publish --dry-run`) leave the disk as it was and say the same thing twice.
- **Published**: every lane with a repository states a release there. Network, so it runs under
  `JUST_DNA_NETWORK_TESTS=1` at the cut (RELEASE_CYCLE step 9), where a red blocks the cut.
"""

import json
from pathlib import Path

import huggingface_hub
import polars as pl
import pytest
import typer
from just_dna_enricher.caches import CACHE_LANES
from just_dna_enricher.cli import app
from just_dna_enricher.cli.cache_commands import _published_release
from just_dna_enricher.locations import RELEASE_FILENAME
from typer.testing import CliRunner

#: What may keep a lane this tier builds off the hub, as the first word of its `unpublished` reason.
#: Each is a fact about the source or the snapshot: terms that refuse it, terms nobody has established,
#: or a snapshot derived from other caches whose pins a pulled copy could not check. A missing
#: repository is none of them; it is work not done.
_BARS = ("refused:", "unestablished:", "derived,")


# ── parity ─────────────────────────────────────────────────────────────────────────────────────


def test_a_lane_that_publishes_nothing_names_what_bars_it() -> None:
    """Open Targets said "not yet published: ... no repository holds one" from 0.8.0 to RM408.

    A lane this tier does not build (Ensembl, cut by prepare-annotations) is published elsewhere and
    pulled here, so it owes no bar.
    """
    unbarred = {
        lane.name: lane.unpublished
        for lane in CACHE_LANES
        if lane.publish_repo is None
        and (lane.rebuild is not None or lane.build_command is not None)
        and not (lane.unpublished or "").startswith(_BARS)
    }
    assert unbarred == {}, (
        f"these lanes are built here and published nowhere without a stated bar ({', '.join(_BARS)}): "
        f"{unbarred}. Give the lane a repository in locations.SNAPSHOT_REPO_IDS and an ensure, or name the bar."
    )


def test_a_published_lane_can_be_pulled_and_a_pulled_lane_is_published_by_someone() -> None:
    """Publish without pull strands the bytes; pull without publish asks a repo nobody fills."""
    for lane in CACHE_LANES:
        if lane.publish_repo is not None:
            assert lane.ensure is not None, (
                f"{lane.name} publishes to {lane.publish_repo} and cannot be pulled"
            )
        if lane.ensure is not None and lane.publish_repo is None:
            assert lane.rebuild is None and lane.build_command is None, (
                f"{lane.name} can be pulled and is built here, but this tier publishes it nowhere"
            )


def _publish_commands() -> dict[str, object]:
    """Every command whose name starts with `publish`, walked off the real Typer tree by its path.

    By shape, never `isinstance(…, click.Group)`: Typer's vendored click is not the `click` a test
    imports, so the check is always False and the walk finds nothing (CLAUDE.md, the docs-site line).
    """
    found: dict[str, object] = {}

    def walk(command, path: tuple[str, ...]) -> None:
        if hasattr(command, "commands"):
            for name, child in command.commands.items():
                walk(child, (*path, name))
        elif path and path[-1].startswith("publish"):
            found[" ".join(path)] = command

    walk(typer.main.get_command(app), ())
    return found


def test_every_publish_command_has_a_dry_run_unless_it_only_refuses() -> None:
    """A publish route an operator cannot rehearse is the CLI half of parity.

    `pubmind publish` takes nothing: it exists to say why PubMind is never published.
    """
    commands = _publish_commands()
    assert commands, "the walk found no publish command"
    for path, command in commands.items():
        names = {opt for param in command.params for opt in getattr(param, "opts", [])}
        assert "--dry-run" in names or not command.params, f"`{path}` publishes and has no --dry-run"


# ── idempotency ────────────────────────────────────────────────────────────────────────────────


class _Hub:
    """A hub where every repo-root `release.json` states one label and every repo is empty otherwise."""

    def get(self, remote: str, local: str) -> None:
        if not remote.endswith(RELEASE_FILENAME):
            raise FileNotFoundError(remote)
        Path(local).write_text(json.dumps({"dataset": "published_label"}), encoding="utf-8")

    def ls(self, prefix: str, detail: bool = True):
        raise FileNotFoundError(prefix)


class _Api:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def list_repo_files(self, repo_id: str, repo_type: str | None = None, revision: str | None = None):
        return []


@pytest.fixture
def quiet_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: _Hub())
    monkeypatch.setattr(huggingface_hub, "HfApi", _Api)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    monkeypatch.setenv("HF_TOKEN", "")


def _tree(*roots: Path) -> dict[str, tuple[int, float]]:
    return {
        str(path): (path.stat().st_size, path.stat().st_mtime)
        for root in roots
        if root.exists()
        for path in root.rglob("*")
    }


def _twice(argv: list[str], *roots: Path) -> None:
    """Run `argv` twice: the disk is unchanged by either run and the two runs say the same thing."""
    before = _tree(*roots)
    first = CliRunner().invoke(app, argv)
    after_first = _tree(*roots)
    second = CliRunner().invoke(app, argv)
    assert after_first == before, f"`{' '.join(argv)}` wrote: {sorted(set(after_first) ^ set(before))}"
    assert _tree(*roots) == before
    assert (first.exit_code, first.output) == (second.exit_code, second.output), (
        f"`{' '.join(argv)}` is not stable"
    )


def test_cache_status_changes_nothing(quiet_hub, no_ambient_caches: Path, tmp_path: Path) -> None:
    _twice(["cache", "status"], no_ambient_caches, tmp_path)


def test_a_dry_run_rebuild_of_every_lane_changes_nothing(
    quiet_hub, no_ambient_caches: Path, tmp_path: Path
) -> None:
    """Every lane at once, with the publish rehearsal: RM411 made this read-only, this keeps it so."""
    out = tmp_path / "caches"
    _twice(["cache", "rebuild", "--out", str(out), "--publish", "--dry-run"], out, no_ambient_caches)
    assert not out.exists()


@pytest.mark.parametrize("path", sorted(_publish_commands()))
def test_every_publish_dry_run_changes_nothing(
    quiet_hub, no_ambient_caches: Path, tmp_path: Path, path: str
) -> None:
    """Against a minimal built snapshot. Whether the rehearsal accepts it is not the question here;
    that it reads, writes nothing and answers the same twice is."""
    command = _publish_commands()[path]
    if not command.params:
        _twice(path.split(), tmp_path)
        return
    snapshot = tmp_path / "snapshot"
    (snapshot / "data").mkdir(parents=True)
    pl.DataFrame({"variant_key": ["1:1:A:G"]}).write_parquet(snapshot / "data" / "table.parquet")
    (snapshot / RELEASE_FILENAME).write_text(json.dumps({"dataset": "local_label"}), encoding="utf-8")
    _twice([*path.split(), str(snapshot), "--dry-run"], tmp_path)


# ── the published release: a red blocks the cut ────────────────────────────────────────────────


@pytest.mark.network
@pytest.mark.parametrize(
    "lane", [lane for lane in CACHE_LANES if lane.publish_repo is not None], ids=lambda lane: lane.name
)
def test_every_lane_with_a_repository_states_a_published_release(lane) -> None:
    """The gate 0.8.0 lacked: a release that names a lane with a repository nobody has filled.

    *Could not ask* fails too: the cut cannot be shown safe on a hub that did not answer.
    """
    published = _published_release(lane.publish_repo)
    assert not published.startswith(("nothing published", "could not ask", "a release.json stating")), (
        f"{lane.name}: {lane.publish_repo} answers {published!r}. Publish the lane before the cut "
        f"(`cache rebuild --only {lane.name} --publish`, on the pm's sign-off) or take its repository away."
    )
