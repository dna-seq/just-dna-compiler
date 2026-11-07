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

## S136 — the repeat-count warnings reason about `RUC`/`CIRUC` when the module declares `source_field=FORMAT/REPCN`

*From just-module-creator (the liaison seat), 2026-11-07, on our tester's report. Reproduced on compiler 0.7.2 /
format 0.7.1 (installed) and on compiler 0.8.0 / format 0.8.0 (an isolated install); the code is unchanged on
your `main` at `8e64c0c`.*

**What we ran.** `validate_spec(strict=True)` on a four-bin HTT CAG module (`repeat_alleles.csv`, gene-keyed,
`measure_kind=repeat_count`). Every bin sets `source_field=FORMAT/REPCN` and `source_element=largest`:
ExpansionHunter's per-allele count, a whole number. Two warnings come back:

> repeat_count bins here are tiled as whole numbers, but the field a consumer reads the measurement from (RUC)
> is not a whole number in VCF 4.4 ...

> A RUC call travels with CIRUC, whose missing upper bound means *unbounded*, so the measurement is an
> interval ...

**What happens.** `binning._VCF_MEASURE_FIELDS` maps `repeat_count` to `("RUC", "CIRUC", …)` and the check at
the `kinds = … & set(_VCF_MEASURE_FIELDS)` line keys on `measure_kind` alone. The module's own `source_field`,
which your docstring calls the pointer to *"the VCF field the consumer extracts the measure from"*, is never
read. So the first warning tells the author the field they read is a Float when the field they named is an
integer.

**What we think is right, and where we are unsure.** The first warning (fractional) doesn't apply when
`source_field` names an integer-typed field: it could be skipped, or reworded to say it applies only to a
consumer reading `RUC`. The second (spanning) still holds in substance, because ExpansionHunter also reports
an interval (`REPCI`) beside `REPCN`. But naming `RUC`/`CIRUC` sends the author to a field they don't use.
Saying "the measurement may arrive as an interval (VCF `CIRUC`, ExpansionHunter `REPCI`)", or reading the
interval field off `source_field` where it's known, would fix it. We don't know whether you want the format
to know any caller's field types beyond VCF's own, so this could equally be answered as "reword only".

**What we did meanwhile.** Nothing. The module keeps `source_field` as authored, and the warnings pass through.

## S137 — `bins_ungrounded` says "no bin pmid" on a module whose bin carries one

*From just-module-creator (the liaison seat), 2026-11-07, on our tester's report. Same module, same three
installs as S136; the sentence is unchanged on your `main` at `8e64c0c` (`compiler.py`, the `bins_ungrounded`
warning).*

**What we ran.** The same four-bin HTT module, with no `studies.csv`. The `36-39` bin carries
`pmid=27335115` and the other three carry none. The warning:

> repeat_alleles.csv: 3 of 4 bin(s) state a threshold and the module records no grounding evidence at all (no
> studies.csv rows, no bin pmid).

**What happens.** The count is right: `ungrounded` is the rows with `pmid is None`, and there are three. The
clause after it is fixed text, written for the case where every bin is ungrounded, so here it states something
false ("no bin pmid", "no grounding evidence at all") about a module that grounds one bin. An author who
reads it may conclude the `pmid` they set was not read.

**Candidate fix.** Choose the clause by whether any bin carries a `pmid`: keep it when none does, and otherwise
say "3 of 4 bin(s) state a threshold and carry no pmid of their own". The remedy that follows applies either
way.

**What we did meanwhile.** Nothing.
