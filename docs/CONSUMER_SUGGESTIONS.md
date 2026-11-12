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

## S152 — RM438's wrong back-filled rsID reaches every catalog module the registry's 0.8 upgrade re-derived

**Reporter:** just-dna-lite (2026-11-12), an addendum to S151 / RM438, which are answered; filed separately so
their record stays as answered.

**What we know.** RM438: a coordinate-only row whose position holds two rsIDs in the split snapshot is back-filled
with the first rsID in string order, ignoring the row's genotype, with no warning (S151's CYP2D6*4 case).

**Why this is wider than one consumer.** just-dna-registry's 0.8 upgrade procedure (`registry upgrade`, its
UPGRADE.md § 0.28) re-derives every stored `resolution.csv` against the split snapshot (`enrich(rederive=True)`)
and publishes immutable successors. Any catalog module with a coordinate-authored row at a position dbSNP 157 now
shares between two rsIDs can therefore carry the wrong rsID in a published version, on both instances, and the
wrong rsID flows into what a reader sees (the dbSNP link, the cited studies joined by rsID, the report text).
Successors cannot be edited, so once RM438 ships the affected modules need re-deriving and a new successor each:
in effect a registry rebuild, or a sweep that finds coordinate-only rows at multi-rsID positions and checks the
back-filled rsID against the genotype first, to size it.

**What we did.** Nothing on the registry (not ours). We have not measured which catalog modules carry such rows.
On our side we hold off rebuilding or publishing modules on 0.8 until RM438 lands.

**Status — folded into [RM438](ROADMAP.md#rm438--resolve_variants-back-fills-a-position-only-row-with-the-first-rsid-at-its-chrom-start-ref-whatever-the-genotype-and-warns-nothing) as its S152 addendum; the pm decided it the same hour: one rule on both paths.** Your
worry is right in kind but not in its worst form. The registry's re-derivation runs through `enrich`, not through
`resolve_variants`, and `enrich` never picked silently. With S151's four rows and no single authored ALT, it gets
both candidates and writes `rsid=rs3892097`, `status=ambiguous` and `rsid_alternates=rs3892097,rs2517910443`. The
pick is the first by ALT order, which is right at CYP2D6*4 only because `A` sorts before `C…`. So no catalog row
carries a wrong rsID unflagged. But that pick ignores the genotype too, so an `ambiguous` row's chosen rsID may be
the wrong one. RM438 now narrows both paths by the row's `alts`, else by its genotype's alleles. `resolve_variants`
withholds when more than one rsID is left. `enrich` keeps pick-and-flag, so a row moves from `ambiguous` to
`resolved` only where exactly one rsID hosts the genotype. That changes published `resolution.csv` files, so it
will be declared as a corrected derivation. The exposure can be sized without a rebuild. The rows it can change are
published rows with `status=ambiguous`, authored by coordinate, with no single `alts`. That query is in the
entry, for the registry to run. Holding your own 0.8 rebuilds until RM438 lands is the right call.

<!-- triaged: RM438 S152 addendum (enrich flags, not silent; one rule both paths) · sha 8408ab19d5bf -->
