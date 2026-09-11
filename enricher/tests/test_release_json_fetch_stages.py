"""An absent `release.json` leaves nothing behind, not a 0-byte one (RM219).

`download.py` states the rule at length and applies it everywhere but one line: *"Staged through
`.part` like every other download here, because a failed one is not a no-op. `HfFileSystem.get`
creates the local file before it discovers the remote path is missing, so fetching straight to the
real name left a 0-byte `LICENSE.txt` in the cache of every snapshot whose repo publishes none."*

`_provision_root_file_snapshot` — the STRchive lane's provisioner — staged its payload and then
fetched `release.json` straight to the target two lines later. By the module's own mechanism a repo
publishing no description left a zero-byte `release.json` in the cache.

**That turns one state into another, which is the whole cost.** An absent label is *nobody said*; a
present-and-unreadable one is *the description is corrupt*. `_json_parses` reads a 0-byte file as
unreadable and `LaneStatus` reports `release_unreadable`, so an operator was sent to re-pull a lane
whose remote simply has no `release.json` to give — `@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`,
and the same distinction `@a-failed-fetch-is-not-a-no-op` is named for.

The fake here reproduces the documented client behaviour rather than assuming it: `get` **creates the
file and then raises**, which is the only reason the bug existed. A fake that raised without touching
the filesystem would pass against the unfixed code and prove nothing.
"""

from pathlib import Path

import just_dna_enricher.download as dl
import pytest
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_enricher.strchive import STRCHIVE_CATALOGUE_FILENAME

_CATALOGUE = '{"loci": []}'


class _CreatesThenFails:
    """`HfFileSystem.get` as the module documents it: the local file appears, then the call raises.

    Serves the payload, refuses `release.json` — the shape of a repo published before the builder
    wrote descriptions, which is four of the repos this tier pulls from.
    """

    def __init__(self) -> None:
        self.attempted: list[str] = []

    def get(self, remote_path: str, local_path: str) -> None:
        name = remote_path.rstrip("/").rsplit("/", 1)[-1]
        self.attempted.append(name)
        Path(local_path).write_text("", encoding="utf-8")  # created before the remote is checked
        if name == RELEASE_FILENAME:
            raise FileNotFoundError(remote_path)
        Path(local_path).write_text(_CATALOGUE, encoding="utf-8")


@pytest.fixture
def hub(monkeypatch) -> _CreatesThenFails:
    import huggingface_hub

    fs = _CreatesThenFails()
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    return fs


def test_a_repo_without_release_json_leaves_no_file_at_all(hub: _CreatesThenFails, tmp_path: Path) -> None:
    cache = tmp_path / "strchive"

    dl.ensure_strchive_snapshot(cache)

    assert RELEASE_FILENAME in hub.attempted, "the fetch is not even attempted"
    assert not (cache / RELEASE_FILENAME).exists(), "a 0-byte release.json was left behind"
    assert not list(cache.glob("*.part")), "a staging file survived"


def test_the_payload_still_lands(hub: _CreatesThenFails, tmp_path: Path) -> None:
    """The control: refusing to leave a stub must not cost the thing the lane is for."""
    cache = tmp_path / "strchive"

    dl.ensure_strchive_snapshot(cache)

    assert (cache / STRCHIVE_CATALOGUE_FILENAME).read_text(encoding="utf-8") == _CATALOGUE


def test_a_repo_that_has_one_still_gets_it(monkeypatch, tmp_path: Path) -> None:
    """And the happy path is unchanged — staging is not skipping."""
    import huggingface_hub

    body = '{"release": "2026-09-01"}'

    class _Serves(_CreatesThenFails):
        def get(self, remote_path: str, local_path: str) -> None:
            name = remote_path.rstrip("/").rsplit("/", 1)[-1]
            self.attempted.append(name)
            Path(local_path).write_text(body if name == RELEASE_FILENAME else _CATALOGUE, encoding="utf-8")

    fs = _Serves()
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    cache = tmp_path / "strchive"

    dl.ensure_strchive_snapshot(cache)

    assert (cache / RELEASE_FILENAME).read_text(encoding="utf-8") == body
    assert not list(cache.glob("*.part"))
