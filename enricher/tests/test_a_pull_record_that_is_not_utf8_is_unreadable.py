"""A pull record that is not UTF-8 reads as unreadable in every reader, never as a traceback (RM455).

Every reader of `pull-record.json` caught `JSONDecodeError` and not `UnicodeDecodeError`, so a record
whose bytes are not UTF-8 escaped `download._pull_record`, `locations.pull_record_repo` (and through it
`pulled_from`) and `locations.snapshot_record_missing` as a traceback instead of taking the reader's own
unreadable arm. 0.9 fixed its own instance (`pulled_groups`, review round 1 item 3); these are the older
ones on `main`.
"""

import json
import logging
from pathlib import Path

import pytest
from just_dna_enricher.download import _pull_record
from just_dna_enricher.locations import (
    PULL_RECORD_FILENAME,
    pull_record_repo,
    pulled_from,
    snapshot_record_missing,
)

_REPO = "datasets/someone/a-snapshot"


def _write_record(cache_dir: Path, raw: bytes) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / PULL_RECORD_FILENAME).write_bytes(raw)


def _readable(cache_dir: Path) -> None:
    _write_record(cache_dir, json.dumps({"repo": _REPO, "files": []}).encode("utf-8"))


def _not_utf8(cache_dir: Path) -> None:
    # Latin-1 bytes for a repo name with an accent: valid JSON in that encoding, invalid UTF-8.
    _write_record(cache_dir, '{"repo": "datasets/caf\xe9/x", "files": []}'.encode("latin-1"))


def test_the_record_used_below_is_not_utf8(tmp_path: Path) -> None:
    _not_utf8(tmp_path)
    with pytest.raises(UnicodeDecodeError):
        (tmp_path / PULL_RECORD_FILENAME).read_text(encoding="utf-8")


def test_every_reader_answers_a_readable_record(tmp_path: Path) -> None:
    # The non-vacuous half: the same readers do read a record when it is UTF-8.
    _readable(tmp_path)
    assert _pull_record(tmp_path) == {"repo": _REPO, "files": []}
    assert pull_record_repo(tmp_path) == _REPO
    assert pulled_from(tmp_path, "datasets/someone/another") == _REPO
    assert snapshot_record_missing(tmp_path) == []


def test_download_pull_record_reads_a_non_utf8_record_as_none(tmp_path: Path) -> None:
    _not_utf8(tmp_path)
    assert _pull_record(tmp_path) is None


def test_pull_record_repo_and_pulled_from_read_a_non_utf8_record_as_naming_no_repo(tmp_path: Path) -> None:
    _not_utf8(tmp_path)
    assert pull_record_repo(tmp_path) is None
    assert pulled_from(tmp_path, _REPO) is None


def test_snapshot_record_missing_reads_a_non_utf8_record_as_unrecorded_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _not_utf8(tmp_path)
    with caplog.at_level(logging.WARNING, logger="just_dna_enricher.locations"):
        assert snapshot_record_missing(tmp_path) is None
    assert any("treating the cache as unrecorded" in record.getMessage() for record in caplog.records)
