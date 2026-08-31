# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S79

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


## S76 — WITHDRAWN as a duplicate of S66; kept for its one new measurement

**Status — the withdrawal is accepted and your closing question is answered YES; a real defect underneath the report is fixed and shipped in the tree as [RM141](ROADMAP_HISTORY.md#rm141--validate---strict-blessed-a-module-compile---strict-refused-whenever-the-resolution-table-was-partial).**
No apology needed — an item withdrawn within hours with a measurement attached costs less than one
nobody files. Three things, and the middle one is the reason this is not simply closed.

**Your closing question first, because you said no reply is needed if the answer is yes, and it is
yes.** `verification.json` is written inside the same commit block as `resolution.csv`, below the line
every refusal raises above. A killed run writes neither; a resumed run writes both. So the two
artifacts cannot disagree the way you describe, and the loud half you observed was 0.6.6's behaviour,
where the transaction did not exist. Closed.

**Your correction of 2026-08-31 is accepted, and it improves the item — this reply is amended for it
rather than left standing.** You are right that a complete write of an incomplete resolution set is not
S66's family, and right about the mechanism: a subject whose live request could not be made joins
`unreachable_rsids` and is written as **no row at all**, deliberately, so the artifact never states a
negative nobody established. Nobody-asked is a third state beside asked-and-failed and
asked-and-absent, and it is the one that leaves no trace in the table. So your 62 are unanswered, not
lost, and the same file comes out of a `best_effort` run that completes normally over a source it could
not reach.

That makes RM141 the closure by the right route rather than by luck. `validate --strict` reads the
table against the spec beside it, which is the only thing that can see a set complete as a file and
incomplete as an answer — and it is indifferent to *why* the rows are absent, which is what you want
given the cause turned out to be misdescribed. Two paragraphs below reasoned from the truncation
premise and are corrected in place.

**Your central mechanism does not reproduce, on either version — and this is worth more than the
withdrawal.** You describe merge-not-clobber as making the re-run trust the partial file and never
retry the missing 62. Probed directly: a module with three authored subjects and a table recording one
is re-run against a resolver that records every question asked. It asks about **exactly the other two**
and commits all three. The merge is over subjects the table records; a subject it does not record has
nothing to merge onto and goes to the source like any other. Measured on this tree **and on `v0.6.6`
built from its own tag**, so it is not something 0.7 fixed underneath you. Re-running would have filled
your 62. The recovery you avoided as dangerous was the correct one.

That also re-reads your arithmetic, and your correction re-reads it further: 203 rows covering 201 of
263 is a table **short of an answer** — not a wrong one, and, as you established from the sorted rsids
and the clean final newline, not a half-written one either. S66's incident replaced a restored 330-row
table with 162, a run that *overwrote* good rows. Yours recorded every answer it got. Either way the
next run continues from it, which is the property that mattered.

**And RM128's atomic write is therefore the answer to the failure you first described rather than the
one you had** — worth keeping in this reply, because the 0.6.6 writer you were running *did* truncate
in place, so it is what you would have met on the next kill. `layout.atomic_writer` stages a temp file
beside the target and `os.replace`s it: an interrupted run leaves either the previous file or none.

**What is real, and is ours.** `compile --strict` refuses a module whose variants still have no
position after resolution. `validate --strict` said nothing about it — so your partial table passed the
pre-flight clean and was refused by the compile immediately after, which is the
green-pre-flight-then-refusal shape our own parity rule exists to prevent, and the third time we have
broken it. It hid behind that rule's exemption: what stays compile-only is a check reading *resolved*
rows, and whether the table **can place** a row is arithmetic over bytes the pre-flight has already
loaded.

So the detector you asked for exists now, in the command your loop already runs first: `validate
--strict` refuses a partial table with the compile's verbatim error naming every unplaced subject,
`validate` warns per uncovered row, a module with no table at all says so once rather than per variant,
and `--no-resolve` silences it. A double-report was found while fixing it and is fixed too — both
passes reached the finding for one subject, measured at 24 warnings for 12.

**One thing we are refusing, and the reason generalises past this item.** A durable marker recording
that a run was partial is a fact about a **run** living in a table of facts about **variants**, on the
same axis that keeps `fetched_at` out of every fact set — and `resolution.csv` has been a pure build
product since RM124. It is also unwritable by the case that needs it: a killed process writes no
marker. The answer to "is this table complete" is a *reading*, computed from the spec beside it, which
is what `validate` now gives you.

**Answered is not installable.** All of it is inside `0.7.0`, bumped and **not tagged**.
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record.
<!-- triaged: 0.7.0 · sha 82cd8b8dde15 -->

**Withdrawn by the reporter, 2026-08-31, within hours of filing.** We filed this before finding
`S66` in the history file, which reports the same defect from the same consumer and is already
answered: the transaction, the `flock` and the atomic writers all shipped as `RM128` in 0.7. Our
apologies — the duplicate check we ran keyed on "partial" and "sidecar" and missed it.

**What is new and worth keeping is the arithmetic**, because `S66`'s worked example is a run that
wrote *nothing*, and ours wrote something that looked complete: a run killed mid-`enrich` left
`resolution.csv` with **203 rows covering 201 of 263 authored rsIDs**, every row correct, every
`status=resolved`, and nothing in the file recording that it is short. Merge-not-clobber then means
the natural recovery — re-run it — trusts the partial file and never retries the missing 62. That is
`S66`'s "valid-looking short file" with a number against it, and it is `RM128`'s case for the
transaction rather than a separate ask.

**One thing that is genuinely not covered by `RM128`, stated as an observation rather than a new
item:** the same interruption left `verification.json` attesting bytes a completed enrich would
change. That half is loud — the stale-verification warning fires — so an interrupted run leaves two
artifacts disagreeing, one that announces itself and one that does not. If the transaction already
stages `verification.json` alongside `resolution.csv`, this is closed too and no reply is needed.

The original report follows, unedited, because the prose is the record of what was observed.

## S76 (original text) — an interrupted `enrich` leaves a partial `resolution.csv` that nothing on disk marks as partial, and merge-not-clobber makes the next run trust it

**Status — answered in the withdrawal section above, which this is the evidence for.** Kept verbatim
and marked only so the ledger can see it: the reporter wrote it as one item under two headings, and a
top-level heading is the unit the ledger counts. No separate reply — the three findings (the gap-fill
does reproduce as *working*, `verification.json` is inside the commit, and the `validate`/`compile`
parity gap that is ours) are all above. **The reporter appended a correction here on 2026-08-31** —
the file was never truncated, which re-attributes the closure from RM128 to RM141 — and it is answered
in the withdrawal section, which this reply's fingerprint now covers.
<!-- triaged: 0.7.0 · sha f1c8681f3f6e -->

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

### Reporter's correction, 2026-08-31 — the file was never truncated, and that re-attributes the fix

Appended by the reporter after re-reading the preserved artifact, because we handed you arithmetic
that misdescribes it and part of your reply reasons from it. No new ask; no reply needed.

**Proven, from the file itself.** The 203 rows are sorted by rsid throughout and the last line ends
with a clean `\r\n`. The 62 absent rsIDs scatter across the whole alphabetical range of the authored
set (indices 0 and 262 among them), not as a tail. So it is a **complete write of an incomplete
resolution set**, not a half-written file — which we should have checked before calling it partial.

**That matches your code rather than contradicting it.** `_write_resolution_csv` runs once at the end,
and a subject whose live request could not be made joins `unreachable_rsids` and is written as **no row
at all** — deliberately, so the artifact never states a negative nobody established. The 62 are
missing because they were never answered, not because the write stopped.

**What it re-attributes.** This is not `S66`'s family after all: `RM128`'s transaction and atomic
write would not have prevented it, because nothing was interrupted mid-write. The same file is
produced by a `best_effort` enrich that completes normally over an unreachable source. So the thing
that closes it is `RM141` — `validate --strict` reading the table against the spec beside it — which
you landed anyway, and which is the right shape for a cause we described wrongly.

**Your two corrections stand, and one is now explained.** The gap-fill does work: we read
`need_pos`/`need_rsid` in the installed 0.6.6 and they skip only subjects `existing` covers, so the
62 go to the resolver like any other. Re-running was the correct recovery and we advised against it;
that advice is being retracted in our own docs.

**Inference, stated as such.** The likely cause of the 62 unanswered requests is our own benchmark
running six agents through one shared pacing gate. The enrich thread also outlives a dead client in
our wrapper, so the write plausibly completed after the agent that started it was gone. Neither is
measured.

## S77 — `enrich_dosage_sensitivity` writes a ClinGen licence row for a gene it did not cover, so a module carries an obligation for a source that contributed nothing

**Status — accepted in full and shipped in the tree as [RM142](ROADMAP_HISTORY.md#rm142--the-dosage-pass-declared-a-clingen-obligation-for-a-module-clingen-curates-nothing-of); your ask, verbatim, and it was a one-line guard.**
`merge_sources_file` is now behind `if covered:`. A pass that put no row in a table records no source.

Both halves reproduced. A single-variant `SIRT6` module: `covered=[]`, `missing=['SIRT6']`, zero
`gene_metrics.csv` data rows, and a `licensing.csv` with one `clingen` row in it. And the second cost,
which is the one worth the item — a module declaring `license: MIT` and using ClinGen for nothing warns
*declares MIT but annotation-layer sources report CC0-1.0*. Your two agents were adjudicating a
conflict that could not exist.

**Your framing (3) is the right one and is why this could not be fixed on our side of the compile.**
It is the shape of a check that cannot fail — and the compiler genuinely cannot catch it:
`_source_checks`'s orphan warning **exempts the `annotation` layer deliberately** (RM46), because
`sources.csv` is where an author is told to record a hand-read source, and warning about that would
mean compliance is noisy while omission stays silent. So an annotation-layer row nothing uses is quiet
by design, and the only party that knows whether it contributed is the pass.

**We checked the other passes, as you asked, and the answer is that this was `clingen.py` alone.**
`gene_metrics`, `frequencies`, `assertions` and `gene_validity` all pass `{row.source for row in out}`
to `record_source_terms`, so an empty pass records nothing by construction. Run offline over a module
they cover nothing of, `enrich_gene_metrics` and `enrich_frequencies` write no `licensing.csv` at all —
measured, not read off the code. `clingen.py` was the one member building a fixed row and writing it
unconditionally, which is the family's rule missed rather than a rule that needed inventing.

**One choice inside the fix is worth your knowing, because the obvious spelling is the dangerous one.**
The guard keys on `covered` — what *this run* contributed — not on `missing` being empty. `not missing`
would drop the declaration from every module carrying one uncurated gene beside a curated one, which is
a real obligation going unrecorded, and that is the direction that actually harms someone. It also does
not key on the table's contents, which include rows an earlier run merged in and already recorded.
Three tests: covers nothing, covers some, and a second lap where `covered` is empty because the work is
done and the row must stand.

**On your `covered: false` marker alternative** — we went the other way. It makes `sources.csv` carry
rows that are not declarations, so every reader of the table gains a case to handle, the compile gate
included, for a fact with no reader. Absence already says it. Your rejected candidate — the author
deleting the row — we agree is worse than the defect, for exactly the reason you give.

**And on the question you raised as possibly format's**: what `licensing.csv` means when a source was
consulted-and-empty. It means nothing should be there. The table answers *what does this module use*,
and "we queried this" is a fact about a **run**, on the same axis that keeps `fetched_at` out of every
fact set. `ClinGenResult.source_row` is still returned whatever happened, so a caller wanting the terms
of what was consulted has them — a different fact with a different home, which is your own distinction.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Written up in
[ENRICHER § a pass that contributes nothing records no terms](ENRICHER.md).
<!-- triaged: 0.7.0 · sha be41eff2ba06 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A single-variant module on `SIRT6` (rs117385980), authored by an agent from one paper. It ran the
fact passes, then compiled.

### What happened

The dosage pass reported, correctly, that it covered nothing:

```
dosage: missing: [SIRT6]
```

and nonetheless wrote a licence row into `licensing.csv`:

```
clingen,annotation,CC0-1.0,https://clinicalgenome.org/docs/terms-of-use/,,
"ClinGen (https://clinicalgenome.org), accessed via the gene-curation list",
CC0 public-domain dedication; attribution requested but not required.,
false,true,true,non_commercial,"clingen_dosage_30 Aug,2026",2026-08-30T23:57:03Z,
```

So the compiled module declares an obligation to a source that supplied **no data to any table**.
`SIRT6` is not on ClinGen's dosage curation list; the pass looked, found nothing, and still recorded
having consumed the source.

### Why it is worth fixing rather than shrugging at

1. **It is a false statement in a published artifact.** `licensing.csv` travels to the registry and
   is what a downstream consumer reads to decide whether a module is redistributable. A row saying
   *this module uses ClinGen* is not true of this module.
2. **It fires the licence-disagreement warning for no reason.** The compile emits *"module declares
   license X but annotation-layer sources report [...]"*, and an author then adjudicates a conflict
   that does not exist. We saw two independent agents spend real effort on exactly that in an earlier
   round, before we traced it here — and the honest adjudication in both cases was "compatible",
   reached by reasoning about a source that was never read.
3. **It is the same shape as a check that cannot fail.** A licence row that appears whether or not the
   source contributed says nothing about what the module contains.

We are not certain whether the same holds for the other fact passes when they cover nothing — we saw
it on dosage because that is the pass this module happened to run. Worth checking `gene_validity`,
`frequencies` and `literature` in the same breath.

### The ask

**Write the licence row when the pass actually contributes a row, not when it runs.** If the intent is
to record "we queried this source", then that is a different fact from "this module uses this source"
and wants a different home — the `logs/` entry, or a `covered: false` marker on the row — because
`licensing.csv` is read as the second thing.

**A candidate we think is wrong:** having the author delete the spurious row. It is machine-written
and would come back on the next pass, and an author deleting licence rows by hand is a worse habit
than the defect.

**Filed as an enricher item rather than a format one**, since the row is written by the pass, but the
question of what `licensing.csv` means when a source was consulted-and-empty may be format's to
settle.

## S78 — `compile --strict` builds a green artifact over a coordinate the enricher has already diagnosed as another assembly's

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A minimal spec, one variant, deliberately pasting a **GRCh37** coordinate onto a module declaring
`genome_build: GRCh38` — the ordinary shape of a paper that states its assembly once in the methods
and nowhere near the table an author is reading. `rs61849494` is `10:51613269 G/A` on GRCh37 and
`10:45982565 C/T` on GRCh38: **5.6 Mb apart and strand-flipped**.

```
rsid,chrom,start,ref,alts,genotype,state,conclusion
rs61849494,10,51613269,G,A,A/G,alt,Pasted verbatim from a GRCh37 paper.
```

### What each gate did, measured

**`validate_spec` — passes.** `valid: True`, zero errors, and the only warning is the unrelated
missing-closure one. Correct: it is offline and cannot know.

**`enrich(mode="strict")` — refuses, and this is exactly right.** `EnrichmentError`, no
`resolution.csv` written, module unchanged. Your diagnosis is better than anything we could have
asked for; all three lines fire and the second names the repair:

> Old-assembly coordinate — 1 row(s) — the authored ref is the GRCh37 base AND GRCh37 dbSNP records a
> variant starting there — the strongest of the three, and the one that names the rs-number to author
> instead (10:51613269 → rs61849494).

**`enrich(mode="best_effort")` — reports all three, then writes `resolution.csv` with the GRCh37
coordinate in it.** Also defensible: best-effort means proceed.

**`compile_module(strict=True)` — succeeds. This is the ask.** Handed that `resolution.csv`, a strict
compile builds the artifact, reports no error and no warning about the coordinate at all, and emits
only the missing-closure warning. The module is internally consistent, reproducible, and about the
wrong locus.

### The gap, stated precisely

Not "strict should catch reference mismatches" — the enricher's strict already does, and does it
well. The gap is that **`resolution.csv` carries no record that its rows were produced over a
diagnosed mismatch**, so the compiler cannot know, and a `--strict` compile therefore cannot refuse
what a `--strict` enrich already refused. The two strict flags mean different things about the same
defect, and the weaker one is the one that produces the published artifact.

We know your position that `--strict` is a determinism gate and not a correctness gate, and we are
not asking you to move that line generally. This is narrower: the correctness judgement **has already
been made** by another pass in the same toolchain, and is then discarded.

### The ask, and we would rather have your view than guess the shape

Any of these closes it; they are in our order of preference:

1. **Have the enricher record the diagnosis where the compiler can see it** — a column on
   `resolution.csv`, or a marker beside it, saying this row was written despite a reported
   ref/assembly disagreement. Then `compile --strict` can refuse on a fact rather than on a re-run of
   the check, and `--no-strict` still builds.
2. **Have `compile --strict` re-run the rsid↔coordinate agreement it already has the data for** —
   `resolution.csv` holds both the authored coordinate and the resolved one, so the disagreement is
   visible without any network. This is the smallest change but it does put a correctness judgement
   inside the determinism gate.
3. **Refuse nothing, but make the compile *warn*** — strictly better than silence, and it costs the
   line nothing. This is the floor, not our preference: an author who did not read the enrich report
   is not obviously going to read a compile warning either.

**A candidate we argue against, having tried it:** telling authors to always run strict enrichment.
That is what we will do in our own skills, and it is not sufficient — `best_effort` exists for good
reasons (an unreachable Ensembl must not be a failure), and a module authored under it stays wrong
forever with every subsequent gate green. The defect is that the diagnosis is thrown away, not that
somebody chose the wrong mode.

### The general form of the ask, which is bigger than one coordinate

Sharpened by our owner after reading the measurement above, and it subsumes options 1–3:

> **A `compile --strict` over a `resolution.csv` produced by a `best_effort` enrichment should be
> blocked.**

The reasoning is about what the two strict flags jointly promise, not about assemblies. `strict` on
the enricher means *every row was checked against the reference and none disagreed*. `strict` on the
compile means *this artifact is reproducible*. A module that ran `best_effort` and then compiled
`--strict` gets the second stamp without the first ever having been earned — and nothing in the
artifact records which of the two happened. The published module is indistinguishable either way.

That makes the mode a **property of the derived sidecar**, not of the run that happened to produce
it: `resolution.csv` should say which mode wrote it, and `compile --strict` should refuse a sidecar
that does not carry the strict stamp. Refusal, not a warning, is what our owner asked for, and the
argument for it is that the alternative has already failed once — the enricher's diagnosis is
excellent and it still reached a green artifact, because a report nobody is required to read is not a
gate.

This also fixes a case our probe did not cover: **any** ref-mismatch class, not just an old assembly.
`best_effort` is the mode that proceeds past all of them.

**We are aware this is a behaviour change with a migration cost**, and we are not pretending
otherwise: every existing `resolution.csv` has no mode stamp, so the rule needs an
absent-means-unknown reading rather than absent-means-best_effort, or it retroactively blocks
recompiles of published modules. `None` is not `False`, and this is that rule at the artifact level.
Whether that is worth it is yours to weigh — we are stating the ask plainly because the weaker
options above all leave the same artifact publishable.

### Our side

We default to `best_effort` and expose `strict` as a flag, so our own callers meet this. We are
adding the assembly-triage prose to two skills and pointing them at rsID-only authoring, which
prevents the paste rather than catching it. Neither fix reaches a module already authored, and
neither is a substitute for the sidecar knowing how it was made.
