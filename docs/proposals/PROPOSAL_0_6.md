# 0.6 design thread — the decisions, with their reasoning

**What this is.** Stage 3 of the design cycle for the 0.6 line: every open `RMn` in
[ROADMAP.md](../ROADMAP.md)'s 0.6 bucket, taken one at a time, argued to a decision. It is the brief the
implementation works from, so it is deliberately exhaustive: each item records the problem in plain
terms, the facts established while deciding it (several overturned what the roadmap entry says), the
decision, the reasoning, **the repairs that were rejected and why**, and the consequences that follow
without being chosen.

The rejected-repairs sections are the load-bearing part. An item's decision is cheap to re-derive; the
knowledge that three plausible alternatives are wrong, and *why*, is what stops the next pass
rediscovering a worse answer. Same convention as RM31/32/33/35.

**Status.** Decided 2026-08-13, on the `0.6` branch, before implementation. Nothing here has shipped.
Where a decision changes what ROADMAP.md says, ROADMAP.md is stale and this file wins until the item
lands and moves to ROADMAP_HISTORY.

**Scope.** Sixteen items. Ten build, two stay deferred, two close as items, two were never in scope.
Plus one charter amendment that lands **first and alone**, because several decisions below depend on
the rule it states.

---

# Commit 0 — the charter amendment: what a schema change costs, by layer

**This is its own commit, before the batch.** It is not an item; it is the rule the batch reasons
with, and four decisions below turn on it.

The Constitution rules on whether a change is *legal* (Principles 3/4/8: additive is minor, removal
and promotion-to-required and retyping are major). It says nothing about what a legal change *costs*.
The absence showed up repeatedly as "too many tables" — an instinct that is correct about some
additions and wrong about others, with no way to tell which.

**The rule.** A schema addition's cost depends on the layer it lands in:

| Layer | Cost | Why |
|---|---|---|
| **Parquet columns** | ~free | materialized, derived, no human ever types one; invisible to an author |
| **Derived CSVs** | half | machine-written, but a human *can* still edit them — and that should be discouraged |
| **Authored schemas** | full | a human writes them, so every column is a burden on the rare author |

**Consequences to state alongside it, because they are what make it operative:**

- The "one CSV, one concern / do not burden the rare author" gate in CLAUDE.md is a rule about the
  **authored** layer. It does not price a parquet column, and it prices a machine-written sidecar at
  half. A new derived fact table is not the same kind of object as a new authored table, and treating
  them alike is what made two obviously-worth-building items look like creep.
- **`resolution.csv` is a build-time derived artifact whose only consumers are the compiler and the
  enricher's update run.** It gets **no parquet**, deliberately. This is currently written down
  nowhere — SCHEMAS.md must say it, because "publish it as a parquet" is the first thing anyone
  proposes when they hit RM43.
- Discouraging hand-editing of a derived CSV is a live design concern, not a style note. RM45 below is
  the first case where a hand-edited derived file is not merely stale but is **forgery**, and it needs
  a mechanism rather than a convention.

**Where it goes.** The Constitution, as an amendment (the charter already rules on additivity, so cost
belongs beside it, and an amendment makes it binding on every future design review). CLAUDE.md and
SCHEMAS.md carry the practical consequences.

---

# Decisions

## RM43 — positions never reach the pharmacogenomics tables

### The problem

`compile_module` resolves rs-numbers to coordinates for `variants.csv` and for nothing else. Every
other table goes through `_build_table`, which is `model_dump()` → parquet. So a module whose main
table is `pharm_variants.csv` or `haplotypes.csv` keeps exactly the coordinates its author typed —
which, for an rs-number-authored module, is none. A consumer matching a patient VCF by position
matches nothing, silently, as an empty result rather than an error.

Reproduced on this tree's own `reference_examples/pgx_slco1b1_simvastatin/`: 9 rows, every coordinate
null, while the `resolution.csv` sitting beside the spec resolves the rs-numbers perfectly well. The
motivating field report is a ClinPGx module with 1,482 rows and 147 variants in the same state.

### Facts established while deciding

- **`resolution.csv` is byte-hashed into `manifest.derived` (S26, 0.6.0) but is materialized as no
  parquet.** `_FACT_TABLES` is frequencies / gene_metrics / literature / sources; resolution is not
  among them. So for a table-only module the coordinates exist **nowhere in the compiled artifact**.
- The three positional table kinds are `pharm_variants.csv` (`PharmVariantRow`, `pgx.py:278`),
  `haplotypes.csv` (`HaplotypeRow`, `pgx.py:81`) and `heteroplasmy.csv` (`HeteroplasmyRow`,
  `binning.py:~310`). `HeteroplasmyRow` already carries the full identity set including `alts` (0.5.1);
  `HaplotypeRow` carries rsid/chrom/start/ref plus its defining `allele`; **`PharmVariantRow` carries
  rsid/chrom/start/ref and has no `alts` column at all**.
- `variant_key` is a **property** on these models, so it is materialized in no PGx parquet — a
  consumer cannot join a PGx row to `weights.parquet` on it even in a module carrying both.

### Decision

1. **Fill** the resolved coordinate into the positional parquets at compile time, from the injected
   `resolution.csv`.
2. Add a **stamped, parquet-only "what identity did the author actually type" column** per positional
   model — the shape `VariantRow.authored_ident` already has (`spec.py:282`, marked `COMPILER_MANAGED`
   at `base.py:66`, materialized to parquet, never re-emitted by reverse).
3. **Materialize `variant_key`** on the positional parquets, the same way.
4. Also fill **`alts` on `PharmVariantRow`**, as a parquet-only column.
5. **No `resolution.parquet`.**

### Reasoning

The cost model decides most of it. A stamped parquet-only column is ~free, and stamped-columns-as-a-
class is overdue: `VariantRow` has had exactly this mechanism since 0.5 and nothing generalized it.

`alts` is filled as **data, not identity**. `variant_key` continues to be computed *without* `alts`,
so the existing contract — "a pharm annotation matches a variant at `chrom:start:ref` regardless of
allele", which `_collect_subjects` deliberately chose — is unchanged. What the consumer gains is a
direct VCF join, since a VCF row carries REF and ALT. The roadmap's worry that adding `alts` "would
make the key allele-specific" conflates the column with the key; keeping them separate costs nothing.

### Rejected, and why

- **Publish `resolution.csv` as `resolution.parquet` and let consumers join through it.** Superficially
  the cheapest repair — nothing is filled, so the round-trip is untouched, and it is a passthrough of a
  file already hashed into the manifest. Rejected because `resolution.csv` is a *build-time derived
  artifact* whose consumers are the compiler and the enricher, and promoting it to a published table
  makes it a consumer contract it was never designed to be. (This is the reasoning that produced the
  charter amendment above; it needs to be written into SCHEMAS.md, or the proposal recurs.)
- **Fill the cells with no stamped column** — the naive repair the roadmap names. It moves
  `content_signature` (`sha256:8173dab7…` → `sha256:fb91ffa2…` on the reference example), because
  `reverse_module` rebuilds the CSV from the parquet and a machine-filled coordinate returns as an
  *authored* one. That is precisely what `authored_ident` exists to prevent.
- **Leave it legible only** (0.5.3's per-table unjoinable counts). Rejected: legibility was the interim,
  and the gap is now the largest correctness hole in the tier.
- **Leave `variant_key` computed and let consumers re-derive it.** Rejected on the RM40/RM41 rule: a
  value this workspace computes and discards gets recomputed by every consumer, and a recomputation is
  a place to drift. The precedence rule (`rsid`, else VA, else coordinate key) is exactly the kind of
  thing a consumer re-implements slightly differently.

### Forced consequences (not choices)

- **`reverse` must rebuild `resolution.csv` from the positional parquets.** Once coordinates are
  filled, a reverse that drops the lookup table produces a spec whose recompile yields unfilled
  parquets — so `compile → reverse → compile` stops reproducing the artifact, breaking P7.
  `_write_resolution_csv` currently rebuilds from `weights.parquet` alone; it gains the positional
  tables as a second source, under the same provenance rules already documented there
  (`source="reversed"`, `status="resolved"`, blank `fetched_at`; provenance columns are outside the
  fact set by design and cannot be recovered).
- A symbolic or unresolvable allele still falls through to the coordinate key; nothing here changes
  identity derivation.

### Touches

`schema` (three positional models gain two stamped fields each; `base.authored_field_names` and
`reference._ALL_MODELS` must stay correct), `compiler` (`_build_table` for positional kinds, the
resolution join, `_write_resolution_csv`, reverse `fieldnames`/`_scalar_cell`), round-trip tests.

---

## RM45 — the manifest cannot say whether anything was verified

### The problem

A downloaded module's manifest is detailed about how rs-numbers were *resolved* and silent about
whether any claim was ever *checked*. A module whose clinical-significance calls were cross-checked
against ClinVar and one where the check never ran ship **identical** manifests — not through an
oversight in some path, but because no field exists that could differ. `Compilation`'s fields carry
nothing about verification; `ResolutionRow`'s columns are all per-row; `EnrichmentResult` holds
`clin_sig_not_checked` / `ref_mismatches` / `stale_rsids` / `vrs` and dies when the process exits.

This is S4's own argument one layer down. 0.5.2 accepted that an empty conflict list means both
"compared everything" and "never compared", and fixed it — on `EnrichmentResult`. The layer that
outlives the run inherited none of it.

### Decision

- **The seam is a derived sidecar the enricher writes and the compiler reads**, consistent with every
  other injected table, with its own fact signature, testable end to end inside this workspace.
- **The attestation is bound to a hash of the module bytes it was computed over, plus a proof-of-work.**
  Purpose is to prevent *accidental* forgery. The library is explicitly **not** meant to be
  hack-resistant, and nothing here should be built as though it were.
- **The proof-of-work is ONE per sidecar, per enrich run — never per row and never per check.**
  Budget ~1 second total. A ClinVar-pathogenic-scale module must build in ≤2 hours; a per-row PoW
  would make that days.
- **The nonce is found deterministically** — the smallest nonce counting up from zero that meets the
  difficulty — never by random search, or the sidecar's bytes differ every run and it collides with
  the determinism rules the round-trip tests pin.
- **A stale or non-matching attestation: warn, and drop the block.** The compile succeeds and the
  manifest carries no verification block, which reads correctly as *says nothing* rather than as a
  pass.
- **Check names are a closed vocabulary, audited once now** — reference allele, rs-number currency,
  ACMG secondary findings, clinical-significance cross-check, identifier/trait currency,
  quote-checking, dosage sensitivity, gene–locus conflict. Members are permanent within a major, so
  the set is fixed against everything that could plausibly join it rather than grown ad hoc.
- **Skip reasons are a closed vocabulary too**, with the human sentence *beside* the machine key, not
  instead of it (`clinical.tautology_reason` already writes a good sentence; it stays as detail).
- **Manifest shape: a `Verification` block**, on `Frequency`'s precedent — it has its own producer, its
  own release and its own fact-hash, and it needs to carry the release id it verified against
  (`locations.read_release`). Absent on a module nothing verified.
- **Also stamp `resolution_signature` / `resolution_sources` for table-only modules.** Unblocked purely
  as a side effect of RM43 (reverse can now rebuild the lookup table from the positional parquets), so
  the hole has no remaining reason to exist.

### Reasoning

Free-string check names would recreate RM44 one level down — a `dict[str, int]` keyed on prose lets the
enricher write one spelling, a registry another, and a consumer substring-match the difference. Same
for skip reasons: backfill triage branches on *why* a pass did not run, so prose relocates the
substring matching rather than ending it.

Counts rather than bools, and **two fields rather than one union-typed slot**, so "ran against 0 rows"
and "did not run" can never occupy the same value — `vrs_alleles`/`vrs_alleles_identified` is the
precedent.

### Rejected, and why

- **An argument on `compile_module`** (what the reporter proposed). Cheaper, no new file — but then the
  only producer is the caller, so the format would declare a manifest field its own reference
  implementation never fills. That is exactly how `VALID_SOURCE_LAYERS` ended up with members no file
  carried. The enricher could not reach it at all without a wrapper wiring both tools.
- **Carry it in `resolution.csv`.** It is per-row by construction; "this pass did not run" is per-pass
  and has no row to attach to.
- **Make a mismatch fatal.** Considered — a record asserting a check over bytes that are not these
  bytes is arguably the same contradiction class as an inconsistent reference allele. Rejected because
  the goal is that a stale record never becomes a *published claim*, not that it be impossible to
  write; dropping the block achieves that without blocking an author mid-edit.

### Trust rule (must ship with it)

`compiled_by`'s description already says "foreign values are untrusted". Every field of the new block
says the same, in the field descriptions **and** in SCHEMAS.md — a forged pass is worse than silence,
and the first consumer to read this off an untrusted manifest will believe it otherwise.

### Does not subsume RM44

`resolution_subjects` is the denominator of a flag about *resolution*, which is not a verification
pass. Already shipped; unaffected.

### Touches

`schema` (the `Verification` block, two vocabularies, the sidecar row model), `enricher` (writes the
sidecar, computes the binding hash + PoW), `compiler` (reads, validates the binding, stamps or drops).
Depends on RM43 for the resolution-signature half.

---

## RM47 — a threshold is the most interpretive claim in the format and the only one with nowhere to cite

### The problem

Binning tables map a measured number to a conclusion — a CAG repeat count to Huntington risk, a
heteroplasmy fraction to a phenotype. Those thresholds are the most *interpretive* thing a module
states, and nothing can cite them. `StudyRow` identifies its subject by `rsid` or `chrom`(+`start`);
a `repeat_alleles.csv` row is keyed `(gene, repeat_unit)`. So no citation row can name a bin.

`reference_examples/htt_repeat_expansion` compiles clean under `--strict` asserting four Huntington
thresholds — 26/27, 35/36, 39/40 — with no citation anywhere, and its README says *"a module making a
novel claim should carry its evidence"*: advice the schema gave the author no way to take.

0.5.4 shipped `_check_binning_grounding`, which warns in both modes. That was the interim.

### Decision

- **A pointer on the binning row** (a PubMed id) grounds the *boundary*. One optional column on the
  binning base reaches all four kinds.
- **The citation table's subject requirement is relaxed** — a citation row may exist without naming a
  variant, so it can ground a module or a gene-keyed table honestly instead of authors writing a bare
  `chrom=4` for HTT. Widening an either-or rule only makes previously-*invalid* rows valid, so no
  published module breaks.
- **The line, which must be stated in the docs: the bin row cites, the citation table describes.**
  That is what stops `StudyRow`'s column set (population, `p_value_num`, `effect_size`,
  `provenance_quote`) migrating onto binning rows one column at a time.

### Reasoning

Grounding granularity was the real question — module, table, or boundary — and only the boundary
answers what was actually asked ("why 36"). Putting the *pointer* on the bin and the *bibliography* in
the citation table gets boundary granularity without restating the thresholds inside their own
evidence, which is what killed the third candidate.

### Rejected, and why

- **A generic `subject_key` on `StudyRow`** (e.g. `HTT|CAG`). Rejected on the binning tables' own rule:
  multicolumn keying, never a packed tuple. It is a second spelling of an identity the columns already
  hold, it can drift from them with nothing to catch it, and P5 gets a field carrying two axes.
- **Key columns on `StudyRow` plus a new any-of alternative, alone.** Legal, but it grounds at *table*
  granularity: a `(gene, repeat_unit)` citation still does not say why 36. Making it say so means
  putting `measure_min`/`measure_max` on the study row — restating the bin inside its own evidence.
  (The subject-relaxation half of this candidate is adopted; the "instead of a bin pointer" half is not.)
- **A `bin_evidence.csv` join table.** Keeps one-CSV-one-concern and grounds per bound, but **the join
  key is the thresholds, and they are floats**: re-authoring `40` as `40.0`, or moving a threshold,
  silently orphans its evidence with no rule able to notice. A join key that is also the data is the
  shape to avoid. It is also a new authored table — full cost.

### Same-release obligation

The enricher's literature pass and the compiler's `_cross_check_literature` **must learn the new
citation site in the same release**, or the format ships evidence it never checks — which is worse
than the honest gap it replaces. This is the reason the item was filed rather than fixed.

### Correction to the original report, preserved

`heteroplasmy.csv` is **not** affected: it has carried optional `rsid`/`chrom`/`start`/`ref`/`alts`
since 0.5.1, and `reference_examples/mt_heteroplasmy` already grounds that way. What is genuinely
unpointable is the three gene-keyed kinds — `repeat_alleles.csv`, `copynumbers.csv`,
`activity_phenotype.csv` — plus a heteroplasmy row naming only a gene. And `studies.csv` is *not*
rejected in a variants-free module; it loads and materializes today.

### Touches

`schema` (binning base gains a column; `StudyRow`'s `REQUIRED_ANY_OF` widens), `compiler`
(`_check_binning_grounding` updates, literature cross-check), `enricher` (literature pass reads the new
site).

---

## RM27 + RM46 — licensing: the source the enricher introduces, and the right it never gates

Settled together because the roadmap says they must be: per-article terms want the use-versus-
distribution axis decided.

### The problems

**RM46.** `enrich_literature` writes `source="pubmed"` into every `literature.csv` row.
`TERMS_BY_SOURCE` has no `pubmed`, and `record_source_terms` deliberately skips a name it has no terms
for. `_source_checks`'s under-declaration branch then names `pubmed` on every literature-enriched
module. **The tier introduces a source, declines to record it, and the finding lands on the author.**
Bounded severity: `SourceRow.source` is free text, so the author *can* hand-write the row — it is the
enricher asking the author to write down something only the enricher knows.

**RM27.** The licence table records three rights — sell, share-alike, redistribute. The compile gate
reads only `commercial_use`. `redistribution` is recorded and never gated, and that is a real gap
rather than a missing branch: **a distribution right is not a use.** A module can be built entirely
legitimately and still not be shippable, and `declared_use` (`unstated`/`non_commercial`/`commercial`)
cannot express that verdict.

### Decisions

- **RM27: record only.** Stamp the most-restrictive redistribution verdict into the manifest. **No gate
  in any of these four packages.** Gating at *publish* is the conceptually right place, but that step
  lives downstream in the registry — so this ships with an explicit **downstream integration ask**:
  the registry enforces it at 0.6 integration. Write the ask down; do not imply it.
- **RM46: per-article licence columns on the derived literature row.** Half cost; the pass already
  holds the licence at the exact moment it would record it (Europe PMC returns open-access status;
  Unpaywall returns a licence per DOI). `is_open_access` is already tri-state on that row.
- **Quoting a CC-BY-NC article: warn, never gate.**

### Reasoning

Gating on the act rather than on a declaration is right — it asks the author no second question at
build time about something they may not know yet — but the act happens downstream, so the honest move
is to publish the verdict and say who must act on it. A recorded-but-ungated right that *nobody is
told to enforce* is the status quo this item was filed about; a recorded right with a named enforcer
is not.

The warn-not-gate call follows the clinical-significance cross-check, which deliberately warns in both
modes because failing would make the format arbitrate a clinical dispute. Arbitrating copyright is the
same class of overreach.

### Rejected, and why

- **A `PUBMED_TERMS` constant.** The reporter's reason holds and is worth keeping: a literature
  source's terms are **per-article, not per-source**. PubMed's *metadata* is one thing; the *article*
  belongs to its publisher, and Europe PMC's open subset spans CC-BY, CC-BY-NC and bronze. One
  `pubmed` row would be right for a module citing only ids and **wrong** for one carrying a
  `provenance_quote` lifted from a CC-BY-NC article — wrong in the dangerous direction, because that
  quote is publisher text in the module's own **annotation** layer, exactly where `taints_commercial_use`
  bites. A row reading "pubmed, fine" would make such a module look cleared.
- **Stop writing `source="pubmed"`.** No: `source` is how a consumer knows which upstream answered, and
  preferring PubMed over Europe PMC (which cannot originate a row, since it silently omits ids it does
  not know) is sound.
- **Have the compiler exempt enricher-introduced sources.** No: the compiler would need a list of which
  sources a pass introduces, which is a **source convention** — forbidden it since 0.5 (P2), and the
  exact mistake RM33 removed.
- **Licensing-table rows keyed by article.** Reuses the existing gate for free, but that table is the
  one fact sidecar a human writes (full cost) and it would grow one row per cited article.
- **A second author declaration ("declared distribution") beside `declared_use`.** Symmetric with the
  existing gate, but it asks the author a build-time question about a later act.

### Touches

`schema` (literature row gains licence columns; manifest gains the redistribution verdict), `enricher`
(the literature pass records terms; `licensing` computes the verdict), `compiler` (stamps the verdict),
plus a written downstream ask for the registry.

---

## RM50 — PubMed and PubMed Central ids are one letter apart

### The problem

`StudyRow.pmid` is free-form and validated through `spec.extract_pmids`, which is `\b(\d{1,8})\b`.
Probed: `PMC3110566` → `[]` and `pmcid: PMC3110566` → `[]` (no word boundary between `C` and a digit),
but **`PMC 3110566` → `['3110566']`**. The outcome turns on a space, and when it is accepted the number
is a **real PMID for an unrelated article** — the S12 class, since these ids are densely allocated. The
rejection message says "must contain at least one PubMed ID" and never says the word PMCID: a generic
refusal where a specific one is a fix.

Separately, only PMID → PMCID is resolved (it arrives free in the esummary `articleids` block, which is
why the PMC id converter is documented as deliberately unused). That reason is true and says nothing
about **PMCID → PMID**, the direction the converter exists for. A curator holding a PMC id has no route
to the id every table keys on.

### Decision

- **The guard ships regardless — no decision, no schema change.** Refuse a digit run whose immediate
  context spells `PMC` in any spacing; **name the id that was seen** rather than the one that was
  missing; and where the record does resolve, compare the authored digits against the PMC id the same
  esummary response already carries, which catches the accepted-with-a-space case for free. Both are
  diagnosis, never repair.
- **The PMC id lives on the derived literature row only.** No authored column.
- **Build PMCID → PMID as a reporting lookup.** It reports; it never fills.

### Reasoning

The citation id is **required** today, and demoting a required field is barred within a major (P8) — so
a citation with no PubMed id cannot become legal in 0.6 whatever column we add. The authoring half
therefore genuinely belongs to 1.0, with the requiredness demotion already queued there. What *can*
close now is the practical gap: give the curator a way to obtain the id they are required to write.

The lookup must report rather than fill, because filling `pmid` would make the existence check compare
a value against the registry that produced it — the `hints.REDUNDANCY_BEARING` rule, already argued for
`doi` (Crossref is asked about the *authored* DOI, since a derived one exists by construction).

### Rejected, and why

- **An optional authored `pmcid` column now.** Additive and legal, but full cost for content the
  enricher fills free, and it still cannot help the row that has no PubMed id — which is the actual
  gap.
- **Resolve every PMCID at enrich time and store only PMIDs.** Smallest surface, and it silently drops
  the records that have none: two ways of returning nothing rendered as one sentence, which is S20
  exactly.
- **Re-key `LiteratureRow` on a general citation id.** The honest shape, and it changes what an existing
  key means — 1.0, not this.

### Touches

`schema` (`extract_pmids`' message), `enricher` (guard, PMC id on the derived row, the reverse lookup).

---

## RM48 — old-assembly coordinates, and a wrong-build diagnosis

### The problem

An author curating from older literature has hg19/GRCh37 coordinates and the module must be GRCh38.
Nothing in the four packages converts, so the conversion happens off-tool and lands as an ordinary
authored coordinate with no provenance.

### Facts established while deciding — the roadmap's stated blocker is wrong

The entry says rs-number recovery needs "either an hg19-keyed dbSNP surface or a chain file, and a
chain file is a provisioned, pinned asset with its own licence and release, i.e. the whole snapshot
apparatus for one authoring convenience". Probed 2026-08-13:

- **Ensembl runs a permanent GRCh37 REST service** at `grch37.rest.ensembl.org`, same API shape.
  `GET /overlap/region/human/7:140453130-140453140?feature=variation` returns rs-numbers with
  `alleles` and an explicit `"assembly_name":"GRCh37"`, from `"source":"dbSNP"`.
- **Reference bases for GRCh37 are free too**: `GET /sequence/region/human/7:140453135..140453137`
  returns plain text. Same coordinates give `CAC` on GRCh37 and `GTT` on GRCh38 — it discriminates
  cleanly.
- **Per-contig lengths for both assemblies** come from `/info/assembly/homo_sapiens` and are 25 numbers
  per build — small enough to ship as offline constants, the same class as `vrs.PAR_GRCh38`.

So: **no chain file, no provisioned asset, no new licence, no snapshot apparatus.**

### Decision

- **rs-number recovery only. No liftover.**
- **Live-only, skipped when offline.** Authoring-time convenience; nothing in a compile depends on it,
  and a second whole-genome variant snapshot in the old assembly is exactly the apparatus to avoid.
- **A second half: an author-time (pre-compile) wrong-build diagnosis**, hints only, reaching no
  parquet, running **only on rows that already failed the reference-base check** so the cost is
  bounded. Three hypotheses beside the existing ±1 neighbour-offset one:
  - the position lies beyond the contig's length in the declared build,
  - the contig name exists only in the other build,
  - the authored base matches the *other* assembly at this position.
- **Placement: split.** The **offline** half (impossible position, wrong-build contig name) goes in the
  **compiler**, in `validate_spec` as well as `compile_module`, per the standing rule that pure
  computation over authored bytes with no `output_dir` belongs in both. It is **provably** wrong, so it
  is an **error in both modes** — the inconsistent-reference-allele class. The **online**
  build-guessing half stays in the enricher.

### Reasoning

The reporter argued against their own request and the argument holds. If the paper gives an rs-number,
liftover is unnecessary *and strictly worse* — authoring the rs-number **produces** the independent
second value `resolution._verify` cross-examines. So liftover is only reachable where there is no
rs-number and only an old coordinate, and in exactly that case the lifted coordinate becomes the row's
**sole identity with nothing to check it against**: a generator of unverifiable-by-construction
identities, the hazard class behind the 3,038-variant off-by-one this tree already paid for. Recovery
converts an unverifiable coordinate into a verifiable one using machinery the enricher already has.

The scope-back condition set during the decision — *drop the ref-checker if it needs reference FASTA
downloads rather than free APIs* — **was assessed and does not trigger.**

### Forced consequences (not choices)

- It **reports, never fills**: filling the recovered rs-number would make resolution verify a value
  against the service that produced it.
- It returns **three** outcomes — recovered / none / ambiguous. `pyliftover` fuses the last two exactly
  as S20's `([], None)` collapse did, in this same resolution path.
- Provenance goes in `resolution.csv`'s `source` column, never into an ordinary authored coordinate.

### Corrections recorded during this round

- **The compiler does not gate authored-ref-versus-reality at all.** It errors only when two rows
  sharing a key disagree with *each other* about `ref` (internal contradiction, offline-catchable,
  fatal in both modes). Comparing an authored base against the *real* base needs the sequence, lives in
  `sequences.verify_reference_alleles`, and follows the mode ladder.
- **The ±1 neighbour mechanism is shipped, not planned.** It reads one window spanning a base either
  side and reports a shifted `start` when exactly one neighbour carries the authored `ref`.

### Touches

`compiler` (offline contig checks in `validate_spec` + `compile_module`; two offline constant tables),
`enricher` (GRCh37 REST link, recovery lookup, the build-guess hints on the existing ref-mismatch path).

---

## RM5 — symbolic / structural alleles

### Facts established while deciding

- **The nucleotide grammar bites in three places, not everywhere** — and one published claim about this
  is wrong. `alleles.py:85` and CLAUDE.md both state that `vocab.validate_allele` "has exactly one
  user, `HaplotypeRow.allele`". It has **two**: `HaplotypeRow.allele` (`pgx.py:113`) and
  `VariantRow.effect_allele` (`spec.py:576`). Plus the shared diploid-genotype validator
  `AuthoredModel._validate_genotype` (`base.py:348`), used by `VariantRow` (required) and
  `PharmVariantRow` (optional). **Fix that docstring and the CLAUDE.md bullet as part of this item.**
- `ref` / `alt` / `alts` genuinely have **no** grammar, so `alts=<DEL>` already loads today.
- `AlleleFunctionRow.allele` (`pgx.py:164`) uses `validate_haplotype_name`, not `validate_allele` — it
  is a star-allele *name*, not a sequence, and is out of scope here.

### What VCF 4.4 actually says

Spec saved at `data/input/VCFv4.4.pdf` (+ extracted `VCFv4.4.txt`), git-ignored.

- **Spelling it out is the default.** "For simple insertions and deletions in which either the REF or
  one of the ALT alleles would otherwise be null/empty, the REF and ALT Strings must include the base
  before the variant". So `A → AAAAA` is an insertion, `AAAAA → A` a deletion, and a known tandem
  duplication is spelled as an insertion.
- **Symbolic is for imprecision.** "When the exact sequence is known, the variant can be represented as
  a non-symbolic ALT allele… When the exact sequence is not known, or when reporting tandem repeat
  'summary' information, the variant can be represented as `<CNV:TR>`."
- **First-level types are a closed five**: `DEL`, `INS`, `DUP`, `INV`, `CNV`. Subtypes are
  colon-separated, "implementations are free to define their own"; recommended: `CNV:TR`,
  `DUP:TANDEM`, `DEL:ME`, `INS:ME`. "The CNV symbolic allele should not be used when a more specific
  one can be applied."
- **Obligations**: the padding base becomes required, POS is the base *immediately preceding* the
  variant, and "SVLEN must be specified for symbolic structural variant alleles".
- Arbitrary named alleles are legal in VCF **only** via a declared `##ALT=<ID=…,Description="…">`
  header line — whose own worked example in the spec is IUPAC codes
  (`##ALT=<ID=R,Description="IUPAC code R = A/G">`).
- `<*>` is the unspecified allele (preferred over `<NON_REF>`); ALT may also be `*` (missing due to an
  overlapping deletion). Contig names must not collide with reserved symbolic names.

### Decision

- **The five closed first-level structural types (plus subtypes), and nothing else.** No `##ALT`-style
  declaration mechanism, no arbitrary named IDs, no readable aliases for spellable alleles.
- **A symbolic allele with no length: discard the row with a warning under `best_effort`, hard-fail
  under `strict`.**
- Consequently **5-HTTLPR is authored as a plain indel** (its ~43 bp sequence is known, so the standard
  says spell it), and **CPIC's IUPAC codes stay unexpressible** — both deliberately.

### Reasoning

The declaration mechanism would have dissolved the open-vs-closed trade neatly and it is what the
standard offers, but it is **unasked extendability**: bloat, complexity, fragility and churn nobody
benefits from, in the one layer where a human has to read the result. Ideas of that kind stay gated
behind a real consumer report. The five types are the part of the standard a consumer can act on
without reading a module's prose; everything above them is optional and therefore not earned.

On the length: a module is a **declarative rulebook**, and an unusable rule is worthless — a `<DEL>`
with no length cannot be matched to a call, sized, or told apart from another deletion. Discarding it
keeps the module honest; refusing under strict keeps a reproducible artifact complete.

### Rejected, and why

- **VCF-faithful with mandatory declarations.** See above — right by the standard, wrong for this DSL.
- **One open token with no closed set.** Uniform and simple, and it drops the only piece a consumer can
  act on.
- **A named alias carrying its own sequence** (so `L/S` is authorable and the machine still has the
  bases). Tempting, since it satisfies both halves of the human-authorable/machine-precise duality —
  rejected as the same unasked extendability, and it creates two spellings of one allele that the
  comparison and identity paths would both have to resolve.

### Forced consequences (not choices)

- A symbolic allele mints **no** content-addressed identity — no sequence to digest, so it falls
  through to the coordinate key, as indels already do.
- Comparing a symbolic allele against a spelled one returns **undecided**, never "no match"
  (`hosting_verdict`'s tri-state; a symbolic allele has no flank for `parsimony_reduce`).
- The enricher **normalises a source's spelling at the boundary** (the `CC` → `C/C` precedent), rather
  than the schema accepting every dialect.
- ⚠ **Discarding an authored row is new behaviour in this codebase.** It does not break P7 — the
  round-trip fixed point is only claimed under `strict`, where this case refuses — but `reverse` will
  not re-emit a discarded row, so the warning must say the row was **dropped**, not merely flagged.

### Touches

`schema` (`_validate_genotype`, `validate_allele`, the wrong docstring at `alleles.py:85`),
`compiler` (the discard/refuse ladder), `enricher` (boundary normalisation for ClinPGx `del`),
CLAUDE.md (the "exactly one user" bullet).

---

## RM4 — gene-panel materialization, and the authored glue it takes with it

### Decision

- **Compile-time materialization is dead.** Wrong surface.
- **The mechanism is enricher draft-scaffolding**, which already ships: a panel call auto-drafts the
  rows, and **the author's no-op over the drafted subset is still an authorial act**. Pipeline
  unchanged, want satisfied.
- **`panel:` loses its last consumer and is deprecated.** Drafting stamps the ClinVar release into the
  licence row's `dataset` column (`sources.py:175`, *"Which release the data came from"*, currently
  left empty by `clinvar_draft`'s `merge_sources_file` call), and `clinical.tautology_reason` keys on
  **that** instead of on the authored block.
- **`panel:` stays in the schema until 1.0 with a compiler deprecation warning**, then is removed. It
  owes a 1.0-cleanup tracker line.
- **The hand-edit hole closes on a mode ladder:**
  - **`strict`** — look up every row and report three buckets: copied-from-source (tautological),
    genuinely authored, conflicting. Full cost, never a meaningless zero.
  - **`best_effort`** — keep the cheap module-level skip, **plus a notice naming the hole**.
- **Unrelated surface bug found while checking, fix it here:** `draft_gene_panel` has a `download`
  parameter the CLI never exposes. **CLI and API surfaces must match** — a flag-driven CLI is fine, the
  API just has to have the same shape.

### Reasoning

The compiler must not create rows no curator wrote. That is the same objection that bars filling
`direction` from `state`, and it does not depend on the digest. Expansion at compile time would also
make a module's content depend on an external file and force `reverse` to choose between re-emitting
the declaration (rows lost) or the rows (declaration lost) — neither a fixed point. Routing through
drafting removes all of it: the rows are authored bytes before the compiler ever sees them.

On the glue: **the enricher should alleviate labour, not impose `panel:` bureaucracy.** The draft was
machined, so the tautology marker should be machined too. The provenance the check needs already has a
machine-written home that is sitting empty.

### What the tautology check is, for anyone reading this cold

`clinical.tautology_reason` (0.5.2). A module drafted by `clinvar_draft` copied its `clin_sig` **out of
the snapshot the cross-check reads**, so the comparison is a value against itself: necessarily zero
conflicts, at 90% of the resolve time (measured: 27.1 s → 2.6 s on a 7,818-row panel, byte-identical
output). Reporting "0 conflicts" there looks like evidence and is not. The skip requires an
**established** match — every unknown leaves the check running.

### Rejected, and why

- **Keep the authored `panel:` declaration** because author-states/snapshot-confirms is two independent
  statements. Real, but the claim being established is *provenance* ("these rows came from this
  snapshot"), and the tool that copied them is the authority on that — it is not a Class-2 redundancy
  claim.
- **Auto-remove `panel:` on reverse.** Considered explicitly, and it is **not available at zero cost**:
  dropping it from reverse's output changes `module_spec.yaml`'s bytes and breaks the round-trip fixed
  point for any module carrying it. Deprecation warning plus documentation is the route.
- **Per-row skip in both modes.** As stated it re-costs the 90% saving: deciding per row whether a value
  still matches the snapshot *requires* the lookup. Hence the ladder.
- **Record per-row draft provenance** in a derived sidecar so hand-edits are detectable offline and free.
  Keeps both properties, and was rejected as surface for a case `strict` already answers.

### Touches

`enricher` (`clinvar_draft` stamps `dataset`; `clinical.tautology_reason` re-keys; the mode ladder; the
CLI `download` parameter), `compiler` (the `panel:` deprecation warning), the 1.0 cleanup tracker.

---

## RM24 — gene–disease validity as a derived table

### Decision — **build it**

One row per `(gene, disease term, classification, source, release)`, serving **ClinGen** gene–disease
validity, **GenCC** aggregate validity and **HPO** gene→phenotype from one shape.

- **Machine-written by an enricher pass → a derived fact sidecar, half cost.** This is what changed the
  answer: the roadmap files it as a schema design problem, and most of that cost evaporates once no
  author has to learn the shape.
- The three submitters' vocabularies map onto **one closed set at the enricher boundary** — the
  dosage-sensitivity precedent: builders store verbatim, readers map, so a mapping fix reaches an
  already-built snapshot.
- **New `gene_validity` member in `VALID_SOURCE_LAYERS`** (`vocab.py:216`, currently
  `{resolution, frequency, gene_metrics, literature, annotation}`). **Fact-class, non-tainting** — a
  ClinGen verdict is a value it publishes identically to everyone, the same standing as a gnomAD
  frequency, and only the annotation layer taints. Widening a vocabulary is legal.
- A table rather than columns because the grain is **gene × term**, not gene — which is exactly why
  dosage sensitivity went the other way and became a column on `gene_metrics`.

All three sources are free, so a module using it stays sellable — unlike RM23.

### Touches

`schema` (`GeneValidityRow`, the layer vocabulary, `reference._ALL_MODELS`), `compiler`
(`_FACT_TABLES` gains an entry; `_DERIVED_FILES` follows automatically since it is derived from
`_FACT_TABLES`), `enricher` (the pass, the vocabulary mapping, `record_source_terms`).

---

## RM25 — ClinVar assertion tier as a derived table

### Decision — **build it**

One row per variant carrying the clinical call, the review status, the star rating and ClinVar's own
stable record id. Derived sidecar, half cost.

### Reasoning

The deciding argument is the house one, now applied a fourth time: **a number this workspace computes
and then discards gets recomputed by every consumer, and a recomputation is a place to drift.**
`clinical.ClinSigFinding` already reports both fields via its `confidence` property, and
`draft_gene_panel` uses the star rating as a *filter* (default 2 — multiple submitters, no conflicts)
and throws it away. A one-star single submission and a practice guideline are not the same claim, and
today a compiled module flattens both to the same `clin_sig`.

Do **not** confuse this with escalating the cross-check's severity — that stays parked, deliberately.

### Rejected, and why

- **Columns on an existing derived table.** Cheaper in file count, and it puts clinical assertion data
  on a table about something else — the one-CSV-one-concern rule.
- **A column on `VariantRow`.** Full cost, and it is a source's fact rather than the author's claim.

### Touches

Same surfaces as RM24. These two are the same mechanics twice and should be one work item.

---

# The VCF 4.4 cluster — RM53 to RM67

**Where these came from.** [VCF_4_4_AUDIT.md](../probes/VCF_4_4_AUDIT.md) is a full read of the VCFv4.4/BCFv2.2
specification (`hts-specs` c101c79) against `just_dna_format`, done 2026-08-13. It produced fourteen
findings, **none of them `RMn`-tracked**, all minor-legal. They were numbered and triaged in the same
session as the sixteen items above; the audit remains the evidence document and is not duplicated here
— it carries the spec quotations, the `file:line` references and the probe transcripts.

**Why they are in 0.6 rather than deferred wholesale.** The format holds no sample data, so VCF is
neither an input nor an output — but it is **the only artifact a consumer actually queries**, and four
authored columns point directly into it. Wherever those columns touch the spec, the spec *is* the
contract, and a mismatch is a silently wrong answer at query time rather than a compile failure.

**The through-line, worth stating once:** three of the four highest-consequence findings are one mistake
in three places — **the schema names a VCF field by a bare token, and a VCF field is not identified by
its name.** It is identified by *namespace* (INFO or FORMAT, two tables that collide on `DP`, `AD`,
`ADF`, `ADR`, `MQ` and, new in 4.4, `CN`) and by *cardinality* (`Number=1|A|R|G|P|.`, which decides how
many values come back and what each is *of*). Where both readings are type-compatible — and for `DP`,
`AF` and `CN` they are — nothing detects the confusion: the consumer reads a well-formed number of the
wrong kind and bins it without error.

---

## RM53 — a bare field name means two different VCF fields

**Severity high — silent wrong answer at query time, on both shipped reference examples.**

`source_field`, `callable_from` and `quality_from` all validate through one grammar that accepts a bare
token. `mt_heteroplasmy` writes `source_field=AF` meaning **FORMAT/AF** (this person's heteroplasmy
fraction); `AF` as the spec reserves it is **INFO/AF** (the cohort frequency of that ALT). Both are
floats in `[0,1]`, both bin cleanly against the module's thresholds, and one of them tells a carrier
they are asymptomatic on the strength of how rare the variant is in a reference panel. Its
`callable_from=DP` is the same error one column over.

### Decision

**Accept the qualified form in the pointer itself** (`INFO/DP`, `FORMAT/DP`), bare name still legal and
still meaning *unqualified*, **and warn whenever a bare name is one of the known collisions**
(`DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF`, `CN`). Widening only, so nothing published breaks.

### Reasoning

Reading `INFO/DP` is how a VCF user already writes it, and one grammar change reaches all three columns
where three companion columns would be three authored columns. The audit's objection to the qualified
form — that it makes the unqualified spelling look like a deliberate choice — is answered by the
warning, whose collision set is **fixed and spec-derived**, not curated data, so it is not the source
convention P2 forbids.

### Rejected, and why

- **A separate namespace column per pointer.** Three optional authored columns for what a slash
  expresses; full cost under the layer rule for no added expressiveness.
- **Default the namespace per column** (`callable_from` ⇒ FORMAT, `source_field` ⇒ INFO). The
  `None`-is-not-`False` mistake: it converts *unstated* into a *stated* answer, and it would be wrong
  for `mt_heteroplasmy` on the very first module.
- **Read the consumer's VCF header to decide.** A source convention inside the format tier (P2, the
  RM33 mistake), and undecidable anyway when both namespaces declare the key.

### Consequences

The two shipped reference examples are **wrong today** and must be re-authored to the qualified form.
Their `content_signature` and `artifact.digest` move; that is a correction, not a regression, and the
round-trip fixed point must be re-verified rather than assumed.

`ROADMAP.md:1042`'s claim that `(INFO/RU, FORMAT/REPCN)` is "consumable with zero glue" is written with
the namespace attached and is falsified by the current schema — the prose knew something the data model
did not. Fix it when the entry is next touched.

---

## RM54 — a pointer at a multi-valued field cannot say which value

**Severity high — silent wrong answer. Same column set as RM53, one design round with it.**

`Number` is part of a VCF field's definition: `A` is one value per ALT, `R` one per allele **reference
first**, `G` one per genotype, `.` unbounded. So a pointer at `AD` returns *n+1* integers of which none
is the answer. It bites hardest where it matters most: `repeat_alleles.csv` is about **dominant**
disorders, the clinical rule for HTT is *the larger of the two alleles*, and
`reference_examples/htt_repeat_expansion` states four thresholds under `--strict` pointing at `REPCN`
with nowhere to say "larger". A consumer that averages, takes the first, or takes the reference allele
gets a well-formed number and a wrong answer with every offline gate passing — the same failure geometry
as the 3,038-row coordinate incident.

### Decision

**A closed vocabulary of selection rules** — larger / smaller / the called alternate / the sum / the
reference element — applied by the consumer. Fixed once for all pointer columns.

**Write the reference-inclusion trap into the vocabulary itself:** on a `Number=R` field the reference
is the first element, so "larger" must state whether it counts. A rule that is silent about this is the
same defect one level down.

### Rejected, and why

- **An index** (`AD[1]`, `REPCN[max]`). The beginning of an expression grammar — what Principle 1
  refuses, and the reason these pointers were a bare token in the first place. A named rule set is
  data, terminates, and needs no evaluator.
- **Document the ambiguity and change nothing.** Leaves the flagship example pointing at a field whose
  reading decides the answer.

---

## RM55 — copy number and repeat count are not whole numbers, and the schema says they are

**Severity high — a measure kind is unauthorable for its own source data. 0.6 warns; the fix is 1.0.**

§7.2, verbatim: *"Redefined INFO and FORMAT CN to support non-integer copy numbers."* The worked
examples are fractional throughout (`CN=3,0.9666`, `CN=1.25`), and §5.6 says granularity is deliberately
undefined and may be *"at a highly granular megabase level of resolution"* — a segment mean, continuous
by construction. Repeat count has the same defect: §3 standardises `RUC` as a **Float**.

Both sit in `_INTEGER_KINDS`. Probed against the real `validate_bins`:

```
integer bins [0,0] [1,1] [2,2] [3,∞)   →  OK, warnings=[]   ← a CN of 2.4 matches NO bin, silently
dense bins   [0,1] [1,2] [2,3]         →  ValueError: overlapping bins
workaround   [0,0.999] [1,1.999]       →  OK, warnings=[]   ← arbitrary; (0.999,1) uncovered, unwarned
```

That is RM35's unsatisfiable triangle re-instantiated on the kind RM35 exempted — and **worse**, because
on an integer kind a hole of exactly 1 is not reported at all: the module compiles green under
`--strict` and a fractional measurement selects nothing.

### Decision — a three-release route, and 0.6 only warns

- **0.6: a loud compiler warning and nothing else.** The columns stay exactly as they are.
- **0.7: the additive, charter-clean half** — a parallel float column beside the integer one, with the
  integer column deprecated. Filed in [ROADMAP_0_7.md](../ROADMAP_0_7.md) as RM55 with this shape as the
  suggested fix.
- **1.0: the removal**, which is the only genuinely major part.

It covers **both** kinds. They were placed in the integer set on one premise and the spec withdrew it
for both; fixing one and leaving the other means the next reader has to rediscover why they differ.

### Reasoning

The honest description is that **the implementation landed prematurely and is wrong**, not that the
format is missing a feature. But the correction is a **retype** (`CopyNumberRow.modifier_cn: int` →
float) plus a change to what published bin tilings *mean*, and the charter reserves retyping for a
major. There are no published copy-number modules to break — and taking the shortcut anyway is
precisely the cost of holding a semi-immutable schema.

So the defect is made **loud** immediately, the **usable** fix arrives one minor later by the additive
route the charter already permits, and only the removal waits for the major. An author is never left
without a way to write a fractional dosage for longer than one minor, and no published table is
retyped under anyone.

### Rejected, and why

- **Move the kinds into the continuous set in 0.6.** One line, and it silently retypes every existing
  table: `[2,2]` beside `[3,3]` is a legal integer tiling today, and under continuous rules the
  shared-endpoint rule and the gap warning both change meaning. It also answers the wrong question —
  the two kind-sets separately answer *"can a hole be arbitrarily small?"* and *"can two bins touch?"*,
  and a rounded catalog count and a continuous segment mean genuinely differ on both.
- **Wait for 1.0 with the whole thing.** Leaves a measure kind unauthorable for its own source data
  across the rest of the 0.x line, with the silent no-match still present under `--strict`.
- **A per-table quantised declaration, or a sixth measure kind.** Both were live candidates, and both
  *add around* an implementation that is simply incorrect. Reconsider them in 0.7 when the parallel
  column is designed — the question of whether quantised-versus-continuous is a table property or a
  kind is still open, and the parallel column does not foreclose it.

---

## RM56 — a measurement can span several bins, and there is no state for that

**Severity high on the flagship example. 0.6 ships an honest placeholder; the policy waits for real
caller output.**

The repeat count VCF standardises travels with a confidence interval, and the spec is explicit that the
upper bound may be **unbounded** (§3: *"a reasonable limit of total length of the repeat could not be
determined"*). §5.7's canonical CAG form is `RUS=CAG;RUC=65;CIRUC=-15,.` — meaning ≥50, most likely 65.
§5.7 states why: *"Many of these techniques result in imprecise variant calls."* Imprecision is the
normal case.

`reference_examples/htt_repeat_expansion` has thresholds at 26/27, 35/36 and 39/40 — three inside a
14-count window. A real call of `RUC=38, CIRUC=-5,5` spans `[33,43]` and crosses all three, so the
module says *benign*, *uncertain* and *fully penetrant*, and there is no honest answer among them. The
consumer contract has exactly three states — a bin matched, no bin matched, or the measurement absent —
and none of them is "the measurement spans bins".

### Decision

- **0.6: a loud, explicitly-not-implemented warning, and withhold as the stated placeholder behaviour.**
- **The policy vocabulary** — withhold / take the worst bin / take the point estimate — **lands when a
  real caller VCF arrives**, together with the rest of the repeat work.
- **Its grain (per table or per row) is deliberately undefined for now.**

### Reasoning

The tempting move was to defer entirely on the same "no real VCF, so it is scaffolding in thin air"
argument that parked RM65 and RM66. What stops that is that we are already one leg in with RM55: the
neighbouring defect is being made loud rather than silent in 0.6, and leaving this one silent would be
inconsistent within the same table. Withholding is also the house default — an unknown is withheld,
never reported and never negated — so the placeholder behaviour is not a guess.

**Widening the measurement into an interval is not available and must not be re-proposed:** it puts a
*measurement* in the module, which the data-agnostic north star forbids outright. What belongs here is
the **rule** for an interval spanning bins, which is annotation.

---

## RM57 — a quality floor inverts on exactly the records it exists for

**Severity medium-high — narrow, but the failure is a confident wrong answer. 0.6, docs + warning.**

§1.6.1.6: QUAL is *"−10log10 prob(variant)"* when ALT is `.`, and *"−10log10 prob(no variant)"*
otherwise. **The sign of the assertion flips with the record.** A QUAL of 60 on a variant record means
the variant is almost certainly real; on a monomorphic record it means the position is almost certainly
*variant* — the opposite of a clean reference call.

`quality_from` recommends `QUAL` and `min_quality` is an inclusive floor. The collision is with
`requires_callable`, the flag for rows where **the absence of the variant is the informative call** — a
consumer evaluating one reads the *reference* record, which is exactly where QUAL is inverted. So
`requires_callable=true, quality_from=QUAL, min_quality=30` asks the consumer to *require* evidence that
the position is variant before asserting that it is not, and the higher the floor the more confidently
wrong the result.

**Second half:** reference evidence is a *block* (`END=4383`), so callability is found by **interval
containment**, not an equality join on position, and the right depth field is `MIN_DP` (the block floor)
rather than `DP` (the block average) — a DP of 25 over a 14 bp block is compatible with an uncovered
base inside it. Nothing says either thing, and `callable_from=DP` is what the shipped example writes.

### Decision

Documentation and a warning naming the inversion, plus guidance that a block wants `MIN_DP` and interval
containment. No validator.

### Rejected, and why

**Refusing `QUAL` on a `requires_callable` row** encodes one reading of a field whose meaning depends on
a record the compiler will never see, and it would refuse the legitimate combination (such a row on a
variant record elsewhere in the same file).

---

## RM58 — `alts = "."` splits identity

**Severity medium-high. The only VCF finding that reaches identity. 0.6, a diagnosis.**

`.` is VCF's MISSING marker meaning *there are no alternate alleles* — a monomorphic reference record,
which the spec's own first example carries. We read it as a literal allele and fold it into
`variant_key`, so a module writing `alts=.` and one leaving the cell empty describe the same site under
two different keys (`1:1:A:.` versus `1:1:A`), with different `content_signature`s, no dedup between
them and no diagnostic anywhere.

### Decision

A **diagnosis, not a grammar**: `.` is not an allele, and `alleles.non_nucleotide_reason` is the existing
place to say so. It currently files `.` under `"notation"` alongside `<DEL>`, **conflating the MISSING
marker with a symbolic allele** — the same two-reasons-under-one-message mistake
`cpic.unusable_allele_reason` had to unwind. Separate them.

### Rejected, and why

**Adding `^[ACGT]+$` to `alts`** is the repair `alleles.py:84` already refuses: it tightens the field RM5
exists to widen and breaks P3. Still refused.

---

## RM59 — the allele that could not be observed

**Severity medium-high. Decided beside RM5, deliberately not inside it. 0.6.**

`*` in ALT means *this sample's allele could not be observed here, because a deletion called elsewhere
overlaps this position*. It is what any modern joint-called VCF puts at such a site, so `GT=0/2` with
`ALT=A,*` is ordinary consumer data. Today `alts='*'` loads (that column has no grammar) but
`genotype='A/*'` is rejected, so no row can be written for it — and a consumer that drops the `*` reads
the call as reference-like and takes the reference conclusion. **That is exactly the
no-call-is-not-homozygous-reference error `requires_callable` was built to prevent, arriving through a
spelling instead of through a missing record.**

### Decision

**Both halves.** The genotype grammar admits `*`, **and** the consumer contract states the withhold rule
for a `*` met in a module that says nothing about it.

### Reasoning

`*` is **not** RM5's axis and must not be folded into it: RM5 covers symbolic and structural alleles,
all of which name a *variant* whose sequence the grammar cannot spell. `*` names no variant — it makes
an **observability** claim, which is the callability axis. The two would otherwise share a syntax and
mean different things, which is why the audit insisted this be decided *against* RM5 rather than inside
it. Since RM5 is being built in this same batch, deciding it now avoids touching the genotype grammar
twice.

---

## RM60 — `chrom` rejects `chrM`

**Severity medium — pure authoring friction, but it rejects the spelling most human pipelines use. 0.6.**

Real GRCh38 files split on the mitochondrion: Ensembl-style writes `MT`, the analysis set most pipelines
actually align against (hs38DH) writes `chrM`. Probed: `MT` and `chrMT` pass; **`chrM` and `M` are
rejected**. Meanwhile `vrs.normalize_chrom`, in the same package, folds `M`/`chrM` → `MT`. Two
normalizers, different tolerance, and the stricter one is the gate an author hits — with a message that
lists `MT` and never mentions that `chrM` is the same contig.

### Decision

Route `_validate_chrom` through `normalize_chrom`. **Widens only** — every value that validates today
still validates and normalizes to the same member — so it is P3-clean. Alt contigs, scaffolds, patches
and decoys stay rejected, correctly and by charter.

This is the same class as the 0.6 `-`-for-`_` vocabulary tolerance: the surface an author learns the
vocabulary from taught a spelling the file rejected.

---

## RM61 — the pointer grammar rejects VCF-legal field names

**Severity low. 0.6, widening only.**

An INFO key matches `^([A-Za-z_][0-9A-Za-z_.]*|1000G)$` — so a dot is legal inside a key, and `1000G` is
a legal key beginning with a digit, reserved explicitly by the spec. `SOURCE_FIELD_PATTERN` allows
neither; probed, `1000G` and `gnomAD.AF` are both refused. A grammar claiming to describe VCF field names
while refusing two shapes the spec names by hand. Strictly widening.

---

## RM62 — 32-bit values against 64-bit bounds

**Severity low. 0.6, consumer contract only.**

Every number a consumer reads out of a VCF is float32; every bound and floor here is float64. Widening is
exact but not value-preserving relative to the decimal an author typed: a VCF `0.1` widens to
`0.100000001490116…`, which is **above** an authored `0.1`.

Harmless for a lower bound (it lands inside the bin, and the higher bin owns a shared endpoint). **Not
harmless for an inclusive upper bound**: any non-dyadic closed bound — `0.1`, `0.3`, the
`mt_heteroplasmy` boundaries — can be missed by a value that reads as equal in the source file. Same for
`min_quality` against a float32 QUAL.

**Decision: state a tolerance rule in the consumer contract, change no schema.** The schema is right to
keep decimal bounds — the DSL exists for the human. Recorded because nothing states it today, and a
lookup rule that is exact in one direction and not the other is the kind of thing found in production.

---

## RM63 — a pipe-separated genotype names no homolog

**Severity low. 0.6, documentation.**

VCF defines allele order only **within a phase set**; there is no global "first homolog", and §1.6.2 is
explicit that PSL exists because with PS a genotype *"isn't connected to any specific haplotype"*. Our
grammar accepts `A|G` as order-significant and the docstring says *"phase encodes which allele sits on
which homolog"*. With no phase-set column, an authored `A|G` and `G|A` are distinguishable to us and
indistinguishable to any consumer, and two rows both written `A|G` assert nothing about being in cis.

Not a live defect — the cis/trans case is carried properly by `DiplotypeRow` and the phase-ambiguity
check — but the docstring claims more than the format supports, and `flags: phased` invites an author to
lean on it. **Correct the docstring**; state that a pipe in a `variants.csv` genotype means "heterozygous,
phase recorded but unaddressable".

---

## RM64 — the VCF id column is a list

**Severity low. 0.6, documentation.**

§1.6.1.3: ID is a *"semicolon-separated list of unique identifiers"*, so a real record may carry
`rs123;rs456`. `validate_rsid` takes exactly one — correct for the authored side, since a row should name
one variant — but a consumer joining on the VCF ID column has to split first, and nothing says so.

---

## RM65 — repeat and copy-number tables are positional, and the code says they are not

**0.6 corrects the false claim. The implementation is 0.7+, gated on real caller output.**

`compiler.py:825` states that beyond the three positional kinds *"the rest are gene- or score-keyed and
are not joinable by position at all, **which is a property of what they describe rather than a gap**"*.
True of `allele_function.csv` and `pgs.csv`. **False of `repeat_alleles.csv` and `copynumbers.csv`**: §5.6
says POS and SVLEN specify the interval a copy number is defined over, and §5.7 says a `<CNV:TR>`
record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based callers"*. A
tandem repeat and a copy-number segment are **loci with coordinates**, emitted at fixed published
positions. So their non-joinability is a **gap in the schema**, not a property of the thing described —
the distinction RM43 drew carefully for the other three tables, applied one table further.

### Decision

- **0.6: correct the comment.** A claim the spec contradicts is a defect in its own right.
- **The coordinates themselves wait for 0.7+**, gated on a real repeat-caller VCF sample or a consumer
  field report. Building the joinability without one is scaffolding in thin air.

**This keeps the coordinate-filling lane (RM43) at three tables.** If it were taken now it would be five.

---

## RM66 — one repeat locus, several motifs

**Deferred to 0.7 with RM65, same prerequisite.**

§5.7: a `<CNV:TR>` allele *"consists of one or more repeat sequences"* and *"can encode multiple different
repeat motifs in a single allele"* (`RN=3`, `RUS=CAG,TG,CAGG`). `RepeatAlleleRow` is keyed
`(gene, repeat_unit)` and binds one count to one motif. For HTT the interruption structure
`(CAG)n(CAA)(CAG)` is exactly what a caller now reports as several `RUS` entries, and the pure-CAG tract
length differs from the total — a difference with published effect on age of onset. The key cannot say
which count the bins are about, and two motifs for one gene read as two unrelated groups rather than
components of one allele.

The audit's own judgement is that this is separate and larger and should not be bundled with RM56, and it
has RM65's prerequisite. Filed beside it so both arrive with the same evidence.

---

## RM67 — polyploid and partially-phased genotypes

**Not work. Numbered so it is findable and not re-probed.**

§7.2 added polyploid partial phasing (`GT |0|0/1/2`), with the first phasing indicator optional. Our
grammar caps at two alleles and refuses a leading separator (probed: `A/A/G` and `A|G/T` both rejected).

This is a **defensible generalization** — the format annotates human diploid loci, and
`_check_contig_ploidy` handles the hemizygous and haploid directions — but it is now a **documented
divergence from the spec** rather than an unexamined default. No change proposed. The spec's own polyploid
example is a tandem duplication with SNVs on it, which a CNV-aware consumer will meet, so revisit if one
does.

---

## Checked and clean — do not re-probe

Recorded from the audit so these are not re-examined: position-1 padding (handled, right-trim-first, and
the docstring says so); telomeric POS 0 (loads, and no VRS id is minted for a position that does not
exist); no content-addressed id is minted for a non-nucleotide ALT, so RM58 is a key-*string* problem and
not a false digest claim; `_check_contig_ploidy` against the pseudoautosomal regions.

**One finding strengthens an existing decision.** CLAUDE.md records that IUPAC codes appear in neither REF
nor ALT across 4,439,382 ClinVar rows, offered as an empirical fact. §1.6.1.4 makes it **structural**:
*"the ambiguous reference base must be reduced to a concrete base by using the one that is first
alphabetically."* The probe was not a lucky sample — the spec mandates the reduction. Two things follow:
an authored `ref=A` may be a **lossily reduced `R`**, so a single-base ref disagreement is not necessarily
a coordinate error (relevant to RM48's diagnosis); and the sanctioned way to express what CPIC's `R` means
is a declared symbolic ALT, which is squarely RM5's axis and strengthens the decision to file it there
rather than widen the nucleotide grammar.

---

# Everything not built here

Deferred and closed items are **not** in this document — they were moved to the roadmap of the release
that will decide them, so this file stays a record of what 0.6 builds and why:

- **[ROADMAP_0_7.md](../ROADMAP_0_7.md)** — RM23 (predictor scores), RM16 (authored PRS weights), RM28
  (the meta-conclusion predicate; its cofactor half closed here).
- **[ROADMAP_1_0.md](../ROADMAP_1_0.md)** — RM15 (multi-build identity), RM52 (the upgrade procedure).
- **RM10** closed as an item — folded into RM28; see ROADMAP_0_7.
- **RM7** was never format scope.

# Implementation plan

## Ordering

**Phase 0 — serial, alone.** The charter amendment. Nothing else in the same commit.

**Phase 1 — parallel, eight lanes.**

**Phase 2 — serial, after their blockers.** Lane G needs A; lane B' needs B.

**Phase 3 — serial.** Documentation reconciliation (see the conflict map).

## Lanes

| Lane | Items | Packages | Notes |
|---|---|---|---|
| **A** | RM43 | schema + compiler | Largest. Touches the compile core and reverse. Blocks G. Stays at **three** positional tables — RM65 deliberately does not add two more. |
| **B** | RM5 | schema + compiler + enricher | The five closed structural types. Also fixes the wrong `validate_allele` docstring (it has two users, not one). Blocks B'. |
| **B'** | RM59 | schema + compiler | The unobservable allele. **After B** — both touch the genotype grammar, and the whole point is that the two spellings must not be conflated. Small. |
| **C** | RM48 | compiler + enricher | Cleanly split offline/online; no shared models. |
| **D** | RM4 | enricher (+ one compiler warning) | Enricher-heavy. Also the CLI/API `download` fix. |
| **E** | RM24 + RM25 | schema + compiler + enricher | Two derived sidecars, same mechanics twice. One agent. |
| **F** | RM46 + RM50 + RM47 | schema + compiler + enricher | **Must be one lane** — see below. |
| **G** | RM45 + RM27 | schema + compiler + enricher | After A. Both are manifest work. |
| **H** | RM53 + RM54 + RM61 | schema + compiler | The VCF-pointer design round: namespace qualifier, selection-rule vocabulary, and the grammar widening that shares the same pattern. One round by decision. **Re-authors two reference examples.** |
| **I** | RM55 + RM56 + RM57 + RM58 + RM60 + RM62 + RM63 + RM64 + RM65 | schema + compiler | The warnings-diagnostics-and-docs lane. Individually too small to be lanes; all touch validation messages and the consumer contract. No schema change except RM60's widening. |

## Why F is one lane and not three

RM46 and RM50 **both add columns to `LiteratureRow`**, and RM47 **wires the literature pass and
`_cross_check_literature`** to a new citation site. Three agents would collide on the same model, the
same pass and the same cross-check. RM47's binning-column half is separable in principle but its
same-release obligation is precisely the literature wiring, so splitting it buys nothing.

## Why I is one lane and not nine

Every member is a warning, a diagnosis, a docstring or a message. None changes a verdict except RM60,
which widens only. They collide on the same handful of validators and on the consumer-contract prose,
and nine agents each opening `binning.py` and `spec.py` to add one message would spend more effort
merging than writing. RM65's half here is a **comment correction**, nothing more.

Two members of this lane need saying explicitly to whoever runs it, because both look like bigger jobs
than they are: **RM55 in 0.6 is a warning only** — no retype, no kind move, the fix is 0.7 — and
**RM56 in 0.6 is a warning plus withhold-as-stated-behaviour**, with the policy vocabulary deferred.
Anyone who "finishes the job" on either has broken the charter or guessed at a vocabulary.

## Shared-file hazards

Every lane that adds a model or a vocabulary member touches the same few files. Flag these to each
agent as **append-only, expect a merge**:

- `schema/src/just_dna_format/vocab.py` — B (allele grammar), B' (genotype), E
  (`VALID_SOURCE_LAYERS`), G (two new vocabularies), H (`SOURCE_FIELD_PATTERN` + the selection-rule
  vocabulary). **The busiest file in the batch.**
- `schema/src/just_dna_format/reference.py` `_ALL_MODELS` — E, F, G. **A model missing from this list
  silently defeats the vocabulary guard test** (S21); adding to it is not optional.
- `compiler/src/just_dna_compiler/compiler.py` — `_TABLE_KINDS` (154), `_FACT_TABLES` (224),
  `_INPUT_FILES` (197), `_OUTPUT_FILES` (203), and the `_POSITIONAL_TABLE_KINDS` comment at 825
  (lane I corrects it, lane A reads it). A, E, F, G, I all edit this file in different places.
- `schema/src/just_dna_format/manifest.py` — `Compilation` and the new blocks: G, and A for the
  resolution-signature half.
- `schema/src/just_dna_format/base.py` — B and B' (`_validate_genotype`, sequentially, not
  concurrently), A (`authored_field_names` must keep covering the new stamped fields).
- `schema/src/just_dna_format/binning.py` — H (the pointer columns' descriptions), I (RM55/RM56
  warnings), F (RM47's citation pointer on the binning base). Three lanes, three different concerns,
  one file.
- `schema/src/just_dna_format/spec.py` — B (`effect_allele`), H (`callable_from`/`quality_from`),
  I (RM57's `min_quality` guidance, RM60's `_validate_chrom`, RM63's docstring), F (`StudyRow`'s
  widened any-of).
- **`reference_examples/`** — H re-authors `mt_heteroplasmy` (both its pointer columns are wrong today)
  and touches `htt_repeat_expansion`. Expect those two examples' signatures to move, deliberately. Any
  lane asserting "all eleven examples keep their digests" must exclude these two and say why.

## Documentation

Every lane wants to edit `docs/SCHEMAS.md`, `docs/COMPILER.md`, `docs/ENRICHER.md`, `docs/ROADMAP.md`,
`docs/RM_TOC.md` and `docs/CHANGELOG.md`. Either assign strict section ownership per lane, or have each
lane write its docs into its own commit and run a **serial reconciliation pass** in phase 3. The
reconciliation pass also moves shipped items from ROADMAP to ROADMAP_HISTORY and updates RM_TOC — which
is a single-writer job by nature.

## Standing requirements for every lane

- **Read the Constitution first-hand** before judging whether a change is legal. Do not delegate that
  to a subagent, and do not reason from a summary of it.
- Round-trip and idempotency (P7) get a real test; every new ordering gets a test.
- Every new column is checked at **three** touch points, and the third is the one that gets missed: the
  pydantic model; the compile-side row dict + polars schema; **the reverse-side `fieldnames` list and
  `_scalar_cell` mapping**. A column missing from the reverse list round-trips as silent data loss.
- Generators over a model must use `base.authored_field_names`, never `model_fields`.
- Verify all eleven `reference_examples/` keep their `artifact.digest`, `content_signature`,
  `resolution_signature` and `source_signature` — by comparing before and after, not by assuming.

---

# Provenance

Decided in one interrogation session on 2026-08-13, item by item, against `docs/ROADMAP.md` at commit
`bcea5a4`. Four decisions rest on facts probed during the session rather than on the roadmap's text:
the Ensembl GRCh37 REST service (RM48), the VCF 4.4 allele rules (RM5), the empty `SourceRow.dataset`
beside a live `panel:` block (RM4), and `resolution.csv` having no parquet (RM43). Where this file and
ROADMAP.md disagree, ROADMAP.md is stale.
