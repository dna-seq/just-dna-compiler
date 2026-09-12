# ClawBio — what it annotates, how, and what it would take for a module to say all of it

**Status** — survey complete, 2026-09-13. This is the **ClawBio half of
[RM188](../ROADMAP_0_8.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)**;
the genomi half was filed the same day by a parallel session as
[`GENOMI_SURVEY.md`](GENOMI_SURVEY.md) — read the two together, and § *Read beside this* below says
where they meet. Written the way RM188's method section asks: their pipelines run end to end on their
own demo input, the reports read, and the logic read *back out* of the reports rather than off the
README. Every claim below names the file it came from.

**Probed artifact.** `github.com/ClawBio/ClawBio` at `1fcecb7e9531210baabe6d5cdbdd08de1ff3ab8d`
(committed 2026-09-12), installed from source into a clean 3.11 venv (`uv pip install -e .`), CLI
`clawbio.py run <alias> --demo`. **Nine demos attempted, eight produced a report**: `nutrigx`,
`pharmgx`, `clinpgx`, `acmg`, `cnv-acmg`, `gwas`, `compare`, `prs`; `methylation` failed on a missing
dependency. Three more were attempted under their catalogue names before the alias table was read
(below). Their nutrition panel was then **translated into a module and compiled** — § *The
translation, run*.

**What this is not.** Not a feature comparison, and RM188 says why: a competitor's inference is
evidence about what a report *needs*, never a licence to copy the rule. Where their logic is an
inference, the outcome here is *the table that would let a consumer make it* — the Constitution's
non-goals are unmoved.

---

## The short answer

ClawBio is not a competitor to this format. It is a **library of 97 agent skills** — procedural
Python that fetches, computes and renders at query time — and it carries the sample (the Corpasome)
rather than annotation about samples. There is no schema, no artifact contract, no signature, no
round trip and no licence gate. The overlap is therefore not "their format vs ours"; it is **the
annotation tables their scripts have inlined as Python dicts and JSON files**, because those are a
module in a shape nothing can validate.

Read that way, the survey has one dominant finding and three real gaps.

**The dominant finding.** Four of their genotype-interpreting skills carry a hand-curated variant
table *inside the code*: `skills/nutrigx/data/snp_panel.json` (28 SNPs), `skills/pharmgx-reporter/
pharmgx_reporter.py` (`PGX_SNPS`, `GENE_DEFS`, `GUIDELINES` — 32 variants, 13 genes, 59 drugs),
`skills/ancestry-risk-profiler/data/ancestry_risk_associations.json` (39 ancestry-stratified
associations), `skills/genome-compare/data/aims_panel.json` (65 AIMs). Every one is an unsigned,
unversioned-against-its-source, uncited-per-row `variants.csv`/`haplotypes.csv`. They already know
this hurts: `ancestry_risk_associations.json` carries a hand-written `removed_v1.1` /
`removed_v1.3.0` changelog *inside the data file*, recording **12 associations withdrawn** — 1 in
v1.1, 11 in v1.3.0. Ten of the twelve went because the cited PMID resolves to a **different paper**,
and two PMIDs account for nine of those: `27005778` (Kettunen 2016, a metabolomics GWAS) was cited
for AFR T2D, hypertension, breast cancer, atrial fibrillation and Parkinson's, and `22158537`
(Cho 2011, an EAS T2D study) for four SAS rows spanning CAD, hypertension and Alzheimer's. The other
two went for having no paper at all (`rs1333049` CAD AFR, `rs699` HTN AFR).

**And this is the sharp version, because existence checking would have passed every one of them.**
Both wrong PMIDs are real articles; `LiteratureRow.exists` comes back `true` on all ten.
`@existence-not-identity` names exactly this — *a lookup must say what it found* — and the mechanism
that catches it is `StudyRow.provenance_quote` checked against `LiteratureRow.quotes_found` /
`quote_source` (`@quote-attestation`). A curator quoting the sentence they are citing cannot silently
attach it to a metabolomics paper. Their file discovered by hand, over two revisions, what that
column exists to make mechanical.

**Nothing in this class is a gap for us**, and § *The translation, run* compiles one of the four to
show that rather than assert it.

**The three gaps, largest first.**

1. **A multi-gene call has no row.** Their pharmgx report's single AVOID is warfarin, keyed
   `["CYP2C9", "VKORC1"]` — and our own `reference_examples/cyp2c9_warfarin_grch37/` carries the
   CYP2C9 diplotypes and the VKORC1 per-variant rows *side by side with nothing joining them*.
   `pgx_draft._cpic_recommendation_rows` says so in a comment. This is not new: it is
   [RM28](../ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half)'s surviving "pairing across
   *subjects*" clause, parked on a corpus that had exactly one entry (RM174/CIViC). **This survey is
   the second corpus entry**, and it is the first one that is a routine clinical guideline rather
   than an oncology molecular profile.
2. **`consequence` / `impact` have no column**, and their ACMG engine reads both as primary inputs.
   These are already named in [ROADMAP § Reserved namespace](../ROADMAP.md#reserved-namespace) as
   *planned future annotation axes* with no release committed. This is their motivating case.
3. **A region-keyed dosage row has no home.** Their CNV classifier's dosage map keys on genes *and
   regions* (`22q11.2`, `chr22:18,900,000-21,500,000`, hi=3 ts=3). Our `GeneMetricsRow` carries
   `haploinsufficiency`/`triplosensitivity` keyed on a **gene symbol**, so ClinGen's recurrent-CNV
   and ISCA region curations — the half of the dosage map a CNV classifier actually needs — cannot be
   written down.

Two smaller ones: a per-tissue eQTL has no row (`expression_effects.csv` aggregates 371 tracks by
design), and a fine-mapping posterior/credible-set membership has no column.

---

## What ClawBio is, and the asymmetry that makes a feature table misleading

| | ClawBio | just-dna-format |
|---|---|---|
| Unit | an agent skill: a `SKILL.md` + a Python script | a module: `module_spec.yaml` + one CSV per concern |
| Artifact | a `report.md` + `result.json` per run | a signed multi-parquet artifact + `manifest.json` |
| When the work happens | query time, in the skill | authoring time; the consumer only joins |
| Network | every skill may fetch | `format`/`compiler` never fetch (P2); `enricher` only |
| Sample data | ships one (the Corpasome, CC0) | never — the measurement arrives from the consumer |
| Identity | file SHA-256 of the input | `variant_key` + `content_signature` + `artifact.digest` |
| Reproducibility | `reproducibility/` bundle: replay command, env, checksums | round trip: `compile → reverse → compile` is lossless or `strict` refuses (P7) |
| Licence handling | per-skill code `license:` (93 MIT, 1 GPL-3.0, 1 Apache-2.0, 1 PROPRIETARY, 1 blank), plus `model_license`/`data_license` filled on **1 of the 97** | `sources.csv` per source × layer, and the compile gate reads that file and nothing else |
| Provenance of an annotation row | none — the row is a dict literal | `source`, `dataset`, `fetched_at`, `status`, plus `studies.csv` grounding |
| Backward compatibility | none stated | additive-within-a-major, enforced (P3/P8) |

That last-but-two row is worth dwelling on, and its numbers are counted off `skills/catalog.json`
rather than sampled. Every skill carries a `license` describing **its own code** — 93 of 97 MIT — and
the two keys that would describe the *data* it reads, `model_license` and `data_license`, are present
on all 97 and non-empty on **one**. Meanwhile the skills read CPIC, ClinPGx/PharmGKB and PharmVar,
which are CC BY-SA with an explicit no-sale clause (`@pgx-research-only`). So "this skill is MIT" is
true and answers the wrong question: nothing ClawBio publishes tells a consumer whether the
*annotation* it returns may be sold. That is the axis our compile gate exists for, and it is the
clearest thing we have that they structurally do not.

**Maturity, so nothing below is scored as shipped when it is not.** From `skills/catalog.json`:
**68 of 97 are `status: planned`**, 29 are `mvp`; the maturity tiers are 40 `cli-registered`, 38
`tested`, 12 `ci-validated`, 4 `spec-only`, 3 `scripted`; and `benchmark_validated` is **`false` on
all 97**. Fifty of the 97 are reachable from the CLI at all — `clawbio.py run cnv-acmg-classifier`
fails with *Unknown skill*, the alias is `cnv-acmg`. One skill in the annotation subset,
`hla-typing`, is a generated scaffold: `run_analysis()` is `# TODO: implement core hla-typing logic`
returning `{"status": "skeleton", "findings": []}`, and it is the only one of its kind in the tree.

---

## The annotation subset — 27 of 97, in the 19 rows below (some grouped)

**A skill is in scope here when it produces a claim about a variant, gene, haplotype or locus** —
the thing a module carries. That excludes the nf-core wrappers, proteomics, single-cell,
metagenomics, imaging, the LIMS/ELN bridges and the meta-tooling, which are pipeline orchestration
and assay analysis: not annotation, and not something a declarative table could ever hold.

Two exclusions worth naming rather than dropping silently:

- **`GENOMEBOOK/` and its two skills (`genome-match`, `recombinator`) are out of scope by their own
  README**: "an engineering sandbox … synthetic fixtures with no biological, medical or scientific
  meaning". Their `disease_registry.json` is invented. Counting them would be counting fiction.
- **`just-prs-mcp` is ours.** `skills/just-prs-mcp/SKILL.md` gives `homepage:
  https://github.com/dna-seq/just-prs-mcp`, author Anton Kulaga. It is the `just-prs` engine wrapped
  as a ClawBio skill, not a ClawBio capability.

### What each one reads

Derived by grepping each skill directory for source names, not from the README:

| Skill | Status | Sources it names | Annotation it produces |
|---|---|---|---|
| `clinpgx` | mvp | ClinPGx, CPIC, PharmGKB | drug × genotype clinical annotations, evidence level |
| `pharmgx-reporter` | mvp | ClinPGx, CPIC, PharmGKB, dbSNP, Ensembl | diplotype → metabolizer phenotype → per-drug action |
| `drug-photo` | planned | CPIC | same, entered from a photograph of packaging |
| `nutrigx` | mvp | ClinVar, CPIC, gnomAD, GWAS Catalog | nutrient-domain risk score from a 28-SNP panel |
| `claw-methylation-cycle` | planned | *(none — 11 rsIDs inlined)* | folate/BH4 enzyme activity, compound heterozygosity |
| `variant-annotation` | planned | ClinVar, gnomAD, Ensembl/VEP, ClinPGx, 1000G | annotation tiers (explicitly *not* ACMG) |
| `vcf-annotator` | planned | ClinVar, gnomAD, dbSNP, Ensembl/VEP | per-variant annotation of a VCF |
| `clinical-variant-prioritizer` | planned | ClinVar, gnomAD, OMIM, VEP | pathogenicity triage, carrier screening |
| `clinical-variant-reporter` | planned | ClinVar, gnomAD, ClinGen, CADD, SpliceAI, OMIM, HPO, VEP | ACMG/AMP 28-criteria classification + ACMG SF v3.2 |
| `cnv-acmg-classifier` | planned | ClinGen, VEP | ClinGen/ACMG 2019 CNV five-tier classification |
| `rare-high-impact-variants` | planned | ClinVar, gnomAD, VEP, 1000G | rare LoF burden count |
| `gwas-lookup` | mvp | GWAS Catalog, Open Targets, GTEx, eQTL Catalogue, PheWeb ×2, FinnGen, Ensembl, LocusZoom | per-variant association, PheWAS, eQTL, credible sets |
| `gwas-prs`, `wgs-prs`, `profile-report` | mvp / planned | PGS Catalog, ClinVar, gnomAD | polygenic score from a published model |
| `ancestry-risk-profiler` | planned | GWAS Catalog, PGS Catalog, gnomAD, 1000G | ancestry-stratified OR vs a EUR reference |
| `archaic-introgression` | planned | ClinVar, gnomAD | Neanderthal/Denisovan **segments** (IBDmix/Sprime/hmmix) |
| `hla-typing` | planned | *(none — skeleton)* | nothing yet |
| `genome-compare` | mvp | *(65 AIMs inlined)* | IBS, continental ancestry |
| `wes-clinical-report-en` / `-es` | planned | ANNOVAR, ClinVar, gnomAD, CADD, REVEL, OMIM, CPIC, PharmGKB, 1000G, GWAS Catalog | a full clinical exome report |
| `gi-annotation` / `-splice` / `-promoter` / `-enhancer` / `-chromatin` / `-expression` | planned ×6 | Ensembl/VEP, SpliceAI, GTEx | DNA language-model predictions over a sequence |

---

## Reading the logic back out of the reports

### `nutrigx` — a `variants.csv` in JSON, and a genetic model as a defaulted lookup

`skills/nutrigx/data/snp_panel.json` is 28 objects keyed
`{rsid, gene, ref_allele, risk_allele, nutrient_domain, weight, effect_direction, pmid}`. Column for
column that is `VariantRow`: `rsid`, `gene`, `ref`, `effect_allele`, `category`, `weight`,
`direction`, and `pmid` via a `studies.csv` row. `score_variants.py` then sums
`raw × weight` per domain and divides by the weight of the SNPs it *found*, so a missing SNP silently
rescales the score rather than widening a confidence interval; the report's "3/3 SNPs tested"
coverage line is what the reader gets instead.

The interesting cell is `inheritance`. `snp_raw_score(risk_count, inheritance)` maps a risk-allele
count to 0 / 0.5 / 1.0 under `additive`, and to 0 / 0 / 1.0 under `dominant_protective`. The panel
carries `inheritance` on **1 of its 28 rows** (`rs4988235`, MCM6 lactase persistence); the other 27
get it from `panel_entry.get("inheritance", "additive")`.

That is `@lookup-with-a-default-hides-a-new-member` in the wild: the map is the first edit, and a
third genetic model added to the panel reads as additive until somebody notices. **Our format has no
such default to be wrong about**, because the genetic model is not a column — `variants.csv` is keyed
`(variant_key, genotype)`, so a dominant-protective rule is three rows with weights `0, 0, 1` and an
additive one is three rows with `0, 0.5, 1`. Strictly more expressive (any genotype→weight function,
not two named ones) and with nothing to default. The cost is three rows where they write one field,
which is the authored-cost trade P9 prices — and it is the right side of it here, because the row set
is enumerable and small.

**Verdict: dissolved.** A nutrigenomics module is authorable today. It would additionally carry the
one thing their file cannot: a `sources.csv` row saying whose data this is.

### `pharmgx-reporter` — three of our PGx tables, in a 2,327-line Python file

The report from `clawbio.py run pharmgx --demo` profiles 13 genes and 59 drugs off 23 SNPs. The three
dicts behind it map one-to-one onto tables we already ship:

| ClawBio structure | Our table |
|---|---|
| `PGX_SNPS` / `GENE_DEFS[g]["variants"]` — rsID → `{gene, allele, effect}` | `haplotypes.csv` (`HaplotypeRow`) + `allele_function.csv` (`AlleleFunctionRow.function_status`) |
| `GENE_DEFS[g]["phenotypes"]` — phenotype → list of diplotype strings | `diplotypes.csv` (`DiplotypeRow`), inverted |
| `GUIDELINES[drug]["recs"]` — phenotype → `standard\|caution\|avoid` | `diplotypes.csv` drug rows (`drug`, `response`, `recommendation_strength`) |

The third row is where the shapes genuinely differ and it is worth being precise, because it is *not*
a gap. CPIC keys a recommendation on `(gene phenotype, drug, population)`; `DiplotypeRow` requires
`haplotype_a` and `haplotype_b`. So a phenotype-keyed recommendation has to be **denormalised across
every diplotype yielding that phenotype**, and that is exactly what `pgx_draft._recommendation_rows`
does — `by_key = {(r.phenotype, r.population): r ...}`, joined onto each pair. The drafter absorbs the fan-out; an author never writes it by hand. The consequence
is real but narrow: a diplotype the module does not enumerate carries no recommendation, which is the
same answer as "this module does not cover that diplotype" and is honest.

**Where it does break is warfarin**, and their report leads with it: the one AVOID in 59 drugs, keyed
`"genes": ["CYP2C9", "VKORC1"]` with `"special": "warfarin"` — a hardcoded branch calling
`get_warfarin_rec(profiles)`. **They have no declarative form for it either.** They have an escape
hatch, in code, for one drug.

Our side is documented in `pgx_draft.py`'s own comment: *"the guideline exists, it is a dosing
algorithm over several genes rather than a per-phenotype recommendation, so nothing lands here and
the author was told CPIC has nothing."* The fix that shipped was a better warning, not a table. See
§ The plan, item 1.

**Two things their report does that ours has the machinery for and no module exercises.** It prints a
*Panel Limitations* section (CNVs, structural alleles, the UGT1A1 TA-repeat, HLA, MT-RNR1, G6PD) and
a *Genes Not Assessed* table with the CPIC guideline each missing gene belongs to. That is
negative-space declaration — "this panel is silent here, and here is what silence costs you". We have
the per-row primitive (`requires_callable`, `@unreachable-not-absent`, the nobody-asked third state)
and no module-level statement of scope; `panel` in `module_spec.yaml` is deprecated (RM4). Worth
noting, not worth a table: see § What we deliberately do not take.

### `acmg` (`clinical-variant-reporter`) — the two columns their engine reads that we cannot store

`acmg_engine.py` is 653 lines implementing 12 of the 28 criteria: `PVS1 PS1 PM1 PM2 PM4 PP3 PP5 BA1
BS1 BP4 BP6 BP7`. The demo classifies 20 GIAB panel variants and prints a per-criterion evidence
table. Its inputs, read off the report:

| Evidence line in their report | Where it lives here |
|---|---|
| `gnomAD AF=0.000020` | `frequencies.csv` — `FrequencyRow`, per population, with `faf95` |
| `ClinVar=Pathogenic, stars=3` | `clinical_assertions.csv` — `ClinicalAssertionRow.review_stars` |
| `[SF]` — ACMG secondary-findings gene | `VariantRow.acmg_sf`, **validated against the published 81-gene list** since 0.5.1 (`enricher/acmg.py`) |
| `CADD=35.0≥25.3`, `SpliceAI=N/A` | **[RM23](../ROADMAP_0_8.md#rm23--computational-predictor-scores-as-a-table)** — `predictions.csv`, deferred on grain + acquisition, *not* on licensing |
| `consequence=frameshift_variant`, `impact=HIGH` | **nowhere** |
| `Transcript: ENST00000357654.9` | **nowhere on a variant row** (`GeneMetricsRow.transcript` is gene-level) |

The last two are the finding. `consequence` and `impact` are already written down in
[ROADMAP § Reserved namespace](../ROADMAP.md#reserved-namespace) as *planned future annotation
axes* — "documented intentions, not yet in the enforced set … they get a slot and a specific
diagnosis only when a release actually commits to building them". A running ACMG engine that reads
`consequence` as its PVS1/PM4/BP7 input is the commitment case those two were waiting for.

**The classification itself we do not take, and that is settled, not new.** [ROADMAP § Annotating
core, not format scope](../ROADMAP.md#annotating-core-not-format-scope-the-05-source-assessment)
refuses it by name: *"ACMG rule application and incidental-findings reporting policy … deciding what
to report to whom is the consumer's."* Their own `SKILL.md` frames the skill as filling the gap that
`variant-annotation` "explicitly disclaims ACMG adjudication" — the two projects drew the same line
and stepped over it in opposite directions, deliberately on both sides.

### `cnv-acmg-classifier` — dosage keyed on a region, not a gene

`data/curated_dosage_map.csv` is `chrom,start,end,name,hi_score,ts_score,benign,element_type,…` with
`element_type ∈ {gene, region}`. Four rows in the demo, two of them `region` (`22q11.2`, and a benign
demo region). The classifier scores Sections 1–3 of the ClinGen/ACMG 2019 point framework off it and
leaves Sections 4–5 to the analyst — its report says so: *"Sections 4 (case/literature) and 5
(inheritance) reflect analyst-supplied evidence and are never auto-generated."*

We carry the gene half: `GeneMetricsRow.haploinsufficiency` / `.triplosensitivity`, filled from
ClinGen by the enricher. We carry no region half, and `enricher/clingen.py` has no region path.
ClinGen publishes four dosage lists — gene curation, **region curation**, recurrent CNVs and ISCA
regions — and `enricher/acmg.py`'s own probe note from 2026-08-03 records seeing all four on the FTP
tree while reaching only for what it needed.

This is a real, small, additive gap. It is also the one place where a region genuinely is the
subject: a 22q11.2 deletion is not a claim about any one gene in the interval, so filing it under a
gene symbol would be a false attribution (`@gene-map-is-another-sources-attribution`).

### `gwas-lookup` — nine databases, and the two axes that come back with no home

`clawbio.py run gwas --demo` on rs3798220 (LPA) returns, in one report: VEP consequences per
transcript; 11 GWAS Catalog / Open Targets associations with OR and risk allele; **PheWAS from three
biobanks** (UKB-TOPMed, FinnGen, Biobank Japan) with per-cohort beta, p and MAF; 5 eQTLs by
**tissue** from GTEx and the eQTL Catalogue; and **3 fine-mapping credible sets** with posterior
probability and 95%/99% membership.

Sorting those:

- **GWAS associations** — `gwas_effects.csv` (`GwasEffectRow`) already carries `effect_size`,
  `effect_measure`, `risk_allele_frequency`, `p_value_num`, `trait_efo_id`, `study_accession`,
  `ancestry`. **Dissolved.**
- **PheWAS across biobanks** — the same row shape with `dataset`/`source` naming the cohort. A
  FinnGen row and a GWAS Catalog row are both "variant × trait × cohort → effect". **Dissolved**, and
  worth saying out loud because it looks like a new axis and is not.
- **eQTL by tissue** — **gap.** `expression_effects.csv` exists but is AlphaGenome-shaped: one row
  per `(variant, gene)` aggregating 371 tissue tracks into `tracks_agreeing`/`tracks_total`, and
  `expression.py` argues explicitly that one row per track "is lossless and unreadable". A GTEx row
  is not a track — it is a measured cis-eQTL in one named tissue with its own beta and p, ~50 tissues
  not 371, and the tissue *is* the fact. Different grain, different source, different table.
- **Fine-mapping posterior / credible-set membership** — **gap.** A per-`(variant, trait, study)`
  posterior inclusion probability is the same class of object as an allele frequency or a LOEUF: a
  number from a named dataset, no measurement, no inference by us. Nothing in the format holds it.

### The two that did not run, and what that tells us

- `clawbio.py run methylation --demo` → `ModuleNotFoundError: No module named 'pyaging'`. The
  methylation *clock* needs an unlisted heavy dep. (`claw-methylation-cycle`, a different skill, is
  not CLI-registered at all.)
- `cnv-acmg-classifier`, `clinical-variant-reporter`, `claw-methylation-cycle` all fail as typed —
  the runner's aliases are `cnv-acmg`, `acmg`, `methylation`, and 47 of the 97 skills have no alias.
  A capability the tool lacks is a result (`@dogfood-lacks-are-results`): the catalogue count is 97,
  the runnable count is 50.

---

## The translation, run

The claim above — *their inlined panels are a module in the wrong language* — is worth nothing
asserted, so it was run. `skills/nutrigx/data/snp_panel.json` (28 rows) was translated
field-for-field into a spec in a scratch directory and put through the real compiler. **It compiles,
after two refusals, and both refusals are findings.**

The translation: each panel row becomes **three `variants.csv` rows**, one per genotype, because the
genetic model is rows here rather than a field — `{ref/ref, ref/risk, risk/risk}` with weights
`0, 0.5w, w` under `additive` and `0, 0, w` under `dominant_protective`, sign-flipped because
`VariantRow.weight` is *positive = protective*. `nutrient_domain` → `category`, `effect_direction` →
`phenotype`, `risk_allele` → `effect_allele`, `pmid` → a `studies.csv` row.

**Refusal 1 — `state` is required, and `direction` is not.** 84 rows × `variants.csv line N [state]:
Field required`. A translation written against the *modern* column is refused for omitting the
*superseded* one. This is already in the [1.0-cleanup tracker](../ROADMAP.md#variantrowstate) with
the reason — P8 forbids demoting a required field inside a major, so the deprecation and the demotion
have to land together at 1.0 — and the entry is right. What the run adds is that the friction is not
hypothetical: it is the **first** error a first-time author sees, before anything about their data.
Fixed by writing `state` = `direction`, which is exactly the duplication the tracker predicts.

**Refusal 2 — `ref/alts require chrom and start to also be provided`.** Their file states a
`ref_allele` for all 28 SNPs and **no coordinate for any of them**. Our schema refuses a bare `ref`,
and it is right to: a reference allele with no locus is unanchored — nothing can check it against a
reference genome, and `@va-omits-ref` plus the three-causes rule for a ref mismatch both depend on
having a position to read a window at. So their 28 `ref_allele` cells are 28 unverifiable assertions.
The honest translation **drops `ref`** and keeps `effect_allele`, letting resolution fill coordinates
from the rsID; the compiler then warns, correctly, that nothing was injected.

**Result.** `validate` passes; `compile` produces `weights.parquet` (84 rows), `annotations.parquet`,
`studies.parquet` and a manifest — 28 variants, 24 genes, 12 categories,
`content_signature: sha256:b398c0bf…`. `compile → reverse → compile` reproduces that signature
**exactly**, so P7 holds over their data; the reverse normalises column order and drops `title`,
`description` and `weighting`, all of which are documented as display/advisory and outside
`content_signature`.

**Two things the run made me write that their file cannot say.** A `sources.csv` — the translated
module has none, so it would not pass the compile gate, which is the correct outcome for annotation
whose terms nobody has established. And `module_spec.weighting` (RM92), which forced an answer to
open question 4: their weights are hand-assigned importances *within* a nutrient domain, and their
scorer divides by the weight of the SNPs it happened to find, so the number is comparable only inside
one domain of one run. Writing that down is `@weight-has-no-unit` doing its job — **and the round
trip then drops the block**, because `weighting` is advisory and not reconstructed by `reverse`. The
only place a module can say what its weights mean does not survive a reverse. Documented, not a bug,
and worth knowing before item 6 leans on it.

---

## The comparison table

Annotation axes only. "Ours" means *a module can state it and the artifact carries it*, not *some
script could compute it*.

| Annotation axis | ClawBio | Ours | Verdict |
|---|---|---|---|
| variant → trait, weighted, with direction | inlined dicts in 4 skills | `variants.csv` | **ours, with provenance they lack** |
| grounding citation per row | a `pmid` string, unchecked | `studies.csv` + `literature.csv` + PMID/DOI existence checks | **ours** |
| per-population allele frequency | fetched from gnomAD at query time | `frequencies.csv`, incl. `faf95`, homozygote and hemizygote counts | **ours** |
| ClinVar significance + review stars | fetched | `clinical_assertions.csv`, plus a 3-way concordance record (RM130) | **ours** |
| gene constraint (pLI/LOEUF) | not carried | `gene_metrics.csv` | **ours** |
| gene–disease validity + mode of inheritance | not carried | `gene_validity.csv` (`moi`, ClinGen classification) | **ours** |
| ACMG SF gene flag | 81-gene frozenset in `acmg_engine.py` | `VariantRow.acmg_sf`, **checked against the published list** | **ours** |
| star allele → function | `GENE_DEFS[g]["variants"]` | `allele_function.csv` (+ `activity_value`, suballele, CNV, hybrid) | **ours** |
| diplotype → metabolizer phenotype | `GENE_DEFS[g]["phenotypes"]` | `diplotypes.csv` | **ours** |
| phenotype → drug action | `GUIDELINES[drug]["recs"]` | `diplotypes.csv` drug rows, denormalised by the drafter | **parity** |
| per-variant drug response | ClinPGx fetch | `pharm_variants.csv`, keyed on all five parts | **ours** |
| CPIC population / clinical context | a `--population` filter | `clinical_context` **in the dedup key** since RM29b | **ours** |
| activity-score → phenotype bins | not carried | `activity_phenotype.csv` | **ours** |
| repeat count / copy number / heteroplasmy bins | not carried | `repeat_alleles.csv`, `copynumbers.csv`, `heteroplasmy.csv` (tissue-keyed) | **ours** |
| HLA allele annotation | listed as *not assessed by this panel* | `haplotypes.csv` — `drug_labels._allele_keys` handles gene-prefixed HLA spellings | **ours** |
| PGS model reference | PGS Catalog fetch + scoring | `pgs.csv` + ancestry-validity fields; scoring is the consumer's | **parity by design** |
| ancestry-stratified effect | `ancestry_risk_associations.json`, with an in-file retraction log | `StudyRow.population` / `GwasEffectRow.ancestry` | **ours** |
| GWAS effect size | GWAS Catalog + Open Targets | `gwas_effects.csv` | **parity** |
| PheWAS across biobanks | 3 cohorts, rendered | expressible as `gwas_effects.csv` rows | **parity** |
| regulatory / expression effect | `gi-*` model inference, GTEx | `expression_effects.csv` (AlphaGenome, per `(variant, gene)`) | **parity, different grain** |
| **molecular consequence + impact + transcript** | VEP, read by the ACMG engine | **absent** | **gap → § plan 2** |
| **region-keyed dosage sensitivity** | `curated_dosage_map.csv`, `element_type=region` | gene-keyed only | **gap → § plan 3** |
| **per-tissue eQTL** | GTEx + eQTL Catalogue, 5 rows by tissue | aggregated over tracks | **gap → § plan 4** |
| **fine-mapping posterior / credible set** | 3 sets with PIP and CS membership | **absent** | **gap → § plan 5** |
| **a call over several genes** | one hardcoded branch (`"special": "warfarin"`) | **absent** | **gap → § plan 1 (RM28)** |
| predictor scores (CADD/REVEL/SpliceAI) | fetched and thresholded | RM23, deferred with named blockers | **known, parked** |
| archaic introgression segments | IBDmix/Sprime/hmmix over two VCFs | **absent, and not annotation** | **§ not taken** |
| ACMG/AMP classification | 12 of 28 criteria implemented | refused by charter | **§ not taken** |
| CNV five-tier classification | ClinGen point framework | refused by charter (same clause) | **§ not taken** |
| DNA-LM predictions (splice/promoter/enhancer/chromatin) | 6 `planned` skills | not annotation | **§ not taken** |
| licence terms per source | empty on all 97 | `sources.csv` + the compile gate | **ours, decisively** |
| signed artifact + round trip | none | Ed25519 + `compile→reverse→compile` | **ours, decisively** |

---

## The gaps, sorted the way RM188 asks

RM188's exit requires each finding **dissolved**, **closed additively with a motivating report in
hand**, or **parked with the reason**.

### (a) A lookup table → an existing kind — *dissolved*

Their nutrigenomics panel, methylation-cycle rsID set, AIMs panel, ancestry-risk associations, and
all three PGx dicts. Every one compiles today. **No work owed.** The useful output is a reference
example, not a schema change — see § plan 6.

### (b) A bounded rule over a table → a binning kind, or a new column

- `consequence` / `impact` / `transcript` — plan 2.
- region-keyed dosage — plan 3.
- per-tissue eQTL — plan 4.
- fine-mapping posterior — plan 5.
- the multi-gene subject — plan 1, and it is RM28's, not a new item.

### (c) A computation over annotation → consumer-side, by design

PRS arithmetic (`gwas-prs`, `wgs-prs`, `profile-report`), IBS and PCA (`genome-compare`,
`claw-ancestry-pca`), the nutrient composite score, the LoF burden count
(`rare-high-impact-variants`), ancestry-effect ratios, fine-mapping *runs* (SuSiE/ABF). The module
supplies the table; `just-dna-lite` does the arithmetic. This is P1 (declarative-not-code) working
as intended and nothing here is owed.

### (d) Model inference → not annotation, no translation

The six `gi-*` skills (DNA language models over sequence), the DeepSpot spatial model, the
methylation clocks, the proteomic organ clocks. A model's output about a sequence is a
*prediction made at query time*, not a curated claim; the closest thing that *is* annotation is a
precomputed score with a named dataset, which is RM23, already parked with reasons.

**One discipline note.** [USE_CASES § 7.2](../USE_CASES.md#7-regulatory-effect--which-gene-a-non-coding-variant-moves-and-which-way-07)
holds open exactly the `gi-chromatin` case — *"this position sits in open chromatin in these cell
types"* — and closes with **"reopen this with a consumer, never with an argument."** Five ClawBio
skills wanting it is an argument. It stays parked.

---

## The plan — what to build, in order, to be a superset on annotation

Sized in the usual units. None of this is filed as an `RMn` by this document; a probe records, the
tracker allocates (`.claude/rm-next.py`).

**1. Take the warfarin case to RM28 as its second corpus entry. — half a day, no code.**
RM28's surviving clause is "pairing across *subjects* — no table keys on more than one", parked
waiting for a corpus. It now has two entries from different domains: CIViC's 209 multi-variant
molecular profiles (RM174) and CPIC's multi-gene dosing guidelines, of which warfarin is the one both
projects hit and neither can express declaratively. Add the entry, re-read the parking decision, and
leave it parked or unpark it on that basis — **do not design the table inside the probe**. The
deliverable is one section appended to RM28 with the measurement: how many CPIC guidelines are
gene-pair-keyed rather than phenotype-keyed, counted off the CPIC snapshot we already provision.

**2. `consequence` + `impact` on `VariantRow`, and the transcript question with them. — a week.**
Two optional columns, minor-legal under P3/P8, with a closed-ish Sequence Ontology vocabulary for
`consequence` and the four-member VEP set for `impact`. **Get the mechanism right**: neither name is
in `RESERVED_NAMES_0_4` today, so `reject_reserved` never claimed them and nothing has to be moved
out of it — an author writing `consequence` now gets the generic `extra="forbid"` message. The
ROADMAP lists them under *planned future annotation axes*, which "get a slot and a specific diagnosis
only when a release actually commits". Committing therefore means one of two things, and choosing is
part of the work: **build the column**, or — if the grain question below defers it — **add the
reserved slot plus a `RESERVED_NAME_REASONS` entry**, so an author hears what the name is held for
instead of the stray-column message. **The blocker to settle first is the same one that parks RM23: grain.** A variant has
one consequence *per transcript*, and `VariantRow` is one row per `(variant_key, genotype)`. Three
options, and the choice is the deliverable: (i) MANE Select only, one value, with `GeneMetricsRow.
mane_select` naming the transcript — cheap, lossy, and honest if the column says so; (ii) the most
severe consequence across transcripts — a ranking policy, which is an interpretation and therefore
out; (iii) a derived `consequences.csv` sidecar keyed `(variant_key, transcript)` — half cost under
P9, no authoring burden, and it is the shape that would *also* unblock RM23. **Recommend (iii), and
settle RM23's grain in the same pass** — they are the same question asked twice, and answering it
once is the whole saving.

**3. Region-keyed ClinGen dosage. — 3–4 days.**
`gene_metrics.csv` cannot hold it (the key is a gene symbol and a region is not one). Either a
`region_metrics.csv` sidecar keyed `(chrom, start, end, name)` with `haploinsufficiency`,
`triplosensitivity` and the ClinGen curation id, or an `element_type` discriminator on the existing
table — and the first is right, because a region row carries coordinates and a gene row carries a
symbol, and `@sidecar-name-and-place` plus the "one CSV = one concern" rule both push apart rather
than together. Enricher side: `clingen.py` gains the region-curation and recurrent-CNV lists it
already saw on the FTP tree in 2026-08-03. Check the ClinGen terms and write the `SourceRow`
(`@write-the-sourcerow` — and the *second surface of an already-declared source* clause applies:
region curation must not claim the gene lane's `(source, layer)` row).

**4. Per-tissue eQTL as its own derived table. — a week, gated on a source decision.**
`eqtl_effects.csv`, one row per `(variant, gene, tissue, dataset)` with `effect_size`, `p_value_num`,
and the tissue as an ontology term (UBERON where GTEx gives one). **Do not widen
`expression_effects.csv`** — it aggregates deliberately and its non-commercial provenance is
AlphaGenome's, while GTEx and the EBI eQTL Catalogue have their own terms. The measurement to do
first is the same one that parked the frequency snapshot: what the bulk artifacts weigh and what the
terms say (`@probe-the-real-file`). **Park it until a consumer asks** — nobody has, and USE_CASES
§7.2's rule applies to this one too.

**5. Fine-mapping posterior. — fold into 4 or park.**
A PIP is per `(variant, trait, study)`, which is `gwas_effects.csv`'s key plus nothing. Two optional
columns there (`posterior_probability`, `credible_set`) is the cheap shape, and GWAS Catalog now
publishes credible sets for harmonised studies. Smallest item on this list; do it when someone
touches `gwas.py` for another reason, not on its own.

**6. Compile their four inlined panels as reference examples. — 2 days, and half of it is done.**
§ *The translation, run* already took `snp_panel.json` through `validate`, `compile` and the round
trip in a scratch directory; what is left is to land it as `reference_examples/nutrigenomics_panel/`
with a `sources.csv` and a README naming the two refusals, and to do the same for
`pharmgx_panel_13_genes/` from `GENE_DEFS`. This is `@probe-becomes-example`, and the remaining
earn is the enrichment pass nobody has run yet: put their 28 PMIDs through `check_literature` **with
provenance quotes**, since § *The short answer* shows existence alone would have cleared all ten
mis-citations in the sibling file. It also gives item 2 a real corpus to test a consequence column
against.

**Order and total.** 6 → 1 → 2 → 3, then 4 and 5 parked behind a consumer. About three weeks of
work for the unparked half, and item 6 is what makes the rest arguable.

---

## What we deliberately do not take

- **ACMG/AMP and ClinGen CNV classification.** Refused by
  [ROADMAP § Annotating core](../ROADMAP.md#annotating-core-not-format-scope-the-05-source-assessment)
  and by the Constitution's no-inference goal. We carry `clin_sig`, `acmg_sf`, the ClinVar review
  stars and the frequencies a classifier reads — the consumer classifies. Their skill implements 12
  of 28 criteria; the remaining 16 need case data, segregation and functional studies, which is
  measurement.
- **Running predictors and choosing their thresholds.** Their PP3 fires on `CADD=35.0≥25.3`. The
  threshold is the interpretation; RM23 carries the score and the dataset, never a verdict.
- **Archaic introgression segments.** A segment call is a sample-level inference from two VCFs — a
  measurement, and the output is about a person, not a locus. The *annotation* half (which alleles
  are archaic-derived) would be a `variants.csv` with a category, and nobody has asked for one.
- **A module-level "what this panel does not cover" declaration.** Their *Genes Not Assessed* table
  is genuinely good reporting, and it is still a report rather than a table: a module's silence is
  already readable from what it contains, `panel` was deprecated for being a claim the compiler could
  not check (RM4), and a hand-written list of what a module *omits* has no way to stay true. If this
  comes back, it comes back as a consumer asking for it, and the answer is probably a compiler-derived
  coverage report rather than an authored field.
- **A skills marketplace, an MCP surface, a benchmark leaderboard, demo genomes.** Different products.
  The one thing worth borrowing in spirit is that they ship a real CC0 genome to run against — our
  equivalent is `reference_examples/`, and item 6 above widens it.

---

## Read beside this: the genomi half

[`GENOMI_SURVEY.md`](GENOMI_SURVEY.md) is RM188's other half, filed the same day by a parallel
session. **The two surveys barely overlap, and that is the useful part** — two consumer-genomics
products, and the annotation they reach for has almost nothing in common:

- genomi reaches **outward from the gene**: pathway membership, Open Targets target–disease scores,
  ENCODE regulatory features, drug mechanism of action, HPA baseline expression. Its §8 prices all
  seven as derived sidecars.
- ClawBio reaches **inward at the variant**: the per-variant clinical axes an ACMG engine consumes —
  consequence, impact, transcript, predictor scores, dosage, credible sets.

Two places they meet, and neither is a collision:

- **Tissue.** Their §8.5 proposes `expression_baseline.csv` (gene × tissue, HPA nTPM); item 4 here
  proposes `eqtl_effects.csv` (variant × gene × tissue, GTEx beta). A baseline and a variant effect,
  and their §8.5 already warns against letting the two share a prefix with
  `expression_effects.csv`. Three tables, three grains, and the naming needs deciding once rather
  than twice — **whichever lands first names all three.**
- **Regulatory.** Their §8.3 `regulatory_features.csv` says *what element a variant sits in*; USE_CASES
  §7.2 holds open *whether that element is open in a given cell type*; `expression_effects.csv`
  already says *which gene it moves*. ClawBio's six `gi-*` skills want the middle one, and §7.2's rule
  — reopen with a consumer, never with an argument — applies to them as it does to everything else.

One shared conclusion worth stating once: **neither competitor is a format.** genomi is a runtime,
ClawBio is a skill library, and both inline their curated annotation as source code. The comparison
that matters is not feature-for-feature; it is that the thing they inline is the thing we compile,
sign and round-trip.

---

## Open questions

1. **How many CPIC guidelines are multi-gene?** Warfarin is the famous one. Item 1 needs the count,
   and we have the snapshot to count it from. If the answer is "three", RM28 stays parked with a
   sharper reason; if it is "thirty", that changes.
2. **Does `consequence` at MANE-Select grain satisfy a real consumer, or only look like it does?**
   Item 2 recommends the sidecar partly to dodge this — but if every asking consumer wants one value
   per variant, the sidecar is over-built and a column with an honest name is better.
3. **Is a region row a second `(source, layer)` for ClinGen, or the same lane?** Item 3 assumes a
   second surface. `@write-the-sourcerow` says a second surface may not claim the first's row; it does
   not say which one region curation is.
4. **~~Is their `weight` on the same scale as ours?~~ Answered by the run, and the answer is no.**
   Their weights run 0.4–0.95 with no stated unit, and their scorer normalises by the weight of the
   SNPs it found, so a domain score is comparable only inside one domain of one run. That is what the
   `weighting` block in § *The translation, run* records. The question that replaces it is sharper:
   **`weighting` does not survive `reverse`**, so the one field that makes a weight interpretable is
   absent from a module reconstructed from its artifact. Documented (RM92 lists it with
   `panel`/`authorship`/`license`) and defensible — it is advisory, not content — but a consumer
   combining two reversed modules has no scale to read. Worth a line in the FAQ at least.
