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
# (.claude/triage-state.sh) once at startup to pick up whatever is already pending.
#
# COOLDOWN is set for an agent author, not a human one: consumers write these notes
# through an agent, so the pattern is a burst of edits (five in a minute is normal) with
# gaps whenever the agent stops to read or probe something. A one-minute timer fires in
# the middle of such a run. 150s clears the pauses that show up in practice; raise it if
# a consumer's runs are slower, since the only cost of waiting is latency.
#
#   FILE=<path> COOLDOWN=<seconds> POLL=<seconds> .claude/watch-suggestions.sh
set -uo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FILE=${FILE:-$REPO/docs/CONSUMER_SUGGESTIONS.md}
COOLDOWN=${COOLDOWN:-150}
POLL=${POLL:-10}

mtime() { stat -c %Y "$FILE" 2>/dev/null || echo 0; }

last=$(mtime)
dirty=0

while true; do
    sleep "$POLL"
    now=$(mtime)

    if [ "$now" != "$last" ]; then
        last=$now
        dirty=1                     # still moving: restart the cooldown
        continue
    fi

    [ "$dirty" = 1 ] || continue
    [ $(($(date +%s) - last)) -ge "$COOLDOWN" ] || continue
    dirty=0

    pending=$("$REPO/.claude/triage-state.sh" "$FILE" --pending 2>/dev/null |
              awk 'NF { n++; if (n <= 8) { printf "%s%s(%s)", sep, $2, $1; sep = " " } }
                   END { if (n > 8) printf " +%d more", n - 8 }')
    if [ -z "$pending" ]; then
        echo "${FILE##*/} settled: nothing pending"
    else
        # Names the runbook: after a /clear this line is the whole brief.
        echo "${FILE##*/} settled: $pending — triage per docs/CONSUMER_TRIAGE_LOOP.md"
    fi
done
