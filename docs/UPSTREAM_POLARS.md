# Upstream ledger — polars

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. Upstream: <https://github.com/pola-rs/polars>, Python releases tagged
`py-<version>`; clone and watcher as the liaison state file's `polars` line says.

## Marks

- **Read mark: `py-2.2.0`** (2026-11-24; on PyPI 18:15Z, tag and GitHub release 18:19Z): its release notes, the
  three breaking entries read against our code, the parquet entries by title. Before: `py-2.1.0` (2026-11-04), with
  the notes of `py-2.0.0-rc.1`, `py-2.0.0-rc.2`, `py-2.0.0` and the 2.0 migration guide read entry by entry.
- **Installed:** `2.1.0` (`uv.lock`, since 5bdcca28 on `0.8`, shipped in 0.8.0). Pins: `polars>=1.42.0` in `compiler/pyproject.toml` (core) and in the
  enricher's `dev` extra (builders only). **No upper bound.**

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
- **Who else holds polars, and where (re-measured live 2026-11-16):** polars-bio, which just-dna-lite and just-vcf
  stand on, released **0.37.0 on 2026-11-07** (biodatageeks/polars-bio#478 "feat: support Polars 2.0 and 2.1",
  merged 2026-11-07), requiring `polars>=1.40.0,<2.2`. The `<2` hold is gone. just-dna-lite took polars 2.1.0 and
  polars-bio 0.37.0 on 2026-11-12 (its 9d588c2); just-vcf is moving now (its RM288, 2026-11-16; its lock still
  polars 1.44.2, polars-bio 0.36.0). **Its new cap is `<2.2`:** a polars 2.2 release holds both again until
  polars-bio widens, so a polars 2.2 is read against polars-bio's cap the day it appears. polars-bio's releases
  wake this seat through the upstream-index watcher since 2026-11-16. **0.38.0 (2026-11-17, read 2026-11-18):** the polars
  cap unchanged (`>=1.40.0,<2.2`); DataFusion's floor moved 53 -> 55 (`datafusion>=55.0.0,<56`); new `seq_*` sequence
  operations, a progress-bar session option, and a fix to a cached `config_meta` accessor. Nothing for polars 2.x. (The 2026-11-04 text here said 0.36.2 with
  #478 open; it went stale for nine days while the notes held the 0.37.0 fact, and the seat answered the person
  from it on 2026-11-16.)
- **Our own consumers' caps (read from each remote's `main`, 2026-11-16):** just-module-creator (a8d425a)
  constrains `polars<2` and `duckdb<2` by its lead's decision of 2026-11-10, to keep `artifact.digest` stable and
  the shared Ensembl cache readable by duckdb-1 tools (RM344). longevity-loci (1ffba5f) caps `polars<2` and
  `duckdb<2` for the same shared cache, and floors our packages at 0.8.6/0.8.7 `<0.9`. Both lock polars 1.44.2,
  duckdb 1.5.6 and our 0.8.6/0.8.7. just-dna-registry (044df54) locks polars 2.1.0 and duckdb 1.5.5 with no cap.
  A clone on this machine is not a read: fetch, then read `origin/main` (a first read here took longevity-loci's
  clone, six days behind, and told its liaison a cap was still there that its main had lifted on 2026-11-12).

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
move in the release that takes 2.x into `uv.lock`. Plan sent to the lead 2026-11-04; the version field is
**RM342**, shipped in 0.8.0 with RM352 (the `toolchain` change kind).

**Lock schedule (the liaison's, 2026-11-04; done 2026-11-05, 0.8.0):** move `uv.lock` to polars 2.x in the release that ships RM342, so
the one-time digest move arrives together with the field that explains it, plus a `RELEASE_RECORDS` line
(parquet bytes move, content unchanged). Nothing breaks on 2.x in the meantime, so there is no earlier deadline.

### py-2.0.0-rc.1 … py-2.1.0, read entry by entry — nothing past the digest (2026-11-04)

The verdict above stands. Every entry that could reach us was checked against the 19 files that import polars:

- **The lazy API now runs on the streaming engine**, which does not keep row order for joins, `group_by` or
  `unpivot`. Our lazy queries are three: `alphagenome_check.py:318` (scan, filter, collect; the result is keyed
  into a dict, so order is moot), `alphagenome_avi_build.py:599` (a row count) and `sweep.py:207` (a schema).
  Every join and `group_by` we run is eager, which 2.0 leaves on the in-memory engine;
  `alphagenome_avi_build.py:545` passes `maintain_order=True` anyway.
- **`read_csv` now runs as `scan_csv(...).collect()`.** Our two calls (`clinvar_build.py:340`;
  `alphagenome_avi_build.py:370`, with `new_columns` and a `schema_overrides` dict) use only parameters that
  2.1.0's `read_csv` still has, and both are under tests that passed on 2.1.0 (`test_clinvar.py`,
  `test_alphagenome_avi_build.py`).
- **`is_in` coerces only when nothing is lost.** Our one call (`alphagenome_check.py:319`) compares integer
  positions with an integer column.
- **`pl.concat(how="horizontal")` now requires equal heights.** We never concatenate horizontally;
  `concat(rechunk=False)` (`alphagenome_avi_build.py:615`) is still a parameter.
- **`pl.Categorical` loses its `ordering` argument, and int↔categorical casts are gone.** We cast strings only
  (`alphagenome_avi_build.py:573`, `:575`).
- **The removed 1.x API** (melt, `with_row_count`, `join_nulls`, `how="outer"`, `replace(default=)`, the
  `streaming=` and `rechunk=` reader arguments, and the rest of the guide's table): grepped, none used.
- **Parquet written by 2.1.0:** besides the nested-column writer (#30251, #30245), #29868 writes statistics and a
  column index for nested values, which is a third candidate for the data pages that moved.
- **Levers, nothing to act on:** 2.1.0 filters Categorical and Enum parquet columns while decoding and compares
  their dictionaries as strings for `is_in` (#29882, #29885). Out-of-core spilling is on by default from 2.0
  (#29741, #29734), at 80 % of RAM and up to 64 GB of disk. The AVI builder avoided the streaming engine on
  purpose (`alphagenome_avi_build.py:588`), so neither change applies to it.

### py-2.2.0 — the digest moves again; polars-bio's `<2.2` holds two consumers (2026-11-24)

- **Breaking list, three entries, none ours.** `Expr.str.find(_many)` returns character offsets (#31026), SQL
  `DELETE` changes the registered table in a `SQLContext` (#30869): neither is called anywhere in `schema/`,
  `compiler/` or `enricher/`. Scalar function arguments are required at plan time (#30914: `slice`, `top_k`,
  `replace`, `pct_change`, `int_range`, `str.slice` and kin): no call of ours passes an expression there (grepped),
  and the suite agrees.
- **Suite:** `uv run --isolated --all-packages --all-extras --all-groups --with polars==2.2.0 pytest -n 4`: 7595
  passed, 124 skipped, no warning (13 min 50 s, nice 19).
- **Bytes:** `pathogenic_clinvar` and `apoe_epsilon` compiled under 2.1.0 (the lock) and 2.2.0. Every parquet's
  table reads back equal; every file's bytes before the footer differ, not only the footer, and every file grows
  0.6 to 2.2 % (`weights.parquet` 62002 → 62396, `diplotypes.parquet` 6172 → 6308). `artifact.digest` moves (`pathogenic_clinvar` `…a426b9334b` →
  `…8679cff008`). Not measured which entry moved the pages; the candidates by title are #30410 (byte-array sizes in
  the statistics), #30653 (pages split by byte size for variable-length columns) and #30982 (parquet writes).
- **Who holds polars-bio, read live 2026-11-24 18:20Z:** 0.38.0 (2026-11-17) is still the newest, requiring
  `polars>=1.40.0,<2.2`, and its `main` says the same. No issue or pull request there names 2.2. So just-dna-lite
  and just-vcf stay on 2.1.x until polars-bio widens, as this ledger expected on 2026-11-16.

- **A regression that does not reach us** (reported by just-vcf's upstream liaison, reproduced here 2026-11-24 19:00Z):
  a grouped `median` over a filter whose mask is `concat_list([pl.lit(False), <list col>]).list.any()`, the list
  column null in every row, panics on 2.2.0 ("validity mask length must match the number of values"); 2.1.0
  returns nulls. We call none of `concat_list`, `list.any` or `median` (grepped). No open issue on polars'
  tracker carries the message (searched 19:03Z); filing it is just-vcf's, on its person's word.

**Sorted: breaks us in the digest only, as every 2.x release does** (the 2.0/2.1 verdict above). Our lock takes
2.2.0 at the weekly bump of 2026-12-01; the release after it moves every `artifact.digest` with the content equal,
which the cut's release record declares (RELEASE_CYCLE §9, a toolchain move). The lead told the same day. No cap
here (the person, 2026-11-04). Asking polars-bio to widen its cap is first agreed with just-vcf's upstream
liaison, who watches it too (told the same day); a post upstream is the person's word.

### The compat runtime, for a server without the default's CPU features (2026-11-26)

Asked by the person through the pm: a new server has no AVX-512, so 0.9.0 gains a `compat` extra pulling
`polars[rtcompat]`. Measured on 2.1.0:

- **Which runtime loads.** `polars._plr` tries `compat`, then `64`, then `32` (`default_prefer` in
  `py-polars/src/polars/_plr.py`), each behind `check_cpu_flags`. With `polars[rtcompat]` installed beside the
  default, `sys.modules["polars._plr"].__name__` is `_polars_runtime_compat._polars_runtime`; `POLARS_FORCE_PKG=32`
  loads the default instead (both run here). So the compat runtime is used **wherever the extra is installed**, also on
  a CPU that has AVX2: the extra costs speed on every machine that takes it.
- **What each runtime needs** (`BUILD_FEATURE_FLAGS` in the wheels, matching `NONCOMPAT_FEATURES` in polars'
  `release-python.yml`): `polars-runtime-32` +sse3,+ssse3,+sse4.1,+sse4.2,+popcnt,+cmpxchg16b,+avx,+avx2,+fma,+bmi1,
  +bmi2,+lzcnt,+pclmulqdq,+movbe (x86-64-v3); `polars-runtime-compat` only up to SSE4.2, popcnt and cmpxchg16b
  (x86-64-v2). **Neither needs AVX-512.** This machine has AVX2 and no AVX-512 and runs the whole suite on the default
  runtime, so a server lacking only AVX-512 does not need compat; one lacking AVX2, FMA or BMI does. polars' import
  error names the missing features.
- **The rest of our native code.** The suite passing here also shows nothing else we depend on requires AVX-512. By
  `objdump`, duckdb, pyyaml, upb, charset-normalizer, cffi and markupsafe use no AVX registers at all; cryptography,
  hf-xet and grpc carry AVX-512 code behind runtime CPU checks. Not proven: that pydantic-core, cryptography, hf-xet
  and grpc run on a CPU without AVX2 (no emulator here); none of them checks CPU flags at import as polars does.

**Sorted: the extra is harmless as an option, and its install line says "only on a CPU without AVX2".** Sent to the
lead and the pm (643975731); the server's real flags decide whether it needs it. **They do (read the same day):** the
server is an Intel Xeon E5-1620 v2 (Ivy Bridge, 2013): plain AVX, no AVX2, FMA, BMI1, BMI2 or LZCNT, no AVX-512. So the
default runtime cannot load there and compat is required. The open risk moves to the line "Not proven" above: a CPU
without AVX2 is now a real target, so the other native libraries are proven only by a run on that server.

## Our pieces that duplicate an upstream feature

None found.

## Outbound

None. The `created_by` change is upstream following the parquet spec, so it is not a defect to report.
