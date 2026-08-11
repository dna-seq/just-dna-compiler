# just-dna-format — Constitution

The durable design charter for `just-dna-format` and `just-dna-compiler`: what these packages are
for, what they will never do, and the invariants every release upholds.

This is the **self-contained** charter: it stands alone and points to no other document, so the core
commitments below cannot be lost or altered as a side effect of routine edits elsewhere. **It changes
only by deliberate amendment.** When any other document, plan, or convention in the repo conflicts
with this one, this document wins; when a plan graduates into a durable rule, promote it here on
purpose.

## Goals

- Be the **declarative schema contract** for just-dna annotation modules and the **reference
  compiler** that targets it: an authored spec (`module_spec.yaml` + CSVs) → a `manifest.json` plus a
  multi-parquet artifact (the three-parquet SNP core — weights/annotations/studies — plus one parquet
  per optional table kind a composed module adds), carrying per-input and per-artifact hashes and a
  Merkle `artifact.digest`.
- Stay **dependency-light, in tiers.** `just-dna-format` (schema + integrity) costs only `pydantic`
  plus `cryptography` (the latter solely for Ed25519 signature verify/sign, added in 0.2 — a small,
  pure-verify dependency, never a heavy transitive tree), so any verify-only client can depend on it;
  `just-dna-compiler` adds polars/pyyaml/typer for the transform, and is pure-Python. A third, **network tier**
  (`just-dna-enricher`, added 0.5) *produces* the injected resolution table these two consume, and is
  the only tier permitted to fetch (httpx/tenacity/huggingface-hub); it depends inward
  (`enricher → compiler → format`) so its deps never enter the compile path. Consumers pick the tier
  they need and pull nothing heavier. The bright line is the *heavyweight* deps in Non-goals below
  (Dagster / LLM SDKs / HuggingFace), which the **format and compiler tiers** may never pull.
- Make **integrity the identity.** A version is identified by its artifact digest and its authored
  content by `content_signature`, both reproducible by anyone holding the inputs and the pinned
  compiler version.

## Non-goals

- **No heavyweight dependencies in `just-dna-format` / `just-dna-compiler`.** Never pull Dagster or
  LLM SDKs into any tier; never pull HuggingFace into the **format or compiler** tiers. Orchestration
  and AI-assisted authoring live in `just-dna-pipelines`. HuggingFace is permitted **only** in the
  network tier (`just-dna-enricher`), which owns the bulk-snapshot download — that carve-out is the
  0.5 amendment below, and it is scoped: HuggingFace never reaches the two dependency-light tiers a
  verify-only or compile-only client installs.
- **No network in the format/compiler tiers.** `just-dna-format` and `just-dna-compiler` never
  download reference data. Resolution facts are **injected** as a persisted, source-independent table
  (`resolution.csv`); the compiler consumes only that table (and, transitionally, an injected
  reference) and **skips with a warning** when nothing is injected, never fetching. Filling that table
  from any source — a cache, the network, or a human — is the job of the separate network tier
  (`just-dna-enricher`), which the compile path never imports.
- **Not a runtime.** The format is data, not a program (Principle 1). A consumer must be able to read
  a module without executing anything the module ships.
- **No UI and no gene–disease inference.** The format catalogs curated annotations that consumers
  *join* against variant data; interpretation and presentation belong to those consumers.

## Principles (invariants)

1. **Declarative, never code.** A module is data — CSV rows, YAML, and lookup tables — never a
   program. Expressive power comes from tables (e.g. diplotype/haplotype lookups), not from a
   scripting language. Turing-complete code in cells (Lua, Python, side-effecting expressions) is
   **rejected**: it breaks server-side-compile safety (arbitrary code execution in the trusted
   compile path), destroys byte-reproducibility (hashing inputs is meaningless if behaviour is code),
   and forces every consumer to embed a runtime. **Declarative *grammars* are welcome, though** — a
   pattern language is data, not a program. If tables are ever outgrown, the sanctioned escapes are
   (a) a **non-Turing-complete boolean predicate** over genotypes (e.g. `rs429358==C AND rs7412==C`)
   and (b) **declarative pattern grammars** such as **regular expressions** for matching allele
   strings / genotypes (e.g. a regex over a PGx star-string), evaluated by a small sandboxable engine
   — a linear-time/safe one, so there is no catastrophic-backtracking (ReDoS) exposure. The line is
   **Turing-completeness and side effects, not apparent sophistication**: bounded predicates and
   pattern grammars are in; general code is out. None of these are needed yet — they are escape
   hatches, available if a task genuinely demands, never a default.

2. **No network; inject-only (format + compiler).** `just-dna-format` and `just-dna-compiler` do not
   fetch. Any reference (Ensembl, ClinVar) is injected by the caller; with nothing injected, the
   compiler skips resolution with a warning rather than downloading. Since 0.5 the injection is
   formalized as a **source-independent resolution table** (`resolution.csv`) the compiler consumes,
   owning no source convention — so this principle *tightened* rather than loosened. Fetching lives in
   a separate tier, `just-dna-enricher`, which *produces* the table (cache / snapshot / live Ensembl /
   human) before compilation begins; it is not part of the format/compiler tiers and the compile path
   never imports it. (The pre-0.5 injected DuckDB reference remains a superseded, still-working
   inject-only path, queued for removal at the next major.)

3. **Backward-compatible within a major version.** Inside an `N.x` line every change is additive and
   non-breaking: `schema_version` is unchanged, existing modules keep validating, and anything
   superseded is kept as a **working derived alias**. **Breaking changes land only at a major bump.**
   The default retirement is two-step — *deprecate at the major* (still readable, emits a deprecation
   event), *remove at the next major*. Purely-internal dead weight may be removed outright at a major.
   A new **optional** column, or a new optional table, is additive and lands in a minor: the authored
   identity — `content_signature` and the per-input hashes — is unchanged, and only a recompile's
   `artifact.digest` moves. **Removing** a column, **promoting** one to required, or **retyping** one
   is major-only: each breaks an existing reader or invalidates published data. The concrete list of
   items queued for the next major is maintained separately, as living material.

4. **Integrity and immutability.** All hashes are SHA-256, lowercase hex, prefixed `sha256:`.
   Identity has two halves and they answer different questions. `artifact.digest` (a Merkle root over
   the artifact files) is the version's **byte** identity — these bytes, from this compiler.
   `content_signature`, over the authored rows and independent of both the reference that resolved
   them and the module's name/display metadata, is its **content** identity — this data, however and
   wherever it was compiled. A published version's bytes are **never mutated**; withdrawal is a *yank*
   (drop from listings, keep fetchable), not an edit. Parquet is not byte-deterministic across
   polars/arrow versions, so reproducibility is pinned via `compiler_version` and the resolved
   reference.

5. **Orthogonal axes, no overloaded fields.** Each concept gets its own column or table; a field must
   not pile up independent axes. (The legacy `state` field — conflating statistical significance,
   effect direction, and a genotype descriptor — is the anti-pattern being unwound in 0.3.) Because
   Principle 3 makes names and vocabularies permanent within a major, **audit every new name against
   likely future additions before adding it**, and reserve the names of anticipated future axes so
   they survive the one-way door.

6. **Vocabulary idiom.** Constrained vocabularies are `frozenset[str]` + a validator, not
   `Enum`/`Literal`. This keeps a vocabulary additive and inspectable, and matches the existing schema.

7. **Round-trip fidelity and idempotency.** The format is declarative data, so the reference
   transform must behave like one. Within a major version:
   - **Lossless round-trip.** `compile_module` → `reverse_module` → `compile_module` preserves every
     authored value. Reversing a compiled artifact back to the spec DSL and recompiling must not drop
     or mutate a column (this is why phase is carried in the artifact, not discarded — a phased `A|G`
     survives the round-trip). If a value cannot survive the round-trip, the artifact is missing a
     field, not the spec.
   - **Idempotency.** Compiling the same spec twice in a fixed compiler environment yields the same
     `artifact.digest`; and every derivation/upgrade is a fixed point — `row.upgraded().upgraded()
     == row.upgraded()`, and the read-time `effective_*` aliases return a set column unchanged. A
     derivation must never oscillate or accumulate.

   These are enforced by tests, not merely asserted here. (Cross-*version* byte-reproducibility is
   still bounded by Principle 4: parquet is not deterministic across polars/arrow versions, so the
   digest guarantee is *within* a fixed `compiler_version`.)

8. **Requiredness is monotonic within a major (field-optionality compatibility).** Whether a field is
   required is itself part of the contract and may only tighten, never loosen, inside an `N.x` line:
   - A field that **any earlier version in the line made required stays required** — it is never
     demoted to optional. Demoting it would let a newer module omit data an older consumer depends
     on. (This is why 0.3 keeps `state` and the ClinVar booleans **required/authoritative** and adds
     `direction`/`clin_sig` as *optional* orthogonal axes with derived fallbacks, rather than the
     inverse first considered.)
   - A **new** field may be introduced and even treated as required for freshly-authored specs, **but
     only if existing data still validates** — i.e. it is optional/defaulted with respect to every
     already-published module (which never set it), so nothing previously valid becomes invalid.
   - The forbidden moves — demoting an existing required field to optional, promoting an existing
     optional field to unconditionally-required, or retyping a field — are **breaking changes
     reserved for the next major** (the requiredness rehaul). Until then, all of the above holds.

   In short: optionality tightens forward-only and never invalidates older data; loosening waits for
   the major bump. This complements Principle 3 (additive within a major) by pinning the *requiredness*
   axis specifically, because it was the axis most easily missed.

## Amendments

This document is amended deliberately, never incidentally. Plans, release history, the
reserved-namespace and 1.0-cleanup trackers, and coding-style conventions (type hints, pathlib,
absolute imports) all live in their own documents, never here. If any of them conflicts with a
principle above, this document governs — resolve the conflict by amending one or the other on
purpose, not by letting the two drift.

**0.5 amendment — the network tier.** Goal 2, the two Non-goals on dependencies and network, and
Principle 2 were amended to introduce `just-dna-enricher`: a third, network-capable tier that
*produces* the injected `resolution.csv` the compiler consumes. The change is additive and scoped, not
a reversal — `just-dna-format` and `just-dna-compiler` become *more* strictly inject-only (they own no
source convention and never fetch), and HuggingFace/httpx/tenacity are confined to the enricher, never
reaching the dependency-light tiers a verify-only or compile-only client installs. This completes the
`just-dna-datasets`/"cache authority leaves the compiler" decoupling recorded in the 0.4.1 plan.

The same amendment **removed `duckdb` from the compiler tier**, which is why Goal 2 now names
polars/pyyaml/typer alone. Resolution moved from an in-compiler DuckDB query over an injected reference
to the injected `resolution.csv` table, so the whole SQL/cache-location half went to the enricher and
the compiler became pure-Python. This is a *tightening* of Goal 2's dependency-light commitment, not a
new allowance, and it is recorded here because Goal 2 read as though duckdb were still sanctioned there
for a full release after it had gone.
