# Roadmap — 0.7 and later minors

**What this file is.** Items that are legal in a minor and were **not** taken into 0.6, each with the
reason it waits. Split out of [ROADMAP.md](ROADMAP.md) on 2026-08-13 so that the active roadmap
describes the line being built and a deferral is filed against the release that will decide it, rather
than accumulating in one document nobody can read as a plan.

Everything here is **additive under Principles 3/4/8** — a new optional column or table — so none of it
is waiting on a version. Each waits on a design question, a corpus, or a consumer.

Indexed in [RM_TOC.md](RM_TOC.md). The 0.6 decisions that touched these items are in
[PROPOSAL_0_6.md](PROPOSAL_0_6.md).

---

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

**What would unpark it:** a real consumer. See [PROPOSAL_0_5.md](PROPOSAL_0_5.md) D1.

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
[PROPOSAL_0_5.md § G3](PROPOSAL_0_5.md): a new **optional** table, a predicate that **never blocks**, a
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

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.

## RM55 — copy number and repeat count are not whole numbers (the usable fix)

**Severity** high · **Status** 0.6 warns loudly; **the fix is here**; the removal is 1.0 · **Owner**
format (schema) + compiler

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
