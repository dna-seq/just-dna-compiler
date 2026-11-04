# Integrating 0.8 — what changed against the 0.7 surfaces

For the repos that consume this one: **just-dna-pipelines**, **just-dna-lite**,
**just-dna-marketplace**, **just-dna-agents**, **just-dna-registry**. It answers one question:
*given a working 0.7 integration, what do I have to check, and what do I have to change?*

**Status: 0.8 is being built on the `0.8` branch and is not cut.** Nothing here is installable yet.
This document is opened by the first 0.8 item that changes what an older reader can parse, and each
later item adds its line. [RM_TOC.md](RM_TOC.md) is the per-item record; a status sentence here goes
stale when work lands, so check it there.

---

## 1. The old-reader break: new warning codes

`ModuleManifest.compilation.warnings_summary` validates its keys against `VALID_WARNING_CODES`, which
is a closed vocabulary. A reader pinned to an older `just-dna-format` therefore **refuses** a manifest
that carries a code added after its pin: `read_manifest` raises rather than ignoring the key. This is
the same shape as 0.7's `verification.checks[].producer` break
([INTEGRATION_0_7 § 1](INTEGRATION_0_7.md)), and the remedy is the same: **a consumer reading manifests
compiled by 0.8 upgrades `just-dna-format` to 0.8 with them.** Only a manifest whose module actually
triggers one of these findings carries the code, so most 0.8 manifests still parse under 0.7; do not
rely on that.

| Code | Item | What it says |
| --- | --- | --- |
| `conclusion_names_other_genotype` | RM308 | A `variants.csv` conclusion names another genotype at its locus and never its own row's: two conclusions look swapped, or one was copied from a neighbour. RM279's hint rule, now at `validate`/`compile`. A warning in both modes. Actionable. |
| `qual_floor_on_reference_evidence` | RM313 | A `requires_callable` row states its `min_quality` floor against QUAL, which the reference record it is decided from usually leaves missing. Replaces `quality_floor_inverted` (§ 1.1). A warning in both modes. Actionable. |
| `fact_rows_contradict` | RM275 | Two rows of a derived fact table (`frequencies`, `gene_metrics`, `literature`, `gene_validity`, `clinical_assertions`, `gwas_effects`, `expression_effects`) share a merge key and state different values for one fact. A warning in both modes; refused from 1.0. Actionable: delete the wrong row, or delete the table and re-run the pass. |

### 1.1 A retired code: `quality_floor_inverted`

RM57's `quality_floor_inverted` is **emitted by nothing from 0.8 on**, because it misstated the VCF
spec: it said a high QUAL on a reference record means the position is probably variant, and QUAL there
is the confidence in the reference call (§1.6.1 item 6, unchanged in 4.5). Its advice to use GQ was
ungrounded too. The code **stays in `VALID_WARNING_CODES`**, so every reader keeps parsing manifests
that carry it, and `vocab.RETIRED_WARNING_CODES` declares it with the reason. If you keyed on it, key on
`qual_floor_on_reference_evidence` instead, which fires on the same rows and says what is actually
wrong. The phrase constant `QUAL_INVERSION_PHRASE` is gone from the compiler; its text stays listed in
COMPILER.md § The phrases, under *retired*, for grepping old manifests.

## 1.2 New manifest fields (no break)

`Stats` ignores keys it does not know, so a 0.7 reader parses these and drops them.

| Field | Item | What it holds |
| --- | --- | --- |
| `stats.clin_sig_counts` | RM300 | Authored `variants.csv` rows per ClinVar tier, from the effective `clin_sig`, every `VALID_CLIN_SIG` member present (zeros included) in sorted order. Rows, the grain of `pathogenic_count`. Empty on a manifest compiled before 0.8, which means *not counted*, never zero. |
| `stats.clin_sig_variant_counts` | RM300 | Distinct `variant_key`s per tier, keyed the same way. |

## 1.3 New derived column and client method (no break)

| Surface | Item | What changed |
| --- | --- | --- |
| `literature.csv` / `literature.parquet` `fulltext_status` | RM258 | New optional derived column, `retrieved \| absent \| unreachable`, null for *not asked*. A 0.7 reader of the parquet sees one more column; the fact signature does not include it. |
| `EuropePmcClient.fetch_fulltext`, `PmcBiocClient.fetch_fulltext`, `literature.FulltextUnavailable` | RM258 | The three-way form of the fulltext question. `fulltext()` is unchanged, so a caller that treats its `None` as "no text either way" keeps working; move to `fetch_fulltext` to tell an outage from an absent copy. |

## 1.4 A new `release.json` key (no break)

| Key | Item | What it holds |
| --- | --- | --- |
| `archive_last_modified` in the ClinPGx snapshot's `release.json` | RM283 | `Last-Modified` of the lane's archive and its sibling archives at build time (name → ISO date, `null` where the `HEAD` did not answer). Absent on a snapshot built from a local archive. Carried by `SnapshotRelease` as an extra key (§ 1.5). |

## 1.5 The reference-snapshot contract moves into `just-dna-format` (RM303)

A new module, **`just_dna_format.snapshot`**, holds what a reference snapshot looks like on disk: the
layout names (`SNAPSHOT_DATA_DIRNAME`, `SNAPSHOT_SIDECAR_DIRNAMES`, `CITATIONS_DIRNAME`,
`RELEASE_FILENAME`, `SNAPSHOT_LICENSE_FILENAME`, `SNAPSHOT_ROOT_FILENAMES`, the two named payload files),
**`SnapshotRelease`**, the model of `release.json`, and `read_release`, `write_release`, `release_label`,
`release_is_unreadable` and `holds_snapshot_payload`. A repo that wanted the layout no longer has to
import the network tier for it. `just_dna_enricher.locations` imports every one of these names, so an
import from there keeps working.

| Surface | What changed | What to do |
| --- | --- | --- |
| `locations.read_release(dir)` | Returns a `SnapshotRelease` or `None`, not a `dict` or `None`. `None` still means absent **or** unreadable. | `release.get("dataset")` becomes `release.dataset`, or call `snapshot.release_label(dir)`. A caller that only tests `is None` (just-dna-marketplace's `cache status`) changes nothing. |
| `release.json` keys | Written in the canonical spelling by every builder: `license` (CIViC wrote `licence`), `row_count` for a total (AlphaGenome AVI wrote `rows`), `row_counts` for a per-file map (MANE and MITOMAP wrote `rows`). ClinVar's now carries `dataset` (`clinvar_<fileDate>`). | A reader of the raw JSON that keys on `rows` or `licence` reads the canonical key, or reads through `SnapshotRelease`, which maps the old spellings of snapshots already published. |
| `CacheLane.release_label` | No lane overrides it; ClinVar's per-lane reader (`clinvar_dataset_label` as the lane's `release_label`) is gone. ClinVar's label is unchanged, for snapshots built before and after 0.8. | Nothing, unless you compared `lane.release_label` against `caches._dataset_label`, which no longer exists: compare against `snapshot.release_label`. |
| `clinpgx.load_snapshot`, `CpicSnapshotClient.release`, `PharmVarSnapshotClient.release`, `mitomap_miss_build.read_miss_release` | Return or hold a `SnapshotRelease` (empty when the file is absent), not a `dict`. | Attribute access instead of `.get`. |

## 2. What to change

1. If you parse `manifest.json` with `just-dna-format`, move your pin to 0.8 when you start reading
   manifests compiled by 0.8 (§ 1).
2. If you key on `warnings_summary`, the new codes are listed in § 1 with their meaning, and
   `quality_floor_inverted` will stop appearing (§ 1.1).
3. If you read a snapshot's `release.json`, through `locations.read_release` or by hand, read § 1.5:
   the reader returns a model, and three keys are spelled differently in a snapshot built by 0.8.
