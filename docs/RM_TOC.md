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


## ⏳ Deferred — additive, lands in a minor (0.6+)

*Sorted by the 2026-08-11 charter amendment: a new **optional** column or table is additive and
minor-legal, while **removal, promotion to required and retyping** are what a major is for. **RM15**
stays 1.0 on its own merits — it changes the semantics of `variant_key` and of every coordinate — and
**RM10**'s placement gate dissolved. The full sort is [ROADMAP § 0.6](ROADMAP.md#06--what-a-minor-permits).*

- **[RM4](ROADMAP.md#rm4--native-clinvar-gene-panel-materialization)** — native ClinVar gene-panel materialization at compile time. The injectable-reference half is unblocked; compile-time materialization is what stays parked. · *also in* USE_CASES, ENRICHER, CHANGELOG, PROPOSAL_0_5
- **[RM5](ROADMAP.md#rm5--symbolic--structural-alleles)** — symbolic / structural alleles (`<DEL>`, 5-HTTLPR, ClinPGx `del`/`ins`, CPIC's `x≥3`). · *also in* CLAUDE.md, USE_CASES, SCHEMAS, ENRICHER, REFERENCE_EXAMPLES, CHANGELOG, PROPOSAL_0_5
- **[RM10](ROADMAP.md#rm10--declarative-inheritance-expectation-field)** — declarative inheritance-expectation field (trio / de-novo). *On demand only*; the placement question is now design-only (column, own table or yaml metadata are all minor-legal — pick on orthogonality). · *also in* USE_CASES, PROPOSAL_0_5
- **[RM15](ROADMAP.md#rm15--build-agnostic-identity--multi-build-support-other-builds-support)** — build-agnostic identity & multi-build support (refget tables beyond GRCh38). **A 1.0 item** — it changes the *semantics* of `variant_key` and of every coordinate, which is the identity-change class a major exists for. Paired with the `end`-column item in the major bucket: both need the coordinate convention *for a second coordinate* settled (interbase-half-open vs inclusive). The authored-`start` half closed in 0.5 — it is 1-based VCF POS and now says so. · *also in* USE_CASES, SCHEMAS, COMPILER, CHANGELOG, PROPOSAL_0_5
- **[RM16](ROADMAP.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest)** — authored PRS weights: a scoring file, not a `pgs.csv` manifest. · *also in* SCHEMAS, PROPOSAL_0_5
- **[RM23](ROADMAP.md#rm23--computational-predictor-scores-as-a-table)** — computational predictor scores as a table (`predictions.csv`), long-form. Deferred on grain + acquisition, not on code. · *also in* CLAUDE.md, CHANGELOG
- **[RM24](ROADMAP.md#rm24--genedisease-validity-as-a-table)** — gene–disease validity as a table (`gene_validity.csv`): ClinGen, GenCC, HPO from one shape. · *also in* CLAUDE.md
- **[RM25](ROADMAP.md#rm25--clinvar-assertion-tier-as-artifact-data)** — ClinVar assertion tier persisted as artifact data. Not the same as escalating the check's severity.
- **[RM27](ROADMAP.md#rm27--a-redistribution-compile-gate)** — a redistribution compile gate. A distribution right is not a *use*, so `declared_use` is the wrong axis; needs the third axis designed first. · *also in* CLAUDE.md, SCHEMAS, COMPILER, CHANGELOG
- **[RM28](ROADMAP.md#rm28--meta-conclusions-and-injected-cofactors)** — meta-conclusions + injected cofactors. **Parked and now smaller**: RM29 moved two of three cofactor classes into columns, and the cis/trans motivation closed as a compiler check. What survives is cross-*subject* pairing, economy, and open-world negation. · *also in* COMPILER, REFERENCE_EXAMPLES, CHANGELOG, PROPOSAL_0_5 § G3
- **[RM43](ROADMAP.md#rm43--resolution-reaches-the-snp-core-only-so-a-04-led-module-is-rsid-joinable-and-nothing-more)** resolution reaches `variants.csv` only, so an rsid-authored PGx module ships every coordinate null and joins to no VCF. The naive repair (fill from `resolution.csv`) **breaks P7**: reverse re-emits a filled coordinate as authored and `content_signature` moves, so it needs an `authored_ident` equivalent per positional table — an optional column, hence **0.6** since the charter amendment. 0.5.3 made the gap legible instead. · *also in* CLAUDE.md, COMPILER, ENRICHER, CONSUMER_SUGGESTIONS § S9, CHANGELOG

- **[RM44](ROADMAP.md#rm44--fully_resolved-answers-a-question-nobody-asked-it-and-prose-is-the-only-record-of-the-real-one)** — `fully_resolved` is `all()` over `variants.csv`, hence **vacuously true** for a table-only module, and a catalog following the documented trust rule served `trusted: true` for modules that join to no VCF. Fixed downstream by substring-matching the 0.5.3 warning's prose, which makes a sentence load-bearing (`compiler.UNJOINABLE_PHRASE` pins it meanwhile). The fix is one additive integer — `resolution_subjects` — beside the flag, the same parts-not-conveniences pattern as `vrs_alleles`. Do **not** make the flag `None`-able. · *also in* CLAUDE.md, COMPILER, CONSUMER_SUGGESTIONS § S13

- **[RM45](ROADMAP.md#rm45--the-manifest-is-rich-about-resolution-and-silent-about-verification-so-unchecked-and-clean-are-one-state-to-a-downloader)** — the manifest records what resolution *achieved* and nothing about which verification passes *ran*, so a module whose `clin_sig` was cross-checked and one where the check never ran ship identical manifests — there is no field that could differ. S4's own argument one layer down: 0.5.2 fixed it on `EnrichmentResult`, and the layer that outlives the run inherited none of it. Additive and **0.6** (the manifest was never in `artifact.digest`), but a design round rather than a patch: the check names and skip reasons both need **closed vocabularies** or the substring matching just moves down a level, the enricher→compiler seam has no per-*pass* channel at all, and the trust rule (`compiled_by`'s "foreign values are untrusted") has to be stated on the fields themselves. Recommended shape is a **`Verification` block** on `Frequency`'s precedent, since it wants the verified-against release id. Does **not** subsume RM44. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S8

- **[RM46](ROADMAP.md#rm46--a-literature-sources-terms-are-per-article-so-the-enricher-names-a-source-it-cannot-record)** — `enrich_literature` writes `source="pubmed"`, `TERMS_BY_SOURCE` has no `pubmed`, and `record_source_terms` rightly refuses to invent one, so every literature-enriched module warns about a source **the enricher introduced**. A `PUBMED_TERMS` constant is the wrong fix and the reporter said why: a literature source's terms are **per-article** (metadata vs the publisher's text), so one row would clear a module carrying a CC-BY-NC `provenance_quote` — publisher text in the module's own annotation layer, where tainting actually happens. The compiler cannot exempt it either (that needs a source convention — P2, the RM33 mistake). Per-article terms want settling with **RM27**'s use-vs-distribution axis. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S10

- **[RM47](ROADMAP.md#rm47--a-bin-boundary-is-the-most-interpretive-claim-in-the-format-and-the-only-one-with-nowhere-to-cite)** — `studies.csv` is required iff `variants.csv` is present, so grounding is enforced where citations usually arrive for free (a ClinVar draft) and absent where a human made the judgement: `htt_repeat_expansion` compiles green under `--strict` stating four Huntington thresholds with no citation anywhere, and `StudyRow` names a variant while a bin is keyed `(gene, repeat_unit)`. Narrowed on probing — `heteroplasmy.csv` **can** be grounded (0.5.1 identity columns; `mt_heteroplasmy` does it), and a variants-free `studies.csv` is accepted today, so the module can be grounded as a whole but never a bound. 0.5.4 ships the visible-decision half (`_check_binning_grounding`); the schema half is **0.6** and a design round, because all four candidate repairs cost a duplicated column set or a duplicated key, and whichever wins, the literature pass has to learn the new PMID site in the same release. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S19, CHANGELOG, SCHEMAS, COMPILER

- **[RM48](ROADMAP.md#rm48--an-hg19-coordinate-has-no-supported-path-into-a-grch38-module-and-liftover-is-the-wrong-primitive)** — an author curating from older literature has hg19 coordinates and the module must be GRCh38; nothing in the four packages converts, so the conversion happens off-tool and lands as an ordinary authored coordinate with no provenance. **Not RM15** (that changes the module's own build and every identity — this is one-way and authoring-time, so it is additive rather than 1.0). The reporter argues *against* liftover and the argument holds: with an rsID it is unnecessary and strictly worse, so it is only reachable where the lifted coordinate becomes the row's *sole* identity with nothing to verify it against — the hazard class behind the 3,038-variant off-by-one. The wanted primitive is **rsID recovery** from an hg19 coordinate; the design round is what surface answers it (an hg19-keyed dbSNP surface, or a chain file with its own licence and release). Three outcomes required — mapped/unmapped/ambiguous — because `pyliftover` fuses the last two exactly as S20 did. · *also in* CONSUMER_SUGGESTIONS_HISTORY § S22

- **[RM49](ROADMAP.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses)** — nothing in a spec listing says which files a human wrote and which the enricher produced, so a registry gave publishers a `derived/` tree and found it is one `compile` refuses; their layout stays transport-only (flatten on upload, re-split on download). The byte-attestation half of S26 shipped as `manifest.derived` in 0.6.0; this is the half that did not. Not the one-line fallback it looks like: `spec_dir / "resolution.csv"` is resolved in **eight places across two packages**, and tolerating the layout on *input* without deciding the *write* side breaks on first use — `enrich` on a downloaded split module writes to the root, producing the both-copies-present collision by following the documented workflow. Three candidate repairs named and refused: search any subdirectory (blinds `_check_misspelled_tables`, re-opening S16's hole), make `derived/` canonical (two supported layouts, and `reverse` emitting a tree older compilers in the same major cannot read), extend it to authored tables (two legal homes for `variants.csv`, so the ignored copy is invisible). · *also in* CONSUMER_SUGGESTIONS_HISTORY § S26

## — Not format scope

- **[RM7](ROADMAP.md#rm7--evaluation-output--report-card-schema)** — evaluation / report-card schema. Per-sample results are a *measurement*, so this is a **consumer** contract (`just-dna-lite`). Listed only so it is not mistaken for format scope. · *also in* USE_CASES, COMPILER, PROPOSAL_0_5

## 🔒 The major bucket — unnumbered on purpose, and that is why it hides

Everything needing a **major** lives in one table in
[ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker). These have **no `RMn`
number**, which is why they are easy to lose. They are not deferred features — each breaks a rule
Principle 3/8 protects, so a minor cannot carry it.

- `VariantRow.state` — deprecate at 1.0, remove at 2.0; a derived alias of `direction` since 0.3
- `state` values `alt` / `ref` — drop from the read-vocabulary; genotype-relative descriptors
- `VariantRow.pathogenic` / `benign` — deprecate → remove; lossy aliases of `clin_sig`
- `StudyRow.p_value: str` — retype (the numeric companion `p_value_num` shipped in 0.5)
- `weights.parquet` `end` — remove or wire; needs an *end*-coordinate convention (interbase-half-open vs inclusive), same as RM15. The authored `start` is settled: 1-based VCF POS, pinned by a test
- `weights.parquet` `likely_pathogenic` / `likely_benign` — remove; dead output, wiring rejected in 0.5
- `VariantRow.weight` vs `effect_size` — review whether `weight` is subsumed
- Deprecated flag / vocab aliases — collapse to the canonical vocab
- `ModuleManifest.authors` + free-form `curator` — fold into RM14's structured record
- `StudyRow.pmid` required — **doi-first**: require ≥1 of `{doi, pmid}`; a requiredness demotion
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
([CONSUMER_FIELD_NOTES](CONSUMER_FIELD_NOTES.md)) → run it against the bricks
([USE_CASES](USE_CASES.md)) → shape it ([PROPOSAL_0_5](PROPOSAL_0_5.md)) → then either **shipped**
(recorded in [COMPILER.md](COMPILER.md)'s coverage table) or **parked as an `RMn`**. An item with no
trail through those was usually found by dogfooding — RM31–RM35 all were.
