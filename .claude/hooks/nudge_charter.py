#!/usr/bin/env python3
"""UserPromptSubmit — inject an early reminder on RM/schema-intent prompts.

If the prompt looks like RM triage, class/severity assignment, or schema work and
the charter has not been read this session, print a one-line reminder to stdout
(added to the model's context). Never blocks; stays silent once the charter is read.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from charter_gate_lib import INTENT, charter_read, load_input  # noqa: E402


def main() -> int:
    data = load_input()
    if charter_read(data):
        return 0
    prompt = str(data.get("prompt", ""))
    if INTENT.search(prompt):
        print(
            "[charter gate] docs/CONSTITUTION.md has not been read in full this "
            "session. Before assigning an RM class/severity or editing schema/src, "
            "Read docs/CONSTITUTION.md IN FULL — the PreToolUse gate will block those "
            "edits until you do."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
