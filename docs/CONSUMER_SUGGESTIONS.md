# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S52

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

# Field notes from just-module-creator

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed, and
`just-dna-registry` 0.18.2. **Priority: we are writing an author-facing skill straight out of
`MODULE_LIFECYCLE.md` §6 this session, so the answer changes text we ship.***

---

# Field notes from just-module-creator — RM10/RM11 session

*Filed 2026-08-20, against format 0.6.1 / compiler 0.6.1 / enricher 0.6.4 as installed, and
`just-dna-registry` 0.18.2. All three came out of one work item: our MCP surface had three answers
that **restated** a schema fact instead of generating it, and we went looking for the public symbol
to generate each from. Two of the three had none. That is the report.*

## S47 — the machine-produced fact tables have no public (csv → row model) enumeration

**Status — accepted and shipped in `just-dna-compiler` today, filed as
[RM112](ROADMAP_HISTORY.md#rm112--the-machine-produced-tables-have-no-public-csv---row-model-resolver).**
`hints.DERIVED_TABLE_MODELS` (the roster) and `hints.derived_model_for(csv_name)` (the resolver) are
public as of this commit. Drop the hand-kept seven-entry map and the cross-package roster both.

**Your four rejected substitutes all reproduce, including the one you measured.**
`ARTIFACT_PARQUETS - LEAD_PARQUETS` really is **nine** names against seven fact tables — confirmed here,
`annotations.parquet` and `studies.parquet` are in neither set, exactly as you said. And
`authoring_reference()["models"]` being keyed by model name is the crux: it answers *"what columns does
`GeneValidityRow` have"* and cannot answer *"which model is `gene_validity.csv`"*, which is the direction
a tool caller holding a filename actually has. That asymmetry is why "just read `authoring_reference()`"
is not the answer, and your framing of it is the one we adopted into the roadmap entry.

**What it is.** Keyed on the filename a caller names, so both spellings of the licence table answer —
`derived_model_for("licensing.csv") is derived_model_for("sources.csv")`, and there is a test. It is
**derived from `_FACT_TABLES`**, not restated beside it: publishing a hand-kept copy of the map in order
to close a report about hand-kept maps would have been the defect wearing a public name. The guard is set
equality over the walked set, so an eighth fact table fails our CI rather than becoming undescribable —
which is the same test you wrote on your side, and you can now delete it.

Two deliberate exclusions. `verification.json` is not in the roster: it is the attestation document, not
a fact table — no parquet, no `_FACT_TABLES` row, and not a CSV. And `sources.csv` is in **both** maps,
`DRAFTABLE` and this one, because it genuinely is both: the one fact table a human legitimately writes.

**Asking the wrong route names the right one.** `derived_model_for("variants.csv")` raises *"is an
authored table, not a machine-produced one — use `model_for('variants.csv')` instead"*, rather than a flat
"unknown". A generic rejection is a dead end where a specific one is a fix, and dispatching on a filename
is exactly where a caller lands on the wrong one of the two.

**What we did not do, and why.** `describe_table` still refuses non-authored names. Widening it was the
first thing we tried and we backed it out: a caller today can rely on that refusal, and you had already
built the second read-only route yourself — the missing piece was the map, not the presentation. If you
want the derived tables to come back through a `describe_table`-shaped dict, say so and we will add a
separate function rather than change what that one accepts.

**On the cross-package cost you accepted knowingly** — deriving the roster from
`specfiles.FACT_CSVS` so a registry release lagging a compiler release makes your answer lag: that is
real and it is now unnecessary, since the roster ships in the tier that owns the loader. Worth saying
because it is the better instinct in general — the registry recognising every file the compiler reads is
its business — and it was the wrong direction only because the map was private on our side.
<!-- triaged: 0.6.5 · sha 5cd3b2bfb2c2 -->

**What we were building.** Our `describe_table` tool answers a table kind's columns straight out of
`hints.describe_table`, and refuses anything outside `draft.DRAFTABLE`. So the six fact sidecars and
`resolution.csv` are unanswerable through it — an author reading `resolution.csv` or
`frequencies.csv` (which they must read and must never hand-finish) gets `'resolution.csv' is not an
authored table of this format`. We are closing that with a second, read-only route.

**What we needed.** `csv name -> row model` for the machine-produced tables. What exists:

* `just_dna_compiler.compiler._FACT_TABLES` — exactly right, `(csv, parquet, model)` triples, and
  **private**. Our own guidelines forbid importing an upstream private name, and for the usual
  reason: it is free to move in a patch release and we would be the ones broken.
* `hints.model_for` / `draft.DRAFTABLE` — authored kinds only, by design.
* `just_dna_registry.specfiles.FACT_CSVS` + `RESOLUTION_CSV` — public, and **names only**, no model.
* `compiler.ARTIFACT_PARQUETS` minus `LEAD_PARQUETS` — we tried this and it does not isolate the
  fact tables: `annotations.parquet` and `studies.parquet` are in neither set, so the difference is
  nine names where the fact tables are seven.
* `reference.authoring_reference()["models"]` — carries every derived model's assembled column list
  (`FrequencyRow`, `ResolutionRow`, …) keyed by **model name**, so it answers "what are this model's
  columns" beautifully and cannot answer "which model is `gene_validity.csv`".

**What we did meanwhile.** Derived the *roster* from `specfiles.FACT_CSVS | {RESOLUTION_CSV}` (public,
and it is the registry's business to recognise every file the compiler reads), and hand-kept a
seven-entry `csv -> public model` map for the model half, with a test pinning its keys to that
roster so an eighth fact table fails our suite rather than being silently undescribable. Two costs
we accepted knowingly: the roster now comes from a *different package* than the loader it describes,
so a registry release lagging a compiler release makes our answer lag too; and the hand-kept map is
precisely the shape of thing that goes stale — see S48, where ours did.

**Candidate fix.** Make `_FACT_TABLES` public, or publish a `hints.model_for`-style resolver that
covers the machine-produced names as well (`hints.derived_model_for(csv)`, or a `machine_produced=True`
flag). The parquet name in the triple is not something we need; the model is.

**Why not "just read `authoring_reference()`".** It gives us the columns once we know the model, and
the thing a *tool caller* has is a filename. Every consumer that wants to answer "what is in this
sidecar" needs the same map, so each will write the same seven lines, and each will be the one that
did not notice the eighth table.

## S48 — a table kind's natural-key *columns* are not obtainable, only its key *values*

**How we found it.** Our `list_tables` reports a `keyed_on` string per kind — what makes two rows the
same row, which is the question an author asks before appending. It shipped
`copynumbers.csv -> (gene, modifier_gene, modifier_cn)` and stayed that way across 0.6, so we were
telling authors to key on a column whose own description reads *DEPRECATED since 0.6, removed at
1.0*. Ours is a hand-kept string and that is our defect, but we went looking for the derivation and
there is none:

* `draft.natural_key(row)` is public and **row-level** — it takes an instance and returns a tuple of
  *values*, so it cannot tell a tool which columns those values came from. It also returns `None` for
  the four binning kinds on purpose (their rule is overlap, not equality), which is the right answer
  to a different question.
* `compiler._TABLE_DUPE_KEYS` is private, and its values are lambdas — even reaching in, a consumer
  gets no column names out of `lambda r: (r.gene, r.allele)` without source inspection.
* `MeasureBinRow._KEY_FIELDS` (and the per-kind overrides) is exactly the tuple of names we want for
  the binning kinds, and is `_`-prefixed. `CopyNumberRow._KEY_FIELDS` also names
  `effective_modifier_copy_number`, the *property*, not the authorable column — correct for the
  grouper, one step away from what an author is told to write.

**What we did meanwhile.** Kept the strings, corrected every one of them to exact model field names
(three were loose prose: `variant`, `a`/`b`/`trait`, `trait`), and added a test that resolves each
token against `model_fields` and fails if any is missing **or** if its `description` contains
`DEPRECATED`. That guard would have caught `modifier_cn` the day 0.6 landed, which is the whole
reason to write it down rather than fix the one cell.

**Candidate fix.** A public `key_fields(csv_name) -> tuple[str, ...] | None`, returning the authorable
column names, `None` where equality is not the rule (binning), and — if it is cheap — a marker for
which reading applies. `describe_table`'s docstring already promises "the natural key two rows are
the same row by"; today the returned dict does not carry it, and that would be the natural home.

**Why it matters more than one stale cell.** A deprecated column can only be *found* by a consumer
who re-reads the field descriptions on every upgrade. Everything else about a table on our surface is
generated and cannot drift; this one string can, and it is the string an author acts on when they
append a row.

## S49 — `COMPANION_KINDS` pulls `variants.csv` in behind `studies.csv`, which RM47 made wrong for a binning module

**What we ran.** A spec directory with `module_spec.yaml`, `copynumbers.csv` (two SMN1 bins, each
carrying `pmid: 9382095`) and `studies.csv` (one row, `pmid,conclusion`, no variant identity —
legal since RM47). No `variants.csv`.

```
compiler.validate_spec(spec, strict=True).valid  ->  True
```

Strict-green: three warnings, all about closure and CN tiling, none about a missing `variants.csv`.
So the module is legal and is the *intended* shape for a binning module that grounds its thresholds
— RM47's whole point, and `_check_binning_grounding` is satisfied by exactly this.

**What the constant says.** `scaffold.COMPANION_KINDS["studies.csv"] == ("variants.csv",)`, whose
comment justifies the symmetry with "`studies.csv` alone fails with *module has no recognized
table*". True when it is *literally* alone; not true when it sits beside a binning table. So
`scaffold_module(kinds=["copynumbers.csv", "studies.csv"])` warns that `variants.csv` is owed, and
upstream's own scaffold adds a stub for it — inviting an empty `variants.csv` into a module whose
author was doing the right thing. Our own composition rule says never add an empty table to keep
another company, so the two advices now contradict each other.

**What we did meanwhile.** Nothing: we pass `COMPANION_KINDS` through rather than restating it, so
our answer is upstream's answer and patching it here would be the drift we are trying to remove. We
added the RM47 half to the composition note our tools return, so an author reading it at least knows
a study row may name no variant.

**Candidate fix.** Make the `studies.csv -> variants.csv` pull conditional on no other recognised
table being requested — the condition the comment already describes ("alone"). A blunter fix is to
drop that direction of the pair and let the "no recognized table" error speak for itself, but that
loses the help in the one case the pair was added for.

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
