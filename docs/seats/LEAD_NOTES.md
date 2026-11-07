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

- **Long jobs run niced (the maintainer, 2026-11-05: "memorize nice setting for the seat jobs"):** every long command
  the lead or its agents start (full pytest suites, enrich/rebuild batches) runs under `nice -n 19`. Per-item batches
  run at `-P1`, at most `-P2`; pytest-xdist at most `-n 4`. Write this into every builder and merge brief. When the
  person or the sysadmin seat reports lag, `renice -n 19 -g PGID` the running groups at once. Why: a `-P4` enrich
  batch beside a full suite drove load to 65 on 16 threads, and the person's remote desktop dropped frames.
- **Registry wakes (2026-11-04, amended 2026-11-05):** `just-dna-registry/liaison` and `just-dna-registry/triage` wake
  our triage, and the registry liaison wakes the lead (re-added 275673f4). The two "false wakes" of 2026-11-04 were not wakes:
  a post to every seat never wakes through wake_from (the kit tooling seat, on winternewt/agent-seat-blueprints#269). The person's Zulip account
  for DMs is id 1213223.

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

- **0.8.0 released, 2026-11-05.** Published on PyPI by the person; tag `v0.8.0` on e97339a3; GitHub release
  up; docs refreshed (INTEGRATION_0_7 archived) and merged. RELEASE_CYCLE step 10 now makes tag, GitHub
  release and docs refresh the lead's after every publish (auto-mode rule 13 covers the release, kit #283).
- **Patches on `main` since the cut, uncut:** RM397 (the enricher wheel no longer ships the Atlas proto
  sources twice), `scripts/build-dists.sh` (wipes `dist/`, builds every member, exit 3 on a non-`.py` share
  over 3% or duplicate bytes), `uv-build<0.13`. They go into the next patch cut.
- **The next patch also waits on** RM400 (both halves), RM401 (after its batch-omission probe) and RM403, placed
  by the pm (`6047e082`, `d61974da`). Patch scope, so triage builds them; told triage 2026-11-07 that I am not,
  and to hand me any it would rather not. I cut the patch once they are on `main`. RM402 waits on RM401.
- **Cache:** `/data/just-dna-cache/ensembl_variations` is the split release; the old one is
  `ensembl_variations.pre-0.8`, to drop on the person's word. The just-dna-lite side still to be told.
- **Desk:** #210 (should the liaison keep `docs/DOWNSTREAM.md`, who waits on us; default: no list) and
  #211 (the stale-branch script in the scratchpad, `delete_stale_branches.sh`; default: nothing deleted).
- **Not done, the person's:** the worktree `.claude/worktrees/lead-RM372/data/rm372/fence_check`; merge
  commit cb6be8a4 has no Co-Authored-By trailer.
- **Records gap:** no release records for 0.7.1 or 0.7.2.
- **Kit v0.1.136:** in this shared clone, commit by path (`git commit --only -- <paths>`).
- Parked: RM388, RM390, RM396 and round-3 findings without a number (ROADMAP.md). 0.9: RM385.
