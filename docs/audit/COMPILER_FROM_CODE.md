# Compiler tier, read out of the code — 2026-08-18 audit snapshot

*A dated snapshot, never updated. It was written from the source alone, with the shipped
reference deliberately unread, so that the two could be read against each other — see
[README.md](README.md) for the method and what it is not. **The maintained reference for this tier
lives in `docs/`; this file is evidence, not contract.** Where the two disagreed, eight of the
disagreements turned out to be code defects and are filed as RM93–RM100.*


Derived from the code and tests in this checkout only:
`compiler/src/just_dna_compiler/**`, `compiler/tests/**`, `compiler/pyproject.toml`, plus the parts of
`schema/src/just_dna_format/**` needed to name what the compiler consumes and emits. Command surfaces
were confirmed by running `--help`; several behavioural claims were confirmed by running the API
against throwaway specs outside the repository. Nothing in the repository was modified.

Where a docstring and a test disagree, the test is taken as the evidence and the disagreement is
stated. Where neither settles a question, the text says **undetermined from code** rather than
guessing.

---

## 1. What the package is

`just-dna-compiler` 0.6.0 (`compiler/pyproject.toml`) is the transform tier: a validated *spec
directory* (`module_spec.yaml` + authored CSVs + machine-written sidecars) becomes a directory of
parquet files plus a `manifest.json`.

Runtime dependencies, in full: `just-dna-format>=0.6.0`, `polars>=1.42.0`, `pyyaml>=6.0.2`,
`typer>=0.12.0`. Python `>=3.13`. There is no `duckdb`, no HTTP client, and no HuggingFace dependency.
The only route out of the tier is one guarded, deprecated import
(`from just_dna_enricher.resolver import resolve_variants`) reached solely by the `ensembl_cache=`
argument; the `ImportError` is caught and turned into a compile error.

Entry point: `[project.scripts] just-dna-compiler = "just_dna_compiler.cli:app"`.

Modules:

| Module | Contents |
| --- | --- |
| `compiler.py` (~6.7k lines) | `validate_spec`, `compile_module`, `reverse_module`, `close_module`, `content_signature`, every check, every parquet builder and every reverse writer |
| `resolution.py` | the injected-table resolver: `resolve_from_table`, `resolve_positional_rows`, `hosting_verdict`, `genotype_fits`, `undecided_reason`, `spelling_caveat` |
| `models.py` | `ValidationResult`, `CompilationResult`, `ClosureResult` |
| `draft.py` | append-only row drafting into authored CSVs; `DRAFTABLE`, `append_rows`, `append_partial_rows`, `authoring_requirements`, `blank_template`, `stub_template`, `place_rows` |
| `hints.py` | read-only CSV inspection: `inspect_rows`, `describe_table`, `field_options` |
| `scaffold.py` | de-novo file creation: `scaffold_module`, `module_spec_template` |
| `cli.py` | the Typer app |

---

## 2. The CLI

Fifteen commands. `just-dna-compiler` with no arguments prints help (`no_args_is_help=True`).
Exit codes: `0` success, `1` failure.

`--help` output was captured for `validate`, `compile`, `reverse` and `verify`; the rest are read off
the Typer definitions in `cli.py`.

### 2.1 `validate SPEC_DIR`

Validates without writing anything. Exit 1 if invalid.

| Flag | Default | Effect |
| --- | --- | --- |
| `--strip-identity` | off | Adds `just_dna_format.normalize.IDENTITY_AUTHORITY_KEYS` — `canonical_id`, `namespace`, `owner` — to the set of `module:` keys stripped before validation |
| `--authority-key TEXT` | `[]`, repeatable | Extra `module:` key to strip |
| `--strict` / `--best-effort` | `--best-effort` | Escalates the mode-laddered findings to errors, matching `compile --strict` |

`_authority_keys()` returns `None` when neither identity flag is given, so nothing is stripped by
default and any unknown `module:` key still trips `extra="forbid"`. Stripped keys are reported on
`.info`, printed as `info:` lines on **stdout** (errors and warnings go to stderr).

`validate_spec` has a fourth Python parameter, `resolve_with_ensembl=True`, which the CLI does **not**
expose. A `compile --no-resolve` therefore has no exact CLI pre-flight.

### 2.2 `compile SPEC_DIR OUTPUT_DIR`

| Flag | Default | Effect |
| --- | --- | --- |
| `--strict` / `--no-strict` | `--no-strict` | All-or-nothing. Escalates the mode-laddered checks, refuses on `resolve_strict_errors`, and refuses if any variant still has no `chrom`+`start` after resolution |
| `--ensembl-cache PATH` | `None` | Deprecated, removed at 1.0. Emits a `DeprecationWarning` and routes to `just_dna_enricher.resolver.resolve_variants` |
| `--resolve` / `--no-resolve` | `--resolve` | Master switch for resolution of every kind, despite the name |
| `--compression TEXT` | `zstd` | Passed straight to `DataFrame.write_parquet` |
| `--compiled-by TEXT` | `None` | `manifest.compilation.compiled_by` |
| `--strip-identity` | off | as `validate` |
| `--authority-key TEXT` | `[]` | as `validate` |

On success it prints `compiled: <dir>`, then `digest:`, `content_signature:`, a
`resolution_mode: … fully_resolved: … (over N variant row(s))` line, and `resolution_signature:` when
one was stamped.

`compile_module` has six parameters the CLI does not expose: `ensembl_reference`, `log_files`,
`provenance_file`, `logo_file`, `readme_file`, `ba1_threshold`. Log/provenance/logo/readme are still
auto-discovered, so the CLI reaches them by discovery but cannot override the paths, and
`ba1_threshold` cannot be tuned from the CLI at all.

### 2.3 `reverse PARQUET_DIR OUTPUT_DIR`

| Flag | Default |
| --- | --- |
| `--module-name TEXT` | recovered from the `module` column of the first present parquet, else the directory name |
| `--title TEXT` | `module_name.replace("_", " ").title()` |
| `--description TEXT` | `f"Annotation module: {module_name}"` |
| `--report-title TEXT` | same as `--title`'s default |
| `--icon TEXT` | `database` |
| `--color TEXT` | `#6435c9` |
| `--version TEXT` | omitted from the emitted `module:` block |
| `--resolution` / `--no-resolution` | `--resolution` |
| `--genome-build TEXT` | the artifact's `manifest.json` `genome_build`, else `GRCh38` |

A `layout.SidecarCollision` (the output directory already holds two copies of one sidecar) is caught
and printed as `  error: …` with exit 1; nothing has been written at that point, because every
sidecar destination is resolved before the first write.

### 2.4 `signature SPEC_DIR`

Prints `content_signature(spec_dir)` — the reference-independent hash over the authored rows. Raises
`ValueError` (uncaught, so a traceback) if a present data CSV fails row validation.

### 2.5 `verify MODULE_DIR`

Re-hashes the artifact against its manifest via `just_dna_format.integrity.verify_manifest`.

| Flag | Default |
| --- | --- |
| `--require-marketplace` / `--no-require-marketplace` | `--require-marketplace` (demands `compile_success` and `compiled_by=marketplace-server`) |
| `--public-key TEXT` | `None` |
| `--check-inputs` | off |
| `--check-logs` | off |
| `--check-provenance` | off |
| `--check-logo` | off |
| `--check-readme` | off |
| `--check-derived` | off |

An unreadable or absent `manifest.json` is a clean exit 1 rather than a traceback
(`_read_manifest_or_exit`). On success it prints the digest, the file count, and one of three
signature verdicts: `verified against the pinned key`, `present, self-consistent only`, or `absent`.

### 2.6 `close SPEC_DIR`

Writes a `closure` block into the module's `verification.json`, bound to the hash of the authored
bytes.

| Flag | Default |
| --- | --- |
| `--by TEXT` | `None` |
| `--private-key PATH` | `None` (must exist if given) |

Refuses (exit 1) if the spec does not validate; does **not** refuse on warnings. Prints
`closed: <path>`, the `authored bytes:` hash, and `signature: present` or
`signature: none (change-evident, not attributed)`.

### 2.7 `sign MODULE_DIR --private-key PATH`

Signs `manifest.artifact.digest` and rewrites `manifest.json` with the signature. `--private-key` is
required and must exist.

### 2.8 `keygen`

`--out PATH` (optional). With no `--out` the PEM goes to stdout and the public key to stderr; with
`--out` the file is written mode `0600` and the command **refuses (exit 1) rather than overwrite** an
existing file. Key is unencrypted PKCS#8.

### 2.9 `reference`

| Flag | Default |
| --- | --- |
| `--json` / `--summary` | `--json` |
| `--schemas` | off — emits `json_schemas()` instead of `authoring_reference()` |

`--summary` prints `schema_version:`, one line per model, then `vocabularies:`, `open/recommended:`
and `reserved names:`. `--schemas --json` is the per-model JSON Schema map; `--schemas --summary`
prints only the model names.

### 2.10 Authoring surface

| Command | Arguments and flags | Behaviour |
| --- | --- | --- |
| `template KIND` | — | Header-only CSV on stdout, `authored_field_names()` order. Requirements go to **stderr** so `template x.csv > x.csv` is clean |
| `stub KIND` | `--rows N` (default 1, min 1) | Header plus stub rows carrying `<<REPLACE>>` where a human must decide; for a binning kind the mandatory `unresolved` companion row is appended |
| `requirements KIND` | `--json` (default off) | `always` / `one of` / `default` / `optional` |
| `scaffold SPEC_DIR` | `--kind` (repeatable), `--name`, `--rows N` (default 1), `--dry-run` | Creates `module_spec.yaml` plus a stub CSV per kind. Never overwrites; a zero-byte file counts as absent |
| `describe KIND` | — | Always JSON: columns, vocabularies, requirements, natural key |
| `hint KIND` | exactly one of `--file PATH` or `--row TEXT`; `--json` | Reads CSV text, writes nothing. Corrected text to stdout, alterations and findings to stderr |

`hint` exits 1 if both or neither of `--file`/`--row` is given. Its findings are located as
`line N [column]`, 1-based and header-inclusive, matching `validate`/`compile`.

`scaffold` pulls in a companion kind: `variants.csv` drags in `studies.csv` and vice versa
(`COMPANION_KINDS`), because each alone fails to compile.

---

## 3. What a spec directory may contain

### 3.1 Authored, one legal name at the spec root

- `module_spec.yaml` — required. Fields: `schema_version`, `module`, `defaults`, `genome_build`,
  `panel`, `authorship`, `license`, `weighting`.
- `variants.csv` (`VariantRow`), `studies.csv` (`StudyRow`) — the SNP core.
- The nine optional table kinds (`_TABLE_KINDS`, in registry order):
  `activity_phenotype.csv`, `copynumbers.csv`, `repeat_alleles.csv`, `heteroplasmy.csv`,
  `haplotypes.csv`, `allele_function.csv`, `diplotypes.csv`, `pgs.csv`, `pharm_variants.csv`.

Three of the nine are *positional* — derived from the models as "declares both `chrom` and `start`":
`heteroplasmy.csv`, `haplotypes.csv`, `pharm_variants.csv`. Four are *binning* — "the model is a
`MeasureBinRow` subclass": `activity_phenotype.csv`, `copynumbers.csv`, `repeat_alleles.csv`,
`heteroplasmy.csv`. Neither list is hand-kept.

Composition rule: at least one of `variants.csv` or a table kind must be present. `studies.csv` is
required **iff** `variants.csv` is present. A present-but-rowless table kind is an error; a
present-but-rowless `variants.csv` is not (`_emptied_table_errors`' docstring states this explicitly
and calls it "measured").

### 3.2 Machine-written sidecars — two legal spellings, two legal places

`_DERIVED_FILES` = `resolution.csv`, `verification.json`, and the seven fact tables
(`frequencies.csv`, `gene_metrics.csv`, `literature.csv`, `gene_validity.csv`,
`clinical_assertions.csv`, `gwas_effects.csv`, `sources.csv`).

Each may sit at the spec root **or** under `derived/`. `sources.csv` additionally has a preferred
spelling `licensing.csv`; `sources.csv` is deprecated and reading it emits a notice naming the file
and the replacement. Two copies of one table (either two spellings, or root + `derived/`) raise
`layout.SidecarCollision`; `_locate_sidecar` turns that into an error string rather than an
exception, and it is fatal for a fact table. For `verification.json` the same collision is reported
but the outcome is only that no verification block is published.

The compiler never copies these into the output directory. They are hashed **where they are
authored**, into `manifest.derived`, and their *identity* is the fact-signature beside them, not that
byte hash.

### 3.3 Optional side assets

`provenance.json` (validated as `ProvenanceDoc`, summarized into `manifest.provenance`), `*.log` at
the root plus `logs/**/*.log`, `logo.{png,jpg,jpeg}`, and a readme from
`manifest.README_CANDIDATES` (`README.md` first). All four are **copied into the output directory**
and hashed, and all four are kept **out of `artifact.digest`**. The readme is additionally out of
`content_signature`.

### 3.4 Anything else

Tolerated silently, with one exception: `_check_misspelled_tables` warns when an unknown file is a
`difflib` near miss (cutoff 0.8) of a known name. At the spec root it inspects `.csv` and `.json`;
under `derived/` only `.csv`. An **authored** table name found under `derived/` is reported
separately as a misplaced table (exact match against the authored name set), because its rows are
being silently ignored.

---

## 4. `compile_module` end to end

Order matters and is largely dictated by one rule: everything that can refuse runs **before**
`output_dir.mkdir()`, so a refusal leaves nothing written.

1. **`validate_spec(spec_dir, authority_keys, resolve_with_ensembl=…)`** — note `strict` is
   deliberately *not* passed, so the pre-flight always runs in best-effort. Any error aborts, and the
   result's warnings seed `all_warnings`.
2. Re-load `module_spec.yaml`, `variants.csv` (with `_restamp_for_build`), `studies.csv`, and every
   present table kind. The compile re-loads its own copies rather than reusing the pre-flight's.
3. **Symbolic-allele ladder** (`_check_symbolic_alleles`). Under `strict` a finding is an error;
   under best-effort rows in `variants.csv`/`pharm_variants.csv` are **dropped** and every other
   table's finding is fatal in both modes. A drop that would empty a table outright is an error in
   both modes. After a `variants.csv` drop, `validation.stats` is recomputed with `variant_stats()`
   so the manifest cannot claim more rows than the artifact holds.
4. Locate and load `resolution.csv`. Verify every stored `vrs_id` (`_verify_vrs_ids`), compute VRS
   coverage, and — if `resolve_with_ensembl` **and** the table has rows — stamp
   `resolution_sources` and `resolution_signature`. A header-only table is deliberately not stamped.
5. `_check_allele_membership` on the **authored** rows (before expansion), then
   `_check_study_effect_alleles`, then `_check_p_value_num`. Each is a mode ladder and returns early
   on errors.
6. If `resolve_with_ensembl` is off but a table is present, emit the "master switch" warning.
7. If `resolve_with_ensembl` **and** `variants`: `resolve_from_table` (or the deprecated
   `ensembl_cache` route, or a "nothing injected" warning). `outcome.errors` are fatal in both modes;
   `outcome.strict_errors` are fatal under `strict`. Then `_cross_validate_variants` re-runs on the
   resolved rows, taking errors only.
8. `_check_contig_ploidy` and `_check_build_coordinates` on the now-final coordinates.
9. Compute `fully_resolved` and `resolution_subjects`; under `strict`, refuse if any variant still
   lacks `chrom`+`start`.
10. **Licence gate** — `_check_license_gate` over `sources.csv`/`licensing.csv`. Last refusal point
    before anything is written.
11. `output_dir.mkdir(parents=True, exist_ok=True)`.
12. Write `weights.parquet` / `annotations.parquet` (only when there are variants) and
    `studies.parquet` (only when there are studies).
13. `_apply_positional_resolution(kind_rows, …)` — the RM43 fill onto the three positional kinds —
    then write one parquet per present table kind.
14. `_check_positional_joinability` and `positional_placement`, then re-run the binning checks
    (`_check_binning_grounding`, `_check_measure_shape`, `_check_binning_deprecations`), all
    de-duplicated on the message.
15. For each entry of `_FACT_TABLES` in order: locate, load, run its check over **every** row, then
    (for `literature.csv` only) narrow to the cited rows, then write the parquet.
    `sources.csv` is last on purpose — `_sources_checks` reads the accumulated `fact_rows` to decide
    which declared sources were actually used.
16. Collect logs, provenance, logo, readme; read the verification block.
17. Build and write `manifest.json`; return `CompilationResult`.

A comment block at step 14 records three checks that are deliberately **not** re-run after
resolution — `_check_missing_allele_marker`, `_check_quality_inversion`, `_check_vcf_pointers` —
because their messages embed counts and resolution changes the row count without changing their
inputs. The stated rule: *re-run a check after resolution exactly when resolution changes its input,
and never when the message embeds a count.*

---

## 5. Output artifact layout

`ARTIFACT_PARQUETS` is the full list, in `artifact.digest` order. `build_artifact` skips absent
files, so a module's digest is over exactly the parquets it has.

```
weights.parquet
annotations.parquet
studies.parquet
activity_phenotype.parquet
copynumbers.parquet
repeat_alleles.parquet
heteroplasmy.parquet
haplotypes.parquet
allele_function.parquet
diplotypes.parquet
pgs.parquet
pharm_variants.parquet
frequencies.parquet
gene_metrics.parquet
literature.parquet
gene_validity.parquet
clinical_assertions.parquet
gwas_effects.parquet
sources.parquet
```

Nineteen names. `LEAD_PARQUETS` is the ten that carry a module's own annotation rows
(`weights.parquet` plus the nine table kinds); `just_dna_enricher.upload` imports both tuples rather
than keeping its own copy.

Beside them the output directory holds `manifest.json`, plus copies of any logs, `provenance.json`,
logo and readme. The authored CSVs and the derived sidecars are **not** copied.

### 5.1 `weights.parquet`

Hand-listed schema (not derived from `VariantRow`), 39 columns:

`rsid` Utf8, `authored_ident` List(Utf8), `variant_key` Utf8, `locus_index` UInt32, `locus_count`
UInt32, `genotype` List(Utf8), `phased` Boolean, `module` Utf8, `weight` Float64, `state` Utf8,
`priority` Utf8, `conclusion` Utf8, `negatives` Utf8, `curator` Utf8, `method` Utf8, `chrom` Utf8,
`start` UInt32, `end` UInt32, `ref` Utf8, `alts` List(Utf8), `clinvar` Boolean, `pathogenic` Boolean,
`benign` Boolean, `likely_pathogenic` Boolean, `likely_benign` Boolean, `direction` Utf8,
`stat_significance` Utf8, `effect_size` Float64, `effect_measure` Utf8, `effect_allele` Utf8,
`flags` List(Utf8), `trait_efo_id` Utf8, `clin_sig` Utf8, `requires_callable` Boolean,
`callable_from` Utf8, `acmg_sf` Boolean, `actionability` Utf8, `quality_from` Utf8,
`min_quality` Float64.

Compiler-stamped, not authored:

- `module` — the module name.
- `variant_key` / `authored_ident` — frozen at row load; `authored_ident` lists which of
  `rsid, chrom, start, ref, alts` the author actually filled.
- `locus_index` / `locus_count` — the one-to-many expansion marker. `locus_count > 1` is the
  predicate that identifies an expansion member.
- `phased` — `"|" in v.genotype`. `genotype` itself is stored as an allele list, which cannot carry
  phase.
- `end` — assigned `v.start`, unconditionally. It is always equal to `start`.
- `likely_pathogenic` / `likely_benign` — hardcoded `False` for every row. Neither is a `VariantRow`
  field, so nothing can ever set them and `reverse` does not emit them.
- `priority`, `curator`, `method` — the row value or the `defaults:` block's value.

### 5.2 `annotations.parquet`

`rsid`, `variant_key`, `genotype`, `conclusion`, `negatives`, `module`, `gene`, `phenotype`,
`category` — all Utf8. Keyed on `(variant_key, genotype, conclusion, negatives)`, first occurrence
wins. `genotype` here is the **authored cell** (`"A/G"`, `"G|A"`), not the allele list. `gene`,
`phenotype` and `category` are written as `""` rather than null when unset.

Because `(variant_key, genotype)` is `VariantRow`'s own natural key and duplicates on it are
rejected, the dedup is provably a no-op; the tests demonstrate both that the older
variant-effect key really did lose a distinction and that the shipped key keeps it
(`test_two_genotypes_sharing_one_conclusion_stay_two_annotation_rows`).

### 5.3 `studies.parquet`

`rsid`, `chrom`, `start` (UInt32), `ref`, `module`, `pmid`, `population`, `p_value`, `conclusion`,
`study_design`, `stat_significance`, `effect_size` (Float64), `effect_measure`, `effect_allele`,
`trait_efo_id`, `doi`, `provenance_quote`, `provenance_regex`, `p_value_num` (Float64),
`neg_log10_p` (Float64).

`neg_log10_p` is **derived on write** and is not a `StudyRow` field, so `reverse` cannot emit it and
the next compile re-derives an identical column.

### 5.4 The nine table-kind parquets

Built by the generic `_build_table`: a `module` Utf8 column, then every field of the model in
declaration order, typed by `_polars_type` (`bool` → Boolean, `int` → Int64, `float` → Float64,
`list[...]` → List(Utf8), everything else → Utf8). Fields are read off the row with `getattr`, not
`model_dump()`, so `exclude=True` stamped columns (`variant_key`, `authored_ident`, and the filled
`alts` on the PGx tables) do reach the parquet while staying out of `content_signature`.

### 5.5 The seven fact parquets

Six use `_build_table`. `frequencies.parquet` uses `_build_frequencies`, which is `_build_table` plus
a derived `allele_frequency` Float64 column that is not a `FrequencyRow` field — the same
derived-on-write pattern as `neg_log10_p`.

`literature.parquet` carries only the **cited** rows (`split_cited_literature`): a row whose PMID no
`studies.csv` row and no binning `pmid` names is dropped from the artifact and kept in the CSV. When
the module cites nothing at all, nothing is dropped.

### 5.6 The manifest

`_build_manifest` fills, among others:

- `identity.name`, and `identity.version` only when the authored `module.version` is already
  canonical SemVer.
- `genome_build`, `curator`, `method`, `display`, `license`, `weighting`, `panel`, `authorship`.
- `stats` from `variant_stats()` plus `weights_rows`.
- `compilation`: `compile_success`, `compiled_by`, `compiler_version`, `ensembl_reference`,
  `compiled_at`, `warnings`, `resolution_mode`, `fully_resolved`, `resolution_subjects`,
  `expanded_keys`, `expanded_rows`, `positional_rows`, `positional_rows_placed`,
  `resolution_signature`, `resolution_sources`, `vrs_alleles`, `vrs_alleles_identified`.
- `inputs` — `file_entries(spec_dir, _INPUT_FILES)` over **raw** bytes.
- `derived` — `file_entries` over every legal spelling and location of `_DERIVED_FILES`.
- `artifact` — `build_artifact(output_dir, ARTIFACT_PARQUETS)`.
- `content_signature`, `logs`, `provenance`, `logo`, `readme`, `verification`, plus the seven fact
  summary blocks (`frequency`, `gene_metrics`, `gene_validity`, `clinical_assertions`,
  `gwas_effects`, `literature`, `sources`).

Tri-state discipline in the summary blocks: `ClinicalAssertions.min_review_stars`/`max_review_stars`
are `None` when nothing is rated (0 is a real rating), `Literature.quotes_found` sums only non-null
rows, and `Sources.commercial_use`/`redistribution` are most-restrictive-first —
`False` if anything forbids, else `None` if anything is unknown, else `True`.

`expanded_keys`/`expanded_rows` are `None` unless the injected-table resolution branch ran; the
deprecated `ensembl_cache` path leaves them `None` deliberately. `positional_rows` /
`positional_rows_placed` are always computed by this compiler (`(0, 0)` for a module with no
positional table), so the `None` the field allows comes from older artifacts only.

**Note on the binding asymmetry**: `authored_input_entries()` hashes the same file set as
`manifest.inputs` but with newlines normalized, while `manifest.inputs` and `artifact.digest` follow
every byte. So rewriting a file's line endings moves the listing and leaves the attestation standing.
The `authored_input_entries` docstring states plainly that an earlier version of itself claimed the
compiler hashes these into `manifest.inputs` and that it never did.

---

## 6. Resolution

### 6.1 What `resolution.csv` supplies

`ResolutionRow` columns: `variant_key` (required), `rsid`, `chrom`, `start`, `ref`, `alts`,
`genome_build` (default `GRCh38`), `locus_index` (default 0), `vrs_id`, `vrs_spec`, `caid`, `source`,
`authority`, `status`, `rsid_alternates`, `rsid_current`, `rsid_status`, `fetched_at`. `extra` is
forbidden.

Only the first eight are `RESOLUTION_FACT_FIELDS` and feed `resolution_signature`; `source`,
`status`, `fetched_at` and the cross-reference columns are provenance and are deliberately outside
it, so a human-filled and an enricher-filled table with the same facts hash equal.

The table is keyed by the **authored** `variant_key`. A one-to-many rsID contributes several rows
under one key, distinguished by `locus_index`.

### 6.2 The SNP-core join (`resolve_from_table`)

Gate: the module must declare `GRCh38`, or the whole pass is skipped with a warning. Within a key,
`_usable_loci` keeps only rows whose `genome_build` matches, whose `status` is not `not_found`, and
which have a `chrom`.

Three shapes:

- **rsid authored, no coordinate.** No loci → warn, leave unresolved. Exactly one → fill
  `chrom`/`start`/`ref`/`alts`, keeping the frozen key. Several → filter through `_hostable_loci`;
  one survivor fills, several expand into one row per locus re-keyed by
  `derive_variant_key(None, chrom, start, ref, alts)` and stamped with `locus_index`/`locus_count`,
  ordered by `(locus_index, chrom, start, ref)`; none leaves the row unresolved.
- **coordinate authored, no rsid.** Fill `rsid` from the first locus that has one, and fill `alts`
  when the author left it empty. Nothing to fill → the row is counted into one aggregated
  "coordinate-authored row(s) have no rsid" warning.
- **both authored.** `_verify` compares the authored coordinate key against the table's; a
  disagreement warns in best-effort and is a `strict_error`.

Three severity channels: `warnings` (both modes), `strict_errors` (the round-trip contract: a dropped
locus, an authored coordinate contradicting the table, and `status == "ambiguous"`), and `errors`
(fatal in both modes — today only `rsid_status == "withdrawn"`).

**`hosting_verdict` is three-valued** and the whole expansion filter rests on it. In order: no
`ref`/`alts` → `True`; strip VCF's `*` from both sides, and if either side empties → `None`; raw set
subset → `True`; a symbolic allele on either side → `None`; reduced (parsimony-stripped) sets match →
`True`; the locus is a substitution or MNV → `False`; the call names fewer than two distinct alleles
→ `None`; the call is not indel-shaped → `False`; an event length the locus does not offer →
`False`; otherwise `None`. `genotype_fits` is the boolean face and collapses `None` to keep.
`undecided_reason` mirrors the withholding branches in the same order so the message names the cause
that was actually reached.

### 6.3 The positional join (`resolve_positional_rows`, via `_apply_positional_resolution`)

Reaches `heteroplasmy.csv`, `haplotypes.csv` and `pharm_variants.csv` — the three kinds declaring
both `chrom` and `start`. Four rules:

- fill only cells the author left empty, in place;
- fill from exactly one locus or from none — several loci are filtered by `hosting_verdict` against
  the row's stated allele (`genotype` for a pharm row, `allele` for a haplotype, nothing for a
  heteroplasmy band), and **there is deliberately no expansion**;
- a row whose own authored `rsid`/`chrom`/`start`/`ref` contradicts the chosen locus is left exactly
  as authored and reported (`alts` is excluded from that comparison on purpose);
- the row is mutated rather than copied, and `variant_key`/`authored_ident` were frozen at load, so
  the fill cannot re-key it.

`_apply_positional_resolution` returns `(warnings, applied)`. `applied` is `False` for four different
situations — no table, no positional rows, non-GRCh38, `resolve=False` — and it is threaded into
`_check_positional_joinability` so that check can say "the table was not consulted" instead of
inventing a reason.

Both the fill and the joinability report run in `validate_spec` as well as `compile_module`;
`validate_spec` first computes the symbolic-allele drop set and filters the rows, so the pre-flight
counts the rows a compile would keep.

### 6.4 With nothing injected

`resolution_table` is empty and usable empty. Allele membership then judges only rows that author
their own `ref`/`alts`; `_check_study_effect_alleles` is silent entirely; the coordinate fill does
nothing. With `variants` present and any lacking a position, one warning is emitted:

> `No resolution.csv and no ensembl_cache injected; variants lacking a genomic position are left unresolved. Produce a resolution.csv with just-dna-enricher.`

With a table present and `--no-resolve`, a different, louder warning fires (§10).

### 6.5 What resolution does **not** reach

`variants.csv` plus the three positional table kinds, and nothing else. `studies.csv`,
`repeat_alleles.csv`, `copynumbers.csv`, `activity_phenotype.csv`, `allele_function.csv`,
`diplotypes.csv` and `pgs.csv` get no coordinates. A comment at `_POSITIONAL_TABLE_KINDS` states
plainly that for `repeat_alleles.csv` and `copynumbers.csv` this is a **schema gap** rather than a
property of what they describe, and that closing it waits for 0.7+.

---

## 7. The validation surface

### 7.1 How severity works

- **error in both modes** — refuses whatever the flag.
- **mode ladder** — warning under best-effort, error under `--strict`.
- **warning in both modes** — `--strict` never escalates it. The stated rule for this class:
  `strict` means *reproducible artifact*, so a finding that is either about a different axis
  (licensing, clinical judgement) or that **no authored edit could clear** stays a warning.

`validate_spec(strict=…)` changes severity only; it never adds or removes a finding. That is asserted
by `test_validate_agrees_with_compile.py` and by the module docstring there.

`compile_module` runs `validate_spec` in best-effort regardless of its own mode, which is why every
mode-ladder check is re-run inside the compile, and why the re-runs de-duplicate on the exact message
string.

### 7.2 The checks

`V` = runs in `validate_spec`, `C` = runs in `compile_module` (a check that only runs in `validate`
still reaches the compile through `validation.warnings`).

| Check | Inspects | Severity | V | C | Notes |
| --- | --- | --- | --- | --- | --- |
| `_check_misspelled_tables` | file names at the root and in `derived/` | warning both | ✓ | via V | `difflib` cutoff 0.8; `.csv`+`.json` at root, `.csv` under `derived/` |
| yaml load | `module_spec.yaml` | error both | ✓ | ✓ | syntax error, empty file, non-mapping and pydantic errors each get their own message |
| `panel:` deprecation | `module_spec.yaml` | warning both | ✓ | via V | removed at 1.0 |
| `module.version` coercion | `module_spec.yaml` | warning both | ✓ | via V | reports what `ModuleInfo` already rewrote |
| row validation, all authored tables | every authored CSV | error both | ✓ | ✓ | surplus-column rows are reported as `more values than header columns` and skipped |
| present-but-empty table kind | each `_TABLE_KINDS` CSV | error both | ✓ | via V | `variants.csv` is exempt |
| `_validate_table_kind` — `validate_bins` | binning tables | overlap = error, coverage gap = warning | ✓ | via V | |
| `_validate_table_kind` — duplicate `unresolved` sentinel | binning tables | error both | ✓ | via V | at most one per key group |
| `_validate_table_kind` — duplicate row | `_TABLE_DUPE_KEYS` kinds | error both | ✓ | via V | keys listed in §7.3 |
| `_cross_validate_haplotype_definitions` | haplotypes vs allele_function/diplotypes | warning both | ✓ | via V | only when `haplotypes.csv` is present; `*1` exempt |
| `_cross_validate_phase_ambiguity` | haplotypes + diplotypes | warning both | ✓ | via V | two classes: identically-defined (phase does not help) and phase-ambiguous |
| row validation, injected sidecars | `resolution.csv` + all seven fact tables | error both | ✓ | ✓ | |
| `_locate_sidecar` collision | sidecar spellings/locations | error both (warning for `verification.json`) | ✓ | ✓ | |
| deprecated spelling notice | `sources.csv` | warning both | ✓ | ✓ | |
| `_verify_vrs_ids` — mismatch | `resolution.csv` | **error both** | ✓ | ✓ | a substitution's VA is deterministic offline, so a mismatch is corruption |
| `_verify_vrs_ids` — unverifiable, `_BLAME_ROW` | `resolution.csv` | error both | ✓ | ✓ | no coordinate, no ALT, or a symbolic allele carrying an id |
| `_verify_vrs_ids` — unverifiable, `_BLAME_TIER` | `resolution.csv` | warning both | ✓ | ✓ | indel/MNV, unsupported build, off-assembly, `*` |
| `_vrs_coverage_warnings` | `resolution.csv` | warning both | ✓ | ✓ | one headline line plus one per gap reason |
| `_check_license_gate` | `sources.csv` | **error both** | ✓ | ✓ | in compile it also runs as the last pre-`mkdir` refusal |
| `_verification_block` staleness | `verification.json` | warning both | ✓ | ✓ | stale ⇒ block dropped, never fatal |
| `_closure_warning` | verification block | warning both | ✓ | ✓ | carries `UNCLOSED_PHRASE` |
| `_apply_positional_resolution` contradiction | positional kinds vs `resolution.csv` | warning both | ✓ | ✓ | rows left exactly as authored |
| `_check_positional_joinability` | positional kinds | warning both, never a strict error | ✓ | ✓ | carries `UNJOINABLE_PHRASE` |
| composition (`no recognized table`) | directory | error both | ✓ | via V | |
| `studies.csv` missing / empty | directory | error both | ✓ | via V | required iff `variants.csv` present |
| `_check_p_value_num` | `studies.csv` | **mode ladder** | ✓ | ✓ | relative comparison at 1%; indefinite strings skipped |
| `_check_binning_grounding` | binning tables + `studies.csv` | warning both | ✓ | ✓ | fires only when the module records **no** study rows and some bin has no `pmid` |
| `_check_measure_shape` | binning tables | warning both | ✓ | ✓ | |
| `_check_binning_deprecations` | binning tables | warning both | ✓ | ✓ | one line per table |
| `_check_missing_allele_marker` | `alts` on every table that has one | warning both | ✓ | ✗ | deliberately not re-run — carries `MISSING_ALLELE_PHRASE` |
| `_check_symbolic_alleles` | every `ALLELE_COLUMNS` cell | ladder on `variants.csv`/`pharm_variants.csv`; **error both** elsewhere | ✓ | ✓ | best-effort drops the row; a drop that empties a table is an error in both modes |
| `_check_build_coordinates` | authored positional tables + `resolution.csv` (per row's own build) | **error both** | ✓ | ✓ (re-run post-resolution) | grouped by reason, not by row |
| `_check_vcf_pointers` | pointer columns on `variants.csv` + binning kinds | warning both | ✓ | ✗ | deliberately not re-run |
| `_cross_check_literature` | `literature.csv` vs `studies.csv` + bin `pmid`s | warning both | ✓ | ✓ | three findings: nonexistent citation, uncited row, non-commercial quote |
| `_cross_validate_variants` — inconsistent position | `variants.csv` | error both | ✓ | ✓ (post-resolution, errors only) | only positioned rows are compared |
| `_cross_validate_variants` — inconsistent `ref` | `variants.csv` | error both | ✓ | ✓ | |
| `_cross_validate_variants` — duplicate `(variant_key, genotype)` | `variants.csv` | error both | ✓ | ✓ | |
| `_cross_validate_variants` — `state`/`direction` vs `weight` sign | `variants.csv` | warning both | ✓ | ✗ | post-resolution pass takes errors only |
| `_check_quality_inversion` | `requires_callable` + `quality_from` | warning both | ✓ | ✗ | carries `QUAL_INVERSION_PHRASE` |
| `_check_allele_membership` | genotype and `effect_allele` vs the locus | **mode ladder** | ✓ | ✓ | run on authored rows, before expansion |
| `_check_study_effect_alleles` | `StudyRow.effect_allele` vs resolved alleles | **mode ladder** | partial — see §13.1 | ✓ | resolved evidence only; silent under `--no-resolve` |
| `_check_genotype_coverage` | authored genotypes per site | warning both | ✓ | ✗ | only sites with ≥2 authored genotypes; message embeds counts |
| `_check_contig_ploidy` | `chrom` ∈ {MT, Y} with a two-allele genotype | warning both | ✓ | ✓ (post-resolution) | X excluded; Y PAR is three-valued via `in_pseudoautosomal_region` |
| non-reserved `flags` | `variants.csv` | **info** | ✓ | via V | reserved tags are `conditional`, `phased`, `pleiotropic` |
| `_cross_validate_studies` orphan / duplicate | `studies.csv` vs `variants.csv` | warning both | ✓ | ✗ | a study naming no variant is not an orphan |
| resolution `withdrawn` rsID | `resolution.csv` | **error both** | ✗ | ✓ | |
| resolution `ambiguous`, dropped locus, authored/table contradiction | `resolution.csv` | mode ladder (strict_errors) | ✗ | ✓ | |
| strict unresolved-position gate | `variants.csv` post-resolution | strict only | ✗ | ✓ | |
| `_check_frequency_arithmetic` — integer impossibilities | `frequencies.csv` | **error both** | ✗ | ✓ | see §13.2 |
| `_check_frequency_arithmetic` — `faf95` above the point estimate | `frequencies.csv` | warning both | ✗ | ✓ | |
| `_cross_check_frequencies` | `frequencies.csv` vs variants | warning both | ✗ | ✓ | position-level match |
| `_check_ba1_lint` | `frequencies.csv` vs pathogenic variants | warning both | ✗ | ✓ | threshold 0.05, overridable via API only |
| `_check_gene_metrics_arithmetic` | `gene_metrics.csv` | warning both | ✗ | ✓ | |
| `_cross_check_gene_metrics` | `gene_metrics.csv` vs variant genes | warning both | ✗ | ✓ | |
| `_cross_check_gene_validity` | `gene_validity.csv` vs variant genes | warning both | ✗ | ✓ | |
| `_cross_check_clinical_assertions` | `clinical_assertions.csv` vs variant positions | warning both | ✗ | ✓ | |
| `_cross_check_gwas_effects` | `gwas_effects.csv` vs `variant_key`/`rsid` | warning both | ✗ | ✓ | key-matched, not position-matched, because the row carries no coordinates |
| `_source_checks` orphan / undeclared | `sources.csv` vs fact tables' `source` | warning both | ✗ | ✓ | `annotation` and `literature` layers are exempt from the orphan half |
| `_check_declared_license_agrees` | yaml `license:` vs annotation-layer rows | warning both | ✗ | ✓ | string equality only, never adjudicated |
| provenance / logo / readme validation | side assets | error both | ✗ | ✓ | `validate_spec` does not read them |

### 7.3 Duplicate-row keys (`_TABLE_DUPE_KEYS`)

| Model | Key |
| --- | --- |
| `HaplotypeRow` | `(haplotype_name, variant_key, allele)` |
| `AlleleFunctionRow` | `(gene, allele)` |
| `DiplotypeRow` | `(gene, haplotype_a, haplotype_b, trait_efo_id, drug, clinical_context)` |
| `PgsRow` | `(pgs_id, trait_efo_id)` |
| `PharmVariantRow` | `(variant_key, drug, genotype, phenotype_category, annotation_id)` |

Binning kinds are absent by design: their duplicate rule is bin *overlap*, checked by
`validate_bins`. The SNP core's keys live in `draft._CORE_DUPE_KEYS`:
`VariantRow → (variant_key, genotype)`, `StudyRow → (variant_key, pmid)`,
`SourceRow → (source, layer)`.

---

## 8. `reverse_module`

Reads a compiled parquet directory and writes an authored spec tree. It never fetches and never reads
the original spec.

Reconstructed:

- `module_spec.yaml` — `schema_version: "1.0"`, a `module:` block, `defaults: {curator, method}` and
  `genome_build`. `genome_build` comes from the argument, else the artifact's own `manifest.json`,
  else `"GRCh38"`.
- `variants.csv` from `weights.parquet` + the `annotations.parquet` lookup, when `weights.parquet`
  exists.
- `studies.csv` from `studies.parquet`.
- One authored CSV per present table-kind parquet, via `_write_table_csv`.
- `resolution.csv`, rebuilt from `weights.parquet` **and** the positional parquets (unless
  `--no-resolution`).
- One CSV per present fact parquet, written through `layout.sidecar_write_path` so a fresh tree gets
  `licensing.csv` and an existing tree's copy is overwritten in place.

### 8.1 What reverse normalizes rather than preserves

- **Column order and cell formatting.** Each writer has a fixed `fieldnames` list; `_scalar_cell`
  renders `None → ""`, `True/False → "true"/"false"`, and an integer-valued float as a bare int
  (`40.0 → "40"`). `_list_cell` pipe-joins list columns.
- **Genotype spelling.** `weights.parquet` stores an allele list plus a `phased` bit. A phased pair
  is re-emitted `a|b` in stored order; an unphased pair is re-emitted **alphabetically sorted** with
  `/`; a single allele passes through. `test_a_phased_genotype_still_finds_its_annotation` notes that
  the model rejects an unsorted unphased pair on load, so sorting loses nothing.
- **`curator` / `method`.** The module default is *inferred* as the most common non-null value
  (`_most_common`, with `min()` as the deterministic tie-break), written into `defaults:`, and every
  row equal to it emits a blank cell.
- **Identity columns.** `_write_variants_csv` and `_write_table_csv` emit only the identity columns
  named in `authored_ident`. A resolved coordinate on an rsid-authored row is written to
  `resolution.csv`, not back into `variants.csv`. This is what keeps `content_signature` stable across
  a round trip.
- **Expansion collapse.** N artifact rows sharing one `authored_ident` key collapse back to the
  single authored row (`emitted_authored_keys`).
- **Provenance in `resolution.csv`.** `source` becomes `"reversed"`, `status` becomes `"resolved"`,
  `fetched_at` is emptied. `locus_index` prefers the stored column and falls back to the smallest
  unused ordinal per key.

### 8.2 Known lossy edges

Stated in the code as deliberate, not as bugs:

- `resolution.csv` loses `rsid_alternates`, `rsid_current`, `rsid_status`, `vrs_id`, `vrs_spec`,
  `caid` and `authority` — none of them reaches any parquet, so there is nowhere to recover them
  from. `_write_resolution_csv` records that this was once filed as a bug about `rsid_alternates`
  and is not one.
- A `resolution.csv` row about a variant the module does not carry, or an unplaced one-to-many, has
  nowhere to come back from. `test_resolution_matrix.Case.table_says_more` pins exactly this: only
  `resolution_signature` may move, and `artifact.digest` and `content_signature` must not.
- `verification.json` is not re-emitted. `reverse_module` logs a warning through the stdlib logger —
  the only thing it can say, since it returns a bare `Path` — and the wording branches on whether the
  dropped block carried checks, a closure, or both.
- Uncited `literature.csv` rows were already dropped at compile, so a reversed copy carries the kept
  rows only. Described as a deterministic narrowing that converges: lap two discards nothing.
- `module_spec.yaml` loses `license:`, `weighting:`, `panel:`, `authorship:`, `defaults.priority`,
  and `module.version` unless `--version` is supplied. `title`/`description`/`report_title`/`icon`/
  `color` are **fabricated** from the module name and the flag defaults.
- Logs, `provenance.json`, logo and readme are not re-emitted.
- `neg_log10_p` and `allele_frequency` are omitted by construction (they are not model fields), and
  the next compile re-derives them identically.
- A module with no `weights.parquet` that resolved nothing gets **no** `resolution.csv` at all; a
  module with a `weights.parquet` always gets one, even if empty of rows.

---

## 9. Round-trip and idempotency, as the tests exercise them

Three signatures, answering three questions:

| Signature | Question | Where |
| --- | --- | --- |
| `artifact.digest` | are the compiled bytes the same? | `manifest.artifact.digest` |
| `content_signature` | is it still the same *authored* module? | `manifest.content_signature` |
| `resolution_signature` | do the injected facts survive being written back out? | `manifest.compilation.resolution_signature` |

**`test_resolution_matrix.py`** enumerates 22 cases over the five identity columns crossed with what
the table says, and pins one rule:

> Every combination is either round-trip stable on all three signatures, or it fails in `strict`.

`test_the_contract_itself_holds` asserts that no case can be declared unstable *and* strict-clean.
`test_artifact_digest_never_moves` asserts the digest is a fixed point for **every** case, including
the unstable ones. `ambiguous` is the one deliberate exception in the other direction — stable, but
refused by `strict` because the label is a deterministic pick rather than a fact.

Cases declared unstable (and therefore strict-refusing): a dropped locus in an expansion, a
`not_found` row, an authored `ref` or coordinate contradicting the table, and "every candidate locus
contradicts the genotype".

**`test_reference_examples_roundtrip.py`** discovers all sixteen `reference_examples/` modules and
runs `compile → reverse → compile → reverse → compile`. It asserts the reversed spec re-validates,
that `(digest, content_signature)` is a fixed point from the first lap, that `resolution_signature`
is a fixed point from the second, that the declared build survives into the reversed yaml, that each
example compiles **and validates** under `--strict`, and that the corpus covers more than one genome
build.

The first-lap `resolution_signature` has a documented, derived exemption: a module declaring GRCh37
has its positional fill skipped, so its coordinates never reach a parquet and reverse cannot rebuild
the injected rows. The exemption is keyed on `manifest.genome_build == "GRCh38"`, not on a module
name list.

**`test_roundtrip_regressions.py`** pins the shapes that used to round-trip wrongly: a position-only
variant keeping its annotation, a position-only study row keeping an identifier, a partially-set
`priority` not being fabricated for rows that never set one, an authored `pathogenic=false` staying
`False` and not collapsing to `None`, `callable_from` staying absent when absent, `neg_log10_p` being
in the parquet and absent from the reversed CSV, and `annotations.parquet` keeping two rows for two
genotypes that share a conclusion.

---

## 10. Ordering guarantees

**Preserved:**

- Authored row order, through compile → reverse → recompile. Parquet bytes depend on it, so it is
  load-bearing for `artifact.digest`.
- Expansion order within a one-to-many rsID: `_sorted_loci` sorts on
  `(locus_index, chrom or "", start or 0, ref or "")`, matching the deprecated DuckDB path's
  `ORDER BY id, chrom, start, ref` so the two produce byte-identical parquet.
- `_symbolic_findings` sorts on `(table, reason, index, column)` so the messages built from it are
  byte-stable — findings reach `manifest.compilation.warnings`, which is artifact-visible.
- `binning_citations` returns first-occurrence order rather than sorted order, because it feeds
  emission order.
- `Frequency.populations` is in canonical order (`population_sort_key`, `global` first) rather than
  alphabetical; every other manifest facet list is sorted.
- `_write_resolution_csv` emits weights first and never re-emits a key from the positional pass, so
  `variants.csv`'s `alts` always wins.

**Normalized, not preserved:** column order and cell formatting in every reversed CSV; the
`curator`/`method` blank-vs-explicit split; unphased genotype allele order.

**Deterministic tie-breaks where a library gives none:** `_module_name_from_parquets` uses `min()`
over `unique()` because polars' `unique()` order is unstable; `_most_common` uses `min()` over
`mode()` for the same reason.

---

## 11. Warning texts a consumer might key on

Three fragments are named constants precisely because a manifest carries the prose and no field.

```python
UNJOINABLE_PHRASE = "have no chrom+start"
QUAL_INVERSION_PHRASE = "QUAL means the opposite thing on the record this row is read from"
MISSING_ALLELE_PHRASE = "is VCF's MISSING marker, not an allele"
UNCLOSED_PHRASE = "records no closure"
```

`UNJOINABLE_PHRASE` carries a documented external consumer: the comment states that
`just-dna-registry` 0.11.3 pins `UNJOINABLE_MARKER = "have no chrom+start"` in its facet builder. The
structured replacement (`manifest.compilation.positional_rows` / `positional_rows_placed`) shipped in
0.6, but the phrase is explicitly **not** retired, because artifacts published under 0.5 carry
neither field.

Full sentences worth quoting exactly:

Positional joinability, as the format string in `_check_positional_joinability` (no example is
invented here — the counts and the `{detail}` clause are computed per table):

```
{csv_name}: {unplaced} of {rows} row(s) have no chrom+start, so this table joins by rsID only —
a VCF whose ID column is empty matches none of them. {detail}.{partial_note}
```

`{detail}` is one of exactly three sentences:

- `the resolution table was not consulted for this table — see the skip reported above`
  (or `resolution.csv names N of them and was not consulted for this table — …`);
- `no resolution.csv row places them — run \`just-dna-enricher enrich\` first`;
- `resolution.csv names N of them, but at more than one locus or at one the row's own allele
  contradicts, so the compiler leaves them unplaced rather than picking`.

The closure reminder:

> `This module records no closure: nothing in it states that authoring is finished, so a consumer cannot tell a spec still being edited from one its author considers done. Run \`just-dna-compiler close <spec-dir>\` when the module is complete — closing is a deliberate act, it is never stamped by a passing check, and editing any authored file afterwards drops the closure again. Compiling without one is a warning today; requiring it is filed for 1.0 (RM73).`

`--no-resolve` with a table present:

> `--no-resolve (resolve_with_ensembl=False) switches off resolution entirely, including the injected resolution.csv beside this spec (N row(s), covering M variant key(s)), which was not read — every variant will compile with no chrom/start and match no VCF. The flag names Ensembl but is the master switch; drop it to use the injected table. There is no flag for 'do not reach the network' because the compiler never does (CONSTITUTION P2) — omitting this one is that request.`

Nothing injected:

> `No resolution.csv and no ensembl_cache injected; variants lacking a genomic position are left unresolved. Produce a resolution.csv with just-dna-enricher.`

VRS coverage headline, as its format string, followed by one indented line per gap reason
(`  {count} allele(s): {reason}`), sorted by descending count then reason:

```
VRS allele identity covers {identified}/{alleles} allele(s) in resolution.csv ({pct}) —
{missing} carry no ga4gh:VA. id. Anything keying on the VA sees only the covered fraction.
```

Symbolic-allele drop (best-effort, droppable table):

> `Those row(s) are DROPPED from the compiled artifact — reverse will not re-emit them — and --strict refuses instead.`

Licence gate refusal:

> `licensing: ['cpic'] contribute annotation-layer content under terms that forbid sale, and this module records no non-commercial declaration for them. Re-run the enricher with a declared use (\`--use non-commercial\`) to record one, or remove the affected content. Declaring it is an assertion about how the module will be used — the compiler records that assertion, it does not verify it.`

`test_validate_agrees_with_compile.py` additionally pins these substrings as contract:
`"forbid sale"`, `"does not match the id recomputed"`, `"could not be verified"`,
`"p_value_num says"`, `"not among the"`, `"IUPAC ambiguity code"`, `"not valid YAML"`,
`"must be a mapping"`. `test_strict_compile.py` pins `"unresolved genomic positions"`.
`test_roundtrip_regressions.py` pins `"pointer, not an expression"`.

---

## 12. Places where a name misleads

- **`resolve_with_ensembl` / `--resolve`** is not about Ensembl. It is the master switch for
  resolution of every kind, including the injected `resolution.csv`. The code says so and emits a
  warning for the combination that cannot be intended. Renaming is deferred because the parameter is
  a published signature.
- **`--ensembl-cache`** does not use a cache in this tier at all; it imports the enricher.
- **`sources.csv`** is the deprecated spelling; `licensing.csv` is preferred. But the *parquet* is
  `sources.parquet`, the manifest key is `sources`, and `_FACT_TABLES` still names `sources.csv`.
  `reverse` writes `licensing.csv` into a fresh tree, so the reversed spec's filename differs from
  the artifact's parquet name.
- **`weights.parquet` `end`** is always equal to `start`. It is not an interval end.
- **`likely_pathogenic` / `likely_benign`** in `weights.parquet` are always `False`. They are not
  authored fields and nothing can set them.
- **`_load_csv_rows`** is an alias for the public `load_csv_rows`; both names exist and are
  imported across package boundaries.
- **`_check_binning_grounding`** does not check that bins are grounded in general — it fires only
  when the module records **no** `studies.csv` rows at all.
- **`content_signature(spec_dir)`** is reference-independent but **not** build-independent: the
  declared `genome_build` is hashed into it.
- **`hosting_verdict`'s "1. no `ref`/`alts` recorded → `True`"** means a locus with no allele
  information never rejects anything, so a sparse `resolution.csv` silently widens what expands.

---

## 13. Confirmed defects

Each was reproduced by running the shipped API against a throwaway spec.

### 13.1 `_check_study_effect_alleles` is not reached by `validate_spec` for a module without `variants.csv`

In `validate_spec` the call sits inside `if variants:` (compiler.py ~3718). In `compile_module` it is
called unconditionally (~4089). A module with a table kind + `studies.csv` + `resolution.csv` and no
`variants.csv` is a legal composition, and it is exactly the fixture shape
`test_validate_agrees_with_compile.py` uses.

Reproduced with `diplotypes.csv` + a `studies.csv` row carrying `effect_allele=G` + a
`resolution.csv` row placing `rs334` at `11:5227002 T>A`:

```
strict=False  validate.valid=True   compile.success=True
              validate warns: (none)
              compile  warns: "rs334 (PMID 16199547): effect_allele 'G' is not among the resolved alleles ..."
strict=True   validate.valid=True   compile.success=False
              compile  errors: same sentence
```

So `validate --strict` reports valid for a module `compile --strict` refuses — the exact failure the
parity test module exists to prevent, and it also means the best-effort warning never appears in the
pre-flight.

### 13.2 `_check_frequency_arithmetic`'s integer errors are compile-only

`validate_spec` loads `frequencies.csv` rows and validates them per row, but only `ResolutionRow`,
`LiteratureRow` and `SourceRow` get their self-checks there. `_check_frequency_arithmetic` returns
**errors** (allele count exceeding allele number; homozygote count implying more alleles than
counted) and runs only inside the fact-table loop in `compile_module`.

Reproduced with `frequencies.csv` carrying `allele_count=500, allele_number=100`:

```
validate.valid = True   errors: []
compile.success = False errors: ['frequencies.csv [rs334 / global]: allele_count 500 exceeds
                                 allele_number 100 — a count cannot be larger than its own denominator']
```

Same class as 13.1 and as the four cases the parity test file was written for.

### 13.3 The p-value warning is published twice into `manifest.compilation.warnings`

`compile_module` seeds `all_warnings` from `validate_spec`'s result and then re-runs
`_check_p_value_num` to reach the strict severity. Every neighbouring re-run filters with
`if w not in all_warnings`; this one (compiler.py ~4097) is a bare `all_warnings.extend(...)`.

Reproduced with `studies.csv` carrying `p_value=1.2e-14, p_value_num=1.2e-41`:

```
compile.success = True
occurrences of the p_value warning in compile warnings: 2
in manifest.compilation.warnings: 2
total warnings: 3   unique: 2
```

The code's own comments treat a duplicated sentence in that published field as a defect (see the
`_check_contig_ploidy` and `_verify_vrs_ids` dedup comments, and the three-checks-not-re-run block).

### 13.4 Internal inconsistencies (not behavioural)

- `_write_variants_csv` declares `emitted_authored_keys: set[str]` and stores 4-tuples in it.
- `_check_genotype_coverage` declares `by_reason: dict[str, list[str]]` and appends
  `(site_key, spelled)` tuples.
- `_recompute_vrs_id` returns `_BLAME_TIER` for the unobservable-allele (`*`) branch while the
  symbolic branch beside it returns `_BLAME_ROW`; the comment on the `*` branch says
  "`_BLAME_TIER` matches the symbolic branch above", which it no longer does — the symbolic branch
  was escalated to `_BLAME_ROW` and the comment was not updated. Severity therefore differs (warning
  vs error) between two branches the comment claims are aligned. Whether that difference is intended
  is arguable both ways; the *comment* is definitely stale.
- `hints._validate_row` and `draft.PartialRow.validation_errors` both catch bare `Exception` with a
  `# pydantic ValidationError` comment, then call `getattr(exc, "errors", list)()`. A non-pydantic
  exception is silently reshaped rather than propagated.

---

## 14. Undetermined from code

- **Why `close_module` discards `validate_spec`'s warnings on the success path** while the failure
  path returns them (filtered on `UNCLOSED_PHRASE`). The asymmetry is not explained anywhere in the
  function or the result model.
- **Whether a stored `vrs_id` on an unobservable (`*`) allele should be `_BLAME_ROW`.** The symbolic
  branch records the identical question as "a real open question, deliberately not answered here"
  and then answers it (escalating to `_BLAME_ROW`); the `*` branch was left at `_BLAME_TIER` with a
  comment implying the two agree. Which is intended is not derivable.
- **Whether `end` in `weights.parquet` is meant to become a real interval end.** It has been
  `v.start` since it was introduced and no consumer of it appears in this tier.
- **Whether `likely_pathogenic` / `likely_benign` are a retired feature or a reserved shape.** They
  are hardcoded `False`, have no authored source, and are not in the reverse writer's field list.
- **What `compression` values are supported.** The string is passed straight to polars; nothing
  validates it and no test exercises anything but the `zstd` default.
- **Whether `validate` should expose `--no-resolve`.** `validate_spec` takes the parameter and
  `compile_module` threads it through, but the CLI does not offer it; the code comments argue at
  length that the pre-flight must not be more optimistic than the compile, which the CLI gap
  reintroduces for `--no-resolve` users.
- **Whether `manifest.compilation.positional_rows` can ever legitimately be `None` from this
  compiler.** `positional_placement` always returns a pair, so the `None` the field permits is
  presumably for older artifacts, but nothing states that.
- **What `vrs_spec` is used for.** It is a `ResolutionRow` column, loaded and validated, but no code
  path in the compiler reads it.
- **How a caller is expected to discover `hint`'s `--row` quoting rules.** The inline form wraps the
  argument as `f"{row}\n"` and `_parse` decides whether a header was supplied by testing whether the
  first line's fields are a subset of the model's authored field names — a single data row whose
  cells happen to be column names would be misread as a header. No test covers that shape.
