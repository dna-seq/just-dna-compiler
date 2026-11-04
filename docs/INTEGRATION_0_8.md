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
| `archive_last_modified` in the ClinPGx snapshot's `release.json` | RM283 | `Last-Modified` of the lane's archive and its sibling archives at build time (name → ISO date, `null` where the `HEAD` did not answer). Absent on a snapshot built from a local archive. RM303 will give `release.json` a model on this branch; this key is one it has to carry. |

## 1.5 New optional authored columns (no break)

A new optional column is minor-legal (Principle 3). A 0.7 `just-dna-format` refuses a CSV carrying one
(`extra="forbid"`), so an authoring tool reading 0.8 specs upgrades with them; a reader of the parquet
sees more columns.

| Surface | Item | What changed |
| --- | --- | --- |
| `diplotypes.csv` / `diplotypes.parquet` `negatives`, `category` | RM322 | Free text, the `VariantRow` columns of the same names; `category` has no vocabulary. Null when unstated. Appended as the last two columns, so every 0.7 column keeps its position. Every module carrying `diplotypes.csv` gets a new `artifact.digest` on a 0.8 recompile, with `content_signature` unchanged unless a cell is filled. |

## 1.6 A new refusal: HLA allele names on `allele_function.csv`

Where `gene` starts with `HLA-`, `allele` must follow IPD-IMGT/HLA's grammar (`*`, two to four
colon-separated numeric fields, an optional `N`/`L`/`S`/`C`/`A`/`Q` suffix), or `validate` and
`compile` refuse the row (RM334). Other genes are unaffected. Principle 3 holds: the published-module
scan of 2026-11-04 found no `allele_function.csv` row with an `HLA-` gene in the reference examples (two
files) or in the registry's prod catalogue (24 modules, 46 versions; the one module carrying the table,
`antonkulaga/fut2_secretor`, names only `FUT2`). A tool that writes HLA alleles into this table, or a
module built outside the catalogue, should spell them `*15:01`, never `*1501` or `HLA-DRB1*15:01`.

## 2. What to change

1. If you parse `manifest.json` with `just-dna-format`, move your pin to 0.8 when you start reading
   manifests compiled by 0.8 (§ 1).
2. If you key on `warnings_summary`, the new codes are listed in § 1 with their meaning, and
   `quality_floor_inverted` will stop appearing (§ 1.1).
