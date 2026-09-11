"""A pull fetches every root file the registry names, not a pair somebody typed twice (RM209).

**The publish half walked `locations.SNAPSHOT_ROOT_FILENAMES`; the pull half did not.** It iterated
`(RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME)` inline, so when RM198 added `avi_knots.parquet` to the
registry the upload started sending it and the download never asked for it. The AVI lane stores no
`PHRED` — `avi_knots.parquet` is the 466 KB curve that reconstructs it — and `alphagenome check`
refuses a snapshot without that file. So `cache pull alphagenome_avi` produced a lane that could not
be used, and the two docstrings over that code said the opposite in as many words: the file "travels
because `SNAPSHOT_ROOT_FILENAMES` names it, not because this function does".

That is the defect shape rather than the count: a registry with a hand-kept copy of itself beside it
(`@registry-completeness`). So the assertion here is an **equality over the walked set** — the names
the provisioner asks the remote for, against the tuple — and not "it also asked for the knots file",
which would pass again the next time the registry grows by one.

The fake is deliberately permissive about what the remote *holds*: it serves every root name, and the
test is about which ones were **asked for**. A provisioner that asks and is refused is correct
behaviour (absence is not an error, and four published repos carry no `LICENSE.txt`); one that never
asks cannot discover the file exists.
"""

from pathlib import Path

import just_dna_enricher.download as dl
import pytest
from just_dna_enricher.locations import SNAPSHOT_ROOT_FILENAMES


class _RootRecordingFS:
    """Serves one parquet under `data/` and every repo-root file, recording what was requested."""

    def __init__(self) -> None:
        self.root_requests: list[str] = []

    def ls(self, prefix: str, detail: bool = True):
        if prefix.rstrip("/").rsplit("/", 1)[-1] != "data":
            raise FileNotFoundError(prefix)
        return [f"{prefix}/alphagenome_avi-chr1.parquet"]

    def get(self, remote_path: str, local_path: str) -> None:
        parts = remote_path.rstrip("/").split("/")
        name = parts[-1]
        if parts[-2] == "data":
            Path(local_path).write_bytes(_PARQUET)
            return
        self.root_requests.append(name)
        Path(local_path).write_bytes(b"root-file")


def _parquet_bytes() -> bytes:
    import io

    import polars as pl

    buf = io.BytesIO()
    pl.DataFrame({"raw_score": [1]}).write_parquet(buf)
    return buf.getvalue()


_PARQUET = _parquet_bytes()


@pytest.fixture
def recording_fs(monkeypatch) -> _RootRecordingFS:
    import huggingface_hub

    fs = _RootRecordingFS()
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
    return fs


def test_a_pull_asks_for_every_root_file_the_registry_names(
    recording_fs: _RootRecordingFS, tmp_path: Path
) -> None:
    dl.ensure_alphagenome_avi_snapshot(tmp_path / "avi")

    assert set(recording_fs.root_requests) == set(SNAPSHOT_ROOT_FILENAMES), (
        f"the pull half and the registry disagree: {set(recording_fs.root_requests) ^ set(SNAPSHOT_ROOT_FILENAMES)}"
    )


def test_the_knots_file_lands_in_the_cache_root(recording_fs: _RootRecordingFS, tmp_path: Path) -> None:
    """The lane-specific consequence, stated separately from the general rule above.

    Named rather than derived on purpose: this one file is what makes the AVI lane *usable*, so it
    earns an assertion a reader can find by grepping the filename after `alphagenome check` refuses.
    """
    cache = tmp_path / "avi"
    dl.ensure_alphagenome_avi_snapshot(cache)

    assert (cache / "avi_knots.parquet").is_file()
    assert (cache / "data" / "alphagenome_avi-chr1.parquet").is_file()


def test_a_repo_missing_a_root_file_still_provisions(monkeypatch, tmp_path: Path) -> None:
    """Absence is not an error — the old behaviour for `release.json`, kept for every root name."""
    import huggingface_hub

    class _NoRootFiles(_RootRecordingFS):
        def get(self, remote_path: str, local_path: str) -> None:
            parts = remote_path.rstrip("/").split("/")
            if parts[-2] == "data":
                Path(local_path).write_bytes(_PARQUET)
                return
            self.root_requests.append(parts[-1])
            raise FileNotFoundError(remote_path)

    fs = _NoRootFiles()
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)

    cache = tmp_path / "avi"
    dl.ensure_alphagenome_avi_snapshot(cache)

    assert (cache / "data" / "alphagenome_avi-chr1.parquet").is_file()
    # Asked for all of them, got none, and left no truncated stubs behind — the `.part` staging rule.
    assert set(fs.root_requests) == set(SNAPSHOT_ROOT_FILENAMES)
    assert not any((cache / name).exists() for name in SNAPSHOT_ROOT_FILENAMES)
    assert not list(cache.glob("*.part"))
