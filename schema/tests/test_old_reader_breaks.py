"""The upgrade note lists the closed members that a reader of the last release rejects."""

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = Path("schema/src/just_dna_format")
_TAG = "v0.9.0"


def _vocabularies(source: Path) -> dict[str, list[str]]:
    reader = Path(__file__).with_name("closed_vocabularies.py")
    output = subprocess.check_output(
        [sys.executable, reader], env={**os.environ, "PYTHONPATH": str(source)}, text=True
    )
    return json.loads(output)


def _new_closed_members(tmp_path: Path, git_output: Callable[..., str | None]) -> set[tuple[str, str]]:
    # Load the tag's own dependencies too: several sets are derived from another module.
    listing = git_output("ls-tree", "-r", "--name-only", _TAG, "--", str(_PACKAGE))
    assert listing
    for path in map(Path, listing.splitlines()):
        if path.suffix == ".py":
            source = git_output("show", f"{_TAG}:{path}")
            assert source is not None
            target = tmp_path / path.relative_to(_PACKAGE.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
    old = _vocabularies(tmp_path)
    now = _vocabularies(_ROOT / _PACKAGE.parent)
    return {
        (name, member)
        for name, members in now.items()
        for member in set(members).difference(old.get(name, ()))
    }


def test_upgrade_note_lists_new_closed_members(
    tmp_path: Path, git_output: Callable[..., str | None], release_tags: list[str]
) -> None:
    if _TAG not in release_tags:
        pytest.skip("no full history with v0.9.0 here; nothing to measure")
    new = _new_closed_members(tmp_path, git_output)
    note = (_ROOT / "docs/INTEGRATION_0_10.md").read_text(encoding="utf-8")
    section = note.split("# Old-reader breaks\n", 1)[1].split("\n#", 1)[0]
    rows = re.findall(r"^\| (.+?) \| `([^`\n]+)` \|$", section, re.MULTILINE)
    declared = {(name, member) for labels, member in rows for name in re.findall(r"`(\w+)`", labels)}
    assert new == declared
