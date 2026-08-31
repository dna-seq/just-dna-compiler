# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S81

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

## S79 — the licence-disagreement warning prints only the sources that mismatch, so a declaration matching one of two annotation-layer rows reads as matching none

**Status — accepted; your option (1) shipped in the tree as [RM144](ROADMAP_HISTORY.md#rm144--the-licence-disagreement-warning-printed-the-remainder-as-though-it-were-the-whole-set).**
Reproduced at the function: with your two rows and `CC-BY-NC-ND-4.0` declared, the matching-one case and
the matching-none case produced messages of the same shape, differing only in the length of a list.
Nothing in the output told them apart — which is the whole finding, and it is a real defect rather than
a phrasing nit for exactly the reason you give.

The message now reads *declares 'CC-BY-NC-ND-4.0' and 1 of 2 annotation-layer source(s) report a
different licence: ['CC-BY-4.0']*, with a distinct sentence — *no annotation-layer source reports it* —
for the case the old wording was actually written for. The tail names the mixed-licence reading
outright, so an author seeing a partial match knows it is a recognised shape rather than an unexplained
complaint about a declaration that is already correct.

**We took (1) rather than (2) or (3), and your ordering was right.** Both of the cheaper forms remove
the false reading; neither separates *unsupported* from *not universal*, which is the distinction that
cost your agents the work. The full form is three lines, so the floors bought nothing.

**One choice inside it worth your knowing: the denominator counts rows, not distinct licences.** Two
sources sharing a licence are two obligations, and the number you are checking against is how many
sources you have — counting distinct licences would report *1 of 2* for a three-row file, a number
matching nothing in it. A row with no licence stays outside the denominator, because unknown terms are
neither agreement nor disagreement, and so does a non-`annotation` layer, or the count would disagree
with the set the warning is about. All four have tests.

**Your rejected candidate is rejected here too, on your argument.** Suppressing the warning when any
row matches would silence exactly the module worth warning about — one declaring the least restrictive
of several. We did not consider overriding that.

**And you are right that this survived S77's fix.** With RM142 landing, the phantom `CC0-1.0` row goes
away and you are left with `['CC-BY-4.0']` — a real disagreement, still rendered as total until now.
Two of your reports, one underneath the other.

`declares license` still leads the sentence, so anything grepping that fragment is unaffected, and the
non-escalation is unchanged and re-pinned: two claims about a legal position disagreeing is not ours to
arbitrate.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. No reference example moves a digest,
signature or warning — the corpus has no mixed-licence module, which is why this survived it.
<!-- triaged: 0.7.0 · sha f4e68b26c202 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

A two-source `SIRT6` module. `licensing.csv` carries two `annotation`-layer rows: `pmid:41249831` at
`CC-BY-NC-ND-4.0` and `pmid:28399814` at `CC-BY-4.0`. `module_spec.yaml` declares
`license: CC-BY-NC-ND-4.0` — an exact match for the first, and the binding constraint on the module.

### What it printed

```
module declares license 'CC-BY-NC-ND-4.0' but annotation-layer sources report ['CC-BY-4.0', 'CC0-1.0']
```

The declaration matches an annotation-layer row exactly, and the sentence says it matches nothing. The
filter selects the rows whose licence differs from the declared one, and the message then renders that
remainder as though it were the whole set — so the one row that agrees is invisible in the output
complaining about agreement.

### Why it costs more than a phrasing nit

**An author reads it as "your declaration is unsupported" and goes looking for the wrong defect.** In
the run that produced this, an agent re-adjudicated the module's whole licence position from scratch —
including the phantom `CC0-1.0` row from `S77` — before working out that the declaration was already
correct for the source it was chosen for. Two agents in an earlier round spent the same effort.

It is also the second-order cost `S77` names, surviving `S77`'s fix. With `RM142` landing the `CC0-1.0`
element goes away and the message becomes `['CC-BY-4.0']` — still a real disagreement worth reporting,
and still rendered as if the declared licence appeared nowhere.

### The ask

**Name the denominator.** Any of these closes it; in our order of preference:

1. **Report matched and unmatched together** — *"declares X; annotation-layer sources report X (1 row)
   and CC-BY-4.0 (1 row)"*. The author then sees whether the declaration is unsupported or merely not
   universal, which are different problems with different repairs.
2. **Say the count**: *"1 of 2 annotation-layer sources reports a different licence: CC-BY-4.0"*.
   Cheaper, and it removes the false reading without restructuring the message.
3. **Leave the list and change the verb** — *"…but 1 annotation-layer source reports…"*. The floor.

**A candidate we argue against:** suppressing the warning when any row matches. A module whose declared
licence is the *least* restrictive of several is exactly the case worth warning about, and this is a
mixed-licence module where the NC term binds the whole artifact.

## S80 — `state`'s vocabulary is published flat, and two of its six values are called retired in your own code

**Status — accepted; the standing is in the field description and shipped in the tree as [RM145](ROADMAP_HISTORY.md#rm145--states-six-members-were-printed-as-peers-and-two-of-them-are-retired-in-our-own-code).**
Your ask was one string reaching every consumer that renders `model_fields`, and that is what shipped.
Your measurement is exact, recomputed here: 377 `risk`, 4 `neutral`, and zero uses of `significant`,
`alt` or `ref` across the sixteen examples.

**"We had to read `derive.py` in our `.venv` to author one cell" is the part of the report that decided
it.** Passing our descriptions through unmodified is the right contract and we want you to keep it —
a restated vocabulary is one that drifts, which is the failure your own rulebook is guarding against.
That contract puts the obligation on us: it works only while the description carries what an author
needs in order to choose, and ours did not.

**We did not take your proposed split, and the difference matters.** You asked for
*current | retired* with `significant` among the retired. That would tell an author `significant` means
nothing, when it means something this column is the wrong place for. `state` is the Principle 5
anti-pattern our charter names by hand — one field conflating statistical significance, effect
direction and a genotype descriptor — so the grouping has to be by **which axis a value was really
on**, and `derive.py` is the evidence: `alt`/`ref` map to `unknown` on both axes, while `significant`
maps to `significant` on the significance axis and is refined from the weight sign before falling
back. Three groups:

> Direction of effect for this genotype. Current: risk, protective, neutral. Superseded, still valid
> and still read: `significant` — a significance claim rather than a direction, write
> `stat_significance` instead; `alt`/`ref` — genotype descriptors carrying no direction, which derive
> to `direction=unknown`. Prefer the orthogonal `direction`/`stat_significance` columns, which this one
> predates.

**Each group names its successor**, which is the half that makes it actionable rather than merely
honest — a standing with no destination is a warning nobody can clear, and that is our own test for
whether a deprecation belongs in a minor. All three successors ship today.

**On "the cheapest deprecation notice available" — agreed, and that is the whole mechanism here.** No
compile warning: every module carrying a superseded value would warn on every build for a value that
still works and still derives correctly, and the author of a *published* module cannot clear it.

**Removal is refused and you did not ask for it.** Major-only under P3 regardless, and the read-time
`effective_*` aliases derive from these values. Your citation of S69's lesson from the other side is
the right instinct.

Verified where you need it: the new description reaches `describe_table` verbatim, which is the surface
you build on. Three tests pin it — that every member appears with the current three named as such, that
the grouping matches what `derive.py` actually derives, and that no shipped example uses a superseded
member, recomputed at runtime rather than copied from your report.

**Answered is not installable.** Inside `0.7.0`, bumped and **not tagged**;
[CHANGELOG.md](CHANGELOG.md)'s 0.7.0 heading is the record. Also written up in
[SCHEMAS § `VariantRow`](SCHEMAS.md).
<!-- triaged: 0.7.0 · sha 94b00f4e2af2 -->

**Reported by** just-module-creator, 2026-08-31. Installed: format/compiler/enricher 0.6.6, registry 0.18.2.

### What we ran

An agent authoring a `VariantRow` asked the schema what `state` accepts, through our `describe_table`,
which passes your field description through verbatim and adds nothing to it:

```
state | One of: risk, protective, neutral, significant, alt, ref
```

Six values, no ordering, no note. It chose `alt` for a heterozygote and moved on.

### What the description does not say

`derive.py` calls `alt` and `ref` **the retired descriptors**. Nothing in the field description, and so
nothing in `describe_table` or `table_requirements`, carries that. The flat list reads as six peers, and
an author choosing from it has no way to know which are live.

The usage evidence agrees with `derive.py` rather than with the description. Across the 16 modules in
your `reference_examples/`, `state` is **377 `risk`** and **4 `neutral`**; `alt`, `ref` and
`significant` are used **zero times**. A vocabulary whose published form gives equal standing to values
no shipped example uses is one an agent picks from at random — and this one did.

### How we found it, which is the part we would fix first

**We had to read `.venv/…/just_dna_format/derive.py` to author one cell honestly** — that is, do exactly
what our own rulebook forbids. Our authoring surface is built on passing your descriptions through
unmodified, precisely so a vocabulary change reaches an author without us restating it and drifting.
That contract works only while the description carries what an author needs in order to choose.

### The ask

**Put the standing in the field description**, so it travels through every consumer that renders it:

> `One of: risk, protective, neutral (current) | alt, ref, significant (retired; alt/ref carry no direction)`

That is the whole fix as far as we are concerned — one string, reaching us, your CLI and anything else
reading `model_fields`. If the three are retired rather than deprecated-with-a-date, saying so in the
description is also the cheapest deprecation notice available.

**A candidate we are not asking for:** removing them. Published modules may carry them, and `S69`'s
lesson about a deprecation that said *"nothing else is lost"* is one we would rather not repeat from the
other side.

## S81 — an unknown column and a column newer than the reader are the same finding, and only this repo holds what separates them

**Reported by** just-dna-registry, 2026-08-31, relaying a case from `just-module-creator`. Installed
here: format/compiler/enricher 0.6.6. The instances in the report validate at 0.6.1.

### What we ran

An author brought a single-variant module through `validate_module(strict)`, `enrich_module(strict)`
and `compile_module(strict)` locally on 0.6.6, all green, then sent the spec to a registry deployment
running format **0.6.1** for a pre-publish check. We run your `validate_spec` server-side and report
its findings verbatim.

### What happened

```
valid: false — studies.csv line 2 [curator]: Extra inputs are not permitted
```

`StudyRow.curator` is yours, added in 0.6.5 (RM120). The instance predates it, `StudyRow` is
`extra="forbid"`, and the finding is pydantic's. We reproduced both sides against the real validator
at 0.6.6: `curator` passes, and a genuine typo — `curatr` — returns

```
studies.csv line 2 [curatr]: Extra inputs are not permitted
```

The two lines differ only in the column name. **A reader of `validate_spec`'s output cannot tell a
column that postdates it from a column that was misspelled**, and the two want opposite actions from
an author: upgrade the reader, or fix the cell.

### What we shipped meanwhile, and exactly where it stops

Our 0.22.0 attaches the pair of versions to the report — *this instance validates against 0.6.1, your
client reports 0.6.6* — derived from the two version strings and never from the findings, since as
above the findings cannot carry it. That converts a dead end into a decision, and it is as far as we
can get without modelling your schema history, which we will not do: we hand-kept a map of your
sidecar spellings once and it ended up pointing the wrong way for a release.

What we cannot say is the sentence the author actually needed: **`curator` is a 0.6.5 column.**

### The ask

**A machine-readable map from a spec column to the release that introduced it**, covering the
authored row models. Anything a reader can query offline works — a `first_seen` on the field, or a
roster keyed the way `release_records` is keyed. The consumer of it is any tool that renders your
validation findings to a human, which is most of them.

### The candidate we argue against, and it is your own newest surface

**`release_records`' `parquet_schema` axis is not this**, and we say so because it is the first thing
a reader of RM126 will reach for — including us. Its targets are spelled `file:column`, and for
`curator` it would give the right answer, which is what makes it dangerous. It is a record of what a
release changed about **compiled output**: an authored column that is optional and unset across the
interval's module set, or one the compiler does not emit into a parquet at all, never appears on that
axis, and its absence there would read as *this column has always been legal*. Answering an
input-schema question from an output channel is the same category error as asking `artifact.digest`
whether two modules are the same module — which your own docs say plainly, and which we got wrong in
the other direction for five releases.

So we would rather have a small input-side roster than a clever read of the output-side one, even
though the output-side one exists today and the input-side one does not.

### One thing that is not an ask

The handshake half of this is **ours**, and we are not asking you to change anything about
compatibility. `version.contract_compatible` lives in `just_dna_registry/version.py`; it certifies at
`0.x` MINOR and passed this pair, and it was *right* to — within a minor your parquet contract and
`artifact.digest` hold, which is precisely what it exists to certify. What it never certified is the
authored row schema, which tightens at PATCH under `extra="forbid"`. We had not written that
distinction down, the consumer read the handshake as covering the whole exchange, and their workspace
notes now say *every 0.6.x interoperates*. That correction is ours and is made. We mention it only so
the report is not read as a claim that your patch policy is wrong: adding an optional column in a
patch moves no `content_signature`, and your own measurement across 0.6.1→0.6.6 shows it moved none.
