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
- **[ROADMAP_0_7.md](ROADMAP_0_7.md)** — RM16, RM23, RM28 and the deferred halves of RM55, RM56, RM65,
  plus RM66 and RM67. RM10 closed there, folded into RM28. **Five of its entries are now records rather
  than decisions** — see the line above.
- **[ROADMAP_1_0.md](ROADMAP_1_0.md)** — RM15, RM52 and RM55's removal half, plus the upgrade ledger.
  **The 1.0 cleanup tracker below did not move** and stays the home for the unnumbered major-only items.

Code comments citing "ROADMAP item N" / "ROADMAP 0.3 item 5b" are historical breadcrumbs — follow them
to [CHANGELOG.md](CHANGELOG.md) / [COMPILER.md](COMPILER.md).

**Status:** **0.6.4 is the current line** — `just-dna-enricher` reads `0.6.4`, tagged and built into
`dist/`; format and compiler stay at `0.6.1`. Three partial cuts in a row, which is normal here: 0.6.2
was RM101, 0.6.3 was S41–S44 and 0.6.4 is S45, and none of them touched a model or the compiler. `schema_version` stays `"1.0"` and has since 0.4. **Tagged is not published**: whether a
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

**Two: [RM102](#rm102--the-enricher-loads-a-env-into-osenviron-from-library-paths-and-only-half-of-that-has-an-off-switch)
and [RM103](#rm103--a-version-with-no-digits-coerces-to-000-which-is-a-real-version-nobody-wrote).**
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
[ROADMAP_1_0.md](ROADMAP_1_0.md) (RM15, RM52, RM55's removal half).

**This section read "None in this file" for a day after the six were filed**, because they were appended
below the *Not format scope* heading and nothing moved the boundary — so the roadmap's own summary line
said it had no open work while carrying two high-severity items. Recorded rather than quietly fixed: it
is the [RM_TOC.md](RM_TOC.md) failure mode (an item nobody can find) arriving in the file the index
points *at*, and it is why a new item starts here as a `## RMn` section and gets its RM_TOC row in the
same commit.

The trackers further down are the other live part of this file: the reserved-namespace tracker and the
1.0-cleanup candidate tracker, which the Constitution deliberately keeps out of itself.

## RM102 — the enricher loads a `.env` into `os.environ` from library paths, and only half of that has an off-switch

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** enricher ·
**Motivating case** S39 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

**The half that is already fixed is not this item.** `load_dotenv_file=False` reached none of the six
cache resolvers — the default directory is computed as an *argument*, and `_cache_dir` loaded the file
unconditionally on its way in — so the knob did nothing at all. That is a defect against the
parameter's own contract and it is repaired in the tree (0.6.3, uncut), with the leak demonstrated
before and after over all six resolvers. What is filed here is everything the repair does **not**
reach, and it is a design question rather than a bug.

**What a consumer actually meets.** `load_dotenv` writes the whole file into `os.environ`, not the
cache variables alone, so a process that asks where the ClinVar cache is inherits whatever credentials
sit in the nearest `.env` above its working directory — for a service, credentials for sources it never
asked about. `override=False` reads as the cautious direction and hides the sharp edge: it skips a
variable that is **present**, so *deleting* one is exactly what lets the file supply it. S39's reporter
lost a test's isolation that way and spent an hour inside their own fixture, because the failure is
green on CI (no `.env` there) and different on every developer's machine. Their own repair —
sweeping `sys.modules` and replacing every bound `load_dotenv` with a no-op — is the right defence
today and stays right whatever this item decides, since a `from dotenv import load_dotenv` binding is
per-module and patching `dotenv` reaches none of them.

**Two candidate repairs, and what is wrong with each.**

- *Flip the default to `load_dotenv_file=False` and leave loading to the entry point.* The machinery
  exists and the shape is right: a CLI loading `.env` is ordinary, a library function doing it while
  answering "where is the cache" is not. But a default flip is **silent for every caller who never
  passed the parameter** — nothing raises, nothing warns, and a deployment that pointed its cache
  through `.env` alone simply stops finding it, which is the "the cache is right there" report the
  unconditional load was added to end. That is S14's shape: the addition being legal does not make the
  change legal. Under the charter's cadence a deprecation has to be **actionable**, so the honest
  route is a release that warns when a load would have happened and no explicit choice was made, then
  the flip — which is a minor's worth of work, not a patch's.
- *Narrow it to the cache variables — load the file, set only `JUST_DNA_*`.* Tempting, and it keeps
  every existing deployment working. It is wrong for a different reason: it makes the enricher a
  filter over somebody else's file, so a `.env` holding `NCBI_API_KEY` (which this codebase reads, by
  `@credential-where-read`) would need that name on the allowlist too, and the allowlist is then a
  hand-kept list of every variable any tier might ever read — the exact registry-not-a-list defect
  this repo keeps repairing. It also cannot answer the reporter's real complaint, which is about
  mutating the process environment at all rather than about which keys.

**And the flagless half.** `net`, `eutils`, `literature` and `pharmvar` call `load_env()` with **no
parameter**, deliberately — a credential has to be loaded where it is read (`@credential-where-read`,
RM100). So a caller who passes `load_dotenv_file=False` everywhere still has `os.environ` mutated by
the first network client they construct, and no switch exists to stop it. Whatever this item decides
has to decide it for both halves or it decides nothing: a knob that covers the cache resolvers and not
the credential paths is a knob that reads as an assurance and is not one.

**Not blocking anything.** The behaviour is documented now (ENRICHER § cache locations names the
mutation, the sharp edge in `override=False`, and the switch), which was the reporter's fallback ask
and is what the patch line can honestly carry.

## RM103 — a version with no digits coerces to `0.0.0`, which is a real version nobody wrote

**Severity** low-medium · **Status** open — **a minor, release undecided** · **Owner** format ·
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

**Why it is filed rather than fixed: a new refusal is a tightening, and tightenings size the release.**
Refusing `version: "abc"` makes a spec that compiles today fail tomorrow, which is exactly the RM50 /
RM48 class — both shipped in **0.6.0** as minor work, not as a patch, and INTEGRATION_0_6 § 1 lists
them under *"two checks can newly refuse an author's spec"* precisely because a consumer compiling
other people's specs (just-dna-pipelines) sees CI go red. Severity orders the queue; legality sizes the
release, and this one is a minor.

**Three candidate repairs, and what each costs.**

- *Refuse a digitless version.* The reporter's implicit ask and the cleanest end state: an
  unparseable version is an error, with a message naming the fix the way the float branch already
  does. It is a tightening (above), and under the charter's cadence the honest route to it is a
  deprecation an author can act on — warn in one minor, refuse in the next — since there is a real
  corpus out there and we have already been surprised once by what it contains.
- *Keep coercing but record it in the manifest.* `version_coerced_from` already holds the authored
  text and the compiler already **warns**, naming both values (*"module.version 'abc' was read as
  SemVer '0.0.0'"*) — `validate_spec` reports it identically, so there is no parity gap. Surfacing
  that string in the manifest would make the fabrication auditable rather than invisible, and it is
  purely additive. It does not stop the bad value being published, so it is a complement to the first
  option and not a substitute.
- *Coerce to something that cannot be mistaken for a version.* Rejected: there is no such SemVer.
  Every three-number string is a legal version, so any sentinel is someone's real one — which is the
  whole complaint, restated.

**What the reporter should do meanwhile, and it is not nothing.** The compiler already tells them:
both `compile` and `validate` emit the coercion warning with the authored string in it, so a build
that greps its warnings catches this today. The gap is between the *model* (silent) and the
*pipeline* (loud), and the reporter was testing the model directly.

**One correction to their report, in their favour.** They note their own CLAUDE.md claimed *"an
unquoted `1` in YAML loads as an int and is rejected"* and is wrong on 0.6.1 — `1` coerces to
`1.0.0`. Confirmed, and our documents do not carry that claim: AGENT_NOTES `@yaml-version-int`,
CHANGELOG and DOGFOOD_0_6_FINDINGS all describe the int refusal as the **pre-0.6** state that RM17's
widening fixed. The hazard is the unquoted *decimal*, which is still refused and deliberately so.


## RM104 — `enrich_gene_metrics` raises `UnboundLocalError` on the ordinary re-run

**Severity** high · **Status** open — **a patch** · **Owner** enricher ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_metrics.md`)

`reference` is bound only inside `if wanted:`, and read unconditionally further down as
`constraint_routes_consulted = reference is not None or not offline`. So the two cases where `wanted`
comes back empty — **the idempotent re-run**, where every gene already has a `gnomad*` row, and **any
module with no `variants.csv`** — raise `UnboundLocalError` out of the pass. Reproduced on a scratch
`hboc_palb2` at enricher 0.6.4, offline and online, through the library and through the CLI.

**Why it is worse than a crash.** The pass is documented as merge-not-clobber, so the re-run is the
*supported* path, and RM101 built `GeneMetricsEnrichmentError` precisely so a caller could wrap this
pass in one `except`. An `UnboundLocalError` is outside that contract, so every caller who followed
RM101's advice is unprotected in exactly the case they were told to expect.

**Fix.** `reference = None` before the branch. The test is the part that matters: run the pass
**twice** on a fixture with rows already present, and once on a module with no `variants.csv`. The
existing merge test re-runs with `wanted` non-empty, which is why a green suite has never seen this.

## RM105 — `logo.jpeg` compiles and is attested, and the publisher never uploads it

**Severity** medium · **Status** open — **a patch** · **Owner** enricher (+ format, for the constant) ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `logo.md`)

`manifest.LOGO_EXTENSIONS` is `{png, jpg, jpeg}` and `_collect_logo` iterates `sorted(...)`, so
**`jpeg` wins over `jpg` over `png`** and a spec dir holding two logos silently ships the jpeg.
`upload._ALLOW_PATTERNS` lists `logo.png` and `logo.jpg` and **not** `logo.jpeg`. The result is a
manifest attesting bytes the published repo does not carry — the exact failure
`@publisher-allowlist-derived` exists to prevent, in the one place the allowlist is still hand-spelled.
`verify_manifest(check_logo=True)` does not catch it either: an absent file is not a failure there.

It is named in the CHANGELOG entry that introduced the derived allowlist, and in a code comment that
defers it (*"a pre-existing instance of that same skew, left alone here because widening it is not this
item's decision"*), and no `RMn` has owned it since.

**Fix.** Derive the logo half of `_ALLOW_PATTERNS` from `LOGO_EXTENSIONS`, the way the readme half
already derives from `README_CANDIDATES`. One line, plus a test that walks `LOGO_EXTENSIONS` and
asserts **set equality** with what the allowlist admits — a floor would pass today.

## RM106 — the `faf95` arithmetic warning is published twice

**Severity** medium · **Status** open — **a patch** · **Owner** compiler ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `frequencies.md`)

`_check_frequency_arithmetic` runs in `validate_spec` (added by RM93 for parity) and again in the
compile-side `_frequency_checks`, with no dedup. `_literature_checks`, eleven lines below it, *does*
filter — *"a finding living in both places would otherwise print twice (the `_check_contig_ploidy`
idiom)"*. Measured on a doctored `hboc_palb2`: **15 warnings, 14 distinct**, the
`faf95 … exceeds the group's own allele frequency` line appearing twice. `manifest.compilation.warnings`
is a published field (RM44), so the duplicate is published, and any consumer counting warnings
overstates what is wrong with the module. Same shape as the shipped RM94; violates
`@no-rerun-with-counts`.

**Fix.** `w for w in … if w not in all_warnings`, matching `_literature_checks`. The test asserts
`len(warnings) == len(set(warnings))` over a module that trips the check — an assertion worth applying
to the whole warning list, since this is the second instance of the shape.

## RM107 — a duplicate `(source, layer)` row compiles green under `--strict`

**Severity** medium · **Status** open — **a patch** · **Owner** compiler ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `licensing.md`)

`SourceRow` is in `draft._CORE_DUPE_KEYS` keyed `(source, layer)` — so *drafting* refuses to append
over one — and absent from `compiler._TABLE_DUPE_KEYS`, so *compiling* never checks it. Measured on
`hboc_palb2`: appending an exact copy of a row gave `strict compile ok: True`, no warning of any kind,
`row_count` 7, and a **moved** `source_signature`. A duplicate carrying the **opposite**
`commercial_use` also compiled green — and `licensing.csv` is the file the compile gate keys on.

`licensing.merge_sources_csv` merges on the same pair, so every other writer in the ecosystem already
treats it as the key. The compiler is the outlier.

**Fix.** `_TABLE_DUPE_KEYS[SourceRow] = lambda r: (r.source, r.layer)`. Worth checking the same
question for the other kinds while in there: the map covers five of the nine authored kinds, and
"keyed kind ⇒ dupe-checked" is not the dividing line anyone assumes it is.

## RM108 — a ClinGen re-curation appends a second row and nothing marks the superseded one

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** enricher ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_validity.md`)

`_merge_key` returns `("id", row.assertion_id)` when the source published one — the right rule in
general, and wrong here, because ClinGen's assertion id **embeds the curation timestamp**
(`CGGV:assertion_…-2019-08-18T160312.829Z`). A re-curated assertion therefore arrives under a
different id, misses the merge key, and is appended beside the old one. Reproduced with two injected
exports differing only in date and grade: the file came back with both, and
`manifest.gene_validity.classifications` then publishes a pair — as far apart as
`["definitive", "refuted"]` — with nothing anywhere saying which is current. `classification_date` and
`dataset` are the only discriminators and no consumer reads either.

**Why it needs design rather than a patch.** This is S45's shape, and S45's answer was *name the
superseded rows, delete nothing* — but S45 could tell superseded from current by the rsID's merge
status, and here the only signal is a date the format does not otherwise treat as authoritative. A
currency notion has to be decided before it can be written: is the newest `classification_date` the
answer, or is a re-curation two facts a consumer should see both of? The enricher's own merge test
re-runs the *identical* export, so it cannot see this either — the test is part of the fix.

## RM109 — the gene-metrics fetch-suppression key is not derived from the merge key

**Severity** medium · **Status** open — **a patch** · **Owner** enricher ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_metrics.md`)

The merge key is `(gene, dataset)`; the fetch-suppression key is
`{row.gene for row in existing.values() if (row.source or "").startswith("gnomad")}`. So a hand-written
correction that honestly records itself as `source="manual"` does **not** mark the gene done, the fetch
runs anyway, and the file comes back with two rows sharing `(gene, dataset)` and contradicting each
other. `compile_module` emits zero warnings (see RM107's neighbour: fact tables have no dupe check
either), and the manifest reports it as ordinary.

`clingen.py` — a sibling pass in the same package — gets this right, testing `if (gene, dataset) in
existing`. So the shape is understood; it was simply not applied here.

**Fix.** Derive `done` from the merge key. The general rule is worth writing down beside the fix:
**a suppression set must be derived from the merge key, never restated beside it** — the same
derive-don't-restate rule `@draft-appends` and the drafting guards already carry.

## RM110 — `constraint_flags` has two producers with two encodings, and the column is inside the fact set

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** enricher ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `gene_metrics.md`)

The live API route writes `"|".join(sorted(flags)) if flags else None`. The snapshot route copies
gnomAD's TSV cell verbatim, and gnomAD writes a **JSON array literal** there; `[]` is not in
`constraint_build._NULLS`, so it survives as the two-character string `"[]"`. Measured over the
published v4.1 snapshot: **17,403 of 18,111 rows** carry `"[]"`. Every consumer writing the obvious
`if row.constraint_flags:` therefore reads 96% of snapshot rows as *flagged*, and the same gene fetched
two ways gives two different cells. The field description (*"kept verbatim and pipe-joined"*) is true
of one producer only.

**Why it is not a patch.** `constraint_flags` is inside `GENE_METRICS_FACT_FIELDS`, so normalizing
`"[]"` → null **moves `gene_metrics.signature`** for every module already carrying snapshot rows. That
is legal — a fact signature moving is not a compatibility break — but it is a recompile the ecosystem
should be told about, which makes it a minor with a CHANGELOG line rather than a quiet fix. Decide the
canonical encoding first (pipe-joined string, or null-when-empty on both legs), then move both
producers to it in one release, and correct the field description in the same change.

## RM111 — three shipped strings assert a registry override of `license` that nothing performs

**Severity** low · **Status** open — **a patch** · **Owner** format ·
**Motivating case** the 2026-08-19 doc audit (just-module-creator's `module_spec.md`)

`spec.py:355` (*"Advisory and registry-overridable, exactly like `module.version`"*), the matching
comment at `compiler.py:5220`, and `normalize.py:40` all state that a publishing registry overrides
the authored `license`. Verified in the registry checkout: its publish path never writes that field.
`module.version` really is stamped, so the analogy the strings lean on is sound for *version* and
false for *license* — which is exactly how the claim survived review.

Two shipped `Field(description=…)` are involved, so this ships to authors through
`describe_table`/`authoring_reference` and is read as a contract.

**Fix.** Decide the intent, then make one side true: either correct the three strings (the cheap and
probably right answer — a licence declaration is the author's claim, and the compiler already checks
it against `licensing.csv` rather than replacing it), or file the override as registry work. Do not
leave them disagreeing; a `Field(description=…)` is the most-read documentation in the repo.


## RM117 — an outrank record exists and no check reads it, and what a check should do is undecided

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** enricher (+ compiler,
if the severity ladder moves) ·
**Motivating case** [S52](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator)

**The half that shipped.** `ProvenanceItem.outranks` — `{column: why}`, per column, additive, in the
tree since 2026-08-20 — so an author overriding a checked value has somewhere to record *why*, and the
capture half the reporter is building has a place to write. Neither identity moves. See SCHEMAS.md.

**The half that is open, and it is a design decision rather than a missing line of code.** The
proposal is that a filled record change the **severity** of a source-mismatch: WARNING today, INFO
where a record names the column. Never silence and never a pass — the record is an author's assertion,
not evidence, and a green check would re-create the vacuity problem through the back door.

**Why this is not obviously right, which is why it is filed rather than shipped.**

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

**What is genuinely free and worth having whatever is decided**, because the check already runs every
compile: a mismatch that has since **resolved** means the archive caught up to the outrank, which is a
trust signal available nowhere else, and a record whose row's value has changed again is stale by
construction. Both are observable without asking anyone anything.

**Do not answer this by parsing the prose.** The field is freeform because the judgement is not
formalizable — a grading pyramid exists, but whether a retraction outranks an archive call is a
natural-language question. Presence is the bit a check may read.

## RM122 — the measure lookup is specified and nothing anywhere implements it

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** format ·
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

