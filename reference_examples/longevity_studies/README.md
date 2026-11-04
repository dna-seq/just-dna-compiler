# Longevity GWAS evidence, per analysis

Five longevity loci and thirteen `studies.csv` rows that use the 0.8 `StudyRow` columns: which outcome
an estimate measured (`phenotype_class`), how many were analysed and in what unit (`sample_size`,
`sample_unit`, `n_cases`), over which age band and whose age (`age_min`, `age_max`, `age_of`), within
which stratum (`stratum`, `stratum_level`), in which superpopulation (`ancestry`), in what unit the
effect is stated (`effect_unit`), whether it was measured on an LD proxy (`proxy_rsid`), and the
`pmid=NONE` + `doi` citation of a preprint. The rows are the longevitymap v2 shape audit's candidates 5,
6, 7, 8, 9, 11 and 13 (`docs/probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md`), rebuilt from the papers. The
audit's sketches were illustrative, and four of their numbers or labels did not survive contact with
the sources (below).

## How it was built

```bash
just-dna-enricher enrich reference_examples/longevity_studies --offline \
    --ensembl-cache /data/just-dna-cache/ensembl_variations
just-dna-compiler validate reference_examples/longevity_studies --strict
just-dna-compiler close reference_examples/longevity_studies
just-dna-compiler compile reference_examples/longevity_studies out/ --strict
```

`resolution.csv` and `licensing.csv` (Ensembl's terms) are the enricher's output (no `clin_sig_*`
concordance pair: the module authors no `clin_sig`, so there was nothing to record, RM370), written against the provisioned Ensembl snapshot. Nothing in them was typed by hand.

## What each row exercises

| Loci and source | Rows | What they show |
|---|---|---|
| rs10455872 (LPA), Timmers 2020, PMID 32678081 | 3 | One paper, three outcomes (`HEALTHSPAN`, `PARENTAL_LIFESPAN`, `EXTREME_SURVIVAL_CC`). Nothing but `phenotype_class` tells them apart: `statistical_test` is left empty on purpose. The outcome strip on `weights.parquet` reads all three cells true. |
| rs10455872, Timmers 2019, PMID 30642433 | 1 | The whole GWAS: 1,012,240 parental **lives**, over the open band "parent age > 40" (`age_min=40`, `age_max` empty, `age_of=parent`). |
| rs10455872, Timmers 2019, Figure 5 source data 1 | 3 | One paper's age-by-sex table: two bands in fathers (60–70, 70–80) and one band (70–80) in both parents. The band tells the first two apart and the `parent_sex` stratum the last two. `sample_size` is the table's own N, in lives. |
| rs429358 (APOE ε4), Deelen 2019, PMID 31413261 | 2 | One class, two case definitions (≥90th and ≥99th survival percentile). The percentile has no typed home, so only `statistical_test` separates them (RM140's rule). `n_cases` differs too, but it is not a narrowing cell. |
| rs429358, Pilling 2017, PMID 29227965 | 1 | A parental-lifespan GWAS that counts **participants** (389,166 `individuals`), against Timmers' lives. |
| rs646776 (CELSR2/PSRC1), Timmers 2019 | 1 | `proxy_rsid=rs4970836`: the estimate was measured on the proxy, and `effect_allele=G` is the proxy's allele, checked against the proxy's resolved alleles. |
| rs75571981 (EYS), a Research Square preprint | 1 | `pmid=NONE`, `doi=10.21203/rs.3.rs-6869504/v1`, `ancestry=EAS`, 964 cases in 8,270. |
| rs2802292 (FOXO3), CHAMP, PMID 41837379 | 1 | `stratum=comorbidity`, `stratum_level=angina`, in a men-only cohort (below). |

Two probes, run on a copy and reverted:

- Blanking `phenotype_class` on the Timmers 2020 healthspan row makes both later rows warn
  `Duplicate (variant, pmid): (rs10455872, 32678081)`, because an unstated class is not a different class
  (`@absent-is-not-different`).
- Setting the proxy row's `effect_allele` to `T` draws `rs646776 via proxy rs4970836 (PMID 30642433):
  effect_allele 'T' is not among the resolved alleles at the proxy (A/C/G)`. The check reads the proxy,
  never the lead.

## What building it broke

1. **Reverse loses the proxy's resolution row (RM331).** The enricher resolves `rs4970836` as a subject
   and writes its row into `resolution.csv`. No parquet carries a proxy's coordinates, so `reverse_module`
   cannot rebuild that row. The lap-2 `resolution_signature` then differs, and the effect-allele check
   against the proxy goes silent after a round trip.
   `test_reference_example_round_trips_to_a_fixed_point[longevity_studies]` fails on exactly this, and
   it stays red until RM331's builder makes every resolution subject reach a parquet that reverse reads.
2. **The paper contradicts itself about two effect alleles.** Timmers 2019's Table 1 names **A** as the
   lifespan-increasing allele of rs10455872, and its Table 2 names **G** for rs4970836. Its Figure 5 source
   data, whose legend says "Variant – rsID, longevity allele", labels the same two variants `rs10455872_G`
   and `rs4970836_A`, with positive betas. The frequencies (A 0.92) and the biology (G raises
   lipoprotein(a)) side with Table 1, but the band rows come from the source data. So those three rows
   **withhold `effect_allele`** rather than pick one. v2's age-band file inherited the `_G` label, and the
   audit's sketch wrote A, so each followed one of the two.
3. **The audit's bands were v2's, not the paper's.** The sketch's 40–60 / 60–80 / 80+ rows are v2's own
   inverse-variance pooling of fathers and mothers. The paper publishes 10-year bands per parent, and its
   top band is a closed "90 to 120". The open band here is the paper's own statement that every life in
   the GWAS had "parent age > 40".
4. **Two smaller corrections.** Timmers 2020's healthspan N is 300,477 (the sketch had 300,447). The
   sketch's `n_cases` for a survival band would have been the band's deaths: those are events in a Cox
   model, not cases in a case-control design, so the column stays empty.
5. **The "two strata on one estimate" case reduced to one stratum.** The audit's FOXO3 case reads "men
   with angina" as two modifiers. CHAMP is a men-only cohort, though, so sex is the cohort (`population`)
   and angina is the one stratum. The audit settled the case as prose; this row does not need it. The
   audit's second locus (GHR rs4130113) was not rebuilt here.
6. **An r² cannot say which lead allele a proxy allele tags.** No shipped pass computes the proxy pair
   (RM331's enricher half), so r² was checked by hand. Ensembl REST `ld/human/pairwise/rs646776/rs4970836`
   gives r² 0.904 in 1000G CEU and 0.965 in GBR. The row still needs the *phase*: does G at rs4970836
   travel with C or with T at rs646776? r² is sign-free. Here gnomAD v4 NFE makes both reference alleles
   the minor ones (rs646776 C 0.22, rs4970836 G 0.20), and coupling minor with major would cap r² near
   0.07. So G travels with C, and the `variants.csv` row is `C/T`. That derivation is the author's to do,
   and a computed r² column will not do it for them.
7. **`effect_unit` on `weights.parquet` can be one study's unit.** rs429358 shows Pilling's Martingale
   unit, because Deelen's two OR rows state no unit and "every study row that states one agrees" counts
   only the rows that state one. That is the PT2 §3 item 17 default (§4 question 5), and it is visible
   here.
8. **The tool caught one authoring error.** The EYS genotype was first written `A/G`. The enricher
   refused it: 6:63910997 is T>C, and "reading A/G on the other strand fits it exactly". The row is now
   `C/T`: C is the minor allele, gnomAD v4 EAS 0.01, and the preprint reports it enriched in centenarians.

## Sources, and how each identifier was checked

Every PMID was checked against NCBI esummary on 2026-11-04 (title, journal, DOI), and every DOI against
Crossref. Every `provenance_quote` was cut programmatically from Europe PMC's `fullTextXML` of that
article, so it is the passage verbatim, and every article quoted is CC BY (3.0 or 4.0). The CHAMP
article (OUP, all rights reserved) is cited but not quoted; its row restates the abstract.

| Citation | Identifier | Where the numbers come from |
|---|---|---|
| Timmers et al. 2020, *Nat Commun* | PMID 32678081, PMC7366647 | Table 1 (β, P) and its footnote (units); Results ¶1 (N) |
| Timmers et al. 2019, *eLife* | PMID 30642433, PMC6333444 | Table 1 and Table 2; `elife-39856-fig5-data1-v2.xlsx` (bands) |
| Deelen et al. 2019, *Nat Commun* | PMID 31413261, PMC6694136 | Table 2 (European discovery); Table 1 (cases, controls) |
| Pilling et al. 2017, *Aging* | PMID 29227965, PMC5764389 | Table 2, the bold "Parents' attained age" P |
| Japanese centenarian GWAS, Research Square preprint | DOI 10.21203/rs.3.rs-6869504/v1 (Europe PMC PPR1042277; no PMID) | Figure 2 legend |
| Abdi et al. 2026, *J Gerontol A* | PMID 41837379 | abstract only |
