#!/usr/bin/env bash
# Debounced watcher for the consumer-suggestion triage loop.
#
# Emits one line on stdout when the watched file has stopped changing for COOLDOWN
# seconds. Consecutive saves inside the cooldown collapse into a single event, because
# each mtime bump restarts the timer. Meant to be driven by the Monitor tool, where one
# stdout line becomes one notification; it works just as well piped to anything else.
#
# It never fires for a change that predates it: `last` is seeded from the current mtime
# and `dirty` starts clear, so an already-settled edit stays quiet. Run the ledger
# (.claude/triage-state.py) once at startup to pick up whatever is already pending.
#
# This is the only one of the three that is really bash; the ledger and the archiver are
# Python, and are invoked through $PYTHON below rather than as bare paths so that neither
# their exec bit nor their shebang is load-bearing (§ 6 of the runbook — the `bash` trap).
#
# COOLDOWN is set for an agent author, not a human one: consumers write these notes
# through an agent, so the pattern is a burst of edits (five in a minute is normal) with
# gaps whenever the agent stops to read or probe something. A one-minute timer fires in
# the middle of such a run. 150s clears the pauses that show up in practice; raise it if
# a consumer's runs are slower, since the only cost of waiting is latency.
#
# It only watches while the tree is on `main`. The loop commits as it goes (§5 of the
# runbook), and a branch — or a detached HEAD — is the user's own work, so triaging into
# it is the one thing the permit does not cover. Off main the watcher idles at
# BRANCH_PAUSE instead of POLL, says so once, and says so again when it resumes; it does
# not touch `last`, so an edit made during the pause is still detected on the way back.
#
# One watcher per watched file, and the newest wins. Arming it again replaces the running
# one instead of adding a second: the older watcher belongs to an earlier run of the agent,
# so it notifies nobody who is listening, and two live watchers report every settle twice.
# The key is the watched file's resolved path, so a sibling repo's watcher is a different key
# and is never touched. On start the watcher records itself in a pidfile and stops the
# previous owner, but only after checking that pid's command line, since a recycled pid
# could be anything. Every poll it checks the pidfile and exits if it no longer owns it.
#
# A replaced watcher exits SUPERSEDED (3), whether it noticed at a poll or was sent TERM by
# its successor; a TERM or INT while it still owns the pidfile is a deliberate stop and exits
# 0. Any other non-zero status is a real failure. The arming wrapper (§1 of the runbook)
# ends in `wait` on this process, so the task's exit status carries the distinction.
#
#   FILE=<path> COOLDOWN=<seconds> POLL=<seconds> BRANCH_PAUSE=<seconds> CAP=<n> \
#     .claude/watch-suggestions.sh
set -uo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FILE=${FILE:-$REPO/docs/CONSUMER_SUGGESTIONS.md}
PYTHON=${PYTHON:-python3}
LEDGER=${LEDGER:-$REPO/.claude/triage-state.py}
COOLDOWN=${COOLDOWN:-150}
POLL=${POLL:-10}
BRANCH_PAUSE=${BRANCH_PAUSE:-900}
BRANCH=${BRANCH-main}           # `-`, not `:-`: BRANCH= is an explicit "never pause", not an unset
CAP=${CAP:-8}

# The singleton. Keyed on the resolved path of the watched file, not on this script.
FILE_ABS=$(cd "$(dirname "$FILE")" 2>/dev/null && echo "$PWD/${FILE##*/}" || echo "$FILE")
PIDFILE=${PIDFILE:-${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/watch-inbox-$(printf %s "$FILE_ABS" | cksum | cut -d' ' -f1).pid}
old=$(cat "$PIDFILE" 2>/dev/null || true)
echo $$ >"$PIDFILE"
if [ -n "$old" ] && [ "$old" != $$ ] && kill -0 "$old" 2>/dev/null &&
   ps -o args= -p "$old" 2>/dev/null | grep -q "${BASH_SOURCE[0]##*/}"; then
    kill "$old" 2>/dev/null && echo "replaced watcher pid $old on ${FILE##*/}" >&2
fi
owner() { [ "$(cat "$PIDFILE" 2>/dev/null)" = $$ ]; }
SUPERSEDED=3
# Leave the pidfile behind only if it names somebody else: never delete a successor's.
trap 'owner && rm -f "$PIDFILE"' EXIT
# The successor writes the pidfile before it signals, so a TERM arriving here reads as not-owner.
trap 'owner && exit 0; exit "$SUPERSEDED"' TERM INT
# Bash runs a trap only after its foreground child returns, so a plain `sleep 900` during a
# branch pause would keep a replaced watcher alive for fifteen minutes. `wait` is interruptible.
nap() { sleep "$1" & wait $!; }

mtime() { stat -c %Y "$FILE" 2>/dev/null || stat -f %m "$FILE" 2>/dev/null || echo 0; }
# A detached HEAD has no symbolic ref, and is no more a place to commit than a branch is.
current_branch() { git -C "$REPO" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "(detached HEAD)"; }

last=$(mtime)
dirty=0
paused=""

while true; do
    owner || exit "$SUPERSEDED"     # replaced by a newer arming
    on=$(current_branch)
    if [ "$on" != "$BRANCH" ]; then
        # Announce the transition once. A pause nobody can see reads as a dead watcher,
        # and repeating it every quarter hour would be the noise the filter exists to avoid.
        if [ "$paused" != "$on" ]; then
            paused=$on
            echo "${FILE##*/} watch paused: tree is on $on, not $BRANCH — the loop commits, so a branch is yours"
        fi
        nap "$BRANCH_PAUSE"
        continue
    fi
    if [ -n "$paused" ]; then
        paused=""
        echo "${FILE##*/} watch resumed: back on $BRANCH"
    fi

    nap "$POLL"
    owner || exit "$SUPERSEDED"
    now=$(mtime)

    if [ "$now" != "$last" ]; then
        last=$now
        dirty=1                     # still moving: restart the cooldown
        continue
    fi

    [ "$dirty" = 1 ] || continue
    [ $(($(date +%s) - last)) -ge "$COOLDOWN" ] || continue
    dirty=0

    # The event line is capped: with a 17-item backlog an uncapped one listed every single item.
    pending=$("$PYTHON" "$LEDGER" "$FILE" --pending 2>/dev/null |
              awk -v cap="$CAP" 'NF { n++; if (n <= cap) { printf "%s%s(%s)", sep, $2, $1; sep = " " } }
                   END { if (n > cap) printf " +%d more", n - cap }')
    if [ -z "$pending" ]; then
        echo "${FILE##*/} settled: nothing pending"
    else
        # Names the runbook: after a /clear this line is the whole brief.
        echo "${FILE##*/} settled: $pending — triage per docs/CONSUMER_TRIAGE_LOOP.md"
    fi
done
