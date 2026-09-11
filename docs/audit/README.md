# Audit snapshots — the tier references, re-derived from the code

Three technical references for `just-dna-format`, `just-dna-compiler` and `just-dna-enricher`, written
on **2026-09-11** from the source and the tests alone. They exist to be read *against*
[SCHEMAS.md](../SCHEMAS.md), [COMPILER.md](../COMPILER.md) and [ENRICHER.md](../ENRICHER.md), not
instead of them.

**These are evidence, not contract.** The maintained reference for each tier is the one in `docs/`.
Nothing here is updated when the code moves, and a reader who patches a fact into one of these files
has patched the wrong document — that is the "second thing to update" failure this repo has removed
twice already (`AUTHORING*.md`, `/write-module`). If a claim below is wrong *today*, the right response
is to check whether the maintained doc is also wrong and fix that one.

## Which round these files are

**The three files here are the 2026-09-11 round.** They replaced the 2026-08-18 ones in place rather
than sitting beside them, because two dated snapshots of one surface is the second-thing-to-update
problem this directory is already one step away from. The first round is in git at `0e5fc58^` —
`git show 0e5fc58^:docs/audit/ENRICHER_FROM_CODE.md` — and its durable material was merged in 2026-08-18
and again in 2026-09-11, so what is in history is the evidence, not a live claim.

Two notes on reading the 2026-09-11 files specifically. Their defect sections cite reproducers under a
session scratchpad that no longer exists; the ones that were real became permanent tests, which is
where to look instead — every item the round confirmed owes one, and
[BLIND_REDERIVATION.md](../BLIND_REDERIVATION.md)'s Rounds table lists what the round came to rather
than repeating a tally here. And a defect candidate in them is a **candidate**: the maintainer pass
reproduced each one before filing it, and left the rest recorded rather than filed. An entry here is
not an open item — ROADMAP is.

Worth recording which way the one disagreement went, because it ran opposite to the expectation. A
*static guard written during the repair* flagged `gwas._get`'s bare `except … : raise` as swallowing
what its decorator retried; reading it refuted the guard, not the code — a handler whose whole body is
`raise` swallows nothing, and the guard now exempts that shape. The **enricher snapshot's** own claim
about the same function (D10: the exhausted transport leg reaches no translation) was correct, and is
RM208's second half.

## The long tail was triaged on 2026-09-11, and two candidates were refuted

The defect sections were worked to the end rather than left. What shipped is in ROADMAP_HISTORY; two
entries are recorded here because the right outcome was **not** a fix, and a later round that
re-derives them should stop at this paragraph.

- **Enricher D6 — `uv sync` performs a network fetch — refuted as a category error.** `uv sync`
  resolves and downloads from PyPI for every package in this workspace, so by that reading
  `just-dna-format` fetches too. The tier rule this was measured against ("only the enricher
  fetches") is about a library's **runtime** behaviour, not about installing it; applying it to a
  build-and-install operation makes it vacuous. The hook's own fetch is pinned, digest-verified and
  documented, and the maintainer confirms it was the intended design from the start. Not a finding.
- **Schema D8 — `chrom` validated on one model of five — deliberate, and the comment beside it was
  the actual defect.** The asymmetry is intended and the vocabulary marker is correctly withheld
  wherever nothing rejects. What was wrong is that the explaining comment named `StudyRow.chrom` as a
  validated counterexample at two sites, and `StudyRow` has no chrom validator. Fixed under RM225;
  the design is unchanged, and 709 corpus cells carry 3 non-canonical spellings, all in the one table
  that normalizes.

The self-declared warts (schema D6/D7, compiler 13.7) are now **RM226**, and RM215's surfaced half is
**RM227**, so neither lives only in a comment any more.

## The method has its own document now

**[BLIND_REDERIVATION.md](../BLIND_REDERIVATION.md) is the pattern; this file is one round's
evidence.** The distinction cost something to learn: the 2026-09-11 round had to reconstruct the
method out of this README and a commit message, because a reusable procedure had been written down
only as the preamble to its first output. What follows here is kept as that round's own record — the
method doc generalises it, records the second round, and is where a third one starts.

## Why write a document you already have

Reading a reference against the code it describes has a failure mode: the reference tells you where to
look, so you check what it claims and never notice what it omits, and a sentence that was true two
releases ago reads as true because you are verifying it rather than deriving it. Writing the document
again from scratch, with the existing one unread, removes that anchor. Then the two can be compared as
peers, and every disagreement asks the same question — **which of these is wrong?**

Eight times the answer was *the code*. Those are
[RM93–RM100](../ROADMAP_HISTORY.md#061--the-eight-the-documents-caught-the-two-the-fixes-found-and-rm88),
all **shipped in 0.6.1**, and every one of them broke a rule this repo had already written down —
which is the finding the pass is really evidence for. The pass
also found the reverse: `@rm43-snp-core-only` was describing, in the present tense, the problem RM43
had already fixed — along with three "still live" traps that were all closed.

## Method, and the one caveat that weakens it

Three agents, one per tier, each reading only its package source, its tests and its `pyproject.toml`,
with `docs/*.md` off limits. Each was told to write "undetermined from code" rather than guess, and
those lists are part of the output rather than an admission — they mark where the code does not explain
itself.

**The isolation was not perfect, and it should be stated rather than glossed.** The harness injected
`CLAUDE.md` into each agent's context before it could act, so "code-only" was unenforceable at the
transport level. All three reported it unprompted; each says it sourced no claim from that file and
followed none of the code's `docs/…` pointers. One found `CLAUDE.md` itself stale against the code,
which is what surfaced the RM43 correction — so on the evidence the contamination cost less than it
threatened, but a second run of this exercise should close the hole rather than rely on that.

Two smaller notes. The agents ran in git worktrees cut from `HEAD`, so the enricher one saw
`docs/pharmvar_api_docs.json` at its pre-reorganization path. And each confirmed the CLI surfaces by
running `--help` rather than reading the Typer decorators, which is how the 26-vs-23 command
discrepancy in RM100 was measured rather than inferred.

## What is in each file

Each is a full reference for its tier, and in several places more complete than the maintained document
— which is the other reason to keep them. Between them they carry a per-check validation table with
validate/compile/severity columns, per-parquet column lists with the compiler-stamped columns marked,
field-by-field tables for every authored row model, the complete 37-command enricher surface, the
resolver chain with what `--offline` changes per pass, and the hash family with exactly what bytes
enter each one.

**The merge was done on 2026-08-18, and it was deliberately partial.** What moved into the maintained
docs is the material that is durable and hard to re-derive: COMPILER gained the deterministic-ordering
rules, the warning-text catalogue (`@warning-text-is-api` had a rule and no catalogue) and
`ARTIFACT_PARQUETS` in digest order; SCHEMAS gained the tri-state inventory — the ~18 concrete sites the
house algebra actually lands on — and the full fourteen-function hash roster, which corrected the doc
map's "nine"; ENRICHER gained the six open questions, one of which turned out to be a defect and became
RM100's fifth bullet.

What stayed here is what would **rot** in a maintained document: per-parquet column lists, per-command
flag tables, field-by-field model dumps. Those are derivable from the models and the CLI, and a
hand-kept copy of one is exactly how `SOURCES_FIELDNAMES` lost a column — so the maintained docs point
at `just-dna-compiler describe`, `--help` and the models, and at this snapshot for a dated listing.
That split is the reason these files can be kept at all without becoming the second thing to update.
