#!/usr/bin/env bash
# Starts the triage seat: an auto-mode Claude Code session the consumer inbox can wake unattended.
#
# The watcher is armed by a SessionStart hook passed with --settings, so it belongs to this one
# session and no other seat in the repo. A hook receives the session's
# $CLAUDE_CODE_MESSAGING_SOCKET and is not subject to auto mode's classifier, which refuses to
# write or launch .claude/wake-on-suggestions.sh itself, as a session driving itself. The hook
# re-fires on /clear and on resume, and the watcher is a newest-wins singleton, so re-arming
# replaces the old watcher rather than adding one.
#
# Auto mode matters twice. It keeps the classifier on, and it is what lets the watcher's messages
# in: a session that bypasses prompts holds every inbox message whose sender declared no
# permission mode, and the only setting that lifts that hold (crossSessionInbound=accept) opens
# the inbox to every other session on the machine as well.
#
#   .claude/triage-session.sh [extra claude args...]
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO"

settings=$(python3 -c '
import json, sys
arm = f"setsid -f {sys.argv[1]}/.claude/wake-on-suggestions.sh >/dev/null 2>&1"
print(json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": arm, "timeout": 10}]}]}}))
' "$REPO")

exec claude --permission-mode auto --name triage --settings "$settings" "$@"
