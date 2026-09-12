# Use a compiled module

You have a module directory and want to report on somebody's genotype. This page is the consumer's
side of the seam: what is in the artifact, what you must check before trusting it, and the two
obligations the format puts on you rather than on the module.

The authoritative field-by-field reference is [SCHEMAS.md](SCHEMAS.md); this is the working order.

## What you received

```text
apoe_epsilon/
├── haplotypes.parquet     one parquet per table kind the module uses
├── diplotypes.parquet
├── manifest.json          identity, build, licence, stats, digests, warnings
└── README.md              optional, authored
```

A module carries **only the kinds it uses**. There is no fixed file list and no empty parquet standing
in for a domain the module has nothing to say about, so read `manifest.json` first and let it tell you
what is there.

Three parquets form the SNP core (`variants`, `weights`, `studies`) when a module is variant-shaped;
a PGx module like this one is haplotype-shaped instead. `manifest.artifact.files[]` is the complete
list, and it is the same list `verify` hashes.

## 1. Verify before you install

```bash
just-dna-compiler verify ./apoe_epsilon --public-key <base64-raw-ed25519>
```

Exit 0 or exit 1, nothing to parse. It re-hashes every file in `artifact.files[]`, recomputes
`artifact.digest` over the set, and checks the Ed25519 signature against the key you pin. Omit
`--public-key` and it will report `signature: absent` rather than fail — pinning is how you demand one.

Add `--no-require-marketplace` for anything you compiled yourself; the default demands
`compiled_by=marketplace-server`.

If you would rather not shell out, `just-dna-format` is the dependency-light way to do the same thing
in-process — that is the whole reason the tier exists, and it costs you pydantic plus cryptography.

### The two digests answer different questions

| Field | Covers | Moves when |
|---|---|---|
| `artifact.digest` | the emitted **bytes** | a recompile, a codec change, a compiler upgrade |
| `content_signature` | the **claims** | an authored value changes — and not otherwise |

Cache on `artifact.digest`. Decide *whether the module actually says something new* with
`content_signature`. Confusing the two is the most common integration bug here, and
[the FAQ](FAQ.md) leads with it.

## 2. Read the tables

Plain parquet, no custom container. Anything that reads parquet reads a module.

```python
import json
from pathlib import Path

import polars as pl

module = Path("apoe_epsilon")
manifest = json.loads((module / "manifest.json").read_text())

build = manifest["genome_build"]          # 'GRCh38' — it lives HERE, in no parquet column
haplotypes = pl.read_parquet(module / "haplotypes.parquet")
```

!!! warning "`genome_build` is a manifest field and not a parquet column"

    Every coordinate in every table is in the build the manifest names, and nothing in the parquet
    repeats it. A pipeline that joins two modules must read both manifests — mixing a GRCh37 module
    into a GRCh38 join produces coordinates that look fine and are wrong by thousands of bases.

`start` is the **1-based VCF position**, not a 0-based offset. Do not subtract one.

### Identity

`variant_key` is the join key, minted as rsID → VRS allele id → `chrom:start:ref[:alts]`, in that
order. It is a string, it is stable across recompiles, and it is what the derived tables key on.

## 3. The join contract — two obligations that are yours

A module supplies the annotation; you supply the measurement. Two things the module cannot do for you:

### Absence is not reference

> A conforming consumer **MUST** distinguish a covered reference call from a no-call before asserting
> any reference or absence interpretation, and **MUST NOT** read "absent from a variant-only callset"
> as hom-reference.

Absence from a variant-only callset means the site matched the reference **or** was never callable.
Collapsing those two fabricates a confident reference genotype, and it fails in the dangerous
direction: for a carrier row, or for the reassurance that a pathogenic variant is absent, it is the
difference between *screened negative* and *not screened*.

The module tells you where this bites:

| Column | Says |
|---|---|
| `requires_callable` | the *absence* of this variant is the informative call. Without callability data, withhold the conclusion rather than assert the reference one. Blank is not `false` |
| `callable_from` | which VCF field carries the proof (`FORMAT/DP`, `FORMAT/GQ`, `FORMAT/FT`) — a pointer, never an expression |
| `quality_from` + `min_quality` | the floor below which what *was* seen is not good enough to act on. A floor you cannot evaluate is unknown, never satisfied |
| `unresolved` (binning tables) | the no-call sentinel. A missing measurement selects it, and never the lowest or reference bin |

This is the house tri-state rule pointed at you: **true / false / unknown, and `None` is never
`False`.** When the answer is unknown, withhold — do not report and do not negate.

### A row is about a (locus, genotype) pair, and some pairs were never authored

An rsID that resolves onto several loci is paired with each of them, so K authored genotypes at one
rsID become K×N rows. ClinVar's reciprocal duplication/deletion pairs are the usual instance: a
genotype written for the duplication lands beside the deletion's `ref` as a **well-formed reference
homozygote** that the author never claimed anything about.

Joining by position is unaffected — nothing matches those rows, which is why this went unnoticed for a
release. Classifying rows, counting them, or asking "what does this module say about someone who is
reference here" reads them as statements, and they are false ones. A reporting consumer found this
with 2,579 such rows queued into a genome's pathogenic section, caught before rendering.

`manifest.compilation.expanded_keys` and `expanded_rows` tell you whether a module contains expansion
rows and how many. Both are `None` where resolution did not run — never `0`, which would claim someone
looked and found none.

## 4. Check what you are allowed to do with it

Licensing is **data**, carried in the module's own licence table and summarised in the manifest — it is
never a compiler flag and never a mode. Three axes, and they are independent:

- **`declared_use`** — what the module was compiled for. Three states, not a boolean.
- **`redistribution`** — recorded, and deliberately *not* gated yet.
- unknown terms — a source may publish no licence at all. That **warns**; it does not gate.

A module built from ClinPGx, CPIC or PharmVar is research-only and no-sale, and the compile gate keys
on `sources.csv` and nothing else. If you are building a commercial product, read the sources block
rather than the headline licence.

## Where to go next

- **[SCHEMAS.md](SCHEMAS.md)** — every model, every column, the vocabularies and the hash family.
- **[MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md)** — where a module comes from and what a second version
  moves.
- **[FAQ.md](FAQ.md)** — settled questions, keyed by the question you would actually ask.
- **[Upgrading to 0.7](INTEGRATION_0_7.md)** — the surface delta, including the one break for an old
  reader.
