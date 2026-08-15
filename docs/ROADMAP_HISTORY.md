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

## RM44 — `fully_resolved` answers a question nobody asked it, and prose is the only record of the real one

**Severity** low (one additive field) · **Status** ✅ shipped in 0.6.0 · **Owner** format (manifest) +
compiler · **Motivating case** a catalog served `trusted: true` for modules that annotate nothing
(S13 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md))

`manifest.compilation.fully_resolved` is `all(...)` over `variants.csv`, so on a module without one it
is `all()` over an empty list — **vacuously `true`**. The field is not wrong; it answers its question
correctly. It simply cannot say *which* question it answered, and the trust rule its own field comment
documents (`resolution_mode == "strict" or fully_resolved`) reads it as a module-level verdict. A
consumer followed that comment and shipped it: `just-dna-registry` granted its `trusted` badge to
`pgx_slco1b1_simvastatin` and `cyp2c19_star_alleles`, both of which join to no VCF, and needed a
migration to repair the stored projection.

**The workaround is the finding.** There is no structured field saying a table joins to nothing, so the
only record surviving into a catalog is the 0.5.3 warning's *prose* — `compile_module` copies its
warnings into `manifest.compilation.warnings`, and a reindex has no spec directory left to re-derive
from. The registry pins `UNJOINABLE_MARKER = "have no chrom+start"` and substring-matches it to decide a
badge. Confirmed from this side: the phrase reaches `manifest.json` verbatim for both modules and is
absent for a module whose core resolves. That sentence is now load-bearing, which is a bad place for a
sentence to be; `compiler.UNJOINABLE_PHRASE` names it and a test pins it, so a reword breaks this build
rather than their catalog, but that is a splint, not a fix.

**The fix is one additive integer on `Compilation`** — `resolution_subjects`, the count of rows
resolution was actually applied to, i.e. the denominator `fully_resolved` quantifies over. Then
`fully_resolved=true` beside `resolution_subjects=0` is self-evidently vacuous with no prose anywhere
and no new vocabulary. This is the same "keep the parts, compute the convenience" pattern as
`vrs_alleles`/`vrs_alleles_identified`, whose comment already argues it in as many words — *"Both `0`
means no resolution table was present, i.e. nothing was attempted, which is not the same as nothing
achieved"* — and the argument was simply never applied to the flag sitting beside it. Additive, and a
manifest field was never inside `artifact.digest`.

**Two things not to do.** Do not make `fully_resolved` tri-state or `None`-able: it is typed `bool`,
consumers branch on it directly, and that is a breaking read for everyone to fix a case an additive
sibling describes better — the reporter asked explicitly for this not to happen. And do not treat the
counter as a substitute for **RM43**: it makes the vacuity visible, it does not make the tables
joinable.

**Open design question, worth settling with S8 rather than alone:** one counter or two. The denominator
of `fully_resolved` (variants in scope) is the cheap, self-evident half. A second count — table rows
that cannot be joined — is what the prose actually carries today, and it overlaps the structured
`checks_run`/`checks_skipped` record S8 asks for. Deciding them together avoids shipping two shapes for
one question (P5). **Settled in [RM45](#rm45--the-manifest-is-rich-about-resolution-and-silent-about-verification-so-unchecked-and-clean-are-one-state-to-a-downloader): three separate things, three homes.**
The denominator is this item's, and it is not blocked by RM45; the unjoinable-row count belongs with
RM43's warning; neither is a member of a verification-checks map, because resolution is not a
verification pass and folding a row count into "which checks ran" overloads that map's axis (P5).

**Shipped as `Compilation.resolution_subjects` (0.6.0).** Counted **after** the one-to-many rsID
expansion, because that is the list `fully_resolved` iterates — `pathogenic_clinvar` authors 328 rows
and resolution applies to 337 loci. Five of the eleven reference examples report
`fully_resolved=true, resolution_subjects=0`, which is the vacuity, now legible without prose.

**One thing the item did not anticipate, recorded so nobody re-derives it: the number was already
present as `Stats.weights_rows`.** Measured, the two are equal on every reference example, because
the materializer emits one weights row per in-scope variant row. It was still right to publish the
counter — that equality is a property of the current transform rather than a contract, and `Stats` is
documented as *card/detail display facets*, so a consumer keying trust on it would be keying on a
coincidence in a block that promises none. A denominator belongs beside the flag it qualifies. A test
pins the two together, so a divergence is a decision rather than a drift. The general lesson is the
narrower one: **before adding a computed field, check whether some other block already carries the
number, and if it does, say why the new home is the right one.**

The two "do not"s held: `fully_resolved` is still `bool`, and `UNJOINABLE_PHRASE` and its pinning
test both stay — this makes the vacuity visible, it does not make the tables joinable (RM43).


## RM49 — a spec directory is flat, so a legible `derived/` layout is one the compiler refuses

**Severity** low-medium (a presentation gap with a working workaround; the reporter's own layout is
transport-only because of it) · **Status** ✅ shipped in 0.6.0 · **Owner**
compiler (path resolution) + enricher (where it writes) + format (any shared constant) ·
**Motivating case** a registry giving publishers a readable spec tree, then finding a downloaded module
does not recompile where it sits (S26 in [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**The ask is narrow and reasonable.** Nothing in a spec listing says which files a human wrote and which
`just-dna-enricher` produced — `module_spec.yaml`/`variants.csv`/`studies.csv` against `resolution.csv`
and the four fact tables, with `sources.csv` genuinely both. A `derived/` subdirectory says it at a
glance. The compiler resolves authored and derived tables at the spec root **and only there**, so that
tree is one `compile` refuses; the reporter flattens on upload and re-splits on download, which works and
means the layout can never be more than presentation. They ask for a *tolerated* input location, not a
required one. The byte-attestation half of S26 shipped in 0.6.0 (`manifest.derived`); this is the half
that did not.

**Why it is not the one-line change it looks like.** `spec_dir / "resolution.csv"` is resolved in **eight
places across two packages** — `validate_spec`, `compile_module`'s resolution and fact-table loops, and
four enricher passes (`enrich`, `frequencies`, `identifiers`, the CLI's inspect path) — so a fallback
added in the compiler alone gives a module that compiles from `derived/` and silently re-enriches to the
root. That is the `locations` failure mode exactly: four parties must agree on a layout, and every
disagreement there so far has been silent.

**The decisive argument, and the reason this is a design round rather than a fix.** Tolerating the layout
on *input* without deciding the *write* side is incoherent, and it breaks on first use: run `enrich` on a
downloaded split module and the enricher writes `resolution.csv` to the root, so the module now carries
both `derived/resolution.csv` and `resolution.csv` — the collision case, reached by following the
documented workflow rather than by misuse. Any acceptable design answers where the enricher writes when
a `derived/` already exists, and what happens when both copies are present and disagree. Note that a
collision cannot be resolved by "newest wins" or by merging: these tables are fact-hashed and
human-overridable, so two copies are two legitimate claims and picking one silently discards a curator's
override.

**Three candidate repairs, and why each is wrong:**

- **Search any subdirectory** (what the registry does on upload). Wrong here: it makes the compiler walk
  the tree, and both S16's unknown-file tolerance and `_check_misspelled_tables`' near-miss guard assume
  one level — a typo'd `derived/varaints.csv` would be invisible to the check written precisely to catch
  that, so the feature would re-open the hole a previous item closed. A single fixed directory name is
  the only version that keeps the guard meaningful.
- **Make `derived/` canonical** — `reverse_module` emits it, the enricher writes it. Wrong: P3 keeps the
  flat spelling working as an alias regardless, so this buys two supported layouts instead of one and
  makes `reverse` emit a tree older compilers in the same major cannot read. A layout migration is a
  major-version move dressed as a convenience.
- **Extend it to the authored tables too**, for symmetry. Wrong, and it is the tempting one: the authored
  CSVs are what `content_signature` reads and what the human-authorable gate is about. Two legal
  locations for `variants.csv` means a module can carry two, and the one the compiler ignores is invisible
  — the silent-success shape this codebase treats as the worst kind of mistake. The asymmetry is the
  point: only machine-written tables move, because only they have a machine that knows where to put them.

**What a shipped version probably looks like**, recorded so the next pass does not re-derive it: one
constant naming the directory, in the **format** tier so both consumers import rather than copy it (the
`locations`/`README_CANDIDATES` precedent); a shared resolver that prefers the root and falls back to the
subdirectory; an **error, not a warning**, when both exist, naming both paths; and the enricher writing
beside whichever copy it read. No new CLI flag — the layout is discovered, not declared.

**Shipped in 0.6.0, in the shape the item predicted**, and it shared its whole mechanism with RM51 —
which is the reusable part: *"the same table in two possible places"* is one problem whether the two
places differ by name or by directory, and it wants one resolver, one collision rule, one write rule.
Doing them apart would have written that resolver twice.

`just_dna_format.layout` holds `DERIVED_SUBDIR`, the resolver, and the write-path rule. Two additions
to what the item recorded:

- **`_check_misspelled_tables` had to learn the subdirectory**, against the *derived* name set alone.
  The item argued that "search any subdirectory" is wrong because it blinds that guard; the same
  argument applies to a single fixed name if the guard is not extended to it, which the first draft
  of the change missed. An authored table name inside `derived/` is itself the near miss worth
  reporting rather than a file to accept.
- **`manifest.derived` records the relative path**, so `FileEntry.name` carries `derived/…`. That
  needed no change to `integrity.file_entries`, which already joins the name onto the directory — and
  it is legal only because that block is documented transport-only and outside `artifact.digest`.

Verified through the CLI rather than in-process: a real module in the split layout compiles to the
same `artifact.digest`, `content_signature` and `resolution_signature` as flat.


## RM51 — `licensing.csv`: land the better name in a minor so the major only has to remove

**Severity** low (legibility; nothing is broken today) · **Status** ✅ shipped in 0.6.0 · **Owner** compiler (one resolver above `_FACT_TABLES`) +
enricher (five write sites) · **Motivating case** the maintainer, 2026-08-12, after SCHEMAS.md needed a
three-row table to explain which of `studies`/`literature`/`sources` is which

**The move.** Accept `licensing.csv` as a second spelling of `sources.csv` now: the enricher writes the
new name, the compiler resolves the old name first and falls back to the new one, and nothing else
changes. Every existing module keeps compiling, and by the time 1.0 arrives every module drafted under
0.6+ already carries the new name — so the major has to **remove** a spelling rather than **add** one,
which is the difference between a rename people notice and one they do not. The old spelling is
**deprecated in the same 0.6 release** (warn-only, still fully read) and **removed at 1.0**, which is
the cadence the 0.6 charter amendment settled — and this item is the case that prompted it. See
[§ 1.0 cleanup — `sources.csv`](ROADMAP.md#sourcescsv--the-name-and-the-source-column-it-collides-with) for the
name argument itself and for the half that cannot come along.

**Why it is minor-legal, checked rather than assumed.** `sources.csv` is deliberately **not** in
`_INPUT_FILES` (`compiler.py`) — the fact sidecars are excluded there because their identity is the
fact hash, not the raw bytes — so the *filename* enters no identity at all: `content_signature` is over
authored rows, `source_signature` over `SOURCE_FACT_FIELDS`, and `manifest.derived` (S26) records
whichever name it found and is documented as transport-only, outside `artifact.digest`. A second
accepted name is therefore additive in the plain P3 sense: existing modules keep validating and no
published artifact moves.

**What does *not* come along, and this is the cost to accept knowingly.** `sources.parquet` is in
`_OUTPUT_FILES`, hence inside `artifact.digest`, and consumers read it by name; `manifest.sources` is a
published key. Renaming either breaks a reader, so both are major-only. For the whole 0.x tail the
module therefore reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is a real
legibility regression against today's single consistent (bad) name, and it is the price of not paying
for the rename twice.

**The one open decision: both files present.** This is RM49's collision in another file, and it must
not be hand-waved the same way. Two copies are two legitimate claims — the table is fact-hashed and
**human-overridable**, so "newest wins" or a merge silently discards a curator's override. The rule to
implement is RM49's: the enricher **writes to the file it read**, creates the new name only when
neither exists, and both-present is an **error naming both paths**. Note `pgx.py` writes
`spec_dir / "sources.csv"` directly while the other four sites go through `record_source_terms` — that
one has to move onto the shared resolver, or it re-creates the retired name behind the alias's back.

**Mechanics, so the next pass does not re-derive them.** The resolver sits **above** `_FACT_TABLES`,
because `_DERIVED_FILES`, `_OUTPUT_FILES`, `_check_misspelled_tables`' name set and both load loops are
all derived from that tuple and must see the alias uniformly (adding the name also, correctly, stops
the near-miss guard flagging `licensing.csv`). `draft.DRAFTABLE` is keyed on the filename and gains the
new key while keeping the old. And the S26 reporter's registry splits and flattens a spec directory
against its own copy of the derived-file list, so it needs telling in the same release.

**Shipped in 0.6.0.** The design was settled apart from the collision rule, and the collision rule
turned out to be RM49's, shared verbatim — both items are "the same table in two possible places".

**The one estimate that was wrong: five enricher write sites, actually nine.** `record_source_terms`
and `merge_sources_file` now take the **spec directory** rather than a path, so no pass can name a
spelling by hand — which is the durable form of the fix, since a count is exactly the thing that goes
stale. The item was right about which one was awkward: `pgx.py`, the only pass whose primary output
is this table and the only one calling `write_sources_csv` directly.

Four reference examples moved to the new name; `hfe_hemochromatosis` deliberately keeps the old one
so the deprecation path stays exercised on a real module rather than only in a fixture. All eleven
kept their exact `artifact.digest`, `content_signature`, `resolution_signature` and `source_signature`
across the rename — which is the measurement behind "the filename enters no identity", made rather
than argued.



# 0.6.0 — the design round, built

**The whole of [PROPOSAL_0_6.md](PROPOSAL_0_6.md)'s decision list, implemented.** Sixteen items were
argued to a decision on 2026-08-13 — each with the facts probed, the repairs rejected and why, and the
consequences that follow without being chosen — and the eleven that build are below with their original
entries intact. The proposal stays the reasoning document; these are the outcomes, and where the two
disagree the note at the top of each section wins, because several of these entries were written before
the decision and describe a shape that was rejected.

**Landing them cost one charter amendment, which went first and alone.** The Constitution ruled on
whether a change was *legal* and said nothing about what a legal change *cost*, and the absence kept
surfacing as an instinct that there were "too many tables" — right about some additions, wrong about
others, with no stated way to tell which. A schema addition now costs what its layer costs: a parquet
column is approximately free, a derived CSV is half, an authored schema is full. Four of the decisions
below turn on it, and two obviously-worth-building items (RM24, RM25) had looked like creep only because
a machine-written sidecar was being priced as though a human had to learn it.

**The VCF 4.4 cluster shipped with them.** RM53–RM65 came from [VCF_4_4_AUDIT.md](VCF_4_4_AUDIT.md), a
full read of the specification against the schema, and they are not repeated here as sections because
the audit remains their evidence document. Their through-line is worth stating once: *the schema named
a VCF field by a bare token, and a VCF field is not identified by its name* — it is identified by
namespace (INFO and FORMAT collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and, new in 4.4, `CN`) and
described by cardinality. Both readings of a colliding key are usually type-compatible, so nothing
detects the confusion: a consumer reads a well-formed number of the wrong kind. Two shipped reference
examples were wrong on exactly this and were re-authored, which is why `mt_heteroplasmy` and
`htt_repeat_expansion` are the only two modules in the corpus whose `content_signature` moved across
the whole batch.

**What the batch cost the corpus, measured rather than assumed.** Across all eleven reference examples:
`content_signature` moved on **two** (the two re-authored above), `artifact.digest` moved on **seven**
(new optional and stamped columns — Principle 4 scopes byte-reproducibility to a fixed
`compiler_version`), `resolution_signature` **gained** a value on the four table-only modules that
carry a `resolution.csv` and no `variants.csv`, which is precisely the hole RM45 closed, and the source
signature moved nowhere. The suite went from 1535 to 2046 tests.

**One pattern showed up three times independently and is now a rule in CLAUDE.md.** Three separate
lanes shipped the same defect and each was caught by its own code review: a check re-run after
resolution counts the *expanded* rows, so an rsID that resolves to several loci produces the same
finding twice with different numbers, message-dedup keys on the sentence and cannot collapse them, and
both reach `manifest.compilation.warnings` — a published field contradicting itself. Measured at
"1 row(s)" beside "2 row(s)", and at 328 beside 337 on `pathogenic_clinvar`. The rule covering it and
its opposite: **re-run a check after resolution exactly when resolution changes its input, and never
when the message embeds a count.**

## RM4 — Native ClinVar gene-panel materialization

✅ **Shipped in 0.6.** Compile-time materialization was dropped rather than built: the mechanism is enricher draft-scaffolding, which already shipped, and the author's no-op over the drafted subset is still an authorial act. `panel:` lost its last consumer and is deprecated (removal at 1.0, tracker line filed); `clinvar_draft` now stamps the ClinVar release into the licence row's `dataset`, and `clinical.tautology_reason` keys on that instead of the authored block — both sides calling one shared label function, because a writer and a reader disagreeing about it would not fail, they would silently never match. The hand-edit hole closed on a mode ladder (`strict` audits every row into copied / authored / conflicting / no_record; `best_effort` keeps the cheap skip plus a notice naming the hole). Two findings the round produced: `merge_sources_csv`'s never-clobber rule is right for terms and wrong for a machine-stamped release label, so the label is now *withdrawn* rather than re-labelled when a module spans two releases; and "copied" had to become allele-exact, since a locus-wide match can be a sibling allele's call (`rs334` carries pathogenic `T>A` beside likely-benign `T>G`). The unrelated surface bug shipped with it: `draft-panel` exposes `--download/--no-download`.

**Severity** medium · **Status** deferred to 0.6+ — the injectable-reference half is unblocked ·
**Owner** format (compiler) + consumer-provided reference · **Motivating case** gene-panel modules
(cardio / cancer / pathogenic)

Compile a `GenePanelSpec` (gene set + significance predicate) into `weights.parquet` at compile
time, gated on a **content-pinned ClinVar reference mixin**. The 0.2 `GenePanelSpec` *interface*
ships and is recorded verbatim; the app-level `gene_panel` adapter in just-dna-lite is the interim
reference implementation. Blocked only by Constitution P2 (no network) — the reference must be
*injected*, not fetched. **0.5 update:** the content-pinned reference now exists as an injectable
artifact — `just-dna-enricher`'s ClinVar snapshot (`clinvar build` → `data/*.parquet` +
`release.json` carrying `source_sha256`/`clinvar_file_date`, feeding
`GenePanelSpec.reference`/`reference_sha256`). What stays parked is the *compile-time
materialization* of a `GenePanelSpec` into `weights.parquet`; the injectable reference half is
unblocked.

## RM5 — Symbolic / structural alleles

✅ **Shipped in 0.6.** The five closed VCF first-level types (`DEL`, `INS`, `DUP`, `INV`, `CNV`) with open subtypes, and nothing above them — the `##ALT` declaration mechanism stayed rejected as unasked extendability. **The one question the decision left open, where the length lives, resolved to *inside the token* (`<DEL:1500>`, `<CNV:TR:30>`) on evidence rather than taste**: VCF carries it as `SVLEN`, which is `Number=A`, so a scalar column cannot describe `alts=<DEL:5>,<DUP:9>` and a parallel array is the desync shape `vrs_id` needed two guards for; and three of the columns holding an allele have no row to hang a length on. A length-less symbolic allele is dropped with a warning saying **dropped** under `best_effort` and refused under `strict` — fatal in both modes on the composite tables, where dropping a row makes a quietly *different* module rather than a smaller one. 5-HTTLPR stays a plain indel and CPIC's IUPAC codes stay unexpressible, both deliberately. Carried the docstring fix: `validate_allele` has two users, not one.

**Severity** medium · **Status** deferred to 0.6+ · **Owner** format (schema) · **Motivating
case** 5-HTTLPR, SNP+SV modules, symbolic-VCF consume

A representation beyond `^[ACGT]+$`: `<S>`/`<L>`, `<DEL>`/`<INS>`/`<DUP>`, `<STR n>`, and large
indels. **Motivating cases: 5-HTTLPR** (a biallelic ~43 bp structural indel → Short/Long, *not* a
repeat count; rejected by today's nucleotide grammar and a category error in `repeat_alleles.csv`)
**and ClinPGx's `del`/`ins` genotypes** (177 rows in the release, e.g. `C/del`, `del/del`), which
the PGx passes skip rather than coerce. Also unblocks SV-scale variation and consuming symbolic
VCF alleles (round-2 §1b/3c).

## RM24 — Gene–disease validity as a table

✅ **Shipped in 0.6** as `gene_validity.csv`, a derived fact sidecar with its own signature, manifest block and non-tainting `gene_validity` source layer. **Probing corrected the stated grain twice**: mode of inheritance had to join the key (59 ClinGen gene/disease pairs carry two rows differing only there) and so did `submitter`, because GenCC is a nineteen-submitter aggregate whose *disagreement* is the data and collapsing it would publish one arbitrary verdict as consensus. **HPO ships no route**, a deviation argued in the PR: its licence URL 404s and OBO Foundry records no SPDX id, so its terms cannot be established, and an inject-only tier does not get to assume them.

**Severity** medium · **Status** deferred on the design, not the code · **Owner** format (schema +
compiler) + enricher · **Motivating case** gene-panel triage; lay-language disease naming

(`gene_validity.csv`) — one row per `(gene, disease term, classification, source, dataset)`,
serving **ClinGen** gene-disease validity, **GenCC** aggregate validity and **HPO** gene→phenotype
from one shape. This is a *different grain* from `gene_metrics.csv` (gene × term, not gene), which
is why it is a table rather than more columns; dosage sensitivity went the other way for the same
reason. The cost is the design (getting one shape to fit three submitters' vocabularies), not the
code. All three sources are free, so unlike RM23 this one leaves a module sellable — worth
remembering if the marketplace ever sells modules, since every PGx upstream forbids it.

## RM25 — ClinVar assertion tier as artifact data

✅ **Shipped in 0.6** as `clinical_assertions.csv` — the clinical call, the review wording, the star rating and ClinVar's own VariationID, one row per allele × record. The deciding argument was the house one applied a fourth time: `draft_gene_panel` was already using the star rating as a filter and throwing it away, so every consumer would have recomputed it. A one-star single submission and a practice guideline are no longer flattened to the same `clin_sig`. The cross-check's severity stays parked, deliberately.

**Severity** medium · **Status** deferred as a new table · **Owner** format (schema + compiler) +
enricher · **Motivating case** authorship/assertion-aware scrutiny

A facts sidecar carrying `clin_sig` + `review_status` + `review_stars` + `variation_id` per
variant, so a consumer can route scrutiny by assertion tier at query time (a 1-star submitter and
a practice guideline are not the same claim). Nothing is lost today: `clinical.ClinSigFinding`
**already** reports both fields via its `confidence` property, so this is about persisting the
tier, not discovering it. Deferred as a new table. **Do not confuse this with escalating the
check's severity** — see *Parked in 0.5*.

## RM27 — A redistribution compile gate

✅ **Shipped in 0.6 as record-only, with a named enforcer.** The most-restrictive redistribution verdict is stamped into the manifest and **no gate exists in these four packages** — gating belongs at *publish*, which lives downstream, so the item ships with an explicit ask addressed to the registry in SCHEMAS.md rather than an implication. That is the whole difference from the status quo the item was filed about: a recorded right nobody is told to enforce, versus a recorded right with a named enforcer. `taints_redistribution` no longer describes the design as open.

**Severity** low (after the design) · **Status** deferred — needs the third axis designed first ·
**Owner** format (compiler) + enricher · **Motivating case** OMIM-/dbNSFP-class sources

RM21's gate keys on `commercial_use` + `declared_use`; the 0.5 `redistribution` column is recorded
but **not** gated. Deferred because it is a genuine design question rather than a missing branch:
a redistribution bar is not a *use*, so `declared_use` (`unstated`/`non-commercial`/`commercial`)
is the wrong axis to resolve it against — a module may be built legitimately and still not be
shippable, which is a different verdict from the ones the gate currently issues. Needs the third
axis thought through before code.
## RM43 — Resolution reaches the SNP core only, so a 0.4-led module is rsid-joinable and nothing more

✅ **Shipped in 0.6.** The injected `resolution.csv` is joined onto the three positional kinds before `_build_table` materializes them, in `validate_spec` as well as `compile_module`. Each model gained stamped, parquet-only `variant_key` and `authored_ident`, plus `alts` on `PharmVariantRow`/`HaplotypeRow` filled as **data, not identity** — the key is still derived without it, so the existing "matches at `chrom:start:ref` regardless of allele" contract is unchanged. The reported case closed: `pgx_slco1b1_simvastatin`'s nine rows went from every coordinate null to `12 / 21178615 / T / A,C`. `reverse` rebuilds the lookup table from the positional parquets as a second source, which P7 forces. No `resolution.parquet`. **One deviation worth keeping**: the stamped fields are `Field(exclude=True)`, because declaring them plainly moves `content_signature` on all five positional-table modules — `model_dump(exclude_none=True)` never omits a stamped field, since it is never `None`. That leaves `VariantRow`'s own two inconsistent with the three new ones, grandfathered and filed as a 1.0-cleanup candidate.

**Severity** high (the prerequisites, not the join) · **Status** open — **0.6**, gated on a design
round rather than on a version · **Owner** format (schema) + compiler · **Motivating case** an rsid-authored ClinPGx
module: 1,482 rows, 147 variants, every coordinate null (S9 in
[CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md))

`compile_module` resolves `variants.csv`; every other table goes through `_build_table`, which is
`model_dump()` → parquet. So a module led by `pharm_variants.csv` or `haplotypes.csv` keeps exactly the
coordinates its author typed, which for an rsid-authored one is none — and a VCF is joined by position,
so the table annotates nothing, silently, as an empty result rather than an error. Reproduced on this
tree's own `reference_examples/pgx_slco1b1_simvastatin/`: 9 rows, all null, while the `resolution.csv`
beside the spec resolves the rsID perfectly well. **0.5.3 made it legible** — the compiler now reports,
per positional table, how many rows cannot be joined and how many of those the injected table could
place — but the fix itself is here.

**The obvious repair is illegal as stated, and that is the part worth recording.** "Join `resolution.csv`
on `variant_key` and fill the empty cells" moves more than the digest the reporter expected: materializing
the coordinate and running `compile → reverse → compile` moves **`content_signature`**
(`sha256:8173dab7…` → `sha256:fb91ffa2…`), because `reverse_module` rebuilds the CSV from the parquet and
a filled coordinate returns as an *authored* one. That is exactly what `VariantRow.authored_ident` exists
to prevent, and no 0.4-family model has an equivalent. So the prerequisite is a stamped
"which identity columns did the author supply" column per positional table — a **new column on an
existing parquet** — which is **0.6 work** since the 2026-08-11 charter amendment, so the prerequisite
is a design round rather than a major bump. What stays major-only is nothing here: the item is gated on
doing the stamped-identity design first, not on a version.

Three more constraints found with it, each of which shapes the design rather than merely costing:

- **`PharmVariantRow` has no `alts` column at all.** A filled row can carry `chrom`/`start`/`ref` and no
  allele, so a positional join lands on the locus and allele matching still goes through `genotype`.
  Adding `alts` is a second new column, and it would make the key allele-specific — which
  `_collect_subjects` deliberately avoids ("a pharm annotation matches a variant at `chrom:start:ref`
  regardless of allele").
- **`variant_key` is a *property* on these models**, so it is materialized in no PGx parquet. A consumer
  cannot join a PGx row to `weights.parquet` on it either — which is a second, smaller instance of the
  same complaint and probably wants solving in the same round.
- **The manifest cannot say any of this.** `fully_resolved` is `all(...)` over `VariantRow`, so it is
  vacuously `true` for a table-only module — against the trust rule its own field comment states — and
  `resolution_signature`/`resolution_sources` stay unset, so the injected table leaves no trace.
  Stamping the signature is itself blocked: `reverse_module` rebuilds `resolution.csv` from
  `weights.parquet` alone, so a table-only module reverses to a spec without one and the round-trip
  fixed point breaks. This half is the same shape as the registry's S8 (a manifest that cannot say a
  check ran) and should be decided with it.

## RM45 — the manifest is rich about resolution and silent about verification, so `unchecked` and `clean` are one state to a downloader

✅ **Shipped in 0.6** as `verification.json` — a derived attestation the enricher writes and the compiler reads, stamping `manifest.verification` or dropping it with a warning when stale. Counts rather than booleans and **two fields rather than one union-typed slot**, so "ran against 0 rows" and "did not run" can never share a value; two closed vocabularies rather than free strings, which would have recreated RM44 one level down; bound to the authored bytes with a **~0.4 s median** proof-of-work, one per sidecar per run, found deterministically so the bytes reproduce. Every field is marked untrusted, in the descriptions *and* in SCHEMAS.md, because a forged pass is worse than silence. **A JSON document rather than a fifth fact CSV**: one attestation over many records is a service row in CSV, and it is the one derived artifact whose human-overridability must not be a feature — which is the mechanism the 0.6 charter amendment asks for. The vocabulary audit moved the set twice: `pgx_evidence_level` and `rsid_coordinate_agreement` were genuinely missing, while lane E's two new passes correctly get no member because they adjudicate nothing, and a test pins that exclusion by name. Wiring it up surfaced two pre-existing holes — the reference-allele and clinical checks each had an internal skip returning an empty list indistinguishable from a clean pass, which is S4's defect surviving inside S4's own machinery. `resolution_signature`/`resolution_sources` are now stamped for table-only modules too, unblocked by RM43.

**Severity** medium (a per-version trust signal nobody can build, and no way to triage what was
published unchecked) · **Status** open — **0.6** · **Owner** format (the manifest shape + vocabulary) +
enricher (the only tier that holds the facts) + compiler (the stamp) · **Motivating case** a catalog
that verifies a module's `clin_sig` on its own deployment has nowhere to record that it did (S8 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Confirmed structurally, which is the strongest form this claim can take.** `Compilation`'s twelve
fields carry nothing about verification. `ResolutionRow`'s eighteen columns are all per-*row*
(`status`, `rsid_status`, `rsid_current`). `EnrichmentResult` holds `clin_sig_not_checked`,
`ref_mismatches`, `stale_rsids` and `vrs`, and dies when the run ends. So a module whose authored
`clin_sig` was cross-checked against ClinVar and one where the check never ran ship **identical**
manifests — not by oversight in some path, but because no field exists that could differ.

**This is S4's own argument one level down.** 0.5.2 accepted that an empty `clin_sig_conflicts` meant
both "compared everything, nothing disagreed" and "never compared", and fixed it — on
`EnrichmentResult`. The layer that outlives the run inherited none of it, so the rule holds in process
memory and nowhere else. The same applies to the reference-allele and rsID-currency passes.

**Legality is not the obstacle, and it is cheaper than the usual case.** The manifest was never inside
`artifact.digest`, and a new optional field is additive and minor-legal (P3, amended 2026-08-11) — so
**0.6, not 1.0**. A manifest field that a *publishing authority* stamps rather than the compiler
deriving is also already this schema's shape: `compiled_by`, `namespace`, `owner`, `published_at` and
`canonical_id` are all that. And the reporter's field shape is right for our own stated reasons —
counts rather than bools, and **two** fields rather than one map with a union-typed value, so "ran
against 0 rows" and "did not run" can never occupy one slot. `vrs_alleles`/`vrs_alleles_identified` is
the precedent; the ACMG pass's `checked: 0` is the other.

**Four things the proposal leaves open, which is what makes this a design round and not a patch:**

1. **The check name is a vocabulary, or this is RM44 again one level down.** A `dict[str, int]` keyed on
   free strings lets the enricher write `clin_sig`, a registry write `clinsig`, and a consumer
   substring-match the difference — an unversioned interface, the exact defect RM44 exists to remove.
   The keys want `frozenset[str]` + a validator (P6), and because vocabulary members are permanent
   within a major (P5) the set has to be audited once against the passes that would plausibly join it:
   reference allele, rsID currency, ACMG SF, identifier/trait currency, quote-checking, dosage
   sensitivity.
2. **The skip *reason* must not be free prose either, for the same reason.** Backfill triage — the
   reporter's own second use case — branches on *why* a pass did not run, so `dict[str, str]` of prose
   relocates the substring matching rather than ending it. The reason wants a small closed vocabulary
   (`tautological`, `no_reference`, `offline`, `not_applicable`) with the sentence *beside* it, not
   instead of it: `clinical.tautology_reason` already writes a good sentence and it is worth keeping as
   human detail rather than promoting to a machine key.
3. **The seam has no channel, and that is the actual work.** `resolution.csv` is the enricher→compiler
   contract and carries per-row facts only; "this pass did not run" is per-pass by nature and has no row
   to attach to — the reporter identifies this precisely. Two routes, and choosing is the design. A new
   sidecar the enricher writes and the compiler reads is consistent with every other injected table
   (and would want its own fact-signature), and it gives the workspace a path it can test end to end.
   An argument on `compile_module` is cheaper and is what the reporter proposes, but then the only
   producer is the caller: the format would declare a field its own reference implementation never
   fills, which is how `VALID_SOURCE_LAYERS` ended up with members no file carried.
4. **The trust rule belongs in the schema's own docs, not in the reporter's caveat.** Their point that a
   forged pass is *worse than silence* is right, and it already has a spelling here — `compiled_by`'s
   description says "foreign values are untrusted". Whatever lands must say the same on each field and
   in SCHEMAS.md, or the first consumer to read `checks_run` off an untrusted manifest believes it.

**Recommended shape: option 2, a `Verification` block.** The reporter's own argument for it is the
stronger one and it is the house pattern — `Frequency` earned a separate block because it has its own
producer, its own release and its own fact-hash, and verification has all three. A `clin_sig` check is
only as good as the snapshot it read, so the block wants that release id, and no existing block has a
home for it; `locations.read_release` (0.5.2) is what makes "verified against ClinVar release X" a
sentence this tier can complete at all. Absent on a module nothing verified, which reads correctly as
*says nothing* rather than as a pass.

**It does not subsume RM44.** S13 offered S8 as the superset and it is not one: `resolution_subjects` is
the denominator of an existing flag about *resolution*, which is not a verification pass. Adopting that
framing would park a one-line additive integer behind this whole round.

## RM46 — a literature source's terms are per-article, so the enricher names a source it cannot record

✅ **Shipped in 0.6** as per-article licence columns on the derived literature row, filled from the Europe PMC response the pass already makes and mapped at read time. No `PUBMED_TERMS` constant: a literature source's terms are per-article, and one `pubmed` row would be right for a module citing only ids and **wrong** for one carrying a quote lifted from a CC-BY-NC article — wrong in the dangerous direction, because that quote is publisher text in the module's own annotation layer. Quoting a restrictive article **warns and gates nothing**, on the clinical-cross-check precedent: arbitrating copyright is the same class of overreach as arbitrating a clinical dispute.

**Severity** low as a symptom (a warning on every literature-enriched module), medium as a hole (a
module quoting a CC-BY-NC article has no way to say so) · **Status** open — **0.6** · **Owner**
enricher (`licensing` + `literature`) · **Motivating case** every literature-enriched module warns
about a source the enricher itself introduced (S10 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Reproduced by reading the three pieces.** `enrich_literature` writes `source="pubmed"` into every
`literature.csv` row. `TERMS_BY_SOURCE` has seven members and no `pubmed`, and `record_source_terms`
deliberately *skips* a name it has no terms for ("inventing a row for the rest would be worse than the
compiler's honest warning"). `_source_checks`'s under-declaration branch then names `pubmed` on every
such module. So the tier introduces a source and declines to record it, and the finding lands on the
author. Worth stating precisely, because it bounds the severity: `SourceRow.source` is free text, so an
author *can* hand-write the row and clear the warning. This is not an unclearable finding — it is the
enricher asking the author to write down something only the enricher knows.

**The reporter is right that a `PUBMED_TERMS` constant would be the wrong fix, and this is the part
worth keeping.** A literature source's terms are **per-article, not per-source**: PubMed's *metadata* is
one thing, the *article* belongs to its publisher, and Europe PMC's OA subset spans CC-BY, CC-BY-NC and
bronze. One `pubmed` row would be right for a module that cites only PMIDs and **wrong** for one
carrying a `provenance_quote` lifted from a CC-BY-NC article — and wrong in the dangerous direction,
because that quote is publisher text sitting in the module's own **annotation** layer, which is exactly
where `taints_commercial_use` bites. A row that reads "pubmed, fine" would make such a module look
cleared when it is not, which is worse than today's warning.

**Two other obvious repairs, both wrong.** *Stop writing `source="pubmed"`* — no: `source` is how a
consumer knows which upstream answered, and the existing reasoning for preferring PubMed over Europe PMC
(which "cannot originate a row", since it silently omits ids it does not know) is sound. *Have the
compiler exempt enricher-introduced sources* — no: the compiler would need to hold a list of which
sources a pass introduces, which is a **source convention**, forbidden it since 0.5 (P2) and the exact
mistake RM33 removed. The fix belongs to the tier that both names the source and owns the terms table.

**The shape that matches the facts is the reporter's option 2, and it is the bigger one.** Per-article
terms, either as an additive licence column on `LiteratureRow` (minor-legal) or as `sources.csv` rows
keyed by DOI, plus one decision that is not the enricher's to make alone: whether quoting a CC-BY-NC
article taints the module for sale. That is the *use*-versus-*distribution* axis **RM27** already parks,
so the two want settling together. The tier is closer than it looks: `is_open_access` is already
tri-state on the row, and the pass holds the licence at the moment it would need to record it (Europe
PMC returns `isOpenAccess`; Unpaywall returns a licence id per DOI).

**Interim step, if 0.6 slips:** the reporter's option 1 (a `literature`-layer `pubmed` row for the
*metadata*, plus a documented rule that quoting requires a second `annotation`-layer row for the
article) is defensible — but only if the row's terms are stated as the metadata's and the quoting
obligation is written where an author reads it. Shipped as a bare terms constant it silences the warning
and buys the false clearance above, so it is not a one-liner.

## RM47 — a bin boundary is the most interpretive claim in the format and the only one with nowhere to cite

✅ **Shipped in 0.6.** `MeasureBinRow.pmid` grounds the *boundary* — one optional column on the binning base reaching all four kinds — and `StudyRow`'s subject requirement relaxed so a citation row may name no variant, which only makes previously-*invalid* rows valid. The documented line is **the bin row cites, the citation table describes**, which is what stops `StudyRow`'s provenance column set migrating onto binning rows one column at a time. The same-release obligation was met rather than deferred: `_cross_check_literature` and the enricher's literature pass both read the new site, reached across the tier boundary through new **public** compiler symbols (`load_binning_rows`/`binning_citations`) rather than a private import or a second hand-kept kind list. `htt_repeat_expansion` stays deliberately uncited — the example exists to show the gap.

**Severity** medium (no module is unauthorable, but the claim a reader would most want to check is the
one the schema asks nothing about) · **Status** open — **0.6**, gated on a design round rather than on a
version · **Owner** format (schema) + compiler + enricher (the literature pass) · **Motivating case** an
HTT CAG module whose thresholds had nowhere to record their source (S19 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Reproduced on this tree's own reference example.** `reference_examples/htt_repeat_expansion` compiles
green under `--strict` stating four Huntington thresholds — 26/27, 35/36, 39/40 — with no citation
anywhere in the module, and until 0.5.4 nothing said a word. Its README even says *"a module making a
novel claim should carry its evidence"*, which is advice the schema gave the author no way to take.
`StudyRow` identifies its subject by `rsid` **or** `chrom`(+`start`), and a `repeat_alleles.csv` row is
keyed `(gene, repeat_unit)`, so no study row can name one; `MeasureBinRow` has no `pmid`, `doi` or
`evidence_level`. The requirement is enforced exactly where citations usually arrive for free — a
ClinVar-drafted `variants.csv` — and absent where a human made the judgement.

**One correction to the report, and it narrows the item.** The same does *not* hold for
`heteroplasmy.csv`: it has carried optional `rsid`/`chrom`/`start`/`ref`/`alts` since 0.5.1, so a study
row on the same variant identity points at it exactly, and `reference_examples/mt_heteroplasmy` already
does this. What is genuinely unpointable is the three gene-keyed kinds — `repeat_alleles.csv`,
`copynumbers.csv`, `activity_phenotype.csv` — plus a heteroplasmy row that names only a gene. A second
correction in the other direction: `studies.csv` is *not rejected* in a variants-free module. It loads,
validates and materializes `studies.parquet` today, so an author can ground the module as a whole right
now — the row simply has to claim a variant identity the bin does not have (a bare `chrom=4` for HTT),
and nothing ties it to a bound.

**Shipped in 0.5.4 (the reporter's option 2), and it is the interim, not the answer.**
`compiler._check_binning_grounding` warns in both modes when a binning table states thresholds and the
module records no study rows at all, with the message split on whether the rows *could* be pointed at:
the heteroplasmy shape gets a remedy ("fill the identity columns"), the gene-keyed shape gets the honest
statement that no study row can name one of these bins. That turns silence into a visible decision and
changes no schema.

**Four candidate repairs, and none is a one-liner — which is why this is filed rather than fixed.**

- **`pmid`/`doi` on `MeasureBinRow`.** The smallest schema move (a new optional column on the base
  reaches all four kinds, minor-legal under P3) and the only one that grounds a *boundary*, which is what
  was actually asked for. It is also the largest **wiring** move: `literature.csv`, `_cross_check_literature`
  and the enricher's literature pass all read `StudyRow.pmid` and nothing else, so a bin-row PMID would
  be a citation no existence check, no bibliographic check (S12) and no quote check ever reaches —
  grounding that *looks* verified and is not, which is worse than the honest gap. And it starts the
  drift: `studies.csv` carries population, `p_value_num`, `effect_size` and `provenance_quote`, so the
  first author wanting a quote begins growing `StudyRow`'s column set onto a binning table.
- **A generic `subject_key` on `StudyRow`.** Rejected on the binning tables' own stated rule —
  *multicolumn keying, never a packed tuple*. `HTT|CAG` is a second spelling of an identity the columns
  already spell, it can drift from them with nothing to catch it, and P5 gets a field carrying two axes.
- **Key columns on `StudyRow` plus a new `REQUIRED_ANY_OF` alternative.** Legal — the columns are
  optional, and widening an any-of only makes previously-*invalid* rows valid, so no published module
  breaks. But it grounds at table granularity, not at the boundary: a `(gene, repeat_unit)` study row
  still does not say why 36. Making it say so means putting `measure_min`/`measure_max` on the study row,
  i.e. restating the bin inside its own evidence. It also quietly changes a contract consumers read —
  every `studies.parquet` row today carries an rsid or a chrom.
- **A `bin_evidence.csv` join table.** Keeps one-CSV-one-concern and grounds per bound, but the join key
  *is* the bounds, and they are floats: re-authoring `40` as `40.0`, or moving a threshold, silently
  orphans its evidence with no rule able to notice. A join key that is also the data is the shape to
  avoid.

**So the decision to make is which granularity the format promises** — module, table, or boundary — and
every honest repair costs either a duplicated column set or a duplicated key. Settle that first; the
column follows in an afternoon. Whichever wins, the literature pass and `_cross_check_literature` have to
learn about the new PMID site in the same release, or the format ships evidence it does not check.

## RM48 — an hg19 coordinate has no supported path into a GRCh38 module, and liftover is the wrong primitive

✅ **Shipped in 0.6, and the roadmap's stated blocker was false.** Ensembl runs a permanent GRCh37 REST service serving both dbSNP variants and reference bases, and per-contig lengths for both builds are 25 numbers each — no chain file, no provisioned asset, no new licence, so the scope-back condition never triggered. rs-number recovery only, live-only, reporting and never filling. The offline half (a position past its contig's end, a contig only one build names) went into the **compiler**, in `validate_spec` and `compile_module`, as an **error in both modes** — it is provably wrong, the inconsistent-reference-allele class. The online build-guessing half stayed in the enricher. **The round's sharpest finding was about already-shipped code**: run on a real wrong-build scenario, the existing ±1 neighbour check reported "shifted 1 base to the right" for two rows whose true variants are 228 and 411 bases away — a neighbouring base equalling the authored `ref` is a one-in-four coincidence. The new diagnosis supersedes it, but only from its two strong evidence tiers, since a single-base GRCh37 match rests on the same coincidence.

**Severity** low-medium (an authoring gap with a manual workaround, filed as a longshot by the
reporter) · **Status** open — **0.6**, gated on choosing the primitive · **Owner** enricher (the
recovery link + any provisioned asset) + format (`resolution.csv` provenance) · **Motivating case** an
author curating from older literature with hg19 supplementary tables (S22 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md))

**Not RM15, and the distinction is the useful part.** RM15 is about supporting another build *as the
module's build* — it changes `variant_key` semantics and every coordinate, which is why it is 1.0. What
is missing here is one-way and authoring-time: the module stays GRCh38, only the author's input is
hg19. It re-keys nothing, needs no GRCh37 refget table, and changes no published identity, so filing it
under RM15 would park an additive tool behind a major-version blocker for no structural reason.

**The reporter argues against their own request, and the argument holds.** Trace when liftover is
actually reachable. If the paper gives an rsID, liftover is unnecessary and worse: authoring the rsID
*produces* the independent second value `resolution._verify` cross-examines. So liftover is only
reachable when there is no rsID and only an hg19 coordinate — and in exactly that case the lifted
coordinate becomes the row's sole identity, with nothing independent to check it against. A liftover
tool is therefore a generator of unverifiable-by-construction identities, which is the hazard class
behind the 3,038-variant off-by-one this tree already paid for. What the author wants is **rsID
recovery**: given an hg19 `chrom:start:ref:alt`, return the rsID or say there is none, so they author
an identity normal resolution can verify. Same input; it converts an unverifiable coordinate into a
verifiable one using machinery the enricher already has.

**Why it is not simply "do rsID recovery, then".** The recovery lookup is against a *build the enricher
does not otherwise touch* — every link is gated on GRCh38 — so it needs either an hg19-keyed dbSNP
surface or a chain file, and a chain file is a provisioned, pinned asset with its own licence and
release, i.e. the whole snapshot apparatus for one authoring convenience. That is the design round, and
it is what the version gate is on. Liftover survives only as the fallback for a locus with no rsID at
all, where it must announce itself rather than emit a coordinate that looks authored.

**One requirement whichever primitive wins, and it is already a shipped lesson.** The outcomes are
**mapped**, **unmapped** and **ambiguous** (a coordinate lifting to several targets), and they must not
collapse — `pyliftover` returns an empty list both for unmapped and for a missing chain file, which is
byte-for-byte the fusing S20 fixed in this same resolution path on the same day. Whatever lands here
returns three states, and the provenance goes in `resolution.csv`'s `source` column rather than being
lost into an ordinary authored coordinate.

## RM50 — PMID and PMCID are one id apart, and only one direction of the conversion exists

✅ **Shipped in 0.6.** `extract_pmids` now declines a digit run whose context spells `PMC` in any spacing, and the refusal **names the id it saw** rather than the one it wanted. This closed a live hazard rather than a cosmetic one: `PMC3110566` never parsed, but **`PMC 3110566` did** — and those digits are a real PMID for an unrelated article, so the outcome turned on a space and the accepted spelling silently cited the wrong paper. A cell that compiled before may refuse now; that is the fix. The PMC id lives on the derived row only, and `hint citation --pmcid` is a **reporting** lookup that never fills `pmid`, because filling it would make the existence check compare a value against the registry that produced it. The authoring half stays 1.0 with the requiredness demotion, since a citation with no PubMed id cannot become legal while P8 holds.

**Severity** medium (the accepted-but-wrong case is a silently misattributed citation — the S12 class)
· **Status** open — the **diagnosis half is an enricher patch and does not wait**; the schema half is
**0.6**, gated on a design round and on the requiredness demotion already queued for 1.0 · **Owner**
enricher (the guard, the reverse lookup) + format (`extract_pmids`' grammar and its message) ·
**Motivating case** raised while reading SCHEMAS.md's own account of the three reference tables
(2026-08-12)

**Three distinct confusions live under one heading, and only the middle one is already tracked.**

**1. A PMCID written where a PMID goes is sometimes accepted, as a different paper.** `StudyRow.pmid`
is free-form and validated through `spec.extract_pmids`, which is `\b(\d{1,8})\b`. Probed:
`PMC3110566` → `[]` and `pmcid: PMC3110566` → `[]` (no word boundary between `C` and a digit), but
`PMC 3110566` → `['3110566']`. The outcome turns on a space. When it is accepted the extracted number
is a **real PMID for an unrelated article** — PMIDs are densely allocated, which is precisely the S12
finding that made `pmid_exists` useless as a fabrication guard and put `title`/`journal`/`year`/
`first_author` on `CitationHint`. The rejected half is barely better: the message says "must contain at
least one PubMed ID" and never says the word PMCID, so it is a generic refusal where a specific one is
a fix — the same shape as `MISPLACED_COLUMN_REASONS` and `reject_reserved` one level down.

**2. A citation with no PMID at all** is *already tracked* and is not re-filed here: [§ 1.0 cleanup —
`StudyRow.pmid` required + PMID-shaped](ROADMAP.md#studyrowpmid-required--pmid-shaped) queues the requiredness
demotion to "≥1 of `{doi, pmid}`", and a PMC-only record (books, NIH reports, some datasets) is largely
covered by it, since such a record normally carries a DOI. What that entry does not say is what
`LiteratureRow` — keyed on `pmid`, digits-only, **required** — is supposed to do with such a row. That
is the piece which has to be decided in the same release, and it is the reason this item exists beside
the tracker entry rather than inside it.

**3. Only one direction of PMID↔PMCID is resolved, and the recorded reason only covers that
direction.** `literature._identifiers` reads `doi` and `pmc` out of the esummary `articleids` block, so
PMID → PMCID arrives free, and `literature.py`'s own docstring records that the **PMC ID converter is
deliberately unused** because of it (and separately that the converter is no existence oracle — its
"invalid article id" is about PMC *membership*). Both statements are true, and neither is about
**PMCID → PMID**, which is the direction the converter actually exists for. So a curator holding a PMC
id has no route through any of the three packages to the `pmid` every table keys on. Do not close this
by quoting the docstring back at it; it answers the other question.

**What can ship without the design round** — enricher plus `extract_pmids`, no schema change, no
verdict changed for anything else: refuse a digit run whose immediate context spells `PMC` in any
spacing, and **name the id that was seen** rather than the one that was missing. And where the record
does resolve, the pass already holds the PMCID from the same esummary response, so comparing it against
the authored digits catches the accepted-with-a-space case for free. Both are diagnosis, never repair —
nothing rewrites an authored cell.

**What needs the design round:** whether a PMCID is an *identity a citation may be authored under*, or
only a cross-reference the enricher fills. Three candidates, with their costs:

- **An optional `StudyRow.pmcid`.** Additive and minor-legal, and it closes the authoring half — but it
  leaves `LiteratureRow`'s key unanswered for a row carrying no PMID, and it puts a second id column on
  a table whose `pmid` is already free-form and may hold several.
- **Resolve every PMCID to a PMID at enrich time and store only PMIDs.** Smallest surface, and it
  silently drops the records that have none: two ways of returning nothing rendered as one sentence,
  which is S20 exactly.
- **Re-key `LiteratureRow` on a general citation id.** The honest shape, and it changes what an existing
  key *means*, so it is 1.0 and not this.

Whichever wins lands **with** the requiredness demotion, not before it — deciding the sidecar's key
while `StudyRow.pmid` is still mandatory answers a question no module can currently ask. Related:
RM47 makes the same observation from the other side, that a new PMID site obliges the literature pass
to learn it in the same release.


# 0.6 dogfooding — the fix round's own findings, repaired

Round 2 of [DOGFOOD_0_6_FINDINGS.md](DOGFOOD_0_6_FINDINGS.md) came from *reading the code around each
repair* rather than from building a module, and the thirteen findings that needed action were numbered
RM74–RM79 on 2026-08-14. What follows is what shipped, in the order it was worked.

## RM74 — the drafting providers read their sources wrong, and the test that would have caught one does not run

**Severity** high (one member) · **Status** ✅ shipped · **Owner** enricher · **Found by** code review
during the 0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-1, R2-11, R2-3

Three defects, one read each and one loop, all in `clinpgx_draft._rows_from_snapshot` and the test file
beside it.

**ClinPGx's `gene` is `;`-multi-valued** (R2-1). Re-probed against the provisioned snapshot before
touching anything: **396 of 16,087 rows** carry a `;` (`IFNL3;IFNL4` ×51, `ANKK1;DRD2` ×24,
`CYP2A7P1;CYP2B6` ×18), and `--gene VKORC1` dropped the **3** rows of `rs17886199`, published as
`PRSS53;VKORC1`. The filter now matches per member. The `;` separator was already a named constant —
for `drugs` — which is the part worth keeping: one dialect, two columns, and only one of them read it.

**What is *written* for a plural cell was the one real choice here, and the three candidates are not
equally wrong.** Writing the cell verbatim is what shipped until now, and it is a non-symbol in a
column described as *"Gene symbol, e.g. VKORC1"* — every consumer's gene filter misses it for exactly
the reason ours did. **One row per gene is illegal, not merely undesirable**: `gene` is *outside*
`PharmVariantRow`'s dedup key, so the copies collide on
`(variant_key, drug, genotype, phenotype_category, annotation_id)` and the compiler refuses the module
— which is the structural difference from `drugs`, which *is* in the key and therefore legitimately
becomes one row each. And **picking from the cell alone has no rule to pick by**: the pharmacogene is
first in `CYP3A5;ZSCAN25` and second in `ANKK1;DRD2`, `CYP2A7P1;CYP2B6` and `PRSS53;VKORC1`, so
position orders nothing and "the one that matters" is a pharmacological judgement this tier does not
make.

What shipped is the CPIC `gene.chr` move — a **lookup in what the caller already stated**. Under
`--gene VKORC1` the request selects exactly one member and writing it asserts only what the source
asserts. With no request, or with a request selecting two members of one cell, nothing selects, and
the answer is the house one: **withhold, and say which genes the cell named**, aggregated by cell so a
panel-scale draft does not print one line per row. An empty cell reads as *not stated*, which is
weaker than the truth; the joined cell is false about its own column.

**`skipped_unidentified` counted the wrong denominator** (R2-11). The rsID check ran before the
`--gene` filter, so a record with no rsID from an unrequested gene incremented it, and on any
`--gene` draft the "records the source could not identify" number was inflated by the rest of the
database — destroying the one thing it is for, judging whether coverage of *your* gene is poor. The
filter moved above it; every skip counter is now scoped to the requested set.

**A test's stated coverage was not exercised** (R2-3). `test_draft_declared_build.py` built its
fixture with a nested `"location"` key while `cpic.defining_variants` reads `"sequence_location"`, so
the dict was always `{}` and the file's claim to cover "one defining variant carrying a coordinate"
was hollow — the drafted `haplotypes.csv` did not exist and the file passed either way. Third
instance of the class after S21's registry and D6-2's `_MOVABLE`. Fixed with the key **and** an
assertion that the coordinate reaches the file, which is what makes the key load-bearing; demonstrated
by restoring the old key and watching the new assertion fail on a missing `haplotypes.csv`.

## RM75 — a complete result is destroyed by an incidental failure, and one handler cannot see its own case

**Severity** medium · **Status** ✅ shipped · **Owner** enricher · **Found by** code review during the
0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-13, R2-4, R2-2

**A client that leaks its transport library's exception type has no contract** (R2-13). `CpicClient._get`
called `raise_for_status()` and wrapped only *shape* failures into `CpicError`, so once retries were
exhausted a raw `httpx.HTTPStatusError` walked through both of `enrich_pgx`'s per-leg handlers — the
handlers written under the comment *"One source failing must not sink the pass — the other may still
answer"* — and took PharmVar's answer with it. The retrying request is now `_request` and the
translating wrapper is `_get`, in that order, because wrapping *inside* the retry would defeat it:
`retry_if_exception_type` tests `httpx.HTTPStatusError`, and a `CpicError` raised there is a
first-and-final attempt. A test asserts the ladder survived the split, since a decorator on the wrong
half turns three attempts into one and nothing fails.

**The same hole was on the PharmVar leg and the ledger named only CPIC.** Repairing one and not the
other would make that comment true in one direction, so the guarantee would hold or not depending on
which source went down — worse than either state. `PharmVarClient` got the identical split; its 401
branch stays inside `_request`, because that is a *diagnosis* raised before the status check rather
than a translation of one, and it must not be retried.

**An optional message-enrichment call could discard a finished draft** (R2-4). `pgx_draft` asks
`cpic.knows_drug` inside the `try` whose `finally` closes the client — deliberately — but by then the
alleles, diplotypes, defining variants and every recommendation have already returned. `knows_drug`
exists only to tell a typo apart from a real drug CPIC scores in a shape this table cannot hold (F5),
so a transport failure there threw away complete work to improve a sentence about it: the gnomAD rule
(a per-item error must never sink a batch) in a different tier. It is caught now, and the `bool | None`
tri-state that was *designed and never delivered from the live client* is finally reachable from it.

**A third reading of "could not establish" earned its own sentence rather than reusing the second.**
`known is None` already meant "the snapshot's recommendation table cannot answer this", whose remedy is
to go live; a failed request is re-runnable. Folding them would put the snapshot's wording in front of
an author who has no snapshot.

**An ordinary mid-authoring state tracebacked** (R2-2). F1's repair routed `draft` and `draft-panel`
through `source_build_mismatch` → `spec_genome_build`, which deliberately raises `EnrichmentError` on a
present-but-unreadable `module_spec.yaml`. Neither CLI named that exception, so a spec carrying only
`name:` turned `draft-panel --gene PALB2 --offline` into a rich traceback where every other enricher
command exits with a message. The presentation regressed *because* the build defect was fixed, which is
the shape worth naming: a shared precondition added to three providers owes the same addition to each
of their handlers. `_DRAFT_PRECONDITION_ERRORS` is what makes the fourth provider inherit it instead of
rediscovering it.

**And the raise moved to the top of both providers.** It landed *after* `_resolve_snapshot` had
provisioned a published ClinVar snapshot and after every CPIC query, for a check that reads one file
beside the spec. The warning is still appended where it was, so no reported order moved.

## RM76 — an unfinished authoring state passes every gate, including `--strict`

**Severity** high · **Status** ✅ the narrow repair shipped; **the general question is
[RM73](ROADMAP_0_7.md#rm73--a-rows-provenance-is-unknowable-in-a-flat-csv-and-nothing-closes-the-authoring-phase)**
· **Owner** format + compiler · **Found by** the 0.6 dogfooding fix round, 2026-08-14 · **Ledger** R2-8

`SourceRow` is a plain `BaseModel`, not an `AuthoredModel`, deliberately and for a stated reason: it is
a machine-produced reference fact, grouped with `ResolutionRow`/`FrequencyRow`/`GeneMetricsRow`/
`LiteratureRow`. S21 then made it **draftable**, also deliberately, because it is *"the only fact
sidecar a human writes"* and the only table the compile licence gate reads. Nobody reconciled the two,
and the gap is exactly the shape of both decisions being right.

Re-probed on `reference_examples/hfe_hemochromatosis` with `source=<<REPLACE>>`: the module **compiles
green under `--strict`** and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]` inside the block
its own `signature` covers. The compiler's only remark on that file was that `sources.csv` is the
deprecated spelling.

**What shipped: the guard, on the model rather than through the base.** `ModuleSpecConfig` is the
precedent — standalone for its own reasons, carrying its own `reject_template_placeholders` all the
same — so the classification stays true and the other four sidecars stay out, since no template is ever
generated for them. It refuses in **both** modes, which is not a choice: a load error is fatal in both,
and it is what every other authored table already does with the same token.

**Why a vocabulary column was hiding it, and why that matters twice.** `layer` refuses `<<REPLACE>>` as
a non-member, so a stub in *that* cell was caught by accident; `source` is free text by design, and
free text is most of this table. The accident is also what made the **first draft of this item's own
test green on the unfixed code** — asserting "some error mentions `<<REPLACE>>`" is satisfied by the
vocabulary message quoting the token back. The test now asserts the guard's own wording, and a second
one isolates the real hole: a valid `layer` with only `source` stubbed. A guard green because a
different mechanism happens to fire is the S21 / D6-2 / R2-3 shape arriving inside the repair for one.

**And the guarantee is now asserted, which it never was.** `draft.stub_template`'s docstring prints
*"an unreplaced stub **cannot compile** — `vocab.reject_template_placeholders` refuses it by name and
row, in both modes"*, and nothing checked it; it held only where a model happened to inherit the right
base. The new test is parametrized over `DRAFTABLE` rather than naming kinds, because the defect was a
model quietly outside a set and a hand-written list would have to be extended by whoever forgot the
base class. One `test_hints` docstring stated the old behaviour as a reason and is corrected in place
rather than deleted — the correction is the useful part.

Nothing in the corpus moved: a `mode="before"` validator that only raises changes no accepted value,
verified against the `artifact.digest` / `content_signature` values recorded independently in
ROADMAP_0_7 and CLAUDE.md.

**What is not closed.** *"A generated stub must be unable to compile"* is now true and now tested, but
it is still a property that holds because each model was individually given the right guard. What marks
authoring as **unfinished** — as opposed to marking one token as unreplaced — reaches this from
underneath, and that is RM73's phase boundary. This item is a sprout, repaired; the root is not.
