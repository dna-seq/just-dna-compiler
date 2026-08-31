# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S84

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

## S82 — a source read by hand that yields no row leaves no trace anywhere, and that is real authoring work with nowhere to go

**Status — your reading (2), and the home is already built: an uncited `literature.csv` row. Shipped as [RM147](ROADMAP_HISTORY.md#rm147--a-source-read-by-hand-that-yields-no-row-had-nowhere-to-go-and-the-home-already-existed) — documentation and a test, no behaviour changed.**
You asked for a view rather than a shape, and the view is that the record belongs in the module, on the
**paper** rather than on the service.

**A `literature.csv` row that nothing cites is kept and reported.** It stays in the CSV; the compiler
drops it from the artifact with `literature_row_uncited`, which reads *describes N citation(s) no
study, bin or pharm row in this module cites — left out of the artifact, and left in the CSV*. That
shipped in RM79 for a citation an author had deleted, and it is the same shape for your case arriving
from the other side: a paper that was read and did not become a row.

You were close on (2) — the transport exists and nothing writes it — and the file is `literature.csv`
rather than `logs/`. That matters for three reasons a log line would not give you. The row is
**structured** (`pmid`, `doi`, `exists`) and checked by the same pass that checks a cited one. It
**cannot make a licence claim**, which is exactly what made your original five rows wrong. And it is
about the **paper**, which is the thing that was consulted — the service is how you reached it, and it
is the paper that carries terms.

So we did not take (2) literally and build a `logs/` writer, and you should not either: we would have
had to specify a line format that publishes, for something unstructured and unqueryable, when a typed
row already exists.

**(1) is the near miss, and worth saying why.** S77 is about **obligations** — a source that
contributed nothing creates none, which is why your removal was right and why we agreed the general
principle two days ago. It is not a rule that the *looking* is uninteresting. Answering (1) would have
made human search effort invisible by a rule that was never about visibility, and the looking is a fact
about a paper, which this format already has a table for.

**(3) we refuse, on your own argument and one more.** You said a row meaning *no obligation* sitting in
the obligations table is the wrong place for a true statement, and that it re-opens the
check-that-cannot-fail shape S77 closed. Both correct. The extra reason: `VALID_SOURCE_LAYERS` is a
wire vocabulary, so the member would be permanent under P3 — a one-way door for a fact with a home
already.

**Your rejected candidate is rejected here too, and your reasoning is the one we kept**: a
`pubmed,literature` row with blank permission booleans sits one column away from a false all-clear for
text quoted out of a `cc by-nc-nd` paper. Losing the record was the right call over putting it there.

**And your gaps-list line is half wrong in the direction you suspected.** For a hand-read *data*
source, writing the row yourself is still right — it has a layer that fits. For a literature service it
collides with RM46, and the resolution is that there is no row to write: the consultation is recorded
on the article, not on the service.

Verified end to end: two articles, one cited and one not, a green `compile --strict`,
`literature_row_uncited` naming the unused one, and **no `licensing.csv` at all** — because nothing is
owed for reading an abstract. Written up in [SCHEMAS](SCHEMAS.md) and in `LiteratureRow`'s own
docstring, which is where the next author to ask this will be standing.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record.
<!-- triaged: 0.7.0 · sha 5be7bed5c007 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.
**We are asking for your view rather than proposing a shape** — this is the one where we think our
instinct is likely to be wrong, and where a guideline from you would be worth more than a column.

### What we ran

An agent authoring a single-variant module read five literature services by hand while working —
Crossref, Europe PMC, OpenAlex, PubMed, Unpaywall — to find and confirm the papers behind two rows. It
recorded that work the only way it could see: five `licensing.csv` rows at `layer=literature`, each
with a `notice` reading *"Bibliographic metadata read by hand through this service while authoring; no
article text was taken from it."*

### Why we removed them, and what removing them cost

They are the wrong home, and your rules say so from two directions. `TERMS_BY_SOURCE` has no `pubmed`
entry and will not (`RM46`); a literature source's terms are per **article** and live on
`LiteratureRow`. And `S77`/`RM142` settled the general principle two days ago in exactly these words —
**a pass that put no row in a table records no source**. Consultation is not consumption. We measured
it too, before deciding: with and without those five rows, `validate --strict` and `compile --strict`
return identical verdicts and identical warnings, because literature-layer rows are exempt from the
orphan check outright. The rows bought no enforcement.

So we removed them and corrected our own skills, which had been contradicting each other about it.

**And that is where the item is.** What was removed was not a licence claim. It was a record that a
human went and looked — at five services, deliberately, and found the second paper that this module's
whole longevity claim rests on. **After removal there is no trace of it anywhere**: not in
`licensing.csv`, not in the manifest, not in `literature.csv` (which has rows only for articles that
became rows), not in `logs/`. The module now says less about how it was made than it did.

### The specific shape of the gap

Our own gaps list has carried this line for a while, and we now think it is half wrong:

> *No column recording why a source was consulted, and none recording that a source was read by a
> human rather than fetched. `source` is free text, so the honest way to record a hand-read source is
> to write the row yourself.*

For a hand-read **data** source that is fine — it has a layer that fits. For a literature service it
collides with `RM46`: write the row yourself, at the one layer that is forbidden. We have scoped our
own text to say so. What we cannot resolve is the underlying question.

### What we are asking

**How do you see a consultation being recorded, if at all?** Genuinely open, and "it should not be" is
a complete answer we will write down. Three readings we can see, none of which we are attached to:

1. **It should not be recorded, and the module is right to be silent.** `S77`'s principle applied
   straight through: a source that contributed nothing creates no obligation and no fact. The
   consequence is that human search effort is invisible by design, which may be correct — provenance
   is about what is *in* the module, not about how long somebody looked.
2. **It belongs in `logs/`, and nothing writes it.** The compile already sweeps `logs/**.log` into the
   published artifact with no opt-out, so the transport exists and costs nothing. What is missing is
   any writer for "consulted X, took nothing" — ours only logs cell-level authoring moves. If this is
   your reading, we would build the writer on our side and would want to know the line format you
   would accept, since it publishes.
3. **The vocabulary is what is short.** You asked us once whether an extension would help elsewhere,
   so we will say where we think one might here: a `layer` member, or a boolean, that means *consulted
   and contributed nothing* would let the row exist without asserting a licence obligation — which is
   the thing that made these rows wrong. We are **least** confident in this one: it re-opens the
   check-that-cannot-fail shape `S77` just closed, and a row that means "no obligation" sitting in the
   obligations table seems like the wrong place to put a true statement.

**A candidate we argue against outright:** keeping the rows as they were. A `pubmed,literature` row
with blank permission booleans is a true statement in a file that a downstream consumer reads to
decide redistributability, sitting one column away from source-level booleans that would be a false
all-clear for the article text quoted from a `cc by-nc-nd` paper. We would rather lose the record than
put it there.

## S83 — `direction` has no member for a concordant trend whose sign is not established, and two runs of one prompt split on it

**Status — your reading (1): not a vocabulary gap, and the description now says so. Shipped as [RM148](ROADMAP_HISTORY.md#rm148--direction-and-stat_significance-are-one-pair-and-the-description-did-not-say-so).**
You named the cheap answer and it is also the right one, for a reason worth stating rather than
asserting: **the orthogonality is itself the answer to your question.** `direction` records the sign of
the reported estimate; `stat_significance` records how far to lean on it. So *is a sign you cannot lean
on still a sign* resolves to yes — because the other column is the one that says you cannot lean on it.

**The state you wanted a member for already exists, as the pair.** `direction=risk` +
`stat_significance=not_significant` is exactly *a real trend the evidence does not establish*, and it
authors and validates today. There is a test that constructs your row — `rs117385980`, `risk`,
`not_significant`, OR 3.58 — rather than arguing about it.

**Run A was right and run B lost information.** Writing `unknown` for a concordant non-significant
trend discards the sign the paper actually reports, and leaves `stat_significance` making a statement
about nothing. That is the half your old description left an author to work out, and both your runs
were defensible against it, which is the definition of a description that does not settle the question
being asked. It now reads:

> Effect direction: one of protective|risk|neutral|unknown. The sign of the reported estimate, whether
> or not it is established — a non-significant or borderline trend still has a direction, and
> `stat_significance` is what says how far to lean on it. `unknown` means no sign to record (not
> assessed, or the sources conflict), never a sign you may not act on. Orthogonal to `state`, which
> predates both.

**Bounding `unknown` is the load-bearing clause.** You identified the overload precisely — it was
covering *no evidence*, *conflicting evidence* and *evidence that does not exclude either direction*.
The first two are one thing (nothing to record); the third is the pair's job. Saying so is what stops
the two readings being equally available.

**(2), a new member, we refuse — and you were right not to push it.** *Looked, and no sign
established* would be a **second spelling of the pair**: two ways to write one state, with consumers
splitting on which they read. That is Principle 5's overloading arriving as a synonym rather than as a
conflation, and it is a wire vocabulary change, permanent under P3, for something already expressible.
A test now asserts the two vocabularies stay disjoint but for `unknown`, over the walked sets rather
than by naming members, so a future addition has to face this deliberately.

**(3) partly stands and is not a substitute.** Your rule — where the interval contains the null or the
row carries a counter-direction, say which value you chose and why in `conclusion` — is good practice
for a genuinely contested row, and your instinct that "prose covering a gap is usually the sign the gap
is real" is a good one. It was right here: the gap was in *our* prose, not in the vocabulary.

**Your module is not self-contradictory**, for what it is worth: `direction: risk` recording the point
estimate, `negatives` carrying the counter-direction, and `flags: pleiotropic` beside it is three cells
each doing its own job, which is what the orthogonal axes are for.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Also in [SCHEMAS](SCHEMAS.md), beside the
`state` note S80 prompted an hour earlier.
<!-- triaged: 0.7.0 · sha ef8be021b4dd -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.
Filed in the same spirit as `S80`, which you accepted an hour ago as `RM145`: the question is whether
the published vocabulary carries what an author needs to choose.

### What we ran

Two runs of a byte-identical prompt over the same paper, by the same model, authoring `rs117385980`
(SIRT6) for a longevity module. Both green through every gate. They wrote **different values in
`direction`** for the same variant on the same evidence:

| | run A | run B (rerun) |
|---|---|---|
| `direction` | `risk` | `unknown` |
| `stat_significance` | `suggestive` | `not_significant` |

### The evidence both were reading

- Two cohorts, Finnish and Iranian, and **both trends run the same way**: the T allele is depleted
  among the longest-lived.
- Neither is significant: **p ≈ 0.074 and 0.073**.
- Combined **OR 3.58, 95% CI 0.96–13.4** — the interval contains 1 — at **28.4% power** by the
  authors' own analysis.
- And the row that says `direction: risk` carries, in its own `negatives`, that the same allele is
  *more* frequent among robust participants than frail ones — the opposite direction — with
  `flags: pleiotropic` set beside it because the source paper raises antagonistic pleiotropy.

So one module simultaneously asserts a direction, records the counter-direction, and flags itself
pleiotropic. Every one of those cells is individually correct.

### What the vocabulary offers, and what it does not

`direction` is `protective | risk | neutral | unknown`, documented as orthogonal to `state`. That
orthogonality is right and is the reason `risk` is defensible here: `stat_significance: suggestive`
already carries "not established", so `direction` is free to record the sign of the point estimate.

But `unknown` is equally defensible, and for a reason the vocabulary cannot express: **an interval
containing the null is a sign that has not been established**, which is a different claim from "nobody
looked" — and `unknown` is the only member available for it. So the same word covers *no evidence*,
*conflicting evidence* and *evidence that does not exclude either direction*, and a consumer cannot
tell them apart. Meanwhile `risk` covers both *established* and *point estimate only*.

### What we are asking, and we are not asking for four new members

**Your view on whether this is a vocabulary gap at all.** We can see three answers and would take any:

1. **It is not.** `direction` records the sign of the estimate, `stat_significance` records whether
   you may lean on it, and reading them together is the consumer's job. If so, **say it in the field
   description** — that is exactly what `RM145` just did for `state`, it costs one string, and it
   would have settled our two runs. Our current text is *"Effect direction: one of
   protective|risk|neutral|unknown. Orthogonal to `state`."*, which does not say whether a
   non-significant trend has a direction.
2. **`unknown` is overloaded and one member would fix it** — something meaning *looked at, and the
   evidence does not establish a sign*, distinct from *not assessed*. This is the extension we can
   most easily imagine, and we note it costs a wire vocabulary change and touches every consumer, so
   we would not push for it on one variant.
3. **It is a `weighting:`-shaped question rather than a column one** and belongs in prose, in which
   case we will keep it in our skills and stop looking for a cell.

**What we did meanwhile.** Kept `risk` in the reference module and added the disagreement to its
decision list, so a reviewer sees the judgement rather than a value. And added a rule to our own
authoring skill: where the interval contains the null or the row carries a counter-direction, say
which value you chose and why in the row's `conclusion`. That is prose covering a gap, which is
usually the sign the gap is real.
