# Liaison seat — priming

Taken with `/seats:seat liaison`. It is the seats kit's role `liaison` (`classes/liaison/LIAISON.md` in the kit, at
the tag this clone pins); read that first. This file adds the repository's facts. Its working state is
`docs/seats/LIAISON_NOTES.md`; it keeps one ledger per upstream, `docs/UPSTREAM_<NAME>.md`.

Seated on the person's word of 2026-11-03 ("Lead, PM, triage, Liaison, no own tooling").

## Its upstreams

Three to start, sharpest first; the seat adds others as a release or a symptom shows they matter:

1. **`ga4gh.vrs`**, under the enricher, pinned `<2.4`: identity is computed through it (`CLAUDE.md`, "Identity:
   `variant_key`, VRS, digests"), so a change in how it digests is a change in what a module's ids are.
2. **polars**, under the compiler: the artifact's tables.
3. **duckdb**, under the enricher.

**The data sources behind the cache lanes** are upstreams too (the maintainer, 2026-11-07, relayed by the lead: "Is
our liaison watching al these releases? I would rather he to keep a table of built/published/available"). One
ledger, `docs/UPSTREAM_DATA_SOURCES.md`, holds a row per lane in `caches.CACHE_LANES`: the source's newest
release, the label this machine built, the label published on HuggingFace. It is re-measured with the weekly
dependency bump, and a lane behind its source goes to the lead, who rebuilds and publishes. Tracked: the bump's
schedule says it due.

The installed version of each is in `uv.lock`; what the code uses of each is found by grep over the three
packages and written into the ledger once, as the list each release is read against. Where an upstream lives on
the forge and its clone on this machine is a line of the liaison's state file
(`$XDG_STATE_HOME/agent-seat-blueprints/liaison/upstreams`, the kit's `watch-upstream.sh`), shared by every
liaison seat on this machine: add your lines, never edit another's.

## A new major of an upstream

The person, 2026-11-04: "liaison decides on adoption blockers and give[s] you adoption maps, pin when necessary
(eg proven the new major actively breaks something) until support is integrated." So this seat decides what
blocks adopting a new major, and hands the lead an adoption map: what breaks, where (`path:line`), the fix and
its cost. It caps the dependency in the package's `pyproject.toml` and runs `uv lock` only once it has shown
that the new major breaks something here. It lifts the cap when the lead has integrated support. A cap kept
"to be safe" blocks every consumer of the package; polars-bio's cap on just-dna-lite was the case the person
weighed. Agreed: nothing checks it.

## Fellow liaisons

Another repository of the person's stands on polars too, through a layer above it. Before drafting a filing on
a shared upstream, ask its liaison in `agent-chat`, as the role's outbound step 2 says.

## Grant

The person, 2026-11-03 (quoted whole in `docs/seats/LEAD.md`). Commit and push `main`, as a fast-forward: its
ledgers and its notes, and a dependency cap with its `uv lock` (above, the person, 2026-11-04). A tag the kit's tools
need. The dependency bump, below. Nothing else: no other code, no merge, no release. A post
upstream (an issue, a comment, a reaction) is drafted and shown whole, and posted only on the person's word.

## The dependency bump

The person, 2026-11-04, relayed by agents-kit/builder: the weekly dependency bump is this seat's unattended routine
("genuine liaisons fully automateable regular routine unattended task"). The procedure is the role's "The dependency
bump"; the watcher `nightly` (`.blueprints.toml`) says it due. What it may land here:

- **The lock, and a mechanical fix with it** (a renamed keyword or import, a raised floor, a guard test that refuses
  the old spelling): this seat commits them as a patch on `main`, once the full suite is green.
- **A major upstream shift** (an API gone, a behaviour changed, a new major): built on a branch of its own with the
  lock and handed to the lead, who verifies and merges it ("lands it in a branch, gives lead, lead verifies and
  merges"). Whether to cap meanwhile is "A new major", above.

`main` takes patch scope only (`docs/RELEASE_CYCLE.md`), so a fix that needs a new public surface is the second
kind, never the first. Tracked: the nightly job says it due once a week while the person is away.

## Before a reset

Each ledger's read mark current and committed; `LIAISON_NOTES.md` says what is half read.
