# Upstream ledger — the data sources behind the cache lanes

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. Asked for by the maintainer on 2026-11-07, relayed by the lead: "Is our
liaison watching al these releases? I would rather he to keep a table of built/published/available".

One row per lane in `caches.CACHE_LANES`. The three columns:

- **Available**: the source's own newest release, read off the source (its FTP listing, release index or
  `Last-Modified`), never off our cache.
- **Built**: the release label in this machine's cache, `/data/just-dna-cache/<lane>/release.json`, as
  `just-dna-enricher cache status` prints it.
- **Published**: the label in `release.json` at the root of the lane's HuggingFace repo
  (`locations.SNAPSHOT_REPO_IDS`), the copy every other machine pulls.

A cell is one of three things: a label, `none` (looked, and there is none), or `unchecked` with the reason (the
house algebra: an unknown is never written as a no).

## Marks

- **Last measured:** 2026-11-07, by hand (curl against each source, `cache status`, each HF repo's `release.json`);
  the published column re-read the same evening after the lead's four publishes.
- **Next:** weekly, with the dependency bump; earlier when a lane's builder or a source announces a release.

## The table (2026-11-07)

| Lane | Available (source) | Built (this machine) | Published (HF) | Behind? |
| --- | --- | --- | --- | --- |
| `ensembl` | Ensembl **116** (REST `/info/data`; FTP tops at `release-116`) | `ensembl-variation-2026_07_13-vep116.0` | `ensembl-variation-2026_07_13-vep116.0` (`ensembl_variations_split`, `manifest.json`; that repo has no `release.json`) | no |
| `clinvar` | weekly `clinvar_20261101.vcf.gz`; `clinvar.vcf.gz` modified 2026-11-02 | `clinvar_2026-06-27` | `clinvar_2026-11-01` (published 2026-11-07) | published: no. This machine's cache: 4 months behind |
| `constraint` | gnomAD **v4.1.2** (`release/4.1.2/constraint/` exists; so does 4.1.1) | `gnomad_v4.1_constraint` | `gnomad_v4.1_constraint` | **yes**: the builder pins `release/4.1/` (`constraint_build.py:60`) |
| `clinpgx` | unchecked: the archive's `Last-Modified` reads 2025-07-05, older than the label we built, so that header is not the release date | `clinpgx_2026-08-05` | `clinpgx_2026-08-05` | unchecked |
| `cpic` | unchecked: the label is a hash of the API's answer, so only a rebuild says whether it moved | `cpic_snapshot_b0ffd4c6f010` | `cpic_snapshot_b0ffd4c6f010` | unchecked |
| `drug_labels` | unchecked (ClinPGx, as above) | `clinpgx_drug_labels_2026-08-05` | `clinpgx_drug_labels_2026-08-05` | unchecked |
| `pharmvar` | unchecked: personal API key, and the label is a hash | `pharmvar_snapshot_56d4125c2ce4` | none (no repo: the lane is unpublishable) | unchecked |
| `pubmind` | `hg38_pubmind_db.txt.gz` modified 2026-08-24 | `pubmind_ca224ebf5ef3` (a hash) | none (no repo) | unchecked: a hash label cannot be compared with a date |
| `civic` | monthly **01-Nov-2026** (`/downloads/01-Nov-2026/` answers 200) | `civic_01-Sep-2026` | `civic_01-Nov-2026` (published 2026-11-07) | published: no. This machine's cache: two releases behind |
| `strchive` | **v2.28.0** (GitHub release, 2026-10-08) | `strchive_v2.26.0` | `strchive_v2.28.0` (published 2026-11-07) | published: no. This machine's cache: behind |
| `mitomap` | `mitomap.dump.sql.gz` modified 2026-11-06 | `mitomap_2026-08-21+2026-08-19` | `mitomap_2026-11-05+2026-11-03` (published 2026-11-07) | published: no. This machine's cache: behind |
| `mitomap_miss` | derived from `mitomap` and `clinvar` | no label (`release.json` carries counts only) | none (no repo) | follows its parents |
| `mane` | **v1.5** (`release_1.5/` is the newest directory) | `mane_grch38_v1.5` | none (no repo) | no |
| `acmg` | unchecked: the list is a journal supplement, with no index to poll | SF **v3.3** (DOI 10.1016/j.gim.2025.101454) | none (no repo) | unchecked |
| `opentargets` | **26.09** (newest directory on the EBI FTP; 26.06, 26.03 before) | `opentargets_26.09` | `opentargets_26.09` (published 2026-11-04, readable since 2026-11-07) | no |
| `alphagenome_avi` | unchecked: no release index found yet | absent here | `2026-08-27` | unchecked |
| `clinvar_gkm` | Parquet set **2026-10-24**; the weekly line is at 2026-10-31 (the release index) | absent here | `clinvar_gkm_2026-10-24` (published today) | no: the set, not the line, is what a rebuild takes |

## What the table says

1. **On the published copy, only `constraint` is behind its source now** (RM410). `clinvar`, `civic`, `strchive`
   and `mitomap` were behind when first measured and were published on 2026-11-07.
2. **This machine's shared cache is older than the published copy** for those four lanes: `cache pull` would bring it
   level.
3. **Three lanes have labels a date cannot be compared with** (`cpic`, `pharmvar`, `pubmind` are hashes). Their
   currency is known only by rebuilding and comparing hashes. Whether that is worth a weekly run is open.
4. **Lanes with a currency command already ask the source**: `clinvar_gkm` (`ClinVarGkmClient.current_release`)
   and ClinVar. The other lanes have none; the probe here is curl by hand.

## Adoption note: gnomAD constraint 4.1 → 4.1.2 (2026-11-07, for the lead)

Asked by the lead before the `constraint` pin moves: the file name, and what changed.

**The files** (bucket listing, `storage/v1/b/gcp-public-data--gnomad/o?prefix=release/<v>/constraint/`):

| Release | Data file | Size | Written | Beside it |
| --- | --- | --- | --- | --- |
| 4.1 (pinned) | `release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv`, plain TSV | 95.5 MB | 2024-04-18 | `README.txt`, the `.ht` |
| 4.1.1 | `release/4.1.1/constraint/gnomad.v4.1.1.constraint_metrics.tsv.bgz`, **bgzip** | 574.5 MB | 2026-03-25 | `gnomad.v4.1.1.gene_constraint_ht_README.md` (the field list), `gnomad.v4.1.1.loeuf_percentile_thresholds.tsv`, `model/`, the `.ht` |
| 4.1.2 | `release/4.1.2/constraint/gnomad.v4.1.2.constraint_metrics.tsv.bgz`, **bgzip** | 574.5 MB | 2026-09-23 | the `.ht` only (its field list is 4.1.1's README) |

So the `.tsv` name the builder would guess 404s because the newer releases ship only `.tsv.bgz`.

**What changed, from gnomAD's own notes** (the v4.1.1 post, `gnomad.broadinstitute.org/news/2026-03-gnomad-v4-1-1/`,
and the changelog entry for v4.1.2, 2026-09-28):

1. **4.1 → 4.1.1 recomputes the metrics**, on the v4.1 exomes:
   - low-coverage coding loci are now included, by allele number (AN%) as the coverage proxy and a coverage
     model for sites between 20% and 90% AN (sites under 20% excluded);
   - chrX and chrY get constraint metrics for the first time;
   - LOFTEE's `END_TRUNC` flag is revised, and the calculation behind LOEUF is updated, with new LOEUF threshold
     recommendations (the `loeuf_percentile_thresholds.tsv`).

   So **pLI, LOEUF, o/e and the z-scores move for genes that were already covered**, and genes gain rows. That is a
   content change of the snapshot, not a relabel.
2. **4.1.1 → 4.1.2 is constraint-only and fixes ranks**: 4.1.1 counted transcripts with missing values in the rank
   denominator, so `lof.oe_ci.upper_bin_decile` and the other bin fields filled deciles 0–7 only. "The constraint
   metric values themselves (including LOEUF) are unchanged; only the rank and bin fields differ." **Skip 4.1.1;
   take 4.1.2.**

**Against the builder** (`constraint_build.py`), measured on the first MiB of the 4.1.2 file:

- **Every column `_COLUMN_MAP` reads is present** (`gene_id`, `transcript`, `lof.pLI`, `lof.oe_ci.upper`, `lof.oe`,
  `lof.oe_ci.lower`, `lof.z_score`, `mis.oe`, `mis.z_score`, `syn.z_score`, `lof.obs`, `lof.exp`,
  `constraint_flags`), and so are `canonical` and `mane_select`, which the row pick uses. The file has **113
  columns** where 4.1 has 55; the new ones include array-valued cells (`[0,0,1,4,…]`, per-ancestry downsamplings).
- **Missing values are `NA`**, and the RefSeq row still carries `gene_id = 1` (`A1BG 1 NM_130786.4 true true`), so
  the "`mane_select` AND an ENSG-shaped `gene_id`" rule still separates the two MANE rows.
- **Three things the pin move has to carry**: read the `.bgz` (a gzip member stream, so a gzip reader takes it);
  the compressed download alone is six times the old plain file, so the snapshot's declared size (RM229) moves; and the lane label moves (`gnomad_v4.1_constraint` → a 4.1.2 one), which with
  item 1 means every module's `gene_metrics.csv` drafted from the snapshot reads as stale against the new lane.
- **`@constraint-two-releases`** applies: the snapshot and the live API route must stay distinguishable. Check
  which release the live route answers before the snapshot moves past it.

Not measured: the whole file (only its header and first rows), and whether the live API already serves 4.1.1+
values.

## Verdicts

- **`constraint`**: filed by the lead as **RM410** (2026-11-07), for the pm to size, from the adoption note above.
- **`clinvar`, `civic`, `strchive`, `mitomap`**: rebuild and publish handed by the lead to the maintainer (2026-11-07);
  publishing is theirs. **Published 2026-11-07** on the pm's sign-off (re-read from the hub that evening).
- **This machine's shared cache** (`/data/just-dna-cache`) still holds the old labels for those four: `cache pull`
  would bring it level. Whose call that is, on a cache other seats' runs read, is the lead's.

## Outbound

None.
