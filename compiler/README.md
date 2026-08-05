# just-dna-compiler

The reference **compiler** for just-dna annotation modules: it turns an authored spec directory into
a deployable parquet artifact **plus a `manifest.json`** with integrity digests.

A module **composes from optional table kinds**: the only always-present file is `module_spec.yaml`.
A SNP module adds `variants.csv` (+ `studies.csv`, required whenever variants are present) → the
`weights` / `annotations` / `studies` parquets; a PGx / PharmGKB / PRS module instead carries only
its own table(s) (`diplotypes.csv`, `pharm_variants.csv`, `pgs.csv`, …) and needs no `variants.csv`.
Each present CSV materializes to its own parquet, so the artifact is the set of parquets the module
actually uses (up to twelve), not a fixed three.

It consumes the schema/contract from [`just-dna-format`](../schema) and is the shared transform
called by both `just-dna-pipelines` (local compile) and `just-dna-marketplace` (server-side
recompile on publish).

```python
from just_dna_compiler.compiler import validate_spec, compile_module, reverse_module

validate_spec(spec_dir)                       # -> ValidationResult (genes/categories lists)
compile_module(spec_dir, out_dir,             # -> CompilationResult (+ manifest.json written)
               strict=False,                  # True: refuse a partial artifact
               compiled_by="marketplace-server")
reverse_module(out_dir, spec_again)           # -> Path (the spec DSL, rebuilt from the artifact)
```

**Resolution is injected, never fetched** (CONSTITUTION Principle 2). Drop a `resolution.csv` beside
`module_spec.yaml` — a table of already-resolved facts keyed by `variant_key` — and the compiler fills
in coordinates and rsIDs from it with no network, no DuckDB and no source convention of its own.
Produce that file with [`just-dna-enricher`](../enricher) (`just-dna-enricher enrich spec/`). With
nothing injected the compiler **skips resolution with a warning** rather than downloading anything.
The pre-0.5 `compile_module(ensembl_cache=…)` DuckDB path still works, is deprecated, and is removed
at 1.0.

**Dependencies:** `just-dna-format`, `polars`, `pyyaml`, `typer` — pure-Python and **duckdb-free since
0.5**, and deliberately no Dagster / LLM SDKs.
