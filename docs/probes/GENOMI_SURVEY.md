# Genomi survey — what a genomics *runtime* annotates, and where our *format* is not yet a superset

**Probed** 2026-09-13 against [`exon-research/genomi`](https://github.com/exon-research/genomi) at
commit `1df4f5b` (2026-08-31), declaring version **0.1.0**, licensed **Apache-2.0**. 110,071 lines of
Python under `src/`, 138 test modules. Read from the code — `src/genomi/evidence/sources.py`,
`src/genomi/runtime/libraries/registry.py`, the eighteen `tool_catalog.json` files and the capability
packages behind them. `README.md` and `GENOMILAB_PRODUCT_DEFINITION.md` were skimmed for headings
only: they describe a product, and the source catalogue describes what is wired.

**This is evidence, never contract** — the standing rule for everything under `docs/probes/`. Nothing
here is a decision, and no `RMn` is filed by it. The candidate list in [§8](#8-the-plan--ranked-candidates-for-becoming-a-superset)
is a ranked set of *proposals*; each one becomes real only when it is filed in
[ROADMAP.md](../ROADMAP.md) and indexed in [RM_TOC.md](../RM_TOC.md).

**A survey rots.** Every claim below is pinned to that commit. Genomi is at 0.1.0 and moving; before
acting on any row, re-run the extractions in [§10](#10-how-to-re-derive-every-table-here).

---

## 1. The short answer

**Genomi is not a competitor to this format. It is the consumer we do not have.**

The two projects sit on opposite sides of the same seam:

| | just-dna-format | genomi |
|---|---|---|
| What it ships | an **authored, compiled, signed artifact** — annotation tables with no sample data | a **runtime** — an agent's local index of *one person's genome* plus fetchers |
| When the facts are gathered | at author time, into a module that is then frozen and digested | at query time, per question, from live APIs and installed libraries |
| Where the genotype lives | nowhere; the consumer supplies it (CONSTITUTION Goal, data-agnostic) | at the centre — the Active Genome Index is the whole architecture |
| What it does with a claim | records it with provenance, licence terms, and a `content_signature` | ranks it, scores it, and hands an LLM a confidence label |
| Reproducibility | byte-identical recompile; round-trip lossless (P7) | a fresh API call, whatever the source says today |

So "who annotates more" is the wrong first question. The right ones are:

1. **Which reference facts does genomi surface that no module here can carry?** — [§4](#4-the-comparison-table--annotation-surface), [§6](#6-the-annotation-shapes-they-have-that-our-row-models-do-not)
2. **Can each of those be expressed declaratively, and at what layer cost?** — [§7](#7-translating-genomi-into-modules), [§8](#8-the-plan--ranked-candidates-for-becoming-a-superset)
3. **Which of them must we deliberately *not* carry?** — [§9](#9-what-we-must-not-chase-and-the-principle-that-says-so)

The headline finding is smaller than the repository size suggests. **Genomi's curated, in-repo
annotation corpus is thirteen records**: ten hardcoded Python dictionaries in
`capabilities/nutrigenomics/catalog.py`, plus three CYP2C19 star-allele markers in
`capabilities/pharmacogenomics/data/star_marker_definitions.json`. Everything else it "annotates" is
fetched live or read from an installed third-party file. **Fifteen of its twenty-nine declared
evidence sources are wired; the other fourteen are marked `record_via_research`**, which means *the
agent looks it up by hand and writes a journal note*. Against that, the real gap list is short and
mostly gene-keyed.

---

## 2. Three buckets, and only one of them is comparable

Genomi exposes roughly a hundred operations across fifteen capability packages. Partitioned the way
[USE_CASES.md](../USE_CASES.md) partitions anything — enabled / consumer-side / gap:

### Bucket A — reference annotation (**the comparable surface**)

Facts about a variant, gene, drug or condition that are true regardless of whose genome is being
asked about. This is the only bucket [§4](#4-the-comparison-table--annotation-surface) compares.

`clinvar.match_variants`, `gnomad.fetch_population_frequency`, `gwas.compare_variant_associations`,
`gwas.compare_gene_associations`, `phenotype.retrieve_gene_disease_associations`,
`phenotype.compare_gene_hpo_evidence`, `phenotype.retrieve_trait_gene_records`,
`phenotype.retrieve_disease_drug_targets`, `phenotype.compare_drug_target_evidence`,
`pathway.retrieve_members`, `cell_type.retrieve_markers`, `region.retrieve_features`,
`functional_genomics.retrieve_perturbation_records`,
`functional_genomics.compare_gene_perturbation`, `pharmacogenomics.fetch_clinpgx`,
`pharmacogenomics.fetch_pgxdb`, `pharmacogenomics.fetch_fda_labels`,
`pharmacogenomics.review_medication`, `prs.search_scores`, `prs.fetch_score_metadata`,
`prs.import_scoring_file`, `nutrigenomics.retrieve_domain_markers`,
`nutrigenomics.retrieve_variant_records`, `ancestry.list_reference_panels`.

### Bucket B — sample compute (**consumer-side here, by charter**)

Arithmetic over a person's genotypes. The **tables these consume are annotation** and belong in a
module; the **arithmetic is the consumer's**, and in this ecosystem that consumer is
`just-dna-lite`. The Constitution's data-agnostic goal is explicit — a module carries no sample data,
no genotype under test, no measured value.

`prs.calculate_score`, `prs.check_score_overlap`, `ancestry.project_pca`,
`ancestry.estimate_population_context`, `ancestry.check_sample_overlap`,
`pharmacogenomics.run_pharmcat`, `pharmacogenomics.preflight_pharmcat`,
`pharmacogenomics.prepare_outside_call_tsv`, `active_genome_index.classify_genotype_support`,
`active_genome_index.classify_region_callability`, `active_genome_index.classify_callset_qc`,
`clinvar.scan_candidates`, `variant.find_gene_variants`, `variant.gather_allele_context`,
`variant.gather_gene_context`, `phenotype.plan_risk_investigation`.

Said once, and not revisited below: **nothing in Bucket B is a gap in this format.** Two of them do
carry a signal for us, though, and they are picked up in [§8](#8-the-plan--ranked-candidates-for-becoming-a-superset):
`classify_region_callability` is the question our `requires_callable` / `callable_from` /
`min_quality` columns already answer from the annotation side, and `prs.check_score_overlap` is what
`PgsRow.match_rate_floor` exists to let a consumer check.

### Bucket C — agent runtime (**out of scope entirely**)

`genomi.parse_source` and the whole Active Genome Index lifecycle, user profiles and scoped access,
`journal.*` (four operations), `research.*` (five), `genomilab.*` (nineteen — a specialist-board
investigation workflow with patient authorization), `decode.render_dashboard`, the seven
`sequence.*` utilities (translate / ORF / restriction sites / Kozak / primers — analysis of a
*supplied* sequence, not annotation of a locus), and `genomi.set_response_profile`.

Listed so nobody re-asks. This repository has no app and no orchestration, deliberately.

---

## 3. What genomi actually annotates from — and the fourteen sources it does not

`src/genomi/evidence/sources.py` declares **29** sources, each with an `adapter_status`. **That field
is the discriminator**, and reading the roster without it credits genomi with roughly twice the
integration it has. The split is **15 wired / 14 `record_via_research`**, counted by the extraction in
[§10](#10-how-to-re-derive-every-table-here) on 2026-09-13 — re-run it rather than trusting these
three numbers, which is what `@counted-prose-needs-a-fixed-field` is for.

### Wired (15)

| Source | `adapter_status` | Evidence types |
|---|---|---|
| ClinVar | `implemented_local_import` | clinical_assertion, review_status, condition_assertion |
| gnomAD | `implemented_api_fetch` | population_frequency, homozygote_context |
| GenCC | `implemented_public_tsv_download` | gene_disease_validity, inheritance |
| HPO | `implemented_local_normalization` | phenotype_term, phenotype_synonym, phenotype_overlap |
| CPIC | `implemented_api_fetch` | pharmacogenomic_guideline, dosing_context, phenotype_mapping |
| Open Targets | `implemented_api_fetch_for_target_disease_and_clinical_drug_targets` | target_disease_association, variant_to_gene, locus_to_gene, clinical_drug_target, tractability_context |
| Reactome | `implemented_api_fetch` | pathway_to_gene_relationship, pathway_participant |
| Human Protein Atlas | `implemented_api_fetch` | tissue_to_gene_expression, cell_type_to_gene_expression |
| ChEMBL | `implemented_api_fetch_for_drug_mechanism_targets` | drug_target, mechanism_of_action, bioactivity |
| PharmGKB | `implemented_api_fetch` | pharmacogenomic_annotation, guideline_link, variant_drug_association |
| PGxDB | `implemented_api_fetch` | pharmacogenomic_annotation, drug_response, variant_drug_association |
| FDA PGx biomarkers | `implemented_web_fetch` | drug_label_biomarker_context, actionability_context |
| FDA PGx associations | `implemented_web_fetch` | pharmacogenetic_association, safety_context |
| GWAS Catalog | `implemented_api_fetch` | association, risk_context, trait_context |
| BioGRID ORCS / DepMap | `implemented_native_retrieval_and_record_verification` | screen_hit, perturbation_context, assay_context |

### `record_via_research` — declared, not wired (14)

ClinGen gene validity, GeneReviews, MONDO, Orphanet, OMIM, GeneCards, MalaCards, NCI Cancer
Genetics, COSMIC Cancer Gene Census, QuickGO/GOA, KEGG, DrugBank, Pharmaprojects, PubMed/primary
literature.

For these, genomi's answer is *"an agent should go read it and store a finding"*. **They are not
annotation surface**, and nothing below counts them as such. This matters most for ClinGen and OMIM,
which a reader of the roster would otherwise assume genomi carries and we do not — the reverse is
true for ClinGen: we import it into `gene_validity.csv`.

### Installed libraries (data genomi ships a fetcher for, beyond the source roster)

`clinvar-grch37/38`, `hpo`, `gencc`, `pgs-catalog-score-metadata`, `gencode-grch37/38`,
`encode-ccre-grch38`, `panglaodb-markers`, `cellmarker-human`, `msigdb-hallmark`,
`ancestry-1000g-30x-grch37/38`, `liftover-chains`, `reference-grch37/38`, `pharmcat`,
`minimap2`/`bwa-mem2`, `prs-scoring-file`, plus live-API descriptors for the sources above.

### The curated corpus (13 records, in two files)

`capabilities/nutrigenomics/catalog.py` holds ten
single-marker records across six domains — folate metabolism (`rs1801133`), lactose tolerance
(`rs4988235`), iron storage (`rs1800562`, `rs1799945`), vitamin D status (`rs2282679`, `rs10741657`,
`rs12785878`), lipid diet response (`rs429358`, `rs7412`) and obesity predisposition (`rs1421085`).

Its module docstring reads *"Add rows by curation commit only."* That is the same job our
`variants.csv` does, done in Python, with no schema, no validator, no licence record, and no digest.
[§7](#7-translating-genomi-into-modules) translates one of those rows and shows exactly what breaks.

The second file is `capabilities/pharmacogenomics/data/star_marker_definitions.json`: **one
definition set, `cyp2c19-common-cpic-marker-subset-v1`, with three markers** — `*2` (rs4244285,
`no_function`), `*3` (rs4986893, `no_function`), `*17` (rs12248560, `increased_function`) — plus
`normal_function_allele: "*1"`. That is `haplotypes.csv` and `allele_function.csv`, in our strongest
area, at three rows of one gene; its own `definition_scope` says *"use PharmCAT or specialized PGx
callers for clinical-grade genotyping"*. The exemption for `*1` matches ours exactly.

Two neighbouring files were checked and do **not** count as curated annotation.
`gene_requirements.json` is PharmCAT plumbing — which genes the named-allele matcher covers, which
need an outside call — the sample-side question our `requires_callable` column answers from the
annotation side. `capabilities/clinvar/static_annotation/` is index-building code over the installed
ClinVar VCF, not curated rows.

---

## 4. The comparison table — annotation surface

Only Bucket A. **Parity** means the fact class is reachable in a module today; **gap** means nothing
here can carry it; **refused** means we looked and declined, with the reason on record.

| Fact class | Genomi's route | Ours | Verdict |
|---|---|---|---|
| Variant clinical significance | ClinVar local import | `clinical_assertions.csv` (RM25) + `clinvar` cache lane + authored `clin_sig` | **parity** (we also carry `clin_sig_concordance.csv`, which genomi has no analogue for) |
| Population allele frequency | gnomAD API | `frequencies.csv`, `gnomad.py` — AC/AN/homozygote/hemizygote/`faf95` | **parity**, ours is wider (`faf95`, hemizygote, PAR handling) |
| GWAS associations | GWAS Catalog API, ranked per candidate | `gwas_effects.csv` (RM90) — effect size, SE, CI, RAF, p-value, ancestry, study accession | **parity**; they *rank*, we *record* |
| Gene–disease validity | GenCC TSV | `gene_validity.csv` (RM24) — GenCC **and** ClinGen, with `moi`, classification, submitter, assertion id | **parity, ours wider** |
| Gene constraint | *nothing* | `gene_metrics.csv` — pLI, LOEUF, o/e, haploinsufficiency, triplosensitivity | **we only** |
| PGx guideline / dosing | CPIC + ClinPGx + PharmGKB APIs | `cpic` / `clinpgx` lanes → `pharm_variants.csv`, `diplotypes.csv`, `allele_function.csv`, `haplotypes.csv` | **parity, ours wider** (they fetch text; we carry the diplotype→phenotype table) |
| FDA PGx label tables | `fda_web` scrape | `drug_labels` lane (RM166) | **parity** |
| PGxDB | API fetch | *nothing* | **gap** (small) |
| PGx star-allele calling | PharmCAT JAR | definitions in `haplotypes.csv`/`allele_function.csv`; the *calling* is Bucket B | **parity on annotation** |
| Curated star-allele definitions | 3 CYP2C19 markers, hardcoded JSON | `haplotypes.csv` + `allele_function.csv`, fed by the `cpic` and `pharmvar` lanes | **we only, by two orders of magnitude** |
| PRS | PGS Catalog metadata + scoring-file import + local calculation | `pgs.csv` — score id, trait, `training_ancestry`, `training_cohort`, `match_rate_floor`, `research_tier` | **parity on annotation**; the weights and the arithmetic are Bucket B |
| Phenotype terms (HPO) | local normalization + gene↔HPO comparison | *nothing* | **refused** — ENRICHER.md § Gene–disease validity records both reasons: HPO's licence URL 404s and OBO records a bare label, so terms cannot be established; and `genes_to_phenotype.txt` is a different grain (gene × HP feature × frequency) |
| Disease ontology normalization (MONDO / Orphanet / OMIM) | `record_via_research` | `trait_efo_id` on eight row models; `disease_id`/`disease_label` on `GeneValidityRow` | **parity-ish** — neither side has a normalizer; we at least have the column |
| Target–disease association | Open Targets GraphQL | *nothing* | **gap** |
| Variant-to-gene / locus-to-gene (L2G) | Open Targets | *nothing* — our `gene` column is authored, never scored | **gap** |
| Drug target / mechanism of action | ChEMBL API; Open Targets clinical drug targets | *nothing* | **gap** |
| Pathway / gene-set membership | Reactome API, KEGG (`record_via_research`), MSigDB Hallmark GMT | *nothing* | **gap** |
| GO term annotation | QuickGO (`record_via_research`) | *nothing* | **neither** |
| Tissue / cell-type expression (baseline) | HPA API + PanglaoDB + CellMarker tables | *nothing* — `expression_effects.csv` is a **variant's predicted effect** on a gene, a different fact | **gap** |
| Regulatory features / cCRE overlap | ENCODE cCRE BED, installed | *nothing* | **gap** |
| Transcript / exon structure, TSS distance | GENCODE GTF, installed | `mane_select` on `GeneMetricsRow`; `distance_to_gene` on `ExpressionEffectRow` | **partial gap** |
| Perturbation / dependency screens | BioGRID ORCS + DepMap + GEO | *nothing* | **gap** |
| Cancer gene role (oncogene / TSG) | COSMIC (`record_via_research`) | CIViC lane — somatic evidence with a direction axis (RM152) | **we only** |
| Ancestry reference panel | 1000 Genomes 30x PCA panel, installed | *nothing* | **gap, but see [§9](#9-what-we-must-not-chase-and-the-principle-that-says-so)** |
| Nutrient / diet single markers | 10 hardcoded records | `variants.csv` — the same shape, schema'd | **parity on mechanism, gap on corpus** |
| Literature | `record_via_research` | `literature.csv` — PMID/DOI/PMCID existence, OA status, per-article licence, quote attestation; LitVar2 coverage tiers (RM167); PubMind (RM134) | **we only, by a wide margin** |

### The count

**Nine gap rows**, of which one (PGxDB) is small and one (ancestry panel) is charter-blocked. The
real list is seven: Open Targets target–disease, Open Targets L2G, drug target/mechanism, pathway
membership, baseline tissue/cell-type expression, regulatory-feature overlap, and perturbation
screens. **Five of the seven are gene-keyed** — the two that are not, L2G and cCRE overlap, are
locus-keyed and therefore join on `variant_key` like every fact sidecar we already have. That
split is the single most useful thing this survey found; see
[§8](#8-the-plan--ranked-candidates-for-becoming-a-superset).

---

## 5. What we carry that genomi has no analogue for

Stated so the plan does not read as chasing. None of the following appears anywhere in genomi's
source tree, capability list, or library registry:

- **mtDNA heteroplasmy** — `heteroplasmy.csv` with allele-fraction bins, tissue and assay context, and the MITOMAP lanes behind it (its `status` column being a two-token grammar, per `docs/probes/MITOMAP_STATUS.md`).
- **Repeat expansions** — `repeat_alleles.csv`, repeat-count bins keyed `(gene, repeat_unit)`, checked against STRchive.
- **Copy number** — `copynumbers.csv`, including the modifier-gene columns SMN1/SMA needs.
- **The whole measure-binning axis** — four kinds sharing one base, with `measure_tiling`, inclusive `measure_max`, and the dense-boundary rule.
- **ACMG secondary findings** — `acmg_sf` / `actionability`, and the `acmg` lane.
- **MANE** — `mane_select` per gene, from its own snapshot.
- **AlphaGenome expression effects** — a model's predicted per-gene effect of a variant, with `tracks_agreeing`/`tracks_total`, under two distinct licence classes.
- **Somatic evidence with a direction axis** — the CIViC lane, and the identity protocol behind resolving a variant a source names but does not identify.
- **Licence as data** — `sources.csv`, `declared_use`, the compile gate, per-article literature terms. Genomi records source URLs; it has no mechanism that can refuse to build an artifact because a licence forbids the use.
- **Integrity as identity** — Ed25519 signing, `manifest.json`, `content_signature`, `verification.json`, the closure phase.
- **The authored overlay** — `overrides.csv`: a human correcting a derived table without the correction being merged into it.
- **Round-trip** — `compile → reverse → compile` reproduces the module or `strict` refuses.
- **Concordance** — `clin_sig_concordance.csv` + `clin_sig_authority_calls.csv`: what each archive published, and where they disagree, without resolving the split.
- **The three-valued algebra as a house rule.** Genomi has a real tri-state instinct — `coverage_state`, `sources_consulted_and_empty` vs `sources_consulted_but_unavailable` vs `sources_not_integrated` is exactly `@unreachable-not-absent`, and it is good work. But it lives per capability as a returned dict; it is not a schema, and nothing tests that two capabilities spell it the same way.

---

## 6. The annotation *shapes* they have that our row models do not

Separate from sources: four **fields** in genomi's curated records that no column here holds. Three
are worth taking.

### 6.1 `out_of_scope_claims` — negative annotation (**take it**)

Every nutrigenomics record lists the popular claims about that variant that the evidence does *not*
support:

```
"out_of_scope_claims": [
  "MTHFR variants as a general 'detoxification gene' — not supported",
  "Avoiding folic acid solely on MTHFR genotype — CDC explicitly says people with MTHFR
   variants can process folic acid and should not avoid it on genotype grounds",
  "Methylfolate-only dosing prescriptions based on genotype alone — limited RCT evidence",
]
```

`VariantRow.negatives` is **not** this. Its description is explicit: *"adverse/antagonistic-pleiotropy
counterpart to `conclusion` (e.g. a protective allele's trade-off)"* — a second real effect, not a
refuted claim. What genomi has is a third thing beside `conclusion` and `negatives`: **the claim in
circulation that this row exists to contradict.**

It also does not collide with `@refutation-withholds` ("evidence against a claim withholds the axis,
it never writes the opposite value"). That rule governs a *derived* axis a source disagrees about.
This is an authored, free-text statement that a named claim is unsupported — it writes no value into
`direction`, `clin_sig` or anything else. Worth a `PROPOSAL_0_8` thread rather than a straight column
add, because the interesting design question is whether it is one free-text column or a keyed table
(a claim, its status, and a citation for the refutation), and whether `overrides.csv` should be able
to reach it.

### 6.2 `established_caveats` — scope conditions (**probably already ours**)

```
"Effect on cardiovascular outcomes is contested across populations",
"Folate fortification status of the population modifies effect size",
```

Line one is `direction=contested`, which we have. Line two is an effect modifier and has no column —
but `StudyRow.population` plus `conclusion` carries it in practice. **Check before filing:** the real
question is whether an author is *told* to put it somewhere, which is a
[TABLES.md](../TABLES.md) matter, not a schema one.

### 6.3 `evidence_tier: established | probable | emerging` (**already ours, differently spelled**)

Their one axis is our two. `VALID_SIGNIFICANCE` is `significant | suggestive | not_significant |
unknown` (how strong *this* result is) and `StudyRow.confidence` carries the number. `VALID_GENE_VALIDITY`
grades the gene–disease body of evidence. Genomi collapses both into one three-member vocabulary.
**Ours is the better decomposition** (P5 — do not overload an axis), and a mapping note in
[FAQ.md](../FAQ.md) would settle it. Not a gap.

### 6.4 `haplotype_partner` — a prose string where we have a table (**we win, and it is worth saying**)

The APOE records carry `"haplotype_partner": "rs7412 (required for e2/e3/e4 assignment)"` — free
text, on both rows, machine-unreadable, where the ε2/ε3/ε4 isoform is a two-variant haplotype and
therefore `haplotypes.csv` + `diplotypes.csv`. Worked against the shipped module in
[§7](#the-reverse-direction-is-the-stronger-claim).

---

## 7. Translating genomi into modules

The punchline of the whole survey: **genomi's curated catalogue is already a module, written in the
wrong language.** This section was *run*, not sketched — the spec below lives in a scratch directory
and every quoted line is `just-dna-compiler validate`'s real output.

`variants.csv`

| rsid | gene | genotype | state | direction | stat_significance | clin_sig | phenotype | trait_efo_id | conclusion |
|---|---|---|---|---|---|---|---|---|---|
| rs1801133 | MTHFR | AA | significant | risk | significant | risk_factor | elevated plasma homocysteine | EFO_0004458 | T/T homozygotes retain ~30% of C/C enzyme activity; associated with higher plasma homocysteine |
| rs1801133 | MTHFR | AG | significant | risk | suggestive | risk_factor | elevated plasma homocysteine | EFO_0004458 | Heterozygotes show intermediate thermolability |

Their `established_effect.claim` splits across `conclusion` and `phenotype`;
`downstream_traits_with_gwas` becomes `trait_efo_id`, one row per trait — theirs is a nested list,
ours is a row, and ours is the one a consumer can join on. `effect_allele: "A"` becomes the
`genotype` column, and **their record cannot distinguish AA from AG at all**: it carries one
`effect_allele` and one `claim`, so the dose–response its own prose describes ("T/T homozygotes have
~30% of C/C activity") is not in their data. `risk_factor` is a real `VALID_CLIN_SIG` member; nothing
above invents a column.

### What actually refused

Two of the record's three sources are web pages (CDC folic-acid guidance, MedlinePlus); the third is
a ClinVar VCV id. Authored as a `studies.csv` row with a URL and no PMID:

```
error: studies.csv line 2 [pmid]: Field required
INVALID: .../mthfr
```

Removing the file instead is worse, and the message is the interesting one:

```
error: studies.csv is missing. Grounding evidence is mandatory; add study rows with PMIDs.
```

Supply one real PMID (7647779, the original thermolabile-variant report) and the same spec validates,
with only the standard no-closure and no-`resolution.csv` warnings:

```
valid: .../mthfr
```

**So genomi's MTHFR record cannot be compiled here as written — and the refusal is correct.** This
is not a gap in our schema; it is a curation shortcut in theirs, caught. The claim *has* primary
literature behind it, and finding it took one search: PMID 7647779 is the original report of the
thermolabile variant, which is what the CDC page is summarizing. A national health authority's
guidance is a **pointer to grounding, not grounding** — the curator who cites the summary instead of
the study has skipped the step the citation exists to record, and there is nothing here for us to
implement. Whether the folate claim is well-evidenced is exactly the question `pmid` makes checkable,
and the enricher's literature pass then checks that the identifier resolves and that a quote is
really in the article.

The rest of the record places cleanly: the ClinVar assertion belongs in `clinical_assertions.csv`
(`variation_id` 3520, enricher-derived), and the CDC page belongs in `sources.csv` — where it is a
*dataset's* terms and attribution, which is a different question from why a bound is where it is.

`sources.csv`

| source | layer | license_url | attribution | commercial_use | declared_use |
|---|---|---|---|---|---|
| cdc_mthfr_guidance | annotation | https://www.cdc.gov/folic-acid/data-research/mthfr/index.html | CDC | true | unstated |
| clinvar | clinical_assertion | … | NCBI ClinVar | true | unstated |

**The cells that do not exist** are §6.1's `out_of_scope_claims` — three of them on the MTHFR record
alone, and they are the most valuable content in genomi's catalogue.

### The reverse direction is the stronger claim

`reference_examples/apoe_epsilon` **already ships the module genomi's catalogue cannot express**, and
against the same two variants at the same two coordinates their records carry:

```
haplotype_name,rsid,chrom,start,ref,allele,gene
e2,rs429358,19,44908684,T,T,APOE
e2,rs7412,19,44908822,C,T,APOE
e3,rs429358,19,44908684,T,T,APOE
e3,rs7412,19,44908822,C,C,APOE
e4,rs429358,19,44908684,T,C,APOE
e4,rs7412,19,44908822,C,C,APOE
```

plus a `diplotypes.csv` giving all six pairs → phenotype, including the one that matters most:

```
APOE,e2,e4,APOE ε2/ε4,MONDO:0004975,unknown,"One ε2 and one ε4 — opposing alleles. Risk is not
the sum of its parts and is poorly resolved; report with caution."
```

Genomi encodes the whole of that relationship as `"haplotype_partner": "rs7412 (required for
e2/e3/e4 assignment)"` — a free-text string, duplicated on both rows, machine-unreadable — and its
own `established_caveats` names the consequence it cannot act on: *"unphased genotypes can be
ambiguous"*, which is our `requires_callable` column. It has no representation at all for ε2/ε4
being `direction=unknown` rather than the average of protective and risk.

## 8. The plan — ranked candidates for becoming a superset

**Every one of these is a derived sidecar produced by an enricher pass, not an authored table kind.**
That follows from what they are: facts a public source publishes identically to everyone, which no
author decides. `gene_validity.csv` (RM24) is the template — a model in `just_dna_format`, a
`VALID_SOURCE_LAYERS` member, an enricher pass that writes a `SourceRow` and merges rather than
clobbers, and an `overrides.csv` entry if an author must be able to correct it. Under the 0.6 charter
amendment that is **half cost**; an authored CSV would be full cost and is not warranted for any of
them. All fetching lives in the enricher (P2). Adding an optional table is minor-legal (P3/P8).

### Release class — all of it is 0.8, and the reason is structural

**Everything below lands in 0.8, under [RM188](../ROADMAP_0_8.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics), the survey item this document is half of.** That is not a scheduling
preference; it follows from what each candidate is. A derived sidecar is four things at once — a row
model in `just_dna_format`, a new `VALID_SOURCE_LAYERS` member, a parquet the compiler emits, and an
enricher pass with its cache lane — so it touches the format and compiler tiers, not just the network
one. A **new optional table is additive and therefore minor-legal** under P3/P8, which makes it
**0.8.0** and never a patch. The same holds for §6.1's `out_of_scope_claims`: a new optional column on
an authored model is minor-legal, minor-required, and the most format-tier item on this page.

**What could still be a 0.7.x patch, and it is one item.** The three packages version independently,
and work confined to the network tier — no parquet, no model, no manifest field — ships as an
enricher patch; `just-dna-enricher` 0.5.1 and 0.5.2 are the precedent, and RM166's `check-labels` is
the shape: a pass that *reports findings* and writes no table. **Tier 3's PGxDB is the only candidate
that can take that shape**, and only in one branch of its probe — if PGxDB says something the
CPIC/PharmGKB/FDA lanes do not, and if what it says can be written as a check over tables that
already exist, it is enricher-only and legal on 0.7.x. If it needs a row model, it is 0.8 like the
rest. The probe decides, and the probe has not been run.

Two things that are not releases at all and need no number: the licence probes each candidate owes
(below), and anything filed into [USE_CASES.md](../USE_CASES.md). Those land whenever they are
written.

Do **not** reach for the patch lane by reducing a candidate to a check. A pass that reports "this
gene appears in four Reactome pathways" and stores nothing is enricher-only and therefore cheap, and
it is also useless — the content *is* the point for every Tier 1 and Tier 2 item here. The one place
that reasoning is honest is PGxDB, where the content may turn out to be a duplicate and the check the
only thing worth keeping.

**Every licence named below is recalled, not probed.** They are there to rank, never to rely on:
`@no-named-licence` and the PharmVar rule both say an unestablished permission is not a permission,
so each candidate owes a real terms probe — the file, its SPDX id, and whether the URL answers — as
the first step of its own RM, before a byte is fetched.

Ranked by *(value to a module author) ÷ (cost + licence risk)*:

### Tier 1 — take these

**1. `pathways.csv` — gene ↔ pathway/gene-set membership.**
Sources: Reactome ContentService (CC0-ish, verify), MSigDB Hallmark GMT (**CC BY 4.0 with a
registration wall — check `declared_use` carefully**), KEGG (**licence-hostile for redistribution;
probably exclude**). **Read [ENRICHER.md § Regulator drug labels](../ENRICHER.md#regulator-drug-labels-drug_labelspy--drug_labels_buildpy--clinpgx-check-labels--rm166) before starting**: ClinPGx publishes a `pathways-tsv` archive from
a source we have already adopted and gated, which looks like a cheap first increment and is not one —
those are drug-metabolism pathways, a narrower scope than Reactome's, and ClinPGx is CC BY-SA with a
no-sale term, so a module carrying them stops being sellable where a Reactome-sourced one would not.
Two different tables that would collide on one column name; decide the scope before the source. Grain: one row per `(gene, pathway_id, source)` with `pathway_name` and
`pathway_source`. Gene-keyed, so RM47's rule applies — the row cites, the citation table describes.
**Release: 0.8.0.** *Why first:* it is the cheapest real gap, it is the join every downstream consumer asks for, and
Reactome alone closes most of it. **Estimate: 2–3 days** including the cache lane, its three stages,
and the licence rows.

**2. `target_disease.csv` — Open Targets target–disease association scores.**
Grain: `(gene, disease_id)` → `overall_score` plus the per-datatype scores, `datasource_count`,
`disease_label`. Open Targets is CC0. This is the biggest single content win: it is the fact class a
module author most often wants and cannot express, and it plugs straight into the existing
`disease_id`/`disease_label` columns on `GeneValidityRow`.
**Release: 0.8.0.** *The design question to settle first:* an aggregated score is a **derived judgement of a judgement**,
and `@a-recorded-judgement-is-a-fact` says a recorded one may be gated on. Whether `strict` may ever
read this column needs deciding in the proposal, not in the code. **Estimate: 3–4 days.**

**3. `regulatory_features.csv` — cCRE / regulatory overlap per locus.**
Sources: ENCODE cCRE (unrestricted), GENCODE (unrestricted). Grain: one row per
`(variant_key, feature_id)` with `feature_class` (promoter-like / enhancer-like / CTCF-bound),
`overlap_bp`, `distance_to_tss`, `nearest_gene`. **Variant-keyed, so it joins on `variant_key` like
every other fact sidecar** — no new key shape. **Release: 0.8.0.** It also pairs naturally with
`expression_effects.csv`: AlphaGenome predicts *that* a variant changes expression, this says *what
element it sits in*. **Estimate: 3 days**, mostly the BED/GTF interval work.

### Tier 2 — take these next

**4. `drug_targets.csv` — gene ↔ drug mechanism of action.**
ChEMBL (CC BY-SA 3.0 — share-alike, so `share_alike=true` and it constrains a carrying module the
way ClinPGx already does) plus Open Targets' clinical drug-target records (CC0). Grain:
`(gene, drug_id)` → `mechanism_of_action`, `action_type`, `max_phase`, `drug_name`. **Release: 0.8.0.** Distinct from
`pharm_variants.csv`, which is *variant → drug response*; this is *gene → drug exists*.
**Estimate: 3 days.**

**5. `expression_baseline.csv` — gene × tissue / cell-type expression specificity.**
Human Protein Atlas (CC BY-SA 3.0). Grain: `(gene, tissue_or_cell_type)` → `specificity_class`,
`nTPM`. **Release: 0.8.0.** Name it away from `expression_effects.csv` deliberately — one is a baseline, the other is a
variant's predicted delta, and letting the two share a prefix invites exactly the confusion §4's row
warns about. **Estimate: 2–3 days.**

**6. `screen_hits.csv` — perturbation / dependency evidence.**
DepMap (CC BY 4.0) and BioGRID ORCS (**registration key required — the PharmVar precedent applies:
gated source, cache unpublishable, `offline` outranks an injected client**). Grain:
`(gene, cell_line, screen_id)` → `score`, `assay`, `perturbation`, `phenotype`.
**Release: 0.8.0.** *Lowest confidence of the six.* Its value to an annotation module is the least obvious — it is
research evidence about a gene, not a fact about a person's variant — and it should be argued in
USE_CASES before it is built. **Estimate: 4 days, and don't start it before a use case exists.**

### Tier 3 — cheap, low value

**7. PGxDB as a `clinpgx`-lane sibling.** One more PGx surface beside CPIC/PharmGKB/FDA. **Release: 0.7.x enricher patch if it reduces to a check, else 0.8.0** — the only split-lane item on
this page, argued above. Check first
whether it says anything the three already there do not; a source that photocopies another is the
`rm171_diff_strategy` lesson. **Estimate: 1 day, after a probe that may kill it.**

### Do not build without a proposal

**8. Ancestry reference panels.** PCA loadings are aggregate, not sample data, so a module *could*
legally carry them. But projecting a sample into that space is Bucket B, the 1000 Genomes panel is
~200 MB (Git LFS territory at best), and the population labels are exactly the kind of judgement the
Constitution's non-goals exist to keep out. **Park it as a proposal question. Do not decide it here,
and do not decide it in an implementation PR.**

### Not chased

Variant-to-gene / L2G scoring. It is a *model output that assigns a gene to a locus*, and our `gene`
column is authored by a human who knows which gene they mean. Adding a scored competitor to an
authored cell is the shape `@hint-redundancy-bearing` warns about. If it ever lands it should be a
hint, not a column.

### Shape work, independent of any source

**9. `out_of_scope_claims`** — [§6.1](#61-out_of_scope_claims--negative-annotation-take-it). **Release: 0.8.0** — a new optional column on an authored model, minor-legal and minor-required. The
cheapest item on this page and the only one that adds *authored* expressiveness rather than fetched
content. **Estimate: an afternoon for a free-text column; 2 days if it becomes a keyed table.** It
should go through a proposal because the keyed-table version is the better design and the column
version is the one that will get built by default.

---

## 9. What we must not chase, and the principle that says so

- **Anything that reads a person's genotype.** PRS calculation, ancestry projection, PharmCAT calling, callability classification, ClinVar candidate scoring, review-group assignment. Data-agnostic is a Constitution goal, and it is the reason this format is safe to publish. The tables those operations consume are ours; the arithmetic is `just-dna-lite`'s.
- **Gene–disease inference.** [Documentation & prose style](../../CLAUDE.md) states it directly: describe the format honestly, never a gene–disease inference. Genomi's `candidate_scoring.py` and `review_groups.py` build ranked candidate matrices with `evidence_support_level` and `answerability` lanes — that is inference at runtime, done by a tool that has the patient's genome in front of it and an LLM downstream. It is a reasonable thing for *that* product to do. A signed annotation artifact that shipped a precomputed ranking would be making the clinical judgement its consumer is supposed to make.
- **Confidence as a returned label.** Genomi's `evidence-quality.md` tells the agent to *derive* confidence per turn from what came back, and explicitly forbids promoting an internal quality field into a final confidence statement. Good rule, and it is the same instinct as our refusal to let a hint fill a cell a Class-2 check cross-examines. Ours is enforced by tests; theirs is enforced by a skill document an LLM reads. **Do not copy the mechanism.**
- **A second feedback file, a journal, or a research memory.** Bucket C. The inbox here is `CONSUMER_SUGGESTIONS.md` and the ledger that watches it.

---

## 10. How to re-derive every table here

```bash
git clone --depth 1 https://github.com/exon-research/genomi.git && cd genomi
git rev-parse HEAD          # pin what you surveyed

# §3 — the source roster with adapter_status (the discriminator)
python3 - <<'PY'
import re
s = open('src/genomi/evidence/sources.py').read()
pat = r'"source_id": "([^"]+)".*?"evidence_types": (\[[^]]*\]).*?"adapter_status": "([^"]+)"'
for m in re.finditer(pat, s, re.S):
    print('%-40s %-34s %s' % (m.group(1), m.group(3), ' '.join(m.group(2).split())))
PY

# §2 — every operation with its description and its network reach
python3 - <<'PY'
import json, glob
for f in sorted(glob.glob('src/genomi/**/tool_catalog.json', recursive=True)):
    for k, v in json.load(open(f)).get('operations', {}).items():
        print('%-46s %-4s %s' % (k, 'NET' if v.get('external_io') else '', v.get('description','')[:110]))
PY

# §3 — installed libraries
python3 -c "import re;s=open('src/genomi/runtime/libraries/registry.py').read();[print('%-34s %s'%(m.group(1),(re.search(r'title=\"([^\"]*)\"',m.group(2)) or [None,''])[1])) for m in re.finditer(r'id=\"([^\"]+)\",(.*?)(?=\n\s{4}LibrarySpec\(|\Z)',s,re.S)]"

# §3 — the whole curated corpus
grep -n 'record_id\|"domain"' src/genomi/capabilities/nutrigenomics/catalog.py
```

### §7 — reproduce the compile refusal

Written into a scratch directory, not into `reference_examples/`:

```bash
mkdir -p /tmp/mthfr && cd /tmp/mthfr
cat > module_spec.yaml <<'Y'
schema_version: '1.0'
module:
  title: MTHFR C677T — folate
  report_title: MTHFR C677T — folate
  description: Probe translation of genomi's mthfr_c677t_folate record.
  name: genomi_mthfr_translation
defaults:
  curator: genomi-survey-probe
  method: literature-review
genome_build: GRCh38
Y
cat > variants.csv <<'C'
rsid,gene,genotype,state,direction,stat_significance,clin_sig,phenotype,trait_efo_id,conclusion
rs1801133,MTHFR,AA,significant,risk,significant,risk_factor,elevated plasma homocysteine,EFO_0004458,T/T homozygotes retain ~30% of C/C enzyme activity
rs1801133,MTHFR,AG,significant,risk,suggestive,risk_factor,elevated plasma homocysteine,EFO_0004458,Heterozygotes show intermediate thermolability
C
printf 'rsid,doi,population,conclusion,trait_efo_id\nrs1801133,,mixed,CDC folic acid guidance page,EFO_0004458\n' > studies.csv

uv run just-dna-compiler validate /tmp/mthfr      # error: studies.csv line 2 [pmid]: Field required
rm studies.csv
uv run just-dna-compiler validate /tmp/mthfr      # error: studies.csv is missing. Grounding evidence is mandatory
printf 'rsid,pmid,population,conclusion,stat_significance,trait_efo_id\nrs1801133,7647779,mixed,Original thermolabile-variant report,significant,EFO_0004458\n' > studies.csv
uv run just-dna-compiler validate /tmp/mthfr      # valid
```

And the negative half, run in *this* tree — the gap list in §4 is only as wide as this grep, per
`@probe-names-the-table`:

```bash
for t in opentargets reactome KEGG msigdb quickgo cCRE DepMap ORCS PanglaoDB \
         CellMarker 'Protein Atlas' PGxDB '1000 Genomes' chembl; do
  echo "$(grep -rli "$t" docs/ enricher/src compiler/src schema/src 2>/dev/null | wc -l)  $t"
done
```

Every one of those returned **0** on 2026-09-13. `GENCODE` returns hits, but they are AlphaGenome's
declared build and protobuf-generated file headers, not an integration; `ENCODE` returns hits that
are the English word *encode*. Both were checked by eye.

## 11. Open questions

**One question this survey opened and closed.** The §7 refusal briefly read as a two-sided finding —
that a CDC guidance page is legitimate grounding `StudyRow` has no slot for, and that a fourth
grounding kind might be owed beside `pmid`, `doi` and the derived `clinical_assertions.csv`. It is
not. The MTHFR claim has primary literature behind it, one search away, and citing the authority's
summary instead is a curation shortcut rather than an expressiveness gap. Recorded as closed rather
than dropped, because the same reading will occur to the next reader of that refusal — and because
the incident that would justify the widening does not exist, which is the standing reason to close
rather than to park.


1. **Is a gene-keyed fact sidecar a shape we already have, or a new one?** `gene_metrics.csv` and `gene_validity.csv` are both gene-keyed, so the answer is probably yes — but five of the six Tier 1/2 candidates are gene-keyed with a *second* key part (pathway, disease, drug, tissue, cell line), and only `gene_validity.csv`'s `(gene, disease_id)` is an existing compound of that shape. Derive from it before assuming it generalizes.
2. **Is there a condition-keyed table here at all?** `disease_id` appears as a *column*, never as a table's subject. If Open Targets lands, "everything known about MONDO:0007739" becomes a natural query with no home.
3. **Does `overrides.csv` reach a new sidecar automatically, or is each one an `OVERRIDABLE_TABLES` entry?** It is an entry. Each candidate above therefore owes that decision explicitly — and the two existing exclusions (`sources.csv`, `clin_sig_authority_calls.csv`) are the precedent for saying no.
4. **What does genomi's `out_of_scope_claims` cost an author?** It is the one item here that touches the authored layer, which the 0.6 amendment prices at full cost. The gate is *"will this burden the author?"* — and a column that is empty on 95% of rows but load-bearing on the 5% that attract folk claims may be exactly the right trade, or may be a `TABLES.md` instruction instead. Probe it against `reference_examples/` before deciding.
5. **Should any of this be a module rather than a sidecar?** A "pathway annotation module" published in the marketplace is a different answer from a pathway sidecar in every module. This survey assumed sidecar throughout; the alternative was not tested.
