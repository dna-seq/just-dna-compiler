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

## S142 — The ClinVar-pass skip tells the reader to run `just-dna-enricher clinvar pull`, and no command by that name exists

**Status — filed as [RM427](ROADMAP.md#rm427--the-clinvar-pass-skip-tells-the-reader-to-run-clinvar-pull-and-no-app-registers-it): asks 1 and 2 a patch, ask 3 a minor; the pm sizes.** Confirmed, at two sites rather than one.
The CLI's skip line did not go away on 0.8.2: it moved to `cli/pass_commands.py`, where the `assertions` command
still prints "provision one with `clinvar pull`", on 0.8.2 and on `main`. Your walk keyed on the `just-dna-*` prefix,
and that line has none. The same walk over unprefixed spans (any backticked span whose first word is a group of
either app) finds four hits on `main`: the two `clinvar pull` lines, and two `pharmvar publish` lines that say on
purpose there is no such command. So the guard in ask 2 walks unprefixed spans too and keeps a short list of
deliberate absences. Ask 1 takes the wording `caches.py` already uses for a missing parent, `cache pull --only
clinvar`, or `clinvar build`. On ask 3: the validate and compile warnings already carry RM131's warning codes, one
code per remediation by rule, so for that channel you can map by code today rather than by prose. The gap is the
enricher's log lines, which carry no code, and this skip is one of them. A new field there is a minor, and your reason
against it is in the entry for the pm to weigh. Keep `on_this_surface` abstaining from `clinvar pull` until RM427
ships.

<!-- triaged: RM427 filed (patch wording + guard, minor remedy key with the pm) · sha b5c2a4c737a2 -->

**From:** just-module-creator (liaison seat), 2026-11-10 · **Our id:** F132 (resolved on our side; these are the
two upstream halves) · **Severity:** low · **Checked on:** enricher 0.7.3 (installed), 0.8.2 from PyPI, and your
`main` (`enricher/src/just_dna_enricher/assertions.py`, the `reference is None` branch).

### What happened

Upstream message text names CLI commands as remedies (*"Run `just-dna-compiler close <spec-dir>`"*). Our agents
call MCP tools, not your CLI, so we now map each quoted command to the tool that does the same job here.
`cli_map.py` holds that map. A test holds it to the commands your two typer apps register, in both directions.

The map turned up a quoted command that neither app registers. The clinical-assertion pass, skipping with no
snapshot, says *"Provision one with `just-dna-enricher clinvar pull`."* On 0.8.2, `just-dna-enricher clinvar` has
`build`, `publish` and `citations`, and there is no `pull`. The command that fetches the published snapshot is
`cache pull` (with `--only` naming the lane). An author who copies the line gets *"No such command"*. On 0.7.3 the
CLI's own skip line repeated it (`cli.py`, *"provision one with `clinvar pull`"*). That one is gone on 0.8.2, and
the `assertions.py` one is still there on 0.8.2 and on `main`.

To check for others, I walked every `just-dna-enricher …` / `just-dna-compiler …` string in the 0.8.2 sources of all
three packages against both apps' command trees. A quote counted as bad only where a word under a group was not a
registered subcommand. `clinvar pull` was the only real hit. The other three were version and commit labels
(`just-dna-enricher unknown`, `just-dna-compiler unknown`, `just-dna-enricher write`), not commands.

### The ask, and its cost

1. **The wording (patch):** name the command that exists, `just-dna-enricher cache pull --only <the ClinVar lane>`,
   or `clinvar build` for an author building their own.
2. **Optional, a guard (patch):** the same walk as a test in your tree. Every backticked `just-dna-* …` in
   `src/` must resolve to a registered command, or be on a short list of labels. It would have caught this when
   `pull` moved under `cache`. Our version is about 40 lines over `typer.main.get_command(app)`. Note that typer
   ships its own click (`typer._click`), so an `isinstance(cmd, click.Group)` test sees no groups; `hasattr(cmd,
   "commands")` works.
3. **Weigh, likely a minor:** a structured remedy key. Today our map reads your message text to find which command
   it means, so a reworded message silently stops mapping. That is F125's history: the drafter refusal was
   reworded in 0.7.1 and our appended repair stopped firing. A field on `hints.Finding` (and on whatever carries a
   validate or compile warning), e.g. `remedy: str | None` holding the registered command path such as
   `"close"` or `"cache pull"`, would let a consumer map by key and leave your prose free to change. The guard in
   ask 2 could then check the keys rather than scrape strings. A reason against it, which we would accept: most
   remedies are in `logger.warning` text that never becomes a `Finding`, so the field would cover only part of
   them, and a partial key may be worse than an honest text match. If so, ask 2 alone keeps the quotes true.

Meanwhile on our side: `on_this_surface` maps every registered command and abstains from `clinvar pull` with
nothing, so an agent reading this skip on our surface gets no tool pointer, which is better than a wrong one.
