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

**The message changed on 2026-08-14; the decision did not.** Dogfooding a duplicated CYP2D6 — the
spec's own polyploid example — refused the call with a bare restatement of the grammar, so a deliberate
limit read as a syntax error, while every other deliberate refusal in this schema names its own limit
in-line. The arity refusals now carry that sentence: two alleles is a decision, VCF 4.4 §7.2 permits
more, and nothing is queued against it. Recorded as D3-2 in
[DOGFOOD_0_6_FINDINGS.md](DOGFOOD_0_6_FINDINGS.md).

---

# The 0.6 dogfooding items deferred out of the fix round

Five findings from [DOGFOOD_0_6_FINDINGS.md](DOGFOOD_0_6_FINDINGS.md) whose obvious repair is itself a
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

## RM69 — `resolution_signature` is not a round-trip invariant when the positional fill is skipped

**Severity** low · **Status** deferred, **blocked on RM15** — a documented limit of Principle 7, not a
breach of it · **Owner** compiler · **Found by** dogfooding on 2026-08-13, the D6 corpus sweep

### What was observed

The D6 sweep round-tripped all sixteen reference examples and compared four signatures.
`artifact.digest`, `content_signature` and `source_signature` are a fixed point everywhere.
`resolution_signature` moves on four modules, in two distinct shapes, and only one of them is this item:

- `None → value` on the three carrying no `resolution.csv` (`grch37_build`, `mt_heteroplasmy`,
  `cyp2d6_structural`). Reverse materializes the table from the parquets, nothing is lost, and lap two
  is stable. Not a defect.
- `value → value` on exactly one, `cyp2c9_warfarin_grch37`: `c6fd3238…` → `a0558501…`.

The mechanism is closed. `_resolve_positional_tables` skips the positional fill when
`genome_build != DEFAULT_GENOME_BUILD`, because the identity minting behind those keys is GRCh38-only
(RM15). So the module's injected coordinates never reach `pharm_variants.parquet`; and
`_write_resolution_csv` rebuilds the table from `weights.parquet` plus the positional parquets, while a
PGx module has no `weights.parquet` at all. The three `source=manual` rows — `rs12777823`, `rs2108622`,
`rs9923231`, each carrying a `ref`/`alts` pair a curator supplied by hand — have nothing to be rebuilt
from and are simply gone.

**Say what is lost precisely:** those three rows are hand-curated, not machine-derived, so re-running
`enrich` does not reproduce them. Recovering them after a round trip means re-authoring them. That is
why the item exists at all; it is *low* severity because the module in the repository is the source of
truth and no published workflow round-trips a module and then discards the original, not because the
content is cheap.

### Is this a Principle 7 violation?

**No, on the letter, and the charter's own next sentence is the diagnosis.** Principle 7 says
*"**Lossless round-trip.** `compile_module` → `reverse_module` → `compile_module` preserves every
authored value."* `resolution.csv` is not an authored value: it is a machine-written, build-time derived
sidecar, priced at half by the 0.6 charter amendment, whose only consumers are the compiler and the
enricher's update run. Every authored value does survive — `content_signature` is `989e8298…` and
`artifact.digest` is `d7a4f37e…` before and after.

The clause that does apply is the one immediately after it: *"If a value cannot survive the round-trip,
the artifact is missing a field, not the spec."* That is exactly right here, and it is the whole
finding. The missing field is the coordinate on the positional parquet. RM43 added it in 0.6 for
`pharm_variants` / `haplotypes` / `heteroplasmy`, and RM15 gates the fill on GRCh38. So Principle 7's
own stated remedy points at a blocker Principle 7 cannot remove, and the honest statement is *a
documented limit of P7 on non-GRCh38 modules*, not a breach.

### Candidate repairs, and why each is wrong

- **Join `resolution.csv` onto the positional tables regardless of build.** This is precisely what the
  RM15 gate refuses. `resolve_from_table` filters on the `genome_build` column, and
  `derive_variant_key`/`derive_vrs_allele_id` default to GRCh38 — so the join would place rows against
  loci the compiler cannot re-derive a key for, and mint GRCh38 identities for GRCh37 coordinates. That
  is the defect `reverse_module`'s hardcoded constant caused and `test_build_call_sites.py` now walks
  the AST to prevent. The compiler would be manufacturing the identity it cannot check.
- **Have `reverse` carry the injected table through verbatim.** It cannot: `reverse_module` is a
  function of the *artifact*, and takes an artifact directory. The original `resolution.csv` is not one
  of its inputs. Making it one would turn reverse into a function of the spec directory as well, which
  is a different transform — and it would re-emit provenance reverse discards on purpose (`source`
  becomes `reversed`, `status` becomes `resolved`, `fetched_at` empties).
- **Write the injected coordinate into the positional parquet without joining.** The join spelled
  differently. Writing the coordinate is what the gate forbids, and doing it without re-deriving the key
  yields a parquet row whose coordinate and whose `variant_key` were computed on two different
  assemblies.
- **Add `resolution.parquet`.** RM43 refused it explicitly, and the charter amendment states the reason
  in general (this is the first repair anyone proposes on finding a table with no coordinate). It also
  does not fix anything here: it would stabilise the signature while the fill it exists to feed stayed
  skipped, so the module would hash as though its resolution survived when the data remained unjoined.
  A stable hash over unusable rows is worse than a moving one.
- **Stop comparing `resolution_signature` across the round trip.** The delete-the-test repair, and the
  D6 sweep is the argument against it: the sweep read `getattr(manifest, "resolution_signature", None)`
  while the field lives on `manifest.compilation`, so it compared `None == None` for eleven examples for
  the whole of 0.6. Un-comparing it now restores exactly the blindness just repaired. What this wants is
  a named, single exception, not a dropped comparison.

**What would unblock it:** RM15. Nothing smaller reaches it — a sixteen-module corpus produces exactly
one instance, because it takes a non-GRCh38 module that also carries a positional table with an injected
coordinate.

## RM70 — `requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption

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

**Severity** medium · **Status** deferred — four members blocked on a printed contract, two deliberately
reserved, one general question open · **Owner** enricher · **Found by** dogfooding on 2026-08-13,
`reference_examples/hboc_palb2/`

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
> output."* (`enricher/src/just_dna_enricher/cli.py:740-741`)
>
> `check-acmg`: *"Writes nothing, for the same reason `check-identifiers` writes nothing: `acmg_sf` is
> an authored cell this asks a registry about, not a fact this pass contributes. Filling it here would
> break the check — see `hints.REDUNDANCY_BEARING`."* (`cli.py:782-784`)

The same promise is made by `hint` in both CLIs (`enricher .../cli.py:1447`,
`compiler .../cli.py:533`), by `lookup`'s module docstring, and — the part that decides how expensive a
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

**`gene_disease_validity`.** Argued in the code at `schema/src/just_dna_format/vocab.py:637-642`: it
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
D4-1 headline count of twelve read correctly the first time.

The exclusion half is already tested in one direction.
`schema/tests/test_verification.py:276`'s `test_a_pass_that_only_records_a_source_gets_no_member` pins
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

### The general question

Is a check that reports to stdout and writes no record a **defect**, or a legitimate **read-only
surface**? Both readings are live in this codebase and neither is stated. `hint` and `lookup` are
read-only on purpose and should stay that way. `enrich` and `enrich_clinpgx` attest. `check-identifiers`
and `check-acmg` sit between: they put a real authored-versus-source question, which is precisely the
membership rule `VALID_VERIFICATION_CHECKS` states — *does this compare something the module asserts
against what a source says?* — and then answer it only to a terminal.

**What would unblock it:** a decision on that line, which then settles the reword. The four members
follow mechanically once it is made; the two reserved ones do not move either way.
