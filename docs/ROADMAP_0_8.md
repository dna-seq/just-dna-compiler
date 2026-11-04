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
| Built on the `0.8` branch, uncut | PT1's RM241, RM258, RM263, RM272, RM275, RM278, RM283, RM288, RM300, RM308, RM313; earlier RM256, RM257, RM259, RM260, RM262 and RM264's docs half | `proposals/PROPOSAL_0_8_PT1.md` and ROADMAP_HISTORY on the `0.8` branch | done (their entries are in ROADMAP_HISTORY since the 2026-11-04 sync) |
| The indel-placement fixes | [RM304](ROADMAP_HISTORY.md#rm304--a-vrs_id-does-not-say-which-vrs-minted-it-and-vrs-21-moves-some-insertion-ids) first, then [RM267](ROADMAP.md#rm267--the-ensembl-snapshot-anchors-a-class-of-insertions-one-base-early-and-resolutioncsv-serves-them-as-a-different-event), [RM270](ROADMAP.md#rm270--an-indels-artifact-key-is-its-sources-spelling-a-left-aligned-vcf-misses-a-respelled-row-and-the-spelling-independent-id-the-enricher-mints-never-reaches-the-artifact), [RM292](ROADMAP.md#rm292--a-verification-check-does-not-say-what-it-checked-against-so-a-check-that-witnesses-itself-reads-as-verified), [RM305](ROADMAP.md#rm305--clinvar-gkms-allele-table-is-an-offline-independent-witness-for-where-an-indel-sits-and-nothing-reads-it) | [ROADMAP.md](ROADMAP.md) | one design, interviewed before it is built; four are high severity |
| The lead's ready minors (2026-11-04) | RM337 (a warning naming each `logs/` file left behind), RM342 (the toolchain in the manifest, with the polars 2 lock) | their entries are in ROADMAP_HISTORY | both built on `0.8` (2026-11-04) |
| Chosen earlier | [RM303](ROADMAP_HISTORY.md#rm303--the-snapshot-layout-is-a-contract-with-six-parties-and-no-model-so-it-belongs-in-just-dna-format) (the snapshot layout as a model), [RM253](ROADMAP_HISTORY.md#rm253--a-repeat-count-star-allele-ugt1a1-28--ta8-has-no-home-a-diplotype-can-name-and-the-cpic-drafter-translates-none-of-cpics-notation) (a repeat-count star allele) | ROADMAP_HISTORY | both shipped 2026-11-04 on `0.8` |
| longevitymap v2 | RM28's combination half, RM322–RM336 ([the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03)), and [RM236](ROADMAP_HISTORY.md#rm236--consequence-and-impact-are-planned-axes-with-no-slot-and-an-acmg-engine-reads-both-as-primary-inputs), [RM239](ROADMAP_HISTORY.md#rm239--a-fine-mapping-posterior-has-no-column-and-gwas_effectscsv-already-has-its-key) as inputs to RM333's confidence labels | this file and [ROADMAP.md](ROADMAP.md) | design first; RM323 decides before RM324, RM326 and RM329 |

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
| [RM323](ROADMAP_HISTORY.md#rm323--a-fact-about-a-locus-has-no-authored-home-so-every-per-locus-axis-is-copied-onto-each-genotype-row-and-nothing-checks-the-copies-agree) | where per-locus facts live: typed columns per genotype plus an agreement warning, or a locus table | full ×n, or a new table kind | **decide first** |
| [RM322](ROADMAP_HISTORY.md#rm322--diplotypescsv-carries-none-of-the-axes-a-scored-finding-needs-so-apoe-the-modules-headline-result-cannot-state-its-tier-mechanism-or-trade-off) | `DiplotypeRow` gains `negatives` and `category` (`priority`, `actionability`, `flags` cut) | full ×2 | ✅ shipped 2026-11-04 |
| [RM324](ROADMAP_HISTORY.md#rm324--there-is-no-evidence-tier-column-so-the-axis-that-gates-visibility-is-a-flags-tiera-token) | evidence tier as value + scheme | full ×2 | home from RM323 |
| [RM325](#rm325--studiescsv-has-no-sample-size-and-v2s-tier-a-rule-is-stated-in-n) | `StudyRow` sample size (and cases) | full ×1–2 |  |
| [RM326](#rm326--a-study-row-cannot-say-which-outcome-it-measured-so-the-definition-of-pro-longevity-lives-in-a-study_design-prefix) | `StudyRow` phenotype class; evidence role and the outcome strip derived from it | full ×1, derived near-zero | check EFO first |
| [RM327](#rm327--pleiotropy-has-no-per-trait-row-so-a-trade-off-can-only-be-prose-and-tradeoff-is-computed-rather-than-authored) | per-trait benefit/harm table (mediator folds in); `tradeoff` computed; reserve the name | full (new kind), derived near-zero, reservation a patch | `tradeoff` decided |
| [RM328](#rm328--no-study-row-can-name-the-ancestry-it-was-measured-in-so-european-only-evidence-is-a-hand-set-flag) | `StudyRow` ancestry on a vocabulary; `eur_only_evidence` derived | full ×1, derived near-zero | RM188 axis 2 |
| [RM329](#rm329--an-age-stratified-estimate-has-no-age-band-so-age-of-action-is-reconstructed-from-statistical_test-prose) | `StudyRow` age band and whose age | full ×2–3 | interim works (RM140) |
| [RM330](#rm330--an-effect-measured-in-one-sex-one-smoking-stratum-or-one-genotype-has-no-row) | the stratum an estimate was measured in; sex as the first query-time modifier | full ×2 | RM188 axis 3 |
| [RM331](#rm331--a-study-measured-on-an-ld-proxy-cannot-say-so-and-filing-it-under-the-lead-checks-the-proxys-allele-against-the-leads) | `StudyRow` proxy variant + r²; the allele check follows the proxy | full ×2–3 |  |
| [RM332](#rm332--a-beta-has-no-unit-on-authored-rows-while-gwas_effectscsv-has-carried-one-since-06) | `effect_unit` on authored rows, as `gwas_effects.csv` has | full ×1–2 |  |
| [RM333](ROADMAP_HISTORY.md#rm333--the-effector-gene-behind-a-gwas-locus-has-no-source-and-no-column) | an Open Targets lane; effector gene, score, release on a derived table | half, plus a lane | ✅ shipped 2026-11-04 on `0.8`, uncut |
| [RM334](ROADMAP_HISTORY.md#rm334--an-hla-allele-has-no-table-and-tag-snps-cannot-stand-in-for-one) | the IPD-IMGT/HLA name grammar on `allele_function.csv` (the table was cut) | near-zero (a refusal) | ✅ shipped 2026-11-04 |
| [RM335](#rm335--model-organism-evidence-has-nowhere-to-go-and-a-study-row-naming-the-rsid-claims-the-mouse-study-was-about-the-human-variant) | a model-organism evidence table | full (new kind) |  |
| [RM336](ROADMAP_HISTORY.md#rm336--a-doi-written-into-pmid-parses-as-five-or-six-pubmed-ids-and-the-literature-pass-looks-each-one-up) | a DOI-token arm in `validate_pmid_cell` | near-zero (a refusal or a warning code) | **shipped 2026-11-04 on `0.8`, uncut** |

**Older items the plan also needs, tagged rather than moved** (each keeps its own entry; the 2026-11-03
scope decision put each in 0.8 or 0.9, as marked):

- **RM236** (**shipped 2026-11-04 on `0.8`**, in ROADMAP_HISTORY) — causal confidence C1 and effector confidence E1 both key on a variant being coding.
- **RM238** ([ROADMAP_0_9.md](ROADMAP_0_9.md), **0.9** since 2026-11-04: Open Targets' coloc, in RM333's lane, replaces it) — the cis-QTL colocalisation behind effector confidence E1/E2.
- **RM239** (**shipped 2026-11-04 on `0.8`**, in ROADMAP_HISTORY) — the fine-mapping posterior is the input to causal confidence C1–C4.
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

**Built on 0.8, 2026-11-04: the meta rows.** A per-trait judgement is a one-member `meta.csv` row with `trait_efo_id`, `direction` and an allele-bearing member (a bare locus bears one when its rows share an `effect_allele`, else `meta_member_allele_ambiguous` and the direction is withheld), `trait_role` (`mediator`) beside it. Still open: `tradeoff` and the resolved facts' Kleene table (B2), computed at `meta_resolved.parquet`'s grain; the name stays reserved until then.

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

**Built on 0.8, 2026-11-04: `sex`.** `meta.csv` gains the closed `sex` condition (`male`, `female`), part of the row key; a sex-scoped row outranks the same key without one, for that sex, and `meta_resolved.parquet` carries one row per scope. Still open: the study's stratum, `StudyRow`'s half (the `StudyRow` batch).

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

## RM28 — Meta-conclusions (the predicate half)

**Built on 0.8, 2026-11-04: the combination half** (the meta-table; its shipped record is [ROADMAP_HISTORY § RM28](ROADMAP_HISTORY.md#rm28--the-combination-half-the-meta-table)). Still open here: the study-orphan widening (wave 3, after the `StudyRow` batch), and the predicate half's remainder, which the maintainer put out of bounds.

**The name and grammar, accepted 2026-11-04 by the maintainer, as written in `proposals/PROPOSAL_0_8_PT2.md`
§3 items 1–4.**

- The file is `meta.csv`, and its parquet `meta.parquet`.
- There is one member grammar, `table[column=value, …]`.
- Members are joined by `&` in one bracket-aware `members` cell.
- Precedence follows from the conditions.
- The key is the sorted members, plus the trait, plus `sex`.

No bare-rsID shorthand yet. Adding one later is additive, if authors ask.

**Settled 2026-11-04 by the maintainer, after the second measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §6):

- **The narrower condition outranks, across tables too.** A diplotype row is more specific than an allele row
  for an allele it contains, just as a genotype row outranks its locus. The ε2/ε4 diplotype row settles the
  tie between the ε2 and ε4 allele rows.
- **`role` has one meaningful value:** empty means an effect, and `mediator` marks the path. Chains of two
  steps (9 v2 loci, LDL → CAD) stay as unordered mediator rows plus prose.
- **A locus-level member counts as allele-bearing** when every row of that locus states one `effect_allele`.
  A warning fires when they differ. That gives v2 about 134 per-trait rows instead of about 268.
- **Two rules set by the pm seat, unless the maintainer objects:**
  - the member tables are those that carry a finding (variants, diplotypes, pharm_variants), plus
    `allele_function.csv` as allele items. `haplotypes.csv` defines alleles and is not one.
  - the LD lookup withholds r² (unknown, counted) for a mixed-ancestry study, and never picks a panel.

**What is still not held, accepted as prose:** two modifiers on one estimate (2 loci), and two
causal-confidence judgements (README). With these rules the shape is sufficient for v2, and every addition
has a v2 case.

**The selector, widened 2026-11-04 by the maintainer** ("selector is just the right spice for meta"). It
supersedes the tag-only form above.

- **One general form, `column=value`**, over a single-statement table's columns. On a list column such as
  `flags`, `=` means "contains", so the legacy row is `flags=legacy_longevitymap`.
- **Several conditions in one member are AND-ed**, e.g. `diplotypes[gene=TPMT, phenotype=Poor Metabolizer]`.
- **Inside a combination, a selector is existential**: "any row of the set". CPIC's 6 gene pairs (18 drugs,
  2,656 recommendation rows) are written as phenotype pairs, one row each, instead of diplotype × diplotype.
  Lewis (FUT2 × FUT3 phenotypes) is the same shape. In a facts-only row, a selector's facts apply to each
  row it matches.
- **The compiler expands every selector** into the concrete rows it matches, in the parquet, so a consumer
  never evaluates a rule (P1). The authored row keeps its selector through `reverse` (P7).
- **A selector that matches nothing is a warning** (almost always a typo), and the manifest records each
  selector's match count (`@dont-discard-computed`).
- **Precedence:** a concrete row key, then a locus-level key, then a selector with more conditions, then
  one with fewer. Two matches that cannot be ordered and disagree withhold the column.
- **Out of bounds:** negation, OR, numeric ranges, joins across tables, and selectors over `studies.csv`.
  Rows are already a disjunction, and negation over an open set cannot be checked.

**Measured:** for v2 itself the widening adds nothing beyond the tag. Only 3 genes have more than one lead
locus (FOXO3, HTT, TERT), and none shares one tier. Its payoff is the PGx gene pairs and Lewis, at no
column cost: one grammar replaces a list of selector kinds.

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
