# just-dna-format — Roadmap

**Forward-only, and now active-only.** Every item here is open work. What shipped moved to
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) with its rationale intact, so this file answers one question:
*what is left to do, and how bad is it?*

- **[RM_TOC.md](RM_TOC.md)** — the complete index of every `RMn`, active and shipped, with the document
  that defines each and every document that mentions it. **Start there if you are looking for an item.**
- **[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md)** — the shipped items, plus the 0.4.1 and 0.5.0
  release narratives.
- **[CHANGELOG.md](CHANGELOG.md)** — what shipped in each release, newest first.
- **[USE_CASES.md](USE_CASES.md)** — where most `RMn` were derived (the *what-blocks?* lens);
  **[PROPOSAL_0_5.md](proposals/PROPOSAL_0_5.md)** — where their shape was argued.

**Split on 2026-08-13, and it changes where to look.** This file is now the **line being built**; a
deferral is filed against the release that will decide it:

- **[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md)** — **the authoritative entry for every active item below.**
  Each was argued to a decision on 2026-08-13, with the facts probed, the repairs rejected and why, and
  the consequences that follow without being chosen. **Where an entry below and the proposal disagree,
  the entry below is stale** — several of these sections were written before the decision and describe
  a shape that was rejected. The proposal also carries RM53–RM67, from
  [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md), which are not repeated here.
- **[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md)** — **the second 0.6 design round, decided 2026-08-16.**
  Everything filed *behind* the first round accumulated in ROADMAP_0_7 because that was the next release
  at the time; PT2 re-asked which release each belonged to now that 0.6 is uncut, and took five back:
  RM55's fix, RM72, RM82, RM84 and RM87. It is authoritative for those five, and for three of them the
  probe overturned what the roadmap entry says.
- **[ROADMAP_0_7.md](ROADMAP_0_7.md)** — items legal in a minor, each waiting on a design question, a
  corpus or a caller. RM10 closed there, folded into RM28. **Five of its entries are now records rather
  than decisions** — see the line above. **Read the membership rule in its header, not a list here**:
  these two bullets carried per-item enumerations until 2026-08-27 and both had gone stale, which is
  what let RM69 sit in the 0.7 file gated on a 1.0 item without anyone noticing.
  [RM_TOC.md](RM_TOC.md) is the complete list, and it is the only one.
- **[ROADMAP_1_0.md](ROADMAP_1_0.md)** — items that need a major, the one that is release-blocking for
  it, and (since 2026-08-27) items *gated on* a major without needing one. Plus the upgrade ledger.
  **The 1.0 cleanup tracker below did not move** and stays the home for the unnumbered major-only items.

Code comments citing "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs — follow them
to [CHANGELOG.md](CHANGELOG.md) / [COMPILER.md](COMPILER.md).

**Status:** **0.6.6 is cut and tagged `v0.6.6`** (2026-08-21) — all three packages read `0.6.6` in
their `pyproject.toml` and the tag is the newest. It carries **nine patch fixes**: the 2026-08-19
doc-audit round (RM104–RM107, RM109, RM111), the two shipped items of the S57–S60 batch (RM121, RM123),
and S61's lookup fix (RM125). RM122 and RM124 are the two of that batch still open, so they are not in
it. Nothing sits uncut on top of the tag as this is written.
**This paragraph read "0.6.4 is the current line" for two releases**, which is the same failure the
*Active items* heading had and the reason both are called out rather than quietly corrected: a status
line nobody re-reads is a status line that lies, so re-read this one whenever a version moves.
`schema_version` stays `"1.0"` and has since 0.4. **Tagged is not published**: whether a
version is installable from PyPI is a separate step and the maintainer's call, so check
[CHANGELOG.md](CHANGELOG.md) before promising a field to anyone. 0.5.0 was released to PyPI on
2026-08-07, with `just-dna-enricher` 0.5.0 the first release of that package.

**0.6.0 was cut and tagged `v0.6.0` on 2026-08-17**, and `0.6.1` followed on 2026-08-18 with RM93–RM100
(see [ROADMAP_HISTORY § 0.6.1](ROADMAP_HISTORY.md#061--the-eight-the-documents-caught-the-two-the-fixes-found-and-rm88)).
This paragraph read *"open on the `0.6` branch, unreleased"* for a release and a half
after that stopped being true, which is the same failure the *Active items* heading had — a status line
nobody re-reads is a status line that lies. What 0.6.0 landed:
`manifest.readme` (S25), `manifest.derived` (S26), then
[RM44](history/ROADMAP_HISTORY_PRE_0_6.md#rm44--fully_resolved-answers-a-question-nobody-asked-it-and-prose-is-the-only-record-of-the-real-one),
[RM51](history/ROADMAP_HISTORY_PRE_0_6.md#rm51--licensingcsv-land-the-better-name-in-a-minor-so-the-major-only-has-to-remove)
and [RM49](history/ROADMAP_HISTORY_PRE_0_6.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses)
— the last two shipped together, because "the same table in two possible places" is one problem whether
the two places differ by name or by directory, and it wants one resolver and one collision rule. Every
reference example kept all four of its signatures across that batch.

**Then the design round itself was built**, in eleven parallel lanes plus a charter amendment that went
first and alone: RM4, RM5, RM24, RM25, RM27, RM43, RM45, RM46, RM47, RM48, RM50, RM59 and the VCF 4.4
cluster RM53–RM65 — the whole of [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md)'s build list, with the rationale in
[ROADMAP_HISTORY § 0.6.0](ROADMAP_HISTORY.md#060--the-design-round-built). Across the corpus that batch
moved `content_signature` on exactly **two** modules (`mt_heteroplasmy` and `htt_repeat_expansion`, both
re-authored deliberately because their VCF pointers named the wrong field), `artifact.digest` on seven,
and it *gained* a `resolution_signature` on the four table-only modules that never had one. The suite
went 1535 → 2046. `schema_version` is still `"1.0"` and cutting the release is the user's call.

**Shipped since: `just-dna-enricher` + `just-dna-compiler` 0.5.1 and 0.5.2** — 0.5.1 was
[RM38](history/ROADMAP_HISTORY_PRE_0_6.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher)
(a cache for every licence-gated source, so a hosted enricher never reaches one live per request) plus
[RM39–RM42](proposals/PROPOSAL_0_5_1.md) from a consumer field report; **0.5.2** is the panel-scale batch behind
S3–S6 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md) — the quadratic DuckDB probe that stopped a
gene panel finishing, a `clin_sig` cross-check that no longer reports a structurally guaranteed zero, a
drafted genotype on the contigs where only one is expressible, and the `.env`-ordering bug behind three
separate "the cache is right there" reports (see [CHANGELOG.md](CHANGELOG.md)). **0.5.3** answers S9 the
same way: it does not widen resolution to the 0.4 families (that is RM43, whose prerequisite column
is 0.6 work since the charter amendment) but makes the scope legible — per positional table, how many rows a VCF cannot join and
how many of those `resolution.csv` could place — and adds `heteroplasmy.csv` to the enricher's subject
list so that family can be resolved at all. The three packages version independently, so
the network tier took a patch while `just-dna-format` stayed at 0.5.0; RM41 is the one item that also
touches the compiler, which is why that package moved too. None of it touches a parquet, a model or a
manifest field, which is why none of it is in the 0.6 table below. **That table is *format/compiler
schema* work**, and enricher-only work sits outside it entirely; do not read "additive work is 0.6" as
covering the network tier.

**The "digest window" is retired — the charter was amended on 2026-08-11 and the sort below follows the
amended rule.** What gates a change is what it does to a *reader*, not to a recompile's bytes:

- **A new optional column is additive and lands in a minor.** An unset optional column is omitted from
  `content_signature` and the per-input hashes cover authored bytes nothing rewrote, so the **authored**
  identity does not move; only a recompile's `artifact.digest` does, and Principle 4 already scopes that
  to a fixed `compiler_version`. Measured, not assumed — see CLAUDE.md for the numbers.
- **A new optional *table* is additive too, and more cheaply**: `file_entries` skips missing files, so a
  module that does not carry the new parquet keeps even its `artifact.digest` byte for byte.
- **Major-only is removal, promotion to required, and retyping** — the moves that break an existing
  reader or invalidate published data.

The practical effect is that several items below were deferred on a rule that no longer holds, and have
been re-sorted on their *own* merits instead; where an item stays deferred, the reason is now stated and
is never "it moves the digest".

Spent while the pre-publication window was open, recorded so it is not re-litigated: the VRS identity switch
(RM19) and the cofactor columns (RM29) — the two that actually needed it — plus
`ResolutionRow.authority` (provenance, so no signature moved), the continuous-bin semantics
(`mt_heteroplasmy` re-authored), indel reconciliation (`shox_par1` gained a resolved coordinate), and
pseudoautosomal locus selection (`shox_par1` halved, 20 rows to 10) — RM33, RM35, RM31 and RM32
respectively. Of the last four only RM31 and RM32 moved an `artifact.digest`; none moved a
`content_signature`, which is pre-resolution by definition.

**The 2026-08-06 readiness audit spent none of it**, which is worth recording because the findings were
severe: it fixed a Principle 7 break where `compile → reverse → compile` relabelled a non-GRCh38 module's
assembly and re-minted its identity key, three further build-confusions in the enricher (including a
frequency pass that would have fetched a *different variant's* counts), and a `validate` that passed
modules `compile` refused (see [CHANGELOG.md](CHANGELOG.md)). Every fix is confined to behaviour
that was only reachable **off** GRCh38 or through the error channel, so all ten pre-existing reference
examples keep their exact `artifact.digest`, `content_signature` and `resolution_signature` — verified by
comparing before and after, not assumed. The one addition is a new example
(`reference_examples/grch37_build/`), and a new module cannot move an existing digest.

Each entry below is `## RMn — name`, a metadata line (**severity**, **status**, **owner**, **motivating
case**), then the detail. Severity is *how much it costs to do*, not how urgent.

# 0.6 — what a minor permits

**Kept as the record of a settled question.** Every ✅ below that named a 0.6 item has since been
built — see [ROADMAP_HISTORY § 0.6.0](ROADMAP_HISTORY.md#060--the-design-round-built) — so this table
now answers *why each was legal in a minor*, which is the part worth not re-deriving. The rows that
stay open (RM23, RM16, RM28, RM15) are the ones deferred to a later line.

Sorted by the amended rule: what a change does to a **reader**, not to a recompile's bytes. Nothing
here is gated on the digest any more, so every ❌ or ⚠ below carries a reason of its own — a design
question, a corpus question, or a genuine break:

| Item | Shape | Minor-legal now? |
|---|---|---|
| **RM23** `predictions.csv` | new optional table | ✅ |
| **RM24** `gene_validity.csv` | new optional table | ✅ |
| **RM25** ClinVar assertion tier | new optional table | ✅ |
| **RM16** authored PRS weights | new optional table | ✅ |
| **RM28** meta-conclusions | new optional table + injected cofactors | ✅ — parked on the corpus, not on the window |
| **RM5** symbolic / structural alleles | *widens* a grammar | ✅ — P3 bars tightening, not widening |
| **RM27** redistribution gate | a gate over a column that already ships | ✅ — reads `sources.csv`, writes no parquet |
| **RM4** gene-panel materialization | compiler behaviour, opt-in per spec | ✅ — row-set expansion pinned on `compiler_version`; only a module that *declares* a panel gains rows |
| **RM10** inheritance expectation | a column, its own table, or yaml metadata | ✅ — all three placements are minor-legal now; pick on orthogonality (P5), not on cost |
| **RM43** resolve the 0.4 families | a stamped-identity column per positional table, then the join | ✅ — the column is additive; what is left is the design round, not a version gate |
| ~~**RM44** `resolution_subjects` count~~ | one additive integer on `Compilation` | ✅ **shipped in 0.6.0** — see [ROADMAP_HISTORY](history/ROADMAP_HISTORY_PRE_0_6.md#rm44--fully_resolved-answers-a-question-nobody-asked-it-and-prose-is-the-only-record-of-the-real-one) |
| ~~**RM51** `licensing.csv` alias~~ | a second accepted spelling of an input filename | ✅ **shipped in 0.6.0**, old spelling deprecated, removal queued for 1.0 |
| **RM50** PMID↔PMCID | a diagnosis (no schema change) + one optional id column | ✅ for the guard, which is an enricher patch; ⚠ for the column — additive, but it wants deciding beside the 1.0 requiredness demotion |
| **RM15** multi-build identity | changes the *semantics* of `variant_key` and of every coordinate | ❌ — 1.0, and not for digest reasons: re-keying published identity is the identity-change class |
| ~~**RM38** gated-source cache~~ | enricher-only: new builders + cache resolvers, no parquet touched | ✅ **shipped in `just-dna-enricher` 0.5.1** — never a 0.6 item; kept here so the *reason* an enricher change bypasses this table stays visible |

Two consequences worth stating outright:

- **RM10's gate dissolved.** It was parked partly because "where it lands" decided whether it was a
  minor or a major. Every placement — a column on an existing table, its own optional table, or
  `module_spec.yaml` metadata reaching only the manifest — is minor-legal under the amended rule, so the
  placement is now a pure design question: which one keeps the axes orthogonal (P5). Decide it on merit.
- **The 1.0 pile split when the rule changed**, and the two items that used to sit together show why.
  `weights.parquet`'s `end` is an *additive optional column*, so it is 0.6 work now, gated on the one
  thing that was always its real blocker: the coordinate convention a second coordinate needs
  (interbase-half-open vs inclusive), which RM15 must settle. **Removing** the dead
  `likely_pathogenic`/`likely_benign` pair stays major, because removal is exactly what the amended
  rule reserves for a major. Same tracker, opposite answers, and the reason is now legible.

# Active items

**Four as of 2026-08-21, and not one of them is a decision:**
[RM103](#rm103--a-version-with-no-digits-coerces-to-000-which-is-a-real-version-nobody-wrote)
(the manifest half only),
[RM108](#rm108--a-clingen-re-curation-appends-a-second-row-and-nothing-marks-the-superseded-one),
[RM110](#rm110--constraint_flags-has-two-producers-with-two-encodings-and-the-column-is-inside-the-fact-set)
and
[RM117](#rm117--an-outrank-record-exists-and-no-check-reads-it-and-what-a-check-should-do-is-undecided)
(the observability half only) — all minors, all with the release undecided, all with their shape
settled and nothing left in them but the typing. **Count them off the sections, not off the
sentence**: this line said *three* for as long as it took to notice that a narrowed item is still an
item, which is the same arithmetic failure recorded two paragraphs down.

**The release-class token in a status line is a fixed field, not prose — a tool reads it.** An open
item's `**Status**` reads `open —` and then, immediately and in bold, `a minor, release undecided`
(or `a patch, …`), because the triage loop's threshold counters grep for exactly that to decide when
to ask whether the next minor should start. An item saying the same thing in other words is invisible
to them, and a counter seeing nothing reads as an all-clear. So write the token verbatim, keep it
**on one line** so a line-based grep sees it whole, and put whatever else the status needs —
*narrowed*, *shape decided*, *the manifest half only* — after its closing `**`. The 2026-08-21
decision round rewrote all four lines below and took the count from six to zero while four items sat
here; that is the second failure of this counter, the first having been that it counted a version
number that then shipped.

**The 2026-08-21 decision round is what emptied the other half.** Six items stood here, every one of
them a decision rather than a missing line of code, and one pass answered all six: **RM102** closed
outright, **RM122** parked on demand and moved to [ROADMAP_0_7.md](ROADMAP_0_7.md), **RM117** narrowed
to the half that costs nobody a decision, and **RM103** split — the manifest half stays here, the
refusal is a tightening and moved to [§ The 1.0 cleanup](#the-10-cleanup-candidate-tracker). The
reasoning is in
[ROADMAP_HISTORY § the 2026-08-21 decision round](ROADMAP_HISTORY.md#the-2026-08-21-decision-round--six-undecided-minors-answered-in-one-pass).

**Two of the six turned out not to be design-blocked at all, and that is the finding worth keeping.**
RM110's encoding was already pinned by a test on one producer — `test_gnomad.py` asserts an empty flag
list is `None`, *not* `""` — so nothing was undecided; it was parked because normalizing the other
producer moves a fact signature and the round that found it was a *patch* round. That is a
release-class reason wearing a design label, and it held the item for two days of looking harder than
it was. RM102's was the mirror image: the item read as a security question and the record held one lost
hour and no incident, which is a disposition nobody had asked for out loud. **Ask what a filed
decision would actually change before treating it as one** — a status line saying *undecided* is not
evidence that anything is.

**The six patches filed beside them shipped on 2026-08-20**
(RM104–RM107, RM109, RM111) and moved to
[ROADMAP_HISTORY § the 2026-08-19 doc-audit patch round](ROADMAP_HISTORY.md#the-2026-08-19-doc-audit-patch-round--six-of-the-eight-fixed).

RM88 and RM93–RM100 all **shipped in 0.6.1** and moved to
[ROADMAP_HISTORY § 0.6.1](ROADMAP_HISTORY.md#061--the-eight-the-documents-caught-the-two-the-fixes-found-and-rm88),
with their rationale and with the five places the eight filings turned out to understate what was
there. **An empty list here is not an all-clear** — it means nothing is *filed*, and this file has read
empty twice before while carrying real work one heading down. The live consumer inbox
([CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md)) is the other half of that question, and
[ROADMAP_0_7.md](ROADMAP_0_7.md) / [ROADMAP_1_0.md](ROADMAP_1_0.md) hold the deferred items.
Every one of them broke a rule this repo had already written down — which is the finding worth keeping
out of the item entries and stating once: **the gotcha book is not the thing that catches a
regression.** In four of the eight the file carrying the violation also carried the rule, sometimes in
an adjacent comment. So the durable half of each is a test, and in six of the nine that test walks a
registry rather than a list.

**RM88 and RM89 were both filed 2026-08-17 out of the 0.6 PT2 batch's lane D**, both *found by
building RM84 rather than by planning it* — neither a defect in what shipped, and neither a blocker
for it. Both are closed now, and RM88's close is worth one line here because the *shape* recurs: the
code half was always cheap and the entry had mispriced it, so what actually held the item for a
release was an undecided policy wearing a technical objection.
**RM89 closed the same week**: the consumer's answer arrived as
[S35](CONSUMER_SUGGESTIONS_HISTORY.md) the day after it was filed, the open question it was waiting on
was the only thing holding it, and building the answer found the defect underneath it — see
[ROADMAP_HISTORY](ROADMAP_HISTORY.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all).
RM74–RM79, the whole 0.6 dogfooding fix round, shipped on 2026-08-15 and moved
to [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md#06-dogfooding--the-fix-rounds-own-findings-repaired) — but
read that as *the sprouts are repaired*, and the ground with them: RM76's narrow repair is what shipped
in that round, and the question it asks from underneath —
[RM73](ROADMAP_HISTORY.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end), the root
several of these grew from — closed on 2026-08-16, both halves. What remains of it is the
**promotion**: making a closure a precondition of compiling is major-only and is filed, with its own
blocker, in [ROADMAP_1_0.md](ROADMAP_1_0.md). Everything that was open on the
`0.6` branch *before* that round was built in the 0.6 batch and moved to
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md) with its rationale; what was deferred moved to the roadmap of
the release that will decide it — [ROADMAP_0_7.md](ROADMAP_0_7.md) (RM16, RM23, RM28, the deferred
halves of RM55, RM56, RM65, plus RM66 and RM67, and the dogfooding items RM68–RM72) and
[ROADMAP_1_0.md](ROADMAP_1_0.md) (RM15, RM52, RM55's removal half). *That sentence records the
2026-08-13 split and is not a current inventory — RM69 has since moved to the 1.0 file, and five of the
0.7 entries shipped in the PT2 round. Follow [RM_TOC.md](RM_TOC.md) for where an item lives today.*

**This section read "None in this file" for a day after the six were filed**, because they were appended
below the *Not format scope* heading and nothing moved the boundary — so the roadmap's own summary line
said it had no open work while carrying two high-severity items. Recorded rather than quietly fixed: it
is the [RM_TOC.md](RM_TOC.md) failure mode (an item nobody can find) arriving in the file the index
points *at*, and it is why a new item starts here as a `## RMn` section and gets its RM_TOC row in the
same commit.

The trackers further down are the other live part of this file: the reserved-namespace tracker and the
1.0-cleanup candidate tracker, which the Constitution deliberately keeps out of itself.

## RM103 — a version with no digits coerces to `0.0.0`, which is a real version nobody wrote

**Severity** low-medium · **Status** open — **a minor, release undecided** — the manifest half
only; the refusal half is a tightening and moved to
[§ The 1.0 cleanup](#the-10-cleanup-candidate-tracker) on 2026-08-21 · **Owner** format ·
**Motivating case** S42 (just-dna-lite, in CONSUMER_SUGGESTIONS_HISTORY.md)

`ModuleInfo(version="abc").version` is `"0.0.0"`. `normalize_version` strips every non-digit, finds
nothing, and pads to three zeros — documented in its own docstring (*"a value with no digits →
`0.0.0`"*) and pinned by a test, so this is deliberate behaviour rather than an oversight. The
reporter's objection is nonetheless right, and it is about *which* value is invented: `0.0.0` is a
legal SemVer and a plausible pre-release marker, so an unreadable string becomes a confident claim
instead of an error. Verified to reach the published artifact — `identity.version` in `manifest.json`
reads `0.0.0`, with nothing beside it recording that the author wrote `abc`.

**The coercion itself is not in question and must not be undone.** RM17 decided coerce-rather-than-
reject because the pre-0.4 corpus is full of `v2` and `3`, and 0.6 widened it at `mode="before"` after
**26 of 61** foreign modules refused on an unquoted integer. Every digit-bearing case — `v2`, `3`,
`1.5`, `v1.2.3-beta` — is working as intended and stays. What is at issue is the *digitless* case
alone, where there is no authorial intent to read and the function invents one.

**Decided 2026-08-21: the item splits, and only the additive half stays here.** Surfacing
`version_coerced_from` in the manifest is purely additive and minor-legal on every reading of the
charter. Refusing a digitless version is a *tightening*, and it moved to
[§ The 1.0 cleanup](#the-10-cleanup-candidate-tracker) because the two readings of the charter
genuinely disagree and settling that is not this item's job: RM50 and RM48 both shipped new refusals
in **0.6.0** as minor work, and INTEGRATION_0_6 § 1 lists them under *"two checks can newly refuse an
author's spec"* precisely because a consumer compiling other people's specs sees CI go red — while
Principle 8's forbidden-moves clause is written to keep anything previously valid from becoming
invalid. Precedent says minor; the principle's stated purpose says major. **Neither half of this item
needed that answer, and the entry was holding its own additive half hostage to it** — which is why
the split is the decision and not a way of ducking one.

**What ships here.** `version_coerced_from` already holds the authored text, and the compiler already
**warns**, naming both values (*"module.version 'abc' was read as SemVer '0.0.0'"*); `validate_spec`
reports it identically, so there is no parity gap to close. What is missing is the *manifest*: publish
the authored string beside `identity.version`, so the fabrication is auditable in the artifact and not
only in a build log somebody had to have kept. It does not stop a bad value being published and was
never claimed to — it makes one legible afterwards, which is the whole of the ask that is additive.

**A sentinel stays rejected.** Coercing to something that cannot be mistaken for a version has no
target: every three-number string is a legal SemVer, so any sentinel is someone's real one — the
complaint restated.

**What the reporter should do meanwhile, and it is not nothing.** The compiler already tells them:
both `compile` and `validate` emit the coercion warning with the authored string in it, so a build
that greps its warnings catches this today. The gap is between the *model* (silent) and the
*pipeline* (loud), and the reporter was testing the model directly.

**One correction to their report, in their favour.** They note their own CLAUDE.md claimed *"an
unquoted `1` in YAML loads as an int and is rejected"* and is wrong on 0.6.1 — `1` coerces to
`1.0.0`. Confirmed, and our documents do not carry that claim: AGENT_NOTES `@yaml-version-int`,
CHANGELOG and DOGFOOD_0_6_FINDINGS all describe the int refusal as the **pre-0.6** state that RM17's
widening fixed. The hazard is the unquoted *decimal*, which is still refused and deliberately so.


## RM108 — a ClinGen re-curation appends a second row and nothing marks the superseded one

**Severity** medium · **Status** open — **a minor, release undecided** — shape decided 2026-08-21 ·
**Owner** enricher · **Motivating case** the 2026-08-19 doc audit (just-module-creator's
`gene_validity.md`)

`_merge_key` returns `("id", row.assertion_id)` when the source published one — the right rule in
general, and wrong here, because ClinGen's assertion id **embeds the curation timestamp**
(`CGGV:assertion_…-2019-08-18T160312.829Z`). A re-curated assertion therefore arrives under a
different id, misses the merge key, and is appended beside the old one. Reproduced with two injected
exports differing only in date and grade: the file came back with both, and
`manifest.gene_validity.classifications` then publishes a pair — as far apart as
`["definitive", "refuted"]` — with nothing anywhere saying which is current. `classification_date` and
`dataset` are the only discriminators and no consumer reads either.

**Decided 2026-08-21: the newest `classification_date` is current, and nothing is deleted.** That is
S45's answer carried over to a weaker signal, and taking it means accepting one thing this format has
not accepted before — that a date is authoritative for currency. The concession is narrower than it
looks. The date decides *ordering* and nothing else: it never says a classification is right, both
rows stay in the file so the drift stays visible, and the superseded one is **marked** rather than
dropped, so a consumer wanting the history has it and a consumer wanting the answer no longer has to
reconstruct one. `manifest.gene_validity.classifications` then publishes the current classification
instead of a pair as far apart as `["definitive", "refuted"]`.

**What the fix has to contain, and the middle one is what gets forgotten.** A re-curated assertion has
to be recognised as the same assertion — ClinGen's id embeds the timestamp, so the id alone cannot do
it, and the recognition belongs beside `_merge_key` rather than inside it. The superseded marking needs
a column, which is additive and minor-legal. And **the merge test has to stop re-running an identical
export**: it cannot see this defect at all as written, so it is part of the fix rather than the thing
that confirms it.

**What was rejected, and why it is worth writing down.** Stripping the timestamp out of the merge key
is the smallest change and removes the pair at source, but it overwrites the earlier curation — the
opposite of S45 — and turns visible drift into invisible drift, which is the thing this item is about.
Publishing both facts and leaving the consumer to choose was the honest alternative and lost on one
point: every consumer then implements the same date comparison, and they will not all implement it the
same way.

## RM110 — `constraint_flags` has two producers with two encodings, and the column is inside the fact set

**Severity** medium · **Status** open — **a minor, release undecided** — decided 2026-08-21; the
minor is because it moves a fact signature, not because anything is unsettled · **Owner** enricher ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_metrics.md`)

The live API route writes `"|".join(sorted(flags)) if flags else None`. The snapshot route copies
gnomAD's TSV cell verbatim, and gnomAD writes a **JSON array literal** there; `[]` is not in
`constraint_build._NULLS`, so it survives as the two-character string `"[]"`. Measured over the
published v4.1 snapshot: **17,403 of 18,111 rows** carry `"[]"`. Every consumer writing the obvious
`if row.constraint_flags:` therefore reads 96% of snapshot rows as *flagged*, and the same gene fetched
two ways gives two different cells. The field description (*"kept verbatim and pipe-joined"*) is true
of one producer only.

**Decided 2026-08-21: pipe-joined when non-empty, `None` when empty, on both legs.** There was never
a second candidate. `enricher/tests/test_gnomad.py` already pins exactly this on the live producer —
`assert myh7["constraint_flags"] is None  # empty flag list → null, not ""` — so the contract exists,
is tested, and the snapshot producer simply never implemented it. **The item was filed as needing a
decision when what it needed was a release**, and that is the part worth keeping: the round that found
it was a *patch* round, normalizing the cell moves `gene_metrics.signature`, and a signature move is
not patch work — a release-class objection that reads, in a status line, exactly like an open design
question.

**Re-measured on the published v4.1 snapshot, and it is worse than this entry first recorded.** Not one
of the 18,111 rows is null or empty, so `if row.constraint_flags:` is true for **18,111 of 18,111 —
100%**, not 96%: the 708 genuinely flagged rows are stored as JSON array literals too
(`["outlier_mis","outlier_syn"]`), so a consumer splitting on `|` gets one bogus token rather than two
flags. Only **3.9%** of genes are actually flagged. The fix is therefore not "empty → null" alone —
the non-empty cells need parsing as well, and the field description (*"kept verbatim and pipe-joined"*)
is false on the snapshot leg in both directions.

**The third consequence is what makes normalizing-at-read insufficient.** `constraint_flags` is inside
`GENE_METRICS_FACT_FIELDS`, so the same gene fetched two ways already produces two different
`gene_metrics.signature` values. A public accessor normalizing on the way out would fix what consumers
*read* and leave that divergence in the artifact, which is why the normalization goes in the cell.

**Cost, measured rather than estimated.** One row in our own corpus: `reference_examples/hboc_palb2/`
carries `constraint_flags=[]`, so its `gene_metrics.signature` and `artifact.digest` move and nothing
else in the sixteen examples does. Beyond that it is whatever consumers have compiled from the
snapshot, which nobody has counted — hence the CHANGELOG line, which is the entire reason this is a
minor rather than a patch.

## RM117 — an outrank record exists and no check reads it, and what a check should do is undecided

*(Heading kept for its anchor; since 2026-08-21 the "undecided" half is decided — see the status line.)*

**Severity** medium · **Status** open — **a minor, release undecided** — narrowed 2026-08-21 to the
observability half; the severity half is **closed**, not deferred · **Owner** enricher ·
**Motivating case** [S52](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

**The half that shipped.** `ProvenanceItem.outranks` — `{column: why}`, per column, additive, in the
tree since 2026-08-20 — so an author overriding a checked value has somewhere to record *why*, and the
capture half the reporter is building has a place to write. Neither identity moves. See SCHEMAS.md.

**Decided 2026-08-21: the severity half is dropped, and the free half is what this item now is.**
The proposal was that a filled record change the severity of a source-mismatch — WARNING today, INFO
where a record names the column. It is closed rather than deferred, on the three objections below and
on one that outranks them: **the 0.7 authored-overlay work supersedes the question.**
[RM124](ROADMAP_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it)
carries it as its own open question 2 — `outranks` and an overlay are both an authored value beating a
source with prose attached, the split between them is *exactly the kind of line that erodes*, and that
entry says outright to decide whether one record serves both **before either grows a second field**.
Giving `outranks` a severity consequence now is growing that field. Deciding the ladder first would
fix a shape against machinery about to move underneath it — the same error as fixing a signature
against a hypothesis.

**What this item is, and it costs nobody a decision.** Two signals the check can already compute,
because it runs on every compile and needs nobody's permission:

- **A mismatch that has since resolved.** The archive caught up to the outrank — the author was right
  and the source moved. That is a trust signal available nowhere else in this format, and it is
  observable without asking anyone anything.
- **A record whose row's value has changed again.** Stale by construction: the justification was
  written about a value that is no longer there. This is the binding problem showing up as an
  observation instead of as a mechanism, which is the honest place for it until there is a binding.

Neither touches the severity ladder, neither puts a verdict under authored control, and both stay
correct whatever 0.7 does to the authored model.

**The three objections the severity half never answered**, kept because they are the record of why
it is closed rather than parked:

- **It puts a checked verdict under authored control**, which nothing else in this format does. Every
  other severity here is a property of the finding; this one would be a property of a cell the author
  writes. The reporter's guard against the obvious abuse is sound — a record is a *response* to a
  warning, never a filter filed ahead of one, since a hallucinated value and a correctly outranked one
  start identically — but the code cannot see the order. Nothing distinguishes a record written after
  reading a warning from one written before, so the guard is a convention and not a mechanism.
- **The ClinVar `clin_sig` cross-check is the obvious first site and is deliberately warn-only in both
  modes.** Adding a downgrade *below* warn-only is legal, but the check's whole design is that its
  severity does not vary — and the reason (`@clinsig-never-escalates`) is that whose limit it is, is
  not knowable from the mismatch. That argument cuts both ways here.
- **A record is not bound to the value it justifies.** The reporter saw this and named the right
  precedent: `verification.json` binds to the authored bytes, and a justification written about one
  `clin_sig` does not carry to a different one. Without a binding, an author edits the value and the
  downgrade silently persists. Any severity change probably wants the binding *first*, which is a
  larger design than the severity ladder.

**Do not answer this by parsing the prose.** The field is freeform because the judgement is not
formalizable — a grading pyramid exists, but whether a retraction outranks an archive call is a
natural-language question. Presence is the bit a check may read.

## RM132 — `pharm_variants.csv` makes a clinical claim per row and cites per variant

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm132--pharm_variantscsv-makes-a-clinical-claim-per-row-and-cites-per-variant) on 2026-08-28 — BUILDS in 0.7, and it is the item that makes the round's sort rule load-bearing.** A full-cost authored column is taken anyway because **the risk P9 prices — getting the shape wrong — was spent by RM47 a release ago**, so demand has nothing left to fix. `PharmVariantRow.pmid` plus both cross-check sites in the same release; `provenance_quote` does **not** follow, stated rather than implied.

**Severity** medium · **Status** open — **a minor, release undecided** — shape settled 2026-08-24 by
the RM47 precedent · **Owner** format + compiler + enricher · **Motivating case** S73
(just-module-creator) in CONSUMER_SUGGESTIONS_HISTORY.md

A ClinPGx-drafted module carried **1,482** drug-response rows and had nowhere to cite any of them.
Sixteen model fields, thirteen authored, none a PMID or DOI.

**The question the reporter asked was which of three provenance models was intended, and the tree
already answers it — RM47 decided this shape one release ago for a different table.** *The bin row
cites; the citation table describes.* The rule underneath is: **a row cites when its claim is
finer-grained than `studies.csv`' key.** `studies.csv` keys on `(variant_key, pmid)`, so a study row
attaches to a *variant*; `pharm_variants.csv` keys on `(variant_key, drug, genotype,
phenotype_category, annotation_id)`, so one study row would attach to every drug, genotype and
phenotype category recorded for that variant. The reporter reached that conclusion themselves and
declined to build on it, which is the right call.

**So the answer is the third reading and the column is missing rather than deliberately absent.**
`evidence_level` is not the provenance handle — it points at somebody else's *grading of* evidence
rather than at the evidence — and the licence row's `source`/`dataset` state redistribution terms, not
grounding. Both are recorded in SCHEMAS beside the citation-site table so nobody re-derives them.

**What the fix contains, and the second half is what makes it a piece of work rather than a column.**
`PharmVariantRow.pmid`, optional, free-form under the same grammar as `StudyRow.pmid` and
`MeasureBinRow.pmid` — additive and minor-legal. And **both literature cross-check sites have to learn
the new citation site in the same release**: `_cross_check_literature` in the compiler and
`enrich_literature` in the enricher. That obligation is not inferred; it is RM47's recorded lesson in
its own words — *shipping the column without both would be evidence the format never checks, which is
worse than the gap* — because every citation from the new site would otherwise read as a stale orphan
in one direction and be invisible in the other. The enricher must reach the rows through **public**
compiler symbols, as `load_binning_rows`/`binning_citations` already do for the bins; a second copy of
the table roster in the enricher is the RM40/RM41 shape.

**Open, and it is the only thing genuinely undecided**: whether `provenance_quote` follows. On the
binning side it deliberately did not — the bin row cites and `studies.csv`/`literature.csv` describe,
which is what stops `StudyRow`'s whole provenance column set migrating one column at a time. The same
argument should hold here, and it is worth stating rather than assuming, because the reporter's skills
teach `provenance_quote` and per-row citation hard, and a 1,482-row body of clinical claims is exactly
where somebody will ask for the quote next. P9 prices this: `pharm_variants.csv` is an **authored**
table, so every column is full cost.

**Not in scope**: widening `studies.csv`' key, which is the repair that looks obvious and is the one
RM47 already refused — it would make a study row's subject depend on which table read it.

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

## RM134 — PubMind as a literature-derived annotation authority, and a ClinVar concordance check

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm134--pubmind-as-a-literature-derived-annotation-authority-and-a-clinvar-concordance-check) on 2026-08-28 — BUILDS in 0.7, pulled in after the other eleven were decided and reviewed against them.** Eight corrections, two of which were defects that would have shipped: **the concordance record is shared with RM130 and RM130's shape changes because of it** (`ClinSigConflict` names its authority in a *field*, so a second authority would have cost a key change or a retype — major-only); and **one normalizer, not two, after two fixes** — `_normalize_clin_sig`'s map keys are underscored while PubMind's tokens are spaced, so `Uncertain significance` and `Conflicting` both fall to `other` today and the check would manufacture a disagreement on PubMind's largest disagreeing class. **A maintainer stress test at five authorities failed the drafted vocabulary**: `pubmind_only`/`clinvar_only` name the authority inside the member, because one field carried two axes. Split into `authority_concordance` and `authored_position`, five members each at any N. **Nothing resolves a split** — E+A agreeing against B/C/D needs a weighting model this repo has refused to invent three times — so the precedence list is recorded as methodology and computed with by nothing. Licensing governs what a module may *do* with the values, not whether the machinery exists: unknown terms warn and never gate, and publishing such a module is RM27's axis.

**Severity** low-medium · **Status** 🔨 **§ A SHIPPED in 0.7** (2026-08-28), §§ B–D in build; the
batch is a minor, release undecided** · **Owner** enricher · **Motivating case** the PubMind paper
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

## RM136 — `enrich` re-reads the derived file, so an overlay correction is invisible to the checks

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** enricher ·
**Found by** the wave-1 audit of RM124, 2026-08-28

The compiler applies `overrides.csv` before any check reads a row, which is the whole point: a check
must see what the module asserts. The enricher does not. Its own passes re-read the raw derived file,
so an author who corrects a `resolution.csv` cell through the overlay — the mechanism RM124 built for
exactly this — will see `enrich` report the same finding on every subsequent run, forever, with no way
to clear it and no indication that their correction was recorded and honoured one tier over.

`INTEGRATION_0_6.md` states the asymmetry for *consumers* ("read the derived parquets, not the derived
CSVs"). It is not stated for the **author**, who meets it first and has no parquet to read at the point
they are curating.

**What is not the repair.** Teaching every enricher pass to apply the overlay puts a second
implementation of `apply_overrides` in the tier that fetches, and the two would drift on exactly the
normalization seam that already produced one silent P7 break in this feature's first week. Nor should
the enricher *write* through the overlay: an overlay row is the author's answer to a difference, never
the tier's (RM83's standing refusal).

**The shape worth designing.** Probably the enricher reading the overlay read-only and suppressing a
finding it has already been answered for — which needs a decision about what "answered" means when the
overlay corrects a different column than the one the check is about, and that decision is the item.

## RM137 — an overlay `update` on a row the compiler drops warns on the second lap only

**Severity** low-medium · **Status** open — **a minor, release undecided** · **Owner** compiler ·
**Found by** the wave-1 audit of RM124, 2026-08-28, reproduced end to end

`reverse_module` rebuilds a derived table from the artifact, and two tables are rebuilt from something
narrower than the file the compiler read: `literature.csv` loses its uncited rows before the parquet
(`@uncited-literature-dropped`) and is rebuilt *from* that parquet, and `resolution.csv` has no parquet
at all and is rebuilt from the SNP core. An `update` naming such a row therefore matches on lap 1 and
warns on lap 2, so a module and its own `compile → reverse → compile` disagree on
`manifest.compilation.warnings`, a published field. Both hashes hold; only the warning moves.

Reproduced on `reference_examples/hboc_palb2` with one uncited `literature.csv` row under a one-row
overlay: lap 1 warns zero times, lap 2 once.

**Already done, and it is not the fix**: the message now names the third reading, so it no longer
tells an author their subject is mistyped when the correction is fine and the table is short.

**Why each obvious repair is wrong.** *Apply the overlay after the drop* — the checks then stop seeing
what the module asserts, which is the property the apply position exists to hold. *Make reverse emit
the dropped rows* — there is no source of truth for them; they are not in the artifact at all.
*Suppress the warning for the two tables* — re-opens the silent-suppress hole the design already calls
its worst case, and it would hide a genuine typo on the tables most likely to carry one.

The honest framing is that this is the round trip being lossy about **warnings** rather than about
content, on a channel RM126 has now made load-bearing.

**RM131's `carried` split shipped in 0.7, so the discriminator now exists and this item can be decided
against it rather than waiting on it.** Two things it settles. `overlay_update_unmatched` is classified
**actionable**, which is the right answer for the reading the entry is about — a mistyped subject is the
author's to fix — and it is therefore *not* excused by carried-ness; a sweep will report it as work
arriving. And RM124's `suppress` record, added in the same release, shows the shape of the repair
available here: **it counts the overlay's own rows rather than the rows it reached**, so it says the same
thing on both laps. An `update` cannot borrow that directly — its finding is precisely *this correction
reached nothing*, which is a fact about the reached set — but the question the repair has to answer is
now narrow: is a warning that fires only on the second lap better reported over the **overlay** (stable,
and silent about the one case the author cares about) or left as-is (truthful per lap, and moving a
published field between a module and its own round trip).

## RM138 — `carried` duplicates the message text, so the channel RM131 shrank nearly doubled

**Severity** low · **Status** open — **a minor, release undecided; filed 2026-08-28 by the RM131
review, measured over the whole reference corpus** · **Owner** format (schema) + compiler ·
**Found by** reviewing RM131 against its own motivation

**Not a defect, and the entry says so first.** The shape was decided per item with the maintainer:
*a `carried` list beside `warnings`, holding the subset the author cannot clear*, chosen over a field
on each finding because it invents no permanent names and because *a consumer subtracts to get the
actionable set*. Both properties hold. What the decision did not have in front of it is the size, and
the size is the thing RM131 exists about.

**Measured, not estimated** — every reference example that emits a warning, byte lengths of
`compilation.warnings` against the `compilation.carried` added beside it:

| module | warnings | carried | warnings (B) | + carried (B) | growth |
|---|---|---|---|---|---|
| `pathogenic_clinvar` | 113 | 109 | 28,059 | 26,991 | 1.96× |
| `hboc_palb2` | 12 | 12 | 2,977 | 2,977 | 2.00× |
| `htt_repeat_expansion` | 3 | 1 | 2,200 | 729 | 1.33× |
| `cyp2d6_structural` | 2 | 1 | 1,787 | 723 | 1.40× |
| `apoe_epsilon`, `shox_par1` | 2 | 2 | 224 / 478 | 224 / 478 | 2.00× |
| **corpus** | | | **41,272** | **+34,744** | **1.84×** |

So the reported 14 kB module becomes a 55 kB one on the worst case here, and a module every one of
whose findings is carried pays exactly double. The channel is still *readable* — that was never about
byte count — but a reader who came to this item because the output was too long to follow deserves the
number stated rather than discovered.

**Why the obvious encodings are each wrong, so nobody re-proposes one.**

- **`carried: list[int]`, indices into `warnings`.** Roughly a hundredth of the bytes and it breaks the
  one property the field was chosen for: the subtraction becomes a zip, and an index means nothing to a
  consumer that filtered or re-ordered the channel it came from. It also makes two published fields
  positionally coupled, which is the shape `manifest.compilation.warnings` has always avoided.
- **`carried: list[str]` of codes.** Cannot say *which messages*, so it answers a different question —
  and it is already answerable, because carried-ness is a property of the code alone:
  `warnings_summary` plus `CARRIED_WARNING_CODES` already gives the count. A consumer wanting the
  count does not need this field at all.
- **Drop `carried` and publish a per-message `codes: list[str]` parallel to `warnings`.** The genuinely
  minimal encoding — about 20 bytes a message instead of 250 — and both `carried` and
  `warnings_summary` derive from it. It is also a **third** shape rather than the one that was decided,
  it re-introduces the positional coupling above, and it hands every consumer a derivation to perform
  where they currently read an answer.

**The honest framing** is that the duplication buys a self-describing field, and the question is
whether a published manifest should pay ~1.8× on this channel for it. Worth deciding once, with the
table above, rather than drifting: a fourth encoding after 1.0 is a removal, and removals are
major-only under Principle 3.

# Not format scope

Listed so they are not mistaken for format scope, and so nobody re-proposes them.

## RM7 — Evaluation-output / report-card schema

**Severity** — · **Status** **not format scope** — a consumer contract · **Owner** consumer
(`just-dna-lite`) · **Motivating case** verification harness (§1a)

For the verification harness — **NOT a format task.** Per-sample results are a *measurement*, so
by the data-agnostic north star this is a **consumer** contract (`just-dna-lite`), listed here
only so it is not mistaken for format scope.

## Annotating core, not format scope (the 0.5 source assessment)

RM7 and RM13 are listed above so they are not mistaken for format scope. The same needs saying about
roughly half of every annotation source assessed in 0.5 — the half that **calls or interprets**. A
module supplies annotation tables; the measurement arrives from the consumer at query time, so none of
the following can land in these libs no matter how useful it is:

- **Star-allele callers** — PharmCAT, and Cyrius / PyPGx for the CYP2D6 case PharmCAT punts on. These
  turn a VCF or a BAM into a diplotype call: measurement. What *does* belong here is their **data** —
  the CPIC allele definitions PharmCAT ships — which is why the drafting helper reads them. Note that
  routing through PharmCAT does not launder the terms: its definitions are CPIC's, so the ClinPGx
  no-sale clause still applies.
- **Running splice or missense predictors**, and choosing their thresholds. A SpliceAI delta of 0.2 vs
  0.5 is an interpretation policy, not an annotation; RM23 carries the score and the dataset, never a
  verdict.
- **ACMG rule application and incidental-findings reporting policy.** The format carries `acmg_sf` as a
  flag and (since 0.5) validates it against the published list; deciding what to report to
  whom is the consumer's.
- **Lay-language rendering.** A module already carries the ontology CURIE and a human `conclusion`;
  turning a MONDO term into patient-facing prose is a presentation concern.

**Cross-repo (tracked elsewhere):** **just-dna-marketplace** — take `just-dna-compiler` as the M4
publish dependency; serve `logs` via the files endpoint; render the cross-version provenance union
(`aggregate.aggregate_provenance`) on the module-detail view.


# Trackers

## The 1.0 cleanup (candidate tracker)

The **compatibility policy** — additive within a major, breaking cleanup only at a major bump, the
two-step deprecate→remove default — is a durable rule in [CONSTITUTION.md](CONSTITUTION.md)
(Principle 3). This is the **living tracker** of concrete items queued for the `→ 1.0` break; add
candidates as they surface.

**Additivity has two axes.** A new version may expand the **column-set** (new optional columns) *and*
the **row-set** (one authored row compiling to several — e.g. a one-to-many rsid → one row per locus).
Both are minor-legal: a new **optional** column leaves the authored identity untouched (it is omitted
from `content_signature`) and moves only a recompile's `artifact.digest`, which P4 already scopes to a
fixed `compiler_version`. Row-set expansion changes identity
*cardinality* but is **not** a schema break: it is resolver behavior pinned on the `compiler_version`
axis (P4 already pins the digest to the resolved reference), so the GRCh38 expansion ships now. Only
the *build-aware* generalization (which/how-many loci per build, cross-build annotatability) is RM15.
The idea is to pile genuinely rule-tripping edge-cases (requiredness demotions, retypes, identity-key
*semantics* changes) on the 1.0/RM15 piles instead of forcing them into a minor.

**The cadence changed on 2026-08-12 and this tracker is read under the new one** (CONSTITUTION § 0.6
amendment). Retirement is *deprecate in a minor, remove at the next major* — so an item whose
replacement already exists gets its warn-only deprecation in a 0.x release and **disappears at 1.0**,
rather than being deprecated at 1.0 and lingering to 2.0. The exception is written into the principle:
a deprecation must be **actionable**, so anything Principle 8 still makes mandatory — `VariantRow.state`,
the `pathogenic`/`benign` booleans — cannot be deprecated while an author has no way to stop setting it.
Those keep the old shape (demoted and deprecated at 1.0, removed at 2.0) because P8 blocks them, not
because the cadence does. Every entry below that says "deprecate at 1.0" should be re-read with that
distinction in mind, and moved forward where nothing blocks it.

Every item here also owes an **upgrade line** under RM52 — written when the item lands, not when the
release is assembled.

Version-axis note: `schema_version` is `"1.0"` while the packages are `0.x` (now `0.5.0`). At `1.0`,
either align them or document explicitly that they track different things (wire format vs. package
release).

### RM135 — `ProvenanceItem.outranks` is superseded by the overlay, and one of them has to go

**Severity** low-medium · **Status** queued for 1.0 — **filed 2026-08-28 by
[PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it)**,
which decided the succession rather than the merge · **Owner** format

RM124's `overrides.csv` records an authored value beating a source, with prose. `ProvenanceItem.outranks`
— `{column: why}`, shipped by S52 — records an authored value beating a source, with prose. They are one
concept in two files, split on authored-versus-derived, and Principle 5 says decide before either grows a
second field. The proposal decided: **both stand in 0.7 and the unification lands here.**

**The rule that survives is the simpler one — the *existence* of an override in an authored table
auto-beats the derived value**, with no separate declaration to write. By Venn diagram the overlay's logic
is a partial superset of what `outranks` allows and reaches it more directly, so once an author controls
both derived overrides and authored tables the `outranks` knob has nothing left to do.

**Why the deprecation is not in 0.7, and this is the part to re-read under the cadence note above.** The
two-step default would put a warn-only deprecation in a minor and the removal here. It cannot, yet: the
overlay covers *derived* tables and `outranks` covers an *authored* cell, so until the overlay's semantics
reach authored tables — which is this item — an author warned off `outranks` has nowhere to go, and
Principle 3 says a deprecation belongs in a minor only where its audience can act on it. **The warning
ships with the replacement, in whichever minor extends the overlay to authored tables; the removal is
here.** That ordering is the item's own upgrade line under RM52.

### `module.version` — refusing a digitless version

**Severity** low-medium · **Status** queued for 1.0 — **filed here on 2026-08-21 by the RM103 split**,
and filed as a charter question rather than as a fix

Split off [RM103](#rm103--a-version-with-no-digits-coerces-to-000-which-is-a-real-version-nobody-wrote),
whose additive half stays open as a minor. `normalize_version("abc")` returns `"0.0.0"` — a legal
SemVer and a plausible pre-release marker — and it reaches `identity.version` in a published
`manifest.json`. Refusing it instead is the cleanest end state and is the reporter's implicit ask; the
coercion for every **digit-bearing** case (`v2`, `3`, `1.5`, `v1.2.3-beta`) is RM17's decision and
stays.

**It is here because the two readings of the charter disagree, and nothing had made them argue.**
Precedent says minor: RM50 and RM48 both shipped new refusals in **0.6.0** as minor work, and
INTEGRATION_0_6 § 1 lists them under *"two checks can newly refuse an author's spec"*. Principle 8's
purpose says major: its forbidden-moves clause exists so that nothing previously valid becomes
invalid, and a spec that compiles today failing tomorrow is exactly that. **The clause is written about
*fields* — requiredness and retyping — and a new refusal on a *value* is an axis it does not name**,
which is why both readings are defensible and why neither is written down.

Filing it here takes the conservative branch by default. That is a decision worth revisiting
deliberately rather than by precedent, because the answer governs RM50 and RM48 retroactively and every
future check: **if a new value-refusal is minor-legal, say so in the Constitution; if it is not, two
0.6.0 changes were mis-sized.** Whoever picks this up should settle the general rule first and let
`module.version` fall out of it.

### `stats`' scalar counters read `0` where the table is absent, and cannot say "inapplicable"

**Severity** low-medium · **Status** queued for 1.0 — **filed here on 2026-08-24 from S72**, because
the fix is a retype of published fields and nothing smaller reaches it

`variant_stats` derives `variant_count`, `unique_rsids`, `study_count` and the ClinVar counts from
`variants.csv` alone, so a module led by any other kind publishes `0` for all of them. Measured on a
**1,482-row `pharm_variants.csv`** module: `variant_count: 0`, `unique_rsids: 0`, `study_count: 0`.

**`unique_rsids: 0` is the one that is simply false rather than merely narrow**, and the reporter is
right about why: `rsid` is the first authored column of `pharm_variants.csv` and 1,482 rows carry one,
so the counter reports none of something that is there. `variant_count: 0` for a module with no
`variants.csv` is *true* and unhelpful; this one is untrue.

**The ask is `None` where the table is absent, and it is a retype.** `Stats.variant_count` and its
siblings are `int` with a default of `0` in a **published** `manifest.json`, so widening to
`int | None` breaks any reader that compares or sums them — P3 names retyping as major-only precisely
for that, and this is the ordinary case rather than a stretch of the rule. The same holds one layer
down for `ValidationResult.stats`: the dict is `dict[str, Any]`, so nothing retypes formally, but its
keys are a documented contract and changing `0` to `None` breaks the same arithmetic. Sizing it as a
minor because "the field is only advisory" is the move RM127 recorded as the tempting one.

**It is the right end state, though, and that is why it is filed rather than refused.** The reporter's
framing is our own rule in our own output: `VerificationRecord`'s docstring says *"`subjects=0` with no
`skipped` means the check ran and had nothing in scope, which is not the same as not running"*, and
`stats` inverts it — a consumer cannot tell *counted, and the answer is none* from *this counter does
not apply here*. A registry keying a facet off either inherits the collapse, which is the S57 failure
one field over.

**What shipped instead, and it is not a substitute.** `row_count` (documented, family-independent) and
`table_rows` (promoted from de-facto to contract) give a caller the honest number today, and the field
description now says in terms that `0` in the scalar counters means *no `variants.csv` rows* and never
*no data*. That makes the counters readable; it does not make them correct.

**Decide it with the `module.version` refusal above**, which is the other charter question on this
tracker: both turn on how far P3/P8's field-shaped clauses reach, and answering one without the other
is how two defensible readings stay unwritten.

### `VariantRow.variant_key` / `authored_ident` are inside `content_signature`; the 0.6 stamped fields are not

**Severity** low · **Status** queued for 1.0 — align the two, one way or the other

Surfaced by RM43 (0.6) rather than designed: the three positional models gained stamped, parquet-only
`variant_key` and `authored_ident` columns, and they had to be declared `Field(exclude=True)`. Declaring
them plainly **moves `content_signature` on all five positional-table modules**, because
`integrity.content_signature` hashes `model_dump(exclude_none=True)` and a *stamped* field is never
`None` — so it lands in the authored identity, which is exactly what the stamped-column mechanism exists
to keep it out of. `_build_table` reads the values off the row instead, so the columns still reach
parquet.

`VariantRow`'s own two are **not** excluded and therefore *are* inside its `content_signature`,
grandfathered: they predate the mechanism being generalized, and changing them now would move the
authored identity of every SNP-core module ever published. So one model hashes its stamped fields and
three do not, for no reason a reader could derive. **Disposition:** at 1.0, exclude `VariantRow`'s two as
well (the honest shape — a compiler-stamped value is not authored content) and accept that every 0.x
`content_signature` moves once, under the major's documented upgrade procedure. The alternative —
un-excluding the three new ones — is strictly worse: it would put machine-filled coordinates into the
authored identity and defeat RM43's whole reason for existing. Owes an RM52 upgrade line either way,
since a moved `content_signature` breaks content-dedup across the boundary.

### `VariantRow.state`

**Severity** medium · **Status** queued for 1.0 — deprecate; remove at 2.0

Overloaded legacy field; a derived alias of `direction` since 0.3. **Disposition:** Deprecate at
1.0 (still read) → remove at 2.0, once consumers read `direction`/`stat_significance`. **This keeps the
pre-amendment shape for a reason, and is not stale:** the field is still *required*, so a deprecation
warning in a 0.x minor would fire on every module in existence and name nothing the author is permitted
to stop doing. P8 is the blocker, not the cadence — the demotion and the deprecation land together at
1.0, and removal falls to 2.0.

### `state` values `alt` / `ref`

**Severity** low · **Status** queued for 1.0 — drop from the read-vocabulary

Genotype-relative descriptors that never belonged; recoverable from `ref`/`alts`/`genotype`; not
emitted since 0.3. **Disposition:** Drop from the accepted read-vocabulary at 1.0.

### `VariantRow.pathogenic` / `benign` booleans

**Severity** medium · **Status** queued for 1.0 — deprecate; remove at 2.0

Lossy (can't express `likely_*`/`uncertain`); derived aliases of `clin_sig` since 0.3 (now
materialized tri-state). **Disposition:** Deprecate at 1.0 → remove at 2.0. (`clinvar` provenance
boolean stays.) Same P8 blocker as `state` above — required/authoritative today, so the deprecation
cannot move into a minor however cheap warn-only is.

### `StudyRow.p_value: str`

**Severity** low · **Status** queued for 1.0 — retype (`p_value_num` shipped in 0.5)

Untyped string holding a number; can't be compared/sorted numerically. **Disposition:** Add a
numeric companion in 0.x if needed; retype/remove the string at 1.0 (breaking).

### `weights.parquet` `end` column

**Severity** low · **Status** split by the charter amendment — **wiring it is 0.6; removing it is 1.0**

Always set equal to `start` — no source column feeds it. **Disposition:** wire it to a real end
coordinate (an additive change to an existing optional column, so a minor) or remove it outright at 1.0
(removal is what the amended rule reserves for a major). **Re-examined in 0.5 and
deliberately left here** rather than wired inside the window: wiring a second coordinate buys an
off-by-one unless the first one's convention is unambiguous, and half of that was still open — every
tier *stored* Ensembl's 1-based position while `VariantRow.start`'s own description said "0-based",
which is the text `describe`/`requirements`/`reference` print at an author.

That half is now closed: the authored `start` descriptions say 1-based VCF POS, and
`schema/tests/test_coordinate_convention.py` pins the prose to what the minting code actually does.
What remains is the genuine design question — whether an `end` is interbase-half-open (VRS) or
inclusive (VCF-ish), which is the same choice RM15 has to make for a build-agnostic identity, so the
two stay paired.

### `weights.parquet` `likely_pathogenic` / `likely_benign`

**Severity** low · **Status** queued for 1.0 — remove; wiring rejected in 0.5

Always `False`; no CSV column feeds them — dead output. **Disposition:** Remove at 1.0, or wire to
the `clin_sig` tier. **Re-examined in 0.5: removal is the answer, and wiring was rejected.**
`clin_sig` is itself materialized into `weights.parquet` and `derive.pathogenic_from_clin_sig`
already maps `likely_pathogenic → True`, so a wired column would tell a consumer nothing it cannot
already read. That argument is unchanged by the charter amendment — wiring is cheap now and still
pointless — while the **removal** stays major, which is the half the amendment does speak to.

### `VariantRow.weight` vs `effect_size`

**Severity** low · **Status** queued for 1.0 — review only

Potential confusion — module-local score vs published magnitude (both kept, documented).
**Disposition:** Review at 1.0 whether `weight` stays or is subsumed by `effect_size`.

### `sources.csv` — the name, and the `source` column it collides with

**Severity** low (nothing is wrong; a reader has to be told three times) · **Status** queued for 1.0 —
rename with the two-step, or decide explicitly to keep it

The file is a **licensing and attribution ledger**: one row per `(source, layer)`, carrying the terms,
the attribution text, `license_sha256`, and the three tri-state permission axes. It is the only file
the compile licence gate reads. Nothing in the name says any of that, and it collides twice over —
with the `source` *column*, which in `resolution.csv`/`frequencies.csv`/`gene_metrics.csv`/
`literature.csv` means "which link answered" (the overload RM33 already had to split, adding
`authority` so the compiler had something to join on), and with the ordinary English sense in which
`studies.csv` and `literature.csv` are also "sources". SCHEMAS.md now carries a three-row table
disambiguating them, which is the tell: a name needing a table is a name doing no work.

**The input half is done — [RM51](history/ROADMAP_HISTORY_PRE_0_6.md#rm51--licensingcsv-land-the-better-name-in-a-minor-so-the-major-only-has-to-remove)
shipped in 0.6.0**: `licensing.csv` is an accepted spelling, `sources.csv` is deprecated (warn-only,
read exactly as before), and four reference examples already carry the new name. Its ledger line is in
[RM52](ROADMAP_1_0.md#rm52--10-ships-an-upgrade-procedure-or-10-does-not-ship). What stays here is the half that
genuinely breaks a reader: `sources.parquet`
is in `_OUTPUT_FILES` and therefore inside `artifact.digest`, and consumers read it by name;
`manifest.sources` is a published key. Renaming either is a **removal**, so both are major-only. The old
CSV spelling retires on the amended cadence (Principle 3, 0.6 amendment): **deprecated in the 0.6 minor
that adds the alias, removed at 1.0** — deprecation is warn-only and needs no major, and an author
carrying `sources.csv` can act on it the day they read the warning, which is the condition that makes a
minor the right place for it.

**Disposition:** at 1.0, rename `sources.parquet` → `licensing.parquet` and the `manifest.sources`
block → `manifest.licensing`, and drop the `sources.csv` spelling deprecated in 0.6 — with the upgrade
line RM52 makes mandatory, which here is a file rename and a recompile.
**`licensing.csv` is the recommendation**: it names what the file is *for*
and what the gate reads it for, and it cannot be confused with a `source` cell. `data_sources.csv` is
the conservative alternative (a smaller change in meaning, but it keeps the collision with the column
and only lengthens it). `provenance.csv` is out — it collides with `manifest.provenance`, which is a
different thing — and `attribution.csv` is out because it undersells the half that refuses a compile.
Renaming the *column* is a separate and larger question and is **not** proposed here: `SourceRow.source`
is inside its own fact set, so it is the row's key, and every other table's `source` already means what
RM33 settled it to mean.

Note what this does **not** unblock: the file's shape is already right. A rename is legibility only,
which is exactly why it waits for a major rather than justifying one.

### `fetched_at` — the column says *fetch*, the value means *write*

**Severity** low (nothing has broken; the name mis-describes what is in the cell) · **Status** queued
for 1.0 — **bundle with the `sources.parquet` rename above, or decline explicitly**

Seven sidecar models carry `fetched_at` — `ResolutionRow`, `FrequencyRow`, `GeneMetricsRow`,
`LiteratureRow`, `GeneValidityRow`, `ClinicalAssertionRow`, `SourceRow`. The name says the row records
when a source was fetched. It does not. Its own field description has to correct it in prose —
*"records when this row was last written by a pass, not when the source published anything"* — and a
description that opens by contradicting its field name is the tell, the same one the `sources.csv`
entry above is built on.

**What the value actually is, measured rather than argued.** Every sidecar merge is never-clobber, so
an already-recorded row wins and its stamp is never rewritten. `record_source_terms` run twice against
one spec directory leaves the file **byte-identical**; only deleting the sidecar re-stamps
(`2026-08-16T02:02:24Z` → `…02:02:27Z`, with `source_signature` unchanged across all three states).
So on an ordinary re-run — including one that really did go and ask the source — the column records no
fetch whatever. It records **when this row's facts were first set**. That is a useful thing to have and
a reasonable thing to publish; it is simply not what it is called. Established independently at
[S7](history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md#s7--sourcescsv-stamps-fetched_at-into-the-digest-so-a-rebuild-is-never-reproducible),
which probed the same `setdefault` and answered the *behaviour* question; the naming question was never
put.

**Be honest about the evidence: no incident is attributable to the name.** S7's proximate cause was
SCHEMAS.md calling `artifact_digest` the "content identity", and it was fixed there. Nothing has
misread `fetched_at` itself. That is exactly why this is low severity and why it does **not** justify a
major on its own — and why the disposition below is *ride along*, not *schedule*.

**What it costs, checked.** `fetched_at` is outside all seven fact sets (verified against
`RESOLUTION_FACT_FIELDS` and its six siblings), so **no signature moves** — not `content_signature`, not
any `*_signature`. It is a column in six parquets (`resolution.csv` alone has none by design), so
**`artifact.digest` moves on every module carrying a sidecar**. Blast radius at 0.6: 36 occurrences in
`schema/src`, 5 in `compiler/src`, 34 in `enricher/src`, 51 across the suites, and 27 reference-example
files.

**The rename obliges one semantic decision, and it is the substance of the item.** Two writers rewrite a
recorded row without touching the stamp: `licensing.withdraw_stale_dataset` blanks `dataset`, and
`provenance.stamp_draft_digest` re-labels `draft_digest`. Under `fetched_at` that silence is plainly
correct — nothing was fetched. Under `updated_at` the row was *updated* and the stamp did not move,
which is a new small untruth. **Recommendation: leave both silent and say so in the description** — the
value dates the row's **facts**, and a provenance-column rewrite is not a new fact. That reading is also
what keeps the delete-and-re-derive drift check sharp (see
[MODULE_LIFECYCLE § 5.1](MODULE_LIFECYCLE.md#51-reading-a-digest-move--the-canary)): a stamp that moved
whenever any cell was rewritten would stop separating "these facts are from that moment" from "somebody
touched this row". If that reading is adopted, the honest name is arguably `recorded_at` rather than
`updated_at`, and the choice should be made deliberately rather than by reaching for the database
convention.

**No 0.x deprecation step, and the cadence's own condition is the reason.** Principle 3's 0.6 amendment
puts a deprecation in a minor **only where its audience can act on it**. Nobody authors this column —
all seven writers are machine passes — and an author *cannot* pre-emptively rename it, because
`extra="forbid"` rejects the unknown column. A 0.x warning would therefore be a finding no authored edit
can clear, which this project treats as a defect wherever else it appears (P5). So: a straight rename at
the major, mitigated on the input side rather than by a warning.

**Mitigation — accept the old spelling on read through the 1.x line.** The writer emits the new name; the
loader keeps accepting `fetched_at` as a deprecated input spelling, so a hand-maintained or downloaded
0.x sidecar keeps loading and the author-side upgrade route is *no action needed*. This is RM51's shape
one layer down, and it is what makes the ledger line below cheap.

**Why this is not the column rename the entry above declines.** That one refuses to touch
`SourceRow.source` because it "is inside its own fact set, so it is the row's key". `fetched_at` is
the exact opposite: outside every fact set, keyed by nothing, joined on by nothing, derived from by
nothing. The stated reason for declining there is the reason this one is cheap.

**Disposition:** rename at 1.0, **in the same change as `sources.parquet` → `licensing.parquet`**. That
item already moves `artifact.digest` on exactly the modules this one would, so bundling spends a cost
already being spent and the two share one upgrade line; taken alone this item would be a digest move for
legibility, which is not a trade worth making. Decide `updated_at` vs `recorded_at` when the semantic
question above is settled — the two names encode different answers to it. If the `sources.parquet`
rename is declined, decline this one with it.

### Deprecated flag/vocab aliases

**Severity** low · **Status** queued for 1.0 — collapse to the canonical vocab

Any transitional vocab kept for 0.x compat (e.g. the trimmed-vs-full `state` set).
**Disposition:** Collapse to the canonical vocab at 1.0.

### `ModuleManifest.authors: list[str]` + free-form `curator`

**Severity** medium · **Status** queued for 1.0 — fold into RM14's record

Flat and overloaded — no role (created/edited/audited), no kind (AI/human); `Defaults.curator`
smuggles kind via its `"ai-module-creator"` default. Superseded by the structured authorship
record (RM14) once it ships. **Disposition:** Keep both as derived projections through 0.x (P8);
at 1.0 fold `authors` into the structured record and drop the kind-smuggling `curator` default.

### `StudyRow.pmid` required + PMID-shaped

**Severity** medium · **Status** queued for 1.0 — a requiredness demotion

Mandatory `pmid` (must parse to a real PubMed id) rejects DOI-only provenance — preprints
(bioRxiv/medRxiv), books, theses, datasets. Demoting a required field is P8-forbidden in-major, so
adding optional `doi` (RM11) alone can't unblock it. **Disposition:** **doi-first at 1.0**: make
`pmid` optional/legacy and require **≥1 of `{doi, pmid}`** (every citation has a stable id, not
necessarily a PMID; the reverse holds). Requiredness change → major-only. **Pairs with RM50**, which
carries the PMCID axis and the `LiteratureRow` key question: this entry decides what a *study row* may
be authored with, and says nothing about what the pmid-keyed sidecar does with a row that has no PMID.
Settle both in one release.

### Compiler `ensembl_cache` deprecated shim

**Severity** low · **Status** queued for 1.0 — remove the parameter

0.5 already moved the whole DuckDB resolver + cache-location into `just-dna-enricher` and dropped
`duckdb`/`platformdirs`/`python-dotenv` from the compiler (it is now pure-Python; resolution is
the `resolution.csv` table). What remains is the `compile_module(ensembl_cache=…)` **surface**,
kept as a deprecated shim that emits `DeprecationWarning` and routes to the enricher via a guarded
import. **Disposition:** Remove the `ensembl_cache`/`resolve_with_ensembl` params outright at 1.0
(internal call, not the wire/artifact contract, so additive-within-major does not protect it).

### Coordinate-first identity (option C)

**Severity** — · **Status** ✅ resolved in 0.5 by VRS — kept for traceability

The objection was that a coordinate key is *build-baked*. A **VRS allele id is not**: it names its
reference sequence by refget accession, so it satisfies RM15's own reconsideration condition.
`variant_key` now derives from the VA for a resolved substitution; rsid-keyed, position-only,
indel and multi-allelic rows keep their previous keys. **Disposition:** **Done, in 0.5.0's
pre-publication window** — an identity-semantics change is major-only because `variant_key` sits
in `artifact.digest`, and that gate is *publication*, not the version number: 0.4 is the published
line and 0.5.0 never shipped, so it rode the same one-time re-baseline as the alt-carrying key. No
published artifact moved.


## Reserved namespace

Because backward-compat makes column names and vocabularies **permanent within a major** (CONSTITUTION
Principle 5), a name expected to become a real **module column** later is reserved against the one-way
door and **must not** be claimed early or smuggled in as `flags`. This list is *only* for genuine
anticipated module-side axes — it is **not** a catalogue of names that "may not appear" (that space is
unbounded and pointless to enumerate; barring `caller` would be as arbitrary as barring `pasta_recipe`).
Audit every new name against this list before adding it.

**Enforced now** (the live set is `just_dna_format.vocab.RESERVED_NAMES_0_4`). Every authored model
inherits `AuthoredModel`, which sets `extra="forbid"` (rejects *any* unknown column) **and** runs the
`reject_reserved` before-validator, so a reserved name fails with a *specific* diagnosis — what it is
reserved for + that a release may claim it (`vocab.RESERVED_NAME_REASONS`) — while a random/misspelled
column gets the generic "extra inputs not permitted":
- **`reference_db`** — a module-side hint naming *which* reference database the app should join this
  annotation against when several exist (implicit Ensembl for variants / ClinVar for `clin_sig` today;
  a module may pin it, e.g. a specific PharmVar release). Annotation-side addressing, a real future axis.
- **`callable_element`** / **`quality_element`** — added in 0.6 by RM54, which built `source_element` on
  the binning tables and deliberately did not build these two companions on `VariantRow`'s pointers: no
  module points `callable_from` or `quality_from` at a multi-valued field, and an authored column is
  full cost. They are reserved rather than merely absent because the symmetry makes them guessable — an
  author reasoning "if `source_field` has one, `callable_from` must too" should hear what the name is
  held for, not the generic stray-column message.

*(**`callable_from` was reserved here through 0.4 and is now BUILT** as a `VariantRow` column in 0.5
(RM6). A built name must leave this list: `reject_reserved` refuses a reserved column at author time,
so leaving it would make the very column the release added unwritable.)*

*(`caller` / `caller_version` were reserved through the 0.4 draft as a "provenance triple" (round-2 Q2)
but are **dropped**: they name which tool produced a *call* — a consumer-side measurement, never module
annotation — so there is no future module axis to hold, and barring the bare name is arbitrary. A
consumer records them on its own call data; a module never carries them, and `extra="forbid"` rejects
them like any stray column. `reference_db` stayed because it has a real annotation-side meaning above,
not the caller-provenance one it was first reserved under.)*

**Planned future annotation axes** (documented intentions, **not yet in the enforced set** above — they
are rejected generically by `extra="forbid"` today, and get a slot + a specific diagnosis only when a
release actually commits to building them):
- **`consequence`** — VEP molecular consequence (Sequence-Ontology term, e.g. `missense_variant`).
  Distinct from `direction` (phenotypic) and `clin_sig` (clinical). **Never repurpose the bare word
  `effect`** for it.
- **`impact`** — VEP impact `{HIGH, MODERATE, LOW, MODIFIER}`, derived from `consequence`.
*(**`allele_frequency`** + **`af_population`** were listed here and are now **built in 0.5 as a
table, not a column** — `frequencies.csv` → `FrequencyRow`, one row per (allele, ancestry group).
A column pair could carry one number for one population; frequency is inherently per-group, and
flattening it onto the variant row would smear two axes together. So the planned axes are retired
rather than shipped. Gene-level constraint arrived beside it as `gene_metrics.csv`. See
[SCHEMAS.md](SCHEMAS.md) and [USE_CASES.md §6](USE_CASES.md).)*

*(`doi`, `provenance_quote`, and `provenance_regex` were reserved here for RM11/RM12 and are now **built**
as optional `StudyRow` columns in 0.4 — so they are absent from this list. The **doi-first** flip that
relaxes the mandatory `pmid` remains a 1.0 item; see the 1.0-cleanup tracker.)*

*(The ploidy / non-SNV quantities that were reserved through 0.3 — `allele_fraction` / heteroplasmy,
`repeat_count` + `repeat_unit`, copy-number dosage — are **built** as the 0.4 binning primitive; the
`hemizygous` genotype case ships via the widened single-allele genotype. Symbolic/structural alleles
remain open as RM5.)*


# The idea-book

## Freeform suggestions — the 0.5 idea-book

The consumer's grounded 0.5 ideas (kept inside the one constraint: **VCF-based, possibly augmented on
top**) came from the round-2 thread, retired on 2026-08-18 with its per-item disposition recorded in
[history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md](history/CONSUMER_SUGGESTIONS_HISTORY_PRE_0_6.md) and
its prose in git at `635da8c`; each idea was run through the what-blocks lens in
[USE_CASES.md](USE_CASES.md) §1. Standing dispositions:

- **3a — module declares where its measurement lives in a VCF.** ✅ Taken early: `source_field` shipped
  in 0.4 (an optional, `|`-alternatable field-name token on every binning table — a *declarative
  pointer, not an expression*, inside Principle 1), and **qualified with its namespace since 0.6**
  (RM53). The "zero glue" claim as first written was **falsified by the schema it described, and the
  prose knew something the data model did not**: it spells the pair `INFO/RU` and `FORMAT/REPCN` with
  the namespaces attached, which is how a VCF user writes them and how the *reader* of this line
  understood it — while the column accepted a bare token only, so `RU` and `REPCN` reached a consumer
  with the half that disambiguates them stripped off. 0.6 accepts the qualified form, warns on a bare
  key that INFO and FORMAT both define, and adds `source_element` for the second half the claim also
  assumed away: `REPCN` carries **both** repeat alleles, and the clinical rule for a dominant expansion
  is *the larger*, which no pointer could previously say.
- **3b — modules as a deterministic verification harness** (run a panel against N VCFs, emit a
  byte-diffable report-card). **The strongest idea, and it needs *nothing* from the format:** a panel
  is already a module, `source_field` names the field to read, `artifact.digest` makes the before/after
  diff trustworthy, and the mandatory `unresolved`/callability contract stops a no-call masquerading as
  a mismatch. It is a **consumer** feature (`just-dna-lite`); the format only supplies properties it
  already froze. Recorded as an *enabled* use case, not a gap.
- **3c — augmented-VCF as the landing pad** for cracked short-read loci (a synthetic `<STR>` record with
  `INFO/RU` + `FORMAT/REPCN` + custom evidence fields, consumed through the same `source_field=REPCN`
  path). Endorsed as the interface — the format binds to the VCF, it does not reinvent it. Consuming the
  *symbolic* alleles themselves is RM5.
- **3d — smaller VCF-native ideas:** callability three-state → RM6; phasing-aware panels → already
  expressible (the `phased` flag + VCF `PS`/`HP`); trio/de-novo assertion → RM10.

### Parked in 0.5 (recorded so they are not re-proposed as if new)

- **Enricher co-authoring** (permission-gated writes to *authored* files, not just sidecars). Attractive
  — it would let a stale rsID or a missing DOI be fixed where it actually lives instead of only being
  reported — and deliberately **not** taken, for a reason stronger than tidiness: `content_signature`
  is *defined* as pre-resolution and reference-independent ("computed from the rows before resolution,
  so recompiling against a different/complete reference does not change it"). If a network fetch could
  edit `variants.csv`, the content-dedup identity would become network-dependent and that documented
  property would simply be false. A secondary problem: `authorship` records who wrote the module, and
  an enricher that edits rows either falsifies that record or must add itself as an `ai`/`agent`
  contribution — coherent, but a much larger design than it first looks. Revisit only with both
  answered.

  **The drafting helper is not this item, and the line between them is one word: *mutate*.** The 0.5
  helper appends rows a source publishes into an authored CSV; it never rewrites a cell that is already
  there. Appending happens at authoring time and leaves `content_signature` a function of the authored
  bytes exactly as before — the property that would break is the one where a *fetch* changes the meaning
  of rows the author already wrote. So a row whose natural key is already present is **reported, never
  overwritten** (drift on existing rows is the cross-check pass's job, `pgx.enrich_pgx`), and the helper
  stamps no `authorship`: it transcribes a published table, and the human owns the module. Dedup keys on
  the compiler's own `_TABLE_DUPE_KEYS`, so an append can never produce a row the compiler would then
  reject as a duplicate, and rows are appended **at the end** — authored row order is preserved through
  compile → reverse → recompile, so re-sorting an existing file would move a compiled module's digest.

- **Escalating the ClinVar `clin_sig` cross-check when the disagreement is with an expert panel.**
  Tempting, because a VCEP or practice-guideline assertion genuinely is a different kind of claim from a
  one-star submitter's, and the snapshot already carries `review_status`/`review_stars` to tell them
  apart. Not taken: this is the one check that warns in **both** modes on purpose, because failing a
  compile over a clinical disagreement makes the format arbitrate a clinical dispute, which the
  data-agnostic charter forbids — and a curator who has read the primary literature and disagrees with a
  submission is doing their job. The tier is already *surfaced* (`clinical.ClinSigFinding.confidence`
  puts it in the message), and persisting it as queryable data is RM25. Surface it, let the consumer
  route on it, do not decide for them.

- **An offline allele-frequency snapshot.** The obvious symmetry with the ClinVar and gene-constraint
  snapshots, and it does not work: gnomAD v4.1's sites VCFs are **58 GB** (exomes) and **742 GB**
  (genomes), so there is no slice to ship at any useful coverage. Frequency is therefore the first and
  only **online-only** link in the chain. This is not a reproducibility hole — once `frequencies.csv` is
  written it *is* the pin, and every later compile reads it offline and deterministically. Revisit only
  if gnomAD publishes a small pre-aggregated frequency release.
- **HGVS string generation** (`c.`/`p.` notation). `ga4gh.vrs`'s extras pull `hgvs` transitively, so it
  would be *available* — but HGVS generation is its own feature with its own argument (which transcript,
  which reference, how to present ambiguity), and taking a dependency for indel normalization does not
  commit to shipping it. Deferred as a feature, not blocked by tooling.
- **Multi-build VRS minting.** A second refget table beside `REFGET_GRCh38`; the remaining half of RM15.
- ~~**dbSNP obsolescence / merge checking**~~ — **built in 0.5** as `identifiers.check_rsids`, wired
  into `enrich()` behind `--verify-rsids`. Two corrections to what this entry used to claim, both found
  by probing: it is **not** "detectable two ways" — Ensembl REST resolves *some* merges (`rs77121243` →
  `rs334`) and returns **HTTP 400** on others (`rs3216883`, which dbSNP correctly reports as merged into
  `rs3051860`), so Ensembl alone would misclassify a merged rsID as unresolvable. **NCBI `esummary
  db=snp` is the oracle**, batched and authoritative. See *the stale-identifier collision* below for
  what is done with the answer.
- **Sex-stratified frequency counts.** gnomAD serves `nfe_XX`/`XY`; sex is a second axis, and folding it
  into `population` would be the `state`-overloading mistake again. A future `sex` column on
  `FrequencyRow` is the additive shape if it is ever wanted.
- **`google-re2` for `provenance_regex` matching** (candidate, only if the current bound proves
  insufficient). The enricher matches `provenance_regex` against fulltext with stdlib `re` inside a
  killable child process (`literature.regex_matches`). That is a *bound*, not a linear-time guarantee,
  and the honest reason it is enough today is that the threat model here is a curator writing a slow
  pattern by accident — the pattern comes from the module being enriched and the document from a public
  archive, on the author's own machine, not an attacker meeting an arbitrary document.

  **The reason not to switch pre-emptively is capability, not cost.** Real fulltext has periodic
  structure — repeated section headers, boilerplate, tabular runs — and pinning a quote inside it often
  needs a **lookahead or lookbehind**. RE2 does not support either, so adopting it would narrow the
  pattern language the format offers authors, in exchange for a guarantee the subprocess already
  approximates. Revisit if `re` exhibits problems the process bound does not contain (a pattern that
  wedges a worker often enough to matter, or memory blow-up rather than time). If it happens, the shape
  is: keep `re` as the default, add `google-re2` as an optional accelerator, and record which engine
  ran — never silently change which patterns match.
- **Fulltext beyond the open-access subset** (candidate, cost-driven). OpenAlex and Unpaywall can point
  at a green-OA repository copy for some closed articles. Probed and *not* taken: the closed paper
  tested (`10.1038/s41580-019-0134-2`) has `is_oa: false` with no location at all, and the copies that
  do exist are PDFs — which would mean a PDF-parsing dependency in the network tier for a partial
  improvement on a check that is already labelled partial. The **abstract fallback shipped instead**,
  which costs nothing (the abstract is already in the Europe PMC response the pass makes) and covers
  four of five non-OA papers. Revisit only if authors report quotes that live in the body of closed
  papers often enough to matter.
- ~~**Google Scholar for citation existence**~~ — **rejected, not deferred.** It publishes no API, and
  automated querying violates its terms of service and is IP-blocked in practice. Crossref (DOIs,
  including preprints/books/datasets) and PubMed (indexed literature) cover the same ground through
  supported interfaces.



### The stale-identifier collision (design note, 0.5)

An obsolete authored rsID forces a choice that Principle 7 and "keep the module current" pull opposite
ways on, and it is worth writing down before anyone implements the lookup.

`weights.parquet` carries **both** `variant_key` and `rsid`, and for an rsid-authored row both are the
authored label. Writing the *updated* label into the artifact is not a one-time digest move — it is an
**identity migration performed by a network lookup**: reverse would then emit the new rsID into
`variants.csv`, the next compile would key on it, and `variant_key` itself would change. The module's
identity would drift without any authored edit, and the round-trip would stop being a fixed point.

So the rule is the one every other check here follows: **report, never repair.** Severity follows the
mode — `best_effort` warns and compiles with the authored label (digest stable, round-trip intact),
`strict` **refuses**, on the grounds that an all-or-nothing artifact should not be built on an
identifier its own source has retired. Failing is the honest move because it pushes the fix to where it
belongs: an authored edit.

That last clause is now load-bearing rather than rhetorical, and it is what qualifies this check for a
mode ladder at all. This entry used to cite "the VRS-unverifiable decision" as its precedent; that
decision was reversed in 0.5 for the half of it where **no authored edit could clear the finding** (an
indel the compiler cannot recompute stays a warning in both modes), which is precisely the test this
item passes and that one did not. An obsolete rsID is a cell a human can rewrite.

Two refinements, both now settled by the 0.5 implementation:

- **Merged ≠ withdrawn — and withdrawn is not observable.** This entry used to say "probe the withdrawn
  shape before deciding", on the assumption that a withdrawn rsID deserved failing in both modes. The
  probe was done, and it dissolved the question rather than answering it: `rs11273140`, a genuinely
  *withdrawn* id, returns a response **byte-identical** to `rs2000000000`, which was never assigned —
  the same `error` string from `esummary`, the same `count=0` from `esearch`, the same Ensembl 400.
  Routes checked and rejected for separating them: `esearch` has no withdrawn filter (the phrase is not
  indexed), and `latest_release/misc/rs_unsupported_b157.txt` looks like a withdrawn registry but is a
  one-off build-157 ClinVar-parsing incident list that does not contain `rs11273140`. Separating them
  would need a historical dbSNP dump, not the live API. So the vocabulary is **`live|merged|absent`**,
  not `live|merged|withdrawn`, and `absent`'s *message* names both readings and asserts neither —
  because guessing "typo" sends an author to fix the wrong thing when the truth is that the variant
  itself was retracted. Severity is the same ladder for both (warn / fail in `strict`), not escalated
  beyond it, since `absent` has benign causes too (a very new rsID, or API lag).
- **The new columns are provenance, not facts.** `rsid_current` + `rsid_status` sit **outside**
  `RESOLUTION_FACT_FIELDS`, beside `rsid_alternates`. They describe time-varying *external* state;
  inside the fact set they would make `resolution_signature` change when dbSNP merges something, with
  no change to the module — the signature would stop being reproducible from the module's own content.
  (Shipped as specified, with a test that pins it.)

One consequence worth recording, since it was previously filed as a loose end: **`reverse_module` does
not carry these columns, and that is correct rather than a gap.** Reverse rebuilds `resolution.csv` from
`weights.parquet`, which by design holds no provenance — it already resets `source` to `reversed`,
`status` to `resolved` and blanks `fetched_at`. `rsid_alternates`/`rsid_current`/`rsid_status` are out
of the fact set *precisely* so they never reach the artifact, so the information does not exist for
reverse to emit; adding the column names would produce a permanently empty header. Recovering them
after a round-trip means re-running the enricher, which is where a statement about a reference at a
moment belongs. What reverse *does* now carry back correctly is the resolved **facts** and the authored
**shape** — see [COMPILER.md § Resolution](COMPILER.md) for the enumerated round-trip contract that
replaced the old "reverse emits position-only" rule.

**The strategic reading:** this whole class of problem is *label drift*, and it exists only for
rsid-keyed rows. A coordinate-authored row keys on a VRS allele id, which is content-addressed and
cannot drift. The obsolescence check is therefore the standing cost of the rsID key, and the format
already offers the escape — author coordinates and carry the rsID as data (reverse already emits
coord-keyed rows as position-only). A strict failure is the nudge toward the drift-proof key.

## Freeform suggestions — the 0.6 idea-book

- ~~**IUPAC ambiguity codes in `ref`/`alts` — expand `Y` to `C,T`**~~ — **probed and rejected as
  specified; one small real defect survives it.**
  ([the code table](https://www.bioinformatics.org/sms/iupac.html): `R`=A/G, `Y`=C/T, `S`=G/C, `W`=A/T,
  `K`=G/T, `M`=A/C, `B`/`D`/`H`/`V` for the three-base sets, `N`=any, `.`/`-` a gap.) Recorded in full
  because the *reasons* it fails are reusable, and because the first draft of this entry asserted a
  premise nobody had checked.

  **The load-bearing premise has no instantiation.** The proposal rested on a code in an ALT column
  being a *compressed ALT set* — `Y` written once instead of `C,T`. Probed: **zero** occurrences of
  `R`/`Y`/`S`/`W`/`K`/`M`/`B`/`D`/`H`/`V` in REF or ALT across all **4,439,382** ClinVar GRCh38 records,
  and zero across all sixteen modules in this tree. Genuine ambiguity codes live in *sequence* contexts
  (consensus FASTA, array-manifest probes) and in *genotype* contexts (a Sanger heterozygote written
  `Y`) — the second of which is a **measurement**, so it is the consumer's by charter, and
  `AuthoredModel`'s genotype validator already refuses it with a clear message. Not one of them is a
  variant record's ALT. This is the "mechanically possible, never instantiated" anti-finding the
  dogfooding rule exists to catch, and the first draft of this entry walked straight into it.

  **The non-ACGT alleles that *are* real are `N`, and they are two different things, neither
  expandable.** 35 ClinVar records carry a single-base `A>N` — *the substituted base is unknown*, so
  expanding to `A,C,G,T` would assert four alleles ClinVar never stated. 633 more carry `N` **inside** a
  longer allele (`TAAAAAT…TTTGG` + `NNNNNNNNNN` + `AAAA…`) — unknown *interior* of a known-length
  insertion, not an ambiguity code at all, and 4¹⁰ expansions of nonsense. A rule keyed on "every
  character is a nucleotide or an IUPAC code" files the second as an ambiguity code, which is precisely
  the false claim `cpic.unusable_allele_reason` was already repaired to stop making about `DELTCT`.

  **And it is already solved, in the right place.** `clinvar_build` filters `^[ACGT]+$` on both alleles
  at the **snapshot builder** and counts what it skipped, so none of those 668 records ever reaches a
  drafted module. Skip-at-the-source-boundary is the pattern; it is implemented; for the only non-ACGT
  ALT that exists in real data it is the correct answer.

  **Both halves of the proposed repair were also wrong on their own terms**, and these are the parts to
  remember:

  * *"Normalize at the enricher boundary, like ClinGen's dosage codes."* The analogy does not hold.
    Those are decoded while **reading a source into rows the enricher authors**. An ambiguity code in
    `variants.csv` is **authored data**, where the enricher's standing rule is *report, never repair* —
    rewriting an authored value destroys the evidence of the upstream bug. The only legitimate site is a
    drafting provider at the moment of transcription, and every provider that meets one already refuses
    correctly.
  * *"Have the compiler reject the code by name."* Far larger than it sounds, and pointed the wrong way.
    **No nucleotide grammar exists on any of the eleven `ref`/`alt`/`alts` columns across six models** —
    `vocab.validate_allele` has **two** users, `HaplotypeRow.allele` and `VariantRow.effect_allele`
    (this said "exactly one" until 0.6; the count was wrong, the argument is not). Introducing one would reject
    `<DEL>` and `N` alongside `Y`, i.e. tighten the very field **RM5** exists to widen. It is also
    **Principle 3-illegal on the published line**: a module with `alts="Y"` *compiles today* under
    `best_effort` (the locus is dropped with a warning), so a grammar would stop an existing module
    validating. The first draft claimed such a module "is already broken by it" — checked, and false.

  **What survived was small, and it shipped.** `hosting_verdict("C/T", "T", "Y")` returns a confident
  **`False`**: a substitution locus has no spelling freedom, so a non-nucleotide alt reads as a positive
  contradiction. The author was told *their genotype does not fit their own locus* — true of the cell,
  false of the variant, and three steps from the actual mistake. A **diagnosis** defect rather than a
  grammar one, so fixing it needed no decision about what `Y` means:
  `alleles.non_nucleotide_reason`/`non_nucleotide_alleles` (format tier, the single definition
  `cpic.unusable_allele_reason` now delegates to) classify the offending allele, and both "cannot host"
  call sites say which of the two it is. Additive, digest-neutral, tightens nothing, orthogonal to RM5.
  The verdict itself is untouched — `False` was never the wrong answer, only the wrong explanation.


- **What an artifact should carry of the 0.3 axes — the residue of the `direction` report, and a 1.0
  question.** The documentation half shipped in 0.5.2: COMPILER.md's coverage row now names the tier
  each tick belongs to, and § Upgrade derivation says outright that `weights.parquet` carries the
  **authored** `direction` only, that an empty one on a legacy module is correct, and that a
  parquet-side consumer applies `derive.direction_from_state(state, weight)` itself. What is not
  settled is whether the artifact should ever carry the derived axes at all — a design question, not a
  version one: what bars it is that filling a blank asserts what no curator wrote. The candidate repairs
  and why each is wrong today —
  *populate at compile* asserts an axis no curator wrote (`state='significant'` has no direction, so
  one gets invented from the weight sign), *trim `state` to a derived mirror on load* is `upgraded()`,
  which belongs to the publisher's `needs_upgrade` flow rather than to the compiler, and `state` stays
  required under P8 regardless. Note for whoever picks it up: there is no numbered `RMn` for the 0.3
  orthogonal-axes work — it shipped in 0.3 and is tracked only in COMPILER.md, which is part of why
  this gap sat unattended. Reported as S5 in [CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md).

- **Rename the compiler's resolution master switch.** `compile_module(resolve_with_ensembl=False)`
  now *warns* when an injected `resolution.csv` is present and being ignored (0.5.2), which closes the
  silent-success half. The name is still wrong — it says Ensembl and means resolution of every kind —
  and a rename is a published-signature change, so `resolve` / `resolution=off|table|cache` is a 1.0
  item rather than a patch.

New ideas enter here as freeform suggestions, then graduate through the design cycle
(feedback → USE_CASES lens → PROPOSAL → shipped or parked as an `RMn` above).


- **`manifest.stats.genes` is derived from `variants.csv` alone, so a table-only module publishes
  `gene_count: 0`.** Relayed from just-dna-lite (2026-08-21), originally measured by
  just-module-creator; filed here because neither of us owns `variant_stats` and we could not tell
  whether it had already been reported. `compiler.py` computes
  `genes = sorted({v.gene for v in variants if v.gene})`, so a module whose gene is stated only in a
  PGx or binning table — `pharm_variants`, `haplotypes`, `diplotypes`, `allele_function`,
  `copynumbers`, `repeat_alleles` — publishes `gene_count: 0, genes: []` despite naming its gene on
  every row. The registry indexes `version_genes` straight off that field, so such a module is
  **unfindable by gene** in the catalog. Reported measured on a CYP2D6 `activity_phenotype` module,
  the corpus's own CYP2C19 example, and the shipped HTT manifest.

  Two candidate homes and we have no view on which is right: widen `variant_stats` to union the
  `gene` column of whichever families the module carries, or leave the manifest alone and index the
  PGx tables' `gene` directly registry-side. The first makes `stats.genes` mean "genes this module
  is about" rather than "genes in `variants.csv`", which is a semantic change to a published field
  even though it is additive in type — worth a Principle 3 read before it is treated as a minor.

  Consumer-side context: the symptom surfaces in just-dna-lite's discovery path, but nothing there
  can fix it — we read the field, we do not compute it. Full triage in that repo at
  `docs/reviews/consumer-handoff-triage.md`.

- **An authored `report:` block — let a module say how its rows should be presented.** Proposal from
  just-dna-lite (2026-08-21), from a survey of everything our report decides *for* a module. Full
  write-up with wiring points and the constraint list at
  `/data/sources/just-dna-lite/docs/MODULE_REPORT_CONFIG.md`; this is the format-side half.

  The bulk of what we found needs no format change at all — a module's `Display` block already
  carries `title`/`description`/`report_title`/`icon`/`icon_set`/`color`, and we never read it at
  report time: a locally compiled or registry-installed module gets it copied once into our own
  config at registration, and a module discovered remotely gets nothing at all, even though we fetch
  and validate its whole manifest to decide its kind. That is ours to fix and is planned on our
  side; noted here only because it is the reason the corpus looks like it has no display metadata.
  (One thing worth knowing on your side: `icon_set` is dropped on every path we have, so the
  vocabulary you validate it against has had no consumer here.) What is left over is a small set of
  decisions the *author* is better placed to make than any consumer, and which have nowhere to live:

  - **`categories:`** — key → `{title, description, order}`. Our report carries five hardcoded
    longevity pathway headings with hand-written prose, reachable only through a surviving
    `elif mod_name == "longevitymap"` name gate. The prose is a property of the module. Given a
    place to put it, the special case becomes a data check, and a second module wanting pathway
    sections needs no consumer code.
  - **`sort_by:`** — closed vocabulary over columns that already exist (`weight_abs`,
    `evidence_level`, `effect_size`, `clin_sig`, `priority`, `p_value`, `gene`, `authored`). We
    currently *guess* the ranking axis from the lead table: `abs(weight)` for weights-led,
    ClinPGx evidence rank for `pharm_variants`. That guess is right twice by luck and has no
    answer for the binning families.
  - **`preview_rows:` / a row budget** — how many rows lead before the fold. Ours is one global
    constant applied identically to a 20-row curated module and a 53k-locus ClinVar panel.
  - **`weight_display:` + a declared weight range** — strictly presentational. We are aware this
    borders on `Weighting`, whose docstring explicitly refuses a typed *precedence* field, and we
    are not asking to reopen that: nothing here blends, combines or reinterprets weights. The
    concrete defect is that our colour ramp hardcodes `min(|w|*200, 200)`, an implicit 0–1
    assumption, while RM92 correctly says the scale is free text — so a `log(OR)` module is
    coloured wrong and we cannot tell. A machine-readable range, or simply *do not render a weight
    column*, is the narrow fix.

  Shape we would expect, and which we think keeps it cheap: **advisory, same class as
  `panel`/`authorship`/`license`/`weighting`** — out of `artifact.digest`, out of
  `content_signature`, not reconstructed by `reverse_module`, additive-optional and therefore a
  minor under Principle 3 as amended. Absent is tri-state and must mean *the module has not said*,
  never a default; every module in the corpus predates it, so absent is the normal path for the
  whole 0.x tail.

  One thing we would ask the format to say out loud if this lands, because it is a contract point
  and not a consumer preference: **a `report:` block governs the presentation of the module's own
  content and nothing else.** It must not be able to suppress a consumer's integrity apparatus —
  an inferred/hom-ref-restored badge, a `locus_count > 1` ambiguity caveat, licence attribution,
  module provenance, or the record that a module was skipped. Each of those exists in our report
  because its absence previously read as a positive claim, and a knob that can turn one off is a
  knob that lets a module launder a caveat. Stating the boundary in the field docs is what stops a
  future consumer from implementing it the permissive way.

  No view from us on whether this is one block or several, or whether `categories:` belongs beside
  `module:` rather than inside a `report:` block — the placement is yours.

---

- **An absence that is a decision has no way to say so — `weight`, `weighting:`, `license`,
  `authorship`, and every sparse column.** From just-dna-lite's 2026-08-21 dogfooding pass (D5, D6,
  D12/D26), dispositioned below. One module authors no `weight` on 190 rows and declares no
  `weighting:`; six declare `version: null`, `license: null`, `authorship: []`; `direction`,
  `stat_significance` and `trait_efo_id` are empty across the whole corpus. In every case
  **"deliberately none" and "forgot" are the same bytes** — which is the house tri-state rule aimed at
  *authoring completeness* rather than at data, and the one place we do not apply it.

  Two halves that should not be answered by accident, because one is cheap and one is a schema
  decision. **A per-column fill count in `stats`** is one pass over rows the validator has already
  loaded, turns *what is there to curate* from a question into a table, and commits to nothing. And
  **a way to declare an absence intentional** — which is a new authored surface, full cost under P9,
  and needs a shape before it needs a field: `weighting:` already exists to say a module has no
  weights, so the question may be narrower than it looks (does the *presence* of the block, rather
  than a new field, discharge it?). The compile gate's precedent is that licensing is data rather than
  a flag, and `declared_use`'s is that a third state beats a mode.

- **A resolved ALT set that is a tandem ladder is a row in the wrong family.** From the same pass
  (D13). `superhuman` authors `rs56185968` as one `variants.csv` row with no coordinates and genotype
  `G/G`; resolution expanded it to a **23-allele** ladder (`G`, `GTGTG`, … up to 45 bases), which is
  where 22 of that module's VRS warnings came from. `repeat_alleles.csv` exists for exactly this and
  the authoring skill states the rule, but nothing notices. The signal is already computed, which is
  what makes it attractive.

  What stops it being an item today: *looks like a ladder* is a heuristic, and a false positive tells
  an author to move a row that belongs where it is. Wants a rule sharp enough to be an `info` at worst
  — and note it would have fired on a module whose other 22 warnings were the S67 flood, so the two
  interact.

- **Nothing checks a `conclusion` against the other cells on its own row.** From the same pass (D14),
  and the reporter measured it before proposing it: **20 hits in 1,418 rows, ≈60% precision by hand
  inspection**, which is why they asked for `warning` rather than `error`. Two of the finds are worth
  quoting because they are exactly what a curation check is for — `coronary` `rs17514846`'s `C/C` and
  `A/A` conclusions are **swapped**, and `rs11591147` is scored `protective +1.2` on `T/T` under text
  saying `GG` is protective. Two candidate rules, neither needing an external source: a conclusion
  naming a genotype **built from alleles at this row's own rsID locus** that is not this row's, and a
  `state` of `risk`/`protective` that the conclusion negates.

  The locus restriction is the idea that makes it tractable — an earlier version of theirs flagged
  *"raised plasma triglyceride (**TG**) levels"*. What has to be designed is the false-positive rate: a
  40% miss on a warning an author reads on every compile is how a channel stops being read, which is
  S68's problem arriving from the other direction.

## Consumer note (just-dna-lite, 2026-08-21) — a dogfooding pass over ten modules, and the eleven findings that are yours rather than the plugin's

**Nothing here is a request to change an artifact, and none of it is urgent.** We ran a
revision/curation pass over all ten modules in `data/interim/v1_port/` driven entirely through the
installed authoring surface (just-module-creator 0.18.0 against format / compiler / enricher
**0.6.6**), and wrote up 26 findings in
`just-dna-lite/docs/MODULE_DOGFOODING.md`. Seven of
them are the plugin's. The rest are compiler- or enricher-tier and are listed here so the plugin
maintainers do not have to relay them. **All ten modules validate clean with zero errors** — every
item below is about what a green run does and does not tell an author.

The corpus is a fair sample of the awkward cases: six hand-curated Gen-I ports (8–528 variants), three
ClinVar-drafted panels (57k / 70k / 309k variants), and one `pharm_variants`-led PGx module.

### The one we would rank first

**`_verify_vrs_ids` emits one warning per allele, and `_vrs_coverage` aggregates — so the
better-resolved module produces the flood.** (`compiler.py:2648` / `:2680`; § D2.)

| module | resolution rows | with `vrs_id` | indel rows | indel rows **with** `vrs_id` | warnings from `validate_spec` |
|---|---|---|---|---|---|
| `superhuman` | 101 | 101 | 47 | **47** | **85**, of which 80 are one VRS line per allele |
| `cardio` | 57,595 | 30,785 | 26,810 | **0** | **7**, of which 1 is the aggregated coverage line |

An absent id is "nothing to check" and lands in one tidy coverage sentence; an id that is *present and
not offline-justifiable* gets its own warning. Same underlying fact — an indel identity needs the
reference sequence — reported as one line or as eighty depending on whether the enricher happened to
mint something. A 190-row module is the worst case in our corpus, and it is the size a human is most
likely to be working on interactively. `_vrs_coverage`'s grouping already exists one function away.

### Presentation of findings (compiler)

- **§ D3 — `warnings` is `list[str]` with no code, no count and no cap.** On `superhuman` the three
  warnings an author can act on (8 het / 31 hom-alt / 46 ref-hom genotypes with no row) are items 83,
  84 and 85. A `warnings_summary: {code: count}` beside the list would be enough and breaks no caller.
- **§ D4 — nothing marks a warning an author cannot clear.** The VRS ones say it themselves
  (*"minted upstream by the enricher, not recomputable here"*) and sit at the same level as a real
  curation gap. `compiler.py:2634` already reasons about exactly this — *"a finding no authored edit
  could clear is not a `strict` matter"* — and applies it to severity but not to presentation. The
  `blame` discriminator is already computed.

### Messages that mislead

- **§ D19 — the `panel:` deprecation says "nothing else is lost", and for a drafted panel that is
  false.** (`compiler.py:3425`.) `cancer`'s block carries **425 genes**, a `significance` filter and a
  `reference_sha256`; the replacement — the licence row's `dataset` — carries `clinvar_2026-06-27`, a
  release *name*. `validate_spec` reports `gene_count: 298` for that module, so 127 panel genes yielded
  no variant and only the block being deleted distinguishes *not in the panel* from *in the panel,
  nothing found*. Worse, **`cardio`'s `dataset` cell is empty** — it was drafted 2026-08-10, before the
  drafter filled it — so following the instruction deletes its only record of which snapshot it came
  from, and `refresh_sidecar` will not backfill a sidecar that is already present. A conditional
  warning, or carrying `panel` into `manifest.json` the way `weighting` is, would settle it.

### Absences that pass in silence (compiler)

Each would be one extra clause on a warning that already fires, and the closure warning is the model —
it fires correctly on all ten.

- **§ D5 — `superhuman` has 190 rows with `weight` empty on every one and no `weighting:` block.**
  Green strict compile, `weights_rows: 190`, no remark. "Authors none deliberately" and "forgot" are
  the same bytes, and `weighting:` is the field that exists to tell them apart. We sum `weight` per
  module, so it renders 0.0 across the board while showing 190 findings.
- **§ D17 — eight of ten modules carry no `verification.json` at all** and nothing says so, while the
  two that do get a closure warning. *"A check that could not run is not a check that passed"* has no
  counterpart for the check that was never run.
- **§ D12 / D26 — the six curated modules declare `version: null`, `license: null`, `authorship: []`,
  and their `sources.csv` carries only an `ensembl / resolution` row** — nothing at
  `layer: annotation`. All six render *Not stated* for version, digest and terms in our report's
  *Modules in this report* table, which is the table that exists to tie a report to the bytes behind
  it. The licence compile gate is scoped to PGx sources, so originally-curated content gets no signal
  in either direction — no nag, and no way to record *deliberately unlicensed for now*.

### `stats` (compiler)

- **§ D7 — for a `pharm_variants`-led module the scalar counters are `0`, not `null`.** `pharmgkb`
  (1,482 rows) reports `variant_count: 0`, `unique_rsids: 0`, `study_count: 0`, with the real number
  only in `table_rows`. `unique_rsids: 0` is wrong rather than inapplicable — the table is keyed on
  `rsid`. This is the tri-state rule the format enforces everywhere else (*"null never means zero"*),
  inverted in its own output. A family-independent `row_count` would also help.
- **§ D6 — `stats` reports fill for `genes`/`clinvar`/`pathogenic`/`benign` and nothing else.** Five of
  our six curated modules have `category` empty on every row and `categories: []` is reported without
  comment; `direction`, `stat_significance` and `trait_efo_id` are empty corpus-wide. A per-column fill
  count is one pass over rows the validator has already loaded, and it turns *what is there to curate*
  from a question into a table.
- **§ D9 — `IFNL3;IFNL4` counts as a gene.** `pharmgkb` reports `gene_count: 33` including all three of
  `IFNL3`, `IFNL4` and `IFNL3;IFNL4` (33 rows carry the joined cell, straight from the ClinPGx export).
  Nothing flags a delimiter in a single-valued cell.

### `verification.json` (enricher)

- **§ D16 — the record counts findings and does not keep them.** `cancer`:
  `clinical_significance`, 141,616 subjects, **20 findings**, `detail: null`. `pathogenic`: 618,629
  subjects, **32 findings**, `detail: null`. Fifty-two rows in our two largest modules assert a
  `clin_sig` ClinVar disagrees with, and there is no way to learn which — no sidecar, and
  `review_queue` covers overrides rather than check findings. The MCP instruction block is emphatic
  that a mismatch means *check both sides*, and neither side is checkable for a finding you cannot
  name. A `verification_findings.csv` keyed on `variant_key` with both values would close it. Related:
  nothing rolls the count up into `validate_spec`, so a pass driven by the validator never learns the
  record exists.
- **§ D20 — `producer` is top-level over a merged record set.** `check_identifiers` on `cancer`
  correctly **preserved** the 0.6.4-produced `clinical_significance` record and appended three — and
  rewrote `producer` to `just-dna-enricher 0.6.6`, so the file now attributes to 0.6.6 a record it did
  not produce. `checked_at` survives, so it is recoverable. `producer` looks like it belongs beside
  `source`, `release` and `checked_at` on the record.

### Two the linter could take, and one routing question

- **§ D14 — nothing checks `conclusion` against anything, including the other cells on its own row.**
  It is `required`, `redundancy_bearing: null`, and absent from `attestation_bearing` — all correct,
  and none of that implies it cannot be *checked*. `lint_rows` over twelve real `thrombophilia` rows
  returned `errors: 0, warnings: 0` on a set containing `rs1799963 A/A` → *"**GA** carriers have 6.74x
  risk"* (the `A/G` row above it says *"GA carriers have 2.8x"*), `rs2519093 C/T` → *"**TT** genotype is
  associated…"*, and `rs1799889 G/G` with `state: risk` under text reading *"…is not increased"*. Two
  rules, no external source:
  - a conclusion naming a genotype **built from alleles at this rsID's own locus** that is not this
    row's — measured **20 hits in 1,418 rows** across the six curated modules, precision ≈ 60% by hand
    inspection, so `warning` not `error`. (The locus restriction is what makes it usable: an earlier
    version flagged *"raised plasma triglyceride (**TG**) levels"*.) The two worst are `coronary`
    `rs17514846`, whose `C/C` and `A/A` conclusions are **swapped**, and `coronary` `rs11591147`,
    scored `protective +1.2` on `T/T` under text saying `GG` is protective.
  - `state` is `risk`/`protective` and the conclusion negates it.
  - A third shape we are **not** proposing as a rule but would like somewhere to record a decision
    about: 480 `longevitymap` rows share a conclusion across genotypes carrying different weights.
    Plausibly correct for a GWAS port — the association is one statement and only the dose differs —
    but a reader sees identical prose and different numbers, and nothing in the module says whether
    that was intended.
- **§ D13 — nothing notices a row in the wrong family.** `superhuman` authors `rs56185968` as one
  `variants.csv` row with no coordinates and genotype `G/G`; resolution expanded it to a **23-allele
  GT ladder** (`G`, `GTGTG`, … up to 45 bases), which is where 22 of that module's VRS warnings come
  from. `module-tables` states the rule (*a repeat count is a binning table, not a variant row*) and
  `repeat_alleles.csv` exists for it. The signal — a resolved locus whose ALT set is a tandem ladder —
  is already computed.

### Two small ones

- **§ D11 — `just_dna_compiler/__init__.py` exports nothing.** `dir(just_dna_compiler)` is `[]`, so
  `from just_dna_compiler import validate_spec` raises `ImportError`; the working import is
  `just_dna_compiler.compiler`. Our own `CLAUDE.md` documented the top-level form, so the drift was on
  both sides — corrected on ours. Flagging only in case the empty `__init__` is unintended.
- **§ D10 — `logo.png` travels through a compile and is not on the registry's roster.**
  `just_dna_registry.specfiles.RECOGNIZED_SPEC_FILES` has 24 names and no image and no log;
  `compile_module` copies both into the output (verified — a compile of `superhuman` emitted
  `logo.png` and `v1_port.log` beside the five parquets). All ten of our modules ship a `logo.png` and
  we consume it in the module cards and the report. Whichever way it should go, it currently survives a
  compile and would not survive a server-side rebuild. No view from us on which is right — we would
  just like it decided and written down.

**Everything above is a note, not a request, and we are not tracking any of it.** Where an entry is
already covered by an item in `PROPOSAL_0_6_PT2` or `ROADMAP_0_7` that we have not read closely enough,
the existing item wins.

### Disposition of the note above — every finding, 2026-08-24

The note arrived in this file rather than in the inbox, so the triage ledger could not see it: an
inbox the ledger cannot see is a backlog nobody sees, which is the whole reason
[CONSUMER_SUGGESTIONS.md](CONSUMER_SUGGESTIONS.md) is the one door. Their prose is left byte-for-byte
above and this is the answer beside it. **Eight of the sixteen findings arrived a second time as
`Sn` items** from just-module-creator and were answered there; the other eight had no ledger entry of
any kind and are dispositioned here, because the reporter says they are not tracking them and an
undispositioned note is one nobody reads again.

**Answered as `Sn`, in [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md):** D2 → S67
(shipped, the VRS flood is grouped by reason). D3 + D4 → S68 (filed as RM131; the `blame`
discriminator they name is the item). D19 → S69 (shipped, both halves — the warning is conditional
*and* stopped claiming nothing else is lost). D16 → S70 (shipped: `detail` on the clin-sig record and
a findings warning; the sidecar is RM130). D20 → S71 (shipped, `producer` per record). D7 + D9 → S72
(`row_count` and the delimiter warning shipped; the `0`→`None` retype is queued for 1.0).

**D17 — "eight of ten carry no `verification.json` and nothing says so" — does not reproduce, and this
is the one worth reading.** A module with no attestation at all *does* warn: `_closure_warning` is
keyed on the **outcome**, not on the file, and its docstring says so — one sentence covers all three
ways a compile publishes no closure, because what an author needs to know is the same in each.
Verified by deleting `verification.json` from `apoe_epsilon` and re-validating: the closure warning
fires. What is genuinely absent is a statement that *no checks were run*, which is a different claim
from *authoring was never declared finished* — and it is deliberately not made, because warning about
an unverified module would fire on nearly every module in this repository.

**D11 — `just_dna_compiler/__init__.py` exports nothing — reproduces exactly** (`dir()` is `[]`,
`from just_dna_compiler import validate_spec` raises) **and is intended.** CLAUDE.md's own rule is
*avoid `__all__` / pure re-export `__init__.py`s — they obscure where a symbol lives*, so
`just_dna_compiler.compiler` is the supported import path and the empty `__init__` is the policy
rather than an oversight. The reporter corrected their side already. Related and now fixed: **S74**
shipped `load_spec`, because the symbol they actually could not reach was a private one.

**D5, D6, D12/D26 are one finding seen three ways, and it is the strongest thing in the note.** A
module that authors no `weight` on 190 rows and declares no `weighting:`; a `stats` that reports fill
for four columns and nothing else while `direction`, `stat_significance` and `trait_efo_id` are empty
corpus-wide; six modules declaring `version: null`, `license: null`, `authorship: []`. In each,
**"deliberately none" and "forgot" are the same bytes**, which is the tri-state rule pointed at
authoring completeness rather than at data. Filed below as an idea-book entry rather than an `RMn`
because the shape is undecided — a per-column fill count in `stats` is cheap and mechanical, while
*declaring* that an absence is intentional is a schema question, and the two should not be answered by
accident.

**D13 — a repeat ladder authored as a `variants.csv` row — is real and is the sharpest of the
remainder.** `superhuman`'s `rs56185968` resolved to a 23-allele tandem ladder, which is where 22 of
that module's VRS warnings came from, and `repeat_alleles.csv` exists for exactly that. They are right
that the signal is already computed. Idea-book below; it is a check with a clear input, and what stops
it being an immediate `RMn` is that a resolved ALT set that *looks* like a ladder is a heuristic, and a
false positive tells an author to move a row that belongs where it is.

**D14 — nothing checks `conclusion` against the other cells on its own row — is real, is measured, and
the measurement is why it is not filed as a check yet.** Their own number is **20 hits in 1,418 rows at
≈60% precision**, and they proposed `warning` rather than `error` for that reason. Two of their finds
are serious enough to quote: `coronary` `rs17514846`'s `C/C` and `A/A` conclusions are **swapped**, and
`rs11591147` is scored `protective +1.2` on `T/T` under text saying `GG` is protective. A 40%
false-positive rate on a warning an author must read every compile is the thing to design against, and
their locus-restriction is the idea that makes it tractable. Idea-book below. Their third shape — 480
`longevitymap` rows sharing a conclusion across genotypes with different weights — they explicitly did
not propose as a rule and we are not treating as one; it is the *"nothing says whether that was
intended"* problem again, which is D5's shape.

**D10 — `logo.png` and the log survive a compile and are not on the registry's roster — is a real
cross-repo inconsistency and is not ours to settle alone.** Verified on our side: `compile_module`
copies both into the output deliberately (`logo_file`/`log_files` are parameters, `manifest.logo` and
`manifest.logs[]` are published entries). `RECOGNIZED_SPEC_FILES` is the registry's list. Either the
roster grows or the copy stops, and the reporter is right that the current state means a module
survives a compile and would not survive a server-side rebuild. Raised with the registry rather than
decided here; recorded so it is not lost.
