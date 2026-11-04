# Roadmap — 0.8

**What 0.8 is, decided 2026-11-03 with the maintainer:** the work already built and the fixes already
chosen, plus longevitymap v2's requirements. "The rest goes to 0.9", so everything else that was waiting
here moved to [ROADMAP_0_9.md](ROADMAP_0_9.md), each entry with a dated line under its heading. That
includes RM188's competitor-parity work, which was 0.8's second half from 2026-09-11, the methylation items
(RM317–RM319), and the Gherkin corpus (RM149), which is frozen. This file is now 0.8's scope and nothing else.

Every item is additive under Principles 3/4/8, so each is legal in a minor. Indexed in
[RM_TOC.md](RM_TOC.md), which is the complete list and the place to look an item up.

## The scope

| Part | Items | Where | State |
|---|---|---|---|
| Built on the `0.8` branch, uncut | PT1's RM241, RM258, RM263, RM272, RM275, RM278, RM283, RM288, RM300, RM308, RM313; earlier RM256, RM257, RM259, RM260, RM262 and RM264's docs half | `proposals/PROPOSAL_0_8_PT1.md` and ROADMAP_HISTORY on the `0.8` branch | done; `main`'s roadmap still lists RM241, RM263 and RM308 until the next sync |
| The indel-placement fixes | [RM304](ROADMAP.md#rm304--a-vrs_id-does-not-say-which-vrs-minted-it-and-vrs-21-moves-some-insertion-ids) first, then [RM267](ROADMAP.md#rm267--the-ensembl-snapshot-anchors-a-class-of-insertions-one-base-early-and-resolutioncsv-serves-them-as-a-different-event), [RM270](ROADMAP.md#rm270--an-indels-artifact-key-is-its-sources-spelling-a-left-aligned-vcf-misses-a-respelled-row-and-the-spelling-independent-id-the-enricher-mints-never-reaches-the-artifact), [RM292](ROADMAP.md#rm292--a-verification-check-does-not-say-what-it-checked-against-so-a-check-that-witnesses-itself-reads-as-verified), [RM305](ROADMAP.md#rm305--clinvar-gkms-allele-table-is-an-offline-independent-witness-for-where-an-indel-sits-and-nothing-reads-it) | [ROADMAP.md](ROADMAP.md) | one design, interviewed before it is built; four are high severity |
| The lead's ready minors (2026-11-04) | RM337 (a warning naming each `logs/` file left behind), RM342 (the toolchain in the manifest, with the polars 2 lock) | this file | RM337 ready; RM342 after its interview |
| Chosen earlier | [RM303](#rm303--the-snapshot-layout-is-a-contract-with-six-parties-and-no-model-so-it-belongs-in-just-dna-format) (the snapshot layout as a model), [RM253](#rm253--a-repeat-count-star-allele-ugt1a1-28--ta8-has-no-home-a-diplotype-can-name-and-the-cpic-drafter-translates-none-of-cpics-notation) (a repeat-count star allele) | this file | taken into 0.8 in September |
| longevitymap v2 | RM28's combination half, RM322–RM336 ([the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03)), and [RM236](#rm236--consequence-and-impact-are-planned-axes-with-no-slot-and-an-acmg-engine-reads-both-as-primary-inputs), [RM238](#rm238--a-per-tissue-eqtl-has-no-row-and-expression_effectscsv-is-the-wrong-table-to-widen), [RM239](#rm239--a-fine-mapping-posterior-has-no-column-and-gwas_effectscsv-already-has-its-key) as inputs to RM333's confidence labels | this file and [ROADMAP.md](ROADMAP.md) | design first; RM323 decides before RM324, RM326 and RM329 |

Patch-class items stay on `main` and are not part of this scope, as [RELEASE_CYCLE.md](RELEASE_CYCLE.md) says.

---

## longevitymap v2 — what its requirements need from the format, taken into 0.8 as a priority (2026-11-03)

**Source.** just-dna-lite's `docs/longevitymap_v2/longevitymap_v2_requirements.md` (draft 1, 2026-11-03),
the plan for re-curating `longevitymap` as 2.0.0 around evidence tiers and seven per-locus axes. It was
read against the 0.7.1 schema on 2026-11-03. Most of its §6 fits today. The items below are the places where
it does not, each with its Principle 9 price. Every one is additive, so each is legal in a minor (P3/P8).

**Status.** The maintainer took the fifteen new items into 0.8 **as a priority** on 2026-11-03. One shape is
already decided: `tradeoff` is **computed** from per-trait rows and never authored (RM327). Every item
the plan needs, new or older, carries the tag `*for* longevitymap v2` in its index row, so
`grep -n 'for\* longevitymap v2' docs/RM_TOC*.md` lists the whole group. Its build plan is the
proposal for the next round on the `0.8` branch, which the pm seat writes; PT1 is concluded.

**Order.** RM323 first, because RM324's tier, RM326's outcome strip and RM329's age-of-action class all
land wherever RM323 puts per-locus facts. RM322 next, since APOE is the lead locus.

| Item | What it adds | Price (P9) | Note |
|---|---|---|---|
| [RM323](#rm323--a-fact-about-a-locus-has-no-authored-home-so-every-per-locus-axis-is-copied-onto-each-genotype-row-and-nothing-checks-the-copies-agree) | where per-locus facts live: typed columns per genotype plus an agreement warning, or a locus table | full ×n, or a new table kind | **decide first** |
| [RM322](#rm322--diplotypescsv-carries-none-of-the-axes-a-scored-finding-needs-so-apoe-the-modules-headline-result-cannot-state-its-tier-mechanism-or-trade-off) | `DiplotypeRow` gains `negatives`, `category`, `priority`, `flags` (maybe `actionability`), so APOE can carry the axes | full ×4–5 |  |
| [RM324](#rm324--there-is-no-evidence-tier-column-so-the-axis-that-gates-visibility-is-a-flags-tiera-token) | evidence tier as value + scheme | full ×2 | home from RM323 |
| [RM325](#rm325--studiescsv-has-no-sample-size-and-v2s-tier-a-rule-is-stated-in-n) | `StudyRow` sample size (and cases) | full ×1–2 |  |
| [RM326](#rm326--a-study-row-cannot-say-which-outcome-it-measured-so-the-definition-of-pro-longevity-lives-in-a-study_design-prefix) | `StudyRow` phenotype class; evidence role and the outcome strip derived from it | full ×1, derived near-zero | check EFO first |
| [RM327](#rm327--pleiotropy-has-no-per-trait-row-so-a-trade-off-can-only-be-prose-and-tradeoff-is-computed-rather-than-authored) | per-trait benefit/harm table (mediator folds in); `tradeoff` computed; reserve the name | full (new kind), derived near-zero, reservation a patch | `tradeoff` decided |
| [RM328](#rm328--no-study-row-can-name-the-ancestry-it-was-measured-in-so-european-only-evidence-is-a-hand-set-flag) | `StudyRow` ancestry on a vocabulary; `eur_only_evidence` derived | full ×1, derived near-zero | RM188 axis 2 |
| [RM329](#rm329--an-age-stratified-estimate-has-no-age-band-so-age-of-action-is-reconstructed-from-statistical_test-prose) | `StudyRow` age band and whose age | full ×2–3 | interim works (RM140) |
| [RM330](#rm330--an-effect-measured-in-one-sex-one-smoking-stratum-or-one-genotype-has-no-row) | the stratum an estimate was measured in; sex as the first query-time modifier | full ×2 | RM188 axis 3 |
| [RM331](#rm331--a-study-measured-on-an-ld-proxy-cannot-say-so-and-filing-it-under-the-lead-checks-the-proxys-allele-against-the-leads) | `StudyRow` proxy variant + r²; the allele check follows the proxy | full ×2–3 |  |
| [RM332](#rm332--a-beta-has-no-unit-on-authored-rows-while-gwas_effectscsv-has-carried-one-since-06) | `effect_unit` on authored rows, as `gwas_effects.csv` has | full ×1–2 |  |
| [RM333](#rm333--the-effector-gene-behind-a-gwas-locus-has-no-source-and-no-column) | an Open Targets lane; effector gene, score, release on a derived table | half, plus a lane | licence unprobed |
| [RM334](#rm334--an-hla-allele-has-no-table-and-tag-snps-cannot-stand-in-for-one) | an HLA allele table keyed `(gene, allele)` | full (new kind) |  |
| [RM335](#rm335--model-organism-evidence-has-nowhere-to-go-and-a-study-row-naming-the-rsid-claims-the-mouse-study-was-about-the-human-variant) | a model-organism evidence table | full (new kind) |  |
| [RM336](#rm336--a-doi-written-into-pmid-parses-as-five-or-six-pubmed-ids-and-the-literature-pass-looks-each-one-up) | a DOI-token arm in `validate_pmid_cell` | near-zero (a refusal or a warning code) | reproduced |

**Older items the plan also needs, tagged rather than moved** (each keeps its own entry; the 2026-11-03
scope decision put each in 0.8 or 0.9, as marked):

- **RM236** (this file, **0.8**) — causal confidence C1 and effector confidence E1 both key on a variant being coding.
- **RM238** (this file, **0.8**) — the cis-QTL colocalisation behind effector confidence E1/E2.
- **RM239** (this file, **0.8**) — the fine-mapping posterior is the input to causal confidence C1–C4.
- **RM241** (this file, **built on `0.8`**) — v2 declares `weighting:` precisely to say it has no weights, and `reverse` drops the block.
- **RM263** ([ROADMAP.md](ROADMAP.md), **built on `0.8`**) — v2 cites preprints, whose rows hold a DOI and need a PMID; RM336 is the parsing half.
- **RM294** ([ROADMAP_0_9.md](ROADMAP_0_9.md), **0.9** since 2026-11-04, after the one-scale tier decision) — a source's evidence grade travelling into a module is the same column family as RM324's tier.
- **RM302** ([ROADMAP_0_9.md](ROADMAP_0_9.md), **0.9** since 2026-11-04: v2's conclusion is already lay) — v2 writes for three readers (citizen, geneticist, ageing researcher), which is the register question.
- **RM308** ([ROADMAP.md](ROADMAP.md), **built on `0.8`**) — v2 hand-writes per-genotype conclusions for its scored loci and a 528-rsID legacy layer.
- **RM321** ([ROADMAP.md](ROADMAP.md), **a patch on `main`**) — v2's plan sets `pleiotropic` and `conditional` expecting behaviour.
- **RM28** (this file, **0.8**: its combination half, taken in 2026-11-04) — KL-VS buffering in APOE4 carriers joins two loci on two chromosomes, so no haplotype holds it. It is now a defined combination, and its facts sit on RM323's table.
- **RM188** ([ROADMAP_0_9.md](ROADMAP_0_9.md), **0.9**) — its axes 2, 3 and 5 are now numbered, as RM328, RM330 and RM324, all three in 0.8.
- **RM248** ([ROADMAP_0_9.md](ROADMAP_0_9.md), **0.9**) — v2's §5 is a report specification: a context card, grouping by mechanism, a research view. The report is the consumer's to build meanwhile.

The authored `report:` block in [ROADMAP.md's idea-book](ROADMAP.md) is the unnumbered half of RM248 and
answers v2's §8 consumer requests 1 and 2 (category prose from the module, no "Net weight").

## RM322 — `diplotypes.csv` carries none of the axes a scored finding needs, so APOE, the module's headline result, cannot state its tier, mechanism or trade-off

**Cut 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §3): `priority` (it restates the tier; v2 says it is "derived from tier") and `actionability` (v2's policy "late-acting ⇒ descriptive" belongs in its README). `DiplotypeRow` gains only **`negatives` and `category`**.

**Decided 2026-11-04 by the maintainer: four columns, no `flags`.** `DiplotypeRow` gains `negatives`, `category`, `priority` and `actionability`, each full price, with RM70 as the precedent. `flags` stays off: no tier acts on its tags (RM321), and v2's flag tokens are what RM323–RM330's typed columns replace. Per-locus facts go on RM323's table, with APOE ε2 and ε4 as `haplotype` subjects.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format (`DiplotypeRow`) + compiler (the diplotype parquet and `reverse`) · **Motivating case** longevitymap v2 requirements §6.4, decision D2 · *for* longevitymap v2 · *related* RM323, RM28

**What was confirmed.** `DiplotypeRow` has `gene`, `haplotype_a`, `haplotype_b`, `trait_efo_id`,
`direction`, `clin_sig`, `phenotype`, `conclusion` and the PharmGKB drug block (`drug`, `response`,
`evidence_level`, `recommendation_strength`, `clinical_context`). It has no `negatives`, `category`,
`priority`, `flags`, `actionability`, `stat_significance` or `effect_*`. v2 scores APOE once, as an ε
diplotype (R-APOE-1), so its tier A locus is the one locus that can say none of the things the report
groups and orders by.

**What already fits.** The key includes `trait_efo_id`, so one row per (diplotype, trait) is legal: an
Alzheimer's row and a lifespan row per ε pair, which is how the plan's two framings coexist.

**Shapes, priced.**

- **Widen `DiplotypeRow`** with the general annotation columns: `negatives`, `category`, `priority`,
  `flags`, and possibly `actionability`. Full price each, minor-legal; RM70 is the precedent for
  carrying a `VariantRow` column to a PGx table. `VariantRow` itself calls these axes general ("any
  variant finding may carry them"), so this is not a foreign domain's columns on a PGx table. Each
  is three touch points, plus the diplotype parquet and `reverse`.
- **Author APOE as rs429358/rs7412 genotype rows in `variants.csv`.** Refused: a per-SNP row cannot
  say ε2/ε4, and the plan's own rule is to score APOE once.
- **README prose.** Drops the axes out of the data entirely.

**To design.** Which columns, and whether the home RM323 decides for locus-level facts also reaches a
gene-pair subject (it does not if that home is keyed on `variant_key`).

## RM323 — a fact about a locus has no authored home, so every per-locus axis is copied onto each genotype row and nothing checks the copies agree

**Cut 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §3): causal and effector confidence are **not authored**. The parquet carries their raw inputs: the fine-mapping posterior, the coding consequence, the L2G score and coloc. The C1–C4 / E1–E4 labels are v2's rubric, i.e. policy, so they live in v2's README and are computed by the consumer, as "evidence role" is. The run computed them on 67 of 75 rows. The 8 hand-curated inputs go in `overrides.csv` as corrections to the derived inputs. The meta-table keeps `tier`, `age_of_action` and its confidence, and gains **`flags`**: the maintainer chose it for parity, so every kind of member can carry tags the way `variants.csv` rows do, such as `ap:<strength>` and `hallmark:…`. `also_in:<module>` stays prose.

**Final, 2026-11-04, the maintainer: "go with C".** This supersedes both decisions below. The per-locus facts
(tier, causal and effector confidence, age of action and its confidence) are columns of **the meta-table only**.
They are never repeated on `variants.csv` or `diplotypes.csv`.

- A single locus's facts are a meta-table row with **one member** and no finding.
- A member is an item of a single-statement table. It may be a locus-level reference (a `variant_key` alone),
  for a fact that does not depend on the genotype, or a full row's key.
- APOE ε2 and ε4 are each a one-member row naming their allele.

One new table holds facts and combinations. Priced at about 20 (a new table at about 10, plus five fact columns
and the finding's columns), against about 30 for a separate fact table or for facts repeated on the
existing tables. The maintainer's standing rule from this decision is in [RM28](#rm28--meta-conclusions-the-predicate-half):
weight toward fewer entities.

**Re-decided 2026-11-04 by the maintainer: no new fact table, and no subject kinds.** This supersedes the
`(subject_kind, subject)` key below.

The per-locus facts become **columns on the single-statement tables** that already exist, such as
`variants.csv` and `diplotypes.csv`, and on the meta-table's rows. The maintainer: "Authoring surface is
human centered. If it were a db it'd be 10x more tables, because many columns are duplicated across
individual-loci-type tables and properly normalized db resolves this by pairing adapters. Humans have trouble
reading such." So the authored layer stays denormalized on purpose. Compilation may normalize it, which is
[RM346](ROADMAP_1_0.md#rm346--the-authored-tables-are-denormalized-for-people-and-the-parquets-copy-that-shape-so-a-machine-reader-gets-it-too) (1.0).

**What this means for a value that differs between rows.** A fact sits on a statement (one genotype row,
one diplotype row), so it is a property of that statement. Two rows of one locus may legitimately differ:
APOE's ε2/ε4 and ε3/ε4 rows each carry their own age-of-action confidence, which dissolves the ε2 versus
ε4 break the archive check found. So no agreement warning is built. When a locus's facts are meant to be
identical on every row, that is the author's to keep, and the 1.0 normalized shape will show any
disagreement as two values. (Superseded by C the same day: facts are not repeated on rows, and the key rule under RM28 decides
what counts as a disagreement.)

**Reopened 2026-11-04 by the maintainer**: "why can't each part of the combination live in its respective table, and the combination plus its finding in the meta-table? A new table is the most expensive thing." The decisions below stand until the analysis is answered.

**Decided 2026-11-04 by the maintainer: a per-locus fact table keyed `(subject_kind, subject)`.** It has three
kinds:

- `variant`: a `variant_key`;
- `gene`: a symbol, for gene-level facts such as LoF burden;
- `haplotype`: `(gene, allele name)`, resolved against `haplotypes.csv` or RM334's HLA allele table.

It deliberately has no region or locus kind. A combination of several subjects, each in a stated genotype
state, is defined by RM28's meta-table. Since 2026-11-04 that is also in 0.8, and each combination becomes a
fourth subject kind here. Facts about a combination therefore live on this table too, never on a second one.

**What the shape was tested against.** A subagent checked it against v2's full research archive
(`data/input/4bf03886-….zip`, the seed's 161 loci): **121 fit, 37 strain, 3 break**. All three breaks are
named alleles, and the `haplotype` kind holds them:

- APOE ε2 and ε4 carry different age-of-action confidence;
- HLA-B\*57:01 and HLA-DRB1\*15:01 carry facts that belong to the allele, not its tag SNP.

**The strains need no new key, but they do need three authoring rules, stated in the proposal:**

1. Which study's fine-mapping posterior sets a causal-confidence level (the seed uses the maximum).
2. A fact measured on a proxy is marked as such (RM331's columns).
3. A European-only tier is scoped by ancestry (RM328's derived flag), never transferred.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first, and **decide this before RM324, RM326 and RM329** · **Owner** format + compiler · **Motivating case** longevitymap v2 requirements §4.2 · *for* longevitymap v2 · *related* RM322, RM324

**What was confirmed.** `VariantRow` keys on `(variant_key, genotype)`. v2's tier, causal confidence,
effector confidence, age of action, outcome profile and animal support describe the **locus**, not a
genotype, so the plan writes each as a `flags` token on all three genotype rows. Nothing compares the
copies, so an edit to one row leaves the locus saying two things. `annotations.parquet` is the
per-variant table, but it is derived (keyed on the variant-effect pair) and an author cannot write it.

**Shapes, priced, neither picked.**

- **Typed optional columns on `VariantRow`**, repeated per genotype, plus a new warning code when the
  rows of one variant disagree. Full price per column; the code is minor-class (RM308's rule).
- **A locus table keyed on `variant_key`** that the per-locus columns live on. Full price, a new table
  kind. It joins the frozen identity, so nothing is restated. It does not reach a diplotype subject
  (RM322), and APOE is the module's lead locus.

The decision is where the per-locus axes live. RM324's tier, RM326's derived outcome profile and
RM329's age-of-action class all land wherever this decides.

## RM324 — there is no evidence-tier column, so the axis that gates visibility is a `flags: tier:A` token

**Placement updated 2026-11-04.** The one `tier` column goes on the meta-table only (RM323's final decision, "go with C"). The scale is still declared once per module.

**Decided 2026-11-04 by the maintainer: one `tier` column, with the scale declared once per module.** The tier column goes on RM323's fact table. The module names the scale it grades on once in `module_spec.yaml`, as `weighting:` names its scale. A module therefore holds one scale, and a source's own grade cannot sit beside the module's tier in this column. RM294 (STRchive's grade) moved to 0.9 for that reason.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format · **Motivating case** longevitymap v2 requirements §4.1 · *for* longevitymap v2 · *related* RM323, RM188 (axis 5), RM294

**Need.** v2's tier A–D decides what is scored and what a reader sees by default. The plan carries it
as `flags: tier:A` and derives `priority` from it. That makes `priority` (described only as "priority
level override") a second spelling of the tier.

**What not to reuse.** `evidence_level` is PharmGKB's closed `1A`–`4` on the PGx tables. Writing a
module's own A–D scale into it puts two instruments under one name (P5).

**Shape.** A value plus the scheme it is measured on, refused without the scheme: the 0.7
`StudyRow.confidence` / `confidence_unit` pair is the precedent, and `@weight-has-no-unit` is why.
Full ×2. Where it lives is RM323's decision. Design it with RM188's axis 5 (a salience separate from
clinical severity; dna-engine carries a `tier`) and RM294 (whether a source's evidence grade travels
into a module), since all three are one column family.

## RM325 — `studies.csv` has no sample size, and v2's tier A rule is stated in N

**Decided 2026-11-04 by the maintainer: `sample_size`, a closed `sample_unit` beside it (individuals / lives), and `n_cases`.** A magnitude carries its unit beside it (`@weight-has-no-unit`), so v2's "N ≥ 100k lives" is checkable from the artifact. The names still get the P5 audit in the proposal.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format (+ enricher, if a derived N is filled) · **Motivating case** longevitymap v2 requirements §4.1 · *for* longevitymap v2 · *related* RM324, RM326

**What was confirmed.** Tier A requires "N ≥ 100k lives, or ≥ 3k cases above the 90th percentile".
No table in the format carries a sample size. A grep for `sample_size` or `n_cases` over the schema
finds nothing, on `StudyRow` or on `GwasEffectRow`. So the rubric cannot be checked from the artifact.

**Shape.** `sample_size` (and `n_cases` for case-control designs) on `StudyRow`. Full ×1–2. **The
name needs the P5 audit**: parental-lifespan studies count *lives* (two parents per participant),
which is not the number of people genotyped. A derived N on `gwas_effects.csv` is a separate half-cost
option. The GWAS Catalog publishes its sample description as text, so probe the real field before
modelling it (`@probe-the-real-file`).

## RM326 — a study row cannot say which outcome it measured, so the definition of "pro-longevity" lives in a `study_design` prefix

**Measured 2026-11-04, then decided by the maintainer.**

The measurement was run by a subagent against both ported longevitymap `studies.csv` files, v2's
`evidence/K_definitions_comparison.csv`, and OLS4. The trait term separates **0 of the 12 classes in
real rows**. Neither ported file fills `trait_efo_id`. The one longevity term in real use, OBA_VT0005372
(EFO_0004300 "longevity" is obsolete and points to it), covers at least four classes. In principle a
term separates only PARENTAL_LIFESPAN (EFO_0007796) and HEALTHSPAN (EFO_0009762). Other findings:

- `study_design` is free text and does not separate the classes either.
- 15 of the K file's 63 PMIDs carry two or three classes.
- v2 spells three class names two ways (FAMILIAL/FAMILIAL_LONGEVITY, MR/MR_MEDIATOR,
  BIOMARKER/BIOMARKER_CLOCK).
- Three real studies fit none of the twelve.

Decided:

- **The column is built:** `phenotype_class` on `StudyRow`, **open, with v2's twelve as the recommended
  members**. A token outside them draws a warning, which catches spelling drift without refusing a
  study that fits no class.
- **One paper, several classes: RM140's rule.** Two rows for one `(variant_key, pmid)` are not duplicate
  citations when both state `phenotype_class` and the values differ. The key stays as it is, and the
  duplicate check narrows (`@absent-is-not-different`).

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format + compiler (derived columns) · **Motivating case** longevitymap v2 requirements §4.5, R-DEF-1 · *for* longevitymap v2 · *related* RM323, RM325

**Need.** v2 sorts every study into one of twelve phenotype classes (`EXTREME_SURVIVAL_CC`,
`PARENTAL_LIFESPAN`, `OWN_SURVIVAL`, `VIABILITY_AF`, `HEALTHSPAN`, `MULTIVARIATE_AGEING`, `FAMILIAL`,
`DISEASE_DEPLETION`, `RARE_BURDEN`, `EVOLUTIONARY`, `MR`, `BIOMARKER`), and the class decides what a row
may do. The plan writes it as a prefix in `study_design`. But `study_design` describes the study
(case-control, GWAS, meta-analysis) and the class describes the outcome, so a prefix puts two axes in
one cell (P5).

**Ask first whether it is derivable.** `StudyRow.trait_efo_id` already distinguishes some classes
(OBA life span against EFO parental longevity). Measure how many of the twelve an ontology term
separates before adding a column.

**Shape.** One optional column with a vocabulary (closed or recommended-open is a decision). Full ×1.
Two things become **derived, near-zero**, once it exists:

- *evidence role* (score or annotate). This is the module's own policy over classes, so it belongs in
  the module's README, never a column.
- *the outcome strip* per locus (healthspan / lifespan / exceptional survival). Kleene, never
  two-valued: a locus with no study row of a class is **untested** and withheld, never "no effect".

## RM327 — pleiotropy has no per-trait row, so a trade-off can only be prose, and `tradeoff` is computed rather than authored

**Default under the 2026-11-04 reduction rule (the pm seat's reading; the maintainer may veto):** a per-trait judgement is a row of RM28's meta-table: one member, `trait_efo_id`, and `direction` (`protective`/`risk`). `tradeoff` is computed over those rows, and no new table kind is built for this item.

**Key to re-derive, 2026-11-04.** RM323 no longer has subject kinds, so "align on RM323's subject" now means: a per-trait row is keyed on an item of a single-statement table plus `trait_efo_id`, using the same item references as the meta-table's members. The proposal settles the exact spelling.

**Decided 2026-11-04 by the maintainer: the key aligns on RM323's subject.** It is `(subject_kind, subject, trait_efo_id)`, and `effect_allele` is kept for `variant` subjects only; a haplotype or gene subject is its own allele. RM323, this table and later RM28 then share one identity, so APOE ε4's per-trait rows are `haplotype` rows.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**; the `tradeoff` shape is **decided** (computed, by the maintainer, 2026-11-03), the table is design first · **Owner** format + compiler · **Motivating case** longevitymap v2 requirements §4.2 (pleiotropy, mediator), §10 · *for* longevitymap v2 · *related* RM321, USE_CASES § 6a

**What was confirmed.** `VariantRow` keys on `(variant_key, genotype)`, so a genotype row states one
claim about one trait. Re-keying a shipped authored table is major-only (P3; RM140's text). `DiplotypeRow`
already keys on `trait_efo_id`, so the two tables disagree on whether pleiotropy is a row. The per-trait
*facts* already arrive in `gwas_effects.csv` (derived, with `effect_direction` increase/decrease). What
has no home is the curator's per-trait *judgement*: whether this allele's effect on that trait is a
benefit or a harm, which `VALID_EFFECT_DIRECTIONS` deliberately does not say.

**`direction: contested` is not the interim.** Its description says the sources disagree about the sign.
At a trade-off nobody disagrees: two known effects point opposite ways. SH2B3 and CDKN2B-AS1 are
genome-wide-significant lifespan hits, so their lifespan sign is established, and the trade-off belongs
in `negatives` until this table exists.

**Shape.**

- **An authored per-trait table** keyed on `(variant_key, effect_allele, trait_efo_id)`, carrying the
  existing `direction` vocabulary, a role (`outcome` or `mediator`), and a citation. The mediator EFO the
  plan parks in `flags: mediator:` folds in here, so `trait_efo_id` stays role-free. Full, a new table
  kind.
- **`tradeoff`, computed, never authored** (decided). True when an allele has a `protective` and a `risk`
  row across traits. Kleene: false only when every trait's judgement is present and none of them is
  opposite, and unknown otherwise, unless both signs are already present. A derived column, near-zero.
- **Reserve the name `tradeoff`** in `RESERVED_NAMES_0_4` with a reason, so nobody authors it before
  the computed one lands. **Done 2026-11-03, on `main`** as a patch: every authored model now refuses
  the column with that reason rather than the generic stray-column message. When the derived column
  ships, the name moves from the reserved set to `MISPLACED_COLUMN_REASONS`, since it will then be real
  on a generated table and still never authored.

## RM328 — no study row can name the ancestry it was measured in, so "European-only evidence" is a hand-set flag

**Decided 2026-11-04 by the maintainer: the 1000G superpopulation codes** (AFR, AMR, EAS, EUR, SAS), the binding `PgsRow.training_ancestry` already uses.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format + compiler (derived) · **Motivating case** longevitymap v2 requirements §5.4 (R-ANC-1, R-ANC-2) · *for* longevitymap v2 · *related* RM188 (axis 2)

**What was confirmed.** `StudyRow.population` is free text. `GwasEffectRow.ancestry` and
`PgsRow.training_ancestry` exist but each is scoped to its own table. RM188 sighted this axis three times
in other projects (dna-engine's `transferability`, kaiseki, OmniGenis). This is the first in-house
module that needs it.

**Shape.** A multi-valued `ancestry` on `StudyRow` bound to a vocabulary. **Which one is the decision**:
the 1000G superpopulation codes behind `training_ancestry`, or the gnomAD population list, and
`vocab.py` forbids merging the two. Full ×1. Then `eur_only_evidence` is **derived** (near-zero): every
supporting row says EUR. Kleene again: a row with no ancestry makes the answer unknown, never false.
The ancestry banner (R-ANC-3) is just-dna-lite's half.

## RM329 — an age-stratified estimate has no age band, so age of action is reconstructed from `statistical_test` prose

**Cut 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §3): `age_event` (0 v2 rows with an event other than death). The band is `age_min`, `age_max` and whose age (`age_of`); names still get the P5 audit. Rows that differ only by band narrow the duplicate-citation check, RM140's pattern, extended to bands.

**Severity** low · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format · **Motivating case** longevitymap v2 requirements §4.2 (age of action), Timmers 2019 age bands · *for* longevitymap v2 · *related* RM323, RM140

**Interim that works.** One study row per age band, each with a stated and different
`statistical_test`. RM140's rule silences `duplicate_study_citation` for exactly that case. Otherwise
it warns, in both modes, and never refuses.

**Shape.** Band bounds plus whose age they are: participant or parent, at which event (death,
recruitment). Full ×2–3. The names need the P5 audit before they are fixed. The age-of-action *class*
(LIFELONG, MIDLIFE, LATE…) is a per-locus judgement and lands in RM323's home. Its confidence grade
(DIRECT, DIRECT_WEAK) is partly derivable from the bands once they are data.

## RM330 — an effect measured in one sex, one smoking stratum or one genotype has no row

**Narrowing extended 2026-11-04** (the final run's gap 12). Two rows that differ only by stratum do not count as a duplicate citation, RM140's pattern.

**Decided 2026-11-04 by the maintainer: the study's stratum and a sex condition.** `StudyRow` gains the stratum an estimate was measured in, a modifier and its level (full ×2). Conclusion rows gain one closed `sex` condition (male/female), which the consumer matches against karyotype. This is RM28's "plain column on demand" rule, with sex as its first class. A modifier that is another locus's genotype stays RM28's (0.9).

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format · **Motivating case** longevitymap v2 requirements §4.2 (context), §10 (`effect_modifiers`) · *for* longevitymap v2 · *related* RM188 (axis 3), RM28

**Need.** FOXO3 rs2802292 is positive in men only, HLA-DRB1\*15:01 is anti-longevity in men, and some
estimates exist only in smoking strata. The plan writes these as `flags: sex_specific:m` and in the
conclusion prose. RM188 sighted this axis three times (open-genome-atlas, a nutrigenomics project,
genomi's caveat). `CopyNumberRow.modifier_gene` / `modifier_cn` is the only precedent, and it is genetic.

**Two different things, kept apart.**

- **The stratum a study measured in**: a fact about the estimate, so optional `StudyRow` columns (the
  modifier and its level). Full ×2.
- **A conclusion that depends on the modifier**: the consumer supplies it at query time (sex from
  karyotype, smoking from nothing). That is the injected cofactor RM28 dropped in 2026-08 with the rule
  "each class gets a plain column on demand". This is the demand, and sex is the candidate first class.

A modifier that is **another locus's genotype** (KL-VS in APOE4 carriers) is not this item. It is RM28's (in 0.8 since 2026-11-04)
corpus entry.

## RM331 — a study measured on an LD proxy cannot say so, and filing it under the lead checks the proxy's allele against the lead's

**Cut 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §3): **authors write only `proxy_rsid`.** r² has no meaning without its population, so r² and its population are a pair, and the pair is **computed**: the enricher asks an LD reference for the r² between proxy and lead in the study's own `ancestry` and writes it to a machine-written table (half price). The allele check runs against the proxy's alleles.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format + compiler (`_check_study_effect_alleles`) · **Motivating case** longevitymap v2 requirements §6.2 (`rsid`, `ld_proxy_of`), §6.4 (APOE proxies) · *for* longevitymap v2 · *related* RM91

**What was confirmed.** The plan scores lead variants only and records proxies "on study rows". But
`StudyRow` has no `flags`, so there is nowhere to write that. A study of a proxy then has two homes, and
both are wrong:

- **Under the lead's rsID**, `_check_study_effect_alleles` checks the proxy's `effect_allele` against
  the lead's alleles. It refuses if they differ and passes silently, with the wrong meaning, if they
  happen to match.
- **Under the proxy's rsID**, it raises `study_variant_orphan`.

The APOE region alone has five proxies (rs2075650, rs4420638, rs769449, rs405509, rs449647), and
rs2075650 is the one genome-wide hit in the Sebastiani 2012 classifier.

**Shape.** A proxy column pair on `StudyRow` (the measured variant and its r², plus the LD reference
population), with `effect_allele` checked against the proxy's alleles rather than the lead's. Full ×2–3.

## RM332 — a `beta` has no unit on authored rows, while `gwas_effects.csv` has carried one since 0.6

**Cut 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §3): the `VariantRow` half, which reverses the morning's "both tables". `effect_unit` is on `StudyRow` only, and the parquet joins it onto a variant's effect from the matching study row.

**Decided 2026-11-04 by the maintainer: both tables.** `effect_unit` goes on `StudyRow` and on `VariantRow`, free text and verbatim, mirroring `gwas_effects.csv`: wherever an effect size is authored, its unit sits beside it.

**Severity** low · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority** · **Owner** format · **Motivating case** longevitymap v2 requirements §6.2 (`effect_measure`), §9 step 3 (sign conventions) · *for* longevitymap v2 · *related* `@weight-has-no-unit`

**What was confirmed.** `GwasEffectRow.effect_unit` (0.6) records the unit of a `beta` verbatim.
`VariantRow` and `StudyRow` have only `effect_measure`. v2's betas come in years per allele (sometimes
doubled from a parental estimate), in Martingale residuals (Pilling) and in healthspan hazards (Zenin),
so the plan writes the unit into `statistical_test` prose.

**Shape.** `effect_unit` on `StudyRow` (and on `VariantRow`, which is a decision), free text and verbatim,
mirroring the derived table. Full ×1–2. A sign convention ("positive = shorter life") is not a unit:
`effect_allele` with `direction` already says it.

## RM333 — the effector gene behind a GWAS locus has no source and no column

**Placement settled 2026-11-04.** The effector-confidence label is never authored (RM323's cut). This lane's derived table is one of its inputs, beside coloc and the coding consequence.

**Licence probed 2026-11-04 (all claims checked at the source); decided by the maintainer: build, under Open
Targets' own terms plus its notice.**

What the probe found:

- L2G now lives in the Platform: release 26.09, dataset `l2g_prediction`, on EBI's FTP. There is no
  Hugging Face copy.
- The release is marked CC0 1.0 (the licence page, and the croissant's only `license` key).
- The terms of use add "no additional restrictions … other than those provided by the original data
  owners" and a third-party-rights disclaimer.

The `SourceRow` therefore records `commercial_use=True`, `share_alike=False`, `redistribution=True`, and
`notice` carries that disclaimer verbatim.

**For a lawyer, named and not settled:**

- "marked with" CC0 against "dedicates", for data Open Targets did not wholly author;
- whether "all Open Targets users" reaches a module's buyer;
- whether the CC BY-SA 3.0 of ChEMBL and HPA, as training inputs, reaches the scores;
- whether a CC0 mark satisfies the CC BY 4.0 attribution owed to eQTL Catalogue and GTEx;
- FinnGen's terms, unstated at its source;
- the 26.09 inputs missing from Open Targets' licence table;
- PanelApp's "commercial use for Open Targets".

**For 0.9:** the host licence defers to the original owners, and an L2G row cannot name its owner
(`@a-hosts-terms-are-not-its-contents-terms` assumes a record can override). That is a `SourceRow` axis
gap, filed as [RM345](ROADMAP_0_9.md#rm345--sourcerow-cannot-state-five-licence-shapes-alphagenomes-four-and-a-host-licence-that-defers-to-owners-a-row-cannot-name) with AlphaGenome's four (`probes/ALPHAGENOME_ATLAS.md` §2.6).

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** enricher (a new lane) + format (a derived table's columns) · **Motivating case** longevitymap v2 requirements §4.2 (causal and effector confidence, R-CAUSAL) · *for* longevitymap v2 · *related* RM239, RM238, RM236

**Need.** v2 names a gene only at effector confidence E1/E2, using Open Targets locus-to-gene (L2G)
scores and coloc. `VariantRow.gene` is a symbol with no provenance, so nothing tells a nearest gene from
an effector call. RM239 covers the fine-mapping posterior on `gwas_effects.csv`, RM238 the per-tissue
eQTL (parked), and RM236 the coding consequence that C1/E1 key on. No item covers L2G, and no lane reads
Open Targets.

**Shape.** An Open Targets snapshot lane, walked through [CACHE_SURFACE.md](CACHE_SURFACE.md)'s checklist,
**licence probed first** (not verified here). Effector gene, score, method and release on a derived table
(half cost). The C1–C4 / E1–E4 labels are the module's rubric over those inputs, so they are computed
once the inputs exist, never authored.

## RM334 — an HLA allele has no table, and tag SNPs cannot stand in for one

**Cut 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §3): **the new HLA table.** `allele_function.csv` (keyed `(gene, allele)`) holds the 8 v2 alleles, and meta-table rows hold their facts and findings. The nomenclature grammar check applies to HLA genes on `allele_function.csv`.

**Decided 2026-11-04 by the maintainer: grammar now, the list in 0.9.** The format checks the nomenclature's grammar (`gene*field:field` at a stated resolution). Checking that an allele exists in IPD-IMGT/HLA's list is an enricher lane whose licence is unprobed, and it waits for 0.9.

**Severity** low · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format · **Motivating case** longevitymap v2 requirements §2 (R-HLA), §10 · *for* longevitymap v2 · *related* RM331

**Need.** HLA-DRB1\*15:01 and B\*57:01 are v2's most consistent non-APOE signals, and the plan defers
them to tag SNPs flagged with r².

**Why no existing brick fits.** `HaplotypeRow` is a *definition*: the variants that are on one strand.
An HLA tag SNP is a probabilistic proxy whose r² depends on ancestry, so writing it as a definition would
be a false claim. `AlleleFunctionRow` has the nearest key, `(gene, allele)`, but its columns are PGx
activity and function.

**Shape.** A per-allele carrier table keyed on `(gene, allele)` at a stated field resolution (two-field),
with `direction`, `trait_efo_id`, `conclusion` and a citation. The consumer joins it against an HLA
typing call, which is a measurement a SNP VCF does not contain. The tag-SNP fallback reuses RM331's proxy
shape. Full, a new table kind. Validating the nomenclature (IPD-IMGT/HLA) is an open question.

## RM335 — model-organism evidence has nowhere to go, and a study row naming the rsID claims the mouse study was about the human variant

**Severity** low · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**, design first · **Owner** format · **Motivating case** longevitymap v2 requirements §4.3 (R-ANIMAL-1…5), §10 · *for* longevitymap v2 · *related* RM327

**What was confirmed.** The plan's interim is a `studies.csv` row with `study_design: model_organism`.
That row is false either way:

- **With the rsID**, it says a mouse lifespan study was about the human SNP.
- **Without one**, it attaches to the whole module, because `StudyRow` has no `gene` column (RM47 made the
  variant optional, not a gene the row could name instead).

**Shape.** A separate table, one concern per table: the human gene with an orthologue id (symbol
matching found 20 of the 22 genes NCBI orthologues found), species, model type, sex, diet, the lifespan
effect, and the direction concordance with the human allele (`concordant`, `discordant`,
`nonmonotone`), with a citation. Annotation only: it never reaches an effect column or a tier
(R-ANIMAL-1). Full, a new table kind.

## RM336 — a DOI written into `pmid` parses as five or six PubMed ids, and the literature pass looks each one up

**Preprints, decided 2026-11-04 by the maintainer after the final run (17 v2 studies are DOI-only).** DOIs stay in `doi` and never in `pmid`. `pmid` accepts a typed sentinel (`NONE` or similar; the exact spelling gets its P5 audit). That sentinel makes `doi` the **mandatory substitute**, and the validator then checks the DOI instead. A DOI written into `pmid` is still refused. `pmid` stays required, because the cell is present, so this is minor-legal (P8). RM263's DOI-to-PMID lookup still fills a real PMID wherever PubMed indexes the paper.

**Decided 2026-11-04 by the maintainer: a refusal, like RM50's PMCID arm.** `validate_pmid_cell` refuses a cell whose only token is a DOI, and names it. Principle 3 says a module that validated keeps validating, so before the build, check the published modules (the registry's catalogue and the reference examples) for a DOI in `pmid`. None found: the refusal breaks no published module. Any found: they go back to the maintainer before the arm ships.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-11-03 as a priority**; a refusal or a warning is the decision · **Owner** format (`spec.validate_pmid_cell`) · **Motivating case** longevitymap v2 requirements §6.3 ("`pmid`, or `doi` for preprints") · *for* longevitymap v2 · *related* RM50, RM263, [ROADMAP § `StudyRow.pmid` required + PMID-shaped](ROADMAP.md#studyrowpmid-required--pmid-shaped)

**Reproduced 2026-11-03.** `StudyRow(rsid="rs429358", pmid="10.1101/2025.03.01.640000")` validates.
`extract_pmids` returns `['10', '1101', '2025', '03', '01', '640000']`, and `doi:10.1038/s41586-019-1234-5`
gives five. `enricher/src/just_dna_enricher/literature.py` iterates `extract_pmids(study.pmid)`, so the
literature pass checks PubMed records 10, 1101 and so on as the row's citations. A preprint-only row is
exactly where an author writes this, because `pmid` is required and the paper has only a DOI.

**Same class as RM50.** RM50 gave `validate_pmid_cell` a PMCID arm, refusing a cell whose only id is a
PubMed Central number and naming it. A DOI is the next registry whose digits read as PMIDs.

**The decision.** A refusal arm like RM50's makes cells that shipped modules may already hold invalid
(P3/P8), while a new warning code is minor-class (RM308's rule). The real fix for preprints stays the 1.0
doi-first demotion. RM263 is the route from a DOI to its PMID.

## RM303 — the snapshot layout is a contract with six parties and no model, so it belongs in `just-dna-format`

**0.8, confirmed 2026-11-03** by the maintainer when scoping 0.8.

**Severity** medium · **Status** open — filed 2026-09-28 at the maintainer's request, **taken into
0.8** · **Owner** format (the model) + enricher (the writers and readers) · **Motivating case** the
builders' `release.json` keys have drifted, and one drift already reached `cache status`

**The problem.** A reference snapshot is `data/*.parquet`, optional sidecars, `LICENSE.txt` and
`release.json`, and `locations.py`'s own header says that at least four parties (builder, publisher,
provisioner, reader) have to agree on those names. The names are constants in the enricher, so any
other repo that wants the layout has to import the network tier to get them. `release.json` has no
model at all. `read_release` returns a `dict`, and the 14 builders write it by hand at 15 sites. The
keys have drifted:

| Key | Writers |
|---|---|
| `built_at` | all 15 sites |
| `builder_version` | 13 |
| `source_url`, `source_sha256`, `dataset` | 11 each |
| `rows` | alphagenome_avi, mane, mitomap |
| `row_count` | clinvar, clinpgx, acmg |
| `license` / `licence` | strchive / civic |
| `builder`, `release`, `parents` | acmg; civic; mitomap_miss |

ClinVar writes no `dataset`, so `cache status` printed a blank release label for it. The repair was a
per-lane exception (`clinvar_dataset_label`, see `caches.py` near `_dataset_label`). That is the drift
surfacing as an incident, and it was repaired at the reader rather than at the contract.

**The split.** The two files mix two kinds of thing, and they are separated by what each is tied to:

- **Contract → `just_dna_format.snapshot`**, pydantic + stdlib only, no environment, no network: the
  layout names (`data/`, `release.json`, `LICENSE.txt`, the sidecar and root-filename tuples), a
  `SnapshotRelease` model, `read_release(dir) -> SnapshotRelease | None`, and a payload predicate
  ("this directory holds a snapshot") that reads no environment.
- **Deployment → stays in the enricher**: `CACHE_BASE_VAR` and the per-lane variables, `.env` loading,
  platformdirs and `APPNAME`, the per-lane resolvers, `CACHE_LANES`, prepare, rebuild and publish. It
  provisions and fetches, and it is tied to specific lanes. The enricher's `locations` names become
  imports from format.

**Charter checks.**

- **Goals: an amendment is owed.** Goal 1 scopes format to "annotation modules", and a snapshot is not
  a module. No principle forbids the move (no network, no new dependency), but it widens what the
  package is for, so it lands as a deliberate one-bullet Goals amendment, with the reasoning in
  CONSTITUTION_AMENDMENTS_HISTORY.md.
- **P3 from then on.** Once the model is published, `release.json` keys are additive-only within the
  major. That makes the drift above a decision to take **before** the first publish: which spelling
  of each drifted pair becomes the field, and whether the other is read as an alias.
- **P9.** A derived file that no human authors: half price at most, and no authored schema moves.
- **The tri-state rule.** `read_release` keeps `None` for both absent and unreadable, as it does
  today. A key the model makes optional stays `None` when it is unstated, never a default, because
  the ClinVar label bug above is exactly a missing key being read as a blank answer.

**Open questions.**

1. **Core plus extension.** `parents` (the derived lane) and lane-specific keys either get typed
   optional fields or ride in `extra="allow"`. Typed fields are safer; extra keys keep the model small.
   Decide by listing what each reader actually reads.
2. **The drifted pairs.** `rows`/`row_count` and `license`/`licence` pick one spelling each; the old
   spelling is read on input and never written again. `builder` against `builder_version` needs a look
   at what acmg means by it.
3. **A guard.** Every builder writes through the model rather than through `json.dumps`. An AST walk
   over `*_build.py` refusing a hand-built `release.json` dict is the usual shape
   (`@registry-completeness`).
4. **Published snapshots.** Snapshots already on HuggingFace keep their old keys. The model reads
   them, and a republish writes the canonical spelling, never an in-place edit.

**Considered and refused on the same day.**

- **Renaming `just-dna-format`** (e.g. to `just-dna-schema`, the workspace directory's name). With the
  snapshot contract added, "format" becomes *more* accurate: the package defines two on-disk formats.
  A rename would touch about 130 importing files across five repos and keep two distribution names
  alive for a major. Refused by the maintainer.
- **A `just-dna-datasets` / `just-dna-builders` package.** First offered on 2026-09-25 (the RM261
  round) as the recommended way to take the builders out of the wheel, and declined then without being
  recorded. Weighed again now, it forms a cycle: builders need the layout from the enricher, and
  `cache rebuild` needs the builders. Breaking the cycle means moving the layout below both, which is
  this item, and after that the separate package buys nothing. Its dependencies are the enricher's
  own, and the columns it writes are read by enricher passes, so every snapshot change would become
  a release of two packages. It would also need a Goal 2 / Principle 2 amendment, since builders fetch
  and the enricher is named as the only tier that may. Builders and readers stay beside the pass that
  reads their columns. just-prs's parquet lanes stay in just-prs (`PRS_CACHE_DIR`), and the v1 port is
  a consumer (pipelines → enricher), not a dataset.
- **A nano-library holding only the convention.** Too small to be its own package. Format already
  depends on pydantic and already owns the module's provenance record (`manifest.json`), and
  `release.json` is that record's snapshot twin.

## RM253 — a repeat-count star allele (UGT1A1 `*28` = TA(8)) has no home a diplotype can name, and the CPIC drafter translates none of CPIC's notation

**Seam 1 decided 2026-11-04 by the pm seat, on the evidence, as the maintainer asked: spelled, VCF-anchored
and left-normalized.**

A subagent read the site in about 120 PGP-HMS VCFs plus local runs. The evidence, all measured:

- DeepVariant, DRAGEN, GATK, Clair3, Isaac, Helix, the imputation servers and CGI vcfBeta all write `*28`
  as the ordinary indel `C>CAT` at the anchor (GRCh38 `2:233760233`, GRCh37 `2:234668879`), left-normalized.
- No file holds a symbolic allele at the site, and no caller gives a repeat count in place of sequence.
- freeBayes and `bcftools mpileup` write the whole 16-base run unnormalized. They match only once the
  consumer normalizes, which the consumer guide already says no format guarantees.

So `*1` is the reference, `*28` is `C>CAT`, `*36` is `CAT>C` and `*37` is `C>CATAT`. Seam 2 follows the
same rule: CPIC's `DEL<bases>`/`INS<bases>` are spelled the same way, and the bare `DEL` with no length
stays skipped.

**One trap to carry into the build.** `rs3064744` appears in no VCF's ID column. Arrays (23andMe,
AncestryDNA) and dbSNP-annotated VCFs carry `rs34983651` for the `+TA` allele, and one imputation server
stamps `rs606231201`, which dbSNP places as a different allele. So an rsID-keyed row must not rely on
`rs3064744`.

**Decided 2026-11-04, in part.** DPYD (seam 3): the drafter writes CPIC's full name with the spaces dropped, as the maintainer chose. The comma between variants is replaced, because a comma inside a name would split any multi-valued cell (MULTI_SEP is `,;|`). The maintainer suggested `:`, tentatively ("maybe?"). **The pm seat picked `&` instead**, and the maintainer may still veto it before the drafter ships. `&` was picked because every other candidate already means something in an allele name. `:` is HGVS's reference separator. `+` is an intronic offset (`c.1905+1G>A`, DPYD `*2A`). `_` is an HGVS range. `/` separates the two halves of a diplotype. So HapB3 is `c.1129-5923C>G&c.1236G>A(HapB3)`. Seam 1, how a repeat count is spelled: open, decided after checking precedent in real VCFs (PGP-HMS, and just-vcf's seats).

**0.8, confirmed 2026-11-03** by the maintainer when scoping 0.8.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-21** · **Owner** format (schema) +
enricher (`pgx_draft`) · **Motivating case**
[S106](CONSUMER_SUGGESTIONS_HISTORY.md#s106--a-repeat-count-star-allele-ugt1a1-28--ta8-has-no-home-repeat_allelescsv-bins-a-count-and-haplotypescsv-names-an-allele-and-nothing-joins-the-two)
— the most common UGT1A1 allele, the one atazanavir and the irinotecan labels key on, ships undefined

**Reproduced on the snapshot, and the reporter's reading holds with one correction.** CPIC defines
`UGT1A1*1` as `TA(7)`, `*28` as `TA(8)`, `*36` as `TA(6)` and `*37` as `TA(9)`, all at **rs3064744**
(the report said rs8175347, the promoter's other name in the literature), plus `*80+*28` and `*80+*37`
as two-variant haplotypes. `draft_gene` skips all six repeat rows, so `haplotypes.csv` defines `*28` by
nothing while `allele_function.csv` and `diplotypes.csv` name it, and `validate` warns *"Star allele(s)
used but not defined"* — correctly, and unfixably by the author. Across the whole snapshot the notation
the drafter skips is 25 distinct spellings: `DEL<bases>` (the bulk, e.g. `DELTCT`), a bare `DEL` (4
rows, lengthless), `INSCGGG`, and `UNIT(n)` repeats (`TA(8)`, `AAAGGGGCG(2)`, `GGA(1)`, `TCAG(2)`).
NUDT15 `*2` has **no** defining row in the snapshot at all, so that half of the report is scoped to the
live API, which was not probed.

**Three seams, and they are not one item's worth of the same thing.**

1. **A repeat count as a defining allele.** The format holds `<CNV:TR:n>` since RM5 — but `n` is a
   *length in bases*, so `TA(8)` would be `<CNV:TR:16>`: legal, distinguishable from `*36`/`*37`/`*1`
   by length, and lossy about the unit. Whether that is the right spelling, or whether the sequence
   should be spelled out (sixteen bases, the standard's own preference when the sequence is known —
   but VCF-anchored, which needs the preceding base the drafter does not have and the Ensembl row
   RM251 now records does), or whether `repeat_alleles.csv` should gain a join to a haplotype name, is
   the design question. The reporter's framing is exact: today it is a bin **or** a name, never both,
   and the diplotype table needs the name. `@hosting-tri-state` says a symbolic allele compares as
   *undecided* against a spelled call, so the first option moves the join to the consumer's caller
   (`requires_callable`) — which may be the honest answer for a VNTR, and is still a decision.
2. **`DEL<bases>` / `INS<bases>` → `<DEL:n>` / `<INS:n>`.** A drafter translation, not a schema gap:
   the length is the notation's own, and the symbolic spelling is exactly what RM5 built for a variant
   "whose sequence is deliberately unspelled". The bare `DEL` stays skipped (no length). The open
   question is whether a spelled deletion should be spelled — CPIC gives the deleted bases and the
   position, and the anchor base is one reference read away.
3. **HGVS-named alleles (DPYD).** `HAPLOTYPE_NAME_PATTERN` refuses whitespace, and CPIC's names are
   `c.1003G>T (*11)` and `c.1129-5923C>G, c.1236G>A (HapB3)`. The report's claim that
   `haplotype_name` accepts them is **wrong as spelled** — probed, all three PGx models refuse on the
   space — so this is a naming *policy* for the drafter (the legacy star in the parenthesis? the HGVS
   string with the space removed? both, one as `suballele`?) before it is anything else. 167 defining
   rows and 3,570 diplotypes wait on it.

**What shipped with the filing (message only, in the uncut 0.7 line):** the RM5 notation warning now
names the three symbolic spellings the format holds and says the *drafter* does not translate into
them, pointing here; and the unparsable-diplotype sentence is bucketed by reason, so DPYD's HGVS names
are no longer reported as CYP2D6's copy-number notation.

**Parking-condition gate audit:** none of the three needs a consumer to act first — the corpus is the
snapshot, already provisioned, and the probe module is a `draft_gene("UGT1A1")` away. This is a design
decision, not a wait.

## RM236 — `consequence` and `impact` are planned axes with no slot, and an ACMG engine reads both as primary inputs

**0.8, decided 2026-11-03.** Kept in 0.8 as an input to longevitymap v2's causal and effector-gene confidence labels (RM333), while the rest of RM188's parity work moved to 0.9.

**Severity** medium · **Status** open — **filed 2026-09-13 from [RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s ClawBio half** ·
**Owner** format (schema + compiler), then enricher · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *the two columns their engine reads that we
cannot store*

**For longevitymap v2 (2026-11-03):** causal confidence C1 and effector confidence E1 both key on a variant being coding. See [the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

[ROADMAP § Reserved namespace](ROADMAP.md#reserved-namespace) lists `consequence` (the VEP/Sequence
Ontology term) and `impact` (`HIGH|MODERATE|LOW|MODIFIER`) as *planned future annotation axes*, with
the rule that they "get a slot and a specific diagnosis only when a release actually commits to
building them". Nobody had committed, because nobody had a case. **The case is now in hand**:
ClawBio's `skills/clinical-variant-reporter/acmg_engine.py` is a running 653-line ACMG/AMP engine
whose per-criterion evidence table prints `consequence=frameshift_variant` for PVS1, `impact=HIGH`
for PM1, and `consequence=frameshift_variant, SpliceAI=N/A` for BP7 — three of its twelve implemented
criteria read a column this format cannot store, and a fourth reads the transcript the term was
called against.

**Get the mechanism right before touching anything.** Neither name is in `RESERVED_NAMES_0_4`, so
`reject_reserved` never claimed them and there is nothing to move out of a "built half": an author
writing `consequence` today gets the generic `extra="forbid"` message. Committing means one of two
things, and choosing is the first deliverable — **build the column**, or **add the reserved slot plus
a `vocab.RESERVED_NAME_REASONS` entry** so an author hears what the name is held for instead of the
stray-column message. The second is the honest outcome if the grain question below defers the build.

**The blocker is grain, and it is [RM23](ROADMAP_0_9.md#rm23--computational-predictor-scores-as-a-table)'s blocker
restated.** A variant has one consequence *per transcript*; `VariantRow` is one row per
`(variant_key, genotype)`. Three options:

1. **MANE Select only** — one value per variant, with `GeneMetricsRow.mane_select` naming the
   transcript it was called against. Cheap, lossy, and defensible only if the column's description
   says so in the field itself (`@field-description-is-a-claim`).
2. **Most severe across transcripts** — a ranking policy. That is an interpretation, so it is out by
   the same clause that keeps threshold-picking out of RM23.
3. **A derived `consequences.csv` sidecar** keyed `(variant_key, transcript)` — half cost under
   Principle 9, no authoring burden, and it is *the same shape RM23 needs*.

**Recommend (3), and settle RM23's grain in the same pass.** They are one question asked twice, and
answering it once is the whole saving; splitting them is how two sidecars end up with two different
answers to "which transcript". Do not build (1) as a stepping stone — a column shipped under a major
cannot be retyped into a table.

**Related** RM23 (same grain blocker, and the pass that should settle both), RM188.

## RM238 — a per-tissue eQTL has no row, and `expression_effects.csv` is the wrong table to widen

**0.8, decided 2026-11-03.** Kept in 0.8 as an input to longevitymap v2's causal and effector-gene confidence labels (RM333), while the rest of RM188's parity work moved to 0.9.

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half; PARKED on a consumer, deliberately** · **Owner** enricher · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *nine databases, and the two axes that come
back with no home*

**For longevitymap v2 (2026-11-03):** the cis-QTL colocalisation behind effector confidence E1/E2. See [the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

`clawbio.py run gwas --demo` on rs3798220 returns five cis-eQTLs **by named tissue** from GTEx and the
EBI eQTL Catalogue — `LPA` in Liver at β −0.82, in Adipose at −0.45, `SLC22A3` in Liver at +0.31.
Nothing here holds that. `expression_effects.csv` exists and is the wrong place: it is
AlphaGenome-shaped, one row per `(variant, gene)` **aggregating 371 tissue tracks** into
`tracks_agreeing`/`tracks_total`, and [`expression.py`](../schema/src/just_dna_format/expression.py)
argues at length that one row per track "is lossless and unreadable". A GTEx row is not a track — it
is a measured cis-eQTL in one named tissue with its own β and p, ~50 tissues rather than 371, and
**the tissue is the fact** rather than something to consensus over. Different grain, different source,
different terms. So: `eqtl_effects.csv`, one row per `(variant, gene, tissue, dataset)`, tissue as an
ontology term where the source gives one.

**This is filed open and parked, and the parking reason is a rule rather than a shortage of time.**
[USE_CASES § 7.2](USE_CASES.md#7-regulatory-effect--which-gene-a-non-coding-variant-moves-and-which-way-07)
closes with *"reopen this with a consumer, never with an argument"*, and a competitor rendering the
table is an argument. **Reopen it with somebody who needs the answer.** When that happens, the first
step is the acquisition measurement that correctly parked the frequency snapshot — what the GTEx and
eQTL Catalogue bulk artifacts weigh, and what their terms say (`@probe-the-real-file`).

**Related** RM188, RM194/RM200 (the AlphaGenome table this must not be folded into), USE_CASES § 7.2.

## RM239 — a fine-mapping posterior has no column, and `gwas_effects.csv` already has its key

**0.8, decided 2026-11-03.** Kept in 0.8 as an input to longevitymap v2's causal and effector-gene confidence labels (RM333), while the rest of RM188's parity work moved to 0.9.

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s ClawBio half** ·
**Owner** enricher · **Motivating case** [`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) §
*nine databases, and the two axes that come back with no home*

**For longevitymap v2 (2026-11-03):** the fine-mapping posterior is the input to causal confidence C1–C4. See [the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

The same `gwas-lookup` report returns three fine-mapping credible sets for rs3798220 with a posterior
probability and 95%/99% set membership per `(trait, study)` — PP 0.92 for Lipoprotein(a) in
GCST005140, 0.45 for aortic valve stenosis in GCST90038614 with 95% `No` and 99% `Yes`.

A posterior inclusion probability is the **same class of object as an allele frequency or a LOEUF**: a
number a named dataset publishes, no measurement by us, no inference by us. Its key is
`(variant, trait, study)`, which is `GwasEffectRow`'s key plus nothing — the row already carries
`trait_efo_id`, `study_accession` and `p_value_num`. So the cheap shape is **two optional columns on
the existing table**, `posterior_probability` and `credible_set`, minor-legal under P3/P8, and the
GWAS Catalog now publishes credible sets for its harmonised studies.

**Smallest item on the survey's list, and it should not be done on its own.** Do it the next time
`enricher/gwas.py` is open for another reason. Two things a design owes: whether `credible_set` is a
membership flag or the set's size/level (`95`/`99` are two answers to one question, and putting both
in one column is the `@field-description-is-a-claim` failure), and a withhold for a study whose
harmonised release carries no credible set, which is a nobody-asked third state and not a zero.

**Related** RM188, RM90 (the table this lands on).

## RM241 — `weighting` does not survive `reverse`, so a reversed module has no scale to read

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half** · **Owner** format · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *The translation, run*, last paragraph

**For longevitymap v2 (2026-11-03):** v2 declares `weighting:` precisely to say it has no weights, and `reverse` drops the block. See [the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

`weight` is the one magnitude in this format with no unit beside it (`@weight-has-no-unit`), and RM92
built `module_spec.weighting` — `scale`, `method`, `note` — to be the place a module says what its
weights mean. It is **advisory, copied into the manifest, and not reconstructed by `reverse_module`**,
in the same class as `panel` / `authorship` / `license`. All of that is documented and, taken one field
at a time, defensible: it is not content, so it is correctly outside `content_signature`.

**The survey hit the consequence.** Translating ClawBio's nutrition panel forced an honest `weighting`
block to be written — their weights are hand-assigned importances *within* a nutrient domain, and
their scorer normalises by the weight of the SNPs it happened to find, so a domain score is comparable
only inside one domain of one run. That block is the single most useful sentence in the translated
module. `reverse` then drops it. So a consumer holding two **reversed** modules has two `weight`
columns and no way to learn that they are on different scales — which is the exact failure RM92 was
built to prevent, surviving in the one path RM92 does not cover.

**Three candidate dispositions, and this entry does not pick one.** (a) Nothing — write it in the
[FAQ](FAQ.md) as a known lossy field and let a consumer read the *original* spec, which is what
`reverse`'s own contract already says. (b) Carry `weighting` through `reverse` from the manifest,
which is where it already lives — cheap, and it changes what `reverse` claims to be. (c) Decide the
lossy set is right and that the real defect is that nothing *warns*, the way the dropped verification
attestation warns. **(c) is the most likely right answer** and is the cheapest to test: `reverse`
already emits one warning for a dropped attestation, so a second for a dropped `weighting` costs one
line and tells the author the thing they need to know at the moment it stops being true.

**Do not fix this by putting `weighting` inside `content_signature`.** It is prose about a column, not
the column; hashing it would make a reworded note move the digest, which is the defect
[FAQ](FAQ.md) already answers twice.

## RM28 — Meta-conclusions (the predicate half)

**A fifth member form, decided 2026-11-04 by the maintainer: the tag selector.** A member may be
`flags:<tag>`, which means every single-statement row carrying that tag. v2's 528 legacy variants all carry
`legacy_longevitymap` (R-LEGACY-1), so one row (`flags:legacy_longevitymap`, tier D) replaces 528 one-line rows.

The decided rules still apply:

- A one-member row naming a specific variant is more specific, and wins. That covers the legacy loci tiered
  C, or A/B on modern evidence, such as APOE.
- A row in two tag sets that disagree on a column has that column withheld.
- An untagged locus is untouched.

**Rejected:** a module-wide default tier. It would silently turn v2's 31 untiered and 4 tier-X seed loci into D,
a stated value standing in for an unstated one. Raised by a side agent from the final run's audit
(`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §2, R-LEGACY-1).

**Two columns added 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §4, gaps 3 and 4):

- **A citation (`pmid`) on meta-table rows.** A row cites when its claim is finer-grained than `studies.csv`'s key, the RM47 pattern. The study-orphan check accepts meta-table members, so APOE's 14 study links, the 8 HLA alleles and KL-VS × ε4 can cite.
- **A role on per-trait rows** (`outcome` / `mediator`). 32 v2 loci act through a trait, such as LDL cholesterol, that is the path and not the outcome.

**Where a difference ends and a disagreement begins: the key, weighed 2026-11-04 by the pm seat at the
maintainer's direction ("it's the good old 'what's a key' in a new skin").** A meta-table row's key is **its
member set, plus `trait_efo_id` on a per-trait row**. The rule follows from it:

- **The same key twice is a disagreement.** Two rows with one member set (and one trait) are a duplicate key,
  and they are refused as on every other keyed authored table. This is the only place two values can
  contradict each other, so no separate agreement warning is needed.
- **Different keys that nest are a difference.** A locus-level row (`variant_key` alone), a genotype-level row
  (`variant_key` + genotype) and a combination that contains them are three statements. The most specific
  matching row wins, column by column; that is the "combination replaces" decision, extended down to a
  single locus.
- **Unstated is not different** (`@absent-is-not-different`). A specific row that leaves a fact empty does not
  contradict the general row's value, and the general value fills it.
- **The residual is identity, not facts.** One variant reachable under two keys would hide a real
  disagreement as a difference. The archive found exactly one such case: IL6R's rs8192284, merged into
  rs2228145, seeded with two tiers. The existing rsID-merge check catches it during enrichment, because NCBI
  is the merge oracle. It must keep running over meta-table members.

The objection that "tier copies on genotype rows are never compared" no longer applies: under C a fact is
written once, never copied onto genotype rows.

**Final shape, 2026-11-04 ("go with C").** One new table. A row is a composite statement, meaning one or more
members, each an item of a single-statement table, mapped to a finding and/or the per-locus facts. A one-member
row with only facts is how a single locus gets its tier, so RM323 needs no table of its own.

**The rule the maintainer set with it, for every proposal here:** "Always weight your proposals towards
reduction of entities. If something can be built with 20 score, don't build it with 30 for 'tidiness', it is
clutter and bloat in guise of strict-typing of non-strict typed data." Under it, RM327's per-trait benefit/harm
judgements default to rows of this same table (one member, a trait, a direction) rather than a table of their
own; the proposal confirms that or says why not.

**Shape decided 2026-11-04 by the maintainer: the meta-table is a map from a composite statement to a finding.**
A composite statement is keyed on **items of the single-statement tables**: a `variants.csv` row's
`(variant_key, genotype)`, a `diplotypes.csv` row's key, and so on. There is no new subject or state grammar.
"KL-VS heterozygous AND APOE ε4 carrier" therefore names the KL-VS genotype row and the ε4-carrying
diplotype rows, one composite per diplotype, since rows are already a disjunction.

The consequence, raised and accepted: a member must exist as a row of its own table, and that row carries
its own required `conclusion`. The meta-table's rows carry the same per-locus fact columns as the
single-statement tables (RM323).

**Decided 2026-11-04 by the maintainer: a matching combination replaces the single-locus findings it names.** A genome that is KL-VS heterozygous and an APOE ε4 carrier gets the buffered finding instead of the plain ε4 risk. The accepted cost is that a reader that predates the combination table shows the unbuffered risk alone.

**0.8, decided 2026-11-04 by the maintainer: the combination half is built in 0.8.** A combination is defined here as a set of subjects (a variant, a gene or a named allele) each in a stated genotype state, for example KL-VS heterozygous together with APOE ε4. Each defined combination becomes one more kind of subject on RM323's per-locus fact table, so its tier, confidence and age of action live in the same place as a single locus's. Facts never get a second table. Boolean `OR` and open-world negation stay out, as the corpus below argues: rows are already a disjunction.


**Severity** medium (after the corpus) · **Status** parked on a corpus — **and halved on 2026-08-13**:
the injected-cofactor half closed, the predicate half stays here · **Owner** format (schema + compiler)
· **Motivating case** combination annotations; disclosure policy

**For longevitymap v2 (2026-11-03):** KL-VS buffering in APOE4 carriers joins two loci on two chromosomes, so no haplotype holds it; added as a corpus entry there. See [the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**Read this entry knowing how much of the original item has already dissolved.** Probing in 0.5 removed
most of it, and the 0.6 review removed the rest of the cofactor axis. What is left is genuinely small
and genuinely unsolved.

**The corpus this was parked waiting for has its first real entry (2026-09-02, [RM174](history/ROADMAP_HISTORY_0_6.md#rm174--a-claim-about-two-variants-in-trans-is-written-as-two-single-variant-rows-because-no-brick-holds-the-real-subject)).**
Not an argument — an adopted source whose grammar was counted. CIViC publishes molecular profiles as
boolean expressions over variants: of 1,964 profiles, **209 are multi-variant** — `AND` 141, `OR` 72,
`NOT` 1 — and they nest (`BRAF Amplification AND ( BRAF V600E OR BRAF V600K )`). Both halves of this
entry's surviving case appear there, with instances:

* **Economy, and it is this entry's own phrase.** Evidence item 8721 is a claim about
  `VHL S183L AND VHL D126N` whose description reads *"heterozygous compound mutation"* — two variants
  **in trans**, observed, cited. `HaplotypeRow` cannot hold it: a haplotype is same-strand co-location,
  so drafting it there asserts *cis* where the source says *trans*, silently, because no column carries
  phase for anything to contradict.
* **Open-world negation.** `MET Amplification AND NOT KRAS Mutation` quantifies over a set no module
  can close, on a class term rather than an enumerable allele.

The 72 disjunctions are the half that is **already expressible** — rows are a disjunction — which is
where this entry drew the line and it holds. **This is evidence for the corpus, not a reason to
unpark**: one source, one observed trans instance, one negation. RM174 carries the measurement; the
decision stays here.

**Second corpus entry, 2026-09-13 — and it is a routine clinical guideline rather than an oncology
molecular profile.** From [RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half ([`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *pharmgx-reporter*). Their
pharmacogenomic report renders exactly one AVOID across 59 drugs, and it is **warfarin**, keyed
`"genes": ["CYP2C9", "VKORC1"]`. Our own `reference_examples/cyp2c9_warfarin_grch37/` carries the
CYP2C9 diplotype phenotypes in `diplotypes.csv` and the VKORC1 per-genotype claims in
`pharm_variants.csv`, **side by side, with nothing keying the pair** — which is this entry's surviving
"pairing across *subjects*" clause with a shipped module standing on it.

Three things make it sharper than the CIViC entry rather than a repeat of it:

* **It is the *drafter's* recorded gap, not an inference.** `pgx_draft`'s own comment says it:
  *"the guideline exists, it is a dosing algorithm over several genes rather than a per-phenotype
  recommendation, so nothing lands here and the author was told CPIC has nothing."* What shipped for it
  was a better **warning**, deliberately, not a table.
* **The competitor has no declarative form either.** ClawBio's answer is `"special": "warfarin"` — a
  hardcoded branch calling `get_warfarin_rec(profiles)`, for one drug out of 59. That is evidence the
  shape is genuinely hard, not evidence that everyone else solved it.
* **It is CPIC, so the population is countable.** The measurement this entry still wants, and the one
  cheap enough to do before any design: **how many CPIC guidelines are keyed on a gene *pair* rather
  than a single gene phenotype**, counted off the CPIC snapshot already provisioned. If the answer is
  three, this parks again with a sharper reason; if it is thirty, the economy argument changes.

**Third corpus entry, 2026-09-13 — and this one is a general-purpose grammar rather than a domain's
by-product.** From the same item's [round-2 roster](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics):
SNPedia publishes **genosets**, boolean expressions over genotypes, and
[`zhaofengli/snappy`](https://github.com/zhaofengli/snappy) (`2d5255f`) has them extracted from a
MediaWiki dump into `data/genosets.json` beside 106,603 SNP entries. The grammar is
`and(rs4988235(C;C), rs182549(C;C))`, it nests, and a genoset may reference another genoset — the
haplogroup trees are built that way.

What makes it the sharpest of the three is that CIViC's profiles and ClawBio's warfarin branch each
fell out of one domain solving one problem, where **this grammar was written for consumer genetics in
general** and has been in use for over a decade. It is also the first entry where the *condition* side
and the *conclusion* side are both published, at scale, by one source.

**This entry and [RM16](ROADMAP_0_9.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest) are one axis at two
operators** — boolean here, weighted-sum there, with the enumerative combiner already shipped in
`diplotypes.csv` and covering the small-arity cases both would serve. RM16 carries the table setting
that out; read it before opening this one, and take the *where does the combining rule live* decision
once rather than twice. They stay separate items, because a categorical conclusion and a number
needing a reference distribution are different outputs.

**One argument from it does reach beyond the count, and it is [RM16](ROADMAP_0_9.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest)'s
rather than this entry's** (maintainer, 2026-09-13): genosets are a *familiar shape*, in use for over a
decade, and an author's ability to bring one across is an adoption signal in its own right. It bears
on this entry only as a reason the count below is worth running rather than as a reason to unpark —
this item is parked on a corpus, and a corpus is measured, not argued.

**It changes no decision yet, and the reason is the same one that has held twice.** The measurement
this entry wants from it is cheap and has not been done: **how many genosets are there, what is the
operator distribution, and how deep does the nesting go** — counted off `genosets.json`, which is a
committed file needing no network. A corpus of forty flat conjunctions argues differently from four
thousand nested ones. The licence is **not** the obstacle a first reading here made it: CC BY-NC-SA
3.0 US is established and adoptable as an unsellable share-alike module
([USE_CASES § 2e](USE_CASES.md#2e-republishing-a-licence-encumbered-third-party-corpus-as-modules-2026-09-13)).
What still has to be beaten is `reference_examples/apoe_epsilon`, which answers the two-variant case
with no predicate at all.


**Fourth corpus entry, 2026-09-13 — and it is the first where enumeration *succeeds* and the schema
around it complains anyway.** Raised by the maintainer from their own genotype: **Kulminski's
subdivision of APOE ε4 by linked TOMM40/APOC1 markers**, where a carrier is not simply *ε4* but
`1-0-0`, `1-1-0`, `1-0-1`, `1-1-1` — a binary vector over the ε4 call plus the linked sites, each
pattern carrying a different reported risk.

**This one is expressible today, and that is the finding rather than a reason to close.** Three
markers is eight patterns and at most thirty-six pairs, which is `haplotypes.csv` (one row per pattern
× defining marker) plus `diplotypes.csv` (pair → phenotype) — the shape
`reference_examples/apoe_epsilon` already ships for ε2/ε3/ε4 across rs429358 and rs7412, with one more
marker. The enumerative combiner is not beaten here, so **this entry argues for no predicate at all**.

**What it does show is the shape being outgrown at a different seam — the *subject*, not the
combiner** (the maintainer's reading, and it is the right one). Expressing it fires two shipped
warnings, and neither is a bug:

- **`composite_gene_cell`.** The haplotype spans TOMM40, APOE and APOC1; `DiplotypeRow.gene` is
  **required and single-valued** (`HaplotypeRow.gene` is optional, so only the diplotype half forces
  the choice). Labelling the locus `TOMM40-APOE-APOC1` publishes a gene name no registry index will
  match, beside its parts — which is exactly what the warning says. So the author picks between **one
  findable symbol and an honest locus label**, and there is no third option. `apoe_epsilon` never met
  this because ε alleles sit in one gene.
- **`diplotype_phase_ambiguous`**, conditionally. `HaplotypeRow` *is* same-strand co-location, so this
  translation is only honest if Kulminski's patterns are **phased haplotypes**. If they are unphased
  multi-locus genotype vectors, writing them as haplotypes asserts *cis* the source never claimed —
  RM174's trap exactly — and the pairs that collapse to one unphased genotype with different
  conclusions are what this warning already catches, telling a consumer with unphased calls to
  withhold.

**So the honest verdict is: yes, with caveats, and the caveats are the entry.** The format holds the
claim; what it cannot do is hold it *cleanly*. A use case that compiles only by choosing between
findability and honesty, and only under a phase assumption, has grown past the gene-keyed subject the
PGx tables were cut for — and that pressure lands on `DiplotypeRow`'s key rather than on any predicate
language. **Read against the other three entries, this is the one that argues RM28 may be the wrong
item for its own class of case**: CIViC's contribution was that enumeration *cannot* reach trans and
open-world negation, ClawBio's was that nobody has a declarative form for a multi-gene dosing
algorithm, SNPedia's was a general grammar at scale — and this one enumerates fine and still does not
fit. A locus-keyed subject would settle it and a predicate would not.

**The count this entry asked for, 2026-09-20 — and it is between the two numbers the question
named.** Measured off the provisioned CPIC snapshot (`cpic_snapshot_b0ffd4c6f010`, built 2026-09-02)
while answering S102, whose reporter had counted the same table from the other side: of **103 drugs**
with a recommendation row, **18 are keyed only on a gene pair** and none is keyed both ways — every
drug is single-gene or pair-keyed, never a mix — and `gene_count` never exceeds 2. By rows it is
**2,656 of 3,411** pair-keyed, which is what made the drafter's *"the snapshot has no row for it"*
false for a drug with 35 of them. The 18 drugs fall into **six pairs**:

| pair | drugs |
|---|---|
| CACNA1S + RYR1 | desflurane, enflurane, halothane, isoflurane, methoxyflurane, sevoflurane, succinylcholine |
| CYP2C19 + CYP2D6 | amitriptyline, clomipramine, doxepin, imipramine, trimipramine |
| NUDT15 + TPMT | azathioprine, mercaptopurine, thioguanine |
| ABCG2 + SLCO1B1 | rosuvastatin |
| CYP2B6 + CYP2C19 | sertraline |
| CYP2C9 + SLCO1B1 | fluvastatin |

Warfarin is **not** among them: it has no recommendation row at any arity, because its guideline is a
dosing algorithm rather than a recommendation table, so the ClawBio entry's case is the one CPIC drug
this count cannot reach. Read against the question — *three parks again, thirty changes the economy
argument* — eighteen drugs across six pairs is the middle: more than a warfarin-shaped exception,
less than a pattern the enumerative combiner is failing at scale, and every one of them is arity 2.
The drafter now names the partner gene instead of claiming absence (RM249), which is a message and
not a table; whether six pairs earn a pair-keyed subject stays the maintainer's decision, and this
entry stays parked on it. The reporter's reading — ClawBio keys each of these on a single gene and
never mentions the partner, *a lossy answer, not a model to copy* — is the right one and is recorded
beside the survey's plan item 1, which this measurement answers.

**Unmeasured, and flagged as such.** This is a *reported* case: the paper has not been read here, so
the marker count, the exact patterns, and above all **whether Kulminski phases them** are unverified.
That last one decides which of the two warnings above applies, and it is the first thing to establish
if anyone builds it. Separately, `just-module-creator`'s `assets/longevity_2026` was checked and does
**not** attempt this — it takes the opposite reading, collapsing the cluster to rs429358 as the shared
causal signal on colocalization evidence, with TOMM40/APOC1 named only in prose and no
`haplotypes.csv` at all.

Still **parked**, on the same rule: the corpus grows, the decision does not move until the count is in.

**2026-09-20 — the count is in, and it does not support the parking reason.** Measured directly off
the provisioned CPIC snapshot (`data/interim/cpic/`, `dataset: cpic_snapshot_3d2123598711`, built
2026-08-07, `recommendations.parquet` 3,411 rows), prompted by a peer session drafting ClawBio's PGx
corpus that hit it from the other side:

* **2,656 of 3,411 recommendation rows (78%) are `gene_count = 2`.** Multi-gene is not the exception
  in CPIC's recommendation table; single-gene is.
* **36 of 121 `(gene, drug)` pairs have no single-gene row at all.** For those the drafter writes
  nothing, because `CpicSnapshot.recommendations` filters `gene_count = 1` (deliberately — a row about
  CYP2C19 *and* CYP2D6 is not a statement about CYP2C19 alone) and the live client applies the same
  `len(phenotypes) != 1` filter.
* They are **recognisable clinical pairs, not edge cases**: TPMT+NUDT15 over the three thiopurines
  (azathioprine, mercaptopurine, thioguanine — 35 rows each); CYP2D6+CYP2C19 over five tricyclics
  (amitriptyline, clomipramine, doxepin, imipramine, trimipramine — 206 rows each); SLCO1B1 with
  CYP2C9 and ABCG2 over fluvastatin and rosuvastatin; CYP2B6+CYP2C19 over sertraline.
* **RYR1+CACNA1S is the one that breaks the fallback argument.** Seven drugs — the six volatile
  anaesthetics plus succinylcholine — and **neither gene appears in a single-gene recommendation
  anywhere in the table**. Elsewhere a module can at least carry the single-gene rule and lose the
  refinement; for malignant-hyperthermia susceptibility there is no single-gene rule to fall back on,
  so a module carries *nothing* for those seven drugs.

**Independently reproduced on a second snapshot, and the two units reconcile exactly.** The peer
session measured `cpic_snapshot_b0ffd4c6f010` and counted **drugs** where the above counts
**`(gene, drug)` pairs**: 103 drugs carry a recommendation, 85 single-gene, **18 pair-keyed across
six pairs** — NUDT15+TPMT (3 drugs), CYP2C19+CYP2D6 (5), CACNA1S+RYR1 (7), ABCG2+SLCO1B1
(rosuvastatin), CYP2B6+CYP2C19 (sertraline), CYP2C9+SLCO1B1 (fluvastatin). Those 18 drugs times two
genes each is **36 `(gene, drug)` pairs**, which is the number measured here from a different
snapshot built six weeks apart. Two denominators, stated apart deliberately
(`@two-surfaces-two-denominators`): *18 of 103 drugs* and *36 of 121 pairs* are the same fact at two
grains, and the drug grain is the more legible one to quote. **Warfarin is in neither**: CPIC's
warfarin guideline is a dosing algorithm and carries no recommendation row at all, so the shape this
entry was reopened on is not even the marginal case — it is off the end of the table.

**What this changes and what it does not.** It does not by itself unpark the entry: the economy and
open-world-negation objections in *What remains* are untouched, and a table keyed on two subjects is
still a design nobody has drawn. What it removes is the *premise* the parking rested on — that
pairing across subjects is a rare shape worth deferring until a corpus appears. Three sources now
carry it (CIViC 209 profiles, CPIC 36 pairs / 78% of rows, ClawBio's one hardcoded branch), and in
CPIC's case the pairs are the routine half of a guideline set this project already ingests and
drafts from.

**The smaller finding beside it is filed separately as S102** (peer report, 2026-09-20): the drafter
does not just skip these, it **misreports** them — the snapshot path's `knows_drug` returns `None`
unconditionally, so the `known is None` arm always fires and tells the author the snapshot *has no
row*, when it has 35 or 206 of them and filtered every one. That is `@answered-is-not-absent`
(answered-and-rejected is a fourth state; the row stays and the *reason* moves), and the arm's
remedy — consult the live API — reaches the identical filter. The fourth arm, the one whose text
names warfarin, is unreachable whenever a snapshot is present.

**A blood-group instance, S119 (2026-09-27): Lewis is keyed on two genes' *phenotypes*.** The
Lewis phenotype (Le(a−b+), Le(a+b−), Le(a−b−)) is a function of the FUT3 phenotype and the FUT2
secretor phenotype, not of either gene's diplotype. `just-dna-lite` shipped FUT2 secretor status as
its own module and left Lewis out for exactly this reason. It is the same subject-pairing shape as
CPIC's six gene pairs, outside pharmacogenomics, and like them it enumerates (a small table over two
per-gene phenotype vocabularies), so it argues for a two-subject key and not for a predicate.
Unbuilt, so it is corpus evidence and not a measured case.

**A longevity instance, 2026-11-03: KL-VS buffering in APOE ε4 carriers.** longevitymap v2's plan
(§4.2, protection type `BUFFERING`) holds that the KL-VS heterozygote matters in ε4 carriers. KL is on
chromosome 13 and APOE on 19, so no haplotype holds the pair, and both halves are already enumerable on
their own (KL-VS as two-SNP haplotype rows, APOE as `apoe_epsilon`). Like CPIC's gene pairs and Lewis, it
argues for a **two-subject key** over two enumerated per-gene states (3 × 6 rows), not for a predicate.
The plan's interim is `flags: conditional` plus prose, and that tag does nothing ([RM321](ROADMAP.md#rm321--variantrowflags-calls-its-reserved-tags-the-tags-the-tooling-acts-on-and-no-tier-acts-on-any-of-them)). Unbuilt; corpus evidence.

### What dissolved, so it is not re-proposed

- **No operator is missing.** Rows are a disjunction and columns are a conjunction, so the existing
  tables already span any finite boolean function over an enumerable set of genotypes: `OR` is two rows,
  `XOR` and bounded `NOT` are enumeration, and `haplotypes.csv` is same-strand `AND`.
- **APOE** — whose ε4 condition (`rs429358==C AND rs7412==C`) is the Constitution's own example of a
  predicate — was built with 0.4 bricks and **no predicate at all**
  (`reference_examples/apoe_epsilon/`). `HaplotypeRow` is a junction table, so same-strand co-location
  is what it already expresses.
- **The cis/trans motivation closed as a check, not a table.** `reference_examples/hfe_compound_het/`
  showed that a diplotype is already a statement about two homologs, so cis and trans are two rows —
  the relational notion the grammar was going to add is what a diplotype pair *is*. What building it
  surfaced instead was that the two rows are **indistinguishable without phase**, which shipped as
  `_cross_validate_phase_ambiguity` (a warning, never a block). A `requires_phase` column was rejected:
  it would make an author restate what the data determines and go stale the moment a haplotype is
  edited. **Confirmed from the caller side, S116 (2026-09-26):** a shipped `just-dna-lite` caller ran
  against this example and the enumeration held — because the module defines the *cis* allele
  (`C282Y-H63D`) as its own haplotype with its own diplotype row, the caller could *name* the
  ambiguity (`ambiguous`, both candidates) rather than guessing or reporting `no_match`. So this is a
  case where enumeration succeeds and no predicate is wanted, which is where the entry drew its line.
  The one thing the caller had to re-derive — *which* diplotype pairs are the phase-confusable set — is
  not a predicate the author states but a value the compiler already computes and discards, filed as
  [RM266](ROADMAP_0_9.md#rm266--the-phase-confusable-diplotype-pair-set-is-computed-at-compile-and-dropped-it-reaches-the-artifact-only-as-a-capped-warning-string), not here.

### What remains

- **Pairing across *subjects*** — no table keys on more than one.
- **Economy and intent** — "any two pathogenic variants in trans" over 300 of them is ~45,000 pairs:
  expressible, unwritable, unreadable.
- **Open-world negation** — "no pathogenic variant in this gene" quantifies over a set the module does
  not close, and absence is only assertable where the region was callable (`requires_callable`). No
  operator fixes this, and a negation feature ignoring it would **manufacture reassurance**, the worst
  failure mode this format has.

It also blocks the "shy module" signal.

### Why it stays parked

It waits on a corpus to generalize from — roughly 70% built; nutrigenomics and supplements do not exist
yet — because fixing a shape against four table kinds and then meeting the fifth is how a one-way door
gets spent badly (P3/P5).

The design thread, the starter shape and what is deliberately left open are in
[PROPOSAL_0_5.md § G3](proposals/PROPOSAL_0_5.md): a new **optional** table, a predicate that **never blocks**, a
grammar kept to the smallest thing covering the motivating case, and a **three-valued** algebra
(true/false/**unknown**, Kleene operators) — with `unknown` withheld, never reported and never negated.
Kleene matters concretely: a conclusion gated on "ε4 present AND QUAL ≥ 60" is decidably **false** at
ref/ref whatever the quality was, so a blanket withhold-on-any-unknown would be strictly worse than the
tables it replaces.

### The cofactor half — CLOSED in the 0.6 review, do not re-open as a general mechanism

The original item proposed **injected cofactors**: values the consumer supplies at query time that a
module must never hold, in three classes. Two of the three were resolved in 0.5 by making them **plain
columns** — clinical context became `DiplotypeRow.clinical_context`, call quality became
`quality_from` / `min_quality` (RM29) — and neither needed a general mechanism.

**Decided 2026-08-13: the general "injected cofactor" mechanism is dropped as never-earned.** Each
remaining class gets the same treatment — a plain column, on demand, one at a time. Two classes wait:

- **Ancestry** — a panel-scale inference, not derivable from a curated module's own gnomAD frequencies,
  since real models do not rely on single SNPs.
- **Family structure** — **this is RM10**, folded in here on 2026-08-13. A declarative trio / de-novo /
  Mendelian-consistency expectation is only meaningful once the consumer supplies family structure at
  query time, which makes it a cofactor class rather than its own item. Designing it separately would
  fix a shape for one class before the axis exists. It was on-demand-only and shapeless for its whole
  life; it stays that way, here.

Neither is built until a real module needs it.

## RM337 — a file under `logs/` that is not `*.log` is dropped from the compile, and nothing says so

**0.8, decided 2026-11-04.** The maintainer told the lead to push its ready-to-build minors into 0.8's scope, and the lead listed this one as ready: about an hour on the `0.8` branch. It also carries the half of RM338 that needs the new warning code.


**Severity** medium · **Status** open — **a minor, release undecided** (corrected 2026-11-04 from "a
patch") · **Owner** compiler (`_collect_logs`) · **Motivating case** S125 in CONSUMER_SUGGESTIONS_HISTORY.md
(just-module-creator `F116`, 2026-10-05) · *related* RM338, RM147, RM308

**Reproduced 2026-11-03** on a copy of `reference_examples/apoe_epsilon` with six files under `logs/`
(`authoring.log`, `trace/session-a.jsonl`, `run.json`, `notes.md`, `notes.txt`, `fig.png`):
`compile_module` succeeds, no warning mentions a log, and both `manifest.logs` and the output's `logs/`
hold `logs/authoring.log` alone. Discovery globs `*.log` at the top level and `logs/**/*.log` below it,
and skips everything else under `logs/` without a word. The registry's server-side compile leaves
discovery to the compiler, so an upload carries the file and the published version does not.

**The patch.** A coded warning, in both modes, naming each file under `logs/` that discovery left behind
and saying that only `*.log` ships. It changes no verdict and ships nothing new, so it is legal whatever
RM338 decides; once RM338 widens the set, the warning names whatever is still left out. An explicit
`log_files` list is unaffected, since it already ships any path it names. The new code owes a
`features/` scenario.

**Sized wrong at filing; a minor (2026-11-04).** No existing member of `VALID_WARNING_CODES` names this
finding, and every compile warning must carry one (`compiler/tests/test_warning_codes.py`), so the item
adds a member. A new member is minor-class: `Compilation.warnings_summary` validates its keys, so a reader
pinned to an older `just-dna-format` refuses a manifest that carries the new code. RM308 is the shipped
precedent ("a new warning code, so minor-class"). A `logger` line would be patch-legal and is not taken:
it is not the warnings channel, so the registry's server-side compile, where S125's file goes missing,
would still say nothing to the uploader. Borrowing a code that names another finding is refused too
(`@warning-code-names-the-finding`). Which minor takes it is the pm's to place. RM338's shipping half
stays a patch; the warning half of its decision is this item.

**Residuals** none yet.

## RM342 — the manifest does not record the toolchain that wrote the bytes, so a digest that moves cannot say why

**Decided 2026-11-04 by the maintainer.**

- **One toolchain block:** a single optional field in `manifest.compilation` holding a small map (e.g. `{polars: 2.1.0, python: 3.13.1}`). A library added later is a new key, not a new field.
- **`verify` gives a toolchain difference its own reason.** "Bytes differ, toolchain differs" is distinct from corruption and never the plain mismatch error (`@vrs-three-outcomes`).
- **Principle 4 is amended.** Reproducibility is pinned via `compiler_version`, the recorded toolchain and the resolved reference. The why goes in `CONSTITUTION_AMENDMENTS_HISTORY.md`, and the lead lands the amendment with the item.

Ready to build; the polars 2 lock moves into 0.8 with it.

**0.8, decided 2026-11-04**, on the lead's list, "not ready": its open questions (one field or a toolchain block; whether `verify` reports a toolchain mismatch as its own reason; whether Principle 4 needs an amendment) are settled in the 0.8 interview. The polars 2 lock moves into 0.8 with it.


**Severity** medium · **Status** open — **a minor** (a new optional manifest field); the pm places it in 0.9 · **Owner** format + compiler · **Motivating case** RM341 · *related* RM304, RM341

**Why it is filed.** polars stays uncapped (RM341, the maintainer, 2026-11-04). From 2.0 the parquet bytes name
the polars release that wrote them, so two installs of one `compiler_version` mint different digests for equal
content, and nothing in the manifest says which polars wrote which. The liaison's adoption map, item 3: record
the polars version beside `compiler_version` in `manifest.compilation`, as an optional field. That is additive
and minor-legal. The alternative, deciding in P4 that the digest names the toolchain, would be a charter
amendment.

**Open questions.** Whether the record is one manifest field or a toolchain block (polars, arrow if it ever
appears, Python); whether `verify` reports a digest mismatch whose recorded toolchain differs from the running
one as its own reason (`@vrs-three-outcomes` asks for that); and whether P4's sentence on reproducibility needs
an amendment once the toolchain is recorded.

**Residuals** none yet.
