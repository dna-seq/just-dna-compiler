# Pm notes

The pm's working state, rewritten to the present before each reset. Last rewritten 2026-11-03, at the
first seating.

## First seating (2026-11-03)

- **Tools against the kit's.** None of the repository's own machinery is this seat's. `.claude/rm-next.py`
  is used by whoever files an `RMn` (the lead files them; this seat proposes); `.claude/triage-state.py`,
  `triage-archive.py`, `watch-suggestions.sh`, `wake-on-suggestions.sh` and the `arm_triage_watcher.py`
  hook are triage's. Retired nothing, moved nothing, kept nothing on this seat's behalf.
- **Watchers**: `pm/watch.desk` and `pm/watch.brief` started at punch-in.
- **Avatar**: asked `agents-kit/admin` in `#agent-chat>avatars`; not set yet.

## 0.8's scope, decided 2026-11-03

The person: "Reorganize so that 0.8 = already built/chosen fixes + longevitymap2 requirements, rest goes to
0.9". In the follow-up question they ticked the indel cluster and RM303 + RM253, wrote "Defer methylation to
0.9, gherkin also goes to freeze for reasons that you can read in nearby bestiary repo investigation", and
left RM248/RM188 unticked. On a side agent's note ("revisit. Add as needed") RM236, RM238 and RM239 came
back into 0.8 as inputs to RM333's confidence labels.

- **0.8** = built on `0.8` (PT1 and earlier) + the indel cluster (RM304, RM267, RM270, RM292, RM305) +
  RM303, RM253 + longevitymap v2 (RM322–RM336, RM294, RM302, RM236, RM238, RM239). Written as the scope
  table at the top of `docs/ROADMAP_0_8.md`.
- **0.9** = everything else, in `docs/ROADMAP_0_9.md` (opened 2026-11-03): RM188's parity work, methylation,
  RM149 (frozen), the long-parked items, and ten minors moved from `ROADMAP.md`. Its theme is undecided.
- **Rejected**: my option A (cut 0.8 at PT1 plus the indel fixes, v2 opening 0.9), and deferring RM333,
  RM334 and RM335 out of the v2 group.
- **Next**: the proposal for the indel round and the v2 round on the `0.8` branch, each with its
  interview first. The interview for RM323 comes first among the v2 items.
- **Merge warning sent to the lead**: the next `main` → `0.8` sync meets `ROADMAP_0_8.md` rewritten on both
  sides.

## Standing rule for every proposal (the maintainer, 2026-11-04)

"Always weight your proposals towards reduction of entities. If something can be built with 20 score, don't
build it with 30 for 'tidiness', it is clutter and bloat in guise of strict-typing of non-strict typed data."
A new table kind counts as about 10 authored columns. The authored surface is human-centred and denormalized on
purpose; normalization is the compiled parquet's job (RM346, 1.0).

## Open questions and owed work

- **The final v2 measuring run (2026-11-04), and what follows it, as the maintainer set it:**
  1. A subagent measures every v2 requirement against the proposed shape. Its output goes to
     `scratchpad/final/REPORT.md` and `EXAMPLES.md`.
  2. I compile its findings into an audit report in `docs/probes/`.
  3. I check that every new column is irreducible, and that none is derivable from the others.
  4. If the shape changed, I ask the maintainer on each difference.
  5. If it is stable (sufficient and necessary for v2), it counts as agreed, and I hand it to the lead to
     plan the branching, the specification, the build order and what runs in parallel, the
     implementation details and the tests.
- RM149's gate: **decided 2026-11-03, it stays** (option 1). Written under RM149 in ROADMAP_0_9.md.
- The test registry `_ENTRY_FILES` → a `ROADMAP*.md` glob: the person asked whether a naming convention can
  replace the hard-coded list. It can (the glob finds the same 8 files). Handed to the lead on 2026-11-03.
- The interviews for the 0.8 rounds, RM323 first, then the indel cluster; the proposals follow them.
- `docs/STRATEGY.md`: not started; the first question is who the three packages serve.
- `docs/DREAMS.md` (the 2026-10-19 four-model dream) is this seat's file and is untracked. Adding it to
  `mkdocs.yml` (`not_in_nav`) is the lead's edit; until then the docs-nav test fails on it. Its ideas
  have no verdicts yet.

## Licensing, as it stands (noted, not yet raised)

- **The copyright holder.** The person, 2026-11-03: "Copyright is technically still mine (Newton Winter) as
  I still am a sole maintainer". `LICENSE` names "DNA-Seq" instead. Whether the line should name them,
  and what reopens it (a second maintainer, an organisation taking the work), is a point for a lawyer
  and for the person. Not raised yet.
- **The packages**: `LICENSE` is MIT, "Copyright (c) 2026 DNA-Seq", at the repository root only. None of
  the four `pyproject.toml` files declares `license`, and no package directory carries a licence file, so
  whether the wheels ship one is unchecked.
- **A source's terms that `SourceRow` cannot say**: the four axes in `docs/probes/ALPHAGENOME_ATLAS.md`
  §2.6 are holder eligibility, a no-training bar, revocability with a delete obligation, and
  notice-of-modification. None has an `RMn` yet.
- **`redistribution` is recorded and gated nowhere here**; the gate belongs to the registry, at publish
  (RM27).
- **Open items**: RM282 (the PGx lane has one licence class), RM286 (PharmVar's research-use-only
  restriction lives in `notice` prose), and RM333 (Open Targets' licence is unprobed).
- **Republishing encumbered corpora** (SNPedia, CC BY-NC-SA) is a use case the maintainer envisions; the
  NC and SA terms are recorded as data, never treated as a refusal.
