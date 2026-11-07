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

## S133 — an online re-derivation spends most of its time in silent Ensembl REST timeouts, and a host cannot see, bound or batch them

*Reporter: just-dna-registry (lead), 2026-11-07, enricher 0.8.0.*

**What we ran.** `registry upgrade --apply --online` on the polygon's 46 modules took 39 minutes, and five
online modules took as long as the other 41 together. We then timed one module ourselves
(multimorbidity_aging_v3: 522 rows, 178 rsIDs): offline enrichment took 11 s; the online re-derivation took
672 s, and 599 s of that was 59 Ensembl REST GETs. 26 of them were `ReadTimeout` at 15.2 s. Five rsIDs
used all 3 attempts and gave up, about 48 s each. The live link placed **none** of the 38 rsIDs it asked
about. Every one was an rsID the snapshot had already placed, rejected under RM382 because the authored
genotype is the reverse complement. Live Ensembl returned the same locus, and the rejection repeated.

**What we measured about the server.** A first GET for an rsID takes 1–12 s, and a repeat 0.21 s.
Abandoning a GET at 4 s and retrying 2 s later still took 7.8–18.1 s, so an abandoned request does not
warm Ensembl's cache, and a shorter timeout only buys more cold first requests. One
`POST /variation/homo_sapiens` with 10 cold ids took 13.9 s, against roughly 100 s one at a time. Raw
numbers: `/tmp/claude-1000/-data-sources-just-dna-registry/c018d93d-31a4-4167-9074-a2bd131ddf82/scratchpad/measurements.md`
(copied to `/data/just-dna-cache/upstream-evidence/registry-replay-2026-11-07/timing/`).

**What a host cannot do today, ranked by measured cost** (paths under `site-packages/`):
1. **Batch the live link.** `enrich/orchestration.py:962` asks one rsID per GET. The batch endpoint takes
   up to 200 ids. Failing that, ask concurrently, bounded, through the resolver's gate.
2. **Skip a live ask that cannot change the answer.** An rsID whose snapshot placement was rejected only
   for strand (RM382) gets the same answer live. On this module that was 38 asks, 0 placed, about 600 s.
3. **See retries.** No tenacity policy has `before_sleep`, and httpx logs only responses, so a timed-out
   attempt leaves no line. The give-up WARNING (`ensembl.py:207`, `orchestration.py:1036`, `:1976`)
   carries neither an attempt count nor the time spent. An operator watching a slow sweep cannot tell
   N×timeout from a slow server.
4. **Share the paced clients everywhere.** `enrich()` builds its own eutils client (`orchestration.py:1959`)
   and a fresh `SequenceProxy` per call (`:728`). Ga4gh's seqrepo proxy calls `requests.get` with **no
   timeout** (`ga4gh/vrs/dataproxy.py:260,269,278`): 141 serial, unpaced reads on one module, 36 s.
   An `eutils_client=` and a `sequence_proxy=` argument, or a whole `LookupClients`, would let a host pace
   them. Until then we run such enrichments one at a time.
5. **Bound retries.** `JUST_DNA_HTTP_RETRY_ATTEMPTS` is a floor (`net.py:131-175`, `max(default,
   configured)`), and the backoff constants are fixed in the decorators. A host can raise the attempt count
   but never lower it.
6. **Offline floor.** 9 of the 10 s of an offline enrichment is four `duckdb.execute` scans by rsID
   (`resolver.py:489`). An indexed or sorted rsID lookup on the Ensembl snapshot would cut every offline
   sweep.

**What we did meanwhile.** Registry 0.28.2 re-publishes modules in parallel (`--jobs`, default 4) through
one shared, paced client bundle, so waits overlap without raising the request rate. It hands `enrich()` the
shared GRCh37 client, and it adds a per-request timeout setting that is left unset, because our
measurements say shorter is worse. None of this reaches the per-rsID GET loop, which is yours.
