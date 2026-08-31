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
