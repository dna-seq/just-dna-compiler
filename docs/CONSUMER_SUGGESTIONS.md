# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S61

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

## S57 — `manifest.stats` is computed from `variants.csv` alone, so a module without one is invisible to a gene search

**Status — accepted; it is the first reading, and the fix shipped in the tree as
[RM121](ROADMAP_HISTORY.md#rm121--manifeststats-described-one-table-and-was-published-as-if-it-described-the-module)
(not yet cut; see the standing rule at the top of this file).** `stats` describes **the module**.
`stats.genes` is now a union over every authored table kind carrying a `gene` column, so nothing needs
re-filing in the registry's intake and your skills can stop telling authors this is a known gap.

**You did not need to leave the choice to us, and the reason is worth having.** `Stats`'s own docstring
has always read *"card/detail stats derived from the spec at compile time"* — from the spec, not from a
table of it — so `variant_stats` was an unimplemented sentence rather than a decision anyone made. That
is the same shape as S48/RM113, where `describe_table` had been promising a key since 0.5 and never
carried one. When a field's documented meaning and its implementation disagree, the documented meaning
is the one we treat as the contract.

**Your measurement reproduced, and the module is worse off than you reported.**
`reference_examples/cyp2c19_star_alleles/` publishes `genes: []` against **1,332** rows naming
CYP2C19 — your 106 in `haplotypes.csv`, plus 1,190 in `diplotypes.csv` and 36 in
`allele_function.csv`. **Seven of our own sixteen reference examples have no `variants.csv`**, and
seven of the eight non-variant gene-bearing models make `gene` *required*, so the affected modules are
precisely the ones that know their genes exactly.

**The guard you wrote into your skills is what made this ours.** An author whose only route to
discoverability is inventing an empty `variants.csv` — which then drags `studies.csv` in behind it —
is being asked to publish a fiction to be found, so the honest module is the invisible one. A gap that
can only be closed by writing something untrue is not a gap the author owns. Keep the README advice
until a release carries this; it stops being necessary then.

Three details you will meet:

- **`variant_stats` is unchanged and still reads `variants.csv` alone.** The wider answer arrived
  beside it as `module_stats(variants, kind_rows)`, because renaming a published function is a major on
  the rule S14 established — a rename is a removal plus an addition. The two differ in exactly two keys.
- **Derived sidecars are not in the union, deliberately.** A gene reaches `gene_metrics.csv` because a
  pass looked it up, not because the author said the module is about it; that set is already published
  as `manifest.gene_metrics.genes`. If your index wants both, it should union them knowingly.
- **No identity moved.** `manifest.json` is not a hashed artifact file and `content_signature` is over
  authored rows, so no `stats` value can reach either — measured byte-for-byte on the module above.
  This is a **patch**, so a recompile publishes the genes and republishes the same digest.

Wiring it found a defect the report could not have seen: the post-symbolic-drop re-derive of `stats`
sat inside the loop's `variants.csv` branch, which was correct while the number read one table.
`pharm_variants.csv` is the other droppable kind and it carries a `gene`, so the fix would have left a
dropped row's gene in a published manifest — the exact class the branch was written against. Moved
after the loop, pinned with a fixture where one row drops and one survives.

The registry half stays yours: what we owed was a field that means what it says.
<!-- triaged: 0.6.6 · sha f8881d2d793d -->

**Reported by** just-module-creator (the authoring plugin), 2026-08-20. Six independent reproductions
during a dossier audit; three of our per-table dossiers reached it separately before anyone connected
them.

`compiler.variant_stats` derives `stats.genes` from `variants.csv` and from nothing else. A module whose
lead table is `diplotypes.csv`, `copynumbers.csv`, `activity_phenotype.csv` or `allele_function.csv`
therefore publishes `gene_count: 0, genes: []` **however many of its rows carry a `gene` cell** — and the
registry's gene index is fed from that field, so `registry_search(gene=…)` cannot return it.

Measured on your own reference example: `cyp2c19_star_alleles` publishes `genes: []` with **106 rows
carrying `gene=CYP2C19`**.

**Why this is a report rather than a request.** The obvious repair is the wrong one and we have written a
guard against it into our skills: adding an empty or invented `variants.csv` to make a PGx module
discoverable trades a discoverability gap for a dishonest module, and `studies.csv` becomes required the
moment `variants.csv` exists. So an author's only honest workaround today is prose — name the genes in
the README, where a text search finds them — which is what we tell them to do.

The question is whether `stats` is meant to describe **the module** or **`variants.csv`**. If the first,
the fix is in `variant_stats`: union the `gene` column across every table kind that has one. If the
second, then the field is doing what it says and the gap is the registry's index reading a
variants-shaped field as a module-shaped one — in which case we will re-file this in their intake, and
the docs should say plainly that `stats` describes one table.

We have no preference between those two; we do have a preference for knowing which, because our skills
currently tell authors this is a known gap and cannot tell them who will close it.

---

## S58 — four authored table kinds are unconsumable end to end, and nothing in the format says so

**Status — accepted as the documentation defect you filed it as; both of your two closers shipped in
the tree, and the third question they raise is filed as
[RM122](ROADMAP.md#rm122--the-measure-lookup-is-specified-and-nothing-anywhere-implements-it).**
[SCHEMAS.md](SCHEMAS.md) now carries the normative bin lookup beside the genotype one, opening with the
plain sentence that the family is specified ahead of its consumers. You asked for either; you have both,
because the paragraph without the admission would still have left an author guessing whether anything
reads it today.

**Your negative finding reproduced, against the one consumer we can check.** `just-dna-lite` — the
reference consumer, and the tree that renders reports — touches `repeat_alleles`, `copynumbers`,
`heteroplasmy` and `activity_phenotype` in exactly two places, both of which **count rows**: the
lead-table roster that decides how a spec is routed, and the enrichment ceiling. Nothing selects a row
by a measured value; there is no `measure_kind`, `measure_min` or `measure_max` anywhere in it. We
cannot speak for consumers we cannot read, so the finding is scoped to that one and stated that way.

**Your recap of the semantics was right in every particular except one, and the exception matters
enough to be why a paragraph beats a summary.** `measure_tiling: continuous` is the tiling where
adjacent bins **may** share an endpoint and the higher one owns it. Under `quantised` a shared endpoint
is an *overlap error* — the grid reading is the stricter one, not the looser one — and `activity_score`,
which defaults to neither, refuses a shared endpoint as well. The tie-break you need is one rule that
covers all three: **among the rows whose inclusive range contains x, take the greatest `measure_min`**,
which is unique because equal lower bounds are refused on every kind.

Four things the paragraph states that a reader of the columns would not arrive at:

- **Scope to the group before selecting.** `validate_bins` enforces non-overlap *within* a group —
  the table's own key columns plus `trait_efo_id` — so a lookup that scopes wrongly meets an overlap the
  compiler passed and is right to. `binning._bin_groups` is that partition, and its docstring already
  said it is "the way a consumer's lookup groups them".
- **`trait_efo_id` multiplies the answer.** Overlap *across* traits is legal and means pleiotropy, so
  one measurement selects one row **per trait**. A lookup returning a single row is wrong on that case,
  and it is the case a PGx-shaped consumer will meet first.
- **Compare in float32** (RM62), which bites hardest on a bin boundary because a boundary is exactly
  the round decimal an author picks. The rule is *compare in* float32, not *narrow the bound* — the
  latter shipped once and is one-sided, since `float32(0.9)` lands below `0.9`.
- **No match withholds; a missing measurement selects `unresolved`.** Two different answers, and
  neither is the lowest bin.

We also put a short paragraph in the authoring skill telling an author to write what the bins mean into
the README, for exactly the reason you give: prose is the path to a reader today.

**What we did not do, and why it is filed rather than shipped.** The obvious next step is to publish the
lookup as a **function** — `alleles.split_genotype` is the precedent, and one leaf every tier calls is
how two implementations are stopped from disagreeing. RM122 carries it, open, because the signature has
real questions that only a consumer can settle: one row or one per trait, `None` for no-match or a
three-state result separating *no match* from *unresolved selected*. Shipping a leaf against a
hypothesis fixes the wrong thing and P3 keeps it working forever. **If you or anyone writes the lookup
against the paragraph, your questions are the signature** — send them and RM122 closes.
<!-- triaged: 0.6.6 · sha 161383883db1 -->

**Reported by** just-module-creator, 2026-08-20. Three independent reproductions.

The binning family — `repeat_alleles.csv`, `copynumbers.csv`, `heteroplasmy.csv`,
`activity_phenotype.csv` — needs a consumer that takes a **measured quantity** and selects the row whose
`[measure_min, measure_max]` contains it. As far as we can find, **no consumer implements that lookup**,
so those four kinds annotate nothing downstream however correctly they are authored.

The format side looks complete to us: bounds inclusive, `min == max` for a sharp value, a null bound for
open-ended, `measure_tiling` deciding whether adjacent bins may share an endpoint, and the `unresolved`
sentinel for an absent measurement. One lookup would serve all four.

**What we are actually reporting is a documentation gap, not a missing feature**, because the feature is
not yours to write. `SCHEMAS.md` specifies the consumer join contract for a genotype in normative detail
— the three states, `*` as unknown, the callability pointers — and specifies nothing equivalent for a
*measure*. So an author reading the docs cannot tell that authoring a heteroplasmy module produces
nothing a reader will render today, and we had to establish it by looking.

Two things would close it for us, either of them: a normative paragraph in `SCHEMAS.md` stating the bin
lookup a conforming consumer must implement (which also gives whoever writes one a target), or an
explicit sentence saying the binning family is specified ahead of its consumers. We tell authors the
tables are still worth writing and to say in the README what the bins mean, since prose is the only path
to a reader right now.

---

## S59 — three attestations record a check that could not have failed

**Status — the generalisation is accepted and shipped as
[RM123](ROADMAP_HISTORY.md#rm123--two-attestations-recorded-a-check-whose-scope-they-could-not-state)
in the tree (not yet cut). Two of your three reproduced; the third shipped four releases before the
enricher you are running.** Taking them in your order.

**(1) `enrich_pgx` grading CPIC's own table — the skip you asked for exists, and you found the one case
where it does not reach the record.** `pgx._tautology_note` is exactly `clinical.tautology_reason` one
source over: the licence row must name **this** release *and* the drafter's digest must still match,
either half missing runs the leg. It has been in the tree since **0.6.0** (RM73's provenance half), it
is **per leg** rather than per record — PharmVar is an independent authority and a whole-record skip
would throw away a real comparison to suppress a hollow one — and `pgx_draft` stamps the release that
keys it.

So the check is not the problem; the **record** was. `_function_check_record` has two branches. The
skip branch joins every non-answered leg's note into `detail`, so a tautology-only run already says so
— that is presumably the one you would have seen on a CPIC-only module. The **answered** branch built
`detail` from the answered legs alone, so a CPIC-drafted module with PharmVar answering published
*"compared N authored allele function(s) against pharmvar (…)"* and nothing at all about CPIC. The note
was on `result.warnings`, which is the run's stderr, and the run is not part of the module. Reproduced
by calling `_function_check_record` with a mixed `legs` dict and asserting `"cpic" not in detail`.

Fixed by appending the withheld legs, **sorted by source in both branches** — `verification.json` is a
hashed input and `legs` fills in whichever order the pass reached the authorities, so an
iteration-order sentence is a file whose bytes depend on which authority answered first.

**(2) `_flag_advisory_columns` — reproduced exactly as reported, including which pairs.** Six of them:
`clin_sig` on all four binning kinds and on `diplotypes.csv`, and `evidence_level` on `diplotypes.csv`.
`verify_clin_sig` takes `list[VariantRow]`; the ClinPGx check loads `pharm_variants.csv`. Your framing
is the one we took — the advice stays right and the *reason* was false, which is the worse half,
because it implies a green run is agreement.

`hints.REDUNDANCY_BEARING_TABLES` now narrows the explanation, and the affected pairs read *"left to
the author on purpose, and on this table for a different reason than on variants.csv: …
does not read diplotypes.csv, so nothing here compares the cell against a source"*.

Three things worth knowing if you consume that map:

- **It scopes the explanation, never the refusal.** `REDUNDANCY_BEARING` stays keyed on the bare
  column, because whether a provider should start filling `clin_sig` on a binning row is a decision
  nobody has taken and we are not taking it as a side effect of fixing a message.
- **Six columns are deliberately absent, and the absences are checked claims.**
  `rsid`/`chrom`/`start`/`ref`/`alts` stay unscoped because resolution reaches the positional table
  kinds and the PGx tables (RM43), so a coordinate on `heteroplasmy.csv` really is cross-examined; and
  `pmid` stays unscoped because RM47 made a binning row a **second citation site** and
  `enricher.literature` reads both through `binning_citations`. We nearly scoped all six from the
  checker-name strings, which would have suppressed a *true* advisory — the same defect facing the
  other way. Every entry and every absence has a test.
- **The model→CSV direction is derived from `draft.DRAFTABLE`**, so a kind added later is scoped by
  construction rather than by someone remembering.

**(3) `enrich_facts` collapsing "no constraint published" into "not asked" — does not reproduce, and
here is what was probed.** No symbol or CLI command of that name exists in any of the three tiers, so
we read it as the gene-constraint pass (`just-dna-enricher gene-metrics` → `enrich_gene_metrics`, the
only thing that fetches constraint). There the two states are already separate, in the same loop:

- a gene that was looked up and gnomAD publishes no constraint for gets a **`not_found` row** — a
  fact, and true of many small or non-coding genes;
- a gene that could be asked through neither route gets **no row at all** and lands in
  `GeneMetricsResult.unconsulted`, with its own warning naming the genes and saying nothing is known
  about them.

That split is RM98, shipped in **v0.6.1** (`c4959f1`, *"two passes recorded an absence nobody
established under --offline"*) — before the enricher 0.6.4 you filed against. So the cell you describe
is not one cell. **This negative is scoped to that pass**: we did not probe the other fact passes for
the same shape, and if you meant one of them, re-file naming it and we will.

**On the generalisation itself, which is the part we found most useful.** *A check that could not have
failed should record why rather than record a zero* is now doing work in two tiers, and your ClinVar
example was the right template to point at because it is the one that had already been generalised —
`tautology_reason` and `_tautology_note` are the same conjunction over different sources, and the
digest half (RM73) is what makes them survive an author's edit. What was missing was never the skip.
It was that a record has to carry the scope even when the check **did** run, which is your sentence.
<!-- triaged: 0.6.6 · sha 20ed3e72a9a7 -->

**Reported by** just-module-creator, 2026-08-20. Found while auditing what our own tools may claim.

`verification.json` is the record a later reader trusts, and three cases inflate what it appears to say.
None is a bug in the checking code; each is a check whose scope makes a green answer uninformative, and
the record does not carry the distinction:

1. **`enrich_pgx` grading CPIC's own table.** A module drafted from CPIC and then compared against CPIC
   agrees by construction. You already solved exactly this for ClinVar: a `panel:` block pins the release
   and `verify_clin_sig` **skips with a stated reason** rather than reporting a zero it could not have
   avoided. The PGx side has no equivalent.
2. **`hints._flag_advisory_columns` naming checkers that cannot see the table.** `REDUNDANCY_BEARING` is
   keyed on a bare column name with no model attached, so the `clin_sig` advisory prints on binning
   tables and the `clin_sig`/`evidence_level` advisories on `diplotypes.csv`, while the checkers it names
   are driven from `variants.csv` and the PGx annotation tables. The advice stays right; a green run is
   not evidence of agreement with anything.
3. **`enrich_facts` collapsing "no constraint published" into "not asked".** Two different states, one
   cell.

The generalisation we would find most useful is the one your ClinVar skip already embodies: **a check
that could not have failed should record *why* rather than record a zero.** `subjects=0` with no
`skipped` key currently means "ran over nothing", and that is the right encoding — the gap is that a
check which ran over a non-empty set it could not disagree with looks identical to one that genuinely
agreed.

We are not asking for a severity change. We are asking whether the record can carry the scope, so a
reader can tell "checked and agreed" from "compared a source with itself".

---

## S60 — an author's correction to a derived table has nowhere to live except inside it

**Status — accepted as a design, filed as
[RM124](ROADMAP_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it)
for 0.7, and it answers the question [RM83](ROADMAP_0_7.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold)
has been blocked on since it was filed.** Your tier argument is accepted and is not among the open
questions. **And your first prerequisite is already discharged: S51 shipped as RM115 and was cut as
0.6.5 this morning** — read the keys off `hints.key_fields`, because your derivation is now stale on
four of the seven tables, and one of the four is the one this design turns on.

**Start with RM83, because it makes your report land differently than you filed it.** RM83 named a
missing `--refresh` and then named what stopped half of it being buildable: *on most sidecars nothing
records that a row was overridden*, so "re-derive the machine rows and keep the overrides" is not
implementable — the tier cannot tell a curator's edit from what the source said last time. It offered
two exits: compare and report every difference without classifying it, **or** something has to start
recording the edit, "a schema question with the usual cost, not a flag."

You built the first exit, in good faith, and it stopped exactly where that paragraph says it must. That
is the strongest thing in your note: it is not a proposal against a hypothetical, it is a report that
the cheap exit has a ceiling and where the ceiling is. RM124 is the second exit, and it carries your
shape.

**The keys, which you should re-read before designing the subject.** `key_fields(csv_name)` now answers
for `resolution.csv` and all seven fact CSVs, and every model declares `_KEY_FIELDS` that every pass
keys its `existing` map off. Against your measured table:

| table | yours | published |
| --- | --- | --- |
| `resolution.csv` | `(variant_key)` | `(variant_key)`, **`rule="subject"`** |
| `frequencies.csv` | `(variant_key, population, dataset)` | `(variant_key, population)` |
| `gene_metrics.csv` | `(gene, dataset)` | `(gene, dataset)` |
| `gene_validity.csv` | `(gene, dataset)` | `(assertion_id)`, **fallback** `(gene, disease_id, moi, submitter, dataset)` |
| `literature.csv` | `(pmid)` | `(pmid)` |
| `clinical_assertions.csv` | `(variant_key, dataset)` | `(variant_key, variation_id)` |
| `gwas_effects.csv` | `(association_id, variant_key, dataset)` | `(association_id)` |

**The `rule` is the one that bites your design, and it bites on your flagship case.** `resolution.csv`'s
key is a **subject**, not a uniqueness constraint: one `variant_key` legitimately resolves onto several
loci, `locus_index` orders them, and a pass replaces the group whole. So a `(table, subject, field)`
overlay row cannot say *which locus* it corrects — and `source="manual"` rows in `resolution.csv` are
precisely the case you say no re-run recovers. Either the subject gains a within-group discriminator for
the one table that needs one, or overlays there are group-scoped and the schema says so. Read `rule` and
`fallback` as well as `columns`; `gene_validity.csv`'s two-level key has the same hazard facing the other
way.

**Three more open questions, all named in RM124 rather than left for you to find.**

- **P5, and it is the one we would settle first.** S52 shipped `ProvenanceItem.outranks: dict[str, str]`
  — `{column: why}`, an authored cell outranking a source, with prose. Your overlay is a corrected cell
  in a *derived* table, with prose. Your split is clean as stated and it is exactly the kind of line that
  erodes: the first author explaining why their `clin_sig` beats ClinVar **and** why their `chrom` beats
  Ensembl has to learn which of two files each belongs in. So your "if you can only do one, we would
  rather have the overlay" is noted and is not quite the choice — S52's capture half is already in the
  tree, and the question is whether one record with a table column serves both.
- **What Principle 7 makes of a build product.** If the compiler applies the overlay, `reverse_module`
  has to produce a spec directory that recompiles byte-identically: pre-overlay table plus overlay, or
  post-overlay table plus overlay (where it applies twice and the fixed point must be checked rather than
  assumed). `resolution_signature` and the fact signatures are over the derived tables as they stand
  today, so which of the two they cover is the same question wearing an identity.
- **Whether merge-not-clobber survives.** This is the real prize and the real cost: `derived = f(source,
  overlay)` lets the rule be dropped for the covered tables, which removes the operational fact RM83
  opens with — and every pass writes through it, so dropping it changes what a re-run does to every
  module already published. That is what makes this 0.7 and not a minor.

**Your second dependency is smaller than you think.** `RECOGNIZED_SPEC_FILES` is the registry's, and it
is built from `SPEC_DATA_FILES` — a **hand-kept mirror** of our table constants, with a comment recording
the `licensing.csv` loss as the reason it must be kept current. So an overlay needs one entry added
there, which is the same one-line coordination every new table kind already needs. Not a blocker; a step.

**What we are keeping regardless of the shape.** The terminal-state observation — an overlay row that no
longer changes anything means the source caught up, so an authored judgement was later vindicated and
the record is retirable. It is free, it is available nowhere else in this format, and it is the second
time you have found the same shape: S52's reply records the same property for a resolved outrank. Two
independent sightings is what makes it a property of the design rather than a nice detail.

Charter-wise this is legal and specifically invited, which is worth saying plainly since you framed it
as a large ask: a new optional authored table is additive and minor-legal, and the 2026-08-12 cost
amendment names your exact class — *a derived table that is both machine-written and human-overridable
can be edited into a state that is not merely stale but is a false claim, and that wants a mechanism
rather than a convention.* It is full-cost, because a human writes it. The four questions above are what
stand between the shape and a build, not the legality.
<!-- triaged: 0.7 · sha 6f54598696e0 -->

**Reported by** just-module-creator, 2026-08-20. A 0.7-sized ask, and we think it is compiler work
rather than ours — the argument for that is at the bottom.

### The mechanic

Every derived sidecar is merge-not-clobber: a pass that finds a subject already recorded leaves it
alone. That is what lets a hand-corrected cell survive a re-run, and it is also why a re-run refreshes
nothing. So the only way to ask a source whether it still says what the file says is to **delete the
file and re-derive it** — which discards the author's rows along with the stale ones.
`resolution.csv`'s `source="manual"` rows are the case that no re-run recovers, because a human worked
them out.

We built a non-destructive wrapper around that sequence (capture, verify the capture, delete,
re-derive, classify, reapply what is provably the author's). It works, and it stops at the one thing it
cannot do. When a subject is present in both the captured and the fresh copy with a differing fact, the
fresh row is **either** a cell the author edited **or** a revision the source published, and with two
data points there is no third to separate them. So it reports and refuses to resolve.

That refusal is honest but it is a symptom. The cause is that **an author's judgement is stored inside
a machine-derived file**, with no marker saying so — authored and derived mixed in one table.

### What we would like instead

A recognized **authored overlay table** that lies on top of a derived one and is never merged into it.
One row per `(table, subject, field)` carrying the authored value, the reason in prose, who decided,
and when. The derived files then become pure build products — `derived = f(source, overlay)` — and:

- nothing is ever hand-edited, so re-derivation is non-destructive **by construction** rather than by a
  wrapper being careful;
- a difference between a fresh row and a previous one means the source revised, full stop. The
  three-explanations ambiguity above stops existing rather than being reported;
- the reason for a correction travels with the module instead of living in whoever's memory;
- **the terminal state becomes detectable, and it is free.** An overlay row that no longer changes
  anything means the source caught up — evidence that an authored judgement was later vindicated, which
  is available nowhere else in this format today, and it makes the record retirable.

### Two dependencies, one of them already filed

The overlay's subject has to name a derived row exactly, and **the per-table merge key is not public** —
each pass keys its own `existing` dict on a local expression. That is already **S51**. We currently
derive the key as each table's `*_FACT_FIELDS` narrowed to the required columns, which reproduces the
pass key on five of seven tables and is coarser on the other two; measured, that gives
`resolution.csv (variant_key)`, `frequencies.csv (variant_key, population, dataset)`,
`gene_metrics.csv (gene, dataset)`, `gene_validity.csv (gene, dataset)`, `literature.csv (pmid)`,
`clinical_assertions.csv (variant_key, dataset)`,
`gwas_effects.csv (association_id, variant_key, dataset)`. An overlay keyed on a derived guess is not
something we would want to ship, so S51 is a prerequisite rather than a nice-to-have.

The second: `RECOGNIZED_SPEC_FILES` has 24 entries and none of them is an overlay, and we found no
`override` or `mask` notion anywhere in the schema or compiler source. A file we invent in a spec
directory is dropped by the next server-side rebuild — the way `licensing.csv` was lost before registry
0.16.2 — so we cannot make this travel on our own however we implement it.

### It also changes what S52 is asking for

**S52** asked you to pick a per-field shape for `provenance.json`, because an outrank is naturally per
field and `rationale` is one string per `variant_key`. If an overlay table exists, that question
narrows a long way: the overlay carries corrections to **derived** tables, and `provenance.json` goes
back to being the reason-record for an **authored** cell that outranks a source — which is what it
reads like it was designed for. If you can only do one of the two, we would rather have the overlay.
We have written per-field records into `provenance.json` in the meantime and they re-emit into whatever
you settle on.

### Why the compiler and not us

We can apply an overlay at build time ourselves, and we considered it. The reason we are asking anyway
is that **an overlay is authored input, not a repair**. A compiler that reads it is doing what it
already does with every other authored table — compiling what the author wrote — and none of
report-never-repair is at stake, because nothing is being inferred or corrected on the author's behalf.
Whereas if each downstream tool applies its own overlay, two consumers compiling the same spec directory
can disagree about what the module says, and the artifact stops being a function of the spec.

The business decision — *whether* this authored value outranks that source — stays ours, and we would
not ask you to take it. What we are asking for is the place to put the answer.
