# `just-dna-format` — the schema tier

The package reference for **`just-dna-format`**: the pydantic contract for the authored spec DSL
(`module_spec.yaml` + CSVs) and the compiled `manifest.json`, plus the integrity/identity helpers.
It is the lightest tier — `pydantic` + `cryptography` only (the latter solely for Ed25519 sign/verify)
— so any verify-only consumer can depend on it without pulling polars/duckdb/network. It **never
fetches** (CONSTITUTION Principle 2) and holds no transform logic; compilation lives in
[`just-dna-compiler`](COMPILER.md), fetching in [`just-dna-enricher`](ENRICHER.md).

> Companion docs: **[COMPILER.md](COMPILER.md)** (the transform), **[ENRICHER.md](ENRICHER.md)** (the
> network tier), **[CONSTITUTION.md](CONSTITUTION.md)** (the invariants every model upholds).
> `__init__.py` carries no re-exports by design — import from the submodule where a symbol lives.

## Module map (dependency tiers, leaf → aggregate)

| Module | Purpose | Imports (intra-package) |
|---|---|---|
| `vocab` | Constrained vocabularies, id grammars, reusable validators | — (stdlib leaf) |
| `identity` | `namespace/name` rules, SemVer `Version`, `canonical_id` | — (stdlib leaf) |
| `derive` | Legacy→0.3 column derivations + read-time aliases | — (stdlib leaf) |
| `normalize` | Inject-only authority-key stripper, `normalize_version` | — (stdlib leaf) |
| `vrs` | GA4GH VRS allele ids: `derive_vrs_allele_id`, the GRCh38 refget table, the `vrs_id` cell codec and the PAR geometry (stdlib only) | — (stdlib leaf) |
| `alleles` | Reference-free allele algebra: `parsimony_reduce`, `event_profile` — what two spellings of one indel have in common (0.5, RM31) | — (stdlib leaf) |
| `base` | `AuthoredModel` + `derive_variant_key` | `vocab`, `vrs` |
| `manifest` | The `manifest.json` contract | `identity`, `vocab` |
| `resolution` | `ResolutionRow` (the 0.5 resolution table) | `vocab`, `vrs` |
| `frequency` | `FrequencyRow` (the 0.5 allele-frequency table) | `vocab`, `vrs` |
| `gene_metrics` | `GeneMetricsRow` (the 0.5 gene-constraint table) | `vocab` |
| `literature` | `LiteratureRow` (the 0.5 citation table) | `spec`, `vocab` |
| `sources` | `SourceRow` (the 0.5 data-source licensing table) | `vocab` |
| `spec` | Authored DSL — `ModuleSpecConfig`, `VariantRow`, `StudyRow` | `base`, `derive`, `identity`, `manifest`, `vocab` |
| `binning` | Measure→phenotype binning rows (4 table kinds) | `base`, `vocab` |
| `pgx` | PGx star-allele rows (4 table kinds) | `base`, `vocab` |
| `pgs` | `PgsRow` (PGS-Catalog-ID manifest) | `base`, `vocab` |
| `integrity` | SHA-256 hashing, the signatures, Ed25519 verify | `manifest`, `resolution`, `frequency`, `gene_metrics`, `literature`, `sources`, `cryptography` |
| `signing` | Ed25519 private-key signing (over `artifact.digest`) | `integrity`, `manifest`, `cryptography` |
| `reference` | Drift-proof authoring reference generated from live models | spec/binning/pgx/pgs/manifest/normalize/vocab |
| `aggregate` | Cross-version log/provenance union | `manifest` |

## The authored surface — one CSV = one concern

A module is a directory. `module_spec.yaml` carries identity/display/defaults; each data CSV is one
concern, and a module includes **only** the CSVs it uses (RM2 — `variants.csv` is not mandatory). The
SNP core is `variants.csv` + `studies.csv` (studies required *iff* variants present). Everything else
is an optional table kind.

**Where grounding evidence goes, and the line between the two citation sites (S19/RM47).**
`studies.csv` identifies its subject the way a variant is identified — by `rsid`, or by
`chrom`(+`start`) — so it grounds `variants.csv` row by row, and it grounds any table whose rows carry
a variant identity: `pharm_variants.csv`, `haplotypes.csv`, and `heteroplasmy.csv` when its optional
`rsid`/`chrom`/`start` columns are filled (`reference_examples/mt_heteroplasmy` is the worked case). It
is **accepted in a module carrying no `variants.csv`** — it loads, validates and compiles to
`studies.parquet` — so a binning or PGx module can cite its literature.

What it could not do before 0.6 was name a *gene-keyed* row: a `repeat_alleles.csv` bin is keyed
`(gene, repeat_unit)` and no study row could point at one, so a citation there grounded the module and
never the boundary — which is the number a reader actually wants to check. **RM47 closed that with a
second citation site and one rule for reading it: the bin row cites, the citation table describes.**

- **`MeasureBinRow.pmid` is a pointer on the row that states the threshold** — one optional column on
  the binning base, so it reaches all four kinds. Free-form like `StudyRow.pmid` and validated by the
  same grammar.
- **The citation table's subject requirement is relaxed**: a `studies.csv` row may now exist without
  naming a variant, so the paper behind a threshold can be described honestly instead of an author
  writing a bare `chrom=4` for HTT — an assertion about a locus the paper is not about. Widening an
  either-or rule only makes previously-*invalid* rows valid, so no published module breaks.
- **The bin carries the pointer and nothing else.** Population, `p_value_num`, `effect_size` and
  `provenance_quote` stay on `StudyRow`. Copying them onto the bin one column at a time would restate
  the bin inside its own evidence, which is what ruled out the alternative designs (a `bin_evidence.csv`
  join table has to key on the thresholds, and they are floats — re-authoring `40` as `40.0` orphans
  the evidence with nothing able to notice).

The compiler still reports a threshold with no evidence at all — a binning table with no bin `pmid`
in a module with no study rows warns in both modes — and both the enricher's literature pass and the
compiler's literature cross-check read the new site, so a bin-grounded citation is checked for
existence and identifiers exactly like a study-grounded one. `sources.csv` does not substitute for
either: it records a *dataset's* terms and attribution, which answers where a table came from, never
why a bound is where it is. `resolution.csv` is compiler *input*, produced by the enricher, not authored
annotation (see [§ resolution table](#the-resolution-table-05-provisional)) — and the same is true of
the six derived-fact sidecars `frequencies.csv` / `gene_metrics.csv` / `literature.csv` /
`gene_validity.csv` / `clinical_assertions.csv` / `sources.csv`, which are therefore absent from the
table below.

**`sources.csv` is the one of those six a human is expected to write, and 0.5.4 stopped pretending
otherwise (S21).** The others are produced by an enricher pass, so an author never starts one by
hand; this one the schema tells them to write — a source read **by hand** leaves no `source` cell
anywhere for the compiler's coverage check to find, so declaring it as a row here is the only route
(`vocab.MISPLACED_COLUMN_REASONS['source']` says exactly that), and the compile licence gate reads this
file and nothing else. It is therefore in `just_dna_compiler.draft.DRAFTABLE` with `(source, layer)` as
its key, and its two vocabulary fields carry their markers so `authoring_reference()` describes it. It
stays out of the table below because its rows are *facts about a dataset*, not annotation — the same
reason its `source` column is inside its fact set while everywhere else `source` is provenance.

| File | Model (module) | Role |
|---|---|---|
| `module_spec.yaml` | `spec.ModuleSpecConfig` (`ModuleInfo`, `Defaults`) | identity / display / defaults / `panel` (deprecated, RM4) / `authorship` |
| `variants.csv` | `spec.VariantRow` | SNP-core annotations (the weights table) |
| `studies.csv` | `spec.StudyRow` | grounding evidence (PMID/DOI + provenance) |
| `resolution.csv` | `resolution.ResolutionRow` | injected rsid↔coord facts (0.5; enricher-produced) |
| `activity_phenotype.csv` | `binning.ActivityPhenotypeRow` | PGx metabolizer activity-score bins |
| `copynumbers.csv` | `binning.CopyNumberRow` | copy-number → phenotype (SMN1/SMA) |
| `repeat_alleles.csv` | `binning.RepeatAlleleRow` | repeat-count bins (VNTR/STR, HTT CAG) |
| `heteroplasmy.csv` | `binning.HeteroplasmyRow` | mtDNA allele-fraction bins |
| `haplotypes.csv` | `pgx.HaplotypeRow` | variant↔star-allele junction |
| `allele_function.csv` | `pgx.AlleleFunctionRow` | star-allele function status |
| `diplotypes.csv` | `pgx.DiplotypeRow` | canonicalized diplotype pair → phenotype |
| `pharm_variants.csv` | `pgx.PharmVariantRow` | single-variant drug response (PharmGKB) |
| `pgs.csv` | `pgs.PgsRow` | PGS-Catalog-ID manifest + ancestry-validity fields |

## Conventions (the idioms every model obeys)

- **`AuthoredModel` (`base.py`).** Every authored *annotation* row inherits it — never `BaseModel`
  directly. It carries `model_config = ConfigDict(extra="forbid")`, the `reject_reserved` before-validator
  (a reserved-namespace name fails with a *specific* diagnosis; any other unknown column gets the generic
  `extra="forbid"` rejection), and the shared field validators (`rsid`, `trait_efo_id`, `direction`,
  `clin_sig`, `stat_significance`, `evidence_level`, finite-`effect_size`) declared `check_fields=False`
  so each runs only for a field the subclass actually declares — per-field rules cannot drift model to
  model. (`ResolutionRow` is the deliberate exception — it is a fact, not an annotation; see below.)
- **Vocabulary idiom (Principle 6).** A constrained vocabulary is a `frozenset[str]` + a validator,
  never `Enum`/`Literal` — additive and inspectable. Live sets in `vocab.py`: `VALID_DIRECTIONS`,
  `VALID_SIGNIFICANCE`, `VALID_CLIN_SIG`, `VALID_EVIDENCE_LEVELS`, `VALID_RESOLUTION_STATUS`,
  `VALID_FREQUENCY_STATUS`, `VALID_RSID_STATUS`, `VALID_AUTHOR_ROLES`, `VALID_DOSAGE_SENSITIVITY`,
  `VALID_PHENOTYPE_CATEGORIES`, `VALID_QUOTE_SOURCE`, `VALID_RECOMMENDATION_STRENGTH`,
  `VALID_SOURCE_LAYERS`, `VALID_DECLARED_USE`; plus the open seeds `RECOMMENDED_AUTHOR_KINDS`,
  `ACTIONABILITY_SEED`. (The rest live with the models that own them — `pgs.VALID_TRAINING_ANCESTRY`,
  `pgx.VALID_FUNCTION_STATUS` — which is why `authoring_reference()` reads the fields' own markers
  rather than this module.)
- **`derive_variant_key(rsid, chrom, start, ref, alts=None)` (`base.py`).** The single source of a
  variant's natural identity: the rsid when present, else `chrom:start:ref`, or `chrom:start:ref:alts`
  (alts normalized/sorted) when an alt is given — so distinct alleles at one locus don't collide. Never
  hand-build the coord key. Position-level *matching* (studies, verify) calls it without `alts`.
- **Frozen `variant_key`.** On `VariantRow` it is a **stored, compiler-managed** column, stamped once
  at load by `_freeze_identity` (authored values ignored) and never re-derived — so resolution can
  fill a coord/rsid or expand a row without ever re-keying it (Principle 7). Since 0.6 the three
  **positional** tables stamp it the same way (see below); it remains a derived read-only *property*
  on `StudyRow`, which is never resolved or expanded. It is excluded from the authoring reference.
  Note the asymmetry that makes a name-based exclusion wrong: `FrequencyRow` declares a `variant_key`
  that is genuinely **authored and required**, so what is compiler-managed is the *field*, not the name.
- **Frozen `authored_ident`.** Stamped by the same validator: which of `{rsid, chrom, start, ref, alts}`
  the author actually supplied. Also compiler-managed and materialized to `weights.parquet`, and it is
  what makes resolution *reversible* — `variant_key` answers "which variant is this", not "what did the
  author write", so it cannot tell an rsid-only row from an rsid+coordinate pair, nor an expanded locus
  from an authored coordinate. Without it reverse materialized resolved coordinates back into
  `variants.csv` and `content_signature` moved on every round-trip of an rsid-authored module. See
  [COMPILER.md § Resolution](COMPILER.md).
- **Stamped identity on the positional tables (RM43, 0.6).** `PharmVariantRow`, `HaplotypeRow` and
  `HeteroplasmyRow` — the three tables that declare both `chrom` and `start` — each stamp
  `variant_key` **and** `authored_ident`, because the compiler now fills a resolved coordinate into
  them and reverse has to re-emit the authored shape rather than the filled one. `PharmVariantRow` and
  `HaplotypeRow` also gain a stamped **`alts`**, filled as *data, not identity*: the key is still
  derived without it (a pharm annotation matches a variant at `chrom:start:ref` regardless of allele),
  and what the column buys is a direct VCF join. `AuthoredModel._KEY_INCLUDES_ALTS` is the tri-state
  that opts a model in and says whether its key carries `alts` — `None` for every model that stamps
  nothing, `True` only for `HeteroplasmyRow`, whose key always did.

  A **compiler-filled** identity column is refused rather than ignored (`base.reject_compiler_filled`,
  the same `mode="before"`-diagnosis shape as `reject_misplaced`): writing `alts` on a
  `pharm_variants.csv` row by analogy with `variants.csv` failed loudly before the column existed, and
  a new column may not turn a loud failure into a quiet one — accepted silently, the value entered
  `authored_ident` and then vanished on reverse, so the round trip stopped being a fixed point. The
  guard is scoped to `IDENTITY_FIELDS`, which is what leaves `variant_key`/`authored_ident` accepted
  and overwritten: those are *stamped*, so ignoring an authored value loses nothing, and `VariantRow`
  has tolerated exactly that since 0.5 on the no-foot-gun rule.

  Two mechanics to keep straight. The key is derived from the **authored subset**, so the fill can run
  any number of times without re-keying a row; and `with_genome_build` re-derives it when the loader
  injects the build, which is this tier's answer to the problem `_restamp_for_build` solves for
  `VariantRow` one tier up (`VariantRow` keeps its own restamp, and stays out of the hook). These six
  fields are declared `exclude=True`, so they are absent from `model_dump()` and therefore from
  `content_signature` — a stamped value is a pure function of the authored cells, so it says nothing a
  *content* identity does not already have, and including it would have moved the signature of every
  already-published module carrying one of these tables. `VariantRow`'s two *are* in
  `content_signature`; that is grandfathered, not a precedent, since changing it in either direction
  moves published signatures. `_build_table` reads fields off the row rather than through
  `model_dump()`, which is how the columns still reach parquet.
- **Both carry the `COMPILER_MANAGED` marker (`base.py`), and every generator over the authored
  surface reads `base.authored_field_names(model)` rather than `model_fields`.** A generator that
  walks `model_fields` directly offers these two as columns an author writes, which is wrong twice
  over: the compiler overwrites whatever is in them, and `authored_ident` is a `list[str]`, so a
  rendered cell (`rsid`) does not reload as one. The marker exists because the two hand-kept
  exclusion lists that preceded it both drifted — one named only `variant_key` and never learned
  about `authored_ident`; the other did not exist at all, so `draft.append_rows` wrote a
  `variants.csv` the compiler then refused to load.
- **Vocabulary binding (`base.vocabulary` / `field_vocabularies`, 0.5).** A field drawn from a
  constrained vocabulary carries its **members** on its own `json_schema_extra`, the same way
  `COMPILER_MANAGED` rides on the field. The marker holds the options rather than a name to look up,
  because the vocabularies live in the leaves that own them (`vocab`, `spec`, `binning`, `pgx`,
  `pgs`, `manifest`) and a central registry would either need `vocab` to import `pgx` — the cycle
  `base`'s dependency note exists to avoid — or be a second hand-kept list, which is the thing being
  fixed. `authoring_reference()["vocabularies"]` is generated from these markers — 21 entries today,
  against the hand-kept dict it replaced, which had already drifted twice.
  `closed=False` marks a *recommended* set, and that flag is load-bearing: `actionability` was
  published as an open seed while `VariantRow` rejected non-members, so a tool offering a novel value
  got a rejection it had been told to expect. Keyed by **vocabulary name**, not field name, which is
  what keeps `PgsRow.training_ancestry` (1000G superpopulations) from merging with gnomAD's
  population list — two ancestry vocabularies `vocab.py` explicitly forbids folding together.

  **The guard that keeps this honest discovers enforcement by behaviour, and it was still defeated by a
  hand-kept list (S21, 0.5.4).** `test_every_enforced_vocabulary_field_declares_its_options` feeds each
  field an invented value and requires a marker wherever the model refuses one — no list of which fields
  are constrained. But it iterates `reference._ALL_MODELS`, and `SourceRow` was not in it, so
  `SourceRow.layer` and `.declared_use` ran closed validators with no marker and `authoring_reference()`
  described `sources.csv` not at all. One omission hid the other, and the cost landed on the one fact
  sidecar a human writes: an author reconstructing that table from its filename has to guess that
  `share_alike`/`commercial_use`/`redistribution` are three orthogonal tri-states, which is not a
  guessable shape. Both markers are on the fields now and the model is in the registry — demonstrated by
  stripping the markers and watching the guard name both fields, not asserted. **Add a new model to
  `_ALL_MODELS` in the same commit that declares it.**
- **`REQUIRED_ANY_OF` (`AuthoredModel`, 0.5).** Alternative identity groups, any one of which
  satisfies the row: `VariantRow` is `({rsid}, {chrom, start})`. Pydantic's `is_required()` is
  field-local and cannot say this — the rule is a `model_validator` — so a tool listing required
  columns used to report that a `variants.csv` row needs no identifier at all. A `ClassVar` rather
  than a per-field marker because `{chrom, start}` is one group meaning "both together", which no
  annotation on `chrom` alone expresses; a test derives cases from the declaration and checks them
  against the validator, so the two cannot drift.
- **`vocab.TEMPLATE_PLACEHOLDER` (`<<REPLACE>>`, 0.5).** The cell a generated template writes where a
  human must decide. Refused by a recursive `mode="before"` guard on every authored row and on
  `module_spec.yaml`, so an unreplaced stub is diagnosed by column and row instead of surfacing as a
  type error, and can never reach a compiled module. A *value* sentinel rather than a marker column,
  so replacement happens one row at a time; and deliberately not `MeasureBinRow.unresolved`, which
  means "no measurement at read time" and is designed to compile — two opposite lifecycles on one
  field would be the overloaded-axis anti-pattern (P5).
- **Reserved namespace (`vocab.RESERVED_NAMES_0_4`).** Only names expected to become real module
  columns later (P5) — today `{reference_db, callable_element, quality_element}`, each with a reason
  in `RESERVED_NAME_REASONS`. It is *not* a catalogue of barred names (`extra="forbid"` already
  rejects any unknown column). (`callable_from` was reserved for RM6 and is now **built**, so it left
  the set: a reserved name is refused at author time, which would make the built column unwritable.)

## The allele grammar — bases, and the five structural types (RM5, 0.6)

An allele is a nucleotide string, or a **symbolic/structural allele carrying its length**:
`<DEL:1500>`, `<CNV:TR:30>`, `<DUP:TANDEM:120>`. The first level is VCF 4.4's **closed five** —
`DEL`, `INS`, `DUP`, `INV`, `CNV` (`alleles.SYMBOLIC_ALLELE_TYPES`); subtypes are colon-separated and
**open**, because the standard leaves them to the implementation
(`alleles.RECOMMENDED_SYMBOLIC_SUBTYPES` seeds the four it recommends).

**Spelling the bases out stays the default**, and that is the standard's own instruction: *"when the
exact sequence is known, the variant can be represented as a non-symbolic ALT allele"*. So 5-HTTLPR —
a ~43 bp indel whose sequence is known — is authored as a plain indel, not as a named `<S>`/`<L>`
pair. Symbolic notation is for imprecision.

**The length rides inside the token, not in a column beside it.** VCF carries it as `INFO/SVLEN`,
which this DSL has no equivalent of, so the choice was a new authored column or the allele string.
The column loses three ways: SVLEN is `Number=A` — *one value per ALT* — so a scalar column cannot
describe `alts=<DEL:5>,<DUP:9>` and a parallel-array column is the desync shape `ResolutionRow.vrs_id`
needed two guards for; `genotype` names two alleles at once and `HaplotypeRow.allele` /
`VariantRow.effect_allele` are single cells on rows about something else, so three of the columns that
hold an allele have no row-level home for it at all; and an authored column is **full cost** under the
0.6 charter amendment, on every table that can carry an allele, forever.

**Where the grammar bites — three sites.** `vocab.validate_allele` (two users:
`HaplotypeRow.allele` and `VariantRow.effect_allele`) and the shared diploid grammar
`AuthoredModel._validate_genotype` (`VariantRow`, required; `PharmVariantRow`, optional), whose
per-allele decision is the one helper `base.genotype_allele_ok`. `ref`/`alt`/`alts` still have **no**
grammar — eleven columns across six models — and adding one stays refused: it would reject `N`, which
is real, and break P3 for a module that already carries an odd cell.

**What is deliberately not here.** No `##ALT=<ID=…,Description="…">` declaration mechanism and no
arbitrary named IDs: it is what VCF offers and it is unasked extendability in the one layer a human
reads, so it stays gated behind a real consumer report. No readable alias carrying its own sequence
either — it would create two spellings of one allele that the comparison and identity paths would both
have to resolve. CPIC's IUPAC codes (`R`) and its `DELTCT`/`AAAGGGGCG(2)` notations stay unexpressible;
they are not VCF symbolic alleles. And `<*>` is **not** one of the five — it makes an *observability*
claim rather than naming a variant, which is a different axis.

**That different axis is `*`, and it is a `genotype` member since 0.6 (RM59).** VCF's *"allele missing
due to overlapping deletion"* is not a symbolic allele and shares none of the machinery above: it has
no first-level type, no length, and `is_symbolic_allele('*')` is `False`, so RM5's checks say nothing
about it — correctly, because there is no variant there to be unspelled. It is the one member of the
genotype grammar that describes the *sample's call* rather than the variant, which is why it is
admitted in `genotype` alone: `vocab.validate_allele` still refuses it for `HaplotypeRow.allele` and
`VariantRow.effect_allele`, since those name the allele a **rule** is about and a rule about an allele
nobody observed states nothing. `alleles.non_nucleotide_reason` reports it as `"unobservable"`, kept
apart from `"notation"` on purpose — a grammar gap is a release away, and this one is permanent. What
a consumer must do with it is in *The consumer join contract* below.

**`*` and `.` are the two markers that name no allele, and they must not be conflated** — the pair
landed one item apart in 0.6 and reads like one thing. `.` (RM58, `"missing"`) asserts that **no
alternate allele exists**, a claim about the *variant*, and it is an identity defect: `derive_variant_key`
folds the cell in, so `alts=.` and an empty cell describe one monomorphic site under two keys. `*`
(RM59, `"unobservable"`) asserts that an allele **could not be observed**, a claim about the *sample's
call*, and it is not a defect at all — the cell is right and nothing wants editing. So only `*` is a
legal `genotype` member, only `.` has an authored repair, and merging the two would either accuse a
correct row or silence a real collision.

**Two consequences that follow rather than being chosen.** A symbolic allele mints no
content-addressed identity — a VRS allele id is a digest of a sequence, and there is none — so it
falls through to the coordinate key exactly as an indel does. And comparing it against a spelled
allele is **undecided**, never "no match": it has no flank for `alleles.parsimony_reduce`, so
`hosting_verdict` returns `None` (see [COMPILER.md](COMPILER.md)).

**A lengthless `<DEL>` loads and the compiler refuses it**, which is forced rather than chosen: a
model-level rejection is a load error, fatal in *both* modes, while the decided behaviour is
warn-and-drop under `best_effort`. The schema says what the DSL can spell; the compiler says what
makes a usable rulebook. `alleles.symbolic_allele_defect` is the shared classifier, and
`AuthoredModel.ALLELE_COLUMNS` — declared on each model beside `REQUIRED_ANY_OF` — is what tells the
compiler which columns to read.

`alleles.is_symbolic_allele` tests for the **opening** bracket alone, deliberately: requiring the
closing one let `<DEL` — the likeliest typo of the lot — read as an ordinary allele string, so it
slipped past the guard in `hosting_verdict` and reached character arithmetic over a token that spells
no sequence. Nothing legal in an allele column begins with `<`, so the looser test costs nothing and
buys a diagnosis where there would otherwise be a generic rejection.

## Row models — key fields

Only the load-bearing fields are listed; read the model for the full set and validators. `?` = optional.

**`VariantRow` → `variants.csv`.** Required `genotype`, `state`, `conclusion`. Identity: `rsid?`,
`chrom?`, `start? (ge=0)`, `ref?`, `alts?` (needs rsid **or** chrom+start), plus the frozen `variant_key`.
Annotation: `weight?`, `negatives?`, `priority?`, `gene?`, `phenotype?`, `category?`,
`clinvar?/pathogenic?/benign?` (tri-state bool). 0.3 axes: `direction?`, `stat_significance?`,
`effect_size?`, `effect_measure?`, `effect_allele?`, `flags?` (open list; reserved
`conditional|phased|pleiotropic`), `trait_efo_id?`, `clin_sig?`. 0.4 axes: `requires_callable?`,
`acmg_sf?`, `actionability?` (`ACTIONABILITY_SEED`). 0.5: `callable_from?` — the VCF field(s) a consumer
establishes callability from (`FORMAT/DP`, `FORMAT/GQ`, `FORMAT/FT`, or `FORMAT/DP|FORMAT/GQ`), the
RM6 pointer half of `requires_callable`; same pointer grammar as `source_field`, validated on
`AuthoredModel` since the two share it. 0.5 (RM29a): `quality_from?` + `min_quality?` — the call-confidence cofactor, a
pointer at the VCF confidence field plus an **inclusive** floor below which the row's conclusion is
withheld. **Both-or-neither** (a model validator): a bound with no field does not say what must clear
it, and a field with no bound is no threshold at all, so either half alone reads as a gate that is not
one. `quality_from` shares the same pointer validator as the two above — three columns, one grammar.
Orthogonal to `requires_callable`/`callable_from`, which ask whether the position was *seen*; this
asks whether what was seen is good enough to act on. A consumer that cannot read the field
**withholds** — an unevaluable floor is unknown, never satisfied. Genotype grammar: phased `A|G` (order kept),
unphased `A/G` (must be sorted), or a single allele (hemizygous/homoplasmic). Read-time upgrade aliases:
`effective_direction`/`effective_stat_significance`/`effective_clin_sig`/`effective_pathogenic`/
`effective_benign`, `needs_upgrade`, and a materializing `upgraded()`.

**`StudyRow` → `studies.csv`.** Required `pmid` (must contain a PubMed token — kept verbatim). Optional
`rsid`/`chrom`/`start`/`ref` — **all of them, since 0.6**: a citation row may name no variant at all
and ground the module or a binning bound instead (RM47), in which case `variant_key` is `None` and the
compiler's orphan check skips it. `population`, `p_value`, `conclusion`,
`study_design`, `stat_significance`, `effect_size`, `effect_measure`, `trait_efo_id`, and the RM11/RM12
provenance columns `doi?` (DOI grammar), `provenance_quote?`, `provenance_regex?` (must `re.compile` at
author time — a declarative pattern grammar, Principle 1). 0.5 adds the **queryable p-value**:
`p_value_num?`, the same number typed, constrained to (0, 1] — an exact `0` is a source's own
underflow rather than a probability, so it is rejected instead of stored as a confident zero.

- **`neg_log10_p` is derived, not authored.** It is materialized into `studies.parquet` (the scale a
  consumer filters and plots on — `7.3` is genome-wide significance) and absent from the CSV, the same
  "store the number, materialize the convenience" split as `allele_frequency` = AC/AN. Authoring it
  would make the human compute a logarithm to write a row down.
- **A mantissa/exponent pair was drafted and dropped.** It is the GWAS Catalog's own representation and
  it survives p-values past float64's range (subnormal below ~1e-308, exactly `0.0` below ~5e-324) —
  but that is a catalogue-of-millions problem, not a curated-module one, and two columns plus a
  both-or-neither rule is a cost every author pays for it. A value that small now reads as
  *indefinite*, not as zero.
- The verbatim `p_value` string stays (retyping or removing it is a 1.0 item), and the compiler
  cross-checks the two at 1% relative tolerance, skipping any cell that is not one definite value.

**`variant_key` is derived against the module's declared build (0.5).** `derive_variant_key`'s
`build` argument always existed and was never passed: `VariantRow._freeze_identity` stamps at row
construction, where no module is in scope, so a `genome_build: GRCh37` module minted GRCh38 VRS ids
for GRCh37 coordinates — HFE C282Y at 6:26093141 (GRCh37) got the identical `ga4gh:VA.…` as a GRCh38
module claiming that coordinate, a locus 228 bp away. `just_dna_compiler` now re-stamps after load
(`_restamp_for_build`), falling back to the coordinate key and **warning that the key is
build-relative**. A no-op on GRCh38.

**`effect_allele` names which allele the effect is about, and nothing reconciles orientation.** `ref`
and `alts` plus the sign of `weight` cannot recover it — that is why the column exists — so a row whose
effect is not obvious from its genotype should carry it. Since 0.5 the compiler checks that the value is
one of the alleles the locus actually has (membership in `{ref} ∪ alts`, error under `strict`), which
catches a strand-flipped spelling; it does **not** complement an allele and rewrite it, and that blind
spot is permanent by charter — see [COMPILER.md](COMPILER.md)'s *what the compiler cannot validate*.
The sharper case is a coordinate an author carried across builds by hand: where the reference base
itself differs between assemblies, an ALT-only representation silently mis-orients, and the module then
says the wrong allele carries the effect with no error anywhere in this tier. Only a check holding the
real sequence can see it — `sequences.verify_reference_alleles` in the enricher, or, when two rows
share a key and disagree, the compiler's *inconsistent reference allele* error. So orient by an
explicit anchor, never by position alone; [RM48](RM_TOC.md) tracks the missing authoring path for an
hg19 coordinate, whose remedy is rsID recovery rather than a liftover.

**Binning rows** (`binning.py`, all subclass `MeasureBinRow`). Shared: `measure_kind` (must match the
row type), inclusive `[measure_min, measure_max]` (finite; `unresolved=True` carries no bounds — the
mandatory no-call sentinel), `conclusion`, plus `direction?`/`clin_sig?`/`phenotype?`/`trait_efo_id?`
and the `source_field?` VCF pointer plus its `source_element?` rule, plus **`pmid?` — the boundary
citation added in 0.6 (RM47)**, a free-form PubMed pointer under the same grammar as `StudyRow.pmid`.
The bin row cites; the citation table describes, which is what keeps `StudyRow`'s provenance column set
from migrating here one column at a time. Per-kind key fields: `ActivityPhenotypeRow`→`(gene)`;
`CopyNumberRow`→`(gene, modifier_gene, modifier_cn)`; `RepeatAlleleRow`→`(gene, repeat_unit)`;
`HeteroplasmyRow`→`(gene, reference_sequence, tissue, variant_key)` (rejects the legacy `NC_001807`
mtDNA lineage, fraction ∈ [0,1]). `validate_bins()` is a table-level check: overlapping resolved ranges
in a key group are a compile error; interior coverage gaps are warnings.

`HeteroplasmyRow`'s **`variant_key` joined the key in 0.5** and closed a blocking gap. A mitochondrial
gene carries several pathogenic variants with different thresholds — MT-TL1 has m.3243A>G *and*
m.3271T>C, both causing MELAS — and keyed on the gene alone their bins collided and `validate_bins`
**errored**, so the module could not compile. `trait_efo_id` is in the group key but could only have
separated them by giving one disease two ontology ids. The row therefore carries optional
`rsid`/`chrom`/`start`/`ref`/`alts` mirroring `PharmVariantRow`, entering the key through `variant_key`;
optional means a single-variant table groups exactly as before (P3/P8), and `alts` is in the derivation
because MT-ATP6 m.8993T>G and m.8993T>C are one base with two alleles. (That `variant_key` was a
*property* until 0.6, when RM43 made it a stamped field so the compiler could fill a resolved
coordinate without re-keying the row; the value is unchanged.)

**On a continuous kind two bins may share an endpoint, and the higher one owns it (RM35, 0.5).** The
lookup rule a consumer implements once: *select the row with the greatest `measure_min ≤ x`* within the
group. So `allele_fraction` bins `0.0–0.1`, `0.1–0.3`, `0.3–1.0` tile exactly, a measurement of `0.1`
selects the middle row, and `1.0` selects the top one. Before this, inclusive bounds +
overlap-is-an-error + any-hole-is-a-warning were jointly **unsatisfiable** on `allele_fraction` /
`prs_percentile` — adjacent bins either shared an endpoint (error) or left a hole (warning), for any
epsilon — so every such table carried a finding forever. `measure_max` stays inclusive on **every**
kind: half-open for continuous kinds only would make one column's meaning depend on `measure_kind` (P5)
and would put the domain's top value (AF `1.0` is homoplasmy) out of reach of a closed top bin.
Discrete kinds are unchanged — `repeat_count`/`copy_number` tile cleanly under inclusive bounds, which
is where the convention came from, so for them a shared endpoint is still a real overlap and an error.
Two bins sharing a *lower* bound refuse on any kind: the tie-break has nothing to order.

**PGx rows** (`pgx.py`). `HaplotypeRow` (variant↔`allele` junction; the allele is bases or a symbolic
structural allele — see *The allele grammar* above);
`AlleleFunctionRow` (`gene`+star `allele` verbatim identity, `function_status` in `VALID_FUNCTION_STATUS`,
`activity_value?`, CN/SV conveniences); `DiplotypeRow` (`gene`+`haplotype_a`/`haplotype_b` canonicalized
`a ≤ b`, `conclusion`, PharmGKB `drug?`/`response?`/`evidence_level?`, CPIC `recommendation_strength?`
and `clinical_context?`); `PharmVariantRow` (`drug`+
`conclusion`, single-variant, `evidence_level?` 1A…4, `genotype?`, `phenotype_category?`, `annotation_id?`).
`HaplotypeRow` and `PharmVariantRow` also carry a **compiler-filled `alts`** since 0.6 — parquet-only,
never authored, outside the key; see *Stamped identity on the positional tables* above.

`PharmVariantRow.genotype` (0.5) carries the axis PharmGKB actually publishes on: a clinical
annotation is stated **per genotype**, and the calls can be opposed (rs4149056/simvastatin reads
"decreased" for CC and CT, "increased" for TT). It is therefore in the dedup key
`(variant_key, drug, genotype)` — without it the real corpus was rejected as duplicate rows. The
grammar is the shared `AuthoredModel` one, so a genotype means the same thing here as on a
`VariantRow`; a haplotype-keyed annotation (`*1`) belongs on `DiplotypeRow` instead. A structural
allele (`del/del`) is now spellable — RM5 shipped in 0.6 — but ClinPGx publishes no **length** for it,
and a lengthless symbolic allele is a rule the compiler drops, so `clinpgx_draft` still declines to
write those rows and now says which of the two reasons it is.

`DiplotypeRow.clinical_context` (0.5, RM29b) is the same shape of fix one table over: CPIC scopes a
gene/drug recommendation to a **setting**, and the settings disagree. Clopidogrel carries three
(`CVI ACS PCI`, `CVI non-ACS non-PCI`, `NVI`) where the same Poor Metabolizer diplotype is graded
`strong` in one and `moderate` in the others. It is in the dedup key
`(gene, haplotype_a, haplotype_b, trait_efo_id, drug, clinical_context)`, so the settings coexist as
distinct rows and the consumer selects its own. Deliberately **not** called `population`:
`FrequencyRow.population` is an ancestry group, and CPIC's real values are indication, age band,
prior-treatment status and dose band — one name for two axes across two tables is the P5 mistake.
Open rather than a vocabulary (every guideline body scopes differently) and whitespace-stripped on
load, since three of CPIC's live values carry a trailing space and the column is part of the key.

`phenotype_category` and `annotation_id` complete the key, and both were earned by real data. One
variant and one drug carry **several distinct annotations**: rs4149056 + simvastatin is
Metabolism/PK at level 1A, Efficacy at 3 *and* Toxicity at 1A, each with its own three genotypes.
1,199 of 17,380 (variant, drug, genotype) triples in the release map to more than one annotation —
839 separated by category, and 283 by neither category nor level, which is what `annotation_id` is
for. A source accession as identity is not novel here: `PgsRow` keys on `pgs_id` the same way. The
full duplicate key is `(variant_key, drug, genotype, phenotype_category, annotation_id)`.

**`PgsRow` → `pgs.csv`.** Required `pgs_id` (`^PGS\d+$`). Optional `trait_efo_id`, `note`, `group`,
`training_ancestry?` (list, `VALID_TRAINING_ANCESTRY`), `training_cohort`, `match_rate_floor?` ([0,1]),
`research_tier?` (`VALID_RESEARCH_TIERS`). A manifest of Catalog IDs — not authored per-variant weights
(that is roadmap RM16).

## The consumer join contract — three states, and the one that gets collapsed

A module supplies the annotation; the consumer supplies the measurement it is joined against. That
split leaves one obligation on the consumer's side of the seam, and it is normative rather than
advisory, because getting it wrong turns a correct annotation into a wrong report:

**A conforming consumer MUST distinguish a covered reference call from a no-call before asserting any
reference or absence interpretation, and MUST NOT read "absent from a variant-only callset" as
hom-reference.** Absence from such a callset means *either* that the site was callable and matched the
reference *or* that it was never callable at all. Collapsing the two fabricates a confident reference
genotype the data does not support — and for a recessive carrier row, or for the reassurance that a
pathogenic variant is absent, that fabrication runs in the dangerous direction: it is the difference
between "screened negative" and "not screened".

This is the tri-state rule the rest of the schema already obeys (`None` is never `False`), one level
down and pointed at the consumer. Four columns exist so a module can say where it applies, and none
of them measures anything:

| Column | Says |
|---|---|
| `VariantRow.requires_callable` | the *absence* of this variant is the informative call, so a consumer without callability data withholds the conclusion rather than asserting the reference one |
| `VariantRow.callable_from` | which VCF field(s) the proof of callability lives in (`FORMAT/DP`, `FORMAT/GQ`, `FORMAT/FT`, `FORMAT/DP\|FORMAT/GQ`) — a pointer, never an expression |
| `VariantRow.quality_from` + `min_quality` | the floor below which what *was* seen is not good enough to act on. A consumer that cannot read the field **withholds** — an unevaluable floor is unknown, never satisfied |
| `MeasureBinRow.unresolved` | the mandatory no-call sentinel on every binning table: a missing measurement selects it and **never** the lowest or reference bin |

### `*` in a call — the same rule arriving as a spelling (0.6, RM59)

The obligation above is usually met by reading `DP`/`GQ`/`FT`. There is one case where the callset
states it outright, in the genotype itself, and it is easy to drop: VCF's `*` — *"allele missing due
to overlapping deletion"* (§1.6.1.5). It is what any joint-called VCF writes at a site some deletion
called elsewhere overlaps, so `ALT=A,*` with `GT=0/2` is ordinary data rather than an edge case.

Since 0.6 a `genotype` may name it, so a module can carry a row about such a call
(`base.genotype_allele_ok`; `alleles.UNOBSERVABLE_ALLELE`). The unphased pair is written sorted like
every other, and `*` sorts first — `*/A`, not `A/*`.

**A conforming consumer MUST NOT drop a `*` from a call and read what remains as the whole genotype.**
Dropping it turns `*/A` into a single observed `A`, which reads as reference-like at a heterozygous
site and takes the reference conclusion — the same "not screened" reported as "screened negative" that
the paragraph above forbids, arriving through a spelling instead of through a missing record. And
because it is a spelling, `requires_callable` does not catch it: the row *is* present, so nothing looks
absent.

**The rule is the house algebra applied at the join.** A `*` member is **unknown**, never reference and
never a mismatch:

- Matching a module's `genotype` against a call carrying `*`, the `*` member matches **nothing** and
  contradicts **nothing** — it withholds. The observable members are still matched normally, so
  `*/A` against a row about `A/A` is *unknown*, and against a row about `C/C` it is decidably **false**
  (Kleene: `unknown AND false` is `false` — the observed `A` already settles it).
- A call whose members are **all** `*` observed nothing at that position; treat it exactly as a no-call.
- A module that says nothing about `*` — which is nearly all of them, since it describes a *sample* and
  a module carries none — leaves a `*`-bearing call **unresolved for that row**. Withhold the
  conclusion; do not fall through to the reference one.

The compiler applies the same reading internally, which is where the rule is enforceable rather than
merely stated: `resolution.hosting_verdict` drops a `*` member before comparing a genotype to a locus —
on **both** sides, so a `*` in the record's own ALT list is ignored the same way — and the *rest* of the
call is still judged, so `*` never reads as a contradiction and never masks one (see
[COMPILER.md](COMPILER.md)). `*` is deliberately **not** a symbolic allele — those name a variant whose
sequence is unspelled, and `*` names no variant at all — so none of RM5's machinery touches it, it
carries no length, and it mints no VRS allele id.

Two corollaries worth stating because each is a real collapse someone has shipped. A measurement that
is *present but matches no bin* is a third thing again — "no matching bin", not `unresolved` — and the
remedy is authoring the reference bin explicitly, since the compiler cannot detect a missing edge bin
without a domain floor (see `binning.validate_bins`). And combining these states uses **Kleene**
semantics, not withhold-on-any-unknown: `unknown AND false` really is `false`, so an ε4-gated
conclusion is decidably false at ref/ref whatever the call quality was.

The format carries no per-sample coverage and never will — the three-state call is derivable from
standard VCF fields (`DP`/`GQ`/`FT`, or a gVCF reference block), which is why this is a contract on the
consumer and a set of pointers in the module rather than a table.

### Reading the VCF the pointers point at (0.6, from the VCF 4.4 audit)

Four columns above name fields in a file this format never sees, so the rules for reading that file are
part of the same contract. Each of these is a real way to get a well-formed number and a wrong answer,
and none of them is detectable by any offline gate.

**`QUAL` changes sign with the record, and `requires_callable` rows are read from the record where it
is inverted (RM57).** §1.6.1.6 defines QUAL as `−10log10 prob(no variant)` when ALT is present and
`−10log10 prob(variant)` when ALT is `.`. So a QUAL of 60 on a variant record means the variant is
almost certainly real, while the same 60 on a monomorphic reference record means the position is almost
certainly *variant* — the opposite of a clean reference call. A `requires_callable` row is exactly the
one a consumer proves against the reference record, so `quality_from=QUAL, min_quality=30` there asks
for evidence that the position *is* variant before concluding that it is not, and raising the floor
makes the answer more confidently wrong. Prefer a per-sample confidence field (`GQ`). The compiler
warns when it sees the combination and does not refuse it: whether QUAL is inverted depends on the
record, which the compile path will never see, and the same row read against a variant record elsewhere
in the file is legitimate.

**Reference evidence is a block, so callability is interval containment and the depth field is
`MIN_DP` (RM57).** A gVCF states reference confidence as one record spanning a range (`1 4370 . G <*>
. . END=4383 GT:DP:GQ:MIN_DP:PL`, §5.5), not one record per base. A consumer joining `callable_from` on
position equality will find nothing at most covered positions and read it as a no-call. And `DP` on such
a record is the block *average*: a DP of 25 over 14 bases is compatible with an uncovered base inside
them, which is precisely the case `requires_callable` exists to catch. `MIN_DP` is the block floor and
is what a callability threshold should be stated against.

**A measurement that spans several bins has no state, and the placeholder is to withhold (RM56).**
`RUC` travels with `CIRUC` and `CN` with `CICN`, and a missing bound on either means *unbounded*
(§3) — so a repeat or copy-number measurement is an interval, and `reference_examples/
htt_repeat_expansion` has three thresholds inside a 14-count window for it to cross. The three states
above do not cover it. Until a policy vocabulary lands (0.7, with the rest of the repeat work), a
conforming consumer that reads an interval touching two or more bins **withholds**: it does not pick
among them, and it does not fall back to `unresolved`, which claims that no measurement was available.
The compiler warns on any such table.

**Compare in float32, not float64 (RM62).** §1.3 makes every VCF `Float` a 32-bit IEEE-754 value, while
every bound and floor here is a Python float64 parsed from the decimal the author typed. Widening a
float32 is exact but not value-preserving against that decimal, and **which way it moves depends on the
decimal**: a VCF `0.1` widens to `0.100000001490116…`, strictly **above** an authored `0.1`, while a VCF
`0.9` widens to `0.899999976158142…`, strictly **below** one. Both directions lose a row. Upward, an
**inclusive `measure_max`** (`0.1`, `0.3`, the `mt_heteroplasmy` boundaries) is missed by a value that
reads as equal in the source file; downward, a `measure_min` drops that value into the bin beneath, so
neither bound is the safe one and `min_quality` against a float32 QUAL is the same shape again. The rule
is to **compare in float32** — narrow the bound the same way the measurement was narrowed
(`struct.unpack("f", struct.pack("f", bound))[0]`, or `numpy.float32`) and compare the two. Rounding to
float32 is monotone, so where the measurement really is a float32 read — the case the spec describes —
that comparison is exact whichever way the decimal moved. Against a value that never went through
float32 it is a *narrowing* rather than an identity: it errs toward admitting the boundary
(`float32(0.30000000000000004) == float32(0.3)`), which is the direction to err in for an inclusive
bound. Narrowing only the bound is **not** the rule, and that is the direction that loses a row:
a consumer parsing the text cell straight to float64 meets a narrowed downward-rounding upper bound
that rejects a value the naive comparison would have matched, which is this defect pointed the other
way. Nor is an epsilon the rule: that is a guess about magnitude and this is an exactly-known
representation. The schema keeps decimal bounds deliberately: the DSL exists for the human, and the
parquet already carries the machine form.

**A pipe in a `variants.csv` genotype means "phase recorded but unaddressable" (RM63).**
VCF defines allele order only *within* a phase set — §1.6.2 adds PSL precisely because with PS a
genotype "isn't connected to any specific haplotype (i.e. first or second)" — and there is no global
first homolog. This format has no phase-set column, so an authored `A|G` and an authored `G|A` are
distinguishable to the schema and indistinguishable to any consumer, and two rows both written `A|G`
assert nothing about being in cis. The order is still preserved byte-for-byte through the round trip
(Principle 7) and `flags: phased` still records that the call was phased; neither says which homolog.
A module that genuinely needs cis/trans says so with `diplotypes.csv`, which names haplotypes. The
claim is about the **homolog**, not about zygosity: `1|1` is an ordinary phased homozygous call and the
grammar accepts its transcription, so "a pipe means heterozygous" — which this passage used to say, and
which the comment above `_validate_genotype` still says — is false of `C|C`. The printed column
descriptions carry the narrower reading; the comment is due the same edit.

**Two alleles is the ceiling, and VCF's is not (RM67).** §7.2 permits any ploidy and adds *partial*
phasing on top of it — `GT |0|0/1/2`, where the leading indicator is optional and each separator says
whether that allele is phased with the one before it. The genotype grammar here caps at two and
refuses a mixed separator, which is a deliberate generalization rather than an oversight: a module
annotates human loci where diploid is the upper bound, and the two narrower directions are already
carried (the single-allele arm spells a haploid or hemizygous call, and the compiler warns when a
two-allele genotype lands on MT or non-PAR Y). Nothing is queued against it; the spec's own polyploid
example is a tandem duplication carrying SNVs, so a CNV-aware consumer meeting one is what would
reopen the question. The three refusals say all of this in-line — an author holding a real triploid
call should be able to tell a decision from a typo.

**The VCF `ID` column is a list, and `rsid` is one variant (RM64).** §1.6.1.3 defines ID as a
"semicolon-separated list of unique identifiers", so a real record may carry `rs123;rs456`, or an rsID
beside a COSMIC id. `validate_rsid` accepts exactly one, which is right for the authored side — a row
should name one variant — but it means a consumer joining on `ID` must split on `;` first. Joining the
raw column matches nothing on any multi-id record.

### The VCF pointer columns — namespace and cardinality (RM53/RM54/RM61, 0.6)

Three authored columns point into a VCF: `MeasureBinRow.source_field`, `VariantRow.callable_from` and
`VariantRow.quality_from`. Until 0.6 all three took a **bare token**, and a bare token does not
identify a VCF field.

**A VCF field is identified by its namespace.** INFO and FORMAT are two reserved-key tables that
overlap deliberately, and they collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and — new in 4.4 — `CN`.
`INFO/DP` is the cohort's combined depth and `FORMAT/DP` is this sample's; `INFO/AF` is the cohort
allele frequency of an ALT and `FORMAT/AF` is this sample's fraction of it; `INFO/CN` is
allele-specific copy number where `FORMAT/CN` is the sample's total, so the two differ by a factor of
the ploidy. Where both readings are type-compatible — and for `DP`, `AF` and `CN` they are — nothing
detects the confusion: the consumer reads a well-formed number of the wrong kind and bins it without
error. Both shipped reference examples that used these columns were wrong this way, and
`mt_heteroplasmy`'s `source_field=AF` would have reported a carrier as asymptomatic on the strength of
how rare the variant is in a reference panel.

So the pointer grammar now accepts the **qualified** form (`INFO/DP`, `FORMAT/REPCN`,
`INFO/DP|FORMAT/DP`). A bare key is still legal and still means *unqualified* — widening only, so
nothing published breaks — and the compiler **warns** whenever a bare key is one of the known
collisions. Nothing is defaulted: reading `callable_from` as FORMAT and `source_field` as INFO would
convert *unstated* into a *stated* answer, and it would have been wrong for `mt_heteroplasmy` on the
very first module. The same release also widened the key charset to the spec's own
(`^([A-Za-z_][0-9A-Za-z_.]*|1000G)$`), which the old grammar refused: a dot is legal inside a key and
`1000G` is a key the spec reserves by name.

**A VCF field is described by its cardinality.** `Number` says how many values come back and what each
one is *of*: `A` is one per ALT, `R` one per allele **reference first**, `G` one per genotype, `P` one
per GT allele, `.` unbounded. A pointer at `AD` therefore returns *n+1* integers of which none is the
answer. `MeasureBinRow.source_element` (0.6) says which one, from a closed set of **named rules** —
`largest`, `largest_alt`, `smallest`, `smallest_alt`, `sum`, `sum_alt`, `annotated_alt`, `reference` —
applied by the consumer. An **index** (`AD[1]`, `REPCN[max]`) was refused: it is the first line of an
expression grammar, which is what Principle 1 exists to keep out and the reason these pointers were a
bare token to begin with. A named rule is data, it terminates, and it needs no evaluator.

**"Element" is one of the values the field carries for a record, which is wider than a `Number` slot
and deliberately so.** A caller may pack several values into a single cell — ExpansionHunter reports
both repeat alleles in one `REPCN` cell as `17/42` — and a rule that only spoke about `Number` would
have had nothing to say about the case it was built for. How multiplicity is encoded is the caller's
business and this tier holds no opinion on it (P2); which of the values the annotation means is the
module's, and that is all `source_element` states.

The reference-inclusion trap is written into the vocabulary rather than left to a footnote. On a
`Number=R` field the reference is element zero, so "the larger of the two" has two answers; every
ranging rule therefore comes in a pair — the bare name counts the reference element, the `_alt` name
does not — and on a field with no reference element (including a packed cell of the sample's own
alleles) the two coincide. Per-member prose lives in `vocab.ELEMENT_RULE_MEANINGS` and reaches an
author through the vocabulary marker, which means through every generated surface at once: the
whole-schema `authoring_reference()["vocabulary_notes"]` block, the `notes` key beside the members on
each field that binds the vocabulary, and `just-dna-compiler describe <kind>`, which is the command an
author filling one table actually runs. `htt_repeat_expansion` now authors
`FORMAT/REPCN` + `largest`, which is the clinical rule for a dominant repeat expansion: *the longer of
the two alleles*, whichever of them happens to be reference-length.

**`callable_from` and `quality_from` have no companion column, deliberately.** Both can name a
multi-valued field (`FORMAT/AD`), and no module does; under the 0.6 charter amendment a `variants.csv`
column is the most expensive kind of addition this format makes, so the two names are **reserved**
(`vocab.RESERVED_NAMES_0_4`) against a real case rather than built against a hypothetical one. Adding
one later is additive and minor-legal, and everything that reads the relation
(`vocab.VCF_POINTER_COMPANIONS`) is generic over it. The compiler's cardinality warning is scoped to
pointers that *have* a companion for the same reason: telling an author to fill a column the schema
does not have is a finding no edit could clear.

**What the compiler declines to say.** `vocab.VCF_FIELD_NUMBER` transcribes the spec's own reserved-key
tables and nothing else. A caller's private key — `REPCN` is ExpansionHunter's, not the spec's — has no
cardinality this tier is entitled to assert, and a bare key whose two namespaces disagree (`CN`) has
none either. Unknown withholds; asserting one would be a source convention wearing a fact (P2). Two
consequences worth naming. `FORMAT/AF` is emitted by every caller and reserved by none, so the
heteroplasmy pointer earns no cardinality warning even though it really is `Number=A` in practice —
which is why the reference example authors `annotated_alt` explicitly. And an element rule sitting on
a field the spec calls **single**-valued is *not* warned about either, which looks like the mirror of
the check and is not: a `Number=1 String` cell is exactly how a packed multi-value field is declared,
so the flag would fire on the correct authoring of the flagship case. The distinction turns on `Type`,
which this tier does not model, and where it cannot decide it withholds.

## Allele identity — the VRS allele id (0.5)

`vrs.derive_vrs_allele_id(chrom, start, ref, alt, *, build="GRCh38") -> str | None` mints a GA4GH VRS
**allele id** (`ga4gh:VA.<32-char digest>`) — a *content-addressed* name for one allele at one place on
one reference sequence.

**It names its build.** The sequence is addressed by its **refget accession**, which is the digest of
the reference sequence itself, so GRCh38 and GRCh37 mint distinct, correctly non-colliding ids. That is
the property RM15's parking note demanded before coordinate identity could be reconsidered, which is why
this is not another entry on the parked pile — see [ROADMAP.md](ROADMAP.md).

**Stdlib only.** The digest is `sha512t24u` over a compact canonical JSON — about twenty lines of
`hashlib` + `base64` + `json`. The format tier gains **no dependency** (it stays pydantic + cryptography),
and a verify-only consumer can recompute the identity offline. Verified rather than assumed: the ids this
mints are byte-identical to the ones `ga4gh.vrs` 2.3.3 computes *and* the ones the live gnomAD API
returns, asserted against a committed ground-truth table.

**Substitutions only, on purpose.** It returns `None` for an indel, an MNV, a multi-allelic cell, a row
with no coordinate, and a contig outside the primary assembly. A VRS allele id is defined over the
*fully justified* allele; for a single-base substitution justification is a provable no-op, but for an
indel it needs the reference *sequence*, which this tier has no access to and will never fetch
(Principle 2). Minting an unjustified indel id would emit a `ga4gh:VA.…` that *looks* interoperable and
silently is not — worse than minting nothing. Indel ids are minted upstream in the enricher and passed
through as data.

`REFGET_GRCh38` (the 24 primary contigs + MT) and `REFGET_GRCh38_LENGTHS` are committed constants, so
minting needs no `seqrepo`, no sequence store and no network. They are remote-*sourced* reference data
frozen into the schema tier, which would normally be a staleness hazard — here it is not, because a
refget accession is the **digest of a sequence that cannot change**: GRCh38's primary contigs are
immutable, so the correct value is fixed forever and the only possible defect is a typo. That is what
the `@integration` re-derivation guards, and it is what makes this unlike a ClinVar snapshot, which
genuinely ages. An `@integration` test re-derives them from
the public seqrepo REST, because a mistyped accession would mint well-formed ids for the *wrong sequence*
and nothing downstream could detect it. Asking for a build with no table raises `UnsupportedBuildError`
rather than quietly answering in GRCh38.

### The rest of the module's public surface

`derive_vrs_allele_id` mints **one** id, but `resolution.csv`'s `vrs_id` is a *cell* — a comma-joined
parallel array of `alts`, one member per ALT, empty where nothing was minted. That codec is public,
because every consumer that reads the column has to agree on it and a second implementation of
"split on commas, keep the holes" is a second chance to lose the alignment:

- **`split_vrs_ids(value) -> list[str | None]`** — the cell → one entry per ALT, `None` for a hole.
  `join_vrs_ids` is the inverse. The pairing with `alts` is positional, so a member is only
  interpretable beside the ALT at the same index; this is what lets the compiler's verify pass give
  each ALT its own verdict, and what makes a swapped pair a mismatch rather than an invisible desync.
  A consumer counting identity coverage counts **slots**, not rows: a two-ALT row where only the
  substitution minted is `(2, 1)`.
- **`validate_vrs_id` / `validate_vrs_id_list` / `validate_caid`** — the grammars, shared by every
  model that declares one of these columns, so `ga4gh:VA.…` means the same thing in every table.
- **`is_substitution(ref, alt)`** — the predicate behind minting's "substitutions only" rule, exposed
  so a caller can ask *before* getting a `None` back and having to guess which of the several reasons
  applied.
- **`normalize_chrom` / `refget_accession`** — contig spelling and the accession lookup.
  `refget_accession` **raises** `UnsupportedBuildError` for a build with no table rather than
  returning `None`; a caller that treats one unaddressable row as a finding rather than a failure has
  to catch it (the compiler's verify pass learned this the expensive way — the exception escaped and
  aborted a whole compile over a single row it could not check).
- **`PAR_GRCh38` / `in_pseudoautosomal_region` / `par_partner`** — the pseudoautosomal *geometry*,
  here rather than in the enricher because it is a fact about the assembly. The pairing is an offset,
  not an equality: PAR1 shares coordinates between X and Y and PAR2 does not, so a "same base on both
  contigs" shortcut passes a PAR1 module and silently fails a PAR2 one. Which contig a *source*
  publishes is a different question and stays in the enricher (P2).

### The identity switch — `variant_key` derives from the VA

`base.derive_variant_key` has three cases, in precedence order:

1. **rsid** — an rsid row keeps its rsid, unchanged.
2. **A resolved single-base substitution** — the key **is** its `ga4gh:VA.…` id (new in 0.5).
3. **Everything else** — `chrom:start:ref`, or `chrom:start:ref:alts` when an alt is present.

Why this was legal now rather than at 1.0: `variant_key` is **derived and frozen, never authored**
(`_COMPILER_MANAGED_FIELDS`), so changing its derivation touches no authored schema, no DSL, and no human
author — the human-authorability gate is untouched. What makes it major-class is not the digest but the
**re-keying**: the same authored row acquires a different `variant_key`, so anything that stored the old
one no longer joins. When this shipped, 0.4 was the published line and 0.5.0 had never been cut, so it
rode the same one-time pre-publication re-baseline the alt-carrying key already rode and no published
artifact moved. **A further identity change is a 1.0 item**, and that holds independently of the 2026-08-11
amendment — an additive optional column is minor-legal now, but changing what an existing key *means*
never was.

> **A VA does not encode `ref`.** VRS addresses the place and the alt; the reference base is *determined*
> by the accession plus the interval (`sequence[start:end]` has exactly one answer), so storing it would
> store a derived value — and a redundant field is a way for one allele to acquire two ids, which is what
> a content-addressed identity exists to prevent. Correct semantics, but it costs two guarantees, and
> each is bought back where it can be: two rows at one position claiming different reference bases used
> to be two keys and are now one, so the **compiler** carries an explicit "inconsistent reference allele"
> error (internal contradiction, catchable offline); and the authored `ref` is otherwise unchecked, so
> the **enricher** — the only tier with sequence access — compares it against the real bases
> (`sequences.verify_reference_alleles`, see [ENRICHER.md](ENRICHER.md)).

Position-level **matching** helpers (studies, the reverse pos→rsid lookup, haplotype dedup) call
`derive_variant_key` **without** `alts` and therefore never mint a VA — a study matches its variant at
`chrom:start:ref` regardless of allele. Mixing those up would orphan every study.

## The derived-fact tables (0.5–0.6, **provisional**)

Six siblings of `resolution.csv` at six different grains — `frequency.FrequencyRow` →
`frequencies.csv` per **allele**, `gene_metrics.GeneMetricsRow` → `gene_metrics.csv` per **gene**,
`literature.LiteratureRow` → `literature.csv` per **citation**, `gene_validity.GeneValidityRow` →
`gene_validity.csv` per **(gene, disease, inheritance mode, submitter)** (0.6, RM24),
`assertions.ClinicalAssertionRow` → `clinical_assertions.csv` per **(allele, archive record)**
(0.6, RM25), and `sources.SourceRow` → `sources.csv` per **(data source, layer)**. All are reference
facts rather than annotation: injected, hashed by facts, and compiled into their own optional
parquets. All are standalone `BaseModel`s with `extra="forbid"`, for the same reason `ResolutionRow`
is.

Five of the six are machine-produced and human-*overridable*; `sources.csv` is machine-produced and
human-**authored**, because a source a curator read by hand has no pass to write its row (see above).
That is why it is the only one with a `draft`/`template` route and a natural key.

**Why six tables is not sprawl, stated once because the instinct recurs.** The 0.6 charter amendment
prices a schema addition by the layer it lands in: a parquet column is approximately free, a *derived*
CSV is half, and an **authored** schema is full cost. The "one CSV, one concern, do not burden the
rare author" gate is a rule about the authored layer — nobody hand-writes `gene_validity.csv`, so its
column count costs the rare author nothing. What a derived table still costs is the half a human pays
when they open one, which is why each of these documents its grain in its own module docstring and why
none of them may be hand-edited into a claim its source never made.

**Three tables sound like they are about the same thing, and they are three different levels.** The
names do not separate them — `studies`, `literature`, `sources` all read as "references" — so read them
by grain and by who writes them:

| | grain | asks | written by |
|---|---|---|---|
| `studies.csv` | a variant, a binning bound, or the module + a claim | *why do I believe this row?* | the curator |
| `literature.csv` | a `pmid` — an article | *does that citation check out, and on what terms?* | an enricher pass |
| `sources.csv` / `licensing.csv` | a `(source, layer)` — a dataset | *where did the bytes come from, on what terms?* | a pass **or** the curator |

They stack rather than overlap, and the reason they cannot merge is that **a paper is not a data
source**. `studies.csv` is authored annotation and feeds `content_signature`; `literature.csv` is a
verification record *over* those citations, and its facts are hashed separately so an embargo lifting
or a re-run cannot move the module's content identity; `sources.csv` is one level up again, describing
the *datasets* consulted.

**PubMed is deliberately not one of them (RM46).** The literature pass writes `source="pubmed"` into
every row it produces, and there is no `pubmed` row in the licence table and will not be one: a
literature source's terms are **per article, not per source**. PubMed's metadata is one thing; the
article belongs to its publisher, and Europe PMC's open subset spans CC-BY, CC-BY-NC and bronze — so
one `pubmed` row would be right for a module citing only ids and a false all-clear for one carrying a
`provenance_quote` lifted from a CC-BY-NC article, since that quote is publisher text sitting in the
module's own *annotation* layer. The terms therefore live on the literature row that names the article
(`license`, `share_alike`, `commercial_use`, `redistribution`), and the compiler excludes
`literature.csv`'s `source` from the values `sources.csv` has to account for. Quoting a non-commercial
article **warns and never gates**, the same call as the ClinVar `clin_sig` cross-check: refusing would
make the format arbitrate a copyright question. A consequence worth stating: nothing in any fact table
can corroborate a `literature`-layer declaration any more, so that layer is unconditionally exempt from
the stale-source check. They are also consumed by
different things — the compile licence gate reads `sources.csv` and no other file — and each hashes its
own fact set with its own exclusions, which one merged table could not do.

The naming is the weakest part of this: `sources.csv` is a licensing and attribution ledger whose name
collides with the `source` *column* that means "which link answered" in four other tables. The better
name is `licensing.csv`, and the rename splits.

**The input half landed in 0.6** (RM51): `licensing.csv` is a second accepted spelling, `sources.csv`
is deprecated (warn-only, read exactly as before) and is removed at 1.0 — the cadence the 0.6 charter
amendment settled, and this is the case that prompted it. Write either; the compiler reads whichever
the module carries and refuses if it carries both. Since 0.6 the file may also sit under a `derived/`
subdirectory (RM49); see [COMPILER.md](COMPILER.md) for the layout rules. `reverse_module` resolves
the name through `layout` rather than joining one on: it regenerates a spec, so it emits the
*preferred* spelling on a fresh tree, migrating a module off the old name across one round trip while
moving none of its four identities. **`draft.append_rows` / `append_partial_rows` resolve it too, since
0.6** — through `draft._draft_path`, which is deliberately *narrower* than `layout.sidecar_write_path`:
it consults `SIDECAR_SPELLINGS` and every other table (`variants.csv`, `studies.csv`, each table kind)
takes the fall-through unchanged. That is the point. `layout`'s general resolver is name-agnostic, so
applying it wholesale there would hand `variants.csv` a second home and reintroduce the asymmetry RM49
exists to protect; and where the caller *names* the file, an absent one is created under the name they
asked for, because silently redirecting `draft sources.csv` elsewhere answers a different question than
the one put. Only the collision is repaired.

Two lanes reached this from opposite ends in the same release, which is worth recording because the
disagreement was real and one side was wrong: one measured the collision (`append_rows(<module carrying
sources.csv>, "licensing.csv", …)` writes a second file and the next compile refuses naming both) and
declined to fix it, on the correct objection that the general resolver would over-reach; the other built
exactly the narrow, spelling-set-gated form that objection implies. The gate on `SIDECAR_SPELLINGS`
membership *is* the "sidecar-name set `layout` owns" the first lane asked for.

**The output half waits for the major.** `sources.parquet` is inside `artifact.digest` and consumers
read it by name, and `manifest.sources` is a published key, so renaming either is a *removal*
([ROADMAP § The 1.0 cleanup](ROADMAP.md#the-10-cleanup-candidate-tracker)). For the whole 0.x tail a
module therefore reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is a real
legibility regression against today's single consistent (bad) name, and it is the price of not paying
for the rename twice.

**`FrequencyRow` — one row per (allele, ancestry group).** Facts: `variant_key` (coordinate-derived, so
it lines up with post-expansion weights rows), `rsid?`, `chrom?`/`start?`/`ref?`, `alt?` (**one** alt, not
`resolution.csv`'s comma-joined `alts` — a frequency is per-allele), `population`, `allele_count` (AC),
`allele_number` (AN), `homozygote_count?`, `hemizygote_count?`, `faf95?`, `dataset`, `genome_build`.
Provenance (excluded): `source?`, `status?`, `fetched_at?`. Cross-references `vrs_id?`/`caid?` are also
outside the fact set.

- **`status` is a closed vocabulary with THREE members, and the third is not redundant.**
  `VALID_FREQUENCY_STATUS = {resolved, not_found, not_covered}`. `not_found` means the source was asked and
  has no such allele — a fact about a locus it *does* cover. `not_covered` means the locus is outside the
  source's callset, so it has no answer and none can be inferred: gnomAD hard-masks the Y pseudoautosomal
  region, and recording an absence there stated something nobody established (`None` ≠ `False`). Not
  `unchecked`, which is this codebase's word for a question never *put*. The column was free text until
  0.5, which is how the false absence reached a fact table in the first place.

- **`allele_frequency` is a derived property, never a stored column.** Integers round-trip through CSV
  exactly; a stored float invites formatting drift, which is a Principle 7 idempotency hazard, for the
  price of duplicating one fact in two columns. The **parquet** materializes it as a real `Float64`, so a
  consumer does no arithmetic — the usual "parquet absorbs the precision, the DSL keeps the human shape"
  split. `AN = 0` yields `None`, not zero: no coverage means *no information*, not "frequency zero".
- **`dataset` is inside the fact set on purpose** — a v4.1 number and a v2.1.1 number are different facts
  about the world, not two spellings of one, so a table that swapped releases must hash differently.
- `faf95` is the one stored float; it is written with `str()`, which since Python 3.1 is the shortest
  representation that reloads to the identical double — exact *and* deterministic, unlike a fixed `%g`.

**`GeneMetricsRow` — one row per gene.** `gene` (matching `variants.csv`'s column), `gene_id?` (`ENSG…`,
the stable identity behind the mutable symbol), `transcript?`, `mane_select?`, `pli?`, `loeuf?`, `oe_lof?`,
`oe_lof_lower?`, `lof_z?`, `mis_z?`, `syn_z?`, `oe_mis?`, `obs_lof?`, `exp_lof?`, `constraint_flags?`,
`haploinsufficiency?`, `triplosensitivity?` (`VALID_DOSAGE_SENSITIVITY`), `dataset`. `loeuf` is stored under that name rather than `oe_lof_upper` because it is the number clinical
readers ask for by name, with `oe_lof`/`oe_lof_lower` beside it so the interval is not lost. Gene-level
and variant-level facts are **separate tables** rather than gene metrics repeated on every variant row
(Principle 5, and one CSV = one concern).

- **Two authorities, two rows, one gene (0.5).** gnomAD says how intolerant of variation a gene looks
  in a population sample; ClinGen says whether a curated panel found evidence that losing or gaining a
  copy causes disease. Different questions, so a gene carries a row per `dataset` rather than one row
  with both — merging them would put a statistical estimate and a curated verdict under one provenance.
- **Dosage ratings are stored as TERMS, not ClinGen's numeric codes**, and this is a deliberate
  exception to the keep-the-source-value-verbatim rule. The codes look ordinal and are not: `0`–`3`
  grade increasing evidence, but `30` means "gene associated with autosomal recessive phenotype" and
  `40` means "dosage sensitivity unlikely", so sorting the raw number ranks `40` above `3` — the
  reverse of the meaning. Verbatim is right for an identity; it is wrong for a code that lies about its
  own order. `vocab.DOSAGE_SENSITIVITY_BY_CODE` holds the total, lossless mapping.

**`LiteratureRow` — one row per cited article, keyed by `pmid`.** The first sidecar not keyed on a
variant, and deliberately so: a DOI, a PMCID and "does PubMed have this record" are properties of the
*paper*. A module with three hundred variants citing five papers carries five rows here, not three
hundred with the same DOI repeated — the same argument that put gene constraint in its own table, and
the one that keeps the file readable by the human the DSL exists for. Facts: `pmid`, `doi?`, `pmcid?`,
`exists?`. Everything else is provenance or time-varying state: `doi_exists?`, `is_open_access?`,
`license?`, `share_alike?`, `commercial_use?`, `redistribution?`, `quotes_authored?`, `quotes_found?`,
`quote_source?`, `source?`, `status?`, `fetched_at?`.

- **No `dataset` column**, unlike its two siblings. gnomAD ships numbered releases; PubMed and Europe
  PMC are continuously updated and publish no release identifier, so the column could only ever be null
  or a fabricated label. `fetched_at` is this table's currency marker.
- **`is_open_access` is outside the fact set** because an embargo lifting is the world changing, not the
  module. Inside it, a module's `literature_signature` would move with no authored edit anywhere —
  exactly the property that makes a fact-hash worth having.
- **The four licence columns are outside it for the same reason (0.6, RM46).** A publisher
  re-licensing an article, or Europe PMC learning terms it did not hold last month, changes the world
  rather than the module. `license` is stored **verbatim** as the source spells it (Europe PMC writes
  `cc by`, `cc by-nc`, `cc by-nc-nd`) and the three rights are derived from it at read time, so a
  mapping correction reaches rows already written. They are **three orthogonal axes** and `None` is
  never `False`: CC BY-NC forbids sale while expressly allowing sharing, and a licence the tier has not
  read is undetermined rather than forbidding. The licence is **independent of `is_open_access`** and
  must not be derived from it — PMID 28546431 comes back `isOpenAccess: N` with `license: cc by`,
  because one describes Europe PMC's OA subset and the other describes the article.
- **`pmcid` is the derived home for a PubMed Central id, and there is no authored one (RM50).**
  `StudyRow.pmid` refuses a cell whose only identifier is a PMC id — in any spacing, naming the id it
  saw, because `PMC 3110566` used to be read as PMID 3110566, a real record for an unrelated article.
  A curator holding only a PMC id gets the PubMed one from `just-dna-enricher hint citation --pmcid`,
  which **reports it and never writes it**: filling `pmid` from NCBI would make the existence check
  compare NCBI with itself.
- **`exists` is PubMed's answer and `doi_exists` is Crossref's, and they are different questions.**
  A paywall does not hide a record from PubMed — it hides the *fulltext* — so `exists` is answered for
  paywalled work. What PubMed cannot answer for is a citation it does not index at all: a preprint,
  book, thesis or dataset has a DOI and no PMID, which is what Crossref covers. Two registries, two
  columns (Principle 5), never one overloaded `exists`.
- **`quote_source` records how far the search reached**, because a hit and a miss are not symmetric: a
  phrase found in an abstract is in the paper, while a phrase absent from a 200-word abstract says
  nothing about the body. Without the column a `quotes_found` of 0 would read as a verdict when it was
  only a partial look.
- **Quote coverage is two integer counts, not a boolean.** A quote is authored per *study row* while
  this table's grain is the citation, and two study rows may cite one paper with different quotes, so a
  single flag would have to lie about one of them. `quotes_found` is **null when no fulltext could be
  retrieved** and `0` when a fulltext was read and the quote was not in it — a distinction the manifest
  block preserves, because collapsing it would report an unread paper as a wrong citation.

**`GeneValidityRow` — one row per curated gene–disease assertion (0.6, RM24).** The question
`gene_metrics.csv` cannot answer: constraint says how intolerant of variation a gene looks and dosage
sensitivity says whether losing a copy causes disease, while this says whether variation in *this*
gene causes *this* disease and how sure a curating body is. Facts: `gene`, `gene_id?` (`HGNC:…`),
`disease_id?` (a CURIE, stored verbatim), `moi?` (`VALID_INHERITANCE_MODE`),
`classification?` (`VALID_GENE_VALIDITY`), `classification_raw?`, `classification_date?`, `submitter?`,
`assertion_id?`, `dataset`. Outside the fact set: `disease_label?` and `report_url?` plus the usual
`source?`/`status?`/`fetched_at?`.

- **A table, not columns on `gene_metrics.csv`, because the grain is `gene × disease × inheritance
  mode`.** Dosage sensitivity went the other way in 0.5 for exactly that reason — a haploinsufficiency
  rating is one value per gene — while *RYR1* carries a definitive assertion for malignant hyperthermia
  and a separate one for a congenital myopathy, and neither is a property of the gene alone.
- **`moi` is part of the KEY, established by probe rather than assumed.** 59 (gene, disease) pairs in
  ClinGen's 2026-08-13 release carry two rows differing only by mode of inheritance; keying without it
  keeps one and leaves the module claiming the survivor covers both. `(gene, disease, moi)` has zero
  collisions in that release.
- **`submitter` is in the key too, because GenCC is an aggregate.** Nineteen submitters, and one
  gene–disease pair routinely carries several at different strengths — the disagreement is the data.
  Reducing it to one row is the bare-triple mistake `PharmVariantRow` already paid for once.
- **Both vocabularies are mapped at the enricher boundary, never stored verbatim.** ClinGen writes
  `Disputed` where GenCC writes `Disputed Evidence`, and `AD` where GenCC writes `Autosomal dominant`;
  a consumer filtering on one spelling would silently miss the other's rows. The submitter's wording
  survives in `classification_raw`, so the mapping stays auditable — the `clin_sig`/`clin_sig_raw`
  shape, and the builders-store-verbatim/readers-map rule the dosage codes already follow.
- **`VALID_GENE_VALIDITY` is a set with a published ladder beside it, not an integer column.**
  `vocab.ORDERED_GENE_VALIDITY` names the four members that really are ordered (limited → definitive);
  `disputed`, `refuted` and `no_known_disease_relationship` are the *opposite* claim rather than points
  on the ladder, and `supportive` is an assertion made off it. This is the ClinGen-dosage argument
  inverted: those codes looked ordered and were not, so they were decoded; these are ordered, so the
  order is published rather than left for each consumer to hardcode.
- **An empty `classification` is an ungraded assertion, not a negative verdict.** A submitter may state
  an association without grading it; that is this codebase's ordinary "withhold when unknown", and it
  is materially different from `no_known_disease_relationship`, which is a graded verdict against.
- **A column that *locates or describes* an assertion is not the assertion**, which is why
  `disease_label` sits outside the fact hash beside `report_url`. It is the ontology's current wording
  for a term the CURIE already names, and it churns on its own: one real export carries
  **MONDO:0017146** under two labels at once — `"sickle cell disease and related diseases"` from
  ClinGen and `"obsolete sickle cell disease and related diseases"` from GenCC. Inside the fact set,
  two submitters recording the same disease would hash differently on label vintage alone.

**`ClinicalAssertionRow` — one row per (allele, archive record) (0.6, RM25).** What a clinical archive
says about an allele **and how much review sits behind it**. Facts: `variant_key`,
`chrom?`/`start?`/`ref?`/`alt?` (one alt, like `FrequencyRow`), `genome_build`, `clin_sig?`
(`VALID_CLIN_SIG`), `clin_sig_raw?`, `review_status?`, `review_stars?` (0–4), `condition?`,
`variation_id?`, `dataset`. Excluded: `rsid?` (see below) and `source?`, `status?`, `fetched_at?`.

- **The number this workspace was computing and discarding.** `clinical.ClinSigFinding.confidence`
  rendered the star rating into a warning string and `draft_gene_panel` used it as a filter (default 2
  — multiple submitters, no conflicts); neither kept it, so a compiled module flattened a one-star
  single submission and a practice guideline to the same `clin_sig`. A number recomputed by every
  consumer is a place to drift, which is the RM40/RM41 argument applied a fourth time.
- **It records; it does not adjudicate.** Whether the module's own `clin_sig` agrees with the archive's
  is `enricher.clinical.verify_clin_sig`'s question, and that check warns in **both** modes on purpose,
  because failing would make the format arbitrate a clinical dispute. Nothing here escalates it; the
  compiler's own check over this table is a position-orphan check and nothing more.
- **`review_stars` is a stored column and not a derived property**, which inverts the house pattern for
  a convenience number (`allele_frequency`, `neg_log10_p`). The derivation — CLNREVSTAT prose to a
  0-to-4 rating — is a **ClinVar convention**, and Principle 2 keeps source conventions out of this
  tier entirely. The enricher owns the mapping (`clinvar_build.review_stars`); the schema holds only
  the bound.
- **Null stars and zero stars are different answers.** `0` is the rating ClinVar gives a submission
  with no assertion criteria; `None` means the record states no review status for anything to be rated.
  Collapsing the second into the first reports an unread record as the weakest evidence available.
- **One row per record, not per variant**, because the archive genuinely holds several records for one
  allele under different conditions — `clinvar.lookup_clin_sig` returns a list and orders it
  best-reviewed first. Collapsing them would pick a condition on the author's behalf.
- **`rsid` is outside the fact set, and the `FrequencyRow` precedent deliberately does not transfer.**
  There the rsID arrives in gnomAD's own payload, so it is part of what the source said. Here the
  lookup is allele-exact on `(chrom, start, ref, alt)` and returns no rsID at all — the column is
  filled from the module's own `resolution.csv`. Inside the hash it would make two modules holding the
  *same ClinVar records* hash differently according to whether their resolver attached an rsID, which
  is precisely the producer-dependence a fact hash exists to exclude.
- **`genome_build` is load-bearing here.** The archive's lookup key is `(chrom, start, ref, alt)` and
  carries no assembly, so a coordinate from another build is a well-formed query returning a different
  variant's clinical call. The pass skips such rows rather than asking (the fourth build confusion in
  this codebase; `assertions.ASSERTION_GENOME_BUILD` is the named constant).

**Ancestry groups** (`vocab.RECOMMENDED_ANCESTRY_GROUPS`) are an **open, seeded** vocabulary in the
`RECOMMENDED_AUTHOR_KINDS` idiom rather than a closed `frozenset` — deliberately, even though Principle 6
makes closed the default. The table must stay source-independent, and TOPMed / ALFA / 1000G bring their
own labels; a closed set would turn a source swap into a schema change. What makes a label interpretable
is the row's `dataset`, not membership. `POPULATION_ORDER` + `population_sort_key` pin the emission order.
This is **not** `pgs.VALID_TRAINING_ANCESTRY` and must never be merged with it: those are 1000G
superpopulations describing *which cohort a score was trained on*, a different axis that happens to share
three letters.

> **Not yet frozen** — the same provisional status as `resolution.csv` below, and for the same reason.

**`SourceRow` — one row per (data source, layer).** Facts: `source`, `layer`
(`VALID_SOURCE_LAYERS`), `license?`, `license_url?`, `license_sha256?`, `attribution?`, `notice?`,
`share_alike?`, `commercial_use?`, `redistribution?`, `declared_use?` (`VALID_DECLARED_USE`),
`dataset?`. Provenance (excluded): `fetched_at?`.

- **`source` is INSIDE this fact set, inverting the other tables.** Everywhere else `source` is
  provenance — which link happened to answer — and is excluded so a human-filled and a machine-filled
  table hash equal. Here the source *is* the subject: "ClinPGx, at the annotation layer, is CC BY-SA
  and forbids sale" is the fact. Drop it and the row loses its key.
- **Exactly five row models carry a `source` column, and four of them are generated** (S17):
  `ResolutionRow`, `FrequencyRow`, `GeneMetricsRow` and `LiteratureRow` — the enricher-produced
  sidecars, where a pass records which link answered — plus `SourceRow` itself, where it is the subject
  as above. **No hand-authored fact table has one**, by design: a curated annotation's provenance is the
  module's, not a per-row link. The consequence is worth stating because it is structural rather than a
  matter of care — the compiler's `used_sources` coverage check is built from those columns, so a source
  an author read **by hand** is invisible to it no matter how carefully they work, and the remedy is to
  add the `sources.csv` row directly. There is nothing to fill in the fact table, which is why writing
  `source` onto one now fails with a message that says so (`vocab.MISPLACED_COLUMN_REASONS`) rather than
  with the bare "extra inputs are not permitted" that sent a consumer to read the models.
- **`share_alike` / `commercial_use` / `redistribution` are tri-state.** `None` means the terms could
  not be established, never "does not forbid". A source not shown to permit anything must not read as
  permissive, so `None` and `False` hash differently and are handled differently everywhere.
- **`redistribution` is a third axis, not a shade of `commercial_use` (0.5).** CC BY-NC forbids sale
  and expressly allows sharing; an academic-use-only source (OMIM, dbNSFP) permits neither, and a
  module embedding one cannot be published at all, free or not. Recording the second as merely
  non-commercial understates it. Summarized module-wide on the same most-restrictive-wins ladder
  (`sources.taints_redistribution`) and, since RM27 settled in 0.6, **recorded and never gated here**
  — see the ask below.

### The redistribution verdict is recorded here and enforced downstream — an ask, addressed (RM27)

`manifest.sources.redistribution` is the module-wide answer to *may this module be passed on at all*:
`false` when an `annotation`-layer source forbids it, `null` when any source's terms could not be
established, `true` only when every one of them is known and permits it. `null` is undetermined and
**never** a permission. `nonredistributable_layers` names which layers carry the bar, the same way
`noncommercial_layers` pairs with `commercial_use`.

**None of these four packages gates on it, and none of them will.** The compile gate reads
`commercial_use` and nothing else, deliberately: a *distribution right is not a use*, so
`declared_use` (`unstated` / `non_commercial` / `commercial`) cannot express the verdict, and asking
the author a second build-time question about an act that has not happened yet is the wrong shape —
the answer is a property of the publish, not of the build. Gating on the act is right; the act is
downstream.

> **To the registry, concretely: enforce `manifest.sources.redistribution` at publish, at 0.6
> integration.** A module whose verdict is `false` must not be served to third parties, and one whose
> verdict is `null` must not be treated as clear — undetermined terms have not been shown to permit
> anything. The verdict is in the manifest already, computed by `_sources_block` on the same
> most-restrictive-wins ladder the sale verdict uses, so the enforcement is a read rather than a
> derivation, and no re-derivation from source names is needed or wanted. Publishing a verdict nobody
> is told to act on is the status quo RM27 was filed about; this paragraph is the difference.
- **`layer` decides what taints.** Only `annotation` — the module's own authored tables, where curated
  prose is embedded — carries a derivative-work obligation. A source consulted purely for a coordinate
  contributed a fact that Ensembl reports identically, so it is recorded without marking the module.
  `sources.taints_commercial_use(row)` is the shared predicate, so the compiler's gate and the manifest
  summary cannot drift apart.
- **The licence travels as data, not as a lookup table.** The enricher reads it from the bytes it
  downloaded where a source ships one, and pins it with `license_sha256`. A source→licence map in the
  compiler would be an un-injected reference (Principle 2) and would go stale — both halves of one did,
  inside a single release.

## The verification attestation (0.6) — `verification.json`

A downloaded manifest is detailed about how rs-numbers were *resolved* and, until 0.6, silent about
whether any claim was ever *checked*. A module whose clinical calls were cross-checked against ClinVar
and one where the check never ran shipped **identical** manifests — not through an oversight in some
path, but because no field existed that could differ. `verification.json` is the field, one layer down
from the fix 0.5.2 made on `EnrichmentResult` (S4: an empty conflict list says both "compared
everything" and "never compared"). The layer that outlives the run had inherited none of it.

**Shape.** `manifest.VerificationDoc` — an attestation over `VerificationRecord`s, one per check:
`check` (`VALID_VERIFICATION_CHECKS`), `subjects`, `findings`, `skipped?`
(`VALID_VERIFICATION_SKIPS`), `detail?`, `source?`, `release?`, `checked_at?`. Facts:
`check`/`subjects`/`findings`/`skipped`/`source`/`release`; prose and the timestamp are out, as
everywhere else. The compiler confirms it and stamps `manifest.verification`.

- **A JSON document, not a fifth fact CSV, and the reason is structural.** The object has two levels —
  one attestation over many records — and a CSV expresses that only with a non-data service row (the
  shape RM36 rejected) or by repeating the attestation on every row, where two rows can then disagree
  about a per-run fact. `provenance.json` is the precedent for exactly this shape. It also keeps the
  attestation out of the family whose **human-overridability is a designed feature**: a curator
  editing `frequencies.csv` is doing the intended thing, while editing an attestation is writing a
  claim nobody put — the case the 0.6 charter amendment says "wants a mechanism rather than a
  convention".
- **Two counts, never a boolean.** `subjects=0` with no `skipped` means the check ran and had nothing
  in scope; a `skipped` key means it did not run. Those are different statements and cannot share a
  value. `vrs_alleles`/`vrs_alleles_identified` is the precedent.
- **Both vocabularies are closed, and fixed for the major.** Free-string check names would recreate
  RM44 one level down — one spelling from the enricher, another from a registry, a substring match
  from a consumer. Skip reasons are closed for a second reason: backfill triage branches on *why*, so
  prose there relocates the substring matching rather than ending it. The human sentence rides in
  `detail`, **beside** the key.
- **The binding covers the AUTHORED bytes only** (`compiler.authored_input_entries` — `module_spec.yaml`,
  `variants.csv`, `studies.csv`, the table kinds). Every check compares something a human wrote, so
  those are what the claim is about; the derived sidecars carry a `fetched_at` per row and binding to
  them would perish the attestation on a re-enrichment that changed nothing anyone claimed. The cost is
  real and stated rather than hidden: re-running the enricher against a fresher ClinVar leaves the
  attestation matching, so read **currency off each record's `release`**, never off the binding.
- **The proof-of-work is one per document per run, ~0.7s at 20 bits, and the nonce is the smallest one
  counting up from zero.** Smallest, never random: a random nonce gives the file different bytes every
  run for the same content. Per row or per check it would turn a ClinVar-scale build into days.
- **A stale or non-matching attestation warns and the block is DROPPED**; the compile succeeds and the
  manifest says nothing, which is the correct reading. Making a mismatch fatal was considered and
  rejected: the goal is that a stale record never becomes a published *claim*, not that it be
  impossible to write while editing.
- **`reverse_module` does not re-emit it**, and must not. Reverse rebuilds a spec from the artifact,
  where the document is not — the same structural reason `rsid_alternates` is unrecoverable. A
  reversed module carries no block, which is the honest *says nothing*; re-attesting means re-running
  the checks.

**Nothing in `manifest.verification` is trusted, and the block's every field description says so.**
`compiled_by` has carried that warning for one field since the beginning; here it has to be on all of
them. A **forged pass is worse than silence** — a consumer that reads "the clinical calls were
cross-checked" off a manifest it did not produce, and believes it, is worse off than one that reads
nothing at all. The binding hash and the proof-of-work do not change this: they defend against a
**stale** record on an honestly-produced module, which is the accidental case, and nothing here is
built to resist a deliberate one. A holder of the module's own bytes can confirm the block by
recomputing `module_binding(authored_input_entries(spec_dir))` and comparing it with
`verification.module_hash`; a holder of only the manifest cannot, and should treat the block as a
claim by whoever `producer` names. The real guarantee in this format is `manifest.signature`, a
detached Ed25519 signature over `artifact.digest` made by a party the client pins.

## The resolution table (0.5, **provisional**)

`resolution.ResolutionRow` → `resolution.csv` — persisted, source-independent rsid↔coordinate facts the
compiler consumes *instead of* querying any reference, so the compiler owns no Ensembl/DuckDB convention.
Produced by [`just-dna-enricher`](ENRICHER.md); a human may hand-author or edit it.

**It is a build-time artifact, and it gets no parquet — deliberately.** Every other table here is either
authored input or a published fact table with a parquet beside it; this one is neither. Its only two
consumers are the compiler, which reads it to resolve a key, and the enricher's own update run, which
merges into it. Promoting it to a published table would make it a consumer contract it was never designed
to be — its provenance columns are explicitly outside the fact set, `reverse_module` cannot reconstruct
half of them, and a downstream reader keying on it would be reading the *lookup* rather than the *answer*,
which is materialized into `weights.parquet` and the positional tables where it belongs. This is written
down here because "publish it as a parquet" is the first repair anyone proposes on finding a table that
does not carry a coordinate, and it is the wrong one — RM43 (0.6) is the right one, and it is what makes
"materialized into the positional tables where it belongs" true rather than aspirational.

- **Join key:** `variant_key` (the frozen authored identity). **Facts** (feed `resolution_signature`):
  `rsid?`, `chrom?`, `start? (ge=0)`, `ref?`, `alts?`, `genome_build="GRCh38"` (the RM15 forward hook),
  `locus_index=0` (0 for 1:1; `0..N-1` for a one-to-many rsid expansion). **Provenance** (excluded from
  the signature): `source?`, `authority?`, `status?` (`VALID_RESOLUTION_STATUS = {resolved, not_found, ambiguous}`;
  `not_found` = "looked, genuinely absent"; `ambiguous` = a reverse position→rsid back-fill hit several
  rsids for the exact allele — a dbSNP merge), `rsid_alternates?` (the full candidate list when
  `ambiguous`; `rsid` holds the deterministic pick), `rsid_current?` / `rsid_status?`
  (`VALID_RSID_STATUS = {live, merged, absent, withdrawn}` — what dbSNP says about `rsid` today),
  `fetched_at?`.
- **`source` names the link; `authority` names the licensed source it speaks for (RM33).** `source` is
  `ensembl-rest`/`ensembl-graphql`/`cache`/`clinvar`/`gnomad`/`authored`/`reversed`/`manual` — *which link
  answered*, which matters for diagnosing a compile and has no other home. `authority` is the thing
  `sources.csv.source` joins on (`ensembl`, `clinvar`, `gnomad`), and it is **empty** where there is no
  external source to name: `authored` is the module's own bytes, `reversed` is the compiler, `manual` is a
  human. Before the split, the compiler compared the link against `sources.csv` by string and every
  enriched module was told `ensembl-rest` has no terms recorded. The link→authority map lives in the
  **enricher**, the only tier permitted a source convention (P2) — never in the compiler.
  Every *other* fact table's `source` already names the licensed source directly, so only this table
  needs the second column; where a route needs distinguishing there, `dataset` does it.
- **`rsid_current`/`rsid_status` are provenance, and the exclusion is load-bearing.** They describe
  *time-varying external state*: inside the fact set, `resolution_signature` would change the day dbSNP
  merged something, with no change to the module, and would stop being reproducible from the module's
  own content. The value is also **recorded, never substituted** — `weights.parquet` carries `rsid` as
  identity, so writing a merged-into label into the artifact would migrate `variant_key` by network
  lookup and break the round-trip fixed point (see ROADMAP § *the stale-identifier collision*).
  `absent` deliberately covers both "never assigned" and "withdrawn" *as an automated verdict*: no
  live endpoint separates them (`rs11273140`, retracted, and `rs2000000000`, never assigned, return
  byte-identical responses), so `identifiers.classify_rsid` reports `absent` and names both readings
  rather than guessing. **`withdrawn` is nevertheless a real fourth member**, and the distinction
  between "nothing produces it today" and "nothing could" is the whole reason it is one: a curator who
  has established a retraction can record it and have the tooling honour it, and a future source that
  can tell the two apart starts emitting it without a vocabulary change — which Principle 3 would
  otherwise make a one-way door. Its severity is deliberately not `absent`'s. A merged or absent rsID
  leaves the annotation intact (dated, or unserved); a retracted variant may leave it describing
  nothing, so `withdrawn` is the one resolution finding that is **fatal in `best_effort` too**.
- **Reverse emits facts and drops provenance, by design.** `reverse_module` rebuilds this table from
  `weights.parquet`, which holds no provenance at all — it resets `source` to `reversed`, `status` to
  `resolved`, blanks `fetched_at`, and cannot emit `authority`/`rsid_alternates`/`rsid_current`/`rsid_status`
  because those columns are kept out of the artifact on purpose. (For `authority` there is a second reason
  and it is not a limitation: a reversed table's facts came out of parquet, so no licensed source answered
  for them.) Recovering them after a round-trip
  means re-running the enricher, which is where a statement about a reference at a moment belongs.
- It is a **standalone `BaseModel`** (not `AuthoredModel`) with `extra="forbid"` — a resolution fact is
  not an annotation and must not inherit VariantRow's annotation validators; it reuses only the shared
  `rsid` grammar and the `status` vocabulary.
- **Cross-references (0.5, outside the fact set):** `vrs_id?` (`ga4gh:VA.…`), `vrs_spec?` (`"2.0"`),
  `caid?` (`CA\d+`), each with a grammar validator. Three registries, three columns — never one
  overloaded `identifier` field (Principle 5). They stay out of `RESOLUTION_FACT_FIELDS` so adding them
  moves no existing `resolution_signature`; the identity they carry reaches the artifact through
  `variant_key` instead, so the fact set does not need them.
- **`RESOLUTION_FACT_FIELDS`** names the fact columns; `integrity.resolution_signature` hashes only
  those (provenance deliberately excluded), so a human-filled and an Ensembl-filled table with identical
  facts hash equal.

> **Not yet frozen.** `resolution.csv` is **new in unreleased 0.5** — no 0.4 module carries it, so the
> additive-within-a-major / digest-freeze obligations (Principles 3/8) have **not** engaged yet. Its
> shape (columns, keying, the `status` vocabulary, how expansion is encoded) is **free to be refactored
> wholesale** during 0.5 development, and is expected to take a few run-overs before it settles. Treat
> everything in this section as provisional until 0.5 ships. The stable parts of the contract
> (`variant_key` identity, `artifact.digest`, `content_signature`) are unaffected by resolution's shape.

## Identity & integrity

Nine SHA-256 hashes (`sha256:` hex prefix), each a different job — see [COMPILER.md](COMPILER.md) and
the CONSTITUTION for how they compose. (Two are structural, `artifact_digest` and `content_signature`;
the other seven are the one-per-injected-table family below — it was five until 0.6 added the two
derived tables, and the count is stated here rather than in prose precisely so it cannot go stale
silently.)

| Hash (`integrity.py`) | Over | Order | Reference-dependent | Purpose |
|---|---|---|---|---|
| `artifact_digest(files)` | compiled parquet file set (Merkle root of `{name,sha256,size}`) | row order preserved in each file | yes (GRCh38 coords) | the version's immutable **byte** identity — *these bytes, from this compiler* (P4). Not its content identity; that is the row below, and conflating the two is what sends a reader hunting a content change that did not happen |
| `content_signature(tables, genome_build)` | raw authored rows, `model_dump(mode="json", exclude_none=True)`, plus `genome_build` when non-default | order-independent (sorted) | no (pre-resolution) | content-dedup key surviving recompile/metadata-strip. **Reference-independent, not build-independent** (RM36): identical rows on two assemblies are two different loci, so the declared build is content. Omitting the default keeps every GRCh38 module's signature unchanged. |
| `resolution_signature(rows)` | resolution **facts** only (`RESOLUTION_FACT_FIELDS`) | order-independent | n/a | pins the resolved facts; producer-independent |
| `frequency_signature(rows)` | frequency **facts** (`FREQUENCY_FACT_FIELDS`) | order-independent | n/a | pins the allele-frequency table |
| `gene_metrics_signature(rows)` | gene-constraint **facts** (`GENE_METRICS_FACT_FIELDS`) | order-independent | n/a | pins the gene-constraint table |
| `literature_signature(rows)` | citation **facts** (`LITERATURE_FACT_FIELDS`) | order-independent | n/a | pins which articles the module cites |
| `gene_validity_signature(rows)` | gene–disease **facts** (`GENE_VALIDITY_FACT_FIELDS`) | order-independent | n/a | pins which curated assertions the module carries, at which strength |
| `clinical_assertion_signature(rows)` | archive-record **facts** (`CLINICAL_ASSERTION_FACT_FIELDS`) | order-independent | n/a | pins the clinical calls **and the review behind them** |
| `source_signature(rows)` | licensing **facts** (`SOURCE_FACT_FIELDS`) | order-independent | n/a | pins what the module was built from, and on what terms |

The last seven share one body, `fact_signature(rows, fact_fields)` — every injected table under one
hashing discipline, so the rule cannot drift between them as more sidecars land. What differs is only
each table's fact set, and the exclusions are where the thinking is: provenance is always out, and so is
any column describing the *outside world's* current state rather than the module's content
(`is_open_access`, `rsid_current`/`rsid_status`). A signature that moved because dbSNP merged an rsID or
an embargo lifted would no longer be reproducible from the module alone.

Reproducibility identity is the triple **`(content_signature, resolution_signature, compiler_version)
⟹ artifact.digest`** — a holder of the two small CSVs reproduces the artifact byte-for-byte, offline.

**A moved `artifact.digest` beside an unmoved `content_signature` is the intended reading of a
provenance-only change, not a puzzle** (CONSUMER_SUGGESTIONS_HISTORY § S7, where a registry spent an
afternoon looking for the content change that had not happened). `fetched_at` is the usual one: it is
outside every fact set, so no signature sees it, but it is a column in `sources.parquet`, so the Merkle
root over the shipped files does — correctly, because those bytes differ. **Key a dedup or
find-by-hash surface on `content_signature`, and a "these exact bytes" claim on `artifact.digest`.**
`just-dna-compiler signature <spec>` computes the former without compiling, which is also what makes it
the usable change-signal in CI. Blanking a column before hashing would not be a tidier digest, it would
be an unverifiable one — `verify_manifest` re-hashes each `artifact.files[]` entry straight from disk
before recomputing the root, so a digest over anything but the bytes on disk cannot be checked by the
consumer it is for.

- **Signing (`signing.py` / `integrity.verify_signature`).** Ed25519 over the `artifact.digest` *string*.
  Private keys are PKCS#8 PEM (`generate_private_key_pem`, `sign_digest`); the public key travels as raw
  base64 in `manifest.signature`. `verify_manifest(public_key=...)` enforces a pinned key.
- **`verify_manifest(...)`** — the verify-then-install path (SPEC §5): re-hash `artifact.files[]`,
  recompute `artifact_digest`, check trust (`compiled_by == "marketplace-server"`), optionally re-hash
  `inputs`/`logs`/`provenance`/`logo`/`readme`/`derived`, and verify the signature. It does **not**
  re-check `content_signature`/`resolution_signature` (sibling identities, out of the digest).
- **`identity.py`** — `NAME_PATTERN` `^[a-z][a-z0-9_]*$`, `NAMESPACE_PATTERN` `^[a-z0-9]+(-[a-z0-9]+)*$`,
  the ordered `Version` dataclass, `canonical_id(namespace, name, version)` → `namespace/name@version`,
  and the legacy `vN → N.0.0` coercion.

## The output half — manifest models

`manifest.py` holds the `manifest.json` contract. `ModuleManifest` is the root: `manifest_version` /
`schema_version` (both `"1.0"`), `identity`, `display`, `genome_build`, curator/method/license/owner,
`authors` + `authorship` (`Contribution`: `who`/`role`/`kind`), timestamps, `stats`, `compilation`,
`inputs`, `content_signature?`, `artifact`, `logs`, `derived`, `provenance?`, `verification?`,
`panel?`, `logo?`, `readme?`, `signature?`, and
one block per derived-fact sidecar the module carries — `frequency?`, `gene_metrics?`,
`gene_validity?`, `clinical_assertions?`, `literature?`, `sources?`. Each carries `signature` /
`sources` / `row_count` plus whatever its own table makes answerable: `datasets` on the four that
have releases to name (gnomAD, ClinGen/GenCC and ClinVar all ship them; PubMed and the licence table
do not), `populations`/`variant_count` on `frequency`, `genes` on `gene_metrics`,
`genes`/`diseases`/`classifications`/`submitters` on `gene_validity`, the star range plus
`unrated_count`/`not_found_count` on `clinical_assertions`, the quote and open-access counters on
`literature`, and the licence roll-up on `sources` (`licenses`, `attributions`, the per-layer facets
and the derived `commercial_use` / `redistribution`). All six are out of `artifact.digest`.

`verification?` (RM45) is the seventh block and the one that is **not** a sidecar summary: it carries
no `row_count` and no `sources` union, because its records are few and are embedded whole rather than
left in the table. It has its own section above, including the reason nothing in it is trusted.

`ClinicalAssertions` publishes `min_review_stars` / `max_review_stars` as **two counts and not an
average**, for the reason `vrs_alleles` sits beside `vrs_alleles_identified`: an average is a number
describing no record, while the pair tells a catalog that a module is mixing a practice guideline with
a single submitter. Both are `None` — never `0` — when no record states a review status at all, and
`unrated_count` publishes the size of that gap, because a range over an unstated fraction is not
something anything can filter on.

The 0.5 additions on **`Compilation`** are two groups, and they answer different questions.
Resolution *policy and outcome*: `resolution_mode?` (`strict`/`best_effort`), `fully_resolved`
(outcome — orthogonal axis, P5), `resolution_subjects` (0.6), `resolution_signature?`,
`resolution_sources`. Allele-identity *coverage*: `vrs_alleles` and `vrs_alleles_identified`, the
counts `_vrs_coverage_warnings` reports, so a consumer can read how completely the identity scheme
names this module's alleles instead of inferring it from the absence of warnings. "Complete" is
`identified == alleles`, derived rather than stored twice.

**Read `fully_resolved` with `resolution_subjects` or you will trust the wrong modules (RM44, 0.6).**
The flag is `all(...)` over the module's variant rows, so on a module with no `variants.csv` it is
`all()` over an empty list — **vacuously `true`**, and the rule
`resolution_mode == "strict" or fully_resolved` then grants a verdict to a module that resolves
nothing. A registry followed exactly that rule and had to migrate a stored projection. The safe rule
is **`resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)`**; a `0` there
means nothing was attempted, which is not the same as nothing achieved. The count is taken after the
one-to-many rsID expansion, because that is the list the flag iterates. `Stats.weights_rows` happens
to equal it today — do not key on that: `Stats` is card/detail display facets and promises no such
relationship.

**`derived` is a BYTE hash of the sidecar CSVs, and it is not their identity.** The derived-fact
tables — `resolution.csv` plus `frequencies`/`gene_metrics`/`literature`/`sources` — are deliberately
excluded from `inputs[]`, because they are multi-producer (the enricher, a human override and
`reverse_module` all legitimately emit different bytes for the same content) and are therefore hashed by
**facts**: `compilation.resolution_signature` and each sidecar block's own `signature`. That left them
attested by no *byte* hash at all, so a registry serving only what the manifest attests could not hand
back the table that produced a parquet, and a consumer could not diff the two (S26). `derived[]` fills
that gap and nothing more. It is out of `artifact.digest` and `content_signature`, so re-running
enrichment against a fresher gnomAD mints no new content identity; entries are hashed **where the files
live, beside the spec**, and not copied into the module dir, since each is its own parquet's content in
another encoding. An absent entry is skipped by `verify_manifest(check_derived=True)` rather than
failing — `logs`' rule, not `inputs`' — because a consumer holding only the artifact has none of them.
**Two hashes over one file answering two questions: read the fact hash for identity and this one for
transport, never the reverse**, or a legitimate re-emission looks like tampering.

**`logo?` and `readme?` are the two *shipped assets*, and both are outside both identities.** Each is
a hashed `FileEntry` naming a file the compiler copies into the module dir from beside the spec —
`logo.{png,jpg,jpeg}`, and the first of `README_CANDIDATES` (`README.md`, then the other stems and
`md`/`rst`/`txt` in a fixed order, so two readmes on disk cannot resolve by luck). Neither is in
`artifact.files`, so neither moves `artifact.digest`; neither is authored data, so neither moves
`content_signature`. That is what makes correcting a caveat a **patch** rather than a new version, and
it is why the alternative of listing `README.md` in `artifact.files` was rejected: on an immutable
registry a fixed typo would cost a version number and the corrected module would then collide with its
own predecessor under a name-independent content-dedup check.

The field exists because *attestation is what makes a file usable downstream* (S25). A registry that
declines to serve files whose hash nothing records — the right policy — cannot serve a readme the
manifest does not list, and neither can an installer, a mirror or a second registry; keeping the prose
in one catalog's own database makes that catalog the source of truth for something no manifest
consumer can reach. Inlining the text into `display` was rejected too: a readme is unbounded (a small
module's can outweigh its data) while `display` is inlined into every card a catalog serves.
`verify_manifest(check_readme=True)` re-hashes it, and `just-dna-compiler verify --check-readme` is
the CLI surface.

`Display` is the base of `spec.ModuleInfo`; `GenePanelSpec` and `Contribution` are authored via
`ModuleSpecConfig`. Everything else in `manifest.py` is manifest-only, never authored into a CSV.

**`GenePanelSpec` is deprecated in 0.6 and removed at 1.0 (RM4).** The compile-time materialization it
was the interface for is dropped rather than deferred — the compiler must not create rows no curator
wrote — and drafting (`just-dna-enricher draft-panel`) writes those rows as authored bytes instead. Its
last machine reader was the enricher's ClinVar `clin_sig` cross-check, which now reads the drafted-from
release out of the `dataset` column of the module's licence row, written by the drafting pass itself: a
provenance claim belongs with the tool that copied the data, not in a block an author has to keep in
step by hand. A module carrying `panel:` still validates and still compiles, with a deprecation warning,
and deleting the block moves neither `artifact.digest` nor `content_signature`.

## Generated authoring reference & aggregation

- **`reference.authoring_reference()` / `json_schemas()`** (RM8) — the field-lists, vocabularies,
  reserved names, and recommended palette generated *from the live models*, so an MCP server / authoring
  agent renders the current schema instead of a hand-maintained summary that drifts. Compiler-managed
  columns are excluded via the fields' own `COMPILER_MANAGED` marker (`base.authored_field_names`),
  never a name list — the list this replaced named `variant_key` and never learned about
  `authored_ident`.

  **Reachable from the CLI since 0.5: `just-dna-compiler reference [--summary|--schemas]`.** This
  package ships no CLI of its own (Typer would breach the pydantic-plus-cryptography floor), so the
  consumer that most needs the reference had to import this module and write Python. Same reasoning
  put `verify`, `sign` and now `keygen` on the compiler's command list.

  Each field carries **`category`** (`required` / `defaulted` / `optional`) beside pydantic's two-way
  `required`. The middle one is the trap: `MeasureBinRow.measure_kind` and `unresolved` have defaults
  so `is_required()` is `False`, but `load_csv_rows` turns an empty cell into `None` and keeps the
  key, so the model receives `None` instead of its default and fails on type. `just_dna_compiler.draft`
  was fixed to the three-way split; this surface was not, until both were pointed at one definition in
  **`base.field_category`** — which lives here because the format tier is the only one both can import
  from. `required` stays beside it: it is insufficient on its own, not wrong, and removing a published
  key would break consumers.

  **The three-way field-ownership boundary is machine-readable here, which is what `extra="forbid"`
  made necessary** (CONSUMER_SUGGESTIONS § S2). A key is authored, compiler-stamped, or
  registry-stamped, and each lands in a different place in the same payload: `models` lists **only**
  the authored fields; a compiler-managed one is excluded from `models` and present in
  `json_schemas()` (the honest complete materialized shape); and **`registry_stamped_keys`** names the
  `module:` keys a publishing registry fills, mapped to why each is not authored
  (`normalize.IDENTITY_AUTHORITY_KEYS` / `IDENTITY_AUTHORITY_REASONS`). `module.version` is
  deliberately in the first group, not the third — it is a genuine advisory authored field, coerced to
  SemVer (RM17) rather than stripped.

  There is deliberately **no enumeration of "what 0.4 newly rejects"**, because the newly-rejected set
  is the *complement* of a finite set rather than a finite set: pre-0.4 dropped every unknown key
  silently, so "what moved from warn to reject" is every name a model does not declare. What is
  enumerable is the other side — **every authored surface closes its namespace**: the `module_spec.yaml`
  blocks (`ModuleSpecConfig` top level, `ModuleInfo`, `Defaults`, `GenePanelSpec` for `panel:`,
  `Contribution` for an `authorship:` entry) and every row model, whether it inherits `extra="forbid"`
  from `AuthoredModel` or sets it directly as the generated sidecars do (`ResolutionRow`, `SourceRow`,
  `FrequencyRow`, `GeneMetricsRow`, `LiteratureRow`). The legal key list for each is what this payload
  generates, so it cannot drift from the models the way a prose migration table would.
- **`signing.generate_private_key_pem()` / `public_key_b64_from_pem()`** — key bootstrap, surfaced as
  `just-dna-compiler keygen`. Unencrypted PKCS#8, which is what `sign_digest` reads; this bootstraps a
  key rather than managing one.
- **`aggregate.aggregate_logs` / `aggregate_provenance`** — the deduplicated union of logs/provenance
  across a set of version manifests ("v3 provenance = v1+v2+v3"), first-occurrence order.

## Testing

`uv run pytest schema/tests` (part of the workspace suite). Real fixtures, runtime-computed expected
values, round-trip/idempotency proven (not asserted). Vocabularies may be hardcoded (domain constants);
row/unique counts read off a data dump may not.
