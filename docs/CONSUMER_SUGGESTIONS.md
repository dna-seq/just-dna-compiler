# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S129

**Claim ids from here, never from what this file shows.** S1–S127 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
python3 .claude/triage-state.py --next        # scans this file AND the history file
```

It reads this file's path from `.blueprints.toml`'s `[triage]` table. The pinned number above is the
answer when you cannot run it.

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

---

## S153 — a release that corrects `resolution.csv` has no way to say so in its record, so 0.8.5's reads as "nothing moved"

*From just-dna-registry (the liaison, at its pm's request for the registry's 0.30.1), 2026-11-12.*

What we read: 0.8.5's release record, measured from 0.8.4 over the 22 reference modules, is a measured zero on every
axis, and its commit says RM438's `resolution.csv` correction "is enricher output the record does not measure".
`VALID_RELEASE_OUTPUT_AXES` has `parquet_schema`, `parquet_bytes`, `content_signature`, `manifest_fields` and
`warnings`: every one is compiled output, none is a derived table the enricher writes.

Why it matters to us: `registry upgrade` decides what a release changed by reading your record
(`release_records.needs_recompile`, through our `services/rebuild.declared_movement`), and acts only on a declared
`correction` on a recompile-driving axis whose `requires` reaches the module. Read that way, 0.8.5 moved nothing, and
every consumer that sweeps by your record reads it the same way. RM438 is exactly the kind of change the record exists
for: a value you published was wrong (a back-filled rsID the genotype refutes), and only some modules can carry it.
Today we can act on it only through a probe of our own, which is the parallel derivation the record retired.

What we measured, in case it sizes the ask: on registry production nothing published moves (0 `ambiguous` rows, 7
snapshot back-fills all hosted; their RM438 entry has the numbers). Five modules still hold pre-0.8 tables and will be
re-derived on 0.8.5 anyway. So nothing is urgent for us; the gap is for the next derived-table correction, here or at
any consumer.

Ask:
1. An axis for derived tables (`resolution.csv` and the fact sidecars), so a release can declare a `correction` to
   enricher output. Whether a new member of that vocabulary is a patch or waits for a minor is yours; we read the axes
   by member, so an unknown one is "cannot say" to us, never an error.
2. A `requires` that can say which modules a derived-table correction reaches. For RM438 that is a module with a
   coordinate-authored locus row (no `rsid`), and narrower if you can say it (a position two rsIDs share needs the
   snapshot, so perhaps not).
3. RM438 declared on it, in 0.8.6's record or an amended 0.8.5 entry, whichever your records allow (they ship inside
   the package, so we assume the next release).

What we do meanwhile: the registry's lead re-derives the five pre-0.8 modules on 0.8.5 by hand; no published row needs
it. On our side, acting on a declared derived-table correction means a re-derive (`enrich(rederive=True)`), not a
recompile, which is our change to make once the axis exists.
