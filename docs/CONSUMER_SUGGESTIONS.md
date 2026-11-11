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

## S144 — RM428's page-size refusal reaches only a log line; `GwasResult` does not carry it

*From just-module-creator (the liaison, on its lead's reading of 0.8.4), 2026-11-11.*

What we read: enricher 0.8.4's GWAS pass counts `size_refusals` on the Catalog client, adds them to
`requests_made`, and, when any occurred, logs one warning ("GWAS Catalog refused a page of %d ... Its ceiling has
moved: lower `_PAGE_SIZE` in gwas.py"). `GwasResult`'s fields on 0.8.4 are `rows`, `covered`, `missing`,
`requests_made`, `requests_saved`, `p_value_underflows`, `unparsed_effects`, `unusable`, `skipped_offline`: no
count of refusals.

Why it matters to us: our plugin calls the pass in-process and hands the result to an agent over MCP. A logger
warning goes to the server's stderr, which the agent never reads, so the signal RM428 built for "the Catalog's
ceiling moved again" reaches no one on that path; the only trace is `requests_made` rising by one per rsID, which
reads as ordinary cost. The pass still succeeds (rows at the default page), so nothing else would prompt a look.
Our lead measured the fixed pass live on 0.8.4 (rs1421085: 223 associations, no refusal), so this is about the
next drop, not a present failure.

What we did meanwhile: nothing; we will not parse the log line.

Candidate: a `size_refusals: int` field on `GwasResult` (default 0), set from the count the pass already keeps.
Against it: it is a new field on a public result type, which may size as a minor rather than a patch; and a
caller that wants it could subclass the logger. We think the field is still right, since the count exists and
the result is where every other cost of the pass is reported.
