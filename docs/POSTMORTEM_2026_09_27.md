# Postmortem — the indel anchor that every gate passed (2026-09-27)

**Status: open.** The findings below are measured. Of the mitigations in § 5, only the residual
gates are being built (by the triage seat, § 6.4); the rest are proposals the maintainer decides.
The backlog in § 6 is worked by a separate seat. This file is a record of one incident and the sweep it
prompted. It is not a rule book: a rule adopted from it goes into the runbook it governs, with its
guard, and this file keeps only the why.

## 1. What happened

On 2026-09-27 a consumer (`just-dna-lite`) filed three reports in one day, each a wider framing of the
last:

- **S117.** Our Ensembl snapshot places `rs8176719` (ABO O1, MAF 0.34) at `9:133257520 G>GC`, which
  is a different haplotype from the `521 T>TC` that ClinVar, dbSNP, gnomAD and real callers carry.
  The snapshot copies Ensembl's own VCF dump faithfully. The dump disagrees with Ensembl's REST
  (dump POS = REST `end` − 1, 7 of 7 checked). Filed as RM267 and RM268; RM268 shipped the same day.
- **S120.** The larger class, about 50,000 insertions and 80,000 deletions, is a harmless respelling
  one base right of left-alignment. But the format names no normalization convention, the compiler
  cannot apply one, and a left-aligned VCF misses the row silently. Carriers of CCR5-Δ32 were dropped
  from a real module. Filed as RM270.
- **S121.** The enricher resolves every coordinate from one authority and checks it against that same
  authority. The ClinVar snapshot that would have disagreed was loaded in the same run and used only
  as a fallback. Folded into RM267.

None of this was new. **The +1 respelling was found and recorded on 2026-08-03 as RM31**, marked
shipped, and its consumer-facing half was lost. The user's question was the right one: how does a
repository with 4,745 tests and a documented lesson about exactly this failure let it through for
three minor versions?

## 2. Timeline

| date | event | what could have caught it |
|---|---|---|
| 08-01 | "Enricher co-authoring" parked in the idea-book, headed *recorded so they are not re-proposed* | — |
| 08-03 | **RM31**: SHOX's deletion is `X:634690 AGAG>AG` in Ensembl and `X:634689 CAG>C` in ClinVar. Fixed by making our own comparison tolerant (`parsimony_reduce`), shipped ✅. The residual says *"a consumer joining the genotype against a VCF … will still miss"*, points at the 08-01 bullet (which never mentions it), and offers the consumer a workaround no consumer document ever carried. A second residual, *"the enricher can still settle it with seqrepo (not yet wired)"*, survives only as a code comment (`enrich.py`, *"the remaining half of RM31"*) | closure with an open residual |
| 08-06 | `@start-1based`: an external author shifts 3,038 rows by one base and every gate passes. Recorded lesson: *"validate-by-redundancy assumes independence"* | the same class, recorded as a gotcha line and not as a procedure or a test |
| 08-14 | `check_rsid_coordinates` lands and calls every indel position difference *undecided*, citing RM31 | a tolerance built on the leaked residual; it counts nothing and nothing owns what it abstains on |
| 09-12 | CONSUMING.md is written for consumers, without RM31's workaround | the promise had a natural home and did not land |
| 09-27 | A consumer measures ~130,000 affected alleles and generalizes it three times in a day | — |
| 09-27 | The triage pass that answered S117 cites *"an indel re-anchors legitimately (RM31)"* in RM267 as justification, without reading RM31's residual | a pointer read as an authority, during the incident itself |

## 3. The blindspots

Each step above was locally correct. RM31 really fixed the comparison it named. The parked bullet
was parked for a good reason. *Undecided* is the right verdict for an indel position difference.
Digest stability is a real concern. What was missing was anything checking the **handoff** between
steps. Four blindspots, each a procedure gap rather than a code bug:

### B1. A closure can carry an open defect

Moving an entry to ROADMAP_HISTORY checks that the thing named was fixed. It does not check that
what the entry *admits it did not fix* has somewhere to live. The sweep (§ 4) found the same shape
about 40 times: *"wants its own item"*, *"it wants its own number"*, *"belongs to RMn"* where RMn is
closed, *"see the residual below"* where the residual does not say it, and, worst, **"filed rather
than improvised" with nothing filed** (RM192). An unnumbered idea-book bullet is not a home. Eight
documents point at the co-authoring bullet as the home of a live defect, and it names none of them.

### B2. Checks that witness themselves

Every check positioned to see the anchor error either compared a source with itself or had been made
tolerant on purpose:

- `parsimony_reduce` (RM31) makes a respelling invisible *inside* the pipeline. That was the fix, and
  it guaranteed nothing downstream could report the disagreement.
- `check_rsid_coordinates` abstains on every indel position difference. It does not count the
  abstentions and does not hand them to anyone.
- The reference-allele check passes a wrong anchor by construction, because the anchor base is a
  real genome base.
- The ClinVar snapshot is loaded in the same run and consulted only for rows Ensembl missed. The
  code comment gives the reason as keeping `artifact.digest` from moving, the one reason the house
  rules say is never sufficient on its own.

The repository had already written this lesson down (`@start-1based`, 08-06). It was written as a
sentence in the gotcha book, which no test reads.

### B3. Nothing does what a consumer does

4,745 tests compile, reverse, recompile, and cross-check tables against each other. None joins a
compiled artifact against an **independently produced, normalized VCF**, which is the consumer's
entire operation. The blind re-derivation audits derive the docs from the code, which is internal
again. And no one measured the class when it was found. RM31 was one SHOX row; the snapshot-wide
count (about 130,000 alleles) was first measured by a consumer 55 days later.

### B4. Records go stale behind the pointers that cite them

A reply is correct when written and then points at a record nobody keeps current. Six replies
(S75–S80) tell consumers *"CHANGELOG.md's 0.7.0 heading is the record"* of whether a release was cut.
That heading still says *"being built … not yet cut"*, and v0.7.0–v0.7.2 are tagged. A shipped entry
is not updated when a later item finds what it missed (RM247 → RM254). A reference example keeps
telling authors a feature does not exist after it ships (the HTT README → RM47).

### Contributing: lessons become lines, not guards

`@start-1based` became a gotcha line. RM31's residual became a paragraph. The standing memory *"the
gotcha book does not catch regressions"* is itself a line. Every one of them was true and none of
them could fail a build. The repository's own rule, *assert an equality over a walked set, never a
count in prose*, was applied to code registries and never to its own records.

## 4. The sweep

Five read-only agents read every closed record: ROADMAP_HISTORY in two halves, the 0.6 and pre-0.6
history files, the closed proposals with the 0.7 deferral file and the idea-book, and every
maintainer reply S1–S116. The maintainer verified the highest-impact findings by hand before they
were cited here. The raw tables are not reproduced; each row below names its source.

| slice | closed records read | homed or later fixed | deliberate, with a reason | leaked |
|---|---|---|---|---|
| ROADMAP_HISTORY RM176–RM247 | ~60 entries | 13 | ~30 | ~17 (10 unhomed or false pointer, 7 plausible) |
| ROADMAP_HISTORY RM70–RM175 | ~65 entries | 17 | 23 | ~10 |
| 0.6 and pre-0.6 history | 85 entries | 17 | 27 | ~11 |
| proposals, 0.7 deferrals, idea-book | 9 proposals + 2 files | 9 | 12 | ~14 |
| replies S1–S116 | ~360 commitments | ~340 kept | — | 21 |

About one closure in seven carries something that leaked. The 0.7 → 0.8 deferral rollover, by
contrast, carried all ten items, because it was a mechanical list.

**What leaked, sorted by who gets a wrong answer:**

*A consumer or author gets a silent wrong answer:*

- **The indel anchor, four more times.** RM171's MITOMAP increment is an exact join, so a MITOMAP
  allele ClinVar holds at another anchor drafts as new. RM153's `anchor_indel` calls prefix-anchoring
  *"the left-aligned representation"*, which is false inside a repeat (CIViC-drafted indels). RM134's
  20,131 PubMind indels are marked *normalization unverified*. RM31's genotype-frame half is in
  neither RM270 nor CONSUMING.md.
- **RM31's seqrepo half.** A same-size different-content indel is kept as *undecided*, so a consumer
  can get an annotation joined to a different event. It lives only in a code comment.
- **RM107.** Six derived fact tables have no duplicate rule, so two contradicting rows under one key
  compile silently. *"It wants its own item"*; never filed.
- **RM170, STRchive.** `evidence` is dropped at parse, so a locus STRchive grades *Refuted* (DMD)
  drafts looking exactly like a solid one.
- **TABLES.md** says `weights` keeps a *sorted* allele list, which is false for phased rows. That is
  S30's own mis-join, re-invited by our docs.
- **S56.** The compiler's `quote_counter_stale` warning says to re-run the literature pass, which does
  nothing for a pinned row. The fix we said we *"would still like"* was never filed.
- **S75–S80.** The CHANGELOG 0.7.0 heading still says *not yet cut*.
- **S81.** We promised to write down that a *patch* can add an authored column. It was never
  written, so readers pinned to a minor assume the authored schema cannot change within it.
- **RM218.** The CLI cannot pass `ensembl_reference`, so every CLI-compiled manifest has a null
  `ensembl_reference`. This is written in COMPILER.md and tracked nowhere.

*Something is promised and does not exist:* RM192's Atlas retry and pacing (*"filed"*, not filed);
RM166's licence diversification and `clinicalVariants` adoption (*"its own number"*); RM72's run-level
skip record; RM171's rCRS anchoring pass; RM39's ClinGen snapshot; RM38's PharmVar personal-key axis
(points at RM27, closed); RM50's `LiteratureRow` key (points at RM50, closed); RM134's terms question
to WGLab/CHOP, never asked.

*Stale but harmless:* SCHEMAS says *"exactly five"* row models carry `source` when there are nine; the
HTT README says bin bounds cannot be cited; RM247 never names RM254; the idea-book's `stats.genes`
bullet still reads as open; RM70 has two TOC rows.

## 5. Mitigations — proposed, for the maintainer to decide

Each one names the procedure it changes, the guard that makes it fail a build rather than rely on
memory, and a cost. Ordered by what would have stopped this incident earliest.

| # | change | guard | where it lives | cost |
|---|---|---|---|---|
| M1 | **A closure states its residuals.** Every entry moved to ROADMAP_HISTORY carries a `**Residuals**` line: `none`, or each residual as an open `RMn`, or `won't fix — <reason>`. An idea-book bullet is not a home. | A test walks ROADMAP_HISTORY entries added after the cutoff and fails on a missing line, on an `RMn` that is not open in RM_TOC, or on *"filed"* with no `RMn` beside it | RELEASE_CYCLE (closing an item), CONSUMER_TRIAGE_LOOP § Step 2 | 2 hours |
| M2 | **Legacy residual phrases are pinned.** The phrases the sweep keyed on (*wants its own item/number, filed rather than, belongs to RMn, still owes, not yet wired*) need an `RMn` in the same paragraph that resolves to an open item or a later ship | The same walker over all three history halves and the proposals, with today's ~40 hits as a burned-down allowlist that may only shrink | the test from M1 | 1 hour on top of M1 |
| M3 | **A check names its witness.** A verification record states the source of what it checks and the source it checks against. When they are the same source it reads *self-consistent*, never *verified*. A tolerance that makes a class undecided counts that class and publishes the count. | A registry field on every check, asserted by an equality over the check roster (`@registry-completeness`) | ENRICHER § the check table; SCHEMAS `VerificationRecord` | a minor, about a day |
| M4 | **One test does what a consumer does.** Compile the reference examples and join them against an independently produced, left-aligned VCF (a committed ClinVar VCF slice, normalized with `bcftools norm`). Assert that every variant expected to match does. | The test itself; it would have failed on 2026-08-03 | `compiler/tests/` | 2 hours |
| M5 | **Measure the class before closing.** A defect found on one row is counted across the relevant snapshot before its entry closes, and the count goes in the entry | M1's closure line gains a `**Class measured**` field | CONSUMER_TRIAGE_LOOP § Step 0b | none beyond the habit |
| M6 | **A workaround handed to a consumer lands in a consumer document in the same commit.** A reply may not be the only place a workaround exists | Reviewer rule, plus the reply sweep (§ 4 slice 5) re-run before each cut | CONSUMER_TRIAGE_LOOP § Step 3 | none |
| M7 | **A release cut rewrites every heading that says *being built*.** And a reply never cites a heading as *the record* of a state that will change; it cites the tag | A test: no CHANGELOG heading for a tagged version says *not yet cut* | RELEASE_CYCLE § the cut | 30 minutes |
| M8 | **The sweep is the pre-cut backstop.** The five-slice sweep runs before every minor cut, as a named step of the blind re-derivation | The step exists in BLIND_REDERIVATION with its prompts | BLIND_REDERIVATION | about 1 hour of agent time per cut |
| M9 | **Before citing an RM as justification, read its residuals.** And when several items in one triage pass touch one mechanism, file one root item and relate the others | Reviewer rule | CONSUMER_TRIAGE_LOOP § Step 1 | none |

M1, M4 and M7 are the cheap, mechanical ones. M3 is the only one that changes a schema, and it is
the one that answers B2 directly.

## 6. The backlog

Two seats work this, and neither takes the other's items (one purpose per session):

- **The postmortem seat** (a separate interactive session with the maintainer): § 6.1–§ 6.3.
- **The triage seat** (the session running CONSUMER_TRIAGE_LOOP.md): § 6.4, the residual gates.

Line numbers are as of commit `58ce41d`. Every row came from the sweep; the ones marked ✔ were
re-checked by hand before this file was written. The rest are candidates, and **each is reproduced
before it is filed or fixed** (CONSUMER_TRIAGE_LOOP § Step 0b): the sweep found where to look, never
what is true. File each RM with `.claude/rm-next.py`, and read CONSTITUTION.md in full before sizing
any of them.

### 6.1 File as RMs — someone gets a silent wrong answer

| id | what | source | note |
|---|---|---|---|
| P1 | **Filed as RM273** (three instances reproduced; the RM31 genotype-frame half goes to D9). **The indel anchor, four more instances.** RM171's `mitomap_miss` exact `(start, ref, alt)` join drafts a MITOMAP allele ClinVar holds at another anchor as new. RM153's `anchor_indel` calls prefix-anchoring *"the left-aligned representation"*, false inside a repeat (CIViC). RM134's 20,131 PubMind indels are *normalization unverified*. RM31's genotype-frame half (`C/CAG` beside `ref=AGAG`) is in neither RM270 nor CONSUMING.md | ROADMAP_HISTORY.md:3858-3860, 3931-3932; :4980-4987 + `clingen_allele.anchor_indel` docstring; :6788-6789 + PUBMIND_ASSESSMENT.md:519-520; history/ROADMAP_HISTORY_PRE_0_6.md:357-363 | Decide one item vs folding into RM270. Read **RM271** (peer, 2026-09-27: both Ensembl rungs serve `dbSNP_novariation`, `<.>`, empty `alts`, `N` runs as resolved) and RM267/RM270 first; they are one resolution chain |
| P2 | **Filed as RM274.** **RM31's seqrepo half.** A same-size different-content indel pair is kept as *undecided*, so a consumer may get an annotation joined to a different event. It survives only as a code comment | PRE_0_6.md:338-340; `enrich.py` *"the remaining half of RM31"* ✔ | RM270's `vrs_id` comparison may settle it; check before filing separately |
| P3 | **Filed as RM275.** **RM107: six derived fact tables have no duplicate rule.** Two contradicting rows under one merge key compile silently. *"It wants its own item"*, never filed | history/ROADMAP_HISTORY_0_6.md:141-145; `compiler._TABLE_DUPE_KEYS` | Check whether RM124's keying covers any of them |
| P4 | **Filed as RM276.** **RM170, STRchive.** `StrchiveLocus` drops `evidence` at parse, so a *Refuted* locus (DMD) drafts looking exactly like a solid one | 0_6.md:2617-2621, 2646-2650 | The entry calls it a source-adoption question |
| P5 | **Filed as RM277.** **S56: the compiler's remedy does nothing.** `quote_counter_stale` says to re-run the literature pass, which skips pinned rows. The recompute-on-merge fix we said we *"would still like"* was never filed | CONSUMER_SUGGESTIONS_HISTORY_0_6.md:3613-3616; `compiler.py` `quote_counter_stale`; `literature.py:854, :977`; `cli.py:795` | The warning text alone is a patch |
| P6 | **Filed as RM278.** **RM218: the CLI cannot pass `ensembl_reference` or `ba1_threshold`**, so every CLI-compiled manifest has a null `ensembl_reference` | ROADMAP_HISTORY.md:2049-2053; COMPILER.md:1820-1831 | |
| P7 | **Filed as RM279** (numbered, parked on a precision measurement). **D14: swapped or contradicted `conclusion` cells go unflagged** (`coronary` `rs17514846`) | ROADMAP.md idea-book, consumer-note D14 | Self-carried in the idea-book with a reason; decide whether it now earns a number |

### 6.2 File or close — promised, pointed at, never homed

| id | what | source |
|---|---|---|
| P8 | **Filed as RM280.** RM192 says the Atlas client's retry and shared pacing were *"filed rather than improvised"*; nothing was filed | ROADMAP_HISTORY.md:3076-3078; PROPOSAL_0_7_PT4.md:374-378 |
| P9 | RM166: licence diversification for the PGx lane, and the `clinicalVariants.zip` adoption (*"it wants its own number"*) | ROADMAP_HISTORY.md:4196-4198, 4222-4227; PROPOSAL_0_7_PT2.md:557-560; CHANGELOG.md:2674-2676 |
| P10 | RM175: nothing notices `summaryAnnotations.zip` itself going quiet | ROADMAP_HISTORY.md:4144-4161 |
| P11 | RM72: a run-level place for a skip (*"a separate question and was not opened"*) | history/ROADMAP_0_7.md:252-254 |
| P12 | RM171's rCRS anchoring pass for `:` deletions, the `VUS*` revisit, the 388 unrated misses | ROADMAP_HISTORY.md:3927-3932; PROPOSAL_0_7_PT3.md:240-245 |
| P13 | Pointers to closed items: RM38's PharmVar personal-key axis → RM27; the idea-book's served-answer redistribution → RM27; the 1.0 tracker's `LiteratureRow` key → RM50; RM32's PAR multi-build half → RM15, which does not mention it | PRE_0_6.md:801-805, :627-628; ROADMAP.md idea-book (S94 peer rung); ROADMAP.md 1.0 tracker `StudyRow.pmid` |
| P14 | RM39's ClinGen snapshot; RM101's list-shape exception contract, recorded only in a test's exemption block | PRE_0_6.md:893-894; `test_pass_exception_contract.py:276-326` |
| P15 | Smaller: RM163 `training_ancestry` description says *"validated in"* (`pgs.py:66`); RM136's checks not wired to the answered set; S60's *vindicated* signal on 1 of 7 overridable tables; S99's skip sentence (`licensing.py:994`); RM85's catalog-side ask; RM123's `clin_sig`-on-binning non-decision; PROPOSAL_0_5 G2 (CPIC activity bins, ClinPGx archives) | ROADMAP_HISTORY.md:4470-4471, :5471-5477, :7066-7067; CONSUMER_SUGGESTIONS_HISTORY_0_6.md:4069-4072; CONSUMER_SUGGESTIONS_HISTORY.md:4237-4240; 0_6.md:302-305; PROPOSAL_0_5.md:242-246 |
| P16 | **Outbound, the maintainer's own:** RM134's terms question to WGLab/CHOP, never asked; the ClinPGx and MITOMAP HuggingFace republish; RM186's legacy ClinVar file on HF | ROADMAP_HISTORY.md:6851-6856; PROPOSAL_0_7_PT3.md:254-256; ROADMAP_HISTORY.md:3933, :3367-3389 |

### 6.3 One documentation patch — nothing to decide

| id | fix | source |
|---|---|---|
| D1 | **Done.** TABLES.md says `weights` keeps a *sorted* allele list; phased rows keep authored order ✔ | TABLES.md:43-44; `schema/tests/test_split_genotype.py` |
| D2 | **Done.** The CHANGELOG 0.7.0 heading still says *being built … not yet cut*; six replies (S75–S80) cite it as the record ✔ | CHANGELOG.md:2839-2841 |
| D3 | **Done.** SCHEMAS says *exactly five* row models carry `source`; there are nine ✔ | SCHEMAS.md:1619 |
| D4 | **Done.** The HTT README says bin bounds cannot be cited and sends authors to RM47, which shipped ✔ | reference_examples/htt_repeat_expansion/README.md:73-84 |
| D5 | RM247's entry never names RM254, the protobuf failure its guards missed | ROADMAP_HISTORY.md `## RM247` |
| D6 | The S81 sentence, never written: a patch can add an authored column under `extra="forbid"`, so a reader pinned to a minor cannot assume a fixed authored schema | CONSUMER_SUGGESTIONS_HISTORY.md:2807-2811 |
| D7 | COMPILER.md's annotations key lacks `genotype` (S29); SCHEMAS' `provenance.json` section still calls a closed question unsettled (S52) | COMPILER.md:1341; SCHEMAS.md:2379-2386 |
| D8 | The ENRICHING guide never says to `--rederive` or delete `resolution.csv` after an upgrade that corrects it (RM268, RM251) | ENRICHING.md:22 |
| D9 | Workarounds that exist only in a reply: `PacingGate` is not a concurrency limit (S15); billing egress on the five clients with a private `_gate` (S95); an older `verification.json` is not re-examined (S78); the RM31 genotype-frame reduction for consumers | CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md:1084-1087; CONSUMER_SUGGESTIONS_HISTORY.md:3926-3929, :2471-2473 |
| D10 | Small: the 0.6.3 CHANGELOG entry's forward pointer (S45); RM84's *which build* reason (S34); `weight` authored zero times, beside its 1.0 review (S36/RM92); `public_key` in the schema README (S34); RM70's duplicate TOC row; the idea-book `stats.genes` bullet, fixed by RM121; the co-authoring bullet, which eight documents lean on and which names none of their defects | history/CHANGELOG_0_6.md:454-455; ROADMAP_0_8.md RM84; ROADMAP.md 1.0 tracker `weight`; schema/README.md; RM_TOC_000_099.md:183, :253; ROADMAP.md idea-book |

The procedure mitigations M3–M6, M8 and M9 (§ 5) are also this seat's, decided with the maintainer.

### 6.4 The triage seat's share: the residual gates

M1 (a closure states its residuals), M2 (the legacy phrases pinned, with an allowlist that may only
shrink) and M7 (no CHANGELOG heading for a tagged version says *not yet cut*). They are tooling, they
guard the step this incident leaked through, and the triage loop is the process that closes most
items.

**Done 2026-09-27**, all three in `schema/tests/test_closure_residuals.py`: M1 as `1b45201`, M2 as
`917b092`, M7 as `2c38031`, each shown to fail on the defect it guards. M2's list
(`schema/tests/data/residual_phrases_legacy.txt`) holds 11 `leak` rows, and they are § 6.1–6.2 items:
homing one deletes its row, so the count of `leak` rows is this backlog's progress.
