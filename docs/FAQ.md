# FAQ — questions that already have answers

**What this is.** A question-shaped index into decisions that are already made. Every entry is a
question somebody actually asked — a consumer in `CONSUMER_SUGGESTIONS`, a dogfooding round, an audit,
or one of our own sessions — together with the one-line answer and a pointer to the entry that holds
the reasoning.

**What this is not: a third index.** [RM_TOC.md](RM_TOC.md) is the complete list of every `RMn` and
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) carries every answered `Sn`. Both
are keyed by **item**. This file is keyed by **question**, which is the only thing a person arriving
cold actually has — and the gap is not hypothetical: writing
[MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md) re-derived S7 from scratch, with the same probe, because
nothing connected *"why did my digest move when nothing changed?"* to an item called
*"`fetched_at` in the digest breaks find-by-hash"*.

**Rules for this file, and they are the reason it can exist beside the other two.**

- **One or two sentences, then a link. Never the reasoning.** The linked entry is the one to edit; a
  second copy of an argument is exactly what made `RM33` unfindable.
- **Only settled questions.** An open item belongs in the roadmap, not here. If the answer is "it
  depends" or "not decided", leave it out.
- **A refusal is an answer**, and usually the most useful kind — most of what follows is a repair
  somebody proposed that was checked and rejected for a reason worth knowing.
- **When a question keeps returning after being answered, say so in the entry.** That is the signal
  that the answer is written down in the wrong place.

---

## Identity, digests and signatures

**Why did `artifact.digest` change when I did not change any data?**
Because the digest is the **byte** identity — *these bytes, from this compiler* — not the content
identity. `content_signature` is the content one. A moved digest beside an unmoved signature is a
provenance-only change and is the intended reading.
→ [SCHEMAS § Identity & integrity](SCHEMAS.md#identity--integrity), and
[S7](CONSUMER_SUGGESTIONS_HISTORY.md#s7--sourcescsv-stamps-fetched_at-into-the-digest-so-a-rebuild-is-never-reproducible),
which was filed after somebody spent an afternoon looking for the content change that had not happened.

**Then should the digest exclude the timestamp column, the way a build system excludes mtimes?**
No — unsound rather than unwanted. `verify_manifest` re-hashes every `artifact.files[]` entry from disk
before recomputing the root, so a digest over anything but the shipped bytes is one no consumer can
check. The mtime analogy misleads because an excluded mtime is not *inside* the artifact; this
timestamp is a column in the parquet. → S7, which also rejects the two other proposed repairs.

**Does a rebuild always mint a new digest?**
No. An untouched spec recompiled under a fixed compiler reproduces it exactly. What moves it across
rebuilds is a **toolchain change** — parquet is not byte-deterministic across polars/arrow versions,
which is why P4 scopes the guarantee to a fixed `compiler_version`.
→ [CONSTITUTION](CONSTITUTION.md) P4, and [MODULE_LIFECYCLE § 6.4](MODULE_LIFECYCLE.md).

**Does re-running the enricher restamp `fetched_at` and churn my digest?**
No. Every sidecar merge is never-clobber, so a recorded row wins and its stamp is never rewritten;
only deleting the sidecar re-stamps. → S7. (The *name* is wrong and the rename is planned for 1.0 —
[ROADMAP § the 1.0 cleanup](ROADMAP.md#fetched_at--the-column-says-fetch-the-value-means-write).)

**Which identity should a dedup or find-by-hash surface key on?**
`content_signature`, and `just-dna-compiler signature <spec>` computes it without compiling. Key a
"these exact bytes" claim on `artifact.digest`. → S7.

**Is `content_signature` build-independent?**
No — reference-independent, not build-independent. Two modules with identical CSVs on different
assemblies describe loci hundreds of bases apart, so a non-default `genome_build` feeds the hash.
Every GRCh38 module's signature is unchanged by this. → RM36.

**Does adding a new optional column break published modules?**
No, and the "digest window" argument that said otherwise expired in 0.4.1. An unset optional column is
omitted from `content_signature`, so the authored identity is untouched; only a recompile's
`artifact.digest` moves, which P4 already scopes. Removal, promotion to required, and retyping are the
major-only moves. → [CONSTITUTION](CONSTITUTION.md) P3, amended 2026-08-11.

**Can I reorder rows in an authored CSV?**
Yes. It moves `artifact.digest` and leaves `content_signature` untouched. The counter-argument was
probed and failed: an author reordering rows in their editor is already legal and already moves the
digest, so forbidding a tool the same move proves too much. → ROADMAP, the row-placement decision.

---

## Sidecars, re-runs and regeneration

**Why did re-running a pass not pick up the newer data?**
Every derived sidecar is merge-not-clobber: an existing row is authoritative because a human may have
overridden it. Delete the file to re-derive. → [ENRICHER.md](ENRICHER.md), and
[MODULE_LIFECYCLE § 6.3](MODULE_LIFECYCLE.md) for what deleting costs.

**Can `resolution.csv` be published as a parquet like the other tables?**
No, and this is the first repair everyone proposes. It is a build-time lookup, not a published fact
table: its provenance columns are outside the fact set by design, `reverse_module` cannot reconstruct
half of them, and a consumer keying on it would be reading the lookup rather than the answer — which
is materialized into `weights.parquet` and the positional tables where it belongs.
→ [SCHEMAS § The resolution table](SCHEMAS.md#the-resolution-table-05-provisional).

**Does `reverse` give me my spec back?**
No. It is a fixed point, not a backup. Manifest-only fields (`authorship`, `provenance`, `logo`,
`readme`), the whole verification attestation *and its closure*, and `resolution.csv`'s provenance are
all lost — deliberately, in each case. → [COMPILER § Reverse](COMPILER.md#reverse) and
[MODULE_LIFECYCLE § 6.9](MODULE_LIFECYCLE.md).

**Reverse drops `rsid_alternates` — is that a bug to file?**
No, closed, do not re-flag. Reverse rebuilds the table from `weights.parquet`, which carries no
provenance at all; those columns are outside the fact set precisely so they never reach the artifact,
so the data does not exist for reverse to emit. Recovering them means re-running the enricher.

**Why does a re-draft report `differs` instead of fixing the row?**
Because rewriting your value would destroy the evidence of the disagreement, and only you know which
side is right. Drafting appends and never mutates; drift on existing rows is a cross-check's job to
report. → ROADMAP § Parked in 0.5, where the one-word line between *append* and *mutate* is drawn.

**Can the enricher just fix the authored cell it found wrong?**
Not in 0.x, and the reason is stronger than tidiness: `content_signature` is *defined* as
pre-resolution and reference-independent, so if a network fetch could edit `variants.csv` that
documented property would simply be false. Also unresolved: what such an edit does to `authorship`.
→ ROADMAP § Parked in 0.5, "Enricher co-authoring".

---

## Validation, checks and trust

**`--strict` passed, so the module is correct?**
No. `strict` means **reproducible**, never *right*. The compiler never fetches, so it has no reference
to check your coordinates against; a whole file shifted by one base passes validate, strict compile,
`fully_resolved: true`, and mints VRS ids that verify. → [COMPILER § What the compiler can and cannot
validate](COMPILER.md#what-the-compiler-can-and-cannot-validate).

**Why does the ClinVar `clin_sig` cross-check warn even under `--strict`?**
Deliberate, and not an inconsistency to fix: failing a compile over a clinical disagreement would make
the format arbitrate a clinical dispute, and a curator who read the primary literature and disagrees
with a submission is doing their job. Same reasoning for the allele-function check and the
article-licence warning. → ROADMAP § Parked in 0.5.

**Should it escalate when the disagreement is with an expert panel rather than a lone submitter?**
Tempting and not taken, for the same reason. The confidence *is* surfaced
(`ClinSigFinding.confidence`) — surface it, let the consumer route on it, do not decide for them.
→ ROADMAP § Parked in 0.5.

**Why can't `validate` stamp the closure when everything passes?**
Because a record stamped by whatever happened to execute says only *someone ran a tool*, which is the
exact defect the closure exists to fix. Closing is a deliberate act; `validate` stays read-only.
→ [SCHEMAS § The closure](SCHEMAS.md#the-closure-rm73--the-authoring-phase-ended).

**`fully_resolved` is `true` — is the module trustworthy?**
Not on its own. The flag is `all()` over `variants.csv`, so it is **vacuously true** for a module with
no `variants.csv`. The safe rule is
`resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)`. A catalog followed the
old rule and had to migrate a stored projection. → RM44 / S13.

**Why is a blank cell not `false`?**
Three-valued is the house algebra: true / false / **unknown**, and `None` is never `False`. Combine
with Kleene semantics rather than withholding on any unknown, because `unknown AND false` really is
`false`. → [CONSTITUTION](CONSTITUTION.md) and the tri-state rules throughout SCHEMAS.

**A check reported zero findings — does that mean it passed?**
Only if it ran. A check that could not run reports *why* (`clin_sig_not_checked`,
`gene_loci_not_checked`, `verification.json`'s `skipped` key), because an empty finding list otherwise
says both "compared everything" and "never compared". → [ENRICHER.md](ENRICHER.md).

---

## Schema shape — repairs that were checked and rejected

**Can `alts` accept IUPAC ambiguity codes, or can `Y` be expanded to `C,T`?**
No to both. No `ref`/`alt`/`alts` column has a nucleotide grammar (eleven columns, six models), so
adding one would reject `N` too and break P3 for modules that compile today. And the expansion reading
has **no instantiation**: probed across 4,439,382 ClinVar rows and all sixteen modules,
`R/Y/S/W/K/M/B/D/H/V` appear in REF or ALT **zero** times. → RM5 and the 0.6 idea-book probe.

**Should the compiler fill a blank `direction` from `state`?**
No. `direction_from_state` is sound as a *consumer's* read-time fallback and a fabricated fact in a
published table — `state='significant'` names no direction at all. A `state`-only module correctly
ships an empty `direction` column. → [COMPILER § Upgrade derivation](COMPILER.md#upgrade-derivation-statebooleans--03-axes).

**Should the compiler materialize a gene panel declared in `module_spec.yaml`?**
Dead, not deferred. The compiler must not create rows no curator wrote, and expansion at compile
leaves `reverse` choosing between the declaration and the rows — neither a fixed point. Drafting
writes those rows as authored bytes instead. → RM4; `panel:` is deprecated in 0.6, removed at 1.0.

**Can there be a `--non-commercial` compile flag?**
No — charter-illegal. A flag cannot be recorded in the artifact, and `reverse_module` rebuilds
`module_spec.yaml` from parquet alone, so `compile → reverse → compile` would refuse on the third step
(P7). The declaration has to be data. → ROADMAP / RM21.

**Should `_check_misspelled_tables` just search any subdirectory?**
No. Tolerating a location without extending the guard puts a typo'd `derived/varaints.csv` exactly
where the check written to catch it cannot see. An authored name under `derived/` is reported as
*misplaced* by exact match; everything else is fuzzy-matched against the full known set. → RM49.

**Two `annotations.parquet` rows with the same key collapse — isn't that a P7 loss?**
No, and this is the standing example of a mechanically-possible finding with no real instantiation.
Sharing a `variant_key` forces a single locus (a one-to-many rsid is expanded to distinct keys), hence
one gene; identical `conclusion`+`negatives` means the same effect, hence the same phenotype. The
constraint set is empty. The genuine poly-effect case is what the keying already fixes.
→ RM80 / S29; and see *Working practice* below.

---

## Naming and renames

**Can we rename a column / a file / a parameter?**
A rename is a **removal plus an addition**, so it is major-only under P3 whatever the thing is. What
*is* legal in a minor is landing the new name as an accepted alias first, so the major only has to
remove — that is RM51 (`sources.csv` → `licensing.csv`), and it is the pattern to copy.
→ [RM51](ROADMAP_HISTORY.md), and the 1.0 cleanup tracker for what is queued.

**Then why not rename `resolve_with_ensembl`, which everyone agrees is misnamed?**
Adding a differently-named alias would be legal and additive; it was declined because the only honest
alias is `--no-resolution`, which buys a better name at the cost of two flags meaning one thing. The
rename itself waits for 1.0. → S14, answered with a refusal.

**Can a field's meaning be corrected in place?**
No — add the corrected field beside it. `Finding.line` was added next to `Finding.row` rather than
redefining `row`, because a consumer already compensating for the old meaning would have started
reporting line 4 for line 3 with no signal. → S18.

---

## Scope boundaries

**Will the format ever carry per-sample results, coverage, or a report card?**
No — a measurement is the consumer's, by the data-agnostic charter. `RM7` (the evaluation-output
schema) is listed in the roadmap only so it is not mistaken for format scope. Callability is expressed
as *pointers* into a VCF the format never sees. → ROADMAP § Not format scope, and
[SCHEMAS § the consumer join contract](SCHEMAS.md#the-consumer-join-contract--three-states-and-the-one-that-gets-collapsed).

**Can a module contain an expression, a script, or a predicate?**
Not code. A module is data (P1). The sanctioned escapes if tables are ever outgrown are a
non-Turing-complete boolean predicate over genotypes and declarative pattern grammars such as regular
expressions — neither is needed yet, and both are escape hatches rather than defaults.
→ [CONSTITUTION](CONSTITUTION.md) P1.

**Can the compiler check my coordinates against the reference?**
No, and it never will: format and compiler never fetch (P2). A check that needs a reference belongs in
the **enricher**. → [COMPILER § the inescapable blind spots](COMPILER.md#the-inescapable-blind-spots).

**Should there be an offline gnomAD frequency snapshot, like ClinVar's?**
No — v4.1's sites VCFs are 58 GB (exomes) and 742 GB (genomes), so there is no slice to ship. Frequency
is the one online-only link, and that is not a reproducibility hole because `frequencies.csv` is the
pin once written. → ROADMAP § Parked in 0.5.

---

## Working practice

**Is `start` 0-based?**
No. **Every `start` in this codebase is the 1-based VCF position.** The docstring that said otherwise
was the bug, and it shifted 3,038 variants across four modules past every offline gate. Pinned by
`schema/tests/test_coordinate_convention.py`. → CLAUDE.md, and the create-module skill's step 3.

**Do I need to file a round-trip or dedup loss I can construct mechanically?**
Only after you have built a **real, sensible** example against the actual code paths. A
mechanically-possible loss with no real instantiation is noise — see the `annotations.parquet` entry
above, where the constraint set turns out to be empty.

**A message cites an `RMn` — is that a bug?**
No, it means known and deliberate. Leave the data honest and note the limitation rather than inventing
a workaround. → [RM_TOC.md](RM_TOC.md) for what any given number is.

**I edited `module_spec.yaml` and the compile says my attestation is stale — is that a bug?**
No, it is the design: `verification.json`'s `module_hash` binds the **authored** bytes, so any authored
edit un-closes the module and drops the block, deliberately and for free. Note the reach — appending
an `authorship:` entry counts, though it moves no identity. What no longer counts is a change of
**line endings**: since 0.6 the binding reads `\r\n` as `\n` (RM82), because an editor or
`core.autocrlf` rewriting them is not an edit anybody made. It stops at newlines — a BOM, trailing
whitespace and a missing final newline are still edits. → [SCHEMAS § the
closure](SCHEMAS.md#the-closure-rm73--the-authoring-phase-ended) and
[MODULE_LIFECYCLE § 6.2](MODULE_LIFECYCLE.md), where both are measured.

**Why does the binding cover only the authored files and not the sidecars?**
Because the derived sidecars carry a `fetched_at` per row, so binding to them would perish the
attestation on a re-enrichment that changed nothing anyone claimed. Read source currency off each
record's own `release`, never off the binding. → SCHEMAS § the verification attestation.

**The consumer-suggestions inbox is empty — were my notes lost?**
No. An answered item moves byte-for-byte to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md) with a row in its index. An empty
live file means nothing is owed. And never read the next free `Sn` off a written-down number; run
`.claude/triage-state.py --next`.
