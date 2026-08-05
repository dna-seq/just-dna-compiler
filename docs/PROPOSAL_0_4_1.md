# Proposal — 0.4.1: inject the authority-key list, own the stripper, adopt `version`

**Status: decided — the S1/S2 + `version` items implemented, pending a release the user cuts; the
*Ensembl cache authority leaves the compiler* item (below) decided but not yet implemented.** This is
the *"means → draft schema → decision"* stage for a **0.4.1 patch**, responding to the registry's field
report in [`CONSUMER_SUGGESTIONS.md`](CONSUMER_SUGGESTIONS.md) (S1/S2) and — for the cache-authority
item — to the `just-dna-datasets` split design. Everything here is **out of `artifact.digest`**
(identity/metadata validation only, or a resolver-input path that changes no output bytes), so it is
patch-shippable (CONSTITUTION P3/P8).

> **Supersedes the earlier draft** that proposed a hardcoded `vocab.REGISTRY_OWNED_KEYS` frozenset
> + an accept-and-drop `mode="before"` validator on `ModuleInfo`. That baked one consumer's identity
> conventions into the format and made the *validator* fix input. Both are wrong per the charter (see
> *Why not hardcode* below); the design below replaces them.

---

## The friction (S1)

0.4 made the authored `module:` block `extra="forbid"` — correct: it catches `colour:` / `nam:` typos
and the `genome_bild:` safety trap. But the same guard now **hard-rejects keys the registry fills on
publish, not the author**: essentially every pre-0.4 `module_spec.yaml` in the wild carries
`module.version` (an author's informal `v2`/`3`), and some carry `namespace` / `owner`. Under 0.3 these
were silently dropped; under 0.4 they are `Extra inputs are not permitted`, breaking three registry
paths for the *entire* legacy corpus (import → `422`, upgrade → `422` mid-upgrade, revalidate → a
`needs_upgrade` flag that never clears).

The format documents these as marketplace-filled: `Identity.{namespace,version,canonical_id}` and
`manifest.owner` are `Optional`, stamped by the registry on publish and *overriding* any authored
value. So the authored copies are **vestigial by construction**.

## Two different problems — split them

The earlier draft lumped four keys together. They are not the same:

- **`version`** is *universal author intent* — a human marker every module has. It is not a consumer
  convention; the format should **genuinely adopt it as a field**, not strip it.
- **`namespace` / `owner` / `canonical_id`** are *authority-stamped identity*. The author has no
  business setting them; *which* keys a given publishing authority stamps is that authority's
  convention, not the format's knowledge.

## The mechanism — dependency injection (CONSTITUTION P2's spirit)

The format already lives by **inject-only** for reference data (P2: "any reference is injected by the
caller; the libraries do not fetch"). The same shape applies here: **the consumer ships the set of
authority-owned keys it stamps; the format owns the reference *stripper* that consumes that set.** The
format hardcodes no consumer's key list and applies nothing by default.

Two schema tools, new module `just_dna_format/normalize.py` (dependency-light leaf, like `vocab`):

1. **`strip_authority_keys(block, authority_keys) -> (clean, dropped)`** — pure, order-preserving,
   byte-preserving when nothing matches; the reference implementation of the registry's own
   `strip_registry_owned_keys()`. **Inject-only**: `authority_keys` is the caller's set.
2. **`IDENTITY_AUTHORITY_KEYS = frozenset({"namespace", "owner", "canonical_id"})`** +
   `IDENTITY_AUTHORITY_REASONS` — a *documented convenience* a consumer may inject. Note `version` is
   **absent** (it is a real field now).

### Pre-strip, not in-validator — "a validator validates, it does not fix"

The strip runs **before** validation, in the loader (`_load_yaml`), never as a `mode="before"`
validator. Consequences, all deliberate:

- The validator keeps `extra="forbid"`'s full teeth. A genuine typo (`namespac:`) is **not** in the
  injected set, so it still fails hard — the strip is exact.
- If a caller forgets to inject, or a key slips the strip, `forbid` errors **loudly**, pointing at
  exactly where expectation broke — instead of a validator silently repairing bad input.
- Reporting is trivial: the loader returns the dropped list; `validate_spec` surfaces it on `.info`.

`validate_spec(spec_dir, authority_keys=None)` and `compile_module(..., authority_keys=None)` thread
the set through; a bare call strips nothing and still forbids stray identity keys.

### Why not hardcode / why not the reserved namespace

- **Hardcoding `REGISTRY_OWNED_KEYS`** makes the format track a *consumer's* naming — the registry's.
  A different authority might stamp a different set; the format cannot and should not know. DI is the
  charter-correct source of the list.
- **The reserved namespace** (`vocab.RESERVED_NAMES_0_4`, P5) is for names expected to become future
  **module columns** — the *opposite* of these, which will never be authored. Reusing it would corrupt
  its meaning. `IDENTITY_AUTHORITY_KEYS` is a separate, distinctly-documented vocabulary.

## Genuinely adopting `version`

`ModuleInfo` gains `version: Optional[str] = None`, **freeform** (accepts the whole legacy corpus's
`v2`/`3`). It is advisory: the registry stamps the canonical SemVer `Identity.version` on publish and
overrides it.

- **Live SemVer preview, today.** The coercion algorithm (`normalize.normalize_version`) is built now
  but used **read-only**: `validate_spec` computes `normalize_version(version)` and, **only when it
  differs from the authored value**, emits a warning previewing what a future release will read
  (`v2` → *"will read it as `2.0.0`"*). A clean `1.2.3` stays silent. This makes the advice actionable
  and pre-tests the 0.5 algorithm. Enforcement (coerce/validate) is **0.5** — see
  [`PROPOSAL_0_5.md`](PROPOSAL_0_5.md) V1.
- **Flows to the manifest only when clean.** `_build_manifest` passes an authored version into
  `Identity.version` **iff it is already valid SemVer** (a freeform `v2` stays `None`; the registry
  stamps it). So the SemVer-validated `Identity.version` never sees a messy value, and manifest
  validation never breaks.
- **Round-trip.** `version` (like `title`/`description`) is out-of-digest `module:` metadata, not
  materialized to any parquet, so `reverse_module` cannot recover it from the artifact — it gains a
  `version=` parameter to re-emit it when a caller supplies it (e.g. from `manifest.identity.version`),
  symmetric with the existing `title`/`description` parameters. Digest-neutral throughout (proven by
  test).

## S2 — the field-ownership boundary, drift-proof

Rather than a hand-maintained table that drifts, the boundary is surfaced from the generated
`reference.authoring_reference()`:

- `version` now appears in `ModuleInfo`'s field list automatically (it is a live field).
- A new `"registry_stamped_keys"` section lists `namespace`/`owner`/`canonical_id` with reasons —
  legibly distinct from `"reserved_names"` (future module columns). An authoring agent reads it and
  omits them. `COMPILER.md` carries the human-facing coverage rows.

The registry's broader lossy `--trim` pass (for stray `defaults:` keys / legacy column aliases) stays
consumer-side (explicit human ops); no format change is requested for it. If the registry's
whole-corpus run surfaces a concrete next offender, it graduates through the design cycle.

## A stable `content_signature` for cross-recompile dedup

**Status: implemented on the 0.4.1 branch.** From a third field report: a registry's dedup pre-check
keys on `artifact.digest`, but importing a module **recompiles locally** (a different/complete Ensembl
reference → different parquet bytes → different digest) and publish **strips metadata**, so the digest
check misses the dedup path entirely. The only authoritative dedup is the server's `content_signature`
(a hash of the raw data CSVs), but it is enforced only at publish (409 `duplicate_content`) with no
client-reachable lookup — so the UI pre-check can't be made robust client-side.

### The friction

`artifact.digest` is a Merkle root over the **compiled parquet**, which is GRCh38-coordinate-relative:
it moves when the same spec is recompiled against a different reference, and it embeds the module name
(materialized into the `module` column), so it also moves on rename/metadata-strip. It is a
*byte-reproducibility* identity, not a *content-dedup* identity. Those are two different jobs.

### The decision — the format owns the canonical content signature

A new `integrity.content_signature(tables)` (the schema package — the lightest tier, so any consumer
can compute it) hashes the **raw authored data rows**, and the compiler stamps it into
`manifest.content_signature` (optional, out of `artifact.digest`). It is:

- **Reference-independent** — computed from the rows *before* resolution, so recompiling against a
  different/complete reference does not change it. (This is also why it is read from disk at compile
  time, not from the already-resolved in-memory rows.) *Corrected in 0.5: this bullet said
  "Ensembl/build-independent", conflating the reference used to resolve with the module's **declared
  assembly** — see `integrity.content_signature` and RM36.*
- **Name/metadata-independent** — the identity/display half of `module_spec.yaml` is excluded.
  `genome_build` is the exception and feeds the hash (when non-default), because identical coordinate
  rows on two assemblies are two different loci, not one module described twice.
- **Normalized** — each row is `model_dump(mode="json", exclude_none=True)`, so CSV reformatting and
  additive schema growth (a new optional column left unset) do not change it.
- **Deterministically sorted, order-independent** — rows are sorted by canonical JSON and files by
  name, so reordering rows yields the same signature. (Deliberately unlike `artifact.digest`, which
  *preserves* authored row order — the two are different identities.)
- **All authored data CSVs** — `variants.csv` + `studies.csv` + the 0.4 table kinds, so a
  PGx/PGS-only module (no `variants.csv`) still gets a signature.

The compiler exposes `content_signature(spec_dir)` and a `just-dna-compiler signature <spec_dir>` CLI
command, so a client computes it **without recompiling** and looks it up — surviving both
metadata-strip and recompile.

### Own, but adopt the marketplace's implementation where possible

The format owns the *canonical* algorithm, but the intent is to **not break the marketplace's existing
`content_signature`**: it keeps the marketplace-compatible conventions (the `sha256:` prefix, the raw
data-CSV file set, per-file grouping). The one deliberate divergence is **raw-bytes → normalized +
deterministically-sorted rows** — chosen for robustness (survives reformat/reorder/recompile), which
the marketplace's raw-CSV hash does not. Adopting it is a one-time backfill of stored signatures (the
marketplace already has `find_versions_by_content` internally — it re-derives with this algorithm and
exposes a client lookup endpoint). Where the marketplace's current bytes already agree, nothing moves;
where they don't (the normalization), the backfill reconciles them.

### Charter check

- **P2 (no network):** untouched — pure local hashing of authored data.
- **P3/P8:** additive — a new **optional** manifest field + new helpers; demotes nothing, retypes
  nothing.
- **`artifact.digest`:** unchanged — `content_signature` is a sibling identity, never fed into the
  digest. Patch-shippable.

## The Ensembl cache authority leaves the compiler — pure inject-only

**Status: decided, not yet implemented.** This item is not from a consumer field note; it fell out of
the `just-dna-datasets` split design (separating dataset download / reference-module *recreation* from
the reference consumer). It shares this patch's inject-only spirit, so it rides the 0.4.1 window.

### The friction

The compiler carries `just_dna_compiler/cache.py`: env-var precedence
(`$JUST_DNA_ENSEMBL_CACHE` › `$JUST_DNA_PIPELINES_CACHE_DIR` › a platformdirs `just-dna-pipelines`
user-cache default), a `.env` loader, and `resolve_ensembl_reference()` that probes those locations for
a usable reference. `resolve_variants(..., ensembl_cache=None)` calls it, so a bare `compile_module()`
**auto-discovers** an upstream deployment's cache.

That is upstream knowledge in the wrong repo. **Where an Ensembl/ClinVar cache lives on disk, and which
env vars name it, is a deployment fact owned by `just-dna-datasets` / `just-dna-pipelines`** — not the
schema-driven compiler. It entered here only as a convenience so `test_resolver_integration.py` could
exercise the resolver *in battle* against a real cache. The need to test the compiler against real data
is genuine; siting the cache-location authority *inside the compiler* to get it was a hack.

Leaving it here is also what makes the datasets split circular: the compiler reaching for a default
cache location is the one back-edge (`compiler → datasets`) against the natural `datasets → compiler`
(module re-tracing needs the engine). Severing it makes the graph one-way.

### The decision — it goes away, not down

The cache-location authority is **removed from the compiler entirely** — not relocated to a leaf module
here, not copied. `just-dna-datasets` owns it (location + download + recreate); `just-dna-pipelines` /
the marketplace resolve a reference and **inject** it. This repo keeps only the reference *reading*
convention — "how to open a reference I was handed" — which is legitimate consumer knowledge.

- **Deleted:** `just_dna_compiler/cache.py` in full — `resolve_ensembl_reference`,
  `default_ensembl_cache_dir`, `load_env`, the `$JUST_DNA_*` precedence, the platformdirs default.
- **Stays (relocated into `resolver.py`):** `DUCKDB_NAME` and the opening logic (`_connect`,
  `_view_over_parquet`) — the reference-*format* knowledge the compiler needs as the party that reads it.
- **Tests — kept local, via a dev-only datasets dep.** The compiler keeps its in-battle coverage here.
  `test_resolver_integration.py` **stays**, rewired from `just_dna_compiler.cache` to
  `just_dna_datasets.locations` — the cache resolver (and downloader) arrive as a **dev-only dependency**
  on `just-dna-datasets` (**base, no `[recreate]`**), exactly as this repo already dev-deps `pytest` /
  `ruff`. The synthetic-injected `test_resolver_unit.py` and the `test_identity_roundtrip.py` fixtures
  **stay as-is** — they inject a `Path` and need no cache, so they run in ordinary CI with no 190 MB
  reference. **Guardrail:** the dev pin is base datasets *without* `[recreate]`; `[recreate]` depends on
  the compiler, so pulling it into the dev group would re-introduce the very cycle this item removes. The
  integration test only *resolves + reads* a cache (never recreates a module), so base is all it needs —
  and the import graph stays acyclic (the compiler never imports datasets at runtime; `locations` never
  imports the compiler).

### The compiler injection shape

Pure inject-only, matching P2's letter:

- `resolve_variants(variants, ensembl_cache, genome_build=...)` — `ensembl_cache` is a resolved reference
  (a `.duckdb` file or a parquet dir) supplied by the caller. `None` → resolution is **skipped with a
  warning**; no env read, no `.env` load, no platformdirs, no default path. (The skip warning drops its
  `set JUST_DNA_…` advice — the compiler no longer names upstream env vars.)
- `compile_module(..., ensembl_cache=None)` — signature unchanged; `None` now means *skip*, not
  *auto-discover*. Pipelines / marketplace / datasets resolve the reference and pass it — they already
  inject in practice, so this narrows only the ambient-discovery convenience (the hack).

### Minus two deps

`platformdirs` and `python-dotenv` were used **only** by `cache.py`; both leave the compiler's
**runtime** deps in `compiler/pyproject.toml`, which drop to `just-dna-format`, `polars`, `duckdb`,
`pyyaml`. The **dev group** gains `just-dna-datasets` (base) for the integration test — a test-only dep
like `pytest` / `ruff`, never shipped to a consumer and (base-only) never a runtime or cyclic edge.

### Charter check

- **P2 (no network / inject-only):** the *point* of the change — the compiler stops computing a
  deployment path and becomes strictly inject-only. The env/platformdirs fallback was the single place it
  "knew" upstream layout; removing it **tightens** conformance rather than amending the charter.
- **P3/P8:** unlike the S1/S2 items (relaxations), this is a scope *removal* — `None` no longer
  auto-discovers. Still legal: it changes no field, no schema, and no `artifact.digest`; any caller that
  injects a reference (pipelines, marketplace) is byte-for-byte unaffected. Only a bare standalone compile
  relying on ambient discovery changes, and that reliance is the hack being retired. Patch-shippable, not
  major-gated.
- **`artifact.digest`:** unchanged for a given `(input, injected reference)` — resolution output is
  identical; only the *default* disappears.

## Strict (all-or-nothing) compile — refuse a partial artifact

**Status: implemented on the 0.4.1 branch.** This item is not a consumer field-note ask either — it fell
out of the **Issue 2 incident** ("post-publish local hash differs from published"). It shares this
patch's reproducibility/inject-only spirit.

### The incident → the lesson

A module was published, then flagged its own *local* copy as differing from the published one — a
scary-looking "conflict" that was a false alarm. Root cause: an **incomplete local Ensembl cache**
(a corrupt `chr1`) left the local compile with 7 `position remains unset` warnings, i.e. a
**half-compiled artifact**. The registry recompiled the same spec against its *complete* reference →
different bytes → different `artifact.digest` → the "conflict".

The consumer side is already fixed (publish now trusts the server's returned manifest as authoritative
instead of a local-vs-server byte comparison, and explains a benign digest difference in plain words
— "the registry recompiled from your spec with its reference build; reinstall to sync"). The
**format-side** gap is what this item closes: the compiler only has a *best-effort* mode, so an
incomplete reference silently yields a partial, non-reproducible artifact.

### Current behavior = a de-facto "half-compile"

`resolver.resolve_variants` (`compiler/src/just_dna_compiler/resolver.py`) is best-effort by design: an
rsid it cannot place appends `"{rsid}: not found in Ensembl, position remains unset"` (resolver.py:216)
and a position with no dbSNP id appends `"Position {key}: no rsid found in Ensembl"` (resolver.py:180)
— but the row is **still materialized** with a null position. So the artifact's bytes depend on how
complete the injected reference happened to be. That best-effort mode is the "0.3 half-compile" — it
stays the default; this item adds the *all-or-nothing* counterpart.

### The decision — opt-in `compile_module(..., strict: bool = False)`

When `strict=True`, after resolution the compiler checks that **every `VariantRow` has a resolved
genomic position (`chrom` + `start`)**; if any is still unset, it **fails with a clear error** instead
of writing a partial artifact. `strict=False` (the default) preserves today's best-effort behavior; a
publisher/registry passes `strict=True`.

- **Gate semantics (precise).** Fails when, after resolution ran, any `VariantRow` lacks `(chrom,
  start)` — which naturally covers both the *incomplete-cache* case (the incident) and the
  *resolution-skipped-because-no-reference* case (with `strict`, "no cache + rsid-only variants" is a
  hard error, not a silent partial). Scope is the **SNP-core `VariantRow` only** — the 0.4 table kinds
  (diplotypes/pgs/…) carry no positions and are untouched. rsid↔coord **consistency disagreements stay
  warnings** (a real dbSNP merge/build difference, not a cache-completeness failure — never fatal, per
  the resolver's stance).
- **Why position, not rsid.** `artifact.digest` is a Merkle root over the compiled parquet and is
  GRCh38-**coordinate**-relative — the coordinate is the anchor. An unresolved *position* is the
  reproducibility hazard; a missing rsid on a positioned row is not.
- **Placement.** In `compile_module`, right after the post-resolution `_cross_validate_variants`
  re-check (~`compiler.py:765`) and **before** the parquet writes (~`compiler.py:773`), so nothing
  partial ever reaches disk.
- **Error shape.** List the offending `rsid`/`variant_key` values and advise *"provide a complete
  Ensembl reference or compile without `--strict`."*

### Charter check

- **P2 (no network / inject-only):** untouched — strict reads no reference the caller didn't inject; it
  only *insists* the injected one was sufficient.
- **P3/P8:** additive — a new **opt-in** flag, default `False`; demotes nothing, retypes nothing.
- **`artifact.digest`:** unchanged for any compile that *succeeds* — strict emits identical bytes; it
  only converts a would-be-**partial success into a failure**. Patch-shippable, not major-gated.

## A compiler CLI (Typer)

**Status: implemented on the 0.4.1 branch.** There was **no CLI** — no `[project.scripts]`, no
`argparse`/`typer`/`__main__`; the compiler's whole surface was the Python API (`validate_spec` /
`compile_module` / `reverse_module`). A catalog operator or CI job had to write a Python snippet to
compile a module. This item adds a first-class command-line front door.

### The decision — a Typer CLI in `just-dna-compiler` only

New `just_dna_compiler/cli.py`, exposed via a `[project.scripts]` console entry (proposed name
**`just-dna-compiler`**; short alias `jdc` optional), with **`typer` added to the compiler's runtime
deps**. **Never `just-dna-format`** — dependency tiers are sacred (CONSTITUTION Goal 2): Typer/click ride
with the already-heavy compiler (polars/duckdb), not the pydantic-only schema package.

The command surface mirrors the three public functions one-to-one, so the CLI is a thin, testable shell:

- **`validate <spec_dir>`** → `validate_spec`; prints errors/warnings/info; **exit 1** if invalid.
  Options: `--strip-identity` (inject `normalize.IDENTITY_AUTHORITY_KEYS`) and/or a repeatable
  `--authority-key KEY` (inject a custom set).
- **`compile <spec_dir> <output_dir>`** → `compile_module`; **exit 1** on failure, prints
  `artifact.digest` on success. Options: `--strict/--no-strict` (the front door to the section above),
  `--ensembl-cache PATH`, `--no-resolve`, `--compression`, `--compiled-by`,
  `--strip-identity`/`--authority-key`.
- **`reverse <parquet_dir> <output_dir>`** → `reverse_module`; options
  `--module-name/--title/--description/--report-title/--icon/--color/--version` (the `version=` param
  0.4.1 added).

**Exit codes 0/1** make it CI/registry-gateable, e.g. a publisher runs
`just-dna-compiler compile spec/ out/ --strict --ensembl-cache ref.duckdb`. The CLI is additive — no
schema, no `artifact.digest` impact.

**Interaction with the cache-authority removal (above):** `--ensembl-cache` is the inject point; the CLI
shape does not change when `cache.py` is deleted — only the meaning of an *omitted* `--ensembl-cache`
flips from auto-discover to skip-with-warning (and, under `--strict`, that skip becomes a hard error for
any rsid-only variant).

## Charter check

- **P2 (no network):** untouched — pure local validation; and the DI shape *extends* P2's inject-only
  spirit rather than amending the charter (the stripper is a schema tool, not a network concern).
- **P3/P8 (additive / requiredness):** a **relaxation** — accepts strictly more inputs (a new optional
  field + an injected strip), demotes no required field, changes no output.
- **`artifact.digest`:** unchanged — `version` and the authority keys are identity/metadata, never
  materialized into parquet. Patch-shippable, not major-gated.
- **P5 (reserved namespace):** deliberately **not** used — `IDENTITY_AUTHORITY_KEYS` is a separate
  vocabulary, keeping the reserved namespace meaning "future module axis" intact.
- **P7 (round-trip):** the *data* round-trips as before; out-of-digest `module:` metadata (version,
  like display) is manifest-carried, re-emitted by `reverse_module` only when the caller supplies it —
  the same status `title`/`description` already have.

## What shipped in this patch

- `just_dna_format/normalize.py` — `IDENTITY_AUTHORITY_KEYS`, `IDENTITY_AUTHORITY_REASONS`,
  `strip_authority_keys`, `normalize_version`.
- `ModuleInfo.version` (freeform advisory); `reference.authoring_reference()` gains
  `registry_stamped_keys`.
- Compiler: `validate_spec(spec_dir, authority_keys=None)` + `compile_module(..., authority_keys=None)`
  pre-strip in `_load_yaml`, surface dropped keys on `.info`, warn with the SemVer preview;
  `_build_manifest` fills `Identity.version` from a clean authored SemVer; `reverse_module(..., version=None)`.
- **`content_signature`**: `just_dna_format.integrity.content_signature(tables)` (canonical, owned) +
  `just_dna_compiler.compiler.content_signature(spec_dir)` convenience + `manifest.content_signature`
  (optional, out of digest) + a `just-dna-compiler signature` CLI command.
- **Strict (all-or-nothing) compile**: `compile_module(..., strict: bool = False)` + the
  post-resolution unresolved-position gate (fails before any parquet is written).
- **Compiler CLI (Typer)**: `just_dna_compiler/cli.py` (validate/compile/reverse), the `typer` runtime
  dep, and the `just-dna-compiler` `[project.scripts]` entry. `--strict` / `--strip-identity` /
  `--authority-key` / `--ensembl-cache` / `--no-resolve`; exit codes 0/1.
- **Dev tooling + metadata**: `ruff` added to the workspace-root dev group (it was referenced but
  present in none of the three dev groups); `authors` + `maintainers` (Newton Winter) on both packages'
  `[project]`.
- Tests: `schema/tests/test_normalize.py`, `compiler/tests/test_authority_keys.py`,
  `compiler/tests/test_strict_compile.py`, `compiler/tests/test_content_signature.py`,
  `compiler/tests/test_cli.py`, plus a reference-surface assertion.
- **Version bump** `0.4.0 → 0.4.1` (`schema_version` stays `"1.0"`) is the user's to cut — not done here.

**Pending in this patch, not yet in the tree** — design-only, deferred to a later pass:

- *Ensembl cache authority leaves the compiler*: delete `just_dna_compiler/cache.py`; make
  `resolve_variants` / `compile_module` pure inject-only (`None` → skip with a warning); relocate
  `DUCKDB_NAME` into `resolver.py`; drop `platformdirs` + `python-dotenv` from the compiler's runtime
  deps and add `just-dna-datasets` (base) to its dev group; keep `test_resolver_integration.py`,
  rewiring it from `just_dna_compiler.cache` to `just_dna_datasets.locations`. (Deferred here because it
  needs the `just-dna-datasets` package to coordinate against — the CLI's `--ensembl-cache` is already
  the inject point, so its shape is unaffected when this lands.)
