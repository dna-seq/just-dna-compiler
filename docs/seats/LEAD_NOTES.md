# Lead notes

The lead's working state, rewritten to the present before each reset. Last rewritten 2026-11-03, at first seating.

## First seating (2026-11-03): the handout's first work

1. **Old triage waker retired**: done, 8c010c0, after triage's message that `watch.inbox` fired on the real
   S125–S127 edit.
2. **The seats in the docs**: done, 17b9a3a (RELEASE_CYCLE § Seats, the CLAUDE.md doc map, `seats/` in
   `not_in_nav`, which the seat PRs had left red).
3. **The id scripts stay**: kept. `.claude/triage-state.py`, `.claude/triage-archive.py`, `.claude/rm-next.py` are the
   repo's own and tested. Moving to the kit's `classes/triage/` copies would be an RM item, not filed.
4. **Trust register** (`docs/TRUST.md`): asked the person once, in chat. No answer yet.
5. **Scope files are the pm's**: noted. `docs/ROADMAP_0_8.md`, `docs/ROADMAP_1_0.md`, `docs/proposals/`.
6. **The kit pin**: this seat moves it (`bin/move-to-tag.py`), on a release announcement that needs it or a fix waited on.

## Standing rules from the person

- **Upstream adoption (2026-11-04):** the liaison decides adoption blockers and hands the lead an adoption map.
  Pin only when a new major is proven to break something, until support is integrated. If the liaison is
  unavailable and work must move, the lead may pin as a safety. (RM341's cap was reverted under this rule.)
  Sent to the seat-builder for LEAD.md and LIAISON.md.

## In flight

- **Push of `main` waits on the person.** Kit v0.1.117's auto-mode rule 11 lets a seat with a push grant push its
  own origin (kit #238 fixed). The person pastes rules 10 and 11 (`bin/automode.py` prints them), then this seat
  pushes. Not routed around meanwhile.
- Kit #239/#240 fixed in v0.1.117. The clone pins v0.1.118 (moved by triage).
- Avatar set (a polar bear).
- Leftover local branches `build/RM341` and `build/RM343`: cherry-picked onto `main`, so `-d` refuses them;
  `-D` is the person's.

## Open decisions

None open.

## Plan

- **RM338**: decided 2026-11-03 (content-checked text plus png/jpg, no SVG). `unattended`, `after RM337`
  (triage's patch, same function). Built by the lead in a worktree once RM337 lands.
- **RM344**: `unattended`, a patch (a duckdb-2-written `.duckdb` cache falls back to parquet).
- **RM342**: a minor, the pm's to place (0.9). Polars version in `manifest.compilation`.
- **Liaison's adoption map, item 4**: when `uv.lock` moves to polars 2, every digest moves once, and that release
  owes a RELEASE_RECORDS line (content unchanged). duckdb 2 lock any time (RM343 landed). The liaison schedules it.

The lead's own, none yet. The plan's states have not been read against what exists; that is the next start's first step.
