# Audit snapshots — the tier references, re-derived from the code

Three technical references for `just-dna-format`, `just-dna-compiler` and `just-dna-enricher`, written
on **2026-08-18** from the source and the tests alone. They exist to be read *against*
[SCHEMAS.md](../SCHEMAS.md), [COMPILER.md](../COMPILER.md) and [ENRICHER.md](../ENRICHER.md), not
instead of them.

**These are evidence, not contract.** The maintained reference for each tier is the one in `docs/`.
Nothing here is updated when the code moves, and a reader who patches a fact into one of these files
has patched the wrong document — that is the "second thing to update" failure this repo has removed
twice already (`AUTHORING*.md`, `/write-module`). If a claim below is wrong *today*, the right response
is to check whether the maintained doc is also wrong and fix that one.

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
