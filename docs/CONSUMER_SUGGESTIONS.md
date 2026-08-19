# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S54

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
