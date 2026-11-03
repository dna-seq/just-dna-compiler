# Liaison notes

The liaison's working state, rewritten to the present before each reset.

## State on 2026-11-03 (first seating, machine october)

**Ledgers:** `docs/UPSTREAM_GA4GH_VRS.md`, `docs/UPSTREAM_POLARS.md`, `docs/UPSTREAM_DUCKDB.md`. Read marks are the
installed versions: ga4gh.vrs 2.3.3, polars 1.44.2, duckdb 1.5.5. `mkdocs.yml` `not_in_nav` carries
`UPSTREAM_*.md`.

**Clones** (in `/data/sources`, lines in `$XDG_STATE_HOME/agent-seat-blueprints/liaison/upstreams`):

- `vrs-python` is a **sparse checkout without `tests/`**. Its VCR cassettes have `>` and `:` in their names,
  which the NTFS `windows_names` mount refuses, so a full checkout fails.
- `polars` and `duckdb-python` are blobless clones (`--filter=blob:none`). Expect a `git log -S` over them to be
  slow, because it fetches blobs.
- `duckdb` (the engine) is blobless and unwatched. It is there to read source at `path:line`.

**Watchers** (`.blueprints.toml`): `ga4gh-vrs` polls every 300 s with no path filter. `polars` and
`duckdb-python` poll every 86400 s, also with no path filter: their trunks are busy, and `--path` would drop
the tag lines. duckdb-python's patch releases are tagged on version branches, so a `--path` watcher on main
would miss them. A tags-only mode would fit better; that is a kit wish.

**Half read (the backlog):**

- polars `py-2.0.0` and `py-2.1.0`: measured as a whole (the digest moves through `created_by`, the compiler suite
  passes). The release notes are not read entry by entry, so the read mark stays at 1.44.2.
- duckdb `1.5.6` and `2.0.0`: measured as a whole (one `EXPLAIN` string test fails). The notes are not read;
  open question: `.duckdb` storage compatibility for `resolver.py:78`.
- The enricher suite under polars 2.1.0 ran at seating. Record its result in the polars ledger.

**Sent to the lead** (it files the RMs; this seat's grant covers only its ledgers and notes): the polars
`created_by` digest move with the uncapped pin; the duckdb 2.0 `EXPLAIN` test; and, for RM304, PR
ga4gh/vrs-python#665 (`RleSubunitMode`, which `vrs/2.1` will default to SMALLEST).

**Push:** none from this seat yet. The lead reports that auto mode denied its own granted push (kit #238), and
the person pushes until that is fixed.
