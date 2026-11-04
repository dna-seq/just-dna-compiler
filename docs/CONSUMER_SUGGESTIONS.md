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

## S128 — every enricher import warns that tenacity's `initial` is deprecated, and a tenacity that drops it would stop the enricher importing

*From prepare-annotations (`v1-port` extra, `pytest`), 2026-11-04, enricher 0.7.3, tenacity 9.2.1.*

**What we ran.** `uv sync --extra v1-port` in prepare-annotations, which resolves just-dna-enricher 0.7.3
and tenacity 9.2.1 (the latest, released 2026-10-07), then `uv run pytest tests/test_v1_port.py`.

**What we expected.** No warnings from the enricher at import.

**What happened.** Six `DeprecationWarning: The 'initial' parameter is deprecated, use 'multiplier'
instead`, from `clingen_allele.py:246`, `ensembl.py:168` and `:190`, `civic_api.py:329`, `gnomad.py:306`
and `grch37.py:115`: the modules our port imports. They fire at import, because each one builds a
`wait_exponential_jitter(initial=...)` in a module-level `@retry` decorator. The same keyword is used at 22
call sites across 17 modules on `0.8` (18 on `main`). `net.py`, `ensembl.py`, `literature.py` (4), `eutils.py`
and `pharmvar.py` are among them.

The risk is more than noise. A tenacity release that removes `initial` turns every one of those
decorators into a `TypeError` at import. The floor is `tenacity>=9.0.0` with no cap, so a fresh resolve
would pick that release up, and every enricher command would die at import. That is the same failure
shape as the protobuf `VersionError` S107 fixed.

**What we did meanwhile.** Nothing. The warnings are harmless today, and prepare-annotations leaves its
warning filters alone.

**Candidate fix.** Rename the keyword to `multiplier=` at every site. In tenacity 9.2.1 it is a drop-in
replacement: the constructor assigns `multiplier = initial` when only `initial` is given, and the wait is
`multiplier * exp_base**(n-1) + jitter` either way, so backoff timing is unchanged. **It needs a floor
bump**, because `multiplier` does not exist before 9.2.1. Measured: 9.1.4's `wait_exponential_jitter`
takes only `initial, max, exp_base, jitter`, and PyPI has no 9.2.0. Raising the floor to
`tenacity>=9.2.1` is a patch-legal dependency move. An AST guard over `src/` that refuses `initial=` in a
`wait_exponential_jitter` call would keep a new site from bringing it back. Wrong option: suppressing the
warning hides exactly the removal this protects against.
