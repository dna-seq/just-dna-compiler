# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S57

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


# Field notes from just-module-creator — RM10/RM11 session

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed, and
`just-dna-registry` 0.18.2. All three came out of one work item: our MCP surface had three answers
that **restated** a schema fact instead of generating it, and we went looking for the public symbol
to generate each from. Two of the three had none. That is the report.*

## S50 — `--no-study-facts` is a permanent choice, and nothing says so

**Status — accepted as a documentation defect; both sites fixed in the tree (not yet cut). No `RMn`:
the behaviour is correct and only the prose was wrong, which is your own reading of it.**
Your three-step sequence reproduced here exactly, with an injected client on the real pass:

```
enrich_gwas(spec, study_facts=False)  ->  pmid ''
enrich_gwas(spec, study_facts=True)   ->  pmid ''          (row skipped, as you measured)
rm gwas_effects.csv
enrich_gwas(spec, study_facts=True)   ->  pmid '16199547'
```

Structurally it is what you said: `_merge_key` is the association id alone and `if key in seen:
continue` fires **before** `_build_row`, so the row is skipped whole rather than rebuilt thinly.

**Your candidate fix is what shipped, close to your wording**, in both places you named.
[ENRICHER.md](ENRICHER.md)'s GWAS section now says the loss is permanent for the rows that run writes,
that the merge is keyed on `association_id` so a later run skips rather than back-fills, and that
deleting the file is the recovery. Your sharpest point is in there too, because it is the part that
makes this worth more than a clause: every other delete-to-regenerate case in the tier is about a
*stale* value, and this one is about a value that was never fetched — so the file looks complete and
cannot be repaired incrementally. The `--no-study-facts` help carries the same, verified against
`--help` rather than assumed.

**Your rejected repair is rejected here for your reason, and it is the stronger of the two you gave.**
A null `pmid` is not distinguishable from a study record that genuinely has none — the case `follow`'s
404 arm deliberately produces — so a back-fill keyed on "the linked columns are null" would rewrite
rows on a guess. That is the house rule about `None` never meaning `False`, and it is why the answer
here is a sentence rather than a mechanism.

Pinned by `test_a_no_study_facts_row_is_never_back_filled_by_a_later_run`, run as your three-step
sequence rather than asserted off the code — the point being that step 2 looks like it should work.
Not installable yet — check [CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha 376e501239e4 -->

*Filed 2026-08-20 by just-module-creator, against enricher 0.6.4 as installed. Doc gap, not a code
defect — the behaviour is the merge rule working correctly.*

**What we were doing.** Wrapping `enrich_gwas` as an MCP tool, so we had to document `study_facts`
for an author who cannot see the source.

**What we expected from the docs.** `ENRICHER.md:2797` and the `--no-study-facts` help both say the
flag "drops the cost to one request per variant, keeping the effects and losing the linked metadata".
Read straight, that is a per-run trade: this run is cheap and thin, a later run fills the rest in.

**What actually happens.** It does not. `_merge_key` is `("id", row.association_id)` alone, and
`enrich_gwas` skips any association whose key is already in the file (`if key in seen: continue`)
before `_build_row` is reached. So a row written with `study_facts=False` keeps `pmid`,
`study_accession`, `ancestry`, `trait` and `trait_efo_id` **null forever**, and a later run with
study facts on is a no-op for exactly those rows. Only deleting `gwas_effects.csv` recovers them.

Measured against the real pass with an injected client, one association, on our side:

```
enrich_gwas(spec, study_facts=False, client=fake)  ->  pmid ''      1 request
enrich_gwas(spec, study_facts=True,  client=fake)  ->  pmid ''      (row skipped)
rm gwas_effects.csv
enrich_gwas(spec, study_facts=True,  client=fake)  ->  pmid '11788828'
```

**Why this is worth a sentence rather than nothing.** Every other "delete to regenerate" case in the
tier is about a *stale* value — the source moved and the file did not. This one is about a value that
was never fetched, so an author who took the cheap run once has a file that looks complete (every
column present, most cells populated) and cannot be repaired incrementally. The cost asymmetry makes
it likely: `--no-study-facts` is the flag a first-timer reaches for precisely because the budget
warning is loud, and the 382-request measurement is what points them at it.

**What we did meanwhile.** Our wrapper emits a warning whenever `study_facts` is off — naming the
five columns and saying a later run will skip rather than backfill — and asserts the three-step
sequence above in a test.

**Candidate fix, and the one we think is wrong.** The right one looks like one clause in
`ENRICHER.md`'s GWAS section and in the CLI help: *"the linked metadata is lost permanently for those
associations; the merge is keyed on `association_id`, so re-running with study facts on skips them —
delete the file to re-derive"*. The wrong one is making the merge backfill a row whose linked columns
are null: it would make the pass rewrite existing rows, which is the one thing merge-not-clobber
exists to prevent, and "null" is not distinguishable from "the study record has no pmid" — a real
case `follow`'s 404 arm deliberately produces.
## S51 — a derived sidecar's *merge key* lives inside its pass, so no consumer can reproduce it

**Status — accepted, shipped as [RM115](ROADMAP_HISTORY.md#rm115--a-derived-sidecars-merge-key-lived-inside-the-pass-that-writes-it) in the tree (not yet cut).**
`hints.key_fields(csv_name)` now answers for `resolution.csv` and all seven fact CSVs — it already
routed derived names through `derived_model_for` after RM113, so the gap was that the seven models
declared no key and it correctly withheld. Your candidate fix is what shipped, in the tier you named:
each model declares `_KEY_FIELDS`, `just_dna_format.base.merge_key(row)` is the row-level answer, and
**every pass keys its `existing` map off it** rather than restating the tuple — which is the half you
identified as the one that makes the two unable to disagree.

Both of your COARSE rows reproduced before the fix, against the published `*_FACT_FIELDS`:
`gene_validity.csv` derived as `('gene', 'dataset')` and `clinical_assertions.csv` as
`('variant_key', 'dataset')`. What they publish now:

```
gene_validity.csv        columns=('assertion_id',)
                         fallback=('gene','disease_id','moi','submitter','dataset')
clinical_assertions.csv  columns=('variant_key','variation_id')
resolution.csv           columns=('variant_key',)   rule='subject'
```

**Two shapes your derivation could not have reached, and each is a wrong answer rather than a coarse
one, so read `rule` and `fallback` as well as `columns`.** `resolution.csv`'s key is a **subject**, not
a uniqueness constraint — `KEY_RULES` has a third member for it — so a tool asserting uniqueness there
would report a legal one-to-many file as a duplicate; your own note already knew this ("a subject holds
several rows"), and it is now machine-readable. And `gene_validity.csv`'s key has **two levels**:
`assertion_id` where the source published one, the gene's grain where it did not. `TableKey.fallback`
carries the second, tagged `"id"`/`"grain"` so a grain tuple cannot collide with an id equal to it.
`gene_validity.csv` is the only table with a fallback today, which is exactly why it is a field and not
a footnote — a consumer ignoring it is right about seven tables and wrong about the one where a gene
carries several assertions.

**Your `source="manual"` case should improve directly**, which is the consequence you put on the record.
With `resolution.csv` published as `rule="subject"`, a hand-resolved row and a fresh `status="not_found"`
row for the same `variant_key` are the same *subject* by construction rather than a collision — the
group is what the pass replaces. The classification of which row within the group is the author's is
still yours; what changed is that the ambiguity is no longer an artefact of an approximate key.

**Your rewire found a defect of ours we would not otherwise have looked for.** Keying the maps off the
declared tuples immediately mismatched three *lookup* sites that rebuilt the key positionally, and one
was a latent break: `pmid not in existing` in the literature pass would have refetched every cited
article on every run. All three now read the attribute off the row instead of unpacking a key.

Documented in [ENRICHER.md § What makes two rows of a sidecar the same row](ENRICHER.md), with the whole
table and the two shapes called out. Guards in `enricher/tests/test_merge_keys.py`; suite 2799 → 2813.
Not installable yet — per the standing rule at the top of this file, check
[CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha 3e1fdfb4f967 -->

> **Triage note added 2026-08-20, after seeing how much you already have in flight.** If you are
> ranking our open notes against each other: **this one first, `S52` second, and both behind anything of
> your own.** The distinction is that `S51` degrades a tool we have **already shipped** — we had to
> approximate the merge key from required fact fields, and the approximation is measurably coarse on two
> of seven tables (`gene_validity.csv` drops `disease_id`, `clinical_assertions.csv` drops
> `variation_id`), so rows that could be safely repaired are being reported as unresolvable conflicts
> today. `S52` is design-shaping rather than blocking. Our other open notes, `S49` and `S50`, are lower
> than both and neither blocks anything.

*Filed 2026-08-20 from just-module-creator, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as
installed. This is **S48's question asked of the machine-written tables**, where the answer is one step
further away: for an authored kind the key at least exists as a lambda in
`compiler._TABLE_DUPE_KEYS`; for a fact sidecar it exists only as a dict-key expression in the body of
the pass that writes it.*

**What we were building.** A `refresh_sidecar` tool. Every derived sidecar is merge-not-clobber, so
re-deriving one means deleting it first, and deleting it discards the author's hand-added rows along
with the stale ones — `resolution.csv`'s `source="manual"` rows most of all, since those are the rows
no re-run can reproduce. So the tool captures the file to a durable location, deletes it, re-runs the
pass, classifies every row, puts back what is provably the author's, and reports the rest. The whole
design turns on one question: **which columns decide that two rows of a sidecar are the same row?**

**What we needed, and what exists.** The *fact* half is excellent and we use it as-is:
`integrity.fact_signature(rows, fields)` plus the eight public `<table>_signature` functions and the
eight public `*_FACT_FIELDS` tuples. Fact equality is therefore exact and derived. What has no public
route is the **subject** — the narrower key a pass merges on:

* `frequencies.csv` — `enrich_frequencies` builds `existing: dict[tuple[str, str], FrequencyRow]` keyed
  `(row.variant_key, row.population)`. A local variable.
* `resolution.csv` — `enrich` builds `existing[variant_key] -> list[ResolutionRow]`, so the subject is
  `variant_key` and a subject holds several rows (one per locus of a one-to-many rsID).
* `gwas_effects.csv` — `association_id`, which we only know because **S50** happens to state it in prose
  while explaining a different problem.
* `gene_metrics.csv`, `gene_validity.csv`, `clinical_assertions.csv`, `sources.csv` — same shape, each
  key readable only by reading the pass.

`draft.natural_key` returns `None` for all of these (they are not authored kinds), and
`compiler._resolution_key` is about `reverse_module`'s re-keying rather than the merge.

**What we did meanwhile, and we would rather not have.** We derive the subject as
`[f for f in FACT_FIELDS if model.model_fields[f].is_required()]` — public pydantic over a public
tuple, so it cannot silently drift with a schema change, and we report the tuple it produced on every
call so the caller can see what "same subject" meant. Measured against the four keys above:

```
resolution.csv          -> ('variant_key',)                              exact
frequencies.csv         -> ('variant_key', 'population', 'dataset')      exact + dataset (constant)
gene_metrics.csv        -> ('gene', 'dataset')                           exact + dataset
literature.csv          -> ('pmid',)                                     exact
gwas_effects.csv        -> ('association_id', 'variant_key', 'dataset')  exact + two constants
gene_validity.csv       -> ('gene', 'dataset')                           COARSE (drops disease_id)
clinical_assertions.csv -> ('variant_key', 'dataset')                    COARSE (drops variation_id)
sources.csv             -> ('source', 'layer')                           exact
```

Five of eight are exact-or-harmlessly-wide. Two are coarse, and the coarse direction is the safe one
for us — a coarse subject reports *more* rows as ambiguous and therefore auto-repairs fewer, which is
the failure we want. But "safe" is not "right": a coarse key demotes a gene's second real disease
assertion into an ambiguity the author has to adjudicate by hand, on exactly the table where a gene
legitimately carries several rows. And the whole derivation is a guess that happens to agree; nothing
tells us when it stops agreeing.

**Candidate fix.** Whatever shape **S48** settles on, extend it to the machine-written names — a public
`key_fields(csv_name) -> tuple[str, ...]` that answers for `resolution.csv` and the seven fact CSVs as
well as for the authored kinds. The tier that ought to own it is the format, beside the
`*_FACT_FIELDS` tuple each table already exports: `RESOLUTION_FACT_FIELDS` and a
`RESOLUTION_KEY_FIELDS` next to it reads as one fact about one table, and each pass would then key its
`existing` dict off the published tuple instead of restating it — which is the half that makes the two
unable to disagree.

**Why not just publish the passes' dicts.** Because the key is a property of the *table*, not of the
pass: the compiler cross-checks these tables, `reverse_module` re-emits them, a registry re-splits
them, and we classify them. Four parties, one key — the same argument `layout.py`'s own docstring makes
about four parties and one layout.

**The consequence we shipped, so it is on the record.** Because the subject key is approximate and
because bucket-3 rows are never auto-resolved, our tool reports a hand-resolved `source="manual"`
resolution row as an *unresolvable collision* whenever the fresh online run wrote a
`status="not_found"` row for the same `variant_key` — the branch at `enrich`'s
`elif genome_build == "GRCh38":`. That is the honest answer with the information available, and it is
also the headline case the tool exists for, so a published key would directly improve what an author
sees.

## S52 — `ProvenanceItem.rationale` is the outrank marker a cross-check needs, and no check reads it

**Status — accepted, split as you proposed: the capture half shipped in the tree (not yet cut), the
check half is filed as [RM117](ROADMAP.md#rm117--an-outrank-record-exists-and-no-check-reads-it-and-what-a-check-should-do-is-undecided) with the reasons it is not obviously right.**

**Taking your explicit ask first, since you said it unblocks you more than the check behaviour does:
it is shape 1.** `ProvenanceItem.outranks: dict[str, str]` — `{column: why}` — is in the tree. Build
against that.

**And a reason from outside your list, which is why it was not close.** Shape 2 is not merely "changes
what an item is": `Provenance.item_count` is a **published manifest number** whose meaning is *variants
carrying a record*, and making items per-(variant, field) silently changes what it counts for every
consumer already reading it. The addition would be legal and the redefinition is not — the same shape
as S14's rename and S18's `Finding.row`, where the break is silent because a compensating consumer
keeps working and keeps being wrong. Shape 3 is refused on your own argument.

Confirmed the rest of your reading of the code before answering: `_collect_provenance` really does read
`len(doc.items)` and nothing else, and `rationale`/`reviewer_verdict`/`confidence`/`human_reviewed`
reach no check and no manifest field. One thing worth knowing that you could not see — `ProvenanceItem`
did not `forbid` extras, so an `outranks` key written before this shipped was **silently dropped** rather
than rejected. It is a real field now.

Three properties pinned by tests: the record survives the compile byte-for-byte (the file is copied and
hashed, not re-serialized, so your prose reaches a reader unchanged), one item justifying two columns
stays one item, and **neither `content_signature` nor `artifact.digest` moves** across a pair differing
only by an outrank record — recording the disagreement costs nothing.

**On the check half, where we are not taking your proposal as-is.** Your three properties are right and
the two-pathway argument is the strongest thing in the note — the WARNING must not be pre-emptible, and
INFO-not-silence follows from it. What stops us wiring it now is that **the guard is a convention the
code cannot see**: nothing distinguishes a record written in response to a warning from one filed ahead
of it, so pathway 1 is protected by an author's good faith rather than by a mechanism. And your own
addendum names what would fix that — a record hash-bound to the value it justifies, as
`verification.json` binds to the authored bytes. Without it an author edits the value and the downgrade
silently persists. We think the binding comes first and the severity ladder after, which is a larger
design than one severity change; RM117 carries all of it, including that the ClinVar cross-check's
deliberate warn-only-in-both-modes design is an argument that cuts both ways here.

**Your terminal-state observation is the part we found most useful and it is recorded as free.** A
mismatch that has since resolved means the archive caught up to the outrank; a record whose row's value
has changed again is stale by construction. The check runs every compile, so both are observable without
asking anyone anything, and they do not depend on the severity question being settled first.

Documented in [SCHEMAS.md § `provenance.json` and the outrank record](SCHEMAS.md), including that
nothing reads it today — stated rather than left for the next person to grep for, since that is how you
found it. Not installable yet — check [CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha b67b4f769fd2 -->

*Filed 2026-08-20 from `just-module-creator`, against format/compiler 0.6.1 and enricher 0.6.4 as
installed. **This is a proposal, and the substrate is already yours** — we are asking for the consuming
half, not for a new field.*

> **Triage note, added the same day.** We called this priority when we filed it and are **lowering that
> relative to `S51`** now that we can see your queue. Rank it **second of ours**, behind anything of your
> own. What changed our read is that we can build the capture half without your answer and are already
> doing so — this shapes our design rather than blocking it, whereas `S51` degrades something shipped.
> **The cheapest thing that would help most is not the severity change**: it is the granularity answer
> in *"The granularity problem"* below. Three shapes are on the table, it is your document, and we are
> deliberately not designing around a guess — so a one-line *"it will be shape 2"* unblocks us further
> than the check behaviour does.


### Where this came from

We are the authoring layer, and we had adopted your `report, never repair` as our own non-negotiable.
Our owner corrected that this week: it is the right stance for your layer, and business decisions are
delegated downstream, so we hold a counterstance — our tools may write and may revise. Fine on its own.
What it exposed is a hazard we had not been reasoning about, and we think it is yours as well as ours.

**The vacuity argument turns out to be the shallow one.** We had justified never touching a checked cell
by "a check that compares your value against the source it came from agrees with itself". True, but the
sharper problem is that **the source lags the edge**:

> *"ClinVar lags behind edge, say the article is retracted, metaresearch refutes conclusion etc —
> validation against ClinVar this way makes the correction done mindlessly, wrong."*

So *"your `clin_sig` disagrees with ClinVar"* is **not a defect report.** It may be the module being
right and current while the archive is stale — a retraction, a refuting meta-analysis, a reclassification
ClinVar has not absorbed. An agent that silently conforms the row to the source **degrades the module**,
and the cross-check then agrees with itself and reports green. That is a worse outcome than the mismatch
it "fixed", and nothing in the current contract distinguishes the two cases.

### What you already have, and it is most of it

We went looking for an existing marker before proposing one, and found `provenance.json`:

```python
class ProvenanceItem(BaseModel):
    variant_key: str
    rationale: str | None        # "Why this annotation was made"
    reviewer_verdict: str | None
    confidence: float | None
    human_reviewed: bool
```

with a header carrying `generator`, `model` (*"Model id, if AI-authored"*) and `agent_version`. This is
already the right shape — freeform, per-variant, and explicitly AI-aware. **Nobody needs to invent a
field.** Our owner's framing of why freeform is correct, and we agree:

> *"Outranking… can't be 100% formalized, there's sci knowledge grading pyramid yet only a natlang agent
> can really judge here (human or ai or a tandem) — so a set of recommendations + freeform record."*

An evidence-grading pyramid exists, but which of a retraction, a meta-analysis and a single larger cohort
outranks an archive call is a natural-language judgement. A vocabulary would either be wrong or
unusably large. Freeform prose plus recommendations is the honest instrument.

### What is missing: nothing reads it

`_collect_provenance` (`compiler.py:604-619`) validates the document, copies it, hashes it, and returns
a lean `Provenance` summary. From the items it reads **`len(doc.items)` and nothing else** — `rationale`,
`reviewer_verdict`, `confidence` and `human_reviewed` reach no manifest field and no check. Grep for
`rationale` across `compiler/src` and `enricher/src`: two hits, both the import and that one
`model_validate_json`. So the file is carried, hashed and never consulted.

### The proposal

Let a filled outrank record change the **severity** of the mismatch, not its existence:

| the module has | today | proposed |
|---|---|---|
| authored value, matches the source | pass | pass |
| authored value, mismatches the source | **WARNING** | WARNING (unchanged) |
| authored value, mismatches, **and an outrank record naming why** | **WARNING** — identical | **INFO**, highlighting the field |

The check still **runs** and the mismatch is still **reported**. What changes is that a mismatch somebody
took responsibility for stops reading as a defect. Three properties we would argue for:

- **Never suppression.** INFO, not silence. A reader must still be able to see that the module and the
  archive disagree — that is the interesting fact about the row, and it is exactly what a reviewer wants
  to land on.
- **Never a pass.** The record is an author's assertion, not evidence. It must not become a green check,
  or you have re-created the vacuity problem through the back door.
- **Presence, not content, is machine-readable.** Do not parse the prose. *A record exists* is the bit a
  check can act on; the prose is for the human or agent reading the INFO.

### The granularity problem, which is the one part we cannot see a clean answer to

`rationale` is **one string per `variant_key`**, and an outrank is naturally **per field**. A row may
outrank ClinVar on `clin_sig` while its `direction` is ordinary and unjustified — one string cannot say
which, so a check keyed on "an item exists for this variant" would downgrade every field's mismatch on
that row at once. That is too blunt, and it is the failure mode we would expect to be reported back to
you within a release.

We can see three shapes and do not have a preference strong enough to argue:

1. a per-field map inside the item (`outranks: {clin_sig: "…"}`), which is precise and changes the schema
2. a `field` on `ProvenanceItem`, making items per-(variant, field) rather than per-variant — cheaper,
   but changes what an item *is*
3. keep it per-variant and accept the bluntness, documenting that it downgrades the whole row

We would rather you pick, since it is your document. **What we would ask against** is inferring the field
from the prose — that puts a parser on freeform text whose whole justification is that it is not
formalizable.

### What we are doing meanwhile, so this is not just a request

Nothing on our side writes `provenance.json` today — we found that gap the same day and have it open as
our own item. We are building the authoring half regardless of this note: capture the outrank reason at
the moment an agent or author overrides a checked value, and write it into `provenance.json` in your
existing shape. That is authoring workflow and ours to own. We will also log every such move into the
`logs/` subtree, which your own docs call the provenance subtree nobody fills.

**So the split we are proposing is:** we capture and record it; you decide whether a check reads it. If
you would rather not wire a severity change at all, that is a legitimate answer and worth saying plainly
— we would then tell authors that an outrank record travels with the module and is read by humans only,
which is still better than the value being changed with no record anywhere.

### Addendum, same day — the two pathways, and why the WARNING must stay in both

Our owner drew the lifecycle after we filed the above, and it sharpens the proposal enough to be worth
appending rather than leaving in our tree. **Two pathways start identically and diverge only afterwards:**

```
1  hallucination, or an author's stale knowledge
     -> erroneously authored item -> check -> MISMATCH -> WARN
     -> the agent sees the flag and corrects the item          <- the warning did its job

2  the module is right and the archive is stale
     -> item corrected -> check -> MISMATCH -> WARN
     -> reasoning provided -> no longer warns on this row
     -> the edit is preserved as a mask across re-revisions
     -> eventually the source catches up and the mismatch disappears
```

**The consequence for your side: the WARNING is correct in both, and must not be pre-emptible.** An
author cannot mark a row as outranked *before* the mismatch is reported, or pathway 1 loses the only
signal that catches it. The record is a **response** to a warning, never a suppression filed ahead of
one. That is a stronger argument for INFO-not-silence than the one we gave above — silence would make
the two pathways indistinguishable at exactly the moment they need distinguishing.

**And it gives the mechanism a terminal state we had not seen, which we think is the most useful part.**
Pathway 2 ends with *"eventually matches updated ClinVar (hopefully)"*. So an outrank record whose
mismatch has since **resolved** is an outrank that turned out to be **right** — the archive caught up to
it. That is a trust signal available nowhere else in the format, and it is free: the check already runs
every compile, so the transition is observable without asking anyone anything.

Three things follow, and they are yours rather than ours because they are all about what a check
reports:

- **A resolved outrank is retirable, and saying so out loud matters** — otherwise records accumulate
  forever and the file becomes noise nobody reads. *"This row no longer disagrees; the record can go"*
  is an INFO worth emitting.
- **An outrank that never resolves is not wrong, but it is worth aging.** A record standing against
  several source releases is either a genuine standing disagreement — a retraction the archive will
  never absorb — or a stale correction nobody revisited. Distinguishing those needs a human; *knowing
  which rows to look at* does not.
- **A record whose row's authored value has since changed again is stale by construction.** This is the
  same shape as your attestation binding: a justification written about one value does not carry to a
  different one. Whatever granularity you pick, it probably wants to be hash-bound to the value it
  justifies, exactly as `verification.json` is bound to the authored bytes.

**What this does not change:** the record must still never produce a pass. Pathway 2's *"no longer
warns"* means downgraded and still visible, not green. A row where the module and the archive disagree
is interesting forever, and the whole point of the record is to say *who decided that, and why* — not
to make the disagreement go away.

**One more reason to resist letting it go quiet, in case ageing-out looks attractive.** The argument for
eventually suppressing a long-standing record is that it is settled and adds noise. We would push back,
and the reason is time rather than policy: *"easy to forget as time passes."* Whoever wrote the
justification understood it; two source releases later nobody remembers whether the retraction that
motivated it was itself superseded, and a row that stopped reporting is a row nobody will revisit while
the module keeps asserting a judgement no living person is standing behind.

We are building the consumer of that visibility on our side, which is why we care: **the outranked rows
are the first candidates for a re-review.** A review pass has no priority list today — a reviewer opens
a module and picks somewhere to start — and these records are that list, ranked by construction, with the
ones standing across the most releases at the top and the resolved ones retirable on sight. That only
works if the check keeps reporting them.

---

# Field notes from just-module-creator — specifying a version comparator, 2026-08-20

## S53 — `content_signature` is whole-module-only, so anything finer has to restate `_resolve_spec_defaults` and re-derive the table roster

**Status — accepted; your candidate fix shipped as [RM116](ROADMAP_HISTORY.md#rm116--content_signature-returned-only-its-hash-so-anything-finer-restated-the-fold) in the tree (not yet cut), and the docs half with it.**
`compiler.spec_tables(spec_dir) -> tuple[dict[str, list[BaseModel]], str]` is public, with the
signature and docstring you proposed; `content_signature` is now `_content_signature(*spec_tables(...))`
and no logic moved. The `ValueError`-on-invalid-CSV contract carries over unchanged, and a test pins it
over both functions rather than assuming it.

**Both of your measurements reproduced before the fix, on the same reference example, to the
character.** Renaming `sources.csv` → `licensing.csv` left `content_signature` at
`sha256:44ad4449…`, and editing a `notice` cell in it left it there too. The fold pair reproduced as
well: `compiler.content_signature` agreed across the two copies while `integrity.content_signature`
over raw `load_csv_rows` output gave your `sha256:0b8dd27c…` for the yaml copy and a different value
for the cells copy.

**Your rejected alternative is rejected here for your reason.** Exporting `_TABLE_KINDS` and
`_resolve_spec_defaults` separately hands out three pieces that must be assembled in one order — load
with the declared build injected, fold, then hash — and the order is the half that is easy to get wrong.
One function that returns the finished mapping cannot be assembled wrongly, which is your argument and
it is the right one.

**You can delete the restatement and the drift alarm with it.** `spec_tables` returns the folded rows,
so a per-table comparison hashes exactly what the whole-module digest hashes:

```python
tables, build = spec_tables(spec_dir)
assert integrity.content_signature(tables, build) == compiler.content_signature(spec_dir)
```

**The documentation half shipped too, since you said it was worth having either way.** COMPILER.md's
public-surface entry now names which CSVs feed the hash, says the licensing table is outside it and
that `integrity.source_signature` is what covers it, and states the fold with the consequence of
omitting it. On your roster note — you are right that `DRAFTABLE` minus `SIDECAR_SPELLINGS` is a
coincidence two files maintain rather than a contract, which is why the answer is the function and not
a documented equality.

Guards in `compiler/tests/test_content_signature.py`, on the RM37 fixtures that already model your
measured pair; the fold test **demonstrates** the raw build disagreeing in the same test that shows the
folded one does not, rather than asserting it. Suite 2813 → 2817. Not installable yet — check
[CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha 655c0d535ca5 -->

We are specifying the tool `MODULE_LIFECYCLE.md` §7 says nothing owns: *"what moved between two
versions of this module"*. The design is a three-level ladder — one signature for whether the content
moved, per-table for where, per-row for what — and levels two and three need the same rows
`integrity.content_signature` hashes. `compiler.content_signature(spec_dir)` returns only the hash, so
the mapping it built has to be rebuilt outside, and rebuilding it means restating two private things.

**1. The table roster.** `_TABLE_KINDS` is private, and `COMPILER.md` describes `content_signature` as
being over *"the raw authored data CSVs"* without saying which those are. The set is derivable in
public — `draft.DRAFTABLE` minus every spelling in `layout.SIDECAR_SPELLINGS` gives exactly
`variants.csv`, `studies.csv` and the nine table kinds — but that equality is a coincidence maintained
by two files rather than a contract, and it breaks silently in the direction that hashes an extra
table.

**We had to probe to learn that the licensing table is outside it**, which we think is a documentation
finding in its own right. On a copy of `reference_examples/hfe_hemochromatosis`:

```
rename sources.csv -> licensing.csv        content_signature sha256:44ad4449…  UNCHANGED
edit a `notice` cell in it                 content_signature sha256:44ad4449…  UNCHANGED
                                           integrity.source_signature sha256:0afb6361… -> sha256:f63f2881…
```

Both are correct and neither is stated anywhere we could find. `SCHEMAS.md:698` says the two resolution
columns are "outside `content_signature`" in exactly the words that would have answered this, so the
convention for saying it already exists — it just is not said for the one authored, hand-editable table
that a licence audit will send an author looking for.

**2. The `defaults:` fold, and this one is a correctness trap rather than a documentation one.**
`_resolve_spec_defaults` and `_DEFAULTED_VARIANT_FIELDS` are private, so a caller hashing
`compiler.load_csv_rows` output directly gets a different answer from `content_signature` for the same
module. Measured on the same reference example, writing one `curator` value on every variant row in one
copy and the identical value under `defaults:` in another with the cells blanked:

| | signature |
|---|---|
| `compiler.content_signature`, both copies | `sha256:921790f3…` (equal, correct — RM37) |
| `integrity.content_signature` over `load_csv_rows` rows, cells copy | `sha256:33b961b4…` |
| `integrity.content_signature` over `load_csv_rows` rows, yaml copy | `sha256:0b8dd27c…` |

So a per-table comparison built the obvious way reports **12 changed rows where there are none**, and
disagrees with the identity the registry deduplicates on. The fold rule is three lines and every one of
them matters: the field set, `authored if authored is not None else getattr(defaults, name)`, and
`None if effective == model_default else effective`. We can derive the field set publicly —
`set(Defaults.model_fields) & set(VariantRow.model_fields)` equals `_DEFAULTED_VARIANT_FIELDS` exactly
on 0.6.1, verified — but the third line is a restatement with no guard, and it is the one whose
omission produces a signature that *looks* fine.

**What we will do meanwhile.** Restate it, with a regression test asserting that our folded per-table
rows reproduce `compiler.content_signature` on a defaults-bearing pair. That test is the drift alarm,
and it is the same trade you have twice named as the defect rather than the fix: a rule restated beside
its authority, reading as current while it drifts.

**Candidate fix — give the first half of `content_signature` a name.**

```python
def spec_tables(spec_dir: Path) -> tuple[dict[str, list[BaseModel]], str]:
    """The parsed, defaults-folded authored rows `content_signature` hashes, and the declared build."""
```

`content_signature` then becomes `integrity.content_signature(*spec_tables(spec_dir))` and no logic
moves. Everything a consumer needs for per-table or per-row work — the roster, the build injection, the
fold, the validation error behaviour — comes from the one function that already does it right, and the
`ValueError`-on-invalid-CSV contract carries over unchanged.

**A candidate we think is wrong: exporting `_TABLE_KINDS` and `_resolve_spec_defaults` separately.** It
hands out three pieces that must be assembled in one order — load with the declared build injected,
fold, then hash — and the order is the part that is easy to get wrong. One function that returns the
finished mapping cannot be assembled wrongly.

**A smaller alternative, if `spec_tables` is more surface than you want:** say in `COMPILER.md` which
CSVs feed the hash and that the licensing table does not, and note that `defaults:` is folded first with
a pointer to `_resolve_spec_defaults`' docstring. That closes the documentation half and leaves the
restatement, so we would rather have the function; but the docs half is worth having either way, since
the next consumer's first question is "which files does this cover".

# Field notes from just-module-creator — the RM15 philosophy audit

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed. Both items
come out of one audit: we were re-reading every rule this repo adopted from yours to find the ones
we took on authority rather than on reasons. `S11` is ours, and it did not survive the re-reading.
`S54` is what we measured while checking it; `S55` is the withdrawal and what we would like instead.*

## S54 — `quotes_found` is satisfied by the article's own title, and four published modules do exactly that

**Status — accepted, shipped as [RM118](ROADMAP_HISTORY.md#rm118--quotes_found-could-not-fail-on-a-title-and-four-published-modules-are-titles) in the tree (not yet cut). Your candidate fix, both halves of it.**
Reproduced against our own tree before writing anything, and your numbers hold: 2045/33/33,
695/19/19, 859/26/26, 69/3/3 — row count, distinct PMIDs and distinct quotes, one quote per PMID on
all four. The quotes are titles.

`LiteratureResult.titles_as_quotes` lists the PMIDs whose every `provenance_quote` is the article's
title, and the CLI prints it in yellow. Warning, never an exit code: whether a title is an acceptable
locator for a claim is the author's decision, and what the tool can honestly say is that
`quotes_found` is not evidence there.

**Your reasoning about the discriminator is what shipped, including the part that rejects the
alternatives.** The comparison is against `bibliographic()`'s title, which arrives in the same
`esummary` response that answers existence, so it costs no request — and it therefore answers for a
**paywalled** article too, which we think is the better half of the deal: that is exactly where
`quotes_found` stays null and a reader has nothing else to go on. Your rejected candidates are
rejected for your reasons; length cannot separate a seventeen-word title from a seventeen-word
sentence, and a regex is as copyable as a quote.

Two narrownesses we added on top, both because an over-eager version of this would be worse than
none. Normalisation is case, whitespace and a trailing period and **nothing more** — a quote that
*contains* the title is a real quote of a paper that names itself. And it fires only when **every**
quote for a citation is the title: a module quoting the title on one row and a passage on another has
an author doing the work, and flagging it would be noise.

**One correction to your report, and it came from a test failing rather than from re-reading you.**
*"A title appears in its own fulltext, always"* is nearly true rather than true. Against the recorded
JATS for PMC5753237, esummary gives `ClinVar: improving access to variant interpretations and
supporting evidence.` **with** a trailing period, the article body carries it **without**, and
`quote_matches` does not strip one — so that exact pair misses and `quotes_found` reads 0. The
substance is untouched: the miss is punctuation and not evidence, the title *is* in the text, and a
module whose two spellings agree gets the green check you describe. Both states are pinned in the same
test, because the finding has to be independent of which way that falls.

Your S11 point is the part we will be carrying forward, and it is answered in [S55](#s55--we-withdraw-the-reasoning-behind-attestation_bearing-and-ask-for-the-attributor-it-was-missing)
rather than here. Documented in [ENRICHER.md § A quote that is the article's own title](ENRICHER.md).
Not installable yet — check [CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha 70e25439f0d5 -->

*Filed 2026-08-20 by just-module-creator, against enricher 0.6.4 as installed. Measured, not
theorised — the numbers below are from your own tree.*

**What we were doing.** Re-reading `S11`, our own note, the one that gave you the
`attestation_bearing` refusal reason. Before arguing about whether a machine may locate a quote, we
went to look at what the column actually holds in practice.

**What we expected.** `provenance_quote` is documented as the passage a curator located, and
`quotes_found` checks it against the Europe PMC fulltext. We expected the column to be mostly empty —
that being the cost of the refusal we ourselves argued for.

**What we found.** Across every `studies.csv` in your tree, 33 files and 44342 rows:

```
reference_examples/*/studies.csv        10 files, provenance_quote not even a column
data/output/corrected_modules/*         4 files, 3668 rows, provenance_quote filled on 3668 of 3668
```

Those four are `aggression_anger`, `risk_impulsivity`, `cognitive_intelligence` and
`big_five_personality` — the published `antonkulaga/*` modules. Every row carries a quote. But:

```
module                    rows   distinct pmids   distinct quotes   quotes per pmid   avg words
cognitive_intelligence    2045              33                33                  1        15.6
risk_impulsivity           695              19                19                  1        17.2
big_five_personality       859              26                26                  1         9.9
aggression_anger            69               3                 3                  1         7.0
```

**Exactly one distinct quote per PMID, on all four.** A passage located for a specific claim varies
row to row, because different rows cite the same paper for different findings. One string per paper,
repeated across every citing row, is structurally not a passage. It is a property of the *article*.

It is the title. Verbatim, trailing period included:

```
studies.csv  pmid 24489884  provenance_quote "Genome-wide association study of proneness to anger."
lookup_citation(24489884)   title            "Genome-wide association study of proneness to anger."
```

The same for the other two in that module, and the pattern holds across all 81 PMIDs.

**Why this is a check defect and not only an authoring one.** A title appears in its own fulltext,
always. So `_study_quote_found` matches, `quotes_found` equals `quotes_authored`, and the module
reports full quote coverage — 2045 of 2045 — while establishing nothing whatsoever about whether any
claim is in any paper. The check cannot fail on a title. It is satisfiable from `esummary` metadata
without retrieving a single word of the article, which is the one thing the column exists to witness.

This is worse than the failure `S11` was written to prevent. We asked you to refuse a machine-located
*passage* on the grounds that it asserts a reading that never happened. What the refusal produced
instead was a machine-copied *title* asserting the same thing, with the check agreeing.

**Candidate fix — make the check able to fail.** Reject, or flag, a `provenance_quote` that is not
distinguishable from article metadata you already hold:

- if the quote equals the `title` for that PMID (normalised: case, trailing period, whitespace), it
  is not a located passage — `quotes_found` should not count it, and `inspect_rows` should say so;
- more generally, one identical quote across every row citing a PMID is a signal worth reporting
  even when it is not the title, because a real passage varies with the claim.

You already have the title: `CitationHint.title` shipped for `S12`. The comparison costs no request.

**A candidate we think is wrong: a minimum length, or requiring `provenance_regex`.** Length does not
separate a title from a passage — 17 words is a perfectly ordinary title and a perfectly ordinary
sentence — and a regex is as copyable as a quote. The discriminator has to be *against the metadata
you already have for that article*, not against the shape of the string.

**What we did meanwhile.** Nothing in the data — these are not our modules and a quote is authored
content we will not rewrite. On our side the audit is changing what we tell an author, and `S55` is
the half that is yours.

### Correction, 2026-08-20, same reporter — the check did not run on any of these four

Filed hours after the above, while remediating `aggression_anger` row by row. **The paragraph titled
*Why this is a check defect and not only an authoring one* overstates one step, and the truth is
worse rather than better.** We wrote that `quotes_found` equals `quotes_authored` and the module
reports full coverage. Measured against the `literature.csv` those four modules actually ship:

```
module                    studies rows   rows with a quote   literature rows   quotes_authored   quotes_found   quote_source
aggression_anger                    69                  69                 3               0             ""             ""
big_five_personality               859                 859                26               0             ""             ""
cognitive_intelligence            2045                2045                33               0             ""             ""
risk_impulsivity                   695                 695                19               0             ""             ""
muscle_lean_mass                    11                   0                 0               —              —              —
```

`quotes_authored` is **0 on every literature row of all four**, and `quotes_found` and `quote_source`
are empty. So `quotes_found` never equalled `quotes_authored`; the quote check **never ran on a
single one of these 3668 rows**. The sidecar was written by a literature pass that ran *before* the
quotes were authored, and because the sidecar is merge-not-clobber nothing revisited it.

Three consequences, and the third is why we are correcting the record rather than leaving it:

1. **The candidate fix as written would not fire on the modules that motivated it.** Comparing a
   quote against `CitationHint.title` happens inside `_study_quote_found`, and on these four that
   code path is never reached. The title check is still right; it is not sufficient.
2. **`quotes_authored: 0` is a confident zero, not a null.** Beside 859 non-empty `provenance_quote`
   cells in the same module, it is the only number a reader has, and it is wrong in the direction
   that reads as "this author wrote no quotes" rather than as "this was never looked at".
3. **Nothing compares the two files.** That is separable from the title problem and from the
   attribution problem, so it is filed on its own as **S56** rather than folded in here.

Everything else in this entry stands, including the measurement it opens with: one distinct quote per
PMID, equal to the title, on all four.

## S55 — we withdraw the reasoning behind `attestation_bearing`, and ask for the attributor it was missing

**Status — accepted; `StudyRow.curator` shipped as [RM120](ROADMAP_HISTORY.md#rm120--the-table-where-the-attestation-lives-could-not-name-its-attributor) in the tree (not yet cut). Your whole ask, verbatim as you wrote it.**

**We think the retraction is right, and it is the most useful thing anyone has sent this inbox.** Our
own answer to S11 turned on *"nothing establishes a human ever looked"*, and you are correct that the
sentence names a **missing attributor** rather than an illegitimate reader. The reading is real; what
the rule protected was a fiction about *who* did it, and the column then stayed empty for the only
reader actually present. S54 is what makes that concrete rather than philosophical, and we would not
have connected the two.

Confirmed both places you say our model already disagrees, first-hand: `Defaults.curator` really does
default to the literal `ai-module-creator`, and `StudyRow` really did have no `curator` while
`VariantRow` has had one all along. The asymmetry is backwards for the reason you give — a variant row
could name who decided it, a quote could not name who located it, and of the two the quote is the
attestation.

```python
curator: str | None = Field(default=None, description="Who located this row's provenance quote/regex …")   # StudyRow, 0.6
```

Your rejected candidate is rejected for your reason: `machine_located: bool` collapses *an agent found
it and a human confirmed it* into one of two lies, and cannot name which agent or which human. And
your framing that this records labour rather than responsibility is carried into the field description
and the docs, because it is the sentence most likely to be misread by whoever reads the column next.

**`ATTESTATION_BEARING` itself is unchanged**, which is your own reading of it — a provider still must
not fill the quote. What changed is that an author who *does* locate a passage has somewhere to say so.

**Wiring your column found a defect in our own gotcha book, which seems worth telling you.** Our note
says adding an authored column is three touch points and names the reverse `fieldnames` list as the
one that gets missed. There is a fourth, and it is quieter: `_write_studies_csv` also fills a row
dict, and naming a column in the list but not the dict makes `csv.DictWriter` write the **header**
with an empty cell on every row. The reversed spec looked right, re-validated, and had lost every
`curator` value; only the digest fixed-point assertion caught it. Fixed, the note corrected, and the
guard is now behavioural — fill every authored `StudyRow` field, round-trip, assert nothing came back
empty — with both guards shown to fail on the buggy code before being kept.

**On your addendum, which arrived while this was being written: it narrows the ask onto exactly what
shipped, and every number in it reproduces here.** `big_five_personality/studies.csv` — 859 rows, 735
variants, 26 PMIDs; the pmids-per-variant distribution 640/75/14/3/3; **95 variants cited by more than
one paper**, **37 of them for different `trait_efo_id`s**; `rs11082011` cited by 29292387, 29500382,
29942085, 30643256 and 35898629. Confirmed, to the id.

You are right that `provenance.json` is close and that the gap is the **grain**, and that is the
argument that decides it rather than anything about AI authorship: a `studies.csv` row is
`(variant_key, pmid)` and `ProvenanceItem` is keyed on `variant_key` alone, so one variant cited by
two papers for two findings collapses to one item and cannot say which passage came from where. At
13% of a module of ordinary size that is not an edge case. `StudyRow.curator` is at the row's own
grain, which is the thing `provenance.json` structurally cannot offer — and note that
[S52](#s52--provenanceitemrationale-is-the-outrank-marker-a-cross-check-needs-and-no-check-reads-it)'s
`outranks` deliberately keeps `ProvenanceItem` per-variant for an unrelated reason, so the two
answers agree about what that file is.

**Your `upgrade` corner: the code you quote is not ours.** There is no `upgrade` path in
format/compiler/enricher — `carry = set(present) - {PROVENANCE_FILE}` lives downstream, so the rule
you are asking about is the registry's to state. What we can say is that the corner closes on our
side by construction: the attributor is a `studies.csv` column, so it travels with the row through
any mechanical re-publish that carries the table, and the reasoning you quote for dropping
`provenance.json` stays untouched and correct.

Documented in [SCHEMAS.md](SCHEMAS.md) beside the provenance columns. Not installable yet — check
[CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha 4f55d9fa3dff -->

*Filed 2026-08-20 by just-module-creator. This one is a retraction of our own argument, so the report
is about reasoning rather than behaviour. `ATTESTATION_BEARING` itself may well be right for your
layer; the case we handed you for it is not one we still hold.*

**What we filed.** `S11`, which you accepted and shipped in 0.5.4 as a fifth refusal reason. Our
argument, quoted from that note: *"a passage extracted from a fulltext a tool just fetched asserts a
curator reading that never occurred. That is a false claim of provenance, not merely a vacuous
check."* Your answer turned on the same hinge: *"no longer evidence that the claim is in the article,
because nothing establishes a human ever looked."*

**What we now think is wrong with it.** The sentence *nothing establishes a human ever looked* names
the actual defect, and it is not the one we asked you to fix. It is a **missing attributor**, not an
illegitimate reader. We treated "a machine read it" as the falsehood. But the machine does read it —
our own `fetch_fulltext` hands the agent the entire article, and has since before `S11` — so the
reading is real, and what the refusal protected was a fiction about *who* did it. The column stayed
empty for the only reader actually present.

**The evidence that this is not academic:** `S54`, above. The refusal did not produce human-located
passages. It produced 3668 rows of title-as-quote in four published modules, with the check green.
That is the outcome the rule bought.

**Your own model already disagrees with our argument, in two places.** `Defaults.curator` defaults to
the literal string `"ai-module-creator"` (`spec.py:296`) — an AI curator is not an edge case in this
format, it is the documented default for every row. And `Contribution` already carries the whole
vocabulary for saying who did what: `who` is *"a name, handle, **or model id**"*, `kind` ladders
`{human, human_expert, human_certified}` against `{ai}` plus a scale `{agent, team, swarm}`, and
`role` is `created|edited|audited|reviewed`. You have modelled mixed human/AI authorship carefully.
`attestation_bearing` is the one place that then refuses the AI contributor a cell, and it refuses on
our say-so.

**What we would like: a per-row attributor on `StudyRow`.** `VariantRow` has `curator: str | None`
("Curator override", `spec.py:513`). `StudyRow` has no such column — so a variant row can name who
decided it and a quote cannot name who located it, which is backwards given which of the two is an
attestation.

```python
# just_dna_format/spec.py, StudyRow
curator: str | None = Field(default=None, description="Curator override")
```

That is the whole ask: the same field, on the table where the attestation lives. Then
`provenance_quote` stops being a claim about an unnamed human and becomes a located passage with a
named locator, resolvable against `authorship` — and `quotes_found` can finally be read for what it
is, per locator, instead of as an undifferentiated coverage number.

**Why the module-level `authorship` block is not enough.** Real work is mixed at row granularity: a
scientist reads a review and an agent traverses its citations, in one module, in one pass. A
module-level contributor list cannot say which of the two located row 1400. `VariantRow.curator`
exists precisely because module-level defaults are not enough for a variant; the same is true here.

**One thing this is explicitly not.** It does not move responsibility. An AI is not a subject of
right, so the human author holds it entirely, whatever a `curator` cell says. The column records the
real distribution of labour so a reviewer can route scrutiny — which is what `Contribution.kind`'s
own docstring already says it is for ("route scrutiny by it") — and not so anyone can point at a
model when a quote turns out to be wrong.

**A candidate we think is wrong: a boolean `machine_located`.** Two-valued collapses the case that
actually occurs — a passage an agent found and a human then confirmed — into one of two lies, and it
cannot name *which* agent or *which* human. A free-text identifier resolvable against `authorship`
carries both, and matches what `VariantRow` already does.

**What we changed on our side, so you can weigh how much of this is ours to fix.** Our `CLAUDE.md`
forbade an agent to locate a passage at all, citing `S11`. That prohibition is reversed as of
2026-08-20: our agents may locate and write a `provenance_quote`, verbatim, and must record who
located it.

### Addendum, hours later: we were wrong that there is nowhere to put it, and the real ask is narrower

The paragraph above originally ended *"we can only write it to our own logs, where it does not travel
with the module"*. We then actually did the remediation and published it, and both halves of that
were wrong. Verified against a real publish and manifest read-back — three records survive:

| Where we put it | Grain | On the published manifest |
|---|---|---|
| `module_spec.yaml: authorship` (`Contribution`) | per version | `manifest.authorship`, verbatim |
| `provenance.json` — `ProvenanceItem.rationale`, keyed by `variant_key` | per **variant** | `manifest.provenance` `{generator, model, agent_version, item_count, sha256}` |
| `logs/*.log` | per run, free text | `manifest.logs` `{name, sha256, size}` |

`provenance.json` is close to what we are asking for and we should have said so: it is per-row-ish,
free text, it travels, and `ProvenanceDoc` already carries `model` and `agent_version` in its header.
So please read this report as narrower than it was written: **the gap is the `(row, quote)` grain, not
the concept.** A `studies.csv` row is `(variant_key, pmid)`; `ProvenanceItem` is keyed on
`variant_key` alone, so one variant cited by two papers for two different findings collapses into a
single item and cannot say which passage came from where. That is the case a `StudyRow` attributor
would fix and `provenance.json` cannot.

**And the collapse is not hypothetical — it is the common case on a real module.** Measured on
`data/output/corrected_modules/big_five_personality/studies.csv`, 859 rows over 735 distinct variants
and 26 PMIDs:

```
pmids citing one variant   1     2     3     4     5
variants                 640    75    14     3     3
```

**95 of 735 variants are cited by more than one paper**, up to five (`rs11082011` is cited by
29292387, 29500382, 29942085, 30643256 and 35898629). And **37 of those are cited by different papers
for different `trait_efo_id`s** — genuinely different findings about the same variant, each of which
would carry its own located passage from its own article, and all of which map onto one
`ProvenanceItem`. That is 13% of the module's variants, on a module of ordinary size, so a
`variant_key`-grained attribution would be lossy for one row in eight before anybody did anything
unusual.

**One thing worth deciding while you are here.** `upgrade` deliberately carries neither
`provenance.json` nor the logs — `carry = set(present) - {PROVENANCE_FILE}`, commented as *"they
describe how the predecessor was built, and this mechanical re-publish has its own (absent)
provenance"*. That reasoning is right for build metadata and we are not asking you to change it. But
under it, a contract upgrade carries `studies.csv` forward with every quote intact and drops the only
record of who located them. If the attributor lands on `StudyRow` it travels with the row and the
question disappears; if instead you decide `provenance.json` is the answer, this is the corner that
needs a rule.

## S56 — `literature.csv` can claim `quotes_authored: 0` beside 859 authored quotes, and nothing compares them

**Status — accepted, both halves shipped as [RM119](ROADMAP_HISTORY.md#rm119--a-citation-sidecar-could-contradict-its-own-studiescsv-and-the-manifest-turned-it-into-a-confident-zero) in the tree (not yet cut).**
Reproduced on our own copy of the data before writing: `aggression_anger/literature.csv` reads
`quotes_authored=0` on all three rows while its `studies.csv` carries 69 quotes — 65 of them on pmid
29500382, the row you quoted.

**The comparison shipped as your first candidate, at compile.**
`_check_quote_counter_is_current` counts the non-empty `provenance_quote`/`provenance_regex` cells per
PMID and warns when the sidecar disagrees, naming both numbers as you asked, aggregated to one line.
Warning rather than error, for your reason. Your `LITERATURE_FACT_FIELDS` observation is what settled
where it goes — the comment already argues that `quotes_authored` is derivable from `studies.csv`, and
that is the argument for recomputing rather than trusting the stored copy.

**Your second candidate — recompute on merge — is not shipped, and we would still like it.** You are
right that it fixes new runs and leaves every published module reporting zero, which is why the
comparison came first; the pass-side half is enricher work and belongs with the next literature-pass
change rather than being bolted on here. Your rejected candidate is rejected for your reason: treating
`0` as `null` when no `quote_source` is set silences the report without making the distinction visible,
and guesses the author's intent from the absence of a second field.

**The second half is the better find and it shipped too.** You are exactly right about the mechanism:
`_literature_block`'s per-row guard works and does not survive the aggregation, because `sum(...)` over
rows that are all null is `0`. The docstring's own sentence is what the block ended up saying, one
aggregation later. Shipped `Literature.quotes_unchecked` — your second option, and the right one for
the reason you gave: three states need three numbers, and `int | None` collapses "never asked" and
"asked and got nothing" back into "no number". It sits beside `open_access_count` as you predicted.
Pinned by a pair of modules identical on `(quotes_authored, quotes_found)` and separated only by the
new counter, which is the confusion it exists to end.

One thing found while wiring it: reading both citation sites means going through `binning_citations`
rather than walking the bin rows, because `DiplotypeRow` has no `pmid` column at all. The suite caught
it. A bin-only citation now carries a denominator of zero rather than being skipped, so a literature
row reachable only from a bin does not read as stale.

Not installable yet — check [CHANGELOG.md](CHANGELOG.md) for whether the version was cut.
<!-- triaged: 0.6.5 · sha 45f7a4949545 -->

*Filed 2026-08-20 by just-module-creator, against enricher 0.6.4 / compiler 0.6.1 as installed.
Found while remediating a real module's quotes; the numbers are from the four published
`antonkulaga/*` modules in your `data/output/corrected_modules/`. This is the separable half of
`S54`'s correction.*

**What we were doing.** Replacing the title-quotes in `aggression_anger` with located passages. Before
editing we read the module's own attestation to see what it currently claimed about them.

**What we expected.** `literature.csv` is the derived sidecar that records what the literature pass
established per PMID, `quotes_authored` among it. With 69 of 69 studies rows carrying a
`provenance_quote`, we expected `quotes_authored` to be 69 spread over three PMIDs, and `quotes_found`
to be some number at or below it.

**What we found.**

```
aggression_anger/literature.csv
pmid,...,quotes_authored,quotes_found,quote_source,...
20585324,...,0,,,...
24489884,...,0,,,...
29500382,...,0,,,...
```

Zero, on every row, in all four modules — 3668 authored quotes and not one of them counted. The
mechanism is ordinary and is not a bug in any single pass: the literature pass ran while
`provenance_quote` was still empty, it wrote what was true then, and the sidecar is merge-not-clobber,
so a later run treats the existing row as authoritative and the counters never move. The module then
compiles and publishes green with a sidecar that contradicts the table it describes.

**Why this is yours and not only an ordering mistake by the author.** The compiler reads both files.
`studies.csv` and `literature.csv` are in the same spec directory, joined on `pmid`, and the count of
non-empty `provenance_quote` per PMID is arithmetic over data you already have in memory. Nothing
compares them, so a sidecar that is stale in exactly the way that matters is indistinguishable from a
current one — and `0` is reported as a number rather than as `null`, which is the distinction this
tier is otherwise built around. A reader cannot tell "the author wrote no quotes" from "nobody ever
checked".

It also defeats the only cheap detector for the `S54` defect. An operator sweeping the catalog for
title-quotes would reasonably start at `quotes_found` / `quotes_authored`; on every module that has
the problem, those columns say nothing at all.

**Candidate fix — one comparison, at compile.** For each `literature.csv` row, count the non-empty
`provenance_quote` + `provenance_regex` cells in `studies.csv` for that `pmid`. If it disagrees with
`quotes_authored`, emit a finding naming both numbers: *"literature.csv records quotes_authored=0 for
pmid 29500382, but studies.csv carries 65 quotes citing it — the sidecar predates the quotes; re-run
the literature pass."* Warning rather than error seems right: the sidecar being behind the table is a
staleness signal, not a malformed module.

**A second candidate, cheaper and weaker: make the pass update the counter on a merge.** The counters
are derivable from the spec without any network — `quotes_authored` needs no fetch at all — so a
literature pass could recompute them even when it merges everything else. That fixes new runs and
leaves every already-published module reporting zero, so we would rather have the comparison; both
together would be better than either.

**A candidate we think is wrong: treating `0` as `null` when no `quote_source` is set.** It would
silence the report without making the distinction visible, and it guesses at the author's intent from
the absence of a second field. The point is that the two files disagree, and saying so is the whole
fix.

**What we did meanwhile.** Nothing in the published data — these are not our modules. In our own
remediation copy we left `literature.csv` as we found it and said so in the module's log, because
correcting it needs the literature pass, which is behind our extended tier; that is our gap and we
are fixing it on our side.

### The second half, found on the way out: the manifest turns the whole thing into a confident zero

We published a remediated copy to the polygon and read the manifest back. `literature.csv` carries
`quotes_found` **empty** on all three rows — null, correctly, because no quote was ever checked. The
manifest for that same module says:

```
"literature": { "row_count": 3, "quotes_authored": 0, "quotes_found": 0, ... }
```

`_literature_block` is careful and its docstring is right: *"`quotes_found` counts only rows where it
is non-null: a null there means 'no fulltext was retrievable', and folding that into zero would report
an unchecked quote as a missing one — the single most misleading thing this block could say."* The
per-row guard does work. What it cannot express is the **total over rows that are all null**: `sum(...)`
over an empty selection is `0`, `Literature.quotes_found` is `int` with `default=0`, and there is no
`quotes_unchecked` beside it. So the exact sentence that docstring calls the most misleading thing this
block could say is what the block ends up saying, one aggregation later.

A reader of the published manifest sees `quotes_authored: 0, quotes_found: 0` and concludes the author
wrote no quotes. That module's `studies.csv` has 69 of them (3668 across the four). And nothing
distinguishes it from a module where three articles were fetched and no quote matched.

**Candidate fix.** Either make the two counters `int | None` in `Literature` and leave them null when
no row carried a number, or add `quotes_unchecked` (rows whose `quotes_found` is null) so the three
states stay three. The second is additive and reads better beside `open_access_count`, which is
already there for exactly this kind of "read it against" qualification.

**And your own note already argues the rest of it for us.** `literature.py`'s `LITERATURE_FACT_FIELDS`
comment gives, as a reason to keep `quotes_authored` out of the fact hash, that it *"is derivable from
`studies.csv` (so storing it as a fact duplicates one fact in two files)"*. That is precisely the
argument for recomputing it at compile rather than trusting the sidecar's stored copy: it is already
understood to be a duplicate of something the compiler holds open at the same moment.
