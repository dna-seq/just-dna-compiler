# PROPOSAL 0.7 PT4 — adopting AlphaGenome: a derived artifact, a two-package client, and the API as a resolver

**Status: live, and the first live proposal since PT3 closed on 2026-09-03.** Drafted 2026-09-10
against eleven measured rounds of [probes/ALPHAGENOME_ATLAS.md](../probes/ALPHAGENOME_ATLAS.md),
and decided with the maintainer the same night. It wins over the roadmap files until its items
land.

**Scope: five items, RM191–RM195.** Four are builds; RM195 is a blocker that gates one field on
one of them. Nothing here is designed from scratch — every shape below is already measured, and
where a measurement refused a shape the refusal is recorded rather than argued around.

**Release class: additive, fits the uncut 0.7.0.** A new cache lane, a new optional extra, new
enricher checks and a new draft source are each minor-legal under P3/P8. No model field is removed,
promoted to required, or retyped. Against the 0.6 charter amendment that prices the *authored*
layer: **RM191–RM194 add no authored column at all.** They add a cache lane (free), an extra
(free), enricher checks that report (free) and a drafting provider that writes rows into tables
that already exist (free). The one authored-surface question — whether `sources.csv` grows a
fourth licence axis — is deliberately **not** proposed here; §RM195 says why.

**Not in scope, named so nobody widens into them:**

- **The merged-splicing and SHAP artifacts.** Both are non-commercial-only and both stack third-
  party terms (SHAP carries AlphaMissense, Cactus and phastCons columns). Only the **AVI** artifact
  is in the Permissive class. Everything below reads AVI and nothing else.
- **A gnomAD allele-frequency lane.** The rarity axis stays where the probe left it (§5): the
  Ensembl snapshot's `MAF` is 94% null and `PHRED` is not a rarity proxy. Not this round.
- **The model service.** Only the **Atlas** service (precomputed scores) is adopted. The model
  service computes on demand, is the only route to indels, and is a separate decision.
- **Anything AlphaGenome-derived in a published module by default.** The compile gate is
  data-driven and stays that way.

---

## The evidence this rests on, and the two claims it must not repeat

[probes/ALPHAGENOME_ATLAS.md](../probes/ALPHAGENOME_ATLAS.md) is ~1,400 lines of measurement over
eleven rounds. **Four of its own claims were refuted by later measurement**, and every one failed
the same way: a plausible reading of upstream prose that the bytes then contradicted.

1. "The 22 MB client is not declarable" — refuted by reading the upstream repository, which ships
   the `.proto` sources under Apache-2.0.
2. "The rarity axis is already inside the calibrated score" — inferred from the FAQ's common-variant
   background, refuted by measuring the corpus, which matches an exact within-corpus rank instead.
3. "AVI does not fit whole" — contradicted by the document's own size table three paragraphs later.
4. "`PHRED` is capped at 50" — taken from the FAQ, refuted by an artifact reaching 89.451.

**The standing rule for this round is therefore: measured, not inferred.** Every claim an item
lands must be pinned by a test or a recorded measurement. A reading of upstream prose is a
hypothesis until bytes confirm it.

The material this round starts from, all already committed:

| | |
| --- | --- |
| [ALPHAGENOME_ATLAS.md](../probes/ALPHAGENOME_ATLAS.md) | the measurements, §§1–7 |
| [alphagenome_poc/](../probes/alphagenome_poc/README.md) | a working two-package Atlas client, 25 tests, 21 offline |
| [alphagenome_knots/avi_knots.parquet](../probes/alphagenome_knots/) | **41,474 knots, 466,370 bytes**, genome-wide, verified |
| [vendor/alphagenome_protos/](../vendor/alphagenome_protos/) | the three Apache-2.0 `.proto` sources, `PROVENANCE.txt` pinning upstream `aa6fc8f` |
| [vendor/alphagenome_*.pdf](../vendor/) | four terms documents, hashed |

---

## Build order, and why

1. **RM192 first — the client.** Everything else that touches the network depends on it, and it is
   the only item whose shape is already fully built and tested. Moving the PoC into the package is
   mechanical; doing it first means RM193 and RM194 are written against a real surface rather than
   against a plan.
2. **RM191 second — the derived artifact.** Independent of the client (it reads a local file), long
   (~4 h of passes), and the thing the overnight window exists for. Start its build as soon as its
   builder is tested, so the passes run while RM193 is written.
3. **RM193 third — the resolver checks.** Needs RM192's client and RM191's knot table.
4. **RM194 last — gene-scoped drafting.** Needs RM192, and is the item most likely to be cut for
   time. Cutting it loses nothing the others depend on.
5. **RM195 is not built.** It is a blocker filed against RM191's `SourceRow`, and it resolves by
   the maintainer saving one web page.

---

## RM191 — the AVI derived artifact: an `Int32` parquet plus the knot table

### What it is

A cache lane, in the shape the repo's existing licence-gated lanes already have
(`@gated-source-caches`): an **operator-built** snapshot under `<base>/alphagenome_avi/`, holding
the AVI corpus re-encoded as parquet, plus the knot table, plus `release.json`. Nothing fetches it;
`cache pull` may serve it later, and RM195 gates whether it may be published at all.

### The measurements that fix its shape

| decision | measurement |
| --- | --- |
| `Int32`×10⁵, not `Float32` | both columns print **at most 5 decimals**, so the integer scale is **exactly lossless** while `Float32` silently rounds the 5th — and is *larger*: 3.154 B/row against 2.413 (§4.9) |
| `PHRED` column **dropped** | it is a rank, monotone in `raw_score`; the knot table reconstructs it with `max |Δ| 3.56e-4` and **zero threshold misclassifications** among unflagged rows across all 50 integer thresholds (§4.6, §4.8) |
| knot table **shipped beside it** | 41,474 knots / **466,370 bytes**, and it carries the curve, the per-knot ambiguity **interval**, and decidable threshold safety at once (§4.7.2) |
| **no threshold** by default | the full corpus is **34.4 GB** keeping `raw_score` alone — inside the stated budget with the sign intact. A threshold is a *consumer's* slice, not the artifact's shape (§4.4.3) |
| `raw_score` **signed**, kept | 49.30% of the corpus is negative and `abs()` would discard what half of it says (§1.4) |

### The build

Under `enricher/src/just_dna_enricher/alphagenome_build.py`, a `typer` command
`just-dna-enricher alphagenome build`, following `clinvar_build`/`constraint_build`:

- `--input` the operator's extracted `alphagenome_variant_impact_score_snvs.tsv.gz` (+ `.tbi`).
  **Never downloads** — the artifact is 88.5 GB behind a sign-in.
- `--out` defaults to `repro_out("alphagenome_avi")`; the AST guard over the CLI already refuses a
  literal (`@a-default-spelled-per-command-is-a-rule-in-prose`).
- Per contig via `tabix`, 12-way, writing `data/alphagenome_avi-<contig>.parquet`. The measured
  passes ran 24 contigs in **41–46 minutes**; budget an hour and a half for the write.
- Columns: `chrom` (categorical), `pos` `UInt32` — **the 1-based VCF position, passed through
  unchanged** (`@start-1based`) — `ref`/`alt` categorical, `raw_score_e5` `Int32`.
- The knot table is **rebuilt by the same command**, not copied from `docs/probes/`, and the
  builder asserts it reconciles: `sum(n)` over knots must equal the row count written. The
  committed copy is evidence; the lane's copy is the artifact.
- `release.json` records the source file's `sha256`, its `Last-Modified`, the AVI artifact's own
  **2026-08-27** stamp, and the row count. The stamp is load-bearing, not hygiene: the Output Terms
  pin the applicable licence version to **the date the Output was generated** (§2.7).
- `LICENSE.txt` beside the data, carrying the Output Terms' **"Use restrictions" section**, because
  restriction 3b requires it to travel *inside* a derivative rather than as a link (§2.7). The
  layout constant `SNAPSHOT_LICENSE_FILENAME` already exists for exactly this.

### Tests

- Round-trip on one contig: build, read back, and assert `raw_score_e5 / 1e5` equals the source's
  printed value **exactly** for every row. That is the losslessness claim, and it is checkable.
- Knot reconciliation: `sum(n)` equals rows written; every `raw_score` in the data has a knot.
- **The threshold-safety property**, which is the item's real contract: for a sample of thresholds,
  rows whose knot does not straddle the threshold classify identically whether you use the stored
  `PHRED` or the knot reconstruction. Zero tolerance, not a bound — that is what §4.8 measured.
- A `SourceRow` is written, and a test that strips `declared_use` asserts the compile refuses
  (`@write-the-sourcerow`).

### What it must not do

- **Not write a `PHRED` column.** It is 24.7 GB of a rank the knot table already carries.
- **Not read the splicing or SHAP artifacts.** Different licence class, and mixing them into one
  lane makes the lane non-commercial.
- **Not collapse "unscored" to zero.** AVI covers ~95% of the assembly, not all of it, and it
  writes **672,931 genuine zeros** — so absence must be row-absence, never `0.0` (§1.4).

---

## RM192 — the Atlas client, on two packages, and the `alphagenome` extra deleted

### What it is

[`docs/probes/alphagenome_poc/`](../probes/alphagenome_poc/README.md) moved into
`enricher/src/just_dna_enricher/atlas_client.py`, with the vendored protos and the generation step
coming with it. **The `alphagenome` extra is deleted entirely.**

### The dependency decision, settled

`grpcio` + `protobuf` go in a **new optional extra, `[atlas]`** — not core. The maintainer's rule:
*"while we can let it be extra; if 2+ APIs want that, we'll move to core."* So the extra is the
resting place until a second gRPC surface appears, and moving it to core later is a one-line change
that needs no redesign.

**`protobuf` is a runtime dependency, not a build one** — the generated `_pb2` modules
`from google.protobuf import descriptor`, so it is imported on every call. Only **`grpcio-tools`**
is build-only, and it joins `dev`. Measured, not assumed: the working client runs in a venv holding
exactly `grpcio`, `protobuf` and the generated bindings, with `import alphagenome` raising
`ModuleNotFoundError`.

| | packages | size |
| --- | ---: | ---: |
| default enricher install | 45 | unchanged |
| `just-dna-enricher[atlas]` | 47 | ~22 MB added |
| the deleted `[alphagenome]` extra | 81 | 255 MB |

### The build

- `docs/vendor/alphagenome_protos/` stays where it is — it is upstream source kept for reference,
  which is what that directory is for. `PROVENANCE.txt` pins upstream `aa6fc8f` (2026-09-08).
- Generation moves to `enricher/` and its output stays **git-ignored**. The staged package path
  must keep the private prefix: staging at upstream's own `alphagenome/protos/` produces a package
  literally named `alphagenome` that shadows the real wheel, and the PoC's
  `test_the_generated_bindings_do_not_shadow_the_upstream_package` exists because that happened.
- The error contract moves unchanged. It is the part that carries the house rules: three refusals
  with three different remedies, and `AtlasNotScored` deliberately **not** deriving from
  `AtlasRefused` so an `except` cannot swallow an indel and record a zero.
- The 25 PoC tests move with it and join `testpaths`. The AST walk pinning the import floor to
  `{grpc, …}` is the test that keeps the 22 MB claim true, and it must survive the move.
- **`enricher/pyproject.toml` lines 59–63 must be rewritten in the same commit.** That comment block
  argues the light client "is not declarable here" and calls vendoring "a decision with a
  maintenance cost attached" — an argument commit `1f9a84a` already refuted by doing it. Left
  alone it survives as a stale case against what this item ships.

### What a first cut owes but need not have

- **No retry layering.** The vendored `grpc_service_config.json` carries upstream's policy; nothing
  layers `tenacity` on top the way the enricher's other clients do (`@retry-attempt-floor`). File as
  debt rather than improvising.
- **No interval RPC.** `ListDenseVariantScores` needs an `x-goog-fieldmask` header and 32 bp
  chunking, and hand-built requests returned `INVALID_ARGUMENT`. RM194 needs it; RM192 does not.

---

## RM193 — the Atlas as a resolver: edge cases, and refusals as findings

### What it is

An enricher check surface that uses the Atlas for the two things the local artifact provably cannot
do, and **only** those. It reports; it never repairs (`@enrichment-is-validation`).

### The three capabilities, each measured

**(a) Knot-straddle refinement.** RM191's artifact reports an ambiguous row as the interval
`[phred_lo, phred_hi]`. Where a caller needs a point and the interval straddles their threshold,
the Atlas resolves it: its `raw_score` is a `float32`, ~**7 significant digits against the file's
4**, and at the exact atom that causes every threshold-3 flip, six rows the file prints identically
as `0.00076` come back as `0.000758832 … 0.000764675`, reproducing the published `PHRED` **exactly
at all five decimals** (§4.7.1).

The scope is small and decidable in advance: **~633,000 rows genome-wide at threshold 3, and zero
at every other integer threshold from 1 to 50.** Rebuilding the whole column is 272 days and ~92 M
RPCs, and prohibition 3 makes it the wrong shape of request anyway — so the check must **refuse**
to run unbounded. A hard cap on rows per invocation, and a refusal naming the knot table as the
cheaper answer.

**(b) `REF`/`ALT` resolution fallback.** The Atlas validates `REF` against GRCh38 and **names the
real base**: `"Variant: chr22:36200000:A>T reference base does not match the expected reference
base: G."` That is a finding the local artifact cannot produce — a file lookup on a wrong `REF`
simply misses, and `@va-omits-ref` is the standing note that a VA does not encode `ref`. Parse it
into `AtlasRefMismatch` (already implemented) and surface it as a **finding with the observed base
quoted**, in the shape `@ref-mismatch-causes` already prescribes: one window read, withhold when
ambiguous, group by reason.

**(c) `UNIMPLEMENTED` as "not scored".** An indel returns `UNIMPLEMENTED`, which is the *third
state* and not a refusal — the request was legal and the answer does not exist. `AtlasNotScored`
already carries it. The check must record could-not-ask, never a zero
(`@unreachable-not-absent`), and `--offline` must produce the same third state rather than a
silent skip.

### On commercial / non-commercial extras beyond `raw_score`

The Atlas serves **22 scorers**, and the question was whether any of them earn a place beside
`raw_score` for drafting or validation. Measured answer: **the AVI carve-out covers the AVI Score
and nothing else.** `AVI_SCORE_FEATURE_IMPORTANCE`, `SPLICE_SITES`, `CHIP_TF` and the rest are
ordinary Output, so they are non-commercial and carry the notice obligation. Two of them still earn
their place *for validation*, where the output is a finding rather than a stored value:

- **`AVI_SCORE_MODEL_FEATURES` / `AVI_SCORE_FEATURE_IMPORTANCE`** (18 values each) explain a score
  rather than restating it, and they are what established that a negative AVI is low conservation
  rather than down-regulation (§4.7). A check that reports *why* a variant scored high is worth
  more than one that repeats the number.
- **`ALPHAMISSENSE`**, inside that feature vector, returns **`nan` on non-coding variants** — a
  genuine missing value where `MERGED_SPLICING` writes `0.0`. That distinction is directly usable.

**So: no new stored column from any of them.** They enter as check output under
`declared_use=non_commercial`, and a module that records one is tainted for sale by the existing
machinery. The gate is data-driven and needs no new axis.

### Tests

- Every refusal path against a fake stub, asserting no `grpc.RpcError` escapes and each arm lands
  on the type its remedy needs — the PoC's parametrised test, moved.
- The unbounded-refinement refusal, with a cap small enough to test.
- Network tests opt-in behind `JUST_DNA_NETWORK_TESTS=1` (`@network-tests-optin`), and a test that
  means "no credential" says so with `setenv(VAR, "")`, never `delenv` (`@test-no-credential`).

---

## RM194 — gene-scoped subslices, and the ±512 kb horizon

### The problem this exists for

A gene panel wants "the SNVs that matter for these genes". Slicing the artifact by gene *position*
answers a narrower question than it appears to: it captures coding and near-splice variants and
**silently drops promoters, enhancers, chromatin-altering and other distal variants** that act on
the gene without sitting in it.

### What the API actually offers, measured

The Atlas attributes a variant to genes across the model's whole input window, and the reach is a
hard measurable horizon:

| offset from the gene | gene-filtered scores returned |
| ---: | --- |
| 0 | yes, `max|score| 0.098` |
| +100 kb | yes, 0.0095 |
| +250 kb | yes, 0.0080 |
| +400 kb | yes, 0.0085 |
| **+500 kb** | **yes, 0.0071** |
| **+700 kb** | **nothing — `(0, 371)`** |

So gene attribution reaches **±512 kb**, the half-window of the 1 MB input, and stops dead beyond
it. An unfiltered 400 bp interval query returns 48 genes at a 1 MB window; **a gene-filtered one
returns 1,200 variants × 371 tracks for one named gene in 1.1 s.**

**The gene filter is not an optimisation, it is required**: the unfiltered query at that window
fails with `RESOURCE_EXHAUSTED` — *"Received message larger than max"*.

### The build

A drafting provider, in the shape the existing ones have: `just-dna-enricher alphagenome draft
--gene <SYMBOL>`, writing rows into tables that already exist. Per gene it queries the interval
spanning the gene ±512 kb with `gene_names=[symbol]` and `requested_scorers=["RNA_SEQ"]`, keeps
variants above a `--min-score`, and writes them with the attribution recorded.

- **Cost, measured:** ~1,091 SNVs/s ⇒ a gene plus its ±512 kb flanks is ~3.3 M SNVs ⇒ **~50 minutes
  per gene**. Feasible for a panel of a few genes; **not** feasible genome-wide, and the provider
  must say so rather than let an operator discover it.
- **The distal decay is real and must reach the author:** scores at 100–500 kb run ~10× lower than
  at the gene. A single `--min-score` applied across the window silently keeps only proximal
  variants, which is the failure this item exists to prevent. Record the **distance** beside the
  score so the threshold can be distance-aware, and default to reporting rather than filtering.
- `@gene-map-is-another-sources-attribution` applies directly: a source with no gene column is
  drafted by gene through another source's per-record attribution, **never a span**. Here
  AlphaGenome *is* the attributing source, which is the point — but the attribution must be
  recorded as its own claim, not folded into a positional range.

### What a first cut owes

- The interval RPC on the two-package tier. RM192 does not build it; RM194 needs it, including the
  `x-goog-fieldmask` header and 32 bp chunking that hand-built requests got wrong.
- A `SourceRow` for the lane, and **a second source name.** `@write-the-sourcerow` keys on
  `(source, layer)`, and one name cannot carry two licence classes — the AVI artifact is Permissive
  while `RNA_SEQ` output is not. Propose `alphagenome_avi` and `alphagenome_atlas` as distinct
  sources, which also keeps RM195's gate on the right one.

---

## RM195 — Permissive-class membership is unpinned, so `commercial_use` is `None`

**Not a build.** A blocker, filed against RM191's `SourceRow`, and it resolves when one web page is
saved.

The Additional Terms **define** the Permissive class and grant it commercial use, but they delegate
**membership** to "the 'Permissive Use Downloadable Artifact' section of the AlphaGenome Services
website" (§2.5). That page is a sign-in-gated single-page app; four terms documents are pinned in
`docs/vendor/` and **none of them says which artifacts are Permissive** (§2.8). Every claim that AVI
is commercially usable rests on the maintainer's reading of a page the repository cannot verify.

**So the AVI `SourceRow` carries `commercial_use=None`, not `True`.** Unknown is a value here and
`None` is never `False` — this is the house algebra applied to a licence rather than to data, and
the existing `@no-named-licence` line already says unknown commercial terms *warn* rather than
gate. A `None` means a module carrying AVI data warns under `declared_use=commercial` instead of
either refusing or silently permitting.

Resolving it takes one action: save the Atlas download page the way the four terms documents were
saved. Then `commercial_use=True` becomes assertable and the warning goes away.

---

## Measured beside this round: the ClinVar spectrum

Queued as evidence for whoever chooses a threshold. The AVI corpus's `PHRED` is an exact
within-corpus rank (§4.4.1), so it says nothing on its own about whether high-scoring variants are
the clinically interesting ones. Joining ClinVar's classified SNVs to the artifact answers that
directly: **if pathogenic variants are not enriched at high `PHRED`, a threshold slice is not a
triage.**

The join is `tabix -R` over 3,523,241 ClinVar regions against the 88.5 GB artifact, covering
**3,887,455 classified SNVs** (2,252,696 VUS, 1,109,507 likely-benign, 178,749 benign, 157,591
conflicting, and the pathogenic/likely-pathogenic set). It was still running when this file was
written; **the run is scheduled rather than reported**, and its results belong in the probe document
under §4.10 with the corpus baseline `10^(-p/10)` beside each class. Whoever lands it should read
the result before treating any threshold in RM191 as a default.

---

## What "done" looks like for this round

- `just-dna-enricher[atlas]` installs a working Atlas client in 47 packages; the `alphagenome`
  extra is gone; `enricher/pyproject.toml`'s stale comment block is rewritten.
- `just-dna-enricher alphagenome build` produces `<out>/data/*.parquet`, `avi_knots.parquet`,
  `release.json` and `LICENSE.txt`, and the genome-wide run has completed into `data/repro/`.
- The losslessness, knot-reconciliation and threshold-safety tests pass, and the full suite is green
  at its previous count plus the new tests.
- RM193's checks report the three states and refuse an unbounded refinement.
- RM194 lands or is cut cleanly; nothing else depends on it.
- RM195 is filed in ROADMAP as open, with `commercial_use=None` shipped rather than guessed.

## Implementation debt, filed rather than improvised

Anything below is a decision the maintainer has not made and that the night run must **not** invent.
File each as an `RMn` in ROADMAP if it becomes load-bearing:

- Retry/pacing layering for the Atlas client (`@retry-attempt-floor`, `@shared-pacing-gate`).
- Whether the lane is `cache pull`-able. It rests on RM195 *and* on whether an HF-published snapshot
  counts as an "open source release" under the Terms' §2.4/1b carve-out — a legal question, not ours.
- A distance-aware threshold for RM194's distal variants.
- Whether `PHRED` should ever be materialised for a thresholded export, and if so, whether it
  carries the interval or a point.
- Wide-by-position layout for AVI (saved 17% on splicing; unmeasured here).
