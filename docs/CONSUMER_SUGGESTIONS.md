# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S63

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

---

---

---

# RebuildHints(
#     parquet_schema=False,          # columns added/removed/retyped
#     parquet_bytes=False,           # a recompile writes different bytes
#     content_signature=False,       # the identity moved  ← the one that must never surprise us
#     manifest_fields={"stats.genes", "stats.gene_count", "compilation.warnings"},
#     unknown_interval=False,
# )
```

Three properties we would need, in descending order of how much they matter to us:

1. **`unknown_interval` must exist and must not be spelled as an empty result.** Asked about an interval
   the installed package has no record of — an artifact compiled under something newer than what is
   installed, or older than the table reaches — the answer has to be *I cannot say*, never *nothing
   changed*. This is your own rule about a value two opposite histories can produce, applied to a version
   table, and without it the hint is strictly worse than no hint: a consumer would stop recompiling on the
   strength of a silence.
2. **`content_signature` needs its own axis, separate from bytes.** For this service a signature is a
   permanent global `409 duplicate_content` claim that only a purge frees, so "the identity moved in a
   patch" is the one answer we would want to fail loudly on rather than merely act on.
3. **The declaration needs a guard, or it becomes the thing it is fixing.** A hand-kept per-release map
   is precisely the shape of five of the six RM104–RM111 fixes, and closing this with one would be the
   defect wearing a public name. We think you already have the enforcement: compile the reference
   examples under the previous release and diff, and fail when the declared hints disagree with what
   actually moved. That also makes the map a *measurement* rather than an author's recollection of what
   they touched, which is the half we would trust.

**What we are deliberately not asking for: a `should_rebuild` verdict.** The same fact carries different
costs per consumer — for `just-dna-lite` a stale cache is a free rebuild, while for us a rebuild mints an
immutable PATCH, spends a version number, and moves what a client tracking `latest` receives. So the
decision is ours and should stay ours; what we cannot get anywhere is the fact.

**One thing that is a different question, filed here only so it is not conflated.** RM107 (a duplicate
`(source, layer)` row is now an error) does not make a stored artifact stale — it makes some *specs*
newly invalid, which is "will my next publish still work?" rather than "is what I stored out of date".
Our `revalidate` already answers that axis by re-running `validate_spec`, and it answers it correctly,
so we are not asking for anything there. If a hints surface ever grows a `newly_refused` field we would
read it, but the existing route works and this item does not depend on it.

**Reproduced against** `just-dna-compiler` 0.6.6 installed, on a catalog of versions stamped
`compiler_version` 0.6.1. Our side of it is in `services/upgrade.py::ContractGap.acts_by_default`, which
now carries this analysis as a comment, and in the 0.20.0 release notes.
