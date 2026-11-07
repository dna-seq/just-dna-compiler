
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
- **[ROADMAP_0_9.md](ROADMAP_0_9.md)** — items legal in a minor, each waiting on a design question, a
  corpus or a caller. Its predecessor `ROADMAP_0_8.md`, 0.8's scope, closed at the 0.8.0 cut on 2026-11-05 into
  [history/](history/ROADMAP_0_8.md), and its one waiting item, RM28's predicate half, moved here. What
  follows describes the 0.8 file as it was. **0.8 is a stabilization and competitor-parity release, decided 2026-09-11 with
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

**Status:** **0.8.0 is cut, tagged and published** — all three packages at `0.8.0`, on 2026-11-05. The
tag is `v0.8.0` at `e97339a3`, and PyPI has the three releases as of 19:56 UTC that day; what a
consumer checks and changes is [INTEGRATION_0_8.md](INTEGRATION_0_8.md), and the cut's own entry is in
[CHANGELOG.md](CHANGELOG.md). The previous cut was **`v0.7.3`** (2026-09-27: format 0.7.1, compiler
0.7.2, enricher 0.7.3), the last of the 0.7 patches after `v0.7.1` (2026-09-21) and `v0.7.2`
(2026-09-25).

**0.7.0 was cut, tagged and published** on 2026-09-12, all three packages. The tag is
`v0.7.0` at `2001215` and it moved through four positions before settling there, each because a gate
found something rather than because anyone changed their mind; the sequence and the reason for each
move are in
[INTEGRATION_0_7 § 5](history/INTEGRATION_0_7.md#5-readiness). PyPI has all six artifacts as of 15:49–15:50
UTC that day, and their hashes are the ones that section lists. The previous cut was **0.6.6,
`v0.6.6`** (2026-08-21), carrying nine patch fixes: the 2026-08-19 doc-audit round (RM104–RM107,
RM109, RM111), the two shipped items of the S57–S60 batch (RM121, RM123), and S61's lookup fix
(RM125). Everything committed after that tag — the 2026-08-21 output-contract, decision and lookup
rounds' successors, the 2026-08-24 consumer round, the source-adoption round and the whole 0.7 build
round — went out in 0.7.0 rather than in any 0.6 number.

**Re-read this paragraph whenever a version moves, because it has lied three times.** It read *"0.6.4
is the current line"* for two releases, then *"0.7.0 is bumped and not tagged"* for as long as it took
somebody to run `git rev-parse v0.7.0`, and then *"0.7.0 is cut, tagged and published"* as the current
status through three 0.7 patches and the 0.8.0 cut — the same failure the *Active items* heading had,
and the reason each is called out rather than quietly corrected. `schema_version` stays `"1.0"` and
has since 0.4. **Tagged is not published** — they are separate steps and the second is the
maintainer's, so check [CHANGELOG.md](CHANGELOG.md) before promising a field to anyone; for 0.8.0 both
have happened. 0.5.0 went to PyPI on 2026-08-07, with `just-dna-enricher` 0.5.0 the first release of
that package.

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
[ROADMAP_0_8.md](#rm164--heteroplasmycsv-is-a-shipped-table-kind-with-no-source-behind-it).
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
outright, **RM122** parked on demand and moved to the minor-deferral file ([ROADMAP_0_8.md](history/ROADMAP_0_8.md) since
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
[ROADMAP_0_9.md](ROADMAP_0_9.md) / [ROADMAP_1_0.md](ROADMAP_1_0.md) hold the deferred items.
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
the release that will decide it — [ROADMAP_0_8.md](history/ROADMAP_0_8.md) (RM16, RM23, RM28, the deferred
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

## RM311 — a `gene_validity.csv` correction the source has since adopted, or superseded, says nothing

**Severity** low · **Status** open — **a patch** if both arms reuse existing codes (a new one would make it a minor), a decision first · **Owner** schema (`gene_validity`, `overrides`) + compiler ·
**Motivating case** RM290's refuted premise, 2026-09-29 · *related* RM290, RM108, RM117

When ClinGen adopts an author's corrected classification, it publishes a newer curation in the same
currency group, and the corrected row stays, marked `SUPERSEDED` (`classify_currency` deletes nothing).
The overlay `update` still matches that old row, so no finding fires. The author is never told the
source caught up, and never told their correction now targets a superseded curation.

**Two arms, both a value comparison against the group's `CURRENT` row.** If the overlay's value equals
the current curation's, the author was vindicated (`overlay_answer_vindicated`'s meaning). If it
differs, the correction patches history while a newer curation says something else
(`gene_validity_superseded` is the nearest existing code). A group whose currency is undecidable
withholds, as `classify_currency` already does. **What to decide:** whether the second arm is the
existing superseded finding or a new code, which sizes this item.

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

## RM321 — `VariantRow.flags` calls its reserved tags "the tags the tooling acts on", and no tier acts on any of them

**Severity** low · **Status** open — **a patch** for the description; deciding what a reserved tag
*should* do is a separate question · **Owner** format (`spec.RESERVED_FLAGS`, the `flags` description) ·
**Motivating case** the longevitymap v2 requirements (just-dna-lite
`docs/longevitymap_v2/longevitymap_v2_requirements.md` §4.2, §6.2, §10), read against the schema
2026-11-03 · *related* RM28, `@field-description-is-a-claim`

**For longevitymap v2 (2026-11-03):** v2's plan sets `pleiotropic` and `conditional` expecting behaviour. See [the group](history/ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**What was confirmed.** The `flags` description says *"Reserved tags the tooling acts on:
conditional|phased|pleiotropic"*, and the comment above `RESERVED_FLAGS` says the same. A grep over
`schema/src`, `compiler/src` and `enricher/src` finds exactly one reader. It is the compiler's INFO
line, and all it does is leave reserved tags out of the "non-reserved flags in use" list. The
`phased` boolean in `weights.parquet` comes from a `|` in `genotype`, never from the tag. Nothing
reads `conditional` or `pleiotropic`.

**Why it matters now.** The longevitymap v2 plan sets `pleiotropic` on every pleiotropy row and
uses `conditional` as its interim for KL-VS-in-APOE4 buffering. Both choices assume the tooling does
something with the tag. It does nothing, so for a reader the tag is a label and the meaning stays in
the conclusion prose. An author who trusts the description believes some behaviour is attached, and
none is.

**The patch.** Make the description and the comment say what is true: the tags are *reserved names*,
held so a later release can give them behaviour, and today they only stay out of the INFO list.
Pin that with a test that walks the three tiers' sources for readers of each reserved tag. Then a
reader added later forces someone to edit the description.

**Not in scope.** Giving `conditional` a meaning. That is RM28's predicate, and RM28 is parked on
a corpus. The longevitymap KL-VS×APOE4 case is a candidate corpus entry there, not a reason to build
it here.

**Residuals** none yet.

## RM344 — a `.duckdb` Ensembl cache written by duckdb 2.0 crashes a 1.x enricher instead of falling back to the parquet beside it

**Severity** low · **Status** open — **a patch**, `unattended` (about 15 minutes) · **Owner** enricher
(`resolver.py`) · **Motivating case** the liaison's adoption map for duckdb 2, item 2, `docs/UPSTREAM_DUCKDB.md`
(2026-11-04) · *related* RM343

**Measured.** duckdb 1.5.5 refuses a database file written by 2.0: `... with version number 999, but we can only
read versions between 64 and 68`. `resolver.py` opens the deprecated prebuilt `ensembl_variations.duckdb` with
`duckdb.connect(..., read_only=True)` at both of its sites and has no handler. An empty or stale db already
falls back to the parquet `data/` beside it, but a db written by a newer duckdb raises from `connect`. A cache
built on a machine with duckdb 2 therefore stops a 1.x enricher that reads it, although the parquet next to it
would answer.

**The patch.** In the cache-directory case, a db this duckdb cannot open falls back to the parquet `data/`, the
same way an empty one does, and says so in a warning that names the file and the storage version. A
`.duckdb` file passed directly has no parquet to fall back to, so it raises `EnsemblReferenceError` naming the
version and suggesting the parquet cache. The path is deprecated and retired at 1.0. The test writes a db the
running duckdb cannot read rather than mocking `connect`.

**Residuals** none yet.

## RM388 — placement readers bypass `usable_loci`

**Parked, the pm (2026-11-05)**, under the maintainer's rule for audit findings: "for once per known universe scenario defer to 'when roadmap is empty/someone steps on this defect'". **Unparks when** a real `resolution.csv` that reaches compile carries a row off the module's build or a `not_found` row with coordinates (the enricher writes neither; only a hand-written or multi-build table does), or when the roadmap is empty, or when a scope the maintainer highlights touches it.

**Severity** low · **Status** open — **a minor, parked** · **Owner** compiler (`allele_checks.py`, `positional.py`, `resolution.read_resolution`) · **Motivating case** audit round 2, class 3 (the lead's scratchpad audit2/report.md (audit round 2 of 0.8, 2026-11-05)) · *related* RM362

**The gap.** RM362 made `resolution.usable_loci` the one rule for which loci an identity sits at: the module's build, and placements only. `allele_checks.py` (~:60-65, :102-105, :405-409) and `positional.py` (~:239-251) read loci without it and filter neither build nor `not_found`, and `read_resolution` does not filter by build.

**What it would be.** Every placement reader goes through `usable_loci`, with an AST guard that no reader of resolution loci bypasses it.

**Residuals** none yet.

## RM390 — the enricher never states a table-level finding the compile acts on

**Parked, the pm (2026-11-05)**, under the maintainer's rule for audit findings: "for once per known universe scenario defer to 'when roadmap is empty/someone steps on this defect'". **Unparks when** an author reports an `enrich` that passed and a `compile --strict` that then refused on the same table. It is not a defect: compile still refuses correctly, and the enricher would only say so earlier. If it unparks, design it after RM387, which settles what RM374 compares, or when the roadmap is empty, or when a scope the maintainer highlights touches it.

**Severity** low · **Status** open — **a minor, parked** · **Owner** enricher (`enrich/orchestration.py`, `verification_records.py`) · **Motivating case** audit round 2, class 5 (the lead's scratchpad audit2/report.md (audit round 2 of 0.8, 2026-11-05)) · *related* RM374, RM373, RM387

**The gap.** RM374's `rsid_placements_disagree` runs only in the compiler (`resolution_step.py` ~:167), so an `enrich` run that writes a mixed or disagreeing `resolution.csv` says nothing, and the author learns of it only when compile refuses. RM373's mixed-release reason likewise appears only in the `ran` arm of `verification_records.py` (~:433-438).

**What it would be.** The enricher runs the same predicate the compiler does on the table it is about to commit, and warns with the same code and text. RM373's withheld-release reason appears in every arm. Design it after RM387 settles what RM374 compares.

**Residuals** none yet.

## RM396 — six paced clients keep their default interval or their gate private, so a host sharing one gate reads a private name

**Severity** low · **Status** open — **a minor, parked** (the pm, 2026-11-05; triage proposed 0.9). The reporter's
interim, reading `pgs._REQUEST_INTERVAL`, works, and only one host shares one client's pace today. **Unparks when** a host
needs a second client's pace or `clingen_allele`'s, when someone renames a private name the registry reads, or when the
roadmap is empty. Until then, keep `pgs._REQUEST_INTERVAL` and `_gate` as they are · **Owner** enricher (`pgs.py`,
`litvar.py`, `civic_api.py`, `clingen_allele.py`, `pharmvar.py`, `atlas_client.py`, ENRICHER.md) · **Motivating
case** S131 in CONSUMER_SUGGESTIONS_HISTORY.md (just-dna-registry's liaison seat, 2026-11-05) · *related* RM203,
RM156, RM384

**The gap, read on `origin/0.8` at `64c835b9` (the same on `main`).** A host that answers many checks holds one
`PacingGate` per upstream and builds a fresh client around it per check, the shape `gate=` and the S15 sharing
contract invite. Building that gate needs the client's interval, and reading the gate back (`gate.spent`, RM203)
needs the gate. The dataclass clients answer both publicly: a `gate` field, and an interval as a public
constant or a settings field. Six do not:

| Client | Default interval | Gate kept as | Takes `gate=` |
|---|---|---|---|
| `pgs.PgsCatalogClient` | `_REQUEST_INTERVAL` (private) | `_gate` | yes |
| `litvar` | `_REQUEST_INTERVAL` (private) | `_gate` | yes |
| `civic_api` | `_REQUEST_INTERVAL` (private) | `_gate` | yes |
| `clingen_allele` | `_REQUEST_INTERVAL` (private) | `_gate` | **no**: no host can share its pace at all |
| `pharmvar` | `PHARMVAR_MIN_INTERVAL` | `_gate` | yes |
| `atlas_client.AtlasClient` | `ATLAS_REQUEST_INTERVAL` | `_gate` | yes |

ENRICHER.md's RM203 paragraph sends a meter to `client._gate.spent` and names five of the six; `atlas_client`
is missing, which is the hand-kept-list failure (`@registry-completeness`).

**What it would be.** Every paced client takes `gate=`, keeps it as a public `gate`, and names its default
interval publicly (`PGS_REQUEST_INTERVAL` and the like, beside the existing public ones). The private names stay
as aliases, since a downstream reads `pgs._REQUEST_INTERVAL` today (P3 does not bind a private name, but nothing
is gained by breaking it). The reporter's (a) and (b) together, over the six rather than PGS alone. A test walks
every `PacingGate(` construction in the enricher (AST) and asserts its client exposes `gate` and its interval
under a public name, so a seventh client cannot reopen it; the ENRICHER.md sentence about `_gate` goes.

**Sizing.** New public names in the enricher are new surface: a minor. P9 prices it near free (no authored or
published field moves). About an hour with the walking test. Not asked, and not proposed: a PGS field in
`LookupClients`, whose bundle is shared while the PGS score cache is per run.

## RM261 — strip comments from the enricher wheel (measured, deferred)

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** the wheel's size becomes a reported problem (an install that hits a size limit), or the packaging is reworked for another reason, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** · *before parking:* open — deferred by the maintainer on 2026-09-25 as risky ("dangerous,
defer") · **Owner** enricher (packaging) · **Motivating case** the 0.7.2 enricher wheel is 893 KB
zipped, all of it Python source

**Measured on `just_dna_enricher-0.7.2`.** Of 2.58 MB of `.py`, docstrings are 31%, comments 19%, and
code plus whitespace 51%. Removing the comments alone takes the zipped `.py` from 847 KB to 664 KB
(−22%). Docstrings stay in any version of this item: they are the `help()` text and the API pages.

**Why it is not simply done.** `hatch_build.py` would have to leave the original `.py` out of the wheel
and force-include stripped copies. `artifacts` / `force_include` collide on the same path (see that
file's own note). The copies must keep line numbers, with a comment-only line becoming an empty line,
or a traceback from an installed wheel points at the wrong source line. Editable installs must not be
touched. It reaches the **enricher only**: format and compiler are on `uv_build`, which has no hooks,
and covering them means changing their build backend.

**Considered and refused in the same round:** taking the 15 `*_build.py` snapshot builders out of the
wheel (112 KB zipped). `scripts/rebuild-caches.sh` documents `pip install 'just-dna-enricher[dev]'`
then `cache rebuild` as a supported deployment, and `caches.py` imports every builder at module
level. The maintainer kept them in.

## RM248 — a declarative report schema: research, not a design

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** a consumer (just-dna-lite, the registry) asks for a report a module cannot declare today, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** — (unsized, deliberately) · **Status** open — **a minor, parked** — a
research item, asked by the maintainer 2026-09-20. Nothing here is a proposal yet; the exit is a
measurement and a charter ruling, not a draft schema. The class is the most additive outcome this
could have, which is a new optional table or spec block; two of its three exits ship nothing at all · **Owner** unassigned — the placement question is half the research · **Pairs with**
[RM28](#rm28--meta-conclusions-the-predicate-half),
[RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics),
and RM7 below (which is **not** the same item — see *What this is not*)

**For longevitymap v2 (2026-11-03):** v2's §5 is a report specification: a context card, grouping by mechanism, a research view. See [the group](history/ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**The ask, verbatim in intent:** some kind of report schema — Jinja templates or something — where the
*contents* are static and declarative and all the fancy CSS lives downstream.

### Why it is filed as research rather than as a design

Because the charter has something to say first, and it does not obviously say yes. The Non-goals are
explicit: *"No UI and no gene–disease inference. The format catalogs curated annotations that consumers
**join** against variant data; interpretation and presentation belong to those consumers."* A report
schema that describes a rendered page is that non-goal by another name.

The maintainer's own framing is also the resolution worth testing: **a report is a declaration of
CONTENTS, not of appearance.** *What a report says, in what order, keyed to which annotation rows* is
arguably still annotation; *how it looks* is unambiguously downstream. If that line holds, this is
legal and the non-goal is untouched. If it does not — if a contents schema cannot be written without
smuggling in ordering, emphasis or layout — then the honest answer is that this belongs to a consumer
and the entry closes. **That ruling is the first deliverable.**

**Principle 1 decides the other half before any syntax is chosen.** OakVar's reporter modules are
Turing-complete, and that is exactly the shape P1 rejects: code in the compile path, no
byte-reproducibility, a runtime every consumer must embed. Jinja is not obviously safer — it has
loops, filters and arbitrary attribute access, so "a template language" is a spectrum and the sanctioned
escapes are named: a **non-Turing-complete boolean predicate** and **declarative pattern grammars**. Any
candidate has to be placed on that spectrum explicitly rather than adopted because it is familiar.

### What this is not

**Not [RM7](ROADMAP.md#rm7--evaluation-output--report-card-schema).** That entry is a *per-sample* evaluation
output — a measurement, and therefore a consumer contract by the data-agnostic north star. This one is
about the structure of a report over **annotation content**, with no sample in it. The two are adjacent
enough to be confused and are listed together on purpose.

**Not a fourth library**, on today's evidence. The maintainer's read is that it looks like overkill, and
nothing here contradicts that yet: a declarative contents schema is a schema, which is
`just-dna-format`'s job, and a renderer is a consumer's. A fourth tier would only be justified if the
research finds a real body of shared rendering logic that is neither schema nor consumer — and finding
that out is part of the item.

### The competitor evidence, which is the reason this is worth research at all

This pairs with [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)
because the surveys already ran and the reports are where every competitor's declarative layer visibly
ends:

- **ClawBio** — `pharmgx-reporter` is a 2,327-line Python file holding its variant tables inline
  (`PGX_SNPS`, `GENE_DEFS`, `GUIDELINES`: 32 variants, 13 genes, 59 drugs), and
  `clinical-variant-reporter` and `cnv-acmg-classifier` are `planned`. Their reports are good and their
  data is a module in a shape nothing validates. See [`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md).
- **genomi** — a runtime rather than a format, with a curated thirteen-record catalogue. See
  [`probes/GENOMI_SURVEY.md`](probes/GENOMI_SURVEY.md).
- **OakVar** — reporter modules, Turing-complete. The counter-example, and the one this repo's P1
  already has an answer to.
- **SelfDecode and the consumer-genomics vendors** — the reports are the product. Not surveyed here,
  and a survey of what their reports *contain* (as opposed to how they look) is cheap and is probably
  the highest-value first measurement this item can take.
- **`just-dna-lite`** already has a built-in reporting system. It is the reference consumer, so **what
  it does today is the baseline any schema has to beat** — and if it needs nothing from us, that is an
  answer rather than a gap.

### Why it pairs with [RM28](#rm28--meta-conclusions-the-predicate-half)

RM28's surviving half is the **predicate** — a claim keyed on more than one subject, which no brick
holds. Its second corpus entry is exactly a *report* finding: ClawBio's pharmgx-reporter renders one
AVOID across 59 drugs, warfarin, and reaches it through `"special": "warfarin"` — a hardcoded branch
calling `get_warfarin_rec(profiles)`. **The report is where the missing predicate surfaces**: a section
that has to say *"CYP2C9 and VKORC1 together"* is RM28's gap wearing a consumer's clothes, and a report
schema that cannot express it would be shipping the same hardcoded branch one layer up. So the two
items constrain each other: **RM28's answer bounds what a report section can be keyed on**, and the
report is the place where an unexpressible pairing is most visible.

### There is already a presentation surface, and it is small and deliberately bounded

Worth knowing before anything is designed, because it sets the precedent this item either follows or
breaks. `module_spec.yaml` carries `report_title`; `normalize.py` splits **identity** keys from
**presentation** keys with a stated reason per key (`PRESENTATION_AUTHORITY_KEYS`, today just
`short_description`); and `RECOMMENDED_*` vocabularies exist for colours and icons. So the format
already admits *some* presentation, as named keys with per-key justifications and a storing authority.
The question this item should answer is whether a report schema is the same thing at a larger scale, or
a different kind of thing that happens to rhyme.

### What would close this

One of three, and the research is choosing which:

1. **Dissolved** — `just-dna-lite`'s existing reporting needs nothing from the format, and the
   contents/appearance line cannot be drawn cleanly. The entry closes with the reasoning recorded.
2. **Closed additively** — a bounded, declarative contents schema (a table kind, or a spec block) that
   passes P1 and the human-authorable ⇔ machine-precise gate, with a motivating report from a real
   consumer. Then it is an ordinary minor-legal addition.
3. **Parked with a sharper reason** — the shape is real but blocked on RM28's predicate, which is the
   most likely outcome if the warfarin case turns out to be representative rather than singular.

**The cheapest first measurement**, and the one to take before any syntax is discussed: read what
`just-dna-lite` actually renders today, and list every field it needs that a module does not carry.
That is a list, it is finite, and it decides between (1) and (2) without a design round.

## RM181 — a byte digest that moves beside intact signatures says something changed and not what, and provenance has no shift tracker

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** a consumer reports an `artifact.digest` that moved and that the signatures could not explain, or the 1.0 review of the hash family opens, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** · *before parking:* open — **filed 2026-09-03 for the 0.8 review of what the hash family
covers, and a candidate for the 1.0 one if it turns out to want a manifest field per domain** ·
**Owner** format · **Motivating case** the maintainer's decision on S87 (RM180), in
CONSUMER_SUGGESTIONS_HISTORY.md

**The observation.** With RM180, an author rewording an overlay `reason` produces: `content_signature`
unchanged, every fact signature unchanged, `resolution_signature` unchanged, `artifact.digest` moved.
Read from outside, that says *something changed* and nothing more — the byte digest is a canary, not a
locator. Before RM180 the same edit moved `content_signature` too, which was wrong for the opposite
reason: a provenance edit read as a content one. Either way there is no hash whose movement means *the
provenance moved*, and the maintainer's words for the gap were that metadata has no dedicated shift
tracker.

**The shape named: digest by domain.** One identity per concern — content (have), facts per sidecar
(have), bytes (have), and a provenance or metadata one (do not have) — so a consumer holding two
manifests can say which domain moved by diffing the hash family rather than diffing parquets. That is a
separation of concerns, not a new axis on an existing hash, and it is why this is not a repair to
RM180.

**Why it waits.** Three questions before it is an item. What the provenance domain *contains* — the
overlay's three cells only, or also `sources.csv`'s `fetched_at`, `verification.json`'s `checked_at`,
the README bytes and `module_spec.yaml`'s display half, each of which is outside some hash today for
its own reason. Whether it is a manifest field (additive, minor-legal) or a member of the
`*_signature` family, whose roster rule in SCHEMAS is *one per derived sidecar* — and this is not a
sidecar. And whether `manifest.inputs` already answers it: the raw-bytes entry for `overrides.csv`
moves on a reason edit, so per file the answer exists, and what may be missing is the *reading* rather
than a hash. RM126's release record answers the neighbouring question — what a *release* changed about
compiled output — not this one, what an *edit* changed about a module.

**What would close it.** A consumer asking *what moved* and getting the wrong answer from the family
as it stands; or the 0.8 review deciding the family is complete and this becomes a FAQ entry.

## RM188 — the competitor survey — run Calwbio's and genomi's pipelines, read their reports, and re-fold the logic into module mechanics

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** the maintainer names competitor parity as a minor's zone, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** · *before parking:* open — **round 1's two surveys filed 2026-09-13 and their findings
routed; round 2's roster is below, searched for rather than named** · **Owner** format (the survey),
then whichever tier the findings land in ·
**Motivating case** the maintainer's direction, not a consumer report

**For longevitymap v2 (2026-11-03):** its axes 2, 3 and 5 are now numbered, as RM328, RM330 and RM324. See [the group](history/ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**Progress.** Both named competitors are now probed, one document each, and neither turned out to be
a competing *format*: [`probes/GENOMI_SURVEY.md`](probes/GENOMI_SURVEY.md) (genomi is a runtime; its
thirteen-record curated catalogue is a `variants.csv` in Python, and §8 ranks seven annotation gaps,
all priced as derived sidecars) and
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) (ClawBio is 97 agent skills — 68 of them
`planned` — whose genotype-interpreting half carries four hand-curated variant tables inlined as
Python dicts and JSON). The two surveys overlap in almost nothing, which is itself the result: one
reaches for pathway, target–disease and regulatory content we do not carry, the other for the
per-variant clinical axes an ACMG engine reads.

**The ClawBio half's findings are filed, 2026-09-13** — a probe records and the tracker allocates, so
the numbers came from `.claude/rm-next.py` rather than the probe: **RM236** (`consequence`/`impact`,
and RM23's grain question with them), **RM237** (region-keyed ClinGen dosage), **RM238** (per-tissue
eQTL, open but parked on a consumer), **RM239** (fine-mapping posterior), **RM240** (land the
translated nutrition panel in the corpus) and **RM241** (`weighting` does not survive `reverse`). The
sixth finding was not filed as a new item because it is not one: warfarin's multi-gene call is
[RM28](#rm28--meta-conclusions-the-predicate-half)'s surviving *pairing across subjects* clause, and
it went in there as that entry's **second corpus entry**. The genomi half's seven ranked candidates
are recorded in its own § 8 and are not filed here.

**What it is.** A survey of the consumer-genomics competitors, with two named first — **Calwbio** and
**genomi** — done the way PUBMIND_ASSESSMENT was done and not the way a feature comparison is: run
their pipelines end to end on real input, obtain the reports they produce, and read the logic *back*
out of the reports — which annotations they join, at what grain, which rules turn a genotype into a
sentence, and where a number comes from. Then re-fold what survives into the module mechanics here:
a table kind, a bounded rule, a vocabulary member, or a use case in USE_CASES.md that names the gap.

**What it is not.** Not a marketing comparison and not a licence to copy a rule: a competitor's
inference is evidence about what a report *needs*, and the charter's non-goals still hold — no
gene–disease inference in the format, annotation tables only. Where a competitor's logic is an
inference, the outcome here is the *table that would let a consumer make it*, never the inference.

**Method, so it can be repeated.** One document per competitor under `docs/probes/`, the shape of
PUBMIND_ASSESSMENT: what was run, on what input, what came back, what it competes with, what it
complements, and the adoption design if any. Real data, the tool turned on its own output
(`@adversarial-role`, `@probe-uniform-corpus`), and every claim about a competitor pinned to an
artifact obtained rather than a page read — the ClinPGx rounds showed a documented surface and the
real one disagreeing.

**Exit.** Each competitor's probe filed, and its findings either dissolved (already enabled), closed
additively (an RM with a motivating report in hand), or parked with the reason — the
USE_CASES → PROPOSAL loop, entered at the top.

**Round 2 — the candidate roster, built 2026-09-13.** Round 1's two competitors were named by the
maintainer; round 2's were **searched for**, and the search is the first half of the result. Method:
GitHub repository search over eight query shapes (personal genome interpretation, 23andMe raw data,
annotation modules, MCP + bioinformatics, nutrigenomics, pharmacogenomics, ACMG, PGS), sorted both by
stars and by recency, plus `awesome-genetics` (last pushed 2024-03) for the pre-agent generation.
Twenty-two repositories were then **skimmed** — not surveyed — against one question: *does it carry
hand-curated per-variant or per-gene rows a human wrote and committed, or does it fetch public
sources at query time?* That is the discriminator round 1 established: both genomi and ClawBio turned
out to be the second kind, and the curated fraction of each was tiny.

**Re-derive the search with:**

```bash
gh api -X GET search/repositories -f q='topic:personal-genomics' -f sort=updated -f per_page=15 \
  --jq '.items[] | "\(.full_name)\t\(.stargazers_count)\t\(.pushed_at[:7])\t\(.description)"'
```

varying `q` over the shapes above. **Nothing found in the 2026 crop has more than ten stars**, which
is itself a finding: the local-first personal-genomics field is a long tail of weekend projects, and
the established tools are older and narrower. Do not read the roster below as a competitive
landscape — it is a list of places to go looking for annotation *shapes*.

### The four that get a full survey

| # | Target | Pinned | Class | What its survey asks |
|---|---|---|---|---|
| 1 | [OakVar](https://github.com/rkimoakbioinformatics/oakvar) | `d4e8090df8`, 48★, licence NOASSERTION | a competing module format **with a store** | **A fresh peer read, not a migration post-mortem** — the maintainer's framing: *an OakVar module is in essence a plugin, arbitrary code, so it is a module plus half an annotator*. Its manifest (`<name>.yml`) declares `type` (annotator / postaggregator / reporter), `level`, `requires` (other modules), `input_columns`, and typed `output_columns` — a **column contract plus a dependency graph**, where ours is a row schema with neither. Ask what the column contract buys, what `requires` expresses that no module here can, and what is left of a module once the arbitrary code is removed. |
| 2 | SNPedia, via [snappy](https://github.com/zhaofengli/snappy) | `2d5255f`, 52★, BSD-2-Clause; SNPedia content CC BY-NC-SA 3.0 US | the corpus round 1 never had | The largest curated variant-trait corpus in existence: **106,603 SNP entries** frozen into `data/snps.json` from a MediaWiki XML dump, plus `genotypes.json` (per-genotype magnitude / good-bad / summary) and `genosets.json`. Survey **the corpus, not the SPA** — snappy is the extraction route that proves a static dump works, where `OSGenome` (146★) only crawls live. **Its terms are CC BY-NC-SA 3.0 US, established off three primary pages 2026-09-13, which makes it adoptable rather than not** — as an unsellable, share-alike, attributed module of its own. See [USE_CASES § 2e](USE_CASES.md#2e-republishing-a-licence-encumbered-third-party-corpus-as-modules-2026-09-13), now the maintainer's named use case for this format. |
| 3 | [BioMCP](https://github.com/genomoncology/biomcp) | `bb3a1d4ad7`, 630★, MIT | the agent-era tier done at scale | Thirteen times genomi's stars and the same architectural class. Ask the one question genomi could not answer at its size: **when an agent tool surface is the product, what does it end up needing to say about a variant that a table does not?** If the answer is "nothing", that closes the whole class and round 3 can skip it. |
| 4 | [Exomiser](https://github.com/exomiser/Exomiser) | `98f4e0b6f2`, 265★, AGPL-3.0 | phenotype-driven prioritization | The only established tool in the roster that **ships its annotation as a versioned data bundle** rather than fetching it — the closest existing thing to a compiled artifact. Ask what its bundle contains, how it is versioned, and how HPO term sets sit in it, given that [HPO ships no route here](ENRICHER.md) for licence reasons. |

### The three small ones worth a read after those

| Target | Pinned | Why |
|---|---|---|
| [dosedna](https://github.com/alejandro-publius/dosedna) | `530cfe7`, 2★, MIT | Hand-curated PGx over six genes, and the closest small analogue of our `haplotypes`/`diplotypes`/`pharm_variants` trio — plus a committed, provenance-stamped CPIC snapshot (`allele_definition` 39, `diplotype_phenotype` 666, `recommendations` 1,180). |
| [dna-engine](https://github.com/ShadowfetchLinux/dna-engine) | `5791bb3`, 0★, Apache-2.0 | **403 curated markers with the richest per-marker schema found anywhere**: `tier`, `effect`, `transferability`, `chips`, per-genotype label/impact/summary/detail/**actions**, and citations as `(pmid, note)` pairs. Also a deliberate non-interpretive posture — it refuses to translate genotype into phenotype, and says why. |
| [allelix](https://github.com/allelix/allelix) | `4b56bbe`, 30★, AGPL-3.0 | Carries no corpus, and is here anyway: **38 ADRs documenting source-precedence and suppression rules** (PharmGKB non-finding suppression, somatic-on-germline suppression, a GWAS odds-ratio magnitude modifier). Competing-source arbitration is `authority_precedence`'s problem, and this is the only project found that wrote its reasoning down. |
| [Custom-Personal-Genome-Interpretation](https://github.com/dianguan0105/Custom-Personal-Genome-Interpretation) | `15fe28a`, 0★, MIT | Two authored tables: 98 rsIDs carrying **GRCh37 and GRCh38 coordinates side by side on one row** plus population-split MAF, and **540 PRS weights transcribed out of a paper's supplementary table** — see [RM16](#rm16--authored-prs-weights-a-scoring-file-not-a-manifest). |

### What the skim already found — five axes, each sighted independently more than once

**This is the part that did not need a survey.** Convergence across unrelated projects is the
`@probe-uniform-corpus` heuristic firing: when three people who have never met each add the same
field, the field is answering a real question.

1. **Which genotyping arrays can call this variant** — three sightings: dosedna's `array_callable` + free-text `coverage_note` per gene, dna-engine's `chips` per marker, and `MrOrtiz/dna-annotator`'s measured-vs-imputed tiering per source array (it refuses to let an imputed call outvote a measured one). **We have nothing.** `requires_callable` / `callable_from` / `min_quality` ask whether the *consumer's own VCF* saw the position; this asks which *platforms in the world* interrogate it, which is a fact about the variant and therefore annotation. Note the per-gene / per-variant scope split, which is the shape [that already cost 39 variants once](ROADMAP_HISTORY.md).

   **A fourth sighting, and the first with a source and a measurement: S111 (just-module-creator,
   2026-09-24).** `just-prs` already holds the Illumina GSA v3 backbone that 23andMe v5, AncestryDNA v2,
   MyHeritage and FTDNA v2 share, as typed positions on both builds (648,379), plus a 1000G LD-proxy
   table. Measured over 16 real modules' `resolution.csv`: 336 of 965 positions typed (35%). The GWAS
   modules came out near 22% and the PGx panels at 51%, and lifting to GRCh37 lost one position. The
   report asks for a *module-level* expected match rate. Recorded here rather than as an `RMn` because
   it is this axis with a candidate source, and three things a design would have to settle came up in
   the reply ([CONSUMER_SUGGESTIONS_HISTORY § S111](CONSUMER_SUGGESTIONS_HISTORY.md)):
   **(a)** the fact is per variant (*which platforms interrogate this position*), and the module figure
   is a manifest summary derived from it, the way the `literature` block summarizes
   `literature.csv`. The per-variant form is also what the reporter's other use, picking the typed one
   of two lead SNPs in LD, actually needs. **(b)** Counts, never a rate, with *typed*, *LD-proxyable*
   and *not position-matchable* kept apart. The proxy count describes a substitution the consumer's
   engine may or may not make, so it stays beside *typed* and is never added to it. *Position-only* goes
   in the field's name or description, since a position match says nothing about allele or strand.
   **(c)** The source is a snapshot lane, never an import of `just-prs`: the per-chip position sets
   published on the HF org with a `release.json`, walked through [CACHE_SURFACE.md](CACHE_SURFACE.md)'s
   checklist, and the GSA manifest's licence probed before it is republished
   (`@probe-the-real-file`, `@no-named-licence`).
2. **A per-variant claim's ancestry transferability** — three sightings: dna-engine's `transferability`, `Bluefinee/kaiseki`'s Japanese-cohort reconciliation, `drhudsonandrade/OmniGenis` recording discovery-cohort ancestry per GWAS association. We carry `PgsRow.training_ancestry` and `GwasEffectRow.ancestry`, both scoped to their own table; there is no way to say *this variants.csv row was established in one population*. **Numbered 2026-11-03 as [RM328](ROADMAP_HISTORY.md#rm328--no-study-row-can-name-the-ancestry-it-was-measured-in-so-european-only-evidence-is-a-hand-set-flag), for longevitymap v2.**
3. **Effect modified by a non-genetic factor** — two sightings, and genomi is the third: `sinhaankur/open-genome-atlas` splits each marker's evidence by `kind` (diet / lifestyle / geo), **each axis independently cited**; `drdaviddelorenzo/nutrigenomics` scopes its `weight` to a `nutrient_domain`; genomi's own caveat *"folate fortification status of the population modifies effect size"* is the same fact in prose. `CopyNumberRow`'s `modifier_gene` / `modifier_cn` is the precedent shape for a *genetic* modifier and there is no environmental one. Note that the second sighting also lands on `@weight-has-no-unit`: their `weight` at least names the domain it is a weight *in*. **Numbered 2026-11-03 as [RM330](ROADMAP_HISTORY.md#rm330--an-effect-measured-in-one-sex-one-smoking-stratum-or-one-genotype-has-no-row), for longevitymap v2.**
4. **Two sources disagreeing, as a recorded verdict** — three sightings: kaiseki's `DISCORDANCE_RATIO`, which **refuses to publish a consensus frequency** when cohorts disagree; `Gunshipz/genomine`'s cross-tool confidence/disagreement layer; allelix's ADRs. `clin_sig_concordance.csv` does exactly this for clinical significance and **only** for clinical significance — kaiseki does it for allele frequency, where `frequencies.csv` has per-population rows and no verdict.
5. **A hand-assigned salience separate from clinical severity** — two sightings: `alexlaverty/dna-health-report`'s `magnitude` 0–6 per genotype, and SNPedia's own `m` field carried through snappy. `VariantRow.priority` is the candidate analogue; whether "priority level override" means the same thing is a question for the survey, not an assumption. **Numbered 2026-11-03 as [RM324](ROADMAP_HISTORY.md#rm324--there-is-no-evidence-tier-column-so-the-axis-that-gates-visibility-is-a-flags-tiera-token), for longevitymap v2.**

**A sixth shape was seen and is already decided against, recorded so it is not re-raised.**
`dianguan0105/Custom-Personal-Genome-Interpretation` stores GRCh37 and GRCh38 coordinates *on the same
row*, so no liftover is needed at read time. That is the opposite of the rule here — `genome_build`
lives in the manifest and in no parquet column (`@build-in-manifest-only`), the build is injected at
load and never authored on a row (`@build-injected`), and a module is single-build by design with
`reference_examples/grch37_build` as the worked case. Their design buys convenience and pays for it
with two coordinates that can disagree and nothing able to notice. **Not a gap.** Worth one paragraph
in whichever survey reads them, and no more.

**And one that is not an axis but a corpus: [RM28](#rm28--meta-conclusions-the-predicate-half) has a third entry.** snappy's
`genosets.json` carries SNPedia's boolean-combinator DSL — `and(rs4988235(C;C), rs182549(C;C))`, with
genoset-of-genoset nesting for haplogroup trees. That is a third independent grammar for the same
thing after CIViC's molecular profiles (RM174) and ClawBio's guideline logic, and unlike those two it
is a **general-purpose** one written for consumer genetics rather than falling out of one domain.
Counting its operators and its nesting depth is worth doing whether or not the rest of snappy is read.

### Checked and skipped — recorded so round 3 does not re-search them

**Same class as genomi (fetch public sources at query time, no curated content):** `lagodinm/dna-health-report`,
`MrOrtiz/dna-annotator`, `Gunshipz/genomine`, `itsrudaynah/Modrik`, `techninja/asili`,
`drhudsonandrade/OmniGenis` (58k LOC and its own scripts say *"Nothing here is authored"*),
`mentatpsi/OSGenome` (146★, crawls SNPedia live and freezes nothing).
**Pipeline or converter, no interpretation:** `GeiserX/Personal-Genome-Pipeline` (10★),
`captainzonks/GeneGnome`.
**Curated but too thin or too stale to teach anything:** `Michael-Sebero/Genetic-Trait-Detector`
(245 rows, one 432-line file, last pushed 2025-03), `dev-kvt/GenomeUpload` (27 uncited rows inline in
JS, with an LLM writing the actual report).
**Curated only as a panel — a list of rsIDs with no fields on them:** `brandonsaldan/codex` (37★, 225
JSON files of bare rsID membership, all interpretation scraped live from SNPedia, dead since 2023).
**Documentation, not a tool:** `matbanik/agentic-genomics` (a setup guide wiring up three MCP servers
that live elsewhere).
**Not competitors, one line each:** the single-source MCP servers (`berntpopp/clinvar-link`,
`cyanheads/gnomad-genetics-mcp-server`, and our own `dna-seq/ensembl-mcp`) wrap one API and carry no
annotation; the general AI-science workbenches (ScienceClaw, aipoch/open-science, wisp-science, all
600–4,000★) are not genome tools; `WGLab/InterVar` (213★) is ACMG classification, which ClawBio's
half already covered, and its last commit is 2021.
**Commercial, no source:** Promethease (now MyHeritage), Genomelink, SelfDecode, Codegen, Nebula.
**RM188's method does not reach them** — a report can be bought and read, but no pipeline can be run
and nothing can be pinned, so a survey of one would be a marketing comparison, which § *What it is
not* forbids. Promethease is reachable **through SNPedia** instead, which is why row 2 is the corpus
and not the product.

### The agent-skill class is closed, and it cost one read

[`BioTender-max/awesome-bio-agent-skills`](https://github.com/BioTender-max/awesome-bio-agent-skills)
(178★) is a directory of AI agent skills for biomedical work. Enumerating the entries that interpret a
**human personal genome** — as opposed to answering "what does the literature say about gene X" — gives
**21**, and they cluster under four collections: `clawbio/` (six: `pharmgx-reporter`,
`nutrigx-advisor`, `gwas-prs`, `genome-compare`, `claw-ancestry-pca`, `clinical-variant-reporter`),
`openclaw/`, `omicsclaw/` and `bioskills/`. The rest are ACMG classification, PRS, and PGx under
different names.

**Round 1 already surveyed the representative of this class.** ClawBio's six skills are *in* this
directory, and [`CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) read them end to end. Nothing in the
remaining fifteen is a different shape — they are the same fetch-and-render procedure over the same
public sources, and the directory itself is the evidence for that rather than an argument. **So the
agent-skill class is closed for round 2**, at the cost of one directory read rather than fifteen
surveys, and round 3 should not reopen it without a reason that is not "there are more of them now".

Two names in it are domains nothing here touches and neither survey raised: `chip-clonal-hematopoiesis-agent`
(somatic clonal haematopoiesis) and `prs-net-deep-learning-agent`. Neither is an annotation table, and
both are recorded only so the next reader knows they were seen.

**Security note, since the search surfaced it.** `Barrelsravennagrass984/Personal-Genome-Pipeline` is a
near-verbatim clone of `GeiserX/Personal-Genome-Pipeline` whose README is replaced with download bait
for a `.zip` committed inside the module tree. **Do not fetch or run it.** Recorded here because the
next person to run this search will find it in the same result set.

## RM237 — ClinGen dosage is gene-keyed, so a recurrent-CNV region has nowhere to be written

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** an author wants to write a recurrent-CNV region and cannot, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** · *before parking:* open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s ClawBio half** ·
**Owner** enricher (the lane) + format (the model) · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *dosage keyed on a region, not a gene*

`GeneMetricsRow` carries `haploinsufficiency` and `triplosensitivity`, keyed on a **gene symbol**, and
`enricher/clingen.py` fills them. ClinGen publishes four dosage lists — gene curation, **region
curation**, recurrent CNVs and ISCA regions — and `enricher/acmg.py`'s own probe note from 2026-08-03
records seeing all four on the FTP tree while reaching for one. The three unread ones are the half a
CNV classifier actually needs: ClawBio's `skills/cnv-acmg-classifier/data/curated_dosage_map.csv`
carries an `element_type` column precisely because two of its four demo rows are regions
(`22q11.2`, `chr22:18,900,000–21,500,000`, hi=3 ts=3), and its ClinGen/ACMG 2019 Section 1 scores off
them.

**A region is genuinely the subject, which is why this is not a widening of the existing table.** A
22q11.2 deletion is not a claim about any one gene in the interval; filing it under a gene symbol
would be a false attribution of the kind `@gene-map-is-another-sources-attribution` forbids. So the
shape is a **sibling sidecar** — `region_metrics.csv`, one row per `(chrom, start, end, name)` with
`haploinsufficiency`, `triplosensitivity` and ClinGen's curation id — rather than an `element_type`
discriminator on `gene_metrics.csv`. "One CSV = one concern" and `@sidecar-name-and-place` both push
apart here: a region row carries coordinates and a gene row carries a symbol, and a table holding both
would have half its key null on every row.

**Two things to settle before writing the pass**, and the second is the one a review will catch:

- **Terms.** ClinGen's dosage lists are believed unrestricted and that is *recalled, not probed*
  (`@no-named-licence`). Read the file and its SPDX id first.
- **Which `(source, layer)` row this claims.** `@write-the-sourcerow`'s second-surface clause says a
  second surface of an already-declared source may not claim the lane's existing row. Whether region
  curation is a second surface of `clingen` or the same lane is undecided, and it decides the
  `SourceRow` key.

**Related** RM188, `@write-the-sourcerow`, `@gene-map-is-another-sources-attribution`.

## RM240 — the ClawBio nutrition panel compiles, and the corpus should carry it

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** the corpus is asked for a nutrigenomics example, or RM188 unparks, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** · *before parking:* open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half; the translation is run, the landing is not** · **Owner** format (the corpus) ·
**Motivating case** [`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *The translation, run*

The survey's headline claim — a competitor's inlined panel is a module written in the wrong language —
was run rather than asserted. `skills/nutrigx/data/snp_panel.json` at `1fcecb7e` (28 SNPs) translated
field-for-field into a spec, `validate` green, `compile` producing 84 weight rows over 28 variants, 24
genes and 12 categories, and `compile → reverse → compile` reproducing `content_signature` exactly.
**Land it as `reference_examples/nutrigenomics_panel/`**, which is `@probe-becomes-example` and is the
only form in which the claim stays true as the code moves.

**What it broke on the way, and the README has to say all of it:**

- **`state` is required and `direction` is not.** 84 rows refused for omitting the *superseded*
  column while carrying the modern one. Already in the [1.0-cleanup tracker](ROADMAP.md#variantrowstate)
  with the right reason (P8 forbids demoting a required field inside a major, so the demotion and the
  deprecation land together at 1.0). What the run adds is that this is the **first** error a
  first-time author meets, before anything about their data.
- **Their 28 `ref_allele` cells carry no coordinate**, and the schema refuses a bare `ref` — correctly,
  since an unanchored reference allele cannot be checked against a reference genome. The honest
  translation drops `ref` and keeps `effect_allele`.

**What the landing still needs**, none of it optional because the corpus walkers assert it: a
`resolution.csv` so `validate --strict` and `compile --strict` pass
(`test_reference_example_compiles_under_strict`), a `sources.csv` whose terms are read rather than
recalled — their `data_license` is blank and the repo is MIT, which is a licence for the *code*
(`@a-hosts-terms-are-not-its-contents-terms`) — a `verification.json` closure
(`test_every_reference_example_is_closed_and_its_closure_still_describes_it`), a README, and a section
in [REFERENCE_EXAMPLES.md](REFERENCE_EXAMPLES.md). Two enricher passes are worth running first because
they are what makes it the worked answer rather than a copy: `check-identifiers` (their panel names
`BCMO1`, a retired HGNC symbol) and `literature` over the 28 PMIDs.

**One observation for the README, not a repair.** Their panel weights `rs429358` and `rs7412` as two
independent additive rows in two different nutrient domains. Those two variants are the APOE ε pair,
which `reference_examples/apoe_epsilon/` models as a haplotype because the isoform is the joint state.
That is a claim about their curation, and it belongs in the README as a sentence.

**Related** RM188, RM92 (see RM241 — the `weighting` block this example is forced to write).

## RM164 — `heteroplasmy.csv` is a shipped table kind with no source behind it

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** its own gate below is met: a source of heteroplasmy calls, PacBio's pipeline output included if it carries one, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** · *before parking:* open — **PARKED to 0.8, decided 2026-09-01**, moved into this file
**2026-09-11** · **Owner** enricher · **Motivating case** the 2026-09-01 source-adoption round

**Decided 2026-09-01 with the maintainer: parks, on the measured negative below.** The candidate field
anyone has named is MITOMAP and the population callsets it re-hosts, and none of them publishes the
axis the kind binds; that is a fact about what exists, not about how hard anyone looked, which is what
makes the deferral honest rather than indefinite. It stays **open and visible** rather than closed,
because a kind with a one-module corpus is exactly what `@probe-uniform-corpus` says to keep in view —
and if a source that bands heteroplasmy by tissue appears, this entry is where it is checked against.
**Reopen it with a source, never with an argument.** The spin-off it noticed is now
[RM171](ROADMAP_HISTORY.md#rm171--mitomaps-curated-mtdna-tables-adopted-as-the-increment-they-carry-over-clinvar).

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

## RM122 — the measure lookup is specified and nothing anywhere implements it

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** its own gate below is met: a caller of the measure lookup (ask just-dna-lite first, as the gate audit says), when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** · *before parking:* **parked on demand, moved here 2026-08-21** — additive and
minor-legal whenever it is wanted; what it waits on is a caller, not a decision · **Owner** format ·
**Motivating case** S58 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

**The specification half shipped; this is the part that was not asked for and might still be right.**
S58 reported that the four binning kinds annotate nothing downstream and asked for either a normative
paragraph or an admission that the family is specified ahead of its consumers. Both are now in
[SCHEMAS.md § The measure lookup a conforming consumer implements](SCHEMAS.md#the-measure-lookup-a-conforming-consumer-implements--the-second-normative-obligation-06-s58),
and that closes the item they filed. What is filed here is the next question, which they did not ask:
whether the rule should also exist as a **public function** so that the first two consumers to
implement it cannot disagree.

**The argument for.** It is the shape S51/RM115 settled one layer down — a rule kept as prose is a rule
every reader re-derives, and the two derivations differ on exactly the cases that matter. Here those
cases are enumerable and sharp: the continuous shared endpoint, the float32 comparison, `unresolved`
versus no-match, and pleiotropy returning several rows rather than one. A consumer will get at least
one of the four wrong, and the failure is silent — a wrong bin renders as a confident phenotype.
`alleles.split_genotype` is the precedent: the *reader* half of RM81 shipped as one public leaf every
tier calls, while the retype waits for a major. It costs the format tier nothing — pure arithmetic over
loaded rows, pydantic-only, no dependency moves.

**The argument against, and it is why this is open rather than done.** There is no consumer to check the
shape against, which is the same reason `measure_step` is not a column: a signature fixed against a
hypothesis fixes the wrong thing, and this one has real shape questions. Does it take rows or a table?
Does it return one row, or one per `trait_efo_id` (the honest answer, and the inconvenient one)? Does it
answer `None` for no-match, or a three-state result distinguishing *no match* from *unresolved selected*
— which is what the house algebra would demand and what a `None` return would collapse. Getting that
wrong ships a leaf whose first real user has to work around it, and P3 keeps it working forever.

**What would settle it:** one consumer implementing the lookup against the paragraph. Their questions
are the signature. Until then the paragraph is the contract and this stays filed — the same
wait-for-the-demand rule that governs `measure_step`, applied to a function instead of a column.

**Decided 2026-08-21: wait for demand, and the wait is the answer rather than a way of postponing
one.** The four shape questions are the reason — does the lookup take rows or a table, does it return
one row or one per `trait_efo_id` (the honest answer, and the inconvenient one), does it answer `None`
for no-match or a three-state result distinguishing *no match* from *unresolved selected*. There is
nobody to check any of those against, and P3 keeps a wrong leaf working forever. This is the same
wait-for-the-demand rule that keeps `measure_step` out of the schema, applied to a function.

**It moved out of the active roadmap because "undecided release" was the wrong bucket for it.** Nothing
about this is undecided; it is parked, which is what this file is for, and it sat under a heading that
made it read like an unmade call. **The settling event is specific**: one consumer implementing the
lookup against the paragraph in [SCHEMAS.md](SCHEMAS.md#the-measure-lookup-a-conforming-consumer-implements--the-second-normative-obligation-06-s58).
Their questions are the signature — file it back in the active roadmap when they arrive, not before.

## RM23 — Computational predictor scores as a table

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** its own gate below is met: the acquisition measurement and the per-transcript decision, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** · *before parking:* deferred — **considered for 0.6 on 2026-08-13 and held**, on the two
blockers unchanged · **Owner** format (schema + compiler) + enricher · **Motivating case** pathogenicity
triage; splice-impact panels

`predictions.csv` — the groundwork every predictor source needs, built **once**: one row per
`(variant, predictor, score_kind)` with `score`, `dataset`, `source`, and an optional `transcript`.
**Long-form, not wide, is the load-bearing choice** — SpliceAI is four deltas plus positions, CADD is
one number, AlphaMissense is one plus a class, so wide columns would make every new predictor a schema
bump while long form makes it *data*. A predictor score is the same class of object as an allele
frequency or a LOEUF (a per-variant number from a named dataset, no measurement), so the 0.5 sidecar
precedent covers it.

**Grain settled by RM236 (0.8, shipped 2026-11-04 on `0.8`).** `consequences.csv` is keyed
`(variant_key, transcript)` with Open Targets' transcript set (one canonical transcript per nearby gene);
`predictions.csv`'s optional `transcript` takes the same grain when this is built, so the two never give
two answers to "which transcript" (RM236's recommendation, one question asked once).

**Why it is still deferred, after the 0.6 review.** Neither blocker is code, and neither has moved:

- **Grain.** SpliceAI scores are per-transcript, and there is no settled way to name the four splice
  deltas without inventing a predictor-specific column set — which is the exact thing long form exists
  to avoid. Whether a per-transcript score is one row each or a picked representative is undecided.
- **Acquisition.** Precomputed splice scores need the *masked vs raw* file sizes measured and the Broad
  lookup API's terms read. This is the same measure-first question that correctly parked the frequency
  snapshot, and skipping it is how a shape gets fixed against a guess.

Unlike the two derived tables 0.6 does build (RM24, RM25), this one is a **full-cost authored table**
under the 2026-08-13 charter amendment, so the bar is higher rather than lower.

**Licensing is solved, not blocking — do not re-raise it as the reason.** SpliceAI/Pangolin, dbNSFP,
AlphaMissense, REVEL, CADD and PrimateAI are all non-commercial or academic-only, and `licensing.csv`
plus the compile gate already confine that to the modules that use them, while phyloP/phastCons/GERP
(UCSC, free, queryable per-range rather than a bulk download) keep a module sellable.

**What would unpark it:** the acquisition measurement done, and a decision on per-transcript grain.
That is a research task, not a schema task, and it commits nothing.

## RM16 — Authored PRS weights (a scoring file, not a manifest)

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** the shape question below is answered: how the weights combine, what reference distribution a score is stated against, and whether a percentile travels with it. That needs nothing built; the PGS Catalog's scoring files and the transcribed table below are enough to try it. The old gate, "a real consumer", was circular (the gate audit), and this restates it. Or when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium-large (on demand) · **Status** open — **a minor, parked** · *before parking:* deferred — **considered for 0.6 on 2026-08-13 and
held; parked on *shape* rather than on demand since 2026-09-13, and its unpark condition needs
restating** · **Owner** format (schema + compiler) · **Motivating case** authored-weight PRS modules

0.4 shipped `pgs.csv` as a *manifest of PGS Catalog IDs* with the ancestry-validity fields — not
authored per-variant weights. `just-prs` resolves a `PGSxxxxxx` id to a harmonized scoring file and
scores each id itself, so inlined weights would be **dead data**; and a PRS is a
Z/percentile-in-reference, a shape the format does not bin.

What is deferred is a distinct, digest-bearing `effect_allele` + `effect_weight` scoring table, for the
case where a module must ship weights the PGS Catalog does not host (a score published only in a
paper's supplementary table).

**Why it is still deferred.** It is **not derivable** — nobody can fetch weights that exist only in an
appendix — so it is a **full-cost authored table**. And the one thing that would validate its shape, a
real consumer combining authored weights into a score, does not exist. A score's shape (how weights
combine, what the reference distribution is, whether a percentile travels with it) is exactly what a
first real case would dictate, so fixing it now spends a one-way door on a guess.

**What would unpark it:** a real consumer. See [PROPOSAL_0_5.md](proposals/PROPOSAL_0_5.md) D1.

**This entry and [RM28](#rm28--meta-conclusions-the-predicate-half) are one axis at two operators
(maintainer, 2026-09-13), and they should be decided together rather than merged.** Both ask the same
question — *how does a conclusion get derived from more than one variant row, and where does the
combining rule live?* — and the format already answers it once:

| Combiner | Where the rule lives | Status |
|---|---|---|
| **Enumerative** — write out each combination | in the table: a `diplotypes.csv` row *is* the combination | **shipped**, `reference_examples/apoe_epsilon` |
| **Boolean** — a predicate over genotypes | nowhere: the table would hold terms, something else the operator | **RM28**, parked on a corpus |
| **Weighted sum** — terms plus coefficients | nowhere: the table would hold weights, the consumer the arithmetic | **this entry**, parked on shape |

Three facts follow from the table and none of them from either entry alone. **The enumerative answer
is why both are parked and neither is urgent** — it covers the small-arity cases, which is most of
them, so any argument for a new combiner has to beat it rather than merely want one. **Both
non-shipped rows split the same way against the data-agnostic goal**: the module carries terms, the
consumer does the combining, so neither is a licence to put an evaluator in the compiler. And **one
corpus supplies evidence for both** — SNPedia has genosets *and* per-genotype magnitudes, which is why
one survey touched both entries on one day.

**They stay separate items.** The outputs differ in kind — RM28's is a categorical conclusion, this
one's is a number that means nothing without a reference distribution — and RM28 was already halved
once on 2026-08-13 for being too broad, so merging would make the smaller hostage to the larger. What
they share is a **precondition**, not a design: whoever opens either should read both, and the *where
does the combining rule live* decision should be taken once rather than twice.

**The hypothesised case now has an instance in the wild (2026-09-13), and it does not unpark this.**
From [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
round-2 skim: [`dianguan0105/Custom-Personal-Genome-Interpretation`](https://github.com/dianguan0105/Custom-Personal-Genome-Interpretation)
(`15fe28a`) ships `metaprs_weights.tsv` — **540 variants transcribed by hand out of a European Heart
Journal 2022 supplementary Table S3**, with `rsid`, `effect_allele`, `other_allele`, `weight`, `maf`
and `traits`. That is this entry's motivating sentence — *"a score published only in a paper's
supplementary table"* — with a real file behind it instead of a hypothesis, and the column set they
arrived at independently is close to the one deferred here.

**The first reading of that was wrong, and the maintainer corrected it the same day.** It was written
here as *the wrong half of the evidence* — the unpark condition is a real consumer, a competitor
transcribing a table is a producer, so nothing moves. **That dichotomy does not hold, and the entry's
own gate is what has to give.**

**An author with a corpus in hand is demand, and for a format it is the demand that matters.** People
reach for familiar shapes: somebody who already has a scoring table, or a set of genosets, adopts a
format when the format can hold what they already have, and declines it when it cannot. That makes
*"can I bring this in"* a consumer question in the sense that decides whether a format gets used at
all — a narrower reading, where a consumer is a downstream tool that reads authored weights and
scores them, gates this entry on the one party who cannot appear until after the table exists.
**Written as it stands, the unpark condition cannot be met by anything except a tool built against a
table this entry is refusing to build.** That is a gate on its own output, and it should be restated
when this entry is next opened for a decision — not silently, and not here, since restating a parking
condition is a change to the item rather than a note on it.

**What survives the correction, and it is the half that was always load-bearing.** The demand
question is answered — somebody did the typing, and SNPedia's magnitude-and-genoset corpus is the same
argument at a hundred thousand rows. The **shape** question is not: how the weights combine, what
reference distribution the score is stated against, and whether a percentile travels with it are still
unanswered, and a transcribed table shows the columns without showing the semantics. The one-way door
is the shape, never the demand, so what this instance does is **move the entry from parked-on-demand to
parked-on-shape** — a smaller and much more answerable place to be parked.

**Register cross-reference (2026-09-27).** [RM302](ROADMAP_0_9.md#rm302--one-conclusion-serves-every-place-a-report-shows-it-a-table-cell-a-details-card-and-an-explanatory-mode-want-different-wordings)
gives `conclusion` optional lay and concise wordings, two columns by default. If this item lands a
separate meta-conclusion table, the maintainer's steer is that the registers may live there instead,
so the two are decided together.

## RM68 — a drafting provider on a non-GRCh38 module: refuse, or strip to the rsID

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** its own gate below is met: an author with a non-GRCh38 module says which outcome they wanted, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium (high before the warning shipped) · **Status** open — **a minor, parked** · *before parking:* the warning shipped in 0.6
(`enrich.source_build_mismatch`); **what the providers should do instead is deferred here** · **Owner**
enricher (the three drafting providers) · **Found by** dogfooding on 2026-08-13,
`reference_examples/cyp2c9_warfarin_grch37/`

### What was observed

`draft`, `draft-panel` and `draft-clinpgx` all take a `spec_dir`, and until the 0.6 dogfooding round
none of them read `genome_build`. `enrich.spec_genome_build` — written one release earlier for the bug
where the guard existed and the value never arrived — had **exactly one caller**. Every source these
providers read serves GRCh38: CPIC's `allele_definitions`, the ClinVar snapshot, the ClinPGx
annotations. So drafting CYP2C9 into a `genome_build: GRCh37` module writes `10,94942290` for
`rs1799853`, whose GRCh37 position is `96702047` — a different base 1.76 Mb away — and nothing anywhere
said a word.

Nothing downstream catches it. A coordinate is legal on either assembly; it is simply a different place.
What the online diagnosis reaches is now measured rather than asserted: of the module's two GRCh37 rows
declared as GRCh38, `grch37.diagnose_wrong_build` caught one and the other minted
`ga4gh:VA.pgprki8YgzfOSV9Dpe1ccPX4uNdlyAvB` and recorded `resolved`, because GRCh38 happens to carry the
authored `ref` at that position too. That is the documented ~3-in-4 sensitivity, so *"the compiler
catches wrong-build coordinates"* is not a reading anyone should take. Two of the three providers write
coordinates and can do this; `draft-clinpgx` writes none.

It hid because `test_pgx_draft.py`'s fixture declares `GRCh38`, and it is the only drafting test that
mentions a build at all.

**What shipped in the same session.** `enrich.source_build_mismatch`: each drafting command asks before
it writes and warns naming both builds, what a drafted coordinate will actually mean, and the two
remedies. The provider still writes the row, which is the enricher's standing shape for a disagreement
— report, never repair.

### The question

Report-and-still-write is the right *default*. What is undecided is whether a provider meeting a
non-GRCh38 module should go further: **refuse**, or **strip to the rsID** — writing the identity the
source does state without stating an assembly, which `derive_variant_key` prefers anyway.

**Refuse — wrong three ways.** It makes a GRCh37 module undraftable, so the author hand-authors instead,
and hand-authoring against a printed contract is where this format's most expensive documented failure
came from (the 0-vs-1-based `start` description shifted four whole modules by one base and passed every
offline gate, `--strict` included). It refuses a provider that cannot do the harm: `draft-clinpgx` writes
no coordinate, so a refusal keyed on the module's build stops a command whose entire output is
build-free. And it is the wrong granularity by the repo's own rule — *scaffolding refuses per file,
drafting refuses per row* — while a build mismatch is a property of the module, so a build-keyed refusal
is per **run**, which is the granularity that self-defuses into "this module cannot be drafted at all".

**Strip to the rsID — wrong, and worst on the rows that need it most.** It is tempting because the row's
identity does not move (`derive_variant_key` returns the rsID first) and an rsID names a variant without
naming an assembly. But CPIC's `sequence_location` publishes defining variants with a position and *no*
rsID — 18 in CYP2C9, 14 in TPMT, 4 in NUDT15 — and `HaplotypeRow` requires an rsID **or** chrom+start.
Stripping the coordinate there is not "write less", it is "drop the row", and it drops exactly the rows
the 0.5.1 `gene.chr` repair recovered after a year of being skipped. It also produces a row
indistinguishable from one the source had no coordinate for, so the author cannot tell a stripped row
from a bare one. Any *partial* strip is barred outright: a drafting provider fills identity whole or not
at all, and a lone `alts` on a position-only row makes `derive_variant_key` mint a `ga4gh:VA.…` instead
of `chrom:start:ref`, silently changing which variant the row is.

**Lift the coordinate over — refused, and RM48 already argues it.** RM48 is deliberately one-way and
reporting-only: a GRCh37 coordinate recovers an rs-number, and the rs-number is *reported*, never
filled, because filling it would make resolution verify a value against the service that produced it.
A liftover inside a drafting provider is that move with an extra assembly on it, and `chrom`/`start`
are both in `hints.REDUNDANCY_BEARING` for the same reason.

**A `--build` flag on the drafting commands — wrong twice.** A flag saying "write GRCh37" asks the
provider to convert, which is the liftover above. A flag saying "yes, I know" is a warning suppressor,
and the tier's standing rule is that `--offline` is the switch and a pass adds no second CLI flag.

**What would unblock it.** Either a real author with a non-GRCh38 module saying which of the two
outcomes they wanted, or **RM15**, which dissolves the premise: once identity is build-agnostic a
provider can write the coordinate under the build it came from, and there is nothing left to refuse or
strip. A behaviour fixed before RM15 lands is one RM15 would have to undo, which is the strongest single
argument for leaving this at a warning.

## RM266 — the phase-confusable diplotype-pair set is computed at compile and dropped: it reaches the artifact only as a capped warning string

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** S116's reporter or another consumer asks for the phase-confusable pairs as data rather than as a warning, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** · **Owner** compiler
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

## RM281 — the PGx lane reads one of ClinPGx's archives, and `clinicalVariants.zip` bears on a shipped table kind

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** an author drafting `pharm_variants.csv` needs a row `clinicalVariants.zip` carries and `summaryAnnotations.zip` does not, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** (a source adoption) · **Owner**
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

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** someone runs the survey its own gate below describes, which needs nothing built, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** · parked on a survey chosen for
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

## RM284 — a skip is a fact about the run, and `verification.json` has no run-level place to keep one

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** a reader reports needing to know, from `verification.json` alone, that a run could not reach a source, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** · **Owner** format (the
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

## RM287 — ClinGen's dosage pass is a live download with no snapshot lane, so an offline deployment never runs it

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** an offline deployment reports a dosage pass that never ran, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** low · **Status** open — **a minor, parked** (a new cache lane) · **Owner**
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

## RM296 — a PRS has no condition → conclusion table, so `pgs.csv` only restates what the PGS Catalog already publishes

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** an author writes a PRS module that needs a score → conclusion band, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** (a new optional binning kind) ·
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

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** the ClinPGx currency check withholds on a real mixed module whose operator needed the answer (RM297's warning is the interim), when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** (a new optional authored
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

## RM306 — no exon structure anywhere in the tier, and AlphaGenome's gene attribution wants one

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the 2026-11-03 sweep that moved everything outside 0.8's scope to 0.9. **Unparks when** a real module's AlphaGenome rows need an exon-level gene attribution, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Severity** medium · **Status** open — **a minor, parked** (a second table in the MANE
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

## RM238 — a per-tissue eQTL has no row, and `expression_effects.csv` is the wrong table to widen

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the pm's placement of 2026-11-04 (below). **Unparks when** its own gate below is met: someone who needs a per-tissue eQTL answer, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**0.9, decided 2026-11-04 by the pm seat, on the lead's build plan (PROPOSAL_0_8_PT2 §4 question 2).** The coloc input v2's effector confidence needs comes from Open Targets' `colocalisation` dataset, in RM333's lane under the same CC0 marking. So this per-tissue GTEx table goes back to waiting on a consumer: one lane and one licence instead of three sources, the maintainer's reduction rule.


**Severity** low · **Status** open — **a minor, parked** · *before parking:* open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half; PARKED on a consumer, deliberately** · **Owner** enricher · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *nine databases, and the two axes that come
back with no home*

**For longevitymap v2 (2026-11-03):** the cis-QTL colocalisation behind effector confidence E1/E2. See [the group](history/ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

`clawbio.py run gwas --demo` on rs3798220 returns five cis-eQTLs **by named tissue** from GTEx and the
EBI eQTL Catalogue — `LPA` in Liver at β −0.82, in Adipose at −0.45, `SLC22A3` in Liver at +0.31.
Nothing here holds that. `expression_effects.csv` exists and is the wrong place: it is
AlphaGenome-shaped, one row per `(variant, gene)` **aggregating 371 tissue tracks** into
`tracks_agreeing`/`tracks_total`, and [`expression.py`](../schema/src/just_dna_format/expression.py)
argues at length that one row per track "is lossless and unreadable". A GTEx row is not a track — it
is a measured cis-eQTL in one named tissue with its own β and p, ~50 tissues rather than 371, and
**the tissue is the fact** rather than something to consensus over. Different grain, different source,
different terms. So: `eqtl_effects.csv`, one row per `(variant, gene, tissue, dataset)`, tissue as an
ontology term where the source gives one.

**This is filed open and parked, and the parking reason is a rule rather than a shortage of time.**
[USE_CASES § 7.2](USE_CASES.md#7-regulatory-effect--which-gene-a-non-coding-variant-moves-and-which-way-07)
closes with *"reopen this with a consumer, never with an argument"*, and a competitor rendering the
table is an argument. **Reopen it with somebody who needs the answer.** When that happens, the first
step is the acquisition measurement that correctly parked the frequency snapshot — what the GTEx and
eQTL Catalogue bulk artifacts weigh, and what their terms say (`@probe-the-real-file`).

**Related** RM188, RM194/RM200 (the AlphaGenome table this must not be folded into), USE_CASES § 7.2.

## RM378 — errors carry no code, so a consumer grading a spec tells one refusal from another by its wording

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the pm's placement of 2026-11-05 (below). **Unparks when** a consumer needs to tell apart refusals that RM377's two phrases do not cover, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**0.9, placed 2026-11-05 by the pm.** 0.8 is the work already built, the fixes already chosen and longevitymap v2, and "the rest goes to 0.9" (the maintainer, 2026-11-03). RM378 is new, its code vocabulary is permanent within the major once shipped, and it has two open design questions, so it is not added to a release at its cut. RM377 already gives the reporter the two phrases it needs today. The maintainer can still take it into 0.8.

**Severity** low · **Status** open — **a minor, parked** (placed by the pm on 2026-11-05; triage proposed 0.8) ·
**Owner** compiler (the result types, every `errors` append site) + format (the vocabulary) · **Motivating
case** S129 in CONSUMER_SUGGESTIONS_HISTORY.md (just-dna-registry's liaison seat, 2026-11-04) · *related*
RM377, RM131, RM218, RM359

**The gap.** RM131 gave the warnings channel a code per finding and `warnings_summary`; `errors` stayed
`list[str]` on `ValidationResult`, `CompilationResult` and `ClosureResult`. A consumer that grades a spec
must read an error's words to know which refusal it is. RM377 published the two phrases the reporter needs
today; this item is the general answer, the reporter's candidate (a).

**What it would be.** A code from a closed vocabulary on each error and an `errors_summary` beside
`warnings_summary`, by RM131's shape: derived in the same `mode="before"` validator, summing to
`len(errors)` or empty, never partial. A mode-laddered finding raised to an error under `strict` already
has a warning code, which is dropped on the error path today, so part of this is keeping a code that exists.

**Open questions, for the interview.**

1. **Pydantic's own errors.** A rejected row's message comes from pydantic and has no closed vocabulary.
   RM131 refuses both a partial summary and a catch-all key. So either every such error gets one code that
   names the finding (*a row the model rejected*), or the summary is defined over the coded errors only and
   says so. The first keeps RM131's rule; the second breaks it.
2. **The vocabulary's cost.** Codes are permanent within the major (P3, P5, P6), so the first set shipped is
   the one consumers key on. RM131 measured that the audit of emission sites is the cost; the container is
   near free (P9: a result-model field, nothing authored).
3. **The reporter's candidate (b)**, a field naming the strict-only module-level refusals, is narrower and
   cheaper. It is not taken here: it builds one consumer's split (module-level against per-row) into the
   model, a classification axis under P5, which the reporter named as the reason it might be wrong. With
   codes, each consumer draws its own line.

**Residuals** none yet.

## RM28 — Meta-conclusions (the predicate half)

**Parked, the pm (2026-11-05)**, out of `ROADMAP_0_9.md`, under the maintainer's rule that a minor takes the zones they name and nothing by default ("'Auto-next minor' was a policy when we didn't have a dedicated decision maker for this"). It reached 0.9 by the move of the items parked on a corpus. **Unparks when** its own gate below is met: the corpus count, when a scope the maintainer highlights touches it, or when the roadmap is empty.

**Moved here from `ROADMAP_0_8.md` at the 0.8.0 cut (2026-11-05)**, unchanged but for the file it sits in: its combination half (the meta-table) shipped in 0.8 ([ROADMAP_HISTORY § RM28](ROADMAP_HISTORY.md#rm28--the-combination-half-the-meta-table)), and the decisions it was built to are in [history/ROADMAP_0_8.md](history/ROADMAP_0_8.md#rm28--meta-conclusions-the-combination-halfs-decisions-shipped-in-08). What waits is the predicate half's remainder (open-world negation, OR, *trans* phase), parked on the corpus below.

**Severity** medium (after the corpus) · **Status** open — **a minor, parked** · *before parking:* parked on a corpus — **and halved on 2026-08-13**:
the injected-cofactor half closed, the predicate half stays here · **Owner** format (schema + compiler)
· **Motivating case** combination annotations; disclosure policy

**For longevitymap v2 (2026-11-03):** KL-VS buffering in APOE4 carriers joins two loci on two chromosomes, so no haplotype holds it; added as a corpus entry there. See [the group](history/ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**Read this entry knowing how much of the original item has already dissolved.** Probing in 0.5 removed
most of it, and the 0.6 review removed the rest of the cofactor axis. What is left is genuinely small
and genuinely unsolved.

**The corpus this was parked waiting for has its first real entry (2026-09-02, [RM174](history/ROADMAP_HISTORY_0_6.md#rm174--a-claim-about-two-variants-in-trans-is-written-as-two-single-variant-rows-because-no-brick-holds-the-real-subject)).**
Not an argument — an adopted source whose grammar was counted. CIViC publishes molecular profiles as
boolean expressions over variants: of 1,964 profiles, **209 are multi-variant** — `AND` 141, `OR` 72,
`NOT` 1 — and they nest (`BRAF Amplification AND ( BRAF V600E OR BRAF V600K )`). Both halves of this
entry's surviving case appear there, with instances:

* **Economy, and it is this entry's own phrase.** Evidence item 8721 is a claim about
  `VHL S183L AND VHL D126N` whose description reads *"heterozygous compound mutation"* — two variants
  **in trans**, observed, cited. `HaplotypeRow` cannot hold it: a haplotype is same-strand co-location,
  so drafting it there asserts *cis* where the source says *trans*, silently, because no column carries
  phase for anything to contradict.
* **Open-world negation.** `MET Amplification AND NOT KRAS Mutation` quantifies over a set no module
  can close, on a class term rather than an enumerable allele.

The 72 disjunctions are the half that is **already expressible** — rows are a disjunction — which is
where this entry drew the line and it holds. **This is evidence for the corpus, not a reason to
unpark**: one source, one observed trans instance, one negation. RM174 carries the measurement; the
decision stays here.

**Second corpus entry, 2026-09-13 — and it is a routine clinical guideline rather than an oncology
molecular profile.** From [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half ([`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *pharmgx-reporter*). Their
pharmacogenomic report renders exactly one AVOID across 59 drugs, and it is **warfarin**, keyed
`"genes": ["CYP2C9", "VKORC1"]`. Our own `reference_examples/cyp2c9_warfarin_grch37/` carries the
CYP2C9 diplotype phenotypes in `diplotypes.csv` and the VKORC1 per-genotype claims in
`pharm_variants.csv`, **side by side, with nothing keying the pair** — which is this entry's surviving
"pairing across *subjects*" clause with a shipped module standing on it.

Three things make it sharper than the CIViC entry rather than a repeat of it:

* **It is the *drafter's* recorded gap, not an inference.** `pgx_draft`'s own comment says it:
  *"the guideline exists, it is a dosing algorithm over several genes rather than a per-phenotype
  recommendation, so nothing lands here and the author was told CPIC has nothing."* What shipped for it
  was a better **warning**, deliberately, not a table.
* **The competitor has no declarative form either.** ClawBio's answer is `"special": "warfarin"` — a
  hardcoded branch calling `get_warfarin_rec(profiles)`, for one drug out of 59. That is evidence the
  shape is genuinely hard, not evidence that everyone else solved it.
* **It is CPIC, so the population is countable.** The measurement this entry still wants, and the one
  cheap enough to do before any design: **how many CPIC guidelines are keyed on a gene *pair* rather
  than a single gene phenotype**, counted off the CPIC snapshot already provisioned. If the answer is
  three, this parks again with a sharper reason; if it is thirty, the economy argument changes.

**Third corpus entry, 2026-09-13 — and this one is a general-purpose grammar rather than a domain's
by-product.** From the same item's [round-2 roster](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics):
SNPedia publishes **genosets**, boolean expressions over genotypes, and
[`zhaofengli/snappy`](https://github.com/zhaofengli/snappy) (`2d5255f`) has them extracted from a
MediaWiki dump into `data/genosets.json` beside 106,603 SNP entries. The grammar is
`and(rs4988235(C;C), rs182549(C;C))`, it nests, and a genoset may reference another genoset — the
haplogroup trees are built that way.

What makes it the sharpest of the three is that CIViC's profiles and ClawBio's warfarin branch each
fell out of one domain solving one problem, where **this grammar was written for consumer genetics in
general** and has been in use for over a decade. It is also the first entry where the *condition* side
and the *conclusion* side are both published, at scale, by one source.

**This entry and [RM16](#rm16--authored-prs-weights-a-scoring-file-not-a-manifest) are one axis at two
operators** — boolean here, weighted-sum there, with the enumerative combiner already shipped in
`diplotypes.csv` and covering the small-arity cases both would serve. RM16 carries the table setting
that out; read it before opening this one, and take the *where does the combining rule live* decision
once rather than twice. They stay separate items, because a categorical conclusion and a number
needing a reference distribution are different outputs.

**One argument from it does reach beyond the count, and it is [RM16](#rm16--authored-prs-weights-a-scoring-file-not-a-manifest)'s
rather than this entry's** (maintainer, 2026-09-13): genosets are a *familiar shape*, in use for over a
decade, and an author's ability to bring one across is an adoption signal in its own right. It bears
on this entry only as a reason the count below is worth running rather than as a reason to unpark —
this item is parked on a corpus, and a corpus is measured, not argued.

**It changes no decision yet, and the reason is the same one that has held twice.** The measurement
this entry wants from it is cheap and has not been done: **how many genosets are there, what is the
operator distribution, and how deep does the nesting go** — counted off `genosets.json`, which is a
committed file needing no network. A corpus of forty flat conjunctions argues differently from four
thousand nested ones. The licence is **not** the obstacle a first reading here made it: CC BY-NC-SA
3.0 US is established and adoptable as an unsellable share-alike module
([USE_CASES § 2e](USE_CASES.md#2e-republishing-a-licence-encumbered-third-party-corpus-as-modules-2026-09-13)).
What still has to be beaten is `reference_examples/apoe_epsilon`, which answers the two-variant case
with no predicate at all.


**Fourth corpus entry, 2026-09-13 — and it is the first where enumeration *succeeds* and the schema
around it complains anyway.** Raised by the maintainer from their own genotype: **Kulminski's
subdivision of APOE ε4 by linked TOMM40/APOC1 markers**, where a carrier is not simply *ε4* but
`1-0-0`, `1-1-0`, `1-0-1`, `1-1-1` — a binary vector over the ε4 call plus the linked sites, each
pattern carrying a different reported risk.

**This one is expressible today, and that is the finding rather than a reason to close.** Three
markers is eight patterns and at most thirty-six pairs, which is `haplotypes.csv` (one row per pattern
× defining marker) plus `diplotypes.csv` (pair → phenotype) — the shape
`reference_examples/apoe_epsilon` already ships for ε2/ε3/ε4 across rs429358 and rs7412, with one more
marker. The enumerative combiner is not beaten here, so **this entry argues for no predicate at all**.

**What it does show is the shape being outgrown at a different seam — the *subject*, not the
combiner** (the maintainer's reading, and it is the right one). Expressing it fires two shipped
warnings, and neither is a bug:

- **`composite_gene_cell`.** The haplotype spans TOMM40, APOE and APOC1; `DiplotypeRow.gene` is
  **required and single-valued** (`HaplotypeRow.gene` is optional, so only the diplotype half forces
  the choice). Labelling the locus `TOMM40-APOE-APOC1` publishes a gene name no registry index will
  match, beside its parts — which is exactly what the warning says. So the author picks between **one
  findable symbol and an honest locus label**, and there is no third option. `apoe_epsilon` never met
  this because ε alleles sit in one gene.
- **`diplotype_phase_ambiguous`**, conditionally. `HaplotypeRow` *is* same-strand co-location, so this
  translation is only honest if Kulminski's patterns are **phased haplotypes**. If they are unphased
  multi-locus genotype vectors, writing them as haplotypes asserts *cis* the source never claimed —
  RM174's trap exactly — and the pairs that collapse to one unphased genotype with different
  conclusions are what this warning already catches, telling a consumer with unphased calls to
  withhold.

**So the honest verdict is: yes, with caveats, and the caveats are the entry.** The format holds the
claim; what it cannot do is hold it *cleanly*. A use case that compiles only by choosing between
findability and honesty, and only under a phase assumption, has grown past the gene-keyed subject the
PGx tables were cut for — and that pressure lands on `DiplotypeRow`'s key rather than on any predicate
language. **Read against the other three entries, this is the one that argues RM28 may be the wrong
item for its own class of case**: CIViC's contribution was that enumeration *cannot* reach trans and
open-world negation, ClawBio's was that nobody has a declarative form for a multi-gene dosing
algorithm, SNPedia's was a general grammar at scale — and this one enumerates fine and still does not
fit. A locus-keyed subject would settle it and a predicate would not.

**The count this entry asked for, 2026-09-20 — and it is between the two numbers the question
named.** Measured off the provisioned CPIC snapshot (`cpic_snapshot_b0ffd4c6f010`, built 2026-09-02)
while answering S102, whose reporter had counted the same table from the other side: of **103 drugs**
with a recommendation row, **18 are keyed only on a gene pair** and none is keyed both ways — every
drug is single-gene or pair-keyed, never a mix — and `gene_count` never exceeds 2. By rows it is
**2,656 of 3,411** pair-keyed, which is what made the drafter's *"the snapshot has no row for it"*
false for a drug with 35 of them. The 18 drugs fall into **six pairs**:

| pair | drugs |
|---|---|
| CACNA1S + RYR1 | desflurane, enflurane, halothane, isoflurane, methoxyflurane, sevoflurane, succinylcholine |
| CYP2C19 + CYP2D6 | amitriptyline, clomipramine, doxepin, imipramine, trimipramine |
| NUDT15 + TPMT | azathioprine, mercaptopurine, thioguanine |
| ABCG2 + SLCO1B1 | rosuvastatin |
| CYP2B6 + CYP2C19 | sertraline |
| CYP2C9 + SLCO1B1 | fluvastatin |

Warfarin is **not** among them: it has no recommendation row at any arity, because its guideline is a
dosing algorithm rather than a recommendation table, so the ClawBio entry's case is the one CPIC drug
this count cannot reach. Read against the question — *three parks again, thirty changes the economy
argument* — eighteen drugs across six pairs is the middle: more than a warfarin-shaped exception,
less than a pattern the enumerative combiner is failing at scale, and every one of them is arity 2.
The drafter now names the partner gene instead of claiming absence (RM249), which is a message and
not a table; whether six pairs earn a pair-keyed subject stays the maintainer's decision, and this
entry stays parked on it. The reporter's reading — ClawBio keys each of these on a single gene and
never mentions the partner, *a lossy answer, not a model to copy* — is the right one and is recorded
beside the survey's plan item 1, which this measurement answers.

**Unmeasured, and flagged as such.** This is a *reported* case: the paper has not been read here, so
the marker count, the exact patterns, and above all **whether Kulminski phases them** are unverified.
That last one decides which of the two warnings above applies, and it is the first thing to establish
if anyone builds it. Separately, `just-module-creator`'s `assets/longevity_2026` was checked and does
**not** attempt this — it takes the opposite reading, collapsing the cluster to rs429358 as the shared
causal signal on colocalization evidence, with TOMM40/APOC1 named only in prose and no
`haplotypes.csv` at all.

Still **parked**, on the same rule: the corpus grows, the decision does not move until the count is in.

**2026-09-20 — the count is in, and it does not support the parking reason.** Measured directly off
the provisioned CPIC snapshot (`data/interim/cpic/`, `dataset: cpic_snapshot_3d2123598711`, built
2026-08-07, `recommendations.parquet` 3,411 rows), prompted by a peer session drafting ClawBio's PGx
corpus that hit it from the other side:

* **2,656 of 3,411 recommendation rows (78%) are `gene_count = 2`.** Multi-gene is not the exception
  in CPIC's recommendation table; single-gene is.
* **36 of 121 `(gene, drug)` pairs have no single-gene row at all.** For those the drafter writes
  nothing, because `CpicSnapshot.recommendations` filters `gene_count = 1` (deliberately — a row about
  CYP2C19 *and* CYP2D6 is not a statement about CYP2C19 alone) and the live client applies the same
  `len(phenotypes) != 1` filter.
* They are **recognisable clinical pairs, not edge cases**: TPMT+NUDT15 over the three thiopurines
  (azathioprine, mercaptopurine, thioguanine — 35 rows each); CYP2D6+CYP2C19 over five tricyclics
  (amitriptyline, clomipramine, doxepin, imipramine, trimipramine — 206 rows each); SLCO1B1 with
  CYP2C9 and ABCG2 over fluvastatin and rosuvastatin; CYP2B6+CYP2C19 over sertraline.
* **RYR1+CACNA1S is the one that breaks the fallback argument.** Seven drugs — the six volatile
  anaesthetics plus succinylcholine — and **neither gene appears in a single-gene recommendation
  anywhere in the table**. Elsewhere a module can at least carry the single-gene rule and lose the
  refinement; for malignant-hyperthermia susceptibility there is no single-gene rule to fall back on,
  so a module carries *nothing* for those seven drugs.

**Independently reproduced on a second snapshot, and the two units reconcile exactly.** The peer
session measured `cpic_snapshot_b0ffd4c6f010` and counted **drugs** where the above counts
**`(gene, drug)` pairs**: 103 drugs carry a recommendation, 85 single-gene, **18 pair-keyed across
six pairs** — NUDT15+TPMT (3 drugs), CYP2C19+CYP2D6 (5), CACNA1S+RYR1 (7), ABCG2+SLCO1B1
(rosuvastatin), CYP2B6+CYP2C19 (sertraline), CYP2C9+SLCO1B1 (fluvastatin). Those 18 drugs times two
genes each is **36 `(gene, drug)` pairs**, which is the number measured here from a different
snapshot built six weeks apart. Two denominators, stated apart deliberately
(`@two-surfaces-two-denominators`): *18 of 103 drugs* and *36 of 121 pairs* are the same fact at two
grains, and the drug grain is the more legible one to quote. **Warfarin is in neither**: CPIC's
warfarin guideline is a dosing algorithm and carries no recommendation row at all, so the shape this
entry was reopened on is not even the marginal case — it is off the end of the table.

**What this changes and what it does not.** It does not by itself unpark the entry: the economy and
open-world-negation objections in *What remains* are untouched, and a table keyed on two subjects is
still a design nobody has drawn. What it removes is the *premise* the parking rested on — that
pairing across subjects is a rare shape worth deferring until a corpus appears. Three sources now
carry it (CIViC 209 profiles, CPIC 36 pairs / 78% of rows, ClawBio's one hardcoded branch), and in
CPIC's case the pairs are the routine half of a guideline set this project already ingests and
drafts from.

**The smaller finding beside it is filed separately as S102** (peer report, 2026-09-20): the drafter
does not just skip these, it **misreports** them — the snapshot path's `knows_drug` returns `None`
unconditionally, so the `known is None` arm always fires and tells the author the snapshot *has no
row*, when it has 35 or 206 of them and filtered every one. That is `@answered-is-not-absent`
(answered-and-rejected is a fourth state; the row stays and the *reason* moves), and the arm's
remedy — consult the live API — reaches the identical filter. The fourth arm, the one whose text
names warfarin, is unreachable whenever a snapshot is present.

**A blood-group instance, S119 (2026-09-27): Lewis is keyed on two genes' *phenotypes*.** The
Lewis phenotype (Le(a−b+), Le(a+b−), Le(a−b−)) is a function of the FUT3 phenotype and the FUT2
secretor phenotype, not of either gene's diplotype. `just-dna-lite` shipped FUT2 secretor status as
its own module and left Lewis out for exactly this reason. It is the same subject-pairing shape as
CPIC's six gene pairs, outside pharmacogenomics, and like them it enumerates (a small table over two
per-gene phenotype vocabularies), so it argues for a two-subject key and not for a predicate.
Unbuilt, so it is corpus evidence and not a measured case.

**A longevity instance, 2026-11-03: KL-VS buffering in APOE ε4 carriers.** longevitymap v2's plan
(§4.2, protection type `BUFFERING`) holds that the KL-VS heterozygote matters in ε4 carriers. KL is on
chromosome 13 and APOE on 19, so no haplotype holds the pair, and both halves are already enumerable on
their own (KL-VS as two-SNP haplotype rows, APOE as `apoe_epsilon`). Like CPIC's gene pairs and Lewis, it
argues for a **two-subject key** over two enumerated per-gene states (3 × 6 rows), not for a predicate.
The plan's interim is `flags: conditional` plus prose, and that tag does nothing ([RM321](ROADMAP.md#rm321--variantrowflags-calls-its-reserved-tags-the-tags-the-tooling-acts-on-and-no-tier-acts-on-any-of-them)). Unbuilt; corpus evidence.

### What dissolved, so it is not re-proposed

- **No operator is missing.** Rows are a disjunction and columns are a conjunction, so the existing
  tables already span any finite boolean function over an enumerable set of genotypes: `OR` is two rows,
  `XOR` and bounded `NOT` are enumeration, and `haplotypes.csv` is same-strand `AND`.
- **APOE** — whose ε4 condition (`rs429358==C AND rs7412==C`) is the Constitution's own example of a
  predicate — was built with 0.4 bricks and **no predicate at all**
  (`reference_examples/apoe_epsilon/`). `HaplotypeRow` is a junction table, so same-strand co-location
  is what it already expresses.
- **The cis/trans motivation closed as a check, not a table.** `reference_examples/hfe_compound_het/`
  showed that a diplotype is already a statement about two homologs, so cis and trans are two rows —
  the relational notion the grammar was going to add is what a diplotype pair *is*. What building it
  surfaced instead was that the two rows are **indistinguishable without phase**, which shipped as
  `_cross_validate_phase_ambiguity` (a warning, never a block). A `requires_phase` column was rejected:
  it would make an author restate what the data determines and go stale the moment a haplotype is
  edited. **Confirmed from the caller side, S116 (2026-09-26):** a shipped `just-dna-lite` caller ran
  against this example and the enumeration held — because the module defines the *cis* allele
  (`C282Y-H63D`) as its own haplotype with its own diplotype row, the caller could *name* the
  ambiguity (`ambiguous`, both candidates) rather than guessing or reporting `no_match`. So this is a
  case where enumeration succeeds and no predicate is wanted, which is where the entry drew its line.
  The one thing the caller had to re-derive — *which* diplotype pairs are the phase-confusable set — is
  not a predicate the author states but a value the compiler already computes and discards, filed as
  [RM266](#rm266--the-phase-confusable-diplotype-pair-set-is-computed-at-compile-and-dropped-it-reaches-the-artifact-only-as-a-capped-warning-string), not here.

### What remains

- **Pairing across *subjects*** — no table keys on more than one.
- **Economy and intent** — "any two pathogenic variants in trans" over 300 of them is ~45,000 pairs:
  expressible, unwritable, unreadable.
- **Open-world negation** — "no pathogenic variant in this gene" quantifies over a set the module does
  not close, and absence is only assertable where the region was callable (`requires_callable`). No
  operator fixes this, and a negation feature ignoring it would **manufacture reassurance**, the worst
  failure mode this format has.

It also blocks the "shy module" signal.

### Why it stays parked

It waits on a corpus to generalize from — roughly 70% built; nutrigenomics and supplements do not exist
yet — because fixing a shape against four table kinds and then meeting the fifth is how a one-way door
gets spent badly (P3/P5).

The design thread, the starter shape and what is deliberately left open are in
[PROPOSAL_0_5.md § G3](proposals/PROPOSAL_0_5.md): a new **optional** table, a predicate that **never blocks**, a
grammar kept to the smallest thing covering the motivating case, and a **three-valued** algebra
(true/false/**unknown**, Kleene operators) — with `unknown` withheld, never reported and never negated.
Kleene matters concretely: a conclusion gated on "ε4 present AND QUAL ≥ 60" is decidably **false** at
ref/ref whatever the quality was, so a blanket withhold-on-any-unknown would be strictly worse than the
tables it replaces.

### The cofactor half — CLOSED in the 0.6 review, do not re-open as a general mechanism

The original item proposed **injected cofactors**: values the consumer supplies at query time that a
module must never hold, in three classes. Two of the three were resolved in 0.5 by making them **plain
columns** — clinical context became `DiplotypeRow.clinical_context`, call quality became
`quality_from` / `min_quality` (RM29) — and neither needed a general mechanism.

**Decided 2026-08-13: the general "injected cofactor" mechanism is dropped as never-earned.** Each
remaining class gets the same treatment — a plain column, on demand, one at a time. Two classes wait:

- **Ancestry** — a panel-scale inference, not derivable from a curated module's own gnomAD frequencies,
  since real models do not rely on single SNPs.
- **Family structure** — **this is RM10**, folded in here on 2026-08-13. A declarative trio / de-novo /
  Mendelian-consistency expectation is only meaningful once the consumer supplies family structure at
  query time, which makes it a cofactor class rather than its own item. Designing it separately would
  fix a shape for one class before the axis exists. It was on-demand-only and shapeless for its whole
  life; it stays that way, here.

Neither is built until a real module needs it.

## RM402 — a snapshot answer rejected under RM382 is asked again of live Ensembl, the same authority, which answers the same locus

**Placed, the pm (2026-11-07): after RM401 ships, and only if a re-measure still shows it.** The 600 s here is 38 cold one-at-a-time GETs, which is RM401's cost; batched, the same 38 ids are one POST of tens of seconds. What RM402 would then save is that remainder, bought with a new release-equality rule over two spellings of one label, which is its own risk. So it waits: once RM401 ships, a re-run of the registry's module (or any online re-derivation with reverse-complement genotypes) says whether the repeat asks still cost enough to build it. If not, it closes as superseded by RM401.

**Severity** medium · **Status** open — **a patch**, waits until RM401 ships and a re-measure (fewer requests; the written
table is unchanged wherever the two releases agree) · **Owner** enricher (`enrich/orchestration.py`, the live link's
`missing` ~:948) · **Motivating case** S133 in CONSUMER_SUGGESTIONS_HISTORY.md · *related* RM382, RM373, RM292,
RM401

**The gap.** RM382 sets a rejected answer aside so the next link is asked (`@answered-is-not-absent`). The live
link's `missing` skips an rsID live Ensembl already rejected (`rejected_from(..., _LIVE_ENSEMBL_LINKS)`) but not
one the Ensembl snapshot rejected. Live REST and the snapshot are one authority (RM292 counts REST
self-consistent with it), so at one release REST returns the locus the snapshot did and the rejection repeats.
On the registry's module that was 38 asks, none placed, about 600 s: every one an rsID whose authored genotype
is the reverse complement. `enrich` already tells the author so ("check the strand your alleles are written
on"), and flipping those genotypes is the author's remedy; this item is the cost of the repeat ask, not that.

**What it would be.** An rsID the snapshot answered and the hosting rule rejected is not asked of live Ensembl
when live REST's data release equals the snapshot's (RM373 records both: `/info/data` and the lane's release
label). The release is asked before the loop rather than after it. ClinVar and gnomAD are still asked, being
other authorities, so the rule the gotcha states holds for every *other* link. When the releases differ, or REST's
cannot be read, the ask stays. **Open question:** the two labels are spelled differently (`ensembl_116` against
`…vep116.0`, RM373's won't-fix), so equality needs a stated mapping, tested both ways
(`@one-normalizer-two-spellings`).

## RM405 — an offline enrichment's floor is the Ensembl snapshot's lookups, and the snapshot has no rsID index

**Parked, the pm (2026-11-07)**, as filed from S133. An offline enrichment takes about 10 s a module, which nobody reported as a problem: S133's complaint was the online path. The cheap half (measure the four queries, fewer scans) buys seconds; the real fix is an rsID-sorted layout, which is the snapshot builder's. **Unparks when** a consumer reports offline enrichment time as a problem (a sweep or a deadline it misses), the snapshot builder offers an rsID-sorted layout under RM303's contract, a scope the maintainer highlights touches it, or the roadmap is empty.

**Severity** low · **Status** open — **a minor or a patch, parked** (class by design) · **Owner** enricher
(`resolver._lookup_rsid_candidates`, `_lookup_positions_by_rsid`, `_lookup_rsid_sets_by_position`,
`_lookup_rsids_by_position`) · **Motivating case** S133 in CONSUMER_SUGGESTIONS_HISTORY.md · *related* RM372,
RM303

**The gap.** The registry measured 9 of an offline enrichment's 10 s in four duckdb queries over the snapshot's
parquet view. Two of the four are rsID lookups and two are by position (the registry's note calls all four
by rsID); each scans the 1.17-billion-record snapshot with no index. Which query costs what was not measured
here.

**What it would be.** Measure the four first. Then either fewer scans in one run (one rsID pass, one positional
pass), or a lookup the snapshot's sort order serves. **Residuals, to be stated at closure:** an rsID-sorted
sidecar or an index is the snapshot builder's, prepare-annotations, and its layout is RM303's contract.

## RM406 — dbSNP witnesses only the indels REST was asked about, though the run already holds its placement for every rsID

**Parked, the pm (2026-11-07)**, split from RM398 on the maintainer's ask: "I was suggesting potentially adding one. As a separate item, for future." RM398, the next patch, puts dbSNP where REST was and no further. **Unparks when** RM398's build has counted dbSNP-versus-snapshot disagreements over the registry's replay and the count says what a disagreement should do, a consumer reports a misplacement outside REST's subjects, a scope the maintainer highlights touches it, or the roadmap is empty.

**Severity** low · **Status** open — **a minor or a patch, parked** (class by design: report-only adds counts,
withholding changes which loci are written) · **Owner** enricher (`placement.py`, `identifiers.classify_rsid`) ·
**Motivating case** the maintainer's ask, 2026-11-07; S117 and S132 for the class of error · *related* RM398,
RM267, RM292, RM303

**The cost is not requests.** The maintainer's worry: "On any placed = very high cost, imagine 1M rest calls.
Should be some flag. Some bayesian sampling maybe?" dbSNP's placement comes from the merge check's
`esummary db=snp`. Every online run already sends that for every rsID it carries, on by default
(`verify_rsids=True`), 200 ids a request (`EutilsSettings.batch_size`). So widening asks nothing new and asks
REST nothing: a million-rsID module costs 5,000 esummary requests today, whether their SPDI is read or not.
What widening costs is:

- **which loci a run withholds:** every substitution or ClinVar-held indel dbSNP disagrees with would be
  withheld, and `strict` refuses a subject with every locus withheld;
- **comparison work:** an indel's left-alignment reads the reference; a substitution's comparison reads none.

**What it would be, cheapest first.**

1. **Report only.** Compare every placed rsID with dbSNP and count the disagreements in `placement_agreement`'s
   detail, withholding nothing beyond RM398's subjects. It needs no flag, since it costs no request and changes
   no written row; it says how often the snapshot and dbSNP part.
2. **Withhold**, if what (1) counts shows dbSNP is right where they part. A flag only if two deployments want
   different answers (`@retry-attempt-floor`).

**Sampling answers a different question:** whether a snapshot as a whole is sound, asked once per snapshot
rather than per module. A sample of the snapshot's indels checked against dbSNP at build or provision time
would estimate its misplacement rate with an interval. What a sample can and cannot say, worked on 2026-11-07:

- **A systematic error is settled by a few samples.** The maintainer: "bayessian samples answers alignmend with
  absurd confidence on 5000 samples." If the whole snapshot, or one event kind in it, is off by one, nearly
  every sample disagrees. Even allowing 1% chance disagreement per sample, 10 disagreeing samples in a row is
  about 10⁻²⁰ (near 9 sigma), and 5,000 is beyond any table.
- **A class error is measured, if the sample is drawn from that class.** The known misplacements are
  insertions (S117; S132's 38% of insertions on two chromosomes), so the sample is drawn from indels, not from
  all records, where substitutions would swamp it. 5,000 indels put a 38% rate at ±1.4%.
- **A rare per-record error is not found.** With no disagreement in 5,000, the 95% bound on the rate is about
  3/5,000, 0.06%; at the snapshot's 1.17 billion records that still allows hundreds of thousands. S117's single
  ABO insertion is of that kind. That is why the per-module comparison stays: it costs no request and checks the
  very records a module uses.

**Residuals, to be stated at closure:** that
snapshot-wide audit is the snapshot builder's (prepare-annotations, under RM303's contract), or a provision-time
check filed on its own.

## RM409 — Ctrl-C does not stop `opentargets build` or its rebuild while parts are downloading

**Open, filed by the lead (2026-11-07)** from the maintainer's run: `cache rebuild --only opentargets --publish`,
interrupted about five minutes in (~1 GB of ~22 GB), ignored two Ctrl-C and had to be stopped with SIGTERM to
its process group.

**Severity** low · **Status** open — **a patch** (no surface moves) · **Owner** enricher
(`opentargets_build.download_release`) · *related* RM333, RM408

**Mechanism, read from the code, not yet reproduced in a test.** `download_release` fetches parts on an
eight-thread `ThreadPoolExecutor`. A `KeyboardInterrupt` in the main thread's `future.result()` reaches
`except BaseException`, whose `pool.shutdown(wait=True, cancel_futures=True)` cancels the queued parts but waits
for the eight in flight, each a large part streamed to the end by `stream_to_file`; the `with` block's exit
and the interpreter's exit join the same worker threads again. So an interrupt lands only after every running
part finishes. It is the only bulk download in the enricher on a thread pool (grep
`shutdown(wait=True, cancel_futures=True)`).

**Shape of a fix.** A stop flag the workers' streaming loop checks between chunks (so `stream_to_file`, or a
wrapper around it, owes a cancel hook), set on interrupt before the shutdown; the `.part` staging already keeps
a half-written part from landing under its name. The test interrupts a mirror whose parts stream slowly from a
fake server and asserts it returns within a chunk's time.

## RM410 — the gnomAD constraint snapshot is pinned to 4.1, and 4.1.2 recomputes the metrics

**Open, filed by the lead (2026-11-07)** from the liaison's data-source table and adoption note
(`docs/UPSTREAM_DATA_SOURCES.md`, "Adoption note: gnomAD constraint 4.1 → 4.1.2"). **Class and severity: the
pm's to size.**

**Severity** low · **Status** open — **a patch**, the next on `main`; its publish waits on the maintainer, as
RM408's does · **Owner** enricher (`constraint_build.py`, the `constraint` lane; `gene_metrics.py`) · *related*
RM229, RM408

**What the note found.** 4.1.1 recomputes pLI, LOEUF, o/e and the z-scores (low-coverage coding loci by AN, chrX
and chrY for the first time, a revised LOFTEE `END_TRUNC`); 4.1.2 fixes only the rank and bin fields 4.1.1 got
wrong, so 4.1.2 is the one to take. Every column `_COLUMN_MAP` reads is present in 4.1.2, but the file is
`gnomad.v4.1.2.constraint_metrics.tsv.bgz` (bgzip, 574.5 MB) where 4.1 was a plain 95.5 MB TSV.

**What a move carries.** The URL and a gzip read; the lane's declared size (RM229) and label; every module's
`gene_metrics.csv` drafted from the old snapshot then reads as stale against the lane, which is a content change
consumers see, not a relabel; and `@constraint-two-releases`: which release the live API route answers must be
checked before the snapshot moves past it.

**Sized, the pm (2026-11-07): a patch.** Nothing a reader of the schema sees moves: a URL, a gzip read, the lane's
label and its declared size. Principle 3 sizes it by the schema and leaves the content to its staleness clause, so it
may ship in a patch, declared in the CHANGELOG and not silently. A new release upstream is not a defect of ours, so
severity is low. What it buys is chrX and chrY metrics for the first time, and gnomAD's corrected LOEUF.

- **The live-route question is already answered.** The live `gnomad_constraint` API serves v2.1.1
  (`API_CONSTRAINT_DATASET_LABEL`), not 4.1, so moving the snapshot to 4.1.2 crosses nothing. The two routes keep
  different labels, as now.
- **The build must also handle one thing the note did not name: a re-run over a module that already holds 4.1
  rows.** `enrich_gene_metrics` counts a gene as done only when its row carries one of the pass's two current
  labels (`pass_datasets`, `gene_metrics.py`). Once the snapshot says 4.1.2, a 4.1 row is no longer the pass's, so
  the gene is fetched again and a 4.1.2 row is appended beside the 4.1 one. The module then states two pLI values
  for one gene, and a consumer joining on `gene` gets both. The fix stays in patch scope: the pass counts a row
  from any release of the constraint snapshot lane as its own, so a default re-run adds nothing. Moving a module
  to 4.1.2 is then the author's choice, made by deleting the sidecar (`@sidecar-authoritative`). Its test: a sidecar
  with a 4.1 row, re-enriched against a 4.1.2 snapshot, comes back unchanged.
- **The note says modules "read as stale" against the new lane, but nothing reports that today.** gnomAD has no
  release probe (`currency.default_probes` asks ClinVar, the PGS Catalog and ClinVar-GKM only). A probe is not
  part of this item. It is a residual, to be filed if a consumer asks to be told.
- **For the build, not a decision:** the 4.1.2 file is 574.5 MB compressed, with 113 columns, some of them arrays.
  Select the columns `_COLUMN_MAP` reads while streaming the file, rather than decompressing all of it into memory.

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

**Swept 2026-09-13** across [ROADMAP.md](ROADMAP.md), [ROADMAP_0_8.md](history/ROADMAP_0_8.md) and
[ROADMAP_1_0.md](ROADMAP_1_0.md), prompted by the maintainer after
[RM16](#rm16--authored-prs-weights-a-scoring-file-not-a-manifest) was caught. Every
item carrying a parked-on / would-unpark clause was checked. **One circular, one marginal, one
possibly already satisfied, and the rest sound** — the sweep's value is mostly the eight it cleared.

**Re-sized 2026-11-05, after the 0.8.0 cut (the pm).** 22 items were parked out of [ROADMAP_0_9.md](ROADMAP_0_9.md) into Active items. The 15 rows from RM261 down are new. RM16, RM23, RM28, RM68, RM122, RM164 and RM238 already had rows here; their verdicts stand, and their entries now live in this file.

| Item | Gate as written | Verdict |
|---|---|---|
| **RM16** — authored PRS weights | "a real consumer" — one that combines authored weights into a score | **Circular.** No such consumer can exist before the table does. Re-parked on *shape* 2026-09-13. **Restated 2026-11-05 by the pm** as the shape question, which needs nothing built: **Sound** now. |
| **RM28** tail — the two remaining cofactor classes (ancestry, family structure) | "Neither is built until a real module needs it" | **Marginally circular**, the same family. A module cannot *need* a cofactor class it has no way to express, so read strictly nothing satisfies this. It survives on the looser reading — an author saying *"I want to write this and cannot"* — which is what the clause should say. Low stakes: both classes are on-demand-only and shapeless by design. |
| **RM122** — the measure lookup as a public function | "what it waits on is a caller, not a decision" | **Sound but possibly already met, and nobody has checked.** The rule is normative prose in SCHEMAS.md today, so a consumer can implement it without the function — which means callers may already exist and be silently disagreeing, which is the exact failure the item predicts. **Ask `just-dna-lite` whether it implements the measure lookup** before treating this as waiting. |
| **RM238** — per-tissue eQTL | "reopen this with a consumer, never with an argument" | **Sound.** Somebody can need a per-tissue eQTL answer without our table existing; they would be asking for the data. |
| **RM164** — `heteroplasmy.csv` with no source | "Reopen it with a source, never with an argument" | **Sound, and the cleanest of the set** — a gate on a measured fact about the world, independent of anything here. |
| **RM28** — the predicate half | parked on a corpus | **Sound.** A corpus is counted off other people's published data; it has three entries and none of them needed us to ship anything. |
| **RM23** — predictor scores | "the acquisition measurement done, and a decision on per-transcript grain" | **Sound.** Both are actions available today; the item is unstarted, not blocked. |
| **RM68** — a drafting provider off GRCh38 | "an author with a non-GRCh38 module saying which outcome they wanted" | **Sound.** Such modules exist — `reference_examples/grch37_build` is one. |
| **RM279** — a `conclusion` checked against its own row (filed 2026-09-27) | a measured precision for the locus-restricted rule | **Sound, and met on 2026-09-28**: 10 of 10 real over 653,706 rows, shipped as a hint. |
| **RM309** — a `state` its own conclusion negates (filed 2026-09-28) | a hand-judged precision over the reporter's six curated modules and the registry corpus | **Sound.** The corpus and the rule both exist today, and RM279 met the same gate the day this was filed. |
| **RM388** — placement readers bypass `usable_loci` (parked 2026-11-05) | a real table reaching compile with a row off the module's build or a `not_found` row with coordinates | **Sound.** Anyone who hand-writes or merges a `resolution.csv` can produce one today; nothing needs the fix to exist first. |
| **RM390** — the enricher does not say what compile will refuse (parked 2026-11-05) | an author reporting an `enrich` that passed and a `compile --strict` that refused | **Sound.** The refusal already fires at compile, so the report can come in through `Sn` today. |
| **RM261** — strip comments from the enricher wheel (parked 2026-11-05) | the wheel's size becomes a reported problem, or the packaging is reworked | **Sound.** Anyone installing the wheel can report its size today. |
| **RM248** — a declarative report schema (parked 2026-11-05) | a consumer asks for a report a module cannot declare | **Sound.** The renderer holding the problem (just-dna-lite) exists; it would describe a report, not our schema. |
| **RM181** — a moved digest says nothing about what moved (parked 2026-11-05) | a consumer reports a moved `artifact.digest` the signatures could not explain, or the 1.0 hash-family review | **Sound.** Digests move today. |
| **RM188** — the competitor survey (parked 2026-11-05) | the maintainer names competitor parity as a minor's zone | **Sound, and not this kind of gate.** A decision, available any day. |
| **RM237** — a recurrent-CNV region has nowhere to be written (parked 2026-11-05) | an author wants to write a recurrent-CNV region and cannot | **Sound on the looser reading**, as RM28's tail: an author saying *"I want to write this and cannot"*. |
| **RM240** — the ClawBio nutrition panel in the corpus (parked 2026-11-05) | the corpus is asked for a nutrigenomics example, or RM188 unparks | **Sound.** The translation is already run. |
| **RM266** — the phase-confusable pair set is dropped (parked 2026-11-05) | a consumer asks for the pairs as data rather than as a warning | **Sound.** S116 already came in through `Sn`. |
| **RM281** — `clinicalVariants.zip` unread (parked 2026-11-05) | an author needs a row that archive carries and `summaryAnnotations.zip` does not | **Sound.** Both archives are public today. |
| **RM282** — the PGx lane has one licence class (parked 2026-11-05) | someone runs the source survey its entry describes | **Sound.** The survey needs nothing built. |
| **RM284** — no run-level place for a skip in `verification.json` (parked 2026-11-05) | a reader needs to know, from `verification.json` alone, that a run could not reach a source | **Sound.** Skips happen today. |
| **RM287** — ClinGen dosage has no snapshot lane (parked 2026-11-05) | an offline deployment reports a dosage pass that never ran | **Sound.** `skipped_offline` already says so in every offline run. |
| **RM296** — a PRS has no condition → conclusion table (parked 2026-11-05) | an author writes a PRS module that needs a score → conclusion band | **Sound.** The author holds the problem; `pgs.csv` exists. |
| **RM298** — no per-row ClinPGx provenance on `pharm_variants.csv` (parked 2026-11-05) | the currency check withholds on a real mixed module whose operator needed the answer | **Sound.** RM297's warning fires today. |
| **RM306** — no exon structure in the tier (parked 2026-11-05) | a real module's AlphaGenome rows need an exon-level gene attribution | **Sound.** The AlphaGenome lane ships. |
| **RM378** — errors carry no code (parked 2026-11-05) | a consumer needs to tell apart refusals RM377's two phrases do not cover | **Sound.** S129 already came in through `Sn`. |
| **RM405** — the offline floor is four unindexed snapshot queries (parked 2026-11-07) | a consumer reports offline enrichment time as a problem, or the snapshot builder offers an rsID-sorted layout | **Sound.** The `Sn` inbox is open, and the layout is another repository's to offer. |
| **RM406** — dbSNP witnesses only REST's subjects (parked 2026-11-07) | RM398's build counts dbSNP-versus-snapshot disagreements on the registry's replay, or a consumer reports a misplacement outside REST's subjects | **Sound.** RM398 is the next patch and its build step produces the count; the `Sn` inbox is S117's and S132's channel. |
| **RM15** / **RM69** / **RM52** and the 1.0 queue | a major-version bump | **Sound, and not this kind of gate.** A release boundary is a schedule, not a satisfier. |

**What the sweep did not find, stated so it is not re-run for a while.** No gate anywhere is parked on
a *consumer report that would have to describe the unbuilt thing* — the `Sn` inbox is a channel
consumers can use before we build anything, and every item that names it is asking for a report about
a problem, never about a solution. That is the structural reason only RM16 failed: it is the one entry
whose gate named the *user of the output* rather than the *holder of the problem*.

## Audit findings parked without a number (until a real run meets them)

The maintainer's rule (2026-11-05): "judge how frequently would any bug would realistically fire. For once per known universe
scenario defer to 'when roadmap is empty/someone steps on this defect'." The findings below were confirmed by a pre-cut audit, but no
real run or example has hit them. Each gets an `RMn` only when it **unparks**: a run, a consumer or a test meets it, a scope the
maintainer highlights touches it, or the roadmap is empty. One line each, so the finding is not re-reported as new.

**Audit round 3 of 0.8 (2026-11-05, at `64c835b9`)**, sized by the pm:

- **A client built in a function and never closed**: `clinvar_gkm.py` `lane_currency`, `caches.py`, `clinvar_gkm_build.py`,
  `cli/clinvar_gkm_commands.py`, `currency.py` (two sites). Nothing leaks past a short process. The guard in `test_cli_surface.py`
  skips a function with no `close()` at all. Unparks when a long-lived process (a server) holds the enricher.
- **The S85 warning "recorded as unresolved" fires for an rsID+coordinate pair** (written `authored`/`resolved`; since 0.7) and for an
  rsID-only subject whose placement `--rederive` carries (RM382). Wrong words on a correct table. Unparks on a report of it.
- **RM391's test fence lets a loopback `HTTPS_PROXY` through.** No proxy is set on any machine that runs the suite. Unparks when one is.
- **The regex timeout counts the worker's start-up** (0.4 s under forkserver), so `test_literature.py`'s catastrophic-regex test cannot
  fail. Since 0.7. Unparks when that bound guards a real regex.
- **A ClinVar witness on another contig reads `unplaced`** (`placement.py` `events.counterparts` needs the same contig). Measured: 0 of
  145 corpus rows. Unparks on the first real one.
- **`test_acmg.py` depends on the working directory** (fails from `enricher/`). Since 0.7. Unparks when the suite runs per package.
- **Europe PMC's two DOI lookups raise the outage type on a 410** (`pmids_for_doi`, `record_for_doi`); the recorded reason is still
  `retired`, so only the type is wrong. RM361's guard checks the module, not each method. Unparks when a caller catches by type.
- **`net.py`'s retired-endpoint message advises "upgrade just-dna-enricher"** even when the operator chose the release or URL
  (RM361's amendment, 0.8). Rare; the advice is wrong only for a hand-picked release. Unparks on a report of it.
- **Two leftover import guards for a core dependency** in `download.py`. Dead code, no effect.
- **A malformed legacy `rows` scalar rides along as an extra** in `snapshot.py` (RM303). No instance.
- **STRchive's snapshot has no prefix and no pull record** (`SNAPSHOT_FILE_GLOBS` has no `strchive`). Unparks when STRchive is pulled
  through the shared path.

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
*(**`tradeoff` was reserved here from 2026-11-03 and MOVED on 2026-11-04 on `0.8`**
([RM327](ROADMAP_HISTORY.md#rm327--pleiotropy-has-no-per-trait-row-so-a-trade-off-can-only-be-prose-and-tradeoff-is-computed-rather-than-authored)): the verdict that an allele is `protective` on one trait and
`risk` on another, which the maintainer decided is **computed**, never authored. Since the compile writes
it on `meta_resolved.parquet` it sits in `vocab.MISPLACED_COLUMN_REASONS`, the map for a column real on a
generated table, and an authored `tradeoff` is still refused, with that reason.)*

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
*(**Built in 0.8 as a table, not a column** (RM236): `consequences.csv` → `ConsequenceRow`, one row per
`(variant_key, transcript)`, carrying `impact` (closed, the four classes) and the consequence as Sequence
Ontology accessions in `consequence_so_ids`, the frequency precedence again: a consequence is per
transcript, and a column on the variant row would have to pick one. The bare name `consequence` stays
held for a term label (`missense_variant`), which a mapping from the accessions would fill.)*
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
*Addendum 2026-11-05 (RM380):* the decision stands and the rationale moved. The parquets now carry every
`ResolutionRow` column but a reasoned few on their resolution loci, `status` and `authority` among them,
so "holds no provenance" is no longer true; these three stay out as statements about dbSNP at a moment
(`parquets.RESOLUTION_LOCUS_NOT_WRITTEN`).

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

- **~~A measure kind for base-modification fractions~~ — promoted 2026-09-30.** The VCF 4.5 audit
  (§ 6) parked it for lack of demand. The maintainer then named demand (PacBio samples arriving), and
  [METHYLATION_PACBIO](probes/METHYLATION_PACBIO.md) measured what PacBio users actually hold. The
  per-base VCF 4.5 `M5mC` shape this bullet described has no PacBio producer. What exists became
  RM317 (TRGT `FORMAT/AM`, FMR1), RM318 (imprinting regions in BED/TSV) and RM319 (TRGT's `MC` count),
  all in [ROADMAP_0_8.md](history/ROADMAP_0_8.md).

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
  home-for-the-three-fields half is [RM265](ROADMAP_0_9.md#rm265--the-panel-deprecation-has-no-accepted-signal-on-the-replaced-branch-the-warning-fires-whether-or-not-you-need-the-three-fields-it-tells-you-to-keep-the-block-for)
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
