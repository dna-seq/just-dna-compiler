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
├── sources.parquet        the licence table (authored as licensing.csv)
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

!!! warning "An indel's coordinates are left-aligned only where the enricher filled them"

    The compiler cannot normalize an indel: left-alignment reads the reference sequence around the
    event, and the compile path has none. Since 0.8 the enricher writes a coordinate it **fills** from
    an rsID in its leftmost parsimonious spelling, ALT by ALT — the spelling `bcftools norm -m -any -f
    <reference>` writes — so those rows join a normalized VCF exactly. Offline the enricher cannot
    left-align, but it still trims each ALT against its ref (RM381), so a split-snapshot site is written
    per ALT, never in the snapshot's padded multi-ALT frame. A coordinate the module's
    **author** wrote keeps its author's spelling, and VCF allows several spellings of one event: the
    Ensembl snapshot often writes an indel one base right of the left-aligned form your caller emits
    (CCR5-Δ32, `rs333`: `3:46373453 ACAGT…CCAGA>A` against `3:46373452 TACAGT…CCAG>T` in a GATK or
    DeepVariant VCF). `resolution.csv`'s `left_aligned` says which rows were checked, and a module
    built before 0.8 carries no such guarantee at all.

    **Join indels on `vrs_id` where you can mint VRS**, or normalize both sides before joining. Every
    variant parquet carries the GA4GH VRS allele id per ALT (`weights.parquet` `vrs_id`, a list
    parallel to `alts`), minted over the fully justified allele, so both spellings of one event carry
    one id and a different event carries another. Otherwise left-align and trim both sides the way
    `bcftools norm -f <reference>` does, or join on the rsID where the row has one. Substitutions are
    unaffected, since a single-base change has only one spelling. This was
    [RM270](ROADMAP_HISTORY.md#rm270--an-indels-artifact-key-is-its-sources-spelling-a-left-aligned-vcf-misses-a-respelled-row-and-the-spelling-independent-id-the-enricher-mints-never-reaches-the-artifact).

    **The genotype cell can be in a third spelling.** A row's `genotype` keeps its author's frame
    while `ref`/`alts` take the resolver's, so they can differ on one row: before RM270
    `reference_examples/shox_par1` carried `rs1569493663` as `genotype C/CAG` (ClinVar's frame) beside
    `ref=AGAG`, `alts=[AG, AGAGAG]` (Ensembl's). Comparing the genotype's alleles with your VCF's by
    string equality misses such a row. Reduce both sides first with
    `just_dna_format.alleles.parsimony_reduce`, which is pure Python with no dependencies: it strips the
    flank a set of alleles shares, so `{C, CAG}` and `{AGAG, AG}` both become `{'', 'AG'}`. It cannot
    reconcile a homozygous indel call, because one allele has no flank to strip (see
    `alleles.event_profile`). This is RM31's consumer half, which until 2026-09-27 lived only in its
    closing entry.

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

Every one of those columns has three states, not two: **true, false, and unknown — and a blank cell is
unknown, never false.** When the answer is unknown, withhold it. Do not report it and do not report
its opposite. The same rule runs through the rest of the schema, so a consumer that collapses blanks
to `false` anywhere will be wrong in the same direction everywhere.

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

A module built from ClinPGx, CPIC or PharmVar is research-only and no-sale. If you are building a
commercial product, read the per-source rows rather than the headline licence: a host's terms are not
its contents' terms, so the licence at the top is a floor each record may override.

In a **compiled** module those rows are `sources.parquet` and `manifest.sources` — the authored file is
named `licensing.csv` (older spelling `sources.csv`), but the artifact keeps the old name for the whole
0.x line, because both are inside `artifact.digest` and renaming them waits for the major.

## 5. What 0.8 added to the artifact

Most additions are a new parquet, a new column or a new manifest key, which a 0.7 reader ignores. The
exceptions are the old-reader breaks in [INTEGRATION_0_8.md](INTEGRATION_0_8.md) § 1 (a 0.7
`just-dna-format` refuses a manifest carrying a warning code it does not know), so upgrade the format
tier first. The additions a reporting consumer meets:

- **`meta.parquet` and `meta_resolved.parquet`**, from an authored `meta.csv`. A `meta.parquet` row
  whose `replaces` is true is a finding about a combination: when every member matches the sample, it
  replaces the findings of the rows in its `matches`. `meta_resolved.parquet` gives each row's `tier`,
  `age_of_action` and flags after precedence, looked up by `(table, key, sex, drug)`. The manifest's
  `tier_scale` names the scale `tier` grades on.
- **`model_organisms.parquet`**: model-organism lifespan findings about a gene. Annotation only, never
  a weight.
- **`studies.parquet`** gains the study's size, ancestry, age band, stratum, LD proxy and effect unit.
  A `pmid` of `NONE` means the work has no PubMed record, and `doi` then names it: skip `NONE` when you
  parse PubMed ids.
- **`weights.parquet`** gains derived cells: `effect_unit`, `eur_only_evidence`, and three `outcome_*`
  cells that are true or null and never false.
- **`resolution_loci`**, on the variant and positional parquets, keeps the lookup's whole answer per
  locus, including `source_release` (the snapshot or service release that answered) and `source_loci`.
  Read its fields by name. It is not a join key: join on the row's own `chrom`/`start`/`ref`/`alts`,
  or on `vrs_id`.
- **Open Targets** (`locus_to_gene.parquet`, `colocalisations.parquet`, `consequences.parquet`) and
  **`ld_pairs.parquet`** appear only in a module the enricher's passes filled.

Run against three reference examples compiled into the working directory
(`just-dna-compiler compile reference_examples/<name> ./<name>`):

```python
import polars as pl

# A combination row, and what it replaces
meta = pl.read_parquet("apoe_klvs_meta/meta.parquet")
print(meta.filter(pl.col("replaces")).select("members", "tier", "match_count", "matches"))

# The per-row statements after precedence: look a row up by (table, key, sex, drug)
resolved = pl.read_parquet("apoe_klvs_meta/meta_resolved.parquet")
print(resolved.select("table", "key", "sex", "drug", "tier", "age_of_action").head(3))

# A study with no PubMed record is cited by its DOI
studies = pl.read_parquet("longevity_studies/studies.parquet")
print(studies.filter(pl.col("pmid") == "NONE").select("rsid", "pmid", "doi", "ancestry"))

# Which release answered each locus, kept inside resolution_loci
weights = pl.read_parquet("longevity_studies/weights.parquet")
loci = weights.select("variant_key", "resolution_loci").explode("resolution_loci").unnest("resolution_loci")
print(loci.select("variant_key", "chrom", "start", "source_release").unique(maintain_order=True).head(3))
```

```text
┌─────────────────────────────────┬──────┬─────────────┬─────────────────────────────────┐
│ members                         ┆ tier ┆ match_count ┆ matches                         │
╞═════════════════════════════════╪══════╪═════════════╪═════════════════════════════════╡
│ diplotypes[gene=KL, haplotype_… ┆ C    ┆ 4           ┆ [{0,"diplotypes",["KL", "KL-VS… │
└─────────────────────────────────┴──────┴─────────────┴─────────────────────────────────┘
┌──────────┬───────────────────────┬──────┬──────┬──────┬───────────────┐
│ table    ┆ key                   ┆ sex  ┆ drug ┆ tier ┆ age_of_action │
╞══════════╪═══════════════════════╪══════╪══════╪══════╪═══════════════╡
│ variants ┆ ["rs10455872", "A/A"] ┆ null ┆ null ┆ A    ┆ MIDLIFE       │
│ variants ┆ ["rs10455872", "A/G"] ┆ null ┆ null ┆ A    ┆ MIDLIFE       │
│ variants ┆ ["rs10455872", "G/G"] ┆ null ┆ null ┆ A    ┆ MIDLIFE       │
└──────────┴───────────────────────┴──────┴──────┴──────┴───────────────┘
┌────────────┬──────┬─────────────────────────────┬───────────┐
│ rsid       ┆ pmid ┆ doi                         ┆ ancestry  │
╞════════════╪══════╪═════════════════════════════╪═══════════╡
│ rs75571981 ┆ NONE ┆ 10.21203/rs.3.rs-6869504/v1 ┆ ["EAS"]   │
└────────────┴──────┴─────────────────────────────┴───────────┘
┌─────────────┬───────┬───────────┬─────────────────────────────────┐
│ variant_key ┆ chrom ┆ start     ┆ source_release                  │
╞═════════════╪═══════╪═══════════╪═════════════════════════════════╡
│ rs10455872  ┆ 6     ┆ 160589086 ┆ ensembl-variation-2026_07_13-v… │
│ rs429358    ┆ 19    ┆ 44908684  ┆ ensembl-variation-2026_07_13-v… │
│ rs646776    ┆ 1     ┆ 109275908 ┆ ensembl-variation-2026_07_13-v… │
└─────────────┴───────┴───────────┴─────────────────────────────────┘
```

(Shapes and dtypes trimmed from polars' output.) [INTEGRATION_0_8.md](INTEGRATION_0_8.md) § 2 lists
every change by surface, and [SCHEMAS.md](SCHEMAS.md) holds the columns.

## Where to go next

- **[SCHEMAS.md](SCHEMAS.md)** — every model, every column, the vocabularies and the hash family.
- **[MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md)** — where a module comes from and what a second version
  moves.
- **[FAQ.md](FAQ.md)** — settled questions, keyed by the question you would actually ask.
- **[Upgrading to 0.8](INTEGRATION_0_8.md)** — the 0.7 → 0.8 surface delta, the upgrade order, and
  the old-reader breaks.
- **[Upgrading to 0.7](INTEGRATION_0_7.md)** — the surface delta, including the one break for an old
  reader.
