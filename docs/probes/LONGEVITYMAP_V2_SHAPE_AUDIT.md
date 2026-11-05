# longevitymap v2 against the 0.8 shape: the final measuring run (2026-11-04)

**What this is.** The audit the maintainer asked for before 0.8's longevitymap v2 work goes to the lead. Every
requirement in just-dna-lite's `docs/longevitymap_v2/longevitymap_v2_requirements.md` was measured against the
shape decided in the 0.8 interview. Then every new column was checked twice: it needs a v2 case it cannot do
without, and it must not be derivable from the others. The run was a subagent (Opus), and the pm seat
compiled it. The full candidate reference examples are in the appendix.

**The proposal measured.** The 2026-11-04 decision lines in [ROADMAP_0_8.md](../history/ROADMAP_0_8.md) (RM28,
RM322–RM336, with RM323's final "go with C" winning over its earlier lines), and RM302 in
[ROADMAP.md](../ROADMAP.md).

**v2's data.**

- All 50 `R-*` requirements and §4.2, §6 and §10.
- `data/seed_variants.csv`: 228 rsIDs, 161 lead loci.
- 391 variant × study candidate rows (tracks A–E), covering 280 distinct (rsid, pmid) pairs and 282
  studies, 242 of them primary.
- The evidence files: H pleiotropy (32 loci), K age of action (40 loci, 24 with age bands), G
  fine-mapping (75 rows), J model organisms (77 rows).
- The research archive `data/input/4bf03886-ed3d-4db5-945c-fa8f09c1049f.zip` (git-ignored).

**Labels.** A count is **M** when read off a column, and **I** when it comes from a keyword or regex
classification of free text, so treat an I count as approximate. A verdict is **T** (fits today), **N** (fits
through a named new column or table), **D** (fits only by derivation) or **X** (does not fit).

## 1. The result in one paragraph

The shape is **neither sufficient nor minimal as proposed**. It cannot hold twelve things v2 has (§4). Five
proposed additions are used by no v2 requirement, and a further five are derivable from other columns (§3).
The pm seat's verdicts per column are in §3's last column. **The maintainer decided all of them on
2026-11-04 as proposed, with three changes:**

- the meta-table gains `flags`, for parity, so `ap:` and `hallmark:` tags have a home (`also_in` stays
  prose);
- the LD pair (r² and its population) is **computed** from `proxy_rsid` and the study's ancestry;
- preprints cite through a `pmid` sentinel that makes `doi` mandatory.

The gaps' fixes in §4 are decided the same way (gap 9: `flags` on the meta-table; gap 5: the sentinel). Each
decision is recorded in its roadmap entry.

## 2. Requirements

| Req | V | Home in the proposed shape | v2 instances |
|---|---|---|---|
| R-PHENO / R-DEF-1 | N | `StudyRow.phenotype_class` (open, 12 recommended) | 242 primary studies (I); 15 of 63 K PMIDs carry 2–3 classes (M) |
| R-TIER (§4.1 gate) | N | meta-table `tier`, scale named in `module_spec.yaml` | 161 leads (M); seed tiers A43 B108 C41 D1 **X4**, none 31; H file **A-5 B-1** (M) |
| R-TIER-1 | N+D | `tier` D on a one-member row | 280 v1 rsIDs (M) |
| R-TIER-2 | N | authored `tier`; the replication cap has no column | not countable |
| R-TIER-3 | D | European-only derived from `ancestry`; the banner is the consumer's | 118 of 161 leads EUR-only, 22 mixed, 21 unknown (I) |
| R-CAUSAL | N or D | meta `causal_conf` / `effector_conf`, or computed from fine-mapping, consequence, L2G and coloc | computable on 67 of 75 G rows (M) |
| R-MECH | T | `category` | 32 loci name a mediator (M) |
| R-PLEIO | N+D | per-trait meta rows; `tradeoff` computed | 15 of 32 loci carry benefit and harm (I) |
| R-VOICE-1…6, R-CONTEXT, R-PGS | T | `conclusion` (already lay), `negatives`, README, `pgs.csv` | all scored rows |
| R-ANC-1 | T | `population` (exists) | all study rows |
| R-ANC-2 / R-ANC-4 | D | European-only and ancestry-specific over `ancestry` (1000G codes) | 315 EUR-only, 56 mixed, 11 unmappable, 9 missing of 391 (I) |
| R-HLA | N | `(gene, allele)` on `allele_function.csv` + meta rows, or a new HLA table | 8 alleles (M) |
| R-ANIMAL-1/-2/-4 | N | the model-organism table only | 77 rows, 40 genes; concordance 19/3/55 (M) |
| R-AGE | N | meta `age_of_action` + `age_conf`; band columns on studies | 40 loci, 72 band rows (M) |
| R-DEF-2 (protection type) | D/X | BUFFERING follows from a combination row; PRESENCE/ABSENCE needs allele frequency | 1 buffering, 3 presence (M) |
| R-RARE-1 | T+N | haplotypes/diplotypes; KL-VS heterozygote modifier as a combination | APOE, KL-VS, d3-GHR (M) |
| R-RARE-2 | N+D | tier cap checkable from `phenotype_class` = MR | 4 lipid LoF genes (M) |
| R-LEGACY-1 | N | one meta-table row with a tag-selector member (`flags:legacy_longevitymap`, tier D), decided 2026-11-04, instead of 528 one-member rows | 528 rsIDs, 671 study rows (M) |
| R-CAT-2 | X | hallmark tags in `flags` work on variants, not on diplotypes | APOE (1) |
| R-APOE-1 | T, warns | haplotypes + diplotypes; studies on rs429358/rs7412 draw `study_variant_orphan` | 14 (rsid, pmid) links (M) |
| R-APOE-2 | N | per-trait diplotype rows + RM322's columns | 6 diplotypes × 2 traits |

The remaining requirements (R-ANC-3, R-APOE-3: the consumer; R-SCOPE, R-ANIMAL-3, R-DEF-3, R-RARE-3…6,
R-LEGACY-2/-3, R-CAT-1, R-TIER-4) fit today or are reporting rules with no data.

## 3. Every new column, tested

The "needed by" column names the v2 case that cannot be written without the column. "Derivable" names the
columns it could be computed from, and how often that derivation holds in v2's data.

| Column / table | Needed by | Derivable from | Holds | Verdict (decided 2026-11-04) |
|---|---|---|---|---|
| meta-table | KL-VS × ε4; APOE ε2 ≠ ε4 facts | — | — | **keep** |
| `tier` | visibility gate: 161 leads + 528 legacy | — | — | **keep**; values open within the module's scale (seed uses X, A-, B-) |
| `causal_conf` | 8 curated rows with no numeric posterior | fine-mapping posterior + consequence | 67/75 (M) | **cut: compute**; the 8 curated inputs go in `overrides.csv` |
| `effector_conf` | the same 8 | L2G + coloc + coding | 67/75 (M) | **cut: compute** (also removes the E1/E2 vs E1–E4 mismatch) |
| `age_of_action` | 9 inferred loci with no bands | — (a judgement) | — | **keep** |
| `age_conf` | 16 of 40 loci have no bands | DIRECT ⇔ band moderation q < 0.05 | 19/24 (M) | **keep** (fails 5, and missing for 16) |
| `sample_size` | tier A "N ≥ 100k" | — | — | **keep** |
| `sample_unit` | Pilling 389,166 participants vs Timmers 1,012,240 lives | `phenotype_class` = PARENTAL | 4/13 (I) | **keep** (not derivable) |
| `n_cases` | Deelen 11,262 / 3,484 vs "≥ 3k cases" | — | — | **keep** |
| `phenotype_class` | Timmers 2020: 3 classes × 10 variants | `trait_efo_id` | 0/12 (M) | **keep** |
| `ancestry` | R-ANC-2/-4 | `population` text | 371/391 map (I) | **keep** (free text cannot be checked) |
| `age_min` / `age_max` | 72 Timmers band rows | — | — | **keep** |
| `age_of` (whose age) | Pilling top-10% parents; rs3135388 parents ≥ 95 | `phenotype_class` | fails ~4 rows (I) | **keep** |
| `age_event` | none: 0 non-death rows (I) | — | — | **cut** |
| stratum + level | Pilling father/mother, 13 rows; FOXO3 "hypertensive men" | — | — | **keep** |
| `sex` (on conclusions) | HLA-DRB1\*15:01, d3-GHR, FOXO3 men, ~3 loci (I) | a sex stratum on supporting rows | fails (rs3135388 unstratified) | **keep** |
| `proxy_rsid` | CELSR2 via rs4970836, FOXO3 via rs3800231; 5 APOE proxies (M) | — | — | **keep** |
| `proxy_r2` | ~5 numeric values anywhere (I) | an LD reference, given the proxy, the lead and the study's ancestry | — | **computed, as a pair with its population** (half price) |
| `proxy_ld_pop` | none: 0 values (I) | study `ancestry` | — | **computed with r²** (a valid specifier; r² is meaningless without it) |
| `effect_unit` on studies | betas in 4 units: years 57, −lnHR 35, Martingale 24, log-odds 16 (I) | `effect_measure` | ratio measures only (I) | **keep** |
| `effect_unit` on variants | restates the anchor study's unit | the anchor study | always | **cut** (reverses a 2026-11-04 decision; asked) |
| diplotype `negatives` / `category` | ε2/ε2 recessive harm; APOE → `brain_memory` | — | — | **keep** |
| diplotype `priority` | APOE ordering | `tier` | always under v2 | **cut** |
| diplotype `actionability` | APOE `descriptive` | v2's policy: LATE ⇒ descriptive | 4 LATE loci (I) | **cut** (the policy belongs in the README) |
| `conclusion_lay` / `_concise` | none: v2's `conclusion` is already lay (R-VOICE-1) | — | 0 uses | **cut from 0.8** (back to 0.9; asked) |
| L2G table (derived) | R-CAUSAL | the Open Targets lane | 40 seed rows (M) | **keep** |
| outcome strip (derived) | §5.1 | `phenotype_class` | — | **keep**; MULTIVARIATE_AGEING's mapping is v2's to state |
| `tradeoff` (derived) | 15 loci | per-trait rows | 30/32 agree with v2's label (I) | **keep** |
| HLA table | 8 alleles | `allele_function.csv` + meta rows hold all 8 | 8/8 | **cut the table**; the grammar check moves to HLA alleles on `allele_function.csv` |
| model-organism table | 24 of 77 rows are gene-only; species, model, diet | — (no gene member, no `StudyRow.gene`) | — | **keep** |

## 4. What the shape cannot hold, and the smallest fix

| # | Gap | v2 cases | Smallest fix (pm, pending) |
|---|---|---|---|
| 1 | Nesting across member kinds: the ε2/ε4 diplotype matches both the ε2 and ε4 allele rows, and neither key contains the other | 1 (M) | a rule, no column: two incomparable matching rows that disagree on a column **withhold** it (Kleene) unless a more specific row exists. The author writes the ε2/ε4 diplotype row to settle it |
| 2 | A per-trait row on a locus-level member has no allele for `direction` to refer to | 4 loci with no determined allele (M) | a rule: a per-trait row must name an allele-bearing member. The 4 loci honestly have no direction |
| 3 | No study row can cite a diplotype, allele or combination member | APOE 14 links; 8 HLA alleles; KL-VS × ε4 | **+1 column, decided**: a citation (`pmid`) on meta-table rows, the RM47 pattern (a row cites when its claim is finer than `studies.csv`'s key). Also, the orphan check accepts meta-table members |
| 4 | The mediator role is lost when per-trait rows replaced RM327's table | 32 loci (M) | **+1 column, decided**: the trait's role (outcome / mediator) on per-trait rows |
| 5 | Preprint-only evidence has no legal `pmid` once a DOI is refused | 17 studies (M) | **decided**: `pmid` accepts a `NONE` sentinel that makes `doi` the mandatory, validated substitute |
| 6 | A percentile threshold has no typed home | Deelen, 16 variants | none: `statistical_test` keeps it (RM140's interim works) |
| 7 | Two modifiers on one estimate | 2 loci (I) | none: prose for 2 loci; a second stratum pair is not worth a column |
| 8 | MULTIVARIATE_AGEING fills no outcome cell | 16 leads (I) | none in the format: the mapping is v2's to state in its README |
| 9 | Tags (also-in, hallmarks) have no home on APOE: diplotypes carry no `flags` | APOE (1) | **decided**: `flags` on the meta-table, for parity with `variants.csv` (APOE is the canary, not the reason) |
| 10 | No bare-gene member | 24 model-organism rows; 7 gene-level LoF rows (out of scope) | the model-organism table keys on gene itself |
| 11 | A closed tier scale would refuse seed `X` (4) and `A-`/`B-` (6) | 10 (M) | tier values are open within the module's named scale |
| 12 | The duplicate-citation narrowing names only `phenotype_class` | 72 band rows, 13 stratum rows | a rule: age bands and strata narrow it too (RM140's pattern), no column |

## 5. Candidate reference examples

These are the non-trivial cases only; obvious single-SNP shapes are left out. Each candidate has full
authored rows in the appendix.

| # | Case | v2 count |
|---|---|---|
| 1 | Facts-only one-member row (how a single locus gets its tier) | 161 leads (M) |
| 2 | Allele facts differ; a diplotype matches two general rows | 1; 3 archive breaks (M) |
| 3 | A combination replaces (KL-VS × ε4) | 1 combination, 3 rows (M) |
| 4 | Per-trait rows → computed `tradeoff` | 15 loci (I); 4 with no allele (M) |
| 5 | Two classes, one paper (Timmers 2020) | 10 variants (M) |
| 6 | Same class, the analysis differs (Deelen percentiles; Pilling parent sex) | 3 + 24 (M) |
| 7 | Parental lives against participants | 4 lives / 9 participants (I) |
| 8 | Age bands on parental age at death, open upper bound | 72 rows (M) |
| 9 | A proxy-measured study with r² unknown | 2 (M) |
| 10 | An HLA allele as a `(gene, allele)` member, sex-conditional | 8 alleles (M) |
| 11 | Preprint-only evidence after the DOI refusal | 17 studies (M) |
| 12 | Model-organism evidence: three candidate homes | 77 rows (M) |
| 13 | Two strata on one estimate | 2 loci (I) |

## 6. Second run, against the reshaped shape (2026-11-04, the same agent, read at `0fb954f`)

The run re-measured every requirement against the shape after §3's verdicts, the computed LD pair, the
meta-table's citation, role and `flags`, the `pmid = NONE` sentinel and the widened selector.

**Verdicts that moved.** These requirements now fit:

- the tier scale, which accepts X, A- and B-;
- the legacy layer: 528 rows become one tag-selector row. 8 seed-tiered v1 rsIDs need a concrete row to beat
  D;
- ADARB (R-RARE-4): 18 rows become 2, through an AND-ed selector (`gene=ADARB1, flags=legacy_longevitymap`);
- hallmark and protection tags (R-CAT-2, R-DEF-2), through the meta-table's `flags`;
- APOE's 14 study links, through the meta-table's citation;
- the 17 DOI-only studies, through `NONE` + `doi`;
- the 32 mediators, through `role`;
- R-CAUSAL, now derived: the computed C agrees with v2's 18 curated assessments on 14 (longevity credible
  sets) or 16 (any-trait sets).

**Every addition has a v2 case** (the run's table, with counts). Two are in question:

- `role=outcome` is derivable;
- the meta-table's `flags` has one locus, which the maintainer accepted for parity.

**Still not held:**

1. **A meta-table row cannot cite a DOI-only preprint**, because there is no `doi` beside its `pmid`. That
   affects 6 preprint HLA alleles (M), and RM335's 17 PMID-less rows have the same question.
2. **ε2/ε4: two concrete keys from different tables tie** (an allele row from `allele_function.csv` and a
   diplotype row). Precedence does not rank a diplotype over the alleles it contains, so no author row can
   settle it (1, M).
3. Two modifiers on one estimate (2 loci) and two causal-confidence judgements stay prose, as already
   accepted.

**Unstated rules the build needs:**

- which tables count as member tables (`haplotypes.csv`?);
- what the LD lookup does for a mixed-ancestry study (3 of 68 links);
- whether `effect_allele` must be uniform across a locus's rows. That uniformity is what lets a locus-level
  per-trait row count as allele-bearing: about 134 rows, against about 268 with genotype keys. v2
  harmonises it (`allele_conflict` false on 228/228, M), but no format rule requires it.

**Edges for the examples:**

- 9 two-hop mediator chains (LDL → CAD) become unordered mediator rows.
- 3 mixed-ancestry proxy links have no single LD panel, and Ashkenazi maps to EUR (12 rows).
- "ε4 carrier" through a diplotype selector works only because pairs are canonicalised. The `(APOE, ε4)`
  allele member says it directly.
- v2 writes the legacy set twice, as `flags` and as `category=legacy_candidate`. That is for v2's README.
- rs2075650 gets tier D from the tag while its seed says C, which is correct if "not scored" is the intent.

**Decided after the second run (2026-11-04).**

- The pmid/doi pair applies to every citing table.
- A diplotype outranks the alleles it contains.
- `role` is empty or `mediator`.
- A uniform `effect_allele` makes a locus allele-bearing, with a warning when the rows differ.
- The member tables, and r² withheld on mixed ancestry, as the pm seat set them.

**The shape is agreed:** sufficient for v2, apart from the two accepted prose cases, and every addition has a v2
case.

The run's rewritten examples, in the final shape only, are in this report's appendix below the first run's;
two of the first run's cases were dropped as trivial.

## 7. Errata, and what the reference examples found (2026-11-04, the lead's report)

Writing 0.8's reference examples from this report's rows found three errors in the illustrative rows. None of
them changes a shape decision.

- **The PPARG model-organism row**: "benefit lost on high-fat diet" is a metabolic outcome, not a lifespan one.
- **The age bands** in the examples were v2's own pooling, not bands the studies report.
- **The healthspan sample size** is 300,477, not the 300,447 the rows give.

The lead also overstated a count in PT2 §3 item 23: "17 of 77 uncited" model-organism rows. The one GenAge entry
checked (Ghrhr) has a PMID, 11371619, so the real number is lower and was not re-measured.

The examples also found four facts with no cell, which this report's runs missed. They are RM360, for 0.9.

## Appendix: the candidate examples, as the run wrote them

Working names throughout (the meta-table as `meta.csv`, members joined by ` & `). Every name still owes its
P5 audit. These rows were written before §3's cuts and §4's fixes, so they still show the cut columns.


### 1. Facts-only, one member: how a single locus gets its tier

**Exercises.** RM323 "go with C" and RM324's single `tier` column on a scale named once per module.
Facts are written once and never repeated on the three genotype rows.

**Count.** Every scored lead locus gets one such row. The seed has 161 leads (M), 93 of them at seed
tier A or B (M). 40 loci have an age-of-action class (M), and 25 leads have fine-mapping or L2G inputs
(M).

```yaml
# module_spec.yaml (excerpt)
tier_scale: longevitymap_v2_A-D      # the scale is named once; its rubric is in README
```
```csv
# meta.csv
members,trait_efo_id,direction,conclusion,negatives,sex,tier,causal_conf,effector_conf,age_of_action,age_conf
rs10455872,,,,,,A,C2,E2,MIDLIFE,DIRECT_WEAK
```
```csv
# variants.csv: the finding per genotype; no tier and no age class here
rsid,genotype,state,direction,effect_allele,effect_size,effect_measure,effect_unit,stat_significance,conclusion,phenotype,category,trait_efo_id,priority,actionability
rs10455872,A/A,neutral,protective,A,0.7639,beta,years of parental lifespan per allele,significant,"You carry two copies of the common version…",Lp(a) and heart disease,heart_vessels,EFO_0007796,high,preventable
rs10455872,A/G,risk,protective,A,0.7639,beta,years of parental lifespan per allele,significant,"You carry one copy of the version that raises Lp(a)…",Lp(a) and heart disease,heart_vessels,EFO_0007796,high,preventable
rs10455872,G/G,risk,protective,A,0.7639,beta,years of parental lifespan per allele,significant,"You carry two copies of the version that raises Lp(a)…",Lp(a) and heart disease,heart_vessels,EFO_0007796,high,preventable
```
**Edge.** `priority` (`high`) is v2's tier A restated (§6.2: "derived from tier"). Here it is written
three times next to a tier that is written once. `causal_conf` C2 follows from the lead PIP of 0.38–0.40
across three credible sets (the seed takes the maximum), and `effector_conf` E2 follows from L2G 0.56
without coloc. Both are computable from the inputs. RM333 calls such labels "computed once the inputs
exist, never authored", while RM323's final decision makes them authored meta-table columns. See the
column table in REPORT.md.

### 2. Allele facts that differ, and a diplotype matching two general rows

**Exercises.** A `(gene, allele)` member, RM322's four new `DiplotypeRow` columns, and nesting across
member kinds.

**Count.** 3 named-allele "breaks" in the archive check (APOE ε2/ε4, HLA-B\*57:01, HLA-DRB1\*15:01; M,
from RM323). 6 ε diplotypes, of which 1 (ε2/ε4) carries both alleles (M). APOE's 31 study rows are 14
distinct `(rsid, pmid)` links over 13 PMIDs (M).

```csv
# haplotypes.csv (as reference_examples/apoe_epsilon)
haplotype_name,gene,rsid,allele
ε2,APOE,rs429358,T
ε2,APOE,rs7412,T
ε3,APOE,rs429358,T
ε3,APOE,rs7412,C
ε4,APOE,rs429358,C
ε4,APOE,rs7412,C
```
```csv
# meta.csv
members,trait_efo_id,direction,conclusion,negatives,sex,tier,causal_conf,effector_conf,age_of_action,age_conf
allele:APOE=ε4,,,,,,A,C1,E1,LATE,DIRECT
allele:APOE=ε2,,,,,,A,C1,E1,LATE,DIRECT_WEAK
```
```csv
# diplotypes.csv: RM322's columns negatives, category, priority, actionability
gene,haplotype_a,haplotype_b,trait_efo_id,direction,phenotype,conclusion,negatives,category,priority,actionability
APOE,ε2,ε2,OBA_VT0005372,protective,APOE ε2/ε2,"You carry two copies of ε2…","Two copies of ε2 can raise rare blood-vessel problems…",brain_memory,high,descriptive
APOE,ε2,ε4,OBA_VT0005372,risk,APOE ε2/ε4,"…",,brain_memory,high,descriptive
APOE,ε3,ε4,OBA_VT0005372,risk,APOE ε3/ε4,"You carry one copy of ε4…",,brain_memory,high,descriptive
APOE,ε3,ε4,MONDO_0004975,risk,APOE ε3/ε4 and Alzheimer's,"…",,brain_memory,high,descriptive
```
**Edges.**
- **Which table holds `allele:APOE=ε4`?** "A member must exist as a row of its own table." `haplotypes.csv`
  is keyed `(haplotype_name, variant_key, allele)`, a junction row per defining variant, so `(APOE, ε4)`
  is a projection of it rather than a key. `allele_function.csv` is keyed `(gene, allele)`, and its name
  rule is `^\S+$`, so `ε4` passes. Under that reading, every named-allele member also costs an
  `allele_function.csv` row, whose other columns are PGx activity.
- **Two general rows, one specific row.** The ε2/ε4 diplotype matches both `allele:APOE=ε2` (age_conf
  `DIRECT_WEAK`) and `allele:APOE=ε4` (`DIRECT`). Neither key contains the other, so "the most specific
  wins" picks nothing, and "an empty cell falls back to the general row" has two general rows. Nesting is
  defined only where one key contains the other, and an allele and a diplotype row relate only through
  `haplotypes.csv`.
- **The ε2/ε2 recessive harm** is a fact of the diplotype, not of an allele. It lands in RM322's new
  `negatives`.
- **Study rows.** APOE's studies cite rs429358 and rs7412. When APOE is scored only as a diplotype
  (R-APOE-1), those SNPs are not `variants.csv` rows, so all 14 links draw `study_variant_orphan`
  (`_cross_validate_studies` matches on `variants.csv` only). No study row can name a diplotype or an
  allele member.

### 3. A combination replaces the findings it names: KL-VS buffering in ε4 carriers

**Exercises.** RM28 in 0.8: a multi-member row, "a matching combination replaces", and a member that
is a diplotype row key.

**Count.** 1 combination in v2 (M), which becomes 3 composite rows, one per ε4-carrying diplotype. 2
study rows from 1 PMID (M). It is the only BUFFERING locus in v2 (M, §4.2).

```csv
# haplotypes.csv
haplotype_name,gene,rsid,allele
KL-VS,KL,rs9536314,G
KL-VS,KL,rs9527025,C
```
```csv
# diplotypes.csv: the member row must exist and carry its own required conclusion
gene,haplotype_a,haplotype_b,trait_efo_id,direction,phenotype,conclusion,category,priority
KL,KL-VS,ref,MONDO_0004975,unknown,KL-VS heterozygote,"On its own, one copy of KL-VS has no clear effect…",brain_memory,low
```
```csv
# meta.csv
members,trait_efo_id,direction,conclusion,negatives,sex,tier,causal_conf,effector_conf,age_of_action,age_conf
dip:KL=KL-VS/ref@MONDO_0004975 & dip:APOE=ε3/ε4@MONDO_0004975,MONDO_0004975,protective,"You carry ε4 and one copy of KL-VS; in ε4 carriers over 60 one KL-VS copy was linked to lower Alzheimer's risk…",,,C,,,,
dip:KL=KL-VS/ref@MONDO_0004975 & dip:APOE=ε4/ε4@MONDO_0004975,MONDO_0004975,protective,"…",,,C,,,,
dip:KL=KL-VS/ref@MONDO_0004975 & dip:APOE=ε2/ε4@MONDO_0004975,MONDO_0004975,protective,"…",,,C,,,,
```
```csv
# studies.csv: age ≥60 is an age band, ε4 carriage is the combination itself (not a stratum)
rsid,pmid,population,ancestry,phenotype_class,effect_allele,effect_size,effect_measure,p_value,age_min,age_of,stratum,stratum_level,statistical_test
rs9536314,32282020,Northwestern European,EUR,AD_RISK,G,0.75,OR,7.4e-7,60,participant,,,"KL-VS heterozygous vs non-carrier, APOE4 carriers"
```
**Edges.** The KL-VS row's `conclusion` is required, although v2 says it has "no marginal net" (the
cost RM28 accepted). The three composites need the ε4 diplotype rows to exist with an Alzheimer's
`trait_efo_id`, so APOE needs Alzheimer's rows as well as lifespan rows. The study row cannot say "in ε4
carriers" as data: that is the stratum RM330 sends to RM28, and RM28's row cannot carry a citation.
Its `phenotype_class` (AD risk) is none of the twelve, so it draws the open vocabulary's warning. v2
has no age-of-action class for KL-VS, so the composites leave those cells empty.

### 4. Per-trait judgements, and `tradeoff` computed from them

**Exercises.** The RM327 default (member + `trait_efo_id` + `direction` as meta-table rows) and the
computed `tradeoff`.

**Count.** 15 of the 32 pleiotropy loci have both a benefit and a harm; about 134 per-trait items
across the 32 (I). The computed `tradeoff` agrees with the authored `TRADEOFF` label on 30 of 32 (M on
labels, I on parsing). The two that differ are TCF7L2 (computed true, not labelled) and HLA rs34831921
(labelled "hypothesised", nothing assessed, so Kleene unknown).

```csv
# meta.csv, reading A: the member is a genotype row, so direction has an allele (rows multiply by genotype)
members,trait_efo_id,direction,conclusion,negatives,sex,tier,causal_conf,effector_conf,age_of_action,age_conf
rs3184504=C/C,TRAIT:hypothyroidism,protective,,,,,,,,
rs3184504=C/C,EFO_0001645,protective,,,,,,,,
rs3184504=C/C,TRAIT:sepsis_mortality,risk,,,,,,,,
rs3184504=C/C,TRAIT:cancer,risk,,,,,,,,
# derived: tradeoff(rs3184504=C/C) = true
```
```csv
# meta.csv, reading B: a locus member needs an allele that direction is about (RM327's earlier effect_allele)
members,effect_allele,trait_efo_id,direction
rs3184504,C,EFO_0001645,protective
rs3184504,C,TRAIT:sepsis_mortality,risk
```
**Edge.** A locus-level member (`rs3184504`) has no allele for `direction` to be about. Either the
member is a genotype row key (reading A, ×3 rows per trait at a biallelic site), or the per-trait row
keeps `effect_allele` (reading B, one more column on the meta-table). The proposal does not choose
between them. CETP rs3764261 and rs5882, TERT and TERC have "allele not determined" (4 loci, M): no
per-trait row can be written for them under either reading.

### 5. Two classes, one paper: Timmers 2020 (and the outcome strip it fills)

**Exercises.** RM326's `phenotype_class` and its narrowing of `duplicate_study_citation`. The derived
outcome strip.

**Count.** 10 variants in PMID 32678081, each with a longevity log-OR, a parental-lifespan −lnHR and a
healthspan beta (M for the 10, I for classes). Among the leads, 8 have study rows in all three outcome
cells, 17 in two, 91 in one, 16 only in MULTIVARIATE_AGEING rows and 29 in none (I).

```csv
# studies.csv
rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,p_value,sample_size,sample_unit,statistical_test
rs10455872,32678081,EXTREME_SURVIVAL_CC,A,0.124,log(OR),log-odds per allele,7e-03,,,longevity component of MANOVA
rs10455872,32678081,PARENTAL_LIFESPAN,A,0.076,beta,-ln HR per allele,9e-25,1012240,lives,parental lifespan component
rs10455872,32678081,HEALTHSPAN,A,0.057,beta,-ln HR per allele,1e-10,300447,individuals,healthspan component
# derived outcome strip for rs10455872: healthspan + / lifespan + / exceptional +
```
**Edges.** These three rows are distinct only because `phenotype_class` is both stated and different.
Note also the multivariate rows: 16 leads have only an mvAge (MULTIVARIATE_AGEING) study (I). That class
fills none of the three cells, so a genome-wide-significant locus reads "untested ×3", and the
proposal has no rule for it.

### 6. Same class, analysis differs: Deelen 90th and 99th percentile; Pilling by parent sex

**Exercises.** The limit of RM326's narrowing: rows that share a class.

**Count.** Deelen (31413261) has 16 variants, 3 of them with both a 90th- and a 99th-percentile row
(M). Pilling (29227965) has 24 variant rows, split by analysis into fathers 11, mothers 2, attained
age 7, age at death 2 and both-parents-top-10% 2 (M).

```csv
# studies.csv
rsid,pmid,phenotype_class,effect_size,effect_measure,n_cases,sample_size,sample_unit,age_of,stratum,stratum_level,statistical_test
rs7412,31413261,EXTREME_SURVIVAL_CC,1.28,OR,11262,36745,individuals,participant,,,">=90th percentile vs <=60th"
rs7412,31413261,EXTREME_SURVIVAL_CC,1.47,OR,3484,28967,individuals,participant,,,">=99th percentile vs <=60th"
rs74444983,29227965,PARENTAL_LIFESPAN,-0.0143,beta,,389166,individuals,parent,parent_sex,father,"BOLT-LMM fathers_attained (Martingale)"
```
**Edges.** The percentile threshold has no typed home. A percentile is an age per birth cohort, so
`age_min` cannot hold it, and it stays in `statistical_test` (RM140's existing split). Pilling's
father/mother split is "whose age" (parent) plus a stratum (parent sex). Two proposed columns together
encode one fact (see the duplication finding in REPORT.md). The Deelen `sample_size` is cases plus
controls (11,262 + 25,483). Whether `sample_size` includes cases is a naming decision.

### 7. Parental lives against participants

**Exercises.** `sample_unit` (individuals / lives) and the claim that it is derivable from the class.

**Count.** Of 22 parental-lifespan studies, 4 state N in parental lives, 9 in participants and 9 give no
N (I). 2 studies outside the parental class state N in parents or lives (28873088 GERA + UKB parents;
29496957 family trees) (I).

```csv
rsid,pmid,phenotype_class,sample_size,sample_unit,n_cases
rs10455872,30642433,PARENTAL_LIFESPAN,1012240,lives,
rs74444983,29227965,PARENTAL_LIFESPAN,389166,individuals,
```
**Edge.** Tier A's rule is "N ≥ 100k lives". Timmers 2019 passes it in lives. Pilling's 389,166
participants report on about twice as many parental lives, but the paper's N is in participants. So the
unit follows the paper, not the class. `n_cases` is empty on both rows: Timmers states about 60% of
parents deceased, which is a fraction, not a count.

### 8. Age bands on parental age at death, with an open upper bound

**Exercises.** RM329's band bounds, whose age and which event. The `age_conf` derivation.

**Count.** 24 loci × 3 bands = 72 band rows, all from Timmers 2019 (PMID 30642433), all parental age
(M). DIRECT ⇔ band-moderation q < 0.05 holds on 19 of 24. LDLR and CELSR2 have bands but are graded
INFERRED, and FOXO3, ZC3HC1 and TMEM18 have bands but are graded UNKNOWN (M).

```csv
rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of,age_event,statistical_test
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.1089,beta,log protection ratio per allele,40,60,parent,death,"age-band estimate, father/mother pooled"
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.0778,beta,log protection ratio per allele,60,80,parent,death,"age-band estimate, father/mother pooled"
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.0530,beta,log protection ratio per allele,80,,parent,death,"age-band estimate, father/mother pooled"
```
**Edges.** The three rows share `(variant_key, pmid)` and `phenotype_class`. The duplicate check must
treat stated, different age bounds as distinct, or the author keeps writing a distinct
`statistical_test` (today's interim). `age_event` is `death` on all 72 rows: no v2 row has a different
event (I). The pooled father/mother estimate is the track's own inverse-variance pooling, not the
paper's.

### 9. Proxy-measured study, r² unknown

**Exercises.** RM331's `proxy_rsid`, `proxy_r2` and `proxy_ld_pop`, with the allele check following
the proxy.

**Count.** 2 age-of-action loci were measured on a proxy (CELSR2 lead rs646776 via rs4970836; FOXO3
lead rs1159806 via rs3800231) (M). There are 67 non-lead seed rsIDs across 24 multi-variant loci (M) and
5 APOE-region proxies (M). Only about 5 distinct numeric LD r² statements exist anywhere in v2 (I), and
0 state an LD reference population with an r² (I).

```csv
rsid,pmid,proxy_rsid,proxy_r2,proxy_ld_pop,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of
rs646776,30642433,rs4970836,,,G,0.2234,beta,years of parental lifespan per allele,,,parent
```
**Edges.** `effect_allele` G is rs4970836's allele and is checked against the proxy. `proxy_r2` is
empty because v2 calls these "unverified LD proxies" (§12). The LD population column has no v2 value
anywhere. The study's own `ancestry` (EUR) is the only candidate, so the column may be derivable or
unused.

### 10. An HLA allele as a `(gene, allele)` member, conditional on sex

**Exercises.** RM334 against the existing `allele_function.csv`, the closed `sex` condition, and the
tag-SNP fallback.

**Count.** 8 HLA alleles (M): 2 published (HLA-DRB1\*15:01, 41116190; HLA-B\*57:01, 41135092) and 6
from one DOI-only medRxiv preprint. 1 tag SNP (rs3135388) (M). Loci with a sex context: 4 of 32 (M).

```csv
# allele_function.csv: today's table, key (gene, allele); every other column optional
gene,allele
HLA-DRB1,*15:01
HLA-B,*57:01
```
```csv
# meta.csv
members,trait_efo_id,direction,conclusion,negatives,sex,tier,causal_conf,effector_conf,age_of_action,age_conf
allele:HLA-DRB1=*15:01,OBA_VT0005372,risk,"Men who carry HLA-DRB1*15:01 were less common among long-lived men…",,male,B,C4,,LATE,INFERRED
allele:HLA-B=*57:01,OBA_VT0005372,risk,"…",,,,C4,,,
```
```csv
# the tag-SNP fallback: the tag is a variants.csv row and the study names it
rsid,pmid,ancestry,phenotype_class,effect_allele,effect_size,effect_measure,stratum,stratum_level
rs3135388,41116190,EUR,EXTREME_SURVIVAL_CC,A,0.89,OR,,   # parents ≥95 vs 40–90: an extreme class on the parent's age
```
**Edges.**
- `allele_function.csv` plus meta-table rows hold the allele, its facts and its finding. The (gene,
  allele) key exists, and a `B*57:01`-shaped name passes `^\S+$`. What this route lacks against RM334:
  - the field-resolution statement and the grammar check (RM334's `gene*field:field`), which would
    have to live on `allele_function.csv` for HLA genes;
  - any citation on the allele itself (StudyRow names variants only).
- The tag-to-allele link (rs3135388 tags \*15:01 with some r² in EUR) is a proxy relation whose target
  is an allele, not a variant. RM331's columns point from variant to variant.
- `sex=male` here is the conclusion condition. The male-only OR 0.64 is a study stratum, but the study
  row above is the tag's UKB row, so the stratum sits on a different row from the finding it supports.

### 11. Preprint-only evidence after the DOI refusal

**Exercises.** RM336 (a DOI in `pmid` is refused) against `StudyRow.pmid` being required.

**Count.** 17 DOI-only studies (M), and 8 candidate rows with no PMID (M): the 6 HLA alleles, CGAS
rs200818241 and EYS rs75571981.

```csv
rsid,pmid,doi,phenotype_class,effect_size,effect_measure
,10.1101/2025.03.30.25324899,10.1101/2025.03.30.25324899,EXTREME_SURVIVAL_CC,0.74,OR   # refused by RM336
```
**Edge.** Once RM336 refuses this, a preprint with no PMID has **no legal study row**: `pmid` is
required and must contain a PMID. v2 tiers preprint-only findings as C (§4.1) and plans "`pmid` (or
`doi` for preprints)" (§6.3). RM263 maps a DOI to a PMID only where one exists, and the 1.0 doi-first
demotion is the real fix.

### 12. Model-organism evidence: the three candidate homes

**Exercises.** RM335's table against meta-table rows and against `StudyRow`.

**Count.** 77 rows over 40 human genes (M). 24 rows name no human variant (M), 17 have no PMID (M),
sex is mentioned on 10 and diet on 4 (I). Concordance is yes 19, no 3, unclear 55 (M).

```csv
# RM335 table (proposed)
gene,orthologue,species,model_type,sex,diet,lifespan_effect,concordance,pmid
PPARG,Pparg,Mus musculus,knock-in Pro12Ala,,high-fat,benefit lost on high-fat diet,nonmonotone,19117549
IGF1R,Igf1r,Mus musculus,heterozygous knockout,female,,+33% (female),concordant,
```
**Edges.**
- **Meta-table route.** Members can be variants, genotype rows, diplotype rows or (gene, allele), but
  not a bare gene. So the 24 gene-only rows (Igf1r+/−, GenAge entries) have no member.
  `species`/`model_type`/`diet` are not finding columns.
- **`allele_function.csv` route.** `(IGF1R, Igf1r+/-)` is a mouse genotype, not a human allele.
- **StudyRow route.** There is no `gene` column (RM47), and one stratum pair cannot carry both sex and
  diet.

### 13. Two strata on one estimate

**Exercises.** RM330's single `stratum` / `stratum_level` pair.

**Count.** FOXO3 rs2802292: "CAD protection only in hypertensive men" and "mortality in men with
cardiometabolic disease" (CHAMP, 41837379). GHR rs4130113: "pro-longevity in hypertensive men" (M,
read). 2 loci, 3 estimates (I). The H file carries 21 CONTEXT tokens over 32 loci: ancestry 6, sex 4,
UV 3, smoking 2 and one each for the rest (M).

```csv
rsid,pmid,ancestry,stratum,stratum_level,effect_measure,statistical_test
rs2802292,41837379,EUR,sex,male,NR,"men with hypertension/diabetes/angina"   # the second modifier has no column
```
**Edge.** One pair holds one modifier. "Hypertensive men" is two, so the second goes back into prose.

## Appendix 2: the examples in the final shape (second run)

### Reference examples, second run: longevitymap v2 in the reshaped 0.8 shape

Measured 2026-11-04 against `ROADMAP_0_8.md` at `0fb954f`, where the latest dated line under each item wins.
v2's data is just-dna-lite `docs/longevitymap_v2/` (requirements, `data/`, `evidence/`).

**Counts.** **M** means read off a column. **I** means a keyword or regex classification of free text, so
treat it as approximate.

**Columns that are gone.** Every row below is in the final shape only, so these never appear:
- `causal_conf` and `effector_conf`;
- `age_event`;
- diplotype `priority` and `actionability`;
- `effect_unit` on variants;
- the HLA table;
- `conclusion_lay` and `conclusion_concise`;
- a hand-written `proxy_r2` or LD population.

#### Conventions (illustrative; nothing below is decided spelling)

- **The meta-table** is written as `meta.csv`, with these columns: `members, trait_efo_id, role, direction,
  conclusion, negatives, sex, tier, age_of_action, age_conf, flags, pmid`.
- **Members** are joined by ` & `. Each member is spelled `table[col=value, …]`.
  - A member that names a table's full key is a **concrete row key**.
  - `variants[rsid=…]` alone is a **locus-level key**.
  - Anything else is a **selector**: conditions are AND-ed, and `=` on a list column means "contains".
- **Precedence** follows RM28: a concrete key wins over a locus key, which wins over a selector with more
  conditions, which wins over one with fewer.
- **Trait ids** are v2's own terms (`OBA_VT0005372`, `EFO_0007796`, `EFO_0009762`), plus `EFO_0001645`
  (CAD) and `MONDO_0004975` (AD). `TRAIT:<name>` marks a term still to be looked up.
- **Conclusions** are abbreviated with `…`.

**Dropped as trivial or decided:**
- Run 1's standalone "facts-only one-member row" is now just a concrete override, folded into case 1.
- "Two strata on one estimate" was decided as prose for its 2 loci (I).

---

#### 1. The legacy layer is one selector, and the rows that beat it

**Exercises:**
- the `flags=` list selector;
- precedence of a concrete key over a selector;
- a 2-condition selector against a 1-condition selector;
- an open `tier` scale.

**Count:**
- 528 legacy rsIDs replaced by 1 row (M).
- 12 seed rsIDs are also in v1 (M). 8 of them carry a seed tier and are not APOE proxies, so each needs a
  concrete row to escape tier D: rs429358, rs7412, rs1063192, rs2802292, rs1333049, rs2149954, rs9536314
  and rs5882.
- R-RARE-4 puts 18 ADARB1/ADARB2 v1 rsIDs at tier C (M). That takes 2 selector rows instead of 18
  concrete ones, but only if each one also names the legacy tag.

```yaml
# module_spec.yaml (excerpt): the scale is named once; values are open within it (X, A-, B- allowed)
tier_scale: longevitymap_v2
```
```csv
# meta.csv
members,trait_efo_id,role,direction,conclusion,negatives,sex,tier,age_of_action,age_conf,flags,pmid
variants[flags=legacy_longevitymap],,,,,,,D,,,,
variants[gene=ADARB1, flags=legacy_longevitymap],,,,,,,C,,,,
variants[gene=ADARB2, flags=legacy_longevitymap],,,,,,,C,,,,
variants[rsid=rs2802292],,,,,,,B,UNKNOWN,UNKNOWN,,
variants[rsid=rs10455872],,,,,,,A,MIDLIFE,DIRECT_WEAK,,
```
**Edges:**
- `variants[gene=ADARB1]` has 1 condition, and so does the legacy row. They cannot be ordered and they
  disagree (C against D), so the tier would be **withheld**. The author has to add the legacy condition to
  win. 18 rows (M).
- The tag selector matches v1's 1,022 genotype rows (M), and the compiler writes the tier onto each
  matched row. The manifest records the match count.
- Legacy rs429358 and rs7412 are `variants.csv` rows, so the tag makes them tier **D**, while the allele
  rows in case 2 are tier **A**. These are different subjects, so precedence never compares them. The
  report shows "not supported" for the SNP and "well established" for the allele unless the author also
  writes `variants[rsid=rs429358]` with tier A. 2 rsIDs (M).
- Two tag sets that disagree: v2 has **0** (I). `legacy` ∩ `preprint` is empty, and `legacy` ∩
  `replication_failed` both give D. One overlap that agrees: `category=legacy_candidate` (v2 §5.2) is the
  same 528-row set as `flags=legacy_longevitymap`, two spellings of one set.
- The tier rows above carry no C or E label. Those are computed from parquet inputs (case 9).

#### 2. APOE alleles: facts, flags and a citation; ε2/ε4 withheld

**Exercises:**
- the `allele_function.csv` (gene, allele) member;
- meta `flags` and `pmid`;
- diplotype `negatives` and `category`;
- withholding when two concrete keys from different tables match.

**Count:**
- 2 allele rows and 6 diplotypes (M).
- 1 diplotype (ε2/ε4) matches two allele rows that disagree on `age_conf` (M).
- APOE has 14 study links (M).
- APOE is the 1 locus whose `AP:`, NONADDITIVE and PROTECT tokens need meta `flags` (M, H file).

```csv
# allele_function.csv (key gene, allele; every other column empty)
gene,allele
APOE,ε2
APOE,ε4
```
```csv
# meta.csv
members,trait_efo_id,role,direction,conclusion,negatives,sex,tier,age_of_action,age_conf,flags,pmid
allele_function[gene=APOE, allele=ε4],,,,,,,A,LATE,DIRECT,ap:weak,30642433
allele_function[gene=APOE, allele=ε2],,,,,,,A,LATE,DIRECT_WEAK,protect:presence,31413261
```
```csv
# diplotypes.csv: RM322's two columns only
gene,haplotype_a,haplotype_b,trait_efo_id,direction,phenotype,conclusion,negatives,category
APOE,ε2,ε2,OBA_VT0005372,protective,APOE ε2/ε2,"You carry two copies of ε2…","Two copies of ε2 can raise rare blood-vessel problems…",brain_memory
APOE,ε2,ε4,OBA_VT0005372,risk,APOE ε2/ε4,"…",,brain_memory
APOE,ε3,ε4,MONDO_0004975,risk,APOE ε3/ε4 and Alzheimer's,"…",,brain_memory
```
**Edges:**
- A genome that is ε2/ε4 carries both alleles:
  - `tier` (A, A) and `age_of_action` (LATE, LATE) agree;
  - `age_conf` (DIRECT against DIRECT_WEAK) disagrees and is **withheld**.
- The author cannot settle it. A meta row keyed on the ε2/ε4 *diplotype* is also a concrete row key,
  and nothing ranks one table's concrete key above another's. The tie stands unless the precedence gains
  "a diplotype row over the allele rows it contains".
- The `pmid` on the allele rows lets ε4's finding cite directly.

#### 3. A combination with an existential selector: KL-VS × ε4 carriers

**Exercises:**
- a selector inside a combination ("any row of the set");
- "a combination replaces what it names";
- a meta `pmid` on a combination.

**Count:** 1 combination row, replacing run 1's 3 rows (M). 2 study rows from 1 PMID (M).

```csv
# meta.csv
members,trait_efo_id,role,direction,conclusion,negatives,sex,tier,age_of_action,age_conf,flags,pmid
"diplotypes[gene=KL, haplotype_a=KL-VS, haplotype_b=ref, trait_efo_id=MONDO_0004975] & diplotypes[gene=APOE, haplotype_b=ε4, trait_efo_id=MONDO_0004975]",MONDO_0004975,outcome,protective,"You carry ε4 and one copy of KL-VS; in ε4 carriers over 60, one KL-VS copy was linked to lower Alzheimer's risk…",,,C,,,protect:buffering,32282020
```
**Edges:**
- "ε4 carrier" is written as `haplotype_b=ε4`. It works only because pairs are canonicalised
  `a <= b` and ε4 sorts last, so it matches ε2/ε4, ε3/ε4 and ε4/ε4.
  - "ε2 carrier" works the same way, as `haplotype_a=ε2`.
  - "ε3 carrier" would need OR (ε2/ε3 on b, ε3/ε4 on a), which is out of bounds. v2 has no such case
    (0, M).
- The KL diplotype row must still exist with its own required `conclusion`.
- `protect:buffering` is derivable: a multi-member row exists. So that flag restates the shape.

#### 4. Per-trait rows: role, allele-bearing members, computed tradeoff

**Exercises:**
- the `role` column (outcome or mediator);
- the "allele-bearing member" rule;
- `tradeoff` computed by Kleene logic.

**Count:**
- 32 loci name a mediator (M); 9 of them write a chain such as "LDL -> CAD" (M).
- 15 of 32 loci carry both a benefit and a harm (I); about 134 per-trait items in total (I).
- 4 loci have no determined allele, so they get no per-trait row (M).

```csv
# meta.csv: allele C of rs3184504; carrier genotypes are rows (no OR), so each trait is 2 rows
members,trait_efo_id,role,direction,conclusion,negatives,sex,tier,age_of_action,age_conf,flags,pmid
variants[rsid=rs3184504, genotype=C/C],TRAIT:hypothyroidism,,protective,,,,,,,,
variants[rsid=rs3184504, genotype=C/T],TRAIT:hypothyroidism,,protective,,,,,,,,
variants[rsid=rs3184504, genotype=C/C],TRAIT:sepsis_mortality,,risk,,,,,,,,
variants[rsid=rs3184504, genotype=C/T],TRAIT:sepsis_mortality,,risk,,,,,,,,
variants[rsid=rs10455872, genotype=A/A],TRAIT:lipoprotein_a,mediator,protective,,,,,,,,
variants[rsid=rs10455872, genotype=A/A],EFO_0001645,mediator,protective,,,,,,,,
# derived: tradeoff(rs3184504 C carriers) = true; tradeoff(rs10455872) = false only if every trait's judgement is present
```
**Edges:**
- **No selector picks the carriers.** `effect_allele` is the same on all 3 genotype rows, and "genotype
  contains C" would need OR. With genotype members, each trait costs 2 rows (about 268, I).
- **The other reading costs 1 row per trait (about 134, I).** v2 §6.2 harmonises `effect_allele` per
  locus, and the seed has one lifespan allele per rsID with `allele_conflict` False on 228 of 228 (M). So a
  locus key `variants[rsid=rs3184504]` already bears an allele, provided the format requires `effect_allele`
  to be uniform across a locus's rows (no such rule today). That is the cheaper reading of "allele-bearing".
- **`role=outcome` is derivable only if the module declares its outcome-trait set once**, the way it names
  `tier_scale`. Nothing declares that set today; given one, `role=outcome` holds exactly when `trait_efo_id`
  is in it. Only `mediator` carries information: incidental pleiotropy (IL6R atopy, DEF8 vitiligo) is
  neither outcome nor mediator and is written with no role.
- **A chain like LDL → CAD** is two mediator rows with no order between them (9 loci, M).

#### 5. Two classes, one paper: Timmers 2020

**Exercises:** `phenotype_class` as part of the duplicate-citation narrowing; the derived outcome strip.

**Count:**
- 10 variants in PMID 32678081 (M).
- Outcome cells per lead, counting study rows (I): 8 leads have all 3, 17 have 2, 91 have 1, 29 have none,
  and 16 are mvAge only. The mvAge mapping is v2's to state in its README.

```csv
rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,p_value,sample_size,sample_unit,statistical_test
rs10455872,32678081,EXTREME_SURVIVAL_CC,A,0.124,log(OR),log-odds per allele,7e-03,,,longevity component of MANOVA
rs10455872,32678081,PARENTAL_LIFESPAN,A,0.076,beta,-ln HR per allele,9e-25,1012240,lives,parental lifespan component
rs10455872,32678081,HEALTHSPAN,A,0.057,beta,-ln HR per allele,1e-10,300447,individuals,healthspan component
```

#### 6. Same class, the analysis differs: Deelen percentiles, Pilling parent sex

**Exercises:**
- the duplicate-citation narrowing by stratum;
- `age_of` set to the parent inside an extreme class;
- a percentile threshold kept in `statistical_test`.

**Count:**
- Deelen has 3 variants with both a 90th- and a 99th-percentile row (M).
- Pilling has 24 rows (M): fathers 11, mothers 2, attained age 7, age at death 2, both parents in the top
  10% 2.

```csv
rsid,pmid,phenotype_class,effect_size,effect_measure,n_cases,sample_size,sample_unit,age_of,stratum,stratum_level,statistical_test
rs7412,31413261,EXTREME_SURVIVAL_CC,1.28,OR,11262,36745,individuals,participant,,,">=90th percentile vs <=60th"
rs7412,31413261,EXTREME_SURVIVAL_CC,1.47,OR,3484,28967,individuals,participant,,,">=99th percentile vs <=60th"
rs74444983,29227965,PARENTAL_LIFESPAN,-0.0143,beta,,389166,individuals,parent,parent_sex,father,"BOLT-LMM fathers_attained"
```
**Edge.** Father against mother is written twice: `age_of=parent` plus `stratum=parent_sex`. That
duplication is unchanged from run 1 (13 rows, M).

#### 7. Parental lives against participants

**Exercises:** `sample_unit`.

**Count:** of 22 parental studies, 4 count lives, 9 count participants and 9 state no N (I). 2 studies
outside the parental class count lives (I).

```csv
rsid,pmid,phenotype_class,sample_size,sample_unit
rs10455872,30642433,PARENTAL_LIFESPAN,1012240,lives
rs74444983,29227965,PARENTAL_LIFESPAN,389166,individuals
```

#### 8. Age bands with an open upper bound (no event column)

**Exercises:**
- `age_min`, `age_max` and `age_of`;
- the narrowing by age band.

**Count:**
- 72 rows: 24 loci × 3 bands (M).
- `age_conf` DIRECT ⇔ band-moderation q < 0.05 holds on 19 of 24 (M), so `age_conf` stays authored.

```csv
rsid,pmid,phenotype_class,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.1089,beta,log protection ratio per allele,40,60,parent
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.0778,beta,log protection ratio per allele,60,80,parent
rs10455872,30642433,PARENTAL_LIFESPAN,A,0.0530,beta,log protection ratio per allele,80,,parent
```

#### 9. Proxy-measured study: the author writes `proxy_rsid`, the enricher computes the LD pair

**Exercises:** `proxy_rsid`, and the machine-written LD table looked up in the study's ancestry.

**Count:**
- 68 `(rsid, pmid)` links rest on 58 non-lead seed rsIDs (I). Of the 68:
  - 64 have a single superpopulation, so a 1000G lookup is possible (62 EUR, 2 EAS);
  - 3 are mixed (trans-ethnic), so there is no single panel;
  - 1 is unmappable.
- 5 non-leads sit more than 500 kb from their lead (M). They are likely independent signals, and the
  computed r² would show that.
- 2 age-band proxies (M), both EUR.

```csv
# studies.csv (authored)
rsid,pmid,proxy_rsid,ancestry,effect_allele,effect_size,effect_measure,effect_unit,age_min,age_max,age_of
rs646776,30642433,rs4970836,EUR,G,0.2234,beta,years of parental lifespan per allele,,,parent
```
```csv
# the LD table (machine-written; illustrative columns; the r² cell is what the lookup fills)
lead_rsid,proxy_rsid,population,r2,ld_reference,release
rs646776,rs4970836,EUR,<computed>,<LD reference>,<release>
```
**Edges:**
- A study with mixed ancestry has no single panel. 3 links: withhold, or pick one panel; the rule is
  unstated.
- Ashkenazi studies map to EUR, because 1000G has no Ashkenazi panel: 12 candidate rows (M).

#### 10. HLA alleles via `allele_function.csv`, and the preprint ones that cannot cite

**Exercises:**
- the HLA grammar check on `allele_function.csv`;
- the meta `sex` condition and `pmid`;
- the hole: no `doi` on meta-table rows.

**Count:**
- 8 alleles (M). 2 are published (DRB1\*15:01, B\*57:01).
- 6 come from one DOI-only medRxiv preprint (10.1101/2025.03.30.25324899).

```csv
# allele_function.csv
gene,allele
HLA-DRB1,*15:01
HLA-B,*57:01
HLA-A,*02:01
```
```csv
# meta.csv
members,trait_efo_id,role,direction,conclusion,negatives,sex,tier,age_of_action,age_conf,flags,pmid
allele_function[gene=HLA-DRB1, allele=*15:01],OBA_VT0005372,outcome,risk,"Men who carry HLA-DRB1*15:01 were less common among long-lived men…",,male,B,LATE,INFERRED,,41116190
allele_function[gene=HLA-A, allele=*02:01],OBA_VT0005372,outcome,protective,"…",,,C,,,,NONE   # NONE needs a doi; meta rows have none
```
**Edge.** The meta `pmid` follows RM47's pattern, and like `MeasureBinRow.pmid` and
`PharmVariantRow.pmid` it has **no `doi` beside it**; only `StudyRow` carries `doi`. So `NONE` cannot be
used, and the 6 preprint alleles' findings cannot cite (M). The only fallback is a studies.csv row with
no subject, which cites the module, not the allele.

#### 11. Preprint evidence on studies.csv: `pmid=NONE`, `doi` mandatory

**Exercises:** the typed sentinel, and the DOI refusal kept.

**Count:**
- 17 DOI-only studies (M): 11 under prefix 10.64898, 4 under 10.1101, 2 under 10.21203.
- 8 DOI-only candidate rows (M). The 2 that land on `studies.csv`: CGAS rs200818241 and EYS rs75571981.

```csv
rsid,pmid,doi,phenotype_class,effect_size,effect_measure
rs75571981,NONE,10.21203/rs.3.rs-6869504/v1,EXTREME_SURVIVAL_CC,,NR
rs75571981,10.21203/rs.3.rs-6869504/v1,,EXTREME_SURVIVAL_CC,,NR    # refused: a DOI in pmid
```

#### 12. C and E computed from inputs; an override corrects an input, never a judgement

**Exercises:**
- the cut of `causal_conf` and `effector_conf`;
- the parquet inputs (RM239 posterior, RM236 consequence, RM333 L2G, RM238 coloc);
- `overrides.csv`.

**Count:** v2 has **no per-locus C or E label**, only the rubric (G synthesis). Compared with the 18
curated assessments (I):
- reading only longevity credible sets, computed C agrees on 14 of 18;
- reading any trait's sets, it agrees on 16 of 18. That choice is a README policy.
- The 2 residuals are judgements on true inputs:
  - rs2075650: the curator calls it a "tag of ε4" with PIP 1.0 for some trait;
  - rs16969968: the curator calls it "plausible causal (missense)" with max PIP 0.17.
- Coloc changes the E level on 22 of 67 rows with L2G (M), so RM238 earns its place.
- On the 10 curated rows that carry an L2G score, the L2G top gene equals the curated effector on 9 (M).
  The miss is rs61905747: CLDN25 0.35, which v2 calls ambiguous and labels ZW10/USP28.

```csv
# overrides.csv: correct a derived input (key table, subject, member, field)
table,subject,member,field,operation,value,reason
gwas_effects.csv,<association_id of the rs7412 credible set>,,<posterior column>,insert,0.81,"median PIP across 500 examined credible sets (Open Targets 26.09); no longevity set contains rs7412"
```
**Edges:**
- To force rs2075650 to C3, the author would have to write a false PIP. The rubric's output has no
  override row, so the curator's call stays prose (2 rsIDs, I).
- rs7412 needs `insert`, not `update`: no longevity set contains it, so there is no row to correct.

#### 13. Model-organism evidence (RM335, unchanged)

**Exercises:** the one table nothing else holds.

**Count:**
- 77 rows covering 40 genes (M).
- 24 rows name no human variant (M) and 17 have no PMID (M).
- Sex is mentioned on 10 rows and diet on 4 (I).
- Concordance is 19 yes, 3 no, 55 unclear (M).

```csv
gene,orthologue,species,model_type,sex,diet,lifespan_effect,concordance,pmid
PPARG,Pparg,Mus musculus,knock-in Pro12Ala,,high-fat,benefit lost on high-fat diet,nonmonotone,19117549
IGF1R,Igf1r,Mus musculus,heterozygous knockout,female,,+33% (female),concordant,
```
**Edge.** 17 rows have no PMID, and GenAge entries have none either. The table's citation cell then needs
the same `NONE`/`doi` rule, or a GenAge id.
