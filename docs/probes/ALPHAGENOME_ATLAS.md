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
- `docs/vendor/alphagenome_additional_tos.pdf`
  (`sha256 0a1b52c469cda9828cc1a5c64b7b39122bd96e20827617fe157d34126005a6c5`, "Last Modified:
  September 8, 2026"), saved by the maintainer from the Terms page, with a `pdftotext -layout`
  extraction beside it at `docs/vendor/alphagenome_additional_tos.txt` so the clauses are
  greppable. **Every quotation in §2 is from that file**, not from the web page.
- The live API, via the `alphagenome` PyPI SDK in a throwaway venv on `/data`, on the
  maintainer's own key.
- The artifact names, sizes and licence classes in §1 are **quoted from the maintainer's reading
  of the Atlas page**, not fetched: `deepmind.google.com/science/alphagenome/*` is a
  sign-in-gated single-page app that serves 185 KB of navigation chrome and no content to
  `curl`/WebFetch. So is `…/terms` and `…/output-terms`. The PDF is why §2 can be precise and
  the missing Output Terms of Use is why §2.7 cannot.

**Date of analysis:** 2026-09-09.

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`.
Nothing here proposes a design and nothing here is an adoption decision — no `RMn` is filed by
this document, deliberately. Where a question is legal rather than technical it is left as a
question.

---

## 0. Summary — the seven things that decide whether this is adoptable

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

5. **All three bulk artifacts are SNV-only** — the filenames say so and the splicing file's
   schema confirms it. **Rare indels do not exist in the bulk data at all**; they exist only
   through the API, which is per-request, tissue-resolved, and non-commercial. Filtering "rare
   indels with low score" is not a slice of these artifacts.

6. **The terms need at least four axes `SourceRow` cannot express**, and one of them is not a
   use restriction at all but a bar on *who may hold the data*: "The AlphaGenome Services aren't
   available for any commercial entity, even if conducting non-commercial work." That is not
   `commercial_use=False`. §2.6 enumerates all four.

7. **There is no `--non-commercial` flag to lean on.** The compile gate is data-driven
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

### 2.7 What could not be read

The **AlphaGenome Output Terms of Use** — the document §2.4/5 requires a distributor to point
at, and therefore the one that actually governs what a downstream reader of a derived module may
do — is at `deepmind.google.com/science/alphagenome/output-terms` and is unreadable without a
signed-in browser. **It is a hole in this analysis, not a detail.** The same applies to the
Atlas page's own per-artifact licence wording. Saving both the way the Additional Terms PDF was
saved would close it.

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

The numbers above are for the *splicing* artifact only. AVI (88.5 GB) is 4.3× larger as source
and carries two score columns rather than one; SHAP (283.9 GB) is a feature *breakdown*, so its
row shape is wholly different and none of this arithmetic transfers to it
(`@probe-names-the-table`).

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

## 6. The API surface

Probed live on the maintainer's key (`ALPHAGENOME_API_KEY`, 39 characters), via the `alphagenome`
SDK:

- **Output types (11):** ATAC, CAGE, DNASE, RNA_SEQ, CHIP_HISTONE, CHIP_TF, SPLICE_SITES,
  SPLICE_SITE_USAGE, SPLICE_JUNCTIONS, CONTACT_MAPS, PROCAP.
- **Recommended variant scorers (19):** the above plus POLYADENYLATION and an `_ACTIVE` variant
  of most.
- **Input windows:** 16 KB, 128 KB, 512 KB, 1 MB (`SUPPORTED_SEQUENCE_LENGTHS`).
- **Build:** hg38 / GENCODE v46. Human and mouse.
- **Indels work.** `chr22:36201698 AC>A` scored without complaint — so the API is the *only*
  route to the indel half of the effect-score idea, and it is non-commercial-only with no AVI
  carve-out for API output (§2.4/1 exempts only the AVI Score).
- **The API returns matrices, not scalars.** Scoring one SNV with `RNA_SEQ` returned an AnnData
  of 13 genes × 371 tracks; `SPLICE_SITE_USAGE` and `SPLICE_JUNCTIONS` are 367 tracks wide. The
  bulk artifact's single `alphagenome_splicing` column is already a heavy reduction of that.
- **Unexplained:** at `chr1:65409 A>C` — a row the bulk file scores 0.003052 — all three
  `SPLICE_*` scorers returned **zero rows** for a 128 KB window. So the merged score is not a
  straightforward aggregate of what those scorers return at that locus, and the merge formula is
  not documented in what was read. Anyone joining bulk to API values needs to establish it
  first; `@two-surfaces-two-denominators` is the rule that says a bulk download and an API are
  different sources and a status basis must be stated.

No quota or rate-limit figure is published in the quick-start docs, and none was measured — this
probe made four API calls in total, deliberately.

---

## 7. Not probed

Named so the next reader knows the shape of the hole rather than inheriting a silent one:

- **The AVI SNV scores artifact** — the only commercially usable one, and the one worth the most.
  1.8 GB of 88.5 GB downloaded at the time of writing. Its schema, its score distribution, its
  Phred column and its genome coverage are all unmeasured. The `hist.awk` used in §3 applies
  unchanged once it lands.
- **The SHAP feature-importance artifact** (283.9 GB). ~40 GB downloaded, nothing read.
- **The AlphaGenome Output Terms of Use** (§2.7) and the Atlas page's own licence wording.
- **Motif datasets** — announced, not published.
- **API quota and rate limits**, and the merge formula behind `alphagenome_splicing` (§6).
- **Whether an HF-published snapshot counts as an "open source release"** under §2.4/1b. This is
  a legal question about the only route by which a non-commercial-derived cache lane could be
  `cache pull`-able, and it is not one this repository should answer for itself.


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

### A.5 The API probe

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
