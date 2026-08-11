# The consumer-suggestion triage loop

How to run [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md) as a conversation rather than an inbox:
a watcher notices when a consumer has finished writing, an agent triages what is new, and every item
gets a **maintainer reply written back into the document itself**. The document is the transcript, and
it is also the state — there is no queue, no database and no external ledger.

**A generalized, self-contained copy of this loop is published as a gist** —
<https://gist.github.com/winternewt/54b94bda01812be937b892146d1bb254> — with the three scripts
parameterized (`INBOX`/`HISTORY`/`PREFIX`) and every repo-specific reference stripped. If you change the
*pattern* here (the algorithm, a script's contract, a gotcha), update it there too; if you change
something only true of this repo, do not. The gist is one-way — it never reads back from here.

**The live document holds only what is unanswered.** An item moves to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) once its reply is written, which is
the same split as [ROADMAP.md](ROADMAP.md) / [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) and exists for
the same reason: an inbox only grows, and the eleven unanswered entries this loop was built for were
invisible inside 6,000 words of answered ones. So an empty live file means nothing is owed — which is
a property worth having and is destroyed the moment answered items are left in place.

This exists because the notes arrive faster than anyone re-reads them. Eleven of the seventeen entries
in that file had no reply of any kind when the loop was built, and six of those are not recorded
anywhere else either, so the only way to find out whether an item had been considered was to read
6,000 words and guess.

---

## 1. Setup

Three scripts, all in `.claude/`, none packaged:

| | |
|---|---|
| `.claude/watch-suggestions.sh` | debounced watcher: one line of stdout when the file stops changing |
| `.claude/triage-state.sh` | the ledger: which sections are new, revised, or already answered. Takes a path, so it reads the history file too; `--next` prints the next unclaimed `Sn` |
| `.claude/triage-archive.sh` | moves answered sections into the history file and **verifies** each fingerprint survived the move |

Arm the watcher with the `Monitor` tool, which turns each stdout line into a notification that
re-invokes the agent:

```
Monitor({
  command: '/data/sources/just-dna-format/.claude/watch-suggestions.sh',
  description: 'CONSUMER_SUGGESTIONS.md settling',
  persistent: true,
})
```

`persistent: true` keeps it alive for the session; `TaskStop` cancels it. It reacts only while the
session is open and the REPL is idle. Nothing needs installing — `inotify-tools`, `entr`, `fswatch` and
python `watchdog` are all absent from this machine, and `stat` polling is enough at this cadence.

**Hooks cannot do this job.** Claude Code hooks fire on the agent's own lifecycle (`PreToolUse`,
`PostToolUse`, `SessionStart`, `Stop`); a consumer editing a file triggers none of them. The trigger has
to be a process.

### The cooldown is sized for an agent author

Consumers write these notes through an agent, so the shape is a burst — five edits in a minute — with
gaps wherever the agent stops to read or probe something. A 60-second timer fires in the middle of such
a run and triages half a note. `COOLDOWN` defaults to **150s**, `POLL` to 10s, so an event lands 150–160
seconds after the last write. Consecutive saves inside the cooldown collapse into **one** event, because
each mtime bump restarts the timer.

Raise it if a consumer's runs are slower. The only cost of waiting is latency, and the cost of firing
early is a reply to a half-written item.

### First run

The watcher seeds itself from the current mtime with the dirty flag clear, so **it never fires for a
change that predates it**. Run the ledger once at startup to pick up the standing backlog:

```
.claude/triage-state.sh            # every section and its verdict
.claude/triage-state.sh --pending  # just the ones needing work
```

---

## 2. How state is derived

**The document is the ledger.** A triaged section carries a marker inside its reply, holding a
fingerprint of the consumer's own text:

```
**Status — accepted, filed as RM45.** … <!-- triaged: 0.5.4 · sha 43031f8f63b3 -->
```

The fingerprint covers the section body with **every `**Status` paragraph and every marker removed**, so
it describes what the consumer wrote and never what we replied. Lines are right-stripped and blank runs
collapsed, so trailing whitespace and reflowing do not count as a change. Four verdicts follow:

| verdict | meaning | action |
|---|---|---|
| `new` | no reply, no marker | triage it |
| `revised` | marker present, fingerprint moved | the consumer edited an answered item — re-triage |
| `unmarked-reply` | answered before the ledger existed | `--backfill` stamps the marker |
| `current` | marker matches | nothing to do |

### Why not git

One fatal reason, and one that expired. A consumer may well commit their own addition, at which point
`git diff HEAD` is empty and the loop sees nothing at all — that one is unchanged and is on its own
enough. The original second reason was that the loop *must not commit*, so a `HEAD` baseline would never
advance; the §5 permit retired that premise on 2026-08-11, and it is recorded here rather than quietly
deleted because a design defended by two reasons is worth re-checking when one of them goes. The design
survives it: the surviving reason is fatal by itself, and the ledger's properties below were never
consequences of the commit rule. `git diff` and `git log -p` stay in the loop for *reading what changed*,
as context. Correctness never depends on them.

The in-document ledger has properties no side-car state has: it works on an uncommitted tree, survives
anyone's commits, travels with the repo, is legible to a human scanning for the backlog, and cannot
drift out of sync with the replies it describes.

### Self-firing is not a loop

Writing a reply bumps the mtime, so the watcher fires again. That run finds nothing pending — the
fingerprint excludes the reply — and no-ops. Expect the second notification; it is the mechanism
working.

---

## 3. The algorithm

### Step 0 — establish what already shipped

**Do this before reproducing, and certainly before designing.** `new` in the ledger means *no reply in
the document*, never *no work done*. On the first full run, **two of eleven** items were already fixed —
S1 by 0.4.1 plus RM17, S2 by a block in `authoring_reference()` whose code comment **names S2** — and a
third's preferred option had shipped in 0.5.2 from a different report (S14). Answering those as though
they were open would have designed a feature that existed.

Cheap and mechanical: grep the item's symbols in the source, then `docs/CHANGELOG.md`,
`ROADMAP_HISTORY.md` and `RM_TOC.md` for its subject; `git log -S "<a phrase from the fix>"` finds when a
guard landed. For S1 this collapsed a feature request into one missing error message.

### Step 0b — reproduce before classifying

Compare the claim against the code, not only against the docs, because the docs are often the thing
that is wrong. This step is the only thing separating a real defect from bucket **(b)**, and it cuts
both ways in this very file: S6's chrY half **did not reproduce** against a real `SRY` row, while S13's
warning-string marker reproduced end to end. Scope the probe to the table you actually looked at — an
unscoped negative finding becomes a permanent false constraint.

**Probe the behaviour, not only the sentence — the probe is where the adjacent defect turns up.** S16
asked whether unknown files in a spec directory are tolerated; building the probe meant putting several
files there, one of which was `varaints.csv`, and that revealed a mistyped table name being dropped from
a green compile — a defect nobody had reported. S7's answer needed three compiles *and* a second probe of
`merge_sources_csv` to establish that a rebuild cannot move `fetched_at` unless the sidecar is deleted,
which is the fact the whole item turns on.

**A bucket-(b) verdict is not the cheap outcome.** Three of the first eleven were non-issues and each
cost the most probing, because "nothing is wrong here" has to be *shown*, and a reply that cannot show it
is worthless.

### Step 1 — charter legality, first-hand

**Read [CONSTITUTION.md](CONSTITUTION.md) yourself.** Never delegate this to a subagent: a summary of a
charter drops the qualifier the decision turned on, and this step decides whether a repair is legal at
all. It is the one part of the loop that cannot be automated away.

**Legality sizes the release; severity only orders the queue inside it.** This is the correction most
worth carrying:

| change | release | why |
|---|---|---|
| new optional column, table, or manifest field | **minor** | additive; an unset optional column is omitted from `content_signature`. A manifest field was never in `artifact.digest` at all, so it is cheaper still |
| pure legibility — a warning, a count, an error *message*, a doc | **patch** | moves no authored identity. A better diagnosis on a path that already failed changes no verdict |
| a **new** flag, parameter or alias beside the old one | **minor** | additive; P3 keeps a superseded name as a working alias |
| removal, promotion to required, retyping — **including a rename** | **major** | breaks a reader or invalidates published data. A rename is a removal plus an addition, so the addition being legal does not make the rename legal (S14) |

So a severe finding whose fix is a new optional field is still minor (S13/RM44), and a trivial one whose
fix is a retype is still major. Severity decides what gets done first, never what version it lands in.
"It moves `artifact.digest`" is **not** on its own a reason to defer: P4 scopes byte-reproducibility to a
fixed `compiler_version`, and the authored identity does not move.

**Where the amendment does *not* reach.** The 2026-08-11 amendment is about columns and tables. Do not
stretch it to a published function signature or CLI flag — S14's rename stays major for that reason,
while *adding* a differently-named alias would have been minor. And a change to a dataclass a consumer
reads (`Finding.row`) is best made additively for the same reason a column is: S18's fix adds `line`
rather than redefining `row`, because a consumer already compensating for the old meaning would break
**silently**.

Round-trip is the trap. P7 can make the obvious repair illegal outright — RM43's option 1 does not merely
move a digest, it moves `content_signature`, because `reverse_module` re-emits a filled coordinate as an
authored one. **A repair that fails P7 routes to (d), not (a).**

### Step 2 — route

| | verdict | lands in | must contain |
|---|---|---|---|
| **a** | real, repairable, legal | `ROADMAP.md` as `## RMn` **plus an [RM_TOC.md](RM_TOC.md) entry** | `**Severity** … · **Status** open — 0.x · **Owner** … · **Motivating case** (Sn in CONSUMER_SUGGESTIONS_HISTORY.md)` |
| **b** | non-issue | the reply only | **what was probed and did not reproduce.** Never a bare "works as intended" |
| **c** | documentation defect | the doc, fixed in the same pass | the reply naming the file changed |
| **d** | real, no acceptable repair | `ROADMAP.md`, **`Status` open only** | the paragraph saying *why each candidate repair is wrong* |

**An item filed as a documentation gap usually has a code half — look for it.** All three entries a
consumer grouped under "Documentation gaps" (S15–S17) ended up with code: a lock, a near-miss guard, and a
specific error message. The reporter is describing where *they* got stuck, which is a fact about the docs;
what stuck them is often a surface that could have told them.

**A wrong consumer conclusion is a place to look for our own defect.** S7's author read a moved
`artifact.digest` as a moved content identity — and SCHEMAS.md's hash table was calling the digest "the
version's immutable **content** identity", against the charter. Bucket **(b)** on the report with bucket
**(c)** underneath it is a common pairing, and the (c) half is the one that stops the next person filing
the same item.

Bucket **(d)** is the one that earns its keep, and the one an unattended agent does worst. It is the
`fix it` / `surface it` line from [CLAUDE.md](../CLAUDE.md): surface anything whose obvious repair is
itself a design decision, and say why each candidate fails. RM33's paragraph is the model, because one
of its two obvious fixes is charter-illegal.

If **(a)** ships in the same pass rather than being filed: code plus a test, a
[CHANGELOG.md](CHANGELOG.md) entry, and the item moves to
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) with its rationale. `RM_TOC.md` is updated either way — it is
the single complete index, and an item missing from it is how `RM33` became unfindable.

### Step 3 — write the reply

`**Status —**` is the existing house idiom in this file; do not invent a second one. It goes **first in
the section, immediately after the heading**, and says four things: the verdict, where it landed (an
`RMn` link, a doc, or a shipped version), what was actually reproduced, and what the consumer should do
now.

```markdown
## S14 — `resolve_with_ensembl=False` reads as "skip Ensembl" …

**Status — accepted; suggestion (1) shipped in compiler 0.5.4.** Reproduced: a spec with a
committed `resolution.csv` compiles green with every coordinate null under `--no-resolve`.
The warning now names the unread table and its row count. Suggestion (2) is filed as
[RM45](ROADMAP.md#rm45--…) — splitting the flag is a CLI break we want to make once.
<!-- triaged: 0.5.4 · sha 43031f8f63b3 -->
```

**Append, never edit.** The consumer's prose is evidence and stays byte-for-byte; the 0.5.2 block says
so in the file itself — *"the notes below are left as written — they are the report, not the
resolution."* Same rule as drafting: it appends, it never mutates.

One reply may cover several sections, as the 0.5.2 block does for S3–S6. The ledger understands that
shape and marks each covered section individually, since one paragraph cannot carry four fingerprints.

### Step 4 — move the answered item to the history file

```
.claude/triage-archive.sh S14 S15 [--dry-run]
```

It cuts each section — heading, consumer prose, reply and marker — out of
[CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md), appends it to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) under its group heading, and then
**verifies the move**: every section's fingerprint is compared before and after, and the write is
rejected if one changed. Do this by hand only if the tool cannot (it prints what it would move under
`--dry-run`).

- **Byte-for-byte, and checked rather than intended.** The one property that matters is that the
  consumer's prose is unchanged, and it is easy to break by reflowing a line while pasting. A changed
  sha means the prose was touched — that is why the tool refuses rather than reports.
- **Add the contents line, and keep it to one line.** The tool does not generate it: naming what an item
  was and how it ended is editorial. The format is `- **Sn** <what it was> — <status> (<RM if any>)`,
  **under 80 characters**, because it is a *contents list* and not a second copy of the reply — the
  detail lives in the section's `**Status —**` paragraph, the one place it cannot drift out of step with
  the answer. (The first version of this index was a four-column table with a paragraph per row; it
  duplicated every reply and was already the thing most likely to rot.) The list still matters for the
  reason `RM_TOC.md` does — an item missing from it is how `RM33` became unfindable, and inbound links
  elsewhere in the repo are file-level (`S5 in CONSUMER_SUGGESTIONS.md`), so a reader following one
  lands on the live file and needs a pointer onward.
- **A group's dateline is repeated in both files when its items split** — while S8 was still open, the
  "adopting 0.5.2" dateline sat in each. Repeating four lines of context beats moving a preamble away
  from an item it still introduces.
- **A block reply travels with the items it answers.** The 0.5.2 block reply sits in the just-dna-lite
  preamble and answers S3–S6, so that whole group moved together.
- **Archive in one pass at the end if you are working a batch.** Sections are appended in the order
  given, so a group whose items are archived in two batches ends up with its heading twice; the fix is
  mechanical (move the later sections under the first heading) but avoidable. Check `grep -n '^# '` on
  the history file when you are done, and give a section its own heading if it was appended under one it
  does not belong to — S18 arrived after S17 and would otherwise read as a "documentation gap".

### Step 5 — hygiene

- **Serial, one item at a time.** `RMn` is a shared counter — **RM47 is the highest, so the next is
  RM48** — and two concurrent triages both claim it. Do not keep this number in your head across a long
  pass: read it off [RM_TOC.md](RM_TOC.md), which indexes every item in both roadmap files.
- **Commit as you go, one commit per item** — see the grant in §5 for what that covers and where it
  stops. Stage explicit paths; never `git add -A`. (This bullet read *do not commit* until 2026-08-11,
  which was the global default before the loop had a permit of its own.)
- **Say what was skipped.** If an item is left untriaged, leave it `new` rather than writing a
  placeholder reply. An empty verdict is honest; a hedged one is not.
- **Run the whole suite after each fix, and `ruff check` before you finish.** Six code fixes in one pass
  touched all three packages; the suite went 1382 → 1410 and stayed green throughout, which is the only
  reason a batch that size is safe to leave in the tree.
- **A new item can arrive mid-pass.** S18 was filed while this pass was running and the watcher picked it
  up on its next fire. Take it in the same pass if the context is warm, or leave it `new` — but do not
  let it silently miss the CHANGELOG entry the rest of the batch gets.
- **Write the CHANGELOG entry for the batch, not per item.** One dated heading covering the pass, with
  the two-of-eleven-already-shipped fact in it: a future reader needs to know the loop's first run found
  answered work sitting unanswered, or they will assume `new` meant untouched.

---

## 4. Thresholds — when to stop the loop and call the user

The loop's output is roadmap items and patch-level fixes, and it will produce both indefinitely without
ever deciding to build or release anything. Triage answers a consumer; it does not schedule the work or
cut the version. Those two are the user's call, so the loop has to **stop and ask** rather than keep
accumulating. Both thresholds are counted off the tree, never remembered:

```
grep -c 'Status\*\* open — \*\*0\.6\*\*' docs/ROADMAP.md    # 0.6-targeted items
grep -h '^version' */pyproject.toml                          # versus the top CHANGELOG heading
```

**Ten or more sizeable open 0.6 items → triage the backlog, then block.** Re-read the set first: an item
that duplicates another, or that never had a reproduced case under it, is not grounded and should be
merged or demoted rather than counted. If they all survive that pass — each with a motivating case and a
reproduction — the backlog is real, and a real backlog of that size is a release-planning decision.
Block the loop with an `AskUserQuestion` (it shows red in herdr) rather than filing an eleventh.

**Around ten accumulated patch-level fixes → publish time, call the user.** The signal that they have
accumulated is the CHANGELOG carrying a version the `pyproject.toml` files do not, which is exactly the
state the tree is in as this is written. Cutting and publishing is the user's domain — never bump a
version, tag, or publish; ask.

**Fewer is fine when something is critical** — a wrong published number, a false claim in a printed
contract, anything a consumer could act on and be harmed by. That is a judgement call and it is the
agent's to make; do not sit on one because a counter reads four.

**The numbers will drift, and they are a trigger rather than a law.** This is an active testing phase, so
they were picked to be roughly right and are expected to move. Update them here when they do — and note
that the count is deliberately of *sizeable* items, since a batch of one-line legibility fixes is not the
thing that needs a planning decision.

---

## 5. What the loop agent may do unattended

A standing grant, given 2026-08-11, that **overrides the global "only commit when asked" default for
this loop and nothing else.** It exists because a batch that sits uncommitted for a whole pass is one
`/clear` away from being unattributable, and because the §4 thresholds are worthless if the agent cannot
act on them.

**Granted.** Commit as you go — one commit per item, the loop's existing serial rule, with the `Sn`/`RMn`
in the message. Bump a version, tag it, and clean and build dists when a §4 threshold fires; bumping is
inside the grant by implication, since a `0.5.4` tag cannot exist while `pyproject.toml` reads `0.5.3`.
Bump and build **only the packages whose code moved** — a partial cut is normal here, and `schema` has
sat at `0.5.0` across two compiler releases. When `schema` is next cut it takes the **aligned** number
rather than the next one in its own sequence (decided 2026-08-11: one version across the workspace beats
a dense per-package count, so a `0.5.4` compiler names a `0.5.4` schema).

**`uv sync` and relock before tagging — the common gotcha, and it is silent.** `uv.lock` is tracked and
records each workspace member's own version, so a bump that stops at `pyproject.toml` leaves the lock
naming the release you just left. Tag that and the tag captures a tree that cannot reproduce itself,
while `uv run <cmd>` keeps resolving through a stale wrapper. The order is **bump → `uv sync` → commit
the lockfile with the bump → tag**, so the tag includes the relock rather than trailing it. Check before
tagging, never after:

```
grep -A1 'name = "just-dna-\(format\|compiler\|enricher\)"' uv.lock   # versus */pyproject.toml
git status --short uv.lock                                            # must be clean at tag time
```

**Not granted, and not by omission.** `git push`, `uv publish`, tag pushes, releases — everything
outward-facing stays the user's. Building a dist is not publishing one; the artifact sits in `dist/`
until a human sends it. **Wipe `dist/` before building**, because `uv publish` uploads everything it
finds there and a stale wheel left by this loop becomes the user's footgun at *their* publish step.

**No history rewriting: linear commits only.** No amend, no rebase, no reset, no merge commits, no
force-push, and no `git stash` in any form — that one has already swept an entire session's uncommitted
work here. Stage explicit paths; never `git add -A`, which is how a `.env` swap file with live tokens
once got committed.

**If you corner yourself, confess with an `AskUserQuestion`.** This is the other half of the rewriting
ban rather than a separate rule: amend and reset are exactly the tools you would reach for to make a bad
commit disappear, so a mistake stays visible by construction. A commit that should not have been made, a
tag on the wrong commit, a build from a dirty tree — say so, say what state the tree is actually in, and
offer the fix-forward options. A wrong commit followed by a correcting commit is a legible history; a
rewritten one is a lie the user cannot audit.

---

## 6. Gotchas found while building this

Each of these was a bug in the loop, not a hypothetical:

- **A reply can live outside the section it answers.** The 0.5.2 block sits under an `# ` heading and
  answers S3, S4 and S6 by name, so a naive presence test reads four answered sections as new.
  `block_replies()` reads that convention instead of forcing a new one.
- **The marker must not be hashed.** Marking a block-replied section puts a standalone comment in its
  body; when the fingerprint covered it, the section read `revised` from the instant it was marked. The
  marker is stripped wherever it appears, not only inside a reply.
- **A reply ends at its marker, not at the first blank line** — found on the loop's own first run.
  `consumer_text()` skipped the `**Status` *paragraph*, so a reply of several paragraphs (the normal
  size for one that says what was probed, where it landed, and why a candidate repair was rejected)
  leaked paragraphs two onward into the fingerprint, and writing a reply reported the section
  `revised` immediately. That is the same self-firing failure the marker exclusion exists to stop,
  arriving by a different route. `reply_end()` now runs to the marker; with no marker ahead it falls
  back to the single paragraph, which is what keeps `unmarked-reply` sections from all hashing to the
  same empty text. The fix is checkable rather than plausible: S1 and S2 hash back to the exact
  fingerprints they carried before their replies were written.
- **Splitting a wrapped paragraph is a substantive change**, and correctly reports as `revised`. Only
  trailing whitespace and blank-run length are normalized away.
- **`S9` appears twice as a heading** — `## S9` at the 0.5-era notes and `### S9` as a follow-up nested
  inside S13's section. The ledger keys on top-level `## Sn` and folds `###` into the parent, so that
  follow-up currently counts toward S13's fingerprint. Harmless, but it is why the unit is the
  top-level section.
- **The event line needs a cap.** With a 17-item backlog the notification listed every one; it now shows
  eight and `+N more`.

---

## 7. State, and what the first full run found

**As of 2026-08-11 the backlog is empty.** S1–S18 all carry a reply and all sit in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) with a contents line each. The next
consumer item is **S19** and the next roadmap item is **RM47** — but read both off the tools rather than
off this sentence, which is exactly the kind that goes stale:

```
.claude/triage-state.sh                                    # the live inbox — empty means nothing owed
.claude/triage-state.sh docs/CONSUMER_SUGGESTIONS_HISTORY.md   # every answered item, all `current`
.claude/triage-state.sh --next                             # the next unclaimed Sn, over BOTH files
```

**An emptied inbox breaks id numbering unless the next id is pinned, and this is the one hazard the
split introduced.** Once answered items move out, the live file's highest visible id is not the corpus's
highest — with the inbox empty it shows none at all, so the obvious next id is `S1`, which already
exists and already has a reply. Two defences, and keep both: the live file states the next id in a
heading, and `--next` computes it from both files so it cannot drift from them. **Ids are never reused**,
not even for an item answered as a non-issue — the reply is part of the record, and a recycled id would
collide with it. Same rule as `RMn`, and the same failure mode as reading the RM counter from memory
during a long pass.

The pass produced six code fixes, two roadmap items (**RM45**, **RM46**), four documentation fixes and
three reasoned non-issues; the suite went 1382 → 1410 tests and every reference example still recompiles
byte-identically. [CHANGELOG.md](CHANGELOG.md)'s 0.5.4 entry is the per-item record. What is worth
carrying into the next run is above, in the algorithm — Step 0 exists because of this run — plus these:

- **The backlog was not what it looked like.** Of eleven `new` items, two were already fixed, one had its
  preferred option shipped from another report, and three were non-issues. Half of an unanswered inbox
  can be answered without writing code, and none of that is discoverable without reading the source
  first. Budget the pass for *establishing* rather than for building.
- **Six items were reported by consumers who had already fixed their half**, and each of those fixes is
  evidence about the right shape: S15's `ServiceGate`, S1's `strip_registry_owned_keys` (which we had
  upstreamed a release earlier), S16's reliance on sibling files, S12's search-instead-of-recall. Read
  what they built before deciding what to build; twice here the consumer's own argument against their
  first option was the reason the item was filed rather than patched (S10's per-article terms, S8's trust
  caveat).
- **The reply is the deliverable even when nothing is filed and nothing is fixed.** A non-issue reply
  that cannot show what was probed is worthless, and a hedged one is worse than silence.
- **Answering an item is not finishing it.** RM43, RM44, RM45 and RM46 are open with S9, S13, S8 and S10
  as their motivating cases. `RM_TOC.md` is the index for that half — this file's history is the record
  of what a consumer was *told*.
