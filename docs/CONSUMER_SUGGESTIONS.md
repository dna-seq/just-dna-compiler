# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S36

**Claim ids from here, never from what this file shows.** S1–S29 are all answered and live in the
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
been cut. S25 and S26 were the first replies to carry that state; **everything labelled 0.6.0 is in it
today**, because all three packages read `0.6.0` while the newest tag is `v0.5.4` — cutting a release
is the maintainer's call. S34 is here because a document of ours presented a table of 0.6 fields as
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

## S36 — `weight` declares no scale and no methodology, so every module means something different by it

Reported 2026-08-17 by Anton Kulaga, over chat, in Russian, from the consumer side (the app that reads
`weights.parquet` and combines the column). Not a bug report — field feedback after living with the
column across a corpus of modules. Quoted verbatim, then translated:

> сейчас уже недома. Но основая идея, что weights какую-то фигню городят
> на по каждому модулю нужно расписыавть методологию и давать по каким шкалам
> часто есть gwas эффект по множеству снипов
> они часто идут лучше чем отфанаревые куратор бейзд весы
> у нас де факто по каждому модулю разные методология если говорить о весах

"Not at my desk right now. But the main idea is that the weights construct some nonsense. For each
module you need to spell out the methodology and say on which scales. There is often a GWAS effect
across many SNPs. Those often work better than eyeballed curator-based weights. De facto we have a
different methodology per module when it comes to weights."

Four claims, and they are not the same claim:

1. **The scale is undeclared.** `VariantRow.weight` is `float | None` described only as "Score
   (positive=protective)". Nothing anywhere — not the row, not `module_spec.yaml`, not the manifest —
   says what range it runs over, whether it is additive, or whether two modules' weights are on one
   scale. `effect_size` has `effect_measure` beside it; `weight` has no unit column at all.
2. **The methodology is undeclared.** `defaults.method` exists and defaults to `literature-review`, a
   free-text string that is about the *annotation* method rather than the *weighting* method.
3. **A different methodology per module, in practice.** So the column is module-local — which the 1.0
   tracker already says ("module-local score vs published magnitude") — but nothing in the artifact
   marks it as module-local, and the consumer combines across modules anyway.
4. **GWAS effect sizes often beat hand-set curator weights,** and are available for many SNPs.

**Candidate the maintainer raised, with the argument against it in the same breath:** have the
enricher procure GWAS effect sizes into a derived table and fill `weight` where the authored cell is
null. The argument against is already written down twice —
[MODULE_LIFECYCLE § Stage 3](MODULE_LIFECYCLE.md) names `weight`/`direction`/`effect_size` verbatim in
the cells no tool fills, and Stage 5 says every check reports and never repairs. A null `weight` is
"the author has not modelled this", which is the tri-state house algebra, and filling it from a source
destroys the redundancy a Class-2 check needs. There is also a sign trap sitting in the middle of it:
`weight` is documented positive=protective while a GWAS beta is positive on the effect allele, so a
silent fill inverts the claim on exactly the rows nobody re-reads.

Claim 4 also overlaps a settled thread: combining a GWAS effect across many SNPs is a polygenic score,
which the format delegates to `pgs.csv` + `just-prs` rather than scoring itself
([RM16](ROADMAP_0_7.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest)).
