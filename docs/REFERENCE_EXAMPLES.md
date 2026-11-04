# Reference examples — worked module drafts

These are **hand-authored sketches** of how modules are expressed with the format's bricks (see
[ROADMAP.md](ROADMAP.md), [CHANGELOG.md](CHANGELOG.md)). They are **ideas and drafts for module
authors and consumers** — a picture of the intended shapes. The sections were first written against the
0.3/0.4 shapes, which are shipped and frozen; where a later release added a source, a check or a
drafting provider to a shape, the section says so in place, with the item that brought it. rsIDs /
coordinates / effect sizes are illustrative.

**Some examples are not sketches but real, compiled modules** — every directory under
[`reference_examples/`](../reference_examples), rebuilt by the commands in its own README. Read those
when you want the authored shape that actually passes the compiler rather than an illustration; the
sections below stay as the *shape* argument. Each README names **what building it broke**, which is the
point of having them: the module is the regression test and the README is the evidence. Highlights:
`pathogenic_clinvar/` (the SNP core from a real ClinVar snapshot), `pgx_slco1b1_simvastatin/` (the PGx
path — no `variants.csv`, and a `licensing.csv` recording that the module is not sellable),
`htt_repeat_expansion/` (the binning path, §7) and `fmr1_cgg_repeat/` (the cited bin boundary, RM47),
`mt_heteroplasmy/` (§4 — two variants in one gene, two tissues, and the key that had to widen for it)
and `mt_common_deletion/` (§4 — a `<DEL:4977>` symbolic allele through every tier, RM5),
`cyp2d6_structural/` (§6 — `copynumbers.csv` and `activity_phenotype.csv` on the gene that motivates
them), `hboc_palb2/` (the whole enricher pipeline on one module), `shox_par1/` + `par_boundary/`
(pseudoautosomal selection, RM32) and `grch37_build/` (§11 — the non-GRCh38 case). Do not maintain a count here; the
directory is the list, and `compiler/tests/test_reference_examples_roundtrip.py` sweeps all of them for
the Principle 7 fixed point by discovery rather than by a second inventory.

This doc is the **"conclusion" stage of the feedback → schema cycle** (see
[`USE_CASES.md`](USE_CASES.md) → *The feedback → schema cycle*): where a use case, once its blockers
are resolved into a settled shape, becomes *how to do it now, with these bricks*. For the
*is-it-reachable-and-what's-missing* analysis of the same use cases, read `USE_CASES.md` first.

**The 0.4 relational/quantitative tables in §2, §4–§8 are schema-validated** by
`just_dna_format.{binning,pgx,pgs}` (see `schema/tests/test_v04.py`) **and materialized to parquet by
the compiler** (every table kind, with lossless idempotent round-trip — shipped in 0.4, see
[CHANGELOG.md](CHANGELOG.md)). Every CSV row below round-trips through its Pydantic model.

**Conventions the sample settled:**
- **Modules compose from optional table kinds (one CSV = one concern).** The only always-present file
  is `module_spec.yaml`; every table below is optional. A SNP module is just `variants.csv`
  (+ `studies.csv`); a PGx module adds `haplotypes`/`allele_function`/`diplotypes`; a PharmGKB module
  adds `pharm_variants.csv`. A module **never** carries an empty `variants.csv` or a foreign domain's
  columns just to host one table — the SNP core stays minimal (see CLAUDE.md, the human-authorable
  gate).
- **Data-agnostic.** A module is a declarative lookup; it contains **no measurement**. The measured
  quantity (activity score, copy number, repeat count, heteroplasmy fraction) is supplied by the
  **consumer** at query time. The table never sees a sample.
- **Binning is uniform and inclusive.** Every quantity table shares one column vocabulary
  (`measure_kind, measure_min, measure_max, direction, clin_sig, phenotype, trait_efo_id, conclusion,
  unresolved`) plus its explicit key columns. Ranges are inclusive `[measure_min, measure_max]`:
  `min == max` is a *sharp* value, `min < max` a range, `measure_max` empty is open-ended. A row with
  `unresolved=true` is the sentinel a consumer selects when the measurement is absent (T1) — it
  carries no bounds, and is **never** the reference/lowest bin.

Contents: (1) simple SNV — needs **none** of the machinery; (2) APOE diplotype; (3) G6PD hemizygous;
(4) mitochondrial homoplasmic + heteroplasmy; (5) SMN1 copy-number dosage; (6) CYP2D6 star-alleles +
activity; (7) HTT repeat expansion; (8) PGS declaration; (9) PharmGKB drug response; (10) general
annotation axes on `VariantRow`.

---

## 1. Simple SNV module — needs none of the below

Most modules are just this: one row per genotype at a locus, on the existing `variants.csv`. The
0.3 column additions (`direction`, `stat_significance`, `effect_allele`, `trait_efo_id`, `clin_sig`)
are all optional; a simple module ignores diplotypes, copy number, and star-alleles entirely.

```csv
rsid,genotype,effect_allele,direction,stat_significance,gene,phenotype,trait_efo_id,conclusion
rs1801133,T/T,T,risk,significant,MTHFR,Homocysteine,EFO_0004518,"677 TT — reduced enzyme activity"
rs1801133,C/T,T,risk,suggestive,MTHFR,Homocysteine,EFO_0004518,"677 CT — intermediate"
rs1801133,C/C,C,neutral,not_significant,MTHFR,Homocysteine,EFO_0004518,"677 CC — normal"
```

---

## 2. APOE ε2/ε3/ε4 — diplotype (SV-free degenerate PGx case)

`haplotypes.csv` (`HaplotypeRow` — junction, one row per haplotype×variant):
```csv
haplotype_name,rsid,allele,gene
e2,rs429358,T,APOE
e2,rs7412,T,APOE
e3,rs429358,T,APOE
e3,rs7412,C,APOE
e4,rs429358,C,APOE
e4,rs7412,C,APOE
```
`diplotypes.csv` (`DiplotypeRow` — canonicalized `haplotype_a <= haplotype_b`, multiple rows per pair
for **pleiotropy**: ε2/ε2 protective for AD, risk for hyperlipoproteinemia).
**Contract (C3):** the pair is stored **lexicographically-sorted** on the star-string (so `*10 < *2`,
because `'1' < '2'`); a consumer MUST sort identically before lookup, or it silently misses the row —
do not sort star-alleles numerically.
```csv
gene,haplotype_a,haplotype_b,trait_efo_id,direction,clin_sig,phenotype,conclusion
APOE,e2,e2,EFO_0000249,protective,protective,Late-onset Alzheimer's,"ε2/ε2 — reduced LOAD risk"
APOE,e3,e4,EFO_0000249,risk,risk_factor,Late-onset Alzheimer's,"ε3/ε4 — ~3x risk"
APOE,e4,e4,EFO_0000249,risk,risk_factor,Late-onset Alzheimer's,"ε4/ε4 — ~12–15x risk"
APOE,e2,e2,EFO_0004749,risk,risk_factor,Type III hyperlipoproteinemia,"ε2/ε2 — dysbetalipoproteinemia predisposition"
```
Unphased `rs429358=C/T, rs7412=C/T` is formally ε4/ε2 *or* ε1/ε3 — the consumer's caller enumerates
pairs of *defined* haplotypes; ε1 undefined ⇒ resolves to ε4/ε2. No author logic. *(Per-study effect
axes — `effect_size`/`effect_measure`/`stat_significance` — are a round-2 extension; the sample
`DiplotypeRow` carries the orthogonal `direction`/`clin_sig` axes only.)*

---

## 3. G6PD — X-linked hemizygous (0.3 item 5b: single-allele genotype)

The author enumerates **both cardinalities**; the consumer matches the sample's allele count
(1 for a male's X, 2 for a female's). The single-allele row is what item 5b enables.
```csv
rsid,chrom,genotype,direction,clin_sig,gene,phenotype,trait_efo_id,conclusion
rs5030868,X,T,risk,pathogenic,G6PD,G6PD deficiency,MONDO_0009905,"Hemizygous deficient (1 X copy)"
rs5030868,X,T/T,risk,pathogenic,G6PD,G6PD deficiency,MONDO_0009905,"Homozygous deficient"
rs5030868,X,C/T,risk,pathogenic,G6PD,G6PD deficiency,MONDO_0009905,"Heterozygous — intermediate (mosaic)"
rs5030868,X,C/C,neutral,benign,G6PD,G6PD deficiency,MONDO_0009905,"Normal"
```
(The drug-trigger meaning — haemolysis on oxidative drugs — is the PGx `drug`/`response` layer.)

---

## 4. Mitochondrial — homoplasmic (0.3 item 5b) + heteroplasmy (0.4 `heteroplasmy.csv`)

Homoplasmic is reachable via a single-allele genotype on `variants.csv`; heteroplasmy is a
`HeteroplasmyRow` binning table. Its bins group on `(gene, reference_sequence, tissue, variant_key)`
plus `trait_efo_id` — the live list is `HeteroplasmyRow._KEY_FIELDS`, and `validate_bins` adds the trait.
Each component earns its place: the **reference accession** because rCRS/`NC_012920` vs legacy
`NC_001807` disagree and `genome_build` does not disambiguate; **tissue** because bins are
tissue-conditional (below); and **`variant_key`** because a gene hosts more than one variant and their
thresholds differ.

**That last one is why this section is worth reading against the built module rather than copied from.**
The illustration below carries one MT variant per gene, and the key was originally the gene — so a second
real MELAS variant (m.3271T>C, whose blood threshold is ~15% where m.3243A>G's is ~30%) landed in the same
group and `validate_bins` rejected the module as overlapping bins. The identity columns are **optional**,
so the rows below still validate and bin exactly as they always did (P3/P8); a table describing two
variants must fill them. `reference_examples/mt_heteroplasmy/` is that module — both variants, both
tissues — and its README names what building it broke.

Homoplasmic (`variants.csv`):
```csv
rsid,chrom,start,genotype,direction,clin_sig,gene,phenotype,trait_efo_id,conclusion
,MT,3243,G,risk,pathogenic,MT-TL1,MELAS,MONDO_0010789,"Homoplasmic m.3243A>G"
```
Heteroplasmy (`heteroplasmy.csv`, `measure_kind=allele_fraction`, bounds in `[0,1]`). `tissue` is
optional but load-bearing — **bins are tissue-conditional** (a blood fraction under-represents the
affected-tissue burden), so tissue is part of the key. `source_field=AF` binds the measure to the VCF
(e.g. Mutect2-mito `FORMAT/AF`). `reference_sequence` rejects the legacy `NC_001807` lineage (it yields
a confidently-wrong haplogroup); use `NC_012920.1` (rCRS).
```csv
gene,reference_sequence,tissue,source_field,measure_kind,measure_min,measure_max,direction,clin_sig,phenotype,trait_efo_id,conclusion,unresolved
MT-TL1,NC_012920.1,blood,AF,allele_fraction,0.8,1.0,risk,pathogenic,MELAS,MONDO_0010789,"high heteroplasmy (blood) — symptomatic",false
MT-TL1,NC_012920.1,blood,AF,allele_fraction,0.1,0.8,neutral,uncertain_significance,MELAS,MONDO_0010789,"low-level (blood) — usually subclinical",false
MT-TL1,NC_012920.1,blood,AF,allele_fraction,,,,,,,"caller artifact rejected — not called",true
```
A two-allele genotype on `MT` still raises the item-5b guardrail warning (MT is not diploid).

**Drafting the mtDNA calls, since 0.7 (RM171).** MITOMAP's curated tables are a cache lane, and the
draft source is *the increment over ClinVar*, not the photocopy: `just-dna-enricher mitomap build`,
then `mitomap miss` (which needs a ClinVar snapshot too and pins both), then
`draft-panel spec/ --source mitomap-miss` (`--gene` filters, never required). Every drafted row's
`genotype` and `conclusion` are stubs a human writes — MITOMAP's record is a claim about a literature
corpus, some of it heteroplasmic, so the compiler will not fill the allele the way it does for ClinVar
on chrMT — and MITOMAP's `[VUS*]` bracket is withheld rather than mapped. A symbolic mtDNA allele is
its own worked module: `reference_examples/mt_common_deletion/` carries `<DEL:4977>` (RM5).

---

## 5. SMN1 — whole-gene copy-number dosage (0.4 `copynumbers.csv`)

`CopyNumberRow`, keyed on `gene`. A sharp dosage is `measure_min == measure_max` (0 copies = `[0,0]`);
`3+` is `measure_min=3` with an empty `measure_max`. SMA severity depends on **SMN1 and SMN2** copy
number, so SMN2 rides in the explicit `modifier_gene`/`modifier_copy_number` columns (multicolumn
keying — never a packed tuple). Single-gene rows leave the modifier null.
```csv
gene,measure_kind,measure_min,measure_max,modifier_gene,modifier_copy_number,direction,clin_sig,phenotype,trait_efo_id,conclusion,unresolved
SMN1,copy_number,0,0,SMN2,3,risk,pathogenic,Spinal muscular atrophy,MONDO_0001516,"0 SMN1 / 3 SMN2 — milder",false
SMN1,copy_number,,,SMN2,3,,,Spinal muscular atrophy,MONDO_0001516,"SMN1 CN not resolved, 3 SMN2 — needs MLPA",true
SMN1,copy_number,0,0,SMN2,1,risk,pathogenic,Spinal muscular atrophy,MONDO_0001516,"0 SMN1 / 1 SMN2 — severe",false
SMN1,copy_number,,,SMN2,1,,,Spinal muscular atrophy,MONDO_0001516,"SMN1 CN not resolved, 1 SMN2 — needs MLPA",true
SMN1,copy_number,0,0,,,risk,pathogenic,Spinal muscular atrophy,MONDO_0001516,"0 copies, SMN2 unknown — affected, severity unstated",false
SMN1,copy_number,1,1,,,risk,pathogenic,Spinal muscular atrophy,MONDO_0001516,"1 copy — carrier",false
SMN1,copy_number,2,2,,,neutral,benign,Spinal muscular atrophy,MONDO_0001516,"2 copies — normal",false
SMN1,copy_number,3,,,,neutral,benign,Spinal muscular atrophy,MONDO_0001516,"3+ copies — normal",false
SMN1,copy_number,,,,,,,Spinal muscular atrophy,MONDO_0001516,"CN not resolved (seg-dup ~20×) — needs MLPA",true
```
Inert until a consumer supplies a CNV call. There is no `copy_number` column — a sharp value is
`measure_min == measure_max`.

**Why nine rows and not six: the modifier columns are part of the bin-group key.** `_KEY_FIELDS` is
`(gene, modifier_gene, effective_modifier_copy_number)` plus `trait_efo_id`, so this one CSV is **three
tilings**, not one — `(SMN1, SMN2, 3)`, `(SMN1, SMN2, 1)` and `(SMN1, null, null)` — and each needs its
own `unresolved` sentinel, plus a `[0,0]` bin in the null-modifier group for a homozygous deletion with
no SMN2 call. The earlier six-row version of this example had one sentinel for the null-modifier group
and none for the two SMN2 groups, and no `[0,0]` bin outside them: an SMN2=3 sample with no SMN1 call
matched nothing, and so did SMN1=0 with SMN2 unknown. **Nothing catches that** — the compile-path
sentinel rule is per-group but only refuses a *second* one, and the authoring-surface warning for a
missing sentinel is table-level, so a single sentinel anywhere in the file satisfies it. Verified: the
nine rows above group into three, each with a sentinel, and `validate_bins` returns no warnings.

**`modifier_copy_number`, not `modifier_cn` (RM55, 0.6).** The integer column is deprecated and goes
at 1.0; the float one holds the non-integer dosages VCF 4.4 §7.2 allows. Setting both is an error.
Everything reads `CopyNumberRow.effective_modifier_copy_number`, and the group key is that value, so
the two spellings never split a group.

This table tiles as a **grid**, which is `copy_number`'s default and correct for a caller that reports
whole copies. A caller reporting a **segment mean** does not: write `measure_tiling: continuous` on
every row of the group and let the bounds touch (`[0,1.5] [1.5,2.5] [2.5,]`), or the fractional value
matches no bin. A fractional *bound* switches the group by itself and says so; a fractional
*modifier dosage* does not, because the modifier is a key column — it says which table you are in,
not where a point sits on the axis being tiled. See [SCHEMAS.md](SCHEMAS.md) for the per-kind
defaults.

---

## 6. CYP2D6 — star-alleles + activity score (the hard PGx case)

The star-string is the **canonical allele-unit identity** (stored verbatim); `copy_number`/`sv_type`/
`hybrid_orientation` are optional parsed conveniences of the *cis* allele-unit. Phenotype is computed
by the **consumer** as `activity_score = Σ activity(allele_i) × copies_i` over the two phased
allele-units, then binned.

`allele_function.csv` (`AlleleFunctionRow` — allele-unit → activity value + CPIC function category):
```csv
gene,allele,activity_value,function_status,suballele,copy_number,sv_type,hybrid_orientation
CYP2D6,*1,1.0,normal_function,,,,
CYP2D6,*2,1.0,normal_function,,,,
CYP2D6,*4,0.0,no_function,,,,
CYP2D6,*4.001,0.0,no_function,4.001,,,
CYP2D6,*5,0.0,no_function,,,deletion,
CYP2D6,*10,0.25,decreased_function,,,,
CYP2D6,*1x2,2.0,increased_function,,2,duplication,
CYP2D6,*36+*10,0.25,decreased_function,,,,*36+*10
```
`activity_phenotype.csv` (`ActivityPhenotypeRow` — per-gene binning; DATA, editable by consensus, so
the 2019 CPIC threshold shift is a data edit, not a code change):
```csv
gene,measure_kind,measure_min,measure_max,direction,clin_sig,phenotype,trait_efo_id,conclusion,unresolved
CYP2D6,activity_score,0,0,,,Poor Metabolizer,,"AS 0 — PM",false
CYP2D6,activity_score,0.25,1.0,,,Intermediate Metabolizer,,"AS 0.25–1 — IM",false
CYP2D6,activity_score,1.25,2.25,,,Normal Metabolizer,,"AS 1.25–2.25 — NM",false
CYP2D6,activity_score,2.5,,,,Ultrarapid Metabolizer,,"AS ≥2.5 — UM",false
CYP2D6,activity_score,,,,,,,"no diplotype resolved (e.g. Cyrius Genotype=None) — unresolved, NOT Normal",true
```
Why a consumer (star-allele caller: Aldy/Cyrius/PharmCAT) is required: **copy number attaches to a
specific cis allele**, so `*2x2/*4` (AS 2 → NM) ≠ `*2/*4x2` (AS 1 → IM) — same variants and total
copy number, different phenotype. The format supplies the tables; the caller supplies the phased
diplotype + CN/SV. The `unresolved` row is the safety property: no diplotype ⇒ *unresolved*, never
"Normal Metabolizer".

---

## 7. HTT — repeat expansion (0.4 `repeat_alleles.csv`)

> **Built for real** at `reference_examples/htt_repeat_expansion/` — the sketch below is the shape; that
> directory is a module that compiles, verifies and round-trips to a fixed-point digest.

`RepeatAlleleRow`, keyed on `(gene, repeat_unit)` — the motif is part of the identity (T3): a repeat
count is only comparable within its motif definition. The count is a **consumer** call
(ExpansionHunter / adVNTR / a span genotyper) that must state the motif it counted. `source_field=REPCN`
binds the measure to an ExpansionHunter VCF (`INFO/RU` → `repeat_unit`, `FORMAT/REPCN` → the count) —
consumable with zero glue. **Author the reference (`≤26 normal`) bin** so every count hits exactly one
bin; `validate_bins()` rejects overlaps and warns on interior gaps.

**A catalogue stands behind the bands since 0.7 (RM165).** `just-dna-enricher strchive build
--release v2.26.0` cuts STRchive into a cache lane; `check-repeat-bands spec/` compares an authored
band table against its `benign_*` / `intermediate_*` / `pathogenic_*` columns and **reports, never
repairs** — the catalogue's `pathogenic_max` (250 for HTT) is reported as its own finding and never
written, because an upper bound on pathogenicity is not a claim this table makes. STRchive reproduces
this module's first two bands (`benign 6–26`, `intermediate 27–35`) independently. It also shows what a
catalogue cannot decide: for `reference_examples/fmr1_cgg_repeat/` it publishes one
`intermediate 45–200` where the module splits `45–54` / `55–200` at the premutation threshold — a
boundary the catalogue does not have, so the check reports the disagreement and the author keeps the
split. `draft-repeats spec/ --gene HTT` drafts the identity row (`gene`, `repeat_unit`, coordinates)
and leaves every band to the author.
```csv
gene,repeat_unit,source_field,measure_kind,measure_min,measure_max,direction,clin_sig,phenotype,trait_efo_id,conclusion,unresolved
HTT,CAG,REPCN,repeat_count,40,,risk,pathogenic,Huntington disease (full penetrance),MONDO_0007739,"≥40 CAG — fully penetrant",false
HTT,CAG,REPCN,repeat_count,36,39,risk,pathogenic,Huntington disease (reduced penetrance),MONDO_0007739,"36–39 CAG — reduced penetrance",false
HTT,CAG,REPCN,repeat_count,27,35,neutral,uncertain_significance,Intermediate allele,MONDO_0007739,"27–35 CAG — intermediate",false
HTT,CAG,REPCN,repeat_count,6,26,neutral,benign,Normal,MONDO_0007739,"≤26 CAG — normal",false
HTT,CAG,REPCN,repeat_count,,,,,,,"repeat not spanned on short reads (CI) — unresolved",true
```
Notes: **`repeat_unit` is free-form** (large composite VNTR motifs like DRD4 exon-3 ~48 bp and DAT1
~40 bp are real, not `CAG`-style trinucleotides — warn, never reject, on non-`[ACGTN]`). Bounds are
`float` because **half-repeats are real** (MAOA-uVNTR 3.5R). Forensic STR **microvariant** notation
(`TH01 9.3` = "9 repeats + 3 bases", not decimal 9.3) is an allele-*name* convention, not a binning
bound — for pathogenic-threshold loci (HTT) it never matters; for forensic STRs, carry the exact
allele string in the reserved motif-path escape hatch, not the float bound. **5-HTTLPR does not belong
here.** It is a biallelic **S/L structural indel** (a ~43 bp insertion), not a repeat *count*. It was
the motivating case for **RM5 (symbolic alleles)**, which shipped in 0.6 with VCF's five closed
first-level types and the length inside the token (`<DEL:1500>`, `<CNV:TR:30>`; worked in
`reference_examples/mt_common_deletion/`) — and the case itself dissolved on the way: 5-HTTLPR is a
plain indel whose `ref`/`alts` state the two alleles directly, so `S`/`L` are names for sequences
`variants.csv` already carries. (It is usually read phased with `rs25531`, so it is really a
mini-diplotype.) What stays unexpressible after RM5 is deliberate: CPIC's IUPAC ambiguity codes.
The complex-VNTR motif-path form (DAT1 `A-A-B-C-D-…`) is reserved as the home for the sanctioned
declarative-grammar escape hatch (a regex over an allele string) if a plain count proves too coarse.

---

## 8. PGS — polygenic score declaration (0.4 `pgs.csv`)

`PgsRow` — a **manifest of PGS Catalog IDs, not authored weights** (a declared interface, like
`GenePanelSpec`, not a binning table). The ancestry-validity fields are the anti-misuse guardrail: a
consumer refuses or caveats an out-of-ancestry application instead of silently miscalibrating.
```csv
pgs_id,trait_efo_id,note,group,training_ancestry,training_cohort,match_rate_floor,research_tier
PGS000135,EFO_0000692,"Schizophrenia (EUR-derived)",psychiatric,EUR,,0.8,research_only
PGS000765,MONDO_0005010,"Coronary artery disease",cardiometabolic,EUR,"UK Biobank NW-EUR",0.8,research_only
```
`research_tier=research_only` pins as *data* that a PRS is a Z/percentile *within a matched reference
distribution*, never an ancestry-calibrated absolute risk; `training_ancestry` (superpop floor) +
optional `training_cohort` (sub-superpop precision) let a consumer withhold or caveat the score
off-population; **`match_rate_floor`** is the author-set variant-match floor below which the score is
invalid. The *observed* per-sample match rate is a measurement — it lives consumer-side, never in the
module (the data-agnostic north star).

**The Catalog is asked about the row since 0.7 (RM163).** `just-dna-enricher check-identifiers spec/`
now carries a PGS leg (`--pgs/--no-pgs`): `pgs_accession_currency` asks whether each `pgs_id` still
names a score, and `pgs_metadata_agreement` asks whether `training_ancestry` / `training_cohort`
still match the record's `ancestry_distribution` / `samples_training` — two records, because they
are two questions. The leg writes the `sources.csv` row for the Catalog with `PGS_TERMS` as a
per-score licence floor, and `enrich --verify-datasets` can probe the Catalog's release the way it
probes ClinVar's. A drift finding here cannot be silenced through `overrides.csv`, because the
overlay reaches derived tables and `pgs.csv` is authored: the author edits the row.

---

## 9. PharmGKB drug response (item 9) — a distinct table, not columns on `VariantRow`

Drug-response annotation maps a variant/diplotype → a **drug** → a **response** + a PharmGKB
**evidence level** (`1A`…`4`) — a different axis from a risk weight. It gets its **own** rowtype so a
SNP author's `variants.csv` never grows drug columns (one CSV = one concern).

Single-variant PharmGKB (`pharm_variants.csv`, `PharmVariantRow` — VKORC1 → warfarin):
```csv
rsid,gene,drug,response,evidence_level,trait_efo_id,conclusion
rs9923231,VKORC1,warfarin,"reduced dose requirement",1A,,"−1639 A — lower warfarin dose"
rs1799853,CYP2C9,warfarin,"reduced clearance",1A,,"*2 — lower warfarin dose"
```
Diplotype-keyed PharmGKB rides on `DiplotypeRow`'s optional `drug`/`response`/`evidence_level` (it is
already a PGx-domain table a SNP author never opens):
```csv
gene,haplotype_a,haplotype_b,trait_efo_id,phenotype,drug,response,evidence_level,conclusion
CYP2D6,*1,*4,,Intermediate Metabolizer,codeine,"reduced analgesia",1A,"*1/*4 — impaired codeine activation"
```
A PharmGKB module carries `pharm_variants.csv` (+ the diplotype tables if star-allele) and **no**
`variants.csv`.

Since 0.7 (RM70) both `pharm_variants.csv` and `haplotypes.csv` also take **`requires_callable`**,
the tri-state flag `variants.csv` has carried since 0.4 — they are the PGx tables that name a locus,
so the claim is about a position the row states. It is what lets a star-allele module write down the
assumption its sources make and state only in prose, that a position which was not called is
reference. On a genotype-keyed row it is sharper still: the reference-homozygote row is unmatchable
from a variant-only callset, since absence of an ALT record is not evidence of that call.
```csv
rsid,gene,genotype,drug,evidence_level,conclusion,requires_callable
rs9923231,VKORC1,C/C,warfarin,1B,"reference homozygote — usual dose",true
rs9923231,VKORC1,C/T,warfarin,1B,"−1639 A — lower warfarin dose",false
```
`callable_from` does **not** travel with it and stays on `variants.csv`; `diplotypes.csv` takes
neither, because it names a star-allele pair rather than a locus and the claim belongs on the
haplotype rows that define the pair. `reference_examples/cyp2c9_warfarin_grch37` populates all three
states across its two tables, and its README says why each row got the value it did.

Since 0.7 (RM132) the table also takes **`pmid`** — the citation for *this row's* claim. It is the
column `studies.csv` cannot supply: a study row keys on `(variant_key, pmid)` and attaches to the whole
variant, while these rows key on drug, genotype and category as well, so one study row would ground
every drug and genotype recorded for that variant at once. Write it per row, and only where the paper
really is about that row — the toxicity evidence for a variant is usually not the efficacy evidence:
```csv
rsid,gene,genotype,drug,phenotype_category,evidence_level,conclusion,pmid
rs4149056,SLCO1B1,C/C,simvastatin,Toxicity,1A,"higher myopathy risk",18650507
rs4149056,SLCO1B1,C/C,simvastatin,Efficacy,3,"decreased response; conflicting evidence",
```
`evidence_level` and `pmid` are separate axes and both are worth writing: one is somebody else's
grading of the evidence, the other points at it. **`provenance_quote` does not travel here** — the row
cites, and `studies.csv`/`literature.csv` describe. The enricher's literature pass reads this site
exactly as it reads `studies.csv`, so a citation written here is checked for existence and identifiers
the same way, and a module whose only citations are pharm pointers is enriched rather than refused.

Two more checks reach this table since 0.7. **Regulator drug labels (RM166)**: `just-dna-enricher
clinpgx build-labels --use non-commercial` cuts ClinPGx's second archive, and `clinpgx check-labels
spec/` compares a `(gene[, allele], drug)` claim against the *Testing Level* five regulators publish
(FDA, Health Canada, EMA, Swissmedic, PMDA) — at the star-allele tier where the row has one and the
gene tier otherwise, reporting and never escalating under `strict`. **Literature coverage (RM167)**:
`just-dna-enricher litvar coverage spec/` asks LitVar2 which papers name each of the module's
alleles and records the answer *with the tier that answered* — allele-resolved, position-only or
absent — as a `literature_coverage` attestation, writing no row; a position-level answer never
stands in for an allele-level one.

---

## 9b. HFE — a gene panel drafted from ClinVar, with the zygosity left to a curator

Compiled example: [`reference_examples/hfe_hemochromatosis/`](../reference_examples/hfe_hemochromatosis/). Since 0.6 it is also the corpus's
demonstration of **RM90/RM92**: it carries 195 real `gwas_effects.csv` rows and a `weighting:` block.
Its README records the two bugs the GWAS pass hit here — a 404 read as an outage rather than as the
Catalog's empty answer, and a `pvalue: 0.0` underflow discarding whole associations — and the
measurement that motivates declaring a weight scale at all: 186 associations for one variant, 62
traits, 12 distinct effect units (three of them spellings of one), 42 rows naming no effect allele.
The first module authored end-to-end with the 0.5 authoring surface — `scaffold` → `draft-panel` →
curate → `enrich` → `compile` — and the one that shows where the tooling stops.

`draft-panel` wrote 12 variant rows and 33 study rows and then refused to finish, because
`VariantRow.genotype` is required and **ClinVar publishes alleles, not genotypes**. Whether carrying
a pathogenic HFE allele once is informative follows from the condition's inheritance mode, not from
the allele, so every drafted row arrived carrying `vocab.TEMPLATE_PLACEHOLDER` and nothing compiled
until a human replaced it. The curation rule is one line — haemochromatosis type 1 is autosomal
recessive, so the informative call is homozygous — and it is stated in the example's README rather
than buried in the rows.

The thirteenth row is the argument for the whole design. `rs1800562` (C282Y) appears twice:

| genotype | `clin_sig` | `state` | meaning |
|---|---|---|---|
| `A/A` | `pathogenic` | `risk` | two pathogenic alleles — the genotype the disease is described for |
| `A/G` | `pathogenic` | `neutral` | one pathogenic allele: a carrier |

Same variant, same ClinVar call, opposite clinical meaning — `clin_sig` describes the **allele**,
`state`/`direction` describe the **finding for that genotype** (Principle 5's orthogonal axes doing
real work). Any provider that derived a genotype from an alt would have picked one of these rows and
been wrong half the time.

Two things drafting a *real* panel taught the provider, both fixed there rather than papered over
here: an rsID can name two alleles (`rs773443949` is both `G>A` and `G>T`, so those rows are carried
by full coordinate instead), and a study row must carry the identity its variant row got, or the
compiler's orphan check fires. Grounding evidence comes from ClinVar's own literature links, ingested
with `just-dna-enricher clinvar citations` — without it a drafted panel could not compile at all,
since `studies.csv` is mandatory and the VCF carries no PMIDs. That table now **travels with the
published snapshot**, so a provisioned cache can ground a panel too; before, only someone who built the
snapshot themselves could, which made a downloaded one quietly unable to do this.

## 2b. APOE ε2/ε3/ε4 — compiled, and the meta-conclusion feasibility probe

Compiled example: [`reference_examples/apoe_epsilon/`](../reference_examples/apoe_epsilon/). §2 above
described the shape; this is the built module, and it exists to settle a design question with
evidence: **does pairing two annotations need new machinery?**

APOE is the sharpest test available — the ε haplotypes are defined by *two* SNPs together
(rs429358 19:44908684 T>C, rs7412 19:44908822 C>T), and CONSTITUTION Principle 1's example of the
predicate escape hatch is literally the ε4 condition, `rs429358==C AND rs7412==C`. It needs no
predicate. `HaplotypeRow` is a junction table — one row per (haplotype × defining variant) — so ε4 is
two rows, ε2 is two rows, and `diplotypes.csv` carries the six pairs and their conclusions.
**Same-strand co-location is what a haplotype table already is.**

Two details worth copying. ε3 carries the *reference* allele at both sites and is written out anyway:
unlike a star-allele `*1`, defined by the absence of variants, ε3 is a real named haplotype whose
defining alleles happen to be reference. And ε2/ε4 declares `direction=unknown` rather than averaging
two opposing alleles into a number nobody measured.

The probe also found a defect: `AlleleFunctionRow.allele` demands a leading `*` while the other two
PGx tables accept any name, so `e4` is legal in two tables and illegal in the third (RM30). APOE is
not blocked — an ε allele has no CPIC activity value, so the module carries no allele-function table
— but a non-star haplotype gene could never carry one.

## 2c. HFE C282Y/H63D — cis, trans, and what a table cannot say

Compiled example: [`reference_examples/hfe_compound_het/`](../reference_examples/hfe_compound_het/).
The companion probe to §2b, aimed at the half APOE left open. **Compound heterozygosity — the same two
alleles meaning opposite things depending on which chromosome each sits on — was the case that most
justified RM28's predicate grammar.** It needs none either.

A **diplotype is already a statement about two homologs.** `haplotypes.csv` says which alleles ride
together on one chromosome (§2b's finding) and `diplotypes.csv` pairs two of them, which is exactly
what "in trans" means. So four haplotypes over two real HFE variants —

| haplotype | rs1800562 (6:26092913 G>·) | rs1799945 (6:26090951 C>·) |
|---|---|---|
| `wt` | G | C |
| `C282Y` | **A** | C |
| `H63D` | G | **G** |
| `C282Y-H63D` | **A** | **G** |

— give `C282Y`/`H63D` as the **trans** compound heterozygote (no wild-type protein from either copy,
an at-risk genotype) and `C282Y-H63D`/`wt` as the **cis** case (one intact copy remains, a carrier).
Two rows, no grammar, and the relational notion the proposal was going to add is what a diplotype pair
*is*. Copy §2b's habit again: `wt` writes out its reference alleles rather than being implicit.

**What building it surfaced is the useful part.** Nothing said those two rows are indistinguishable
without phase — identical unphased genotype, opposite conclusions, and nearly all consumer data is
unphased. Silently reporting the first manufactures a finding; silently reporting the second
suppresses one. It is derivable from the two tables, so it became a compiler warning
(`_cross_validate_phase_ambiguity`) rather than a `requires_phase` column an author would have to keep
in sync by hand. Compiling this module emits exactly one, and the other six rows are clean.

The conclusions are deliberately hedged — HFE penetrance is incomplete and heavily modified by sex,
age, alcohol and blood loss — and no row claims secondary-findings reportability, because ACMG SF
v3.3 (the workbook `acmg build` reads; v3.2 is what NCBI's page still serves) scopes HFE to
*"c.845G>A; p.C282Y homozygotes only"*, narrower than the gene and narrower than this module.

## 9c. CYP2C19 — star alleles drafted from CPIC, curated by removal

Compiled example: [`reference_examples/cyp2c19_star_alleles/`](../reference_examples/cyp2c19_star_alleles/).
The PGx counterpart to the HFE panel, and instructive because it fails the *opposite* way. CPIC
publishes every column the star-allele models require, so `draft --gene CYP2C19` produced 811 rows
with no placeholders that validated immediately. The curator's job was not to fill a hole but to
decide what to take out — and to notice what the source never had.

What came out: `*36`, `*37` and `*42` were paired across 71 diplotype rows (two declared
`no_function`) while `haplotypes.csv` defined none of them. A star-allele caller can never emit an
allele nothing defines, so those rows could never match. That is a cross-table redundancy settleable
without any reference, so `_cross_validate_haplotype_definitions` now warns about it — as a warning,
and only when `haplotypes.csv` is present, because a module leaning on an external caller's
definitions is legitimate.

What CPIC could not express, reported rather than coerced: IUPAC ambiguity codes on one defining
variant each of `*2`/`*4`/`*35` (the alleles survive — they have other defining variants); `n/a`
activity scores, which mean *not scored* rather than a bound; and no chromosome anywhere, so a
defining variant is identified by rsID or not at all.

What is deliberately absent: **drugs**. `DiplotypeRow.drug`, `evidence_level` and
`recommendation_strength` are all empty. The module answers genotype → metabolizer phenotype and
stops, because CPIC's prescribing recommendations live in a resource the provider does not read and
inventing them would be worse than silence.

## 10. General annotation axes on `VariantRow` (optional, sparse)

Three optional refinements apply to *any* variant finding, so they live on `VariantRow` (not a domain
table); a plain SNP row omits them entirely.
```csv
rsid,genotype,gene,clin_sig,requires_callable,acmg_sf,actionability,conclusion
rs80357906,A/AT,BRCA1,pathogenic,true,true,preventable,"BRCA1 frameshift — HBOC; risk-reducing options"
```
- `requires_callable=true` — the *absence* of this variant is the informative call; a consumer lacking
  callability data must withhold the "no pathogenic variant" reassurance, never assert it.
- `acmg_sf=true` — the gene is on the ACMG secondary-findings list.
- `actionability=preventable` — an `ACTIONABILITY_SEED` value a consumer's return-of-results policy may
  read; the format never decides disclosure.

---

## 11. A module on GRCh37 — what "the key names its build" costs

Built for real as [`reference_examples/grch37_build/`](../reference_examples/grch37_build). Every other
example is GRCh38, which is exactly why this one earns a section: a uniform corpus cannot tell "reads the
module's build" apart from "writes GRCh38", and for one release three separate code paths were doing the
second while looking like the first.

Authoring is unremarkable — coordinates, not rsIDs, because an rsID is only resolvable against GRCh38:

```csv
chrom,start,ref,alts,genotype,state,conclusion,gene,clin_sig
6,26093141,G,A,A/A,risk,C282Y homozygote,HFE,pathogenic
6,26091179,C,G,G/G,risk,H63D homozygote,HFE,uncertain_significance
```

with `genome_build: GRCh37` in `module_spec.yaml`. HFE C282Y is 6:26,093,141 here and 6:26,092,913 on
GRCh38 — a 228 bp offset, so either number is a real place and neither is a place at the other's
coordinate.

**What the tools do, and why each is the honest answer:**

- `variant_key` is `6:26093141:G:A`, a **coordinate** key, not a `ga4gh:VA.…`. A VA addresses its
  sequence by refget accession and there is one refget table (GRCh38, RM15), so minting here would
  either need a table that does not exist or produce a GRCh38 identity for a GRCh37 base. The compiler
  says so once, counted: *"GA4GH VRS allele identity is GRCh38-only (RM15), so 3 variant(s) are keyed by
  coordinate instead."*
- **Resolution is skipped, not attempted.** The compiler warns that it is GRCh38-bound; the enricher
  resolves nothing and — since no link ran — records **no row at all** rather than a `not_found` one.
  `not_found` means "the source was asked and does not have it", and the source was never asked.
  (`VALID_RESOLUTION_STATUS` has no `unchecked` member to write instead, and adding one to describe a
  row carrying no fact is worse than writing no row.)
- **Authored coordinates are still transcribed** into `resolution.csv`, under `GRCh37`. What the author
  wrote is not a lookup result, so refusing to record it would lose data — while recording a *fetched*
  GRCh38 coordinate under a GRCh37 label would invent it.
- `compile → reverse → compile` is a fixed point on `artifact.digest`, `content_signature` **and**
  `resolution_signature`, and the reversed `module_spec.yaml` still says `GRCh37`.

**This is not multi-build support.** RM15 stays open: one refget table, coordinates untagged by build,
cross-build annotatability unrecorded. What ships is the narrower and more basic guarantee — the tools
**state which build they are working in and never quietly change it**. A coordinate key is
build-relative, so a GRCh37 module's keys will not join against a GRCh38 module's; that is a true fact
about coordinates, and the warning says it rather than hiding it behind an id that looks portable.

## 12. Longevity GWAS evidence, per analysis — the 0.8 `StudyRow` columns

Built for real as [`reference_examples/longevity_studies/`](../reference_examples/longevity_studies), from the
longevitymap v2 shape audit's candidates 5–9, 11 and 13 (PROPOSAL_0_8_PT2 §6), rebuilt from the papers. Five
loci and thirteen `studies.csv` rows. A row says which outcome it measured, how many were analysed and in which
unit, over which age band and whose age, within which stratum, in which superpopulation, and on which variant:

```csv
rsid,pmid,doi,proxy_rsid,phenotype_class,effect_allele,effect_size,effect_measure,sample_size,sample_unit,n_cases,age_min,age_max,age_of,stratum,stratum_level,ancestry
rs10455872,32678081,,,HEALTHSPAN,A,0.057,beta,300477,individuals,,,,,,,EUR
rs10455872,32678081,,,PARENTAL_LIFESPAN,A,0.076,beta,1012240,lives,,,,,,,EUR
rs10455872,30642433,,,PARENTAL_LIFESPAN,,0.0722,beta,272204,lives,,60,70,parent,parent_sex,father,EUR
rs429358,31413261,,,EXTREME_SURVIVAL_CC,C,0.60,OR,36745,individuals,11262,,,,,,EUR
rs646776,30642433,,rs4970836,PARENTAL_LIFESPAN,G,0.2234,beta,1012240,lives,,40,,parent,,,EUR
rs75571981,NONE,10.21203/rs.3.rs-6869504/v1,,EXTREME_SURVIVAL_CC,,,,8270,individuals,964,,,,,,EAS
```

One paper's rows are told apart by `phenotype_class`, by the band or by the stratum, each only when both rows
state it and the values differ. Deelen's ≥90th and ≥99th percentile analyses share a class, so only
`statistical_test` separates them: a percentile threshold has no typed home. The README names what the build
broke: reverse drops the LD proxy's `resolution.csv` row (RM331); Timmers 2019 states two different effect
alleles for one estimate, so its band rows withhold `effect_allele`; the audit's age bands were v2's pooling,
not the paper's; and an r² cannot say which lead allele a proxy allele tags.

## 13. HLA alleles — `allele_function.csv` items on `meta.csv`, by sex and by DOI

Built for real as [`reference_examples/hla_alleles/`](../reference_examples/hla_alleles) (audit candidate 10).
An HLA allele is an `allele_function.csv` item under RM334's grammar, and its finding is a `meta.csv` row:

```csv
members,trait_efo_id,direction,sex,pmid,doi
"allele_function[gene=HLA-DRB1, allele=*15:01]",OBA_VT0005372,risk,male,41116190,10.1186/s13073-025-01554-1
"allele_function[gene=HLA-DRB1, allele=*15:01]",OBA_VT0005372,,female,41116190,10.1186/s13073-025-01554-1
"allele_function[gene=HLA-A, allele=*02:01]",OBA_VT0005372,risk,,NONE,10.1101/2025.03.30.25324899
```

`sex` is part of the key, so a male finding and its female counterpart are two statements. A preprint allele
cites by `pmid=NONE` plus `doi`, which closes the hole the audit's second run left open. Still open: an
allele's odds ratio has no numeric home (a study row names a variant or nothing), and a tag SNP standing for
an allele has no column (RM331's proxy points from variant to variant).

## 14. Model-organism lifespan evidence — `model_organisms.csv` beside a lead table

Built for real as [`reference_examples/model_organisms/`](../reference_examples/model_organisms) (audit
candidate 12/13, RM335). The table is annotation only and is not a lead table, so the module also carries
`variants.csv` (PPARG Pro12Ala for type 2 diabetes):

```csv
gene,orthologue,species,model_type,sex,diet,lifespan_effect,concordance,pmid
PPARG,Pparg,Mus musculus,knock-in Pro12Ala (Ala/Ala),,chow,Ala/Ala mice lived longer; the abstract gives no figure,,19117549
IGF1R,Igf1r,Mus musculus,heterozygous knockout (Igf1r+/-),female,,+33% against wild-type females (P < 0.001),concordant,12483226
IGF1R,Igf1r,Mus musculus,heterozygous knockout (Igf1r+/-),male,,+16% against wild-type males (not significant),,12483226
```

One experiment in two sexes is two keys. `concordance` stays empty where no human lifespan direction exists to
agree with. The README records that the audit's PPARG row read a metabolic result as a lifespan one, that the
v2 "uncited" rows checked here have a primary reference GenAge loads by script, and that a database entry has
no citation column.

## The meta-table (0.8): APOE alleles, KL-VS × ε4 and the legacy tier

Built for real as [`reference_examples/apoe_klvs_meta/`](../reference_examples/apoe_klvs_meta), from the
longevitymap v2 shape audit's candidates 1, 2 and 3 and its legacy tag selector (PROPOSAL_0_8_PT2 §6). APOE is
scored only as ε diplotypes, ε2 and ε4 are `allele_function.csv` items so a `meta.csv` row can name them, and
the per-allele facts live once on the meta-table:

```csv
members,tier,age_of_action,age_of_action_confidence,flags,pmid
variants[flags=legacy_longevitymap],D,,,,
variants[variant_key=rs10455872],A,MIDLIFE,DIRECT_WEAK,,30642433
"allele_function[gene=APOE, allele=ε4]",A,LATE,DIRECT,ap:weak,30642433
"allele_function[gene=APOE, allele=ε2]",A,LATE,DIRECT_WEAK,protect:presence,31413261
"diplotypes[gene=APOE, haplotype_a=ε2, haplotype_b=ε4]",,,INFERRED,,
```

The tag selector gives tier D to every tagged row a locus row does not beat (TOMM40 rs2075650 stays D, LPA
goes to A). The ε2/ε4 diplotype carries both alleles, which disagree on confidence and on flags; the
diplotype row outranks the alleles it contains and settles the confidence, and the flags it does not state
stay withheld. The combination `diplotypes[gene=KL, haplotype_a=KL-VS, haplotype_b=ref] &
diplotypes[gene=APOE, haplotype_b=ε4]` is one row whose `meta.parquet` entry lists the four diplotype rows
it replaces. APOE's study links on rs429358 and rs7412 draw no orphan warning, because `haplotypes.csv`
defines the alleles on them. `compiler/tests/test_reference_examples_meta.py` asserts each value off the
compiled parquets.

## The meta-table (0.8): per-trait judgements and the computed trade-off

Built for real as [`reference_examples/pleiotropy_tradeoff/`](../reference_examples/pleiotropy_tradeoff),
the audit's candidate 4. One row per trait on a bare locus member, which bears an allele because every
`variants.csv` row of the locus states the same `effect_allele`:

```csv
members,trait_efo_id,trait_role,direction,pmid
variants[variant_key=rs3184504],MONDO:0005130,,risk,20560212
variants[variant_key=rs3184504],MONDO:0005113,,protective,20560212
variants[variant_key=rs10455872],EFO:0006925,mediator,protective,20032323
variants[variant_key=rs10455872],MONDO:0005010,,protective,20032323
variants[variant_key=rs5882],OBA:VT0005372,,protective,14559957
```

`meta_resolved.parquet` computes `tradeoff`: true on every SH2B3 genotype row (a harm and a benefit for one
allele), null on LPA (protective only; false needs every trait stated, and no module states a closed trait
list), null on CETP. CETP rs5882 states no `effect_allele`, so its row draws `meta_member_allele_ambiguous`
and its direction is withheld. That row is there on purpose, to show the warning; v2 writes no per-trait
row for a locus whose allele is not determined.

## The meta-table (0.8): CPIC's TPMT × NUDT15 phenotype pairs

Built for real as [`reference_examples/cpic_gene_pairs/`](../reference_examples/cpic_gene_pairs). The two
genes are drafted from the CPIC snapshot (`draft --gene TPMT --allele '*2' --allele '*3A' --offline`, then
NUDT15 with `*3`), and each of CPIC's thiopurine recommendations is one row over two existential phenotype
selectors, scoped to its drug:

```csv
members,conclusion,pmid,drug
"diplotypes[gene=TPMT, phenotype=Poor Metabolizer] & diplotypes[gene=NUDT15, phenotype=Normal Metabolizer]",Consider alternative nonthiopurine immunosuppressant therapy.,30447069,azathioprine
```

27 rows (three phenotypes per gene, three drugs), each listing every drafted diplotype its two phenotypes
match. `drug` is part of `meta.csv`'s key, so one pair's azathioprine, mercaptopurine and thioguanine rows
are three statements rather than duplicates. The README records three findings: the CPIC snapshot keeps no
recommendation id, so a pair cannot be reassembled from it and the rows came from a hand-run API call;
`meta.csv` could not scope a row to a drug, so the module first carried azathioprine only, which is what
added `drug` to the key; and CPIC's `classification` has no column on a pair row. It also names one compiler
defect the build hit (a haplotype row whose indel placement disagrees with `resolution.csv` loses the
injected fact on reverse) and the one `*1` row removed to keep the round trip.
