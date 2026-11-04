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

## S129 — a strict refusal's errors carry no code, so a consumer cannot tell a module-level one from a per-row one

*From just-dna-registry's liaison seat, 2026-11-04, against format 0.7.1 / compiler 0.7.2 installed, and the `0.8`
branch at `503730c` read.*

**What we ran.** The registry's dry runs (`/validate`, `/check`) grade a spec twice: a modeless
`validate_spec` first, whose verdict becomes `would_publish_module_level`, then a strict one after enrichment,
which is what the publish's strict compile will do. Our reasoning for keeping the module-level verdict from the
modeless pass was the sentence your docstring carried until RM218: *strict changes severity only*, so every
strict-only error was a per-row judgement and belonged to the enrichment tier.

**What happened.** RM218 corrected that sentence, and it was right to: under `strict` two findings are
*aggregates with no `best_effort` counterpart* — the unresolved-position refusal (`strict compile: N variant(s)
…`) and `build_disagreement_error`. The first is per-row and enrichment's, as we assumed. The second is
module-level (one authored file contradicting another about the genome build), and our maintainer decided today
that a module-level strict-only refusal should flip `would_publish_module_level` to false.

We cannot do that without matching a sentence. `ValidationResult.errors` is `list[str]`; warnings got codes and
`warnings_summary` in RM131, errors got nothing, on 0.7.3 and on the `0.8` branch alike (no `errors_summary`, no
coded error in `schema/src` or `compiler/src`). Telling `build_disagreement_error`'s output apart from the
unresolved aggregate means reading its wording, which is yours to change.

**What we did meanwhile.** Queued a correction of our own comments to say what RM218 says, and left the verdict as it is
(module-level from the modeless pass), which is wrong only for a module whose files disagree about the build.

**Candidate fixes.** (a) Errors carry a code from a closed vocabulary, with an `errors_summary` beside
`warnings_summary` — RM131's shape, applied to the other list. (b) Narrower: a field on `ValidationResult` naming
the strict-only module-level refusals (today just the build disagreement). (a) is the general answer and helps
every consumer that grades; (b) is what we need and nothing more. A reason (b) might be wrong: it bakes our
"module-level vs per-row" split into your model, when a code would let each consumer draw its own line.
