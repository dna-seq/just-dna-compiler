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

   Since 0.9 a re-derive can be scoped. `--rederive-subject KEY` (repeatable) re-asks only the named
   `variant_key`s and carries every other row of `resolution.csv` byte for byte, and `--verify-written-only`
   runs the row checks over the fresh rows only, each record in `verification.json` opening
   `Verification scoped to fresh resolution rows.`:

   ```bash
   just-dna-enricher enrich ./my_module --rederive-subject rs1800562 --verify-written-only
   ```

   ```text
   enriched: my_module/resolution.csv
   rows: 12  fully_resolved: True  sources: ['cache']
     compared recorded subjects: rs1800562
   ```

   Run on a copy of `reference_examples/hfe_hemochromatosis`, whose answer had not moved: the table came
   back byte-identical. A subject whose answer moved is listed as a drift, as `--rederive` lists one.
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

Online runs share a per-host answer store. Set `JUST_DNA_ANSWER_STORE` to a file or existing directory
to choose its disk. An unchanged source release lets a second module reuse the subjects the first one
asked about. The `stored` and `live` counts in the report show which route answered. To bypass the store
for one run, use `just-dna-enricher --no-answer-store enrich --rederive ./my_module`. To disable it for
the shell, use `export JUST_DNA_ANSWER_STORE=`. [Store settings and keys](ENRICHER.md#the-live-answer-store).

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

To check REF and left-align and mint indels offline, set `reference_uri` to the absolute URI of
your uncompressed GRCh38 FASTA, in the form `fasta+file:///abs/path.fa`, with `path.fa.fai` beside
it. Run `just-dna-enricher enrich ./my_module --offline --sequence-uri "$reference_uri"`. Each contig
must match its GRCh38 refget digest. The output reports how many rows the local FASTA checked
and names contigs it could not read. The GRCh37 wrong-build diagnosis still requires the network.
To see which chromosomes can supply bases before running enrichment, use
[`SequenceProxy.contig_identity` with your local reference](ENRICHER.md#local-grch38-reference).

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
  dataset moved on: clinvar (resolution): drafted from clinvar_2026-06-27, now clinvar_2026-11-15
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
  clinvar_gkm   absent   — ClinVar-GKM indels, the placement witness (RM292's checks, RM267); provision with `cache pull` or `clinvar-gkm build`
```

`cache status` reads only, so it cannot see whether a lane's repository has anything published; a lane
that can be pulled or built names both routes.

For the HLA check, run `just-dna-enricher cache pull --only ipd_imgt_hla` on each host.
It fetches the curators' tagged release directly. Subsequent offline runs can check HLA names against
that release. The curators ask operators to avoid mirrors.

Each Hub-backed lane's HuggingFace repository is written in one place, `locations.SNAPSHOT_REPO_IDS`, so
pin a snapshot by reading it there rather than spelling the repo:

```python
from just_dna_enricher.locations import SNAPSHOT_REPO_IDS

SNAPSHOT_REPO_IDS["ensembl"]      # 'just-dna-seq/ensembl_variations_split'
```

`clinvar_gkm` is in that map and has a published snapshot (17 MB), so `cache pull --only clinvar_gkm`
fetches it and ends with what is on disk; `clinvar-gkm build` still builds it locally instead:

```text
  clinvar_gkm: <base>/clinvar_gkm
on disk: clinvar_gkm
```

A lane whose repository holds nothing yet says *not published yet* and leaves nothing on disk, and
`cache prepare` reports the same and does not build a pullable lane.

One lane is built only when you name it: the Ensembl rsID index (`ensembl_rsid_index`), about 42 minutes and
6 GB from the Ensembl core, which makes an rsID lookup a pruned read instead of a scan. `cache prepare` and a
bare `cache rebuild` pass it over, and `cache status` names the command that builds it where it is read:

```text
  ensembl_rsid_index absent   — rsID → (chrom, start) over the Ensembl core, …; built only when named, … ; build it where it is read with `just-dna-enricher cache rebuild --only ensembl_rsid_index --out <base>`
```

Name it to build it, beside the core it indexes. The index pins that core (its release and a digest of its
files), so an index whose core moved under it is **`stale`** (since 0.9): `cache status` says so with the
reason, `cache prepare` leaves it alone and reports it unavailable, and an rsID lookup refuses it with a
warning and scans the core. Run on a scratch base whose fixture-sized core was replaced after its index
was built (paths shortened to `<base>`):

```bash
just-dna-enricher cache status
just-dna-enricher cache prepare --only ensembl_rsid_index
just-dna-enricher cache rebuild --only ensembl_rsid_index --out <base>
```

```text
  ensembl_rsid_index stale    <base>/ensembl_rsid_index  ensembl-variation-2026_07_13-vep116.0  0.0 MB — it pins release ensembl-variation-2026_07_13-vep116.0 over other files than the Ensembl core at <base>/ensembl_variations holds; built only when named, …
  ensembl_rsid_index unavailable stale: it pins release ensembl-variation-2026_07_13-vep116.0 over other files than the Ensembl core at <base>/ensembl_variations holds; …
0 of 1 cache(s) ready (0 pulled, 0 built, 0 already there). Run `cache status` to confirm.
  ensembl_rsid_index built    12 rsID loci of ensembl-variation-2026_07_13-vep116.0, 0 MB in 5 s
rebuilt 1, failed 0, not run 0 of 1 lane(s) into <base>
```

After the rebuild `cache status` says `present` again. On the real core the build is the 42 minutes above.
A host that configures its paths itself passes the index's directory as `rsid_index=` to `lookup_variant`,
`enrich` or `resolver.lookup_loci`, and `caches.lane_status(locations={...})` reports on the paths it
names rather than on the environment.

### The Ensembl lane's optional column groups

The split Ensembl snapshot keeps every annotation value (consequence, clinical flags, frequencies, CADD and
more) in `groups/<name>/` beside the core, joined to it on `(chrom, row_idx)`, which holds within one
release only. Since 0.9 the lane pulls them, attested by the same manifest and re-pulled with the core
whenever its release moves: `just-dna-enricher cache pull --only ensembl --groups consequence,clinical --use
non-commercial` names two (the 0.9 docs pass did not run that pull, which writes gigabytes into the cache; the two
refusals below were run).

Read a group's directory from `locations.ensembl_group_dir(cache, group)`, which refuses a group of
another release than the core's, never by spelling the path. Each group is licensed by its own licensor:
`cadd` downloads under a `non-commercial` use, is refused under a commercial one and is skipped under an unstated
one. The names come from the manifest, and two mistakes are refused before anything runs:

```text
$ just-dna-enricher cache pull --groups cadd
│ Invalid value for --groups: --groups selects groups of the ensembl lane, so  │
│ it is refused beside any other lane; with no --only every lane is selected.  │
│ Pass --only ensembl.                                                         │
$ just-dna-enricher cache pull --only ensembl --groups core
│ Invalid value for --groups: `core` is not a group name: the core (data/) is  │
│ always pulled, and a group selection names only the optional groups beside   │
│ it.                                                                          │
```

A lane has three stages, and where one is absent the status says **why** as a field rather than
leaving you to guess. A derived lane also names its parents: an absent parent is *could not run*,
never *an empty result*, and a parent that moved and a parent that is gone are different instructions.

Snapshot builders (`clinvar`, `cpic`, `clinpgx`, `civic`, `mane`, `strchive`, `mitomap`, `gnomad`,
`pubmind`, `pharmvar`, `acmg`, `alphagenome`, and since 0.8 `clinvar-gkm` and `opentargets`) are the
operator surface — you build them once and the deployment reads them, rather than every request
reaching the source. Which of them may be *published* is a licence question answered per source, and
the command's help says which.

## Read a lane this machine does not hold

Since 0.9 a host with no local snapshot of a lane can read it remotely: from the registry's proxy, then
from the lane's Hugging Face repository. Nothing does this unless you hold a `RemoteSnapshots`, so every
existing call reads and fetches what it did before, and `--offline` never reads remotely. Install duckdb's
`httpfs` once on the box (`python -c "import duckdb; duckdb.connect().install_extension('httpfs')"`),
because it is loaded with auto-install off.

```python
from just_dna_enricher.clients import LookupClients
from just_dna_enricher.lookup import lookup_variant
from just_dna_enricher.remote import RemoteSnapshots

with RemoteSnapshots(proxy_url="https://module-polygon.just-dna.life") as holder:
    answer = holder.lookup("clinvar", "clinvar", {"rsid": ["rs429358"]})
    print(len(answer.rows), answer.route)
    hint = lookup_variant(rsid="rs429358", clients=LookupClients(snapshots=holder))
print(hint.routes["clinvar"])
print([(l["chrom"], l["start"], l["ref"], l["alts"]) for l in hint.loci])
```

Run against the registry's test server on a box with no ClinVar or Ensembl cache:

```text
1 RemoteRoute(route='proxy', release=None, served_from='local', revision=None)
RemoteRoute(route='proxy', release=None, served_from='local', revision=None)
[('19', 44908684, 'T', 'C')]
```

Every answer says where it came from. The proxy is `proxy_url=`, else `$JUST_DNA_SNAPSHOT_PROXY_URL`, and
unset by default; a proxy answer's `release` is what its reply states, here nothing. With no proxy, or
when it paces you, Hugging Face answers at a pinned commit with the release it read, and in seconds
rather than tenths:

```text
1 RemoteRoute(route='hf', release='clinvar_2026-11-15', served_from=None, revision='50db2b896a42744f6d5a19c604eaf807a2dd2d31')
```

Ensembl is asked remotely by position only, so an rsID alone is placed by ClinVar, asked next. A route
that could not be asked is a finding, never an empty answer (`SnapshotRouteUnavailable`); a wrong
request, or a lookup on a holder already closed, raises. Close a holder you share only after its last
lookup. [INTEGRATION_0_9.md § 1.2](INTEGRATION_0_9.md#12-remote-reads-just_dna_enricherremote-rm430-no-break-off-unless-a-caller-holds-one)
has the rest.

## 4. Open Targets: genes, colocalisations and consequences

New in 0.8, the Open Targets lane fills three derived tables from one pinned release:
`locus_to_gene.csv` (the locus-to-gene score of every GWAS credible set a module variant belongs to),
`colocalisations.csv` and `consequences.csv` (per transcript), plus a fine-mapping posterior on
`gwas_effects.csv`. Provision the snapshot once, with `cache pull --only opentargets` (about 5.5 GB) or by
building it from the Platform release with `opentargets build` (about 22 GB of download), then:

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
[INTEGRATION_0_8.md](history/INTEGRATION_0_8.md) § 1.27 and § 1.40 have the whole family.

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
