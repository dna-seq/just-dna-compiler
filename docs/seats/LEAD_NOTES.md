# Lead notes

The lead's working state, rewritten to the present before each reset. Last rewritten 2026-11-07.

## First seating (2026-11-03): the handout's first work

1. **Old triage waker retired**: done, 8c010c0, after triage's message that `watch.inbox` fired on the real
   S125–S127 edit.
2. **The seats in the docs**: done, 17b9a3a (RELEASE_CYCLE § Seats, the CLAUDE.md doc map, `seats/` in
   `not_in_nav`, which the seat PRs had left red).
3. **The id scripts**: kept at seating; triage then moved to the kit's copies (150d916). Claim an `RMn` with
   the kit's `classes/triage/item-next.py --note`.
4. **Trust register** (`docs/TRUST.md`): the maintainer, 2026-11-08: "lowprio, PM to reask after 1.0".
   Not started; handed to the pm to ask again after the 1.0 cut.
5. **Scope files are the pm's**: noted. `docs/ROADMAP_0_8.md`, `docs/ROADMAP_1_0.md`, `docs/proposals/`.
6. **The kit pin**: this seat moves it (`bin/move-to-tag.py`), on a release announcement that needs it or a fix waited on.

## Standing rules from the person

- **HF uploads on the pm's sign-off (the maintainer, 2026-11-07):** "you have HF upload rights on PM's signoff
  (basically, two-agent consensus instead of human)". Reference snapshots only, never a registry module or
  PyPI. Ask the pm with lane, label, dry-run file count and reason; quote its yes. RELEASE_CYCLE § Patches.
- **No cut with an unpublished lane (same day):** `JUST_DNA_NETWORK_TESTS=1 uv run pytest
  enricher/tests/test_prerelease_gates.py` green at the cut commit (RM413).
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
- **0.8.1 released, 2026-11-07** (enricher only: RM397, RM398, RM400, RM401, RM403, RM407). Tag `v0.8.1`
  on 6330f908, pushed. The GitHub release is not up (notes were in a session scratchpad,
  `release_notes_0_8_1.md`); auto-mode rule 13 is pasted now (2026-11-08), so the lead can create it.
- **0.8.2 released, 2026-11-08** (all three packages; RM408, RM410, RM411, RM413-RM417). On PyPI (the
  maintainer); tag `v0.8.2` on b98f7e9c, pushed. gnomAD constraint 4.1.2 published to
  `just-dna-seq/gnomad_constraint` (rebuilt with 0.8.2 from `data/input/gnomad/`, parquet byte-identical to the
  pre-bump build; the hub answers `gnomad_v4.1.2_constraint`). GitHub release up (the maintainer granted
  that one command; rule 13 was pasted afterwards, `automode.py --check` clean on 2026-11-08). Docs refresh merged (9c37d7db). Liaison's ledger updated
  (fe38e101). `CLAUDE.md`'s `@constraint-two-releases` headline changed on the maintainer's yes (59491cbf).
  RELEASE_CYCLE step 10 complete.
- **0.8.3 released, 2026-11-10** (all three packages; RM418, RM420, RM409, RM421, RM422, RM423). On PyPI (the
  maintainer); tag `v0.8.3` on 725eb2bb, pushed; GitHub release up; README and the CLAUDE.md doc map name 0.8.3
  (67a514b8). RELEASE_CYCLE step 10 complete. RM424 parked (a minor). The 0.8.3 worktrees and branches were removed by the maintainer, 2026-11-10. RM409's interrupt test failed once at load 30–48 (1.0 s bound): file
  if it recurs.
- **0.8.4 released, 2026-11-11** (all three packages; RM425, RM426, RM427, RM428). On PyPI (the maintainer, 01:14
  UTC); tag `v0.8.4` on 36cbc20f, pushed; GitHub release up (notes corrected: one public attribute,
  `GwasCatalogClient.size_refusals`, also aec2b744 in the CHANGELOG); README and the CLAUDE.md doc map name 0.8.4
  (9c4cf9cc). RELEASE_CYCLE step 10 complete. Desk #258 withdrawn (done); #259's default applied (307a5ae3).
  `wt-cut-084` unlocked; `cut/v0.8.4` handed to the maintainer for `-D` (cherry-picked, `git cherry` shows it on main).
- **0.8.5 released, 2026-11-12** (all three; RM432, RM434, RM436, RM438). On PyPI 22:06 UTC (the maintainer); tag
  `v0.8.5` on c036c700, pushed; GitHub release up; README and the CLAUDE.md doc map name 0.8.5 (a5308f60). RELEASE_CYCLE
  step 10 complete. The priming takes the package-index reader and the branch sweep on publish (6fcf74a5, desk #271,
  the maintainer: "treat builder as my word"); watcher `pypi` running. Merged `worktree-agent-*` branches deleted. For
  the maintainer: `cut/v0.8.4`, `cut/v0.8.5`, `build/RM438` need `-D` (cherry-picked, on main by `git cherry`) after
  their worktrees go. RM437's doc half, RM439, RM440 built 2026-11-13.
- **0.8.6 cut, 2026-11-13, waiting on the maintainer's publish** (all three; RM439, RM440, RM437's doc half). Cut commit
  2f03ab4a on `main`, pushed (prepared on `cut/v0.8.6` as c84edafb). Record: a measured zero over 22 modules. Gates:
  full suite 7408 passed, 180 skipped; prerelease gates 26; sweep and strict docs green. Dists in `dist/`, twine 7.0.0
  passed (6). Notes: scratchpad `release_notes_0_8_6.md`. After the publish: tag `v0.8.6` on 2f03ab4a, GitHub release,
  README + doc map. `cut/v0.8.6` needs `-D` with the others; `wt-cut-086` unlocked.
- **Next patch on `main`, uncut (after the 0.8.4 cut commit):** RM432 (ac3f1bcc, the lead's, 2026-11-11: two
  snapshot readers raise `FileNotFoundError`; a behaviour change for a direct caller), the GWAS docstring's 15/s budget
  (7a88e10f), RELEASE_CYCLE's floor rule (307a5ae3). Lesson from RM428: it added the public attribute
  `GwasCatalogClient.size_refusals` on `main`, which patch scope forbids; it shipped in the 0.8.4 cut and stays (the
  pm), and RM429 is the minor that surfaces it. A builder's own new attribute gets a leading underscore on `main`.
- **Carried by the 0.8.4 cut (was the next patch after 0.8.3):** RM425, RM426, RM427 (e7fa81d6, triage's: the ClinVar skip names `cache pull --only clinvar`, and a walk checks every quoted command), the fence test's hub-registry fix (11f86d74) and the liaison's first weekly dependency bump (867e8462, 4e30ef46; huggingface-hub 2.4.0, duckdb held at 1.5.5).
- **Shipped in 0.8.3 (was the next patch):** RM409 shipped 2026-11-08 (e0ceaa28: Ctrl-C stops the Open Targets mirror and the
  AVI build within a chunk); RM421 filed from it, sized by the pm and shipped 2026-11-08 (83182f88: a 120 s default timeout in
  `stream_to_file`, an AST walk refusing `timeout=None`). RM420 shipped 2026-11-08 (dd900ff3: `cache pull`/`prepare` follow the hub's
  release over a pulled cache; a local build is left alone; the pm sized it ahead of everything). The 0.8.2 GitHub
  notes and INTEGRATION_0_8 § 4 carry its correction. RM418 shipped 2026-11-08 (d28c74b5, one NCBI gate per process via
  `net._service_gate`). RM419 filed (the same class beyond NCBI); the pm parked it as a patch (88bda8eb): it
  unparks on a reported rate-limit refusal with two of our clients in one process, or the registry running
  enrichments as threads, then the Ensembl pair first.
- **Cache:** `/data/just-dna-cache/ensembl_variations` is the split release. The old
  `ensembl_variations.pre-0.8` was deleted by the maintainer, 2026-11-08. The just-dna-lite side still to be told.
- **Desk:** #210 (should the liaison keep `docs/DOWNSTREAM.md`, who waits on us; default: no list) and
  #211 (the stale-branch script in the scratchpad, `delete_stale_branches.sh`; default: nothing deleted).
- **Not done, the person's:** the worktree `.claude/worktrees/lead-RM372/data/rm372/fence_check`; merge
  commit cb6be8a4 has no Co-Authored-By trailer.
- **Records gap:** no release records for 0.7.1 or 0.7.2.
- **Kit v0.1.136:** in this shared clone, commit by path (`git commit --only -- <paths>`).
- Parked: RM388, RM390, RM396 and round-3 findings without a number (ROADMAP.md). 0.9: RM385.
