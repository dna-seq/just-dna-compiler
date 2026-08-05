# XG and SPRY3 — annotation across a pseudoautosomal boundary

Built to answer the question [RM32](../../docs/ROADMAP_HISTORY.md) left open: *is a pseudoautosomal
locus one place or two, and whose decision is that?* The SHOX panel
([`shox_par1/`](../shox_par1/README.md)) showed the symptom — ten findings compiling to twenty rows.
This module is the control that decides the shape of the fix.

## Why these two genes

They are the only two genes that **straddle** a pseudoautosomal boundary in GRCh38, and they straddle
in opposite directions:

| Gene | Span (GRCh38) | Boundary it crosses |
|---|---|---|
| **XG** (Xg blood group) | X:2,751,798–2,816,500 | runs **out of** PAR1, which ends at 2,781,479 |
| **SPRY3** (Sprouty homolog 3) | X:155,612,298–155,782,459 | runs **into** PAR2, which starts at 155,701,383 |

That makes them the case that settles the design. If "pseudoautosomal" were a property of a *gene* —
or worse, of a module, which is what a `--par` compile flag would have made it — then either gene would
be classified wrongly for half of itself. It is a property of the **locus**, and nothing coarser can be
correct.

The three alleles here are real ClinVar records with ClinVar's own citations, drafted with
`draft-panel`. They are all **benign**, and that is honest rather than incidental: the module exists for
the coordinate mechanics, so it carries the grounding evidence a module must carry and makes no clinical
claim it cannot support. A benign annotation is still a real one — it is what stops a consumer flagging
the allele.

## What it demonstrates

One `enrich` run, one module, and the verdict differs per row:

```
pseudoautosomal: kept the X spelling of 1 locus/loci; left out rs184115031 Y:56960499
```

| rsID | Gene | Resolved | In a PAR? | Partner | Rows |
|---|---|---|---|---|---|
| `rs184115031` | SPRY3 | X:155,773,979 | **yes** (PAR2) | Y:56,960,499 | 1 — the Y twin is left out |
| `rs12395656` | XG | X:2,808,207 | no | — | 1 — never a candidate |
| `rs202025841` | XG | X:2,811,333 | no | — | 1 — never a candidate |

**The PAR2 coordinates are the point.** PAR1 happens to be coordinate-identical on X and Y, so the SHOX
panel could have been "fixed" by a shortcut that pairs the same base on the two contigs. PAR2 would have
silently defeated it: X:155,773,979 and Y:56,960,499 are the same place at a constant offset of
98,813,480, which is what `vrs.par_partner` computes from the interval table rather than assuming.
Ensembl confirms the pairing independently for both SPRY3 alleles.

Selecting X follows the sources rather than the consumer. Probed 2026-08-04: ClinVar records **no**
variant in either PAR on Y (all 677 of its Y records lie outside them), gnomAD v4 excludes the Y PAR from
its callset entirely, and the ClinGen Allele Registry does mint a separate Y allele id but leaves the
record a bare dbSNP cross-reference. Only the coordinate resolver reports both.

## The round trip, which is why this is the enricher's decision and not the compiler's

```
compile → reverse → compile
digest                sha256:bf0fc867…  (unchanged)
content_signature     sha256:7bd0073c…  (unchanged)
resolution_signature  sha256:3e6dea31…  (unchanged)
```

A fixed point, including `resolution_signature`. That is the whole argument: the choice is recorded in
`resolution.csv`, which is injected data and travels with the module, so reverse re-emits it and the
recompile agrees. A compiler flag could not do this — `reverse_module` rebuilds the spec from parquet
alone, so the third step would diverge (Principle 7).

## Keeping both, for an unmasked reference

A consumer whose reference is not analysis-set masked can have both spellings:

```bash
just-dna-enricher enrich <spec> --keep-par-twin
```

which yields 4 rows instead of 3, and the compiler then names the pair for what it is rather than
reporting it as a paralog:

```
warning: rs184115031 is pseudoautosomal: it maps to 2 loci (X:155773979 and Y:56960499) that are
1 place(s) … count distinct findings by rsid rather than by row
```

## Three things building it found, none about PAR — all since fixed

**1. `draft-panel --clin-sig uncertain_significance` drafted nothing, and said only
`state: Field required`.** Twenty-six times, one identical line per row, no count and no explanation.
The underlying *decision* was right and documented — `_STATE_BY_CLIN_SIG` folds only the four decided
calls, because `VALID_STATES` has no "undecided" member and every candidate asserts something ClinVar
did not (`neutral` says benign, `risk` says a direction). But `state` is required, so a correct refusal
to guess became a **silent drop** of the conclusion, phenotype, `clin_sig` and citations already
assembled. `state` is now stubbed like `genotype` — the same shape, and what `PartialRow` is for — so
XG at 1★ drafts 26 rows where it drafted 0, and the compiler names both columns when it refuses.

**2. The genotype worklist named rows that did not exist.** It was handed every candidate record rather
than the rows that landed, so a "3 row(s) carry a placeholder" header came with a 27-line worklist
covering refused and already-present rows too. It now covers exactly what was added.

**3. The run summary added rows across tables.** `added 7 row(s)` for what the per-file lines correctly
reported as `variants.csv: 3 added` and `studies.csv: 4 added` — a number matching neither file. The CLI
reports per table now.

This module still carries the three **benign** alleles it was first built from, rather than being
re-drafted to include the uncertain ones. That is deliberate: the boundary mechanics are what it exists
to demonstrate, three loci show them exactly as well as twenty-six would, and a module whose every row is
`uncertain_significance` would be a worse example to copy.

## Reproduce

```bash
just-dna-enricher draft-panel reference_examples/par_boundary --gene XG --gene SPRY3 \
    --clin-sig benign,likely_benign --min-review-stars 1 --snapshot <clinvar-snapshot>
# then decide each genotype from the allele pairs the draft reports — unphased alleles are
# alphabetically sorted, which the model tells you if you get it wrong
just-dna-enricher enrich reference_examples/par_boundary --no-clinvar
just-dna-compiler compile reference_examples/par_boundary out/par_boundary
```

Adding `uncertain_significance` to that `--clin-sig` list is how finding 1 above turned up, and it now
drafts 23 more rows carrying a second placeholder. The module keeps the three decided calls.

`--no-clinvar` is deliberate, and it is worth knowing why. The chain is first-hit-wins, so with the
ClinVar link enabled ClinVar answers — and since it holds no Y-PAR record, the table comes out X-only
for a completely different reason, and the selection never runs. Same table, two different mechanisms;
forcing the Ensembl link is what makes this module exercise the one under test.
