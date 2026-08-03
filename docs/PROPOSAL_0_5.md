# Proposal — 0.5 design threads (carried forward from the 0.4 proposal)

**Status: proposal / forward design — nothing here is shipped.** This is the *"means → draft schema
→ decision"* stage of the design cycle (CLAUDE.md → *The design cycle*) for the **0.5** milestone. It
holds the design threads that the 0.4 round **deliberately did not take**, moved here when the 0.4
proposal was retired (its shipped decisions now live in [`CHANGELOG.md`](CHANGELOG.md), 2026-07-10 and
the 0.4.0 branch-review passes).

The concrete deferred-item tracker (`RMn`) stays in [`ROADMAP.md`](ROADMAP.md); this doc is the
design discussion behind the 0.5-scope rows, the same way the 0.4 proposal sat beside the roadmap.
Everything below stays inside the Constitution (declarative-not-code, additive-within-a-major,
orthogonal axes, reserved namespace, the `frozenset[str]` vocabulary idiom).

---

## Carried forward — genuinely deferred (not built in 0.4)

### D1 — Authored PRS weights (a scoring file, not a manifest) → ROADMAP RM16

0.4 shipped `pgs.csv` as a **manifest of PGS Catalog IDs** with the ancestry-validity one-way-door
fields (`training_ancestry`, `training_cohort`, `match_rate_floor`, `research_tier`) — *not* authored
per-variant weights. The reasoning holds: just-prs resolves a `PGSxxxxxx` id to a harmonized scoring
file itself and scores each id independently, so inlined per-PGS weights would be dead data, and a
PRS yields a Z/percentile *within a matched reference distribution* — a shape the format does not bin.

**Deferred means:** an authored `effect_allele` + `effect_weight` scoring file (the separable, heavier
form) for the case a module must ship weights the PGS Catalog does not host. It is a distinct table
kind, digest-bearing (new parquet), and only worth building against a real consumer that combines
authored weights into a score. Parked as **RM16** in the roadmap; do not build speculatively.

### D2 — Complex-VNTR motif-path / declarative allele-string grammar → RM5 / round-3 escape hatch

0.4's `repeat_alleles.csv` bins a plain `repeat_count` keyed on `(gene, repeat_unit)`. The complex-VNTR
**motif-path** form (DAT1 `A-A-B-C-D-…`, where a bare count is too coarse) was **reserved as the home
for the Constitution's sanctioned declarative-grammar escape hatch** (a regex/pattern over an allele
string — Principle 1, data not code), *not* built. It is a near neighbour of:

- **RM5** (symbolic / structural alleles beyond `^[ACGT]+$` — 5-HTTLPR S/L, `<DEL>`/`<INS>`/`<STR n>`),
- the **round-3 STR-microvariant** note (forensic `full.partial` allele names like TH01 `"9.3"`, which
  is *not* the float 9.3 — a distinct allele *string*, never smuggled into a numeric bound).

**Deferred means:** a declarative allele-string pattern column (author-time `re.compile`-checked,
consumer-side ReDoS-safe match), reusing the `source_field`/`provenance_regex` pattern-grammar idiom.
Build it only when a real module's count proves too coarse; until then it stays an escape hatch, not a
required shape.

### V1 — Enforce SemVer on `module.version` (0.4.1's advisory preview → 0.5 rule) → ROADMAP RM17

0.4.1 genuinely adopted `module.version` as a **freeform advisory** field (the whole pre-0.4 corpus
carries an informal `v2`/`3`; see [`PROPOSAL_0_4_1.md`](PROPOSAL_0_4_1.md)). It ships the coercion
algorithm now — `just_dna_format.normalize.normalize_version` — but uses it **read-only**: the compiler
*previews* what a future release will read (warning `v2` → *"will read it as `2.0.0`"*, silent on a
clean `1.2.3`).

**0.5 means:** promote `normalize_version` from preview to **enforcement** on `ModuleInfo.version` — a
`field_validator` that coerces the authored value to canonical `MAJOR.MINOR.PATCH` (or a strict
validator that rejects a non-coercible value, TBD below). The algorithm as built: strip every char
that is not a digit or the `.` separator, split on `.`, take the first three fields (empty/absent → `0`,
leading zeros dropped), right-pad to three — so `v2`→`2.0.0`, `1.5`→`1.5.0`, `1.2.3`→`1.2.3`
(idempotent), a no-digit value → `0.0.0`.

**Charter check:** still **out of `artifact.digest`** (identity metadata) and additive — coercion
*accepts* the same inputs 0.4.1 does, just normalizes them, so it does not tighten requiredness (P8) or
move digest bytes (P3). Once enforced, an authored SemVer flows straight into `Identity.version` (0.4.1
already does this for already-clean values).

**Open questions for 0.5:**
- **Coerce vs. reject.** Coercing (`v2`→`2.0.0`) is maximally compatible and matches the preview an
  author already saw; strict-reject is louder but re-breaks the corpus 0.4.1 just unbroke. Lean:
  **coerce**, keeping the authored string recoverable if a consumer wants the verbatim marker.
- **Separator.** The field report said "comma-separated fields"; a version delimiter is conventionally
  `.`. Confirm the delimiter (the built algorithm uses `.`) before enforcing.
- **Round-trip.** Coercion must stay idempotent (`normalize_version(normalize_version(v)) ==
  normalize_version(v)` — already tested) so compile → reverse → recompile does not oscillate.

---

## Settled in 0.4 — do not reopen

Recorded here as forward-design guardrails so these are not re-proposed for 0.5:

- **One physical binning table** (the field-notes' literal B0). **Rejected** in favour of
  **per-quantity tables sharing one column vocabulary** — the natural keys differ per quantity and
  PRS is ancestry-conditional, so one table would contort the frozen shape. The single "bin-a-measure"
  consumer code path (the actual win) comes from the shared vocabulary, not one table.
- **Tuple binning keys** (`(gene, count)` crammed into one cell). **Rejected** in favour of
  **explicit named columns (multicolumn keying)** — legible to a CSV reader, queryable per-component,
  order-independent. A tuple-as-key is a coder reflex, not a protocol idiom. (Coding-standards call,
  firm; this is why B4's SMN modifier is `modifier_gene`/`modifier_cn`, two columns, not a tuple.)

---

## G1 — gnomAD v4.1: population frequency, gene constraint, and VRS identity → **built in 0.5**

The design thread behind [USE_CASES.md §6](USE_CASES.md) and the two new sidecars. Recorded here with
the reasoning, because several of the decisions were made *against* the plan's own expectations once the
assumptions were probed.

### The shape

gnomAD enters in three roles, deliberately different in kind: a **resolution link** (no schema change,
appended last), an **allele-frequency pass** (`frequencies.csv`, variant-level), and a **gene-constraint
pass** (`gene_metrics.csv`, gene-level). Each sidecar is injected, machine-produced, human-overridable,
fact-hashed, and compiled into its own optional parquet. The three-parquet SNP core is untouched.

### Decisions, and what changed under probing

**Ancestry vocabulary: open and seeded, not closed.** Principle 6's default is a closed `frozenset`, and
this is a deliberate exception: the table must stay *source-independent*, and TOPMed / ALFA / 1000G bring
their own labels. A closed set would make a source swap a schema change. What makes a label interpretable
is `dataset`, not membership.

**`allele_frequency` derived, not stored.** AC/AN are integers and round-trip through CSV exactly; a
stored float invites formatting drift (a P7 idempotency hazard) to duplicate one fact in two columns. The
parquet materializes it as a real `Float64`, so the machine artifact still hands consumers the number.

**VRS: minted, not merely recorded — and the dependency story inverted twice.** The plan's first draft
deferred minting because "computing a VA needs `seqrepo`/`biocommons.hgvs`". Probing killed that: the
*identification* step is `sha512t24u` over a compact canonical JSON, reproducible in ~20 lines of stdlib,
so the format tier mints substitutions with **no new dependency at all**. The plan then assumed the
remaining half — indel *normalization* — needed `ga4gh.vrs[extras]` (`seqrepo` + `pysam` + `hgvs`: a
compiled extension and a multi-gigabyte local sequence store), and quarantined it to `[dev]`. Probing
killed that too: core `ga4gh.vrs` with the seqrepo **REST** data proxy normalizes over HTTP for 14
pure-Python packages. Reading a remote sequence is exactly what a network tier is for, so complete allele
identity became a **core** enricher capability rather than an opt-in extra, with `--offline` the only
thing that degrades it to substitutions-only.

A further correction: the plan explained the 1.x/2.0 allele-id stability by saying the allele is
serialized over the location's *content*. It is not — the allele embeds the location's **digest**. The
*conclusion* (our id equals gnomAD's) is right and is now pinned by ground-truth tests; the stated
mechanism was wrong, and the serialization was settled empirically against recorded ids rather than by
reading spec prose.

**The identity switch rides 0.5.0's unpublished window.** `variant_key` derives from the VA for a
resolved substitution. This is legal *now* because `variant_key` is derived and frozen, never authored —
so no authored schema, no DSL, and no human author is touched. It is "major-only" for exactly one reason:
the column is in `weights.parquet`, hence in `artifact.digest`. That gate is **publication**, not the
version number, and 0.4 is the published line while 0.5.0 never shipped. Doing it before any 0.5.0 module
exists costs one re-baseline and breaks no published artifact.

**Substitutions only.** An indel keeps its coordinate key rather than an enricher-minted one. The plan
wanted indels keyed on their normalized VA, but that cannot hold: the key is frozen at row load in the
format tier, and re-keying from an enricher-supplied id would make `artifact.digest` depend on whether an
optional network call succeeded. Indels get an interoperable `vrs_id` **column** instead — identity stays
reproducible, interoperability is still recorded.

**The two gene-constraint routes are different releases.** The plan wanted a test asserting the snapshot
and the live API agree for BRCA1 within float tolerance. They do not, and should not: the live
`gnomad_constraint` field serves **v2.1.1** while v4.1 ships only in the bulk file (BRCA1 LOEUF 0.928 vs
0.885, same MANE transcript). They are labelled as the different datasets they are, and the test asserts
the *difference*.

### Verify severity

A stored `vrs_id` is recomputed at compile time. A **substitution** mismatch is an error in both modes
(deterministic here, so it can only be corruption); an **indel** is a warning in `best_effort` (minted
against a sequence proxy, carried unverified) and an error in `strict` (whose contract is
byte-reproducibility, so an unverifiable identity has no place in it).

### Still deferred

Multi-build VRS minting (a second refget table — the remaining half of RM15), HGVS *generation* as a
feature, and an offline frequency snapshot (58 GB / 742 GB — parked, not scheduled).

## G2 — Pharmacogenomics: per-genotype annotations and source licensing → **built in 0.5**

The design thread behind RM20/RM21/RM22. It began as "add a PharmGKB fetch pass to the enricher" and
grew twice, both times because real data contradicted a shape that had been validated against a
hand-authored sample.

### What probing overturned

**`api.pharmgkb.org` is dead.** Retired 2026-07-20; the successor is `api.clinpgx.org`, paths and
formats unchanged. ClinPGx is the umbrella that merged PharmGKB, CPIC and PharmCAT.

**PharmGKB annotations are per-genotype, and per-category on top of that.** RM3 modelled
`PharmVariantRow` on the *summary* table (variant → drug → level) and never met the per-genotype child
table. Two rounds of correction were needed — first `genotype`, then `phenotype_category` +
`annotation_id` — and the second round only surfaced because the reference example was built from the
real corpus. Numbers and the argument are in [`USE_CASES.md` § 2b](USE_CASES.md).

**No PGx source is sellable, and CPIC is not an escape hatch.** All three are CC BY-SA 4.0 *plus* a
contractual bar on sale, so a bare "CC BY-SA" line must not be read as permission to sell. CPIC's
licence page 302-redirects to the ClinPGx policy. PharmVar's API also became key-gated
(`Api-Key` header, 2 rps, personal key).

### The shape

`sources.csv` → `SourceRow`, one row per **(source, layer)**, carrying the licence, a pinned
`license_sha256`, attribution, notice, tri-state `share_alike`/`commercial_use`, and the acquirer's
`declared_use`. Compiled to `sources.parquet`, fact-hashed by `source_signature`, summarized into
`manifest.sources`. Enricher passes 5 (`pgx.py`, live PharmVar/CPIC) and 6 (`clinpgx.py`, offline
snapshot) produce it.

### Charter check

- **Principle 2 (inject-only).** A source→licence map in the compiler would give it a source
  convention — the exact thing the 0.5 tightening removed — and would be an un-injected reference. The
  licence therefore travels as data, read by the enricher from the bytes it downloaded. Not a
  hypothetical: two halves of such a map went stale inside this release.
- **Principle 3/8 (additive).** Every new column is optional and `sources.parquet` enters
  `artifact.digest` only for modules that carry the table, so no existing module's digest moves.
- **Principle 5 (orthogonal axes).** `declared_use` is a third axis, never folded into `mode`: `mode`
  grades how hard to fail on a *finding*, `declared_use` states who is using the data. Likewise the
  licensing gate does not escalate under `strict`, whose single meaning is a reproducible artifact.
- **Principle 6 (vocabulary idiom).** `VALID_SOURCE_LAYERS`, `VALID_DECLARED_USE` and
  `VALID_PHENOTYPE_CATEGORIES` are `frozenset` + validator, never `Enum`/`Literal`.
- **Principle 7 (round-trip).** The reason the gate is data-driven — see below.

### The rejected alternative: a `--non-commercial` compiler flag

The first proposal was a EULA-style flag on `compile_module` that refuses unless passed. It is
**charter-illegal**, for a mechanical reason rather than a philosophical one: a flag cannot be
recorded in the artifact, and `reverse_module` rebuilds `module_spec.yaml` from parquet alone, so
`compile → reverse → compile` would refuse on the third step. Principle 7's fixed point, broken by a
policy flag — the same lesson that demoted the allele-membership check to the mode ladder one round
earlier.

Keying the refusal on **data carried by the module** keeps everything the flag was for. `sources.csv`
round-trips, so the declaration travels with the module and the cycle reproduces; the compiler still
refuses, and it does so reading only injected facts. No amendment needed.

### Two decisions that look wrong until you know why

**Only the `annotation` layer taints.** A source consulted purely to look up a coordinate contributed
a fact Ensembl reports identically; marking that module viral would be a false positive. This is why
`manifest.sources` keeps per-layer *lists* rather than a single `share_alike` boolean, and why
ClinPGx/CPIC are deliberately never wired as resolution links.

**`None` is not `False`.** A source whose terms could not be established has not been shown to permit
anything. Unknown skips with a warning, and the module-wide verdict is `None` (undetermined), never
`True`.

### Still deferred

Scaffolding the PGx tables from CPIC/PharmVar (they are *authored* `_TABLE_KINDS`, so generation stays
an explicit human-owned step); ClinPGx `variantAnnotations`/`relationships`; CPIC's prescribing
recommendations; and the `activity_phenotype.csv` bins, which CPIC publishes as inequality strings
(`"≥3.0"`) that do not map onto `MeasureBinRow`'s numeric bounds.

## The rest of 0.5 scope

Everything else that was open at the end of the 0.4 round is tracked as `RMn` in
[`ROADMAP.md`](ROADMAP.md) (§ *0.5 scope*): RM4 (native ClinVar gene-panel materialization), RM5
(symbolic/structural alleles), RM6 (callability as a first-class typed column + `callable_from`), RM10
(inheritance-expectation field), RM15 (build-agnostic identity), RM16 (D1 above). RM7/RM13 are
explicitly **consumer** contracts, not format scope. New ideas enter through the freeform idea-book in
the roadmap and graduate here once they are worth a draft shape.

**Near-term note:** the 0.4.1 patch (inject the authority-key list + genuinely adopt `module.version`
— a consumer field report, not a 0.5 item) has its own plan in
[`PROPOSAL_0_4_1.md`](PROPOSAL_0_4_1.md). Its version follow-up (enforce SemVer) is **V1 / RM17**
above.

## G3 — Meta-conclusions: pairing annotations, and the cofactors a module must not hold

**Status: starter shape, deliberately unbuilt.** Recorded now because the shape is already legible
and the risk is drift, not ignorance — but the *grammar* is what drifts, so this proposal commits to
the carrier and keeps the expression at the narrowest thing that is useful.

### The use case

A module is rarely one axis. A cardiovascular module is variants and PGS; a treatment module is drug
susceptibility (and, once it exists, nutrigenomics). What an author actually wants is to pair them:
a CVD module that also says something about aspirin or warfarin *given* what the rest of the module
already found. Those are **meta-conclusions** — conclusions whose subject is a combination of
annotations rather than one row.

The format has no way to state one. Every table keys on a single subject (a variant, a diplotype, a
bin), and `conclusion` is prose about that subject alone. A curator can only write the pairing into
free text, where nothing can act on it.

### Why this is not new machinery

CONSTITUTION Principle 1 already sanctions the escape: *"a **non-Turing-complete boolean predicate**
over genotypes (e.g. `rs429358==C AND rs7412==C`) … available if a task genuinely demands, never a
default."* Drafted since 0.1 and never wired, because nothing demanded it. This is the demand.

### The starter shape

A new **optional table kind**, `meta_conclusions.csv`, carrying a predicate and a conclusion.
Additive by construction: `integrity.file_entries` skips missing files, so a module that omits it is
byte-identical to one from before the table existed.

Three commitments, in decreasing confidence:

1. **The carrier is a separate table.** One CSV = one concern. Columns on `VariantRow` would overload
   a row with a second subject and move every module's digest.
2. **It never blocks.** A predicate referencing an annotation the module does not carry is a
   **warning**, never an error — the same stance as the sidecar-orphan checks. Meta-info is
   commentary on a module, not a constraint on its consistency. This is the property that lets an
   author add one without risking the module.
3. **The predicate starts as conjunction only.** `AND` over terms, no `OR`, no `NOT`, no
   parentheses — exactly Principle 1's own example and nothing more. Widening a grammar later is
   additive; narrowing one that already accepted everything is a breaking change. **The table is the
   safe commitment; the grammar is where drift happens.**

### Phase is where this earns its keep — and it corrects the grammar above

The highest-value case is not a conjunction at all. On **phased** data, whether two variants sit on
the *same* strand or on opposite ones is decisive, and no single-row annotation can say which. The
textbook instance is compound heterozygosity in a recessive condition: two pathogenic alleles **in
trans** leave no functional copy and the finding is affected; the same two alleles **in cis** leave
one intact copy and the finding is a carrier. Same two rows, same two genotypes, opposite
conclusion — and the same-strand co-location of trait-associated alleles is decisive for heritability
modules more generally.

The format already carries the input: phase survives the round-trip by design (a phased `A|G` is
preserved rather than sorted, which is why the genotype grammar treats `|` as order-significant), and
`flags` reserves `phased`. What is missing is any way to *state a conclusion about the relationship*.

**This corrects the "conjunction only" commitment above, and the correction matters.** `rs1 AND rs2`
is true for both the cis and the trans case, so a grammar of pure conjunction cannot express the
example that most justifies building this at all. The starter shape therefore needs exactly one
relational notion — *in-cis* / *in-trans* between two terms — and nothing else. That is still far
short of a boolean language, still bounded, still non-Turing-complete, and it is the smallest grammar
that covers the motivating case rather than the smallest grammar that is easy to write.

It also sharpens the never-blocks rule into a safety property. **Unphased data must not resolve a
phase-dependent conclusion in either direction.** A consumer with unphased genotypes knows the two
alleles are present and not which strand they are on; silently choosing the affected reading would
manufacture a diagnosis and silently choosing the carrier reading would suppress one. It withholds —
the same discipline as `unresolved` for a missing measurement and `requires_callable` for an
uncalled absence, applied to a missing *relationship*. Phase is therefore itself cofactor-shaped:
present or absent at query time, never stored by the module.

### Injectable cofactors — the part that is not obvious

A meta-conclusion often depends on something the module must never hold. Detected ancestry is the
clearest case: population inference is not this repo's job, and a module carrying a sample's
population would break the data-agnostic rule outright. But a *detected* population is exactly the
kind of thing a conclusion turns on.

So predicate terms come in two kinds:

- **module-internal** — a reference to an annotation the module carries (a variant + genotype, a
  diplotype, a bin outcome);
- **injected cofactors** — named values the **consumer supplies at query time**, the same way it
  already supplies the measurement. The module declares which it needs; it never stores one.

Two rules follow, and both mirror machinery that already exists:

- A cofactor must be **declared**, so a consumer knows what to supply — the `source_field` idea
  applied to context rather than to a VCF field.
- A **missing** cofactor must never silently select a branch. It withholds the conclusion, exactly as
  a missing measurement selects `unresolved` and never the lowest bin, and as `requires_callable`
  forbids asserting an absence that was never called.

**This round produced the first real evidence for it.** CPIC scopes its clopidogrel recommendations
to three clinical populations (`CVI ACS PCI`, `CVI non-ACS non-PCI`, `NVI`) and they disagree — the
same Poor Metabolizer diplotype is a `strong` recommendation in one and `moderate` in another.
`DiplotypeRow` has no population column, so `draft --population` makes the *author* pick one at
authoring time and bake it in. That flag is a workaround for a missing cofactor mechanism: the
clinical context is knowable at query time and unknowable at authoring time, which is the definition
of an injected cofactor. A module that could express it would carry all three and let the consumer
resolve which applies.

**The tempting shortcut, and why it does not work.** A module carrying `frequencies.csv` already
holds gnomAD's per-population allele counts, so it looks as though ancestry could be *derived* from
the module's own data rather than injected — read the genotypes, compare against the population
frequencies, infer the group. It does not work, and the reason is not a limitation of this format:
**real ancestry models do not rely on single SNPs.** Population inference is a panel-scale
computation — principal components over thousands of markers, or an explicitly ancestry-informative
panel — and any per-variant likelihood built from a handful of curated loci is noise wearing a
number's clothes. A module curated for cardiovascular risk is selected for association with disease,
not for ancestry information, which makes it precisely the wrong panel. So gnomAD frequencies stay
what they are — the denominator a consumer interprets a genotype against — and ancestry stays an
injected cofactor computed by something that holds the whole genotype, which the module never does.

### Columns are already a conjunction — which is what the DSL is *not* for

The sharpest scoping constraint on this whole proposal is that most of it does not need a predicate
at all. **A row's columns are a de-facto `AND`**: a `VariantRow` carrying `genotype=A/G`,
`requires_callable=true` and (say) a quality floor already means "all of these hold", with no grammar,
no parser and no new concept. The format has been doing this since 0.4 — `HeteroplasmyRow.tissue` is
exactly a cofactor-as-column, the bins are explicitly *tissue-conditional*, and the consumer selects
the row matching the tissue it measured.

So the line is not "cofactor vs not". It is **arity**:

| condition | carrier | mechanism |
|---|---|---|
| about **one** subject (this variant, this diplotype) | an optional **column** on that row | columns conjoin for free; the consumer selects the matching row |
| about a **relation between** subjects (cis/trans, this finding *given* that one) | `meta_conclusions.csv` | needs a grammar, because no column can name another row |

That reclassifies two of the three cofactors above:

- **Call quality on a SNP** is single-subject, so it is a column — an optional quality floor on
  `VariantRow`, in the `requires_callable` idiom, not a predicate term.
- **CPIC's clinical population** is single-subject too: it qualifies *one* diplotype row. A
  `population`/`indication` column inside `_TABLE_DUPE_KEYS` would let all three CPIC contexts coexist
  as distinct rows, and the consumer would select the one matching its setting — which dissolves the
  `--population` refusal this round had to build, and mirrors `tissue` exactly. (A column change moves
  every module's digest, so it is major-only once 0.5 ships; recorded here rather than slipped in.)
- **Ancestry** stays genuinely injected: it is not a property of any one row, and no column can hold
  a value that belongs to the sample rather than to the annotation.

What survives for the predicate is therefore much smaller than it first looked: **relations between
annotations, and essentially nothing else** — with compound heterozygosity's cis/trans as the
motivating case. That is the drift-resistant answer, and it came from noticing that the table already
had a conjunction and nobody had called it one.

### The third cofactor: call quality, and why it is not the `caller` mistake

An author often wants a conclusion to be *conditional on the call being good enough* — assert the
certainty-bearing reading only where the underlying variants are high-grade (`QUAL ≥ 60`, a depth or
genotype-quality floor), and stay quiet otherwise. That is a third cofactor class beside ancestry and
phase, and it has the same shape: the value lives in the consumer's VCF, changes per sample, and must
never be stored by the module.

The format already has the idiom for naming it without holding it. `source_field` points at the VCF
`FORMAT`/`INFO` field a binning table's measure comes from, and `callable_from` (RM6) points at where
a consumer establishes callability — both are *declarative pointers*, deliberately constrained to a
bare field token so they can never become an expression (Principle 1). A quality cofactor is the same
device pointed at `QUAL`/`GQ`/`DP`, and the threshold is the module's own annotation about where its
conclusion stops being reliable.

**This is not the `caller`/`caller_version` mistake, and the line is worth stating because it looks
adjacent.** Those names were dropped from the reserved namespace because they record *which tool
produced a call* — measurement provenance, consumer-side, with no module-side meaning. A quality
*floor* is the opposite: it is the module saying how good a call has to be before this particular
conclusion applies, which is a property of the annotation and of nothing else. The module states the
threshold; the consumer supplies the value; neither holds the other's half.

Grammar consequence: terms need a **numeric comparison against an injected cofactor**
(`@qual >= 60`), which is a third element beside conjunction and the cis/trans relation. Still
bounded, still non-Turing-complete — comparison of a named value to a literal, no arithmetic, no
call. And the safety rule is unchanged and now load-bearing three times over: a **missing** quality
value withholds the conclusion rather than passing or failing the test. A consumer that cannot tell
you `QUAL` has not told you the call is good.

### The feasibility probe, and what it took away

`reference_examples/apoe_epsilon/` was built to test this proposal rather than to illustrate it, and
it **weakened the case for the table**, which is the more useful outcome. APOE is the sharpest
possible test — the ε haplotypes are defined by two SNPs *together*, and P1's escape-hatch example is
literally the ε4 condition — and it turns out to need nothing new. `HaplotypeRow` is a junction
table, one row per (haplotype × defining variant), so a two-SNP haplotype is two rows and
`diplotypes.csv` carries the conclusion. **Same-strand co-location is what a haplotype table already
is**; the predicate would have restated it less legibly.

That removes the cis/trans motivation from the *same-gene* case, which was the strongest example
above. What genuinely survives is narrower: pairing across **subjects** (an APOE diplotype with a
cardiovascular variant and a drug row — no table keys on more than one subject, and no column can
name a row in another table), and compound heterozygosity without enumerating every pair, which is an
argument from economy rather than from expressiveness and should be labelled as such.

### What is deliberately not decided

The column set, the reference syntax for a module-internal term, and the cofactor namespace. Those
follow from a corpus of annotations to combine, and the corpus is roughly 70% built — the SNP core,
the binning family, the PGx tables and now drug context exist; nutrigenomics and supplements do not.
Fixing a shape against four table kinds and then meeting the fifth is how a one-way door gets spent
badly (Principles 3 and 5). The evidence to finish this is the next few modules, not more thought.

### What this blocks

The "shy module" signal — an INFO noting that a module carries nothing a curator added, only
transcribed source rows — was considered this round and **deferred as meaningless without this
table**. Absence of authored contribution cannot be detected from `authorship` alone (a transcription
can still be attributed), and marking drafted rows would put machine provenance into authored data.
Meta-conclusions are the first thing a module carries that a source could not have produced, which
is what makes their absence a meaningful signal rather than a guess.
