"""Shared helpers for the Constitution-read gate hooks.

The gate enforces the CLAUDE.md rule "READ docs/CONSTITUTION.md IN FULL before
judging or changing anything" for the two actions the maintainer named: recording
an RM class/severity (an edit to ROADMAP*/RM_TOC) and editing the schema tier.

The marker is per-session (keyed on the hook's session_id) and is set only by a
*full* Read of the charter — a grep (a different tool) or a narrow line-range Read
does not satisfy it, matching the "whole-file Read first" rule.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

CHARTER_SUFFIX = "docs/CONSTITUTION.md"

# Edits to these require the charter to have been read this session.
GATED_PATTERNS = (
    re.compile(r"(^|/)schema/src/"),  # schema tier
    re.compile(r"(^|/)docs/ROADMAP(_[0-9_]+)?\.md$"),  # open-RM processing + class/severity
    re.compile(r"(^|/)docs/RM_TOC\.md$"),  # RM status/class index
)

# Prompt intents that should trigger the early nudge.
INTENT = re.compile(
    r"\bRM\s?\d|\bRMn?\b|severit|classif|\bclass(es|ify|ification)?\b|triage|"
    r"\bschema\b|proposal|principle|\bP[378]\b|legal(ity)?|roadmap|open item|parked",
    re.IGNORECASE,
)


def load_input() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def marker_path(data: dict) -> Path:
    session = str(data.get("session_id") or "nosession")
    session = re.sub(r"[^A-Za-z0-9_-]", "_", session)
    return Path(tempfile.gettempdir()) / f"jdf-charter-read-{session}"


def charter_read(data: dict) -> bool:
    return marker_path(data).exists()


def is_full_charter_read(tool_input: dict) -> bool:
    fp = str(tool_input.get("file_path", ""))
    if not fp.endswith(CHARTER_SUFFIX):
        return False
    offset = tool_input.get("offset")
    limit = tool_input.get("limit")
    if offset not in (None, 0, 1):
        return False  # started mid-file — a range read, not the whole chapter
    if limit is not None and limit < 190:  # charter is 198 lines
        return False
    return True


def is_gated_edit(tool_input: dict) -> bool:
    fp = str(tool_input.get("file_path", ""))
    return any(p.search(fp) for p in GATED_PATTERNS)
