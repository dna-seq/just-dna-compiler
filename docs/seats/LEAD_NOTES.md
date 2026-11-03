# Lead notes

The lead's working state, rewritten to the present before each reset. Last rewritten 2026-11-03, at first seating.

## First seating (2026-11-03): the handout's first work

1. **Old triage waker retires**: open, `after triage's message`. Waits for triage to say its kit watcher
   (`[seat.triage.watch.inbox]`) fired. Then, in one commit with a changelog line: `git rm`
   `.claude/wake-on-suggestions.sh`, `.claude/watch-suggestions.sh`, `.claude/hooks/arm_triage_watcher.py`,
   `schema/tests/test_triage_watcher.py`; drop the `UserPromptSubmit` entry from `.claude/settings.json`; reword
   `CLAUDE.md` and `docs/CONSUMER_TRIAGE_LOOP.md` to "the triage seat's watchers, `.blueprints.toml`". Leave
   `docs/history/CHANGELOG_0_6.md` as it is.
2. **The seats in the docs**: done, 17b9a3a (RELEASE_CYCLE § Seats, the CLAUDE.md doc map, `seats/` in
   `not_in_nav`, which the seat PRs had left red).
3. **The id scripts stay**: kept. `.claude/triage-state.py`, `.claude/triage-archive.py`, `.claude/rm-next.py` are the
   repo's own and tested. Moving to the kit's `classes/triage/` copies would be an RM item, not filed.
4. **Trust register** (`docs/TRUST.md`): asked the person once, in chat. No answer yet.
5. **Scope files are the pm's**: noted. `docs/ROADMAP_0_8.md`, `docs/ROADMAP_1_0.md`, `docs/proposals/`.
6. **The kit pin**: this seat moves it (`bin/move-to-tag.py`), on a release announcement that needs it or a fix waited on.

## In flight

- **Push of `main` blocked by auto mode** (`[Remote Repoint]`, kit #238). Local `main` is ahead of `origin`.
  Asked the person to let it through; not routed around.
- Kit issues filed at seating: #238 (auto mode vs a granted push), #239 (onboard refuses a renamed repo's
  clone), #240 (join refuses a pre-existing `.blueprints.toml` without `[repo]`).
- Avatar asked of the admin seat in `#agent-chat>avatars`. Set it with `watchdog.py avatar lead --from ID` once it
  replies.

## Open decisions

None of the lead's own yet. The plan's states have not been read against what exists; that is the next start's first step.
