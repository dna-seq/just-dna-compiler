# Model-organism lifespan evidence beside a human variant

`model_organisms.csv` (RM335) holds mouse lifespan experiments on two human genes, PPARG and IGF1R,
beside a module that annotates one human variant (PPARG Pro12Ala, rs1801282) for type 2 diabetes. This
is the longevitymap v2 shape audit's candidate 12 (first run) / 13 (second run).

## How it was built

```bash
just-dna-enricher enrich reference_examples/model_organisms --offline \
    --ensembl-cache /data/just-dna-cache/ensembl_variations
just-dna-compiler validate reference_examples/model_organisms --strict
just-dna-compiler close reference_examples/model_organisms
just-dna-compiler compile reference_examples/model_organisms out/ --strict
```

## What it exercises

- **The table needs a lead table beside it.** A module of `model_organisms.csv` alone is refused ("module
  has no recognized table"), as the model's docstring says it should be: the rows are annotation only,
  and nothing in them is matched against a genome. `variants.csv` carries the one human variant.
- **The key is the experiment.** The IGF1R heterozygous-knockout result is two rows, one per sex, with the
  same citation: females +33% (P < 0.001), males +16% (not significant). They differ only in `sex`, and
  that is enough. `sex` here is the animals' sex, free text, not `meta.csv`'s karyotype condition.
- **`concordance` stays empty when nobody can say it.** The female IGF1R row is `concordant`: Suh et al.
  2008 (PMID 18316725) found heterozygous, reduced-activity IGF1R mutations over-represented in female
  centenarians, the same direction and the same sex. The PPARG row leaves it empty. Ala/Ala mice lived
  longer, but this module's human evidence for Ala12 is about diabetes, not lifespan, so there is no human
  lifespan direction to agree with.
- **Annotation never reaches a score.** `weights.parquet` carries the variant's finding. The mouse rows
  land in `model_organisms.parquet` alone.

## What building it broke

1. **The audit's PPARG row overstated the paper.** The sketch read "benefit lost on high-fat diet" as a
   lifespan result and marked it `nonmonotone`. The abstract says Ala/Ala mice "have longer lifespans" on
   chow, and that high-fat feeding removed the benefit "on adiposity, plasma lipids, and insulin
   sensitivity". It reports no lifespan on high fat. So this row is a chow-diet lifespan gain, with
   `concordance` empty.
2. **The "uncited" rows mostly have a paper one fetch away.** v2 has 17 rows with no PMID, and the audit
   gave that count as the reason `pmid` is optional here. Sixteen of the 17 are GenAge entries that v2
   notes as "primary PMID not retrieved". GenAge loads the reference with a script call after the page
   renders, and a page scrape never sees it. The one checked here, the mouse Ghrhr entry, has one: the
   call (`libage.ageing-map.org/api/get/genage_model/301/`) returns Flurkey et al. 2001, PMID 11371619.
   So this example carries no uncited row. The seventeenth (Klotho) is recorded by v2 with conference
   abstract DOIs and no PMID, not checked here. The optional, warning-free `pmid` may still be right,
   but the count overstated the need.
3. **A database entry has no citation column.** When a row's real source is a GenAge entry rather than a
   paper, `pmid`/`doi` cannot name it. GenAge's descriptions are CC BY 3.0 (HAGR's legal page), so citing
   the entry would be enough if a column held it. The audit already named this as "or a GenAge id", and it
   is still open.

## Sources, and how each identifier was checked

PMIDs were checked against NCBI esummary/efetch on 2026-11-04. Every lifespan figure is read from the
abstract, and no row quotes an article.

| Row | Citation | Identifier |
|---|---|---|
| rs1801282 (`studies.csv`) | Altshuler et al. 2000, *Nat Genet*: "The common PPARgamma Pro12Ala polymorphism is associated with decreased risk of type 2 diabetes" | PMID 10973253 |
| PPARG / Pparg | Heikkinen et al. 2009, *Cell Metab*: "The Pro12Ala PPARgamma2 variant determines metabolism at the gene-environment interface" | PMID 19117549 |
| IGF1R / Igf1r (both sexes) | Holzenberger et al. 2003, *Nature*: "IGF-1 receptor regulates lifespan and resistance to oxidative stress in mice" | PMID 12483226 |
| (concordance basis) | Suh et al. 2008, *PNAS*: "Functionally significant insulin-like growth factor I receptor mutations in centenarians" | PMID 18316725 |
