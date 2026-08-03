# just-dna-format — Roadmap

Forward-looking plans for the schema contract + reference compiler. **This doc is forward-only:**
what already shipped (0.1.0 → 0.4.0) and the rationale behind it now live where they belong —

- **[CHANGELOG.md](CHANGELOG.md)** — what shipped in each release, newest first (the record of
  0.1–0.4 that this doc used to duplicate).
- **[COMPILER.md](COMPILER.md)** — the per-feature coverage table (validated / materialized / computed).
- **[CHANGELOG.md](CHANGELOG.md)** + **[CONSUMER_ROUND2_AND_0_5.md](CONSUMER_ROUND2_AND_0_5.md)**
  — the shipped 0.4 design rationale (the 0.4 proposal was retired into the changelog on release) and
  the round-2 answers.
- **[PROPOSAL_0_5.md](PROPOSAL_0_5.md)** — the forward 0.5 design threads;
  **[PROPOSAL_0_4_1.md](PROPOSAL_0_4_1.md)** — the near-term 0.4.1 patch (inject the authority-key list
  + genuinely adopt `module.version`).
- **[USE_CASES.md](USE_CASES.md)** — each use case run through the *what-blocks?* lens (the `RMn`
  items below are derived there); **[REFERENCE_EXAMPLES.md](REFERENCE_EXAMPLES.md)** — worked drafts.

Code comments that cite "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs for
already-shipped features — follow them to CHANGELOG.md / COMPILER.md.

**Status:** **0.4.0 is the published line** (tags stop at `v0.4.0`; `dist/` holds only 0.4.0 wheels).
All three packages are at **`0.5.0`, unpublished**, on `enricher-0.5`; `schema_version` stays `"1.0"`.

**The unpublished window is load-bearing while it lasts.** `integrity.file_entries` skips missing
files, so a **new optional table** never moves the digest of a module that does not carry it (additive
any time), while a **new column on an existing parquet** moves every module's digest — major-only once
0.5 ships. Anything digest-moving is therefore cheap now and expensive after the cut, which is why the
0.5 pre-cut batch is columns-plus-tooling and everything heavier is deferred below.

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

## 0.5.0 (in progress, `enricher-0.5`) — the resolution-table + enricher rework

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
  digest-neutral. The ACMG SF cross-check was scoped here too and is **deferred to 0.5.1**: the probe
  found no machine-readable list to check against (see below).

## 0.5.1 — queued behind the cut (nothing here needs the window)

Small, additive, and digest-neutral, so waiting costs nothing.

**Shipped in 0.5.1** (see [CHANGELOG](CHANGELOG.md) for the detail): the whole authoring surface —
templating (`stub`/`scaffold`), offline hints, the enricher lookup surface, **delegated insertion**
and **partial rows**; **RM26**'s remaining two drafting providers (ClinPGx → `pharm_variants.csv`,
ClinVar → `variants.csv`) plus CPIC prescribing recommendations; **RM30**; a cross-table check for
star alleles used but never defined; and three reference examples authored end to end with the
surface (`hfe_hemochromatosis`, `cyp2c19_star_alleles`, `apoe_epsilon`).

**The ACMG SF cross-check — ✅ shipped (0.5.1), as the guarded scrape.** Re-probed 2026-08-03 and the
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

**Still queued:** nothing from the 0.5.1 list.

## 0.6.0 scope — deferred roadmap items (`RMn`)

Derived in [USE_CASES.md](USE_CASES.md) ("Roadmap items surfaced") by running each real/desired use
case against the shipped 0.4 bricks. RM1/RM2/RM3/RM8/RM9/RM11/RM12/RM14 **shipped in 0.4** (their
rows below are kept for traceability, marked ✅); RM18/RM19/RM20/RM21/RM22 **shipped in 0.5**; RM13 is
**realized by `just-dna-enricher`** in 0.5; the rest are 0.6-and-beyond scope.

**RM3 is the cautionary row.** It was marked shipped in 0.4 against a *hand-authored sample*, and the
real ClinPGx corpus then rejected roughly 97% of itself against that shape — corrected by RM20. When
marking an item shipped, check what it was validated against.

| # | Item | Owner | Motivating use case | Effort |
|---|---|---|---|---|
| RM4 | **Native ClinVar gene-panel materialization** — compile a `GenePanelSpec` (gene set + significance predicate) into `weights.parquet` at compile time, gated on a **content-pinned ClinVar reference mixin**. The 0.2 `GenePanelSpec` *interface* ships and is recorded verbatim; the app-level `gene_panel` adapter in just-dna-lite is the interim reference implementation. Blocked only by Constitution P2 (no network) — the reference must be *injected*, not fetched. **0.5 update:** the content-pinned reference now exists as an injectable artifact — `just-dna-enricher`'s ClinVar snapshot (`clinvar build` → `data/*.parquet` + `release.json` carrying `source_sha256`/`clinvar_file_date`, feeding `GenePanelSpec.reference`/`reference_sha256`). What stays parked is the *compile-time materialization* of a `GenePanelSpec` into `weights.parquet`; the injectable reference half is unblocked. | format (compiler) + consumer-provided reference | gene-panel modules (cardio / cancer / pathogenic) | medium |
| RM5 | **Symbolic / structural alleles** — a representation beyond `^[ACGT]+$`: `<S>`/`<L>`, `<DEL>`/`<INS>`/`<DUP>`, `<STR n>`, and large indels. **Motivating cases: 5-HTTLPR** (a biallelic ~43 bp structural indel → Short/Long, *not* a repeat count; rejected by today's nucleotide grammar and a category error in `repeat_alleles.csv`) **and ClinPGx's `del`/`ins` genotypes** (177 rows in the release, e.g. `C/del`, `del/del`), which the PGx passes skip rather than coerce. Also unblocks SV-scale variation and consuming symbolic VCF alleles (round-2 §1b/3c). | format (schema) | 5-HTTLPR, SNP+SV modules, symbolic-VCF consume | medium |
| RM6 | ✅ **shipped in 0.5** — **Callability as first-class state.** Both halves are now built: `requires_callable` was already a materialized tri-state column, and **`callable_from`** ships as the pointer beside it — the VCF field(s) a consumer establishes callability from (`DP`, `GQ`, `FT`, `DP\|GQ`), reusing `source_field`'s bare-token grammar rather than inventing a second one. It left the reserved namespace on being built: a reserved name is refused at author time, which would make the column unwritable. The consumer's own oracle enum (`CONFIRMED_NEGATIVE`/`LOW_DP_NEG`/`UNCOVERED`) is why this matters — a named negative is assertable only where the proof is, and now the module says where to look. | format (schema) | callability / no-call ≠ hom-ref | done |
| RM10 | **Declarative inheritance-expectation field** — an optional trio / de-novo / Mendelian-consistency assertion carried *as data* (the panel says what it expects; a consumer checks it). Only if a real module needs it. | format (schema) | trio / multi-sample panels | low (on demand) |
| RM14 | ✅ **shipped in 0.4** — **Structured per-version authorship**: an optional `authorship: [Contribution]` on `module_spec.yaml`/`ModuleManifest`, unbundling the flat `authors` + free-form `curator` (which smuggled kind via the `"ai-module-creator"` default) into three orthogonal axes (P5): **identity** (`who`), **role** (closed vocab created/edited/audited/reviewed), **kind** (open, multi-valued: human ladder `human`→`human_expert`→`human_certified`, or `ai`+scale `agent`/`team`/`swarm`; no `hybrid` — a joint contribution is two entries). Motivating case: **AI and human error-spectra overlap but differ**, so a consumer (the RM13 validator, a marketplace review queue, a human auditor) routes scrutiny by author-kind — the format carries the kind, the consumer picks the profile (north star). **Digest-neutral** (manifest metadata, out of `artifact.digest`); like `panel`, not reconstructed by the lossy `reverse_module`. Folding the flat `authors`/`curator` in is a 1.0-cleanup candidate. | format (schema) | authorship-aware scrutiny (§5a) | done |
| RM7 | **Evaluation-output / report-card schema** for the verification harness — **NOT a format task.** Per-sample results are a *measurement*, so by the data-agnostic north star this is a **consumer** contract (`just-dna-lite`), listed here only so it is not mistaken for format scope. | consumer (`just-dna-lite`) | verification harness (§1a) | — |
| RM11 | ✅ **shipped in 0.4** — **`doi` provenance column** on `StudyRow`, wider than `pmid` (covers preprints/books/theses/datasets with no PubMed id); validated against the DOI grammar, kept verbatim, materialized into `studies.parquet`. A network-first validator (RM13) cross-fills `doi`↔`pmid`. Additive/optional → P3/P8 clean. The full DOI-only fix (relaxing the mandatory `pmid`) is a 1.0 item — see the 1.0 tracker. | format (schema) | validator source-checks (§4a) | done |
| RM12 | ✅ **shipped in 0.4** — **Provenance locator**: optional `provenance_quote` (keyword phrase) + `provenance_regex` on `StudyRow`, pointing at the passage in the cited article's fulltext so a validator can answer *"does the fulltext contain this claim?"* yes/no. The regex is a **declarative pattern grammar** (Principle 1 — data, not code; `re.compile`-checked at author time, matched by a consumer-side ReDoS-safe engine); the provenance analogue of `source_field`. | format (schema) | validator fulltext check (§4a) | done |
| RM13 | ✅ **realized in 0.5 as `just-dna-enricher`** — the network-first resolution/enrichment tier. 0.5 builds the rsid↔coordinate resolution half (cache + Ensembl V2/V1 + tenacity, producing `resolution.csv`); the source-check half (validate `pmid` in PubMed, confirm fulltext provenance, cross-fill ids) is additional resolver links the same package can grow. Principle 2 stays intact — the enricher is a *separate tier* that fetches; format/compiler never do. | network tier (`just-dna-enricher`) | deterministic module scrutiny (§4a) | in progress |
| RM20 | ✅ **shipped in 0.5** — **PharmGKB annotations are per-genotype and per-category.** `PharmVariantRow` gains `genotype`, `phenotype_category` (closed vocab, multi-valued) and `annotation_id`; the duplicate key becomes `(variant_key, drug, genotype, phenotype_category, annotation_id)`. Corrects RM3: one variant+drug carries several distinct annotations (rs4149056+simvastatin is Metabolism/PK 1A, Efficacy 3 *and* Toxicity 1A), and 1,199 of 17,380 triples in the ClinPGx release collide without the two extra columns. | format (schema + compiler) | 2b, the real ClinPGx corpus | done |
| RM21 | ✅ **shipped in 0.5** — **Data-source licensing as data.** `sources.csv`/`SourceRow` per (source, layer): licence, pinned `license_sha256`, attribution, notice, tri-state `share_alike`/`commercial_use`, and the acquirer's `declared_use`; summarized into `manifest.sources`. The compiler refuses annotation-layer content that forbids sale when no declaration is recorded — **data-driven, not a CLI flag**, because a flag cannot round-trip (P7). Motivated by every PGx upstream being CC BY-SA *plus* a bar on sale. | format (schema + compiler) + enricher | 2c, marketplace redistribution | done |
| RM22 | ✅ **shipped in 0.5** — **PGx tables join resolution.** `enrich()` reads `pharm_variants.csv` and `haplotypes.csv` as well as `variants.csv`, so a PGx module (which carries no `variants.csv` by design) gets coordinates instead of an empty `resolution.csv`. | enricher | 2c, 3c | done |
| RM16 | **Authored PRS weights (a scoring file, not a manifest).** 0.4 shipped `pgs.csv` as a *manifest of PGS Catalog IDs* with the ancestry-validity fields — not authored per-variant weights (just-prs resolves a `PGSxxxxxx` id to a harmonized scoring file and scores each id itself, so inlined weights would be dead data; a PRS is a Z/percentile-in-reference, a shape the format does not bin). Deferred: a distinct, digest-bearing `effect_allele`+`effect_weight` scoring table for the case a module must ship weights the PGS Catalog does not host. Build only against a real consumer that combines authored weights into a score. See [PROPOSAL_0_5.md](PROPOSAL_0_5.md) D1. | format (schema + compiler) | authored-weight PRS modules | medium-large (on demand) |
| RM17 | ✅ **shipped in 0.5** — **SemVer on `module.version`, coercing.** The 0.4.1 read-only preview became enforcement on `ModuleInfo`: `v2` → `2.0.0`, with the rewrite reported once via `version_coerced_from` (silently editing an authored value is the thing this codebase does not do). **Coerce rather than strict-reject**, decided against the corpus: the pre-0.4 modules are full of `v2`/`3`, and rejecting them would break every one to gain a stricter spelling of an advisory field. Digest-neutral. One consumer-visible change: a non-SemVer version used to be dropped from `Identity.version` entirely, so such a module published with no version at all — it now reaches the manifest coerced. | format (schema) | pre-0.4 corpus `module.version` | done |
| RM15 | **Build-agnostic identity & multi-build support (other-builds-support)** — today a coordinate is *implicitly GRCh38* (legacy-from-implementation): `genome_build` is authored/manifest metadata, but every `chrom/start/ref`, the Ensembl resolver, and all coord-based reasoning silently assume GRCh38. Coordinates are **not absolute** — GRCh37 / GRCh38 / T2T-CHM13 disagree, and the rsid↔coordinate mapping is **build-specific**: an rsid may resolve in one build and be un-annotatable (unplaced/absent) in another, and presence/absence combinations vary per build. This item makes the build a first-class axis — coordinates tagged by (or resolved per) build, a **build-aware resolver** (the injected reference declares its build; a module/reference build mismatch degrades to *unverified* rather than a false consistency error), and cross-build rsid annotatability recorded *as data*. **The "coordinate-first identity" parking is now RESOLVED, on its own stated condition.** This item parked option C because a bare coordinate "would bake GRCh38 into `variant_key`", and said it "becomes reconsiderable only once identity can name its build". A **GA4GH VRS allele id names its build**: the sequence is addressed by its refget accession — the digest of the reference sequence itself — so GRCh38 and GRCh37 mint distinct, correctly non-colliding ids. 0.5 therefore ships coordinate-first identity as the VA for a resolved substitution (see [SCHEMAS.md](SCHEMAS.md) § the identity switch). What remains of RM15 here is the **multi-build** half: a second refget table beside `REFGET_GRCh38`, per-build coordinates, and cross-build annotatability. The GRCh38-only minting ships now — the same "GRCh38-now, multi-build-later" split this item already applies to one-to-many expansion. **Generalizes one-to-many rsid expansion to multi-build:** a no-coord rsid that maps to several loci is expanded to one row per locus (a paralog/SV signal a client can count — data-agnostic), and that ships **GRCh38-only now as compiler behavior** (pinned by `compiler_version`, not a schema break). What is build-specific is *which* loci and *how many*, so RM15 tags expanded coordinates by build and records cross-build annotatability; the GRCh38 expansion itself is not deferred. Blocked by nothing external (schema-shape + resolver decision) but large — touches identity, positions, the resolver, and `artifact.digest`. Interacts with RM5 (symbolic/structural alleles differ across assemblies) and the reserved `reference_db` axis. | format (schema + compiler) | GRCh37 / T2T modules; cross-build annotatability | large |

| RM23 | **Computational predictor scores as a table** (`predictions.csv`) — the groundwork every predictor source needs, built **once**: one row per `(variant, predictor, score_kind)` with `score`, `dataset`, `source`, and an optional `transcript`. Long-form, not wide, is the load-bearing choice — SpliceAI is four deltas plus positions, CADD is one number, AlphaMissense is one plus a class, so wide columns would make every new predictor a schema bump while long form makes it *data*. A predictor score is the same class of object as an allele frequency or a LOEUF (a per-variant number from a named dataset, no measurement), so the 0.5 sidecar precedent covers it. Deferred on two unsettled questions, neither of which is code: the **grain** (per-transcript scores; how to name the four splice deltas without inventing a predictor-specific column set) and the **acquisition** — precomputed splice scores need the *masked vs raw* file sizes measured and the Broad lookup API's terms read, which is the same measure-first question that correctly parked the frequency snapshot. Licensing is already solved rather than blocking: SpliceAI/Pangolin, dbNSFP, AlphaMissense, REVEL, CADD and PrimateAI are all non-commercial or academic-only, and `sources.csv` + the compile gate already confine that to the modules that use them, while phyloP/phastCons/GERP (UCSC, free — and queryable per-range rather than a bulk download) keep a module sellable. | format (schema + compiler) + enricher | pathogenicity triage; splice-impact panels | medium |
| RM24 | **Gene–disease validity as a table** (`gene_validity.csv`) — one row per `(gene, disease term, classification, source, dataset)`, serving **ClinGen** gene-disease validity, **GenCC** aggregate validity and **HPO** gene→phenotype from one shape. This is a *different grain* from `gene_metrics.csv` (gene × term, not gene), which is why it is a table rather than more columns; dosage sensitivity went the other way for the same reason. The cost is the design (getting one shape to fit three submitters' vocabularies), not the code. All three sources are free, so unlike RM23 this one leaves a module sellable — worth remembering if the marketplace ever sells modules, since every PGx upstream forbids it. | format (schema + compiler) + enricher | gene-panel triage; lay-language disease naming | medium |
| RM25 | **ClinVar assertion tier as artifact data** — a facts sidecar carrying `clin_sig` + `review_status` + `review_stars` + `variation_id` per variant, so a consumer can route scrutiny by assertion tier at query time (a 1-star submitter and a practice guideline are not the same claim). Nothing is lost today: `clinical.ClinSigFinding` **already** reports both fields via its `confidence` property, so this is about persisting the tier, not discovering it. Deferred as a new table. **Do not confuse this with escalating the check's severity** — see *Parked in 0.5*. | format (schema + compiler) + enricher | authorship/assertion-aware scrutiny | medium |
| RM26 | ✅ **shipped (0.5.1)** — all three drafting providers. CPIC → PGx tables (`pgx_draft`), **ClinPGx → `pharm_variants.csv`** (`clinpgx_draft`), and **ClinVar → `variants.csv`** (`clinvar_draft.draft_gene_panel`, `enricher draft-panel`), which partially dissolves RM4: a gene panel is authorable with no compile-time reference materialization. The ClinVar one needed two mechanisms rather than a compromise. `VariantRow.genotype` is required and ClinVar publishes **alleles, not genotypes** — whether carrying a pathogenic allele is a carrier state or an affected one follows from the condition's inheritance mode, which the source does not state and a provider must not invent. So it writes a **partial row** (`draft.PartialRow`): every cell ClinVar publishes, with `genotype` carrying `TEMPLATE_PLACEHOLDER`, which no mode compiles. Sameness is decided by `match_on` (the identity columns) rather than by the natural key, because that key runs through the stub — so once a human fills a genotype, a re-draft reports `already_present` instead of re-adding the stub. Rows land in their gene's block via delegated insertion, which is what made this usable on a 2,500-row panel rather than merely possible. Identity is filled whole or not at all: a lone `alts` on a position-only row mints a VRS `ga4gh:VA.…` key instead of `chrom:start:ref`. | enricher | gene-panel authoring; PGx authoring | — |
| RM27 | **A redistribution compile gate** — RM21's gate keys on `commercial_use` + `declared_use`; the 0.5 `redistribution` column is recorded but **not** gated. Deferred because it is a genuine design question rather than a missing branch: a redistribution bar is not a *use*, so `declared_use` (`unstated`/`non-commercial`/`commercial`) is the wrong axis to resolve it against — a module may be built legitimately and still not be shippable, which is a different verdict from the ones the gate currently issues. Needs the third axis thought through before code. | format (compiler) + enricher | OMIM-/dbNSFP-class sources | low (after the design) |

**Delegated insertion — shipped (0.5.1). The reasoning, kept because it corrects itself:**

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

**RM29 — ✅ shipped (0.5.1): cofactor columns, taken inside the unpublished-digest window.** Three
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

**RM30 — ✅ fixed (0.5.1): one rule for a haplotype name across all three PGx tables.**
`AlleleFunctionRow.allele` enforced `STAR_ALLELE_PATTERN` (a leading `*`) while
`HaplotypeRow.haplotype_name` and `DiplotypeRow.haplotype_a`/`haplotype_b` had no rule at all, so
`e4` was legal in two of three tables and illegal in the third — and an author working around it
with `*4` in one and `e4` in another hit the 0.5.1 cross-table check's "used but not defined",
with no spelling that satisfied both. Found by `reference_examples/apoe_epsilon/`. The three now
share `validate_haplotype_name`: non-empty, no whitespace, and nothing else — **a name is an
identity, not a grammar**. `STAR_ALLELE_PATTERN` stays exported and is still what `pgx_draft`
checks at its four sites, so loosening the schema did not loosen CPIC drafting. Net effect is a
loosening (previously-valid data stays valid, P3-safe) plus a negligible tightening on the two
columns that had no floor: an empty or whitespace-split name could never have identified a real
haplotype.

**RM28 — meta-conclusions and injected cofactors (starter shape recorded, deliberately unbuilt):**
A module is rarely one axis, and what a curator wants is to pair them — a CVD module that also says
something about aspirin or warfarin *given* what the rest of the module found. The format cannot
state that today: every table keys on one subject and `conclusion` is prose about it alone.
CONSTITUTION P1 already sanctions the mechanism (a non-Turing-complete boolean predicate, drafted
since 0.1 and never wired because nothing demanded it). **The algebra is three-valued, not boolean** — true/false/**unknown**, Kleene operators, with
`unknown` a first-class value. That is not new here, it is the rule this codebase already follows
everywhere (`None` ≠ `False` in `SourceTerms`, `CrossrefClient.exists`, `quotes_found`, `--offline`
reporting `unchecked`, `unresolved` for a missing measurement, `requires_callable` for an uncalled
absence) finally stated as an algebra rather than as separate cases. It matters concretely: with
Kleene `AND`, a conclusion gated on "ε4 present AND QUAL ≥ 60" is decidably **false** at ref/ref
whatever the quality was, so a blanket withhold-on-any-unknown would be strictly worse than the
tables it replaces. A predicate evaluating to `unknown` is withheld — never reported, never negated.
The full design thread, the starter shape and what is deliberately left open are in
[PROPOSAL_0_5.md § G3](PROPOSAL_0_5.md). In brief: a new
**optional** table, a predicate that **never blocks** (an unresolvable reference warns), a grammar
kept to the smallest thing that covers the motivating case — conjunction **plus one relational
notion, in-cis/in-trans**, because the case that most justifies the table is compound
heterozygosity, where the same two alleles mean *affected* in trans and *carrier* in cis and a
pure conjunction cannot tell them apart (*the table is the safe commitment; the grammar is where
drift happens*) — and **injected cofactors** — values the consumer supplies at query time that a module must
never hold. Three classes so far, each with the same withhold-on-missing rule: **ancestry**
(a panel-scale inference, not derivable from a curated module's own gnomAD frequencies —
real models do not rely on single SNPs), **clinical context** (CPIC's populations), and
**call quality** (a `QUAL`/`GQ` floor, the `source_field`/`callable_from` declarative-pointer
idiom pointed at confidence — and distinct from the dropped `caller` names, which recorded
measurement provenance rather than an annotation's own applicability). The first real evidence arrived with
CPIC's clopidogrel populations, where `draft --population` makes an author bake in a choice that is
only knowable at query time. **Feasibility probed 2026-08-03 and the result argues for keeping it parked:**
`reference_examples/apoe_epsilon/` builds the highest-profile meta case — APOE, whose ε
haplotypes are defined by two SNPs together and whose ε4 condition is P1's own example
(`rs429358==C AND rs7412==C`) — with **bricks that shipped in 0.4 and no predicate at all**.
`HaplotypeRow` is a junction table, so same-strand co-location is what it already expresses;
`diplotypes.csv` carries the conclusion. What stays out of reach is narrower than it looked. **Rows are a disjunction and columns are a
conjunction**, so the existing tables already span any finite boolean function over an enumerable
set of genotypes — `OR` is two rows, `XOR` and bounded `NOT` are enumeration, and `haplotypes.csv`
is same-strand `AND`. No operator is missing. What is missing is (a) **economy and intent** — "any
two pathogenic variants in trans" over 300 of them is ~45,000 pairs, expressible but unwritable
and unreadable — and (b) **open-world negation**, which no operator fixes: "no pathogenic variant
in this gene" quantifies over a set the module does not close, and absence is only assertable where
the region was callable (`requires_callable`). A negation feature ignoring that would manufacture
reassurance, the worst failure mode this format has.

**Probed again 2026-08-03, and the cis/trans motivation is now closed — as a check, not a table.**
`reference_examples/hfe_compound_het/` builds the case that most justified the predicate grammar:
HFE C282Y and H63D, where the same two heterozygous calls mean *compound heterozygote, at-risk* in
trans and *carrier* in cis. It needs no new machinery either. A **diplotype is already a statement
about two homologs** — `haplotypes.csv` says which alleles ride together on one chromosome and
`diplotypes.csv` pairs two of them, which is what "in trans" means — so cis and trans are two rows,
and the relational notion the proposal was going to add to the grammar is what a diplotype pair *is*.
Between this and APOE, **both** halves of the phase argument are now answered by the existing tables.

What building it *did* surface is narrower and real: nothing said the two rows are
**indistinguishable without phase**. They present the identical unphased genotype with opposite
conclusions, and nearly all consumer data is unphased. That is derivable from the two tables the
compiler already holds, so it shipped as `_cross_validate_phase_ambiguity` — a warning, never a block.
A `requires_phase` column was rejected: it would make an author restate what the data determines and
would go stale the moment a haplotype is edited. It is closed-world by design (it compares stated rows,
never omitted ones), which is why APOE — whose ε2/ε4 vs ε1/ε3 is the textbook collision — stays quiet:
the module carries no ε1.

**So what remains of RM28 is smaller again**, and is the same two items APOE named: pairing across
*subjects* (no table keys on more than one), and **economy** — "any two pathogenic variants in trans"
over 300 of them is ~45,000 pairs, expressible and unwritable — plus open-world negation, which is not
an operator problem. RM29 removed two of the three cofactor classes into columns in the same round, so
only ancestry stays genuinely injected. Still parked. It waits on a corpus to generalize from — roughly 70% built; nutrigenomics
and supplements do not exist yet — because fixing a shape against four table kinds and then meeting
the fifth is how a one-way door gets spent badly (P3/P5). It also blocks the "shy module" signal.
| format (schema + compiler) | combination annotations; disclosure policy | medium (after the corpus) |

**RM31 — indel representation mismatch defeats allele-aware resolution (found 2026-08-03, real).**
`resolution.genotype_fits` compares **allele strings**, so two valid spellings of one indel do not
match and the locus is dropped. Confirmed end to end while drafting
`reference_examples/shox_par1/`: `rs1569493663` is drafted from ClinVar as `X:634689 CAG>C` and
Ensembl publishes the same 2 bp AG deletion as `X:634690 AGAG>AG` — anchored one base earlier with a
padding base — so the authored genotype "cannot host" Ensembl's alleles and the variant resolves to
`not_found`. Nothing about it is a merge or a paralog; it is one deletion written two ways. The
message that reported it *asserted* the wrong reading ("a different variant sharing the rsID"), which
is now corrected to name both — that part is shipped.

The fix is not. A reference-free **parsimony trim** (strip the shared suffix, then the shared prefix)
reconciles this particular pair, but it does **not** left-align inside a repeat, which genuinely needs
the reference sequence — and `genotype_fits` is deliberately **shared three ways**, including with the
compiler, which by charter holds no reference (P2). So the options are a bounded reference-free
normalization in the shared predicate (helps many real cases, silently misses others, and changes
which loci survive expansion → digest-visible), or a reference-backed normalization that can only run
in the enricher and would make the two callers disagree about what fits. Neither is a small change,
and picking one is the decision. | format + enricher | any indel-bearing panel | **medium** |

**RM32 — a pseudoautosomal locus is one place and two contigs; the format models it as two variants.**
Nine of the ten SHOX variants in `reference_examples/shox_par1/` map to **both** X and Y at the same
base (PAR1 has identical coordinates on the two contigs in GRCh38), so the one-to-many expansion emits
two rows per variant: 19 rows for 10 findings, all in `weights.parquet` and in `artifact.digest`. A
consumer counting the module's findings gets 19. Worse, standard GRCh38 analysis sets **hard-mask the
Y PAR**, so in a normal pipeline the nine Y rows can never match anything.

The obvious "fix" — collapse the pair — contradicts the identity model 0.5 just adopted: VRS keys on
the **refget accession**, and X and Y are different sequences, so `ga4gh:VA.…` says these are two
alleles. The expansion is also *correct* for the case it was built for (paralogs are genuinely
distinct loci). So this is not a bug to patch but a question to answer: does a module say something
about a *place in the genome* or about a *contig coordinate*, and if the former, what is the identity
of a locus present on two contigs? Recording it with the evidence rather than guessing.
| format (identity) | any PAR gene: SHOX, CSF2RA, ASMT, CD99 | **medium** |

**RM33 — `source` names two different things in two tables, and the compiler compares them.**
`_source_checks` warns when a fact table cites a source with no `sources.csv` row, by exact string
set difference. But `resolution.csv`'s `source` column names **which link answered** (`ensembl-rest`,
`ensembl-graphql`, `cache`, `authored`, `reversed`, `clinvar`, `gnomad`) while `sources.csv`'s names a
**licensed data source** (`ensembl`, `clinvar`, `clingen`, …). They are different vocabularies under
one name — the overloaded-axis anti-pattern (P5) — spread across two tables, which is why every
enriched module warns that `ensembl-rest` has no terms recorded.

Both obvious repairs are wrong. Writing a `SourceRow` per link makes `ensembl-rest` and
`ensembl-graphql` two "sources" with identical terms. Teaching the compiler a link→source map gives it
a **source convention**, which is exactly what P2's 0.5 tightening removed and what
`licensing.py` says in as many words ("the compiler holds no source→licence map — that would give it
a source convention and an un-injected reference"). What is missing is a third thing: the resolution
table recording *both* the link and the source it stands for, which is additive but is a schema change
to `ResolutionRow`. Note `VALID_SOURCE_LAYERS` already reserves `"resolution"` for the row nobody
writes — `enrich()` is the only pass that records no source at all.
| format (schema) + enricher | every enriched module | **medium** |

**RM34 — the CPIC provider has no filter, and CYP2D6 shows what that costs (found 2026-08-03).**
`draft --gene CYP2D6` succeeds and produces a module nobody can use: **16,290 diplotype rows, 11,825
of them (73%) `Indeterminate`** — CPIC saying it cannot call that pair. It compiles, in 1.9s, and it
is not wrong; every row is a faithful transcription, and an `Indeterminate` row is genuinely better
than silence for a consumer whose caller emits `*100/*102`. But the module is not human-authorable in
the sense the charter gates on, and the author has **no way to draft a subset** — `--drug` *adds* rows
rather than filtering them.

The gap is visible as a parity difference between the two providers: `draft-panel` (ClinVar) takes
`--clin-sig` and `--min-review-stars`, and `draft` (CPIC) takes nothing. The reason to record this
rather than add a flag is that *which* filter is the decision — by called phenotype, by allele set, by
activity score — and each spends a CLI name and asserts a different view of what a PGx module is for.
CYP2C19 (2,664 rows) is borderline; CYP2D6 is where it stops working.

Two smaller CYP2D6 observations, both already fixed: 546 diplotypes are skipped because CPIC writes
copy number as `x≥3` and `≥` is not a star-string character (RM5 territory — the notation, not the
biology), and those skips were emitted one line each until they were aggregated like the activity
scores beside them. | enricher (CLI) | CYP2D6, and any large star-allele gene | **medium** |

**RM35 — a continuous binning table cannot be tiled without a finding (proved 2026-08-03).**
Three rules that are individually right and jointly unsatisfiable on a continuous measure: bounds are
**inclusive at both ends**, an overlap is an **error**, and any positive hole is a **warning**. Two
adjacent `allele_fraction` bins therefore either share an endpoint (a measurement of exactly `0.1`
selects two phenotypes → error) or do not (a hole → warning). No epsilon escapes it — `[0, 0.0999999]`
and `[0.1, 1.0]` still warn. So every `allele_fraction` and `prs_percentile` table must carry a
finding forever, which is a check that cannot be satisfied rather than a check that is failing.

Integer kinds are unaffected and that is why it was missed: HTT `[6,35]`, `[36,39]`, `[40,∞)` is
genuinely gapless because the domain is discrete, and the inclusive convention was generalized from
those. Proved by construction in `schema/tests/test_heteroplasmy_variant_key.py`; visible on
`reference_examples/mt_heteroplasmy/`.

The candidate resolutions are all semantic decisions, which is why this is recorded rather than
patched: **half-open `[min, max)` for continuous kinds** (correct, but changes the meaning of every
already-authored continuous bound), **drop the interior-gap check for continuous kinds** (what
`activity_score` already does, but it throws away a real check), or **treat a shared endpoint as a
boundary rather than an overlap** (implicit and easy to misread). | format (binning semantics) |
heteroplasmy, PRS percentile | **medium** |

**Round-3 / on-demand (widen additively only if a real module hits it):**
- **STR microvariant notation** — forensic loci use `full.partial` allele names (TH01 `"9.3"` = 9 full
  `TCAT` repeats + 3 extra bases), which is *not* the decimal 9.3. A binning bound stays a plain
  magnitude for ordering; the `full.partial` allele *name* is a distinct string (a candidate for the
  reserved repeat motif-path / allele-string escape hatch), never smuggled into the float bound
  (CONSUMER_ROUND2 C2). Pathogenic-threshold loci (HTT CAG) are unaffected.

### Annotating core, not format scope (the 0.5 source assessment)

RM7 and RM13 are listed above so they are not mistaken for format scope. The same needs saying about
roughly half of every annotation source assessed in 0.5 — the half that **calls or interprets**. A
module supplies annotation tables; the measurement arrives from the consumer at query time, so none of
the following can land in these libs no matter how useful it is:

- **Star-allele callers** — PharmCAT, and Cyrius / PyPGx for the CYP2D6 case PharmCAT punts on. These
  turn a VCF or a BAM into a diplotype call: measurement. What *does* belong here is their **data** —
  the CPIC allele definitions PharmCAT ships — which is why the drafting helper reads them. Note that
  routing through PharmCAT does not launder the terms: its definitions are CPIC's, so the ClinPGx
  no-sale clause still applies.
- **Running splice or missense predictors**, and choosing their thresholds. A SpliceAI delta of 0.2 vs
  0.5 is an interpretation policy, not an annotation; RM23 carries the score and the dataset, never a
  verdict.
- **ACMG rule application and incidental-findings reporting policy.** The format carries `acmg_sf` as a
  flag and (with the pre-cut check) validates it against the published list; deciding what to report to
  whom is the consumer's.
- **Lay-language rendering.** A module already carries the ontology CURIE and a human `conclusion`;
  turning a MONDO term into patient-facing prose is a presentation concern.

**Cross-repo (tracked elsewhere):** **just-dna-marketplace** — take `just-dna-compiler` as the M4
publish dependency; serve `logs` via the files endpoint; render the cross-version provenance union
(`aggregate.aggregate_provenance`) on the module-detail view.

## Freeform suggestions — the 0.5 idea-book

The consumer's grounded 0.5 ideas (kept inside the one constraint: **VCF-based, possibly augmented on
top**) live in full in [CONSUMER_ROUND2_AND_0_5.md](CONSUMER_ROUND2_AND_0_5.md) §3, each run through
the what-blocks lens in [USE_CASES.md](USE_CASES.md) §1. Standing dispositions:

- **3a — module declares where its measurement lives in a VCF.** ✅ Taken early: `source_field` shipped
  in 0.4 (an optional, `|`-alternatable **bare field-name token** on every binning table — a
  *declarative pointer, not an expression*, inside Principle 1). An ExpansionHunter VCF (`INFO/RU` →
  `repeat_unit`, `FORMAT/REPCN` → the measure) is consumable with zero glue.
- **3b — modules as a deterministic verification harness** (run a panel against N VCFs, emit a
  byte-diffable report-card). **The strongest idea, and it needs *nothing* from the format:** a panel
  is already a module, `source_field` names the field to read, `artifact.digest` makes the before/after
  diff trustworthy, and the mandatory `unresolved`/callability contract stops a no-call masquerading as
  a mismatch. It is a **consumer** feature (`just-dna-lite`); the format only supplies properties it
  already froze. Recorded as an *enabled* use case, not a gap.
- **3c — augmented-VCF as the landing pad** for cracked short-read loci (a synthetic `<STR>` record with
  `INFO/RU` + `FORMAT/REPCN` + custom evidence fields, consumed through the same `source_field=REPCN`
  path). Endorsed as the interface — the format binds to the VCF, it does not reinvent it. Consuming the
  *symbolic* alleles themselves is RM5.
- **3d — smaller VCF-native ideas:** callability three-state → RM6; phasing-aware panels → already
  expressible (the `phased` flag + VCF `PS`/`HP`); trio/de-novo assertion → RM10.

### Parked in 0.5 (recorded so they are not re-proposed as if new)

- **Enricher co-authoring** (permission-gated writes to *authored* files, not just sidecars). Attractive
  — it would let a stale rsID or a missing DOI be fixed where it actually lives instead of only being
  reported — and deliberately **not** taken, for a reason stronger than tidiness: `content_signature`
  is *defined* as pre-resolution and reference-independent ("computed from the rows before resolution,
  so recompiling against a different/complete reference does not change it"). If a network fetch could
  edit `variants.csv`, the content-dedup identity would become network-dependent and that documented
  property would simply be false. A secondary problem: `authorship` records who wrote the module, and
  an enricher that edits rows either falsifies that record or must add itself as an `ai`/`agent`
  contribution — coherent, but a much larger design than it first looks. Revisit only with both
  answered.

  **The drafting helper is not this item, and the line between them is one word: *mutate*.** The 0.5
  helper appends rows a source publishes into an authored CSV; it never rewrites a cell that is already
  there. Appending happens at authoring time and leaves `content_signature` a function of the authored
  bytes exactly as before — the property that would break is the one where a *fetch* changes the meaning
  of rows the author already wrote. So a row whose natural key is already present is **reported, never
  overwritten** (drift on existing rows is the cross-check pass's job, `pgx.enrich_pgx`), and the helper
  stamps no `authorship`: it transcribes a published table, and the human owns the module. Dedup keys on
  the compiler's own `_TABLE_DUPE_KEYS`, so an append can never produce a row the compiler would then
  reject as a duplicate, and rows are appended **at the end** — authored row order is preserved through
  compile → reverse → recompile, so re-sorting an existing file would move a compiled module's digest.

- **Escalating the ClinVar `clin_sig` cross-check when the disagreement is with an expert panel.**
  Tempting, because a VCEP or practice-guideline assertion genuinely is a different kind of claim from a
  one-star submitter's, and the snapshot already carries `review_status`/`review_stars` to tell them
  apart. Not taken: this is the one check that warns in **both** modes on purpose, because failing a
  compile over a clinical disagreement makes the format arbitrate a clinical dispute, which the
  data-agnostic charter forbids — and a curator who has read the primary literature and disagrees with a
  submission is doing their job. The tier is already *surfaced* (`clinical.ClinSigFinding.confidence`
  puts it in the message), and persisting it as queryable data is RM25. Surface it, let the consumer
  route on it, do not decide for them.

- **An offline allele-frequency snapshot.** The obvious symmetry with the ClinVar and gene-constraint
  snapshots, and it does not work: gnomAD v4.1's sites VCFs are **58 GB** (exomes) and **742 GB**
  (genomes), so there is no slice to ship at any useful coverage. Frequency is therefore the first and
  only **online-only** link in the chain. This is not a reproducibility hole — once `frequencies.csv` is
  written it *is* the pin, and every later compile reads it offline and deterministically. Revisit only
  if gnomAD publishes a small pre-aggregated frequency release.
- **HGVS string generation** (`c.`/`p.` notation). `ga4gh.vrs`'s extras pull `hgvs` transitively, so it
  would be *available* — but HGVS generation is its own feature with its own argument (which transcript,
  which reference, how to present ambiguity), and taking a dependency for indel normalization does not
  commit to shipping it. Deferred as a feature, not blocked by tooling.
- **Multi-build VRS minting.** A second refget table beside `REFGET_GRCh38`; the remaining half of RM15.
- ~~**dbSNP obsolescence / merge checking**~~ — **built in 0.5** as `identifiers.check_rsids`, wired
  into `enrich()` behind `--verify-rsids`. Two corrections to what this entry used to claim, both found
  by probing: it is **not** "detectable two ways" — Ensembl REST resolves *some* merges (`rs77121243` →
  `rs334`) and returns **HTTP 400** on others (`rs3216883`, which dbSNP correctly reports as merged into
  `rs3051860`), so Ensembl alone would misclassify a merged rsID as unresolvable. **NCBI `esummary
  db=snp` is the oracle**, batched and authoritative. See *the stale-identifier collision* below for
  what is done with the answer.
- **Sex-stratified frequency counts.** gnomAD serves `nfe_XX`/`XY`; sex is a second axis, and folding it
  into `population` would be the `state`-overloading mistake again. A future `sex` column on
  `FrequencyRow` is the additive shape if it is ever wanted.
- **`google-re2` for `provenance_regex` matching** (candidate, only if the current bound proves
  insufficient). The enricher matches `provenance_regex` against fulltext with stdlib `re` inside a
  killable child process (`literature.regex_matches`). That is a *bound*, not a linear-time guarantee,
  and the honest reason it is enough today is that the threat model here is a curator writing a slow
  pattern by accident — the pattern comes from the module being enriched and the document from a public
  archive, on the author's own machine, not an attacker meeting an arbitrary document.

  **The reason not to switch pre-emptively is capability, not cost.** Real fulltext has periodic
  structure — repeated section headers, boilerplate, tabular runs — and pinning a quote inside it often
  needs a **lookahead or lookbehind**. RE2 does not support either, so adopting it would narrow the
  pattern language the format offers authors, in exchange for a guarantee the subprocess already
  approximates. Revisit if `re` exhibits problems the process bound does not contain (a pattern that
  wedges a worker often enough to matter, or memory blow-up rather than time). If it happens, the shape
  is: keep `re` as the default, add `google-re2` as an optional accelerator, and record which engine
  ran — never silently change which patterns match.
- **Fulltext beyond the open-access subset** (candidate, cost-driven). OpenAlex and Unpaywall can point
  at a green-OA repository copy for some closed articles. Probed and *not* taken: the closed paper
  tested (`10.1038/s41580-019-0134-2`) has `is_oa: false` with no location at all, and the copies that
  do exist are PDFs — which would mean a PDF-parsing dependency in the network tier for a partial
  improvement on a check that is already labelled partial. The **abstract fallback shipped instead**,
  which costs nothing (the abstract is already in the Europe PMC response the pass makes) and covers
  four of five non-OA papers. Revisit only if authors report quotes that live in the body of closed
  papers often enough to matter.
- ~~**Google Scholar for citation existence**~~ — **rejected, not deferred.** It publishes no API, and
  automated querying violates its terms of service and is IP-blocked in practice. Crossref (DOIs,
  including preprints/books/datasets) and PubMed (indexed literature) cover the same ground through
  supported interfaces.


### The stale-identifier collision (design note, 0.5)

An obsolete authored rsID forces a choice that Principle 7 and "keep the module current" pull opposite
ways on, and it is worth writing down before anyone implements the lookup.

`weights.parquet` carries **both** `variant_key` and `rsid`, and for an rsid-authored row both are the
authored label. Writing the *updated* label into the artifact is not a one-time digest move — it is an
**identity migration performed by a network lookup**: reverse would then emit the new rsID into
`variants.csv`, the next compile would key on it, and `variant_key` itself would change. The module's
identity would drift without any authored edit, and the round-trip would stop being a fixed point.

So the rule is the one every other check here follows: **report, never repair.** Severity follows the
mode, matching the VRS-unverifiable decision exactly — `best_effort` warns and compiles with the
authored label (digest stable, round-trip intact), `strict` **refuses**, on the grounds that an
all-or-nothing artifact should not be built on an identifier its own source has retired. Failing is the
honest move because it pushes the fix to where it belongs: an authored edit.

Two refinements, both now settled by the 0.5 implementation:

- **Merged ≠ withdrawn — and withdrawn is not observable.** This entry used to say "probe the withdrawn
  shape before deciding", on the assumption that a withdrawn rsID deserved failing in both modes. The
  probe was done, and it dissolved the question rather than answering it: `rs11273140`, a genuinely
  *withdrawn* id, returns a response **byte-identical** to `rs2000000000`, which was never assigned —
  the same `error` string from `esummary`, the same `count=0` from `esearch`, the same Ensembl 400.
  Routes checked and rejected for separating them: `esearch` has no withdrawn filter (the phrase is not
  indexed), and `latest_release/misc/rs_unsupported_b157.txt` looks like a withdrawn registry but is a
  one-off build-157 ClinVar-parsing incident list that does not contain `rs11273140`. Separating them
  would need a historical dbSNP dump, not the live API. So the vocabulary is **`live|merged|absent`**,
  not `live|merged|withdrawn`, and `absent`'s *message* names both readings and asserts neither —
  because guessing "typo" sends an author to fix the wrong thing when the truth is that the variant
  itself was retracted. Severity is the same ladder for both (warn / fail in `strict`), not escalated
  beyond it, since `absent` has benign causes too (a very new rsID, or API lag).
- **The new columns are provenance, not facts.** `rsid_current` + `rsid_status` sit **outside**
  `RESOLUTION_FACT_FIELDS`, beside `rsid_alternates`. They describe time-varying *external* state;
  inside the fact set they would make `resolution_signature` change when dbSNP merges something, with
  no change to the module — the signature would stop being reproducible from the module's own content.
  (Shipped as specified, with a test that pins it.)

One consequence worth recording, since it was previously filed as a loose end: **`reverse_module` does
not carry these columns, and that is correct rather than a gap.** Reverse rebuilds `resolution.csv` from
`weights.parquet`, which by design holds no provenance — it already resets `source` to `reversed`,
`status` to `resolved` and blanks `fetched_at`. `rsid_alternates`/`rsid_current`/`rsid_status` are out
of the fact set *precisely* so they never reach the artifact, so the information does not exist for
reverse to emit; adding the column names would produce a permanently empty header. Recovering them
after a round-trip means re-running the enricher, which is where a statement about a reference at a
moment belongs. What reverse *does* now carry back correctly is the resolved **facts** and the authored
**shape** — see [COMPILER.md § Resolution](COMPILER.md) for the enumerated round-trip contract that
replaced the old "reverse emits position-only" rule.

**The strategic reading:** this whole class of problem is *label drift*, and it exists only for
rsid-keyed rows. A coordinate-authored row keys on a VRS allele id, which is content-addressed and
cannot drift. The obsolescence check is therefore the standing cost of the rsID key, and the format
already offers the escape — author coordinates and carry the rsID as data (reverse already emits
coord-keyed rows as position-only). A strict failure is the nudge toward the drift-proof key.

New ideas enter here as freeform suggestions, then graduate through the design cycle
(feedback → USE_CASES lens → PROPOSAL → shipped or parked as an `RMn` above).

## Reserved namespace

Because backward-compat makes column names and vocabularies **permanent within a major** (CONSTITUTION
Principle 5), a name expected to become a real **module column** later is reserved against the one-way
door and **must not** be claimed early or smuggled in as `flags`. This list is *only* for genuine
anticipated module-side axes — it is **not** a catalogue of names that "may not appear" (that space is
unbounded and pointless to enumerate; barring `caller` would be as arbitrary as barring `pasta_recipe`).
Audit every new name against this list before adding it.

**Enforced now** (the live set is `just_dna_format.vocab.RESERVED_NAMES_0_4`). Every authored model
inherits `AuthoredModel`, which sets `extra="forbid"` (rejects *any* unknown column) **and** runs the
`reject_reserved` before-validator, so a reserved name fails with a *specific* diagnosis — what it is
reserved for + that a release may claim it (`vocab.RESERVED_NAME_REASONS`) — while a random/misspelled
column gets the generic "extra inputs not permitted":
- **`reference_db`** — a module-side hint naming *which* reference database the app should join this
  annotation against when several exist (implicit Ensembl for variants / ClinVar for `clin_sig` today;
  a module may pin it, e.g. a specific PharmVar release). Annotation-side addressing, a real future axis.

*(**`callable_from` was reserved here through 0.4 and is now BUILT** as a `VariantRow` column in 0.5
(RM6). A built name must leave this list: `reject_reserved` refuses a reserved column at author time,
so leaving it would make the very column the release added unwritable.)*

*(`caller` / `caller_version` were reserved through the 0.4 draft as a "provenance triple" (round-2 Q2)
but are **dropped**: they name which tool produced a *call* — a consumer-side measurement, never module
annotation — so there is no future module axis to hold, and barring the bare name is arbitrary. A
consumer records them on its own call data; a module never carries them, and `extra="forbid"` rejects
them like any stray column. `reference_db` stayed because it has a real annotation-side meaning above,
not the caller-provenance one it was first reserved under.)*

**Planned future annotation axes** (documented intentions, **not yet in the enforced set** above — they
are rejected generically by `extra="forbid"` today, and get a slot + a specific diagnosis only when a
release actually commits to building them):
- **`consequence`** — VEP molecular consequence (Sequence-Ontology term, e.g. `missense_variant`).
  Distinct from `direction` (phenotypic) and `clin_sig` (clinical). **Never repurpose the bare word
  `effect`** for it.
- **`impact`** — VEP impact `{HIGH, MODERATE, LOW, MODIFIER}`, derived from `consequence`.
*(**`allele_frequency`** + **`af_population`** were listed here and are now **built in 0.5 as a
table, not a column** — `frequencies.csv` → `FrequencyRow`, one row per (allele, ancestry group).
A column pair could carry one number for one population; frequency is inherently per-group, and
flattening it onto the variant row would smear two axes together. So the planned axes are retired
rather than shipped. Gene-level constraint arrived beside it as `gene_metrics.csv`. See
[SCHEMAS.md](SCHEMAS.md) and [USE_CASES.md §6](USE_CASES.md).)*

*(`doi`, `provenance_quote`, and `provenance_regex` were reserved here for RM11/RM12 and are now **built**
as optional `StudyRow` columns in 0.4 — so they are absent from this list. The **doi-first** flip that
relaxes the mandatory `pmid` remains a 1.0 item; see the 1.0-cleanup tracker.)*

*(The ploidy / non-SNV quantities that were reserved through 0.3 — `allele_fraction` / heteroplasmy,
`repeat_count` + `repeat_unit`, copy-number dosage — are **built** as the 0.4 binning primitive; the
`hemizygous` genotype case ships via the widened single-allele genotype. Symbolic/structural alleles
remain open as RM5.)*

## The 1.0 cleanup (candidate tracker)

The **compatibility policy** — additive within a major, breaking cleanup only at a major bump, the
two-step deprecate→remove default — is a durable rule in [CONSTITUTION.md](CONSTITUTION.md)
(Principle 3). This is the **living tracker** of concrete items queued for the `→ 1.0` break; add
candidates as they surface.

**Additivity has two axes.** A new version may expand the **column-set** (new optional columns —
routine, digest-only-move while unpublished) *and* the **row-set** (one authored row compiling to
several — e.g. a one-to-many rsid → one row per locus). Row-set expansion changes identity
*cardinality* but is **not** a schema break: it is resolver behavior pinned on the `compiler_version`
axis (P4 already pins the digest to the resolved reference), so the GRCh38 expansion ships now. Only
the *build-aware* generalization (which/how-many loci per build, cross-build annotatability) is RM15.
The idea is to pile genuinely rule-tripping edge-cases (requiredness demotions, retypes, identity-key
*semantics* changes) on the 1.0/RM15 piles instead of forcing them into a minor.

Version-axis note: `schema_version` is `"1.0"` while the packages are `0.x` (now `0.4.0`). At `1.0`,
either align them or document explicitly that they track different things (wire format vs. package
release).

| Candidate | Why | Proposed disposition |
|---|---|---|
| `VariantRow.state` | Overloaded legacy field; a derived alias of `direction` since 0.3. | Deprecate at 1.0 (still read) → remove at 2.0, once consumers read `direction`/`stat_significance`. |
| `state` values `alt` / `ref` | Genotype-relative descriptors that never belonged; recoverable from `ref`/`alts`/`genotype`; not emitted since 0.3. | Drop from the accepted read-vocabulary at 1.0. |
| `VariantRow.pathogenic` / `benign` booleans | Lossy (can't express `likely_*`/`uncertain`); derived aliases of `clin_sig` since 0.3 (now materialized tri-state). | Deprecate at 1.0 → remove at 2.0. (`clinvar` provenance boolean stays.) |
| `StudyRow.p_value: str` | Untyped string holding a number; can't be compared/sorted numerically. | Add a numeric companion in 0.x if needed; retype/remove the string at 1.0 (breaking). |
| `weights.parquet` `end` column | Always set equal to `start` — no source column feeds it. | Remove outright at 1.0 (artifact-digest change, major-only) or wire it to a real end coordinate. **Re-examined in 0.5 and deliberately left here** rather than wired inside the window: an end coordinate needs the 0-based/1-based convention settled first, and the repo currently has that inconsistency in the open (`start`'s docstring says 0-based while the pipeline stores Ensembl's 1-based position, per the CPIC/PharmVar gotcha). Wiring a second coordinate onto an unsettled first one buys an off-by-one, not a feature. |
| `weights.parquet` `likely_pathogenic` / `likely_benign` | Always `False`; no CSV column feeds them — dead output. | Remove at 1.0, or wire to the `clin_sig` tier. **Re-examined in 0.5: removal is the answer, and wiring was rejected.** `clin_sig` is itself materialized into `weights.parquet` and `derive.pathogenic_from_clin_sig` already maps `likely_pathogenic → True`, so a wired column would tell a consumer nothing it cannot already read — it would spend the window's one free digest move on redundancy. |
| `VariantRow.weight` vs `effect_size` | Potential confusion — module-local score vs published magnitude (both kept, documented). | Review at 1.0 whether `weight` stays or is subsumed by `effect_size`. |
| Deprecated flag/vocab aliases | Any transitional vocab kept for 0.x compat (e.g. the trimmed-vs-full `state` set). | Collapse to the canonical vocab at 1.0. |
| `ModuleManifest.authors: list[str]` + free-form `curator` | Flat and overloaded — no role (created/edited/audited), no kind (AI/human); `Defaults.curator` smuggles kind via its `"ai-module-creator"` default. Superseded by the structured authorship record (RM14) once it ships. | Keep both as derived projections through 0.x (P8); at 1.0 fold `authors` into the structured record and drop the kind-smuggling `curator` default. |
| `StudyRow.pmid` required + PMID-shaped | Mandatory `pmid` (must parse to a real PubMed id) rejects DOI-only provenance — preprints (bioRxiv/medRxiv), books, theses, datasets. Demoting a required field is P8-forbidden in-major, so adding optional `doi` (RM11) alone can't unblock it. | **doi-first at 1.0**: make `pmid` optional/legacy and require **≥1 of `{doi, pmid}`** (every citation has a stable id, not necessarily a PMID; the reverse holds). Requiredness change → major-only. |
| Compiler `ensembl_cache` deprecated shim | 0.5 already moved the whole DuckDB resolver + cache-location into `just-dna-enricher` and dropped `duckdb`/`platformdirs`/`python-dotenv` from the compiler (it is now pure-Python; resolution is the `resolution.csv` table). What remains is the `compile_module(ensembl_cache=…)` **surface**, kept as a deprecated shim that emits `DeprecationWarning` and routes to the enricher via a guarded import. | Remove the `ensembl_cache`/`resolve_with_ensembl` params outright at 1.0 (internal call, not the wire/artifact contract, so additive-within-major does not protect it). |
| ~~Coordinate-first identity (option C)~~ — **resolved in 0.5** | The objection was that a coordinate key is *build-baked*. A **VRS allele id is not**: it names its reference sequence by refget accession, so it satisfies RM15's own reconsideration condition. `variant_key` now derives from the VA for a resolved substitution; rsid-keyed, position-only, indel and multi-allelic rows keep their previous keys. | **Done, in 0.5.0's pre-publication window** — an identity-semantics change is major-only because `variant_key` sits in `artifact.digest`, and that gate is *publication*, not the version number: 0.4 is the published line and 0.5.0 never shipped, so it rode the same one-time re-baseline as the alt-carrying key. No published artifact moved. |
