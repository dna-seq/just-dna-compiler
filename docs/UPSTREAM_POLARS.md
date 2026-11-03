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
  warnings; `enricher/tests`: 2281 passed, 68 skipped.
- **Bytes:** three reference examples (`apoe_epsilon`, `pathogenic_clinvar`, `cyp2c19_star_alleles`) compiled
  twice under 1.44.2 and once under 2.1.0. Under 1.44.2 the two compiles are byte-identical. Under 2.1.0 every
  parquet's sha256 and every `artifact.digest` differ (`pathogenic_clinvar`: `…8ef062b846eb` → `…c04864c8f97f`).
- **Why:** read back with polars and pyarrow, every table is equal (`DataFrame.equals`), with the same schema,
  codec (ZSTD), encodings (`PLAIN`, `RLE`), statistics, format version and row-group count. Two separate
  things moved the bytes, found by comparing each file's bytes before its footer (`pq_footer.py` in the
  seating session; it reads the footer length from the last 8 bytes):
  1. **1.44.2 → 2.0.0: only the footer.** The data pages are byte-identical; the footer's `created_by` went
     from `'Polars'` to `'Polars (python) version 2.0.0 (build 22a147de…)'`. Upstream: PR pola-rs/polars#29106
     "Add polars version to parquet created_by field", merged 2026-09-03, first in `py-2.0.0`. The string is
     built in `crates/polars-parquet/src/arrow/write/file.rs:59` from the version and the build commit, and
     nothing in `write_parquet` (2.1.0 signature) sets or omits it.
  2. **2.0.0 → 2.1.0: the data pages.** They differ in all eight parquets of two examples, with the tables still
     equal. 2.1.0 changed how nested columns are written (#30251, #30245), and our `List(Utf8)` columns
     (`authored_ident`, `genotype`, `alts`, `flags`) are nested.
- **Suites, both majors together** (`--with polars==2.1.0 --with duckdb==2.0.0`, all three packages): 4833
  passed, 73 skipped, 3 failed. Of the three, only duckdb's `EXPLAIN` test is a major's (`UPSTREAM_DUCKDB.md`).
  `docs/DREAMS.md` was a peer's untracked file, and the triage-archive test passed on rerun under both majors
  (a peer commit landed mid-run).
- **Code against the breaking lists:** 2.0's (SQL window and literal semantics, plugin CSE, Parquet ENUM read
  as String, the `.map` namespace, `cut`/`qcut` deprecated) and 2.1's (no mixed string/numeric arithmetic in
  eager) reach nothing we call. Our one `map_elements` (`enricher/src/just_dna_enricher/clinvar_build.py:373`)
  is not the `.map` namespace.
- **Who else holds polars below 2:** polars-bio 0.36.2, which just-dna-lite stands on, pins `polars<2,>=1.40.0`.

**Sorted: breaks us, in the digest only.** Every 2.x release writes its own version and build into every
parquet we produce, so from 2.0 on `artifact.digest` changes with every polars release, even a patch. Releases
like 2.1.0 also change the data pages. The table contents stay equal. P4 and P7 already limit byte reproducibility
to a fixed `compiler_version` and compiler environment. Goal 3 says a digest is reproducible by "anyone holding
the inputs and the pinned compiler version", but `polars>=1.42.0` has no upper bound, so the compiler version
does not pin the bytes. Under 1.x two machines minted the same digest unless the writer changed; under 2.x they
mint different digests whenever their polars versions differ. Writing a constant `created_by` would not remove
this: 2.1.0 changes the data pages anyway.

**No cap** (the person, 2026-11-04: "what's the reason to pin? Their pin limits the top by itself, by imposing
second cap we'll block em"). Nothing functional blocks 2.x. polars-bio already caps the consumers that need it,
and a cap here would block every other consumer and would hold just-dna-lite back after polars-bio lifts its
own. The digest question is for the lead: record the polars version beside `compiler_version`, and declare the
move in the release that takes 2.x into `uv.lock`. Plan sent to the lead 2026-11-04.

## Our pieces that duplicate an upstream feature

None found.

## Outbound

None. The `created_by` change is upstream following the parquet spec, so it is not a defect to report.
