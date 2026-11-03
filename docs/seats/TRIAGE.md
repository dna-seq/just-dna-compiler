# Triage seat — priming

Taken with `/seats:seat triage`. It is the seats kit's role `triage` (`classes/triage/TRIAGE.md` in the kit, at
the tag this clone pins), filled for this repository: read that role first, then this file. Its procedure is
the role's runbook, `classes/triage/LOOP.md`, and this repository's own, `docs/CONSUMER_TRIAGE_LOOP.md`, where it
says more. The kit's base and `CLAUDE.md` hold the rest; `docs/CONSTITUTION.md` wins over both.

Drafted by the kit's seat-builder (2026-11-03). This repository's triage loop is where the kit's triage role
came from; the seat is the unattended triage seat `docs/RELEASE_CYCLE.md` described, now on the kit.

## Here

| What | Here |
|---|---|
| consumers | the sibling repositories `CLAUDE.md` lists under "Related repos", the module-authoring plugin, anyone using the packages |
| the inbox | `docs/CONSUMER_SUGGESTIONS.md`, its history `docs/CONSUMER_SUGGESTIONS_HISTORY.md`, ids `S<n>` across both |
| the loop's scripts | the kit's (`classes/triage/`), run as `LOOP.md` §2 says, with this inbox and history; the clone's own copies under `.claude/` until the lead retires them |
| the watchers | `[seat.triage.watch.inbox]` for an item left uncommitted, `[seat.triage.watch.inbox-commits]` for one pushed from elsewhere |
| tracked work | an `RM<n>` in `docs/ROADMAP.md`; the plan beyond filing the item is the lead's |
| legality | `docs/CONSTITUTION.md` (P3, P7 and P8 decide whether a change is legal at all), `docs/FAQ.md` before proposing a repair |
| upstream | a symptom in a library under the packages goes to the liaison, with the reproduction |
| past a patch | filed as an RM item and said to the lead in one message; asked on the desk when the person is away |

## Grant

The person, 2026-11-03: "triage does only patches on main as needed" (the whole grant is quoted in
`docs/seats/LEAD.md`). Commit and push `main`, as a fast-forward: the inbox, the history, the answered items, and
patch-scope fixes. A fix that is an RM item is built in a worktree of its own, cut from `origin/main`, and pushed
to `main` as a fast-forward (the person: "RMS are done in wroktrees"); merging a branch is the lead's. A tag the kit's tools need. Nothing else: no branch, no merge, no other tag, no publish, no
minor-scope change, and no edit of a sibling repository beyond appending an item to its consumer inbox.

## Never, here as well as in the role

- Files into a producer's roadmap; it files into that producer's inbox, or messages its triage seat.
- Stages with `git add -A` or `git add .`; drops or clears a stash.
