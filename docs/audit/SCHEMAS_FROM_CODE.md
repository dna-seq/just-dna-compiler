# Schema tier, read out of the code — 2026-08-18 audit snapshot

*A dated snapshot, never updated. It was written from the source alone, with the shipped
reference deliberately unread, so that the two could be read against each other — see
[README.md](README.md) for the method and what it is not. **The maintained reference for this tier
lives in `docs/`; this file is evidence, not contract.** Where the two disagreed, eight of the
disagreements turned out to be code defects and are filed as RM93–RM100.*


Derived only from `schema/src/just_dna_format/**`, `schema/tests/**` and `schema/pyproject.toml` at
version 0.6.0. Nothing in it was read out of the repository's prose documentation. Where a field's
own `description=` string is the authoritative statement of a rule, that string is quoted rather than
paraphrased, because three surfaces (`describe`, `requirements`, `reference`) print those strings
verbatim and tests pin phrases inside them.

---

## 1. Package, dependencies, entry points

| | |
| --- | --- |
| Distribution | `just-dna-format` 0.6.0 |
| Import package | `just_dna_format` |
| Python | `>=3.13` |
| Runtime deps | `pydantic>=2.12.5`, `cryptography>=44.0.0` |
| Dev deps | `pytest>=9.0.3` |
| Build backend | `uv_build` (`requires = ["uv-build"]`) |
| Console scripts / entry points | **none** — `pyproject.toml` declares no `[project.scripts]` and no plugin entry points. This tier is a library only. |

`cryptography` is used in exactly two modules (`signing`, and `integrity.verify_signature`) and only
for Ed25519. Everything else is pydantic plus the standard library. `just_dna_format/__init__.py`
contains a docstring and nothing else — there are no re-exports, so every symbol must be imported
from its own submodule.

### Module map

| Module | Role |
| --- | --- |
| `base` | `AuthoredModel`, the field markers (`COMPILER_MANAGED`, `vocabulary`), `derive_variant_key`, the genotype grammar, identity stamping |
| `vocab` | stdlib-only leaf: every shared vocabulary, identifier pattern, and reusable validator helper |
| `alleles` | stdlib-only leaf: nucleotide/symbolic/unobservable allele predicates, genotype splitting, reference-free indel comparison |
| `vrs` | GA4GH VRS allele ids, refget accessions, contig geometry, PAR tables |
| `spec` | the authored DSL: `ModuleSpecConfig` / `ModuleInfo` / `Defaults`, `VariantRow`, `StudyRow`, PMID/DOI grammar |
| `binning` | `MeasureBinRow` and its four subclasses; bin coherence checking and tiling resolution |
| `pgx` | `HaplotypeRow`, `AlleleFunctionRow`, `DiplotypeRow`, `PharmVariantRow` |
| `pgs` | `PgsRow` |
| `resolution`, `frequency`, `gene_metrics`, `gene_validity`, `assertions`, `gwas`, `literature`, `sources` | the derived-fact sidecar row models and their fact-field tuples |
| `manifest` | `ModuleManifest` and every nested block; also `Signature`, `Closure`, `VerificationRecord`, `VerificationDoc` |
| `integrity` | hashing, artifact digest, content signature, fact signature, `verify_manifest` |
| `signing` | Ed25519 private-key side |
| `verification` | attestation binding, proof-of-work, record merge |
| `identity` | module name/namespace/version grammar |
| `normalize` | authority-key stripping, version coercion, p-value parsing, UTC timestamp canonicalization |
| `derive` | legacy `state` → 0.3 axis derivations |
| `aggregate` | cross-version log/provenance union |
| `layout` | where machine-written sidecars live and what they may be called |
| `reference` | `authoring_reference()` / `json_schemas()` — a generated description of the authored surface |

---

## 2. `AuthoredModel` and the base machinery

`just_dna_format.base.AuthoredModel` is the base for every **authored** row model. The derived-fact
sidecar rows deliberately do *not* inherit it (see §7).

```python
class AuthoredModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

### 2.1 The raw-input guard chain

`_guard_raw_input` is a `mode="before"` model validator. It runs on the **raw dict**, before field
coercion, so each check produces its own diagnosis rather than pydantic's type error. Order is fixed
and each step raises:

1. `vocab.reject_template_placeholders(data, what=f"{cls.__name__} row")` — refuses any cell whose
   stripped value is exactly `TEMPLATE_PLACEHOLDER` (`"<<REPLACE>>"`). The scan
   (`vocab._placeholder_paths`) recurses into nested dicts and lists and reports dotted paths.
2. `vocab.reject_misplaced(data, cls.model_fields, ...)` — a column that is real *somewhere* in the
   DSL but not on this model. Driven by `MISPLACED_COLUMN_REASONS`, which today has exactly one
   entry, `source`. Keyed on the model's own fields, so `FrequencyRow.source` is untouched.
3. `base.reject_compiler_filled(data, cls.model_fields, ...)` — refuses an **identity** column
   (`IDENTITY_FIELDS = ("rsid", "chrom", "start", "ref", "alts")`) that this model marks
   `COMPILER_MANAGED`. Today that is `alts` on `HaplotypeRow` and `PharmVariantRow`. Deliberately
   scoped to `IDENTITY_FIELDS`, which is why an authored `variant_key`/`authored_ident` is
   *accepted and silently overwritten* instead.
4. `vocab.reject_reserved(data)` — refuses a name in `RESERVED_NAMES_0_4` with a message quoting
   `RESERVED_NAME_REASONS`.

Anything not caught by these four falls through to `extra="forbid"`'s generic
`Extra inputs are not permitted`. `test_v04.py` asserts the split over all eight authored models:
a reserved name gets `"reserved column name"`, `source` gets `"not authored on a …"`, and
`xyzzy_random` / `directon` / `caller` / `caller_version` get the generic message.

### 2.2 Shared field validators

Declared with `check_fields=False`, so a subclass runs each only for the fields it actually declares.

| Validator | Fields | Rule |
| --- | --- | --- |
| `_validate_rsid` | `rsid` | `vocab.validate_rsid` — `^rs\d+$` |
| `_validate_trait_efo_id` | `trait_efo_id` | `vocab.validate_trait_ids` — each `[,;\|]`-separated token must match `^[A-Za-z][A-Za-z]*[:_]\w+$` |
| `_validate_shared_vocabulary` | `direction`, `clin_sig`, `stat_significance`, `evidence_level`, `source_element` | `check_vocab` against `SHARED_VOCABULARIES[field]` |
| `_validate_effect_size` | `effect_size` | `validate_finite` — rejects `NaN`/`inf` |
| `_validate_vcf_field_pointer` | `source_field`, `callable_from`, `quality_from` | `vocab.validate_field_token` — the VCF pointer grammar |
| `_validate_genotype` | `genotype` | the genotype grammar, §4.3 |

`SHARED_VOCABULARIES` is `{"direction": VALID_DIRECTIONS, "clin_sig": VALID_CLIN_SIG,
"stat_significance": VALID_SIGNIFICANCE, "evidence_level": VALID_EVIDENCE_LEVELS,
**dict.fromkeys(VCF_POINTER_COMPANIONS, VALID_ELEMENT_RULES)}` — i.e. the element-rule entry is
derived from the `VCF_POINTER_COMPANIONS` relation rather than listed.

Two `mode="after"` model validators are also shared:

* `_validate_pointer_companions` — for each `element_field → pointer_field` pair in
  `VCF_POINTER_COMPANIONS` (today `source_element → source_field`), an element rule set with an
  empty pointer raises. The converse (pointer without element rule) is legal.
* `_freeze_stamped_identity` — calls `stamp_identity` when the model sets `_KEY_INCLUDES_ALTS`.

### 2.3 Field markers

`COMPILER_MANAGED = {"compiler_managed": True}` is attached via `json_schema_extra`.
`authored_field_names(model)` returns `model_fields` minus anything carrying it. Every generator
over the authored surface reads through that function rather than a name list.

`stamped_identity_field(description, *, default=None)` builds a `Field(...)` that is
`COMPILER_MANAGED` **and** `exclude=True` (so it leaves `model_dump()` and therefore
`content_signature`) with a fresh `FieldInfo` per call.

`vocabulary(name, options, *, closed=True, notes=None)` builds
`{"vocabulary": {"name": …, "options": sorted(options), "closed": bool[, "notes": {...}]}}`.
`field_vocabularies(model)` reads both binding sites: a marker declared on the field, and a field
whose vocabulary is enforced by the shared validators (looked up in `SHARED_VOCABULARIES`, with
prose from `SHARED_VOCABULARY_NOTES`).

Two tests in `test_reference.py` pin the marker against actual behaviour, by probing
`model.model_validate({field: "zzz_not_a_vocabulary_member"})` and reading the error:
enforcement implies a marker, and a `closed` marker implies enforcement. Both iterate
`reference._ALL_MODELS`, so a model outside that registry is not covered.

### 2.4 Requiredness is three-valued

`field_category(model, name)` returns `"required"` / `"defaulted"` / `"optional"`:

* `required` — `field.is_required()`.
* `optional` — not required and the annotation admits `None`.
* `defaulted` — not required and the annotation does **not** admit `None`
  (`MeasureBinRow.measure_kind: str = "repeat_count"`, `unresolved: bool = False`,
  `ResolutionRow.genome_build: str = "GRCh38"`).

The middle category exists because a CSV loader turns an empty cell into `None` *and keeps the key*,
so a `defaulted` column left blank reaches the model as `None` and fails on type. A `defaulted` cell
must be written out with its value.

`REQUIRED_ANY_OF: ClassVar[tuple[frozenset[str], ...]]` declares alternative identity groups that no
field-level `required` can express. Declared on:

| Model | `REQUIRED_ANY_OF` |
| --- | --- |
| `VariantRow` | `({"rsid"}, {"chrom", "start"})` |
| `HaplotypeRow` | `({"rsid"}, {"chrom", "start"})` |
| `PharmVariantRow` | `({"rsid"}, {"chrom", "start"})` |
| `StudyRow` | `()` — empty since 0.6; a study row may name no variant at all |

`test_reference.test_required_any_of_agrees_with_each_models_own_validator` proves each declared
group against the real validator rather than trusting the declaration.

### 2.5 The genome build is a private attribute

`AuthoredModel._genome_build: str = PrivateAttr(default=DEFAULT_GENOME_BUILD)` where
`DEFAULT_GENOME_BUILD = "GRCh38"`. It is exposed read-only as `.genome_build` and set by
`with_genome_build(build)`, which returns `self` so a loader can map over rows.

Because it is private it is absent from `model_fields` and `model_dump()`, reaches no CSV and no
parquet, and `extra="forbid"` still rejects `genome_build` as an authored column on an authored row.
(The *fact* tables do carry a real `genome_build` column — see §7.)

`with_genome_build` re-derives `variant_key` for any model that sets `_KEY_INCLUDES_ALTS`.
`VariantRow` deliberately leaves `_KEY_INCLUDES_ALTS` unset and is **not** re-stamped here; its
restamp lives one tier up in the compiler.

### 2.6 `_KEY_INCLUDES_ALTS` — a tri-state class variable

| Value | Meaning | Models |
| --- | --- | --- |
| `None` (default) | this model stamps no positional identity | every model except the three below |
| `False` | stamps `variant_key`, key **omits** `alts` | `HaplotypeRow`, `PharmVariantRow` |
| `True` | stamps `variant_key`, key **includes** `alts` | `HeteroplasmyRow` |

`stamp_identity(row, keys_on_alts, freeze_authored)` derives the key from the *authored subset only*
(`authored_ident`), so a compile-time coordinate fill can never re-key the row. When the row names
neither `rsid` nor `start` in its authored subset, `variant_key` is set to `None`.

### 2.7 `ALLELE_COLUMNS`

`ClassVar[tuple[str, ...]]`, empty by default, naming the columns of the model that hold an **allele
sequence**:

| Model | `ALLELE_COLUMNS` |
| --- | --- |
| `VariantRow` | `("ref", "alts", "genotype", "effect_allele")` |
| `StudyRow` | `("effect_allele",)` — `ref` is deliberately excluded: it merely points at a variant |
| `HeteroplasmyRow` | `("ref", "alts")` |
| `HaplotypeRow` | `("ref", "allele")` — the compiler-filled `alts` is excluded |
| `PharmVariantRow` | `("ref", "genotype")` — the compiler-filled `alts` is excluded |

Nothing in this tier reads `ALLELE_COLUMNS`; it is declared here for the compiler's symbolic-allele
check.

---

## 3. Vocabularies

Every constrained vocabulary is a `frozenset[str]` plus a validator — never `Enum` or `Literal`.

### 3.1 Closed and enforced

| Constant | Module | Members | Enforced on |
| --- | --- | --- | --- |
| `VALID_DIRECTIONS` | `vocab` | `protective`, `risk`, `neutral`, `unknown` | `VariantRow.direction`, `MeasureBinRow.direction`, `DiplotypeRow.direction` |
| `VALID_SIGNIFICANCE` | `vocab` | `significant`, `suggestive`, `not_significant`, `unknown` | `VariantRow.stat_significance`, `StudyRow.stat_significance` |
| `VALID_CLIN_SIG` | `vocab` | `pathogenic`, `likely_pathogenic`, `uncertain_significance`, `likely_benign`, `benign`, `drug_response`, `association`, `risk_factor`, `protective`, `affects`, `conflicting`, `not_provided`, `other` | `VariantRow.clin_sig`, `MeasureBinRow.clin_sig`, `DiplotypeRow.clin_sig`, `ClinicalAssertionRow.clin_sig` |
| `VALID_EVIDENCE_LEVELS` | `vocab` | `1A`, `1B`, `2A`, `2B`, `3`, `4` | `DiplotypeRow.evidence_level`, `PharmVariantRow.evidence_level` |
| `VALID_ELEMENT_RULES` | `vocab` | `largest`, `largest_alt`, `smallest`, `smallest_alt`, `sum`, `sum_alt`, `annotated_alt`, `reference` | `MeasureBinRow.source_element` |
| `VALID_RECOMMENDATION_STRENGTH` | `vocab` | `strong`, `moderate`, `optional`, `no_recommendation` | `DiplotypeRow.recommendation_strength` |
| `VALID_PHENOTYPE_CATEGORIES` | `vocab` | `efficacy`, `toxicity`, `dosage`, `metabolism_pk`, `pd`, `other` | `PharmVariantRow.phenotype_category` (multi-valued) |
| `VALID_DOSAGE_SENSITIVITY` | `vocab` | `no_evidence`, `little_evidence`, `some_evidence`, `sufficient_evidence`, `autosomal_recessive`, `dosage_sensitivity_unlikely` | `GeneMetricsRow.haploinsufficiency`, `.triplosensitivity` |
| `VALID_GENE_VALIDITY` | `vocab` | `definitive`, `strong`, `moderate`, `limited`, `supportive`, `disputed`, `refuted`, `no_known_disease_relationship`, `animal_model_only` | `GeneValidityRow.classification` |
| `VALID_INHERITANCE_MODE` | `vocab` | `autosomal_dominant`, `autosomal_recessive`, `x_linked`, `x_linked_dominant`, `x_linked_recessive`, `y_linked`, `mitochondrial`, `semidominant`, `undetermined` | `GeneValidityRow.moi` |
| `VALID_SOURCE_LAYERS` | `vocab` | `resolution`, `frequency`, `gene_metrics`, `literature`, `gene_validity`, `clinical_assertion`, `gwas_effect`, `annotation` | `SourceRow.layer` (required) |
| `VALID_DECLARED_USE` | `vocab` | `unstated`, `non_commercial`, `commercial` | `SourceRow.declared_use` |
| `VALID_EFFECT_DIRECTIONS` | `vocab` | `increase`, `decrease` | `GwasEffectRow.effect_direction` |
| `VALID_RESOLUTION_STATUS` | `vocab` | `resolved`, `not_found`, `ambiguous` | `ResolutionRow.status`, `LiteratureRow.status`, `GeneValidityRow.status`, `ClinicalAssertionRow.status`, `GwasEffectRow.status` — **not** `GeneMetricsRow.status` (§14) |
| `VALID_FREQUENCY_STATUS` | `vocab` | `resolved`, `not_found`, `not_covered` | `FrequencyRow.status` |
| `VALID_RSID_STATUS` | `vocab` | `live`, `merged`, `absent`, `withdrawn` | `ResolutionRow.rsid_status` |
| `VALID_QUOTE_SOURCE` | `vocab` | `fulltext`, `abstract` | `LiteratureRow.quote_source` |
| `VALID_AUTHOR_ROLES` | `vocab` | `created`, `edited`, `audited`, `reviewed` | `Contribution.role` (required) |
| `ACTIONABILITY_SEED` | `vocab` | `actionable`, `preventable`, `pharmacogenomic`, `incurable`, `reproductive`, `descriptive`, `modifiable` | `VariantRow.actionability` — **closed**, despite the constant's name (see note below) |
| `VALID_VERIFICATION_CHECKS` | `vocab` | 17 members, §12 | `VerificationRecord.check` (required) |
| `VALID_VERIFICATION_SKIPS` | `vocab` | `not_requested`, `offline`, `no_reference`, `unreachable`, `nothing_to_check`, `tautology`, `unsupported`, `not_permitted` | `VerificationRecord.skipped` |
| `VALID_STATES` | `spec` | `risk`, `protective`, `neutral`, `significant`, `alt`, `ref` | `VariantRow.state` (required) |
| `VALID_CHROMOSOMES` | `spec` | `1`…`22`, `X`, `Y`, `MT` | `VariantRow.chrom` only |
| `VALID_MEASURE_KINDS` | `binning` | `activity_score`, `copy_number`, `repeat_count`, `allele_fraction`, `prs_percentile` | `MeasureBinRow.measure_kind` |
| `VALID_MEASURE_TILINGS` | `binning` | `quantised`, `continuous` | `MeasureBinRow.measure_tiling` |
| `VALID_FUNCTION_STATUS` | `pgx` | `no_function`, `decreased_function`, `normal_function`, `increased_function`, `uncertain_function`, `unknown_function` | `AlleleFunctionRow.function_status` |
| `VALID_TRAINING_ANCESTRY` | `pgs` | `EUR`, `EAS`, `AFR`, `AMR`, `SAS`, `multi` | `PgsRow.training_ancestry` (multi-valued) |
| `VALID_RESEARCH_TIERS` | `pgs` | `research_only`, `calibrated` | `PgsRow.research_tier` |
| `VALID_ICON_SETS` | `manifest` | `fomantic`, `awesome` | `Display.icon_set` |
| `SYMBOLIC_ALLELE_TYPES` | `alleles` | `DEL`, `INS`, `DUP`, `INV`, `CNV` | first-level type of a symbolic allele |

`ACTIONABILITY_SEED` is named as a seed and its own comment in `vocab.py` calls it documentation
only, but `VariantRow._validate_actionability` calls `check_vocab` against it, so it is closed. The
marker on the field records `closed=True`, and `test_reference` asserts it appears under
`vocabularies` rather than `open_recommended`; the mismatch between the constant's name/comment and
its enforcement is called out in `spec.py`'s own field comment.

### 3.2 Open / recommended (a member set, but non-members are kept)

| Constant | Module | Members | Where |
| --- | --- | --- | --- |
| `RECOMMENDED_EFFECT_MEASURES` | `vocab` | `OR`, `HR`, `RR`, `beta`, `log(OR)`, `log(HR)`, `NR` | `VariantRow.effect_measure`, `StudyRow.effect_measure`, `GwasEffectRow.effect_measure` — marker `closed=False`, no validator |
| `RECOMMENDED_AUTHOR_KINDS` | `vocab` | `human`, `human_expert`, `human_certified`, `ai`, `agent`, `team`, `swarm` | `Contribution.kind` — tags are lowercased, stripped and de-duplicated in order; unknown tags kept; at least one tag required |
| `RECOMMENDED_ANCESTRY_GROUPS` | `vocab` | `global`, `afr`, `ami`, `amr`, `asj`, `eas`, `fin`, `mid`, `nfe`, `sas`, `remaining` | `FrequencyRow.population` — only well-formedness is enforced (`^[a-z0-9_]+$`, non-empty, unpadded); an unfamiliar label is kept |
| `RESERVED_FLAGS` | `spec` | `conditional`, `phased`, `pleiotropic` | `VariantRow.flags` — marker `closed=False`; only non-emptiness is enforced |

`FrequencyRow.population` also runs `normalize_population` first: stripped, lowercased, and an
empty/blank label becomes `global`. `POPULATION_ORDER` gives the deterministic emission order
(`global` first, then alphabetical, then unseeded labels alphabetically after all of them) via
`population_sort_key`.

### 3.3 The `-`/`_` separator slip

`vocab.match_vocab(value, vocab)` tries the value as written, then `value.replace("-", "_")`, then
`value.replace("_", "-")`, and returns the **canonical declared member** or `None`.
`check_vocab(value, vocab, field_name)` passes `None` through (absent = unknown) and otherwise raises
`f"{field_name} must be one of {sorted(vocab)}, got: {value!r}"`.

So `declared_use="non-commercial"` is stored as `non_commercial`
(`test_vocab_separator.test_the_authored_cell_now_agrees_with_the_cli_flag`). `test_vocab_separator`
discovers every `VALID_*` frozenset in `vocab` by inspection and asserts both that either separator
resolves and that no vocabulary has two members differing only by separator.

Two things this does **not** cover: it is case-sensitive (`Strong` is refused), and it only
canonicalizes where the caller *uses* `check_vocab`'s return value. Three validators discard it
(§14).

`validate_phenotype_categories` is a separate normalizer: it splits on `[,;|]`, lowercases, and maps
`/`, space and `-` to `_`, so ClinPGx's `Metabolism/PK` becomes `metabolism_pk`. It re-joins with
`;` and returns `None` for an all-empty cell.

### 3.4 The reserved namespace

`RESERVED_NAMES_0_4 = {"reference_db", "callable_element", "quality_element"}`, each with an entry in
`RESERVED_NAME_REASONS` (a test pins that the two sets are equal). These are names a future release
is expected to claim as real module columns. `caller`/`caller_version` were removed from the set and
now take the generic `extra="forbid"` message; `requires_callable`, `acmg_sf`, `actionability`,
`callable_from` and `source_field` left the set by being **built**.

Separately, `normalize.IDENTITY_AUTHORITY_KEYS = {"namespace", "owner", "canonical_id"}` are keys the
format knows about but that a publishing registry stamps. `normalize.reject_authority_keys` is a
`mode="before"` guard on `ModuleInfo` that names them and their reasons; it **diagnoses, it does not
strip**. `normalize.strip_authority_keys(block, authority_keys)` is the opt-in stripper, returning
`(clean, dropped)`; the format applies nothing by default. `version` is deliberately in neither set.

---

## 4. Alleles, genotypes, and the allele algebra

### 4.1 Identifier patterns

| Pattern | Module | Regex |
| --- | --- | --- |
| `RSID_PATTERN` | `vocab` | `^rs\d+$` |
| `ALLELE_PATTERN` | `vocab` | `^[ACGT]+$`, `re.IGNORECASE` |
| `TRAIT_ID_PATTERN` | `vocab` | `^[A-Za-z][A-Za-z]*[:_]\w+$` |
| `MULTI_SEP` | `vocab` | `[,;\|]` |
| `SOURCE_FIELD_PATTERN` | `vocab` | `^ATOM(\|ATOM)*$` where `ATOM = (?:(?:INFO|FORMAT)/)?(?:[A-Za-z_][0-9A-Za-z_.]*|1000G)` |
| `POPULATION_PATTERN` | `vocab` | `^[a-z0-9_]+$` |
| `PMID_PATTERN` | `spec` | `\b(\d{1,8})\b` |
| `PMCID_PATTERN` | `spec` | `PMC(?:ID)?\s*[:\-]?\s*(\d{1,9})`, `re.IGNORECASE` |
| `DOI_PATTERN` | `spec` | `10\.\d{4,9}/\S+` |
| `STAR_ALLELE_PATTERN` | `pgx` | `^\*[0-9A-Za-z][0-9A-Za-z.\-+x×*]*$` |
| `HAPLOTYPE_NAME_PATTERN` | `pgx` | `^\S+$` |
| `PGS_ID_PATTERN` | `pgs` | `^PGS\d+$` |
| `VRS_ID_PATTERN` | `vrs` | `^ga4gh:(VA\|SL\|SQ\|CX\|CN)\.[A-Za-z0-9_-]{32}$` |
| `CAID_PATTERN` | `vrs` | `^CA\d+$` |
| `NAME_PATTERN` | `identity` | `^[a-z][a-z0-9_]*$` |
| `NAMESPACE_PATTERN` | `identity` | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `COLOR_PATTERN` | `manifest` | `^#[0-9a-fA-F]{6}$` |

### 4.2 Allele kinds

`alleles.non_nucleotide_reason(allele)` returns exactly one of five reasons, or `None` when the value
is a nucleotide string. The five are deliberately distinct:

| Reason | Meaning |
| --- | --- |
| `"missing"` | the bare `.` (`MISSING_ALLELE`) — VCF's MISSING marker, asserting there is **no** alternate allele. Not an allele of any kind. |
| `"unobservable"` | `*` (`UNOBSERVABLE_ALLELE`) — this sample's allele could not be observed. A statement about the *call*, not the variant. |
| `"symbolic"` | a well-formed symbolic/structural allele, e.g. `<DEL:1500>` |
| `"ambiguity"` | every character is a base or an IUPAC code (`IUPAC_AMBIGUITY_CODES = RYSWKMBDHVN`), including `N` inside a longer allele |
| `"notation"` | anything else — a repeat notation, a `DELTCT`-style spelling, a typo, or `<FOO>` |

`non_nucleotide_reason` upper-cases and strips before testing, and returns `None` for an **empty**
string as well as for a pure-ACGT string.

`non_nucleotide_alleles(ref, alts)` returns `{allele: reason}` for every non-nucleotide member of a
locus, insertion-ordered with `ref` first. It exists because **no** `ref`/`alt`/`alts` column in the
schema has a nucleotide grammar.

**Symbolic alleles.** `_SYMBOLIC_TOKEN = ^<([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)(?::([0-9]+))?>$`.
`parse_symbolic_allele` returns a frozen `SymbolicAllele(text, type, subtypes, length)` — `type` and
`subtypes` upper-cased, `text` kept as written — or `None` for anything not angle-bracketed, malformed,
or whose first-level type is outside `SYMBOLIC_ALLELE_TYPES`. `.kind` is the colon-joined type without
the length. A length of `0` **parses**. `RECOMMENDED_SYMBOLIC_SUBTYPES = ("CNV:TR", "DUP:TANDEM",
"DEL:ME", "INS:ME")` — the subtype level is open.

`is_symbolic_allele` is deliberately lenient (`^<`), so the unterminated `<DEL` is recognised as an
attempt. `symbolic_allele_defect` answers `"unknown_type"`, `"no_length"` (absent or `<= 0`), or `None`.

**The schema/compiler split is explicit:** `vocab.validate_allele` accepts a lengthless `<DEL>`, and
the field's own error message says "a compile refuses one that states none". Rejecting it at load
would make the row fail to parse, which is fatal in both modes; the decided behaviour is
warn-and-drop under `best_effort`.

`vocab.validate_allele` has exactly two users: `HaplotypeRow.allele` and `VariantRow.effect_allele`.
It accepts a nucleotide string or a well-formed symbolic allele, and **refuses `*`**.

### 4.3 The genotype grammar

`AuthoredModel._validate_genotype` runs on `VariantRow.genotype` (required) and
`PharmVariantRow.genotype` (optional). `base.genotype_allele_ok(allele)` is the single predicate for
one member: a nucleotide string, **or** a parseable symbolic allele, **or** `*`.

Branches, in order:

1. `None` passes through.
2. **GT-index diagnosis**, against `_GT_INDEX_CELL`:

```
^(\d+|\.)([/|](\d+|\.))*$
```

   A cell matching it (`0/1`, `0|1`, `./.`, `0/1/1`) raises with `_GT_INDEX_DIAGNOSIS`, which explains
   that those are indices into the record's own REF/ALT list. This branch is deliberately **before**
   the arity check. (The pattern is fenced rather than inline because it contains `]` followed by `(`,
   which the repository's dead-link guard reads as a markdown link — see `test_doc_links.py`.)
3. **Contains `|`:**
   * if it *also* contains `/` **and** every member (after `|`→`/`) is a spellable allele, it is
     diagnosed as VCF partial phasing;
   * exactly two pipe-separated members are required (otherwise the arity refusal);
   * each member must satisfy `genotype_allele_ok`;
   * a phased pair is **not** sorted — authored order is preserved.
4. **One slash-separated member** — the hemizygous/haploid form (`G`).
5. **Two slash-separated members** — each must be spellable, and `parts == sorted(parts)` is
   enforced: `A/G` is legal, `G/A` is not.
6. **Three or more** — the arity refusal, which appends `_PLOIDY_DIVERGENCE`, a paragraph stating
   that the two-allele cap is a decision rather than a grammar gap and that VCF 4.4 §7.2 goes
   further.

Every one of these three shapes appears verbatim in the printed field description, and
`test_printed_contract.py` asserts that: `A|G` / `C|T` present, the word `hemizygous` present, `/`
present, plus the phrases `"phase recorded but unaddressable"`, `"names no homolog"` and
`"diplotypes.csv"`. It also asserts the description does **not** say `"heterozygous, phase"`, because
`C|C` is an ordinary phased homozygous call the grammar accepts.

`alleles.split_genotype(genotype)` splits on `[/|]` and drops empty fragments, **never sorting**. It
is a split, not a grammar — `|A|G` yields `['A', 'G']` even though the validator refuses that cell.

### 4.4 Reference-free indel comparison

`alleles.parsimony_reduce(alleles)` strips shared flanking sequence — right first, then left, the VCF
trimming convention — stopping before any member is consumed past empty. A collection with fewer than
two distinct members is returned unchanged. Documented doctests:

```
sorted(parsimony_reduce(["C", "CAG"]))   -> ['', 'AG']
sorted(parsimony_reduce(["AGAG", "AG"])) -> ['', 'AG']
sorted(parsimony_reduce(["C", "T"]))     -> ['C', 'T']
```

`alleles.event_profile(alleles)` returns the frozenset of reduced-allele lengths, or **`None`** when
fewer than two distinct alleles remain — which means "the frame is unknown", not "the profile is
empty". A homozygous indel genotype lands there. The three outcomes are: reduced sets match (same
event), length profiles differ (a confident contradiction), lengths agree but content does not
(unknown — only a reference sequence settles it).

---

## 5. Coordinates, builds, and VRS identity

### 5.1 The coordinate convention

Every authored `start` is the **1-based VCF POS**. This is stated in the field descriptions of
`VariantRow.start`, `StudyRow.start`, `HaplotypeRow.start`, `PharmVariantRow.start` and
`ResolutionRow.start`, and `test_coordinate_convention.py` asserts that each description contains
`"1-based"` and does **not** contain `"0-based"`. `VariantRow.start` and `StudyRow.start` also carry
`ge=0`; `HaplotypeRow.start`, `PharmVariantRow.start` and `HeteroplasmyRow.start` carry no bound.

The interbase conversion happens once, inside `vrs.derive_vrs_allele_id`: a 1-base ref at POS *p*
spans `[p-1, p)`.

`vrs.normalize_chrom(chrom)` strips a `chr`/`CHR`/`Chr` prefix, folds `M`/`MT` to `MT`, upper-cases
`X`/`Y`, and otherwise returns the remaining string **unchanged in case**.
`VariantRow._validate_chrom` routes through it and then requires membership in `VALID_CHROMOSOMES`;
on refusal it consults `vrs.sole_build_naming_contig` and, when a contig name belongs to exactly one
tabled build, appends a clause naming that build. No other model validates `chrom`.

### 5.2 Build tables

`vrs.REFGET_GRCh38` maps each of the 25 primary contigs to its refget accession
(`SQ.` + `sha512t24u`). `REFGET_GRCh38_LENGTHS` carries the contig lengths.
`PRIMARY_CONTIG_LENGTHS` holds `{"GRCh38": …, "GRCh37": …}` — GRCh37 is present for *geometry only*;
there is deliberately no `REFGET_GRCh37`, so nothing mints under GRCh37.

`CONTIGS_ONLY_IN` is the set *difference* of top-level scaffold names between the two builds (the 25
primary names are identical across both, so only scaffolds can decide a name question). Lookups fold
case. `sole_build_naming_contig` withholds (`None`) on every name the tables cannot settle, including
an unversioned accession like `GL000205`.

`PAR_GRCh38` gives the two pseudoautosomal intervals per sex contig, 1-based inclusive:
`X: ((10_001, 2_781_479), (155_701_383, 156_030_895))`, `Y: ((10_001, 2_781_479), (56_887_903, 57_217_415))`.

Build-related predicates and their failure modes:

| Function | Off-GRCh38 behaviour |
| --- | --- |
| `refget_accession(chrom, build)` | **raises `UnsupportedBuildError`** — a wrong answer here would corrupt an identity |
| `refget_supports_build(build)` | returns `False`; both read the one predicate `_build_has_refget_table(build)`, i.e. `build == "GRCh38"` — so `None` and `""` are `False` |
| `in_pseudoautosomal_region(chrom, start, build)` | returns `None` (tri-state: `True`/`False`/cannot say) |
| `par_partner(chrom, start, build)` | returns `None` |
| `contig_length(chrom, build)` | returns `None` |
| `builds_containing_position(chrom, start)` | returns a sorted tuple; only the **upper** bound is consulted, because VCF's telomere convention writes POS 0 |
| `derive_vrs_allele_id(..., build)` | **raises `UnsupportedBuildError`** for an untabled build; returns `None` for an unmintable row |

`par_partner` uses `zip(here, there, strict=True)`, so a PAR table that ever gained an interval on
one contig and not the other fails loudly rather than silently answering for PAR1 only.

### 5.3 VRS allele ids

`sha512t24u(blob)` is unpadded base64url of the first 24 bytes of SHA-512 — exactly 32 characters.
`_canonical(obj)` is `json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")`.

`sequence_location_digest(chrom, start, end, build)` digests
`{"end": …, "sequenceReference": {"refgetAccession": …, "type": "SequenceReference"}, "start": …, "type": "SequenceLocation"}`
over **interbase** coordinates, returning the bare digest (not the `ga4gh:SL.` CURIE).

`derive_vrs_allele_id(chrom, start, ref, alt, build="GRCh38")` mints
`"ga4gh:VA." + sha512t24u(_canonical({"location": <bare SL digest>, "state": {"sequence": ALT, "type": "LiteralSequenceExpression"}, "type": "Allele"}))`.

It returns `None` — never guesses — when the row is not a mintable **single-base substitution**
(`is_substitution`: one ACGT base to a *different* one ACGT base, case-insensitive):

* no coordinate; `start < 1`;
* an indel or MNV (justification needs the reference sequence, which this tier will not fetch);
* a multi-allelic `alt` (a comma) — the caller must split first;
* a contig outside the primary assembly, or a position past the contig's length.

`VRS_SPEC_VERSION = "2.0"`. `ResolutionRow.vrs_spec` records it to disambiguate an embedded location
id, not because the allele digest drifts.

**The parallel-array contract.** `ResolutionRow.vrs_id` is one id per ALT, comma-joined, positionally
aligned with `alts`; an empty member is a *hole* meaning "that allele's id could not be minted".
`split_vrs_ids(cell) -> list[str | None]` and `join_vrs_ids(ids) -> str | None` (all holes → `None`,
never `",,"`). `validate_vrs_id_list` validates member by member and returns the canonical joined
spelling; `ResolutionRow._vrs_ids_align_with_alts` then checks the counts, but **only when both
columns are filled** — a `vrs_id` on a row with no `alts` is left alone as under-specified rather
than contradictory.

`validate_vrs_id` accepts any of the five identifiable VRS types; `validate_vrs_allele_id` requires
the `ga4gh:VA.` prefix and is what both `vrs_id` columns use.

### 5.4 `variant_key`

`base.derive_variant_key(rsid, chrom, start, ref, alts=None, *, build="GRCh38")` — three cases, in
precedence order:

1. **rsid**, unchanged, whenever `rsid is not None`.
2. **A resolved single-base substitution** — the GA4GH VRS allele id. Only attempted when `alts` is
   truthy and contains no comma; `_mint_vrs_key` swallows `UnsupportedBuildError` and falls through.
3. **The coordinate key** — `f"{chrom}:{start}:{ref}"`, or `f"{chrom}:{start}:{ref}:{alts_norm}"`
   where `alts_norm` is the comma-separated alleles **sorted** and re-joined, so authored allele
   order does not change identity.

`alts` is passed only when *minting* an identity. Position-level matching calls it without: `StudyRow`
and the two PGx models derive their key with `alts=None`.

Worked values from the tests:

```
derive_variant_key("rs9", "1", 5, "A")            == "rs9"
derive_variant_key(None, "1", 5, "A")             == "1:5:A"
VariantRow(chrom="11", start=5226762, ref="C", alts="CAAAG", …).variant_key == "11:5226762:C:CAAAG"
VariantRow(chrom="11", start=5226762, ref="C", alts="G,A",   …).variant_key == "11:5226762:C:A,G"
VariantRow(chrom="11", start=5226762, ref="C", alts="G",     …).variant_key == derive_vrs_allele_id("11", 5226762, "C", "G")
```

**Freezing.** `VariantRow._freeze_identity` is a `mode="after"` validator, so it runs at construction
and **not** on `model_copy`. It unconditionally overwrites any authored `variant_key`,
`authored_ident`, `locus_index` (`0`) and `locus_count` (`1`). That is what lets the resolver fill an
rsid or a coordinate afterwards without the row re-keying:

```python
row = VariantRow(chrom="1", start=100, ref="A", …)   # variant_key == "1:100:A"
row.model_copy(update={"rsid": "rs1"}).variant_key    # still "1:100:A"
```

`authored_ident` records which of `("rsid", "chrom", "start", "ref", "alts")` the author actually
supplied, in that order. It is what makes resolution reversible: a reverse writer re-emits the
authored shape rather than whatever resolution filled in.

`VariantRow._freeze_identity` calls `derive_variant_key` **without** a `build` argument, so a row
constructed in isolation on a GRCh37 module takes the GRCh38 default until the compiler restamps it.
That is documented in `AuthoredModel.with_genome_build`, which notes `VariantRow` deliberately keeps
its own restamp; it is a real sharp edge for anyone using these models standalone.

`StudyRow.variant_key` is a derived **property**, not a stored column — a study row is never resolved
or expanded. It answers `None` when both `rsid` and `chrom` are `None`.

`HeteroplasmyRow.variant_key`/`authored_ident` are `stamped_identity_field`s: compiler-managed,
`exclude=True`, and re-derived by `with_genome_build` because this key includes `alts` and can
therefore mint a VA. `HaplotypeRow` and `PharmVariantRow` are the same but with
`_KEY_INCLUDES_ALTS = False`.

---

## 6. The authored DSL

### 6.1 `module_spec.yaml` — `ModuleSpecConfig`

`extra="forbid"` at every level. A `mode="before"` validator refuses `<<REPLACE>>` anywhere in the
document (the scan recurses into nested mappings and lists).

| Key | Type | Category | Default | Notes |
| --- | --- | --- | --- | --- |
| `schema_version` | `str` | defaulted | `"1.0"` | must equal `manifest.SCHEMA_VERSION`; any other value raises |
| `module` | `ModuleInfo` | required | — | |
| `defaults` | `Defaults` | defaulted | `Defaults()` | |
| `genome_build` | `str` | defaulted | `"GRCh38"` | free string; the description states the reference compiler is GRCh38-bound and another build is recorded but not honoured |
| `panel` | `GenePanelSpec \| None` | optional | `None` | deprecated in 0.6, removal announced for 1.0 |
| `authorship` | `list[Contribution]` | defaulted | `[]` | |
| `license` | `str \| None` | optional | `None` | advisory; registry-overridable; not reconstructed by a reverse |
| `weighting` | `Weighting \| None` | optional | `None` | what the module's `weight` column means |

`ModuleInfo` extends `manifest.Display` and adds:

| Key | Type | Category | Default | Notes |
| --- | --- | --- | --- | --- |
| `title`, `description`, `report_title` | `str` | required | — | inherited from `Display` |
| `icon` | `str` | defaulted | `"database"` | free-form within `icon_set` |
| `icon_set` | `str` | defaulted | `"fomantic"` | closed: `fomantic`, `awesome` |
| `color` | `str` | defaulted | `"#6435c9"` | `^#[0-9a-fA-F]{6}$` |
| `name` | `str` | required | — | `^[a-z][a-z0-9_]*$` |
| `version` | `str \| None` | optional | `None` | advisory; coerced to SemVer |

`version` handling has two stages. A `mode="before"` validator turns an `int` into a `str` (because
YAML reads a bare `version: 3` as an integer), passes a `bool` through to the string check, and
**raises on a `float`** with a message telling the author to quote it — YAML has already read `1.10`
as `1.1`, so the text is unrecoverable. Then a `mode="after"` validator runs
`normalize.normalize_version` and, if the result differs, records the original on the private
`_version_coerced_from`, exposed as the `version_coerced_from` property (not a field, so it never
reaches `model_dump()`).

`normalize_version` strips everything that is not a digit or `.`, takes the first three fields
(empty → `0`), and right-pads to three: `v2 → 2.0.0`, `3 → 3.0.0`, `1.5 → 1.5.0`,
`v1.2.3-beta → 1.2.3`, a value with no digits → `0.0.0`. It is idempotent.

`Defaults`: `curator` (defaulted, `"ai-module-creator"`), `method` (defaulted,
`"literature-review"`), `priority` (optional, `None`).

`GenePanelSpec` (deprecated): `source` required; `reference`, `reference_sha256` optional; `genes`
and `significance` default to empty lists. The compiler records it verbatim and never materializes
rows from it.

`Weighting`: `scale`, `method`, `note` — all optional free text, deliberately not a vocabulary, and
deliberately carrying no *precedence* rule.

### 6.2 `VariantRow` (`variants.csv`)

Identity rule (`_validate_identification`): at least `rsid` **or** `chrom`+`start`; if either
positional column is given both are required; `ref`/`alts` require `chrom`+`start`.

| Field | Type | Category | Default | Notes |
| --- | --- | --- | --- | --- |
| `rsid` | `str \| None` | optional | `None` | `^rs\d+$` |
| `chrom` | `str \| None` | optional | `None` | closed `chromosome` vocabulary; normalized (`chr7`→`7`, `chrM`/`M`→`MT`) |
| `start` | `int \| None` | optional | `None` | `ge=0`; 1-based VCF POS |
| `ref` | `str \| None` | optional | `None` | always bases — "VCF's REF is a sequence, never symbolic" |
| `alts` | `str \| None` | optional | `None` | comma-separated; bases or a symbolic allele carrying its length |
| `variant_key` | `str \| None` | optional | `None` | **compiler-managed**, *not* `exclude`d |
| `authored_ident` | `list[str] \| None` | optional | `None` | **compiler-managed**, *not* `exclude`d |
| `locus_index` | `int \| None` | optional | `0` | compiler-managed, `exclude=True` |
| `locus_count` | `int \| None` | optional | `1` | compiler-managed, `exclude=True`; `locus_count > 1` is the row-level "this row is one of an expansion" predicate |
| `genotype` | `str` | **required** | — | §4.3 |
| `weight` | `float \| None` | optional | `None` | finite; "Score (positive=protective)"; **no unit column** — see `Weighting` |
| `state` | `str` | **required** | — | closed: `risk`, `protective`, `neutral`, `significant`, `alt`, `ref` |
| `conclusion` | `str` | **required** | — | |
| `negatives` | `str \| None` | optional | `None` | adverse/antagonistic-pleiotropy counterpart to `conclusion` |
| `priority`, `gene`, `phenotype`, `category`, `curator`, `method` | `str \| None` | optional | `None` | |
| `clinvar`, `pathogenic`, `benign` | `bool \| None` | optional | `None` | the legacy ClinVar flags |
| `direction` | `str \| None` | optional | `None` | closed |
| `stat_significance` | `str \| None` | optional | `None` | closed |
| `effect_size` | `float \| None` | optional | `None` | finite |
| `effect_measure` | `str \| None` | optional | `None` | open, recommended set |
| `effect_allele` | `str \| None` | optional | `None` | `validate_allele` — bases or a symbolic allele; `*` refused |
| `flags` | `list[str] \| None` | optional | `None` | CSV cell split on `[,;\|]`; open; entries must be non-empty strings |
| `trait_efo_id` | `str \| None` | optional | `None` | multi-valued CURIEs |
| `clin_sig` | `str \| None` | optional | `None` | closed |
| `requires_callable` | `bool \| None` | optional | `None` | true when the *absence* of the variant is the informative call |
| `acmg_sf` | `bool \| None` | optional | `None` | |
| `actionability` | `str \| None` | optional | `None` | closed against `ACTIONABILITY_SEED` |
| `callable_from` | `str \| None` | optional | `None` | VCF pointer grammar |
| `quality_from` | `str \| None` | optional | `None` | VCF pointer grammar |
| `min_quality` | `float \| None` | optional | `None` | finite; inclusive floor |

`_require_quality_pair`: `quality_from` and `min_quality` are **both or neither**; either half alone
raises, because half a floor reads as a configured gate and is not one.

**Read-time derivations.** `state` and the ClinVar booleans stay required/authoritative; the 0.3 axes
are optional with derivations as fallback, all total and idempotent (`just_dna_format.derive`):

| Property | Falls back to |
| --- | --- |
| `effective_direction` | `derive.direction_from_state(state, weight)` — `significant` refines by weight sign (positive → `protective`, negative → `risk`); `alt`/`ref`/`significant` otherwise → `unknown` |
| `effective_stat_significance` | `derive.stat_significance_from_state(state)` — only `significant` is informative |
| `effective_clin_sig` | `derive.clin_sig_from_booleans(pathogenic, benign, clinvar)` — `pathogenic`, else `benign`, else in-ClinVar → `uncertain_significance`, else `None` |
| `effective_pathogenic` | `derive.pathogenic_from_clin_sig` — `True` for the two pathogenic tiers, else `None` (never a fabricated `False`) |
| `effective_benign` | `derive.benign_from_clin_sig` — `True` for the two benign tiers, else `None` |

`upgraded()` returns a `model_copy` with those materialized and `state` projected through
`derive.trimmed_state(direction)` (`unknown → neutral`). `needs_upgrade` is `self.upgraded() != self`.

### 6.3 `StudyRow` (`studies.csv`)

| Field | Type | Category | Default | Notes |
| --- | --- | --- | --- | --- |
| `rsid`, `chrom`, `ref` | `str \| None` | optional | `None` | no `chrom` vocabulary and no chrom validator on this model |
| `start` | `int \| None` | optional | `None` | `ge=0` |
| `pmid` | `str` | **required** | — | free-form, kept verbatim; must carry at least one PubMed id |
| `population`, `p_value`, `conclusion`, `study_design` | `str \| None` | optional | `None` | |
| `stat_significance` | `str \| None` | optional | `None` | closed |
| `effect_size` | `float \| None` | optional | `None` | finite |
| `effect_measure` | `str \| None` | optional | `None` | open |
| `effect_allele` | `str \| None` | optional | `None` | absent means the study did not state one — *not* the reference allele |
| `trait_efo_id` | `str \| None` | optional | `None` | |
| `doi` | `str \| None` | optional | `None` | must contain a DOI token; kept verbatim |
| `provenance_quote` | `str \| None` | optional | `None` | a literal passage |
| `provenance_regex` | `str \| None` | optional | `None` | must compile under Python `re`; ReDoS-safety is the consumer's problem |
| `p_value_num` | `float \| None` | optional | `None` | `gt=0.0`, `le=1.0` — an exact `0` is a source's underflow, not a probability |

`neg_log10_p` is a derived property (`-log10(p) + 0.0`, the `+ 0.0` normalizing the `-0.0` that
`p == 1` would otherwise produce). `None` when `p_value_num` is unset.

`_validate_study_identification`: a row may name **no** variant at all (`REQUIRED_ANY_OF == ()`), but
never half of one — `start`/`ref` present with neither `rsid` nor `chrom` raises.

**PMID/DOI grammar.** `validate_pmid_cell(value, field, *, required)` is shared with
`MeasureBinRow.pmid`. It accepts anything carrying at least one PMID token and keeps it verbatim
(`"PMID 17478681; PMID 21378990;"` round-trips unchanged). If the cell carries only PMC ids it
raises a message naming them — `PMC 3110566` used to parse as PMID 3110566, a real unrelated
article, because `PMID_PATTERN` finds a digit run and there *is* a word boundary after the space.
`extract_pmids` excludes any digit run whose span lies inside a `PMCID_PATTERN` match;
`extract_pmcids` canonicalizes to `PMC…`. The function **never repairs** a PMCID into a PMID.

### 6.4 The binning primitive

`MeasureBinRow` is the base; four subclasses pin `_EXPECTED_KIND` and declare `_KEY_FIELDS`.

Shared columns:

| Field | Type | Category | Default | Notes |
| --- | --- | --- | --- | --- |
| `measure_kind` | `str` | required on the base, defaulted on each subclass | — / the subclass's kind | closed |
| `measure_min` | `float \| None` | optional | `None` | **inclusive** lower bound; `None` = open below; also the tie-break under continuous tiling |
| `measure_max` | `float \| None` | optional | `None` | **inclusive** on every kind; `None` = open above |
| `measure_tiling` | `str \| None` | optional | `None` | closed: `quantised`, `continuous`; empty means the kind's default, never a third value |
| `direction`, `clin_sig` | `str \| None` | optional | `None` | closed |
| `phenotype`, `trait_efo_id` | `str \| None` | optional | `None` | |
| `conclusion` | `str` | **required** | — | |
| `unresolved` | `bool` | **defaulted** | `False` | the sentinel a consumer selects when the measurement is absent |
| `source_field` | `str \| None` | optional | `None` | VCF pointer grammar |
| `source_element` | `str \| None` | optional | `None` | closed `VALID_ELEMENT_RULES`; requires `source_field` |
| `pmid` | `str \| None` | optional | `None` | grounds **this boundary**; the bin row cites, `studies.csv` describes |

`_validate_range`: an `unresolved` row must carry neither bound; a resolved bin needs at least one;
`measure_min <= measure_max` (equal is a sharp value). Both bounds go through `validate_finite`.

`measure_max`'s description carries the float32 rule verbatim, and `test_printed_contract.py` asserts
the words `float32`, `narrow` and `epsilon` appear in it, and that every subclass renders the same
string. The rule: a VCF `Float` is 32-bit, so a source cell reading `0.3` widens to
0.300000011920928955… (above an authored inclusive `0.3`) while `0.9` widens to 0.899999976158142…
(below it). **Neither bound is the safe one**, so the comparison is done by narrowing *both* sides to
float32 — never with an epsilon, which would be a guess where the representation is exactly known.

Subclasses:

| Model | `_EXPECTED_KIND` | Extra fields | `_KEY_FIELDS` |
| --- | --- | --- | --- |
| `ActivityPhenotypeRow` | `activity_score` | `gene` (required) | `("gene",)` |
| `CopyNumberRow` | `copy_number` | `gene` (required), `modifier_gene`, `modifier_cn` (deprecated `int`), `modifier_copy_number` (`float`) | `("gene", "modifier_gene", "effective_modifier_copy_number")` |
| `RepeatAlleleRow` | `repeat_count` | `gene`, `repeat_unit` (both required) | `("gene", "repeat_unit")` |
| `HeteroplasmyRow` | `allele_fraction` | `gene`, `reference_sequence` (both required), `rsid`, `chrom`, `start`, `ref`, `alts`, `tissue`, `assay_context`, stamped `variant_key`/`authored_ident` | `("gene", "reference_sequence", "tissue", "variant_key")` |

`CopyNumberRow`: setting both `modifier_cn` and `modifier_copy_number` is an **error**, not a
precedence rule. `effective_modifier_copy_number` coalesces with `is not None` (0 is a legal dosage)
and is what both grouping sites read. `modifier_gene` and the effective dosage are set together or
both null. `binning.deprecation_warnings(rows)` emits at most one line per table naming
`modifier_cn`.

`HeteroplasmyRow`: bounds constrained to `[0, 1]`; `reference_sequence` refuses the
`LEGACY_MT_REFERENCE_BASES = {"NC_001807"}` lineage (matched on the accession stem, so `NC_001807.4`
is refused too), because it silently disagrees with rCRS coordinates and yields a confidently-wrong
haplogroup. `CANONICAL_MT_REFERENCE_SEQUENCES = {"NC_012920.1"}`.

**Tiling.** `DEFAULT_MEASURE_TILING` is derived from three private sets rather than restated:

| Kind | Default tiling |
| --- | --- |
| `copy_number`, `repeat_count` | `quantised` |
| `allele_fraction`, `prs_percentile` | `continuous` |
| `activity_score` | `None` — neither: a shared endpoint is an overlap error **and** interior holes are not reported |

`resolve_tiling(group) -> TilingResolution(value, declared, default, fractional, disagreement)`:

* two rows of one group declaring different tilings are recorded as `disagreement` and **returned**,
  not raised, so the warning path cannot be crashed by a table the error path will refuse;
* otherwise the single declared value wins;
* otherwise, if the group carries a fractional bound **and** the kind's default is `quantised`, the
  value becomes `continuous` (`.inferred` is `True`);
* otherwise the kind's default.

The inference runs one way only: fractional-ness contradicts a grid, integer-ness contradicts
nothing. An explicit `quantised` beside a fractional bound **stands** and is reported via
`.contradicted`. Only `measure_min`/`measure_max` are read — `_fractional_values` deliberately
excludes the modifier dosage, because it is a *group-key* column and letting it vote flips legality
on identical bins.

`validate_bins(rows) -> list[str]` groups by `_KEY_FIELDS + (trait_efo_id,)`, ignoring `unresolved`
rows, and per group:

* **raises** on conflicting `measure_tiling`;
* warns on an inferred tiling, or on a contradicted `quantised` declaration;
* **raises** `"overlapping bins"` when `lo < prev_hi`, or when `lo == prev_hi` and the tiling is not
  `continuous`;
* **raises** `"bins with the same lower bound"` when two bins share `measure_min` — the boundary rule
  picks the greatest `measure_min <= x` and equals cannot be separated;
* warns `"coverage gap for key …: no bin covers (prev_hi, lo)"` when the hole exceeds `1e-9`
  (continuous) or `1 + 1e-9` (quantised); under `None` tiling no gap is reported at all.

The quantised step is hardcoded to `1` and there is no way to state another — documented on
`measure_tiling`'s description, which notes that declaring `quantised` on a bounded domain switches
interior gap reporting off entirely.

`format_group_key` renders an integral float as an integer, so the coalesce of the deprecated `int`
modifier column does not turn every published warning's `2` into `2.0`. Warning text is treated as an
API: `FRACTIONAL_MEASURE_PHRASE = "is not a whole number in VCF 4.4"`,
`SPANNING_MEASUREMENT_PHRASE = "one measurement can span several bins"`,
`DEPRECATED_MODIFIER_PHRASE = "`modifier_cn` is deprecated"` are named constants.

`measurement_shape_warnings(rows)` emits, once per kind and never per row, two findings for the kinds
in `_VCF_MEASURE_FIELDS` (`copy_number` → `CN`/`CICN`, `repeat_count` → `RUC`/`CIRUC`): a fractional
measurement between adjacent quantised bins matches neither (only when some group of that kind
resolves to `quantised`), and a measurement travelling with a confidence interval can span several
bins (only when the widest group has ≥2 resolved bins). Both are warnings in **both** modes and never
escalate.

### 6.5 The PGx tables

`validate_haplotype_name(value, field)` is the one rule for a haplotype **name**, shared by all three
tables: `^\S+$` — non-empty and no whitespace. `STAR_ALLELE_PATTERN` still exists and is used by
drafting providers, but is no longer enforced by any model; `e4` and `ε4` are legal everywhere.
`test_v04.test_the_three_pgx_tables_agree_on_what_a_haplotype_name_is` asserts this as a property
over the three tables.

**`HaplotypeRow`** — one defining variant of a named haplotype.

| Field | Type | Category | Notes |
| --- | --- | --- | --- |
| `haplotype_name` | `str` | required | a name, not a star grammar |
| `rsid`, `chrom`, `start`, `ref` | optional | | no chrom validator; `start` has no `ge` bound |
| `alts` | `str \| None` | optional | **compiler-filled**, `exclude=True`; authoring it raises |
| `allele` | `str` | required | the defining allele — `validate_allele` |
| `gene` | `str \| None` | optional | |
| `variant_key`, `authored_ident` | | | stamped, `exclude=True` |

`_validate_identification`: rsid, or chrom **and** start.

**`AlleleFunctionRow`** — allele-unit → activity.

| Field | Type | Category | Notes |
| --- | --- | --- | --- |
| `gene`, `allele` | `str` | required | `allele` is the verbatim canonical identity |
| `activity_value` | `float \| None` | optional | finite |
| `function_status` | `str \| None` | optional | closed |
| `suballele`, `sv_type`, `hybrid_orientation` | `str \| None` | optional | parsed conveniences; the string is truth |
| `copy_number` | `int \| None` | optional | *cis* copy number of the allele-unit |

**`DiplotypeRow`** — a haplotype pair → phenotype.

| Field | Type | Category | Notes |
| --- | --- | --- | --- |
| `gene`, `haplotype_a`, `haplotype_b`, `conclusion` | `str` | required | the pair is canonicalized so `haplotype_a <= haplotype_b` |
| `trait_efo_id`, `direction`, `clin_sig`, `phenotype` | | optional | |
| `drug`, `response` | `str \| None` | optional | |
| `evidence_level` | `str \| None` | optional | PharmGKB `1A`…`4` |
| `recommendation_strength` | `str \| None` | optional | CPIC's grading — a **different axis** from `evidence_level`; the two vocabularies are disjoint |
| `clinical_context` | `str \| None` | optional | free text (indication, age band, prior treatment, dose); stripped, empty → `None`; part of the row key so contexts coexist |

**`PharmVariantRow`** — one variant → drug → response.

| Field | Type | Category | Notes |
| --- | --- | --- | --- |
| `rsid`, `chrom`, `start`, `ref` | | optional | rsid, or chrom+start |
| `alts` | | optional | compiler-filled, `exclude=True`, carried as *data*: the key omits it |
| `gene` | | optional | |
| `genotype` | `str \| None` | optional | the shared grammar; canonical form is sorted and slash-separated (`C/C`, not PharmGKB's `CC`) |
| `variant_key`, `authored_ident` | | | stamped, `exclude=True` |
| `drug` | `str` | **required** | |
| `phenotype_category` | `str \| None` | optional | closed, multi-valued via `[,;\|]`; part of the identity |
| `annotation_id` | `str \| None` | optional | the source's own accession; the tie-break of last resort |
| `response`, `evidence_level`, `trait_efo_id` | | optional | |
| `conclusion` | `str` | **required** | |

### 6.6 `PgsRow` (`pgs.csv`)

A manifest of PGS Catalog ids, not authored weights.

| Field | Type | Category | Notes |
| --- | --- | --- | --- |
| `pgs_id` | `str` | required | `^PGS\d+$` |
| `trait_efo_id`, `note`, `group`, `training_cohort` | `str \| None` | optional | |
| `training_ancestry` | `list[str] \| None` | optional | CSV cell split on `[,;\|]`; each token checked against the closed `VALID_TRAINING_ANCESTRY` |
| `match_rate_floor` | `float \| None` | optional | finite and within `[0, 1]`; only the **floor** lives in-module — the observed rate is a measurement |
| `research_tier` | `str \| None` | optional | closed: `research_only`, `calibrated` |

`VALID_TRAINING_ANCESTRY` (1000G superpopulations) and `RECOMMENDED_ANCESTRY_GROUPS` (gnomAD
population labels) are two different axes and `vocab.py` forbids merging them; the vocabulary marker
is keyed by vocabulary *name* rather than field name precisely so the two cannot collapse.

---

## 7. Derived-fact sidecars

These row models are **standalone `BaseModel`s**, not `AuthoredModel`s: a derived fact is not an
authored annotation, so it must not inherit the annotation validators or the authoring guards. Each
sets `extra="forbid"` so a typo'd column is caught rather than dropped. `SourceRow` is the one
exception that reaches back for a guard — it carries `reject_template_placeholders`, because it is
the only fact sidecar a human writes from a template and the only one the compile licence gate reads.

Every one of them carries `source` / `status` / `fetched_at` as **provenance**, excluded from its
fact hash. `fetched_at` is canonicalized on load by `normalize.normalize_utc_timestamp`.

| Model | File | Grain / natural key | Fact tuple |
| --- | --- | --- | --- |
| `ResolutionRow` | `resolution.csv` | one resolved (or attempted) locus per authored `variant_key`; a one-to-many rsid is several rows sharing `variant_key` with distinct `locus_index` | `RESOLUTION_FACT_FIELDS` |
| `FrequencyRow` | `frequencies.csv` | one `(allele, ancestry group)` pair | `FREQUENCY_FACT_FIELDS` |
| `GeneMetricsRow` | `gene_metrics.csv` | one gene per source/release | `GENE_METRICS_FACT_FIELDS` |
| `LiteratureRow` | `literature.csv` | one cited article, keyed by PMID | `LITERATURE_FACT_FIELDS` |
| `SourceRow` | `sources.csv` (deprecated) / `licensing.csv` | one `(source, layer)` pair | `SOURCE_FACT_FIELDS` |
| `GeneValidityRow` | `gene_validity.csv` | one assertion: `(gene, disease, mode of inheritance, submitter)` | `GENE_VALIDITY_FACT_FIELDS` |
| `ClinicalAssertionRow` | `clinical_assertions.csv` | one `(allele, archive record)` | `CLINICAL_ASSERTION_FACT_FIELDS` |
| `GwasEffectRow` | `gwas_effects.csv` | one published association, keyed by `association_id` | `GWAS_FACT_FIELDS` |

### 7.1 Fact-field tuples, verbatim

```
RESOLUTION_FACT_FIELDS   = variant_key, rsid, chrom, start, ref, alts, genome_build, locus_index
FREQUENCY_FACT_FIELDS    = variant_key, rsid, chrom, start, ref, alt, population, allele_count,
                           allele_number, homozygote_count, hemizygote_count, faf95, dataset,
                           genome_build
GENE_METRICS_FACT_FIELDS = gene, gene_id, transcript, mane_select, pli, loeuf, oe_lof, oe_lof_lower,
                           lof_z, mis_z, syn_z, oe_mis, obs_lof, exp_lof, constraint_flags,
                           haploinsufficiency, triplosensitivity, dataset
LITERATURE_FACT_FIELDS   = pmid, doi, pmcid, exists
SOURCE_FACT_FIELDS       = source, layer, license, license_url, license_sha256, attribution, notice,
                           share_alike, commercial_use, redistribution, declared_use, dataset
GENE_VALIDITY_FACT_FIELDS= gene, gene_id, disease_id, moi, classification, classification_raw,
                           classification_date, submitter, assertion_id, dataset
CLINICAL_ASSERTION_FACT_FIELDS = variant_key, chrom, start, ref, alt, genome_build, clin_sig,
                           clin_sig_raw, review_status, review_stars, condition, variation_id, dataset
GWAS_FACT_FIELDS         = association_id, variant_key, rsid, effect_allele, effect_size,
                           effect_measure, effect_unit, effect_direction, standard_error,
                           confidence_interval, risk_allele_frequency, p_value, p_value_num,
                           trait_efo_id, pmid, study_accession, ancestry, dataset
VERIFICATION_FACT_FIELDS = check, subjects, findings, skipped, source, release
```

The inclusions and exclusions are individually argued in the code and several of them invert each
other on purpose:

* `dataset` is **inside** every tuple that has one — two releases are two facts.
* `source` is **outside** everywhere except `SOURCE_FACT_FIELDS`, where the source is the *subject*
  of the row rather than the provenance of one.
* `rsid` is **inside** `FREQUENCY_FACT_FIELDS` and `GWAS_FACT_FIELDS` (both sources return it in
  their own payload) and **outside** `CLINICAL_ASSERTION_FACT_FIELDS` (the ClinVar lookup is
  allele-exact and returns none, so the column is filled from the module's own `resolution.csv` —
  inside the hash it would make identical archive records hash differently by producer).
* `disease_label` and `trait` are **outside** their tuples on one rule: a column that *locates or
  describes* an assertion is not the assertion. `report_url` likewise.
* `vrs_id`/`caid` are outside both `RESOLUTION_FACT_FIELDS` and `FREQUENCY_FACT_FIELDS`.
* `LiteratureRow`'s licence columns, `is_open_access`, and the quote counters are all outside: an
  embargo lifting or a publisher re-licensing changes the world, not the module.
* `SourceRow.draft_digest` is outside; it moves on every re-draft while the terms stand still.

### 7.2 Notable per-model rules

`ResolutionRow` — `variant_key` required; `locus_index` defaulted `0`, `ge=0`; `genome_build`
defaulted `"GRCh38"`. `source` names the **link** that answered (`cache`, `ensembl-graphql`,
`ensembl-rest`, `manual`, `reversed`); `authority` names the **licensed source** the link speaks for
and is what joins `sources.csv.source`. The two columns exist separately because one name was
carrying two vocabularies. `rsid_current` is *recorded, never substituted*. `rsid_status` uses the
four-member `VALID_RSID_STATUS`; the field's own description states that the automated check never
emits `withdrawn`, that `absent` names two readings (typo *or* retraction), and that the two differ
in severity.

`FrequencyRow` — `alt` is deliberately **singular** (a frequency is per-allele; a multi-allelic site
is several rows), unlike `ResolutionRow.alts`. Counts are integers; `allele_frequency` is a derived
property returning `None` when `allele_count` is `None` **or** `allele_number` is falsy — an `AN` of
0 means "no information", not "frequency zero". `faf95` is the one stored float, bounded `[0, 1]`,
set only on the group the source names as owning it.

`GeneMetricsRow` — `dataset` required. `haploinsufficiency`/`triplosensitivity` are stored as
**terms**, not ClinGen's numeric codes, because the codes `{0, 1, 2, 3, 30, 40}` look ordinal and are
not (`40` = "dosage sensitivity unlikely" would sort above `3` = "sufficient evidence").
`DOSAGE_SENSITIVITY_BY_CODE` publishes the total, lossless mapping.

`LiteratureRow` — `pmid` must be digits only here (the free-form authored form lives in
`studies.csv`); `pmcid` is upper-cased and must be `PMC` + digits; `doi` must contain a DOI token.
`quotes_found` is null-means-not-checked, distinct from `0`. There is deliberately no `dataset`
column — PubMed and Europe PMC publish no release identifier. The article's licence lives on this row
**per article**, and there is deliberately no `pubmed` row in the licence table.

`SourceRow` — `source` and `layer` required. `share_alike`, `commercial_use` and `redistribution` are
three orthogonal tri-state booleans where `None` means **unknown, never false**.
`sources.taints_commercial_use(row)` is `row.commercial_use is False and row.layer == "annotation"`;
`taints_redistribution` is the same shape on the third axis. An *unknown* never taints.

`GeneValidityRow` — `gene` and `dataset` required and stripped-non-empty. `classification_date` goes
through the same UTC canonicalizer as `fetched_at`, because ClinGen writes
`2024-03-14T16:00:00.000Z` and GenCC writes `2018-03-30 13:31:56`.

`ClinicalAssertionRow` — `variant_key` and `dataset` required. `review_stars` is `ge=0, le=4` and is
**stored** rather than derived from `review_status`, because the prose→stars mapping is a ClinVar
convention this tier does not hold. Null stars ≠ 0 stars.

`GwasEffectRow` — `association_id`, `variant_key`, `dataset` required. The row carries **no
coordinates** by design. `effect_allele` is null where the Catalog wrote `-?`; such rows are counted
rather than dropped. `effect_unit` is kept verbatim including uninformative values like `"unit"`.
`confidence_interval` is a string because the bracket forms vary and `[NR]` is real.

---

## 8. CSV table families

The schema tier owns filenames only for the machine-written sidecars (`layout.py`). The authored
table filenames appear in docstrings and diagnostics but no constant declares them.

| File | Model | Kind | Optional? | Natural key |
| --- | --- | --- | --- | --- |
| `module_spec.yaml` | `ModuleSpecConfig` | authored | required | — |
| `variants.csv` | `VariantRow` | authored | a module includes only the kinds it uses | `variant_key` + `genotype` |
| `studies.csv` | `StudyRow` | authored | optional | `(variant_key, pmid)`; `variant_key` may be `None` |
| `repeat_alleles.csv` | `RepeatAlleleRow` | authored | optional | `(gene, repeat_unit)` + `trait_efo_id` + the bin range |
| `copynumbers.csv` | `CopyNumberRow` | authored | optional | `(gene, modifier_gene, effective_modifier_copy_number)` + `trait_efo_id` + range |
| `activity_phenotype.csv` | `ActivityPhenotypeRow` | authored | optional | `(gene,)` + `trait_efo_id` + range |
| `heteroplasmy.csv` | `HeteroplasmyRow` | authored | optional | `(gene, reference_sequence, tissue, variant_key)` + `trait_efo_id` + range |
| `haplotypes.csv` | `HaplotypeRow` | authored | optional | `(haplotype_name, variant_key)` |
| *(allele-function table)* | `AlleleFunctionRow` | authored | optional | `(gene, allele)` — **filename undetermined from the schema tier's code** |
| `diplotypes.csv` | `DiplotypeRow` | authored | optional | `(gene, haplotype_a, haplotype_b, clinical_context, …)` — multiple rows per pair are allowed |
| `pharm_variants.csv` | `PharmVariantRow` | authored | optional | `(variant_key, drug, genotype, phenotype_category, annotation_id)` |
| `pgs.csv` | `PgsRow` | authored | optional | `pgs_id` |
| `resolution.csv` | `ResolutionRow` | derived, injected | optional | `(variant_key, locus_index)` |
| `frequencies.csv` | `FrequencyRow` | derived | optional | `(variant_key, population, dataset)` |
| `gene_metrics.csv` | `GeneMetricsRow` | derived | optional | `(gene, dataset)` |
| `literature.csv` | `LiteratureRow` | derived | optional | `pmid` |
| `licensing.csv` (pref.) / `sources.csv` (deprecated) | `SourceRow` | derived, human-editable | optional | `(source, layer)` |
| `gene_validity.csv` | `GeneValidityRow` | derived | optional | `(gene, disease_id, moi, submitter)` |
| `clinical_assertions.csv` | `ClinicalAssertionRow` | derived | optional | `(variant_key, variation_id)` |
| `gwas_effects.csv` | `GwasEffectRow` | derived | optional | `association_id` |
| `verification.json` | `VerificationDoc` | derived | optional | one record per `check` |
| `provenance.json` | `ProvenanceDoc` | authored beside the spec | optional | `variant_key` per item |

The natural keys above are stated as far as this tier states them: the `_KEY_FIELDS` ClassVars, the
`REQUIRED_ANY_OF` groups, `VerificationDoc._check_unique`, and the explicit key sentences in the
model docstrings (`PharmVariantRow`'s five-part key, `GeneValidityRow`'s four-part key). The
compiler's own duplicate-row keys are not in this tier and are not asserted here.

### 8.1 Sidecar location and spelling (`layout.py`)

```
SOURCES_CSV = "sources.csv"          # deprecated spelling
LICENSING_CSV = "licensing.csv"      # preferred since 0.6
VERIFICATION_JSON = "verification.json"
SIDECAR_SPELLINGS = {SOURCES_CSV: (SOURCES_CSV, LICENSING_CSV)}   # deprecated first, preferred last
DEPRECATED_SPELLINGS = frozenset({SOURCES_CSV})
DERIVED_SUBDIR = "derived"
```

`sidecar_candidates(spec_dir, name)` enumerates each spelling at the spec root **then** under
`derived/`, root first. `resolve_sidecar` returns the single existing copy, `None` for none, and
**raises `SidecarCollision`** for more than one — deliberately not a merge and not newest-wins,
because these tables are human-overridable and two copies are two claims.
`sidecar_write_path` writes to the file it read, falling back to the preferred spelling at the root.
`deprecation_notice(path, name, shown_as=None)` returns a warning string or `None`.

The scope is machine-written sidecars only. The authored DSL has exactly one legal name in exactly
one legal place, and the asymmetry is deliberate: a second legal home for `variants.csv` would let a
module carry two copies with the ignored one invisible.

---

## 9. The manifest

`manifest.ModuleManifest` is written next to the parquets as `manifest.json`.
`read_manifest(path)` / `write_manifest(manifest, path)` — the writer uses
`model_dump_json(indent=2, exclude_none=False)` plus a trailing newline, so nulls are written out.

`MANIFEST_VERSION = "1.0"`, `SCHEMA_VERSION = "1.0"`,
`MARKETPLACE_COMPILED_BY = "marketplace-server"`.

### 9.1 Top level

| Field | Type | Category | Default |
| --- | --- | --- | --- |
| `manifest_version`, `schema_version` | `str` | defaulted | `"1.0"` |
| `identity` | `Identity` | **required** | — |
| `display` | `Display` | **required** | — |
| `genome_build` | `str` | defaulted | `"GRCh38"` |
| `curator`, `method`, `license`, `owner`, `created_at`, `published_at` | `str \| None` | optional | `None` |
| `weighting` | `Weighting \| None` | optional | `None` |
| `authors` | `list[str]` | defaulted | `[]` |
| `authorship` | `list[Contribution]` | defaulted | `[]` |
| `stats` | `Stats` | defaulted | `Stats()` |
| `compilation` | `Compilation` | defaulted | `Compilation()` |
| `frequency`, `gene_metrics`, `gene_validity`, `clinical_assertions`, `gwas_effects`, `literature`, `sources`, `verification` | block or `None` | optional | `None` — absent when the module carries no such sidecar |
| `inputs` | `list[FileEntry]` | defaulted | `[]` |
| `content_signature` | `str \| None` | optional | `None` |
| `artifact` | `Artifact` | **required** | — |
| `logs`, `derived` | `list[FileEntry]` | defaulted | `[]` |
| `provenance` | `Provenance \| None` | optional | `None` |
| `panel` | `GenePanelSpec \| None` | optional | `None` |
| `logo`, `readme` | `FileEntry \| None` | optional | `None` |
| `signature` | `Signature \| None` | optional | `None` |

`Identity`: `name` required (`^[a-z][a-z0-9_]*$`); `namespace` (slug rule), `version` (strict
`MAJOR.MINOR.PATCH`) and `canonical_id` (`namespace/name@version`) are marketplace-filled and
optional.

`Stats`: `variant_count`, `weights_rows`, `study_count`, `gene_count`, `clinvar_count`,
`pathogenic_count`, `benign_count` (all `int`, default `0`), plus `genes` and `categories` lists.
Documented as **card/detail display facets**, not a trust surface.

`Compilation`: `compile_success` (`bool`, default `False`), `compiled_by`, `compiler_version`,
`ensembl_reference`, `compiled_at`, `warnings: list[str]`, plus the resolution block —
`resolution_mode` (`"strict"`/`"best_effort"`/`None` = legacy or skipped), `fully_resolved` (`bool`),
`resolution_subjects` (`int`, the denominator `fully_resolved` quantifies over, counted **after**
rsID expansion), `expanded_keys`/`expanded_rows` (`int | None` — `None` means resolution did not run,
`0` means it ran and found no expansion), `resolution_signature`, `resolution_sources`,
`vrs_alleles`/`vrs_alleles_identified`, and `positional_rows`/`positional_rows_placed`
(`int | None`, where `None` distinguishes "compiled before 0.6" from `0` = "carries no positional
table").

The pattern throughout is **keep the parts, compute the convenience**: "complete" is
`vrs_alleles_identified == vrs_alleles` and `positional_rows_placed == positional_rows`, derived by
the reader rather than stored.

Every sidecar block carries a `signature` (the fact-hash of the corresponding CSV, kept **out of**
`artifact.digest`) plus facets a catalog can read without opening the parquet:

| Block | Distinctive fields |
| --- | --- |
| `Frequency` | `datasets`, `populations`, `row_count`, `variant_count` |
| `GeneMetrics` | `datasets`, `row_count`, `genes` |
| `GeneValidity` | `genes`, `diseases`, `classifications` (sorted, read as a set not a verdict), `submitters` |
| `ClinicalAssertions` | `clin_sigs`, `min_review_stars`/`max_review_stars` (`int \| None` — null is not zero), `unrated_count`, `not_found_count` |
| `GwasEffects` | `measures`, `units` (more than one entry means the betas must not be pooled), `traits`, `with_effect_allele`/`without_effect_allele`, `not_found_count` |
| `Literature` | no `datasets` (PubMed publishes no release id); `resolved_count`, `missing_count`, `open_access_count`, `abstract_only_count`, `quotes_authored`, `quotes_found` |
| `Sources` | `layers`, `licenses`, `attributions`, `notices`, `share_alike_layers`, `noncommercial_layers`, `nonredistributable_layers`, `unknown_terms_sources`, `declared_uses`, and the two derived tri-state verdicts `commercial_use` / `redistribution` (most-restrictive-wins; `null` means undetermined, never permitted) |
| `Verification` | `module_hash`, `producer`, `produced_at`, `closure`, `checks` |

`Sources` keeps its per-layer facets as **lists** rather than booleans on purpose: a module that used
CPIC only to resolve a coordinate and one that embeds ClinPGx annotation prose would render
identically under a single `share_alike: bool`.

---

## 10. The hash and signature family

All byte hashes are SHA-256, lowercase hex, prefixed `sha256:` (`SHA256_PREFIX`). `integrity.py`
never reads the clock — timestamps are passed in by callers.

| Name | Over what bytes | Excludes | Where recorded |
| --- | --- | --- | --- |
| `sha256_bytes(data)` / `sha256_file(path)` | raw bytes (1 MiB streaming reads) | — | `FileEntry.sha256` |
| `newline_normalized_file_entry(dir, name)` | the file's bytes with `\r\n` read as `\n`; **`size` is the length of the normalized stream, not `stat().st_size`** | line-ending differences only — a BOM, trailing whitespace and a missing final newline all still count | fed only to `verification.module_binding` |
| `artifact_digest(files)` | `json.dumps(sorted([{"name","sha256","size"} …], key=name), sort_keys=True, separators=(",",":"))` | everything not in the `FileEntry` list — logs, derived sidecars, provenance, logo, readme, authorship, content_signature, every sidecar block | `manifest.artifact.digest` |
| `content_signature(tables, genome_build)` | per file, the rows' `model_dump(mode="json", exclude_none=True)` canonicalized and **sorted**, files sorted by name; then `{"genome_build": build}` appended **only when it is not `"GRCh38"`** | `None` cells; every `exclude=True` field; the private `_genome_build`; the identity/display half of `module_spec.yaml`; row order | `manifest.content_signature` |
| `fact_signature(rows, fact_fields)` | per row, `model_dump(mode="json")` restricted to `fact_fields` with `None` dropped; canonicalized and sorted | every column outside the tuple — always `source`/`status`/`fetched_at`, plus the per-table exclusions in §7.1; row order | the nine wrappers below |
| `resolution_signature` | `RESOLUTION_FACT_FIELDS` | | `compilation.resolution_signature` |
| `frequency_signature` | `FREQUENCY_FACT_FIELDS` | | `frequency.signature` |
| `gene_metrics_signature` | `GENE_METRICS_FACT_FIELDS` | | `gene_metrics.signature` |
| `literature_signature` | `LITERATURE_FACT_FIELDS` | | `literature.signature` |
| `source_signature` | `SOURCE_FACT_FIELDS` | | `sources.signature` |
| `gene_validity_signature` | `GENE_VALIDITY_FACT_FIELDS` | | `gene_validity.signature` |
| `clinical_assertion_signature` | `CLINICAL_ASSERTION_FACT_FIELDS` | | `clinical_assertions.signature` |
| `gwas_effect_signature` | `GWAS_FACT_FIELDS` | | `gwas_effects.signature` |
| `verification.verification_signature` | `VERIFICATION_FACT_FIELDS` (`check`, `subjects`, `findings`, `skipped`, `source`, `release`) — so `detail` and `checked_at` are outside | | `VerificationDoc.signature`, `Verification.signature` |
| `verification.module_binding(entries)` | `artifact_digest` over the **authored** input entries, normally built with the newline-normalizing entry builder | the derived sidecars entirely (they carry a per-row `fetched_at`) | `VerificationDoc.module_hash` |
| `verification.pow_digest(module_hash, signature, nonce)` | raw `hashlib.sha256(f"{module_hash}\|{signature}\|{nonce}".encode()).digest()` — **not** prefixed, returns `bytes` | — | judged by `meets_difficulty`, not stored |

### 10.1 `artifact.digest` vs `content_signature`

They answer different questions and the distinction is load-bearing:

* `artifact.digest` is the version's immutable **byte** identity — *these bytes, from this compiler*.
  A recompile against a different reference moves it while the authored content is untouched. It
  **preserves** authored row order, because parquet bytes depend on it.
* `content_signature` is a **content-dedup key** over the raw authored rows: reference-independent
  (computed before resolution), name- and metadata-independent, normalized
  (`exclude_none=True` absorbs an unset new optional column, so additive schema growth does not move
  it), and **order-independent** (rows are sorted).

`content_signature` is **build-aware but not build-independent**: `genome_build` feeds the hash only
when it differs from `DEFAULT_GENOME_BUILD`, so every GRCh38 module keeps the signature it already
had while two byte-identical CSVs under different declared builds — which describe loci hundreds of
base pairs apart — stop hashing equal.

No test in this tier exercises `content_signature`; its coverage lives elsewhere.

### 10.2 Signatures

`Signature` is `algorithm` (default `"ed25519"`), `public_key` (base64 raw), `signature` (base64),
`signed_at`. It is used for two different messages:

* `manifest.signature` — over the `artifact.digest` **string's** UTF-8 bytes;
* `Closure.signature` — over the `module_hash` string's UTF-8 bytes.

`signing.sign_digest(digest, private_key_pem, signed_at=None)` signs whichever digest string it is
handed. `signing.public_key_b64_from_pem`, `signing.generate_private_key_pem` complete the key side.

`integrity.verify_signature(digest, signature, *, trusted_public_key=None)` rejects a non-ed25519
algorithm, rejects a mismatch against a pinned key, and otherwise verifies self-consistency only.
A self-embedded key proves nothing against a backend that can rewrite both digest and key — the
pinned key is the actual defence.

### 10.3 `verify_manifest`

```python
verify_manifest(module_dir, manifest, *, require_marketplace=True,
                check_inputs=False, check_logs=False, check_provenance=False,
                check_logo=False, check_readme=False, check_derived=False,
                public_key=None)
```

Always: every `artifact.files[]` must exist and hash to its declared value; the recomputed
`artifact_digest` must match. With `require_marketplace=True` (the default), `compile_success` must
be true and `compiled_by` must equal `"marketplace-server"` — which means the default **rejects
every locally-compiled module**, including one this project's own compiler produced (it leaves
`compiled_by` null). The docstring is explicit that this is a policy switch and that a consumer
installing from both registry and local needs two call sites.

The optional checks all skip a file that is absent on disk except `check_inputs`, which raises
`"input file missing on disk"`. Finally: if a signature is present it is verified (against
`public_key` when pinned); if `public_key` is pinned and no signature is present, that is an error.

Raises `IntegrityError` on the first failure.

---

## 11. Identity and versioning (`identity.py`)

* `name`: `^[a-z][a-z0-9_]*$` — underscores yes, hyphens no.
* `namespace`: `^[a-z0-9]+(-[a-z0-9]+)*$` — hyphens *separate* segments, so `just-dna-`, `-lead` and
  `a--b` are all invalid.
* `Version` is a frozen, totally-ordered dataclass of three ints; `parse_version` accepts strict
  `MAJOR.MINOR.PATCH` only (`1.0`, `v1.0.0`, `1.0.0-rc1` all raise). Ordering is numeric:
  `1.2.0 < 1.10.0`.
* `version_from_legacy("v1"|"1")` → `"1.0.0"`.
* `canonical_id(namespace, name, version)` → `"namespace/name@version"`.
* `latest(versions)` returns the highest as a string; raises on an empty list.

---

## 12. The verification attestation

`verification.json` is a `VerificationDoc`: one attestation over a list of `VerificationRecord`s.
It is a JSON document rather than a fifth fact CSV because the object has two levels, and because it
is the one derived artefact whose human-overridability must **not** silently pass.

`VerificationRecord` (`extra="forbid"`):

| Field | Type | Category | Notes |
| --- | --- | --- | --- |
| `check` | `str` | **required** | closed `VALID_VERIFICATION_CHECKS` |
| `subjects` | `int` | defaulted `0` | the denominator; `0` with no `skipped` means the check ran and had nothing in scope |
| `findings` | `int` | defaulted `0` | |
| `skipped` | `str \| None` | optional | closed `VALID_VERIFICATION_SKIPS`; null when the check ran |
| `detail` | `str \| None` | optional | the human sentence **beside** the machine key, outside the fact set |
| `source`, `release`, `checked_at` | `str \| None` | optional | |

`_check_counts` rejects a negative count. `_check_consistent` rejects a record that is both skipped
and has subjects/findings, and rejects `findings > subjects`. `VerificationDoc._check_unique` rejects
more than one record per check name — a re-run replaces rather than accumulates.

`VALID_VERIFICATION_CHECKS`, with the emitter each member's own inline comment names:

| Member | Emitter |
| --- | --- |
| `reference_allele`, `rsid_currency`, `clinical_significance`, `rsid_coordinate_agreement`, `genome_build_agreement` | the enricher's `enrich` run |
| `citation_existence`, `citation_identifier`, `provenance_quote` | `literature` |
| `allele_function` | `pgx` |
| `pgx_evidence_level` | `clinpgx check` |
| `vrs_allele_id` | `vrs mint` |
| `acmg_secondary_findings` | `check-acmg` |
| `gene_symbol_currency`, `trait_currency`, `gene_locus_agreement` | `check-identifiers` |
| `gene_disease_validity`, `dosage_sensitivity` | **RESERVED — no emitter**, deliberately |

The membership rule is one question: does this compare something the module **asserts** against what
a source says? Recording a source's verdict without comparing anything authored (the ClinVar
assertion table, `frequencies.csv`, `gene_metrics.csv`) does not qualify.

`VerificationDoc` fields: `module_hash`, `signature`, `difficulty`, `nonce` (all required),
`producer`, `produced_at`, `closure`, `records`.

`VERIFICATION_DIFFICULTY_BITS = 20` — chosen by measurement (~0.7 s at ~1.5 M hashes/s), one
proof-of-work per document per run. `find_nonce` returns the **smallest** nonce counting up from
zero, never a random search, so the file's bytes are reproducible for identical content.
`pow_digest` binds both `module_hash` and `signature`: binding to the first alone would let the
records be edited freely, and to the second alone would let a whole attestation be lifted onto
another module. The closure is deliberately **outside** the proof-of-work payload, so closing a
document re-mines nothing and every attestation written before closures existed still verifies.

`attest(records, module_hash, *, producer, produced_at, difficulty=None, closure=None)` builds the
document. `difficulty=None` and reading the constant in the body is deliberate: a default evaluated
at import would freeze the value and make the knob unreachable from a test.

`attestation_failure(doc, module_hash, *, difficulty=None) -> str | None` returns a **reason**, never
raises and never repairs, for each of five conditions in order: the binding no longer matches; the
recorded signature is not the hash of the records beside it; the recorded difficulty is below the
reader's minimum; the nonce does not meet the claimed difficulty; a *present* closure signature does
not verify. The caller's answer to all five is the same — warn and drop the block.

`verification_block(doc)` summarizes and deliberately takes no `module_hash` and performs no check,
so a caller cannot skip `attestation_failure`.

`merge_records(existing, fresh, *, existing_still_binds=True)` is newest-wins per check, with one
exception: a **`skipped` record does not replace a `ran` one** while the earlier document still binds
the current bytes. A check absent from `fresh` keeps its earlier record. With
`existing_still_binds=False` it is plain newest-wins, because a record about bytes that have moved
describes rows that no longer exist. `_ordered` sorts records by check name for reproducible file
bytes.

`Closure` (`extra="forbid"`): `closed_at` required, `closed_by` optional and explicitly untrusted,
`signature` optional. It rides `VerificationDoc` so it inherits the binding, the staleness check and
the transport, carrying no second copy of the hash — an author who edits a row after closing loses
the closure for free.

Every field description in the verification family repeats `UNTRUSTED_NOTE`:
*"Foreign values are untrusted: this records what a producer SAYS it checked, and only a consumer
holding the module's own bytes can confirm it."* The code is explicit that the binding and the
proof-of-work defeat **accidental** forgery only.

---

## 13. Tri-state and unknown-vs-false semantics

The house rule — true / false / unknown, with `None` never standing for `False` — appears in these
concrete places:

| Site | The third state |
| --- | --- |
| `SourceRow.share_alike` / `.commercial_use` / `.redistribution` | `None` = terms could not be established; never rendered as "does not forbid" |
| `Sources.commercial_use` / `.redistribution` (manifest) | `null` = undetermined, never permitted |
| `LiteratureRow.exists`, `.doi_exists` | `False` is a fact (the citation does not resolve); `None` is never-checked |
| `LiteratureRow.quotes_found` | `None` = not checked (nothing retrievable); `0` = something was read and the quote was not in it |
| `LiteratureRow.quote_source` | a *hit* is conclusive from either source; a *miss* is only conclusive against fulltext |
| `VALID_FREQUENCY_STATUS` | `not_found` (covered locus, allele absent) vs `not_covered` (source's scope excludes the locus) |
| `FrequencyRow.allele_frequency` | `None` when `AN` is 0 — "no information", not "frequency zero" |
| `vrs.in_pseudoautosomal_region`, `.par_partner`, `.contig_length`, `.sole_build_naming_contig` | `None` = cannot say; a caller must not read it as `False` |
| `vocab.vcf_field_number` | `None` for a key the reserved tables do not carry, and for a bare colliding key whose two namespaces disagree |
| `vocab.is_multi_valued_number` | `None` is **not** multi-valued: withhold, never negate |
| `alleles.event_profile` | `None` = the frame is unknown, which is not "the profile is empty" |
| `binning.DEFAULT_MEASURE_TILING["activity_score"]` | `None` = neither dense nor gap-checked |
| `AuthoredModel._KEY_INCLUDES_ALTS` | `None` = stamps nothing, distinguishable from `False` = stamps without `alts` |
| `Compilation.expanded_keys` / `.expanded_rows`, `.positional_rows` / `.positional_rows_placed` | `None` = this compiler did not say; `0` = it said zero |
| `ClinicalAssertions.min_review_stars` / `.max_review_stars` | `null` = no rated record; `0` = the rating "no assertion criteria provided" |
| `ClinicalAssertionRow.review_stars` | same distinction at row grain |
| `derive.pathogenic_from_clin_sig` / `benign_from_clin_sig` | `True` or `None` — never a fabricated `False` |
| `MeasureBinRow.unresolved` vs "no matching bin" | measurement absent vs measurement present and unbinned are different states |
| `check_vocab(None, …)` | absent = unknown, and never becomes a member |

---

## 14. Bugs and internal contradictions found in the code

Each was reproduced against the installed package.

1. **`MeasureBinRow._validate_measure_kind` discards `check_vocab`'s canonical return.**
   `check_vocab(v, VALID_MEASURE_KINDS, "measure_kind")` is called for its side effect and the
   validator then returns the raw `v`. Consequences: on the base model,
   `MeasureBinRow(measure_kind="copy-number", measure_min=1, conclusion="x")` **stores
   `"copy-number"`**, an undeclared spelling; and on every subclass, the same input is rejected with
   `CopyNumberRow requires measure_kind='copy_number', got: 'copy-number'`, because
   `_EXPECTED_KIND` is compared against the uncanonicalized value. Both outcomes contradict
   `test_vocab_separator`'s stated contract that "the value is what gets stored, hashed into a fact
   signature and compared by a consumer, so two spellings must not both survive into data" — that
   test only exercises `check_vocab` directly, never through this validator.
   Two other validators discard the same return (`Contribution._check_role`,
   `PgsRow._validate_ancestry`); those are latent only because neither vocabulary has a member
   containing `_` or `-`.

2. **`GeneMetricsRow.status` names a vocabulary that nothing enforces.** Its description reads
   `"Outcome: resolved|not_found (the ResolutionRow vocabulary)"`, but the model declares no
   validator for it — `GeneMetricsRow(gene="BRCA1", dataset="x", status="totally-made-up")`
   validates and stores the value. `ResolutionRow.status`, `FrequencyRow.status`,
   `LiteratureRow.status`, `GeneValidityRow.status`, `ClinicalAssertionRow.status` and
   `GwasEffectRow.status` all enforce theirs. The behaviour-discovering guards in `test_reference.py`
   cannot see it because `GeneMetricsRow` is outside `reference._ALL_MODELS` —
   `reference.py`'s own comment acknowledges that gap for `FrequencyRow`/`GeneMetricsRow`/
   `LiteratureRow`, but does not note that one of them has an *unenforced* claim rather than merely
   an unmarked one.

3. **`variant_key` can contain the literal string `"None"`.** `derive_variant_key` interpolates
   `chrom:start:ref` unguarded, so a legal, commonly-authored row produces a key with a `None`
   segment:
   * `VariantRow(chrom="1", start=100, genotype="A/G", state="risk", conclusion="c")` (no `ref`,
     which the identity rule explicitly permits) → `variant_key == "1:100:None"`. This exact row is
     constructed in `test_spec.test_start_position_must_be_non_negative`.
   * `StudyRow(chrom="4", pmid="8458085").variant_key == "4:None:None"`. `StudyRow.variant_key`'s
     docstring calls out that `derive_variant_key(None, None, None, None)` "would otherwise hand back
     the string `\"None:None:None\"` — a key that looks like an identity and names nothing", and
     guards only the *all*-absent case. A bare `chrom` with no `start` was the shape the pre-0.6 rule
     actively pushed authors into, so published modules may carry such rows.

4. **Allele and genotype columns are case-insensitive to validate and case-preserving to store, so
   one variant has two identities.** `ALLELE_PATTERN` carries `re.IGNORECASE`, and no validator
   upper-cases. Reproduced:
   * `VariantRow(chrom="11", start=5226762, ref="c", alts="ca", genotype="c/ca", …).variant_key ==
     "11:5226762:c:ca"` while the upper-case row keys as `"11:5226762:C:CA"` — two content
     signatures, two keys, no dedup, for one variant. (Substitutions are unaffected: `is_substitution`
     upper-cases before minting, so `c>g` and `C>G` mint the same VA — which makes the inconsistency
     *depend on the variant type*.)
   * `VariantRow(..., genotype="a/g")` stores `"a/g"` — and genotype is part of a row's identity
     (`PharmVariantRow`'s docstring puts it in the dedup key "mirroring the SNP core's (variant,
     genotype) rule"), so two spellings are two rows.
   * The sortedness check is byte-wise, so `G/a` is **accepted** and `a/G` is **rejected** — an
     ordering rule that is incoherent across cases.
   * `HaplotypeRow(haplotype_name="*4", rsid="rs1", allele="a").allele == "a"`.
   `alleles.non_nucleotide_reason` and `parsimony_reduce` both upper-case internally, so the tier is
   internally inconsistent about whether allele case is significant.

5. **`VariantRow.variant_key` / `authored_ident` are inside `content_signature` while every other
   stamped identity column is outside it.** They carry `COMPILER_MANAGED` but not `exclude=True`, so
   they survive `model_dump()`; `HeteroplasmyRow`, `HaplotypeRow` and `PharmVariantRow` declare the
   same two columns through `stamped_identity_field`, which sets `exclude=True`. `base.py` names this
   as a grandfathered inconsistency carried until a major, so it is a known defect rather than an
   unknown one — but it does mean the "content" identity of the most common table includes two
   derived columns.

6. **A comment in `spec.ModuleSpecConfig` contradicts the function it calls.** It says "Only the top
   level is scanned here; the nested blocks (`module:`, `defaults:`) are models of their own and are
   checked when they validate", while `vocab._placeholder_paths` recurses into nested dicts and lists
   precisely *because* (per its own docstring) those inner blocks "are plain `BaseModel`s, not
   `AuthoredModel`s — so they carry no guard of their own". The recursive behaviour is the correct
   one; the comment describes the bug it was written to fix. A real residual hole follows from the
   same fact: passing an already-constructed `ModuleInfo` instance rather than a dict bypasses the
   scan entirely, since neither `ModuleInfo` nor `Defaults` nor `Contribution` carries a placeholder
   guard.

7. **`ACTIONABILITY_SEED`'s defining comment states the opposite of the code.** In `vocab.py` it
   reads "The reserved `actionability` axis's recommended seed vocabulary (documentation — the field
   is not built yet, so this is not enforced)". The field *is* built (`VariantRow.actionability`) and
   *is* enforced (`_validate_actionability` calls `check_vocab`), and `test_v04` asserts a
   non-member is rejected. `spec.py`'s own field comment records the closedness drift on the
   marker side; the constant's comment was never corrected, and it is the one a reader of `vocab.py`
   meets first.

8. **`integrity.verify_signature`'s error message hardcodes "artifact digest"** —
   `f"artifact digest signature is invalid: {exc}"` — but the same function is called by
   `verification.attestation_failure` to verify a **closure** signature over `module_hash`.
   `Signature`'s own docstring was updated to say the signed message is "whichever digest string the
   caller hands `signing.sign_digest`"; the verifier's message was not. Cosmetic, but it is the
   string a consumer sees when a closure signature fails.

9. **`layout.sidecar_candidates` is asymmetric in its key.** `SIDECAR_SPELLINGS` is keyed on the
   deprecated name, so `resolve_sidecar(dir, "sources.csv")` searches both spellings while
   `resolve_sidecar(dir, "licensing.csv")` searches only `licensing.csv` and would miss a module
   carrying the deprecated file. Nothing in this tier enforces that callers pass the canonical key,
   and `preferred_spelling` returns the name that does *not* work as a lookup key — which is the
   natural one for a caller to reach for.

10. **`GwasEffectRow._check_finite` hardcodes the wrong field name.** It validates both `effect_size`
    and `standard_error` but calls `validate_finite(v, "effect_size")`, so
    `GwasEffectRow(..., standard_error=float("inf"))` — which passes the `ge=0` bound — raises
    `"effect_size must be a finite number, got: inf"`. Every sibling model that shares a finite check
    across fields threads `info.field_name` (`GeneMetricsRow._check_finite`) or declares one
    validator per field.

11. **`start` carries `ge=0` on two of the five models that declare it.** `VariantRow.start` and
    `StudyRow.start` are bounded; `HaplotypeRow.start`, `PharmVariantRow.start` and
    `HeteroplasmyRow.start` are not, so `HaplotypeRow(haplotype_name="*4", chrom="1", start=-5,
    allele="A")` validates. All five describe the same 1-based VCF convention, and
    `test_spec.test_start_position_must_be_non_negative` states the reason for the bound — "start is
    materialized as an unsigned parquet column; a negative position is a clean validation error
    rather than a downstream polars overflow" — which applies to the unbounded three equally.

Not a bug, but worth an integrator's attention: `VariantRow._freeze_identity` calls
`derive_variant_key` with no `build` argument, so a `VariantRow` constructed outside the compiler on
a GRCh37 module mints a GRCh38 `ga4gh:VA.…`. The design intends the compiler to restamp
(`base.with_genome_build` says so explicitly and names `VariantRow` as the deliberate exception), but
the model alone will silently produce a wrong-build identity.

---

## 15. Undetermined from code

* **The CSV filename for `AlleleFunctionRow`.** No string in `schema/src` names it; the other ten
  authored tables are named in docstrings or diagnostics. This tier owns filenames only for the
  machine-written sidecars (`layout.py`), so the authored filenames are conventions asserted
  elsewhere.
* **Whether `content_signature`'s `tables` mapping is expected to be keyed by bare filename or by a
  relative path.** The docstring says "each data-CSV filename", and files are sorted by that string,
  but nothing constrains it, and `layout.sidecar_relative_names` produces `derived/…` paths for the
  sidecars.
* **The exact per-table duplicate-row keys the compiler enforces.** This tier states key *components*
  (`_KEY_FIELDS`, `REQUIRED_ANY_OF`, the prose keys on `PharmVariantRow` and `GeneValidityRow`) but
  never assembles a dedup key; §8's natural keys are read off those statements.
* **What `Stats.weights_rows` counts relative to `Compilation.resolution_subjects`.** The comment
  says the two are equal across the reference examples today and that the equality is "a property of
  the current transform, not a contract", but neither is computed here.
* **`ProvenanceItem.confidence`'s scale.** Described as "Author/model confidence 0..1" with no
  bound declared and no validator.
* **`ResolutionRow.source` / `authority` membership.** Both are documented as open with example
  values (`cache`, `ensembl-graphql`, `ensembl-rest`, `manual`, `reversed`; `ensembl`, `clinvar`,
  `gnomad`, `authored`); the link→authority map lives in the enricher and is not visible here.
* **Whether `ModuleSpecConfig.genome_build` is meant to be constrained at all.** It is a free `str`
  with a default; `PRIMARY_CONTIG_LENGTHS` knows two builds and `REFGET_GRCh38` one, but nothing
  validates the field against either.
* **`SourceRow.draft_digest`'s algorithm.** Described as "a hash of the drafted table projected onto
  the column a cross-check later compares against this source", computed by a drafting provider
  outside this tier.
