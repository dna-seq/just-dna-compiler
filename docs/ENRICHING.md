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
   **So an enricher upgrade that corrects a resolution does not reach a table you already have.** After
   one (RM251 and RM268 are two), run `just-dna-enricher enrich --rederive ./my_module`: it re-asks every
   subject, replaces what was answered, keeps rows it could not re-ask, and reports what changed.
   Deleting `resolution.csv` and re-running also works, but loses that report. See
   [After the 0.8 snapshot switch](#after-the-08-snapshot-switch) below.
2. **Local Ensembl cache** — DuckDB lookups, offline. Since 0.8 this is the split snapshot
   (dbSNP 157 / VEP 116, `just-dna-seq/ensembl_variations_split`).
3. **HuggingFace snapshot** — fetched if no cache is present. A static slice of popular rsIDs, not a
   canonical reference, so a miss falls through rather than answering.
4. **ClinVar snapshot** — for what Ensembl missed. It sits *after* Ensembl deliberately: `alts` is a
   resolution fact that flows into the artifact digest, and Ensembl carries every dbSNP allele where
   ClinVar carries only its submitted ones. A variant both know keeps the Ensembl answer, so no
   already-compiled module's digest moves.
5. **Live Ensembl** — REST, paced under Ensembl's published budget.
6. **gnomAD** — last.

Every row now names the release that answered it in `source_release`
(`ensembl-variation-2026_07_13-vep116.0` for the split snapshot, `clinvar_<date>` for ClinVar,
`ensembl_116` for live REST). An empty cell means not recorded, never current.

Every rsID the enricher places is also put to a second authority, the ClinVar snapshot and
ClinVar-GKM (and online, for an indel neither holds, Ensembl REST). A placement two authorities give
as two different events is withheld: that locus gets no row, and `--strict` refuses an rsID it leaves
unresolved. `resolution.csv`'s `placement_witness` and `placement_verdict` record who was asked and
what they said. ClinVar-GKM is read from `--clinvar-gkm-cache` or `$JUST_DNA_CLINVAR_GKM_CACHE` and never
downloaded by `enrich`.

### After the 0.8 snapshot switch

0.8 moved the Ensembl lane to a new snapshot, and a table you already have keeps the old answers until
you re-derive it. Move the cache once per machine, then re-derive each module online:

```bash
just-dna-enricher cache pull --only ensembl     # once per machine; budget 14.5 GB
just-dna-enricher enrich --rederive ./my_module
```

`cache pull` trusts a cache whose pull record already names the new repo, so on a machine that has
moved it finishes at once:

```text
  ensembl: <base>/ensembl_variations
```

(`<base>` stands for the cache base directory the run printed.)

Run against `reference_examples/hfe_hemochromatosis` as it stood at v0.7.3, the re-derive reports
each subject whose answer changed (one shown):

```text
  re-derived: rs1800562: rs1800562|rs1800562|6|26092913|G|A|GRCh38|0 → rs1800562|rs1800562|6|26092913|G|A,T|GRCh38|0 (moved: the source names a different event)
```

Read that diff before you compile: resolutions move as data, so `artifact.digest` moves where a fill
changed, while `content_signature` does not. Here dbSNP 157 lists a second ALT at the site. A module
enriched before the switch and again after it **without** `--rederive` holds two placement sets for one
rsID, and `compile --strict` refuses it (`rsid_placements_disagree`, see
[Compile a module](COMPILING.md#the-refusals-new-in-08)).

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

Each is a flag, each defaults on, and each **reports**. On `reference_examples/longevity_studies` an
ordinary `enrich` draws only a currency line: its licence row names a ClinVar release older than the
one ClinVar publishes today.

```text
  dataset moved on: clinvar (resolution): drafted from clinvar_2026-06-27, now clinvar_2026-11-01
```

| Flag | Asks |
|---|---|
| `--verify-ref` | does each authored `ref` match the reference sequence? |
| `--verify-clinsig` | does each authored `clin_sig` match ClinVar's own? (warns, never fails) |
| `--verify-rsids` | is each rsID current in dbSNP, or merged, or withdrawn? |
| `--vrs` | mint GA4GH VRS allele ids onto resolved rows |

A disagreement is a finding, not a correction. The enricher will tell you that an authored `ref`
disagrees with the reference sequence; it will not write the reference's value into your file.

The findings are recorded in `verification.json`, and a later `compile --strict` reads that record.
**A record written by an older enricher is not re-examined**, so it carries none of the diagnoses
added since. After upgrading the enricher, re-run `enrich` on a module you mean to compile strictly, so
the record, and the gate reading it, reflect the current checks (S78).

## 2. Draft — rows from a source

```bash
just-dna-enricher draft ./my_module --gene CYP2C9 --use non-commercial
just-dna-enricher draft-clinpgx ./my_module --snapshot ./clinpgx --drug warfarin --use non-commercial
just-dna-enricher draft-panel ./my_module --gene BRCA1
just-dna-enricher draft-repeats ./my_module --gene FMR1
```

CPIC and ClinPGx forbid sale, so without `--use` those two draft nothing and say why:

```text
  skipped: cpic forbids sale and no use was declared, so it was skipped. Re-run with --use non-commercial to record a declaration (https://www.clinpgx.org/page/dataUsagePolicy).
```

With it, the CPIC draft for CYP2C9, into a freshly scaffolded `draft_mod`, reports per table:

```text
CYP2C9:
  haplotypes.csv: 187 added, 0 already present, 0 differing (left unchanged)
  allele_function.csv: 94 added, 0 already present, 0 differing (left unchanged)
  diplotypes.csv: 2850 added, 0 already present, 0 differing (left unchanged)
  …
added 3131 row(s) across 1 gene(s) in draft_mod
```

`draft-repeats` reads the STRchive snapshot `cache status` lists (or `--catalogue <dir>`), and leaves
every band for you to write:

```text
  1 of 1 locus/loci state a fractional ref_copies (the reference allele is not a whole number of motif copies). No authored column carries it, so it was read and not written — it is not rounded anywhere.
added 1 row(s) from 1 strchive locus/loci (strchive_v2.26.0)
  every drafted row needs its bands and its conclusion written; the placeholder is what stops the module compiling until they are
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
just-dna-enricher cache pull        # download what is published; --only <lane> for one
just-dna-enricher cache prepare     # pre-provision: pull what is published, build what is not
just-dna-enricher cache rebuild
just-dna-enricher cache prune       # asks before deleting
```

`cache status` prints one line per lane (three shown):

```text
  ensembl       present  <base>/ensembl_variations  ensembl-variation-2026_07_13-vep116.0  14539.7 MB
  opentargets   present  <base>/opentargets  opentargets_26.09  5455.6 MB
  clinvar_gkm   absent   — ClinVar-GKM indels, the placement witness (RM292's checks, RM267); provision with `cache pull`
```

Each pulled lane's HuggingFace repository is written in one place, `locations.SNAPSHOT_REPO_IDS`, so
pin a snapshot by reading it there rather than spelling the repo:

```python
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS

SNAPSHOT_REPO_IDS["ensembl"]      # 'just-dna-seq/ensembl_variations_split'
```

`clinvar_gkm` is in that map, but nothing is published there yet, so `cache pull --only clinvar_gkm`
says so and `clinvar-gkm build` (or `cache prepare`) builds it locally:

```text
  clinvar_gkm: not published yet — nothing is published at datasets/just-dna-seq/clinvar_gkm/data — the repo or its data/ does not exist. Build the snapshot locally (`cache rebuild --only …`), or publish one.
```

A lane has three stages, and where one is absent the status says **why** as a field rather than
leaving you to guess. A derived lane also names its parents: an absent parent is *could not run*,
never *an empty result*, and a parent that moved and a parent that is gone are different instructions.

Snapshot builders (`clinvar`, `cpic`, `clinpgx`, `civic`, `mane`, `strchive`, `mitomap`, `gnomad`,
`pubmind`, `pharmvar`, `acmg`, `alphagenome`, and since 0.8 `clinvar-gkm` and `opentargets`) are the
operator surface — you build them once and the deployment reads them, rather than every request
reaching the source. Which of them may be *published* is a licence question answered per source, and
the command's help says which.

## 4. Open Targets: genes, colocalisations and consequences

New in 0.8, the Open Targets lane fills three derived tables from one pinned release:
`locus_to_gene.csv` (the locus-to-gene score of every GWAS credible set a module variant belongs to),
`colocalisations.csv` and `consequences.csv` (per transcript), plus a fine-mapping posterior on
`gwas_effects.csv`. Build the snapshot once with `opentargets build`, then:

```bash
just-dna-enricher opentargets enrich ./ot_mod
```

On a copy of `reference_examples/longevity_studies` in `./ot_mod` (six resolved subjects):

```text
ot_mod/locus_to_gene.csv: 17591 row(s)
ot_mod/colocalisations.csv: 431755 row(s)
ot_mod/consequences.csv: 242 row(s)
dataset: opentargets_26.09  asked: 6  not in release: 1  not read (snapshot not whole): 0  off build: 0  allele-ambiguous: 0
```

Each compiles to its own parquet. Mind the size: the colocalisations of six variants came to 117 MB of
CSV and a 6 MB parquet. `just-dna-enricher ld-pairs` is the other new derived pass, filling
`ld_pairs.csv` from each study's `proxy_rsid` (online only).

## 5. One command for the whole loop

```bash
just-dna-enricher enrich-and-compile ./my_module ./out
```

Resolve, then compile, in one call.

## 6. Publish

`upload` sends a compiled module to a HuggingFace dataset. `--dry-run` runs every check the real
publish runs, reading the hub without writing:

```bash
just-dna-enricher upload ./pub_ok --name docs-pass-apoe --dry-run
```

```text
Would upload to just-dna-seq/annotators at data/docs-pass-apoe/:
  • haplotypes.parquet
  • diplotypes.parquet
  • sources.parquet
  • manifest.json
  • README.md
no versioned copy: manifest.json states no identity.version
```

A publish refuses rather than send what its manifest cannot vouch for. `./pub_bad` is the same
compiled module with `diplotypes.parquet` deleted:

```text
UPLOAD FAILED: docs-pass-apoe: manifest.json attests ['diplotypes.parquet'] but the upload would not carry it — `artifact.digest` is computed over the attested files, so what arrived could not be verified against the manifest that describes it. Re-compile pub_bad if the file is missing.
```

Since 0.8 every such refusal is an `upload.PublishRefused`, so a caller in Python catches that one
type: a plan the module cannot satisfy (`ModuleNotPublishable`), a repo that moved since the plan read
it (`RemoteMovedError`), a file that changed since it was hashed (`PlanChangedError`), and a
versioned path already holding something else (`PublishCollisionError`).
[INTEGRATION_0_8.md](INTEGRATION_0_8.md) § 1.27 and § 1.40 have the whole family.

## Look something up without writing anything

```bash
just-dna-enricher hint variant --rsid rs429358
just-dna-enricher hint citation --pmid 12345678
just-dna-enricher hint gene APOE
```

A PMID that exists is not yet the paper you meant, and `hint citation` says so:

```text
  info: PMID 12345678 names: 'Denpasar Declaration on Population and Development.' (Ministerial Meeting on Population of the Non-Aligned Movement (1993: Bali), Integration (Tokyo, Japan), 1994) — existence is not identity, so confirm this is the paper you meant.
```

`hint` reports what is known about a variant or a citation and writes nothing — no authored cell, no
table row. `litvar coverage` answers which papers a variant-literature index holds for a module's
alleles, **and at which tier**, because allele-resolved, position-only and absent are three different
answers to "is there literature on this":

```bash
just-dna-enricher litvar coverage ./my_module --quiet
```

```text
loci: 5 (from 3 table(s): studies.csv, variants.csv, resolution.csv)
allele: 2
position: 2
absent: 1
unchecked: 0
```

## Where to go next

- **[ENRICHER.md](ENRICHER.md)** — the reference, including the open questions.
- **[Compile a module](COMPILING.md)** — what happens to the `resolution.csv` this produced.
- **[CACHE_SURFACE.md](CACHE_SURFACE.md)** — what a cache lane is, and the checklist for adding one.
- **[CLI reference](https://just-dna.life/just-dna-compiler/cli/)** — every command and
  flag, generated from the tool itself. It is written at build time from the live command tree,
  so it exists on the site and not in this repository.
