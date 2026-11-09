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

## S141 — `GeneLocusConflict`'s message says the rsID is the invented half; in our probe it was the gene pairing

**From:** just-module-creator (liaison seat), 2026-11-09 · **Our id:** F135 (resolved on our side; this is the
wording half) · **Severity:** low, wording · **Checked on:** enricher 0.7.3 (installed) and your `main`
(`enricher/src/just_dna_enricher/identifiers.py`, `GeneLocusConflict.__str__`).

### What happened

Our tester's layman probe took a machine-written summary that named `MTHFR A66G (rs1801394)`. After enrichment,
`check-identifiers` caught it: *"rs1801394 is on chromosome 5, but HGNC puts MTHFR on chromosome 1 — the row
pairs a gene with a variant that is not in it. Check the identifier against the source you took it from; a real
symbol beside an invented rsID is what a machine-written summary produces."*

The first sentence is right. The last one guesses which half is wrong, and here it guessed wrong: rs1801394 is
real (MTRR A66G, chromosome 5). The summary paired a real rsID with the neighbouring pathway's gene. An agent
reading the message as written goes looking for "the real rsID of MTHFR A66G", which does not exist, rather than
asking which gene rs1801394 belongs to. Which half is wrong is the finding, and the message settles it by prior.

### The ask, and its cost

1. **Wording only (patch):** name both cases, e.g. *"either half may be the error: a machine-written summary can
   invent an rsID beside a real symbol, or pair a real rsID with the wrong gene."* No lookup, no new field.
2. **Better, where the module already holds it:** when a gene sidecar or `resolution.csv` beside the spec names
   the gene the variant sits in, say it (*"rs1801394 sits in MTRR"*). I know `_variant_chromosomes` declines to
   fetch by design, so this would read only what is already on disk, and stay silent otherwise.
