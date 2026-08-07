# Roadmap history — the items that shipped

Split out of [ROADMAP.md](ROADMAP.md), which is **forward-only**: it now carries active work and
nothing else. This file keeps the *rationale* of every `RMn` that shipped, because a lot of it is
reasoning worth not re-deriving — including one entry that corrects an argument it originally made.

- **[CHANGELOG.md](CHANGELOG.md)** is the release record: what changed, newest first, shared across
  the ecosystem repos. This file is the roadmap-item view of the same events.
- **[RM_TOC.md](RM_TOC.md)** is the complete index of every `RMn`, active and shipped.
- **[COMPILER.md](COMPILER.md)** carries the per-feature coverage table.

`RM1`, `RM2`, `RM3`, `RM8`, `RM9`, `RM18` and `RM19` also shipped, but their entries live in
[USE_CASES.md § Roadmap items surfaced](USE_CASES.md#roadmap-items-surfaced) — where they were
derived — and were never duplicated here.

# Release narratives

The **0.4.1** items below were implemented and **fold into the 0.5.0 cut** (no separate patch release);
see [PROPOSAL_0_4_1.md](PROPOSAL_0_4_1.md):

- **Inject the authority-key list (not hardcode it).** The format owns a reference stripper
  (`normalize.strip_authority_keys`) and a documented convenience set
  (`normalize.IDENTITY_AUTHORITY_KEYS = {namespace, owner, canonical_id}`), but **applies nothing by
  default** — a consumer injects the set of registry-stamped identity keys it wants dropped from the
  authored `module:` block *before* validation (`validate_spec(..., authority_keys=...)`). Extends
  CONSTITUTION P2's inject-only spirit; keeps the validator strict (a stray/typo'd key still trips
  `extra="forbid"` loudly — "a validator validates, it does not fix").
- **Genuinely adopt `module.version`** as a freeform advisory field (accepts the pre-0.4 corpus's
  `v2`/`3`); the compiler previews the future SemVer coercion and warns only when it would change the
  value. Digest-neutral. SemVer *enforcement* is deferred to **RM17** below.
- **`content_signature`** — a stable, name-/Ensembl-independent content identity over the raw authored
  data rows (`manifest.content_signature`, out of `artifact.digest`; `just-dna-compiler signature`
  computes it without recompiling), so a registry can dedup across recompile + metadata-strip where the
  parquet digest can't. Canonical algorithm owned here; the marketplace adopts it.
- **Strict (all-or-nothing) compile** — `compile_module(..., strict=True)` refuses a partial artifact
  when a variant position is left unresolved (the "local hash differs from published" failure mode).
- **A compiler CLI (Typer)** — `just-dna-compiler validate|compile|reverse`, a compiler-only dep (tiers
  intact). Plus `ruff` added to the dev group and package `authors`/`maintainers`.

*Still design-only in [PROPOSAL_0_4_1.md](PROPOSAL_0_4_1.md): the "Ensembl cache authority leaves the
compiler" item (needs the `just-dna-datasets` package to coordinate against).* Everything else below is
0.5-and-beyond scope plus the open idea-book.


## 0.5.0 (released 2026-08-07) — the resolution-table + enricher rework

**0.5.0 is now the source-independent resolution-table rework** (see [PROPOSAL_0_5.md](PROPOSAL_0_5.md)
and [CHANGELOG.md](CHANGELOG.md)): resolution becomes a persisted, source-independent `resolution.csv`
the compiler *consumes* (owning no source convention), produced by a new **`just-dna-enricher`**
network tier (cache → HF snapshot → Ensembl V2 GraphQL → V1 REST fallback + tenacity; best-effort/
strict/`--offline`). It **subsumes RM13** (a network-first resolution/enrichment sibling) and completes
the 0.4.1 *"cache authority leaves the compiler"* decoupling. The `0.4.1` items ride in folded into the
same 0.5.0 cut (no separate patch release).

**Also landed in 0.5.0:** the **gnomAD v4.1** work — a last-resort live resolver link, the
`frequencies.csv` and `gene_metrics.csv` derived-fact sidecars, an offline gene-constraint snapshot, and
**GA4GH VRS allele identity** (stdlib minting, `vrs_id`/`caid` columns, and `variant_key` deriving from
the VA for a resolved substitution — the one intended `artifact.digest` re-baseline, taken inside the
unpublished window). See [PROPOSAL_0_5.md § G1](PROPOSAL_0_5.md) for the decisions and the several
places probing overturned the plan's assumptions.

**The `RMn` schema items below are pushed to 0.6.0** — they are additive and independent of this
rework, so they wait behind it rather than blocking it.

### The pre-cut batch — what rides the closing window

A survey of five candidate annotation-source groups (splice predictors, ClinGen/GenCC/ACMG SF,
PharmCAT+CPIC, HPO/MONDO/Orphanet, missense predictors) produced a clean split: the groundwork each
needs is either a **new table** (no window pressure — deferred below) or a **new column** (window
pressure). So the last 0.5 work is columns plus tooling that carries no schema risk:

- **`StudyRow` queryable p-value** — a single `p_value_num` in (0, 1], with `neg_log10_p` **derived**
  into `studies.parquet`, mirroring `allele_frequency` = AC/AN. A mantissa/exponent pair (the GWAS
  Catalog's representation) was drafted and then dropped: it buys p-values past float64's range
  (subnormal below ~1e-308, zero below ~5e-324), which is a catalogue-scale problem rather than a
  module-scale one, at the price of two columns and a both-or-neither rule every author pays. An
  authored `-log10` was rejected for the opposite reason: it makes the human compute a logarithm.
- **`VariantRow.callable_from`** (the built half of RM6) — the `source_field` pointer grammar, reused
  rather than re-derived.
- **`DiplotypeRow.recommendation_strength`** — CPIC's recommendation strength has nowhere to live;
  folding it into `evidence_level` (PharmGKB 1A–4) would be the `state`-overloading mistake again.
- **ClinGen dosage sensitivity** on `GeneMetricsRow` — gene-keyed, so columns on the existing sidecar
  rather than a new table. Planned as "store ClinGen's integer codes verbatim"; **probing the real file
  overturned that**. The codes look ordinal and are not (`30` = autosomal recessive, `40` = dosage
  sensitivity unlikely), so a consumer sorting them ranks `40` above `3` — the reverse of the meaning.
  They are decoded to terms at the enricher boundary instead. Two more shapes the file has and its
  documentation does not mention: a literal `"Not yet evaluated"` (210 of 1,520 rows) and a comment
  block whose last line is the header.
- **`SourceRow.redistribution`** — tri-state, legibility only. `share_alike` + `commercial_use` cannot
  express "may not be redistributed at all", which is what OMIM- and dbNSFP-class academic-only terms
  actually say; recording that as `commercial_use=False` understates it.
- **RM17** SemVer enforcement (coercing), the `verify`/`sign` CLI, the generic drafting helper with its
  first CPIC provider, an `ORDO` ontology route, and the `htt_repeat_expansion` reference example — all
  digest-neutral. The ACMG SF cross-check was scoped here too and is **deferred to the post-cut round**: the probe
  found no machine-readable list to check against (see below).

## The post-cut round — queued behind the digest window (nothing here needed it)

Small, additive, and digest-neutral, so waiting costs nothing. This was labelled `0.5.1` while it was
being planned as a separate release; it never became one — nothing 0.5.x has been published, so it ships
as part of 0.5.0 with everything above (see the note at the top of [CHANGELOG.md](CHANGELOG.md)).

**Shipped in the post-cut round** (see [CHANGELOG](CHANGELOG.md) for the detail): the whole authoring surface —
templating (`stub`/`scaffold`), offline hints, the enricher lookup surface, **delegated insertion**
and **partial rows**; **RM26**'s remaining two drafting providers (ClinPGx → `pharm_variants.csv`,
ClinVar → `variants.csv`) plus CPIC prescribing recommendations; **RM30**; a cross-table check for
star alleles used but never defined; and three reference examples authored end to end with the
surface (`hfe_hemochromatosis`, `cyp2c19_star_alleles`, `apoe_epsilon`).

**Also shipped in 0.5** (the 2026-08-03 round): the **ACMG SF cross-check** (above), **RM29**'s
three cofactor columns, **RM28**'s cis/trans case closed as a compiler check, the **CLI/API parity**
pass (`keygen`, `reference`, and one requiredness definition shared by `draft` and the authoring
reference), and four adversarial reference examples with the defects each exposed —
`hfe_compound_het`, `shox_par1`, `mt_heteroplasmy`, plus the CYP2D6 probe. The fixes those produced:
the non-diploid guardrail made coordinate-aware and PAR-aware in both directions; `variant_key`
re-derived against the module's declared build (a GRCh37 module was minting GRCh38 VRS ids);
`HeteroplasmyRow` gaining a variant identity; live Ensembl reaching `hint variant`; and three walls of
un-aggregated warnings collapsed. What they surfaced rather than fixed was **RM31–RM35**; four of those
five — **RM31**, **RM33**, **RM34**, **RM35** — were then fixed in the same window, and their entries are
below. Two of the four had been argued to be undecidable, and in both cases part of the argument turned out
to be wrong (RM31's trim did not need an anchor the row does not have; RM33's third column cost no
signature). **RM32** was the fifth, held back as a question about identity rather than a defect, and it was
answered in its own run — with the same result a third time: the probe it was waiting on refuted the
direction the entry had called most promising, and the objection that had parked the *other* candidate did
not survive contact with the data either. Its entry is below.

**The ACMG SF cross-check — ✅ shipped (0.5), as the guarded scrape.** Re-probed 2026-08-03 and the
data file still does not exist: ClinGen's FTP publishes gene-curation, region-curation, dosage and
recurrent-CNV lists and **no secondary-findings list**, and ClinVar's FTP tree carries no ACMG flag
(`gene_condition_source_id`, 13,478 rows, zero mentions of ACMG). So the second branch was taken —
`acmg.py`, `just-dna-enricher check-acmg` — with the guards that branch was made conditional on.

The deferral's reasoning turned out to be *understated* rather than cautious. The pre-cut probe called
it a "91-row HTML table"; it is 94 gene-condition rows over 81 genes, and the obvious `<tr>` split
returns **78 genes, silently**, because two rows open with a bare `<td>` and no `<tr>` at all. The
three genes it drops are `TP53`, `COL3A1` and `TPM1` — i.e. the predicted failure mode ("a
silently-truncated gene list makes correctly authored `acmg_sf=true` rows look wrong") would have
begun with the most recognizable secondary-findings gene there is. The parse therefore counts **cells**
rather than rows and refuses on five guards, none of which hard-codes a gene count; the floor is a
floor, not the list. Details and the verdict tri-state in [ENRICHER.md](ENRICHER.md).

**Still queued:** nothing from that list.


# Shipped items

**RM3 is the cautionary row.** It was marked shipped in 0.4 against a *hand-authored sample*, and the
real ClinPGx corpus then rejected roughly 97% of itself against that shape — corrected by RM20. When
marking an item shipped, check what it was validated against.


## RM6 — Callability as first-class state

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** format (schema) · **Motivating case**
callability / no-call ≠ hom-ref

**Callability as first-class state.** Both halves are now built: `requires_callable` was already a
materialized tri-state column, and **`callable_from`** ships as the pointer beside it — the VCF
field(s) a consumer establishes callability from (`DP`, `GQ`, `FT`, `DP\|GQ`), reusing
`source_field`'s bare-token grammar rather than inventing a second one. It left the reserved
namespace on being built: a reserved name is refused at author time, which would make the column
unwritable. The consumer's own oracle enum (`CONFIRMED_NEGATIVE`/`LOW_DP_NEG`/`UNCOVERED`) is why
this matters — a named negative is assertable only where the proof is, and now the module says
where to look.

## RM11 — `doi` provenance column on `StudyRow`

**Severity** — · **Status** ✅ shipped in 0.4 · **Owner** format (schema) · **Motivating case**
validator source-checks (§4a)

**`doi` provenance column** on `StudyRow`, wider than `pmid` (covers
preprints/books/theses/datasets with no PubMed id); validated against the DOI grammar, kept
verbatim, materialized into `studies.parquet`. A network-first validator (RM13) cross-fills
`doi`↔`pmid`. Additive/optional → P3/P8 clean. The full DOI-only fix (relaxing the mandatory
`pmid`) is a 1.0 item — see the 1.0 tracker.

## RM12 — Provenance locator (`provenance_quote` / `provenance_regex`)

**Severity** — · **Status** ✅ shipped in 0.4 · **Owner** format (schema) · **Motivating case**
validator fulltext check (§4a)

**Provenance locator**: optional `provenance_quote` (keyword phrase) + `provenance_regex` on
`StudyRow`, pointing at the passage in the cited article's fulltext so a validator can answer
*"does the fulltext contain this claim?"* yes/no. The regex is a **declarative pattern grammar**
(Principle 1 — data, not code; `re.compile`-checked at author time, matched by a consumer-side
ReDoS-safe engine); the provenance analogue of `source_field`.

## RM13 — The network-first resolution tier

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** network tier (`just-dna-enricher`) ·
**Motivating case** deterministic module scrutiny (§4a)

The network-first resolution/enrichment tier. 0.5 builds the rsid↔coordinate resolution half
(cache + Ensembl V2/V1 + tenacity, producing `resolution.csv`); the source-check half (validate
`pmid` in PubMed, confirm fulltext provenance, cross-fill ids) is additional resolver links the
same package can grow. Principle 2 stays intact — the enricher is a *separate tier* that fetches;
format/compiler never do.

## RM14 — Structured per-version authorship

**Severity** — · **Status** ✅ shipped in 0.4 · **Owner** format (schema) · **Motivating case**
authorship-aware scrutiny (§5a)

**Structured per-version authorship**: an optional `authorship: [Contribution]` on
`module_spec.yaml`/`ModuleManifest`, unbundling the flat `authors` + free-form `curator` (which
smuggled kind via the `"ai-module-creator"` default) into three orthogonal axes (P5): **identity**
(`who`), **role** (closed vocab created/edited/audited/reviewed), **kind** (open, multi-valued:
human ladder `human`→`human_expert`→`human_certified`, or `ai`+scale `agent`/`team`/`swarm`; no
`hybrid` — a joint contribution is two entries). Motivating case: **AI and human error-spectra
overlap but differ**, so a consumer (the RM13 validator, a marketplace review queue, a human
auditor) routes scrutiny by author-kind — the format carries the kind, the consumer picks the
profile (north star). **Digest-neutral** (manifest metadata, out of `artifact.digest`); like
`panel`, not reconstructed by the lossy `reverse_module`. Folding the flat `authors`/`curator` in
is a 1.0-cleanup candidate.

## RM17 — SemVer on `module.version`, coercing

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** format (schema) · **Motivating case**
pre-0.4 corpus `module.version`

**SemVer on `module.version`, coercing.** The 0.4.1 read-only preview became enforcement on
`ModuleInfo`: `v2` → `2.0.0`, with the rewrite reported once via `version_coerced_from` (silently
editing an authored value is the thing this codebase does not do). **Coerce rather than
strict-reject**, decided against the corpus: the pre-0.4 modules are full of `v2`/`3`, and
rejecting them would break every one to gain a stricter spelling of an advisory field.
Digest-neutral. One consumer-visible change: a non-SemVer version used to be dropped from
`Identity.version` entirely, so such a module published with no version at all — it now reaches
the manifest coerced.

## RM20 — PharmGKB annotations are per-genotype and per-category

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** format (schema + compiler) · **Motivating
case** 2b, the real ClinPGx corpus

**PharmGKB annotations are per-genotype and per-category.** `PharmVariantRow` gains `genotype`,
`phenotype_category` (closed vocab, multi-valued) and `annotation_id`; the duplicate key becomes
`(variant_key, drug, genotype, phenotype_category, annotation_id)`. Corrects RM3: one variant+drug
carries several distinct annotations (rs4149056+simvastatin is Metabolism/PK 1A, Efficacy 3 *and*
Toxicity 1A), and 1,199 of 17,380 triples in the ClinPGx release collide without the two extra
columns.

## RM21 — Data-source licensing as data

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** format (schema + compiler) + enricher ·
**Motivating case** 2c, marketplace redistribution

**Data-source licensing as data.** `sources.csv`/`SourceRow` per (source, layer): licence, pinned
`license_sha256`, attribution, notice, tri-state `share_alike`/`commercial_use`, and the
acquirer's `declared_use`; summarized into `manifest.sources`. The compiler refuses
annotation-layer content that forbids sale when no declaration is recorded — **data-driven, not a
CLI flag**, because a flag cannot round-trip (P7). Motivated by every PGx upstream being CC BY-SA
*plus* a bar on sale.

## RM22 — PGx tables join resolution

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** enricher · **Motivating case** 2c, 3c

**PGx tables join resolution.** `enrich()` reads `pharm_variants.csv` and `haplotypes.csv` as well
as `variants.csv`, so a PGx module (which carries no `variants.csv` by design) gets coordinates
instead of an empty `resolution.csv`.

## RM26 — All three drafting providers

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** enricher · **Motivating case**
gene-panel authoring; PGx authoring

All three drafting providers. CPIC → PGx tables (`pgx_draft`), **ClinPGx → `pharm_variants.csv`**
(`clinpgx_draft`), and **ClinVar → `variants.csv`** (`clinvar_draft.draft_gene_panel`, `enricher
draft-panel`), which partially dissolves RM4: a gene panel is authorable with no compile-time
reference materialization. The ClinVar one needed two mechanisms rather than a compromise.
`VariantRow.genotype` is required and ClinVar publishes **alleles, not genotypes** — whether
carrying a pathogenic allele is a carrier state or an affected one follows from the condition's
inheritance mode, which the source does not state and a provider must not invent. So it writes a
**partial row** (`draft.PartialRow`): every cell ClinVar publishes, with `genotype` carrying
`TEMPLATE_PLACEHOLDER`, which no mode compiles. Sameness is decided by `match_on` (the identity
columns) rather than by the natural key, because that key runs through the stub — so once a human
fills a genotype, a re-draft reports `already_present` instead of re-adding the stub. Rows land in
their gene's block via delegated insertion, which is what made this usable on a 2,500-row panel
rather than merely possible. Identity is filled whole or not at all: a lone `alts` on a
position-only row mints a VRS `ga4gh:VA.…` key instead of `chrom:start:ref`.

## RM29 — Cofactor columns

**Severity** — · **Status** ✅ shipped in 0.5, inside the unpublished-digest window · **Owner**
format (schema) · **Motivating case** PGx; call-confidence gating

**✅ shipped (0.5): cofactor columns, taken inside the unpublished-digest window.** Three
optional columns carrying single-subject cofactors with **no predicate language at all**, because a
row's columns already conjoin. Both halves mirror `HeteroplasmyRow.tissue`, already a
cofactor-as-column.

(a) **`VariantRow.quality_from` + `min_quality`** — "assert this only where the call is at least this
good", in the `source_field`/`callable_from` declarative-pointer idiom (`quality_from` joined that
shared validator rather than growing a third private one). Two columns rather than one expression:
the pointer says which VCF field, the number says the inclusive floor, and neither needs a grammar,
an evaluator or a sandbox (P1). A **both-or-neither** model rule, because half a floor reads as a
configured gate and is not one — a consumer would have to guess the missing half, and every guess is
a clinical policy the module did not write. Still not the dropped `caller` names: those recorded
which tool made a call (consumer-side measurement provenance); this is an applicability bound the
annotation carries, the same kind of thing a `MeasureBinRow` bound states.

(b) **`DiplotypeRow.clinical_context`**, in `_TABLE_DUPE_KEYS` — which dissolves the
`draft --population` refusal rather than resolving it. Drafted live against CPIC, clopidogrel now
yields 1,998 rows over three contexts instead of a refusal, and the disagreement the refusal was
protecting is visible in the data: `*2/*2` Poor Metabolizer is `strong` in `CVI ACS PCI` and
`moderate` in the other two, with different prescribing text for `NVI`. `--population` survives as a
*filter*. **Not named `population`**: `FrequencyRow.population` is an ancestry group with its own
validated vocabulary, and probing CPIC's live table (2,115 rows, 2026-08-03) showed these values are
indication, age band, prior-treatment status and dose band — reusing the name would put two unrelated
axes under one label across two tables and spend the name ancestry will want on `DiplotypeRow` later
(P5). Open rather than a vocabulary, since every guideline body scopes differently; whitespace-stripped
on load, because three of CPIC's sixteen live values carry a trailing space and the column is in the
key. | format (schema) | PGx; call-confidence gating | **done** |


## RM31 — One indel spelled two ways defeats allele-aware resolution

**Severity** — · **Status** ✅ shipped in 0.5 (found by dogfooding 2026-08-03, fixed in the same window;
one residual, stated below) · **Owner** format + enricher · **Motivating case** any indel-bearing panel

`genotype_fits` compared **allele strings**, so two valid spellings of one indel did not match and the
locus was dropped. Confirmed end to end while drafting `reference_examples/shox_par1/`: `rs1569493663` is
drafted from ClinVar as `X:634689 CAG>C` while Ensembl publishes the same 2 bp AG deletion as
`X:634690 AGAG>AG`, so the authored genotype "could not host" Ensembl's alleles and the variant resolved
to `not_found`.

**What shipped is the bounded reference-free normalization, and two things the entry had wrong made it
smaller than it looked.**

*First*, the entry assumed the trim would need the authored row's anchor. It does not, and it could not
have: the row records **no coordinate at all** (`clinvar_draft` prefers the rsID, and the model forbids
`ref`/`alts` without a coordinate), so the genotype `C/CAG` is spelled in ClinVar's frame in a row that
never stated that frame. A genotype naming two alleles nevertheless *carries* its frame, because the two
strings share whatever flank their record used — so `alleles.parsimony_reduce` strips the flank a
*collection* shares and needs no position. `{C, CAG}` and `{AGAG, AG}` both reduce to `{'', 'AG'}`.

*Second*, the entry framed the choice as "bounded normalization that silently misses cases" vs
"reference-backed normalization the compiler cannot run". The third option is the house algebra:
`hosting_verdict` returns **three** values, so nothing is missed silently. The confident negative has a
real invariant behind it — re-anchoring moves an indel but never changes how many bases the event adds or
removes — so differing event **sizes** prove different variants (`rs281864532`'s 1 bp insertion vs its
2 bp deletion), while same-size different-content pairs are reported as **undecided** and the locus is
*kept*. That is the residual the reference would settle, named rather than swallowed, and the enricher can
still settle it with seqrepo (not yet wired — see the residual below).

**Monotonicity is what made it safe to ship inside the window.** The raw string comparison runs *first*,
so normalization can only ever add acceptances: every locus that was hostable is hostable, byte for byte,
with the same expansion. Pinned by a property test over every real (genotype, ref, alts) triple in the
reference examples.

**Adding the case to `test_resolution_matrix.py` immediately found a second defect, in the other half of
the compiler.** `_check_allele_membership` was a string comparison of the same kind, doing its own exact
set difference — so once resolution reconciled the spellings and expanded onto the locus, membership
refused the same module under `strict` because the literal `C` and `CAG` were not in the resolved set. The
compiler contradicting itself. It now asks the shared predicate, Kleene-OR'd over the loci (one locus that
can host it settles the question; an undecidable spelling withholds; only all-False is a finding).

**The residual, and it is worth being precise about.** `reference_examples/shox_par1/` now resolves
fully — `rs1569493663` located, 10 findings out of 10 (in 20 rows at the time of this entry, and in 10
since RM32 kept only the X spelling of each pseudoautosomal locus) — but the compiled row carries
`genotype ["C","CAG"]` (ClinVar's frame) beside `ref=AGAG, alts=["AG","AGAGAG"]` (Ensembl's). The module
is located and coherent, and a consumer joining the genotype against a VCF's alleles by string equality
will still miss, because the VCF is in the reference's frame. Two ways out, and only one is legal today:
the consumer applies the same reduction (`just_dna_format.alleles` is public and dependency-free for
exactly this), or the enricher rewrites the authored genotype into the resolved frame — which is the
parked **enricher co-authoring** item, since editing an authored cell would make `content_signature`
depend on a network fetch. So the reduction is offered to the consumer, and the rewrite stays parked.

## RM34 — The CPIC provider has no filter

**Severity** — · **Status** ✅ shipped in 0.5 (found by dogfooding 2026-08-03, fixed in the same
window) · **Owner** enricher (CLI) · **Motivating case** CYP2D6, and any large star-allele gene

`draft --gene CYP2D6` produced a module nobody could use: **16,290 diplotype rows, 73% of them
`Indeterminate`**. Every row a faithful transcription, and it compiled — but not human-authorable in the
sense the charter gates on, and the author had no way to draft a subset (`--drug` *adds* rows).

**`--allele` shipped, and the reason it is the right filter is that the author already knows the answer:**
a consumer's caller emits a bounded allele set, and *n* alleles is *n(n+1)/2* pairs. Six alleles collapse
CYP2D6 to 21 diplotypes — verified against live CPIC, and it compiles. It filters **all three** tables
(defining variants, function rows, and only diplotypes whose *both* halves are selected), because
filtering one and not the others leaves a module naming alleles it never defines, which is exactly what
`_cross_validate_haplotype_definitions` warns about. `*1` is always kept and the message says so: it is
defined by carrying no variants, so it costs nothing, and dropping it would make `*1/*2` — the commonest
real diplotype — undraftable for an author who asked for `*2`. An unknown allele name refuses and lists
what CPIC publishes, since a typo would otherwise yield a quietly smaller module. `--allele` requires a
single `--gene`: a star name is gene-scoped, so one set across several genes would filter each by a name
meaning something else there, and drafting is per-gene and re-runnable by design.

The alternatives considered and not taken: `--skip-indeterminate` / `--phenotype` (filtering on CPIC's own
call is cheaper, but an absent row cannot then be told from "CPIC declined to call", and it does not
address scale), and an activity-score threshold (the same objection, plus CPIC writes some scores as
inequalities).

**Dogfooding the filter on real CYP2D6 immediately found three more defects, all fixed here:**

- **The filter's own count was misleading.** It read "567 of 16836 diplotype(s) drafted" for six alleles,
  because the 546 copy-number rows (`*4x≥3/*95`) that the filter deliberately leaves alone were tallied as
  kept and then skipped by the notation rule — two findings, and the reader could see neither. It now
  counts over parsable pairs: "21 of 16290".
- **`DELTCT` and `AAAGGGGCG(2)` are not IUPAC ambiguity codes**, and the message announced them as such —
  a false claim about the data that points an author at the wrong thing. `cpic.unusable_allele_reason`
  now separates an *ambiguity* (an uncertainty CPIC recorded, never expressible) from a *notation* (a
  grammar gap, RM5, that a release may widen), and reports them as two findings.
- **Two more walls of un-aggregated warnings**: 67 unusable-allele lines and 10 "no rsID and no
  chromosome" lines in one CYP2D6 run, each one line per row. Both collapsed to one line per reason with
  a count and examples — the third and fourth time this file has needed that.

## RM36 — A model property cannot know its module's build

**Severity** — · **Status** ✅ shipped in 0.5 (filed and closed on 2026-08-06, in that order) ·
**Owner** format (schema) + compiler · **Motivating case** a GRCh37 module carrying `heteroplasmy.csv`

**The finding.** `HeteroplasmyRow.variant_key` is a *property* that passes `alts` to
`derive_variant_key`, so it can mint a `ga4gh:VA.…` — and a property has no module in scope, so it
always took the GRCh38 default. One locus on a `genome_build: GRCh37` module therefore carried two
identities: `6:26093141:G:A` from `variants.csv` (a stored field the compiler re-stamps) and a GRCh38 VA
from `heteroplasmy.csv`. It was the last of seven instances the build sweep found, and the only one
filed rather than fixed on the spot, because the three obvious repairs were each a design decision.

**The entry's own three candidates were all rejected, and the reason is the same one each time: they
answer "where should the build be stated?" when the build was already stated correctly.** It lives in
`module_spec.yaml`, once, and that is right — it is a module-wide property, so per-row is overkill and
**per-CSV (a "service row") is worse**: two files could then disagree about one fact, a data table would
carry a non-data row (Principle 5), an author copying rows between files would silently drop it, and it
would *still* not reach the model — a loader parsing such a row already knows the build from the yaml it
just read. Stamping it like `VariantRow` fails differently: there is no stored field here to correct
after load, which is precisely what distinguishes a property from `variant_key`.

**Closed by injection instead: the row is *told*, it does not *hold*.** `AuthoredModel._genome_build` is
a pydantic `PrivateAttr` that `_load_csv_rows` sets on every row it builds, from the build the caller
read out of the yaml. Being private it is absent from `model_fields` and `model_dump()`, so it is not a
column, reaches no CSV and no parquet, moves no `artifact.digest`, and `extra="forbid"` still rejects it
if an author tries to write one. The declaration stays in exactly one place and reaches every row that
needs it. `PrivateAttr` + a read-only property was already the house idiom
(`ModuleInfo._version_coerced_from`), so this introduced no new mechanism.

**And it exposed a second thing, which is why the entry is longer than the fix.** `content_signature`
documented itself as **"build-independent"**. That was true of the *reference used to resolve* and false
of the **declared assembly**, and conflating the two meant the content-dedup key hashed two modules
describing loci 228 bp apart as identical content. The realistic instantiation is not contrived: "lift
over" a GRCh37 panel by editing the yaml and not the coordinates, and a registry keyed on this calls the
result the same module. `genome_build` now feeds the hash — **but only when it is not the default**,
which is the same omit-the-default normalization the algorithm already applies to an unset optional
column, not an exception to it. That keeps the fix targeted: every GRCh38 module, which is every module
published to date, keeps its signature byte for byte, so `find_versions_by_content` still links a 0.4
module to its own 0.5 recompile; only the modules that were being *misidentified* move.

## RM35 — A continuous binning table cannot be tiled without a finding

**Severity** — · **Status** ✅ shipped in 0.5 (proved by construction 2026-08-03, fixed in the same
window) · **Owner** format (binning semantics) · **Motivating case** heteroplasmy, PRS percentile

Three rules, individually right and jointly unsatisfiable on a continuous measure: bounds **inclusive at
both ends**, an overlap an **error**, any positive hole a **warning**. Two adjacent `allele_fraction`
bins therefore either shared an endpoint (a measurement of exactly `0.1` selecting two phenotypes) or
did not (a hole), and no epsilon escaped it — `[0, 0.0999999]` + `[0.1, 1.0]` still warned. Every
`allele_fraction`/`prs_percentile` table carried a finding forever: a check that could not be satisfied
rather than one that was failing.

**Resolved as "a shared endpoint is a boundary, and the higher bin owns it".** The lookup rule is *select
the row with the greatest `measure_min ≤ x`*, so a real heteroplasmy table tiles `0.0–0.1`, `0.1–0.3`,
`0.3–1.0` and reports nothing. The overlap test becomes `lo < prev_hi` on a dense kind and stays
`lo <= prev_hi` on a discrete one, where two integer bins sharing an endpoint really do both claim it.

**Half-open `[min, max)` for continuous kinds was the other serious candidate and lost on authorship,
which is the charter's own gate.** It is formally cleaner — each row's coverage is self-contained — but
it makes one column mean two things depending on another column's value (P5), the number written in the
cell is then *not* in the bin while the same column stays inclusive on integer tables, and a bounded
domain's top value (AF `1.0` is homoplasmy, and real) becomes unreachable unless the last bin is
authored open, which is a new convention and a new finding class. Both candidates produce *identical
authored bytes* in a table's interior and need the *same* check predicate; they differ in one cell (the
last bin's upper bound) and in what an author has to remember. Dropping the interior-gap check for
continuous kinds — the third candidate — was rejected for throwing away a real check while leaving the
shared-endpoint error in place, so an exactly-tiling table would still have refused.

One case the design turned up that the entry had not: two bins sharing a **lower** bound refuse on every
kind, because the tie-break selects the greatest `measure_min` and equals do not sort. It is reachable
only as a sharp `[0.1, 0.1]` beside a range starting at `0.1` (anything wider is already a crossing
overlap), and there a measurement of `0.1` genuinely has two answers — an ambiguous selection, so it
refuses rather than warning.

`reference_examples/mt_heteroplasmy/` migrated from `0.099`/`0.299`/`0.399`/`0.149` to touching bounds
and now compiles clean; its digest moved, inside the unpublished window. The original bind stays
demonstrable in `schema/tests/test_heteroplasmy_variant_key.py` by running the same pair of bounds
through `copy_number`, which still obeys the old rule.

## RM33 — `source` names two different things in two tables

**Severity** — · **Status** ✅ shipped in 0.5 (found by dogfooding 2026-08-03, fixed in the same
window) · **Owner** format (schema) + enricher · **Motivating case** every enriched module

`resolution.csv`'s `source` names **which link answered** (`ensembl-rest`, `cache`, `clinvar`, …) while
`sources.csv`'s names a **licensed data source** (`ensembl`, `clinvar`, …), and `_source_checks`
compared the two by string equality — so every enriched module warned that `ensembl-rest` has no terms
recorded. Two vocabularies under one name (P5), spread across two tables.

**What shipped is the third thing the original entry said was missing:** `ResolutionRow.authority`, a
provenance column naming the licensed source the link speaks for, with the link→authority map in the
**enricher** (`licensing.RESOLUTION_AUTHORITY_BY_LINK`) because that is the only tier permitted to hold
a source convention. It cost nothing in identity terms — `authority` sits outside
`RESOLUTION_FACT_FIELDS`, so no `resolution_signature` moved, and `resolution.csv` is fact-hashed rather
than byte-hashed. Reverse does not re-emit it: a reversed table's facts came from parquet, so there is
no authority to name, which is the accurate statement rather than an empty column.

Both repairs the entry rejected stayed rejected: a `SourceRow` per link would make `ensembl-rest` and
`ensembl-graphql` two sources with identical terms, and a link→source map in the compiler would hand it
the source convention P2's 0.5 tightening removed.

Three things came out of implementing it that the entry had not seen:

- **`enrich()` now writes its `SourceRow`s**, at the reserved `"resolution"` layer that nothing had ever
  written — as do the frequency and gene-metrics passes, via one shared `licensing.record_source_terms`.
  None of these layers can taint a module (only `annotation` does), so what they carry is the
  **attribution** gnomAD, Ensembl and ClinVar each request, which is exactly what the table is for.
  `GNOMAD_TERMS` was read from gnomAD's own policy page for this (CC0, attribution requested, and a
  notice that layered annotations like SpliceAI keep their own CC BY-NC terms).
- **`gene_metrics.csv` had the same overloading**: `source` was `gnomad-constraint`/`gnomad-api`, two
  *routes* for one licensed source. It now records `gnomad`, and the route stays in `dataset`, which is
  where this codebase already says the release distinction lives — and `dataset` is inside the fact set
  while `source` is not, so the v2.1.1-vs-v4.1 distinction the tests pin is untouched.
- **An `annotation`-layer row could never be corroborated**, so the orphan half of the check called it
  stale on every drafted module. "No table used it" is decided by reading fact tables' `source` columns,
  and the annotation layer *is* `variants.csv`/`diplotypes.csv`, which carry none by design. Those rows
  are now exempt — they are also the rows the licence gate keys on, so reporting them as unused was
  precisely backwards.

## RM30 — One rule for a haplotype name across all three PGx tables

**Severity** — · **Status** ✅ fixed in 0.5 · **Owner** format (schema) · **Motivating case**
`reference_examples/apoe_epsilon/`, which found it

**✅ fixed (0.5): one rule for a haplotype name across all three PGx tables.**
`AlleleFunctionRow.allele` enforced `STAR_ALLELE_PATTERN` (a leading `*`) while
`HaplotypeRow.haplotype_name` and `DiplotypeRow.haplotype_a`/`haplotype_b` had no rule at all, so
`e4` was legal in two of three tables and illegal in the third — and an author working around it
with `*4` in one and `e4` in another hit the later cross-table check's "used but not defined",
with no spelling that satisfied both. Found by `reference_examples/apoe_epsilon/`. The three now
share `validate_haplotype_name`: non-empty, no whitespace, and nothing else — **a name is an
identity, not a grammar**. `STAR_ALLELE_PATTERN` stays exported and is still what `pgx_draft`
checks at its four sites, so loosening the schema did not loosen CPIC drafting. Net effect is a
loosening (previously-valid data stays valid, P3-safe) plus a negligible tightening on the two
columns that had no floor: an empty or whitespace-split name could never have identified a real
haplotype.


## RM32 — A pseudoautosomal locus is one place on two contigs

**Severity** large (it was a question, not a patch) · **Status** ✅ shipped in 0.5 (found by dogfooding
2026-08-03, answered in its own run 2026-08-04) · **Owner** format (identity) + enricher · **Motivating
case** any PAR gene: SHOX, CSF2RA, ASMT, CD99

Nine of the ten SHOX variants in `reference_examples/shox_par1/` mapped to **both** X and Y at the same base
(PAR1 is coordinate-identical on the two contigs in GRCh38), so the one-to-many expansion emitted two rows
per variant — **20 rows for 10 findings**, all inside `artifact.digest` — while standard GRCh38 analysis sets
hard-mask the Y PAR, so the ten Y rows could match nothing. The entry was held back because the obvious
repairs each failed for a different reason, and what remained was a question: *does a module say something
about a place in the genome or about a contig coordinate, and if the former, what identifies a place present
on two sequences?*

**The probe the entry named came back negative, and that is what settled it.** The ClinGen Allele Registry
mints **two** CA ids for one PAR base — `CA254919` (X:640851) and `CA254920` (Y:640851) for `rs137852556`,
`CA10330023` and `CA2467802563` for `rs746801054`. So `ResolutionRow.caid` cannot carry a place identity, and
no upstream mints one; a format that named the concept itself would be inventing a term with no source behind
it, against P5's one-way-door rule.

**What the probing found instead was that the sources had already chosen, and the objection that had parked
the enricher policy did not survive it.** That objection was that a PAR policy "encodes the *consumer's*
analysis set into the module". It does not:

- **ClinVar** — what `draft-panel` reads — holds **no** variant in either PAR on Y. All 677 of its Y records
  lie outside the PARs, and all 1,675 records across SHOX/CSF2RA/ASMT/CD99/XG/SPRY3/IL9R/VAMP7 are on X.
- **gnomAD v4** excludes the Y PAR from its callset outright: `region(chrom:"X", 640000-641500)` serves
  **880** variants and the identical interval on Y serves **none**.
- The **Registry**'s Y record is a stub — a dbSNP cross-reference, no ClinVar, no gnomAD, and a title that
  degrades from `NM_000451.4(SHOX):c.517C>T (p.Arg173Cys)` to the bare `NC_000024.10:g.640851C>T`.
- **Ensembl/dbSNP** reports both, and is the only source that does — the single link that manufactures the
  Y row.

So recording the X spelling follows the **sources' own convention**, which is exactly what the enricher
exists to do and what P2 makes it the only tier permitted to hold. `enrich` keeps the X locus of a PAR pair
and reports the twin it left out; `--keep-par-twin` records both for a consumer whose reference is not
analysis-set masked. It **selects, it does not repair** — the same contract as the allele-aware
`hosting_verdict` filter beside it in the same function.

**The verdict is per locus, and a real gene proves it has to be.** **XG** (X:2,751,798–2,816,500) runs out of
PAR1, which ends at 2,781,479; **SPRY3** (X:155,612,298–155,782,459) runs into PAR2, which starts at
155,701,383. Any gene- or module-scoped policy is wrong for half of either one.
`reference_examples/par_boundary/` is that case built end to end: one run, one PAR2 locus whose Y twin is
left out, two XG loci past the boundary that were never candidates.

**PAR2 is why the mapping is arithmetic rather than an equality.** PAR1 shares coordinates between the
contigs, so a shortcut comparing "the same base on X and Y" would have passed the SHOX panel and silently
failed PAR2, where X:155,773,979 and Y:56,960,499 are the same place at a constant offset of 98,813,480.
`vrs.par_partner` computes that from the interval table — the paired intervals are equal-length in both PARs,
because GRCh38's Y PAR *is* a copy of the X PAR, and a test pins that property over the table so a future
build whose intervals do not pair cannot corrupt a locus selection silently. It is public and
dependency-free for the same reason `alleles.parsimony_reduce` is: a consumer can apply the identical test.

**Why the other three candidates stayed rejected.** *Collapsing the pair* contradicts the identity model 0.5
adopted — a VA keys on the refget accession, X and Y are different sequences — and would break the paralog
case the expansion was built for; selecting between two spellings of one place is not collapsing two alleles.
*A `--par` compiler flag* is charter-illegal (P7): a flag cannot be recorded in the artifact and
`reverse_module` rebuilds the spec from parquet alone, so `compile → reverse → compile` would diverge. The
enricher flag is legal for precisely the inverse reason, and `par_boundary` demonstrates the fixed point —
`digest`, `content_signature` **and** `resolution_signature` all reproduce across the round trip. *A
`place_key` column* was rejected because the correspondence is derivable from constants already in the tier,
so a column would make an author restate what the data determines — the argument that already rejected
`requires_phase`.

**Two things the entry claimed that turned out not to be problems**, checked rather than assumed:
`studies.csv` is rsID-keyed, so both expanded rows inherited the citation and the expansion never orphaned
grounding evidence; and the non-diploid guardrail branches only on `chrom in {MT, Y}`, so selecting X makes
`_check_contig_ploidy` quiet rather than wrong — it stays for hand-authored and `--keep-par-twin` modules.

**It also exposed a defect nowhere near PAR.** `enrich_frequencies` recorded `status="not_found"` for any
locus gnomAD returned nothing for, with a comment asserting the row was a **fact** — "gnomAD was asked and
does not have this allele". For a Y-PAR locus that is false, so a SHOX frequency run would have written ten
absences gnomAD never established. Fixed with a third vocabulary member: `not_covered`
(`VALID_FREQUENCY_STATUS`, and `FrequencyRow.status` gained the validator it never had), the coverage rule in
`gnomad.covers_locus` where a source convention belongs, and such a locus is no longer even queried — the
question was spending a slot of a 10-per-minute budget to learn nothing, and asking is what produced the
false absence. `not_covered` rather than `unchecked`, which is this codebase's word for a question never
put; this is the stronger statement that the source's scope excludes the locus. It is deliberately outside
the `strict` gate: a locus gnomAD cannot cover is perfectly reproducible, and refusing would make a PAR
module uncompilable for a reason no authored edit could fix.

**Digest impact, spent inside the window on purpose:** every PAR module's `artifact.digest` moves, because
half its rows are gone. `shox_par1` went from 20 rows to 10 with every other cell byte-identical, and
`content_signature` did not move at all — it is pre-resolution and reference-independent by definition, which
this is a clean demonstration of. What remains of the PAR question is the **multi-build** half: PAR intervals
are per-assembly, so `par_partner` withholds on any build but GRCh38 and the generalization belongs to RM15.

## Delegated insertion — the reasoning, kept because it corrects itself

**Severity** — · **Status** ✅ shipped in 0.5 · **Owner** compiler (`draft`) · **Motivating case**
re-drafting a multi-gene module


Drafting appended at the end. That was the right first cut, but the reasoning originally recorded here
led with `artifact.digest` and **that argument did not survive checking**, so it is corrected rather
than quietly dropped:

| probed | result |
|---|---|
| a pure row reorder moves `artifact.digest` | yes |
| …and `content_signature` | **unchanged** — it is order-independent by construction |
| a reordered module is still a compile → reverse → compile fixed point | **yes**, P7 is untouched |
| duplicate keys are rejected outright, so order can disambiguate nothing | yes |
| anything reads the append-only prefix property | **no** — one test asserts it; no other code consumes it |

So row order is semantically vacuous here: with duplicates rejected, a table is a bag, not a
sequence, and the digest's order-sensitivity is a parquet serialization artifact rather than a
meaning. The decisive point is that **an author reordering rows in their editor is already legal and
already moves the digest, and nothing objects** — so "it moves the digest" cannot be a reason to
refuse a tool the same move; it would equally forbid the human from tidying their own file. Nor is
mid-flight digest stability worth much: the digest is consumed at exactly one moment, *publish*, and
during authoring every edit changes it anyway.

What *is* worth refusing is **arbitrary** insertion — `insert_rows(at=N)` — and for an unglamorous
reason: it adds a second writer and index arithmetic to buy an ergonomic nicety a text editor already
does, with no safety the compiler does not already provide.

**Delegated insertion is the shaped-right primitive**, and is what was built (`draft.place_rows`,
`append_rows(..., group_by=…)`): the tool chooses *where*, never *what*. New rows land adjacent to
the block that shares their group columns (gene, haplotype, drug) instead of at a caller-supplied
index. It buys the whole win that matters — append-only makes a re-drafted file
*chronological* rather than logical, and after a few re-runs a gene's rows are scattered down the
file, which taxes the human half of the human-authorable ⇔ machine-precise duality this DSL is gated
on. It needs no `at=` parameter, keeps one writer's worth of story ("appends into a group"), and
leaves the never-rewrite-a-cell rule exactly where it is — a test asserts that every shifted row's
cells are byte-identical afterwards. `DraftReport.shifted` names each one, because that is cheap and
makes the diff legible.

Still a hard **no**: a `sort`/`canonicalize` command. It moves every row at once for no authoring
gain, and unlike a grouped append there is no local reason for any individual move.

## RM37 — `content_signature` counted *where* a value was written

**Severity** medium · **Status** ✅ shipped in 0.5 (filed and closed on 2026-08-06, in that order) ·
**Owner** format (compiler) · **Motivating case** an externally drafted GWAS module

**The finding.** `compile → reverse → compile` held `artifact.digest` and `resolution_signature`
exactly, but moved `content_signature` for any module that filled `curator` or `method` **on the row**
instead of in `module_spec.yaml`'s `defaults:`. `reverse_module` infers the module default from the
commonest value (`_most_common`), writes it into the rebuilt `defaults:`, and blanks every cell that
matches — so the value survives, in the other place. `content_signature` hashed the CSVs *before* spec
defaults were applied, so it saw two different contents. The `create-module` skill states the two values
must match (*Module structure* — "a value every row shares belongs in `defaults:`"); for this shape they
did not.

**No reference example could have caught it.** All eleven put `curator`/`method` in `defaults:`, which
is the canonical form reverse emits, so every one of them was already at the fixed point on the first
pass. It took a module authored elsewhere — 207 rows carrying one per-row `method` string — to show
it, which is the same lesson as RM36's: the corpus cannot probe an axis on which it is uniform, and
"where the author chose to write this" is such an axis.

**The repair, and why the other two stayed rejected.** The entry filed three candidates:

- *Stop inferring defaults on reverse; always write cells explicitly.* Rejected — it mirrors the bug.
  A module that legitimately uses `defaults:` would then round-trip into explicit per-row cells and
  move its own signature. The asymmetry is unavoidable as long as one value has two homes and the
  hash can see which one was used.
- *Refuse a per-row `curator`/`method`.* Rejected — it deletes an authored column doing real work. A
  module drawing rows from several sources genuinely has a per-row method, which is precisely what the
  motivating module had.
- *Apply spec defaults before hashing.* **Shipped.** It makes the signature a function of what the
  module *means* rather than of where the author typed it, which is the property a content-dedup key
  needs. `_resolve_spec_defaults` folds `defaults:` into each variant row (the only model carrying
  those fields) immediately before hashing.

**The objection to the shipped option was compatibility, and it was overtaken by two facts.** Filing
it, the entry called this "a P3/P8 identity change" because it moves `content_signature` for already
published modules. First: **0.5 was unpublished when this landed** — tags stopped at `v0.4.0` and all
three packages sat at `0.5.0` — and that window is exactly where an identity change is cheap. Second, and more
useful, the change is **narrower than it looked**, because it reuses the normalization RM36 already
established for `genome_build`: an effective value equal to the `Defaults` model's *own* field default
is written back as `None` and therefore omitted from the hash (`exclude_none=True`), the same way an
unset optional column always was. A module that says nothing about `curator`/`method`, or that names
the built-in values, keeps its signature byte for byte. Measured rather than assumed: **one of eleven
reference examples moved** (`grch37_build`, which sets `curator: audit` with blank cells), and it is
itself a 0.5-era addition.

**It closed a second defect nobody had filed.** Because `defaults:` reached the hash through no path
at all, two modules whose *only* difference was `defaults.curator` hashed **equal** — different
content, one identity, which is the same class of error as the pre-RM36 `genome_build` blindness and
the thing a dedup key must never do. The test that pins it
(`test_a_different_curator_is_still_different_content`) fails on the pre-fix code for that reason, not
for the round-trip one.

**Not touched, deliberately: `priority`.** `reverse_module` refuses to infer a default for it, and
that stays right — `Defaults.priority` is `None`, so inferring from the mode would fabricate a value
for rows that never set one, turning `['high', None]` into `['high', 'high']` on recompile. Resolving
defaults before hashing handles `priority` correctly *by the same rule* (its model default is `None`,
so an unset one stays omitted) without needing reverse to change its mind.

## RM38 — A cache for every gated source (the hosted enricher)

**Severity** medium · **Status** ✅ **shipped in `just-dna-enricher` 0.5.1** (2026-08-07) · **Owner**
enricher · **Motivating case** the marketplace's hosted `POST …/check?pgx=true` surface

The entry below is kept as it was filed, because the survey in it is the reasoning worth not
re-deriving; what shipped is recorded against it at the end.

**Why 0.5.1 and not 0.6.0.** Two independent reasons, both worth recording so the next reader does not
file the number as an error:

- *It is legal there.* The 0.6 table above sorts items by **digest legality** — it is about the
  format/compiler schema surface, where a new column moves every compiled module's identity. RM38 touches
  no parquet, no model and no manifest field. It is confined to `just-dna-enricher`, which is a separately
  versioned package: all three sit at 0.5.0 in the uv workspace, publish independently, and the enricher
  depends on the other two by `>=`. So the network tier can take a patch release with format and compiler
  untouched.
- *It is wanted there.* The cache is what unblocks a deployment, and 0.6 is schema work (RM23, RM24,
  RM25, RM16, RM28 — all new tables). Coupling an enricher fix to a schema minor would be the tail wagging
  the dog.

**What differs between a host and a service.** An author running the enricher on their own machine
accepts the source's terms themselves, spends their own rate budget, and holds their own PharmVar key.
That case needs nothing. A hosted enricher is a different act for two reasons that are worth keeping
apart, because either alone justifies the cache and they have different consequences: the operator's
acceptance and *personal, non-transferable* PharmVar key stand in for every end user's (there is no
per-user switch — the key's presence in the environment *is* the switch), and every published rate figure
is **per IP**, so a server multiplies its callers onto one allowance rather than getting one each.

**Current state, so this is actionable as written.** The gated set is exactly the three PGx sources — the
only `licensing.TERMS` entries with `commercial_use=False`; Ensembl, ClinVar, gnomAD and ClinGen are all
`True` and already snapshot-first, so resolution needs no change at all.

| Gated source | Builder | `locations` resolver | `download.ensure_*` | Publish | Runtime pass |
|---|---|---|---|---|---|
| **ClinPGx** | ✅ `clinpgx_build.py` | ❌ | ❌ | ❌ | `clinpgx.py:164-169` — skips silently when `snapshot=None` |
| **CPIC** | ❌ | ❌ | ❌ | ❌ | `pgx.py`, `pgx_draft.py` — always live |
| **PharmVar** | ❌ | ❌ | ❌ | ❌ | `pgx.py` — always live |

`pgx.py:162-167` makes `--offline` a no-op that warns and returns; `pgx_draft.py` has no `offline`
parameter at all. `locations.py` knows three caches, `download.py` fetches those same three, and
ClinPGx's snapshot is orphaned from all of that plumbing.

**This is demand, not speculation.** `just-dna-marketplace` reaches all three live, per request, from
`services/enrich.py`, on a deployment where self-registration is open and the only requirement is
`PUBLISH` on a namespace one proof-of-work away. Its own API reference already states the consequence —
that a public deployment means third parties query PharmVar on the operator's account — and its enrich
service already comments that the passes are skipped offline because there is no PGx snapshot to fall
back on the way resolution falls back to Ensembl/ClinVar. It has also already hand-built the workaround
for the one source that *has* a snapshot: a `clinpgx_snapshot` setting, skipped with a message naming
`just-dna-enricher clinpgx build`. RM38 generalizes a pattern a consumer already needed.

**The shape, following ClinVar/constraint exactly.** `cpic_build.py` and `pharmvar_build.py` (`[dev]`,
polars, guarded import) → `data/*.parquet` + `release.json`. `locations` gains `CPIC_SUBDIR` /
`PHARMVAR_SUBDIR` / `CLINPGX_SUBDIR`, the matching `default_*_cache_dir` and `resolve_*_reference`, and
the `$JUST_DNA_{CPIC,PHARMVAR,CLINPGX}_CACHE` overrides. Runtime passes read with **duckdb** — the house
convention is builder in polars, runtime pass in duckdb, and it is what keeps the declared dependency set
honest about what the runtime needs. `--offline` becomes real for `pgx` and arrives on `draft`. The
snapshot route records which release answered in `dataset`, the way the two gnomAD constraint routes
already do, so a module can say whether a live API or a pinned file gave it the answer.

**Three things it must not do**, each for a reason that is the actionable part of this entry:

- **No PharmVar publish.** Recorded terms permit redistribution for all three, so ClinPGx and CPIC can
  follow the full build → publish → `ensure_*` path. PharmVar cannot: bulk data pulled under a personal,
  non-transferable key is not covered by any axis the terms record, and an unestablished permission is
  never a permission (`None` ≠ `False`, the same rule as `share_alike`/`commercial_use`). It stays
  operator-built and inject-only.
- **No new `SourceRow` column** for research-use-only or personal-key. PharmVar's restriction is
  genuinely narrower than `commercial_use=False` and today lives only in `notice` as prose — but a new
  column on an existing parquet moves every compiled module's digest, so it is **1.0**, not a minor. It
  is surfaced here and belongs to the RM27 design round, which already owns "the recorded axes do not
  cover every real restriction".
- **No second CLI flag.** `--offline` is the switch and an explicit `--snapshot`/`--*-cache` path is the
  inject-only escape hatch. A `--use-snapshot` would be the second flag the `ensure_*` shape exists to
  avoid.

**Two prerequisite defects found while surveying**, worth fixing on the way through rather than leaving
for the next reader to rediscover:

- `upload.py`'s snapshot allow-patterns are `data/*.parquet`, `citations/*.parquet` and `release.json`,
  so publishing a ClinPGx snapshot would **silently drop its `LICENSE.txt`** — the pinned-licence design
  is the entire reason that file is extracted from the archive. Any share-alike snapshot publish needs
  the licence to travel with the bytes.
- `clinpgx.py:36` imports `RELEASE_FILENAME` **from the `[dev]` builder** `clinpgx_build.py`, and
  `clinpgx_build.SNAPSHOT_DIRNAME` is dead code referenced nowhere. `acmg.py:83-85` documents this exact
  inversion as the thing to avoid; a layout constant belongs in `locations`, where the
  builder/publisher/provisioner/reader rule already puts the others.

### What shipped, against the plan above

Every item, and the plan held. `cpic_build.py` and `pharmvar_build.py` (`[dev]`, polars, guarded
import); `locations` gained `CPIC_SUBDIR`/`PHARMVAR_SUBDIR`/`CLINPGX_SUBDIR`, their `default_*_cache_dir`
and `resolve_*_reference`, and the three `$JUST_DNA_*_CACHE` overrides; `download.ensure_cpic_snapshot`
and `ensure_clinpgx_snapshot` (**and no `ensure_pharmvar_snapshot`**); duckdb snapshot clients
duck-typed against the live ones, so `enrich_pgx`/`draft_gene` needed no branch; `--offline` became real
for `pgx` and arrived on `draft`; the snapshot's release lands in `dataset`. Both prerequisite defects
were fixed on the way. Sizes, measured rather than estimated: the whole CPIC database is **256 KB** of
zstd parquet (132 genes, 120,778 rows) and PharmVar is **36 KB** (15 genes, 1,173 alleles).

Five things worth recording that the plan did not anticipate:

- **A `cache` command group, because the plan described plumbing and not an operation.** `cache status`
  and `cache pull` are what an operator actually runs, and having no single entry point would have left
  the documented provisioning step as a Python snippet per snapshot. `pull` gates the two sellable-
  forbidding snapshots on `--use` for the reason the rest of the tier does: under a data-usage policy the
  terms are accepted when the data is **taken**, and a download is taking it.
- **`clinpgx` provisions automatically; `pgx` and `draft` fall back to live.** The asymmetry is not
  inconsistency — ClinPGx has no live route at all (`api.pharmgkb.org` was retired), so there is nothing
  to degrade to, while pulling a whole database to answer one gene would be the wrong default for an
  author on a laptop. Neither adds a second flag.
- **`offline` outranks an injected client, decided on the type.** An injected client is the inject-only
  escape hatch, but a *live* one under `--offline` would egress from a run documented as making none,
  which is the failure this item exists to close. A snapshot client is exempt because reading a local
  parquet is not egress. Deliberately not decided on `configured`: a live client with a perfectly good
  key is exactly the one that must not be used.
- **PharmVar's coordinates were wrong, and only a snapshot would have shown it.** PharmVar publishes each
  defining variant against **both** assemblies and lists GRCh37 first, and `_merge_variants` was
  first-wins over any `NC_` row — so **451 of 739** rsID-keyed defining variants carried a GRCh37
  position. It had never bitten because nothing consumed `PharmVarAllele.variants`; a snapshot stores
  them, which is what turns a latent wrong number into a written one. The accession *version* cannot
  separate the two (chr10 is `.10`/`.11`, and so is chr22) — `referenceCollections` can, exactly. Fourth
  build confusion in this workspace, hence `pharmvar.PHARMVAR_GENOME_BUILD` as a named constant, on the
  `gnomad.FREQUENCY_GENOME_BUILD` precedent. The test fixture carried only a GRCh38 row, which is the
  corpus-uniformity lesson again: it now carries both, in the order the real payload uses.
- **CPIC does publish a chromosome, and the old comment saying otherwise was a probe artefact.** The
  2026-08-03 probe read `sequence_location` alone — which genuinely has genesymbol/dbsnpid/position and
  no chromosome — and concluded CPIC has none, so `pgx_draft` skipped every defining variant CPIC gives
  no rsID for: 18 in CYP2C9, 14 in TPMT, 4 in NUDT15. `gene.chr` carries it (`chr10` for CYP2C9), and
  joining on the symbol the location row already names is a lookup in CPIC's own tables rather than the
  inference that probe rightly refused. `draft --gene CYP2C9` now writes 17 coordinate-only haplotype
  rows it used to drop, and the module validates. The general lesson is the one already in this file
  under a different name: **a negative finding about a source is only as wide as the table you looked
  at** — say which table, so the next reader knows what was not checked.

## RM39 — one pass in the family ignored `offline`

**Severity** low · **Status** ✅ **shipped in `just-dna-enricher` 0.5.1** · **Owner** enricher ·
**Motivating case** a `just-dna-registry` field report

Every other pass took `offline: bool` and degraded on it; `clingen.enrich_dosage_sensitivity` did not,
and downloaded ClinGen's curation TSV unconditionally. The only way to stop it was to inject
`curation_text=`, which requires the caller to have fetched the thing already — i.e. to have solved the
problem the parameter would solve. The `dosage` command had no `--offline` either, so the asymmetry was
user-visible.

**The cost is not the flag, it is the shape.** ENRICHER.md documents `--offline` as *clamps to local
caches / sidecars*, and a consumer advertises the same guarantee, so a caller running the family under
one switch had to know out of band that one member did not honour it and hoist a `if not offline:`
around that call specifically. The failure mode of forgetting is **silent egress from a path documented
as having none** — and it is a guard every consumer has to re-derive.

`enrich_frequencies` was the model: online-only, `--offline` makes it a **no-op with a warning**,
reported as `skipped_offline`. That is a first-class answer a caller can render (*"the dosage pass did
not run because this deployment is offline"*), and it is different both from "it ran and found nothing"
(`missing`) and from a failure. `ClinGenResult` now carries the same field.

**An injected `curation_text` still wins, deliberately** — handing over bytes you already hold is not
egress, and refusing it would break the inject-only escape hatch every pass in this tier keeps.

**Not done, and it was asked for explicitly: a ClinGen *snapshot*.** That is RM38's family and a much
bigger question. This was only about the flag meaning the same thing in every function that takes one.

## RM40 — VRS coverage was computed and thrown away

**Severity** low · **Status** ✅ **shipped in `just-dna-enricher` 0.5.1** · **Owner** enricher ·
**Motivating case** a publish dry run that wants to report coverage before compiling

`vrs.mint_resolution_rows` returns a `MintResult` carrying exactly the two numbers `compile_module`
later stamps into `manifest.compilation.vrs_alleles` / `vrs_alleles_identified` — plus
`unmintable_reasons`, the grouped-by-reason breakdown that is the *actionable* half — and `enrich()`
logged `coverage_warnings()` and dropped the object.

**Why that is a defect rather than a missing convenience.** The whole point of the coverage counters is
that a consumer can *read* the reliability of the identity scheme instead of inferring it. A consumer
that wants to read it **before** a compile — which is what a publish dry run is — could not, so it
re-implemented the counting over `EnrichmentResult.rows`, and had to get two non-obvious rules right to
agree with the manifest a publish would produce: count per **ALT slot**, not per row, because `vrs_id`
is a parallel array of `alts`; and treat an *absent* cell as `len(alts)` unnamed slots rather than zero
slots, or a table where nothing minted reports flawless coverage out of a denominator of nothing. Both
are in `MintResult`'s own docstring, and a consumer reading only the field list gets the second one
wrong in the direction that reports a problem as a success — the exact failure the two-counters-not-a-
ratio design exists to prevent.

**And the reasons were unreachable at all.** `unmintable_reasons` is where *"no refget table for build
'GRCh37'"* and *"needs the reference sequence"* live — the difference between a finding an author can
act on and one that is the tier's own limit, which is the distinction the verify pass's three-outcome
table is built on. As a log line, a service reporting to a publisher over HTTP could show the shortfall
and not the reason for it.

`EnrichmentResult.vrs: MintResult | None`, populated when `mint_vrs=True` and `None` when the pass did
not run — `None` ≠ a coverage of zero, the house rule. Purely additive: a dataclass field with a
default, no behaviour change, no signature change.

## RM41 — the only correct CSV loader was private

**Severity** low · **Status** ✅ **shipped in `just-dna-compiler` / `just-dna-enricher` 0.5.1** ·
**Owner** compiler + enricher · **Motivating case** a consumer wiring the 0.5 pipeline server-side

Two checks take rows rather than a spec directory — `acmg.verify_acmg_sf` and
`identifiers.check_identifiers` — unlike every other pass. So a caller had to turn `variants.csv` into
`VariantRow`s itself, and the only thing that does that correctly was
`just_dna_compiler.compiler._load_csv_rows`, which was private. This workspace's own enricher CLI
reached across the package boundary for it in both `check-acmg` and `check-identifiers`, which is the
definition of de-facto public.

**Re-implementing it is a trap rather than a chore.** It is not `csv.DictReader` plus `Model(**row)`:

- **an empty cell becomes `None`, and the key is kept.** `MeasureBinRow.measure_kind` has a default, so
  `is_required()` is `False`, but the model then receives `None` rather than its default and **fails on
  type**. A `""` where the loader would have put `None` is a different failure again.
- **`genome_build` is told to each row, not read from it.** A pydantic model built from a CSV dict has
  no `module_spec.yaml` in scope, so a loader that does not inject the module's declared build mints
  GRCh38 identities for a GRCh37 module — the exact bug `_restamp_for_build` exists to fix, one layer up.

Both halves shipped, as the entry preferred. `compiler.load_csv_rows` is public (`_load_csv_rows` kept
as an alias, so nothing breaks); `compiler.load_spec_variants(spec_dir)` does the yaml read, the
injection and the re-stamp in one call; and both checks accept `spec_dir=` beside the existing
`variants=`. **Exactly one, never both** — a caller passing both has two answers in mind and only one is
right, and silently preferring either is the guess this tier does not make anywhere else. The row-taking
form stays: it is the right thing for an in-process caller that already holds the rows.

This is the one item that touches the **compiler**, which is why 0.5.1 is a two-package cut. Nothing in
the format tier changed, and no parquet, model or manifest field moved.

## RM42 — the retry ceiling was an import-time constant

**Severity** low · **Status** ✅ **shipped in `just-dna-enricher` 0.5.1** · **Owner** enricher ·
**Motivating case** an unattended server-side publish

Nine clients retry with a sound policy — tenacity, exponential jitter, on transport errors and the two
clients' own rate-limit exceptions, and (the part that makes this safe to touch at all) **paced before
the retry**, so an extra attempt spends a slot of the published budget rather than bursting past it.
What a caller could not do is choose *how many*: the policies were `@retry(stop=stop_after_attempt(3))`
— or `(4)` for gnomAD and eutils — evaluated at import, with no parameter, setting or variable.

**One number cannot serve both callers.** Three attempts is right for the audience the CLI was written
for: an author at a terminal who would rather see a failure in ten seconds than wait out a flapping
upstream. It is wrong for the other deployment shape the 0.5 tiering created — a **server** running
`enrich()` inside a publish. That work is unattended and already queued, nobody is watching a spinner,
and giving up on a transient 502 does not cost ten seconds: it costs the publisher a whole re-upload of
a module the server had already accepted, validated and dedup-checked. Two callers wanting opposite
things from one constant is the definition of a knob.

`net.attempt_floor(default)` is a tenacity `stop_base` that resolves per call, reading
`$JUST_DNA_HTTP_RETRY_ATTEMPTS`. Two shape decisions, both from the entry and both kept:

- **A floor, not a setting per client.** The per-client differences are deliberate — gnomAD and eutils
  are at 4 because their budgets are tightest — so a single number that *raises* everything to at least
  `n` preserves that tuning, where one that *sets* it would flatten it. Below a client's own default it
  is a no-op: there is no deployment that wants *less* persistence than an author at a terminal, and
  allowing it would turn one variable into a footgun.
- **Leave a composed `stop` alone.** `stop_after_attempt(3) | stop_after_delay(60)` means both, and
  raising one term silently changes a policy whose author meant the conjunction. None of the nine is
  composed today; the rule matters the day one is, so only bare `stop_after_attempt`s were replaced.

What this replaces on the consumer side is a walk over the package reassigning `policy.stop` — which
worked, and was pinned by a test, and was still a consumer reaching into another package's decorator
state to change behaviour its author had not exposed. That is what an RM is for.
