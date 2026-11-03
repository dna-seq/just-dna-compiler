"""Where the triage scripts find a repository's documents (#242): each setting from the environment, else from
the clone's `.blueprints.toml` table `[triage]`, else the default. A path in the table is relative to the clone's
root, so a repository whose inbox and index have their own names writes them once there and every seat runs the
scripts bare:

    [triage]
    inbox = "docs/REPORTS.md"        # INBOX      (default docs/FEEDBACK.md)
    history = "docs/REPORTS_DONE.md" # HISTORY    (default beside the inbox, <stem>_HISTORY.md)
    prefix = "S"                     # PREFIX
    index = "docs/ITEMS.md"          # INDEX      (default docs/ROADMAP.md)
    scan_dir = "docs"                # SCAN_DIR   (default the index's folder)
    item_prefix = "RM"               # ITEM_PREFIX
    anchor = "## Open"               # ANCHOR

The clone is the working directory's, at its main worktree: these scripts run from the kit's copy, so their own
location says nothing about the repository they serve (RM2), and the inbox a reporter leaves uncommitted, and the
watcher reads, is the shared checkout's, never a linked worktree's committed copy. A `.blueprints.toml` that cannot
be read is refused, never taken for an empty table.
"""
from __future__ import annotations

import functools
import os
import pathlib
import subprocess
import sys
import tomllib

KEYS = {"INBOX": "inbox", "HISTORY": "history", "PREFIX": "prefix", "INDEX": "index", "SCAN_DIR": "scan_dir",
        "ITEM_PREFIX": "item_prefix", "ANCHOR": "anchor"}


def _prog() -> str:
    return pathlib.Path(sys.argv[0]).name


@functools.cache
def clone_root() -> pathlib.Path | None:
    """The main worktree of the working directory's clone; None outside one."""
    r = subprocess.run(["git", "worktree", "list", "--porcelain"], capture_output=True, text=True)
    first = r.stdout.splitlines()[0] if r.returncode == 0 and r.stdout else ""
    return pathlib.Path(first[len("worktree "):]) if first.startswith("worktree ") else None


@functools.cache
def table() -> dict:
    """The clone's `[triage]` table, {} where the clone or its `.blueprints.toml` has none."""
    root = clone_root()
    f = root / ".blueprints.toml" if root else None
    if f is None or not f.is_file():
        return {}
    try:
        got = tomllib.loads(f.read_text()).get("triage", {})
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        sys.exit(f"{_prog()}: {f} could not be read ({e}), so where the triage documents are is unknown: fix it, "
                 "or set the paths in the environment")
    if not isinstance(got, dict):
        sys.exit(f"{_prog()}: {f}'s triage is not a table")
    return got


def source(var: str) -> str:
    """Where VAR's value comes from, for a refusal or a line that names the file it read or wrote."""
    if os.environ.get(var):
        return f"from the environment's {var}"
    if KEYS[var] in table():
        return f"from .blueprints.toml [triage] {KEYS[var]}"
    return f"the default; set {var} or .blueprints.toml [triage] {KEYS[var]}"


def text(var: str, default: str) -> str:
    """A setting that is not a path: the environment's, the table's, or DEFAULT."""
    got = os.environ.get(var) or table().get(KEYS[var])
    return str(got) if got else default


def path(var: str, default: str | None) -> pathlib.Path | None:
    """A path setting, resolved: the environment's as given, the table's against the clone's root, else DEFAULT
    (a path under the clone's root, or None for one the caller derives). None outside a clone with neither."""
    if os.environ.get(var):
        return pathlib.Path(os.environ[var]).resolve()
    root = clone_root()
    got = table().get(KEYS[var])
    if got:
        return (root / str(got)).resolve() if root else None
    return (root / default).resolve() if root and default else None


def need(p: pathlib.Path | None, var: str) -> pathlib.Path:
    """P, or a refusal naming VAR when it could not be found: outside a clone, with VAR unset."""
    if p is None:
        sys.exit(f"{_prog()}: not in a git clone, and {var} is not set: run it in the repository, or set it")
    return p
