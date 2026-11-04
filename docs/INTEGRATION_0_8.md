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
| `log_file_not_shipped` | RM337 | A file under the module's `logs/` that compile discovery left behind, with the path and its reason (one of `LOG_NOT_SHIPPED_REASONS`: hidden path, symlink or a path under one, a file over the ceiling, a file the compile could not read, an image with the wrong signature, SVG, another extension, not UTF-8, `.json` or a `.jsonl` line that does not parse; RM348 adds the unreadable arm and holds a top-level `*.log` to the same rules). Text: `<path> does not ship with the module: <reason>.` A warning in both modes. Actionable: fix, rename or remove the file. |
| `fact_rows_contradict` | RM275 | Two rows of a derived fact table (`frequencies`, `gene_metrics`, `literature`, `gene_validity`, `clinical_assertions`, `gwas_effects`, `expression_effects`) share a merge key and state different values for one fact. A warning in both modes; refused from 1.0. Actionable: delete the wrong row, or delete the table and re-run the pass. |
| `vrs_version_differs` | RM304 | A `resolution.csv` row's `vrs_spec` names a VRS version other than the module's pin (`compilation.vrs_version`). Reported beside each allele's own verdict, never instead: within the pin's major a substitution that recomputes differently is still the mismatch error, and only one under another major (a different digest serialization) is counted in this line. The enricher's mint pass emits it too, for a recorded id under a version other than its own. One line per stated version. A warning in both modes. Actionable: clear `vrs_id` and `vrs_spec` on those rows and re-run `just-dna-enricher vrs mint`. |
| `meta_selector_matches_nothing` | RM28 | A `meta.csv` member matches no row of its table, almost always a value spelled other than the table stores it. A warning in both modes. Actionable. |
| `phenotype_class_unrecognized` | RM326 | A `studies.csv` `phenotype_class` outside the recommended twelve (`RECOMMENDED_PHENOTYPE_CLASSES`), one finding naming each token with its row count. The set is open and the rows stand. A warning in both modes. Actionable: respell a second spelling of a recommended class, or leave a genuinely new class. |
| `meta_member_allele_ambiguous` | RM28 / RM327 | A bare-locus member (`variants[variant_key=…]`) on a `meta.csv` row stating a `direction`, whose `variants.csv` rows do not share one `effect_allele`; the row's direction is withheld (`meta.parquet` `withheld`). A warning in both modes. Actionable. |

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
| `compilation.toolchain` | RM342 | The libraries that wrote the bytes, `{"polars": "2.1.0", "python": "3.13.1"}`; a library added later is a new key. Outside `artifact.digest`. `null` on a manifest compiled before 0.8, which means *not recorded*. `Compilation` ignores unknown keys too, so a 0.7 reader drops it. |
| `compilation.vrs_version` | RM304 | The VRS spec version, at its minor (`"2.0"`), the module's `vrs_id`s are pinned to: the rule this compiler verifies them against. `null` when no allele in `resolution.csv` carries an id, and on a manifest compiled before 0.8. `Compilation` ignores keys it does not know, so a 0.7 reader drops it. |

`ModuleManifest` itself ignores keys it does not know, so a 0.7 reader parses these top-level fields
and drops them too.

| Field | Item | What it holds |
| --- | --- | --- |
| `tier_scale` | RM324 | The scale `meta.csv`'s `tier` grades on, copied from `module_spec.yaml`'s new `tier_scale:` (free text). Absent when the module states no tier. |
| `meta_selectors` | RM28 | Every member of every `meta.csv` row with the number of rows it matched: `{row, selector, matches}`, `row` the 0-based `meta.parquet` row, `selector` verbatim. `null` when the module carries no `meta.csv`. |

## 1.2.1 A new authored table and its two parquets (no break)

A module may carry `meta.csv` (RM28, RM323, RM324; RM327's per-trait rows; RM330's `sex`; `drug`). It compiles to
two new parquets, listed after `overrides.parquet` in `ARTIFACT_PARQUETS`: neither is in `LEAD_PARQUETS`,
and a module carrying no `meta.csv` carries neither file and keeps its digest. A 0.7 reader of the
artifact ignores both, and therefore shows a member row's own finding where a matching combination
replaces it (the accepted cost, RM28).

| Parquet | One row per | Columns a consumer reads |
| --- | --- | --- |
| `meta.parquet` | authored `meta.csv` row, in authored order | every authored cell; `members_key`; `match_count`; `matches` (list of `{member, table, key}`, `key` in that table's `_KEY_FIELDS` order); `replaces` (a matching combination replaces the findings of exactly the rows in `matches`); `withheld` |
| `meta_resolved.parquet` | (single-statement row a one-member meta row reaches, `sex` scope, `drug` scope) | `table`, `key`, `sex`, `drug`, `tier`, `age_of_action`, `age_of_action_confidence`, `flags` after precedence; `tradeoff` (RM327: true when one member reaching the row has a `protective` and a `risk` per-trait row, otherwise null, **never false**); `withheld`; `meta_rows` |

The table's key is `(members_key, trait_efo_id, sex, drug)`: `sex` and `drug` each scope a whole row, so one
member set may state one finding per sex and per drug (CPIC's TPMT × NUDT15 pair, once per thiopurine). A
consumer looks up a target in `meta_resolved.parquet` by a `(sex, drug)` pair it builds per axis: its own
value where the target has rows for that value, and `null` where it has none (a `female` consumer at a
target only `male` rows scope, or a drug no row names) or the consumer does not condition on the axis. The
compile writes every combination of the values the rows reaching a target state, so that pair exists
whenever any row applies in it: a `male` row and an `azathioprine` row also yield a `(male, azathioprine)`
row, where a disagreeing column between the two is withheld. No row for the pair means no row applies.
A `meta.parquet` row's `replaces` holds within that row's own scope: a combination scoped to
`mercaptopurine` replaces the rows it matches for a consumer on mercaptopurine, not for one on another drug
or on none.

A `variants` match is keyed by the authored `(variant_key, genotype)`; for an rsID that resolution expands
onto several loci, `weights.parquet` keys those rows by coordinate, and they are reached through `rsid`.
`module_spec.yaml` gains the optional `tier_scale:`; a `tier` cell without it is refused.

`tradeoff` leaves `vocab.RESERVED_NAMES_0_4` (three names now) for `vocab.MISPLACED_COLUMN_REASONS`: a
`tradeoff` column on any authored table is still refused, now with the reason that the compiler computes
it. A consumer reading `RESERVED_NAMES_0_4` to list unwritable names should read both maps;
`authoring_reference()` carries the second as the new key `misplaced_columns`.

## 1.2.2 A new authored table: model-organism evidence (no break)

A module may carry `model_organisms.csv` (RM335): one row per model-organism lifespan finding about a
human gene, `gene` required, `orthologue`, `species`, `model_type`, `sex` (the animals', free text),
`diet`, `lifespan_effect`, `concordance` (closed: `concordant`, `discordant`, `nonmonotone`; empty is
unstated), `pmid`, `doi` (optional; an uncited row draws no warning). It compiles verbatim to
`model_organisms.parquet`, listed last in `ARTIFACT_PARQUETS` and not in `LEAD_PARQUETS`; a module
carrying no such file keeps its digest. **Annotation only**: it reaches no weight, effect, tier or
meta-table member, it does not make a directory a module on its own, and its genes are not in
`manifest.stats.genes` nor in the enricher's gene-level scope (constraint, gene validity, dosage). A 0.7 reader of the artifact ignores the parquet; a 0.7 compiler does not read
the CSV, so it neither checks nor compiles it.

## 1.2.3 Three derived tables, three parquets, and RM239's two columns (no break)

The Open Targets lane (RM333, RM239, RM236) adds three machine-written sidecars beside the spec, each
compiled to its own parquet listed after `expression_effects.parquet` in `ARTIFACT_PARQUETS` (none is a
`LEAD_PARQUET`; a module carrying none of them keeps its digest), each summarised by a new top-level
manifest block that `ModuleManifest` lets a 0.7 reader drop. No new warning code.

| Surface | One row per / what it holds |
| --- | --- |
| `locus_to_gene.csv` → `locus_to_gene.parquet`, manifest `locus_to_gene` | (study locus, gene, module variant): the L2G score of every GWAS credible set the module's variant is a member of, led or not; key `(study_locus_id, gene_id, variant_key)`; `lead_variant_id` names the set's lead |
| `colocalisations.csv` → `colocalisations.parquet`, manifest `colocalisations` | (left, right study locus, module variant): `h4`, `clpp`, the right study's type, gene and tissue; key `(study_locus_id, right_study_locus_id, variant_key)` |
| `consequences.csv` → `consequences.parquet`, manifest `consequences` | (variant, transcript): `consequence_so_ids`, `impact` (closed: HIGH, MODERATE, LOW, MODIFIER), `mane_select`, `canonical` |
| `gwas_effects.csv` / `.parquet` `posterior_probability`, `fine_mapping_method`; manifest `gwas_effects.with_posterior` | two optional columns, empty unless exactly one fine-mapping value answers; a 0.7 reader of the parquet sees two more columns, and a 0.7 `validate_spec` refuses a `gwas_effects.csv` carrying them (`extra="forbid"`), so upgrade before enriching |

The manifest blocks are `{signature, sources, datasets, row_count, variant_count}`. `VALID_SOURCE_LAYERS`
gains `locus_to_gene`, `colocalisation` and `consequence`; a 0.7 reader refuses a `sources.csv` row
carrying one, which is the same upgrade-first rule.

**A `resolution.csv` row with an rsID and no ALT is answered (added 2026-11-04).** The pass takes the
release's allele when exactly one at the row's position carries the rsID, on the row's REF, and no
other allele there could be the one, and withholds the row otherwise; ENRICHER.md's Open Targets section has the arms. For a
consumer: rows in the four tables may now be of an allele the module did not author, and nothing on the
row says so; the pass's result names those keys (`allele_supplied`) beside the withheld ones
(`allele_unstated_withheld`, `allele_unstated_no_rsid`, `allele_unstated_unasked`), `summarise` and the
CLI count them, and `PosteriorCounts` gains `allele_withheld`. For an operator: the lane snapshot's
`variants.parquet` gains the list column `rs_ids`, so **rebuild the `opentargets` snapshot**; an older
one answers those rows as not asked, and `--strict` refuses it when the module has such a row. No new
warning code.

## 1.2.4 The computed LD pair: one derived table, one parquet (RM331, no break)

`ld_pairs.csv` → `ld_pairs.parquet`, listed after `consequences.parquet` in `ARTIFACT_PARQUETS` (not a
`LEAD_PARQUET`; a module carrying none keeps its digest), summarised by a new top-level manifest block
`ld_pairs` (`{signature, sources, datasets, populations, row_count, with_r2}`) that a 0.7 reader drops. Key
`(proxy_rsid, variant_key, ld_population)`; `status` is the closed `VALID_LD_PAIR_STATUS` (`resolved`,
`not_reported`, `rsid_unknown`, `ancestry_mixed`, `ancestry_unstated`, `lead_has_no_rsid`), and only
`resolved` carries `r2`/`d_prime`. `VALID_SOURCE_LAYERS` gains `ld_pair`; a 0.7 reader refuses a
`sources.csv` row carrying it, the same upgrade-first rule as 1.2.3. Written by the new
`just-dna-enricher ld-pairs` command (online only). No new warning code.

## 1.3 New derived column and client method (no break)

| Surface | Item | What changed |
| --- | --- | --- |
| `literature.csv` / `literature.parquet` `fulltext_status` | RM258 | New optional derived column, `retrieved \| absent \| unreachable`, null for *not asked*. A 0.7 reader of the parquet sees one more column; the fact signature does not include it. |
| `EuropePmcClient.fetch_fulltext`, `PmcBiocClient.fetch_fulltext`, `literature.FulltextUnavailable` | RM258 | The three-way form of the fulltext question. `fulltext()` is unchanged, so a caller that treats its `None` as "no text either way" keeps working; move to `fetch_fulltext` to tell an outage from an absent copy. |
| `resolution.csv` `vrs_spec` (since 0.5), `vrs.vrs_spec_release`, `just_dna_enricher.vrs.MINTER_VRS_VERSION` | RM304 | No new column: the per-row VRS version already existed as `vrs_spec` and is now **read**. The enricher stamps it from `ga4gh.vrs.VRS_VERSION` at the spec's minor (`"2.0"`, as before) on the rows it mints, and leaves a recorded id's cell alone; an empty cell means *unstated*, never the current version. No parquet carries it yet; RM270 carries the minted `vrs_id` and its version onto the artifact. |

## 1.4 A new `release.json` key (no break)

| Key | Item | What it holds |
| --- | --- | --- |
| `archive_last_modified` in the ClinPGx snapshot's `release.json` | RM283 | `Last-Modified` of the lane's archive and its sibling archives at build time (name → ISO date, `null` where the `HEAD` did not answer). Absent on a snapshot built from a local archive. Carried by `SnapshotRelease` as an extra key (§ 1.9). |

## 1.5 The pmid/doi pair on every citing table (RM336)

| Surface | What changed |
| --- | --- |
| `pmid` on `studies.csv`, the four binning kinds, `pharm_variants.csv`, `gwas_effects.csv` | **A tightening:** a cell whose only identifier is a DOI is refused, naming it (before, `10.1101/…` parsed as PubMed ids `10`, `1101`, …). Every published module was scanned first (the prod registry, all 24 modules and every version, and `reference_examples/`): no `pmid` cell holds a DOI, so nothing published stops validating. `gwas_effects.csv`'s `pmid` is now checked by the same grammar; it had none. |
| `pmid` = `NONE` | **New accepted value**, exactly that spelling: the work has no PubMed record, and `doi` must then name it. A 0.7 reader **refuses** a module using it (`must contain at least one PubMed ID`), so a deployment validating 0.8 modules server-side upgrades with them. `extract_pmids("NONE")` is empty. |
| `doi` on the binning kinds, `pharm_variants.csv`, `gwas_effects.csv` | **New optional column** (authored on the first two, derived on the third), checked for a DOI token when stated. A 0.7 reader refuses it as an unknown column (`extra="forbid"`). The compiled `*.parquet` for each gains a nullable `doi` column, so recompiling a module with one of those tables moves its `artifact.digest`; `content_signature` moves only where a `doi` is filled, and the `gwas_effects` fact signature does not move for an empty one. |
| `spec.CitationPair`, `spec.check_citation_pair`, `spec.validate_doi_cell`, `spec.PMID_NONE`, `spec.cited_as`, `spec.doi_key` | New public names: the shared rule, for a consumer writing its own citing table, and how a message names a `NONE` row. |
| `duplicate_study_citation`, `study_effect_allele_not_at_locus`, `p_value_encodings_disagree` | Unchanged codes, and unchanged text for every row with a real `pmid`. A `NONE` row is named `NONE doi <doi>`; two `NONE` rows on one variant are distinct when their DOI tokens differ (case and a doi.org prefix ignored). |
| `verification.json` `provenance_quote` and `citation_existence` records | **Since RM349** a `NONE` citation is asked about by its DOI: Crossref for existence, the text Europe PMC holds for that DOI for the quote. Each distinct DOI with a verdict is a `citation_existence` subject and one no agency knows a finding (named in `detail` with the title Crossref found); each quote a text settled is a `provenance_quote` subject. A module citing only by DOI records `citation_existence` with `source="crossref"`, or skips it as `not_requested` (`--no-doi`) or `unreachable`. Offline both records say `offline` (before RM349 the quote record said `unsupported`); `unsupported` is left for a row whose `doi` carries no DOI token. A module citing only by DOI is not refused by `enrich_literature` as citing nothing. |
| `LiteratureResult.doi_citations`, `literature.DoiCitation`, `CrossrefWork.agency`, `EuropePmcClient.record_for_doi` / `fetch_preprint_fulltext` / `repo_url`, `just_dna_format.literature.settled_quotes` | RM349. New names, no break: one `DoiCitation` per DOI-only citation (existence, the title, `fulltext_status`, the quote counts); the agency that registered a DOI; the DOI search and the preprint-repository fetch; and `LiteratureRow.quotes_checked`'s rule as a function. **A behaviour change for every caller of `CrossrefClient.work`/`exists`**: a DOI another agency registered (a DataCite dataset) now answers `exists=True` with `agency` set and no title, where it answered `False`; the 404 costs one more request. Nothing is written to `literature.csv` for a `NONE` row. |

## 1.6 New optional authored columns (no break)

A new optional column is minor-legal (Principle 3). A 0.7 `just-dna-format` refuses a CSV carrying one
(`extra="forbid"`), so an authoring tool reading 0.8 specs upgrades with them; a reader of the parquet
sees more columns.

| Surface | Item | What changed |
| --- | --- | --- |
| `studies.csv` / `studies.parquet` `sample_size`, `sample_unit`, `n_cases` | RM325 | The total analysed (cases included), what it counts (`individuals` or `lives`, closed) and the case count. The counts are `Int64` in the parquet. A size without a unit, or more cases than analysed, is refused. Appended after every 0.7 column. Every module carrying `studies.csv` gets a new `artifact.digest` on a 0.8 recompile, with `content_signature` unchanged unless a cell is filled. |
| `studies.csv` / `studies.parquet` `phenotype_class` | RM326 | Which outcome the study measured; open, recommended over v2's twelve classes, and a token outside them draws `phenotype_class_unrecognized`. Null when unstated. |
| `studies.csv` / `studies.parquet` `ancestry` | RM328 | The 1000 Genomes superpopulation code(s) the estimate was measured in, closed over `VALID_SUPERPOPULATIONS` (`AFR`, `AMR`, `EAS`, `EUR`, `SAS`) and multi-valued: a `List(Utf8)` parquet column, `\|`-joined in the CSV. `pgs.VALID_TRAINING_ANCESTRY` is now derived from the same constant (members unchanged). |
| `studies.csv` / `studies.parquet` `age_min`, `age_max`, `age_of` | RM329 | The age band an estimate covers, in years (`Float64`, either bound may be null: an open band), and whose age it is (`participant` or `parent`, closed). No rule ties the three together. |
| `studies.csv` / `studies.parquet` `stratum`, `stratum_level` | RM330 | The modifier an estimate was measured within and its level, free text, both or neither (one without the other is refused). |
| `studies.csv` / `studies.parquet` `proxy_rsid` | RM331 | The LD proxy a study measured in place of the row's lead. `study_effect_allele_not_at_locus` then reads the proxy's resolved alleles, and its text names both (`<lead> via proxy <proxy> (PMID …)`, `at the proxy`); a row with no proxy keeps the 0.7 text byte for byte. The enricher resolves each proxy as a subject, so `resolution.csv` gains rows for rsIDs no other table names (keyed by the rsID); the GWAS, frequency and clinical-assertion passes leave them out, so no fact table gains a row for a proxy. A reader treating every `resolution.csv` row as a module locus should do the same: a proxy-only rsID is a `studies.csv` `proxy_rsid` that no other table names. |
| `studies.parquet` `proxy_loci` (compiler-filled) | RM331 | `List(Struct{rsid, chrom, start, ref, alts, locus_index})`: the proxy's resolved loci on the module's build, null when the row names no proxy or the proxy did not resolve. Not authored and never written to `studies.csv`; `reverse` re-emits them as the proxy's `resolution.csv` rows, so `compile → reverse → compile` keeps `resolution_signature`. Appended last, so **every module carrying `studies.csv` gets a new `artifact.digest` on a 0.8 recompile**; `content_signature` does not move. |
| `studies.csv` / `studies.parquet` `effect_unit` | RM332 | The unit of `effect_size`, free text and verbatim (as on `gwas_effects.csv`). |
| `weights.parquet` `effect_unit` (derived) | RM332 | The unit of the variant's effect, joined from its study rows when every one that states a unit states the same one; null when none does or two disagree. Not authored on `variants.csv` and never written back by `reverse`. Appended after every 0.7 column, so **every module carrying `variants.csv` gets a new `artifact.digest` on a 0.8 recompile**; `content_signature` does not move. |
| `weights.parquet` `eur_only_evidence` (derived) | RM328 | Nullable `Boolean`: true when every supporting study row states only `EUR`, false when one states another code, null when any states none or the variant has no study rows. Repeated on each genotype row of the locus. |
| `weights.parquet` `outcome_healthspan`, `outcome_lifespan`, `outcome_exceptional` (derived) | RM326 | Nullable `Boolean`, **true or null, never false**: true when a supporting study row's `phenotype_class` maps to the cell (`vocab.OUTCOME_STRIP_CELLS`), null meaning *not studied*. True says the outcome was studied at the locus, not that an effect was found. |
| `diplotypes.csv` / `diplotypes.parquet` `negatives`, `category` | RM322 | Free text, the `VariantRow` columns of the same names; `category` has no vocabulary. Null when unstated. Appended as the last two columns, so every 0.7 column keeps its position. Every module carrying `diplotypes.csv` gets a new `artifact.digest` on a 0.8 recompile, with `content_signature` unchanged unless a cell is filled. |

## 1.7 A new refusal: HLA allele names on `allele_function.csv`

Where `gene` starts with `HLA-`, `allele` must follow IPD-IMGT/HLA's grammar (`*`, two to four
colon-separated numeric fields, an optional `N`/`L`/`S`/`C`/`A`/`Q` suffix), or `validate` and
`compile` refuse the row (RM334). Other genes are unaffected. Principle 3 holds: the published-module
scan of 2026-11-04 found no `allele_function.csv` row with an `HLA-` gene in the reference examples (two
files) or in the registry's prod catalogue (24 modules, 46 versions; the one module carrying the table,
`antonkulaga/fut2_secretor`, names only `FUT2`). A tool that writes HLA alleles into this table, or a
module built outside the catalogue, should spell them `*15:01`, never `*1501` or `HLA-DRB1*15:01`.

## 1.8 The CPIC drafter's output (no break)

| Surface | Item | What changed |
| --- | --- | --- |
| `pgx_draft.draft_gene` / `draft --gene` | RM253 | CPIC's `DEL<bases>`/`INS<bases>`/`UNIT(n)` defining alleles are drafted as VCF-anchored, left-normalized REF/ALT rows (UGT1A1 `*28` = `2:233760233 C>CAT`), keyed by coordinate for a repeat; HGVS-named alleles are written with spaces dropped and `&` for the comma (`c.1003G>T(*11)`). A tool that drafts DPYD, RYR1, CACNA1S or MT-RNR1 gets rows where it got none. A new optional `sequences` argument; spelling reads GRCh38 bases from the seqrepo service, so `--offline` withholds those rows with a stated reason. |
| CPIC client warnings | RM253 | `defining_variants` no longer returns a "skipped — … notation" line; the drafter reports what it could not spell, one line per reason (`not spelled — a bare \`DEL\`…`, `… alternatives …`, `… could not be read …`). A consumer that grepped the old sentence, which named RM253 as tracking it, reads the new ones. |

## 1.9 The reference-snapshot contract moves into `just-dna-format` (RM303)

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

## 1.10 A behaviour narrowing: what a `*.log` ships (no new code)

| Surface | Item | What changed |
| --- | --- | --- |
| log discovery in `compile_module` | RM348 | A symlinked `*.log` (beside the spec or under `logs/`), anything under a `logs/` that is itself a link, and any discovered file over `LOG_MAX_BYTES` (5 MiB) used to ship, the `*.log` ones since before RM338; they now stay behind with `log_file_not_shipped`. A file the compile cannot read stays behind the same way instead of failing the compile, and a directory it cannot list is named in place of the files it hides. An explicit `log_files` list is unaffected. The ceiling is now `LOG_MAX_BYTES`; `LOG_IMAGE_MAX_BYTES`, RM338's name on `main`, stays as an alias of it. |

## 1.11 A new release-change kind: `toolchain` (an old-reader break)

`DeclaredChange.kind` (in `just_dna_format.release_records`) validates against
`VALID_RELEASE_CHANGE_KINDS`, a closed vocabulary that gains `toolchain` in 0.8 (RM352): the bytes
moved, the content did not, and the recorded toolchain (`compilation.toolchain`) says why. The 0.8.0
record is expected to declare the polars 1 → 2 byte move with it. The records ship inside the package,
so a 0.7 install never holds the 0.8.0 one; the break reaches a consumer that **serializes** a record
(JSON, a cache, an API response) and validates it again with a 0.7 `just-dna-format`, which refuses
`kind: toolchain`. That is the same shape as § 1 and has the same remedy: validate with 0.8. The
member is legal on `axis: parquet_bytes` only; the model refuses it on any other axis.

`RecompileAnswer` gains `toolchain_moves` beside `corrections` and `additions`, and the three together
cover `declared`. A registry that spends a PATCH only on `corrections` needs no change: a toolchain
move is not one. `output_differs` still reads `True` for it, because the bytes do differ.

## 1.12 Which alleles `star_allele_undefined` reports (no new code)

| Surface | Item | What changed |
| --- | --- | --- |
| `star_allele_undefined` (validate and compile) | RM351 | Matched on `(gene, allele)`, not the bare name: a gene that uses an allele another gene defines (CYP2C9 `*2` beside CYP2C19 `*2`) is now reported, and an HLA gene that `haplotypes.csv` defines nothing for is no longer reported (its alleles are typed). A `haplotypes.csv` row with no `gene` still defines its name for every gene. The text keeps every phrase and appends `By gene: <gene> <alleles>; …`, then, when an HLA gene was skipped, `Not checked for <genes>: …`. `diplotype_definitions_identical` and `diplotype_phase_ambiguous` read each gene's own definitions, so one gene's `*2` no longer hides a finding about another's. |

## 1.13 Every verification record names its witness (RM292) — an old-reader break

`VerificationRecord` (`verification.json`, and `manifest.verification.checks[]`) gains four optional
fields, all `null` on a record written before 0.8:

| Field | What it holds |
| --- | --- |
| `checked_source` | Where the values the check read came from: `authored` (`vocab.AUTHORED_SOURCE`) for cells no run established as a copy of a named source, or that source when a drafter's digest establishes it; `recorded_source` / `reporting_source` / `civic` for the checks whose subject is a source's own earlier answer. `null` when nothing could settle it (the licence table names the witness and no digest says which cells it supplied, or the table is unreadable). |
| `witness_source` | The source(s) the values were compared against, `+`-joined in sorted order (`cpic+pharmvar`). Not `source`, which stays a single licence-table join key. |
| `independence` | `VALID_VERIFICATION_INDEPENDENCE` (closed): `self_consistent` when the checked side is the witness, `independent` when it is not among the witnesses, `null` when either side is unstated or the checked side is one of several witnesses. Derived on the model; a stated value its two sources contradict is refused. |
| `undecided` | How many rows a tolerance abstained on, outside `subjects`. `rsid_coordinate_agreement` has one (indel pairs a re-anchoring may explain, RM31), and so has `placement_agreement` (respellings nothing could settle, RM267, § 1.15); `null` for every other check. May ride a skip. |

**This breaks a 0.7 reader, unconditionally.** `VerificationRecord` forbids unknown keys, so a reader
pinned to 0.7 refuses every 0.8-written `verification.json`, and every manifest whose `verification`
block a 0.8 enricher wrote — unlike § 1's codes, which appear only when a module triggers them. It is
0.7's `producer` break again ([INTEGRATION_0_7 § 1](INTEGRATION_0_7.md)), with the same remedy:
upgrade `just-dna-format` to 0.8 before reading 0.8-attested modules. A 0.8 reader parses every older
record and leaves the four fields `null`.

**`independence` is validated on read**, like `check` and `skipped`: a member a later release adds
would be refused by a 0.8 reader, so the vocabulary is fixed for the major. The fact hash
(`verification.signature`) takes `checked_source`, `witness_source` and `undecided`; `null` is dropped
from it, so no signature or proof-of-work published before 0.8 moved.

**What to do with it.** A check reading `self_consistent` compared a value with the source it was
copied from (or, for the currency checks, a source's earlier answer with its answer now). Its
**agreement** is not evidence for the value, and a consumer weighting a module by its checks should not
count it as such; its **findings** still are findings — the source moved since the value was taken —
so do not drop the record. `null` is unknown, never independent.

## 1.14 A new cache lane, `clinvar_gkm` (RM305, no break)

| Surface | What changed | What to do |
| --- | --- | --- |
| `caches.CACHE_LANES` | Gains `clinvar_gkm`: ClinVar-GKM's GRCh38 indels, a placement witness (`$JUST_DNA_CLINVAR_GKM_CACHE`, `clinvar-gkm build`, publish repo `just-dna-seq/clinvar_gkm`, not created yet). | A consumer that renders or provisions the registry picks it up by walking it. One that hand-lists lanes adds it. |
| `currency.PROBE_SOURCES` | Gains `clinvar_gkm`, so `--verify-datasets` can answer for a `sources.csv` row naming it. | Nothing; a row with that source was `unsupported` before. |
| `licensing.TERMS_BY_SOURCE` | Gains `clinvar_gkm` (CC0-1.0 over ClinGen's transformation). | Nothing, until a check writes that `SourceRow`. |

## 1.15 Which study rows `study_variant_orphan` reports (RM28, no new code)

| Surface | What changed | What to do |
| --- | --- | --- |
| `study_variant_orphan` (validate and compile) | A study's variant is no longer an orphan when it is a defining variant in `haplotypes.csv`, a `pharm_variants.csv` row's (whether or not a `meta.csv` member reaches it), or the variant of a row a `meta.csv` member reached; before, only a `variants.csv` row counted. Its text keeps `Studies reference variants not in variants.csv: [keys]` and appends ` — nor among haplotypes.csv's defining variants, pharm_variants.csv's rows or the rows a meta.csv member reaches.` | Nothing, unless you match the whole sentence rather than its prefix. |
| `study_variant_orphan`, `duplicate_study_citation` on a module with no `variants.csv` | Both used to run only beside a `variants.csv`, so a diplotype-only or PGx-only module's `studies.csv` was never checked. They run whenever `studies.csv` is present (the lead, 2026-11-04). On such a module either warning can now fire where 0.7 said nothing; on every other module the orphan warning fires less often, never more. None of the 16 reference examples gains one. | Nothing, unless a module of yours with no `variants.csv` cites a variant in no table: carry it, or drop the study's variant columns if the row grounds the module rather than a locus (RM47). |

## 1.16 Two genes' allele on one variant are two `haplotypes.csv` rows (RM356, no new warning code)

| Surface | What changed | What to do |
| --- | --- | --- |
| `haplotypes.csv` duplicate refusal (validate and compile) | Two rows sharing `(haplotype_name, variant_key, allele)` are no longer refused when both state `gene` and the genes differ (case and surrounding space ignored). A row with no `gene`, or the same gene twice, is refused exactly as before, with the same `haplotypes.csv: duplicate row for key (…)` text. | Nothing, unless you keep your own duplicate rule for this table: then split it the same way, only on two stated genes that differ. |
| `haplotypes.parquet` | `(haplotype_name, variant_key, allele)` is no longer unique in a compiled artifact: two rows may share it and differ by `gene`. A module with no such pair compiles to the same bytes as before. | A reader that indexes this table by name, variant and allele adds `gene` to its key, or it merges two genes' definitions of one name. |
| `draft.append_rows`, `hints.inspect_rows` | Ask the compiler's predicate (`compiler.tables.same_row`), so a drafted second gene's row is `added` and the lint stops flagging it. | Nothing. |
| `hints.TableKey` / `describe_table(...)["key"]` | Gains `distinct_when_stated` (`("gene",)` for `haplotypes.csv`, `()` for every other kind): columns outside `columns` that split two rows only when both state them and the values differ. | A tool that tells an author when two rows collide reads it beside `columns`. One reading only `columns` over-reports for this table, as before. |

## 1.17 Under `strict`, an escalated finding is in `errors` only (RM359, no new code)

| Surface | What changed | What to do |
| --- | --- | --- |
| `CompilationResult` of `compile_module(strict=True)` | A mode-ladder finding (the `@ladder` codes, plus `symbolic_allele_unusable`'s droppable half) used to arrive in `errors` **and** in `warnings`; a resolution ladder carried its warning beside its longer refusal. It is now in `errors` only. The pre-flight runs in the compile's mode, so a strict compile refuses with `validate --strict`'s accumulated errors, where it used to stop at the first ladder that refused. | A consumer that matched an escalated finding in a strict run's `warnings` reads `errors`. One that counted findings across both lists stops counting the escalated ones twice. `best_effort` is unchanged. |

## 1.18 A placement is compared with a second authority, and two new `resolution.csv` columns (RM267) — an old-reader break

`enrich` now asks the ClinVar snapshot and ClinVar-GKM where they place every rsID it placed, and
**withholds** a placement two authorities give as two different events: that locus gets no row, an rsID
left with none is unresolved (`strict` refuses through the existing unresolved gate, naming the
disagreement), and a warning names both placements. An `overrides.csv` answer on the subject clears the
unresolved state. Each witness a written row names gets a `resolution`-layer `SourceRow` (`clinvar`,
`clinvar_gkm`), and the compiler counts it as used. S117's
`rs8176719` (ABO O1) is the motivating case: the Ensembl snapshot's `9:133257520 G>GC` against the
`9:133257521 T>TC` dbSNP and Ensembl REST give, two haplotypes. Probed 2026-11-04 on real data: neither loaded witness holds `rs8176719` (ClinVar's 2026-06-27 VCF has no record at `9:133257510–529` and no `RS=8176719`; ClinVar-GKM lacks it, RM305), so against today's witnesses S117's own case is counted in the one-witness class and named in `detail`, not withheld. The spelling `9:133257521 T>TC` is dbSNP's and Ensembl REST's; the tests supply it as a ClinVar row to exercise the withhold. A respelling (`rs72613567`, `rs77944059`) mints one VRS id and is
written, left-aligned since RM270 (§ 1.19).

| Surface | What changed |
| --- | --- |
| `resolution.csv` `placement_witness` | New optional provenance column: which second authority was asked (`clinvar`, `clinvar_gkm`, or both `+`-joined). Empty means nobody independent was asked. Outside `resolution_signature`. |
| `resolution.csv` `placement_verdict` | New optional provenance column, `VALID_PLACEMENT_VERDICTS` (closed): `same_event`, `undecided`, `unplaced`. Outside `resolution_signature`. |
| `VALID_VERIFICATION_CHECKS` | Gains `placement_agreement` (`checked_source` `reporting_source`, witness `clinvar+clinvar_gkm`, with an `undecided` count; the one-witness count is in `detail`). |
| `enrich(clinvar_gkm_cache=)`, `enrich --clinvar-gkm-cache` | Where the ClinVar-GKM witness is read from; `$JUST_DNA_CLINVAR_GKM_CACHE` otherwise. Read locally, never downloaded by `enrich`. |
| `EnrichmentResult.placement`, `placement.PlacementCheck`, `ClinVarGkmWitness.by_rsids` | What the comparison did, and the batch lookup it uses. |

**This breaks a 0.7 reader of a 0.8-enriched `resolution.csv`.** `ResolutionRow` forbids unknown
columns, so a 0.7 compiler refuses the table once a 0.8 enricher has written it, and a 0.7 reader of a
0.8 attestation refuses the new check name. Same remedy as § 1.13: upgrade before compiling. No parquet
carries either column, and no fact signature moves.

**What to do with it.** Nothing reaches a `resolution.csv` written before 0.8 on an ordinary run
(merge-not-clobber): re-run `enrich --rederive`, or delete the file and re-run, to have its placements
compared. A subject that comes back unresolved with a *placement disagreement* warning has a source
contradicting another; check the spelling against the reference and record the one you stand behind in
`overrides.csv`.

## 1.19 An indel's spelling-independent id on every variant parquet, and a filled coordinate written left-aligned (RM270) — an old-reader break

The `vrs_id` the enricher records in `resolution.csv` now reaches the artifact. Both legal spellings of
one indel carry one id (`rs72613567` at `4:87310240 T>TA` and at `4:87310241 A>AA`), and two events carry
two (`rs8176719`'s two placements), so a consumer that can mint VRS from its own VCF has a key that does
not depend on how either side spelled the event. Each row's ids are copied from its own
`resolution.csv` row (the one filed under its authored key, at its coordinate) by allele, never minted by
the compiler and never borrowed from another subject's row; an allele with no recorded id is a null
member, and an allele its key records with two ids is withheld.

| Surface | What changed |
| --- | --- |
| `weights.parquet` `vrs_id`, `vrs_spec` | `List(Utf8)` parallel to `alts` (null where no id is recorded; the cell is null when none is) and the VRS version the ids were minted under (`Utf8`, null unless every id on the row states the same one). Appended after every other column, so **every module carrying `variants.csv` gets a new `artifact.digest` on a 0.8 recompile**; `content_signature` does not move. |
| `pharm_variants.parquet`, `haplotypes.parquet`, `heteroplasmy.parquet` `vrs_id`, `vrs_spec` | `Utf8`, the comma-joined cell `resolution.csv` uses (parallel to the table's own `alts`, holes kept). Appended last; same digest note. |
| `studies.parquet` `proxy_loci` | The struct gains `vrs_id` and `vrs_spec`, the proxy row's cells. |
| `reverse` | Writes `vrs_id` and `vrs_spec` back into `resolution.csv`, so `compile → reverse → compile` keeps every id and `vrs_alleles_identified` (before 0.8 the second lap counted 0). |

Not on `annotations.parquet` (no allele to be parallel to; join it to `weights.parquet` on
`variant_key`) and not on `frequencies.parquet`, whose `vrs_id` is gnomAD's.

**The enricher writes a coordinate it fills left-aligned, and judges an authored one.** A coordinate
`enrich` fills from an rsID is now written in its leftmost parsimonious spelling, ALT by ALT, the spelling
a caller's `bcftools norm -m -any` writes, so an exact `(chrom, pos, ref, alt)` join meets it. A
multi-allelic locus whose ALTs land on two references becomes two loci (SHOX's `X:634690
AGAG>AG,AGAGAG` is now `X:634689 CAG>C` and `X:634689 C>CAG`, and the compiler expands the rsID onto
both). An authored coordinate is never rewritten: a non-left-aligned one draws a warning naming its
leftmost spelling, and its `vrs_id` is what joins it.

| Surface | What changed |
| --- | --- |
| `resolution.csv` `left_aligned` | New optional verdict column, tri-state: `true` checked left-aligned, `false` checked and not, empty unknown. Outside `resolution_signature`; no parquet carries it. |
| `resolution.csv` filled rows | Written left-aligned on a fresh fill or under `--rederive`; a recorded row is untouched otherwise. The respelling moves `resolution_signature` and `artifact.digest` on the next compile, never `content_signature`. |
| `EnrichmentResult.spelling`, `sequences.SpellingCheck`, `left_normalize`, `normalize_locus` (returns `NormalizedLocus`), `spelling_verdict` | What the pass did (the fills respelled, the authored coordinates judged and the ones not left-aligned, with the counts), and the normalizer. |
| `SubjectDrift.respelled` | `--rederive`'s drift canary names a subject whose facts moved while every allele's `vrs_id` stayed the same (the left-aligned fill) apart from one the source changed; it is logged at INFO, not in the drift warning. A new field with a default, so an existing constructor call is unchanged. |
| `reference_examples/shox_par1` | `resolution.csv` re-derived (`enrich --rederive --no-clinvar`): `rs1569493663` is two left-aligned loci, and every row carries RM267's and RM270's columns. `test_consumer_join` now passes with no expected miss. |

**This breaks a 0.7 reader of a 0.8-enriched `resolution.csv`**, for § 1.18's reason: `ResolutionRow`
forbids unknown columns. Same remedy.

## 1.20 `reverse` gives back what the compile carried, and the positional parquets carry `resolution_loci` (RM364, no break)

Which manifest fields `compile → reverse → compile` gives back is now a registry,
`just_dna_compiler.compiler.reverse.REVERSE_MANIFEST_RECONSTRUCTED`, with every other field in
`REVERSE_MANIFEST_EXCLUDED` and a reason each; `reconstructed_projection(manifest)` is the comparison the
round-trip gates make, lap against lap.

| Surface | What changed |
| --- | --- |
| `reverse` | Copies `provenance.json` and every shipped log back into the reversed spec, byte for byte after a hash check against the manifest, as it already did the README and logo (`reverse.shipped_files`). A file that disagrees with its record, or a recorded name that leaves the module directory, is not copied and is logged. Before, `manifest.provenance` and `manifest.logs` were empty on the second lap. |
| `weights.parquet`, `pharm_variants.parquet`, `haplotypes.parquet`, `heteroplasmy.parquet` `resolution_loci` (compiler-filled) | `List(Struct{rsid, chrom, start, ref, alts, locus_index, vrs_id, vrs_spec})`, the `proxy_loci` shape: the loci the post-overlay `resolution.csv` files under the row's authored key (on `weights.parquet` the key the author wrote, not an expanded row's locus key), on the module's build. **Null wherever the row's own cells already rebuild those loci exactly** (every cleanly resolved row), and null when the table files none or under `--no-resolve`; so it is filled exactly on a row the fill left alone, and then repeated on every genotype row and expanded locus of that authored row. Not authored and never written to a CSV; `reverse` rebuilds `resolution.csv` from it, so a row whose authored coordinate the table contradicts no longer comes back with that coordinate written as a resolution fact. It is the lookup's answer kept for the round trip; a consumer joining a VCF reads the row's own `chrom`/`start`/`ref`/`alts`. Appended last, so **every module carrying `variants.csv` or a positional table gets a new `artifact.digest` on a 0.8 recompile** (a new column, null on a clean module); `content_signature` does not move. |
| `reverse`, a module that read no table | Writes no `resolution.csv` when the manifest records no `resolution_signature`, its `derived` list names none, and no parquet row carries a filled identity cell. It used to rebuild one from the authored coordinates, and the second lap's manifest then published a `resolution_signature`, VRS coverage and expansion counts the first did not. A spec that carried a table with no rows gets a header-only one back. |
| `reference_examples/cpic_gene_pairs` | The NUDT15 `*1` row `rs1457579126` (removed while the example was built, for this defect) is back in `haplotypes.csv`, with its `resolution.csv` row and a ClinVar `licensing.csv` row (the placement's witness). The module was re-enriched and re-closed. |

## 2. What to change

1. If you parse `manifest.json` with `just-dna-format`, move your pin to 0.8 when you start reading
   manifests compiled by 0.8 (§ 1).
2. If you key on `warnings_summary`, the new codes are listed in § 1 with their meaning, and
   `quality_floor_inverted` will stop appearing (§ 1.1).
3. **Publishers (RM342).** `upload_module` raises `ToolchainDiffersError`, a subclass of
   `PublishCollisionError`, when the versioned path holds a different digest and the two manifests'
   recorded toolchains differ; its `reason` is `"toolchain_differs"` (the plain collision's is `None`)
   and it carries `published_toolchain` / `local_toolchain` and `content_unchanged` (tri-state: `False`
   when the `content_signature` moved too, so the toolchain does not account for all of it). It still
   refuses, so a handler of the
   collision keeps working unchanged; catch the subclass first if you want to say why the digest
   moved. If either manifest predates 0.8 the plain collision is raised, as before.
4. **Release-sweep readers (RM342).** `ModuleDelta` gains `toolchain_differs` (tri-state) and
   `bytes_reason` (`"toolchain_differs"` or `null`), `SweepMeasurement` gains `moved_under_other_toolchain` (the
   modules whose bytes moved under a different recorded toolchain), and `measurement_json` carries all
   three. `compilation.toolchain` joins `EXCLUDED_MANIFEST_FIELDS`, so it never appears in a record's
   `manifest_fields`.
5. If you validate authored modules (a registry, a server-side `validate_spec`), upgrade before you
   accept 0.8 modules: `pmid=NONE` and the new `doi` columns are refused by 0.7 (§ 1.5). If you parse
   `pmid` yourself, skip `NONE` and take the citation from `doi` there.
6. If you read a snapshot's `release.json`, through `locations.read_release` or by hand, read § 1.9:
   the reader returns a model, and three keys are spelled differently in a snapshot built by 0.8.
7. If you read a module's findings, read `meta.parquet` too: a row with `replaces` true whose members all
   match the sample replaces the findings of the rows in its `matches` (§ 1.2.1), within the row's own
   `sex` and `drug` scope.
8. **Release-record readers (RM352).** If you switch on `DeclaredChange.kind`, add the third arm,
   `toolchain` (§ 1.11), or read `RecompileAnswer.corrections` / `additions` / `toolchain_moves` rather
   than the raw kind. `SweepMeasurement` gains `before_toolchain` / `after_toolchain` (the one toolchain
   each side recorded, `null` when unrecorded or mixed) and `before_digests` / `after_digests` (each
   module's `artifact.digest`), `measurement_json` carries all four, and
   `sweep --toolchain-before DIR --json` nests the fixed-compiler sweep under `toolchain_sweep`.

9. If you keep a hand-written list of artifact parquets or authored CSVs (a publisher's allowlist, a
   spec-directory mirror), add `model_organisms.parquet` and `model_organisms.csv`, or derive the list
   from `ARTIFACT_PARQUETS` and `table_bindings()` (§ 1.2.2).

10. If you read `verification.json` or `manifest.verification`, upgrade to 0.8 first (§ 1.13), and do not
   count a `self_consistent` check's agreement as evidence for the value it checked (its findings stand).
