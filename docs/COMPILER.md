# `just-dna-compiler` — the transform tier

The package reference for **`just-dna-compiler`**: the reference compiler that turns a validated spec
directory into a multi-parquet artifact + `manifest.json`, and reverses it back. Since 0.5 it is
**pure-Python and duckdb-free** — its runtime deps are `just-dna-format`, `polars`, `pyyaml`, `typer`.
It **never fetches** (Principle 2): resolution is consumed from an injected, source-independent
`resolution.csv`; the pre-0.5 DuckDB reference path moved to [`just-dna-enricher`](ENRICHER.md) and is
reachable only through a deprecated, guarded shim (removed at 1.0).

The compiler adopts the schema with a **C++-standard-style feature-coverage** stance — not
all-or-nothing conformance but a per-feature table (below). As of 0.4 the validator is complete, the
upgrade derivation ships, the artifact round-trips losslessly including phase, and all nine 0.4 table
kinds materialize with enforced table-level coherence.

> Companion docs: **[SCHEMAS.md](SCHEMAS.md)** (the models it compiles), **[ENRICHER.md](ENRICHER.md)**
> (what produces `resolution.csv`), **[CONSTITUTION.md](CONSTITUTION.md)** (the invariants).

## Public API

Import from `just_dna_compiler.compiler`.

- **`validate_spec(spec_dir, authority_keys=None) -> ValidationResult`** — validate a spec dir without
  producing output; strips inject-only authority keys pre-validation (dropped keys → `.info`), runs
  `validate_bins` and the duplicate/identity checks, populates `.stats`.
- **`content_signature(spec_dir) -> str`** — the stable, name-/Ensembl-independent content identity over
  the raw authored data CSVs (no compile, no resolution); raises `ValueError` if a present data CSV is
  invalid. See [SCHEMAS.md § identity & integrity](SCHEMAS.md#identity--integrity).
- **`compile_module(spec_dir, output_dir, compression="zstd", resolve_with_ensembl=True,
  ensembl_cache=None, compiled_by=None, ensembl_reference=None, log_files=None, provenance_file=None,
  logo_file=None, authority_keys=None, strict=False) -> CompilationResult`** — compile to parquet +
  `manifest.json`. `resolve_with_ensembl`/`ensembl_cache` are **deprecated (removed at 1.0)** — see the
  precedence block.
- **`reverse_module(parquet_dir, output_dir, module_name=None, title=None, description=None,
  report_title=None, icon="database", color="#6435c9", version=None, write_resolution=True) -> Path`** —
  reverse a compiled artifact back to the authored DSL.

`models.py`: **`ValidationResult`** (`valid`, `errors`, `warnings`, `info`, `stats`) — the `.stats` key
contract is `variant_count`/`unique_rsids`/`gene_count`/`genes`/`categories`/`study_count`/
`clinvar_count`/`pathogenic_count`/`benign_count`/`module_name`. **`CompilationResult`** (`success`,
`output_dir`, `errors`, `warnings`, `stats`, `manifest` — the emitted `ModuleManifest`, `None` on failure).

## The compile pipeline

`compile_module` runs in this order:

1. **Validate** (`validate_spec`); fail early if invalid.
2. **Load** `module_spec.yaml` (authority-key pre-strip), then `variants.csv` / `studies.csv` if present.
3. **Load `resolution.csv`** if present → group rows by `variant_key` into a resolution table (a
   row-parse error fails the compile).
4. **Resolve** (only if `resolve_with_ensembl and variants`) — the precedence block below.
5. **Re-validate identity post-resolution** (`_cross_validate_variants`) — resolution can change identity
   (fill a coord, expand a one-to-many rsid), so a post-resolution duplicate/inconsistency fails the
   compile (`"post-resolution: …"`).
6. **Compute `fully_resolved`** = every variant has `chrom`+`start` (vacuously true for a variant-less
   module).
7. **Strict gate** — if `strict` and any variant still lacks `(chrom, start)`, fail **before any parquet
   is written** (refuse a non-reproducible partial artifact).
8. **Write parquets** — SNP core (`weights`/`annotations`/`studies.parquet`, only when the relevant rows
   exist) + one parquet per present table kind.
9. **Collect** logs / `provenance.json` / logo (a malformed one fails the compile, not raises).
10. **Build the manifest** (`content_signature` re-read from raw disk, plus the resolution fields) and
    write `manifest.json`.

### Resolution precedence (additive; Principle 3)

Inside step 4, gated on `resolve_with_ensembl and variants`, with `resolution_mode = "strict" if strict
else "best_effort"`:

1. **`resolution.csv` present → `resolve_from_table`** (the preferred, source-independent path — no
   `duckdb`, no network, no Ensembl convention). Sets `resolution_signature` (fact-hash of the rows) and
   `resolution_sources` (sorted union of row `source`s).
2. **else `ensembl_cache` given → DEPRECATED DuckDB path.** Emits a `DeprecationWarning` ("… removed at
   1.0. Produce a resolution.csv …") and routes to the enricher via a **guarded lazy import**
   (`from just_dna_enricher.resolver import resolve_variants`); if the enricher isn't installed, the
   compile fails with a message pointing at it or at precomputing `resolution.csv`. The compiler declares
   no dependency on the enricher.
3. **else (nothing injected) → skip.** `None` no longer auto-discovers a cache (the 0.5 Principle-2
   tightening); variants lacking a position are left unresolved with a warning pointing at the enricher.

**Digest parity** between paths 1 and 2 is the load-bearing guarantee: given the same facts, both emit
byte-identical `weights.parquet` (hence `artifact.digest`). The one order-sensitive spot — a one-to-many
expansion — is pinned by sorting on `(locus_index, chrom, start, ref)`.

### `resolve_from_table` (`compiler/resolution.py`)

Pure. Mirrors the DuckDB resolver's semantics from the injected table: **fill (1:1)** a `variant_key`
with one usable locus fills the missing coord/rsid (frozen key kept); **expand (1:N)** an rsid with N
usable loci becomes N coord-keyed rows, each re-keyed by `derive_variant_key`; **verify** a row with both
rsid and coord is checked, a disagreement is a warning (never fatal). GRCh38-bound (a non-GRCh38 module
is skipped with a warning; `not_found`/wrong-build rows are ignored).

## Reverse

`reverse_module` reads the **parquet artifact only** (never `manifest.json`) and emits into `output_dir`:
`module_spec.yaml` (always), `variants.csv` + `resolution.csv` (when `weights.parquet` exists;
`resolution.csv` gated on `write_resolution=True`), `studies.csv` (when present), and one CSV per present
table kind.

- **Preserved (round-trip-critical, Principle 7):** every authored `VariantRow`/`StudyRow`/table value;
  genotype phase (the `phased` bit re-emits `A|G` vs sorted `A/G`); tri-state bools; `priority` verbatim;
  poly-effect annotations keyed on `(variant_key, conclusion, negatives)`.
- **Frozen-`variant_key` authored shape:** the stored key decides emission — a row keyed on its rsid
  emits the rsid; a coord-keyed row (resolved rsid, position-only, or an expanded one-to-many locus) emits
  **position-only**, dropping the resolved rsid so recompute + re-resolution reproduce the same key.
- **`resolution.csv` emission** carries that dropped rsid back: one `ResolutionRow` per positioned weights
  row (`source="reversed"`, `status="resolved"`, `locus_index=0`), so **`reverse → compile` reproduces the
  identical `artifact.digest` with no reference and no network** — hardening Principle 7's round-trip from
  reference-dependent to self-contained.
- **Normalized:** `genome_build` re-emitted as `GRCh38`; title/description/report_title fall back to
  name-derived defaults; icon/color from args; curator/method from the most-common column value.
- **Lost (manifest-only, out of `artifact.digest`):** `authorship`, `panel`, `provenance`, `logo`, a
  non-GRCh38 build label. A consumer needing these reads `manifest.json` (preserved verbatim by the
  forward compile).

## Output artifact & hashing

- **`_OUTPUT_FILES`** (feed `artifact.digest`): `weights`/`annotations`/`studies.parquet` + the 9
  table-kind parquets.
- **`_INPUT_FILES`** (feed `manifest.inputs`, raw-bytes hashed): `module_spec.yaml` + `variants.csv` +
  `studies.csv` + the 9 table-kind CSVs. **`resolution.csv` is deliberately NOT here** (nor in
  `_OUTPUT_FILES`) — it is a multi-producer artifact hashed only by the normalized `resolution_signature`
  (a raw-bytes hash would be unstable across enricher/human/reverse producers). `provenance.json` is
  likewise out of the digest.
- **Manifest `Compilation` fields the compiler populates:** `compile_success`, `compiled_by`,
  `compiler_version`, `ensembl_reference`, `compiled_at`, `warnings`, and the 0.5 resolution provenance —
  `resolution_mode` (policy), `fully_resolved` (outcome — orthogonal axis, P5), `resolution_signature`,
  `resolution_sources`. All out of `artifact.digest`. Together `resolution_mode == "strict" or
  fully_resolved` tells a catalog a trustworthy module from a best-effort half-baked one.

The three hashes and how they compose into `(content_signature, resolution_signature, compiler_version)
⟹ artifact.digest` are documented in [SCHEMAS.md § identity & integrity](SCHEMAS.md#identity--integrity).

## CLI

`just-dna-compiler` (Typer): `validate <spec>`, `compile <spec> <out>`, `signature <spec>`,
`reverse <parquet_dir> <out>`. Exit 0/1 (CI/registry-gateable). Key flags: `compile` takes
`--strict/--no-strict`, `--resolve/--no-resolve`, `--compression`, `--compiled-by`,
`--strip-identity`/`--authority-key`, and the **deprecated** `--ensembl-cache` (routes to the enricher,
removed at 1.0); it prints `digest`, `content_signature`, and `resolution_mode`/`fully_resolved`/
`resolution_signature`. `reverse` takes `--resolution/--no-resolution` (default on) plus the
display-metadata overrides.

## Coverage table (0.3 / 0.4 features)

| 0.3 / 0.4 feature | Validated | Materialized (→ parquet) | Computed / derived | Status |
|---|---|---|---|---|
| `direction` (`VariantRow`) | ✅ full vocab | ✅ `weights.parquet` | ✅ `effective_direction` / `upgraded()` from `state`(+`weight`) | complete |
| `stat_significance` (`VariantRow`, `StudyRow`) | ✅ full vocab | ✅ | ✅ derived from `state` (not inferred from `p_value`) | complete |
| `effect_size` (`VariantRow`, `StudyRow`) | ✅ float | ✅ | — | complete |
| `effect_measure` (`VariantRow`, `StudyRow`) | ✅ permissive (open) | ✅ | — | complete (intentionally open) |
| `effect_allele` (`VariantRow`) | ✅ nucleotides | ✅ | ⛔ no strand/ref reconciliation | validate + passthrough |
| `flags` (`VariantRow`) | ✅ open; split; reserved set | ✅ `List[str]` | ✅ unknown-tag INFO (`ValidationResult.info`) | complete |
| `trait_efo_id` (`VariantRow`, `StudyRow`) | ✅ CURIE(s) | ✅ | — | complete |
| `doi` (`StudyRow`, RM11) | ✅ DOI grammar, verbatim | ✅ `studies.parquet` | — | complete |
| `provenance_quote` / `provenance_regex` (`StudyRow`, RM12) | ✅ free-text / author-time `re.compile` | ✅ `studies.parquet` | — | complete (P1 pattern grammar; matched consumer-side) |
| `authorship` (`ModuleSpecConfig`/`ModuleManifest`, RM14) | ✅ `Contribution` (role closed, kind open, `extra=forbid`) | ✅ **manifest** (out of digest) | — | complete (metadata; not reversed) |
| `clin_sig` (`VariantRow`) | ✅ full vocab | ✅ | ✅ ↔ `pathogenic`/`benign` aliases | complete |
| `module.version` (`ModuleInfo`, 0.4.1) | ✅ freeform advisory (legacy `v2`/`3`) | ✅ **manifest** `Identity.version` iff valid SemVer; `reverse_module(version=)` re-emits | ✅ `normalize_version` preview (RM17 enforces) | complete (advisory) |
| authority-key strip (0.4.1) | ✅ inject-only pre-strip; dropped → `.info`; typo'd still `extra=forbid` | — | — | complete (DI) |
| strict compile (0.4.1) | ✅ `strict=True` fails (pre-write) on an unresolved `(chrom, start)` | — (refuses a partial) | — | complete (opt-in) |
| `content_signature` (0.4.1) | ✅ over raw authored rows, normalized+sorted, name-/Ensembl-independent | ✅ **manifest** (out of digest); `signature` CLI computes it without recompiling | — | complete (canonical dedup identity) |
| **`resolution.csv` path (0.5)** | ✅ `resolve_from_table` consumes injected facts; digest-parity with the DuckDB path proven; **provisional shape** (§ note) | ✅ drives `weights.parquet` coords; `resolution_signature`/`resolution_mode`/`fully_resolved`/`resolution_sources` → **manifest** (out of digest) | ✅ fill / expand / verify (pure, no duckdb) | complete (preferred path) |
| CLI (0.4.1) | ✅ Typer `validate`/`compile`/`signature`/`reverse`; `--strict`, `--strip-identity`/`--authority-key`, deprecated `--ensembl-cache`, `--resolution` | — | — | complete (compiler-only dep; tiers intact) |
| genotype widening: hemizygous single allele | ✅ | ✅ (1-element list) | — | complete |
| genotype widening: phased `A\|G` | ✅ (order kept) | ✅ `phased` bit → lossless round-trip | ✅ | complete |
| `state` (legacy) | ✅ (stays required — P8) | ✅ | ✅ read alias via `effective_direction`; trimmed to {protective,risk,neutral} on `upgraded()` | complete |
| MT / non-diploid genotype | ✅ warning on a two-allele MT or Y genotype | — | — | complete |
| direction/weight sign consistency | ✅ warning | — | — | complete |

## 0.4 compiler coverage (materialized)

| 0.4 kind (model) | Validated | Materialized (→ parquet, round-trip) | Status |
|---|---|---|---|
| binning primitive `MeasureBinRow` + `Activity/CopyNumber/RepeatAllele/Heteroplasmy` rows | ✅ shared vocab, inclusive `[min,max]`, mandatory `unresolved`, `extra=forbid`, `source_field` pointer, heteroplasmy `tissue` + legacy-ref guard | ✅ `*.parquet` via generic materializer | **materialized** |
| table-level `validate_bins(rows)` | ✅ per `(key…, trait_efo_id)` group | overlap → error, gap → warning, >1 `unresolved`/group → error | **enforced** |
| duplicate-row detection (diplotype pair, `pgs_id`, `(pharm variant, drug)`, allele-function allele, haplotype-defining variant) | ✅ per-kind natural key | error (0.4 analog of duplicate-(variant, genotype)) | **enforced** |
| PGx `HaplotypeRow` / `AlleleFunctionRow` / `DiplotypeRow` (+ `drug`/`response`/`evidence_level`) | ✅ | ✅ | **materialized** |
| PharmGKB `PharmVariantRow` (single-variant drug response, `evidence_level` 1A…4) | ✅ | ✅ | **materialized** |
| `VariantRow` general axes: `requires_callable` / `acmg_sf` / `actionability` | ✅ (`actionability` vs `ACTIONABILITY_SEED`) | ✅ into `weights.parquet` (tri-state bool round-trip) | **materialized** |
| PGS `PgsRow` (declared interface; ancestry-validity fields) | ✅ `PGS<digits>`, ancestry/tier vocab, `match_rate_floor∈[0,1]` | ✅ | **materialized** |
| reserved namespace (`reference_db` / `callable_from`) | ✅ specific diagnosis via `reject_reserved` on top of `extra=forbid` | — | reserved |
| authoring reference + palette (`reference.authoring_reference()`/`json_schemas()`) | ✅ generated from live models (drift-proof) | n/a | **shipped** (RM8/RM9) |
| frozen `variant_key` identity (`base.derive_variant_key`) | ✅ stamped once, never re-keyed by resolution (P7); excluded from `authoring_reference()` | ✅ `weights.parquet` (compiler-managed) | **shipped** |
| rsid↔coord resolution: one-to-many expansion, deterministic order, inject-only consistency check | ✅ `ORDER BY`; disagreement → warning; non-GRCh38 skipped | ✅ N coord-keyed rows per one-to-many rsid; idempotent | **shipped** (the DuckDB engine now lives in `just-dna-enricher`; GRCh38-only; multi-build RM15) |

## Upgrade derivation (`state`/booleans → 0.3 axes)

`state` and the ClinVar booleans **stay required/authoritative** for 0.2 backward-compat (P8). The new
axes are optional, and `just_dna_format.derive` supplies fallbacks:

- **Read-time (non-mutating):** `VariantRow.effective_direction` / `effective_stat_significance` /
  `effective_clin_sig` / `effective_pathogenic` / `effective_benign` return the set column, else the
  derivation — so a legacy 0.1/0.2 row exposes all three axes with no re-publish.
- **Materializing:** `VariantRow.upgraded()` fills those axes and trims `state` to `{protective, risk,
  neutral}` (kept as a derived mirror of `direction`). `needs_upgrade` is the signal the marketplace
  `revalidate`/`needs_upgrade` flow consumes. Both idempotent (P7).

## Intentionally unimplemented — and why

1. **New computed manifest stats.** `Stats` carries the 0.2 counts only; no new distributions (by
   `direction`/`clin_sig`) — no consumer needs them yet.
2. **`effect_allele` strand/ref reconciliation.** Validated (nucleotides) and passed through; the `+`
   strand / `genome_build` assumption is documentation, not an enforced computation.
3. **Single build — GRCh38-bound.** `genome_build` is recorded but only GRCh38 is honored: coordinates
   are GRCh38, the resolution table's `genome_build` is checked against the module's, and
   `artifact.digest` is GRCh38-relative. A GRCh37/T2T module compiles but is not re-resolved for that
   build. Legacy-from-implementation, not a principle — build-aware identity is RM15. A no-coord rsid
   mapping to several loci is expanded to one row per locus (data-agnostic), shipping GRCh38-now.
4. **`reverse_module` reconstructs the compilable core, not manifest-only metadata** (reads parquet only,
   never `manifest.json`). `authorship`/`panel`/`provenance`/`logo` are not restored and `genome_build`
   emits `GRCh38`; the digest fixed point still holds (these are out of the digest). What *is*
   round-trip-critical — every authored value, including a poly-effect variant's per-effect
   `gene`/`phenotype`/`category` — is restored.

## Consequences worth knowing

- **`weights.parquet`/`studies.parquet` carry the 0.3 columns + a `phased` bit**, so a re-compile under
  this compiler changes `artifact.digest` for every module; reproducibility is pinned by
  `compiler_version`, and published versions keep their digest until re-published. (Pre-1.0 digest moves
  are still free to absorb while unpublished.)
- **Round-trip is lossless and idempotent** (P7): `reverse_module` → recompile preserves every column
  including phase, and the same spec compiles twice to the same digest. In 0.5 the round-trip is
  additionally **offline** — reverse emits `resolution.csv`, so recompile needs no reference and no
  network (regression-tested: DuckDB compile → reverse → no-cache recompile → identical digest).
- The **`ValidationResult.info`** channel carries non-reserved `flags` notes via stdlib logging — the
  format packages do not depend on Eliot.

Tests: `compiler/tests/test_v03*.py` (validator, genotype widening, warnings/INFO, materialization,
round-trip/idempotency); `test_v04_compile.py` (the nine table kinds); `test_resolution_table.py` (the
0.5 resolution-table path, digest parity, offline round-trip, strict/best-effort, the deprecation).
