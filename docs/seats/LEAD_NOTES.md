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

- **In flight, 2026-11-04 night (the person asleep, "build unattended"):** the /batch run building all of 0.8
  (plan `~/.claude/plans/glimmering-greeting-sketch.md`, contracts in PT2). Integration worktree
  `/tmp/claude-1000/-data-sources-just-dna-format/cb39872f-9ac8-49ad-96ce-7354acea34da/scratchpad/wt-08sync` (0.8).
  Merged on 0.8: wave 0 (sync, polars 2.1.0), RM337, RM342, probes; a merge agent is landing RM304, RM336,
  RM322+RM334, RM253, RM303, meta-core, RM348. Building: RM352 (blocks the cut). On main: RM338, RM347 merged.
  Filed: RM348–RM353. Next: wave 2 (StudyRow batch, RM335, RM292, Open Targets lane, B2, RM349, RM351), wave 3–5,
  four-leaf audit, cut subagent (its brief items in the scratchpad's `cut_brief_notes.md`). Charter wording
  vetted by the person. Never `git branch -D` (classifier).
  Wave 1 all merged on 0.8 (9bfc87d, 5195 passed); a merge agent is syncing main into 0.8. Wave 2 running, each
  builder in its own `.claude/worktrees/lead-<unit>` on `build/<unit>`: studyrow, RM335, RM292, RM333 (Open Targets
  lane + RM239 + RM236), meta-derived (RM327 tradeoff), RM349, RM351, RM305 (ClinVar-GKM), RM353 (on main); RM352
  still building. Quota ran past 85% at 05:15 CET: a builder that died on quota is respawned after the 07:29 CET
  reset with "continue from build/<unit>'s last commit" (shared brief: scratchpad `worker_common_w2.md`).
  Wave 3 after the StudyRow batch: study-orphan widening, RM331's computed LD pair; wave 4: RM267, examples;
  wave 5: RM270, release-gate sweep.

- **0.8's build** (the pm's handout, 2026-11-04): the plan is `docs/proposals/PROPOSAL_0_8_PT2.md`
  (3d5adcd), critic-read. Seven pm questions in its §4, each with a default the build takes. Wave 0 is
  the lead's: push `0.8` (150 unpushed commits; auto mode refused the push, the person must unblock),
  merge `main` into it in `wt-08sync` (13 conflicts, rules in §1), the polars 2 lock, RM338's patch on
  `main`. Then four lanes (A schema adds, B meta-table, C indel, D derived inputs), one builder each.

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
