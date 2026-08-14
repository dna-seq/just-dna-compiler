# `RM` table of contents — every roadmap item and where it actually lives

**The single complete list.** Nothing else was: [ROADMAP.md](ROADMAP.md)'s detail table covers
RM4–RM7 / RM10–RM17 / RM20–RM27, [USE_CASES.md](USE_CASES.md)'s covers RM1–RM14 / RM18–RM22, neither is
sorted, RM28–RM35 lived only as prose paragraphs, and the major-version items are not numbered at all.
So `RM33` was genuinely unfindable. This file exists to make that impossible.

**Add an entry here whenever you add an item, and keep it sorted.** If you find yourself wanting a
second index somewhere else, don't — two lists of the same 35 things is what caused this.

Format of an entry: the **number** links to the authoritative entry, the one to edit. *also in* lists
every other document that mentions it, so a rename or a status change can be propagated without
grepping.

---

## ✅ Shipped

**0.4**

- **[RM1](USE_CASES.md#roadmap-items-surfaced)** — compiler materializes every 0.4 table → parquet, lossless round-trip. · *also in* ROADMAP, CHANGELOG
- **[RM2](USE_CASES.md#roadmap-items-surfaced)** — composed modules: `variants.csv` optional, a module carries only the kinds it uses. · *also in* ROADMAP, CHANGELOG, SCHEMAS
- **[RM3](USE_CASES.md#roadmap-items-surfaced)** ⚠ — PharmGKB row shape. **Superseded by RM20**, and the cautionary row: marked shipped against a hand-authored sample, then the real corpus rejected ~97% of itself. · *also in* ROADMAP, PROPOSAL_0_5
- **[RM8](USE_CASES.md#roadmap-items-surfaced)** — generated authoring reference (`authoring_reference()` / `json_schemas()`), reachable since 0.5 as `just-dna-compiler reference`. · *also in* ROADMAP, SCHEMAS, COMPILER, CHANGELOG
- **[RM9](USE_CASES.md#roadmap-items-surfaced)** — recommended colour / icon palette (`RECOMMENDED_COLORS` / `RECOMMENDED_ICONS`). · *also in* ROADMAP, COMPILER, CHANGELOG
- **[RM11](ROADMAP_HISTORY.md#rm11--doi-provenance-column-on-studyrow)** — `doi` provenance column on `StudyRow`. · *also in* USE_CASES, SCHEMAS, COMPILER, CHANGELOG
- **[RM12](ROADMAP_HISTORY.md#rm12--provenance-locator-provenance_quote--provenance_regex)** — provenance locator: `provenance_quote` / `provenance_regex`. · *also in* USE_CASES, SCHEMAS, COMPILER, CHANGELOG
- **[RM14](ROADMAP_HISTORY.md#rm14--structured-per-version-authorship)** — structured per-version `authorship` (identity / role / kind). · *also in* USE_CASES, COMPILER, CHANGELOG

**0.5**

- **[RM6](ROADMAP_HISTORY.md#rm6--callability-as-first-class-state)** — callability as first-class state: `requires_callable` + `callable_from`. · *also in* USE_CASES, SCHEMAS, COMPILER, CHANGELOG, PROPOSAL_0_5
- **[RM13](ROADMAP_HISTORY.md#rm13--the-network-first-resolution-tier)** — network-first resolution tier, **realized as `just-dna-enricher`**. · *also in* USE_CASES, CHANGELOG, PROPOSAL_0_5
- **[RM17](ROADMAP_HISTORY.md#rm17--semver-on-moduleversion-coercing)** — SemVer enforcement on `module.version`, coercing. · *also in* COMPILER, CHANGELOG, PROPOSAL_0_5
- **[RM18](USE_CASES.md#roadmap-items-surfaced)** — frequency + gene-constraint sidecars (`frequencies.csv`, `gene_metrics.csv`). · *also in* ROADMAP
- **[RM19](USE_CASES.md#roadmap-items-surfaced)** — GA4GH VRS allele identity: `vrs_id`, `caid`, VA-derived `variant_key`. Satisfies RM15's build-naming condition; multi-build minting stays RM15. · *also in* ROADMAP
- **[RM20](ROADMAP_HISTORY.md#rm20--pharmgkb-annotations-are-per-genotype-and-per-category)** — PharmGKB annotations are per-genotype **and** per-category. Corrects RM3. · *also in* USE_CASES, PROPOSAL_0_5
- **[RM21](ROADMAP_HISTORY.md#rm21--data-source-licensing-as-data)** — data-source licensing as data: `sources.csv` + the compile gate. · *also in* USE_CASES, COMPILER, ENRICHER, CHANGELOG, PROPOSAL_0_5
- **[RM22](ROADMAP_HISTORY.md#rm22--pgx-tables-join-resolution)** — PGx tables join resolution (`enrich()` reads the PGx CSVs too). · *also in* USE_CASES, PROPOSAL_0_5

*Found by dogfooding on 2026-08-03 — the batch of five that produced RM31–RM35. Four were fixed in that same window and are listed here; **RM32** was held back as a question about identity and shipped in 0.5, below. Each entry keeps the probe, the repairs that stayed rejected, and (for three of the five) the part of the original argument that turned out to be wrong on probing.*

- **[RM31](ROADMAP_HISTORY.md#rm31--one-indel-spelled-two-ways-defeats-allele-aware-resolution)** — ✅ **shipped in 0.5**: ClinVar's `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the same 2 bp deletion, and string comparison called it `not_found`. Closed by a frame-free parsimony reduction with a tri-state verdict; one residual (the authored genotype keeps its source's frame) is stated there. · *also in* CLAUDE.md, SCHEMAS, COMPILER, CHANGELOG
- **[RM33](ROADMAP_HISTORY.md#rm33--source-names-two-different-things-in-two-tables)** — ✅ **shipped in 0.5**: `source` named a *link* in `resolution.csv` and a *licensed source* in `sources.csv`, compared by string equality. Closed by `ResolutionRow.authority` + the link→authority map in the enricher; the two repairs the entry rejected stayed rejected. · *also in* CLAUDE.md, SCHEMAS, ENRICHER, CHANGELOG
- **[RM34](ROADMAP_HISTORY.md#rm34--the-cpic-provider-has-no-filter)** — ✅ **shipped in 0.5**: CYP2D6 drafted 16,290 rows, 73% `Indeterminate`, with no way to take a subset. Closed by `draft --allele`, applied to all three tables; six alleles make CYP2D6 21 diplotypes. · *also in* ENRICHER, CHANGELOG
- **[RM35](ROADMAP_HISTORY.md#rm35--a-continuous-binning-table-cannot-be-tiled-without-a-finding)** — ✅ **shipped in 0.5**: inclusive bounds + overlap-is-error + hole-is-warning were jointly unsatisfiable on a continuous measure. Resolved as *a shared endpoint is a boundary and the higher bin owns it*; half-open bounds lost on authorship. · *also in* CLAUDE.md, SCHEMAS, create-module skill, CHANGELOG
- **[RM37](ROADMAP_HISTORY.md#rm37--content_signature-counted-where-a-value-was-written)** — ✅ **shipped in 0.5**: `compile → reverse → compile` moved `content_signature` for a module authoring `curator`/`method` per row, because reverse re-emits the value under `defaults:` and the hash read the CSVs before defaults applied. Closed by resolving `defaults:` into each row *before* hashing, reusing RM36's omit-the-model-default normalization so only a module stating something non-built-in moves (one of eleven reference examples). Also closed an unfiled defect: two modules differing only in `defaults.curator` hashed **equal**. The other two candidate repairs stayed rejected, with reasons. · *also in* CLAUDE.md, create-module skill, CHANGELOG
- **[RM36](ROADMAP_HISTORY.md#rm36--a-model-property-cannot-know-its-modules-build)** — ✅ **shipped in 0.5**: a model *property* that mints an identity had no module in scope, so `HeteroplasmyRow.variant_key` gave a GRCh37 module's locus a GRCh38 VA while `variants.csv` gave it a coordinate key. Closed by **injection** — the loader *tells* each row the build via a `PrivateAttr`, so the declaration stays in `module_spec.yaml` alone and reaches no CSV, parquet or digest. Per-row and per-CSV ("service row") declaration were both rejected, with reasons. Carried the correction that `content_signature` was **not** build-independent: it now hashes a non-default `genome_build`, leaving every GRCh38 module's signature untouched. · *also in* CLAUDE.md, SCHEMAS, CHANGELOG

*The post-cut round of the same 0.5.0, which was still unpublished at the time. These carried a `0.5.1`
label for a while; no 0.5.x had been published, so they shipped as 0.5.0 like everything above — see the
note at the top of [CHANGELOG.md](CHANGELOG.md). **0.5.0 released 2026-08-07.***

- **[RM26](ROADMAP_HISTORY.md#rm26--all-three-drafting-providers)** — all three drafting providers: CPIC, ClinPGx, ClinVar. Partially dissolves RM4. · *also in* ENRICHER, CHANGELOG
- **[RM29](ROADMAP_HISTORY.md#rm29--cofactor-columns)** — cofactor columns: `quality_from` / `min_quality` on `VariantRow`, `clinical_context` on `DiplotypeRow`. Dissolved the `draft --population` refusal. · *also in* CHANGELOG
- **[RM30](ROADMAP_HISTORY.md#rm30--one-rule-for-a-haplotype-name-across-all-three-pgx-tables)** — one haplotype-name rule across all three PGx tables. · *also in* REFERENCE_EXAMPLES, CHANGELOG
- **[RM32](ROADMAP_HISTORY.md#rm32--a-pseudoautosomal-locus-is-one-place-on-two-contigs)** — ✅ **shipped in 0.5**, the fifth of the 2026-08-03 dogfooding batch and the one held back as a question: a pseudoautosomal locus is one place on two contigs, modelled as two variants (10 SHOX findings → 20 rows). The probe the entry named **refuted** its own preferred direction — ClinGen mints two CA ids per PAR base, so there is no place identity to adopt — while the objection that had parked the enricher policy also failed: ClinVar and gnomAD place PAR annotation on X exclusively, so selecting X records the *sources'* convention, not the consumer's analysis set. Closed by `vrs.par_partner` + X-spelling selection (`--keep-par-twin` keeps both), per locus because XG and SPRY3 straddle a boundary. Carried a false-absence fix in `frequencies.csv` (`not_covered`) with it. · *also in* CLAUDE.md, SCHEMAS, ENRICHER, COMPILER, create-module skill, REFERENCE_EXAMPLES, CHANGELOG

**0.5.1 — the network tier alone (enricher + compiler; format untouched at 0.5.0)**

*Not a schema release. Every item is enricher/compiler API shape, out of `artifact.digest`, and touches
no parquet — which is what makes a patch legal inside the closed 0.5 digest window (P3/P8). RM38 came
from design; RM39–RM42 are a `just-dna-registry` **consumer field report**, and the through-line is one
this codebase already makes elsewhere: a number this workspace computed and then discarded gets
recomputed by every consumer, and a recomputation is a place to drift.*

- **[RM38](ROADMAP_HISTORY.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher)** — ✅ **shipped in 0.5.1**: the three licence-gated PGx sources were the only ones with no cache, so a **hosted** enricher either fetched them live per request on the operator's own credentials or skipped the check. Closed by `cpic_build`/`pharmvar_build`, `locations.resolve_{cpic,pharmvar,clinpgx}_reference`, `download.ensure_{cpic,clinpgx}_snapshot`, duckdb snapshot clients duck-typed against the live ones, and a real `--offline` on `pgx`/`draft`. **PharmVar is build-only** — its key is personal and non-transferable, so no publish and no `ensure_*`. Two prerequisite defects fixed on the way (`LICENSE.txt` never published; the layout constants imported from a `[dev]` builder) and two integration defects found by probing (PharmVar's GRCh37-first coordinates; CPIC's `gene.chr`). · *also in* CLAUDE.md, ENRICHER, CHANGELOG
- **[RM39](ROADMAP_HISTORY.md#rm39--one-pass-in-the-family-ignored-offline)** — ✅ **shipped in 0.5.1**: `enrich_dosage_sensitivity` was the only pass with no `offline` parameter, so one member of a family run under one flag egressed on a path documented as making none. Closed additively: the flag, `ClinGenResult.skipped_offline`, `--offline` on `dosage`. An injected `curation_text` still wins — that is not egress. · *also in* ENRICHER, CHANGELOG
- **[RM40](ROADMAP_HISTORY.md#rm40--vrs-coverage-was-computed-and-thrown-away)** — ✅ **shipped in 0.5.1**: `enrich()` computed the `MintResult` the compiler later stamps into the manifest and dropped it, so a pre-compile consumer re-implemented per-ALT-slot counting and could disagree with the manifest a publish would produce. Closed by `EnrichmentResult.vrs`; `None` when the pass did not run, never a coverage of zero. · *also in* ENRICHER, CHANGELOG
- **[RM41](ROADMAP_HISTORY.md#rm41--the-only-correct-csv-loader-was-private)** — ✅ **shipped in 0.5.1**: `compiler._load_csv_rows` was private and the only correct authored-CSV loader, so consumers chose between a private symbol and a re-implementation with two known traps. Closed both ways: `compiler.load_csv_rows` is public (old name kept as an alias), `compiler.load_spec_variants` does the build injection and re-stamp, and `verify_acmg_sf`/`check_identifiers` accept `spec_dir=` beside `variants=`. · *also in* COMPILER, ENRICHER, CHANGELOG
- **[RM42](ROADMAP_HISTORY.md#rm42--the-retry-ceiling-was-an-import-time-constant)** — ✅ **shipped in 0.5.1**: nine `stop_after_attempt(3..4)` decorator arguments with no setting, so a server inside an unattended publish could not ask for more persistence than an author at a terminal wants; a consumer was walking the package to reassign `policy.stop`. Closed by `net.attempt_floor` + `$JUST_DNA_HTTP_RETRY_ATTEMPTS` — a **floor** that preserves the deliberate per-client tuning, never a flat set. · *also in* ENRICHER, CHANGELOG


## ✅ Also shipped in 0.6.0

- **[RM44](ROADMAP_HISTORY.md#rm44--fully_resolved-answers-a-question-nobody-asked-it-and-prose-is-the-only-record-of-the-real-one)** — ✅ **shipped in 0.6.0**: `fully_resolved` is `all()` over `variants.csv`, hence **vacuously true** for a table-only module, and a catalog following the documented trust rule served `trusted: true` for modules that join to no VCF. Fixed downstream by substring-matching the 0.5.3 warning's prose, which makes a sentence load-bearing (`compiler.UNJOINABLE_PHRASE` pins it meanwhile). The fix is one additive integer — `resolution_subjects` — beside the flag, the same parts-not-conveniences pattern as `vrs_alleles`. Do **not** make the flag `None`-able, and it does **not** retire `UNJOINABLE_PHRASE` (that count belongs with RM43). Counted after rsID expansion, since that is the list the flag iterates. One thing the item missed and the history entry records: the number was already available as `Stats.weights_rows` — publishing it beside the flag is still right, because that equality is a property of the materializer rather than a contract and `Stats` is display facets, but *check for an existing carrier before adding a computed field*. · *also in* CLAUDE.md, COMPILER, CHANGELOG, CONSUMER_SUGGESTIONS § S13

- **[RM49](ROADMAP_HISTORY.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses)** — ✅ **shipped in 0.6.0**, together with RM51 and sharing its resolver: nothing in a spec listing says which files a human wrote and which the enricher produced, so a registry gave publishers a `derived/` tree and found it is one `compile` refuses; their layout stays transport-only (flatten on upload, re-split on download). The byte-attestation half of S26 shipped as `manifest.derived` in 0.6.0; this is the half that did not. Not the one-line fallback it looks like: `spec_dir / "resolution.csv"` is resolved in **eight places across two packages**, and tolerating the layout on *input* without deciding the *write* side breaks on first use — `enrich` on a downloaded split module writes to the root, producing the both-copies-present collision by following the documented workflow. Three candidate repairs named and refused: search any subdirectory (blinds `_check_misspelled_tables`, re-opening S16's hole), make `derived/` canonical (two supported layouts, and `reverse` emitting a tree older compilers in the same major cannot read), extend it to authored tables (two legal homes for `variants.csv`, so the ignored copy is invisible). Shipped as `just_dna_format.layout` — tolerated, never canonical; write to the file you read; both present is an error naming both. Two things the item did not record: `_check_misspelled_tables` had to be extended into the subdirectory or a single fixed name blinds it just as a tree walk would, and `manifest.derived` carries the relative path so a re-splitting registry can use it. · *also in* CHANGELOG, CONSUMER_SUGGESTIONS_HISTORY § S26

- **[RM51](ROADMAP_HISTORY.md#rm51--licensingcsv-land-the-better-name-in-a-minor-so-the-major-only-has-to-remove)** — ✅ **shipped in 0.6.0**: accept `licensing.csv` as a second spelling of `sources.csv` in 0.6 (enricher writes it, compiler falls back to it), so the 1.0 rename only has to **remove** a spelling rather than add one. Minor-legal for a checked reason: the fact sidecars are **not** in `_INPUT_FILES`, so the filename enters no identity — `content_signature` is rows, `source_signature` is facts, `manifest.derived` is transport-only. What cannot come along is `sources.parquet` (inside `artifact.digest`, read by name) and the `manifest.sources` key — both removals, both major — so the 0.x tail reads `licensing.csv` → `sources.parquet` → `manifest.sources`, which is the cost. Both files present is RM49's collision (fact-hashed and human-overridable, so no merge and no newest-wins) — write to the file you read, error naming both; the two items shipped together for exactly that reason. The item estimated **five** enricher write sites and there were **nine**, so `record_source_terms`/`merge_sources_file` take the spec directory now and no pass names a spelling by hand. Old spelling deprecated in 0.6, removed at 1.0. · *also in* CHANGELOG, SCHEMAS, COMPILER, ENRICHER

## ✅ The 0.6 design round — decided, then built

*All decided on 2026-08-13 in [PROPOSAL_0_6.md](PROPOSAL_0_6.md) and **all built** in the batch that
followed; the outcome of each, with what probing changed along the way, is in
[ROADMAP_HISTORY § 0.6.0](ROADMAP_HISTORY.md#060--the-design-round-built). The proposal stays the
authoritative record of the **reasoning**: the problem, the facts probed, the decision, **the repairs
that were rejected and why**, and the consequences that follow without being chosen — which is the half
worth not re-deriving. Where an entry below and the built result disagree, the history entry wins.
RM53–RM67 came from [VCF_4_4_AUDIT.md](VCF_4_4_AUDIT.md), which stays the evidence document (spec
quotations, `file:line`, probe transcripts).*

*Landed on the `0.6` branch in eleven parallel lanes plus a charter amendment that went first and alone
(schema-change cost by layer: a parquet column is ~free, a derived CSV half, an authored schema full —
four of the decisions turn on it). Corpus effect, measured: `content_signature` moved on **two** modules
(both re-authored on purpose), `artifact.digest` on seven, `resolution_signature` was **gained** by the
four table-only modules that never had one, and the source signature moved nowhere. Suite 1535 → 2046.*

- **[RM4](PROPOSAL_0_6.md)** — gene-panel materialization. **Off the compiler**: the surface is enricher draft-scaffolding, and the author's no-op over the drafted subset is the authorial act. Takes the `panel:` block with it (deprecated, machine-recorded release replaces it) and re-keys the tautology check on a mode ladder. · *also in* ROADMAP_1_0, USE_CASES, ENRICHER
- **[RM5](PROPOSAL_0_6.md)** — symbolic / structural alleles. **The five closed VCF first-level types and nothing beyond the standard** — no declaration mechanism, no named aliases. 5-HTTLPR is a plain indel; CPIC's IUPAC codes stay unexpressible, deliberately. · *also in* CLAUDE.md, USE_CASES, SCHEMAS, ENRICHER, REFERENCE_EXAMPLES
- **[RM24](PROPOSAL_0_6.md)** — gene–disease validity (ClinGen, GenCC, HPO). **Build it, as a derived sidecar** — machine-written, half cost, new non-tainting `gene_validity` source layer. · *also in* CLAUDE.md
- **[RM25](PROPOSAL_0_6.md)** — ClinVar assertion tier. **Build it, as a derived sidecar.** Compute-and-discard, the fourth instance.
- **[RM27](PROPOSAL_0_6.md)** — redistribution. **Record only**, verdict in the manifest; no gate in these four packages. Enforcement is an explicit downstream ask on the registry at 0.6 integration. · *also in* CLAUDE.md, SCHEMAS, COMPILER
- **[RM43](PROPOSAL_0_6.md)** — resolution reaches the SNP core only. **Fill the positional parquets**, plus a stamped parquet-only authored-identity column per model and a materialized join key; `alts` on the pharm table as data, not identity. No `resolution.parquet`. Reverse must rebuild the lookup table (forced by P7). · *also in* CLAUDE.md, COMPILER, ENRICHER, CONSUMER_SUGGESTIONS § S9
- **[RM45](PROPOSAL_0_6.md)** — the manifest cannot say what was verified. A derived attestation sidecar, hash-bound with one ~1s proof-of-work **per sidecar** and a deterministic nonce; stale ⇒ warn and drop the block; two closed vocabularies; a `Verification` block. Depends on RM43. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S8
- **[RM46](PROPOSAL_0_6.md)** — per-article literature terms. **Licence columns on the derived literature row**; quoting a restrictive article **warns, never gates**. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S10
- **[RM47](PROPOSAL_0_6.md)** — a threshold has nowhere to cite. **A pointer on the bin row, and the citation subject relaxed.** The bin cites, the citation table describes. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S19, SCHEMAS, COMPILER
- **[RM48](PROPOSAL_0_6.md)** — old-assembly coordinates. **rs-number recovery only, no liftover, no chain file** — Ensembl's permanent GRCh37 REST service removes the stated blocker. Plus an author-time wrong-build diagnosis, split offline (compiler, fatal) / online (enricher, hints). · *also in* CONSUMER_SUGGESTIONS_HISTORY § S22
- **[RM50](PROPOSAL_0_6.md)** — PubMed vs PubMed Central ids. Guard + the PMC id on the derived row + a reporting reverse lookup. The authored half is 1.0 with the requiredness demotion.
- **[RM53](PROPOSAL_0_6.md)** — a bare VCF field name means two different fields (`DP`, `AD`, `MQ`, `AF`, `CN`). Accept the qualified form; warn on a bare colliding name. **Both shipped reference examples are wrong today.** · *from* VCF_4_4_AUDIT § 1
- **[RM54](PROPOSAL_0_6.md)** — a pointer at a multi-valued field cannot say which value. A **closed vocabulary of selection rules**, never an index. Shipped on the binning base's `source_field` **only** — `callable_element`/`quality_element` are **reserved, not built**: `callable_from` and `quality_from` can name a multi-valued field too and no module does, and an authored column on `variants.csv` is full cost under the 0.6 amendment. Additive whenever a real case arrives (P3), the names held in `RESERVED_NAMES_0_4` so they survive the one-way door, and everything reading `VCF_POINTER_COMPANIONS` is generic over it. The proposal reads as though the rule reached all three columns; this is the built shape. · *from* VCF_4_4_AUDIT § 2
- **[RM55](PROPOSAL_0_6.md)** (0.6 half) — copy number and repeat count are not whole numbers. **0.6 warns loudly and changes nothing.** Fix in [ROADMAP_0_7](ROADMAP_0_7.md), removal in [ROADMAP_1_0](ROADMAP_1_0.md). · *from* VCF_4_4_AUDIT § 3, § 4
- **[RM56](PROPOSAL_0_6.md)** (0.6 half) — a measurement can span several bins. **0.6 withholds and says loudly that no policy exists.** Policy vocabulary in [ROADMAP_0_7](ROADMAP_0_7.md). · *from* VCF_4_4_AUDIT § 4
- **[RM57](PROPOSAL_0_6.md)** — a quality floor inverts on reference records; callability evidence is a block, wanting interval containment and the block minimum. Docs + warning. · *from* VCF_4_4_AUDIT § 5
- **[RM58](PROPOSAL_0_6.md)** — `alts="."` splits identity. A diagnosis, not a grammar; stop filing the MISSING marker beside symbolic alleles. **The only VCF finding reaching identity.** · *from* VCF_4_4_AUDIT § 6a
- **[RM59](PROPOSAL_0_6.md)** — `*`, the allele that could not be observed. **Writable, and the contract states the withhold rule.** Decided beside RM5, deliberately not inside it — `*` names no variant, it makes an observability claim. · *from* VCF_4_4_AUDIT § 6b
- **[RM60](PROPOSAL_0_6.md)** — `chrom` rejects `chrM` while a normalizer in the same package accepts it. Widening only. · *from* VCF_4_4_AUDIT § 7
- **[RM61](PROPOSAL_0_6.md)** — the pointer grammar rejects VCF-legal keys (`1000G`, dotted). Widening only. · *from* VCF_4_4_AUDIT § 8a
- **[RM62](PROPOSAL_0_6.md)** — 32-bit values against 64-bit inclusive upper bounds. Consumer contract, no schema change. · *from* VCF_4_4_AUDIT § 8b
- **[RM63](PROPOSAL_0_6.md)** — a pipe-separated genotype names no homolog without a phase set. Docstring correction. · *from* VCF_4_4_AUDIT § 8c
- **[RM64](PROPOSAL_0_6.md)** — the VCF id column is a semicolon list. Documentation. · *from* VCF_4_4_AUDIT § 8e
- **[RM65](PROPOSAL_0_6.md)** (0.6 half) — repeat and copy-number tables *are* positional and the code says they are not. **0.6 corrects the claim**; the coordinates wait in [ROADMAP_0_7](ROADMAP_0_7.md). · *from* VCF_4_4_AUDIT § 10

## ⏳ Deferred to 0.7 — [ROADMAP_0_7.md](ROADMAP_0_7.md)

- **[RM16](ROADMAP_0_7.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest)** — authored PRS weights. Not derivable, so a full-cost authored table, and no consumer combines authored weights into a score. · *also in* SCHEMAS, PROPOSAL_0_5
- **[RM23](ROADMAP_0_7.md#rm23--computational-predictor-scores-as-a-table)** — predictor scores (`predictions.csv`). Both blockers unmoved: per-transcript grain, and the acquisition measurement. Licensing is **not** the blocker. · *also in* CLAUDE.md
- **[RM28](ROADMAP_0_7.md#rm28--meta-conclusions-the-predicate-half)** — meta-conclusions, the predicate half only. Parked on a corpus. **The general injected-cofactor mechanism was dropped on 2026-08-13** as never-earned; each class gets a plain column on demand. · *also in* COMPILER, REFERENCE_EXAMPLES, PROPOSAL_0_5 § G3
- **[RM55](ROADMAP_0_7.md#rm55--copy-number-and-repeat-count-are-not-whole-numbers-the-usable-fix)** (the fix) — a parallel float column beside the integer one, integer deprecated. The charter-clean half of the three-release route.
- **[RM56](ROADMAP_0_7.md#rm56-policy-half--the-rule-for-a-measurement-that-spans-bins)** (the policy) — withhold / worst bin / point estimate, as a closed vocabulary. Gated on real caller output; grain undefined on purpose.
- **[RM65](ROADMAP_0_7.md#rm65-implementation-half--repeat-and-copy-number-tables-are-positional)** (the coordinates) — gated on a real repeat-caller or CNV VCF, or a consumer report. Would take RM43's lane from three tables to five.
- **[RM66](ROADMAP_0_7.md#rm66--one-repeat-locus-several-motifs)** — one repeat locus, several motifs; the key cannot say which count the thresholds describe. Same prerequisite as RM65.
- **[RM67](ROADMAP_0_7.md#rm67--polyploid-and-partially-phased-genotypes)** — polyploid / partially-phased genotypes. **Not work** — a documented divergence, numbered so it is findable and not re-probed.

*The five 0.6 dogfooding findings the ledger classes **surface** rather than **fix** — the repair is
itself a design decision, so each entry carries the candidates and why each one fails. The eleven other
findings of that batch were fixed in the round that found them.*

- **[RM68](ROADMAP_0_7.md#rm68--a-drafting-provider-on-a-non-grch38-module-refuse-or-strip-to-the-rsid)** — a drafting provider on a non-GRCh38 module: refuse, or strip to the rsID. The **warning** shipped in 0.6 (`enrich.source_build_mismatch`); the behaviour is open. Refusal makes a GRCh37 module undraftable; stripping drops the 36 CPIC defining variants that have a position and no rsID. Probably dissolved by RM15. · *from* DOGFOOD_0_6_FINDINGS § D2 (F1)
- **[RM69](ROADMAP_0_7.md#rm69--resolution_signature-is-not-a-round-trip-invariant-when-the-positional-fill-is-skipped)** — `resolution_signature` moves across the round trip on a non-GRCh38 module carrying a positional table. **Not a Principle 7 breach** — `resolution.csv` is a derived sidecar, and P7's own next sentence (*"the artifact is missing a field, not the spec"*) is the diagnosis. Blocked on RM15. · *from* DOGFOOD_0_6_FINDINGS § D2 (F8), measured in § D6
- **[RM70](ROADMAP_0_7.md#rm70--requires_callable-is-variantrow-only-so-no-pgx-table-can-state-cpics-core-assumption)** — `requires_callable` is `VariantRow`-only, so a star-allele module cannot record the assumption CPIC states in prose. Additive and minor-legal; the open question is which of the three PGx tables owns it — `haplotypes.csv` and `pharm_variants.csv` name a position, `diplotypes.csv` does not. **Not** gated on RM65/RM66's caller VCF. · *from* DOGFOOD_0_6_FINDINGS § D2 (F11)
- **[RM71](ROADMAP_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file)** — a drafted `genotype` stub must be written from alleles the file does not carry, emitted once to stdout and not re-requestable. Every legal home is also the wrong home; the real question is where an author does the work. · *from* DOGFOOD_0_6_FINDINGS § D4 (D4-3)
- **[RM72](ROADMAP_0_7.md#rm72--six-verification-members-still-emitted-by-nothing-and-the-writes-nothing-contract)** — the remainder of D4-1 after six members were wired: **four** blocked on the printed *"Writes nothing"* contract of `check-identifiers`/`check-acmg`, **two** deliberately reserved (`gene_disease_validity`, `dosage_sensitivity`), one open question about read-only surfaces, and one about the merge rule — `merge_records` is *newest wins, per check*, so an offline re-run downgraded a real `subjects=2 findings=1` verdict to `skipped=offline`. · *from* DOGFOOD_0_6_FINDINGS § D4 (D4-1)

## 🔒 Deferred to 1.0 — [ROADMAP_1_0.md](ROADMAP_1_0.md)

- **[RM15](ROADMAP_1_0.md#rm15--build-agnostic-identity--multi-build-support)** — build-agnostic identity & multi-build support. A major because it changes the *semantics* of `variant_key` and of every coordinate — not for digest reasons. The build-naming half shipped as RM19. **Not RM48**, which is one-way and authoring-time. · *also in* USE_CASES, SCHEMAS, COMPILER, PROPOSAL_0_5
- **[RM52](ROADMAP_1_0.md#rm52--10-ships-an-upgrade-procedure-or-10-does-not-ship)** — the upgrade procedure. **Release-blocking by charter.** Decided 2026-08-13: the 0.6 batch owes **no** per-item ledger rows — that is premature decision-making, and the obligation belongs at 1.0.
- **[RM55](ROADMAP_1_0.md#rm55-removal-half--the-integer-copy-number-and-repeat-count-columns)** (the removal) — the integer columns and the integer tiling semantics. The only genuinely major part of the three-release route.
- Plus the unnumbered items in [ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker), which stays where it is.

## ✖ Closed as an item

- **RM10** — declarative inheritance expectation. **Folded into RM28 on 2026-08-13**: it is an injected cofactor (family structure arrives at query time, exactly like ancestry), so designing it separately would fix a shape for one class before the axis exists. Reasoning lives in [ROADMAP_0_7 § RM28](ROADMAP_0_7.md#rm28--meta-conclusions-the-predicate-half). · *also in* USE_CASES, PROPOSAL_0_5

## — Not format scope

- **[RM7](ROADMAP.md#rm7--evaluation-output--report-card-schema)** — evaluation / report-card schema. Per-sample results are a *measurement*, so this is a **consumer** contract (`just-dna-lite`). Listed only so it is not mistaken for format scope. · *also in* USE_CASES, COMPILER, PROPOSAL_0_5

## 🔒 The major bucket — unnumbered on purpose, and that is why it hides

Everything needing a **major** lives in one table in
[ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker). These have **no `RMn`
number**, which is why they are easy to lose. They are not deferred features — each breaks a rule
Principle 3/8 protects, so a minor cannot carry it.

**Read this list under the amended cadence** (CONSTITUTION § 0.6 amendment, 2026-08-12): *deprecate in a
minor, remove at the next major*. An item whose replacement already exists takes its warn-only
deprecation in a 0.x release and is **gone at 1.0**, not deprecated at 1.0 and lingering to 2.0 — the
entries below still phrased the old way are stale, not decided. What genuinely keeps the old shape is
whatever Principle 8 makes mandatory (`state`, the `pathogenic`/`benign` booleans), because an author
cannot comply with a warning about a field they must still set. Every item here also owes an upgrade
line under **RM52**, which is release-blocking for 1.0.

- `VariantRow.state` — deprecate at 1.0, remove at 2.0; a derived alias of `direction` since 0.3
- `state` values `alt` / `ref` — drop from the read-vocabulary; genotype-relative descriptors
- `VariantRow.pathogenic` / `benign` — deprecate → remove; lossy aliases of `clin_sig`
- `StudyRow.p_value: str` — retype (the numeric companion `p_value_num` shipped in 0.5)
- `weights.parquet` `end` — remove or wire; needs an *end*-coordinate convention (interbase-half-open vs inclusive), same as RM15. The authored `start` is settled: 1-based VCF POS, pinned by a test
- `weights.parquet` `likely_pathogenic` / `likely_benign` — remove; dead output, wiring rejected in 0.5
- `VariantRow.weight` vs `effect_size` — review whether `weight` is subsumed
- Deprecated flag / vocab aliases — collapse to the canonical vocab
- `ModuleManifest.authors` + free-form `curator` — fold into RM14's structured record
- `StudyRow.pmid` required — **doi-first**: require ≥1 of `{doi, pmid}`; a requiredness demotion. Pairs with RM50, which carries the PMCID axis and the `LiteratureRow` key
- `sources.csv` — **rename** (recommendation: `licensing.csv`). The *input* half is RM51 and lands in 0.6; what waits for the major is `sources.parquet` (inside `artifact.digest`) and the `manifest.sources` key — both removals. The old CSV spelling is deprecated in 0.6 beside the alias and **removed at 1.0**, on the amended cadence this item prompted. It is a licensing/attribution ledger whose name collides with the `source` *column* meaning "which link answered" (the overload RM33 had to split) and with the ordinary sense in which `studies.csv`/`literature.csv` are sources too
- Compiler `ensembl_cache` shim — remove the deprecated parameter outright
- ~~Coordinate-first identity~~ — **resolved in 0.5** by VRS; kept struck through for traceability

## The other trackers

| Tracker | Where | What it holds |
|--------------|----------------------|----------------------------------------------------------------|
| Reserved namespace | [ROADMAP § Reserved namespace](ROADMAP.md#reserved-namespace) | Names withheld because a release will plausibly claim them (Principle 5). Currently just `reference_db`. |
| Freeform idea-book | [ROADMAP § Freeform suggestions](ROADMAP.md#freeform-suggestions--the-05-idea-book) | Unshaped ideas, plus **Parked in 0.5** — recorded so they are not re-proposed as new. |
| Not format scope | [ROADMAP § Annotating core](ROADMAP.md#annotating-core-not-format-scope-the-05-source-assessment) | Half of every source assessed: anything that *calls or interprets* is a consumer's job. |
| Design threads | [PROPOSAL_0_5.md](PROPOSAL_0_5.md) | Where an item's shape was argued before it became an `RMn`. |
| What shipped | [CHANGELOG.md](CHANGELOG.md) | Newest first. The statuses above summarize it. |

## Where an item comes from

An `RMn` is stage 5 of the design cycle, not its start: a field report
([CONSUMER_SUGGESTIONS](CONSUMER_SUGGESTIONS.md)) → run it against the bricks
([USE_CASES](USE_CASES.md)) → shape it ([PROPOSAL_0_5](PROPOSAL_0_5.md)) → then either **shipped**
(recorded in [COMPILER.md](COMPILER.md)'s coverage table) or **parked as an `RMn`**. An item with no
trail through those was usually found by dogfooding — RM31–RM35 all were.
