# AlphaGenome Atlas — the bulk artifacts, the terms that govern them, and what a slice would cost

**Subjects:** the three precomputed artifacts published on the AlphaGenome Atlas "learning"
page (AVI SNV scores, AlphaGenome SNV merged splicing scores, AVI SNV feature importance
scores); the *AlphaGenome Services Additional Terms of Service* that govern all three; and the
live AlphaGenome API reached with a personal `ALPHAGENOME_API_KEY`.
**Basis:**

- `/data/downloads/combined_splicing_snvs_tabix.zip` — the merged-splicing artifact, downloaded
  complete (20,637,481,745 bytes over two members, `combined_alphagenome_splicing_snvs.tsv.gz`
  and its `.tbi`; member timestamps 2026-08-27 19:16/19:17). Every splicing number below was
  re-derived from those bytes in this session.
- **Four terms documents**, all saved by the maintainer from a signed-in browser and pinned in
  `docs/vendor/` with `pdftotext -layout` extractions beside them so the clauses are greppable —
  `alphagenome_additional_tos.pdf` (`sha256 0a1b52c4…`, Last Modified 2026-09-08),
  `alphagenome_output_terms.pdf` (`sha256 a1293588…`, Effective 2025-06-25),
  `google_terms_of_service.pdf` (`sha256 79fc5e45…`, Effective 2026-07-30) and
  `google_apis_terms_of_service.md` (`sha256 b6d1364e…`, Last modified 2021-11-09). **Every
  quotation in §2 is from those files**, never from a web page. §2.8 lists the two binding
  documents still missing.
- The live API, via the `alphagenome` PyPI SDK in a throwaway venv on `/data`, on the
  maintainer's own key.
- The three artifacts themselves, now all downloaded, at `/data/genomes/alphagenome/`.
- The artifact **licence classes** in §1 are still **quoted from the maintainer's reading of the
  Atlas page**, not fetched: `deepmind.google.com/science/alphagenome/*` is a sign-in-gated
  single-page app that serves 185 KB of navigation chrome and no content to `curl`/WebFetch. That
  page is the only place membership of the Permissive class is stated, which §2.8 records as the
  one gap that matters.

**Date of analysis:** 2026-09-09.

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`.
Nothing here proposes a design and nothing here is an adoption decision — no `RMn` is filed by
this document, deliberately. Where a question is legal rather than technical it is left as a
question.

---

## 0. Summary — the things that decide whether this is adoptable

1. **The three bulk artifacts are not one licence.** Only *AVI SNV scores* (88.5 GB) is a
   *Permissive Use Downloadable Artifact*, usable commercially and by commercial
   organizations. The merged splicing scores (20.6 GB) and the AVI *feature importance* / SHAP
   scores (283.9 GB) are non-commercial-only. **The artifact already on disk is the
   non-commercial one**; the commercially usable one is 1.8 GB into an 88.5 GB download and is
   unmeasured here (`@probe-names-the-table`).

2. **The score distribution is not the shape the effect-size plan assumes.** There is no long
   tail toward zero. The merged splicing score has a **floor near 0.03**: 86.7% of all
   3.92 billion rows sit in two adjacent quarter-decade bins between 0.032 and 0.100, and only
   0.32% of the corpus falls below 0.01 at all. "Discard the negligible 90%" is therefore a
   **threshold choice against a background lump**, not a filter of zeros — and the whole
   reduction happens between 0.02 (91.3% kept) and 0.05 (10.4% kept). See §3.

3. **Size is not the binding constraint, and the 40 GB budget never bites.** Re-encoded as
   parquet — `UInt16` at 10⁻⁴ precision, one row per position with three ALT columns — **the
   entire corpus is about 9.6 GB with nothing discarded**, less than half the 20.6 GB source.
   A ≥0.1 threshold slice is ~1.1 GB. Measured on `chr22` and scaled, not estimated (§4). This
   dissolves the forcing argument for a threshold: the question stops being "which slice fits"
   and becomes "is this a lookup table or a finding list", which §4.2 sets out and does not
   decide.

4. **The rarity axis exists offline but is 6% populated, which is not the same as absent.** The
   Ensembl snapshot already on disk carries `MAF`/`MAC` — but on `chr22` only 6.1% of its SNVs
   have a value, and after joining to AlphaGenome only **0.61% of the ≥0.1 slice has a
   frequency at all**. A 2D effect × rarity surface is therefore buildable today and would be
   tiny — *for the wrong reason*. `MAF` absent means unmeasured, never rare, so the surface is
   governed by the sparsity of one column rather than by biology. §5 has the measurements.

5. **All three bulk artifacts are SNV-only**, checked rather than inferred: the SHAP file is
   *named* `…indels_with_am_snvs` and carries `IS_INSERTION`/`IS_DELETION` columns, but across
   8 M sampled rows both flags are constant `0` and no `REF`/`ALT` is multi-base (§1.5). **Rare
   indels do not exist in the bulk data at all** — only through the API, which is per-request,
   tissue-resolved and non-commercial. Filtering "rare indels with low score" is not a slice of
   these artifacts.

5b. **The SHAP artifact is a 20-column feature table**, not an opaque attribution: it carries
   `MERGED_SPLICING` (the splicing artifact rescaled by ~3.345, not copied), nine `MAX_ABS_*`
   modality scores, and three **third-party** features — `ALPHAMISSENSE`, `CACTUS_241_WAY`,
   `PHASTCONS_470_WAY` — each with its own upstream terms. And it writes `0.0` where the
   splicing pipeline never scored a position, so the source itself collapses unmeasured into
   no-effect (§1.5).

5f. **A negative `AVI` is low conservation, not down-regulation.** The Atlas exposes the model's
   own 18 inputs and attributions, and they are the SHAP file's columns in order (verified against
   the splicing artifact to four significant figures). At both negative variants probed, essentially
   the entire score is one feature — `CACTUS_241_WAY`, the signed 241-way comparative-genomics score,
   at −20.0 and −11.5 — so a negative reads as **evidence against functional impact**. The nine
   regulatory features are all `MAX_ABS_*`, magnitudes with the sign already discarded, so there is
   no expression direction anywhere in the model. The axis is benign ↔ damaging, not down ↔ up (§4.7).

5m. **A `PHRED` threshold is a triage, not just a size dial** — the one thing §4.4.1 could not
   settle. Against ClinVar (8 of 24 contigs, 959,844 joined rows): **`PHRED ≥ 20` keeps 97.5% of
   pathogenic variants, discards 94.4% of benign ones and 99% of the corpus** — 97× the baseline,
   586× at ≥ 30. Median `PHRED` runs 31.2 pathogenic against 7.3 benign. And the sign agrees
   independently of §4.7's attribution reading: **0.16% of pathogenic variants score negative
   against 33.20% of benign**. Read it with the ascertainment caveat — ClinVar's pathogenic set is
   mostly coding, which is what AVI scores high for reasons already known (§4.10).

5l. **Ship a 502 KB knot table instead of querying anything.** The `raw_score` value set is a fixed
   grid that saturates at **~41,000 values** — 400 M rows scanned grew it 1.7% past one chromosome,
   and the **2,001 ambiguous knots and 0.000700 widest span did not move at all**. A
   `(raw, phred_lo, phred_hi, n)` table is **501,592 bytes**, and it carries the reconstruction
   curve, the per-knot ambiguity interval, and decidable threshold safety at once. Rebuilding the
   column by API is **272 days and ~92 M RPCs** at the measured 375 variants/s — and prohibition 3
   plus a revocable licence make it the wrong shape of request anyway (§4.7.2).

5k. **The precision the file lost exists on the API, and neither surface is a superset of the
   other.** The Atlas returns `raw_score` as `float32` — ~7 significant digits against the file's 4
   — and at the exact atom that causes every threshold-3 flip, six rows the file prints identically
   come back distinct and in the right order, reproducing the published `PHRED` **exactly at five
   decimals**. So the 3.56e-4 residual is a publishing artefact, not a model limit. But the file
   still wins above `PHRED` 72.247, where the API's `float32` quantile saturates at 1.0 (§6.3). No
   other download helps: splicing and SHAP publish at the same four digits, and SHAP carries no AVI
   column. The shape this implies is **bulk build plus targeted API refinement**, and §4.8.1 says
   exactly which rows need it (§4.7.1).

5h. **The reconstruction residual reranks pervasively but microscopically, and rounding does not
   mend it.** One row in six changes rank, but the largest move anywhere is 3,168 places in 36 M —
   **0.0088 of a percentile**. Threshold flips are not smooth: **zero at every integer threshold
   1–50 except one**, where 1,218 rows move together because a single printed `raw_score`
   (`0.00076`, 8,443 rows) spans `PHRED` 2.99961–3.00027 and straddles 3.0. That makes safety
   **decidable** — a threshold is unsafe iff it lands inside a knot's span, checkable against the
   curve in advance. Rounding to 10⁻³ makes 97% of rows compare equal but raises the **worst case
   from 3.6e-4 to 1.0e-3**, so it hides the common case and worsens the rare one (§4.8).

5j. **A rescaled `UInt16` for `PHRED` is dominated by not storing it.** 16.3 GB to be twice as
   inaccurate (7.6e-4 against 3.6e-4) and five times as flip-prone as the free reconstruction from
   `raw_score`. Beating that reconstruction needs a scale of 1,404, which puts the top of the range
   at 125,632 — nearly twice what 16 bits hold. So the only two rational choices are `Int32`×10⁵
   exact, or nothing at all (§4.9.1).

5i. **Store the floats as `Int32`×10⁵ — lossless and 13% smaller than `Float32`.** Both columns
   print at most 5 decimals, so the integer scale is exact while `Float32` is both larger *and*
   lossy. Whole rows: 59.2 GB against 67.9 GB, or 34.4 GB keeping `raw_score` alone. The general
   lesson is not AlphaGenome-specific: **wherever a source publishes fixed decimals, a float is the
   wrong container** — its low mantissa bits are noise the source never had, and noise does not
   compress (§4.9).

5g. **`PHRED` cannot be recomputed from the published `raw_score` exactly**, and the obstacle is
   precision, not floating point: the file prints `raw_score` to **four** significant digits and
   `PHRED` to **six**, so 2,001 of `chr22`'s 40,204 distinct `raw_score` values carry up to **68**
   distinct `PHRED`s. Reconstruction through the empirical curve is off by `max 3.6e-4` — eleven
   orders of magnitude above `ε·N` — but reclassifies **zero rows** at any threshold. Exact for
   triage, lossy for reporting a rank (§4.6). And the 88.5 GB → 69 GB gap is not container overhead:
   the two float columns are **80% of the parquet** and text holds up because the values only ever
   had 4–6 digits (§4.5).

5e. **AVI's `PHRED` is a size dial, not a measurement.** Measured over all 8,812,917,339 rows,
   `PHRED ≥ p` keeps exactly `10^(-p/10)` of the corpus — to four significant figures across four
   orders of magnitude. So its histogram is a straight line by construction, there is no natural
   cut to find, and choosing a threshold *is* choosing a dataset size: **6.7 GB at ≥10 (top
   decile), 662 MB at ≥20 (top percentile), 34.4 GB for everything with `raw_score` alone**. It
   also contradicts the FAQ's common-variant background, so `PHRED` cannot substitute for the
   missing rarity axis. And because a rank discards sign, thresholding on it drops **every
   negative-scored variant** — 49.30% of the corpus (§4.4). *Negative-scored*, not
   *down-regulating*: AVI is not marked `is_signed` and the source says nothing about direction.

5d. **Motifs are not a dataset at either surface, and the API is still the only route.** "motif"
   appears nowhere in the SDK and none of the 22 Atlas scorers is one; the announced "Motif
   datasets" are unpublished. What reads a motif is in-silico mutagenesis, and one interval query
   returns a **600-variant × 1,617-TF-track** ISM matrix in **1.6 s**, each track named with its
   transcription factor and cell type. The files cannot: `MAX_ABS_CHIP_TF` collapses those 1,617
   named tracks into one unsigned magnitude. The API's addition is **resolution, not more scores**
   — 36,152 values per variant against the files' 20 (§6.4, §6.5).

5c. **The Output Terms require the licence text to travel *inside* the artifact**, not as a
   link: restriction 3b says anyone attaching their own terms must carry the "Use restrictions"
   section as an enforceable provision. They also let Google demand deletion on breach, not only
   on termination — and they pin the applicable version to **the date the Output was generated**,
   which makes the artifact's own timestamp legally load-bearing. §2.7.

6. **The terms need at least four axes `SourceRow` cannot express**, and one of them is not a
   use restriction at all but a bar on *who may hold the data*: "The AlphaGenome Services aren't
   available for any commercial entity, even if conducting non-commercial work." That is not
   `commercial_use=False`. §2.6 enumerates all four.

7. **A 22 MB client exists, and `uv add alphagenome` is 255 MB.** The Atlas service serves the
   precomputed scores — all 22 scorers, SHAP included — over gRPC, and the generated protos plus
   `grpcio`/`protobuf` are a complete client (`numpy.frombuffer` decodes the score bytes; the
   request filter is a string). The SDK's own import path costs 242 MB because `atlas.py` imports
   `anndata` at module level. Six declared dependencies are never loaded on any scoring path.
   §6.2 sets out three shapes and picks none; the `alphagenome>=0.9.0` line currently in
   `enricher/pyproject.toml` is a probe and is **not** committed here.

8. **AVI reproduces exactly from the API; merged splicing does not.** The bulk AVI file is the
   API's float32 printed to five decimals, so the download and the RPC are one source. The
   splicing file is not reachable from the documented merge formula — 2.81 against a stated
   2.735, and zero rows at a locus the file scores. §6.3.

9. **There is no `--non-commercial` flag to lean on.** The compile gate is data-driven
   (`@gate-is-data-driven`): the mechanism is `declared_use` on a `SourceRow` in `sources.csv`,
   whose vocabulary is `{unstated, non_commercial, commercial}`. A flag was considered and
   refused once because it breaks the round trip.

---

## 1. What is actually published

| Artifact | Size | Format | Licence class |
| --- | --- | --- | --- |
| **AVI SNV scores** — AVI scores and Phred-scaled scores | 88.5 GB | Tabix | **Permissive Use** — commercial *and* non-commercial |
| **AlphaGenome SNV merged splicing scores** | 20.6 GB | Tabix | Non-commercial only |
| **AVI SNV feature importance scores** (SHAP) | 283.9 GB | Tabix | Non-commercial only |

392.9 GB in total. **Motif datasets are announced but not published** — "AlphaGenome Motif
datasets will be made available soon" — so nothing here plans against them.

The class split is not incidental. §2.5 shows it is written into the Terms as a definition: the
*AVI Score* is carved out of nearly every prohibition, and the *AVI Score Feature Breakdown* is
expressly **not part of** the AVI Score. The SHAP artifact is the Feature Breakdown, which is why
the same "AVI" prefix appears on both a permissive artifact and a non-commercial one.

### 1.1 The merged splicing file's schema

Five columns, tab-separated, bgzip-compressed with a tabix index:

```
#CHROM  POS  REF  ALT  alphagenome_splicing
chr1    65409  A  C  0.003052
chr1    65409  A  G  0.003479
chr1    65409  A  T  0.001343
```

One scalar per (position, ALT). No gene, no tissue, no transcript, no strand, no direction of
effect — it is a **magnitude with no sign and no unit** (`@weight-has-no-unit` is the house rule
that names why that matters for authoring). `POS` is 1-based VCF position, matching
`@start-1based`. Build is not stated in the file; the API and the docs are hg38/GRCh38 with
GENCODE v46, and §6 records that. **A file that does not state its own build is
`@build-in-manifest-only` territory** — the build would have to be stamped by whatever ingests
it, not read from the bytes.

### 1.2 Coverage — it is not "every possible SNV in the genome"

Measured over the whole file (24 per-contig `tabix` streams, aggregated):

| | |
| --- | --- |
| Rows | **3,924,674,451** |
| Distinct positions | **1,308,224,817** |
| Rows per position | **3.000** — exactly the three non-reference ALTs, everywhere |
| Contigs | `chr1`–`chr22`, `chrX`, `chrY`. **No `chrM`.** |
| Score range | max **5.799**; **no zeros anywhere** — the catch-all bin for `score ≤ 10⁻⁹`
is empty across all 3.92 B rows, and the lowest populated bin is `[10⁻⁶·²⁵, 10⁻⁶)` with 10 rows |
| Mean score | 0.045180 |

An exhaustive all-SNV map of GRCh38's ~3.1 Gb primary assembly would be ~9.3 billion rows. This
is 3.92 billion, so **roughly 42% of the assembly is covered** and the rest is simply absent —
consistent with a splicing model scored over gene-proximal windows rather than the whole genome.
The acrocentric short arms confirm it: `chr13` starts at 19,173,761, `chr14` at 18,601,089,
`chr15` at 20,531,841, `chr21` at 10,521,473, `chr22` at 15,528,065.

**Absent is not zero here** — a position missing from this file was not scored, which is the
`@unreachable-not-absent` distinction and would have to survive into whatever carries it. A
consumer asking "what is the splicing effect at chr1:1000?" must be able to get *unknown*, not
0.0.

`chrX` and `chrY` both begin at position **276,225** — the PAR1 region scored on both contigs,
which is `@par-one-place` arriving from a new direction: one place, two contigs, and here two
independent score rows for it. Whether they agree is unmeasured.


---

### 1.3 The AVI file's schema — two columns, and one is derived from the other

Downloaded complete on 2026-09-10 (`avi_scores_snvs_tabix(1).zip`, 88,473,344,811 bytes;
members `alphagenome_variant_impact_score_snvs.tsv.gz` 88,470,182,310 bytes and a 3,161,911-byte
`.tbi`, stamped 2026-08-27 17:40/17:42).

```
#CHROM  POS  REF  ALT  raw_score  PHRED
chr1    10001  T  A  -0.03868  1.06466
chr1    10001  T  C  -0.032    1.3114
chr1    10001  T  G  -0.0372   1.11839
```

Three differences from the splicing file, each of them load-bearing:

1. **`raw_score` is signed.** The splicing score is a magnitude; this one has a direction, and a
   negative AVI is a different claim from a positive one of the same size. Any ingest that takes
   `abs()` throws away half the content.
2. **It starts at `chr1:10001`** — the first non-N base of GRCh38 — where splicing starts at
   65,409. AVI looks genome-wide where splicing is gene-proximal. Confirmation is pending the
   full pass (§1.4).
3. **`PHRED` is not a second score.** The Atlas API returns, beside `raw_score`, a *calibrated*
   value, and `PHRED = −10·log₁₀(1 − calibrated)` reproduces the file exactly:

   | variant | API `raw` | API `calibrated` | −10·log₁₀(1−cal) | file `PHRED` |
   | --- | ---: | ---: | ---: | ---: |
   | chr1:10001 T>A | −0.03868196 | 0.21739846 | 1.06466 | 1.06466 |
   | chr1:10001 T>C | −0.03200157 | 0.26062370 | 1.31139 | 1.3114 |

   And `calibrated` is not an unexplained number: the upstream FAQ defines it as the **quantile
   score**, an empirical rank against a background distribution estimated per scorer and per track
   from **common variants — MAF > 0.01 in any gnomAD v3 population**, about 300 K of them. A
   quantile of 0.99 means "as extreme as the 99th percentile of common variation". Two
   consequences: the background is capped at **±0.999990** by that sample size, so `PHRED` cannot
   exceed **50** whatever the raw score does; and for the seven `is_signed` scorers the quantile is
   linearly mapped to [−1, 1] instead, with 0 at the median. AVI is unsigned, so its quantile is
   [0, 1) and the Phred transform applies.

   **That description does not match what the published AVI artifact does** — see §4.4, which
   measures `PHRED` against the whole corpus and finds it is an exact rank *within the corpus of
   all possible SNVs*, not against a 300 K common-variant background. The FAQ is describing the
   API's `quantile_score` for the recommended per-modality scorers; AVI's published column behaves
   differently, and the difference is measurable to four significant figures. So **the rarity axis
   is not already inside `PHRED`** — a tempting inference from the FAQ alone, and the measurement
   refuses it.

   So `calibrated` is a percentile rank and `PHRED` is its presentation. **A parquet needs
   `raw_score` and one of the two, never all three** — and the choice matters, because a
   percentile is bounded and quantises well while a Phred value does not. This also answers what
   the Atlas page means by "AVI scores and Phred-scaled scores": one score and one rescaling of
   its calibration, not two independent measures.

### 1.4 AVI, measured whole

Same 12-way per-contig pass as §3, over the complete extracted artifact; 46 minutes.

| | |
| --- | --- |
| Rows | **8,812,917,339** |
| Distinct positions | **2,937,639,113** (3.000 rows each) |
| Contigs | `chr1`–`chr22`, `chrX`, `chrY`. No `chrM`. |
| `raw_score` | −1.269 … 6.081, mean 0.028291 |
| …negative | **4,344,533,049 — 49.30%** |
| …exactly zero | 672,931 |
| `PHRED` | 0 … 89.451, mean 4.343 |

**AVI is genome-wide where splicing was not.** 2.94 billion positions against splicing's 1.31
billion — about **95% of the GRCh38 primary assembly** rather than 42%, and 2.25× the rows. The
§3/§4 arithmetic does not transfer, which §4.3 already said and this confirms.

**`raw_score` is signed and the sign is half the corpus.** 49.30% negative is not a tail; it is a
direction, and any ingest that takes `abs()` throws away what half the rows are saying. It also
has **672,931 exact zeros**, where the splicing artifact had none — so for AVI, unlike splicing,
`0.0` is a value the file actually writes and `absent` has to be represented some other way.

Its magnitude distribution is a clean lognormal-ish hump, peaking two quarter-decades below 0.03:

| `\|raw_score\|` | rows | share | cumulative |
| --- | ---: | ---: | ---: |
| ≥ 0.562 | 88,276,488 | 1.002% | 1.00% |
| 0.316 – 0.562 | 216,463,116 | 2.456% | 3.46% |
| 0.178 – 0.316 | 564,208,351 | 6.402% | 9.86% |
| 0.100 – 0.178 | 986,164,637 | 11.190% | 21.05% |
| 0.056 – 0.100 | 1,403,446,097 | 15.925% | 36.98% |
| **0.032 – 0.056** | **1,803,697,674** | **20.467%** | 57.44% |
| 0.018 – 0.032 | 1,471,529,460 | 16.697% | 74.14% |
| 0.010 – 0.018 | 956,931,155 | 10.858% | 85.00% |
| below 0.010 | 1,321,401,459 | 15.000% | 100.00% |

### 1.5 The SHAP artifact is a feature table, not an opacity

Read from `/data/genomes/alphagenome/avi_feature_importances_snvs_tabix.zip`
(283,875,513,566 bytes; member
`combined_ag_cond_linear_ensemble_20260417_feature_importance_indels_with_am_snvs.tsv.gz`,
283,872,737,358 bytes, stamped **2026-09-01** — four days later than the other two artifacts).
Header and streamed samples only; the file was not extracted.

**Twenty columns**, and they are the AVI model's inputs rather than a post-hoc attribution blob:

```
#CHROM POS REF ALT MERGED_SPLICING
MAX_ABS_ATAC MAX_ABS_CONTACT_MAPS MAX_ABS_DNASE MAX_ABS_CHIP_TF MAX_ABS_CHIP_HISTONE
MAX_ABS_CAGE MAX_ABS_PROCAP MAX_ABS_RNA_SEQ MAX_ABS_POLYADENYLATION
ALPHAMISSENSE CACTUS_241_WAY PROTEIN_TERMINATION START_LOST STOP_LOST
PHASTCONS_470_WAY IS_INSERTION IS_DELETION
```

Four findings, each one measured.

**It carries three third-party sources.** `ALPHAMISSENSE` is a different DeepMind model with its
own licence; `CACTUS_241_WAY` and `PHASTCONS_470_WAY` are comparative-genomics conservation
scores. A module carrying any of those columns stacks terms rather than inheriting one set
(`@a-hosts-terms-are-not-its-contents-terms` is the rule; §2.8 records the gap).

**`MERGED_SPLICING` is the splicing artifact rescaled, not copied.** Joining the two files over
`chr1:65,409–1,200,000` on `(pos, ref, alt)` gives **534,528 rows in common** and a ratio
`splicing / SHAP` of **3.345 ± 0.043** (min 2.915, max 3.500). Near-constant but not constant, so
neither file is exactly recoverable from the other, and a module must record **which file** its
splicing number came from. The scale is presumably the feature standardisation the linear
ensemble in the filename was fitted with.

**Zero means unscored, and the source does not distinguish them.** In that same window SHAP has
**2,953,776 rows** against splicing's **534,528**, and every one of the 534,528 joined rows had a
*nonzero* `MERGED_SPLICING` — so the other 2.42 M rows carry `MERGED_SPLICING = 0.0` at positions
the splicing pipeline never scored. This is `@unreachable-not-absent` occurring **inside the
source**: a consumer reading that column as a splicing effect reads 82% of this window as "no
effect" when the truth is "not measured". Anything ingesting this file has to reconstruct the
distinction from the splicing artifact's own coverage, because the column cannot express it.

**No indels, despite the filename and the two flags.** The member is named
`…feature_importance_indels_with_am_snvs`, and `IS_INSERTION`/`IS_DELETION` are real columns —
but across the first 8,000,000 rows sampled there is **not one** row with a multi-base `REF` or
`ALT`, and both flags are constant `0`. The final token of the name is the operative one: this is
the SNV slice of a feature schema that *supports* indels. So the SNV-only statement in §0 holds
for all three published artifacts, and the flags are a hint that an indel artifact could follow.

## 2. The terms, clause by clause

All quotations from `docs/vendor/alphagenome_additional_tos.txt`, Last Modified 2026-09-08 — one
day before this probe, and the same day the Atlas launched. A recorded `license_sha256` is the
repo's existing answer to terms that move (`licensing.py`'s module docstring records that both
halves of the static PGx table went stale inside one release); the hash is in the Basis block
above.

### 2.1 Eligibility — a bar on the holder, not on the use

> The AlphaGenome Services are **only** available for use by individuals and non-commercial
> organizations (universities, non-profit organizations and research institutes, educational and
> government bodies), or for journalism.

and, in *Account and Registration*:

> The AlphaGenome Services aren't available for any commercial entity, even if conducting
> non-commercial work.

This is the clause with no analogue anywhere in the repo. Every existing gated source
(ClinPGx/CPIC/PharmVar) restricts what you may *do* — no sale, share-alike. This one restricts
**who may hold it**. A commercial organization doing unfunded basic research is eligible for
none of it.

### 2.2 The two definitions that carry everything

> "**Output**" … (a) any model output, AVI Scores, other pre-computed scores, or pre-computed
> datasets and related information provided by an AlphaGenome Service … "**Derivatives**" … any
> visual representations, computational predictions, descriptions, modifications, copies, or
> adaptations that are substantially derived from Output.

A thresholded parquet slice of the splicing file is squarely a **Derivative**: it is a
modification and a copy, substantially derived. Nothing about compiling it into a module
changes its class.

### 2.3 The grant, and the word in it that matters

> Subject to your compliance with the Terms, you may access, use and modify the AlphaGenome
> Assets and distribute Output and Derivatives. We grant you a non-exclusive, royalty-free,
> **revocable**, non-transferable and non-sublicensable … license …

Distribution of Derivatives is expressly granted. The licence is **revocable**, and *Termination*
says what revocation costs:

> you must immediately stop using and delete all copies of the Output and Derivatives in your
> possession or control, require all third parties (except for scientific journals) that you
> have shared any Output or Derivatives with to stop using and delete such Output and
> Derivatives …

### 2.4 The prohibitions that bite

- **1.** No use "on behalf of a commercial organization or in connection with any commercial
  activities" — except Permissive Use artifacts; journalism is the only other exception.
- **1b.** "You must not share Output or Derivatives with any commercial organization or use any
  AlphaGenome Services in a manner that will grant a commercial organization any rights in
  Output or Derivatives, **in each case aside from indirectly via a scientific publication, open
  source release or to support journalism**." The italicised carve-out is the only route by
  which a non-commercial-derived module could legitimately reach a commercial reader.
- **2.** Not for HIPAA-regulated health information — worth reading beside the repo's standing
  "no sample data" rule, which already keeps a module clear of it.
- **3.** No reverse-engineering, republishing, copying, modifying, distributing, selling or
  granting access to the *Services* — closed with "This doesn't stop you from using and sharing
  Output or Derivatives in accordance with the Terms."
- **4.** Except for Permissive artifacts, not "to train machine learning models or related
  technology for predicting the effects of genetic variants similar to AlphaGenome."
- **5.** Except for Permissive artifacts, no distribution "without providing conspicuous notice
  that any Output or Derivatives you publish or distribute are provided under and subject to
  [the] AlphaGenome Output Terms of Use **and of any modifications you make to Output**." 5b
  adds: if you attach your own terms, you must carry the "Use Restrictions" section as an
  enforceable provision binding subsequent users.
- **7a.** Credentials "are personal" and must not be published or shared "even within your
  organization" — the same standing as the PharmVar key (`@pgx-research-only`), and the reason
  the `.env.template` entry added by this session says so.

### 2.5 The AVI carve-out, stated exactly

> "**AVI Score**" means the AlphaGenome Variant Impact score … the AVI Score Feature Breakdown …
> **does not form part of AVI Score**. "AVI Score Feature Breakdown" means the breakdown showing
> features and inputs used to generate the AVI Score.

> AVI Scores and other artifacts that are made available for download within the "Permissive Use
> Downloadable Artifact" section … **may be used for commercial use and in connection with any
> commercial organisations**.

So: AVI scores → commercial-safe. SHAP feature importances → not. Merged splicing → not.

### 2.6 The four axes `SourceRow` cannot express

`SourceRow` carries `share_alike`, `commercial_use`, `redistribution` (recorded, not gated —
RM27 has not designed the axis) and `declared_use ∈ {unstated, non_commercial, commercial}`.
Against the Terms above, four things have no home:

**(a) Holder eligibility.** §2.1. `commercial_use=False` says "this may not be sold". It does not
say "a commercial entity may not hold this at all". The nearest existing precedent is PharmVar's
cache, which is unpublishable — but that is enforced by an *operator* rule (the key is personal),
not by a field a consumer can read.

**(b) The no-training restriction.** §2.4/4 is a field-of-use bar on a specific downstream
activity. There is no axis for it, and it is not a shade of `commercial_use`: a non-commercial
lab training a variant-effect model is in breach.

**(c) Revocability with a delete obligation.** §2.3. Principle 4 makes integrity identity and a
published module's digests are frozen; the repo has never carried a source that can compel
deletion of already-distributed derivatives. Every existing source's worst case is "stop
fetching".

**(d) Notice-must-travel, including a statement of modification.** §2.4/5. `SourceRow.notice`
exists and would carry the Output Terms notice, but the clause also demands notice **of the
modifications you make**, and a threshold slice is exactly such a modification. Whether
`notice` free text is the right home, or whether the modification belongs in `dataset`, is a
design question this document does not answer.

Two further shapes are recognisably *existing* gotchas rather than gaps:

**(e) Acquisition is gated where the read is not.** Downloading the AVI artifact requires the
eligibility of §2.1; *using* the downloaded AVI artifact commercially is expressly permitted.
That is `@acquisition-gate-is-not-a-read-gate` verbatim — `check_declared_use` gates a fetch, and
reading a snapshot the operator built is not one.

**(f) One source name, two licence classes.** `@write-the-sourcerow` keys a `SourceRow` on
`(source, layer)`. A module carrying both AVI scores and merged splicing scores under
`source="alphagenome"` would have one row for two incompatible licence classes. Whether that
forces two source names (`alphagenome_avi` / `alphagenome_splicing`) or a wider key is open.

### 2.7 The Output Terms of Use — read, and they change three things

Saved by the maintainer on 2026-09-10 as `docs/vendor/alphagenome_output_terms.pdf`
(`sha256 a12935888c9c39e5…`), **Effective: June 25, 2025**. It is the document §2.4/5 requires a
distributor to point downstream readers at, so it governs what someone who receives a derived
module may do with it.

**It predates the Atlas by fifteen months and carries no AVI carve-out.** Its opening is flat:

> The AlphaGenome API belongs to us. We make Output available free of charge, **for
> non-commercial use only**, in accordance with following use restrictions.

Its five Use restrictions mirror the Additional Terms' prohibitions 1, 4, 5, 6 and 7 almost
word for word, including the same carve-out — sharing with a commercial organization is barred
"aside from indirectly via a scientific publication, open source release or to support
journalism". What it does **not** have is the Permissive Use exception: that lives only in the
2026-09-08 Additional Terms, which state they govern where the two conflict, and whose
prohibition 5 exempts Permissive artifacts from the notice-and-Output-Terms requirement
altogether. So the AVI artifact is outside this document, and everything else is inside it.

Three things follow that the Additional Terms alone did not say:

**(a) The licence text must travel inside the artifact, not as a link.** Restriction 3b:

> If you provide additional or different terms and conditions for use, reproduction or
> distribution of Output or Derivatives, you must include **this "Use restrictions" section of
> these Terms as an enforceable provision** and provide clear notice to subsequent users that
> Output and Derivatives are subject to such use restrictions.

A module carries its own `sources.csv` terms, which is exactly "additional or different terms".
So a compiled module carrying AlphaGenome-derived data must **embed the Use restrictions text**.
The repo already has the machinery and the precedent: `SNAPSHOT_LICENSE_FILENAME` exists because
ClinPGx bundles a `LICENSE.txt` inside its archive and the builder extracts it so a holder of the
snapshot can read the terms without the archive (`@a-hosts-terms-are-not-its-contents-terms`).
This is the same shape with the requirement made explicit by the licensor.

**(b) Revocation is not limited to termination.** §2.3 read the Additional Terms' termination
clause; this one is broader and needs no termination at all:

> If you breach these Terms, Google reserves the right to request that you delete and cease use
> or sharing of Output or Derivatives in your possession or control. You agree to **immediately
> comply** with any such request.

**(c) The terms are pinned to the date the Output was generated**, which is the one clause that
helps rather than constrains:

> The version of these Terms that were effective on the date the relevant Output was generated
> will apply to your use of that Output.

So recording **when the bytes were produced** fixes which terms apply to them, permanently. That
turns the artifact's own timestamp into a legally load-bearing field rather than provenance
hygiene — the splicing and AVI files are stamped 2026-08-27, the SHAP file 2026-09-01 — and it is
the argument for `license_sha256` plus a recorded `dataset` date being the right pattern here
rather than a link to a live page. `licensing.py` already records both for exactly this reason.

One sign the document is a reused template rather than a bespoke one: its liability section
disclaims "**Structure predictions** provided by AlphaGenome", which is AlphaFold's language. It
does not weaken anything, but it is a reason to read it as the general API output licence it is
rather than as a considered statement about Atlas artifacts.

### 2.8 The document set, and what is still missing

Six documents are binding, by the Additional Terms' own first page. Four are now pinned in
`docs/vendor/`:

| document | version | in repo |
| --- | --- | --- |
| AlphaGenome Services Additional Terms of Service | Last modified 2026-09-08 | `alphagenome_additional_tos.pdf` + `.txt` |
| AlphaGenome Output Terms of Use | Effective 2025-06-25 | `alphagenome_output_terms.pdf` + `.txt` |
| Google APIs Terms of Service | Last modified 2021-11-09 | `google_apis_terms_of_service.md` |
| Google Terms of Service | Effective 2026-07-30 | `google_terms_of_service.pdf` + `.txt` |
| Google Generative AI Prohibited Use Policy | — | **missing** (incorporated by prohibition 8) |
| the website's "Permissive Use Downloadable Artifact" section | — | **missing** |

The second gap is the load-bearing one. **Nothing in the four pinned documents says which
artifacts are Permissive.** The Additional Terms define the class and grant it commercial use,
but they delegate membership to "the 'Permissive Use Downloadable Artifact' section of the
AlphaGenome Services website" — so §1's table, the single most consequential claim in this
document, rests on the maintainer's reading of a sign-in-gated page and cannot be verified from
the repo. That page, saved the way these four were, is the last thing this analysis needs.

A third document is owed by the *data* rather than by Google's terms: the SHAP artifact carries
an `ALPHAMISSENSE` column (§1.5), and AlphaMissense is a separate model with its own licence. A
module carrying that column stacks two sets of terms, not one.

---

## 3. The merged splicing corpus, measured

Aggregated from 24 per-contig passes over the complete file (~17 minutes wall, 12-way parallel
by contig). The per-contig outputs are on disk at
`/data/downloads/alphagenome/hist/<contig>.txt` and **the programs are Appendix A**, inlined
rather than left in a session scratchpad so they can be re-run unchanged against the AVI
artifact when it finishes downloading.

### 3.1 The distribution has a floor, not a tail

Bins are quarter-decades of `-log10(score)`, so the top row is `[0.562, 1)` and each row down is
the next quarter-decade toward zero.

| bin (score range) | rows | share |
| --- | ---: | ---: |
| ≥ 1 (off-scale, up to 5.799) | 22,633,144 | 0.577% |
| 0.562 – 1 | 26,489,642 | 0.675% |
| 0.316 – 0.562 | 48,816,986 | 1.244% |
| 0.178 – 0.316 | 88,612,929 | 2.258% |
| 0.100 – 0.178 | 167,461,791 | 4.267% |
| **0.056 – 0.100** | **1,041,514,138** | **26.538%** |
| **0.032 – 0.056** | **2,359,593,514** | **60.122%** |
| 0.018 – 0.032 | 147,066,299 | 3.747% |
| 0.010 – 0.018 | 9,738,426 | 0.248% |
| below 0.010 (20 further bins) | 12,747,582 | 0.325% |

**86.7% of the corpus is in two adjacent bins between 0.032 and 0.100**, and only 0.32% of rows
fall below 0.01 at all. The smallest value observed anywhere is above 10⁻⁶ and only 10 rows reach
that bin. There is no mass approaching zero to discard.

The practical reading: everything below ~0.1 is one undifferentiated background lump, and the
signal is the 4.75% above it. That makes the threshold choice easy but it also means **the
threshold is doing all the work** — there is no natural gap the data picks out for you.

### 3.2 Exceedance — the numbers a slice is chosen from

| threshold | rows kept | share of corpus |
| ---: | ---: | ---: |
| ≥ 0.01 | 3,902,188,443 | 99.427% |
| ≥ 0.02 | 3,583,347,875 | 91.303% |
| ≥ 0.05 | 408,709,233 | 10.414% |
| ≥ 0.1 | 186,552,701 | 4.753% |
| ≥ 0.2 | 85,537,292 | 2.180% |
| ≥ 0.3 | 52,478,818 | 1.337% |
| ≥ 0.5 | 26,777,898 | 0.682% |
| ≥ 1.0 | 9,761,281 | 0.249% |

Between 0.02 and 0.05 the corpus falls from 91% to 10%. That cliff is the background lump of
§3.1, and it is where any threshold argument will actually be had.

**One threshold is not an argument, because the source states it.** The splicing scoring
documentation says variants above **1.0** "generally exhibit substantial effects on splicing".
That is the bottom row of the table: 9,761,281 rows, 0.249% of the corpus, about **62 MB** as
parquet. A build that wants a defensible cut rather than a budget-driven one already has it.

**A caution about extrapolating from a sample:** a first pass over the leading 20 M rows (the 5′
end of `chr1`) gave ≥0.05 → 16.3% and ≥0.1 → 7.4%, against the whole-genome 10.4% and 4.8%. The
head of `chr1` is gene-dense and scores high; a slice sized from it would have been ~55% too
large.

### 3.3 Per contig

Rows, distinct positions, and the two thresholds that matter, sorted as the file is:

| contig | rows | positions | ≥0.1 | ≥0.5 | first pos | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chr1 | 344,221,512 | 114,740,504 | 18,794,870 | 2,709,506 | 65,409 | 5.731 |
| chr2 | 318,219,231 | 106,073,077 | 14,381,990 | 2,056,951 | 38,785 | 5.718 |
| chr3 | 297,576,552 | 99,192,184 | 12,033,889 | 1,716,275 | 196,737 | 5.675 |
| chr4 | 219,503,733 | 73,167,911 | 7,750,646 | 1,086,293 | 53,249 | 5.635 |
| chr5 | 213,847,131 | 71,282,377 | 8,554,598 | 1,191,969 | 92,161 | 5.751 |
| chr6 | 216,606,720 | 72,202,240 | 9,520,798 | 1,349,482 | 291,585 | 5.753 |
| chr7 | 233,344,368 | 77,781,456 | 9,064,261 | 1,289,057 | 192,513 | 5.620 |
| chr8 | 184,283,136 | 61,427,712 | 6,808,076 | 946,849 | 166,017 | 5.784 |
| chr9 | 156,433,656 | 52,144,552 | 7,910,879 | 1,114,499 | 14,465 | 5.749 |
| chr10 | 192,592,920 | 64,197,640 | 8,308,398 | 1,167,986 | 46,849 | 5.740 |
| chr11 | 196,735,392 | 65,578,464 | 10,326,069 | 1,506,114 | 167,681 | 5.756 |
| chr12 | 201,140,565 | 67,046,855 | 10,116,783 | 1,500,471 | 66,689 | 5.692 |
| chr13 | 99,530,640 | 33,176,880 | 3,666,302 | 509,131 | 19,173,761 | 5.559 |
| chr14 | 120,690,816 | 40,230,272 | 5,955,536 | 847,936 | 18,601,089 | 5.193 |
| chr15 | 130,616,439 | 43,538,813 | 6,656,368 | 952,921 | 20,531,841 | 5.799 |
| chr16 | 120,760,464 | 40,253,488 | 7,443,803 | 1,104,429 | 46,337 | 5.670 |
| chr17 | 135,784,704 | 45,261,568 | 10,108,191 | 1,505,648 | 137,473 | 5.757 |
| chr18 | 89,039,376 | 29,679,792 | 3,223,229 | 433,461 | 47,105 | 5.787 |
| chr19 | 100,511,232 | 33,503,744 | 9,589,773 | 1,444,883 | 107,009 | 5.645 |
| chr20 | 85,478,508 | 28,492,836 | 4,889,405 | 684,444 | 87,169 | 5.440 |
| chr21 | 41,268,855 | 13,756,285 | 2,015,161 | 279,121 | 10,521,473 | 4.748 |
| chr22 | 57,280,128 | 19,093,376 | 4,261,341 | 590,207 | 15,528,065 | 5.704 |
| chrX | 158,547,765 | 52,849,255 | 4,731,711 | 721,401 | 276,225 | 5.760 |
| chrY | 10,660,608 | 3,553,536 | 440,624 | 68,864 | 276,225 | 4.476 |

`chr19` is the outlier worth noticing: 2.6% of the corpus by rows but 5.1% of everything ≥0.1 —
9.5% of its own rows clear the threshold against a genome-wide 4.8%. It is the most gene-dense
chromosome, so a threshold slice is *not* uniform across the genome and a per-contig sanity check
belongs in whatever builds one.

---

## 4. What a slice would cost

### 4.1 Measured, not estimated

`chr22` (57,280,128 rows, 1.46% of the corpus) written with polars, zstd level 9, `chrom`/`ref`/
`alt` as categoricals and `pos` as `UInt32`:

| layout | rows | bytes | B/row |
| --- | ---: | ---: | ---: |
| long, `score` as `Float32` | 57,280,128 | 238,615,404 | 4.17 |
| long, `score` as `UInt16` ×10⁴ | 57,280,128 | 169,239,561 | 2.95 |
| long, `score` as `UInt16` ×10³ | 57,280,128 | 138,378,415 | 2.42 |
| **wide** — one row per position, three ALT columns, `UInt16` ×10⁴ | 19,093,376 | 140,384,691 | **2.45 per SNV** |
| long ≥0.05, `Float32` | 9,283,678 | 52,657,543 | 5.67 |
| long ≥0.1, `Float32` | 4,261,341 | 25,770,801 | 6.05 |
| long ≥0.2, `Float32` | 1,903,739 | 12,292,536 | 6.46 |
| long ≥0.5, `Float32` | 590,207 | 3,911,004 | 6.63 |
| long ≥1.0, `Float32` | 203,548 | 1,288,439 | 6.33 |

**Verbatim costs 11.4 GB, not 9.6.** `@verbatim-except-order` says to store a source's value as
the source states it, and the source states six decimals. The exactly-lossless encoding is
`UInt32` ×10⁶ in the wide layout: `chr22` at **165,849,495 bytes, 2.90 B/SNV → ≈11.4 GB**
genome-wide. The 9.6 GB figure below rounds to four decimals and is the *cheaper, lossy* option;
both are smaller than the 20.6 GB source, so the rule costs nothing here and the verbatim number
is the one an adoption item should quote.

Two things the table says that an estimate would not have. **Filtering makes each surviving row
more expensive** — 4.17 B/row unfiltered against 6.63 B/row at ≥0.5 — because a dense sorted
`pos` column delta-encodes almost to nothing and a sparse one does not. And **the score is the
whole payload**: `UInt16` at 10⁻⁴ precision loses nothing that matters (the maximum observed
value, 5.799, scales to 57,990, inside `UInt16`) and takes 29% off the file.

### 4.2 The conclusion the arithmetic forces

Scaling `chr22`'s bytes-per-row to the full 3,924,674,451 rows:

| what you keep | rows | parquet |
| --- | ---: | ---: |
| **everything**, wide, `UInt32` ×10⁶ — *verbatim, lossless* | 3,924,674,451 | **≈ 11.4 GB** |
| everything, wide, `UInt16` ×10⁴ (lossy at the 5th decimal) | 3,924,674,451 | ≈ 9.6 GB |
| everything, long, `UInt16` ×10⁴ | 3,924,674,451 | ≈ 11.6 GB |
| everything, long, `Float32` | 3,924,674,451 | ≈ 16.4 GB |
| ≥0.05 | 408,709,233 | ≈ 2.3 GB |
| ≥0.1 | 186,552,701 | ≈ 1.1 GB |
| ≥0.2 | 85,537,292 | ≈ 0.55 GB |
| ≥0.5 | 26,777,898 | ≈ 0.18 GB |
| ≥1.0 — *the threshold the source itself names* | 9,761,281 | ≈ 0.062 GB |

**The 40 GB budget is not binding, and neither is the size question.** The entire 20.6 GB
artifact re-encoded **without losing a digit** is about 11.4 GB — smaller than the source,
without discarding a single row. There is no need to choose a threshold to fit a size, which
removes the only forcing argument for one.

That inverts the design question. It is no longer "which slice fits" but "**what is the annotation
for?**" — and the answers differ:

- **Every row, no threshold** (~9.6 GB) is a *lookup table*: any SNV in the covered 42% gets an
  answer, and absent-means-unscored stays honest. It is also the only shape that can serve a
  query about a variant nobody flagged in advance.
- **A threshold slice** (~1 GB at ≥0.1) is a *finding list*: it answers "is this variant
  notable?" and cannot answer "what is the score here?", because a missing row now means two
  things — unscored, or scored and below threshold. That collision is the `@unreachable-not-absent`
  failure in a new costume, and any threshold build has to record its own threshold in the
  artifact or the ambiguity is unrecoverable.

Neither is chosen here.

### 4.3 What the sizing does not cover

**Everything in §3 and §4 is the 20.6 GB merged-splicing artifact and nothing else.** The
~11.4 GB verbatim figure, the 3,924,674,451 rows, the exceedance table and every bytes-per-row
number are that corpus. They are **not** AVI's.

AVI is a different corpus, not a bigger one: 88.5 GB of source, a **signed** `raw_score` plus a
derived `PHRED` (§1.3), and rows that begin at `chr1:10001` rather than 65,409 — so it is
plausibly genome-wide at ~9.3 billion rows, 2.4× the splicing count, and its own measurement is
running (§1.4). SHAP (283.9 GB) is a feature *breakdown* with a wholly different row shape and
none of this arithmetic reaches it either. `@probe-names-the-table`: a negative or a positive
finding about "the source" is only as wide as the table it was taken from.

---

### 4.4 AVI triage: `PHRED` is a size dial, exactly

This is the 2D size × rarity × effect surface projected onto one axis — and the projection turns
out to be degenerate in a way that is worth knowing before anyone designs against it.

#### 4.4.1 The histogram carries no information, because it *is* the transform

`PHRED = -10 log10(1 - q)` with `q` a rank, so if the ranking is over the corpus itself then
`PHRED ≥ p` keeps exactly `10^(-p/10)` of the rows. Measured against all 8,812,917,339:

| threshold | rows kept | observed | `10^(-p/10)` | ratio |
| --- | ---: | ---: | ---: | ---: |
| ≥ 1 | 7,000,282,021 | 79.4321% | 79.4328% | 0.99999 |
| ≥ 5 | 2,786,658,500 | 31.6202% | 31.6228% | 0.99992 |
| ≥ 10 | 881,307,226 | 10.0002% | 10.0000% | 1.00002 |
| ≥ 15 | 278,594,125 | 3.1612% | 3.1623% | 0.99966 |
| ≥ 20 | 88,119,754 | 0.9999% | 1.0000% | 0.99990 |
| ≥ 25 | 27,854,420 | 0.3161% | 0.3162% | 0.99960 |
| ≥ 30 | 8,812,976 | 0.1000% | 0.1000% | 1.00000 |
| ≥ 40 | 882,484 | 0.0100% | 0.0100% | 1.00000 |

**Four significant figures across four orders of magnitude.** `PHRED` in this artifact is the
variant's exact percentile rank among all possible human SNVs, and nothing else. Two consequences:

- **A `PHRED` histogram is a straight line in log space and tells you nothing about the data.**
  Any threshold selects a predetermined fraction. There is no shoulder to find, no natural cut, no
  "most variants are negligible" to discover — that shape was assigned by the transform, not
  measured from biology.
- **Choosing a `PHRED` threshold is identical to choosing a dataset size**, which makes it an
  unusually honest dial: state the budget, read off the cut. It is the *opposite* of the splicing
  file, where §3.2's cliff between 0.02 and 0.05 was real structure.

It also contradicts the upstream FAQ, which describes the quantile background as ~300 K **common**
variants (MAF > 0.01 in gnomAD v3). An all-possible-SNV corpus scored against a common-variant
background would be shifted upward, visibly and by a lot. It is not shifted at all. So the FAQ
describes the API's `quantile_score` for the recommended per-modality scorers, and the AVI
artifact's `PHRED` is calibrated on something corpus-shaped instead. **Whatever the mechanism, the
practical point stands: `PHRED` is not a rarity comparison, so it cannot stand in for the missing
allele-frequency axis of §5.**

#### 4.4.2 Where the information actually is

`raw_score`, and it is not degenerate: §1.4's magnitude histogram is a lognormal-ish hump peaking
at 0.032–0.056 with 20.5% of rows in that one quarter-decade, and it is **signed**, with 49.30%
negative. The sign is the half of the corpus a rank transform necessarily discards — every row
above `PHRED` 5 is positive, and at `PHRED ≥ 1` still 36.17% are negative, so the negatives are
compressed into the bottom of the scale where a threshold cannot distinguish them.

**A triage that thresholds on `PHRED` therefore throws away every negative-scored variant**, which
is a design decision rather than a filter, and one nothing in the column names warns you about.

*Negative-scored*, deliberately, not *down-regulating*: `AVI_SCORE` is **not** among the seven
scorers the Atlas metadata marks `is_signed`, and its quantile is [0, 1) rather than the [−1, 1]
the FAQ describes for signed ones. So the calibration treats the score as unsigned and negatives
simply rank lowest; what a negative *means* — a direction, or sub-baseline noise — is not
something the published metadata says. Reading direction into it would be
`@field-description-is-a-claim`: an interpretation asserted where the source states none.

#### 4.4.3 Dataset size at each cut

Measured on `chr22` (117,479,331 rows) and scaled by the genome-wide row counts above. The float
column was measured as `Float64` — mislabelled `f32` in an earlier draft of this table, and
`Float32` is barely cheaper (67.9 GB against 69.0 GB) for the reason §4.5 gives. `both int`
stores `raw_score` and `PHRED` as scaled integers at the source's own decimal places; `raw only`
drops `PHRED` entirely, which is defensible precisely because §4.4.1 shows it is a rank the
threshold already encodes.

| threshold | rows | % corpus | both `f64` | both int | `raw_score` only |
| --- | ---: | ---: | ---: | ---: | ---: |
| all | 8,812,917,339 | 100% | 69.0 GB | 59.1 GB | **34.4 GB** |
| ≥ 1 | 7,000,282,021 | 79.43% | 56.3 GB | 46.5 GB | 27.9 GB |
| ≥ 5 | 2,786,658,500 | 31.62% | 22.8 GB | 18.5 GB | 12.5 GB |
| ≥ 10 | 881,307,226 | 10.00% | 6.7 GB | 5.7 GB | 3.9 GB |
| ≥ 15 | 278,594,125 | 3.16% | 2.1 GB | 1.8 GB | 1.2 GB |
| ≥ 20 | 88,119,754 | 1.00% | 662 MB | 550 MB | 387 MB |
| ≥ 25 | 27,854,420 | 0.32% | 201 MB | 168 MB | 127 MB |
| ≥ 30 | 8,812,976 | 0.10% | 70 MB | 61 MB | 48 MB |
| ≥ 40 | 882,484 | 0.01% | 7 MB | 6 MB | 5 MB |

**AVI still fits whole, but only one way.** With both columns it is 69 GB as parquet against the
splicing file's 11.4 GB — 2.25× the rows and two columns instead of one — so a both-column build
needs a cut somewhere between `PHRED ≥ 1` and `≥ 5` to reach 40 GB. Keeping **`raw_score` alone**
is **34.4 GB for every row**, inside the budget with the sign intact and nothing discarded. And
dropping `PHRED` costs nothing that cannot be rebuilt: §4.4.1 shows it is the rank, so a holder of
the complete `raw_score` column can recompute it exactly.

Three cuts worth naming, none chosen here:

- **`PHRED ≥ 10` — 6.7 GB, 881 M rows, the top decile.** Comparable in size to the caches this
  repo already provisions, and a round number a consumer can reason about.
- **`PHRED ≥ 20` — 662 MB, 88 M rows, the top percentile.** Small enough to ship anywhere, and
  still 30× more variants than ClinVar carries in total.
- **Everything, `raw_score` only, 34.4 GB.** Keeps the sign and every row, inside the stated
  budget, and lets a consumer compute their own rank because §4.4.1 shows `PHRED` is recoverable
  from the ranking they would then hold.

The same collision as §4.2 applies and is worse here: at any threshold a missing row means either
"not scored" or "scored below the cut", and AVI writes **672,931 exact zeros**, so `0.0` cannot be
the sentinel either. A thresholded AVI artifact must record its own threshold or the ambiguity is
unrecoverable.

### 4.5 Where the bytes are, and why tabix is competitive

The 88.5 GB artifact re-encodes to 69 GB, which is a 22% saving and not the order-of-magnitude one
a columnar format usually gives. Decomposed on `chr22` (117,479,331 rows) and scaled:

| representation | B/row | genome-wide |
| --- | ---: | ---: |
| uncompressed TSV | 35.17 | 310 GB |
| **published `.tsv.gz`** (bgzip) | **10.04** | **88.5 GB** |
| parquet + zstd-9, key + both `f64` | 7.83 | 69.0 GB |
| parquet + zstd-9, key + both `f32` | 7.70 | 67.9 GB |
| parquet + zstd-9, key + `raw` as `int32`×10⁵ | 3.90 | 34.4 GB |

Per column, written in isolation:

| column | B/row | genome-wide |
| --- | ---: | ---: |
| `chrom` (categorical) | 0.002 | 0.02 GB |
| `pos` (`UInt32`) | 1.25 | 11.0 GB |
| `ref` + `alt` (categorical) | 0.24 | 2.1 GB |
| `raw_score` as `Float32` | 3.15 | 27.8 GB |
| `raw_score` as `Float64` | 2.94 | 25.9 GB |
| **`raw_score` as `Int32`×10⁵** | **2.41** | **21.3 GB** |
| `PHRED` as `Float32` | 3.06 | 26.9 GB |
| `PHRED` as `Float64` | 3.40 | 29.9 GB |

**There is no container overhead to find.** bgzip's block headers are ~18 bytes per 64 KB (0.03%)
and the `.tbi` index is 3.2 MB against 88.5 GB. The gap is not tabix being wasteful; it is that
**the two float columns are 80% of the parquet** (54.7 of 67.9 GB) and they are nearly
incompressible in either format.

The reason text holds up so well is precision. §4.5.1 measures it: `raw_score` is printed to **four
significant digits** and `PHRED` to **six**, so a decimal row carries only the digits that exist,
and DEFLATE squeezes the rest — the repeated `chrom`, the near-constant leading digits of `POS`,
the tab structure. An IEEE float, by contrast, stores a full 24- or 53-bit mantissa whose low bits
are noise the source never had, and noise does not compress. That is the whole 22%.

It is also why `Float64` beat `Float32` on `raw_score` (2.94 against 3.15 B/row): the `f64`
representation of a 4-significant-digit decimal has long runs of zero mantissa bits, while the
`f32` rounding scatters them. And it is why quantising to the source's real precision wins
outright — **`Int32`×10⁵ at 2.41 B/row is 23% under `Float32`**, because it stores exactly the
information the file contains and nothing else.

#### 4.5.1 The two columns are not published at the same precision

Measured over 2,000,000 `chr22` rows, counting significant digits:

| column | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `raw_score` | 0.5% | 3.4% | 20.3% | **75.7%** | — | — | — |
| `PHRED` | — | 0.1% | 0.8% | 5.0% | 24.7% | **66.5%** | 2.8% |

`PHRED` is published at roughly **100× the resolution of `raw_score`**, which is the fact §4.6
turns on.

### 4.6 Can `PHRED` be dropped and recomputed? Not exactly, and the reason is not floating point

§4.4.1 shows `PHRED` is a rank, so it is a **monotone function of `raw_score`** — confirmed
directly: over `chr22`'s 40,204 distinct `raw_score` values sorted ascending, `PHRED` has **zero
negative steps**. There is one 1-D curve, not a per-variant computation, and it is not a closed
form either: it is an empirical quantile function, so reconstruction means carrying the curve (tens
of thousands of knots, a few hundred KB) rather than a formula.

Tested as asked. The curve was built from `chr22` (mean `PHRED` per distinct `raw_score`) and
applied to three disjoint regions:

| region | rows | `raw` unseen | mean \|Δ\| | p99 \|Δ\| | max \|Δ\| | Σ\|Δ\| | ε·N |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chr21:20–30 Mb | 29,999,886 | 0.000% | 0.000026 | 0.000307 | 0.000356 | 764.9 | 6.7e-09 |
| chr1:1–6 Mb | 14,869,476 | 0.001% | 0.000022 | 0.000302 | 0.000356 | 321.7 | 3.3e-09 |
| chr7:50–55 Mb | 15,000,003 | 0.000% | 0.000025 | 0.000307 | 0.000356 | 369.2 | 3.3e-09 |

**The `ε·N` test fails by about eleven orders of magnitude**, and the cause is not float error. It
is §4.5.1: the file rounds `raw_score` to four significant digits while computing `PHRED` from the
unrounded value, so **2,001 of `chr22`'s 40,204 distinct `raw_score` values carry more than one
`PHRED`** — up to **68 distinct values** behind a single printed `raw_score`. The residual is that
rounding, and it is bounded: `max |Δ| = 3.56e-4` everywhere tested.

So the answer splits by use:

- **For triage, it is exact.** Across 59.9 M rows in three regions, thresholding on the
  reconstructed value reclassified **zero rows** at `PHRED ≥ 10` and **zero** at `≥ 20`. If the
  column's job is to pick a slice, dropping it costs nothing measurable.
- **For reporting a rank, it is lossy.** `PHRED` is the finer of the two published columns, so
  "drop it and recompute" trades the artifact's highest-resolution field for its coarsest. A
  consumer quoting a variant's percentile should keep it.

The honest framing is therefore the reverse of the intuition: it is not that `PHRED` is redundant
given `raw_score`; it is that **`raw_score` is published too coarsely to regenerate `PHRED`**, and
the 34.4 GB `raw_score`-only build in §4.4.3 buys its size by accepting a 3.6e-4 rank error that no
threshold can see.

### 4.7 What the score means, and what a negative one is

`AVI` is an **impact score, not a direction**. The Atlas exposes the model's own inputs and
attributions as two more scorers — `AVI_SCORE_MODEL_FEATURES` and `AVI_SCORE_FEATURE_IMPORTANCE`,
18 values each — and they are the SHAP artifact's 18 columns in order. Confirmed rather than
assumed: feature 0 came back as 4.0252 and 0.0345 at two `chr22` loci where the splicing artifact
independently says **4.025** and **0.03451**, and as 0.0 at a locus the splicing file does not
cover at all — which is §1.5's zero-means-unscored finding arriving from the other side.

Three variants, queried live:

| | chr22:11249481 T>C | chr22:30000581 G>A | chr22:30339156 C>A |
| --- | ---: | ---: | ---: |
| **`AVI_SCORE`** | **−1.2592** | **−0.6592** | **+4.6258** |
| `MERGED_SPLICING` | 0.0 | 0.0345 | 4.0252 |
| `ALPHAMISSENSE` | `nan` | `nan` | 0.9241 |
| **`CACTUS_241_WAY`** | **−20.0** | **−11.507** | **+8.898** |
| `PROTEIN_TERMINATION` | 0.0 | 0.0 | 1.0 |
| `PHASTCONS_470_WAY` | 0.0 | 0.0 | 1.0 |
| *importance of* `CACTUS_241_WAY` | **−1.2258** | **−0.7049** | +0.6146 |
| *importance of* `PROTEIN_TERMINATION` | 0.0 | 0.0 | **1.6255** |
| *importance of* `MERGED_SPLICING` | 0.0 | 0.0103 | 1.2895 |

**A negative AVI is conservation, not direction.** In both negative cases essentially the whole
score is one feature: `CACTUS_241_WAY`, the 241-way comparative-genomics score, which is itself
signed and strongly negative — sites evolving *faster* than neutral expectation. Its attribution is
−1.226 and −0.705, and every other feature contributes near zero. So a negative `AVI` reads as
**evidence against functional impact**: the site looks less constrained than baseline. It does not
mean down-regulation, and there is no expression direction anywhere in the feature set — the nine
regulatory features are all `MAX_ABS_*`, magnitudes with the sign already discarded before the
model sees them.

The positive extreme decomposes the way a deleteriousness score should: a stop-gain
(`PROTEIN_TERMINATION` 1.0, the largest single attribution at 1.63), a strong splicing effect
(4.03, attribution 1.29), a high AlphaMissense score (0.92, attribution 0.83) and positive
conservation.

**So the axis is closer to benign ↔ damaging than to down ↔ up**, with the caveat §4.4.2 already
states: the Atlas does not mark `AVI_SCORE` as `is_signed`, so this reading comes from the feature
attributions rather than from a declared semantics. `ALPHAMISSENSE` being `nan` on both non-coding
variants is worth noting separately — the feature vector carries a genuine missing value, not a
zero, so at least one input distinguishes *unmeasured* from *zero* even though `MERGED_SPLICING`
does not.

### 4.7.1 The lost precision exists — on the API, not in any file

The 3.56e-4 residual of §4.6 is a **publishing artefact of the TSV**, not a property of the model.
The Atlas returns `raw_score` as a `float32`, roughly **seven significant digits** against the
file's four, and that is precisely the information the reconstruction is missing.

Tested where it matters — the `raw_score = 0.00076` atom that causes every threshold-3 flip in
§4.8.1. Six rows the file cannot tell apart:

| variant | file `raw` | **API `raw`** | file `PHRED` | `PHRED` derived from API `raw` | Δ |
| --- | ---: | ---: | ---: | ---: | ---: |
| chr22:10535072 A>C | 0.00076 | **0.000758832** | 2.99986 | 2.99986 | **0.00000** |
| chr22:10513191 G>T | 0.00076 | **0.000759043** | 2.99987 | 2.99987 | **0.00000** |
| chr22:10537946 C>G | 0.00076 | **0.000759331** | 2.99989 | 2.99989 | **0.00000** |
| chr22:10553451 T>G | 0.00076 | **0.000761419** | 3.00003 | 3.00003 | **0.00000** |
| chr22:10513734 C>T | 0.00076 | **0.000761990** | 3.00007 | 3.00007 | **0.00000** |
| chr22:10520436 G>A | 0.00076 | **0.000764675** | 3.00025 | 3.00025 | **0.00000** |

Sorted by the API's `raw_score`, the file's `PHRED` is **perfectly monotone**. The tie is not a tie
in the model; it is six distinct values printed to four significant digits. With the API's
precision the derived `PHRED` reproduces the published column **exactly at its full five decimals**
for all six.

**So each surface is more precise than the other, in a different place.** The API wins on
`raw_score`, everywhere — seven digits against four. The file wins on `PHRED` above 72.247, where
§6.3 showed the API's `float32` quantile saturates at exactly 1.0 while the file still carries
values to 89.451. Neither is a superset of the other, which is `@two-surfaces-two-denominators`
stated as sharply as it can be: **there is no single surface that carries the artifact at full
fidelity.**

**No other download helps.** The splicing artifact publishes its own score at the same four
significant digits, and the SHAP artifact carries the eighteen model *features* — also at four —
and **no AVI score column at all**. Its `AVI_SCORE_FEATURE_IMPORTANCE` sibling, which does sum to
the score, exists only as an Atlas scorer and not as a file.

The practical consequence is a two-stage shape rather than a choice: build the bulk artifact from
the download, and **refine a shortlist through the API** where the fourth digit is load-bearing.
§4.8.1's rule says exactly when that is — a threshold falling inside a knot's span — so the refine
step is targetable rather than blanket, and at 161 ms per variant a few thousand rows is minutes.

### 4.7.2 Rebuilding the column from the API is not viable — and not necessary

**The whole column, by API.** 8,812,917,339 variants. The interval RPC measured at **375
variants/s** (600 in 1.6 s, the SDK's default 10 workers), which is **23.5 million seconds — 272
days** of continuous querying, in roughly **92 million RPCs**. Single-variant calls at 161 ms
serial would be **45 years**. Even the 14.2% of rows that sit on an ambiguous knot (~1.25 billion
genome-wide) is 39 days. None of these are engineering problems; they are answers.

They are also the wrong question, and the Terms make that explicit: prohibition 3 bars anyone from
"reverse engineer, disassemble, republish, copy, modify, distribute" the Services, the licence is
**revocable** (§2.3), and credentials are personal (§2.4/7a). Reconstructing a published artifact
through 92 million calls on a personal key is the shape of thing that ends a key, and the artifact
is a download.

**What is actually needed is 502 KB and no calls at all.** The `raw_score` value set is not open —
four-significant-digit printing makes it a fixed grid, and it **saturates immediately**:

| corpus scanned | distinct `raw_score` | ambiguous knots | widest span |
| --- | ---: | ---: | ---: |
| chr22 | 40,204 | **2,001** | 0.000700 |
| + chr21 | 40,546 | **2,001** | 0.000700 |
| + chr20 20–40 Mb | 40,655 | **2,001** | 0.000700 |
| + chr19 20–40 Mb | 40,742 | **2,001** | 0.000700 |
| + chr1 20–40 Mb | 40,858 | **2,001** | 0.000700 |
| + chr7 20–40 Mb | **40,888** | **2,001** | 0.000700 |

Roughly 400 million rows scanned and the knot set grew **1.7%** past what one chromosome already
showed, while the ambiguous count and the widest span did not move at all. The ambiguity structure
is **global, small, and enumerable**.

So ship the knots. A table of `(raw_score, phred_lo, phred_hi, n)` over ~41,000 rows is
**501,592 bytes** as parquet — **381,432** without the counts. It carries three things at once:

- **the reconstruction curve**, exactly, so `PHRED` need not be stored (§4.6);
- **the ambiguity bounds per knot**, so an ambiguous row reports the interval
  `[phred_lo, phred_hi]` rather than a point — which is the house answer rather than a workaround
  (`@tri-state-is-the-house-algebra`: withhold where the answer is not determined);
- **threshold safety, decidable in advance** (§4.8.1) — scan 41,000 rows, not 8.8 billion.

The API refinement of §4.7.1 then shrinks to a genuine last resort: only rows on a knot that
straddles the specific threshold in use. At threshold 3 that is ~633,000 rows genome-wide; at every
other integer threshold from 1 to 50 it is **zero**. And even those need querying only if a caller
insists on a point estimate where the data supports an interval.

### 4.7.3 Corrections from the build — four numbers in this document were wrong

RM191–RM193 were built against §§4.4–4.9 on 2026-09-10, and building them refuted four things
written above. Each is corrected in place; this section records what moved and why, because the
pattern is the one the whole document keeps hitting — a measurement taken one way, generalised one
step too far.

#### `34.4 GB` is a **writer setting**, not a property of the schema

§4.9's whole-row figure came from `write_parquet` with polars' default row-group size. The shipped
builder writes 1,000,000-row groups, and that alone costs **22%**. Re-measured on a 30 M-row
`chr22` slice, same schema, same `zstd-9`:

| row groups | B/row | genome-wide |
| --- | ---: | ---: |
| polars default | 3.963 | **34.9 GB** |
| `row_group_size=1_000_000` | 4.835 | **42.6 GB** |

Almost all of the difference is `pos`: **1.250 B/row standalone against 2.067 in the shipped
file**, because a smaller row group truncates the delta-encoding run that a sorted position column
depends on. So the artifact's size is set by a knob nobody named, and "34.4 GB" was only ever true
of the default. **Both numbers are right about different files** — the tradeoff is size against
random-access granularity, which is a real choice and now an item (RM197).

#### "Exactly lossless" is true of the encoding and **not** of the obvious way to decode it

`Int32`×10⁵ is exact for the printed decimal: over 200,000 sampled values, `Decimal(printed)`
scaled by 10⁵ round-trips with **zero** disagreements. But the natural decode does not:

| how the decimal is recovered | disagrees with `float(printed)` |
| --- | ---: |
| Python `e5 / 100000` (true division) | **0 / 200,000** |
| **polars `pl.col("e5") / 100000`** | **3,165,111 / 6,000,003 — 52.75%** |
| polars `pl.col("e5") * 1e-5` | 3,165,111 — **the identical rows** |
| polars `Float32` division | 5,995,703 — 99.93% |

The two polars results being *bit-identical in count* is the tell: **polars compiles the division
into a multiplication by the reciprocal**, and `1e-5` is not exactly representable, so the product
is rounded twice and lands one ULP off on half the corpus. IEEE division is correctly rounded and
Python's is exact; the vectorised path is not the same operation.

The differences are invisible at `repr` — `0.00114` prints as `0.00114` either way — so nothing
warns. **The remedy is not a tolerance: threshold and compare in the integer domain**, where the
values are exact by construction. A consumer that needs the decimal should be told the scale, not
handed a float.

#### The interval RPC's refusal was `Strand`, not the field mask

§6.5 attributed the hand-built `ListDenseVariantScores` failure to a missing `x-goog-fieldmask`
header and 32 bp chunking, on the evidence that the SDK sends both. Wrong on both counts, and the
real cause is a proto3 trap:

```
Strand: STRAND_UNSPECIFIED=0, STRAND_POSITIVE=1, STRAND_NEGATIVE=2, STRAND_UNSTRANDED=3
```

**There is no meaningful zero.** An `Interval` that omits `strand` therefore carries
`STRAND_UNSPECIFIED`, which the server rejects — as a bare `INVALID_ARGUMENT` naming no field.
Verified directly on the two-package tier:

| request | result |
| --- | --- |
| `strand` omitted (proto3 default `0`) | `INVALID_ARGUMENT: Request contains an invalid argument.` |
| `strand=STRAND_UNSTRANDED` | **OK, 96 variants, no next page** |

The field mask is optional (the same answer comes back without it) and 32 bp chunking is not
required — 128 bp answers in one call. A *filter* is effectively required, but for a different
reason than §6.5 gave: an unfiltered 32 bp request is a **43 MB** message against a 4 MB limit.

**A proto3 enum whose zero is a sentinel makes "field absent" and "field invalid" the same wire
state**, and a server that validates it can only answer with a message that names nothing. Worth
remembering wherever generated bindings are hand-driven.

#### The straddling knot is 676,356 rows, not ~633,000

§4.7.2 scaled `chr22`'s 8,443 rows to a genome-wide estimate. The committed knot table has the
real number, and it confirms the shape exactly — **one** knot straddles any integer threshold from
1 to 50:

| `raw_score` | rows | `phred_lo` | `phred_hi` |
| ---: | ---: | ---: | ---: |
| **0.00076** | **676,356** | 2.99961 | 3.00027 |

An estimate where the artifact carries the count is the smallest version of this document's
recurring mistake, and it is the one that had a table sitting next to it the whole time.

#### One silent trap, found by a test that asserted a positive

`VariantRow` normalizes `chrom` to `22`; the artifact ships `chr22`. Joining one onto the other
**matched nothing and raised nothing** — every variant came back "absent from the snapshot", which
is indistinguishable from a genuinely uncovered region, and AVI covers only ~95% of the assembly
so that answer is plausible. It was caught only because the test asserted a *positive* match count
rather than the absence of an exception.

A join key that silently produces the corpus's own legitimate answer is worse than one that
crashes. Assert a positive.

### 4.8 Does the 3.6e-4 residual actually rerank anything?

Three questions, measured on a 36 M-row `chr21` slice against a curve built from `chr22`.

#### 4.8.1 Threshold flips are rare, lumpy, and predictable

| threshold | selected (true) | rows flipped | flipped / selected |
| ---: | ---: | ---: | ---: |
| 1 | 26,626,452 | **0** | — |
| **3** | 15,167,587 | **1,218** | 8.0e-05 |
| 5 | 8,737,261 | **0** | — |
| 10 | 2,252,898 | **0** | — |
| 15 / 20 / 25 / 30 / 35 / 40 / 45 / 50 | … | **0** | — |

A smooth model predicts a few thousand flips at low thresholds and fractions of a row above 40.
The truth is nothing at all everywhere except **one threshold**, where 1,218 rows move at once —
and the diagnosis is exact: **every one of those flips comes from a single printed `raw_score`.**

`raw_score = 0.00076` appears 8,443 times on `chr22` and spans `PHRED` **2.99961 – 3.00027**. It
straddles 3.0. The curve's mean for that knot is 2.999939, a hair below, so every row behind it
reconstructs below the threshold and the ones truly at or above 3.0 flip together.

That gives a **decidable rule** rather than an error bar. A knot is a printed `raw_score`; 2,001 of
`chr22`'s 40,204 knots (4.98%) span more than one `PHRED`, and the **widest span is 0.000700**. A
threshold is unsafe **iff it falls inside a knot's span**, which is checkable in advance against
the curve — and across all fifty integer thresholds from 1 to 50, **exactly one is unsafe**. The
"sharp 50" case the question raises is safe: no knot goes near it, and at that end the corpus is so
thin (107 rows ≥ 50 in the whole slice) that atoms cannot form.

So the remedy is not a tolerance, it is a lookup: build the curve, list the knots straddling your
threshold, and either nudge the threshold off the atom or read those rows from the stored column.

#### 4.8.2 Rounding does not mend it — it makes the worst case worse

| rounding grid | identical after rounding | **max residual** | flips at 10/20/30 |
| --- | ---: | ---: | ---: |
| none | 85.34% | **3.56e-4** | 0 |
| 1e-5 | 85.34% | 3.60e-4 | 0 |
| 1e-4 | 86.60% | 4.00e-4 | 0 |
| **1e-3** | 97.43% | **1.00e-3** | 0 |
| 1e-2 | 99.71% | 1.00e-2 | 0 |

Rounding to 10⁻³ makes 97% of rows compare equal, which looks like a fix and is not one: **the
worst case rises from 3.6e-4 to 1.0e-3**, because two values 3.6e-4 apart can land on opposite
sides of a grid line and be pushed a full step apart. Rounding buys agreement in the common case by
making the rare case worse — the opposite of what a tolerance should do. It also cannot recover
what §4.5.1 lost: the information is gone from `raw_score`'s fourth significant digit, and no
post-hoc grid puts it back.

#### 4.8.3 Reranking is pervasive but microscopic

| | |
| --- | --- |
| rows whose rank changes at all | **15.74%** |
| mean rank shift | 143 places |
| p99 rank shift | 2,053 places |
| **max rank shift** | **3,168 places** (of 36 M) |

One row in six moves, so "the ordering is preserved" is false. But the largest move anywhere is
3,168 places out of 35,999,777 — **0.0088 of a percentile**. No variant can cross another that is
meaningfully different from it; the churn is entirely inside ties that `raw_score`'s rounding
created. For a ranked shortlist of any practical length the reconstruction and the stored column
give the same answer, and §4.8.1's rule covers the one case where they do not.

### 4.9 Storing the noise-carriers as integers

The floats are 80% of the parquet (§4.5) and their low mantissa bits are noise the source never
had. Both columns are printed to **at most 5 decimals** — measured over all 117 M `chr22` rows,
`raw_score` 70.2% at 5 decimals and `PHRED` 90.2%, neither ever more — so `Int32`×10⁵ is **exactly
lossless** for both (`raw` reaches 608,100 and `PHRED` 8,945,120, both far inside `Int32`).

| encoding | B/row | genome-wide | lossless? |
| --- | ---: | ---: | --- |
| `raw` `Float32` | 3.154 | 27.8 GB | no — rounds the 5th decimal |
| `raw` `Float64` | 2.943 | 25.9 GB | yes |
| **`raw` `Int32`×10⁵** | **2.413** | **21.3 GB** | **yes** |
| `raw` dictionary code `UInt32` | 2.342 | 20.6 GB | yes |
| `raw` `Int32`×10⁴ | 1.841 | 16.2 GB | **no** — 70% of values have 5 decimals |
| `PHRED` `Float32` | 3.056 | 26.9 GB | no |
| `PHRED` `Float64` | 3.397 | 29.9 GB | yes |
| **`PHRED` `Int32`×10⁵** | **2.808** | **24.8 GB** | **yes** |
| `PHRED` `Int32`×10³ | 1.972 | 17.4 GB | no |

And whole rows:

| layout | B/row | genome-wide |
| --- | ---: | ---: |
| key + both `Float32` | 7.700 | 67.9 GB |
| **key + both `Int32`×10⁵** | **6.711** | **59.2 GB** |
| key + `raw` `Int32`×10⁵ | 3.903 | 34.4 GB |
| key + `raw` dictionary code | 3.828 | 33.7 GB |

**Integer packing is a 13% saving at zero information cost** — it is strictly better than
`Float32`, which is both larger *and* lossy here. The dictionary code is marginally smaller again
(chr22 has only 40,204 distinct `raw_score` values, a consequence of the 4-significant-digit
printing), but parquet already dictionary-encodes internally, which is why the gain over `Int32` is
only 3%; an explicit dictionary would have to travel with the artifact to be decodable, so it buys
little for a real cost.

#### 4.9.1 Sixteen bits does not suffice — but the bit-width is not why

`PHRED` reaches 89.45, so at 5 decimals it needs 8,945,120 codes and `Int32` is forced. The
interesting question is the rescaled one: give up the decimals, spread 65,536 codes across the
range, and take the precision hit. Measured on the same 36 M-row slice, against the *free* option
of not storing the column at all and reconstructing it from `raw_score` (§4.6):

| how `PHRED` is carried | size | genome-wide | max \|err\| | threshold flips |
| --- | ---: | ---: | ---: | ---: |
| `Int32`×10⁵, stored | 2.804 B/row | 24.7 GB | **0** | **0** |
| `UInt16`×655.35, rescaled | 1.846 B/row | 16.3 GB | 7.63e-4 | 6,615 |
| `UInt16`×700, rescaled | 1.869 B/row | 16.5 GB | 7.14e-4 | 10,513 |
| **not stored — rebuilt from `raw_score`** | **0** | **0 GB** | **3.56e-4** | **1,218** |

*(flips summed over thresholds 1, 3, 5, 10, 15, 20, 25, 30, 40, 50)*

**A rescaled `UInt16` is strictly dominated.** It costs 16.3 GB to be **twice as inaccurate and
five times as flip-prone** as storing nothing at all. There is no operating point at which it is
the right answer: if exactness matters, `Int32`×10⁵ is the only choice; if it does not, the column
is free to drop and the reconstruction is better than any 16-bit code.

The arithmetic says this is not a tuning problem. To beat the reconstruction's 3.56e-4 a uniform
code needs a scale of at least **1,404**, which puts the top of the range at **125,632** — nearly
twice what `UInt16` holds. **No uniform 16-bit encoding can match a column you get for free**, and
65,536 codes over 89.45 `PHRED` units is a mean spacing of 1.37e-3 whatever you do with them.

A *non-uniform* code — codes allocated by density, which for a rank means concentrating them at low
`PHRED` where 10^(-p/10) puts the mass — could in principle do better in the dense region at the
cost of the tail. It was not measured, and it would have to beat free.

`Float64` beating `Float32` on `raw_score` (2.943 against 3.154) is the same effect seen from the
other end: the `f64` representation of a 5-decimal value has long runs of zero mantissa bits, while
`f32` rounding scatters them into noise. **Wherever a source publishes fixed decimals, the float is
the wrong container** — that is the general lesson, and it is not specific to AlphaGenome.

### 4.10 The ClinVar spectrum — the threshold is a triage, and the sign agrees

**Scope: 8 of 24 contigs, 959,844 joined rows**, taken while the remaining sixteen were still
streaming. The shape is stable across the eight and the samples are large, but the numbers below
are a partial pass and are labelled as one.

§4.4.1 established that `PHRED` is an exact within-corpus rank, which makes any threshold a size
dial. It says nothing on its own about whether the variants it keeps are the ones anyone cares
about. Joining ClinVar's classified SNVs to the artifact answers that, and the answer is clear.

| class | rows | median `PHRED` | median `raw_score` | negative `raw` |
| --- | ---: | ---: | ---: | ---: |
| **pathogenic** (P + LP) | 47,920 | **31.19** | 1.6265 | **0.16%** |
| VUS | 561,022 | 21.53 | 0.6664 | 3.14% |
| conflicting | 42,007 | 16.81 | 0.3973 | 12.97% |
| **benign** (B + LB) | 308,895 | **7.27** | 0.0764 | **33.20%** |

Share of each class at or above a threshold, against the corpus baseline `10^(-p/10)`:

| `PHRED ≥` | corpus | pathogenic | benign | VUS | conflicting |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 79.43% | 99.89% | 76.98% | 98.02% | 90.38% |
| 5 | 31.62% | 99.80% | 58.81% | 95.49% | 83.84% |
| 10 | 10.00% | 99.45% | 40.19% | 87.08% | 69.87% |
| 15 | 3.16% | 98.91% | 18.99% | 77.38% | 55.89% |
| **20** | **1.00%** | **97.49%** | **5.60%** | 59.65% | 39.26% |
| 25 | 0.32% | 88.59% | 0.61% | 20.76% | 15.22% |
| **30** | **0.10%** | **58.59%** | **0.10%** | 4.18% | 4.64% |
| 40 | 0.01% | 8.52% | 0.01% | 0.16% | 0.34% |

**`PHRED ≥ 20` keeps 97.5% of pathogenic variants while discarding 94.4% of benign ones and 99% of
the corpus.** That is a 97× enrichment over the baseline, and at `≥ 30` it is 586×. So the size
dial is also a triage — which was not guaranteed and is the thing worth knowing before anyone
picks a default.

**The sign agrees, independently.** §4.7 read a negative `AVI` as evidence *against* functional
impact, inferred from the feature attributions — one feature, the signed 241-way conservation
score, carrying the whole of it. ClinVar confirms it from the other side without being asked:
**0.16% of pathogenic variants score negative against 33.20% of benign ones**, a 200× ratio.
Nothing in the join knew about the attributions.

**Two cautions, and the first is serious.** ClinVar is an **ascertained** set: variants are in it
because somebody looked. Pathogenic entries skew heavily to coding, nonsense and splice-disrupting
changes — exactly what AVI scores high through `PROTEIN_TERMINATION`, `ALPHAMISSENSE` and
`MERGED_SPLICING` (§4.7). So part of this enrichment is "AVI recognises coding damage", which is
not news, and the table must not be read as evidence about **regulatory** variants, where the model
is interesting and ClinVar is nearly empty. The benign contrast is the more informative half:
benign variants are ascertained too, and they score low.

Second, this measures **agreement with a curated call**, not accuracy. A pathogenic variant AVI
scores low is a disagreement between two sources and not a proven miss — which is the shape
`@a-recorded-judgement-is-a-fact` already prescribes, and the reason RM193's check is named
`variant_impact_agreement` rather than anything stronger.

## 5. The rarity axis — it exists, and it is 6% populated

The proposed surface is *size × rarity × effect*. The effect axis is measured in §3. The rarity
axis turns out to be present offline and almost empty, which is a worse problem than absent.

### 5.1 What is already on disk

`locations.py` says gene constraint gets a snapshot precisely because *allele frequency cannot*
ship offline, and that is true of a genome-wide gnomAD AF table. But the **Ensembl variation
snapshot the enricher already provisions carries a frequency column of its own**:

```
chrom start end id ref alt alts qual filter … MA MAF MAC AA
                                                  ^^^^^^^ Float32 / Int32
```

plus boolean evidence flags `E_gnomAD`, `E_1000G`, `E_TOPMed`, `E_ESP`, `E_ExAC`. So route 3 of
the old three-route framing is not a proxy at all — there is a real global minor-allele frequency
to join on, and no new download is needed.

### 5.2 How thin it is, measured on `chr22`

| | |
| --- | --- |
| Ensembl rows (chr22) | 14,915,802 |
| …of which SNVs | 11,114,671 |
| …**with a non-null `MAF`** | **682,227 (6.1%)** |
| `E_gnomAD` set | 5,231,445 |
| `E_TOPMed` set | 6,323,750 |
| `E_1000G` set | 1,073,892 |

Joining AlphaGenome's chr22 SNVs to that snapshot on `(pos, ref, alt)`:

| | rows | share of the AlphaGenome column above it |
| --- | ---: | ---: |
| AlphaGenome chr22 SNVs | 57,280,128 | — |
| …observed in the Ensembl snapshot at all | 5,701,427 | 9.95% |
| …with a known `MAF` | 377,644 | 0.66% |
| AlphaGenome chr22, score ≥0.1 | 4,261,341 | — |
| …observed at all | 437,236 | 10.26% |
| …with a known `MAF` | 26,087 | **0.61%** |
| …**and `MAF` < 0.01** | 23,496 | 0.55% |

Scaled by chr22's 1.46% share of the corpus, "score ≥0.1 **and** rare" is on the order of
**1.6 million rows genome-wide** — a few megabytes.

### 5.3 Why that number is a trap

It is small because **`MAF` is 94% null**, not because rare high-effect variants are rare. And
the null is exactly the tri-state the house algebra exists for: **`MAF` absent means unmeasured,
never rare.** A build that filters `MAF < 0.01` silently answers a different question — "of the
6% of variants somebody measured, which are rare" — and a build that treats null as rare inverts
the meaning outright. Both are `@unreachable-not-absent`, and the second is the `None`-is-never-
`False` rule (`@tri-state-is-the-house-algebra`) broken directly.

The honest options, none chosen here:

1. **Effect only, keep the null.** Threshold on score, carry `MAF` where known and `unknown`
   where not, and let the consumer decide. The only shape that does not lie.
2. **Effect × observed-ness.** `E_gnomAD` is set on 47% of chr22's Ensembl SNVs against `MAF`'s
   6%, so "has been seen in gnomAD" is a far denser signal than "has a frequency" — but it is a
   boolean, and it says *observed*, not *common*. Denser and coarser.
3. **A real AF lane.** A genome-wide gnomAD sites table, which is a multi-hundred-GB download
   before filtering and a new cache lane with all three stages to build
   (`@a-cache-lane-has-three-stages-and-a-list-cannot-say-which-are-missing`). It would make the
   surface mean what it says, at the cost the snapshot decision already declined once.
4. **Live gnomAD per variant** — implemented, rate-limited (`@gnomad-rate-limits`), and hopeless
   at 10⁸ scale. It is a per-variant check for an authored module, not a bulk join.

One more thing the join says on its own: **only 9.95% of AlphaGenome's SNVs are observed
variants at all.** The bulk artifact is exhaustive over positions and the variation snapshot is a
record of what has been seen, so intersecting them changes the corpus *kind* — from "an answer
for any query" to "an answer for known variants". Which of those a consumer wants is a use-case
question, and `docs/USE_CASES.md` is where the design cycle says it starts.

## 6. Two surfaces, and three dependency tiers

There are two ways to reach these numbers — the bulk downloads of §1 and a network API — and the
API is really two APIs: a **model** service that runs AlphaGenome on a sequence window, and an
**Atlas** service that serves the *precomputed* scores, the same content as the downloads, one
variant at a time.

### 6.1 What the Atlas service offers

`alphagenome.atlas.atlas` wraps three RPCs on `gdmscience.googleapis.com:443`, authenticated with
`x-goog-api-key`: `GetDenseVariantScores` (one variant), `ListDenseVariantScores` (an interval)
and `ListVariantScoresMetadata`. The metadata call reports **22 precomputed scorers**, which is a
superset of what is downloadable:

```
AVI_SCORE  AVI_SCORE_FEATURE_IMPORTANCE  AVI_SCORE_MODEL_FEATURES
SPLICE_SITES  SPLICE_SITE_USAGE  SPLICE_JUNCTIONS  POLYADENYLATION
RNA_SEQ  RNA_SEQ_ACTIVE  CAGE  CAGE_ACTIVE  PROCAP  PROCAP_ACTIVE
ATAC  ATAC_ACTIVE  DNASE  DNASE_ACTIVE  CHIP_TF  CHIP_TF_ACTIVE
CHIP_HISTONE  CHIP_HISTONE_ACTIVE  CONTACT_MAPS
```

Seven carry `is_signed: true`. **The SHAP feature importances that are a 283.9 GB download are
one of these scorers**, so a consumer needing them for a handful of variants never has to take
the file.

### 6.2 The dependency question, measured

`uv add alphagenome` pulls **anndata, pandas, scipy, zarr, h5py, numcodecs, pyarrow, matplotlib,
seaborn, pyfaidx, absl-py, fsspec, jaxtyping, typeguard, ml-dtypes, zstandard, grpcio, protobuf,
numpy, tqdm, immutabledict** and their closures. That is not an artefact of the resolver: the
upstream `pyproject.toml` declares **twenty flat runtime dependencies** with matplotlib, seaborn,
pyfaidx, absl-py, fsspec and pyarrow among them, and its only extras are `dev`, `docs` and
`scripts`. There is no light variant to ask for, by design. Against a tier whose whole dependency list is
`httpx`/`tenacity`/`huggingface-hub`, that is not a size question, it is the
**"dependency tiers are sacred"** rule in CLAUDE.md.

Four install shapes, each built as a real venv and measured:

| tier | what you install | size | what works |
| --- | --- | ---: | --- |
| **protos only** | `alphagenome --no-deps` + `grpcio` + `protobuf` | **22 MB** | every Atlas RPC; scores come back as raw little-endian `float32` bytes |
| + numpy | the above + `numpy`, `ml_dtypes`, `zstandard`, `immutabledict` | 85 MB | the above, plus `tensor_utils` for the model service's packed tensors |
| SDK import path | the above + `anndata`, `pandas`, `tqdm` and their closure | 242 MB | `alphagenome.atlas.atlas` and `alphagenome.models.dna_client` import |
| full declared | `uv add alphagenome` | 255 MB | everything, including plotting |

**The 22 MB tier is not a trick — it is a complete client.** `DenseVariantScore.scores` and
`.calibrated_scores` are `bytes` fields, not tensor protos, so `struct.unpack('<f', …)` decodes
them with no third-party package at all; and the request's `filter` is a plain AIP-160 **string**
(`'scores.variant_scorer.name = "AVI_SCORE"'`), not a message that needs building. The whole
call, verified live, is in Appendix A.6.

**And it *is* declarable, contrary to what this section said before the upstream repository was
read.** `github.com/google-deepmind/alphagenome` is Apache-2.0 and ships the four `.proto`
sources; the wheel generates its bindings at build time from them (`hatch_build.py` calling
`grpc_tools.protoc`). The Atlas surface needs three of the four —
`atlas_service.proto` (170 lines), `dna_model.proto` (560) and `tensor.proto` (104), **28 KB
together** — so vendoring those and generating bindings with `grpcio-tools` gives a declarable
dependency set of exactly `grpcio` + `protobuf`.

Verified end to end: in a venv with **no `alphagenome` package installed** (`import alphagenome`
→ `ModuleNotFoundError`), bindings generated from the three vendored protos returned
`chr1:10001 T>A raw=-0.03868196 calibrated=0.21739846` in 372 ms, decoded with `struct.unpack`
from the standard library. Appendix A.8 is the recipe. That makes four shapes below, not three,
and it is the only one that is both light and declarable — at the cost of owning generated code
against a service whose protos can move.

Six of the declared dependencies — **matplotlib, seaborn, pyfaidx, absl-py, fsspec, pyarrow** —
are never imported on any scoring path; they belong to `alphagenome.visualization` and
`alphagenome.io`. The wheel declares them flat, so there is no extra to opt out of.

**Where the jungle becomes unavoidable is `anndata`.** Both `atlas/atlas.py` and
`models/dna_client.py` `import anndata` at module level, and anndata drags scipy, zarr, h5py,
numcodecs, pydantic-settings and natsort. So the split is not "a light half of the SDK" — it is
**use the generated protos and skip the SDK's convenience layer**, which is a real cost: the
`AnnData` return type is where track metadata, ontology terms and gene ids are attached, and
anything hand-rolled on the protos re-implements that.

Four shapes follow, none chosen here:

1. **`grpcio` + `protobuf` as enricher core deps** (22 MB), talking to the generated stubs. Two
   new core dependencies on the network tier, and a hand-written decode layer to maintain against
   a service whose protos can change under it.
2. **An optional extra** — `just-dna-enricher[alphagenome]` with a guarded module-level
   `try/except ImportError`, which is the one exception CLAUDE.md's no-inline-imports rule
   already allows for an optional dep. Nothing changes for a consumer that does not ask for it.
3. **Vendor three Apache-2.0 protos** (28 KB) and declare `grpcio` + `protobuf`. Light *and*
   declarable — and **built, with tests**: [`alphagenome_poc/`](alphagenome_poc/) is a working
   client with 23 passing tests, 20 of them offline. An AST walk pins the dependency floor at
   `{grpc, docs}` so the 22 MB claim is a property of the code; a live test asserts the RPC
   returns what the 88.5 GB file contains. The cost it makes visible is that generated code has
   **no compile-time signal when the service's protos move** — `PROVENANCE.txt` records the commit
   so re-vendoring is a diff, but noticing it is due is manual.
4. **No client at all** — treat the bulk artifacts as a snapshot lane like ClinVar's, built by an
   operator with `tabix`, and never reach the service from library code at all. This is the shape
   the repo's existing licence-gated caches already have, and it needs no new dependency
   whatsoever.

`alphagenome>=0.9.0` is presently in `enricher/pyproject.toml` and `uv.lock` as the maintainer's
own probe. **It is deliberately not committed by this document**, because adding it is exactly
the decision the three shapes above are for.

### 6.3 The two surfaces do not agree equally well

`@two-surfaces-two-denominators` says a bulk download and an API are different sources. Measured
here, that is true of one artifact and not the other:

- **AVI's `raw_score` reproduces exactly; its `PHRED` does not, at the top of the scale.** The
  Atlas API returns `raw_score` −0.03868196 where the file says −0.03868, and −0.03200157 where it
  says −0.032 — the file is the API's float32 printed to five decimals. But `calibrated_scores` is
  also a **float32**, and the largest float32 below 1.0 is `1 − 2⁻²⁴`, which caps a derived Phred
  at **72.247**. The published file goes to **89.451**. Checked on the two highest-Phred variants
  on `chr22`:

  | variant | file `raw` / `PHRED` | API `raw` | API `calibrated` | derived `PHRED` |
  | --- | --- | ---: | ---: | --- |
  | chr22:30339156 C>A | 4.626 / **84.10132** | 4.62584 | **1.0** | **+∞** |
  | chr22:41781345 C>A | 4.499 / **81.86764** | 4.49909 | **1.0** | **+∞** |

  The quantile saturates and the Phred value is unrecoverable. It affects **17 of `chr22`'s
  117,479,331 rows**, about **1,300 genome-wide** — vanishing as a fraction and precisely the rows
  an impact-ranked consumer would look at first. So for AVI the download and the RPC are one source
  on the magnitude and **two** on the rank, and `@two-surfaces-two-denominators` applies to this
  artifact after all, narrowly.
- **Merged splicing does not.** The documented formula is
  `max(splice_sites) + max(splice_site_usage) + max(splice_junctions) / 5` — full weight to site
  identity and usage, a 0.2 multiplier on junctions because their magnitudes run larger. Scoring
  through the model service at a 1 MB window and applying it gives **2.81 against the file's
  2.735**, and **1.83 against 2.112** — right in shape, wrong in detail, so the exact aggregation
  (which tracks, which axis, which window) is not pinned by what is published. The upstream
  notebook's own `compute_merged_splicing_score` takes a **signed** `max` over genes and tracks,
  not an absolute one; re-running with the signed max changed nothing (every value was positive),
  so that is ruled out as the cause rather than assumed away.
- And at `chr1:65409 A>C`, where the file says 0.003052, all three splice scorers return **zero
  rows** at both a 128 KB and a 1 MB window, so the value in the file is not reachable through
  the documented recommended scorers at all. The locus sits ~10 bp upstream of *OR4F5*, so it is
  not a case of there being no gene nearby.

The docs also give the merged score a **source-sanctioned threshold**: variants above **1.0**
"generally exhibit substantial effects on splicing". §3.2 measures that at 9,761,281 rows,
0.249% of the corpus — about 62 MB as parquet. That is a threshold the source names, not one
invented to hit a budget.

### 6.4 What the API adds over the offline copies, measured

The question is worth asking precisely because the files are the cheap option: they are offline,
unmetered, and reproducible. Measured against them, three surfaces exist and not two.

| | bulk files | **Atlas API** (precomputed) | model API (computed) |
| --- | --- | --- | --- |
| SNVs | yes | yes | yes |
| **indels** | **no** | **no** — `UNIMPLEMENTED` | **yes** |
| wrong `REF` | silently misses | **`INVALID_ARGUMENT`, names the real base** | validates |
| values per variant | **20** | **36,152** | matrices |
| per-track resolution | none | **yes, named** | yes |
| rate limit | none | unmeasured | unmeasured |
| offline / reproducible | yes | no | no |

**One variant, unfiltered, returns 36,152 values across 22 scorer blocks.** Against 20 offline —
two AVI columns, one splicing column, seventeen SHAP feature columns — that is a factor of
**1,800**. The breakdown is where the interesting part is, because it shows exactly what the
files collapse:

| scorer | tracks the API returns | what the files carry |
| --- | ---: | --- |
| `CHIP_TF` | **1,617** | one `MAX_ABS_CHIP_TF` |
| `CHIP_HISTONE` | 1,116 | one `MAX_ABS_CHIP_HISTONE` |
| `CAGE` | 546 | one `MAX_ABS_CAGE` |
| `POLYADENYLATION` | 371 | one `MAX_ABS_POLYADENYLATION` |
| `SPLICE_SITE_USAGE` / `SPLICE_JUNCTIONS` | 367 each | folded into one `MERGED_SPLICING` |
| `DNASE` | 305 | one `MAX_ABS_DNASE` |
| `ATAC` | 167 | one `MAX_ABS_ATAC` |
| `RNA_SEQ` | 37 genes × 371 tracks = 13,727 | one `MAX_ABS_RNA_SEQ` |
| `CONTACT_MAPS` | 28 | one `MAX_ABS_CONTACT_MAPS` |
| `AVI_SCORE_MODEL_FEATURES` / `…_FEATURE_IMPORTANCE` | 18 each | the SHAP file's 17 columns |

So the API's addition is not *more scores*, it is **resolution**: which assay, which cell type,
which transcription factor, which gene. `MAX_ABS_` is a lossy aggregate over hundreds of named
tracks, and the name is what the file throws away.

Timings, on the maintainer's connection: a single-variant AVI RPC has a **median latency of
161 ms** (min 125, max 353, n=12) against a `tabix` lookup in the local file, which is disk-bound
and three orders of magnitude faster. The API is not a bulk surface and does not pretend to be.

### 6.5 Motifs — the expectation was that this is the API-only capability, and it is not a dataset

**There is no motif surface anywhere.** The string "motif" does not appear once in the
`alphagenome` SDK, none of the 22 Atlas scorers is a motif scorer, and the download page's
"AlphaGenome Motif datasets will be made available soon" describes something not yet published.
The quick-start's mention is incidental.

What exists instead is the raw material, and it is already reachable. Motifs are read from a
sequence model by **in-silico mutagenesis** — score every possible SNV across a window and read
the (position × base) matrix — and the SDK ships `interpretation/ism.py` with exactly two
functions for it, `ism_variants` and `ism_matrix`. Measured:

```
query_interval(chr22:36,200,000-36,200,200, scorers=["CHIP_TF"])
  -> AnnData (600 variants × 1,617 tracks) = 970,200 values in 1.6 s
  track names: "CL:0000062 TF ChIP-seq CTCF", "CL:0000115 TF ChIP-seq CTCF", …
  var columns: name, strand, Assay title, ontology_curie, biosample_name,
               biosample_type, biosample_life_stage, transcription_factor
```

A 200 bp window is 600 SNVs; one interval query returns the full ISM matrix for all 1,617 TF
tracks in **1.6 seconds**, with a `transcription_factor` column naming each one. **That is a
motif footprint**, per TF and per cell type, available today.

Upstream says the same thing in the only place the word appears — the quick-start notebook, after
plotting a contribution-score track:

> These contribution scores can be used to systematically discover motifs important for different
> modalities and cell types, find the transcription factors binding those motifs and map motif
> instances across the genome.

and it names the downstream toolchain rather than an AlphaGenome surface: **tfmodisco-lite**,
**tangermeme**, **tomtom**. So the intended route to a motif is contribution scores out of
AlphaGenome and motif discovery outside it, which is why there is no motif scorer to find.

The offline files cannot do this at all, and the reason is §6.4's: the SHAP file's
`MAX_ABS_CHIP_TF` is a single unsigned magnitude over all 1,617 tracks, so the genome-wide ISM
matrix it does contain has had the TF identity and the cell type removed — which is the entire
motif question. **So the motif expectation is right about the conclusion and wrong about the
mechanism**: the API is the only route, not because a motif dataset exists behind it, but because
a motif needs per-track resolution and the files publish an aggregate.

Two consequences worth stating. The forthcoming "Motif datasets" would be a *precomputed
convenience*, not a new capability, so nothing here is blocked on waiting for them. And motif work
is inherently **per-locus and network-bound** — 1.6 s per 200 bp per modality — which puts it on
the enricher side of the tier line as a check about a variant, never as something a compiled
module carries.

### 6.4 The model service, for completeness

- **Output types (11):** ATAC, CAGE, DNASE, RNA_SEQ, CHIP_HISTONE, CHIP_TF, SPLICE_SITES,
  SPLICE_SITE_USAGE, SPLICE_JUNCTIONS, CONTACT_MAPS, PROCAP; **19 recommended variant scorers**
  including POLYADENYLATION and `_ACTIVE` variants.
- **Input windows:** 16 KB, 128 KB, 512 KB, 1 MB. **Build:** hg38 / GENCODE v46; human and mouse.
- **Indels work** — `chr22:36201698 AC>A` scored without complaint, and the model service is the
  only route to them: all three bulk artifacts are SNV-only.
- **It returns matrices, not scalars.** One SNV through `RNA_SEQ` came back as 13 genes × 371
  tracks; the splice scorers are 367 tracks wide. The bulk files' single columns are heavy
  reductions of that.
- No quota or rate-limit figure is published, and none was measured — this probe made roughly a
  dozen calls in total, deliberately.

## 7. Not probed

Named so the next reader knows the shape of the hole rather than inheriting a silent one.

- **AVI's distribution.** The artifact is downloaded and extracted; the pass is queued
  (§1.4, Appendix A.7). Its row count, its coverage, the sign split on `raw_score` and the shape
  of `PHRED` are all open until it lands. **Nothing in §3 or §4 may be quoted about AVI.**
- **The SHAP artifact's distribution.** Its schema, its third-party columns, its zero-means-
  unscored behaviour and its splicing ratio are measured (§1.5), but nothing beyond the first
  8 M rows of `chr1` was read and the file was never extracted — 284 GB and roughly three hours.
  Note §6.1 makes it optional for small numbers of variants: `AVI_SCORE_FEATURE_IMPORTANCE` is
  an Atlas scorer, so a consumer needing a handful never takes the file.
- **The Atlas page's "Permissive Use Downloadable Artifact" section.** Now the largest hole and
  the only one that changes a conclusion: it is the sole statement of *which* artifacts are
  commercially usable, and §1's table rests on it (§2.8).
- **Google's Generative AI Prohibited Use Policy**, incorporated by prohibition 8.
- **AlphaMissense's own terms**, owed by the `ALPHAMISSENSE` column in the SHAP artifact, and the
  provenance of its `CACTUS_241_WAY` / `PHASTCONS_470_WAY` columns.
- **Motif datasets** — announced, not published, and §6.5 shows nothing is blocked on them.
- ~~The Atlas interval RPC on the two-dependency tier.~~ **Closed by the build** — the cause was
  `Strand` having no meaningful zero, not the field mask or the chunking, and the interval RPC now
  works hand-built. §4.7.3 has the measurement.
- **Everything a shipped lane would need beyond reachability**: retry layering, pacing, caching and
  a `SourceRow`. The blueprint proves the transport and deliberately stops there; its README lists
  what it omits.
- **API quota and rate limits.** Not measured; roughly a dozen calls were made in total.
- **The exact merged-splicing aggregation.** The formula is documented and §6.3 shows it lands
  within ~15% but does not reproduce the file, and fails entirely at one locus. What is *not*
  known is which tracks, which axis and which window the published file used.
- **Whether an HF-published snapshot counts as an "open source release"** under §2.4/1b — the
  only route by which a non-commercial-derived cache lane could be `cache pull`-able. A legal
  question, not one this repository should answer for itself.
- **Whether the two PAR copies agree.** `chrX` and `chrY` both carry position 276,225 onward
  (§1.2); no comparison was run.
- **The ClinVar spectrum — scheduled, not skipped.** `PHRED` is an exact within-corpus rank
  (§4.4.1), so it says nothing on its own about whether high-scoring variants are the clinically
  interesting ones. The join is running as this section is written: `tabix -R` over 3,523,241
  ClinVar regions against the artifact, covering **3,887,455 classified SNVs** (2,252,696 VUS,
  1,109,507 likely-benign, 178,749 benign, 157,591 conflicting, plus the pathogenic set). It lands
  here as **§4.10**, with the corpus baseline `10^(-p/10)` beside each class. **Nobody should treat
  a threshold as a default before reading it**: if pathogenic variants are not enriched at high
  `PHRED`, a threshold slice is a size dial and not a triage.
- **Whether a knot's `[lo, hi]` interval is stable across releases.** The knot structure was
  measured once, on the 2026-08-27 artifact. A re-derived model would move the ranks and therefore
  every knot; nothing here says how much.

---

## Appendix A — the programs, so this is re-runnable

Inlined deliberately: the 9.6/11.4 GB and the exceedance numbers are unverifiable without them,
and a path under a session temp directory does not survive the session.

### A.1 The histogram, one contig at a time (`hist.awk`)

```awk
$1=="#CHROM"{next}
{n++; s=$5+0
 sum+=s; if(s>mx)mx=s
 if($2!=prev){np++; prev=$2}
 b=int(-log(s+1e-12)/log(10)*4); if(b<0)b=0; if(b>39)b=39; h[b]++
 if(s>=0.01)t[1]++; if(s>=0.02)t[2]++; if(s>=0.05)t[3]++; if(s>=0.1)t[4]++
 if(s>=0.2)t[5]++; if(s>=0.3)t[6]++; if(s>=0.5)t[7]++; if(s>=1)t[8]++
 if(minp==0||$2<minp)minp=$2; if($2>maxp)maxp=$2}
END{printf "N %d\nSUM %.6f\nMAX %.6f\nMINPOS %d\nMAXPOS %d\nDISTINCTPOS %d\n", n,sum,mx,minp,maxp,np
 for(i=1;i<=8;i++) printf "T %d %d\n", i, t[i]+0
 for(i=0;i<=39;i++) printf "H %d %d\n", i, h[i]+0}
```

`b` is the quarter-decade of `-log10(score)`; the `+1e-12` and the clamp at 39 mean a literal
zero would land in bin 39, which is how §1.2 can state there are none. Counting distinct
positions by comparing against the previous row relies on the file being position-sorted, which
tabix guarantees; **do not** build a hash of positions instead — `chr1` alone has 114 M of them
and twelve parallel workers will take the machine down.

### A.2 The driver

```bash
D=/data/downloads/alphagenome
F=$D/combined_alphagenome_splicing_snvs.tsv.gz
mkdir -p $D/hist
tabix -l $F | xargs -P 12 -I{} sh -c "tabix '$F' '{}' | mawk -F'\t' -f hist.awk > $D/hist/{}.txt"
```

Per contig rather than one stream because `mawk`, not the decompressor, is the bottleneck: a
single-threaded pass over 3.9 B rows is ~50 minutes against 17 for this.

### A.3 The parquet sizing

```python
import subprocess
import polars as pl

F = "/data/downloads/alphagenome/combined_alphagenome_splicing_snvs.tsv.gz"
raw = subprocess.run(["tabix", F, "chr22"], capture_output=True, text=True, check=True).stdout
df = pl.read_csv(raw.encode(), separator="\t", has_header=False,
                 new_columns=["chrom", "pos", "ref", "alt", "score"],
                 schema_overrides={"pos": pl.UInt32, "score": pl.Float64})

# wide, one row per position, three ALT columns; UInt32 x1e6 is exact for six decimals
wide = (df.with_columns((pl.col("score") * 1_000_000).round().cast(pl.UInt32).alias("s"))
          .sort(["pos", "alt"])
          .group_by("pos", maintain_order=True)
          .agg(pl.col("ref").first(), pl.col("s"))
          .with_columns([pl.col("s").list.get(i, null_on_oob=True).alias(f"alt{i}")
                         for i in range(3)])
          .drop("s")
          .with_columns(pl.col("ref").cast(pl.Categorical)))
wide.write_parquet("chr22_wide.parquet", compression="zstd", compression_level=9)
```

Scale the resulting bytes by `3_924_674_451 / 57_280_128` for the genome-wide figure. `chr22` is
1.46% of the corpus and its score distribution is close to the whole-genome one (§3.3), but it is
still one contig — `chr19` would extrapolate high and `chr18` low.

### A.4 The rarity join

```python
import glob, os, subprocess
import polars as pl

base = os.environ["JUST_DNA_PIPELINES_CACHE_DIR"]
ens = pl.scan_parquet(glob.glob(base + "/ensembl_variations/data/homo_sapiens-chr22.parquet")[0])
snv = ens.filter((pl.col("ref").str.len_bytes() == 1) & (pl.col("alt").str.len_bytes() == 1))
es = snv.select(["start", "ref", "alt", "MAF"]).collect().rename({"start": "pos"})

joined = df.join(es, on=["pos", "ref", "alt"], how="inner")   # df from A.3
```

`start` in the Ensembl snapshot is the 1-based position and joins directly against AlphaGenome's
`POS` (`@start-1based`); no `-1` anywhere.

### A.5 The model-service probe

```python
import os
from alphagenome.data import genome
from alphagenome.models import dna_client, variant_scorers

m = dna_client.create(os.environ["ALPHAGENOME_API_KEY"])
rs = variant_scorers.RECOMMENDED_VARIANT_SCORERS
v = genome.Variant(chromosome="chr22", position=36201698,
                   reference_bases="AC", alternate_bases="A")   # an indel
out = m.score_variant(interval=v.reference_interval.resize(2**17), variant=v,
                      variant_scorers=[rs["RNA_SEQ"]])
```

`pip install alphagenome`. Keep the venv off `/`: this machine has 8 GB free on root and the
artifacts live on `/data`.

### A.6 The Atlas service on two dependencies

The whole client, verified live on 2026-09-10. `pip install --no-deps alphagenome grpcio
protobuf` — 22 MB — and nothing else:

```python
import importlib.resources, os
import grpc, numpy as np
from alphagenome.protos import (atlas_service_pb2 as a,
                                atlas_service_pb2_grpc as ag,
                                dna_model_pb2 as d)

cfg = (importlib.resources.files("alphagenome") / "protos/grpc_service_config.json").read_text()
channel = grpc.secure_channel("dns:///gdmscience.googleapis.com:443",
                              grpc.ssl_channel_credentials(),
                              options=(("grpc.service_config", cfg),))
grpc.channel_ready_future(channel).result(30)
stub = ag.AtlasServiceStub(channel=channel)
md = [("x-goog-api-key", os.environ["ALPHAGENOME_API_KEY"])]

# the 22 scorers
meta = stub.ListVariantScoresMetadata(
    a.ListVariantScoresMetadataRequest(organism=d.ORGANISM_HOMO_SAPIENS), metadata=md)
names = [m.variant_scorer.name for m in meta.variant_scorer_metadata]

# one variant's AVI score; `filter` is an AIP-160 string, not a message
resp = stub.GetDenseVariantScores(
    a.GetDenseVariantScoresRequest(
        variant=d.Variant(chromosome="chr1", position=10001,
                          reference_bases="T", alternate_bases="A"),
        organism=d.ORGANISM_HOMO_SAPIENS,
        filter='scores.variant_scorer.name = "AVI_SCORE"'),
    metadata=md)

for s in resp.scores:
    raw = np.frombuffer(s.scores, dtype="<f4")            # -0.03868196
    cal = np.frombuffer(s.calibrated_scores, dtype="<f4")  # 0.21739846
    phred = -10 * np.log10(1 - cal)                        # 1.06466 == the file's PHRED
```

`numpy` is used here only to read four bytes; `struct.unpack("<f", …)` does the same with no
dependency at all, which is what makes the honest floor two packages rather than three.

### A.7 The AVI histogram

`/data/downloads/alphagenome/avi_hist.awk` and `avi_pass.sh` — deliberately written to that
directory rather than a session temp, because the pass waits on an 88.5 GB extraction and fires
whether or not the session that queued it is alive. Same 12-way `tabix`-per-contig shape as A.2,
with two differences the extra column forces: `raw_score` is **signed**, so every threshold is
counted twice (all, and negative-only), and `PHRED` gets its own half-unit histogram since it is
a percentile transform and a log-decade bin would say nothing.
