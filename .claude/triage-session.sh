#!/usr/bin/env bash
# Starts the triage seat: a Claude Code session that the consumer inbox can wake unattended.
#
# Two things the repo's own settings cannot do, so they ride in on --settings, which scopes
# them to this one session and no other seat:
#   - crossSessionInbound=accept. A session that bypasses prompts holds every message posted
#     to its inbox socket for approval, and a repo setting may only tighten this value, never
#     loosen it. Only user settings or the --settings flag can say accept.
#   - a SessionStart hook that arms .claude/wake-on-suggestions.sh. Hooks receive the session's
#     $CLAUDE_CODE_MESSAGING_SOCKET, and a hook is not subject to auto mode's classifier. It
#     re-fires on /clear and on resume, and the watcher is a newest-wins singleton, so re-arming
#     replaces the old watcher rather than adding one.
#
#   .claude/triage-session.sh [extra claude args...]
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"

settings=$(python3 -c '
import json, sys
arm = f"setsid -f {sys.argv[1]}/.claude/wake-on-suggestions.sh >/dev/null 2>&1"
print(json.dumps({
    "crossSessionInbound": "accept",
    "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": arm, "timeout": 10}]}]},
}))' "$REPO")

exec claude --dangerously-skip-permissions --name triage --settings "$settings" "$@"
