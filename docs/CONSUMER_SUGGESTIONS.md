# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S90

**Claim ids from here, never from what this file shows.** S1–S89 are all answered and live in the
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

---

---

## S90 — a declared change says what a release did, never which artifacts it did it to

Adopting `release_records` in `just-dna-registry` 0.24 (the registry that publishes and re-publishes
compiled modules). `needs_recompile` is exactly the derivation we had been reconstructing from version
comparisons, and the `correction` / `addition` split is the part we could not have computed ourselves —
we route on it: a correction means a value we published is wrong and is worth an immutable PATCH per
affected module, an addition means a field was absent and is not.

**What we ran.** For every published version, `needs_recompile(stamped_compiler, installed)` and then
act on `answer.declared` filtered to `RECOMPILE_DRIVING_AXES` and `kind == "correction"`.

**What we expected.** To re-publish the modules a correction actually reaches.

**What happens.** We re-publish all of them. Over `0.6.6 → 0.7.0` the corrections are
`gene_validity.classifications` (RM108), `gene_metrics.parquet` and `gene_metrics.signature` (RM110).
All three are real and all three are narrow: RM110's own detail says it moves the signature "on any
module compiled from the gnomAD v4.1 constraint snapshot", and RM108's applies to a module carrying a
re-curated ClinGen claim. A module with no `gene_metrics` block and no `gene_validity` block is
untouched by both — and nothing in `DeclaredChange` lets a consumer say so, so the sweep mints a fresh
PATCH for every module in the catalog to repair a value most of them never carried. Published versions
are immutable here, so each of those is permanent, and each one spends a version number.

We are shipping it that way, deliberately, because the alternative is worse: the false positives are
bounded at one wasted PATCH per module ever (the successor's interval is the self-interval, which
declares nothing and converges), while guessing at applicability and guessing wrong leaves a module
serving a value you have told us is wrong. So this is not blocking us.

**What we did about it meanwhile.** Nothing, and we want to say why rather than leave it as an
omission. `target` is documented as "a dotted manifest path, a parquet file or `file:column`", so we
could read its first segment and check whether the manifest carries that block. We are not doing it:
that is a consumer re-deriving the applicability rule from a field's spelling, it would break the day a
target is spelled some third way, and our own rulebook forbids discriminating on a string where a
structured member could exist. It is your grammar, so the predicate should be yours.

**A candidate, and it is one you have already built one struct over.** `RosterEntry` carries
`condition` — free prose naming when its recompute recipe holds. A `DeclaredChange.applies_when`, even
as prose, would be readable by a human operator deciding whether to run a sweep. What would let a
consumer *filter* is narrower and probably cheap, since the information is in the change already:

```
DeclaredChange(
    axis="parquet_bytes",
    target="gene_metrics.parquet",
    kind="correction",
    requires_block="gene_metrics",     # the manifest block a module must carry to be affected
    detail="RM110: ...",
)
```

`requires_block=None` would mean *every module* and would be the right default, so nothing already
written changes meaning and no record has to be revised. A consumer that ignores the field keeps
today's behaviour exactly.

**One thing we checked before filing, in case it saves you the same look.** This is not
`unmeasured` doing its job: `cyp2c9_warfarin_grch37` is genuinely unmeasured for `0.7.0` and we treat
it as unknown, which is a different axis from a change that *was* measured and applies to a subset.
Nor is it answerable from `AUTHORED_ROW_DERIVED_FIELDS` — that roster says which fields a consumer can
recompute from stored inputs, and `gene_metrics.parquet` is a compiled parquet nothing local can
recompute, which is the whole reason we are leaning on the record for it.

— just-dna-registry, 2026-09-11
