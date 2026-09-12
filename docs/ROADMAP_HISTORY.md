# Roadmap history — the items that shipped

Split out of [ROADMAP.md](ROADMAP.md), which is **forward-only**: it now carries active work and
nothing else. This file keeps the *rationale* of every `RMn` that shipped from the 0.6 line onward —
and, since 2026-08-21, of the ones **closed by a decision not to do them**, which leave the active
file for the same reason and are just as worth not re-deriving —
the earlier ones are in the archive named below — because a lot of it is reasoning worth not
re-deriving, including one entry that corrects an argument it originally made.

- **[CHANGELOG.md](CHANGELOG.md)** is the release record: what changed, newest first, shared across
  the ecosystem repos. This file is the roadmap-item view of the same events.
- **[RM_TOC.md](RM_TOC.md)** is the complete index of every `RMn`, active and shipped.
- **[COMPILER.md](COMPILER.md)** carries the per-feature coverage table.

`RM1`, `RM2`, `RM3`, `RM8`, `RM9`, `RM18` and `RM19` also shipped, but their entries live in
[USE_CASES.md § Roadmap items surfaced](USE_CASES.md#roadmap-items-surfaced) — where they were
derived — and were never duplicated here.

**The 0.5 line and everything before it moved to
[ROADMAP_HISTORY_PRE_0_6.md](history/ROADMAP_HISTORY_PRE_0_6.md)** on 2026-08-17 — the release narratives
through 0.5.0, and every `RMn` that shipped before 0.6.

**The 0.6 line moved to [ROADMAP_HISTORY_0_6.md](history/ROADMAP_HISTORY_0_6.md)** on 2026-09-12,
when 0.7.0 was cut and published — every `RMn` that shipped in a 0.6 number, and the rounds that
produced them. This file starts at the 0.7 build round. The boundary is the `v0.6.6` tag read off
`git show`, never a date: three rounds dated 2026-08-21 shipped in 0.7.0 rather than in 0.6.6.
[RM_TOC.md](RM_TOC.md) indexes all three halves plus the open roadmap, so it is where to look an item
up.




# The 0.7 build round

The items [PROPOSAL_0_7.md](proposals/PROPOSAL_0_7.md) decided on 2026-08-27/28 and the 0.7 batch then
built. Every one is additive under Principles 3 and 8; what is kept here is each entry's reasoning,
including the repairs it refused, which is the half that would otherwise be re-derived.

**The round's twelve are all here as of 2026-08-31**, which is when the last four entries left the
forward-only files they had been sitting in with a `SHIPPED` banner on them: RM126 and RM71 from
`ROADMAP_0_7.md`, RM133 and RM134 from [ROADMAP.md](ROADMAP.md). An entry marked shipped in a file that
describes what is *not* built reads as late rather than done, which is the state this move ends. The
deferral round those two came from closed at the same time —
[history/ROADMAP_0_7.md](history/ROADMAP_0_7.md) keeps it, and everything still waiting moved to
[ROADMAP_0_8.md](ROADMAP_0_8.md). RM83 is in this file as **closed, not shipped**, and RM139 was filed
by the cut itself rather than by the proposal.

**RM140 joined them on 2026-08-31 from a consumer report, after the round had closed.** It is not one
of the twelve and does not reopen the thread; it lands inside the same uncut `0.7.0`, because a new
optional column is what sizes a release and the number was already decided.
[PROPOSAL_0_7.md](proposals/PROPOSAL_0_7.md) carries its decision as a dated addendum, in the file's own
idiom, so the reasoning sits beside the twelve rather than in a thread of its own.

**And a second round joined the same uncut release on 2026-09-01: the source-adoption batch,
RM163–RM168.** Six items filed out of one sweep, every one gated on a probe that had not been run;
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) is its record. It is a *round* rather than an
addendum — six items decided together against a shared sort rule — which is why it has its own file
rather than joining RM140 and RM152 as a third dated note on the first thread. Five of the six build
here and RM164 parks on a measured negative, having spun off RM171. What the round is worth remembering
for is not any one adoption: **five of the six entries said something their own probe contradicted**,
and then four of the six verdicts the proposal drafted were overturned again in the maintainer pass —
so an unprobed entry is a question, and a probed one is still only a proposal.

**The round closed the same day it was decided**, which is the third drift and the one worth counting:
of the five items built, **four contradicted their own entry again during the build**. RM165's entry
proposed drafting four columns `RepeatAlleleRow` does not have. RM167's three headline measurements did
not reproduce — a gene-node count that conflated two id shapes, a locus count off by 34, and an id
grammar contradicted by the example printed beside it. RM163 offered `overrides.csv` as the author's
remedy for a finding the overlay cannot reach. RM166's licence motivation was already gone before the
build began. **RM168 is the only one of the six that held**, and it is the one whose questions were
cheapest to ask — a directory listing and a 1.1 MB download.

So the three-stage pattern is: an entry states what it believes, a probe contradicts it, a decision
overturns the probe's verdict, and a build contradicts the entry again. Each stage was cheaper than the
one before, and each caught something the previous one asserted. That is an argument for probing early
and for writing entries that can be contradicted, not for trusting any of the four stages on its own.

## RM234 — `AcmgReport.clean` answered `True` about a comparison that never happened

**Severity** medium · **Status** ✅ **shipped 2026-09-12 in the uncut 0.7 line**, enricher only — no
parquet, model or manifest field changes · **Owner** enricher · **Motivating case** S100
(just-module-creator), wrapping `check-acmg` as an MCP tool against enricher 0.7.0 from PyPI

`clean` was `not self.mismatches`, and `mismatches` selects the verdicts `not_listed` and `denied`. A
run that obtained no SF list gives every row the verdict `unchecked`, so `mismatches` was empty and
`clean` returned **`True`** — a run that compared nothing reporting as a run in which everything
agreed. Reproduced with every cache lane blanked:

```
version=None  checked=0  clean=True     # no list consulted
version=3.3   checked=13 clean=True     # 13 rows compared, all agree
```

The two `True`s mean entirely different things, and `if report.clean:` takes the first for a pass.
That is the check-that-cannot-fail shape (`@tautology-zero`), one layer under S54's title-as-quote and
one layer over S86's "current out of nothing".

**The attestation was already right, which is what made this findable and what shaped the fix.**
`verification_record` has always returned a `skipped` record on both arms — `"offline"` when no list
was obtained, `"nothing_to_check"` when one was obtained that no row could be looked up in — so the
persisted record never claimed a pass while the in-memory property did. The repair is therefore not a
second condition beside it: `not_consulted` names the arm or `None`, `clean` withholds where it is
set, and `verification_record` reads the same property. The two answer the same question by
construction, and a test asserts that equality across all five arms rather than checking either alone
(`@answered-is-not-absent` — a verdict function with several arms owes a reason function with the same
arms).

**`None`, never `False`.** Returning `False` would say the module disagrees with a list nobody read,
which is the report-the-negation move the house algebra refuses; withholding is the third state. The
reporter proposed both shapes and named this one as matching the rest of the toolchain.

**Behaviour change for callers.** `None` is falsy, so `if report.clean:` was already correct and stays
correct — it is the spelling the CLI's green line uses, and its `and report.version` guard is now
redundant and gone. `if not report.clean:` newly fires on an unconsulted run, which is the point.
`check-acmg --strict` gates on `mismatches` and never on `clean`, so no offline run newly refuses.

**One existing test was pinning the defect.** `test_offline_without_a_snapshot_is_still_unchecked_not_
absent` asserted `report.clean` on an all-`unchecked` run. Unchecked-not-absent is a real property and
the verdict list is what carries it; the `clean` line was the bug, asserted. It now reads
`report.clean is None`.

**The same shape sits one module over and is worse** — see RM235, filed from this investigation rather
than found by the reporter.

· *from* S100 (just-module-creator) · *related* RM235, RM72, RM94

## RM233 — `main` was red on two jobs and green on every local run, and the difference was a colour code

**Severity** medium · **Status** ✅ **shipped 2026-09-12**, test infrastructure only — no package
version moves, nothing in a shipped surface changes · **Owner** enricher tests + the suite root ·
**Motivating case** CI run 34703638770 at `2001215`, the tip of `main`

Two tests failed on both Python jobs while `uv run pytest` was green locally: 2 failed, 4571 passed.
Neither failure was about what it named.

`test_the_flag_the_refusal_names_exists_on_the_command` asserted `"--use" in result.output` over
Typer's `--help`, and Typer renders through rich, which decides colour from the environment. A GitHub
runner gets it; a non-tty local shell does not. With colour on, rich styles the two dashes as their own
span, so the flag is emitted as `\x1b[1;36m-\x1b[0m\x1b[1;36m-use\x1b[0m` and the assertion is false
for a flag that is right there in the text — reported as a command missing a flag it declares.
Reproduced locally with `FORCE_COLOR=1`, which is the whole environment difference.

`test_a_source_path_that_does_not_exist_is_refused_before_anything_downloads` asserted
`"nothing will fetch it"`, and that one is **not** environment-dependent at all: Typer's error box is
drawn at a width `click.testing.CliRunner` pins inside `invoke()`, so a sentence longer than the box is
broken across lines with `│` and padding in the middle. It had been passing through a local
`_unwrapped()` helper that collapsed the box — and *that* is how the two became one item.

**The repair is split because the causes are, and one of the two exits was measured shut.** Colour is
pinned once for the suite: a root `conftest.py` sets `TERM=dumb`, which is the value that fixes both
halves of rich's styling where `NO_COLOR=1` fixes only one and `FORCE_COLOR` outranks it anyway.
`COLUMNS` was in the first draft beside it and is deliberately **not** there now: `CliRunner` pins its
own width, so no environment variable can widen the box, and a line that looks like it addresses the
wrapping while doing nothing is worse than its absence. Wrapping is handled where it can be, at the
match: `_unwrapped` moves into `enricher/tests/conftest.py` as `cli_text`, exposed as a fixture because
`--import-mode=importlib` means a conftest is not importable by name.

**The transferable half is the private name.** A normalizer for exactly this existed, in
`test_cache_lanes.py`, called `_unwrapped`, and the second site that needed it could not find it —
wrote `in result.output`, and was the test that went red
(`@roster-is-as-wide-as-the-tables-it-reads`: *grep for the question, not the bug; a private name keeps
the second caller from finding the first*).
It also only ever collapsed box drawing, never escapes, which is why it survived colour and the raw
assertion beside it did not. `cli_text` strips both and reads `stderr` as well as `stdout`, since Typer
writes a `BadParameter` to stderr and a helper over `result.output` alone matches nothing for exactly
the errors worth asserting on.

**Scope, measured rather than assumed:** 491 tests across 18 files invoke a CLI, and exactly two were
affected — the other 489 pass on the luck of matching a token rich does not split, inside a phrase short
enough not to wrap. That is why the colour pin is central rather than per-test: the next one would
otherwise be found the same way, by a red `main` on a green local run.

`enricher/tests/test_cli_rendering.py` is the guard, and it asserts the property rather than the
mechanism — no escape codes in rendered output, a flag name survives whole, and a wrapped diagnostic is
matchable through `cli_text` **and not through `result.output`**, so the day the box stops wrapping the
helper's reason is reported rather than left standing. Both halves were demonstrated failing first: the
flag under `FORCE_COLOR=1`, the phrase in any environment.

## RM232 — a drafted row lands before its licence row, and the seam RM231 built does not reach the compiler's writer

**Severity** high · **Status** ✅ **landed 2026-09-12, past the `v0.7.0` tag** — the cut went in at
`83b1674` while this was being built, so it is the first item of the next release rather than part of
0.7.0. **The number is the maintainer's and CHANGELOG carries both readings**: no parquet, no
signature, no model and no manifest field (the test 0.5.2 used to take a patch), against a public
compiler function growing an optional parameter (additive, so a minor). Not decided here · **Owner**
compiler + enricher · **Motivating case** the two exemptions RM231 had to name

RM231 folded each enrichment pass's licence row into its data table's commit, so eight passes can no
longer write a table and then fail to record what licensed it. Its guard is a roster equality, and to
close that roster it had to name five exemptions. **Two of them are this item**, and they are S98's
shape one layer over rather than a different problem:

- `civic_citations.draft_civic_citations` gates `merge_sources_file` on `result.added`.
- `drafting.record_draft_provenance` gates `record_source_terms` on `covered` — the scaffold's
  recorder, reached by `civic_draft`, `mitomap_draft`, `pgx_draft`, `strchive_draft` and
  `clinpgx_draft`.

Both are true only **after** the compiler's `draft.append_rows` / `append_partial_rows` has already
renamed the drafted rows into place. A refused merge — a scaffold's `<<REPLACE>>` placeholder in
`licensing.csv` is enough, which is the S98 trigger and needs no corrupt file — therefore leaves
drafted rows in the author's own tables with no licence record. `sources.csv` is the only file the
compile gate reads, so a CPIC-drafted module in that state has no no-sale clause to refuse on.

**Why RM231's seam does not already cover it.** `layout.atomic_writer`'s `before_commit` binds one
callback to one rename. A drafter appends to **several** tables — `pgx_draft` writes `haplotypes.csv`,
`allele_function.csv` and `diplotypes.csv` in three separate `append_rows` calls, each its own atomic
commit — so there is no single rename to hang the licence merge on. The compiler's writer never took
the parameter, and the enricher cannot reach past it.

**The fix, and the two repairs that are wrong.** `append_rows` and `append_partial_rows` grow the same
optional `before_commit` kwarg, threaded to all three `atomic_writer` sites, and every drafter passes a
licence-commit closure factored out of `record_draft_provenance` so there is one body and not a second
copy of RM228's decision. The callback then fires **per file that actually writes**, which is the
correct grain: `append_rows` enters the writer only when it has rows to add, so the callback fires
exactly when a licence row becomes owed for that table, and `merge_sources_file` being never-clobber
makes N firings write one row.

- *Hoisting the merge ahead of the first append is wrong.* `covered` is `added` or `already_present`,
  and the outcome vocabulary also has `differs`, `appended_unkeyed` and `invalid` — so a run whose rows
  all `differ` covers nothing and must write no row (`@write-the-sourcerow`'s converse, S77/RM142).
  That cannot be known before the append is attempted.
- *Binding it to the first or the last append only is wrong.* Last-only leaves tables 1..N-1 committed
  unlicensed if the merge fails there; first-only misses a run whose first table is all-`differs` and
  whose second adds.

`record_draft_provenance` stays at the tail and keeps all three of its jobs: the `already_present`-only
run covers something, fires no callback, and still owes the row; `withdraw_stale_dataset` needs
`drafted` computed over every report; the projection restamp is `kind`-driven. RM228 exists because
those were once split.

**The residual is stated rather than closed**, the same one RM231 accepted: a rename that fails after
its `before_commit` has returned leaves the licence row without that table. Conservative, and the
`OSError` says what landed. Two files are two renames.

**Filed at discovery, before the fix was approved** — recorded here because the previous state of this
gap was two honest exemption reasons in `enricher/tests/test_licence_row_inside_the_commit.py` and
nothing in this file, and the release check is *no open RMs, all green*. A defect a test documents is
not a defect the release gate can see. · *from* the RM231 handover · *related* RM231, RM228, RM222,
RM142

**What shipped.** `append_rows` and `append_partial_rows` take `before_commit`, threaded to all three
of their `atomic_writer` sites; `drafting.licence_commit` is the merge half of
`record_draft_provenance` as a closure factory, so there is one body and the drafters hand the same
callable to every append they make. `record_draft_provenance` calls that body itself at the tail, for
the run that covered something and wrote nothing, and keeps the stale-label withdrawal and the
projection restamp — both are answers about the run rather than about one table. The pre-flight sits
inside the factory rather than in each drafter, so a new provider inherits it.

**The guard is an equality from both ends.** RM231's roster grows from eight to nine (`civic_citations`
stops being an exemption), the two closures are named as *being* the callback, and a new walk asserts
that **every** `append_*` call under `just_dna_enricher` carries a `before_commit` — 11 of them, all 11
unbound before this change and all 11 bound after. The AST helper had to learn the difference between a
function's own calls and a nested `def`'s: without it, a pass that did exactly what was asked read as a
bare recorder, and a callback defined and never passed would have read as safe.

**Two behaviour-preserving hoists were needed and are noted where they landed.** `clinvar_draft` and
`pubmind_draft` read their release label at the tail, and `clinpgx_draft` read its licence text there;
the row's contents have to be known before the first write, so the pure reads moved up and the warnings
each can raise stayed exactly where they were, gated as they were.

## RM231 — `alphagenome expression` wrote the data, then failed to record its licence, and called that FAILED

**Severity** high · **Status** ✅ shipped 2026-09-12 in the uncut 0.7.0 (`just-dna-format`: one
keyword on `layout.atomic_writer`; `just-dna-enricher`: one strict reader factored out of the merge,
eight pass tails moved inside their table's commit, one AST guard; no schema change) · **Owner**
enricher · **Motivating case** S98 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md), a
freshly scaffolded APOE module and the guide's own first AlphaGenome command

**What it reproduced, and why the severity is high.** `_write_csv` then `merge_sources_file`, two
steps; a scaffold's `licensing.csv` carrying `<<REPLACE>>` made the second refuse. On disk: 12,003
rows of `commercial_use=False` Atlas output and no licence record anywhere. On screen: `EXPRESSION
FAILED`. The compile gate keys on the licence table and nothing else, so the orphaned rows did not
merely lack provenance — they compiled clean, as though unrestricted. A module that should be
refused became one that is not; that is a licensing hole, not an untidy write. And scaffold →
expression is the default happy path, so it landed there every time.

**It was eight passes, not one.** Grepping every writer (`@sidecar-name-and-place`'s own rule) found
`enrich`, `assertions`, `gene_metrics`, `frequencies`, `gene_validity`, `gwas`, `clingen` and
`expression` with the same tail, each written independently; the eighth's author had read
`@enrich-is-a-transaction` while writing it and still split the two, because the licence row did not
read as part of the table. It is, and the fix is one primitive rather than eight edits of opinion.

**The seam, and the two candidates it beat.** `layout.atomic_writer(before_commit=…)` runs the
callback after the temp file is closed and fsynced and before the rename. The merge refusing removes
the temp; a table that fails to serialize never reaches the merge; neither file exists without the
other. The consumer's first candidate, *write the licence row first* — small, idempotent, harmless
in one direction — was refused because it is not harmless in the other: a row for a pass that then
contributed nothing is the S77/RM142 false statement in a published artifact, and
`@write-the-sourcerow`'s converse forbids it. Their second, *validate up front*, is taken as well
(`require_sources_file`, the strict read factored out of the merge and run before the fetch, so a
placeholder fails in a second instead of after a 47-minute query) and is not sufficient, as they
said: a concurrent writer or a full disk between the two writes reopens the window the seam closes.
The `if write and result.written` gate is unchanged — a dry run and an empty match write neither file.

**The residual is stated rather than hidden.** Two files are two renames, and no callback ordering
makes them one: the table's rename failing after the licence row's has returned leaves the row for
data that never arrived. Conservative, and the `OSError` raised then names what landed — the
consumer's closing ask, that a partial commit say what it committed, answered in the one case that is
left. Pinned with a monkeypatched `os.replace`.

**The guard is an equality over a walked set, and it names a gap it cannot close.** Every function
under `just_dna_enricher` that records a licence row either passes the merge as `before_commit` and
pre-reads the table, or is listed exempt with its reason. Two of the five exemptions are the same
defect one layer over: `drafting.record_draft_provenance` and `civic_citations.draft_civic_citations`
record the row after the compiler's `draft.append_*` has landed the drafted rows, and the seam that
would reach them is the compiler's draft writer — RM228's surface, handed to its owner rather than
folded in here. A guard that names a known gap with its reason is honest; one that cannot see it is not.

## RM230 — a leak an exemption hid, a remedy no flag could reach, and a debt that was not owed

**Severity** high · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 · **Owner** enricher ·
**Motivating case** the last three items of the 2026-09-11 re-derivation's enricher tail (C3, 7.6(a))
plus the debt RM228 recorded against itself

**C3 — `EuropePmcClient.lookup` leaked all three legs, and the exemption that hid it was argued per
method.** `lookup` called `_get` bare and then `.json()` on the result, so a persistent 503 escaped as
`httpx.HTTPStatusError`, a refused connection as `httpx.ConnectError`, and a 200 that is not JSON as
`json.JSONDecodeError` — the exact fourth leg `test_client_exception_contract.py` exists for. Where it
lands is what makes it high: `enrich_literature` calls this inside a `try:` whose only companion is
`finally:`, verbatim the shape `test_pass_exception_contract.py` was written to refuse, and that
suite's stub raises earlier on the eutils call so the leg was never driven.

**The class sat in the contract suite's `exempt` set behind a note reading "`EuropePmcClient.fulltext`
is deliberately *not* a leak".** That is true of `fulltext`, which catches httpx and returns `None`
— the tri-state withhold. **An exemption is per class and that justification was per method**, so it
silently exempted a sibling nobody had looked at. This is the RM101/RM208 blind spot in a third form:
first a roster's `exempt` set, then a guard inheriting the roster's exemptions, now an exemption whose
*reason* is narrower than its *scope*. The note now says to argue from what the class promises.

Removing it exposed a second limitation: `covered` was keyed on the **module**, so it could not say
that one `literature` client is covered while two remain exempt — it would have marked all three
covered. A per-class `covered_classes` set is named explicitly beside it.

**7.6(a) — the compile named a remedy that did not exist, and the trap is live.**
`identifiers._pgs_source_rows` built every PGS row with `declared_use="unstated"`, hardcoded. The
`academic_research_only` class is `ScoreRights(commercial_use=False)` at the `annotation` layer, which
is exactly where `taints_commercial_use` reads — so the compile refused, saying *"Re-run the enricher
with a declared use (`--use non-commercial`)"*, and `check-identifiers` had no `--use` option.
`merge_sources_csv` is never-clobber, so a re-run could not correct the cell either: the only exit was
a hand edit. A refusal naming an unreachable remedy is worse than one naming none, because it sends an
operator to a flag they cannot find and implies they mistyped it.

The audit left "does any live score classify that way" undetermined from code, so it was **measured**:
`GET /rest/score/all?limit=250` on 2026-09-11 returned three distinct licence strings, and **6 of
those 250** matched the phrase — PGS000013 through PGS000017 among them. Reachable, not latent, which
is what decided it got a flag rather than a note. The hyphenated spelling the refusal prints is pinned
in a test, because the vocabulary member is `non_commercial` and it only works through
`check_vocab`'s separator normalization (`@vocab-separator-slip`).

**The debt RM228 recorded against itself, disproved by writing the test first.** That entry said
`clinvar_draft` and `pubmind_draft` write their licence row on any non-dry run — the shape RM222 found
wrong in `civic_draft` — and owed a fix. They do not: **both return early**, at "nothing matched; no
rows drafted", *before* the licence write, so the property holds upstream of the gate and `covered=True`
is correct for each. Measured: a `--gene` filter matching nothing ends with `reports == []` and an
empty spec directory. The test that would have proved the bug passes unchanged, and that is the
finding. It is kept as a pin on the **early return** — the thing actually holding the rule, which
nothing else asserted — so deleting it as redundant, or reordering the licence write above it, fails
loudly rather than shipping the RM222 defect into two more providers. RM228's entry and ENRICHER.md
are corrected rather than left claiming a debt that does not exist.
`@client-exception-contract` · `@write-the-sourcerow`

## RM228 — drafting was seven grassroots implementations of one mechanism

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 · **Owner** enricher ·
**Motivating case** the long-tail triage of the 2026-09-11 re-derivation (enricher 8.10 #3–#9), where
the maintainer's read was that drafting "was created bottom-up and lacks structure — this is a clear
sign", and the repair was scoped as a scaffold rather than as four patches

Seven `*_draft.py` providers turn a snapshot into authored rows. They grew one at a time, and by 0.7
each carried its own copy of the same four decisions. The copies had drifted:

- **`clinpgx_draft` and `pgx_draft` recorded a `dataset` and never withdrew a stale one.** A module
  widened from a newer CPIC or ClinPGx release kept a licence row naming the older one — `merge_sources_file`
  is never-clobber, which protects a curator's terms and turns the release label into a false claim.
  Every other snapshot-drafting provider already withdrew.
- **`pubmind_draft` imported `clinvar_draft._MATCH_ON` across modules**, coupling two providers'
  lap-2 matching through a private constant.
- **`civic_draft` consumed pydantic's rendered error message as an API**, branching on
  `"identifier" in message or "positional" in message or "chrom" in message`.
- **`DRAFT_PROJECTIONS` was a hand-kept copy of the drafters' `match_on`** — its own comment pointed
  at `clinvar_draft._MATCH_ON` by name.

**The measurement that shaped the repair, and refuted the obvious fix.** Four providers restated the
model's skip rule and two derived it, so "migrate everyone onto the derived one" is the instinct. It
is wrong: `authoring_requirements("variants.csv")` answers `any_of: [['rsid'], ['chrom','start']]`, a
grammar that **cannot express** `VariantRow`'s third clause — *`ref`/`alts` require `chrom` and
`start`*. The derived implementation therefore accepts `{"rsid": "rs1", "alts": "G"}`, a partial
coordinate the model refuses and a compile would refuse (`@identity-whole-or-none`). The one provider
that looked correct was derived from a subset, and migrating the others onto it would have spread the
defect. **Constructing the model is the oracle** — the only complete one, and the one compile uses.
`authoring_requirements` answers the human-readable *which cells are missing* and is not the verdict.
That also deletes the message parsing: with every non-identity field pre-filled from values the model
accepts, any `ValidationError` reaching the probe **is** an identity refusal.

**The split the scaffold enforces.** A skip rule is two rules: the **model's requirement**, derived
and identical everywhere, and the **source's precondition**, a true fact about that snapshot declared
with a reason. Mashed into one list they are indistinguishable — which is the state `mitomap_draft`'s
`clin_sig` clause was in. It gates *identity* on a column the model does not require, and it turned
out **correct**: a `rated_miss` carries one by construction, and the guard buys a named refusal rather
than a raw `ValidationError` about a column the author never wrote (`@specific-rejection`). The reason
sat three lines below in a comment, so a legitimate constraint and a genuine misread read the same.
`SourcePrecondition.reason` is a field and a missing one fails at construction. **This item predicted
mitomap would be its one behaviour change and it was not** — the prediction was wrong, and the
structure is what made the difference legible.

**The import cycle was the diagnosis, not an obstacle.** Deriving `DRAFT_PROJECTIONS` created a cycle
the moment the scaffold needed `stamp_draft_digest`. That revealed `draft_digest`,
`stamp_draft_digest` and `drafted_unchanged` had been drafting code sitting in `provenance.py` all
along — a boundary only holdable while the registry was a copy. `drafting` now owns the registry, the
derived projections and the whole drafted-value axis; `provenance` keeps the `DraftProjection`
dataclass and imports nothing back.

**`record_source_terms` gained `license_texts`**, the same shape RM222 gave `datasets` one axis over.
`SourceTerms.row` had always accepted one and this function had no way to pass it, so the two PGx
drafters that extract a licence file had to build rows by hand — and were therefore outside every
other guarantee it gives, including the withdrawal they were missing.

**Enforcement is both kinds, because they catch different evasions.** `test_drafting_scaffold.py`
asserts the registry equals the `*_draft.py` modules on disk, and walks each module's AST to refuse a
hand-listed identity column (off `base.IDENTITY_FIELDS`, so it inherits the schema's answer) or a
direct `merge_sources_file`/`withdraw_stale_dataset`/`record_source_terms` call. All 18 fail on every
one of the seven pre-migration.

**Deliberately not unified**, because either would change behaviour under cover of a refactor: each
provider's *covered* predicate, and the stale-label wording — two providers ship two sentences and a
published warning is an API (`@warning-text-is-api`).

**A debt this entry recorded and then disproved.** It said `clinvar_draft` and `pubmind_draft` write
their licence row on any non-dry run — the shape RM222 found wrong in `civic_draft` — and owed a fix.
Writing the test first refuted it: **both return early**, at "nothing matched; no rows drafted",
*before* the licence write is reached, so the unconditional-looking gate is guarded upstream and
`covered=True` is correct for both. The test that would have proved the bug passes unchanged, which is
the finding. It is kept as a pin on the early return — the thing actually holding the property, which
nothing else asserted — so removing it as redundant, or reordering the licence write above it, fails
loudly instead of shipping the RM222 defect into two more providers. `@drafting-scaffold`

## RM229 — `CacheLane` declared no size, so an onboarding offer had to `du` a box to price one

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: one
field on `CacheLane` filled for every lane, one field on `LaneStatus`, two functions, one number on a
rendered line; no schema change) · **Owner** enricher · **Motivating case** S97 (just-module-creator,
in CONSUMER_SUGGESTIONS_HISTORY.md), building a first-run offer to provision the locally-built lanes

**What it reproduced.** `CacheLane` carried everything about *whether* and *how* and nothing about
*how much*, so the consumer `du`'d a provisioned box and kept the table as a dated constant — the
hand-kept list RM176 retired for names, kept for a number that drifts faster, and one that cannot say
whether it is stale. Their measurement agreed with this box's to the megabyte.

**Taken: their option (1), with the canary that makes a declared number honest.** `approx_mb` is an
order of magnitude in whole megabytes, rounded up, `1` meaning *at most a megabyte*; `None` stays
legal and means *nobody measured*, which is the answer they wanted to be able to report. A declared
size is a counted-prose shape — it rots — so the test re-measures every lane present on the machine
it runs on and refuses a declared number more than an order of magnitude off. That is the difference
between this field and their constant: theirs could not tell a caller it was stale, this one fails a
developer's suite when it is. Option (2), the size in `release.json`, is half taken the cheaper way:
`LaneStatus.size_bytes` measures a present lane from the bytes rather than from a record a builder
would have to write, and `cache status` prints it. Option (3), a `Content-Length` probe, was not asked
for and is not taken: a network call to price a prompt.

**The other half is a cost fact wearing a correctness field.** `parents` reads as *which digests get
recorded*, and the consumer found it is also *what a blank box pays*: `mitomap_miss` is under a
megabyte and its parents are a ClinVar download. `provisioning_closure(lane)` walks it transitively
in registry order, parents first — the sum they had hand-written — and the field's docstring and
ENRICHER say so.

**What they got right and did not need us for.** Classifying `acmg` by calling `prepare_lane` and
reading the refusal, rather than pattern-matching a `<…>` placeholder in `build_command`, is the
intended reading: the route depends on the install, not the lane, and only the adapter knows.

## RM225 — four stale claims a reader acts on, and the closedness one had drifted three times

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 · **Owner** format ·
**Motivating case** the long-tail triage of the 2026-09-11 re-derivation's schema candidates (D3, D4,
D8, D9), walked item by item with the maintainer rather than batch-closed

Four candidates that a first pass reads as nits. Each turned out to be a sentence a reader would act
on, and one of them had been written wrong in three separate places.

**D3 — `actionability` is closed, and three places said otherwise.** `VariantRow.actionability`
shipped in 0.4.0 and `_validate_actionability` is `check_vocab(...)`, a closed-vocabulary rejection.
Against that: `vocab.py`'s comment said "the field is not built yet, so this is not enforced";
`base.vocabulary`'s **own docstring** — the helper that defines what `closed` means — listed the set
among the `closed=False` recommended-but-open ones; and `reference.py` had already filed the axis
under `open_recommended` in an earlier incident it still carries a note about. The constant's name
carried it too: `_SEED` reads as "suggestions you may extend", which is what the validator refuses.
Renamed to `VALID_ACTIONABILITY` with `ACTIONABILITY_SEED` kept as a working derived alias (P3), all
three sentences corrected, and the SCHEMAS roster gains the row — where RM217's existing guard caught
the rename within seconds, which is what that guard is for.

**D4 — a dead constant that was not dead, it was unwired.** `CANONICAL_MT_REFERENCE_SEQUENCES` is
referenced nowhere in any tier, and the obvious reading is to delete it. The comment one line above
explains why nothing enforces it — "not a closed allow-list (future refs exist), the validator rejects
only this enumerated landmine" — and that is correct: an allow-list would refuse a legitimate future
rCRS revision. But the refusal beside it ends `use NC_012920.1` as a **literal**, restating the value
the constant exists to hold. So the set had one real job and was not doing it. The message now
interpolates it; the published text is byte-identical (`@warning-text-is-api`), and deleting the
constant would have left the literal behind.

**D8 — a comment naming the wrong counterexample, twice.** `pgx.py` says, at two sites, "unlike
`VariantRow.chrom`/`StudyRow.chrom`, these two models run no chrom validator". Measured:
`StudyRow.chrom` has **no validator and no vocabulary marker**. `VariantRow` is the only one of the
five models declaring `chrom` that validates. The asymmetry itself is deliberate and correctly
documented — the marker is withheld precisely because nothing rejects, which is the drift D3 is about
— so the fix is the counterexample, not the design. Measured across the corpus: 709 `chrom` cells, 3
non-canonical, all of them in the one table that normalizes. Latent, not live.

**D9 — a docstring promising a tri-state the signature cannot express.**
`is_multi_valued_number` returns a bare `bool` and its docstring closed with "withhold, never negate,
and never accuse". Checked every caller before touching it, as asked: there is exactly one
(`compiler._vcf_pointer_warnings`), it is `if is_multi_valued_number(number):` gating whether to
*raise* a warning, so `False` on an unknown cardinality **is** the withhold — warning there would be
the accusation the sentence forbids. The narrowing is correct at the point where it happens; the
sentence was the defect. Docstring now says why the collapse is the contract, and what a future
caller needing the distinction must do instead.

**The guard is the deliverable.** Fixing four sentences fixes four instances;
`test_closedness_is_measured_not_declared.py` is the class. It **measures** each marked field's
closedness by handing its validator a certain non-member, and compares that against the flag the
marker publishes — nothing in it reads a comment, a name or a document. A second test walks the
constant names out of `base.vocabulary`'s docstring and measures each: run against the pre-fix text
it reports `ACTIONABILITY_SEED (closed on VariantRow.actionability)`, which is instance #3, the one
no tool could have caught because the marker was right and only the prose was wrong.

**Recorded twice over:** the grep guard failed on its own author's first run, because the replacement
comment explains the defect by quoting the stale claim verbatim — the same trap RM218 hit. It now
requires an occurrence to be wrapped in `used to say "…"`, and the lesson is in its docstring: write
the guard before the replacement prose. `@registry-completeness` · `@field-description-is-a-claim`

## RM224 — `sidecar_spellings` was keyed on the table key only, so the preferred filename missed the deprecated copy

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-format` only: one
derived map, one public `sidecar_key`, one normalisation inside `sidecar_spellings`; no schema
change, no spelling added or removed) · **Owner** format · **Motivating case** S96
(just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md), building `remote_derive` over the
registry's derived-sidecar tarball

**What it reproduced.** `SIDECAR_SPELLINGS` is keyed on the table key — `sources.csv`, the spelling
`sources.parquet` and `manifest.sources` keep — and the preferred filename is not a key. So
`sidecar_spellings("licensing.csv")` answered the one-tuple of a table it had never heard of,
`resolve_sidecar` never saw the deprecated copy, and `sidecar_write_path(spec_dir, "licensing.csv")`
on a module carrying `sources.csv` returned the preferred spelling: the collision the function's own
docstring says it exists to prevent, reached by following it. A consumer holding bytes — a tar member
named `derived/licensing.csv`, an upload part — has the filename and not the key, so the helper
handed them exactly the spelling that did not work.

**The fix, and the half not taken.** The consumer offered two: normalise inside `sidecar_spellings`,
or document that `name` is the table key. The first, because the second leaves the next consumer to
notice the same thing. `_KEY_FOR_SPELLING` is the map read the other way, derived rather than written
so a second aliased table costs no edit; `sidecar_key(name)` publishes it; `sidecar_spellings` looks
the key up through it. Every helper that reads spellings — `sidecar_candidates`, `resolve_sidecar`,
`sidecar_write_path`, `preferred_spelling`, the compiler's name sets, `draft`'s spelling map — is
fixed by that one line. Refusing a filename was not considered: the helper is most useful exactly
where a caller has bytes and a name.

**The sharper half is the read side, and it went into the gotcha book.** The consumer's first defect
was not the write: their displacement diff looked for `licensing.csv`, found nothing on a spec
carrying `sources.csv`, and reported no rows leaving the table while the replacement went ahead under
the other name. A helper whose wrong answer is a plausible path rather than an exception fails
quietly in both directions — the shape `@sidecar-name-and-place` now names.

**Pinned by two tests.** One walks `SIDECAR_SPELLINGS` and asserts every spelling of every entry
answers the same tuple, the same key and the same preferred name — an equality over the map, so a
second alias is covered without an edit. The other is the consumer's measurement reversed, at the
root and under `derived/`, plus the fresh-directory case still creating the preferred spelling
whichever name was asked.

## RM200 — the Atlas's other twenty-one scorers: what a module can take from them

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 · **Owner** enricher ·
**Motivating case** the AVI artifact is one number per variant with the sign discarded; the API
carries direction, tissue and mechanism, and nobody had asked which of it is usable

**Everything here is non-commercial.** Only `AVI_SCORE` is a Permissive Use artifact (RM195). Every
other scorer is ordinary Output, so it enters under `declared_use=non_commercial` and needs the
second source name `alphagenome_atlas` — one `(source, layer)` key cannot carry two licence classes.

**Built 2026-09-11, and what shipped is narrower than this entry proposed.** The item asked what a
module can take from the Atlas's other twenty-one scorers; the answer is `RNA_SEQ` and nothing else,
for the reasons measured below. It ships as `expression_effects.csv`, the tenth derived-fact sidecar
— **not** as an authored column and **not** as a finding. That third route is the one this entry's
own open question did not consider: RM193's rule is that non-commercial Output never becomes a
*stored authored value*, and a derived sidecar honours it literally while still carrying the per-gene
direction a finding would have had to flatten into prose. Half cost under Principle 9 rather than
full, and the compile gate stays exactly as data-driven as it was.

The two questions this entry left open are answered rather than deferred: **what one cell records** is
one row per `(variant, gene)` with the tissue axis collapsed and the gene axis kept, because the gene
axis is the whole reason the scorer is worth having; and **finding or column** is neither, per above.
`*_ACTIVE` and the positional scorers are not adopted — the measurements below stand as the record of
why, and nothing about them changed.

### The correction this starts from

[ALPHAGENOME_ATLAS.md § 4.7](probes/ALPHAGENOME_ATLAS.md) concludes *"there is no expression
direction anywhere in the model"*. That is true of the **AVI aggregate**, whose eighteen features are
all `MAX_ABS_*`, and **false of the API**. Measured on the live service: `is_signed` is `True` for
`RNA_SEQ`, `CAGE`, `ATAC`, `DNASE`, `CHIP_TF`, `CHIP_HISTONE`, `PROCAP` and
`AVI_SCORE_MODEL_FEATURES`. AVI throws the sign away; those never had it thrown away.

### 1. `RNA_SEQ` — adopt for drafting

**The only scorer with a gene axis.** Shape is `(genes, tracks)` and the gene count *varies with the
window* — 61 genes at one variant, 48 at another, against `(1, N)` for all twenty other scorers. So
AlphaGenome attributes it to genes itself, which is what `@gene-map-is-another-sources-attribution`
requires: a gene claim must come from a source's own per-record attribution, never from a span the
caller drew.

Signed, 371 RNA-seq tracks, and at `chr22:20002007` it returns 22,631 values across 61 genes. That is
**expression, per gene, per tissue, with direction** — the axis the shipped artifact cannot express.

Per-request only: no bulk copy exists, and at ~1,091 SNVs/s a gene plus its ±512 kb flanks is ~50
minutes (RM194). So it is a drafting surface for named genes, never a genome-wide pass.

### 2. Positional enrichment of authored rows — the shape is right, the obvious pick was wrong

A module is **not** gene-scoped: the mandatory gene filter is RM194's *drafting* constraint, because
an unfiltered interval query dies with `RESOURCE_EXHAUSTED`. For a variant an author has already
written, the position is known and a positional score needs no attribution at all.

**`CHIP_TF` is refused on the measurement, and it was the most promising candidate.** All 1,617
tracks carry a real `transcription_factor_code` (`CTCF`, `EZH2`, …), so "this variant disrupts CTCF
binding" *looks* sayable. Aggregating |effect| by transcription factor over 751 distinct TFs:

| variant | `PHRED` | top-3 TFs' share | leading factors |
| --- | ---: | ---: | --- |
| chr22:30339156 C>A | **84.1** | **2%** | ZNF513(1), HMBOX1(1), PCBP1(1) |
| chr22:20002017 C>A | 19.6 | 3% | AGO2(1), IKZF3(1), HMBOX1(1) |
| chr22:20002007 G>A | 10.6 | 3% | NRL(1), ZNF280B(1), ZNF768(1) |
| chr1:10001 T>A | 1.1 | 1% | ZNF48(1), PRDM6(1), SMAD7(1) |

Two things kill it. The concentration **does not track effect size** — the `PHRED` 84 variant is no
more concentrated than the `PHRED` 1 one — and every leading factor is a **singleton track**, so the
"top TF" is whichever TF happens to be measured once. Naming a TF from that would publish a sampling
artefact as a mechanism. Same test sinks a named-cell-type claim from `ATAC`: top-5 of 167 tracks
carry 22% / 15% / 5% of the mass, *least* concentrated at the most extreme variant.

**`*_ACTIVE` is not what its name suggests, and that is the useful finding.** It is an **activity
level, not a variant effect**: raw assay units (ATAC 5.7–31, ChIP_TF 332–475), and swapping the ALT
barely moves it. So it does not describe the variant — it describes **the locus**. "This position
sits in open chromatin in these cell types" is exactly the positional annotation an authored row
could carry, and it is a different claim from anything the format holds today.

It needs a normaliser, and the metadata has one: **every track carries `nonzero_mean`** (167/167 for
ATAC), so a level becomes fold-over-typical for that track. Without it a raw 31 and a raw 0.7 are
incomparable, and a threshold means nothing — which is why the first pass found all 167 tracks "above
0.5" at every variant.

### What has to be decided before building

1. **What one cell records.** A per-track vector is not an authored cell. A magnitude, a count of
   tracks above a normalised threshold, or a top-k of *ontology-typed* terms are three different
   claims, and the track vocabulary is mixed — `EFO 65 · UBERON 44 · CLO 40 · CL 15 · NTR 3` — so
   `EFO:0001203 MCF-7` (a cancer cell line) and `UBERON:0001159 sigmoid colon` (an anatomical
   structure) are not comparable and `NTR:` is ENCODE's "no term registered".
2. **Whether this is a check or a column.** RM193's position is that non-commercial Output enters as a
   *finding* and never as a stored value, which keeps the compile gate data-driven. A stored
   accessibility column would be the first thing to test that.
3. **`CAGE` was measured on 2026-09-11 and it splits: the ranking fails, the sign holds.**

   | variant | `PHRED` | tracks negative | top-5 share of 546 |
   | --- | ---: | ---: | ---: |
   | chr22:30339156 C>A | **84.1** | **100%** | 2% |
   | chr22:20002017 C>A | 19.6 | **0%** | 3% |
   | chr22:20002007 G>A | 10.6 | 2% | 4% |
   | chr22:20002123 G>T | 3.0 | 92% | 5% |
   | chr1:10001 T>A | 1.1 | 18% | 7% |

   The top-5 share is 2–7% and runs **backwards** to effect size, exactly as `CHIP_TF` did, so
   naming a tissue is the same sampling artefact — the leaders (Jurkat, retina, amygdala) are the top
   of a flat distribution.

   **The consensus fraction is a different quantity and it is not flat.** 100% and 0% are unanimous
   predicted loss and unanimous predicted gain of transcription initiation, which is a directional
   claim about the *variant* needing no tissue named at all. It is **not monotone in `PHRED`** — 19.6
   is unanimous-positive while 3.0 is 92% negative — which is what makes it an independent axis
   rather than a restatement of the score.

   **So the recordable shape is a consensus fraction, not a top-k**, and that is the hypothesis the
   next scorer should be tested against rather than concentration.

### Assayed 2026-09-11 — the full measurement is [probes/ALPHAGENOME_ATLAS.md § 6.6](probes/ALPHAGENOME_ATLAS.md)

Three assays, and two of them refuted a hypothesis this entry had raised.

**Consensus fraction is a property of the scorer, not the variant**, so it is not a confidence
measure and the shape proposed above is dead. `CAGE` and `PROCAP` are near-unanimous at *every*
variant — 97% at `PHRED` 0.007 — while `RNA_SEQ` never exceeds 61%. What survives is only that under
high consensus the **direction** is a claim; a record may say which way, never how sure.

**`RNA_SEQ`'s lack of consensus is structural, not noise.** A variant can raise one gene and lower
another, so its tracks *should* disagree — which is the sharpest argument that the gene axis is the
thing to use and a fraction is the wrong summary for it.

**`*_ACTIVE` does move with the ALT, and the maintainer's objection holds for every motif class.**
Re-tested against motifs found in the artifact's own `REF` column: `ATAC_ACTIVE` moves ~**16×
control** in a Z-DNA former, ~**15×** in a G-quadruplex and ~10× in a poly-T run, reaching 20% at
individual loci. So it is mostly positional with a real per-variant component wherever DNA geometry
is at stake. **The G4 row read *background* until the probe was fixed** — it had been sampling motif
*centres*, which are mostly loop bases, where disrupting a quadruplex requires breaking a tetrad. The
signed `ATAC` channel spreads 27–151% at the same positions, so the model is not insensitive at all;
the *level* is damped, as a level should be.

**Positional scorers remain unusable as named claims**, now on two independent tests rather than
one: ranking fails (top-5 carries 2–7%, running backwards to effect size) and consensus does not
discriminate. The track vocabularies also mix cancer cell lines, anatomical structures and cell types
under one ranking, with three ENCODE *no term registered* placeholders.

**So the item narrows to `RNA_SEQ`**, and the remaining questions are unchanged: what one authored
cell records, and whether non-commercial Output may be a stored column at all or stays a finding as
RM193 has it.

**Still unmeasured, and it is a use-case question rather than an assay one:** whether an averaged
locus accessibility buys a module anything. Every number says what the scorers do; none says a
consumer wants it. That belongs in USE_CASES.md.

## RM194 — gene-scoped SNV subslices, and the ±512 kb horizon

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 · **Owner** enricher ·
**Motivating case** slicing the artifact by gene *position* silently drops promoters, enhancers and
other distal variants that act on a gene without sitting in it

**Built 2026-09-11.** Shipped as `just-dna-enricher alphagenome expression`, writing
`expression_effects.csv` — a recording pass rather than the drafting provider this entry describes,
because RM200 landed with it and the rows belong in a derived sidecar rather than in `variants.csv`.

**Both span forms ship, and the interval wins.** The three candidates this entry weighed were the
wrong shortlist: a fourth option — the operator supplying `--chrom/--start/--end` outright — needs no
lane, no staleness story and no answer to "what if the span source disagrees with the module", and it
is the default route. `--gene` alone resolves the span from the **MANE lane** (the only in-tier source
with gene coordinates; the Ensembl snapshot is eliminated by its own schema, which has no gene column
at all), widened by the ±512 kb horizon measured here. The gene filter is mandatory in **both** forms,
because it is a server-side requirement rather than an optimisation.

**Distance is recorded, as this entry required, and it is tri-state.** The MANE lane is consulted even
when the interval was supplied by hand — those are two questions, and an explicit interval only
answers the first. With no lane the column is null and the pass says so, never an interval edge.

Two defects surfaced only by running the real command, both of which every offline test had agreed
with: the Atlas wants `chr22` on the wire where a module stores `22`, and `summary.parquet` lives
under a snapshot's `data/` rather than at its root. A fixture confirms the convention its author
chose, which is the standing argument for a live leg however small.

**The blocker this item carried is gone.** [PROPOSAL_0_7_PT4](proposals/PROPOSAL_0_7_PT4.md#rm194--gene-scoped-subslices-and-the-512-kb-horizon)
listed the interval RPC as the thing a first cut owes, "including the `x-goog-fieldmask` header and
32 bp chunking that hand-built requests got wrong". Measured on 2026-09-10 and **none of that was
the cause**:

| claim | measured |
| --- | --- |
| the `x-goog-fieldmask` header is required | **no** — the same interval answers identically without it; asserted as equality of the two answers, not as "both succeeded" |
| 32 bp chunking is required | **no** — a 128 bp interval answers in one call; the SDK's 32 bp sub-intervals are its *parallelism* strategy |
| — | **`Interval.strand` must be a real member.** `Strand` has **no zero**: `STRAND_UNSPECIFIED = 0` is the proto3 default, so an omitted `strand` goes on the wire as a value the server rejects — as a bare `INVALID_ARGUMENT` naming no field. That was the entire failure |
| — | **a filter is effectively required**: unfiltered, 32 bp answers with a **43 MB** message against a 4 MB receive limit |

`AtlasClient.score_interval` shipped with RM192's commit for that reason — it is the client's missing
half, it is now tested (offline and live), and leaving it out would have left the measurement
unrecorded in code. **This item is now the drafting provider and nothing else.**

**An upstream bug found on the way, and it is in the pagination:** the server returns a
`next_page_token` on an exactly-full final page, and following it is `INVALID_ARGUMENT`. A 1,000 bp
interval (3,000 variants, short last page) correctly omits the token; 1,024 bp (3,072 = six pages of
512) does not. AIP-158 says an omitted token means no further pages, so a faithful client crashes on
the one interval width that divides evenly. The SDK has the same loop and never trips it, because
32 bp cannot fill a page. `score_interval` follows the token but also stops once the requested
interval is covered, with an offline regression test.

**Why the provider was not built.** Two reasons, neither of them the RPC:

1. **It cannot be validated in one night.** Measured cost is ~1,091 SNVs/s, so a gene plus its
   ±512 kb flanks is ~3.3 M SNVs and **~50 minutes per gene**. A drafting provider whose only
   end-to-end test takes an hour per case is not something to land unattended.
2. **Where the gene's coordinates come from is a design decision, not a detail.** The provider needs
   a span before it can query one, and the tier has three candidates (the MANE lane, the Ensembl
   snapshot, the module's own authored `gene`) with different currency and different failure modes.
   `@gene-map-is-another-sources-attribution` says a source with no gene column is drafted through
   another source's *per-record attribution*, never a span — and here AlphaGenome **is** the
   attributing source, so the span is only a query hint and the attribution it returns is the claim.
   Which of the three supplies the hint changes what a stale one does.

**What still stands from the design**, unchanged and measured: gene attribution reaches **±512 kb**
and stops dead beyond it (scores returned at +500 kb, nothing at +700 kb — the half-window of the
model's 1 MB input); distal scores run **~10× lower** than at the gene, so a flat `--min-score`
would silently keep only proximal variants and the **distance must be recorded beside the score**;
and the lane needs a second source name, `alphagenome_atlas`, because `RNA_SEQ` output is ordinary
non-commercial Output while the AVI artifact is the Permissive candidate — one `(source, layer)` key
cannot carry two licence classes.

## RM223 — the upgrade guide was the one maintained doc nothing walked, and four of its counts had rotted

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (docs + one guard; no code
change) · **Owner** compiler (the guard lives beside `test_counted_prose.py`) · **Motivating case** a
consumer repository measured four of the document's numbers against the installed packages and found
all four wrong

`INTEGRATION_0_7.md` is read once, at upgrade time, by somebody who then acts on it. It said
`ARTIFACT_PARQUETS` goes 19 → 22 where the constant holds 23; `VALID_WARNING_CODES` had 72 members in
§ 2.4 and 71 in § 3 where the vocabulary holds 73; and the authoring reference rendered "31 models, up
from 28" where it renders 32. Three of the four moved for one reason — the AlphaGenome round landed
`expression_effects` after the numbers were taken — and the fourth was a second copy of the first.

**The document already stated the rule it was breaking.** Its § 8 says a counted claim in prose rots
exactly like a hand-kept list, and §§ 2.2 and 2.3 already tell the reader to derive from
`ARTIFACT_PARQUETS` and `OVERRIDABLE_TABLES`. The advice was correct and was sitting one paragraph
above the numbers that contradicted it, which is the same shape as the three long-tail items in this
round: **the rule is written down one layer away from where it was broken.**

The reason it rotted is narrower than the rule, though, and it is the part worth keeping:
`test_counted_prose.py` reads `SCHEMAS.md` and `COMPILER.md` and stops. Nothing walked this file. So
the repair is not the four words — it is
`compiler/tests/test_integration_doc_states_no_registry_count.py`, which refuses the *shape*: a
current-size claim about a registry, in any of the three forms this document used. After the fix the
document states no size at all, so the absence is the invariant and there is nothing left to
value-check. Run against the pre-fix file at `1879a1f` the guard reports all four.

**What the guard deliberately permits**, because its first draft did not and would have been worked
around rather than obeyed: a frozen *before* value (`goes 19 → len(ARTIFACT_PARQUETS)`), an RM id or
release line beside a constant, an enumerated delta, a measurement of a built artifact ("24 parquets"
of atlas data is not a claim about `ARTIFACT_PARQUETS`), and the document quoting its own stale word
back while explaining that it was wrong. Three of those five are sentences this item itself wrote.

**Not fixed here, and not ours:** the consumer also measured `expression_effects.csv` as present in
`OVERRIDABLE_TABLES` and `DERIVED_TABLE_MODELS` but absent from their `RECOGNIZED_SPEC_FILES`, so the
overlay grammar invites a correction against a table their rebuild drops. Both of this tier's
registries agree with each other; the third is in their tree and is filed there. `@registry-completeness`

## RM215 — allele case is inside `content_signature`, so one pair had two identities

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 · **Owner** format ·
**Motivating case** found by derivation during the 2026-09-11 blind re-derivation round, beside RM214

`ALLELE_PATTERN` is `^[ACGT]+$` with `re.IGNORECASE`, so a lowercase allele is legal, and an allele
cell is stored verbatim. Measured on one `VariantRow` with the genotype spelled four ways:

```
'A/G'  sha256:ec8c6bcc…      'a/G'  sha256:1653d7ee…
'A/g'  sha256:0b0a1369…      'a/g'  sha256:78cb573e…
```

Four content identities for one heterozygote, which for a *content-dedup* key is wrong in exactly the
way RM36's build conflation was. `content_signature` now upper-cases a cell whose grammar is
case-insensitive; the four collapse to one, and the survivor is `ec8c6bcc…`, the value every
existing module already had.

**This entry was filed for 1.0 and the filing was wrong.** It sized the change as major "the same
reasoning RM81 applies to a retype", and that citation does not transfer: RM81 is a **parquet retype**
(`List(Utf8)` vs `Utf8`), which P3 names explicitly as major-only. Folding at hash time adds, removes
and retypes nothing — the authored cell is untouched, `model_dump()` is unchanged, the parquet column
is unchanged, and the round trip is unaffected. What moves is a *computed* value, which is P3's own
**corrected derivation** case: it "may ship in any release", never silently. **RM36 is the precedent
in this very function** — `genome_build` was made to feed the hash in 0.5, a minor, on the identical
argument: only the modules that were being misidentified move.

The three repairs the filing listed were also not the only options, and the one it did not consider is
the cheap one. Upper-casing *at the model* would rewrite an authored cell; refusing lowercase would be
a tightening needing RM52's upgrade procedure; hashing case-insensitively was described as making the
signature "stop reading as the bytes" — but the signature has never read as the bytes. It already
normalizes `1.00`→`1.0`, column order, and an unset optional column, and allele case under a
case-insensitive grammar is the same category. The bullet that says so was already in the docstring.

**Scope is measured, not assumed.** The fold is driven by a `CASE_INSENSITIVE_ALLELE` marker and
reaches the four columns whose validator *is* that grammar — `VariantRow.genotype`,
`VariantRow.effect_allele`, `HaplotypeRow.allele`, `PharmVariantRow.genotype` — found by probing all
57 models behaviourally rather than by grepping for the word "allele". Two near-misses are the reason
the probe is behavioural: `AlleleFunctionRow.allele` is a haplotype *name* (`*36+*10`) whose validator
merely shares a method name, and `ModuleSpecConfig.authority_precedence` is a `list[str]` that a
string probe trips by its own duplicate check. **`ref`/`alts` are deliberately out**: neither is
grammar-checked (both accept `zz`), because a non-nucleotide there is a spelling defect a later pass
diagnoses (`@non-nucleotide-spelling`) — a field with no grammar has no case-insensitivity to inherit,
and folding it would collapse values that genuinely differ.

**No published signature moves, measured rather than asserted:** 536 marked cells across
`reference_examples`, none carrying a lowercase letter, so the fold is the identity function on every
module published to date. That measurement is a test, because the minor-legality argument rests on it.

**Nothing is declared in `RELEASE_RECORDS`, on purpose.** The first draft added a
`DeclaredChange(axis="content_signature", kind="correction")` and the record's own invariant refused
it — a declared axis must be one the measurement reports as moved, and this one is `False` because
nothing moved. P3's corrected-derivation clause is written for the case where earlier artifacts hold a
value we no longer stand behind; zero artifacts are affected here, so there is no movement to declare,
and forcing the axis to `True` would put a false measurement in the record to satisfy a rule about
honesty. This entry and the CHANGELOG are the declaration.

**Surfaced, not fixed (`@fix-vs-surface`):** `derive_variant_key`'s coordinate fallback does not fold
case either — `1:100:a:g,t` vs `1:100:A:G,T` — firing for a multi-alt row or a non-GRCh38 build, since
the VA path normalizes case already. That splits *joins and dedup* rather than identity and it moves a
**stored** cell, so it is a different item. A parametrized test pins the current behaviour so the note
cannot rot into a silent fix. `@verbatim-except-order` · `@registry-completeness`

## RM217 — two vocabularies were documented in no maintained file at all

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (docs + one guard; no code
change) · **Owner** format · **Motivating case** the same superset sweep that produced RM216

Eight of `vocab`'s 29 `VALID_*`/`RECOMMENDED_*` frozensets were named nowhere in `SCHEMAS.md`, the
maintained reference for the tier that owns them. **`RECOMMENDED_ANCESTRY_GROUPS` and
`VALID_EFFECT_DIRECTIONS` appeared in no maintained document at all.** The other six were reachable
only from INTEGRATION and ROADMAP_HISTORY — files that record what one release did, not files that
describe the tier — so a reader who arrived at the reference could not find them from there.

**The document already described the mechanism and not the registry**, which is the recurring shape:
the vocabulary-binding bullet explains how a field carries its members and why there is no central
registry, and explains it well. What it did not do is say which sets exist.

**The table carries three things and deliberately not the members.** Members are
`authoring_reference()` and the constants themselves, and a hand-kept copy of a member list is how
`SOURCES_FIELDNAMES` lost a column (`@fieldnames-from-model`). A count, an openness flag and a
sentence about what the set is *for* are what a table can hold without rotting — and the count is
asserted, so adding a member without touching the doc fails rather than drifting.

**Openness is asserted too, because that flag is load-bearing.** `actionability` shipped as an open
seed while `VariantRow` rejected non-members, so a tool offering a novel value got a rejection it had
been told to expect. A table mislabelling one would re-create exactly that.

**Scoped to `vocab`'s own sets**, not the leaves' — `spec`, `binning`, `pgx`, `pgs`, `manifest` and
`sources` own theirs, and a central registry would need `vocab` to import `pgx`, which is the cycle
`base`'s dependency note exists to avoid. The guard says so rather than pretending to be complete
over something it is not.

## RM222 — the CIViC drafter's licence row: written when it drafted nothing, and carrying no release

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: a
gate, an optional parameter, and a docstring; no schema change) · **Owner** enricher · **Motivating
case** the 2026-09-11 blind re-derivation — `docs/audit/ENRICHER_FROM_CODE.md` D13–D15

Three findings at one call site, all of them `@write-the-sourcerow`.

**"One that contributed nothing writes none" was a comment, not a gate.** The condition was
`if not dry_run:` and nothing else, with that exact sentence directly above it — so a `--gene` filter
matching nothing still wrote a `civic` row into `licensing.csv`. A licence row is a claim that the
module uses the source; writing one for a module with no CIViC rows in it is a false claim, and the
compile gate reads that file and nothing else. Both sibling drafters implement the rule
(`strchive_draft`, `mitomap_draft`) and `test_strchive_draft.py` refuses this shape on that path, so
the predicate was written down twice already and missing here.

**`dataset` was computed and dropped on the floor.** `civic_dataset_label(...)` reaches every drafted
row's `conclusion`, and `record_source_terms` had no parameter to carry one — so the licence row read
`dataset=''`. Not cosmetic: `SourceRow.dataset` is what `--verify-datasets` compares and what
`withdraw_stale_dataset` withdraws, so **a CIViC-drafted module sat outside the currency check every
other drafted module is inside**. `record_source_terms` gains an optional `datasets` mapping; an
absent entry still leaves the column unset rather than guessing, which is what the fact passes want.

**And the function's own docstring had stopped covering its callers.** It read *"None of these layers
can taint a module: `taints_commercial_use` requires the `annotation` layer"* — true of the three
fact passes it was written for, and false since `civic_draft` began recording at `annotation` with an
explicit `declared_use`. It sent a reader to the wrong conclusion about whether a drafting pass can
taint. It can; that layer is exactly the one the gate reads.

The test drafts from the checked-in CIViC slice, so both "drafted something" and "drafted nothing" are
real runs of the real provider. It is unfiltered for the positive case deliberately — naming a gene
couples the test to which genes happen to be in a fixture, and what the case needs is *a run that
drafted*.

## RM219 — one fetch in the module whose documented rule is that fetches stage

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only:
one fetch staged; no schema change) · **Owner** enricher · **Motivating case** the 2026-09-11 blind
re-derivation — `docs/audit/ENRICHER_FROM_CODE.md` D9

`download.py` states the rule at length and applies it everywhere but one line: *"Staged through
`.part` like every other download here, because a failed one is not a no-op. `HfFileSystem.get`
creates the local file before it discovers the remote path is missing."* The parquet fetch, the
sidecar fetch and the root-file loop all stage. `_provision_root_file_snapshot` staged its payload and
then fetched `release.json` straight to the target two lines later.

**The cost is a state change, not a stray file.** An absent label is *nobody said*; a
present-and-unreadable one is *the description is corrupt*. A 0-byte `release.json` reads as the
second: `_json_parses` rejects it and `LaneStatus` reports `release_unreadable`, sending an operator to
re-pull a lane whose remote simply has no description to give
(`@an-absent-input-is-the-unknown-arm-and-a-malformed-one-is-the-refusal`).

The test's fake reproduces the documented client behaviour rather than assuming it — `get` creates the
file *and then* raises, which is the only reason the bug existed. A fake that raised without touching
the filesystem would have passed against the unfixed code.

## RM220 — the offline flag meant two different things, and the gated pass had the ungated one

**Severity** high · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: one
gate; no schema change) · **Owner** enricher · **Motivating case** the 2026-09-11 blind re-derivation —
`docs/audit/ENRICHER_FROM_CODE.md` D5

Two readings of the flag coexisted and nothing said which applied where. `pgx` makes it **absolute**,
and `test_pgx_licensing.py` asserts it by name: *"An injected live client is not a loophole: `offline`
outranks the injection, because a live client under a flag documented as making no egress is exactly
the failure RM38 closes."* `gwas` does **not**, and says so in its own docstring: *"An injected
`client` still wins, because handing over a transport you already hold is not egress."*

**`expression` had `gwas`'s shape against `pgx`'s situation.** Its gate was
`if offline and client is None:`, and the AlphaGenome Atlas is licence-gated — its Additional Terms bar
classes of holder outright — so an injected client fetched from a gated source under a flag documented
as making none. `@flag-means-same`.

**The axis the two readings differ on is the source's licence**, and that is now written down in
ENRICHER.md rather than inferable only by reading three modules. `gwas` keeps its behaviour on
purpose: the GWAS Catalog is ungated, its docstring argues the case, and changing a stated contract
for a Python-API caller is a decision rather than a repair.

**The licence gate was masking the egress hole**, which is why the test declares its use. With
`declared_use` at its default the run is skipped by `check_declared_use` anyway, so a test that left it
there would have passed against the unfixed code — the second gate standing in for the first. Declaring
the use removes it and leaves only the gate under test.

## RM221 — three help texts, a size, a "vendored", and a count: five claims that had stopped being true

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (help strings, comments and one
doc paragraph; no behaviour change) · **Owner** enricher + format · **Motivating case** the 2026-09-11
blind re-derivation — `docs/audit/ENRICHER_FROM_CODE.md` D1–D4

**Rich ate the extra's name out of three rendered help texts.** Typer renders through Rich, which
reads a bare `[word]` as a style tag, so `atlas --help` printed *"Needs the  extra"* and
`atlas generate --help` printed *"which is in `` and deliberately not in ``"* — telling a new user
nothing at all about which install to do, on the first screen they read. Escaped.

**Two declarations of the extra's size disagreed**, 22 MB against 19 MB, and the file carrying the
measurement is the one that was right: `enricher/pyproject.toml` records 19 MB in a clean venv on
2026-09-10, and 22 MB is the grpcio release current at the design round. The stale figure had reached
five places — including two paragraphs of `ENRICHER.md` written *earlier the same day* by the pass
that added the AlphaGenome §, which is how a superseded number propagates.

**"Vendored" survived RM196 in two places.** The `atlas` group help and `ENRICHER.md` both said the
bindings are generated from sources vendored in `docs/vendor/alphagenome_protos/`, while
`atlas generate --help` two lines away said *"The sources are not vendored"* — and the directory holds
a README and nothing else. The second is what the code does.

**And a count beside its registry, one tier over** (D4): `VALID_VERIFICATION_CHECKS`' first block read
*"`enrich` writes these six"* while `enrich` writes **eight** — `published_refutation` and
`evidence_status_currency` are filed under the next heading with `— enrich` beside them, so membership
was right and the sentence had drifted. This is the failure `verification.py`'s docstring records
correcting three times, one file from where that lesson is written down, and it survived because the
existing guards assert membership of the *whole* vocabulary and no test read a block. The number is
gone and `test_verification_record.py` now walks both sides — the names `enrich._verification_records`
passes to `ran`/`skipped`, and the names commented `— enrich` in `vocab.py`.

## RM218 — the counted-prose rule reached `docs/` and stopped at the source

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-compiler` only:
comments, one docstring pair, and a floor promoted to an equality; no behaviour change) · **Owner**
compiler · **Motivating case** the 2026-09-11 blind re-derivation — `docs/audit/COMPILER_FROM_CODE.md`
§§ 13.4–13.6, 13.8

`test_counted_prose.py` exists because the same number went stale twice, and its `_DOCS` constant
scopes it to the documentation tree. The same class was live in `compiler.py` itself:

| claim | measured |
| --- | --- |
| "up to twelve in all" (the module docstring's parquet count) | **23** |
| "There are six reasons … and a reader needs the six" (`_vrs_gap_reason`) | **8** return arms |
| "covered three of the sixteen names" beside `ARTIFACT_PARQUETS` | true as *history*, read as current |

`_vrs_gap_reason` is the instructive one: RM5 added the symbolic class and RM59 the unobservable
class, each correctly, and neither moved the number two paragraphs up.

**No number was re-counted.** Both sentences state the rule now, and the guard asserts the property
each was standing in for — for the parquets, that the docstring names the constant; for the reasons,
`@answered-is-not-absent`'s actual requirement that the arms be **pairwise distinct**, which a count
never checked. Eight arms returning six distinct strings would have satisfied the old sentence exactly.

**The guard's first catch was the repair's own prose**, which is worth keeping: the replacement
docstring quoted the stale phrase verbatim while explaining it, and a stale figure in quotation marks
two lines below the rule reads to a skimming reader exactly like the rule.

**A floor became an equality** (§13.5). `_build_weights` states its 39 columns twice by hand — its own
comment says so — and the guard was `required.issubset(...)` over a **15-name literal**, leaving 24
columns unwatched. `@registry-completeness` says equality over a walked set, never a floor; the
declared schema is now that set, the emitted parquet must match it exactly, and a second test compares
the function's two hand-kept halves to each other. No live drift was found, so this is an unguarded
invariant rather than a broken one.

**And a docstring that over-claimed, in both copies of itself** (§13.6). `validate_spec`'s said
`strict` *"changes severity only; it never adds or removes a finding"*. Two findings are aggregates
with no `best_effort` counterpart sentence — the unresolved-position refusal and
`build_disagreement_error` — whose `best_effort` rung is a *different* sentence firing in both modes,
so `strict` genuinely adds them. The code is right and the sentence was wrong: the contract the two
commands share is that `validate(strict=x)` and `compile(strict=x)` reach the same verdict, not that
the two modes of `validate` differ by a severity column.

**Surfaced, not fixed** (§13.8): `ensembl_reference` and `ba1_threshold` are `compile_module`
parameters the CLI cannot reach, so `manifest.compilation.ensembl_reference` cannot be stamped by the
shipped command at all. Neither is a defect and neither is a decision anyone took —
`test_cli_parity.py` does not assert compile-flag parity — so COMPILER.md records the gap and leaves
whether to close it open.

## RM216 — fifty-one error types named nowhere, in the § titled *what a caller catches*

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (docs + one guard; no code
change) · **Owner** enricher · **Motivating case** the superset sweep of the 2026-09-11 blind
re-derivation — every identifier the from-code snapshot names, grepped against the maintained document

The sweep the round owed and had not run: take each `*_FROM_CODE.md`, pull every backticked identifier,
keep the ones the package actually defines at top level, and grep them against the maintained doc.
341 real surfaces came back absent across the three tiers. Most are legitimately delegated — per-field
and per-column names are `@fieldnames-from-model`'s business and belong in the snapshot, not in a
hand-kept table. **Error types are not**, because a consumer writes one in an `except`.

`ENRICHER.md`'s exception-contract § carried the ten-row pass→type table a consumer usually needs, and
the tier defines **83 classes**. Fifty-one of them appeared nowhere in the document, so a consumer
meeting `ClinPgxUnavailable`, `GatedSnapshotError` or `AtlasRefMismatch` had nothing to look it up in.

**Grouped by what raises them rather than alphabetically**, because the groups are the contract: a
runtime pass's type is what a consumer catches, a client's is what the pass translates and the
consumer never sees, a builder's belongs to `cache rebuild`, and the snapshot readers' are
`FileNotFoundError` subclasses on purpose.

**The third column is a ladder, not a set**, and a second test asserts it really is one. A subclass
makes a caller's `except` **order** load-bearing (`@client-exception-contract`), so a reader uses that
column to decide which handler comes first — a row claiming a narrowing that is not one would have
them order handlers against a hierarchy that does not exist. `AtlasRefMismatch` is the single entry
two levels deep.

**Equality, not containment**, since the table says about itself that it is every type this tier
defines: a name in it the package does not define sends a reader looking for a class that is not
there, which is the same defect one direction over. Builtins are dropped rather than the pattern
narrowed — the pattern is what makes a new error type join the roster by existing.

## RM213 — `merge_key` raised for a missing key and collapsed silently for an empty one

**Severity** low (latent) · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-format` only:
one guard; no schema change) · **Owner** format · **Motivating case** the 2026-09-11 blind
re-derivation — `docs/audit/SCHEMAS_FROM_CODE.md` D1, measured

The function's own docstring states the failure it must produce: *a caller reaching here for an unkeyed
kind has a bug, and a silent `()` would merge every row into one*. It raised `AttributeError` for a
model **declaring no key** and returned `()` for one declaring an **empty** key. `MeasureBinRow`
declares exactly that, as a base-class default meaning *subclasses set this*.

Measured: two `MeasureBinRow`s differing in every column returned equal keys.

**Latent rather than live**, and worth saying so. `measure_bins.csv` is authored while `merge_key`
serves the machine-produced sidecars, and every `MeasureBinRow` subclass overrides the default — so
nothing reaches it today. What made it worth fixing is that the next kind to inherit the default and
forget would find the collapse in a merge pass rather than here, and a docstring that promises a
failure is a claim like any other.

**`hints.table_key` is deliberately unchanged.** It reads the same falsy value as *no declared key* and
answers `None`, which is correct for its own question — does this table publish a key a consumer can
join on? This one asks what two rows' identity **is**, and there is no empty answer to that.

## RM214 — the allele grammar is case-insensitive and the ordering rule beside it was not

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-format` only: a
sort key; **loosening only**, so no authored value moves) · **Owner** format · **Motivating case** the
2026-09-11 blind re-derivation — `docs/audit/SCHEMAS_FROM_CODE.md` D2, measured

`vocab.ALLELE_PATTERN` carries `re.IGNORECASE`, so a lowercase allele is a deliberately legal
spelling. The unphased ordering rule next to it used a plain `sorted()` — ASCII, which puts every
uppercase letter before every lowercase one. So of the four case spellings of one heterozygote:

```
A/G  accepted        A/g  accepted
a/g  accepted        a/G  REFUSED
```

The same unordered pair, two answers, decided by which half the author happened to shift.

**The key is `str.casefold` and the sort is stable**, so every value that sorted before still sorts and
nothing already authored moves. It only stops refusing the mirror spelling, which makes this a
loosening and therefore minor-legal (P3 bars tightening, not widening).

**What it deliberately does not do, and why that is the interesting half.** It does not make the pair
canonical: `A/g` and `a/G` are both accepted and hash **differently** under `content_signature`,
because the cell is stored verbatim. `@verbatim-except-order` is exactly on point — the rule normalizes
the ORDER and nothing else, and the exception it names is an encoding that lies about its own order,
which is what ASCII was doing here. Normalizing allele *case* is a different act: it would move the
signature of every module carrying a lowercase allele, which is a question about what an identity key
means and therefore **1.0** work. Filed as such rather than smuggled into a minor.

## RM212 — the AlphaGenome key in a `.env` was invisible to the two paths that read it

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only:
`load_env()` at two call sites, and the refusal gains its diagnosis; no schema change) · **Owner**
enricher · **Motivating case** the 2026-09-11 blind re-derivation — `docs/audit/ENRICHER_FROM_CODE.md`
D12, measured with a real `.env`

**`@credential-where-read` has two clauses and only the first was kept.** Reading `os.environ` at the
point of use is one; *a guard in front of a loader must load too* is the other. `expression._connect`
— the one function in this tier whose own docstring cites the rule — read the variable without calling
`load_env()`, and nothing else on `alphagenome expression`'s path loads a `.env`. So a key that lives
only there, which is where this workspace's does, was invisible, and the pass refused with
*ALPHAGENOME_API_KEY is not set* while the file sat in the working directory.

`cli._atlas_client_or_none` had the same gap with a quieter failure: it degrades to a printed sentence
rather than raising, so `alphagenome check` reported *no ALPHAGENOME_API_KEY, so nothing was refined*
and fell back to the knot table's interval for rows the Atlas could have refined. Two sites, one
omission, which is why one test asserts both.

**It is the same incident one lane over**, and `caches._rebuild_pharmvar` already carries the comment:
the PharmVar lane reported "no key" and never built on the one machine most likely to have one,
because `PharmVarClient.__init__` loaded the `.env` and the guard in front of it did not. That comment
ends *a pre-check that answers differently from the code it is guarding is worse than no pre-check* —
this is the same sentence with a different variable.

**The refusal now names which absence it is.** `missing_credential_reason` was already the tier's
answer to `export FOO=` being strictly stronger than never setting the variable (`load_env` uses
`override=False`, so a present-but-empty value is kept); both AlphaGenome messages said only "not
set", which sends an operator with an exported-empty shell to the wrong fix. Both states are asserted.

**One rule violation fixed on the way**: `cli._atlas_client_or_none` carried an inline `import os`,
which is not the guarded-optional-dependency exception the function's other inline import is. It is at
module level now.

## RM210 — one finding, two counts, because the two sides were handed two views of the table

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-compiler` only:
one argument changed; no schema change) · **Owner** compiler · **Motivating case** the 2026-09-11 blind
re-derivation — `docs/audit/COMPILER_FROM_CODE.md` § 13.2

`_cross_check_literature` runs on both sides of the validate/compile pair and **every message it builds
embeds a count**. `compile_module` de-duplicates the second run on the message string, which is exactly
as safe as the two runs seeing the same input. They did not: the pre-flight got `loaded_kinds` (the
tables as loaded), the compile its own `kind_rows` (the tables after `_apply_symbolic_drops`).

**One table is both droppable and citing, which is the whole mechanism.** `pharm_variants.csv` is in
`_SYMBOLIC_DROPPABLE_TABLES` and in the citing kinds, so a pharm row that carries an unusable symbolic
allele *and* cites a PMID is citing to one side and gone to the other. Reproduced on
`reference_examples/pgx_slco1b1_simvastatin` plus two cells:

```
literature.csv describes 1 citation(s) … ['99999999']
literature.csv describes 2 citation(s) … ['29165669', '99999999']
warnings_summary: {'literature_row_uncited': 2}
```

Two contradictory published claims and a count of two for one finding. The existing guard asserts
`len(warnings) == len(set(warnings))`, which two *distinct* strings pass.

**The repair is to make the inputs agree, not to stop re-running.** `@no-rerun-with-counts` forbids
re-running a check whose message embeds a count; running a check on both sides is the normal case here
and the rule says so. The pre-flight had already computed `survivors` — the same post-drop view —
three lines earlier for the positional fill, so this is one argument, not a new code path.

**Which of the two sentences is right matters**, and it is the post-drop one: the dropped row is not in
the artifact, so the citation it carried really is orphaned there. Publishing the pre-drop count would
describe a module that was never compiled.

**Scope stated rather than narrowed.** The same input reaches `citation_not_in_pubmed` and the
quote-counter finding, which share the function; all three are fixed by the one argument.

## RM211 — `@parity-by-check`, on the sibling RM93 left behind

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-compiler` only:
four checks gain a pre-flight call site; no schema change, no message change) · **Owner** compiler ·
**Motivating case** the 2026-09-11 blind re-derivation — `docs/audit/COMPILER_FROM_CODE.md` § 13.3

**The compile-side per-model closures are where parity keeps failing**, and the reason is structural:
a table is loaded in both commands, so a pass auditing table by table sees it covered and stops.
`@parity-by-check` exists because of that. RM93 moved `_check_frequency_arithmetic` out of one such
closure and **left its sibling behind** — `_check_gene_metrics_arithmetic` is the same
validate-by-redundancy over a sidecar's own numbers, needs no `output_dir`, no reference and no
resolved row, and stayed compile-only for two releases. A module whose `oe_lof` disagrees with
`obs_lof / exp_lof` passed a green `validate` and warned at compile.

Four moved, each with what makes it legal under the standing exemption — what stays compile-only is a
check reading **resolved rows**, not the word "resolution":

| check | why it is pre-flight-legal |
| --- | --- |
| `_check_gene_metrics_arithmetic` | reads one sidecar's own columns and nothing else |
| `_cross_check_gene_metrics` | keyed on **gene**, which is authored and which nothing fills |
| `_cross_check_gene_validity` | same key, one table over |
| `_check_declared_license_agrees` | `sources.csv` against `module_spec.yaml`'s own `license:` — two authored files, no join |

**And five deliberately did not move**, recorded because an exemption nobody writes down is re-derived
as a bug next round. `_cross_check_frequencies`, `_cross_check_clinical_assertions`,
`_cross_check_gwas_effects` and `_check_ba1_lint` are keyed on **position or `variant_key`**, and an
rsID-only authored row has no coordinate until resolution runs — asking them early would report every
such row as an orphan, which is a worse answer than a late one. `_source_checks` is the other kind: its
`used_sources` is complete only once every sidecar has been read, and `sources.csv` is last in
`_FACT_TABLES` precisely so the compile can ask it against a full set. Asking it in the loop would
answer over a partial set and warn about orphans that are not.

**No new dedup was added**, which is worth saying because the neighbouring closures carry one. The
fact-table **extend site** already filters every check's warnings on the message
(`@first-fact-check-on-both-sides`: dedupe where the results are collected), so the two newly-doubled
findings are covered by the mechanism that was already there — and neither message embeds a count,
which is what makes the two runs byte-identical.

## RM207 — the one refusal that is fatal in both modes was asked of the wrong key, on the wrong side

**Severity** high · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-compiler` only: one
loop replaced by three shared helpers, and four lines in the pre-flight; no schema change, no published
text change) · **Owner** compiler · **Motivating case** the 2026-09-11 blind re-derivation round —
`docs/audit/COMPILER_FROM_CODE.md` § 13.1, written from the code with the maintained doc unread

**Two defects with one root, and the second is the one that mattered.** `resolve_from_table` ended with
a loop over `patched` — the rows *after* the fill and the expansion — looking each one's `variant_key`
up in the injected table. But the table is keyed by the key the **author** wrote, and the loop at the
top of the same function says so (`resolution.get(v.variant_key)`). For a row the fill merely completes,
the two strings are equal and the check worked. For a row the table **expands**, they are not:
`update["variant_key"] = derive_variant_key(...)` mints the locus's `ga4gh:VA.…` id, and looking *that*
up in a table keyed by `rs111033563` misses every time.

So the refusal the code's own comment calls "fatal in BOTH modes" was silently skipped on exactly the
rows that expanded. Reproduced on `reference_examples/hfe_hemochromatosis` with one extra resolution
row: a module carrying a withdrawn rsID on a two-locus variant compiled clean, `success=True`.

**And the check only ever existed on the compile side.** `resolve_from_table` is called from
`compile_module` and nowhere else, so where it *did* fire, `validate` reported the spec valid in both
modes and a plain `compile` then refused it — the sequence `test_validate_agrees_with_compile.py`'s own
docstring calls "the one thing this command must never do". The standing compile-only exemption does not
cover it: what stays compile-only is a check reading **resolved rows**, and this one reads the injected
table's own `rsid_status` column, needing no `output_dir`, no reference and no resolution having run.
That is the same test `unresolved_subjects` was factored out under (S76), and the repair is the same
shape — `withdrawn_refusals`, `ambiguous_refusals` and `ambiguous_warnings` are now shared predicates
both sides call.

**Sentences, not subjects — a deliberate difference from `unresolved_subjects` beside it.** That one
returns names and lets each caller phrase them, which is safe because both phrasings are one clause.
These interpolate *two* things, the subject and the retracted rsID, and the standing rule is share the
predicate and copy the error; a two-interpolation sentence copied into a second caller is precisely how
the two drift. So the sentence is shared and there is one of it.

**The channel prefixes are copied, and that was the deciding constraint.** `compile_module` publishes
these as `resolution: …` and `strict resolution: …`, and that text is what a consumer greps
(`@warning-text-is-api`). Emitting the bare sentence from the pre-flight would have changed the
published string on every module that carries one — so only the channel label is restated, and a test
asserts `set(validate.errors) == set(compile.errors)` rather than "validate also said something".

**Refused: re-deriving the check in the pre-flight.** A second implementation beside the first is the
drift the shared predicate exists instead of, and it is what `unresolved_subjects`'s docstring already
argues at length one function up.

**The ambiguous arm rode along** because it is the same loop and the same key bug, one severity down:
`strict`-only, so `validate --strict` is where it has to appear. `compile_module` runs its pre-flight in
`best_effort` whatever its own mode, so the strict arm there is `validate --strict`'s and the compile
reaches the identical text by its own path.

## RM208 — two clients put the translation inside the retry, so one never retried and one never translated

**Severity** high · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: the
`_request`/`_get` split on two clients; no schema change) · **Owner** enricher · **Motivating case** the
2026-09-11 blind re-derivation round — `docs/audit/ENRICHER_FROM_CODE.md` D10 and D11

**One root cause, two opposite symptoms**, which is why they are one item. Every other client in the
tier keeps the retrying half in its own function and the translation **outside** it — `eutils._request`
/ `_get`, `cpic._request`, `gnomad._request`. Two clients never got that split, and each broke a
different half of `@client-exception-contract`'s "retry, then translate, both legs".

**`CrossrefClient.exists` never retried.** Its decorator asked for `attempt_floor(3)` on
`(httpx.TransportError, httpx.TimeoutException)`; its body caught `httpx.HTTPError`, the **superclass of
both**, and returned `None`. So a `ConnectError` became a withhold before tenacity could see it.
Measured against a transport that refuses every time: **one** upstream request, not three — and
`attempt_floor`, the knob `@retry-attempt-floor` exists so a deployment can raise, moved nothing at all.

**`GwasCatalogClient` never translated the leg the retry gives back.** `_get` re-raised transport errors
bare so tenacity could match them, which is correct, and with `reraise=True` nothing caught the last one
once the attempts were spent — so `associations_for` raised a raw `httpx.ConnectError` at a caller told
to expect `GwasError`, while the body's own docstring said "Both legs are translated". Measured: the
httpx type, after three attempts.

**The guard is static and walks the package, because the defect is a shape.** Neither instance is
visible in a passing test or in review — the decorator and the `except` are forty lines apart and each
is individually correct. `test_retry_is_reachable.py` walks every `@retry`-decorated function in the
package and refuses any whose body catches an **ancestor** of a type its own decorator retries. A
handler whose entire body is a bare `raise` is exempt by construction, since it swallows nothing.

**It walks the package rather than the roster on purpose.** `test_client_exception_contract.py` could
not have caught either one: `literature.CrossrefClient` and `gwas.GwasCatalogClient` both sat in that
file's named `exempt` set, and a guard that iterates a roster inherits the roster's exemptions — the
RM101 blind spot, one file over. GWAS's exemption is now **removed** rather than re-argued, and the
reason it was wrong is worth keeping: it argued from the type that *is* raised (`GwasError` is both the
client's and the pass's, so no cross-module mismatch), which cannot see a leg raising a different one.

**`gwas` joins `FOUR_OH_FOUR_IS_AN_ANSWER`**, and for its own reason rather than OLS4's: the Catalog
holds only variants carrying a published association, so a 404 is *absent* and `associations_for` turns
it into the empty answer `[]` — the third outcome that has to stay distinct from could-not-ask.

## RM209 — the publish half walked the root-file registry and the pull half did not

**Severity** high · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: one
hand-kept tuple replaced by the registry it copies; no schema change) · **Owner** enricher ·
**Motivating case** the 2026-09-11 blind re-derivation round — `docs/audit/ENRICHER_FROM_CODE.md` D8

**RM198 added `avi_knots.parquet` to `locations.SNAPSHOT_ROOT_FILENAMES` and only one side noticed.**
`upload.py` walks that tuple; `download._provision_snapshot` iterated `(RELEASE_FILENAME,
SNAPSHOT_LICENSE_FILENAME)` inline. So the publisher sent the file and the puller never asked for it.

**The consequence is a lane that cannot be used.** The AVI lane stores no `PHRED` — it is an exact
within-corpus rank, so the 466 KB knot table is what reconstructs it, and `alphagenome check` refuses a
snapshot without that file. `cache pull alphagenome_avi` therefore produced a snapshot whose scores
nobody can rank, which is the one thing RM198 existed to prevent.

**Two docstrings said the opposite in as many words**, which is the part worth keeping: "That file
travels because `SNAPSHOT_ROOT_FILENAMES` names it, not because this function does", and "`_provision_snapshot`
fetches the root files from `SNAPSHOT_ROOT_FILENAMES` for every lane, so this needs no special case".
Both were written when the registry was introduced and describe the design rather than the code — a
registry with a hand-kept copy of itself beside it (`@registry-completeness`), where the copy is the
thing that runs.

**The test asserts the equality, not the file.** What the provisioner *asks the remote for* is compared
as a set against the tuple, so a registry that grows by one is covered without anybody remembering. The
named assertion for `avi_knots.parquet` sits beside it as the second test, because that filename is what
a reader greps after `alphagenome check` refuses. Absence stays non-fatal and `.part` staging is
asserted: a repo publishing none of the three root files still provisions, and leaves no truncated stub.

## RM206 — `LookupClients` had three lazy-build semantics and the call site could not tell which

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only:
one method and one lock on `LookupClients`, `CLIENT_FIELDS` derived, nine legs rewritten onto it, five
public calls closing the bundle they build; no schema change) · **Owner** enricher · **Motivating
case** S92 (just-dna-registry, in CONSUMER_SUGGESTIONS_HISTORY.md), hosting the five `lookup_*`
surfaces behind one process-wide bundle

**What it reproduced.** The bundle's docstring says to hold one because a fresh client per question
discards the pacing state — and six of the eight legs did exactly that whenever their field was
unset: `clients.x or X()`, closed in a `finally`. Two legs (`ensembl`, `grch37`) assigned back onto
the caller's bundle instead. The consumer filled six of eight fields and had an unpaced-egress bug on
precisely the leg whose absence mattered, `pmc_idconv`, which read identically at the call site to
`grch37`, whose absence did not. Their fix was to fill all eight and stop reasoning about it, which
is the right consumer move and the wrong thing to require.

**One path, and the lock that makes the assign-back a property a caller can see.** `ensure(name,
factory)` reads the field under the bundle's own lock, builds on `None`, stores, returns. The name is
checked against `CLIENT_FIELDS` first, because a plain dataclass accepts `setattr` on any spelling and
a typo would build a client per call forever while looking exactly like the lazy path. `close()` walks
the same tuple, derived from `fields()` rather than the hand-kept eight it was
(`@registry-completeness`). The consumer's other candidate — one constructor that fills every field —
was not taken: it makes eight connections for a one-shot `hint trait`, and the property wanted is
*uniform*, not *eager*.

**Ownership follows construction.** With the legs no longer closing what they build, a bundle a
`lookup_*` call makes for itself (`clients=None`) would leak every connection it opened; each of the
five now closes its own in a `finally`, and an injected bundle is never closed by a call. Pinned by a
monkeypatched client that counts its closes across both shapes.

**The CPIC half is the consumer's, and said so.** `pgx_draft.draft_gene` takes `client=`, so a host
shares pacing by holding one `CpicClient` and passing it; a `cpic` field on a bundle nothing in
`lookup` reads would be a promise the module cannot keep, and their snapshot-only answer is a fine
one.

## RM205 — the lookup surface put absolute snapshot paths in its payload

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: one
field on `VariantHint`, two label substitutions, three recording sites; no schema change) · **Owner**
enricher · **Motivating case** S93 (just-dna-registry, in CONSUMER_SUGGESTIONS_HISTORY.md), exposing
`lookup_variant` over HTTP from a box whose layout is not the caller's business

**What it reproduced.** `_lookup_from_cache` wrote `str(reference)` into `hint.checked` and
interpolated the same path into the *unreadable* finding, while the live leg wrote `ensembl-rest` into
the same set. A host therefore scrubbed: every known snapshot path mapped back to its lane name, inside
finding prose too — and, as the consumer said, that audit has to be repeated every time a field is
added and silently stops being complete.

**The shape, taken as proposed.** The set was already half right — `ensembl-rest` is exactly the kind
of member it wants — so the cache case now writes the link's label (`ensembl`, `clinvar`), the finding
reads `{label} snapshot unreadable: …`, and the path moves to a structured field, `snapshots`, keyed
by the same labels and filled for every snapshot the lookup opened or tried to open, the clin_sig and
PubMind legs included. That makes the payload safe by construction: one field carries a path, a host
drops it, nothing else is audited.

**A behaviour change on a read field, and why it is not a break.** A reader that matched the old
`str(path)` members of `checked` now sees lane names. `checked` is documented as *what was consulted*
and the consumer who reads it asked for this; a path in it was the defect, and the value that
replaced it is the one `ensembl-rest` already set the pattern for. The path is not lost — it moved.

**What stays.** `_brief(exc)` is duckdb's first line and may name the file; that is upstream's
sentence, kept as evidence rather than rewritten, and a host that scrubs has one predictable place
left to look rather than an audit.

## RM204 — `cache status` was CLI-only, so every consumer re-derived the projection it renders

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only:
one dataclass and one function in `caches`, `cache status` rendering from it, one new rendered state;
no schema change) · **Owner** enricher · **Motivating case** S91 (just-dna-registry, in
CONSUMER_SUGGESTIONS_HISTORY.md), serving `GET /caches` from a box holding some of the snapshots

**What it reproduced.** RM176 made the registry a walked list and left its status half as the loop
inside `cli.cache_status_()`: `resolve()`, `release_label()`, print. A consumer serving the same answer
over HTTP wrote the loop again, and had already been bitten at exactly this spot — their two
projections drifted by seven lanes. Two projections of one registry is the shape RM176 exists to end,
and this one was ours.

**The third state, and why the name is `occupied` rather than the consumer's `partial`.** A directory
that exists, is non-empty and holds no snapshot is the target `prepare_lane` refuses to build over
(provisioning never deletes), and `cache status` rendered it as `absent` — an instruction to run a
pull that was going to decline. The consumer renders it `partial`. Not taken, because the state is
defined by a fact (*holds no snapshot*) and not by a cause: a build that failed after its downloads
is partial, a foreign parquet is not, a stray `.part` beside a deleted payload is neither, and
`prepare` refuses all three alike. `occupied` names what the operator has to do — move it aside —
without guessing what put it there. `LANE_STATES` is a closed set of three, so a renderer can walk it.

**`looked_in` is on the record because status and prepare do not read the same directory.**
`resolve()` reads the lane's `env_var` first; `prepare`'s refusal is about `default_dir()`. An override
pointing at a junk directory reads `occupied` here while `prepare` would build into an empty default
that the override then hides, so the status names which directory its verdict is about rather than
leaving the operator to guess between two.

**The two rendered lines that existed are byte-identical** (`@warning-text-is-api`: `test_pubmind_cli`
greps one of them, and an operator's script may grep either), and the present-and-unreadable
`release.json` case moved from an inline `if` in the CLI to a field, `release_unreadable`, so a
consumer gets it without re-deriving that check too.

## RM203 — `PacingGate` could not report what it spent

**Severity** low · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-enricher` only: one
integer field on `PacingGate`, one increment under the existing lock; no schema change) · **Owner**
enricher · **Motivating case** S95 (just-dna-registry, in CONSUMER_SUGGESTIONS_HISTORY.md), building a
caching proxy that meters egress per upstream

**What it reproduced.** The gate is the one object every egressing client waits on, and it recorded
nothing but `last`. A host wanting to charge a caller for the upstream calls its request actually made
had to charge by the request's shape instead — an upper bound it had to label as one, and one that
bills for a call a snapshot hit never made.

**The counter, and what one increment means.** `spent` is bumped inside the slot lock, so it is exact
under the thread sharing S15 made a contract. Its unit was checked rather than assumed: `gnomad._post`
and `eutils._request` call `wait()` inside their `@retry`-decorated body, so one admission is one
upstream **attempt**, and a 429 retried three times counts three. That is the honest number for
metering — the attempts are what the upstream saw.

**Refused: a `waited` total.** Not asked for, and the sleep happens outside the lock by design (the
lock covers the bookkeeping, not the wait), so a seconds-slept total would need the lock re-taken
after the sleep or a planned wait recorded before it. Neither is worth a second number nobody asked
for; a host that wants it can difference two clock readings around the call.

## RM201 — a declared correction said what a release did, never which modules it did it to

**Severity** medium · **Status** ✅ shipped 2026-09-11 in the uncut 0.7.0 (`just-dna-format` only: one
optional field on `DeclaredChange`, one predicate, one filter on `RecompileAnswer`, three declarations
filled; no parquet, manifest or vocabulary change) · **Owner** format · **Motivating case** S90
(just-dna-registry, in CONSUMER_SUGGESTIONS_HISTORY.md), found adopting `needs_recompile` for a
re-publish sweep

**What it reproduced.** `DeclaredChange` had five fields and none of them stated reach. Over
`0.6.6 → 0.7.0` the corrections are `gene_validity.classifications` (RM108) and `gene_metrics.parquet`
plus `gene_metrics.signature` (RM110); each `detail` names the block it reaches in prose, and the model
could not, so a sweep routing on `kind == "correction"` minted a fresh immutable PATCH for every module
in a catalogue to repair a value most of them never carried. The consumer's two pre-checks were right
too: `unmeasured` is a different axis (a module the sweep could not compare, not a change that applies
to a subset), and `AUTHORED_ROW_DERIVED_FIELDS` cannot help because a compiled parquet is nothing a
consumer can recompute locally.

**Why the consumer was right to refuse the workaround.** `target` is spelled three ways — a dotted
manifest path, a parquet filename, `file:column` — and reading its first segment as "the block a module
must carry" works until a fourth spelling arrives, silently. That is a consumer re-deriving a rule
from a field's spelling, and the rule is ours to state.

**The shape, and the two candidates refused.** The consumer proposed `requires_block: str | None` with
`None` meaning *every module*. Refused on the algebra: `None` is never a definite answer here, and the
case that proves it is already in the table — RM121's `stats.genes` correction reached a real subset
(modules whose lead table named no gene while another table did) that presence cannot spell, because
every module carries the field. That correction must be able to say *unstated*, and a consumer must
keep it; making `None` mean *every module* would make the honest answer and the definite one the same
value. So `requires: tuple[str, ...] | None` — a conjunction of dotted manifest paths, spelled as
`manifest_fields` spells them, `()` for every module, `None` for unstated. A prose `applies_when`
beside `RosterEntry.condition` was the second candidate and was not taken: the roster's condition is
checkable because `compilation.dropped_rows` shipped, and a prose-only reach here would be readable by an
operator and filterable by nobody, which is the state the report describes.

**A necessary condition, said out loud.** `("gene_metrics",)` over-approximates RM110's true reach —
the snapshot route, `@constraint-two-releases` — in the safe direction, so `reaches()` is documented
asymmetrically: `False` is the certain answer and the only one acted on, `True` is *not excluded by what
the record states*, `None` is unstated. `declared_for` drops only `False`, the Kleene fold, because the
two mistakes cost differently — a change kept needlessly is one wasted version number, bounded by the
self-interval; a change dropped wrongly is a module serving a value we have said is wrong.

**Forced rather than defaulted.** The record's own rule is that the measurement forces the declaration;
this field gets the same treatment one level down: a test asserts, as an **equality**, that the
corrections with an unstated reach are exactly RM121's pair, so a correction added without deciding its
reach fails the suite instead of reading as unstated. Every required path is walked against the
manifest models by the test helper `manifest_fields` already uses, not a second walker. The grammar's
boundary is on the field: presence of a path is all it says, and a value or membership predicate would
be a separate field, audited per Principle 5 rather than grown onto this one.

## RM202 — a `publish_repo` that nothing could reach, and the guard that was missing on one side

**Severity** medium · **Status** ✅ shipped 2026-09-11 (`just-dna-enricher` only: one CLI command, one
lane field, one guard) · **Owner** enricher · **Motivating case** the maintainer asked for the publish
command and there wasn't one

**What was wrong.** RM198 wired `alphagenome_avi`'s `publish_repo`, asserted the field was set, and
shipped. `cache rebuild --publish` walks lanes that have a **`rebuild` adapter** — which is every
publishable lane but this one, because its source sits behind an eligibility gate and there is nothing
for an unattended rebuild to fetch. So the lane advertised a repo that no command could send anything
to, and the only generic publisher was `clinvar publish`, which is the wrong name to hand an operator
for AlphaGenome.

**Why the tests passed.** They asserted the registry's *data* — `lane.publish_repo is not None`,
`lane.unpublished is None` — and the one publish test called `plan_reference_snapshot` **directly**,
bypassing the CLI. Nothing invoked a command. `@registry-completeness` is usually about a list that
falls behind the set it lists; this is its neighbour: **a field can be set correctly and mean nothing,
if no path acts on it.**

**The guard already existed on the other side, which is the sharp part.**
`test_every_build_command_the_registry_names_is_one_the_cli_answers_to` walks the real Typer tree for
every lane's `build_command`, and it exists because `cache status` once printed two commands that do
not exist. The publish side had no equivalent, so the same class of defect had one door open.

**What shipped.** `just-dna-enricher alphagenome publish`, a `CacheLane.publish_command` field, and
`test_every_publishable_lane_can_actually_be_published` — which asserts the **biconditional**: a lane
with a `publish_repo` is reachable by a rebuild adapter **or** by its own publish command, exactly one
of the two, and if it names a command that command answers `--help` in the real CLI. A lane that names
a publish command with no repo fails too.

Measured while scoping it: of nine lanes with a `publish_repo`, eight ride `cache rebuild --publish`
and `alphagenome_avi` was the only unreachable one. The hole was exactly one lane wide, which is why
nobody had met it.

## RM199 — the description is the last thing a publish sends

**Severity** medium · **Status** ✅ shipped 2026-09-10 (`just-dna-enricher` only: a size threshold,
a two-phase publish, one registry reordered) · **Owner** enricher · **Motivating case** the AVI lane
is 32 GB and `upload_folder` is a single atomic commit with no resumption

**Revised the same day it shipped, by a deprecation warning in a real publish.** The size branch
below is **gone**: `huggingface_hub` 1.x makes `upload_folder` multi-commit itself and deprecates
`upload_large_folder`, which now emits a `FutureWarning` naming `upload_folder` as the replacement.
So the threshold, its two constants and the whole large path are removed, and one `upload_folder`
carries every payload.

Two consequences worth keeping. **The RM186 collision dissolved rather than being solved** —
`upload_folder` takes `delete_patterns`, so a declared retirement rides the payload call again and
the refusal this function used to raise is deleted; a guard now asserts the retirement is on the
payload commit at 6 GB as well as at 1 KB, since a small-snapshot test would not have exercised the
branch that used to exist. And **the one-commit guarantee is upstream's business now**: a large
upload is several commits either way, so it holds for payloads that fit in one and is the Hub's to
keep for those that do not. That is a weaker promise honestly stated rather than a strong one
quietly broken.

The lesson is the ordinary one and it still cost a revision: **heed terminal warnings, deprecations
especially.** This one appeared the first time an operator ran the command against a real repo, and
nothing in the test suite would ever have raised it — the tests mock `HfApi`, so a deprecated method
on a `MagicMock` warns about nothing.

**Two changes, and only one of them is about size.**

**`release.json` goes last, on every path.** It is what a puller reads to learn which release it
holds, so a publish that lands the description and then fails leaves a snapshot that *reads as*
provisioned and is not — `@a-publish-may-not-orphan-the-bytes-it-stops-describing` reached from the
other direction. The payload is one commit and the description is a second, which costs one extra
commit on a path that was already going to be several.

**The ordering lives in `SNAPSHOT_ROOT_FILENAMES`, not in the publisher.** Putting
`RELEASE_FILENAME` last in the tuple means the plan a `--dry-run` prints is already in the order the
upload sends, so the two cannot disagree. That is the same lesson as `@publisher-allowlist-derived`
one turn further on: the promise and the act are one list.

**Above 5 GB the payload goes through `upload_large_folder`.** Not a performance dial — an atomicity
one. `upload_folder` is a single commit with no resumption, which is right for a snapshot measured
in megabytes and wrong for 32 GB, where a transport failure at 30 GB starts over. The large uploader
chunks, retries per file and resumes, at the cost of **not being atomic**, which is exactly why the
threshold exists rather than always using it. Every lane but AVI is orders of magnitude below it.

**A collision between two rules, refused rather than resolved silently.** RM186 promises that a
declared retirement rides in the *same commit* as the file replacing it, so a reader never sees the
repo with neither or both. `upload_large_folder` takes no `delete_patterns` and is inherently
multi-commit, so that guarantee cannot be honoured on the large path. The publish **raises**, naming
both rules, rather than quietly doing the deletion in a separate commit and leaving exactly the
window RM186 exists to close. No lane is in that state today; the refusal is there for the one that
will be.

**A second copy of the root-file bug, fixed in passing.** `plan_reference_snapshot` has two
branches, and only the parquet one had been moved onto the registry by RM198 — the payload-only
branch (STRchive, ACMG) still carried its own hardcoded pair, so a lane of that shape gaining a root
file would have dropped it exactly the way the parquet branch dropped `LICENSE.txt`. Both walk the
registry now.

**What the tests pin.** That the union of the two commits equals the plan, because splitting an
upload may not drop a file; that `release.json` is in the second call and not the first; that a
sub-threshold snapshot still goes out unchanged; that the large path is chosen by **measuring the
payload** rather than the directory, so a description cannot tip the decision; and that a retirement
on the large path refuses **before** either uploader is called.

## RM197 — the ALT column that a proof made unnecessary

**Severity** low · **Status** ✅ shipped 2026-09-10 (`just-dna-enricher` only: the lane's parquet
schema, a widening step, a public `to_long`, five tests; no consumer-visible join change) · **Owner**
maintainer · **Motivating case** the lane is published to HuggingFace now (RM198), so transfer size
binds where local disk never did

**What shipped.** One row per position with three ALT-score columns, and **no stored `alt`**:
`chrom, pos, ref, alt0, alt1, alt2`. **3.371 B/row against 3.882 long — 29.7 GB rather than 34.2**, a
13% saving that is simply not writing `pos` three times. `pos` costs 1.249 B/row even perfectly
delta-encoded, so it is the whole of the difference.

**The column disappears because of a proof, not an assumption.** Which base each column means is
`{A,C,G,T} − ref` ascending — a function of `ref` alone, so nothing has to travel beside the data.
That is only well-defined if every locus really carries all three, which was measured over the whole
corpus before anything changed: across 24 contigs and **8,812,917,339 rows**, `rows == 3 × distinct
positions` exactly (2,937,639,113 of them), `pos` sorted, `alt` strictly ascending within a position,
and **no `alt` equal to `ref`** — so three *distinct non-ref* bases must be all three of them. Zero
violations.

Two earlier attempts at that check were **OOM-killed**: `group_by(pos).agg(...)` and `n_unique` both
have to hold billions of keys. Counting boundaries in a sorted column holds nothing, and did the
whole genome in 178 seconds. The measurement technique is the transferable part.

**It is not a schema break, and that is the point.** `to_long()` recovers `(chrom, pos, ref, alt,
score)` rows from the stored ones with no lookup table, so `alphagenome_check`'s join is unchanged —
it converts the handful of rows it already filtered to. The test proves the round trip against **the
published source text**, not against another derivation of the same parquet.

**A proof taken once is a proof about the artifact that existed then**, so the builder re-runs it on
every build and **refuses** a locus that breaks it. Padding a missing ALT with a null would silently
redefine what `alt1` refers to at that locus — a table that reads fine and answers wrongly, which is
the failure mode this whole round kept meeting.

**The defect the genome-wide build found, and every test in the file passed while it was there.**
`_stream_lines` yields whole *lines*; a locus is three lines. So a chunk boundary falls inside a
position roughly once per chunk, `_widen` saw two ALTs where the file has three, and the build
refused at `chr1:1196920` — a locus the source carries in full. The docstring on `_widen` asserted
the opposite ("a chunk boundary cannot split a locus"), which is the same shape as everything else
this round found: a plausible claim nobody had checked.

`_build_contig` now carries the trailing partial locus into the next chunk and emits the final one
after the loop — without that second half every contig would silently lose its last position. The
fix belongs there rather than in `_widen`, which cannot tell a truncated locus from a malformed one
and should not guess.

**The fixture could not see it.** The committed slice is 4 MB and the chunk size is 64 MB, so every
test built in one chunk. The regression test builds the *same slice* at 64 KB — hundreds of split
loci — and asserts the table, the knot table and the row counts are identical to the single-chunk
build, including that the contig's final position is still present. Demonstrated failing on the
unfixed code before being kept: it refuses at `chr22:20000624`. An assertion that the build merely
*succeeds* would have been satisfied by dropping the partial rows.

**What was measured and rejected.** One column per base with the ref slot null — the obvious
alternative — is **worse**: 3.677 B/row, because the nulls cost more than dropping `alt` saves. And
setting `row_group_size` explicitly remains worse at every value tried; the default adaptive sizing
is what responds to the data.

## RM198 — the lane that publishes a file the publisher did not know how to carry

**Severity** medium · **Status** ✅ shipped 2026-09-10 (`just-dna-enricher` only: a layout registry,
a provisioner, a repo id, three lane fields) · **Owner** enricher · **Motivating case** the AVI lane
became publishable when RM195 closed, and wiring it found the publisher would have dropped the one
file that makes the snapshot usable

**What it wires.** `ensure_alphagenome_avi_snapshot`, `DEFAULT_ALPHAGENOME_AVI_REPO_ID`, and the
lane's `ensure` / `publish_repo`, with `unpublished` removed — the roster asserts that
biconditional, so a lane cannot both publish and excuse itself. `cache status`, `cache pull`,
`prepare` and `upload` all pick it up from the registry with no per-lane branch, which is what
RM176's registry was for.

**The lane is still the odd one out on the build half.** `rebuild` stays `None` with its `unbuilt`
reason intact: this tier cannot fetch the 88.5 GB source, because the eligibility clause bars
classes of holder outright. So it is **pullable without being buildable** — an operator who may not
download the artifact can still provision the re-encoded snapshot, which is the entire point of
publishing it.

**The defect it found, and it is the third of its exact shape.** `plan_reference_snapshot` collected
`data/*.parquet`, the sidecar *directories*, and then a **hardcoded pair** — `release.json` and
`LICENSE.txt`. `avi_knots.parquet` is a root-level sibling of `data/`: one small parquet, not a
directory of them. It would have been dropped silently, and the published snapshot would have looked
complete — every score present, `release.json` valid — while **nothing on the other side could
reconstruct a `PHRED`**, because the artifact deliberately does not store one. `alphagenome check`
refuses such a snapshot outright, so the failure would have surfaced far from its cause.

That pair was itself a repair: `LICENSE.txt` is only in it because publishing a share-alike snapshot
had already gone out without the terms it exists to carry (`@publisher-allowlist-derived`). So the
names moved to `locations.SNAPSHOT_ROOT_FILENAMES` and the publisher walks them — the same move
`CACHE_LANES` is, one layer down. A fourth such file added to a lane and not to the registry now
fails a test rather than a publish.

**What the test asserts** is the walk over a **real built snapshot**, not the constant against
itself: the plan for the fixture build must contain the knot table, and every root file actually on
disk must be carried. A test comparing `SNAPSHOT_ROOT_FILENAMES` to a literal would have passed
while the publisher ignored it.

## RM196 — the repository stopped carrying somebody else's source and started carrying a pin

**Severity** medium · **Status** ✅ shipped 2026-09-10 (`just-dna-enricher` only: a build-backend
change for that package, a resolver, a build hook, five files removed from `docs/vendor/`) ·
**Owner** maintainer · **Motivating case** `pip install just-dna-enricher[atlas]` installed two
packages and then could not import the client

**What it was.** RM192 vendored upstream's `.proto` sources and generated the bindings into a
git-ignored tree. Neither `docs/` nor `generated/` is in a wheel, so an installed package had no
sources to generate from and no bindings to import: the extra worked from a checkout and nowhere
else. The client's import was guarded and named the command, which made the failure legible rather
than absent, but it was still a broken install path.

**What was measured before choosing.** Three things, and two of them shrank the problem:

- **The build backend is declared per package.** The ROADMAP entry said changing it "touches how all
  three packages are built"; that was wrong. `just-dna-format` and `just-dna-compiler` stay on
  `uv_build` and only the tier that runs `protoc` moved.
- **`hatch-protobuf` cannot do this job**, checked rather than assumed: its options are
  `generate_grpc`, `generate_pyi`, `generators`, `import_site_packages`, `library_paths`,
  `output_path` and `proto_paths`, and **none rewrites an import**. The rewrite is the entire safety
  property — without it the generated package is literally named `alphagenome` and shadows the real
  wheel — so the plugin would have produced exactly the artifact
  `test_the_generated_bindings_do_not_shadow_the_upstream_package` exists to prevent.
- **A custom hatchling hook does**, in about thirty lines, which is what upstream AlphaGenome itself
  does for the same reason.

**What shipped, and it is not any of the three options the entry listed.** The maintainer's shape:
the repository carries **neither the sources nor the bindings — it carries the pin.**
`atlas_protos.fetch_protos()` downloads the five files from `google-deepmind/alphagenome` at a
pinned commit and verifies each against a recorded sha256; `hatch_build.py` runs that and `protoc`
at build time; and both trees are **git-ignored and deliberately not build-ignored**, so an sdist and
a wheel carry the files while the repository's history does not.

**Why a commit id *and* a digest.** A commit id proves what git had; a digest proves what arrived.
The fetch crosses HTTPS to a CDN, and a pin is worth exactly what something checks it against — the
same reason `SourceRow.license_sha256` exists. A file already on disk and matching is left alone, so
the build is offline after the first run; a file that does *not* match is re-fetched rather than
trusted, because the only thing worse than no pin is a pin nobody acts on.

**Three defects the real build found**, none of which a plan would have:

- The Apache-2.0 `LICENSE` is at upstream's **repository root**, not beside the protos. A
  single-directory assumption 404s on it, so the pin maps each file to its own upstream path.
- Hatchling globs `LICEN[CS]E*` for the **package's own** `License-File` metadata, so a fetched file
  called `LICENSE` was both added to the archive twice *and* advertised as `just-dna-enricher`'s
  licence — which it is not. It ships as `alphagenome_apache-2.0.txt`, outside the glob.
- `force_include` duplicated every file, because the trees sit **inside** the declared package and
  hatchling already walks it. `artifacts` is the mechanism for build-time output that lives in the
  package tree and is deliberately absent from version control.

**Verified from a clean venv**, not from the checkout that built it: the wheel installs with
`grpcio` and `protobuf` alone, the bindings import, the service config and upstream's notice are
present, and `importlib.util.find_spec("alphagenome")` is `None` — no shadowing.

**What `docs/vendor/` keeps.** The four terms documents and the download page, and the README there
now says why: those are **evidence about licensing**, which is exactly the kind of file that should
be frozen in the repository rather than re-fetched. Upstream's source code is the opposite kind.

## RM195 — the most consequential claim about a source, resting on a page nobody had saved

**Severity** medium · **Status** ✅ resolved 2026-09-10 (`just-dna-enricher` only: one `SourceTerms`
field, one pinned vendor document, two tests) · **Owner** maintainer · **Motivating case** RM191
needed to state whether AVI may be used commercially, and no document in the repository said

**What it was.** The AlphaGenome Services Additional Terms **define** a "Permissive Use Downloadable
Artifact" class and grant it commercial use outright — then delegate **membership** of that class to
the download section of the Atlas website. Four terms documents were pinned in `docs/vendor/` and
none of them named a single artifact. The page is a sign-in-gated single-page app that serves 185 KB
of navigation chrome to `curl`. So the claim "AVI may be sold" — the most consequential single fact
about this source, and one that would sit inside a signed module's attribution ledger — rested on
one reading of one page the repository could not check.

**What shipped in the meantime, and why it was not a placeholder.** `commercial_use=None`. Unknown is
a value, `None` is never `False`, and `@no-named-licence` already settles what follows: unknown
commercial terms **warn** rather than gate. So a module carrying AVI compiled under
`declared_use=commercial` with a warning, rather than either refusing or silently asserting a
permission nobody had established.

**What resolved it.** The maintainer saved the page from a signed-in browser. It carries its content
as **embedded JSON rather than markup**, which is why fetching it had failed and why the extraction
beside it is the greppable half:

> `"Permissive Use Downloadable artifacts for commercial and non-commercial use"` — **AVI SNV
> scores**, `avi_scores_snvs_tabix.zip`, 88.5 GB
>
> `"Downloadable artifacts for non-commercial use only"` — AlphaGenome SNV merged splicing scores
> (20.6 GB), AVI SNV feature importance scores (283.9 GB)

**It confirmed the probe's reading rather than overturning it**, which is worth stating plainly:
four of that document's claims had already been refuted by measurement, so the prior was not good.
It is also independent confirmation of why `alphagenome_avi_build` refuses the other two artifacts by
name — they really are a different licence class.

`commercial_use=True`. The page is pinned as `docs/vendor/alphagenome_download_page.html.gz` (1.1 MB
gzipped, from 7.1 MB — the complete document travels rather than an excerpt, and it stays under the
Git LFS threshold) with `alphagenome_download_page.txt` beside it carrying the extraction and the
uncompressed `sha256`. The test asserts against **those bytes**, not against a constant: if the file
is dropped, or upstream reclassifies and it is re-saved, the test fails rather than going on
asserting yesterday's permission.

**`redistribution=True`, and it is the one value on this row that rests on judgement.** The page
classifies **use**, not sharing. Prohibition 1 separately bars passing Output to a commercial
organization "aside from indirectly via a scientific publication, open source release or to support
journalism", and **the maintainer read an openly published snapshot as an open source release within
that carve-out** on 2026-09-10. No document in `docs/vendor/` says so in as many words, which is why
this entry names the reading as a reading.

What makes it defensible in practice rather than only in principle is restriction 3b, which this
lane already honours in fact: a published snapshot carries the "Use restrictions" section as
`LICENSE.txt` beside the data, so a puller receives the terms *with the bytes* rather than a link to
them, and `license_sha256` pins which version they got.

**The three axes now rest on three different kinds of ground**, and the row cannot show that — a
consumer reading `sources.csv` sees three booleans. `commercial_use=True` and `share_alike=False` are
documented; `redistribution=True` is decided.
`test_the_three_permission_axes_each_rest_on_a_different_kind_of_ground` is where that distinction is
written down, so anyone revisiting the reading knows which of the three to revisit. Wiring the lane
into `cache pull` / `upload` is **RM198**.

## RM193 — the three questions a nine-billion-row file on your own disk cannot answer

**Severity** medium · **Status** ✅ shipped 2026-09-10 in the uncut 0.7.0 (`just-dna-enricher` plus
one new `VALID_VERIFICATION_CHECKS` member in `just-dna-format` — additive, minor-legal under P3/P8;
no column, no table, no manifest field) · **Owner** enricher · **Motivating case**
[PROPOSAL_0_7_PT4](proposals/PROPOSAL_0_7_PT4.md#rm193--the-atlas-as-a-resolver-edge-cases-and-refusals-as-findings)

**What shipped.** `alphagenome_check.py` and `just-dna-enricher alphagenome check <spec>`, plus the
`variant_impact_agreement` check member. Reports, never repairs
(`@enrichment-is-validation`).

**Most of it never touches the network, and that is the design rather than a fallback.** Without
`--threshold` there is no question RM191's snapshot cannot answer, so the pass is entirely offline.
With one, the knot table says — **from 466 KB, before a single request** — which variants sit inside
a `PHRED` interval spanning the cut, and only those are asked about. `threshold_is_safe()` answers
the prior question ("can I cut here at all?") for the same 466 KB, and genome-wide the answer is yes
at every integer threshold from 1 to 50 except 3.

**The refusal is the item's spine.** Rebuilding the `PHRED` column by RPC is 272 days and ~92 M
requests at the measured rate, and prohibition 3 governs the result, so a check that could start
down that road has to stop. `refinement_cap` refuses **before any request is spent**, and the
message names the knot table — because what the caller actually wants, which rows are affected and
by how much, is already on their disk. `test_an_unbounded_refinement_is_refused_and_names_the_cheaper_answer`
asserts the stub's call log is empty, not merely that an exception was raised.

**Four no-answer reasons, kept apart** (`@answered-is-not-absent`, `@unreachable-not-absent`):
`ref_mismatch` (the Atlas validated `REF` against GRCh38 and **named the real base**, which
`@va-omits-ref` says only this tier can discover), `not_scored` (an indel, or a quantile saturated
off the top of the `float32` scale — the artifact reaches `PHRED` 89.451 where the API caps at
72.247), `unreachable` (asked, no answer — and deliberately **no finding**, since a bad minute at
Google is not a claim about the caller's data), and `offline`/`no_client` (nobody asked). A fifth,
`absent_from_snapshot`, is the local artifact's own silence. None of them is a zero, which matters
at a scale where the corpus holds 672,931 genuine ones.

**It emits its own check member rather than a second `reference_allele`.** The Atlas answers the
`REF` question too, but that check belongs to `enrich` and compares against the reference
*sequence*; letting an Atlas outage write a skip against it would make one registry's availability
speak for another's question (`@one-registrys-outage-may-not-speak-for-another`). Two sources, two
checks, side by side.

**A silent-wrong-answer bug the tests caught, and it is the kind worth recording.** `VariantRow`
normalizes `chrom` through `vrs.normalize_chrom` and stores `22`; AlphaGenome ships UCSC-style
`chr22` and indexes it that way. Joining the module's spelling straight onto the snapshot matched
**nothing** — and produced no error, just every variant reported `absent_from_snapshot`, which reads
exactly like an artifact that does not cover them. Found only because a test asserted a *positive*
count rather than the absence of a crash. `artifact_contig()` converts at the boundary, one
direction, and a test asserts the two spellings give the **same** answer rather than that neither is
empty.

**The `[atlas]` extra stays optional, and a test proves it in a subprocess.** `atlas_client` imports
`grpc`, so a module-level import anywhere on the CLI's import graph would make RM192's 19 MB extra a
requirement of the whole tier — undoing the thing RM192 measured its way out of. Both `cli.py` and
`alphagenome_check.py` guard it, the latter binding a never-raised class rather than `None` so the
`except` arms stay well-formed. Checked with `grpc` blocked at `sys.meta_path` in a child process,
because in this environment the extra *is* installed and an in-process assertion would pass for the
wrong reason — the same trap `test_imports_stay_within_the_declared_floor` avoids with an AST walk.

**What it does not do.** No new stored column from any of the Atlas's other 21 scorers. They are
ordinary Output — non-commercial, notice-bearing — so they may enter as *findings* under
`declared_use=non_commercial` and never as values, and the existing data-driven gate needs no new
axis for that.

## RM191 — nine billion scores, and the column that is a function of another column

**Severity** medium · **Status** ✅ shipped 2026-09-10 in the uncut 0.7.0 (`just-dna-enricher` only:
a new builder module, a new cache lane, a new CLI command, a new `SourceTerms` entry; no model, no
authored column, no manifest field) · **Owner** enricher · **Motivating case**
[PROPOSAL_0_7_PT4](proposals/PROPOSAL_0_7_PT4.md#rm191--the-avi-derived-artifact-an-int32-parquet-plus-the-knot-table), against
[ALPHAGENOME_ATLAS.md §§ 1.4, 4.4–4.9](probes/ALPHAGENOME_ATLAS.md)

**What shipped.** `alphagenome_avi_build.py` and `just-dna-enricher alphagenome build --input`,
writing `<out>/data/alphagenome_avi-<contig>.parquet` + `avi_knots.parquet` + `release.json` +
`LICENSE.txt`, and a fifteenth `CACHE_LANES` entry. `--input` is required and there is no default
URL: the artifact is 88.5 GB behind a sign-in whose eligibility clause bars classes of holder
outright, so acquisition is the operator's act under their own acceptance
(`@acquisition-gate-is-not-a-read-gate`).

**`PHRED` is not stored, and the 466 KB that replace it are the item.** Measured over all
8,812,917,339 rows, `PHRED ≥ p` keeps `10^(-p/10)` of the corpus to four significant figures across
four decades — it is an exact within-corpus rank, a function of `raw_score`, and 24.7 GB of it. The
knot table carries the curve instead, and it carries the *interval* rather than a point: the
artifact prints `raw_score` to four significant digits and `PHRED` to six, so one printed score can
span many ranks. Publishing a midpoint would turn a measurable ambiguity into an invisible one.
**That interval is what makes threshold safety decidable** — a threshold is unsafe iff it lands
inside a knot's span, checkable from 466 KB without reading a data row. Genome-wide, **exactly one
knot straddles any integer threshold from 1 to 50**: `0.00076`, 676,356 rows, `PHRED` 2.99961 to
3.00027. Every other threshold is decided.

**Two measurements corrected the proposal, and both are recorded rather than worked around.**

- **Size — and the correction is the finding, not the number.** The first build measured **4.878
  B/row → 43.0 GB** and this entry said so, adding that the proposal's 34.4 GB "reproduces in
  neither layout". **That was wrong, and it was wrong because the measuring instrument was the
  defect.** The builder assembled each contig with `scan_parquet(...).sink_parquet(...)`, which
  fragments the result into one arrow chunk per morsel — 1,432 for chr22 — and parquet writes at
  least one row group per chunk, inside each of which a sorted `pos` has almost no run left to
  delta-encode. Varying nothing but the chunk count on the same frame: **1–64 chunks 3.871 B/row,
  128 chunks 3.904, 1,432 chunks 4.892**; `pos` alone goes 1.249 → 2.067. Reproduced independently
  on a different slice, where the cliff sat between 512 and 1,432 — around twenty-odd thousand rows
  per chunk both times, which is why the cap ships as a rows-per-chunk floor as well as a chunk
  count. The shipped builder assembles in bounded groups and measures **3.882 B/row → 34.2 GB**, so
  the proposal's figure was right all along.

  Two things fell out of it. `row_group_size` set explicitly is **worse at every value tried**
  (4.7–5.1 B/row) — the default adaptive sizing is what responds to the data, so the obvious tuning
  knob is the wrong one. And a wide-by-position layout measures ~29.7 GB against ~34.2, a real but
  much smaller gap than the first (bugged) comparison implied; **RM197 carries that as an open
  question rather than as a 31% saving over a number that was never real.**
- **Losslessness is about the decimal, not about a float round-trip.** `Int32`×10⁵ is exact for a
  value printed to five decimals, and the builder *checks* it — `_scaled_scores` refuses a value
  that does not land on the grid rather than rounding it, so the guarantee holds over every row
  written rather than over the 900,003-row slice it was measured on. But recovering a float with
  `raw_score_e5 / 1e5` disagrees with `float(printed)` on **53% of rows**: the division rounds a
  second time and lands one ulp off. The test compares in `Decimal`, and both the module docstring
  and the test say why — asserting it the obvious way would have weakened the claim to whatever a
  tolerance admitted.

**What the tests pin**, all against a committed 1.2 MB slice of the real artifact
(`assets/alphagenome/avi_chr22_slice.tsv.gz`) with expected values re-derived from its own text:
the decimal round-trip; the refusal when a score carries more precision than the scale; that
`PHRED` is absent from the parquet and present in the knots; that `sum(n)` over knots equals the
rows written **and** every stored score has a knot; the threshold-safety property at seven
thresholds with zero misclassifications; and that the one straddling knot really has rows on both
sides of 3.0 — without which the safety test would be `@tautology-zero`, which is why the slice was
cut around that locus rather than anywhere.

**Built genome-wide, and every number cross-checks against something measured independently.**
The 88.5 GB artifact re-encodes in **85 minutes** on twelve tabix streams to **34,291,319,173 bytes
over 24 parquets — 3.891 B/row**:

| | built here | measured elsewhere |
| --- | ---: | --- |
| rows | 8,812,917,339 | the probe's corpus size, § 4.4 |
| knots | **41,474** | 41,474 — the sibling session's independently-built table |
| negative `raw_score` | 4,344,533,049 (49.30%) | 49.30%, § 1.4 |
| genuine zeros | **672,931** | 672,931, § 1.4 |
| straddling knots | **1** (`0.00076`, n=676,356, PHRED 2.99961–3.00027) | 1, and only at threshold 3 |

The knot table was compared against `docs/probes/alphagenome_knots/avi_knots.parquet` — built by a
different session, from a different pass over the same bytes — knot by knot rather than by count:
**zero raw values in one and not the other, zero `n` disagreements, zero `phred_lo` disagreements.**
`source_sha256` is `46434eab0ddc73ef…`, and `release.json` pins the artifact's own 2026-08-27 stamp,
which is what § 2.7c resolves the applicable terms against.

**Two defects the real artifact found that no fixture could.** `pl.len()` is `UInt32`, so summing
the per-contig knot tables wrapped 8,812,917,339 to 222,982,747 — exactly `− 2·2³²` — and only the
reconciliation guard saw it, after 65 minutes of building. And `read_local_scores` joined before
filtering, which on 34 GB is not slow but fatal: the first smoke test was killed by the OOM killer
on a twelve-variant module. It now selects parquets by contig from the filename and filters `pos`
inside the scan, where row-group statistics skip almost everything; the same query takes 4 seconds.
A third, smaller: `subjects` counted `decided + unanswered` and a straddling variant is legitimately
in both, so a three-variant module published four.

**"No threshold" was the right default, and the evidence arrived after the decision.** The artifact
ships the whole corpus with the sign intact, on the argument that a cut is a consumer's slice. The
ClinVar join measured beside this round (probe § 4.10, 21 of 24 contigs) shows a threshold *is* a
real triage rather than only a size dial — `PHRED ≥ 20` keeps **97.63% of pathogenic** variants
while discarding **94.3% of benign** and 99% of the corpus, 98× the baseline — and it independently
confirms § 4.7's reading of the sign, with **0.16% of pathogenic scoring negative against 34.35% of
benign**. Neither result changes what shipped, and the reason is the caveat attached to them:
ClinVar is an **ascertained** set skewed to coding changes, so part of that enrichment is "AVI
recognises coding damage", and the table is not evidence about regulatory variants. A default cut
baked into the artifact would have carried that bias into every consumer; offering the whole corpus
plus a knot table that says which cuts are *safe* leaves the choice where the caveat can travel with
it.

**Absence is row-absence.** AVI covers ~95% of the assembly and writes 672,931 genuine zeros, so an
unscored position has no row and a scored-zero position has a row holding zero. The test asserts
**set equality over `(pos, ref, alt)` in both directions**, because a count cancels an invented row
against a dropped one.

**Two registry guards caught real defects rather than needing to be widened**, which is the shape
`@registry-completeness` predicts. `test_the_lane_that_reads_its_release_differently_is_exactly_the_one_named`
rejected a `release_label` that was byte-identical to the default — a duplicate that would have
drifted — and it was deleted. `test_every_builder_module_has_a_lane_and_every_lane_but_one_has_a_builder`
rejected a module named for something other than its lane, and the module was renamed to
`alphagenome_avi_build.py` rather than excepted, exactly as its own docstring instructs. That test
also had to be split: **having a builder module and having a `rebuild` adapter stopped being the
same property**, because this lane has the first and cannot have the second.

**`commercial_use` is `None`, not `True`** — see RM195. Unknown is a value.

## RM192 — half a gigabyte of wheel for a service whose scores are plain bytes

**Severity** medium · **Status** ✅ shipped 2026-09-10 in the uncut 0.7.0 (`just-dna-enricher` only:
a new `[atlas]` extra, two new modules, one new CLI command, the `alphagenome` extra deleted; no
model, no parquet, no manifest field) · **Owner** enricher · **Motivating case**
[PROPOSAL_0_7_PT4](proposals/PROPOSAL_0_7_PT4.md#rm192--the-atlas-client-on-two-packages-and-the-alphagenome-extra-deleted), against
[ALPHAGENOME_ATLAS.md § 6.2](probes/ALPHAGENOME_ATLAS.md)

**What it reproduced.** `uv add alphagenome` resolves to **47 packages and 550 MB** — anndata, pandas,
scipy, zarr, h5py, numcodecs, pyarrow, matplotlib, seaborn, pyfaidx, absl-py, fsspec — against a
tier whose entire runtime list is httpx/tenacity/huggingface-hub/typer/ga4gh.vrs. Six of the
twenty declared dependencies are never imported on any scoring path, and `atlas.py` imports
`anndata` at module level, so even the SDK's own import costs 242 MB. CONSTITUTION Goal 2 makes
that a dependency-tier question rather than a disk-space one.

**What the measurement changed.** The probe's first answer was *"a 22 MB client exists and is not
declarable"* — the light path being `pip install --no-deps alphagenome grpcio protobuf`, a
deployment recipe rather than a dependency specifier. Reading the upstream repository refuted the
second half: `github.com/google-deepmind/alphagenome` is Apache-2.0 and ships the `.proto` sources
its own wheel generates bindings from. So the light path **is** declarable, and this is one of the
four claims in that document that upstream prose got wrong and bytes corrected.

**What shipped.** `enricher/src/just_dna_enricher/atlas_client.py` (the three Atlas RPCs with the
transport's exceptions kept inside), `atlas_protos.py` (the generator), `just-dna-enricher atlas
generate`, and `enricher/tests/test_atlas_client.py` — 25 tests, now inside `testpaths`, all 25
green including the four live ones against the real service. Dependencies are the new `[atlas]`
extra: `grpcio` + `protobuf`, measured at **19 MB and +2 packages** in a clean venv on 2026-09-10
(grpcio 1.83.1, protobuf 7.36.1). `grpcio-tools` is build-only and joined `[dev]`; the dev group
gained `just-dna-enricher[atlas]` so the suite collects the moved tests instead of erroring on
`import grpc`. The `alphagenome` extra is gone.

**What kept it honest.** `test_imports_stay_within_the_declared_floor` walks the client's AST and
asserts its third-party roots are exactly `{grpc, just_dna_enricher}` — an AST walk rather than a
`sys.modules` check, because another test's heavier import would already be resident by then and
the assertion would pass for the wrong reason. That test is what makes the size claim a property of
the code instead of a sentence in a comment.

**The stale argument, deleted rather than left standing.** `enricher/pyproject.toml` carried a
comment block asserting the light client "is not declarable here" and calling vendoring "a decision
with a maintenance cost attached". Commit `1f9a84a` had already refuted it by doing the vendoring,
and a comment arguing against what the file now declares is worse than no comment. Rewritten in the
same commit as the extra it describes.

**What it did not do, filed rather than improvised.** No `tenacity` layer over the vendored
`grpc_service_config.json` (`@retry-attempt-floor`), no shared pacing gate, and no interval RPC —
`ListDenseVariantScores` needs an `x-goog-fieldmask` header and 32 bp chunking, which RM194 owes.
And the bindings are a build product no wheel can build, which is **RM196**.

## RM184 — `CACHE_LANES` published every attribute of a lane except the variable that steers it

**Severity** low · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only: one
required field on `CacheLane`, fifteen constants in `locations`, no behaviour change in any resolver)
· **Owner** enricher · **Motivating case** S89 (just-module-creator, in
CONSUMER_SUGGESTIONS_HISTORY.md), filed as *not deadline-bound* and taken before the cut because it
was cheaper to land than to schedule

**What it reproduced.** The consumer's 1:1 count: fourteen lanes in `CACHE_LANES`, fourteen
`JUST_DNA_<LANE>_CACHE` literals in `locations.py` (one per resolver, passed to `_resolve_parquet_cache`
or `_resolve_named_cache`), plus `JUST_DNA_PIPELINES_CACHE_DIR`, the shared base every default
directory hangs off. `CacheLane` carried fourteen attributes and not that one, so the registry RM176
built *so that a consumer stops keeping its own copy of what the lanes are* still left one attribute to
copy — and the consumer's suite, a `.env.template` generator and a provisioning audit were each keeping
the fourteen names by hand.

**What shipped.** `CacheLane.env_var: str`, populated from new `locations.<LANE>_CACHE_VAR` constants
that the resolvers now read in place of their literals — so the field and the behaviour are one
string, and the field cannot name a variable the resolver ignores. `CACHE_BASE_VAR` is declared beside
them and is deliberately **not** a lane attribute: it moves every lane's default at once and no lane
owns it. Two tests: each lane's variable, pointed at a probe directory shaped to satisfy every
presence test while the base is moved somewhere empty, resolves there and nowhere else; and an equality
over the walked module — every `JUST_DNA_*` string `locations` declares is exactly one lane's
`env_var` or the base — with each lane's identity-checked against its `<LANE>_CACHE_VAR`.

**`str`, not `str | None`, against the consumer's candidate.** They proposed `None` for *a lane
steered only by the shared base*. No such lane exists, and inventing the state would put an
*undetermined* value into a column where every row is determinate — RM87's argument for
`locus_count = 1`. A lane that ever lacks a variable has to be argued for in the walked test rather than
slip past an optional. The peer session that had just added `release_label` suggested the
equality-over-the-exception pattern for the `None` set; with no exception the equality is over the
whole set instead, which is stricter.

**Not changed.** `cache status` does not print the variable. The consumer's audit case — *which caches
were provisioned by variable rather than by path* — is answered by reading `env_var` off the registry
and the environment; a resolver cannot say which rung of its ladder answered, and adding that would be
a change to every resolver for a question the registry already lets a caller ask.

## RM183 — `needs_recompile` crashed on the one input a registry is most likely to hand it, an unstamped compiler version

**Severity** medium · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-format` only:
one early return in `needs_recompile`, one re-raise in `release_version`, two `str | None` widenings on
`RecompileAnswer`; no schema, parquet or manifest change) · **Owner** format · **Motivating case** S88
(just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md), found while reading INTEGRATION_0_7 § 2.8 to
decide whether to adopt the call

**What it reproduced.** The consumer's table, row for row. `Compilation.compiler_version` is
`str | None` with a `None` default, so a manifest carrying nothing there is well-formed and comes back
through `read_manifest` as `None`; `needs_recompile(None, "0.7.0")` then died in
`release_version`'s `.strip()` with `AttributeError`, an error no caller can catch by type or act on
by reading. `""` raised `ValueError` instead — the same fact, nobody stamped, answering two different
ways. And a stamp with a trailing note, `just-dna-compiler 0.6.6 (marketplace-server)`, was refused as
`'(marketplace-server)'`, the last token, which names nothing the caller wrote.

**Why this input is the one that matters.** INTEGRATION_0_7 § 3 tells the marketplace to adopt this
call for `revalidate`/`needs_upgrade`, and the obvious implementation is a loop over stored manifests
it did not produce. One unstamped manifest took that loop down. The three-valued axis is the whole
point of the surface — `None` is *unknown*, `complete=False` over a span with no record — and an
unstamped version is the purest unknown provenance it can be asked about. It already answered
all-`None` for a release it had no record of; `None` deserved the same answer for a stronger reason.

**The line, and the consumer's doubt.** They worried the unknown answer was *too* quiet — a `None`
passed by accident gets a valid answer instead of a crash. Weighed, and the line is drawn one row down
rather than at the whole table: `None`, `""` and whitespace are **absent** and answer unknown
(`compiled_under=None`, `span=(None, current)`, every axis `None`, `complete=False`); a stamp that is
**present and unreadable** — `"0.7"`, `"v0.7.0"`, `"0.6.6+local"`, the trailing note — is asked-and-
cannot-be-read, a caller's bug, and still raises `ValueError`, now quoting the whole stamp. That is
`@unreachable-not-absent` read onto an input: nobody-stamped is a third state beside stamped-and-
readable and stamped-and-malformed, and only the last is a refusal. The package prefix stays
unchecked on purpose — one version across the workspace is the rule since 2026-08-11, so
`just-dna-format 0.6.6` names the same release and refusing it would invent a distinction the
workspace does not make.

**Two type widenings, additively.** `RecompileAnswer.compiled_under` and `span[0]` are `str | None`;
`None` appears only where the call used to raise, so no reader that worked before sees a new value.
Pinned by three tests: the three blank spellings answer identically (`is None` per axis, never
truthiness), the four malformed spellings raise with the whole stamp in the message, and absent and
uncovered — both unknown — are asserted **not** to collapse into one object, because a consumer
grouping unknowns by cause reads `compiled_under`.

## RM180 — an overlay row's provenance was inside `content_signature`, and rewording a reason minted a new content identity

**Severity** medium · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-format` — one
field marker and its reader in `base`, one `exclude=` in `integrity.content_signature`, three marked
fields on `OverrideRow`; `just-dna-compiler` — a roster comment and two tests; no parquet column, no
vocabulary member, no CLI change) · **Owner** format · **Motivating case** S87 (just-module-creator, in
CONSUMER_SUGGESTIONS_HISTORY.md), a before-the-cut report against the 0.7 branch at `f4a9b14`

**What it reproduced.** On `reference_examples/hboc_palb2`, with no compile and no network, one
`frequencies.csv` correction produced four `content_signature`s: none, the correction, the correction
with its `reason` reworded, and the correction with `decided_by`/`decided_at` changed. The first three
movements are right — the overlay is authored input and the value it writes changes what the module
asserts. The fourth is byte-identical data under a different sentence, and the consumer's reading of
`spec_tables`' comment was accurate: it justified including the overlay without distinguishing the
value cells from the provenance cells, because nobody had.

**The decision, and who took it.** The maintainer, 2026-09-03: exclude the three. The six cells
`table`/`subject`/`member`/`field`/`operation`/`value` say *what* the correction is; `reason`/
`decided_by`/`decided_at` say why, who and when. The precedents are S25 — a README caveat is outside
both identity halves, so fixing a typo in it is a patch — and the fact-signature family, which keeps
`fetched_at`/`status` out of every derived table's hash. The counter-precedent is stated rather than
repaired: `curator`/`method` on `variants.csv` are inside the signature, folded from `defaults:` as
content (RM37), and moving them re-keys every published module. Nothing in the compiler or enricher
reads the three cells; they exist for a human reader, and they are exactly the cells an author
improves on a second pass.

**Why the window was the release.** The three fields are `since("0.7.0")`, 0.7.0 is uncut, and no
published module carries an overlay, so excluding them moved no signature. After the cut the same
change moves every overlay-carrying module's signature — the one move `stamped_identity_field`'s
docstring says a content-dedup key may not make. Filing it to a roadmap would therefore have been a
decision to keep them in, taken by default; it was put to the maintainer as that.

**The candidate mechanism was refused, and the suite is what refused it.** The consumer proposed
`exclude=True`, the `stamped_identity_field` idiom. Probed in a detached worktree first: the
signatures collapsed exactly as expected, 1,054 schema and overlay tests passed, and `reason`
survived `reverse` — whose column list is `authored_field_names`, which filters on `COMPILER_MANAGED`
and nothing else. The **full** suite then failed one enricher test, `test_answered_call_shift`,
because its overlay writer serializes rows through `model_dump()` and an excluded `reason` came out
blank, which `OverrideRow` refuses by design. `draft._authored_dump` makes the same `model_dump()`
call, read from the code rather than run: every drafted overlay row would have failed its own compile on a blank the tool wrote. A
stamped column can be excluded because nothing authors it and no writer reads it back; an authored
column cannot, because `model_dump()` is the writers' contract. So the fact lives on the field as
`OUTSIDE_CONTENT_IDENTITY`, `content_identity_exclusions(model)` walks it, and
`integrity.content_signature` passes it as `exclude=` — the one reader. A test asserts the marked set
over `_ALL_MODELS` equals exactly the overlay's three, so a fourth cannot leave the signature silently
and a marker on any other model is a visible decision.

**What still sees the prose.** `overrides.parquet` (`_build_table` reads fields off the model),
`manifest.inputs` (raw bytes of `overrides.csv`), the verification binding (a reworded reason still
un-closes a module), `reverse` (re-emits all nine columns; the fixed-point test now asserts the reason
cells on the reversed bytes, since the signature can no longer vouch for them) and `artifact.digest`,
which moves. That is the README shape.

**What it did not repair.** A reader that dedups on `content_signature` and then opens
`overrides.parquet` can find two modules with one signature whose overlay prose differs — the
consumer's own argument against their fix, and the shape README already has; stated in SCHEMAS. And
the maintainer's observation on the resulting picture — byte digest moved, every signature intact,
*what* moved unstated — is [RM181](ROADMAP_0_8.md#rm181--a-byte-digest-that-moves-beside-intact-signatures-says-something-changed-and-not-what-and-provenance-has-no-shift-tracker).

## RM187 — eleven bulk downloads carried one body in eleven copies, four of them leaking the transport

**Severity** high · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only —
one shared helper, eleven call sites, two adapter handlers; no schema, no parquet column, no CLI
flag) · **Owner** enricher · **Motivating case** a real failure during RM179's republish: NCBI closed
the connection **180,927,542 bytes into a 193,427,450-byte** ClinVar VCF on 2026-09-03 and the run
died with a raw `httpx.RemoteProtocolError` traceback

**The leak is the item; the missing retry is what made it likely.** `_rebuild_clinvar` catches
`ClinVarBuildError`, and `download_clinvar_vcf` raised `httpx`'s own type — so the lane could not
report `built=False`, and the exception escaped `rebuild_lane` as well. In a full `cache rebuild` that
aborts **every lane after the flaky one**, which is precisely the rule that loop was written to hold
("one snapshot failing must not sink the rest"), defeated one level below where it is stated. Four of
the eleven builder downloads were in that state — `clinvar_build`'s two, `constraint_build`'s and
`clinpgx_build`'s — and the other seven translated correctly.

**All eleven had no retry, which is the part worth pausing on.** Every *live client* in this tier has
had `attempt_floor` since RM42, and the requests without it were the largest ones the tier makes: a
~190 MB VCF and a ~95 MB TSV over public mirrors, exactly the fetches most likely to be cut short. The
asymmetry had a cause rather than being an oversight — `net.py` was documented as pacing for live API
clients and `download.py` as HuggingFace provisioning, so each builder reached for neither and wrote
its own fifteen lines. Eleven copies of a body nobody owned.

**One helper, and the eleven public signatures unchanged.** `net.stream_to_file` returns a
`StreamedFile` (path, sha256, etag, last_modified) and each downloader builds its own return type from
it, so no caller moved — the five different return shapes (`Path`, `tuple[Path, str]`, and three
per-lane dataclasses) are all still there. Four properties, each of which had been a defect somewhere:
atomic through `.part`, retried on transport failure, translated at the boundary, and **restarted from
zero on each attempt** — the hasher and the file handle are created *inside* the attempt, because a
retry that appended would produce a file whose digest is real and whose contents are nonsense, which
neither a footer check nor `raise_for_status` would catch.

**Retried only where retrying is honest.** `httpx.TransportError` is the predicate:
`RemoteProtocolError` subclasses it, so the motivating incident is covered, and a second attempt
genuinely fixes a cut connection. A **status** error is deliberately not retried — a 404 from a
mistyped release tag is the same 404 four times over, and three backoffs only delay telling the caller
what the first response already said. That matches the tier's dominant predicate rather than gnomAD's
wider one, which retries `HTTPStatusError` because its own rate limiting arrives that way.

**`constraint_build` had no error type at all**, which is *why* its download leaked: there was nothing
to translate into, and `_rebuild_constraint` therefore caught `(FileNotFoundError, ImportError,
OSError)`. A lane without its own type cannot be caught as that lane. It gains one, and
`ClinVarUnavailable` / `ClinPgxUnavailable` / `ConstraintUnavailable` are **subclasses** of their
lane's error so a caller catching the build error still catches them, while one that wants to tell *the
source was unreachable* from *the bytes were unreadable* can ask by name — the distinction that decides
whether retrying is even the right response.

**Third appearance of `@client-exception-contract`, and the guard is shaped by the second one's
failure.** RM97 found the leak in the clients, RM101 one layer up in the passes, and the builder
downloads were never swept. RM101's own coverage guard **hand-kept eight module names and missed
`identifiers`**, leaving `OntologyClient` leaking raw `httpx` for a release — so this guard walks the
package by AST, and twice: no `download_*` may open a stream, and `httpx.stream` appears nowhere
outside `net.py`. The second walk exists because the first is keyed on a naming convention, and a new
bulk fetch called `fetch_dump` would satisfy it by not matching.

**Two defects found by the sweep rather than reported.** `pubmind_build` was the one handler of eleven
that did **not** unlink its `.part` on failure, so a failed fetch there left a partial behind
(`@a-failed-fetch-is-not-a-no-op`). And four of the eleven computed a sha256 while streaming and only
logged it, so a caller recording the provenance of bytes it had just fetched had to hash the file again
— two lanes had already grown a `tuple[Path, str]` return for exactly that reason, one at a time
(`@dont-discard-computed`). The shared body returns it to all eleven.

**The old behaviour is demonstrated on the old arrangement**, not asserted about the new one: a test
restores `download_clinvar_vcf` to raising the transport type and watches the exception come back out
of `rebuild_lane`. Without that, the claim that this repair fixes something is a claim about code
nobody ran.

**What it does not do.** No downloader gains a resume — a retry re-fetches from byte zero, so a
connection that dies at 180 MB costs the whole 190 MB again. Range requests would fix that and are not
free: the mirrors' `Accept-Ranges` support is unmeasured, and a resumed body needs the digest computed
across two responses, which is a different design from this one. Worth an item if the incident
recurs; not worth guessing at now.

## RM185 — a publish could replace a `release.json` describing bytes it was not carrying

**Severity** high · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only —
one guard in the publisher, wired into three publish paths; no schema change) · **Owner** enricher ·
**Motivating case** RM179's own entry, which fixed the ClinVar lane and left the general shape to the
maintainer; decided with them the same day

**The general form of RM179.** A snapshot's `release.json` describes every half the artifact carries,
because a builder merges its block in rather than writing a file of its own. A publish that carries
one half replaces the whole description — and the publisher adds without deleting, so the other half
survives as bytes nothing describes. ClinVar is the lane it happened to, and RM179 stopped that lane
from producing the input; nothing stopped a publish from *accepting* it, and any lane that grows a
sidecar could repeat it.

**It reads the remote tree, not the remote `release.json`, and that is the load-bearing choice.** The
intuitive guard — compare the incoming description against the published one — would have passed the
second bad publish exactly as it passed the first, because by then the block was already gone from the
published file while `citations/citations.parquet` was still there. The bytes are what a puller gets,
so the bytes are what the guard asks about. Scoped to publishes that carry `release.json`, since one
that carries none overwrites no provenance; a repo that does not exist yet lists nothing and passes,
because that is a first publish and not an orphan.

**`OrphanedSidecarError`, its own type**, for the reason `PublishCollisionError` is one: the CLI has to
tell it from the refusals `plan_*` raises. Those say the local snapshot is unpublishable; this one says
the local snapshot is fine and the remote holds bytes this publish would stop describing. The message
names the file and the command that builds the missing half. **The dry run runs it too** — a rehearsal
that skips what the real thing refuses on is the same defect as an allowlist that drops a file the dry
run promised (`@publisher-allowlist-derived`), so `--dry-run` reads the repo and exits non-zero with
`WOULD BE REFUSED`.

**The state it was written against was repaired while it was being written**, which is worth recording
rather than smoothing over: `just-dna-seq/clinvar` was republished on 2026-09-03 with the citations
block restored (`clinvar_file_date` 2026-08-29, 3,925,275 links, 30 files), so the mixed-vintage
artifact this guard refuses no longer exists on that repo. The guard was verified against the live
tree as it stands — carrying the sidecar and a matching description, it passes — and against the found
state as a fixture. That the repair and the guard landed the same day is not a reason to trust the
repair alone: RM179 stopped the lane producing the input, this stops any lane's publish accepting it.

· *from* RM179's deferred half · *related* RM179, RM186 · *also in* CHANGELOG, AGENT_NOTES
`@a-publish-may-not-orphan-the-bytes-it-stops-describing`

## RM186 — deletion on a published repo, by declaration or by asking, never as a side effect

**Severity** medium · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only —
`LayoutShift` + `cache prune`; no schema change) · **Owner** enricher · **Motivating case** the
159 MB single-file `data/clinvar.parquet` from the pre-2026 layout, still at HEAD in
`just-dna-seq/clinvar` beside the 25 `clinvar-chr*.parquet` that replaced it

**The policy is the maintainer's, and it corrects a premise of this repository's own.**
`@snapshot-accumulates` had been read as *never delete*, and the audit that produced this round
inherited that reading and reported the remnant as a human's job. The maintainer's correction: a
HuggingFace dataset repo is git-backed, so a delete is a commit and a superseded revision still
resolves — three of them were read off the hub while auditing this. Deletion is therefore recoverable,
and the reason to be careful is not lost bytes. It is that a retired file **goes on answering 200** to
whoever still asks for it, which is how a lane's default archive stayed frozen for a year
(`CLINPGX_ARCHIVES`), and that a sweep deletes what nobody looked at.

**So there are exactly two ways a published file goes away, and neither is a side effect of a
publish.**

1. **A declared retirement — `LayoutShift`.** A change that retires one published file and introduces
   another carries the migration with it: *if the new spelling is absent from the repo and the old one
   is present, upload the new and delete the old.* The predicate is over the **remote**, so it fires
   once per repo and is a no-op forever after; it rides in the upload's own commit as
   `delete_patterns`, so the arrival and the removal are one commit rather than a window in which the
   repo has both or neither, and the retired name appears in the commit message. What makes it safe is
   not that it is small but that it is *named*, in the commit that changed the layout, where a reviewer
   sees both halves at once.
2. **`cache prune`, which asks.** It names two kinds of file and nothing else: one under `data/` that
   the lane's own glob excludes — not part of the snapshot by the same definition provisioning uses,
   which already refuses to download it — and one a `LayoutShift` declares retired. `README.md`,
   `.gitattributes`, `release.json`, `LICENSE.txt` and sidecar directories are never candidates.
   Without `--yes` it reads, prints each file with its size and the reason it is nameable, and stops.

**The declared entry is already past its own condition, and it stays literal.**
`just-dna-seq/clinvar` carries the old file *and* the new, because the publish that introduced the
per-chromosome layout predated this rule — so the shift will not fire there, and the remnant is
`cache prune`'s. Loosening the predicate to *retire the old whenever the new is present* would sweep
it, and would also make every publish a prune until the file was gone, which is what
deletion-by-declaration exists not to be. The entry stays for the repo cloned or re-created later,
which is the state it is actually for.

**Second reader of the per-lane globs, so they became a registry.** `cache prune` asks *what does this
repo carry that this lane is not made of*, which can only be asked by lane; `SNAPSHOT_FILE_GLOBS` is
now the one place each lane's file pattern is spelled and the `ensure_*` closures read it, so the
provisioner and the pruner cannot come to disagree about what a snapshot is. Walked by test against
the publishable lanes, with STRchive the one enumerated exclusion — its snapshot is a single JSON at
the repo root, so there is no `data/` for a file to be outside of, and `cache prune` says *n/a* rather
than *clean*, because "found nothing" and "cannot look" are different answers.

**Measured, read-only, against the live repos**: one candidate in `clinvar` (159.5 MB, declared),
`constraint`/`clinpgx`/`cpic`/`drug_labels`/`civic`/`mitomap` clean, `strchive` n/a, and every
unpublishable lane skipped with the registry's own reason. Re-measured after that repo was republished
mid-session and unchanged, which is the predicate behaving as designed: the republish restored the
citations half and did not touch the legacy file, so the shift still does not fire and prune still
names it. **Nothing was deleted** — publishing and deleting on HuggingFace remain the maintainer's to
run.

· *from* the 2026-09-03 published-artifact audit · *related* RM185, RM178 · *also in* CHANGELOG,
AGENT_NOTES `@a-publish-may-not-orphan-the-bytes-it-stops-describing`

## RM179 — the ClinVar rebuild built one half of a two-half artifact, and published its provenance over the other

**Severity** high · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only —
one rebuild adapter; no schema, no parquet column, no CLI flag) · **Owner** enricher ·
**Motivating case** the published `just-dna-seq/clinvar` on 2026-09-03: records from ClinVar
2026-08-29 beside a `citations/citations.parquet` built from 2026-06-27, and a `release.json`
describing only the first

**A published snapshot is two halves on two cadences, and only one of them was being rebuilt.** ClinVar
publishes `var_citations.txt` separately from the VCF, so a snapshot legitimately carries records from
one release and citations from another — which is why `build_citations` merges a `citations` block into
`release.json` rather than writing its own file. `_rebuild_clinvar` called `build_snapshot` and stopped,
and `release.json` is written by that half. So `cache rebuild clinvar --publish` uploaded a fresh,
citations-free provenance over a repo whose sidecar it had not replaced, and the publisher adds without
deleting: the sidecar survived the description that had named it. The block was there until the
2026-09-02 publish (revision `8f5c5720` has it) and gone afterwards.

**The defect is structural, and that is what makes it worth an entry.** Nobody deleted the block and no
operator did anything wrong; the adapter's shape guaranteed the outcome on every rebuild. The same
shape is one `@registry-completeness` step away from the class this repo keeps meeting — a fact about a
lane that lives in a comment (*"the citations table is published with the snapshot"*) rather than in
code that has to hold.

**Both halves or neither.** The adapter now downloads `var_citations.txt` and runs `build_citations`
into the same directory, so the merged `release.json` describes the pair the publisher will carry. A
failure in the second half returns `built=False` **with no `out_dir`** rather than a quieter success:
`cache rebuild --publish` uploads only on `built is True`, so the artifact this item exists to stop
anyone publishing cannot reach the plan. The detail line says the records did build, which is the
difference between *retry the pair* and *it broke*.

**What it costs, stated rather than hidden.** `--source clinvar=<vcf>` remains the VCF's off-switch,
and the citations file is a separate ClinVar download that is still fetched — so a fully offline
rebuild of this lane now reports failed where it used to report a snapshot. That snapshot was the
mixed-vintage one, so the trade is deliberate; a lane-local second `--source` was refused as a flag
grammar for one lane's second input, which is the shape MANE and CIViC already refuse.

**Not repaired here: the publish-side guard.** A publish that overwrites a remote `release.json`
describing sidecars the plan does not carry should refuse, and that is the general form of this bug —
it would have caught this one at the boundary rather than at the lane. It is a policy about what a
publisher may overwrite, so it is the maintainer's call and not this item's. **Nor does this repair the
repo as it stands**: `just-dna-seq/clinvar` still needs a citations rebuild off 2026-08-29, which is an
outbound operation.

· *from* the 2026-09-03 published-artifact audit · *related* RM176, RM178 · *also in* CHANGELOG,
AGENT_NOTES `@a-lane-with-two-halves-publishes-the-provenance-of-one`

## RM182 — `cache status` named the release of every snapshot except the one that moves weekly

**Severity** low · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only — one
field on `CacheLane` and the reporter that reads it; no schema change) · **Owner** enricher ·
**Motivating case** the same audit: `cache status` over a freshly pulled cache printed
`clinpgx_2026-08-05`, `civic_01-Sep-2026`, `strchive_v2.26.0` … and a blank for `clinvar`

**One reader, twelve writers, and the odd one out was the one that matters most.** `cache status`
labelled a lane with `release.json`'s `dataset`. Eleven builders write it; `clinvar_build` writes
`clinvar_file_date` and `record_count` instead, and has since long before the field existed. So the
lane that refreshes weekly was the only one an operator could not read a release off — precisely the
lane where *which release is this?* is asked.

**The label is a lane's own property, not the reporter's.** `release_label` joins `build_command` as a
field that exists because a convention holding for eleven of twelve is not a convention: the reporter
composing one for every lane is what produced the blank, exactly as composing `f"{name} build"` once
printed two commands nobody could run. ClinVar's is `clinvar_dataset_label` — the function
`clinvar_draft` already writes onto its licence row and `clinical.tautology_reason` recomputes to
compare — shared rather than mirrored, because two spellings of one label never match and never fail
either. The exception is asserted as an equality over the registry, so a second lane that stops writing
`dataset` has to say so here instead of quietly printing nothing.

**Refused: adding `dataset` to `clinvar_build`'s `release.json`.** It repairs nothing already on disk
or already published — every existing snapshot would still print blank until rebuilt — and it makes a
second writer of a label `clinvar_dataset_label` already owns. It stays available as an additive
follow-up; it is not the fix.

· *from* the 2026-09-03 published-artifact audit · *related* RM176, RM179 · *also in* CHANGELOG,
AGENT_NOTES `@the-reporter-cannot-compose-a-lanes-label`

## RM178 — a failed optional fetch left a 0-byte licence in every pulled cache, and an empty licence pins the empty string

**Severity** medium · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only —
one download loop, one normalization in `SourceTerms.row`, one archive reader; no schema, no parquet
column, no vocabulary member) · **Owner** enricher · **Motivating case** an audit of the published
HuggingFace artifacts on 2026-09-03, which pulled every publishable lane into a scratch cache and found
`LICENSE.txt` at 0 bytes in four of them

**The transport does not behave the way the `try` assumed.** `_provision_snapshot` ends by fetching the
two optional root files, `release.json` and `LICENSE.txt`, inside a `try/except` that logs "the cache
carries data only" — written on the assumption that a failed fetch changes nothing. It does not:
`HfFileSystem.get` opens the destination for writing *before* it resolves the remote path, so a repo
publishing neither file leaves a 0-byte one behind. Four of the nine published snapshots publish no
`LICENSE.txt` (clinvar, gnomad_constraint, cpic, mitomap), so every `cache pull` on a hosted deployment
created four phantom licence files. The same call **truncated an existing local copy from 36 bytes to
0** — verified against the live hub, both halves, before anything was changed.

**An empty licence is not a smaller absence, it is a different answer.** The readers guard on
`is_file()`, which cannot separate the two, and the answers diverge: an absent `LICENSE.txt` leaves
`license_sha256` null and warns, while an empty one records `sha256:e3b0c442…b855`, the hash of the
empty string, as a pin — a definite claim about terms nobody read, in a field whose only purpose is to
tie recorded terms to the text that governed the bytes (S44's whole point). Nothing had noticed because
the one lane that reads the file, ClinPGx, publishes a real one.

**Repaired at both ends, and the read end at the sink.** The write end stages through `.part` and
renames on success — the idiom the parquet and sidecar loops of that same function already used — so a
failure leaves nothing and cannot overwrite what is there. The read end normalizes in
`SourceTerms.row`: blank or whitespace-only `license_text` is `None`. At the sink because there are
four callers (`clinpgx_build.read_license`, `drug_labels_build`, `clinpgx_draft`, and a registry's
status field), and a rule restated per caller is a rule three callers drift from; `read_license`
answers `None` for a present-but-blank archive member for the same reason one level up. `clinpgx_draft`
keeps a blank check of its own only because it owes a *warning*, which the sink cannot emit.

**Refused: deleting the phantom files from operator caches.** `_provision_snapshot` already reports a
foreign parquet rather than removing it — someone else's cache directory is not ours to clean — and the
same rule holds here. A 0-byte `LICENSE.txt` in an existing cache is now inert (nothing pins it, and the
next pull replaces or leaves it), and an operator who wants it gone can delete it.

· *from* the 2026-09-03 published-artifact audit · *related* RM176, S44 · *also in* CHANGELOG,
AGENT_NOTES `@a-failed-fetch-is-not-a-no-op`

## RM177 — nine builders wrote their snapshot beside `pyproject.toml`, because the rule that forbade it was prose

**Severity** medium · **Status** ✅ shipped 2026-09-03 in the uncut 0.7.0 (`just-dna-enricher` only —
fourteen `--out` defaults and one `locations` helper; no schema, no parquet column, no vocabulary
member) · **Owner** enricher · **Motivating case** the enricher reference and the authoring skill both
telling an operator to run `clinpgx build --out ./clinpgx` from a checkout

**The rule was old and it had been enforced exactly once.** *Nothing a command generates goes in the
repository root* was filed when `civic reproduce` wrote `civic-reproduce/` there and needed its own
`.gitignore` line to say so; the repair moved that one default under `data/repro/` and wrote the rule
into CLAUDE.md. Every builder written after it repeated the defect, because a rule stated in prose is
checked by whoever remembers to read it. `civic`, `clinvar`, `pubmind`, `gnomad_constraint`, `mane`,
`strchive`, `acmg_sf`, `mitomap` and `mitomap_miss` each defaulted `--out` to a bare relative name, so
running any of them from a checkout dropped a snapshot directory beside `pyproject.toml`. Four more —
`clinpgx build`, `clinpgx build-labels`, `cpic build`, `pharmvar build` — required `--out` with no
default at all, which is how the reference came to show `--out ./clinpgx`. Nothing was ever committed
by accident, because blind staging is banned here for an unrelated reason; the defect was visible on
every `git status` and survived nine builders anyway.

**What shipped is one function, not fourteen corrections.** `locations.repro_out(name)` returns
`data/repro/<name>/`, and every builder's `--out` default is a call to it. `cache rebuild` keeps
`data/caches/` as `locations.CACHES_DIRNAME`, in the same file, because a cache base is a different
concept from one snapshot and the point is that neither is spelled inline. `civic reproduce` moved from
`data/repro/civic` to `data/repro/civic_reproduce`, since `civic build` now takes the plain name; the
probe records that name the old path ([CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md)) are
dated and keep it. A caller passing `--out` sees no change.

**The guard walks rather than lists** (`@registry-completeness`). `test_build_out_defaults.py` parses
`cli.py`, finds every `typer.Option` bound to `--out`, and asserts each default is `repro_out(...)` or
a `locations` constant — never a literal. Sixteen found, and sixteen `"--out"` strings in the file, so
nothing escaped the walk. The one required `--out` that remains, `clinvar citations`, names an
**input** (an existing snapshot to add a sidecar to) and is enumerated as an equality, so the exemption
cannot grow quietly. A floor — *at least nine under `data/`* — would have passed forever while the
tenth builder wrote wherever it liked.

**Refused: a `.gitignore` line per lane.** It is the repair `civic reproduce` originally got, and it is
the shape that produced nine repeats: each new builder would need its own line, which is the same
prose rule at a different address. `/data/` is ignored whole, so a default under it needs no line.

---

## RM160 — the citations ten CIViC records carry are published on one surface, and it is the one nothing read

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-03 in the uncut 0.7.0** — the provenance half,
as shape 3 (`just-dna-enricher` client + command + check, two optional `studies.csv` columns, one new
`VALID_VERIFICATION_CHECKS` member). Its *coverage* half shipped earlier as
[RM169](ROADMAP_HISTORY.md#rm169--the-wider-basis-was-published-as-a-dated-file-all-along-and-nobody-had-looked),
and the VCF that answered the first could not answer this one ·
**Owner** enricher · **Motivating case** the 2026-09-01 residue round, variant 1955
([CIVIC_LEGACY_INSERTIONS](probes/CIVIC_LEGACY_INSERTIONS.md) §7.4)

> **Read this first: the item's original premise was wrong.** It said the API has no dated release to
> pin, and therefore that any wider basis costs the snapshot its reproducibility. CIViC publishes
> `<date>-civic_accepted_and_submitted.vcf` **in the same dated directory** as the TSVs, so the wider
> corpus was pinnable all along and RM169 took it: 507 rows on 270 variants → **1,149 on 397**, with a
> byte-identical rebuild. The three shapes below were framed against the *coverage* half, which RM169
> then dissolved without using any of them; they are re-scoped rather than retired, because for the
> half that is left the tension is real.
>
> **What that leaves here is narrower and still real.** The VCF cannot carry a variant with no GRCh37
> position, so it holds **none of the 10 records** whose hidden citations motivated this item, and 1
> of the 53 unresolvable variants. The provenance half is API-only or nothing.

`civic build` reads the dated bulk TSV release, and **every row in it is `evidence_status = accepted`**.
CIViC's own GraphQL API defaults to `NON_REJECTED` and serves 11,518 evidence items against the bulk
file's 4,903 — a 2.35× difference between two published faces of one database, declared by neither.
`SUBMITTED` (a curator entered it, no editor signed off) is **the majority of CIViC**: 6,614 of 11,518.

The snapshot records `status_basis: "accepted"` in `release.json`, so the basis is not hidden. What is
missing is any sense that the choice **costs** something, and there is now a worked instance where it
costs more than rows.

### The instance, because a doubled row count was never the argument

Variant 1955 (`VHL P71fs (c.211insT)`) is one of two records in the whole corpus that nothing
resolves: a legacy insertion notation with two readings, both registered as real and different
alleles, and no discriminator anywhere. Its accepted evidence item cites Olschwang 1998, paywalled and
not in PMC. Ong 2007, behind the sibling record 2131, likewise.

Queried directly, `evidenceItems(variantId: 1955, status: ALL)` returns **two** items. The second,
EID 9969, cites PMID 12202531 — Dollfus 2002, **free full text**, whose Table 3 states the numbering
convention the whole ambiguity turns on. It is `SUBMITTED`, so it exists in the API and in **no file
the builder reads**.

So the basis does not merely shrink the corpus. Here it hides the only reachable evidence that could
settle an identity the snapshot is currently unable to state — and it hid it from a probe that had
already gone looking, because the probe read the file the builder reads.

### Re-measured 2026-09-01, and it is worse than "a bigger corpus"

Two numbers sharpen the item, and the second changes what it is *about*.

**On the direction axis the gap is 2.77×, not 2.35×.** Queried per status rather than taken from the
whole-database ratio:

| basis | all evidence items | `PREDISPOSITION`/`SUPPORTS` |
|---|---:|---:|
| `ACCEPTED` | 4,906 | 534 |
| `SUBMITTED` | 6,617 | 946 |
| `NON_REJECTED` | 11,523 | **1,480** |

So the axis this source was adopted *for* is more skewed toward unreviewed content than the database
as a whole. (`DOES_NOT_SUPPORT` is 2 → 4 and `PROTECTIVENESS` 1 → 2, which is why the
contested-variant count moves 0 → 3 and genuine `risk`-vs-`protective` opposition still does not.)

**Ten of the twenty records nothing can place gain a citation the accepted basis does not carry.**
This is the finding, and it is not about volume. Asked `status: ALL`, per record:

| record | accepted citations | citations only `SUBMITTED` brings |
|---|---:|---:|
| 844 `VHL Exon 1 Deletion` | 3 | **34** |
| 1939 `VHL Exon 3 Deletion` | 4 | **33** |
| 843 `VHL Exon 1-3 Deletion` | 2 | 17 |
| 845 `VHL Exon 1-2 Deletion` | 1 | 18 |
| 2182 `VHL Null (Large deletion)` | 3 | 7 |
| 2439 `VHL Rearrangement` | 2 | 7 |
| 715 `STK11 Mutation` | 3 | 4 |
| 2036 `VHL Null (Partial del Ex2&3)` | 1 | 2 |
| 3298 `VHL P81S and L188V` | 1 | 1 |
| 1955 `VHL P71fs (c.211insT)` | 1 | **1 — the free-fulltext one** |

**A verdict is only as wide as the papers read, and these were read on the accepted basis.** The
class-C three-way split in [CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md) — *never measured* /
*measured then generalised away* / *measured at a resolution that is not allele resolution* — was
decided from each record's cited papers, and for 2036, 2182 and 2439 those were the accepted ones
only. The verdicts about what the **name** denotes are untouched (a class label stays a class label
however many papers cite it), but the claim that *the source never measured breakpoints* is scoped to
papers that a wider basis would have added 2, 7 and 7 more of. That scope belongs on those verdicts
whether or not this item is ever taken.

### What is already measured, so nobody re-derives it

- Reading `SUBMITTED` roughly **doubles** the corpus and moves **every** number in
  [CIVIC_SURVEY](probes/CIVIC_SURVEY.md).
- It takes the **contested-variant count from 0 to 3** (variants 2161, 2428, 2533, all VHL, all
  `risk` against `not_risk`). Under `accepted` the count is 0 because both sides of every contest are
  `SUBMITTED`.
- Genuine `risk`-vs-`protective` opposition stays **0** at every basis, so this does not reopen the
  concordance route (that is closed on arithmetic, not on volume).
- The direction slice is 533 rows on the accepted basis and 925 `SUBMITTED` against 533 `ACCEPTED`
  over the wider germline direction set.

### The design question, re-scoped 2026-09-01 after RM169

**Is the API richer than the files? Yes, on exactly one axis, and it is this one.** The whole dated
download surface is enumerated in [CIVIC_SURVEY](probes/CIVIC_SURVEY.md) § the bulk releases: seven
TSVs and two VCFs. Both TSVs the builder reads are `accepted`-only (`ClinicalEvidenceSummaries`, and
`VariantSummaries` too — a fact nothing had stated before that enumeration), the only two files
carrying `submitted` at all are the VCFs, and a VCF record needs a POS. So submitted evidence attached
to a variant with **no GRCh37 coordinate** is published on one surface only, the API. For everything
that has a coordinate, RM169's dated VCF already carries it, pinnable, no API. Nothing else about the
API is richer than the files, and the three summaries the builder does not read
(`AssertionSummaries` 145 rows, `FeatureSummaries`/`GeneSummaries` 973 and byte-identical to each
other, `VariantGroupSummaries` 30) do not bear on this: none is an evidence table.

**So the reproducibility tension survives, narrowed to this half.** `civic build` is byte-reproducible
because its input is a pinned dated file pair, and `civic reproduce` proves it by building twice. An
API read still has nothing to pin. Of the original three shapes, two stay live and one stopped meaning
what it meant — **this is not an open three-way choice, and it was mistakenly re-put as one on
2026-09-01**:

1. **Snapshot the API response** with a retrieval timestamp and hash it as an input, the way the
   download files are hashed. Reproducible against *that capture*, not against CIViC.
2. ~~**A second parquet beside the accepted one**, built from the API~~ — **dissolved by RM169.** The
   wider parquet exists and is built from files; one more from the API would be a *third* basis rather
   than a second, and the consumer decision this shape was priced against has already been spent.
3. **Leave the build alone and read `SUBMITTED` at `enrich` time**, beside the CAID pass, where
   network reads already live and reproducibility is not claimed. Narrowest, and it does not enlarge
   the published snapshot — which may be the point or may be the missing half.

**DECIDED 2026-09-02 with the maintainer: shape 3.** `civic build` and `civic reproduce` keep their
byte-reproducibility contract untouched and the published snapshot does not grow; the API read lives
where network reads already do and where reproducibility is never claimed. The motivating case is an
enrich-time question anyway — an author resolving one identity, holding one variant, needing the
citations that variant's record carries. Shape 1 was available and not taken: hashing a capture keeps
the *word* reproducible while changing what it is reproducible against, and a snapshot that reproduces
only against itself is a weaker claim than one that reproduces against a dated release.

**Not yet built.** What it needs: a per-variant `evidenceItems(variantId:, status: ALL)` read behind
the same offline/`check_declared_use` discipline as the other enricher fetches (CIViC is CC0, so no
gate), the `status` on each returned item carried as `confidence`/`confidence_unit` unconverted, and
a skip that is `offline`/`unreachable` rather than a silent empty — the pass has to distinguish *the
API said this variant has nothing more* from *nobody asked*. It is one variant at a time by
construction, which is why it fits `enrich` and would not fit a build.

**The labelling requirement is settled and half-shipped.** An `accepted` row and a `submitted` row
must not be indistinguishable once both are in the file, and for the file-built half RM169 did it:
every row carries `evidence_status`, CIViC's own word, unconverted. Whatever shape this half takes
owes the same stamp — and where it lands as a magnitude rather than a column, that is `confidence`
with `confidence_unit`, named rather than translated into a house grade, the way
`ClinSigAuthorityCallRow` already requires a magnitude to name its instrument.

**Related** RM152 (the adoption), RM159 (the name-identity table, whose two unresolved records are the
motivating case), RM153.

### What shipped, 2026-09-03

**`civic_api.py`** — the client. `evidenceItems(variantId:, status: ALL)`, paginated (variant 844
really is 37 items and a first-page reader would have reported four), checked against the payload's
own `totalCount`, paced on a shared `PacingGate`, retried on `attempt_floor(3)`, and translated at the
boundary: `CivicApiUnavailable` for the question that was never put, `CivicApiError` for an answer
this client cannot read — a GraphQL `errors` block is the second, because the service *did* answer.
Statuses are lower-cased to the spelling `civic_vcf` already writes and not otherwise touched, and a
member outside `{accepted, submitted, rejected}` raises rather than defaulting.

**`civic citations <spec>`** — the command. Three routes reach a CIViC variant id, and the third
exists because the first two miss the class this item is about: the snapshot's coordinate join through
`clinical.comparison_plan` (the same resolved-`(chrom, start, ref, alt)` route the refutation leg
uses, never an rsID), the curated name-identity table, and `--variant-id N` for a record neither can
place. **1955 is not in `CIVIC_NAME_IDENTITY_BY_VARIANT`** — being unresolvable is why its citations
were unreachable — so without the third route the motivating case would not have been reached by the
thing built to reach it. Those rows ground the *module* rather than a variant, which `StudyRow` has
permitted since RM47.

**A recovered citation is a `studies.csv` row and nothing writes `literature.csv`.** That table is
derived from these PMIDs by the `literature` pass, and an article row nothing cites is dropped from
the artifact (`@uncited-literature-dropped`) — so drafting the citing row and letting `literature`
fill the article is the pairing that works in both directions. Five evidence items citing one paper
are one row, because `(variant_key, pmid)` is the grain.

**`StudyRow.confidence` / `confidence_unit`**, optional and 0.7.0. The labelling requirement was
settled before the round: an accepted row and a submitted row must not be indistinguishable once both
are in a file, and where the state lands as a magnitude rather than a column it rides here, named
rather than translated. **This is one authored column pair more than PROPOSAL_0_7_PT3 priced the item
at** — that file says RM160 "adds no authored column at all" — and the correction is recorded as a
dated addendum there rather than left as a silent contradiction. It is still minor-legal: a new
optional column is additive under P3/P8, `content_signature` does not move for a module that fills
neither, and the parquet it lands in is the one RM140 had already moved this release.

**`evidence_status_currency`** — the canary, and the half the maintainer asked for by name. Drafting
from a live read is only honest if something re-asks: the pin says *when* and *on what basis*
(`fetched_at` and `dataset` on the `(civic, literature)` `SourceRow`), and `enrich` re-asks and reports
what has moved — a status accepted or rejected since, or a citation added since. Two codes because two
remedies. **Warns in both modes and escalates in neither**
(`@a-source-recuring-is-not-a-strict-matter`), and deliberately **not** `dataset_currency`: that one
asks which release a table came from, this one asks whether a per-item judgement has moved.

**The pin's layer is `literature`, and neither half of that is arbitrary.** `(civic, annotation)` is
`civic_draft`'s row and a second surface of an already-declared source may not claim the lane's slot
(`@write-the-sourcerow`); a `civic_api` *source* would publish a route as a licensed body, which is
the overloading `@source-vs-authority` fixed in `gene_metrics.csv`; and `literature` is one of the two
layers the compiler's orphan check exempts, so a module carrying `studies.csv` rows does not warn
`source_row_unused`. `merge_sources_csv` is never-clobber, so the pin records the ask that *first* put
a recovered citation into the module — a floor on "not asked since", which is precisely the gap the
canary closes.

**Three withholds, and each is counted rather than silent.** Rejected evidence is not drafted at all
(`rejected_by_source`) — `status: ALL` returns what CIViC's editors threw out, and a module must not
carry it as though the source stood behind it; where a rejected item sits *beside* a live one for the
same paper, the live ones decide the row, which is the real case on variant 1939 (PMID 28256701). A
paper whose live items disagree about their status gets its confidence **withheld** rather than
picked. A `citationId` on a non-PubMed source is a real id in another namespace and withholds rather
than becoming a `pmid` (`@pmid-vs-pmcid`).

**What it does not reach, said rather than smoothed over.** A citation recovered through
`--variant-id` names no variant, so nothing can map it back to a CIViC id on a later run: the canary
reports those as `not_re_askable` under a `no_reference` skip rather than counting them as agreement.
That is a real bound on the route built for the motivating record, and the honest form of it is a
published number, not silence.

**Tests.** Three real recorded responses under `assets/civic_api_slice/` (1955 for the motivating
pair, 844 for volume and the five-items-one-paper case, 1939 for the only rejected item in the
corpus), served through a mock transport so the suite never fetches; every expected value derived from
them at runtime. The `--offline` probe's transport fails the run if it is reached, because an
off-switch needs its own probe rather than a reading (`@off-switch-needs-a-probe`).

## RM171 — MITOMAP's curated mtDNA tables, adopted as the increment they carry over ClinVar

**Severity** low-medium · **Status** ✅ **SHIPPED 2026-09-03 in the uncut 0.7.0** — two cache lanes
(one of them the registry's first *derived* lane), a `parents` field on `CacheLane`, a draft source, a
`SourceTerms` row and five abbreviations in the shared clinical-significance normalizer. Nothing
removed, promoted to required or retyped · **Owner** enricher · **Motivating case** RM164's probe,
which found the table while answering a different question ·
**Design** [rm171_diff_strategy](probes/rm171_diff_strategy.md), written by the maintainer, on the
measurements in [MITOMAP_STATUS](probes/MITOMAP_STATUS.md); build order in
[PROPOSAL_0_7_PT3](proposals/PROPOSAL_0_7_PT3.md)

**What the entry was blocked on, and why that binary was the wrong question.** It read *does a source
contributing sixteen new expert-panel calls earn an adoption, or does ClinVar already carry this?* —
and "16" is not a fact about MITOMAP. It is a fact about one join against one ClinVar vintage, and a
hardcoded list of sixteen alleles is a snapshot of a diff, stale the next time either parent is
rebuilt. What shipped answers the other question instead: **what does MITOMAP publish that the ClinVar
cache does not**, derived every time both caches are current.

**The shape: two parents and one derived child.** `mitomap` is an ordinary lane — `curl` the published
`pg_dump`, keep six of its hundred-odd tables, write parquet. `mitomap_miss` is not a download at all:
its acquire stage is *both parents on disk*, its build is an exact `(start, ref, alt)` join on chrMT
against the ClinVar parent, and its `release.json` pins both parents so a ClinVar rebuild without a
child rebuild is detectable rather than silent. `CacheLane` gained `parents` for it — empty for the
twelve that shipped with [RM176](ROADMAP_HISTORY.md#rm176--eleven-builders-three-stages-each-and-the-roster-that-was-supposed-to-name-them-was-a-list),
a two-lane tuple here — plus a guard whose outcome is `built=None` naming the missing parent. Both
wrong answers were available and both are silent: a `False` files another lane's absence as this lane
breaking, and an empty miss is the strongest possible claim about MITOMAP derived from a comparison
that never ran.

**Four buckets, and only one drafts.** *photocopy* — the exact allele is in ClinVar, so the ClinGen
mtDNA VCEP's call already reaches this repository with ClinVar's own provenance; drafting a second copy
would attribute it to the wrong publisher and would hand a ClinVar concordance check a copy of ClinVar
to agree with (`@tautology-zero`). *rated miss* — absent, and the bracket is one of the five documented
VCEP classes. *unrated miss* — absent, and MITOMAP published no class this tier may map. *unmintable*
is a fourth because the question cannot be **asked** of it: MITOMAP writes a deletion right-anchored
(`refna="TA"` against `regna=":"`), and turning that into a VCF allele needs the rCRS base at
`position - 1`, which Principle 2 forbids these tiers from fetching.

**The bracket is a normalization; the confirmation token never is.** `status` is a two-token grammar —
a confirmation token (`Reported`/`Cfrm`/`Conflicting reports`, plus `Unclear` in the sibling table)
followed by an optional bracketed rating. MITOMAP's own legend says in as many words that the first is
**not** an assignment of pathogenicity; it is a literature-count criterion, so mapping `Cfrm` onto
`pathogenic` would write a judgement the source declines to make. The second is somebody else's
instrument entirely — the ClinGen mtDNA VCEP's five classes, which is exactly what `VALID_CLIN_SIG`
already carries — so the five abbreviations became **keys in the one shared normalizer**
(`@one-normalizer-two-spellings`) rather than a MITOMAP-local map that would then have to agree with it.

**`[VUS*]` is withheld, and the withhold could not be left to the normalizer.** It is not the legend's
footnote marker (a diamond, printed *inside* the bracket), not a sixth class, and not APOGEE's
`[VUS+]`/`[VUS-]`, which leak into `rtmutation` on one row each from a seven-tier in-silico predictor
sharing three letters. Nobody wrote down what it means. The subtlety is that `normalize_clin_sig`'s own
default is `other` — a **definite** member of the vocabulary, not an unknown — so an unmapped token
falling through would have become a confident call. `mitomap.vcep_clin_sig` therefore decides
membership *before* anything is normalized, and the withheld brackets are counted in the snapshot's
`release.json` rather than folded into `VUS`.

**Both tables, and that was settled before the build.** `reference_examples/mt_heteroplasmy` carries
two variants and both live in `rtmutation`; neither is in `mmutation`. An `mmutation`-only lane would
have drafted nothing the repository's one mtDNA module needs — and shipping one table and discovering
the sibling later is how RM164 happened.

### What the first build measured, on the ClinVar of its own day

The entry owed a rejoin rather than a quotation, and the rejoin **moves the number the entry was
about**. Against `clinvar_file_date 2026-06-27` (3,104 distinct chrMT alleles) and the dump served on
2026-08-24 (`mmutation` curated through 2026-08-21, `rtmutation` through 2026-08-19):

| | photocopy | rated miss | unrated miss | unmintable |
|---|---:|---:|---:|---:|
| `mmutation` (602) | 352 | **3** | 218 | 29 |
| `rtmutation` (494) | 303 | **3** | 170 | 18 |

**Six rated misses, not sixteen — and the difference is not a disagreement with the probe.** The probe
counted 16 bracketed `mmutation` rows absent from that same snapshot, and all 16 reproduce. **Thirteen
of them are `:` deletions**, which the design's own §6 puts in the unmintable count until an enricher
pass anchors them; the three that remain are insertions the schema *can* spell. The sibling table
contributes three more of the same kind. So the motivating number was never sixteen new *draftable*
calls — it was sixteen rows, thirteen of which the same document says this tier may not mint. That is
the sharpest possible argument for the rule the entry shipped under: **the number is derived, never
stored**.

**Every one of the six keys on an indel**, which the lane publishes rather than hides. The join is
exact and neither side is left-aligned, so a miss on an indel key is either an allele ClinVar does not
carry or one it carries at another anchor, and this lane says which it cannot tell you.

**The `nlmid` walk, which the strategy left owed on a sample of four.** All 6,770 reference rows were
walked: **6,372 carry a bare-digit PMID, 397 state none, and exactly one states
`01930224-202601000-00006`** — an Ovid article id whose first eight characters are digits, which a
substring search would have cited as somebody else's paper (`@pmid-vs-pmcid`, one registry over). So
`nlmid_pmid` requires the *whole cell* to be a digit run, deliberately stricter than
`spec.extract_pmids`. The increment carries 802 citation links for its non-photocopy rows.

**One more finding the build turned up, reported and not repaired.** One drafted row's `allele` **name**
states a variable number of copies (`T961delT+ / -C(n)ins`) while its allele *columns* state one
definite pair (`T`→`CC`) — the source disagreeing with itself about definiteness. The row keeps
MITOMAP's own `ref`/`alt`, because dropping it would discard a published call and rewriting it would
need a rule for what `(n)` means that MITOMAP has not given; the drafter names it, on a row the author
has to curate by hand anyway (`@multiplicity-is-a-finding`).

### `genotype` is stubbed, and the reason is not the contig's

This is the departure worth recording, because the house already has a rule that points the other way.
`clinvar_draft.sole_expressible_genotype` **fills** the ALT on chrMT — a haploid contig leaves no
zygosity open, so the placeholder is protecting a decision that does not exist (S6,
`@placeholder-protects-decision`). That argument is right about ClinVar, whose record is a claim about
an allele. MITOMAP's row is a claim about a **literature corpus**: `homo` and `hetero` are presence
flags saying whether the variant has been *reported* in each state, and on the real increment three of
the six drafted rows are reported only heteroplasmically. Writing `genotype=<ALT>` there states the
homoplasmic reading — which is precisely the claim `reference_examples/mt_heteroplasmy` keeps in
`variants.csv` and separates from its `heteroplasmy.csv` bins. So the cell is stubbed, the flags
MITOMAP *did* publish go in front of the author per row as an uncapped worklist, and **a
MITOMAP-drafted module cannot compile until a human writes those cells.** That is the cost of this
adoption and it is stated rather than engineered around.

### The five places the build departed from the plan

Recorded here and as a dated addendum on [PROPOSAL_0_7_PT3](proposals/PROPOSAL_0_7_PT3.md), because a
silent contradiction of a build plan is worse than a noisy one.

1. **The lane is `mitomap_miss`; `mitomap-miss` is accepted everywhere and folds to it.** The registry
   is walked by identity — `resolve_<name>_reference`, `<NAME>_SUBDIR`, `<name>_build.py` — so a
   hyphen cannot be a lane name. `drug_labels` is the precedent, and `caches.lane_name` returns the
   **declared** member rather than the caller's spelling (`@vocab-separator-slip`).
2. **The command is `draft-panel --source mitomap-miss`**, not a bare `draft --source`: `draft` is the
   CPIC command and `draft-panel` is the one that writes `variants.csv` + `studies.csv` from a
   `--source` vocabulary. `--gene` became optional **for this source alone** and is still refused as
   absent for the other three — the increment is asked for as a whole, where an unfiltered ClinVar
   draft would be the whole snapshot.
3. **`dataset` comes from the dump's own `edit_date`, not from HTTP `Last-Modified`.** The ClinVar
   precedent the design names is `##fileDate` — a statement the file makes about itself — so a build
   from a local dump produces a label a downloaded one can be compared against. Both tables' dates,
   because both are adopted and they are curated separately; the header and the sha256 stay in
   `release.json`, where provenance of the *fetch* belongs. The increment's own label is that plus the
   ClinVar release, since a derived artifact's identity is the pair it came from, and it is withheld
   entirely when either half is unknown.
4. **The child carries its own citations parquet**, for the non-photocopy rows only, so the drafter
   reads one snapshot rather than two — the alternative lets a draft run against a MITOMAP snapshot
   that is *not* the one the join used.
5. **`STATE_BY_CLIN_SIG` moved to `clin_sig.py`.** `pubmind_draft` was already importing it out of
   `clinvar_draft`; a third caller made the private home indefensible, on the normalizer's own
   argument.

### What it deliberately does not do, and what is still open

Never maps a confirmation token; never maps `[VUS*]`; never drafts a photocopy; never left-anchors the
`:` deletions in the format or compiler tiers; and never puts a count in a constant — the tests assert
relationships (a miss key is absent from the parent, a photocopy key is present, a rated-miss
`clin_sig` is the normalizer's image of its bracket, the four buckets partition the source rows, a
child whose parent pin does not match the parent on disk is stale).

Still open, and none of it blocking: **`VUS*` is withheld rather than understood** — a legend, or
McCormick 2020 read in full, would revisit it, and until then a rated-miss count that silently included
those rows would be a lie. **The 388 unrated misses are a real identity increment with no mappable
class**, counted and not drafted; whether their identity earns a row at all is a second, smaller call.
**The `:` deletions want an enricher pass** that anchors them against the rCRS — legal in that tier,
which may fetch. **Indel normalization** would turn the left-alignment caveat into an answer. And
**publishing the MITOMAP snapshot to HuggingFace is outbound and stays the maintainer's**: the lane has
`mitomap publish` and CC BY 3.0 permits it, but nothing has been uploaded. The derived child is
deliberately unpublishable for a fourth reason that is neither a refusal nor an unestablished
permission — a pulled copy would carry a currency check its holder cannot run.

**Related** RM164 (where it was found), RM176 (the registry it extends),
[MITOMAP_STATUS](probes/MITOMAP_STATUS.md), [rm171_diff_strategy](probes/rm171_diff_strategy.md),
`@one-normalizer-two-spellings`, `@lookup-with-a-default-hides-a-new-member`, `@tautology-zero`,
`@currency-asks-the-source-not-the-cache`, `@stub-cannot-compile`, `@probe-names-the-table`.

## RM176 — eleven builders, three stages each, and the roster that was supposed to name them was a list

**Severity** high · **Status** ✅ **SHIPPED 2026-09-02 in the uncut 0.7.0** — the cache registry, three
missing resolvers, three new publish/provision pairs, and `cache rebuild` (`just-dna-enricher`; no
schema, no vocabulary, no parquet column) · **Owner** enricher · **Motivating case** the maintainer's
2026-09-02 question — *do all the caches we build have a common rebuild endpoint, and does each have
download, build and upload?* — asked of every lane except Ensembl

**The answer was no, and the three gaps were one defect wearing three faces.** Every one was a fact
about a lane that no code anywhere asserted, because the roster was a four-tuple list inside `cli.py`.

- **Three lanes were not in it at all.** `acmg_build`, `strchive_build` and `drug_labels_build`
  existed and had no roster entry, so `cache status` reported nine caches on a machine that has
  twelve and `cache pull` refused the other three as unknown names.
- **Those same three had no resolver.** Each check took an explicit path and looked nowhere else, so
  the only way to run one against a built snapshot was to name it on every invocation. The path a
  deployment actually takes is the flagless one, and for all three it did something worse than fail:
  ACMG's fell through to scraping NCBI's page, which serves **v3.2** while the snapshot holds v3.3, so
  a correctly authored row came back reported as wrong; the other two skipped themselves with
  `no_reference` about a catalogue sitting in the cache directory.
- **Three lanes had the licence to publish and no way to.** The roster's own comment called CIViC's
  absent `ensure_*` a *gap* rather than a refusal — CC0 grants redistribution outright — and STRchive's
  MIT and the drug labels' CC BY-SA say the same on their own terms. What was missing was plumbing.

**What shipped.** `caches.CACHE_LANES` is a registry: one entry per lane, carrying its three stages
(acquire, build, publish) and, for each stage it lacks, **the reason as a field rather than a
comment**. `test_cache_lanes.py` walks it against the `*_build` modules on disk in both directions,
which is the check a list could never have (`@registry-completeness`). Resolvers and cache
subdirectories for acmg, strchive and drug_labels, each wired into the *flagless* branch of its own
check, and the tests assert the **call** rather than the resolver — a resolver nothing calls passes
its own unit test while leaving the defect exactly where it was (`@ensure-must-be-called`). Publish
and provision for CIViC, STRchive and the drug labels, with `strchive publish` and
`clinpgx publish-labels` as new commands. And `cache rebuild`, the endpoint the question asked for:
one command over eleven builders, calling the same `download_*`/`build_*` the per-lane commands call,
so there is one conversion algorithm with two callers rather than two that have to agree.

**And `cache prepare` beside it, which is the command a deployment actually wanted.** `cache pull`
fetches the published snapshots and stops, so a machine that only pulled is short exactly the four
lanes nothing publishes — and those four are unpublished *for recorded reasons*, which means the gap
was permanent rather than pending. `prepare` runs each lane by the route it has, pulling or building,
and the route is a property of the lane rather than a flag: asking an operator to choose would be
asking them to restate the licensing story. It leaves a present cache alone, like `pull`, and stages a
built one beside its target rather than writing into a live cache directory — a build there is visible
half-done, and unlike a truncated download no footer check catches it because the file is real.
`prepare_caches` and `rebuild_caches` are the Python halves, returning one outcome per lane in
registry order.

**Two shapes had to be generalized to get there, and both were premises rather than bugs.** The
publisher assumed every snapshot is `data/*.parquet`; ACMG's is `acmg_sf.csv` and STRchive's is
`STRchive-loci.json`, each at the snapshot root. `plan_reference_snapshot` now takes the payload
filename **from its caller** — a lane knows what it builds, and a roster of lane filenames inside the
publisher would make it the fourth place a new snapshot kind has to be taught about. The provisioner
could *not* be generalized the same way and is not: `_provision_snapshot` is parquet all the way down
and a JSON file has no footer to check, so `_provision_root_file_snapshot` gives the same guarantee by
parsing before the rename.

**`publish_reference_snapshot` now derives its allowlist from the plan** instead of restating it as
patterns. The two were separate statements of one thing that had to agree and twice did not — that is
how `citations/` and `LICENSE.txt` each went a release printed-in-the-dry-run and dropped-on-upload
(`@publisher-allowlist-derived`). One list, so a dry run is a promise.

**The rebuild outcome is three-valued, and the third state is the item's most load-bearing decision.**
ACMG needs a workbook that is Elsevier supplementary material, PharmVar a personal key, CIViC a release
date to pin, Ensembl is built by just-dna-pipelines. Folding those into *failed* would have a nightly
rebuild alarm on four lanes behaving exactly as their licences intend; folding them into *built* would
be a lie. They print as **not run** with the registry's own reason, and the exit code counts only real
failures. Each lane builds into `<base>/<lane>/`, **never in place** — a rebuild takes minutes and a
short parquet still has a `PAR1` footer, so an `enrich` reading a half-written snapshot sees a real but
incomplete table and no resolver can catch it.

**Two defects the suite caught rather than review**, and both are the repository's own recorded
shapes. `clinpgx publish-labels` had landed *after* the `__main__` guard, where nothing registers it.
And `cache status` composed its instruction as `f"{name} build"`, which is right for ten lanes and
names two commands that do not exist — there is no `drug_labels build` and no `constraint build` — so
`build_command` is a field the guard invokes against the real Typer tree (`@warning-text-is-api`).

**The dependency question the item also asked was already answered**: every builder-only dependency
(`polars`, `openpyxl`) is in the `[dev]` extra behind a guarded import, and no runtime check reads
either. Nothing moved.

**Four defects its own probe found, after the round looked finished**, and three of them are the
item's own shapes turned back on it. *One:* the default `cache pull` exited 1 on a fresh machine,
because three lanes gained an `ensure_*` before anyone created their repos and the transport's error
reached the blanket handler as a failure — nobody-published is the same third state as nobody-asked,
so `SnapshotNotPublished` is its own type and is printed rather than counted. *Two:*
`Path("./x.xlsx").as_uri()` raises, so `--source acmg=./workbook.xlsx` — the *documented*
invocation — produced a traceback instead of an outcome. *Three:* the PharmVar adapter reported every
exception as *not run*, folding a lane that broke into a lane that opted out; the split is decided
before the request now, from whether a key is configured at all, because the service's 401 is
identical for an absent, a malformed and an unrecognised key and a flat `PharmVarError` cannot carry
the difference (`@answered-is-not-absent`). *Four:* the CIViC adapter fetched the release VCF
unconditionally, which RM169 made opt-in because it *widens the status basis* — so one release would
have built two different snapshots depending on which caller asked, the exact fork this endpoint
exists to prevent.

**And two more the maintainer's question found, both `@credential-where-read`.** Asked whether the
endpoint handles credentials kept in a `.env`, it did not — for `$PHARMVAR_API_KEY` and `$HF_TOKEN`,
the two the operator actually holds. The PharmVar one is the worse of the pair and is this round's own
tri-state repair turned against it: the guard deciding *no key configured* versus *a key that failed*
read `os.environ` directly, while `PharmVarClient.__init__` calls `load_env()` before reading the same
variable — so the key was visible to the builder and invisible to the check standing in front of it,
and the lane claimed the designed third state on exactly the machine most likely to have a key. **A
pre-check that answers differently from the code it guards is worse than no pre-check.** `$HF_TOKEN`
failed honestly by comparison: `_hf_api` called `get_token()`, which reads the real environment and
`~/.cache/huggingface/token`, so a publish refused. Both load where the credential is read now, and
the probes run in subprocesses with the real variables stripped and `HF_HOME` redirected — otherwise
they pass on any laptop that has ever run `hf auth login`.

**Left undone on purpose.** The three new repos — `just-dna-seq/civic`, `just-dna-seq/strchive`,
`just-dna-seq/clinpgx_drug_labels` — do not exist on HuggingFace; the first publish creates each, and
until then both `ensure_*` and `cache pull` say so rather than failing obscurely. No lane's snapshot
was rebuilt or uploaded as part of this. And the PGS/PRS parquets under `just-dna-seq` are **out of
scope by decision**, not by oversight: `pgs-catalog`, `prs-percentiles`, `prs-sample-scores` and
`polygenic_risk_scores` are built by `just-prs`'s Dagster pipeline, and pulling them into this tier
would cross the dependency-tier rule the charter's Goal 2 states.

## RM175 — the PGx lane's default archive was a retired filename, and every row it had ever built came out of a frozen 2025 object

**Severity** high · **Status** ✅ **SHIPPED 2026-09-02 in the uncut 0.7.0** — the rebuild onto
`summaryAnnotations.zip` plus the guard that refuses the retired one (`just-dna-enricher`; no schema,
no vocabulary, no parquet column) · **Owner** enricher · **Motivating case** the maintainer's
2026-09-02 investigation ([CLINPGX_ARCHIVES](probes/CLINPGX_ARCHIVES.md)), which started from RM173's
canary and found what it was a canary of · **Supersedes** RM173

**PharmGKB renamed the table on 2025-07-29** ([the ClinPGx launch
post](https://blog.clinpgx.org/pharmgkb-is-now-clinpgx/)): *"Clinical annotations … are now called
**summary annotations**."* The archive followed. `clinicalAnnotations.zip` was last written to S3 on
**2025-07-05, twenty-four days before that post**, and has not been rebuilt since; it is on no
downloads page; and the API still answers it **200** through a 303 to the frozen object.
`clinpgx_build.DEFAULT_CLINPGX_URL` named it.

**So this was not a stale cache and not a slow source.** Every `annotations.parquet` this lane had
built, every PGx row drafted from it and every check that read one rested on a snapshot of the database
as it stood **fourteen months ago**, and nothing in the response said so — a retired filename that
still 200s is indistinguishable from a live one at the HTTP layer. RM173 measured the 13-month gap
correctly and diagnosed it as two live surfaces refreshing out of lockstep. It was one live surface and
one leftover.

### What shipped

`summaryAnnotations.zip`, `CREATED_2026-08-05`, is the same 15-column table under new names:

| 2025 archive | 2026 archive |
|---|---|
| `clinical_annotations.tsv` | `summary_annotations.tsv` |
| `clinical_ann_alleles.tsv` | `summary_ann_alleles.tsv` |
| `clinical_ann_evidence.tsv` | `summary_ann_evidence.tsv` |
| `clinical_ann_history.tsv` | `summary_ann_history.tsv` |
| `Clinical Annotation ID` | `Summary Annotation ID` |

The other fourteen column names are identical and in the same order, and `Phenotype Category` has the
same values with the same `;` separator, so **no vocabulary moved and no model changed**. The builder
reads two of the four members; the evidence and history siblings are renamed upstream and named
nowhere in this tier, so they cost nothing. What changed is the URL, two member names, the id column,
the numbers derived from the old file — and the guard.

**The guard is the item.** An archive carrying the old member names parses perfectly and yields a
plausible parquet, so `require_current_archive` reads the member names *before* anything else and
answers in three arms (`@answered-is-not-absent`): the current spelling builds; the retired one is
refused with the rename, its date, the retired filename and the URL to build from instead
(`@specific-rejection` — a generic "member missing" is a dead end where naming the rename is a fix);
an archive that is neither says so separately, listing what it holds. `clinpgx build` prints
`CLINPGX BUILD FAILED: …` and exits 1, matching `build-labels`.

Both spellings live in **one table** the reader takes its member names and its id column from, so the
guard cannot drift from what the builder reads (`@suppression-from-merge-key` has the same shape).
`RETIRED_ARCHIVE` is returned by nothing: no path through the module can read a 2025 archive, which is
stronger than refusing to. No compatibility layer was built, deliberately — a reader that parses both
vintages is a reader that can still publish 2025 data.

**It was not a rename-only patch, because the data moved.** Re-derived against both archives on
2026-09-02: over the 5,179 ids in both, 7 annotations gone, 11 new, **8 rows change `Level of
Evidence`**, 2 `Variant/Haplotypes`, 40 `Drug(s)`, 14 `Score`, 68 `Level Modifiers`, and every `URL`
rehosts `pharmgkb.org` → `clinpgx.org` on a path that still reads `/clinicalAnnotation/`. At the
snapshot's own grain the rebuild is 16,087 → **16,117 rows** across 5,186 → **5,190 annotations**,
1,086 → 1,087 genes: 22 (annotation, genotype) keys gone, 52 new, and among the 16,065 shared keys
30 rows change `evidence_level`, 120 `drugs`, 47 `annotation_text`, 38 `phenotypes` and 4 `subject`.
The parquet digest moves, and a module drafted from this lane can see an evidence level change under
it — which is correct, and is the first thing this lane has ever had to say about currency.

**And one recorded number was wrong twice.** `clinpgx_build`'s docstring said *"4,618 of 5,113 carry
exactly three"* genotype rows. 4,618 is the 2025 file's three-genotype count and 5,113 is neither
file's annotation count (5,186 then, 5,190 now) — it is the *distinct-key* count of the
`clinicalVariants` rollup. The pair appeared in five live files. It is gone from all of them, replaced
by the relationship ("the large majority carry exactly three") rather than by a fresh count: a number
measured off one download is exactly what this item is about. The fixture-bearing measurements that
are *dated but true* — 396 of 16,087 rows with a multi-gene cell (RM74), 15,331 of 16,087 with a gene,
1,199 of 17,380 colliding triples (RM29b) — were left as the release-time evidence they are.

**The fixture is real bytes now.** `assets/clinpgx_annotations_slice/` is cut verbatim from the
2026-08-05 archive: the real `LICENSE.txt` and `CREATED_*.txt`, the three rs4149056/simvastatin
annotations that disagree with each other, and a real CYP2C19 haplotype annotation replacing an
invented id the old in-memory fixture carried. Every expected value is computed from it at runtime, and
the retired-vintage archive the guard is tested against is **the same rows under the old member names
and the old header** — one copy of the data, two spellings, so the refusal is proved against an archive
that would otherwise have built.

### The general half, which is why this was severity high and RM173 was not

A filename can retire while its bytes keep serving, and **nothing in this lane could have noticed**:
the download succeeded, the members parsed, the licence read, the row count was plausible, and
`release.json` recorded a `CREATED_*.txt` nobody compared against anything. Three candidate guards were
listed when the item was sized, and **none was built** — the item is a rebuild, and each of the three
is a design in its own right:

- **Audit every default URL in the lane against what the source lists.** ClinPGx serves 19 zips;
  `drugLabels.zip`, `relationships.zip` and `clinicalVariants.zip` are all on the page and
  `clinicalAnnotations.zip` is not. A one-off read, not machinery — and one that needs a browser, per
  the trap below.
- **Record the S3 `Last-Modified` beside the `CREATED_*.txt`** in `release.json`, so an archive that
  stops being rebuilt is visible in the artifact rather than only in the source.
- **Fire when one archive of a multi-archive source is much older than its siblings** — the shape
  RM173 stumbled into, generalised. `@two-surfaces-two-denominators` is the neighbour, and
  `@currency-asks-the-source-not-the-cache` says the question goes to the source.

The name check that shipped is narrower than any of them on purpose: it catches *this* failure — a
retired name still serving — at the only moment the lane can see it, without claiming to detect
staleness in general. Nothing built here would notice `summaryAnnotations.zip` itself going quiet, and
that gap is the honest remainder.

**A trap that cost the investigation real time, and belongs in the record.** Every ClinPGx HTML route
— `/downloads`, every help page — serves the same JS shell whose no-JS body is *"Javascript Is
Disabled!"*. `curl` and `WebFetch` therefore **cannot** answer "is this file listed?", and both return
200 while telling you nothing. The downloads listing in the probe is a rendered-DOM capture from a
browser. Treat a no-JS fetch of this host as no evidence at all (`@probe-the-real-file`, one host
further on).

**Related** RM173 (closed into this), RM166 and RM29b (both built on the lane this rebuilds), RM164,
`@two-surfaces-two-denominators`, `@currency-asks-the-source-not-the-cache`, `@probe-the-real-file`,
`@pgx-research-only`.

## RM166 — the whole PGx lane is one licence class, and a second authority exists that is not in it

**Severity** low-medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** — the cross-check
built, **the licence half closed measured** (`just-dna-enricher`, plus one
`VALID_VERIFICATION_CHECKS` member; `compiler/` untouched) · **Owner** enricher ·
**Motivating case** the 2026-09-01 source-adoption round

**The item split, and only one half is code.** What builds is a `drugLabels.zip` builder beside
`clinpgx_build` — the same cache, the same payload-read `LICENSE.txt` handling, its own
`CREATED_*.txt` and therefore its own `release.json` — and a regulator-label cross-check joining at
**two tiers**, the star-allele tier where `Variants/Haplotypes` supplies one and the gene tier
otherwise, with the tier **distinguishable in the finding** because a gene-level agreement and an
allele-level agreement are not the same claim.

**The half that closes is the one the item was filed for, and it closes on measurement rather than on
deferral.** The entry wanted a PGx lane member whose terms may not gate. Both routes refute it: the
ClinPGx route is CC BY-SA + no-sale, **the same gate**, so it diversifies nothing; and the FDA's own
Table of Pharmacogenetic Associations is **126 associations in an HTML page** with no bulk download and
**no copyright or public-domain statement on the page at all**. *"US government work is public domain"*
is a rule with exceptions, the entry said so, and the page does not settle it. So the direct route
supplies a quarter of the FDA content ClinPGx already carries, in a shape that must be scraped, on
terms that are unestablished. Leaving that half open would have left an item riding on a source shown
not to serve it. **If licence diversification for the PGx lane still matters — and it plausibly does,
being a single point of failure on the axis the format gates on — it wants its own entry, with
candidates chosen for their terms first**, which is the opposite of how this one chose.

**It is five regulators, not one, and the surface is named for the labels.** `Source` counts: FDA,
Health Canada, EMA, Swissmedic, PMDA. The entry asked for the FDA and the file supplies four more at
no extra cost, which turns the concordance shape from *module ↔ authority ↔ authority* into a lane
where **the number of authorities is a parameter** — exactly what RM134's vocabulary split was built to
survive. Naming any one agency in the surface would bake an authority into a published key, the
mistake RM134 caught in `ClinSigConflict` before it shipped.

**The join key exists, contra the entry's own closing worry.** `Genes` is populated on ~87 % of rows
and `Variants/Haplotypes` on ~15 %, and the star-allele tokens in the latter are `haplotypes.csv`'s key
verbatim. So *"a check with no key to join on is not a check"* is answered: a gene-level key for most
rows, an allele-level key for a sixth, **and the sixth is where this lane's rows actually live**.

**A blank `Testing Level` is `unknown` and withholds.** Roughly a third of the file states none, which
is an absence and not a *no*: reading it as `No Clinical PGx` would manufacture a negative regulatory
claim on 472 rows. Kleene, not a default — and the levels the snapshot states that the vocabulary does
not know are **collected and reported** rather than folded into an "other" bucket
(`@lookup-with-a-default-hides-a-new-member`).

**It warns in both modes**, like every other cross-check in this round: five expert regulators
genuinely disagree with each other and with a curator, and failing would make the format arbitrate
between its own authorities (`@clinsig-never-escalates`).

**The finding that outgrew the item, noticed and not built.** ClinPGx publishes **at least twelve**
archives and `clinpgx_build` reads one. `clinicalVariants.zip` is the one bearing on a shipped table
kind — ~5,190 rows of `pharm_variants.csv` territory, whose `type` is a six-member base vocabulary that
**comma-combines**, so any adoption normalizes the *combination* rather than the token. The honest
restatement is that the PGx lane reads one of twelve files from a source it has already adopted and
gated, and the FDA question was a narrow way into a broad finding. It wants its own number.

**What the code review found after the item was written, and it is a shape rather than a slip.** The
lane shipped a `VALID_AUTHORED_POSITION` holding five members while `just_dna_format.vocab` already had
that **exact name** holding five different ones — the clinical-significance concordance axis. Nothing
broke, because one test file imported one and another the other, which is precisely what made it
dangerous: the collision is invisible until a third caller imports both and the later `from … import`
wins silently, and two members are shared so even a spot-check passes. A lane-local vocabulary carries
the lane's prefix, and the rule is now `@a-lane-local-vocabulary-may-not-shadow-a-schema-one`. Its
related half: **a reason map only a test reads is a map nothing speaks** — the equality guard over the
sentence maps passed while every actual reader still met a bare token with no statement of what it
claims.

The same pass corrected two measurements this entry would otherwise have preserved. An allele claim
whose gene-tier sibling was never answered had been counted as *no label names this allele*, when the
truth is that nothing was asked about its gene either; it is withheld, and the three buckets are now
asserted as a partition rather than checked one at a time. And the gene-qualified join composes a token
**two ways**, because the file spells it two ways — the star alleles run together (`TPMT*3A`) and the
DPYD haplotypes are spaced (`DPYD c.2846A>T`) — so trying only the concatenation told a DPYD module its
allele was named by no label while two regulators named it exactly. A false coverage claim, which is
worse than a miss.

**`@two-surfaces-two-denominators` is the live rule**: ClinPGx's bulk file and the FDA's web table are
different sources with different denominators, and any count either produces must say which. And
`clinpgx_build`'s own docstring records that `relationships.zip` was a year newer than
`clinicalAnnotations.zip`, so this archive carries its own `CREATED_*.txt` rather than inheriting the
lane's release.

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm166--the-whole-pgx-lane-is-one-licence-class-and-a-second-authority-exists-that-is-not-in-it)**,
which proposed 0.8 and was overturned: *largest in the batch* and *least urgent* is an argument about
**order**, not about the release. It was sequenced last so that an early cut would leave one item in
flight rather than four.

**Related** RM134 § B, RM29b, `@pgx-research-only`, `@two-surfaces-two-denominators`,
`@clinsig-never-escalates`, `@acquisition-gate-is-not-a-read-gate`.

## RM167 — LitVar2/PubTator3 answers "which papers name this allele", which is the half PubMind structurally cannot

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher`,
plus one `VALID_VERIFICATION_CHECKS` member; `compiler/` untouched) · **Owner** enricher ·
**Motivating case** the measured limits of the PubMind adoption (RM134)

**The entry set its own test and the test passes.** [PUBMIND_ASSESSMENT](PUBMIND_ASSESSMENT.md)
measured that PubMind has *record* identity, not variant identity — 68,744 coordinate keys carry more
than one PVID, HFE C282Y alone holds eight with four different verdicts — and the entry proposed
LitVar2 as an independent second vote on exactly that fan-out, *"complements if LitVar's identity is
genuinely allele-level"*. It is. BRAF rs113488022's three CAIDs resolve to three distinct ALTs at one
position and carry 31,276 / 99 / 41 papers: allele resolution doing real work, three orders of
magnitude apart.

**The finding is that the tier a locus is answerable at is a property of the LOCUS, not of the
source.** APOE rs429358's position node carries 3,945 papers and its single allele node carries 328,
so **92 % of the literature at that locus is not allele-resolved**. A pass reporting the allele node's
count as *the* answer would understate it twelvefold. So the shipped pass names which tier answered:
allele-resolved, position-only, absent — plus `unchecked` as the fourth state the house algebra needs
— each arm with its own reason sentence, the fall-back to the position node **never silent**
(`@refutation-withholds`: a position-level answer to an allele-level question withholds rather than
answering approximately), and the position-only residue counted over the union of every allele node
rather than folded into the matched one (`@dont-discard-computed`).

**It writes no row, which was pre-authorised and is a complete outcome rather than a half-done one.**
A PMID list per variant is not a table kind, `literature.csv` is keyed by article, and `sources.csv`
means *this module uses this source*, which would be false here. What lands is one
`literature_coverage` attestation.

**The corpus measurement, which the entry made the build's first task.** Over the 11 reference modules
carrying a `resolution.csv` — **389 loci, of which 180 (46.3 %) have at least one CAID node**: 165
answered at allele tier, 92 at position tier only, 122 absent, 10 could not be asked. **14,168 papers
sit on a position node no allele node claims**, 6,700 of them APOE's.

**Three of the proposal's own numbers did not reproduce, and that is the round's shape again.** Its
*"of 588 HFE nodes … 299 are gene-level"* conflates two id shapes: measured off the recorded payload
there is **exactly one** gene node (3,285 papers) and **298 text mentions**, which is a fifth shape
(`litvar@#<gene_id>#<protein_name>`, all three `flag_*` false) and not a variant at all. The
**423-locus join does not reproduce** — a roster derived from `DRAFTABLE` finds 389 loci and 388
distinct rsIDs. And the stated id grammar `litvar@<clingen_id>#<rsid>#<gene_id>` is contradicted by the
proposal's own example: `litvar@rs1800562##` puts the rsID in the ClinGen slot, so the field count
varies by tier rather than the slots being fixed.

**The bound ships with the pass, in its own documentation.** Measured against the two records this
workspace could not resolve — CIViC 1955 and 2131, worked down in
[CIVIC_LEGACY_INSERTIONS](probes/CIVIC_LEGACY_INSERTIONS.md) to four candidate alleles with registered
CAIDs — LitVar returns **no node for any of the four**, and the one nominal hit for `VHL P71fs` is an
unrelated paper that happens to write the string. The reason is structural: PubTator3's export for all
four source papers is title and abstract only, with **zero variant annotations**, and the alleles live
in a table inside a paywalled paper. So **on precisely the class this workspace built a protocol for,
LitVar is the wrong instrument** — it answers *which papers discuss an already-identified allele* and
never *which allele this name meant*. Those read as the same question and are not.

**`data_clinical_significance` is not adopted in any form.** It is populated on position nodes and
`None` on every allele node measured, so it is position-level, unattributed, undated, and cannot even
be attributed to the allele it would be voting on.

**Two API facts pinned before anyone writes a second client.** `variant/search/gene/GENE` returns
**line-delimited Python `repr()`, not JSON** — `.json()` raises on it, so the shipped client parses
rather than deserializes (`@probe-the-real-file`). And NCBI publishes a **policy, not a licence**: it
places no restrictions and in the same passage declines to grant permission, so under
`@no-named-licence` every gating axis is `None`. Recording it as public domain by analogy with ClinVar
is exactly the move that rule forbids — ClinVar has a page saying so and this surface does not. NCBI's
side only; nothing is asserted about EMBL-EBI's terms for surfaces EBI co-hosts.

**It also repaired a defect one file over.** `clingen_allele._parse` computed a one-sided allele and
then discarded it whenever an rs-number arrived, because the rsID alone makes the outcome `resolved` —
so every PALB2 indel read as incomparable. `unanchored` now travels on a `resolved` result too.

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm167--litvar2pubtator3-answers-which-papers-name-this-allele-which-is-the-half-pubmind-structurally-cannot)**,
which reversed twice: an earlier draft proposed CLOSES on a misread id, the file then proposed BUILDS
in 0.8, and the maintainer pass took it now — the three stated blockers were a small client, a tiering
rule that is the item's own result, and an artifact question the entry had already pre-authorised.

**Related** RM134, RM153, `@existence-not-identity`, `@probe-the-real-file`, `@no-named-licence`,
`@refutation-withholds`, `@dont-discard-computed`.

## RM165 — `repeat_alleles.csv` has no source, and RM65/RM66 have been waiting on exactly the corpus one would bring

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher`,
plus one `VALID_VERIFICATION_CHECKS` member; `compiler/` untouched) · **Owner** enricher ·
**Motivating case** RM65's own stated prerequisite

**What shipped, and the split is the finding rather than a caution.** STRchive — `dashnowlab/STRchive`,
**MIT**, 82 loci across 79 genes — is adopted **by column**: a `check-repeat-bands` cross-check over
`benign_*`/`intermediate_*`/`pathogenic_*`, and a `draft-repeats` provider over the identity half. Two
commits, so the check is revertible without the provider.

**The reason the bands are checked and never drafted was measured on both corpus modules, and it is
one agreement and one disagreement.** STRchive reproduces `htt_repeat_expansion`'s first two bands
exactly — `benign 6–26`, `intermediate 27–35`, independently authored, about as strong a validation as
a drafting provider can get before it is written. And it gives FMR1 a single `intermediate 45–200`
where the module has `45–54` and `55–200`: **the boundary it does not have is 55, the premutation
threshold**, and the module's own conclusions name what would be lost — the 45–54 grey zone where *"the
carrier is not at risk, but the allele may be unstable in transmission"*, and the 55–200 FXTAS/POF
range. Drafting the three bands straight would have erased a clinically load-bearing line in one of the
corpus's two modules. The finding names the missing boundary rather than reporting that the tables
differ.

**`pathogenic_max` is emitted nowhere, and this is the second refusal worth keeping.** STRchive gives
HTT 250 where the module leaves `measure_max` empty. A catalogue's `pathogenic_max` is the largest
allele the literature reports — an **observation**, not a clinical bound — and written as `measure_max`
a 300-repeat allele would match **no bin at all**, silently, `--strict` included, which is the exact
silence RM55 shipped a loud warning about (`@bin-grounding`). It is reported as its own finding kind
instead. `@verbatim-except-order` is about not re-encoding a source's values; it is not a licence to
import a bound the source did not intend as one, and **the band's meaning is the schema's, not the
catalogue's**.

**It warns in both modes.** Two curators disagreeing about a threshold is not a `strict` matter
(`@clinsig-never-escalates`), and a `strict` run reports exactly what a best-effort run reports.

**Four things the build contradicted, and the first is the most useful.** *The identity half is mostly
uncarryable*: `RepeatAlleleRow` has no column for coordinates, `locus_structure`, `ref_copies` or the
OMIM/MONDO disease ids, so a drafted row is gene, motif, trait and a stubbed conclusion. That gap **is**
RM65/RM87 rather than a shortfall in this provider — the entry proposed drafting columns the schema
does not have. *No `DRAFT_PROJECTIONS` entry is owed*, because the split means the checked columns were
never copies, and a test asserts the absence with the reason. *HTT is finer than the catalogue too*,
dividing the pathogenic band at 40, which the entry named only for FMR1. And drafting into a real
shipped module exposed a **pre-existing crash** in `just_dna_compiler.draft.append_partial_rows` on any
table whose header is narrower than its model; it reaches all four existing partial-row providers, was
reproduced independently of this work, and is left for its own item because `compiler/` was barred this
round.

**Two things named and deliberately not built.** RM66's evidence is real and partial — `locus_structure`
is present on **23 of 82** loci, HTT's being the `(CAG)n(CAA)(CAG)` structure RM66 asks about, published
as typed data with its own three-member vocabulary, while FMR1's is `[]`. That is enough to *decide*
RM66 and not enough to make the answer universal; naming the evidence and stopping was the whole of
this round's obligation to it. And STRchive's `evidence` is a ClinGen-style validity classification on
all 82 loci **including Disputed 3 and Refuted 1** — a second instance of **RM170**'s problem in a
different domain, worth knowing before RM170 is designed against CIViC alone.

**gnomAD's tandem-repeat release is out on category, not on terms.**
`gnomAD_STR_genotypes__2022_01_20.tsv.gz` is `Genotype`/`Allele1`/`Allele2`/`Sex`/`Age` — **one row per
sample per locus**, per-sample genotype data, the one category this format does not carry — so the
question of inheriting `GNOMAD_TERMS` never arises. A category exclusion is cheaper and more durable
than a licence answer, because it cannot be renegotiated.

**RM65's attached obligation carries forward**: `_write_resolution_csv`'s positional pass hard-codes
`locus_index = 0`, honest only while these tables never expand, and repeat coordinates are exactly what
could expand one (RM87).

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm165--repeat_allelescsv-has-no-source-and-rm65rm66-have-been-waiting-on-exactly-the-corpus-one-would-bring)**
— which drafted the provider as held to 0.8 and was overturned: the deferral assumed a cut about to
close, and the argument that the split made deferring the larger half cheap reads equally well as an
argument that the half is cheap.

**Related** RM65, RM66, RM87, RM164, RM170, `@bin-grounding`, `@enrichment-is-validation`,
`@verbatim-except-order`.

## RM163 — `pgs.csv` is keyed on a Catalog accession and nothing ever asks the Catalog about it

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher`,
plus two `VALID_VERIFICATION_CHECKS` members in `just-dna-format`; `compiler/` untouched) ·
**Owner** enricher · **Motivating case** the 2026-09-01 source-adoption round

**What shipped.** A fourth registry in `identifiers.py` and a `pgs.py` client asking the PGS Catalog
about every authored `pgs_id`, `PGS_TERMS` as a per-score licence **floor**, and `pgs_catalog` as the
second member of `currency.default_probes`. It attests under **two** names — `pgs_accession_currency`
and `pgs_metadata_agreement` — because currency asks whether the id still names a score and drift asks
whether two cells beside it still match: different questions, different subjects, different
denominators, and one record over two populations publishes a findings count that means nothing.

**The verdict is read off the body, never the status.** `GET /rest/score/PGS999999` — a never-assigned
id — returns **HTTP 200 and `{}`**, and so does `GET /rest/score/PGSXXXX`, which is not a well-formed
accession at all. So the status code carries no existence information and a withdrawn score, a typo and
a malformed id are indistinguishable *by construction*. `@existence-not-identity`, and RM153's warning
about a 200 that is not an answer arriving in a second source.

**And the absence message is weighted by a measured base rate, which is `@rsid-absent-two-readings`
run backwards.** About 35 % of the accession range is assigned, so an unrecognised `pgs_id` is
overwhelmingly a *never-assigned* one. dbSNP earns its equal-weight treatment because its id space is
densely assigned and merges are a frequent, real event; here the base rate runs the other way, and
naming withdrawal as a co-equal reading would send an author looking for a retirement notice that
almost certainly does not exist. The message states the absence, states the sparsity, and names
withdrawal as the rarer reading — and where the Catalog offers no supersession field at all, that is
stated as a limit of the source rather than resolved by guessing.

**Drift is over two fields, not the four the entry named.** Reading the model rather than recalling
it: `match_rate_floor` is described in its own `Field` as *"Author-set variant-match floor"* and
`research_tier` is a two-member curator judgement. **The Catalog publishes neither**, so there is
nothing to drift them against, and a check with no source-side value is a check that cannot fail
(`@tautology-zero`). The reason is written down where somebody would otherwise add them later. What
is checked is `training_ancestry` against `ancestry_distribution` and `training_cohort` against
`samples_training`, reporting and never repairing.

**The licence half is the one that had to be right, and it is a correctness requirement rather than an
optimisation.** `license` is a field on each **score record**, not a property of the Catalog: over the
first 250 of ~6,982 scores, most carry the generic *"used in accordance with any licensing restrictions
set by the authors"* string, a handful are academic-research-use-only — the class `licensing.py`'s own
comments name as barring redistribution outright — and a couple are CC0. So `PGS_TERMS` is written as
the **floor**, with EBI's terms-of-use URL and every gating axis `None`, and each score's own `license`
string overrides it in that score's `SourceRow`. `@licensing-as-data`, the shape ClinPGx's bundled
`LICENSE.txt` already uses, and `@per-article-terms` one source over: the Catalog is a **host** for
scores licensed by their authors. **The consequence is visible rather than theoretical** — a module
naming a single academic-use-only score is now refused by the compile gate *by name*, where one flat
constant would only have warned, and would have been a false claim in the permissive direction.

**Currency is read, not built.** `/rest/info` publishes the release date, the score count and the
trait and publication totals, so the infrastructure this item wanted did not have to be written — the
same finding as MANE's `README_versions.txt` in RM168, and the second time in one round that a source
turned out to publish its own release record.

**Four things the build contradicted, all of them recorded.** The section's e2e recipe wanted one spec
directory carrying a malformed accession beside a live one; `PgsRow` refuses `PGSXXXX` at load, so it
never reaches the Catalog and the malformed case has to be probed at the client. *"A drifted cell is
the author's to fix or to answer in `overrides.csv`"* is **impossible** for these cells — the overlay
is derived-tables-only and `pgs.csv` is authored, so the sentence names a remedy that does not exist
and the finding has no silencing route. `PgsRow` disagrees with itself about which ancestry
`training_ancestry` means: the name says training, the description says *"validated in"*. And
`/rest/release/current` bought nothing over `/rest/info`, so it is not read.

**Severity is deliberately split.** An unrecognised accession escalates under `--strict`; a metadata
disagreement never does, because the Catalog and a curator are two authorities and the format does not
arbitrate between them (`@clinsig-never-escalates`).

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm163--pgscsv-is-keyed-on-a-catalog-accession-and-nothing-ever-asks-the-catalog-about-it).**
**RM16 is not re-opened** — that is authored per-variant weights and stays deferred on a missing
consumer; `PgsRow` is a manifest of Catalog ids and this item touched only the manifest.

**Related** RM16, S86, RM153, `@existence-not-identity`, `@licensing-as-data`, `@tautology-zero`,
`@rsid-absent-two-readings`.

## RM168 — the identity procedure downloads MANE by hand, and nothing in the code knows the file exists

**Severity** medium · **Status** ✅ **SHIPPED 2026-09-01 in the uncut 0.7.0** (`just-dna-enricher` only;
no schema change, no authored column, `compiler/` untouched) · **Owner** enricher ·
**Motivating case** [CIVIC_IDENTITY_PROTOCOL](probes/CIVIC_IDENTITY_PROTOCOL.md) § 3b

**What shipped.** `MANE_TERMS` in `licensing.py`, a `mane/` cache with `$JUST_DNA_MANE_CACHE` and the
`default_mane_cache_dir` / `resolve_mane_reference` pair, `mane_build.py`, a `mane build` sub-app, a
`_CACHES` row, and an `ENRICHER.md` lane section. **Three files in one pass**, together under 1.2 MB:
the summary, `changed_select_accessions` and `protein_coding_genes_not_in_mane`. Splitting them was
refused for a reason worth keeping — the second file *is* the currency check, so shipping the cache
without it would ship the thing this item complains about (a version pinned in prose that nothing will
notice going stale) with a cache wrapped round it.

**The source publishes its own staleness list, and its own provenance.** `README_versions.txt` is 96
bytes and states the MANE version, the NCBI RefSeq annotation release and the Ensembl release; the
builder **copies** it rather than parsing a filename, because two of those three are in no filename and
reconstructing less information than the source hands over is `@probe-the-real-file` backwards.
`changed_select_accessions` carries `Update_Affects_CDS` — **the numbering-frame axis, stated by the
source**: a MANE Select change that moves the CDS moves every `c.` and `p.` derived in that frame, and
one that does not, does not. So the currency check for a numbering frame turns out to be *read one
small file*, not *diff two releases*.

**`MANE_status` is a column and is never collapsed**, which is the decision the item exists for. 74 of
19,437 rows are MANE Plus Clinical (0.38 %), and CDKN2A is the case: two rows for GeneID 1029 with
different CDS numbering, `NM_000077.5` MANE Select beside `NM_058195.4` MANE Plus Clinical. A builder
keeping one row per gene would drop them and reintroduce the exact blind spot the table can see and a
remembered accession cannot.

**And the negative roster is a third state served by the source.**
`protein_coding_genes_not_in_mane` lists 222 genes **with a reason** over a seven-member vocabulary —
`gene not on assembled chromosomes`, `gene located on mitochondrial genome`, `pending MANE review` and
four others — so *"MANE has no answer for this gene"* is distinguishable from *"nobody asked"*
(`@unreachable-not-absent`), and `pending MANE review` is neither absent nor decided. The vocabulary is
**derived from the file and asserted as an equality against it**, so a reason MANE adds is counted
rather than joining an "other" bucket (`@registry-completeness`).

**The bound ships with it: MANE is the default, not the answer.** RUNX1 is a single row, and the
27-residue RUNX1c/RUNX1b offset § 3b derived by translating each isoform's CDS is **not in MANE and
cannot be**. The table makes the CDKN2A class of problem visible and is *silent* on the RUNX1 class, so
a pass treating it as an oracle would be wrong in a way the file itself cannot warn about. Said in the
lane's documentation rather than left for a reader to rediscover.

**Terms: NCBI publishes a policy, not a licence.** `license=None`, `license_url` at the policy, the two
operative sentences in `notice`, every gating axis `None` (`@no-named-licence`). *No restriction
imposed* is not *permission granted*. MANE is a joint NCBI/EMBL-EBI product and **only NCBI's side was
read** — the terms constant says so, and asserts nothing about EMBL-EBI's. Consequently there is no
`--use` flag on the build and no `ensure_mane_snapshot`: a declared-use gate whose every answer is a
skip is a flag that does nothing (`@acquisition-gate-is-not-a-read-gate`), and nothing publishes a MANE
snapshot to ensure.

**Pinned by the versioned directory, never `current/`.** One 96-byte request reads `current/` to
*discover* the newest version, and the answer is resolved to a `release_<v>/` URL before anything is
downloaded — so a build is pinnable after the fact. That distinction became its own gotcha,
`@current-discovers-a-version-a-directory-pins`.

**Why it went first.** Nothing else in the round depends on it and the identity protocol does: it is
the only item that makes an already-shipped result re-derivable — RM159's 33 curated name→identity
answers were derived in this frame, and the frame was recorded nowhere a re-derivation could read.

**Probed and decided in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm168--the-identity-procedure-downloads-mane-by-hand-and-nothing-in-the-code-knows-the-file-exists).**
Worth recording: of the round's six items this is **the only one whose probe the build did not move**.
Every fact was re-measured live against NCBI while building — 19,437 rows, 74 MANE Plus Clinical, 120
changed accessions with `Update_Affects_CDS` Yes on 74, 222 excluded genes over exactly 7 reasons,
CDKN2A two rows, RUNX1 one, VHL `NM_000551.4` — and none of them contradicted the entry. In a round
whose keeper is that five of six entries said something their own probe contradicted, the one that held
is the one whose questions were cheapest to ask.

**Related** RM159, RM153, RM152, `@snapshot-layout-locations`, `@release-json-provenance`,
`@current-discovers-a-version-a-directory-pins`, `@accession-version-names-no-build`.

## RM169 — the wider basis was published as a dated file all along, and nobody had looked

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`;
**no schema change**) · **Owner** enricher · **Motivating case** RM160, whose central premise this
item falsified

RM160 was filed on the finding that `civic build` reads the `accepted`-only bulk TSV while the API
serves 2.35× as much, and it stated the tension as a reproducibility bargain: *the API has no dated
release to pin*, so any wider read costs the snapshot its byte-reproducibility. All three shapes it
proposed were ways of paying that price.

**The premise was false, and the check was one HTTP request.** CIViC publishes
`<date>-civic_accepted_and_submitted.vcf` **inside the same dated release directory** the builder
already reads. It is pinnable, hashable and immutable exactly like the three TSVs. Nobody had probed
the download surface past the files already in use — the survey named three TSVs and stopped.

### What the file is, and why it is not the input

The whole release surface, enumerated: seven TSVs and two VCFs. (`GeneSummaries.tsv` is
**byte-identical** to `FeatureSummaries.tsv` — one file under two names.) The VCF carries one `CSQ`
entry per evidence item, with `CIViC Entity Status` on each.

**But it is a strict subset of the TSV, and the subset is not arbitrary.** A VCF record needs a POS,
so a variant with no GRCh37 coordinate cannot appear at all. Over `01-Aug-2026` the accepted VCF holds
473 direction rows on 236 variants against the TSV's 533 on 290 — and **52 of the 54 it drops are
exactly the `unresolvable_identity` class**, the records whose identity RM159 had to read out of their
names. Reading the VCF as the row source would silently discard the hardest-won half of the snapshot.

So the TSV pair stays primary and the VCF is joined onto it, behind `--submitted`.

### What it added, measured

| | accepted | accepted+submitted |
|---|---:|---:|
| Rows | 507 | **1,149** |
| …of which `submitted` | 0 | 642 |
| Variants | 270 | **397** — 127 of them new |
| refget coordinates cross-checked | 57 | **129**, 0 mismatches |
| `input_rows` the drop registry closes over | 4,878 | 8,328 |

`release.json` gains `status_basis`, `status_counts`, `vcf_evidence` and `unjoinable_submitted`, and
every row gains `evidence_status` carrying CIViC's own word. **A rebuild on the wider basis is
byte-identical**, so Principle 7 survives the join.

### The second accepted-only file, which is why `vcf_csq` exists

`VariantSummaries.tsv` is `accepted`-only **too** — a fact nothing had stated. So **112 of the 127**
variants the submitted evidence introduces have no row there at all: no gene, no aliases, no HGVS, no
registry id. A first cut kept identity strictly TSV-sourced and recovered only 15 of them.

The same `CSQ` entry carries all four identity cells, so for a variant the TSV cannot describe they
are read from there instead — through **the same parsers**, on **the same published identifiers**:

| route | variants |
|---|---:|
| ClinGen CAID only | 57 |
| rs-number only | 40 |
| GRCh38 accession only | 14 |
| both an rs-number and a coordinate | 1 |
| **total** | **112** |

Those rows are stamped `identity_derivation="vcf_csq"`, a member of its own: the routes inside are the
ordinary ones, and what the member names is the **file**, which is the part a consumer cannot
otherwise recover. Measured over the emitted parquet, not over the input — 172 rows on those 112
variants, and the other 15 new variants join the TSV normally and take an ordinary derivation.

**Nothing is placed from the VCF's own position.** It is GRCh37 throughout
(`##reference=…GRCh37-lite.fa.gz`) and lifting it stays refused (RM48); a CSQ-sourced row leaves the
`civic_grch37_*` provenance columns empty rather than recording a coordinate whose build this file
never states, and a test pins it.

### Two guards the round earned

- **The drop registry caught a real accounting error.** A first cut counted submitted items that
  could not join under a new drop reason — but those rows never entered the evidence list the
  registry's equality is over, so the input total disagreed with the list the loop walks. The guard
  raised (`@registry-completeness` working exactly as designed), and the count moved to its own field,
  `unjoinable_submitted`, outside the registry.
- **The vocabulary is enumerated, not computed.** The VCF spells members `SCREAMING_CASE` where the
  TSV uses title case, and a `.title()`-shaped rule gets `RARE_GERMLINE` right and
  `SENSITIVITYRESPONSE` wrong — the TSV writes it `Sensitivity/Response`, with a separator the VCF
  drops. Three exceptions in twenty members is a map, and it raises on an unmapped member rather than
  emitting a mis-spelled token (`@lookup-with-a-default-hides-a-new-member`).

### What this leaves for RM160

Its **coverage** half is answered and closed here. Its **provenance** half is not: the sweep behind it
found that 10 of the 20 records nothing can place gain citations only a wider basis carries, and the
VCF reaches **none of them** — it holds 0 of those 10 and 1 of the 53 unresolvable variants, for the
structural reason above. That half still needs the API or nothing, and RM160 stays open carrying it.

## RM159 — the identity a source states in a variant's name, adopted rather than left in a probe

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`;
**no schema change**) · **Owner** enricher · **Motivating case** the 2026-09-01 residue round
([CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md))

`civic build` placed a row from what CIViC puts in its *identifier columns* — an rs-number, or a
GRCh38 RefSeq accession it can parse — and dropped 53 variants as `unresolvable_identity`. For most
of them the identity was published the whole time, one column over: in the variant's own `name`.
`N150fs (c.448delA)`, `IVS2+1G>A`, `D1709N`. A `c.` or protein fragment plus the gene's numbering
frame is an allele, and an allele registry holds it.

**Adopted: 33 of the 34 that resolved.** Coverage over the dated `01-Aug-2026` release goes from
**237/290 variants (81.7%) to 270/290 (93.1%)**, and from 474/533 evidence rows (88.9%) to
**507/533 (95.1%)**. `unresolvable_identity` falls from 59 rows to 26.

**The one excluded, and why it is not an oversight.** CIViC 4968 `TP53 R72P` resolves — rs1042522,
CA178298 — and its identity is the **reference** allele: codon 72 is `CCC` = Pro on GRCh38, so the
name has reference and alternate inverted, and the registry answers `NC_000017.11:g.7676154G=`.
A snapshot row is `chrom/start/ref/alt` and `ref == alt` is not a variant row. The identity exists and
this representation cannot carry it, which is a fact about the representation.

### Why the answers ship as data and the procedure does not run

Resolving a name needs the network, and `civic build` must stay byte-reproducible from a pinned dated
release — which is why the CAID pass (RM153) runs at *draft* time and never in a build. The obvious
repair is therefore "do this at draft time too", and it was refused: **four of the 33 required a
judgement no lookup makes.** A legacy `IVS2` name that converts structurally to the wrong exon
(788 — the structural answer `c.319+1` and the true one `c.444+1` are both real registered alleles
9 kb apart, so nothing in a lookup flags the error); a name pairing a missense protein label with a
*synonymous* cDNA change (2459); a protein consequence standing over an intronic allele (804); an
rs-number that is position-level where two alleles spell the same substitution (2196). A draft-time
resolver would either fail on those or silently pick a side.

So the **answer** is a shipped constant — `civic_identities.CIVIC_NAME_IDENTITIES`, 33 rows carrying
coordinates, rsID, the CAID as provenance and a note where one was needed — the **procedure** is
written down as [CIVIC_IDENTITY_PROTOCOL](probes/CIVIC_IDENTITY_PROTOCOL.md), and the build stays
offline. `P9` — zero authored-layer cost, no CSV, no column.

### The name is the key, and that is the safety property

Every identity was derived from the `name` string quoted beside it, so a build applies a row only on
an **exact** name match. Each curated row lands in exactly one of four counted states, published in
`release.json` and asserted as an equality over the walked table (`@registry-completeness`):

- `applied` — the name still matches, CIViC still publishes no identifier, the row was placed.
- `superseded` — CIViC now publishes an identity of its own. **The source always wins**, and a
  supersession is the cheapest currency signal available: it means the upstream has curated.
- `renamed` — the variant is there and its name changed. The answer was an answer to a name.
- `absent` — the variant is not in the file. Kept apart from `renamed` on `@unreachable-not-absent`:
  over a full release it means withdrawn, over a slice it means nothing at all.

A curated answer therefore cannot outlive the record it answered, which is what makes a hand-built
table safe against the next release rather than merely correct for this one.

### What the external check says

`civic reproduce` cross-examines every placed coordinate against the GRCh38 reference through
refget/seqrepo — an unrelated service asked whether the reference base at each position is what the
snapshot wrote. It read 24 coordinates before this item and reads **57 of 57 with 0 mismatches**
after. Every one of the 33 hand-read alleles is confirmed at its stated position by something that
has never heard of CIViC.

### Two smaller things the adoption fixed on the way

- **`allele_registry_id` is untouched.** It is CIViC's verbatim cell and is empty for all 33 by
  definition; the CAIDs the probe recovered live on the curated table as provenance. Writing them into
  the source's column would publish a finding as if the source had made it, and a test pins it.
- **`curated_name` is its own `identity_derivation` member**, not folded into `rsid`/`grch38_hgvs`.
  Those mean "the source stated this in the column for it", and a consumer must be able to exclude the
  difference without re-deriving it. The drafter needed no change — it special-cases `caid` and lets
  every other member through the placed path — but that is now an equality over the vocabulary rather
  than a property nobody checked (`@lookup-with-a-default-hides-a-new-member`).

## RM162 — `RM_TOC.md` is an index, and an index is not an allocator

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (tooling only — no package,
no schema change) · **Owner** the triage loop · **Motivating case** the 2026-09-01 collision, git
`741ec59`

The consumer-suggestion loop has had an allocator for `Sn` since it was built (`triage-state.py
--next`), because the id is written into a document and a stale one collides. `RMn` never got one.
`docs/RM_TOC.md` is the complete index of every item — that is what it was written for — but reading a
number out of it *claims* nothing, so the procedure was grep the highest, add one, and write the entry.
The window between the read and the write is exactly where a second session reads.

**Reproduced rather than hypothesised, and by this loop on itself.** On 2026-09-01 two sessions sharing
this working tree filed different work as **RM159** a minute apart, and the tree carried two RM159
entries pointing at different items. `741ec59` renumbered one to RM161, picking the cheaper move: the
other pair was contiguous and already referenced from three probe documents and the enricher reference.

**Grepping cannot fix this.** Any read-then-write with a gap has the same race, so the claim has to be
a single atomic write: `.claude/rm-next.py` scans every `docs/**/*.md` and appends the reservation
inside one critical section. Scanning outside the lock and appending inside it would be the same defect
with a smaller window, so the scan is in there too.

**The lock is on `docs/`, the directory, and the second reason was measured.** A lockfile left behind by
exactly the kill this guards against would block every later run, and the staleness rule that repairs
that is a clock — `@flock-not-a-lockfile`, the idiom `transaction.spec_lock` already uses for `enrich`.
The sharper reason is that `flock` binds an **inode**: an editor or an atomic writer that renames a new
file over `RM_TOC.md` leaves the holder locking an unlinked inode while a second process opens the new
file and acquires immediately. Verified in a sandbox before the tool was written — locking the file
would have looked correct and excluded nothing.

**A reservation is a visible index row, not a side-car.** `🔷 reserved`, under the open-items heading,
replaced by the item's real row when the entry is written. A number claimed and abandoned is then
*visible* rather than silently burned, and a state file the index cannot see is precisely how a number
goes missing — the failure `RM_TOC.md` exists to prevent. Placement is checked: the file ends in a prose
section, and a row appended at EOF would read as part of it, which is the furniture hazard the triage
loop's own §6 records one document over.

**`--release` leaves a tombstone, and the first cut of this shipped the bug it fixes.** Deleting the
reservation row made the number invisible to the scan, so a released RM10 was immediately re-reserved as
RM10 — contradicting the rule the tool's own docstring states. Ids are never reused: whatever argued the
withdrawal refers to the number, and reusing it makes two items answer to one name in the record. The
tombstone has to contain the number literally, since a scan is all that reads it. Found by running the
release path rather than by reading it.

**Pinned by a guard watched failing.** `test_rm_allocator.py` runs eight allocators at once and asserts
eight distinct contiguous numbers — and runs *the same eight with `flock` neutered*, asserting they
collide. Without that second test the first passes for reasons that have nothing to do with the lock.
The unlocked run produced 5 distinct of 8, with one number taken three times.

Also corrected: the loop's own Step 5 hygiene bullet said to read the number off `RM_TOC.md`, which is
the instruction the incident came from, and named `RM47` as the highest — a counter in prose, stale for
114 items (`@counted-prose-needs-a-fixed-field`).

## RM161 — a release record's two halves are written at different times, and the second left the first behind

**Severity** high (a red release gate) · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0
(`just-dna-format`) · **Owner** format · **Motivating case** the pre-build gate run for the 0.7.0 cut

`sweep --release 0.7.0` exited **1** with two findings: `gene_validity.superseded_count` and
`identity.version_coerced_from` *"moved and the release record does not list it"*. Both are real
manifest additions from the 2026-08-31 batch, both carry a `DeclaredChange` written the day they
landed, and neither was in the record's `manifest_fields`. The readiness table had recorded the gate
green on 2026-08-31; the two declarations were added at 06:52 and 07:04 that morning, after the
measurement the list came from.

**The shape is the record's own construction.** `SweepMeasurement.as_record` produces the *measured*
half — `axes` and `manifest_fields` — with `declared` deliberately empty, so the gate keeps refusing
until a person classifies each movement. That split is what makes the gate work, and it is also what
lets an item landing after the measurement add its declaration and leave the measured list behind.
Nothing in a checkout could see it: the gate needs the previous release installed and is a
release-sequence command by design, so between two cuts the record can be wrong for a fortnight and
every test stays green.

**The guard is an asymmetry, not a symmetry.** A declared **addition** must appear in
`manifest_fields`: a field that did not exist before moves wherever its block appears, so a release
claiming to add one while measuring no movement is claiming something its own corpus contradicts. A
declared **correction** may legitimately be unmeasurable — 0.7.0 declares `gene_validity.classifications`
and `gene_metrics.signature`, and no reference module carries a re-curated gene-validity claim or a row
from the snapshot the second is about. Those stay declared and unlisted, and the gate already has a
*note* for the reverse case. Asserting the full set equal would have forced two false claims into the
record to silence a true one.

The test walks `RELEASE_RECORDS`, so a future release joins by existing. It fails on the pre-fix tree
naming exactly the two fields, which is the whole point: this was findable offline and was not being
looked for.

**Evidence unchanged.** The record's `evidence` sentence already carried today's numbers
(`content_signature 0/15, manifest_fields 15/15, parquet_bytes 14/15, parquet_schema 14/15, warnings
3/15`) — only the field list was stale, which is why nothing else in the record needed touching. After
the fix: *"release record for 0.7.0 covers the measurement"*, exit 0.

## RM158 — the GWAS pass asked about one table's rsIDs, and the answer already existed in this package

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** the RM155 sweep, third instance

`gwas._module_subjects` built its `(rsid, variant_key)` list from `variants.csv` while five authored
models carry `rsid`, so a module whose rsIDs live in `haplotypes.csv` or `pharm_variants.csv` got no
associations and no line saying none had been asked for. Reproduced against the pre-fix code: a spec
carrying one `haplotypes.csv` row for `rs4244285` — CYP2C19\*2, which the Catalog has associations for
— returned `[]`.

**What makes this the useful one of the three: the fix was already written.** `enrich.Subject` and its
collector exist for precisely this question, and the docstring says so — resolution read `variants.csv`
alone until RM43, so a PGx module *"which by design carries **no** `variants.csv`"* enriched to an
empty `resolution.csv` and shipped with no coordinates at all. That repair normalized the question to
a subject and let three tables through the unchanged resolver. The GWAS pass, written afterwards,
restated the narrow loop instead of calling it. So the shape recurs even where the package has already
paid to end it, and a sweep is worth more than a fix: **grep for the question, not for the bug.**

`_collect_subjects` and `_Subject` are now `collect_subjects` and `Subject` — a private name is what
kept the second caller from finding the first. `studies.csv` carries `rsid` and is deliberately not a
subject: a study row *references* the variant it grounds, which the module already carries as a row of
its own, so admitting it would add no rsID and only change which table an identity came from.

**Nothing moves for a module that already had subjects.** Measured across the corpus before and after:
`pathogenic_clinvar` (301), `hboc_palb2` (16), `mt_heteroplasmy` (2) and `grch37_build` (0) return
identical lists, because `variants.csv` goes first in the collector and first occurrence wins — the
precedence that exists so a PGx row cannot take an identity a SNP row minted. This pass inherits it
rather than re-implementing it.

**No schema change**: no column, no vocabulary member, no signature moves.

## RM157 — the gene set three passes take their scope from read one table while nine carry the column

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** the RM155 sweep, run against this repo's own corpus

`gene_metrics.module_genes` built its list from `variants.csv` alone while nine authored models declare
`gene`. It is not a report: it is the **scope** of the constraint-metrics pass, the gene-validity pass
and the ClinGen dosage pass — all three call it, the second through a wrapper that exists only to
re-raise its error as its own type — so a module whose genes live in its PGx tables had all three
quietly do nothing. No rows, no findings, and no line saying a question had not been put.

**Measured on the corpus, not on a fixture.** `cyp2c19_star_alleles`, `apoe_epsilon`,
`cyp2c9_warfarin_grch37` and `hfe_compound_het` returned `[]` here while naming CYP2C19, APOE, CYP2C9,
VKORC1, CYP4F2 and HFE on rows an enrichment could have asked gnomAD and ClinGen about. A fixture
written to the widened roster cannot produce that evidence, which is the general rule this pair of
items leaves behind.

**The workspace was already carrying two answers to one question.** `pgx._module_genes` reads two PGx
tables, and this one read a table those modules do not have; nobody had put them side by side. And the
pass had already been patched for the *symptom* without anyone asking why the list was empty — RM104
bound `reference` before the branch because "any module with no `variants.csv`" raised
`UnboundLocalError` out of a run where `wanted` came back empty. That sentence was in the code, in a
comment, describing the defect as a shape rather than a question.

**Derived, and refusing rather than narrowing.** The set now comes from the same registry walk the
identifier roster uses (`@registry-completeness`), so a table kind that gains the column joins by
existing and a second implementation cannot drift from the first. A table that exists and will not
parse **raises** here, in this pass's own phrasing — a reporting surface may route an unreadable table
to `not_read`, but a scope may not: half a gene set is a silently narrowed one, which is the same
defect one table wider. `IdentifierRoster` gained `read_errors` so the loader's own message survives
into that refusal instead of being reconstructed by string surgery, which is what keeps
`gene_validity`'s `variants.csv is invalid` diagnosis exactly as it was.

**`pgx._GENE_TABLES` stays two tables** and is not this roster: it decides whether the star-allele
cross-check *applies*, which is a fact about that check's inputs rather than about what the module is
about. Widening it would run the cross-check over modules carrying no star alleles at all.

**No schema change**, and no ordering change: `gene_metrics` sorts its rows by `(gene, dataset)` before
writing, so the roster's order reaches no artifact. What moves is that three passes now have a scope on
modules where they had none.

## RM156 — the widened roster was gated behind the one table it had stopped depending on

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** the RM155 sweep, run against this repo's own corpus

RM155 widened `check_identifiers`' rosters from `variants.csv` to the nine authored tables that carry
each column. Two gates in front of it were still keyed on `variants.csv` alone, so on the module shape
the widening was most for, the wide roster was never reached: `check_identifiers(spec_dir=)` loaded
that table unconditionally and raised `variants.csv is invalid: ... not found`, and the command
returned *"no variants.csv — nothing to check"* one call earlier and hid it.

**The table has never been mandatory (RM2), and four of the nine carrying `gene` are the PGx kinds a
module is built entirely out of.** Reproduced on this repo's own reference examples rather than a
fixture: `cyp2c19_star_alleles`, `apoe_epsilon`, `cyp2c9_warfarin_grch37` and `hfe_compound_het` carry
no `variants.csv` at all, and between them name CYP2C19, APOE, CYP2C9, VKORC1, CYP4F2 and HFE on rows
the roster now reads. `check-identifiers` printed *"no variants.csv — nothing to check"* and exited 0
on every one. That is S86's unreadable `0` surviving one level above the function that repaired it,
which is the more useful half of the lesson: a widening is not done while a caller still gates on the
narrow thing.

**The old guard's comment is what dated.** It justified writing no attestation on the grounds that such
a module "has no `gene`, `trait_efo_id` or row for these checks to have an opinion about, so the check
does not APPLY". The first clause became false the moment the roster walked `DRAFTABLE`; the second —
no attestation without a question — was right and is kept, now derived: nothing to check means **no
id-bearing table was read**, which is a fact about the roster rather than about a filename. Both checks
switched off is a different state and keeps its own path, recorded as `not_requested`.

**A third site, found by following the rows.** With `variants` empty and symbols in hand,
`_gene_locus_conflicts` returned `compared=0` with `None` beside it — the `ran(0, 0)` its own
attestation docstring forbids, and the same vacuous pass a third time. It now returns the reason: no
`variants.csv` rows, so no symbol could be placed against a variant's chromosome. The guard sits
*before* the "no row names a gene" arm because it is the more specific fact — since the widening, a
module can reach that code with genes and no rows.

Present-and-unparseable still raises, deliberately: that is a module whose rows exist and cannot be
read, which is the author's to fix rather than a shape the check should tolerate.

**No schema change**: no column, no vocabulary member, no signature moves. What moves is which modules
the check runs on at all.

## RM153 — the identity CIViC does not publish, recovered through the registry rather than by lifting a coordinate

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`; additive — one new client, one
snapshot derivation, two withhold reasons, one licence row. **No schema change.**)
**Severity** low-medium · **Owner** enricher · **Motivating case** measured while building RM152

The residue RM152 left: CIViC publishes GRCh37 coordinates or none, and after every published
identifier is read, some variants still have no route to a GRCh38 identity. The item carried two
questions — should a ClinGen CAID be resolved, and should the remainder be lifted over. **Both are now
answered, and they answer in opposite directions.**

### What was measured

Over the dated `01-Aug-2026` release, 533 germline direction rows on 290 variants:

| | Variants | |
|---|---:|---|
| Recovered by the builder before this item | 138 | 48% |
| Recoverable through a ClinGen CAID | **+64** | 52 via an rs-number, 12 via a GRCh38 coordinate |
| …plus one-sided indels the registry states, once anchored | **+35** | 22 deletions, 13 insertions — **all 35**, no exceptions |
| **After RM153** | **237** | **82%** |
| No identifier of any kind | 53 | of which **9** carry a GRCh37 coordinate |

The registry answered all 102 probe requests with **zero failures**, serves both an rs-number and a
GRCh38 coordinate, and needs no key.

**A correction to this item's own figures, and then a correction to the correction.** It said 131
unreachable where the dated release gives 157. That gap was first written up as nightly-versus-dated —
reach numbers from one file, row counts from the other. Re-measured on **2026-09-01** it is not two
files at all: the nightly and `01-Aug-2026` are identical on this slice, and 131 versus 157 is one
file read two ways, counting variants that *carry* a GRCh38 accession (40) against variants carrying
one `parse_grch38_substitution` can *read* (12). 157 is the number the builder acts on.
[CIVIC_SURVEY](probes/CIVIC_SURVEY.md) carries the measurement and now labels the *definition* behind
every identity figure, not just the file.

### What shipped

- **`clingen_allele.ClingenAlleleClient`** — CAID → rs-number and/or GRCh38 coordinate, paced, cached
  per run, with **three outcomes and never two**: `resolved`, `no_identity` (the registry answered and
  holds none — a 404 is an answer), `unchecked` (a 5xx or a transport failure), plus
  `skipped_offline`. It raises nothing; the outcome *is* the contract, which is why it joins
  `Grch37Client` in the exception-contract suite's named exemptions rather than being given an error
  type to leak.
- **`identity_derivation="caid"`** — the snapshot now **keeps** a CAID-only row with null coordinate
  and null rsID, instead of dropping it. It has a *route* to an identity rather than an identity, and
  dropping it made the recovery invisible to every later pass. `unresolvable_identity` now means no
  identifier of any kind, and falls from 204 rows to 59.
- **The pass runs at draft time, not build time.** A build that fetched would forfeit the offline
  byte-reproducibility that is the whole reason `civic build` reads a dated file. `--offline` is the
  switch, as it is everywhere in this tier, and a run without the registry withholds those rows as
  **`caid_unresolved`** — unplaced, never unplaceable.
- **The rs-number is preferred over the coordinate**, and the reason is the item's central argument:
  ClinGen supplies it and the ordinary resolution chain verifies it against **Ensembl**. Two
  authorities, so the check is real — which is precisely the property a lifted coordinate lacks.

- **One-sided indels are anchored VCF/Picard-style, and that closed the last recoverable class.** The
  registry states an insertion as `referenceAllele=""` and a deletion as `allele=""`, in interbase
  terms — neither is a row a `ref`/`alts` pair can hold. Prefixing both sides with the single
  reference base before the event is the left-aligned representation VCF requires, and the registry's
  interbase `start` *is* that anchor position for both shapes, so one rule covers them with no
  per-shape arithmetic. `anchor_indel` is a pure function with the base reader injected; the reader is
  `SequenceProxy`, already in this tier for the reference-allele check. **All 35 rows that previously
  read `no_identity` are one-sided indels, and every one anchors.**

  Verified two ways rather than asserted: the reference base at `chr3:10142013` is `G`, and ClinGen's
  own HGVS for that allele is `NC_000003.12:g.10142013dup` — a duplication of `G`, which is exactly
  the `G>GG` row produced. An anchor that cannot be read is withheld under its own reason
  (`anchor_base_unreadable`), never guessed: a guessed anchor is a wrong `ref` on a right position,
  which is the mismatch class `sequences.RefMismatch` exists to report.

Measured end to end, the drafter goes from **115 variant rows offline to 201 online**, withholding
nothing.

### Repairs rejected

- **Liftover.** Reopened at the maintainer's instruction with new balance weights and refused on the
  measurement — the full probe is [CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md). Its ceiling is
  **13 evidence rows on 9 variants**, 2.4% of the corpus, and after analysing what those events *are*
  the honest recovery is **at most one variant**. Three are gene-level assertions (`Loss`, `Mutation`)
  that no genotype satisfies on any build. Five are imprecise by the source's own HGVS
  (`c.1-?_340+?del`) — the ClinGen registry **refuses those expressions outright**, which is a
  stronger statement than a count: they have no allele identity on either build. And variant 2099 is
  the worked instance of RM48's hazard: its own coordinate pair says 15 bp while its name and alias
  say 24, and lifting CIViC's coordinate exactly yields **a different allele** from the one the source
  is describing. The format cannot defend itself either — a fabricated `<DEL:340>` and a bare
  gene-span locus both compile clean in both modes.
- **`pyliftover` as a dev dependency.** Tried. It agrees with Ensembl on all 18 endpoints, so it buys
  no accuracy; it downloads an unpinned chain file from UCSC at construction; and the assembly-map
  endpoint already returns interval *segment structure*, which two point-lifts cannot.
- **Picard `LiftoverVcf` as the tool of record.** Not run, and the reason is worth keeping. Two
  independent implementations already agree to the base on all 18 endpoints, so a third would confirm
  arithmetic nobody disputes — while eight of the nine carry no `REF`/`ALT` at all, so feeding
  `LiftoverVcf` would mean **fabricating** symbolic records with invented spans, which is
  manufacturing the input whose correctness is the question. The blocker was never the mapping.
- **Resolving CAIDs inside `civic build`.** It would make the snapshot depend on a live service and
  cost the reproducibility the dated input exists to provide.
- **Inheriting ClinGen's CC0 for the registry.** The gene-curation surface is CC0; this is a different
  surface, and `reg.clinicalgenome.org/site/terms` answers **HTTP 200 with a generic Genboree
  "broken link" page** — a soft-404, the same shape as HPO's licence URL. Every axis is recorded
  `None`: unknown is not permissive. Nothing is redistributed, and reading a public endpoint to place
  a row is a read rather than an acquisition anyone has gated.

### Charter check

P2 — the fetch is in the enricher, the only tier permitted one. P3/P8 — no column, no table, no
vocabulary member; a new `identity_derivation` value on a **derived snapshot**, which is not the
authored surface. P5 — `caid_unresolved` and `caid_no_identity` are two withhold reasons because they
are two facts, and collapsing them is the S20 defect. P7 — the snapshot stays byte-reproducible
precisely because this pass is not in it. P9 — zero authored-layer cost.

### What it left open

**53 variants carry no identifier at all**, and five of the nine coordinate-bearing ones can never be
reached by any identity pass, because an unambiguous identity does not exist for them. That is a
permanent floor on CIViC's germline reach rather than a gap to close.

Two smaller residues are sized in the probes and not taken: 26 unresolved variants publish a GRCh38
**deletion** accession the substitution-only parser cannot read *directly* — most are reached through
the registry instead, which is why this was not worth a second parser — and 31 carry a `c.` HGVS
inside their *name* rather than in `hgvs_descriptions`. Whether a name plus a transcript resolves
through the registry was not measured and is the obvious next question.

**Measured on 2026-09-01, and the answer moves this item's residue a long way.** It does resolve: all
53 were put through a four-tier identity procedure and **34 of them have an identity**, from the
fragments CIViC publishes in the variant's own name. The paragraph above understated it by testing a
per-**gene** fact (which transcript a `c.` fragment is numbered against) as a per-**record** one, so
29 variants were written off for lacking a `representative_transcript` cell. Thirty-three of the 34 were adopted the
same day as **RM159**, taking coverage from 237/290 to **270/290 variants** and 474/533 to **507/533
rows**; the one held back is `TP53 R72P`, whose identity is the reference allele and so is not a
`ref`/`alt` row. The "53 carry no identifier" sentence
above therefore stands only as the state at this item's cut. What survives unchanged is the five that
can never be reached, plus six more that name a class of event rather than an allele. Class by class,
with the four wrong CIViC names and three self-duplicates the round also turned up, in
[CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md).

## RM152 — CIViC's germline quarter says almost nothing on the axis we asked it, and a great deal on the one next to it

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`; additive — a new snapshot
builder, a new drafting source, one licence row, and no schema change of any kind).
**Severity** low-medium · **Owner** enricher · **Motivating case**
[S84](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator), 2026-08-31

**The item was filed carrying no release class**, because both adoptions S84 proposed had been refuted
by measurement and an item with no repair has none to state. It acquired one when the probe it named
was finally run: the refutations stood, and a third route nobody had proposed turned out to be
buildable. The full measurement record is [CIVIC_SURVEY.md](probes/CIVIC_SURVEY.md), which is evidence
and not contract.

### What was measured, and by whom

S84 reported the germline split and declined to claim the follow-up probe. The reply named it —
`SUPPORTS`/`DOES_NOT_SUPPORT` × `PREDISPOSITION`/`PROTECTIVENESS` against `VALID_DIRECTIONS`, over a
corpus that can say how much it reaches — and it was run on 2026-08-31. Every figure in the item
reproduced, including the 412 obtained by subtraction. Four things it did not know:

1. **The contested count was wrong in both directions.** The item read `PREDISPOSITION` ×
   `DOES_NOT_SUPPORT` as "4 items, precisely the reading `contested` was added for". Grouped by
   molecular profile it is 1; grouped by **variant**, which is the granularity identity uses, it is
   **3**, because a two-variant profile's refuting row propagates to both members while each carries
   supporting evidence on its own profile. Two of the original four are lone refutations, which
   `contested` does not describe. **Genuine opposition — a risk call against a protective one — is 0**,
   at every scope probed and under every status basis.
2. **Widening the scope changes nothing.** All 620 variants re-swept with no origin, significance or
   status filter: 2,811 items, 11 newly camp-bearing, every one `SUPPORTS` on a variant already
   carrying risk, **0 new contested variants**.
3. **The assertions table cannot carry the axis at all.** Not thinly — *structurally*.
   `AssertionSignificance` is a different 16-member enum that does not contain `PREDISPOSITION` or
   `PROTECTIVENESS`, so filtering by them is a GraphQL type error rather than an empty result. No
   CIViC assertion can ever hold a direction call, however the database grows.
4. **The number everything quotes has an undeclared denominator.** Both connections default to
   `status: NON_REJECTED`, so the 11,518 in the item and the report is that basis; `ACCEPTED` is 4,904.
   The bulk TSV release is `accepted`-only at 4,903 rows. Two published surfaces of one source, 2.35×
   apart, neither declaring it.

### What shipped

- **`civic build`** — a dated release reduced to one parquet plus `release.json`, byte-reproducible.
  It reads the **bulk TSVs**, not the API, because only the download side has dated releases and a
  snapshot that cannot name its input cannot be reproduced; `release.json` records the `accepted`
  basis so a count from it is never compared with one from the API. Three input files, because
  `MolecularProfileSummaries.tsv` is what tells a combination genotype from a dangling reference.
- **`draft-panel --source civic`** — writes `direction`, never `clin_sig`, reading the snapshot.
- **`CIVIC_TERMS`** — CC0 1.0, permissive on all three axes.
- **A defect in shared drafting code**, found by dogfooding rather than by review: `append_partial_rows`
  built its covered-set from `partials[0].match_on` while comparing each row against its own, so a
  batch of mixed arity re-added rows on every lap. Fixed at the provider and guarded at the helper.

### Repairs rejected

- **CIViC as a concordance authority.** S84's preferred candidate, refuted before this round and
  confirmed by it: five germline ACMG-tier calls, **zero** benign-class, so `discordant` is unsayable.
- **A `direction`-axis concordance apparatus.** The open question the item carried, and the answer is
  no. Genuine opposition is 0; the 3 contested variants are claim-against-refutation, all three
  dissolve under `ACCEPTED`, and nothing else in the enricher fills `direction` — `clinvar_draft`'s
  fold targets `state`, the legacy axis, and `@axes-passthrough` bars crossing them. A concordance
  record needs two authorities and this axis has one.
- **`draft_from_civic` on the `clin_sig` axis.** Still refused, and the surviving half of the item's
  own objection is the silent somatic drop — now a counted drop rather than a filter. The half that
  did **not** survive is "it would write rows with an empty significance column": true of `clin_sig`
  at 812 `NA`, and false of `direction`, where `NA` is 0 of 1,458. The rejection had been measured on
  the axis the report aimed at rather than the one the item itself identified as surviving.
- **Liftover, to reach the GRCh37 coordinates.** Reopened on the maintainer's instruction and closed
  again on the number — see [RM153](ROADMAP_HISTORY.md#rm153--the-identity-civic-does-not-publish-recovered-through-the-registry-rather-than-by-lifting-a-coordinate).
- **Reading "does not support predisposition" as `protective`.** A refutation removes a claim without
  establishing its opposite. The row is kept, the axis value withheld, and the count reported.

### Charter check

P1 — a snapshot is data and a drafted row is an ordinary authored row; no predicate language. P2 — all
of it in the enricher, the only tier permitted to fetch; the compile path imports none of it. P3/P8 —
**no schema change at all**: no new column, no new table, no vocabulary member, nothing demoted or
retyped, no published module invalidated. The whole adoption rides on `direction` and `state`, which
have existed since 0.3. P5 — `direction` and `clin_sig` stay separate axes, which is the entire finding.
P7 — a rebuild is byte-identical and a re-draft is a no-op, both pinned. P9 — the snapshot is the free
layer and the drafter writes only authored columns that already exist, so the authored surface is
priced at zero.

### What it measured

Over the `01-Aug-2026` release: 4,878 evidence rows in, 329 kept on 133 variants; dropped
`non_germline_origin` 4,067, `not_direction_axis` 278, `unresolvable_identity` 204, and the two
structural reasons 0 each. Identity: `rsid` 305, `both` 17, `grch38_hgvs` 7. Drafted into an empty
spec: 110 variant rows and 311 study rows, every study row carrying a real PMID.

## RM146 — every authored column now says which release it appeared in

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`; **additive** — a marker on each
field declaration, no column, no parquet, no signature). **Severity** medium · **Owner** format
(schema) · **Motivating case** [S81](CONSUMER_SUGGESTIONS_HISTORY.md) (just-dna-registry, relaying
just-module-creator)

### The finding

A module authored on 0.6.6 was sent to a registry deployment running format 0.6.1, which runs our
`validate_spec` server-side and reports its findings verbatim:

```
studies.csv line 2 [curator]: Extra inputs are not permitted
```

`StudyRow.curator` is ours, added in 0.6.5. A genuine typo produces the byte-identical shape
(`[curatr]`), and the two want **opposite actions** from an author — upgrade the reader, or fix the
cell. The finding is pydantic's under `extra="forbid"`, so it could not be reworded into carrying the
distinction: the information was not in the model at all.

### What shipped

`base.since("0.6.5")` on every authored field, read back by `base.field_first_seen(model)`. It
composes with `vocabulary()` rather than replacing it — both are entries in one `json_schema_extra`
dict — and `stamped_identity_field` takes `first_seen` as a **required** argument, because a
compiler-stamped column is still one an older reader refuses and defaulting it would let the next such
column inherit a version nobody measured.

**On the field, not in a roster.** A list keyed like `release_records` was the alternative and loses on
the rule this repo keeps relearning: a hand-kept list beside a model is a second statement of one fact,
and it is the copy that goes stale. Declared on the field, it travels through every rename and move.

### The backfill was measured, and the numbers are worth recording

Parsed out of each release tag's own sources — `git ls-tree` per tag, the model classes read from the
**AST** rather than imported, since old code need not import under a current Python. **414 fields
across 31 models**, and the distribution is a fair summary of this format's history: 115 fields date to
0.2.0, 81 to 0.4.0, 150 to 0.5.0, 160 to 0.6.0, 3 to 0.6.5, and 78 land in the uncut 0.7.0.

**`curator` is the worked example and it is the reason the answer is per `(model, field)`**: it is on
`VariantRow` from 0.2.0 and gains its `StudyRow` twin only in 0.6.5. A roster keyed by column name
would have given one answer for two facts — and the wrong one for the module in the report.

### The guard, and why it is an equality

`test_first_seen.py` asserts **set equality over the walked registry**: every field of every model in
`_ALL_MODELS` declares one. A floor (`>= 400`) or a truthiness check is satisfied by exactly the state
that produced this report (`@registry-completeness`). Two guards ride with it — the registry itself is
checked for completeness, since a guard over an incomplete registry reports a clean bill about the
models it happens to know (RM96's shape), and every declared version is checked against the set of
releases that actually exist, because a typo'd number is the one error the model cannot catch itself.

### Two things the build turned up

**A mechanical edit needs an AST, and the AST needs to know what a field is.** The first pass wrapped
nine `ClassVar` declarations — `ALLELE_COLUMNS`, `REQUIRED_ANY_OF` — in `Field(...)`, which is not a
field at all; the suite caught it as `TypeError: 'FieldInfo' object is not iterable` from the tests
that iterate those constants. Unwrapped by AST rather than by regex, because the multi-line forms are
invisible to a line-oriented pattern.

**The entry said 402 fields and the tree holds 414.** It was written before 0.7's own additions
landed, which is the ordinary fate of a counted number in prose (`@counted-prose-needs-a-fixed-field`)
— and the reason the test asserts a floor on the *total* while asserting equality on the *coverage*.

### Repairs rejected, kept from the entry

Reading `release_records`' `parquet_schema` axis names **4 of 402** authored columns, because it records
what a release changed about compiled output; `curator` happens to be there, which is what makes it
dangerous — right for the case in hand, silently wrong for 398 others. Rewording the pydantic message
has nothing to word. Loosening `extra="forbid"` removes the guard that catches the typo half. And a
compatibility handshake was explicitly *not* asked for; the reporter corrected their own side.

### What it does not settle

A reader still cannot be told *which* release it is missing without also knowing its own — that pairing
is the consumer's, already shipped in their 0.22.0, and stays theirs. This supplies the half nobody
outside this repo can compute.

## RM117 — the vindication signal shipped, and it replaced a message that read as an accusation

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`).
**Severity** medium · **Owner** enricher when filed, compiler as built · **Motivating case**
[S52](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What the item was by the time it was built

Two halves settled before this one. `ProvenanceItem.outranks` — `{column: why}`, per column, additive
— landed 2026-08-20 so an author overriding a checked value has somewhere to record why. The
**severity** half was closed on 2026-08-21, not deferred: putting a checked verdict under authored
control is something nothing else in this format does. What remained was the observability half: two
signals a check can compute because it runs on every compile and needs nobody's permission.

**Recast onto the overlay rather than `outranks`.** The entry proposed both signals over
`provenance.json`, and by 2026-08-28 that was the wrong file: RM135 settled the overlap as a dated
succession, `outranks` is filed for removal at the major, and `concordance.py` already names the
overlay as where an answer goes. Growing observability on a field queued for deletion is what RM135
warns against, so the signals compute from `overrides.csv`, where the surviving mechanism is.

### The signal was already firing, with the wrong words on it

This is the part worth keeping. `clin_sig_concordance.csv` holds **contested subjects only** and is
**rewritten whole**, and `concordance.py` states outright that a subject leaving the record is how an
author learns the archive caught up with them. So the state RM117 wanted to observe — *the archive
resolved a conflict the author had answered* — already produced an observable: the overlay row reaches
nothing.

What it produced was the generic finding, offering *the subject may be mistyped, or the correction may
be aimed at a row the compiler drops* — put to an author in the one case where their judgement had just
been confirmed. **So the work was not adding a signal; it was stopping a wrong one**, which is why this
earns a code (`overlay_answer_vindicated`) rather than a rewording, and why the test asserts the
misleading line is **gone** as well as that the good one appears.

### It is an observation, not a verdict, and the wording is pinned

The authorities agreed and the overlay row is now unnecessary. Whether the author was right about the
biology is not something a compiler can say. The test greps the message for adjudicating words on a
**word boundary**, and it caught a real one: the first wording said *the conflict ended rather than
that the correction is wrong*, which grades the author's row while claiming not to. The published
sentence says the disagreement ended and the row can be retired.

### The second signal was filed rather than built, and shipped the same day

*A record whose row's value has changed again* needs the archive's value **now** against its value at
record time, so it needs a fetch — enricher work, with the offline/no-snapshot/nobody-asked ladder
every network check here carries. It is **RM151**, and it turned out more tractable than this entry
assumed: `clin_sig_authority_calls.csv` records each authority's call, its verbatim wording and its
release, so the baseline exists — for the concordance pair alone, which is the scope RM151 states. It
is below, shipped inside the same uncut 0.7.0.

### Scope

One table, because one table's absence has a single reading. Every other overridable table's unmatched
update is ambiguous and takes RM137's split; `VINDICATING_OVERLAY_TABLE` names the exception, and the
routing is a `continue` rather than a reachability predicate, since the generic classifier's two
readings are exactly what must not be printed here.

## RM151 — the second vindication signal, and the baseline is the file the same run overwrites

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`). **Severity** low-medium ·
**Owner** enricher · **Motivating case** [S52](CONSUMER_SUGGESTIONS_HISTORY.md)
(just-module-creator), RM117's second signal

RM117 shipped the signal that a subject has **left** the concordance record. This is the other one: an
`overrides.csv` row answering a contested subject is a judgement written *about a particular
disagreement* — the archive said X, the author says Y, and `reason` explains why — and if the archive
later says Z, that reason was written about a value that is no longer there. Nothing distinguished a
justification that still describes the disagreement on file from one that describes a disagreement
since replaced by a different one.

### The baseline exists, and it is exactly one file

RM117 said a record "is not bound to the value it justifies", and for the concordance pair that is no
longer quite true. `clin_sig_authority_calls.csv` records what each authority actually said —
`clin_sig`, the verbatim `clin_sig_raw`, and the `dataset` release it came from, keyed
`(variant_key, genotype, authority)` — so recorded-call against fresh-call is available here and
nowhere else in this format.

**Scoped to that table, and the finding says so in its own text** (`@probe-names-the-table`). An
overlay row against `frequencies.csv` or `resolution.csv` has no recorded prior value at all, so a
general *the value moved* check would be answerable for one table and silently absent for every other
— an unscoped negative becoming a permanent false constraint.

### The ordering is the feature, and it is guarded where a refactor would break it

`write_concordance_tables` replaces the record whole, so the previous run's rows exist only until this
run commits. The comparison is therefore computed in the staging phase, above the commit — which
`enrich()` already does for every product of a run, for the unrelated reason that a refused `strict`
run must change nothing. No assertion over a return value can see statement order, so the test walks
the AST and asserts the read's line precedes the write's, in the same enclosing function. The guard
was demonstrated to fail on a source copy with the two swapped before it was kept.

### A move is observable exactly once, and that is the honest shape

The run that notices also rewrites the baseline; the next run compares against the new one and is
silent. Persisting it needs the overlay row **bound** to the value it justifies — a column on
`overrides.csv` recording what the answer was written against — and that is a schema change to the
authored surface, a minor rather than a patch, and precisely the binding RM117's three objections all
turned on missing. **None of those objections is an objection to noticing that the value moved**, which
is why this ships as an observation and the binding stays unbuilt. Decided per item with the maintainer.

### Three states, and the third is the whole point

Unchanged is `recorded` on both sides with the same classification, `dataset` moved or not: a
re-released archive saying the same thing has not moved the disagreement. A **shift** is a changed
classification, or `recorded → no_record` and back — asked both times, and the answer differs.
Everything else is **withheld**, `no_prior_record` or `unchecked_now`, and reported as an info note.
Neither withheld state ever reads as *nothing moved*: telling an author their reasoning still stands on
evidence nobody looked at is the one way this check does real harm, and it is what the tests spend
their weight on.

**A move this tier's own normalizer made is reported apart from the archive's.** Same verbatim
`clin_sig_raw`, different normalized member, means `clin_sig.py` changed rather than ClinVar — a fact
about our code with nothing for an author to do. Folding it in would accuse a source of a change we
made.

### What counts as an answer, and why it is the opposite rule from RM136's

**Any overlay row naming the subject** — every operation, every field. What goes stale is the `reason`,
which the model makes mandatory on every row whatever the row does, so a per-field rule would have to
name a column the reason does not live in. RM136's `overlay_answers` is per field for the opposite
direction: it decides whether a finding may be **silenced**, and anything looser silences findings the
author never looked at. A finding raised too widely costs a reader one line; one silenced too widely
costs them the finding. `licensing.overlay_answered_subjects` is the second reader, beside rather than
inside the first.

### The boundary with RM117, and the wording

A subject that has left the record entirely never enters this comparison: that is
`overlay_answer_vindicated`, reported by the compiler as good news, and hanging a second and gloomier
finding on the same overlay row is exactly the *already firing with the wrong words* failure RM117 was.
The messages are pinned by a word-boundary grep refusing `correct`, `wrong`, `mistaken`, `vindicated`,
`confirmed` and their siblings — *the disagreement you answered is not the one on record now* is a
statement about the record, and *your answer may be wrong* is a verdict this check cannot see the
reasoning for.

**Warning-tier in both modes, escalating in neither** (`@clinsig-never-escalates`), with more force
than the record itself: gating on it would make an artifact refuse over an archive's release schedule.

## RM138 — closed: the duplication costs 1.84× raw and 1.06× compressed, and the encoding stands

**Closed on 2026-08-31 with no code change**, inside the uncut 0.7.0. **Severity** low · **Owner**
format (schema) + compiler · **Found by** reviewing RM131 against its own motivation

**Not a defect, and the entry said so first.** The shape was decided per item with the maintainer — a
`carried` list beside `warnings`, holding the subset the author cannot clear — over a field on each
finding, because it invents no permanent names and a consumer subtracts to get the actionable set.
Both properties hold. What the decision did not have in front of it was the size, and the size is the
thing RM131 exists about.

### The number that was missing, measured rather than argued

The entry measured the raw cost at **1.84×** across the corpus. The question it left open was whether a
published manifest should pay that. Re-measured on 2026-08-31 with the compression a real transport
uses, over every reference example that emits a warning:

| module | warnings | carried | raw | gzip |
|---|---|---|---|---|
| `pathogenic_clinvar` | 113 | 109 | 1.96× | **1.13×** |
| `hboc_palb2` | 12 | 12 | 2.00× | **1.07×** |
| `shox_par1` / `apoe_epsilon` | 2 | 2 | 2.00× | 1.05× / 1.07× |
| `htt_repeat_expansion` | 3 | 1 | 1.33× | 1.02× |
| **corpus** | | | **1.84×** | **1.06×** |

The raw column reproduces the entry's figure exactly, which is what makes the second column
trustworthy. **`carried` is a verbatim subset of `warnings`, which is precisely the input DEFLATE's
back-references are for**, so the duplication that doubles the bytes on the wire uncompressed adds
**6%** compressed — and the whole with-`carried` payload gzips to **0.21×** the *uncompressed*
warnings-only one. The worst case in the corpus, the 113-warning module the item was filed about, pays
13%.

### The decision

**Keep the encoding, and recommend compression where the size matters** — a catalog serving many
manifests, an API response, anything shipping `manifest.json` over a wire. That is a deployment
concern rather than a schema one, and it is where the cost actually lands.

The three cheaper encodings the entry weighed stay rejected, unchanged, and their reasons are now
cheaper to accept because the thing they were buying is worth ~6%:

* **`carried: list[int]`, indices into `warnings`.** Breaks the one property the field was chosen for
   — the subtraction becomes a zip, and an index means nothing to a consumer that filtered or
   re-ordered the channel. It also positionally couples two published fields, which
   `manifest.compilation.warnings` has always avoided.
* **`carried: list[str]` of codes.** Answers a different question, and one already answered:
   carried-ness is a property of the code alone, so `warnings_summary` plus `CARRIED_WARNING_CODES`
   gives the count without this field at all.
* **Drop `carried`, publish a per-message `codes: list[str]`.** The genuinely minimal encoding, and
   still a **third** shape rather than the decided one — it re-introduces the positional coupling and
   hands every consumer a derivation where they currently read an answer.

**Closing it now rather than leaving it open is the point.** A fourth encoding after 1.0 is a removal,
and removals are major-only under Principle 3, so this had to be settled inside 0.7 either way. It is
settled with a number rather than by drift.

## RM136 — the enricher reads the author's overlay, so a correction stops coming back forever

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler` — one loader made public —
plus `just-dna-enricher`). **Severity** medium · **Owner** enricher · **Found by** the wave-1 audit of
RM124, 2026-08-28

### The asymmetry

The compiler applies `overrides.csv` before any check reads a row, which is the whole point: a check
must report on what the module asserts. The enricher did not — its passes re-read the raw derived file
— so an author who corrected a `resolution.csv` cell through the overlay went on being told the same
finding on every subsequent run, forever, with no way to clear it and no indication that the
correction had been recorded and honoured one tier over. `INTEGRATION_0_6` states the asymmetry for
*consumers*; it was never stated for the **author**, who meets it first and has no parquet to read at
the point they are curating.

### The decision, and the line it draws

**Read-only, at INPUT reads, per field.** Three separable choices, and each has a refused alternative:

* **Read-only.** The enricher never *writes* through the overlay: an overlay row is the author's
  answer to a difference, never the tier's (RM83's standing refusal).
* **Input reads only, never merge baselines.** A pass that reads its own output file to merge against
  it writes that file back, so feeding it post-overlay rows would bake the correction into the derived
  table. The three input sites — `frequencies`, `assertions`, and `identifiers`' gene-locus check —
  read `resolution.csv` as an input to something else and take the overlay; every merge baseline stays
  raw. Same rule the sidecar gotchas already state from the other side: read the file you write.
* **Per field, not per row.** A finding is answered when the overlay `update`s the very cell the
  finding is about, so correcting a coordinate silences the coordinate check and leaves an unrelated
  `clin_sig` finding standing. Per row was cheaper and was refused: an author correcting one cell would
  silence findings they never looked at, which is the silent-suppress hole the overlay's design calls
  its worst case.

**No second implementation of `apply_overrides`** — the entry's central refusal, on the grounds that
two copies would drift on exactly the normalization seam that produced a silent P7 break in this
feature's first week. `compiler.load_overlay` became public (the S74 shape: a private symbol the
enricher would otherwise reach into) and `licensing.overlaid_input_rows` calls *the* `apply_overrides`.
A test compares the helper's output against `apply_overrides` directly, so a future copy would be seen.

### Answered is not agreed, and that is what keeps it honest

An answered pair **leaves `disagreements` and stays in `subjects`**, with `PairCheck.answered`
counting it and one INFO line saying so. The comparison ran and found a difference; dropping it from
the denominator would report a cleaner module than there is, which is the silent-success shape this
codebase keeps closing. What changes is only that the difference reads as *settled by the author*
rather than as work owed — and the author finally gets the acknowledgement that was missing.

### What it does not reach, stated rather than left to be discovered

One check consults the answered set today: the rsid↔coordinate comparison, which is the finding an
`overrides.csv` row on `resolution.csv` can actually answer. The mechanism is general — `overlay_answers`
takes a table name — but a check is wired to it deliberately rather than in bulk, because "which cells
does this comparison read" is a per-check fact and guessing it wrong silences a finding nobody
answered. `_COORDINATE_FIELDS` is that fact written down for the first one.

## RM137 — the unmatched-overlay warning is now a property of the module, not of the lap

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`).
**Severity** low-medium · **Owner** compiler · **Found by** the wave-1 audit of RM124, 2026-08-28,
reproduced end to end

### The defect

`reverse_module` rebuilds a derived table from the artifact, and two of the eight overridable tables
are rebuilt from something narrower than the file the compiler read: `literature.csv` loses its uncited
rows before the parquet and is rebuilt *from* that parquet, and `resolution.csv` has no parquet at all
and is rebuilt from the SNP core, which re-emits only positioned rows. An `update` naming such a row
matched on lap 1 and warned on lap 2, so a module and its own `compile → reverse → compile` disagreed
on `manifest.compilation.warnings` — a published field, and one RM126 had made load-bearing.

### What "count it over the overlay's own rows" means in code

The decision was to report the finding the way `suppress` reports its own — over the overlay rather
than over what it reached. Turning that into code needed one step the entry did not have:

* counting the overlay's `update` rows outright is a **tautology** that fires on every healthy module
  (`@tautology-zero`);
* counting the ones that reached nothing is the **lap-dependent original**.

The stable quantity is neither. It is a property of the **target**: *could an artifact of this module
carry that row at all?* For `literature.csv` that is "is the PMID cited", and for `resolution.csv` it
is "can the module place that `variant_key`" — both computable from data that survives the round trip,
so both answer the same on lap 1 and lap 2 whether or not the row is there to be matched.

**The unreachable finding therefore fires matched-or-not, and that asymmetry is the whole fix.** An
earlier cut of this classified only the *unmatched* set and was silently lap-dependent all over again:
on lap 1 the uncited row is present and the update matches, so nothing was reported. Caught by
asserting **equality between the two laps** rather than "lap 2 warns", which would have passed on the
broken code.

### Two readings, and neither of them is "a typo"

That framing was the original entry's and it is wrong. A mistyped PMID is also an uncited one and a
mistyped `variant_key` is also an unpositioned one, so a mistake lands in the *unreachable* bucket.
What the reachable bucket really means is narrower and more useful:

* **`overlay_update_unmatched`** (reworded) — the subject *is* cited or positioned, so the artifact
  could carry the row and the sidecar simply does not have it. Re-run the enrichment pass.
* **`overlay_update_target_unreachable`** (new, actionable) — no artifact of this module can carry the
  row. Two readings, named rather than collapsed: the subject may be mistyped, or the correction may
  be aimed at a row the compiler drops and be perfectly fine.

### Scope, and why it is not a dodge

Only `literature.csv` and `resolution.csv` — `LOSSY_OVERLAY_TABLES`, asserted as an equality over the
walked registry. The other six rebuild whole on a reverse, so an `update` reaching nothing there is
unmatched on **both** laps already and needs none of this. The predicate is defined only where the
loss is, and a table added to `OVERRIDABLE_TABLES` has to face the question deliberately.

### Two traps the build hit

**The predicate must share the drop's own function, not restate it.** `cited_pmids` was extracted out
of `split_cited_literature` so both ask one question; two statements would drift, and in the worst
direction — the predicate would call a row unreachable that the drop had kept, and a healthy overlay
would report a finding forever.

**And it must mirror the drop's empty-cited guard.** `split_cited_literature` discards *nothing* when
the module cites nothing at all, on the stated grounds that such a module cannot distinguish a stale
sidecar from citations not yet authored. Without the mirror, every literature `update` on such a module
reads as unreachable — a **stable false positive**, which is worse than the unstable true one.

### Where the classification happens, and why it moved

Not at apply time. `apply_overrides` runs before any check reads a row, and the question needs
`studies.csv` and the citing tables, which `validate_spec` and `compile_module` both load later. So
`apply_overrides` gained `defer_unmatched=True` (additive, default off), the unmatched set is stashed
from the **pre-overlay** rows — apply rebinds its input, and an `insert` earlier in the same overlay
would otherwise make a later update look matched — and one shared helper splits it late in both
functions, so the two cannot classify differently (`@parity-by-check`). Hoisting the `studies.csv`
load instead was refused: pre-flight warnings seed the compile's list, so reordering the load reorders
a published field for no gain.

## RM150 — `unknown` was carrying an absence and a finding, and `contested` takes the second

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`). **Severity** low-medium ·
**Owner** format (schema) · **Motivating case** [S83](CONSUMER_SUGGESTIONS_HISTORY.md)
(just-module-creator), the residue RM148 did not take · **Taken into 0.7 by the maintainer** on the
grounds that there was no sense postponing it — it was filed to `ROADMAP_0_8.md` earlier the same day
and moved here without its shape changing.

### The shade RM148 left

The reporter said `direction`'s `unknown` covers three things: *no evidence*, *conflicting evidence*,
and *evidence that does not exclude either direction*. RM148 removed the third by **reassignment** —
an unestablished sign is still a sign, so that state is the pair `direction=<sign>` +
`stat_significance=not_significant`, and a member for it would have been a second spelling. That
reasoning holds and is not reopened.

It does not reach the first two, and RM148's own field description said so out loud — *"not assessed,
or the sources conflict"* — while adding nothing that told a consumer which. **They are not one thing:
one is an absence and the other is a finding.** The reply to S83 asserted the two were "one thing
(nothing to record)", and that was our assertion rather than the reporter's concession.

### The decision, and why the member is earned here where it was refused there

`contested` is added and **`unknown` keeps its original meaning**. Both halves are load-bearing.
Re-pointing a shipped member at the narrower sense would silently change what every published module
already says by it — a retype in everything but name, and Principle 3 territory; adding beside it is
minor-legal. The name is the workspace's own word for the same idea one table over
(`clin_sig_concordance.csv` is one row per *contested* subject, and `clin_sig_concordance_contested`
is an existing warning code), so coining a synonym would be the drift
`@one-normalizer-two-spellings` records.

The cost that made RM148 refuse a member — a wire vocabulary gains one — is paid here because this
shade is genuinely **not expressible as a pair**: no combination of `direction` and
`stat_significance` says *two sources disagree about the sign*.

### The trap, and it is why the map was the first edit rather than a follow-up

`trimmed_state()` projects a `direction` back into the legacy `state` set through
`_DIRECTION_TO_STATE.get(direction, "neutral")` — **a `.get` with a default, not a lookup that
raises**. Measured before anything was changed: `trimmed_state("contested")` already returned
`"neutral"`, and so does `trimmed_state("a string that is not a direction")`. So adding `contested` to
`VALID_DIRECTIONS` and stopping there ships a module whose `upgraded()` silently emits the wrong
legacy `state`, with nothing failing anywhere.

The map entry therefore went in first, and the guard is a **registry-iterating equality** —
`set(_DIRECTION_TO_STATE) == VALID_DIRECTIONS`, walked. A test asserting
`trimmed_state("contested") == "neutral"` would have passed against the unfixed code and measured
nothing; the assertion has to be about the map's *coverage*, not its output, and the test says so with
the demonstration beside it. `contested → neutral` is the right projection once it is **explicit**:
the legacy set has no member for it, and `neutral` is where `unknown` already lands.

### What it deliberately did not touch

* **`_STATE_TO_DIRECTION` gains nothing.** The two maps look like they should mirror and do not: no
  legacy `state` value means *the sources disagree about the sign*, so there is nothing to map from. A
  module upgraded off the legacy column can never produce `contested`; only an author writing
  `direction` directly can. Commented at the site, because it invites a "fix".
* **`stat_significance` gains nothing.** Two sources disagreeing about the *sign* is not two sources
  disagreeing about the *strength*, so the two vocabularies' intersection is still exactly `unknown` —
  asserted, so a later member has to face the question deliberately.
* **Nothing re-points, so nothing drifts.** `upgraded()` stays idempotent and `needs_upgrade` does not
  start reporting existing `unknown` rows, which is the half that makes this an addition rather than a
  retype.

## RM155 — the identifier roster read one table while eleven carry the column

**Severity** medium · **Status** ✅ shipped 2026-09-01 in the uncut 0.7.0 (`just-dna-enricher`) ·
**Owner** enricher · **Motivating case** S86 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

`check_identifiers` built its trait and gene rosters from `variants.csv` alone. Walking `_ALL_MODELS`,
**eleven** authored models declare `trait_efo_id` or `gene` — `StudyRow` has carried the trait column
since 0.3 — so a 67-variant module carrying the id on all 68 `studies.csv` rows reported nothing
checked and nothing flagged, and could ship a retired or simply wrong CURIE with every gate green.
Reproduced offline in both directions before anything moved.

**The unreadable `0` is the item; the missing table is only how it got there.** `traits checked: 0`
asserted *this module declares no trait* and *its traits are in a table nobody read* in one breath —
`@unreachable-not-absent` at a finer grain, a question never put rendered as an answer. Widening the
roster alone would have left that hole, because a wide roster still returns `[]` for a module that
genuinely declares none. So the fix is both halves, which is what the reporter proposed as an
either/or and is really an and: `IdentifierReport` gained `trait_tables_read` /
`trait_tables_not_read` and the gene pair beside them, and the CLI count names its own denominator.

**The roster is derived from `DRAFTABLE`, never listed.** A hand-kept set would be the same defect with
a longer literal in it, so the test asserts an **equality over the walked `_ALL_MODELS`**
(`@registry-completeness`) and a table kind added later joins by existing. Nine tables carry
`trait_efo_id`, nine carry `gene`. Two edges the walk settled: `MeasureBinRow` is correctly absent as
the abstract base whose four concrete subclasses are each their own entry — pinned rather than assumed
— and the three **derived** models carrying these columns (`GeneMetricsRow`, `GeneValidityRow`,
`GwasEffectRow`) are outside the roster on purpose, since a stale id in a machine-written row is the
*source's* currency and no author can act on it. Widening to them would report findings against rows
nobody wrote, and `dataset_currency` is the surface that asks that question.

**A third instance, one level up, found by the same framing.** `report.clean` is `all()` over a set
that can be empty, so `check-identifiers` printed a green *"all identifiers current"* having asked
nothing at all. It now says what it read. Worth the general form: a predicate that is `all()` over a
possibly-empty set reports a pass it did not earn.

An absent optional table and one that exists and will not parse are kept apart — the first is every
module's normal shape, the second means ids the module carries went unchecked, and only the second
warns. The narrow roster survives for a caller passing `variants=`, which is all rows-in-hand can
serve, and that caller is told so in `*_tables_not_read` rather than left indistinguishable from the
wide case.

**No schema change**: no column, no vocabulary member, no signature moves. `IdentifierReport` is a
report object rather than a published row, and the added fields default to empty, so an existing
caller reads unchanged.

## RM154 — an answered lookup whose alleles were rejected was published as an absence

**Severity** medium · **Status** ✅ shipped 2026-08-31 in the uncut 0.7.0 (`just-dna-format` +
`just-dna-compiler` + `just-dna-enricher`) · **Owner** enricher · **Motivating case** S85
(just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

A 64-variant longevity module authored from a paper whose supplementary is GRCh37/hg19 left five
subjects unresolved, each written into `resolution.csv` as `status: not_found`, `source: ensembl`.
Ensembl has all five and returns them immediately. What failed was allele matching: the paper spells
the submitted strand, so its `G/A` meets GRCh38's `C/T` and the allele-aware filter rejects every
locus, emptying `loci` and dropping the row through to the `not_found` arm.

**Two states of the world, byte-identical rows.** Reproduced offline against the real `enrich` path: a
snapshot that *has* the rsID with complemented alleles and one that genuinely lacks it produce the same
`(rsid, status, chrom, start)`. That is the collapse RM98 repaired one branch over — the reporter cited
its comments back at us — arriving from a third direction: `unreachable_rsids` means the request failed,
`unconsulted_rsids` that nobody looked, and this one that the asking **succeeded** and the answer did
not match. The consumer's own framing is the item: `not_found` sends an author to *does this rsID exist*,
a question with an obvious answer that is not the problem.

**Both obvious repairs are worse, and the second is worse in a way that had to be measured.** A new
`VALID_RESOLUTION_STATUS` member changes a wire vocabulary every reader of a published `resolution.csv`
shares — the reporter argued this themselves. *Deleting* the row looks more honest and is not:
`variant_key` and `rsid` are `RESOLUTION_FACT_FIELDS` while `status` is provenance and is not, so
removing the row **moves `resolution_signature`** and changing its status is free. Checked with the real
function rather than reasoned from the field list. The row was never the untruth — it is honestly
unresolved either way — so what moved is the reason, not the row.

**Shipped:** `EnrichmentResult.allele_mismatches`, carrying
`AlleleMismatch(rsid, genotype, loci, offered, strand_flip)` — the shape `ref_mismatches` and
`stale_rsids` already have, which is the option the reporter proposed. One aggregated run warning in both
modes, naming the rsIDs and saying the source *has* them, because an author who greps the artifact for
`not_found` is exactly who this exists to contradict.

**A second defect the report did not file, found in the sentence it quoted.** `hosting_verdict` returns
a confident `False` from two arms — a substitution/MNV locus (no flank, so no spelling freedom) and an
event length the locus does not offer — and the warning gave the second arm's reason for both. So a
strand-flipped SNV was reported as *"The event sizes differ, which re-anchoring cannot change"* about two
1 bp substitutions: a false claim, and the one that cost the run its largest diagnosis detour.
`contradiction_reason` is now `undecided_reason`'s twin on the `False` side (five causes there, two
here), walked by a test asserting the arms' reasons are pairwise distinct — the failure mode is a third
arm silently inheriting a second's sentence, which raises nothing and reads as a diagnosis.

`strand_flip_explains` and `reverse_complement` landed in **format**, not the enricher: they are pure
string work over the four bases with no reference access, the compiler's twin reporting site needs them,
and digest parity between the two resolution paths is a documented guarantee. `reverse_complement`
withholds on anything that is not four bases — a degenerate code states an uncertainty, and complementing
it would assert a base the source declined to name. `strand_flip_explains` tests `called <= locus` first,
because a palindromic SNV (`A/T` at `T>A`) satisfies both readings and would otherwise be reported as a
flip when it needed no explaining at all.

**No artifact changes**: no column, no vocabulary member, no signature moves, and every existing module
recompiles byte-identically. The `not_found` rows stay exactly where they were, which is what the
reporter concluded too — nothing in their data needed editing beyond the five genotypes' strand.

## RM108 — a re-curation is recognised, and currency is DERIVED rather than marked

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler` +
`just-dna-enricher`). **Severity** medium · **Owner** enricher, and the derivation landed in format ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_validity.md`)

### The finding

`_merge_key` returns `("id", row.assertion_id)` when the source published one — the right rule in
general, and wrong here, because ClinGen's assertion id **embeds the curation timestamp**
(`CGGV:assertion_…-2019-08-18T160312.829Z`). A re-curated assertion arrives under a different id,
misses the merge key, and is appended beside the old one. `manifest.gene_validity.classifications`
then published a pair as far apart as `["definitive", "refuted"]`, with `classification_date` and
`dataset` the only discriminators and no consumer reading either.

### The decision that survived contact with the code, and the one that did not

**Survived:** the newest `classification_date` is current, and nothing is deleted. That is S45's
answer carried over to a weaker signal, and taking it means accepting one thing this format had not
accepted before — that a date is authoritative for currency. The concession is narrower than it looks.
The date decides *ordering* and nothing else: it never says a classification is right, both rows stay
in the file so the drift stays visible, and a consumer wanting the answer no longer has to reconstruct
one.

**Did not survive: the marker column.** The entry said the superseded marking "needs a column, which
is additive and minor-legal". Legal it is; workable it is not, and the reason only shows up when you
try to write it. **The row that must be marked is the one already in the file**, and merge-not-clobber
forbids this pass editing it (`@sidecar-authoritative`). So the marker would be correct on every run
*except the one that created the ambiguity* — the run that appends the new curation is exactly the run
that cannot go back and mark the old one. A boolean fails that way and a `superseded_by` pointer fails
that way too, plus three of its own: GenCC rows may carry no `assertion_id` to point at, a row
superseded twice needs a rule about immediate-versus-current successor, and a pointer *locates* rather
than asserts, which is the line `GENE_VALIDITY_FACT_FIELDS` already draws to keep `report_url` outside.

**So nothing is stored.** Currency is a total function of the rows present, so it is derived at every
read (`@derived-not-stored`): `classify_currency` in the format tier, called by the enricher to report
and by the compiler to warn and to build the manifest block. One consequence worth stating plainly —
**no column changed, so `gene_validity.signature` does not move and no existing module recompiles to
different bytes.** The reported harm was in the manifest, and the manifest is where it is fixed.

### The grouping, and its one difference from the merge key

`(gene, disease_id, moi, submitter)` — the source's grain **without `dataset`**. A re-curation is by
definition a later *release* of the same claim, so including `dataset` would put the two rows in
different groups and answer "nothing was superseded" every time. Computed **beside** `_merge_key` and
never inside it: the merge must keep both rows, because the drift staying visible is the property the
item exists to preserve.

### Two edges, and both withhold

Neither was in the original entry, and both are decisions rather than defaults:

* a **tie** on `classification_date` — two curations stamped the same instant, and nothing says which
  came second;
* **any row in the group carrying no date** — including the dated siblings, because being the newest
  of the rows that *stated* a date is not the same as being the newest.

In both cases no row is current and none superseded, and the manifest publishes every classification
in the group. Breaking a tie on `assertion_id` was rejected: an identifier carries no chronology, and
sorting on one manufactures a winner out of a spelling. A group of **one** is current, dated or not —
there is nothing to order it against, and that is what keeps the finding quiet on an ordinary module.

### Severity: a warning in both modes, in both tiers

The enricher **never raises**, in `best_effort` or `strict` — a curating body re-curating is the source
working, not the module being wrong. That is the pass's own argument for `missing` (*"`strict` is a
report, not a refusal to have looked"*) and the stronger form of it: the only edit available to an
author is deleting a row, which falsifies the record rather than repairing it. It is a deliberate
departure from `@enrichment-is-validation`'s mode ladder, and the second such check.

The compiler warns in both modes and never escalates, on the rule `_vrs_coverage_warnings` and
`frequencies`' `not_covered` already follow — **a finding no authored edit could clear is not a
`strict` matter** — and both codes are in `CARRIED_WARNING_CODES` for the same reason.
`validate_spec` reports the same two findings, since this is pure computation over injected bytes
(`@parity-by-check`).

### What the build turned up on the way

**The first fact-table check to run on both sides, so it was the first to double.** `compile_module`
runs `validate_spec` as its pre-flight, both reached the identical sentence, and
`manifest.compilation.warnings` carried it twice — which doubled `warnings_summary`'s count with it,
the case `@no-rerun-with-counts` is about. The fact-handler loop now dedupes on the message like every
other both-sides check (RM94's idiom); both passes read the same *post-overlay* rows, so the counts
agree and the rule is satisfied rather than dodged.

**`manifest.gene_validity.superseded_count` is new, and it is gated on the round trip.**
`gene_validity.csv` is rebuilt whole from its parquet — no row drops, unlike `literature.csv` — so the
row set is identical on lap 2 and the derivation over it is too. Asserted rather than assumed, because
a published field that differs between a module and its own round trip is precisely RM137.

**The merge test could not see this defect and is part of the fix, not the thing that confirms it.**
`test_a_rerun_merges_rather_than_duplicating` feeds the same bytes twice, and the same bytes carry the
same ids, so the key matches and nothing is appended however wrong the key is. The new fixture is two
*different* exports of one claim, which is what the real source produces.

## RM103 — the manifest now records the version that was READ, not only the one that was invented

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`; the
manifest half of the split item — the refusal half stays on the 1.0 tracker). **Severity** low-medium
· **Owner** format · **Motivating case** S42 (just-dna-lite, in CONSUMER_SUGGESTIONS_HISTORY.md)

### What shipped, and what deliberately did not

`Identity.version_coerced_from` — the authored `module.version` when the model rewrote it, `None`
when it was already canonical SemVer. `'v2'` beside `'2.0.0'`, `'abc'` beside `'0.0.0'`. Additive,
out of `artifact.digest`, declared in `RELEASE_RECORDS` on the `manifest_fields` axis.

**The coercion is untouched and must stay untouched.** RM17 decided coerce-rather-than-reject because
the pre-0.4 corpus is full of `v2` and `3`, and 0.6 widened it at `mode="before"` after **26 of 61**
foreign modules refused on an unquoted integer. Every digit-bearing case still behaves exactly as it
did, and the test parametrizes all of them precisely so a later change cannot quietly undo RM17 while
appearing to be about this item.

**A sentinel stays rejected.** Coercing to something unmistakable has no target: every three-number
string is a legal SemVer and therefore somebody's real release. Publishing what was *read* is the only
repair available, which is exactly why the additive half was worth separating from the refusal.

### The second-order effect that was nearly shipped, in the release that files RM137 about it

`reverse_module` takes `version` from its caller, and the caller has `manifest.identity.version` — the
**coerced** string. Re-emitting that leaves lap 2 with nothing to coerce, so `version_coerced_from`
comes back absent and a module disagrees with its own round trip on a published field. That is RM137's
exact shape, and it would have arrived in the same release.

So reverse re-emits the **pre-coercion** string: `_authored_version_from_artifact` reads the
artifact's own manifest, prefers `version_coerced_from`, falls back to `version`. Both cells then hold
across two laps, which the test asserts rather than assumes — and the failure was demonstrated on the
naive implementation before the test was called a regression net (`abc` → lap 1 `abc`, lap 2 `None`).

**It also repairs a quieter loss nobody had filed.** Reverse emitted no `version:` at all unless a
caller supplied one, so even an ordinary canonical version did not survive a round trip. Nothing
hashed on it — `module.version` is advisory and out of `artifact.digest` — which is why it went
unnoticed. An explicit argument still wins, and a bare parquet directory with no manifest still leaves
the key out: recover it or say nothing, never invent one, the same rule `genome_build` follows.

### What the reporter should do meanwhile, restated because it was already true

Both `compile` and `validate` have always warned, naming the authored string and the coerced result,
so a build that greps its warnings caught this before 0.7. The gap was between the *model* (silent)
and the *pipeline* (loud), and the reporter was testing the model directly. The manifest closes it for
a consumer holding only the artifact, which is the population that could not act at all.

**One correction to their report, in their favour**, kept from the original entry: they noted their own
CLAUDE.md claimed *"an unquoted `1` in YAML loads as an int and is rejected"* and is wrong on 0.6.1 —
`1` coerces to `1.0.0`. Confirmed, and our documents do not carry that claim. The hazard is the
unquoted *decimal*, still refused and deliberately so.

## RM110 — `constraint_flags` had two producers, two encodings, and one of them inside the fact set

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-enricher`).
**Severity** medium · **Owner** enricher, and it moved to format — see below · **Motivating case**
the 2026-08-19 doc audit (just-module-creator's `gene_metrics.md`)

### What was wrong, measured on the published snapshot rather than estimated

The live GraphQL route wrote `"|".join(sorted(flags)) if flags else None`. The snapshot route copied
gnomAD's bulk-TSV cell verbatim, and gnomAD writes a **JSON array literal** there. Re-probed against
`/data/.../gnomad_constraint/data/*.parquet` before any code was touched:

| cell | rows | what a consumer got |
|---|---|---|
| `[]` | 17,403 | `if row.constraint_flags:` → **true**, for an unflagged gene |
| a real array literal (`["outlier_mis","outlier_syn"]`, 14 distinct shapes) | 708 | splitting on `\|` → **one bogus token**, never two flags |
| null or empty | **0** | — |

So `if row.constraint_flags:` was true for **18,111 of 18,111 rows — 100%**, where the true flagged
fraction is **3.9%**. The field description (*"kept verbatim and pipe-joined"*) was false on the
snapshot leg in both directions, and `constraint_flags` is inside `GENE_METRICS_FACT_FIELDS`, so the
same gene fetched two ways minted two `gene_metrics.signature` values.

### The decision, and the one thing it changed on contact with the code

Pipe-joined when non-empty, `None` when empty, on both legs — never in doubt:
`enricher/tests/test_gnomad.py` had pinned `constraint_flags is None` on the live producer since 0.5,
so the contract existed, was tested, and the snapshot producer had simply never implemented it. **The
item was filed as needing a decision when what it needed was a release.**

What the entry did not anticipate is *where* the normalizer belongs. It said the normalization "goes
in the cell" rather than in a public accessor, and that argument, followed properly, puts it on the
**model** — `just_dna_format.gene_metrics.normalize_constraint_flags`, bound as a `mode="before"`
validator on the field. `mode="before"` because neither producer hands over the `str | None` the field
declares (a Python `list` from the API, an array literal from the TSV), and a `mode="after"` validator
cannot rescue a value the field's type rejects first (`@yaml-version-int`).

**Putting it in the fetching tier would have fixed the wrong half.** The published v4.1 snapshot is
immutable, and every `gene_metrics.csv` already written from it — including this repo's own
`reference_examples/hboc_palb2/` — carries `[]` on disk. A producer-side fix makes new tables agree
with each other and leaves those still contradicting the column's description and still hashing apart
from a live fetch. On the model, one function reaches every producer there will ever be, a
hand-written table, and a re-read of a file some earlier release wrote.

Three call sites nonetheless, and each earns its place: the live route (so the payload is normal
before it becomes a row), `gene_metrics.lookup_snapshot` (so the **published** snapshot reads
correctly — the leg that matters most), and `constraint_build._gene_record` (so a snapshot built from
here on is clean at source). All three are the same function, so they cannot drift; it is idempotent,
so a rebuilt snapshot passes through unchanged.

### What "empty → null" would have missed

Half the finding. It clears the 17,403 `[]` rows and leaves the 708 flagged ones still unparsed, so a
consumer splitting on `|` still gets one token. The non-empty cells needed **parsing**, which is why
the normalizer takes the cell apart instead of testing it against a null set. A bracketed string that
does not parse is kept verbatim — this normalizes an encoding it recognises and invents no reading for
one it does not, and a cell surviving unchanged stays visible to whoever reads the table.

### Cost, measured

Exactly one row in the corpus: `reference_examples/hboc_palb2/gene_metrics.csv` carried
`constraint_flags=[]`, so its `gene_metrics.signature` and `artifact.digest` move and nothing else in
the sixteen examples does. The checked-in file was corrected in the same commit, so it now holds what
the model stores. Beyond that it is whatever consumers have compiled from the snapshot, which nobody
has counted — which is the entire reason this is a minor with a CHANGELOG line rather than a patch.

### The test that would have caught it

`enricher/tests/test_constraint_flags_normalization.py`, and its shape is the durable part
(`@one-normalizer-two-spellings`): it runs **both producers' raw tokens** through the one function and
names the answer both must reach. A suite over the live leg alone was green throughout — that is
exactly what let this survive a release. The pre-fix behaviour was demonstrated before the tests were
called a regression net: an unflagged gene read as flagged, and a two-flag cell split to one token.

## RM147 — a source read by hand that yields no row had nowhere to go, and the home already existed

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`, documentation only — no
behaviour changed). **Severity** low-medium · **Owner** format · **Motivating case**
[S82](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The question

An agent read five literature services by hand — Crossref, Europe PMC, OpenAlex, PubMed, Unpaywall —
to find and confirm the papers behind two rows, and recorded that as five `licensing.csv` rows at
`layer=literature`. The reporter removed them, correctly, on our own two rules: a literature source's
terms are per **article** and live on `LiteratureRow` (RM46), and a pass that put no row in a table
records no source (S77/RM142). They measured that the rows bought no enforcement — identical verdicts
and warnings with and without them, since literature-layer rows are exempt from the orphan check.

Then they asked the real question: **after removal there is no trace anywhere** that a human went and
looked, and found the second paper the module's whole claim rests on. They offered three readings and
were attached to none.

### The answer: reading (2), and the home is already built

Their reading (2) was *"it belongs in `logs/`, and nothing writes it"*. Close, and the file is
`literature.csv` rather than a log. A row no study, bin or pharm row cites is **kept in the CSV and
dropped from the artifact** with `literature_row_uncited` — shipped since RM79 for the case of a
citation the author deleted, and the same shape answers the opposite case exactly: a paper that was
read and did not become a row.

That gives the consultation the three properties the report wanted and a log would not have. It is
**structured** — a `pmid`, a `doi`, an `exists` verdict, checked by the same pass that checks a cited
one. It **cannot make a licence claim**, which is what made the original rows wrong. And it is
**about the paper**, which is the thing that was actually consulted; a service is only how the author
reached it, and it is the paper that carries terms.

The compiler dropping the row from the artifact is right rather than a loss: nothing in the module
joins to it, and the CSV is where the author's own record lives.

### Documented rather than built, and that is the whole change

Nothing in the code moved. `LiteratureRow`'s docstring now says the uncited row is this case's home
and why the licensing table is not, and a test authors the reported shape end to end: two articles,
one cited and one not, a green `--strict` compile, `literature_row_uncited` naming the unused one, and
**no `licensing.csv` at all** — because nothing is owed for reading an abstract.

### The readings not taken

- **(1), "it should not be recorded."** Their straight application of S77, and the near miss. S77 is
  about *obligations*: a source that contributed nothing creates none. It is not a rule that the
  looking is uninteresting — and the looking is a fact about a paper, which this format already has a
  table for. Answering (1) would have made human search effort invisible by a rule that was never
  about visibility.
- **(3), a new `layer` member or a boolean meaning "consulted, contributed nothing".** The reporter
  was least confident in this and named the reason themselves: a row meaning *no obligation*, sitting
  in the obligations table, re-opens the check-that-cannot-fail shape S77 had just closed. Agreed, and
  it is worse than they said — `VALID_SOURCE_LAYERS` is a wire vocabulary, so the member would be
  permanent under P3 for a fact that has a home already.
- **Keeping the rows as they were.** Their own rejected candidate, and their argument is the one to
  keep: a `pubmed,literature` row with blank permission booleans sits one column from a false
  all-clear for text quoted out of a `cc by-nc-nd` paper.
- **A `logs/` writer.** Their (2) read literally. The transport exists, but a log line is unstructured,
  unchecked and unqueryable, and would have made us specify a line format that publishes. The typed
  row is strictly better and needed no new surface.

### Charter check

P3/P8/P9 — a docstring and a test; no field, no vocabulary member, no behaviour, and zero cost on the
authored layer. Measured: nothing in the corpus changes, so the 0.7.0 release record is unaffected.

## RM148 — `direction` and `stat_significance` are one pair, and the description did not say so

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`). **Severity** low-medium ·
**Owner** format · **Motivating case** [S83](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The measurement

Two runs of a byte-identical prompt, same model, same paper, authoring `rs117385980` for a longevity
module. Both green through every gate, and they wrote **different values in `direction`** for the same
variant on the same evidence: `risk`/`suggestive` against `unknown`/`not_significant`.

The evidence: two cohorts trending the same way, p ≈ 0.074 and 0.073, combined OR 3.58 with a 95% CI
of 0.96–13.4 — the interval contains 1 — at 28.4% power. Filed in the same spirit as S80, an hour
after that one was accepted.

### The answer: not a vocabulary gap, and the reason is the orthogonality itself

The reporter's reading (1), which they identified as the cheap one and which is also the correct one.
`direction` records the **sign of the reported estimate**; `stat_significance` records **how far to
lean on it**. They are orthogonal by design — the split RM145 just finished unwinding out of `state` —
and orthogonality is precisely the answer to *is a sign you cannot lean on still a sign*: yes, because
the other column is what says you cannot lean on it.

**The state they wanted a member for already exists as the pair.** `direction=risk` +
`stat_significance=not_significant` is exactly *a real trend the evidence does not establish*, and it
authors and validates today — asserted by a test that constructs their row rather than arguing about
it.

**Writing `unknown` there is the lossy choice**, which is the half the old description left an author
to work out. It discards the sign the paper reports and leaves `stat_significance` making a statement
about nothing. So the description now bounds `unknown`: *no sign to record* — not assessed, or the
sources conflict — **never a sign you may not act on**.

### Why no new member

Their reading (2) — a member meaning *looked, and the evidence does not establish a sign* — is the one
they could most easily imagine and did not push for. It would be a **second spelling of the pair**,
which is Principle 5's overloading arriving as a synonym rather than as a conflation: two ways to say
one thing, with consumers splitting on which they read. It is also a wire vocabulary change touching
every consumer, permanent under P3, for a state that is already expressible.

A test asserts the two vocabularies stay disjoint but for `unknown`, over the walked sets rather than
by naming members, so a future addition to either has to face this deliberately.

### What the fix is

One description string, the RM145 mechanism the reporter explicitly cites — it reaches `describe`,
`requirements`, `reference` and any consumer rendering `model_fields`, and it would have settled their
two runs. Their own interim repair (say which value you chose and why in `conclusion`) stays good
practice for a genuinely contested row; it is no longer the only thing standing between two agents and
a coin flip.

### Charter check

P3/P8 — a description string; no member added or removed, nothing invalidated. P5 — the fix *is* that
principle, stated where an author reads it. Measured: no reference example moves anything.

## RM144 — the licence-disagreement warning printed the remainder as though it were the whole set

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler`). **Severity** medium ·
**Owner** compiler · **Motivating case** [S79](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The defect

`_check_declared_license_agrees` filtered the annotation-layer rows to those whose licence *differs*
from the module's declaration, then rendered that remainder as if it were the whole set. So a
two-source module declaring `CC-BY-NC-ND-4.0` — an exact match for one row, and the binding constraint
on the artifact — printed *declares 'CC-BY-NC-ND-4.0' but annotation-layer sources report
['CC-BY-4.0']*. The row that agrees is invisible in the sentence complaining about agreement.

Reproduced at the function, both ways: the matching-one case and the matching-none case produced
messages of the same shape, differing only in the length of a list. Nothing in the output told the two
apart.

**Two problems with different repairs read identically.** *Your declaration is unsupported* means the
author picked a licence no source grants. *Your declaration is not universal* is the ordinary shape of
a mixed-licence module, where the most restrictive term binds and the declaration is already right. An
author reading the first when the second was true re-adjudicated a module's whole licence position and
found nothing wrong — measured twice, in two separate reported rounds, and it survived RM142's fix
because removing the phantom `CC0-1.0` row leaves a real disagreement still rendered as total.

### What shipped

The reporter's option (1): the count leads and the agreeing rows are named beside the disagreeing ones.
*declares 'CC-BY-NC-ND-4.0' and 1 of 2 annotation-layer source(s) report a different licence:
['CC-BY-4.0']*, with a distinct sentence — *no annotation-layer source reports it* — for the case the
old message was actually written for. The tail names the mixed-licence reading explicitly, so an author
who sees a partial match knows it is a recognised shape rather than an unexplained complaint.

**The denominator counts rows, not distinct licences.** Two sources sharing a licence are two
obligations, and the number the author is checking against is how many sources they have; counting
distinct licences would report "1 of 2" for a three-row file, a number matching nothing in it. Rows with
no licence stay outside the denominator — unknown terms are neither agreement nor disagreement — and so
do non-`annotation` layers, or the count would disagree with the set the warning is about.

`declares license` still leads the sentence: it is the fragment an existing test keys on, and the
non-escalation is unchanged and re-pinned — two claims about a legal position disagreeing is not the
compiler's to arbitrate.

### Repairs rejected

- **Suppressing the warning when any row matches.** The reporter argued this against their own case and
  is right: a module declaring the *least* restrictive of several licences is exactly the one worth
  warning about.
- **Their (2), a bare count, and (3), changing only the verb.** Both remove the false reading and
  neither separates unsupported from not-universal, which is the distinction that cost the work. They
  offered these as cheaper floors; the full form is three lines of code, so the cheaper ones buy
  nothing.
- **An SPDX compatibility matrix.** Unchanged and not reopened: world-knowledge that goes stale, in the
  wrong tier.

### Charter check

P2/P3/P8 — pure text over already-loaded rows; no schema change, no field, no vocabulary member, and no
severity change. `@warning-text-is-api` is the live constraint and the grepped fragment is preserved.
Measured: no reference example moves a digest, signature or warning, so the 0.7.0 release record is
unaffected — the corpus has no mixed-licence module, which is why this survived it.

## RM145 — `state`'s six members were printed as peers, and two of them are retired in our own code

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format`). **Severity** low-medium ·
**Owner** format · **Motivating case** [S80](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The defect, and how it was found

`VariantRow.state` was described as `One of: risk, protective, neutral, significant, alt, ref`. Six
values, no ordering, no standing. `derive.py` calls `alt`/`ref` **the retired descriptors** and maps
both to `direction=unknown`; nothing in the printed string carried that.

A consumer's authoring surface passes our descriptions through verbatim — deliberately, so a vocabulary
change reaches an author without them restating it and drifting — so an agent was offered six equal
choices and picked `alt` for a heterozygote, honestly. **The reporter had to read `derive.py` inside
their own `.venv` to author one cell**, which is the part they said they would fix first, and they are
right: that contract works only while the description carries what an author needs in order to choose.

Their usage measurement recomputed here: across the sixteen reference examples `state` is **377 `risk`
and 4 `neutral`**, with `significant`, `alt` and `ref` used **zero** times.

### What shipped, and why it is three groups rather than the two asked for

The description now reads: *Direction of effect for this genotype. Current: risk, protective, neutral.
Superseded, still valid and still read: `significant` — a significance claim rather than a direction,
write `stat_significance` instead; `alt`/`ref` — genotype descriptors carrying no direction, which
derive to `direction=unknown`.*

The report proposed *current | retired*, with `significant` among the retired. **That would tell an
author `significant` means nothing, when it means something this column is the wrong place for.**
`state` is the Principle 5 anti-pattern the charter names by hand — one field conflating statistical
significance, effect direction and a genotype descriptor — so the split has to be by *which axis a
value was really on*, and `derive.py` is the evidence: `alt`/`ref` map to `unknown` on both axes, while
`significant` maps to `significant` on the significance one and is refined from the weight sign before
falling back.

**Each group names its successor**, because a standing with no destination is a warning nobody can
clear — P3's own test for whether a deprecation belongs in a minor — and all three successors ship.

### Repairs rejected

- **Removing the three.** The reporter did not ask for it and it is major-only regardless: published
  modules carry these values and the read-time `effective_*` aliases derive from them. They cited S69's
  lesson about a deprecation claiming *nothing else is lost*, from the other side.
- **A `RECOMMENDED_STATES` frozenset beside the closed one.** Two lists to keep in step for a fact that
  fits in the string every surface already prints.
- **A compile warning on a superseded value.** Every such module would warn on every build for a value
  that still works and still derives correctly, and the author of a *published* module cannot clear it.
- **Fixing it in the consumer's `describe_table`.** Their own rulebook forbids it and they are right to
  — a restated vocabulary is one that drifts.

### Charter check

P3/P8 — a description string; no schema change, no vocabulary member added or removed, nothing
invalidated. P5 — the fix is that principle applied to the field the charter cites as its own example.
P9 — zero cost on the authored layer; the burden it removes is on the author. Measured: no reference
example moves anything, and none uses a superseded member — pinned by a test that recomputes it.

## RM143 — the enricher diagnosed a wrong-assembly coordinate and `compile --strict` built over it anyway

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler`). **Severity** medium ·
**Owner** compiler · **Motivating case** [S78](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### The measurement

A one-variant spec with a GRCh37 coordinate pasted into a GRCh38 module — the ordinary shape of a paper
stating its assembly once in the methods and nowhere near the table an author reads. `rs61849494` is
`10:51613269 G/A` on GRCh37 and `10:45982565 C/T` on GRCh38: 5.6 Mb apart and strand-flipped.

The reporter walked all four gates. `validate` passes, correctly — it is offline and cannot know.
`enrich(strict)` refuses, with a diagnosis they call better than anything they could have asked for.
`enrich(best_effort)` reports all three readings and writes the table, which is what best-effort means.
And `compile_module(strict=True)` **succeeds**, silently, over a module that is internally consistent
and about the wrong locus.

### Two of the three asks were already shipped, and saying so is half the answer

They offered three repairs in order of preference and asked for our view rather than guessing.

**Their (2) — have the compiler re-run the rsid↔coordinate agreement — is refutable on the data.**
`resolution.csv` does not hold both coordinates. For a coordinate-authored row the enricher records
what the author wrote, so there is one coordinate in the table and nothing to compare it against. The
change is not small, it is impossible without a fetch, and P2 forbids the fetch.

**Their (3) — make the compile warn — shipped in this same release and they could not have seen it.**
`verification_findings_recorded` (S70/RM130) reports every recorded finding at the author. It is absent
from 0.6.6, the version they measured. Reproduced: with the diagnosis in `verification.json`, a 0.7
compile prints *records 2 finding(s) across 2 check(s): genome_build_agreement (1 of 1),
reference_allele (1 of 1)*.

**Their (1) — record the diagnosis where the compiler can see it — is also mostly shipped**, and the
`verification.json` record is that place. What was missing is the last step: no severity attached to
it, so the fact was carried and never acted on.

### What shipped

`build_disagreement_error` refuses a `strict` compile when `verification.json` records a finding on
`genome_build_agreement`, in both `validate_spec` and `compile_module`, with the error equal on both
sides and placed ahead of `output_dir.mkdir()` so a refusal writes nothing.

**This does not move the strict line, and that distinction is the item.** `strict` means *reproducible*,
never *right* — the FAQ says so and it stands. `genome_build_agreement` is the exception on
**internal-consistency** grounds: a finding there says the module's rows are on a different assembly
than the `genome_build` it declares, which is one authored file contradicting another, not the module
disagreeing with an outside archive. Every other recorded finding keeps warning, pinned by a
parametrized test over four checks — including `reference_allele`, which *produces* this diagnosis's
input and still does not refuse on its own, because a ref mismatch has three causes and only one is an
assembly.

**The compiler adds no judgement.** It acts on a record the enricher wrote against a GRCh37 service the
compiler may never call. What changed is that the answer stops being discarded at the tier boundary.

Three things it must not do, each with its own test: **no attestation is silent** (an unverified module
is the ordinary case, and refusing on absent evidence reads unknown as wrong); **`findings=0` is a
clean bill**, so the gate keys on findings and not on the record's presence; and a **`skipped` record
is unknown**, which is what an `--offline` run writes — refusing there would make offline enrichment
poison a module.

### Repairs rejected

- **A column on `resolution.csv` marking the row as diagnosed** — their (1) read literally. It is a
  fact about a *check* in a table of facts about *variants*, the same axis that keeps `fetched_at` out
  of every fact set, and `verification.json` is the file that already exists for it. Also full cost
  under P9 for a fact with one reader.
- **Re-running the check in the compiler** — their (2), refuted above on the data.
- **Escalating every recorded finding under `strict`.** The obvious generalisation and the wrong one:
  it would fail a build over a ClinVar disagreement, which the cross-check deliberately refuses to do
  because the archive is the stale side often enough that the format would be arbitrating someone
  else's dispute.
- **Telling authors to always run strict enrichment.** Their own rejected candidate and correct:
  `best_effort` exists for good reasons, and a module authored under it stays wrong forever with every
  later gate green. The defect was the discarded diagnosis, not the chosen mode.

### Charter check

P2 — no fetch; the gate reads an injected sidecar. P3/P8 — no schema change, no field, no vocabulary
member; `BUILD_AGREEMENT_CHECK` names an existing one. P5 — severity and reporting stay separate axes:
the warning still fires in both modes and the refusal is the ladder's upper rung. Measured: no
reference example carries a `genome_build_agreement` finding, so nothing in the corpus changes and the
0.7.0 release record is unaffected.

## RM142 — the dosage pass declared a ClinGen obligation for a module ClinGen curates nothing of

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-enricher`). **Severity** medium ·
**Owner** enricher · **Motivating case** [S77](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What was measured

A single-variant `SIRT6` module. The dosage pass reported, correctly, that it covered nothing —
`dosage: missing: [SIRT6]` — wrote no `gene_metrics.csv` row, and wrote a ClinGen licence row into
`licensing.csv` anyway. Reproduced exactly: `covered=[]`, `missing=['SIRT6']`, zero data rows,
`licensing.csv` present with one `clingen` row.

Two costs, and the reporter is right that the second is the expensive one:

- **A false statement in a published artifact.** `licensing.csv` travels to the registry and is read as
  *this module uses this source*. It is not true of a module ClinGen curates no gene of.
- **It fires `declared_license_disagrees` for nothing.** Reproduced: a module declaring `license: MIT`
  and using ClinGen for nothing warns *declares MIT but annotation-layer sources report CC0-1.0*, and
  an author then adjudicates a conflict that does not exist. Two agents were measured spending real
  effort on exactly that in an earlier round.

**The compiler cannot catch it**, which is what makes this the pass's job rather than a check. The
orphan warning `_source_checks` emits exempts the `annotation` layer deliberately (RM46), because
`sources.csv` is where an author is told to record a hand-read source and warning about that would make
compliance noisy while omission stayed silent. So an annotation-layer row nothing uses is silent by
design, and only the pass knows whether it contributed.

### The fix, which is what the siblings already do

`merge_sources_file` is now behind `if covered:`. That is not a new rule — it is the rule the rest of
the family already follows and this one member missed. `gene_metrics`, `frequencies`, `assertions` and
`gene_validity` all pass `{row.source for row in out}` to `record_source_terms`, so a pass that wrote
no row records no source. `clingen.py` alone built a fixed row and wrote it unconditionally.

**Checked rather than assumed, because the reporter asked us to check the others**: `enrich_gene_metrics`
and `enrich_frequencies` were run offline over a module they cover nothing of, and neither writes a
`licensing.csv` at all. The defect is `clingen.py`'s alone.

**`covered`, not `out`, and not `not missing`.** `out` carries rows a *previous* run merged in, whose
terms are already recorded, so keying on it would be keying on history. `not missing` is the dangerous
inversion — it would drop the declaration from every module carrying one uncurated gene beside a
curated one, which is a real obligation going unrecorded. Both directions have a test, and so does the
second lap, where `covered` is empty because the work is done and the row must stand.

`ClinGenResult.source_row` is still populated whatever happened: the terms of what was *consulted* are
a fact a caller may want to render, and they are a different fact from what the module uses.

### Repairs rejected

- **Having the author delete the row.** The reporter's own rejected candidate and correct: it is
  machine-written and returns on the next pass, and authors deleting licence rows by hand is a worse
  habit than the defect.
- **A `covered: false` marker on the row.** Their alternative suggestion. It makes `sources.csv` carry
  rows that are not declarations, so every consumer reading the table — the compile gate included —
  gains a case to handle for a fact that has no reader. Absence already says it.
- **Removing the `annotation` exemption from the compiler's orphan check.** It would catch this and
  reintroduce what RM46 removed: a warning at the author who followed the documented advice to declare
  a hand-read source. Compliance warning while omission stays quiet is the wrong direction, and the
  exemption's reasoning is unchanged.
- **Recording "we queried this source" somewhere.** The reporter floated a `logs/` entry. Nothing reads
  it, and a run's history is not what `licensing.csv` is for — the same axis that keeps `fetched_at` out
  of every fact set.

### Charter check

P2 — no new fetching; the pass consults exactly what it consulted. P3/P8 — no schema change, no field,
no vocabulary member; a `licensing.csv` that was being written is not written, which cannot invalidate
a module that never depended on it. Measured: no reference example changes — none carries a ClinGen
dosage row from an empty pass — so the published 0.7.0 release record is unaffected.

The direction is worth naming: this **removes** a declaration, and a licence table losing a row is the
dangerous direction in general. It is safe here only because the row's own predicate is now the thing
that decides — a module ClinGen fed keeps its row, checked by test in three arrangements.

## RM141 — `validate --strict` blessed a module `compile --strict` refused, whenever the resolution table was partial

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-compiler`). **Severity** medium ·
**Owner** compiler · **Motivating case** [S76](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What was reported, and what reproduced

A consumer's `enrich` was killed by an external quota limit partway through a 263-subject module,
leaving a well-formed `resolution.csv` covering 201 of them. They reported two things: that nothing on
disk marks such a file partial, and — the part that made it urgent — that **merge-not-clobber turns it
into a silent wrong answer**, because the natural recovery of re-running merges onto the stale rows and
never retries the missing 62.

**The second half does not reproduce, and it does not reproduce on the version they ran either.**
Probed directly: a run over a table covering one of three subjects asks the source about exactly the
other two and commits all three. Measured on this tree and again on `v0.6.6` built from its own tag, so
this is not something 0.7 fixed underneath them. `enrich` gap-fills; the merge is over subjects the
table records, and a subject it does not record has nothing to merge onto. Their proposed repair (1),
writing the sidecar atomically, is also already shipped — `layout.atomic_writer`, from RM128 in this
same release, which is why the interrupted run left the *previous* table rather than a truncated one.

**And the reporter corrected their own account the same day, which sharpens what this closes.** From
the preserved artifact: the 203 rows are sorted throughout, the last line ends cleanly, and the 62
absent rsIDs scatter across the whole alphabetical range rather than forming a tail. So it is a
**complete write of an incomplete resolution set**, not a half-written file — which matches the code
rather than contradicting it, because a subject whose live request could not be made joins
`unreachable_rsids` and is written as **no row at all**, deliberately, so the table never states a
negative nobody established (`@unreachable-not-absent`). Nothing was interrupted mid-write, so RM128's
transaction and atomic writer would not have prevented it, and the same file comes out of a
`best_effort` run that completes normally over an unreachable source.

That re-attributes the closure to this item rather than to RM128, and by the right route: a check
reading the table against the spec beside it is the only thing that can see a set complete as a file and
incomplete as an answer, and it is indifferent to *why* a row is absent — which matters, because the
cause was misdescribed and the check does not depend on the cause.

**What is real is that nothing said so until the compile**, and that is a defect of ours.

### The defect

`compile --strict` refuses a module whose variants have no position after resolution — the check that
keeps a partial artifact from being published as a reproducible one. `validate --strict` did not
report it at all. So a spec whose table covers some of its variants passed the pre-flight clean and was
refused by the compile immediately after: the green-pre-flight-then-refusal shape the parity rule exists
to prevent, and the third time that rule has been broken in the same way.

It hid behind the rule's own exemption. What stays compile-only is *a check reading resolved rows*, and
coverage looks like one — but whether the injected table **can** place an authored row is arithmetic
over bytes the pre-flight has already loaded, and needs no resolution to have run. The exemption is
about resolved rows, not about the word "resolution".

### What shipped

`resolution.unresolved_subjects` is the predicate `resolve_from_table` applies, factored out and called
from both sides, so the two cannot drift into disagreeing about which rows are unplaceable — the
alternative was a second implementation of `_usable_loci`'s three exclusions (a `not_found` sentinel, a
row under another build, a row with no `chrom`). The pre-flight emits `rsid_unresolved` with the
sentence resolution already emits, and under `strict` appends the compile's error **verbatim**, which
the test asserts by equality rather than by both being non-empty: a pre-flight refusing in its own words
still sends the author hunting.

Two distinctions the fix had to keep, both the compile's own rather than new:

- **Nobody-asked is not asked-and-absent.** With a table present, an uncovered row is absent from
  something that was consulted and is named. With no table, nothing was consulted, and the pre-flight
  says so once instead of blaming a missing file once per variant. Both still refuse under `strict`.
- **`--no-resolve` means the same thing on both sides.** The master switch turns resolution off by
  request, and `resolution_disabled` already says that once with its row count; the coverage check
  stays silent there rather than restating it per row.

**A double-report was found and fixed while doing it.** `compile_module` runs the pre-flight in
best_effort whatever its own mode, so both passes reach this finding for the same subject; appending
blind published every one twice, measured at **24 warnings for 12 subjects** on a real example, with
`warnings_summary` counting 24. De-duplicated on the message, the `_check_contig_ploidy` idiom — safe
here because no message resolution re-derives embeds a count, which is the condition
`@no-rerun-with-counts` sets.

### Repairs rejected

- **A partial-file marker, sentinel, or row-count header on `resolution.csv`** — the reporter's
  framing. The file is a pure build product since RM124, and a marker in it would be a fact about a
  *run* living in a table of facts about *variants*, on the same axis `fetched_at` is kept off the fact
  set. It would also be unwritable by the case that needs it: a killed process writes no marker.
- **A `--rederive`-style completeness command** (their option 3). They offered to build it themselves
  and asked whether it is theirs; it is neither theirs nor a new surface — `compile` already answers it,
  and now so does `validate`, which is the command their authoring loop runs first.
- **Having `enrich` refuse to start on a short-looking sidecar.** Argued against by the reporter
  themselves and correct: a deliberately-resolved subset and an injected curated table are both
  supported practice, and nothing distinguishes either from a crash.
- **Recording the intended subject count in the run's output** (their option 2). `SubjectProgress`
  already carries `(done, total)` live, and a durable count of what a *killed* run meant to do is the
  marker above wearing a different hat.

### Charter check

P2 — pure computation over already-loaded bytes; nothing fetches, and the pre-flight gains no new input.
P3/P8 — no schema change, no new field, no vocabulary member: `rsid_unresolved` and
`resolution_not_injected` are existing codes and the strict error is the existing sentence. Measured:
no reference example moves its `artifact.digest`, `content_signature` or warnings, so the published
0.7.0 release record is unaffected — none of the sixteen has a partial table, which is why the defect
survived a corpus this size.

**One test was asserting the defect and was corrected**, not deleted:
`test_quoting_a_noncommercial_article_warns_and_never_gates` built a fixture with no `resolution.csv`
and asserted `validate --strict` reported valid. Its subject is that a licence finding never gates, and
the module was independently strict-refusable for an unrelated missing coordinate — so the fixture now
injects the table, and the assertion means what it says.

## RM140 — a study row's p-value and effect size are asserted to belong together, and nothing recorded what either came from

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`).
**Severity** medium · **Owner** format + compiler · **Motivating case**
[S75](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

### What was measured, and by whom

A reproducibility benchmark the reporter ran: two agents, byte-identical prompts, the same three DOIs,
one module each. They overlapped on exactly one row — `rs117385980` from PMID 41249831 — and disagreed
on its `p_value`, 0.36 against 0.75, with an identical `effect_size` of 1.42.

Neither was a misreading. The paper reports **two analyses of the same association**: an allelic
Fisher's exact test giving `OR 1.4, p 0.36` on the 2×2 allele table, and a univariate logistic
regression giving `OR 1.42, 95% CI 0.18–11.67, p 0.75`, with five adjusted models after it. One run's
row was internally consistent. The other carried the logistic regression's `effect_size` beside the
Fisher test's `p_value` — one analysis's estimate and another's p-value on one row.

**Everything was green**, and this is the part that made it an item rather than an authoring mistake:
`validate_module(strict)`, `compile_module(strict)` and `audit_module` all passed, and `quotes_found`
was satisfied — the provenance quote is verbatim and correct, because it grounds the *significance
verdict* and contains no statistic at all. A quote cannot witness a number it does not contain, so
quote verification is structurally blind to this class of error.

`StudyRow` had `study_design` — *"e.g. meta-analysis, GWAS"* — which describes the **study**. Nothing
described the **analysis**. So a correct row and a mispaired one were byte-indistinguishable to every
consumer and every check, and no check could be written, because the facts it would compare were not
recorded anywhere.

### What shipped

**One optional free-form column, `StudyRow.statistical_test`**, shaped like `study_design` beside it:
which test or model produced this row's `p_value`/`effect_size`, and what it was adjusted for. Plain
`str | None`, no vocabulary marker, no `RECOMMENDED_*` set — the space is open and a recommended set is
additive later if a corpus ever shows a shape. Wired through all four touch points, with the round trip
watched failing on each of the last two in turn before the test was called done.

**And one behaviour change, which is what makes the column do something.**
`duplicate_study_citation` fires on a repeated `(variant_key, pmid)` because the check's own docstring
reads that pair as *the same claim written twice* — which two rows naming two analyses are not. Since
this item, **both stated and different** suppresses it. Nothing else does: an absent `statistical_test`
is *unknown*, and unknown against a stated value cannot establish that two rows describe separate work.
Kleene, not `a != b` — the naive form would suppress on every absent cell and silently retire the check
for every module written before the column existed.

**`StudyRow._KEY_FIELDS` is not widened**, which the reporter explicitly scoped out and which is also
the legal answer: that tuple drives `hints.key_fields` and the `key.columns` an authoring surface
publishes, and re-keying a shipped authored table changes what an identity key means — major-only under
P3. The check restates `(variant_key, pmid)` rather than reading `_KEY_FIELDS`, so the split is
contained in the one place that needed it.

### Repairs rejected

- **A validator requiring the pair to come from one analysis.** The reporter argued this against their
  own ask and is right: it cannot be written, because nothing on either side of the boundary knows what
  test a number came from until the column exists, and adding column and gate together would make every
  published row retroactively incomplete. **Column first, and possibly never a gate** — what a gate
  would need is a second recorded fact per number, not a stricter reading of one.
- **Widening `(variant_key, pmid)` to carry an analysis.** Above. Also unnecessary: both rows already
  reach `studies.parquet` today — the duplicate is a warning, never a drop — so the capability was
  present and only the *legibility* was missing.
- **A `RECOMMENDED_STATISTICAL_TESTS` vocabulary.** A recommended set is a claim about what the corpus
  contains, and one module is not a corpus. Open now, additive later.
- **A second warning code for the half-stated pair** — one row naming an analysis, the other blank.
  Considered and not taken: it is one more permanent key for a case that is a transient state of an
  author mid-adoption, and the existing message plus the rule stated in
  [COMPILER § the analysis grain](COMPILER.md#one-paper-several-analyses-and-the-dedup-key-rm140)
  covers it. File it if anyone actually reports being stuck there.
- **Editing a reference example to exercise the column.** It moves digests for no gain and manufactures
  the RM139 *one side only* case at the next cut. Test fixtures only.

### Charter check

P3 — a new optional column on an authored model: additive, minor-legal, and it lands inside the already
decided `0.7.0`. P8 — optional with respect to every published module, so nothing previously valid
becomes invalid; pinned by a test asserting two specs differing only in the *presence* of the column
hash to the same `content_signature`. P5 — `study_design` and `statistical_test` are separate axes, and
a future `analysis_covariates` sits beside this one rather than inside it. P7 — the round trip carries
the value and the digest is a fixed point. P9 — full cost, an authored column, and the answer is that
the rare author here is the one asking: an unset cell burdens nobody and the alternative is prose in a
README that no consumer can read.

### What it measured

`artifact.digest` moved on **10 of the 16** reference examples — exactly the ten carrying a
`studies.parquet` — and `content_signature` on **none** of the sixteen. The same shape RM91 measured
when it added `effect_allele`, for the same reason: a new column in a materialized table moves bytes
and no authored identity.

**The published `0.7.0` release record was re-measured rather than left standing.** RM126's record
carries measured counts, and this item landed after they were taken: the 0.6.6 → 0.7.0 sweep was re-run
end to end with 0.6.6 built from its own tag, and the two parquet axes went from `4/15` to `14/15`
while `content_signature` stayed `0/15`. `studies.parquet:statistical_test` is declared on both axes,
and the concordance-parquet declaration calling itself *the release's most visible consequence* was
corrected in place — it was a measured claim, and ten digests to four is no longer that. The gate
exits 0 against the amended record. A stale measured number reads as an all-clear, which is the failure
this repo keeps meeting from the other direction.

The suppression is a **loosening of a warning**, not of validity: no module that compiled stops
compiling, and no module that was silent starts warning. The message and code are byte-identical for
every case that still reports (`@warning-text-is-api`), pinned by its own test.

## RM139 — the release gate could not tell a broken compile from a spec that outgrew the old compiler

**Shipped on 2026-08-31, inside the uncut 0.7.0** (`just-dna-format` + `just-dna-compiler`). Filed by
running RM126's gate for real at that cut, decided and built the day after.

**Severity** medium · **Status** ✅ shipped · **Owner** compiler · **Found by** the 0.7.0 cut

`gate_findings` failed a release when a module compiled on **one side only**, and its reasoning was
sound as far as it went: the likeliest operator error is running the sweep before `uv sync` propagated
the bump, and a module vanishing into an all-`False` result over its surviving neighbours is a false
green in the one mechanism the item rests on. But *one side only* was read as *a compile failed*, and
the very first real use of the gate hit the other cause. RM70 added the optional `requires_callable`
column to `pharm_variants.csv`, `reference_examples/cyp2c9_warfarin_grch37/` uses it, and 0.6.6
refuses that spec under `extra="forbid"`. Nothing failed: the previous release cannot produce a before
state for that module at all, so no like-for-like comparison exists and the sweep is right to say
nothing about it. The 0.7.0 record stated the exclusion in `evidence` prose the gate cannot read, and
the tag was waved through by a human — which is the state this entry ends.

**The decision, in two halves.**

*Which side, not whether.* The two directions are facts about **different releases**, and collapsing
them lost that. A module in the BEFORE tree and not the AFTER one is a regression **in the release
being gated** — it fails unconditionally, and now carries the compiler's own errors, which
`build_outputs` had been logging and discarding. A module in the AFTER tree and not the BEFORE one is
a fact about the *previous* release: whatever the cause, nothing in this release failed, and there is
no measurement to declare. A stale reused BEFORE directory holding a module the spec root no longer
has reads as the first, which is the fail-safe direction; the runbook already says fresh trees every
time.

*The exclusion moves into a field the gate reads.* `ReleaseRecord.unmeasured` names the modules the
previous release produced no output for, and the second direction fails until the published record
lists them. Old records read `[]`, which is the correct claim for them.

**Why that is not the per-module escape hatch this entry originally refused.** The refusal was right
about the shape it named — a field an operator can use to silence the gate is weaker exactly where the
docstring warns — and `unmeasured` is not that field, because the check is an **equality** over the
measured set rather than a membership test (`@registry-completeness`). It cannot cover a module the
sweep measured on both sides: listing one is reported as a note. It cannot cover a module this release
broke: that direction is fatal however it is listed, and `as_record` refuses to mint a record over
one. And a movement on a measured module still gates however the list reads. What is lost, precisely
and only, is that *the previous release could not compile module X* no longer blocks a tag — which is
right, because it is not a fact about the release being cut. What is gained is the forcing function:
`as_record` fills the field from the measurement, so the exclusion is committed to the published record
rather than remembered in a sentence nothing checks. That is the same mechanism `declared` already
uses, extended to the unmeasured set, not a second kind of gate input beside it.

The other three refusals in the original entry stand and were not revisited: the sweep still cannot
see the authored spec at the previous version, compiling the old spec from git would vary input *and*
compiler, and demoting the check to a note would re-open the false green RM126 exists to close.

**Measured, not asserted.** The 0.6.6 → 0.7.0 sweep was re-run end to end over all sixteen reference
examples with 0.6.6 installed in an isolated environment: fifteen measured, `cyp2c9_warfarin_grch37`
refused by 0.6.6 on `requires_callable]: Extra inputs are not permitted`, and the gate now exits 0
against the shipped record instead of needing a human to read past it. Removing a module from the spec
root exits 1 on the other direction, naming it.

**The prose-versus-field shape is the recurring one.** A count or an exclusion stated only in a
sentence goes blind — the triage threshold counter did it twice — so the field is pinned to the
sentence by a test rather than maintained beside it.

## RM126 — nothing tells a consumer what a release changed about compiled *output*

**SHIPPED in 0.7 on 2026-08-28 — `just_dna_format.release_records` (record, `needs_recompile`, roster), `just_dna_compiler.sweep` + `just-dna-compiler sweep` (instrument and gate), and `0.6.1`/`0.6.6` backfilled by measurement. See [SCHEMAS § The release record](SCHEMAS.md#the-release-record-07-rm126--what-a-release-changed-about-compiled-output) and [COMPILER § The release-record sweep](COMPILER.md#the-release-record-sweep-rm126).**

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output) on 2026-08-28 — BUILDS in 0.7, in full plus the S65 roster.** Record + `needs_recompile` in format, the sweep in the compiler, the gate in the bump→tag sequence; intervals compose as a union over `(a, b]`, which is what gives S65's convergence requirement for free.

**Severity** medium-high · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the record, `needs_recompile`,
the roster, the sweep and the release gate. The charter *required* this channel: Principle 3 says a corrected derivation may ship in
any release but never silently, and this is the declaration it mandates. Until it exists the charter
describes a surface that is not there · **Owner** format (record + `needs_recompile`) + compiler
(the sweep) · **Motivating case** [S62](CONSUMER_SUGGESTIONS_HISTORY.md) (just-dna-registry)

A registry sweeping its catalog for artifacts that should be recompiled has two questions it can
answer and one it cannot. *Is the stored input still legal?* — re-run `validate_spec`, which answers
`ok`. *Was this compiled under a contract-incompatible compiler?* — compare versions, and a patch is
compatible. Neither is the question a changed derivation raises: **would recompiling this artifact
produce different output than the stored one?** Today the only way to answer it is to enrich into a
scratch directory, recompile and diff — which is the operation, not a triage for it.

**Reproduced here, and it is wider than the report.** All sixteen `reference_examples/` compiled under
`v0.6.1` (detached worktree) and under `0.6.6`, spec inputs byte-identical across the interval — the
whole of which is patch releases:

| | measured |
|---|---|
| changed at least one published manifest field | **16 / 16** |
| moved `artifact.digest` (and `artifact.files` with it) | **10 / 16** |
| moved `content_signature` | **0 / 16** |

`compilation.compiled_at` is a timestamp and is excluded as noise. The digest movement is not noise:
`studies.parquet` grew by exactly 257 bytes on each of the ten because **RM120 added the authored
column `curator`**, first present in `v0.6.5`. So the *parquet schema* moved across a patch interval,
which is the sharpest form of the finding and the one the reporter had not seen — they reported
changed manifest fields. `stats.genes`/`stats.gene_count` moved on **seven** (RM121) and
`literature.quotes_unchecked` appeared on three (RM119). **Six of the sixteen changed a published,
indexed manifest field with *both* hashes byte-identical** — `apoe_epsilon` went `genes: []` →
`["APOE"]` at the same `artifact.digest` and the same `content_signature`. That is the sharpest number
here and the one the surface has to answer to.

**Authored identity held throughout**, which is the charter working as designed: an unset optional
column is omitted from `content_signature`, so nothing a consumer keys on moved. That is exactly why
no existing surface can see this — a digest comparison, a signature comparison and a `revalidate` all
correctly report no change while an indexed field goes stale.

**The shape asked for** is a declaration keyed on the **interval** rather than on a version, because
the question is always *compiled under X, installed Y*, with the axes separated — parquet schema,
parquet bytes, `content_signature`, and the set of manifest fields. Deliberately **not** a
`should_rebuild` verdict: the same fact carries different costs per consumer (a stale cache is a free
rebuild for `just-dna-lite`; for a registry it mints an immutable PATCH and moves what a client
tracking `latest` receives), so the decision is the consumer's and only the fact is ours.

**Three things the design has to get right, and the third is why this is filed rather than shipped.**

- **Unknown must be a state, not an empty result.** Asked about an interval the installed package has
  no record of — an artifact compiled under something newer, or older than the table reaches — the
  answer is *cannot say*, never *nothing changed*. That is the house tri-state (`None` is never
  `False`), and without it the surface is worse than nothing, because a consumer would stop
  recompiling on the strength of a silence.
- **`content_signature` needs its own axis, separate from bytes.** For a registry a signature is a
  permanent global duplicate-content claim that only a purge frees, so *the identity moved in a patch*
  is an answer to fail loudly on rather than merely to act on. Our sweep says it has never happened;
  the axis exists so that stays checkable rather than remembered.
- **A hand-kept per-release map is the defect wearing a public name.** The reporter said so themselves,
  and it is `@registry-completeness` — five of the six RM104–RM111 fixes were a derived value restated
  by hand. So the map has to be a **measurement**: the sweep above is the guard's prototype, and it is
  cheap — check out the previous tag into a detached worktree, compile `reference_examples/`, diff the
  manifests, and fail when the declared hints disagree with what actually moved.

**The shape, decided 2026-08-21 in the S62 thread — two axes, and only one of them is measurable.**

- **`output_differs` — measured.** One record per release, produced by the sweep: parquet schema,
  parquet bytes, `content_signature`, and the set of changed manifest fields. Intervals compose as a
  **union over the releases in `(a, b]`**, so storage is linear rather than O(releases²) and
  *moved-and-moved-back still counts as moved*, which is the right reading for staleness. Backfillable
  for 0.6.1→0.6.6 by measurement with the harness that produced the numbers above; older intervals stay
  honestly `unknown`.
- **Correction versus addition — declared.** Only the person fixing the bug knows whether the stored
  value was **wrong** (`stats.genes`) or merely **absent** (`curator`), and no diff can tell them
  apart: both look like "a field changed". This is the canary — *not a minor, but rebuild time* — and
  it is the half the consumer cannot compute for themselves at any price.
- **The gate is what keeps the declaration honest.** A release whose sweep shows a changed field with
  no declaration covering it **fails**. That is what stops this becoming the hand-kept map everyone
  agrees it must not be: the measurement forces the declaration rather than the author remembering to
  write one. A release where nothing moved records a measured zero **with its evidence**, never
  silence (`@tautology-zero`).

**This does not contradict the reporter's "no `should_rebuild` verdict", and the item must say so.**
Their objection is to a *cost* verdict, because the cost differs per consumer. The correction flag is
not a cost judgement — it is a fact about whether a value we published was wrong, which is upstream
knowledge only this repo holds. The per-axis breakdown stays exposed underneath it, so a consumer who
wants the facts rather than the flag still has them. A bare boolean with nothing under it would deserve
their objection exactly.

**Tiers.** The record, its model and a pure `needs_recompile(compiled_under, current)` belong in
`just-dna-format` — a static table plus a function, which pydantic-only holds comfortably, and format
is the tier every consumer has. The **sweep instrument** belongs in the compiler, since producing a
record means compiling. The **gate** runs in the bump → `uv sync` → tag sequence rather than as an
ordinary test, because it needs the previous release actually installed. Keyed on `compiler_version`,
which is what `manifest.compilation` already stamps and what a consumer holds. **Scope v1 to
compiler-derived outputs and say so** — enricher-side outputs stay unmeasured rather than unchanged.

**Open, because the representation is not obvious.** An interval table is O(releases²) unless it is
composed from per-release records, and composing them means deciding whether the axes are unions
(a field that moved and moved back still moved) — probably yes, but that is a decision. The tier is
open too: the natural caller is a consumer of `just-dna-compiler`, and the hints describe compiler
behaviour, but a verify-only consumer holding `just-dna-format` alone has the same question about a
manifest it can read. **[RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one)
is why this is needed rather than a nicety**, and it is now **closed**: a corrected derivation is a bug
fix, deferring it to a minor means serving a wrong value meanwhile, so the release number cannot carry
staleness and a second channel is the only resolution left. The charter amendment of 2026-08-21 made
that a rule, which is what turns this item from a nicety into a debt.

### Four constraints handed back by the consumer who built the other half (S65, 2026-08-21)

just-dna-registry shipped the recomputation side as `services/rebuild.py` in their 0.21.0 and reported
what building it taught them. Each of these narrows the design and none was visible from here.

- **Convergence is a hard requirement, and the obvious shape fails it.** If a hint fires for a version
  compiled by the *exact* compiler now installed, recompiling derives the same value again — so an
  automated sweep mints a fresh PATCH every run, forever. That is the *a patch is not a gap* rule
  re-entering by a different door. **The interval-keyed shape gets this for free, because the interval
  from a version to itself is empty** — so state that as load-bearing rather than incidental, since a
  field-keyed or "latest known defect" shape would not have the property. It is also what bounds a
  false positive to one wasted version number per module ever, which is what made them willing to act
  unattended at all.
- **Recomputability splits the problem in half, and the better half already shipped.** For a manifest
  field that is a pure function of the authored rows, a consumer can recompute the *current* answer
  from stored inputs — no enrichment, no parquet, no network — using `spec_tables` (RM116) for the
  defaults-folded rows and `module_stats` (RM121) for the derivation. Neither landed for this reason.
  **So what would help most is not a bigger table but a small published roster: which manifest fields
  are pure functions of the authored rows.** That is a fact we hold and they guess at, and it *shrinks*
  this item rather than growing it. The interval-keyed table then only has to cover what a consumer
  cannot recompute — `literature.quotes_unchecked` (RM119) is their worked example, since it derives
  from a sidecar rather than from authored rows.
- **The roster's boundary is conditional, and the condition is invisible from outside.** `validate_spec`
  computes `stats` over the full row set; `compile_module` re-derives over the survivors **only when
  the symbolic-allele drop removed something**. So a recomputation from authored rows is the *pre-drop*
  side, and `manifest.stats` legitimately disagrees with it — permanently, under any compiler — for a
  module that lost the sole row naming a gene. A roster stating "pure function of the authored rows"
  without that condition would send consumers to spend version numbers on modules that are current.
- **`compilation.dropped_rows` closes the residue, and shipped 2026-08-24.** Their guard discriminates
  on `variant_count`, which catches a drop from `variants.csv`; a drop inside a *kind* table moved no
  published counter at all. With the counter, the `stats` half of the roster is unconditionally
  checkable. They rejected reading the warning text for the reason our own catalogue rule gives.

**Scope it for coexistence rather than replacement, at the reporter's request.** Their probes sit
behind one named seam so a probe this covers retires by deletion, and they may keep one or two anyway
— a recomputation checks the artifact actually in front of them, a hint states what a release did in
general, and the two fail differently. **The useful division: we state what a release did, they check
what a specific stored artifact says.** And they are not re-asking for `should_rebuild`; building the
decision themselves is what surfaced all four constraints above.

---

## RM134 — PubMind as a literature-derived annotation authority, and a ClinVar concordance check

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm134--pubmind-as-a-literature-derived-annotation-authority-and-a-clinvar-concordance-check) on 2026-08-28 — BUILDS in 0.7, pulled in after the other eleven were decided and reviewed against them.** Eight corrections, two of which were defects that would have shipped: **the concordance record is shared with RM130 and RM130's shape changes because of it** (`ClinSigConflict` names its authority in a *field*, so a second authority would have cost a key change or a retype — major-only); and **one normalizer, not two, after two fixes** — `_normalize_clin_sig`'s map keys are underscored while PubMind's tokens are spaced, so `Uncertain significance` and `Conflicting` both fall to `other` today and the check would manufacture a disagreement on PubMind's largest disagreeing class. **A maintainer stress test at five authorities failed the drafted vocabulary**: `pubmind_only`/`clinvar_only` name the authority inside the member, because one field carried two axes. Split into `authority_concordance` and `authored_position`, five members each at any N. **Nothing resolves a split** — E+A agreeing against B/C/D needs a weighting model this repo has refused to invent three times — so the precedence list is recorded as methodology and computed with by nothing. Licensing governs what a module may *do* with the values, not whether the machinery exists: unknown terms warn and never gate, and publishing such a module is RM27's axis.

**Severity** low-medium · **Status** ✅ **SHIPPED in 0.7** — all four sections (§ A the snapshot and
the shared normalizer, § B the N-authority check, § C `draft-panel --source pubmind`, § D the hint)
· **Owner** enricher · **Motivating case** the PubMind paper
(doi:10.1038/s41467-026-76834-4, 20 August 2026), and a user direction on 2026-08-28 to design both a
ClinVar-shaped derived table and a ClinVar concordance check · **Full design**
[PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md)

PubMind extracts variant–disease–pathogenicity associations from 41.7 M PubMed abstracts and 5.4 M PMC
full texts with LLaMA-3.3-70B behind a fine-tuned BERT triage stage. It is **a source, not a
competitor**: its own discussion calls it *"a literature-grounded complement to human curated
databases"*, and the description holds one layer further down — it produces assertions and stops
exactly where we start, at identity, integrity, licensing and the round trip. The only contested
surface is its pitch to institutions wanting their own interpretation database, which is our module
author's use case; what it hands them is a SQLite file behind a Flask app.

**What is reachable, measured against the bytes rather than the paper.** The web API takes `gene`,
MONDO and PMID/PMCID only — an rsID query is refused — and returns aggregate counts, never a record,
which the response says outright. So the single per-variant channel is the coordinate table ANNOVAR
redistributes as `hg38_pubmind_db` (2026-08-24, 6.5 MB gzipped, 909,224 rows: `PVID`,
`pathogenicity_sum`, `paper_level_pathogenicity_score`, `confidence` 0–3). Its coordinates are
**VCF-style despite the ANNOVAR packaging** — no `-` alleles anywhere, deletions carry the anchor base
— so it joins our `chrom`/`start`/`ref`/`alts` with no translation. Whether the indels are
left-normalized is not established.

**It is much smaller than 909,224.** 439,388 rows (48 %) are **enumerated codon alternatives, not
observed variants**: where only a protein change was recovered from text, every codon encoding that
amino acid is written out, and 439,383 of those triplets need two or three simultaneous base changes
to reach the reported protein — which is a statement about the protein, not a position anyone can
genotype.
Decomposing the single-base codons leaves **342,209 distinct `chrom:start:ref:alt` keys over 305,935
loci** as the honest joinable layer. 523 rows have `Ref == Alt`.

**Consolidation is on extracted text, never on a coordinate**, so PubMind has record identity where we
have variant identity: 68,744 coordinate keys (8.4 %) carry more than one PVID, worst case 35. At
chr6:26092913 G>A (HFE C282Y) eight PVIDs disagree four ways, and one of them — `PVID926871`, verdict
**Benign** — pairs `rs1800562` with gene *TMPRSS6*, a chromosome 22 gene on a chromosome 6 variant.
`_gene_locus_conflicts` catches that shape today (`@gene-locus-relationship`).

**Worth on our own corpus**: 173 of 423 GRCh38 `reference_examples` loci matched (40.9 %), 190 of 589
authored ALTs exactly (32.3 %), and where both sides state a verdict they agree on 83 of 134 (62 %),
every disagreement running our-pathogenic vs their-uncertain-or-benign. That profile — real breadth,
low confidence — is a **cross-check source, not a fact source**.

**The design, directed 2026-08-28, is four sections.** An earlier draft of this entry stopped at a
report-only check and recorded the rest as blocked; that framing is overtaken, and the licence
constraint moves from *reason not to design* to *precondition on shipping*.

**A. `pubmind build` / `pubmind publish`**, a sub-app beside `clinvar`, mirroring `clinvar_build.py`:
polars builder, fixed column order for a byte-identical rebuild (P7), one parquet plus `release.json`
through `locations`. Schema follows `_empty_schema()`'s split, except **no column is a resolver link** —
"authority" here means an authoritative *annotation* source the way ClinVar is one, never
`resolution.csv`'s `authority` (`@source-vs-authority`), because PubMind's coordinates are PyEnsembl
back-mappings of extracted text. `pathogenicity_sum` maps into `VALID_CLIN_SIG` with the composite kept
verbatim in `pubmind_sig_raw`, the `clin_sig_raw` precedent. Every normalization drop is **counted into
`release.json`** rather than silently applied (`@dont-discard-computed`): 160,090 codon rows decomposed,
439,388 enumerations and 523 `Ref == Alt` rows dropped, 20,131 indels kept but stamped, and PVID
fan-out kept as separate rows because collapsing it would pick a winner by an ordering nobody defined.
**`publish` refuses**, on the PharmVar precedent (`@gated-source-caches`) — a bulk file under terms we
cannot establish is not one we may pass on, and the command exists and refuses rather than being
absent, which would read as an oversight somebody helpfully fixes.

**B. A three-way check, module ↔ ClinVar ↔ PubMind**, beside the existing ClinVar `clin_sig` check
rather than replacing it. Seven outcomes — `concordant`, `authored_dissents`, **`authorities_differ`**
(the case nothing today can report), `pubmind_only`, `clinvar_only`, `neither`, `unchecked` — combined
under Kleene, with unknown withheld and never negated. `ClinSigConflict.opposed` already draws the
severity line (opposed vs merely different) and is reused rather than re-invented. Warning-tier in both
modes, never escalating (`@clinsig-never-escalates`), and `authorities_differ` is not a module defect at
all. Corpus-wide concordance is stamped into `release.json` **at build time only** — our own
reproduction of their 10.6 % / >80 % claims against our denominator — because a message embedding a
count that runs twice publishes two numbers (`@no-rerun-with-counts`).

**C. Drafting**, through `--source pubmind` on the existing `draft-panel` rather than a new command,
since it writes the same tables from the same gene argument and a twin would duplicate the genotype
worklist, placeholder guard and dedup pass. `--min-confidence` is the `min_review_stars` analogue;
identity is coordinate-whole or nothing (`@identity-whole-or-none`), most PubMind rows carrying no
rsID. **The self-agreement trap has an existing answer**: a module drafted from PubMind and then checked
against PubMind agrees with itself, so `pubmind` joins `DRAFT_PROJECTIONS` projected onto `clin_sig`
(`@draft-digest`) — raw CSV cells at draft time, and the skip a conjunction of release **and** digest.
The ClinVar half of B is unaffected, which is why the three-way shape earns its keep.

**D. The hint surface**, unchanged and cheapest: surface verdict, confidence, paper count and PMIDs
beside the cell, and never pre-fill `clin_sig` (`@hint-redundancy-bearing`) — the same defect
`@draft-digest` solves one layer down, without a digest to rescue it.

**The gate is one unanswered question, and asking is the unblock action.** A and D are buildable now;
B and C acquire and carry values. The ANNOVAR-distributed table publishes **no data terms** —
`LICENSE.md` covers the software (academic, non-commercial), the paper is CC BY-NC-ND, the table itself
says nothing, and unknown is not permissive (`@no-named-licence`). Ask WGLab and CHOP's Office of
Technology Transfer in writing; it will not resolve itself by the file continuing to download without
a key. Separately, RM27 still owes the redistribution axis (`@redistribution-ungated`) — a gate on
*publishing a module that carries such bytes*, not on building the snapshot or running the check
locally, and conflating the two is what stalled this area in the first draft.

## RM133 — a card subtitle has no amendable home, and the binding is not where that gets fixed

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm133--a-card-subtitle-has-no-amendable-home) on 2026-08-28 — BUILDS in 0.7, on the authored layer at zero cost.** `short_description` joins the registry-owned family as a **separate** frozenset beside `IDENTITY_AUTHORITY_KEYS`, stripped by the same function, so the stored bytes are untouched and the closure stands; the ~120-character calibration ships as a constant rather than being guessed at downstream.

**Severity** low-medium · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the binding question it
arrived with is **answered and closed** · **Owner** format (+ registry, for the half that is theirs) ·
**Motivating case** S64 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

Measured by the reporter: editing `module.description` from 44 words to 11 moves **no**
`content_signature`, **no** `artifact.digest`, **no** fact signature — and drops the closure, because
`manifest.inputs` covers the raw bytes of `module_spec.yaml`. `README.md`, by a wide margin the longer
prose, is outside `inputs` and freely amendable. The shortest fixable prose in the system was the one
that could not be fixed.

**The binding stays as it is, and the reason is the partition, not the cost.** The ask was to split it
along the line `content_signature` already draws. That line is stated in `integrity.py` and excludes
**name, version and namespace** alongside title and colour — so a binding drawn there makes a closure
**transferable across a rename**: a module closed and signed by a named reviewer keeps its attestation
after its identity is changed. `content_signature` excludes those *so a registry strip does not move
content identity*, which is right for a content-dedup key and exactly wrong for an attestation. The two
hashes cannot share a partition because they answer opposite questions about the same fields. **Do not
re-propose this.**

The reporter's narrower six-field version (`title`/`description`/`report_title`/`icon`/`icon_set`/
`color`) does **not** carry that attack and is recorded as the better form of the idea. It inherits the
cost they named themselves — hashing a *parse* of the yaml, and so every canonicalization question
`content_signature` answers, with two hashes able to disagree about what counts as display. RM82 is the
precedent that prices it: the last change to the binding turned on being *a byte transform needing no
loader, no parse and no schema knowledge*, and refused BOM/whitespace/final-newline because each
*"makes the binding more content-ish without making it content"*. A field-aware split crosses that line
on purpose.

**What the binding buys, since the reporter asked and could not construct it:** it is the *reviewer's*
claim rather than the artifact's. The other two hashes answer *is this the same data* and *are these
the same bytes*; this one answers *is this the same document a named person signed off*. A card
subtitle is a claim about what the rows mean, so excluding it would make the attestation cover less
than the reviewer actually read.

**The route that actually unblocks it, and it is the item.** The framing *"the binding overrides the
registry's rule from a layer below"* assumes an amend must **rewrite the stored `module_spec.yaml`**.
It need not: `normalize.IDENTITY_AUTHORITY_KEYS` (`namespace`, `owner`, `canonical_id`) is the standing
precedent for **registry-owned** metadata that sits beside the module rather than inside it, with
`strip_authority_keys` handing the spec to our validator without them. A registry-owned display
override leaves the stored bytes untouched, so `manifest.inputs` still matches, `verify_manifest` still
passes and the closure stands. **So the registry's `amend_display` is not gated on this item** — it is
gated on whether the amended value is registry-owned or a spec rewrite.

**What is left to design: where a bounded `short_description` lives so that it lands amendable.** Not
on `ModuleInfo` — under the answer above every field in `module_spec.yaml` is on the un-amendable side,
so putting it there reproduces the defect in a new place, which is the reporter's own objection and it
is correct. Their argument for why a `max_length` is legitimate on a **new** field where it is not on
`description` holds and is why this is a real item: a field that exists to fit a fixed layout is
*specified* by that layout, it refuses nothing anyone has written, and absent it everything behaves as
today. Calibration from the live catalog: ~**120 characters**, against a measured 71 (comfortable) and
467 (the case that prompted it).

**Not in scope**: render-time truncation or folding, which hides prose an author chose to write and
leaves the spec as wrong; and anything retroactive to the seven published modules, which met every
requirement that existed.

## RM71 — the alleles a drafted `genotype` stub must be written from are in no file

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file) on 2026-08-28 — BUILDS in 0.7, and no schema moves.** The answer to *where does an author do this work* is **in the command they already ran**: the worklist covers every stubbed row in the file rather than only this run's additions, and `draft-panel` gains the `--dry-run` that `draft` has. The bulk advisory command is rejected for putting the worklist in a third place.

**Severity** medium · **Status** ✅ **SHIPPED in 0.7** (2026-08-28) — the worklist now covers every
stubbed row in the file, and the `--dry-run` the decision asked for turned out to have shipped in
0.5.1 already, so what landed is the test that pins it · **Owner** enricher (`clinvar_draft`) ·
**Found by** dogfooding on 2026-08-13, `reference_examples/hboc_palb2/`

### What was observed

`draft-panel` drafts `variants.csv` rows from ClinVar and leaves `genotype` as
`vocab.TEMPLATE_PLACEHOLDER`, correctly: ClinVar publishes **alleles, not genotypes**, and whether
carrying a pathogenic allele once is informative is inheritance-mode interpretation the source does not
state. The mechanism under it is `draft.PartialRow` — the row is validated by **omission** and matched
on `match_on` (the identity columns) rather than the natural key, because the natural key runs *through*
the stub, which is what makes a re-draft after the human fills the genotype report `already_present`
instead of appending a second stub. None of that is in question.

What is missing is that the alleles the author must write the genotype *from* are in no file. A drafted
row is rsID-only — identity whole or not at all — so `rs118203998` arrives with empty `ref`/`alts`, and
the pair is stated once, in the warning stream:

```
warning:   genotype for rs118203998: ClinVar publishes G>T — an allele pair from {G, T}
```

The author's next action is an edit to a file that does not contain the information. At the 16 rows
PALB2 yields at ClinVar's 3-star floor this is a transcription exercise; at the **761** the same command
drafts for PALB2 at the 2-star floor it is not one.

**And it is emitted exactly once.** The worklist is built inside `if report.added:` and scoped to
`added_records`, which is itself a correct earlier repair — it used to name rows the model had refused
and rows already in the file, so a "3 row(s) carry a placeholder" header was followed by twenty-seven
lines. The consequence is that re-running `draft-panel` after the first draft adds nothing and therefore
prints **no worklist at all**, and `draft-panel` has no `--dry-run` (`draft` does). The information
cannot be re-requested from the command that produced it.

### Candidate repairs, and why each is wrong

- **Write `ref`/`alts` into the drafted row.** The one the ledger already names. A drafting provider
  fills identity whole or not at all, and the model forbids `ref`/`alts` without a coordinate — so this
  means writing the full coordinate, which discards the rsID identity the provider deliberately chose as
  the stabler and more legible one. `alts` is also `REDUNDANCY_BEARING`: the compiler's allele-membership
  check compares the author's genotype against it, and that check keeps its force *because* the two were
  authored independently. Filling it makes the compiler compare ClinVar with ClinVar.
- **A comment column on `VariantRow`.** `extra="forbid"` rejects any column the model does not declare,
  so a "comment" is a real optional field — full cost on the most expensive table, carrying text that is
  dead the moment the stub is replaced. It
  is also a provenance claim with no machine reader: "ClinVar publishes G>T" is a statement about a
  snapshot release, and a re-draft from a newer one leaves it naming the old alleles. That is exactly
  the staleness `licensing.withdraw_stale_dataset` had to be built for on `dataset`, on a column where
  nothing could notice.
- **A sidecar the author reads beside the CSV.** Half cost, so the cheapest legal candidate, and still
  wrong three ways. Its only reader is a human, which is the one thing the charter amendment says to
  discourage rather than leave unmentioned. Its join key is the key the stub runs through, so it either
  keys on the rsID — saying nothing a `hint variant` call does not — or on the natural key, which
  contains the placeholder. And an unknown file in a spec directory is tolerated but not read, hashed or
  listed in `artifact.files` (S16), so a worklist file the author must remember to delete becomes a
  permanent resident of every drafted module, with one more name for `_check_misspelled_tables` to
  learn.
- **Have the enricher fill it after resolution.** `enrich` resolves the alleles, so it *could*. It must
  not, twice: `ref` and `alts` are both in `hints.REDUNDANCY_BEARING` (`ref` against
  `verify_reference_alleles`, `alts` against the allele-membership check), and filling a cell a Class-2
  check cross-examines makes the comparison vacuous. And the dependency runs the other way — `enrich`
  refuses to load a file containing a placeholder, correctly, because forward resolution is allele-aware
  (`hosting_verdict`) and a placeholder genotype would silently skip that filter on exactly the
  one-to-many rsIDs that need it. Rewriting the authored cell at all is the parked enricher-co-authoring
  item, which nothing here should ship by accident.
- **Make `genotype` optional so the stub is unnecessary.** Barred by Principle 8 — it is a required
  field, and demoting one within a major is the forbidden move. It would be wrong at 1.0 too: the
  zygosity decision is what the stub protects, and an optional genotype lets a module ship without it
  silently, which is the reassurance-manufacturing failure this format guards hardest against.

### What is actually undecided

`just-dna-enricher hint variant rs118203998` already returns the alleles and already refuses to apply
them (`refusal="redundancy_bearing"`), so the information is reachable at one command per row. The
candidate that survives every objection above is therefore a **bulk read-only advisory** over a module's
stubbed rows: it changes no schema, fills no cell, and re-answers a question the drafting run answered
once. That is a build rather than a decision — but it is not obviously the answer either, because it
puts the worklist in a *third* place while the author's complaint is that it is not in the one place
they are editing.

So the open question is not "which column" but **where an author does this work**, and this repo has no
model of that. Filed here rather than built for exactly that reason.

## RM85 — a recorded release, compared against the one its source publishes now

**Shipped in `just-dna-enricher` (plus a `just-dna-format` vocabulary member) on 2026-08-29.** The
enricher check `PROPOSAL_0_7` decided: `currency.check_dataset_currency`, run at the end of `enrich()`
and attested as `dataset_currency`, with `--verify-datasets/--no-verify-datasets` as its switch.

**Severity** low-medium · **Status** ✅ shipped in 0.7 · **Owner** enricher ·
**Motivating case** a source-drafted panel two ClinVar releases later

### What it does

`SourceRow.dataset` had recorded which release a module's rows came from since RM4, and two things read
it — the tautology skip, and `withdraw_stale_dataset` when a module ends up mixing two. Neither answered
*"ClinVar has published since you drafted this"*. The check reads `sources.csv`, asks each source which
release it publishes now, and reports the gap. It writes nothing: repairing a stale label is a re-draft,
which is an author's decision and a different command.

It is `--rederive`'s cheap neighbour, and ENRICHER § `rederive` now says so where an author reads it.
Both ask *has the world moved* — one about the rows, one about the release **label** — and the label
question costs one request per source, so it is what tells an author whether the expensive one is worth
running.

### The three things the entry did not settle, decided in the build

- **Which source can actually be asked.** The entry said "the source's current release" as though every
  source publishes one in a form we record. They do not: `dataset` labels are minted by whichever pass
  wrote the row, and only ClinVar's has a live counterpart this tier can read in the same namespace
  (`clinvar_<##fileDate>`, through the reader `clinvar_build` already uses). So **one probe ships**, in
  a registry (`PROBE_SOURCES`, derived from `default_probes` rather than restated beside it), and every
  other source reports `unsupported` — an honest *this tier cannot ask*, never a clean bill. Widening it
  is adding a member.
- **Comparability is a third state, beside the tri-state the entry did name.** `clinvar_dataset_label`
  has a digest form for a snapshot built from a VCF whose header stated no date. A digest against a
  stated date names one release space in two spellings and equality across them means nothing, so it is
  *uncomparable* (`no_reference`), not *behind*. Reporting it as behind would send an author to
  re-draft a module that may already be current.
- **`strict` refuses over `behind` alone.** Severity follows the mode, as the decision says — but an
  unreachable source and an `--offline` run both leave every leg unchecked, and escalating those would
  make `--offline --strict` impossible forever over something no author can edit. That is the
  `unreachable_rsids` rule (warned in both modes, escalated in neither), and the gate is written over
  the superseded set so the two cannot be confused.

### What the shape had to avoid

**A check must not be able to agree with itself.** Wave 2 had just found a `--rederive` path seeded from
its own staged answers, reporting a clean bill for exactly the subjects it was re-checking. The same
shape was available here — comparing `dataset` against the *provisioned snapshot's* `release.json`,
which is very often the snapshot the module was drafted from. So the current release is read from the
source over the wire, and the rows compared are the ones on disk before this run's commit; the licence
rows `enrich()` itself writes are at the `resolution` layer and carry no `dataset` at all.

**And the denominator has to be honest.** `subjects` counts the legs asked *and* answered comparably;
an unreachable or unaskable source is named in the record's `detail` rather than counted, and with no
leg settled the pass records a **skip** instead of `ran(0, 0)`.

### Repairs refused, and still refused

- **A column stating what this module was made from and what would age it** — RM71's argument one table
  over: it restates `dataset` and rots where `dataset` is maintained.
- **A publish-time or catalog-side signal** — puts the notice where a reader is rather than where an
  author is, and is out of these packages' scope. Still recorded as an ask rather than built.
- **Nothing, deliberately** — defensible only while a module has one author who remembers.

### Also worth knowing

The probe **streams and abandons** rather than sending a `Range` header: a server that ignores one
answers `200` with the whole 200 MB body, and the probe silently becomes a download. Reading the first
256 kB off a normal stream and closing it needs no promise from the server.

## RM130 — a check's findings were counted and not kept, so a conflict had no name to act on

**Shipped in `just-dna-format` + `just-dna-compiler` + `just-dna-enricher` on 2026-08-28.** Two new
optional derived tables, three new closed vocabularies and one new warning code — additive throughout,
and no published module's identity moves, because a module that carries neither file contributes
neither entry.

**Severity** medium · **Status** ✅ shipped in 0.7 (the observability half shipped 2026-08-24) ·
**Owner** enricher · **Motivating case** S70 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md ·
**Decided in** [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm130--a-checks-findings-are-counted-and-not-kept-so-a-conflict-has-no-name-to-act-on),
amended the same day by RM134

### What shipped

`clin_sig_concordance.csv`, keyed `(variant_key, genotype)`, and its paired
`clin_sig_authority_calls.csv`, keyed `(variant_key, genotype, authority)`. The first carries the
agreement state — `authority_concordance`, `authored_position`, `opposed`, and the module's own call —
and the second carries what each authority actually said, with its raw token and its confidence in its
own units. Both are compiled to parquets, fact-hashed, summarized in `manifest.clin_sig_concordance`,
and reported at `validate` and `compile` by `clin_sig_concordance_contested`.

The enricher half is `concordance.py` (the classifier, the row builder and the writer) plus
`clinical.clin_sig_concordance`, which returns the two tables or `None`. `ClinSigConflict.clinvar`
became `authority_clin_sig` beside a new `authority`, with the old name kept as a read-only alias.

### Why the shape changed before it was built, and the reason is the durable part

The entry asked for a table carrying *the authored value, the source's value, and whether the two are
opposed or merely different*. That shape names its authority in a **field** — `ClinSigConflict` really
did carry `clinvar: str` — and RM134 arrived in the same release with a second authority. Shipping the
first shape would have cost a key change or a retype one item later, and Principle 3 reserves both for
a major. Two items landing in one release is what caught it; either alone would not have.

So the parent row carries an agreement *state* instead of a pair of values, and *which* authority spoke
became data in the detail table. That is what makes the key stable at any N.

### The stress test, and why one field could not have held it

A single vocabulary was drafted with seven outcomes and failed at five authorities: its members named
the authority inside themselves (`clinvar_only`, `pubmind_only`), so a third source needed a third
member and five needed every subset. The root cause was one field carrying two axes — *do the
authorities agree with each other* and *where does the module's own call sit* — with `concordant`
defined as "both agree **and** the authored row agrees with them" and `authored_dissents` as a sibling
member. That is the Principle 5 anti-pattern and the combinatorial growth was its symptom. Split, both
vocabularies are five members at two authorities and five at five.

### Nothing resolves a split, and that is a decision rather than an omission

At five authorities with a declared order E>B>D>C>A, suppose E and A agree and B, C and D agree against
them. Lexicographic resolution says E; majority says B/C/D; choosing between those rules is a judgement
about how authority rank trades against agreement count, and it needs a weighting model. This
workspace has refused to invent one three times — RM126's `should_rebuild` (*the same fact costs
consumers differently, so the decision is theirs and only the fact is ours*), `@clinsig-never-escalates`,
and RM16's PRS weights. So `authored_position` is a relation to the **set**: computable with no weights,
true at any topology, and the E+A case reads `discordant` + `matches_some` under either rule.

The same refusal one level down keeps confidence unnormalized. A gold-star count and a literature
miner's evidence-depth count are different instruments, and folding them into one number is three axes
in one field — so the detail row carries the published value with `confidence_unit` beside it, and the
model refuses a magnitude with no instrument named (`@weight-has-no-unit`, enforced rather than
documented).

### The lifetime, and the succession it promotes

**A conflict is a question and an `overrides.csv` row is the answer.** The record joined the overlay's
covered set, taking it from seven to eight, and it is in for a *different* reason from the other seven:
not because it carries hand-curation a re-derivation would destroy — it carries none and is rewritten
whole on every run — but because answering a contested subject is what an overlay row is. RM124's
vindication signal then works for free: when the archive catches up, the author's `suppress` stops
changing anything.

The paired detail table is **out**, by name, in the same equality test. The author answers the question;
they do not get to rewrite what an archive published, and an overlay over the detail table would let a
module ship ClinVar's name above a classification ClinVar never made.

The table's documentation and the warning both name `overrides.csv` and **never**
`provenance.json`'s `outranks`. The two are the same idea one table apart, 0.7 settled the overlap as a
dated succession in the overlay's favour, and steering a new author onto the side that survives 1.0
cost a sentence.

### Severity, and the one thing it must never become

Warning-tier in both modes, never escalating under `strict` (`@clinsig-never-escalates`). A
disagreement with an archive is a fact about the field, not a defect in the module: half the time the
archive is the stale side, and failing a build on one would have this format arbitrate a clinical
dispute.

The finding is **actionable rather than carried**, which inverts its neighbour
`verification_findings_recorded` and does so deliberately. Nothing an author writes moves a number
sitting in `verification.json`; a contested row is answered by writing an overlay row, and the count is
taken over the **post-overlay** table, so writing one clears the finding. `overlay_rows_suppressed`
reports the removal, so an answered conflict is visible rather than silent.

### Two things found while building it

**`opposed` is a tautology at one authority, and the record is what makes it stop being one.** The
two-way check only reports where both sides are opinionated and their camps differ, and
`pathogenic`/`benign` are the only two opinionated camps — so every conflict it reports is opposed by
construction, and `_clin_sig_detail`'s differing-but-not-opposed group has no producer today. Filed
rather than mended: the formatter lives in `enrich.py`, the group becomes reachable as soon as two
authorities can disagree while neither contradicts the module, and that is exactly what the record is
shaped for.

**Several vocabulary members are reachable by the classifier and not by today's producer** — `absent`
needs a subject the module makes no clinical claim about, and `none` needs every archive asked and
empty; neither is a contested subject, so neither is written. They are kept on the
`VALID_RSID_STATUS.withdrawn` precedent: a member is permanent within a major, so reserving one now is
free and adding one later is not. The classifier tests walk every topology at three and five
authorities and assert an equality against both vocabularies, which is where the members are exercised.

### Repairs rejected

- **Folding the conflict into the overlay as an evidence column.** A conflict nobody has answered has
  no overlay row to live on, so unanswered conflicts — the entire point — would have nowhere to be.
- **Escalation under `strict`, or auto-correction.** Out of scope on the reporter's own scoping and
  ours: a conflict is a question, and half the time the archive is the stale side.
- **A `majority` or consensus field.** The E+A case is the argument; precomputing it is
  `should_rebuild` wearing a different name, and it would publish a judgement as a fact.
- **A second significance map.** The check's whole output is a comparison of two normalizations, so a
  drift between two maps would report a disagreement with ourselves as a disagreement between two
  archives. `CLIN_SIG_CAMP` moved out of `clinical.py` rather than being copied, for the same reason
  one level up.
- **Writing a row for every compared subject.** A record of every agreement is a copy of the module's
  own `clin_sig` column with a second opinion attached, and the number of subjects compared is already
  published as the check's denominator.

## RM131 — the warnings channel says what each finding is, and whether an author can clear it

**Shipped in `just-dna-format` + `just-dna-compiler` on 2026-08-28**, with the deprecated DuckDB
resolver in `just-dna-enricher` brought along because its warnings land in the same published channel.
Both halves the proposal sequenced, in one release, because the audit is the cost and doing it twice is
what the sequencing existed to avoid.

**Severity** medium · **Status** ✅ shipped in 0.7 · **Owner** compiler ·
**Motivating case** S68 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

### What shipped

`compilation.carried` and `compilation.warnings_summary` beside `compilation.warnings`, which is
unchanged down to the byte — the same sentences in the same order, so nothing that greps a phrase
broke. `carried` is the subset **no edit to the spec directory can clear**; a consumer subtracts it to
get the actionable set. `warnings_summary` is `{code: count}` over `vocab.VALID_WARNING_CODES`, with the
values summing to `len(warnings)` so a reader can tell the digest is complete. The same three fields
are on `ValidationResult`, `CompilationResult` and `ClosureResult`, on every path including a failed
compile.

Sixty-eight codes, nine of them carried. `findings.CodedWarning` is a `str` subclass, so the transport
stayed `list[str]` and every de-duplication, extend and phrase-grep went untouched.
`sweep.compare_module` reports `carried_added` beside `actionable_added`, which is the discriminator
RM126's own comment said would land here.

### The three things worth not re-deriving

**The container was free and the vocabulary was the release**, which was the whole of the original
deferral and is answered rather than dismissed: the set was derived across every emission site in three
tiers, and the derivation rule is *one code, one remediation* — two sentences cleared by the same edit
share a member and the sentence says which cell, two cleared differently do not. So the weight-sign
pair is one code across `state` and `direction` (two axes under P5, one edit) and the five orphan fact
tables are one code, while a VCF pointer collision and an unselected element are two.

**The emission surface was larger than the entry's "~29 append sites and 16 returning helpers"**, and
the parts it missed are the parts that would have shipped unclassified: the `findings`/`messages`
collectors a survey of `.append` cannot see, two `.extend` sites reaching into the schema tier's
`measurement_shape_warnings`/`deprecation_warnings`, `validate_bins`, `overrides.apply_overrides`, and
the deprecated resolver in the *enricher*, whose warnings reach `manifest.compilation.warnings` like
everything else. Re-derive such a count; never trust the one in an entry.

**A `carried` list beside `warnings` was the right shape and a field on each finding was not**, but the
`str`-subclass transport that makes it cheap leaks the code at exactly two places, and both are
load-bearing: a pydantic field flattens the subclass (so `compile_module`/`close_module` seed from an
internal `_validate_spec` that returns the classified list beside the result), and any reformat returns
plain prose (so three prefixing sites go through `findings.restate`, which refuses an uncoded input
rather than inventing a code). Both are pinned by tests, and the second half of the guard is a run over
the whole reference corpus — a static walk proves every *site* names a code, and only a run proves every
*message that arrives* still carries one.

### What it did not do

**No cap, no truncation, no verbosity flag**, per the reporter and us: all three hide findings rather
than organising them, and the author with the most warnings is the one who most needs the hidden ones.
**No metainfo artifact** — the channel already ships and `artifact_digest` is a Merkle root over the
parquet `FileEntry` list, so `manifest.json` sits outside it and neither new field moved a hash on any
published module. **Codes were not derived from the pinned phrase catalogue** (partial by construction,
and a digest that silently omits findings is worse than none because the reader believes it) **nor from
the emission site** (a refactor then renames a published key — P3's rename arriving by the back door).

**`axes["warnings"]` still fires on any movement of the set**, deliberately: narrowing it would make a
published axis mean something other than what every record already written claims about it, and the axis
drives no rebuild. A pre-0.7 manifest reports every addition as actionable, which is the safe direction —
calling an unrecorded finding carried would tell a reader that something fixable is not.

### The suppression record it carried in (RM124 × RM131)

A row removed by a `suppress` was invisible in the build product: absent, with no trace of why, and a
consumer holding the compiled bytes has no `overrides.csv` to read. It now reports one line per
**reason** with a count — which is what `reason` being a required column buys — and the count is over
the *overlay's* rows, never over the rows removed. That is not tidiness: after `reverse_module` the
derived table is already post-overlay, so an effect-based count would say a number on lap 1 and vanish
on lap 2, making a module disagree with its own round trip on a published field. Proved against the real
compile → reverse → compile path. Classified **actionable** rather than carried, because the author owns
the overlay and deleting the row clears it.

The three candidate derivations are argued at length in
[PROPOSAL_0_7 § RM131](proposals/PROPOSAL_0_7.md#rm131--warnings-is-a-flat-liststr-and-the-discriminator-that-would-make-it-readable-is-discarded),
which is where the decision was taken; the entry this replaces lived in ROADMAP.md and not in
ROADMAP_0_7, so there is no second copy to keep in step.

## RM124 — an author's correction to a derived table now has somewhere to live

**Shipped in `just-dna-format` + `just-dna-compiler` + `just-dna-enricher` on 2026-08-28**, as
`overrides.csv` — a new optional authored table, additive under Principles 3 and 8, so no published
module's `content_signature` or `artifact.digest` moves. It is the keystone of the 0.7 round: RM83
closes into it, RM130 was blocked on one of its questions, and RM128's central ask thins because of it.

**What it discharges.** The 2026-08-12 cost amendment names the class in its own words — *a derived
table that is both machine-written and human-overridable can be edited into a state that is not merely
stale but a false claim, which wants a mechanism rather than a convention.* RM45 discharged that for
exactly one table by making `verification.json` unwritable by hand. Nothing discharged it for the seven
where overriding **is** the intended feature, and their merge-not-clobber rule meant that re-deriving
one required deleting it, which discarded every hand-curated row in it.

**The covered set is seven, and the number is a correction.** The proposal says "the six covered
derived tables" and never enumerates them; the roadmap entry it inherits the number from does not
either. The maintainer settled it on 2026-08-28 as every merge-not-clobber derived sidecar —
`resolution.csv`, `frequencies.csv`, `gene_metrics.csv`, `gene_validity.csv`,
`clinical_assertions.csv`, `literature.csv`, `gwas_effects.csv` — with `sources.csv` / `licensing.csv`
outside it, because it has its own merge path and is the one derived table the schema tells a human to
write. `overrides.OVERRIDABLE_TABLES` is the registry and a test asserts the equality against the
compiler's own table tuples rather than a floor.

**Three decisions worth not re-deriving**, all of them recorded in
[SCHEMAS § the authored overlay](SCHEMAS.md#the-authored-overlay-07-rm124--overridescsv):

- **One `member` column, whose meaning the named table fixes**, rather than a per-table key grammar —
  which is a rule every consumer would re-derive, differently. An empty `member` on a grouped table is
  group-scoped for `update` and refused for `suppress` (not recoverable by reading the result) and for
  `insert` (the row it would create carries no member value, so nothing could match it again).
- **No `previous_value` column.** `reverse_module` emits the post-overlay derived table plus the
  overlay, so the overlay applies twice; all three operations are idempotent set operations, so the
  second lap is a fixed point, checked by test rather than assumed. The alternative would put a derived
  cell inside an authored table, which rots the moment the source moves.
- **No operation reports its own no-op**, and that is forced rather than tidy: after a reverse, all
  three no-ops are true of a healthy module, so reporting any of them would make a module and its own
  round trip disagree on `manifest.compilation.warnings`. The price is stated rather than hidden — a
  `suppress` with a typo'd subject does nothing, forever, and cannot warn.

**Merge-not-clobber's behaviour is unchanged and its cost is gone.** A re-run still gap-fills rather
than re-asking every subject — re-asking was explicitly rejected, since it would put the full
resolution time on every pass. What changed is that a recorded row now carries no authored content, so
leaving it alone risks nothing and a full re-derivation (`rm` plus a re-run) is free. The seven writers'
docstrings say so where a reader outside this repo actually meets them, in the same commit as the
behaviour.

**The `outranks` overlap is a dated succession rather than a merge.** Both mechanisms stand in 0.7, the
duplication is stated in SCHEMAS, and the unification is [RM135](ROADMAP.md#rm135--provenanceitemoutranks-is-superseded-by-the-overlay-and-one-of-them-has-to-go)
on the 1.0 tracker. 0.7 emits no deprecation warning, which is P3 rather than caution: an author warned
off `outranks` has nowhere to go until the overlay reaches authored tables.

**Coordination.** `just-dna-registry` rebuilds a spec directory from `RECOGNIZED_SPEC_FILES`, a
hand-kept mirror of our table constants, and a name missing there is a file dropped on re-publish —
which is how `licensing.csv` was lost before their 0.16.2. `overrides.csv` needs one entry added there;
it is recorded in [INTEGRATION_0_6.md](history/INTEGRATION_0_6.md) rather than left to be discovered.

## RM128 — `enrich()` persisted nothing until its tail, so a run killed at minute 29 had written nothing

**Shipped in `just-dna-enricher` on 2026-08-28**, as `just_dna_enricher.transaction` plus three
keyword arguments on `enrich()` and two flags on the command. Additive: no schema, no manifest field,
no vocabulary. **Motivating case** S66 (just-module-creator).

**The truncation half was already closed** on 2026-08-24 — nine sidecar writers go through
`layout.atomic_writer`, so a killed process leaves the previous table rather than a short one. What
this entry records is the three asks beside it, each of which was a decision rather than a missing
line.

**The central ask dissolved rather than being argued down.** It was filed as incremental or
checkpointed persistence, and it turned on a question nobody had written down: *is a `strict` refusal
allowed to leave rows behind?* The choice looked like **keep the promise or recover the thirty
minutes**. It is not a choice. The run becomes a **transaction**, which keeps the promise absolutely
and recovers the work as well.

- **Durable staging beside the target, plus an atomic commit at the gate.** Each live link's answer is
  staged to `.<name>.staging/answers.csv` beside `resolution.csv` as it arrives; the table is still
  written once, at the bottom, by a writer that renames into place. `layout.atomic_writer` already
  staged exactly there, so this extends a shipped primitive from one file to a whole run rather than
  inventing one.
- **Same-directory staging is the correctness condition, not a convenience.** A rename within one
  filesystem is atomic; `shutil.move` across a partition degrades to copy-then-delete and is not.
  Staging beside the target makes a cross-device move structurally impossible rather than merely
  avoided, which is why the test asserts the sibling relationship structurally.
- **What is staged is the answer, never the row.** Everything downstream of an answer recomputes —
  the hosting filter, the pseudoautosomal selection, `locus_index`, the minted ids — so a flag that
  changed between the kill and the resume changes the table exactly as it would have, and the journal
  cannot carry a stale derivation. It is seeded **between the caches and the live links**, so a
  snapshot provisioned in between still wins the variant it would have won on a first run.
- **Only positive answers are staged.** A failed request is unchecked rather than absent
  (`@unreachable-not-absent`), and freezing one into the journal would make a transient outage
  permanent on every future run. And a staged answer is honoured **only if the link that produced it
  would run this time**: the seeding reads the same two booleans that gate the live blocks, so a
  `--no-gnomad` or `--offline` resume drops that link's answers rather than stamping a row a first run
  with those flags could never have written — `alts` is a fact column, so the alternative would move
  the compiled digest.
- **The gate commits**, so *a refused `strict` run changes nothing* became a written promise instead
  of an accident of statement order — the item's actual question, answered in the direction that
  breaks nothing. The test asserts it on the bytes of a pre-existing table, not on a return value.
- **`--keep-staging` keeps the staged answers after a successful commit**, for debugging; the default
  removes them, and both values are exercised.
- **Not mode-conditional**, as the entry refused in advance: `write=True` meaning "at the end" under
  `strict` and "as we go" under `best_effort` is a flag that does not mean the same thing in every
  function that takes one. Under a transaction it does, because committing is the only write, and
  `write=False` stages nothing and takes no lock — with nothing written there is no window to exclude.

**RM124 thins what the promise has to protect**, and the two were reached independently. What a
staged, uncommitted table can contain is now provably machine-derived and never an authored value,
because the author's corrections live in the overlay.

### The lock, and why it is `flock`

The transaction does not close the concurrency window: two runs can each stage and each commit, last
writer winning over a merge with neither knowing. The reported incident is the sharp form — a
client-side kill did not stop the worker, a zombie run reached the write and overwrote a restored
330-row table with 162 rows, and the module then validated, closed and compiled green. Nothing
downstream could see it, because the three branches that deliberately write **no row** for an
unanswerable subject make a shorter table indistinguishable from a module whose author resolved less.
Those branches are correct and were not in scope.

`flock` on the spec directory's own descriptor, non-blocking, **no lockfile**. A lockfile left by
exactly the kill this item is about would block every subsequent run — a worse unattended failure than
the one it prevents — and the staleness rule that would fix it is a clock, which this repo has refused
before (*guard the plan, not the clock*). `flock` dies with the process, so there is nothing to expire.
Non-blocking because a run silently waiting half an hour behind a zombie is its own unattended failure,
and the refusal is accurate by construction: the lock is only ever held by a live process.

**The degradation is documented rather than silent, which the design explicitly owed.** No `fcntl` on
a non-POSIX platform, or a filesystem answering `ENOLCK`/`EOPNOTSUPP`, logs that the run is **not**
excluded from a concurrent one and carries on. Both branches are reached by tests — an unreached
refusal branch is not an API, which the wave-1 audit had just demonstrated. **`flock` is untested here
on the network filesystems a consumer may use**, and ENRICHER says so where a consumer meets it.

### The progress unit, argued rather than guessed

`progress: Callable[[int, int], None] | None = None`, reporting `(done, total)` over **subjects**. The
entry filed this rather than shipping it because the resolver chain is batched inside `resolver.py`
rather than being a per-subject loop, so the unit reported is a design choice — and a leaf shipped
against a guess is one Principle 3 keeps working forever.

- **The incident is an idle timeout.** Both reported runs died at 1800 s with essentially every
  variant resolved, so what the caller needs first is a keepalive with monotonic progress — which
  rules out **phases**, since a 29-minute phase emits nothing and the timeout fires anyway.
- **`total` must be known up front** for the number to mean anything to a caller rendering it. The
  subject count is; the link count is not, since it depends on what resolution finds.
- **Subjects are the only unit the author's mental model already has.** Links are an implementation
  detail of the batched resolver, and publishing one would make a refactor of `resolver.py` a contract
  change — the rename P3 forbids arriving through the back door.

No protocol was added, because none was asked for: two integers, no object, no event vocabulary to
keep working forever. Monotonicity is structural — `done` is the size of a set that only grows — and
the assembly loop touches every subject, so the last report is always `(total, total)`.

### `enrich --rederive` — RM83's residue, and it composes rather than adds

A full re-derivation that keeps a baseline reports what moved, which is MODULE_LIFECYCLE § 5.1's
canary performed. It composes with the transaction: the recorded table is still in memory and the
fresh one has not been committed, so both sides exist at the commit boundary and the comparison is
free. The comparison is over `RESOLUTION_FACT_FIELDS`, read off the registry rather than restated,
because the provenance columns move on every run by design.

- **`None` is not `[]`.** `None` says nobody re-derived; `[]` says every recorded subject was re-asked
  and every one still answers the same. Only a real difference prints — a comparison whose empty
  result is the normal case must not announce a zero as though it were evidence.
- **A recorded subject the run could not ask about keeps its recorded rows**, and the carry-forward
  warns naming them. Without it, an offline `--rederive` would replace a full table with an empty one:
  the reported incident wearing a new flag, and the sharpest test in the unit. Answered-and-absent is
  an answer and does replace (it writes a `not_found` row); could-not-ask is not.
- **A re-derivation resumes only another re-derivation.** After a gap-filling run commits, its staged
  answers are exactly what produced the recorded table, so seeding them would compare that table
  against its own provenance and report a clean bill for precisely the subjects being re-checked —
  the canary silenced by a file left behind for debugging. The journal records which run wrote each
  row; the reverse direction is allowed, because an answer a re-derivation obtained is still an answer.
- **The honest limit is stated rather than hidden.** `rm resolution.csv` plus a re-run re-derives just
  as correctly and reports **nothing**, because it destroys the old values before the fresh ones
  arrive and nothing holds both sides.

**Repairs rejected**, kept because each looks obvious from the headline: a `--refresh` command (RM83's
three open questions were all answered elsewhere, leaving a mode on the command that already does the
derivation); a diffs file or table, or a proposed table beside the current one (version control with no
consumer, beside the version control the author already has); a pass that *applies* the newer value
(rewriting an authored or curator-set cell destroys the evidence of the upstream change — still the
rule, and the overlay does not soften it); and re-asking every subject on **every** run (dropping
merge-not-clobber did not mean that, and reading it that way would put the full resolution time on
every pass to buy drift detection nobody asked to run continuously).

### Charter check

P2 — enricher-only; the compile path imports none of it. P3 — three keyword arguments with defaults, a
staging directory and a new module are additive; no schema, no manifest field, no vocabulary. P7 — a
committed run produces the table an uninterrupted run produces, which the resume path proves by test.

## RM83 — a derived sidecar can only be refreshed by deleting it, which discards the overrides it exists to hold

**Closed, not shipped, on 2026-08-28**, in the commit that landed RM124 and not before — a closure
recorded against an unlanded dependency is the kind of bookkeeping that makes a ledger untrustworthy.
**Dissolved rather than argued down**: the premise stopped holding.

The entry named a missing operation, a `--refresh` that re-asks the source about recorded rows and
reports the difference, and it had two halves. **The refresh half stops existing** — its problem was
that re-deriving a sidecar means deleting it and losing the curator's rows, and once the derived files
are pure build products with the corrections in the overlay there is nothing inside a sidecar to
preserve, so `rm` costs nothing and needs no command wrapped around it to be safe. **The drift half
stops being unperformable** — merge-not-clobber meant a re-run never re-asked about a recorded row, so
a source that silently *revised* an answer moved no `fetched_at`, no fact signature and no digest,
making MODULE_LIFECYCLE § 5.1's canary an instrument that could not fire, because detecting drift *was*
the delete-and-re-derive that discarded the overrides. With the discard harmless, a full re-derivation
is an ordinary operation and the canary fires from it.

**The blocking question is answered rather than deferred.** The entry named it: on most sidecars
nothing records that a row was overridden, so "re-derive the machine rows and keep the overrides" was
not implementable, because the tier could not tell a curator's edit from what the source said last
time. Under the overlay the tier never has to — the edit is recorded by construction and the derived
row carries no authored content at all.

**Nothing named in the entry is built.** No `--refresh` command, no proposed table beside the current
one, no diffs file. What remains is a residue and it is a flag rather than a command: `enrich
--rederive`, which stages a fresh table beside the current one and commits by rename (composing with
RM128's transaction), so both files exist at the commit boundary and the report of what moved is free.
The honest limit is stated with it — `rm` followed by a re-run destroys the old values before the fresh
ones arrive, so that path re-derives silently and correctly and no report is possible.

**Repairs rejected**, kept because each looks obvious from the headline: a diffs file or table tracking
what moved between passes (version control with no consumer, beside the version control the author
already has, over a file now regenerable from source plus overlay); a pass that *applies* the newer
value (rewriting a curator-set cell destroys the evidence of the upstream change — still the rule, and
the overlay does not soften it: an overlay row is the author's answer to a difference, never the
tier's); and re-asking every subject on every run (dropping merge-not-clobber does not mean this, and
reading it that way would put the full resolution time on every pass to buy drift detection nobody
asked to run continuously).
## RM132 — `pharm_variants.csv` made a clinical claim per row and could only cite per variant

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm132--pharm_variantscsv-makes-a-clinical-claim-per-row-and-cites-per-variant) on 2026-08-28 — SHIPPED in 0.7.** `PharmVariantRow.pmid` plus both literature cross-check sites in the same release; `provenance_quote` did **not** follow, stated rather than implied.

**Severity** medium · **Status** ✅ shipped in 0.7 · **Owner** format (schema) + compiler + enricher ·
**Motivating case** S73 (just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

### What was observed

A ClinPGx-drafted module carried **1,482** drug-response rows and had nowhere to ground any of them:
sixteen model fields, thirteen authored, none a PMID or DOI. The reporter asked which of three
provenance models was intended, worked out that none of them held, and declined to build on any.

**The tree had already answered it one release earlier.** RM47 decided this shape for a structurally
identical table, and the rule underneath generalizes: **a row cites when its claim is finer-grained
than `studies.csv`'s key.** `studies.csv` keys on `(variant_key, pmid)`, so a study row attaches to a
*variant*; `pharm_variants.csv` keys on `(variant_key, drug, genotype, phenotype_category,
annotation_id)`, so one study row would attach the paper to every drug, genotype and phenotype
category recorded for that variant at once. `evidence_level` is not the provenance handle — it points
at somebody else's *grading of* the evidence rather than at the evidence — and the licence row's
`source`/`dataset` state redistribution terms rather than grounding a claim.

### Why a full-cost authored column was taken rather than deferred

This is the item the round's sort rule turns on, so the argument is kept rather than assumed.

**What P9 prices is not the byte.** An authored column is full cost because a human must learn it and
P3 keeps it working forever, so the risk being priced is *getting the shape wrong* — and that risk was
spent a release ago. The column is a copy of two shipped fields under one grammar, so an author who
has met either learns nothing new. Demand fixes an *unfixed* shape; there was none left here for
demand to fix.

**It is closer to a half-defect than to a new capability.** The table already made a clinical claim
per genotype and structurally could not ground one. That is a hole in an existing concern rather than
a new concern added to a table, which is the distinction the *one concern per table* gate turns on.

### What was built

`PharmVariantRow.pmid`, optional and free-form, validated by `spec.validate_pmid_cell` — the one
grammar every citation pointer in the schema routes through, so the PMCID diagnosis and the
`[PMID: N]` spelling come with it and cannot drift. No compiler change was needed for the column
itself: the parquet materializer and the reverse writer both derive their column lists from the model.

**Both cross-check sites learned the site in the same release**, which is the half that made this a
piece of work rather than a column, and is RM47's recorded lesson in its own words — *shipping the
column without both would be evidence the format never checks, which is worse than the gap.*
`_cross_check_literature` (with `split_cited_literature` and `_check_quote_counter_is_current`
beneath it) and the enricher's `enrich_literature` both read it. Since RM79 the orphan finding has
teeth: blind to the new site, the compiler would not merely report a pharm-grounded citation as stale,
it would **discard** the literature row the claim's evidence lives in.

**The roster is derived, which is the part that generalizes.** Rather than a third hand-kept list,
`_CITING_TABLE_KINDS` is every `_TABLE_KINDS` model declaring a `pmid`, and the new public
`load_citing_rows` / `table_citations` walk it. The enricher reads through that pair — the RM40/RM41
requirement, met structurally: a test walks the enricher's own source with `ast` and asserts no citing
CSV name appears in a string constant there, so the next kind to declare the column is read by both
tiers with no edit to either. `load_binning_rows` / `binning_citations` stay and stay narrow; a caller
asking for the binning kinds is asking about thresholds, not about the citations a module makes.

One warning text moved with it — `literature_row_uncited` now reads *"no study, bin or pharm row in
this module cites"*. The code is the stable handle and did not change; the phrase is pinned by four
tests, which is what makes each rewording a deliberate act.

### The open question, answered

**`provenance_quote` does not follow, and the release says so rather than leaving it implied.** The
binning side drew the same line deliberately: the row cites, and `studies.csv`/`literature.csv`
describe. That is what stops `StudyRow`'s whole provenance column set — population, `p_value_num`,
`effect_size`, `provenance_quote`, `curator` — migrating onto a citing row one column at a time. A
1,482-row body of clinical claims is exactly where somebody asks next, which is the reason to state
the line rather than the reason to cross it. The consequence is carried in the code too: a pharm row
cites and cannot quote, so it contributes a denominator of **zero** to the quote-counter check rather
than being skipped, or a literature row reachable only from a pharm row would read as cited by
nothing.

### Repairs refused

- **Widening `studies.csv`'s key.** The repair that looks obvious and the one RM47 already refused: it
  would make a study row's subject depend on which table read it.
- **Treating `evidence_level` as the provenance handle.** It grades evidence rather than pointing at
  it, and the two now sit side by side in the model so the distinction stays visible (P5).
- **A second table roster in the enricher.** The RM40/RM41 shape, and a list that goes stale the next
  time a model declares the column.
- **A grounding warning for an uncited pharm row.** `_check_binning_grounding` exists for the
  interpretive-threshold case — where a boundary is a clinical judgement with nothing behind it — and
  a drug-response table is not that case. Adding one would have fired on every ClinPGx draft.

### Charter check

P3 — a new optional column, additive; no published module is invalidated. P5 — citation and grading
are separate axes on separate columns. P7 — the round trip is asserted on the `pharm_variants.parquet`
bytes as well as on `content_signature` and `artifact.digest`. P8 — optional with respect to every
published module, proved by running it: a spec with no `pmid` header hashes equal to the same spec
carrying the header with every cell empty. P9 — full cost, taken with the argument above rather than
by weighing file count.

## RM70 — `requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm70--requires_callable-is-variantrow-only-so-no-pgx-table-can-state-cpics-core-assumption) on 2026-08-28 — BUILDS in 0.7.** `requires_callable` on `HaplotypeRow` and `PharmVariantRow`, not on `DiplotypeRow`; `callable_from` does not travel with them.

**Severity** medium · **Status** SHIPPED in 0.7 — optional `requires_callable` on `HaplotypeRow` and
`PharmVariantRow`, not on `DiplotypeRow`, and `callable_from` did not travel · **Owner** format (schema)
· **Found by** dogfooding on 2026-08-13, `reference_examples/cyp2c9_warfarin_grch37/`

### What was observed

CPIC's star-allele system assumes that a position not called is reference — that is literally
`requires_callable=false` — and `haplotypes.csv`, `pharm_variants.csv` and `diplotypes.csv` carry no such
column. `requires_callable` and its companion `callable_from` are on `VariantRow` alone. So a
star-allele module cannot record whether its call needed the defining positions to be callable, which is
the single assumption a consumer most needs to know before trusting a `*1/*1` result.

The corpus shows both sides of it. D6 confirmed RM57's inversion warning fires correctly on the row type
it exists for: a `requires_callable=true` row with `quality_from=QUAL, min_quality=30` warns, cites VCF
§1.6.1.6, and names GQ and MIN_DP as the fix. D2 could not exercise it at all, because a PGx module has
no `variants.csv` — the check and the column are unreachable from the module kind whose upstream states
the assumption in prose.

### What was built

The two columns as decided, and nothing else. The parquet schema and the reverse writer both derive
their column lists from the model, so no compiler change was needed — `_polars_type` maps `bool | None`
to a nullable `pl.Boolean` and `_scalar_cell` already rendered `None` and `False` as `""` and `"false"`.
That was proven rather than assumed: a temporary mutation collapsing an authored `False` into a blank
cell was run against the round-trip test first, and it failed on both tables.

`reference_examples/cyp2c9_warfarin_grch37`, the module the gap was found against, now populates the
column and exercises all three states. `haplotypes.csv` records CPIC's assumption verbatim (`false` on
both defining SNPs). `pharm_variants.csv` is keyed on genotype and so splits: the reference-homozygote
rows carry `true`, because a variant-only callset emits no record for them and absence is not the call;
the rows naming an alternate allele carry `false`; and the twelve rows whose reference allele the
module's own `resolution.csv` never named are left **blank** rather than guessed. That answers the PGx
half of the consumer ask for `requires_callable` *"populated somewhere real, to try the round trip
against"*. The module was re-closed, so its attestation binds the edited bytes.

**No cross-table equality check, and the reason is not cost.** `haplotypes.csv` and
`pharm_variants.csv` can name one locus and legitimately disagree: a haplotype row's claim is about
assigning the *reference haplotype* there, and a pharm row's is about matching *that row's genotype*.
The fixture holds exactly this shape — a haplotype default-to-reference (`false`) beside a
reference-homozygote genotype needing a proof (`true`) — so a checker asserting the two agree would
refuse a correct module. Both field descriptions say what each claim is about, and a test compiles the
disagreeing pair clean so the check is not added later.

### Cost, priced honestly

`requires_callable` is an **authored** column, which is full cost under the 0.6 charter amendment — the
most expensive kind of addition this format makes, on the layer the rare human writes. That is the
reason the item is filed rather than done, and it is also why the scoping question below is not a
detail: covering three tables and covering the two that name a position are different prices for the
same capability, and the difference is a column on the table a human writes.

### Candidate repairs, and why each is wrong

- **Copy the column onto all three PGx tables.** Full cost, three times, and wrong on the third.
  `haplotypes.csv` and `pharm_variants.csv` name loci — they are two of RM43's three positional tables —
  so a callability claim on either is about a position the row states, which is exactly what the column
  means on `VariantRow`. `diplotypes.csv` names a star-allele *pair*, not a locus, so the same column
  there could only mean "the variants defining these two haplotypes were callable" — a fact about
  `haplotypes.csv`'s rows, restated one table over where it drifts the moment a definition is edited.
  One concept, one home (P5).
- **Declare it once in `module_spec.yaml`.** The verdict is per locus, and this repo has twice paid for
  assuming otherwise: RM36 rejected per-CSV build declaration because two files could disagree about one
  fact, and RM32 rejected a gene-scoped PAR verdict because XG and SPRY3 straddle a boundary. CPIC's own
  assumption is not uniform either — a gene whose common alleles are single SNPs and one defined partly
  by a structural event do not have the same callability requirement, and CYP2D6 has both inside one
  gene.
- **Derive it from `callable_from`.** There is no `callable_from` on the PGx tables either, so this
  starts by adding the more expensive of the two columns. It is also an axis overload: `callable_from`
  says *where the proof lives*, `requires_callable` says *a proof is required*, and a row may
  legitimately require one and not know where the evidence is. Deriving requiredness from the presence
  of a pointer collapses two questions into one column.
- **A stamped, compiler-managed parquet column.** Nearly free under the amendment, and it cannot work:
  this is a curator's claim about what the annotation assumes, so there is nothing for the compiler to
  compute. A stamped column carries only what the compiler derives.
- **Author the defining positions a second time in `variants.csv`.** Two tables then name one locus, and
  `variants.csv` alone carries `alts` as a resolution fact, so the shadow rows move `artifact.digest`
  while asserting nothing new — and it re-opens *a star allele can be used without being defined* from
  the other end, with two definitions instead of none.

### Is it gated on the same thing as RM65/RM66?

**No, and the difference is the useful part of this entry.** RM65 and RM66 wait on a real repeat-caller
or CNV VCF because the open question there is what a *caller emits* — the shape of the data decides the
schema. This question is about what a *curator asserts*, and the assertion already exists in prose: CPIC
states it. A PGx caller VCF would say nothing about which of three tables should carry a curator's
claim. The adjacency the ledger records is that both ask whether a non-`variants.csv` table should carry
something `variants.csv` has, not that they share a blocker.

**What unblocked it:** the entry's own closing reading, put to the maintainer and taken as written —
*two* optional columns, on `HaplotypeRow` and `PharmVariantRow`, the PGx tables that name a position,
and **not** on `DiplotypeRow`. The second question the entry left open, whether `callable_from` travels
with them, was answered the cheap way: it does not, and it is added when a module needs to say where the
proof lives. What the entry got wrong is the other half of its unblocker — it also asked for *a real
module whose author wants to state it*, and the module was already in the corpus. The one this was found
against is the one that now states it.

# The 2026-08-24 consumer round (S63–S74)

Twelve items from two reporters, triaged in one pass. The per-item record is in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md); what is here is the reasoning
behind each `RMn` the round produced.

## RM129 — `producer` described the document and was read as describing the checks

**Shipped in `just-dna-format` + `just-dna-enricher` on 2026-08-24**, a minor. `verification.json`
carried `producer` at the document level only, and `record_verification` refills it from
`producer_label()` on every write — so a merge that correctly **kept** an older run's record
restamped that record's attribution to the writing release. Reported against a module carrying a
0.6.4 `clinical_significance` record that came back attributed to 0.6.6.

**The reporter's argument is the item and it is an argument from the other fields.** Every field
describing *one piece of work* was already on the record — `source` (which authority answered),
`release` (which snapshot), `checked_at` (when) — and `producer`, naming *who ran it*, was the only
one on the document. Once the list is written out that way the asymmetry reads as an oversight rather
than a design, and the fix is where the field goes rather than what it says.

**`produced_at` stays on the document and is correct there**, which is the discriminator worth
keeping: it genuinely describes the file's last write, and so does `producer` **under its new
reading**. The two are now a pair meaning *what last wrote this file*, and the per-record field means
*who put this check*. `Verification.producer`'s own description had said *"Tool and version that put
the checks"* — the false claim, sitting in the printed contract where `describe`/`reference` render it
verbatim — and correcting it was part of the fix, not a follow-up (`@field-description-is-a-claim`).

**Three obligations a new field on a fact-hashed record owes, discharged rather than assumed.**
`producer` is outside `VERIFICATION_FACT_FIELDS` on exactly the reasoning that excluded `checked_at`
(*who* ran a check is a fact about the run, not about the module), so no published
`verification.signature` moved — asserted by a test rather than reasoned about. It is `str | None`
defaulting to `None`, so a record written before the field existed reads as *not recorded*; defaulting it to the
reading version would manufacture the false attribution the item is about, which is the tri-state rule
applied to a provenance field. And `merge_records` carries whole records, so the value travels with
no change to the merge — pinned by a test that hand-builds a 0.6.4 record, merges over it, and asserts
the old attribution survives.

**What was not changed: the merge.** The reporter went out of their way to record that
`merge_records` did the right thing — RM72's rule that a fresh *skip* does not displace an earlier
*answer* held, and nothing was lost. That mattered to the triage: a report framed as "the merge is
broken" would have aimed the repair at the one part that was correct.


# The 2026-08-21 output-contract round — what a patch may change about a compiled artifact

One report from a new consumer, just-dna-registry ([S62](CONSUMER_SUGGESTIONS_HISTORY.md)), and the
two items it produced are open in [ROADMAP.md](ROADMAP.md). What belongs here is **a framing that was
filed and then withdrawn the same day**, kept because the withdrawn version is the more tempting one
and will be re-proposed by anyone who reads only the measurement.

**RM127 was first filed as *the release-class table and the release practice disagree*.** The argument
ran: our table sizes a new optional column as a **minor**; `StudyRow.curator` shipped in **0.6.5**, a
patch, and the cut's own entry names it (*"Additive only: one new authored column"*); so the rule we
state and the rule we practise disagree and one of them must give. Three candidates were recorded —
the table is right and 0.6.5 was mis-sized; the practice is right and both documents should say *a
change that moves no authored identity may take a patch*; or split the axis so authored surface sizes
the release and derived surface does not.

**It was withdrawn because it indicts the wrong release.** `curator` is additive, no already-published
module can carry it, and **no stored value became wrong** — the only consequence is that a recompile
writes different bytes, which P4 already declines to guarantee across compiler versions. Sizing it as
a patch is defensible; the table calling it a minor is the table being strict, not the cut being
wrong. Chasing that disagreement would have produced a rule change that fixed nothing the consumer
reported.

**The defect is RM121, and it is a change class the taxonomy does not have** — an existing published
field whose *derivation was corrected*, so the same spec yields a different value. Neither additive nor
a removal/retype. And because a corrected derivation is a **bug fix**, deferring it to a minor means
knowingly serving a wrong value meanwhile, so no release-class scheme can carry it: the version number
answers *is the code contract compatible*, never *are your stored outputs stale*. The two axes have to
be separated rather than reconciled, which dissolves all three original candidates instead of choosing
among them. The rewritten entry is
[RM127](#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one).

**The lesson worth keeping is the tautology.** The safety argument for RM121 was *`content_signature`
is unchanged, measured* — true, and incapable of being false, because `stats` sits outside
`content_signature` by design. A check that cannot fail was read as a pass (`@tautology-zero`), one
level up from where that rule is usually applied. The same property has a second edge: a field outside
identity is a field no digest, no signature and no `revalidate` can see move, so **the cheapest changes
to make are exactly the ones with no detection channel.** Measured across 0.6.1→0.6.6: six of sixteen
reference examples changed a published, indexed manifest field with *both* hashes byte-identical.


## RM127 — a corrected derivation has no release class, and the version number is the wrong place to carry one

✅ **Severity** medium · **Status** **CLOSED 2026-08-21 — the charter was amended the same day it was
filed**, which is the whole item; filed, rewritten and answered within one pass · **Owner** maintainer
· **Motivating case** [S62](CONSUMER_SUGGESTIONS_HISTORY.md) (just-dna-registry)

**What shipped.** Principle 3 gained two rules — *Release class and artifact staleness are different
axes* and *Authored identity is not the sizing test* — and the charter gained a **Rules only** header
item plus Principle 9, the cost-by-layer pricing promoted out of an amendment entry where it had been
the only rule stated nowhere else. The reasoning moved to `CONSTITUTION_AMENDMENTS_HISTORY.md`, a new
file, and the charter came out **11.5% smaller while gaining three rules**. The obligation the
amendment creates — a release declares its corrections — is owed by
[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output),
queued for 0.7, and until it is built the charter names a channel that does not exist.

**This entry was first filed as *the release table and the practice disagree*, and that was aimed at
the wrong target.** The original framing indicted `StudyRow.curator` shipping in 0.6.5. It should not
have: `curator` is additive, no already-published module can carry it, no stored value became wrong,
and the only consequence is that a recompile writes different bytes — which P4 already declines to
guarantee across compiler versions. Sizing it as a patch is defensible, and the table calling it a
minor is the table being strict rather than the cut being wrong. The original text is preserved in
[the 2026-08-21 output-contract round](#the-2026-08-21-output-contract-round--what-a-patch-may-change-about-a-compiled-artifact).

**The real item is RM121, and it is a change class the taxonomy does not have.** `stats.genes` is an
*existing published field whose derivation was corrected* — the same spec now yields a different
value. Nothing was added, removed, promoted or retyped. The three rows we have are *additive → minor*,
*legibility → patch*, *removal/promotion/retype → major*, and a corrected derivation is in none of
them. It did not fall between two rules; it fell outside the list.

**Why it read as safe, and this is the mechanism.** The only test applied was *does authored identity
move?* But `stats` sits outside `content_signature` **by design** — it is a derived facet, not
content. So that test returns "safe" for *any* change to `stats` whatsoever, including replacing it
with nonsense. It cannot fail there. It was not evidence; it was a tautology, and `@tautology-zero` is
our own name for the shape — *a check that cannot fail must not report a zero*. RM123 shipped that
same week about compile checks; the identical error was made one level up, in the release-sizing
argument, where nothing was watching for it.

**And the structural half.** The property that makes a derived field cheap to change is the same
property that makes the change undetectable downstream. `stats` is outside identity, so changing it
costs nothing by the identity test *and* no digest, no signature and no `revalidate` can see it move.
**Measured: six of sixteen reference examples changed a published, indexed manifest field while both
hashes stayed byte-identical.** The cheapest changes to make are exactly the ones with no detection
channel, and the identity test rewards them.

**The version number cannot carry this, and the reason closes the original question rather than
answering it.** A corrected derivation is a **bug fix**. Deferring it to the next minor means
knowingly serving a wrong value for an undefined period, which is not a trade anybody should take —
so "make it a minor" is not available, and neither is any other scheme that encodes staleness in the
release class. SemVer answers *is the code contract compatible*; it was never designed to answer *are
your stored outputs stale*, and those are orthogonal. **They must be separated rather than reconciled**
— which dissolves this entry's original three candidates instead of picking one.

**What is left here is one charter question**, and it is the maintainer's: does P3's sentence — *"a new
optional column… lands in a minor: the authored identity is unchanged, and only a recompile's
`artifact.digest` moves"* — get amended to say that release class and artifact staleness are different
axes, with the second carried by the mechanism in
[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)? The sentence
currently states a ruling and, in the same breath, offers the identity test as its rationale — which
is exactly the reading that sized RM121, so leaving it unamended leaves the trap armed. Everything
else RM127 used to ask now belongs to RM126.


# The 2026-08-21 decision round — six undecided minors answered in one pass

[ROADMAP.md § Active items](ROADMAP.md#active-items) held six items whose common property was that
every one of them was a *decision* rather than a missing line of code, and none had been made. All six
were answered in a single pass on 2026-08-21. Four stayed open with their shape settled or narrowed and
are still in the active file (RM103's manifest half, RM108, RM110, RM117); **RM122** parked on demand
and moved to the minor-deferral file ([ROADMAP_0_8.md](ROADMAP_0_8.md) since the 0.7 cut); **RM103's refusal half** moved to
[ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker); and **RM102** closed
outright, which is why it is here.

**The finding worth keeping is about the queue rather than any item in it.** Two of the six were not
design-blocked at all. RM110's encoding was already pinned by a test on one of its two producers, so
nothing was undecided — it was parked because normalizing the other producer moves a fact signature
and the round that found it was a *patch* round, which is a release-class objection that reads, in a
status line, exactly like an open design question. RM102's was the mirror image: the entry argued two
candidate repairs at length and the thing nobody had written down was that **no incident had ever
followed from the behaviour**, which made "close it" a live option that had never been on the list.
Both cost more attention than they were worth, and the same question would have found both: *what
would a decision here actually change?*

## RM102 — the enricher loads a `.env` into `os.environ` from library paths

✖ **Closed 2026-08-21 as a decision not to act**, after the half of it that was a real defect had
already shipped. Motivating case [S39](CONSUMER_SUGGESTIONS_HISTORY.md) from just-module-creator.
**Owner** enricher.

**What shipped, and it was the actual bug.** `load_dotenv_file=False` reached none of the six cache
resolvers: each passes its `default_*_cache_dir()` as an *argument*, and that helper went through a
`_cache_dir` whose `load_env()` was unconditional, so the file was loaded before the resolver looked at
its own flag. The knob did nothing at all. Threaded through `_cache_dir` and the six
`default_*_cache_dir` helpers in **0.6.3**, with `test_locations.py` running each resolver in a
subprocess and pinning both directions plus the pre-fix arrangement, and a twelfth test walking both
families so a seventh resolver cannot quietly reopen it. That is `@off-switch-needs-a-probe` and
`@registry-completeness` in one repair.

**What was filed and is now closed.** Everything the repair does not reach: `load_dotenv` writes the
*whole* file into `os.environ`, not the cache variables alone, and four credential paths — `net`,
`eutils`, `literature`, `pharmvar` — call `load_env()` with **no flag at all**, deliberately, because
a credential is loaded where it is read (`@credential-where-read`). So a caller passing `False`
everywhere still has the process environment mutated by the first network client they construct.

**Why it closed rather than shipping a fix.** The record holds exactly one incident, and it is not one:
S39's reporter lost about an hour to a test named `test_a_token_does_not_leak_between_sessions` failing
with *"The server is configured offline"* instead of its assertion, because their fixture had cleared
a variable with `monkeypatch.delenv` and `override=False` — which skips a variable that is
**present** — let the file refill it. The credential involved was their own, in their own process,
from their own `.env`; nothing crossed a boundary, no build shipped wrong data. Weighed against that:
both candidate repairs cost a full minor, and the better-looking one is **silent for every caller who
never passed the parameter**, so a deployment pointing its cache through `.env` alone simply stops
finding it — the exact "the cache is right there" report the unconditional load was added to end
(S14's shape: the addition being legal does not make the change legal).

**The two repairs, recorded so they are not re-proposed as if new.**

- *Flip the default and leave loading to the entry point.* Right shape — a CLI loading `.env` is
  ordinary, a library function doing it while answering "where is the cache" is not — but a bare flip
  is silent, so the honest route is warn-in-one-minor-then-flip, and it has to cover the four flagless
  credential paths too or it is an assurance that is not one.
- *Narrow it to the cache variables.* Rejected on its own terms: it makes the enricher a filter over
  somebody else's file, and the allowlist becomes a hand-kept list of every variable any tier might
  read — `@registry-completeness`, arriving as a design rather than as a bug. It also does not answer
  the reporter's actual complaint, which is about mutating the process environment at all.

**What stands as the answer for 0.x.** [ENRICHER.md](ENRICHER.md) § cache locations states that the
load writes into `os.environ`, that it is a library path rather than a CLI one, that `override=False`
skips a variable that is present so *deleting* one is what lets the file win, and names both the switch
and the flagless credential paths. That was the reporter's own fallback ask. Their defence — walking
`sys.modules` and replacing every bound `load_dotenv`, rather than patching `dotenv.load_dotenv`, since
every `from dotenv import load_dotenv` holds its own binding — is correct and stays correct.

**Reopen it if the record changes**, and the trigger is specific: something worse than a lost hour —
a credential reaching a subprocess, a crash report, or any boundary at all. The failure mode argues for
watching rather than for building, because it is **green in CI and different on every developer's
machine**, which is the shape that stays undiagnosed longest.


