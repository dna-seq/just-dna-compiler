# `just-dna-compiler` — a reference re-derived from code and tests

**What this is.** A blind re-derivation of the `just-dna-compiler` reference, written from
`compiler/src/**`, `compiler/tests/**`, `compiler/pyproject.toml`, the workspace root
`pyproject.toml`, and `schema/src/**` only. The maintained `docs/` tree was deleted from the
worktree before this document was started and was never read. It is meant to be compared as a peer
against the maintained reference, so that each disagreement is a question — *which of these two is
wrong?* — rather than a correction.

**Version under study.** `just-dna-compiler` 0.7.0 (`compiler/pyproject.toml:3`), depending on
`just-dna-format>=0.7.0`, `polars>=1.42.0`, `pyyaml>=6.0.2`, `typer>=0.12.0`
(`compiler/pyproject.toml:17-22`). Python `>=3.13` (`compiler/pyproject.toml:6`). Console script
`just-dna-compiler = just_dna_compiler.cli:app` (`compiler/pyproject.toml:25-26`).

**Evidence grades.** Every claim below carries one of three:

- **[T]** asserted by a test — cited `test_x.py:N`, usually with the pinned string quoted.
- **[C]** implemented at code — cited `file.py:N`.
- **[D]** stated by a docstring or comment only, with no test and no executable consequence I
  could find. A **[D]** claim is quoted, never paraphrased into fact.

Anything that is none of those is in §12, *Undetermined from code*.

---

## Sections

1. Public API
2. The validation-check table
3. The compile pipeline
4. Resolution
5. Reverse, round-trip and idempotency
6. The output artifact
7. Hashing
8. Deterministic ordering
9. The warning-text catalogue
10. The CLI
11. Everything else the package owns
12. Undetermined from code
13. Defect candidates
14. CLAUDE.md contamination statement

---

## 1. Public API

The module docstring at `compiler/src/just_dna_compiler/compiler.py:1-13` names three entry points.
That list is short of what the package actually exports without a leading underscore; the full set
follows, grouped by what it is for.

### 1.1 The three named entry points

#### `validate_spec(spec_dir, authority_keys=None, *, strict=False, resolve_with_ensembl=True) -> ValidationResult`

`compiler.py:3764-3805`. A read-only pre-flight over a spec directory. Delegates entirely to
`_validate_spec`, returning only the first element of its pair (`compiler.py:3802-3804`).

- `authority_keys` — inject-only. Consumer/registry-owned keys stripped from the authored `module:`
  block before the model sees it, so a legacy spec carrying `namespace:`/`owner:`/`canonical_id:`
  still validates. The format applies **none** by default; stripped keys are surfaced on
  `.info` (`compiler.py:3773-3779`, effected at `compiler.py:3858-3864`). Everything else still trips
  `extra="forbid"`.
- `strict` — severity only. **[D]** the docstring's claim is "It changes severity only; it never adds
  or removes a finding" (`compiler.py:3784-3785`). That is *not* quite what the code does: under
  `strict` `_validate_spec` **adds** `build_disagreement_error` (`compiler.py:4131-4134`) and the
  strict-resolution refusal (`compiler.py:4337-4343`), neither of which has a `best_effort`
  counterpart in this function. See §13.
- `resolve_with_ensembl` — the master resolution switch, mirrored so the pre-flight is not *more
  optimistic* than the compile it precedes (`compiler.py:3787-3792`).

#### `compile_module(...) -> CompilationResult`

`compiler.py:4688-4746` (signature), body to `compiler.py:5560`. Twelve parameters:

| Parameter | Default | What it does |
| --- | --- | --- |
| `spec_dir` | — | the authored spec directory |
| `output_dir` | — | where parquets + `manifest.json` land |
| `compression` | `"zstd"` | polars parquet codec, passed to every `write_parquet` |
| `resolve_with_ensembl` | `True` | master switch for resolution **of every kind**, despite the name (`compiler.py:4707-4712`) |
| `ensembl_cache` | `None` | **deprecated, removed at 1.0**; routes to `just_dna_enricher.resolver.resolve_variants` through a guarded optional import and emits a `DeprecationWarning` (`compiler.py:5017-5044`) |
| `compiled_by` | `None` | manifest provenance tag; the marketplace passes `"marketplace-server"` |
| `ensembl_reference` | `None` | pinned reference id recorded in the manifest |
| `log_files` | `None` | explicit logs; else auto-discovers a top-level `*.log` plus `spec_dir/logs/` (`_collect_logs`, `compiler.py:661`) |
| `provenance_file` | `None` | else auto-discovers `spec_dir/provenance.json` (`compiler.py:699`) |
| `logo_file` | `None` | else auto-discovers `spec_dir/logo.{png,jpg,jpeg}` (`compiler.py:725`) |
| `readme_file` | `None` | else the first of `manifest.README_CANDIDATES` (`compiler.py:756`) |
| `authority_keys` | `None` | as `validate_spec` |
| `strict` | `False` | all-or-nothing compile; see §2 mode column |
| `ba1_threshold` | `BA1_ALLELE_FREQUENCY_THRESHOLD` = `0.05` | ACMG BA1 cutoff for `_check_ba1_lint`; warning-only in both modes, so it tunes noise and never success (`compiler.py:4740-4745`, constant at `compiler.py:236`) |

`compile_module` **calls `_validate_spec` first** (`compiler.py:4752-4754`) and returns
`success=False` with the pre-flight's errors if it is not valid (`compiler.py:4755-4759`).
Crucially it passes `resolve_with_ensembl` but **deliberately not `strict`** — the pre-flight always
runs in `best_effort`, "which is why every mode-ladder check re-runs below"
(`compiler.py:4748-4751`). This is the structural fact behind most of §2.

#### `reverse_module(parquet_dir, output_dir, module_name=None, title=None, description=None, report_title=None, icon="database", color="#6435c9", version=None, write_resolution=True, genome_build=None) -> Path`

`compiler.py:7638-7650`. Rebuilds an authored spec from a compiled artifact. Returns `output_dir`.
Details in §5.

### 1.2 Also public, also part of the contract

| Symbol | Where | Contract |
| --- | --- | --- |
| `close_module(spec_dir, *, closed_by=None, private_key_pem=None, now=None, difficulty=None) -> ClosureResult` | `compiler.py:5563-5569` | writes the `closure` block into `verification.json`. Refuses on an invalid spec, never on a warning (`compiler.py:5596-5610`). §11.3 |
| `content_signature(spec_dir) -> str` | `compiler.py:4668` | the reference-independent identity of the authored data. §7 |
| `load_spec(path, *, authority_keys=None) -> ModuleSpecConfig` | `compiler.py:801` | loads `module_spec.yaml`, raising `SpecError` |
| `SpecError(ValueError)` | `compiler.py:792` | raised by `load_spec` |
| `load_csv_rows(...)` | `compiler.py:880` | the public wrapper around `_load_csv_rows` |
| `load_spec_variants(spec_dir) -> (rows, errors, warnings)` | `compiler.py:951` | |
| `load_overlay(spec_dir) -> (rows, errors, warnings)` | `compiler.py:3708` | reads `overrides.csv`. §11.1 |
| `load_citing_rows(spec_dir)` / `load_binning_rows(spec_dir)` | `compiler.py:2022` / `2037` | |
| `spec_tables(spec_dir) -> (rows_by_csv, module_name)` | `compiler.py:4604` | |
| `variant_stats(variants)` / `module_stats(variants, kind_rows=None)` | `compiler.py:4512` / `4535` | the `stats` contract; see `ValidationResult.stats` (`models.py:112-129`) |
| `table_citations` / `binning_citations` | `compiler.py:2060` / `2076` | |
| `split_cited_literature` / `cited_pmids` | `compiler.py:6849` / `6891` | |
| `literature_target_survives` / `resolution_target_survives` | `compiler.py:6912` / `6929` | overlay reachability predicates |
| `positional_placement(rows_by_csv) -> (rows, placed)` | `compiler.py:1540` | the counts behind `manifest` positional fields (S31) |
| `build_disagreement_error(block) -> str \| None` | `compiler.py:6241` | the one recorded judgement `strict` gates on |
| `authored_input_entries(spec_dir) -> list[FileEntry]` | `compiler.py:475` | the verification binding's file set; public **because two tiers must agree on it byte for byte** (`compiler.py:477-481`) |

### 1.3 Public constants (registries)

Measured by importing the module, not read off the source:

| Constant | Count | Members |
| --- | --- | --- |
| `ARTIFACT_PARQUETS` | **23** | §6 |
| `LEAD_PARQUETS` | **10** | `weights.parquet` + the 9 `_TABLE_KINDS` parquets (`compiler.py:414-417`) |
| `OVERRIDES_CSV` / `OVERRIDES_PARQUET` | — | `"overrides.csv"` / `"overrides.parquet"` (`compiler.py:351-352`) |
| `BA1_ALLELE_FREQUENCY_THRESHOLD` | — | `0.05` (`compiler.py:236`) |
| `UNJOINABLE_PHRASE` | — | `"have no chrom+start"` (`compiler.py:1413`) |
| `QUAL_INVERSION_PHRASE` | — | `"QUAL means the opposite thing on the record this row is read from"` (`compiler.py:1718`) |
| `MISSING_ALLELE_PHRASE` | — | `"is VCF's MISSING marker, not an allele"` (`compiler.py:1785`) |

Private-but-load-bearing registries, measured the same way: `_TABLE_KINDS` = **9**,
`_FACT_TABLES` = **10**, `_INPUT_FILES` = **13**, `_DERIVED_FILES` = **12**,
`_TABLE_DUPE_KEYS` = **9** models, `_POSITIONAL_TABLE_KINDS` = **3**
(`heteroplasmy.csv`, `haplotypes.csv`, `pharm_variants.csv`), `_GENE_BEARING_TABLE_KINDS` = **8**.

### 1.4 The result models (`models.py`)

All three results inherit `_Findings` (`models.py:11-101`), which derives two halves from `warnings`
in a `mode="before"` validator: `carried` (the subset no authored edit can clear) and
`warnings_summary` (counted by code). **[C]** `mode="before"` is load-bearing because pydantic
coerces a `CodedWarning` `str` subclass to a plain `str` on its way into `list[str]`, so a later
validator would see messages that no longer know their own code (`models.py:22-26`).

- Supplying **both** derived halves is accepted (rebuilt-from-a-dump); supplying **one** raises
  (`models.py:65-72`).
- `carried` must be a subset of `warnings`, and a non-empty `warnings_summary` must sum to
  `len(warnings)` (`models.py:83-100`).
- `ValidationResult`: `valid`, `errors`, `info`, `stats` (`models.py:104-130`).
- `ClosureResult`: `closed`, `path`, `module_hash`, `signed`, `dropped_checks`, `errors`
  (`models.py:133-159`).
- `CompilationResult`: `success`, `output_dir`, `errors`, `stats`, `manifest` (`models.py:162-168`).

---

## 2. The validation-check table

### 2.1 How to read it

Three facts about the architecture make this table's columns mean what they mean, and all three are
measured from the call graph rather than read off a summary:

1. **`compile_module` runs `_validate_spec` as its first act** (`compiler.py:4752-4754`) and returns
   `success=False` on any pre-flight error (`compiler.py:4755-4759`). So *every* validate-side check
   also constrains the compile, and the "does compile run it" column below distinguishes
   **`inherited`** (only through the pre-flight) from **`re-run`** (called again from
   `compile_module`'s own body). I computed the two sets with an AST walk over each function's direct
   `ast.Name` calls, not by reading comments.
2. **The pre-flight always runs in `best_effort`**, even under `compile --strict`
   (`compiler.py:4748-4751`: "`strict` is deliberately NOT passed"). This is why every *mode-ladder*
   check is re-run: the inner pass cannot know the mode.
3. **Re-run checks de-duplicate on the message text** — the idiom is literally
   `all_warnings.extend(w for w in X if w not in all_warnings)`, at 30 sites (measured: `grep -c 'if w not in all_warnings' compiler.py`). Message equality is
   the dedup key, so a re-run whose message embeds a count that *resolution changed* cannot collapse
   and would publish two numbers. `compiler.py:5223-5239` names the three checks deliberately not
   re-run for exactly that reason.

**Only four checks take a `strict` parameter at all** (measured by walking every check signature):
`_check_allele_membership`, `_check_study_effect_alleles`, `_check_symbolic_alleles`,
`_check_p_value_num`. Everything else is mode-independent; the remaining strict behaviour lives in
three gates written inline in the orchestrators (rows marked *strict gate* below).

### 2.2 Table

Legend — **V**: run by `_validate_spec`. **C**: `re-run` = called again in `compile_module`'s body;
`inherited` = reaches a compile only through the pre-flight; `only` = compile-side only.

| Check | Refuses / warns about | V | C | Severity | Mode | Message (verbatim, `{}` as written) |
| --- | --- | --- | --- | --- | --- | --- |
| `_load_yaml` `compiler.py:834` | a `module_spec.yaml` pydantic failure | yes `:3858` | inherited | **error** | both | `module_spec.yaml [{loc}]: {err['msg']}` `:876` |
| `load_csv_rows` `:880` | a ragged CSV row | yes | inherited | **error** | both | `{file_label} line {line_num}: more values than header columns (surplus: {surplus}) — check for a shifted or extra column` `:923` |
| `load_csv_rows` `:880` | any row-model failure | yes | inherited | **error** | both | `{file_label} line {line_num} [{loc}]: {err['msg']}` `:941` |
| `_check_misspelled_tables` `:3611` | an authored table sitting in `derived/` | yes `:3857` | inherited | warning `table_file_misplaced` | both | `{shown} is an authored table sitting in {DERIVED_SUBDIR}/, which holds only the machine-written sidecars — every row in it is being silently ignored. Move it to the spec root. Only resolution.csv and the fact tables have a second legal home.` `:3686` |
| `_check_misspelled_tables` `:3611` | a filename one edit from a real table | yes | inherited | warning `table_file_near_miss` | both | `{shown} is not a table this compiler reads, and it is one small edit from {close[0]} — if that is a typo, every row in it is being silently ignored. Unknown files are otherwise tolerated (curation notes or a publisher's receipt are fine): nothing outside the known table set reaches artifact.digest.` `:3697` |
| `ModuleInfo` version coercion | a non-SemVer `module.version` | yes `:3870` | inherited | warning `module_version_coerced` | both | `module.version {config.module.version_coerced_from!r} was read as SemVer {config.module.version!r}. It is advisory either way — the registry stamps the canonical version on publish — but the module now compiles under the coerced value.` `:3872` |
| `_restamp_for_build` `:1064` | a non-GRCh38 module's coordinate-keyed identities | yes `:3899` | re-run `:4776` | warning `non_grch38_variant_keys` | both | `genome_build is {genome_build!r}: GA4GH VRS allele identity is GRCh38-only (RM15), so {restamped} variant(s) are keyed by coordinate instead. A coordinate key is **build-relative** — it will not join against GRCh38-keyed data, and the same key means a different locus on another build. Publish GRCh38 coordinates if the module is meant to join against gnomAD, ClinVar or ClinGen.` `:1097` |
| *(inline)* `:3917` | a table-kind CSV present with no rows | yes | inherited | **error** | both | `{csv_name} is present but has no rows.` |
| `_validate_table_kind` `:3521` | >1 unresolved sentinel per bin group | yes `:3921`,`:4022` | inherited | **error** | both | `{csv_name}: {count} unresolved sentinel rows for key {format_group_key(group)} — a consumer selects one when a measurement is absent, so at most one is allowed` `:3564` |
| `_validate_table_kind` `:3521` | a duplicate row under the model's `_KEY_FIELDS` | yes | inherited | **error** | both | `{csv_name}: duplicate row for key {key}` `:3576` |
| `_validate_table_kind` `:3521` | bin overlap / gap / tiling (delegated to `binning.validate_bins`) | yes | inherited | errors + warnings (`bin_coverage_gap`, `bin_tiling_inferred`, `bin_tiling_contradicted`) | both | schema-owned; §9.3 |
| `_cross_validate_haplotype_definitions` `:3240` | a star allele used but never defined (`*1` exempt, `compiler.py:3237`) | yes `:3928` | inherited | warning `star_allele_undefined` | both | `Star allele(s) used but not defined in haplotypes.csv: {undefined}. A consumer's caller cannot emit an allele nothing defines, so rows about it can never match.` `:3270` |
| `_cross_validate_phase_ambiguity` `:3306` | diplotype rows indistinguishable without phase | yes `:3935` | inherited | warning `diplotype_phase_ambiguous` | both | `{gene}: {len(groups)} group(s) of diplotype rows are indistinguishable without phase — same unphased genotype, different conclusions. A consumer with unphased calls must withhold rather than pick one; a phased consumer resolves it. {_examples(groups)}` `:3422` |
| `_cross_validate_phase_ambiguity` `:3306` | diplotype rows whose haplotypes are defined identically | yes | inherited | warning `diplotype_definitions_identical` | both | `{gene}: {len(groups)} group(s) of diplotype rows name haplotypes this module defines identically, so nothing in it can tell them apart — phase does not help. A consumer's caller may still emit each name and the rows disagree, so at most one can be right: either the defining variants are incomplete or the rows describe one allele under several names. {_examples(groups)}` `:3411` |
| `load_overlay` `:3708` + `overlay_coherence_errors` | a malformed / self-contradicting `overrides.csv` | yes `:3963` | re-run `:4829` | **error** | both | schema-owned (`just_dna_format.overrides`) |
| `apply_overrides` | overlay application findings | yes `:4009` | re-run `:4864`,`:5417` | errors + warnings (`overlay_rows_suppressed`, `overlay_answer_vindicated`) | both | schema-owned; §9.3 |
| `_overlay_targets_missing` `:3741` | an override naming a table the module does not carry | yes `:4092` | re-run `:5450` | warning `overlay_targets_missing_table` | both | `{OVERRIDES_CSV} corrects {', '.join(missing)}, which this module does not carry. An overlay lies on top of a derived table and never creates one, so those rows change nothing. Run the pass that writes the table, or drop the override rows.` `:3755` |
| `_classify_deferred_overlay_updates` `:7143` | an `update` row whose target no artifact of this module could carry | yes `:4237` | re-run `:5456` | warnings `overlay_update_unmatched` / `overlay_update_target_unreachable` | both | schema-owned split; §11.1 |
| `_check_gene_validity_currency` `:7176` | a superseded ClinGen curation kept beside the current one | yes `:4032` | re-run `:5281` | warning `gene_validity_superseded` | both | `gene_validity.csv carries a later curation for {len(superseded)} gene-disease claim(s), so an earlier row is superseded and kept: {_currency_group_names(superseded)}. Nothing is deleted and nothing is wrong — the newest classification_date is read as current, both rows stay so the drift is visible, and manifest.gene_validity.classifications publishes the current one. A curating body re-curating is not an error in your module.` `:7201` |
| `_check_gene_validity_currency` `:7176` | curations nothing orders | yes | re-run | warning `gene_validity_currency_undecidable` | both | `gene_validity.csv carries several curations for {len(undecidable)} gene-disease claim(s) and nothing orders them: {_currency_group_names(undecidable)}. Either two rows share a classification_date or one states none, so no row is called current and none superseded — every classification in those groups is published, which is the honest answer rather than a winner picked from an identifier. Withheld deliberately, not skipped.` `:7213` |
| `_verify_vrs_ids` `:2841` | a stored `vrs_id` that does not recompute | yes `:4043` | re-run `:4881` | **error** | both (explicitly not a ladder, `:2843-2845`) | `{where}: stored vrs_id {vrs_id!r} does not match the id recomputed from {row.chrom}:{row.start} {row.ref}>{alt} ({recomputed}) — a substitution's id is deterministic here, so this is corruption, not a difference of opinion.` `:2926` |
| `_verify_vrs_ids` `:2841` | a `vrs_id` on a row with nothing to check it against | yes | re-run | **error** | both | `{message}. An id recorded against nothing to check it with is a contradiction in the table, not a limit of this tier: resolve the row, or drop the vrs_id.` `:2917` |
| `_carried_vrs_warnings` `:2940` (from `_verify_vrs_ids`) | an id this tier cannot verify | yes | re-run | warning `vrs_id_unverifiable` (**carried**) | both | `{len(wheres)} allele(s): vrs_id could not be verified — {reason}; carried unverified ({named}{more}).` `:2959` |
| `_vrs_coverage_warnings` `:3083` | alleles carrying no `ga4gh:VA.` id | yes `:4049` | re-run `:4885` | warning `vrs_coverage_incomplete` | both | `VRS allele identity covers {identified}/{alleles} allele(s) in resolution.csv ({identified / alleles:.0%}) — {alleles - identified} carry no ga4gh:VA. id. Anything keying on the VA sees only the covered fraction.` `:3099`, then one continuation line per reason: `  {count} allele(s): {reason}` `:3110` |
| `_check_frequency_arithmetic` `:6675` | `allele_count > allele_number` | yes `:4059` | re-run `:5259` | **error** | both | `{where}: allele_count {ac} exceeds allele_number {an} — a count cannot be larger than its own denominator` `:6694` |
| `_check_frequency_arithmetic` `:6675` | homozygote count implying more alleles than counted | yes | re-run | **error** | both | `{where}: homozygote_count {hom} implies at least {2 * hom} alleles, but allele_count is {ac} — each homozygote contributes two` `:6699` |
| `_check_frequency_arithmetic` `:6675` | `faf95` above the point estimate | yes | re-run | warning `faf95_exceeds_frequency` | both | `{where}: faf95 {row.faf95} exceeds the group's own allele frequency {frequency} — a 95% CI *lower bound* should sit at or below the point estimate, so these two numbers may not describe the same denominator` `:6709` |
| `_concordance_warnings` `:5865` | contested ClinVar-vs-module significance subjects | yes `:4068` | re-run `:5322` | warning `clin_sig_concordance_contested` | both — "never fails a build in either mode" `:5898` | `clin_sig_concordance.csv records {len(rows)} contested subject(s): {split}. A contested subject is a question, not a defect — half the time the archive is the stale side, which is why this never fails a build in either mode. Answer one by adding a row to overrides.csv naming table 'clin_sig_concordance.csv', the subject's variant_key and its genotype, with the reason you stand by the module's call.` `:5898` |
| `_cross_check_clin_sig_concordance` `:7300` | a concordance/authority-call subject no variant carries | yes `:4069`,`:4071` | re-run `:5325`,`:5337` | warning `derived_row_orphan` | both | `{table} records {len(orphans)} subject(s) no variant in this module carries: {orphans}. The record is rebuilt whole on every run, so this means variants.csv was narrowed since the comparison last ran — re-run it rather than editing the table.` `:7327` |
| `_check_license_gate` `:5909` | a no-sale source with no `declared_use: non_commercial` | yes `:4089` | re-run `:5162` | **error** | both — explicitly (`:5912-5915`) | `licensing: {undeclared} contribute annotation-layer content under terms that forbid sale, and this module records no non-commercial declaration for them. Re-run the enricher with a declared use (\`--use non-commercial\`) to record one, or remove the affected content. Declaring it is an assertion about how the module will be used — the compiler records that assertion, it does not verify it.` `:5936` |
| `_read_verification_block` `:6169` | two copies of `verification.json` | yes `:4160` | re-run `:5497` | warning `verification_two_copies` | both | layout-owned text, re-coded at `:6203` |
| `_read_verification_block` `:6169` | an unreadable attestation | yes | re-run | warning `verification_unreadable` | both | `{shown} could not be read as a verification attestation ({exc}); this compile records no verification. Re-run the checks (just-dna-enricher) to rewrite it.` `:6214` |
| `_read_verification_block` `:6169` | an attestation bound to other bytes | yes | re-run | warning `verification_stale` | both | `{shown} is stale: {failure}. The manifest records no verification for this compile, which says nothing rather than claiming a pass. {remedy}` `:6232` |
| `_closure_warning` `:6297` | a module whose authoring was never closed | yes | re-run | warning `module_not_closed` | both — "never a `strict` matter" `:6307` | `This module {UNCLOSED_PHRASE}: nothing in it states that authoring is finished, …` `:6317` (full text §9.1) |
| `_findings_warning` `:6125` | recorded enricher findings | yes | re-run | warning `verification_findings_recorded` (**carried**) | both | `verification.json records {sum(r.findings for r in found)} finding(s) across {len(found)} check(s): {named}. …` `:6158` |
| **`build_disagreement_error`** `:6241` | `genome_build_agreement` findings in the attestation | yes `:4162` **strict only** | re-run `:5145` **strict only** | **error** | **strict gate** — no `best_effort` counterpart | `strict compile: verification.json records {total} row(s) of {subjects} whose coordinates the enricher diagnosed as another assembly's ({BUILD_AGREEMENT_CHECK}). …` `:6273` (full text §9.1) |
| `panel:` deprecation (inline) `:4118` | a `panel:` block in the yaml | yes | inherited | warning `panel_block_deprecated` | both | two variants, `:4124` and `:4136`; §9.1 |
| `_apply_positional_resolution` `:1331` | a positional row the resolution table contradicts | yes `:4185` | re-run `:5186` | warning `positional_identity_contradicted` | both | `{csv_name}: {len(report.contradicted)} row(s) authored an identity the resolution table disagrees with, and are left exactly as authored — {_examples(report.contradicted)}` `:1384` |
| `_apply_positional_resolution` `:1331` | a non-GRCh38 module's positional fill | yes | re-run | warning `resolution_skipped_cross_build` | both | `Positional-table fill skipped: the compiler is GRCh38-bound and this module's genome_build is {genome_build!r}, so the injected resolution table is not joined onto {', '.join(…)} (RM15). Those rows keep the coordinates their author typed.` `:1369` |
| `_check_positional_joinability` `:1438` | positional rows with no `chrom`+`start` | yes `:4190` | re-run `:5208` | warning `positional_rows_unjoinable` | both | `{csv_name}: {len(unplaced)} of {len(rows)} row(s) {UNJOINABLE_PHRASE}, so this table joins by rsID only — a VCF whose ID column is empty matches none of them. {detail}.{partial_note}` `:1530` |
| *(inline)* `:4193` | a module carrying no recognized table | yes | inherited | **error** | both | `module has no recognized table: add variants.csv or a 0.4 table (e.g. pharm_variants.csv, diplotypes.csv, pgs.csv).` `:4195` |
| *(inline)* `:4217` | `studies.csv` present but empty | yes | inherited | **error** | both | `studies.csv is present but has no study rows. Grounding evidence is mandatory.` |
| *(inline)* `:4225` | `studies.csv` missing while `variants.csv` exists | yes | inherited | **error** | both | `studies.csv is missing. Grounding evidence is mandatory; add study rows with PMIDs.` `:4227` |
| **`_check_p_value_num`** `:2804` | `p_value` string vs `p_value_num` disagreeing >1% | yes `:4223` | re-run `:4956` | **mode ladder** | warning in `best_effort`, **error** in `strict` (`:2837`) | `{row.variant_key} pmid {row.pmid}: p_value {row.p_value!r} reads as {parsed:g}, but p_value_num says {row.p_value_num:g} — two encodings of one number disagree, so one of them is a transcription slip (the string is the record; the number is what a consumer filters on).` `:2830` |
| `_check_binning_grounding` `:1589` | thresholds with no grounding evidence | yes `:4249` | re-run `:5216` | warning `bins_ungrounded` | both | `{csv_name}: {len(ungrounded)} of {len(rows)} bin(s) state a threshold and the module records no grounding evidence at all (no studies.csv rows, no bin pmid). {remedy}.` `:1671` |
| `_check_measure_shape` `:1680` | an integer tiling for a fractional measurement | yes `:4253` | re-run `:5219` | warnings `measure_field_fractional`, `measurement_spans_bins` | both | schema-owned (`binning.measurement_shape_warnings`) |
| `_check_binning_deprecations` `:1699` | `modifier_cn` | yes `:4257` | re-run `:5220` | warning `deprecated_bin_modifier` | both | schema-owned (`binning.deprecation_warnings`) |
| `_check_missing_allele_marker` `:1795` | `.` written in an `alts` cell | yes `:4261` | **inherited only** (`:5223-5239`) | warning `missing_allele_marker_in_alts` | both | `{csv_name}: {len(offenders)} row(s) write '.' in alts, which {MISSING_ALLELE_PHRASE} — it states that the record has no alternate allele (VCF §1.6.1.5), so it is not the same kind of thing as a symbolic allele like <DEL>. {detail}. Leave the cell empty instead.` `:1870` |
| **`_check_symbolic_alleles`** `:2737` | a symbolic allele the module cannot apply | yes `:4180`,`:4267` | re-run `:4804` | **mode ladder**: warn+drop in `best_effort`, **error** in `strict`; **error in both modes** on a non-droppable table | ladder | `{table}: {affected} row(s) carry {_SYMBOLIC_REASONS[reason]}. {fate} e.g. {shown}{rest}.` `:2729`, code `symbolic_allele_unusable` |
| `_emptied_table_errors` `:2773` | a drop that would empty a whole table | yes (via `_check_symbolic_alleles`) | re-run | **error** | both — explicitly | `{table}: every row would be dropped for carrying an unusable symbolic allele, leaving a table that states nothing — so the compile would quietly produce a module that annotates nothing at all. Refused in both modes. Give the alleles their lengths, or remove the table.` `:2790` |
| `_check_build_coordinates` `:1200` | a coordinate past the contig's end on the stated build | yes `:4284` | re-run `:5101` (post-resolution) | **error** | both | `{label}: {len(found)} row(s) place a variant past the end of {chrom} on {build} ({length} bp) — {explanation} ({_examples(found)})` `:1272`; compile prefixes `post-resolution: ` `:5104` |
| `unresolved_subjects` gate (inline) `:4325` | variants the injected table cannot place | yes | — (compile has its own, `:5124`) | warning `rsid_unresolved` / `resolution_not_injected`; **error under `strict`** | **strict gate** | warning `{name}: not found in resolution table, position remains unset` `:4330`; error `strict compile: {len(unplaceable)} variant(s) have unresolved genomic positions after resolution: {unplaceable}. A partial artifact would not be byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or compile without strict.` `:4347` |
| `_check_vcf_pointers` `:1880` | a pointer naming an INFO/FORMAT-ambiguous key | yes `:4357` | **inherited only** | warning `vcf_pointer_key_collision` | both | `{sum(collisions.values())} VCF pointer cell(s) name a key that INFO and FORMAT both define, so the pointer does not say which field it means: {where}. {reasons} Qualify the pointer — INFO/{keys[0]} or FORMAT/{keys[0]} — a bare key stays legal and keeps meaning unqualified, which is why this is a warning and not a refusal.` `:1964` |
| `_check_vcf_pointers` `:1880` | a multi-valued field with no element rule | yes | inherited only | warning `vcf_pointer_unselected_element` | both | `{sum(unselected.values())} VCF pointer cell(s) point at a field the spec defines as multi-valued and state no element rule, so the pointer names a list rather than a number: {where}. Set the companion column to one of {sorted(VALID_ELEMENT_RULES)} — on a Number=R field the reference is element zero, which is why each ranging rule comes in a pair (largest counts it, largest_alt does not).` `:1979` |
| `_cross_check_literature` `:6787` | a cited PMID PubMed has no record of | yes `:4360` | re-run `:5274` | warning `citation_not_in_pubmed` | both | `literature.csv records {len(missing)} citation(s) PubMed has no record of: {missing} — either the id is a typo or the article was retracted from the index; the annotation resting on it should be re-examined either way` `:6828` |
| `_cross_check_literature` `:6787` | a literature row nothing cites | yes | re-run | warning `literature_row_uncited` | both | `literature.csv describes {len(dropped)} citation(s) no study, bin or pharm row in this module cites: {sorted({r.pmid for r in dropped})} — left out of the artifact, and left in the CSV, which is the pin that keeps a re-run cheap` `:6837` |
| `_check_quoted_article_licenses` `:7011` (via the above) | a quote from a non-commercial article | yes | re-run | warning `quoted_article_license_restrictive` | both — "Not adjudicated here" | `{len(pmids)} study quote(s) come from article(s) licensed {license_name}, which forbids commercial reuse: {sorted(pmids)}. Not adjudicated here — quoting for comment or research is often fine and the format is not the tier that decides — but the passage is publisher text in this module's annotation layer, so a commercial distribution has to answer for it` `:7035` |
| `_check_quote_counter_is_current` `:6948` (via the above) | `quotes_authored` disagreeing with the quotes | yes | re-run | warning `quote_counter_stale` | both | `literature.csv's quotes_authored disagrees with studies.csv for {len(stale)} citation(s): {…} — the sidecar predates the quotes (it is merge-not-clobber, so a re-run keeps the old row); re-run the literature pass to bring the counters and quotes_found up to date` `:6998` |
| **`_check_study_effect_alleles`** `:2359` | a study `effect_allele` absent from the resolved locus | yes `:4373` (**outside `if variants:`**, `:4363-4371`) | re-run `:4938` | **mode ladder** | ladder | `{key} (PMID {study.pmid}): effect_allele {study.effect_allele!r} is not among the resolved alleles at this locus ({shown}) — effect_size is stated relative to it, so a wrong effect allele inverts the study's finding rather than breaking it; the resolving source's allele list may also be incomplete, so check which before editing` `:2400` |
| `_cross_validate_variants` `:982` | two positioned rows for one key disagreeing | yes `:4380` | re-run `:5078` (**errors only**) | **error** | both | `Inconsistent positions for {key}: {key_positions[key]} vs {pos}` `:1006`; compile prefixes `post-resolution: ` `:5081` |
| `_cross_validate_variants` `:982` | two `ref` values under one key | yes | re-run | **error** | both | `Inconsistent reference allele for {key}: {key_refs[key]!r} vs {row.ref!r} at {row.chrom}:{row.start} — the reference base at a position is a single fact, so at most one of these is correct` `:1012` |
| `_cross_validate_variants` `:982` | a duplicate `(variant_key, genotype)` | yes | re-run | **error** | both | `Duplicate (variant, genotype): ({row.variant_key}, {row.genotype})` `:1024` |
| `_cross_validate_variants` `:982` | `weight` sign vs `state`/`direction` | yes | re-run (warnings discarded there) | warning `weight_sign_disagrees_with_effect` | both | four sentences, `:1035`/`:1042`/`:1049`/`:1056`; §9.1 |
| `_check_quality_inversion` `:1739` | a `min_quality` floor stated against `QUAL` | yes `:4386` | **inherited only** | warning `quality_floor_inverted` | both | `variants.csv: {len(offenders)} row(s) set requires_callable=true and state their min_quality floor against QUAL. {QUAL_INVERSION_PHRASE}: …` `:1771`; §9.1 |
| **`_check_allele_membership`** `:2259` | a genotype allele absent from the locus | yes `:4397` | re-run `:4927` | **mode ladder** | ladder | `{variant.variant_key} genotype {variant.genotype}: allele(s) {', '.join(missing)} are not among the {provenance} alleles at this locus ({shown}) — {because}` `:2333`, code `genotype_allele_not_at_locus` |
| `_check_allele_membership` `:2259` | an `effect_allele` absent from the locus | yes | re-run | **mode ladder** | ladder | `{variant.variant_key} genotype {variant.genotype}: effect_allele {variant.effect_allele!r} is not among the {provenance} alleles at this locus ({shown}) — direction/weight/effect_size are all stated relative to it, so a wrong effect allele inverts the conclusion rather than breaking it; {because}` `:2345`, code `effect_allele_not_at_locus` |
| `_check_genotype_coverage` `:2431` | a site whose genotype set has a hole | yes `:4408` | **inherited only** — deliberately (`:4402-4407`) | warning `genotype_coverage_gap` | both | `{len(found)} genotype(s) at {sites_missing} site(s) have no row: {reason}. The module states two or more genotypes at each of those sites, so this is a gap in a set the author started rather than a rule that fires once — {_examples(…)}` `:2555` |
| `_check_contig_ploidy` `:1108` | a two-allele genotype on a haploid contig | yes `:4416` | re-run `:5092` (**first point `chrom` is final**) | warning `contig_ploidy_mismatch` | both | `{row.variant_key} genotype {row.genotype}: chrom={row.chrom} is not diploid here — use a single-allele genotype (e.g. 'G') for a homoplasmic/hemizygous call` `:1164` |
| `_check_contig_ploidy` `:1108` | `chrom=Y`, two alleles, no PAR table for the build | yes | re-run | warning `contig_ploidy_undecidable` | both | `{row.variant_key} genotype {row.genotype}: chrom=Y with two alleles on build {genome_build}, which has no pseudoautosomal table here — so whether this locus is diploid could not be decided. Outside PAR1/PAR2 Y is hemizygous and this should be a single allele (e.g. 'G'); inside them the genotype is right.` `:1154` |
| `_cross_validate_studies` `:3439` | a study naming a variant `variants.csv` lacks | yes `:4418` | inherited only | warning `study_variant_orphan` | both | `Studies reference variants not in variants.csv: {sorted(set(orphans))}` `:3477` |
| `_cross_validate_studies` `:3439` | a duplicate `(variant, pmid)` | yes | inherited only | warning `duplicate_study_citation` | both | `Duplicate (variant, pmid): ({row.variant_key}, {row.pmid})` `:3509` |
| `_check_composite_gene_cells` `:4475` | a `gene` cell carrying a list separator | yes `:4455` | inherited only | warning `composite_gene_cell` | both | `{len(seen)} gene cell(s) contain a list separator and are published as single gene names: {named}. …` `:4501`; §9.1 |
| `resolve_from_table` `resolution.py:70` | resolution outcomes (unresolved, expansion, hosting, withdrawn rsID) | — | **compile only** `:4994` | errors + warnings + `strict_errors` | mixed — a `withdrawn` rsID is an **error in both modes** and the pre-flight never sees it (**§13.1**) | §4, §9.2 |
| **strict resolution gate** (inline) `:5067` | `outcome.strict_errors` | — | compile only | **error** | **strict gate** | `strict resolution: {e}` `:5070` |
| **strict unresolved gate** (inline) `:5124` | any variant with no `chrom`/`start` after resolution | — | compile only | **error** | **strict gate** | `strict compile: {len(unresolved)} variant(s) have unresolved genomic positions after resolution: {unresolved}. A partial artifact would not be byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or compile without strict.` `:5130` |
| `--no-resolve` notice (inline) `:4975` | `resolve_with_ensembl=False` with a table present | — | compile only | warning `resolution_disabled` | both | §9.1 |
| `_cross_check_frequencies` `:6753` | frequency rows at coordinates no variant occupies | — | **compile only** `:5261` | warning `derived_row_orphan` | both | `frequencies.csv describes {len(orphans)} coordinate(s) no variant in this module sits at: {orphans}` `:6779` |
| `_check_ba1_lint` `:7047` | a `pathogenic` call above the BA1 frequency | — | compile only `:5262` | warning `clin_sig_contradicts_frequency` | both — "warning-only in both modes" `:4744` | `{variant.variant_key} genotype {variant.genotype}: clin_sig {variant.effective_clin_sig} but the {measure} of ALT {alt} in {population} is {value}, above the ACMG BA1 threshold of {threshold} — BA1 treats that as stand-alone evidence of benign impact. The threshold is disease-specific (a common recessive carrier allele sits above it legitimately), so this is a prompt to check, not a verdict.` `:7112` |
| `_check_gene_metrics_arithmetic` `:6719` | `oe_lof` outside its own interval | — | compile only `:5266` | warning `oe_lof_outside_interval` | both | `{where}: oe_lof {point} lies outside its own interval [{lower}, {upper}] — the point estimate and the bounds may have come from different releases or columns` `:6734` |
| `_check_gene_metrics_arithmetic` `:6719` | `obs_lof/exp_lof` disagreeing with `oe_lof` | — | compile only | warning `oe_lof_disagrees_with_counts` | both | `{where}: obs_lof/exp_lof is {derived} but oe_lof is {point} — these are the same quantity, so a disagreement means one of the three columns is mismapped` `:6744` |
| `_cross_check_gene_metrics` `:7125` | metrics for genes the module never mentions | — | compile only `:5267` | warning `derived_row_orphan` | both | `gene_metrics.csv names {len(orphans)} gene(s) this module never mentions: {orphans}` `:7136` |
| `_cross_check_gene_validity` `:7237` | validity rows for genes the module never mentions | — | compile only `:5280` | warning `derived_row_orphan` | both | `gene_validity.csv names {len(orphans)} gene(s) this module never mentions: {orphans}` `:7254` |
| `_cross_check_clinical_assertions` `:7261` | assertions at coordinates no variant occupies | — | compile only `:5285` | warning `derived_row_orphan` | both | `clinical_assertions.csv describes {len(orphans)} coordinate(s) no variant in this module sits at: {orphans}` `:7292` |
| `_cross_check_gwas_effects` `:7336` | GWAS rows for identities the module lacks | — | compile only `:5288` | warning `derived_row_orphan` | both | `gwas_effects.csv carries associations for {len(orphans)} identity(ies) no variant in this module carries: {orphans}` `:7359` |
| `_expression_effect_checks` `:5290` | **nothing, deliberately** — returns `([], [])` | — | compile only | — | — | the docstring (`:5291-5313`) argues the absence: an `ExpressionEffectRow` is locus-wide by construction, so the orphan check would fire on nearly every row |
| `_source_checks` `:5948` | a declared source no table uses | — | compile only `:5360` | warning `source_row_unused` | both — "Never escalates under `strict`" `:5950` | `sources.csv declares {len(orphans)} source(s) no table in this module uses: {orphans}` `:6005` |
| `_source_checks` `:5948` | a used source with no `sources.csv` row | — | compile only | warning `source_terms_unrecorded` | both | `sources.csv has no row for {len(undeclared)} source(s) the module's fact tables cite: {undeclared} — their terms are unrecorded.` `:6013` |
| `_check_declared_license_agrees` `:6022` | `module.license` vs the sources' terms | — | compile only `:5361` | warning `declared_license_disagrees` | both | `module declares license {declared_license!r} and {standing}. Not adjudicated here — a compatible pair is legitimate, an incompatible one is a real problem, and only a human can tell which. A declaration matching some but not all of them is the ordinary mixed-licence case, where the most restrictive term binds the whole artifact.` `:6063` |
| `_locate_sidecar` `:503` | a deprecated sidecar spelling | yes | re-run at each sidecar site | warning `sidecar_spelling_deprecated` | both | layout-owned (`layout.deprecation_notice`) |
| `_locate_sidecar` `:503` | **two copies of one sidecar** | yes | re-run | **error** (warning for `verification.json` only, `:6198-6206`) | both | layout-owned (`layout.SidecarCollision`) |
| `_collect_provenance` `:699` | a malformed `provenance.json` | — | compile only `:5484` | **error** | both | `provenance.json is invalid: {exc}` `:5488` |
| `_collect_logo` / `_collect_readme` `:725`/`:756` | a malformed logo/readme | — | compile only | **error** | both | `str(exc)` from the collector |

**Measured counts.** 63 distinct warning codes are emitted from within this package (76
`CodedWarning(...)` construction sites), out of 73 in
`just_dna_format.vocab.VALID_WARNING_CODES`. The 10 the compiler does not construct itself are
raised inside `just-dna-format` and reach the channel through it: `bin_coverage_gap`,
`bin_tiling_contradicted`, `bin_tiling_inferred`, `deprecated_bin_modifier`,
`measure_field_fractional`, `measurement_spans_bins`, `overlay_answer_vindicated`,
`overlay_rows_suppressed`, `overlay_update_target_unreachable`, `overlay_update_unmatched`. I
computed this by AST-walking every `CodedWarning` call in `compiler/src/**` and differencing against
the imported vocabulary.

---

## 3. The compile pipeline, in execution order

Derived by reading `compile_module` top to bottom (`compiler.py:4746-5560`). Line numbers are the
stage's first statement. **Stages 1-17 run before `output_dir.mkdir()`**, which is stated as a rule
in three separate comments: a refusal must leave nothing written (`:5150-5153`, `:4783-4786`,
`:2781-2785`).

| # | Stage | Line | Can refuse? |
| --- | --- | --- | --- |
| 1 | `_validate_spec(spec_dir, authority_keys, resolve_with_ensembl=…)` — **without `strict`** | `:4752` | yes: returns the pre-flight's errors |
| 2 | `_load_yaml` again (this pass re-loads its own rows) | `:4761` | `assert config is not None` |
| 3 | `variants.csv` load + `_restamp_for_build` | `:4770` | yes (load errors) |
| 4 | `studies.csv` load | `:4777` | yes |
| 5 | every present `_TABLE_KINDS` CSV load — **here, not at materialization time**, so the symbolic check can reach them before `mkdir` (`:4782-4786`) | `:4786` | yes |
| 6 | `all_warnings = list(validation_findings)` — seeded from the **classified** list, not `validation.warnings`, which pydantic has flattened (`:4792-4795`) | `:4796` | — |
| 7 | `_check_symbolic_alleles(..., strict=strict)` → drop or refuse; `module_stats` re-derived when anything dropped (`:4815-4823`) | `:4804` | yes under `strict`, and always on a table emptied |
| 8 | `load_overlay(spec_dir)` | `:4829` | yes |
| 9 | `resolution.csv`: locate → load → **overlay applied first** (`:4860-4863`) → group into `resolution_table` → `_verify_vrs_ids` → `_vrs_coverage_warnings` → `_vrs_coverage` → stamp `resolution_sources`/`resolution_sig` | `:4848` | yes |
| 10 | `_check_allele_membership(variants, resolution_table, strict=)` — on the **authored** rows, before expansion (`:4922-4925`) | `:4927` | ladder |
| 11 | `_check_study_effect_alleles(..., strict=)` | `:4938` | ladder |
| 12 | `_check_p_value_num(studies, strict=)` | `:4956` | ladder |
| 13 | the `--no-resolve`-with-a-table notice | `:4975` | no |
| 14 | **resolution** (`if resolve_with_ensembl and variants`): `resolve_from_table` → or the deprecated `ensembl_cache` route → or the nothing-injected notice; then the strict gate on `outcome.strict_errors`; then `_cross_validate_variants` **errors only**, prefixed `post-resolution:` | `:4989` | yes |
| 15 | `_check_contig_ploidy` — **here, once**, because this is the first point `chrom` is final (`:5084-5088`) | `:5092` | no |
| 16 | `_check_build_coordinates` post-resolution, prefixed `post-resolution:` | `:5101` | yes |
| 17 | `fully_resolved` / `resolution_subjects` computed together, so the flag can never publish without its denominator (`:5111-5116`) | `:5117` | — |
| 18 | **strict**: refuse any variant still lacking `chrom`+`start` | `:5124` | strict |
| 19 | **strict**: `build_disagreement_error(_verification_block(spec_dir)[0])` | `:5144` | strict |
| 20 | **the licence gate** — last point at which nothing is written (`:5150-5153`) | `:5155` | yes, **both modes** |
| 21 | `output_dir.mkdir(parents=True, exist_ok=True)` | `:5166` | — |
| 22 | SNP core built and written: `weights.parquet`, `annotations.parquet`, `studies.parquet`, each only when its rows exist | `:5169` | — |
| 23 | `_apply_positional_resolution` — **after** the symbolic drop, **before** `_build_table` (`:5178-5185`) | `:5186` | no |
| 24 | every present `_TABLE_KINDS` CSV → `_build_table` → `write_parquet`; `table_rows[parquet] = height` | `:5193` | — |
| 25 | `_check_positional_joinability`, then `positional_placement` computed **beside the check** so the two cannot describe different row sets (`:5213-5215`) | `:5205` | no |
| 26 | `_check_binning_grounding`, `_check_measure_shape`, `_check_binning_deprecations` | `:5216` | no |
| 27 | the three checks **deliberately not re-run** — `_check_missing_allele_marker`, `_check_quality_inversion`, `_check_vcf_pointers` — with a measured justification (`:5222-5239`) | — | — |
| 28 | the `_FACT_TABLES` loop, in the tuple's order with **`sources.csv` last**: locate → load → overlay → `check(rows)` over **every** row → `split_cited_literature` for `LiteratureRow` only → store → `build(rows)` → `write_parquet` | `:5397` | yes |
| 29 | `_overlay_targets_missing`, then `_classify_deferred_overlay_updates` | `:5450` | no |
| 30 | `overrides.parquet` written **verbatim and in authored order** when the overlay is non-empty | `:5462` | — |
| 31 | `_collect_logs`, `_collect_provenance`, `_collect_logo`, `_collect_readme` | `:5480` | yes (malformed asset) |
| 32 | `_verification_block(spec_dir)` re-read (the pre-flight threw the block away, `:5496-5499`) | `:5500` | no |
| 33 | `_build_manifest(...)` with `content_sig=content_signature(spec_dir)` computed over the **raw authored bytes re-read from disk** (`:5504-5506`) | `:5507` | — |
| 34 | `write_manifest(manifest, output_dir / "manifest.json")` | `:5545` | — |
| 35 | return `CompilationResult(success=True, …, stats={module_name, weights_rows, annotations_rows, studies_rows, table_rows})` | `:5547` | — |

### 3.1 Three placement rules the pipeline encodes

- **A refusal must leave nothing written.** The licence gate (20), the symbolic check (7), the
  build-disagreement gate (19) and the table-kind loads (5) are all placed above `mkdir`
  specifically for this. `compiler.py:5150-5153`, `:4783-4786`.
- **Re-run a check after resolution exactly when resolution changes its input, and never when the
  message embeds a count** (`compiler.py:5236-5239`). This is stated as the rule that covers both the
  ploidy check moving *down* and the three VCF checks staying *up*. It was measured: an rsid-only
  `requires_callable` row over a two-locus `resolution.csv` emitted "1 row(s) …" beside "2 row(s) …",
  and the pointer check emitted 328 beside 337 on `pathogenic_clinvar` (`compiler.py:5231-5235`).
- **The overlay is applied before any check reads a row** — in both orchestrators
  (`compiler.py:3960-3963`, `:4855-4863`, `:5410-5422`). A check reports on what the module
  *asserts*, which since 0.7 is the derived table plus the author's corrections.

---

## 4. Resolution

### 4.1 What `resolution.csv` is, and the master switch

`resolution.csv` is an **injected** table of already-resolved facts
(`just_dna_format.resolution.ResolutionRow`), keyed by the frozen `variant_key`. The compiler
consumes it and "knows only *read the facts I was handed*" — no `duckdb`, no SQL, no Ensembl
convention (`resolution.py:1-13`). The deprecated alternative, `ensembl_cache`, routes to
`just_dna_enricher.resolver.resolve_variants` through a guarded optional import and is removed at 1.0
(`compiler.py:5017-5044`).

`resolve_with_ensembl` is **the master switch for resolution of every kind, despite the name**
(`compiler.py:4707-4712`). Turning it off with a complete table present compiles *successfully* with
`chrom=None` on every weight row, so that combination emits the `resolution_disabled` warning
(`compiler.py:4972-4987`).

**It is not a `strict`-mode thing.** `resolution_mode` in the manifest is `"strict"` or
`"best_effort"` (`compiler.py:4990`), but only when `resolve_with_ensembl and variants`; it stays
`None` otherwise.

### 4.2 The three severity channels

`ResolutionOutcome` (`resolution.py:36-68`) splits findings three ways, and the split is the design:

| Channel | Meaning | Members |
| --- | --- | --- |
| `warnings` | reported in both modes, never fatal | `rsid_unresolved`, `rsid_no_hosting_locus`, `locus_hosting_undecidable`, `locus_cannot_host_genotype`, `rsid_without_resolution_label`, `rsid_expanded_to_multiple_loci`, `rsid_ambiguous`, `rsid_coordinate_disagrees`, `resolution_skipped_cross_build` |
| `strict_errors` | the **round-trip contract** — conditions under which `compile → reverse → compile` cannot reproduce the injected table, plus `ambiguous`, which *is* reproducible but rests on a guessed label | a dropped non-hosting locus (`resolution.py:156`), an `ambiguous` status (`:290`), a coordinate disagreement (`_verify`, `:976`) |
| `errors` | fatal in **both** modes | **only** `rsid_status == "withdrawn"` (`resolution.py:274-286`) |

`expanded_keys` / `expanded_rows` are carried out for `manifest.compilation` — two numbers, never a
ratio, because one authored key can expand to any number of rows (`resolution.py:49-56`). They are
`None` on the non-GRCh38 early return and nowhere else: that path resolved nothing, so `0` would say
"looked, found no expansion" of a module nothing looked at (`resolution.py:58-62`).

### 4.3 `resolve_from_table` — the three operations

`resolution.py:70-305`. Per authored `VariantRow`, keyed on its frozen `variant_key`:

- **fill (1:1)** — exactly one usable locus fills the missing coordinate or rsid, **keeping the
  frozen key** (`:133`).
- **expand (1:N)** — N usable loci become N coordinate-keyed rows, ordered by
  `(locus_index, chrom, start, ref)` to match the DuckDB path's `ORDER BY id, chrom, start, ref`
  (`resolution.py:11-13`, sort at `_sorted_loci`, `:971`). Each expanded row is re-keyed with
  `derive_variant_key(None, chrom, start, ref, alts, build=genome_build)` (`:198-206`) and stamped
  with the RM87 pair `locus_index` / `locus_count` (`:216-218`).
  - `_hostable_loci` filters candidates by `hosting_verdict` first (`:187`). A locus that
    **positively cannot** host the genotype is dropped (warning + `strict_error`); a locus where the
    verdict is *undecidable* is **kept** and said out loud (`:139-153`). This is the tri-state in
    action: the `locus_index` counts within `usable` (post-drop), not within the injected table's own
    `locus_index` (`:209-215`).
- **verify** — a row carrying both an rsid and a coordinate is checked against the table; a
  disagreement warns in `best_effort` and refuses in `strict` (`_verify`, `resolution.py:976`).

`hosting_verdict(genotype, ref, alts) -> bool | None` (`resolution.py:508`) is three-valued, with
`undecided_reason` (`:641`) and `contradiction_reason` (`:692`) supplying the *which* arm.

### 4.4 Which tables resolution reaches

Two distinct functions, and they are not the same mechanism:

| | `variants.csv` | the positional 0.4 kinds |
| --- | --- | --- |
| function | `resolve_from_table` `resolution.py:70` | `resolve_positional_rows` `resolution.py:332`, driven by `_apply_positional_resolution` `compiler.py:1331` |
| tables | `variants.csv` only | `_POSITIONAL_TABLE_KINDS` = `heteroplasmy.csv`, `haplotypes.csv`, `pharm_variants.csv` (measured: 3) |
| expansion | yes, 1:N | **no, deliberately** — it would multiply a pharm annotation's key across loci the author never named (`resolution.py:352-357`) |
| mutation | `model_copy` (rows are copied) | **in place** (`resolution.py:363-366`) |
| conflict | warns, and `strict` refuses | reported, **never repaired, never fatal** (`resolution.py:358-362`) |
| report | `ResolutionOutcome` | `PositionalFill(filled, unplaced_ambiguous, unplaced_absent, contradicted)` `resolution.py:316-330` |

`PositionalFill` keeps `unplaced_ambiguous` and `unplaced_absent` apart for the standing tri-state
reason: "the table names this key at several loci and the compiler will not pick one" and "nothing
has resolved this key" are different situations with different next moves (`resolution.py:319-323`).

The fill is **not** short-circuited on `not fillable`: a fully populated row can still contradict the
table it is keyed into, and reporting that is the promise (`resolution.py:387-394`).

### 4.5 `authored_ident` — what makes resolution reversible

`authored_ident: list[str] | None` records **which of the five identity columns the author actually
filled**, from `IDENTITY_FIELDS = ("rsid", "chrom", "start", "ref", "alts")`
(`schema/src/just_dna_format/base.py:376-379`). It is stamped at load and never re-derived
(`VariantRow._freeze_identity`, `spec.py:845-872`; `stamp_identity`, `base.py:466-495`), which is
what lets resolution fill or expand without disturbing it.

Its job: `reverse_module` re-emits **the shape the author wrote**, not whatever resolution filled in.
`_write_table_csv` (`compiler.py:604-645`) blanks any identity column the row's `authored_ident` does
not name (`:626-634`). Without it, reverse materialized resolved coordinates into `variants.csv` and
`content_signature` moved across every round trip of an rsid-authored module (`spec.py:852-858`,
`compiler.py:611-614`).

Two notes the code makes explicitly:

- A parquet with **no** `authored_ident` column — anything compiled before 0.6 — blanks nothing and
  behaves as it did (`compiler.py:617-618`).
- The 0.4-family positional models declare `authored_ident` through `stamped_identity_field`, which
  is `exclude=True` and therefore **outside** `content_signature`. `VariantRow.variant_key` and
  `VariantRow.authored_ident` are **not** excluded and **are** inside `content_signature` today;
  `base.py:394-400` calls this "a grandfathered inconsistency, not a precedent". See §13.

### 4.6 The round-trip matrix

`compiler/tests/test_resolution_matrix.py` enumerates the grid: five identity columns the author may
or may not supply, crossed with what the table says. **Measured: 22 cases** — 16 declared stable, 8
declared strict-refusing, 4 flagged `table_says_more`, 6 exercising the positional half
(`pharm_variants.csv`). `uv run pytest compiler/tests/test_resolution_matrix.py -q` → **24 passed**.

The contract, asserted three ways:

1. **Per case** (`test_resolution_round_trip_contract:310`): `best_effort` always compiles; the three
   signatures (`artifact.digest`, `content_signature`, `resolution_signature`) either all hold or the
   case is declared unstable; `strict` succeeds iff `not case.strict_refuses`.
2. **Over the table** (`test_the_contract_itself_holds:340`): *instability always implies a strict
   refusal* — asserted over the whole list so a future entry cannot declare itself unstable and
   strict-clean.
3. **The strongest** (`test_artifact_digest_never_moves:350`): `artifact.digest` must reproduce for
   **every** case, including the ones where the other two legitimately cannot.

The `table_says_more` flag is a **third axis** beside authored-shape and mishap: the injected table
carries a fact the module never uses, so `resolution_signature` cannot survive the round trip
(reverse rebuilds the table from the artifact, and a fact the artifact never held has nowhere to come
from), while nothing about the module is wrong and `strict` accepts it. The test asserts the **exact**
mover set `== ["resolution_signature"]`, not "something may move" (`test_resolution_matrix.py:320-327`).

Selected declared outcomes, quoted from the case labels:

| Case | stable | strict refuses |
| --- | --- | --- |
| rsid-only, 1:1 fill | yes | no |
| rsid-only, one-to-many expansion (both loci can host the genotype) | yes | no |
| coord+alt authored, rsid resolved | yes | no |
| rsid-only indel, table carries the other published spelling | yes | no |
| rsid-only indel, spelling the tier cannot reconcile (kept, reported) | yes | no |
| expansion drops a locus whose indel is a different size | **no** | **yes** |
| ambiguous: several rsIDs for one allele, deterministic pick recorded | yes | **yes** (the deliberate exception) |
| expansion drops a locus that cannot host the genotype | **no** | **yes** |
| not_found: the table records the rsid as genuinely absent | **no** | **yes** |
| authored ref contradicts the table | **no** | **yes** |
| authored coordinate contradicts the table | **no** | **yes** |
| no resolution row at all: the rsid stays unresolved | yes | **yes** |
| every candidate locus contradicts the genotype: left unresolved | **no** | **yes** |
| the table carries a row about a variant the module does not have | yes (`table_says_more`) | no |
| table-only, rsid-authored pharm row, 1:1 fill | yes | no |
| table-only, one-to-many rsid: left unplaced, never picked or expanded | yes (`table_says_more`) | no |

### 4.7 `unresolved_subjects` — the shared predicate

`resolution.py:474` is the predicate `resolve_from_table` applies, **shared rather than restated**,
so the pre-flight and the compile cannot drift into disagreeing about which rows are unplaceable
(`compiler.py:4302-4306`). `_validate_spec` calls it at `:4325`; the compile derives the same answer
from `outcome.variants` at `:5117`.

---

## 5. Reverse, and the round-trip guarantees

### 5.1 What `reverse_module` writes, in order

`compiler.py:7638-7869`. Every step is conditional on the corresponding parquet existing — a module
carries only the kinds it uses (RM2).

1. **Resolve every sidecar destination first** (`:7696-7710`), before the first write.
   `sidecar_write_path` raises `layout.SidecarCollision` on an output directory that already holds
   two copies of one table, and resolving late would raise it *after* `module_spec.yaml` and the
   authored CSVs had been rewritten — "a refusal that leaves a half-rebuilt spec behind"
   (`:7698-7702`).
2. **Recover identity**: `module_name` from any present parquet's `module` column
   (`_module_name_from_parquets`, `:7516`), `genome_build` from the artifact's `manifest.json`
   (`_genome_build_from_artifact`, `:7562`) else `"GRCh38"`, `version` from
   `identity.version_coerced_from` else `identity.version` (`_authored_version_from_artifact`,
   `:7537`).
3. **Notice the attestation it cannot carry** (`:7723-7731`): `logger.warning(_verification_loss_notice(...))`.
   `reverse_module` returns a bare `Path` and has no findings channel, so this goes to stdlib
   `logging` (`compiler.py:205-210`).
4. **`module_spec.yaml`** with `defaults` recovered from the modal `curator`/`method` in
   `weights.parquet` (`_most_common`, `:8117`). `priority` is **deliberately not defaulted**
   (`:7733-7739`): it is Optional with no `Defaults.priority` fallback, so a null priority is
   *authored-absent*, and inferring one would turn `['high', None]` into `['high', 'high']` on
   recompile — a P7 idempotency break.
5. **`variants.csv`** (only when `weights.parquet` exists), joined to `annotations.parquet` on a key
   **read off the artifact rather than assumed** (`:7768-7778`): three generations of that table are
   in the wild — 0.6 keys on `(variant_key, genotype, conclusion, negatives)`, 0.5 on the
   variant-effect pair, the oldest on `variant_key` alone.
6. **`studies.csv`** (`_write_studies_csv`, `:8319`).
7. **Each `_TABLE_KINDS` parquet → its authored CSV** via `_write_table_csv`, collecting the
   positional frames.
8. **`resolution.csv` last**, because it is rebuilt from everything above — the SNP core **and** the
   positional tables since RM43 (`:7815-7828`).
9. **Each `_FACT_TABLES` parquet → its CSV**, through `sidecar_paths` (never a literal join), so the
   licence table lands under the **preferred** spelling rather than the deprecated `sources.csv` name
   `_FACT_TABLES` still uses for the parquet (`:7830-7853`).
10. **`overrides.csv`** at the spec root under its one legal name — it is authored like
    `variants.csv`, not a machine sidecar (`:7855-7867`).

### 5.2 What is not carried

| Thing | Why | Where |
| --- | --- | --- |
| `verification.json` / the attestation | bound to authored bytes by hash; reverse has nothing to rebuild it from, **and must not invent one**. It warns instead, because otherwise the round trip changes `manifest.compilation.warnings`, a published field | `:7723-7731` |
| `rsid_alternates` | the artifact never held it, so it has nowhere to come back from | `:4930-4934` (comment) |
| any identity column outside `authored_ident` | re-emitting a machine-filled coordinate as authored data would move `content_signature` | `_write_table_csv`, `:611-618` |
| `allele_frequency` on `frequencies.csv` | derived on write, absent from `FrequencyRow`'s fields, so `_write_table_csv` drops it **by construction rather than by a special case**; the next compile re-derives the identical column | `:7830-7834` |
| `neg_log10_p` on `studies.csv` | same pattern — derived on write, absent from `StudyRow`'s fields | `:7474-7478` |
| `module` column | injected, not authored | `_write_table_csv`, `:604-606` |

### 5.3 The round-trip guarantee

**The claim.** `compile → reverse → compile` reproduces `artifact.digest`, `content_signature` and
`resolution_signature`, *or* `strict` refuses. Enumerated and asserted in
`compiler/tests/test_resolution_matrix.py` — see §4.6 for the 22 cases and the three assertions.

**What `strict` refuses.** Six things, and they are not one list in the code — I collected them by
walking every `if strict` in `compile_module` and `_validate_spec`:

1. A symbolic/structural allele a droppable table carries (`_check_symbolic_alleles`,
   `compiler.py:2764-2766`) — `best_effort` drops the row and says so.
2. A `p_value` / `p_value_num` disagreement (`_check_p_value_num`, `:2837`).
3. An allele-membership failure, genotype or effect allele (`_check_allele_membership`, `:2354`).
4. A study effect-allele failure (`_check_study_effect_alleles`, `:2407`).
5. `outcome.strict_errors` — a dropped non-hosting locus, an `ambiguous` status, a coordinate
   disagreement (`compiler.py:5067`, prefixed `strict resolution: `).
6. Any variant still lacking `chrom`+`start` after resolution (`compiler.py:5124`), and
   `build_disagreement_error` on the attestation (`compiler.py:5144`).

**What `strict` deliberately does *not* refuse**, each with an explicit argument in the source:

- A licence-gate failure — refuses in **both** modes, because "`strict`'s single meaning is *produce
  a reproducible artifact*" and overloading it is the orthogonality P5 protects (`:5911-5915`).
- A `withdrawn` rsID — fatal in **both** modes (`resolution.py:274-281`).
- A table emptied by the symbolic drop — refuses in **both** modes (`:2775-2781`).
- The ClinVar `clin_sig` concordance finding — "never fails a build in either mode" (`:5898`).
- `_source_checks` — "Never escalates under `strict`" (`:5950`).
- `_check_ba1_lint` — warning-only in both modes, which is why `ba1_threshold` "tunes noise, never
  whether the compile succeeds" (`:4744-4745`).
- `_closure_warning` — "An unclosed module is perfectly reproducible — `strict` means *reproducible
  artifact*, an unrelated axis" (`:6306-6310`).
- `_check_quoted_article_licenses` / `_check_declared_license_agrees` — "refusing would make the
  format arbitrate a copyright question" (`:6812-6818`).

**Idempotency of the overlay.** `reverse_module` emits the **post-overlay** derived tables *and* the
overlay, so the overlay applies twice. The code states that this is the design, not an oversight
(`:7857-7866`): all three operations are idempotent set operations — an update to a value already
present, an insert of a row already keyed, a suppress of a row already absent are each a no-op — so
the second lap is a fixed point. "It is checked by test, never assumed — Principle 7 requires that of
every derivation."

**`artifact.digest` is the strongest of the three.** `test_artifact_digest_never_moves` asserts it
across every matrix case, including the ones where `content_signature` or `resolution_signature`
legitimately cannot hold.

---

## 6. The output artifact

### 6.1 The count

**`ARTIFACT_PARQUETS` holds 23 members** — measured by importing the constant, not counted by eye.
`= 3` SNP core + `9` authored table kinds (`_TABLE_KINDS`) + `10` derived-fact tables
(`_FACT_TABLES`) + `1` overlay.

Two counts in the source **disagree with the measurement** — see §13.

**Digest order is name-sorted, not tuple order.** `integrity.artifact_digest`
(`schema/src/just_dna_format/integrity.py:159-180`) builds
`[{"name","sha256","size"}, ...]` **sorted by name**, serializes with `sort_keys=True` and
`separators=(",", ":")`, and hashes that. So a member's position in `ARTIFACT_PARQUETS` is invisible
to the digest; the tuple's order governs the `manifest.artifact.files` **listing** a consumer
iterates. The source says this twice, because "the false version stood in five documents for a
release" (`compiler.py:361-368`).

### 6.2 Every parquet, in digest (name-sorted) order

Columns measured by calling each builder with an empty row list and reading `df.columns`.
"Stamped" = present in the parquet and **not** in `just_dna_format.base.authored_field_names(model)`.

| # | Parquet | Cols | Columns | Compiler-stamped |
| --- | --- | --- | --- | --- |
| 1 | `activity_phenotype.parquet` | 15 | module, measure_kind, measure_min, measure_max, measure_tiling, direction, clin_sig, phenotype, trait_efo_id, conclusion, unresolved, source_field, source_element, pmid, gene | `module` |
| 2 | `allele_function.parquet` | 9 | module, gene, allele, activity_value, function_status, suballele, copy_number, sv_type, hybrid_orientation | `module` |
| 3 | `annotations.parquet` | 9 | rsid, variant_key, genotype, conclusion, negatives, module, gene, phenotype, category | `module`, `variant_key`; **keyed on `(variant_key, genotype, conclusion, negatives)`**, first occurrence wins (`:7367-7396`) |
| 4 | `clin_sig_authority_calls.parquet` | 11 | module, variant_key, genotype, authority, status, clin_sig, clin_sig_raw, confidence, confidence_unit, dataset, checked_at | `module` |
| 5 | `clin_sig_concordance.parquet` | 8 | module, variant_key, genotype, authored_clin_sig, authority_concordance, authored_position, opposed, checked_at | `module` |
| 6 | `clinical_assertions.parquet` | 18 | module, variant_key, rsid, chrom, start, ref, alt, genome_build, clin_sig, clin_sig_raw, review_status, review_stars, condition, variation_id, dataset, source, status, fetched_at | `module` |
| 7 | `copynumbers.parquet` | 18 | module, measure_kind, measure_min, measure_max, measure_tiling, direction, clin_sig, phenotype, trait_efo_id, conclusion, unresolved, source_field, source_element, pmid, gene, modifier_gene, modifier_cn, modifier_copy_number | `module` |
| 8 | `diplotypes.parquet` | 14 | module, gene, haplotype_a, haplotype_b, trait_efo_id, direction, clin_sig, phenotype, conclusion, drug, response, evidence_level, recommendation_strength, clinical_context | `module` |
| 9 | `expression_effects.parquet` | 20 | module, variant_key, rsid, chrom, start, ref, alt, gene, gene_id, effect_size, effect_measure, effect_unit, effect_direction, tracks_agreeing, tracks_total, distance_to_gene, dataset, source, status, fetched_at | `module` |
| 10 | `frequencies.parquet` | 21 | module, variant_key, rsid, chrom, start, ref, alt, genome_build, population, allele_count, allele_number, homozygote_count, hemizygote_count, faf95, dataset, vrs_id, caid, source, status, fetched_at, **allele_frequency** | `module`, **`allele_frequency`** (derived on write from AC/AN; the CSV stores only the integers, `:6645-6650`) |
| 11 | `gene_metrics.parquet` | 22 | module, gene, gene_id, transcript, mane_select, pli, loeuf, oe_lof, oe_lof_lower, lof_z, obs_lof, exp_lof, oe_mis, mis_z, syn_z, constraint_flags, haploinsufficiency, triplosensitivity, dataset, source, status, fetched_at | `module` |
| 12 | `gene_validity.parquet` | 16 | module, gene, gene_id, disease_id, disease_label, moi, classification, classification_raw, classification_date, submitter, assertion_id, report_url, dataset, source, status, fetched_at | `module` |
| 13 | `gwas_effects.parquet` | 23 | module, association_id, variant_key, rsid, effect_allele, effect_size, effect_measure, effect_unit, effect_direction, standard_error, confidence_interval, risk_allele_frequency, p_value, p_value_num, trait, trait_efo_id, pmid, study_accession, ancestry, dataset, source, status, fetched_at | `module` |
| 14 | `haplotypes.parquet` | 12 | module, haplotype_name, rsid, chrom, start, ref, alts, allele, gene, requires_callable, variant_key, authored_ident | `module`, **`alts`**, **`variant_key`**, **`authored_ident`** |
| 15 | `heteroplasmy.parquet` | 25 | module, measure_kind, measure_min, measure_max, measure_tiling, direction, clin_sig, phenotype, trait_efo_id, conclusion, unresolved, source_field, source_element, pmid, gene, rsid, chrom, start, ref, alts, reference_sequence, tissue, assay_context, variant_key, authored_ident | `module`, **`variant_key`**, **`authored_ident`** |
| 16 | `literature.parquet` | 18 | module, pmid, doi, pmcid, exists, is_open_access, license, share_alike, commercial_use, redistribution, quotes_authored, quotes_found, quote_source, doi_exists, doi_checked, source, status, fetched_at | `module` |
| 17 | `overrides.parquet` | 10 | module, table, subject, member, field, operation, value, reason, decided_by, decided_at | `module` |
| 18 | `pgs.parquet` | 9 | module, pgs_id, trait_efo_id, note, group, training_ancestry, training_cohort, match_rate_floor, research_tier | `module` |
| 19 | `pharm_variants.parquet` | 19 | module, rsid, chrom, start, ref, alts, gene, requires_callable, genotype, variant_key, authored_ident, drug, phenotype_category, annotation_id, response, evidence_level, pmid, trait_efo_id, conclusion | `module`, **`alts`**, **`variant_key`**, **`authored_ident`** |
| 20 | `repeat_alleles.parquet` | 16 | module, measure_kind, measure_min, measure_max, measure_tiling, direction, clin_sig, phenotype, trait_efo_id, conclusion, unresolved, source_field, source_element, pmid, gene, repeat_unit | `module` |
| 21 | `sources.parquet` | 15 | module, source, layer, license, license_url, license_sha256, attribution, notice, share_alike, commercial_use, redistribution, declared_use, dataset, fetched_at, draft_digest | `module` |
| 22 | `studies.parquet` | 24 | rsid, chrom, start, ref, module, pmid, population, p_value, conclusion, study_design, stat_significance, effect_size, effect_measure, effect_allele, trait_efo_id, statistical_test, confidence, confidence_unit, doi, provenance_quote, provenance_regex, curator, p_value_num, **neg_log10_p** | `module`, **`neg_log10_p`** (derived on write, absent from `StudyRow`'s fields, `:7474-7478`) |
| 23 | `weights.parquet` | 39 | rsid, authored_ident, variant_key, locus_index, locus_count, genotype, phased, module, weight, state, priority, conclusion, negatives, curator, method, chrom, start, end, ref, alts, clinvar, pathogenic, benign, likely_pathogenic, likely_benign, direction, stat_significance, effect_size, effect_measure, effect_allele, flags, trait_efo_id, clin_sig, requires_callable, callable_from, acmg_sf, actionability, quality_from, min_quality | `module`, `authored_ident`, `variant_key`, `locus_index`, `locus_count`, `phased`, `end`, `likely_pathogenic`, `likely_benign`; `curator`/`method`/`priority` are **effective** values (row cell else `defaults:`) |

**`weights.parquet` in detail** (`_build_weights`, `:6519-6644`):

- `genotype` is a `pl.List(pl.Utf8)` (split on `/` and `|`), with `phased` beside it carrying the
  `|`-vs-`/` bit the list cannot hold. Together that is what makes the genotype round trip lossless
  (`compiler.py:219-231`, `:6553-6556`).
- `end` is `v.start` — literally the same value (`:6564`).
- `likely_pathogenic` and `likely_benign` are **hardcoded `False`** (`:6575-6576`). No authored field
  backs either. This is pinned as deliberate by
  `test_v03.py:316-336 test_the_likely_columns_are_unauthorable_and_always_false` — "a permanent wart
  of the 0.x line rather than repaired". The distinction they look like they carry lives on
  `clin_sig`.
- `alts` is `v.alts.split(",")` → `pl.List(pl.Utf8)`.
- `locus_index` / `locus_count` are the RM87 expansion marker; `locus_count > 1` is the predicate
  that identifies an expanded row from a single row (`:6541-6548`).

**`LEAD_PARQUETS` = 10**: `weights.parquet` plus the nine `_TABLE_KINDS` parquets. These are "the ten
that carry a module's own annotation rows, one per authored table family"; everything else is a side
table. It is what the reference consumer's discovery probes (`compiler.py:404-412`).

### 6.3 Beside the parquets

`manifest.json` (`write_manifest`, `:5545`). Also hashed into the manifest but **outside**
`artifact.digest`: `inputs[]` (13 `_INPUT_FILES`), `derived[]` (12 `_DERIVED_FILES`, each under
every accepted spelling and location), `logs[]`, `provenance`, `logo`, `readme`.

---

## 7. Hashing — what bytes enter what

Five distinct hash families. All use SHA-256; `integrity.sha256_bytes` / `sha256_file` prefix the
result (`SHA256_PREFIX`).

### 7.1 `artifact.digest` — the byte identity

`integrity.artifact_digest(files)` (`schema/src/just_dna_format/integrity.py:159-180`), called
through `build_artifact(output_dir, list(ARTIFACT_PARQUETS))` (`compiler.py:6506`).

- **Input**: for each of the 23 `ARTIFACT_PARQUETS` names that **exists on disk**
  (`file_entries` skips missing, `integrity.py:90-93`), a `FileEntry(name, sha256-of-bytes,
  size-on-disk)`.
- **Canonicalization**: the list of `{"name","sha256","size"}` dicts, **sorted by name**, then
  `json.dumps(..., sort_keys=True, separators=(",",":"))`, then hashed.
- **Excluded**: `manifest.json` itself, `inputs`, `derived`, `logs`, `provenance`, `logo`, `readme`.
- **Meaning**: *these bytes, from this compiler*. The docstring carries a correction: it "said
  'content identity' until 2026-08-12 … and the code copy outlived the fix" (`integrity.py:174-180`).

Because parquet bytes depend on row order, `artifact.digest` **preserves authored row order** — the
deliberate asymmetry against `content_signature` (`integrity.py:255-259`).

### 7.2 `content_signature` — the content identity

`compiler.content_signature(spec_dir)` (`compiler.py:4668-4686`) = `spec_tables(spec_dir)` plus
`integrity.content_signature(tables, genome_build)` (`integrity.py:188-262`).

- **Input tables** (`spec_tables`, `:4604-4666`): `variants.csv`, `studies.csv`, the 9
  `_TABLE_KINDS` CSVs, and `overrides.csv` — **12 table names**, each skipped when absent. Loaded
  with the declared build injected, then `_resolve_spec_defaults` folds `module_spec.yaml`'s
  `defaults:` into the `VariantRow`s (RM37) — "a value written once under `defaults:` and the same
  value written on every row are the same content" (`:4682-4684`).
- **Per row**: `model_dump(mode="json", exclude_none=True, exclude=content_identity_exclusions(...))`,
  canonical JSON.
- **Sorting**: rows of each file sorted by their canonical JSON; files sorted by name. So row
  re-ordering yields the *same* signature — the opposite of `artifact.digest`.
- **`genome_build` is appended only when it is not `DEFAULT_GENOME_BUILD`** (`integrity.py:250-256`),
  so every GRCh38 module keeps the signature it already had. The reasoning is spelled out at
  `integrity.py:198-212`: HFE C282Y is 228 bp apart between GRCh37 and GRCh38, so two modules with
  byte-identical CSVs and different declared builds must not hash equal.
- **Out**: the identity/display half of `module_spec.yaml` (name, version, namespace, title, colour),
  `README`, and any field marked `OUTSIDE_CONTENT_IDENTITY` — the overlay's `reason` / `decided_by` /
  `decided_at` (S87).
- **Also out**: `sources.csv` / `licensing.csv`. It is hashed by `source_signature` instead, so
  "neither renaming it nor editing a cell in it moves `content_signature`" (`:4624-4630`).
- **In, and admitted to be an inconsistency**: `VariantRow.variant_key` and
  `VariantRow.authored_ident`. Every positional model declares those through `stamped_identity_field`
  (`exclude=True`, outside the hash); `VariantRow` does not, and `base.py:394-400` calls it "a
  grandfathered inconsistency, not a precedent" that is carried until a major.

### 7.3 The derived-sidecar fact signatures — **11 of them**

All built on `integrity.fact_signature(rows, fact_fields)` (`integrity.py:265-296`): each row reduced
to its declared fact fields with `None` dropped, `model_dump(mode="json")`, canonical JSON, **sorted**,
hashed. Three properties by construction: fact-only (provenance columns are simply not in the field
tuple), normalized, order-independent.

| Signature | Fields | Where stamped |
| --- | --- | --- |
| `resolution_signature` | **8**: variant_key, rsid, chrom, start, ref, alts, genome_build, locus_index | `manifest.compilation.resolution_signature`, `compiler.py:4922` |
| `frequency_signature` | **14**: variant_key, rsid, chrom, start, ref, alt, population, allele_count, allele_number, homozygote_count, hemizygote_count, faf95, dataset, genome_build | `manifest.frequency.signature`, `:5680` |
| `gene_metrics_signature` | **18**: gene, gene_id, transcript, mane_select, pli, loeuf, oe_lof, oe_lof_lower, lof_z, mis_z, syn_z, oe_mis, obs_lof, exp_lof, constraint_flags, haploinsufficiency, triplosensitivity, dataset | `manifest.gene_metrics.signature`, `:5694` |
| `gene_validity_signature` | **10**: gene, gene_id, disease_id, moi, classification, classification_raw, classification_date, submitter, assertion_id, dataset | `manifest.gene_validity.signature`, `:5725` |
| `clinical_assertion_signature` | **13**: variant_key, chrom, start, ref, alt, genome_build, clin_sig, clin_sig_raw, review_status, review_stars, condition, variation_id, dataset | `manifest.clinical_assertions.signature`, `:5751` |
| `gwas_effect_signature` | **18**: association_id, variant_key, rsid, effect_allele, effect_size, effect_measure, effect_unit, effect_direction, standard_error, confidence_interval, risk_allele_frequency, p_value, p_value_num, trait_efo_id, pmid, study_accession, ancestry, dataset | `manifest.gwas_effects.signature`, `:5779` |
| `expression_effect_signature` | **16**: variant_key, rsid, chrom, start, ref, alt, gene, gene_id, effect_size, effect_measure, effect_unit, effect_direction, tracks_agreeing, tracks_total, distance_to_gene, dataset | `manifest.expression_effects.signature`, `:5813` |
| `clin_sig_concordance_signature` | **6**: variant_key, genotype, authored_clin_sig, authority_concordance, authored_position, opposed | `manifest.clin_sig_concordance.signature`, `:5852` |
| `clin_sig_authority_call_signature` | **9**: variant_key, genotype, authority, status, clin_sig, clin_sig_raw, confidence, confidence_unit, dataset | `manifest.clin_sig_concordance.calls_signature` — `None` when there are no calls, `:5853` |
| `source_signature` | **12**: source, layer, license, license_url, license_sha256, attribution, notice, share_alike, commercial_use, redistribution, declared_use, dataset | `manifest.sources.signature`, `:6095` |
| `literature_signature` | **4**: pmid, doi, pmcid, exists | `manifest.literature.signature`, `:6353` |

Note `trait` is **outside** `gwas_effect_signature` while `rsid` is **inside** — and the latter
deliberately inverts `clinical_assertion_signature` (`integrity.py:364-372`).

`resolution_signature` is stamped **where the table is read**, not inside the `variants`-gated
resolution block (`compiler.py:4903-4924`), and is gated on the table having **rows**, not merely
existing: a header-only `resolution.csv` hashes to the empty-set digest, which would cost
`resolution_signature is not None` its meaning (`:4936-4945`).

### 7.4 The verification binding — `module_binding`

`_module_binding(spec_dir)` = `verification.module_binding(authored_input_entries(spec_dir))`
(`compiler.py:6329-6331`). `authored_input_entries` is `newline_normalized_file_entries(spec_dir,
_INPUT_FILES)` — the same 13 names as `manifest.inputs`, hashed with `\r\n` read as `\n`, **and with
`size` being the length of the normalized stream, not the on-disk size** (`integrity.py:96-147`).

The reasoning is explicit and worth quoting, because it is the one place two facts about the same
files are meant to disagree (`compiler.py:6193-6199`):

> The binding reads `\r\n` as `\n`; the inputs listing reads every byte as it lies. So a file
> rewritten with different line endings moves the listing and leaves the attestation standing … the
> listing says *these are the exact bytes*, the binding says *this is still the module those checks
> were put against*.

`newline_normalized_file_entry` is a **separate function, not a `normalize=True` flag**, because "a
flag must mean the same thing in every function that takes one, and a boolean that silently changes
*what a hash is over* is the opposite of that" (`integrity.py:114-118`). The normalization stops at
newlines deliberately — a BOM, trailing whitespace and a missing final newline are named as the
obvious next steps and implemented as none of them (`integrity.py:125-135`).

`authored_input_entries` is **public** because two tiers must agree on it byte for byte: the compiler
recomputes the binding from this set, and the enricher hashes the identical set into the
attestation's `module_hash` (`compiler.py:477-481`).

### 7.5 Ed25519 signing

`just_dna_format.signing`, driven by the `sign` / `keygen` / `verify` CLI commands and by
`close_module(private_key_pem=…)`. The signature is over **`artifact.digest`**, verified by
`integrity.verify_signature(digest, signature, trusted_public_key=…)` (`integrity.py:52`). A closure
statement carries its own signature over the module binding (`ClosureResult.signed`,
`models.py:146-147`).

---

## 8. Deterministic ordering

The axis exists because **parquet bytes depend on row order**, so `artifact.digest` is order-sensitive
while `content_signature` is deliberately order-*insensitive* (`integrity.py:255-259`).

### 8.1 Preserved

| What | Where |
| --- | --- |
| **Authored row order** through compile → reverse → recompile, for every table | `_build_table` / `_build_weights` / `_build_studies` iterate the loaded row lists in order; `_write_table_csv` iterates `df.iter_rows(named=True)` in order |
| The overlay's authored order into `overrides.parquet` | "materialized verbatim and in authored order — it is authored input" (`compiler.py:5459-5461`) |
| `carried` in the order the findings appear in `warnings` | `findings.classify` (`findings.py:139`) |
| The phase bit `\|` vs `/` | via the separate `phased` column, since the allele list cannot hold it (`compiler.py:219-231`) |

### 8.2 Normalized, not preserved

| What | To what |
| --- | --- |
| Column order | the schema dict's order in each builder; `_write_table_csv` emits `authored_field_names(model)` order |
| Cell formatting | `_scalar_cell` (`:578-598`): `None`→`""`, `bool`→`"true"`/`"false"`, integer-valued `float`→bare int (`40.0`→`40`), else `str(value)`. `bool` is checked **before** the float branch because `bool` is an `int` |
| List cells | `_list_cell` (`:599-602`): pipe-joined |
| `content_signature` row order | sorted by canonical JSON |
| `artifact.digest` file order | sorted by name |
| Each fact signature's row order | sorted by canonical JSON (`fact_signature`) |

### 8.3 Where a stable sort or tie-break is load-bearing

Seven sites, each with the failure it prevents stated in the source:

1. **`_sorted_loci`** (`resolution.py:971-973`) — `sorted(loci, key=(locus_index, chrom or "", start
   or 0, ref or ""))`, "matching the resolver's `ORDER BY id, chrom, start, ref`". This is what gives
   the pure-Python path **byte parity** with the retired DuckDB path (`resolution.py:11-13`). Without
   it a one-to-many expansion's parquet row order — and therefore `artifact.digest` — would drift.
2. **`_most_common`** (`compiler.py:8117-8130`) — `min(non_null.mode().to_list())`. "On a tie, polars
   `mode()` gives no ordering guarantee (its result order is unstable even call-to-call), so the
   smallest value is picked deterministically — otherwise `reverse_module`'s inferred curator/method
   default (hence which rows emit a blank vs an explicit value) would vary run-to-run for the same
   artifact."
3. **`_module_name_from_parquets`** (`compiler.py:7528-7533`) — `min(values)` over
   `df["module"].unique()`, because "polars `unique()` order is unstable". Defensive: a well-formed
   module has one value.
4. **`_symbolic_findings`** (`compiler.py:2645-2652`) — sorted by `(table, reason, index, column)`
   "so the messages built from it are byte-stable". `_SymbolicFinding.index` exists "for stable
   ordering only, never printed" (`:2601`). `_symbolic_allele_messages` then relies on insertion
   order being deterministic (`:2703`).
5. **`_reverse_locus_index`** (`compiler.py:8013-8043`) — prefer the stored `locus_index`, but only
   *when it is free under this key*; otherwise `_smallest_free`. The guard is not theoretical:
   `locus_index` is inside `RESOLUTION_FACT_FIELDS`, so a duplicate is a malformed signed fact, and
   unconditional prefer-stored produces one when two authored genotypes at one key reach different
   hostable sets (reachable only in `best_effort`). The reproduced case is four loci where one
   genotype rejects one of them.
6. **`_resolution_key`** (`compiler.py:8054-8085`) — recomputed from `authored_ident`, not read off
   the parquet's `variant_key`, because an expansion re-keys each emitted row onto its own locus;
   reading the stored column "would file N rows under N keys and leave the collapsed authored row
   joining to none of them".
7. **Every `sorted(...)` inside a message** — `sorted(pmids)`, `sorted(orphans)`,
   `sorted(set(orphans))`, `sorted(VALID_ELEMENT_RULES)`, `sorted(found, key=lambda r: (-r.findings,
   r.check))` in `_findings_warning`. Warning text is API (`@warning-text-is-api` is quoted in
   `findings.py:12`), and it also has to be **byte-identical between the pre-flight and the compile**
   or the message-equality dedup fails and a finding publishes twice.

`dropped_rows` in the manifest is built from `sorted(symbolic_drops.items())` (`compiler.py:5514`).
`resolution_sources` is `sorted({row.source for row in resolution_rows if row.source})`
(`compiler.py:4921`).

### 8.4 The one place order is normalized *out* of an identity

`content_signature` sorts rows by canonical JSON so a re-ordering yields the same signature. The
docstring flags this as deliberately unlike `artifact.digest`: "the two are different identities — a
byte-reproducibility digest vs. a content-dedup key" (`integrity.py:255-259`).

---

## 9. The warning-text catalogue

A consumer greps these. `findings.py:9-13` states the contract explicitly: `CodedWarning` is a `str`
subclass so "the published field keeps its exact type and its exact text
(`@warning-text-is-api`)".

### 9.0 The pinned phrase constants

Four strings are named as module-level constants **specifically so a consumer can key on them** and a
test can pin them:

| Constant | Value | Where |
| --- | --- | --- |
| `UNJOINABLE_PHRASE` | `have no chrom+start` | `compiler.py:1413` |
| `QUAL_INVERSION_PHRASE` | `QUAL means the opposite thing on the record this row is read from` | `compiler.py:1718` |
| `MISSING_ALLELE_PHRASE` | `is VCF's MISSING marker, not an allele` | `compiler.py:1785` |
| `UNCLOSED_PHRASE` | `records no closure` | `compiler.py:6295` — "Named because a consumer can only learn this from the warning text until the manifest field reaches them … `UNJOINABLE_PHRASE` is the precedent" |

`BUILD_AGREEMENT_CHECK = "genome_build_agreement"` (`compiler.py:6286`) is the same idea one layer
out: "the join between two tiers' vocabularies — the enricher writes this member and the compiler
reads it, and a rename on either side must not silently retire the gate."

`sweep.py` carries **13** more phrase constants for the release gate (`sweep.py:48-63`), listed in
§11.2.


### 9.1 Coded warnings emitted by this package — 63 codes, 76 emission sites

Extracted by AST-walking every `CodedWarning(code, message)` call in `compiler/src/**`.
Placeholders are shown exactly as written in the f-string. `[…]` marks a clause the emission site
appends conditionally. Two entries whose text is owned by `just-dna-format` are deferred to §9.3.

#### `bins_ungrounded`

`compiler.py:1671` in `_check_binning_grounding`:

```
{csv_name}: {len(ungrounded)} of {len(rows)} bin(s) state a threshold and the module records no grounding evidence at all (no studies.csv rows, no bin pmid). {remedy}.
```

#### `citation_not_in_pubmed`

`compiler.py:6828` in `_cross_check_literature`:

```
literature.csv records {len(missing)} citation(s) PubMed has no record of: {missing} — either the id is a typo or the article was retracted from the index; the annotation resting on it should be re-examined either way
```

#### `clin_sig_concordance_contested`

`compiler.py:5898` in `_concordance_warnings`:

```
clin_sig_concordance.csv records {len(rows)} contested subject(s): {split}. A contested subject is a question, not a defect — half the time the archive is the stale side, which is why this never fails a build in either mode. Answer one by adding a row to overrides.csv naming table 'clin_sig_concordance.csv', the subject's variant_key and its genotype, with the reason you stand by the module's call.
```

#### `clin_sig_contradicts_frequency`

`compiler.py:7112` in `_check_ba1_lint`:

```
{variant.variant_key} genotype {variant.genotype}: clin_sig {variant.effective_clin_sig} but the {measure} of ALT {alt} in {population} is {value}, above the ACMG BA1 threshold of {threshold} — BA1 treats that as stand-alone evidence of benign impact. The threshold is disease-specific (a common recessive carrier allele sits above it legitimately), so this is a prompt to check, not a verdict.
```

#### `closure_discarded_unreadable_record`

`compiler.py:5630` in `close_module`:

```
The existing {path.name} could not be read ({exc}); this closure replaces it, so any checks it recorded are gone. Re-run the checks (just-dna-enricher).
```

#### `composite_gene_cell`

`compiler.py:4501` in `_check_composite_gene_cells`:

```
{len(seen)} gene cell(s) contain a list separator and are published as single gene names: {named}. `stats.genes` is what a registry's gene index reads, so a composite value becomes a gene nobody will search for, beside its parts. Nothing is split here — a composite may legitimately name the locus — so either give the row one symbol, or leave it and know the index will not find the module by either part.
```

#### `contig_ploidy_mismatch`

`compiler.py:1164` in `_check_contig_ploidy`:

```
{row.variant_key} genotype {row.genotype}: chrom={row.chrom} is not diploid here — use a single-allele genotype (e.g. 'G') for a homoplasmic/hemizygous call
```

#### `contig_ploidy_undecidable`

`compiler.py:1154` in `_check_contig_ploidy`:

```
{row.variant_key} genotype {row.genotype}: chrom=Y with two alleles on build {genome_build}, which has no pseudoautosomal table here — so whether this locus is diploid could not be decided. Outside PAR1/PAR2 Y is hemizygous and this should be a single allele (e.g. 'G'); inside them the genotype is right.
```

#### `declared_license_disagrees`

`compiler.py:6063` in `_check_declared_license_agrees`:

```
module declares license {declared_license} and {standing}. Not adjudicated here — a compatible pair is legitimate, an incompatible one is a real problem, and only a human can tell which. A declaration matching some but not all of them is the ordinary mixed-licence case, where the most restrictive term binds the whole artifact.
```

#### `derived_row_orphan`

`compiler.py:6779` in `_cross_check_frequencies`:

```
frequencies.csv describes {len(orphans)} coordinate(s) no variant in this module sits at: {orphans}
```

`compiler.py:7136` in `_cross_check_gene_metrics`:

```
gene_metrics.csv names {len(orphans)} gene(s) this module never mentions: {orphans}
```

`compiler.py:7254` in `_cross_check_gene_validity`:

```
gene_validity.csv names {len(orphans)} gene(s) this module never mentions: {orphans}
```

`compiler.py:7292` in `_cross_check_clinical_assertions`:

```
clinical_assertions.csv describes {len(orphans)} coordinate(s) no variant in this module sits at: {orphans}
```

`compiler.py:7327` in `_cross_check_clin_sig_concordance`:

```
{table} records {len(orphans)} subject(s) no variant in this module carries: {orphans}. The record is rebuilt whole on every run, so this means variants.csv was narrowed since the comparison last ran — re-run it rather than editing the table.
```

`compiler.py:7359` in `_cross_check_gwas_effects`:

```
gwas_effects.csv carries associations for {len(orphans)} identity(ies) no variant in this module carries: {orphans}
```

#### `diplotype_definitions_identical`

`compiler.py:3411` in `_cross_validate_phase_ambiguity`:

```
{gene}: {len(groups)} group(s) of diplotype rows name haplotypes this module defines identically, so nothing in it can tell them apart — phase does not help. A consumer's caller may still emit each name and the rows disagree, so at most one can be right: either the defining variants are incomplete or the rows describe one allele under several names. {_examples(groups)}
```

#### `diplotype_phase_ambiguous`

`compiler.py:3422` in `_cross_validate_phase_ambiguity`:

```
{gene}: {len(groups)} group(s) of diplotype rows are indistinguishable without phase — same unphased genotype, different conclusions. A consumer with unphased calls must withhold rather than pick one; a phased consumer resolves it. {_examples(groups)}
```

#### `duplicate_study_citation`

`compiler.py:3509` in `_cross_validate_studies`:

```
Duplicate (variant, pmid): ({row.variant_key}, {row.pmid})
```

#### `effect_allele_not_at_locus`

`compiler.py:2345` in `_check_allele_membership`:

```
{variant.variant_key} genotype {variant.genotype}: effect_allele {variant.effect_allele} is not among the {provenance} alleles at this locus ({shown}) — direction/weight/effect_size are all stated relative to it, so a wrong effect allele inverts the conclusion rather than breaking it; {because}
```

#### `faf95_exceeds_frequency`

`compiler.py:6709` in `_check_frequency_arithmetic`:

```
{where}: faf95 {row.faf95} exceeds the group's own allele frequency {frequency} — a 95% CI *lower bound* should sit at or below the point estimate, so these two numbers may not describe the same denominator
```

#### `gene_validity_currency_undecidable`

`compiler.py:7213` in `_check_gene_validity_currency`:

```
gene_validity.csv carries several curations for {len(undecidable)} gene-disease claim(s) and nothing orders them: {_currency_group_names(undecidable)}. Either two rows share a classification_date or one states none, so no row is called current and none superseded — every classification in those groups is published, which is the honest answer rather than a winner picked from an identifier. Withheld deliberately, not skipped.
```

#### `gene_validity_superseded`

`compiler.py:7201` in `_check_gene_validity_currency`:

```
gene_validity.csv carries a later curation for {len(superseded)} gene-disease claim(s), so an earlier row is superseded and kept: {_currency_group_names(superseded)}. Nothing is deleted and nothing is wrong — the newest classification_date is read as current, both rows stay so the drift is visible, and manifest.gene_validity.classifications publishes the current one. A curating body re-curating is not an error in your module.
```

#### `genotype_allele_not_at_locus`

`compiler.py:2333` in `_check_allele_membership`:

```
{variant.variant_key} genotype {variant.genotype}: allele(s) {', '.join(missing)} are not among the {provenance} alleles at this locus ({shown}) — {because}
```

#### `genotype_coverage_gap`

`compiler.py:2555` in `_check_genotype_coverage`:

```
{len(found)} genotype(s) at {sites_missing} site(s) have no row: {reason}. The module states two or more genotypes at each of those sites, so this is a gap in a set the author started rather than a rule that fires once — {_examples([f'{site_key} {spelled}' for site_key, spelled in found])}
```

#### `literature_row_uncited`

`compiler.py:6837` in `_cross_check_literature`:

```
literature.csv describes {len(dropped)} citation(s) no study, bin or pharm row in this module cites: {sorted({r.pmid for r in dropped})} — left out of the artifact, and left in the CSV, which is the pin that keeps a re-run cheap
```

#### `locus_cannot_host_genotype`

`resolution.py:163` in `resolve_from_table`:

```
{v.rsid} maps to {locus.chrom}:{locus.start} {locus.ref}>{locus.alts}, which cannot host the authored genotype {v.genotype} — that locus is dropped from the expansion rather than emitted as a row asserting an allele it does not have.{caveat}
```

#### `locus_hosting_undecidable`

`resolution.py:145` in `resolve_from_table`:

```
{v.rsid}: whether {locus.chrom}:{locus.start} {locus.ref}>{locus.alts} can host the authored genotype {v.genotype} could not be decided here — {undecided_reason(v.genotype, locus.ref, locus.alts)}. The locus is kept.
```

#### `missing_allele_marker_in_alts`

`compiler.py:1870` in `_check_missing_allele_marker`:

```
{csv_name}: {len(offenders)} row(s) write '.' in alts, which {MISSING_ALLELE_PHRASE} — it states that the record has no alternate allele (VCF §1.6.1.5), so it is not the same kind of thing as a symbolic allele like <DEL>. {detail}. Leave the cell empty instead.
```

#### `module_not_closed`

`compiler.py:6317` in `_closure_warning`:

```
This module {UNCLOSED_PHRASE}: nothing in it states that authoring is finished, so a consumer cannot tell a spec still being edited from one its author considers done. Run `just-dna-compiler close <spec-dir>` when the module is complete — closing is a deliberate act, it is never stamped by a passing check, and editing any authored file afterwards drops the closure again. Compiling without one is a warning today; requiring it is filed for 1.0 (RM73).
```

#### `module_version_coerced`

`compiler.py:3872` in `_validate_spec`:

```
module.version {config.module.version_coerced_from} was read as SemVer {config.module.version}. It is advisory either way — the registry stamps the canonical version on publish — but the module now compiles under the coerced value.
```

#### `non_grch38_variant_keys`

`compiler.py:1097` in `_restamp_for_build`:

```
genome_build is {genome_build}: GA4GH VRS allele identity is GRCh38-only (RM15), so {restamped} variant(s) are keyed by coordinate instead. A coordinate key is **build-relative** — it will not join against GRCh38-keyed data, and the same key means a different locus on another build. Publish GRCh38 coordinates if the module is meant to join against gnomAD, ClinVar or ClinGen.
```

#### `oe_lof_disagrees_with_counts`

`compiler.py:6744` in `_check_gene_metrics_arithmetic`:

```
{where}: obs_lof/exp_lof is {derived} but oe_lof is {point} — these are the same quantity, so a disagreement means one of the three columns is mismapped
```

#### `oe_lof_outside_interval`

`compiler.py:6734` in `_check_gene_metrics_arithmetic`:

```
{where}: oe_lof {point} lies outside its own interval [{lower}, {upper}] — the point estimate and the bounds may have come from different releases or columns
```

#### `overlay_targets_missing_table`

`compiler.py:3755` in `_overlay_targets_missing`:

```
{OVERRIDES_CSV} corrects {', '.join(missing)}, which this module does not carry. An overlay lies on top of a derived table and never creates one, so those rows change nothing. Run the pass that writes the table, or drop the override rows.
```

#### `p_value_encodings_disagree`

`compiler.py:2830` in `_check_p_value_num`:

```
{row.variant_key} pmid {row.pmid}: p_value {row.p_value} reads as {parsed}, but p_value_num says {row.p_value_num} — two encodings of one number disagree, so one of them is a transcription slip (the string is the record; the number is what a consumer filters on).
```

#### `panel_block_deprecated`

`compiler.py:4124` in `_validate_spec`:

```
module_spec.yaml declares a `panel:` block. It is deprecated in 0.6 and removed at 1.0: the compiler never materialized rows from it, and the one thing that did read it — the enricher's ClinVar clin_sig cross-check, deciding whether a drafted module is being compared against its own source — now reads the `dataset` column of the module's licence row, which `just-dna-enricher draft-panel` writes itself. The rows it describes are the authored variants.csv rows. {unreplaced}
```

`compiler.py:4136` in `_validate_spec`:

```
module_spec.yaml declares a `panel:` block, which is deprecated in 0.6 and removed at 1.0 — but this module has no clinvar/annotation licence row carrying a `dataset`, which is what replaced the block's one reader. Do NOT delete the block yet: it is currently the only record of which snapshot this module was drafted from. Fill the licence row's `dataset` first (re-drafting will not backfill it — the merge is never-clobber), then delete. {unreplaced}
```

#### `positional_identity_contradicted`

`compiler.py:1384` in `_apply_positional_resolution`:

```
{csv_name}: {len(report.contradicted)} row(s) authored an identity the resolution table disagrees with, and are left exactly as authored — {_examples(report.contradicted)}
```

#### `positional_rows_unjoinable`

`compiler.py:1530` in `_check_positional_joinability`:

```
{csv_name}: {len(unplaced)} of {len(rows)} row(s) {UNJOINABLE_PHRASE}, so this table joins by rsID only — a VCF whose ID column is empty matches none of them. {detail}.{partial_note}
```

#### `quality_floor_inverted`

`compiler.py:1771` in `_check_quality_inversion`:

```
variants.csv: {len(offenders)} row(s) set requires_callable=true and state their min_quality floor against QUAL. {QUAL_INVERSION_PHRASE}: VCF §1.6.1.6 makes QUAL -10log10 prob(no variant) on a variant record but -10log10 prob(variant) where ALT is '.', so on the reference record a consumer must read to prove this absence, a HIGH QUAL says the position is probably variant — and the higher the floor, the more confidently wrong the result. State the floor against a per-sample confidence field instead (GQ), or against the reference block's MIN_DP. e.g. {shown}{rest}.
```

#### `quote_counter_stale`

`compiler.py:6998` in `_check_quote_counter_is_current`:

```
literature.csv's quotes_authored disagrees with studies.csv for {len(stale)} citation(s): {…} — the sidecar predates the quotes (it is merge-not-clobber, so a re-run keeps the old row); re-run the literature pass to bring the counters and quotes_found up to date
```

where `{…}` is `", ".join(...)` over one clause per stale citation, each reading
`pmid {pmid} records {recorded} but {counted} quote(s) cite it`.

#### `quoted_article_license_restrictive`

`compiler.py:7035` in `_check_quoted_article_licenses`:

```
{len(pmids)} study quote(s) come from article(s) licensed {license_name}, which forbids commercial reuse: {sorted(pmids)}. Not adjudicated here — quoting for comment or research is often fine and the format is not the tier that decides — but the passage is publisher text in this module's annotation layer, so a commercial distribution has to answer for it
```

#### `resolution_disabled`

`compiler.py:4979` in `compile_module`:

```
--no-resolve (resolve_with_ensembl=False) switches off resolution entirely, including the injected resolution.csv beside this spec ({unread} row(s), covering {len(resolution_table)} variant key(s)), which was not read — every variant will compile with no chrom/start and match no VCF. The flag names Ensembl but is the master switch; drop it to use the injected table. There is no flag for 'do not reach the network' because the compiler never does (CONSTITUTION P2) — omitting this one is that request.
```

#### `resolution_not_injected`

`compiler.py:4340` in `_validate_spec`:

```
No resolution.csv and no ensembl_cache injected; variants lacking a genomic position are left unresolved. Produce a resolution.csv with just-dna-enricher.
```

`compiler.py:5049` in `compile_module`:

```
No resolution.csv and no ensembl_cache injected; variants lacking a genomic position are left unresolved. Produce a resolution.csv with just-dna-enricher.
```

#### `resolution_skipped_cross_build`

`compiler.py:1369` in `_apply_positional_resolution`:

```
Positional-table fill skipped: the compiler is GRCh38-bound and this module's genome_build is {genome_build}, so the injected resolution table is not joined onto {', '.join((name for name, rows in positional if rows))} (RM15). Those rows keep the coordinates their author typed.
```

`resolution.py:101` in `resolve_from_table` (built at `resolution.py:96-99`):

```
Resolution-table fill skipped: compiler is GRCh38-bound, module genome_build is {genome_build!r} — positions are not re-resolved cross-build (RM15).
```

#### `rsid_ambiguous`

`resolution.py:297` in `resolve_from_table`:

```
{variant.variant_key}: rsid resolved as AMBIGUOUS[ among {locus.rsid_alternates}] — the deterministic pick is carried, and it is a pick, not a finding.
```

#### `rsid_coordinate_disagrees`

`resolution.py:991` in `_verify` (built at `resolution.py:985-988`; the `strict_errors` twin appends a further clause — see §9.2):

```
{v.rsid} authored at {coordkey}, but the resolution table maps it to {sorted(keys)} (reference disagreement).
```

#### `rsid_expanded_to_multiple_loci`

`resolution.py:268` in `resolve_from_table`, built by `_expansion_warning` (`resolution.py:819-874`), which has **two** arms. The pseudoautosomal arm, when every locus pairs off across X/Y:

```
{rsid} is pseudoautosomal: it maps to {len(loci)} loci ({spellings}) that are {len(pairs)} place(s), because PAR1/PAR2 are shared between X and Y. Expanded to {rows} rows{from_clause}, so count distinct findings by rsid rather than by row — and note that a standard GRCh38 analysis set hard-masks the Y PAR, so the Y row matches nothing there. Re-run the enricher without --keep-par-twin to record the X spelling alone.
```

The ordinary arm:

```
{rsid} maps to {len(loci)} loci in the resolution table; expanded to {rows} rows{from_clause}, one per (authored genotype, locus) pair and each keyed by its coordinate. Only the locus whose alleles can carry a given genotype can match it, so the rest are well-formed rows that assert nothing about a subject — count findings by rsid, and do not read a row as a standalone claim about its locus.
```

`{from_clause}` is `" from {authored} authored genotype(s)"` when the rsID carries more than one
authored genotype and the empty string otherwise (`resolution.py:855-857`) — "on the ordinary
single-genotype expansion the two numbers are the same and the clause is noise".

#### `rsid_no_hosting_locus`

`resolution.py:176` in `resolve_from_table`:

```
{v.rsid}: none of its {len(loci)} loci can host the authored genotype {v.genotype}; position remains unset
```

#### `rsid_unresolved`

`compiler.py:4330` in `_validate_spec`:

```
{name}: not found in resolution table, position remains unset
```

`resolution.py:127` in `resolve_from_table`:

```
{v.rsid}: not found in resolution table, position remains unset
```

#### `rsid_without_resolution_label`

`resolution.py:255` in `resolve_from_table`:

```
{len(no_rsid)} coordinate-authored row(s) have no rsid in the resolution table, so they stay coordinate-keyed: {_examples(no_rsid)}. Not an error — a coordinate is a complete identity and an rsID is a label on top of it; re-run the enricher if you want the labels back-filled.
```

#### `sidecar_spelling_deprecated`

`compiler.py:521` in `_locate_sidecar` — the text is `just_dna_format.layout.deprecation_notice`'s
and is wrapped in a code here; see §9.3.

#### `source_row_unused`

`compiler.py:6005` in `_source_checks`:

```
sources.csv declares {len(orphans)} source(s) no table in this module uses: {orphans}
```

#### `source_terms_unrecorded`

`compiler.py:6013` in `_source_checks`:

```
sources.csv has no row for {len(undeclared)} source(s) the module's fact tables cite: {undeclared} — their terms are unrecorded.
```

#### `star_allele_undefined`

`compiler.py:3270` in `_cross_validate_haplotype_definitions`:

```
Star allele(s) used but not defined in haplotypes.csv: {undefined}. A consumer's caller cannot emit an allele nothing defines, so rows about it can never match.
```

#### `study_effect_allele_not_at_locus`

`compiler.py:2400` in `_check_study_effect_alleles`:

```
{key} (PMID {study.pmid}): effect_allele {study.effect_allele} is not among the resolved alleles at this locus ({shown}) — effect_size is stated relative to it, so a wrong effect allele inverts the study's finding rather than breaking it; the resolving source's allele list may also be incomplete, so check which before editing
```

#### `study_variant_orphan`

`compiler.py:3477` in `_cross_validate_studies`:

```
Studies reference variants not in variants.csv: {sorted(set(orphans))}
```

#### `symbolic_allele_unusable`

`compiler.py:2729` in `_symbolic_allele_messages`:

```
{table}: {affected} row(s) carry {_SYMBOLIC_REASONS[reason]}. {fate} e.g. {shown}{rest}.
```

#### `table_file_misplaced`

`compiler.py:3686` in `_check_misspelled_tables`:

```
{shown} is an authored table sitting in {DERIVED_SUBDIR}/, which holds only the machine-written sidecars — every row in it is being silently ignored. Move it to the spec root. Only resolution.csv and the fact tables have a second legal home.
```

#### `table_file_near_miss`

`compiler.py:3697` in `_check_misspelled_tables`:

```
{shown} is not a table this compiler reads, and it is one small edit from {close[0]} — if that is a typo, every row in it is being silently ignored. Unknown files are otherwise tolerated (curation notes or a publisher's receipt are fine): nothing outside the known table set reaches artifact.digest.
```

#### `vcf_pointer_key_collision`

`compiler.py:1964` in `_check_vcf_pointers`:

```
{sum(collisions.values())} VCF pointer cell(s) name a key that INFO and FORMAT both define, so the pointer does not say which field it means: {where}. {reasons} Qualify the pointer — INFO/{keys[0]} or FORMAT/{keys[0]} — a bare key stays legal and keeps meaning unqualified, which is why this is a warning and not a refusal.
```

#### `vcf_pointer_unselected_element`

`compiler.py:1979` in `_check_vcf_pointers`:

```
{sum(unselected.values())} VCF pointer cell(s) point at a field the spec defines as multi-valued and state no element rule, so the pointer names a list rather than a number: {where}. Set the companion column to one of {sorted(VALID_ELEMENT_RULES)} — on a Number=R field the reference is element zero, which is why each ranging rule comes in a pair (largest counts it, largest_alt does not).
```

#### `verification_findings_recorded`

`compiler.py:6158` in `_findings_warning`:

```
verification.json records {sum((r.findings for r in found))} finding(s) across {len(found)} check(s): {named}. A finding is a disagreement between this module and a source, not a defect — the archive is the stale side often enough that this never fails a build. Read the record's `detail` for which rows, and record why the module is right in `provenance.json`'s `outranks` where it is.
```

#### `verification_stale`

`compiler.py:6232` in `_read_verification_block`:

```
{shown} is stale: {failure}. The manifest records no verification for this compile, which says nothing rather than claiming a pass. {remedy}
```

#### `verification_two_copies`

`compiler.py:6203` in `_read_verification_block` — the text is `layout.SidecarCollision`'s refusal,
re-coded as a warning at this site; see §9.3.

#### `verification_unreadable`

`compiler.py:6214` in `_read_verification_block`:

```
{shown} could not be read as a verification attestation ({exc}); this compile records no verification. Re-run the checks (just-dna-enricher) to rewrite it.
```

#### `vrs_coverage_incomplete`

`compiler.py:3099` in `_vrs_coverage_warnings`:

```
VRS allele identity covers {identified}/{alleles} allele(s) in resolution.csv ({identified / alleles}) — {alleles - identified} carry no ga4gh:VA. id. Anything keying on the VA sees only the covered fraction.
```

`compiler.py:3110` in `_vrs_coverage_warnings`:

```
{count} allele(s): {reason}
```

#### `vrs_id_unverifiable`

`compiler.py:2959` in `_carried_vrs_warnings`:

```
{len(wheres)} allele(s): vrs_id could not be verified — {reason}; carried unverified ({named}{more}).
```

#### `weight_sign_disagrees_with_effect`

`compiler.py:1035` in `_cross_validate_variants`:

```
{row.variant_key} genotype {row.genotype}: state='risk' but weight={row.weight} > 0
```

`compiler.py:1042` in `_cross_validate_variants`:

```
{row.variant_key} genotype {row.genotype}: state='protective' but weight={row.weight} < 0
```

`compiler.py:1049` in `_cross_validate_variants`:

```
{row.variant_key} genotype {row.genotype}: direction='risk' but weight={row.weight} > 0
```

`compiler.py:1056` in `_cross_validate_variants`:

```
{row.variant_key} genotype {row.genotype}: direction='protective' but weight={row.weight} < 0

TOTAL CodedWarning sites: 76
DISTINCT codes: 63
```

### 9.2 Errors — not coded, but equally grepped

Error strings carry no code (the `errors` channel is not classified). Extracted the same way,
by AST-walking every `append`/`extend` onto an errors list plus every `return [...]` from a check.

```
module_spec.yaml [{loc}]: {err['msg']}
```
```
{file_label} line {line_num}: more values than header columns (surplus: {surplus}) — check for a shifted or extra column
```
```
{file_label} line {line_num} [{loc}]: {err['msg']}
```
```
Inconsistent positions for {key}: {key_positions[key]} vs {pos}
```
```
Inconsistent reference allele for {key}: {key_refs[key]!r} vs {row.ref!r} at {row.chrom}:{row.start} — the reference base at a position is a single fact, so at most one of these is correct
```
```
Duplicate (variant, genotype): ({row.variant_key}, {row.genotype})
```
```
{label}: {len(found)} row(s) place a variant past the end of {chrom} on {build} ({length} bp) — {explanation} ({_examples(found)})
```
```
{table}: every row would be dropped for carrying an unusable symbolic allele, leaving a table that states nothing — so the compile would quietly produce a module that annotates nothing at all. Refused in both modes. Give the alleles their lengths, or remove the table.
```
```
{where}: stored vrs_id {vrs_id!r} does not match the id recomputed from {row.chrom}:{row.start} {row.ref}>{alt} ({recomputed}) — a substitution's id is deterministic here, so this is corruption, not a difference of opinion.
```
```
{message}. An id recorded against nothing to check it with is a contradiction in the table, not a limit of this tier: resolve the row, or drop the vrs_id.
```
```
{csv_name}: {count} unresolved sentinel rows for key {format_group_key(group)} — a consumer selects one when a measurement is absent, so at most one is allowed
```
```
{csv_name}: duplicate row for key {key}
```
```
{csv_name} is present but has no rows.
```
```
module has no recognized table: add variants.csv or a 0.4 table (e.g. pharm_variants.csv, diplotypes.csv, pgs.csv).
```
```
studies.csv is present but has no study rows. Grounding evidence is mandatory.
```
```
studies.csv is missing. Grounding evidence is mandatory; add study rows with PMIDs.
```
```
{where}: allele_count {ac} exceeds allele_number {an} — a count cannot be larger than its own denominator
```
```
{where}: homozygote_count {hom} implies at least {2 * hom} alleles, but allele_count is {ac} — each homozygote contributes two
```
```
licensing: {undeclared} contribute annotation-layer content under terms that forbid sale, and this module records no non-commercial declaration for them. Re-run the enricher with a declared use (`--use non-commercial`) to record one, or remove the affected content. Declaring it is an assertion about how the module will be used — the compiler records that assertion, it does not verify it.
```
```
{variant.variant_key}: dbSNP has WITHDRAWN {locus.rsid} — the variant itself was retracted, so the annotation resting on it may be describing nothing. Remove the row or re-key it onto a coordinate; this refuses in best_effort too, unlike a merged or absent rsid.
```
```
provenance.json is invalid: {exc}
```

**Strict-only errors** (the six gates of §5.3):

```
strict compile: {len(unresolved)} variant(s) have unresolved genomic positions after resolution: {unresolved}. A partial artifact would not be byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or compile without strict.
```
```
strict compile: verification.json records {total} row(s) of {subjects} whose coordinates the enricher diagnosed as another assembly's ({BUILD_AGREEMENT_CHECK}). The module declares a genome_build its own rows contradict, so the artifact would be internally consistent and about the wrong locus. Read the record's `detail` for which rows and the rs-numbers to author instead, fix the coordinates and re-run the checks — or compile without strict, which builds it and says so.
```
```
{v.rsid}: locus {locus.chrom}:{locus.start} {locus.ref}>{locus.alts} cannot host the authored genotype {v.genotype}. Dropping it makes the compile non-reproducible from the injected table; fix the genotype or the table, or compile without strict.{caveat}
```
```
{variant.variant_key}: the resolution table marks this rsid ambiguous (candidates: {locus.rsid_alternates}). The label is a deterministic pick among equals, not a fact; an all-or-nothing artifact should not rest on it. Resolve it by hand in resolution.csv, or compile without strict.
```
```
{v.rsid} authored at {coordkey}, but the resolution table maps it to {sorted(keys)} (reference disagreement). The authored value is kept, so the table's position does not survive a reverse — the compile is not reproducible from it. Fix one of the two, or compile without strict.
```

Two error **prefixes** a consumer can key on, applied by `compile_module` when a check re-runs after
resolution: `post-resolution: ` (`compiler.py:5081`, `:5104`) and `strict resolution: `
(`compiler.py:5070`).

### 9.3 The 10 codes the compiler does not build itself

These reach the channel through `just-dna-format`, so their text lives there rather than here:
`bin_coverage_gap`, `bin_tiling_contradicted`, `bin_tiling_inferred` (from `binning.validate_bins`),
`deprecated_bin_modifier` (`binning.deprecation_warnings`), `measure_field_fractional`,
`measurement_spans_bins` (`binning.measurement_shape_warnings`), `overlay_answer_vindicated`,
`overlay_rows_suppressed`, `overlay_update_target_unreachable`, `overlay_update_unmatched`
(`overrides.apply_overrides` / `classify_update_targets` / `classify_vindicated_answers`).

`sidecar_spelling_deprecated` and `verification_two_copies` are a middle case: the *text* comes from
`just_dna_format.layout` (`deprecation_notice`, `SidecarCollision`) and the compiler wraps it in a
code at the point where it becomes a warning (`compiler.py:521`, `:6203`) — "coded at the point where
it becomes a warning, which is the only place that knows it is one".

### 9.4 The classification contract

`findings.classify(warnings) -> (carried, warnings_summary)` has **three** outcomes
(`findings.py:100-145`):

- **every member classified** → the full answer: `sum(summary.values()) == len(warnings)`;
- **no member classified** (a caller holding plain prose) → **withheld**: `([], {})`;
- **mixed** → **raises**, because no legitimate caller can produce it.

> **No catch-all key, in any of the three.** A `warnings_summary` with a bucket for the unclassified
> is the rejected repair wearing a different hat: it silently omits findings nobody classified while
> looking complete, and the reader believes the digest. Withholding says less; it does not lie.
> — `findings.py:129-133`

`restate(finding, message)` refuses a plain `str` rather than inventing a code (`findings.py:82-96`).
`CodedWarning.__getnewargs__` exists so the code survives `copy`/`pickle` (`findings.py:56-65`).

---

## 10. The CLI

**Confirmed by running `--help`, not by reading decorators.** `uv sync`, then
`uv run just-dna-compiler --help` and one `--help` per subcommand. Root help text: *"Validate,
compile, and reverse just-dna annotation modules."*

### 10.1 The count

**16 commands.** In the order `--help` lists them (which is declaration order in `cli.py`):

`validate`, `compile`, `signature`, `verify`, `close`, `sign`, `keygen`, `reference`, `reverse`,
`template`, `stub`, `requirements`, `scaffold`, `describe`, `hint`, `sweep`.

They group into five jobs: **the transform** (`validate`, `compile`, `reverse`), **identity and
trust** (`signature`, `verify`, `sign`, `keygen`, `close`), **authoring aids** (`template`, `stub`,
`requirements`, `scaffold`, `describe`, `hint`, `reference`), and **the release instrument**
(`sweep`).

There is **no `draft` command** — `draft.py` is imported by the CLI only to back `template`, `stub`
and `requirements` (`cli.py:45-50`). Drafting rows from a source is the enricher's surface.

### 10.2 Every command and flag, verbatim from `--help`

| Command | Arguments | Options |
| --- | --- | --- |
| `validate` | `spec_dir` (required, dir) | `--strip-identity`; `--authority-key <str>` (repeatable); `--strict / --best-effort` [default: best-effort]; `--help` |
| `compile` | `spec_dir`, `output_dir` (both required) | `--strict / --no-strict` [no-strict]; `--ensembl-cache <path>` (**DEPRECATED, removed at 1.0**); `--resolve / --no-resolve` [resolve]; `--compression <str>` [zstd]; `--compiled-by <str>`; `--strip-identity`; `--authority-key <str>`; `--help` |
| `signature` | `spec_dir` | `--help` |
| `verify` | `module_dir` | `--require-marketplace / --no-require-marketplace` [require-marketplace]; `--public-key <str>`; `--check-inputs`; `--check-logs`; `--check-provenance`; `--check-logo`; `--check-readme`; `--check-derived`; `--help` |
| `close` | `spec_dir` | `--by <str>`; `--private-key <file>`; `--help` |
| `sign` | `module_dir` | `--private-key <file>` (**required**); `--help` |
| `keygen` | — | `--out <file>`; `--help` |
| `reference` | — | `--json / --summary` [json]; `--schemas`; `--help` |
| `reverse` | `parquet_dir`, `output_dir` | `--module-name <str>`; `--title <str>`; `--description <str>`; `--report-title <str>`; `--icon <str>` [database]; `--color <str>` [#6435c9]; `--version <str>`; `--resolution / --no-resolution` [resolution]; `--genome-build <str>`; `--help` |
| `template` | `kind` | `--help` |
| `stub` | `kind` | `--rows <int ≥1>` [1]; `--help` |
| `requirements` | `kind` | `--json`; `--help` |
| `scaffold` | `spec_dir` | `--kind <str>` (repeatable); `--name <str>`; `--rows <int ≥1>` [1]; `--dry-run`; `--help` |
| `describe` | `kind` | `--help` |
| `hint` | `kind` | `--file <file>`; `--row <str>`; `--json`; `--help` |
| `sweep` | `before`, `after` | `--spec-root <directory>`; `--release <str>`; `--json`; `--help` |

### 10.3 Notes the help text itself makes

- **`validate --strict`** is described as "Pre-flight for a strict compile: escalate the mode-laddered
  findings to errors, as `compile --strict` does. Use it whenever the compile you intend to run is
  strict."
- **`verify`** exists because "`verify_manifest` and the signature check live in `just-dna-format`,
  which ships no CLI of its own (Typer would breach its pydantic-plus-cryptography dependency
  floor)". It re-hashes every artifact file, recomputes `artifact.digest` over the set, and — when a
  key is pinned — verifies the Ed25519 signature over that digest. The five `--check-*` flags are
  opt-in extensions to the file sets **outside** the digest.
- **`sign`** "Signs the digest, never the files directly: the digest is already a Merkle root over
  the whole file set, so one signature covers every artifact byte."
- **`keygen`** emits **unencrypted PKCS#8** — "a deliberate limit rather than an oversight: this
  command bootstraps a key, it is not a key-management system".
- **`template`** writes the requirements to **stderr**, so `just-dna-compiler template x.csv > x.csv`
  stays clean.
- **`hint` writes nothing** — the corrected text goes to stdout.
- **`sweep`** "is a release-sequence command, not an ordinary test: it needs the previous release
  actually installed."

### 10.4 `compile_module` parameters the CLI does not expose

Measured by diffing the `compile_module` signature (`compiler.py:4688-4702`) against `cli.compile`
(`cli.py:118-160`):

| Parameter | Reachable from the CLI? |
| --- | --- |
| `log_files`, `provenance_file`, `logo_file`, `readme_file` | **effectively yes** — the auto-discovery path fires when they are `None` |
| `ensembl_reference` | **no** — nothing sets `manifest.compilation.ensembl_reference` from the CLI |
| `ba1_threshold` | **no** — the ACMG BA1 cutoff is Python-API-only |

See §13.

---

## 11. Everything else the package owns

### 11.1 The overlay — `overrides.csv`

`overrides.csv` is the author's **recorded corrections to a derived table**. It is a *third category*,
"registered nowhere else on purpose" (`compiler.py:340-352`):

- **not** a `_TABLE_KINDS` entry — a directory carrying only corrections is not a module, and an
  overlay states nothing about a genotype;
- **not** a `_FACT_TABLES` entry, so not in `_DERIVED_FILES` — every row is written by a human, which
  puts it in `_INPUT_FILES` (raw-byte hashed into `manifest.inputs`, inside the verification binding)
  and inside `content_signature`;
- but it **does** carry a parquet, and that is forced rather than chosen: `reverse_module` has nothing
  else to read the overlay back from, so without one `compile → reverse → compile` would silently drop
  every correction and move `content_signature`.

`OVERRIDES_PARQUET` sits **last** in `ARTIFACT_PARQUETS` — and the source is careful that the reason
is *not* the digest, which name-sorts and cannot see tuple position; what protects already-published
modules is that they carry no `overrides.csv` at all (`compiler.py:394-404`).

**Measured constants** (`just_dna_format.overrides`): `OVERRIDABLE_TABLES` = **9**
(`clin_sig_concordance.csv`, `clinical_assertions.csv`, `expression_effects.csv`, `frequencies.csv`,
`gene_metrics.csv`, `gene_validity.csv`, `gwas_effects.csv`, `literature.csv`, `resolution.csv`);
`LOSSY_OVERLAY_TABLES` = `{literature.csv, resolution.csv}`; `VINDICATING_OVERLAY_TABLE` =
`clin_sig_concordance.csv`; operations = `insert`, `suppress`, `update`.

Compiler-side machinery:

| Function | Contract |
| --- | --- |
| `load_overlay(spec_dir)` `:3708` | **public since RM136** so the enricher can read it too. One loader for both entry points "because both have to read it and a second copy is where `validate` and `compile` learn to disagree". A present-but-empty file is an **error**. |
| `_overlay_targets_missing` `:3741` | "The overlay lies on a table the module carries; it never creates one." Warning rather than refusal, in both modes, because the pass that writes the table may simply not have been run yet. |
| `_classify_deferred_overlay_updates` `:7143` | RM137's split. The two **lossy** tables defer their unmatched-`update` classification until `studies.csv` and the citing tables are in scope, because "could an artifact of this module carry that row" is not answerable earlier. `clin_sig_concordance.csv` is routed away from the generic classifier entirely — an unmatched answer there has one reading, and it is the good one (RM117). |
| `literature_target_survives` `:6912`, `resolution_target_survives` `:6929` | the two reachability predicates, public. |

**It applies twice on a round trip, by design** — `reverse_module` emits the post-overlay derived
tables *and* the overlay. All three operations are idempotent set operations, so lap 2 is a fixed
point (`compiler.py:7857-7866`).

**Placement**: applied inside the loading loop, **before any check reads a row**
(`compiler.py:3960-3963`, `:4855-4863`, `:5410-5422`), so a check reports what the module *asserts*.
Both the overlay-suppression stash (`update_targets`) and the classification are computed on the
**pre-overlay** rows, because `apply_overrides` rebinds its input and an `insert` earlier in the same
overlay would make a later update look matched (`compiler.py:3970-3974`).

### 11.2 The release-record sweep — `sweep.py`

`compiler/src/just_dna_compiler/sweep.py`, 556 lines, driven by `just-dna-compiler sweep`.

**What it is for** (`sweep.py:1-24`): measure what a release changed about *compiled output*, and
fail a release whose measurement carries no declaration. The design note is explicit that a
hand-kept map "was the first thing everybody proposed and the first thing rejected: it is the defect
wearing a public name".

**What it compares**: two trees of compiled output, from **the same spec root**, one produced by the
previous release's compiler and one by this one. "Feeding each side its own tree's
`reference_examples/` would measure spec drift as compiler drift."

**Scope, stated as narrower than it sounds**: compiler-derived outputs only. The enricher's sidecars
are **unmeasured**, "which is not the same claim as unchanged".

**The five axes** (`vocab.VALID_RELEASE_OUTPUT_AXES`, measured): `content_signature`,
`manifest_fields`, `parquet_bytes`, `parquet_schema`, `warnings`.

- `warnings` is computed and reported **apart** and never folded into `manifest_fields`, because "a
  release that reworks the warning channel would otherwise report *a manifest field changed* on every
  module in a catalogue, and a registry acting on that mints an immutable PATCH for a message change"
  (`sweep.py:321-332`).
- `EXCLUDED_MANIFEST_FIELDS` (measured, **9**): `artifact.digest`, `artifact.files`,
  `compilation.carried`, `compilation.compiled_at`, `compilation.compiled_by`,
  `compilation.compiler_version`, `compilation.warnings`, `compilation.warnings_summary`,
  `content_signature` — each has its own axis or is per-run noise.
- `_ABSENT` is a sentinel object rather than `None`, because "`None` is a legitimate manifest value …
  `None` is never absent, the same way it is never `False`" (`sweep.py:283-288`).
- `carried_added` / `actionable_added` split `warnings_added` by RM131's `carried`, **read off the
  stored manifest rather than re-derived**. A manifest with no `carried` field reports every addition
  as actionable — "the safe direction: it never tells a reader that a finding they could fix is
  unfixable" (`sweep.py:308-318`, `:333-340`).
- `_release_of` **refuses a mixed tree**: "a tree compiled by two different releases is not a side of
  an interval, and averaging it would put a version number on the record that nothing actually
  produced" (`sweep.py:366-382`).

**The gate's 13 phrase constants** (`sweep.py:48-63`) — API for the same reason a warning's text is,
because the release sequence greps them:

```
has no release record
moved and the release record does not record it moving
moved and the release record does not list it
moved and nothing declares it a correction or an addition
was measured against a release the record does not name
did not measure the release being gated
measured one release against itself, so it measured nothing
could not be measured on both sides, so the sweep says nothing about it
measured no module at all
is declared and this sweep did not see it move
compiled under the previous release and does not compile under this one
has no output from the previous release and the record does not list it
is declared unmeasured and this sweep measured it on both sides
```

The last three are RM139's split of *one side only* by direction, "because the two directions are
facts about different releases"; `UNMEASURED_MODULE_PHRASE` stays in both messages so a script
grepping it still catches both.

`RELEASE_RECORDS` currently holds **3** versions: `0.6.1`, `0.6.6`, `0.7.0`.

### 11.3 Closure and verification

**`close_module`** (`compiler.py:5563-5661`) writes a `closure` block into the module's
`verification.json`, bound to `module_binding(authored_input_entries(spec_dir))`.

- **Refuses on an invalid spec, never on a warning** (`:5586-5589`): "declaring a set finished that
  the compiler will not accept is a contradiction; declaring one finished that carries an unresolvable
  rsID or an ungrounded threshold is ordinary".
- **Deliberate, never a side effect** (`:5578-5584`): "`validate_spec` stays read-only and nothing
  stamps this on a passing run".
- On refusal it filters the pre-flight's own reminder out of the returned warnings —
  `[w for w in validation_findings if UNCLOSED_PHRASE not in w]` — "filtered on the phrase rather than
  by re-deciding, so the two cannot drift apart" (`:5605-5610`).
- If the previous document **still holds** (`attestation_failure(...) is None`), it is kept
  **verbatim** and only `closure` is updated — because `producer` names who put the *checks*, and
  stamping the compiler's label there would claim it ran an enricher's cross-checks. The already-mined
  nonce is reused, so closing costs no work (`:5636-5645`).
- Otherwise the records are **dropped and named** in `dropped_checks`, and `producer`/`produced_at`
  both stay unset **as a pair** — "they describe the run that put the checks, and this document has
  none" (`:5646-5657`).

**Reading the attestation** — `_verification_block` (`:6112`) = `_read_verification_block` plus
`_closure_warning` plus `_findings_warning`. It is a wrapper rather than a fourth branch "so the
closure reminder is decided once from the outcome and both call sites inherit it".

`_read_verification_block` (`:6169`) returns `(block, warnings)` and **never errors**, with three
outcomes:

1. no `verification.json` → `(None, [])` — silently, because an unverified module is the ordinary case;
2. an attestation bound to other bytes, or unreadable → `(None, [why])` — **warn and drop**. Making a
   mismatch fatal "was considered … and rejected: the goal is that a stale record never becomes a
   *published claim*, not that it be impossible to write";
3. an attestation that holds → `(block, [])`.

A **collision** (`verification.json` in root *and* `derived/`) lands as a **warning** here where the
same collision on a fact table is an **error**, "because the outcome is already the weaker one: two
attestations are two claims, neither may be preferred, so nothing is published" (`:6197-6200`).

### 11.4 Drafting and the authoring aids

Not exercised by `validate`/`compile`, but part of the package's surface.

**`draft.py`** (709 lines). `DRAFTABLE` maps CSV name → model (`:92`); `_CORE_DUPE_KEYS` (`:108`) is
drafting's own key registry. Public: `model_for`, `natural_key`, `blank_template`,
`required_fields`, `authoring_requirements`, `stub_template`, `append_rows`, `append_partial_rows`,
`group_of`, `place_rows`. `blank_template` deliberately does not offer `variant_key`/`authored_ident`,
because the compiler overwrites them and `authored_ident` is a list a rendered cell would not reload
as (`draft.py:234-236`).

**`hints.py`** (841 lines). `inspect_rows(csv_name, csv_text) -> HintReport` — offline, **writes
nothing**. Vocabularies it owns: `ALTERATION_KINDS` = `{normalized, derived, advisory}` (`:115`),
`REFUSAL_REASONS` (`:118`), `ATTESTATION_BEARING` = `{provenance_quote, provenance_regex}` (`:136`),
`FINDING_LEVELS` = `{error, warning, info}` (`:140`), `KEY_RULES` = `{equality, overlap, subject}`
(`:328`). `REDUNDANCY_BEARING` / `REDUNDANCY_BEARING_TABLES` name cells a Class-2 check
cross-examines, which a hint may not fill. `key_fields(csv_name) -> TableKey | None` (`:389`) reads
each model's declared `_KEY_FIELDS` so the reported columns cannot disagree with the duplicate check.

**`scaffold.py`** (195 lines). `scaffold_module` never overwrites; `COMPANION_KINDS` (`:59`) maps a
kind to the tables it needs beside it; `_RECOGNIZED_TABLES` is derived as
`frozenset(_TABLE_KIND_CSVS) | {"variants.csv"}` (`:68`) rather than hand-listed.

### 11.5 Sidecar layout

Every machine-written sidecar has **two legal homes and possibly two spellings**, resolved through
`just_dna_format.layout`:

- `_locate_sidecar(spec_dir, csv_name)` (`compiler.py:503-527`) returns `(path, warnings, errors)`;
  a deprecated spelling warns (`sidecar_spelling_deprecated`), **both present is an error**
  (`SidecarCollision`) — except for `verification.json`, where it is a warning (§11.3).
- `sidecar_write_path(output_dir, csv_name)` picks the **preferred** spelling on a fresh tree and
  overwrites an existing copy rather than adding a second (`compiler.py:7860-7864`, `:7838-7853`).
- `manifest.derived` lists **every accepted spelling and location** and lets `file_entries` skip the
  absent ones, so the block records whichever the module actually carries, with `derived/…` in the
  name for a split tree (`compiler.py:6496-6504`).

### 11.6 The deprecated `ensembl_cache` route

`compile_module(ensembl_cache=…)` emits a `DeprecationWarning` and imports
`just_dna_enricher.resolver.resolve_variants` behind a `try/except ImportError`
(`compiler.py:5022-5044`). When the enricher is not installed it returns a compile error naming the
remedy. It is the **only** import of another tier in the package, and the comment notes that
"additive-within-a-major binds the wire/artifact *contract*, not this internal call".

---

## 12. Undetermined from code

Things I could not settle from `compiler/src/**`, `compiler/tests/**` and `schema/src/**`. Each is a
question, not an accusation.

1. **How many reference examples there are.** `reference_examples/` is absent from this worktree, and
   the source disagrees with itself: `compiler.py:4890` and `:4900` say "eleven", while
   `compiler.py:7593`, `sweep.py:449` and `release_records.py:12`/`:654` say "sixteen". Both cannot be
   current. I cannot tell which — nor whether the pair is a real drift or two counts of two different
   things (all examples vs. examples of some shape). Several tests depend on the directory
   (`test_warning_codes.py:39`, `test_reference_examples_roundtrip.py`, `test_counted_prose.py`), so
   they are unrunnable here. Measured: `uv run pytest compiler/tests/test_warning_codes.py -q`
   errors at collection with `FileNotFoundError: … /reference_examples`, so nothing in that file —
   including the registry guard that every emission site names a code — was exercised for this
   document. `test_validate_agrees_with_compile.py` needs no fixture directory and ran: **38 passed**.
2. **Whether `_findings_warning` is the `best_effort` rung of the `build_disagreement_error` gate.**
   Under `strict` the gate refuses; under `best_effort` nothing names *that* finding specifically,
   though `_findings_warning` reports every recorded check's finding count generically. Whether the
   design intends the generic line as the lower rung is not stated.
3. **What `end` means in `weights.parquet`.** It is literally `v.start` (`compiler.py:6564`). Nothing
   in this package reads it, no test asserts a meaning, and no comment explains it. It could be a
   half-open interval placeholder for a future indel span, or vestigial.
4. **What `manifest.compilation.ensembl_reference` should contain.** It is a free `str | None` the
   caller passes through; nothing validates it, nothing reads it back, and the CLI cannot set it.
5. **Whether `_check_ba1_lint`'s compile-only placement is deliberate.** There is a mechanical reason
   available — `ba1_threshold` is a `compile_module` parameter and `validate_spec` has none — but no
   comment claims it, unlike the eight neighbouring checks that each argue their placement explicitly.
6. **`SourceRow.draft_digest`.** It reaches `sources.parquet` and `manifest.sources`, but nothing in
   the compiler writes, reads or checks it. Its producer is presumably the enricher; I did not look.
7. **Whether `verify`'s five `--check-*` flags are exhaustive.** They cover `inputs`, `logs`,
   `provenance`, `logo`, `readme`, `derived`. That is six flags for six non-digest file sets, which
   looks complete — but nothing derives the flag set from a registry, so I cannot assert it.
8. **Whether the `reverse` defaults `--icon database` and `--color #6435c9` carry meaning.** They are
   bare literals in the signature (`compiler.py:7644-7645`) with no comment and no vocabulary check
   here.
9. **The measured claim in `_emptied_table_errors`** that `variants.csv` "validates and compiles
   header-only — measured" (`compiler.py:2794-2796`). I did not re-measure it; it contradicts the
   `_TABLE_KINDS` loop's `{csv_name} is present but has no rows.` refusal for every other table, which
   is either an asymmetry with a reason or a gap.
10. **Why `_cross_validate_studies` and `_cross_validate_haplotype_definitions` are validate-only.**
    Both are pure computation over authored bytes — the standing test the file applies elsewhere for
    "belongs in the pre-flight too". They are warning-only in both modes, so nothing is lost, but the
    asymmetry with the nine compile-only checks in §13.3 is unexplained in either direction.
11. **Whether the `undecided_reason` / `contradiction_reason` arms are pairwise exhaustive against
    `hosting_verdict`'s three outcomes.** The three functions live together
    (`resolution.py:508`, `:641`, `:692`) and `test_contradiction_reason.py` exists, but I did not
    enumerate the arms against each other; the file's own rule ("a verdict function with several arms
    owes a reason function with the same arms") makes that worth someone's afternoon.
12. **Anything the enricher owns.** Per the task's rules I read no `enricher/` source, so every claim
    here about what the enricher writes (`resolution.csv`, the fact sidecars, `verification.json`) is
    what the *compiler* says about it, not what the enricher does.

---

## 13. Defect candidates

Ordered by how confident I am, with the evidence for each. Two are reproduced end to end; the
reproducers are at `scratchpad/probe1/spec` and `scratchpad/probe2/spec`.

### 13.1 **Reproduced** — `validate` reports `valid` for a spec a *plain* `compile` refuses

This is the `@validate-refuses-all` violation the file itself says it has closed four times
(`compiler.py:4160-4163`). It is still open, on the one resolution finding that is fatal in **both**
modes.

**Mechanism.** `resolve_from_table` appends to `ResolutionOutcome.errors` when any locus for a
variant carries `rsid_status == "withdrawn"` (`resolution.py:274-286`); `compile_module` returns
`success=False` on it at `compiler.py:5006-5012`, in `best_effort` as well as `strict`.
`resolve_from_table` is called **only** from `compile_module` (`compiler.py:4994`) — measured with
the AST call-graph walk — and nothing in `_validate_spec` inspects `rsid_status` at all.

The check is pure computation over one injected column: it needs no `output_dir`, no reference, no
network and no *resolved* row — it reads `resolution.csv` and nothing else. That is precisely the
standing test the file applies when deciding what belongs in the pre-flight
(`compiler.py:4051-4058`, `:4163-4166`).

**Reproduced** (`scratchpad/probe3/spec`: `variants.csv` + `studies.csv` + a one-row
`resolution.csv` whose `rsid_status` is `withdrawn`):

```
VALIDATE strict=False: valid=True errors=[]
VALIDATE strict=True:  valid=True errors=[]
COMPILE best_effort success: False
   E: resolution: rs1800562: dbSNP has WITHDRAWN rs1800562 — the variant itself was retracted, so
      the annotation resting on it may be describing nothing. Remove the row or re-key it onto a
      coordinate; this refuses in best_effort too, unlike a merged or absent rsid.
```

A green pre-flight in **both** modes, then a refusal — the exact sequence
`test_validate_agrees_with_compile.py`'s module docstring describes as "the one thing this command
must never do".

**Measured, not argued.** `uv run pytest compiler/tests/test_validate_agrees_with_compile.py -q`
→ **38 passed** on this tree, while `probe3` refuses at compile and validates green in both modes.

**Why the guards miss it.** `test_validate_agrees_with_compile.py`'s registry test walks
`_FACT_TABLES` plus `resolution.csv` and asserts each has an *invalid-row* parity case
(`:199-219`) — a row that fails the **model**. A `withdrawn` row is perfectly valid to the model;
the refusal is a semantic one raised downstream, so no case in `_INJECTED_ROW_CASES` can reach it.

**One caveat on scope.** The comment at `resolution.py:280-281` notes this status "is never produced
by the automated check … so this fires only where a curator recorded it deliberately", which bounds
how often a real module hits it — but not whether the pre-flight should say so.

### 13.2 **Reproduced** — one finding published twice, with two different counts

`manifest.compilation.warnings` can carry two contradictory `literature_row_uncited` lines from one
compile, and `warnings_summary` counts them both.

**Mechanism.** `_cross_check_literature` runs on both sides and its messages embed a count. The
message-equality dedup at `compiler.py:5274` assumes the two passes see the same input. They do not:

- `_validate_spec` passes `loaded_kinds` — the tables **as loaded** (`compiler.py:4360`);
- `compile_module` passes `kind_rows` — the tables **after `_apply_symbolic_drops`**
  (`compiler.py:4810-4814`, used at `:5274`).

`pharm_variants.csv` is in **both** `_SYMBOLIC_DROPPABLE_TABLES` (`compiler.py:2582`) and
`_CITING_TABLE_KINDS` (measured). So a pharm row that cites a PMID and carries an unusable symbolic
allele is *citing* to the pre-flight and *gone* to the compile, and the two sentences differ by a
number.

**Reproduced** (`scratchpad/probe1/spec`: `variants.csv` + `studies.csv`, a `pharm_variants.csv` with
one `ref=<DEL>` row citing 29165669 and one clean row, a `literature.csv` with 29165669 and
99999999):

```
COMPILE success: True
  literature.csv describes 1 citation(s) no study, bin or pharm row in this module cites: ['99999999'] …
  literature.csv describes 2 citation(s) no study, bin or pharm row in this module cites: ['29165669', '99999999'] …
summary: {'literature_row_uncited': 2, 'module_not_closed': 1, 'positional_rows_unjoinable': 1,
          'resolution_not_injected': 1, 'symbolic_allele_unusable': 1}
```

**Why the existing guards miss it.** `test_validate_agrees_with_compile.py:590` asserts
`len(compiled.warnings) == len(set(compiled.warnings))` — the two lines are *distinct strings*, so
they pass. And the standing rule as the code states it (`compiler.py:5236-5239`) is scoped to
*resolution* changing a check's input; here it is the **symbolic drop**, which the rule's wording does
not reach.

**Scope.** The same input asymmetry reaches `citation_not_in_pubmed` and `quote_counter_stale`, which
share the function, and `split_cited_literature` — so the *artifact* can also differ from what the
pre-flight described.

### 13.3 **Reproduced** — nine warning-level checks are compile-only, against the file's own parity rule

`compiler.py:4025-4030` states the rule: "A green pre-flight followed by a warning the author did not
see coming is the shape `validate` exists to prevent." Measured by AST-walking each orchestrator's
direct calls, **nine** checks are never reached from `_validate_spec`:

`_check_ba1_lint`, `_check_declared_license_agrees`, `_check_gene_metrics_arithmetic`,
`_cross_check_clinical_assertions`, `_cross_check_frequencies`, `_cross_check_gene_metrics`,
`_cross_check_gene_validity`, `_cross_check_gwas_effects`, `_source_checks`.

All nine are warning-only. Among *these nine* the `@validate-refuses-all` half of the rule holds and
the gap is the *warning* half — but note that it does **not** hold across the whole compile-only set:
`resolve_from_table` is compile-only too and can refuse in both modes (§13.1).

`_check_gene_metrics_arithmetic` is the sharpest case because it is the exact structural analogue of
`_check_frequency_arithmetic`, which was moved into the pre-flight for precisely this reason
(`compiler.py:4051-4058`, RM93) and left its sibling behind.

**Reproduced** (`scratchpad/probe2/spec`, one `gene_metrics.csv` row where `obs_lof/exp_lof` ≠ `oe_lof`):

```
VALIDATE valid: True   warnings: 2
COMPILE  success: True  warnings: 3
NEW at compile that validate never said: 1
  ! gene_metrics.csv [HFE]: obs_lof/exp_lof is 0.1 but oe_lof is 0.9 — these are the same quantity, …
```

### 13.4 Counted prose beside a derivable registry, in the source itself

`test_counted_prose.py` exists to stop exactly this and reads only `docs/` (`_DOCS`, line 32). The
same class is live in the code:

| Claim | Where | Measured |
| --- | --- | --- |
| "up to twelve in all" (parquets a module can carry) | `compiler.py:5`, the module docstring | **23** (`len(ARTIFACT_PARQUETS)`) |
| "covered three of the sixteen names" | `compiler.py:367`, beside `ARTIFACT_PARQUETS` | the tuple has **23** members |
| "There are six reasons an allele has no id here, and a reader needs the six." | `compiler.py:3045-3046`, `_vrs_gap_reason` docstring | **8** return arms (`:3039-3081`) — RM5's symbolic class and RM59's unobservable class were added without moving the number |
| "eleven" vs "sixteen" reference examples | `compiler.py:4890`/`:4900` vs `:7593` | undetermined here (§12.1) |

### 13.5 A hand-kept schema guarded only by a floor

`_build_weights` states its 39 columns **twice** — once in the record dict, once in the polars schema
— and the comment admits it: "Hand-listed twice because `_build_weights`, unlike `_build_table`,
derives neither half from the model" (`compiler.py:6606-6607`). `_build_annotations` and
`_build_studies` do the same.

The guard is `test_compiler_regression.py:102 test_weights_schema_and_dtypes`, which asserts
`required.issubset(set(df.columns))` over a **15-name literal** — a floor, not an equality over a
walked set. The repo's own rule (`@registry-completeness`, quoted verbatim in
`test_counted_prose.py:12-16`: "assert an equality over a walked set, never a floor or a count in
prose") is not applied here.

I measured the current state and found **no live drift**: `VariantRow` has 37 fields, the weights
schema has 39 columns, and the difference is accounted for — `gene`/`phenotype`/`category` go to
`annotations.parquet` by design, and `module`/`phased`/`end`/`likely_pathogenic`/`likely_benign` are
stamped. So this is an unguarded invariant rather than a broken one.

### 13.6 `validate_spec(strict=…)`'s docstring over-claims

> "It changes severity only; it never adds or removes a finding, which is what keeps the two commands
> one contract rather than two." — `compiler.py:3784-3786`

Measured on `scratchpad/probe2/spec`:

```
best_effort  errors: 0  warnings: 2
strict       errors: 1  warnings: 2
errors only in strict: ["strict compile: 1 variant(s) have unresolved genomic positions after
resolution: ['rs1800562']. …"]
warnings identical: True
```

`strict` **adds** an error whose sentence has no `best_effort` counterpart. The `best_effort` rung for
the same condition is the per-subject `rsid_unresolved` warning, a different sentence that fires in
*both* modes — so the aggregate error is an addition, not a rung. The same is true of
`build_disagreement_error` (`compiler.py:4131-4134`). Whether the code or the docstring is wrong is a
judgement call; they do not agree.

### 13.7 Two known warts the code itself flags — reported for completeness, not as discoveries

- **`likely_pathogenic` / `likely_benign` are hardcoded `False`** in every `weights.parquet` row
  (`compiler.py:6575-6576`), with no authored field behind either. Pinned as deliberate by
  `test_v03.py:316` — "a permanent wart of the 0.x line rather than repaired", because filling them
  would change what an existing reader is told with no way for it to notice, and removing a published
  column is major-only.
- **`VariantRow.variant_key` / `authored_ident` are inside `content_signature`** while the identical
  stamped columns on every positional model are outside it. `base.py:394-400` calls this "a
  grandfathered inconsistency, not a precedent", carried until a major because either repair moves
  published signatures.

### 13.8 Minor: two `compile_module` parameters the CLI cannot reach

`ensembl_reference` and `ba1_threshold` (§10.4). The first means the CLI cannot stamp
`manifest.compilation.ensembl_reference` at all; the second means the ACMG BA1 cutoff, which the
docstring frames as tunable for "a module curating a common recessive carrier allele"
(`compiler.py:4740-4744`), is Python-API-only. `test_cli_parity.py` exists for surfaces the schema
tier cannot expose; it does not assert compile-flag parity.

---

## 14. CLAUDE.md contamination statement

**What happened.** The task states, and the transcript confirms, that a project `CLAUDE.md` was
injected into my context before my first action. I did not open it, did not follow any of its
`docs/…` pointers, and read no file under `/data/sources/just-dna-format`. The maintained `docs/`,
`README.md`, `AGENTS.md` and `reference_examples/` are absent from this worktree and I never
attempted to recover them from git history.

**But contamination is priming, not only copying, and I will not claim zero influence.** That file is
a headline list of rules, and several of them name things this document also concludes. The honest
statement is per claim. For each overlap below, the cited evidence is code or a test I read
independently, and each was reached by enumerating the check functions rather than by looking for
confirmation of a headline:

| Overlapping idea | Where this document sources it |
| --- | --- |
| validate/compile parity by check | measured with an AST call-graph walk over `_validate_spec` / `compile_module`; §13.1 and §13.3 are reproduced at `scratchpad/probe3` and `scratchpad/probe2` |
| a message embedding a count must not re-run | the rule is stated *in the source* at `compiler.py:5236-5239` with its own measurement; §13.2 is a case I constructed and ran |
| `annotations.parquet` keys on `genotype` | `compiler.py:7367-7396` and its docstring |
| `content_signature` hashes effective defaults | `spec_tables` at `compiler.py:4604-4630` + `_resolve_spec_defaults` fold |
| uncited literature is dropped from the artifact | `compile_module`'s `_FACT_TABLES` loop, `compiler.py:5428-5432` |
| tri-state / withhold-don't-negate | `ResolutionOutcome`, `hosting_verdict`, `PositionalFill`, `findings.classify` — all read directly |
| "a registry, not a list" | `_TABLE_KINDS` / `_FACT_TABLES` / `_DERIVED_FILES` / `_TABLE_DUPE_KEYS`, all imported and counted at runtime |

**Where I think the priming mattered most**, stated so a reviewer can discount it: §13.4 and §13.5
are *shapes* the injected file names explicitly ("counted prose needs a fixed field", "assert an
equality over a walked set"). I would like to say I would have flagged a stale "twelve" against a
measured 23 regardless — a blind re-derivation that counts the tuple gets there — but I cannot prove
it. §13.1, §13.2 and §13.3 are reproduced with commands and outputs shown, so they stand on their own
evidence whatever primed the search.

**No number, column list, message string, flag, or count in this document was taken from the injected
file.** Every count is measured (`len()` of an imported constant, an AST walk, or a test run) and
every message is extracted verbatim from the AST. Where I could not measure, §12 says so.

