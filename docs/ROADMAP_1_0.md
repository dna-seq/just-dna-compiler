# Roadmap — 1.0

**What this file is.** Items that need a **major**, plus the one item that is release-blocking for it.
Split out of [ROADMAP.md](ROADMAP.md) on 2026-08-13, alongside [ROADMAP_0_7.md](ROADMAP_0_7.md), so the
active roadmap describes the line being built.

**What makes an item belong here.** Under the amended charter (2026-08-11) a new optional column or
table is additive and lands in a minor. **Major-only is removal, promotion to required, and
retyping** — the moves that break an existing reader or invalidate published data — plus any change to
what a published identity *means*. "It moves a recompile's `artifact.digest`" is **not** a reason;
Principle 4 already scopes byte-reproducibility to a fixed `compiler_version`.

**A third class lives here too, added 2026-08-27: an item that is *gated on* a major without needing
one.** RM69 is the case — its own repair is minor-legal, and every way of reaching it before RM15 lands
was refused. An item is filed against **the release that decides it**, not the release its diff would be
legal in, because filing by legality leaves it in the minor file waiting on a version that file promises
nothing waits on. Such an entry names its gate in the status line and is listed under the gating item, so
building the gate closes it rather than leaving it to be re-found.

**Read the 1.0 cleanup tracker with this file.** It still lives in
[ROADMAP.md § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker) and holds the unnumbered
items (the `state` alias, the `pathogenic`/`benign` booleans, `StudyRow.p_value: str`, the
`weights.parquet` dead columns, the `sources.csv` → `licensing.csv` rename's removal half, and now the
`panel:` block deprecated in 0.6). Indexed in [RM_TOC.md](RM_TOC.md).

**The amended cadence, which several tracker entries predate:** *deprecate in a minor, remove at the
next major.* An item whose replacement already exists takes its warn-only deprecation in a 0.x release
and is **gone at 1.0**, not deprecated at 1.0 and lingering to 2.0. What genuinely keeps its old shape
is whatever Principle 8 makes mandatory, because an author cannot comply with a warning about a field
they must still set.

---

## RM15 — Build-agnostic identity & multi-build support

**Severity** large · **Status** deferred to 1.0 — **and not for digest reasons** · **Owner** format
(schema + compiler) · **Motivating case** GRCh37 / T2T modules; cross-build annotatability

Today a coordinate is *implicitly GRCh38*: `genome_build` is authored/manifest metadata, but every
`chrom/start/ref`, the resolver, and all coordinate reasoning assume GRCh38. Coordinates are **not
absolute** — GRCh37, GRCh38 and T2T-CHM13 disagree — and the rs-number↔coordinate mapping is
**build-specific**: an rs-number may resolve in one build and be unplaceable in another.

This item makes the build a first-class axis: coordinates tagged by (or resolved per) build, a
**build-aware resolver** (a module/reference build mismatch degrades to *unverified* rather than a false
consistency error), and cross-build annotatability recorded **as data**. It also generalizes one-to-many
rs-number expansion to multi-build — *which* loci and *how many* are build-specific; the GRCh38
expansion itself is not deferred.

**Why it is a major.** It changes the *semantics* of `variant_key` and of every coordinate. That is the
identity-change class a major exists for, and it is the one thing `reverse_module` cannot mitigate: a
third party who stored joins against the old keys is not helped by a faithful round-trip.

**What already shipped out of it, so it is not re-scoped.** The build-naming half closed as RM19: a
GA4GH VRS allele id names its build, because the sequence is addressed by its refget accession, so
GRCh38 and GRCh37 mint distinct, correctly non-colliding ids. That resolved the "coordinate-first
identity" parking on its own stated condition.

**What a non-GRCh38 module gets today is pinned, and was not before.** The 2026-08-06 audit found four
paths quietly answering a GRCh38 question in a GRCh37 module's name — all four survived because every
reference example was GRCh38, so "reads the build" and "writes `GRCh38`" were indistinguishable.
`reference_examples/grch37_build/` closes that and `test_reference_examples_roundtrip.py` asserts the
corpus spans more than one build. This does not shrink RM15: **RM15 is about *supporting* another build;
what shipped is only that the tools *decline* to answer for one rather than answering wrongly.**

**Not to be confused with RM48** (an hg19 coordinate reaching a GRCh38 module), which is one-way,
authoring-time, re-keys nothing, and is built in 0.6 — see [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md).

**Paired with** the `weights.parquet` `end` column in the cleanup tracker: both need the coordinate
convention *for a second coordinate* settled (interbase-half-open vs inclusive). The authored `start`
half closed in 0.5 — it is 1-based VCF POS and now says so, pinned by a test.

Interacts with RM5 (structural alleles differ across assemblies) and the reserved `reference_db` axis.

**What lands with it, so whoever builds RM15 knows what it closes** *(the list is the point — until
2026-08-27 both of these named RM15 and RM15 named neither, which is how a gated item stops being
findable from its gate)*:

- **[RM69](#rm69--resolution_signature-is-not-a-round-trip-invariant-when-the-positional-fill-is-skipped)
  closes outright.** The `_resolve_positional_tables` skip on `genome_build != DEFAULT_GENOME_BUILD`
  *is* the RM15 gate; un-gating the fill makes the injected rows reach the positional parquets, which is
  the missing field Principle 7's own remedy clause points at. Nothing else reaches it.
- **[RM68](ROADMAP_0_7.md#rm68--a-drafting-provider-on-a-non-grch38-module-refuse-or-strip-to-the-rsid)
  loses its premise but keeps its own exit.** Once a provider can write the coordinate under the build
  it came from there is nothing left to refuse or strip. It stays filed in 0.7 because its other exit —
  an author with a non-GRCh38 module saying which outcome they wanted — is reachable first and would
  settle it without RM15; check its status before assuming this closes it too.

---

## RM69 — `resolution_signature` is not a round-trip invariant when the positional fill is skipped

**Severity** low · **Status** **gated on [RM15](#rm15--build-agnostic-identity--multi-build-support),
moved here from [ROADMAP_0_7.md](ROADMAP_0_7.md) on 2026-08-27** — the repair itself needs no major, but
every route to it before RM15 lands is refused below, so 1.0 is the release that decides it. Until then
it is a documented limit of Principle 7 on non-GRCh38 modules, not a breach · **Owner** compiler ·
**Found by** dogfooding on 2026-08-13, the D6 corpus sweep

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

### Why it was not simply closed instead, 2026-08-27

Closing was the live alternative when the misfiling was found, and the case for it is real: severity
low, no incident behind it, and a mechanism reproduced once in sixteen modules is normally grounds to
close rather than to carry. **It stays open because the fix arrives on its own** — RM15 un-gates the
fill and the signature becomes an invariant with no work filed against this entry, so filing it as a
"documented divergence" the way [RM67](ROADMAP_0_7.md#rm67--polyploid-and-partially-phased-genotypes)
is filed would say the wrong thing — RM67 is **not work**, a limit nobody intends to lift, and this one
is scheduled. (Neither is *closed*: RM_TOC's ✖ section holds two items and neither of these is one.)
The other half of the argument is the candidate-repair list above, which is the record of five refusals.
Closing the entry retires that record just as the release most likely to re-propose all five arrives.

---

## RM52 — 1.0 ships an upgrade procedure, or 1.0 does not ship

**Severity** high — **release-blocking by charter** · **Status** open, 1.0, mandatory · **Owner** format
+ compiler + enricher · **Origin** the 0.6 charter amendment (CONSTITUTION § Amendments), which permits
breakage at a major only when it arrives mitigated

**The obligation.** A major carries the documented route from the previous line: per item, either the
mechanical migration or an explicit *no action needed*. A removal whose upgrade path is left to the
reader to work out is not ready to ship, however long it was deprecated first. This is a principle, so
1.0 is blocked on it the way it is blocked on the round-trip tests.

**It is not the CHANGELOG, and the difference is the audience.** Two audiences break in different places
and cannot use each other's instructions:

- **A module author holding a 0.x spec** — what moved on the authored surface (the `sources.csv` →
  `licensing.csv` rename, the `panel:` block, the `StudyRow.pmid` requiredness demotion, the `alt`/`ref`
  vocabulary members dropped from the read set, whatever `state` and the `pathogenic`/`benign` booleans
  become). Their remedy is an edit, a rename, or a tool run.
- **A consumer holding a 0.x artifact** — a parquet filename, a manifest key, a `variant_key` semantics
  change (RM15). No edit of theirs helps: they need to know what to re-read, what to re-key, and what
  silently still works.

**What "mechanical migration" can mean, because the primitive exists.** `reverse_module` rebuilds the
authored spec from a compiled artifact, so for anything expressible in the DSL the upgrade is *reverse
under the old compiler, recompile under the new one* — and the procedure's real job is to say **which
items that covers and which it does not**. It does not cover an identity re-key. Naming that boundary is
most of the value.

**Three rules for how it gets written**, all of which exist because the alternative has already failed
here. The line is written **when the item lands**, not when the release is assembled. A **"no action
needed" must be stated explicitly**, because silence is indistinguishable from an oversight — the same
reason `clin_sig_not_checked` and `gene_loci_not_checked` exist. And the claims are **checkable, so
check them**: "reverse and recompile" can be run across `reference_examples/` and asserted to reproduce.
An unrun migration is prose, and prose that has never been executed is how a documented `start`
convention shifted 3,038 variants.

**Decided 2026-08-13: the 0.6 batch does not owe per-item ledger rows.** Imposing the discipline on
every work item now is premature decision-making — the obligation belongs here, where it can be settled
against the shape that actually exists by then. 0.6's deprecations (`panel:`, and `sources.csv`
alongside `licensing.csv`) are recorded in the 1.0 cleanup tracker in the ordinary way.

### The ledger

One line per breaking item, written **when the item lands**. Deprecations count: the removal is the
breaking half, and the line is owed by whoever created the obligation.

| landed | item | what breaks at 1.0 | upgrade route |
|---|---|---|---|
| 0.6.0 | **RM51** — `sources.csv` deprecated in favour of `licensing.csv` | the old input filename stops being read | **Author:** `git mv sources.csv licensing.csv`. No content change, and no signature moves — verified across all eleven reference examples when four of them were renamed. **Consumer: no action needed** — `sources.parquet` and `manifest.sources` keep their names through the whole 0.x line and are untouched by this item. |
| 0.6.0 | **RM4** — the `module_spec.yaml` `panel:` block deprecated | the block stops being read | **Author:** delete it. Nothing replaces it — the enricher now records the drafted-from release into the licence row's `dataset` column itself, which is what the tautology check reads. Deleting it moves neither `artifact.digest` nor `content_signature`, measured on `reference_examples/apoe_epsilon` with the block appended. **Consumer: no action needed** — `manifest.panel` is passthrough metadata nothing derives from. |
| 1.0 (planned) | **RM73** (gate half) — a closed authoring attestation becomes a **precondition of compiling** | a module with no closure stops compiling; since 0.6.0 it only warns. **Blocked, not merely planned — see § RM73 below: the gate refuses on step 3 of the round trip** | **Author:** run `just-dna-compiler close spec/` once the module is finished, and re-run it after any edit. It is a deliberate act by design — `validate` stays read-only, so nothing stamps behind your back. **Consumer:** no action; the artifact already carries `manifest.verification.closure` where a module was closed, and reading it is optional. The whole mechanism (`Closure`, `close`, the warning) **shipped additively in 0.6.0**; what waits for the major is only the promotion of the warning to a refusal, which is P8. |
| 1.0 (planned) | **`fetched_at` → `updated_at`/`recorded_at`** on the seven sidecar models — bundled with the `sources.parquet` rename, which moves the same digests. Unnumbered; see the 1.0 cleanup tracker | the column name changes in six parquets and seven CSVs. **No signature moves** — it is outside all seven fact sets — so `content_signature` and every `*_signature` are untouched; only `artifact.digest` moves, on modules carrying a sidecar | **Author: no action needed.** The loader keeps accepting `fetched_at` as a deprecated input spelling through 1.x, so an existing sidecar loads unchanged; the writer emits the new name from the next pass that touches it. No 0.x deprecation warning is owed, because nobody authors this column and `extra="forbid"` means an author could not act on one. **Consumer:** re-read the column by its new name in `frequencies`/`gene_metrics`/`literature`/`gene_validity`/`clinical_assertions`/`sources.parquet`; nothing derives from it, and it is in no signature |
| 0.6.0 | **RM55** — `CopyNumberRow.modifier_cn` deprecated in favour of `modifier_copy_number` | the integer column is **removed** (not retyped — the float one has existed since 0.6), and with it the kind-keyed tiling defaults | **Author:** move the dosage to `modifier_copy_number`; a whole number is still a whole number, so no re-authoring of the *value* is needed, and setting both was always an error so there is nothing to reconcile. If your `copy_number`/`repeat_count` bins are a genuine grid, state `measure_tiling: quantised` before 1.0 removes the default that assumed it. **Consumer:** read `modifier_copy_number` (or `effective_modifier_copy_number`, which is what everything in-tier already reads) and take a group's tiling from `measure_tiling` rather than from `measure_kind`. |

---

## RM55 (removal half) — the integer copy-number and repeat-count columns

**Severity** high · **Status** the whole usable fix **shipped in 0.6**, so what is left here is a
removal and nothing else: `CopyNumberRow.modifier_cn`, deprecated warn-only since 0.6, and the
kind-keyed tiling defaults · **Owner** format (schema) + compiler

VCF 4.4 stopped treating copy number as an integer (§7.2, with fractional worked examples throughout)
and standardises the repeat count as a Float (§3). Both kinds were modelled here as integral, so a
fractional measurement matches **no bin at all**, silently, `--strict` included.

**Only the removal is major.** The route was decided on 2026-08-13 as three releases precisely so that
the usable fix would not wait for the major, and then collapsed to two when the fix landed in 0.6.

**Re-dated on 2026-08-16 and built the same week; the route is now two releases rather than three.**
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM55 took the usable fix back into **0.6**, so what this
entry calls "0.7" is 0.6, and what is left here is a **removal and nothing else**. Two corrections to
the description above:

- **The parallel-column shape does not apply to the bounds** — `measure_min`/`measure_max` have been
  `float | None` since 0.4. What ships instead is an optional `measure_tiling` column
  (`{quantised, continuous}`) that the gap and shared-endpoint rules read in place of `_INTEGER_KINDS`,
  as an **effective** value: declared, else forced by a fractional value in the group, else the kind's
  default. So 1.0 removes the kind-keyed tiling *defaults*, not a capability — by then the tiling is
  either stated or forced by the data, and the default is the only part left that guesses.
- **It does apply to `CopyNumberRow.modifier_cn`, which is the one genuine `int`** — 0.6 adds
  `modifier_copy_number: float | None` beside it, read through an effective-value alias that falls back
  to `float(modifier_cn)`, with both-set an error and `_KEY_FIELDS` keying on the effective value so the
  key never holds two spellings. `modifier_cn` is **deprecated in 0.6** (actionable, so the amended
  cadence permits it) and **removed here**. That is why 1.0 inherits a removal rather than the retype
  this entry was written expecting.

**Why the direct correction could not be taken in a minor**, recorded so it is not re-argued: it is a
**retype** (`CopyNumberRow.modifier_cn: int` → float) *and* a change to what published bin tilings mean —
`[2,2]` beside `[3,3]` is a legal integer tiling today, and under continuous rules both the
shared-endpoint rule and the gap warning change meaning. There were no published copy-number modules to
break, and the shortcut was declined anyway: that is the cost of holding a semi-immutable schema, and
the implementation being wrong is not a licence to break the rule that keeps it trustworthy.

Design detail, **settled on 2026-08-16 rather than carried forward**: quantised-versus-continuous is a
**declaration**, not a sixth measure kind — `measure_kind` answers *what is measured* and tiling answers
*how the axis is divided*, and folding the second into the first is the `state` anti-pattern the
Constitution names by name (P5), besides being a product rather than a sum as kinds are added. It lands
as `measure_tiling` in 0.6, shipped. So the removal here leaves behind a schema where the tiling is
stated, not one where it has to be inferred from the kind. See
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM55, and [SCHEMAS.md](SCHEMAS.md) for the built shape —
including the one place the build departed from the proposal, which is that the fractional inference
fires only against a `quantised` default (`activity_score` is fractional by nature and asserts nothing
about the grid, so reading it as continuous invents coverage gaps rather than revealing them).

---

## RM81 — one artifact spells a genotype two ways

**Severity** medium · **Status** open — 1.0 (a retype of a published parquet column) · **Owner** format
(schema) + compiler · **Motivating case** S30 in [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md)

`weights.parquet` stores `genotype` as `List(Utf8)` — the compiler splits the authored cell on
`/`/`|` — while the 0.4-family tables (`pharm_variants.parquet` and the rest) are materialized verbatim
from their authored CSV and keep the string `"C/C"`. Both are documented and neither is wrong on its
own, but a consumer joining either family to the same VCF meets two representations of one concept, and
the split is invisible until the join raises:

```
SchemaError: datatypes of join keys don't match - `genotype`: list[str] on left
does not match `genotype`: str on right
```

The report that produced this is the same one that produced `alleles.split_genotype` (S30, shipped in
0.6): the reader half — *how do I split it* — is closed, because there is now one public leaf every
tier and every consumer calls. What is left is the artifact half, and it is major-only.

**Why not a minor.** Changing `pharm_variants.parquet.genotype` from `Utf8` to `List(Utf8)` is a
**retype of a published column**, which P3/P8 put in a major exactly because it breaks an existing
reader — and here the reader is not hypothetical: the reporting consumer reads that column as a string
today and normalizes it themselves. RM43's fill was additive (stamped columns that were not there
before); this is not the same move.

**Why not the additive workaround.** Adding a parallel `genotype_alleles: List(Utf8)` beside the string
is minor-legal and is the wrong shape: it puts two spellings of one value in one table, which is the
desync failure `ResolutionRow.vrs_id` needed two guards for, and it leaves the original defect — *this
artifact spells a genotype two ways* — in place with a third spelling added to it. A consumer meeting
both columns has to know which is authoritative, and nothing in the parquet says.

**What to decide at 1.0**, since the direction is not obvious: unify **up** (split everywhere, so every
table matches `weights.parquet`) or **down** (store the cell verbatim everywhere and let each reader
call `split_genotype`). Up is what the reporting consumer implemented and what a join wants; down is
what `reverse_module` wants, since the 0.4 families re-emit their cell byte-for-byte and a split column
has to be rejoined — and a rejoin must reproduce the authored separator, which means the `phased` bit
travels too, as it already does for `weights.parquet`. Whichever is taken, it is one rule for the whole
artifact, and `split_genotype`'s "never sorted" contract holds under both.

---

## RM73 (gate half) — the closure gate refuses on step 3 of the round trip

**Severity** high, and **release-blocking for the gate itself** · **Status** open; a precondition of the
ledger row above, not a detail of it · **Owner** compiler · **Found by** probing whether compile should
*warn* on an absent closure, 2026-08-16 — the answer for 0.x turned out to be the reason the 1.0 half is
blocked

The mechanism [shipped in 0.6.0](ROADMAP_HISTORY.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end)
— `Closure`, `just-dna-compiler close`, and a warning when a compile publishes none — and it is
warn-only and charter-clean. Promoting that warning to a refusal is what this row is, and it does not
work as written:

- `reverse_module` rebuilds authored files from parquet alone. It **cannot re-emit `verification.json`**
  and already says so, warning that the source artifact carried an attestation the reversed spec will
  not. So a reversed spec is unclosed **by construction**, not by omission.
- Under the gate, `compile_module` → `reverse_module` → `compile_module` therefore **refuses on step 3**
  — for every module, including all sixteen reference examples. Principle 7's lossless round-trip is
  enforced by tests rather than asserted, and those tests do not start failing subtly; the sequence
  stops being runnable at all.

**Why this is invisible today, which is the part worth recording.** Probed while deciding the 0.x
behaviour: `artifact_digest` is a Merkle root over `_OUTPUT_FILES`, which is parquet only. `manifest.json`
is not in it, warnings feed no signature, and no round-trip test compares them. So the same asymmetry
already exists — a closed module and its round trip differ in `manifest.compilation.warnings` — and in
0.x it **costs exactly nothing enforceable**, even though RM44 established that a catalog parses that
field. `verification.json` has carried the identical asymmetry since RM45 with no consequence, for
precisely this reason. The precedent is therefore silent about the danger, and the gate is what converts
a free divergence into a refusal.

The obvious repair is closed too: `manifest.verification` carries the `checks` but **not** `difficulty`
or `nonce`, so reverse cannot rebuild a valid attestation document out of the artifact it holds.

**Candidate answers, none decided.** Stated with their costs so the gate is not built on whichever occurs
to someone first:

- **Widen `Verification` to carry the whole document**, so reverse can re-emit it. Additive and
  minor-legal, so it could land well before 1.0 — but it makes `reverse` write a closure it did not
  witness, which is the self-asserted provenance RM73 rejected when it rejected the `origin:` column. And
  reverse holds no key, so whatever it writes is unsigned by construction.
- **Exempt a reversed spec from the gate.** Requires the reversed spec to state that it came from
  reverse: the same self-assertion one level down, in a marker any author can type.
- **Require a human to re-close a reversed spec.** Honest, and possibly correct — reverse produces a
  spec, not a finished module — but it changes what the round-trip guarantee *means*. The fixed point
  would still hold over every authored value, while `compile → reverse → compile` stops being a sequence
  that runs without a human in it. If this is the answer then Principle 7's wording is what needs
  amending, deliberately and on purpose, and the reference-example corpus needs a documented closing step.

**What would unblock it:** picking one of the three *before* the gate is built. The severity change is one
line; this question is the whole of the item.
