# APOE, KL-VS and the legacy tier: the meta-table

The 0.8 meta-table (`meta.csv`) on the longevitymap v2 cases it was designed for: candidates 1, 2 and 3
of `docs/probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` (Appendix 2), plus the legacy tag selector. Every row is
the smallest one that exercises its case. The expected values below are asserted against the compiled
parquets by `compiler/tests/test_reference_examples_meta.py`, and the round trip by the discovered
sweep in `compiler/tests/test_reference_examples_roundtrip.py`.

## How it was built

```bash
# variants.csv, haplotypes.csv, allele_function.csv, diplotypes.csv, studies.csv, meta.csv by hand
just-dna-enricher enrich reference_examples/apoe_klvs_meta --strict   # online: rsID currency, ref bases
just-dna-compiler close reference_examples/apoe_klvs_meta
just-dna-compiler validate reference_examples/apoe_klvs_meta --strict
just-dna-compiler compile reference_examples/apoe_klvs_meta out/ --strict
```

The two `clin_sig_*.csv` files the enricher writes were deleted: the module authors no `clin_sig`, so
both are header-only. `licensing.csv` holds the one row the enricher wrote (Ensembl, the resolution
link).

## What it exercises

**The legacy layer is one selector, and a locus row beats it.** `variants[flags=legacy_longevitymap]`
gives tier D to every `variants.csv` row carrying the tag. `variants[variant_key=rs10455872]` is a locus
key, which outranks a selector, so LPA's three genotype rows resolve to tier A with `MIDLIFE` /
`DIRECT_WEAK`. TOMM40 rs2075650 has no row of its own and stays at D. That is the audit's edge: v2's seed
says C, and D is right if "not scored" is the intent, because rs2075650 travels with ε4 and its
association is ε4's.

**`tier` is on a scale the module names once.** `module_spec.yaml` says `tier_scale: longevitymap_v2`;
the manifest carries it and `reverse` writes it back. The rubric: A well established, B good, C weak or
a single study, D a legacy candidate that is not scored. The format does not check a value against it
(the scale is the module's).

**APOE is scored only as diplotypes.** ε2 and ε4 are `allele_function.csv` items (the key, nothing
else) so that a meta row can name them: `allele_function[gene=APOE, allele=ε4]`. Their facts differ on
`age_of_action_confidence` (ε4 `DIRECT`, ε2 `DIRECT_WEAK`) and on `flags`. The ε2/ε4 diplotype carries
both alleles, so in `meta_resolved.parquet`:

| column | ε2 row | ε4 row | ε2/ε4 diplotype row | ε2/ε4 resolved |
|---|---|---|---|---|
| `tier` | A | A | (unstated) | A |
| `age_of_action` | LATE | LATE | (unstated) | LATE |
| `age_of_action_confidence` | DIRECT_WEAK | DIRECT | INFERRED | **INFERRED** |
| `flags` | protect:presence | ap:weak | (unstated) | null, `withheld = ["flags"]` |

A diplotype outranks the alleles it contains, so the diplotype row settles the column it states. It
states no `flags`, and unstated is not different, so the two alleles' disagreement on `flags` still
stands and the column is withheld rather than picked. A diplotype holding one of the two alleles
(ε3/ε4, ε4/ε4, ε2/ε2, ε2/ε3) takes that allele's facts whole.

**APOE's study links draw no orphan warning.** `studies.csv` cites rs429358 and rs7412, which are no
`variants.csv` row. `haplotypes.csv` defines the ε alleles on exactly those two variants, and the 0.8
study-orphan check counts a defining variant as one the module carries.

**KL-VS × ε4 is one combination row that replaces what it names.**

```
diplotypes[gene=KL, haplotype_a=KL-VS, haplotype_b=ref] & diplotypes[gene=APOE, haplotype_b=ε4]
```

`haplotype_b=ε4` reads "an ε4 carrier" because a diplotype pair is stored with
`haplotype_a <= haplotype_b` and ε4 sorts last, so the existential selector matches ε2/ε4, ε3/ε4 and
ε4/ε4. `meta.parquet` lists the four rows matched (the KL heterozygote and the three APOE rows), and
`replaces` is true: a consumer whose genome matches both members shows this row's finding in place of
those four. Its `tier` (C) is about the combination, so it never reaches a member row in
`meta_resolved.parquet`. Belloy et al. 2020 (PMID 32282020): KL-VS heterozygosity was associated with
reduced AD risk in APOE4 carriers aged 60 and older, more prominently at 60 to 80.

## Sources

PMIDs checked against PubMed by title on 2026-11-04: 30642433 (Timmers 2019, parent lifespans),
31413261 (Deelen 2019, longevity GWAS meta-analysis), 32282020 (Belloy 2020, KL-VS and APOE4). No row
carries a `provenance_quote`. Coordinates come from the provisioned Ensembl cache through `enrich`.

## What building it broke

Nothing in the compiler. Two things the author has to know:

- The KL `ref` haplotype must be defined in `haplotypes.csv` (rs9536314 T, rs9527025 G), or the
  star-allele definition check reports it as used but undefined. The audit's rows left it implicit.
- The ε2/ε4 tie is settled only per column. A diplotype row that states one fact leaves every other
  disagreeing fact withheld, so an author who wants a fully resolved ε2/ε4 states each column there.
