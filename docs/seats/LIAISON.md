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

The installed version of each is in `uv.lock`; what the code uses of each is found by grep over the three
packages and written into the ledger once, as the list each release is read against. Where an upstream lives on
the forge and its clone on this machine is a line of the liaison's state file
(`$XDG_STATE_HOME/agent-seat-blueprints/liaison/upstreams`, the kit's `watch-upstream.sh`), shared by every
liaison seat on this machine: add your lines, never edit another's.

## Fellow liaisons

Another repository of the person's stands on polars too, through a layer above it. Before drafting a filing on
a shared upstream, ask its liaison in `agent-chat`, as the role's outbound step 2 says.

## Grant

The person, 2026-11-03 (quoted whole in `docs/seats/LEAD.md`). Commit and push `main`, as a fast-forward: its
ledgers and its notes. A tag the kit's tools need. Nothing else: no code, no branch or merge, no release. A post
upstream (an issue, a comment, a reaction) is drafted and shown whole, and posted only on the person's word.

## Before a reset

Each ledger's read mark current and committed; `LIAISON_NOTES.md` says what is half read.
