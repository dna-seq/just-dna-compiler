#!/usr/bin/env python3
"""PreToolUse:Edit|Write|MultiEdit — block gated edits until the charter is read.

Blocks (exit 2) an edit to schema/src/** or docs/ROADMAP*.md / docs/RM_TOC.md when
docs/CONSTITUTION.md has not been Read in full this session. Everything else passes.
Exit 2 feeds the stderr text back to the model as the reason.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from charter_gate_lib import charter_read, is_gated_edit, load_input  # noqa: E402


def main() -> int:
    data = load_input()
    tool_input = data.get("tool_input", {})
    if is_gated_edit(tool_input) and not charter_read(data):
        fp = tool_input.get("file_path", "the target")
        sys.stderr.write(
            "BLOCKED by the charter gate: this edit records an RM class/severity or "
            "changes the schema tier, and docs/CONSTITUTION.md has not been read in "
            f"full this session.\nRead docs/CONSTITUTION.md IN FULL (a plain Read of the "
            "whole file — not a grep, not a line range) before editing "
            f"{fp}. Principles 3/7/8 decide whether the change is even legal.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
