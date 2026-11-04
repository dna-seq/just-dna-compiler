# TPMT × NUDT15: CPIC's phenotype-pair recommendations on the meta-table

The second addendum's case (ROADMAP_0_8 § RM28, "inside a combination, a selector is existential"):
CPIC keys its thiopurine recommendations on a TPMT phenotype and a NUDT15 phenotype together, and the
0.8 meta-table writes each pair as one row over two phenotype selectors instead of diplotype ×
diplotype. The values below are asserted by `compiler/tests/test_reference_examples_meta.py`.

**This module carries all three thiopurines: azathioprine, mercaptopurine and thioguanine.** Until
`meta.csv` gained `drug` it carried azathioprine only; finding 2 below records why.

## How it was built

```bash
# module_spec.yaml by hand, then the two genes drafted from the provisioned CPIC snapshot
just-dna-enricher draft reference_examples/cpic_gene_pairs --gene TPMT --allele '*2' --allele '*3A' \
    --use non-commercial --offline
just-dna-enricher draft reference_examples/cpic_gene_pairs --gene NUDT15 --allele '*3' \
    --use non-commercial --offline
# meta.csv: 27 rows, nine pairs × three drugs, from CPIC's API (below)
# haplotypes.csv: one row removed (below)
just-dna-enricher enrich reference_examples/cpic_gene_pairs --strict
just-dna-compiler close reference_examples/cpic_gene_pairs
just-dna-compiler compile reference_examples/cpic_gene_pairs out/ --strict
```

`enrich` writes no `clin_sig_*.csv` concordance pair here: the module authors no `clin_sig`, so the
check has nothing to ask, and a pass that answered nothing writes no table (RM370). `--offline` drafts from the snapshot (`cpic_snapshot_b0ffd4c6f010`) and nothing else. `--allele` keeps
the table small: TPMT `*1`, `*2`, `*3A` and NUDT15 `*1`, `*3` give six and three diplotypes covering the
Normal, Intermediate and Poor Metabolizer phenotypes of each gene. The drafter wrote `haplotypes.csv`,
`allele_function.csv`, `diplotypes.csv` and the CPIC row of `licensing.csv`: CC-BY-SA-4.0, share-alike,
no sale, `declared_use=non_commercial` (`@pgx-research-only`). `enrich` added the Ensembl row.

## What it exercises

27 rows: TPMT {Normal, Intermediate, Poor} × NUDT15 {Normal, Intermediate, Poor}, once per thiopurine in
`drug`, each like

```
diplotypes[gene=TPMT, phenotype=Poor Metabolizer] & diplotypes[gene=NUDT15, phenotype=Normal Metabolizer]
```

with CPIC's `drugrecommendation` verbatim in `conclusion` (CPIC's own spelling kept, `mecaptopurine`
included) and the guideline's PMID (30447069, Relling et al. 2019, the CPIC TPMT/NUDT15 thiopurine
guideline, checked against PubMed) in `pmid`. The rows are drug-major (azathioprine, mercaptopurine,
thioguanine), and within a drug TPMT-major, each gene in the order Normal, Intermediate, Poor.

- **One pair, one row per drug.** `drug` is part of `meta.csv`'s key, so the pair's three rows are three
  statements. For TPMT Poor × NUDT15 Normal, azathioprine reads "Consider alternative nonthiopurine
  immunosuppressant therapy.", mercaptopurine starts "For malignancy: initiate therapy with drastically
  reduced starting doses", and thioguanine "Initiate therapy with drastically reduced starting doses".

- **A selector is existential inside a combination.** `phenotype=Poor Metabolizer` matches all three
  drafted TPMT poor-metabolizer diplotypes (`*2/*2`, `*2/*3A`, `*3A/*3A`); the row lists every one in
  `meta.parquet`'s `matches`, so a consumer joins rows and evaluates nothing.
- **Every row replaces what it names** (`replaces` true): a genome matching both members shows the pair
  recommendation in place of the two single-gene phenotype rows.
- **Nothing reaches `meta_resolved.parquet`.** No row has one member, so no fact resolves onto a
  diplotype row, whatever its drug.

## The CPIC call made by hand

The provisioned snapshot cannot give the pairs (finding 1), so the rows come from CPIC's API, called by
hand on 2026-11-04T14:54:58Z for the nine azathioprine rows and again on 2026-11-04T17:15:31Z for all 27:

```
GET https://api.cpicpgx.org/v1/recommendation?select=id,lookupkey,phenotypes,drugrecommendation,
    classification,population,implications,drug!inner(name),guidelineid
    &drug.name=in.(azathioprine,mercaptopurine,thioguanine)&order=id
→ 200, 105 recommendations (35 phenotype pairs × 3 drugs), every one with two genes, all population "general"
```

Every azathioprine half the snapshot holds matches the API's text exactly (checked per gene, per
phenotype); the snapshot just cannot say which halves belong together. The second call returned the
same nine azathioprine texts as the first, byte for byte, and the 18 other rows were written from it.

## Findings

1. **The CPIC snapshot cannot reassemble a pair recommendation.** `recommendations.parquet` flattens a
   recommendation's `phenotypes` map to one row per gene and keeps no recommendation id and no partner
   phenotype (`cpic_build.py`; `CpicSnapshot.partner_genes` already says so). For azathioprine the
   snapshot's 70 rows are 35 NUDT15 halves and 35 TPMT halves, and the text does not pair them: "Consider
   alternative nonthiopurine immunosuppressant therapy." is the whole recommendation for 11 different pairs.
   No drafter writes `meta.csv` rows either. So the pair rows were written from the live API, not
   drafted.
2. **`meta.csv` could not scope a row to a drug, so the module first held one drug's pairs. Answered:
   `drug` is now part of the key.** The key was the member set plus `trait_efo_id` plus `sex`. CPIC gives
   each phenotype pair a different recommendation per thiopurine (for Normal × Normal: azathioprine
   "e.g., 2 mg/kg/day", mercaptopurine "e.g., 75 mg/m2/day", thioguanine "e.g., 40 mg/m2/day"), so a
   mercaptopurine row for the same pair was refused as a duplicate key, and a test pinned that. The
   members cannot carry the drug: `diplotypes[…, drug=azathioprine]` needs diplotype rows with that drug,
   and the drafter writes drug rows only from single-gene recommendations (RM249), which pair-keyed drugs
   have none of. Writing the drug into `trait_efo_id` would overload the trait axis (P5). The lead added an
   optional `drug` to `meta.csv` on 2026-11-04, in the key beside `sex`, and the module now carries all
   three drugs; `test_cpic_every_phenotype_pair_states_each_thiopurine_once` asserts it.
3. **CPIC's `classification` has no column on the meta-table.** Of the 27 rows, 23 are `Strong` and four
   are `Moderate` (azathioprine's Intermediate × Intermediate and three of thioguanine's).
   `DiplotypeRow.recommendation_strength` holds it for a single gene, and a pair row drops it. It was not put into `tier`, which is an evidence tier on a
   module-named scale, not CPIC's strength.

## What building it broke

- **One `haplotypes.csv` row was removed: `*1,rs1457579126,13,48040982,A,NUDT15`.** CPIC places this
  NUDT15 deletion at 48040982; the Ensembl cache places it at `48040978 AA>A`, the left-aligned spelling.
  The compiler warns that the row "authored an identity the resolution table disagrees with" and leaves
  it as authored, so no parquet carries the resolution table's placement. `reverse` rebuilds
  `resolution.csv` from the parquets, the injected fact is gone, and the round trip's lap-1
  `resolution_signature` moves:
  `test_reference_example_round_trips_to_a_fixed_point[cpic_gene_pairs]` failed with
  *"reverse lost injected resolution facts on a module the fill was applied to"*. That is a compiler
  defect in the indel-placement family (RM267's lane), reported to the 0.8 lead for filing and not
  fixed here. The removed row is a
  `*1` reference row, so no phenotype the module states depends on it, and removal is the
  `cyp2c19_star_alleles` precedent (curated by removal). Correcting the start by hand was not done: it is
  the rewrite RM267's open half withholds from the enricher.
- **Rows with no rsID and no `ref` get a `variant_key` like `13:48037749:None`.** Nine of the drafted
  `*1` rows carry a position and an allele but no rsID and no reference base, and `derive_variant_key`
  formats the missing `ref` as the Python literal `None`. It compiles and round-trips; the key is still
  wrong. Reported to the 0.8 lead for filing, not fixed here.
