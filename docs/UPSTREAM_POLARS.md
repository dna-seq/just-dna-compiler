# Upstream ledger — polars

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. Upstream: <https://github.com/pola-rs/polars>, Python releases tagged
`py-<version>`; clone and watcher as the liaison state file's `polars` line says.

## Marks

- **Read mark: `1.44.2`**, the version `uv.lock` installs. Pins: `polars>=1.42.0` in `compiler/pyproject.toml`
  (core) and in the enricher's `dev` extra (builders only). **No upper bound.**
- **Backlog: `py-2.0.0`, `py-2.1.0`** (newest, 2026-10-25) are past the read mark. Not read entry by entry yet;
  measured as a whole on 2026-11-03 (below). The read mark moves when the entries are read and sorted.

## What we use of it

The compiler owns polars (CONSTITUTION Goal 2); the enricher's runtime passes read snapshots with duckdb and
use polars only in builders (`@duckdb-vs-polars`).

| Ours | Theirs | What it decides |
| --- | --- | --- |
| `compiler/src/just_dna_compiler/compiler.py:5336`–`:5340`, `:5363`, `:5612`, `:5634` | `DataFrame.write_parquet(compression="zstd")` | **the artifact's bytes, so `artifact.digest`** |
| `compiler/src/just_dna_compiler/compiler.py:598`, `:6773`– | `pl.Utf8`, `pl.List`, `pl.Int*`, `pl.Float*`, `pl.Boolean`, `pl.UInt*`, `pl.Categorical` | the parquet schemas consumers read |
| `compiler/src/just_dna_compiler/compiler.py`, `sweep.py` | `DataFrame`, `col`, `concat`, `sort`, `unique`, `group_by`, `read_parquet`, `scan_parquet` | row order (load-bearing, CLAUDE.md "Deterministic ordering") |
| `enricher/src/just_dna_enricher/*_build.py` (clinvar, clinpgx, civic, constraint, cpic, drug_labels, mane, mitomap, mitomap_miss, pharmvar, pubmind, alphagenome_avi), `civic_draft.py`, `civic_refutation.py`, `mitomap_draft.py`, `alphagenome_check.py`, `cli.py` | `read_csv`, `read_parquet`, `write_parquet`, `DataFrame` | the published snapshots' bytes |

## Verdicts

### 2.0.0 / 2.1.0, measured as a whole — every artifact digest moves; nothing else did (2026-11-03)

- **Suites:** `uv run --isolated --with polars==2.1.0 pytest compiler/tests`: 1557 passed, 1 skipped, no
  warnings. The enricher suite under 2.1.0: see the notes file until it is recorded here.
- **Bytes:** three reference examples (`apoe_epsilon`, `pathogenic_clinvar`, `cyp2c19_star_alleles`) compiled
  twice under 1.44.2 and once under 2.1.0. Under 1.44.2 the two compiles are byte-identical. Under 2.1.0 every
  parquet's sha256 and every `artifact.digest` differ (`pathogenic_clinvar`: `…8ef062b846eb` → `…c04864c8f97f`).
- **Why:** read back with polars and pyarrow, every table is equal (`DataFrame.equals`), with the same schema,
  codec (ZSTD), row-group count and key-value metadata keys. The one difference is the footer's `created_by`:
  `'Polars'` under 1.44.2, `'Polars (python) version 2.1.0 (build 7f902bd3ffd27ff82d14278a09a295ff2f7aed92)'`
  under 2.1.0. The files grow by about that string's length (7651 → 7721 bytes). Upstream: PR pola-rs/polars#29106
  "Add polars version to parquet created_by field", merged 2026-09-03, first in `py-2.0.0`, written to follow
  the parquet spec's `<Application> version <App Version> (build <App Build Hash>)`.

**Sorted: breaks us.** From 2.0 on, the polars version and build hash are inside every parquet we write, so
`artifact.digest` changes with every polars release, even a patch, when the spec and the compiler stay the same.
P4 already scopes reproducibility to a fixed `compiler_version` (FAQ, "Does a rebuild always mint a new
digest?"), but `polars>=1.42.0` has no upper bound, so one `compiler_version` installed on two machines can
mint two digests for one spec. That was possible before; from 2.0 on it is certain whenever the polars versions
differ. The fix belongs to the lead: pin polars, record the polars version, or decide that the digest names
the toolchain. Sent to the lead 2026-11-03.

## Our pieces that duplicate an upstream feature

None found.

## Outbound

None. The `created_by` change is upstream following the parquet spec, so it is not a defect to report.
