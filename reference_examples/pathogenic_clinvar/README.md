# ClinVar pathogenic (HBB) — a 0.5 dogfood of the enricher ClinVar machinery

This is a **worked reference example**, not a curated clinical product. It re-creates the spirit of
the Generation-I `pathogenic` module (genome-wide ClinVar pathogenicity flag) using the **0.5
machinery** — the `just-dna-enricher` ClinVar snapshot + resolution table — *instead of* the v1
`gene_panel` adapter that baked ClinVar coordinates directly into the module.

Scope here is **HBB only** (sickle-cell / β-thalassemia) so the files stay small and human-reviewable.
The findings below come from the full dogfood run (genome-wide, and a 6-gene resolution run:
BRCA1/2, CFTR, LDLR, TP53, HBB); the committed HBB slice reproduces every mechanism.

## Provenance

- Source: NCBI **ClinVar GRCh38 VCF, `##fileDate=2026-06-27`**, built into a parquet snapshot with
  `just-dna-enricher clinvar build`. Pathogenic = `clin_sig ∈ {pathogenic, likely_pathogenic}`.
- Built with `just-dna-enricher` / `just-dna-compiler` 0.5. Evidence citation is the ClinVar resource
  paper (Landrum et al., PMID 29165669) — a placeholder for the dogfood, not per-variant curation.

## Files & how to compile

```
module_spec.yaml   variants.csv   studies.csv   resolution.csv   literature.csv
```

`resolution.csv` and `literature.csv` are **enricher-produced** and committed, so this compiles with no
ClinVar cache and no network — and it compiles under **`--strict`**, which is the point: strict refuses
anything it could not reproduce from the injected table, so passing it is a claim about the whole
module, not just the syntax.

```bash
just-dna-compiler compile reference_examples/pathogenic_clinvar /tmp/hbb_out --strict
```

To rebuild from scratch (needs the local ClinVar snapshot at `data/interim/clinvar`, produced by
`just-dna-enricher clinvar build --vcf <clinvar.vcf.gz>`):

```bash
rm reference_examples/pathogenic_clinvar/resolution.csv   # existing rows are authoritative — delete first
just-dna-enricher enrich reference_examples/pathogenic_clinvar \
    --offline --ensembl-cache /nonexistent --clinvar-cache data/interim/clinvar   # ClinVar-only
just-dna-enricher literature reference_examples/pathogenic_clinvar                # online (PubMed/Crossref)
just-dna-compiler compile reference_examples/pathogenic_clinvar /tmp/hbb_out --strict
```

**Not carried, deliberately:** `frequencies.csv` (gnomAD is online-only and 337 alleles is a lot of
committed rows for a file meant to stay human-reviewable) and `gene_metrics.csv` (no local v4.1
constraint snapshot here, so the live route would pin the older `gnomad_v2.1.1_constraint` label into a
reference example — correct, but it reads like an error). Both are one command away if wanted.

## Authoring model (the point of the dogfood)

Variants are authored **by identity, not by baked coordinate** — the 0.5 way:

- **rsid variants** (301 here): carry only `rsid` + `genotype`/`state`/`conclusion`/`clin_sig`/`gene`. The
  enricher fills `chrom/start/ref/alts` into `resolution.csv` from the ClinVar snapshot
  (`source=clinvar`). Coordinates are *never* baked into `variants.csv`.
- **coordinate-only variants** (27 here): the ~10% of ClinVar pathogenic variants that carry **no
  rsID** cannot be authored by rsid, so they are authored `chrom/start/ref/alts` directly (a
  first-class `VariantRow` shape). The enricher passes them through (`source=authored`) unless a
  co-located ClinVar record lends an rsID (see finding 4).

Every row also carries **`clin_sig`** — the typed ClinVar call, in the closed `VALID_CLIN_SIG`
vocabulary — alongside the free-text `conclusion`. That is not decoration: it is what the enricher's
ClinVar cross-check reads, so the module is checkable against the source it was built from. It agrees on
all 328 rows, which is the expected result and therefore a real regression guard: a future change to
allele matching or `clin_sig` normalization that starts producing conflicts here is producing them
wrongly.

## Findings

### 0. One rsID can name several *different* variants, and the genotype says which
Three rsIDs here resolve to ClinVar records the module's own genotype rules out — `rs281864532` is
`G>GT`, `GT>G` **and** `GTT>G` at one position; `rs613985` names records at two positions 254 bp apart.
An rsID is a position/multi-allelic tag, so this is dbSNP behaving normally, not a data error. The
enricher therefore resolves **allele-aware in the forward direction too** (it already did for the
reverse position→rsid back-fill): a record the authored genotype cannot host is reported and left out
of `resolution.csv`, because recording it would only hand the compiler a locus it must drop — and a
dropped locus makes the compile unreproducible from the injected table, which `--strict` refuses.

Before that fix this example expanded to 340 resolution rows and reverse wrote three of them back out
as *authored* rows asserting alleles their locus does not have. It now resolves to 337, and
`compile → reverse → compile` is a fixed point on all three signatures.

### 1. The new machinery is a strict **superset** of the v1 re-port
Genome-wide, the snapshot's pathogenic set (**339,038** ALT-rows) vs the v1 `gene_panel` adapter run
on the *same* VCF (**338,825**): **0 rows only in v1**, **213 only in the new build**, fully explained:
- **180** carry a comma-qualified `CLNSIG` such as `Pathogenic,_low_penetrance`. v1's `_is_pathogenic`
  splits `CLNSIG` on `|` and `/` only, so `pathogenic,_low_penetrance` is one unrecognised token and
  the variant is dropped. The 0.5 builder splits on `,` too → keeps them (arguably more correct — they
  *are* pathogenic).
- **33** have no `GENEINFO` gene. v1 requires a gene; a resolution reference is gene-agnostic.

*(Both read the current local VCF, so these are **method** differences, not 4-year drift. A true
temporal diff would compare against the published Gen-I artifact on HuggingFace — not done here.)*

### 2. Coordinates round-trip exactly (no off-by-one)
For the 11,099 rsid variants (6-gene run), enricher-resolved coordinates vs the v1 baked coordinates:
**11,095 exact matches + 4 one-to-many supersets, 0 genuine disagreements.** The enricher reproduces
the baked coordinates — confirming the 1-based VCF-POS convention end to end.

### 3. no-rsID variants: ~10% loss if you author by rsid alone
1,405 / 14,305 (**9.8%**) pathogenic variants in the 6-gene set carry no rsID. An rsid-only authoring
silently drops them — which is exactly why coordinate-only entries are first-class and why they are
**added** to this module. (Native gene→variant *materialization* — capturing them from a gene list —
is the still-parked RM4; the enricher *resolves*, it does not materialize.)

### 4. Coordinate-only entries compile cleanly — and back-fill is allele-aware (no guessing)
The compiler accepts the mixed rsid / coordinate-only spec with no trouble. The reverse (position→rsid)
back-fill is **allele-aware**: it matches the authored `(chrom,start,ref,alt)` and only attaches an
rsID that is *exact for that allele*. So a coordinate-only entry with no rsID for its exact allele
stays `rsid=null`/`source=authored` — it never borrows a co-located different-allele rsID (HBB: **27**
stay authored, **313** resolved from ClinVar; **0** ambiguous). If an *exact allele* genuinely carries
several rsIDs (a dbSNP merge), the row is marked `status="ambiguous"` with a deterministic `rsid` pick
and the full candidate list in `rsid_alternates` — the ambiguity is recorded, never silently guessed.
*(This corrects an earlier allele-blind back-fill that let the un-rs'd insertion `11:5226762 C>CAAAG`
inherit the SNV rsID `rs33922842` at that position — see finding 7.)*

### 5. One-to-many rsIDs expand to distinct allele-keyed rows
530 rsIDs (6-gene run; 11 in HBB) map to more than one locus and expand to one weight row per locus,
each re-keyed to its allele (`variant_key = chrom:start:ref:alts`, `locus_index` 0..N−1). Example
(BRCA1): `rs1131691004 → 17:7676039:A:ACGGAAAC` (insertion) **and** `17:7676039:ACGGAAAC:A` (deletion).

### 6. Reverse round-trip is a full fixpoint (once `variant_key` carries `alt`)
`compile → reverse → compile` is now **idempotent for `artifact.digest`, `content_signature`, *and*
`resolution_signature`** (byte-identical on the second pass). Reverse still normalizes to a canonical,
full-column, coordinate-baked, expanded spec (that asymmetry is intended: authored row order is
preserved, column order and cell formatting are normalized).

Getting `resolution_signature` to a fixpoint took a second fix beyond the allele-aware back-fill
(finding 4). The dogfood first showed it *not* converging, and the cause was that
`variant_key = chrom:start:ref` **excluded `alt`**: two different alleles at one locus collapsed onto
one key — in HBB the coordinate-only insertion `11:5226762 C>CAAAG` (rsID null) and the expanded
`rs33979901` locus `11:5226762 C>CA` both keyed to `11:5226762:C`, so the decompiler could not tell
which rsID belonged to which and its choice drifted across passes. The fix: **`variant_key` now carries
the alt** — `chrom:start:ref:alts` (normalized) — so the insertion is `11:5226762:C:CAAAG`, distinct
from `11:5226762:C:CA`. (rsid keys, position-only keys, and the position-level study/consistency joins
are unchanged — studies match a variant at `chrom:start:ref` regardless of allele.) This is exactly the
kind of pre-freeze identity fix the dogfood exists to surface — taken while `resolution.csv` was still
provisional, before 0.5.0 published on 2026-08-07 and froze it.

### 7. Why ClinVar collocates coord-only and rsID variants (the dbSNP data model)
**This is structural in the ClinVar/dbSNP data model, not an oversight.** Variant identity is
`(position, ref, alt)`; the rsID is a coarser **position/multi-allelic-level** tag. At one position
there are usually several distinct ALT alleles, each its own ClinVar Variation ID, and:

- **One rsID spans several alleles with different conclusions.** dbSNP `rs33922842` (HBB, 11:5227… )
  tags `C>A` (**Pathogenic**, E44*), `C>G` (**Benign**, E44Q) and `C>T` (**Uncertain**, E44K) — one
  rsID, three alleles, three classifications (ClinVar IDs 15406/15203/3572116). Likewise BRCA1
  `rs80357415` spans `C>G/C>A/C>T`. **So collocated entries do *not* share a conclusion — the
  conclusion is per-allele, never per-rsID.**
- **Some variants have no rsID at all** — newer or complex insertions dbSNP hasn't minted/linked
  (e.g. `11:5226762 C>CAAAG`, Variation 3572115). Not an oversight; dbSNP linkage is per-variant and
  incomplete.
- **Different rsIDs collocate as different variant *types*** at overlapping coordinates (a SNV rs and a
  nearby indel rs, e.g. `rs33922842` SNVs vs `rs33979901` a small indel).

**Takeaways for the format.** (a) Clinical identity is rightly keyed on coordinate + genotype/effect,
**not** rsID — a single rsID legitimately maps to alleles with opposite conclusions, so resolving *by
rsID* is coordinate-faithful but never conclusion-faithful. (b) The enricher aggregates `alts` per
`(rsid, chrom, start, ref)` for the same reason. (c) Reverse (position→rsid) back-fill is now
allele-aware and records genuine ambiguity (finding 4) instead of guessing. (d) `variant_key` now
carries `alt` (finding 6), so distinct alleles at one locus are distinct identities and the reverse
round-trip is a full fixpoint.
