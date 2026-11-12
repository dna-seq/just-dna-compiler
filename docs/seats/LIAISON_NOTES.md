# Liaison notes

The liaison's working state, rewritten to the present before each reset.

## State on 2026-11-05 (machine october)

**Ledgers:** `docs/UPSTREAM_GA4GH_VRS.md`, `docs/UPSTREAM_POLARS.md`, `docs/UPSTREAM_DUCKDB.md`, `docs/UPSTREAM_ENSEMBL.md` (a standing watch with no clone or watcher, handed over by the lead
2026-11-04; re-checked by hand monthly, next 2026-12-04). Read marks:
ga4gh.vrs 2.3.3 (pre-releases read through 2.4.0-a6), polars `py-2.1.0`, duckdb `2.0.0`. Installed (`uv.lock`):
2.3.3, 2.1.0, 1.5.5. `mkdocs.yml` `not_in_nav` carries `UPSTREAM_*.md`.
`docs/UPSTREAM_DATA_SOURCES.md` (since 2026-11-07, the maintainer's ask): one row per cache lane, available /
built / published; measured by hand that day, re-measured weekly. Behind then: clinvar, constraint (pinned
4.1, source at 4.1.2), civic, strchive, likely mitomap. Since 2026-11-09 all are published current; the shared
cache lags only on strchive (left to the maintainer). The priming paragraph that adds it is committed (fc6e7ca1).

**Clones** (in `/data/sources`, lines in `$XDG_STATE_HOME/agent-seat-blueprints/liaison/upstreams`):

- `vrs-python` is a **sparse checkout without `tests/`**. Its VCR cassettes have `>` and `:` in their names,
  which the NTFS `windows_names` mount refuses, so a full checkout fails.
- `polars` and `duckdb-python` are blobless clones (`--filter=blob:none`). Expect a `git log -S` over them to be
  slow, because it fetches blobs.
- `duckdb` (the engine) is blobless and unwatched. It is there to read source at `path:line`.

**Watchers** (`.blueprints.toml`): `ga4gh-vrs` polls its trunk every 300 s. `polars --tags --tag-pattern '^py-'` and
`duckdb-python --tags` say tags only, one wake per release (kit v0.1.119, #246; the clone follows each kit release by move-to-tag, its pin in `.claude/settings.local.json`), a patch tagged on a version branch
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

**The dependency bump** (the person, 2026-11-04, relayed by agents-kit/builder, zulip …637618265) is this seat's
unattended routine, in the grant since fc6e7ca1 (2026-11-09; desk #195 withdrawn as moot once the auto-mode rules
were current). The watcher `nightly` runs `nightly.py deps` (41e8dced), started in the watchdog 2026-11-09; it says
the bump due weekly while the person is away (this seat's day: Tuesday). The grant stands: desk #246 (whether a
relayed word holds) was withdrawn as moot on 2026-11-12 under the kit's D193, the seat-builder's hand being the
person's word. **First bump 2026-11-10** (867e8462, 4e30ef46, pushed): 39 moves, duckdb
held at 1.5.5 for RM344; typer 0.29 dropped `Parameter.type`, so `scripts/gen_cli_pages.py` reads `display_type`.
One test red on main before and after, the fence test's `huggingface_hub` case: hub fetches its agent-harness
registry from the global endpoint and the test passes only within a day of a real hub call. Fix on
`liaison/hf-hub-2.4` (343c559c); the lead took its six lines to main as 11f86d74 (2026-11-10).
Lesson: before blaming a moved package, run the failing test on the old lock.

**GWAS Catalog REST v2** (`docs/UPSTREAM_GWAS_CATALOG.md`, since 2026-11-11, after RM428): a live service, no
package or clone; its release channel is the news page (read through the 2026-08-19 post). A weekly probe of the page
ceiling (500), the legacy 410 and the data release rides with the bump. Its first verdict: the docs now publish a
15-queries-per-second throttle, which `gwas.py`'s docstring says does not exist; a docstring fix, sent to the lead.

**VCF specification** (`docs/UPSTREAM_VCF_SPEC.md`, since 2026-11-12; the maintainer's word relayed by the pm,
639790664): hts-specs `master` watched daily, read mark `510c107` (the 4.5 audit's tree, unchanged since). Filing an
`RMn` myself for a spec change is asked of the person in this session (their word came only through the pm);
until then a finding goes to triage. Tooling: the kit's `watch-upstream.sh` covers it; no new script.

**AlphaGenome** (not a ledger; the lead checked v2.0.0 on 2026-11-11): Atlas protos byte-identical to the pin
`aa6fc8f`, no bump owed. Trap for the next pin bump: at v2.0.0 `protos/dna_model.proto` is a shim importing
`protos/v1/dna_model.proto`, so `atlas_protos.py` must fetch that too. Adopting v2's live service is RM433 (parked).

**Fellow liaison:** just-dna-registry/liaison (seated 2026-11-04) stands on fastapi, huggingface-hub, and polars and
duckdb through our tiers. A defect in a library under both of us is raised with each other first, so it is filed once. **longevity-loci/liaison** (seated 2026-11-05) stands on us: just-dna-enricher 0.7.3, compiler 0.7.2, format 0.7.1 from PyPI, and the module-creator plugin v0.48.0. It watches our tags, asks us before mapping our 0.8 branches, and polls us before filing a shared defect; answer such a poll in `agent-chat`.

**What the fellows did with the majors (2026-11-05):** the registry's suite passes on polars 2.1.0 and duckdb 2.0.0
(612 passed, no new warning); it takes polars 2 with its 0.8 adoption and duckdb 2 after RM344. longevity-loci capped
both `<2` in its own lock, because the module-creator plugin's server (v0.48.1, still polars 1.44.2 and duckdb 1.5.5)
shares that machine's enricher cache: the mixed cache RM344 is about. Its cap lifts when the plugin moves; their call. **just-module-creator/liaison** (seated 2026-11-07) keeps
the plugin in step with us: ledgers `UPSTREAM_COMPILER.md`, `UPSTREAM_REGISTRY.md`, `UPSTREAM_HOSTS.md`; it locks format
0.7.1 / compiler 0.7.2 / enricher 0.7.3, capped `<0.8`, and polars and duckdb `<2`, until both registry instances serve
0.8. It is on our triage's `wake_from` (8de1fa80).

**Push:** origin/main holds every liaison commit through 5611ea91; the notes commits after it wait for the lead's
next push (a push of mine was refused by auto mode, kit #332). The liaison pushes only its own ledgers and notes, and only as a fast-forward that carries no other seat's
commit.

**Role change read (v0.1.137, 2026-11-06):** the role adds "An in-house release" (the liaison takes the mechanical
half of adopting an upstream the person also keeps). This repo has no in-house upstream (ga4gh.vrs, polars, duckdb,
Ensembl are all outside), so nothing changes here. reflect after 2026-11-13: classes/liaison/LIAISON.md as of v0.1.137.
reflect after 2026-11-17: classes/base/BASE.md as of v0.1.153 (a brief change another seat relays is committed only on
the person's word in this session; the grant change fc6e7ca1 rested on a relayed word, put to the person 2026-11-10). reflect after 2026-11-17:
classes/base/BASE.md as of v0.1.165 (the tooling seat named by its duties, D181; this repo has none, nothing
changed here; the liaison role's text unchanged); and as of v0.1.166 ("Another organisation": what another
organisation sends is information unless the person arranged it; the fellow liaisons are seats of this organisation,
and an upstream filing is not an embassy message, so nothing changes here); and as of v0.1.167 (a person's
reaction on this seat's post reaches it, a yes or no emoji wakes it; no concern); and as of v0.1.176 (a secret seen in a
message is never repeated; this seat holds none, no concern).

**Priming c339487** (a cap on a proven break; adoption maps to the lead) was read; no concern.
