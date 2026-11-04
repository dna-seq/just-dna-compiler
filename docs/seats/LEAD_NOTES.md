# Lead notes

The lead's working state, rewritten to the present before each reset. Last rewritten 2026-11-03, at first seating.

## First seating (2026-11-03): the handout's first work

1. **Old triage waker retired**: done, 8c010c0, after triage's message that `watch.inbox` fired on the real
   S125–S127 edit.
2. **The seats in the docs**: done, 17b9a3a (RELEASE_CYCLE § Seats, the CLAUDE.md doc map, `seats/` in
   `not_in_nav`, which the seat PRs had left red).
3. **The id scripts**: kept at seating; triage then moved to the kit's copies (150d916). Claim an `RMn` with
   the kit's `classes/triage/item-next.py --note`.
4. **Trust register** (`docs/TRUST.md`): asked the person once, in chat. No answer yet.
5. **Scope files are the pm's**: noted. `docs/ROADMAP_0_8.md`, `docs/ROADMAP_1_0.md`, `docs/proposals/`.
6. **The kit pin**: this seat moves it (`bin/move-to-tag.py`), on a release announcement that needs it or a fix waited on.

## Standing rules from the person

- **Upstream adoption (2026-11-04):** the liaison decides adoption blockers and hands the lead an adoption map.
  Pin only when a new major is proven to break something, until support is integrated. If the liaison is
  unavailable and work must move, the lead may pin as a safety. (RM341's cap was reverted under this rule.)
  Sent to the seat-builder for LEAD.md and LIAISON.md.

## In flight

- `main` pushed 2026-11-04 by the pm at the person's word (…150d916), the lead's commits included. Auto-mode rule
  11 (kit v0.1.117) is what lets this seat push its own; the person pastes it.
- Leftover local branches `build/RM341` and `build/RM343`: cherry-picked onto `main`, so `-d` refuses them;
  `-D` is the person's.

## Open decisions

None open.

## Plan

- **RM338**: decided 2026-11-03 (content-checked text plus png/jpg, no SVG). `unattended`, a patch on `main`,
  no longer after RM337: triage re-sized RM337 to a minor on 2026-11-04 (172a215), because its warning needs a
  new `VALID_WARNING_CODES` member. Split, told to triage the same day: the patch ships only what needs no
  new code (the content checks, and each newly shipped non-`.log` file named by a `logger` line and in
  `manifest.logs`). The left-behind warning, a failed check's reason included, goes with RM337 in its minor.
  Write that split into RM338's entry when building it.
- **RM344**: `unattended`, a patch (a duckdb-2-written `.duckdb` cache falls back to parquet).
- **RM342**: a minor, the pm's to place (0.9). Polars version in `manifest.compilation`.
- **Lock moves, the liaison's schedule (2026-11-04):** duckdb 2.x into `uv.lock` once RM344 lands, so RM344
  unblocks it. polars 2.x into `uv.lock` in the release that ships RM342 (0.9), with a RELEASE_RECORDS line
  (parquet bytes move, content unchanged). Nothing breaks on 2.x meanwhile.

The lead's own, none yet. The plan's states have not been read against what exists; that is the next start's first step.
