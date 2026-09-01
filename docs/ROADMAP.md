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
  Everything filed *behind* the first round accumulated in the minor-deferral file because that was the
  next release
  at the time; PT2 re-asked which release each belonged to now that 0.6 is uncut, and took five back:
  RM55's fix, RM72, RM82, RM84 and RM87. It is authoritative for those five, and for three of them the
  probe overturned what the roadmap entry says.
- **[ROADMAP_0_8.md](ROADMAP_0_8.md)** — items legal in a minor, each waiting on a design question, a
  corpus or a caller. RM10 closed there, folded into RM28. **It succeeded `ROADMAP_0_7.md` at the 0.7
  cut** — that round is closed in [history/](history/ROADMAP_0_7.md), which keeps four of the five
  records the line above names; only RM84 is still waiting and still here. **Read the membership rule in its header, not a list here**:
  these two bullets carried per-item enumerations until 2026-08-27 and both had gone stale, which is
  what let RM69 sit in the 0.7 file gated on a 1.0 item without anyone noticing.
  [RM_TOC.md](RM_TOC.md) is the complete list, and it is the only one.
- **[ROADMAP_1_0.md](ROADMAP_1_0.md)** — items that need a major, the one that is release-blocking for
  it, and (since 2026-08-27) items *gated on* a major without needing one. Plus the upgrade ledger.
  **The 1.0 cleanup tracker below did not move** and stays the home for the unnumbered major-only items.

Code comments citing "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs — follow them
to [CHANGELOG.md](CHANGELOG.md) / [COMPILER.md](COMPILER.md).

**Status:** **0.7.0 is bumped and not tagged.** The twelve items `PROPOSAL_0_7.md` decided have all
landed on the `0.7` branch, the release record is measured, and the three `pyproject.toml` files read
`0.7.0` since 2026-08-31; **the tag is the one remaining step and it is the maintainer's**, so work
still sits on top of `v0.6.6` as far as git is concerned.
The last cut release is **0.6.6, tagged `v0.6.6`** (2026-08-21) — It carries **nine patch fixes**: the 2026-08-19
doc-audit round (RM104–RM107, RM109, RM111), the two shipped items of the S57–S60 batch (RM121, RM123),
and S61's lookup fix (RM125). RM122 and RM124 were the two of that batch not in it; RM124 has
since shipped in 0.7.
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

**Seven** (the count is the `## RMn` sections below — it
read "four as of 2026-08-21" for two rounds after it stopped being four, then *not one of them is a
decision* through the three that are, then *three* for the hour it took a fourth to be filed, then
*two* until RM151 shipped, then *one* naming RM152, then *one* naming RM153, then none, and now
seven — which is why the paragraph under it says to count off the sections rather than off this
sentence).

**Six of the seven are one round: the 2026-09-01 source-adoption round, RM163–RM168.** They were asked
for as a batch — *what else should we adopt as enrichment sources, besides CIViC and PubMind* — and are
filed together because they share a shape and a discipline rather than a mechanism. Three of them
(RM163, RM164, RM165) come out of one measurement: a drafting **provider** exists for four of the nine
table kinds, and `heteroplasmy.csv`, `repeat_alleles.csv`, `copynumbers.csv`, `pgs.csv` and
`activity_phenotype.csv` have no source behind them at all. The other three each name a source that a
*procedure* already leans on without the code knowing (RM168), a second authority on a lane that is
currently a single licence class (RM166), or an axis a source we did adopt structurally cannot serve
(RM167).

**Not one of the six has been probed, and every entry says so in its own words.** Each separates what
is *measured* — a table kind with no provider, a snapshot's actual contents, a number from a probe
already run — from what is merely *candidate*, and **none asserts a licence**. That split is the whole
discipline of the round: the failure it is most likely to cause is a remembered licence or a remembered
API hardening into a permanent false constraint in these files (`@probe-names-the-table`), so each
item's **first step is the probe**, and a negative closes the item rather than leaving it open. Two of
them, RM164 and RM166, name in advance the finding that would close them.

**RM166 may not be a new source at all** — if ClinPGx's own drug-label download already carries the FDA
content, it is a second file from a source already adopted, which is a cheaper item with a different
terms answer and a different owner. That question is its first line of work for exactly that reason.

The candidates deliberately **not** filed are not restated here: the predictor tier is RM23, authored
PRS weights are RM16, and Google Scholar, OpenAlex/Unpaywall fulltext and an offline gnomAD frequency
snapshot are dispositioned in the 0.5 idea-book below. Academic-only sources (OMIM, dbNSFP) and
subscription-gated ones (HGMD) are out on terms; callers (PharmCAT, Cyrius, PyPGx) are out on scope,
which is *Annotating core, not format scope* further down.

**RM152 and RM153 both arrived and both shipped on 2026-08-31**, which is the sequence worth keeping.
RM152 stood here carrying **no release class**, on the stated grounds that both its candidate
adoptions had been refuted and an item with no repair has none to state — the correct state for it.
What changed that was a measurement, not an argument: the probe it had named was run, both refutations
held, and a third route nobody had proposed turned out to be buildable with no schema change. RM153
was its residue, and it answered its own two questions in opposite directions — the ClinGen CAID pass
taken, liftover refused with its ceiling measured at 13 evidence rows. Both entries are in
[ROADMAP_HISTORY](ROADMAP_HISTORY.md); the measurements are in
[CIVIC_SURVEY](probes/CIVIC_SURVEY.md) and [CIVIC_UNRESOLVED](probes/CIVIC_UNRESOLVED.md).
RM151, filed on 2026-08-31 the same day RM117's other half shipped, was built the same day. Both items
the RM124 wave-1 audit filed — RM136 and RM137 — shipped on 2026-08-31, and so did RM117's
observability half and RM146; RM138 was closed the same day with its numbers measured. RM110, RM103's
manifest half and RM108 were three more settled ones and all three shipped on 2026-08-31.

**Count them off the sections, not off the sentence**: this line said *three* for as long as it took
to notice that a narrowed item is still an item, *not one of them is a decision* for as long as it
took three decisions to be filed beneath it, and *two* while one of the two was already built — the
same arithmetic failure recorded two paragraphs down, three times more.

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
outright, **RM122** parked on demand and moved to the minor-deferral file ([ROADMAP_0_8.md](ROADMAP_0_8.md) since
the 0.7 cut), **RM117** narrowed
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
[ROADMAP_0_8.md](ROADMAP_0_8.md) / [ROADMAP_1_0.md](ROADMAP_1_0.md) hold the deferred items.
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
the release that will decide it — [ROADMAP_0_8.md](ROADMAP_0_8.md) (RM16, RM23, RM28, the deferred
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

**It happened a second time, to RM160, and the repair is the same one line.** Filed 2026-09-01 as
`open — worth doing` with owner *enricher*, it was appended below the same heading and sat under *Not
format scope* — a section whose own intro says it lists things "so they are not mistaken for format
scope" — until the 2026-09-01 source-adoption round moved the boundary back down to RM7. Twice is a
pattern rather than a slip: **appending an item to this file puts it wherever the last heading left
you**, so check which `# ` heading you are under before writing the section, not after.

The trackers further down are the other live part of this file: the reserved-namespace tracker and the
1.0-cleanup candidate tracker, which the Constitution deliberately keeps out of itself.

## RM170 — a source that both asserts and refutes a claim is muddy water, and nothing tells an author

**Severity** medium · **Status** open — **worth doing** (maintainer, 2026-09-01) · **Owner** enricher
· **Motivating case** the RM169 widening, which made the first such variants visible in a built
snapshot

**A second corpus exists, found while probing RM165 (2026-09-01) — design against both, not against CIViC alone.** STRchive's `evidence` field is a ClinGen-style validity call on **all 82** of its repeat loci, and its members include **`Disputed` (3) and `Refuted` (1)** beside Definitive 46 / Limited 14 / Moderate 8 / Provisional 6 / Strong 4. That is this entry's shape in a different domain and on a *published, closed vocabulary* rather than CIViC's per-record assertion/refutation pair — so the two corpora disagree about where the contradiction lives (a field vs. two rows), which is exactly the sort of thing that decides a record shape. Probe both before fixing one.

**The correction this item starts from.** It was reported during the RM169 round that reading
submitted evidence would make three VHL variants `contested` and so stop them being drafted. That was
wrong, and the way it was wrong is the item. `contested_variants` counts a variant whose camps include
**both** `risk` and `protective` — genuine opposition — and a `Does Not Support` row does not enter a
camp at all: `CIVIC_DIRECTION_MAP` maps it to `None`, because a refutation removes a claim without
establishing the opposite one. So `contested_variants` is **0 on both bases**, correctly, and the
drafter withholds nothing new.

But the three variants are real, and an author has no way to learn about them:

| variant | claim | refutation |
|---|---|---|
| 2161 `VHL S183L (c.548C>T)` | 2 supporting items | ev 8721 `DOES_NOT_SUPPORT` |
| 2428 `VHL G104V (c.311G>T)` | 1 supporting item | ev 10949 `DOES_NOT_SUPPORT` |
| 2533 `VHL D126N (c.376G>A)` | 1 supporting item | ev 8721 `DOES_NOT_SUPPORT` |

Each carries a claim **and** a published rebuttal of that claim. The snapshot keeps both rows — the
refutation with its raw words and a null `direction`, which is the three-valued rule working — and
then nothing downstream ever mentions it. A module can author a `risk` row over one of these and every
gate stays green.

### Why a check rather than a filter

`enrich`-tier checks report and never repair (`@enrichment-is-validation`), and this is squarely that
shape: a fact about the world an author should weigh, not a defect to fix. The natural home is a new
`VALID_VERIFICATION_CHECKS` member — the vocabulary already holds sixteen of exactly this kind, each
comparing something authored against something external.

The subject is **an authored row whose variant a source both asserts and refutes**, so it fires
regardless of how the row got there: a hand-authored module gets the same warning as a drafted one,
which is the point. Muddy water is a property of the variant, not of the provenance.

### Probed 2026-09-02 — [CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md)

Both corpora measured before designing against either, as this entry asked. It answered both open
questions and corrected the entry on the one that mattered.

**The weight question is answered, and this entry had it backwards.** It said only 2428 has a
refutation an editor signed off. 2428's *claim* is accepted; its refutation (EID 10949) is
`SUBMITTED`. **No refutation anywhere in CIViC that stands against a claim is accepted** — both
accepted refutations in the whole database (CHEK2 788 / EID 1854, TP53 4968 / EID 1302) are
refutation-**only**, with no claim beside them. So the subject count is not merely basis-dependent, it
is **0 on `accepted` and 3 on `accepted+submitted`**: the class does not exist on the basis the
builder read before RM169, and exists entirely on the strength of unreviewed content. A hint that
states the basis alongside the disagreement is now the *only* shape that can be honest, rather than
the preferred one. (TP53 4968 never enters the snapshot at all — dropped `unresolvable_identity`, and
absent from the VCF for want of a GRCh37 position. One of the two accepted refutations in the database
is invisible to every consumer of this artifact.)

**The three instances are one pair plus one combination-profile item counted twice.** EID 8721 belongs
to molecular profile 5278, which CIViC publishes as `VHL S183L (c.548C>T) AND VHL D126N (c.376G>A)` —
one statement about a two-variant genotype. `_submitted_evidence_row` stamps `molecular_profile_id`
from the *variant's* single-variant profile, so the parquet writes it as two rows claiming MP 2037 and
2406 and the column that would say "combination" is overwritten. Bounded and measured: 5 evidence ids
on 2 parquet rows each, 108 fanning out across the whole VCF. Note the path asymmetry — a combination
profile arriving via the TSV is dropped `combination_profile`, via the VCF it is fanned out and kept.

**The scope question is answered from the adopted set rather than guessed, and STRchive is not a new
axis.** A walk of all 26 `VALID_*` frozensets finds refuting members in exactly two source-facing
vocabularies: `VALID_GENE_VALIDITY` (`disputed`/`refuted`/`no_known_disease_relationship`, for
ClinGen+GenCC) and `VALID_CLIN_SIG` (`conflicting`, for ClinVar). Four adopted sources carry this
shape and three already land it somewhere — `gene_validity` even publishes an unorderable
`["definitive","refuted"]` group as a **set, not a verdict**, which is this item's machinery already
built one grain up. **STRchive's is the one that lands nowhere**: `StrchiveLocus` drops `evidence` at
parse, and a real `draft-repeats --gene DMD` run (DMD is the single `Refuted` locus) writes a row
indistinguishable from HD_HTT's and says nothing — the field is not even in the read-and-not-written
accounting.

**But the two corpora do not share a subject, so one check cannot be both.** CIViC's contradiction is
*inter-row, post-join, per variant*: neither row is contradictory alone, and the subject exists only
after an authored row is matched to a snapshot variant. STRchive's is *intra-record, pre-join, per
locus*, and is not a contradiction in CIViC's sense at all — nothing asserts the locus is pathogenic
and then denies it; one field grades the association `Refuted` while the same record still publishes a
pathogenic band the drafter writes. That is a self-inconsistent record, closer to a grade the drafter
drops than to a disagreement. Its vocabulary is also **open**, not closed: the published schema uses
`examples` + `combobox: true`, and carries `Provisional` (6 loci), which the schema's own text defines
as *not yet curated* — a nobody-asked, not a grade, and it has no house member. The two corpora
overlap on **one gene (`CBL`) and zero loci**, and no reference example authors any of the six genes,
so zero corpus modules would fire either finding today.

### What has to be decided, and what is already settled

- **The subject set is per authored row, not per snapshot row.** A check that counted snapshot rows
  would publish a number about CIViC; this one is about the module.
- **Severity: warn in both modes, never gate.** Its two nearest neighbours both say so
  (`@clinsig-never-escalates`, and `@a-source-recuring-is-not-a-strict-matter`), and for the same
  reason: a source disagreeing with itself is not an authoring error.
- **Settled by the probe — the hint must state the status basis**, because every pair rests on
  submitted content and a check that did not say so would publish a finding whose subject count
  silently depends on a build flag.
- **Open, and reshaped — one check or two?** The measured answer to "CIViC-scoped or general" is that
  the *shape* is general (four adopted sources) but the *subject* is not shared: a per-variant
  post-join contradiction and a per-locus published grade are two different findings that would only
  look like one in a vocabulary. Deciding this is deciding whether STRchive's `evidence` is adopted at
  all — today it is dropped at parse, so the STRchive half is a **source-adoption** question wearing a
  check's clothes.
- **Open — the combination-profile stamp is a defect, not a design question.** `molecular_profile_id`
  overwritten with the variant's own profile is wrong regardless of what this item decides; it belongs
  to whoever fixes it first, and it makes 8721 look like two independent refutations.

**Related** RM169 (which made these visible), RM152, RM160.

## RM160 — the CIViC snapshot reads the reviewed quarter of its source and says so nowhere a reader acts on

**Severity** medium · **Status** open — **narrowed 2026-09-01**. Its *coverage* half shipped as
[RM169](ROADMAP_HISTORY.md#rm169--the-wider-basis-was-published-as-a-dated-file-all-along-and-nobody-had-looked);
what remains is the *provenance* half, and the VCF that answered the first cannot answer it ·
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

**The labelling requirement is settled and half-shipped.** An `accepted` row and a `submitted` row
must not be indistinguishable once both are in the file, and for the file-built half RM169 did it:
every row carries `evidence_status`, CIViC's own word, unconverted. Whatever shape this half takes
owes the same stamp — and where it lands as a magnitude rather than a column, that is `confidence`
with `confidence_unit`, named rather than translated into a house grade, the way
`ClinSigAuthorityCallRow` already requires a magnitude to name its instrument.

**Related** RM152 (the adoption), RM159 (the name-identity table, whose two unresolved records are the
motivating case), RM153.

## RM164 — `heteroplasmy.csv` is a shipped table kind with no source behind it

**Severity** medium · **Status** open — **PARKED to 0.8, decided 2026-09-01** · **Owner** enricher ·
**Motivating case** the 2026-09-01 source-adoption round

**Decided 2026-09-01 with the maintainer: parks, on the measured negative below.** The candidate field
anyone has named is MITOMAP and the population callsets it re-hosts, and none of them publishes the
axis the kind binds; that is a fact about what exists, not about how hard anyone looked, which is what
makes the deferral honest rather than indefinite. It stays **open and visible** rather than closed,
because a kind with a one-module corpus is exactly what `@probe-uniform-corpus` says to keep in view —
and if a source that bands heteroplasmy by tissue appears, this entry is where it is checked against.
**Reopen it with a source, never with an argument.** The spin-off it noticed is now
[RM171](#rm171--mitomaps-mmutation-is-a-curated-mtdna-variant-table-behind-29-free-text-status-strings).

**Probed and drafted in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm164--heteroplasmycsv-is-a-shipped-table-kind-with-no-source-behind-it) on 2026-09-01 — proposed PARKS to 0.8; the maintainer pass took it as proposed.** **Answered by reading the source, after the maintainer supplied the 2026-08-24 `pg_dump` (61 MB, 95 tables).** MITOMAP is **reachable** — plain `curl` gets the dump at `mitomap.org/downloads/`, HTTP 206 with ranges; the Cloudflare challenge is on the *web* surface only, and two earlier readings of this entry (a "refusal", then "unreachable by the machinery") were both a 403 from a path that was not the data path. **The axis answer is a measured no.** The schema has **exactly one `tissue` column**, on `mitomap.unpublished` — per-patient submissions beside `sample_id` and `ethnicity`, i.e. sample data this format does not carry. `mitomap.mmutation` is **602 rows** whose `homo`/`hetero` are *presence flags* (`+` 286/270, `-` 216/238, `nr` 90/89, plus `.`/`na`/NULL), with no threshold, no band and no tissue — the only levels in the table are two rows where a percentage was typed into a flag column. The only heteroplasmy numbers anywhere are re-hosted blood-cohort data (`mitomap.gnomad` 18,164 rows, `mitomap.helix` 14,104), where `max_observed_heteroplasmy` is a cohort observation, not a clinical threshold. So `HeteroplasmyRow`'s binding columns have **no source-side value in MITOMAP**. Terms are **unread**, not unestablishable — the dump carries no licence text in 6.7 M lines and the page a browser reaches was not opened. Parks, not closed. **Separately noticed and not part of this entry**: `mmutation` is a plausible mtDNA `variants.csv` source, blocked on `status` being 29 free-text strings rather than a vocabulary — its own item when taken.

**The measurement, taken over `_TABLE_KINDS` and the enricher's providers.** Every table kind is in
`DRAFTABLE` by construction, so *structurally* all nine are draftable. A **provider** exists for four:
`haplotypes`/`allele_function`/`diplotypes` (`pgx_draft` ← CPIC), `pharm_variants` (`clinpgx_draft` ←
ClinPGx), and `variants` (`clinvar_draft`, `civic_draft`, `pubmind_draft`). `heteroplasmy.csv`,
`repeat_alleles.csv`, `copynumbers.csv`, `pgs.csv` and `activity_phenotype.csv` have **none**, and no
enrichment pass reads them for a cross-check either. `enrich()` does resolve heteroplasmy rows — it is
the third table that can ask, and the one that keys *with* `alts` — but resolution is not a source.

The corpus behind the kind is one module: `reference_examples/mt_heteroplasmy`, two MT-TL1 variants of
one gene, hand-authored from the literature. That is the `@probe-uniform-corpus` shape exactly — the
schema generalized from a single case, and nothing since has taken a second one.

MITOMAP is the canonical mtDNA variant table and the obvious candidate. **Two things must be
established before that is a plan, and neither is:**

1. **The terms.** MITOMAP is not CC0, and this entry states nothing further about its licence.
   Whether it is expressible as a `SourceTerms` at all, and whether it lands as a **draft** source or
   only as a **check**, is decided by reading its published terms. RM153 is the standing reminder that
   a source's terms page can answer HTTP 200 with something that is not terms, and that the honest
   record of an unestablished axis is `None` (`@no-named-licence`).
2. **Whether it carries the axis at all.** `HeteroplasmyRow` binds a *level band* per
   `(gene, reference_sequence, tissue, variant_key)`. A per-variant pathogenicity table with no tissue
   and no threshold fills the identity columns and none of the binding ones — it would draft rows that
   say nothing the kind exists to say. Probe the real file and name the table probed
   (`@probe-the-real-file`, `@probe-names-the-table`); a negative here is as useful as a positive and
   closes the item cleanly rather than leaving it open forever.

**Related** RM165 (the same shape on the other uncovered binning kind), RM171 (the spin-off),
`@probe-uniform-corpus`.

## RM171 — MITOMAP's `mmutation` is a curated mtDNA variant table behind 29 free-text status strings

**Severity** low-medium · **Status** open — **a minor, release undecided** · **Owner** enricher ·
**Motivating case** RM164's probe, which found it while answering a different question

**Filed 2026-09-01, out of RM164's decision rather than out of a sweep.** RM164 read MITOMAP's full
`pg_dump` to answer whether the source carries a heteroplasmy *level* per tissue — it does not — and
found, beside that negative, a table that is not about heteroplasmy at all. **`mitomap.mmutation` is
602 curated mtDNA disease variants with a confirmation status**, which is `variants.csv` territory and
a different table kind from the one RM164 is about. It is filed separately for that reason: widening an
item by changing what it is about is how an item stops meaning anything, and RM164's negative would
have been kept artificially alive by a positive that has nothing to do with it.

**What blocks it is one column.** `status` is **29 distinct free-text strings**, not a vocabulary —
`Reported` 419, `Cfrm [LP]` 42, `Conflicting reports` 16, `Cfrm [P]` 16, and a long tail of one-offs
like *"Reported: individually neutral variants causing LHON in combination"* and *"Reported; hg D1 D2
M33 R30 marker"*. Mapping that onto `clin_sig` is **a curation decision, not a normalization**:
`@one-normalizer-two-spellings` is the rule for a vocabulary two sources spell differently, and it
stops being enough at the point where one side is prose. A provider that mapped the four common
strings and dropped the tail would be writing a judgement the source did not make; one that mapped
every string would be inventing 25 of them.

**Its terms were unread, exactly as RM164 left them. They are read now (2026-09-02), and they are
permissive.** The dump carries no licence text in 6.7 million lines; MITOMAP states its terms on
`MITOWIKI/HelpTerms`, linked from `CitingMitomap` as *Terms of Use for data content and figures*:

> All content on MITOWeb (including MITOMAP, MITOMASTER, & MITOWIKI) except where otherwise noted, is
> made available under a **Creative Commons Attribution 3.0 License**. Authors retain ownership of the
> copyright of their contributions, while allowing anyone to download, reuse, reprint, modify,
> distribute, and/or copy content, so long as **the original authors and source are cited**. No
> permissions are required from the authors or publishers to use the work in these terms.

CC BY 3.0: commercial use permitted, redistribution permitted, attribution required, no separate
agreement. **So the terms negative that would have closed this item outright does not fire** — the
item survives on its `status` column alone.

**How that was read, because the scope matters (`@probe-names-the-table`).** The live page returns
**403** to both `curl` and the fetch tool — a Cloudflare interstitial, not a paywall — so the text
above is the Wayback capture of **2026-04-17**, of a page whose own last revision is **r4,
2019-07-30**. It is not a live read and should be re-read from a browser before anything is published
from this table. Two traps found while reading: a search for MITOMAP's licence surfaces **CC BY-NC**,
which is the *NAR article's* licence and not the database's; and **"except where otherwise noted"** is
the floor-plus-per-record-override shape (`@a-hosts-terms-are-not-its-contents-terms`), so a per-record
note outranks the site default and the licence row must be written as a floor. Also unrecorded, and
owed: how RM164 acquired the `pg_dump`. If it came from a mirror rather than mitomap.org, that
mirror's terms are a separate question this read does not answer.

**So the decision is back where it was, minus the gate.** `status` is 29 free-text strings and mapping
them onto `clin_sig` is a curation decision, not a normalization. Whether the adoptable part is a
`clin_sig` mapping or only the identity columns plus the verbatim string carried as evidence is a
maintainer call, deliberately not pre-empted here.

**Related** RM164 (where it was found), `@one-normalizer-two-spellings`, `@no-named-licence`,
`@probe-the-real-file`.

## RM174 — a combination-genotype refutation reaches the parquet as two single-variant rows, and the column that would say so is overwritten

**Severity** medium · **Status** open — **two candidate repairs, neither chosen** · **Owner** enricher
· **Motivating case** the RM170 probe, which found it while measuring the refutation set
([CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md) §2.2)

CIViC evidence item 8721 belongs to molecular profile **5278**, which CIViC publishes as
`VHL S183L (c.548C>T) AND VHL D126N (c.376G>A)` — one statement about a **two-variant genotype**.
`_submitted_evidence_row` stamps `molecular_profile_id` from **the variant's**
`single_variant_molecular_profile_id` rather than from the evidence item's own profile, which the VCF
CSQ block already carries and `CivicVcfEntry.molecular_profile_id` already parses. So the parquet
states, twice, that a combination-genotype refutation is a single-variant refutation, and the one
column that could have said otherwise has been written over.

**Bounded and measured.** 1,149 rows carry 1,144 distinct `evidence_id`s; the five that repeat are
5634, 6740, 6868, 8721, 8790 — all VHL, all submitted, four of them `Supports`. Across the whole VCF
the fan-out is 108 evidence ids over 279 CSQ entries; only 5 survive the germline + direction-axis
filter.

**The overwrite is not gratuitous, which is why this is not a one-line fix.** The row is shaped
exactly like a TSV evidence row so it rejoins `evidence` and goes through one origin filter, one
direction map, one profile join and one identity route. `molecular_profile_id` is the join key into
`by_profile`, so the *true* profile id would not join — and the TSV path already handles that case by
dropping a multi-variant profile as `combination_profile`, counted. The overwrite is what makes the
VCF path keep a row the TSV path would drop.

### Two repairs, and the choice is a real one

1. **Carry the entry's own profile and let the existing machinery drop it.** One behaviour on both
   paths, the drop counted under `combination_profile` like any other. **But it removes exactly the
   two rows RM170 is about** — 8721 is the rebuttal standing against 2161 and 2533 — so the item that
   found this defect would lose its motivating case to the repair.
2. **Keep the fan-out and stop the false claim.** The join key stays the variant's single-variant
   profile; the evidence item's own profile id and name are published in their own columns. Additive
   and minor-legal, keeps every row, and makes a combination profile *legible* rather than either
   silently wrong or silently dropped. Costs a parquet column, which the 0.6 charter amendment prices
   at approximately free.

Repair 2 is the one this entry would take, on the grounds that dropping a row to fix a mislabelled
column trades a wrong answer for no answer. It is written down as a recommendation rather than a
decision because the path asymmetry it leaves — the TSV drops a combination profile, the VCF keeps it
labelled — is the sort of thing `@parity-by-check` says to audit deliberately rather than inherit.

**Related** RM170 (where it was found), RM169 (which added the VCF path), `@parity-by-check`.

## RM175 — the PGx lane's default archive is a retired filename, and every row it has ever built came out of a frozen 2025 object

**Severity** high · **Status** open — **a rebuild, sized below; supersedes RM173** · **Owner** enricher
· **Motivating case** the maintainer's 2026-09-02 investigation
([CLINPGX_ARCHIVES](probes/CLINPGX_ARCHIVES.md)), which started from RM173's canary and found what it
was a canary of

**PharmGKB renamed the table on 2025-07-29** ([the ClinPGx launch
post](https://blog.clinpgx.org/pharmgkb-is-now-clinpgx/)): *"Clinical annotations … are now called
**summary annotations**."* The archive followed the rename. `clinicalAnnotations.zip` was last written
to S3 on **2025-07-05, twenty-four days before that post**, and has not been rebuilt since; it is on no
downloads page; and the API still answers it **200** through a 303 to the frozen object.
`clinpgx_build.DEFAULT_CLINPGX_URL` still names it.

**So this is not a stale cache and not a slow source.** Every `annotations.parquet` this lane has ever
built, every PGx row drafted from it and every check that read one rests on a snapshot of the database
as it stood **fourteen months ago**, and nothing in the response says so — a retired filename that
still 200s is indistinguishable from a live one at the HTTP layer. RM173 measured the 13-month gap
correctly and diagnosed it as two live surfaces refreshing out of lockstep. It is one live surface and
one leftover.

### What the rebuild actually is

`summaryAnnotations.zip`, `CREATED_2026-08-05`, is the same 15-column table under new names:

| 2025 archive | 2026 archive |
|---|---|
| `clinical_annotations.tsv` | `summary_annotations.tsv` |
| `clinical_ann_alleles.tsv` | `summary_ann_alleles.tsv` |
| `clinical_ann_evidence.tsv` | `summary_ann_evidence.tsv` |
| `clinical_ann_history.tsv` | `summary_ann_history.tsv` |
| `Clinical Annotation ID` | `Summary Annotation ID` |

The other fourteen column names are identical and in the same order, and `Phenotype Category` has the
same thirteen values with the same `;` separator, so **no vocabulary moves and no model changes**. The
work is the URL, the four member names, the id column, and the numbers that were derived from the old
file.

**It is not a rename-only patch, because the data moved.** Over the 5,179 ids in both: 7 annotations
gone, 11 new, **8 rows change `Level of Evidence`**, 2 change `Variant/Haplotypes`, 40 change
`Drug(s)`, 14 change `Score`, 68 change `Level Modifiers`. Every `URL` rehosts
`pharmgkb.org` → `clinpgx.org` on a path that still reads `/clinicalAnnotation/`. The parquet digest
moves, and a module drafted from this lane can see an evidence level change under it — which is
correct, and is the first thing this lane has ever had to say about currency.

**And one recorded number is wrong twice.** `clinpgx_build`'s docstring says *"4,618 of 5,113 carry
exactly three"* genotype rows. 4,618 is the 2025 file's three-genotype count and 5,113 is neither
file's annotation count (5,186 then, 5,190 now) — it is the *distinct-key* count of the rollup. Derive
it at runtime rather than restating it (`@dont-discard-computed` has the same shape one step over).

### The general half, which is why this is severity high and RM173 was not

A filename can retire while its bytes keep serving, and **nothing in this lane could have noticed**:
the download succeeded, the members parsed, the licence read, the row count was plausible, and
`release.json` recorded a `CREATED_*.txt` nobody compared against anything. Candidate guards, none
chosen — this entry sizes the rebuild, it does not design the canary:

- **Audit every default URL in the lane against what the source lists.** ClinPGx serves 19 zips;
  `drugLabels.zip`, `relationships.zip` and `clinicalVariants.zip` are all on the page and
  `clinicalAnnotations.zip` is not. This is a one-off read, not machinery.
- **Record the S3 `Last-Modified` beside the `CREATED_*.txt`** in `release.json`, so an archive that
  stops being rebuilt is visible in the artifact rather than only in the source.
- **Fire when one archive of a multi-archive source is much older than its siblings** — the shape
  RM173 stumbled into, generalised. `@two-surfaces-two-denominators` is the neighbour, and
  `@currency-asks-the-source-not-the-cache` says the question goes to the source.

**A trap that cost the investigation real time, and belongs in the record.** Every ClinPGx HTML route
— `/downloads`, every help page — serves the same JS shell whose no-JS body is *"Javascript Is
Disabled!"*. `curl` and `WebFetch` therefore **cannot** answer "is this file listed?", and both return
200 while telling you nothing. The downloads listing in the probe is a rendered-DOM capture from a
browser. Treat a no-JS fetch of this host as no evidence at all (`@probe-the-real-file`, one host
further on).

**Related** RM173 (closed into this), RM166 and RM29b (both built on the lane this rebuilds), RM164,
`@two-surfaces-two-denominators`, `@currency-asks-the-source-not-the-cache`, `@probe-the-real-file`,
`@pgx-research-only`.

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

Split off [RM103](ROADMAP_HISTORY.md#rm103--the-manifest-now-records-the-version-that-was-read-not-only-the-one-that-was-invented),
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

### `trait_efo_id` is named for one ontology and accepts every ontology

**Severity** low · **Status** queued for 1.0 — **filed 2026-08-31 by the maintainer** after the name
misled a provider in this tree · **Owner** format (+ every consumer reading the column by name)

The column takes any ontology CURIE and always has: `validate_trait_ids` enforces only a
`PREFIX:LOCAL` / `PREFIX_LOCAL` shape, the cell is multi-valued, and the field's own description reads
*"EFO/MONDO/OBA/HP trait ontology id(s)"*. `HP:0000006`, `MONDO:0005265`, `DOID:1612` and
`OBA:2040158` are all legal today, singly or together. The name says EFO because it matches just-prs's
column, and that is the whole of the reason.

**A name is a claim, and this one is read as a restriction.** The CIViC provider withheld a `DOID:` id
from the column on the reasoning that a DOID in an EFO column would be a wrong identifier, and put it
in `conclusion` prose instead — losing a joinable id on **every row it drafted**, since every CIViC
germline row carries a DOID. That is the same class as an analogy in a field description being taken
for a rule: the field was doing its job and the label was not. It has been fixed at the provider and
the rule is now stated in [SCHEMAS.md § Conventions](SCHEMAS.md#conventions-the-idioms-every-model-obeys),
but the durable repair is the name.

**It is here rather than in a minor because a rename is a removal plus an addition**, and removal is
what P3/P8 reserve for a major — a consumer selecting `trait_efo_id` by name breaks the moment the old
name goes. The additive half (a new `trait_id` column) is minor-legal on its own and is deliberately
**not** proposed: two spellings of one fact is the overloading P5 forbids, and a deprecation window
that leaves both columns readable is exactly the state this tracker exists to end. So it waits, and
lands as one rename with the removal.

**Two things for whoever takes it.** The successor name should not encode an ontology at all —
`trait_id` — and the description should keep naming the accepted prefixes, because the next provider
will read the name first. And the rename has to move with the reserved-namespace and
`authoring_reference` surfaces together, since a consumer's column list is generated from the model
rather than hand-kept.

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
already covered by an item in `PROPOSAL_0_6_PT2` or the minor-deferral file that we have not read
closely enough,
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
