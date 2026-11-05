# HLA alleles and longevity

Three HLA alleles held as `allele_function.csv` items (RM334: HLA has no table of its own) with their
longevity findings on `meta.csv`. One finding is scoped to men, and its counterpart in women sits beside
it under the same member. One finding cites a medRxiv preprint by DOI alone. This is the longevitymap
v2 shape audit's candidate 10 (`docs/probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md`).

## How it was built

```bash
just-dna-compiler validate reference_examples/hla_alleles --strict
just-dna-compiler close reference_examples/hla_alleles
just-dna-compiler compile reference_examples/hla_alleles out/ --strict
```

There is no `variants.csv`, so nothing for the enricher to resolve, and no `resolution.csv`.
`allele_function.csv` is a lead table on its own, and `meta.csv` matches its members against it.

## What each row exercises

- **The RM334 grammar.** `*15:01`, `*57:01` and `*02:01` are two-field IPD-IMGT/HLA names: the field
  count is the resolution the name states, and no column states it. The German study reports the
  allele at three fields (`DRB1*15:01:01`), and its UK Biobank and Danish replications at two. v2, and
  this module, record the two-field name all three share.
- **A member that names an allele.** `allele_function[gene=HLA-DRB1, allele=*15:01]` is a concrete
  `(gene, allele)` key. `meta.parquet` stores the conditions sorted (`allele=…, gene=…`) and the authored
  spelling verbatim, and it matches exactly one row.
- **`sex` in the key.** The `male` row says DRB1\*15:01 lowers the odds of reaching extreme old age, and
  the `female` row records that the study found no such decrease in women. Same member, same trait,
  two statements. The female row states a `conclusion` and no `direction`: "no substantial decrease"
  is not a measured neutral effect, so the direction is left unknown.
- **`pmid=NONE` with a `doi` on a meta-table row.** HLA-A\*02:01's finding comes from a preprint with no
  PubMed id. The audit's second run listed this as "still not held", because meta-table rows had no `doi`.
  The 0.8 `CitationPair` gives every citing table the pair, and that hole is closed.

## What building it broke, or did not

1. **The audit's open hole is closed.** All six preprint alleles could now cite. One is enough to show it.
2. **An allele's magnitude still has no home.** `meta.csv` carries a direction and a conclusion. The odds
   ratio (0.64 in German men, about 0.68 for B\*57:01) can only live in the conclusion prose: a
   `studies.csv` row must name a variant or nothing, and a row naming nothing cites the module, not the
   allele. So this module states the ORs in prose and no numeric column carries them. This is a finding
   about the shape, not a workaround.
3. **Two of the three findings were measured on a tag SNP, not on the allele.** B\*57:01's evidence is
   the frequency of rs2395029-G, and DRB1\*15:01's Danish replication used rs3135388-A (r² 0.97 in
   Europeans, per the paper). RM331's `proxy_rsid` points from a variant to a variant, so the
   tag-to-allele link has no column, and the conclusion names the tag in prose.
4. **Nothing matches a genome to an HLA allele.** A consumer has to bring HLA typing (an imputed or typed
   allele call) to join against `allele_function.parquet`. The format carries no rule that derives an HLA
   allele from SNP genotypes, and should not: that is imputation, not annotation.

## Sources, and how each identifier was checked

PMIDs were checked against NCBI esummary on 2026-11-04 and DOIs against Crossref, and the medRxiv
record against the bioRxiv API (version 1, 2025-03-31, not published in a journal, licence
`cc_by_nc_nd`). No row quotes any article. The figures in the conclusions are from each abstract,
and the female and tag-SNP details are from the Genome Medicine full text (CC BY 4.0).

| Allele | Citation | Identifier |
|---|---|---|
| HLA-DRB1\*15:01 | Genome Med 2025, "HLA-DRB1\*15:01 is associated with a reduced likelihood of longevity in northern European men" | PMID 41116190, DOI 10.1186/s13073-025-01554-1 |
| HLA-B\*57:01 | Aging Dis 2025, "The HLA-B\*57:01 Haplotype, Genetic Key Linking Innate Immunity and Longevity" | PMID 41135092, DOI 10.14336/AD.2025.1109 |
| HLA-A\*02:01 | medRxiv 2025, "Cognitively healthy centenarians are characterized by lower frequencies of six disease-associated HLA alleles" | DOI 10.1101/2025.03.30.25324899 (no PMID) |
