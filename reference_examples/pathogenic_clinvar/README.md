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
module_spec.yaml   variants.csv   studies.csv   resolution.csv
```

`resolution.csv` is the **enricher-produced** table (committed so this compiles with no ClinVar cache
and no network):

```bash
just-dna-compiler compile reference_examples/pathogenic_clinvar /tmp/hbb_out   # offline, deterministic
```

To rebuild the whole thing from scratch (needs the local ClinVar snapshot at
`data/interim/clinvar`, produced by `just-dna-enricher clinvar build --vcf <clinvar.vcf.gz>`):

```bash
just-dna-enricher enrich reference_examples/pathogenic_clinvar \
    --offline --ensembl-cache /nonexistent --clinvar-cache data/interim/clinvar   # ClinVar-only
just-dna-compiler compile reference_examples/pathogenic_clinvar /tmp/hbb_out
```

## Authoring model (the point of the dogfood)

Variants are authored **by identity, not by baked coordinate** — the 0.5 way:

- **rsid variants** (301 here): carry only `rsid` + `genotype`/`state`/`conclusion`/`gene`. The
  enricher fills `chrom/start/ref/alts` into `resolution.csv` from the ClinVar snapshot
  (`source=clinvar`). Coordinates are *never* baked into `variants.csv`.
- **coordinate-only variants** (27 here): the ~10% of ClinVar pathogenic variants that carry **no
  rsID** cannot be authored by rsid, so they are authored `chrom/start/ref/alts` directly (a
  first-class `VariantRow` shape). The enricher passes them through (`source=authored`) unless a
  co-located ClinVar record lends an rsID (see finding 4).

## Findings

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

### 4. Coordinate-only entries compile cleanly — and some get an rsID back-filled
The compiler accepts the mixed rsid / coordinate-only spec with no trouble. During enrich, a
coordinate-only variant whose `(chrom,start,ref)` collides with a **co-located rsID-bearing** ClinVar
record gets that rsID back-filled (6-gene run: **474** back-filled, **931** stayed `authored`; HBB: 11
back-filled, 16 authored). **This back-fill is lossy/ambiguous — see finding 7.**

### 5. One-to-many rsIDs expand to distinct coordinate-keyed rows
530 rsIDs (6-gene run; 11 in HBB) map to more than one locus and expand to one weight row per locus,
each re-keyed to its coordinate (`variant_key = chrom:start:ref`, `locus_index` 0..N−1). Example
(BRCA1): `rs1131691004 → 17:7676039:A` (SNV) **and** `17:7676039:ACGGAAAC` (insertion).

### 6. Reverse round-trip reaches a fixpoint for the artifact identity
`compile → reverse → compile` is **idempotent for `artifact.digest` and `content_signature`** (byte-
identical on the second pass). Reverse normalizes to a canonical, full-column, **coordinate-baked,
expanded** spec — it is *not* a byte-inverse of the minimal hand-authoring (that asymmetry is intended:
authored row order is preserved, column order and cell formatting are normalized). One wrinkle:
`resolution_signature` is **not** a perfect fixpoint (see finding 7).

### 7. Why ClinVar collocates coord-only and rsID variants — and why back-fill is lossy
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

Concrete consequence in this module (HBB, `11:5226762`): the un-rs'd insertion `C>CAAAG` gets
back-filled with **`rs33922842`** — which is really the SNV rsID at that position, i.e. a **mild
mis-attribution**. And because a single rsID (`rs33922842`) legitimately maps to alleles with opposite
conclusions, resolving *by rsID* is coordinate-faithful but **not** conclusion-faithful.

**Takeaways for the format.** (a) Clinical identity is rightly keyed on `variant_key = chrom:start:ref`
+ genotype/effect, **not** rsID. (b) The enricher aggregates `alts` per `(rsid, chrom, start, ref)` for
the same reason. (c) The pos→rsID back-fill of coordinate-only entries is convenient but ambiguous
when several rsIDs collocate; the reverse round-trip's `resolution_signature` non-fixpoint (finding 6)
is a direct symptom — the chosen rsID label can drift across passes while `artifact.digest` (keyed on
coordinate) stays stable. A future refinement could skip pos→rsID back-fill when the position is
multi-rsID, or record the ambiguity, rather than attach one label. Recorded here as a candidate
follow-up; `resolution.csv` is provisional in 0.5, so nothing in the released contract is at stake.
