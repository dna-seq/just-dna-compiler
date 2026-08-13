# VCF 4.4 against the schema — what the spec says that we do not hold

**Research doc, 2026-08-13. No code changed, no `RMn` filed.** A read of the full VCFv4.4/BCFv2.2
specification (`hts-specs` c101c79, 5 Nov 2025) against `just_dna_format`, looking for cases the schema
gets wrong or cannot express that are **not** already tracked as an `RMn` and not already declared as a
blind spot in [COMPILER.md](COMPILER.md).

Scope note on what this audit is *for*. The format holds no sample data, so VCF is not an input or an
output — but it is the **only** artifact a consumer actually queries, and four authored columns point
directly into it (`source_field`, `callable_from`, `quality_from`, plus the `genotype` a consumer must
match). Everywhere those columns touch the spec, the spec is the contract, and a mismatch is a silently
wrong answer at query time rather than a compile failure. That is where every finding below sits.

Each item states what the spec says (with §), what the code does (with `file:line`), why it breaks, and
why the obvious repair is wrong — that last part being the half that makes an item actionable later.
Findings are ordered by consequence, not by how interesting they are.

Section [9](#9-checked-and-not-a-finding) records what was probed and came back clean, so it is not
re-probed.

---

## The through-line

Three of the four highest-consequence findings are one mistake in three places: **the schema names a
VCF field by a bare token, and a VCF field is not identified by its name.** It is identified by
*namespace* (INFO or FORMAT — two tables that collide on `DP`, `AD`, `ADF`, `ADR`, `MQ` and, as of 4.4,
`CN`) and by *cardinality* (`Number=1|A|R|G|P|.`, which decides how many values come back and what each
one is *of*). A token names neither. Where both readings are type-compatible — and for `DP`, `AF` and
`CN` they are — nothing anywhere detects the confusion: the consumer reads a well-formed number of the
wrong kind and bins it without error.

The fourth is the same shape one level up: **VCF 4.4 stopped treating copy number and repeat count as
integers**, and two of the five `measure_kind`s are built on the premise that they are.

---

## 1. A bare field token names two different fields, and 4.4 made the worst case worse

**Severity: high. Silent wrong answer at query time. Not RM-tracked.**

### What the spec says

VCF has two independent key namespaces, and the spec defines a reserved key table for each — Table 1
(INFO, §1.6.1.8) and Table 2 (FORMAT, §1.6.2). They overlap by name, deliberately, with different
meanings and in one case different *types*:

| Key | INFO (Table 1) | FORMAT (Table 2) |
|---|---|---|
| `DP` | `1 Integer` — **combined depth across samples** | `1 Integer` — **read depth for this sample** |
| `MQ` | `1 **Float**` — RMS mapping quality | `1 **Integer**` — RMS mapping quality |
| `AD`/`ADF`/`ADR` | `R Integer` — total read depth per allele | `R Integer` — per-sample read depth per allele |
| `AF` | `A Float` — **allele frequency, estimated from primary data, not called genotypes** | *not reserved* — but universally emitted by GATK/Mutect2/DeepVariant as the per-sample **allele fraction (VAF)** |
| `CN` | `A Float` — **allele-specific** copy number (§3, §5.6) | `1 Float` — **total** copy number for the sample (§4, §5.6) |

`CN` is new in this release and the split is explicit — §7.2: *"Redefined INFO CN as allele-specific
copy number and FORMAT CN as total copy number."* §5.6 spells out the consequence: in
`CN=1,2 … GT:CN 1/2:3`, the INFO values are `1` and `2` and the FORMAT value is `3`. Same token, and the
two answers differ by a factor of the ploidy.

### What we do

`source_field`, `callable_from` and `quality_from` all validate through one grammar
(`vocab.py:56`, `vocab.py:466`) that accepts a bare token and nothing else. Their own descriptions name
both namespaces without offering a way to pick one:

- `binning.py:136` — *"Optional VCF FORMAT/INFO field the consumer extracts this measure from (e.g.
  REPCN, AF, CN|DS)"*
- `spec.py:396` — *"Optional VCF FORMAT/INFO field(s) a consumer establishes callability from"*
- `spec.py:418` — *"Optional VCF FORMAT/INFO field the `min_quality` floor is stated against"*

Both shipped reference examples that use the columns land on a colliding key:

```
reference_examples/mt_heteroplasmy/heteroplasmy.csv : source_field=AF   (measure_kind=allele_fraction)
reference_examples/mt_heteroplasmy/variants.csv     : callable_from=DP  (requires_callable=true)
```

`mt_heteroplasmy` means **FORMAT/AF** — the per-sample heteroplasmy fraction of m.3243A>G in this
person's blood. `AF` as the spec reserves it is **INFO/AF** — the cohort allele frequency of that ALT.
Both are floats in `[0, 1]`; both bin cleanly against `0.0–0.1 / 0.1–0.3 / 0.3–1.0`; one of them tells a
carrier they are asymptomatic on the strength of how rare the variant is in a reference panel. Nothing
in the schema, the compiler or the consumer contract can tell them apart. `callable_from=DP` is the same
error one column over: INFO/DP is the cohort's combined depth and says nothing about whether *this*
sample's position was callable, which is the entire question `requires_callable` exists to make a
consumer ask.

### The claim this falsifies

ROADMAP.md:1042 states the pair `(INFO/RU, FORMAT/REPCN)` is *"consumable with zero glue."* That
sentence is written with the namespace attached and the schema has no column that can carry it — the
prose knows something the data model does not.

### Why the obvious repairs are wrong

- **Widen the grammar to `INFO/DP`.** Tempting and half-right, but it is a *retype in disguise*:
  every module carrying `source_field=AF` today keeps parsing and keeps meaning nothing in particular,
  so the ambiguity is preserved under a syntax that looks like it was resolved. A widened grammar with
  no migration is worse than the current state, because it makes the unqualified form look like a
  deliberate choice.
- **Default the namespace per column** (`callable_from` ⇒ FORMAT, `source_field` ⇒ INFO). This is the
  `None`-is-not-`False` mistake: it converts *unstated* into a *stated* answer, and it would be wrong
  for `mt_heteroplasmy` on the very first module.
- **Pick by reading the consumer's header.** That is a source convention inside the format tier (P2,
  the RM33 mistake), and it is not decidable anyway when both namespaces declare the key.

The shape that survives is an **additive optional column** (`source_namespace` / a qualified second
column) leaving the bare token meaning *unqualified*, plus a compiler warning naming the collision set
— which is a fixed, spec-derived list, not curated data. Legality: additive optional column, minor-legal
under the 2026-08-11 amendment.

---

## 2. A field pointer with no element selector, where the field has many elements

**Severity: high. Silent wrong answer. Not RM-tracked. Same column set as §1 and probably the same design round.**

### What the spec says

§1.4.2/§1.4.4: `Number` is part of a field's definition, not decoration. `A` = one value per ALT, in ALT
order. `R` = one per allele, **reference first**. `G` = one per genotype, in the ordering of §1.6.2.
`P` = one per GT allele value (new in 4.4). `.` = unknown/unbounded.

So a pointer at `AD` (`R`) returns *n+1* integers of which none is the answer — an allele fraction is
`AD[i] / sum(AD)`, and `i` is not in the field name. A pointer at `AF` (`A`) returns one value per ALT.
A pointer at `RUC` (`.`, §3) returns a flattened list-of-lists across every ALT allele, whose inner
lengths are given by a *different* field (`RN`).

### What we do

Nothing. `SOURCE_FIELD_PATTERN` (`vocab.py:56`) permits a token and `|`-alternation, and
`|`-alternation is explicitly *fallback between fields*, not indexing. `min_quality` (`spec.py:426`) is a
scalar floor with no rule for what to do against a multi-valued `quality_from`.

### Why it bites hardest where it matters most

`repeat_alleles.csv` is a table about **dominant** repeat disorders. The clinical rule for HTT is *the
larger of the two alleles*; `reference_examples/htt_repeat_expansion` states four thresholds under
`--strict` and points at `REPCN` with nowhere to say "larger". A consumer that averages, takes the
first, or takes the reference allele gets a well-formed number and a wrong answer, and every offline
gate passes — the same failure geometry as the 3,038-row coordinate incident, where a printed contract
was followed exactly and the result was wrong.

### Why the obvious repair is wrong

An **index** (`AD[1]`, `REPCN[max]`) is where this naturally goes and it is the beginning of an
expression grammar — the thing Principle 1 exists to refuse, and the reason `source_field` was
constrained to a bare token in the first place. What is actually wanted is a **closed vocabulary of
selection rules** (`max` / `min` / `alt` / `sum` / `ref`), which is data, terminates, and needs no
evaluator. That is a design round, not a patch: the rule set has to be decided once for all four
columns, and `max` on a `Number=R` field silently includes the reference element unless the vocabulary
says otherwise.

---

## 3. `copy_number` is modelled as an integer kind; VCF 4.4 says it is not

**Severity: high. A whole `measure_kind` is unauthorable for its own source data. Not RM-tracked — RM35 explicitly exempted this kind on a premise the spec has now withdrawn.**

### What the spec says

§7.2, verbatim: *"Redefined INFO and FORMAT CN to support non-integer copy numbers."* The worked
examples are fractional throughout — §5.7's `<CNV:TR>` record carries `CN=3,0.9666` (INFO) and
`GT:PS:CN 1|2:100:3.9666` (FORMAT); §5.7's later example `CN=1.25`. §5.6 adds that granularity is
deliberately undefined and may be *"at a highly granular megabase level of resolution"* — i.e. a
segment-mean, which is continuous by construction.

### What we do

`binning.py:77` puts `copy_number` in `_INTEGER_KINDS` and `binning.py:86` keeps it out of
`_DENSE_KINDS`. RM35's own reasoning (`binning.py:37`) is *"`repeat_count`/`copy_number` tile exactly
under inclusive bounds … because the domain is integral"*. That premise is now false against the spec.

Probed against the real `validate_bins`:

```
integer bins [0,0] [1,1] [2,2] [3,∞)   →  OK, warnings=[]      ← a CN of 2.4 matches NO bin, silently
dense bins   [0,1] [1,2] [2,3]         →  ValueError: overlapping bins
workaround   [0,0.999] [1,1.999]       →  OK, warnings=[]      ← arbitrary, and (0.999,1) uncovered, unwarned
```

That is RM35's unsatisfiable triangle exactly — inclusive bounds + overlap-is-error + hole-is-warning —
re-instantiated on the kind RM35 exempted. It is *worse* than the `allele_fraction` case RM35 fixed,
because on an integer kind a hole of exactly 1 is not reported at all: the module compiles green,
`--strict` included, and a fractional CN selects nothing. The consumer contract's third state
("present but matches no bin") is reached for every non-integral measurement, which is not a rare edge
on a read-depth caller — it is the normal output.

`CopyNumberRow.modifier_cn` (`binning.py:225`) is additionally typed `int`, so even the *modifier*
dosage (SMN2 copy number, routinely fractional before rounding) cannot be written down.

### Why the obvious repair is wrong

**Moving `copy_number` into `_DENSE_KINDS`** is a one-line change and it silently retypes every existing
`copy_number` table: today `[2,2]` beside `[3,3]` is a legal integer tiling, and under dense semantics
the shared-endpoint rule and the gap warning both change meaning for tables already published. It also
answers the wrong question — RM35's own comment beside `_DENSE_KINDS` says the two sets answer *"can a
hole be arbitrarily small?"* and *"can two bins touch?"* separately, and a rounded integer CN from a
catalog caller and a continuous segment-mean genuinely differ on both. The honest shapes are either a
**per-table declaration of whether the measure is quantized** (additive column, minor-legal) or a
**sixth `measure_kind`** for continuous dosage; picking between them is the design round. Retyping
`modifier_cn` to `float` is a retype and therefore 1.0 — but an additive `modifier_cn_max` or a
parallel float column is not.

---

## 4. A repeat count is a Float with a confidence interval, and may be unbounded above

**Severity: high on the flagship binning example. Not RM-tracked (RM47 is about *citing* a bound, not about the measurement's shape).**

### What the spec says

§3: `##INFO=<ID=RUC,Number=.,Type=Float,Description="Repeat unit count of corresponding repeat
sequence">` — the repeat count VCF 4.4 standardizes is a **Float**, not an integer. It travels with
`CIRUC` (§3), and the spec is explicit that the upper bound may be absent: *"If the lower bound is the
missing value '.', is assumed to be 0 and if the upper bound is the missing value '.', it is assumed to
be an **unbounded estimate**. That is, the length of repeat has been determined to be at least a certain
length but a reasonable limit of total length of the repeat could not be determined."* §5.7 gives the
canonical form for a CAG tract: `RUS=CAG;RUC=65;CIRUC=-15,.` — meaning ≥50, most likely 65.

§5.7 states why: *"Many of these techniques result in imprecise variant calls which cannot be
unambiguously represented with non-symbolic alleles."* Imprecision is the normal case, not the edge.

### What we do

`repeat_count` is an `_INTEGER_KINDS` member (`binning.py:77`), bins are scalar-valued, and the
consumer contract (`binning.py:41-47`) has exactly three states: a bin matched, no bin matched, or
`unresolved` (measurement absent). There is no state for **a measurement that spans several bins**, and
no way for a table to say what a consumer should do with one.

`reference_examples/htt_repeat_expansion` is where this lands. Its boundaries are 26/27, 35/36 and
39/40 — three thresholds inside a 14-count window — and a real ExpansionHunter/`<CNV:TR>` call of
`RUC=38, CIRUC=-5,5` spans `[33,43]`, crossing all three. The module says *neutral/benign*,
*uncertain_significance*, and the fully-penetrant bin, and there is no honest answer among them. A
consumer that takes the point estimate is asserting a precision the source explicitly declined to
claim; one that withholds has no schema affordance saying it should.

### Related, same table, distinct: one locus, several motifs

§5.7: a `<CNV:TR>` allele *"consists of one or more repeat sequences"* and *"can encode multiple
different repeat motifs in a single allele"* — `RN=3` with `RUS=CAG,TG,CAGG`. `RepeatAlleleRow` is keyed
`(gene, repeat_unit)` (`binning.py:256`) and binds one count to one motif. For HTT specifically the
interruption structure `(CAG)n(CAA)(CAG)` is exactly what a caller now reports as multiple `RUS`
entries, and the pure-CAG tract length differs from the total — a difference with published effect on
age of onset. The key cannot express which of the three counts the bins are about, and by
`_KEY_FIELDS` two rows for the same gene with different `repeat_unit` are different *groups*, not
components of one allele.

### Why the obvious repair is wrong

**Widening the measurement to an interval** (`measure_min_observed`/`measure_max_observed`) puts a
*measurement* in the module, which the data-agnostic north star forbids outright — the table never sees
a sample. What belongs here is the **rule for an interval that spans bins**, which is annotation: a
per-table or per-row policy (`withhold` / `take the worst bin` / `take the point estimate`), stated by
the curator, evaluated by the consumer. That is a closed vocabulary and stays inside Principle 1. The
motif-composition half is a separate and larger question and should not be bundled with it.

---

## 5. A `min_quality` floor against `QUAL` inverts on exactly the rows it exists for

**Severity: medium-high, narrow but the failure is a confident wrong answer. Not RM-tracked.**

### What the spec says

§1.6.1.6: *"QUAL — quality: Phred-scaled quality score for the assertion made in ALT. **If ALT is '.'
(no variant) then this is −10log10 prob(variant), and if ALT is not '.' this is −10log10 prob(no
variant).**"*

The sign of the assertion flips with the record. A QUAL of 60 on a variant record means *this variant is
almost certainly real*; a QUAL of 60 on a monomorphic/reference record means *this position is almost
certainly variant* — the opposite of a clean reference call.

### What we do

`spec.py:418` names `QUAL` as a recommended `quality_from` value, and `spec.py:426` defines
`min_quality` as an inclusive floor: *"withhold this row's conclusion where the consumer's value is
below it."* That is monotone in one direction only.

The collision is with `requires_callable` (`spec.py:366`) — the flag for rows where *the absence of the
variant is the informative call*. A consumer evaluating such a row reads the **reference** record for
that position: either a gVCF `<*>` block (§5.5) or a monomorphic `ALT=.` record (the fourth record in
the spec's own §1.1 example). Both are precisely the case where QUAL's meaning is inverted. So a module
that writes `requires_callable=true, quality_from=QUAL, min_quality=30` is asking the consumer to
*require* the evidence that the position is variant, before asserting that it is not — and the higher
the author sets the floor, the more confidently wrong the result. `mt_heteroplasmy` uses
`callable_from=DP` rather than QUAL and so avoids it, which is luck, not design.

### Second half: the record is a block, not a position

§5.5: reference evidence is a *range* — `1 4370 . G <*> . . END=4383 GT:DP:GQ:MIN_DP:PL`. So for a
`requires_callable` row the callability evidence is found by **interval containment**, not by an
equality join on POS, and the right depth field is `MIN_DP` (the block floor) rather than `DP` (the
block average) — a `DP` of 25 over a 14bp block is compatible with a single uncovered base inside it.
Nothing in `callable_from`'s description or in the create-module guidance says either thing, and
`callable_from=DP` is what the shipped example writes.

### Why the obvious repair is wrong

**Rejecting `QUAL` on a `requires_callable` row** is a validator that encodes one reading of a field
whose meaning depends on a record the compiler will never see, and it would refuse the legitimate
combination (a `requires_callable` row on a *variant* record elsewhere in the same VCF). This is a
documentation and diagnosis item first — a warning naming the inversion, and guidance that says
`MIN_DP` for blocks — with a schema change only if the interval-vs-position distinction turns out to
need a column.

---

## 6. `alts` accepts four VCF-legal spellings the genotype grammar can never name, and one of them splits identity

**Severity: medium-high for the identity half. `*` is not covered by RM5.**

### What the spec says

§1.6.1.5, ALT may be: *"a non-empty String of bases (A,C,G,T,N; case insensitive); the '*' symbol
(allele missing due to overlapping deletion); the MISSING value '.' (no variant); an angle-bracketed ID
String; the unspecified allele '<*>'; or a breakend replacement string."*

### What we do

Probed against the real models:

```
alts='*'      → accepted, variant_key = 1:1:A:*
alts='.'      → accepted, variant_key = 1:1:A:.
alts='<DEL>'  → accepted, variant_key = 1:1:A:<DEL>
alts='N'      → accepted, variant_key = 1:1:A:N
genotype='A/*'  → rejected      genotype='A/N' → rejected
```

`VariantRow.alts` runs no validator at all — deliberate, and the reason is recorded (`alleles.py:84`:
adding a nucleotide grammar would tighten the field RM5 exists to widen and would break P3). The
`genotype` grammar (`base.py:348` → `ALLELE_PATTERN`, `vocab.py:46`) is `^[ACGT]+$`. So the two halves
of a row disagree about what an allele is, and the consequences are two distinct bugs:

**(a) `alts='.'` splits identity.** `.` is VCF's MISSING marker meaning *there are no alternate
alleles* — a monomorphic reference record, which §1.1's own example carries. We read it as a literal
allele and fold it into `variant_key` (`base.py:171`), so a module writing `alts=.` and one leaving the
cell empty describe the same monomorphic site under two different keys — `1:1:A:.` and `1:1:A` — with
different `content_signature`s, no dedup between them, and no diagnostic anywhere. This is the only
finding in this document that reaches identity.

**(b) `*` has no home and is not RM5's problem.** RM5 covers *symbolic and structural* alleles —
`<DEL>`, 5-HTTLPR, ClinPGx `del`/`ins`, CPIC's `x≥3` — all of which are ways of naming a **variant**
whose sequence the grammar cannot spell. `*` names no variant: it is a statement that *this sample's
allele could not be observed here because a deletion called elsewhere overlaps this position*. That is
an **observability** claim, which is RM6's axis (`requires_callable` / `callable_from`), not RM5's. It
also matters more than its obscurity suggests: `*` is what a modern joint-called VCF puts in ALT at any
site under an overlapping deletion, so `GT=0/2` with `ALT=A,*` is an ordinary genotype in real consumer
data — and no `variants.csv` row can be written for it, while a consumer that drops the `*` reads the
call as `0/0`-ish and takes the reference conclusion. That is the exact no-call-is-not-hom-ref error
`requires_callable` was built to prevent, arriving through a spelling instead of through a missing
record.

### Why the obvious repair is wrong

**Adding `^[ACGT]+$` to `alts`** is the repair `alleles.py:84` already refuses, for good reasons that
still hold. The narrow correct move for (a) is a **diagnosis, not a grammar**: `.` is not an allele, and
`non_nucleotide_reason` (`alleles.py:50`) is the existing place to say so — it currently files `.` under
`"notation"` alongside `<DEL>`, conflating *the MISSING marker* with *a symbolic allele*, which is the
same two-reasons-under-one-message mistake that `cpic.unusable_allele_reason` had to unwind. For (b),
widening `genotype` to admit `*` is a genotype-grammar change that has to be decided against RM5 rather
than inside it, since the two would then share a syntax and mean different things.

---

## 7. `chrom` rejects `chrM`, and the same tier has a normalizer that accepts it

**Severity: medium. Pure authoring friction, but it rejects the GRCh38 analysis-set spelling.**

§1.4.7 permits essentially any contig name (`[0-9A-Za-z!#$%&+./:;?@^_|~-][...]*`). Real GRCh38 VCFs
split on the mitochondrion: Ensembl-style writes `MT`, UCSC/analysis-set style (hs38DH — the reference
most human pipelines actually align against) writes `chrM`.

Probed:

```
chrom='MT'    → MT       chrom='chrMT' → MT
chrom='chrM'  → REJECTED chrom='M'     → REJECTED   chrom='CHR7' → REJECTED
```

`VariantRow._validate_chrom` (`spec.py:557`) does `removeprefix("chr")` and then requires membership in
`VALID_CHROMOSOMES` (`spec.py:57`). Meanwhile `vrs.normalize_chrom` (`vrs.py:118`), in the same package,
folds `M`/`chrM` → `MT` and strips `chr`/`CHR`/`Chr`. Two normalizers, different tolerance, and the
stricter one is the gate an author hits — with a message that lists `MT` and does not mention that
`chrM` is the same contig.

This is the same class the 0.6 `-`-for-`_` vocabulary tolerance shipped for (`vocab.match_vocab`): the
surface an author learns the vocabulary from taught a spelling the file rejected. The repair is the same
shape — route `_validate_chrom` through `normalize_chrom` — and it **widens only**, so it is P3-clean:
every value that validates today still validates and normalizes to the same member. Alt contigs,
scaffolds, patches and decoys stay rejected, correctly and by charter (`REFGET_GRCh38` is primary
assembly only).

---

## 8. Lower-consequence items

### 8a. The pointer grammar rejects VCF-legal keys

§1.6.1.8 / §1.6.2: an INFO key matches `^([A-Za-z_][0-9A-Za-z_.]*|1000G)$` and a FORMAT key
`^[A-Za-z_][0-9A-Za-z_.]*$`. (The `.txt` extraction renders the underscores as spaces; the PDF and the
`hts-specs` source carry `_`.) So a dot is legal *inside* a key, and `1000G` is a legal key beginning
with a digit — the spec reserves it explicitly as a legacy value.

`SOURCE_FIELD_PATTERN` (`vocab.py:56`) allows neither. Probed: `1000G` and `gnomAD.AF` are both refused.
Low consequence today, but it is a grammar claiming to describe VCF field names while refusing two
shapes the spec names by hand — cheap to fix, and the fix is strictly widening.

### 8b. Float32 at an inclusive bound

§1.3: *"Float (32-bit IEEE-754 …)"*. Every number a consumer reads out of a VCF is float32; every bound
and floor in the schema is Python float64. Widening is exact but not value-preserving relative to the
decimal an author typed: an authored `0.1` is `0.1000000000000000055…` in float64, while the VCF's
`0.1` widens to `0.100000001490116…`. The value is therefore **above** the authored bound.

For `measure_min` this is harmless — it lands inside the bin and the shared-endpoint rule already says
the higher bin owns a boundary. For **`measure_max`** it is not: a top bin closed at `1.0` on
`allele_fraction` is fine (1.0 is exact in both), but any non-dyadic closed upper bound (`0.1`, `0.3`,
the `mt_heteroplasmy` boundaries) can be missed by a value that reads as equal in the source file. Same
for `min_quality` against a float32 `QUAL`. The schema is right to keep decimal bounds — the DSL exists
for the human — so this belongs in the **consumer contract** as a stated tolerance rule, not as a schema
change. Recording it because nothing states it today, and a lookup rule that is exact in one direction
and not the other is the kind of thing that gets discovered in production.

### 8c. `A|G` names no homolog without a phase set

§1.6.2 (PS/PSL) is unusually explicit: *"A given sample-genotype must not have values for both PS and
PSL"*, and PSL exists precisely because with PS *"it isn't connected to any specific haplotype (i.e.
first or second), but PSL is."* VCF only defines allele order **within** a phase set; there is no global
"first homolog".

Our genotype grammar accepts `A|G` as order-significant (`base.py:355`: *"phase encodes which allele
sits on which homolog"*) and the compiler materializes `phased` as a bare boolean
(`compiler.py:3059`). With no phase-set column, an authored `A|G` and an authored `G|A` are
distinguishable to us and indistinguishable to any consumer, and two rows both written `A|G` assert
nothing about being in cis. This is not a live defect — the cis/trans case is carried properly by
`DiplotypeRow` and the phase-ambiguity check, which is RM28's closed half — but the docstring's claim is
wider than what the format can support, and `flags: phased` invites an author to lean on it. A one-line
docstring correction, or an explicit statement that a pipe-separated `variants.csv` genotype means "het,
phase recorded but unaddressable".

### 8d. Polyploid and partially-phased GT

§7.2: *"Added polyploid partial phasing support (e.g. GT |0|0/1/2). GT now defined as a prefix notation
with the first phasing indicator optional."* Our grammar caps at two alleles and refuses a leading
separator (probed: `A/A/G` and `A|G/T` both rejected). This is a **defensible generalization** — the
format annotates human diploid loci, and `_check_contig_ploidy` already handles the hemizygous/haploid
direction — but it is now a documented divergence from the spec rather than an unexamined default, and
the spec's own polyploid example is a tandem duplication with SNVs on it, which is a shape a CNV-aware
consumer will meet. Recorded, not filed.

### 8e. `ID` is a list

§1.6.1.3: *"Semicolon-separated list of unique identifiers where available."* A real record may carry
`rs123;rs456` (or an rsID beside a COSMIC id). `validate_rsid` (`vocab.py:545`) takes exactly one
`rs\d+`. Correct for the authored side — a row should name one variant — but a consumer joining on the
VCF `ID` column has to split first, and nothing says so. Documentation only.

---

## 9. Checked, and *not* a finding

Recorded so these are not re-probed.

- **Position-1 padding.** §1.6.1.4: at position 1 the padding base goes on the **right**, not the left.
  `alleles.parsimony_reduce` (`alleles.py:100`) trims *right first, then left*, so it handles both;
  the docstring says so explicitly. Clean.
- **Telomeric POS 0 / N+1** (§1.6.1.2, §5.4.5). `VariantRow.start` is `ge=0` so POS 0 loads, and
  `derive_vrs_allele_id` returns `None` for `start < 1` (`vrs.py:301`) rather than minting an id for a
  position that does not exist. Clean, and apparently by accident of a guard written for another
  reason — worth keeping.
- **No VA is minted for a non-nucleotide ALT.** `is_substitution` (`vrs.py:249`) requires
  `{ref, alt} ⊆ {A,C,G,T}`, so `alts='*'`, `'.'`, `'N'` and `'<DEL>'` all fall through to the coordinate
  key. The identity-splitting bug in §6a is a `variant_key` *string* problem, not a false
  content-addressed claim. Clean.
- **Why the IUPAC probe found zero.** CLAUDE.md records that `R/Y/S/W/K/M/B/D/H/V` appear in neither
  REF nor ALT across 4,439,382 ClinVar rows, offered as an empirical fact. §1.6.1.4 explains it and
  makes it structural: *"If the reference sequence contains IUPAC ambiguity codes not allowed by this
  specification (such as R = A/G), the ambiguous reference base must be reduced to a concrete base by
  using the one that is first alphabetically."* The probe is not a lucky sample — the spec mandates the
  reduction. Two things follow that are worth writing down. An authored `ref=A` may be a **lossily
  reduced `R`**, so a ref-mismatch diagnosis should not treat a single-base disagreement as necessarily
  a coordinate error. And §1.4.5 gives the sanctioned way to express what CPIC's `R` means — a
  **symbolic ALT** `##ALT=<ID=R,Description="IUPAC code R = A/G">` — which is squarely RM5's axis and
  strengthens the existing decision to file it there rather than widening the nucleotide grammar.
- **`_check_contig_ploidy` vs the PAR.** Consistent with §1.6.2's haploid guidance and already
  three-valued. No change.

---

## 10. One claim in the codebase that the spec contradicts

`compiler.py:825`, on `_POSITIONAL_TABLE_KINDS`:

> *"a table is positional exactly when it declares both `chrom` and `start`. Today that is
> `heteroplasmy.csv`, `haplotypes.csv` and `pharm_variants.csv`; **the rest are gene- or score-keyed and
> are not joinable by position at all, which is a property of what they describe rather than a gap.**"*

True of `allele_function.csv` and `pgs.csv`. **False of `repeat_alleles.csv` and `copy_number.csv`
under VCF 4.4**, which gives both of them coordinates as a matter of spec:

- §5.6, CNV: *"POS and INFO SVLEN specify the genomic interval over which the copy number is defined."*
- §5.7, tandem repeats: *"The POS and END of `<CNV:TR>` records should match the STR/VNTR reference
  catalog sizes for catalog-based callers."*

A tandem repeat and a copy-number segment are *loci with coordinates*, and a catalog-based caller emits
them at fixed, published positions. So the non-joinability of those two tables is a **gap in the
schema**, not a property of the thing described — which is exactly the distinction RM43 was careful to
draw for the other three tables, applied one table further than it was taken. It is also the reason a
consumer holding an ExpansionHunter or a `<CNV:TR>` VCF cannot mechanically find our HTT row: the join
runs through a gene symbol they have to annotate for themselves.

This does not change RM43's scope (RM43 is about resolution *filling* coordinates on tables that
declare them). It is a separate observation about which tables *should* declare them, and it belongs
with §4's motif question in the same design round.

---

## Summary — candidate items, with the legality that sizes them

| # | Finding | Class | Legality |
|---|---|---|---|
| 1 | INFO/FORMAT namespace collision on `DP`/`AF`/`CN`/`MQ`/`AD` | silent wrong quantity | additive optional column — minor |
| 2 | No element selector for `Number=A/R/G/.` fields | silent wrong quantity | additive column + closed vocabulary — minor, design round |
| 3 | `copy_number` treated as integral; 4.4 made CN a Float | kind unauthorable | additive column or 6th kind — minor; `modifier_cn` retype is 1.0 |
| 4 | Repeat count is Float + interval + possibly unbounded; multi-motif alleles | no state for a spanning measurement | additive policy column — minor, design round |
| 5 | `QUAL` inverts on reference records | confident wrong answer on `requires_callable` rows | docs + warning — patch |
| 6a | `alts='.'` splits `variant_key` | identity | diagnosis — patch |
| 6b | `*` (overlapping deletion) has no home and is not RM5 | unwritable real genotype | genotype-grammar decision — minor, with RM5 |
| 7 | `chrom` rejects `chrM` | authoring friction | widening only — patch |
| 8a | Pointer grammar rejects `1000G` and dotted keys | authoring friction | widening only — patch |
| 8b | float32 at an inclusive `measure_max` | boundary miss | consumer contract — docs |
| 8c | `A|G` names no homolog | overclaiming docstring | docs |
| 8d | Polyploid / partial-phase GT | documented divergence | none proposed |
| 8e | `ID` is a `;`-list | consumer-side | docs |
| 10 | "gene-keyed ⇒ not positional by nature" is false for repeats/CNVs | claim contradicted by spec | design round, with #4 |

Nothing here needs a major. The two that most want deciding together are **#1 and #2** — one column set,
one design round, and every module that already uses `source_field` is affected by both.
