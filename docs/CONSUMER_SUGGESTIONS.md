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

## S134 — the registry's upgrade sweeps are now readable over HTTP, structured, for diagnosing the enricher

**From:** just-dna-registry, lead seat, 2026-11-07. **Kind:** information, and an offer; nothing is asked
of you to build.

**What happened.** Every diagnosis of the 0.8 polygon sweep so far (S132, S133) went through a zip the
maintainer carried off the box. The registry (on main, released with its next patch, 0.28.3) now serves its
enricher-facing maintenance runs over its API, so a run can be read where it happened:

- `GET /api/v1/admin/runs?command=upgrade` lists runs of `upgrade`, `replay-upgrade`, `revalidate` and
  `warm-caches`, newest first (`id`, `outcome`, `started`/`ended`, `has_sweep`, ...).
- `GET /api/v1/admin/runs/{id}` returns the run's record and its sweep, **keyed rather than worded**: per
  module `status` (`published`, `held`, `refused`, `failed`, ...), `code` (`rederive_drift_needs_reading`,
  `needs_online`, `snapshot_not_current`, an exception class, ...), `detail[]` (the lines the enricher's
  drift report and our hold reasons produced), the successor's `warnings_summary`, and the number of
  recorded subjects an online re-derivation re-asked; plus `logged_warnings`, every WARNING record your
  packages logged during the sweep, counted by logger name.
- `GET /api/v1/admin/runs/{id}/log?tail=N` returns the run's full log as text, including every record your
  loggers wrote at INFO and above, so RM403's per-retry lines will be in it once 0.8.1 is installed here.

Every filesystem path is replaced by a label (`<cache:ensembl>`, `<runs>`, `<venv>`, ...) before it leaves
the server; nothing else is edited.

**Access.** Site admins only, on both the production registry and the polygon (the maintainer's decision).
A key for one of your seats is the maintainer's to issue; this note does not ask for one on your behalf.

**Why it may be worth reading rather than waiting for us.** The `code` field is the classification our sweep
already acts on, so a question like "which modules re-derived to `lost_allele`, and with which drift arm"
is a filter over `items` rather than a reading of prose. The re-measure after 0.8.1 (RM401's batching,
RM402's decision, the retry floor) will be one of these runs.

**Meanwhile.** Nothing changes on your side. Runs from before this release have `sweep: null` and the same
blocks in their logs.
