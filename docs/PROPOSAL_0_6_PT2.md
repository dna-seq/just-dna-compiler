# 0.6 PT2 design thread — the items that fell in while 0.6 was open

**What this is.** Stage 3 of the design cycle for the second half of the 0.6 line. The first design
round ([PROPOSAL_0_6.md](PROPOSAL_0_6.md)) was decided on 2026-08-13 against the roadmap as it stood
that morning. Everything since — two dogfooding rounds, the VCF 4.4 audit's deferred tail, the module
lifecycle pass, and five consumer reports — filed items *behind* that line. They accumulated in
[ROADMAP_0_7.md](ROADMAP_0_7.md) because the release they were filed against was the next one, and
nobody re-asked whether the release they were filed against was still the right one now that 0.6 is
uncut.

This document re-asks it, once, and closes the question. Same convention as PROPOSAL_0_6: each item
records the problem in plain terms, **the facts established while deciding it** (three of them overturn
what the roadmap entry says), the decision, the reasoning, **the repairs that were rejected and why**,
and the consequences that follow without being chosen.

**Status.** Decided 2026-08-16, on the `0.6` branch, before implementation. **Nothing here has
shipped.** Where a decision changes what ROADMAP_0_7.md or ROADMAP_1_0.md says, those files are stale
and this one wins until the item lands and moves to ROADMAP_HISTORY.

**Scope.** Twenty-one open items were sorted. **Five build**, sixteen stay deferred with the reason
restated per item. RM55 appears on both lists — its usable fix is taken and its removal half stays at
1.0 — which is why the deferral table below has seventeen rows for sixteen items. No charter amendment is needed — the 2026-08-13 cost amendment is what does most of
the sorting work below, and it is already in the Constitution.

---

# The sort, and the rule it used

Three rules, applied in this order, and the order matters because the first is the only one that is
not a judgement call:

1. **Blocked is blocked.** An item whose stated unblock condition is unmet is not a candidate, however
   severe. Six items are blocked on RM15, on a real caller VCF, or on another repository's reply.
2. **A new expensive feature waits.** An item whose repair is a capability nobody has asked for yet —
   a new authored table, a new authored column with no author wanting it, a new command — waits for the
   demand that would fix its shape. This is the charter's own reasoning about one-way doors (P3/P5)
   stated as a scheduling rule.
3. **A half-defect is ordered by severity.** An item where something *already shipped* is wrong,
   silent, or lying is taken, and the worse ones go first. Legality sizes the release; severity only
   orders the queue.

Rule 3 is what puts RM55 at the top of a document that also contains a two-line newline fix: a schema
that silently answers nothing for a legal measurement outranks a schema that has a column nobody wanted.

**What none of this is gated on.** Not the digest — the 2026-08-11 amendment retired that window, and
two of the five items below move `artifact.digest` on most of the corpus (five modules and twelve of
sixteen respectively) without that being a cost worth naming. Not the version — every item here is additive under P3/P8. Legality decided nothing in this
round; it only failed to stop anything.

---

# Decisions

## RM55 — a fractional copy number matches no bin, and the fix is not the column the entry names

**Severity** high · **Owner** format (schema: `binning`) + compiler · **Filed** 2026-08-13 from
[VCF_4_4_AUDIT.md](VCF_4_4_AUDIT.md) · **Entry** [ROADMAP_0_7.md § RM55](ROADMAP_0_7.md#rm55--copy-number-and-repeat-count-are-not-whole-numbers-the-usable-fix)

### The problem

VCF 4.4 §7.2 redefined INFO/FORMAT `CN` to support non-integer copy numbers, with fractional worked
examples throughout, and §3 types the repeat unit count `RUC` as a Float. This schema tiles both kinds
as whole numbers, so a copy number of 2.4 matches **no bin at all** — silently, `--strict` included.
0.6 shipped a loud warning saying exactly that and naming 0.7 as where the fix lands.

### The facts, which overturn the entry's suggested fix

The entry's fix is *"a parallel float column beside the integer one, with the integer column deprecated
and removed at 1.0"*. Probing the code for the column it names found mostly that there is not one.

- **The bin bounds are already floats.** `MeasureBinRow.measure_min` and `measure_max` are
  `float | None` (`schema/src/just_dna_format/binning.py:231`, `:238`). A curator can author
  `measure_min=2.5` on a `copynumbers.csv` row today and it validates. There is no integer bound
  column to sit a float one beside, on either kind.
- **`_INTEGER_KINDS` has exactly one reader in the entire tree.** It is defined at `binning.py:148` and
  read at `binning.py:688` — the gap-width rule — and nowhere else in `schema/src`, `compiler/src` or
  `enricher/src`. The "integer" premise is one boolean branch, not a type system.
- **The one genuine `int` is not a bound.** `CopyNumberRow.modifier_cn: int | None` (`binning.py:386`)
  is the dosage of a *modifier* locus, and it is inside `_KEY_FIELDS` (`binning.py:380`) — it is part
  of the row's key, not part of the measured axis.

So the defect is not a type at all. It is **three semantic rules keyed on the kind**, and only one of
them is the one the entry describes:

1. **The gap rule tolerates a hole of exactly one** — `binning.py:687-694`. On an integer kind a gap is
   only reported when it is *wider* than a whole number, so `[2,2]` beside `[3,3]` strands every value
   in the open interval `(2,3)` and the check that exists to report holes is told this one is not a
   hole. This is the mechanism behind the 0.6 warning's own worked example.
2. **The shared-endpoint rule refuses the tiling that would fix it** — `binning.py:666-677`.
   `copy_number` and `repeat_count` are not in `_DENSE_KINDS` (`binning.py:157`), so two bins sharing
   an endpoint is an **overlap error**. An author who reaches for the obvious repair — write
   `[0,2] [2,4]` and cover the axis continuously — is refused by the schema. **This half is not in the
   roadmap entry at all**, and it is the half that makes the defect unworkaroundable: the entry says a
   fractional measurement matches no bin, and the truth is stronger, that the schema also forbids
   writing a table where it would.
3. **`modifier_cn` cannot hold a fractional dosage** — `binning.py:386`. Real, and, as below, not this
   release's problem.

**Corpus.** Three modules carry an affected table: `reference_examples/cyp2d6_structural/copynumbers.csv`,
`reference_examples/fmr1_cgg_repeat/repeat_alleles.csv`,
`reference_examples/htt_repeat_expansion/repeat_alleles.csv`. All three tile as whole numbers today.

### The decision

**Take the usable fix whole, in the shape the code turns out to want — a declaration, a companion
column, and the semantics that make either mean anything. Only the removal stays at 1.0.**

**(a) The tiling becomes authorable — a new optional `measure_tiling` column on `MeasureBinRow`,**
carrying a closed two-member vocabulary `{quantised, continuous}` in the house idiom (`frozenset[str]`
plus a validator, P6). The gap rule and the shared-endpoint rule stop reading `_INTEGER_KINDS` and
`_DENSE_KINDS` directly and read an **effective tiling** instead: the declared value if there is one,
else the reading the data forces (b′), else the kind's current default.

**Absent means "the kind's current default", not a value.** This is what keeps the change additive:
`copy_number` and `repeat_count` default to `quantised`, `allele_fraction` and `prs_percentile` to
`continuous`, and `activity_score` keeps its third behaviour (no gap warning, a shared endpoint is an
error) by defaulting to neither. Every module published today keeps its exact meaning, and no author
ever meets this column unless they are departing from their kind's default — which is what makes a
full-cost authored column cheap here in practice as well as legal in principle.

**What the column is for, once (b′) infers the common case.** It states the claim *before* the data
proves it: a curator tiling a continuous measure who has only whole-number thresholds to write has no
fractional row to infer from, and this is the one place they can say so. It is the declaration; (b′) is
the safety net under it.

**Grain: per row, constrained to agree within a bin group.** The tiling rules already operate over the
groups `_bin_groups` computes (`binning.py:547-562`), so that is the grain the semantics have; a check
refuses two rows in one group that disagree, the way `_validate_modifier` refuses a half-filled
modifier pair (`binning.py:400-407`). Repeating a per-group value on every row is not a new cost being
introduced: `measure_kind` is itself per-row and constant within a group, and has been since 0.4.

**(b) `modifier_cn` gains a parallel float column, `modifier_copy_number`, read through a legacy
fallback.** This is the entry's original shape, applied to the one column it actually fits, and it
survives the objection that was raised against it in this document's first draft.

- **The name spells out what the abbreviation shortened**, which is what makes the pair legible without
  a comment. The house precedent for this move is `StudyRow.p_value` → `p_value_num` (0.5), and the
  suffix is deliberately *not* copied: `_num` there separated a string from a number, and here both
  columns are numbers, so a `_num` suffix would name nothing.
- **Read:** an effective-value alias returns `modifier_copy_number` when set, else `float(modifier_cn)`
  when set, else `None`. Nothing anywhere reads the raw pair — the alias is the only reader, the way
  every `effective_*` alias in this schema already works. It must be a fixed point under P7's
  idempotency clause, which for a coalesce is free but still owed a test.
- **Both set is an error**, not a precedence rule. Two spellings that can disagree, with a rule for
  picking a winner, is the `vrs_id` desync shape; refusing is the same move `_validate_modifier` already
  makes on the half-filled modifier pair (`binning.py:400-407`).
- **`_KEY_FIELDS` keys on the effective value, not on either column** (`binning.py:380`). This is what
  dissolves the objection that killed the parallel column in the first draft — that it would put two
  spellings of one value into a row's **key**, which is
  [RM81](ROADMAP_1_0.md#rm81--one-artifact-spells-a-genotype-two-ways)'s shape and worse in a key than
  in a payload. A coalesced effective value is **one** spelling by the time grouping and dedup see it,
  so the key never holds the ambiguity. The objection was to two values in a key; it is not an objection
  to a companion column read through one.
- **`modifier_cn` is deprecated in this minor and removed at 1.0**, which is exactly the shape the 0.6
  cadence amendment authorises: warn-only, the field still reads and behaves as before, and the warning
  is *actionable* — the replacement exists and an author can stop setting it the day they read it. That
  actionability is the amendment's own condition, and it is met here, unlike `state` and the ClinVar
  booleans where P8 blocks it.

**(b′) A float value and the continuous rules are one change, not two — so the rules follow the
evidence, and say that they did.** A fractional dosage evaluated under quantised tiling is the current
defect wearing a new column: it would match nothing, exactly as 2.4 matches nothing today. Shipping the
column without the semantics would be shipping a way to write a value the schema still cannot answer
for. So:

- **A group carrying a fractional value is read under the continuous rules**, whatever its kind's
  default says, unless `measure_tiling` states otherwise explicitly.
- **The switch is never silent** — it emits an informational line naming the group, the value that
  triggered it, and the fact that the shared-endpoint and gap rules were the continuous ones. An
  inference a reader cannot see is the thing this repo distrusts about inference; an inference that
  announces itself is not that.
- **An explicit `measure_tiling: quantised` beside a fractional value is a contradiction, and warns**
  rather than being overridden in either direction — the author has stated something the data
  contradicts, and picking a winner silently is what a three-valued house algebra exists to avoid.

**Why the inference is safe in this direction and not the other.** Fractional-ness *implies* continuous:
a value between two whole numbers is incompatible with quantised semantics, so there is no
false-positive direction — the warning text 0.6 already ships says as much. Integer-ness implies
nothing: `[0,1] [2,3]` is exactly what a genuinely continuous measure looks like when its author has
only ever seen whole-number data, which is why deriving the tiling *in general* is rejected below. The
asymmetry is the whole reason one direction can be automatic and the other cannot.

**Nothing here refuses a module that validates today.** `measure_min=2.5` on a `copynumbers.csv` row
already loads — the bounds are floats and nothing checks integrality (`binning.py:309-346`) — and after
this change it still loads, and finally gets answered. The one behavioural change to such a table is
that its bins are read under the rules that can answer it, which is a widening. Refusing it instead
would be the tightening P3 bars, the same reasoning that keeps RM5 a widening.

**(c) The 0.6 warning becomes conditional and is reworded.** `binning.py:600-610` fires unconditionally
on every `copynumbers.csv` and `repeat_alleles.csv`. Two things about it stop being true. Its text says
*"a parallel float column is queued for 0.7 and the integer column goes at 1.0"* — the release is wrong
(it is this one), and the column is not the one the sentence means, since the bounds never needed one
and `modifier_cn` is what gets the companion. And its central claim, *"the table is green and silently
unanswerable at every one of its own boundaries"*, stops being true of any table whose **effective**
tiling is continuous — declared or inferred — because those boundaries are now answered. **It must fire
only where it is still true**: a group under quantised tiling, on a kind VCF 4.4 types as fractional.

**`FRACTIONAL_MEASURE_PHRASE` (`binning.py:185`) stays byte-identical**:
it is pinned deliberately (`binning.py:177-184`) and a warning's text is an API. The sentence around it
changes; the phrase a consumer greps for does not.

### Why not a sixth measure kind

The other candidate the entry names, and it is the wrong axis. `measure_kind` answers *what is being
measured*; tiling answers *how the axis is divided*. Folding the second into the first is the `state`
anti-pattern the Constitution names by name (P5: *"a field must not pile up independent axes"*), and it
does not scale — it is a product, not a sum: `copy_number_continuous`, `repeat_count_continuous`, and
then `activity_score_quantised` the first time somebody wants the other direction on the third kind.
A closed vocabulary in its own column is additive in both directions; a kind-per-tiling vocabulary is
additive in neither.

### Other repairs rejected

- **Move `copy_number`/`repeat_count` into `_CONTINUOUS_GAP_KINDS`.** The entry already forbids this
  and the probe confirms why: `[2,2]` beside `[3,3]` is a legal integer tiling today, and continuous
  semantics change **both** the shared-endpoint rule and the gap warning for tables already published.
  It would also be a silent change of meaning rather than a declared one — the author who wrote a
  quantised catalog count would find their table re-read as continuous with no edit and no notice.
- **Derive the tiling from the rows and drop the column** — i.e. make the inference in (b′) the *whole*
  mechanism, so nothing is ever declared. Tempting, and it is a named house pattern
  (`@derived-not-stored`), and half of it is exactly what (b′) does. It fails on the other half, which
  is the one that has to be right: absence of a fractional value implies **nothing**. `[0,1] [2,3]` is
  what a genuinely continuous measure looks like when its author has only ever seen whole-number data,
  so a derivation-only mechanism reads the ambiguous table the wrong way, silently, and gives the
  curator no way to say otherwise. Fractional-ness is evidence; integer-ness is absence of evidence, and
  the house algebra does not let absence of evidence be a value. Hence both: the column for the claim,
  the inference for the case where the data has already settled it.
- **Declare it in `module_spec.yaml`.** Module-level, and this repo has paid twice for assuming a
  per-module answer to a per-table question (RM36's per-CSV build declaration, RM32's gene-scoped PAR
  verdict). A module carrying both a quantised catalog count and a continuous segment mean is not
  hypothetical — `cyp2d6_structural` already carries a copy-number table *and* an activity-score table.
- **Retype the bounds.** Nothing to do: they are already floats. Recorded because "retype the bounds"
  is the first thing this entry's headline suggests, and the answer is that it happened before anyone
  noticed the tiling rules had not followed.

### Charter check

Additive under P3 — two new optional columns on an existing authored table, both defaulted so every
published module validates unchanged and means what it meant. Requiredness is untouched (P8). **No
retype**: `modifier_cn` keeps its `int` and keeps working, which is the whole point of the companion —
the retype is what 1.0 gets to skip, because by then there is nothing left to retype, only a deprecated
column to remove. The deprecation is legal in this minor under the 0.6 cadence amendment because it is
actionable. The evidence-driven switch in (b′) is a **widening**: a table carrying a fractional value
loads today and keeps loading, and the change is that its bins are now read under rules that can answer
it. Nothing that validates today stops validating, and the one refusal added — an explicit
`quantised` beside a fractional value — is a warning, not an error.

Cost is **full** under the 0.6 amendment — two authored columns — paid deliberately and mitigated by
the absent-means-default rule, which means the rare author meets neither unless they have a fractional
measurement or a non-default tiling. `content_signature` moves only on a module that *writes* one of
them, which today is none of them. **`artifact.digest` does move**, though, on every module carrying a
binning table: `_build_table` derives its polars schema from `model.model_fields`
(`compiler.py:407-424`), so `measure_tiling` reaches all four binning parquets and
`modifier_copy_number` reaches `copynumbers.parquet`, all-null or not. Five reference examples are
affected — `cyp2d6_structural`, `fmr1_cgg_repeat`, `htt_repeat_expansion`, `mt_heteroplasmy`,
`mt_common_deletion` — and P4 scopes exactly that to a fixed `compiler_version`.

---

## RM87 — an expanded row is indistinguishable from an authored one, and the weights builder reads only the row

**Severity** medium-high (a consumer produced 3,762 false findings; caught before rendering) · **Owner**
format (schema) + compiler (materializer, reverse) · **Filed** 2026-08-16 from S33 · **Entry**
[ROADMAP_0_7.md § RM87](ROADMAP_0_7.md#rm87--an-expanded-row-is-indistinguishable-from-an-authored-one-in-the-artifact)

### The problem

A one-to-many rsID is paired with every locus it resolves to, so K authored genotypes at that key become
K×N rows in `weights.parquet`, and only the member whose alleles can carry a given genotype can match
it. The others are ordinary well-formed rows — real coordinate, real reference allele, the module's own
conclusion — and nothing on the row says so. 0.6 shipped the artifact-level answer
(`manifest.compilation.expanded_keys` / `expanded_rows`, declared at
`schema/src/just_dna_format/manifest.py:264`, `:268`, whose own docstring at `:260-263` says outright
that it *"deliberately does not substitute"* for the row-level one). The row-level question is open.

### The facts

- **`weights.parquet` has 37 columns and none of them marks an expansion** —
  `compiler/src/just_dna_compiler/compiler.py:5090-5128`. Confirmed by
  `docs/SCHEMAS.md:508-509`, which states the absence as a decision.
- **`_build_weights` reads only from the `VariantRow`** — `compiler.py:5027-5089` is a dict
  comprehension over `v.<field>` and nothing else. So a weights column requires a field **on the row**;
  there is no side channel to smuggle a derived value through, the way `_build_table` could.
- **A plain new field on `VariantRow` would land in `content_signature`.** `VariantRow.variant_key` and
  `authored_ident` are `COMPILER_MANAGED` but *not* `exclude=True` (`schema/src/just_dna_format/spec.py:403-424`),
  which `schema/src/just_dna_format/base.py:302-305` records as **a grandfathered inconsistency, not a
  precedent**. The mechanism that exists for this is `stamped_identity_field`
  (`base.py:290-313`): `default=None`, `exclude=True`, `json_schema_extra=COMPILER_MANAGED`. It is used
  eight times across `HeteroplasmyRow`, `HaplotypeRow` and `PharmVariantRow` (RM43), and `_build_table`
  reads excluded fields off the row by attribute so they still reach parquet (`compiler.py:411-416`) —
  which is exactly what `_build_weights` already does.
- **The stamp site already knows both numbers.** The expansion loop is
  `compiler/src/just_dna_compiler/resolution.py:178-188`: it iterates `_sorted_loci(usable)` and holds
  `usable` whole, so the ordinal is an `enumerate` and the total is a `len`.
- **Reverse recomputes the index by encounter order** — `compiler.py:6046-6062`, working only because
  the weights rows are sorted on it (`resolution.py:854-858`). The positional-table pass hard-codes `0`
  (`compiler.py:6084`).
- **Nothing tests a multi-member sequence surviving the round trip.** The one direct assertion is
  `compiler/tests/test_positional_resolution.py:545`, a single-locus `== "0"`. Two reference examples
  do carry `locus_index > 0` rows (`pathogenic_clinvar`: 9, `hboc_palb2`: 2), but only indirectly,
  through `resolution_signature`.

### The decision

**Two stamped, compiler-managed, `exclude=True` columns on `VariantRow`: `locus_index` and
`locus_count`**, declared through `stamped_identity_field`, stamped at `resolution.py:178-188`,
materialized into `weights.parquet` by `_build_weights`.

Three details that are the whole of the design:

- **`locus_count` defaults to `1`, not `0`.** A non-expanded row genuinely resolves to one locus, and
  `locus_count > 1` has to be the row-level predicate a consumer can apply while holding one row. A
  zero default would make the predicate read `locus_count > 1 or locus_count == 0`, which is the same
  under-determination `locus_index` alone already has and which this item exists to remove.
- **Reverse prefers the stored column and keeps the recompute as the fallback.** An artifact compiled
  before this lands has no column, and P3 requires it to keep reversing. So: read the column when
  present, recompute by encounter order when absent — and a test that the two agree across the corpus,
  which is the test that would have caught the sort dependency the recompute silently relies on.
- **Both are outside `content_signature` and that is the point.** `exclude=True` keeps them out of
  `model_dump()`, so the authored identity of every module is unchanged. `artifact.digest` moves on
  every module that has a `weights.parquet`; the four table-only modules keep even that.

### Why two columns and not one

`locus_count` alone is the cheaper answer and it does carry the predicate. It loses the ability to line
a weights row up with its `resolution.csv` row, which is the other thing S33's reporter asked for and
the only thing that makes the parquet and the lookup table jointly readable. `locus_index` also is not
a new name — it already exists on `ResolutionRow` (`schema/src/just_dna_format/resolution.py:78-82`)
and inside `RESOLUTION_FACT_FIELDS` (`:44`) — so reusing it costs nothing under P5's one-way-door rule
and spelling the same concept differently in the parquet would be the `vrs_id` desync shape again.

### Repairs rejected

- **A single boolean `expanded`.** Cheapest to read, and it forecloses both other options under P5: a
  `bool` cannot later carry an ordinal without a retype, which is major-only. The entry refutes it and
  the refutation stands.
- **`locus_index` alone.** `0` on a non-expanded row *and* on the first member of every expansion, so a
  reader holding one row cannot tell them apart. This is the specific thing S33 asked for and the
  specific reason it is not enough.
- **A plain (non-excluded) field.** Would move `content_signature` on every SNP-core module ever
  published, to record something no human authored — the exact defect RM43's stamped-column mechanism
  was built to avoid, and the one already queued for repair at 1.0 on `VariantRow`'s other two.
- **Publish `resolution.csv` as a parquet.** Refused by the 0.6 charter amendment by name, and it does
  not answer the question anyway: the reader's problem is a row in `weights.parquet` with nothing on it,
  and a second file does not put anything on it.
- **Filter the non-matching member at compile.** Refused for the two reasons COMPILER.md § Resolution
  already gives — a source's allele list is incomplete at least as often as a module is wrong, and
  dropping rows changes what `reverse_module` reads back, which P7 forbids. The reporter argued this
  case against their own first candidate and they were right.

### Charter check

Additive under P3, and the cheapest class the 0.6 amendment recognises (*"a stamped, compiler-managed
column is the cheapest thing this format can add"*). No requiredness change (P8). `artifact.digest`
moves on ~~twelve~~ **nine** of sixteen examples, which P4 already scopes to a fixed
`compiler_version`. *(Measured when the lane landed: nine reference examples carry a `variants.csv`,
not twelve — the other seven are table-only. Nothing else moved on any of the sixteen.)* P7 gains an
obligation rather than losing one: the round trip must now preserve a real `0..N-1` sequence, and a test
must say so.

### Consequence, stated because it follows without being chosen

The positional pass's hard-coded `0` (`compiler.py:6084`) is honest only while those tables never
expand. That is true today — RM43's fill is one locus per row — and it stops being true if RM65 ever
puts coordinates on the repeat and copy-number tables. Not a blocker; a line the RM65 entry should
carry, and this document is the record that it was noticed here first.

---

## RM84 — the publisher writes a path that cannot express a version

**Severity** medium-high · **Owner** enricher (`upload.upload_module`) · **Filed** 2026-08-16 from
MODULE_LIFECYCLE § 6.8 · **Entry** [ROADMAP_0_7.md § RM84](ROADMAP_0_7.md#rm84--a-module-has-no-version-identity-on-the-discovery-path-and-the-publisher-is-the-half-we-own)

### The problem

On the HuggingFace discovery path there is no version in the path, no manifest fetch and no digest
check, so a republished module keeps the same URL and a cached copy shadows it. The only invalidation
is keyed on the *consumer application's own package version* — the identity used to detect "the module
changed" is a property of the reader, not of the module. Half of that is ours: this tier publishes the
layout that cannot express a version.

### The facts

It is one line. `plan_upload` (`enricher/src/just_dna_enricher/upload.py:121-141`) returns
`path_in_repo=f"data/{name}"` at `:139`, and `upload_module` (`:144-166`) does a single
`api.upload_folder` into it. `plan_upload` already receives the compiled `module_dir`, so the manifest —
and therefore the module's version — is in hand at the point the path is built. Nothing else in the
tier reads or constructs that path.

### The decision

**Write both.** Upload to `data/<name>/v<version>/` **and** keep `data/<name>/` as the latest copy, in
the same commit.

The dual write is not a hedge, it is the requirement: the unversioned path is what is deployed, so it
has to keep working and keep meaning *latest*; and a version segment nobody reads is dead bytes while a
reader looking for a segment nobody writes finds nothing. Writing both is what lets the two sides land
independently, which is what makes this cheap enough to do without waiting.

**`v<version>` verbatim from the manifest** — `v0.6.0`, not a bare `vN`. A bare major segment throws
away the rest, so two patch releases of one module would collide at one path, which is the defect being
fixed rather than a smaller version of it.

**One thing to confirm before it ships, and it is theirs:** [S34 § 4](CONSUMER_SUGGESTIONS.md) says
*"if the publisher grows a version segment we will follow it in discovery; the `vN` fallback in our
generic fsspec scan is already the shape"*. Whether their scan matches `v0.6.0` or only `v1`-shaped
segments is a fact about their regex, which this repository cannot assert from its own rules. It goes
to them as an ask in RM27's shape — a question, not an implication — and the publisher writes whichever
spelling they confirm. Nothing else in this decision depends on the answer.

### Repairs rejected

- **A digest segment instead of a version.** Content-addressed, so it never collides and never lies —
  and it is unreadable and unguessable, so a human cannot construct a URL and a consumer cannot ask for
  "the newest" without an index. The registry path already made the opposite choice deliberately
  (`namespace/name/version`, with a comment giving the reason), and having the two paths disagree about
  what a module is addressed by is worse than either.
- **A pointer file.** A second round trip before any fetch, on a path whose whole problem is that
  nothing fetches anything before using the cached copy. It fixes the layout by adding a step the
  broken reader is precisely the one not to take.
- **Migrate everything already published flat.** Not needed, and that is the argument for the dual
  write: the flat path keeps being written, so every module already published stays exactly where it is
  and keeps resolving.

### Charter check

Enricher-only. No schema, no model, no parquet, no manifest field, no digest, no signature. Outside the
format/compiler tiers entirely, which is why it can ride in this batch without touching anything else
in it.

---

## RM72 — the verification vocabulary is half-wired, and the contract that blocks it is a blanket over a narrow reason

**Severity** medium · **Owner** enricher · **Filed** 2026-08-14 from DOGFOOD_0_6_FINDINGS § D4 ·
**Entry** [ROADMAP_0_7.md § RM72](ROADMAP_0_7.md#rm72--six-verification-members-still-emitted-by-nothing-and-the-writes-nothing-contract)

### The problem

Four of the seventeen `VALID_VERIFICATION_CHECKS` members are emitted by nothing:
`gene_symbol_currency`, `trait_currency` and `gene_locus_agreement` belong to `check-identifiers`;
`acmg_secondary_findings` belongs to `check-acmg`. Both commands put a real authored-versus-source
question, report the answer to stdout, and let the record die with the process — which is the sentence
RM45's own docstring opens with as the thing it exists to fix. Wiring them is blocked on the two
commands' printed promise that they write nothing.

### The reasoning that settles it

These are **checks**. The apply route is wrong and stays wrong — filling `acmg_sf` or a gene symbol from
the registry being asked about it is what `hints.REDUNDANCY_BEARING` exists to prevent, and it makes the
comparison vacuous. An **open-ended check**, where the answer is reported and the downstream decides
what to do with it, is a legitimate route and is what these two already are.

What follows is narrow and it decides the item. Recording *that the check was run* has exactly one
possible home on our side: `verification.json`. It cannot be offloaded downstream, because a consumer
holding the artifact has no way to distinguish "asked and clean" from "never asked" — that collapse is
the whole of RM45. It cannot go in the authored section, because there is no field for it and there
should not be: an author does not attest to a check they did not run. So: **if we want to discern the
two states, we write.** There is no third option, and the "Writes nothing" promise is what stands
between the code and the only available answer.

### The facts, which price the reword at a fraction of what the entry feared

The entry treats the reword as expensive on the grounds that the promise is *"a published contract in
both CLIs, both package references and the skill"*. Enumerated:

- **Thirty-seven sites carry some form of the promise. Three carry the one being changed.**
  `enricher/src/just_dna_enricher/cli.py:773-774` (`check-identifiers`),
  `enricher/src/just_dna_enricher/cli.py:815-817` (`check-acmg`), and their doc mirror at
  `docs/ENRICHER.md:2238-2239`.
- **Every other site is a different promise, and none of them changes.** `hint` and `lookup` promise not
  to write an *authored cell* (`enricher/cli.py:1515`, `compiler/cli.py:584`,
  `enricher/src/just_dna_enricher/lookup.py:6`, `compiler/src/just_dna_compiler/hints.py:1-4`);
  `validate` promises not to stamp a closure (`docs/COMPILER.md:1198`, `docs/FAQ.md:137`,
  `docs/SCHEMAS.md:1245`); `--dry-run` promises not to write at all. Those are the promises worth
  keeping blanket, and they keep it.
- **The `create-module` skill needs no edit.** Its command tables annotate `hint` (`SKILL.md:570`,
  `:596`) and `validate` (`:571`) with "Writes nothing" — and its `check-identifiers` and `check-acmg`
  rows (`SKILL.md:592-593`) carry **no such annotation**. The reader with no checkout, whose existence
  is the entry's strongest argument, was never told these two commands write nothing.

Two stale things found in passing and repaired in the same lane, because both are the drift their own
neighbours warn about:

- `enricher/src/just_dna_enricher/verification.py:20-25` says the recorders are *"`enrich` (four
  checks), `literature` (three) and `clinpgx` (one)"*. There are **five** call sites — `pgx.py:586` and
  `cli.py:1500` (`vrs mint`) were added and the sentence was not — and `enrich` emits **five** members,
  not four. The next sentence of that same docstring is a warning against exactly this.
- RM72's own citations have drifted: it cites `cli.py:740-741` and `:782-784` for text now at `:773-774`
  and `:815-817`, and `cli.py:1447` / `compiler cli.py:533` for docstrings now at `:1515` / `:584`.

### The decision

**Four parts.**

**(a) Wire the four members, unconditionally.** `check-identifiers` records
`gene_symbol_currency`, `trait_currency` and `gene_locus_agreement`; `check-acmg` records
`acmg_secondary_findings`. No flag. A `--attest` switch is refused for the reason the entry already
gives and the user's reasoning restates: an optional record is ambiguous between "the check was not
run" and "it ran without the flag", which reintroduces the two-readings-of-one-absence defect the skip
vocabulary was built to end. A record is unconditional or it is absent by design.

**(b) Reword the three sites, separating two claims the blanket ran together.** The new promise is
*writes no authored cell, and records that the question was put* — with the `hints.REDUNDANCY_BEARING`
reason kept verbatim, because that reason is the one that must not be softened. The wording must not
read as an invitation to `--apply`; naming the record as *an attestation, never a value* is what keeps
the two apart.

**(c) Fix the merge rule: within a check, a `ran` record is not replaced by a `skipped` one.**
`merge_records` (`schema/src/just_dna_format/verification.py:285-298`) is unconditional newest-wins per
check — a plain `dict.update` — and an offline `literature` re-run, a documented no-op, rewrote a real
`subjects=2 findings=1` record to `subjects=0 findings=0 skipped=offline`.

The argument is the function's own docstring, applied one step further than it currently reaches: *"A
check absent from `fresh` keeps its earlier record: a run that did not put a question has said nothing
about it, and deleting the older answer would turn 'not asked this time' into 'never asked'."* A
`skipped(offline)` record **is** a run that did not put the question — the same fact, spelled as a
record instead of as an absence — so the argument that protects the absent check protects this one, and
newest-wins performs the deletion the docstring refuses. Newest-wins still holds between two records of
the same disposition.

This is load-bearing rather than tidy, and (a) is why: every check wired from here on merges through
this function, so wiring four more members into a rule that can silently downgrade them multiplies the
defect by four.

The counter-argument is real and is answered rather than dismissed: a reader may legitimately want to
know that today's enrichment could not reach the source. That is a fact about **the run**, not about
**the check**, and `verification.json` is a per-check document. If the run-level fact is wanted it needs
a run-level place, which is a different question and is not opened here.

**(d) Say on its own line whether a member is wired or reserved.** `gene_disease_validity` argues its
reservation in the code (`schema/src/just_dna_format/vocab.py:637-642`); `dosage_sensitivity`
(`vocab.py:672`) is reserved for a pass that does not exist and nothing says so. That asymmetry is why
D4-1's headline count of twelve read wrong the first time. A comment per member, and it is free.

### Repairs rejected

- **Wire them and leave the docstrings.** Ships two commands whose printed contract is false. Cheap and
  dishonest, and this repo has measured what a false printed contract costs.
- **Fold both checks into `enrich`.** They are separate commands because they are separately expensive
  and separately optional (OLS4, HGNC, the ACMG page), so this makes every enrichment pay for them —
  and it contradicts `merge_records`, whose whole purpose is that two commands write into one document.
- **Drop the unreachable members.** The one move P3 bars outright: the vocabulary is closed and
  permanent within a major, so a removed member cannot return until 1.0.
- **Wire the two reserved members too.** Would report a check where no question was put, which is the
  confusion RM45 exists to end. They stay reserved; (d) is the entire change they get.

### Charter check

No schema change, no model, no parquet, no manifest field beyond what `manifest.verification` already
carries. `VALID_VERIFICATION_CHECKS` is unchanged — every member wired here is already in it, which is
the vocabulary's own stated reason for having been written whole. The merge-rule change alters what a
*re-run* leaves behind, never what a first run writes, and it can only preserve information the current
rule deletes.

### The general question, and what this decides of it

The entry asks whether a check that reports to stdout and writes no record is a defect or a legitimate
read-only surface. This decides it **for the two commands that put an authored-versus-source question**,
on the membership rule `VALID_VERIFICATION_CHECKS` already states, and leaves `hint` and `lookup`
read-only on purpose. The line is not *does it write* but *does it compare something the module asserts
against what a source says* — a surface that puts that question owes a record of having put it; a
surface that answers a question about a value owes nothing.

---

## RM82 — the attestation binds raw bytes, and `size` is inside the binding

**Severity** low-medium · **Owner** format (`verification.module_binding`) · **Decided** 2026-08-16,
**built 2026-08-17** · **Entry** [ROADMAP_0_7.md § RM82](ROADMAP_0_7.md#rm82--the-attestation-binds-raw-bytes-so-an-editors-line-endings-un-close-a-module)

### The problem and the standing decision

Rewriting an authored CSV with different line endings changes no value, no digest and no signature — and
still drops the attestation and the closure. An author whose editor normalizes newlines, or whose Git
does it through `core.autocrlf`, un-closes their module without touching a cell. The decision was taken
on 2026-08-16: **normalize `\r\n` → `\n` on the bytes before hashing, and stop there.** It is a byte
transform needing no loader, no parse and no schema knowledge, which is what separates it from the
content-aware binding RM45 refused. It is carried into this document as a build item, not re-argued.

### What probing added, and it is the whole implementation

**Confirmed unbuilt.** `sha256_file` (`schema/src/just_dna_format/integrity.py:71-77`) opens `"rb"` and
streams raw chunks into `hashlib`. There is no `\r\n` handling anywhere in `schema/src`, `compiler/src`
or `enricher/src`.

Two facts the entry does not carry, and the second one is a defect in the naive fix:

- **`module_binding` *is* `artifact_digest`.** `schema/src/just_dna_format/verification.py:79-90` is one
  line: `return artifact_digest(list(entries))`, over entries built by
  `authored_input_entries` (`compiler/src/just_dna_compiler/compiler.py:332-346`). That is the **same
  function** as the artifact's own Merkle root (`integrity.py:92-112`). So the normalization must not go
  into `sha256_file` or `artifact_digest`: those also serve `manifest.inputs[]` and `artifact.digest`,
  which the decision says explicitly must **not** follow.
- **`size` is inside the hashed listing.** `file_entry` stamps `size=path.stat().st_size`
  (`integrity.py:80-83`), and `artifact_digest` hashes `{"name", "sha256", "size"}` per file
  (`integrity.py:106-112`). A CRLF file and its LF twin differ in length by one byte per line. **So
  normalizing the digest input while reporting the on-disk size still moves the binding, on exactly the
  files the fix exists to protect** — the naive implementation is a no-op that looks like a fix and
  would pass a test asserting the hash changed.

### The decision

**A separate normalized entry builder, used by the binding and by nothing else** — a sibling of
`file_entries` that reads the bytes, replaces `\r\n` with `\n`, and reports **both** the digest and the
length **of the normalized bytes**. `authored_input_entries` calls it; `manifest.inputs[]` and
`artifact.digest` keep calling `file_entries` unchanged.

**A distinct function rather than a `normalize=True` flag on `file_entries`.** The house rule is that a
flag must mean the same thing in every function that takes one, and a boolean that silently changes
*what a hash is over* is the opposite of that: a caller who passes it by habit re-baselines
`manifest.inputs[]` with no error and no warning. Two functions cannot be confused at a call site.

**The stopping point is newlines, and it is chosen rather than inherited.** A BOM, trailing whitespace
and a missing final newline are the obvious next steps, and each makes the binding more content-ish
without making it content. Newlines are the one difference a *tool* introduces on a file the author did
not edit; the others are things a human typed. If a real case arrives for one of them it is additive
(P3) and gets argued then, on its own evidence.

### The cost, measured

- **Twelve files per module** are covered — `_INPUT_FILES` (`compiler.py:259-264`), an explicit tuple,
  not a glob; `module_spec.yaml` plus eleven CSVs, all line-oriented.
- **All sixteen reference examples are closed** (16 of 16 carry a `verification.json` with a real
  `closure`), so all sixteen re-close, in the same commit as the change.
- **A one-time invalidation of every `module_hash` in existence**, and it is a **soft** break: a stale
  attestation warns and is dropped (`compiler.py:4780-4834`), it never fails a build. **Measured on
  build: 7 of 16, not 16 of 16** — a binding moves only where an authored file really carries `\r\n`,
  and the nine that did not kept their records, producer and nonce verbatim through the re-close.
  Which half of the corpus is CRLF is the surprise: `csv.writer`'s default terminator is `\r\n`, so it
  is the *machine-written* files, and the rewrite an author really performs is the normalization to LF.
- **No test fixture needs rewriting.** No test anywhere hardcodes a real digest — the only constant is
  synthetic (`schema/tests/test_verification.py:35`, `"sha256:" + "ab" * 32`), and every other test
  recomputes the binding from its fixture. The one test whose *semantics* shift is
  `schema/tests/test_verification.py:223-226` (a value edit still moves the binding, so it still
  passes). **Nothing currently tests the CRLF case in either direction**, and both directions need a
  test: a CRLF rewrite must not move the binding, and a value edit must still move it.

### Charter check

No schema change, no authored surface, no vocabulary. The binding is a derived attestation over derived
bytes; P3's additivity is not engaged because nothing published becomes invalid — a dropped attestation
is a warning and a re-close. `manifest.inputs[]` and `artifact.digest` are deliberately untouched, which
is coherent rather than an inconsistency to tidy later: those answer *are these the exact bytes*, and
that is a different question.

---

# Not taken, and why

Sixteen items, seventeen rows — RM55's removal half is listed separately from its fix. Each reason is
the item's own stated blocker unless marked otherwise: nothing here is newly deferred on a new argument,
and nothing is deferred because of the digest.

| Item | Where | Why not now |
|---|---|---|
| **RM16** authored PRS weights | [0.7](ROADMAP_0_7.md#rm16--authored-prs-weights-a-scoring-file-not-a-manifest) | Full-cost authored table; unblocks on a real consumer combining authored weights, which does not exist. Fixing the shape now spends a one-way door on a guess. |
| **RM23** `predictions.csv` | [0.7](ROADMAP_0_7.md#rm23--computational-predictor-scores-as-a-table) | Full-cost authored table; both blockers unmoved — per-transcript grain undecided, acquisition unmeasured. A research task, not a schema task. |
| **RM28** meta-conclusions (predicate half) | [0.7](ROADMAP_0_7.md#rm28--meta-conclusions-the-predicate-half) | Parked on a corpus that is ~70% built. The cofactor half already closed; what remains is open-world negation, which no operator fixes. |
| **RM55** removing `modifier_cn` | [1.0](ROADMAP_1_0.md#rm55-removal-half--the-integer-copy-number-and-repeat-count-columns) | Removal is what the amended rule reserves for a major. The column is *deprecated* here, which needs no major, and 1.0 drops it — so 1.0 inherits a removal rather than a retype. |
| **RM56** (policy half) | [0.7](ROADMAP_0_7.md#rm56-policy-half--the-rule-for-a-measurement-that-spans-bins) | Prerequisite is a real caller VCF, so the closed vocabulary is fixed against what callers emit rather than a guess. 0.6 ships withhold plus an explicit not-implemented warning. |
| **RM65** positional repeat/CN tables | [0.7](ROADMAP_0_7.md#rm65-implementation-half--repeat-and-copy-number-tables-are-positional) | Same caller-VCF prerequisite. Also takes RM43's fill lane from three tables to five. |
| **RM66** several motifs per locus | [0.7](ROADMAP_0_7.md#rm66--one-repeat-locus-several-motifs) | Filed beside RM65 so both arrive with the same evidence; a keying change on a shipped table, the expensive kind. |
| **RM67** polyploid genotypes | [0.7](ROADMAP_0_7.md#rm67--polyploid-and-partially-phased-genotypes) | **Not work** — a documented divergence. The message was fixed on 2026-08-14; the decision did not change. |
| **RM68** drafting on a non-GRCh38 module | [0.7](ROADMAP_0_7.md#rm68--a-drafting-provider-on-a-non-grch38-module-refuse-or-strip-to-the-rsid) | Blocked on RM15, which dissolves the premise. Both candidate behaviours are refuted; the warning shipped in 0.6. A behaviour fixed before RM15 is one RM15 would have to undo. |
| **RM69** `resolution_signature` off GRCh38 | [0.7](ROADMAP_0_7.md#rm69--resolution_signature-is-not-a-round-trip-invariant-when-the-positional-fill-is-skipped) | Blocked on RM15. A documented limit of P7, not a breach — P7's own stated remedy points at a blocker P7 cannot remove. |
| **RM70** `requires_callable` on the PGx tables | [0.7](ROADMAP_0_7.md#rm70--requires_callable-is-variantrow-only-so-no-pgx-table-can-state-cpics-core-assumption) | Two **authored** columns, full cost twice, on the layer the rare human writes; the unblock condition — a real module whose author wants to state it — is unmet. Additive, so nothing waits on a version. |
| **RM71** the drafted-stub allele worklist | [0.7](ROADMAP_0_7.md#rm71--the-alleles-a-drafted-genotype-stub-must-be-written-from-are-in-no-file) | Every candidate that writes is refuted; the one survivor puts the worklist in a *third* place while the complaint is that it is not in the one being edited. The open question is where an author does this work, and this repo has no model of that. |
| **RM83** sidecar refresh | [0.7](ROADMAP_0_7.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold) | A new command, and the blocking sub-question stands: nothing records that a row was overridden, so "keep the overrides" is not implementable. Tier ownership undecided. Decide with RM85. |
| **RM85** origin and source drift | [0.7](ROADMAP_0_7.md#rm85--the-origin-of-a-module-predicts-the-shape-of-its-second-pass-and-nothing-records-it) | The same *has the world moved* question as RM83, asked about the release label instead of the rows. Deciding them separately is how one gets a shape the other has to undo. |
| **RM86** the review pass downstream | [0.7](ROADMAP_0_7.md#rm86--a-review-pass-is-legal-at-the-gate-refused-by-the-pre-flight-and-invisible-once-published) | Two thirds is the registry's, filed as their S10–S12; the third that is ours is a documentation decision that waits on their S12 reply. |
| **RM50** the optional PMCID column | [ROADMAP.md](ROADMAP.md) | The guard shipped as an enricher patch. The column is additive but the entry pairs it with the 1.0 `StudyRow.pmid` requiredness demotion, and both want settling in one release. |
| `weights.parquet` `end` | [ROADMAP.md](ROADMAP.md) 1.0 tracker | Minor-legal since the amendment, and its real blocker is unmoved: whether an `end` is interbase-half-open or inclusive is the same choice RM15 must make. |

**RM15 is the load-bearing absence.** Three of the sixteen are blocked on it directly and a fourth is
paired with it. It is a 1.0 item for identity-semantics reasons that have nothing to do with the digest,
and it is not made more urgent by this list — but the list is the honest measure of what it is holding.

---

# Implementation plan

## Ordering

Five lanes. **A, B, C and D are independent and can land in any order. E lands last**, because it
re-closes all sixteen reference examples and any lane that changes an authored file or an artifact
before it would make that closure immediately stale.

- **Lane A — RM55.** `schema/src/just_dna_format/binning.py` (the `measure_tiling` vocabulary and
  column, the group-agreement check, `modifier_copy_number` + its effective-value alias + the
  both-set refusal + the `modifier_cn` deprecation, `_KEY_FIELDS` reading the effective value, the gap
  and shared-endpoint rules reading the **effective tiling** — declared, else inferred from a fractional
  value, else the kind's default — plus the informational line the inference emits, the
  declared-quantised-beside-a-fractional-value warning, and the reworded RM55 warning),
  `compiler/src/just_dna_compiler/compiler.py` (`_check_measure_shape`; and `_polars_type` already
  handles the new column, but `copynumbers.parquet` gains one and that wants checking rather than
  assuming), `compiler/src/just_dna_compiler/hints.py` (`_check_bins`).
- **Lane B — RM87.** `schema/src/just_dna_format/spec.py` (two `stamped_identity_field` declarations),
  `compiler/src/just_dna_compiler/resolution.py` (the stamp at the expansion loop),
  `compiler/src/just_dna_compiler/compiler.py` (`_build_weights` record dict + polars schema; the
  reverse prefer-stored-else-recompute).
- **Lane C — RM72.** `enricher/src/just_dna_enricher/cli.py` (two docstrings, two record calls),
  `enricher/src/just_dna_enricher/identifiers.py` and `acmg.py` (the records),
  `enricher/src/just_dna_enricher/verification.py` (the stale docstring),
  `schema/src/just_dna_format/verification.py` (`merge_records`),
  `schema/src/just_dna_format/vocab.py` (the wired/reserved comments), `docs/ENRICHER.md`.
- **Lane D — RM84.** `enricher/src/just_dna_enricher/upload.py` alone, plus the ask to the consumer.
- **Lane E — RM82.** `schema/src/just_dna_format/integrity.py` (the normalized builder),
  `compiler/src/just_dna_compiler/compiler.py` (`authored_input_entries`), then re-close all sixteen
  examples.

## Shared-file hazards

- **`compiler/src/just_dna_compiler/compiler.py` is touched by A, B and E**, in three unrelated regions
  (`_check_measure_shape` ~1429, `_build_weights` ~5020 and the reverse writers ~6032, and
  `authored_input_entries` ~332). Serialize the lanes rather than the edits.
- **A and B both move `artifact.digest`, and neither moves a `content_signature`.** A moves it on the
  five modules carrying a binning table (the parquets gain all-null columns, because `_build_table`
  derives its schema from the model); B on the twelve carrying a `weights.parquet`. Take the corpus
  signature baseline **once, before either**, and attribute each move to its lane rather than reading a
  combined diff — with five and twelve overlapping, a combined diff is unattributable.
- **E's re-close must be the last commit of the batch.** A closure taken before A or B lands is stale
  by the time the batch ends, and a stale closure is a warning that would be read as E having failed.

## Standing requirements for every lane

- `uv run pytest` green, `ruff check` clean — the gate means something and a finding gets fixed, never
  reported.
- **The four-signature corpus sweep** before and after: `artifact.digest`, `content_signature`,
  `source_signature`, `resolution_signature`, read from where each actually lives — `resolution_signature`
  is on `manifest.compilation`, and the D6 sweep compared `None == None` for eleven examples for the
  whole of 0.6 by reading it off the manifest root.
- **Every claimed movement is measured, not predicted.** This document predicts A moves five digests
  and no signature, and B moves twelve digests and no signature. Both are claims to check, not results.
- **A new ordering or a new round-trip obligation gets a real test.** Lane B owes the one nobody wrote:
  a multi-member `0..N-1` sequence surviving `compile → reverse → compile`.
- **The RM_TOC row and the roadmap status line move in the same commit as the code.** That is the
  unfindable-item rule, and this batch is filed against a document that only exists because it was once
  broken.
- **Documentation is part of the lane, not after it**: SCHEMAS for A and B, COMPILER § Resolution for B,
  ENRICHER for C and D, MODULE_LIFECYCLE for E, CHANGELOG for all five, and the `create-module` skill
  for A alone — the new authored column is the only thing in this batch an author ever types, and the
  skill stays fully dereferenced when it says so.

---

# Provenance

Sorted on 2026-08-16 from [ROADMAP_0_7.md](ROADMAP_0_7.md) and [ROADMAP.md](ROADMAP.md)'s open items,
against [CONSTITUTION.md](CONSTITUTION.md) read in full. The candidate pool is every item filed while
0.6 was open: RM68–RM72 (dogfooding, 2026-08-13/14), RM82–RM87 (the lifecycle pass, 2026-08-16), the
VCF 4.4 tail RM55/RM56/RM65/RM66/RM67 (2026-08-13), and the three long-parked additive tables
RM16/RM23/RM28.

Three entries were overturned by probing before they were decided, which is the reason this stage
exists at all:

- **RM55's suggested fix names a column that mostly does not exist** — the bin bounds have been
  `float | None` since 0.4, `_INTEGER_KINDS` has one reader, and the unstated half of the defect is that
  the shared-endpoint rule *refuses the tiling that would fix it*.
- **RM82's naive implementation is a no-op that looks like a fix** — `size` is inside the hashed
  listing, so normalizing only the digest input still moves the binding on the CRLF files the change
  exists for.
- **RM72's reword is three sites, not the printed-contract surface the entry feared** — and the
  `create-module` skill, whose reader-with-no-checkout is the strongest argument in the entry, does not
  annotate either of the two commands being changed.

RM72's decision follows the maintainer's reasoning of 2026-08-16, recorded here in the form it was
given: these are checks, so the apply route is wrong and an open-ended check is a valid route; a
`--attest` switch is wrong; the only place *"was this check run"* can live on our side is
`verification.json`, it cannot be offloaded downstream, and the authored section has no field for it —
so if we want to discern the two states, we write.
