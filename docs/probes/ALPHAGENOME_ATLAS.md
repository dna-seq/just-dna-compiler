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

   So `calibrated` is a percentile rank and `PHRED` is its presentation. **A parquet needs
   `raw_score` and one of the two, never all three** — and the choice matters, because a
   percentile is bounded and quantises well while a Phred value does not. This also answers what
   the Atlas page means by "AVI scores and Phred-scaled scores": one score and one rescaling of
   its calibration, not two independent measures.

### 1.4 AVI's distribution — measured, pending

The same 12-way per-contig pass is queued behind the extraction (`/data/downloads/alphagenome/
avi_pass.sh`, writing `avi_hist/<contig>.txt`). Until it lands, **none of §3's or §4's numbers
apply to AVI** — different corpus, different row count, an extra column and a sign
(`@probe-names-the-table`). The one thing already established is that its rows begin at the
start of the assembly, so the ~3.9 billion of §1.2 is a floor and not an estimate for it.

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
numpy, tqdm, immutabledict** and their closures. Against a tier whose whole dependency list is
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
`.calibrated_scores` are `bytes` fields, not tensor protos, so `numpy.frombuffer(s.scores,
'<f4')` decodes them; and the request's `filter` is a plain AIP-160 **string**
(`'scores.variant_scorer.name = "AVI_SCORE"'`), not a message that needs building. The whole
call, verified live, is in Appendix A.6.

Six of the declared dependencies — **matplotlib, seaborn, pyfaidx, absl-py, fsspec, pyarrow** —
are never imported on any scoring path; they belong to `alphagenome.visualization` and
`alphagenome.io`. The wheel declares them flat, so there is no extra to opt out of.

**Where the jungle becomes unavoidable is `anndata`.** Both `atlas/atlas.py` and
`models/dna_client.py` `import anndata` at module level, and anndata drags scipy, zarr, h5py,
numcodecs, pydantic-settings and natsort. So the split is not "a light half of the SDK" — it is
**use the generated protos and skip the SDK's convenience layer**, which is a real cost: the
`AnnData` return type is where track metadata, ontology terms and gene ids are attached, and
anything hand-rolled on the protos re-implements that.

Three shapes follow, none chosen here:

1. **`grpcio` + `protobuf` as enricher core deps** (22 MB), talking to the generated stubs. Two
   new core dependencies on the network tier, and a hand-written decode layer to maintain against
   a service whose protos can change under it.
2. **An optional extra** — `just-dna-enricher[alphagenome]` with a guarded module-level
   `try/except ImportError`, which is the one exception CLAUDE.md's no-inline-imports rule
   already allows for an optional dep. Nothing changes for a consumer that does not ask for it.
3. **No client at all** — treat the bulk artifacts as a snapshot lane like ClinVar's, built by an
   operator with `tabix`, and never reach the service from library code at all. This is the shape
   the repo's existing licence-gated caches already have, and it needs no new dependency
   whatsoever.

`alphagenome>=0.9.0` is presently in `enricher/pyproject.toml` and `uv.lock` as the maintainer's
own probe. **It is deliberately not committed by this document**, because adding it is exactly
the decision the three shapes above are for.

### 6.3 The two surfaces do not agree equally well

`@two-surfaces-two-denominators` says a bulk download and an API are different sources. Measured
here, that is true of one artifact and not the other:

- **AVI reproduces exactly.** The Atlas API returns `raw_score` −0.03868196 where the file says
  −0.03868, and −0.03200157 where it says −0.032 — the file is the API's float32 printed to five
  decimals. For AVI, the 88.5 GB download and the per-variant RPC are one source.
- **Merged splicing does not.** The documented formula is
  `max(splice_sites) + max(splice_site_usage) + max(splice_junctions) / 5` — full weight to site
  identity and usage, a 0.2 multiplier on junctions because their magnitudes run larger. Scoring
  through the model service at a 1 MB window and applying it gives **2.81 against the file's
  2.735**, and **1.83 against 2.112** — right in shape, wrong in detail, so the exact aggregation
  (which tracks, which axis, which window) is not pinned by what is published.
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
- **The Atlas interval RPC on the two-dependency tier.** `ListDenseVariantScores` needs an
  `x-goog-fieldmask` header and 32 bp chunking; hand-built requests returned `INVALID_ARGUMENT`
  and the measurement in §6.5 was taken through the SDK instead. The single-variant RPC works on
  the protos alone (§6.2) — the interval one was not made to.
- **API quota and rate limits.** Not measured; roughly a dozen calls were made in total.
- **The exact merged-splicing aggregation.** The formula is documented and §6.3 shows it lands
  within ~15% but does not reproduce the file, and fails entirely at one locus. What is *not*
  known is which tracks, which axis and which window the published file used.
- **Whether an HF-published snapshot counts as an "open source release"** under §2.4/1b — the
  only route by which a non-commercial-derived cache lane could be `cache pull`-able. A legal
  question, not one this repository should answer for itself.
- **Whether the two PAR copies agree.** `chrX` and `chrY` both carry position 276,225 onward
  (§1.2); no comparison was run.

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
