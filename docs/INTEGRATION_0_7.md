# Integrating 0.7 — what changed against the 0.6 surfaces

For the repos that consume this one: **just-dna-pipelines**, **just-dna-lite**,
**just-dna-marketplace**, **just-dna-agents**, **just-dna-registry**. It answers one question —
*given a working 0.6 integration, what do I have to check, and what do I have to change?*

The baseline throughout is the **published `v0.6.6` tag**. It is the last cut, and every measurement
below was taken against it rather than against a remembered surface: where this document says
*measured*, a command was run on this branch and its number copied out.

**Status: 0.7.0 is bumped and NOT cut.** All three `pyproject.toml` files read `0.7.0` (bumped
2026-08-31) and `git tag` stops at `v0.6.6`, so the number is decided while work still lands inside
it. The standing rule from the 0.6 document applies unchanged and is worth restating, because it has
caught someone every release: **answered, in the tree, cut and installable are four different
states**. Nothing here is installable yet.

**This release is two batches, and a consumer on 0.6.6 has seen neither.** The
[2026-08-24 pass](CHANGELOG.md) answered twelve consumer items (S63–S74) and was deliberately left
uncut with no number; [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md) then decided twelve roadmap items with
the maintainer, one at a time, and all twelve shipped. RM140 landed after the round closed, as a dated
addendum, and RM139 / RM141 / RM142 landed on top of it from three more consumer reports. They are one
release because the version bump happened once; read this document as covering the whole interval.

**One item is in the working tree and not committed** — RM143 (S78), a new `strict` refusal. It is
called out in § 1 and § 2.6 with that label on it. Do not plan against its wording.

---

## 1. The headline: your reads still work, your digests do not

Measured, not asserted. `RELEASE_RECORDS["0.7.0"]` in `just_dna_format.release_records` is the
release's own record of what it moved, produced by `just-dna-compiler sweep` over the reference corpus
with 0.6.6 installed in an isolated environment and **re-measured on 2026-08-31** when RM140 landed:

| axis | result |
| --- | --- |
| Reference modules that compile under 0.7.0 | **16 / 16** |
| Modules measurable across the boundary | **15** — `cyp2c9_warfarin_grch37` is *unmeasured*, see below |
| `content_signature` moved | **0 / 15** |
| `artifact.digest` (parquet bytes) moved | **14 / 15** |
| Parquet schema moved | **14 / 15** |
| Manifest fields moved | **15 / 15** |
| `warnings` moved | **3 / 15** |
| Fields removed, retyped, or promoted to required | **none** |
| `schema_version` | unchanged, `"1.0"` |

That is the Principle 3 shape for a minor, again: new optional columns and new manifest blocks move
the *byte* identity of an artifact and leave the *content* identity alone.

**Four more items landed on 2026-08-31 after that sweep was taken**, and one of them changes a *value*
rather than adding a field, so it is called out here rather than left to § 2: **RM110** normalizes
`gene_metrics.constraint_flags`, which moves `gene_metrics.signature` and `artifact.digest` on any
module compiled from the gnomAD v4.1 constraint snapshot — a correction, not drift, and the reference
corpus carries exactly one such row. The other three are additive: **RM103**
(`identity.version_coerced_from`), **RM108** (`gene_validity.superseded_count`, plus a narrowed
`gene_validity.classifications` that is also a correction) and **RM150** (`contested` on
`VALID_DIRECTIONS`). `content_signature` is untouched by all four. The parquet movement is
dominated by one cheap thing — RM140's `statistical_test` column lands in every `studies.parquet`, and
ten of the sixteen examples carry one.

**`cyp2c9_warfarin_grch37` is unmeasured rather than unchanged, and the reason is the one asymmetry in
this release.** RM70 added `requires_callable` to that example's `pharm_variants.csv`, and 0.6.6
refuses the spec under `extra="forbid"`. So there is no like-for-like before state for it. Generalised:
**a spec authored with 0.7 columns does not compile on a 0.6.6 compiler** — which is the ordinary cost
of an additive column and is why the compiler is upgraded before the spec is edited, not after.

### The one thing you must re-pin

**Any stored `artifact.digest` from a 0.6.x compile will not reproduce under 0.7.** Re-compile and
re-pin at the version boundary if you cache digests, gate on them, or diff a recompile against a
stored value. If you key on `content_signature`, **no action** — it did not move on any measured
module, which is the whole point of having two identities.

### One old-reader break, and it is not where you would look

The 0.6 document could say a `v0.5.4` client parsed every 0.6 manifest. **That does not hold across
this boundary, for one field.** Measured here, by parsing all sixteen freshly compiled 0.7 manifests
with `v0.6.6`'s own `ModuleManifest`:

| | result |
| --- | --- |
| 0.6.6 client parses a 0.7 manifest | **15 / 16** |
| refused | **1** — `mt_common_deletion`, on `verification.checks.0.producer` |

`ModuleManifest` and `Compilation` do not forbid extra keys, so every new *top-level* block and every
new `compilation` field is invisible to an old reader. But `VerificationRecord` carries
`extra="forbid"`, and RM129 (S71) added `producer` to it. `write_manifest` serialises with
`exclude_none=False`, so the key is present as `null` even on a record that never set it — and a null
extra key trips `extra_forbidden` exactly as a populated one does. **The trigger is a module with at
least one check record**, not a module with a verification block: fifteen of the corpus carry a block
holding no checks and parse fine.

The same applies to `verification.json` on disk, which is the same model.

So: **a consumer that reads `verification` must upgrade `just-dna-format` to 0.7 before it meets a
0.7-enriched module.** A consumer that ignores the block is unaffected. This is the same standing cost
that `warnings_summary`'s closed vocabulary carries and that COMPILER.md already states for warning
codes — *additive* describes the writer, never the reader — but it had not been said about
`VerificationRecord`, and it is the sharper case because it needs no new vocabulary member to fire.

### Three checks can newly refuse

None of them is a schema change, and each is a fix:

- **RM141 — `validate --strict` now refuses what `compile --strict` refuses, on a partial resolution
  table.** A module whose variants have no position after resolution was refused by the compile and
  blessed by the pre-flight, so a green `validate` immediately preceded a red `compile`. The predicate
  (`resolution.unresolved_subjects`) is now called from both sides and the pre-flight appends the
  compile's error verbatim. **If your pipeline treats a green `validate` as a compile guarantee, that
  is now true where it was not** — and if it treats a post-`validate` compile failure as an
  infrastructure error, it will stop misclassifying these. Two distinctions are kept: nobody-asked is
  not asked-and-absent, and `--no-resolve` silences the check the way it silences the fill.
- **RM91's `effect_allele` check and RM48's wrong-build arithmetic are unchanged from 0.6** and are
  listed here only so nobody re-derives them from a corpus run that does not fire them.
- **RM143 (S78) — in the working tree, uncommitted.** `compile --strict` refuses a module whose
  `verification.json` records a `genome_build_agreement` finding: the enricher has already diagnosed
  the rows as another assembly's, and the compiler was discarding that answer. It gates on a *record*,
  adds no reference and no network, is silent when no attestation exists, and `best_effort` still
  builds and warns. No reference example carries such a finding. **The wording may move before the
  cut** — S78 is still open in the inbox.

---

## 2. The surface delta, by layer

### 2.1 `manifest.json`

Three new fields on `compilation`, two new top-level entries, one new field per verification
record, and — from the 2026-08-31 batch — one new field on `identity`, one on `gene_validity`, and one
corrected `gene_validity` facet:

| field | type | what it is |
| --- | --- | --- |
| `compilation.warnings_summary` | `dict[str, int]` | `warnings` counted by kind, keyed on `VALID_WARNING_CODES`. **Either empty — this compile did not classify — or its values sum to `len(warnings)`.** Never complete-looking and short. |
| `compilation.carried` | `list[str]` | the subset of `warnings` **no edit to the spec directory can clear**: a limit of this tier or a fact of a source. Subtract it from `warnings` to get what the author still owes. Empty is a real answer. |
| `compilation.dropped_rows` | `dict[str, int]` | authored rows this compile discarded, per table — today only RM5's unusable-symbolic-allele drop. Empty means nothing was dropped. It exists because a drop inside a *kind* table moved no published counter at all (S65), so from outside it was indistinguishable from a changed spec. It is also why a round trip can be short. |
| `clin_sig_concordance` | block or absent | summary of the concordance record (RM130): `row_count`, `call_count`, **`opposed_count`**, **`unchecked_count`**, the authorities and datasets consulted, the two signatures, and the value sets present. |
| `authority_precedence` | `list[str]` | the authorities this module's curator weighted, most-trusted first (RM134 § B). **Nothing computes with it** — no tier, no check, no verdict. Empty means the module has not said, which is not the same as saying they weigh equally. Out of both identity halves. |
| `verification.checks[].producer` | `str \| null` | tool and version that put **this** check. Read it, not the block-level `producer`, when asking whether a record predates a fix — `merge_records` carries an older run's record across and restamps the block-level one (S71). See § 1 for what it does to an old reader. |
| `identity.version_coerced_from` | `str \| null` | RM103. The `module.version` the author actually wrote, when the model rewrote it — `"v2"` beside `"2.0.0"`, `"abc"` beside `"0.0.0"`. **Absent means the authored value was already canonical SemVer**, never that nothing was authored. Advisory like `version` itself. |
| `gene_validity.superseded_count` | `int` | RM108. How many rows a later curation of the same claim replaced. **Derived, not stored** — no column exists — so nothing hashes on it and `gene_validity.signature` did not move. `0` is a real answer. |
| `gene_validity.classifications` | `list[str]` | **CHANGED, and it is a correction.** It now spans the **current** rows rather than every row, so a module carrying a re-curated claim publishes one verdict where it published a pair as far apart as `["definitive", "refuted"]`. A group nothing can order (a tie on `classification_date`, or a member stating none) still contributes all of its classifications. |

Two counters in the concordance block earn their place and are the ones to render: `opposed_count`
(the disagreement crosses the pathogenic/benign line) and `unchecked_count` (an authority could not be
consulted). A shrinking record with a rising `unchecked_count` is a missing snapshot, not an improving
module. **There is no consensus field and the omission is deliberate** — resolving a split needs a
weighting model this format does not have.

The block-level `Verification.producer` description was corrected rather than the field changed: it
means *who last wrote this file*, and it always did.

**`gene_validity.classifications` is the one manifest field in 0.7 whose existing values change
meaning**, so it is worth stating plainly: if you render that list, a module whose curating body
re-curated its own claim will stop showing the superseded verdict. That is the fix arriving, not a
regression — the old list named a classification nothing anywhere said was stale. The rows are all
still in `gene_validity.parquet`; only the summary narrowed.

**`identity.version_coerced_from` also changes what `reverse` writes.** `reverse_module` now recovers
the authored `module.version` from the artifact's own `manifest.json` when no caller supplies one, and
re-emits the **pre-coercion** string. Two consequences: a reversed spec carries a `version:` key where
it used to carry none, and the field is a fixed point across `compile → reverse → compile` rather than
going absent on lap 2. Nothing hashes on `module.version`.

### 2.2 Parquets

**Three new files, so `ARTIFACT_PARQUETS` goes 19 → 22.** Derive from the constant; do not hand-keep a
list. The 0.6 guide says the same thing and it is the defect that broke the publisher.

| parquet | when it appears |
| --- | --- |
| `clin_sig_concordance.parquet` | the module carries the concordance record (RM130) |
| `clin_sig_authority_calls.parquet` | ditto — the paired per-authority detail |
| `overrides.parquet` | the module carries an authored overlay (RM124) |

`artifact.files` is name-sorted before hashing, so tuple position is invisible to the digest and these
land alphabetically rather than at the end.

**Four new columns**, all optional, all absent-means-nothing-was-said:

| parquet | column | item |
| --- | --- | --- |
| `studies.parquet` | `statistical_test` — which analysis produced this row's `p_value`/`effect_size`. Free text; `study_design` describes the *study*, this describes the *analysis*, and one study routinely runs several | RM140 |
| `haplotypes.parquet` | `requires_callable` — tri-state | RM70 |
| `pharm_variants.parquet` | `requires_callable` — tri-state | RM70 |
| `pharm_variants.parquet` | `pmid` — the third citation site, beside `StudyRow.pmid` and `MeasureBinRow.pmid` | RM132 |

`requires_callable` is **not** on `DiplotypeRow`, deliberately: a diplotype names a star-allele pair,
not a locus. `callable_from` did not travel with it anywhere — "a proof is required" and "here is where
the proof lives" are different axes.

> **One discrepancy worth knowing.** `RELEASE_RECORDS["0.7.0"]`'s declared list names
> `requires_callable` for `pharm_variants.parquet` and does not name `pmid`. Both columns are in the
> compiled parquet — verified by compiling `reference_examples/pgx_slco1b1_simvastatin` and reading
> the schema. The gate is per-axis, so this failed nothing; the *record* is a sentence short. Read
> this table rather than that `detail` for the column list.

`_KEY_FIELDS` for `studies.csv` is **not** widened by RM140 — the published `key.columns` is still
`(variant_key, pmid)`, and re-keying a shipped authored table is major-only.

### 2.3 Files in a spec directory

| file | kind | detail |
| --- | --- | --- |
| `overrides.csv` | **authored** | the overlay (RM124). Columns `table`, `subject`, `member`, `field`, `operation`, `value`, `reason`, `decided_by`, `decided_at`, with **`reason` required** — that is what makes it a record rather than a knob. Operations are `update` / `insert` / `suppress`. |
| `clin_sig_concordance.csv` | derived | contested subjects, keyed `(variant_key, genotype)` |
| `clin_sig_authority_calls.csv` | derived | what each authority said, keyed `(variant_key, genotype, authority)` |
| `.<name>.staging/` | transient | `enrich`'s staged raw answers (RM128). Removed on a successful commit unless `--keep-staging`; **a killed run leaves them either way, and the next run resumes from them.** |

**The overlay makes seven derived tables pure build products** — `resolution.csv`, `frequencies.csv`,
`gene_metrics.csv`, `gene_validity.csv`, `clinical_assertions.csv`, `literature.csv`,
`gwas_effects.csv`, plus `clin_sig_concordance.csv` as the eighth. `derived = f(source, overlay)`, so
deleting one and re-running is now free, which is what dissolved RM83. `licensing.csv` / `sources.csv`
is deliberately **outside** the covered set: it has its own merge path and is the one derived table a
human is told to write.

**Read the derived parquets, not the derived CSVs, if you want what the module asserts.** The overlay
is applied at compile, so `frequencies.parquet` and its siblings are post-overlay while the CSVs beside
the spec stay exactly as the enricher wrote them. That asymmetry is the design.

`reverse_module` emits the post-overlay tables **plus** the overlay, so the overlay applies twice; all
three operations are idempotent, which is why there is no `previous_value` column and why the fixed
point is a test rather than an assumption. One consequence stated rather than hidden: **no operation
reports its own no-op**, so a `suppress` with a typo'd subject does nothing and cannot warn.

### 2.4 Python API

| symbol | tier | why you care |
| --- | --- | --- |
| `release_records.needs_recompile(compiled_under, current)` | format | *does an artifact compiled under X need recompiling at Y?* Answers per axis in three values — `True` / `False` / `None` for **unknown** — over the interval, not the release. This is the derivation a registry's `revalidate` / `needs_upgrade` wants. |
| `release_records.RELEASE_RECORDS` | format | the published records themselves (`0.6.1`, `0.6.6`, `0.7.0`), each with its `axes`, `manifest_fields`, `declared` changes, `unmeasured` modules and an `evidence` sentence carrying its denominator. |
| `release_records.ReleaseRecord` / `DeclaredChange` / `RECOMPILE_DRIVING_AXES` | format | the models, and the axis set that actually drives a recompile — `warnings` is deliberately outside it. |
| `findings.classify(warnings)` | format | `(carried, summary)` from a warning list. **Withholds — an empty pair — rather than part-classifying**, so a caller holding plain prose gets nothing instead of a misleading digest. |
| `findings.CodedWarning` / `findings.restate` | format | a `str` subclass carrying its code. A `Finding` loses its code at a pydantic field and at any reformat; `restate` is how you reformat without dropping it. |
| `overrides.apply_overrides` / `OVERRIDABLE_TABLES` / `VALID_OVERRIDE_TABLES` / `VALID_OVERRIDE_OPERATIONS` / `OverrideRow` | format | the overlay. `OVERRIDABLE_TABLES` maps a table name to its subject/member fields — read it rather than restating the grammar. |
| `concordance.ClinSigConcordanceRow` / `ClinSigAuthorityCallRow` | format | the two record models, plus `CLIN_SIG_*_FACT_FIELDS`. |
| `integrity.clin_sig_concordance_signature` / `clin_sig_authority_call_signature` | format | two fact-hashes because they are two tables: a corrected normalization moves the detail rows without moving a verdict. |
| `layout.atomic_write_text` / `layout.atomic_writer` | format | write a sidecar so a reader sees the whole file or the previous one. Nine writers were routed through these (S66) — if you write a sidecar yourself, use them. |
| `normalize.PRESENTATION_AUTHORITY_KEYS` / `SHORT_DESCRIPTION_MAX_CHARS` / `PRESENTATION_AUTHORITY_REASONS` | format | the registry-held card subtitle (RM133), and its ~120-character ceiling. Still inject-only: `strip_authority_keys` takes the set *you* pass. |
| `just_dna_compiler.compiler.load_spec` | compiler | public since S74, ending a private-symbol reach the enricher itself was making. |
| `just_dna_compiler.sweep` | compiler | `read_outputs`, `build_outputs`, `compare_outputs`, `gate_findings`, `measurement_json` — the release measurement behind `sweep`. **`build_outputs` returns `(outputs, failures)`**; a release script calling it directly must unpack. |

**Three new closed vocabularies**, all on the concordance record:
`VALID_AUTHORITY_CONCORDANCE` (`concordant`/`discordant`/`single`/`none`/`unchecked`),
`VALID_AUTHORED_POSITION` (`matches_all`/`matches_some`/`matches_none`/`absent`/`unchecked`) and
`VALID_AUTHORITY_CALL_STATUS` (`recorded`/`no_record`/`unchecked`). They are two axes deliberately kept
apart — *do the authorities agree with each other* and *where does the module sit* — because a single
set naming the authority inside its members needed a new member per source and failed a stress test at
five. Which authority spoke is **data**, in `clin_sig_authority_calls.csv`.

Also new: `VALID_WARNING_CODES` (71 members) and `CARRIED_WARNING_CODES` (11),
`VALID_RELEASE_OUTPUT_AXES` and `VALID_RELEASE_CHANGE_KINDS`. `VALID_VERIFICATION_CHECKS` gains one
member, `dataset_currency` (RM85) — if you validate check names against a hard-coded set, add it.

**`VALID_DIRECTIONS` gains a fifth member, `contested` (RM150)** — the one existing vocabulary that
grew. `unknown` had been carrying both *nobody assessed the sign* and *the sources disagree about it*,
which are an absence and a finding. **`unknown` keeps its original meaning**, so nothing a published
module already says changes and no row newly reports `needs_upgrade`; `contested` is added beside it.
If you validate `direction` against a hard-coded set, or switch on it exhaustively, add the member.
`stat_significance` deliberately gains nothing — a disputed *sign* is not a disputed *strength* — and
`derive.direction_from_state` can never produce it, because no legacy `state` value means it.
`derive.trimmed_state("contested")` is `"neutral"`, like `unknown`.

**One derived cell changed value, and it is a correction: `GeneMetricsRow.constraint_flags`
(RM110).** gnomAD's bulk-TSV route had been storing the source's **JSON array literal** verbatim, so
the published v4.1 snapshot writes `"[]"` on 17,403 of its 18,111 rows and a real literal
(`["outlier_mis","outlier_syn"]`) on the other 708 — **not one row null**. A consumer writing the
obvious `if row.constraint_flags:` therefore read **100 %** of snapshot rows as flagged where the true
figure is 3.9 %, and one splitting on `|` got a single bogus token instead of two flags. The column is
now pipe-joined-and-sorted when non-empty and **`None` when empty**, normalized on the model itself so
it reaches tables written before 0.7 as well as new ones. **If you have modules compiled from that
snapshot, their `gene_metrics.signature` and `artifact.digest` move on the next recompile** — that is
this fix arriving, not drift. `if row.constraint_flags:` is now the right test.

The registry `reference()` / `authoring_reference()` walks now renders **31 models, up from 28**
(`OverrideRow` and the two concordance rows). If you snapshot that output, it grew.

### 2.5 CLI

One new compiler command, one new enricher command group, four new `enrich` flags. Nothing was removed
or retyped.

| command | what it does |
| --- | --- |
| `just-dna-compiler sweep BEFORE AFTER [--spec-root DIR] [--release V] [--json]` | measures what a release changed about compiled output, and with `--release` runs the **release gate** — a measured movement no `ReleaseRecord` declares exits 1. It needs the previous release actually installed, so it is a release-sequence command rather than a test. Under `--json` stdout is one JSON document and the gate's prose goes to stderr. |
| `just-dna-enricher pubmind build` | reduces the ANNOVAR-distributed PubMind table to the snapshot the checks read |
| `just-dna-enricher pubmind publish` | refuses to publish it, and says why — the snapshot is operator-built and inject-only |

| `enrich` flag | default | note |
| --- | --- | --- |
| `--verify-datasets` / `--no-verify-datasets` | **on** | RM85. Asks each source in `sources.csv` whether it has published since the recorded release. **One request per source**, and only ClinVar has a probe today; everything else reports `unsupported`. Three-valued: `behind` is `True`, `False`, or `None` for nobody-asked — `--offline` makes every recorded release `unchecked`, never *up to date*. `strict` refuses on a superseded release and never on an unchecked one. |
| `--rederive` | off | re-asks every source about every subject and reports which answers changed. An ordinary run gap-fills and never re-asks. **`--verify-datasets` is its cheap neighbour — put it first.** It never shortens a table: answered replaces, could-not-ask keeps its rows. |
| `--keep-staging` | off | leaves the staged answers after a successful commit |
| `--pubmind-cache PATH` | `$JUST_DNA_PUBMIND_CACHE` | the second authority in the concordance check. With neither, PubMind's leg reads `unchecked` rather than agreement. |

`draft-panel` gains `--source clinvar|pubmind` and `--min-confidence`, and `hint variant` reports
PubMind's reading beside the rest (RM134 §§ C and D). PubMind is an LLM's reading of the literature and
is labelled as such at every surface; the measured corpus join agrees with ClinVar 62 % of the time.

### 2.6 Warnings: the same channel, now with codes

This is the release's biggest read-side change, and it is purely additive.

`compilation.warnings` **stays the complete list, with its exact text**, so nothing that greps a phrase
breaks. Beside it, `warnings_summary` says what each finding *is* and `carried` says whether an author
can do anything about it. Together they are the discriminator a consumer has been re-deriving from
prose:

```python
summary = manifest.compilation.warnings_summary      # {"rsid_expanded_to_multiple_loci": 9, ...}
actionable = [w for w in manifest.compilation.warnings if w not in manifest.compilation.carried]
```

Three properties are worth knowing before you build on it:

1. **A code names the finding, never the emission site.** A refactor cannot rename a published key.
   One code carries one remediation: two sentences cleared by the same edit share a code, two that
   need different edits do not.
2. **The vocabulary is a one-way door and it is closed.** Adding a member is minor-legal *for the
   writer*; a consumer pinned to an older `just-dna-format` will **refuse** a manifest carrying a code
   minted after their pin, because `warnings_summary`'s validator checks its keys. Upgrade the schema
   package alongside the compilers whose manifests you read.
3. **`carried` holds full message text**, which grows the channel **1.84× across the reference corpus**
   (1.96× on `pathogenic_clinvar`). That is the shape the item decided, not an oversight; three cheaper
   encodings are weighed as **RM138** rather than taken unilaterally. If you ship manifests over a
   wire, budget for it.

**Two more carried codes landed on 2026-08-31 (RM108)**, which is why the counts above read 71/11 and
not 69/9: `gene_validity_superseded` (a curating body re-curated its own claim, so an earlier row is
superseded and kept) and `gene_validity_currency_undecidable` (several curations of one claim and
nothing orders them — a tie on `classification_date`, or a row stating none). Both are carried because
the only edit available to an author is deleting a true record. They are the first fact-table findings
`validate` computes as well as `compile`, so a pre-flight now reports them too, and they stay **two
codes rather than one** on purpose: the archive having moved on and the archive not having said enough
to tell are different messages to a reader.

New pinned phrase: `SUPPRESSED_PHRASE` (`"suppress override(s) remove"`). The overlay's two other
warnings — an `update` reaching no row, and an overlay naming a table the module does not carry — are
pinned in [COMPILER.md](COMPILER.md). The new `clin_sig_concordance_contested` code is **actionable
rather than carried**, unlike its neighbour `verification_findings_recorded`, because it counts the
*post-overlay* rows: writing the answer clears the finding. It never escalates under `--strict`, for
the reason the check beneath it does not.

The sweep reports `carried_added` beside `actionable_added`, read off the after-manifest rather than
re-derived. `axes["warnings"]` still fires on any movement — narrowing it would change what every
record already written claims — and a pre-0.7 manifest reports every addition as actionable, which is
the safe direction.

### 2.7 An enrichment run is now a transaction

`enrich()` persisted nothing until its tail, so a run killed at minute 29 wrote zero bytes (RM128).
Now:

- **Each live link's answer is staged** to `.<name>.staging/answers.csv` beside `resolution.csv` as it
  arrives; the table itself is still written once, at the bottom, by a writer that renames into place.
  Same-directory staging is the correctness condition, not a convenience — `os.replace` is atomic only
  within one filesystem.
- What is staged is the **raw answer**, never the assembled row, so a resumed run reproduces the table
  an uninterrupted one produces. That is the P7 obligation and it has a test.
- **A refused `strict` run commits nothing**, now as a written promise asserted on the bytes on disk.
- **`flock` on the spec directory**, non-blocking, no lockfile — a second concurrent run fails fast
  rather than racing a merge.
- A **progress callback** is available; its unit is **subjects**, because `total` has to be known up
  front.

If you wrap `enrich` in a service or a job runner: the lock is the behaviour change to plan for, and a
crashed run now leaves a staging directory that the next run consumes rather than a truncated table.

### 2.8 The release record, and how to ask "must I recompile?"

RM126 exists because nothing told a consumer what a release changed about compiled output. The answer
is now data:

```python
from just_dna_format.release_records import needs_recompile
answer = needs_recompile("just-dna-compiler 0.6.1", "0.7.0")
answer.axes             # {"content_signature": False, "parquet_bytes": True, ...} — None means unknown
answer.declared         # the DeclaredChange rows covering the interval
answer.complete         # False when the span crosses a release with no record
```

Both spellings of a version are accepted — a bare `0.7.0` and the stamped
`just-dna-compiler 0.7.0` you would paste out of a manifest. Three things to hold onto:

- **The axes are three-valued.** `None` is *unknown*, never *no*. A span crossing a release with no
  record blunts to unknown rather than answering `False` over the releases it does know.
- **`warnings` is deliberately outside `RECOMPILE_DRIVING_AXES`.** Acting on it would mint a version
  across a whole catalogue for a message change.
- **`unmeasured` is not `unchanged`.** `0.7.0` names `cyp2c9_warfarin_grch37` there, for the reason in
  § 1.

---

## 3. Per-consumer check / change lists

### just-dna-registry (spec storage / re-publish)

**Change — do this before 0.7 lands, and it is the one item in this document with a deadline.**

1. **Add `overrides.csv` to `SPEC_DATA_FILES` / `RECOGNIZED_SPEC_FILES`.** A name missing there is a
   file dropped on the next re-publish, the way `licensing.csv` was lost before 0.16.2. The
   consequence is worse than for an ordinary table: an overlay row is an author's recorded judgement
   that a derived value is wrong, so losing it silently restores the value they rejected while the
   module keeps compiling green. This ask was carried in
   [INTEGRATION_0_6 § 9](INTEGRATION_0_6.md) as a warning about a coming release; the release is here.
2. Add `clin_sig_concordance.csv` and `clin_sig_authority_calls.csv` to the same list — derived, so a
   drop is recoverable by re-running `enrich`, but a re-publish that loses them silently shrinks the
   module.
3. **`reverse` now writes a `version:` key into `module_spec.yaml` where it wrote none** (RM103). If
   you round-trip specs, expect the authored `module.version` to survive where it used to be dropped —
   the pre-coercion spelling, so `v2` comes back as `v2`. Nothing hashes on it, and an explicit
   argument still wins.
4. If you hold module presentation metadata, adopt `short_description` (RM133) as a **registry-held
   override** of the card subtitle, bounded by `normalize.SHORT_DESCRIPTION_MAX_CHARS` (120).
   `module.description` remains the authored subtitle and a module with no override shows it,
   unchanged. The point of holding it beside the module is that amending it leaves `module_spec.yaml`'s
   bytes — and therefore `manifest.inputs` and any closure over them — untouched. Strip it with
   `strip_authority_keys(block, PRESENTATION_AUTHORITY_KEYS)` before validation; an authored
   `short_description:` is still refused by `extra="forbid"`, which is correct.

### just-dna-marketplace (catalog / storage / serving)

**Change**

1. **Adopt `needs_recompile` for the `revalidate` / `needs_upgrade` derivation** (§ 2.8). It is the
   derivation you were reconstructing from version comparisons. Treat a `None` axis as *unknown* and
   surface it as such — an artifact whose provenance crosses a release with no record has not been
   cleared, it has not been asked.
2. **Upgrade `just-dna-format` to 0.7 before serving 0.7-enriched modules.** § 1: a 0.6.6
   `ModuleManifest` refuses a manifest whose `verification.checks` carries `producer`, and it refuses
   on the null. If you parse manifests to build a catalog, this is the one hard break in the release.
3. **Three new parquets may appear in a file list.** Derive from `ARTIFACT_PARQUETS`, not from a
   hand-kept list.
4. Surface `clin_sig_concordance` on a module page if you render provenance. Render `opposed_count`
   and `unchecked_count`, not `row_count` alone: a row count on its own reads as confidence, and the
   two splits are what tell a reader whether the disagreement matters and whether the check ran.
5. Surface `authority_precedence` verbatim where you show `weighting` and `authorship`. **Do not
   compute with it** — nothing here does, and a consensus derived from it would publish a judgement as
   a fact.
8. **If you render `gene_validity.classifications`, it narrowed** (RM108): a module carrying a
   re-curated claim now publishes the current verdict instead of the pair. Render
   `superseded_count` beside it where you show the block — a nonzero value is what tells a reader the
   drift exists, since the pair used to be what showed it. The superseded rows are all still in
   `gene_validity.parquet`.
9. **If you cache `gene_metrics.signature`, expect it to move for snapshot-compiled modules** (RM110).
   The cell was wrong, not merely differently spelled, so this is a correction; see § 2.4.

**Check**

6. Re-pin stored `artifact.digest` values; `content_signature` needs nothing.
7. If you render or count warnings, switch to `warnings_summary` and `carried` (§ 2.6), and budget for
   the 1.84× channel growth.
8. `manifest.artifact.files` remains the source of truth for what a module contains — the publisher
   still never removes a file. Unchanged from 0.6 and still the most important line in that document.

### just-dna-lite (reference consumer, the annotating engine)

**Change**

1. **Stop substring-matching warning prose.** `warnings_summary` gives you the kinds and `carried`
   gives you actionability. The rule that used to need prose — *is this finding the author's problem?*
   — is now one membership test.
2. **Read the derived parquets, not the derived CSVs**, if you consume a spec tree directly. The
   overlay is applied at compile, so the parquet is post-correction and the CSV is not (§ 2.3).
3. If you read `verification`, upgrade `just-dna-format` (§ 1), and prefer the per-record `producer`
   over the block-level one when asking whether a record predates a fix.

**Check**

4. `studies.parquet` gains `statistical_test`. If you display or compare a study's `p_value` and
   `effect_size`, show it beside them: the column exists because a `p_value` from one analysis and an
   `effect_size` from another on one row is invisible without it, and the pair is *asserted* to belong
   together by nothing but the row.
5. `pharm_variants.parquet` gains `pmid`. It cites this row's own drug/genotype claim —
   `evidence_level` is somebody else's *grading of* the evidence and this points *at* it. Different
   axes; show both or neither.
6. `requires_callable` on `haplotypes` and `pharm_variants` is the CPIC assumption made explicit: an
   uncalled position taken as reference. The reference-homozygote `pharm_variants` row is the sharp
   case — it is unmatchable from a variant-only callset, where absence of an ALT record is not the
   call. **Empty is not `False`.** The two tables may legitimately disagree at one locus and no check
   compares them.
7. `clin_sig_concordance` gives you contested subjects, joinable on `(variant_key, genotype)`. If you
   badge a clinical call, this is what says the authorities disagreed. Nothing resolves the split, by
   design — do not read the first authority in `authority_precedence` as a winner.
8. **`gene_metrics.constraint_flags` is now a flag list rather than a JSON array literal** (RM110).
   `if row.constraint_flags:` is the right test, and it is right for the first time: the published
   gnomAD v4.1 snapshot carries `"[]"` on 96 % of rows, so that test used to be true for **every**
   snapshot row where 3.9 % of genes are actually flagged. Splitting on `|` now yields the flags. Any
   workaround you wrote for `"[]"` should come out.
9. **`direction` may now read `contested`** (RM150). If you switch on it, add the branch. It means the
   sources disagree about the *sign*, where `unknown` means nobody assessed it — an absence and a
   finding, which used to share one member. No existing module's rows change.

### just-dna-pipelines (compiler / discovery)

**Change**

1. **`sweep` belongs in your release sequence**, not in the test suite: bump → `uv sync` → `sweep
   --release <version>` → tag. It needs the previous release actually installed, and its own gate
   catches the likeliest operator error — running before `uv sync` propagated the bump, which builds
   both trees with one compiler and passes an unmeasured release.
2. Add `overrides.csv` to any spec-tree handling. `reverse` round-trips it, provided the filename is
   recognised.
3. Expect `enrich` to take a `flock` on the spec directory and to leave a staging directory behind a
   killed run (§ 2.7). If you run enrichments concurrently over one tree, that now fails fast instead
   of racing.

**Check**

4. **Re-baseline digest-comparison CI.** 14/15 measured modules move `artifact.digest`.
5. **A spec that passed `validate --strict` at 0.6.6 can newly fail it** — RM141, and possibly RM143
   when it lands. Both are cases where `compile --strict` was already going to refuse, so this moves
   the failure earlier rather than adding one.
6. New optional authored columns are available and nothing forces them: `statistical_test`,
   `requires_callable` on the two PGx locus tables, `pharm_variants.pmid`, and the `authority_precedence:`
   block in `module_spec.yaml`.

### just-dna-agents (MCP surface)

**Change**

1. The authoring reference grew to **31 models**, three new closed vocabularies, and 71 warning codes.
   `VALID_DIRECTIONS` also gained `contested` (RM150), which is the first *existing* vocabulary in this
   release to grow — an authoring agent picking `direction` from a stale list will not offer it.
   If you echo member lists to a model, regenerate them — `authoring_reference()` and the
   `RECOMMENDED_*` / `VALID_*` constants remain the replacements for `get_spec_format` / `list_colors`
   / `list_icons`, which drift further out of date again this release.
2. `overrides.csv` is a table kind an author can now be told about, and it is the answer to *"the
   derived value is wrong"* — which used to have no answer that survived a re-run.

---

## 4. Deprecated in 0.7, removed at 1.0

**Nothing new is deprecated in 0.7.** The 0.6 deprecations stand unchanged: `sources.csv` (the file),
`CopyNumberRow.modifier_cn`, the `panel:` block, and `ensembl_cache=`.

`ProvenanceItem.outranks` is **not** deprecated. Its succession by the overlay is filed as **RM135**
for 1.0 and will ship with a deprecation warning only once the overlay reaches *authored* tables,
which is where an author warned off `outranks` would have somewhere to go. If you read it, keep
reading it.

Already visible as 1.0 work, so do not design around it: **RM81** (`weights.parquet` splits the
genotype while the 0.4 families keep the string) and the `stats` counter retype.

---

## 5. Readiness

**Gates, run on this branch on 2026-08-31:**

| gate | result |
| --- | --- |
| `uv run pytest` | **3394 passed, 17 skipped, 0 failed** (2916 at the 2026-08-24 batch) |
| `uv run ruff check` | clean |
| Reference corpus under the 0.7 compiler | **16 / 16 compile** |
| 0.6.6 → 0.7.0 release sweep | 15 measured, gate exit 0 against the shipped record |
| 0.6.6 client parses 0.7 manifests | **15 / 16** — see § 1 |
| Open consumer inbox | **S78 open** (RM143, in the tree, uncommitted). S76 withdrawn as a duplicate of S66; S75 and S77 answered as RM140 / RM142. |
| Open roadmap items in format scope | RM103, RM108, RM110, RM117, RM136, RM137, RM138 — none blocking the cut; the last three were **filed by this release's own items**. |

**Not ready to cut, and the reason is one item rather than a gate.** RM143 is in the working tree with
its test untracked, and S78 is unanswered in the inbox. Everything else is committed, green and
measured. Two release-management notes on top of that:

1. The three `pyproject.toml` files already read `0.7.0` while `git tag` stops at `v0.6.6`. Anything
   published from here must be a real cut; **wipe `dist/` before building**, since `uv publish`
   uploads everything in it.
2. This release moves all three packages. Format gains models and columns, the compiler gains columns
   and `sweep`, the enricher gains the transaction, the PubMind surface and the currency check. There
   is no partial cut available.

---

## 6. What deliberately did not change

Each of these is a repair somebody has proposed. State them when asked:

- **`content_signature` does not move.** Measured at 0/15.
- **`schema_version` stays `"1.0"`.** It moves at a major.
- **`compilation.warnings` keeps its exact text and its completeness.** `warnings_summary` and
  `carried` are derived from it and replace nothing.
- **Nothing resolves an authority split.** No `majority`, no consensus call, no resolved winner — not
  in the tables, not in the manifest block, not from `authority_precedence`. Choosing between a
  declared order and a majority needs a weighting model this workspace has declined to invent three
  times. A consumer holding its own model computes what it likes from the detail rows.
- **`authority_precedence` is computed with by nothing.** Two modules differing only in it compile to
  byte-identical parquets with the same `content_signature` and the same `artifact.digest`.
- **The overlay has no `previous_value` column** and **no operation reports its own no-op** — both fall
  out of the operations being idempotent, which is what makes the double application safe.
- **`clin_sig_authority_calls.csv` is outside the overridable set**, by name: the author answers the
  contested question and does not get to rewrite what an archive published.
- **`resolution.csv` still gets no parquet.**
- **The attestation binding is unchanged** — RM133 was solved beside the module rather than by
  re-drawing the binding, because a field-aware partition along `content_signature`'s line would make
  a closure transferable across a rename.
- **`licensing.csv` stays outside the overlay's covered set** and keeps its own merge path.
- **Merge-not-clobber's behaviour is unchanged.** A re-run still gap-fills rather than re-asking; what
  changed is that a full re-derivation is now free, and `--rederive` is the switch when you want one.
