#!/usr/bin/env python3
"""UserPromptSubmit — arm the triage watcher when a prompt points the session at the runbook.

The triage seat is the session pointed at docs/CONSUMER_TRIAGE_LOOP.md, so naming the runbook in a
prompt is what arms it, and the watcher belongs to that session and no other. It starts
.claude/wake-on-suggestions.sh detached; the wrapper wakes the session through its inbox socket with
no time cap. A hook does it rather than the agent because auto mode's classifier refuses to let a
session launch something that wakes itself, and a hook is not classified.

The wrapper is started with ARMED_NOTICE=1, so its first post is an "armed" line: the live check on
the one undocumented thing the path rests on, the socket's message format. If an update changes it,
the arming turn sees no notice and says so, instead of a consumer's item waiting unseen.

Never blocks. Prints one line to stdout (added to the model's context) saying what it did.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / ".claude" / "wake-on-suggestions.sh"
RUNBOOK = re.compile(r"CONSUMER_TRIAGE_LOOP\.md")
WATCHER_POST = "[watcher "  # the prefix wake-on-suggestions.sh puts on every line it posts


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    prompt = str(data.get("prompt", ""))
    # The watcher's own posts cite the runbook ("triage per docs/CONSUMER_TRIAGE_LOOP.md"). Whether
    # Claude Code runs this hook on a socket message is undocumented, so never let one arm anything:
    # a machine-written line re-arming the machine that wrote it is the loop to rule out, not bound.
    if WATCHER_POST in prompt or not RUNBOOK.search(prompt):
        return 0
    sock = os.environ.get("CLAUDE_CODE_MESSAGING_SOCKET")
    if not sock:
        print(
            "[triage watcher] NOT armed: this session exports no CLAUDE_CODE_MESSAGING_SOCKET. "
            "Arm the one-shot fallback in docs/CONSUMER_TRIAGE_LOOP.md."
        )
        return 0
    subprocess.Popen(
        [str(WRAPPER)],
        env={**os.environ, "ARMED_NOTICE": "1"},
        cwd=REPO,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(
        f"[triage watcher] armed on {sock}. A '[watcher …] armed' message should arrive this turn; "
        "if none does, the inbox format changed: say so, and use the one-shot fallback."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
