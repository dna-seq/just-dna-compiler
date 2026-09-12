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

**Everything this document describes is committed.** RM143 (S78) carried an "in the working tree and
not committed" label for a while; it **shipped on 2026-08-31** and the label outlived it in two places
while § 5 already said it had landed. A status claim here goes stale the moment the work lands —
[RM_TOC.md](RM_TOC.md) is the per-item file that is actually maintained, so check any status sentence
in this document against it rather than reading one as normative.

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

### Two old-reader breaks, and neither is where you would look

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

**And the second break is the case that does need one.** RM193 added `variant_impact_agreement` to
`VALID_VERIFICATION_CHECKS`, and `VerificationRecord.check` is validated against that vocabulary by a
field validator — not merely annotated with it. Measured against a real `just-dna-format==0.6.6` in a
clean environment:

```
rsid_currency              ACCEPTED by 0.6.6
variant_impact_agreement   REJECTED by 0.6.6 — "check must be one of [...]"
```

**It does not move the 15/16 row above**, and the reason is worth stating rather than leaving to be
inferred: no reference module runs `alphagenome check`, so no corpus manifest carries the member. The
row measures the corpus, and the corpus has not changed. A *consumer's* module that runs the check
does carry it, and a 0.6.6 reader refuses that manifest outright.

The two breaks compose in the direction you would hope: both are `VerificationRecord`, both are
fixed by the same upgrade, and a consumer that ignores `verification` meets neither. What they share
is the shape worth carrying — **a vocabulary is additive for the writer and closed for the reader**,
so every new member is a compatibility event for anybody validating against their own copy of it.

### Four checks can newly refuse

None of them is a schema change, and each is a fix:

- **An overlay that spells one key two ways is refused (2026-09-09, the pre-cut audit).** The overlay's
  key cells are raw author text and the derived rows are canonical; the *match* already went through
  the model, so `member=AFR` and `member=afr` each reached the same `afr` row, but the *grouping* did
  not, so the file-level "one operation per key group" rule had nothing to refuse. An `update` under one
  spelling beside a `suppress` under the other applied both, and two `update`s of one field under two
  spellings let the later row silently win. Both are errors now, from `apply_overrides`, so `validate`
  and `compile` meet them alike. **No reference example carries an `overrides.csv`**, and no published
  module does, so nothing in the sweep moved; a consumer's module can only be affected if its overlay
  already carried a contradiction it was not being told about.

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
- **RM143 (S78) — shipped 2026-08-31.** `compile --strict` refuses a module whose
  `verification.json` records a `genome_build_agreement` finding: the enricher has already diagnosed
  the rows as another assembly's, and the compiler was discarding that answer. It gates on a *record*,
  adds no reference and no network, is silent when no attestation exists, and `best_effort` still
  builds and warns. No reference example carries such a finding. `build_disagreement_error` is wired
  into **both** `validate_spec` and `compile_module`, so the refusal arrives at validate time
  (`@validate-refuses-all`). S78 is answered and archived.

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
| `expression_effects` | block or absent | RM194 + RM200. Summary of the tenth derived-fact sidecar: `signature`, `sources`, `datasets`, `row_count`, `variant_count`, `genes`, `measures`, `with_direction` / `without_direction`, **`without_distance`** and `max_distance_to_gene`. `without_distance` is the one to read before a join — the distance comes from the MANE lane, and a deployment without it records the absence rather than an interval edge, so a whole table of nulls is visible up front. |
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

**`content_signature` covers `overrides.csv` by its value cells only (S87, RM180).** A module carrying
an overlay hashes `table`/`subject`/`member`/`field`/`operation`/`value` and not
`reason`/`decided_by`/`decided_at`, so a registry keyed on the signature treats a reworded reason as
the same content — while `artifact.digest` and the `manifest.inputs` entry for the file still move.
Decided before the cut, so no published signature changed. If you compute the signature yourself rather
than calling `integrity.content_signature`, drop those columns via
`base.content_identity_exclusions(OverrideRow)` or your dedup will split on prose.

### 2.2 Parquets

**Four new files, so `ARTIFACT_PARQUETS` goes 19 → `len(ARTIFACT_PARQUETS)`.** Derive from the
constant; do not hand-keep a list — the count in this sentence was written when there were three and
is exactly the drift being warned about. The 0.6 guide says the same thing and it is the defect that
broke the publisher.

| parquet | when it appears |
| --- | --- |
| `clin_sig_concordance.parquet` | the module carries the concordance record (RM130) |
| `clin_sig_authority_calls.parquet` | ditto — the paired per-authority detail |
| `overrides.parquet` | the module carries an authored overlay (RM124) |
| `expression_effects.parquet` | the module carries per-gene expression effects (RM194 + RM200) |

`artifact.files` is name-sorted before hashing, so tuple position is invisible to the digest and these
land alphabetically rather than at the end.

**New columns** (the table is the list), all optional, all absent-means-nothing-was-said:

| parquet | column | item |
| --- | --- | --- |
| `studies.parquet` | `statistical_test` — which analysis produced this row's `p_value`/`effect_size`. Free text; `study_design` describes the *study*, this describes the *analysis*, and one study routinely runs several | RM140 |
| `studies.parquet` | `confidence` / `confidence_unit` — how far the **citing source** stands behind this evidence link, in that source's own units and unconverted (CIViC's `submitted`/`accepted`). They travel together: a magnitude with no instrument beside it is refused at the model | RM160 |
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
| `expression_effects.csv` | derived | per-gene expression direction, keyed `(variant_key, gene)` (RM194 + RM200). An `overrides.csv` target on that key |
| `.<name>.staging/` | transient | `enrich`'s staged raw answers (RM128). Removed on a successful commit unless `--keep-staging`; **a killed run leaves them either way, and the next run resumes from them.** |

**The overlay makes every covered derived table a pure build product** — the set is
`OVERRIDABLE_TABLES`, today `resolution.csv`, `frequencies.csv`, `gene_metrics.csv`,
`gene_validity.csv`, `clinical_assertions.csv`, `literature.csv`, `gwas_effects.csv`,
`clin_sig_concordance.csv` and `expression_effects.csv`. **Walk the constant rather than this
sentence**; it has been a count twice and gone stale twice. `derived = f(source, overlay)`, so
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
| `overrides.update_targets` / `classify_update_targets` / `LOSSY_OVERLAY_TABLES` | format | RM137's split. Only needed if you re-implement the overlay's findings; `apply_overrides(..., defer_unmatched=True)` suppresses the warning so a caller can classify it where the inputs exist. |
| `overrides.apply_overrides` / `OVERRIDABLE_TABLES` / `VALID_OVERRIDE_TABLES` / `VALID_OVERRIDE_OPERATIONS` / `OverrideRow` | format | the overlay. `OVERRIDABLE_TABLES` maps a table name to its subject/member fields — read it rather than restating the grammar. |
| `concordance.ClinSigConcordanceRow` / `ClinSigAuthorityCallRow` | format | the two record models, plus `CLIN_SIG_*_FACT_FIELDS`. |
| `integrity.clin_sig_concordance_signature` / `clin_sig_authority_call_signature` | format | two fact-hashes because they are two tables: a corrected normalization moves the detail rows without moving a verdict. |
| `layout.atomic_write_text` / `layout.atomic_writer` | format | write a sidecar so a reader sees the whole file or the previous one. Nine writers were routed through these (S66) — if you write a sidecar yourself, use them. |
| `normalize.PRESENTATION_AUTHORITY_KEYS` / `SHORT_DESCRIPTION_MAX_CHARS` / `PRESENTATION_AUTHORITY_REASONS` | format | the registry-held card subtitle (RM133), and its ~120-character ceiling. Still inject-only: `strip_authority_keys` takes the set *you* pass. |
| **`caches.CACHE_LANES` / `CacheLane`** | enricher | RM176. The cache registry: one entry per lane carrying its three stages (`resolve`, `rebuild`, `ensure`), where it lives (`subdir`, `default_dir`), its licence terms, its `parents` when it is derived from other lanes (RM171: `mitomap_miss` names `mitomap` and `clinvar`, and an absent parent is `built=None` naming it), its publish repo, and — for each stage it lacks — **the reason as a field** (`unpublished`, `unbuilt`). Read it instead of hard-coding which snapshots exist; a hand-kept list is what this replaced, and it had drifted by three lanes. **`env_var`** (S89, RM184) is the variable that overrides the lane's location, the same constant its resolver reads; derive the full set of cache variables as `{lane.env_var for lane in CACHE_LANES} \| {locations.CACHE_BASE_VAR}`. |
| **`caches.prepare_caches(lanes=None, *, declared_use, pins, sources)`** | enricher | provisions every lane by its own route and returns one `PrepareOutcome` per lane, in registry order. `ready` is tri-state and `route` is `present` / `pulled` / `built` / `none` — a deployment auditing its caches has to tell a snapshot it *fetched* from one it *made*, and `release.json` names the release but not the route. This is what `cache prepare` calls. |
| **`caches.rebuild_caches(lanes=None, *, out, declared_use, pins, sources)`** | enricher | the rebuild loop, returning `RebuildOutcome` per lane. Tri-state: `built is None` means the lane cannot run unattended (an Elsevier workbook, a personal key, a release to pin, or built elsewhere) and is **not** a failure. |
| **`caches.prepare_lane` / `rebuild_lane` / `RebuildRequest`** | enricher | the single-lane forms, if you drive your own loop. |
| **`download.SnapshotNotPublished`** | enricher | a repo that does not exist yet, distinguished from a download that broke. Subclasses `FileNotFoundError`, so a handler catching that still catches this. |
| **`locations.resolve_acmg_reference` / `resolve_strchive_reference` / `resolve_drug_labels_reference`** | enricher | three new caches, with `default_*_cache_dir` beside each and `$JUST_DNA_ACMG_CACHE` / `$JUST_DNA_STRCHIVE_CACHE` / `$JUST_DNA_DRUG_LABELS_CACHE`. |
| **`locations.missing_credential_reason(var)`** | enricher | why a credential is unusable, distinguishing **absent** from **exported empty** — `override=False` means `export FOO=` outranks a `.env` where `unset FOO` does not, and the two want different remedies. |
| `just_dna_compiler.compiler.load_spec` | compiler | public since S74, ending a private-symbol reach the enricher itself was making. |
| `base.since` / `base.field_first_seen` | format | RM146. Which release each authored column first appeared in, declared on the field and read back as `{field: release}`. **This is what tells an "Extra inputs are not permitted" finding apart from a typo**: `[curator]` is a 0.6.5 column, `[curatr]` is a mistake, and the two want opposite actions. Per `(model, field)` — `curator` is on `VariantRow` from 0.2.0 and on `StudyRow` only from 0.6.5. |
| `just_dna_compiler.compiler.load_overlay` | compiler | public since RM136, for the same reason: the enricher needs the author's overlay to stop re-reporting a finding they have already answered, and a second reader of `overrides.csv` is the drift the overlay's design refuses. |
| `just_dna_compiler.sweep` | compiler | `read_outputs`, `build_outputs`, `compare_outputs`, `gate_findings`, `measurement_json` — the release measurement behind `sweep`. **`build_outputs` returns `(outputs, failures)`**; a release script calling it directly must unpack. |

**Three new closed vocabularies**, all on the concordance record:
`VALID_AUTHORITY_CONCORDANCE` (`concordant`/`discordant`/`single`/`none`/`unchecked`),
`VALID_AUTHORED_POSITION` (`matches_all`/`matches_some`/`matches_none`/`absent`/`unchecked`) and
`VALID_AUTHORITY_CALL_STATUS` (`recorded`/`no_record`/`unchecked`). They are two axes deliberately kept
apart — *do the authorities agree with each other* and *where does the module sit* — because a single
set naming the authority inside its members needed a new member per source and failed a stress test at
five. Which authority spoke is **data**, in `clin_sig_authority_calls.csv`.

Also new: `VALID_WARNING_CODES` and `CARRIED_WARNING_CODES` — **take both lengths from the
constants**, which is the same rule § 8 states about any counted claim here,
`VALID_RELEASE_OUTPUT_AXES` and `VALID_RELEASE_CHANGE_KINDS`. `VALID_VERIFICATION_CHECKS` gains
**eight** members — `dataset_currency` (RM85), `pgs_accession_currency` and `pgs_metadata_agreement`
(RM163), `repeat_band_agreement` (RM165), `literature_coverage` (RM167), `regulator_label_agreement`
(RM166), `published_refutation` (RM170) and `evidence_status_currency` (RM160) — if you validate check
names against a hard-coded set, take the set from the vocabulary rather than adding them by hand.

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

The registry `reference()` / `authoring_reference()` walks render more models than 0.6.6 did —
`OverrideRow`, the two concordance rows and `ExpressionEffectRow` among them. **Count them off
`len(authoring_reference()["models"])`, never off this sentence**: it said 31 while the release
shipped 32, because the AlphaGenome round landed after the number was taken. If you snapshot that
output, it grew.

**One exception contract tightened (RM230).** `literature.EuropePmcClient.lookup` used to let its
transport library's types escape — `httpx.HTTPStatusError`, `httpx.ConnectError`, and
`json.JSONDecodeError` on a 200 that is not JSON. It now raises `LiteratureUnavailable` (a subclass of
`LiteratureEnrichmentError`) on all three. **If you catch `httpx` types around this call, that
`except` will stop firing**; catch the tier's own type instead, which is what every other client here
already promised. `EuropePmcClient.fulltext` is unchanged and still returns `None` for
could-not-be-retrieved — the two methods answer different questions, which is how the leak survived
review.

### 2.5 CLI

One new compiler command, several new enricher commands, four new `enrich` flags. Nothing was removed
or retyped — **except one extra**: `just-dna-enricher[alphagenome]` is gone, replaced by
`[atlas]` (RM192). It pulled the upstream SDK at **550 MB and 47 packages** (measured 2026-09-11); the replacement is
`grpcio` + `protobuf`, measured at 19 MB and +2. Nothing in the tier imported the old one, so the
only breakage is a deployment that named it in an install line. **Two behaviour changes for anyone scripting a builder**: `clinpgx build` refuses the
retired `clinicalAnnotations.zip` member names and exits 1 naming `summaryAnnotations.zip` (RM175 —
the old filename still answers 200 and serves a frozen 2025 object), and every builder's `--out` now
defaults to `data/repro/<lane>/` — `cpic build`, `clinpgx build`, `clinpgx build-labels` and
`pharmvar build` no longer require it, the nine that defaulted to a bare relative name no longer
write into the working directory, and `civic reproduce` moved to `data/repro/civic_reproduce`
([RM177](ROADMAP_HISTORY.md#rm177--nine-builders-wrote-their-snapshot-beside-pyprojecttoml-because-the-rule-that-forbade-it-was-prose)). A caller passing `--out` is unaffected.

**One flag added late in the line, and it is the one an error message tells you to use.**
`check-identifiers` gains `--use` (`unstated | non-commercial | commercial`, default `unstated`),
because a PGS score licensed *"freely available to the academic community for research use"* records
`commercial_use=False` at the `annotation` layer — where the compile gate reads — and the refusal has
always said to re-run with a declared use. Until RM230 that flag did not exist, and
`merge_sources_csv` is never-clobber, so the only exit was editing `sources.csv` by hand. Measured
against the live Catalog: **6 of the first 250 scores** are in that class. If you script
`check-identifiers` over modules citing PGS scores, pass `--use` or expect the compile to refuse.

| command | what it does |
| --- | --- |
| `just-dna-compiler sweep BEFORE AFTER [--spec-root DIR] [--release V] [--json]` | measures what a release changed about compiled output, and with `--release` runs the **release gate** — a measured movement no `ReleaseRecord` declares exits 1. It needs the previous release actually installed, so it is a release-sequence command rather than a test. Under `--json` stdout is one JSON document and the gate's prose goes to stderr. |
| `just-dna-enricher pubmind build` | reduces the ANNOVAR-distributed PubMind table to the snapshot the checks read |
| `just-dna-enricher pubmind publish` | refuses to publish it, and says why — the snapshot is operator-built and inject-only |
| **`just-dna-enricher cache prepare`** | RM176. **The one a deployment wants.** Leaves the machine with every cache it can have: pulls the published snapshots, builds the five that are unpublished for recorded reasons (PharmVar, PubMind, MANE, ACMG, and the derived `mitomap_miss`, which would only pin somebody else's ClinVar if it travelled). A present cache is left alone, so it is idempotent. |
| **`just-dna-enricher cache rebuild`** | RM176. Re-derives every lane into `<base>/<lane>/` (default `data/caches`), **never in place**, with `--publish` to upload each. The complement of `prepare`: rebuild cuts a fresh set, prepare fills in what is missing. |
| **`just-dna-enricher strchive publish`** / **`clinpgx publish-labels`** / **`acmg build`** / **`mane build`** / **`strchive build`** / **`clinpgx build-labels`** | RM176 and RM168. Three lanes gained a publish command; three gained a cache and a resolver. |
| **`just-dna-enricher alphagenome build --input <file>`** | RM191. Re-encodes AlphaGenome's AVI artifact into a cache lane. `--input` is **required** and there is no default URL — the source is behind an eligibility gate, so this tier never fetches it. |
| **`just-dna-enricher alphagenome check <spec>`** | RM193. Cross-checks a module's variants against those scores; reports, never repairs. Offline unless `--threshold` names a cut the local artifact cannot decide, and it **refuses** to refine more than `--refinement-cap` rows over the network. |
| **`just-dna-enricher atlas generate`** | RM192/RM196. Fetches the pinned upstream `.proto` sources and builds the gRPC bindings. Once per checkout; a released wheel carries them already. Needs the `[dev]` group for `grpcio-tools`. |

| `enrich` flag | default | note |
| --- | --- | --- |
| `--verify-datasets` / `--no-verify-datasets` | **on** | RM85. Asks each source in `sources.csv` whether it has published since the recorded release. **One request per source**, and only ClinVar has a probe today; everything else reports `unsupported`. Three-valued: `behind` is `True`, `False`, or `None` for nobody-asked — `--offline` makes every recorded release `unchecked`, never *up to date*. `strict` refuses on a superseded release and never on an unchecked one. |
| `--rederive` | off | re-asks every source about every subject and reports which answers changed. An ordinary run gap-fills and never re-asks. **`--verify-datasets` is its cheap neighbour — put it first.** It never shortens a table: answered replaces, could-not-ask keeps its rows. |
| `--keep-staging` | off | leaves the staged answers after a successful commit |
| `--pubmind-cache PATH` | `$JUST_DNA_PUBMIND_CACHE` | the second authority in the concordance check. With neither, PubMind's leg reads `unchecked` rather than agreement. |

**Three caches became reachable without a flag, which changes what a no-flag run does.** `check-acmg`,
`check-repeat-bands` and `clinpgx check-labels` each took an explicit path and looked nowhere else; each
now reads a provisioned snapshot first (`$JUST_DNA_ACMG_CACHE`, `$JUST_DNA_STRCHIVE_CACHE`,
`$JUST_DNA_DRUG_LABELS_CACHE`, or the shared cache base). **`check-acmg` is the one to look at**: with
no snapshot it fell through to scraping NCBI's page, which serves SF **v3.2** while ACMG published
v3.3, so a correctly authored v3.3 row came back `unverifiable`. A consumer that provisions caches
centrally will see that check start answering. An explicit flag still wins everywhere.

`cache pull`'s **exit code changed**: a repo that has never been published is reported and no longer
counted as a failure, so `pull` on a fresh machine exits 0 where it used to exit 1. A download that
breaks still fails and still exits 1.

`draft-panel` gains `--source clinvar|pubmind|civic|mitomap-miss` and `--min-confidence` (`--gene` is
required for every source but `mitomap-miss`, where the increment over ClinVar is the query — RM171),
`draft-repeats` drafts `repeat_alleles.csv` identity rows from STRchive (RM165), `check-repeat-bands`
compares an authored band table against it, `litvar coverage` / `litvar gene` ask LitVar2 which papers
name an allele (RM167), `civic citations` drafts the citations CIViC's dated files cannot reach and
records the source's review state in `StudyRow.confidence` (RM160), `clinpgx check-labels` compares a
drug claim against five regulators' labels (RM166), `mitomap build` / `miss` / `publish` are the two
MITOMAP lanes (RM171), and `hint variant` reports PubMind's reading beside the rest (RM134 §§ C
and D). PubMind is an LLM's reading of the literature and
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
   uncompressed (1.96× on `pathogenic_clinvar`) — and **1.06× gzipped**, 1.13× on that worst case.
   `carried` is a verbatim subset of `warnings`, which is exactly what DEFLATE's back-references
   eliminate, so **if you ship manifests over a wire, serve them compressed and the duplication is
   essentially free**; the whole with-`carried` payload gzips to 0.21× the *uncompressed*
   warnings-only one. Measured on 2026-08-31, which closed **RM138**: the encoding stands, and the
   three cheaper ones stay rejected (indices break the subtraction that the field exists for, a code
   list is what `warnings_summary` already gives you).

**Two more carried codes landed on 2026-08-31 (RM108)**, which is why the counts above read 71/11 and
not 69/9: `gene_validity_superseded` (a curating body re-curated its own claim, so an earlier row is
superseded and kept) and `gene_validity_currency_undecidable` (several curations of one claim and
nothing orders them — a tie on `classification_date`, or a row stating none). Both are carried because
the only edit available to an author is deleting a true record. They are the first fact-table findings
`validate` computes as well as `compile`, so a pre-flight now reports them too, and they stay **two
codes rather than one** on purpose: the archive having moved on and the archive not having said enough
to tell are different messages to a reader.

**The overlay's unmatched-update warning split in two on 2026-08-31 (RM137), and one of them is
reworded — re-grep if you match its prose.** `overlay_update_target_unreachable` is new and says no
artifact of this module can carry the row (a mistyped subject, or a correction aimed at a row the
compiler drops); `overlay_update_unmatched` now means the narrower and more useful *the subject is
cited or positioned and the sidecar is short — re-run the enricher*. Only `literature.csv` and
`resolution.csv` are affected, and the older text still stands verbatim for the other six overridable
tables. **The point of the split is that both are now stable across `compile → reverse → compile`**,
where the single warning used to fire on the second lap only — so if you diff a module's warnings
against its own round trip, that difference is gone.

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
- **A licence row is part of its table's commit (S98, RM231).** Every fact pass — `enrich`,
  `assertions`, `gene-metrics`, `frequencies`, `gene-validity`, `gwas`, `clingen`, `alphagenome
  expression` — merges its `SourceRow` inside the data table's atomic write, and reads `licensing.csv`
  before its fetch. A scaffold's placeholder row now fails in a second and leaves nothing; it used to
  fail after the query with the data table already on disk and no licence record, which the compile
  gate then passed. `layout.atomic_writer(before_commit=…)` is the seam if you write a table of your own.
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
- **An unstamped `compiler_version` is unknown, not a crash (S88, RM183).** `needs_recompile(None,
  current)` — and `""` — answers every axis `None` with `complete=False` and `compiled_under=None`, so a
  loop over stored manifests survives one that stamped nothing. A present but unreadable stamp
  (`"0.7"`, `"v0.7.0"`, a trailing note) still raises `ValueError`, now quoting the whole stamp. Two
  fields widened to `str | None`: `RecompileAnswer.compiled_under` and `span[0]`.
- **The cache status projection is a function (S91, RM204).** `caches.lane_status()` returns one
  `LaneStatus` per lane in registry order — `state` in `present` / `absent` / `occupied`, `looked_in`,
  `path`, `release`, `release_unreadable` — and `cache status` renders it. `occupied` is new: the place
  the lane looks is non-empty and holds no snapshot, the target `prepare` refuses; it printed as
  `absent` before. Serve it rather than re-deriving the loop from `CACHE_LANES`.
- **`LookupClients` has one lazy path (S92, RM206).** `bundle.ensure(name, factory)` builds a client
  under a lock on first use and keeps it; every leg uses it, so an unfilled field is paced from the
  first call like a filled one, and the per-request build-and-close six legs did is gone. `close()`
  walks `CLIENT_FIELDS`. A `lookup_*` call given no bundle now closes the one it built. Nothing
  changes for a host that fills every field; a host that fills some can stop.
- **`PacingGate.spent` (S95, RM203).** Admissions so far, one per `wait()` that returned, bumped under
  the slot lock. That is one upstream **attempt** rather than one call, because the clients wait inside
  their retry loop — so a host meters egress from it instead of charging by request shape. A `waited`
  total was refused deliberately: the sleep is outside the lock by design
  (`@shared-pacing-gate`), so a figure for it would be a number nothing guarantees.
- **The hint payload names lanes, not paths (S93, RM205).** `VariantHint.checked` holds labels only
  (`ensembl`, `clinvar`, `ensembl-rest`), the unreadable-snapshot finding interpolates the label, and
  the new `VariantHint.snapshots` (label → path) is the one field carrying a filesystem path — drop it
  to serve the hint from a host whose layout is not the caller's business. A reader matching the old
  `str(path)` members of `checked` sees lane names instead.
- **A lane declares its size (S97, RM229).** `CacheLane.approx_mb` (order of magnitude, whole MB,
  `None` = unmeasured), `LaneStatus.size_bytes` (measured, present lanes only, printed by
  `cache status`), and `caches.provisioning_closure(lane)` — the lane plus its transitive parents in
  registry order, which is what a blank box actually pays for a derived lane.
- **Either spelling of a sidecar is a key (S96, RM224).** `layout.sidecar_spellings`, and every
  helper over it (`resolve_sidecar`, `sidecar_write_path`, `sidecar_candidates`, `preferred_spelling`),
  accept the table key or any of its spellings — `"licensing.csv"` now finds a module's `sources.csv`
  instead of creating a second copy beside it. New public `layout.sidecar_key(name)` is the
  filename → key map, derived from `SIDECAR_SPELLINGS`; a consumer that built its own can delete it.
- **A declaration says which modules it can reach (S90, RM201).** `DeclaredChange.requires` names the
  dotted manifest paths a module must carry for the change to apply — `("gene_metrics",)` on RM110's
  corrections, `("gene_validity",)` on RM108's — and `change.reaches(manifest)` evaluates it for you,
  three-valued: `False` is the only answer to act on (skip the module), `True` is *not excluded*, and
  `None` is *unstated*, which a sweep keeps. `answer.declared_for(manifest)` is that filter over the
  whole answer; `answer.corrections` after it is the set worth an immutable PATCH. Records written
  before the field read `None` on every row, so a consumer ignoring it keeps today's behaviour exactly.

---

### CIViC — a new source, and none of it is a schema change (RM152)

**Nothing here changes the artifact, the manifest or any model.** No column, no table, no vocabulary
member, no signature. A consumer that never runs the enricher sees none of it, and a module drafted
from CIViC is an ordinary module: the rows it writes are `direction`, `state`, `gene`, `rsid`,
coordinates and `conclusion`, every one an authored column that has existed since 0.3.

| Surface | What it is |
|---|---|
| `just-dna-enricher civic build --release <date>` | Builds a snapshot from a **dated** CIViC bulk release into `data/civic.parquet` + `release.json`. Three input files, and a fourth behind `--submitted` — the dated `<date>-civic_accepted_and_submitted.vcf`, which widens the basis to accepted+submitted and adds `status_counts`, `vcf_evidence`, `unjoinable_submitted` and a per-row `evidence_status` (RM169); `--evidence/--variants/--profiles` build offline from local copies. No `--use` flag — CC0 permits every declaration, so a gate there would never gate. |
| `draft-panel --source civic` | Drafts the **`direction`** axis (`risk`/`protective`), never `clin_sig`. `--clin-sig` is reported inert under it rather than silently ignored. |
| `--civic-cache` / `$JUST_DNA_CIVIC_CACHE` | Points at a built snapshot. There is no published one to download. |
| `CIVIC_TERMS` in `licensing.py` | CC0 1.0, permissive on all three axes. A module drafted from CIViC lands `civic` in `sources.csv` and taints nothing. |

**One behaviour change a provider author must know about**, and it is the only thing here that can
break existing code: `append_partial_rows` now **raises `ValueError`** when the `PartialRow`s in one
batch do not share a `match_on`. It previously accepted them and silently mismatched — the covered-set
is built from the first partial's tuple and every signature compared against it, so a mixed batch could
never match and re-added those rows on every lap. Every in-tree caller already passes one constant
tuple; an out-of-tree provider computing `match_on` per row was already broken and now finds out.

**Two facts about the source worth carrying**, because a consumer comparing our numbers with CIViC's
own will otherwise disagree with us. Its GraphQL API defaults to `status: NON_REJECTED` and serves
11,518 evidence items; the dated bulk TSV is `accepted`-only at 4,903. We build from the TSV by
default, and `release.json` records `status_basis` for exactly that reason — `accepted` or, with
`--submitted`, `accepted+submitted` (RM169). And CIViC publishes **no GRCh38 coordinates** — rows are
placed by the rsID and GRCh38 RefSeq accession it publishes beside them, never by lifting a coordinate
over; where neither is published, two more `identity_derivation` members place a row: `vcf_csq`, from
the CSQ block of the wider VCF (RM169), and `curated_name`, from the identity the source states in a
variant's own name (RM159, 33 variants resolved by a recorded procedure rather than a lookup). A row
also carries `evidence_molecular_profile_id` / `_name` beside its join key, so a claim about a
combination profile is visible as one — a composite is the inequality of the two ids, counted in
`release.json` as `composite_profile_rows` (RM174).


### AlphaGenome — two sources under one name, and one of them is non-commercial (RM191–RM200)

**RM191–RM199 was almost none of a schema change**; **RM194 + RM200, which landed on 2026-09-11,
is one.** The first round added no column, no table, no manifest field and no signature — a consumer
that never runs the enricher saw one thing only, the new `variant_impact_agreement` check member,
which is the second old-reader break in § 1. The second round added the **tenth derived-fact
sidecar**: `expression_effects.csv` → `expression_effects.parquet`, `expression_effect_signature`, a
`manifest.expression_effects` block, an `overrides.csv` target keyed `(variant_key, gene)` and the
`expression_effect` source layer. All of that is in § 2.1–2.3 with the rest of the surface delta;
none of it is authored, so `content_signature` does not move.

**The one thing to take from this section if you take nothing else: `alphagenome_avi` and
`alphagenome_atlas` are two source names, and they carry two different licence classes.** The AVI
artifact is Permissive Use and a module drafted from it stays sellable; the Atlas API's output is
**non-commercial only**. One `(source, layer)` key cannot carry two licence classes, which is why the
second name exists rather than a second row. A consumer that reads "AlphaGenome is permissive" off the
AVI row and then joins a table produced by `alphagenome expression` has mis-licensed the module.

| Surface | What it is |
|---|---|
| `just-dna-enricher alphagenome build --input <file>` | Re-encodes AlphaGenome's AVI artifact into a cache lane. **`--input` is required and there is no default URL** — the 88.5 GB source sits behind a sign-in whose eligibility clause bars *classes of holder*, so acquisition is the operator's act under their own acceptance |
| `just-dna-enricher alphagenome check <spec>` | Cross-checks a module's variants against those scores. Reports, never repairs. Mostly offline: without `--threshold` there is no question the local snapshot cannot answer |
| `just-dna-enricher atlas generate` | Builds the Atlas gRPC bindings from pinned upstream sources. Once per checkout; a released wheel carries them already |
| `--alphagenome-avi-cache` / `$JUST_DNA_ALPHAGENOME_AVI_CACHE` | Points at a built or pulled snapshot |
| `just-dna-enricher[atlas]` | **New extra**: `grpcio` + `protobuf`, measured at 19 MB and +2 packages. The `alphagenome` extra is **deleted** — it was **550 MB and 47 packages** |
| `variant_impact_agreement` | **New `VALID_VERIFICATION_CHECKS` member.** The one thing here a format-tier consumer sees |
| `ALPHAGENOME_AVI_TERMS` in `licensing.py` | `commercial_use=True`, `share_alike=False`, `redistribution=True`. A module drafted from it lands `alphagenome_avi` in `sources.csv` |
| `just-dna-enricher alphagenome expression <spec> --gene <SYMBOL>` | Fills `expression_effects.csv` from the Atlas (RM194 + RM200). `--gene` is mandatory in **both** span forms — the server-side filter is a requirement, not an optimisation. **`--use non-commercial` is required or the run writes nothing**. Since RM231 it reads `licensing.csv` before the query and lands its licence row inside the table's commit, so a scaffold's placeholder row refuses in a second and leaves no table behind |
| `ALPHAGENOME_ATLAS_TERMS` in `licensing.py` | `commercial_use=False`. A module fed by `alphagenome expression` lands **`alphagenome_atlas`** in `sources.csv`, at the `expression_effect` layer |

**Three things that will surprise a consumer**, and none is a schema question:

**The lane is pullable but not buildable by the tier.** It is the first with `rebuild=None` *and* a
builder: this tier cannot fetch the source, but the re-encoded snapshot is publishable, so an operator
who may not download the artifact can still `cache pull` it. `cache status` reports it like any other
lane.

**The stored scores are integers, and you should compare them as integers.** `raw_score` is `Int32` at
a scale of 10⁵ — exactly lossless, since the source prints at most five decimals. Recovering a float
with `raw_score_e5 / 1e5` disagrees with the printed value on **53% of rows**, because the division
rounds a second time. `score >= 0.1` is `raw_score_e5 >= 10_000`.

**`PHRED` is not stored, and the file that reconstructs it is not optional.** It is an exact
within-corpus rank, so `avi_knots.parquet` carries the curve in 466 KB instead — as an *interval* per
printed score, which makes threshold safety decidable in advance: a threshold is unsafe iff it lands
inside a knot's span. Genome-wide exactly one does, at 3. A snapshot without that file holds scores
nobody can rank, and `alphagenome check` refuses it.

**The artifact is wide by position** (RM197): one row per locus, `chrom, pos, ref, alt0, alt1, alt2`,
and **no `alt` column**. Which base each column means is `{A,C,G,T} − ref` ascending — a function of
`ref` alone, so nothing travels beside the data. `alphagenome_avi_build.to_long()` recovers
`(chrom, pos, ref, alt, score)` rows if you want them. Apply it to a *filtered* frame: over the whole
corpus it is 2.9 billion loci becoming 8.8 billion rows, which is the shape the layout exists to avoid
storing.

**One change that is not about AlphaGenome at all.** `just-dna-enricher`'s build backend moved from
`uv_build` to **hatchling** (RM196), because the Atlas bindings are generated at build time and
`uv_build` has no build hook. Backends are declared per package, so `just-dna-format` and
`just-dna-compiler` are untouched. **This matters only if you build the enricher from source**; a
wheel or an editable install behaves as before. The `.proto` sources are no longer vendored in the
repository — it carries a commit id and a sha256 per file, and the build fetches and verifies them —
so a source build needs network **once**, and a released sdist carries the files already.

**And publishing a snapshot is now two commits** (RM199): the payload, then `release.json`. The
description is what tells a puller which release it holds, so it must never arrive before the bytes it
describes. That is the only thing this tier adds to the upload — `huggingface_hub` 1.x made
`upload_folder` multi-commit and deprecated `upload_large_folder`, so one call carries a payload at
any size and a declared layout retirement rides it as `delete_patterns`.

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
   on the null. If you parse manifests to build a catalog, this is the hard break in the release —
   and since RM193 there is a **second** one on the same model, a `check` of
   `variant_impact_agreement` that 0.6.6's vocabulary validator rejects. One upgrade fixes both. The
   general form is worth building against rather than patching per member: **a vocabulary is additive
   for the writer and closed for the reader**, so validating a manifest against your own copy of one
   makes every future member a break.
3. **New parquets may appear in a file list.** Derive from `ARTIFACT_PARQUETS`, not from a
   hand-kept list — this line said "three" while the release shipped four, which is the failure the
   advice is meant to prevent.
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

0. **Swap `cache pull` for `cache prepare` in provisioning** (RM176). `pull` fetches the published
   snapshots and stops, and four lanes are not published for recorded reasons — so a deployment that
   only pulled has been running with four caches absent and the checks reading them skipping
   themselves. `prepare` pulls what is published and builds the rest; it leaves a present cache alone,
   so it is safe to run on every deploy. In Python it is `caches.prepare_caches()`. Two smaller
   consequences: `cache pull` no longer exits 1 for a repo that has never been published, and three
   checks (`check-acmg`, `check-repeat-bands`, `clinpgx check-labels`) now find a provisioned snapshot
   with no flag — `check-acmg` in particular stops falling back to a page that serves SF v3.2.
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
   It also gains `confidence`/`confidence_unit` — the citing source's own review state, unconverted.
   Read them together or not at all: the value is meaningless without the instrument beside it, and
   `civic_evidence_status` values (`accepted`, `submitted`) are CIViC's ladder rather than anything
   this format grades. A row with neither cell is the ordinary case and says nothing either way.
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

### Anyone who might touch the AlphaGenome lane (RM191–RM199)

**Check**

1. **Nothing is required of you.** No module carries AlphaGenome data unless somebody drafts it in,
   and no reference module does. The only surface that reaches a format-tier consumer is the new
   check member above.
2. **If you parse `sources.csv`**, a module built on this source carries `alphagenome_avi` with
   `commercial_use=True`, `share_alike=False`, `redistribution=True`. The first two are documented —
   the classifying page is pinned in `docs/vendor/` — and **the third is a recorded reading** of the
   Output Terms' "open source release" carve-out, not a quoted clause. The row cannot show that
   difference; ROADMAP_HISTORY RM195 names it.
3. **Two obligations travel with the data and are not expressible on a `SourceRow`**: no training of
   variant-effect models, and Google may demand deletion of Output already in your possession on
   breach — not only on termination. If you redistribute a module carrying these scores, the
   snapshot's `LICENSE.txt` has to travel with it; restriction 3b makes that an enforceable provision
   rather than a courtesy.

**Change**

4. **Read scores as integers.** `raw_score_e5` is exact; dividing it back disagrees with the
   published value on 53% of rows.
5. **Do not treat a missing row as a zero.** The corpus covers ~95% of the assembly and contains
   672,931 genuine zeros. Absence is absence.

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
5. **A spec that passed `validate` at 0.6.6 can newly fail it** — RM141, RM143 and **RM207**, all
   shipped. Each is a case where `compile` was already going to refuse, so this moves the failure
   earlier rather than adding one. RM207 is the widest of the three and the only one that is not
   `strict`-only: a `resolution.csv` row recording `rsid_status=withdrawn` now refuses at `validate` in
   **both** modes, because `compile` refuses it in both modes and did so without the pre-flight saying
   anything. Two consequences for a consumer running `validate` in CI: a spec carrying such a row
   fails earlier than it used to, and one whose *expanded* variant carried it used to compile clean —
   that artifact was never legal and is now refused.
6. New optional authored columns are available and nothing forces them: `statistical_test`,
   `confidence`/`confidence_unit` on `studies.csv`, `requires_callable` on the two PGx locus tables,
   `pharm_variants.pmid`, and the `authority_precedence:` block in `module_spec.yaml`.

### just-dna-agents (MCP surface)

**Change**

1. The authoring reference grew by several models, three new closed vocabularies, and a warning-code
   vocabulary — **read the counts off `authoring_reference()` and `VALID_WARNING_CODES`.** Two
   numbers spelled here were already stale when a consumer measured them.
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

**Gates, re-run on this branch on 2026-09-12 at `83b1674`, the commit `v0.7.0` was retagged to.** The
first `v0.7.0` tag sat at `8b981f6` (2026-09-11) and three commits landed after it inside the same
uncut number — RM231, a licensing hole (S98); the atlas-generate message fix; and a release-record
declaration the gate itself demanded — so the tag was deleted and re-cut at `83b1674` rather than
publishing a known hole and shipping the fix as 0.7.1. The 2026-09-10 measurement at `7153df4` is
superseded: RM201–RM231 landed after it, and one of them (RM200) added a top-level manifest block the
release record had not declared — which this table's sweep row is what found.

| gate | result |
| --- | --- |
| `uv run pytest` | **4634 passed, 29 skipped, 0 failed** at `83b1674` (4627 at `b3a3765`; 4398 at `7153df4`; 4311 at `a6f31f8`; 4273 at `0d73268`; 3760 at the 2026-09-01 sweep; 3653 at 2026-08-31; 2916 at 2026-08-24). In-tree run; the skips are the network-gated tests. **An earlier pass of this same commit reported one failure and it was the machine, not the code**: `test_a_regex_locator_matches_the_fulltext` returned `None` where it wanted `True`, and `regex_matches` returns `None` on **timeout**, enforced in a subprocess (`@regex-timeout-process`). It ran while a 12-way genome-wide build saturated all sixteen cores. Worth knowing before a loaded CI runner meets it, because the failure reads as a logic error rather than as a timeout |
| `uv run ruff check` and `ruff format --check` | both clean at `83b1674` — the format gate is new since `019fe35` (2026-09-11) and CI runs it beside `ruff check`. A gate row is a measurement, not a property: it had gone red once before this table was re-measured on 2026-09-01 |
| Reference corpus under the 0.7 compiler | **16 / 16 compile** at `83b1674`; `content_signature` unmoved on all 15 comparable modules against 0.6.6 (the sweep row). The 2026-09-09 claim that every digest was byte-identical to `0d73268` is not re-asserted here — that tree is gone and a claim nobody can re-measure is not a gate row |
| 0.6.6 → 0.7.0 release sweep | 15 measured, **gate exit 0** at `83b1674` — and **exit 1 one commit earlier**, at `53819f0`: `expression_effects`, the top-level block RM200 added, appears as `null` on every module under 0.7.0 and on none under 0.6.6, and the record did not list it. Declared as an addition in `83b1674`; the gate is why the tag moved. Earlier: exit 0 at `a6f31f8`, and again at `0d73268` before the fixes: content_signature 0/15, manifest_fields 15/15, parquet_bytes 14/15, parquet_schema 14/15, warnings 3/15, `cyp2c9_warfarin_grch37` unmeasured (its `requires_callable` column does not exist under 0.6.6, so the BEFORE side refuses it). The record covers every field that moved. Re-run the gate whenever a `DeclaredChange` is added, not only at the cut |
| 0.6.6 client parses 0.7 manifests | **15 / 16** at `83b1674`, same one field (`mt_common_deletion`, four validation errors, all `verification.checks[].producer`), re-measured by parsing this cut's AFTER manifests with `just-dna-format==0.6.6` in an isolated venv (and see below — a *consumer's* module that runs `alphagenome check` is a sixteenth case this row does not cover). Previously re-measured at `a6f31f8` by parsing the sweep's AFTER manifests with `just-dna-format==0.6.6`. **The previous row's stated basis was wrong**: it said nothing had touched the manifest surface since 2026-08-31, and RM160 then added a `verification.checks` member. The result held anyway, on the same one field: `mt_common_deletion`, `verification.checks[].producer`, now across its four check records rather than one. The basis of this row is a measurement, not a claim about the diff |
| Open consumer inbox | **empty** at `83b1674` (`triage-state.py`: nothing pending, and no `🔷 reserved` row in RM_TOC). S90–S98 were answered 2026-09-11/12 as RM201, RM203–RM206, RM224, RM229, RM231 and one idea-book entry; S87–S89 on 2026-09-03 as RM180/RM183/RM184 |
| Open roadmap items in format scope | **none**. RM164 is parked to 0.8 (enricher scope), RM7 is marked not format scope, everything else in ROADMAP is queued for 1.0. The AlphaGenome round closed in two parts — RM191–RM199 on 2026-09-10, then **RM194 + RM200 on 2026-09-11**, both enricher scope. RM201 and RM203–RM206 also shipped 2026-09-11; RM207–RM231 through 2026-09-12, all inside the same uncut number. RM226/RM227 are queued for 1.0 |
| AlphaGenome lane, built genome-wide | **8,812,917,339 rows → 29.8 GB** over 24 parquets at `54b1f6a`, and every published number cross-checked against an independent measurement: 41,474 knots **knot-for-knot** against a table built by a different session from a different pass, 672,931 zeros, 49.30% negative, one straddling knot at threshold 3 |

**The blocker this section carried is gone.** RM143 shipped and S78 was answered, and the 2026-08-31
batch took the seven roadmap items that stood above with them. Everything here is committed, green and
measured; what remains before a cut is release management rather than work.

**A readiness table is worth exactly as much as the last time somebody ran it**, which is why it
carries the commit it was measured at and why every row above was re-run rather than read. The
2026-09-01 pass had found a red lint gate and a release gate exiting 1; the 2026-09-09 pass found the
0.6.6-parse row resting on a basis RM160 had falsified (the result held), and `dist/` holding bytes
from 145 commits ago under the current version number. What the 2026-09-09 audit changed in the code
is in CHANGELOG § 2026-09-09: seven fixes, none of which moved a reference example's digest or
signature (the corpus row above is the measurement). Two notes on the cut itself:

1. `v0.7.0` is at `83b1674` and `uv.lock` records `0.7.0` for all three members. **`dist/` was
   rebuilt on 2026-09-12 from a detached worktree at `83b1674`** and holds the six 0.7.0 artifacts and
   nothing else; the six it held before were built at `8b981f6` under the first tag and lack RM231 —
   the same version number over different bytes again, and the reason this table carries hashes.
   Those six were moved out of the tree, not deleted. The compiler wheel's hash is unchanged from
   `8b981f6` because no compiler source moved between the two tags; format and enricher moved.
   Verified after building: the three packages install from the wheels into an isolated venv, report
   `0.7.0`, `atomic_writer` takes `before_commit`, the 0.7.0 record declares `expression_effects`, and —
   the RM196 check — the enricher wheel and sdist both carry `_atlas_protos/*.proto` and the generated
   `generated/_alphagenome_atlas_protos/` package, so with `grpcio` + `protobuf` added
   `just_dna_enricher.atlas_client` imports and `client_absence()` answers `None`.
   The sha256 of each artifact, so a later `dist/` can be told from this one:

   | artifact | sha256 |
   | --- | --- |
   | `just_dna_format-0.7.0-py3-none-any.whl` | `c7e417c321d4bae3e84e1deafc2d3363751b1c32f4fa1d6ecfd4bc6b16ba6df1` |
   | `just_dna_format-0.7.0.tar.gz` | `9a07bcfdc7d2d23405c88cf6a2a42a778275302036152d004cab8324e98043ed` |
   | `just_dna_compiler-0.7.0-py3-none-any.whl` | `0d76c16bea236e62ee002eb4fed80c59f63a29c7fbb2486c23ffca636b451151` |
   | `just_dna_compiler-0.7.0.tar.gz` | `efc8a080d4930006b83dd61de1468ecf090dc6aaa0c2fad619140590f70cebf9` |
   | `just_dna_enricher-0.7.0-py3-none-any.whl` | `ec72badcc2331fa3cb4129c79b79674663e3edae4c3931f97bbc8ad440d72bc0` |
   | `just_dna_enricher-0.7.0.tar.gz` | `b05c8d14dc8c1a9edd3fd408b7ed8fbf669c77f38db81bd5af1fe87de6dc639a` |

   A build is taken from a detached worktree rather than the checkout because `uv build` reads the
   working tree, so an uncommitted file inside a package directory would ship in the wheel. The
   intra-workspace floors read `0.7.0` and a test walks them.
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
