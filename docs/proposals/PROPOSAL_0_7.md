# 0.7 design thread — the deferrals that were waiting on a decision, not on the world

**What this is.** Stage 3 of the design cycle for the 0.7 line. [ROADMAP_0_7.md](../ROADMAP_0_7.md)
holds items that are legal in a minor and were not taken into 0.6, each waiting on **a design
question, a corpus, or a caller**. That taxonomy is the whole of this round's sort: an item waiting on
a corpus or a caller is not ours to decide, and an item waiting on a design question has been waiting
for somebody to make one. This document makes them, per item, with the maintainer.

Same convention as [PROPOSAL_0_6_PT2.md](PROPOSAL_0_6_PT2.md): each item records the problem in plain
terms, the **facts established while deciding it** — four of which change what the roadmap entry says —
the decision, the repairs rejected and why, and the charter check. Two items dissolved into others
while being decided, and one grew an obligation nobody had filed.

**Status.** Decided 2026-08-28, on the `0.7` branch, before implementation. **Nothing here has
shipped.** Where a decision changes what ROADMAP_0_7.md or ROADMAP.md says, those files are stale and
this one wins until the item lands and moves to ROADMAP_HISTORY.

**The release.** 0.7 **is** the minor that was left uncut on 2026-08-27 — the S63–S74 batch already on
this branch, whose `next-minor` markers resolve here. Everything below joins that batch and cuts with
it as `0.7.0` across all three packages. Nothing in this document is gated on a version: every item is
additive under Principles 3 and 8, and legality stopped nothing this round.

**Scope.** Eleven items decided: six from ROADMAP_0_7.md and five that were sitting in ROADMAP.md as
*a minor, release undecided*. **Ten build and one closes into another** — RM83, whose premise stopped
holding. The succession filed alongside them is RM135 and is not one of the eleven.
Nine further items stay deferred on a gate that is not ours to open, restated per item in
[Not taken](#not-taken-and-the-gate-in-each-case). One new item (RM135) was filed by the round itself, and
RM134 arrived alongside it from an unrelated thread and is out of scope here.

---

# The sort, and the rule it used

One rule, and it is the file's own taxonomy read as a scheduling instruction:

**An item waiting on a corpus or a caller is not a candidate. An item waiting on a design question is
a candidate, and the decision is the work.**

That is narrower than PT2's three rules and does the same job, because PT2's rule 2 — *a new expensive
feature waits for the demand that would fix its shape* — is a statement about **which** open question
an item has, not a separate test. Demand fixes a shape nobody has fixed. Where the shape is already
fixed by a decision one release old, demand has nothing left to contribute, and RM132 is the item that
makes the distinction load-bearing: a full-cost authored column that would normally wait is taken here
because RM47 already decided its shape for a structurally identical table, so the risk P9 prices was
spent a release ago.

**What sizes the release.** Legality, as always, and it settles nothing: every item is a new optional
column, a new optional table, a new report, or a flag. **Severity orders the queue inside it**, and by
severity this round is led by a charter debt (RM126) and a mechanism the charter itself named as
missing (RM124).

**The two dissolutions are the most valuable output of the round**, and both went the same way: an
item was filed as a missing *operation*, and deciding a neighbour removed the condition that made the
operation necessary. RM83 is one and RM128's central ask is the other. Neither was argued down — the
premise stopped holding.

---

# Decisions

## RM126 — nothing tells a consumer what a release changed about compiled output

**Severity** medium-high · **Owner** format (record + `needs_recompile` + roster) + compiler (the
sweep) · **Entry** [ROADMAP_0_7.md § RM126](../ROADMAP_0_7.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output) ·
**Motivating case** S62 (just-dna-registry), narrowed by S65

### The problem

Principle 3, as amended 2026-08-21, says a corrected derivation may ship in any release but **never
silently** — each release declares its corrections, readable offline and without recompiling. No such
channel exists, so the charter names a surface that is not there. This is the one item in the round
that is owed rather than offered.

A consumer holding a stored artifact can ask two questions and not the third. *Is the stored input
still legal?* — `validate_spec` answers `ok`. *Was this compiled under a contract-incompatible
compiler?* — compare versions, and a patch is compatible. Neither is **would recompiling this artifact
produce different output than the stored one?** Answering it today means enriching into a scratch
directory and recompiling, which is the operation rather than a triage for it.

### Facts established while deciding it

The sweep in the entry stands and is the design's own prototype: all sixteen `reference_examples/`
compiled under `v0.6.1` and `0.6.6` from byte-identical spec inputs, an interval that is **entirely
patch releases** — 16/16 changed at least one published manifest field, 10/16 moved `artifact.digest`,
0/16 moved `content_signature`. The digest movement is RM120's authored `curator` column growing
`studies.parquet` by 257 bytes, so a **parquet schema** moved across a patch interval. Six changed a
published, indexed manifest field with *both* hashes byte-identical.

Authored identity held throughout, which is the charter working as designed and is exactly why no
existing surface can see any of this: a digest comparison, a signature comparison and a `revalidate`
all correctly report no change while an indexed field goes stale.

### The decision

Build the shape settled in the S62 thread, in full, plus the roster S65 asked for.

- **`just-dna-format` carries the record and the function.** A static table of per-release records and
  a pure `needs_recompile(compiled_under, current)` over it. Four axes per record — parquet schema,
  parquet bytes, `content_signature`, and the set of changed manifest fields — plus the **declared**
  correction-versus-addition split, which is the half no diff can compute: only the person fixing the
  bug knows whether the stored value was *wrong* (`stats.genes`) or merely *absent* (`curator`). A
  static table and a function is pydantic-only work, and format is the tier every consumer has.
- **Intervals compose as a union over the releases in `(a, b]`.** Storage is linear rather than
  O(releases²), and *moved-and-moved-back still counts as moved*, which is the right reading for
  staleness. The interval shape is also what gives S65's convergence requirement for free — **the
  interval from a version to itself is empty**, so an automated sweep cannot mint a fresh PATCH every
  run forever. That property is load-bearing and is recorded as such, because a field-keyed or
  latest-known-defect shape would not have it.
- **Unknown is a state, never an empty result.** Asked about an interval the installed package has no
  record of, the answer is *cannot say*. Without it the surface is worse than nothing, because a
  consumer would stop recompiling on the strength of a silence. House tri-state, and `None` is never
  `False`.
- **`just-dna-compiler` carries the sweep instrument**, since producing a record means compiling.
  Backfill `0.6.1`→`0.6.6` by measurement with the harness that produced the numbers above; older
  intervals stay honestly `unknown`.
- **The gate runs in the bump → `uv sync` → tag sequence**, not as an ordinary test, because it needs
  the previous release actually installed. A release whose sweep shows a changed field with no
  declaration covering it **fails**. That is what stops this becoming the hand-kept map everyone agrees
  it must not be. A release where nothing moved records a **measured zero with its evidence**, never
  silence.
- **The roster ships beside it**, and it is the half that shrinks the item rather than growing it: a
  published set naming which manifest fields are pure functions of the authored rows, so a consumer can
  recompute the current answer from stored inputs using `spec_tables` (RM116) and `module_stats`
  (RM121) rather than consulting the table at all. **Its boundary is conditional and the condition
  must be published with it**: `validate_spec` computes `stats` over the full row set while
  `compile_module` re-derives over the survivors only when the symbolic-allele drop removed something,
  so a recomputation from authored rows is the *pre-drop* side and `manifest.stats` legitimately
  disagrees with it, permanently, for a module that lost the sole row naming a gene. The condition is
  now checkable, because `compilation.dropped_rows` shipped 2026-08-24.
- **Scope v1 to compiler-derived outputs and say so.** Enricher-side outputs stay **unmeasured**,
  which is not the same claim as unchanged.

### Repairs rejected

- **A `should_rebuild` verdict.** The same fact costs a registry an immutable PATCH and `just-dna-lite`
  a free rebuild, so the decision is the consumer's and only the fact is ours. The declared correction
  flag is not this: it is a fact about whether a value we published was wrong, which is upstream
  knowledge only this repo holds, and the per-axis breakdown stays exposed underneath it. A bare
  boolean with nothing under it would deserve the objection exactly.
- **A hand-kept per-release map.** The defect wearing a public name, and `@registry-completeness` is
  the tag: five of the six RM104–RM111 fixes were a derived value restated by hand. The measurement
  forces the declaration rather than the author remembering to write one.
- **A field-keyed table.** Fails S65's convergence requirement — a hint firing for a version compiled
  by the exact compiler now installed mints a version number every run, forever.
- **Replacing the consumer's recomputation probes.** Scoped for coexistence at the reporter's request:
  we state what a release did, they check what a specific stored artifact says, and the two fail
  differently.

### Charter check

P3 — this *is* the amendment's channel, so the item exists to discharge a rule rather than to test one.
P4 — reads identity, moves neither hash. P6 — the axis names are a closed vocabulary, `frozenset[str]`
plus a validator. P9 — a static table plus a pure function in format, and an instrument in the
compiler: no authored layer is touched at all, so this is the cheapest layer the charter prices.

---

## RM124 — an author's correction to a derived table has nowhere to live except inside it

**Severity** medium-high · **Owner** format (schema) + compiler (apply + reverse) + enricher (the
derived-table writers) · **Entry** [ROADMAP_0_7.md § RM124](../ROADMAP_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it) ·
**Motivating case** S60 (just-module-creator)

**This is the keystone of the round.** RM83 closes into it, RM130 was blocked on one of its questions,
and RM128's central ask thins because of it.

### The problem

Every derived sidecar is merge-not-clobber: an existing row is authoritative and a re-run adds to it
rather than replacing it. The rule exists because these tables are human-overridable by design, and its
consequence is the single most important operational fact about a second pass — **to re-derive a
sidecar you delete it first, and deleting it discards every hand-curated row in it along with the stale
ones.** `reference_examples/cyp2c9_warfarin_grch37/` carries three hand-authored `source="manual"` rows
in `resolution.csv` that no re-run reproduces; `literature.csv`'s loss includes a curator's deliberate
blank, which a merge cannot distinguish from an absent value in the first place.

The 2026-08-12 cost amendment names this class in its own words — *a derived table that is both
machine-written and human-overridable can be edited into a state that is not merely stale but a false
claim, which wants a mechanism rather than a convention.* RM45 discharged it for exactly one table by
making `verification.json` unwritable by hand. Nothing discharges it for the six where overriding **is**
the intended feature.

A consumer built the conservative exit — a non-destructive capture / verify / delete / re-derive /
classify / reapply wrapper — and it stops precisely where the problem predicted: a subject present in
both copies with a differing fact is *either* a cell the author edited *or* a revision the source
published, and with two data points there is no third to separate them. Their tool reports and refuses
to resolve, which is the honest outcome and is a symptom.

### The decision

**`overrides.csv`: an authored overlay table that lies on top of a derived one and is never merged into
it.** The derived files become pure build products — `derived = f(source, overlay)` — and the four
consequences the reporter named all hold: nothing is hand-edited so re-derivation is non-destructive by
construction rather than by a wrapper being careful; a difference between a fresh row and a previous one
means the source revised, full stop; the reason for a correction travels with the module; and the
terminal state becomes detectable for free, since an overlay row that no longer changes anything means
the source caught up — evidence that an authored judgement was later vindicated, available nowhere else
in this format.

**Columns.** `table`, `subject`, `member`, `field`, `operation`, `value`, `reason`, `decided_by`,
`decided_at`. `reason` is **required**, and that is what makes this a record rather than a knob.

**Operations are `update`, `insert` and `suppress`** — a closed vocabulary, `frozenset[str]` plus a
validator per P6. `update` corrects one field of a derived row; `insert` supplies a row the source has
no answer for, which is what the three `source="manual"` rows in the flagship module actually are;
`suppress` removes a derived row the author rejects. An inserted row is written as several overlay rows
sharing `(table, subject, member)`, one per field, so the table has one shape rather than two.

### The keying decision, which the entry left open and the operations make sharper

`(table, subject, field)` is not enough, and the table it fails on is the flagship case. RM115 published
`resolution.csv`'s merge rule as `subject`, **not** a uniqueness constraint: one `variant_key`
legitimately resolves onto several loci, `locus_index` orders them, and a pass replaces the group whole.
So a subject names a *group of rows* and an overlay keyed on it cannot say which locus it corrects.
`gene_validity.csv` needs the same care in the other direction, its key having two levels
(`assertion_id` else the gene's grain).

**The key is `(table, subject, member, field)`, where `member` is an optional within-group
discriminator whose meaning is the named table's own ordering or sub-key column** — `locus_index` for
`resolution.csv`, `assertion_id` for `gene_validity.csv`, empty for every table whose subject already
identifies exactly one row. That single column serves all three tables without a per-table key grammar,
which is the thing to avoid: a key that differs by table is a rule every reader re-derives.

**An empty `member` on a grouped table is group-scoped for `update`, and refused for `suppress`.** The
asymmetry is deliberate and is the whole reason the operations made this question sharper. A
group-scoped correction is a coherent thing to want — *every locus this key resolves to has the wrong
`source`* — and it is recoverable if wrong. A group-scoped suppression silently drops every locus for a
`variant_key` when the author almost certainly meant one, and it is not recoverable by reading the
result, because the rows are simply absent. **The destructive operation refuses the wildcard**; an
author who genuinely wants a whole group gone writes one row per member, and the count is small by
construction.

### What P7 makes of a build product, and why no `previous_value` column is needed

`reverse_module` emits the **post-overlay** derived table plus the overlay. The entry flagged that this
means the overlay applies twice and the fixed point has to be checked rather than assumed — which is
right, and checking it is what P7 requires of every derivation anyway. **It passes, because all three
operations are idempotent set operations by construction**: `update` to a value already present is a
no-op, `insert` of a row already keyed `(subject, member)` is a no-op, `suppress` of a row already
absent is a no-op. `row.upgraded().upgraded() == row.upgraded()` is the same property the charter
already demands, and it holds here without a new column.

The alternative — reverse emitting the *pre*-overlay table so the apply happens exactly once — would
require the overlay to record the value it replaced, so reverse could un-apply. That is a derived cell
inside an authored table, and it rots the moment the source moves: precisely the staleness
`licensing.withdraw_stale_dataset` had to be built for, and the reason RM71 refuses a comment column.
Idempotency buys the round trip at no schema cost.

**Idempotency proves value identity; the round trip is compared on bytes, and row order is load-bearing**
— parquet bytes depend on it, and authored row order is preserved through compile → reverse → recompile.
So `insert` owes a placement rule, and it is stated here rather than invented by the implementer: **an
inserted row is appended at the end of its subject's group, in the order the overlay rows appear.** That
makes placement a function of the overlay's own authored order, which the round trip already preserves,
rather than of a sort over values that a corrected cell could move. `update` and `suppress` need no rule —
one edits a row in place and the other removes one, and neither reorders what remains.

The fact signatures and `resolution_signature` are over the derived tables **as they stand**, therefore
post-overlay, which is right: a signature should describe what the module actually asserts. The overlay
is authored input, so it is inside `content_signature` — and **no published module's `content_signature`
moves**, because an absent optional table contributes nothing, exactly as an unset optional column does.

### Whether merge-not-clobber survives: it does not, and what replaces it

**Dropped for the six covered derived tables.** That is the prize, and it is what makes this 0.7 rather
than a smaller thing: it changes what a re-run does to every module already published.

What replaces it is narrower than "every run re-asks", which would cost the full resolution time on
every pass and is not what dropping the rule means:

- **Gap-filling stays the default.** A re-run fills subjects with no row and leaves recorded rows alone,
  as today — the difference is that a recorded row now carries no authored content, so leaving it alone
  risks nothing.
- **Full re-derivation becomes free**, because the author's corrections are in the overlay and cannot be
  lost. `rm` plus a re-run is the crude form and now costs nothing; `enrich --rederive` is the form that
  keeps a baseline, and it is where RM83's residue lands (below).

**The enricher's docstrings are part of this change, not a follow-up.** Every writer of a covered table
states, in the docstring a reader outside this repo actually has, that the artifact is now purely
derived, that hand-authoring it is not expected, and that `overrides.csv` is where a correction goes.
A printed contract is the surface this repo has measured the cost of getting wrong, at 3,038 rows for
the 0-versus-1-based `start` description, and the sweep belongs in the same commit as the behaviour.

### The overlap with `provenance.json`, and the succession

`ProvenanceItem.outranks: dict[str, str]` — `{column: why}`, an authored cell outranking a source, with
prose — is the same concept one table over. The entry says to decide before either grows a second
field, and the decision is a succession rather than a merge:

**Both mechanisms stand in 0.7, the duplication is stated rather than hidden, and the unification is
filed for 1.0.** The rule that survives is the simpler one: **the existence of an override in an
authored table auto-beats the derived value**, with no separate declaration to write. By Venn diagram
the new logic is a partial superset of what `outranks` allows and reaches it more directly, and once an
author controls both derived overrides and authored tables the `outranks` knob's need evaporates. Filed
to the 1.0 cleanup tracker, since a removal is major-only under P3.

**0.7 emits no deprecation warning, and that is a P3 decision rather than caution.** A deprecation
belongs in a minor only where its audience can *act* on it. `outranks` covers an authored cell beating a
source; the overlay covers derived tables. Until the overlay's semantics reach authored tables — which
is the 1.0 work — an author warned off `outranks` has nowhere to go, and a warning nobody can clear is
noise rather than notice. The succession is documented in SCHEMAS and on the tracker; the warning
follows the replacement.

### Repairs rejected

- **Per-consumer application of the overlay.** If each downstream tool applies its own, two consumers
  compiling one spec directory disagree about what the module says and the artifact stops being a
  function of the spec. The reporter's tier argument was accepted and is not an open question.
- **Update-only, with manual rows left inside the derived file.** The sidecar is then not a pure build
  product after all, and merge-not-clobber has to survive for exactly those rows — which re-opens what
  this item exists to close.
- **A per-table key grammar.** Each table's own key spelled into the overlay reads as precise and is a
  rule every consumer re-derives, differently. One `member` column, whose meaning the named table
  fixes, is the same expressiveness with one thing to learn.
- **Merging `outranks` into the overlay now.** Legal only if the old form survives as a working derived
  alias (P3), which means shipping the unification *and* its compatibility shim in a release where the
  overlay has no users yet. The succession costs a documented duplication for one major line and buys
  the decision being made against real usage.

### Charter check

P1 — data, not code. P2 — authored input, not a fetch; the compiler reading it is doing what it already
does with every other authored table. P3 — a new optional table is additive and minor-legal, and no
published module's identity moves. P5 — the overlap with `outranks` is the principle's own question, and
it is answered by a dated succession rather than left to erode. P7 — the round trip holds by
idempotency, proven by test rather than asserted. P8 — demotes nothing. P9 — **full cost, and the
amendment is what invited it**: a mechanism rather than a convention for the class the amendment names.

### The coordination step, which is real and routine

`just-dna-registry` rebuilds a spec directory from `RECOGNIZED_SPEC_FILES`, built from `SPEC_DATA_FILES`
— a hand-kept mirror of our table constants — and a name missing there is a file dropped on the next
re-publish, which is how `licensing.csv` was lost before their 0.16.2. `overrides.csv` needs one entry
added there. It is the same one-line change every new table kind already needs, and it goes in the
integration notes rather than being discovered.

---

## RM83 — a derived sidecar can only be refreshed by deleting it

**Severity** medium-high · **Owner** enricher · **Entry** [ROADMAP_0_7.md § RM83](../ROADMAP_0_7.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold) ·
**Disposition** **closed as filed, contingent on RM124 landing**

### The decision, and it is not a build

**RM83 is dissolved by RM124 rather than argued down**, and both of its halves go the same way. The
`--refresh` command with its three open questions is not built; nothing named in the entry — no proposed
table beside the current one, no diffs file, no new command with a lifecycle — is built either.

- **The refresh half stops existing.** The entry's problem is *"to re-derive a sidecar you delete it
  first, and deleting it discards the curator's rows."* Once the derived files are pure build products
  with the overrides in the overlay, there is nothing inside a sidecar to preserve, so `rm` costs
  nothing and needs no command wrapped around it to be safe.
- **The drift half stops being unperformable.** The entry's problem is that merge-not-clobber means a
  re-run never re-asks about a recorded row, so a source that silently *revised* an answer moves no
  `fetched_at`, no fact signature and no digest — making §5.1's canary an instrument that cannot fire on
  its own, because detecting drift **is** the delete-and-re-derive that discards the overrides. With the
  discard harmless, a full re-derivation is an ordinary operation and the canary fires from it.

**The blocking question is answered rather than deferred.** The entry named it: *on most sidecars
nothing records that a row was overridden*, so "re-derive the machine rows and keep the overrides" is
not implementable, because the tier cannot tell a curator's edit from what the source said last time.
Under the overlay the tier never has to tell them apart — the edit is recorded by construction and the
derived row carries no authored content at all.

### The residue, and it is a flag rather than a command

A full re-derivation that keeps a baseline can report what moved, and this is where the round's honesty
has to be exact rather than comfortable. **The report is only free where a baseline exists.** `rm`
followed by a re-run destroys the old values before the fresh ones arrive, so nothing holds both sides
and no report is possible — that path re-derives silently and correctly, and the proposal says so.

**`enrich --rederive`** is the path that keeps one, and it composes with RM128's transaction below
rather than adding machinery of its own: the run stages a complete fresh table beside the current one
and commits by rename, so **both files exist at the commit boundary** and the diff is genuinely free.
What it reports is which recorded subjects changed value — the canary, performed.

**This is a flag on an existing command, not RM83's `--refresh`.** The distinction is not cosmetic: what
made RM83 a design item was three open questions — which tier owns it, what it does with a difference,
and the blocking one about recording overrides. All three are now answered by decisions made elsewhere
in this document (the enricher, because it fetches; report and commit the fresh side, because the
author's corrections are safe; and the overlay). What is left is a re-derivation mode on the command
that already does the derivation, which is the shape the entry would have reached had its blocker not
existed.

### Bookkeeping

The entry moves to ROADMAP_HISTORY as **closed, not shipped**, in the commit that lands the overlay —
not before. Until RM124 is in the tree the problem it names is still real, and a closure recorded
against an unlanded dependency is the kind of bookkeeping that makes a ledger untrustworthy.

### Repairs rejected

- **A diffs file or table tracking what moved between passes.** It is version control with no consumer,
  beside the version control the author already has, over a file that is now regenerable from source
  plus overlay.
- **A pass that applies the newer value.** Rewriting an authored or curator-set cell destroys the
  evidence of the upstream change. Still the rule, and the overlay does not soften it: an overlay row is
  the author's answer to a difference, never the tier's.
- **Re-asking every subject on every run.** Dropping merge-not-clobber does not mean this, and reading
  it that way would put the full resolution time on every pass to buy drift detection nobody asked to
  run continuously.

---

## RM130 — a check's findings are counted and not kept, so a conflict has no name to act on

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP.md § RM130](../ROADMAP.md#rm130--a-checks-findings-are-counted-and-not-kept-so-a-conflict-has-no-name-to-act-on) ·
**Motivating case** S70 (just-module-creator)

### The problem, and what was blocking it

The observability half shipped 2026-08-24: `clinical_significance` writes a `detail` grouped on
`opposed`, and `_findings_warning` says at `validate`/`compile` that a record reports non-zero
`findings`. What is left is the sidecar — a derived table carrying the authored value, the source's
value, and whether the two are *opposed* or merely *different* — and it was deliberately unshipped
because it is a third table in the overlay/`outranks` family, so shipping it would pre-empt RM124's
question 2.

That question is now answered, so this ships.

### The decision

**A derived conflict table, keyed `(variant_key, genotype)`, positioned as the overlay's input side.**
The lifetime follows directly from the succession decided above: **a conflict is a question and an
overlay row is the answer.** An author reads the conflict table, decides, and writes an `overrides.csv`
row — which is also what makes the terminal state visible, since a conflict that stops being reported
means the archive caught up with the author.

**It promotes the mechanism that survives to 1.0.** The table's own documentation, and the warning that
points at it, name `overrides.csv` as where an answer goes — never `outranks`. Steering authors onto the
succession's winning side from the start is the cheapest form of a migration, and it costs a sentence.

**The key cannot be a bare `variant_key`**, and this was settled rather than re-derived: `compare_clin_sig`
compares an authored call for a *genotype*, and `annotations.parquet` keys on genotype for the same
reason. A table keyed on the variant alone would collapse two authored calls that disagree with the
archive differently.

### Repairs rejected

- **Folding the conflict into the overlay as an evidence column.** A conflict nobody has answered yet
  has no overlay row to live on, so unanswered conflicts — the entire point — would have nowhere to be.
- **Escalation, a `strict` matter, or auto-correction.** Out of scope on the reporter's own scoping and
  ours. A conflict is a question and half the time the archive is the stale side, which is why the
  ClinVar cross-check does not escalate under `strict` and why the shipped warning says so in its text.

### Charter check

P2 — derived from an injected comparison, no fetch in the compile path. P3 — a new optional derived
table, additive. P9 — **half cost**: machine-written, and under RM124 it is not human-overridable at
all, since the answer goes in the overlay rather than into this file.

---

## RM128 — `enrich()` persists nothing until its tail, so a run killed at minute 29 has written nothing

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP.md § RM128](../ROADMAP.md#rm128--enrich-persists-nothing-until-its-tail-so-a-run-killed-at-minute-29-has-written-nothing) ·
**Motivating case** S66 (just-module-creator)

### The problem, and the ask that dissolved

The truncation half closed 2026-08-24: nine sidecar writers now go through `layout.atomic_writer`, so a
killed process leaves the previous table rather than a short one. Three asks remained, and the central
one was **incremental or checkpointed persistence**, which turned on a promise nobody had written down:
*is a `strict` refusal allowed to leave rows behind?* Today `enrich(mode="strict")` raises before the
single `if write:` block, so a refused run leaves the module exactly as it was — a property somebody may
be relying on, unwritten, which is exactly the state in which it gets broken by accident.

**The question dissolves, because checkpointing was the wrong lever.** The choice as filed was between
keeping the promise and recovering the thirty minutes. It is not a choice: **the run becomes a
transaction**, which keeps the promise *absolutely* and recovers the work as well.

### The decision

**Durable staging beside the target, plus an atomic commit at the gate.**

- The run stages resolved rows **to disk, in the target's own directory**, as it goes — the editor
  `.swp` pattern, and `layout.atomic_writer` already stages exactly there, so this extends a shipped
  primitive from one file to a whole run rather than inventing one.
- Same-directory staging is not a convenience, it is the correctness condition: a rename within one
  filesystem is atomic, while `shutil.move` across a partition degrades to copy-then-delete and is not.
  Staging beside the target makes a cross-device move structurally impossible rather than merely
  avoided.
- **The gate commits.** A `strict` refusal commits nothing, so *"a refused strict run changes nothing"*
  becomes a written promise rather than an accident of statement order — the item's actual question,
  answered in the direction that breaks nothing.
- **A kill at minute 29 leaves the staged work**, and the next run resumes from it. That is the
  incident, and it is fixed without the mode-conditional behaviour that was refused in advance: `write`
  means one thing in every mode, and staging is not writing.
- **A flag keeps the staging files after a successful commit**, for debugging. The default removes them.

**Not mode-conditional, and the refusal in the entry stands**: `write=True` meaning "at the end" under
`strict` and "as we go" under `best_effort` is a flag that does not mean the same thing in every
function that takes one. Under a transaction the flag means the same thing everywhere, because
committing is the only write.

**RM124 thins what the promise has to protect.** What a staged, uncommitted table can contain is now
provably machine-derived and never an authored value, since authored corrections live in the overlay.
The two decisions were reached independently and reinforce each other, which is worth recording.

### Ask 3 — an advisory lock, taken

**`flock` on the spec directory for the read-modify-write window.** The transaction does not close the
concurrency window: two runs can each stage and each commit, and the last writer wins over a merge with
neither knowing. The reported incident is the sharp form — a client-side kill did not stop the worker, a
zombie run reached the write and overwrote a restored 330-row table with 162 rows, and the module then
validated, closed and compiled green. Nothing downstream could see it, because the three branches that
deliberately write **no row** for an unanswerable subject make a shorter table indistinguishable from a
module whose author resolved less. Those branches are correct and are not in scope.

`flock` is the shape because it has neither of the alternative's problems: a lockfile left by exactly
the kill this item is about would block every subsequent run, which is a worse unattended failure than
the one it prevents, and the staleness rule that would fix it is a clock — which this repo has refused
before (*guard the plan, not the clock*). `flock` dies with the process. **It is untested here on the
network filesystems a consumer may use, and the implementation owes a documented degradation rather
than a silent one.**

### Ask 4 — a progress callback, taken, and the unit is decided here

`progress: Callable[[int, int], None] | None = None`, reporting **`(done, total)` over subjects.**

The entry filed this rather than shipping it because the resolver chain is batched inside `resolver.py`
rather than being a per-subject loop, so the unit reported is a design choice — and a leaf shipped
against a guess is one P3 keeps working forever. The guess is therefore argued rather than made:

- **The incident is an idle timeout.** Both reported runs died at 1800 s with essentially every variant
  resolved. What the caller needs first is a keepalive with monotonic progress, which rules out
  **phases**: a 29-minute phase emits nothing and the timeout fires anyway.
- **`total` must be known up front** for the number to mean anything to a caller rendering it. The
  subject count is; the link count is not, since it depends on what resolution finds.
- **Subjects are the only unit the author's mental model already has.** Links are an implementation
  detail of the batched resolver, and publishing one makes a refactor of `resolver.py` a contract
  change — the rename P3 forbids arriving through the back door.

The reporter explicitly did not ask for a protocol, and none is added: two integers, no object, no
event vocabulary to keep working forever.

### Charter check

P2 — enricher-only; the compile path imports none of it. P3 — a keyword argument with a default and a
staging directory are additive; no schema, no manifest field, no vocabulary. P7 — a committed run
produces the table an uninterrupted run produces, which the resume path owes a test.

---

## RM131 — `warnings` is a flat `list[str]`, and the discriminator that would make it readable is discarded

**Severity** medium · **Owner** compiler · **Entry** [ROADMAP.md § RM131](../ROADMAP.md#rm131--warnings-is-a-flat-liststr-and-the-discriminator-that-would-make-it-readable-is-computed-and-discarded) ·
**Motivating case** S68 (just-module-creator)

### The problem

`ValidationResult`, `ClosureResult` and `CompilationResult` all carry `warnings: list[str]` with no code,
no count, and no way to tell a finding an author can clear from one they cannot. A compile of a 190-row
module returned roughly **14 kB** of warnings. `strict=false` does not help — it changes what counts as
an *error*, not how much prose the channel carries — and every document on both sides of this seam tells
an author that warnings on a green run are the real output, which is followable only if the output can
be read.

**We already compute the answer and spend it on severity alone.** `_BLAME_TIER`/`_BLAME_ROW` is
literally *whose limit this is*, and its own comment says *"blame decides severity and nothing else"*;
`_closure_warning` reaches the same distinction from the other end. The actionability of each finding
exists at the point it is built and is dropped on the way out.

### Facts established while deciding it

Two, both of which shrink the item:

- **`manifest.compilation.warnings` already exists and already ships.** The channel is not missing; it
  is unreadable. This is a structure change to a published surface rather than a new surface.
- **`artifact_digest` is computed over the parquet `FileEntry` list**, so `manifest.json` sits outside
  the digest and appending to it moves no hash. A richer findings channel is therefore free of the
  identity cost that would otherwise price it. **There is no separate metainfo artifact to build**, and
  filing one would put a second home beside a shipped one.

The compiler emits **zero** `logger.info` calls, so there is no discarded informational tier either —
the findings that exist are the warnings, and they are already persisted.

### The decision

**Both halves, sequenced, in 0.7.**

1. **Actionability first, because it needs no vocabulary.** A `carried` list beside `warnings`, holding
   the subset of findings the author *cannot* clear. `warnings` is unchanged and stays the complete
   list, so nothing that greps it breaks; a consumer subtracts to get the actionable set. This is the
   reporter's own fallback shape — a list beside, rather than a field on each — it invents no permanent
   names, and it answers the question they actually asked: *can I do anything about this?* `blame` and
   the closure branch already classify two families; what it needs is for every emission site to say
   which side it is on.
2. **Then codes, named by each check where it is built**, feeding `warnings_summary: dict[str, int]`.
   Most work, most stable, and it has a precedent in this repo that is already a closed vocabulary a
   consumer keys on: `VALID_VERIFICATION_CHECKS`.

**The audit is the shared groundwork and is done once.** Roughly 29 append sites and 16 returning
helpers must each declare their side and their code; doing it twice is the actual cost being avoided by
sequencing rather than splitting across releases.

**The suppression record rides this channel.** A row suppressed by `overrides.csv` is invisible in the
build product — absent, with no trace of why — which is the one thing RM124's `suppress` operation costs.
It emits a finding into the same channel, **aggregated by reason** rather than one per row, so a module
suppressing forty rows produces one line with a count. Same rule the tier already follows for repeated
warnings, and it needs no new home precisely because the facts above say the home exists.

### Repairs rejected

- **`warnings_summary` with a plausible code set, shipped unattended.** The container is free and **the
  code is not**: a published vocabulary is permanent within a major under P3 and P6, so the first set
  shipped is the one every consumer keys on forever. That is the whole of the original deferral, and it
  is answered by deriving the set deliberately, not by declining the field.
- **Codes derived from the pinned catalogue.** Honest, and covers exactly what consumers already match
  on — but partial by construction, and a summary that silently omits unpinned findings is worse than
  none, because a consumer reading a digest believes it complete.
- **Codes derived from the emission site.** Mechanical and complete, and it keys on where the code lives
  rather than on what the finding is, so a refactor renames a published key.
- **A cap, a truncation, or a verbosity flag.** All three hide findings rather than organising them, and
  the author with the most warnings is the one who most needs the hidden ones.
- **A new metainfo artifact.** The channel ships already and is outside the digest; a second home would
  be one more thing to keep in step with the first.

### Charter check

P3 — `carried` and `warnings_summary` are additive fields; `warnings` keeps its meaning and its text,
and `@warning-text-is-api` is not disturbed. P5 — actionability and severity are separated rather than
overloaded onto `blame`, which is the principle applied to a field that was quietly carrying two axes.
P6 — the code vocabulary is `frozenset[str]` plus a validator. P9 — nothing authored is touched.

---

## RM132 — `pharm_variants.csv` makes a clinical claim per row and cites per variant

**Severity** medium · **Owner** format (schema) + compiler + enricher · **Entry**
[ROADMAP.md § RM132](../ROADMAP.md#rm132--pharm_variantscsv-makes-a-clinical-claim-per-row-and-cites-per-variant) ·
**Motivating case** S73 (just-module-creator)

### The problem

A ClinPGx-drafted module carried **1,482** drug-response rows and had nowhere to cite any of them.
Sixteen model fields, thirteen authored, none a PMID or DOI.

The shape was settled 2026-08-24 by the RM47 precedent, one release old and reached for a structurally
identical table: **a row cites when its claim is finer-grained than `studies.csv`'s key.** `studies.csv`
keys on `(variant_key, pmid)`, so a study row attaches to a *variant*; `pharm_variants.csv` keys on
`(variant_key, drug, genotype, phenotype_category, annotation_id)`, so one study row would attach to
every drug, genotype and phenotype category recorded for that variant. `evidence_level` is not the
provenance handle — it points at somebody else's *grading of* evidence rather than at the evidence — and
the licence row's `source`/`dataset` state redistribution terms, not grounding.

### Why a full-cost authored column is taken rather than deferred

This is the item that makes the round's sort rule load-bearing, so the argument is recorded rather than
assumed.

**What P9 prices is not the byte.** An authored column is full cost because a human must learn it and
P3 keeps it working forever, so the risk being priced is *getting the shape wrong*. **That risk was
spent a release ago.** `PharmVariantRow.pmid` is a copy of two shipped fields under the same grammar
(`StudyRow.pmid`, `MeasureBinRow.pmid`); an author who has met either learns nothing new. Demand is what
fixes an unfixed shape, and there is no shape here left for demand to fix.

**It is closer to a half-defect than to a new capability.** The table already makes a clinical claim per
genotype and structurally cannot ground one. That is a hole in an existing concern, not a new concern
added to a table — the distinction the *one concern per table* gate actually turns on.

**And the second half gets dearer with delay.** Both literature cross-check sites must learn the new
citation site **in the same release** — `_cross_check_literature` in the compiler and `enrich_literature`
in the enricher — and that obligation is RM47's recorded lesson in its own words: *shipping the column
without both would be evidence the format never checks, which is worse than the gap.* Every citation
from the new site would otherwise read as a stale orphan in one direction and be invisible in the other.
The cheapest moment to discharge a recorded lesson is while someone has just read it.

### The decision

- **`PharmVariantRow.pmid`, optional, free-form under the same grammar as `StudyRow.pmid` and
  `MeasureBinRow.pmid`.**
- **Both cross-check sites learn the site in the same release.** The enricher reaches the rows through
  **public** compiler symbols, as `load_binning_rows`/`binning_citations` already do for the bins; a
  second copy of the table roster in the enricher is the RM40/RM41 shape and is not repeated.
- **`provenance_quote` does not follow, and the entry says so rather than leaving it implied.** On the
  binning side it deliberately did not: the bin row cites and `studies.csv`/`literature.csv` describe,
  which is what stops `StudyRow`'s whole provenance column set migrating one column at a time. A
  1,482-row body of clinical claims is exactly where somebody will ask next, which is the reason to
  state the line rather than the reason to cross it.

### Repairs rejected

- **Widening `studies.csv`'s key.** The repair that looks obvious and the one RM47 already refused: it
  would make a study row's subject depend on which table read it.
- **Treating `evidence_level` as the provenance handle.** It grades evidence rather than pointing at it.

### Charter check

P3 — a new optional column, additive; no published module is invalidated. P5 — citation and grading are
separate axes and stay on separate columns. P8 — optional with respect to every published module. P9 —
full cost, taken with the argument above rather than by weighing file count.

---

## RM70 — `requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption

**Severity** medium · **Owner** format (schema) + compiler · **Entry**
[ROADMAP_0_7.md § RM70](../ROADMAP_0_7.md#rm70--requires_callable-is-variantrow-only-so-no-pgx-table-can-state-cpics-core-assumption) ·
**Found by** dogfooding 2026-08-13, `reference_examples/cyp2c9_warfarin_grch37/`

### The problem

CPIC's star-allele system assumes a position not called is reference — literally `requires_callable=false`
— and `haplotypes.csv`, `pharm_variants.csv` and `diplotypes.csv` carry no such column;
`requires_callable` and its companion `callable_from` are on `VariantRow` alone. So a star-allele module
cannot record the single assumption a consumer most needs before trusting a `*1/*1` result, and the
check that exists for it is unreachable from the module kind whose upstream states the assumption in
prose.

**Not gated on RM65/RM66's caller VCF.** Those wait on what a *caller emits*, because the shape of the
data decides the schema. This is about what a *curator asserts*, and the assertion already exists in
prose. The adjacency is that both ask whether a non-`variants.csv` table should carry something
`variants.csv` has, not that they share a blocker.

### The decision

**`requires_callable` on `HaplotypeRow` and `PharmVariantRow`, optional. Not on `DiplotypeRow`.
`callable_from` does not travel with them.**

Two tables and not three because those two name loci — they are two of RM43's three positional tables —
so a callability claim on either is about a position the row states, which is exactly what the column
means on `VariantRow`. `diplotypes.csv` names a star-allele *pair*, not a locus, so the same column there
could only mean "the variants defining these two haplotypes were callable", which is a fact about
`haplotypes.csv`'s rows restated one table over, where it drifts the moment a definition is edited. One
concept, one home.

`callable_from` waits because the two are different axes and the cheaper answer is to add it when a
module needs to say where the proof lives: `callable_from` says *where the proof is*, `requires_callable`
says *a proof is required*, and a row may legitimately require one and not know where the evidence sits.

### Repairs rejected

- **The column on all three PGx tables.** Full cost three times and wrong on the third, per above.
- **Declaring it once in `module_spec.yaml`.** The verdict is per locus and this repo has twice paid for
  assuming otherwise — RM36 rejected per-CSV build declaration because two files could disagree about
  one fact, RM32 rejected a gene-scoped PAR verdict because XG and SPRY3 straddle a boundary. CPIC's own
  assumption is not uniform: a gene whose common alleles are single SNPs and one defined partly by a
  structural event do not have the same callability requirement, and CYP2D6 has both inside one gene.
- **Deriving it from `callable_from`.** Starts by adding the more expensive of the two columns, and
  collapses two questions into one: deriving requiredness from the presence of a pointer is an axis
  overload.
- **A stamped, compiler-managed parquet column.** Nearly free under P9 and it cannot work — this is a
  curator's claim about what the annotation assumes, and a stamped column carries only what the compiler
  derives. There is nothing to compute.
- **Authoring the defining positions a second time in `variants.csv`.** Two tables then name one locus,
  the shadow rows move `artifact.digest` while asserting nothing new, and it re-opens *a star allele can
  be used without being defined* from the other end, with two definitions instead of none.

### Charter check

P3/P8 — new optional columns, additive, optional with respect to every published module. P5 — the home
question *is* the principle, and the answer is the table that names the locus the claim is about. P9 —
full cost on two authored tables, and the scoping decision is what keeps it from being three.

---

## RM71 — the alleles a drafted `genotype` stub must be written from are in no file

**Severity** medium · **Owner** enricher (`clinvar_draft`) + compiler (`draft`) · **Entry**
[ROADMAP_0_7.md § RM71](../ROADMAP_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file) ·
**Found by** dogfooding 2026-08-13, `reference_examples/hboc_palb2/`

### The problem

`draft-panel` leaves `genotype` as `vocab.TEMPLATE_PLACEHOLDER`, correctly — ClinVar publishes alleles,
not genotypes. The alleles the author must write the genotype *from* are in no file: a drafted row is
rsID-only, so `rs118203998` arrives with empty `ref`/`alts`, and the pair is stated once, in the warning
stream. At the 16 rows PALB2 yields at ClinVar's 3-star floor this is a transcription exercise; at the
**761** the same command drafts at the 2-star floor it is not one.

**And it is emitted exactly once.** The worklist is built inside `if report.added:` and scoped to
`added_records` — itself a correct earlier repair, since it used to name rows the model had refused and
rows already in the file. The consequence is that re-running `draft-panel` after the first draft adds
nothing and therefore prints **no worklist at all**, and `draft-panel` has no `--dry-run` (`draft` does).
The information cannot be re-requested from the command that produced it.

### The decision

**Make it re-requestable from the command that produced it.** Two changes, neither of which touches a
schema:

- **The worklist covers every stubbed row in the file**, not only the rows this run added. The
  `if report.added:` guard and the `added_records` scope are what make a second run silent; widening the
  worklist to the file's current placeholder rows keeps the earlier repair's benefit — refused rows and
  settled rows stay out — while removing the once-only property.
- **`draft-panel` gains the `--dry-run` that `draft` already has**, so the worklist is obtainable
  without appending anything. A flag that means the same thing in both commands, which is the standing
  rule.

This answers the entry's actual open question — *where does an author do this work* — with **in the
command they already ran**, rather than by inventing a third place. It changes no schema, fills no cell,
moves no digest, and re-answers a question the drafting run answered once.

### Repairs rejected

Every column-shaped repair, and the entry's own surviving candidate.

- **Writing `ref`/`alts` into the drafted row.** A provider fills identity whole or not at all, and the
  model forbids `ref`/`alts` without a coordinate — so this means writing the full coordinate, discarding
  the rsID identity the provider deliberately chose as stabler and more legible. `alts` is also
  `REDUNDANCY_BEARING`: the allele-membership check compares the author's genotype against it and keeps
  its force *because* the two were authored independently. Filling it makes the compiler compare ClinVar
  with ClinVar.
- **A comment column on `VariantRow`.** Full cost on the most expensive table, carrying text dead the
  moment the stub is replaced, and a provenance claim with no machine reader: "ClinVar publishes G>T" is
  a statement about a snapshot release, and a re-draft from a newer one leaves it naming the old alleles.
- **A sidecar the author reads beside the CSV.** Half cost and still wrong three ways: its only reader is
  a human, its join key either says nothing a `hint variant` call does not or contains the placeholder,
  and an unknown file in a spec directory is tolerated but not read, hashed or listed in `artifact.files`
  — so a worklist file becomes a permanent resident with one more name for `_check_misspelled_tables` to
  learn.
- **Having the enricher fill it after resolution.** Both cells are `REDUNDANCY_BEARING`, and filling a
  cell a Class-2 check cross-examines makes the comparison vacuous. The dependency also runs the other
  way: `enrich` refuses to load a file containing a placeholder, correctly.
- **Making `genotype` optional.** Barred by P8, and wrong at 1.0 too: the zygosity decision is what the
  stub protects.
- **A bulk read-only advisory command.** The entry's surviving candidate, and it puts the worklist in a
  *third* place while the author's complaint is that it is not in the one they are editing. The chosen
  repair is strictly smaller and lands the information where they already look.

### Charter check

P3 — a new flag and a widened report; no schema, no vocabulary, no manifest field. P7 — untouched,
since nothing authored changes.

---

## RM85 — the origin of a module predicts the shape of its second pass, and nothing records it

**Severity** low-medium · **Owner** enricher · **Entry**
[ROADMAP_0_7.md § RM85](../ROADMAP_0_7.md#rm85--the-origin-of-a-module-predicts-the-shape-of-its-second-pass-and-nothing-records-it)

### The problem

A module drafted from a source inherits that source's release cadence and needs a **source-refresh
pass**; a module built from one paper inherits the literature's cadence and needs an **evidence pass**.
Nothing tells an author their source has moved on. The tautology skip reads the release the module was
drafted from and `withdraw_stale_dataset` handles a module that ends up mixing two, but neither answers
*"ClinVar has published since you drafted this"*. `SourceRow.dataset` records the release, so the fact is
nearly there; what is missing is anything that acts on it.

### The decision

**An enricher check comparing `SourceRow.dataset` against the source's current release, reporting the
gap.** It needs the network, so it is an enricher check by the validation-ceiling rule, and it reads
rather than writes — which is what keeps it out of the column-shaped repair the entry refuses.

It is RM83's neighbour: the same *has the world moved* question, asked about the release label instead of
about the rows. With RM83's residue landing as a re-derivation that reports, the two compose — the label
check is the cheap one that runs offline-adjacent and tells an author whether the expensive one is worth
running.

**Tri-state, and `--offline` is where it bites.** Unreachable is not absent: a source whose current
release could not be fetched is `unchecked`, never *up to date*. Severity follows the mode, as every
enricher check does, and it reports rather than repairing.

### Repairs rejected

- **A column saying what this module was made from and what would age it.** Refused one table over in
  RM71, on the same grounds: it restates what `dataset` already states and rots where `dataset` is
  maintained — exactly the staleness `withdraw_stale_dataset` had to be built for, on a column where
  nothing could notice.
- **A publish-time or catalog-side signal.** Puts the notice where a reader is rather than where an
  author is, and is out of these packages' scope. Recorded as an ask rather than built.
- **Nothing, deliberately.** The status quo, defensible only while a module has one author who
  remembers, and it fails exactly when a module outlives its curator — which is the case the whole
  lifecycle document was written for.

### Charter check

P2 — the enricher is the only tier that may fetch, and the check lives there. P3 — a new check with a
new record member; the vocabulary member is additive. P9 — nothing authored, nothing derived stored.

---

## RM133 — a card subtitle has no amendable home

**Severity** low-medium · **Owner** format (+ registry, for their half) · **Entry**
[ROADMAP.md § RM133](../ROADMAP.md#rm133--a-card-subtitle-has-no-amendable-home-and-the-binding-is-not-where-that-gets-fixed) ·
**Motivating case** S64 (just-module-creator)

### The problem, and the half that is already closed

Measured by the reporter: editing `module.description` from 44 words to 11 moves **no**
`content_signature`, **no** `artifact.digest` and **no** fact signature — and drops the closure, because
`manifest.inputs` covers the raw bytes of `module_spec.yaml`. `README.md`, by a wide margin the longer
prose, is outside `inputs` and freely amendable. The shortest fixable prose in the system was the one
that could not be fixed.

**The binding stays as it is and that question is closed** — it is the reviewer's claim rather than the
artifact's, and a partition drawn along `content_signature`'s line would make a closure transferable
across a rename. Not re-proposed here. What is left is where a bounded `short_description` lives so that
it lands **amendable**.

### The decision

**Registry-owned, beside the module, following the standing authority-key precedent.**

- A `short_description` key joins the **registry-owned** family alongside
  `normalize.IDENTITY_AUTHORITY_KEYS` (`namespace`, `owner`, `canonical_id`) — as a **separate**
  frozenset, since ownership and presentation are different reasons for a key to be registry-owned, and
  stripped by the same function so there is one path rather than two.
- `strip_authority_keys` learns it, so a registry-injected value passes our validator and **never reaches
  the stored bytes**. `manifest.inputs` still matches, `verify_manifest` still passes, and the closure
  stands. Nothing about the binding moves, which is what makes this the route that actually unblocks the
  item.
- **The calibration ships as a constant on our side** rather than being guessed at downstream: ~**120
  characters**, against a measured 71 (comfortable) and 467 (the case that prompted it). A field that
  exists to fit a fixed layout is *specified* by that layout; it refuses nothing anyone has written, and
  absent it everything behaves as today.

### Repairs rejected

- **`short_description` on `ModuleInfo`.** Under the answered binding question every field in
  `module_spec.yaml` is on the un-amendable side, so this reproduces the defect in a new place. The
  reporter's own objection, and it is correct.
- **Splitting the binding along `content_signature`'s line.** Closed above; the two hashes cannot share a
  partition because they answer opposite questions about the same fields.
- **A field-aware six-field binding.** Recorded as the better form of the idea and still refused: it
  inherits the cost of hashing a *parse* of the yaml, and RM82 is the precedent that prices it — the last
  change to the binding turned on being a byte transform needing no loader, no parse and no schema
  knowledge.
- **Render-time truncation or folding.** Hides prose an author chose to write and leaves the spec wrong.
- **Anything retroactive to the seven published modules.** They met every requirement that existed.

### Charter check

P3 — a recognised registry-owned key and a published constant; no authored field, no schema change,
nothing invalidated. P4 — the binding is untouched, deliberately. P9 — zero cost on the authored layer,
which is the point of choosing this route over the natural-looking one.

---

# Filed by this round

Two items the decisions above created. Neither is 0.7 work.

- **RM135 — the `outranks` succession → the 1.0 cleanup tracker.** Retire `ProvenanceItem.outranks` in
  favour of a single mechanism in which the *existence* of an override in an authored table auto-beats
  the derived value. A removal, hence major-only under P3. 0.7 documents the succession and emits no
  deprecation warning, because the replacement does not yet cover `outranks`'s own case and a warning
  nobody can clear is noise rather than notice. Numbered rather than left as a prose note, because an
  unnumbered filing is one RM_TOC cannot index and nobody can find. Written into ROADMAP.md's 1.0
  cleanup tracker and indexed in RM_TOC in the same commit as this correction.
- **Nothing else.** The suppressed-row record was considered as its own item and folded into RM131
  instead: `manifest.compilation.warnings` already ships and sits outside the digest, so the home exists
  and a second one would be one more thing to keep in step.

**RM134 arrived during this round and is deliberately not sorted here.** It was filed 2026-08-28 from a
PubMind assessment written in parallel with these interviews, after the eleven-item scope was fixed, and
it is *assessed and designed, no code written* with its own full design document. Sorting it would mean
re-opening a scope the maintainer set; it belongs to the next round, and this line exists so that its
absence reads as a boundary rather than an oversight.

---

# Not taken, and the gate in each case

Nine items, each waiting on something that is not a decision this repo can make. Restated so the
deferral is a reason rather than an omission.

| Item | Gate |
| --- | --- |
| [RM122](../ROADMAP_0_7.md#rm122--the-measure-lookup-is-specified-and-nothing-anywhere-implements-it) — the measure lookup as a public function | **A caller.** The signature's open choices — one row or one per trait, `None` or a three-state result — are exactly what a first consumer implementing the lookup would settle. A leaf shipped against a hypothesis is one P3 keeps working forever. |
| [RM68](../ROADMAP_0_7.md#rm68--a-drafting-provider-on-a-non-grch38-module-refuse-or-strip-to-the-rsid) — drafting on a non-GRCh38 module | **A real author with a GRCh37 module saying which outcome they wanted.** Refusal makes such a module undraftable; stripping drops the 36 CPIC defining variants that have a position and no rsID. The warning shipped in 0.6. |
| [RM16](../ROADMAP_0_7.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest) — authored PRS weights | **A real consumer combining authored weights into a score.** Not derivable, so full cost, and a score's shape is exactly what a first case would dictate. |
| [RM56](../ROADMAP_0_7.md#rm56-policy-half--the-rule-for-a-measurement-that-spans-bins) (policy) — a measurement spanning bins | **Real caller output**, so the vocabulary is fixed against what callers emit rather than against a guess. |
| [RM65](../ROADMAP_0_7.md#rm65-implementation-half--repeat-and-copy-number-tables-are-positional) — coordinates on the positional repeat/CNV tables | **A real repeat-caller or CNV VCF.** Same gate as RM56. Would take RM43's coordinate lane from three tables to five. |
| [RM66](../ROADMAP_0_7.md#rm66--one-repeat-locus-several-motifs) — several motifs at one repeat locus | **Same gate as RM65**, and it is a keying change on a shipped table, the expensive kind. |
| [RM23](../ROADMAP_0_7.md#rm23--computational-predictor-scores-as-a-table) — predictor scores as a table | **Two blockers unmoved**: per-transcript grain, and the acquisition measurement. Licensing is not the blocker. |
| [RM28](../ROADMAP_0_7.md#rm28--meta-conclusions-the-predicate-half) — meta-conclusions, predicate half | **A corpus.** The injected-cofactor half dissolved on 2026-08-13; what is left is small and genuinely unsolved. |
| [RM67](../ROADMAP_0_7.md#rm67--polyploid-and-partially-phased-genotypes) — polyploid / partially-phased genotypes | **Not work** — a documented divergence, numbered so it is findable and not re-probed. |

**RM126 is the counter-example that makes the table honest**: it is in this document rather than this
table because it waits on nobody, which is what "owed rather than offered" means.

---

# Implementation plan

## Ordering

**RM124 is the keystone and goes first.** RM83's closure, RM130's sidecar and RM128's thinned promise all
hang off it, and its enricher docstring sweep belongs in its own commit rather than being scheduled
separately.

**RM126 is fully independent** and may run first or in parallel — it touches no file the other lanes
touch, and its release gate is the only piece that lands outside the packages.

| Lane | Items | Tier |
| --- | --- | --- |
| A | RM126 — record + `needs_recompile` + roster; the sweep; the release gate | format, compiler, release sequence |
| B | **RM124** — the overlay: model, apply, reverse, merge-not-clobber drop, docstring sweep | format, compiler, enricher |
| B1 | RM83 — the closure bookkeeping and `enrich --rederive` | enricher, docs |
| B2 | RM130 — the conflict table | enricher |
| C | RM128 — the transaction, `flock`, `progress` | enricher |
| D | RM131 — actionability, then codes; the suppression finding | compiler |
| E | RM132 — `PharmVariantRow.pmid` + both cross-check sites | format, compiler, enricher |
| F | RM70 — two `requires_callable` columns | format, compiler |
| G | RM71 — the widened worklist and `draft-panel --dry-run` | enricher, compiler |
| H | RM85 — the dataset-currency check | enricher |
| I | RM133 — the registry-owned key and the constant | format |

**B before B1 and B2**, by construction. **C before B1**, because `enrich --rederive` composes with the
transaction rather than reimplementing staging. **D before the suppression finding lands**, which is
inside D anyway.

## Shared-file hazards

- **`compiler/src/just_dna_compiler/compiler.py`** is touched by **B** (the overlay apply and the reverse
  half), **D** (roughly 29 warning append sites) and **E** (`_cross_check_literature`). Serialize these
  three; do not run them as parallel worktrees. Suggested order **B → D → E**, so the warning-site audit
  happens once the overlay's own findings exist and E's new citation site is classified when it is added
  rather than afterwards.
- **`enricher/src/just_dna_enricher/enrich.py`** is touched by **B** (writers and docstrings), **C** (the
  transaction) and **H** (the new check). **B → C → H.**
- **`schema/src/just_dna_format/normalize.py`** is **I** alone.
- **`manifest.py`** is touched by **A** (nothing — the record table is its own module) and **D** (the new
  result fields). No conflict.

## Standing requirements for every lane

- **A test per decision, not per file.** P7's round trip for the overlay (compile → reverse → compile,
  byte-identical, with the overlay applied twice proving idempotency); the resume path for RM128
  (a committed run equals an uninterrupted run); the interval union for RM126 (moved-and-moved-back
  still reads as moved, and a version against itself is empty).
- **Registry-iterating guards assert an equality over a walked set**, never a floor. The overlay's
  covered-table set, the warning codes and the authority-key family are all registries.
- **Every new warning phrase is pinned**, and the catalogue in COMPILER.md gains it in the same commit.
- **No count is computed and discarded**, and no check that cannot fail reports a zero.
- **Tri-state everywhere**: `unknown` for an uncovered interval, `unchecked` for an unreachable source,
  and `None` is never `False`.
- **Docs move with the code, in the same commit.** SCHEMAS for the overlay and the succession, COMPILER
  for the warnings channel and the citation site, ENRICHER for the transaction and the checks,
  MODULE_LIFECYCLE § 6.3 for what deleting a sidecar now costs (nothing), and CHANGELOG under the 0.7
  heading.
- **The `/create-module` skill** gains the overlay and the `draft-panel --dry-run` flag; its command
  tables rot silently, so re-run `--help` against them.

---

# Provenance

Decided across four interview rounds with the maintainer on 2026-08-27/28, on the `0.7` branch, against
the full text of [CONSTITUTION.md](../CONSTITUTION.md) and the complete roadmap entries for all eleven
items.

Four things changed during the interview rather than being carried in from the entries, and each is
recorded above where it applies: **RM83 dissolved** into RM124 once derived tables became pure build
products; **RM128's central ask dissolved** the same way, into a transaction that keeps the promise
instead of trading it; **the metainfo artifact was not filed**, because `manifest.compilation.warnings`
already ships outside the digest; and **the `outranks` overlap became a dated succession** rather than
either a merge or an unstated duplication.
