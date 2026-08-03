# CYP2C19 star alleles — a PGx module drafted from CPIC

The PGx counterpart to [`hfe_hemochromatosis/`](../hfe_hemochromatosis/), and the interesting thing
is how *differently* the two behave. The ClinVar panel came back with a hole a human had to fill.
This one came back **complete** — every column the models require was published — and what a curator
has to do instead is decide what to *remove*, and notice what the source never had.

## How it was built

```bash
just-dna-compiler scaffold reference_examples/cyp2c19_star_alleles --name cyp2c19_star_alleles
just-dna-enricher draft reference_examples/cyp2c19_star_alleles --gene CYP2C19 --use non-commercial
# ... curation, below ...
just-dna-enricher enrich reference_examples/cyp2c19_star_alleles --offline
just-dna-compiler compile reference_examples/cyp2c19_star_alleles out/
```

811 rows across three tables, no placeholders, valid immediately. `--use non-commercial` is required
rather than polite: CPIC's terms forbid sale, so a draft is **skipped** when the use is unstated and
**refused** when it is commercial — the terms are accepted by taking the data, so the check happens
before anything is fetched.

## What the curator removed, and why a warning existed to prompt it

CPIC pairs every allele it knows into diplotypes, including alleles whose defining variants it does
not publish in a form this format can hold. `*36`, `*37` and `*42` arrived used across 71 diplotype
rows — two of them declared `no_function` — and defined in `haplotypes.csv` by nothing at all. A
star-allele caller can never emit an allele nothing defines, so every row about them was dead.

That is a cross-table redundancy the compiler can settle without any reference, so it now does:

```
warning: Star allele(s) used but not defined in haplotypes.csv: ['*36', '*37', '*42'].
         A consumer's caller cannot emit an allele nothing defines, so rows about it can never match.
```

The curation here was to drop them (666 → 595 diplotypes). A module that leans on an *external*
caller's definitions could legitimately keep them, which is why this is a warning and not an error —
and why the check only runs when `haplotypes.csv` is present at all.

## What CPIC could not express, reported rather than coerced

* **IUPAC ambiguity codes.** `*2`, `*4` and `*35` each have one defining variant CPIC records as `R`,
  `Y` or `M` — a *set* of nucleotides, not a nucleotide. `HaplotypeRow.allele` takes ACGT, so those
  rows are skipped with a warning rather than guessed. The alleles survive: each has other defining
  variants, so `*2` and `*4` are still callable — just from fewer positions than CPIC lists.
* **No numeric activity score.** All 666 diplotypes carry CPIC's `n/a`, which means *CPIC did not
  score this pair* — an absence, so the cell is simply empty. (Distinct from a value like `≥3.0`,
  which is a real bound the numeric bin columns cannot hold; the provider now says which it saw
  instead of calling both "an inequality".)
* **No chromosome.** CPIC's `sequence_location` publishes `genesymbol`, `dbsnpid` and `position` and
  no chromosome column, so a defining variant is identified by rsID or not at all — see below.

## What is deliberately *not* here: drugs

`DiplotypeRow` can carry `drug`, `evidence_level` and `recommendation_strength`, and every one is
empty. This module answers **genotype → metabolizer phenotype** and stops there. CPIC publishes
prescribing recommendations in a separate resource the provider does not read, so filling those
columns would mean inventing them — and a CYP2C19 module that named clopidogrel without CPIC's actual
recommendation text would be worse than one that stays silent. Adding that is roadmapped, not done;
the module's name says star alleles, not clopidogrel, for the same reason.

## What drafting a real gene taught the tooling

Three fixes, all in the provider rather than worked around here:

1. **`draft --gene CYP2C9` crashed** with a raw pydantic traceback. The skip guard checked "no rsID
   *and* no position", but `HaplotypeRow` needs an rsID *or* chromosome **and** position — and CPIC
   never publishes a chromosome. 18 CYP2C9 defining variants have a position and no rsID, as do 14 in
   TPMT and 4 in NUDT15. CYP2C19 has none, which is exactly why the provider looked fine. A guard
   that does not match the model it builds is not a guard.
2. **`n/a` was reported as "an inequality rather than a number"**, which is simply the wrong reading
   of it, and it was emitted once per row — ~600 identical lines for this gene, and 2,184 for CYP2C9,
   burying every other finding. Now classified and aggregated, with the total stated.
3. **Nothing recorded CPIC as a source.** The provider checked the licence before fetching and then
   wrote no `SourceRow`, so a module built entirely out of CC BY-SA no-sale data carried no
   `sources.csv` and the compile gate had nothing to refuse on. That is the `clingen.py` bug, in the
   newest provider. `sources.csv` here is the fix; strip its `declared_use` and the compile fails.

## Files

| file | authored by |
|---|---|
| `module_spec.yaml` | `just-dna-compiler scaffold`, then filled by hand |
| `haplotypes.csv` | `draft --gene CYP2C19` (CPIC allele definitions) |
| `allele_function.csv` | `draft`, minus the alleles nothing defines |
| `diplotypes.csv` | `draft`, minus pairs using those alleles |
| `sources.csv` | `draft` (CPIC: CC BY-SA 4.0, no sale) |
| `resolution.csv` | `just-dna-enricher enrich --offline` |
