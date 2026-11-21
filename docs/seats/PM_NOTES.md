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
- **Audit round 3 and the docs pass sized, 2026-11-05.** Four block (all on the rederive migration path), six go in as the docs pass,
  eleven park without a number in ROADMAP.md's "Audit findings parked without a number" (an `RMn` only on unparking, to keep the
  entity count down). The containment breach (two outside runs left their copy) is already the kit's #278.
- **ROADMAP_0_9.md re-sized, 2026-11-05, after the 0.8.0 cut: done.**
  - **Parked into ROADMAP.md Active items (22):** the old default had moved them to 0.9. Each now has a "**Unparks when**" line, its
    status token reads `a minor, parked`, and it has a gate-audit row; the 15 new rows were all judged Sound.
  - **Stays in 0.9 (15):** what the maintainer placed there by name (methylation RM317–RM319, RM350, RM385, RM302); the PacBio zone
    (RM56, RM65 and RM66, which wait on RM319's repeat-caller output); longevitymap v2's leftovers (RM360, RM358, RM294, RM345, plus
    RM286 as the same licence-shape design); and RM265, which a real run hits (S114: it warns on every compile of just-dna-lite's
    three ClinVar panel modules).
  - **Kept in 0.9 as notes, not work:** RM67, RM84's consumer half and RM149 (frozen).
  - **Fixed after the first commit:** the move had carried two group headings of the 0.9 file (the VCF 4.4 items, the 0.7
    vocabulary residue) into ROADMAP.md; they are back. RM16's circular gate is restated as its shape question. The RM_TOC rows of
    the 22 say "parked" but still sit under their old 0.9-era headings; a later TOC pass may move them.
  - **The §4 counter lamp now counts parked items.** `grep -c 'Status** open — **a minor'` reads 25, past the 20 lamp, and
    most of that is parked. The lamp asks nothing (RELEASE_CYCLE), so this is information for triage, not a change I make.
- **Priming edit through change-priming, done (2026-11-05):** `docs/seats/PM.md` and `LEAD.md` named `docs/ROADMAP_0_8.md`,
  which the cut moved to `docs/history/`; both now name the open minor's file (0.9). LEAD.md's "`0.8` today" branch line
  now says none is open between cuts, as RELEASE_CYCLE does. No CHANGELOG line: no behaviour moved, and it is not my file.

## Open questions and owed work

- **Desk #276, link `~/.claude/projects/-data-sources-just-dna-compiler` to the existing `-data-sources-just-dna-format`
  memory**, filed 2026-11-12, S4, after the checkout swap. Recommended yes; on silence nothing changes.


- **RM433's second trial: done 2026-11-14** (8ebe578a): a signal at strong mQTLs, the probe doc's § 7, RM433
  updated. Next for it: RM317's design interview inside the 0.9 scope interview; a third trial (moderate mQTLs)
  only if the design needs it. The live AlphaGenome terms changed (training ban wider, carve-out renamed): told
  the liaison, whose vendored copies these are.

- **Desk #261 answered 2026-11-15: "1, 2"**, remote reads are a 0.9 zone with the follow-ups, read order disk →
  registry proxy → Hugging Face (429 sends a client on). Recorded under RM430/RM431 (5ddfd16f). The RM_TOC rows
  and the gate-audit row for RM430 still say parked: the lead's records pass, or mine at the scope write.
  The registry's lead answered the same hour: the proxy is live (registry 0.30+), its contract recorded under
  RM430 (12da77c9). The night trial measures disk, the polygon (`module-polygon.just-dna.life`) and Hugging Face.
- **Standing rule (the maintainer, 2026-11-15): smaller minors.** "don't make it too big, these half-a-week release
  maraphons bleed me dry, lets make em smaller". A minor is one seam, its decisions made before the branch, no new
  table kind; the rest goes to the next small minor or is parked.
- **0.9 and 0.10 scope: set 2026-11-16 (8076cf54), desk #326 applied on its default** under the base's real-fork rule
  (v0.1.224, kit #510: a yes-question with no drawback on one side is the seat's; the maintainer: "I'm not a parrot").
  0.9 = RM430, RM431, RM437, RM443, RM404, RM412's second half (enricher only); 0.10 = RM399 + RM441 (with S156),
  RM435, RM265, RM385; methylation after 0.10, undated. Parked into ROADMAP.md with gates and gate-audit rows: RM302,
  RM350, RM294, RM345 + RM286, RM358, RM360. **No ROADMAP_0_10.md**: the file is "0.9 and later minors" already, so
  0.10 sits under its own heading there and the 0.9 cut opens 0_10 with what is left (fewer files, no nav change).
  #327/#328 applied as a 0.9 trial, written atop ROADMAP_0_9.md with the blocker definition; RELEASE_CYCLE.md
  unchanged; **owed: report after 0.9 how both went**. #329 withdrawn (a "when" doubt is no question): methylation
  `waits until` the maintainer reports the PacBio samples in hand. All four withdrawn `default applied:` with a veto
  offer. **One fork left for 0.10's opening**: RM265's shape (an authored `panel_provenance:` block, full cost, or the
  machine-written licence row, half cost; the gene denominator a list or a count). RM385's two questions are mine (a
  trial: seqrepo vs FASTA; the URI weighs ahead). #276 got an Update (the new-name folder exists since 11-14 with two
  transcripts); it stays the maintainer's, a change in their settings folder outside any grant.
  **Fixes after review, same day:** RM302, RM350, RM294 were the maintainer's own 0.9 placements, so parking them is a
  real fork: desk #347 (parked / a 0.11 / into 0.10; default parked, recommend 0.11). RM412 split written (half 2 and
  the flag in 0.9; the per-lane release probe parked with a gate row); RM404 goes first alone, RM385 builds behind its
  parameter in 0.10. Parked entries' status tokens now `a minor, parked`.
- **0.9's design decisions: written 2026-11-16** as dated "Decided for 0.9 (the pm)" blocks under the six entries in
  ROADMAP_0_9.md, each with what it rejected. No PROPOSAL_0_9.md from the pm: as with 0.8's PT2, the lead writes the
  build plan from decisions recorded under the items, and a second copy would drift. Main calls: proxy explicit and
  unset by default (`JUST_DNA_SNAPSHOT_PROXY_URL`), 3 s / 10 s timeouts, HF 429 is could-not-ask with no retry, one
  release pinned per session, the route recorded on every answer; enrich() does not read remotely in 0.9; the session
  is the holder's life; `enrich(clients=, sequences=)`; `parse_release` makes 0.9 touch the schema package by one
  function. **rsID index: local only, never published** (the registry's lead, 2026-11-16: both proxy boxes hold the
  Ensembl lane; "publish nothing"). The night trial is canceled: its only purpose was that decision; the builder
  measures size and build time.
- **RM385's trial (0.10): `waits until` 0.9's build is in review.** Its two questions are mine (a local seqrepo vs a
  GRCh38 FASTA; a lane vs a URI), settled by measuring both on real indels, unattended at night. Not tonight: the
  lead's 0.9 builders load the machine, and 0.10 cannot branch before 0.9 is cut. Needs a GRCh38 FASTA download
  (about 3 GB; /data has 256 GB free) and a seqrepo snapshot (larger); neither is on this machine (2026-11-16).
- **Desk in line, 2026-11-16 21:10Z (unattended):** open questions are #347 and #276 only; nothing waits in chat.
  **The lead's critic answered the same evening** (blocks A-H) as "Answers to the lead's critic" under RM430, RM437,
  RM404, RM431: a `remote.RemoteSnapshots` holder, opt-in (no holder, no remote read), declared-use gated per lane;
  one release per route per holder; truncation split to one key; one `SnapshotRouteUnavailable`; per-group licence by
  licensor; sticky groups; only `BatchResolver` public; `offline` outranks an injected proxy; the rsID index
  rebuild-only; ask 7 canceled. Handed to the liaison: ask the registry to put the release label in the proxy reply.
- **Remote-read trial: done 2026-11-15** (25bbdc6b): disk 0.02-0.1 s, proxy 0.2-0.4 s, HF 2-29 s and bound by its
  anonymous quota (3,000 requests / 5 min / IP); open the chromosome file, not the glob. Handed on: this machine's
  ClinVar cache has a new release.json over August parquet (triage, DM 640494788); the polygon's stale ClinPGx copy,
  an id-only Ensembl key answered 200, the cross-product batch (the registry, 640494791, info). DREAMS.md tracked
  (f4c7840a, over the lead's 2d87a9f5; the lead pushes both).
- **RM445's three calls (the lead, 2026-11-16), answered:** enrich never fetches beside a local build (could-not-run
  instead of withdrawing the label); an unfetchable `release.json` refuses (keep); the 0.8.3-0.8.7 sticky case is
  closed before the cut by comparing kept files with the listing (size, LFS sha256), else its own patch RM. The lead
  records them in the entry on build/RM445. **S156** folded into RM441 by triage; the pm's call: the enricher holds the
  per-table "newest release that could change it" (d0e71825); desk #326 updated.


- **Re-ask the trust register after the 1.0 cut** (`docs/TRUST.md`, the base rule for a repo whose code can
  reach private things). The maintainer, 2026-11-08, through the lead: "lowprio, PM to reask after 1.0". Not
  started; nothing is owed before then. `waits until` the 1.0 cut; then one question to the maintainer, chat or desk.
- **RM419 parked (2026-11-08, 88bda8eb)**: a patch, unparks on a reported rate-limit refusal with two of our clients
  in one process, or the registry saying it runs enrichments as threads in one process. That second half is the
  question put to the registry for RM418, still unanswered.
- **S133's five placed (2026-11-07), triage's ask.** RM401 and RM403 the next patch (RM401 probes the batch
  omission first). RM402 waits for RM401 and a re-measure; batching likely makes it moot. RM404 into 0.9 with
  RM385 (same seam); it does not meet RM396's gate, which stays parked. RM405 parked (offline is ~10 s a module).
- **S132's three placed (2026-11-07), triage's ask.** RM399 into 0.9 (a real sweep heard nothing of a corrected
  derivation; P3 met in prose only; near free). RM398 parked, gated on a planned snapshot move or a second report.
  RM400 the next patch on `main`, both halves; my default for its design half is to filter the recorded side the
  same way, adding no word. S132 noted on RM385 as its second case.
- reflected 2026-11-17: v0.1.136 (joined kit #486) and v0.1.161 (a new behavior issue); both neutral to good.
- reflected 2026-11-20: v0.1.199 (D193, a seat-builder handoff is the person's word): not exercised at this seat
  in seven days, neutral; kit #558.
- reflected 2026-11-21: v0.1.206 (the `nothing` button closes the wake, not the turn, kit #481): good, the pm checks
  its pending list after each press; one side effect, a bare press counts a mixed listing's actionable message as
  noise; kit #575.
- reflect after 2026-11-24: classes/base/BASE.md as of v0.1.231 (a claim of done is checked from where the person
  looks; a claim of absence carries its time; read 2026-11-17, no concern: the pm checks the desk and origin live).
- reflect after 2026-11-23: classes/base/BASE.md as of v0.1.224 (only a real fork goes to the person, kit #510; read
  2026-11-16, applied at once: desk #326-#329 withdrawn under it, #347 filed as the one real fork).
- **RM442 filed 2026-11-14** (0d84b3d6), the lead's ask: the AlphaGenome licence rows' three strings, a patch on
  `main`; caution sent on the AVI bar (June 2025 Output Terms' restriction 2 may still bind a downstream holder).
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
