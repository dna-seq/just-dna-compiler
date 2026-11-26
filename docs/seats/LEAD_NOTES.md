# Lead notes

The lead's working state, rewritten to the present before each reset. Last rewritten 2026-11-16.

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

- mitomap behind source (liaison 643088167, 2026-11-24): the dump moved 2026-11-18 (mmutation edited 2026-11-17, 603 rows, +6 citation links). Built as mitomap_2026-11-17+2026-11-03 into `data/caches/rebuild-2026-11-24/mitomap`, upload rehearsed (5 files). `blocked: the person` (the classifier refuses a seat's publish, kit #529): `uv run just-dna-enricher mitomap publish data/caches/rebuild-2026-11-24/mitomap`. After it: `cache pull --only mitomap`, then `mitomap miss` (mitomap_miss follows its parents).
- **0.9 rescope (the pm on the maintainer's word, 2026-11-26; ROADMAP_0_9.md "The rescope", e60bfbd6).** Steps 1-2
  done. **Step 5, the cut redone: built, gated, dists ready; `blocked: desk #461` (the publish, the person's).**
  Branch `cut/v0.9.0-2` at 284192b4, pushed, in `.worktrees/cut-090-2` (locked): origin/0.9 + origin/main merged +
  the first cut's four commits carried (roadmap close redone: the nine rescoped items in ROADMAP_HISTORY, RM468 into
  ROADMAP_0_10, RM469 filed for RM461's residual) + INTEGRATION_0_9/CHANGELOG/record for the rescope. Gates: full
  suite 8338 passed (the one red was the links fixed mid-run, re-run green); sweep --release 0.9.0 green, 22/22
  unmoved; real runs 22 modules x {asis, fresh} x {0.8.10, 0.9.0} enrich+compile, 176 rc=0, outputs equal but clocks
  and producer, content_signature 44/44, the 13 digest moves reproduce from the inputs (harness
  `.worktrees/cut-090-2/data/interim/gate-090/`); network 45 passed, 1 red: ClinVar-GKM retired `v1/1.1` today (1.2
  live, 0.8.10 red too), sent to the liaison (643876032), desk #461 asks publish now (default rec.) or fold the fix
  in. Dists: `dist/` holds the six 0.9.0 files (0.8.10's wiped), twine PASSED. If the liaison's fix is small and
  lands before the publish: fold it into the cut, rebuild dists, post an Update on #461. **RM469 was claimed into the
  primary checkout's docs/RM_TOC.md** (uncommitted, beside the old RM458-466 rows): never stage them; run
  `item-next.py --release` for RM458-RM469 once the cut is on main. After the publish: RELEASE_CYCLE step 10 (tag
  `v0.9.0` on the cut commit, GitHub release, README/CLAUDE.md say 0.9.0 is current), merge the cut into 0.9 and,
  after the consumers' trial (desk #370), 0.9 into main; LEAD.md/PM.md point at ROADMAP_0_10 (change-priming).
  `.worktrees/cut-090` (cut/v0.9.0) is superseded and unlocked; its branch needs the person's `-D` (cherry-picked).
- **RM470 (ClinVar-GKM v1/1.1 → v1/1.2), 0.9.1 by the pm (643877146): built, checked, not merged.** Branch
  `build/09-rm470` at 6004d52c, pushed, worktree `.worktrees/09-rm470` (locked), off the cut. Merge into main after
  0.9 merges there, then cut 0.9.1 at once after the 0.9.0 publish. Before that cut: one real `clinvar-gkm build`
  against v1/1.2 (2.3 GB, not run yet). Its RM_TOC reservation row (RM470) sits uncommitted in the primary
  checkout beside RM458-RM469: release them all with item-next.py --release once on main.
- 0.8.10 published 2026-11-26 (PyPI 11:11Z, all three; desk #415): tag `v0.8.10` on 65cfa25b, GitHub release,
  README.md:94 and CLAUDE.md:84 name 0.8.10, done-line to releases, the registry told. The 0.9 merge is now unblocked
  by the tag; it still waits on the two trials or the person's "skip" (desk #370). Branches cut/v0.8.9, land/v0.8.9,
  cut/v0.8.10 and land/v0.8.10 are the person's to delete.
- Lanes behind source (liaison, 2026-11-17): done 2026-11-18. clinvar_2026-11-15 and mitomap_2026-11-09+2026-11-03
  published by the person (the classifier refused the seat, kit #529), pulled here; mitomap_miss rebuilt, the old copy
  moved to `/data/just-dna-cache/mitomap_miss.before-2026-11-18` (the person's to delete).
- 0.8.8 released 2026-11-17: enricher 0.8.8 on PyPI (02:17Z), tag `v0.8.8` on 655f1ebc, GitHub release, README and
  CLAUDE.md name it.
- `main` pushed 2026-11-04 by the pm at the person's word (…150d916), the lead's commits included. Auto-mode rule
  11 (kit v0.1.117) is what lets this seat push its own; the person pastes it.
- Leftover local branches `build/RM341` and `build/RM343`: cherry-picked onto `main`, so `-d` refuses them;
  `-D` is the person's.

- 0.9 (2026-11-16): every decision made (ff09d949, the pm's answers to the critic; RM431 ask 4 local-only, never
  published, decided the same evening). Build plan: `/tmp/claude-1000/-data-sources-just-dna-format/cb39872f-9ac8-49ad-96ce-7354acea34da/scratchpad/BUILD_PLAN_0_9.md`
  (scratch; this line is the record): branch `0.9` off `main`; wave 0 `LookupClients` leaf module + `parse_release`;
  wave 1 RM443, RM412, RM404, RM437 in parallel; wave 2 RM430; wave 3 RM431 asks 6, 5, then 4. Then one four-leaf
  round (two at most), the pm sorts, the cut. `unattended`: starts when the person is away.
- 0.9 cut built 2026-11-19, not merged: local branch cut/v0.9.0 at e057186b (worktree .worktrees/cut-090, unlocked;
  dists in its dist/). Gates: suite 8196 + 1 red only until v0.8.10 is tagged (test_first_seen, by design), sweep
  --release 0.9.0 green, network gates 28, strict docs, twine 6. Before the merge: (1) 0.8.10 published and tagged,
  then the full suite re-run at the cut commit; (2) the consumers' trial (desk #370, default: registry and
  module-creator try d9c578ae; module-creator blocked by its own auto-mode rules, kit #550); (3) merge cut/v0.9.0
  into main taking the branch's side of docs/ROADMAP_0_9.md (moved to history); (4) `item-next.py --release` for
  RM458-RM466, whose reservation rows sit uncommitted in the primary checkout's docs/RM_TOC.md: never stage them;
  (5) LEAD.md/PM.md name ROADMAP_0_9.md as the open minor's file: point at ROADMAP_0_10.md (change-priming). Then
  dists into dist/ for the person's publish. Scratch under .worktrees/ (cut-090-docs/ holds a throwaway signing key).

## Open decisions

None open.

reflect after 2026-11-24: classes/base/BASE.md as of v0.1.231 (a done-claim is checked from where the person
looks; read 2026-11-17, no concern).
reflect after 2026-11-23: classes/base/BASE.md as of v0.1.224 (only a real fork goes to the person; read as its
adversary 2026-11-16, no concern: the lead's only standing wait is the PyPI publish, a step that is the person's, not
a choice).
reflect after 2026-12-01: classes/base/BASE.md and classes/lead/LEAD.md as of v0.1.272 (an asked action is the
seat's until it works; a granted step is taken then reported; a procedure is run before it is handed over; no work
parked on a quota figure; a seated lead starts its own team's idle seats, D219. Read as its adversary 2026-11-24, no
concern: the two standing waits, the PyPI and mitomap publishes, are steps outside the grant (the classifier refuses
a seat's publish), and the mitomap upload was rehearsed by dry run before it was handed over).
reflect after 2026-12-01: classes/base/BASE.md as of v0.1.275 (a direct message mentioning someone not in it is named
in the first reply, relay or slip; read 2026-11-24, no concern: the lead takes direct messages rarely).

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
- **0.8.6 released, 2026-11-13** (all three; RM439, RM440, RM437's doc half). On PyPI 14:24 UTC (the maintainer); tag
  `v0.8.6` on 2f03ab4a, pushed; GitHub release up; README and the CLAUDE.md doc map name 0.8.6 (48d287ce).
  RELEASE_CYCLE step 10 complete. The publish sweep took the merged cut and build branches; `cut/v0.8.6` stays, held by
  its worktree `wt-cut-086` (unlocked), for the maintainer to remove.
- **0.8.7 released, 2026-11-15** (enricher only; RM442, RM444; sized by the pm). On PyPI 16:01 UTC (the
  maintainer); format and compiler stay 0.8.6. Tag `v0.8.7` on 3b65ab7a, pushed; GitHub release up; README and the
  CLAUDE.md doc map name 0.8.7. RELEASE_CYCLE step 10 complete. `test_first_seen`'s release list now
  takes every package's version (an enricher-only cut left format's on the old tag). The AVI interrupt test's
  load flake recurred and is fixed (d8c0e0f2, 10 s of work against a 4 s bound). `cut/v0.8.7` and worktree
  `wt-cut-087` (unlocked) are the maintainer's to remove.
- **0.8.8 cut, 2026-11-16, unpublished** (enricher only; RM445 alone; sized by the pm to cut at once). Cut commit
  655f1ebc on `main`, pushed; format and compiler stay 0.8.6. `dist/` holds the enricher 0.8.8 wheel and sdist,
  twine-checked (`scripts/build-dists.sh` needs `bash`, not `sh`). Gates: full suite 7446 passed, network gates 26,
  strict docs build green. After the maintainer publishes: tag `v0.8.8` on 655f1ebc, GitHub release from the
  scratchpad's `release_notes_0_8_8.md`, README and the CLAUDE.md doc map name 0.8.8. For the maintainer to remove:
  worktrees `wt-rm445`, `wt-cut-088` (unlocked); `build/RM445`, `land/RM445` need `-D` (cherry-picked onto main);
  `cut/v0.8.8` takes `-d` once its worktree goes.
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
- **Desk:** none open. #210 and #259 withdrawn 2026-11-14 as `default applied:` (no downstream list; the
  release rule of 307a5ae3), #211 as `moot:` (5 local branches left, the publish sweep takes merged ones).
- **Not done, the person's:** the worktree `.claude/worktrees/lead-RM372/data/rm372/fence_check`; merge
  commit cb6be8a4 has no Co-Authored-By trailer.
- **Records gap:** no release records for 0.7.1 or 0.7.2.
- **Kit v0.1.136:** in this shared clone, commit by path (`git commit --only -- <paths>`).
- Parked: RM388, RM390, RM396 and round-3 findings without a number (ROADMAP.md). 0.9: RM385.
