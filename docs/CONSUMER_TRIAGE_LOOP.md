# The consumer-suggestion triage loop

How to run [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md) as a conversation rather than an inbox:
a watcher notices when a consumer has finished writing, an agent triages what is new, and every item
gets a **maintainer reply written back into the document itself**. The document is the transcript, and
it is also the state — there is no queue, no database and no external ledger.

**A generalized, self-contained copy of this loop is published as a gist** —
<https://gist.github.com/winternewt/54b94bda01812be937b892146d1bb254> — with the three scripts
parameterized (`INBOX`/`HISTORY`/`PREFIX`) and every repo-specific reference stripped. If you change the
*pattern* here (the algorithm, a script's contract, a gotcha), update it there too; if you change
something only true of this repo, do not.

### Sync in from the gist at the start of a pass, and adopt what has come back

**The gist is where fixes from other repositories arrive, so it is read as well as written.** Other
trees run this loop, and a defect in the *pattern* is usually met there first — the `**Status`-preamble
collision in §6 was found while adopting the loop into a second repository, not here. That makes the
published copy an inbound channel, and a fix sitting in it unadopted is the same failure this whole
document is about: something answered somewhere nobody looks. What stays one-way is the **content** —
the gist never reads this repo's items, only its machinery.

**Check the digest first, and pull the files only when it has moved.** Fetching both scripts and
diffing them every pass is almost always work for nothing: the gist changes rarely, and the diff is
noisy enough (below) that reading one is not free either. The gist's own revision id is a digest of
the whole thing and is public, so the check costs a single unauthenticated request:

```bash
GIST=54b94bda01812be937b892146d1bb254
curl -sf "https://api.github.com/gists/$GIST" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["history"][0]["version"])'
```

**Adopted through gist revision `bd793a8ce98b729f00b97733d38ed82d4d127a48`**, published 2026-08-18 —
and that one is ours, an outward push rather than an adoption, so it is in sync by construction. It
supersedes `ab7e2a89c48d…` (committed 2026-08-16), which was the baseline the digest check was first
pinned to. Same sha back means nothing has arrived and the sync-in is finished for that pass; a
different one means pull the files and read the diff. **Update this line, with its date, whenever an
adoption *or* a push lands** — it is the baseline, and a stale one re-diffs work already taken, which
after a push means re-reading your own writing as though a stranger had sent it.

`history[0]` is the newest entry, checked and not recalled — its `committed_at` equals the gist's
`updated_at`. Getting that orientation backwards is the failure worth guarding, because it does not
announce itself: the check would read `unchanged` forever and the inbound channel would look healthy
while nothing came through it. If `api.github.com` is ever unreachable, the fallback is a conditional
GET against the raw URLs carrying a stored `ETag`, where a `304` is the same "unchanged" answer. Build
one or the other, never both.

When the digest has moved, the files are at `<gist>/raw/<name>`, and the local names differ for the
watcher only (`watch-inbox.sh` → `.claude/watch-suggestions.sh`):

```bash
G=https://gist.githubusercontent.com/winternewt/54b94bda01812be937b892146d1bb254/raw
for f in triage-state.py triage-archive.py; do curl -sfL "$G/$f" -o "/tmp/gist-$f"; done
diff -u /tmp/gist-triage-state.py .claude/triage-state.py     # noisy: most of it is parameterization
```

**Read the diff for logic, not for prose.** Nearly every line differs because the gist is
parameterized and names no repo document, so a raw diff buries the two or three lines that matter.
Compare the code with docstrings and comments stripped, and adopt only what is a *behaviour* change:
in the 2026-08-17 sync those were `RULE_RE` (a trailing horizontal rule was being hashed as if the
consumer had written it) and the archiver's closing line, which still said "add each one's row to the
index table" — wording §4 retired when the table became a contents list.

**Auto-adopt is the default, and it has exactly one gate: does adopting move a fingerprint?** A fix to
the machinery is presumed wanted, since it was found by someone running the same loop and there is no
local reason to differ. But a change to `fingerprint()` re-scores every marker already stamped, and
those sections then read `revised` — our own adoption impersonating a consumer revision, which is the
one signal the ledger exists to carry. So run the ledger over **both** documents immediately after,
and if nothing moved you are done.

**If something moved, prove the cause before restamping, and the proof is cheap.** Do not reach for
git archaeology: if the ledger read all-`current` immediately *before* the adoption, then the old
function still matched every recorded marker, so the whole delta is the function and no prose changed.
That check is one command and it is stronger than a diff. Restamp to the new values and say so in the
commit. `--backfill` will not do it — it only touches `unmarked-reply`, deliberately, because silently
restamping a `revised` section is how a genuine re-triage signal gets erased. Adopting `RULE_RE` moved
four (S2, S6, S7, S12 — the four reports ending in a `---`) and they were restamped on that proof.

**What must not be adopted**, since the gist is the generic copy and this tree is not: the
`INBOX`/`HISTORY`/`PREFIX` parameterization, the `FEEDBACK.md` defaults, and any pointer to
`TRIAGE_LOOP.md`, which is the gist's name for this file. Adopting those silently repoints the tools at
documents that do not exist here.

**Push the other way too, and check it in the same pass** — the sync is bidirectional even though each
direction is a separate act. **The standing debt was discharged on 2026-08-18**: the branch-pause in
`watch-suggestions.sh` (§1) and the digest check above both reached the gist in revision `bd793a8c…`,
genericized, along with the correction to §2's "why not git" that the branch-pause forced — the
published copy still called *the loop must not commit* a fatal reason for the design, which stopped
being true here when §5's permit was granted, and a watcher that pauses because the loop commits cannot
sit in a document saying it does not. Nothing is owed outward as of that revision. Updating the gist is
a publish and stays the user's to authorize; it was authorized for that push and is not a standing
permission.

**The live document holds only what is unanswered.** An item moves to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) once its reply is written, which is
the same split as [ROADMAP.md](ROADMAP.md) / [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) and exists for
the same reason: an inbox only grows, and the eleven unanswered entries this loop was built for were
invisible inside 6,000 words of answered ones. So an empty live file means nothing is owed — which is
a property worth having and is destroyed the moment answered items are left in place.

**The history file has itself been split once, and the loop is unaffected.** On 2026-08-17 the items
the 0.5 line answered — S1–S24, S27 and S28 — moved to
[history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md](history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md),
byte-for-byte and with every fingerprint intact. `triage-archive.py` still archives into
`CONSUMER_SUGGESTIONS_HISTORY.md`, which is the file it should keep writing to; `triage-state.py`
globs for the history files rather than naming them, so `--next` counts ids across every half. The
contents list stays whole in the live history file — splitting an index is how an item stops being
findable, and that is what `RM_TOC.md` exists to remember.

This exists because the notes arrive faster than anyone re-reads them. Eleven of the seventeen entries
in that file had no reply of any kind when the loop was built, and six of those are not recorded
anywhere else either, so the only way to find out whether an item had been considered was to read
6,000 words and guess.

---

## 1. Setup

Three scripts, all in `.claude/`, none packaged:

| | |
|---|---|
| `.claude/watch-suggestions.sh` | debounced watcher: one line of stdout when the file stops changing. The only one that is really bash |
| `.claude/triage-state.py` | the ledger: which sections are new, revised, or already answered. Takes a path, so it reads the history file too; `--next` prints the next unclaimed `Sn` |
| `.claude/triage-archive.py` | moves answered sections into the history file and **verifies** each fingerprint survived the move |

**Run the two Python ones, never `bash` them** — `./.claude/triage-state.py` or
`python3 .claude/triage-state.py`. They carried a `.sh` extension until 2026-08-16 and the mismatch had
a cost; §6 has it.

Arm the watcher with the `Monitor` tool, which turns each stdout line into a notification that
re-invokes the agent:

```
Monitor({
  command: '/data/sources/just-dna-format/.claude/watch-suggestions.sh',
  description: 'CONSUMER_SUGGESTIONS.md settling',
  persistent: true,
})
```

**It watches only while the tree is on `main`.** The loop commits as it goes (§5), and a branch — or a
detached HEAD — is the user's own work, which is the one thing that permit does not cover: triaging into
it would put unattended commits on top of whatever they are mid-way through. Off `main` the watcher idles
at `BRANCH_PAUSE` (900s) instead of `POLL`, emits one line saying which branch it is on, and stays quiet
until the branch changes back, when it emits one more. It does not touch its `last` mtime while paused,
so a consumer's edit written during the pause is still picked up on the way back rather than lost —
verified across a `main → branch → main` switch, with the edit made while paused arriving in the resume
event. `BRANCH=<name>` overrides the branch it considers home.

`persistent: true` keeps it alive for the session; `TaskStop` cancels it. It reacts only while the
session is open and the REPL is idle. **Editing the script does not reach a running monitor** — bash
reads a script incrementally — so `TaskStop` and re-arm after changing it. Nothing needs installing — `inotify-tools`, `entr`, `fswatch` and
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
.claude/triage-state.py            # every section and its verdict
.claude/triage-state.py --pending  # just the ones needing work
```

**Point it at the history file too, every time — an empty inbox is not an all-clear.** That run is the
lint described in §6, and it is the only thing standing between a mis-archive and a permanently lost
item: a well-formed archived section reads `current`, so anything else means a marker went in wrong or
did not survive the move. On 2026-08-17 the inbox was empty and this turned up two, S35 `revised` and
S36 `unmarked-reply`, both from the pass that had archived them.

```
.claude/triage-state.py docs/CONSUMER_SUGGESTIONS_HISTORY.md   # every row must read `current`
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
[RM45](ROADMAP_HISTORY.md#rm45--…) — splitting the flag is a CLI break we want to make once.
<!-- triaged: 0.5.4 · sha 43031f8f63b3 -->
```

**Append, never edit.** The consumer's prose is evidence and stays byte-for-byte; the 0.5.2 block says
so in the file itself — *"the notes below are left as written — they are the report, not the
resolution."* Same rule as drafting: it appends, it never mutates.

One reply may cover several sections, as the 0.5.2 block does for S3–S6. The ledger understands that
shape and marks each covered section individually, since one paragraph cannot carry four fingerprints.

### Step 4 — move the answered item to the history file

```
.claude/triage-archive.py S14 S15 [--dry-run]
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
  **An item filed under no group heading needs one written by hand**, and the tool now says so instead
  of guessing: it prints `No group heading travelled with Sn` and you add a `# ` line naming who
  reported it and when. That notice exists because the silent version of this went wrong twice — see the
  title-is-not-a-group gotcha in §6.

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

## 4. Thresholds — when to call the user

The loop's output is roadmap items and patch-level fixes, and it will produce both indefinitely without
ever deciding to build or release anything. Triage answers a consumer; it does not schedule the work or
cut the version. Those two are the user's call, so the loop has to **ask** rather than keep accumulating
silently. Note which way each threshold points — two of them say *start something* and only the last
says *stop*, so do not collapse them into one "the loop halts" rule. All are counted off the tree, never
remembered:

```
grep -c 'Status\*\* open — \*\*0\.6\*\*' docs/ROADMAP.md    # 0.6-targeted items
grep -h '^version' */pyproject.toml                          # versus the top CHANGELOG heading
```

**Ten or more sizeable open 0.6 items → 0.6 development should START. This is the dev-start trigger, and
it is *not* "0.6 scope is closing".** Read it the wrong way — as a scope freeze, a ceiling, a
stop-filing rule — and it inverts: it would silence the loop exactly when the release it feeds is ready
to begin. A minor keeps taking additive items right up until it is cut, so filing continues after the
trigger fires; what changes is that enough grounded work has accumulated to be worth *building*, and
scheduling a build is the user's call. Re-read the set before calling it: an item that duplicates
another, or that never had a reproduced case under it, is not grounded and should be merged or demoted
rather than counted. If they all survive that pass — each with a motivating case and a reproduction —
raise it with an `AskUserQuestion` (it shows red in herdr): the question is *shall 0.6 development
start*, never *shall we stop filing*. Ask once per pass, not once per item over the line.

**Twenty sizeable open 0.6 items is the ceiling — there, stop filing and block.** A backlog that size
means the dev-start trigger fired and went unanswered for long enough that the queue is no longer being
managed by anyone, and a twenty-first item buys nothing: nobody reads that far, and an unread item is
indistinguishable from an unfiled one. Say what you would have filed, in the reply to the consumer, and
block rather than adding to a list that has stopped being a plan.

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
- **A document's own title is not a group heading, and `triage-archive.py` thought it was.** It took the
  *last* `# ` heading before a section as that section's group; for an item filed under no group — the
  normal shape once the split made the inbox empty, since a consumer appending one report writes no
  group heading — the last `# ` before it is the live file's own `# Consumer suggestions`, whose span
  runs to the next `##` and therefore swallows the whole inbox preamble. So archiving appended a copy
  of "this file is the inbox, so an empty one means nothing is owed" into the *history* file, twice,
  before anyone read the result. **The verification could not see it**: fingerprints cover the
  consumer's prose alone, so the move reported "every fingerprint intact" while the file grew duplicate
  front matter. Fixed by taking the first `# ` in a document as its title and a group as any later one;
  a section with no group now prints a notice telling you to add one, rather than the tool inventing a
  name, on the same reasoning that keeps the index row hand-written. Reproduced both ways in a sandbox
  before and after.

  **It does *not* disturb the preceding section, and the first repair of this claimed it did.** The
  injected heading is separated by one blank line, and `fingerprint()` ends in `.strip()`, so the
  section above keeps its hash. Worth stating because the tempting story — "archiving S25 shifted S24" —
  was written into this file and one commit message before being checked, and it explains a symptom that
  has a different cause (below). The lesson is the loop's own: establish it, then write it.
- **A marker can be stamped with a sha that never matched its section, and the ledger can only report
  it, not explain it.** S24 read `revised` with prose that git shows byte-identical since the pass that
  archived it — verified by running the ledger against `CONSUMER_SUGGESTIONS_HISTORY.md` at that very
  commit, where it already disagreed. So the marker was written wrong *in its own pass*, most likely by
  stamping before a last edit to the consumer's text, and no later operation is implicated. Restamped
  to the computed value on 2026-08-12 after establishing that much. `--backfill` deliberately will not
  do this — it only touches `unmarked-reply`, because silently restamping a `revised` section is exactly
  how a genuine re-triage signal would be erased — so it is a hand edit, and it needs the prose-unchanged
  check first. If you cannot show the prose is unchanged, the verdict is honest and you re-triage.
- **A Python script named `.sh` gets run as bash sooner or later, and `import` is an ImageMagick
  binary.** Both tools shipped as `triage-state.sh` / `triage-archive.sh` with a
  `#!/usr/bin/env python3` shebang, which is correct only for a caller who *executes* them. Someone —
  a person, or an agent going by the extension — eventually types `bash .claude/triage-state.sh`. Bash
  ignores the shebang, reads the docstring as commands, and reaches `import hashlib`, where
  `/usr/bin/import` is **ImageMagick's screen-capture tool** and takes its argument as an output
  filename. The repository root grew four empty files named `hashlib`, `pathlib`, `re` and `sys` — the
  script's own imports, in order. `triage-archive` writes a `subprocess` instead, which is how you tell
  which of the two was run. Renamed to `.py` on 2026-08-16.

  Two things make this worth recording rather than just fixing. **It is silent**: `import` creates the
  output file and *then* fails on its security policy, so nothing announces a write, and the litter is
  0 bytes with plausible names — a stray `re` in a project root reads as a vendored module, not as
  debris. And **the extension was the entire invitation**: nobody types `bash foo.py`. So the fix is
  the rename; a guard would be defending the wrong door. Established before being written down —
  `bash -c 'import sys'` in an empty directory creates `sys`, and running the real script under `bash`
  reproduces the full set.

  The same reasoning removed every bare-path invocation: `triage-archive.py` shells out to the ledger
  through `sys.executable` and `watch-suggestions.sh` through `$PYTHON`, so neither the exec bit nor
  the shebang is load-bearing anywhere any more.
- **The archiver verifies the move, not the verdict.** It will archive a section the ledger still calls
  `new` without complaint: it checks that the prose arrived byte-for-byte, not that anyone answered it.
  The lint is the ledger itself pointed at the *history* file — a well-formed archived section reads
  `current` there, so anything reading `new` or `unmarked-reply` was either archived unanswered or lost
  its marker in transit. Two seconds, and it is the only thing between a silent mis-archive and a
  permanently lost item.
- **A preamble line beginning `**Status` is read as a block reply**, and marks every id it names
  answered. `**Status:** intake for field notes — S1 and S2 are open` is an entirely ordinary thing to
  write at the top of an inbox and collides with the reply idiom exactly; `--backfill` then stamps both
  untriaged sections `current`. The loop's one job, inverted, by a line of prose nobody would look at
  twice. The block-reply rule is right — a release note under a `#` heading really does answer items by
  name — so the fix is on the writing side: **do not open a preamble line with `**Status`** unless it
  is a real reply; a blockquote (`> **Status:** …`) is enough. Found while adopting the loop into a
  second repository rather than here, which is the argument for keeping the published copy in sync.
- **A link guard and "the prose is evidence" collide, and the guard must give way.** `test_doc_links.py`
  requires every relative link in every markdown file to resolve, and it exists because an item moving
  live→history breaks every pointer at it. Consumers have now started citing `RMn` items by link inside
  their reports — so when RM89 shipped, S35's quoted prose held a link the guard called dead, and the
  pass that archived the next item quietly retargeted it. That edit moved S35's fingerprint, and the
  ledger duly reported the section `revised`: our own edit wearing a consumer revision's clothes, which
  is precisely the signal the marker exclusion exists to keep clean. **Never edit a report to satisfy a
  tool.** The link was not even stale in the sense the guard means — it records where RM89 lived on the
  day it was written, and the reply directly above it carries the current pointer. Fixed on the guard's
  side: `_verbatim_lines` exempts everything below a section's marker in both consumer documents, our
  replies stay checked because they sit above it, and a test asserts a genuinely dead anchor still
  survives down there. The prose was restored to what the consumer wrote and the fingerprint came back
  to the exact value it had carried.
- **An off-switch spelled `${VAR:-default}` is not an off-switch, and the watcher's `BRANCH` knob was
  one.** `${BRANCH:-main}` treats an explicitly empty value as unset, so `BRANCH=` — the one thing
  anybody would type to turn the pause off — silently restored `main` and enabled it instead. Found
  while porting the branch-pause to the gist on 2026-08-18, by *running* the off-switch in a sandbox
  rather than reading it, and fixed in both copies to `${BRANCH-main}`. The two spellings behave
  identically for every value except the empty one, which is exactly the value no test reaches by
  accident; the general form is that a knob's disabling value is its own case and needs its own probe.

- **A `#` at column 1 inside a fenced code block ends the section, and the ledger cannot tell.**
  `BOUNDARY_RE` is `^#{1,2} ` and knows nothing about fences, so a python comment written flush left
  in a reply — `# StudyRow, 0.6` above a field declaration, which is the natural way to label a
  snippet — truncates the section there. Everything after it, **including the marker**, is outside
  the body the ledger reads, so `stored_sha` returns `None` and a freshly-stamped section reports
  `unmarked-reply` forever. It looks exactly like the git-sha failure below and has a different
  cause; what distinguishes them is that `stored_sha` on the hand-sliced section finds the marker
  while the tool's own `sections()` does not. Found writing S55's reply. **The fix is on the writing
  side** — indent the comment or put it at the end of the line — for the same reason the `**Status`
  preamble collision is: teaching the splitter about fences means teaching it about indented fences,
  tildes and nested blocks, and the failure is rare and self-announcing once you know the shape. It
  also affects the *consumer's* prose, so if a report ever arrives with a flush-left `#` in a
  snippet, that section's body is short and the fix is still not to edit their text: stamp by hand
  after checking `sections()` agrees, and say so.

- **A marker can be stamped with a git commit sha, and it fails twice over.** S36's read
  `<!-- triaged: 0.6.0 · sha cbeeb8f -->`, which is a real commit in this repo and not a fingerprint at
  all. `MARKER_RE` wants exactly twelve hex characters, so seven made the marker **invisible**: the
  section read `unmarked-reply`, indistinguishable from one answered before the ledger existed. The
  second failure is the one worth remembering, because it compounds silently — with no marker visible,
  `reply_end()` falls back to the single-paragraph rule, so paragraphs two onward of a long reply leaked
  back into the fingerprint. The value the ledger *reported* for S36 was therefore also wrong, and
  restamping to it left the section `revised` a second time. Stamp the sha the ledger prints for the
  section, then re-run the ledger and confirm it reads `current` — the confirmation is the whole check,
  and it is two seconds.

---

## 7. State, and what the first full run found

**As of 2026-08-11 the backlog is empty.** S1–S18 all carry a reply and all sit in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) with a contents line each. The next
consumer item is **S19** and the next roadmap item is **RM47** — but read both off the tools rather than
off this sentence, which is exactly the kind that goes stale:

```
.claude/triage-state.py                                    # the live inbox — empty means nothing owed
.claude/triage-state.py docs/CONSUMER_SUGGESTIONS_HISTORY.md   # every answered item, all `current`
.claude/triage-state.py --next                             # the next unclaimed Sn, over BOTH files
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
