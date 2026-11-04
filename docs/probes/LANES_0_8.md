# The three 0.8 outside-service lanes, probed by hand before any code depends on them

**Subjects:** the Open Targets Platform release 26.09 (RM333's lane, feeding RM239 and RM236: PROPOSAL_0_8_PT2
§5 D2 and §4 question 2), Ensembl REST pairwise LD (RM331, D3 and §4 question 4), and ClinGen's ClinVar-GKM
`allele.parquet` (RM305, C3).
**Basis:** HTTP calls made from this machine on 2026-11-04 between 02:39 and 03:10 UTC; every command is
quoted below. Downloads went to a git-ignored `data/probes_0_8/` directory, were read with polars 1.44.2 under
`uv run python -I`, and are not committed. Files over 1 GB were never written to disk: they were read by
projection over HTTP range requests (polars `scan_parquet` on the URL).
**Date of analysis:** 2026-11-04.

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`. It proposes no
design. Each claim is tagged **[M]** (measured here, from the bytes or the response) or **[I]** (inferred from
measurements, with the step that could be wrong named). Where a measurement contradicts PT2, a ROADMAP entry
or [GKS_SURVEY.md](GKS_SURVEY.md), the contradiction is stated rather than smoothed. Section 0 lists them.

---

## 0. What contradicts the plan

1. **Open Targets publishes no 99% credible-set membership.** Every one of the 40,967,780 GWAS credible-set
   member rows in 26.09 has `is95CredibleSet = true` and `is99CredibleSet = true` [M, whole dataset]. The
   `locus` array is cut at the 95% set (the croissant calls the dataset "95% credible sets"), so the 95-vs-99
   split RM239 was designed against (GWAS Catalog's `No`/`Yes` for GCST90038614) cannot come from this lane.
   The posterior (`posteriorProbability`, never null) can. What the second RM239 column carries goes back to
   the pm.
2. **`variantId` is underscore-separated, and the croissant says hyphens.** The croissant documents
   `{chromosome}-{position}-{referenceAllele}-{alternateAllele}`; all 7,886,762 ids in `variant` use `_`
   (`19_43828188_GT_G`), none contains `-` [M]. And 2,114 ids are `OTVAR_<chr>_<pos>_<md5>`, a hash standing
   in for alleles up to 9,983 bases long [M]. A builder takes alleles from the `referenceAllele` and
   `alternateAllele` columns, never by splitting the id.
3. **"Keyed to rsIDs" is a join, and many-to-many.** No Open Targets table except `variant` carries an rsID.
   `variant.rsIds` is a list: 491,617 variants have none and 9,803 have more than one [M]. L2G rows carry no
   variant and no study at all: their grain is `(studyLocusId, geneId)` [M].
4. **Coloc is 16.5 GB, 283,303,467 rows, and names no gene, tissue or study type on the left** [M]. The gene
   and tissue behind an eQTL colocalisation sit three joins away (`rightStudyLocusId → credible_set.studyId →
   study.geneId / biosampleId`). The GWAS-left × molQTL-right rows alone would weigh about 3.7 GB [I].
5. **ClinVar-GKM is on Cloudflare R2, not Google Cloud Storage, and its Parquet cannot be pinned.**
   `https://data.clinvar-gkm.org/v1/1.1/parquet/` holds one Parquet set, overwritten every release; there are
   no dated or archived Parquet sets [M: its own docs and manifest]. PT2 C3 and RM305 say "Google Cloud
   Storage" and "a pinned release"; GKS_SURVEY already said R2. A pin can only record `(source_release,
   sha256)` and detect drift.
6. **ClinVar-GKM moved under VRS 2.1.1 at its 1.0.0** (changelog date 2026-10-12, GitHub release
   2026-10-10), not the 2.0.x RM305 records [M: its changelog]. The data carries no per-row VRS version. RM270's two insertion ids are byte-identical to the
   ones the survey found under 1.0-rc3 [M], so on these two rows 2.0 and 2.1 agree. How many of the other
   289,929 `ReferenceLengthExpression` ids differ from what our vrs-python 2.3.x would mint is not measured.
7. **Only 71% of the indel slice carries an rsID** (219,871 of 309,479 rows, §3.5), and S117's `rs8176719` is not
   in ClinVar-GKM at all [M]. A witness keyed only on rsID loses the rest; the VRS id and the `gnomad` VCF
   spelling are keys every row has.
8. **The five 1000 Genomes superpopulations are absent from Ensembl's own LD population listing, yet the
   pairwise endpoint answers for them** [M]. And an empty answer (`[]`, HTTP 200) is not r² = 0: it comes back
   for a pair on two chromosomes, and for the APOE pair in `AFR`, whose admixed `ASW` subpopulation answers
   r² 0.0635 (§2.4).
9. **Open Targets' `study.ldPopulationStructure` codes are gnomAD-style** (`nfe`, `fin`, `eas`, `afr`, `amr`),
   not PT2 decision 12's 1000G codes, and no GWAS study names `sas` [M, whole table]. Not a D3 input as PT2
   writes it (D3 reads our own `ancestry`), but any mapping between the two is lossy.

---

## 1. Open Targets Platform 26.09

### 1.1 Where it is, and the release and licence markers

```bash
curl -sS -L https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/            # release directories
curl -sS -L https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.09/      # one release
curl -sS -o croissant.json https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/26.09/croissant.json
```

- The platform directory lists `25.06`, `25.09`, `25.12`, `26.03`, `26.06`, `26.09` and a `latest/` pointer
  (all dated 2026-09-24 10:54 for 26.09) [M]. The release identity is the directory name.
- `26.09/` holds `croissant.json` (621 KB), `manifest.json` (19,314,465 bytes, Last-Modified 2026-09-24
  08:44 GMT), `metrics.parquet`, `release_data_integrity` (+ `.sha1`), and the folders `output/`, `input/`,
  `intermediate/`, `excluded/`, `etc/`, `disk_images/`, `view/` [M].
- `manifest.json` is **a pipeline run log, not a release descriptor**: it opens `{"result": "success",
  "started_at": "2026-09-07T15:35:09.880877Z", "modified_at": "2026-09-24T09:44:06.783599", "steps":
  {"pis_l2g": …` with per-task log lines [M: first 2.5 KB, read with `curl -r 0-2500`]. It names no licence.
- The croissant (MLCommons croissant 1.0) carries the only in-release markers [M]:

  | key | value |
  |---|---|
  | `name` | `Open Targets Platform Datasets` |
  | `version` | `26.09` |
  | `datePublished` | `2026-09-18` |
  | `license` | `https://creativecommons.org/publicdomain/zero/1.0/` (the only `license` key anywhere in the file) |
  | `citeAs` | `@article{PMID:39657122, author = {Buniello, Annalisa and …` |

  The terms-of-use text RM333's probe recorded (the third-party-rights disclaimer `notice` will carry) is on
  the website, not in the release; it was not re-read here.

### 1.2 The five datasets: format, count, size

Listing each `output/<dataset>/` directory and sending a HEAD to every file
(`httpx.head(url).headers["content-length"]`, 16 threads); row counts by `pl.scan_parquet(url).select(pl.len())`
per file, which reads only footers [M]:

| dataset | files | total bytes | rows | smallest / largest part |
|---|---|---|---|---|
| `l2g_prediction` | 200 `part-*.parquet` (no codec in the name) | 509,628,512 (0.51 GB) | 3,293,342 | 0.37 MB / 8.5 MB |
| `credible_set` | 200 `part-*.zstd.parquet` + `_SUCCESS` | 2,990,567,440 (2.99 GB) | 4,761,925 | 4.3 MB / 194 MB |
| `colocalisation` | 200 `part-*.zstd.parquet` + `_SUCCESS` | 16,519,695,769 (16.5 GB) | 283,303,467 | 82.4 MB / 82.8 MB |
| `variant` | 25 `part-*.zstd.parquet` + `_SUCCESS` | 1,967,290,736 (1.97 GB) | 7,886,762 | 62 MB / 107 MB |
| `study` | 1 `part-*.zstd.parquet` + `_SUCCESS` | 97,748,879 (0.10 GB) | 3,004,247 | — |

All five are Spark output (`org.apache.spark.version` in the footer's key-value metadata of the part each
was read from) [M]. One part of each was
downloaded whole for row-level reads: `l2g` part-00104, `credible_set` part-00101, `colocalisation`
part-00003, `variant` part-00017, `study` part-00000 (the whole table).

### 1.3 `l2g_prediction`

Schema [M]: `studyLocusId: String`, `geneId: String`, `score: Float64`,
`features: List(Struct{name: String, value: Float32, shapValue: Float32})`, `shapBaseValue: Float32`.

- **Grain:** one row per `(studyLocusId, geneId)`. In part-00104, 1,912 study loci carry 1 to 11 gene rows
  (median 1, mean 1.8) [M]. 24% of rows score ≥ 0.5 [M, one part].
- **Gene:** Ensembl gene id (`ENSG00000105609`), no symbol [M].
- **Variant and study:** absent. `studyLocusId` is a 32-hex hash (`1011cca96efba523e1b64960a9faaab8`);
  its lead variant and study come from `credible_set` [M].
- Sample: `020161096bcedf3cca6a6effa6043c3b | ENSG00000104974 | 0.082117` [M].
- `features[].name` includes `credibleSetConfidence`, `distanceFootprintMean`, `distanceSentinelTss`, … [M];
  the features and their SHAP values are the model's explanation, not an input PT2 names.

### 1.4 `credible_set`

Top-level columns [M]: `studyLocusId, studyId, variantId, chromosome, position, region, beta, zScore,
pValueMantissa, pValueExponent, effectAlleleFrequencyFromSource, standardError, subStudyDescription,
qualityControls, finemappingMethod, credibleSetIndex, credibleSetlog10BF, purityMeanR2, purityMinR2,
locusStart, locusEnd, sampleSize, ldSet, locus, confidence, studyType, isTransQtl` (27).

- `locus: List(Struct{is95CredibleSet, is99CredibleSet, logBF, posteriorProbability, variantId,
  pValueMantissa, pValueExponent, beta, standardError, r2Overall})` is the per-variant membership;
  `ldSet: List(Struct{tagVariantId, r2Overall})` is the lead's LD tags [M].
- **Grain:** one row per credible set (`studyLocusId`); `variantId` is the lead "by posterior probability"
  (croissant) [M].
- **Study:** `studyId`. Over the whole dataset, by `studyType` [M]:

  | studyType | credible sets |
  |---|---|
  | eqtl | 1,718,748 |
  | gwas | 1,519,507 |
  | sqtl | 844,764 |
  | tuqtl | 521,558 |
  | sceqtl | 123,630 |
  | pqtl | 33,718 |

  The 1,519,507 GWAS sets come from 58,931 studies, with 497,530 distinct lead variants. Their `studyId`s are
  `GCST…` (1,498,743 sets) or `FINNGEN_R12_…` (20,764) [M]. The `study` table lists 165,517 GWAS studies, so
  about 106,600 GWAS studies have no credible set in this release [I: subtraction; assumes every set's
  `studyId` is in `study`]. That is RM239's withhold case, at scale.
- **Per-variant posterior:** yes. The 40,967,780 GWAS member rows (3,007,117 distinct variants) all carry a
  `posteriorProbability`, none null; median 0.0066, max 1.0. One variant sits in up to 4,613 GWAS credible
  sets [M].
- **95% / 99% membership:** `is95CredibleSet` and `is99CredibleSet` are both `true` on all 40,967,780 rows
  [M]. Only the 95% set is published (finding 1 in §0).
- **Fine-mapping method** (part-00101, all study types): `SuSiE-inf` 10,232, `PICS` 6,785, `SuSie` 4,996;
  `confidence` spells out four classes, such as "SuSiE fine-mapped credible set with out-of-sample LD" and
  "PICS fine-mapped credible set based on reported top hit" [M, one part]. Three methods and four
  `confidence` classes stand behind one `posteriorProbability` column, so RM239's posterior needs the method
  and confidence beside the number, or its field description claims more than the row says.
- Sample member rows [M]:

  | studyLocusId | variantId | posteriorProbability | is95 | is99 |
  |---|---|---|---|---|
  | ed1fb72127743d920e5b6991b314bb1c | 19_43828188_GT_G | 0.406155 | true | true |
  | ed1fb72127743d920e5b6991b314bb1c | 19_43827818_C_G | 0.363211 | true | true |
  | ed1fb72127743d920e5b6991b314bb1c | 19_43830901_TAA_T | 0.00731 | true | true |

### 1.5 `colocalisation`

Schema [M]: `leftStudyLocusId, rightStudyLocusId, rightStudyType, chromosome, colocalisationMethod,
numberColocalisingVariants, h3, h4, clpp, betaRatioSignAverage` (10 columns; no `leftStudyType`, no h0–h2).

- **Grain:** one row per `(leftStudyLocusId, rightStudyLocusId)` pair. The croissant calls the dataset
  "GWAS-GWAS and GWAS-molQTL credible set colocalisation results using colocPIP and eCAVIAR methods" [M].
- **Statistics:** every row read carries both `h4` and `clpp`, none null, under the single method value
  `COLOC_PIP_ECAVIAR` [M: parts 00000, 00060, 00120, 00199 and 00003].
- **Pairing:** `rightStudyType` in part-00000 is `gwas` 1,016,991, `eqtl` 183,940, `sqtl` 95,985, `tuqtl`
  56,883, `pqtl` 36,909, `sceqtl` 25,011; the five other parts read have the same proportions within 0.1% [M].
  So GWAS loci are paired with eQTL loci, and about 72% of rows are GWAS-GWAS [M, five parts].
- **What a coloc row does not name:** the gene, the tissue, the right-hand study and the left-hand study type.
  All come through `credible_set.studyId` and then `study` (`geneId`, `biosampleId`, `projectId`, e.g.
  `GTEx-v10`) [M: schemas]. This is the per-tissue coloc PT2 §4 question 2 put in place of RM238's GTEx table.
- Sample [M]: `59fac2aee157b91b29d59c4f660ea9df | 00aba7c3fe6d9512d7618e292d8049a8 | gwas | 1 |
  COLOC_PIP_ECAVIAR | 139 | h3 0.172332 | h4 0.827668 | clpp 0.004317 | null`.
- In part-00003, 398,752 of 1,413,254 rows have a molQTL right side; 254,155 of those have h4 ≥ 0.8 and
  174,502 have clpp ≥ 0.01 [M, one part]. The two statistics disagree often enough that a lane must keep
  both, never pick one.

### 1.6 `variant`

Top-level columns [M]: `variantId, chromosome, position, referenceAllele, alternateAllele, variantEffect,
mostSevereConsequenceId, transcriptConsequences, rsIds, hgvsId, alleleFrequencies, dbXrefs,
variantDescription` (13).

- **Grain:** one row per `variantId` (chrom, 1-based position, ref, alt; GRCh38). Indels are VCF-anchored
  (`4_87310240_T_TA`) [M]. 982,985 of the 7,886,762 variants are not single-base substitutions [M].
- **Coverage:** "variants are included if any phenotypic information is available … GWAS or molQTL credible
  sets, ClinVar, UniProt or ClinPGx" (croissant) [M]. It is not a catalogue of all variants. The probe set was
  all present [M]:

  | rsID | variantId | mostSevereConsequenceId |
  |---|---|---|
  | rs646776 | 1_109275908_C_T | SO_0001631 |
  | rs2075650 | 19_44892362_A_G | SO_0001627 |
  | rs429358 | 19_44908684_T_C | SO_0001583 |
  | rs7412 | 19_44908822_C_T | SO_0001583 |
  | rs72613567 | 4_87310240_T_TA | SO_0001630 |
  | rs3798220 | 6_160540105_T_C | SO_0001583 |
  | rs10455872 | 6_160589086_A_G | SO_0001627 |

- **rsIDs:** `rsIds: List(String)`, with `rs` prefix. 7,395,145 variants have at least one, 491,617 none,
  9,803 more than one [M].
- **Per-transcript consequences: yes.** `transcriptConsequences: List(Struct{variantFunctionalConsequenceIds:
  List(String) (SO ids), aminoAcidChange, uniprotAccessions, isEnsemblCanonical, codons,
  distanceFromFootprint, distanceFromTss, appris, maneSelect (RefSeq NM_ id or null), targetId (ENSG), impact
  (HIGH|MODERATE|LOW|MODIFIER), lofteePrediction, siftPrediction, polyphenPrediction, consequenceScore,
  transcriptIndex, approvedSymbol, biotype, transcriptId (ENST)})` [M].
  - 280,906,222 transcript rows over the dataset, **every one with `isEnsemblCanonical = true`**; 88,175,399
    carry a `maneSelect` [M]. So the list is one canonical transcript per nearby gene, not every transcript
    of every gene [I: from the flag being uniformly true]. RM236's `(variant_key, transcript)` key still
    holds; the transcript set is Open Targets' choice, and the field description would have to say so.
  - About 36 transcript rows per variant on average, mostly `MODIFIER`: in part-00017, 7,022,438 MODIFIER,
    29,536 MODERATE, 15,149 LOW, 5,779 HIGH [M, one part].
  - Sample: `4_53007534_T_C | ENST00000248706 | [SO_0001632] | MODIFIER | NM_023940.3 | true | RASL11B |
    ENSG00000128045` [M].
- Also present: `variantEffect` methods `VEP`, `GERP`, `SIFT`, `AlphaMissense`, `FoldX`, `LOFTEE`;
  `alleleFrequencies` with gnomAD `*_adj` populations; `dbXrefs` sources `ensembl_variation`, `gnomad`,
  `clinvar`, `protvar`, `omim` [M, one part]. Whether AlphaMissense and FoldX here carry their own terms
  (`@a-hosts-terms-are-not-its-contents-terms`) is not checked.

### 1.7 `study`

30 columns [M], among them `studyId, geneId, projectId, studyType, traitFromSource,
traitFromSourceMappedIds (List: EFO_/MONDO_ ids), pubmedId, nSamples, ldPopulationStructure
(List(Struct{ldPopulation, relativeSampleSize})), discoverySamples (List(Struct{sampleSize, ancestry})),
biosampleId, hasSumstats`.

- **Grain:** one row per study; molQTL studies are split per gene and biosample, which is why GTEx-v10 alone
  has 1,933,030 rows [M].
- `studyType`: eqtl 1,476,085, sqtl 767,929, tuqtl 476,698, gwas 165,517, sceqtl 114,263, pqtl 3,755 [M].
- GWAS `studyId` is a GCST accession (`projectId = GCST`, 163,181 rows) or a FinnGen id
  (`FINNGEN_R12_AUTOIMMUNE_HYPERTHYROIDISM`) [M].
- `ldPopulationStructure` over the GWAS rows: `nfe` 122,554, `eas` 34,536, `afr` 26,840, `amr` 9,814, `fin`
  2,336, null 17 [M] (finding 9 in §0).

### 1.8 How each table names things

| thing | how it is named | where |
|---|---|---|
| variant | `variantId` = `<chr>_<pos>_<ref>_<alt>`, GRCh38, VCF-anchored; or `OTVAR_<chr>_<pos>_<md5>` | every table |
| rsID | `rsIds` list, `rs`-prefixed | `variant` only |
| study | `studyId` (GCST…, FINNGEN_R12_…, molQTL ids such as `gtex_…`) | `credible_set`, `study` |
| study locus | `studyLocusId`, a 32-hex hash | `l2g_prediction`, `credible_set`, `colocalisation` |
| gene | Ensembl `ENSG…` id; symbol only as `approvedSymbol` inside `transcriptConsequences` | `l2g_prediction`, `variant`, `study` |
| trait | `traitFromSourceMappedIds` (EFO/MONDO) | `study` |

The join path for an effector-gene row keyed to an rsID is therefore
`l2g.studyLocusId → credible_set (studyId, lead variantId) → variant (rsIds)`, and `→ study` for the trait.

### 1.9 What a GRCh38 subset keyed to rsIDs would weigh [I]

Trimmed projections of the downloaded parts were written once with zstd to measure bytes per row, then
deleted; the per-row cost is multiplied by the measured whole-dataset row counts. Compression on a full,
sorted build will differ, so read these as orders of magnitude.

| piece | columns kept | rows (whole release) [M] | bytes/row [M, one part] | estimate |
|---|---|---|---|---|
| rsID map | `variantId, chromosome, position, ref, alt, rsIds` | 7,886,762 | 14.4 | ~115 MB |
| L2G | `studyLocusId, geneId, score` | 3,293,342 | 15.3 | ~50 MB |
| GWAS credible-set heads | `studyLocusId, studyId, variantId, finemappingMethod, credibleSetIndex, confidence` | 1,519,507 | 23.3 | ~35 MB |
| GWAS set members | `studyLocusId, variantId, posteriorProbability, is95, is99` | 40,967,780 | 15.4 | ~630 MB |
| transcript consequences, all | `variantId, transcriptId, consequence ids, impact, maneSelect, isEnsemblCanonical, targetId, approvedSymbol` | 280,906,222 | 0.83 | ~235 MB |
| … MANE rows only | same | 88,175,399 | 1.9 | ~165 MB |
| … non-MODIFIER only | same | ~1.3 M (0.167 per variant, one part) | 5.8 | ~8 MB |
| coloc, molQTL right side | `leftStudyLocusId, rightStudyLocusId, rightStudyType, h4, clpp, numberColocalisingVariants` | ~80 M (28.2% of 283.3 M) | 46.8 | ~3.7 GB |

Without coloc the lane is about 1 GB; with coloc's molQTL half, about 5 GB. Restricting members to variants
that carry an rsID changes little, since 94% do [M: 7,395,145 / 7,886,762]. Coloc is the piece that decides
the lane's size.

---

## 2. Ensembl REST pairwise LD

### 2.1 The calls

All with header `Content-Type: application/json`, from an httpx client that retried 500/502/503/504/429 up
to four times with a 5 s, 10 s, 15 s back-off:

```text
GET https://rest.ensembl.org/info/variation/populations/human?filter=LD
GET https://rest.ensembl.org/ld/human/pairwise/rs646776/rs4970836?population_name=1000GENOMES:phase_3:{EUR,AFR,EAS,SAS,AMR}
GET https://rest.ensembl.org/ld/human/pairwise/rs429358/rs2075650?population_name=1000GENOMES:phase_3:{EUR,AFR,EAS,SAS,AMR}
GET https://rest.ensembl.org/ld/human/pairwise/rs646776/rs4970836                         (no population)
GET https://rest.ensembl.org/ld/human/pairwise/rs429358/rs2075650                         (no population)
GET https://rest.ensembl.org/ld/human/pairwise/rs646776/rs999999999999                    (unknown rsID)
GET https://rest.ensembl.org/ld/human/pairwise/rs646776/rs4970836?population_name=gnomADg:nfe   (non-LD population)
GET https://rest.ensembl.org/ld/human/pairwise/rs646776/rs429358?population_name=1000GENOMES:phase_3:EUR (two chromosomes)
GET https://rest.ensembl.org/ld/human/pairwise/rs429358/rs2075650?population_name=1000GENOMES:phase_3:AFR;r2=0
GET https://rest.ensembl.org/ld/human/pairwise/rs1624712/rs4970836?population_name=1000GENOMES:phase_3:EUR (synonym of rs646776)
GET https://rest.ensembl.org/info/data   → {"releases": [116]}
```

### 2.2 The population listing omits the superpopulations

`?filter=LD` returns 30 records with keys `name`, `size`, `description` [M]: the 26 1000 Genomes phase 3
subpopulations (`1000GENOMES:phase_3:ACB` … `YRI`, sizes 61 to 113) and four Gambian Genome Variation
Project groups (`GGVP:GWF`, `GGVP:GWD`, `GGVP:GWW`, `GGVP:GWJ`). **`EUR`, `AFR`, `EAS`, `SAS`, `AMR` and `ALL`
are not listed**, yet `population_name=1000GENOMES:phase_3:EUR` (and the other four, and `ALL`) returns a
row [M]. A pairwise call with no population returns 29 rows, one per listed group except `GGVP:GWJ`, and no
superpopulation [M]. A builder spells the five names itself (`1000GENOMES:phase_3:<CODE>`, the CODE being
decision 12's member) and cannot validate them against the listing.

### 2.3 What comes back

Response shape [M]: a JSON array of
`{"variation1": "rs646776", "variation2": "rs4970836", "r2": "0.924767", "d_prime": "0.975903",
"population_name": "1000GENOMES:phase_3:EUR"}`. **`r2` and `d_prime` are JSON strings**, six decimals.

| pair | EUR | AFR | EAS | SAS | AMR |
|---|---|---|---|---|---|
| rs646776 / rs4970836 (r², D′) | 0.924767, 0.975903 | 0.136863, 0.933203 | 0.833807, 0.953989 | 0.994703, 1.000000 | 0.792206, 0.964114 |
| rs429358 / rs2075650 (r², D′) | 0.492959, 0.773975 | **`[]`** | 0.683996, 0.883058 | 0.286828, 0.655345 | 0.453817, 0.678868 |

[M, all ten.] `ALL` for the first pair: r² 0.552116. CEU for the first pair: 0.903728 (EUR, the pooled
superpopulation, is 0.924767).

### 2.4 Three outcomes, and an empty one that is not zero

| request | HTTP | body [M] |
|---|---|---|
| unknown rsID (`rs999999999999`) | 400 | `{"error": "Could not fetch variation object for id: rs999999999999."}` |
| population not in the LD set (`gnomADg:nfe`) | 400 | `{"error": "Could not fetch population object for population name: gnomADg:nfe"}` |
| two chromosomes (rs646776 chr1, rs429358 chr19) | 200 | `[]` |
| APOE pair in AFR | 200 | `[]` |
| APOE pair in AFR with `r2=0` | 200 | `[]` |
| APOE pair in AFR with `d_prime=0` | 200 | `[]` |
| APOE pair in YRI | 200 | `[]` |
| APOE pair, no population | 200 | 20 rows; none for ACB, ESN, GWD, LWK, MSL, YRI or any GGVP group; ASW r² 0.063522 |
| first pair in EUR with `r2=0.95` | 200 | `[]` (the parameter is a floor: 0.92 is filtered out) |
| `rs1624712` (a synonym of rs646776) / rs4970836 in EUR | 200 | one row naming `variation1: "rs646776"` |
| a variant with itself | 200 | r² 1.000000, D′ 1.000000 |

So `[]` arrives both when the pair cannot be computed (two chromosomes) and when the African r² is
presumably small (ASW, an admixed group, shows 0.0635; the six African-ancestry groups return nothing), and
lowering the `r2` floor to 0 does not bring a row back. This is consistent with an internal floor below which
pairs are dropped, but the floor's value is not established here [I]. A builder writes `[]` as the withheld
arm with its own reason, never as r² = 0 (`@unreachable-not-absent`, `@answered-is-not-absent`). The
response also names the *current* rsID, not the one asked for, so a row is keyed on the request.

### 2.5 Rate limits, latency, release

- Headers on every answer [M]: `x-ratelimit-limit: 55000`, `x-ratelimit-period: 3600`,
  `x-ratelimit-remaining` counting down by one per call, `x-ratelimit-reset` in seconds. No `retry-after` was
  seen.
- **The service was flaky during the probe** [M]: at 02:39 UTC `/info/ping`, `/info/software` and the
  population listing all returned HTTP 500 with a 10,135-byte EBI HTML error page (`content-type: text/html`),
  then 200s with 22–37 s latency a minute later; one later pairwise call (EAS) needed a retry after a 500.
  Single calls otherwise took 0.2–16 s. The existing `ensembl.py` client contract (retry, then translate)
  applies, and a non-JSON 500 is the "200 that is not JSON" leg's sibling (`@client-exception-contract`).
- Release marker: `/info/data` → `{"releases": [116]}`, `/info/software` → `{"release": 116}` [M]. LD here is
  computed from 1000 Genomes phase 3 genotypes inside that release, so `ld_pairs.csv`'s "reference and its
  release" can be `1000GENOMES:phase_3` + `ensembl 116` [I].
- Licence: nothing new on the wire. `licensing.ENSEMBL_TERMS` already records Ensembl (Apache-2.0,
  unrestricted); 1000 Genomes' own terms were not re-read [I].

---

## 3. ClinVar-GKM

### 3.1 Where it is now

```bash
curl -sS https://data.clinvar-gkm.org/index.json                          # version manifest
curl -sS https://data.clinvar-gkm.org/v1/1.1/index.json                   # the line's release index
curl -sS https://data.clinvar-gkm.org/v1/1.1/parquet/manifest.json        # the Parquet set's manifest
curl -sS https://data.clinvar-gkm.org/v1/1.1/deltas/clinvar-gkm-delta_2026-1031.manifest.json
curl -sSI https://data.clinvar-gkm.org/v1/1.1/parquet/allele.parquet
```

plus the repository's own docs, read from `raw.githubusercontent.com/clingen-data-model/clinvar-gkm/main/`
(`docs/data-access/download.md`, `parquet.md`, `docs/reference/changelog.md`).

- **Host:** Cloudflare R2 behind `https://data.clinvar-gkm.org` (`server: cloudflare`), plain HTTPS, no
  authentication [M]. Not Google Cloud Storage (the pipeline runs on BigQuery; the files are served from R2).
  The survey's `pub-f0ad0e0dac0345408dcc95bda20beb42.r2.dev/index.json` now answers 401 [M].
- **Release line:** the root `index.json` names `"current": "v1/1.1"` (`schema 1.1.0`, status `current`) and
  `v1/1.0` (`schema 1.0.1`, status `frozen`) [M]. GitHub releases: `1.1.0` 2026-10-22, `1.0.1` 2026-10-14,
  `1.0.0` 2026-10-10, `1.0-rc3` 2026-08-26 [M: `gh api repos/clingen-data-model/clinvar-gkm/releases`]. 1.1.0
  "moved every download URL to `v1/1.1/`" and declares itself generally available with immutable published
  files [M: download.md, changelog].
- **Layout:** `v1/1.1/` holds monthly fulls (`clinvar-gkm_YYYY-MM.json.gz`, about 4.7 GB each), the current
  month's weekly fulls under `weekly/`, weekly deltas under `deltas/` (earlier months in `deltas/YYYY-MM/`),
  and **one** Parquet set under `parquet/` [M: download.md and the index]. Each bundle has a `.sha256`
  sidecar. Paths outside `/v1/` and the root index answer 403; a moved file answers 404; "HTTP 429. Requests
  are rate-limited. Download whole files and query them locally rather than issuing many small range
  requests" [M: download.md].
- **Parquet cannot be pinned:** "**One** Parquet dataset is published, rebuilt every release (weekly) from
  the newest weekly release and overwritten in place. There are no dated, per-delta or archived Parquet sets"
  [M: parquet.md]. A past state is rebuilt from a monthly bundle plus deltas, or by a `clinvar-gkm-parquet`
  tool that "is in design and not yet released" [M]. `v1/1.0/parquet/allele.parquet` → 404 [M].

### 3.2 The current release

| marker | value [M] |
|---|---|
| line index `latest_release` | `2026-10-31` (updated 2026-11-04T01:07:03Z) |
| latest weekly delta | `clinvar-gkm-delta_2026-1031.json.gz`, 26,052,563 bytes, index `modified 2026-11-03`; its manifest: `baseline_release 2026-10-24`, `pipeline_version 1.1.0-10-g8a248d9`, `allele` added 16,557, updated 0, 3 deleted |
| Parquet `source_release` | `2026-10-24`, `dataset clinvar_2026_10_24_v2_6_1`, `build_date 2026-10-27T19:50:32Z`, `builder "BigQuery export"`, `schema_version 1.1.0` |
| `allele.parquet` | 1,119,974,942 bytes, `sha256 cfd29e54…c625`, Last-Modified 2026-10-27 19:46:48 GMT, `accept-ranges: bytes` |
| `variation.parquet` | 3,914,257,911 bytes |
| `location.parquet` | 714,136,812 bytes |
| whole Parquet set | 22 files, 13,167,316,939 bytes |

**The Parquet set lags the newest weekly release by one week** (2026-10-24 against 2026-10-31) [M]. The
weekly cadence the survey found stalled at 2026-08-22 has resumed: deltas exist for every week from
2026-07-06 to 2026-10-31 [M]. A currency check against `latest_release` would have fired on 2026-11-04 by one
week even though the Parquet set was the newest one published.

### 3.3 Licence markers, verbatim from `parquet/manifest.json` [M]

- `license.id`: `CC0-1.0`
- `license.scope`: "CC0 covers ClinGen's contribution (the code and this published transformation) only. It
  adds no restriction, and it cannot grant rights that NCBI or ClinVar's submitters hold."
- `attribution`: "Derived from NCBI's ClinVar. If you use or redistribute these data, attribute ClinVar as
  the data source and cite it; cite ClinVar-GKM (doi:10.5281/zenodo.18343663) if you used these files."
- `disclaimer`: "ClinVar's disclaimer applies: the information is not intended for direct diagnostic use or
  medical decision-making without review by a genetics professional. ClinVar-GKM is not an NCBI, NLM or NIH
  product and is not endorsed by them."
- `source.data_use_policy`: `https://www.ncbi.nlm.nih.gov/clinvar/docs/maintenance_use/#disclaimer`

The repository's `LICENSE` is CC0-1.0 [M: GitHub API `license.spdx_id`]. Whether the lane writes its own
`SourceRow` or is a second surface of `clinvar` (`@write-the-sourcerow`: "A second surface of an
already-declared source may not claim the lane's `(source, layer)` row") is open, not decided here.

### 3.4 `allele.parquet`: schema and rows

Read by projection over HTTP, never written to disk:

```python
import polars as pl
URL = "https://data.clinvar-gkm.org/v1/1.1/parquet/allele.parquet"
pl.scan_parquet(URL).collect_schema()
pl.scan_parquet(URL).select(pl.len()).collect()
```

- Schema [M]: `id: String, type: String, digest: String, name: String, location_id: String, data: String`.
  No key-value metadata. The state, the expressions and the location reference are only inside `data`, a JSON
  string per row.
- **4,599,039 rows** [M] (the survey's 4,460,884 was 1.0-rc3 on 2026-09-28).
- A row [M]: `id ga4gh:VA.tOv53DGAbxNlmZkjWmICHRGOFYdiQNUj`, `name NC_000003.12:g.46265894G>A`, `data
  {"digest": …, "expressions": [{"syntax": "spdi", "value": "NC_000003.12:46265893:G:A"}, {"syntax":
  "hgvs.g", …}, {"syntax": "gnomad", "value": "3-46265894-G-A"}], "location":
  "#/location/ga4gh:SL.lzrz…", "state": {"sequence": "A", "type": "LiteralSequenceExpression"}, "type":
  "Allele"}`.
- **No ClinVar id and no rsID on the allele.** The allele → ClinVar variation link is in `variation.parquet`
  (`constraints[].type = "DefiningAlleleConstraint"`, `constraints[].allele`), one to one: 4,599,039 links,
  4,599,039 distinct alleles [M]. The rsID is in `variation.mappings[]` with `coding.system =
  "https://www.ncbi.nlm.nih.gov/snp/"`, `relation = "relatedMatch"`, and `code` **without** the `rs` prefix
  (`"879687080"`) [M]. 2,896,736 of 4,692,217 variations carry one; 222,457 rsIDs name more than one allele
  (multi-allelic sites) and 54 alleles carry more than one rsID [M]. Reading `variation.parquet`'s `id`,
  `mappings` and `constraints` columns over HTTP took 8 s [M]; the 3.9 GB file is mostly the `data` and
  `extensions` columns.

### 3.5 How many are indels

Every allele was streamed (projection `name, data`, 13 s) and classified by the SPDI expression in `data`
(deleted length against inserted length) and by `state.type` [M]:

```python
spdi = pl.col("data").str.extract(r'"syntax":"spdi","value":"([^"]+)"', 1)
state_type = pl.col("data").str.extract(r'"state":\{[^}]*"type":"(\w+)"', 1)
# SNV: one base deleted, one inserted; then same-length MNV, net deletion, net insertion
```

| `state.type` | count [M] |
|---|---|
| `LiteralSequenceExpression` | 4,309,110 |
| `ReferenceLengthExpression` | 289,929 |

| SPDI class | count [M] |
|---|---|
| SNV (1 for 1) | 4,270,774, of which 1,270 are `ReferenceLengthExpression` reference-agreeing alleles (`NC_000019.10:g.18161380=`) |
| net deletion | 207,412 |
| net insertion | 101,993 |
| same-length MNV | 12,768, of which 70 are multi-base `ReferenceLengthExpression` reference-agreeing alleles |
| no SPDI expression | 6,092 (names such as `NC_000019.9:g.40405975C>A`, `NM_175918.3:c.1111G>A`: GRCh37 or transcript-only) |

All SPDI accessions are GRCh38 (`NC_0000NN.1x` at the GRCh38 versions, `NC_012920.1` for 3,115 mitochondrial
alleles), with one `NC_060946.1` (T2T) [M].

**The indel slice** (net insertions plus net deletions) is **309,405 alleles**: 285,144
`ReferenceLengthExpression` and 24,261 `LiteralSequenceExpression` [M]. The slice as first cut also let
through 70 multi-base reference-agreeing alleles (`NC_000021.9:g.45504512_45504520=`, SPDI deleting and
inserting the same `GGCCCCCCA`), so the measured file below has 309,475 alleles; a builder drops those 70
with the 1,270 single-base ones. Joined to its ClinVar variation and rsID the cut is 309,479 rows (four
alleles carry two rsIDs), 219,871 of them with an rsID, 202,251 distinct rsIDs, and **15.6 MB** as zstd
Parquet with the columns `vrs_id, state_type, spdi, gnomad, clinvar_variation_id, rsid` [M: written once and
measured]. The `gnomad` spelling is unique per allele (no spelling names two ids) [M].

RM270's insertion ids are present and unchanged since rc3 [M]:

| rsID | ClinVar | VRS id | SPDI | gnomad |
|---|---|---|---|---|
| rs72613567 | `clinvar:1247925` | `ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7` | `NC_000004.12:87310240:A:AA` | `4-87310240-T-TA` |
| rs77944059 | `clinvar:167657` | `ga4gh:VA.ks2GTWYOW0aKfGbJ2aeQUOZxOT_xC2ts` | `NC_000002.12:166204470:AAACAAACAAA:AAACAAA` | `2-166204470-GAAAC-G` |

The first is PT2 C1's pinned test id. Their states are `{"length": 2, "repeatSubunitLength": 1, "sequence":
"AA"}` and `{"length": 7, "repeatSubunitLength": 4, "sequence": "AAACAAA"}` [M]. `rs8176719`, C4's
two-id test case, has no ClinVar variation with that rsID in this release [M].

### 3.6 VRS version marker

No VRS version is recorded in `allele.parquet` (no key-value metadata, no per-row field) or in
`parquet/manifest.json` (`schema_version 1.1.0` is ClinVar-GKM's own schema) [M]. The changelog's 1.0.0 entry
says: "First official release on the finalized GKM standards — VRS 2.1.1, Cat-VRS 1.1.1, VA-Spec 1.1.0, and
GKM-Core 1.3.0" [M]. GKS_SURVEY's `vrs_output_2_0_1.schema.json` described 1.0-rc3 and no longer holds.
The lane's `release.json` therefore carries the VRS version as a declared value read off the changelog of the
release it pinned, not off the bytes [I].

### 3.7 Built (RM305, 2026-11-04)

The lane was built once for real, through the shipped command and its download path:

```bash
JUST_DNA_HTTP_RETRY_ATTEMPTS=6 uv run just-dna-enricher clinvar-gkm build --out data/repro/clinvar_gkm
```

Run 04:57 to 05:22 UTC. Both inputs were downloaded whole and matched `manifest.json` in size and sha256 [M].
A first attempt with plain `curl` had its `variation.parquet` connection reset at about 1 GB; the build's
own download retries the transport.

| what | value [M] |
|---|---|
| `dataset` | `clinvar_gkm_2026-10-24` (`source_release` 2026-10-24, source `dataset` `clinvar_2026_10_24_v2_6_1`) |
| `allele.parquet` sha256 | `cfd29e5464c9903c7645e7ca4359c6b0bc660e329ba0176635037f0ac45bc625` (1,119,974,942 bytes) |
| `variation.parquet` sha256 | `136b0db54d39fe74a570a3e59e00acc2aa7d24de1f937d8a441b0b52392740f1` (3,914,257,911 bytes) |
| alleles read | 4,599,039 |
| dropped: no SPDI / off GRCh38 / same length / no VCF spelling | 6,092 / 1 / 4,283,541 / 0 |
| indel alleles kept | **309,405**, the §3.5 figure: 285,144 `ReferenceLengthExpression`, 24,261 `LiteralSequenceExpression` |
| rows (one per allele and rsID) | 309,409 |
| rows with an rsID / distinct rsIDs | 219,844 / 202,236 |
| `data/clinvar_gkm-indels.parquet` | 17,172,269 bytes (zstd; 10 columns, so larger than §3.5's six-column 15.6 MB) |
| line's `latest_release` at build | 2026-10-31, so the build reported that the set lags by one week |

The rsID counts are 27 and 15 below §3.5's 219,871 and 202,251. §3.5 counted the 70 multi-base
reference-agreeing alleles the probe's filter let through, and the builder drops them [I: the difference is
not otherwise measured]. No SPDI deleted or inserted field is digit-only in this release, so the length rule
never had to read a deletion length [M]. The `gnomad` expression spells the mitochondrion `MT` and the sex
chromosomes `X` and `Y` [M]. `rs72613567` and `rs77944059` resolve to the §3.5 ids, VCF spellings and ClinVar
variations; `rs8176719` is not witnessed [M: `clinvar-gkm lookup`, and `test_clinvar_gkm.py` against the
built snapshot]. `cache status` shows the lane present at 17.2 MB, and the publish plan is
`data/clinvar_gkm-indels.parquet`, `LICENSE.txt`, `release.json`, in that order [M].

---

## 4. Files and reproduction

- Scratch reads lived in `data/probes_0_8/{ot,ld,gkm}/` (git-ignored): the five Open Targets parts, the
  croissant, every raw LD response body, ClinVar-GKM's index, Parquet manifest, delta manifest and docs.
  Nothing there is committed; the numbers above are re-derivable from the commands quoted.
- One slip worth recording: an `httpx` GET with `Range: bytes=-8` against `allele.parquet` came back
  **200 with the whole 1.12 GB body** once (held in memory, not saved), while `curl -r` and a suffix range
  from curl both got 206. A builder that range-reads R2 checks for 206, never assumes it.

---

## 5. Built 2026-11-04: the `opentargets` lane

**Basis:** the lane builder on `build/RM333`, run on this machine on 2026-11-04 between 05:34 and 06:47 UTC.
Every number below is [M], read off the built files or the commands' output.

### 5.1 What was downloaded, and how

The full release this lane reads is about 22 GB, past the ~6 GB the build brief allows for a hand-run, but
all of it was mirrored, because a partial coloc set would turn "no colocalisation for this pair" into a false
fact. The mirror ran as eight parallel `curl` streams (a scratch script, `curl --retry 5`), at 3 to 7 MB/s in
aggregate: `l2g_prediction` 200 parts, `credible_set` 200, `variant` 25, `study` 1, `colocalisation` 200, plus
`croissant.json` (version `26.09`, `datePublished` 2026-09-18, licence CC0 1.0). The builder's own download
path was run separately, `just-dna-enricher opentargets build --parts 1 --out data/rm333/net_build`: it listed
all five datasets over https, fetched one part of each (and `study` whole) in 2 min 54 s, built, recorded
`parts_read` 1 of 25 / 1 of 200 / 1 of 200 / 1 of 200, printed the partial warning, and deleted its mirror.

### 5.2 The build

`just-dna-enricher opentargets build --source <mirror> --out /data/just-dna-cache/opentargets` took 14 min 52 s
and wrote 5.2 GB (5,419.5 MB as `cache status` measures it; `approx_mb` is 5500):

| table | rows | MB |
|---|---|---|
| `variants.parquet` | 7,886,762 | 62 |
| `consequences-*.parquet` (25) | 280,906,222 | 115 |
| `credible_sets.parquet` (GWAS only) | 1,519,507 | 40 |
| `credible_set_members-*.parquet` (200) | 40,967,780 | 474 |
| `l2g.parquet` | 3,293,342 | 48 |
| `colocalisations-*.parquet` (200, molecular-QTL right side only) | 79,887,470 | 4,607 |

Every L2G row of the release survived the GWAS-locus filter (3,293,342 in, 3,293,342 out). The coloc filter kept
79,887,470 of 283,303,467 rows (28.2%, the §1.9 estimate), by right-hand type `eqtl` 36,928,981, `sqtl`
19,144,070, `tuqtl` 11,382,592, `pqtl` 7,393,415, `sceqtl` 5,038,412; every kept row named its right-hand gene.
Fine-mapping methods over the GWAS sets: `PICS` 759,320, `SuSiE-inf` 739,423, `SuSie` 20,764. Impact over the
transcript rows: MODIFIER 278,807,665, MODERATE 1,134,511, LOW 667,184, HIGH 296,862. `cache status` printed
`opentargets   present  /data/just-dna-cache/opentargets  opentargets_26.09  5419.5 MB`.

### 5.3 The three grain questions, answered from the built tables

1. **Coloc is a sibling table.** Over the whole snapshot, 10,326,986 `(study locus, right gene)` pairs, of
   which 2,308,572 have more than one right-hand credible set, up to 1,738 for one pair (tissues and QTL kinds).
   `h4`/`clpp` on the L2G row would have had to pick one.
2. **The lead-only predicate is narrow.** Over the whole release (raw `credible_set`): rs429358 is in 1,826 GWAS
   sets and leads 1,682; rs7412 2,627 and 2,019; rs2075650 175 and 41; rs72613567 123 and 54; rs646776 2,061 and
   205; rs10455872 1,335 and 960; rs3798220 226 and 180; **rs1800562 82 and 0**. A module variant that is a
   member but not the lead gets a posterior on `gwas_effects.csv` and no `locus_to_gene.csv` row.
3. **A (variant, study) pair can carry two posteriors.** 1,096,671 of the release's 39,795,615 GWAS (variant,
   study) pairs have more than one distinct (posterior, method); the pass withholds them.

### 5.4 The pass over a real module

`opentargets enrich` over a copy of `reference_examples/hfe_hemochromatosis`, against the full snapshot, in
1.3 s: 12 alleles asked, all 12 in the release; 1,140 consequence rows; no `locus_to_gene` or coloc row (no
HFE allele leads a GWAS set); posterior filled on **0** of 195 association rows: 168 name a study with
credible sets that do not contain rs1800562, 18 a study with none, 9 no study. rs1800562's 82 memberships are
in 82 studies, none of which the module's Catalog rows name. With rs2075650 added (its resolution row and the
103 associations the Catalog's v2 API lists for it), the same pass writes 88 L2G rows over its 41 led sets,
185 coloc rows and 1,200 consequence rows, and fills the posterior on 36 rows. That module, against a slice
cut by `subset_snapshot` for its alleles and studies (696 KB, committed as `assets/opentargets_slice/`), gives
the same tables and counts as against the whole snapshot (`test_the_slice_answers_as_the_whole_release_does`).

### 5.5 What this found outside the lane

The GWAS Catalog's legacy REST API, which the `gwas` pass reads
(`https://www.ebi.ac.uk/gwas/rest/api/singleNucleotidePolymorphisms/<rsid>/associations`), answers **HTTP 410**
with "This legacy GWAS Catalog REST API is no longer available", pointing at its v2 migration guide. The v2
endpoint (`/gwas/rest/api/v2/associations?rs_id=`) answers 200. So `gwas_effects.csv` cannot be filled for a
new module until the pass moves to v2; RM239's posterior is filled on rows that already exist.
