# SLCO1B1 × simvastatin — a PharmGKB/ClinPGx drug-response module

The reference example for the pharmacogenomics path: a module that carries **no `variants.csv`**, is
keyed per genotype, and records the terms its data came under.

## What it is

`rs4149056` (SLCO1B1 `*5`, c.521T>C) and simvastatin. ClinPGx publishes **three separate clinical
annotations** for that one variant-and-drug pair, and this module transcribes all three:

| Annotation | Category | Level | What it says |
|---|---|---|---|
| 1449556772 | Metabolism/PK | 1A | C carriers have higher simvastatin-acid exposure |
| 1451356520 | Efficacy | 3 | C carriers respond less well (evidence conflicting) |
| 655384011 | Toxicity | 1A | C carriers have higher myopathy risk |

Each is stated **per genotype** (`C/C`, `C/T`, `T/T`), so the module has nine rows.

## Why it looks like this

**Nine rows, not three, and not one.** A PharmGKB clinical annotation is published per genotype —
the large majority in any release carry exactly three — and the calls can be opposed: `T/T` has
*lower* myopathy risk where `C/C` has higher. Collapsing them would lose the axis a consumer looks up.

**`phenotype_category` and `annotation_id` are identity, not decoration.** Without the category, the
efficacy, toxicity and metabolism rows for one genotype collide; 1,199 of 17,380 (variant, drug,
genotype) triples in the release map to more than one annotation. The duplicate-row key is therefore
`(variant_key, drug, genotype, phenotype_category, annotation_id)`. `annotation_id` is the tie-break
for the 283 triples that differ by neither — a source accession as identity, like `PgsRow.pgs_id`.

**No `variants.csv`.** One CSV = one concern: a drug-response module carries `pharm_variants.csv` and
nothing else. Resolution still reaches it — since 0.5 the resolver reads `pharm_variants.csv` and
`haplotypes.csv` too, so `resolution.csv` here has a real coordinate for rs4149056.

**`license:` and `sources.csv`.** ClinPGx is CC BY-SA 4.0 *plus* a contractual bar on sale, so this
module is **not sellable** and says so in machine-readable form. The compiler refuses to build a
module carrying such content unless a matching declaration is recorded — try deleting the
`declared_use` cell from `sources.csv` and recompiling.

## Rebuilding it

```bash
# 1. the snapshot (dev surface; accepts the terms at download time)
just-dna-enricher clinpgx build --out data/interim/clinpgx --use non-commercial

# 2. coordinates — driven by pharm_variants.csv, with no variants.csv present
just-dna-enricher enrich reference_examples/pgx_slco1b1_simvastatin

# 3. cross-check the authored evidence levels + record the terms
just-dna-enricher clinpgx check reference_examples/pgx_slco1b1_simvastatin \
    --snapshot data/interim/clinpgx --use non-commercial

# 4. compile
just-dna-compiler compile reference_examples/pgx_slco1b1_simvastatin out/
```

Step 3 is silent when the module is faithful. Change one `evidence_level` and it names the row; add
`--strict` and it refuses, because an evidence level is ClinPGx's own metadata about its own
annotation — a difference there means the module is stale, not that two experts disagree.

## Attribution

Annotation content derived from ClinPGx (https://www.clinpgx.org/page/citingClinpgx), CC BY-SA 4.0.
Data may not be sold for private or commercial use. Coordinates from Ensembl.
