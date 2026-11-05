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

## Standing rule for audit findings (the maintainer, 2026-11-05)

"For the next list of findings, judge how frequently would any bug would realistically fire. For once per known universe scenario defer
to 'when roadmap is empty/someone steps on this defect'." Audit rounds have found exotic defects, and every minor still needed a few
patches right after real use started, so the pm reads an audit sceptically: the adversary to a lead who wants to fix everything.

- A built branch is never deferred (the same morning: "Defer unbuilt items").
- For each unbuilt finding, ask: has a real run or an example hit it, and what must a run do to hit it?
- A finding no real run plausibly reaches is parked, gated on "a real run hits it, or the roadmap is empty", not sized into the next minor.
- A regression the release itself introduced, which a normal run reaches, still blocks the cut.
- **Price the fix's own risk** (the maintainer, 2026-11-05, on RM386): a fix that rewrites working code nothing exercises live
  swaps battle-tested code for untested code, which is a risk of its own. Weigh that before sizing a rare finding in, not after it is built.
  RM386 itself ships as built, with no rehearsal; if the next real publish breaks, it is a patch then.
- **No automatic next minor** (the maintainer, 2026-11-05): "'Auto-next minor' was a policy when we didn't have a dedicated decision
  maker for this." The pm parks and unparks as it sees fit. The maintainer highlights zones of interest for a minor (as with
  longevitymap v2); a parked item such a zone touches is unparked into it. Parked items live in ROADMAP.md with a gate, each checked
  in its gate-audit table. RM388 and RM390 parked on this rule (2026-11-05).

## Open questions and owed work

- **0.8's scope, agreed 2026-11-04.**
  - The final run's audit is in `docs/probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md`. The diffs were put to the
    maintainer and decided; the hand-written cost went from about 85 to about 55.
  - Every decision is a dated line in its `ROADMAP_0_8.md` entry, and the latest line wins.
  - The handout went to the lead on 2026-11-04 (in the clone, the live session and the messenger). The lead
    plans the branching, the specification, the order, the parallel work, the implementation and the tests.
  - The pm reads the lead's plan for scope drift only.
  - Three addenda followed the handout: the tag selector; the selector widened to `column=value`; and the
    second run's decisions (pmid/doi on every citing table, narrower outranks across tables, the role and
    effect-allele rules). The second run is audit §6, and the shape is agreed as sufficient and necessary for
    v2.

- **Drift read of `0.8`, 2026-11-04, at c3ac4d8** (RM253, RM322/334, RM336, RM304, RM337, RM342, RM239's
  columns): no drift. RM253's repeat rows carry no rsID and key on the coordinate, which fits "must not rely
  on rs3064744". RM342 keeps the `polars>=1.42.0` floor and locks 2.1.0, because polars-bio still caps <2.
  The next read starts after c3ac4d8.
- **Drift read of `0.8`, 2026-11-04 evening, c3ac4d8..503730c6**: no drift. The whole v2 group (RM322–RM336),
  RM236, RM239, RM253, RM303 and RM372 shipped as scoped; RM361–RM370 are the pre-cut audit's round-1 classes,
  which the person ordered. The next read starts after 503730c6. Put to the lead in `#just-dna-compiler>scope`
  (unattended, so no desk item):
  - the scope table has no row for RM361–RM370 or the RM267 REST witness; I write it on main unless the lead
    writes it on 0.8;
  - RM_TOC.md on 0.8 still carries RM361–RM370's reservation lines (the lead's records pass);
  - RM373–RM376: **0.8, by the maintainer's decision in the lead's interview on the migration probe**
    (2026-11-04 evening), which my default did not know of. The lead writes the RM_TOC cleanup at the cut merge.
  - Both scope rows written on main in e1869851 (done).
- **RM378 (coded errors, from S129) placed in 0.9, 2026-11-05** (f8b595d6), against triage's proposal of 0.8:
  the person's "the rest goes to 0.9", a permanent vocabulary, two open questions, and RM377 already covers
  the reporter. The person may take it into 0.8; told in the report, no desk item, since their rule decides it.
- **RM384 (a public name for the Ensembl lane's repo, from S130) placed in 0.8, 2026-11-05** (81e7dde2), as RM372's
  tail: RM372 is the maintainer's 0.8 item, the registry's 0.8 adoption pins the name, about 30 minutes. The line
  against RM378: a fix that completes a decided 0.8 item goes in; a new capability goes to 0.9. If the lead
  finds no room before the cut, it goes to 0.9.
- **RM380–RM383 are 0.8** (the lead, 2026-11-05), in the migration-probe scope row (8aab3e5d). RM382 reverses
  S85's "the row stays" by the maintainer's word; triage notes it at S85. The lead confirmed RM384 fits.
- **RM385 written for 0.9** (5dc2598f), on the maintainer's word: offline enrich has no reference at all.
- **Audit round 2 sized, 2026-11-05** (the maintainer asked, through the lead, for "what really blocks the release"). The line: a defect 0.8 itself
  introduced on a surface a consumer gates on (a strict refusal of a valid module, a P7 loss) blocks; a defect that was already there is
  sized by how often a real run hits it; the maintainer's word overrides. Blocks: RM387 (from RM374), RM389 (from RM364). In if built
  and cheap: RM361's amendment (merged whole, the lead's call), RM391, RM392. 0.9: RM388, RM390. RM386 first went to 0.9; the
  maintainer moved it to 0.8 the same morning: "if branch is built, what's the sense to defer then? Defer unbuilt items." So a built
  branch is never deferred; only unbuilt work is sized by frequency. RM387's reach measured on the 16 examples'
  `resolution.csv` at origin/0.8: no rsID at two loci, so it is rare in the corpus, but the enricher writes the shape itself. Residuals
  owed on 0.8: RM368 → RM386, RM362 → RM388, RM374 → RM390 (the lead's edit).
- **RM253's precedent, from just-vcf's lead (2026-11-04)**: the short-read callers they read (GATK,
  DeepVariant, DRAGEN, freeBayes, CGI) all write a repeat-length change as a left-aligned sequence indel,
  so 0.8's spelling matches. The repeat-count forms (ExpansionHunter `<STRn>` + REPCN, TRGT AL/MC,
  VCF 4.4 `<CNV:TR>`) are a second, rarer form. A 0.9 candidate only if a consumer meets one; no `RMn`.
- **The `0.8` push is the lead's, under its grant**, not the person's. I said otherwise in chat on
  2026-11-04 and withdrew it in `#just-dna-compiler>scope`.
- **Charter wording before the cut: settled.** The person read each changed sentence old → new in the
  lead's chat before leaving (P4, P7, the Goals snapshot bullet, the Goals toolchain clause) and answered
  "Good, I accept". The lead records it in CONSTITUTION_AMENDMENTS_HISTORY.md on `0.8`; no desk item.
- **Unattended from 04:10Z, 2026-11-04**: the desk holds no pm question, and none was waiting in chat.
  The licensing points below stay unraised: no work waits on them.
- RM149's gate: **decided 2026-11-03, it stays** (option 1). Written under RM149 in ROADMAP_0_9.md.
- The test registry `_ENTRY_FILES` → a `ROADMAP*.md` glob: the person asked whether a naming convention can
  replace the hard-coded list. It can (the glob finds the same 8 files). Handed to the lead on 2026-11-03.
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
