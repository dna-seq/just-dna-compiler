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
  corpus or a caller. **0.8 is a stabilization and competitor-parity release, decided 2026-09-11 with
  the maintainer**; the theme is stated in that file's header and does not itself admit an item. RM10 closed there, folded into RM28. **It succeeded `ROADMAP_0_7.md` at the 0.7
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

**Status:** **0.7.0 is cut, tagged and published** — all three packages, on 2026-09-12. The tag is
`v0.7.0` at `2001215` and it moved through four positions before settling there, each because a gate
found something rather than because anyone changed their mind; the sequence and the reason for each
move are in
[INTEGRATION_0_7 § 5](INTEGRATION_0_7.md#5-readiness). PyPI has all six artifacts as of 15:49–15:50
UTC that day, and their hashes are the ones that section lists. The previous cut was **0.6.6,
`v0.6.6`** (2026-08-21), carrying nine patch fixes: the 2026-08-19 doc-audit round (RM104–RM107,
RM109, RM111), the two shipped items of the S57–S60 batch (RM121, RM123), and S61's lookup fix
(RM125). Everything committed after that tag — the 2026-08-21 output-contract, decision and lookup
rounds' successors, the 2026-08-24 consumer round, the source-adoption round and the whole 0.7 build
round — went out in 0.7.0 rather than in any 0.6 number.

**Re-read this paragraph whenever a version moves, because it has lied twice.** It read *"0.6.4 is the
current line"* for two releases, and then *"0.7.0 is bumped and not tagged"* for as long as it took
somebody to run `git rev-parse v0.7.0` — the same failure the *Active items* heading had, and the
reason both are called out rather than quietly corrected. `schema_version` stays `"1.0"` and has since
0.4. **Tagged is not published** — they are separate steps and the second is the maintainer's, so
check [CHANGELOG.md](CHANGELOG.md) before promising a field to anyone; for 0.7.0 both have happened,
which is not the state this file has usually been in. 0.5.0 went to PyPI on 2026-08-07, with
`just-dna-enricher` 0.5.0 the first release of that package.

**0.6.0 was cut and tagged `v0.6.0` on 2026-08-17**, and `0.6.1` followed on 2026-08-18 with RM93–RM100
(see [ROADMAP_HISTORY § 0.6.1](history/ROADMAP_HISTORY_0_6.md#061--the-eight-the-documents-caught-the-two-the-fixes-found-and-rm88)).
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
[ROADMAP_HISTORY § 0.6.0](history/ROADMAP_HISTORY_0_6.md#060--the-design-round-built). Across the corpus that batch
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
built — see [ROADMAP_HISTORY § 0.6.0](history/ROADMAP_HISTORY_0_6.md#060--the-design-round-built) — so this table
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

**No count here: the open items are the `## RMn` sections below, and `test_triage_tools.py` walks
them.** This line stopped stating a count on 2026-09-30, the day it was caught stale again (it
read "four as of 2026-08-21" for two rounds after it stopped being four, then *not one of them is a
decision* through the three that are, then *three* for the hour it took a fourth to be filed, then
*two* until RM151 shipped, then *one* naming RM152, then *one* naming RM153, then none, then seven for
the 2026-09-01 source-adoption round, then one, **none again on 2026-09-11** when RM164 moved to
the 0.8 file, **one again on 2026-09-12** when RM232 was filed, none again the same day when it
shipped, and **one again that evening** when RM235 was filed, then **none on 2026-09-20** once
RM235 and RM244-RM246 had all shipped, then **one again the same day** when RM247 was filed, none once it shipped in 0.7.1 — this line went on
naming it until 2026-09-24 — and **one again on 2026-09-24** when RM258 was filed, then **two on 2026-09-25** when RM263 was filed, and **three the same day** when RM264 split from RM256, then **two** when RM264 shipped on the rebuilt patch line, and it went on saying *two, RM258 and
RM263* while the 2026-09-27 postmortem sweep and the rounds after it filed some thirty more, and after
those two had moved to the 0.8 file. That is why the paragraph under it says to count off the
sections rather than off this sentence, and why the sentence no longer offers one).

**RM232 was filed open and shipped in the same session, and the filing is the part worth keeping.**
It was written into this file the moment it was confirmed rather than when its fix was approved,
because until then it existed only as two named exemptions in a passing test — a state this file
cannot see, and a release reading *no open RMs, all green* therefore cannot either. Whether to fix a
confirmed defect now is a question; whether to file it is not.

**The last one was RM164, and it is filed against 0.8 now.** The 2026-09-01
source-adoption round (RM163–RM168) was asked for as a batch — *what else should we adopt as
enrichment sources, besides CIViC and PubMind* — and filed together because its items shared a shape
and a discipline rather than a mechanism. Five of the six shipped inside the uncut 0.7.0, and RM164
**parked on a measured negative**: no source publishes a heteroplasmy level per tissue, so the table
kind stays without one. It stayed open rather than closed because a source would reopen it, and its own
entry names in advance the finding that would close it instead. It sat in *this* file for ten days
after the decision that sent it to 0.8, which is the failure mode the split exists to prevent — a
decided deferral that no release file can see — so on **2026-09-11** it moved to
[ROADMAP_0_8.md](ROADMAP_0_8.md#rm164--heteroplasmycsv-is-a-shipped-table-kind-with-no-source-behind-it).
**A decision to park is not filed until the section has moved.**

**The spin-off RM164 filed shipped on 2026-09-03.** RM171 adopted MITOMAP's curated mtDNA tables as
the increment they carry over the ClinVar cache — the *variants* half of the source RM164 probed for
its *heteroplasmy* half and did not find. ROADMAP_HISTORY has it. The two are deliberately separate
items: widening one by changing what it is about is how an item stops meaning anything, and RM164's
negative would have been kept artificially alive by a positive that has nothing to do with it.

**The discipline the round is worth remembering for**, since it is the reason these entries read the
way they do: not one of the six had been probed when it was filed, every entry said so in its own
words, and each separated what was *measured* from what was merely *candidate* while asserting no
licence. The failure it was written against is a remembered licence or a remembered API hardening into
a permanent false constraint in these files (`@probe-names-the-table`), so each item's first step was
the probe — and five of the six entries turned out to say something their own probe contradicted.

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
number that then shipped. The third was an item filed with no such token at all — RM235, on
2026-09-12 — so the field is now **asserted by a test** rather than only described:
`schema/tests/test_triage_tools.py` walks every `## RMn` between this heading and
`# Not format scope` and refuses the one the counters cannot see. Write the token, or the suite says
which item is invisible and to whom.

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
[ROADMAP_HISTORY § the 2026-08-19 doc-audit patch round](history/ROADMAP_HISTORY_0_6.md#the-2026-08-19-doc-audit-patch-round--six-of-the-eight-fixed).

RM88 and RM93–RM100 all **shipped in 0.6.1** and moved to
[ROADMAP_HISTORY § 0.6.1](history/ROADMAP_HISTORY_0_6.md#061--the-eight-the-documents-caught-the-two-the-fixes-found-and-rm88),
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
[ROADMAP_HISTORY](history/ROADMAP_HISTORY_0_6.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all).
RM74–RM79, the whole 0.6 dogfooding fix round, shipped on 2026-08-15 and moved
to [ROADMAP_HISTORY.md](history/ROADMAP_HISTORY_0_6.md#06-dogfooding--the-fix-rounds-own-findings-repaired) — but
read that as *the sprouts are repaired*, and the ground with them: RM76's narrow repair is what shipped
in that round, and the question it asks from underneath —
[RM73](history/ROADMAP_HISTORY_0_6.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end), the root
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

## RM258 — an outage during the literature fetch writes a row that merge-not-clobber never asks again

**Severity** medium · **Status** open — **a minor, release undecided** — found while building RM257 ·
**Owner** enricher (`literature`) · **Motivating case**
[S110](CONSUMER_SUGGESTIONS_HISTORY.md#s110--the-literature-pass-leaves-an-author-manuscript-abstract-only-when-pmcs-bioc-service-serves-it-whole-tables-included)
— Europe PMC answered HTTP 500 for `PMC6463297` on 2026-09-24

**What was confirmed.** `EuropePmcClient.fulltext` and the new `PmcBiocClient.fulltext` both return
`None` for a 404 (no copy) and for a 5xx or a transport failure (never answered). The pass then falls
back to the abstract and writes `quote_source=abstract` with the abstract's count. The row is keyed by
PMID and `literature.csv` is merge-not-clobber, so `wanted` skips it on every later run: **a transient
outage becomes a permanent abstract-only pin.** Pinned by
`test_every_way_bioc_has_no_text_reads_as_not_retrieved`, whose 500 arm writes exactly that row. That
test asserts today's behaviour, not a decision. `@unreachable-not-absent` at the row level. The
reporter named the conflation in `fulltext()`, and the pin is what it costs.

**Rows pinned before RM257 have the same problem without any outage.** The BioC rung only runs for a
citation the pass fetches, so a module enriched before it keeps its abstract-only rows until
`literature.csv` is deleted. Since 0.7 that delete costs nothing (RM124), and that is the
workaround the S110 reply gives. It is still a step nobody will know to take.

**Candidate repairs, none chosen:**

1. **Write no row when the fulltext could not be asked.** Refused in advance: existence, identifiers
   and the licence were all answered, and answered is per field
   (`@answered-is-not-absent`). Dropping those answers to get a retry is the wrong trade.
2. **Re-ask fulltext on every run for any row whose `quote_source` is not `fulltext`.** No schema
   change, and it picks up rows pinned before RM257. It costs one paced request per paywalled citation
   per run, forever, for articles that will never have a copy. Changing the pass's merge from per row
   to per field is the precedent this would set, and `--rederive` already has rules for that
   (`@rederive-never-shortens`).
3. **Record how the fulltext question ended, as a derived column** (`fulltext_status`, roughly
   `retrieved | absent | unreachable`), and re-ask only `unreachable`, plus null on rows written
   before the column existed. An optional column on a derived CSV is minor-legal and half-cost
   (P9). It needs the two clients to stop returning one `None` for two answers, which is the
   `@client-exception-contract` shape. The question for review is whether null on old rows should
   mean "ask once" or "leave alone".

## RM263 — a DOI has no route to its PMID, although `StudyRow.pmid` is the required half

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** enricher (`lookup`,
`literature`) · **Motivating case** [S113](CONSUMER_SUGGESTIONS_HISTORY.md#s113--lookup_citationdoi-settles-existence-and-never-identity-title-journal-year-and-author-are-always-null), the reporter's second candidate fix

**What was confirmed.** A curator holding only a DOI (what a paper's landing page gives you) can now
learn which paper it is (RM262), but not its PMID, and `StudyRow.pmid` is the column the schema
requires. RM50 built the same route for a PMC id through NCBI's converter; a DOI has none. Europe PMC's
search answers it: `DOI:"10.1038/ng826"` returns PMID `11788828`, measured 2026-09-25, and covers all
of PubMed. NCBI's converter also takes DOIs but only answers for articles in PMC, and Enattah 2002 is
not in PMC, so it would miss exactly the paywalled case.

**The shape is RM50's, and the open question is the second title.** The resolved PMID comes back as an
advisory (`applied=False`, `refusal="redundancy_bearing"`), never a fill, since `pmid` is
redundancy-bearing. Then PubMed is asked which paper that PMID is, as `_check_pmcid` does. That gives a
DOI-only lookup two titles, Crossref's and PubMed's, and whether a disagreement between them is a
`warning` or only two `info` findings side by side is the decision still to make. `EuropePmcClient`
has no DOI search today; one method.

## RM265 — the `panel:` deprecation has no "accepted" signal: on the replaced branch the warning fires whether or not you need the three fields it tells you to keep the block for

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** compiler / format
(`panel:`, the licence row) · **Motivating case** [S114](CONSUMER_SUGGESTIONS_HISTORY.md#s114--the-panel_block_deprecated-replaced-branch-warns-whether-or-not-you-need-the-three-fields-it-says-to-keep-the-block-for-so-there-is-no-way-to-signal-accepted)

**What was confirmed.** Reproduced against all three just-dna-lite ClinVar panel modules and against
the code. `panel_block_deprecated` fires on the `replaced=True` branch (`compiler.py:4231`) for a
module that has done everything the migration asks — its `clinvar/annotation` licence row carries a
non-empty `dataset`, so the block's one machine reader (the enricher's clin_sig cross-check) is
migrated. The message's closing clause, correct since S69, is that `genes`, `significance` and
`reference_sha256` "have no replacement anywhere — keep the block until 1.0 if you need them recorded."
But keeping the block *is* the permanent warning: the block emits `panel_block_deprecated` whether or
not those fields are wanted, and there is no key to say "accepted, I need the three, stop." A consumer
who needs them warns forever; a consumer who wants a clean compile drops provenance the format itself
says has no home. The two outcomes are "warn forever" and "lose data".

**The design question this records.** Is `panel:` deprecated *as a whole*, or only its reader? P3
deprecates in a minor only where the audience can **act** — the replacement exists and the deprecated
thing is not still the only record — and for these three fields on the replaced branch no replacement
exists, which is the state P3 forbids. Two candidate fixes, and the naive one is not free:

- **Give the three fields a non-deprecated home** — a small `panel_provenance:` sub-block, or three
  keys beside `dataset` on the licence row. This is the P3-clean answer: it completes the replacement,
  so the deprecation becomes actionable. Cost is P9-full if authored (a `panel_provenance:` block the
  rare author writes) or P9-half if it rides the machine-written licence row; additive either way, so
  **minor**. It is a schema-shape decision — where the fields live, whether the gene *denominator*
  (S114's one lossy field: `cardio` requested 327 genes, 297 matched a variant, the 30 that matched
  none are absent from `variants.csv`) is a list or a count — and belongs in the version interview,
  not an unattended pass.
- **Fire `panel_block_deprecated` only on the `replaced=False` branch** (patch). Tempting and **not
  free**: it silences a *true* statement on exactly the modules that keep the block for the three
  fields, so they compile clean until 1.0 removes the block under `extra="forbid"` and the data with
  it. P3 requires a major to ship its upgrade procedure; theirs would read "lose the data." So this
  mitigates the noise at the cost of hiding the loss — a stopgap, not the resolution.

**Related.** The idea-book's § D19 (this file) raised the same two candidates against the pre-S69
message; S114 is its sharpened, corpus-backed form. The stale RM4 row in
[ROADMAP_1_0.md](ROADMAP_1_0.md) § the upgrade tracker still tells the author "delete it, nothing
replaces it, consumer: no action needed" — corrected there in the same triage pass as a doc fix,
since that tracker is the procedure P3 turns on.

## RM266 — the phase-confusable diplotype-pair set is computed at compile and dropped: it reaches the artifact only as a capped warning string

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** compiler
(`_cross_validate_diplotypes`) · **Motivating case** [S116](CONSUMER_SUGGESTIONS_HISTORY.md#s116--rm28-the-hfe-compound-het-vs-cis-case-is-a-meta-conclusion-a-consumer-can-name-but-not-resolve), note 2

**What was confirmed.** Reproduced by compiling `reference_examples/hfe_compound_het`: the
`diplotype_phase_ambiguous` warning fires and names the exact set S116 says the artifact cannot carry —
`HFE: 1 group(s) … e.g. C282Y/H63D, C282Y-H63D/wt`. So the compiler **already computes** the
phase-confusable pair set. `_cross_validate_diplotypes` (`compiler.py:3457`) groups a gene's diplotype
pairs by their phase-preserving definition signature and separates *indistinguishable at all* (identical
definitions, `diplotype_definitions_identical`) from *phase would decide* (`diplotype_phase_ambiguous`) —
which is precisely the distinction a caller reconstructs at query time. It is then flattened into a
warning string and capped at three examples (`_examples`), so a reader of the artifact who is not
running a caller cannot recover the set, and beyond three groups cannot see it at all.

**Why this is not RM28.** S116 frames note 2 as wanting an RM28 axis — an author *stating* "this pair
is distinguishable from that one only by phase." But the author does not need to state it and should
not: it is **derived** from `haplotypes` + `diplotypes`, and the compiler derives it today. This is
`@dont-discard-computed`, not a new authored surface — the fix is to stop discarding the structure, not
to add an axis. The general shape is the idea-book's § D3/§ D4 (warnings are `list[str]` with no code,
count or payload); RM266 is the specific case where the *payload* — the confusable groups, by name — is
the thing worth carrying, over and above D3's per-code count.

**The shape, filed not built.** A structured surface for the computed groups — a `manifest.json` field
keyed by gene, or a small optional parquet — so a downstream reader sees the confusable set without
re-deriving it. Additive (a new optional derived surface, P9 ≈ free-to-half), so **minor**; the open
question is manifest field versus parquet, and whether it subsumes or sits beside a general
`warnings_summary` (§ D3). Corpus, not code, decides urgency: this is `just-dna-lite`'s first caller and
it already re-derives the set successfully, so nothing is blocked.

## RM267 — the Ensembl snapshot anchors a class of insertions one base early, and `resolution.csv` serves them as a different event

**Severity** high · **Status** open — **a minor, release undecided** · **Owner** enricher (the resolver
chain's snapshot link), with the upstream half in `just-dna-pipelines` · **Motivating case**
[S117](CONSUMER_SUGGESTIONS_HISTORY.md#s117--the-ensembl-variation-cache-spells-indel-rsids-at-a-different-anchor-from-clinvar-for-every-insertion-and-for-some-it-names-a-different-event)

**What was confirmed.** `lookup_loci` against the local snapshot returns `rs8176719` (ABO O1, MAF 0.34)
as `9:133257520 G>GC`. GRCh38 reads `GGGG T ACC` at 517–524, so that spelling is the haplotype
`GGGGCTACC` and ClinVar/dbSNP's `521 T>TC` is `GGGGTCACC`: two events, not one respelled. Both of the
report's other −1 examples reproduce the same way against the reference (`rs546596010`: `CCATTCC`
vs `CCTATCC`; `rs1553364018`: `GTCCCC` vs `GCTCCCC`).

**The mechanism, and where it lives.** The snapshot is faithful: Ensembl's own current VCF dump
(`homo_sapiens-chr9.vcf.gz`, read by remote `bcftools`) carries `133257520 rs8176719 G GC`. Ensembl's
**REST** mapping for the same rsID disagrees with its VCF and agrees with ClinVar — `start 133257522,
end 133257521, -/C`, an insertion between 521 and 522, which VCF-anchors at `521 T>TC`. Across seven
insertions (the two cited plus five sampled from the −1 class on chr3/5/12/16) the dump's POS is REST
`end` − 1 every time, and REST `end` is ClinVar's POS every time. So the dump anchors a class of
insertions one base left of Ensembl's own interbase point: invisible inside a run of the anchor base,
a different event outside one. `@two-surfaces-two-denominators` applies to Ensembl against itself.

**Why no check here sees it.** The wrong anchor base is a real genome base, so
`sequences.verify_reference_alleles` passes it by construction. `check_rsid_coordinates` calls every
indel position difference *undecided* (RM31: an indel re-anchors legitimately). And for an rsID-only row
`_verify` never runs. A module resolving `rs8176719` through the table therefore compiles green and
matches no sample.

**Why each candidate repair is wrong alone.**

1. **Re-anchor at snapshot build.** Correct, and it is `just-dna-pipelines`' build, not this tier's
   (`CACHE_LANES["ensembl"].unbuilt`). It also leaves every deployed snapshot wrong until rebuilt.
2. **Left-normalize in `resolve_variants`** (the reporter's first candidate). It fixes the +1 class,
   which is harmless respelling one base right of VCF left-normalization. It cannot fix the −1 class:
   `G>GC` after `GGGG` has no left-shift room, so it normalizes to itself and stays the wrong event.
3. **Re-derive insertions from REST.** Right values, but it turns a bulk snapshot into one request
   per insertion rsID, and REST's rung has its own defect (RM268) to fix first.
4. **A finding that withholds** (the reporter's second candidate): for each insertion the snapshot
   resolves, compare against a second placement the enricher holds (the ClinVar snapshot on rsID,
   else REST). Apply both spellings to the reference window, report a different haplotype, and
   withhold the row rather than choosing. It reports without repairing (`@enrichment-is-validation`)
   and is the part that fits here. What it does not settle is whether the enricher may then
   **write** the corrected spelling. Under `@provenance-beside-a-claim-is-outside-content-identity` a
   rewritten snapshot value should say so on its row, which is a new optional `resolution.csv`
   column. That column is minor-legal, and it is why this item is sized as a minor, not a patch.

`content_signature` is unaffected either way (a resolution fill is `authored_ident`, `@rm43-positional-fill`).
`@sidecar-authoritative` applies: a corrected spelling reaches an existing `resolution.csv` only on
`--rederive` or a deleted sidecar, so the release that ships it must say so.
Measured scale (the reporter's join, not re-run here): 5,788 insertion and 2,111 deletion alleles in
the −1 class, of which roughly three in four of the sampled insertions are a different event.

**Addendum 2026-09-27, [S121](CONSUMER_SUGGESTIONS_HISTORY.md#s121--the-enricher-resolves-a-coordinate-from-one-authority-and-validates-it-against-that-same-authority-so-a-wrong-anchor-is-confirmed-rather-than-caught-a-cross-authority-discordance-should-warnwithhold-not-resolve-silently):
candidate 4 is the general rule, not an Ensembl special case.** Confirmed in code: the ClinVar link
(`enrich.py`, the "ClinVar cache link" block) fills only what the Ensembl cache missed. The same run
already holds the ClinVar snapshot for the `clin_sig` cross-check, yet it never compares a placement.
The comment gives the reason for that order as *"so no compiled module's artifact.digest moves"*, which
is the one reason the house rules say is never enough on its own. So every
coordinate in `resolution.csv` has one witness, and `authority=ensembl` reads the same whether a
second authority agreed, disagreed, or was never asked. The build is therefore:

- **Compare every placement two loaded authorities give for one rsID, and withhold on disagreement.**
  Compare by minted `vrs_id` where both sides can be minted, because it needs no tolerance. Probed for
  RM270: a respelling mints one id (`rs72613567`, `rs77944059`) and S117's wrong event mints two
  (`rs8176719`). Elsewhere, use `parsimony_reduce` plus a reference window. A disagreement is a finding
  naming both placements, and the row is not written. The count of rsIDs that had only one witness is
  published beside it (`@tautology-zero`).
- **Record the witness on the row.** A new optional `resolution.csv` column saying which second
  authority was asked and what it answered, tri-state. This is the minor-legal addition this item was
  already sized for.
- **S121's third ask is inverted, not adopted.** The VRS id is the arbiter, not the hazard: the three
  rows S121 cites mint the *same* id as ClinVar's spelling, so their ids are correct. A −1-class row
  is withheld whole, id included, by the first bullet.

This is the same failure `@start-1based` recorded on 2026-08-06 ("validate-by-redundancy assumes
independence"), and the RM31 residual (0.5) that went unfiled. The postmortem of the 2026-09-27 round
covers the procedure side.

## RM270 — an indel's artifact key is its source's spelling: a left-aligned VCF misses a respelled row, and the spelling-independent id the enricher mints never reaches the artifact

**Severity** high · **Status** open — **a minor, release undecided** · **Owner** enricher (resolution
fill, `vrs.mint_resolution_rows`) + compiler (the parquet column) · **Motivating case**
[S120](CONSUMER_SUGGESTIONS_HISTORY.md#s120--the-format-declares-no-coordinate-normalization-convention-so-a-legal-respelling-of-an-indel-is-a-silent-position-join-miss-no-one-is-wrong-is-the-footgun)

**What was confirmed.** The three cases S120 cites (`rs72613567`, `rs77944059`, `rs333` CCR5-Δ32) sit
in our Ensembl snapshot one base right of ClinVar's left-aligned spelling, which is also what the
callers emit. Against GRCh38 (UCSC `hg38`; Ensembl REST was down) each pair gives the same haplotype,
so they are one event spelled two legal ways. That is RM267's harmless +1 class, not its wrong-event
−1 class. Nothing in the contract names a normalization. The compiler cannot apply one either, because
left-alignment reads flanking sequence and the compiler has no sequence (P2). So an indel's
`variant_key` is `chrom:start:ref:alts` in whatever spelling its source used. Compiling
`reference_examples/hboc_palb2` keys `rs1555461597` as `16:23635706:G:GT`.

**The identity that would join them already exists and is dropped.** The enricher mints each indel's
`vrs_id` over the *fully justified* allele. Probed: both spellings of `rs72613567` mint
`ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7`, and both of `rs77944059` mint
`ga4gh:VA.ks2GTWYOW0aKfGbJ2aeQUOZxOT_xC2ts`. S117's `rs8176719` pair mints **two different** ids, so the
id also tells RM267's wrong event apart from a respelling instead of masking it. That id lives in
`resolution.csv`, which has no parquet by design. Of the compiled parquets only `frequencies.parquet`
carries a `vrs_id`, and that one is gnomAD's. `@dont-discard-computed`.

**Candidate repairs, and why each is wrong or partial.**

1. **Compiler left-normalizes and stamps a field** (the reporter's preferred option). Refused twice.
   It needs reference sequence in the compile path, the line COMPILER.md § the VRS verify pass says
   not to cross (P2). And on an *authored* coordinate it rewrites a value `reverse_module` then
   re-emits, so lap 1 moves `content_signature` (P7).
2. **An authored `coordinate_normalization` key.** It is a claim no offline tier can check. It costs
   the full authored price (P9) and would be believed by exactly the consumer it misleads. As a
   **verdict the enricher stamps** (tri-state: checked left-aligned / not / unknown), it is honest and
   minor-legal, and it is part of the answer.
3. **The enricher left-normalizes the coordinates it fills.** Legal: a resolution fill is outside
   `content_signature` (`@rm43-positional-fill`). It fixes the +1 class for rsID-authored rows. It
   does not reach an authored coordinate. For those the enricher reports the normalized spelling as a
   finding and never rewrites the cell (`@enrichment-is-validation`). `@sidecar-authoritative`: it
   reaches an existing table only on `--rederive`.
4. **Carry the per-ALT `vrs_id` onto the variant parquets.** A parquet column is approximately free
   (P9) and it is already computed. It gives a consumer who can mint VRS from its VCF a key that does
   not depend on spelling. Alone it is not enough, because minting an indel needs sequence access the
   consumer may not have. Hence it pairs with 3.

The build is 3 + 4, plus the stamped verdict from 2. The part that ships without a decision, the
consumer guide stating that no normalization is guaranteed, landed with the S120 reply.


**Pinned by RM291 (2026-09-27).** `compiler/tests/test_consumer_join.py` joins every reference example
against a bcftools-normalized ClinVar slice, and the two SHOX rows Ensembl spells at `X:634690`
(`AGAG>AG`, `AGAG>AGAGAG`; ClinVar and callers write `X:634689`) are its expected misses, pinned to
this item. Shipping this empties that set, and the test fails until the pin is removed.
## RM272 — an answered-but-unplaceable rsID has no structured name in `EnrichmentResult`

**Severity** low · **Status** open — **a minor**, for the `0.8` branch · **Owner** enricher
(`EnrichmentResult`) · **Motivating case** RM268 and RM271, 2026-09-27

RM268 withholds a live REST locus whose anchor base cannot be read, and RM271 withholds loci whose
alleles are not bases; RM274 keeps an indel the reference could not settle, and drops one it showed is
a different event. On `main` all of these are reported by a log warning only, because a new
`EnrichmentResult` field is minor-class (the first RM268 commit added `unanchored_rsids` there and was
fixed forward). A caller reading the result sees these rsIDs only in `unresolved`, which is silent about
why, the gap `unreachable_rsids`, `unconsulted_rsids` and `allele_mismatches` each closed for their
state. Add the field (or fields) on `0.8`, beside those, and decide whether "anchor base unreadable"
(transient, re-run) and "not a base" (permanent) are one list or two. · *related* RM268, RM271, S20, S85

## RM275 — seven derived fact tables have no duplicate rule, so two contradicting rows under one key compile green under `--strict`

**Severity** medium · **Status** open — **a minor** (re-sized 2026-09-27, see the last paragraph), with
refusal at **1.0** · **Owner** compiler (`_TABLE_DUPE_KEYS`) · **Motivating case** RM107's residual (0.6), *"it wants its own item"*,
found unfiled by the 2026-09-27 postmortem sweep (P3) · *related* RM107, RM109, RM124, RM130

RM107 widened the duplicate check to `sources.csv` and wrote down what it left: *"The remaining gap is
the other fact tables, which have no duplicate rule at all; RM109's own defect produced exactly such a
pair and nothing reported it."* Walked on 2026-09-27, `_FACT_TABLES` minus `_TABLE_DUPE_KEYS` is
`frequencies`, `gene_metrics`, `literature`, `gene_validity`, `clinical_assertions`, `gwas_effects`
and `expression_effects`. RM124 and RM130 registered their own tables, and none of these.

**Reproduced.** `reference_examples/hboc_palb2` with its first `gene_validity.csv` row duplicated and
the copy's `classification` changed from `definitive` to `refuted`. `compile --strict` exits 0, and
`gene_validity.parquet` carries both rows for `PALB2 / MONDO:0012565 / autosomal_recessive`. A consumer
reads one or the other depending on row order.

**Two constraints on the build.**

- **Derive each key from the merge key the enricher already writes the table by**
  (`base.merge_key`, `@suppression-from-merge-key`), never a second hand-kept tuple. `gene_validity`
  keeps two rows on purpose when the source's classification drifts (the comment at
  `gene_validity.py:288-311`). So "duplicate" means **both stated and different** under the merge key
  (`@absent-is-not-different`), not merely a repeated key.
- **Refusing is a tightening.** A published module carrying such a pair compiles today, and P3 says
  existing modules keep validating inside a major. So the check lands as a warning in both modes on
  `main`, and becomes a refusal at 1.0 (a 1.0-tracker line when this is built).


**Re-sized to a minor, 2026-09-27, before building.** The warning needs its own code, and a new member
of `VALID_WARNING_CODES` is not legibility-only: `ModuleManifest.warnings_summary` validates every key
against that closed set, so a just-dna-format 0.7.2 reader **refuses** a manifest carrying the new
code. That is an old-reader break (the INTEGRATION_0_7 shape), which `main` cannot take. Reusing an
existing code would name the wrong finding (`@warning-code-names-the-finding`), and a log line alone
is invisible to every consumer reading findings. Build it on the `0.8` branch, with the INTEGRATION
note that says a reader must be at 0.8 to read such a manifest.
## RM294 — STRchive's evidence grade has no place in the module, so a Refuted locus is doubted only in a draft note

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** format / enricher ·
**Motivating case** RM276's minor half, split off when the warning shipped on 2026-09-27 · *related*
RM276, RM170, RM165

RM276 names a drafted locus STRchive grades `Refuted` or `Disputed`, in a note the drafting run prints
once. Nothing in the module keeps it, so the next reader of `repeat_alleles.csv` sees `DMD`'s bands
with no trace of the source's doubt. Carrying it is a minor: an authored column costs full price (P9),
and STRchive's vocabulary is open upstream (`combobox: true`), so a closed `frozenset` would have to be
priced against a source that adds members. The alternatives to weigh first are a derived sidecar
(half price) or the manifest's provenance block, and whether RM170's CIViC answer already fixed the
shape. Decide on the `0.8` branch.

## RM278 — the `compile` command cannot pass `ensembl_reference` or `ba1_threshold`, so every CLI-compiled manifest has a null `ensembl_reference`

**Severity** low · **Status** open — **a minor**, for the `0.8` branch · **Owner** compiler (`cli.py`
`compile`) · **Motivating case** RM218's *surfaced, not fixed* (§13.8), which left the question open
and tracked nowhere, found by the 2026-09-27 postmortem sweep (P6) · *related* RM218

**Confirmed on 2026-09-27.** `compile_module` takes `ensembl_reference` and `ba1_threshold`, and
`just-dna-compiler compile --help` offers neither. So
`manifest.compilation.ensembl_reference` cannot be stamped by the shipped command, and a module
compiled through the CLI records no reference, whatever it was resolved against. `ba1_threshold` is
the ACMG BA1 cutoff its own docstring says a carrier-allele module would want to move. COMPILER.md
states the gap and `test_cli_parity.py` does not assert compile-flag parity, so nothing will move it.

**Why a minor, not a patch.** Two new CLI options are new public surface, and `main` takes none
(the RM268 fix-forward). The decision is small: add both, or say in COMPILER.md why the CLI
deliberately stays narrower than the API. Either way, extend `test_cli_parity.py` to assert the
decided set, so the next parameter cannot drift in unweighed.

## RM281 — the PGx lane reads one of ClinPGx's archives, and `clinicalVariants.zip` bears on a shipped table kind

**Severity** low · **Status** open — **a minor, release undecided** (a source adoption) · **Owner**
enricher (`clinpgx_build`, `clinpgx_draft`) · **Motivating case** RM166's *"It wants its own number"*,
unfiled until the 2026-09-27 postmortem sweep (P9) · *related* RM166, RM173, RM175

RM166 noticed that ClinPGx publishes at least twelve archives while the lane builds from one
(`summaryAnnotations.zip` today, per RM173). `clinicalVariants.zip` is the one that bears on a shipped
kind: about 5,190 rows of `pharm_variants.csv` territory. Its `type` is a six-member base vocabulary
that **comma-combines**, so an adoption has to normalize the *combination*, not the token
(`@one-normalizer-two-spellings`).

**Confirmed on 2026-09-27.** No module in `enricher/` names `clinicalVariants`. The lane's builder
reads `summaryAnnotations.zip` and refuses the retired `clinicalAnnotations.zip` (RM173), and the
`drug_labels` lane is separate.

**Why a minor.** Adopting it is a new drafting route, or new columns in a published snapshot. It is
also the same terms as the rest of the lane (CC BY-SA, no sale), so it widens nothing on the licence
axis. That half is RM282.

## RM282 — the PGx lane has one licence class, CC BY-SA with no sale, and nothing looks for a source outside it

**Severity** low · **Status** open — **a minor, release undecided** · parked on a survey chosen for
terms first, and the class is settled by what it finds · **Owner** enricher (source adoption) · **Motivating case** RM166's *"it
wants its own entry"* (also PROPOSAL_0_7_PT2 § the decision), unfiled until the 2026-09-27 postmortem
sweep (P9) · *related* RM166, RM281, `@pgx-research-only`

RM166 closed its FDA half measured: *"the lane does not gain a member outside its licence class by
this route, and the direct route cannot supply one either"*. It then said that if licence
diversification for the PGx lane still matters (*"it plausibly does, since it is a single point of
failure on the axis the format gates on"*), it wants its own entry, with candidates chosen for their
terms first. No entry was written.

**What is true today.** ClinPGx, CPIC and PharmVar are all CC BY-SA with no sale
(`@pgx-research-only`), and the compile gate (`@gate-is-data-driven`) refuses a commercial declared use
on every module drafted from them. A commercial author has no PGx source at all.

**The gate, and why it is satisfiable now.** A survey of PGx sources ranked by terms before content.
Anyone can do it today and it needs nothing built. If it finds a candidate, adopting it is a normal
source adoption (a minor). If it finds none, this closes as measured, with the survey as the record.

## RM283 — nothing notices the ClinPGx archive the lane builds from going quiet, which is how it served a fourteen-month-old snapshot

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** enricher
(`clinpgx_build`, its `release.json`) · **Motivating case** RM175's *"that gap is the honest
remainder"*, left unfiled, found by the 2026-09-27 postmortem sweep (P10) · *related* RM175, RM173,
`@currency-asks-the-source-not-the-cache`

RM175 found the lane building from `clinicalAnnotations.zip`, retired upstream and frozen on S3 for
fourteen months while still answering 200. It shipped a narrow guard, refusing the retired member
names, and listed three wider ones it did not build: audit each default URL against the source's
listing, record the S3 `Last-Modified` beside `CREATED_*.txt` in `release.json`, and fire when one
archive of a multi-archive source is much older than its siblings. It closed with *"Nothing built
here would notice `summaryAnnotations.zip` itself going quiet, and that gap is the honest
remainder"*, and gave that remainder no number.

**Confirmed on 2026-09-27.** `clinpgx_build` records `CREATED_*.txt` only. It reads no
`Last-Modified` and compares nothing across archives.

**What to build, cheapest first.** Record `Last-Modified` in `release.json`. That is a new field in a
published snapshot's description, so it is minor-class. Then a finding that compares it with the
sibling archives' dates on the same fetch, reporting and never refusing (a source going quiet is not a
`strict` matter, `@a-source-recuring-is-not-a-strict-matter`). The URL audit needs a browser (RM175's
trap: every ClinPGx HTML route is a JS shell), so it stays a manual step written into the lane's
rebuild runbook, not machinery.

## RM284 — a skip is a fact about the run, and `verification.json` has no run-level place to keep one

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** format (the
verification document) + enricher (the writer) · **Motivating case** RM72's *"a run-level fact needs a
run-level place, which is a separate question and was not opened"* (decided in 0.6 PT2), found unfiled
by the 2026-09-27 postmortem sweep (P11) · *related* RM72

RM72 decided the merge rule for `verification.json`: newest wins between two records of the same
disposition, and a skip does not displace an answer while the earlier record still binds the authored
bytes (`existing_still_binds`). The design half it answered and set aside is this one. A reader may
legitimately want to know that *today's* enrichment could not reach a source, and under the shipped
rule that fact is dropped: the older `ran` record is what stays.

**Confirmed on 2026-09-27.** No open item names a run-level skip record, and `verification.json`
remains a per-check document.

**Why a minor.** A run-level record is a new field or block in a published document, whatever shape it
takes. The shape question is where it lives: in `verification.json` beside the per-check records, or
in the run's own output (`EnrichmentResult`), which RM272 is already widening on the `0.8` branch.

## RM285 — the MITOMAP lane's two open remainders: `VUS*` withheld, and the unrated-miss identity rows

**Severity** low · **Status** open — **a patch** (either answer is drafter behaviour), two decisions first; the anchoring pass shipped as RM293 ·
**Owner** enricher (`mitomap_miss_build`, `mitomap_draft`) · **Motivating case**
RM171's *"Still open, and none of it blocking"* paragraph and PROPOSAL_0_7_PT3 § *What a first cut
still owes*, never filed, found by the 2026-09-27 postmortem sweep (P12) · *related* RM171, RM273, RM293

RM171 listed what it left, and nothing carried the list. Checked on 2026-09-27 against the local
`mitomap_miss` snapshot (47 unmintable rows, 388 unrated misses).

1. **Closed by RM293 (2026-09-27, `v0.7.3`).** The `:` deletions (`refna="TA"` against `regna=":"`)
   are anchored on the vendored rCRS base at `position - 1` in `mitomap_miss_build`, checked against
   rCRS and joined through RM273's event key: 39 of the 47 `unmintable` rows left that bucket, and the
   8 that stay are `ref_equals_alt` and `non_nucleotide`. RM293 was filed as RM273's residual and did
   not name this entry; the two now point at each other.
2. **`VUS*` is withheld rather than understood.** A MITOMAP legend, or McCormick 2020 read in full,
   decides whether it maps to a `clin_sig` member. Until then the withhold is right, and this is a
   reading task, not code.
3. **The unrated misses are an identity increment with no mappable class.** They are counted and never
   drafted. Whether an identity with no classification earns a drafted row at all is the smaller call
   RM171 deferred.

Indel normalization, RM171's fourth remainder, is RM273 (1). The MITOMAP snapshot has been on HuggingFace since
2026-09-03 (`just-dna-seq/mitomap`), so RM171's publish remainder is already closed.

## RM286 — PharmVar's research-use-only, personal-key restriction lives in `notice` prose, and RM27 closed without the axis RM38 handed it

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** format (`SourceRow`) +
enricher (the PharmVar terms constant) · **Motivating case** RM38's *"belongs to the RM27 design
round"*, a pointer to an item that closed without it, found by the 2026-09-27 postmortem sweep (P13)
· *related* RM38, RM27, `@pgx-research-only`, `@gated-source-caches`

RM38 declined a `SourceRow` column for PharmVar's restriction (research use only, a non-transferable
personal key). The restriction is narrower than `commercial_use=False`, so today it lives only in
`notice` as prose. RM38 handed the axis to *"the RM27 design round, which already owns 'the recorded
axes do not cover every real restriction'"*. RM27 shipped in 0.6 as a record-only redistribution
verdict with the registry named as enforcer. It designed no further axis, so the handoff landed
nowhere.

**One premise to correct before designing.** RM38 sized the column as 1.0 because *"a new column on an
existing parquet moves every compiled module's digest"*. A digest moving is not by itself a reason to
defer (the house coding standards say so), and a new optional column is minor-legal under P3 and P8.
So this is a minor if built.

**What to decide.** Whether research-use-only and personal-key are one axis or two, and whether
either is tri-state like `share_alike`/`commercial_use` (an unestablished permission is never a
permission). Also whether the compile gate reads it, or it stays recorded-only like `redistribution`.
A new authored-schema column costs the full P9 price, though `sources.csv` is mostly machine-written.

## RM287 — ClinGen's dosage pass is a live download with no snapshot lane, so an offline deployment never runs it

**Severity** low · **Status** open — **a minor, release undecided** (a new cache lane) · **Owner**
enricher (`clingen`, `CACHE_LANES`) · **Motivating case** RM39's *"Not done, and it was asked for
explicitly: a ClinGen snapshot"*, never filed, found by the 2026-09-27 postmortem sweep (P14) ·
*related* RM39, RM38, `@gated-source-caches`

RM39 gave the ClinGen dosage pass an `offline` flag and a `skipped_offline` state, so an offline run
says it did not ask. It left the snapshot the reporter asked for explicitly, calling it *"RM38's family
and a much bigger question"*. Nothing filed it.

**Confirmed on 2026-09-27.** `CACHE_LANES` has fifteen lanes and none is ClinGen. `clingen.py` still
fetches the gene-curation list live and skips under `--offline`. Every other pass in the family reads
a snapshot, so an offline deployment gets every answer but this one.

**What building it owes.** A lane, so `docs/CACHE_SURFACE.md`'s checklist applies line by line
(three stages, each absent one with its reason as a field, `repro_out` default, parents). ClinGen's
terms have to be recorded as a `SourceRow` before the lane can be published. A new lane is new public
surface, so this is a minor.

## RM288 — two snapshot builders and the PGx drafter make every caller enumerate their exception family, a question RM101 named and left in a test's exemption block

**Severity** low · **Status** open — **a minor, release undecided** (a public exception base) ·
**Owner** enricher (`cpic_build`, `pharmvar_build`, `pgx_draft`) · **Motivating case** RM101's
exemption block in `enricher/tests/test_pass_exception_contract.py`, *"a real question and a wider one
than this item"*, found unhomed by the 2026-09-27 postmortem sweep (P14) · *related* RM101, RM96,
`@client-exception-contract`

RM101 made every enrichment pass raise one documented type. It exempted `cpic_build.build_snapshot`,
`pharmvar_build.build_snapshot` and `pgx_draft.draft_gene` by name. Their callers spell the family out
(`except (CpicError, CpicBuildError)`, `except (CpicError, *_DRAFT_PRECONDITION_ERRORS)`). That works,
but it is the *list* shape: a caller has to know which types to name, which is the drift RM96 was the
lesson for. The only record of the question is the comment in the test's `exempt` set.

**Confirmed on 2026-09-27.** The three entries are still exempt, and no ROADMAP file names the
question.

**What to decide.** Whether each surface gets one catchable base (a subclass relation over the existing
types, which makes a caller's `except` order load-bearing: `@client-exception-contract`'s AST guard
applies), or whether the list shape is kept on purpose and the exemption comment is rewritten as a
decision rather than a deferral. A new public exception base is new surface, so building it is a minor.

## RM290 — the "vindicated" reading of an unmatched overlay row exists for one overridable table, and nobody decided the others

**Severity** low · **Status** open — **a patch** (a finding's classification), a decision first ·
**Owner** schema (`overrides.VINDICATING_OVERLAY_TABLE`) + compiler · **Motivating case** S60's
*"what we are keeping regardless of the shape"* and RM117, found unhomed by the 2026-09-27 postmortem
sweep (P15) · *related* S60, S52, RM117, RM137

S60 found that an overlay row which no longer changes anything can mean the source caught up: the
author's judgement was later vindicated and the row can retire. The reply kept it as *"a property of
the design rather than a nice detail"*, since S52 had seen the same shape. RM117 built it for exactly
one table: `VINDICATING_OVERLAY_TABLE = "clin_sig_concordance.csv"`, which the compiler routes away
from the generic *"may be mistyped"* finding.

**Confirmed on 2026-09-27.** `OVERRIDABLE_TABLES` has more members, and every other table's unmatched
row still reads *may be mistyped*. On a table whose values a later source release can change (for
example `gene_validity.csv`, whose classifications drift), that is the wrong thing to tell an author
whose correction the source has since adopted.

**What to decide.** Per table, whether an unmatched update has a vindicated reading, and whether that
reading is the only one (as on the concordance table) or one of two, which would be withheld
(`@two-vocabularies-that-do-not-meet-withhold`). Turning the constant into a per-table field on
`OverlayTarget` is internal. Reporting it reuses the existing warning code, so it is a patch.

## RM292 — a verification check does not say what it checked against, so a check that witnesses itself reads as verified

**Severity** high · **Status** open — **a minor**, for the `0.8` branch · **Owner** format
(`VerificationRecord`) + enricher (the check roster) · **Motivating case** the 2026-09-27 postmortem,
blindspot B2 and mitigation M3, decided with the maintainer that day · *related* RM267, RM270,
RM274, `@start-1based`, `@registry-completeness`

Every check that could have seen the indel anchor error either compared a source with itself or was
tolerant by design. The reference-allele check passes a wrong anchor because the anchor base is a real
genome base. `check_rsid_coordinates` abstains on every indel position difference and counts none of
them. The ClinVar snapshot was loaded in the same run and used only as a fallback. `@start-1based`
wrote the lesson down on 2026-08-06 (*validate-by-redundancy assumes independence*), but only as a
sentence.

**The change.** Each check declares two things: the source of what it checks, and the source it checks
against. When those are the same source, the record reads *self-consistent*, never *verified*. A
tolerance that makes a class undecided counts that class and publishes the count (`@tautology-zero`).
It is carried as a field on the check registry and asserted by an equality over the roster, so a new
check cannot ship without stating its witness.

**Why a minor.** The field on `VerificationRecord` is a new member of a published document, and
*self-consistent* is a new verdict vocabulary member. Both are additive and minor-legal (P3, P8).
Price: the record is machine-written, so half cost (P9). Not on `main`.

## RM296 — a PRS has no condition → conclusion table, so `pgs.csv` only restates what the PGS Catalog already publishes

**Severity** medium · **Status** open — **a minor, release undecided** (a new optional binning kind) ·
**Owner** format (schema) + compiler · **Motivating case** the maintainer, 2026-09-27: *"modules are
condition → conclusion by design; just listing PGS is a bit tautological, they have own EFOs"* ·
*related* RM16, RM47, RM289, RM163

**What is missing.** Every other kind a module carries maps a measured condition to an authored
conclusion: a genotype to a `conclusion`, an activity score to a metabolizer phenotype, a repeat count
or a copy number or a heteroplasmy fraction to a band. `pgs.csv` maps nothing. Its row is an accession,
the trait's EFO ids, ancestry and a research tier, all of which the PGS Catalog already publishes per
score. A module cannot say *"above the 95th percentile of PGS000018 in a matched reference: elevated
CAD risk relative to that reference"*, which is the sentence a PRS module exists to carry.

**Why the refusal it replaces was a choice, not a constraint.** `pgs.py`'s docstring says a PRS yields a
Z or percentile within a matched reference distribution, *"which the format does not bin"*. Binning
one is the `activity_phenotype.csv` shape: the consumer computes the number and the module bins it, so
the data-agnostic line (no measured value in a module) holds exactly as it does there. Nothing in the
charter forbids it. A new optional table is minor-legal (P3, P8) and costs the full authored price
(P9).

**The shape, as a starting point.** A `MeasureBinRow` subclass keyed on `pgs_id` (joining `pgs.csv`,
which becomes the declaration the bins hang on rather than the whole module). It inherits bounds,
`measure_tiling`, the `unresolved` no-call sentinel and bin-level `pmid` (RM47).

**What has to be designed, and it is the part that stops this being a tautology too.**

- **The measure's unit and frame are part of the claim.** A percentile and a Z are different axes, and
  either is meaningful only against a named reference distribution. A bin has to say which
  (`measure_unit`, and a reference identifier), or a band means nothing.
- **Ancestry mismatch withholds.** A sample outside the bin's reference or `training_ancestry` gets
  *unknown*, never the band (the house tri-state). The same applies below `match_rate_floor`, which is
  what `unresolved` is for.
- **`research_tier` constrains the conclusion.** A `research_only` score supports only relative
  statements (*"higher than N% of the reference"*). An absolute-risk band needs `calibrated`. Whether
  that is a check or a documented rule is open.
- **Continuous tiling** is the natural default for a percentile or a Z (`@measure-tiling`).

RM16 (authored weights) is a different question and this does not depend on it. When this ships,
`pgs.py`'s docstring, TABLES.md § `pgs.csv` and ROADMAP_0_8 § RM16's *"a shape the format does not
bin"* all change with it.

### RM297 — the ClinPGx currency check compares a row against an annotation it never cited

✅ **Shipped 2026-09-28 on `main`, uncut — a patch.** The entry is in
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md#rm297--the-clinpgx-currency-check-compares-a-row-against-an-annotation-it-never-cited).
This heading stays only because S122's reply links here, and replies are the triage seat's to
retarget; delete it in the same commit that moves that link. It is a `###` on purpose: a `## RMn` here
is an open item to the §4 counter (`test_triage_tools.py`), and this one is not open.

## RM298 — nothing records per row that a `pharm_variants.csv` row came from ClinPGx

**Severity** medium · **Status** open — **a minor, release undecided** (a new optional authored
column) · **Owner** format (`PharmVariantRow`) + enricher (`clinpgx_draft`, `clinpgx`) · **Motivating
case** S122 via RM297, decided with the maintainer 2026-09-27: *"the mitigation is warning, not
blocking. Solution comes in minor"* · *related* RM297, `@source-vs-authority`, `@write-the-sourcerow`

**What is missing.** Provenance for this table is recorded per `(source, layer)` in `sources.csv`. A
module that mixes ClinPGx-drafted rows with rows a curator took from an article, CPIC or DPWG cannot
say which is which. So the ClinPGx currency check cannot tell a withdrawn ClinPGx annotation from a
row that never cited one, and RM297 has to withhold on both.

**The shape, as a starting point.** An optional per-row column naming the source whose accession
`annotation_id` is. `draft_pharm_variants` fills it, and a curator may set it or leave it empty. The
check then refuses under `strict` on an absent id only for rows that name ClinPGx, and withholds on the
rest. Empty stays the unknown arm, never "not ClinPGx".

**To design before building.**

- **The name and the vocabulary.** The value set is the `sources.csv` `source` column, so an
  undeclared name is a finding. Audit the name against the reserved namespace (P5).
- **Back-fill for published modules.** An existing drafted row has none. Whether `draft-clinpgx`
  fills it on a row it recognises as `already_present` is a merge-not-clobber question
  (`@draft-appends`: drafting appends and never mutates).
- **Whether other tables want it too.** The same gap exists wherever one table takes rows from
  several sources. Build it here first, on the table with the incident.

**Price and legality.** A new optional column is minor-legal (P3, P8) and costs the full authored
price (P9), because a curator has to learn it. That cost is why it waits for a minor and a case,
rather than shipping with RM297.

## RM300 — the manifest cannot say how many rows are pathogenic, only how many carry the folded flag

**Severity** low · **Status** open — **a minor, release undecided** (new optional manifest fields) ·
**Owner** format (`manifest.Stats`) + compiler (`_variant_stats`) · **Motivating case** S123 in
CONSUMER_SUGGESTIONS_HISTORY.md, via RM299 · *related* RM299, S43

**What is missing.** `stats.pathogenic_count` and `stats.benign_count` sum the legacy booleans, and
each boolean folds a tier pair. A catalog facets on the listing without reading the artifact, so it
cannot split `pathogenic` from `likely_pathogenic`. just-dna-lite's card had to fall back to a tooltip.
The reporter's own measurement for `just-dna-seq/pathogenic`: 403,534 `pathogenic` rows and 215,095
`likely_pathogenic`.

**The shape.** Per-tier counts derived from `clin_sig` (the effective value, so a boolean-only row
still counts through `clin_sig_from_booleans` where it can), beside the existing fields. The existing
fields keep their meaning. Whether it is a count per tier or a mapping keyed on `VALID_CLIN_SIG` is
the one design question: a mapping takes a new tier without a new field. Decide whether distinct
variants per tier are wanted too, since the existing counts are per genotype row.

**Legality and price.** A new optional manifest field is additive and minor-legal (P3). It is not in
`artifact.digest`, and the compiler writes it, so it costs nearly nothing (P9). Not on `main`.

## RM302 — one `conclusion` serves every place a report shows it; a table cell, a details card and an explanatory mode want different wordings

**Severity** medium · **Status** open — **a minor, release undecided**; principle decided, shape kept
open (see *Decided*) · **Owner** format (the authored models) + compiler (the parquet columns) ·
**Motivating case** the maintainer, 2026-09-27: a report shows a variant's conclusion in a table, in a details card and in
an explanatory mode, and one text cannot be right for all three · *related* RM7, RM28, the "not format
scope" note on lay-language rendering

**The ask.** Today every annotation carries one `conclusion`, the detailed wording. The report needs up
to three **registers** of the same claim: **detailed** (today's text), **lay** (a simpler explanation for
someone without the background), and **concise** (scientifically accurate but very brief, for a table
cell). They are one claim written three ways, never three claims.

**Where `conclusion` lives today**, all authored: `VariantRow` (required), every `MeasureBinRow` kind
(required), `DiplotypeRow` (required), `PharmVariantRow` (required) and `StudyRow` (optional). It is
also inside `annotations.parquet`'s key, `(variant_key, conclusion, negatives)` (USE_CASES § the S-key
rework), which constrains every option below.

**What the charter already settles.**

- **Legal as a minor** (P3/P8): new optional columns or a new optional table. `conclusion` itself stays
  what it is and stays required; it becomes the *detailed* register by declaration, not by rename (a
  rename is a removal plus an addition, major-only).
- **Not in any key.** A register is a rendering of the claim the key already identifies. Keying on it
  would split one effect into several rows whenever an author adds a lay text, the dedup failure the
  annotations key exists to prevent.
- **Not the refused "lay-language rendering".** That note (§ Not format scope) is about *generating*
  patient prose from a CURIE, a presentation job. This is text a curator writes and signs, which is
  annotation data like `conclusion` is. The entry adds a line there so the two are not read as one.
- **Priced at full** (P9): every option is authored text, the most expensive layer. The argument for
  paying is that a consumer cannot derive a correct lay or concise wording from the detailed one
  without an LLM in the loop, which the charter keeps out of every tier.

**Decided by the maintainer, 2026-09-27.**

- **Tools never write a register; authors and curators may, if they see fit.** No drafter, enricher
  pass or compiler step fills, rewrites or derives a lay or concise wording, and none is required: a
  module with only `conclusion` is complete. This is the line the § Not format scope note on
  lay-language rendering draws from the other side.
- **Shape: kept open, with two columns as the default.** Unless something below changes it, the build
  is option 1: two optional columns on the carrying kinds.
- **The exception is meta-conclusions.** If [RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half)
  lands its own table, the registers may belong there instead (a meta-conclusion is the claim a report
  most needs in lay words), and the two items then decide the shape together.

**Design options, as they stood before the decision.**

1. **Two optional columns on each carrying kind** (`conclusion_lay`, `conclusion_concise`, names to be
   audited under P5). Simplest to read and to author row by row; costs two columns on five kinds, and
   every future register is another column on all five.
2. **One optional side table** (`conclusions.csv`: the row's key, a closed `register` vocabulary, the
   text). One CSV, one concern: an author who writes no registers never sees it, a new register is a
   vocabulary member rather than a column, and the key is the carrying row's own. Costs a join for
   every consumer and a key per carrying kind.
3. **A register vocabulary with `detailed` implicit** either way, so `conclusion` never has to move.

**Open questions.**

- Which of the five kinds need registers. `StudyRow.conclusion` is a study's finding, not the report's
  claim, and may not.
- Does `content_signature` include the registers? They are authored claim text, so the default reading
  is yes; the counter-argument is that a lay rewording does not change what the module asserts
  (`@provenance-beside-a-claim-is-outside-content-identity` decides it).
- Language is a **separate axis** from register (P5: no overloaded fields). A lay text in German is
  register `lay`, language `de`; a design that folds the two into one vocabulary would have to be
  unwound when a second language arrives. Reserve the language axis's name now if it is expected.
- Does the reference consumer (just-dna-lite) need all three, or `concise` first? That orders the build.
- Should drafting ever fill a register? The house answer so far is that a provider fills facts, never
  prose; a register is prose.

## RM304 — a `vrs_id` does not say which VRS minted it, and VRS 2.1 moves some insertion ids

**Severity** high · **Status** open — **a minor, release undecided**, to land before RM270 · **Owner**
format (where the version is recorded) + enricher (the minting) · **Motivating case** [GKS_SURVEY.md](probes/GKS_SURVEY.md) §0 findings 2 and 3,
2026-09-28

**Two facts, both measured in the survey.**

1. **The id carries no version.** For BRAF V600E (`chr7:140753336 A>T`) three `ga4gh:VA.` ids exist:
   ours under VRS 2.0 (`…Otc5ovrw…`), vrs-python's VRS 1.3 computation (`…fZiBjQEo…`), and the ClinGen
   Allele Registry's (`…HaPTmn-r…`, a VRS 1.x shape). All three are well-formed and none says which
   spec produced it. Nothing in the repo records the version: `grep -rni 'vrs_version'` over
   `schema/`, `enricher/` and SCHEMAS.md finds nothing.
2. **VRS 2.1.0 (2026-09-01) changes ambiguous-insertion normalization**: it now picks the smallest
   repeat-unit factor where 2.0 picked the greatest, and that moves the digest of affected alleles.
   vrs-python has not implemented it. Both 2.3.3 (ours) and 2.4.0a4 still iterate the factors
   descending, and the change is open as vrs-python issue #637. Today everyone we compare against
   mints 2.0.x ids: our enricher, ClinVar-GKM and gnomAD. The first vrs-python release that ships the
   2.1 rule will make a fresh `enrich` mint a different id for some insertions than the one stored
   in `resolution.csv` and the one gnomAD publishes, with nothing to say why.

**Why it is filed before RM270.** RM270's candidate repair carries the enricher's `vrs_id` onto the
parquets as the spelling-independent join key. A key whose derivation silently changes under a
dependency upgrade is the failure RM270 exists to remove, moved one layer down.

**Mitigation shipped separately, the same day.** `ga4gh.vrs` is capped `<2.4` in the enricher, so no
upgrade can change the rule unannounced. The cap is a stopgap. It is lifted by this item, never
quietly: once the version is recorded, an upgrade becomes a declared re-id instead of a silent one.

**Open questions.**

1. **Where the version lives.** It could be one run-level fact on `resolution.csv`'s provenance or in
   the manifest (every id in a run is minted by one library), or a column beside `vrs_id`. Both
   spellings of one allele can coexist only in the column form. The run-level form is cheaper, and a
   merge-not-clobber sidecar mixing runs is the case that breaks it (`@currency-cannot-be-a-column`
   asks which run writes it).
2. **What the verify pass does on a version mismatch.** Recomputing a stored 2.0 id under 2.1 gives a
   mismatch that is neither corruption nor a wrong event. It needs its own reason, never the
   existing mismatch error (`@vrs-three-outcomes`).
3. **A pinned insertion.** The ground-truth tests pin substitutions against gnomAD. `rs72613567`
   (`4-87310240-T-TA` → `ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7`, present in ClinVar-GKM) is the
   insertion to pin, behind `JUST_DNA_NETWORK_TESTS=1` since indel minting reads the SeqRepo proxy.
   The test is what turns a future rule change red.

## RM305 — ClinVar-GKM's allele table is an offline, independent witness for where an indel sits, and nothing reads it

**Severity** medium · **Status** open — **a minor, release undecided** (a new cache lane and a check)
· **Owner** enricher (a lane beside the ClinVar VCF lane, and the check) · **Motivating case**
[GKS_SURVEY.md](probes/GKS_SURVEY.md) §0 finding 4, 2026-09-28 · *related* RM267, RM270, RM292

**What exists.** ClinGen's ClinVar-GKM pipeline republishes each ClinVar release in GA4GH form. Its
`allele.parquet` is 1.09 GB, **CC0**, and holds 4.46 M alleles, each with a VRS 2.0 id beside
`spdi`, `hgvs.g` and a gnomAD-style VCF expression. The survey found **exactly** the two insertion
ids RM270 minted (`rs72613567`, `rs77944059`) in it, and our stdlib SNV ids matched it byte for byte
on the two rows sampled.

**Why it matters here.** Three open items need to know whether a placement is right, and each checks
it today against a source that shares our failure: RM267's anchoring error comes from the Ensembl
snapshot, RM270's respelling from the source's spelling, and RM292 asks that a check say what it
checked against. A table built by a different pipeline, with a spelling-independent id on every row,
is a witness none of them has. It **does not replace** the ClinVar VCF lane: clinical significance
still comes from there, and this lane is used for placement only.

**Things the survey recorded that the design must carry.**

- **Maturity.** The dataset is at 1.0-rc3, and a breaking change landed mid-RC. The lane pins a
  release and records it in `release.json` (RM303's model, if it has landed).
- **Currency.** The latest weekly delta was dated 2026-08-22, about five weeks stale at survey time,
  so the lane owes a currency finding (`@currency-asks-the-source-not-the-cache`).
- **Distribution** is Google Cloud Storage, not FTP. The builder's download is a new transport and
  owes the client contract (`@client-exception-contract`).
- **VRS version.** Its ids are 2.0.x (`vrs_output_2_0_1.schema.json`). Comparing them against ours
  is exactly where RM304's version record is needed.

**Open questions.** Is it a new check, or the witness an existing check gains (RM292's shape)? Should
the lane carry the full 4.46 M rows, or only the 270,161 `ReferenceLengthExpression` alleles and
other indels, where placement is actually in doubt?

## RM306 — no exon structure anywhere in the tier, and AlphaGenome's gene attribution wants one

**Severity** medium · **Status** open — **a minor, release undecided** (a second table in the MANE
lane) · **Owner** enricher (`mane_build`, `gene_spans`) · **Motivating case**
[GKS_SURVEY.md](probes/GKS_SURVEY.md) §5, 2026-09-28; the maintainer's ask for gene/exon coordinate
mapping behind the AlphaGenome lane

**What exists.** `gene_spans.py` reads the MANE *summary* for one span per gene, and its docstring
fixes the rule: a span is a query hint, never an attribution. Nothing in the tier knows an exon.
`grep -ri exon` over the enricher finds only `civic_identities.py`.

**The measured options, lightest first.**

| Option | Size | Covers | Misses | Licence |
|---|---|---|---|---|
| **MANE Ensembl GTF**, a second file in the existing MANE lane | 8.6 MB gz; 19,437 transcripts, 204,815 exons, CDS and UTR rows, `exon_number`, versioned ENSG/ENST, RefSeq xref | exon boundaries and numbers for MANE Select + Plus Clinical | non-coding genes; non-MANE isoforms | NCBI policy, already `MANE_TERMS` |
| **GENCODE v46 basic GTF** | 29 MB gz | the exact annotation AlphaGenome used, all biotypes | MANE selection, unless joined by ENST | "open access", no named licence (`@no-named-licence`) |
| cool-seq-tool + UTA + SeqRepo | 309 MB install, a UTA Postgres service, 13.5 GB SeqRepo | any transcript version, c.↔g. with exon offsets | nothing AlphaGenome attribution needs | UTA is CC BY-SA 4.0 |

The third is refused on weight, not on merit. It needs a database service and a 13.5 GB store, which
conflicts with the tier's `--offline` provisioning and with "builder in polars, runtime in duckdb".

**Release skew to state, not hide.** MANE 1.5 corresponds to Ensembl 116, while AlphaGenome was
annotated with GENCODE v46 (Ensembl 112). An exon boundary that moved between the two releases
attributes differently in each. The lane records both release labels, and a lookup answers in MANE's
frame by default.

**Open questions.** Is MANE alone enough (1–1.5 days), or does non-coding coverage justify a GENCODE
v46 lane too (about one more day)? And the answering surface: `gene_exons(symbol)` next to
`gene_span`, or a position → (gene, transcript, exon) lookup. The attribution rule in `gene_spans.py`
constrains both: an exon lookup answers *where*, and AlphaGenome's own per-record gene remains the
attribution.

## RM308 — the conclusion-genotype finding runs only on the authoring surface, so a module nobody linted compiles green with a swapped pair

**Severity** low · **Status** open — **a minor, release undecided** (a new warning code) · **Owner** format
(`VALID_WARNING_CODES`) + compiler (`validate_spec`, `compile_module`) · **Motivating case** RM279's
residual, 2026-09-28 · *related* RM279, RM309

RM279 shipped the rule as a hint because the compile half needs a member of `VALID_WARNING_CODES`, and a
new member is minor-class: a reader pinned to an older `just-dna-format` refuses a manifest carrying it.
So an author who never runs `hint` or `lint_rows` still gets a green `--strict` compile on a swapped
pair. The rule is `just_dna_compiler.conclusion.conclusion_genotype_mismatches`, already separate from
`hints` so the compile path can call it. What the minor owes: one code named for the finding (for
example `conclusion_names_other_genotype`), emission at both `validate` and `compile`
(`@parity-by-check`), aggregated by reason, a `features/` scenario, and the phrase pinned in the
COMPILER.md warning catalogue. It stays a warning in both modes: 10 of 10 is a measurement over one
corpus, not a licence to refuse.

## RM309 — a `risk`/`protective` state whose own conclusion negates it goes unflagged

**Severity** low · **Status** open — **a patch** (a hint), parked on a precision measurement · **Owner**
compiler (`conclusion.py`) · **Motivating case** RM279's second rule, 2026-09-28, never measured ·
*related* RM279, RM308

D14 proposed two rules, and RM279 built the first. The second is a row whose `state` is `risk` or
`protective` under a conclusion that negates it: `thrombophilia` `rs1799889 G/G` carries `state: risk`
under *"…is not increased"*. A negation reader is noisier than a genotype token, since *"not associated"*
on a neutral row is correct, and *"does not reduce risk"* can support either state. **Parked on the
same gate RM279 had**, a hand-judged precision over the reporter's six curated modules plus the
registry corpus. The gate is satisfiable today, because both the corpus and the rule exist. Like
RM279 it is patch-class only as a hint, and its compile half would join RM308.

## RM310 — `cache rebuild --only cpic` lets a CPIC outage escape as a traceback, and the lanes after it never build

**Severity** medium · **Status** open — **a patch** (one handler, no surface) · **Owner** enricher
(`caches._rebuild_cpic`) · **Motivating case** found 2026-09-29 while vetting RM288 for the 0.8 pt1
proposal · *related* RM288, RM97, RM101, `@client-exception-contract`

**Reproduced.** `caches._rebuild_cpic` catches `(cpic_build.CpicBuildError, ImportError, OSError)`.
`cpic_build.build_snapshot` fetches through `CpicClient`, which raises `CpicError` on a transport
failure or a 5xx (RM97 made it do so), and nothing in `cpic_build` translates it. With
`build_snapshot` stubbed to raise `CpicError("… 503")`, `_rebuild_cpic` raises instead of returning a
failed `RebuildOutcome`. The CLI's `cache rebuild` loop (`cli.py`, the `rebuild_lane` call) and
`rebuild_caches` have no per-lane backstop, so every lane after CPIC in registry order is neither
built nor reported. `prepare_caches` survives only through its catch-all `except Exception`, which
reports the lane as a generic crash.

**Why it happened.** It is the list shape RM288 records: the CLI's `cpic_build_` names
`(CpicError, CpicBuildError)` correctly, and the second caller, written later, named one of the two.
That is the drift RM96 was the lesson for, and it is the first incident RM288 had lacked.

**The patch.** Add `cpic.CpicError` to the handler, and a test that stubs each builder's client to
raise its documented type and asserts every `_rebuild_*` returns an outcome rather than raising. The
test walks `CACHE_LANES`, never a hand-kept list. Which mechanism stops the next drift is RM288's
question, not this one's.

## RM312 — `test_a_wrapped_diagnostic_is_matchable_through_cli_text` passes or fails on the length of `tmp_path`

**Severity** low · **Status** open — **a patch** (test only) · **Owner** enricher tests
(`test_cli_rendering.py`) · **Motivating case** the 0.8 post-merge suite, 2026-09-29 · *related* RM233

**Reproduced on `main` and on `0.8` alike.** The test's last assertion says the raw CLI output does
**not** contain *"nothing will fetch it"*, because Typer's error box wraps the sentence. Whether it
wraps depends on how long the missing file's path is, and that path is `tmp_path`. Under
`/tmp/pytest-of-mau/pytest-9/…` the phrase fits on one line and the test fails. Under a longer
basetemp it wraps and the test passes. Its docstring says this half "was never environment-dependent";
it is, through the path length. The `cli_text` half, which is the behaviour, holds either way.

**The patch.** Pin the path length. Build the missing path from a fixed long name, or feed a path whose
length makes the box wrap inside the phrase by construction. Drop the negative assertion if it cannot
be made deterministic, since the helper's reason is recorded in the docstring.

## RM313 — RM57's `quality_floor_inverted` warning reads VCF QUAL backwards, and tells authors so on every compile

**Severity** medium · **Status** open — **a patch, taken into 0.8 on 2026-09-30** with its replacement finding, as part of `docs/proposals/PROPOSAL_0_8_PT1.md` on the `0.8` branch; not built on `main` · **Owner** compiler (`_check_quality_inversion`) + format (the `quality_from` description) · **Motivating case** relayed 2026-09-30 by the just-vcf session, which found it checking its own frame schema against VCFv4.5 · *related* RM57, RM6, [VCF_4_4_AUDIT § 5](probes/VCF_4_4_AUDIT.md#5-a-min_quality-floor-against-qual-inverts-on-exactly-the-rows-it-exists-for)

**The misreading.** VCF §1.6.1 item 6 (identical in 4.4 and 4.5): QUAL is *"Phred-scaled quality score
for the assertion made in ALT. i.e. −10log10 prob(call in ALT is wrong). If ALT is '.' (no variant)
then this is −10log10 prob(variant), and if ALT is not '.' this is −10log10 prob(no variant)."* On a
monomorphic record the assertion is *no variant*, so QUAL 60 means P(variant) = 10⁻⁶: a confident
reference call. QUAL is the confidence in whatever ALT asserts on both kinds of record, and an
inclusive floor moves the same way on both. The 4.4 audit's § 5 read it as *"almost certainly
variant"*, and RM57 built that into code.

**What ships the false claim today.** `compiler._check_quality_inversion` emits
`quality_floor_inverted` in both modes on any `requires_callable` row with `quality_from` naming QUAL,
saying *"a HIGH QUAL says the position is probably variant"* (`QUAL_INVERSION_PHRASE`). The
`VariantRow.quality_from` description says the same, and so do the COMPILER.md catalogue,
`test_vcf_conformance_warnings.py` and the `features/` scenario. Its remedy recommends GQ, which Table 2
defines as *conditioned on the site's being variant*, so it is not a reference-call confidence either.

**What survives from § 5.** Its second half: reference evidence is an interval (a `<*>` block;
FORMAT `LEN` in 4.5, with INFO `END` deprecated), found by containment, with `MIN_DP` as the right
depth. And a narrower true finding: a `<*>` block usually carries QUAL `.`, so a QUAL floor on a
`requires_callable` row is a check that **cannot run**, not an inverted one
(`@unreachable-not-absent`).

**The decision.** `quality_floor_inverted` is a permanent key naming a finding that is false
(`@warning-code-names-the-finding`). The patch stops emitting it and corrects the description, the
catalogue and the scenario. The code stays in `VALID_WARNING_CODES`, because removing it is major, and
the registry tests have to accept a retired, unemitted member. The honest replacement, a floor on a
field the reference record usually leaves missing, is a new code and therefore a minor on `0.8`.
Whether to build that at all, or only document it, is the call.

## RM314 — the reference-block rule we print reads INFO `END`, which VCF 4.5 made a cross-sample maximum, so a multi-sample file credits one sample's block to another's positions

**Severity** medium · **Status** open — **a patch** · **Owner** format (the `callable_from` description) + docs (SCHEMAS.md, the consumer contract) · **Motivating case** [VCF_4_5_AUDIT § 1](probes/VCF_4_5_AUDIT.md), 2026-09-30 · *related* RM53, RM54, RM57, RM313

**What 4.5 changed.** §5.5 moves a gVCF reference block's extent to a per-sample FORMAT `LEN`. §1.6.1
deprecates INFO `END` and, when it is present, makes it *"the maximum end reference position"* over
every sample's `LEN`. §5.5 also says a position covered by a sample's own earlier `<*>` block carries
`GT=.` for that sample.

**What we tell consumers.** `VariantRow.callable_from`'s description and SCHEMAS.md's *Reference
evidence is a block* paragraph say a block is *"one record with END="*, found by interval containment
on it. In the record `1 100 . A <*> . . END=199 GT:MIN_DP:LEN 0/0:30:100 0/0:30:10`, sample two called
100–109 only, and our rule credits it with 150. For a `requires_callable` row at 150 that is a
confident absence nobody screened for: the direction SCHEMAS.md itself calls dangerous. The `GT=.` rule
errs the safe way, but our text still sends the consumer to the wrong record.

**The patch (text only).** Read the sample's own FORMAT `LEN` first, and `END` only where `LEN` is
absent (the spec's own fallback). A `.` GT inside that sample's own earlier block is that block's call,
not a no-call. Update the `callable_from` description, the SCHEMAS.md paragraph and its quoted 4.4
record, and the consumer contract. No column, no validator: P3 and P8 are not reached. Severity is
stated for the file the spec permits; no real multi-sample 4.5 file with per-sample `LEN` was measured.

## RM315 — the VCF reserved-key tables we transcribe miss keys the spec reserves, among them `RUC`, and name no spec version

**Severity** medium · **Status** open — **a patch** · **Owner** format (`vocab.VCF_FIELD_NUMBER`, `VCF_COLLIDING_KEYS`, `VCF_NUMBER_MEANINGS`) + docs · **Motivating case** [VCF_4_5_AUDIT §§ 3–4](probes/VCF_4_5_AUDIT.md), 2026-09-30 · *related* RM53, RM54, RM57, RM313

**What is missing.** `VCF_FIELD_NUMBER` claims to transcribe the spec's reserved keys, but it lacks
§3's INFO keys (`RUC`, `RN`, `RUS`, `RUL`, `RB`, `RUB`, `CIRUC`, `CIRB`, `SVLEN`, `CIPOS`, `CIEND`,
`CILEN`, `CICN`, …), §4's FORMAT `CICN`, `NQ`, `HAP` and `AHAP`, Table 2's `PP`, and every 4.5 key
(`LEN`, `LAA`, `LA`, the local-allele family, the base-modification aliases). `CICN` is reserved in both
namespaces with different cardinality, like `CN`, and is absent from `VCF_COLLIDING_KEYS`. And no doc a
consumer reads says which spec version the tables describe.

**Why it bites.** `binning._VCF_MEASURE_FIELDS` names `RUC` as the field a `repeat_count` is read
from, and `RUC` is `Number=.`. Probed on `htt_repeat_expansion` with `source_element` emptied:
`INFO/RUC` gives no warning, while `FORMAT/AD` gives `vcf_pointer_unselected_element`.

**The patch.** Transcribe the missing keys, add `CICN` with its sentence in `VCF_COLLISION_REASONS`
(asserted total), and fix the comment placing the structural keys in §5.6 (they are §3 and §4). Add
`VCF_NUMBER_MEANINGS` entries for `LA`/`LR`/`LG`/`M`: it is read through `.get(..., default)`, so a
missing meaning prints the default silently (`@lookup-with-a-default-hides-a-new-member`). Assert
equality between the codes the table uses and the codes the meanings cover. State "VCF 4.5; a key added
after it is unknown and withholds" in SCHEMAS.md and COMPILER.md. Leave the pinned `"is not a whole
number in VCF 4.4"` phrase alone: it is API and still true. The `M[0-9]+[ACGTUN]` family is a pattern,
so its named aliases go in, and the ChEBI-numbered form stays unknown. No new code.

## RM316 — the `annotated_alt` element rule counts by ALT position, and VCF 4.5's local-allele fields order their values through `LAA`

**Severity** low (medium for the first module that points at an `A`/`R`/`G` FORMAT field with it) · **Status** open — **a patch** · **Owner** format (`vocab.ELEMENT_RULE_MEANINGS`) + docs (the consumer contract) · **Motivating case** [VCF_4_5_AUDIT § 5](probes/VCF_4_5_AUDIT.md), 2026-09-30 · *related* RM53, RM54, RM57, RM313

**What 4.5 added.** §1.6.2: `LAA` lists, per sample, which ALT alleles are in play and in what order.
Every `A`/`R`/`G` FORMAT field has a local equivalent (`LAD`, `LPL`, …) read through it, and a file may
carry only the local one. In the spec's example, ALT `A,C,T,<*>` with `LAA=2,4` gives `LAD=20,30,10` as
REF, C, `<*>`.

**What we say.** `annotated_alt` is *"at its index in the record's ALT list, which is element index+1
on a Number=R field"*. On `LAD`, ALT `C` (index 2) is element 1. A module rightly writes
`source_field=FORMAT/AD`. A consumer whose merged 4.5 file carries only `LAD`, and falls back to it
under our sentence, reads the wrong allele's depth: well-formed and wrong.

**The patch (text).** In `annotated_alt`'s meaning and in the consumer contract: resolve a local-allele
field to its global equivalent through `LAA` before applying any element rule, as §1.6.2 recommends.
The value-ranging rules survive unchanged. A `local_annotated_alt` rule is refused, because it would
make the module describe how the consumer's file was merged (P2).

# Not format scope

Listed so they are not mistaken for format scope, and so nobody re-proposes them.

## RM7 — Evaluation-output / report-card schema

**Severity** — · **Status** **not format scope** — a consumer contract · **Owner** consumer
(`just-dna-lite`) · **Motivating case** verification harness (§1a)

For the verification harness — **NOT a format task.** Per-sample results are a *measurement*, so
by the data-agnostic north star this is a **consumer** contract (`just-dna-lite`), listed here
only so it is not mistaken for format scope.

**Corpus (S115, 2026-09-26).** The first output shape a shipped caller produced, recorded here as
ground truth for whatever RM7 settles on (in the consumer, not the format): a four-state `status`
(`called` / `ambiguous` / `not_assessable` / `no_match` — never silence, never a reference default);
`phenotype` set only when every consistent diplotype agrees; the consistent candidates; a tri-state
per-site evidence list (`called` / `restored_hom_ref` / `no_call`); and a `phase_would_decide`
predicate. The one artifact question it raised — a per-gene defining-site set — resolved (b): it is
the union of the gene's `haplotypes` rows, derivable by any reader, so it stays out of the format
(`@derived-not-stored`).

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
  turning a MONDO term into patient-facing prose is a presentation concern. Author-written lay text is a
  different thing, annotation data a curator signs, and is filed as RM302.

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
**Disposition:** Review at 1.0 whether `weight` stays or is subsumed by `effect_size`. Evidence for
that review is in § D5 of the consumer-note triage below: a real module (`superhuman`) authors
`weight` on none of its 190 rows and declares no `weighting:` block.

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
shipped the PMCID axis in 0.6 and left the `LiteratureRow` key question open (its *re-key on a general
citation id* option), so **this entry now carries both questions**: what a *study row* may be authored
with, and what the pmid-keyed sidecar does with a row that has no PMID. Settle them in one release.

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


## Parking conditions (the gate audit)

A deferred item states what would unpark it. **A gate is only honest when the thing that satisfies it
can exist while the item is still parked** — and the failure mode this tracker exists for is the gate
that cannot: one whose only possible satisfier is a tool built against the very table the item is
refusing to build. Read narrowly, such an item is not deferred, it is closed, and nothing in the
entry says so.

**The rule, for whoever files the next parked item.** Write the gate, then ask *who or what satisfies
this, and can they exist today?* If the answer names something downstream of the unbuilt thing, the
gate is circular and the entry needs a different one — usually the **shape** question hiding behind
the demand question, which is answerable now.

**Swept 2026-09-13** across [ROADMAP.md](ROADMAP.md), [ROADMAP_0_8.md](ROADMAP_0_8.md) and
[ROADMAP_1_0.md](ROADMAP_1_0.md), prompted by the maintainer after
[RM16](ROADMAP_0_8.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest) was caught. Every
item carrying a parked-on / would-unpark clause was checked. **One circular, one marginal, one
possibly already satisfied, and the rest sound** — the sweep's value is mostly the eight it cleared.

| Item | Gate as written | Verdict |
|---|---|---|
| **RM16** — authored PRS weights | "a real consumer" — one that combines authored weights into a score | **Circular.** No such consumer can exist before the table does. Re-parked on *shape* 2026-09-13; the gate itself still needs restating when the entry is next opened for a decision. |
| **RM28** tail — the two remaining cofactor classes (ancestry, family structure) | "Neither is built until a real module needs it" | **Marginally circular**, the same family. A module cannot *need* a cofactor class it has no way to express, so read strictly nothing satisfies this. It survives on the looser reading — an author saying *"I want to write this and cannot"* — which is what the clause should say. Low stakes: both classes are on-demand-only and shapeless by design. |
| **RM122** — the measure lookup as a public function | "what it waits on is a caller, not a decision" | **Sound but possibly already met, and nobody has checked.** The rule is normative prose in SCHEMAS.md today, so a consumer can implement it without the function — which means callers may already exist and be silently disagreeing, which is the exact failure the item predicts. **Ask `just-dna-lite` whether it implements the measure lookup** before treating this as waiting. |
| **RM238** — per-tissue eQTL | "reopen this with a consumer, never with an argument" | **Sound.** Somebody can need a per-tissue eQTL answer without our table existing; they would be asking for the data. |
| **RM164** — `heteroplasmy.csv` with no source | "Reopen it with a source, never with an argument" | **Sound, and the cleanest of the set** — a gate on a measured fact about the world, independent of anything here. |
| **RM28** — the predicate half | parked on a corpus | **Sound.** A corpus is counted off other people's published data; it has three entries and none of them needed us to ship anything. |
| **RM23** — predictor scores | "the acquisition measurement done, and a decision on per-transcript grain" | **Sound.** Both are actions available today; the item is unstarted, not blocked. |
| **RM68** — a drafting provider off GRCh38 | "an author with a non-GRCh38 module saying which outcome they wanted" | **Sound.** Such modules exist — `reference_examples/grch37_build` is one. |
| **RM279** — a `conclusion` checked against its own row (filed 2026-09-27) | a measured precision for the locus-restricted rule | **Sound, and met on 2026-09-28**: 10 of 10 real over 653,706 rows, shipped as a hint. |
| **RM309** — a `state` its own conclusion negates (filed 2026-09-28) | a hand-judged precision over the reporter's six curated modules and the registry corpus | **Sound.** The corpus and the rule both exist today, and RM279 met the same gate the day this was filed. |
| **RM15** / **RM69** / **RM52** and the 1.0 queue | a major-version bump | **Sound, and not this kind of gate.** A release boundary is a schedule, not a satisfier. |

**What the sweep did not find, stated so it is not re-run for a while.** No gate anywhere is parked on
a *consumer report that would have to describe the unbuilt thing* — the `Sn` inbox is a channel
consumers can use before we build anything, and every item that names it is asking for a report about
a problem, never about a solution. That is the structural reason only RM16 failed: it is the one entry
whose gate named the *user of the output* rather than the *holder of the problem*.

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

  **This bullet is a refused mechanism, never a home for a defect** (added 2026-09-27, after the
  postmortem of that day). Most documents cite it for what it is: the reason a repair that would
  rewrite an authored cell is refused. One used it as a home. RM31's genotype-frame residual pointed
  here, and that defect went unowned for 55 days. Its consumer workaround is now in CONSUMING.md's
  indel warning, and the artifact-side answer is RM270. A defect that needs an authored cell rewritten
  gets its own `RMn`, and names this bullet only as the repair it cannot use.

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


- *Fixed by RM121 (2026-08-20): `stats.genes` now unions the gene column of every family a module
  carries. Kept for the triage record.* **`manifest.stats.genes` was derived from `variants.csv` alone,
  so a table-only module published `gene_count: 0`.** Relayed from just-dna-lite (2026-08-21), originally measured by
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

- **Nothing checks a `conclusion` against the other cells on its own row.** *Numbered as RM279 on
  2026-09-27; the genotype rule shipped as a hint on 2026-09-28, with RM308 and RM309 left.* From the same pass (D14),
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

## Freeform suggestions — the 0.7 idea-book

- **A resolver-ladder rung that consults a configured peer** (S94, just-dna-registry, 2026-09-11 —
  *a suggestion, not a request*, in their words, and filed here rather than as an `RMn` for that
  reason). The ladder every snapshot reads is *explicit argument → `$JUST_DNA_<LANE>_CACHE` → shared
  base → live → `None`*; the idea is a rung between the local snapshot and the live source that asks a
  configured registry, so a thin client with no caches has every enricher command work unchanged
  instead of each consumer coding against an HTTP surface separately — the shape `just-dna-lite`'s
  `Source` discovery already has for modules. The consumer has built the serving half (S91–S93 are
  the field notes from it) and named the asymmetry rather than asking for the client half.

  **The one question worth keeping, and it is the gate, not a detail.** A peer serving *answers*
  drawn from a licence-gated snapshot is a different act from a client downloading that snapshot
  under its own `declared_use`: `check_declared_use` gates a fetch, and a read of an operator-built
  snapshot is not a fetch (`@acquisition-gate-is-not-a-read-gate`) — but a rung that fetches answers
  from somebody else's snapshot is neither of those two, and the licence table has no row shape for
  it. ClinPGx and PharmVar are CC BY-SA + no-sale with a personal key; whether an answer served over
  HTTP is a redistribution is outside what RM27 designed: RM27 shipped redistribution as record-only,
  enforced by the registry at *publish*, and a served answer is neither a publish nor a fetch
  (`@redistribution-ungated`). So the design order is: settle what a served answer is under each
  gated source's terms, *then* the rung. Not before, because a rung that works for Ensembl and ClinVar
  and silently also works for PharmVar is the failure mode.

  Two smaller things a design would have to say: a peer's answer is a fourth provenance beside
  `snapshot` / `ensembl-rest` / `ensembl-live` and has to be labelled as one in `checked` (S93 made
  the labels the payload's contract); and `--offline` has to mean *no peer either*, since the
  operator's word for "reach nothing" cannot quietly exclude the one hop that reaches something.
  Nobody has asked for this; when somebody does, start from the licence question.

- **A declared dependency graph over a module's derived sidecars** (S112, just-module-creator,
  2026-09-24 — *"offered as an observation, not a design"*, and filed here rather than as an `RMn`
  for that reason). `expression_effects.csv` is computed from `resolution.csv`'s coordinates and,
  since RM259, can also be computed from the MANE lane's candidate genes. Nothing records that, so a
  consumer re-deriving one sidecar cannot tell that another one built from it is now stale, and
  orders its passes from knowledge nobody wrote down.

  **The shape exists one layer out.** A cache lane's parents are a field
  (`@a-derived-lane-has-parents-and-an-absent-parent-is-not-an-empty-result`), and a parent that
  moved is reported, never silently rebuilt. Spec-directory sidecars have no such field. Today's
  settled answer for downstream staleness is delete-to-regenerate (`@sidecar-authoritative`), which
  costs nothing since 0.7. So this is not a defect to re-file, and it is not a cascade either.

  **What a design would have to answer first.** What does it mean for `expression_effects.csv` to
  depend on `resolution.csv` when it is keyed on `variant_key`, which is rsID-first and does not move
  when a coordinate does? A row can be stale in its *distance* column while its key is still right.
  So a dependency is on columns, not tables, which is what the reporter wrote. Second, a staleness
  signal needs a baseline, and a merge-not-clobber sidecar's rows were written on different runs. Per
  row, the question is which parent state each row was computed from, and no sidecar records that
  (`@currency-cannot-be-a-column`). Nobody has asked for the cascade itself; the observation is what
  was offered.

- **A measure kind for base-modification fractions** (the VCF 4.5 audit, § 6, 2026-09-30). 4.5
  reserves FORMAT `M5mC`, `M5hmC`, `M6mA` and the `M[0-9]+[ACGTUN]` family: the fraction of bases
  modified, `Number=M`, strand-specific. The pointer grammar accepts them and the cardinality lookup
  withholds, so nothing is wrong today. What is missing is a home: no `measure_kind` is a methylation
  fraction (binning one as `allele_fraction` would put two quantities under one name, P5), and no
  element rule selects the value at one base on one strand. FMR1 full-mutation methylation is the
  plausible first case, and `fmr1_cgg_repeat` is in the corpus, but no module or consumer has asked. If
  built, a minor: two vocabulary members, no column, with the names audited first (P5). Design it
  against a real file, as RM65 and RM66 are.

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
  **Update:** S69 shipped the message half (the warning stopped claiming nothing else is lost); the
  home-for-the-three-fields half is [RM265](#rm265--the-panel-deprecation-has-no-accepted-signal-on-the-replaced-branch-the-warning-fires-whether-or-not-you-need-the-three-fields-it-tells-you-to-keep-the-block-for)
  (S114), which showed the replaced-branch warning is unclearable for a module that needs them.

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
discriminator they name is the item). D19 → S69 (the message half shipped — the warning is per-branch
*and* stopped claiming nothing else is lost; the home-for-the-three-fields half is RM265, from S114). D16 → S70 (shipped: `detail` on the clin-sig record and
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
