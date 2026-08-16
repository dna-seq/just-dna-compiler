# Roadmap — 1.0

**What this file is.** Items that need a **major**, plus the one item that is release-blocking for it.
Split out of [ROADMAP.md](ROADMAP.md) on 2026-08-13, alongside [ROADMAP_0_7.md](ROADMAP_0_7.md), so the
active roadmap describes the line being built.

**What makes an item belong here.** Under the amended charter (2026-08-11) a new optional column or
table is additive and lands in a minor. **Major-only is removal, promotion to required, and
retyping** — the moves that break an existing reader or invalidate published data — plus any change to
what a published identity *means*. "It moves a recompile's `artifact.digest`" is **not** a reason;
Principle 4 already scopes byte-reproducibility to a fixed `compiler_version`.

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
authoring-time, re-keys nothing, and is built in 0.6 — see [PROPOSAL_0_6.md](PROPOSAL_0_6.md).

**Paired with** the `weights.parquet` `end` column in the cleanup tracker: both need the coordinate
convention *for a second coordinate* settled (interbase-half-open vs inclusive). The authored `start`
half closed in 0.5 — it is 1-based VCF POS and now says so, pinned by a test.

Interacts with RM5 (structural alleles differ across assemblies) and the reserved `reference_db` axis.

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
| 0.7 (planned) | **RM55** — the integer copy-number / repeat-count columns deprecated in favour of float ones | the integer column and the integer tiling semantics are removed | **Author:** move the value to the float column; a whole number is still a whole number, so no re-authoring of the *values* is needed. **Consumer:** re-read the float column, and note that bin tiling for these two kinds becomes continuous — a shared endpoint is owned by the higher bin, and a gap is reportable. Written when the 0.7 half lands. |

---

## RM55 (removal half) — the integer copy-number and repeat-count columns

**Severity** high · **Status** 0.6 warns loudly, 0.7 ships the additive float column, **1.0 removes the
integer one** · **Owner** format (schema) + compiler

VCF 4.4 stopped treating copy number as an integer (§7.2, with fractional worked examples throughout)
and standardises the repeat count as a Float (§3). Both kinds were modelled here as integral, so a
fractional measurement matches **no bin at all**, silently, `--strict` included.

**Only the removal is major.** The three-release route was decided on 2026-08-13 precisely so that the
usable fix does not wait for it: 0.6 makes the defect loud, 0.7 adds a parallel float column beside the
integer one (strictly additive, charter-clean) and deprecates the integer one, and 1.0 removes it along
with the integer tiling semantics.

**Why the direct correction could not be taken in a minor**, recorded so it is not re-argued: it is a
**retype** (`CopyNumberRow.modifier_cn: int` → float) *and* a change to what published bin tilings mean —
`[2,2]` beside `[3,3]` is a legal integer tiling today, and under continuous rules both the
shared-endpoint rule and the gap warning change meaning. There were no published copy-number modules to
break, and the shortcut was declined anyway: that is the cost of holding a semi-immutable schema, and
the implementation being wrong is not a licence to break the rule that keeps it trustworthy.

Design detail carried forward from 0.7: whether quantised-versus-continuous is a **per-table
declaration** or a **sixth measure kind** is still open at the point the integer column is removed, and
the answer decides what the removal leaves behind. See [ROADMAP_0_7.md](ROADMAP_0_7.md) § RM55.

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
