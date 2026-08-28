# Roadmap — 0.7 and later minors

**What this file is.** Items that are legal in a minor and were **not** taken into 0.6, each with the
reason it waits. Split out of [ROADMAP.md](ROADMAP.md) on 2026-08-13 so that the active roadmap
describes the line being built and a deferral is filed against the release that will decide it, rather
than accumulating in one document nobody can read as a plan.

Everything here is **additive under Principles 3/4/8** — a new optional column or table — so none of it
is waiting on a version. Each waits on a design question, a corpus, or a consumer.

**RM122 arrived here on 2026-08-21 from the active roadmap**, and the move is the point rather than
a detail: it was filed under *open, release undecided* when nothing about it was undecided. An item
waiting on a caller belongs in this file. A heading that says "undecided" turns a park into a
backlog item nobody can close.

**RM69 left for [ROADMAP_1_0.md](ROADMAP_1_0.md) on 2026-08-27, and it is the mirror of that move.**
It was filed here on 2026-08-13 by *legality class* — its repair is minor-legal — while its only stated
unblocker was RM15, a major. So it contradicted the paragraph above it from the day it arrived: an item
whose deciding release is 1.0 is not waiting on a design question, it is waiting on a version, and this
file says nothing here does. Filing by what a fix *costs* rather than by what decides it is how an item
becomes unreachable from either plan. **RM68 stays**, and the distinction is worth stating because the
two entries look alike: RM68 has two exits, and the one that governs is *a real author with a non-GRCh38
module saying which outcome they wanted*. RM15 merely dissolves its premise. A demand exit keeps an item
here; a version exit does not.

**Five of these were taken back into 0.6 on 2026-08-16, and this file no longer decides them.** RM55's
fix, RM72, RM82, RM84 and RM87 were sorted into
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md), which re-asked whether the release they were filed against
was still the right one now that 0.6 is uncut. **That document is authoritative for all five**; their
entries below are kept as the record of what was observed, and where a probe overturned an entry the
entry says so at the top. Nothing was taken on a legality argument — everything here was already legal
in a minor — so what moved them is severity: a shipped thing that is silent, wrong or lying outranks a
capability nobody has asked for.

Indexed in [RM_TOC.md](RM_TOC.md). The 0.6 decisions that touched these items are in
[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md) and [PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md).

---

**RM126 arrived here on 2026-08-21 and is the one item in this file that is owed rather than
offered.** Everything else here waits on a design question, a corpus or a caller. RM126 waits on
nobody: the Constitution was amended the same day to require that a release declare its corrections,
so the charter now names a channel that does not exist. It is filed here because it is 0.7-sized, not
because it is deferred.

## RM126 — nothing tells a consumer what a release changed about compiled *output*

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output) on 2026-08-28 — BUILDS in 0.7, in full plus the S65 roster.** Record + `needs_recompile` in format, the sweep in the compiler, the gate in the bump→tag sequence; intervals compose as a union over `(a, b]`, which is what gives S65's convergence requirement for free.

**Severity** medium-high · **Status** **queued for 0.7, moved here 2026-08-21 — to be built, not
parked.** The charter now *requires* this channel: Principle 3 says a corrected derivation may ship in
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

## RM122 — the measure lookup is specified and nothing anywhere implements it

**Severity** medium · **Status** **parked on demand, moved here 2026-08-21** — additive and
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

**Severity** medium · **Status** deferred — **considered for 0.6 on 2026-08-13 and held**, on the two
blockers unchanged · **Owner** format (schema + compiler) + enricher · **Motivating case** pathogenicity
triage; splice-impact panels

`predictions.csv` — the groundwork every predictor source needs, built **once**: one row per
`(variant, predictor, score_kind)` with `score`, `dataset`, `source`, and an optional `transcript`.
**Long-form, not wide, is the load-bearing choice** — SpliceAI is four deltas plus positions, CADD is
one number, AlphaMissense is one plus a class, so wide columns would make every new predictor a schema
bump while long form makes it *data*. A predictor score is the same class of object as an allele
frequency or a LOEUF (a per-variant number from a named dataset, no measurement), so the 0.5 sidecar
precedent covers it.

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

---

## RM16 — Authored PRS weights (a scoring file, not a manifest)

**Severity** medium-large (on demand) · **Status** deferred — **considered for 0.6 on 2026-08-13 and
held** · **Owner** format (schema + compiler) · **Motivating case** authored-weight PRS modules

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

---

## RM28 — Meta-conclusions (the predicate half)

**Severity** medium (after the corpus) · **Status** parked on a corpus — **and halved on 2026-08-13**:
the injected-cofactor half closed, the predicate half stays here · **Owner** format (schema + compiler)
· **Motivating case** combination annotations; disclosure policy

**Read this entry knowing how much of the original item has already dissolved.** Probing in 0.5 removed
most of it, and the 0.6 review removed the rest of the cofactor axis. What is left is genuinely small
and genuinely unsolved.

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
  edited.

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

---

# The VCF 4.4 items deferred out of 0.6

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.

## RM55 — copy number and repeat count are not whole numbers (the usable fix)

**Severity** high · **Status** ✅ **shipped in 0.6** — built to
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM55, which is authoritative and against which this entry
is stale in its suggested fix; only the **removal** of `modifier_cn` is still 1.0
([ROADMAP_1_0.md](ROADMAP_1_0.md)). Indexed in [RM_TOC.md](RM_TOC.md); the built shape is described in
[SCHEMAS.md](SCHEMAS.md) · **Owner** format (schema) + compiler

**One deviation from the proposal, taken while building and recorded here.** The proposal says a group
carrying a fractional value is read under the continuous rules *"whatever its kind's default says"*.
As built, the inference fires only where the kind would default to `quantised` — that is the only
reading a fraction contradicts. `activity_score` defaults to *neither* precisely because the score is
summed onto a grid whose step the schema does not know, and it is fractional by nature: reading it as
continuous produced three "coverage gap" warnings on `reference_examples/cyp2d6_structural`, whose real
bins sit at 0.25/0.5/1.25/2.25, for intervals no activity score can land in. The proposal's own
sentence two paragraphs earlier — that `activity_score` *"keeps its third behaviour (no gap warning, a
shared endpoint is an error)"* — is the half that was kept.

> **Stale below.** The proposal's probe found the bin bounds are *already* `float | None`
> (`binning.py:231`, `:238`), `_INTEGER_KINDS` has exactly one code reader (`binning.py:688`), and the
> unstated half of the defect is that the shared-endpoint rule **refuses the continuous tiling that
> would fix it** (`binning.py:666-677`). So "a parallel float column beside the integer one" names a
> column that mostly does not exist. What was decided instead: an optional `measure_tiling` column
> (`{quantised, continuous}`) for the tiling half, read as an **effective** tiling — declared, else
> inferred from a fractional value (one-directional and announced, since fractional-ness is
> incompatible with quantised semantics while integer-ness implies nothing), else the kind's current
> default — **plus** the
> parallel float column applied to `modifier_cn` — the one genuine `int` — as `modifier_copy_number`,
> read through an effective-value alias that falls back to `float(modifier_cn)`, with `_KEY_FIELDS`
> keying on the effective value so a key never holds two spellings. `modifier_cn` is deprecated in 0.6
> and **removed** at 1.0, so the three-release route collapses to two.

VCF 4.4 §7.2: *"Redefined INFO and FORMAT CN to support non-integer copy numbers"*, with fractional
worked examples throughout, and §3 standardises the repeat count `RUC` as a **Float**. Both kinds sit in
`_INTEGER_KINDS` here, so a copy number of 2.4 matches **no bin at all**, silently, `--strict` included —
and `CopyNumberRow.modifier_cn` is typed `int`, so even a modifier dosage cannot be written down.

**Suggested fix, and the reason it is this one.** A **parallel float column beside the integer one**,
with the integer column deprecated and removed at 1.0. It is strictly additive and therefore
charter-clean, where the direct correction is a **retype** plus a change to what published bin tilings
mean — reserved for a major. Three-release route, decided 2026-08-13: **0.6 makes the defect loud, 0.7
makes it fixable, 1.0 removes the wrong column.** An author is never more than one minor away from being
able to write a fractional dosage, and no published table is retyped under anyone.

**Still open when this is designed**, and the parallel column does not foreclose either: whether
quantised-versus-continuous is a **per-table declaration** or a **sixth measure kind**. The two kind-sets
answer *"can a hole be arbitrarily small?"* and *"can two bins touch?"* separately, and a rounded catalog
count and a continuous segment mean genuinely differ on both — so this is not a formality.

**Do not** simply move the kinds into the continuous set: `[2,2]` beside `[3,3]` is a legal integer
tiling today, and continuous semantics change both the shared-endpoint rule and the gap warning for
tables already published.

## RM56 (policy half) — the rule for a measurement that spans bins

**Severity** high on the flagship example · **Status** 0.6 ships withhold plus an explicitly
not-implemented warning; **the policy lands here, gated on real caller output** · **Owner** format
(schema) + compiler

A real repeat call is `RUC=38, CIRUC=-5,5` — `[33,43]`, crossing all three Huntington thresholds, so
`htt_repeat_expansion` says *benign*, *uncertain* and *fully penetrant* at once. 0.6 makes withholding
the stated behaviour and says loudly that no policy exists yet.

**The policy is a closed vocabulary** — withhold / take the worst bin / take the point estimate — stated
by the curator and applied by the consumer. That is annotation rather than measurement, so it stays
legal. **Its grain is deliberately undefined**: per table matches how the decision is actually made (a
stance on a whole disorder), per row is more expressive and nobody has demonstrated the need.

**The prerequisite is a real caller VCF**, so the vocabulary is fixed against what callers emit rather
than against a guess. Same gate as RM65 and RM66.

**Never** widen the measurement into an interval on the row (`measure_min_observed` and friends): that
puts a *measurement* in the module, which the data-agnostic north star forbids outright.

## RM65 (implementation half) — repeat and copy-number tables are positional

**Severity** medium · **Status** 0.6 corrects the false claim in the code; **the coordinates wait here**
· **Owner** format (schema) + compiler

§5.6 says POS and SVLEN specify the interval a copy number is defined over; §5.7 says a `<CNV:TR>`
record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based callers"*. So
a tandem repeat and a copy-number segment are **loci with coordinates**, emitted at fixed published
positions, and the compiler's claim that these tables are unjoinable *"which is a property of what they
describe rather than a gap"* is false for both. 0.6 fixes the comment.

**Adding the coordinates waits on a real repeat-caller or CNV VCF sample, or a consumer field report.**
Without one it is scaffolding in thin air — and it is not free: it would put two more tables into RM43's
coordinate-filling path, taking that lane from three tables to five.

**And it carries an RM87 obligation, noticed while that lane was being built.** The reverse writer's
positional-table pass hard-codes `locus_index = 0` (`_write_resolution_csv`, the second loop), which is
honest only while those tables never expand — true today, since RM43's fill is one locus per row.
Putting coordinates on the repeat and copy-number tables is exactly what could make one of them expand,
and the `0` would then be a wrong number rather than a trivially correct one. Not a blocker for RM65;
a line whoever implements it must clear.

## RM66 — one repeat locus, several motifs

**Severity** medium · **Status** deferred here with RM65, same prerequisite · **Owner** format (schema)

§5.7: a `<CNV:TR>` allele *"can encode multiple different repeat motifs in a single allele"* (`RN=3`,
`RUS=CAG,TG,CAGG`). `RepeatAlleleRow` is keyed `(gene, repeat_unit)` and binds one count to one motif.
For HTT the interruption structure `(CAG)n(CAA)(CAG)` is exactly what a modern caller reports as several
`RUS` entries, and the pure-CAG tract length differs from the total — a difference with published effect
on age of onset. The key cannot say which count the thresholds are about, and two motifs for one gene
read as two unrelated groups rather than components of one allele.

A keying change on a shipped table, which is the expensive kind. Filed beside RM65 so both arrive with
the same evidence.

## RM67 — polyploid and partially-phased genotypes

**Status** **not work** — a documented divergence, numbered so it is findable and not re-probed

VCF 4.4 §7.2 added polyploid partial phasing (`GT |0|0/1/2`), first phasing indicator optional. Our
grammar caps at two alleles and refuses a leading separator (probed: `A/A/G` and `A|G/T` both rejected).

This is a **defensible generalization** — the format annotates human diploid loci, and
`_check_contig_ploidy` already handles the hemizygous and haploid directions. **No change proposed.** The
spec's own polyploid example is a tandem duplication with SNVs on it, which a CNV-aware consumer will
meet, so revisit if one actually does.

**The message changed on 2026-08-14; the decision did not.** Dogfooding a duplicated CYP2D6 — the
spec's own polyploid example — refused the call with a bare restatement of the grammar, so a deliberate
limit read as a syntax error, while every other deliberate refusal in this schema names its own limit
in-line. The arity refusals now carry that sentence: two alleles is a decision, VCF 4.4 §7.2 permits
more, and nothing is queued against it. Recorded as D3-2 in
[DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md).

---

# The 0.6 dogfooding items deferred out of the fix round

Five findings from [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) whose obvious repair is itself a
design decision. The ledger classes each **surface** rather than **fix**, which is this repo's standing
split: a false claim, a misdiagnosis, an unaggregated wall or an unreached guard gets fixed in the round
that finds it; anything whose repair has to be *chosen* gets filed with the candidates and the reason
each one fails. The refutations are the point of these entries — an item that only names a gap is one
somebody re-derives from scratch a release later.

Everything below is legal in a minor. Where a repair would be additive it says so; where the only
candidate repairs are illegal it says which principle bars them. Legality sizes the release; severity
only orders the queue.

## RM68 — a drafting provider on a non-GRCh38 module: refuse, or strip to the rsID

**Severity** medium (high before the warning shipped) · **Status** the warning shipped in 0.6
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

## RM70 — `requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm70--requires_callable-is-variantrow-only-so-no-pgx-table-can-state-cpics-core-assumption) on 2026-08-28 — BUILDS in 0.7.** `requires_callable` on `HaplotypeRow` and `PharmVariantRow`, not on `DiplotypeRow`; `callable_from` does not travel with them.

**Severity** medium · **Status** deferred — additive and minor-legal, waiting on a decision about which
table owns the claim · **Owner** format (schema) + compiler · **Found by** dogfooding on 2026-08-13,
`reference_examples/cyp2c9_warfarin_grch37/`

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

**What would unblock it:** a decision on the home, plus a real module whose author wants to state it.
The reading that survives the candidates above is *two* optional columns, on `HaplotypeRow` and
`PharmVariantRow` — the PGx tables that name a position — and **not** on `DiplotypeRow`; whether the
companion `callable_from` travels with them is a second question, and the cheaper answer is to add it
only when a module needs to say where the proof lives. Additive and minor-legal under P3, so nothing
waits on a version.

## RM71 — the alleles a drafted `genotype` stub must be written from are in no file

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file) on 2026-08-28 — BUILDS in 0.7, and no schema moves.** The answer to *where does an author do this work* is **in the command they already ran**: the worklist covers every stubbed row in the file rather than only this run's additions, and `draft-panel` gains the `--dry-run` that `draft` has. The bulk advisory command is rejected for putting the worklist in a third place.

**Severity** medium · **Status** deferred — every place the information could legally go is also the
wrong place, and that is the decision · **Owner** enricher (`clinvar_draft`) + compiler (`draft`) ·
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

## RM72 — six verification members still emitted by nothing, and the "Writes nothing" contract

**Severity** medium · **Status** **SHIPPED in 0.6 PT2 (lane C), 2026-08-17.** The four members are
wired unconditionally (`check-identifiers` three, `check-acmg` one), the reword landed at the three
sites that carry *this* promise, every member of `VALID_VERIFICATION_CHECKS` now says on its own line
whether it is wired or reserved, and `merge_records` no longer lets a `skipped` record displace a
`ran` one. The merge rule gained a condition the proposal did not anticipate and the implementation
found: the protection holds **while the authored bytes stand still**, because an answer over bytes the
author has since edited is not an answer this document may keep asserting — without it the fix
re-opened a defect an earlier `literature` round had closed. The `create-module` skill needed no edit,
as predicted: its rows for both commands carry no "Writes nothing" annotation. See
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM72; the two reserved members did not move. *Previously:*
deferred — four members blocked on a printed contract, two deliberately
reserved, one general question open · **Owner** enricher · **Found by** dogfooding on 2026-08-13,
`reference_examples/hboc_palb2/`

**The quoted docstrings below are the pre-RM72 text, kept because they are what the item was about.**
The citations in this entry had already drifted to lines that no longer held them once, so they now
name the command or the symbol rather than a line number.

**Scope.** This is the surfaced remainder of the D4-1 finding. That finding counted **twelve** of
seventeen `VALID_VERIFICATION_CHECKS` members as emitted by nothing; six of them were wired in the same
round that filed this (`citation_existence`, `citation_identifier`, `provenance_quote` from `literature`;
`allele_function` and `vrs_allele_id` from `pgx` and `vrs mint`; `rsid_coordinate_agreement` inside
`enrich`). The honest remainder is narrower than the headline, and the narrowing is the point.

### The four blocked on a printed contract

`gene_symbol_currency`, `trait_currency` and `gene_locus_agreement` belong to `check-identifiers`;
`acmg_secondary_findings` belongs to `check-acmg`. Both commands do put their question, report the
answer to stdout, and let the record die with the process — the sentence RM45's own docstring opens with
as the thing it exists to fix. Wiring them is not a small matter, because both commands **promise not to
write**:

> `check-identifiers`: *"Writes nothing: unlike the rsID check (whose verdict lands on resolution.csv),
> these are module-level identifiers with no sidecar column to record, so the report is the whole
> output."* (`enricher/src/just_dna_enricher/cli.py`, `check_identifiers_`)
>
> `check-acmg`: *"Writes nothing, for the same reason `check-identifiers` writes nothing: `acmg_sf` is
> an authored cell this asks a registry about, not a fact this pass contributes. Filling it here would
> break the check — see `hints.REDUNDANCY_BEARING`."* (same file, `check_acmg_`)

The same promise is made by `hint` in both CLIs (`hint_app`'s help in each `cli.py`), by `lookup`'s
module docstring, and — the part that decides how expensive a
reword is — by `docs/ENRICHER.md`, `docs/COMPILER.md`'s coverage table and the `create-module` skill's
command tables, which are printed for an author who has `pip install`ed the package and has no checkout.
It is a published contract in both CLIs, both package references and the skill, not an implementation
note.

**What "writes nothing" protects, and it is not one thing.** For `hint`/`lookup` it protects the
inject-only escape hatch and the Class-2 checks: `lookup`'s docstring says *"not a file, not a cell"*,
and the reason is `REDUNDANCY_BEARING` — a surface that can write is a surface someone asks to write,
and `--apply` on a lookup would ship the parked co-authoring item without deciding it. For
`check-identifiers`/`check-acmg` the stated reason is narrower and different: the cell in question is
*authored*, and filling it breaks the check. Both reasons are about not writing into the module's
authored data. Neither is about not writing a record of having asked.

**Is an attestation a *write* in the sense the promise means?** On the reason, no: `verification.json`
holds two counts and a closed skip key per check and no authored cell at all, so it cannot make a
Class-2 comparison vacuous, which is the harm both docstrings name. On the words, yes — and the words
are what a reader outside this repo has. The asymmetry gives the item away: `enrich` writes
`verification.json` and nobody calls that a violation, because `enrich` never promised otherwise. So the
blocker is not the design, it is that a narrowly-justified rule was written down as a blanket. Restating
one is not a docstring edit here: a printed contract is the surface this repo has measured the cost of
getting wrong, at 3,038 rows for the 0-vs-1-based `start` description.

**Would `--attest` be a second switch?** Yes, and it is the wrong shape twice over. The tier's standing
rule is that `--offline` is the switch and a pass adds no second CLI flag. Worse, a flag makes the
record *optional*, and an optional record is ambiguous between "the check was not run" and "it ran
without the flag" — which reintroduces the two-readings-of-one-absence defect the skip vocabulary
(`not_requested` versus `offline`) was built to end. A record has to be unconditional or absent by
design, never conditional on a switch.

**Candidate repairs, then:**

- **Wire them and leave the docstrings.** Ships commands whose printed contract is false. `describe` /
  `requirements` / `reference` and the skill's command tables are the authoring contract, not
  commentary, and this batch already found four other items landing just short of that surface.
- **Wire them and reword every site that carries the promise.** Legal, probably right, and a decision —
  the reword has to separate *writes no authored cell* from *writes no file* without inviting the
  `--apply` request the blanket wording deters, and one of those sites is written for a reader who
  cannot follow a pointer to the reason.
- **Fold both checks into `enrich` so the record comes from the pass that already writes.** They are
  separate commands because they are separately expensive and separately optional (OLS4, HGNC, the ACMG
  page), so this makes every enrichment pay for them. It also contradicts `merge_records`, whose whole
  purpose is that two commands write into one document.
- **Drop the unreachable members.** The one move Principle 3 bars: the vocabulary is closed and
  permanent within a major, so a removed member cannot return until 1.0 — and the vocabulary's own
  comment argues the opposite direction, that adding a name *late* means the release that needs it has
  none to write.

### The two deliberately reserved — not gaps, and not to be "wired too"

**`gene_disease_validity`.** Argued in the code beside `vocab.VALID_VERIFICATION_CHECKS`: it
*"has **no emitter yet** and is kept on the `withdrawn` precedent … 0.6's `enrich_gene_validity`
**records** ClinGen/GenCC verdicts into a derived table and compares nothing authored, so it does not
emit this. The member is for a future pass that checks an authored gene/phenotype pair against those
verdicts."* Wiring it to `gene-validity` would report a check where no question was put, which is the
confusion RM45 exists to end.

**`dosage_sensitivity`.** The same shape, with less written down. `dosage` is a `gene_metrics.csv`
writer and does not appear in `docs/ENRICHER.md`'s check table at all; the member's own comment reads
*"an authored dosage claim vs ClinGen's curation"*, and there is no authored dosage claim anywhere in
the schema — `haploinsufficiency` and `triplosensitivity` are columns on the **derived**
`GeneMetricsRow`. So it is reserved for a pass that does not exist, exactly like `gene_disease_validity`,
and unlike it nothing states so. That asymmetry is the small concrete deliverable this item carries: a
member should say on its own line whether it is *wired* or *reserved*, which is what would have made the
D4-1 headline count of twelve read correctly the first time. **Both now do**, and both stay reserved.

The exclusion half is already tested in one direction.
`schema/tests/test_verification.py`'s `test_a_pass_that_only_records_a_source_gets_no_member` pins
that `clinvar_assertion_tier`, `clinical_assertions`, `allele_frequency`, `gene_constraint` and
`article_license` are **not** members, on the rule the `assertions` command states about itself: *"It
records; it does not adjudicate."* Nothing tests the other direction, which is where the two reserved
members live.

### A finding about the merge itself, not about any one pass

Wiring the first of the six turned up something that belongs here rather than in the pass that found
it, because it is a property of the mechanism every future wiring will use: **`merge_records` replaces
per check, so a later run can downgrade a true verdict to a skip.** Measured — an offline `literature`
re-run, which is a documented no-op that keeps the existing sidecar as the pin, rewrote a real
`subjects=2 findings=1` record to `subjects=0 findings=0 skipped=offline`. The pass that found it is
repairing its own instance.

What is worth recording is that the general rule may be the one at fault. `merge_records` is *newest
wins, per check*, and its own docstring already argues the opposite case one step out:

> A check absent from `fresh` keeps its earlier record: a run that did not put a question has said
> nothing about it, and deleting the older answer would turn "not asked this time" into "never asked",
> which is the exact collapse RM45 exists to undo.

A `skipped(offline)` record **is** a run that did not put the question — the same fact, spelled as a
record instead of as an absence — so the argument that protects an absent check protects this one too,
and newest-wins does the deletion the docstring refuses. The counter-argument is real and is why this
is not decided here: a skip is a *fact about the latest run*, a reader may legitimately want to know
that today's enrichment could not reach the source, and a rule that lets an old `ran` outlive every
later skip can present a stale verdict as current. Both readings are defensible, which is what makes
the merge rule a design question rather than a bug: whether "newest wins" should hold unconditionally,
hold only between two `ran` records, or be replaced by something that keeps both facts. It reaches
every check wired from here on, so it wants deciding once.

**Decided and shipped in 0.6 PT2.** Newest-wins holds between two records of the same disposition; a
skip does not displace an answer. The counter-argument above is answered rather than dismissed — a
skip is a fact about the **run** and `verification.json` is a per-check document, so a run-level fact
needs a run-level place, which is a separate question and was not opened. The stale-verdict half of
the counter-argument turned out to be the real constraint and is handled by a condition the
implementation added: the protection applies only while the earlier record still describes the
module's authored bytes (`existing_still_binds`). Once they have moved the older record is about rows
that no longer exist, and this run's honest "could not ask" wins — which is what `literature` relies
on when a module's citations change, and without it this fix would have re-opened a defect an earlier
round had closed.

### The general question

Is a check that reports to stdout and writes no record a **defect**, or a legitimate **read-only
surface**? Both readings are live in this codebase and neither is stated. `hint` and `lookup` are
read-only on purpose and should stay that way. `enrich` and `enrich_clinpgx` attest. `check-identifiers`
and `check-acmg` sit between: they put a real authored-versus-source question, which is precisely the
membership rule `VALID_VERIFICATION_CHECKS` states — *does this compare something the module asserts
against what a source says?* — and then answer it only to a terminal.

**What would unblock it:** a decision on that line, which then settles the reword. The four members
follow mechanically once it is made; the two reserved ones do not move either way.

**Decided for these two commands, and only for them.** The line is not *does it write* but *does it
compare something the module asserts against what a source says* — a surface that puts that question
owes a record of having put it; a surface that answers a question about a value owes nothing. So
`hint` and `lookup` stay read-only on purpose, and their "writes nothing" is untouched.

---

# The lifecycle items — what writing down the second pass surfaced

Filed on **2026-08-16** out of [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md), which mapped a module from
origin to publish to a consumer's join and found that **the second pass had never been written down at
all**. Four items, none of them a defect in a rule: each is a place where two individually-correct rules
compose into something nobody chose, or where an absence only bites the second time somebody opens a
module. The document keeps the measurements (§5.1 the canary, §6.2 the six-edit consequence matrix, §6.3
what deleting a sidecar costs); these entries keep the decisions and the refused repairs, and do not
restate the numbers.

They were the closing section of that document — an "open questions" list — which is exactly the shape
this repo has twice found to be a backlog nobody reads. A question filed against a release is findable;
a question at the bottom of a prose document is not.

Everything here is legal in a minor.

## RM82 — the attestation binds raw bytes, so an editor's line endings un-close a module

**Severity** low-medium · **Status** **shipped in 0.6 (2026-08-17)** — `\r\n` → `\n` before hashing,
nothing else; `integrity.newline_normalized_file_entry`, used by the binding and by nothing else ·
**Owner** format (schema: `verification.module_binding`) · **Found by** the §6.2 measurement, and
sighted once before from the other side

> **One fact this entry does not carry, and it is the whole implementation.**
> `module_binding` *is* `artifact_digest` (`verification.py:79-90`), and `size=stat().st_size` is inside
> the hashed listing (`integrity.py:80-83`, `:106-112`). So normalizing the digest input while reporting
> the on-disk size **still moves the binding** on exactly the CRLF files the fix exists for — the naive
> implementation is a no-op that looks like a fix. The normalized length has to travel with the
> normalized digest, through a builder used by the binding and by nothing else. See
> [PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM82.

### What was observed

Measured in [MODULE_LIFECYCLE § 6.2](MODULE_LIFECYCLE.md#62-the-consequence-matrix--measured-not-derived):
rewriting `variants.csv` with a different line ending changed no value, no digest and no signature —
and still dropped the attestation **and** the closure. `verification.json`'s `module_hash` binds the raw
bytes of the authored files, so a formatting change an author never intended costs exactly what a
re-authored conclusion costs. An author whose editor normalizes newlines un-closes their module without
touching a cell.

### The decision

**Normalize `\r\n` → `\n` on the bytes before `module_binding` hashes them.** What separates this from
the content-aware binding RM45 rightly refused is that it needs **no loader, no schema knowledge and no
parse** — it is a byte transform, and the binding stays a byte binding. Precedent is on its side:
normalize-before-hashing is already the house move for `content_signature` (defaults folded in,
`exclude_none`, the default build omitted).

Three things settled with it, because each is a way the fix could go wrong:

- **The stopping point is newlines, and it is chosen rather than inherited from the first symptom
  reported.** A BOM, trailing whitespace and a missing final newline are the obvious next steps, and
  each makes the binding more content-ish without making it content. Newlines are the one difference a
  *tool* introduces on a file the author did not edit — an editor's default, or Git itself through
  `core.autocrlf`; the others are things a human typed. If a real case arrives for one of them it is
  additive (P3) and gets argued then, on its own evidence.
- **The cost is a one-time invalidation of every `module_hash` in existence**, all sixteen closed
  reference examples included. That is a **soft** break: a stale attestation warns and is dropped, it
  never fails a build. But it is every module in the wild re-attesting once, and the corpus re-closing
  in the same commit as the change.
- **`manifest.inputs[]` must not follow it.** Those raw-byte hashes answer *are these the exact bytes*,
  which is a different question — so normalizing one and not the other is coherent, not an
  inconsistency to tidy up later.

**As built, and where the prediction was wrong.** The invalidation is **not** universal: a binding moves
only for a module that actually carries `\r\n` in one of the twelve authored files, so **7 of the 16
reference examples re-bound and 9 were byte-identical** — for those nine `close_module` took its
`held` branch and kept records, producer and nonce verbatim. Which way round the corpus was CRLF is the
part worth keeping: `csv.writer`'s default line terminator **is** `\r\n`, so the machine-written half of
the corpus ships CRLF and the edit an author really makes is *normalizing to LF*. Two modules lost four
attested check records each (`cyp2c9_warfarin_grch37`, `hboc_palb2`) — dropped rather than re-bound,
which is the rule working. Nothing else moved: `artifact.digest`, `content_signature`,
`source_signature` and `resolution_signature` are byte-identical across all sixteen, measured before and
after.

### It was sighted once before, from the other side

[DOGFOOD_0_6.md](probes/DOGFOOD_0_6.md)'s lane plan asked whether a round-tripped spec's attestation may read
as stale **to its own compiler** with nothing edited, since `reverse` normalizes cell formatting and
column order, and closed with *"Both are legitimate outcomes; neither is documented."* Same mechanism,
different trigger. The editor case is the one an author actually meets, which is what promoted the
question from an observation to a decision.

### What this is not

A change to **which files** the binding covers. That question — should the `authorship:` block be inside
it, given that appending a reviewer drops the attestation while moving no identity — was asked beside
this one and **answered the other way** on 2026-08-16: a review stamp is an attestation that zero
changes were needed, so un-closing is exactly correct and the reviewer re-closes. Recorded in
[MODULE_LIFECYCLE § 6.6](MODULE_LIFECYCLE.md#66-authorship-across-passes). Do not re-open it as a
by-product of building this.

## RM83 — a derived sidecar can only be refreshed by deleting it, which discards the overrides it exists to hold

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it) on 2026-08-28 — CLOSED, dissolved by RM124 rather than argued down, contingent on the overlay landing.** Both halves stop existing once derived tables are pure build products. The residue is `enrich --rederive` — a flag on the command that already derives, composing with RM128's transaction so a baseline exists for the diff — not the `--refresh` command with its three open questions. Move this entry to ROADMAP_HISTORY in the commit that lands the overlay, not before.

**Severity** medium-high · **Status** open — one shape named, tier undecided · **Owner** enricher
(probably; see below) · **Motivating case** every second pass; upstream-drift detection

### The two halves, which are one mechanism

**The refresh half.** Every derived sidecar is merge-not-clobber: an existing row is authoritative and a
re-run adds to it rather than replacing it. The rule exists because these tables are human-overridable
by design. Its consequence is the single most important operational fact about a second pass, and
[MODULE_LIFECYCLE § 6.3](MODULE_LIFECYCLE.md#63-what-must-be-deleted-and-what-deleting-costs) tabulates
it per table: **to re-derive a sidecar you delete it first, and deleting it discards every hand-curated
row in it along with the stale ones.** For `resolution.csv` those rows are real and not reproducible by
re-running — `reference_examples/cyp2c9_warfarin_grch37/` carries three hand-authored `source=manual`
rows — and for `literature.csv` the loss includes a curator's deliberate blank, which a merge cannot
distinguish from an absent value in the first place.

**The drift half.** Merge-not-clobber also means a re-run never re-asks about a row already recorded, so
a source that quietly **revised** an existing answer moves nothing at all: no `fetched_at`, no fact
signature, no digest. §5.1's canary — *content unchanged, a fact signature moved, therefore the world
moved* — is a real instrument and it cannot fire on its own. Detecting upstream drift **is** the
delete-and-re-derive: note the signature, delete the sidecar, re-derive, compare. No command performs
that sequence, and the sequence is the one that discards the overrides.

So they are not two items. The same missing operation causes both, and one shape closes both.

### The charter already knows about this, and discharged it exactly once

The 2026-08-12 amendment says a derived table that is both machine-written and human-overridable *wants
a mechanism rather than a convention*. RM45 discharged that for **one** table: `verification.json` is
"the one derived artifact whose human-overridability must not be a feature", which is why it is a JSON
document rather than a fifth fact CSV. Nothing discharges it for the six tables where overriding **is**
the intended feature. The second pass is where the convention fails, and `rm` is the whole of the
current mechanism.

### The shape

A `--refresh` that **re-asks and reports the difference rather than merging**. It re-puts the question
to the source for rows already recorded, and renders what changed instead of silently taking either
side — which keeps the standing rule that a pass reports and never repairs, and makes the canary
performable rather than merely readable.

### The open questions, which are why this is filed rather than built

- **Which tier owns it.** The enricher is what re-asks, so the refresh belongs there; but "tell me what
  moved between this sidecar and a freshly derived one" is a comparison over injected bytes, which is
  compiler-shaped. Splitting it wrongly gives two half-commands.
- **What it does with a difference.** Report only and leave the file untouched is the conservative
  answer and consistent with every other check; it also means the author is back to `rm` if they want
  the new value. A third file (a proposed table beside the current one) is the other shape and needs a
  name, a lifecycle and a rule about what compiles.
- **The blocking one: on most sidecars nothing records that a row was overridden.** `source` is an open
  provenance column that *can* say `manual` — `ResolutionRow`'s does, on real rows — but nothing sets it
  when a human edits a cell of an existing machine-written row in place, so that row still reads
  `source=gnomad`. "Re-derive the machine rows and keep the overrides" is therefore **not implementable
  today**: the tier cannot tell a curator's edit from what the source said last time. Either the refresh
  compares against the source and reports every difference without classifying it, or something has to
  start recording the edit — and that second option is a schema question with the usual cost, not a flag.

  **The second option now has a proposed shape and a motivating case: [RM124](#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it),
  filed 2026-08-20 from S60.** A consumer built the *first* option — a non-destructive
  capture/delete/re-derive/reapply wrapper — and it stops precisely where this paragraph says it must,
  on a subject present in both copies with a differing fact. Their answer is an authored overlay table
  that is never merged into the derived one, so the edit is recorded by construction. RM124 carries the
  four questions it leaves open; this item stays the *refresh operation*, which the overlay makes
  implementable rather than replaces.

### What it must not become

A pass that **applies** the newer value. Rewriting an authored or curator-set cell destroys the evidence
of the upstream change, which is the rule every cross-check in this tier already follows, and it is the
parked co-authoring item wearing a different name.

## RM84 — a module has no version identity on the discovery path, and the publisher is the half we own

**Severity** medium-high · **Status** **our half SHIPPED in the 0.6 PT2 batch (lane D, 2026-08-17)** —
`upload_module` writes `data/<name>/` and `data/<name>/v<version>/`. **The segment spelling is settled
and both asks are answered** ([S35](CONSUMER_SUGGESTIONS_HISTORY.md), 2026-08-17): `v<version>` verbatim
stays. Only the consumer's discovery half is open, and it is theirs, which is why this entry stays here.
*Previously:* our half taken into 0.6 PT2 on
2026-08-16 ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM84); before that, open — **joint with the
reference consumer, and their half is already agreed in writing** · **Owner** enricher
(`upload.upload_module`) + `just-dna-lite` discovery ·
**Motivating case** a republished module on the HuggingFace path

### What was observed

[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) traces two
acquisition paths with two entirely different notions of "updated", and neither delivers a notification.
The registry path at least has a per-version audit. The **discovery path has no version identity at
all**: no version in the path, no manifest fetch, no digest check. A republished module keeps the same
URL, so a cached copy shadows it, and the only invalidation is a purge keyed on the *consumer
application's own package version*. Stated plainly: on that path the identity used to detect "the module
changed" is a property of the reader, not of the module. A module republished with new science while the
app stays pinned is invisible; an app patch release with no module change purges everything.

**Half of that is ours.** `just_dna_enricher.upload.upload_module` writes the flat `data/<name>/` layout
— so this tier publishes the shape that cannot express a version, and no amount of consumer-side work
invents one.

### Why it is joint rather than ours alone

A pinning surface is a change to our publisher **and** to their discovery in the same breath: a version
segment nobody reads is dead bytes, and a reader looking for a segment nobody writes finds nothing.
[S34 § 4](CONSUMER_SUGGESTIONS.md) is the consumer's half, already stated: *"If the publisher grows a
version segment we will follow it in discovery; the `vN` fallback in our generic fsspec scan is already
the shape."* That is as close to a pre-agreement as a cross-repo item gets, and it makes this cheaper
than "wants agreeing" implied when it was first written down.

### What is undecided

*Was:* the layout itself — a `vN` segment, a digest segment, or a pointer file — and what happens to
every module already published flat, which is all of them. Whatever is chosen has to leave an
unversioned path working, because that is what is deployed.

**Settled on our side.** The layout is the dual write, decided in PROPOSAL_0_6_PT2 § RM84 and built in
lane D. Nothing already published moves, because the flat path keeps being written and keeps meaning
*latest*. The full behaviour, including the null-version fallback and the two-commit caveat, is
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

### The ask was put, and answered the next day — both questions closed

**Asked** in ENRICHER.md (RM27's shape: a finding about a downstream reader is an explicit ask, never an
implication), delivered there rather than into their tree because `just-dna-lite` carries no consumer
inbox. **Answered as [S35](CONSUMER_SUGGESTIONS_HISTORY.md) on 2026-08-17**, read off their code file
and line rather than recalled.

*(1)* **Their scan matches only `v`-plus-integer** — `^v(\d+)$`, compared with `int()`, so `v1.0.0` does
not match and `v10` would sort under `v9`. **The half that actually decides it is their correction, not
the regex:** that fallback lives only in `_discover_fsspec_source`, the generic github/http/s3 branch.
HuggingFace has its own branch with **no version fallback at all** — so on the path this item is *about*,
no spelling is read today and the segment cannot be chosen to suit one. Their words: S34 § 4's *"the `vN`
fallback in our generic fsspec scan is already the shape"* was accurate about the shape and quoted about
a branch that does not serve HF, and they call that their error rather than a misreading here.
**So `v<version>` verbatim stays** — a bare major segment would still collide two patch releases at one
path, and would buy nothing since the code that would read it is not on this path.

*(2)* **No, and by construction rather than by luck.** Both discovery branches call `fs.ls` at exactly
one level and never `fs.find`, a `**` glob or a recursive listing, and their probe asks `fs.exists` on
named files rather than listing the directory it is probing — so a nested `data/<name>/v<version>/` is
never enumerated and never probed. Verified in their tree by search: no `fs.find`, `recursive=True`,
`maxdepth` or `snapshot_download` against a module path anywhere. The one part of this change that could
have regressed a consumer who never adopts it, and it does not.

**One consequence recorded rather than fixed**, raised by them as a consequence and not an objection:
the dual write doubles the collection's bytes and nothing prunes `data/<name>/v<version>/`, so the repo
grows one full artifact set per release forever. It does not affect discovery. Retention is the
collection owner's decision, not the publisher's; noted in
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

**What is left here is theirs and unscheduled:** teach `_discover_hf_source` a versioned fallback, and
replace the regex and `int()` with `just_dna_format.identity.Version`, which already gives them parsing
and ordering. Nothing is broken meanwhile — the flat path resolves and keeps meaning *latest* — so their
`read_module_provenance` states `version: None` for every HF-discovered module, which their report
renders as *Not stated*.

**Confirmed by exhaustive search to have had no `Sn` and no `RMn`** before this entry, which is why it
is filed rather than cross-referenced.

### Two items building this surfaced, filed 2026-08-17 rather than folded in

Both were found by writing the code, not by planning it, and neither is a defect in what shipped —
recorded here because this entry is where a reader meets the publisher.

- **[RM88](ROADMAP_HISTORY.md#rm88--republishing-without-bumping-version-overwrites-a-versioned-path-with-different-bytes)** — the versioned path cannot notice that the version has *not* moved, so a republish
  without a `version:` bump overwrites it with different bytes. Refusing needs a remote read *and* an
  undecided policy (warn / refuse / `--force`), which is why it is an item and not a fix.
- **[RM89](ROADMAP_HISTORY.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all)** —
  `_REQUIRED` still demanded all three SNP-core parquets, so a table-only module could not be published
  at all: seven of the sixteen reference examples, measured. Its open question — what the discovery path
  actually needs open — went to the same team as the two asks above rather than as a third message, and
  **came back with them in S35, so it shipped on 2026-08-17**. Answering it found the larger half:
  `_ALLOW_PATTERNS` carried no 0.4 family and no derived-fact table either, so eight *more* examples
  published a manifest attesting parquets that were never uploaded.

## RM85 — the origin of a module predicts the shape of its second pass, and nothing records it

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm85--the-origin-of-a-module-predicts-the-shape-of-its-second-pass-and-nothing-records-it) on 2026-08-28 — BUILDS in 0.7** as the enricher check comparing `SourceRow.dataset` against the source's current release. Tri-state: unreachable is `unchecked`, never up-to-date.

**Severity** low-medium · **Status** open — the fact is nearly recorded already; nothing acts on it ·
**Owner** format (a column) or enricher (a report) — undecided, and that is the item · **Motivating
case** a source-drafted panel two ClinVar releases later

### The observation

A module drafted from a source (ClinVar, CPIC, ClinPGx) inherits that source's release cadence and will
need a **source-refresh pass**. A module built from one paper the author read inherits the *literature's*
cadence and needs an **evidence pass** when the preprint is published or a replication lands. The origin
picks the shape of the second pass, and
[MODULE_LIFECYCLE § 7](MODULE_LIFECYCLE.md#7-what-no-stage-owns) records the consequence: **nothing tells
an author their source has moved on.** The tautology skip reads the release the module was drafted from
and `withdraw_stale_dataset` handles a module that ends up mixing two, but neither answers *"ClinVar has
published since you drafted this"*. Today the author has to know.

`SourceRow.dataset` records the release, so the fact is nearly there. What is missing is anything that
acts on it.

### Why the obvious repair is not obvious

The tempting shape is a column saying what this module was made from and what would age it — and the
identical proposal is already refused one table over, in
[RM71](ROADMAP_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file):
a comment column would be *"a statement about a snapshot release, and a re-draft from a newer one leaves
it naming the old alleles — exactly the staleness `licensing.withdraw_stale_dataset` had to be built for
on `dataset`, on a column where nothing could notice."* Same shape one table over. A column that states
what `dataset` already states, and rots where `dataset` is maintained, is the wrong half of the answer.

So the live candidates are the ones that read rather than write:

- **A check that compares `SourceRow.dataset` against the source's current release** and reports the
  gap. Needs the network, so it is an enricher check, and it is the cheapest thing that answers the
  actual question. It is also RM83's neighbour — the same "has the world moved" question, asked about
  the release label instead of about the rows.
- **A publish-time or catalog-side signal**, which puts the notice where a reader is rather than where
  an author is, and is out of these packages' scope.
- **Nothing, deliberately** — the author knows their sources. This is the status quo, and it is only
  defensible while modules have one author who remembers; it fails exactly when a module outlives its
  curator, which is the case the whole lifecycle document was written for.

**Confirmed to have no `Sn` and no `RMn`** of its own before this entry.

## RM86 — a review pass is legal at the gate, refused by the pre-flight, and invisible once published

**Severity** medium-high · **Status** ✅ **CLOSED 2026-08-20** — all three findings answered by
`just-dna-registry`, two of them by code, and the question that was ours is decided and written into
[MODULE_LIFECYCLE § 6.6](MODULE_LIFECYCLE.md#66-authorship-across-passes). Filed with them on 2026-08-16
as their S10, S11 and S12, one item per finding; all three are answered and archived in their history ·
**Owner** `just-dna-registry`, with a documentation half here — **that half is now done** · **Found by**
reading the registry tree on 2026-08-16, while settling whether a review pass costing the attestation is
a defect (it is not) · **Closed by** re-reading that tree at **registry 0.18.3** on 2026-08-20, prompted
by [S46](CONSUMER_SUGGESTIONS_HISTORY.md) from `just-module-creator`, who measured the recognition half
from outside and reported §6.6 as stale

**How it closed, per finding.** The dispositions are not uniform, which is the reason this entry keeps
all three rather than collapsing to one line:

- **The pre-flight — fixed in registry 0.16.0.** `published_elsewhere` is a new field carrying the
  subset of content hits under a *different* `(namespace, name)`, and `would_publish_module_level`
  quantifies over it, so the verdict now matches the gate; `published_as` still lists the same-module
  hit, because a review pass wants to see it. The namespace is threaded through both pre-flight routes.
  Verified first-hand at `services/enrich.py` — the carve-out and the comment naming this exact defect.
- **The closure — fixed across 0.16.0 and 0.17.** `verification.json` is in `RECOGNIZED_SPEC_FILES`
  (0.16.0), so a rebuild carries it forward; it is in that registry's `DERIVED_FILES` and
  `manifest.derived` (0.17), so `download(include_inputs=True, layout="split")` returns it at
  `derived/verification.json`; and `manifest.verification` is projected onto the module-detail response,
  with `closed` re-bound by that server's own compile. Still **out of `SIGNATURE_INPUTS`**, which is the
  property that made recognising an unread file safe and is asserted by their tests. The version-lag
  clause is also dead: they now require `just-dna-format>=0.6.1` / `just-dna-compiler>=0.6.1`, not 0.5.4.
- **`authorship` unsurfaced — answered as policy, not repaired, and correctly.** It stays payload: a
  server that compiles what it publishes must not render the author's statement about their own reviewer
  beside claims of its own. Read it from the manifest, where it is plainly the manifest's word.

**The question that was ours is answered too**, by their reply to S12, and it is now §6.6's advice
verbatim: a `reviews` row by default; an `authorship` entry when the record has to travel inside the
module or be signed; both when both matter. The version-bump path is legal and costs a version number
and nothing else.

**Where the report lives:** `../just-dna-registry/docs/CONSUMER_SUGGESTIONS_HISTORY.md` (the tree is also
reachable as `just-dna-marketplace`, a symlink to it, which is the name this entry used to give), under
*Field notes from just-dna-format — the second pass*, as their S10–S12 with a reply on each. The original
filing carried the standing caveat that **0.6 was not published and not finished**, so the half of S11
needing a reader of ours was explicitly filed as *do not build against this yet*; 0.6 has since been cut
and that caveat has expired. This entry is the tracking record; their file is the authoritative report,
and the citations below were each verified in their tree first-hand rather than taken second-hand.

**Everything below this line is the 2026-08-16 finding as first written**, kept because the reasoning is
what a publisher should still hold and because two of the three sections describe behaviour that a
registry deployment older than 0.16.0 still has. Read it against the dispositions above.

### Why this was looked at

The decision that a review stamp is an attestation of zero changes settles the *format* side and
immediately raises the downstream one: a review pass publishes a version whose `content_signature`
**and** `artifact.digest` are byte-identical to its predecessor, differing only in `authorship` and
`verification.json`, neither of which is in either identity. Whether a catalog can even represent that
is not something this repository can assert from its own rules, so the registry was read. RM27's shape
applies — a finding about a downstream enforcer is filed as an **explicit ask**, not as an implication.

### What the publish actually does

**It succeeds, and the gate is right.** The duplicate-content check is keyed on `content_signature`
alone, enforced in the service layer before enrich/compile, and the same-module carve-out is real code
rather than prose — it compares `(namespace, name)` and is pinned by a test. Nothing else can bite:
there is no unique index on the digest or the content hash, and storage keys are
`namespace/name/version`, deliberately **not** content-addressed, with a comment giving this exact
reason. `latest` advances normally. `find-by-hash` returns both versions in a deterministic list, which
is the one place the shared digest is visible and is by design.

So the §6.6 sentence this document has carried — that the gate permits identical content within one
module — is now **confirmed against code** rather than believed.

### The three things that are wrong

- **The pre-flight disagrees with the gate on precisely this case.** `validation_report` computes
  `published_as` from the raw content lookup with **no same-module carve-out**, and the namespace is
  never threaded into the worker — so `validate` and `check` report the predecessor and answer
  `would_publish: false` for a publish that then succeeds. The registry's own test file states the
  standard this breaks (*"a pre-check that disagreed with the gate would be worse than none, because it
  would give a publisher confidence before taking it away"*), and its coverage tests only the
  different-name direction. **This is the one with a blast radius**: an automated publisher branching on
  the field the API documentation says to branch on refuses a legal publish, and a review pass is the
  commonest way to reach it.
- **The closure reaches nothing.** `verification.json` is uploaded by the client and copied into
  storage, and then read by no code path: it is not in `RECOGNIZED_SPEC_FILES`, so every server-side
  spec rebuild (`revalidate`, `upgrade`) drops it, and it is outside the served allow-list so no
  endpoint hands it back. `provenance.json`, one file over, *is* recognised and *is* served — so this
  is an omission rather than a policy. Compounded but not caused by a version lag: the registry pins
  **0.5.4**, where `manifest.verification` does not exist and `close_module` does not either, and the
  server regenerates `manifest.json` from its own compile — so today the closure cannot appear even in
  principle. The recognition gap outlives that upgrade; the pin does not.
- **The review is served but unsurfaced.** `authorship` does reach the published manifest and is
  readable two ways, but no projected field, column, filter or card element carries it, so seeing who
  reviewed a module means parsing the manifest — and only for the latest version without a second
  request. The registry's own schema states the policy this follows (*"a column is for something you
  filter or sort by; the rest is payload"*), naming `authorship` as payload.

### The question that is ours, not theirs

The registry already has a **`reviews` table** with a verdict tier and a `highlighted` flag, projected
onto module cards, costing no version number at all. This document has been saying that a pure review
is *"a real version bump without pretending the data changed"* — which is true of the format and may be
the wrong instrument on that catalog. The two mechanisms record different things (an `authorship` entry
travels **inside the module**, survives a download and a hand-off on disk, and is signed by the same
key; a registry review lives in the catalog and does not travel), so this is not a case of one being
redundant. What is undecided is what an author should be told to do, and whether both should be
recorded — and it is a **documentation** decision here, not a schema one: nothing in the format changes
either way.

### What this is not

A reason to re-open the binding question. Un-closing on a review is correct
([MODULE_LIFECYCLE § 6.2](MODULE_LIFECYCLE.md#62-the-consequence-matrix--measured-not-derived)); every
finding here is about what a catalog does with the result, and none of them would be fixed by keeping a
closure the reviewer did not make.

**What would unblock it** *(as written on 2026-08-16; all three happened)*: the pre-flight carve-out and
the `verification.json` recognition are theirs and are small; the review-versus-version guidance is ours
and needs deciding once, wherever an author is told how to run a review pass.

## RM87 — an expanded row is indistinguishable from an authored one in the artifact

**Severity** medium-high (a consumer produced 3,762 false findings on it; caught before rendering) ·
**Status** **SHIPPED in 0.6 PT2 (lane B)** — `VariantRow.locus_index` **+** `locus_count`, both
`stamped_identity_field` (`exclude=True`, so no `content_signature` moved anywhere), stamped at the
expansion loop in `resolution.py` **and** at its twin in the deprecated `resolver.resolve_variants`
(digest parity between the two paths is a guarantee, and two round-trip tests caught the omission);
`locus_count` defaults to **1**; `_build_weights` materializes both as `UInt32`; reverse prefers the
stored column over its encounter-order recompute and keeps the recompute for a pre-0.6 artifact.
`_freeze_identity` overwrites an authored cell of either name, the way it already does for
`variant_key`. Measured over the sixteen reference examples: `artifact.digest` moved on the **nine**
carrying a `variants.csv` — hence a `weights.parquet` — and on nothing else; `content_signature`,
`sources.signature`, `verification.signature` and `compilation.resolution_signature` all held on all
sixteen. (The proposal predicted twelve and four; the real split is nine and seven, which is a
miscount in the prediction and not a behaviour difference.)
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM87 is the design record · **Owner** format (schema) +
compiler (materializer, reverse) · **Motivating case** S33 in
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), from just-dna-lite

A one-to-many rsID is paired with every locus it resolves to, so K authored genotypes at that key
become K×N rows in `weights.parquet` and only the member whose alleles can carry a given genotype can
match it. The others are ordinary well-formed rows — real coordinate, real reference allele, the
module's own conclusion — and **nothing on the row says so**. `locus_index` lives in `resolution.csv`,
which SCHEMAS.md states is a lookup rather than a consumer contract and which gets no parquet by
design; the artifact carries `variant_key` and `authored_ident` and neither separates the members.

The reporting consumer that found this measured 2,579 rows into one genome's `pathogenic` section and
1,183 into `cancer`, each stating that a subject carried a pathogenic variant they do not have, all
from `TA/TA`-beside-`ref=TA` reference homozygotes at ClinVar duplication/deletion pairs. Their
mitigation — withhold any locus the artifact spells with more than one `ref` — took those to zero and
is **partial by their own account**, because same-`ref` expansions are invisible to it. They are real
here: `--keep-par-twin` records a pseudoautosomal locus on X and Y with identical alleles, which is
what `reference_examples/shox_par1/` was built from (nine of ten SHOX variants, 20 rows for 10
findings — RM32), and a paralogous rsID can name two positions carrying the same reference base.

**0.6 shipped the artifact-level half** — `manifest.compilation.expanded_keys`/`expanded_rows`, plus
the read-side contract in SCHEMAS § *the consumer join contract* and one expansion warning per rsID
carrying the true row total. Those answer *does this artifact contain expansion rows*. They do not
answer *is this row one*, which is the question a row-by-row reader actually has.

### The premise this item exists to correct

S33 declines to ask for the parquet column: *"the 0.5 digest window is closed and a new column moves
every module's digest, so that is a 1.0 conversation if it is one at all."* **That is wrong under our
own charter, and the mistake is ours for not having said so plainly enough.** Principle 3: *"A new
optional column, or a new optional table, is additive and lands in a minor: the authored identity —
`content_signature` and the per-input hashes — is unchanged, and only a recompile's `artifact.digest`
moves."* Principle 4 scopes byte-reproducibility to a fixed `compiler_version` in the first place, so a
digest that moves between compiler versions is the documented behaviour rather than a cost. And the
0.6 cost amendment prices this exact object at the bottom of its scale: *"Parquet columns —
approximately free. Materialized and derived; no human ever types one, and an author cannot see one. A
stamped, compiler-managed column is the cheapest thing this format can add."*

So the thing the reporter says they actually want is both **legal in a minor** and the cheapest class
of change the charter recognises. It is filed rather than shipped in the same pass for one reason
only, and it is not legality.

### The open design question — `locus_index` alone does not answer it

`locus_index` is what S33 names, and taken by itself it is under-determined: it is `0` on every
non-expanded row *and* on the first member of every expansion, so a reader holding one row cannot tell
the two apart. Making it answerable needs one of:

- **`locus_index` + `locus_count`** — index within the key's expansion, and how many members that key
  has. `locus_count > 1` is then the row-level predicate, self-sufficient and mirroring what
  `resolution.csv` already records. Two columns for one fact, which is the cost.
- **`locus_count` alone** — the predicate without the ordinal. Cheaper, and it loses the ability to
  line a weights row up with its `resolution.csv` row, which is the other thing an index buys.
- **A single boolean `expanded`** — cheapest to read, and it forecloses both of the above under
  Principle 5's one-way-door rule: a `bool` cannot later carry an ordinal without a retype, which is
  major-only.

None of these is obviously right, the name is permanent within the major (P5), and picking one during
a triage pass is exactly the kind of decision this repository files instead of guessing. Whichever
lands, it is compiler-managed and stamped, so it needs the three touch points — model, compile-side
row dict plus polars schema, and the reverse `fieldnames`/`_scalar_cell` pair — plus a round-trip test:
reverse currently *recomputes* `locus_index` by encounter order over the weights rows (which works only
because those rows are sorted on it), and a stored column would have to be shown either to agree with
that or to supersede it.

**What it does not change.** The expansion stays. Filtering the non-matching member is refused for the
two reasons COMPILER.md § Resolution already gives — a source's allele list is incomplete at least as
often as a module is wrong, and dropping rows changes what `reverse_module` reads back, which
Principle 7 forbids. The reporter argued the same case against their own first candidate, and they are
right.

## RM124 — an author's correction to a derived table has nowhere to live except inside it

**Decided in [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it) on 2026-08-28 — BUILDS in 0.7, and it is the round's keystone.** `overrides.csv`, keyed `(table, subject, member, field)`; operations `update`/`insert`/`suppress`, with the wildcard refused for `suppress` alone; applied at load and merge-not-clobber dropped for the six covered tables; P7 held by idempotency, so no `previous_value` column. Question 2 answered as a dated succession — see **RM135**.

**Severity** medium-high · **Status** open — a shape proposed by a consumer who built the workaround,
tier argued, four questions unsettled · **Owner** format + compiler · **Motivating case**
S60 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md) · **Answers the blocking sub-question of
[RM83](#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold)**

### What RM83 was blocked on, and what this is

RM83 named a missing operation — a `--refresh` that re-asks and reports — and named the thing that made
half of it unbuildable: *on most sidecars nothing records that a row was overridden*, so "re-derive the
machine rows and keep the overrides" cannot be implemented, because the tier cannot tell a curator's
edit from what the source said last time. It offered two exits: compare and report every difference
without classifying it, or **something has to start recording the edit**, which it called a schema
question with the usual cost.

This is that second exit, proposed by a consumer who built the first one and hit its ceiling. They wrote
a non-destructive wrapper around the delete-and-re-derive sequence — capture, verify the capture, delete,
re-derive, classify, reapply what is provably the author's — and it stops exactly where RM83 predicted:
when a subject is present in both copies with a differing fact, the fresh row is *either* a cell the
author edited *or* a revision the source published, and with two data points there is no third to
separate them. Their tool reports and refuses to resolve, which is the honest outcome and is a symptom.

### The proposed shape

A recognized **authored overlay table** that lies on top of a derived one and is never merged into it:
one row per `(table, subject, field)` carrying the authored value, the reason in prose, who decided, and
when. The derived files become pure build products — `derived = f(source, overlay)` — and four things
follow, three of which are theirs and all of which check out:

- nothing is hand-edited, so re-derivation is non-destructive **by construction** rather than by a
  wrapper being careful;
- a difference between a fresh row and a previous one means the source revised, full stop; the
  three-explanations ambiguity stops existing rather than being reported;
- the reason for a correction travels with the module instead of living in someone's memory;
- **the terminal state becomes detectable and it is free** — an overlay row that no longer changes
  anything means the source caught up, which is evidence that an authored judgement was later vindicated
  and is available nowhere else in this format. That is the observation to keep whatever else changes;
  it is the same shape as S52's, recorded there for the same reason.

### The charter, first-hand

Legal, and specifically invited. A new optional authored table is additive and minor-legal (P3), it
demotes nothing (P8), it is data and not code (P1), and it is authored input rather than a fetch (P2) —
a compiler reading it is doing what it already does with every other authored table. Under the 2026-08-12
cost amendment it is the **full-cost** layer, a human writes it; but that same amendment is what names
this class in the first place — *a derived table that is both machine-written and human-overridable can
be edited into a state that is not merely stale but is a false claim, and that wants a mechanism rather
than a convention.* RM45 discharged that for exactly one table by making `verification.json` unwritable
by hand. Nothing discharges it for the **seven** where overriding **is** the intended feature —
enumerated in [PROPOSAL_0_7 § RM124](proposals/PROPOSAL_0_7.md#whether-merge-not-clobber-survives-it-does-not-and-what-replaces-it),
which corrected this count on 2026-08-28. It said *six* here and there, and listed them in neither.

### Four questions, and none of them is the tier

**Their tier argument is accepted and is not an open question.** An overlay is authored input, not a
repair, so report-never-repair is not at stake; and if each downstream tool applies its own overlay, two
consumers compiling one spec directory disagree about what the module says and the artifact stops being a
function of the spec. That settles *where*, and leaves:

1. **`(table, subject, field)` is not enough, and the table it fails on is their flagship case.** RM115
   shipped the merge keys they were blocked on, and it published something their derivation could not
   reach: `resolution.csv`'s key is `rule="subject"`, not a uniqueness constraint. One `variant_key`
   legitimately resolves onto several loci, `locus_index` orders them, and a pass replaces the group
   whole — so a subject names a *group of rows*, and an overlay row keyed on it cannot say which locus it
   corrects. Their `source="manual"` rows are in exactly that table. Either the subject gains a
   within-group discriminator for the one table that needs one, or overlays on `resolution.csv` are
   group-scoped and say so. `gene_validity.csv` needs the same care in a different direction — its key
   has two levels (`assertion_id` else the gene's grain), so an overlay written against one level is
   silent about rows keyed by the other.
2. **P5: this and `provenance.json` must not become two records of one concept.** S52 shipped
   `ProvenanceItem.outranks: dict[str, str]` — `{column: why}`, an authored cell outranking a source,
   with prose. The overlay is a corrected cell in a *derived* table, with prose. Their split is clean as
   stated (authored vs derived) and it is exactly the kind of line that erodes: the first author who
   wants to explain why their `clin_sig` beats ClinVar *and* why their `chrom` beats Ensembl has to learn
   which of two files each belongs in. Decide whether one record with a table column serves both, or
   whether the two are genuinely different axes, **before** either grows a second field.
3. **What P7 makes of a build product.** If the compiler applies the overlay, `reverse_module` has to
   reproduce a spec directory that recompiles byte-identically — which means deciding whether it re-emits
   the *pre-overlay* derived table plus the overlay, or the post-overlay table with the overlay beside it
   (in which case the overlay applies twice and the fixed point has to be checked, not assumed).
   `resolution_signature` and the fact signatures are over the derived tables as they stand today, so
   which of the two they cover is the same question wearing an identity.
4. **Whether merge-not-clobber survives.** The real prize is that `derived = f(source, overlay)` lets the
   rule be dropped for the tables the overlay covers, which removes the operational fact RM83 opens with.
   The real cost is that every pass writes through it, and dropping it changes what a re-run does to every
   module already published. That is the part that makes this 0.7 rather than a minor.

### The dependency that is real but routine

The registry rebuilds a spec directory from its own `RECOGNIZED_SPEC_FILES`, and a name missing there is
a file dropped on the next re-publish — which is how `licensing.csv` was lost before their 0.16.2. That
tuple is built from `SPEC_DATA_FILES`, a **hand-kept mirror** of our table constants, so an overlay needs
one entry added there. It is the same one-line change every new table kind already needs, and their own
comment records the scar; it is a coordination step, not a design blocker.

