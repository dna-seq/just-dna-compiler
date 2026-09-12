# Resolve, draft and enrich

The enricher is the only package that fetches anything. It does two jobs: it **produces** the
`resolution.csv` the compiler consumes, and it **drafts** rows from a source so you are not
transcribing a database by hand. [ENRICHER.md](ENRICHER.md) is the reference — the full resolver
chain, the check table, the rate limits, the caches and the open questions the code does not answer.

Everything here reports. Nothing here repairs your authored values.

## 1. Resolve — where coordinates come from

```bash
just-dna-enricher enrich ./my_module
```

It reads every table that can ask for a coordinate — `variants.csv`, `pharm_variants.csv`,
`haplotypes.csv` — works out which rows still need something (an rsID with no coordinate, a coordinate
with no rsID), and writes `resolution.csv` beside the spec.

The chain is **first-hit-wins**, in this order:

1. **What is already there.** A `resolution.csv` beside the spec is authoritative and never clobbered.
   A `variant_key` it already covers is skipped entirely.
2. **Local Ensembl cache** — DuckDB lookups, offline.
3. **HuggingFace snapshot** — fetched if no cache is present. A static slice of popular rsIDs, not a
   canonical reference, so a miss falls through rather than answering.
4. **ClinVar snapshot** — for what Ensembl missed. It sits *after* Ensembl deliberately: `alts` is a
   resolution fact that flows into the artifact digest, and Ensembl carries every dbSNP allele where
   ClinVar carries only its submitted ones. A variant both know keeps the Ensembl answer, so no
   already-compiled module's digest moves.
5. **Live Ensembl** — V2 GraphQL, falling back to V1 REST.
6. **gnomAD** — last.

### Three outcomes, not two

A lookup answers with loci, answers with *nothing found*, or **could not be asked**. Those are
different facts and the table records them differently — an unreachable rsID leaves **no
`resolution.csv` row at all**, rather than a row claiming absence.

This matters most under `--offline`, where "nobody asked" is the common case:

```bash
just-dna-enricher enrich ./my_module --offline    # cache-only, never touches the network
just-dna-enricher enrich ./my_module --strict     # fail unless every variant resolves
```

`--strict` refuses rather than half-writing: an enrich run is a transaction, and a refused one commits
nothing.

### The build

`enrich` is GRCh38-bound. A module declaring another build gets a warning, **no** link is run and **no**
lookup result is recorded — not even `not_found`, which would claim a source was asked. Your authored
coordinates are still transcribed verbatim, under the module's own build.

`genome_build` lives in the manifest and in no parquet column, so the module's declaration is what
decides this.

### The checks it runs while it is there

Each is a flag, each defaults on, and each **reports**:

| Flag | Asks |
|---|---|
| `--verify-ref` | does each authored `ref` match the reference sequence? |
| `--verify-clinsig` | does each authored `clin_sig` match ClinVar's own? (warns, never fails) |
| `--verify-rsids` | is each rsID current in dbSNP, or merged, or withdrawn? |
| `--vrs` | mint GA4GH VRS allele ids onto resolved rows |

A disagreement is a finding, not a correction. The enricher will tell you that an authored `ref`
disagrees with the reference sequence; it will not write the reference's value into your file.

## 2. Draft — rows from a source

```bash
just-dna-enricher draft ./my_module --gene CYP2C9
just-dna-enricher draft-clinpgx ./my_module --snapshot ./clinpgx --drug warfarin
just-dna-enricher draft-panel ./my_module --gene BRCA1
just-dna-enricher draft-repeats ./my_module --gene FMR1
```

Drafting **appends, never mutates** — new rows go at the end, and a partial row validates by omission
and matches on `match_on` rather than the natural key. Where a human must decide something, the
drafter writes a **placeholder** rather than a plausible value, and a generated stub is built so that
it *cannot* compile. Both are deliberate: a tool that guessed would hide the decision.

Every provider writes its own `licensing.csv` row, keyed `(source, layer)`, inside the same atomic
commit as the rows it drafted. The compile gate keys on that file and nothing else, so a module drafted
from a licensed source arrives already carrying what the gate reads. (`sources.csv` is the older
spelling of the same file — still read, deprecated, removed at 1.0; a module carrying both is refused.)

!!! warning "Licensing follows the source, and some of it is research-only"

    ClinPGx, CPIC and PharmVar are CC BY-SA with no-sale terms. PharmVar needs your own key and its
    cache is unpublishable. A source may also publish no licence at all — unknown commercial terms
    **warn**, they do not gate. Read `licensing.csv` before shipping anything commercial.

## 3. Caches and snapshots

```bash
just-dna-enricher cache status      # what each lane has, and what it is missing
just-dna-enricher cache prepare     # pre-provision
just-dna-enricher cache rebuild
just-dna-enricher cache prune       # asks before deleting
```

A lane has three stages, and where one is absent the status says **why** as a field rather than
leaving you to guess. A derived lane also names its parents: an absent parent is *could not run*,
never *an empty result*, and a parent that moved and a parent that is gone are different instructions.

Snapshot builders (`clinvar`, `cpic`, `civic`, `mane`, `strchive`, `mitomap`, `gnomad`, `pubmind`,
`pharmvar`, `alphagenome`) are the operator surface — you build them once and the deployment reads
them, rather than every request reaching the source. Which of them may be *published* is a licence
question answered per source, and the command's help says which.

## 4. One command for the whole loop

```bash
just-dna-enricher enrich-and-compile ./my_module ./out
```

Resolve, then compile, in one call.

## Look something up without writing anything

```bash
just-dna-enricher hint variant rs429358
just-dna-enricher hint citation 12345678
just-dna-enricher hint gene APOE
```

`hint` reports what is known about a variant or a citation and writes nothing — no authored cell, no
table row. `litvar coverage` answers which papers a variant-literature index holds for a module's
alleles, **and at which tier**, because allele-resolved, position-only and absent are three different
answers to "is there literature on this".

## Where to go next

- **[ENRICHER.md](ENRICHER.md)** — the reference, including the open questions.
- **[Compile a module](COMPILING.md)** — what happens to the `resolution.csv` this produced.
- **[CACHE_SURFACE.md](CACHE_SURFACE.md)** — what a cache lane is, and the checklist for adding one.
- **[CLI reference](https://just-dna.life/just-dna-compiler/cli/)** — every command and
  flag, generated from the tool itself. It is written at build time from the live command tree,
  so it exists on the site and not in this repository.
