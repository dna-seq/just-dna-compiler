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

- **Last measured:** 2026-11-07, by hand (curl against each source, `cache status`, each HF repo's `release.json`).
- **Next:** weekly, with the dependency bump; earlier when a lane's builder or a source announces a release.

## The table (2026-11-07)

| Lane | Available (source) | Built (this machine) | Published (HF) | Behind? |
| --- | --- | --- | --- | --- |
| `ensembl` | Ensembl **116** (REST `/info/data`; FTP tops at `release-116`) | `ensembl-variation-2026_07_13-vep116.0` | `ensembl-variation-2026_07_13-vep116.0` (`ensembl_variations_split`, `manifest.json`; that repo has no `release.json`) | no |
| `clinvar` | weekly `clinvar_20261101.vcf.gz`; `clinvar.vcf.gz` modified 2026-11-02 | `clinvar_2026-06-27` | file date `2026-08-29` (its `release.json` carries no `dataset`) | **yes**: published is 9 weeks behind the source, and this machine's cache is 2 months behind published |
| `constraint` | gnomAD **v4.1.2** (`release/4.1.2/constraint/` exists; so does 4.1.1) | `gnomad_v4.1_constraint` | `gnomad_v4.1_constraint` | **yes**: the builder pins `release/4.1/` (`constraint_build.py:60`) |
| `clinpgx` | unchecked: the archive's `Last-Modified` reads 2025-07-05, older than the label we built, so that header is not the release date | `clinpgx_2026-08-05` | `clinpgx_2026-08-05` | unchecked |
| `cpic` | unchecked: the label is a hash of the API's answer, so only a rebuild says whether it moved | `cpic_snapshot_b0ffd4c6f010` | `cpic_snapshot_b0ffd4c6f010` | unchecked |
| `drug_labels` | unchecked (ClinPGx, as above) | `clinpgx_drug_labels_2026-08-05` | `clinpgx_drug_labels_2026-08-05` | unchecked |
| `pharmvar` | unchecked: personal API key, and the label is a hash | `pharmvar_snapshot_56d4125c2ce4` | none (no repo: the lane is unpublishable) | unchecked |
| `pubmind` | `hg38_pubmind_db.txt.gz` modified 2026-08-24 | `pubmind_ca224ebf5ef3` (a hash) | none (no repo) | unchecked: a hash label cannot be compared with a date |
| `civic` | monthly **01-Nov-2026** (`/downloads/01-Nov-2026/` answers 200) | `civic_01-Sep-2026` | `civic_01-Sep-2026` | **yes**: two monthly releases |
| `strchive` | **v2.28.0** (GitHub release, 2026-10-08) | `strchive_v2.26.0` | `strchive_v2.26.0` | **yes**: v2.26.1, v2.27.0 and v2.28.0 since |
| `mitomap` | `mitomap.dump.sql.gz` modified 2026-11-06 | `mitomap_2026-08-21+2026-08-19` | `mitomap_2026-08-21+2026-08-19` | **yes**, by file date; whether the content moved needs a rebuild |
| `mitomap_miss` | derived from `mitomap` and `clinvar` | no label (`release.json` carries counts only) | none (no repo) | follows its parents |
| `mane` | **v1.5** (`release_1.5/` is the newest directory) | `mane_grch38_v1.5` | none (no repo) | no |
| `acmg` | unchecked: the list is a journal supplement, with no index to poll | SF **v3.3** (DOI 10.1016/j.gim.2025.101454) | none (no repo) | unchecked |
| `opentargets` | **26.09** (newest directory on the EBI FTP; 26.06, 26.03 before) | `opentargets_26.09` | unchecked: the repo answers 401, being published today (RM408) | no |
| `alphagenome_avi` | unchecked: no release index found yet | absent here | `2026-08-27` | unchecked |
| `clinvar_gkm` | Parquet set **2026-10-24**; the weekly line is at 2026-10-31 (the release index) | absent here | `clinvar_gkm_2026-10-24` (published today) | no: the set, not the line, is what a rebuild takes |

## What the table says

1. **Four lanes are behind their source on the published copy**: `clinvar`, `constraint` (a pinned point
   release), `civic` and `strchive`; `mitomap` probably is. A rebuild and a publish is the lead's (the builders and
   the publish are code and outbound); this seat schedules it and says when.
2. **This machine's `clinvar` cache is older than the published one** (06-27 against 08-29): `cache pull clinvar`
   would bring it level, before any rebuild.
3. **Three lanes have labels a date cannot be compared with** (`cpic`, `pharmvar`, `pubmind` are hashes). Their
   currency is known only by rebuilding and comparing hashes. Whether that is worth a weekly run is open.
4. **Lanes with a currency command already ask the source**: `clinvar_gkm` (`ClinVarGkmClient.current_release`)
   and ClinVar. The other lanes have none; the probe here is curl by hand.

## Verdicts

None filed yet. The table goes to the lead with the four lanes behind; the lead decides the rebuilds.

## Outbound

None.
