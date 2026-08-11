# HTT CAG repeat — a quantity-binning module

The reference example for the **binning** path: a module with no variants, no studies, and no
coordinates — just a measured quantity mapped to a phenotype by range.

## What it is

Huntington disease CAG repeat-length interpretation for `HTT`, as four bins plus a sentinel:

| CAG count | Interpretation |
|---|---|
| ≤ 26 | normal, meiotically stable |
| 27–35 | intermediate — the carrier is not at risk, but the allele may expand in offspring |
| 36–39 | reduced penetrance — disease may or may not develop in a normal lifespan |
| ≥ 40 | fully penetrant; earlier onset with longer repeats |
| *(no count)* | `unresolved` — the locus was not spanned; no interpretation is made |

## Why it looks like this

**The module holds no measurement.** The repeat count comes from the consumer's caller
(ExpansionHunter or another span genotyper) at query time; the table only says what a count *means*.
That is the data-agnostic rule, and it is the reason this module is expressible at all without a
single coordinate — the locus is named by `(gene, repeat_unit)`, not by a position.

**`repeat_unit` is part of the key, not decoration.** A count of 40 means nothing without the motif
it counted, and two callers using different motif definitions produce incomparable numbers. The
duplicate/overlap rules group on `(gene, repeat_unit)` for exactly this reason.

**`source_field=REPCN` binds the table to a VCF without any glue.** It is a declarative pointer — a
bare field name, never an expression — naming where in an ExpansionHunter VCF the count lives
(`FORMAT/REPCN`, with `INFO/RU` carrying the motif). The consumer reads the field; the module never
computes anything.

**The `unresolved` row is mandatory, and it is not the same as "normal".** A short-read caller that
cannot span a long expansion returns no confident count, and the failure mode this row prevents is
exactly the dangerous one: falling through to the lowest bin would report a possible expansion
carrier as normal. A missing measurement selects the sentinel, never the reference bin.

**The reference bin is authored explicitly** (`6–26`), so every count lands in exactly one bin.
`validate_bins()` rejects overlapping resolved bins as an error and warns on interior gaps; because
`repeat_count` is an integer kind, adjacent bins (`27–35`, `36–39`) are treated as contiguous.

**No `variants.csv`, so no `studies.csv` — and this module is the reason that is a tracked gap.** One
CSV = one concern, and grounding evidence is mandatory only where variants are, so these four
thresholds compile green under `--strict` with no citation anywhere. That is the wrong way round: 26/27
and 35/36 and 39/40 are clinical judgements drawn from a specific literature, and they are exactly the
numbers a reader would want to check. Since 0.5.4 the compiler says so — a binning table stating
thresholds in a module with no study rows warns in both modes.

You *can* add a `studies.csv` here: it is accepted in a module carrying no `variants.csv`, and it
silences the warning. What it cannot do is name one bound — a study row identifies its subject by rsid
or `chrom`+`start`, and a `(gene, repeat_unit)` row has neither — so the citation grounds the module,
not the 36. Closing that properly is **RM47**; the thresholds here are the established clinical ones and
are left uncited deliberately, so this example keeps showing the gap.

## What it deliberately does not contain

**5-HTTLPR-style alleles.** A repeat *count* is not the same shape as a biallelic short/long
structural indel, and `S`/`L` are not nucleotides — that is RM5 (symbolic alleles), not something to
smuggle into a count. **Forensic microvariant notation** (`TH01 9.3` = nine repeats plus three bases)
is an allele *name*, not the decimal 9.3, and never belongs in a numeric bound. Neither affects
pathogenic-threshold loci like this one.

## Rebuilding it

Nothing here needs the network — there is no rsID to resolve and no coordinate to fill, so the
enricher has no work to do on this module.

```bash
uv run just-dna-compiler validate reference_examples/htt_repeat_expansion
uv run just-dna-compiler compile  reference_examples/htt_repeat_expansion out/htt
uv run just-dna-compiler verify   out/htt --no-require-marketplace
```

Round-trip (Principle 7) — the digest is a fixed point, and the reversed CSV differs from the
authored one only in **column order and cell quoting**, which reverse normalizes by design:

```bash
uv run just-dna-compiler reverse out/htt out/htt_reversed
uv run just-dna-compiler compile out/htt_reversed out/htt_again   # same digest
```

Starting a table of your own from the same shape:

```bash
uv run just-dna-enricher template repeat_alleles.csv > my_module/repeat_alleles.csv
```
