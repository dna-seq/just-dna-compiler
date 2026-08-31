# Choosing the table kind

One CSV = one concern. Include only the kinds you use. The question that decides it is **what is the
row's subject** — not what data you happen to have.

Run `just-dna-compiler describe <kind>` for the columns and vocabularies; this file only decides
*which* kind.

## The decision

| The row is about… | Table | Model | Keyed on |
|---|---|---|---|
| one variant + one genotype | `variants.csv` | `spec.VariantRow` | `(variant_key, genotype)` |
| the evidence for a variant | `studies.csv` | `spec.StudyRow` | `(variant_key, pmid)` |
| which variants make up a named allele | `haplotypes.csv` | `pgx.HaplotypeRow` | `(haplotype_name, variant, allele)` |
| what a named allele *does* | `allele_function.csv` | `pgx.AlleleFunctionRow` | `(gene, allele)` |
| a **pair** of alleles (a diplotype) | `diplotypes.csv` | `pgx.DiplotypeRow` | `(gene, a, b, trait, drug, clinical_context)` |
| one variant + one drug | `pharm_variants.csv` | `pgx.PharmVariantRow` | `(variant_key, drug, genotype, category, annotation_id)` |
| a metabolizer **activity score** range | `activity_phenotype.csv` | `binning.ActivityPhenotypeRow` | `(gene)` |
| a **copy number** range | `copynumbers.csv` | `binning.CopyNumberRow` | `(gene, modifier_gene, modifier copy number)` |
| a **repeat count** range | `repeat_alleles.csv` | `binning.RepeatAlleleRow` | `(gene, repeat_unit)` |
| an mtDNA **heteroplasmy fraction** range | `heteroplasmy.csv` | `binning.HeteroplasmyRow` | `(gene, reference_sequence, tissue, variant_key)` |
| a published polygenic score | `pgs.csv` | `pgs.PgsRow` | `(pgs_id, trait)` |

Enricher-produced sidecars you never hand-author: `resolution.csv`, `frequencies.csv`,
`gene_metrics.csv`, `gene_validity.csv`, `clinical_assertions.csv`, `gwas_effects.csv`,
`literature.csv`, `licensing.csv`. The one exception is `licensing.csv` when you copied rows out of a
source by hand — no pass ran, so no pass will write the row, and the compile gate reads that file and
nothing else. (`sources.csv` is the older name for it; still read, and the compile tells you to rename
it. Never keep both — a module carrying two copies is refused.)

**Correcting one of them is a table too, and it is `overrides.csv`.** Never edit a derived file: it is
a build product, so a re-derivation reproduces it and your edit is a value nothing preserves. Write one
overlay row per column you are changing — `table`, `subject`, `member`, `field`, `operation`
(`update`/`insert`/`suppress`), `value`, and a **required** `reason` — and the compiler applies it on
every build. It covers all seven tables above except `licensing.csv`, which you write by hand anyway.
The full rules are in the main workflow under module structure.

Any of the enricher-produced files may sit either beside `module_spec.yaml` or in a `derived/` subdirectory, which is
a way to show at a glance which files a tool produced. Pick one and stay there: a pass writes back to
wherever it found the file, and the same table in both places is refused. Your hand-authored tables
above stay beside `module_spec.yaml` — they have one legal place.

## The four decisions people get wrong

**A quantity with a threshold is a binning table, not a variant row.** If the finding depends on *how
much* — repeat length, copy number, heteroplasmy fraction, activity score — the subject is the
measurement, and the module supplies the bins. Use inclusive `[measure_min, measure_max]`, `min == max`
for a sharp value, a null bound for open-ended, and **always author the `unresolved` sentinel**. If the
caller you expect reports the quantity as a decimal rather than a whole number, say so with
`measure_tiling: continuous` and let the bins touch.

**Say in the README what the bins mean, because today prose is the only path to a reader.** The four
binning tables are specified ahead of the tools that read them: the lookup a consumer performs — take
the measured quantity, select the row whose inclusive range contains it — is written down and, as of
2026-08-20, no consumer implements it. Authoring the table is still the right move (the module is the
durable thing, and the lookup is thirty lines whenever someone writes it), but a heteroplasmy or
copy-number module renders nothing today unless its README says what the ranges mean. Write that
paragraph as part of the module, not as an afterthought.

**Two alleles on one chromosome vs one on each is a haplotype vs a diplotype.** `haplotypes.csv` is a
junction table, so a haplotype defined by two SNPs is two rows — that is same-strand co-location, and
it needs no predicate language. A `diplotypes.csv` row pairs two haplotypes, which is what *in trans*
means. Together they express compound heterozygosity and its cis counterpart as distinct rows.

**Drug response splits by subject, not by source.** One variant + one drug → `pharm_variants.csv`. A
diplotype + a drug → the optional drug columns on `diplotypes.csv`. A haplotype-keyed annotation (`*1`)
belongs on `DiplotypeRow` even if the source published it beside single-variant rows.

**Where a citation goes: a row cites when its claim is finer-grained than a study row's.** A
`studies.csv` row is keyed `(variant_key, pmid)`, so it attaches to a **variant** — right for a
`variants.csv` row, wrong wherever one variant carries several distinct claims. Those tables carry
their own optional `pmid` instead:

- a binning row (`repeat_alleles.csv`, `copynumbers.csv`, `activity_phenotype.csv`,
  `heteroplasmy.csv`) — a threshold is the most interpretive number a module states, and a study row
  cannot point at one, since the bins are keyed by gene rather than by variant;
- a `pharm_variants.csv` row — keyed on drug, genotype and category as well as the variant, so one
  study row would attach the paper to every drug and genotype recorded for that variant at once.

The pointer is the whole of what moves. **The row cites; `studies.csv` and `literature.csv` describe**
— population, effect size, p-value and `provenance_quote` stay on the study row and do not follow.
Both spellings work everywhere a `pmid` is accepted (`9545397`, `[PMID: 9545397]`, a `;`-joined list),
and every site is checked for existence by the same pass, so a citation written on a bin or a pharm
row is verified exactly like one written on a study row.

**One paper often reports several analyses of one association — name each one in `statistical_test`.**
`study_design` says what the *study* was (case-control, GWAS, meta-analysis); `statistical_test` says
what produced *this row's* numbers, and a paper giving `OR 1.4, p 0.36` from an allelic Fisher's exact
test and `OR 1.42, p 0.75` from a univariate logistic regression of the same variant needs two rows,
not a choice. Free text, no fixed vocabulary — write what the paper calls it, adjustments included:
`Fisher's exact (allelic)`, `logistic regression adjusted for age, sex and BMI`.

Two things follow, and both are easy to get wrong:

- **Never mix analyses on one row.** A `p_value` from one test beside an `effect_size` from another is
  accepted by every check there is — the two cells assert that they belong together and nothing can
  contradict them. A provenance quote does not save you either: a quote grounding "not statistically
  significant" contains no statistic, so it cannot witness the numbers beside it. Take both numbers
  from the same table of the paper, and say which table it was.
- **Two rows sharing a variant and a PMID warn as a duplicate unless *both* name an analysis, and the
  two names differ.** An empty `statistical_test` is *unknown*, not *different*, so filling it on one
  row and leaving it blank on the other still reports the duplicate. Fill both, or accept the warning.

If the paper's own numbers do not reconstruct from its own counts, that is a finding about the paper —
record what you can support and leave `effect_size`/`effect_measure`/`effect_allele` empty rather than
copying a magnitude you cannot ground. An absent cell is honest; a wrong one is checked by nothing.

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
  and muscle, and one MT gene carries several variants with different thresholds. Keying on the gene
  alone makes a second real variant in that gene uncompilable.

## Axes that look interchangeable and are not

Never fold these together; each pair is two independent facts.

- `evidence_level` (PharmGKB/ClinPGx 1A–4: how well established) vs `recommendation_strength` (CPIC:
  how firmly to act). A well-evidenced association can carry an optional action. A provider fills only
  its own.
- `evidence_level` (somebody else's **grading of** the evidence) vs `pmid` (a pointer **at** the
  evidence). A row carrying `1A` still says nothing about which paper it rests on. Write both.
- `requires_callable` (a negative must be *proven*) vs `callable_from` (where the proof lives) vs
  `quality_from` / `min_quality` (whether what was seen is good enough to act on). The first two ask
  whether the position was seen; the third asks whether the call is trustworthy. Because they are
  separate axes they travel separately: `requires_callable` is available on `variants.csv`,
  `haplotypes.csv` and `pharm_variants.csv` — every table that names a locus — while `callable_from`
  stays on `variants.csv`. A row may require a proof without knowing which VCF field holds it.
- `FrequencyRow.population` (an **ancestry** group) vs `DiplotypeRow.clinical_context` (an indication,
  age band, prior treatment or dose). Two unrelated axes; do not reuse the name.
- `acmg_sf` (gene-list membership) vs `actionability` (the gene–condition–intervention category). A
  flag, not a value in the axis.

## Composition

A module with no `variants.csv` is normal and correct — a PGx, PRS or binning module carries only its
own tables. `studies.csv` is required **iff** `variants.csv` is present. At least one recognised table
must exist.

Module shapes that work, as a sanity check on your own:

| Shape | Tables |
|---|---|
| a ClinVar-drafted gene panel, zygosity curated by hand | `variants.csv` + `studies.csv` |
| a two-SNP haplotype needing no predicate language (APOE ε) | `variants.csv` + `studies.csv` |
| cis vs trans as two rows (HFE compound het) | `haplotypes.csv` + `diplotypes.csv` |
| CPIC star alleles, curated by removal | `haplotypes.csv` + `allele_function.csv` + `diplotypes.csv` |
| single-variant drug response (SLCO1B1 / simvastatin) | `pharm_variants.csv` |
| repeat-count bins (HTT) | `repeat_alleles.csv` |
| tissue- and variant-conditional bins with `unresolved` sentinels | `heteroplasmy.csv` |
| a pseudoautosomal panel | `variants.csv` + `studies.csv`, X spelling only |

Each of these is a whole module. Adding an empty `variants.csv` to a PGx module to make it look
complete is the mistake the composition rule exists to prevent.
