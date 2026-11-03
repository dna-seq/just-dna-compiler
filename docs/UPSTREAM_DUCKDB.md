# Upstream ledger — duckdb

Kept by the liaison seat (`docs/seats/LIAISON.md`); another seat that meets a symptom here sends it to the
liaison rather than writing in this file. What pip installs is built from <https://github.com/duckdb/duckdb-python>
(tags `v<version>`, patches tagged on version branches such as `v1.5-variegata`), which vendors the engine from
<https://github.com/duckdb/duckdb>, where the release notes are. Clones as the liaison state file's
`duckdb-python` (watched) and `duckdb` (a reading aid, not watched) lines say.

## Marks

- **Read mark: `1.5.5`**, the version `uv.lock` installs. Pin: `duckdb>=1.1.0` in `enricher/pyproject.toml`
  (core). **No upper bound.**
- **Backlog: `1.5.6`, `2.0.0`** are past the read mark. Not read entry by entry yet; 2.0.0 measured as a whole on
  2026-11-03 (below). The read mark moves when the entries are read and sorted.

## What we use of it

The enricher's runtime passes read snapshots with duckdb (`@duckdb-vs-polars`); it writes nothing we publish.

| Ours | Theirs | What it decides |
| --- | --- | --- |
| `enricher/src/just_dna_enricher/clinvar.py:83`, `:269`; `clinpgx.py:215`; `gene_metrics.py:178`; `drug_labels.py:403`; `pharmvar.py:372`; `cpic.py:614`; `gene_spans.py:112`; `pubmind.py:96`; `resolver.py:63` | `duckdb.connect(":memory:")`, SQL over `read_parquet(...)`, `fetchall()` | every snapshot lookup |
| `enricher/src/just_dna_enricher/resolver.py:78`, `:86` | `duckdb.connect(<file>, read_only=True)` | the deprecated `.duckdb` Ensembl reference: **its storage format is a version question** |
| `enricher/src/just_dna_enricher/gene_spans.py:146`, `:158`; `lookup.py:363`, `:583`, `:678` | `duckdb.Error` | which failures are handled |
| `enricher/tests/test_query_shapes.py:104` | the text of `EXPLAIN` | pins that the batch lookup is a hash join (`@hash-the-probe`) |

## Verdicts

### 2.0.0, measured as a whole — one test's string match breaks; behaviour holds (2026-11-03)

- `uv run --isolated --with duckdb==2.0.0 pytest enricher/tests`: 2280 passed, 68 skipped, **1 failed**,
  in 9 minutes. The same file passes on 1.5.5 (9 passed).
- The failure is `test_lookup_clin_sig_is_a_hash_join_not_an_or_chain`, which asserts `"HASH_JOIN" in plan`.
  2.0's `EXPLAIN` renders the operator as `Hash Join` (the renderer was unified in duckdb/duckdb#23222), and the plan it printed is still an INNER hash join on
  `chrom, start, ref, alt`. The timing test beside it (`…beats_the_or_chain_by_an_order_of_magnitude`) passed
  under 2.0, so the query shape held.

**Sorted: breaks us, in a test only.** The test reads a display string that 2.0 changed. The fix is the
test's (match the operator case-insensitively with `_` and space treated alike, or read the plan another way),
and it belongs to the lead. Sent to the lead 2026-11-03.

- **Storage, measured both ways:** a file 1.5.5 wrote (a table and a view over a parquet) opens read-only under
  2.0.0 and both answer. A file 2.0.0 wrote is refused by 1.5.5: `IOException: Trying to read a database file
  with version number 999, but we can only read versions between 64 and 68`. `resolver.py:78` and `:86` open
  `ensembl_variations.duckdb` with no handler around the `connect`, so a 2.0-built cache read by a 1.x enricher
  raises instead of falling back to the parquet `data/` beside it, which the function does for an empty or
  stale database. just-dna-lite opens the same file (`just_dna_pipelines/annotation/duckdb_assets.py:170`,
  `:238`). The path is deprecated (removed at 1.0). The one exposure is a machine where one side runs 2.0 and
  the other 1.x.
- **Client side** (duckdb-python 2.0 notes): Python 3.10 dropped (we require 3.13); `fetch_arrow_table`,
  `fetch_record_batch`, `arrow(n)` and `pl()` on an `execute()` result removed (we call none of them); results
  stream, so an error late in a query raises from the fetch. In the sites read (`gene_spans.py:146`, `:158`) the
  `fetchall()` sits inside the `duckdb.Error` handler; the suite passed. 2.0 deprecates the implicit
  table-function string (`FROM 'x.parquet'`); we always write `read_parquet(...)`.

**No cap** (the person, 2026-11-04). Nothing we publish is written by duckdb, and the test fix is the one change.

## Our pieces that duplicate an upstream feature

None found.

## Outbound

None.
