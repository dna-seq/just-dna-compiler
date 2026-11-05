# Liaison notes

The liaison's working state, rewritten to the present before each reset.

## State on 2026-11-04 (machine october)

**Ledgers:** `docs/UPSTREAM_GA4GH_VRS.md`, `docs/UPSTREAM_POLARS.md`, `docs/UPSTREAM_DUCKDB.md`, `docs/UPSTREAM_ENSEMBL.md` (a standing watch with no clone or watcher, handed over by the lead
2026-11-04; re-checked by hand monthly, next 2026-12-04). Read marks:
ga4gh.vrs 2.3.3 (pre-releases read through 2.4.0-a6), polars `py-2.1.0`, duckdb `2.0.0`. Installed (`uv.lock`):
2.3.3, 1.44.2, 1.5.5. `mkdocs.yml` `not_in_nav` carries `UPSTREAM_*.md`.

**Clones** (in `/data/sources`, lines in `$XDG_STATE_HOME/agent-seat-blueprints/liaison/upstreams`):

- `vrs-python` is a **sparse checkout without `tests/`**. Its VCR cassettes have `>` and `:` in their names,
  which the NTFS `windows_names` mount refuses, so a full checkout fails.
- `polars` and `duckdb-python` are blobless clones (`--filter=blob:none`). Expect a `git log -S` over them to be
  slow, because it fetches blobs.
- `duckdb` (the engine) is blobless and unwatched. It is there to read source at `path:line`.

**Watchers** (`.blueprints.toml`): `ga4gh-vrs` polls its trunk every 300 s. `polars --tags --tag-pattern '^py-'` and
`duckdb-python --tags` say tags only, one wake per release (kit v0.1.119, #246), a patch tagged on a version branch
included.

**Backlog: none.** Read entry by entry on 2026-11-04, unattended: polars `py-2.0.0-rc.1` through `py-2.1.0` with the
2.0 migration guide, and duckdb `1.5.6` and `2.0.0` (both packages' notes). Nothing new breaks us; the verdicts and
the RMs stand. One new fact: duckdb 1.5.6 refuses a 2.0 file with a different message (`version number 69`, not
`999`), the same `IOException`, so RM344's handler must key on the type. The lead was told.

**The person's rule (2026-11-04, relayed by the lead):** the liaison decides adoption blockers and hands the
lead adoption maps. A pin goes on only when a new major is proven to break something, and only until support is
integrated. The lead pins as a safety only if the liaison is unavailable and work must move. The lead commits
the lock; the liaison schedules it and tells the lead when.

**Decided by the person, 2026-11-04: no cap on either major.** polars-bio's own `<2` already holds just-dna-lite,
and a second cap here would block everyone else.

**Sent to the lead** (it files the RMs; this seat's grant covers only its ledgers and notes), 2026-11-03/04: the
adoption plan for both majors without a cap, which supersedes the first message's cap option; and, for RM304, PR
ga4gh/vrs-python#665 (`RleSubunitMode`, which `vrs/2.1` will default to SMALLEST).

**Lock schedule:** duckdb 2.x once RM344 lands; polars 2.x with RM342, which the pm moved into **0.8** (f3377a6;
its shape is being interviewed). RM343 (EXPLAIN test) is done. polars-bio: still `<2` at 0.36.2; its polars-2
PR is biodatageeks/polars-bio#478 (open, green). Watch for 0.37.0.

**Blocked on the person: the dependency bump** (the person, 2026-11-04, relayed by agents-kit/builder, zulip
…637618265). The bump (`uv lock --upgrade`, the suite, its new warnings, the fixes) becomes this seat's unattended
routine; the role text is in the kit since v0.1.127, which this clone pins. Step (2), the priming change, is written in
the working tree of `LIAISON.md` (grant + "## The dependency bump") but **uncommitted**: auto mode refused the commit
as self-modification (kit issue #267). Put on the desk for the person to commit or allow (desk #195). Kit v0.1.128 widens auto-mode rule 5 to cover it (#267 fixed); this clone moved to v0.1.128 on 2026-11-05, but the person's installed rule 5 is still the 2026-11-03 one (`automode.py --check`), so #195 now recommends pasting it; once pasted, commit the priming here. Default on
silence: stays uncommitted, no bump runs. After it lands: (1) add `[seat.liaison.watch.nightly]`, `cmd = "sh
kit:bin/py.sh kit:classes/base/nightly.py deps"`, to `.blueprints.toml` (may be refused the same way). Do not run a
bump before the grant is committed.

**Fellow liaison:** just-dna-registry/liaison (seated 2026-11-04) stands on fastapi, huggingface-hub, and polars and
duckdb through our tiers. A defect in a library under both of us is raised with each other first, so it is filed once. **longevity-loci/liaison** (seated 2026-11-05) stands on us: just-dna-enricher 0.7.3, compiler 0.7.2, format 0.7.1 from PyPI, and the module-creator plugin v0.48.0. It watches our tags, asks us before mapping our 0.8 branches, and polls us before filing a shared defect; answer such a poll in `agent-chat`.

**Push:** origin/main holds every liaison commit through 324eaee (pushed with the other seats' commits on
2026-11-04). The liaison pushes only its own ledgers and notes, and only as a fast-forward that carries no other seat's
commit.

**Priming c339487** (a cap on a proven break; adoption maps to the lead) was read; no concern.
