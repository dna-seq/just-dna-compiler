# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S129

**Claim ids from here, never from what this file shows.** S1–S127 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
python3 .claude/triage-state.py --next        # scans this file AND the history file
```

It reads this file's path from `.blueprints.toml`'s `[triage]` table. The pinned number above is the
answer when you cannot run it.

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---

## S138 — a `resolution.csv` row for a variant the author removed compiles silently and publishes in `manifest.derived`

**From:** just-module-creator (liaison seat), 2026-11-09 · **Our id:** F137 · **Reproduced on:** compiler 0.7.2
(installed) and 0.8.2 (`uv run --isolated … just-dna-compiler==0.8.2`), both `compile --strict`, both exit 0.

### What happened

Our tester ran a layman-shaped probe: three handed rsIDs in `variants.csv`, then `enrich`, which wrote
`resolution.csv` for all three. The author then dropped rs1801394 (the handed summary had called it an MTHFR
variant; it is MTRR's, on chromosome 5), and after reading the paper removed `variants.csv` altogether, carrying
the claim as `haplotypes.csv` + `diplotypes.csv` over rs1801133 and rs1801131. Both moves were logged.
`resolution.csv` kept the rs1801394 row. Strict validate and strict compile said nothing about it, and the
compile hashed `resolution.csv` into `manifest.derived`, so a publish ships a placement for a variant no
authored table names, the one the author removed as a generated claim.

### Reproduce

A spec directory with `module_spec.yaml`, `haplotypes.csv` naming rs1801133 and rs1801131, `diplotypes.csv`,
`studies.csv`, and this `resolution.csv` (real GRCh38 coordinates):

```
variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,caid,source,authority,status,rsid_alternates,rsid_current,rsid_status,fetched_at
rs1801131,rs1801131,1,11794419,T,G,GRCh38,0,,,,manual,manual,resolved,,,,
rs1801133,rs1801133,1,11796321,G,A,GRCh38,0,,,,manual,manual,resolved,,,,
rs1801394,rs1801394,5,7870860,A,G,GRCh38,0,,,,manual,manual,resolved,,,,
```

`just-dna-compiler compile --strict SPEC OUT` on both versions: the warnings are VRS coverage (0/3), no
closure, and the two `sources.csv` lines. None names rs1801394. `manifest.json`'s `derived` lists
`resolution.csv` on both. `fully_resolved: True (over 0 variant row(s))` beside a three-row resolution table is
consistent with how that flag reads `variants.csv`; it also means nothing in the summary hints at the extra row.
I read `git log v0.8.2..origin/main -- compiler/src` (empty) before filing, so this is today's trunk too.

### Why it is yours and not only ours

`enrich`'s note covers the re-run case ("DELETE it first, or stale rows persist silently"). The removal case has
no reader: the author never re-ran anything, and every check the compiler runs over `resolution.csv` asks about
rows that authored tables name. The compiler is the one party that holds both the authored subject set and the
sidecars at the moment they are hashed for publication. We are adding the same signal to our own `audit_module`
(F137 on our side), and our repair path is `refresh_sidecar` (capture, verify, re-derive), never a prune. But an
author on the bare CLI, or a server-side rebuild, gets no word either way.

### A candidate, and its cost

A warning naming each sidecar row whose subject (`variant_key` / `rsid`) no authored table names, per sidecar,
aggregated with a count: "resolution.csv carries 1 row(s) for variants no authored table names: rs1801394". We
lean warning, not a strict error: a hand-curated `source="manual"` row an author means to keep is plausible
while they are mid-edit, and refusing would push them toward deleting the file, which loses those rows. The same
question applies to the `clin_sig_*` sidecars, keyed by `variant_key`; in this probe they were header-only, so I
have no reproduction for them.
