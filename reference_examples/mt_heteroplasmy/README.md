# MT-TL1 heteroplasmy — the level is the finding, and the tissue changes what it means

The third adversarial probe. Mitochondrial disease is the case the binning primitive was built for —
the module holds no measurement, the consumer supplies a heteroplasmy fraction, and the table says
what that fraction means — so it is the right place to ask whether the primitive actually holds a
real module.

Two MELAS-causing MT-TL1 variants (m.3243A>G and m.3271T>C), binned in blood and in muscle. It found
one blocking defect and one that is provably unfixable without a design decision.

## Why heteroplasmy is genuinely hard

mtDNA is present in hundreds of copies per cell, and a pathogenic variant occupies some **fraction**
of them. Below a threshold the cell compensates and there is no phenotype; above it, there is. Two
things make that awkward to annotate:

- **The threshold is tissue-specific.** Blood heteroplasmy for m.3243A>G declines with age and
  systematically under-represents the burden in post-mitotic tissue, so the same 35% means
  MELAS-spectrum risk in blood and unremarkable in muscle. `HeteroplasmyRow.tissue` is in the key for
  exactly this, and it works.
- **The threshold is variant-specific.** m.3243A>G and m.3271T>C both cause MELAS and do not share a
  threshold.

## 1. One gene, two variants — the table could not say which (fixed)

`HeteroplasmyRow` keyed on `(gene, reference_sequence, tissue)` and carried **no variant identity at
all**. So both variants' bins landed in one group, `validate_bins` saw `[0, 0.099]` overlapping
`[0, 0.149]`, and refused — as an **error**, so the module could not compile.

No workaround existed. `trait_efo_id` is in the group key and would have separated them, but both
variants cause MELAS, so using two ontology ids would mean falsifying the data to satisfy the tool.
The alternatives were one module per variant (defeating "one CSV = one concern") or dropping a real
annotation.

`HeteroplasmyRow` now carries `rsid` / `chrom` / `start` / `ref` / `alts`, mirroring
`PharmVariantRow` exactly, and enters the key through a derived `variant_key` property. The columns
are **optional**, so a single-variant table groups precisely as it did before (P3/P8). `alts` is part
of the derivation because MT-ATP6 m.8993T>G and m.8993T>C are the same base with different alleles
and different phenotypes.

The documented example in `REFERENCE_EXAMPLES.md` §4 only ever showed one variant per gene, which is
why the limitation was invisible rather than decided — the schema generalized from a one-variant case.

## 2. A continuous measure cannot be tiled at all (surfaced — [RM35](../../docs/ROADMAP.md))

Compiling this module emits four coverage-gap warnings, and **no authoring fixes them**. Three rules
are jointly unsatisfiable on a continuous scale:

- bounds are inclusive at both ends,
- overlapping bins are an **error**,
- any positive hole is a **warning**.

So two adjacent bins either share an endpoint — an overlap, and a measurement of exactly `0.1` would
select two phenotypes — or they do not, leaving a hole. No epsilon escapes it; `[0, 0.0999999]` and
`[0.1, 1.0]` still warn. Every `allele_fraction` and `prs_percentile` table must therefore carry a
finding forever.

Integer kinds are fine: HTT `[6,35]`, `[36,39]`, `[40,∞)` is genuinely gapless because the domain is
discrete — which is where the inclusive convention was generalized from, and why this was missed. The
fix is a semantic decision (half-open intervals for continuous kinds, or dropping the continuous gap
check), so it is recorded rather than guessed at.

## What the module says, and what it refuses to say

Each variant/tissue group carries an explicit `unresolved` sentinel. That is the load-bearing part:
**an absent measurement selects it, never the lowest bin.** No heteroplasmy read is not a low
heteroplasmy read, and the conclusions say so — the low-blood row tells a reader to measure urine or
muscle before reassuring anyone, because blood is the tissue most likely to look innocent.

`variants.csv` carries the two variants as **homoplasmic** single-allele genotypes, which is the other
half of the mitochondrial shape (§4). `requires_callable=true` with `callable_from=DP`: a
mitochondrial no-call is not a reference call, and at these loci that distinction is the whole
finding.

## Reproduce

```bash
just-dna-compiler validate reference_examples/mt_heteroplasmy
just-dna-compiler compile reference_examples/mt_heteroplasmy out/mt_heteroplasmy
```
