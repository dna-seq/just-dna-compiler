# Roadmap — 0.8 and later minors

**What this file is.** Items that are legal in a minor and were **not** taken into 0.7, each with the
reason it waits. It is the direct successor of `ROADMAP_0_7.md`, which was split out of
[ROADMAP.md](ROADMAP.md) on 2026-08-13 so that the active roadmap describes the line being built and a
deferral is filed against the release that will decide it, rather than accumulating in one document
nobody can read as a plan.

**Why it was renamed rather than kept.** 0.7 was built on 2026-08-28 and the file's name had stopped
being true: it read as the plan for a release that is finished, so an item in it looked shipped-or-late
rather than waiting. On 2026-08-31 the round it recorded closed —
[history/ROADMAP_0_7.md](history/ROADMAP_0_7.md) keeps that record, entries and all, including the
five taken back into 0.6 and the two that built in 0.7 — and everything still waiting moved here.
**Nothing about any item below changed in the move**; the file name did. Expect the same succession at
the next minor: the deferral file is named for the release that will decide its contents, so a cut
closes one and opens the next.

Everything here is **additive under Principles 3/4/8** — a new optional column or table — so none of it
is waiting on a version. Each waits on a design question, a corpus, or a consumer. An item waiting on a
**version** belongs in [ROADMAP_1_0.md](ROADMAP_1_0.md) instead, and RM69 moved there on 2026-08-27 for
exactly that reason: filing by what a fix *costs* rather than by what decides it is how an item becomes
unreachable from either plan. **RM68 stays**, and the two look alike enough to be worth separating: its
governing exit is *a real author with a non-GRCh38 module saying which outcome they wanted*, and a
demand exit keeps an item here where a version exit does not.

**Two of these are not waiting on us at all.** RM84's own half shipped in the 0.6 PT2 batch and only
the consumer's discovery half is open; RM67 is **not work** — a documented divergence, numbered so it
stays findable and does not get re-probed. Both are here so that a reader meets the reasoning instead
of re-deriving it.

Indexed in [RM_TOC.md](RM_TOC.md), which is the complete list and the place to look an item up. The 0.6
decisions that touched these items are in [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md) and
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md); the 0.7 round that emptied the rest is
[PROPOSAL_0_7.md](proposals/PROPOSAL_0_7.md).

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

The findings from [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) whose obvious repair is itself a
design decision — the round filed five, and two have since left: RM69 for
[ROADMAP_1_0.md](ROADMAP_1_0.md) (see the header), and **RM70 shipped in 0.7**, its entry now in
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md). The three below are what remains. No fixed count is stated
here on purpose: one goes wrong silently the next time an item leaves, and this section has already
lost two. The ledger classes each **surface** rather than **fix**, which is this repo's standing
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

# Vocabulary residue from the 0.7 consumer round

## RM150 — `direction`'s `unknown` still conflates *nobody asked* with *the sources disagree*

**Severity** low-medium · **Status** open — **a minor, release undecided; filed 2026-08-31 by the
maintainer, reviewing RM148's answer** · **Owner** format (schema) · **Motivating case**
[S83](CONSUMER_SUGGESTIONS_HISTORY.md) (just-module-creator), the residue RM148 did not take

**RM148 answered two of the three shades and this is the third.** The reporter said `direction`'s
`unknown` covers *no evidence*, *conflicting evidence*, and *evidence that does not exclude either
direction*. RM148 removed the last by **reassignment**: an unestablished sign is still a sign, so that
state is the pair `direction=<sign>` + `stat_significance=not_significant`, and a member for it would
have been a second spelling. That reasoning holds and is not reopened.

It does not reach the first two. `unknown` still means both *not assessed* and *the sources conflict*,
and RM148's own description says so out loud — *"not assessed, or the sources conflict"* — while adding
nothing that tells a consumer which. The reply to S83 asserted the two are "one thing (nothing to
record)"; that was our assertion, not the reporter's concession, and it is the weakest sentence in the
answer. **They are not one thing: one is an absence and the other is a finding.**

### The decision

**Extend the vocabulary, keeping `unknown` for *no evidence*.** Both halves of that are load-bearing:

- **`unknown` keeps the original meaning**, because that is what every published module already means
  by it. Re-pointing a shipped member at the narrower sense would silently change what existing data
  says — a retype in everything but name, and P3 territory. Adding beside it is minor-legal.
- **The new member is `contested`**, which is this tier's established word for the same idea one table
  over: `clin_sig_concordance.csv` is *one row per contested subject*, and
  `clin_sig_concordance_contested` is an existing warning code. Coining a synonym for a concept the
  workspace already names is the failure `@one-normalizer-two-spellings` records.

### The trap this must not walk into, and it is silent

`trimmed_state()` projects a `direction` back into the legacy `state` set through
`_DIRECTION_TO_STATE.get(direction, "neutral")` — **a `.get` with a default, not a lookup that
raises**. Verified: `trimmed_state("contested")` returns `neutral` today, before any member exists. So
adding `contested` to `VALID_DIRECTIONS` and stopping there produces a module whose `upgraded()`
silently emits `state=neutral` for a contested row, with nothing failing anywhere.

That makes the map the *first* edit rather than a follow-up, and it makes the guard a
registry-iterating equality: **every member of `VALID_DIRECTIONS` has an explicit entry in
`_DIRECTION_TO_STATE`**, walked, so the next member added cannot inherit the default. A test asserting
`trimmed_state("contested") == "neutral"` would pass today and prove nothing — the assertion has to be
about the map's coverage, not about its output.

`contested` collapsing to `state=neutral` is nonetheless the right projection once it is *explicit*:
the legacy set has no member for it, and `neutral` is what `unknown` already collapses to.

### What else it touches

- **`P7` round trip** — `upgraded()` must stay idempotent with the new member, and `needs_upgrade`
  must not start reporting every existing `unknown` row as drifted. The reassignment direction matters:
  nothing re-points, so nothing drifts.
- **`direction_from_state`** — unchanged. No legacy `state` value means *contested*, so the reverse
  map gains nothing; that asymmetry is correct and worth a comment, since the two maps look like they
  should mirror.
- **The field description** — RM148's sentence bounds `unknown` as *"not assessed, or the sources
  conflict"* and must lose the second half when this lands, or the two members overlap in print.
- **Consumers** — a wire vocabulary gains a member, which is the cost that made RM148 refuse one for
  the third shade. It is paid here because this shade is *not* expressible as a pair: no combination of
  `direction` + `stat_significance` says "two sources disagree about the sign".

### Repairs rejected

- **Two new members, retiring `unknown`.** The maintainer offered this as the alternative. It is a
  removal in effect — every published row carrying `unknown` would be speaking a retired member — and
  removals are major-only under P3. The one-new-member form gets the same expressiveness at minor cost.
- **Leaving it in RM148.** Answered-with-a-caveat is how a residue stops being findable. RM148 is
  correct about what it closed and this is a separate claim.
- **A `direction_provenance` column.** A second column to say why a cell is empty, which is the shape
  P5 exists to refuse — the member *is* the distinction.

# Specification form — the ambiguity the prose costs

## RM149 — expected behaviour lives in prose, and the prose is where two readers split

**Severity** medium · **Status** open — **a minor, release undecided; asked by the maintainer
2026-08-31** · **Owner** format + compiler (the test corpus) · **Found by** running the consumer loop

**The ask, verbatim in intent:** express our described scenarios as Gherkin, because the freeform prose
in expected-behaviour descriptions is producing ambiguities faster than it resolves them.

**The evidence for it is this repo's own recent record**, which is what makes this an item rather than a
preference. Three consumer reports in one week were **two readers splitting on one sentence**, none of
them a code defect:

- **S80** — `state`'s six members printed as peers; an agent chose a retired one honestly.
- **S83** — two runs of a byte-identical prompt wrote `risk` and `unknown` for one variant on one body
  of evidence, both green, both defensible against the field description.
- **S79** — a warning's text read as *your declaration is unsupported* when it meant *not universal*.

Each was answered by writing a better sentence. That is three fixes to prose in a week, and the pattern
says the next one is already in flight somewhere.

### What is actually being asked

Not a testing framework — the suite is not the problem, and a `pytest`-to-`behave` migration would be
motion rather than progress. The gap is that a **scenario** — *given a module with a partial
`resolution.csv`, when `validate --strict` runs, then it refuses with the compile's own error* — exists
today as a docstring, a test name, and a paragraph in `COMPILER.md`, and those three can drift from
each other and from the code. A structured form is one statement, and the natural home is a
`.feature`-shaped corpus each side is derived from or checked against.

### Open questions this needs decided before it can be built

- **What is the source of truth.** Gherkin generated *from* the tests is documentation that cannot
  drift; tests generated *from* Gherkin makes the feature files the contract and every existing test a
  migration. These are opposite projects with the same output, and the ask does not say which.
- **What is in scope.** Every check the compiler runs is ~140 warning codes plus a mode ladder. The
  release-gate scenarios, the tri-state outcomes and the parity rules are the parts where ambiguity has
  actually cost something; the round-trip fixed points are already pinned by assertion and would gain
  nothing from prose.
- **Where it lives.** A `features/` tree at the root, per-package, or inside `docs/`. That decides
  whether it ships to consumers — and if it does, it becomes a published surface under P3, which is a
  much larger commitment than an internal one.
- **What it costs the next contributor.** A second dialect to learn beside the docstring convention
  this repo already leans on heavily, and every new check owing a `.feature` clause. That is the P9
  question one layer up: this is a *maintenance* surface, not an authored one, and it is not free.

### Why it is filed rather than started

The three reports above were each fixed by naming what the rule is, and the fix was one string. A
scenario corpus is worth building when the *cost of ambiguity* exceeds the cost of the corpus, and the
measurement that would show that has not been taken — this entry is where it goes when it is. What is
not in doubt is the direction: the recurring failure is real and repeatedly measured, and it is filed
here so the next instance lands against a number rather than as a fourth anecdote.

**Not to be confused with** the `/create-module` skill's authoring guidance, which is a different
document for a different reader and stays prose. This is about *our* stated behaviour, not an author's.

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
