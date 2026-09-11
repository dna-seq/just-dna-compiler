# `just-dna-format` — a reference re-derived from code and tests alone

**Provenance of this document.** Written against a detached worktree at
`scratchpad/wt-schema` with `docs/`, `CLAUDE.md`, `AGENTS.md`, `README.md` and `reference_examples/`
removed. The only sources read were `schema/src/just_dna_format/**`, `schema/tests/**`,
`schema/pyproject.toml`, the workspace-root `pyproject.toml`, and — for the single question "who
consumes this model" — an import grep over `compiler/src` and `enricher/src`. Nothing here is
sourced from the maintained documentation. See **§13 Contamination statement**.

Package version at the commit read: `just-dna-format` **0.7.0** (`schema/pyproject.toml:3`).
Runtime floor `>=3.13`; declared dependencies are exactly `pydantic>=2.12.5` and
`cryptography>=44.0.0` (`schema/pyproject.toml:6,13-16`). Dev group: `pytest>=9.0.3`
(`schema/pyproject.toml:23-26`). The workspace root declares three members — `schema`, `compiler`,
`enricher` (`pyproject.toml:1-2`).

Line citations are `file.py:LINE` relative to `schema/src/just_dna_format/` unless a path is given.

---

## Contents

1. Module map
2. Authored row models, field by field
3. The manifest models
4. The hash family
5. The tri-state inventory
6. The allele grammar
7. Identity
8. Derived-fact tables, sidecars, and the release/verification/overlay/resolution models
9. Vocabularies
10. Everything else the code owns
11. Defect candidates
12. Undetermined from code
13. Contamination statement

---

## 1. Module map

Thirty-two modules in `just_dna_format` (`ls schema/src/just_dna_format/*.py` → 32 including
`__init__.py`). One line each, from the module docstring plus its top-level symbols.

| Module | Lines | Owns |
| --- | --- | --- |
| `__init__.py` | 15 | Docstring only. No re-exports — "Import from the submodules directly" (`__init__.py:9`). |
| `aggregate.py` | 50 | Cross-version provenance/log union across several manifests: `aggregate_logs` (15), `aggregate_provenance` (29). |
| `alleles.py` | 496 | Reference-free allele algebra: nucleotide/symbolic/missing/unobservable grammar, genotype splitting, parsimony reduction, event profiles, reverse-complement and strand-flip explanation. |
| `assertions.py` | 265 | `ClinicalAssertionRow` — the clinical-assertion sidecar (`clinical_assertions.csv`). |
| `base.py` | 904 | `AuthoredModel` (the shared base for every authored row), the field-marker vocabulary (`COMPILER_MANAGED`, `OUTSIDE_CONTENT_IDENTITY`, `vocabulary()`, `since()`), `derive_variant_key`, `merge_key`, `field_category`, genotype grammar, stamped positional identity. |
| `binning.py` | 1138 | The measure→phenotype binning primitive: `MeasureBinRow` and its four subclasses, the tiling algebra, bin-overlap/gap validation, VCF measurement-shape warnings, deprecation warnings. |
| `concordance.py` | 403 | `ClinSigConcordanceRow` + `ClinSigAuthorityCallRow` — the paired clin-sig concordance sidecars. |
| `derive.py` | 119 | Legacy→0.3 column derivations (`state`↔`direction`/`stat_significance`, ClinVar booleans↔`clin_sig`). Imports nothing from `spec`, so it is a leaf both `spec` and external consumers can use. |
| `expression.py` | 366 | `ExpressionEffectRow` — the per-(variant, gene) predicted-expression sidecar. |
| `findings.py` | 141 | `CodedWarning` — a `str` subclass carrying the warning code its emission site named (`findings.py:27`), plus `restate` (79) and `classify` (94). Not a pydantic model. |
| `frequency.py` | 241 | `FrequencyRow` — the population allele-frequency sidecar. |
| `gene_metrics.py` | 336 | `GeneMetricsRow` — the gene-constraint sidecar, plus `normalize_constraint_flags`. |
| `gene_validity.py` | 415 | `GeneValidityRow` — the gene–disease validity sidecar, plus the currency classifier (`classify_currency`, `superseded_groups`, `undecidable_groups`). |
| `gwas.py` | 342 | `GwasEffectRow` — the GWAS-effect sidecar. |
| `identity.py` | 98 | Module identity and versioning: name/namespace patterns, `Version`, `parse_version`, `canonical_id`, `version_from_legacy`, `latest`. |
| `integrity.py` | 617 | SHA-256 primitives, `artifact_digest`, `content_signature`, `fact_signature` + the per-sidecar wrappers, `verify_manifest`, `verify_signature`. |
| `layout.py` | 249 | Where sidecars live and what they may be called: spellings, collision detection, `resolve_sidecar`, `sidecar_write_path`, atomic writers. |
| `literature.py` | 294 | `LiteratureRow` — the citation sidecar. |
| `manifest.py` | 1858 | The `manifest.json` contract — every block model, `ModuleManifest`, `read_manifest`/`write_manifest`, display vocabularies. |
| `normalize.py` | 285 | Pre-validation normalization the *consumer* injects: authority-key stripping/rejection, `normalize_version`, `parse_p_value`, UTC timestamp helpers. |
| `overrides.py` | 968 | `OverrideRow` — the authored overlay on top of a derived table, and the overlay application machinery. |
| `pgs.py` | 126 | `PgsRow` — the polygenic-score declaration table. |
| `pgx.py` | 630 | Star-allele PGx: `HaplotypeRow`, `AlleleFunctionRow`, `DiplotypeRow`, `PharmVariantRow`. |
| `reference.py` | 332 | `authoring_reference()` / `json_schemas()` — the machine-facing DSL description generated from the live models, and the `_ALL_MODELS` registry. |
| `release_records.py` | 999 | `DeclaredChange` / `ReleaseRecord` / `RecompileAnswer` — what a release changed about compiled output, answered with Kleene logic. |
| `resolution.py` | 271 | `ResolutionRow` — the injected rsid↔coordinate resolution table. |
| `signing.py` | 65 | Ed25519 key generation and `sign_digest` over `artifact.digest`. |
| `sources.py` | 291 | `SourceRow` — the licensing table, plus `taints_commercial_use` / `taints_redistribution`. |
| `spec.py` | 1411 | The authored DSL: `ModuleSpecConfig`, `ModuleInfo`, `Defaults`, `VariantRow`, `StudyRow`, PMID/PMCID/DOI extraction. |
| `verification.py` | 375 | The verification attestation: binding, proof-of-work, `close`/`attest`, `merge_records`, read/write. |
| `vocab.py` | 1520 | Every shared constrained vocabulary, identifier pattern and reusable validator helper. |
| `vrs.py` | 812 | GA4GH VRS allele identity, contig geometry (lengths, PAR, refget accessions), build inference. |

### Tests that do not exercise the package's own surface

`schema/tests/` holds 44 test modules. Three of them test repository tooling rather than the format
tier and could not be run in this worktree because the trees they read were deleted:
`test_doc_links.py`, `test_rm_allocator.py`, `test_triage_tools.py`. They are named here so a peer
comparison does not read their absence as a gap in coverage of the format.

---

## 2. Authored row models, field by field

### How to read these tables

Everything below is machine-read off the live models (`pydantic` `model_fields`) rather than
transcribed, using `just_dna_format.base.field_category`, `field_first_seen` and
`field_vocabularies`.

* **req** is the *three*-way split `base.field_category` (`base.py:167`) defines, not pydantic's
  two-way `is_required()`:
  * `required` — `is_required()` is true;
  * `defaulted` — has a default and the annotation does **not** admit `None` (so an empty CSV cell,
    which a loader turns into `None` while keeping the key, fails on *type*; the cell must be written
    out with its default);
  * `optional` — has a default and admits `None`.
  `base.accepts_none` (`base.py:162`) is the predicate. The docstring records that the compiler's
  `draft` and `reference.authoring_reference` had drifted into disagreeing about this, and that both
  now read this one function.
* **first_seen** is the release stamped on the field itself by `base.since()` (`base.py:255`), read
  back by `base.field_first_seen` (`base.py:285`). It is per *(model, field)* — `curator` reads
  `0.2.0` on `VariantRow` and `0.6.5` on `StudyRow`. `schema/tests/test_first_seen.py` asserts an
  equality over the walked registry, so a new column cannot omit it.
* **vocabulary** is the `base.vocabulary()` marker (`base.py:189`) — `name`, sorted `options`,
  `closed`, and optional per-member `notes`. `closed=True` means a validator rejects anything
  outside; `closed=False` means the members are recommendations and a novel value is legal.
  `field_vocabularies` (`base.py:300`) reports both binding sites: a marker on the field itself, and
  a field whose vocabulary is enforced by `AuthoredModel`'s shared validators via
  `SHARED_VOCABULARIES` (`base.py:229`).
* **notes** carries `marks=compiler_managed` (`COMPILER_MANAGED`, `base.py:80`),
  `marks=outside_content_identity` (`OUTSIDE_CONTENT_IDENTITY`, `base.py:94`), `exclude=True`, and
  pydantic constraint metadata.

### The shared base: `AuthoredModel` (`base.py:630`)

Every authored row model inherits it; no authored model inherits `BaseModel` directly.
`model_config = ConfigDict(extra="forbid")` (`base.py:633`).

Class-level declarations it defines:

| ClassVar | Default | Meaning |
| --- | --- | --- |
| `ALLELE_COLUMNS` | `()` | which of this model's columns hold an allele **sequence** (`base.py:647`). Deliberately excludes star-allele *names* and pure pointers. |
| `REQUIRED_ANY_OF` | `()` | alternative column sets, any one of which satisfies identity — machine-readable alongside the `model_validator` that enforces it (`base.py:703`). |
| `_KEY_INCLUDES_ALTS` | `None` | tri-state: `None` = stamps no positional identity; `False`/`True` = stamp one, with/without `alts` in the key (`base.py:718`). |
| `_genome_build` | `PrivateAttr("GRCh38")` | the module's assembly, injected by the loader via `with_genome_build()` (`base.py:663`, `671`). A **private attribute**, so it is absent from `model_fields`, from `model_dump()`, from every CSV and parquet, and `extra="forbid"` still rejects it as a column. |

Validators it contributes:

| Validator | Mode | Behaviour |
| --- | --- | --- |
| `_guard_raw_input` | before | Runs four raw-dict guards in this order (`base.py:722`): `reject_template_placeholders` → `reject_misplaced` → `reject_compiler_filled` → `reject_reserved`. Each gives a specific diagnosis; anything left falls through to `extra="forbid"`'s generic message. |
| `_validate_rsid` | field, `rsid` | `vocab.validate_rsid` |
| `_validate_trait_efo_id` | field, `trait_efo_id` | `vocab.validate_trait_ids` |
| `_validate_shared_vocabulary` | field: `direction`, `clin_sig`, `stat_significance`, `evidence_level`, `source_element` | `check_vocab(v, SHARED_VOCABULARIES[name], name)` — the validator and the marker a tool reads are the same object (`base.py:757`). |
| `_validate_effect_size` | field | `validate_finite` |
| `_validate_vcf_field_pointer` | field: `source_field`, `callable_from`, `quality_from` | `validate_field_token` |
| `_validate_pointer_companions` | after | an element rule with no pointer beside it is refused; a pointer with no element rule is fine (the converse would break every existing module) (`base.py:775`). |
| `_validate_genotype` | field, `genotype` | the genotype grammar — see §6. |
| `_freeze_stamped_identity` | after | `stamp_identity(..., freeze_authored=True)` for models with `_KEY_INCLUDES_ALTS is not None`. |

All field validators use `check_fields=False`, so a subclass runs only the ones for fields it
actually declares (`base.py:12-17`).

### `VariantRow` — `variants.csv`

#### `VariantRow` — `spec.py:447`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': ('ref', 'alts', 'genotype', 'effect_allele'), 'REQUIRED_ANY_OF': (frozenset({'rsid'}), frozenset({'start', 'chrom'})), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('variant_key', 'genotype')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `rsid` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.2.0 | `chromosome` closed=True: `1`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`, `2`, `20`, `21`, `22`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `MT`, `X`, `Y` | — |
| `start` | `int | None` | optional | `None` | 0.2.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `alts` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `variant_key` | `str | None` | optional | `None` | 0.4.0 | — | marks=compiler_managed |
| `authored_ident` | `list[str] | None` | optional | `None` | 0.5.0 | — | marks=compiler_managed |
| `locus_index` | `int | None` | optional | `0` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `locus_count` | `int | None` | optional | `1` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `genotype` | `str` | required | — | 0.2.0 | — | — |
| `weight` | `float | None` | optional | `None` | 0.2.0 | — | — |
| `state` | `str` | required | — | 0.2.0 | `state` closed=True: `alt`, `neutral`, `protective`, `ref`, `risk`, `significant` | — |
| `conclusion` | `str` | required | — | 0.2.0 | — | — |
| `negatives` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `priority` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `gene` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `phenotype` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `category` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `clinvar` | `bool | None` | optional | `None` | 0.2.0 | — | — |
| `pathogenic` | `bool | None` | optional | `None` | 0.2.0 | — | — |
| `benign` | `bool | None` | optional | `None` | 0.2.0 | — | — |
| `curator` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `method` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `direction` | `str | None` | optional | `None` | 0.3.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `stat_significance` | `str | None` | optional | `None` | 0.3.0 | `stat_significance` closed=True: `not_significant`, `significant`, `suggestive`, `unknown` | — |
| `effect_size` | `float | None` | optional | `None` | 0.3.0 | — | — |
| `effect_measure` | `str | None` | optional | `None` | 0.3.0 | `effect_measure` closed=False: `HR`, `NR`, `OR`, `RR`, `beta`, `log(HR)`, `log(OR)` | — |
| `effect_allele` | `str | None` | optional | `None` | 0.3.0 | — | — |
| `flags` | `list[str] | None` | optional | `None` | 0.3.0 | `reserved_flags` closed=False: `conditional`, `phased`, `pleiotropic` | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.3.0 | — | — |
| `clin_sig` | `str | None` | optional | `None` | 0.3.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `requires_callable` | `bool | None` | optional | `None` | 0.4.0 | — | — |
| `acmg_sf` | `bool | None` | optional | `None` | 0.4.0 | — | — |
| `actionability` | `str | None` | optional | `None` | 0.4.0 | `actionability` closed=True: `actionable`, `descriptive`, `incurable`, `modifiable`, `pharmacogenomic`, `preventable`, `reproductive` | — |
| `callable_from` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `quality_from` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `min_quality` | `float | None` | optional | `None` | 0.5.0 | — | — |

**Model-specific validators.**

* `_validate_state` (`spec.py:944`) — membership in `VALID_STATES`; message is
  `f"state must be one of {sorted(VALID_STATES)}, got: {v!r}"`.
* `_validate_chrom` (`spec.py:951`) — routes through `vrs.normalize_chrom` **then** requires
  membership in `VALID_CHROMOSOMES`. So `chr7`, `CHR7`, `M`, `chrM` all normalize and are stored as
  the declared member; alt contigs, scaffolds, patches and decoys stay rejected. When the rejected
  name is uniquely another build's, `vrs.sole_build_naming_contig` adds a clause naming that build;
  it withholds (adds no clause) when the tables cannot settle it.
* `_validate_actionability` (`spec.py:1008`) — `check_vocab(v, ACTIONABILITY_SEED, ...)`. Note the
  constant is named `..._SEED` but is enforced as **closed** (see §11).
* `_validate_effect_allele` (`spec.py:1013`) — `vocab.validate_allele`.
* `_validate_weight` / `_validate_min_quality` — `validate_finite`.
* `_split_flags` (before) splits a CSV cell on `_MULTI_SEP`; `_validate_flags` rejects empty
  entries only. The `flags` vocabulary is **open** (`RESERVED_FLAGS` is a suggestion set).
* `_require_quality_pair` (after, `spec.py:829`) — `quality_from` and `min_quality` are
  both-or-neither: *"A floor needs a field to be measured against, and a field needs a floor to be a
  floor."*
* `_validate_identification` (after, `spec.py:1044`) — three rules: at least `rsid` **or**
  (`chrom`+`start`); if either positional column is set both must be; `ref`/`alts` require the
  positional pair. Error strings, verbatim:
  `"At least one identifier is required: provide rsid or position (chrom + start)"` and
  `"ref/alts require chrom and start to also be provided"`.
* `_freeze_identity` (after, `spec.py:846`) — stamps `variant_key`, `authored_ident`,
  `locus_index=0`, `locus_count=1`, **overwriting** any authored values ("no foot-gun"). Because a
  `mode="after"` validator does not re-run on `model_copy`, the frozen key survives resolution.

**Read-time 0.3 aliases and `upgraded()`** (`spec.py:889`–`spec.py:941`). `state` and the ClinVar
booleans stay required/authoritative for 0.2 compatibility, and five properties derive the
orthogonal 0.3 axes for a legacy row: `effective_direction`, `effective_stat_significance`,
`effective_clin_sig`, `effective_pathogenic`, `effective_benign`. `upgraded()` materializes those
into a copy and trims `state` via `derive.trimmed_state`; the docstring claims idempotency
(`r.upgraded().upgraded() == r.upgraded()`). `needs_upgrade` is `self.upgraded() != self`.

### `StudyRow` — `studies.csv`

#### `StudyRow` — `spec.py:1065`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': ('effect_allele',), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('variant_key', 'pmid')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `rsid` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.2.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `pmid` | `str` | required | — | 0.2.0 | — | — |
| `population` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `p_value` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `conclusion` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `study_design` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `stat_significance` | `str | None` | optional | `None` | 0.3.0 | `stat_significance` closed=True: `not_significant`, `significant`, `suggestive`, `unknown` | — |
| `effect_size` | `float | None` | optional | `None` | 0.3.0 | — | — |
| `effect_measure` | `str | None` | optional | `None` | 0.3.0 | `effect_measure` closed=False: `HR`, `NR`, `OR`, `RR`, `beta`, `log(HR)`, `log(OR)` | — |
| `effect_allele` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.3.0 | — | — |
| `statistical_test` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `confidence` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `confidence_unit` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `doi` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `provenance_quote` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `provenance_regex` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `curator` | `str | None` | optional | `None` | 0.6.5 | — | — |
| `p_value_num` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Gt(gt=0.0);Le(le=1.0) |

**Model-specific validators.**

* `_validate_pmid` (`spec.py:1332`) — `validate_pmid_cell(v, "pmid", required=True)`. Grounding
  evidence is mandatory on a study row.
* `_validate_doi` (`spec.py:1341`) — must contain a DOI token per `DOI_PATTERN`
  (`10\.\d{4,9}/\S+`, `spec.py:91`), kept **verbatim** rather than normalized.
* `_validate_provenance_regex` (`spec.py:1353`) — the pattern must `re.compile()`. The comment
  states ReDoS-safety is the consumer's concern and that a consumer evaluates it with a linear-time
  engine, never Python `re`.
* `_blank_confidence_cell_is_absent` (`spec.py:1366`) — `(v or "").strip() or None` on both
  `confidence` and `confidence_unit`, the same normalization `ClinSigAuthorityCallRow` applies.
* `_refuse_a_magnitude_with_no_instrument` (after, `spec.py:1374`) — `confidence` set with
  `confidence_unit` empty is refused; the converse is allowed ("a unit with no magnitude is
  harmless").
* `_validate_study_identification` (after, `spec.py:1389`) — a study row may name **no** variant at
  all (since 0.6), but never half of one: `start`/`ref` present with neither `rsid` nor `chrom` is
  refused as "a half-written coordinate, not an absent one".

`_KEY_FIELDS = ("variant_key", "pmid")` (`spec.py:1072`); `REQUIRED_ANY_OF = ()` (`spec.py:1100`) —
the empty tuple is itself the statement that a subject-less row is legal.

### The binning family — `MeasureBinRow` and its four subclasses

#### `MeasureBinRow` — `binning.py:238`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': (), '_EXPECTED_KIND': None}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `measure_kind` | `str` | required | — | 0.4.0 | `measure_kind` closed=True: `activity_score`, `allele_fraction`, `copy_number`, `prs_percentile`, `repeat_count` | — |
| `measure_min` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_max` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_tiling` | `str | None` | optional | `None` | 0.6.0 | `measure_tiling` closed=True: `continuous`, `quantised` | — |
| `direction` | `str | None` | optional | `None` | 0.4.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.4.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `phenotype` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |
| `unresolved` | `bool` | defaulted | `False` | 0.4.0 | — | — |
| `source_field` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `source_element` | `str | None` | optional | `None` | 0.6.0 | `source_element` closed=True: `annotated_alt`, `largest`, `largest_alt`, `reference`, `smallest`, `smallest_alt`, `sum`, `sum_alt` +notes | — |
| `pmid` | `str | None` | optional | `None` | 0.6.0 | — | — |

#### `ActivityPhenotypeRow` — `binning.py:440`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('gene',), '_EXPECTED_KIND': 'activity_score'}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `measure_kind` | `str` | defaulted | `'activity_score'` | 0.4.0 | `measure_kind_activity_score` closed=True: `activity_score` | — |
| `measure_min` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_max` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_tiling` | `str | None` | optional | `None` | 0.6.0 | `measure_tiling` closed=True: `continuous`, `quantised` | — |
| `direction` | `str | None` | optional | `None` | 0.4.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.4.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `phenotype` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |
| `unresolved` | `bool` | defaulted | `False` | 0.4.0 | — | — |
| `source_field` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `source_element` | `str | None` | optional | `None` | 0.6.0 | `source_element` closed=True: `annotated_alt`, `largest`, `largest_alt`, `reference`, `smallest`, `smallest_alt`, `sum`, `sum_alt` +notes | — |
| `pmid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `gene` | `str` | required | — | 0.4.0 | — | — |

#### `CopyNumberRow` — `binning.py:463`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('gene', 'modifier_gene', 'effective_modifier_copy_number'), '_EXPECTED_KIND': 'copy_number'}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `measure_kind` | `str` | defaulted | `'copy_number'` | 0.4.0 | `measure_kind_copy_number` closed=True: `copy_number` | — |
| `measure_min` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_max` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_tiling` | `str | None` | optional | `None` | 0.6.0 | `measure_tiling` closed=True: `continuous`, `quantised` | — |
| `direction` | `str | None` | optional | `None` | 0.4.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.4.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `phenotype` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |
| `unresolved` | `bool` | defaulted | `False` | 0.4.0 | — | — |
| `source_field` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `source_element` | `str | None` | optional | `None` | 0.6.0 | `source_element` closed=True: `annotated_alt`, `largest`, `largest_alt`, `reference`, `smallest`, `smallest_alt`, `sum`, `sum_alt` +notes | — |
| `pmid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `gene` | `str` | required | — | 0.4.0 | — | — |
| `modifier_gene` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `modifier_cn` | `int | None` | optional | `None` | 0.4.0 | — | — |
| `modifier_copy_number` | `float | None` | optional | `None` | 0.6.0 | — | — |

#### `RepeatAlleleRow` — `binning.py:577`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('gene', 'repeat_unit'), '_EXPECTED_KIND': 'repeat_count'}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `measure_kind` | `str` | defaulted | `'repeat_count'` | 0.4.0 | `measure_kind_repeat_count` closed=True: `repeat_count` | — |
| `measure_min` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_max` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_tiling` | `str | None` | optional | `None` | 0.6.0 | `measure_tiling` closed=True: `continuous`, `quantised` | — |
| `direction` | `str | None` | optional | `None` | 0.4.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.4.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `phenotype` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |
| `unresolved` | `bool` | defaulted | `False` | 0.4.0 | — | — |
| `source_field` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `source_element` | `str | None` | optional | `None` | 0.6.0 | `source_element` closed=True: `annotated_alt`, `largest`, `largest_alt`, `reference`, `smallest`, `smallest_alt`, `sum`, `sum_alt` +notes | — |
| `pmid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `gene` | `str` | required | — | 0.4.0 | — | — |
| `repeat_unit` | `str` | required | — | 0.4.0 | — | — |

#### `HeteroplasmyRow` — `binning.py:612`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': ('ref', 'alts'), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': True, '_KEY_FIELDS': ('gene', 'reference_sequence', 'tissue', 'variant_key'), '_EXPECTED_KIND': 'allele_fraction'}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `measure_kind` | `str` | defaulted | `'allele_fraction'` | 0.4.0 | `measure_kind_allele_fraction` closed=True: `allele_fraction` | — |
| `measure_min` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_max` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `measure_tiling` | `str | None` | optional | `None` | 0.6.0 | `measure_tiling` closed=True: `continuous`, `quantised` | — |
| `direction` | `str | None` | optional | `None` | 0.4.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.4.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `phenotype` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |
| `unresolved` | `bool` | defaulted | `False` | 0.4.0 | — | — |
| `source_field` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `source_element` | `str | None` | optional | `None` | 0.6.0 | `source_element` closed=True: `annotated_alt`, `largest`, `largest_alt`, `reference`, `smallest`, `smallest_alt`, `sum`, `sum_alt` +notes | — |
| `pmid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `gene` | `str` | required | — | 0.4.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `alts` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `reference_sequence` | `str` | required | — | 0.4.0 | — | — |
| `tissue` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `assay_context` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `variant_key` | `str | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `authored_ident` | `list[str] | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |

**Shape of the family.** One base (`MeasureBinRow`, `binning.py:238`) declaring the measure→phenotype
columns, and four subclasses that pin `measure_kind` to a literal and add the columns that key the
table. Each subclass declares `_EXPECTED_KIND` and its own single-member `measure_kind` vocabulary
marker, and each has its own `_KEY_FIELDS`.

| Subclass | `_EXPECTED_KIND` | `_KEY_FIELDS` | Added columns |
| --- | --- | --- | --- |
| `ActivityPhenotypeRow` (`binning.py:440`) | `activity_score` | `("gene",)` | `gene` |
| `CopyNumberRow` (`binning.py:463`) | `copy_number` | `("gene", "modifier_gene", "effective_modifier_copy_number")` | `gene`, `modifier_gene`, `modifier_cn` (deprecated), `modifier_copy_number` |
| `RepeatAlleleRow` (`binning.py:577`) | `repeat_count` | `("gene", "repeat_unit")` | `gene`, `repeat_unit` |
| `HeteroplasmyRow` (`binning.py:612`) | `allele_fraction` | `("gene", "reference_sequence", "tissue", "variant_key")` | the five identity columns, `reference_sequence`, `tissue`, `assay_context`, plus stamped `variant_key`/`authored_ident` |

`HeteroplasmyRow` is the only binning kind that sets `_KEY_INCLUDES_ALTS = True` (`binning.py:720`),
so it stamps a positional identity through `base.stamp_identity` with `alts` in the key.

**Validators on the base.**

* `_validate_pmid` (`binning.py:382`) — `validate_pmid_cell(..., required=False)`.
* `_validate_bound_finite` (`binning.py:388`) — `validate_finite(v, "measure bound")` on both bounds.
* `_validate_measure_tiling` (`binning.py:393`) — `check_vocab(..., VALID_MEASURE_TILINGS, ...)`.
* `_validate_measure_kind` (`binning.py:398`) — **returns** `check_vocab`'s canonical member and
  compares *that* against `_EXPECTED_KIND`. The comment records the bug this fixed (RM95): called
  for its raising side effect alone, the validator stored the author's raw `copy-number` inside
  `content_signature` and then compared the raw string against `_EXPECTED_KIND`, so "every subclass
  rejected exactly what this base class had just accepted".
* `_validate_range` (after, `binning.py:414`) — three rules: an `unresolved=True` row must carry
  neither bound; a resolved row needs at least one; `measure_min <= measure_max`, with
  `min == max` explicitly legal ("a sharp value").

**`CopyNumberRow` specifics.** `effective_modifier_copy_number` (`binning.py:537`) coalesces
`modifier_copy_number` then `modifier_cn`, using `is not None` rather than `or` because **0 is a
legal dosage** (SMN2 = 0 copies). `_validate_modifier` (`binning.py:556`) refuses *both* spellings
being set — "two spellings that can disagree, with a rule for picking a winner, is the `vrs_id`
desync shape" — and requires `modifier_gene` and the effective copy number to be set together or
both null.

**`HeteroplasmyRow` specifics.** `_reject_legacy_reference` (`binning.py:722`) refuses any
`reference_sequence` whose accession base is in `LEGACY_MT_REFERENCE_BASES` (`{"NC_001807"}`,
`binning.py:608`) — "yields a confidently-wrong haplogroup; use NC_012920.1". It is **not** a closed
allow-list: `CANONICAL_MT_REFERENCE_SEQUENCES` (`{"NC_012920.1"}`, `binning.py:609`) exists but the
validator "rejects only this enumerated landmine" (`binning.py:607`). `_validate_fraction_bounds`
(`binning.py:733`) requires both bounds within `[0, 1]`.

### The PGx family — `pgx.py`

#### `HaplotypeRow` — `pgx.py:82`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': ('ref', 'allele'), 'REQUIRED_ANY_OF': (frozenset({'rsid'}), frozenset({'start', 'chrom'})), '_KEY_INCLUDES_ALTS': False, '_KEY_FIELDS': ('haplotype_name', 'variant_key', 'allele')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `haplotype_name` | `str` | required | — | 0.4.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.4.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `alts` | `str | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `allele` | `str` | required | — | 0.4.0 | — | — |
| `gene` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `requires_callable` | `bool | None` | optional | `None` | 0.7.0 | — | — |
| `variant_key` | `str | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `authored_ident` | `list[str] | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |

#### `AlleleFunctionRow` — `pgx.py:208`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('gene', 'allele')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `gene` | `str` | required | — | 0.4.0 | — | — |
| `allele` | `str` | required | — | 0.4.0 | — | — |
| `activity_value` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `function_status` | `str | None` | optional | `None` | 0.4.0 | `function_status` closed=True: `decreased_function`, `increased_function`, `no_function`, `normal_function`, `uncertain_function`, `unknown_function` | — |
| `suballele` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `copy_number` | `int | None` | optional | `None` | 0.4.0 | — | — |
| `sv_type` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `hybrid_orientation` | `str | None` | optional | `None` | 0.4.0 | — | — |

#### `DiplotypeRow` — `pgx.py:274`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('gene', 'haplotype_a', 'haplotype_b', 'trait_efo_id', 'drug', 'clinical_context')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `gene` | `str` | required | — | 0.4.0 | — | — |
| `haplotype_a` | `str` | required | — | 0.4.0 | — | — |
| `haplotype_b` | `str` | required | — | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `direction` | `str | None` | optional | `None` | 0.4.0 | `direction` closed=True: `contested`, `neutral`, `protective`, `risk`, `unknown` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.4.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `phenotype` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |
| `drug` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `response` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `evidence_level` | `str | None` | optional | `None` | 0.4.0 | `evidence_level` closed=True: `1A`, `1B`, `2A`, `2B`, `3`, `4` | — |
| `recommendation_strength` | `str | None` | optional | `None` | 0.5.0 | `recommendation_strength` closed=True: `moderate`, `no_recommendation`, `optional`, `strong` | — |
| `clinical_context` | `str | None` | optional | `None` | 0.5.0 | — | — |

#### `PharmVariantRow` — `pgx.py:411`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': ('ref', 'genotype'), 'REQUIRED_ANY_OF': (frozenset({'rsid'}), frozenset({'start', 'chrom'})), '_KEY_INCLUDES_ALTS': False, '_KEY_FIELDS': ('variant_key', 'drug', 'genotype', 'phenotype_category', 'annotation_id')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `rsid` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.4.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `alts` | `str | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `gene` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `requires_callable` | `bool | None` | optional | `None` | 0.7.0 | — | — |
| `genotype` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `variant_key` | `str | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `authored_ident` | `list[str] | None` | optional | `None` | 0.6.0 | — | marks=compiler_managed exclude=True |
| `drug` | `str` | required | — | 0.4.0 | — | — |
| `phenotype_category` | `str | None` | optional | `None` | 0.5.0 | `phenotype_category` closed=True: `dosage`, `efficacy`, `metabolism_pk`, `other`, `pd`, `toxicity` | — |
| `annotation_id` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `response` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `evidence_level` | `str | None` | optional | `None` | 0.4.0 | `evidence_level` closed=True: `1A`, `1B`, `2A`, `2B`, `3`, `4` | — |
| `pmid` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `conclusion` | `str` | required | — | 0.4.0 | — | — |

**Four tables.** `HaplotypeRow` (`haplotypes.csv`, the many-to-many variant↔allele junction),
`AlleleFunctionRow` (`allele_functions.csv`), `DiplotypeRow` (`diplotypes.csv`) and
`PharmVariantRow` (`pharm_variants.csv`). The per-gene `ActivityPhenotypeRow` binning table is the
fourth member of the model in the docstring's counting (`pgx.py:1-10`).

**Haplotype names.** One rule shared by all three tables carrying one:
`validate_haplotype_name` (`pgx.py:58`) against `HAPLOTYPE_NAME_PATTERN = re.compile(r"^\S+$")`
(`pgx.py:56`). The comment (`pgx.py:41-55`) records that `STAR_ALLELE_PATTERN`
(`^\*[0-9A-Za-z][0-9A-Za-z.\-+x×*]*$`, `pgx.py:40`) *was* enforced on `AlleleFunctionRow.allele` and
on neither `HaplotypeRow.haplotype_name` nor `DiplotypeRow.haplotype_a`/`_b` — so `e4` was legal in
two PGx tables and illegal in the third, which made APOE's ε alleles unstateable. `STAR_ALLELE_PATTERN`
remains defined and is now enforced by **no model in this package** (see §11).

**Validators.**

* `HaplotypeRow._validate_allele` (`pgx.py:190`) — `vocab.validate_allele` (a nucleotide sequence).
  Note `HaplotypeRow.allele` is a *sequence* while `AlleleFunctionRow.allele` is a *name*: the two
  columns share a name and take opposite validators (`pgx.py:190` vs `pgx.py:255`), and
  `ALLELE_COLUMNS` on `HaplotypeRow` is `("ref", "allele")` while on `AlleleFunctionRow` it is `()`.
* `HaplotypeRow._validate_identification` / `PharmVariantRow._validate_identification`
  (`pgx.py:201`, `pgx.py:626`) — `"a haplotype variant needs an identifier: rsid, or chrom + start"`
  and `"a pharm variant needs an identifier: rsid, or chrom + start"`.
* `AlleleFunctionRow._validate_function_status` — `check_vocab(..., VALID_FUNCTION_STATUS, ...)`.
* `DiplotypeRow._normalize_clinical_context` (`pgx.py:387`) — strips, because "CPIC ships trailing
  whitespace in three of its sixteen values" and the column is part of the row key.
* `DiplotypeRow._canonicalize_pair` (after, `pgx.py:402`) — swaps so `haplotype_a <= haplotype_b`,
  making the key order-independent.
* `PharmVariantRow._validate_pmid` (`pgx.py:616`) — `validate_pmid_cell(..., required=False)`.

Both `HaplotypeRow` and `PharmVariantRow` set `_KEY_INCLUDES_ALTS = False` (`pgx.py:188`,
`pgx.py:609`): they stamp a positional identity **without** `alts`, and `alts` on both is
`COMPILER_MANAGED` + `exclude=True` — filled from the injected resolution table, and refused with a
specific diagnosis if an author writes it (`base.reject_compiler_filled`, `base.py:422`).

### `PgsRow` — `pgs.csv`

#### `PgsRow` — `pgs.py:41`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('pgs_id', 'trait_efo_id')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `pgs_id` | `str` | required | — | 0.4.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `note` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `group` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `training_ancestry` | `list[str] | None` | optional | `None` | 0.4.0 | `training_ancestry` closed=True: `AFR`, `AMR`, `EAS`, `EUR`, `SAS`, `multi` | — |
| `training_cohort` | `str | None` | optional | `None` | 0.4.0 | — | — |
| `match_rate_floor` | `float | None` | optional | `None` | 0.4.0 | — | — |
| `research_tier` | `str | None` | optional | `None` | 0.4.0 | `research_tier` closed=True: `calibrated`, `research_only` | — |

**Validators.** `_validate_pgs_id` (`pgs.py:87`) against `PGS_ID_PATTERN = ^PGS\d+$` (`pgs.py:34`);
`_split_ancestry` (before) splits a CSV cell on `MULTI_SEP`; `_validate_ancestry` (`pgs.py:103`)
**rebuilds** the list from `check_vocab`'s returns rather than validating and discarding — the
comment names this as RM95's sharpest case, since canonicalizing per element and returning the
original list would let a `-`/`_` slip survive into `content_signature`, "latent today only because
no member of `VALID_TRAINING_ANCESTRY` contains a separator"; `_validate_match_rate_floor` requires
finite and within `[0, 1]`; `_validate_research_tier` against `VALID_RESEARCH_TIERS`.

The module docstring states `pgs.csv` is "a manifest of PGS Catalog IDs, not authored weights"
(`pgs.py:4`) — a declared interface, not a `measure→phenotype` binning table.

### `OverrideRow` — `overrides.csv`, the authored overlay

#### `OverrideRow` — `overrides.py:195`
config: {'extra': 'forbid'}
classvars: {'ALLELE_COLUMNS': (), 'REQUIRED_ANY_OF': (), '_KEY_INCLUDES_ALTS': None, '_KEY_FIELDS': ('table', 'subject', 'member', 'field')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `table` | `str` | required | — | 0.7.0 | `overridable_table` closed=True: `clin_sig_concordance.csv`, `clinical_assertions.csv`, `expression_effects.csv`, `frequencies.csv`, `gene_metrics.csv`, `gene_validity.csv`, `gwas_effects.csv`, `literature.csv`, `resolution.csv` | — |
| `subject` | `str` | required | — | 0.7.0 | — | — |
| `member` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `field` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `operation` | `str` | required | — | 0.7.0 | `override_operation` closed=True: `insert`, `suppress`, `update` +notes | — |
| `value` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `reason` | `str` | required | — | 0.7.0 | — | marks=outside_content_identity |
| `decided_by` | `str | None` | optional | `None` | 0.7.0 | — | marks=outside_content_identity |
| `decided_at` | `str | None` | optional | `None` | 0.7.0 | — | marks=outside_content_identity |

`OverrideRow` (`overrides.py:195`) is an `AuthoredModel`, not a fact model — "a human writes this,
every other row in the tables it names is machine-written" (`overrides.py:198`).

**The registry it is keyed against.** `OVERRIDABLE_TABLES` (`overrides.py:137`) maps a derived-table
filename to an `OverlayTarget(model, subject_field, member_field)` dataclass (`overrides.py:71`).
Nine entries, and the docstring says the number is "a decision rather than a count"
(`overrides.py:86`):

| Table | subject column | member column |
| --- | --- | --- |
| `resolution.csv` | `variant_key` | `locus_index` |
| `frequencies.csv` | `variant_key` | `population` |
| `gene_metrics.csv` | `gene` | `dataset` |
| `gene_validity.csv` | `gene` | `assertion_id` |
| `clinical_assertions.csv` | `variant_key` | `variation_id` |
| `literature.csv` | `pmid` | — |
| `gwas_effects.csv` | `association_id` | — |
| `clin_sig_concordance.csv` | `variant_key` | `genotype` |
| `expression_effects.csv` | `variant_key` | `gene` |

Two tables are deliberately **outside**: `sources.csv`/`licensing.csv` (it has its own merge path and
is the one derived sidecar a human is told to hand-write, and the only one the compile licence gate
reads — `overrides.py:100`) and `clin_sig_authority_calls.csv` ("the author answers the question;
they do not get to rewrite what an archive published", `overrides.py:127`).

`VALID_OVERRIDE_TABLES = frozenset(OVERRIDABLE_TABLES)` (`overrides.py:165`) — derived off the
registry, not restated. The two field descriptions on `table`/`subject` are generated by `_by_column`
(`overrides.py:153`) for the same reason; the comment records that they were hand-written prose and
had already lost `clin_sig_concordance.csv`.

`VALID_OVERRIDE_OPERATIONS = {"update", "insert", "suppress"}` (`overrides.py:178`), each carrying
per-member prose in `_OPERATION_MEANINGS` (`overrides.py:182`). All three are stated to be
"idempotent set operations by construction", which is what buys the round trip instead of a
`previous_value` column — `reverse_module` emits the post-overlay table *plus* the overlay, so the
overlay applies twice.

**Validators.**

* `_reason_is_the_point` (before, `overrides.py:302`) — a missing/blank `reason` gets its own
  diagnosis before pydantic's generic required-field message.
* `_validate_table` / `_validate_operation` — `check_vocab` against the two closed sets.
* `_require_content` (`overrides.py:337`) — `subject` and `reason` may not be blank:
  `f"{info.field_name} may not be blank"`.
* `_strip_key_columns` (`overrides.py:345`) — strips `member`/`field`, blank → `None`.
* `_canonical_decided_at` (before, `overrides.py:364`) — `normalize.normalize_utc_timestamp`.
* `_operation_and_key_agree` (after, `overrides.py:374`) — the cross-field rules: `suppress` writes
  nothing so `value` must be empty (`"suppress writes nothing, so value must be empty (got …)."`);
  `update`/`insert` need a `field`
  (`f"{self.operation} needs a field naming the column it writes."`); `suppress` refuses an empty
  `member` on a grouped table; group-scoped `update` is the one operation allowed one.

`reason`, `decided_by` and `decided_at` carry `OUTSIDE_CONTENT_IDENTITY` (`base.py:94`) — they say
*why/who/when* rather than *what*, so `content_signature` omits them, but they are **not**
`exclude=True`, because `model_dump()` has to stay complete for the drafting and test writers.

### The module-level config models (`module_spec.yaml`)

#### `ModuleSpecConfig` — `spec.py:317`
config: {'extra': 'forbid'}
classvars: {}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `schema_version` | `str` | defaulted | `'1.0'` | 0.2.0 | — | — |
| `module` | `spec.ModuleInfo` | required | — | 0.2.0 | — | — |
| `defaults` | `spec.Defaults` | defaulted | factory `Defaults` | 0.2.0 | — | — |
| `genome_build` | `str` | defaulted | `'GRCh38'` | 0.2.0 | — | — |
| `panel` | `manifest.GenePanelSpec | None` | optional | `None` | 0.2.0 | — | — |
| `authorship` | `list[manifest.Contribution]` | defaulted | factory `list` | 0.4.0 | — | — |
| `license` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `weighting` | `manifest.Weighting | None` | optional | `None` | 0.6.0 | — | — |
| `authority_precedence` | `list[str]` | defaulted | factory `list` | 0.7.0 | — | — |

#### `ModuleInfo` — `spec.py:172`
config: {'extra': 'forbid'}
classvars: {}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `title` | `str` | required | — | 0.2.0 | — | — |
| `description` | `str` | required | — | 0.2.0 | — | — |
| `report_title` | `str` | required | — | 0.2.0 | — | — |
| `icon` | `str` | defaulted | `'database'` | 0.2.0 | — | — |
| `icon_set` | `str` | defaulted | `'fomantic'` | 0.2.0 | `icon_set` closed=True: `awesome`, `fomantic` | — |
| `color` | `str` | defaulted | `'#6435c9'` | 0.2.0 | — | — |
| `name` | `str` | required | — | 0.2.0 | — | — |
| `version` | `str | None` | optional | `None` | 0.5.0 | — | — |

#### `Defaults` — `spec.py:296`
config: {'extra': 'forbid'}
classvars: {}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `curator` | `str` | defaulted | `'ai-module-creator'` | 0.2.0 | — | — |
| `method` | `str` | defaulted | `'literature-review'` | 0.2.0 | — | — |
| `priority` | `str | None` | optional | `None` | 0.2.0 | — | — |

#### `GenePanelSpec` — `manifest.py:1032`
config: {'extra': 'forbid'}
classvars: {}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `str` | required | — | 0.2.0 | — | — |
| `reference` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `reference_sha256` | `str | None` | optional | `None` | 0.2.0 | — | — |
| `genes` | `list[str]` | defaulted | factory `list` | 0.2.0 | — | — |
| `significance` | `list[str]` | defaulted | factory `list` | 0.2.0 | — | — |

#### `Contribution` — `manifest.py:1493`
config: {'extra': 'forbid'}
classvars: {}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `who` | `str` | required | — | 0.4.0 | — | — |
| `role` | `str` | required | — | 0.4.0 | `author_role` closed=True: `audited`, `created`, `edited`, `reviewed` | — |
| `kind` | `list[str]` | defaulted | factory `list` | 0.4.0 | `author_kind` closed=False: `agent`, `ai`, `human`, `human_certified`, `human_expert`, `swarm`, `team` | — |
| `at` | `str | None` | optional | `None` | 0.4.0 | — | — |

#### `Weighting` — `manifest.py:1572`
config: {'extra': 'forbid'}
classvars: {}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `scale` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `method` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `note` | `str | None` | optional | `None` | 0.6.0 | — | — |

`ModuleSpecConfig` (`spec.py:317`) is the root of `module_spec.yaml`. `ModuleInfo` (`spec.py:172`)
**subclasses `manifest.Display`**, adding `name` and `version` — so the authored display block and
the manifest display block are one model by construction. `Defaults`, `GenePanelSpec`, `Contribution`
and `Weighting` all set `extra="forbid"`; `Display` does **not** (its config is empty).

**Validators.**

* `ModuleSpecConfig._reject_template_placeholders` (before, `spec.py:327`) — refuses
  `vocab.TEMPLATE_PLACEHOLDER` (`"<<REPLACE>>"`, `vocab.py:980`) anywhere in the block.
* `ModuleSpecConfig._check_authority_precedence` (`spec.py:410`) — rejects an empty entry and a
  repeated one; the vocabulary of authority names itself stays **open**. The field description states
  the list is "a methodological stance, recorded and computed with by nothing".
* `ModuleSpecConfig._validate_version` (`spec.py:439`) — `schema_version` must equal
  `manifest.SCHEMA_VERSION` (`"1.0"`), message
  `f"Unsupported schema_version: {v!r}. Expected {SCHEMA_VERSION!r}"`.
* `ModuleInfo._diagnose_authority_keys` (before, `spec.py:207`) — `normalize.reject_authority_keys`;
  nothing is stripped, the key is named.
* `ModuleInfo._accept_the_number_yaml_read` (before, `spec.py:217`) — an `int` version is coerced to
  `str`; a `float` is **refused** with a message about YAML reading `1.10` as `1.1`; a `bool` falls
  through to the string check. The docstring records the measurement behind it: of 61 foreign
  modules swept through `close_module`, **26 refused on exactly this**, 90% of all refusals.
* `ModuleInfo._enforce_semver` (after, `spec.py:255`) — coerces `version` through
  `normalize.normalize_version` and records the pre-coercion string on the private
  `_version_coerced_from`, surfaced by the `version_coerced_from` property (`spec.py:275`). It is
  **not a field**, so it stays out of `model_dump()` and every CSV — but the compiler copies it into
  `Identity.version_coerced_from`.
* `ModuleInfo._validate_name` (`spec.py:290`) — `identity.validate_name`.

### Authored-model coverage check

Walking every `BaseModel` subclass defined in the package (`pkgutil` + `inspect`) finds **57**
models. `reference._ALL_MODELS` (`reference.py:176`) holds **32** — the authored surface plus the
fact models plus the overlay row. The 25 not in it are the manifest-side block models plus
`AuthoredModel` itself; that exclusion is consistent with `authoring_reference()` describing the
*authored* DSL. No member of `_ALL_MODELS` is missing from the walk.

Thirteen concrete `AuthoredModel` subclasses: `VariantRow`, `StudyRow`, `MeasureBinRow`,
`ActivityPhenotypeRow`, `CopyNumberRow`, `RepeatAlleleRow`, `HeteroplasmyRow`, `HaplotypeRow`,
`AlleleFunctionRow`, `DiplotypeRow`, `PharmVariantRow`, `PgsRow`, `OverrideRow`.

---

## 3. The manifest models

`manifest.json` is the compiled output half. `ModuleManifest` (`manifest.py:1623`) is the root;
`read_manifest` / `write_manifest` (`manifest.py:1849`, `1854`) are the I/O pair — writing is
`model_dump_json(indent=2, exclude_none=False)` plus a trailing newline, so **null fields are
serialized**.

Module-level constants: `MANIFEST_VERSION = "1.0"`, `SCHEMA_VERSION = "1.0"` (`manifest.py:37-38`),
`MARKETPLACE_COMPILED_BY = "marketplace-server"` — "the only `compiled_by` value a downloader trusts"
(`manifest.py:41`).

**Extra-field policy differs between halves and it is load-bearing.** Every authored row model sets
`extra="forbid"`. On the manifest side only **six** do — `GenePanelSpec`, `Contribution`, `Weighting`,
`Closure`, `VerificationRecord`, `VerificationDoc` (measured by reading `model_config` off every
class in the package). `ModuleManifest` and every other block leave pydantic's default (`ignore`), so an older
reader tolerates a newer manifest. The exception is `VerificationRecord`, which forbids: a field
added there (`producer`, first seen 0.7.0) is a hard break for a reader pinned to 0.6.

### `ModuleManifest` — the root

#### `ModuleManifest` — `manifest.py:1623`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `manifest_version` | `str` | defaulted | `'1.0'` | — | — | — |
| `schema_version` | `str` | defaulted | `'1.0'` | — | — | — |
| `identity` | `manifest.Identity` | required | — | — | — | — |
| `display` | `manifest.Display` | required | — | — | — | — |
| `genome_build` | `str` | defaulted | `'GRCh38'` | — | — | — |
| `curator` | `str | None` | optional | `None` | — | — | — |
| `method` | `str | None` | optional | `None` | — | — | — |
| `license` | `str | None` | optional | `None` | — | — | — |
| `authority_precedence` | `list[str]` | defaulted | factory `list` | — | — | — |
| `weighting` | `manifest.Weighting | None` | optional | `None` | — | — | — |
| `owner` | `str | None` | optional | `None` | — | — | — |
| `authors` | `list[str]` | defaulted | factory `list` | — | — | — |
| `authorship` | `list[manifest.Contribution]` | defaulted | factory `list` | — | — | — |
| `created_at` | `str | None` | optional | `None` | — | — | — |
| `published_at` | `str | None` | optional | `None` | — | — | — |
| `stats` | `manifest.Stats` | defaulted | factory `Stats` | — | — | — |
| `compilation` | `manifest.Compilation` | defaulted | factory `Compilation` | — | — | — |
| `frequency` | `manifest.Frequency | None` | optional | `None` | — | — | — |
| `gene_metrics` | `manifest.GeneMetrics | None` | optional | `None` | — | — | — |
| `gene_validity` | `manifest.GeneValidity | None` | optional | `None` | — | — | — |
| `clinical_assertions` | `manifest.ClinicalAssertions | None` | optional | `None` | — | — | — |
| `gwas_effects` | `manifest.GwasEffects | None` | optional | `None` | — | — | — |
| `expression_effects` | `manifest.ExpressionEffects | None` | optional | `None` | — | — | — |
| `literature` | `manifest.Literature | None` | optional | `None` | — | — | — |
| `clin_sig_concordance` | `manifest.ClinSigConcordance | None` | optional | `None` | — | — | — |
| `sources` | `manifest.Sources | None` | optional | `None` | — | — | — |
| `verification` | `manifest.Verification | None` | optional | `None` | — | — | — |
| `inputs` | `list[manifest.FileEntry]` | defaulted | factory `list` | — | — | — |
| `content_signature` | `str | None` | optional | `None` | — | — | — |
| `artifact` | `manifest.Artifact` | required | — | — | — | — |
| `logs` | `list[manifest.FileEntry]` | defaulted | factory `list` | — | — | — |
| `derived` | `list[manifest.FileEntry]` | defaulted | factory `list` | — | — | — |
| `provenance` | `manifest.Provenance | None` | optional | `None` | — | — | — |
| `panel` | `manifest.GenePanelSpec | None` | optional | `None` | — | — | — |
| `logo` | `manifest.FileEntry | None` | optional | `None` | — | — | — |
| `readme` | `manifest.FileEntry | None` | optional | `None` | — | — | — |
| `signature` | `manifest.Signature | None` | optional | `None` | — | — | — |

**Who stamps what.** The module docstring (`manifest.py:1-9`) states the split, and the field
descriptions repeat it per field:

* **Compiler-stamped**: `display`, `stats`, `compilation`, `inputs`, `artifact`, plus every
  derived-fact block (`frequency`, `gene_metrics`, `gene_validity`, `clinical_assertions`,
  `gwas_effects`, `expression_effects`, `literature`, `clin_sig_concordance`, `sources`,
  `verification`), `logs`, `derived`, `logo`, `readme`, `content_signature`.
* **Marketplace/registry-stamped on publish** (Optional here): `identity.namespace`,
  `identity.version`, `identity.canonical_id`, `owner`, `published_at`.
* **Author-declared and merely copied through**: `license`, `authority_precedence`, `weighting`,
  `authorship`, `panel`, `genome_build`. `license` "reads like one of them and is not" — the
  compiler cross-checks it against the licensing table and warns rather than overwriting, and
  "nothing downstream stamps this field" (`manifest.py:1640`).
* **Optional and externally added**: `signature` (a detached Ed25519 signature over
  `artifact.digest`).

`genome_build` defaults to `"GRCh38"` and its description says "the reference compiler is
GRCh38-bound — the digest is GRCh38-relative; other builds are recorded but not honored (RM15)"
(`manifest.py:1632`).

`authority_precedence` is explicitly **out of `artifact.digest` and `content_signature`**
(`manifest.py:1652`), and "nothing computes with it, here or in any tier".

### The blocks

#### `Identity` — `manifest.py:95`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `namespace` | `str | None` | optional | `None` | — | — | — |
| `name` | `str` | required | — | — | — | — |
| `version` | `str | None` | optional | `None` | — | — | — |
| `version_coerced_from` | `str | None` | optional | `None` | — | — | — |
| `canonical_id` | `str | None` | optional | `None` | — | — | — |

#### `Display` — `manifest.py:143`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `title` | `str` | required | — | 0.2.0 | — | — |
| `description` | `str` | required | — | 0.2.0 | — | — |
| `report_title` | `str` | required | — | 0.2.0 | — | — |
| `icon` | `str` | defaulted | `'database'` | 0.2.0 | — | — |
| `icon_set` | `str` | defaulted | `'fomantic'` | 0.2.0 | `icon_set` closed=True: `awesome`, `fomantic` | — |
| `color` | `str` | defaulted | `'#6435c9'` | 0.2.0 | — | — |

#### `Stats` — `manifest.py:204`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_count` | `int` | defaulted | `0` | — | — | — |
| `weights_rows` | `int` | defaulted | `0` | — | — | — |
| `study_count` | `int` | defaulted | `0` | — | — | — |
| `gene_count` | `int` | defaulted | `0` | — | — | — |
| `genes` | `list[str]` | defaulted | factory `list` | — | — | — |
| `categories` | `list[str]` | defaulted | factory `list` | — | — | — |
| `clinvar_count` | `int` | defaulted | `0` | — | — | — |
| `pathogenic_count` | `int` | defaulted | `0` | — | — | — |
| `benign_count` | `int` | defaulted | `0` | — | — | — |

`Identity` validators (`manifest.py:125-140`): `name` via `identity.validate_name`, `namespace` via
`identity.validate_namespace`, `version` must satisfy `identity.is_valid_version` —
`f"version must be MAJOR.MINOR.PATCH, got: {v!r}"`. `version_coerced_from` records what the author
wrote before SemVer coercion.

`Display` validators (`manifest.py:189-201`): `color` against `COLOR_PATTERN` (`^#[0-9a-fA-F]{6}$`) —
`f"color must be a 6-digit hex code like #21ba45, got: {v!r}"`; `icon_set` against `VALID_ICON_SETS`
— `f"icon_set must be one of {sorted(VALID_ICON_SETS)}, got: {v!r}"`. `icon` is free-form within the
set. `RECOMMENDED_COLORS` (9 entries) and `RECOMMENDED_ICONS` (9 entries) are recommendation-only and
enforced nowhere (`manifest.py:66-93`).

#### `Compilation` — `manifest.py:229`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `compile_success` | `bool` | defaulted | `False` | — | — | — |
| `compiled_by` | `str | None` | optional | `None` | — | — | — |
| `compiler_version` | `str | None` | optional | `None` | — | — | — |
| `ensembl_reference` | `str | None` | optional | `None` | — | — | — |
| `compiled_at` | `str | None` | optional | `None` | — | — | — |
| `warnings` | `list[str]` | defaulted | factory `list` | — | — | — |
| `carried` | `list[str]` | defaulted | factory `list` | — | — | — |
| `warnings_summary` | `dict[str, int]` | defaulted | factory `dict` | — | `warning_code` closed=True: `bin_coverage_gap`, `bin_tiling_contradicted`, `bin_tiling_inferred`, `bins_ungrounded`, `citation_not_in_pubmed`, `clin_sig_concordance_contested`, `clin_sig_contradicts_frequency`, `closure_discarded_unreadable_record`, `composite_gene_cell`, `contig_ploidy_mismatch`, `contig_ploidy_undecidable`, `declared_license_disagrees`, `deprecated_bin_modifier`, `derived_row_orphan`, `diplotype_definitions_identical`, `diplotype_phase_ambiguous`, `duplicate_study_citation`, `effect_allele_not_at_locus`, `faf95_exceeds_frequency`, `gene_validity_currency_undecidable`, `gene_validity_superseded`, `genotype_allele_not_at_locus`, `genotype_coverage_gap`, `literature_row_uncited`, `locus_cannot_host_genotype`, `locus_hosting_undecidable`, `measure_field_fractional`, `measurement_spans_bins`, `missing_allele_marker_in_alts`, `module_not_closed`, `module_version_coerced`, `non_grch38_variant_keys`, `oe_lof_disagrees_with_counts`, `oe_lof_outside_interval`, `overlay_answer_vindicated`, `overlay_rows_suppressed`, `overlay_targets_missing_table`, `overlay_update_target_unreachable`, `overlay_update_unmatched`, `p_value_encodings_disagree`, `panel_block_deprecated`, `positional_identity_contradicted`, `positional_rows_unjoinable`, `quality_floor_inverted`, `quote_counter_stale`, `quoted_article_license_restrictive`, `resolution_disabled`, `resolution_not_injected`, `resolution_skipped_cross_build`, `rsid_ambiguous`, `rsid_coordinate_disagrees`, `rsid_expanded_to_multiple_loci`, `rsid_no_hosting_locus`, `rsid_unresolved`, `rsid_without_resolution_label`, `sidecar_spelling_deprecated`, `source_row_unused`, `source_terms_unrecorded`, `star_allele_undefined`, `study_effect_allele_not_at_locus`, `study_variant_orphan`, `symbolic_allele_unusable`, `table_file_misplaced`, `table_file_near_miss`, `vcf_pointer_key_collision`, `vcf_pointer_unselected_element`, `verification_findings_recorded`, `verification_stale`, `verification_two_copies`, `verification_unreadable`, `vrs_coverage_incomplete`, `vrs_id_unverifiable`, `weight_sign_disagrees_with_effect` | — |
| `dropped_rows` | `dict[str, int]` | defaulted | factory `dict` | — | — | — |
| `resolution_mode` | `str | None` | optional | `None` | — | — | — |
| `fully_resolved` | `bool` | defaulted | `False` | — | — | — |
| `resolution_subjects` | `int` | defaulted | `0` | — | — | — |
| `expanded_keys` | `int | None` | optional | `None` | — | — | — |
| `expanded_rows` | `int | None` | optional | `None` | — | — | — |
| `resolution_signature` | `str | None` | optional | `None` | — | — | — |
| `resolution_sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `vrs_alleles` | `int` | defaulted | `0` | — | — | — |
| `vrs_alleles_identified` | `int` | defaulted | `0` | — | — | — |
| `positional_rows` | `int | None` | optional | `None` | — | — | — |
| `positional_rows_placed` | `int | None` | optional | `None` | — | — | — |

`Compilation.warnings_summary` carries the closed `warning_code` vocabulary — **73 members**
(`len(VALID_WARNING_CODES)`, `vocab.py:1389`). `_check_warning_codes` (`manifest.py:425`) validates
each key through `check_vocab` and rejects a negative count
(`f"warnings_summary[{checked}] is a count and may not be negative"`, and `"a warnings_summary key is
required"` for an empty key). `carried` is the subset an author cannot clear; the split is
`CARRIED_WARNING_CODES` (**11 members**) and `ACTIONABLE_WARNING_CODES = VALID_WARNING_CODES -
CARRIED_WARNING_CODES` (**62**, derived not listed — `vocab.py:1520`).

### The derived-fact blocks — nine of them, for eleven tables

The mapping is **not** one block per sidecar, and the two exceptions are worth stating because a
peer document will either match them or contradict them:

* **eleven** derived tables (§8) →
* **nine** manifest blocks: `Frequency`, `GeneMetrics`, `GeneValidity`, `ClinicalAssertions`,
  `ExpressionEffects`, `GwasEffects`, `Literature`, `ClinSigConcordance`, `Sources`;
* `resolution.csv` has **no block at all** — its fact hash is published as
  `Compilation.resolution_signature` (`manifest.py:229`), beside the other resolution counters;
* `clin_sig_authority_calls.csv` has **no block of its own** — its hash rides on its parent as
  `ClinSigConcordance.calls_signature`.

Every one of the nine blocks opens with a `signature` field (the fact hash of §4).

#### `Frequency` — `manifest.py:447`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `populations` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `variant_count` | `int` | defaulted | `0` | — | — | — |

#### `GeneMetrics` — `manifest.py:480`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `genes` | `list[str]` | defaulted | factory `list` | — | — | — |

#### `GeneValidity` — `manifest.py:497`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `genes` | `list[str]` | defaulted | factory `list` | — | — | — |
| `diseases` | `list[str]` | defaulted | factory `list` | — | — | — |
| `classifications` | `list[str]` | defaulted | factory `list` | — | — | — |
| `superseded_count` | `int` | defaulted | `0` | — | — | — |
| `submitters` | `list[str]` | defaulted | factory `list` | — | — | — |

#### `ClinicalAssertions` — `manifest.py:565`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `variant_count` | `int` | defaulted | `0` | — | — | — |
| `clin_sigs` | `list[str]` | defaulted | factory `list` | — | — | — |
| `min_review_stars` | `int | None` | optional | `None` | — | — | — |
| `max_review_stars` | `int | None` | optional | `None` | — | — | — |
| `unrated_count` | `int` | defaulted | `0` | — | — | — |
| `not_found_count` | `int` | defaulted | `0` | — | — | — |

#### `ExpressionEffects` — `manifest.py:635`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `variant_count` | `int` | defaulted | `0` | — | — | — |
| `genes` | `list[str]` | defaulted | factory `list` | — | — | — |
| `measures` | `list[str]` | defaulted | factory `list` | — | — | — |
| `with_direction` | `int` | defaulted | `0` | — | — | — |
| `without_direction` | `int` | defaulted | `0` | — | — | — |
| `without_distance` | `int` | defaulted | `0` | — | — | — |
| `max_distance_to_gene` | `int | None` | optional | `None` | — | — | — |

#### `GwasEffects` — `manifest.py:719`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `variant_count` | `int` | defaulted | `0` | — | — | — |
| `with_effect_allele` | `int` | defaulted | `0` | — | — | — |
| `without_effect_allele` | `int` | defaulted | `0` | — | — | — |
| `measures` | `list[str]` | defaulted | factory `list` | — | — | — |
| `units` | `list[str]` | defaulted | factory `list` | — | — | — |
| `traits` | `list[str]` | defaulted | factory `list` | — | — | — |
| `not_found_count` | `int` | defaulted | `0` | — | — | — |

#### `Literature` — `manifest.py:791`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `resolved_count` | `int` | defaulted | `0` | — | — | — |
| `missing_count` | `int` | defaulted | `0` | — | — | — |
| `open_access_count` | `int` | defaulted | `0` | — | — | — |
| `abstract_only_count` | `int` | defaulted | `0` | — | — | — |
| `quotes_authored` | `int` | defaulted | `0` | — | — | — |
| `quotes_found` | `int` | defaulted | `0` | — | — | — |
| `quotes_unchecked` | `int` | defaulted | `0` | — | — | — |

#### `ClinSigConcordance` — `manifest.py:858`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `calls_signature` | `str | None` | optional | `None` | — | — | — |
| `authorities` | `list[str]` | defaulted | factory `list` | — | — | — |
| `datasets` | `list[str]` | defaulted | factory `list` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |
| `call_count` | `int` | defaulted | `0` | — | — | — |
| `opposed_count` | `int` | defaulted | `0` | — | — | — |
| `unchecked_count` | `int` | defaulted | `0` | — | — | — |
| `concordance_states` | `list[str]` | defaulted | factory `list` | — | — | — |
| `authored_positions` | `list[str]` | defaulted | factory `list` | — | — | — |

#### `Sources` — `manifest.py:937`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `layers` | `list[str]` | defaulted | factory `list` | — | — | — |
| `licenses` | `list[str]` | defaulted | factory `list` | — | — | — |
| `attributions` | `list[str]` | defaulted | factory `list` | — | — | — |
| `notices` | `list[str]` | defaulted | factory `list` | — | — | — |
| `share_alike_layers` | `list[str]` | defaulted | factory `list` | — | — | — |
| `noncommercial_layers` | `list[str]` | defaulted | factory `list` | — | — | — |
| `unknown_terms_sources` | `list[str]` | defaulted | factory `list` | — | — | — |
| `nonredistributable_layers` | `list[str]` | defaulted | factory `list` | — | — | — |
| `declared_uses` | `list[str]` | defaulted | factory `list` | — | — | — |
| `commercial_use` | `bool | None` | optional | `None` | — | — | — |
| `redistribution` | `bool | None` | optional | `None` | — | — | — |
| `row_count` | `int` | defaulted | `0` | — | — | — |

`ClinSigConcordance` is the one block carrying **two** signatures — `signature` for
`clin_sig_concordance.csv` and `calls_signature` for its paired detail table
`clin_sig_authority_calls.csv` (`manifest.py:858`).

`Sources.commercial_use` and `Sources.redistribution` are `bool | None` — the two tri-state verdicts
in the manifest (§5).

### Provenance, verification, signature, artifact

#### `ProvenanceItem` — `manifest.py:1080`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | — | — | — |
| `rationale` | `str | None` | optional | `None` | — | — | — |
| `reviewer_verdict` | `str | None` | optional | `None` | — | — | — |
| `confidence` | `float | None` | optional | `None` | — | — | — |
| `human_reviewed` | `bool` | defaulted | `False` | — | — | — |
| `outranks` | `dict[str, str]` | defaulted | factory `dict` | — | — | — |

#### `ProvenanceDoc` — `manifest.py:1115`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `generator` | `str | None` | optional | `None` | — | — | — |
| `model` | `str | None` | optional | `None` | — | — | — |
| `agent_version` | `str | None` | optional | `None` | — | — | — |
| `items` | `list[manifest.ProvenanceItem]` | defaulted | factory `list` | — | — | — |

#### `Provenance` — `manifest.py:1126`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `generator` | `str | None` | optional | `None` | — | — | — |
| `model` | `str | None` | optional | `None` | — | — | — |
| `agent_version` | `str | None` | optional | `None` | — | — | — |
| `item_count` | `int` | defaulted | `0` | — | — | — |
| `file` | `str | None` | optional | `None` | — | — | — |
| `sha256` | `str | None` | optional | `None` | — | — | — |

#### `Closure` — `manifest.py:1169`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `closed_at` | `str` | required | — | — | — | — |
| `closed_by` | `str | None` | optional | `None` | — | — | — |
| `signature` | `manifest.Signature | None` | optional | `None` | — | — | — |

#### `VerificationRecord` — `manifest.py:1213`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `check` | `str` | required | — | 0.6.0 | `verification_check` closed=True: `acmg_secondary_findings`, `allele_function`, `citation_existence`, `citation_identifier`, `clinical_significance`, `dataset_currency`, `dosage_sensitivity`, `evidence_status_currency`, `gene_disease_validity`, `gene_locus_agreement`, `gene_symbol_currency`, `genome_build_agreement`, `literature_coverage`, `pgs_accession_currency`, `pgs_metadata_agreement`, `pgx_evidence_level`, `provenance_quote`, `published_refutation`, `reference_allele`, `regulator_label_agreement`, `repeat_band_agreement`, `rsid_coordinate_agreement`, `rsid_currency`, `trait_currency`, `variant_impact_agreement`, `vrs_allele_id` | — |
| `subjects` | `int` | defaulted | `0` | 0.6.0 | — | — |
| `findings` | `int` | defaulted | `0` | 0.6.0 | — | — |
| `skipped` | `str | None` | optional | `None` | 0.6.0 | `verification_skip` closed=True: `no_reference`, `not_permitted`, `not_requested`, `nothing_to_check`, `offline`, `tautology`, `unreachable`, `unsupported` | — |
| `detail` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `release` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `checked_at` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `producer` | `str | None` | optional | `None` | 0.7.0 | — | — |

#### `VerificationDoc` — `manifest.py:1346`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `module_hash` | `str` | required | — | — | — | — |
| `signature` | `str` | required | — | — | — | — |
| `difficulty` | `int` | required | — | — | — | — |
| `nonce` | `int` | required | — | — | — | — |
| `producer` | `str | None` | optional | `None` | — | — | — |
| `produced_at` | `str | None` | optional | `None` | — | — | — |
| `closure` | `manifest.Closure | None` | optional | `None` | — | — | — |
| `records` | `list[manifest.VerificationRecord]` | defaulted | factory `list` | — | — | — |

#### `Verification` — `manifest.py:1430`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `signature` | `str | None` | optional | `None` | — | — | — |
| `module_hash` | `str | None` | optional | `None` | — | — | — |
| `producer` | `str | None` | optional | `None` | — | — | — |
| `produced_at` | `str | None` | optional | `None` | — | — | — |
| `closure` | `manifest.Closure | None` | optional | `None` | — | — | — |
| `checks` | `list[manifest.VerificationRecord]` | defaulted | factory `list` | — | — | — |

#### `FileEntry` — `manifest.py:1017`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `name` | `str` | required | — | — | — | — |
| `sha256` | `str` | required | — | — | — | — |
| `size` | `int` | required | — | — | — | — |

#### `Artifact` — `manifest.py:1025`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `digest` | `str` | required | — | — | — | — |
| `files` | `list[manifest.FileEntry]` | defaulted | factory `list` | — | — | — |

#### `Signature` — `manifest.py:1153`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `algorithm` | `str` | defaulted | `'ed25519'` | — | — | — |
| `public_key` | `str` | required | — | — | — | — |
| `signature` | `str` | required | — | — | — | — |
| `signed_at` | `str | None` | optional | `None` | — | — | — |

**`ProvenanceDoc` vs `Provenance`.** The same shape one level apart: `ProvenanceDoc` is the on-disk
document holding `items`; `Provenance` is the manifest block holding the *count* plus the file name
and its `sha256`. `ProvenanceItem.outranks` is a `dict[str, str]`.

**`VerificationDoc` vs `Verification`.** Again a document/block pair. The document carries the
proof-of-work (`module_hash`, `signature`, `difficulty`, `nonce` — all required) and the full
`records`; the block carries the same identifiers plus `checks`. Validators:

* `VerificationRecord._check_name` (`manifest.py:1306`) — `check_vocab` against
  `VALID_VERIFICATION_CHECKS` (**26 members**); `None` raises `"check is required"`.
* `VerificationRecord._check_skip` — `check_vocab` against `VALID_VERIFICATION_SKIPS`
  (**8 members**).
* `VerificationRecord._check_counts` — `"a count must not be negative"`.
* `VerificationRecord._check_consistent` (after, `manifest.py:1326`) — two cross-field rules: a
  record that is `skipped` may not also report subjects/findings ("a skipped check has no
  subjects. Record the skip, or record the counts, not both"), and `findings <= subjects`
  ("a finding is one of the rows the check was evaluated over").
* `VerificationDoc._check_unique` (after, `manifest.py:1417`) — one record per check; a duplicate is
  refused because "a re-run replaces rather than accumulates — merge before writing".

`VerificationRecord.producer` is the only field in the whole manifest with `first_seen = "0.7.0"`
and it lives on an `extra="forbid"` model — the one shape where an additive column is a break for a
pinned older reader.

`Closure` (`manifest.py:1169`) is the authoring-has-ended marker: `closed_at` (required),
`closed_by`, and an optional `Signature`.

`Contribution` (`manifest.py:1493`) validators: `who` non-empty; `role` via `check_vocab` against
`VALID_AUTHOR_ROLES` (closed, 4 members); `kind` against `RECOMMENDED_AUTHOR_KINDS` (**open**,
7 members) with non-empty tags.

---

## 4. The hash family — the complete roster

### Counting rule

I counted every **named function in this package whose return value IS a hash**, found by grepping
`hashlib\.`, `sha512t24u`, `def .*_signature`, `def .*digest`, `def .*binding` across
`schema/src/just_dna_format/`. That gives **22**:

* **2 byte primitives** — `sha256_bytes`, `sha256_file`;
* **4 module-level identity/attestation hashes** — `artifact_digest`, `content_signature`,
  `module_binding`, `verification_signature`;
* **1 generic fact hash** (`fact_signature`) plus **11 per-table wrappers** that only supply a field
  tuple;
* **3 VRS digests** — `sha512t24u`, `sequence_location_digest`, `derive_vrs_allele_id`;
* **1 proof-of-work digest** — `pow_digest`.

Four further functions *embed* a hash without returning one — `file_entry`, `file_entries`,
`newline_normalized_file_entry`, `newline_normalized_file_entries` — since they return a `FileEntry`
whose `sha256` is computed inside.

If instead you count only *published identities* — a value that lands in a manifest field or a
`variant_key` — the number is **16**: `artifact.digest`, `content_signature`, the 11 sidecar fact
signatures, `verification.signature`, the module binding, and the VRS allele id. Any count of "the
hash family" travels with which of those two rules it used; they differ by the primitives and the
`FileEntry` builders.

`SHA256_PREFIX = "sha256:"` (`integrity.py:44`); every SHA-256 result in this package is lowercase
hex with that prefix. `_CHUNK = 1 << 20` (1 MiB) is the streaming read size.

### Group 1 — byte primitives

| Function | Input bytes | Excluded |
| --- | --- | --- |
| `sha256_bytes(data)` (`integrity.py:70`) | exactly `data` | — |
| `sha256_file(path)` (`integrity.py:75`) | the file's raw bytes, streamed | — |

### Group 2 — file entries

| Function | Input bytes | Excluded / notes |
| --- | --- | --- |
| `file_entry(dir, name)` (`integrity.py:84`) | raw file bytes; `size` is `stat().st_size` | this is what `manifest.inputs[]` and `artifact.files[]` carry |
| `newline_normalized_file_entry(dir, name)` (`integrity.py:96`) | file bytes with `\r\n` read as `\n`, **and `size` is the length of the normalized stream, not the length on disk** | BOM, trailing whitespace and a missing final newline are deliberately **not** normalized; a lone `\r` is left as-is. It exists only for `verification.module_binding` (RM82), so a `core.autocrlf` checkout cannot un-close a module. A chunked read holds a trailing `\r` back across the boundary in case it is half of a `\r\n`. |

The docstring argues explicitly against a `normalize=True` flag on `file_entries`: "a boolean that
silently changes *what a hash is over* is the opposite of that" (`integrity.py:118`).

### Group 3 — identity and attestation hashes

**`artifact_digest(files)` (`integrity.py:159`)** — the module's **byte** identity.
Bytes entering: `json.dumps(listing, sort_keys=True, separators=(",", ":"))` where `listing` is the
`[{"name", "sha256", "size"}, …]` array **sorted by name**. Excluded: everything that is not one of
those three keys per file; the order the files were listed in. The docstring carries a correction —
it said "content identity" until 2026-08-12 and that wording is wrong: "a recompile against a
different reference moves the digest while the authored content is untouched".

**`content_signature(tables, genome_build)` (`integrity.py:188`)** — the module's **content**
identity, for dedup. Bytes entering: for each filename, the sorted list of
`json.dumps(row.model_dump(mode="json", exclude_none=True, exclude=content_identity_exclusions(type(row)) or None), sort_keys=True, separators=(",", ":"))`;
files sorted by name; then **`{"genome_build": …}` appended only when the build is not
`DEFAULT_GENOME_BUILD`**.
Deliberately excluded:

* every `None` cell (`exclude_none=True`) — so an unset new optional column does not move it;
* every field marked `OUTSIDE_CONTENT_IDENTITY` — today `OverrideRow.reason`/`decided_by`/`decided_at`;
* every field declared with `stamped_identity_field` (`exclude=True`) — the
  `variant_key`/`authored_ident` pair on `HeteroplasmyRow`, `HaplotypeRow` and `PharmVariantRow`,
  the compiler-filled `alts` on the two PGx models only (`HeteroplasmyRow.alts` is **authored** and
  carries no marker), and `VariantRow.locus_index`/`locus_count`;
* the identity and display half of `module_spec.yaml` — name, version, namespace, title, colour;
* **row order** (rows are sorted by canonical JSON) and column order and cell formatting;
* the resolution outcome — rows are hashed as authored, before resolution.

**Not** excluded, and the docstring flags it as a grandfathered inconsistency:
`VariantRow.variant_key` and `VariantRow.authored_ident` are `COMPILER_MANAGED` but **not**
`exclude=True`, so they *are* inside `content_signature` (`base.py:397-404`). The comment says
un-excluding the others or excluding these would move published signatures either way, "so the
asymmetry is carried until a major".

`genome_build` is described as making the signature **reference-independent but not
build-independent** — the docstring records that the bullet used to say "build-independent", which
was false, with HFE C282Y at 6:26,093,141 (GRCh37) vs 6:26,092,913 (GRCh38) as the worked case.

**`module_binding(entries)` (`verification.py:88`)** — deliberately *is* `artifact_digest` over
whatever entries the caller passes, rather than a second canonicalization. The caller is expected to
pass `newline_normalized_file_entries` over the authored inputs.

**`verification_signature(records)` (`verification.py:107`)** — `fact_signature(records,
VERIFICATION_FACT_FIELDS)`.

### Group 4 — `fact_signature` and its eleven wrappers

`fact_signature(rows, fact_fields)` (`integrity.py:265`). Bytes entering: the **sorted** list of
`json.dumps({k: v for k, v in row.model_dump(mode="json").items() if k in fact_fields and v is not None}, sort_keys=True, separators=(",", ":"))`,
then that list re-serialized canonically. Excluded by construction: any column not named in
`fact_fields` (so `source`, `status`, `fetched_at` and every other provenance column), every `None`
value, and row order. The stated purpose is **producer-independence** — "a human-filled and a
machine-filled table with identical facts hash equal".

| Wrapper | Table | Fact tuple | n |
| --- | --- | --- | --- |
| `resolution_signature` (`integrity.py:440`) | `resolution.csv` | `resolution.RESOLUTION_FACT_FIELDS` | 8 |
| `frequency_signature` (`integrity.py:298`) | `frequencies.csv` | `frequency.FREQUENCY_FACT_FIELDS` | 14 |
| `gene_metrics_signature` (`integrity.py:309`) | `gene_metrics.csv` | `gene_metrics.GENE_METRICS_FACT_FIELDS` | 18 |
| `literature_signature` (`integrity.py:314`) | `literature.csv` | `literature.LITERATURE_FACT_FIELDS` | 4 |
| `gene_validity_signature` (`integrity.py:325`) | `gene_validity.csv` | `gene_validity.GENE_VALIDITY_FACT_FIELDS` | 10 |
| `clinical_assertion_signature` (`integrity.py:340`) | `clinical_assertions.csv` | `assertions.CLINICAL_ASSERTION_FACT_FIELDS` | 13 |
| `gwas_effect_signature` (`integrity.py:357`) | `gwas_effects.csv` | `gwas.GWAS_FACT_FIELDS` | 18 |
| `expression_effect_signature` (`integrity.py:376`) | `expression_effects.csv` | `expression.EXPRESSION_FACT_FIELDS` | 16 |
| `clin_sig_concordance_signature` (`integrity.py:399`) | `clin_sig_concordance.csv` | `concordance.CLIN_SIG_CONCORDANCE_FACT_FIELDS` | 6 |
| `clin_sig_authority_call_signature` (`integrity.py:413`) | `clin_sig_authority_calls.csv` | `concordance.CLIN_SIG_AUTHORITY_CALL_FACT_FIELDS` | 9 |
| `source_signature` (`integrity.py:429`) | `sources.csv` / `licensing.csv` | `sources.SOURCE_FACT_FIELDS` | 12 |

Plus `verification.verification_signature` over `VERIFICATION_FACT_FIELDS` (6), which lives in
`verification.py` rather than `integrity.py` because it hashes a JSON document rather than a CSV.
That makes **12** fact-hash call sites over **12** `*_FACT_FIELDS` tuples — the sets match exactly
(measured: the package defines 11 distinct `*_FACT_FIELDS` names in leaf modules plus
`VERIFICATION_FACT_FIELDS`; `integrity` re-exports the 11 by import).

Excluded from `VERIFICATION_FACT_FIELDS` and named as such: `detail` ("it is prose — rewording a
sentence must not move a signature") and `checked_at` ("when a pass ran is a fact about the run, not
about the module") — `verification.py:64-67`.

### Group 5 — VRS digests (`sha512`, not `sha256`)

| Function | Bytes entering | Output |
| --- | --- | --- |
| `sha512t24u(blob)` (`vrs.py:403`) | `blob` | unpadded base64url of the **first 24 bytes** of SHA-512; 24 is chosen so the encoding is exactly 32 characters with no `=` padding, which is what lets `VRS_ID_PATTERN` pin the length |
| `sequence_location_digest(chrom, start, end, build)` (`vrs.py:622`) | `_canonical({"end", "sequenceReference": {"refgetAccession", "type"}, "start", "type": "SequenceLocation"})`; `start`/`end` are **interbase** (0-based half-open) | bare digest, no `ga4gh:SL.` prefix — that bare form is what an enclosing Allele embeds |
| `derive_vrs_allele_id(chrom, start, ref, alt, build)` (`vrs.py:657`) | `_canonical({"location": <the bare SL digest>, "state": {"sequence": alt.upper(), "type": "LiteralSequenceExpression"}, "type": "Allele"})` | `"ga4gh:VA." + digest` |

`_canonical` (`vrs.py:412`) is `json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")`.
The location appears **as its own digest** — not inlined, not as a CURIE — and the docstring says
that exact shape is what reproduces the ids gnomAD serves, pinned against recorded ground truth
rather than a reading of the spec.

### Group 6 — proof of work

`pow_digest(module_hash, signature, nonce)` (`verification.py:116`) —
`hashlib.sha256(f"{module_hash}|{signature}|{nonce}".encode()).digest()`, returned **raw** (not
prefixed, not hex). Both halves are in the payload deliberately: binding to `module_hash` alone would
let the records be edited under a still-valid nonce, binding to `signature` alone would let an
attestation be lifted onto another module. `VERIFICATION_DIFFICULTY_BITS = 20` (`verification.py:85`),
justified by measurement: "~1.5M/s, and 2^20 expected trials is ~0.7s". `find_nonce`
(`verification.py:140`) returns the **smallest** nonce counting up from zero, for reproducibility —
a random nonce would make `verification.json` the one derived sidecar that cannot be reproduced.

### Signing

`signing.sign_digest(digest, private_key_pem, signed_at)` (`signing.py:54`) signs
`digest.encode("utf-8")` — the `artifact.digest` string itself, not a re-hash of anything — with
Ed25519, and returns a `Signature`. `integrity.verify_signature` (`integrity.py:52`) is the inverse
and raises `IntegrityError` on an unsupported algorithm, a public key that does not match a pinned
one, or an invalid signature. `_ALGORITHM = "ed25519"` (`signing.py:24`).

---

## 5. The tri-state inventory

The rule the code states repeatedly: an answer has three outcomes — true / false / unknown — and
**`None` is never `False`**; the unknown case is *withheld*, never reported and never negated.
Combination is **Kleene**, not withhold-on-any-unknown, because `unknown OR true` really is `true`.
The explicit statements are at `gene_validity.py:316` ("`None` is the third state and is not a
failure mode … the house algebra withholds rather than guessing (`None` is never `False`)") and
`release_records.py:402` ("`True` dominates, then `None`, then `False`. The house algebra, not
withhold-on-any-unknown").

### Sites: functions returning `bool | None`

| Function | `True` | `False` | `None` |
| --- | --- | --- | --- |
| `vrs.in_pseudoautosomal_region` (`vrs.py:446`) | the position is in a PAR | it is on X/Y and outside | no coordinate, contig is not X/Y, or the build has no PAR table. Docstring: "A caller must not read `None` as `False`: 'this row has no position' and 'this position is outside the PAR' are different facts" |
| `derive.pathogenic_from_clin_sig` (`derive.py:107`) | `clin_sig ∈ {pathogenic, likely_pathogenic}` | *never returned* | everything else — "we never fabricate a `False` a curator did not state" |
| `derive.benign_from_clin_sig` (`derive.py:115`) | `clin_sig ∈ {benign, likely_benign}` | *never returned* | everything else |
| `spec.VariantRow.effective_pathogenic` / `effective_benign` (`spec.py:907`, `914`) | the authored boolean when set, else the derived one | the authored boolean when set to `False` | neither authored nor implied |
| `release_records.DeclaredChange.reaches` (`release_records.py:154`) | not excluded by what the record states (a *necessary*, over-approximating condition) | the manifest lacks a required path — "the only one a consumer acts on" | `requires` is `None`: the record does not state its reach at all, and "a consumer keeps the change" |
| `release_records.RecompileAnswer.output_differs` (`release_records.py:366`) | any driving axis is `True` | every driving axis measured `False` | any axis is `None` and none is `True` |
| `release_records._kleene_or` (`release_records.py:402`) | either side `True` | both `False` | otherwise |

### Sites: `bool | None` columns

Measured across all 57 models (counting a field once per declaring class): **20** `bool | None`
fields and **8** bare `bool` fields. The bare ones are four distinct flags — `unresolved` (declared
on `MeasureBinRow` and inherited by its four subclasses, so it appears five times),
`compile_success`, `fully_resolved` and `human_reviewed` — all genuinely two-valued with a
`False` default.

| Field | What `None` means, per its own description |
| --- | --- |
| `SourceRow.commercial_use` / `redistribution` / `share_alike` | the terms could not be read; an unknown **warns** and does not gate |
| `Sources.commercial_use` / `redistribution` (manifest) | the module-level roll-up of the above |
| `LiteratureRow.exists` / `doi_exists` / `is_open_access` / `commercial_use` / `redistribution` / `share_alike` | nobody asked, or the registry could not answer |
| `ClinSigConcordanceRow.opposed` (`concordance.py:168`) | "`None` where the camps could not be established, which is not `False`: a subject nobody could be asked about has not been shown to be uncontroversial" |
| `GeneMetricsRow.mane_select` | the source did not say |
| `VariantRow.clinvar` / `pathogenic` / `benign` / `requires_callable` / `acmg_sf` | the author did not state it |
| `HaplotypeRow.requires_callable` / `PharmVariantRow.requires_callable` | as above |
| `ReleaseRecord.axes: dict[str, bool | None]` | per axis: moved / did not move / unmeasured |

### Sites: a third state spelled as a vocabulary member rather than `None`

* `VALID_RESOLUTION_STATUS = {resolved, not_found, ambiguous}` (`vocab.py:614`).
* `VALID_FREQUENCY_STATUS = {resolved, not_found, not_covered}` (`vocab.py:639`) — `not_covered` is
  the "the source does not cover this at all" arm, distinct from "asked and absent".
* `VALID_AUTHORITY_CALL_STATUS = {recorded, no_record, unchecked}` (`vocab.py:725`) — the field
  description spells the distinction out: "`no_record` is an established absence — asked, and it has
  nothing here. `unchecked` is nobody-asked … The two are never interchangeable, and neither is
  agreement."
* `VALID_RSID_STATUS = {live, merged, absent, withdrawn}` (`vocab.py:656`) — four members.
* `VALID_DECLARED_USE = {unstated, non_commercial, commercial}` (`vocab.py:606`) — `unstated` is the
  third state on its own axis.
* `VALID_VERIFICATION_SKIPS` (8 members, `vocab.py:879`) — every reason a check did not run, so
  "did not run" is never confused with "ran and found nothing".
* `gene_validity`'s `CURRENT` / `SUPERSEDED` / `None` (`gene_validity.py:318-319`).

### Sites: functions that withhold by returning a narrower thing

* `gene_validity.classify_currency` (`gene_validity.py:327`) returns `list[str | None]`. Two edges
  withhold for the **whole group**: a tie on `classification_date`, and any undated row in the
  group. A group of one is `CURRENT`. `superseded_groups` and `undecidable_groups`
  (`gene_validity.py:377`, `395`) report the two outcomes **separately**, because "collapsing them
  would publish one number meaning two facts".
* `findings.classify` (`findings.py:94`) — three cases, no flag: all-coded returns the full answer,
  none-coded **withholds** (`([], {})`), mixed **raises**. "An empty summary beside a non-empty
  channel reads as *not classified*, which is a different statement from *complete and short*."
  There is deliberately no catch-all bucket in any of the three.
* `vrs.sole_build_naming_contig` (`vrs.py:545`) returns `str | None` and withholds for any contig
  both builds carry.
* `binning.resolve_tiling` (`binning.py:840`) returns a `TilingResolution` NamedTuple rather than a
  string, so "inferred" and "contradicted" are separate readable properties.
* `alleles.event_profile` (`alleles.py:428`) returns `frozenset[int] | None` — `None` where the
  profile cannot be computed, which is the third state behind the hosting verdict.
* `alleles.reverse_complement` (`alleles.py:452`) returns `str | None` — `None` for anything not
  spelled in the four bases, rather than complementing a degenerate code into a base the source
  declined to name.
* `alleles.symbolic_allele_defect` (`alleles.py:179`) returns `str | None` with **two** named
  defects and `None` for both "usable" and "not a symbolic allele at all" — a parser answering one
  question, with the three-way discrimination pushed into `is_symbolic_allele` +
  `parse_symbolic_allele`.
* `vocab.vcf_field_number(namespace, key)` (`vocab.py:1103`) returns `str | None` and its docstring
  opens "Three-valued, and the third value is the common one." `None` covers a caller's own key, and
  a **bare colliding key whose two namespaces disagree** (`CN` is `A` under INFO and `1` under
  FORMAT). `AF` is named as the case that makes it load-bearing: the spec reserves `INFO/AF` and not
  `FORMAT/AF`, so answering from the one known entry "would answer a question about a field the spec
  never described".
* `normalize.parse_p_value` (`normalize.py:205`) returns `float | None`; `None` means "does not
  denote one definite value", and the docstring is explicit that "an unreadable cell is not a
  disagreement". An exact `0` and an underflowing value both read as `None`.
* `layout.resolve_sidecar` (`layout.py:131`) returns `Path | None` for "the module carries none",
  and **raises** `SidecarCollision` rather than picking when two copies exist — absent, present, and
  ambiguous as three distinct outcomes.
* `vrs.par_partner` (`vrs.py:470`) returns `tuple[str, int] | None`, withholding on a non-PAR locus
  and on another build (`test_vrs.py:300`, `:304`).

### The one place `None` is deliberately collapsed, and why

`sources.taints_commercial_use` and `taints_redistribution` (`sources.py:258`, `272`) return a bare
`bool`, and that is argued rather than overlooked: the predicate is *"does this row alone make the
module non-sellable"*, and it requires `commercial_use is False` — an identity comparison, not a
truthiness test — **and** `layer == "annotation"`. An unknown "does not taint, it warns, because
'we could not read the terms' is not a finding that they forbid anything". So the tri-state lives in
the column and the predicate is a two-valued question asked of it.

`vrs.refget_supports_build` (`vrs.py:587`) is the sibling case done the other way: it returns a bare
`bool` and the *three*-outcome question is `refget_accession`, which returns an accession, `None` for
an unmapped contig, and **raises** `UnsupportedBuildError` for an assembly with no table. The
docstring names the incident behind the split — "`sequences.verify_reference_alleles` came to swallow
a whole GRCh37 module row by row and report the pass as having run: an unbuilt assembly is a
statement about the module, an unmapped contig is a statement about one row". Both now read the same
private predicate `_build_has_refget_table` (`vrs.py:560`), added after they disagreed on `None` and
`""`.

---

## 6. The allele grammar

### What the columns are, and which of them have a grammar at all

`ALLELE_COLUMNS` is declared per model (`base.py:647`). Measured across the registry:

| Model | `ALLELE_COLUMNS` |
| --- | --- |
| `VariantRow` | `("ref", "alts", "genotype", "effect_allele")` |
| `StudyRow` | `("effect_allele",)` |
| `HeteroplasmyRow` | `("ref", "alts")` |
| `HaplotypeRow` | `("ref", "allele")` |
| `PharmVariantRow` | `("ref", "genotype")` |
| `AlleleFunctionRow` | `()` — its `allele` is a star-allele **name**, not a sequence |

`schema/tests/test_symbolic_alleles.py:207` asserts every declared allele column is a real field of
its model, and `:217` pins `AlleleFunctionRow.ALLELE_COLUMNS == ()`.

**`ref`, `alt` and `alts` have no grammar anywhere in the schema.** `alleles.py:370` states it —
"no `ref`/`alt`/`alts` column in the schema has a nucleotide grammar — eleven columns across six
models" — and gives the reason: a grammar would reject `N` alongside a genuine typo and would stop
an existing module validating (P3). So the value is accepted and the *diagnosis* improves instead.
`schema/tests/test_symbolic_alleles.py:188` pins this: a row with `ref="N"`, `alts="<FOO>,Y"` loads
and stores those values unchanged.

Exactly **two** columns run `vocab.validate_allele`: `HaplotypeRow.allele` and
`VariantRow.effect_allele` (`vocab.py:1234`, with the note that both `alleles.py` and the project
docs said "exactly one" until RM5 — "the count is what an author of a grammar change reads to size
the blast radius"). The genotype grammar is a third site, on `VariantRow` (required) and
`PharmVariantRow` (optional).

### Nucleotides

`ALLELE_PATTERN = re.compile(r"^[ACGT]+$", re.IGNORECASE)` (`vocab.py:71`). `alleles.NUCLEOTIDES`
is `frozenset("ACGT")` (`alleles.py:43`) and `vrs._BASES` is the same set (`vrs.py:117`) — three
spellings of one fact, in three modules.

`IUPAC_AMBIGUITY_CODES = frozenset("RYSWKMBDHVN")` (`alleles.py:49`) — accepted in `ref`/`alts`
(which have no grammar) and classified as `"ambiguity"` by `non_nucleotide_reason`, never expanded.
The comment records the measurement: across 4,439,382 ClinVar GRCh38 rows, `N` is the only one of
the eleven that occurs at all.

### Symbolic / structural alleles (0.6, RM5)

`SYMBOLIC_ALLELE_TYPES = {"DEL", "INS", "DUP", "INV", "CNV"}` (`alleles.py:67`) — **closed**, and
pinned by `test_symbolic_alleles.py:33`:
`assert set(SYMBOLIC_ALLELE_TYPES) == {"DEL", "INS", "DUP", "INV", "CNV"}`.
Subtypes are **open**: `RECOMMENDED_SYMBOLIC_SUBTYPES = ("CNV:TR", "DUP:TANDEM", "DEL:ME", "INS:ME")`
(`alleles.py:72`) is a recommendation only, and an unfamiliar subtype parses
(`test_symbolic_alleles.py:51` asserts `("DEL", ("SOMETHING_ELSE",), 12)`).

VCF's `##ALT=<ID=…>` declaration mechanism was **rejected** — "unasked extendability in the one layer
a human has to read" (`alleles.py:55`). `<*>` is deliberately absent from the closed five: it makes
an *observability* claim, a different axis (`alleles.py:64`).

Two patterns, and the pair is the design:

* `_SYMBOLIC_SHAPE = re.compile(r"^<")` (`alleles.py:79`) — the lenient *shape* test. The comment
  records that it was `^<[^<>]*>$` for one round, which let a missing closing bracket read as an
  ordinary allele string and reach arithmetic over characters that spell no sequence.
* `_SYMBOLIC_TOKEN = re.compile(r"^<([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)(?::([0-9]+))?>$")`
  (`alleles.py:84`) — a subtype must start with a letter and a length is all digits, "which is what
  lets the length ride inside the token instead of in a column beside it".

**The length rides inside the token** (`<DEL:1500>`, `<CNV:TR:30>`), argued at `alleles.py:90-118`
against a column: SVLEN is `Number=A` so a scalar column cannot describe `alts=<DEL:5>,<DUP:9>`; three
of the columns holding an allele have no row to hang a length on; and an authored column is full
cost under the 0.6 charter amendment.

Case: `parse_symbolic_allele` upper-cases `type` and `subtypes` but `SymbolicAllele.text` keeps the
author's spelling, and `validate_allele("<del:9>")` returns `"<del:9>"` unchanged
(`test_symbolic_alleles.py:65`).

**The layer split, stated in the code.** A *lengthless* symbolic allele (`<DEL>`) passes
`validate_allele` and is refused by the **compiler**. `vocab.py:1238`: "That split is forced, not
chosen: rejecting it at load makes the row fail to parse, which is fatal in **both** modes, and the
decided behaviour is a warning-and-drop under `best_effort`. So the schema says what the DSL can
spell and the compiler says what makes a usable rulebook."
`test_symbolic_alleles.py:168` is named `test_a_lengthless_symbolic_allele_LOADS_because_the_compiler_owns_that_refusal`.

`symbolic_allele_defect` (`alleles.py:179`) returns two reasons, kept apart:
`"unknown_type"` (opens with `<` but is not one of the five, or does not parse — `<FOO>`, `<DEL`,
`<*>`) and `"no_length"` (a real type carrying no usable length: absent, or `0`). A length of `0`
**parses** and is judged unusable separately.

### `.` and `*` — the two tokens that name no allele

`MISSING_ALLELE = "."` (`alleles.py:210`) — VCF's MISSING marker. In an ALT column it states that
*there are no alternate alleles*. `alleles.py:311` names the consequence precisely: it is an
**identity** defect, because `derive_variant_key` folds the cell in as though it were an allele, so
`alts=.` and an empty cell describe one site under `1:1:A:.` and `1:1:A` with different
`content_signature`s and no dedup between them. "The repair is to leave the cell empty."

`UNOBSERVABLE_ALLELE = "*"` (`alleles.py:232`) — VCF's allele-missing-due-to-overlapping-deletion.
`is_unobservable_allele` is an exact match on the one token, with none of `is_symbolic_allele`'s
leniency. `*` is legal **in a genotype** and refused in `HaplotypeRow.allele` /
`VariantRow.effect_allele` — `base.py:543`: "Those columns name the allele a *rule* is about, and a
rule about an allele nobody observed states nothing. A genotype is the one place the observation
itself is written down."

The docstring at `alleles.py:323` is explicit that the two may not be merged: "`.` asserts that **no
alternate allele exists** … while `*` asserts that an allele **could not be observed**".

### `non_nucleotide_reason` — five answers

`alleles.py:290`, evaluated in this order:

1. `"missing"` — the bare `.`;
2. `"unobservable"` — `*`;
3. `None` — empty, or every character in `ACGT` (after `.strip().upper()`);
4. `"symbolic"` — a well-formed symbolic allele;
5. `"ambiguity"` — every character in `ACGT ∪ IUPAC`;
6. `"notation"` — anything else: a repeat notation `AAAGGGGCG(2)`, a deletion spelling `DELTCT`, a
   typo, `<FOO>`.

Pinned verbatim at `test_symbolic_alleles.py:121-129`:
`non_nucleotide_reason("<DEL:1500>") == "symbolic"`, `("DELTCT") == "notation"`,
`("AAAGGGGCG(2)") == "notation"`, `("<FOO>") == "notation"`, `("Y") == "ambiguity"`,
`("ACGT") is None`.

`N` *inside* a longer allele is filed under `"ambiguity"` deliberately, with the measurement: 633
ClinVar records spell a known-length insertion whose interior is unknown (`alleles.py:349`).

### The genotype grammar (`base.AuthoredModel._validate_genotype`, `base.py:801`)

`GENOTYPE_SEPARATORS = "/|"` (`alleles.py:255`). A member is spellable iff
`genotype_allele_ok` (`base.py:522`) — `ALLELE_PATTERN` match, **or** `parse_symbolic_allele` is not
`None`, **or** `is_unobservable_allele`. The three arms are one function so a widening cannot be
applied to two of three.

Branch order, and each branch is argued in the source:

1. **`_GT_INDEX_CELL`** — a pasted VCF `GT` field
   (`0/1`, `0|1`, `./.`, `0/1/1`), matched at `base.py:596` by

```
^(\d+|\.)([/|](\d+|\.))*$
```

   Fenced at column 0 rather than inlined or indented: the pattern contains `]` followed by `(`,
   which `test_doc_links.py` reads as a markdown link to a file that cannot exist. The 2026-08-18
   round of this exercise hit the same constant and made the same repair. The fence must start at
   column 0 because that guard's `_FENCE` is anchored with `^```` — an indented fence is valid
   markdown and invisible to it.

   Checked **first**, ahead of the arity branch, because "a correct
   sentence aimed at the wrong defect is worse than a generic one". The message is
   `f"genotype {v!r} looks like a VCF GT field: {_GT_INDEX_DIAGNOSIS}"` where `_GT_INDEX_DIAGNOSIS`
   (`base.py:612`) is verbatim: *"those are VCF GT allele indices (0 is the record's REF, 1 the first
   ALT, 2 the second, '.' a no-call), and this column spells the alleles out instead. Translate
   against that record's own REF and ALT — with REF=C ALT=T, a GT of 0/1 is 'C/T' and 1/1 is 'T/T'.
   The indices cannot be resolved here, because a genotype cell carries no REF/ALT to count from."*
2. **Mixed separators** — a cell containing both `|` and `/` where every member is spellable is
   diagnosed as VCF's partial-phasing notation, above the arity check.
3. **Phased** (`|`): exactly two members, **not** sorted — authored order is preserved through the
   round trip. A long comment (`base.py:845-870`) records that the claim "a pipe encodes which
   homolog" was refuted by RM63, and that the replacement claim about *zygosity* was also false
   (`C|C` loads, and `1|1` is an ordinary phased homozygous call).
4. **Hemizygous**: one member.
5. **Unphased** (`/`): exactly two members, and they must be **alphabetically sorted** —
   `f"unphased genotype alleles must be alphabetically sorted: expected {'/'.join(sorted(parts))!r}, got: {v!r}"`.
6. **Three or more** slash-separated members: the arity refusal, always carrying `_PLOIDY_DIVERGENCE`
   (`base.py:619`), which states the cap at two is a decision, names VCF 4.4 §7.2 as going further,
   and explicitly promises nothing ("nothing is queued against it: a consumer that actually meets
   such a call is what would reopen the question").

`test_symbolic_alleles.py:154` pins that **all three arms** admit a symbolic allele, and `:161` that
the unphased sort rule still applies to a symbolic member.

**What the tests actually pin, versus what the code merely states.** Neither `_GT_INDEX_DIAGNOSIS`
nor `_PLOIDY_DIVERGENCE` is asserted as a whole string anywhere in `schema/tests/`; the tests pin
*fragments*, and they pin the **branch order** rather than the wording:

* `test_genotype_gt_indices.py:56-60` — `assert "VCF GT" in message`, `assert "indices" in message`,
  `assert "REF" in message and "ALT" in message`;
* `:71-72` — for `0/1/1`: `assert "VCF GT" in message` and `assert "ceiling" not in message` — the
  GT branch must win over the arity branch;
* `:78-79` — the converse, for a genuine three-allele cell: `assert "ceiling" in str(excinfo.value)`
  and `assert "VCF GT" not in str(excinfo.value)`;
* `:123` — `pytest.raises(ValueError, match="alphabetically sorted")`;
* `test_polyploid_genotype.py:65-67` — `assert "RM67" in message`, `assert "7.2" in message,
  "the message must cite the section of VCF that permits higher ploidy"`, and
  `assert genotype in message, "the refusal must quote the cell it is about"`;
* `:81` — for the mixed-separator cell: `assert "nucleotides" not in message`, i.e. the partial-
  phasing branch must not fall through to the allele-grammar message;
* `:107` — `assert "'<DEL/INS>'" in str(caught.value)`; `:119-120` — `assert "'X'" in message` and
  `assert "RM67" not in message, "a bad allele is not the ploidy divergence"`.

So the two long diagnostic constants are **stated in code and only fragment-pinned by test** — a
rewording that kept `VCF GT`, `indices`, `REF`, `ALT`, `RM67` and `7.2` would pass the suite.

`alleles.split_genotype` (`alleles.py:260`) is the public splitter — **never sorted**, empty
fragments dropped, so it is total over any string. Its docstring warns it is not a validator: it
returns `['A','G']` for `|A|G`, a cell `_validate_genotype` refuses.

### Reference-free allele algebra (`alleles.py`, 0.5 / RM31)

* `parsimony_reduce(alleles)` (`alleles.py:396`) — strips the shared flank, **right first then
  left** (the VCF trimming convention), stopping before any member is consumed past empty. Fewer
  than two distinct members is returned unchanged. Doctests pin
  `parsimony_reduce(["C","CAG"]) → ['', 'AG']` and `parsimony_reduce(["AGAG","AG"]) → ['', 'AG']` —
  ClinVar's and Ensembl's spellings of one SHOX deletion.
* `event_profile(alleles)` (`alleles.py:428`) — `frozenset[int] | None`, the length of each reduced
  allele. `None` when fewer than two distinct alleles, "a different answer from 'the profile is
  empty'". A homozygous indel genotype (`C/C`) lands there.
* `reverse_complement` (`alleles.py:452`) — `None` for anything not spelled in the four bases:
  empty, symbolic, `*`, or carrying a degenerate code. Complementing a degenerate code "would assert
  a definite base the source declined to name".
* `strand_flip_explains(genotype, ref, alts)` (`alleles.py:469`) — `True` only when **every** called
  allele complements into the locus set **and** the raw call does not already fit (so a palindromic
  SNV never reports a flip); an uncomplementable allele withholds the whole answer. The docstring
  warns: "`False` here means *not established*, never *established otherwise*, and the caller's
  message must not invert it."

`hosting_verdict`, which several of these docstrings reference, is **not in this package** — the
format tier defines the algebra and the compiler owns the verdict.

---

## 7. Identity

### `derive_variant_key` (`base.py:320`) — three cases, in precedence order

```
1. rsid is not None                      → the rsid, unchanged
2. alts given and carrying no comma      → _mint_vrs_key(...)  →  "ga4gh:VA.<32 chars>"
   (only when that returns non-None)
3. otherwise                             → "chrom:start:ref"  or  "chrom:start:ref:alts_norm"
```

`alts_norm` is `",".join(sorted(a.strip() for a in alts.split(",") if a.strip()))`, so the key is
stable regardless of authored allele order. When `alts` is empty the key is the bare
`chrom:start:ref`.

Case 2 covers **single-base substitutions only** — an indel, an MNV, a multi-allelic cell and a
contig outside the primary assembly all fall through to case 3, "because a VRS allele id is defined
over the *fully justified* allele and justifying an indel needs the reference sequence, which this
tier will never fetch (Principle 2)".

`_mint_vrs_key` (`base.py:503`) swallows `UnsupportedBuildError` and returns `None`, so a GRCh37
module keeps its coordinate key rather than failing at row-load time.

Pinned by `schema/tests/test_variant_key_freeze.py:15-18`:

```python
assert _v(rsid="rs1").variant_key == "rs1"
assert _v(chrom="1", start=100, ref="A").variant_key == "1:100:A"
assert _v(rsid="rs1", chrom="1", start=100, ref="A").variant_key == "rs1"   # rsid wins
```

and by `test_vrs.py:163` (a resolved substitution keys on its VA), `:197` (unmintable rows keep the
coordinate fallback) and `:202` (`derive_variant_key(None, "11", 5227002, "T") == "11:5227002:T"` —
**position-level matching never mints a VA**, because it is called without `alts`).

### Freezing

Two mechanisms, for two families of model:

* **`VariantRow._freeze_identity`** (`spec.py:846`) — a `mode="after"` validator, so it does not
  re-run on `model_copy`. It sets `variant_key`, `authored_ident`, `locus_index=0`, `locus_count=1`,
  **overwriting anything authored**. `test_variant_key_freeze.py:21` pins that the frozen key
  survives a `model_copy` that fills in an rsid: `assert resolved.variant_key == "1:100:A"  # NOT "rs1"`.
  `:31` pins that an authored `variant_key` is ignored.
* **`AuthoredModel._freeze_stamped_identity` + `base.stamp_identity`** (`base.py:465`, `base.py:894`)
  — for the models declaring `_KEY_INCLUDES_ALTS`: `HeteroplasmyRow` (`True`), `HaplotypeRow` and
  `PharmVariantRow` (`False`). Here the key is derived from the **authored subset only** (`cell()`
  reads a field only if its name is in `authored_ident`), so filling `chrom`/`start`/`ref`/`alts`
  later cannot re-key the row however many times it runs.

`IDENTITY_FIELDS = ("rsid", "chrom", "start", "ref", "alts")` (`base.py:379`) is the tuple
`authored_ident` records, in that order. `authored_identity(row)` (`base.py:459`) is "which of
`IDENTITY_FIELDS` this row's model declares *and* the author actually filled".

A row naming no variant at all keys as `None` (`base.py:487`) — the pre-0.5 `heteroplasmy.csv` shape.

### The build, and where it is not passed

`DEFAULT_GENOME_BUILD = "GRCh38"` (`base.py:519`), matching `ModuleSpecConfig.genome_build`'s
default deliberately. The build reaches a row through `AuthoredModel.with_genome_build()`
(`base.py:671`), which sets the **private** `_genome_build` and, for a model with
`_KEY_INCLUDES_ALTS` set, re-derives `variant_key` on the spot.

`VariantRow` deliberately does **not** join in: it leaves `_KEY_INCLUDES_ALTS` unset, keeps its own
`_freeze_identity`, and `_freeze_identity` calls `derive_variant_key(...)` **with no `build`
argument** (`spec.py:868`) — so a `VariantRow` constructed from a CSV dict takes the GRCh38 default
and the compiler is expected to re-stamp. The code says so at `base.py:684`: "a row is constructed
from a CSV dict where `module_spec.yaml` is not in scope, so the key it froze at construction took
`derive_variant_key`'s GRCh38 default … `VariantRow` deliberately does not join in — it leaves
`_KEY_INCLUDES_ALTS` unset and keeps its existing restamp".

A removed property is recorded in a comment at `spec.py:876`: `authored_key` was deleted because it
had no caller and was **build-blind** — "on a `genome_build: GRCh37` module it minted a GRCh38
`ga4gh:VA.…`, the exact identity falsification the 2026-08-06 sweep found in four other places".

### VRS allele ids (`vrs.py`)

`VRS_ALLELE_PREFIX = "ga4gh:VA."` (`vrs.py:33`);
`VRS_ID_PATTERN = ^ga4gh:(VA|SL|SQ|CX|CN)\.[A-Za-z0-9_-]{32}$` (`vrs.py:37`);
`CAID_PATTERN = ^CA\d+$` (`vrs.py:39`); `VRS_SPEC_VERSION = "2.0"` (`vrs.py:45`).

`derive_vrs_allele_id` returns `None` — never guesses — for: no coordinate; an indel or MNV;
a multi-allelic `alt` (a VA names *one* allele, "so the caller must split first — silently picking
one would be a data error wearing an id"); a contig outside the primary assembly; a position past
the contig's end; `start < 1`. It **raises** `UnsupportedBuildError` for exactly one input, a build
with no refget table, and the docstring insists this must not be softened to `None`: "`None` here
means 'this row is not mintable', a per-row fact, while an unknown build means the caller's whole
frame of reference is unavailable".

`test_vrs.py:80` pins the consequence the code calls out: **a VA does not encode `ref`** —
`derive_vrs_allele_id("11", 5227002, "T", "A") == derive_vrs_allele_id("11", 5227002, "C", "A")`.
`test_vrs.py:72` pins that `chr11`/`11` and `chrM`/`M`/`MT` mint the same id.
`test_vrs.py:221` cross-checks the stdlib implementation against the reference `ga4gh.vrs` library,
and `:244` against the public SeqRepo — both opt-in.

**One id per ALT, as a parallel array.** `split_vrs_ids` / `join_vrs_ids` (`vrs.py:714`, `737`) make
`vrs_id` a comma-joined array positionally parallel to `alts`, with an **empty member kept** as a
real value meaning "this allele's id could not be minted". `join_vrs_ids` returns `None` rather than
`",,"` when nothing was minted. The docstring records the cost of the rejected alternative: minting
nothing for a multi-allelic row "cost the id on 909 of 1,613 rows in one real module while every
input needed to compute all 2,110 of them sat in the same row".

Three validators, at three strictnesses (`vrs.py:748`, `761`, `778`):

* `validate_vrs_id` — well-formedness only, **any** of the five VRS types. Deliberately lenient.
* `validate_vrs_allele_id` — well-formed **and** `ga4gh:VA.`. Used by `ResolutionRow.vrs_id` and
  `FrequencyRow.vrs_id`. The docstring records the measurement legalizing the tightening: "a probe
  across all sixteen reference examples found **844 ids, every one `ga4gh:VA.`, zero of the other
  four types".
* `validate_vrs_id_list` — member by member, returning the canonical joined spelling. Alignment with
  `alts` is **not** checked here because "a field validator cannot see a sibling field — so
  `ResolutionRow` checks the count itself".

`validate_caid` (`vrs.py:808`) validates a ClinGen canonical allele id.

`vrs_id` is **outside** `RESOLUTION_FACT_FIELDS`, so widening it moved no signature (`vrs.py:731`).

### Contig geometry, PAR, and build inference (`vrs.py`)

* `PRIMARY_CONTIG_LENGTHS` (`vrs.py:134`) and `CONTIGS_ONLY_IN` (`vrs.py:176`) — per build.
* `REFGET_GRCh38` / `REFGET_GRCh38_LENGTHS` — `test_vrs.py:126` asserts both cover exactly the
  primary assembly, that every accession starts `SQ.` and is 35 characters, and that they are
  distinct.
* `normalize_chrom` (`vrs.py:417`) — `chr7`→`7`, `chrX`→`X`, `M`/`chrM`→`MT`, whitespace stripped,
  `""`→`None`.
* `contig_length`, `builds_containing_position`, `sole_build_naming_contig` (`vrs.py:506`, `524`,
  `545`) — the last withholds (`None`) for any contig both builds name.
* `in_pseudoautosomal_region` (`vrs.py:446`) over `PAR_GRCh38` (`vrs.py:440`: X `(10001, 2781479)`
  and `(155701383, 156030895)`; Y `(10001, 2781479)` and `(56887903, 57217415)`), and `par_partner`
  (`vrs.py:470`), which returns the **offset-matched** partner coordinate on the other contig.
  `test_vrs.py:300` pins that a non-PAR locus withholds and `:304` that another build does too.

### Module identity and versioning (`identity.py`)

| Rule | Value |
| --- | --- |
| `NAME_PATTERN` | `^[a-z][a-z0-9_]*$` |
| `NAMESPACE_PATTERN` | `^[a-z0-9]+(-[a-z0-9]+)*$` — hyphens *separate*, so `just-dna-`/`a--b` are invalid |
| `_VERSION_PATTERN` | `^(\d+)\.(\d+)\.(\d+)$` |
| `_LEGACY_PATTERN` | `^v?(\d+)$` — `v1`/`1` → `1.0.0` |
| `canonical_id(ns, name, version)` | `f"{ns}/{name}@{version}"` |

`Version` is a `@total_ordering @dataclass(frozen=True)` over `(major, minor, patch)`;
`latest(versions)` raises on an empty list rather than returning a default.

### `content_signature` as the second identity

Covered in §4. The two identities are deliberately different: `artifact.digest` **preserves**
authored row order and is byte-reproducibility; `content_signature` **sorts** rows and is a
content-dedup key (`integrity.py:229`).

---

## 8. Derived-fact tables, sidecars, and the release / verification / overlay / resolution models

### Where a sidecar lives, and what it may be called (`layout.py`)

`layout.py` is "the standard library and two tuples of names" (`layout.py:8`). It fetches, parses and
validates nothing.

* `SOURCES_CSV = "sources.csv"`, `LICENSING_CSV = "licensing.csv"` (`layout.py:45-46`);
  `VERIFICATION_JSON = "verification.json"` (`layout.py:55`).
* `SIDECAR_SPELLINGS = {SOURCES_CSV: (SOURCES_CSV, LICENSING_CSV)}` (`layout.py:59`) — deprecated
  first, preferred last. A sidecar absent from the map has exactly one spelling, its own name.
* `DEPRECATED_SPELLINGS = {SOURCES_CSV}` (`layout.py:67`) — warn-only in both modes, removal queued
  for 1.0. The comment records the whole reasoning: the file records licence *terms*, and its own
  `source` column collides with four other tables' `source`; renaming in a minor means 1.0 only has
  to **remove** a spelling rather than add one. What could not come along and is a knowingly-taken
  cost: `sources.parquet` is inside `artifact.digest` and `manifest.sources` is a published key, so
  for the whole 0.x tail a module reads `licensing.csv` → `sources.parquet` → `manifest.sources`.
* `DERIVED_SUBDIR = "derived"` (`layout.py:87`) — **tolerated, never required, never canonical**.
  One fixed name rather than "search any subdirectory", because walking the tree would blind the
  near-miss guard that catches a mistyped table name.
* `SidecarCollision(ValueError)` (`layout.py:90`) — two files claiming to be one sidecar is an
  **error**, not a merge and not newest-wins: "two copies are two legitimate claims and picking one
  discards somebody's work without saying so".
* API: `sidecar_spellings`, `preferred_spelling`, `is_deprecated_spelling`, `sidecar_candidates`,
  `resolve_sidecar` (returns the single existing copy or `None`), `sidecar_relative_names`,
  `sidecar_write_path` (the copy that exists, else the preferred spelling), `deprecation_notice`,
  `atomic_write_text`, `atomic_writer` (a context manager whose writes land only if the block
  completes).

### The eleven derived-fact tables

Every one is a plain `BaseModel` with `extra="forbid"` — **not** an `AuthoredModel`, because a
machine writes it. Each declares `_KEY_FIELDS` for `base.merge_key`, carries the provenance trio
`source` / `status` / `fetched_at` outside its fact set, and has a `*_FACT_FIELDS` tuple and a
manifest block.

| CSV | Model | `_KEY_FIELDS` | since |
| --- | --- | --- | --- |
| `resolution.csv` | `ResolutionRow` (`resolution.py:50`) | `("variant_key",)` | 0.5.0 |
| `frequencies.csv` | `FrequencyRow` (`frequency.py:66`) | `("variant_key", "population")` | 0.5.0 |
| `gene_metrics.csv` | `GeneMetricsRow` (`gene_metrics.py:126`) | `("gene", "dataset")` | 0.5.0 |
| `literature.csv` | `LiteratureRow` (`literature.py:79`) | `("pmid",)` | 0.5.0 |
| `sources.csv` / `licensing.csv` | `SourceRow` (`sources.py:85`) | `("source", "layer")` | 0.5.0 |
| `gene_validity.csv` | `GeneValidityRow` (`gene_validity.py:83`) | `("assertion_id",)`, fallback `("gene", "disease_id", "moi", "submitter", "dataset")` | 0.6.0 |
| `clinical_assertions.csv` | `ClinicalAssertionRow` (`assertions.py:78`) | `("variant_key", "variation_id")` | 0.6.0 |
| `gwas_effects.csv` | `GwasEffectRow` (`gwas.py:86`) | `("association_id",)` | 0.6.0 |
| `expression_effects.csv` | `ExpressionEffectRow` (`expression.py:115`) | `("variant_key", "gene")` | 0.7.0 |
| `clin_sig_concordance.csv` | `ClinSigConcordanceRow` (`concordance.py:108`) | `("variant_key", "genotype")` | 0.7.0 |
| `clin_sig_authority_calls.csv` | `ClinSigAuthorityCallRow` (`concordance.py:227`) | `("variant_key", "genotype", "authority")` | 0.7.0 |

`GeneValidityRow` is the only model with a **two-level** key: `merge_key` (`base.py:124`) tags the
tuple `("id", …)` when any primary member is non-null and `("grain", …)` when every one is null, "so
a grain tuple can never collide with an id that happens to equal it".

The full field tables:

#### `ResolutionRow` — `resolution.py:50`
classvars: {'_KEY_FIELDS': ('variant_key',)}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | 0.5.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `alts` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `genome_build` | `str` | defaulted | `'GRCh38'` | 0.5.0 | — | — |
| `locus_index` | `int` | defaulted | `0` | 0.5.0 | — | constraints=Ge(ge=0) |
| `vrs_id` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `vrs_spec` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `caid` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `authority` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.5.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `rsid_alternates` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `rsid_current` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `rsid_status` | `str | None` | optional | `None` | 0.5.0 | `rsid_status` closed=True: `absent`, `live`, `merged`, `withdrawn` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.5.0 | — | — |

#### `FrequencyRow` — `frequency.py:66`
classvars: {'_KEY_FIELDS': ('variant_key', 'population')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | 0.5.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `alt` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `genome_build` | `str` | defaulted | `'GRCh38'` | 0.5.0 | — | — |
| `population` | `str` | required | — | 0.5.0 | — | — |
| `allele_count` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `allele_number` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `homozygote_count` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `hemizygote_count` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `faf95` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0);Le(le=1.0) |
| `dataset` | `str` | required | — | 0.5.0 | — | — |
| `vrs_id` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `caid` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.5.0 | `frequency_status` closed=True: `not_covered`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.5.0 | — | — |

#### `GeneMetricsRow` — `gene_metrics.py:126`
classvars: {'_KEY_FIELDS': ('gene', 'dataset')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `gene` | `str` | required | — | 0.5.0 | — | — |
| `gene_id` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `transcript` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `mane_select` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `pli` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0);Le(le=1.0) |
| `loeuf` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0) |
| `oe_lof` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0) |
| `oe_lof_lower` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0) |
| `lof_z` | `float | None` | optional | `None` | 0.5.0 | — | — |
| `obs_lof` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `exp_lof` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0) |
| `oe_mis` | `float | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0.0) |
| `mis_z` | `float | None` | optional | `None` | 0.5.0 | — | — |
| `syn_z` | `float | None` | optional | `None` | 0.5.0 | — | — |
| `constraint_flags` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `haploinsufficiency` | `str | None` | optional | `None` | 0.5.0 | `dosage_sensitivity` closed=True: `autosomal_recessive`, `dosage_sensitivity_unlikely`, `little_evidence`, `no_evidence`, `some_evidence`, `sufficient_evidence` | — |
| `triplosensitivity` | `str | None` | optional | `None` | 0.5.0 | `dosage_sensitivity` closed=True: `autosomal_recessive`, `dosage_sensitivity_unlikely`, `little_evidence`, `no_evidence`, `some_evidence`, `sufficient_evidence` | — |
| `dataset` | `str` | required | — | 0.5.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.5.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.5.0 | — | — |

#### `LiteratureRow` — `literature.py:79`
classvars: {'_KEY_FIELDS': ('pmid',)}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `pmid` | `str` | required | — | 0.5.0 | — | — |
| `doi` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `pmcid` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `exists` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `is_open_access` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `license` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `share_alike` | `bool | None` | optional | `None` | 0.6.0 | — | — |
| `commercial_use` | `bool | None` | optional | `None` | 0.6.0 | — | — |
| `redistribution` | `bool | None` | optional | `None` | 0.6.0 | — | — |
| `quotes_authored` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `quotes_found` | `int | None` | optional | `None` | 0.5.0 | — | constraints=Ge(ge=0) |
| `quote_source` | `str | None` | optional | `None` | 0.5.0 | `quote_source` closed=True: `abstract`, `fulltext` | — |
| `doi_exists` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `doi_checked` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.5.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.5.0 | — | — |

#### `SourceRow` — `sources.py:85`
classvars: {'_KEY_FIELDS': ('source', 'layer')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `source` | `str` | required | — | 0.5.0 | — | — |
| `layer` | `str` | required | — | 0.5.0 | `source_layer` closed=True: `annotation`, `clinical_assertion`, `expression_effect`, `frequency`, `gene_metrics`, `gene_validity`, `gwas_effect`, `literature`, `resolution` | — |
| `license` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `license_url` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `license_sha256` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `attribution` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `notice` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `share_alike` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `commercial_use` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `redistribution` | `bool | None` | optional | `None` | 0.5.0 | — | — |
| `declared_use` | `str | None` | optional | `None` | 0.5.0 | `declared_use` closed=True: `commercial`, `non_commercial`, `unstated` | — |
| `dataset` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `fetched_at` | `str | None` | optional | `None` | 0.5.0 | — | — |
| `draft_digest` | `str | None` | optional | `None` | 0.6.0 | — | — |

#### `GeneValidityRow` — `gene_validity.py:83`
classvars: {'_KEY_FIELDS': ('assertion_id',), '_KEY_FALLBACK_FIELDS': ('gene', 'disease_id', 'moi', 'submitter', 'dataset')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `gene` | `str` | required | — | 0.6.0 | — | — |
| `gene_id` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `disease_id` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `disease_label` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `moi` | `str | None` | optional | `None` | 0.6.0 | `inheritance_mode` closed=True: `autosomal_dominant`, `autosomal_recessive`, `mitochondrial`, `semidominant`, `undetermined`, `x_linked`, `x_linked_dominant`, `x_linked_recessive`, `y_linked` | — |
| `classification` | `str | None` | optional | `None` | 0.6.0 | `gene_validity` closed=True: `animal_model_only`, `definitive`, `disputed`, `limited`, `moderate`, `no_known_disease_relationship`, `refuted`, `strong`, `supportive` | — |
| `classification_raw` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `classification_date` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `submitter` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `assertion_id` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `report_url` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `dataset` | `str` | required | — | 0.6.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.6.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.6.0 | — | — |

#### `ClinicalAssertionRow` — `assertions.py:78`
classvars: {'_KEY_FIELDS': ('variant_key', 'variation_id')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | 0.6.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.6.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `alt` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `genome_build` | `str` | defaulted | `'GRCh38'` | 0.6.0 | — | — |
| `clin_sig` | `str | None` | optional | `None` | 0.6.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `clin_sig_raw` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `review_status` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `review_stars` | `int | None` | optional | `None` | 0.6.0 | — | constraints=Ge(ge=0);Le(le=4) |
| `condition` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `variation_id` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `dataset` | `str` | required | — | 0.6.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.6.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.6.0 | — | — |

#### `GwasEffectRow` — `gwas.py:86`
classvars: {'_KEY_FIELDS': ('association_id',)}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `association_id` | `str` | required | — | 0.6.0 | — | — |
| `variant_key` | `str` | required | — | 0.6.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `effect_allele` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `effect_size` | `float | None` | optional | `None` | 0.6.0 | — | — |
| `effect_measure` | `str | None` | optional | `None` | 0.6.0 | `effect_measure` closed=False: `HR`, `NR`, `OR`, `RR`, `beta`, `log(HR)`, `log(OR)` | — |
| `effect_unit` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `effect_direction` | `str | None` | optional | `None` | 0.6.0 | `effect_direction` closed=True: `decrease`, `increase` | — |
| `standard_error` | `float | None` | optional | `None` | 0.6.0 | — | constraints=Ge(ge=0) |
| `confidence_interval` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `risk_allele_frequency` | `float | None` | optional | `None` | 0.6.0 | — | constraints=Ge(ge=0);Le(le=1) |
| `p_value` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `p_value_num` | `float | None` | optional | `None` | 0.6.0 | — | constraints=Gt(gt=0);Le(le=1) |
| `trait` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `trait_efo_id` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `pmid` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `study_accession` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `ancestry` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `dataset` | `str` | required | — | 0.6.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.6.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.6.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.6.0 | — | — |

#### `ExpressionEffectRow` — `expression.py:115`
classvars: {'_KEY_FIELDS': ('variant_key', 'gene')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | 0.7.0 | — | — |
| `rsid` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `chrom` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `start` | `int | None` | optional | `None` | 0.7.0 | — | constraints=Ge(ge=0) |
| `ref` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `alt` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `gene` | `str` | required | — | 0.7.0 | — | — |
| `gene_id` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `effect_size` | `float | None` | optional | `None` | 0.7.0 | — | — |
| `effect_measure` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `effect_unit` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `effect_direction` | `str | None` | optional | `None` | 0.7.0 | `effect_direction` closed=True: `decrease`, `increase` | — |
| `tracks_agreeing` | `int | None` | optional | `None` | 0.7.0 | — | constraints=Ge(ge=0) |
| `tracks_total` | `int | None` | optional | `None` | 0.7.0 | — | constraints=Ge(ge=0) |
| `distance_to_gene` | `int | None` | optional | `None` | 0.7.0 | — | constraints=Ge(ge=0) |
| `dataset` | `str` | required | — | 0.7.0 | — | — |
| `source` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `status` | `str | None` | optional | `None` | 0.7.0 | `resolution_status` closed=True: `ambiguous`, `not_found`, `resolved` | — |
| `fetched_at` | `str | None` | optional | `None` | 0.7.0 | — | — |

#### `ClinSigConcordanceRow` — `concordance.py:108`
classvars: {'_KEY_FIELDS': ('variant_key', 'genotype')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | 0.7.0 | — | — |
| `genotype` | `str` | required | — | 0.7.0 | — | — |
| `authored_clin_sig` | `str | None` | optional | `None` | 0.7.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `authority_concordance` | `str` | required | — | 0.7.0 | `authority_concordance` closed=True: `concordant`, `discordant`, `none`, `single`, `unchecked` | — |
| `authored_position` | `str` | required | — | 0.7.0 | `authored_position` closed=True: `absent`, `matches_all`, `matches_none`, `matches_some`, `unchecked` | — |
| `opposed` | `bool | None` | optional | `None` | 0.7.0 | — | — |
| `checked_at` | `str | None` | optional | `None` | 0.7.0 | — | — |

#### `ClinSigAuthorityCallRow` — `concordance.py:227`
classvars: {'_KEY_FIELDS': ('variant_key', 'genotype', 'authority')}

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `variant_key` | `str` | required | — | 0.7.0 | — | — |
| `genotype` | `str` | required | — | 0.7.0 | — | — |
| `authority` | `str` | required | — | 0.7.0 | — | — |
| `status` | `str` | required | — | 0.7.0 | `authority_call_status` closed=True: `no_record`, `recorded`, `unchecked` | — |
| `clin_sig` | `str | None` | optional | `None` | 0.7.0 | `clin_sig` closed=True: `affects`, `association`, `benign`, `conflicting`, `drug_response`, `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`, `risk_factor`, `uncertain_significance` | — |
| `clin_sig_raw` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `confidence` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `confidence_unit` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `dataset` | `str | None` | optional | `None` | 0.7.0 | — | — |
| `checked_at` | `str | None` | optional | `None` | 0.7.0 | — | — |

**Fact-row validators worth naming.**

* `ResolutionRow._vrs_ids_align_with_alts` (after, `resolution.py:235`) — the parallel-array
  invariant: `len(split_vrs_ids(vrs_id)) == len(alts.split(","))`, checked **only when both are
  filled**. A `vrs_id` on a row with no `alts` is "under-specified, not contradictory, and refusing
  it would be this tier inventing a rule".
* Every fact row canonicalizes `fetched_at` / `checked_at` through
  `normalize.normalize_utc_timestamp` in a `mode="before"` validator.
* `gene_metrics.normalize_constraint_flags` (`gene_metrics.py:66`, bound `mode="before"`) — folds
  gnomAD's two encodings (a Python list from GraphQL, a JSON-array *literal* from the bulk TSV) to
  one sorted pipe-joined string, `None` for empty. The docstring carries the measurement: over
  18,111 v4.1 snapshot rows, **not one** is null — 17,403 carry `"[]"` and 708 carry a real array
  literal, so `if row.constraint_flags:` read 100% of rows as flagged where the true figure is 3.9%.
  It lives in this tier rather than the enricher on purpose: "the normalization goes in the CELL",
  so it reaches a hand-written table and a re-read of a file an earlier release wrote.
  A string that starts like an array and does not parse is kept **verbatim**.
* `SourceRow._reject_template_placeholders` (before, `sources.py:114`) — the `<<REPLACE>>` guard,
  which the fact models otherwise do not get (they are not `AuthoredModel`s).
* `sources.taints_commercial_use` / `taints_redistribution` (`sources.py:258`, `272`) — both require
  `layer == "annotation"`; only the annotation layer carries a derivative-work obligation, because
  "the fact sidecars report facts, not expression" (`sources.py:127`). `redistribution` is recorded
  and summarized and **deliberately not gated** in any package (`sources.py:279`): "a distribution
  right is not a *use*, so the three-state `unstated|non_commercial|commercial` axis has nothing to
  say about it … the act is a publish — which happens downstream, in a registry, not in a compile."

### `verification.json` — the attestation (`verification.py`)

The document is `manifest.VerificationDoc`; the manifest block is `manifest.Verification`; the
behaviour lives in `verification.py`.

| Function | Does |
| --- | --- |
| `module_binding(entries)` (88) | `artifact_digest` over the caller's file entries — the authored inputs, newline-normalized |
| `verification_signature(records)` (107) | `fact_signature(records, VERIFICATION_FACT_FIELDS)` |
| `pow_digest` / `leading_zero_bits` / `meets_difficulty` / `find_nonce` (116–140) | the proof of work; `VERIFICATION_DIFFICULTY_BITS = 20` |
| `close(...)` (155) | builds a `Closure`, optionally Ed25519-signed |
| `attest(...)` (184) | builds a `VerificationDoc` with its nonce |
| `attestation_failure(...)` (226) | why an attestation does not hold, or `None` |
| `verification_block(doc)` (284) | `VerificationDoc` → `manifest.Verification` |
| `merge_records(...)` (301) | a re-run **replaces** a record rather than accumulating |
| `read_verification` / `write_verification` (354, 359) | I/O |

### `overrides.csv` — the overlay (`overrides.py`)

Covered in §2 as an authored model. The module additionally owns the application machinery:
`OverlayTarget` / `OVERRIDABLE_TABLES` (the nine-table registry), `_key_groups`, `_spelling_errors`,
`_unmatched_warnings`, `_suppression_warnings`, `_canonical_key_cell` and `_rebuild`.

Two design statements the code makes explicitly:

* `_rebuild` (`overrides.py:446`) reconstructs the row **through the model** rather than mutating a
  field, so "the value lands under the column's own type, every field validator runs against it, and
  so does every cross-field one".
* `_canonical_key_cell` (`overrides.py:460`) matches an overlay key **as the model stores it**, not
  as the author spelled it, "because a table of rules is a second copy of every validator — and
  `population` was only …" (the comment names the case that forced it).

### Release records (`release_records.py`)

`ReleaseRecord` (`release_records.py:203`) and `DeclaredChange` (`release_records.py:89`), both
`extra="forbid"`:

#### `DeclaredChange` — `release_records.py:89`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `axis` | `str` | required | — | — | `release_output_axis` closed=True: `content_signature`, `manifest_fields`, `parquet_bytes`, `parquet_schema`, `warnings` | — |
| `target` | `str` | required | — | — | — | — |
| `kind` | `str` | required | — | — | `release_change_kind` closed=True: `addition`, `correction` | — |
| `detail` | `str` | required | — | — | — | — |
| `item` | `str | None` | optional | `None` | — | — | — |
| `requires` | `tuple[str, ...] | None` | optional | `None` | — | — | — |

#### `ReleaseRecord` — `release_records.py:203`

| field | type | req | default | first_seen | vocabulary | notes |
| --- | --- | --- | --- | --- | --- | --- |
| `version` | `str` | required | — | — | — | — |
| `previous` | `str` | required | — | — | — | — |
| `axes` | `dict[str, bool | None]` | required | — | — | — | — |
| `manifest_fields` | `list[str]` | defaulted | factory `list` | — | — | — |
| `declared` | `list[release_records.DeclaredChange]` | defaulted | factory `list` | — | — | — |
| `unmeasured` | `list[str]` | defaulted | factory `list` | — | — | — |
| `evidence` | `str` | required | — | — | — | — |

* `VALID_RELEASE_OUTPUT_AXES` (`vocab.py:1329`) — `content_signature`, `manifest_fields`,
  `parquet_bytes`, `parquet_schema`, `warnings` (5, closed).
* `NON_RECOMPILE_AXES = {"warnings"}` and
  `RECOMPILE_DRIVING_AXES = VALID_RELEASE_OUTPUT_AXES - NON_RECOMPILE_AXES` (`release_records.py:62`)
  — **derived by subtraction rather than restated**, so a new axis joins the driving set unless
  explicitly excluded, "the safe default for a staleness signal".
* `ReleaseRecord.axes` must name **every** axis; a validator raises
  `f"axes must name every release output axis; missing: {missing}"` (`release_records.py:292`).
  The reasoning: "A record silent about an axis and a record saying `None` about it are the same
  claim, and making the silence illegal is what forces a new axis to be answered."
* `EXCLUDED_MANIFEST_FIELDS` (`release_records.py:72`) — 9 entries, each with its reason in the
  value. `compilation.compiler_version` is named as "the trap and it is not hypothetical: it moves
  on **every** release by construction". `compilation.carried` and `compilation.warnings_summary`
  are excluded because they are derived from `compilation.warnings`.
* `release_version(stamp)` (`release_records.py:299`) accepts `0.7.0` or
  `just-dna-compiler 0.7.0` and **raises** on anything else — including
  `just-dna-compiler unknown` — because "a malformed version is a caller bug, not an unknown *fact*".
* `RecompileAnswer` (`release_records.py:330`) is a frozen dataclass of facts, explicitly "not a
  verdict". It carries `out_of_span_manifest_fields` / `out_of_span_declared` **withheld rather than
  dropped**, since folding an overshooting link's evidence into the main tuples "would contradict
  the axis in the same object".
* `declared_for(manifest)` (`release_records.py:387`) drops a change only where `reaches` answers
  `False`; an unstated reach is **kept**, "the cost of keeping one it did not need is one version
  number, where the cost of dropping one it needed is a module serving a value we have said is
  wrong".

---

## 9. Vocabularies

### The mechanism

Per CONSTITUTION Principle 6, as the code states it (`vocab.py:6`): "constrained vocabularies are
`frozenset[str]` + a validator, never `Enum`/`Literal`". A binding is declared with
`base.vocabulary(name, options, closed=…, notes=…)` (`base.py:189`), which puts the **members
themselves** on the field rather than a name to look up — "a name would need a central registry, and
the vocabularies deliberately live in the leaves that own them … `vocab` cannot import `pgx`".

Two binding sites, both reported by `base.field_vocabularies`:

1. a `vocabulary()` marker in the field's own `json_schema_extra`;
2. membership in `base.SHARED_VOCABULARIES` (`base.py:229`), enforced by `AuthoredModel`'s
   `_validate_shared_vocabulary` — five entries: `direction`, `clin_sig`, `stat_significance`,
   `evidence_level`, and (derived from `VCF_POINTER_COMPANIONS`, not listed) `source_element`.
   `SHARED_VOCABULARY_NOTES` carries per-member prose for `source_element` only; the other four
   "need none — `risk`, `1A`, `pathogenic` and `significant` are each their own definition"
   (`base.py:246`).

`test_reference.test_declared_closed_options_are_exactly_what_is_accepted` is named in the source
(`base.py:751`) as the guard that "discovers enforcement by *behaviour*, so it cannot be satisfied by
the declaration it is checking".

### Separator normalization

`match_vocab(value, vocab)` (`vocab.py:1177`) treats `-` and `_` as the same separator. The **exact
value is tried first**, then `value.replace("-","_")`, then `value.replace("_","-")`. It returns the
**canonical member**, "so the stored cell is always the declared spelling".

`check_vocab(value, vocab, field_name)` (`vocab.py:1203`) passes `None` through (absent = unknown),
canonicalizes through `match_vocab`, and raises
`f"{field_name} must be one of {sorted(vocab)}, got: {value!r}"`.

The **return value is load-bearing** and the code says so twice: `binning._validate_measure_kind`
(`binning.py:400`) and `pgs._validate_ancestry` (`pgs.py:103`) both record RM95 — a validator that
calls `check_vocab` for its raising side effect alone stores the author's raw spelling inside
`content_signature`.

Multi-valued cells split on `MULTI_SEP = re.compile(r"[,;|]")` (`vocab.py:76`).

### The declared bindings — 41 distinct vocabulary names across the registry

Measured by walking `reference._ALL_MODELS` through `base.field_vocabularies`.

| Vocabulary | Closed | n | Bound to |
| --- | --- | --- | --- |
| `actionability` | yes | 7 | `VariantRow.actionability` |
| `author_kind` | **no** | 7 | `Contribution.kind` |
| `author_role` | yes | 4 | `Contribution.role` |
| `authored_position` | yes | 5 | `ClinSigConcordanceRow.authored_position` |
| `authority_call_status` | yes | 3 | `ClinSigAuthorityCallRow.status` |
| `authority_concordance` | yes | 5 | `ClinSigConcordanceRow.authority_concordance` |
| `chromosome` | yes | 25 | `VariantRow.chrom` |
| `clin_sig` | yes | 13 | 10 fields across 10 models |
| `declared_use` | yes | 3 | `SourceRow.declared_use` |
| `direction` | yes | 5 | 7 fields (shared validator) |
| `dosage_sensitivity` | yes | 6 | `GeneMetricsRow.haploinsufficiency`, `.triplosensitivity` |
| `effect_direction` | yes | 2 | `ExpressionEffectRow`, `GwasEffectRow` |
| `effect_measure` | **no** | 7 | `GwasEffectRow`, `StudyRow`, `VariantRow` |
| `evidence_level` | yes | 6 | `DiplotypeRow`, `PharmVariantRow` (shared validator) |
| `frequency_status` | yes | 3 | `FrequencyRow.status` |
| `function_status` | yes | 6 | `AlleleFunctionRow.function_status` |
| `gene_validity` | yes | 9 | `GeneValidityRow.classification` |
| `icon_set` | yes | 2 | `Display.icon_set`, `ModuleInfo.icon_set` |
| `inheritance_mode` | yes | 9 | `GeneValidityRow.moi` |
| `measure_kind` | yes | 5 | `MeasureBinRow.measure_kind` |
| `measure_kind_activity_score` / `_allele_fraction` / `_copy_number` / `_repeat_count` | yes | 1 each | the four binning subclasses |
| `measure_tiling` | yes | 2 | 5 binning fields |
| `overridable_table` | yes | 9 | `OverrideRow.table` |
| `override_operation` | yes | 3 | `OverrideRow.operation` (+notes) |
| `phenotype_category` | yes | 6 | `PharmVariantRow.phenotype_category` |
| `quote_source` | yes | 2 | `LiteratureRow.quote_source` |
| `recommendation_strength` | yes | 4 | `DiplotypeRow.recommendation_strength` |
| `research_tier` | yes | 2 | `PgsRow.research_tier` |
| `reserved_flags` | **no** | 3 | `VariantRow.flags` |
| `resolution_status` | yes | 3 | 7 `status` fields |
| `rsid_status` | yes | 4 | `ResolutionRow.rsid_status` |
| `source_element` | yes | 8 | 5 binning fields (+notes, shared validator) |
| `source_layer` | yes | 9 | `SourceRow.layer` |
| `stat_significance` | yes | 4 | `StudyRow`, `VariantRow` (shared validator) |
| `state` | yes | 6 | `VariantRow.state` |
| `training_ancestry` | yes | 6 | `PgsRow.training_ancestry` |
| `verification_check` | yes | 26 | `VerificationRecord.check` |
| `verification_skip` | yes | 8 | `VerificationRecord.skipped` |

**Three** of the 41 are open (`closed=False`): `author_kind`, `effect_measure`, `reserved_flags`.
The other 38 are closed. Note `actionability`, whose backing constant is named `ACTIONABILITY_SEED`
and which is nonetheless declared and enforced `closed=True` — see §11.

`warning_code` is a 42nd marker, on `Compilation.warnings_summary` in `manifest.py` — not counted
above because `Compilation` is outside `_ALL_MODELS`.

### Every module-level `frozenset[str]` constant

Measured by walking each module's namespace.

| Constant | File:line | n | Members |
| --- | --- | --- | --- |
| `NUCLEOTIDES` | `alleles.py:43` | 4 | A C G T |
| `IUPAC_AMBIGUITY_CODES` | `alleles.py:49` | 11 | B D H K M N R S V W Y |
| `SYMBOLIC_ALLELE_TYPES` | `alleles.py:67` | 5 | CNV DEL DUP INS INV |
| `VALID_MEASURE_KINDS` | `binning.py:157` | 5 | activity_score, allele_fraction, copy_number, prs_percentile, repeat_count |
| `VALID_MEASURE_TILINGS` | `binning.py:170` | 2 | continuous, quantised |
| `_INTEGER_KINDS` | `binning.py:175` | 2 | copy_number, repeat_count |
| `_CONTINUOUS_GAP_KINDS` | `binning.py:176` | 2 | allele_fraction, prs_percentile |
| `_DENSE_KINDS` | `binning.py:185` | 2 | allele_fraction, prs_percentile |
| `LEGACY_MT_REFERENCE_BASES` | `binning.py:608` | 1 | NC_001807 |
| `CANONICAL_MT_REFERENCE_SEQUENCES` | `binning.py:609` | 1 | NC_012920.1 |
| `_FLAG_NULLS` | `gene_metrics.py:63` | 7 | `""`, NA, NaN, None, na, nan, null |
| `DEPRECATED_SPELLINGS` | `layout.py:67` | 1 | sources.csv |
| `VALID_ICON_SETS` | `manifest.py:47` | 2 | awesome, fomantic |
| `LOGO_EXTENSIONS` | `manifest.py:49` | 3 | jpeg, jpg, png |
| `README_EXTENSIONS` | `manifest.py:54` | 3 | md, rst, txt |
| `IDENTITY_AUTHORITY_KEYS` | `normalize.py:50` | 3 | canonical_id, namespace, owner |
| `PRESENTATION_AUTHORITY_KEYS` | `normalize.py:85` | 1 | short_description |
| `VALID_OVERRIDE_TABLES` | `overrides.py:165` | 9 | derived from `OVERRIDABLE_TABLES` |
| `VALID_OVERRIDE_OPERATIONS` | `overrides.py:174` | 3 | insert, suppress, update |
| `LOSSY_OVERLAY_TABLES` | `overrides.py:778` | 2 | literature.csv, resolution.csv |
| `VALID_TRAINING_ANCESTRY` | `pgs.py:36` | 6 | AFR AMR EAS EUR SAS multi |
| `VALID_RESEARCH_TIERS` | `pgs.py:38` | 2 | calibrated, research_only |
| `VALID_FUNCTION_STATUS` | `pgx.py:70` | 6 | the CPIC function categories |
| `NON_RECOMPILE_AXES` | `release_records.py:62` | 1 | warnings |
| `RECOMPILE_DRIVING_AXES` | `release_records.py:63` | 4 | derived by subtraction |
| `VALID_STATES` | `spec.py:69` | 6 | alt neutral protective ref risk significant |
| `VALID_CHROMOSOMES` | `spec.py:70` | 25 | 1–22, X, Y, MT |
| `RESERVED_FLAGS` | `spec.py:74` | 3 | conditional, phased, pleiotropic |
| `VALID_DIRECTIONS` | `vocab.py:46` | 5 | contested neutral protective risk unknown |
| `VALID_SIGNIFICANCE` | `vocab.py:49` | 4 | not_significant significant suggestive unknown |
| `VALID_CLIN_SIG` | `vocab.py:51` | 13 | the VEP CLIN_SIG tiers |
| `VCF_NAMESPACES` | `vocab.py:97` | 2 | FORMAT, INFO |
| `VCF_COLLIDING_KEYS` | `vocab.py:115` | 7 | AD ADF ADR AF CN DP MQ |
| `VALID_ELEMENT_RULES` | `vocab.py:227` | 8 | largest/smallest/sum × bare and `_alt`, plus annotated_alt, reference |
| `RESERVED_NAMES_0_4` | `vocab.py:328` | 3 | callable_element, quality_element, reference_db |
| `VALID_EVIDENCE_LEVELS` | `vocab.py:378` | 6 | 1A 1B 2A 2B 3 4 |
| `VALID_RECOMMENDATION_STRENGTH` | `vocab.py:394` | 4 | moderate no_recommendation optional strong |
| `VALID_DOSAGE_SENSITIVITY` | `vocab.py:416` | 6 | |
| `VALID_GENE_VALIDITY` | `vocab.py:456` | 9 | |
| `VALID_INHERITANCE_MODE` | `vocab.py:495` | 9 | |
| `VALID_PHENOTYPE_CATEGORIES` | `vocab.py:517` | 6 | dosage efficacy metabolism_pk other pd toxicity |
| `VALID_SOURCE_LAYERS` | `vocab.py:564` | 9 | |
| `RECOMMENDED_EFFECT_MEASURES` | `vocab.py:588` | 7 | **open** |
| `VALID_EFFECT_DIRECTIONS` | `vocab.py:599` | 2 | decrease, increase |
| `VALID_DECLARED_USE` | `vocab.py:606` | 3 | commercial, non_commercial, unstated |
| `VALID_RESOLUTION_STATUS` | `vocab.py:614` | 3 | ambiguous, not_found, resolved |
| `VALID_FREQUENCY_STATUS` | `vocab.py:639` | 3 | not_covered, not_found, resolved |
| `VALID_RSID_STATUS` | `vocab.py:656` | 4 | absent, live, merged, withdrawn |
| `VALID_QUOTE_SOURCE` | `vocab.py:662` | 2 | abstract, fulltext |
| `VALID_AUTHORITY_CONCORDANCE` | `vocab.py:687` | 5 | concordant discordant none single unchecked |
| `VALID_AUTHORED_POSITION` | `vocab.py:711` | 5 | absent matches_all matches_none matches_some unchecked |
| `VALID_AUTHORITY_CALL_STATUS` | `vocab.py:725` | 3 | no_record, recorded, unchecked |
| `VALID_VERIFICATION_CHECKS` | `vocab.py:773` | 26 | |
| `VALID_VERIFICATION_SKIPS` | `vocab.py:879` | 8 | |
| `RECOMMENDED_ANCESTRY_GROUPS` | `vocab.py:903` | 11 | **open**: afr ami amr asj eas fin global mid nfe remaining sas |
| `VALID_AUTHOR_ROLES` | `vocab.py:952` | 4 | audited created edited reviewed |
| `RECOMMENDED_AUTHOR_KINDS` | `vocab.py:962` | 7 | **open** |
| `ACTIONABILITY_SEED` | `vocab.py:969` | 7 | |
| `VALID_RELEASE_OUTPUT_AXES` | `vocab.py:1329` | 5 | content_signature manifest_fields parquet_bytes parquet_schema warnings |
| `VALID_RELEASE_CHANGE_KINDS` | `vocab.py:1343` | 2 | addition, correction |
| `VALID_WARNING_CODES` | `vocab.py:1389` | 73 | |
| `CARRIED_WARNING_CODES` | `vocab.py:1496` | 11 | |
| `ACTIONABLE_WARNING_CODES` | `vocab.py:1520` | 62 | derived: `VALID_WARNING_CODES - CARRIED_WARNING_CODES` |
| `_BASES` | `vrs.py:117` | 4 | A C G T |

### Paired-list consistency — measured

I ran an equality/subset check over every `VALID_X` / `X_REASONS` / `ORDERED_X` / `DEFAULT_X` pair in
the package. **All the intended equalities hold.** Four pairs are unequal and all four are documented
as deliberate subsets:

| Pair | Relation | Stated reason |
| --- | --- | --- |
| `VALID_GENE_VALIDITY` (9) vs `ORDERED_GENE_VALIDITY` (4) | strict subset | "the members … that are actually ordered. `supportive` is absent because it is an assertion made off the ladder, and the three negative verdicts are absent because they are a different claim — putting `refuted` at position zero would read as 'the weakest evidence for', which inverts it" (`vocab.py:470`) |
| `VCF_FIELD_NUMBER` values vs `VCF_NUMBER_MEANINGS` keys | `{'0','1'}` missing | the meanings map covers "each **multi-valued** `Number` code"; `0` is a Flag and `1` a scalar. Measured: every value in `VCF_FIELD_NUMBER` for which `is_multi_valued_number` is true **is** in the meanings map |
| `VALID_MEASURE_KINDS` (5) vs `_VCF_MEASURE_FIELDS` (2) | subset | "for each kind this schema tiles as integral" — i.e. exactly `_INTEGER_KINDS` (`binning.py:208`) |
| `SHARED_VOCABULARIES` (5) vs `SHARED_VOCABULARY_NOTES` (1) | subset | "The other four shared vocabularies need none" (`base.py:246`) |

Checks that passed: `RESERVED_NAMES_0_4` ↔ `RESERVED_NAME_REASONS`; `VCF_COLLIDING_KEYS` ↔
`VCF_COLLISION_REASONS`; `VALID_ELEMENT_RULES` ↔ `ELEMENT_RULE_MEANINGS`;
`DOSAGE_SENSITIVITY_BY_CODE` values ≡ `VALID_DOSAGE_SENSITIVITY`; `CARRIED ⊆ VALID_WARNING_CODES`;
`VCF_POINTER_COMPANIONS` values ⊆ `VCF_POINTER_FIELDS`; `POPULATION_ORDER` ≡
`RECOMMENDED_ANCESTRY_GROUPS`; both `normalize` key/reason pairs; `VALID_MEASURE_KINDS` ≡
`DEFAULT_MEASURE_TILING` keys; `derive`'s three maps against `VALID_STATES`/`VALID_DIRECTIONS` in
both directions; `NON_RECOMPILE_AXES ⊆ VALID_RELEASE_OUTPUT_AXES`; every key of
`EXCLUDED_MANIFEST_FIELDS` names a real `ModuleManifest` path; `VALID_OVERRIDE_TABLES` ≡
`OVERRIDABLE_TABLES`; `_OPERATION_MEANINGS` ≡ `VALID_OVERRIDE_OPERATIONS`;
`LOSSY_OVERLAY_TABLES ⊆ OVERRIDABLE_TABLES`.

### Other patterns in `vocab.py` worth naming

* **Identifier patterns**: `RSID_PATTERN ^rs\d+$`, `ALLELE_PATTERN ^[ACGT]+$` (IGNORECASE),
  `TRAIT_ID_PATTERN ^[A-Za-z][A-Za-z]*[:_]\w+$`, `SOURCE_FIELD_PATTERN` (the VCF field pointer,
  built from `_VCF_KEY = (?:[A-Za-z_][0-9A-Za-z_.]*|1000G)`), `POPULATION_PATTERN ^[a-z0-9_]+$`.
* **The reserved namespace** (`vocab.py:328`): `RESERVED_NAMES_0_4 = {callable_element,
  quality_element, reference_db}`, each with a specific diagnosis in `RESERVED_NAME_REASONS`.
  `reject_reserved` (`vocab.py:1057`) runs before `extra="forbid"` so a reserved name gets a
  specific message and anything else gets the generic one.
* **`TEMPLATE_PLACEHOLDER = "<<REPLACE>>"`** (`vocab.py:980`) with `reject_template_placeholders`
  and `_placeholder_paths` reporting *where* in a nested structure the placeholder sits.
* **`reject_misplaced`** (`vocab.py:1041`) + `MISPLACED_COLUMN_REASONS` (`vocab.py:1030`) — a column
  that is real on a *generated* table but not on this one gets its own diagnosis.
* **`validate_finite`** (`vocab.py:1301`) — rejects `NaN`/`inf`.
* **`validate_phenotype_categories`** (`vocab.py:522`) — a multi-valued cell validated token by token.
* **`population_sort_key` / `normalize_population` / `validate_population`** (`vocab.py:1266`–`1282`)
  — the ancestry vocabulary is **open**: an unfamiliar label is kept, a *malformed* one (empty,
  padded, carrying a separator) is rejected. `normalize_population` folds an empty label to
  `global`, "which is how gnomAD reports the whole-dataset row".

---

## 10. Everything else the code owns

### `normalize.py` — pre-validation steps the *consumer* injects

The module states its own design rule at `normalize.py:7`: "the **consumer injects** the set", and
"a validator validates, it does not fix".

| Symbol | Behaviour |
| --- | --- |
| `IDENTITY_AUTHORITY_KEYS` (50) | `{namespace, owner, canonical_id}` — registry-stamped |
| `IDENTITY_AUTHORITY_REASONS` (53) | one reason per key |
| `PRESENTATION_AUTHORITY_KEYS` (85) | `{short_description}`, with `SHORT_DESCRIPTION_MAX_CHARS = 120` (98) |
| `strip_authority_keys(block, authority_keys)` (126) | returns `(clean, dropped)`. **Byte-preserving when nothing matches**, pure, idempotent. `authority_keys` is supplied by the caller and never hardcoded, "so the format bakes in no one consumer's conventions" |
| `reject_authority_keys(data)` (149) | a `mode="before"` diagnosis. **It diagnoses; it does not strip** — "A message is not an application … Validity is unchanged" |
| `normalize_version(raw)` (183) | strip non-`[0-9.]`, split on `.`, first three fields, empty→`0`, right-pad to three. `v2`→`2.0.0`, `1.5`→`1.5.0`, `v1.2.3-beta`→`1.2.3`, no digits→`0.0.0`. Idempotent |
| `parse_p_value(raw)` (205) | `float | None`. Returns `None` for absent/blank, a bound or a word, trailing commentary, an exact `0` ("the source's own underflow"), and an underflowing value. Accepts `5e-8`, `5E-8`, `5 × 10^-8`, `5x10-8`, plain decimals. The two regexes are **anchored on the whole string** so `5e-8 (adjusted)` is not half-read |
| `UTC_TIMESTAMP_FORMAT` (240) | `"%Y-%m-%dT%H:%M:%SZ"` |
| `now_utc_iso()` (243) | the single producer of a provenance timestamp. **Second** resolution deliberately: "sub-second precision says nothing true about when a *source* published anything — it is the latency of our own HTTP call". The comment names the drift it ended: `sources.csv` wrote `2026-08-03T02:03:23Z` and `literature.csv` wrote `2026-08-01T20:55:37.406184+00:00` |
| `normalize_utc_timestamp(raw)` (258) | bound `mode="before"` on every `fetched_at`/`checked_at`. Offsets convert to UTC, a naive value is *read* as UTC, sub-second is dropped, and an unreadable value **raises** rather than passing through |

### `reference.py` — the generated authoring description

`authoring_reference()` (`reference.py:281`) returns a JSON-serializable dict with keys:
`schema_version`, `genome_build_default`, `models`, `vocabularies` (closed), `open_recommended`
(open), `vocabulary_notes`, `required_any_of`, `reserved_names`, `registry_stamped_keys`,
`recommended_palette`. Every vocabulary block is **generated from the fields' own markers**, and the
comment records the two drifts that forced it: the hand-kept list "never learned about
`recommendation_strength` or `phenotype_category` when 0.5 added them, and it filed `actionability`
under `open_recommended` although `VariantRow` rejects a non-member — a drift in *closedness*".

`json_schemas()` (`reference.py:329`) returns `model_json_schema()` per model.

The registry is six dicts merged into `_ALL_MODELS` (`reference.py:176`): `_MODULE_MODELS` (7),
`_VARIANT_MODELS` (2), `_BINNING_MODELS` (5), `_PGX_MODELS` (4), `_PGS_MODELS` (1), `_FACT_MODELS`
(12), `_OVERLAY_MODELS` (1) — 32 total, measured.

### `aggregate.py` — cross-version union

`aggregate_logs(manifests)` (`aggregate.py:15`) — dedup key `(name, sha256)`, first occurrence wins,
result **sorted** by that key.
`aggregate_provenance(manifests)` (`aggregate.py:29`) — dedup key is the provenance document hash;
a summary with no hash is keyed by a monotonic counter "so distinct-but-unhashed summaries are not
silently merged". Result is in **first-occurrence order**, and the comment records the bug: keying on
`id()` "is non-reproducible across processes, so sorting by it gave a run-dependent order".

### `binning.py` — the tiling algebra and the table-level checks

* `VALID_MEASURE_TILINGS = {quantised, continuous}`; `DEFAULT_MEASURE_TILING` (`binning.py:197`) is
  **derived** from `_DENSE_KINDS`/`_CONTINUOUS_GAP_KINDS`/`_INTEGER_KINDS`, giving
  `activity_score → None`, `allele_fraction → continuous`, `copy_number → quantised`,
  `prs_percentile → continuous`, `repeat_count → quantised`.
* `TilingResolution` (`binning.py:812`) is a `NamedTuple` of `(value, declared, default, fractional,
  disagreement)` with `inferred` and `contradicted` properties.
* `resolve_tiling(grp)` (`binning.py:840`) — declared, else inferred, else the kind's default.
  Three stated rules: **agreement is checked first** and *returned* rather than raised; the
  inference runs **one way only** (fractional ⇒ continuous; integer-ness implies nothing); and it
  fires **only against a `quantised` default**, "because that is the only reading a fractional value
  contradicts". The last is argued from a real case —
  `reference_examples/cyp2d6_structural` states bins at 0.25/0.5/1.25/2.25, and reading a fractional
  activity score as continuous would produce three false coverage-gap warnings.
* `_fractional_values(row)` (`binning.py:781`) — reads **bounds only**.
* `validate_bins(rows)` (`binning.py:1007`) — groups by `_KEY_FIELDS` + `trait_efo_id`. Overlap
  **raises**; overlap across different `trait_efo_id` is allowed (pleiotropy). Under `continuous`
  the error is `lo < prev_hi` and a shared endpoint belongs to the **higher** bin; under `quantised`
  it is `lo <= prev_hi` and only a hole wider than one step is a hole; under `None` a shared endpoint
  is an overlap and interior holes are not reported at all. **Two bins sharing a lower bound refuse
  in every case.** Returns warnings; a `measure_tiling` disagreement within one group raises.
* `measurement_shape_warnings(rows)` (`binning.py:897`) — RM55/RM56, stated **against the kind, once
  per table**. Two pinned phrases: `FRACTIONAL_MEASURE_PHRASE = "is not a whole number in VCF 4.4"`
  and `SPANNING_MEASUREMENT_PHRASE = "one measurement can span several bins"` (`binning.py:234-235`).
  The comment beside them is explicit that these "are the only surviving record of these findings for
  a consumer reading a published `manifest.json`". **Test-pinned**: `test_measure_tiling.py` imports
  `FRACTIONAL_MEASURE_PHRASE` (`:16`) and asserts on it at `:391`, `:392`, `:405`, `:423` and `:433`
  (the last is `== 1`, pinning that the finding fires once per table, not per row).
  `SPANNING_MEASUREMENT_PHRASE` is **not** referenced by any test by name; the nearest assertion is
  `test_vcf_measure_shape.py:199`, `assert "withholds" in spanning[0]`.
* `deprecation_warnings(rows)` (`binning.py:981`) with ``DEPRECATED_MODIFIER_PHRASE = "`modifier_cn`
  is deprecated"`` (`binning.py:978`), imported and asserted by `test_measure_tiling.py:15` / `:566`
  (`assert DEPRECATED_MODIFIER_PHRASE in warnings[0]`).
* `format_group_key(group_key)` (`binning.py:758`) — rendered once per group so "an integral
  effective modifier dosage must not start printing as `2.0` on a module nobody edited".

### `spec.py` — citation parsing

* `PMID_PATTERN = \b(\d{1,8})\b`; `PMCID_PATTERN = PMC(?:ID)?\s*[:\-]?\s*(\d{1,9})` (IGNORECASE);
  `DOI_PATTERN = 10\.\d{4,9}/\S+` (`spec.py:78`, `86`, `91`).
* `extract_pmcids` / `extract_pmids` (`spec.py:94`, `109`) — **a digit run whose immediate context
  spells `PMC` is skipped**. The comment carries the incident (RM50): `PMC3110566` never parsed as a
  PMID (no word boundary between `C` and a digit) "but **`PMC 3110566` did** — and 3110566 is a real
  PMID for an unrelated article, because PMIDs are densely allocated. So the outcome turned on a
  space and the accepted spelling silently cited the wrong paper."
* `validate_pmid_cell(value, field, *, required)` (`spec.py:131`) — the single grammar all three
  citation pointers route through (`StudyRow.pmid` required, `MeasureBinRow.pmid` and
  `PharmVariantRow.pmid` optional). **It never repairs**: converting a PMC id to a PMID needs the
  registry. Two verbatim messages — the PMCID branch quotes
  `f"{field} names PubMed Central id(s) {pmcids} and no PubMed ID…"` and the fallback is
  `f"{field} must contain at least one PubMed ID (bare digits, or a bracketed/prefixed form like '[PMID: 9545397]'), got: {value!r}"`.

### `derive.py` — the legacy→0.3 derivations

The one module neither the compiler nor the enricher imports directly; `spec` reaches it for
`VariantRow.effective_*`.

* `direction_from_state(state, weight=None)` (`derive.py:63`) — `_STATE_TO_DIRECTION` lookup, except
  that `significant` is **refined from the weight sign** first: positive → `protective`, negative →
  `risk`, and a zero or absent weight falls back to `unknown`. "Significance is not a direction."
* `stat_significance_from_state(state)` (`derive.py:77`) — only `significant` is informative.
* `trimmed_state(direction)` (`derive.py:82`) — `_DIRECTION_TO_STATE.get(direction, "neutral")`, a
  **lookup with a default**, which the surrounding comment (`derive.py:40-51`) names as the hazard:
  "a direction missing from this map does not fail, it silently projects to `neutral`. Measured
  before `contested` was added: `trimmed_state("contested")` already returned `"neutral"`, and so does
  `trimmed_state("total nonsense")`." The guard it therefore demands is "a **registry-iterating
  equality** over the walked set (`set(_DIRECTION_TO_STATE) == VALID_DIRECTIONS`) and not a spot
  check". I ran that equality in §9 and it **holds**, in both directions, as do the two `_STATE_TO_*`
  maps against `VALID_STATES` and their value sets against `VALID_DIRECTIONS`/`VALID_SIGNIFICANCE`.
* `clin_sig_from_booleans` / `pathogenic_from_clin_sig` / `benign_from_clin_sig` (`derive.py:92`,
  `107`, `115`) — see §5. `clin_sig_from_booleans` is "lossy by construction — legacy cannot recover
  `likely_pathogenic`/`likely_benign`"; the asymmetry with `_DIRECTION_TO_STATE` (which has no
  `contested` source) is argued at `derive.py:16`: "no legacy `state` value means *the sources
  disagree about the sign*, so there is nothing to map FROM".

### `findings.py` — coded warnings

`CodedWarning(str)` with `__slots__ = ("code",)` (`findings.py:27`). It is a `str` subclass so
"every `.extend`, every `if w not in all_warnings` de-duplication, every `"; ".join` and every
consumer already grepping a phrase keeps working untouched". `__getnewargs__` (`findings.py:57`) is
overridden so the code survives `copy`/`pickle` — the docstring records that without it
`copy.deepcopy` raised `TypeError`. `restate(finding, message)` (`findings.py:79`) **refuses** a
plain `str` rather than inventing a code. `classify` is covered in §5.

The stated trap: "**Pydantic strips the subclass at a model boundary**, which is a feature for
serialization … and a trap for anything that reads warnings back off a result model and keeps
building. So the rule is: classify *before* constructing the model."

### `signing.py`

`generate_private_key_pem()` (44) → PEM bytes; `public_key_b64_from_pem` (39);
`sign_digest(digest, private_key_pem, *, signed_at=None)` (54) → `Signature`. `_ALGORITHM =
"ed25519"` (24). `cryptography` is imported here and in `integrity.verify_signature`, and nowhere
else — which is what keeps the package's second dependency to one purpose.

### Tests present in `schema/tests/`

44 modules. Beyond the ones cited above, the set names its own concerns:
`test_contig_geometry`, `test_coordinate_convention`, `test_direction_contested`,
`test_dsl_regression`, `test_fact_model_guards`, `test_first_seen`, `test_genotype_gt_indices`,
`test_heteroplasmy_variant_key`, `test_logs`, `test_measure_tiling`, `test_pgx_callability`,
`test_pmid`, `test_polyploid_genotype`, `test_printed_contract`, `test_split_genotype`,
`test_strand_flip`, `test_unobservable_allele`, `test_v04`, `test_vcf_measure_shape`,
`test_vocab_separator`, `test_workspace_versions`.

### Who consumes these models (the one cross-tier question)

Import grep over `compiler/src` and `enricher/src` only (`grep -rho 'from just_dna_format\.[a-z_]*'`):

* **compiler** imports **29** of the 31 submodules — all but `aggregate` and `derive`.
* **enricher** imports **25** — all but `aggregate`, `derive`, `integrity`, `reference`,
  `release_records` and `signing`.
* `aggregate` and `derive` are imported by **neither** tier. `derive` is still reached indirectly
  (`spec` imports it for `VariantRow.effective_*`); `aggregate` has no in-workspace caller at all,
  and its docstring names the marketplace's module-detail view as the intended consumer.
* No module of `just_dna_format` imports anything from `just_dna_compiler` or `just_dna_enricher` —
  measured, zero hits.

---

## 11. Defect candidates

Each item says what was measured, and separates *the code contradicts itself* from *this is
documented and I am only flagging it as surprising*.

### D1 — `merge_key` on `MeasureBinRow` returns `()` instead of raising, so every bin row is one row

`base.merge_key` (`base.py:124`) documents the failure mode it is designed to avoid:

> Raises `AttributeError` for a model declaring no key, which is the honest failure: a caller
> reaching here for an unkeyed kind has a bug, and a silent `()` would merge every row into one.

But `MeasureBinRow` declares `_KEY_FIELDS: ClassVar[tuple[str, ...]] = ()` — an *empty* tuple, not an
absence — so the guard never fires. Measured:

```
merge_key(MeasureBinRow(measure_kind='copy_number', conclusion='x', measure_min=0, measure_max=1)) == ()
merge_key(MeasureBinRow(measure_kind='repeat_count', conclusion='y', measure_min=5, measure_max=9)) == ()
equal: True
```

Two rows of different kinds share a key. `MeasureBinRow` is instantiable (all four subclasses'
extra columns are what it lacks, and none is required of the base), it is a member of
`reference._BINNING_MODELS` and therefore of `_ALL_MODELS`, and `merge_key` is public API.
No test in `schema/tests/` walks `merge_key` over the registry, so nothing catches it. Severity is
low today because no enricher pass merges a binning table — but the function's own docstring says
that is exactly the reasoning that must not be relied on.

**The fix the code implies**: make the declaration an absence (`MeasureBinRow` does not declare
`_KEY_FIELDS` and the four subclasses do), or have `merge_key` refuse an empty primary the way it
refuses a missing one.

### D2 — allele case is accepted, stored unnormalized, and is therefore part of content identity

`ALLELE_PATTERN` is `re.compile(r"^[ACGT]+$", re.IGNORECASE)` (`vocab.py:71`) and
`vocab.validate_allele` returns `value` **unchanged**. Measured:

```
validate_allele("acgt")                          -> 'acgt'
HaplotypeRow(..., allele='acgt').allele          -> 'acgt'
VariantRow(..., effect_allele='g').effect_allele -> 'g'
content_signature({'variants.csv': [effect_allele='A']})
  != content_signature({'variants.csv': [effect_allele='a']})
```

Two spellings of one allele are two content identities. That contradicts the rule the package states
everywhere else about spelling versus stored value:

* `vocab.match_vocab` (`vocab.py:1191`): "Returns the canonical member (so the stored cell is always
  the declared spelling)";
* `spec.VariantRow._validate_chrom` (`spec.py:968`): "what is stored is always the declared member,
  never the author's spelling, so nothing downstream ever sees two spellings of one contig";
* `schema/tests/test_alleles.py:70`, named `test_case_and_whitespace_do_not_decide_anything` — the
  *algebra* upper-cases (`parsimony_reduce`, `non_nucleotide_reason`, `is_substitution`,
  `reverse_complement`, `derive_vrs_allele_id` all `.upper()`), so the identity minted from a
  lowercase cell is the same, while the signature computed over it is not.

A second, sharper consequence: the unphased-genotype sort rule is ASCII, so case changes **legality**.
Measured against `VariantRow`:

```
'A/G' ACCEPTED     'a/g' ACCEPTED
'A/g' ACCEPTED     'a/G' REFUSED ("unphased genotype alleles must be alphabetically sorted")
'g/a' REFUSED
```

`'A/g'` and `'a/G'` name the same unordered pair and only one of them loads. Nothing in the source
argues for this; the genotype docstrings discuss order and phase at length and never mention case.

**The counter-argument, and why it does not close this.** A reviewer will reach for
`SymbolicAllele`'s docstring (`alleles.py:107`) — "Case is preserved as written and normalized only
here … while `text` keeps the author's spelling so no cell is silently rewritten" — and for
`test_symbolic_alleles.py:65`, `test_case_is_normalized_on_the_parse_and_preserved_on_the_cell`.
That is a real rule, and it applies to *symbolic* tokens. The point is that the package states **two
opposite rules** — preserve-the-cell (symbolic `text`) and store-the-canonical (`check_vocab`,
`_validate_chrom`) — and the nucleotide allele columns inherit **neither explicitly**: no validator
upper-cases them and no comment says they are preserved on purpose. Meanwhile the algebra one module
over declares the opposite in a test *name*: `test_case_and_whitespace_do_not_decide_anything`
(`test_alleles.py:70`). So the same package holds that `a` and `A` are one allele for reduction,
comparison, complementing and VRS minting, and two content identities for dedup.

**What I could not settle from code**: whether the compiler normalizes case at load. That is outside
the tier I read, and it would not fix `content_signature`, which is computed over the parsed rows.

### D3 — `ACTIONABILITY_SEED`'s own comment says it is not enforced; it is

`vocab.py:965`, immediately above the constant:

> The reserved `actionability` axis's recommended seed vocabulary (documentation — the field is not
> built yet, so this is not enforced).

The field *is* built: `VariantRow.actionability` (`spec.py:0.4.0`) exists, and
`VariantRow._validate_actionability` (`spec.py:1008`) is
`return check_vocab(v, ACTIONABILITY_SEED, "actionability")` — a closed-vocabulary rejection.
Measured: the field's `vocabulary` marker reports `closed=True` with exactly the seven members.

`reference.py:290` already records this as a past incident — the hand-kept reference "filed
`actionability` under `open_recommended` although `VariantRow` rejects a non-member — a drift in
*closedness*". The marker was fixed; the comment beside the constant, and the `_SEED` name, were not.
Both now read as an invitation to treat the set as open.

### D4 — `CANONICAL_MT_REFERENCE_SEQUENCES` is dead, and sits beside an enforced deny-list

`binning.py:609` defines `CANONICAL_MT_REFERENCE_SEQUENCES = frozenset({"NC_012920.1"})`. Measured:
it is referenced **nowhere else** — not in `schema/src`, not in `schema/tests`, not in
`compiler/src`, not in `enricher/src`. Its neighbour `LEGACY_MT_REFERENCE_BASES` (608) *is* enforced,
by `HeteroplasmyRow._reject_legacy_reference`, and the comment between them
(`binning.py:607`) says "Not a closed allow-list (future refs exist) — the validator rejects only
this enumerated landmine." So a reader meeting the pair naturally reads the allow-list as the
positive rule, and nothing enforces or tests it.

### D5 — `STAR_ALLELE_PATTERN` is defined in this tier and enforced by nothing in it

`pgx.py:40` defines it; the only other occurrence in `schema/src` is the comment at `pgx.py:43`
explaining that it "stays available for providers that genuinely draft star alleles (`pgx_draft`
checks it at four sites)". Measured: zero validators in `schema/src` use it, and its only
cross-tier reference is `enricher/src/just_dna_enricher/pgx_draft.py`. So it is a *pattern the format
publishes and does not apply* — legal,
and stated, but it is the shape that produced the APOE bug the surrounding comment documents (it
was enforced on one of the three PGx allele columns and not the other two).

### D6 — the grandfathered `content_signature` asymmetry (self-declared)

`base.stamped_identity_field` (`base.py:395`) states it outright:

> `VariantRow.variant_key`/`authored_ident` are **not** excluded and are inside `content_signature`
> today; that is a grandfathered inconsistency, not a precedent — un-excluding them here, or
> excluding them there, moves published signatures either way, so the asymmetry is carried until a
> major.

Measured and confirmed: on `VariantRow`, `variant_key` and `authored_ident` carry
`compiler_managed` with `exclude` unset, while `locus_index`/`locus_count` and every stamped column
on `HeteroplasmyRow`/`HaplotypeRow`/`PharmVariantRow` carry `exclude=True`. Flagged not as an
oversight but because it is the one place where "a compiler-stamped column is outside content
identity" is false, and a peer document that states the rule without the exception would be wrong.

### D7 — `VariantRow._freeze_identity` derives its key with no build (self-declared)

`spec.py:868` calls `derive_variant_key(self.rsid, self.chrom, self.start, self.ref, self.alts)`
with no `build=`, so it takes `derive_variant_key`'s `"GRCh38"` default regardless of the module's
declared assembly. `base.py:683` says this is deliberate — `VariantRow` "leaves `_KEY_INCLUDES_ALTS`
unset and keeps its existing restamp, which also emits the 'keyed by coordinate instead' warning a
GRCh37 module must hear" — so the correction lives one tier up. It is listed here because the same
shape *was* a real bug four times (`spec.py:876`–`880` record the removed `authored_key`, "build-blind …
the exact identity falsification the 2026-08-06 sweep found in four other places"), and because a
`VariantRow` used outside the compiler silently gets a GRCh38 key.

### D8 — `chrom` is validated on exactly one of the five models that declare it

`VariantRow._validate_chrom` normalizes and gates. `StudyRow`, `HeteroplasmyRow`, `HaplotypeRow` and
`PharmVariantRow` all declare `chrom` and run **no** validator, so `chr7`, `CHR7` and an arbitrary
string are accepted and stored verbatim. The code states this is deliberate in two places —
`binning.py:649` ("No `chromosome` vocabulary marker, matching the other tables that run no chrom
validator") and `pgx.py:102` and `pgx.py:457` ("attaching one where nothing rejects would be the" drift the marker
exists to prevent) — and the *marker* is correctly withheld, which is the part that matters for a
tool. It is still an asymmetry a reader will meet: one artifact can carry `7` in `variants.csv` and
`chr7` in `pharm_variants.csv`, and both stamp identities through `normalize_chrom`, so the keys
agree while the stored cells do not.

### D9 (soft) — `is_multi_valued_number` collapses unknown into `False`

`vocab.is_multi_valued_number(number)` (`vocab.py:1130`) returns a bare `bool`, and its own docstring
closes with: "`None` (unknown) is **not** multi-valued: withhold, never negate, and never accuse."
The implementation is `return number is not None and number not in {"0", "1"}` — so an unknown
cardinality and a known-scalar one give the same answer, from a total function, on a question the
package elsewhere insists has three outcomes.

Flagged **soft**, with the argument for the current shape stated: the function's only input is
`vcf_field_number`'s output, which is *already* three-valued and already returns `None` for unknown,
and the caller's action on "unknown" and on "scalar" is plausibly the same (do not warn about an
unselected element). So this may be a deliberate narrowing at the right place rather than a lost
third state. What makes it worth flagging anyway is that the docstring **claims the tri-state**
("withhold, never negate") for a signature that cannot express it — the mismatch is between the
sentence and the return type, and a reader taking the sentence at face value will assume a `None`
return exists.

### Non-defects I checked and cleared

Four paired lists are unequal and all four are documented subsets, not drift — see §9's table
(`ORDERED_GENE_VALIDITY`, `VCF_NUMBER_MEANINGS`, `_VCF_MEASURE_FIELDS`, `SHARED_VOCABULARY_NOTES`).
`RECOMMENDED_COLORS` and `RECOMMENDED_ICONS` have different key sets, which is fine: they are two
independent semantic-use palettes, neither enforced.
`VerificationRecord` has no `_KEY_FIELDS`, so `merge_key` raises `AttributeError` on it — the
documented honest failure; uniqueness there is enforced by `VerificationDoc._check_unique` instead.

---

## 12. Undetermined from code

Things a reader of this reference will want and that `schema/src` + `schema/tests` do not answer.
Nothing below is a guess.

**Release history and the meaning of `first_seen`.** Every authored field carries a `first_seen`
string, and the values range over `0.2.0` … `0.7.0`. The code never says what those releases
*were* — no changelog, no mapping from a release to a date, no statement of which of them was the
first public one. `since()`'s docstring (`base.py:255`) explains the mechanism and gives one worked
example (`StudyRow.curator`, 0.6.5) and nothing more.

**The `RMn` / `Sn` / `R2-n` identifiers.** The source cites dozens (`RM5`, `RM15`, `RM43`, `RM47`,
`RM55`, `RM59`, `RM63`, `RM67`, `RM78`, `RM82`, `RM87`, `RM90`, `RM95`, `RM110`, `RM115`, `RM124`,
`RM130`, `RM131`, `RM134`, `RM146`, `RM150`, `S7`, `S17`, `S25`, `S30`, `S45`, `S51`, `S87`, `S88`,
`S90`, `R2-9`, `R2-10`, `R2-12`, `R2-14`, `D1-4`, `C1`, `Q9`, …). What each one *is* lives outside
this tier. I have quoted them only where the surrounding sentence carries the substance.

**The validation ceiling.** Several docstrings say a rule belongs to "the compiler" rather than the
schema (a lengthless symbolic allele, the `hosting_verdict`, the resolution fill, the near-miss
table-name guard, the `_restamp_for_build` pass). Where the boundary is drawn *in general* is not
stated in this package.

**Whether the compiler normalizes allele case at load.** Bears directly on D2; not answerable from
`schema/`.

**`MISSING_ALLELE` in `alts`.** `non_nucleotide_reason` classifies `.` and names the identity
collision it causes, but nothing in this tier *refuses* it. Which layer refuses it — and whether the
`missing_allele_marker_in_alts` warning code is a warning or a gate — is not stated here.

**`ProvenanceItem.outranks` — mostly determined, on a second read** (`manifest.py:1080-1112`). The
contract *is* stated: `{column: why}`, a per-column justification for a row deliberately disagreeing
with a source, and "**A key's presence is what a tool may read; the prose is for a human**" — never a
parse of the text, "whose whole justification is that the judgement is not formalizable". The
docstring adds that nothing in this format reads it today, and that an item stays per-*variant*
because `Provenance.item_count` is a published number meaning *variants with a record*. What remains
undetermined is only the **key vocabulary**: any column name is accepted, unvalidated.

**`Compilation.dropped_rows` / `resolution_mode` / `resolution_sources`.** Compiler-stamped
`dict[str, int]` / free-form strings with no vocabulary binding. The legal values are the compiler's,
not this tier's.

**`SourceRow.draft_digest`.** Present since 0.6.0 and outside `SOURCE_FACT_FIELDS`. What it digests
is not derivable from this package.

**The `authority` vocabulary.** `ClinSigAuthorityCallRow.authority` is documented as
"clinvar|pubmind|manual (open)" in a field description, but there is no constant, no validator and
no marker — so the set is prose only, and I cannot state it as a vocabulary.

**Parquet.** Several docstrings refer to `weights.parquet`, `studies.parquet`, `sources.parquet`,
`annotations.parquet` and to what `artifact.digest` covers. This package writes no parquet and
declares no parquet schema; the column lists are the compiler's.

**`reference_examples/`.** Cited in several docstrings as evidence (the SHOX case, `cyp2d6_structural`
at 0.25/0.5/1.25/2.25, "all sixteen reference examples", "844 ids"). The directory was removed from
this worktree, so I could not verify any of those figures and have quoted them as the code's claims.

**Whether `MeasureBinRow` is ever instantiated directly in practice.** It is instantiable and
registered, which is what D1 turns on, but no caller in this package constructs one.

**Which `VALID_WARNING_CODES` members the compiler actually emits, and where.** The vocabulary is
owned here (73 members, 11 carried) and every emission site is elsewhere. A test in this tier cannot
tell whether a member is dead.

**Which quoted strings are actually test-pinned.** The task's rule is to quote a test's exact string
where one exists. Measured by grepping `schema/tests/` for each phrase constant and each distinctive
message fragment:

| Constant / message | Pinned by |
| --- | --- |
| `FRACTIONAL_MEASURE_PHRASE` | imported and asserted, `test_measure_tiling.py:16,391,392,405,423,433` |
| `DEPRECATED_MODIFIER_PHRASE` | imported and asserted, `test_measure_tiling.py:15,566` |
| `RESERVED_NAME_REASONS` | `test_v04.py` |
| `MISPLACED_COLUMN_REASONS` | `test_reference.py`, `test_v04.py` |
| `ELEMENT_RULE_MEANINGS` | `test_reference.py` |
| `IDENTITY_AUTHORITY_REASONS` | `test_normalize.py` |
| `_GT_INDEX_DIAGNOSIS` | **fragments only** — `"VCF GT"`, `"indices"`, `"REF"`, `"ALT"` (`test_genotype_gt_indices.py:56-60`) |
| `_PLOIDY_DIVERGENCE` | **fragments only** — `"RM67"`, `"7.2"`, the cell itself (`test_polyploid_genotype.py:65-67`), and `"ceiling"` as a branch marker (`test_genotype_gt_indices.py:71-79`) |
| the unphased-sort message | fragment `"alphabetically sorted"` — `test_genotype_gt_indices.py:123`, `test_symbolic_alleles.py:164`, `test_unobservable_allele.py:105`, `test_dsl_regression.py:103` |
| `_validate_chrom`'s message | fragment `"chrom must be one of"` — `test_contig_geometry.py:179,184` |
| `StudyRow`'s half-coordinate refusal | fragment `"half-written coordinate"` — `test_citation_identifiers.py:153` |
| `check_vocab`'s `"must be one of"` | fragment — `test_release_records.py:248,250` and others |
| `SPANNING_MEASUREMENT_PHRASE` | **not referenced by any test by name**; nearest is `assert "withholds" in spanning[0]` (`test_vcf_measure_shape.py:199`) |
| `UNTRUSTED_NOTE`, `TEMPLATE_PLACEHOLDER`, `_OPERATION_MEANINGS`, `VCF_COLLISION_REASONS`, `VCF_NUMBER_MEANINGS` | **stated in code, not test-pinned** |

So: several messages this document quotes are quoted from **source**, because no test pins them.
Where that is so I have said which fragment the suite does pin, and a rewording that preserved the
fragment would pass.

**Deprecation timelines.** `DEPRECATED_SPELLINGS` and `modifier_cn` are both said to be removed "at
1.0"; `panel_block_deprecated` is a warning code. Nothing in this package states a release date or
what else is queued for that major.

---

## 13. Contamination statement

The harness injected a `CLAUDE.md` (project instructions), a global user `CLAUDE.md`, and a
`MEMORY.md` into my context before I could act. All three make specific claims about this exact
tier — the hash roster's shape, `variant_key` precedence, VRS ids per ALT, a `ge=0` bound on `start`,
the tri-state algebra, `VALID_RSID_STATUS`'s member count, the `@` gotcha tags, and more.

**No claim in this document is sourced from any of them.** The working rule I applied: a sentence
lands only with a `file:line` I had on screen from `schema/src/**` or `schema/tests/**` in this
worktree, a measured result from a script I ran against the installed package, or a verbatim quote
from source I had just read. Before finalizing I grepped this document for the injected phrasings
(`rsid → VA`, `four members`, `one id per ALT`, `ge=0`, `two identity halves`, `@`-tags) and confirmed
each surviving statement has its own citation beside it, independently derived:

* the `derive_variant_key` order is stated from `base.py:320`'s body and pinned by
  `test_variant_key_freeze.py:15-18`, which I read and quoted;
* "one id per ALT" is stated from `vrs.split_vrs_ids`/`join_vrs_ids` (`vrs.py:714`, `737`) and
  `ResolutionRow._vrs_ids_align_with_alts` (`resolution.py:237`);
* `start`'s `ge=0` is reported from the measured pydantic field metadata (`constraints=Ge(ge=0)`),
  not from memory;
* `VALID_RSID_STATUS`'s four members are printed from the live constant;
* the hash roster is counted from a grep I ran and reported with its counting rule, and it
  deliberately gives **two** numbers because the count depends on the rule.

I followed **no** `docs/…` pointer from the injected file, read nothing under
`/data/sources/just-dna-format`, and read no deleted file out of git history. I also did not read
`schema/README.md`, which survived the deletion but is outside the permitted read list.

Two indirect effects I cannot fully rule out and should name rather than deny:

1. **Prioritization.** Knowing in advance that this repo cares about tri-state logic, registry
   completeness and paired-list drift shaped *where I looked* — §5, §9's paired-list audit and
   several of §11's probes were aimed by that prior. The findings themselves are measured, but a
   truly blind reader might have looked elsewhere first.
2. **Vocabulary.** Phrases like "withhold rather than negate", "the house algebra" and "registry, not
   a list" also appear in the source's own docstrings, so I cannot separate which reading taught me
   the idiom. Every use of them in this document is beside a source quote that uses it too.
