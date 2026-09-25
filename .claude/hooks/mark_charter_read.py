#!/usr/bin/env python3
"""PostToolUse:Read — mark the charter read for this session on a full Read.

Sets the per-session marker only when docs/CONSTITUTION.md was Read in full
(no offset, no narrowing limit). Always exits 0 — this hook never blocks.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from charter_gate_lib import is_full_charter_read, load_input, marker_path  # noqa: E402


def main() -> int:
    data = load_input()
    if data.get("tool_name") == "Read" and is_full_charter_read(data.get("tool_input", {})):
        try:
            marker_path(data).touch()
        except OSError:
            pass  # a marker we cannot write just means the gate stays closed — safe
    return 0


if __name__ == "__main__":
    sys.exit(main())
