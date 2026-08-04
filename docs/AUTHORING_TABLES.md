# Choosing the table kind

One CSV = one concern. Include only the kinds you use. The question that decides it is **what is the
row's subject** — not what data you happen to have.

## The decision

| The row is about… | Table | Model | Keyed on |
|------------------------------|----------------------|----------------------|--------------------------|
| one variant + one genotype | `variants.csv` | `spec.VariantRow` | `(variant_key, genotype)` |
| the evidence for a variant | `studies.csv` | `spec.StudyRow` | `(variant_key, pmid)` |
| which variants make up a named allele | `haplotypes.csv` | `pgx.HaplotypeRow` | `(haplotype_name, variant, allele)` |
| what a named allele *does* | `allele_function.csv` | `pgx.AlleleFunctionRow` | `(gene, allele)` |
| a **pair** of alleles (a diplotype) | `diplotypes.csv` | `pgx.DiplotypeRow` | `(gene, a, b, trait, drug, clinical_context)` |
| one variant + one drug | `pharm_variants.csv` | `pgx.PharmVariantRow` | `(variant_key, drug, genotype, category, annotation_id)` |
| a metabolizer **activity score** range | `activity_phenotype.csv` | `binning.ActivityPhenotypeRow` | `(gene)` |
| a **copy number** range | `copynumbers.csv` | `binning.CopyNumberRow` | `(gene, modifier_gene, modifier_cn)` |
| a **repeat count** range | `repeat_alleles.csv` | `binning.RepeatAlleleRow` | `(gene, repeat_unit)` |
| an mtDNA **heteroplasmy fraction** range | `heteroplasmy.csv` | `binning.HeteroplasmyRow` | `(gene, reference_sequence, tissue, variant_key)` |
| a published polygenic score | `pgs.csv` | `pgs.PgsRow` | `(pgs_id, trait)` |

Enricher-produced sidecars you never hand-author: `resolution.csv`, `frequencies.csv`,
`gene_metrics.csv`, `literature.csv`, `sources.csv`.

## The four decisions people get wrong

**A quantity with a threshold is a binning table, not a variant row.** If the finding depends on *how
much* — repeat length, copy number, heteroplasmy fraction, activity score — the subject is the
measurement, and the module supplies the bins. Use inclusive `[measure_min, measure_max]`, `min == max`
for a sharp value, a null bound for open-ended, and **always author the `unresolved` sentinel**.

**Two alleles on one chromosome vs one on each is a haplotype vs a diplotype.** `haplotypes.csv` is a
junction table, so a haplotype defined by two SNPs is two rows — that is same-strand co-location, and
it needs no predicate language. A `diplotypes.csv` row pairs two haplotypes, which is what *in trans*
means. Together they express compound heterozygosity and its cis counterpart as distinct rows; see
`reference_examples/hfe_compound_het/`.

**Drug response splits by subject, not by source.** One variant + one drug →
`pharm_variants.csv`. A diplotype + a drug → the optional drug columns on `diplotypes.csv`. A
haplotype-keyed annotation (`*1`) belongs on `DiplotypeRow` even if the source published it beside
single-variant rows.

**A per-genotype or per-context axis belongs in the key, or the rows collide.** These were all learned
from real corpora rejecting themselves:
- `PharmVariantRow.genotype` — ClinPGx publishes per genotype, and the calls can be *opposed*
  (rs4149056/simvastatin: CC/CT "decreased", TT "increased").
- `phenotype_category` + `annotation_id` — one variant+drug+genotype carries several distinct
  annotations; 1,199 of 17,380 triples collide without them.
- `DiplotypeRow.clinical_context` — CPIC scopes a recommendation to a setting and the settings
  disagree; the same Poor Metabolizer diplotype is `strong` in `CVI ACS PCI` and `moderate` in `NVI`.
  Draft all of them and let the consumer select.
- `HeteroplasmyRow.tissue` **and** `variant_key` — the same fraction means different things in blood
  and muscle, and one MT gene carries several variants with different thresholds.

## Axes that look interchangeable and are not

Never fold these together; each pair is two independent facts (Principle 5).

- `evidence_level` (PharmGKB 1A–4: how well established) vs `recommendation_strength` (CPIC: how firmly
  to act). A well-evidenced association can carry an optional action. A provider fills only its own.
- `requires_callable` (a negative must be *proven*) vs `callable_from` (where the proof lives) vs
  `quality_from`/`min_quality` (whether what was seen is good enough to act on). The first two ask
  whether the position was seen; the third asks whether the call is trustworthy.
- `FrequencyRow.population` (an **ancestry** group) vs `DiplotypeRow.clinical_context` (an indication,
  age band, prior treatment or dose). Two unrelated axes; do not reuse the name.
- `acmg_sf` (gene-list membership) vs `actionability` (the gene–condition–intervention category). A
  flag, not a value in the axis.

## Composition

A module with no `variants.csv` is normal and correct — a PGx, PRS or binning module carries only its
own tables. `studies.csv` is required **iff** `variants.csv` is present. At least one recognised table
must exist.

Worked examples, each README naming what it exercises:

| Example | Shows |
|--------------------------|--------------------------------------------------------------------------|
| `hfe_hemochromatosis` | a ClinVar-drafted panel, zygosity curated by hand |
| `pathogenic_clinvar` | a large panel; rsID one-to-many expansion |
| `apoe_epsilon` | a two-SNP haplotype needing no predicate |
| `hfe_compound_het` | cis vs trans as two diplotype rows |
| `cyp2c19_star_alleles` | CPIC star alleles, curated by removal |
| `pgx_slco1b1_simvastatin` | single-variant drug response |
| `htt_repeat_expansion` | repeat-count bins |
| `mt_heteroplasmy` | tissue- and variant-conditional bins, `unresolved` sentinels |
| `shox_par1` | a pseudoautosomal panel, and what it broke |
| `par_boundary` | XG and SPRY3 straddling a PAR boundary — why the PAR verdict is per locus |
