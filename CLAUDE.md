# Agent Guidelines — just-dna-format

This repo is a **uv workspace** publishing three libraries in dependency tiers
(`enricher → compiler → format`):

- **`just-dna-format`** — the schema contract: pydantic models for the authored spec DSL and the
  compiled `manifest.json`, plus integrity/identity helpers. `pydantic` + `cryptography` only (the
  latter solely for Ed25519 signing), so any verify-only consumer stays light. → [docs/SCHEMAS.md](docs/SCHEMAS.md)
- **`just-dna-compiler`** — the reference compiler: a validated spec → a multi-parquet artifact +
  manifest (the three-parquet SNP core plus one parquet per optional table kind). `polars`/`pyyaml`/
  `typer` — **pure-Python and duckdb-free since 0.5**. → [docs/COMPILER.md](docs/COMPILER.md)
- **`just-dna-enricher`** — the network tier, the **only** package that fetches: it *produces* the
  injected `resolution.csv` the compiler consumes (cache → HF snapshot → live Ensembl V2/V1) and
  carries the module-upload publisher surface. `httpx`/`tenacity`/`huggingface-hub`. → [docs/ENRICHER.md](docs/ENRICHER.md)

Any consumer picks the tier it needs. **`just-dna-format` and `just-dna-compiler` never fetch**
(Principle 2 — inject-only); all network + HuggingFace live in `just-dna-enricher`. There is still
**no app and no orchestration here** — those live in `just-dna-pipelines` / `just-dna-lite` /
`just-dna-marketplace`.

## Authoring a module? Use the skill

`.claude/skills/write-module/` is the workflow for *using* this format rather than changing it — which
table kind a finding belongs in, the order the commands must run in (and the one place deviating from it
deadlocks), what only a human may decide, and a symptom→cause→action index for the messages that cost
someone a day. Every command in it was run end to end. Prefer it over re-deriving the flow from the
package docs; come back here when you are changing the schema rather than authoring against it.

## Read these first, in this order

1. **[docs/CONSTITUTION.md](docs/CONSTITUTION.md) — the durable charter. READ IT BEFORE JUDGING OR
   CHANGING ANYTHING.** It is the source of truth for what these packages are, what they will never
   do, and the invariants every release upholds (declarative-not-code, no network, backward-compat
   within a major, integrity-as-identity, orthogonal axes, the vocabulary idiom, round-trip/
   idempotency, and requiredness compatibility). When a plan conflicts with it, it wins. **An audit
   or design review that has not read the Constitution is incomplete** — its compatibility rules
   (Principles 3, 7, 8) decide whether a proposed change is even legal. **The charter is
   self-contained — it names no other document.** The navigation *into* the living material it
   alludes to is here in this guide (below); keep it that way — never add an outward pointer to the
   Constitution.

   **Never delegate a Constitution question to a spawned agent — read it yourself, in full.** It is
   150 lines and it is the document that decides whether a change is legal at all. A subagent returns
   a *summary*, and a summary of a charter is exactly the lossy relay that loses the clause the
   decision turned on: a principle's force is in its wording (the difference between "additive" and
   "non-breaking", between `None` and `False`, between "tightened" and "loosened"), and a paraphrase
   silently drops the qualifier. The same applies to any other durable rule you are about to *judge*
   a design against, as opposed to merely locate — delegation is for finding things, never for
   deciding them. Exploring wide (which files touch X, where does Y live) is what agents are for;
   reading the charter, the principle you are invoking, or the exact test that pins a behaviour is
   first-hand work.
2. **[docs/ROADMAP.md](docs/ROADMAP.md)** — forward-only, revised often. Holds the 0.5 scope (`RMn`
   items), the freeform idea-book, **the reserved-namespace tracker** (Constitution Principle 5), and
   **the 1.0-cleanup candidate tracker** (Principles 3 and 8). These two trackers are the concrete,
   living lists the Constitution keeps out of itself.
3. **[docs/CHANGELOG.md](docs/CHANGELOG.md)** — what actually shipped, newest first (shared across the
   ecosystem repos that consume these libs).
4. **Per-package references** — [docs/SCHEMAS.md](docs/SCHEMAS.md) (the schema tier: models, the CSV
   families, conventions, the seven hashes), [docs/COMPILER.md](docs/COMPILER.md) (the transform:
   compile pipeline, the Resolution section + its round-trip matrix, reverse, the coverage table), and
   [docs/ENRICHER.md](docs/ENRICHER.md) (the network tier: the resolver chain, Ensembl V2→V1, snapshot
   download + module upload). Read the tier your task touches.

## 0.5 enricher — current state & gotchas (read before touching resolution)

Both the **ClinVar snapshot** and the **gnomAD v4.1** work are shipped (see
[ENRICHER.md](docs/ENRICHER.md); reference example at `reference_examples/pathogenic_clinvar/`; the
design thread and the decisions in [PROPOSAL_0_5.md § G1](docs/PROPOSAL_0_5.md)). gnomAD landed as a
last-resort resolver link, a `frequencies.csv` pass, an offline-capable `gene_metrics.csv` pass, and
**GA4GH VRS allele identity**. The plan file
[docs/gnomad_4.1_enricher_a2c1ccca.plan.md](docs/gnomad_4.1_enricher_a2c1ccca.plan.md) is now history —
**read the docs, not the plan**, since probing overturned several of its assumptions (listed in the
CHANGELOG entry).

- **`variant_key` is the VRS allele id for a resolved substitution (0.5).**
  `derive_variant_key(rsid, chrom, start, ref, alts=None)` returns, in order: the **rsid**; else the
  **`ga4gh:VA.…`** id when the row is a single-base substitution with a coordinate; else
  `chrom:start:ref:alts` (alts sorted/normalized) or bare `chrom:start:ref`. Indels, MNVs,
  multi-allelic cells and off-assembly contigs deliberately fall through to the coordinate key — a VRS
  id is defined over the *justified* allele, and justifying an indel needs the reference sequence.
  Pass `alts` **only when minting a variant identity** (`VariantRow._freeze`, the one-to-many expansion
  re-key sites). Position-level **matching** — studies, `_verify`, the reverse pos→rsid lookup,
  haplotype dedup — deliberately calls it **without** `alts`, so it never mints a VA (a study matches a
  variant at `chrom:start:ref` regardless of allele). Mixing these up would orphan every study *and*
  reintroduce the same-locus allele collision.
- **A VA does not encode `ref`.** VRS names the place and the alt; the reference base is determined by
  the accession + interval, so it is not a digest component. Two consequences, both guarded, both of
  which must stay: the compiler has an **"inconsistent reference allele"** error (two rows sharing a key
  while disagreeing on `ref` — internal contradiction, catchable offline), and the enricher has
  `sequences.verify_reference_alleles` (authored `ref` vs the real bases — needs the sequence, so
  online only). A *single-base* wrong ref still mints the correct id, so **only** the enricher check can
  find it; a *multi-base* wrong ref mints a different allele entirely.
- **Know the validation ceiling before adding a check.** [COMPILER.md](docs/COMPILER.md) opens with
  *What the compiler can and cannot validate*: three strengthening classes it **can** do (formal
  conformance → validate-by-redundancy → content-addressed self-verification, which is the class VRS
  moved `vrs_id` into) and a table of **inescapable blind spots** that follow from what the tier is.
  The compiler is an assembler/linker, not a truth oracle: it proves well-formed and self-consistent,
  never *true*. When you find something it "should" catch, check that table first — several entries are
  permanent by charter, and what cannot be validated is instead made **legible** (`source`, `dataset`,
  `status`, `authorship.kind`, the signatures). Adding a check that needs a reference means adding it
  to the **enricher**, not the compiler.
- **Enrichment is partly validation, by design.** The enricher is the only tier that can compare
  authored data against reality (format/compiler are inject-only). Every such check **reports, never
  repairs** — rewriting an authored value destroys the evidence of an upstream bug — and severity
  follows the mode (`best_effort` warns, `strict` refuses). Add new checks in that shape; see the table
  at the top of [ENRICHER.md](docs/ENRICHER.md).
- **The compiler's VRS check has THREE outcomes, not two.** *verified* (silent), *mismatch*
  (recomputed and different — **error in both modes**, since a substitution's id is deterministic here
  so a difference can only be corruption), and *unverifiable* (**could not be recomputed at all** —
  warning in `best_effort`, error in `strict`). An indel is **never** a "mismatch": this tier cannot
  recompute one, so it can only report that it did not check, and saying otherwise would claim a
  verdict never reached. Unverifiable covers indel/MNV, multi-allelic, position-only, no-coordinate,
  off-assembly contig, and non-GRCh38 build. Full matrix in [COMPILER.md](docs/COMPILER.md).
- **`refget_accession` RAISES for a non-GRCh38 build** (it must — a caller asking for GRCh37 should
  hear "not built", not get a GRCh38 answer). Every call site therefore has to catch
  `UnsupportedBuildError`; one that didn't used to abort a whole compile over a single row.
- **`ga4gh.vrs` is a CORE enricher dependency, not `[dev]`.** Substitution minting is stdlib in the
  format tier; indel normalization goes over the **seqrepo REST** proxy (14 pure-Python packages — the
  plan's `[extras]`/`pysam`/multi-GB-seqrepo assumption was wrong). `--offline` is the only thing that
  degrades minting to substitutions-only. Never add `ga4gh.vrs` to format or compiler: the compiler's
  verify pass is stdlib on purpose.
- **The two gene-constraint routes are different releases.** The live `gnomad_constraint` API field
  serves **v2.1.1**; v4.1 ships only in the bulk TSV. They carry different `dataset` labels, and
  `dataset` is inside the fact set. Don't "fix" a test that asserts they differ.
- **An rsID is position/multi-allelic-level, not per-allele.** One rsID (`rs33922842`) legitimately spans
  pathogenic + benign + uncertain alleles at one locus, so clinical identity keys on `variant_key`+
  genotype, never rsID. The reverse pos→rsID back-fill is therefore **allele-aware**
  (`resolver._lookup_rsid_candidates`, shared by `clinvar`): 0 allele-exact candidates → leave `rsid`
  null (don't guess); 1 → attach; ≥2 (a dbSNP merge) → deterministic pick + `status="ambiguous"` +
  `ResolutionRow.rsid_alternates`.
- **`enrich()` treats an existing `resolution.csv` beside the spec as authoritative** (merged, never
  clobbered) — and so do the two new passes for `frequencies.csv` / `gene_metrics.csv`, and VRS minting
  for an existing `vrs_id`. To regenerate after a machinery change you MUST **delete the sidecar first**,
  or stale rows silently persist (this bit me while regenerating the reference example).
- **Rate limits are load-bearing in `gnomad.py`.** 10 requests/IP/60s, so everything is batched (20
  aliases; 29 returns HTTP 400) behind a 6s pacing gate on an **injectable clock** — tests prove the
  interval without really sleeping. Per-alias GraphQL errors must never sink a batch; a *pathless* error
  must raise (it's our broken query, and swallowing it looks like "nothing found").
- **Reverse dropping `rsid_alternates` is NOT a bug — closed, don't re-flag it.** This was filed as an
  open loose end and is neither open nor fixable in the writer. `_write_resolution_csv` rebuilds the
  table from `weights.parquet`, which by design carries **no provenance at all** (it already resets
  `source="reversed"`, `status="resolved"`, blank `fetched_at`). `rsid_alternates`/`rsid_current`/
  `rsid_status` are outside the fact set *precisely* so they never reach the artifact, so the data does
  not exist for reverse to emit; adding the column names would produce a permanently empty header.
  Recovering them after a round-trip means re-running the enricher.
- **Resolution must be REVERSIBLE — read [COMPILER.md § Resolution](docs/COMPILER.md) before touching
  it.** One rule: `compile → reverse → compile` reproduces the module, or `strict` refuses. The finite
  matrix of authored-shape × mishap is enumerated and enforced in
  `compiler/tests/test_resolution_matrix.py`; a new resolution behaviour adds a row there.
  - **`authored_ident` is what makes it work.** It records which of `{rsid, chrom, start, ref, alts}`
    the author supplied, stamped at load beside `variant_key` and materialized to `weights.parquet`.
    Reverse re-emits exactly that shape. `variant_key` **cannot** substitute for it: it answers "which
    variant is this", not "what did the author write" — identical for an rsid-only row and an
    rsid+coordinate pair, and after expansion it is the per-locus allele id with no trace of the rsid.
  - **An expansion collapses back to ONE authored row on reverse.** Until 0.5 it emitted N position-only
    rows, which moved `content_signature` on every rsid-authored module *and* wrote each locus out
    carrying the single authored genotype — fabricating annotations for loci that genotype cannot
    describe (three such rows in `reference_examples/pathogenic_clinvar/`).
  - **A locus that cannot host the authored genotype is dropped from the expansion**
    (`resolution.genotype_fits`). The predicate is **shared three ways** — the compiler, the enricher's
    deprecated DuckDB path (digest parity is a documented guarantee) and `enrich()`'s forward
    rsid→loci resolution, which since this round leaves such a record out of `resolution.csv`
    entirely. Resolution is allele-aware in BOTH directions now; the reverse back-fill always was.
  - **`withdrawn` refuses in BOTH modes**, unlike `merged`/`absent` (strict-only). Nothing automated
    emits it — the API cannot tell a retraction from a never-assigned id — but it is a real vocabulary
    member for curator-recorded retractions and for a future source. Don't drop it as dead code.
  - **`ambiguous` is stable and still refuses in strict.** The enricher writes ONE row (deterministic
    pick + `rsid_alternates`); a two-row fixture is fabricated and will invent an instability that does
    not exist. Strict refuses because a pick among equals is not a finding, not because anything is lost.
- **The allele-membership check compares against the UNION of every locus a key resolves to**, on the
  authored rows before `resolve_from_table` — a per-expanded-row comparison flags the siblings the
  genotype was never about. Severity is the mode ladder, never an unconditional error. Pinned by tests.
- **The ClinVar `clin_sig` cross-check is the one check where `strict` does NOT escalate** — it warns in
  both modes, deliberately, because failing would make the format arbitrate a clinical dispute. The
  reason is documented at the call site; don't "fix" the inconsistency.
- **`absent` for an rsID means typo *or* withdrawn, and the API cannot separate them.** `rs11273140`
  (withdrawn) and `rs2000000000` (never assigned) return byte-identical responses. `VALID_RSID_STATUS`
  is `{live, merged, absent}` — there is no `withdrawn` member because nothing could ever produce it,
  and the message names both readings. A test asserts the equality on the *recordings* so a future dbSNP
  release that separates them fails loudly.
- **Existence vs retrievability for citations.** A paywall hides the *fulltext*, never the PubMed
  record — `exists` is answered for paywalled work. The real gaps, both now covered: citations PubMed
  does not index at all (preprints/books/datasets → **Crossref**, checking the *authored* DOI, since
  the derived one exists by construction) and quote-checking for paywalled papers (→ the **abstract**,
  which Europe PMC serves for non-OA records in the same response). `quote_source` records how far the
  search reached because a hit and a miss are not symmetric — an abstract miss is not a verdict.
  Google Scholar is rejected, not deferred: no API, and automated querying violates its terms.
- **A thread-based regex timeout is a trap.** `re` cannot be interrupted, threads cannot be killed, and
  the interpreter joins `ThreadPoolExecutor` threads at exit — so the obvious implementation returns
  `None` on schedule and then hangs the process on the way out. `literature.regex_matches` uses a
  killable child process. Don't "simplify" it back to a thread.
- **For rsID merge status, NCBI is the oracle — not Ensembl.** Ensembl resolves *some* merged rsIDs
  (`rs77121243` → `rs334`) and returns **HTTP 400 on others** (`rs3216883`, which dbSNP correctly
  reports as merged into `rs3051860`), so Ensembl alone would misclassify a merged rsID as
  unresolvable. `esummary db=snp` is batched and authoritative: `snp_id` != requested + `merged_sort=1`
  means merged, an `error: "cannot get document summary"` record means absent. **There is no distinct
  "withdrawn" state**: an rsID retracted for mapping/clustering errors (`rs11273140`) is byte-identical
  to one never assigned (`rs2000000000`) across esummary, esearch and Ensembl, so a message about an
  absent rsID must name *both* readings — typo vs withdrawn-and-the-annotation-may-be-worthless — and
  assert neither. (`misc/rs_unsupported_b157.txt` looks like a withdrawn registry and is not; it is a
  one-off build-157 ClinVar-parsing incident list.) And when picking a negative-test rsID, check it:
  `rs999999999` looks synthetic but is a real variant at chr6:58247859.
- **Network tests are opt-in:** `JUST_DNA_NETWORK_TESTS=1` runs the live gnomAD query, the seqrepo
  refget re-derivation, and indel-normalization round-trips. They pass; they just aren't run by default.
- **PharmGKB is now ClinPGx, and every PGx upstream is research-only.** `api.pharmgkb.org` was
  **retired 2026-07-20** and no longer resolves; the successor is `api.clinpgx.org` with paths and
  formats unchanged. ClinPGx is the umbrella that merged PharmGKB + CPIC + PharmCAT, so **CPIC is not
  an unrestricted alternative** — `cpicpgx.org/license/` 302-redirects to the ClinPGx data usage
  policy. All three sources (ClinPGx, CPIC, PharmVar) are **CC BY-SA 4.0 plus a contractual no-sale
  clause**, so none is sellable: don't read a bare "CC BY-SA" line as permission to sell, read the
  surrounding terms (`docs/pharmvar_lic.txt` §3 is the PharmVar one). Ensembl/dbSNP already cover
  rsID→coordinate, so never wire ClinPGx/CPIC as a resolution link — that keeps the coordinate layer
  unrestricted. PharmVar needs an **`Api-Key:` header** (not `X-API-KEY`) at **2 rps**, and its ToS §2
  makes the key personal — never bake one into a module, fixture, or snapshot. API schema:
  `docs/pharmvar_api_docs.json`.
- **PharmGKB clinical annotations are per-genotype — `(variant_key, drug)` is not a key.** 4,618 of
  5,113 carry exactly three genotype rows, sometimes opposed (rs4149056/simvastatin: CC/CT
  "decreased", TT "increased"), so `PharmVariantRow.genotype` is in the dedup key. Its grammar lives
  on `AuthoredModel` — shared with `VariantRow`, so don't re-declare it. Route haplotype-keyed
  annotations (`*1`) to `DiplotypeRow`; skip symbolic alleles (`del/del`, 177 rows) as **RM5** rather
  than widening the nucleotide grammar. PharmGKB writes `CC`; canonical form is `C/C`, since `CC`
  would otherwise parse as a single two-base allele — disambiguate using the *resolved* ref/alt.
- **`(variant_key, drug, genotype)` is STILL not a PharmGKB key** — one variant+drug carries several
  distinct annotations (rs4149056+simvastatin is Metabolism/PK 1A, Efficacy 3 AND Toxicity 1A). 1,199
  of 17,380 triples collide; 839 separate by `phenotype_category`, 283 only by `annotation_id`. The key
  is `(variant_key, drug, genotype, phenotype_category, annotation_id)`. **Any code that indexes
  ClinPGx by the bare triple has this bug** — the first cross-check did, and reported correctly-authored
  levels as stale. Look it up by `annotation_id`, then category, and report ambiguity rather than
  comparing against an arbitrary candidate.
- **A runtime pass may not depend on a `[dev]` package — read snapshots with duckdb, not polars.**
  `polars` is `[dev]` in the enricher (builders only); `duckdb` is core. `clinpgx.py` first read its
  snapshot with polars, which made a *runtime* cross-check unusable on a plain
  `pip install just-dna-enricher`. `clinvar.py` had it right: builder in polars, pass in duckdb. Check
  which side of that line new code sits on.
- **Licensing lives as DATA in `sources.csv`, never as a table in the compiler.** A source→licence map
  in `just_dna_compiler` would give it a source convention (Principle 2, tightened in 0.5) and an
  un-injected reference — and it goes stale (both halves of one did inside 0.5). The enricher reads the
  terms from the bytes it downloaded and pins them with `license_sha256`. Three rules the tests pin,
  don't "simplify" any of them: **only the `annotation` layer taints** (a coordinate is a fact Ensembl
  reports identically, so marking it viral is a false positive); **most-restrictive-wins module-wide**
  (a permissive source can't launder a restricted one); and **`None` ≠ `False`** on
  `share_alike`/`commercial_use` (unknown terms are undetermined, never permitted).
- **A pass that consults a source must WRITE its `SourceRow`, via `licensing.merge_sources_file`.**
  Building the row is half the job; the compile gate and `manifest.sources` read `sources.csv` and
  nothing else, so a row that is only returned is a source the module cannot account for. `clingen.py`
  returned one and never wrote it — permissive terms (CC0) made it look harmless, but CC0 still asks
  for attribution and the table exists to carry it. The helper does the load-merge-write in one place
  and takes the caller's own error type; don't grow a third private copy of that wrapper.
- **The compile gate is data-driven; a `--non-commercial` CLI flag would be charter-illegal.** It
  refuses when an annotation-layer source forbids sale and the module records no declaration, reading
  only injected `sources.csv`. A *flag* cannot be recorded in the artifact — `reverse_module` rebuilds
  `module_spec.yaml` from parquet alone — so `compile → reverse → compile` would refuse on the third
  step (P7). The gate sits immediately before `output_dir.mkdir()`, which is why `sources.csv` is
  parsed there rather than with the other fact tables (they load after mkdir). It refuses in **both**
  modes; `strict` means "reproducible artifact", an unrelated axis (P5).
- **`declared_use` (`--use`) is a THIRD axis, not a mode.** `mode` says how hard to fail on a finding;
  `declared_use` says who is using the data. Three states, so not a bool pair — defaulting either way
  would make the tool assert a purpose for the user. A forbidding source is *skipped* on `unstated`
  and *refused* on `commercial`, at acquisition (nothing is fetched), in both modes.
- **The Ensembl snapshot's `alt` is PIPE-joined; every other link uses commas.** A multi-allelic site
  is one snapshot row (`A|C|T`), not one row per alt. `resolver._snapshot_alleles` normalizes at that
  boundary — don't remove it, and don't "fix" it by widening `genotype_fits` instead (the locus-dict
  contract is comma-separated, and the snapshot is the deviation). This silently broke *all*
  cache-resolved genotyped variants until 0.5: the comma-only split made `A|C|T` one opaque allele, so
  the allele-aware filter dropped every locus and `rs4244285` with genotype `A/G` came back
  `not_found`. Unit fixtures were comma-separated, so only a real cache showed it — when adding a
  resolver fixture, use the pipe shape for multi-allelic sites.
- **Resolution reads `pharm_variants.csv` and `haplotypes.csv` too, not just `variants.csv`** (0.5,
  `enrich._collect_subjects`). PGx modules carry no `variants.csv`, so they used to enrich to an empty
  `resolution.csv`. Subjects dedupe by `variant_key` with **`variants.csv` first** — it alone carries
  `alts`, a fact column, so a PGx row winning would move `artifact.digest`. PGx tables key **without**
  `alts`; a `HaplotypeRow` passes its defining `allele` to the shared `genotype_fits`.
- **CPIC/PharmVar coordinates are 1-based — do NOT convert.** Despite the `start` docstring saying
  "0-based", the pipeline stores Ensembl's 1-based position (`rs1135071` → 5226799 in both), and CPIC
  `sequence_location.position` / PharmVar `NC_……:g.` use the same convention. The instinctive `-1`
  introduces an off-by-one. Two more CPIC traps: `variantallele` uses **IUPAC ambiguity codes** (`R`),
  which `HaplotypeRow.allele` rejects; and activity scores are **inequality strings** (`"≥3.0"`), not
  numbers, so they don't drop into `MeasureBinRow`'s numeric bounds.
- **The digest asymmetry decides what is urgent while 0.5 is unpublished.** `integrity.file_entries`
  **skips missing files**, so a **new optional table** never moves the digest of a module that does not
  carry it (additive any time), while a **new column on an existing parquet** moves every module's
  digest (major-only once 0.5 ships). That is why the pre-cut batch is columns and the heavy items
  (`predictions.csv`, `gene_validity.csv` — RM23/RM24) are roadmapped rather than rushed.
- **Adding an authored column is exactly three touch points, and the third is the one that gets
  missed.** The pydantic model; the compile-side row dict + polars schema in `compiler.py`; and the
  **reverse-side `fieldnames` list + `_scalar_cell` mapping**. A column missing from the reverse list
  round-trips as silent data loss, which is why every new column gets a round-trip test. Table kinds
  under `_TABLE_KINDS` are exempt — `_build_table`/`_write_table_csv` are generic over `model_fields`,
  so `DiplotypeRow.recommendation_strength` needed no compiler change at all.
- **`model_fields` is NOT the authored surface — generators must use `base.authored_field_names`.**
  `VariantRow.variant_key` and `authored_ident` are declared fields (carried in memory, materialized
  to `weights.parquet`) that the compiler *stamps* and `reverse_module` deliberately never writes
  back. Anything that turns a model into CSV columns for a human — `draft.blank_template`,
  `draft.append_rows`, `reference.authoring_reference` — has to skip them, and it must skip them by
  the field's own `COMPILER_MANAGED` marker, **never by name**: `FrequencyRow.variant_key` is the same
  name and is genuinely authored and required, so a name set hides a column an author must fill. Both
  hand-kept exclusion lists that preceded the marker were wrong — `reference.py`'s named only
  `variant_key` and never learned about `authored_ident`; `draft.py` had none, so it wrote a
  `variants.csv` the compiler then refused to load (`authored_ident` renders as `rsid` and does not
  reload as a `list[str]`). The bug survived a green suite because every drafting test used a PGx or
  binning table, and no model but `VariantRow` has a stamped field. **When adding a drafting provider
  or any new model-driven generator, test it against `variants.csv` specifically.**
- **A vocabulary binding lives on the FIELD, and it carries the members — `base.vocabulary`.** The
  authoring reference's vocabulary block used to be a hand-kept dict and drifted twice: it never
  learned about `recommendation_strength`/`phenotype_category` (0.5), and it filed `actionability`
  under `open_recommended` while `VariantRow` *rejects* a non-member — a drift in **closedness**, not
  membership, which is why the marker carries a `closed` flag and not just a list. The marker holds
  the frozenset's members rather than a name to look up, because a registry in `vocab` cannot import
  `pgx` (the cycle `base`'s dependency note exists to avoid) and a registry elsewhere is a second
  hand-kept list. Rule for where a binding goes: **wherever its validator is** — shared validator →
  `base.SHARED_VOCABULARIES`; model-specific validator → that model's `Field(...)`. Never mark a
  field nothing enforces: `StudyRow.chrom` and the PGx `chrom`s run no chrom validator, so they carry
  no marker, and the guard test catches it in both directions.
- **Requiredness has THREE shapes, and the middle one is invisible to pydantic.** `is_required()` is
  false for `MeasureBinRow.measure_kind` and `unresolved` — they have defaults — but they are not
  `Optional`, and `_load_csv_rows` turns an empty cell into `None` **and keeps the key**, so the model
  gets `None` instead of its default and fails on type. `blank_template` + `required_fields` therefore
  told an author to fill three columns and produced a file the compiler refused, naming a fourth.
  Use `draft.field_category` (`required` / `defaulted` / `optional`) and `draft.authoring_requirements`
  — which also reports `REQUIRED_ANY_OF`, the "rsid **or** chrom+start" rule that is a model validator
  and which no per-field flag can express.
- **A generated stub must be unable to compile — `vocab.TEMPLATE_PLACEHOLDER`, guarded before
  coercion.** The guard is `mode="before"` on purpose: an unreplaced stub in `start: int` then reads
  as "unreplaced template placeholder in column start", not "Input should be a valid integer". Do
  **not** reuse `MeasureBinRow.unresolved` for this — that sentinel means "no measurement at read
  time" and is designed to *compile*; two opposite lifecycles on one field is the overloaded-axis
  anti-pattern (P5).
- **Scaffolding refuses per FILE; drafting refuses per ROW — and the difference is derivable.** A
  file-level rule self-defuses for `draft` (you re-run it per gene), but you scaffold a module once,
  and a stub row has no natural key to merge on because its key columns *are* the placeholder.
  Refusal is per file, not per run, or a module could never gain a second table kind. Both use the
  same definition of absent — a zero-byte file counts as missing.
- **A hint may not fill a cell a Class-2 check cross-examines — `hints.REDUNDANCY_BEARING`.** Class 2
  works because two *independently-authored* things must agree. Fill `chrom`/`start` from Ensembl and
  `resolution._verify` compares Ensembl with Ensembl; worse, for an rsid-only row that check never
  runs at all, so the row moves from honestly unverified to apparently verified and the compile
  reports success. Same for `doi` vs `literature._doi_conflicts` and `ref` vs
  `verify_reference_alleles`. `literature` already argued this for one field (Crossref is asked about
  the **authored** DOI, since a derived one "exists by construction"). So a looked-up value comes back
  `applied=False` with a refusal; the only thing `hints` applies is a `normalized` rewrite the model
  already performs silently on load (`DiplotypeRow` swaps its haplotype pair). A `--apply` flag on a
  lookup would ship the parked enricher-co-authoring item without deciding to.
- **"It moves the digest" is NOT a reason to refuse a row move — that argument was checked and it
  failed.** Probed: a pure reorder moves `artifact.digest` but leaves `content_signature` untouched
  (order-independent by construction), the compile → reverse → compile fixed point still holds,
  duplicate keys are rejected so order can disambiguate nothing, and **nothing reads the append-only
  prefix property** (one test asserts it; no other code). The decisive point: an author reordering
  rows in their editor is already legal and already moves the digest, so forbidding the tool the same
  move proves too much. Mid-flight digest stability is worth ~nothing — the digest is consumed at
  exactly one moment, *publish*, and every authoring edit changes it anyway. What stays refused is an
  `at=N` index (it buys nothing an editor does not) and a `sort`/`canonicalize` command (every row
  moves, no local reason for any of them). What shipped is `append_rows(..., group_by=…)` /
  `place_rows`: **the tool picks where, the caller never supplies an index.** Shifted rows keep their
  cells byte-for-byte — `_render_existing` re-reads them as text — and `DraftReport.shifted` names them.
- **A partial row is validated by OMISSION, and matches on `match_on`, not the natural key.**
  `draft.PartialRow` exists because ClinVar publishes **alleles, not genotypes**, and
  `VariantRow.genotype` is required: zygosity is inheritance-mode interpretation the source does not
  state, so `clinvar_draft` writes what is published and leaves `genotype` as `TEMPLATE_PLACEHOLDER`.
  Two traps. (1) Validating the non-stubbed cells by substituting dummy values needs a per-column
  value oracle — a hand-kept list again; instead the row is built **without** the stubbed columns and
  errors located on them are discarded. (2) The natural key runs *through* the stub, so it cannot
  decide sameness; `match_on` (the identity columns) does, which is what makes a re-draft after the
  human fills the genotype report `already_present` instead of appending the stub a second time.
- **A drafting provider fills identity WHOLE or not at all.** rsID, else the complete
  `chrom`/`start`/`ref`/`alts` — never a subset. A lone `alts` on a position-only row makes
  `derive_variant_key` mint a VRS `ga4gh:VA.…` id instead of `chrom:start:ref`, so a partial
  coordinate silently changes *which variant the row is*.
- **Derived-not-stored is the house pattern for a convenience number**: store the exact parts in the
  CSV, materialize the derived value into parquet as a `@property`, and let it fall away on reverse
  because it is not a model field. `FrequencyRow.allele_frequency` (AC/AN) and
  `StudyRow.neg_log10_p` (mantissa/exponent) both do this. For p-values it is load-bearing rather than
  cosmetic: float64 goes subnormal below ~1e-308 and is flatly `0.0` below ~5e-324, so a single float
  column would render a panel's strongest association as its weakest.
- **Store a source's value verbatim — EXCEPT when the encoding lies about its own order.** ClinGen's
  dosage codes are `{0,1,2,3,30,40}` where `30` = "autosomal recessive" and `40` = "dosage sensitivity
  unlikely", so sorting the raw numbers ranks `40` above `3` (sufficient evidence). They are decoded to
  `VALID_DOSAGE_SENSITIVITY` terms at the enricher boundary (`vocab.DOSAGE_SENSITIVITY_BY_CODE` holds
  the total mapping). Verbatim is right for an *identity* (a star allele, an accession); it is wrong
  for a code a consumer will sort. Also: that file writes `"Not yet evaluated"` in the
  triplosensitivity column for 210 of 1,520 genes — an absence, and what makes `int(cell)` crash.
- **`redistribution` is a third licensing axis, recorded but NOT gated.** CC BY-NC forbids sale and
  allows sharing; academic-use-only (OMIM, dbNSFP) forbids both. The compile gate deliberately keys
  only on `commercial_use` — a distribution right is not a *use*, so `declared_use` is the wrong axis
  to resolve it against (RM27). Don't "finish" the gate without doing that design.
- **Drafting appends, it never mutates — that word is the whole line.** `just_dna_compiler.draft`
  appends rows into an authored CSV at **row** granularity (a file-level "refuse if it exists" rule
  self-defuses after the first gene and makes a multi-gene module unbuildable). A row whose key exists
  is reported (`already_present` / `differs`), never rewritten; drift on existing rows is
  `pgx.enrich_pgx`'s job. Dedup keys on the compiler's own `_TABLE_DUPE_KEYS` so an append cannot
  create a row the compiler then rejects, and rows go **at the end** because authored row order is
  load-bearing for the digest. This is *not* the parked enricher-co-authoring item: appending leaves
  `content_signature` a function of the authored bytes; editing a cell a human wrote would not.
- **Probe a source's real file before modelling it; the docs lie by omission.** Every non-obvious
  decision in this round came from a probe, not from a spec: CPIC's recommendation classifications
  (five values, `n/a` among them), ClinGen's non-ordinal codes, the ACMG SF list existing only as an
  HTML table (so the check was deferred rather than built on a scrape), and Orphanet's IRI — `ORPHA:558`
  is a term at `…/ORDO/Orphanet_558`, so composing `stem + PREFIX + "_" + local` queries `ORPHA_558`
  and gets **HTTP 200 with zero terms**, which is indistinguishable from "this id does not exist". That
  last one is the shape to watch for: a lookup bug that surfaces as a false finding about the module.
- **Dogfood data is git-ignored** (`/data/` now in `.gitignore`): local ClinVar VCF at
  `/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz` (2026-06-27); the built snapshot the example used
  is `data/interim/clinvar`. `resolution.csv` is provisional in 0.5, so `artifact.digest` changes for
  alt-bearing coordinate modules are acceptable pre-freeze.
- **A row is stamped before the module is known — so anything build-dependent must be re-derived by
  the compiler.** `VariantRow._freeze_identity` runs at construction, where `module_spec.yaml` is not
  in scope, so it always took `derive_variant_key`'s GRCh38 default. A `genome_build: GRCh37` module
  therefore minted GRCh38 VRS ids, silently, for years of the design — the `build` parameter and its
  fall-through-rather-than-lie guard both existed and were simply never reached.
  `compiler._restamp_for_build` fixes it after load, at **both** load sites (`validate_spec` and
  `compile_module` each read their own copy; fixing one leaves the artifact wrong). When adding
  anything else that depends on the spec, check whether the model can possibly know it.
- **A warning computed post-resolution is discarded — the second `_cross_validate_variants` call takes
  errors only.** That is right for a warning about authored cells and wrong for any whose input
  resolution fills. It made the non-diploid guardrail invisible to every rsID-authored row, i.e. to
  everything a drafting provider emits. `_check_contig_ploidy` now runs where `chrom` is final and
  keeps a pass inside `validate_spec` (which has no resolution step), de-duplicated on the message.
- **`chrom=Y` is NOT "never diploid" — PAR1 and PAR2 are diploid in every karyotype.**
  `vrs.in_pseudoautosomal_region` is three-valued and `vrs.PAR_GRCh38` holds the intervals; they are
  assembly constants of the same class as `REFGET_GRCh38`, not an un-injected reference. A PAR rsID
  (`rs6603251` → X:359845 **and** Y:359845) also expands to two rows the author never chose — one
  place, two contigs, tracked as RM32.
- **`genotype_fits` compares allele STRINGS, so one indel spelled two ways does not match.** ClinVar's
  `X:634689 CAG>C` and Ensembl's `X:634690 AGAG>AG` are the same 2 bp deletion; the row resolves to
  `not_found`. The message names both readings now and must keep doing so — it used to assert "a
  different variant sharing the rsID", sending an author after a dbSNP merge that does not exist.
  Normalization is RM31 and is not a small change: the predicate is shared with the reference-less
  compiler.
- **Before adding a table-level check, ask whether its rules are jointly satisfiable.** Inclusive
  bounds + overlap-is-an-error + any-hole-is-a-warning cannot all hold on a continuous measure, so
  every `allele_fraction` table warns forever (RM35). Integer kinds tile cleanly, which is why nobody
  noticed.

## The design cycle (the order of things)

Feature ideas move through **one loop**; the docs are its stages, and a design task should walk them
in order rather than jumping to code:

1. **Feedback** — a consumer's field report → [docs/CONSUMER_FIELD_NOTES.md](docs/CONSUMER_FIELD_NOTES.md),
   [docs/CONSUMER_ROUND2_AND_0_5.md](docs/CONSUMER_ROUND2_AND_0_5.md)
2. **Usage → blockers → solvability** — run each use case against the current bricks: *enabled*,
   *consumer-side* (the format owns nothing), or a *gap* closable additively? →
   [docs/USE_CASES.md](docs/USE_CASES.md)  ← **start a design task here**
3. **Means → draft schema → decision** — the proposed shape + charter check + open questions →
   [docs/PROPOSAL_0_5.md](docs/PROPOSAL_0_5.md) (0.5 design threads),
   [docs/PROPOSAL_0_4_1.md](docs/PROPOSAL_0_4_1.md) (the 0.4.1 patch). *(0.4's proposal shipped and
   was retired — its decisions live in [docs/CHANGELOG.md](docs/CHANGELOG.md).)*
4. **Conclusion — how to author it now, with these bricks** → [docs/REFERENCE_EXAMPLES.md](docs/REFERENCE_EXAMPLES.md)
5. **Terminal** — either **shipped** (schema + compiler; recorded in COMPILER.md coverage) **or**
   **deferred** (a recognised gap parked as an `RMn` roadmap item in ROADMAP.md).

`USE_CASES.md` and `REFERENCE_EXAMPLES.md` are the **same use cases at two points in the loop** —
questions (what blocks?) vs answers (author it like this). A blocker is never a dead end: it is
dissolved (was consumer-side), closed additively, or explicitly parked. See *The feedback → schema
cycle* in `USE_CASES.md`.

## Coding standards

- **Dependency tiers are sacred** (CONSTITUTION Goal 2 + the 0.5 amendment): never add a heavy dep to
  `just-dna-format` (pydantic + cryptography only); `just-dna-compiler` is pure-Python since 0.5
  (polars/pyyaml/typer — **duckdb-free**). Network **and HuggingFace** live **only** in
  `just-dna-enricher`. Never pull Dagster / LLM SDKs into any tier.
- **No network in format/compiler; inject-only** (Principle 2): they never download — the compiler
  consumes an injected `resolution.csv` (or, deprecated until 1.0, an injected reference) and skips
  with a warning when nothing is injected. Fetching is `just-dna-enricher`'s job.
- **Data-agnostic — a north star, not a totality claim.** A module and its compiled artifact are
  pure *annotation*: lookup tables and bounded rules mapping a quantity/genotype to a phenotype. They
  carry **no sample data, no genotype under test, no measured value** — the measurement is supplied by
  the consumer at query time (the format supplies the table; the consumer supplies the call). *But*
  the pydantic schemas are a **generalization over a practical subset** of real data items — concrete
  loci, callers, and realistic value ranges — i.e. an implicit data model with an untracked empirical
  footprint, not an all-encompassing universal one. Be explicit that a shape generalizes known cases
  rather than pretending it covers everything: when a real data item doesn't fit, that is a schema gap
  to widen *additively*, not a consumer error. (This is why `copy_number`-as-a-measured-value was
  wrong — the module never holds the measurement — yet the *range* shapes are still only as general as
  the cases they were generalized from.)
- **Human-authorable ⇔ machine-precise — a gate on every schema change.** The authored DSL
  (`module_spec.yaml` + CSVs) is a *duality*: it must be **both** a legible, human-authorable artifact
  **and** a formally algorithmizable, machine-precise one. The compiled parquet is already the
  pure-machine form — **if we only wanted machine precision we would ship parquet-only.** The DSL
  exists for the human. So gate any schema change on: **"will this burden the rare human author?"**
  Modules must never read like enterprise-DB internals — alien, sprawling, machine-code-like. Corollary
  — **one CSV = one concern; compose from optional table kinds**: the SNP core (`variants.csv` +
  `studies.csv`) stays minimal; a module includes only the table kinds it uses; a PGx / PharmGKB / PRS
  module adds its own focused table (`diplotypes.csv`, `pharm_variants.csv`, `pgs.csv`) rather than an
  empty `variants.csv` or a foreign domain's columns on every row. When human-legibility and
  machine-precision tension, the parquet absorbs the precision; the DSL keeps the human shape.
- Type hints mandatory; **pathlib** for paths; **absolute imports only**; **no inline imports** (a
  guarded module-level `try/except ImportError` for optional deps is the only exception).
- **Avoid nested try/except** — it is a nightmare to read and debug, and usually just swallows the
  real error. Use it only where an error is an unavoidable, handled part of the use case (that guarded
  optional-dep import is that case).
- **Polars in the compiler**: prefer lazyframes (`scan_parquet`) and streaming (`sink_parquet`), and
  pre-filter before joining so you never materialize more than needed. (The format tier stays
  polars-free — Goal 2.)
- **Typer for every CLI**; the root package's `[project.scripts]` owns the user-facing command. If a
  `uv run <cmd>` wrapper goes stale after a dependency upgrade, bump this package's version and
  re-run `uv sync` — never rename the command to dodge a stale wrapper.
- **Standard-library `logging`** for diagnostics — never `print`.
- **Heed terminal warnings, deprecations especially** — they are the signal that an API moved since
  training. Read and fix them; don't paper over them.
- **No placeholder paths or fabricated example values** in code (`/my/custom/path/`, dummy digests, …).
- **Refactor internals aggressively** — don't keep dead code or an old API around for nostalgia. The
  one exception is the wire/artifact **contract**: it obeys additive-within-a-major (Principles 3/8),
  never "no legacy support." Internals are free; the schema and `manifest.json` shape are not.
- **Versions read from `pyproject.toml`** (via `module.version`); never hardcode a version string in
  `__init__.py`.
- **Avoid `__all__` / pure re-export `__init__.py`s** — they obscure where a symbol actually lives.
- Pydantic 2 for all data models. Constrained vocabularies are `frozenset[str]` + a validator, never
  `Enum`/`Literal` (Principle 6).
- **Authored row models inherit `AuthoredModel`** (`just_dna_format.base`), never `BaseModel` directly.
  It carries the reserved-namespace guard (`extra="forbid"` + the `reject_reserved` before-validator)
  and the shared field validators (`rsid`/`trait_efo_id`/`direction`/`clin_sig`/`stat_significance`/
  `evidence_level`/finite-`effect_size`). Don't re-declare `model_config` or re-copy those validators
  per model (that per-model duplication is the anti-pattern being unwound); when a validator is
  identical across ≥2 models, move it onto the base with `check_fields=False`. Keep only field-specific
  rules on each model.
- **The reserved namespace (`vocab.RESERVED_NAMES_0_4`) is only for names expected to become real
  module columns later** (Principle 5) — *not* a catalogue of barred names. `extra="forbid"` already
  rejects any unknown/misspelled column generically, so barring a specific non-feature is arbitrary
  (barring `caller` is as pointless as barring `pasta_recipe`). Before reserving a name, ask: *will a
  release plausibly build this as a module column?* A reserved name earns a specific author-time
  diagnosis (`vocab.RESERVED_NAME_REASONS` via `reject_reserved`); everything else gets the generic
  message. (This is why `caller`/`caller_version` were dropped — consumer-side measurement provenance
  with no module-side meaning — while `reference_db`, a join-target-DB hint, was kept.)
- **Additive within a major** (Principles 3/8): new columns are optional; a required field is never
  demoted; anything that changes `artifact.digest` bytes (parquet column set/types) is major-only —
  *except* while a version is still unpublished, where the digest is not yet frozen.
- **Round-trip must stay lossless and idempotent** (Principle 7) — prove it with tests, don't assume.
- **CPIC recommendations are keyed by (gene phenotype, drug, POPULATION) — and the populations
  disagree.** Clopidogrel has three (`CVI ACS PCI`, `CVI non-ACS non-PCI`, `NVI`); the same Poor
  Metabolizer diplotype is `strong` in one and `moderate` in another. `DiplotypeRow` has no
  population column, so drafting them all collides on `_TABLE_DUPE_KEYS` and defaulting to one would
  assert a clinical context the author never chose — `draft --drug` therefore *refuses* and lists the
  choices when several exist. Drug rows sit **beside** the phenotype rows (the key includes `drug`),
  they do not replace them. And `recommendation_strength` is CPIC's; `evidence_level` is PharmGKB's;
  they are different axes and a provider must fill only its own.
- **The house algebra is THREE-valued: true / false / unknown — and `None` is never `False`.** This
  is the single rule behind a dozen separate-looking ones: `SourceTerms.share_alike`/`commercial_use`
  (unknown terms are undetermined, never permitted), `CrossrefClient.exists` (`Optional[bool]`, so
  "could not ask" ≠ "no such work"), `LiteratureRow.quotes_found` (null, not zero, when no text could
  be read), `--offline` reporting `unchecked` rather than `absent`, `unresolved` for a missing
  measurement (never the lowest bin), `requires_callable` for an absence nobody called, and
  `hints`/`lookup` returning findings rather than verdicts. When adding anything that answers a
  question, give it three outcomes, not two — and when the answer is unknown, **withhold**: never
  report, never negate. The one place this gets subtle is combining them: use **Kleene** semantics,
  not withhold-on-any-unknown, because `unknown AND false` really is `false` (an ε4-gated conclusion
  is decidably false at ref/ref whatever the call quality was) and collapsing that loses real answers.
- **A drafting provider's skip guard must be DERIVED from the model's rule, not restated beside it.**
  `pgx_draft` skipped a CPIC variant when "no rsID *and* no position", while `HaplotypeRow` requires
  an rsID **or** chrom AND start — and CPIC publishes no chromosome (`sequence_location` carries
  genesymbol/dbsnpid/position and nothing else, probed 2026-08-03). So `draft --gene CYP2C9` died on
  an unhandled pydantic error while `--gene CYP2C19` was fine: 18 CYP2C9 defining variants have a
  position and no rsID, 14 in TPMT, 4 in NUDT15, and none in CYP2C19. Test the guard against the
  model case-by-case rather than asserting a message — doing that immediately found a second bug,
  `chrom` never being passed to the constructor at all.
- **Every provider must write its `SourceRow` — check the newest one, not just the old one.** The
  rule was recorded for `clingen.py` and then `pgx_draft` shipped without it, which is the worst
  instance: CPIC is CC BY-SA **with a no-sale clause**, so a module drafted entirely from it carried
  no `sources.csv`, and the compile gate keys on that file and nothing else — the restriction simply
  vanished. A test that strips `declared_use` and asserts the compile refuses is what keeps the row
  load-bearing rather than decorative.
- **Distinguish "the source did not say" from "the source said something we cannot hold", and
  aggregate repeated warnings.** CPIC's `n/a` means *not scored* (an absence → an empty cell);
  `≥3.0` is a real bound the numeric columns cannot express. Both were reported as "an inequality
  rather than a number", one line per row — ~600 lines for CYP2C19 and 2,184 for CYP2C9, which
  buries every other finding a run produces. Say which case it is, once, with the count.
- **A star allele can be *used* without being *defined*.** `allele_function.csv`/`diplotypes.csv`
  name alleles that `haplotypes.csv` may never define, and a consumer's caller can then never emit
  one — every row about it is dead. `_cross_validate_haplotype_definitions` warns (Class 2), only
  when `haplotypes.csv` is present, since a module leaning on an external caller's definitions is
  legitimate. `*1` is exempt: the reference allele is defined by carrying no variants.
- **Dogfooding means using the shipped surface to do real work — and a capability the tool LACKS is
  the result, not an obstacle to route around.** The moment you reach for an ad-hoc script, a raw
  `httpx` call, or a hand-written query to get past something the product cannot do, the exercise has
  stopped producing its signal: you have proven the task is possible with *general* tooling, which was
  never in question, and learned nothing about the product. When the tool cannot do the step, that is
  the finding — record it (roadmap / field notes) and, if it blocks the work, **build it into the
  product and carry on with the product**. This happened for real: drafting an HFE panel needed
  citations, the enricher turned out to *check* an authored PMID but have no way to *find* one, and
  the reflex was to script PubMed esearch directly. That script would have produced a
  reference example while hiding the actual result — grounding evidence is mandatory for a module, the
  ClinVar snapshot carries no PMIDs, so `draft-panel` cannot produce a compilable panel on its own.
  (The same round's *good* dogfooding went the other way: drafting a real panel exposed that one rsID
  naming two alts collapsed to a single row and silently lost an allele, and that got fixed in
  `clinvar_draft`.)
- **Dogfooding is not validation.** Validation is what tests do — real fixtures, computed
  expectations, adversarial cases. Dogfooding asks a different question: *is this usable, and what is
  missing?* So do not "verify the tool's answers" with a second, independent implementation while
  dogfooding; that is a test, and it belongs in the suite. Use the tool, notice the friction, and
  write down what was not there.
- **The adversarial role, and why it pays.** Dogfooding finds friction; the sharper yield comes from
  switching roles deliberately — *be a beta-tester trying to show the libraries fail at something they
  advertise*, then switch back and fix. Two rules keep it honest, and both matter. **Attack claims,
  not gaps**: a documented deferral (RM5's symbolic alleles, VRS-for-indels) is a decision, and
  "finding" it proves nothing; what counts is where a docstring, a comment or a doc *promises*
  something the code does not do. **Use real data**: no `rs999999999`, no `e-328`. Every finding of
  the 2026-08-03 round came from a real gene, and each is a sentence that quotes the code's own claim
  back at it — `vrs.py` promised "GRCh38 and GRCh37 mint distinct, correctly non-colliding ids" while
  a GRCh37 module minted GRCh38 ids; a comment called `chrom=Y` "the false-positive-free half" while
  PAR1 is diploid in everyone; `draft-panel` asked for a `genotype` and supplied neither `ref` nor
  `alts`.
- **Pick the probe by where the schema generalized from one case.** The two blocking defects that
  round were both "the documented example only ever showed one": `REFERENCE_EXAMPLES.md` §4 shows one
  MT variant per gene, so `HeteroplasmyRow` keyed on the gene and a second real MELAS variant made the
  module uncompilable; the binning bounds were generalized from integer kinds, so a continuous measure
  turned out to be untileable (RM35). Choose a real case with **two** of whatever the example has one
  of, and a case at the edge of a stated convention (a PAR locus for "Y is not diploid", a non-GRCh38
  build for "the key names its build").
- **Turn the tool on the work you just did.** A check written in the morning is the best candidate for
  the afternoon's probe, and it will be wrong in a way its tests were not. The phase-ambiguity check
  shipped, then reported 595 ambiguities in a CYP2C19 module that has none (grouped by row instead of
  by haplotype pair), then — once fixed — told CYP2D6 authors that phase would resolve alleles the
  module defines *identically*, which phase cannot. Both were found by running it on a real 16k-row
  module, neither by re-reading it.
- **Finish each probe as a reference example with a README that names what it broke.** The module is
  the regression test and the README is the evidence; a finding recorded only in a commit message is
  not reproducible. Keep the failing observation in the test suite by demonstrating it on the *old*
  behaviour (strip the column, watch the compiler reject the real rows) rather than asserting that it
  used to fail.
- **Separate "fix it" from "surface it" before writing any code, and be strict about the line.** Fix a
  false claim, a misdiagnosis, a wall of un-aggregated warnings, a guard that is never reached. Surface
  anything where the obvious repair is itself a design decision — and say *why each candidate repair is
  wrong*, because that is the part that makes the item actionable later. RM31/32/33/35 each carry that
  paragraph; RM33's is the cleanest, since one of its two obvious fixes is charter-illegal.
- **Dogfood a P7/dedup finding before you report it — construct a *real, sensible* example against
  the actual code paths, or it is not a finding.** A round-trip/dedup "loss" that is mechanically
  possible but has no real instantiation is noise; walk the data model with a biologist's eye before
  flagging it. The standing example: `annotations.parquet` dedups on the **variant-effect pair**
  `(variant_key, conclusion, negatives)`. An audit flagged "two rows sharing that key + identical
  `conclusion`/`negatives` but differing `gene`/`phenotype`/`category` collapse to the first — a P7
  loss." It read airtight mechanically, yet it is **non-real**, and trying to build one example proves
  why: sharing a `variant_key` forces a *single locus* (a one-to-many rsid is **expanded to distinct
  coord-keys** by the resolver, so paralogs never share a key) ⟹ one `gene`; and identical
  `conclusion`+`negatives` means the *same effect* ⟹ the same `phenotype`/`category`. `gene` isn't
  even carried in `weights.parquet`, so two such rows are physically indistinguishable regardless of
  keying. The constraint set is empty — no real, sensible module hits it. The **genuine** poly-effect
  loss (one locus, two genotypes, *distinct* conclusions — het "carrier" vs hom "affected") is what
  the variant-effect-pair keying already fixed. Lesson: empirical probing + a real-example test beat a
  plausible-looking mechanistic claim; the mechanistic claim, unfalsified, was a mechanical re-flag of
  an already-closed item.
- **Deterministic ordering is load-bearing** (an implicit consequence of Principle 7, not its own
  charter rule). Parquet bytes depend on **row order**, so `artifact.digest` is order-sensitive:
  **authored row order is preserved** through compile → reverse → recompile and must stay that way.
  Never derive emitted rows, CSV/parquet contents, or manifest fields from `set`/`dict` iteration or
  from polars `mode()`/`unique()` without an explicit stable sort or tie-break (both give *no* order
  guarantee — `mode()` is unstable even call-to-call). Prefer explicit `ORDER BY` in SQL, `sorted(...)`
  /`min(...)` for picks, and first-occurrence (insertion) order for dedup. **Column order and cell
  formatting, by contrast, are normalized, not preserved** (reverse emits a fixed `fieldnames` order;
  values are stripped/canonicalized) — that asymmetry is intended. New orderings get a test.
- Use `uv sync` / `uv add`; **never** `uv pip install`. `uv run pytest` runs the suite (see *Testing*).
- New markdown (except this file / `README`) goes in `docs/`.

## Testing

- `uv run pytest` runs the suite; run it **`-vvv`** when diagnosing.
- **Real data + ground truth**: exercise the actual compile / reverse paths against real fixtures and
  **compute expected values at runtime** rather than hardcoding them.
- **Deterministic coverage**: fixed seeds or explicit filters; cover representative *and* edge cases.
- **Meaningful assertions**: prefer relationships and aggregates over existence-only checks; prefer
  set equality (`assert a == b`) over count checks.
- Hardcoding **domain constants** (vocabulary members from the spec) is fine; hardcoding **row/unique
  counts** read off a data dump is not.
- **Avoid the AI test anti-patterns**: happy-path-only tests, hardcoded counts derived from inspecting
  data, mocking a data transformation instead of running the real path, and claiming a test "would
  have caught" a bug without first demonstrating the failure on the buggy code.
- Round-trip / idempotency (Principle 7) and every new ordering get a real test — see the dogfood rule
  above; a mechanically-possible loss with no real instantiation is not a finding.
- **Async tests use `pytest-asyncio`** (kept in the dev deps for when async paths land; today there
  are none).

## Documentation & prose style

- Write in natural, human prose. Avoid AI-typical tells (em-dash pile-ups, filler transitions,
  marketing voice). Never hallucinate documentation or overpromise an unimplemented feature.
- Keep the `README` concise; deep detail belongs in `docs/`.
- Describe the format honestly: it supplies **annotation tables**, never sample data and never a
  gene–disease inference. Don't let docs imply a module measures or calls anything — the consumer
  supplies the measurement at query time (mirrors the data-agnostic rule above).
- **Self-correction**: when outdated API knowledge causes a real crash or logic failure, fix the code
  *and* update this `CLAUDE.md` / the affected `docs/` with the correct pattern so the next agent
  doesn't repeat it. Update the guides immediately whenever code is refactored.

## Data & assets conventions

- Generated and sample data lives under `data/`, **git-ignored and build-ignored** — nothing here
  travels with the repo or the package:
  - `data/input/` — input samples, where applicable
  - `data/interim/` — code-generated intermediates
  - `data/output/` — results
- Data that must **travel with the project** (a fixture a test or example genuinely needs) lives in
  `assets/`, committed.
- Any asset that exceeds **~5 MB** and must travel goes through **Git LFS**: `git lfs install` once,
  `git lfs track "<path>"`, then commit the **LFS pointer** — never the raw blob.

**Gotcha — check tree history whenever LFS is introduced; no large blob may remain in history.** A
blob committed *before* `git lfs track` stays in every past commit even after the pointer replaces it
at HEAD, so the pack still ships it. Detect it:

```bash
git lfs ls-files                       # what LFS tracks at HEAD
git rev-list --objects --all \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '/^blob/ && $3 > 5000000 {print $3, $4}' | sort -rn   # large blobs anywhere in history
```

I don't run history-rewriting operations. **If a large blob is found in history, here is the
remediation sequence for you to run:**

1. `git lfs migrate import --include="<path-or-glob>" --everything` — rewrites history, moving matching
   blobs into LFS.
2. Verify: re-run the large-blob scan above (should be empty) and `git lfs ls-files --all` (should list
   the migrated paths).
3. `git push --force-with-lease` the rewritten history; collaborators must re-clone or hard-reset, since
   history has diverged.
4. Optionally reclaim local space: `git reflog expire --expire=now --all && git gc --prune=now`.

## Related repos (read-only unless the task targets them)

`just-dna-pipelines` (compiler/discovery, depends on these libs), `just-dna-lite` (app + webui, the
reference consumer), `just-dna-marketplace` (catalog/storage/serving; consumes the `revalidate`/
`needs_upgrade` derivation these libs supply), `just-dna-agents` (MCP surface — its `get_spec_format`/
`list_colors`/`list_icons` are the drift `authoring_reference()`/`RECOMMENDED_*` replace), `just-prs`.
