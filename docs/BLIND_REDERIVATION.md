# Blind re-derivation — writing the document twice on purpose

The method behind [audit/](audit/README.md), written down as a method rather than as one round's
README. It has been run twice, on 2026-08-18 and on 2026-09-11, and both times the *contradictions*
were the deliverable — not the second document.

**One sentence:** derive the same surface twice, once **top-down** from what the release said it
shipped and once **bottom-up** from the code alone with the existing reference unread, then reconcile
every disagreement by asking which of the two is wrong.

## Why duplicated work is the instrument

Reading a reference *against* the code it describes has a failure mode that effort does not fix. The
reference tells you where to look, so you check what it claims and never notice what it omits; and a
sentence that was true two releases ago reads as true because you are verifying it rather than
deriving it. Both halves of that are anchoring, and an auditor who knows about anchoring is still
anchored.

Writing the document again from scratch, with the existing one unread, removes the anchor. Then the
two can be compared as peers, and every disagreement asks the same question — **which of these is
wrong?** — instead of the question a review asks, which is "can I find a problem with this sentence?"

The duplication is therefore not waste to be minimised. Running only the bottom-up half produces a
second reference nobody maintains; running only the top-down half reproduces the anchoring. The value
is in the *diff*, and a diff needs two inputs.

## The two directions, and who does which

**Top-down** is the maintained doc's own owner, working from CHANGELOG, ROADMAP_HISTORY, the RM
entries and the release's stated intent. It asks *what did this release promise, and does the
reference say it?* It finds **omissions** — a pass that shipped with no section, a source with no
licence row, an RM whose surface is described nowhere — because it starts from a list of things that
are supposed to be there.

**Bottom-up** is one agent per tier, reading only that tier's `src/`, its `tests/` and its
`pyproject.toml`, with the maintained docs deleted from its tree. It asks *what does this code
actually do?* It finds **false claims and drift** — a count that moved, a flag that no longer exists,
a rule the code states in one place and breaks in another — because it never sees the sentence it
would otherwise be tempted to confirm.

Neither direction finds the other's class of defect reliably. That is the whole argument for running
both.

## Running the bottom-up half

- **One agent per tier**, in a **detached git worktree** cut from `HEAD`, with `docs/`, `CLAUDE.md`,
  `AGENTS.md`, `README.md` and `reference_examples/` deleted from it. Deleting is what makes the
  isolation real; an instruction not to read something is not isolation.
- **The harness still injects `CLAUDE.md`**, and that cannot be prevented from inside the session. So
  each agent is told to source no claim from it and to **state unprompted** whether anything in its
  document came from it. Both rounds disclosed this; on the first one an agent found `CLAUDE.md`
  itself stale against the code, which is how the RM43 correction surfaced — the contamination has so
  far cost less than it threatened, and it is still a hole.
- **Confirm a CLI by running `--help`, never by reading the Typer decorators.** The 26-vs-23 command
  discrepancy in RM100 was *measured* that way rather than inferred.
- **Write incrementally, section by section.** The enricher tier is ~180 files; an agent that holds
  the whole document in memory and writes once loses everything to a crash at the end.
- **"Undetermined from code" is part of the output, not an admission.** An agent that guesses to look
  complete destroys the comparison, because a guess that happens to match the maintained doc reads as
  confirmation. One of the first round's six open questions turned out to be a real defect and became
  RM100's fifth bullet.
- **Prefer measuring to inferring.** If a count matters, compute it against the models; a number read
  off a list is the thing this whole exercise exists to catch.

## Reconciling — every disagreement has exactly four outcomes

1. **The code is wrong.** This is the one the exercise is for. The first round produced eight of them
   (RM93–RM100), and the finding underneath all eight is that *every one broke a rule this repository
   had already written down*.
2. **The maintained doc is wrong.** Patch it, and ask whether the same claim is repeated somewhere
   else — a stale fact usually has copies.
3. **Both are right, at different scopes.** Say so explicitly in the maintained doc. A dated,
   deliberately-scoped table beside a complete registry is not a contradiction, and collapsing them
   loses the date.
4. **The re-derivation is wrong.** It happens, and it is not a failure of the round. Answer from the
   code, never from either document's prose.

Decide these yourself, from the code and the charter. **Delegation is for finding, never for
deciding** — a summary of a rule drops the qualifier the decision turned on.

## The rule that makes a round worth more than its findings

**A finding with no walking test is a finding that recurs.** Every drift this method has caught was in
prose, and nothing walks prose, so the third drift gets discovered the way the first two were — by a
reader who happens to care. Both rounds ended with counts being re-counted, which fixes instances and
not the class.

So a reconciliation is not done when the doc is correct. It is done when the registry behind the
claim is **asserted over a walked set** (`@registry-completeness`), in a test that reads the
maintained document. `test_counted_prose.py`, `test_warning_codes.py`, `test_module_map.py` and
`test_enricher_doc_registries.py` are all that shape, and each exists because a specific sentence went
stale. Prefer equality where both directions are entailed; prefer containment where only one is, and
say which in the docstring (`@a-record-written-in-two-passes-drifts-between-them`).

## What to merge, and what to leave in the snapshot

The merge is **deliberately partial**, and the split is by **rot rate**, not by importance.

- **Merge what is durable and hard to re-derive**: the rules, the rosters, the reasons, the warning
  catalogue, the per-check severity table, the hash family and what enters each hash.
- **Leave in the dated snapshot what a tool can print**: per-parquet column lists, per-command flag
  tables, field-by-field model dumps. A hand-kept copy of one is exactly how `SOURCES_FIELDNAMES` lost
  a column (`@fieldnames-from-model`), so the maintained docs point at `describe`, `--help` and the
  models, and at the snapshot for a dated listing.

That split is the only reason a second set of files can be kept here at all. This repository has
deleted a redundant second description of the same surface twice (`AUTHORING*.md`, `/write-module`),
both times because the next reader patched a fact into the wrong one. So the framing on every snapshot
file is load-bearing: **a dated snapshot, never updated, evidence and not contract**, and a wrong
claim in it means checking whether the maintained doc is wrong too.

## When to run it

After a release's work has landed and before it is cut. Not on a schedule — the trigger is that
enough has shipped that the maintained reference is being trusted for things nobody has re-read. Both
rounds were run in exactly that position.

## Rounds

| Date | Found |
| --- | --- |
| **2026-08-18** | RM93–RM100 (eight code defects, every one breaking an already-written rule); the `@rm43-snp-core-only` rule describing in the present tense a problem RM43 had fixed; three "still live" traps that were all closed; six open questions, one of which was a defect |
| **2026-09-11** | Top-down half: SCHEMAS' module map eight modules short; ENRICHER's twenty-six short with a duplicated row and two stale counts; the check table missing `variant_impact_agreement`, a vocabulary member whose own comment says it was audited against that table; no AlphaGenome section in the tier that produces `expression_effects.csv`; the licence table scoped to PGx where the registry holds eighteen sources; `INTEGRATION_0_7.md` contradicting itself on whether RM143 had shipped, and calling the shipped RM194 open |
