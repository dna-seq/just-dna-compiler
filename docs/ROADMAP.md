# just-dna-format — Roadmap

Forward-looking plans for the schema contract + reference compiler. **This doc is forward-only:**
what already shipped (0.1.0 → 0.4.0) and the rationale behind it now live where they belong —

- **[CHANGELOG.md](CHANGELOG.md)** — what shipped in each release, newest first (the record of
  0.1–0.4 that this doc used to duplicate).
- **[COMPILER.md](COMPILER.md)** — the per-feature coverage table (validated / materialized / computed).
- **[CHANGELOG.md](CHANGELOG.md)** + **[CONSUMER_ROUND2_AND_0_5.md](CONSUMER_ROUND2_AND_0_5.md)**
  — the shipped 0.4 design rationale (the 0.4 proposal was retired into the changelog on release) and
  the round-2 answers.
- **[PROPOSAL_0_5.md](PROPOSAL_0_5.md)** — the forward 0.5 design threads;
  **[PROPOSAL_0_4_1.md](PROPOSAL_0_4_1.md)** — the near-term 0.4.1 patch (inject the authority-key list
  + genuinely adopt `module.version`).
- **[USE_CASES.md](USE_CASES.md)** — each use case run through the *what-blocks?* lens (the `RMn`
  items below are derived there); **[REFERENCE_EXAMPLES.md](REFERENCE_EXAMPLES.md)** — worked drafts.

Code comments that cite "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs for
already-shipped features — follow them to CHANGELOG.md / COMPILER.md.

**Status:** **0.4.0 released** (packages at `0.4.0`; `schema_version` `"1.0"`). The next patch is
**0.4.1** — implemented, pending a release the user cuts (see [PROPOSAL_0_4_1.md](PROPOSAL_0_4_1.md)):

- **Inject the authority-key list (not hardcode it).** The format owns a reference stripper
  (`normalize.strip_authority_keys`) and a documented convenience set
  (`normalize.IDENTITY_AUTHORITY_KEYS = {namespace, owner, canonical_id}`), but **applies nothing by
  default** — a consumer injects the set of registry-stamped identity keys it wants dropped from the
  authored `module:` block *before* validation (`validate_spec(..., authority_keys=...)`). Extends
  CONSTITUTION P2's inject-only spirit; keeps the validator strict (a stray/typo'd key still trips
  `extra="forbid"` loudly — "a validator validates, it does not fix").
- **Genuinely adopt `module.version`** as a freeform advisory field (accepts the pre-0.4 corpus's
  `v2`/`3`); the compiler previews the future SemVer coercion and warns only when it would change the
  value. Digest-neutral. SemVer *enforcement* is deferred to **RM17** below.
- **`content_signature`** — a stable, name-/Ensembl-independent content identity over the raw authored
  data rows (`manifest.content_signature`, out of `artifact.digest`; `just-dna-compiler signature`
  computes it without recompiling), so a registry can dedup across recompile + metadata-strip where the
  parquet digest can't. Canonical algorithm owned here; the marketplace adopts it.
- **Strict (all-or-nothing) compile** — `compile_module(..., strict=True)` refuses a partial artifact
  when a variant position is left unresolved (the "local hash differs from published" failure mode).
- **A compiler CLI (Typer)** — `just-dna-compiler validate|compile|reverse`, a compiler-only dep (tiers
  intact). Plus `ruff` added to the dev group and package `authors`/`maintainers`.

*Still design-only in [PROPOSAL_0_4_1.md](PROPOSAL_0_4_1.md): the "Ensembl cache authority leaves the
compiler" item (needs the `just-dna-datasets` package to coordinate against).* Everything else below is
0.5-and-beyond scope plus the open idea-book.

## 0.5.0 (in progress, `enricher-0.5`) — the resolution-table + enricher rework

**0.5.0 is now the source-independent resolution-table rework** (see [PROPOSAL_0_5.md](PROPOSAL_0_5.md)
and [CHANGELOG.md](CHANGELOG.md)): resolution becomes a persisted, source-independent `resolution.csv`
the compiler *consumes* (owning no source convention), produced by a new **`just-dna-enricher`**
network tier (cache → HF snapshot → Ensembl V2 GraphQL → V1 REST fallback + tenacity; best-effort/
strict/`--offline`). It **subsumes RM13** (a network-first resolution/enrichment sibling) and completes
the 0.4.1 *"cache authority leaves the compiler"* decoupling. The `0.4.1` items ride in folded into the
same 0.5.0 cut (no separate patch release).

**Also landed in 0.5.0:** the **gnomAD v4.1** work — a last-resort live resolver link, the
`frequencies.csv` and `gene_metrics.csv` derived-fact sidecars, an offline gene-constraint snapshot, and
**GA4GH VRS allele identity** (stdlib minting, `vrs_id`/`caid` columns, and `variant_key` deriving from
the VA for a resolved substitution — the one intended `artifact.digest` re-baseline, taken inside the
unpublished window). See [PROPOSAL_0_5.md § G1](PROPOSAL_0_5.md) for the decisions and the several
places probing overturned the plan's assumptions.

**The `RMn` schema items below are pushed to 0.6.0** — they are additive and independent of this
rework, so they wait behind it rather than blocking it.

## 0.6.0 scope — deferred roadmap items (`RMn`)

Derived in [USE_CASES.md](USE_CASES.md) ("Roadmap items surfaced") by running each real/desired use
case against the shipped 0.4 bricks. RM1/RM2/RM3/RM8/RM9/RM11/RM12/RM14 **shipped in 0.4** (their
rows below are kept for traceability, marked ✅); RM13 is **realized by `just-dna-enricher`** in 0.5;
the rest are 0.6-and-beyond scope:

| # | Item | Owner | Motivating use case | Effort |
|---|---|---|---|---|
| RM4 | **Native ClinVar gene-panel materialization** — compile a `GenePanelSpec` (gene set + significance predicate) into `weights.parquet` at compile time, gated on a **content-pinned ClinVar reference mixin**. The 0.2 `GenePanelSpec` *interface* ships and is recorded verbatim; the app-level `gene_panel` adapter in just-dna-lite is the interim reference implementation. Blocked only by Constitution P2 (no network) — the reference must be *injected*, not fetched. **0.5 update:** the content-pinned reference now exists as an injectable artifact — `just-dna-enricher`'s ClinVar snapshot (`clinvar build` → `data/*.parquet` + `release.json` carrying `source_sha256`/`clinvar_file_date`, feeding `GenePanelSpec.reference`/`reference_sha256`). What stays parked is the *compile-time materialization* of a `GenePanelSpec` into `weights.parquet`; the injectable reference half is unblocked. | format (compiler) + consumer-provided reference | gene-panel modules (cardio / cancer / pathogenic) | medium |
| RM5 | **Symbolic / structural alleles** — a representation beyond `^[ACGT]+$`: `<S>`/`<L>`, `<DEL>`/`<INS>`/`<DUP>`, `<STR n>`, and large indels. **Motivating case: 5-HTTLPR** (a biallelic ~43 bp structural indel → Short/Long, *not* a repeat count; rejected by today's nucleotide grammar and a category error in `repeat_alleles.csv`). Also unblocks SV-scale variation and consuming symbolic VCF alleles (round-2 §1b/3c). | format (schema) | 5-HTTLPR, SNP+SV modules, symbolic-VCF consume | medium |
| RM6 | **Callability as first-class state** — promote `requires_callable` from an optional flag to a queryable typed column, and build the reserved **`callable_from`** (the DP,GQ,FT three-state signal from round-2 §3d). The consumer's own oracle enum (`CONFIRMED_NEGATIVE`/`LOW_DP_NEG`/`UNCOVERED`) is why "a named negative is assertable only where proof is `CONFIRMED_NEGATIVE`" — consumers *will* filter on it. | format (schema) | callability / no-call ≠ hom-ref | low-medium |
| RM10 | **Declarative inheritance-expectation field** — an optional trio / de-novo / Mendelian-consistency assertion carried *as data* (the panel says what it expects; a consumer checks it). Only if a real module needs it. | format (schema) | trio / multi-sample panels | low (on demand) |
| RM14 | ✅ **shipped in 0.4** — **Structured per-version authorship**: an optional `authorship: [Contribution]` on `module_spec.yaml`/`ModuleManifest`, unbundling the flat `authors` + free-form `curator` (which smuggled kind via the `"ai-module-creator"` default) into three orthogonal axes (P5): **identity** (`who`), **role** (closed vocab created/edited/audited/reviewed), **kind** (open, multi-valued: human ladder `human`→`human_expert`→`human_certified`, or `ai`+scale `agent`/`team`/`swarm`; no `hybrid` — a joint contribution is two entries). Motivating case: **AI and human error-spectra overlap but differ**, so a consumer (the RM13 validator, a marketplace review queue, a human auditor) routes scrutiny by author-kind — the format carries the kind, the consumer picks the profile (north star). **Digest-neutral** (manifest metadata, out of `artifact.digest`); like `panel`, not reconstructed by the lossy `reverse_module`. Folding the flat `authors`/`curator` in is a 1.0-cleanup candidate. | format (schema) | authorship-aware scrutiny (§5a) | done |
| RM7 | **Evaluation-output / report-card schema** for the verification harness — **NOT a format task.** Per-sample results are a *measurement*, so by the data-agnostic north star this is a **consumer** contract (`just-dna-lite`), listed here only so it is not mistaken for format scope. | consumer (`just-dna-lite`) | verification harness (§1a) | — |
| RM11 | ✅ **shipped in 0.4** — **`doi` provenance column** on `StudyRow`, wider than `pmid` (covers preprints/books/theses/datasets with no PubMed id); validated against the DOI grammar, kept verbatim, materialized into `studies.parquet`. A network-first validator (RM13) cross-fills `doi`↔`pmid`. Additive/optional → P3/P8 clean. The full DOI-only fix (relaxing the mandatory `pmid`) is a 1.0 item — see the 1.0 tracker. | format (schema) | validator source-checks (§4a) | done |
| RM12 | ✅ **shipped in 0.4** — **Provenance locator**: optional `provenance_quote` (keyword phrase) + `provenance_regex` on `StudyRow`, pointing at the passage in the cited article's fulltext so a validator can answer *"does the fulltext contain this claim?"* yes/no. The regex is a **declarative pattern grammar** (Principle 1 — data, not code; `re.compile`-checked at author time, matched by a consumer-side ReDoS-safe engine); the provenance analogue of `source_field`. | format (schema) | validator fulltext check (§4a) | done |
| RM13 | ✅ **realized in 0.5 as `just-dna-enricher`** — the network-first resolution/enrichment tier. 0.5 builds the rsid↔coordinate resolution half (cache + Ensembl V2/V1 + tenacity, producing `resolution.csv`); the source-check half (validate `pmid` in PubMed, confirm fulltext provenance, cross-fill ids) is additional resolver links the same package can grow. Principle 2 stays intact — the enricher is a *separate tier* that fetches; format/compiler never do. | network tier (`just-dna-enricher`) | deterministic module scrutiny (§4a) | in progress |
| RM16 | **Authored PRS weights (a scoring file, not a manifest).** 0.4 shipped `pgs.csv` as a *manifest of PGS Catalog IDs* with the ancestry-validity fields — not authored per-variant weights (just-prs resolves a `PGSxxxxxx` id to a harmonized scoring file and scores each id itself, so inlined weights would be dead data; a PRS is a Z/percentile-in-reference, a shape the format does not bin). Deferred: a distinct, digest-bearing `effect_allele`+`effect_weight` scoring table for the case a module must ship weights the PGS Catalog does not host. Build only against a real consumer that combines authored weights into a score. See [PROPOSAL_0_5.md](PROPOSAL_0_5.md) D1. | format (schema + compiler) | authored-weight PRS modules | medium-large (on demand) |
| RM17 | **Enforce SemVer on `module.version`** — 0.4.1 adopted `version` as a *freeform advisory* field and ships the coercion algorithm (`normalize.normalize_version`) used **read-only** to preview what a future release will read. 0.5 promotes it to an enforced `ModuleInfo.version` validator (coerce `v2`→`2.0.0`, or strict-reject — TBD). **Out of `artifact.digest`**, additive (accepts the same inputs, normalizes them). Once enforced, a clean authored SemVer flows into `Identity.version` (0.4.1 already does this for already-valid values). See [PROPOSAL_0_5.md](PROPOSAL_0_5.md) V1. | format (schema) | pre-0.4 corpus `module.version` | low |
| RM15 | **Build-agnostic identity & multi-build support (other-builds-support)** — today a coordinate is *implicitly GRCh38* (legacy-from-implementation): `genome_build` is authored/manifest metadata, but every `chrom/start/ref`, the Ensembl resolver, and all coord-based reasoning silently assume GRCh38. Coordinates are **not absolute** — GRCh37 / GRCh38 / T2T-CHM13 disagree, and the rsid↔coordinate mapping is **build-specific**: an rsid may resolve in one build and be un-annotatable (unplaced/absent) in another, and presence/absence combinations vary per build. This item makes the build a first-class axis — coordinates tagged by (or resolved per) build, a **build-aware resolver** (the injected reference declares its build; a module/reference build mismatch degrades to *unverified* rather than a false consistency error), and cross-build rsid annotatability recorded *as data*. **The "coordinate-first identity" parking is now RESOLVED, on its own stated condition.** This item parked option C because a bare coordinate "would bake GRCh38 into `variant_key`", and said it "becomes reconsiderable only once identity can name its build". A **GA4GH VRS allele id names its build**: the sequence is addressed by its refget accession — the digest of the reference sequence itself — so GRCh38 and GRCh37 mint distinct, correctly non-colliding ids. 0.5 therefore ships coordinate-first identity as the VA for a resolved substitution (see [SCHEMAS.md](SCHEMAS.md) § the identity switch). What remains of RM15 here is the **multi-build** half: a second refget table beside `REFGET_GRCh38`, per-build coordinates, and cross-build annotatability. The GRCh38-only minting ships now — the same "GRCh38-now, multi-build-later" split this item already applies to one-to-many expansion. **Generalizes one-to-many rsid expansion to multi-build:** a no-coord rsid that maps to several loci is expanded to one row per locus (a paralog/SV signal a client can count — data-agnostic), and that ships **GRCh38-only now as compiler behavior** (pinned by `compiler_version`, not a schema break). What is build-specific is *which* loci and *how many*, so RM15 tags expanded coordinates by build and records cross-build annotatability; the GRCh38 expansion itself is not deferred. Blocked by nothing external (schema-shape + resolver decision) but large — touches identity, positions, the resolver, and `artifact.digest`. Interacts with RM5 (symbolic/structural alleles differ across assemblies) and the reserved `reference_db` axis. | format (schema + compiler) | GRCh37 / T2T modules; cross-build annotatability | large |

**Round-3 / on-demand (widen additively only if a real module hits it):**
- **STR microvariant notation** — forensic loci use `full.partial` allele names (TH01 `"9.3"` = 9 full
  `TCAT` repeats + 3 extra bases), which is *not* the decimal 9.3. A binning bound stays a plain
  magnitude for ordering; the `full.partial` allele *name* is a distinct string (a candidate for the
  reserved repeat motif-path / allele-string escape hatch), never smuggled into the float bound
  (CONSUMER_ROUND2 C2). Pathogenic-threshold loci (HTT CAG) are unaffected.

**Cross-repo (tracked elsewhere):** **just-dna-marketplace** — take `just-dna-compiler` as the M4
publish dependency; serve `logs` via the files endpoint; render the cross-version provenance union
(`aggregate.aggregate_provenance`) on the module-detail view.

## Freeform suggestions — the 0.5 idea-book

The consumer's grounded 0.5 ideas (kept inside the one constraint: **VCF-based, possibly augmented on
top**) live in full in [CONSUMER_ROUND2_AND_0_5.md](CONSUMER_ROUND2_AND_0_5.md) §3, each run through
the what-blocks lens in [USE_CASES.md](USE_CASES.md) §1. Standing dispositions:

- **3a — module declares where its measurement lives in a VCF.** ✅ Taken early: `source_field` shipped
  in 0.4 (an optional, `|`-alternatable **bare field-name token** on every binning table — a
  *declarative pointer, not an expression*, inside Principle 1). An ExpansionHunter VCF (`INFO/RU` →
  `repeat_unit`, `FORMAT/REPCN` → the measure) is consumable with zero glue.
- **3b — modules as a deterministic verification harness** (run a panel against N VCFs, emit a
  byte-diffable report-card). **The strongest idea, and it needs *nothing* from the format:** a panel
  is already a module, `source_field` names the field to read, `artifact.digest` makes the before/after
  diff trustworthy, and the mandatory `unresolved`/callability contract stops a no-call masquerading as
  a mismatch. It is a **consumer** feature (`just-dna-lite`); the format only supplies properties it
  already froze. Recorded as an *enabled* use case, not a gap.
- **3c — augmented-VCF as the landing pad** for cracked short-read loci (a synthetic `<STR>` record with
  `INFO/RU` + `FORMAT/REPCN` + custom evidence fields, consumed through the same `source_field=REPCN`
  path). Endorsed as the interface — the format binds to the VCF, it does not reinvent it. Consuming the
  *symbolic* alleles themselves is RM5.
- **3d — smaller VCF-native ideas:** callability three-state → RM6; phasing-aware panels → already
  expressible (the `phased` flag + VCF `PS`/`HP`); trio/de-novo assertion → RM10.

### Parked in 0.5 (recorded so they are not re-proposed as if new)

- **Enricher co-authoring** (permission-gated writes to *authored* files, not just sidecars). Attractive
  — it would let a stale rsID or a missing DOI be fixed where it actually lives instead of only being
  reported — and deliberately **not** taken, for a reason stronger than tidiness: `content_signature`
  is *defined* as pre-resolution and reference-independent ("computed from the rows before resolution,
  so recompiling against a different/complete reference does not change it"). If a network fetch could
  edit `variants.csv`, the content-dedup identity would become network-dependent and that documented
  property would simply be false. A secondary problem: `authorship` records who wrote the module, and
  an enricher that edits rows either falsifies that record or must add itself as an `ai`/`agent`
  contribution — coherent, but a much larger design than it first looks. Revisit only with both
  answered.

- **An offline allele-frequency snapshot.** The obvious symmetry with the ClinVar and gene-constraint
  snapshots, and it does not work: gnomAD v4.1's sites VCFs are **58 GB** (exomes) and **742 GB**
  (genomes), so there is no slice to ship at any useful coverage. Frequency is therefore the first and
  only **online-only** link in the chain. This is not a reproducibility hole — once `frequencies.csv` is
  written it *is* the pin, and every later compile reads it offline and deterministically. Revisit only
  if gnomAD publishes a small pre-aggregated frequency release.
- **HGVS string generation** (`c.`/`p.` notation). `ga4gh.vrs`'s extras pull `hgvs` transitively, so it
  would be *available* — but HGVS generation is its own feature with its own argument (which transcript,
  which reference, how to present ambiguity), and taking a dependency for indel normalization does not
  commit to shipping it. Deferred as a feature, not blocked by tooling.
- **Multi-build VRS minting.** A second refget table beside `REFGET_GRCh38`; the remaining half of RM15.
- **dbSNP obsolescence / merge checking** (candidate, cheap). dbSNP merges and retires rsIDs, so an
  older module can key on a label its source has since superseded. Detectable two ways, both verified:
  Ensembl REST returns the *current* `name` for a merged query (`rs77121243` → `rs334`, with the
  queried id in `synonyms`) — a signal the enricher **already receives and discards** in
  `_loci_from_rest` — and NCBI `esummary db=snp` reports it batched (`merged_sort`, plus a `snp_id`
  differing from the requested uid). The interesting part is not the lookup but what to do with it:
  see *the stale-identifier collision* below.
- **Sex-stratified frequency counts.** gnomAD serves `nfe_XX`/`XY`; sex is a second axis, and folding it
  into `population` would be the `state`-overloading mistake again. A future `sex` column on
  `FrequencyRow` is the additive shape if it is ever wanted.


### The stale-identifier collision (design note, 0.5)

An obsolete authored rsID forces a choice that Principle 7 and "keep the module current" pull opposite
ways on, and it is worth writing down before anyone implements the lookup.

`weights.parquet` carries **both** `variant_key` and `rsid`, and for an rsid-authored row both are the
authored label. Writing the *updated* label into the artifact is not a one-time digest move — it is an
**identity migration performed by a network lookup**: reverse would then emit the new rsID into
`variants.csv`, the next compile would key on it, and `variant_key` itself would change. The module's
identity would drift without any authored edit, and the round-trip would stop being a fixed point.

So the rule is the one every other check here follows: **report, never repair.** Severity follows the
mode, matching the VRS-unverifiable decision exactly — `best_effort` warns and compiles with the
authored label (digest stable, round-trip intact), `strict` **refuses**, on the grounds that an
all-or-nothing artifact should not be built on an identifier its own source has retired. Failing is the
honest move because it pushes the fix to where it belongs: an authored edit.

Two refinements the implementation will need:

- **Merged ≠ withdrawn.** A merged rsID still resolves to the right locus, so the module is *dated*,
  not wrong. A withdrawn one is a repudiation of the variant itself and may deserve failing in both
  modes. Probe the withdrawn shape before deciding.
- **The new columns are provenance, not facts.** `rsid_current` + `rsid_status` (`live|merged|
  withdrawn`) belong **outside** `RESOLUTION_FACT_FIELDS`, beside `rsid_alternates`. They describe
  time-varying *external* state; putting them in the fact set would make `resolution_signature` change
  when dbSNP merges something, with no change to the module — the signature would stop being
  reproducible from the module's own content.

**The strategic reading:** this whole class of problem is *label drift*, and it exists only for
rsid-keyed rows. A coordinate-authored row keys on a VRS allele id, which is content-addressed and
cannot drift. The obsolescence check is therefore the standing cost of the rsID key, and the format
already offers the escape — author coordinates and carry the rsID as data (reverse already emits
coord-keyed rows as position-only). A strict failure is the nudge toward the drift-proof key.

New ideas enter here as freeform suggestions, then graduate through the design cycle
(feedback → USE_CASES lens → PROPOSAL → shipped or parked as an `RMn` above).

## Reserved namespace

Because backward-compat makes column names and vocabularies **permanent within a major** (CONSTITUTION
Principle 5), a name expected to become a real **module column** later is reserved against the one-way
door and **must not** be claimed early or smuggled in as `flags`. This list is *only* for genuine
anticipated module-side axes — it is **not** a catalogue of names that "may not appear" (that space is
unbounded and pointless to enumerate; barring `caller` would be as arbitrary as barring `pasta_recipe`).
Audit every new name against this list before adding it.

**Enforced now** (the live set is `just_dna_format.vocab.RESERVED_NAMES_0_4`). Every authored model
inherits `AuthoredModel`, which sets `extra="forbid"` (rejects *any* unknown column) **and** runs the
`reject_reserved` before-validator, so a reserved name fails with a *specific* diagnosis — what it is
reserved for + that a release may claim it (`vocab.RESERVED_NAME_REASONS`) — while a random/misspelled
column gets the generic "extra inputs not permitted":
- **`reference_db`** — a module-side hint naming *which* reference database the app should join this
  annotation against when several exist (implicit Ensembl for variants / ClinVar for `clin_sig` today;
  a module may pin it, e.g. a specific PharmVar release). Annotation-side addressing, a real future axis.
- **`callable_from`** — the callability signal a consumer establishes a negative from (DP, GQ, FT);
  reserved for RM6/round-2 §3d as the typed successor to the built `requires_callable` flag.

*(`caller` / `caller_version` were reserved through the 0.4 draft as a "provenance triple" (round-2 Q2)
but are **dropped**: they name which tool produced a *call* — a consumer-side measurement, never module
annotation — so there is no future module axis to hold, and barring the bare name is arbitrary. A
consumer records them on its own call data; a module never carries them, and `extra="forbid"` rejects
them like any stray column. `reference_db` stayed because it has a real annotation-side meaning above,
not the caller-provenance one it was first reserved under.)*

**Planned future annotation axes** (documented intentions, **not yet in the enforced set** above — they
are rejected generically by `extra="forbid"` today, and get a slot + a specific diagnosis only when a
release actually commits to building them):
- **`consequence`** — VEP molecular consequence (Sequence-Ontology term, e.g. `missense_variant`).
  Distinct from `direction` (phenotypic) and `clin_sig` (clinical). **Never repurpose the bare word
  `effect`** for it.
- **`impact`** — VEP impact `{HIGH, MODERATE, LOW, MODIFIER}`, derived from `consequence`.
*(**`allele_frequency`** + **`af_population`** were listed here and are now **built in 0.5 as a
table, not a column** — `frequencies.csv` → `FrequencyRow`, one row per (allele, ancestry group).
A column pair could carry one number for one population; frequency is inherently per-group, and
flattening it onto the variant row would smear two axes together. So the planned axes are retired
rather than shipped. Gene-level constraint arrived beside it as `gene_metrics.csv`. See
[SCHEMAS.md](SCHEMAS.md) and [USE_CASES.md §6](USE_CASES.md).)*

*(`doi`, `provenance_quote`, and `provenance_regex` were reserved here for RM11/RM12 and are now **built**
as optional `StudyRow` columns in 0.4 — so they are absent from this list. The **doi-first** flip that
relaxes the mandatory `pmid` remains a 1.0 item; see the 1.0-cleanup tracker.)*

*(The ploidy / non-SNV quantities that were reserved through 0.3 — `allele_fraction` / heteroplasmy,
`repeat_count` + `repeat_unit`, copy-number dosage — are **built** as the 0.4 binning primitive; the
`hemizygous` genotype case ships via the widened single-allele genotype. Symbolic/structural alleles
remain open as RM5.)*

## The 1.0 cleanup (candidate tracker)

The **compatibility policy** — additive within a major, breaking cleanup only at a major bump, the
two-step deprecate→remove default — is a durable rule in [CONSTITUTION.md](CONSTITUTION.md)
(Principle 3). This is the **living tracker** of concrete items queued for the `→ 1.0` break; add
candidates as they surface.

**Additivity has two axes.** A new version may expand the **column-set** (new optional columns —
routine, digest-only-move while unpublished) *and* the **row-set** (one authored row compiling to
several — e.g. a one-to-many rsid → one row per locus). Row-set expansion changes identity
*cardinality* but is **not** a schema break: it is resolver behavior pinned on the `compiler_version`
axis (P4 already pins the digest to the resolved reference), so the GRCh38 expansion ships now. Only
the *build-aware* generalization (which/how-many loci per build, cross-build annotatability) is RM15.
The idea is to pile genuinely rule-tripping edge-cases (requiredness demotions, retypes, identity-key
*semantics* changes) on the 1.0/RM15 piles instead of forcing them into a minor.

Version-axis note: `schema_version` is `"1.0"` while the packages are `0.x` (now `0.4.0`). At `1.0`,
either align them or document explicitly that they track different things (wire format vs. package
release).

| Candidate | Why | Proposed disposition |
|---|---|---|
| `VariantRow.state` | Overloaded legacy field; a derived alias of `direction` since 0.3. | Deprecate at 1.0 (still read) → remove at 2.0, once consumers read `direction`/`stat_significance`. |
| `state` values `alt` / `ref` | Genotype-relative descriptors that never belonged; recoverable from `ref`/`alts`/`genotype`; not emitted since 0.3. | Drop from the accepted read-vocabulary at 1.0. |
| `VariantRow.pathogenic` / `benign` booleans | Lossy (can't express `likely_*`/`uncertain`); derived aliases of `clin_sig` since 0.3 (now materialized tri-state). | Deprecate at 1.0 → remove at 2.0. (`clinvar` provenance boolean stays.) |
| `StudyRow.p_value: str` | Untyped string holding a number; can't be compared/sorted numerically. | Add a numeric companion in 0.x if needed; retype/remove the string at 1.0 (breaking). |
| `weights.parquet` `end` column | Always set equal to `start` — no source column feeds it. | Remove outright at 1.0 (artifact-digest change, major-only) or wire it to a real end coordinate. |
| `weights.parquet` `likely_pathogenic` / `likely_benign` | Always `False`; no CSV column feeds them — dead output. | Remove at 1.0, or wire to the `clin_sig` tier. |
| `VariantRow.weight` vs `effect_size` | Potential confusion — module-local score vs published magnitude (both kept, documented). | Review at 1.0 whether `weight` stays or is subsumed by `effect_size`. |
| Deprecated flag/vocab aliases | Any transitional vocab kept for 0.x compat (e.g. the trimmed-vs-full `state` set). | Collapse to the canonical vocab at 1.0. |
| `ModuleManifest.authors: list[str]` + free-form `curator` | Flat and overloaded — no role (created/edited/audited), no kind (AI/human); `Defaults.curator` smuggles kind via its `"ai-module-creator"` default. Superseded by the structured authorship record (RM14) once it ships. | Keep both as derived projections through 0.x (P8); at 1.0 fold `authors` into the structured record and drop the kind-smuggling `curator` default. |
| `StudyRow.pmid` required + PMID-shaped | Mandatory `pmid` (must parse to a real PubMed id) rejects DOI-only provenance — preprints (bioRxiv/medRxiv), books, theses, datasets. Demoting a required field is P8-forbidden in-major, so adding optional `doi` (RM11) alone can't unblock it. | **doi-first at 1.0**: make `pmid` optional/legacy and require **≥1 of `{doi, pmid}`** (every citation has a stable id, not necessarily a PMID; the reverse holds). Requiredness change → major-only. |
| Compiler `ensembl_cache` deprecated shim | 0.5 already moved the whole DuckDB resolver + cache-location into `just-dna-enricher` and dropped `duckdb`/`platformdirs`/`python-dotenv` from the compiler (it is now pure-Python; resolution is the `resolution.csv` table). What remains is the `compile_module(ensembl_cache=…)` **surface**, kept as a deprecated shim that emits `DeprecationWarning` and routes to the enricher via a guarded import. | Remove the `ensembl_cache`/`resolve_with_ensembl` params outright at 1.0 (internal call, not the wire/artifact contract, so additive-within-major does not protect it). |
| ~~Coordinate-first identity (option C)~~ — **resolved in 0.5** | The objection was that a coordinate key is *build-baked*. A **VRS allele id is not**: it names its reference sequence by refget accession, so it satisfies RM15's own reconsideration condition. `variant_key` now derives from the VA for a resolved substitution; rsid-keyed, position-only, indel and multi-allelic rows keep their previous keys. | **Done, in 0.5.0's pre-publication window** — an identity-semantics change is major-only because `variant_key` sits in `artifact.digest`, and that gate is *publication*, not the version number: 0.4 is the published line and 0.5.0 never shipped, so it rode the same one-time re-baseline as the alt-carrying key. No published artifact moved. |
