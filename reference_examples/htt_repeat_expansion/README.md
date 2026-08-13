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

**`source_field=FORMAT/REPCN` + `source_element=largest` binds the table to a VCF without any glue.**
It is a declarative pointer — a field name, never an expression — naming where in an ExpansionHunter
VCF the count lives (with `INFO/RU` carrying the motif). The consumer reads the field; the module never
computes anything.

**Both halves of that pointer were re-authored in 0.6, and the second one was a wrong answer waiting
to happen (RM53/RM54).** It used to read `source_field=REPCN` alone. `REPCN` returns **one count per
allele**, and Huntington disease is dominant: the clinical rule is *the larger of the two*. A consumer
that averaged the pair, took the first, or took the shorter allele got a well-formed number and a wrong
answer, and every offline gate passed — including `--strict`, which is the mode this README prints.
There was nowhere in the schema to say "larger", so `source_element` was added as a closed set of named
selection rules (an index like `REPCN[max]` was refused: it is the first line of an expression grammar,
which the charter's declarative-not-code principle exists to keep out). The namespace was added at the
same time for the same class of reason — INFO and FORMAT are two key tables that collide on seven
names. `content_signature` and `artifact.digest` both moved; that is a correction, not a regression,
and the round trip was re-verified rather than assumed.

`largest` rather than `largest_alt` is deliberate and the pair exists because of a trap: on a
`Number=R` VCF field the reference is element zero, so "the larger of the two" has two answers. `REPCN`
has no reference element — both values are the sample's own alleles, and the longer one may perfectly
well be the reference-length one — so the rule that ranges over every value is the right one here.

**"Element" does not mean "VCF `Number` slot", and `REPCN` is why.** ExpansionHunter reports both
alleles in a *single* cell (`17/42`, half-repeats and all), rather than as two values of a
multi-valued field. A selection rule defined strictly over `Number` would therefore have had nothing
to say about the one case it was built for. So the rule names *one of the values the field carries for
this record*, and how the caller encodes that multiplicity is the caller's business — the format holds
no opinion on it, which is the same inject-only line that keeps every other source convention out of
these tiers. The module states which value it means; the consumer knows how to get it.

That is also why the compiler stays quiet here rather than prompting for the rule: `REPCN` is
ExpansionHunter's key and not the spec's, so this tier is not entitled to assert its cardinality. The
warning exists for the keys the spec *does* define — point this table at `FORMAT/AD` with no
`source_element` and it fires.

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
