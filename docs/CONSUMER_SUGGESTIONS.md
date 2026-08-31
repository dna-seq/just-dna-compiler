# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S87

**Claim ids from here, never from what this file shows.** S1–S86 are all answered and live in the
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
