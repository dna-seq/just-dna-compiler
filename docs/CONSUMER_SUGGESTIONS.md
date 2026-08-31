# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S77

**Claim ids from here, never from what this file shows.** S1–S46 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.py --next        # scans this file AND the history file
```

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.


## S75 — `StudyRow` records a p-value and an effect size with no field naming the analysis that produced them, so a mispaired row is indistinguishable from a correct one

**Status — accepted and shipped in the tree as [RM140](ROADMAP_HISTORY.md#rm140--a-study-rows-p-value-and-effect-size-are-asserted-to-belong-together-and-nothing-recorded-what-either-came-from); the minimal ask, exactly as scoped.**
`StudyRow.statistical_test` is one optional free-form column shaped like `study_design` — the test or
model that produced this row's `p_value`/`effect_size`, and what it was adjusted for. Open, no
vocabulary, and **no gate**: your argument against your own candidate is the one we took, and it is
recorded in the roadmap entry rather than paraphrased. Column first, and possibly never a gate.

**Answered is not installable.** This is inside `0.7.0`, whose three `pyproject.toml` files are bumped
and whose tag is **not cut** — so it is committed, not published. [CHANGELOG.md](CHANGELOG.md)'s 0.7.0
heading is the record, and it will say so when that changes.

**One premise of the report does not reproduce, and it changes what you can do today.** Point (2) reads
`key.columns = (variant_key, pmid)` as meaning one paper's several analyses can be represented by
exactly one, the rest dropped by silent choice. Probed on a real spec: two rows sharing a variant and a
PMID **both reach `studies.parquet`**, and the duplicate is a *warning* — `duplicate_study_citation`,
which does not escalate under `strict`. Nothing was ever dropped. What was missing was the legibility,
not the capacity.

**So the one behaviour change is that warning, and it is what makes the column do something.** The
check reads a repeated key as *the same claim written twice*, which your two rows are not. Since RM140,
**both rows stating an analysis, with the two names different**, suppresses it. Nothing else does: an
absent `statistical_test` is *unknown*, and unknown against a stated value cannot establish that two
rows describe separate work — `a != b` would have suppressed on every blank cell and quietly retired
the check for every module written before the column existed. Neither stated, both the same, or one
stated and one blank in either order: warns as before, with the byte-identical message and code.

**What that buys you concretely.** Your SIRT6 row can now be two rows —
`0.36 / Fisher's exact (allelic)` and `0.75 / univariate logistic regression`, same variant, same PMID
— compiling with no duplicate warning, each self-describing. The discrepancy your README and
`logs/authoring.log` were holding has a place in the module itself. Your decision to withhold
`effect_size`/`effect_measure`/`effect_allele` where the reported OR is not reconstructible from the
paper's own counts is the right one and stays right; the column does not ask you to fill anything.

**`(variant_key, pmid)` is unwidened**, as you asked, and independently that is the legal answer:
`_KEY_FIELDS` drives `hints.key_fields` and the published `key.columns`, and re-keying a shipped
authored table is major-only under Principle 3. The check restates the pair rather than reading the
tuple, so the split is contained in one function and reaches no drafting provider.

**On quote verification being blind to this** — you are right, and the roadmap entry says so in those
terms rather than treating it as a limitation to be worked around. A quote cannot witness a number it
does not contain, and yours grounds the significance verdict correctly. That is a fact about what an
attestation is, not a gap in the pass.

Reproduced end to end before deciding: the duplicate-warning behaviour on a real spec, the round trip
carrying the column through `compile → reverse → compile` byte-identically (watched failing on each of
the two reverse touch points in turn), and two specs differing only in the *presence* of the column
hashing to the same `content_signature`, which is what makes it minor-legal. Written up in
[COMPILER § the analysis grain](COMPILER.md#one-paper-several-analyses-and-the-dedup-key-rm140),
[SCHEMAS](SCHEMAS.md), and the authoring skill's table reference.
<!-- triaged: 0.7.0 · sha 745de3190cb9 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A reproducibility benchmark: two agents, byte-identical prompts, same three DOIs, building one module
each. They overlapped on exactly one row — `rs117385980` from PMID 41249831
(`10.1038/s41598-025-24018-3`, SIRT6 and frailty) — and disagreed on it:

| run | `effect_size` | `effect_measure` | `p_value` | `stat_significance` |
|---|---|---|---|---|
| A | 1.42 | OR | **0.36** | not_significant |
| B | 1.42 | OR | **0.75** | not_significant |

### What we expected, and what is actually there

We expected one of them to be a misreading. Neither is. The paper reports **two different tests of the
same association**, and each run took a different one:

- **Table 3**, with Table 5 naming the test: allelic **Fisher's exact**, `OR 1.4`, `p 0.36`, on the 2×2
  allele table (non-frail T 8/376, frail T **0**/78). The paper states this one in its own prose.
- **Table 6**, `Univariate(Allele)`: **univariate logistic regression**, `OR 1.42`, `95% CI 0.18–11.67`,
  `p 0.75`. Five further adjusted models follow in the same table, down to `OR 0.96, p 0.98`.

So run B's row is internally consistent — OR, CI and p all from Table 6's single row. **Run A's is not:
it carries Table 6's `effect_size 1.42` beside Table 3's `p_value 0.36`**, and its own `conclusion`
cites Table 6's confidence interval, so the row names one analysis's estimate and another's p-value.

**Everything was green.** `validate_module(strict)` passed, `compile_module(strict)` passed,
`audit_module` raised nothing relevant, and `quotes_found` was satisfied — the provenance quote is
verbatim and correct, because it grounds the *significance verdict* ("not statistically significant")
and contains no statistic at all. A quote cannot witness a number it does not contain, so quote
verification is structurally blind to this class of error.

### The gap

`StudyRow` has `study_design` — *"e.g. meta-analysis, GWAS"* — which describes **the study**. There is
no field describing **the analysis**: which test, which model, adjusted for what. So:

1. A `p_value` and an `effect_size` on one row are asserted to belong together, and **nothing records
   or checks that they came from the same analysis.** `redundancy_bearing` lists neither, and there is
   no plausible place for such a check to live today because the facts it would compare are not
   recorded.
2. `key.columns` is `["variant_key", "pmid"]` with `rule: equality`, so a paper reporting several
   analyses of one variant can be represented by **exactly one** of them. The others are dropped by
   silent choice — and, as above, which one was chosen is not recorded either.

The consequence is not that a module is wrong. It is that a *correct* row and a *mispaired* row are
byte-indistinguishable to every consumer and every check.

### What we did meanwhile

Built a reference module carrying `p_value 0.36` (allelic Fisher's exact — the appropriate test given
a zero cell; the logistic MLE under near-separation is what the 65-fold CI is reporting) and
**withheld `effect_size`, `effect_measure` and `effect_allele` entirely**, because the reported ORs are
not reconstructible from the paper's own counts: with frail T = 0/78 and non-frail T = 8/368 the
T→frail odds ratio is 0 raw, ≈0.28 Haldane-corrected and ≈3.6 reverse-coded, none of which is 1.4. The
authors' own prose says the T allele "increased with robustness", i.e. the opposite direction to an
OR > 1. The second test and the discrepancy are recorded in the module's README and its
`logs/authoring.log`, which is the only place they can go.

### The ask, minimal

**One optional free-form column on `StudyRow` naming the analysis** — `statistical_test`,
`analysis_model` or similar, shaped like `study_design`: open vocabulary, no validation, no new check.
That alone makes `0.36 / Fisher's exact` and `0.75 / univariate logistic` two self-describing rows
instead of two indistinguishable ones, and it gives a future check somewhere to compare against.

**The key constraint is context, not a second ask.** We are *not* asking you to widen
`(variant_key, pmid)`; carrying one analysis per variant-paper is a defensible design and prose can
hold the rest. We mention it only because it is why the choice is silent: with one row available and
no field naming what was chosen, the discarded analyses leave no trace.

**A candidate we think is wrong**, argued against ourselves: a validator requiring the pair to come
from one test. It cannot be written — nothing on either side of the boundary knows what test a number
came from until the column above exists, and adding the column plus a gate in one step would make
every existing published row retroactively incomplete. Column first, and possibly never a gate.

## S76 — an interrupted `enrich` leaves a partial `resolution.csv` that nothing on disk marks as partial, and merge-not-clobber makes the next run trust it

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A reproducibility benchmark: six agents building modules in parallel, sharing one process. One was
authoring a GWAS module from a paper's supplementary workbook — 789 variant rows over **263 distinct
rsIDs** — and was killed by an external quota limit partway through `enrich`.

### What we found on disk

```
variants.csv      789 rows, 263 distinct rsIDs
resolution.csv    203 rows, 201 distinct rsIDs   <- written by the killed run
```

`resolution.csv` is a well-formed, complete-looking CSV. Every row in it is correct: real coordinates,
real VRS ids, `status=resolved`, `source=cache`. **Nothing in the file, its header, or any sibling file
records that it covers 201 of 263 subjects.** There is no marker, no row count, no "in progress"
sentinel, no partial flag. A reader — human or agent — opening this directory tomorrow sees a resolution
sidecar and has no way to tell it from a finished one without independently counting distinct rsIDs in
`variants.csv` and diffing the two sets.

### Why this is worse than an ordinary crash artifact

**Merge-not-clobber turns it into a silent wrong answer.** The documented behaviour is that an existing
sidecar is authoritative and merged rather than regenerated. So the natural recovery — "it died, run it
again" — merges onto the stale 201 and reports success. The 62 unresolved rsIDs are not retried, because
from the merge's point of view there is nothing to do for the rows already present and no record that
the others were ever attempted.

The correct recovery is to delete or capture-and-replace the sidecar first, which the enricher's own
docs do say. Our objection is not that the recovery is undocumented — it is that **the failure is
undetectable**. A consumer who does not already suspect a partial write has no signal to prompt them
into that recovery, and the one they will naturally reach for is the one that entrenches it.

There is a second-order effect we hit in the same directory: the run had written `verification.json`
before the interruption, so the module now carries an attestation over spec bytes that a completed
enrich will change. That part is at least loudly reported — the stale-verification warning fires — but
it means an interrupted run leaves two artifacts disagreeing about the module's state, one loud and one
silent.

### What we did meanwhile

Nothing automatic, deliberately: we surfaced it to the operator rather than repairing it, because
deleting a sidecar is destructive and `resolution.csv` can carry hand-curated `source="manual"` rows
that a blind delete would discard. Our own `refresh_sidecar` (capture, verify the capture, re-derive)
is the safe path and it exists precisely because this class of delete is dangerous. But it is a repair,
not a detector: it does not tell you the sidecar needs refreshing.

### The ask

**A completeness signal a reader can check without reconstructing the subject set.** The cheapest form
we can see is the one that costs no schema change at all: since `fetched_at` is already a column, an
interrupted write is in principle distinguishable from a complete one *if* something records what the
run set out to do. Concretely, one of:

1. **Write the sidecar atomically** — temp file, then rename — so an interrupted run leaves either the
   previous file or none, and never a half one. This is the smallest fix and needs no new field.
2. **Record the intended subject count** in the run's own output (a `logs/` entry, or a manifest-side
   counter), so `resolved 201 of 263` is recoverable after the fact.
3. **A cheap completeness check** callable against a spec directory: distinct authored rsIDs versus
   distinct resolved subjects, three-valued, with `unknown` where the authored set cannot be determined.

We think (1) alone would close the reported failure, and it is the one we would pick. (3) is more
useful but is arguably ours to build rather than yours — say so and we will, since it is a reading
rather than a schema fact.

**A candidate we argued ourselves out of:** having `enrich` refuse to start when a sidecar looks
short. It cannot distinguish a partial write from a legitimately smaller sidecar — an author who
resolved a subset deliberately, or injected a curated `resolution.csv` for exactly the rows they care
about, both of which are supported today. Refusing there would break a working practice to catch a
crash.
