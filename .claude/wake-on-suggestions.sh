#!/usr/bin/env bash
# Wakes the arming Claude Code session whenever the consumer inbox settles with work in it.
#
# The harness caps every watch it owns: a background Bash task at 2 h (30 min by default,
# since 2.1.285), a Monitor at 30 min. So this runs detached, outside the harness, and wakes
# the session by posting a user message to that session's own inbox socket
# ($CLAUDE_CODE_MESSAGING_SOCKET, exported to every Bash command and hook). An idle session
# starts a new turn when one arrives. The line format is the one Claude Code's own help text
# gives: an auth line with the session's token, then
# {"type":"user","message":{"role":"user","content":...}}. Verified 2026-09-30 on 2.1.285.
#
# Unlike the one-shot arming it does not stop at the first event: the watcher keeps running,
# and every settle with something pending becomes one message. It ends when the watcher ends
# (superseded by a newer arming, exit 3, or stopped) or when the socket is gone, which is what
# a closed or restarted session leaves behind. Arm it from the session that triages:
#
#   setsid -f .claude/wake-on-suggestions.sh >/dev/null 2>&1
#
# Every env knob of watch-suggestions.sh (FILE, LEDGER, COOLDOWN, POLL, ...) passes through.
set -uo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SOCK=${CLAUDE_CODE_MESSAGING_SOCKET:?run from inside a Claude Code session}
TOKEN=${CLAUDE_CODE_MESSAGING_TOKEN:-}

post() {
    SOCK=$SOCK TOKEN=$TOKEN TEXT=$1 python3 -c '
import json, os, socket
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(os.environ["SOCK"])
lines = [{"type": "auth", "token": os.environ["TOKEN"]}] if os.environ["TOKEN"] else []
lines.append({"type": "user", "message": {"role": "user", "content": os.environ["TEXT"]}})
s.sendall("".join(json.dumps(x) + "\n" for x in lines).encode())
s.close()
'
}

coproc W { exec "$REPO/.claude/watch-suggestions.sh"; }
p=$W_PID
# Keep our own copy of the read end: bash unsets W once the coprocess exits. A blocking read
# was seen to outlive a killed watcher, so it wakes every minute to check both ends are alive.
exec {rfd}<&"${W[0]}"
while :; do
    IFS= read -r -t 60 line <&"$rfd"
    rc=$?                           # >128 is the timeout; anything else non-zero is EOF
    if [ "$rc" -ne 0 ]; then
        [ "$rc" -gt 128 ] && kill -0 "$p" 2>/dev/null && [ -S "$SOCK" ] && continue
        break
    fi
    case "$line" in *"nothing pending"*|*paus*|*resum*) continue;; esac
    [ -S "$SOCK" ] || break
    # The timestamp keeps two identical settles apart: the inbox drops a quick repeat.
    post "[watcher $(date -u +%FT%TZ)] $line" || break
done
kill "$p" 2>/dev/null
wait "$p"
