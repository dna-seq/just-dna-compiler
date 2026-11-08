# Liaison notes

The liaison's working state, rewritten to the present before each reset.

## State on 2026-11-05 (machine october)

**Ledgers:** `docs/UPSTREAM_GA4GH_VRS.md`, `docs/UPSTREAM_POLARS.md`, `docs/UPSTREAM_DUCKDB.md`, `docs/UPSTREAM_ENSEMBL.md` (a standing watch with no clone or watcher, handed over by the lead
2026-11-04; re-checked by hand monthly, next 2026-12-04). Read marks:
ga4gh.vrs 2.3.3 (pre-releases read through 2.4.0-a6), polars `py-2.1.0`, duckdb `2.0.0`. Installed (`uv.lock`):
2.3.3, 2.1.0, 1.5.5. `mkdocs.yml` `not_in_nav` carries `UPSTREAM_*.md`.
`docs/UPSTREAM_DATA_SOURCES.md` (since 2026-11-07, the maintainer's ask): one row per cache lane, available /
built / published; measured by hand that day, re-measured weekly. Behind then: clinvar, constraint (pinned
4.1, source at 4.1.2), civic, strchive, likely mitomap. The priming paragraph that adds it sits uncommitted in
`LIAISON.md` beside the bump's (desk #195, rule 5).

**Clones** (in `/data/sources`, lines in `$XDG_STATE_HOME/agent-seat-blueprints/liaison/upstreams`):

- `vrs-python` is a **sparse checkout without `tests/`**. Its VCR cassettes have `>` and `:` in their names,
  which the NTFS `windows_names` mount refuses, so a full checkout fails.
- `polars` and `duckdb-python` are blobless clones (`--filter=blob:none`). Expect a `git log -S` over them to be
  slow, because it fetches blobs.
- `duckdb` (the engine) is blobless and unwatched. It is there to read source at `path:line`.

**Watchers** (`.blueprints.toml`): `ga4gh-vrs` polls its trunk every 300 s. `polars --tags --tag-pattern '^py-'` and
`duckdb-python --tags` say tags only, one wake per release (kit v0.1.119, #246; the clone pins v0.1.144 since 2026-11-08), a patch tagged on a version branch
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

**Lock schedule:** polars 2.1.0 is in `uv.lock` (5bdcca28) and shipped in **0.8.0** (cut 2026-11-05, with RM342 and
RM352). duckdb 2.x once RM344 (open, a patch on `main`) lands: then tell the lead. RM343 (EXPLAIN test) is done. polars-bio **0.37.0** (on PyPI by 2026-11-07) requires `polars>=1.40.0,<2.2`: the `<2` block on just-dna-lite
is gone; the lead was told (zulip …638402138). Its new cap is `<2.2`: a polars 2.2 release holds just-dna-lite again until polars-bio follows.

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

**What the fellows did with the majors (2026-11-05):** the registry's suite passes on polars 2.1.0 and duckdb 2.0.0
(612 passed, no new warning); it takes polars 2 with its 0.8 adoption and duckdb 2 after RM344. longevity-loci capped
both `<2` in its own lock, because the module-creator plugin's server (v0.48.1, still polars 1.44.2 and duckdb 1.5.5)
shares that machine's enricher cache: the mixed cache RM344 is about. Its cap lifts when the plugin moves; their call. **just-module-creator/liaison** (seated 2026-11-07) keeps
the plugin in step with us: ledgers `UPSTREAM_COMPILER.md`, `UPSTREAM_REGISTRY.md`, `UPSTREAM_HOSTS.md`; it locks format
0.7.1 / compiler 0.7.2 / enricher 0.7.3, capped `<0.8`, and polars and duckdb `<2`, until both registry instances serve
0.8. It is on our triage's `wake_from` (8de1fa80).

**Push:** origin/main holds every liaison commit through fe38e101 (the liaison's own fast-forward, 2026-11-08;
the ledger commits before it went out with the lead's pushes). The liaison pushes only its own ledgers and notes, and only as a fast-forward that carries no other seat's
commit.

**Role change read (v0.1.137, 2026-11-06):** the role adds "An in-house release" (the liaison takes the mechanical
half of adopting an upstream the person also keeps). This repo has no in-house upstream (ga4gh.vrs, polars, duckdb,
Ensembl are all outside), so nothing changes here. reflect after 2026-11-13: classes/liaison/LIAISON.md as of v0.1.137.

**Priming c339487** (a cap on a proven break; adoption maps to the lead) was read; no concern.
