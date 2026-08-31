# `just-dna-compiler` — the transform tier

The package reference for **`just-dna-compiler`**: the reference compiler that turns a validated spec
directory into a multi-parquet artifact + `manifest.json`, and reverses it back. Since 0.5 it is
**pure-Python and duckdb-free** — its runtime deps are `just-dna-format`, `polars`, `pyyaml`, `typer`.
It **never fetches** (Principle 2): resolution is consumed from an injected, source-independent
`resolution.csv`; the pre-0.5 DuckDB reference path moved to [`just-dna-enricher`](ENRICHER.md) and is
reachable only through a deprecated, guarded shim (removed at 1.0).

The compiler adopts the schema with a **C++-standard-style feature-coverage** stance — not
all-or-nothing conformance but a per-feature table (below). As of 0.4 the validator is complete, the
upgrade derivation ships, the artifact round-trips losslessly including phase, and all nine 0.4 table
kinds materialize with enforced table-level coherence.

> Companion docs: **[SCHEMAS.md](SCHEMAS.md)** (the models it compiles), **[ENRICHER.md](ENRICHER.md)**
> (what produces `resolution.csv`), **[CONSTITUTION.md](CONSTITUTION.md)** (the invariants).

## Read beside this: the 2026-08-18 code-first re-derivation

**A second reading of this tier, written from the code alone on 2026-08-18, is in
[audit/COMPILER_FROM_CODE.md](audit/COMPILER_FROM_CODE.md)** — the 17-step pipeline, per-parquet column
lists, and a validation table with validate/compile/severity columns. It is the instrument that found
RM93 and RM94, both fixed in 0.6.1 — so the parity this document asserts is now a property of the
binaries too. Evidence, not contract: this document is the maintained one.

## Public API

Import from `just_dna_compiler.compiler`.

- **`validate_spec(spec_dir, authority_keys=None, *, strict=False) -> ValidationResult`** — validate a
  spec dir without producing output; strips inject-only authority keys pre-validation (dropped keys →
  `.info`), runs `validate_bins` and the duplicate/identity checks, populates `.stats`. `strict` grades
  the mode-ladder findings at the severity a `strict` compile would, so a caller can *report* what
  strict would refuse without building anything — note it cannot see the unresolved-position gate,
  which lives in `compile_module` and needs a resolution table.
- **`content_signature(spec_dir) -> str`** — the stable, name-/Ensembl-independent content identity over
  the raw authored data CSVs (no compile, no resolution); raises `ValueError` if a present data CSV is
  invalid. See [SCHEMAS.md § identity & integrity](SCHEMAS.md#identity--integrity).
  **Which CSVs, exactly:** `variants.csv`, `studies.csv`, and any present table kind — the *authored*
  roster. The licensing table (`sources.csv` / `licensing.csv`) is **outside it**: it is hashed by
  `integrity.source_signature` instead, so neither its presence nor an edit to a `notice` cell in it
  moves this digest. That is correct — the licence layer carries its own identity — and it is stated
  because it is the one authored, hand-editable table a licence audit sends an author looking for (S53).
- **`load_spec(path, *, authority_keys=None) -> ModuleSpecConfig`** — the public route to a parsed
  `module_spec.yaml`, raising `SpecError` (a `ValueError`) on anything wrong. Sibling of
  `just_dna_format.read_manifest` / `read_verification`: one loader per file a module carries, same
  raise-don't-return contract. It exists because the **model** was public from the start and the only
  thing producing one was `_load_yaml`, so a consumer wanting `weighting:`, `authorship:` or `license`
  hand-parsed the file, lost the authority-key handling and every diagnosis, and carried PyYAML purely
  to work around a private symbol — the enricher itself was doing the same thing across the tier
  boundary (S74). `_load_yaml` keeps its `(config, errors, dropped)` tuple for `validate_spec`, which
  accumulates diagnoses from a dozen sources; that difference is why both exist. It is in **this** tier
  rather than the format one because parsing YAML needs `pyyaml`, and the format tier is
  `pydantic` + `cryptography` by charter. **It does not fold `defaults:`** — that is per row and is
  `spec_tables` below; the pairing is `load_spec` for the yaml's blocks, `spec_tables` for the rows.
- **`spec_tables(spec_dir) -> tuple[dict[str, list[BaseModel]], str]`** — the parsed, **defaults-folded**
  rows `content_signature` hashes, plus the declared build. `content_signature` is exactly this plus the
  hash, so anything finer than a whole-module digest — per-table, per-row, *what moved between two
  versions* — builds on these rows instead of restating the roster and the fold (S53). Same
  `ValueError`-on-invalid-CSV contract. **The fold is why this returns the finished mapping rather than
  exporting the pieces:** a caller hashing `load_csv_rows` output directly gets a *different* digest for
  the same module, because a value written once under `defaults:` and the same value written on every row
  are one content (RM37) and only this path folds them — measured on `hfe_hemochromatosis`, the raw build
  reports twelve changed rows where there are none.
- **`compile_module(spec_dir, output_dir, compression="zstd", resolve_with_ensembl=True,
  ensembl_cache=None, compiled_by=None, ensembl_reference=None, log_files=None, provenance_file=None,
  logo_file=None, readme_file=None, authority_keys=None, strict=False, ba1_threshold=0.05)
  -> CompilationResult`** —
  compile to parquet + `manifest.json`. `ensembl_cache` is **deprecated (removed at 1.0)** — see the
  precedence block. `resolve_with_ensembl` is not deprecated and is misnamed: since 0.5 it is the
  master switch for consuming `resolution.csv` at all, so turning it off ignores an injected table
  and has nothing to do with Ensembl. `ba1_threshold` is the ACMG BA1 allele-frequency cutoff — a
  parameter rather than a constant, because the right value is disease-specific.
- **`reverse_module(parquet_dir, output_dir, module_name=None, title=None, description=None,
  report_title=None, icon="database", color="#6435c9", version=None, write_resolution=True,
  genome_build=None) -> Path`** — reverse a compiled artifact back to the authored DSL.
  `genome_build=None` reads it from the artifact's own `manifest.json` (it lives in no parquet
  column); pass it only for a bare parquet directory carrying no manifest.

- **`load_csv_rows(path, row_model, file_label, genome_build=DEFAULT_GENOME_BUILD) -> (rows, errors,
  warnings)`** — the authored-CSV loader, **public since 0.5.1** (RM41). It was `_load_csv_rows`, and it
  was public in practice: `just-dna-enricher` consumes it across a package boundary in a dozen places,
  and a consumer wiring the pipeline server-side had the choice of a private symbol or a
  re-implementation. Re-implementing is a trap, not a chore — it is not `csv.DictReader` plus
  `Model(**row)`, because **an empty cell becomes `None` with the key kept** (so a defaulted-but-not-
  `Optional` field like `MeasureBinRow.measure_kind` receives `None` rather than its default and fails
  on *type*) and **`genome_build` is told to each row** rather than read from it. `_load_csv_rows`
  remains as an alias, so nothing that imported it breaks.
- **`load_spec_variants(spec_dir) -> (variants, errors, warnings)`** — a spec directory's
  `variants.csv`, loaded with the build the module declares **and re-stamped for it**. Three steps, not
  one: read `genome_build` out of `module_spec.yaml`, inject it into every row, then `_restamp_for_build`
  — because `VariantRow._freeze_identity` runs at construction, where the yaml is not in scope, so a
  loader that skips either step mints GRCh38 identities for a GRCh37 module. Missing or unreadable yaml
  falls back to `DEFAULT_GENOME_BUILD`, matching what compiling that directory would assume; this is a
  read-only check helper, unlike the enrichment path, which refuses rather than choose a build for a
  module whose declaration cannot be read (it writes facts back). Added for the two enricher checks that
  take rows rather than a `spec_dir` — `verify_acmg_sf` and `check_identifiers`, which now accept both.

- **`load_citing_rows(spec_dir) -> dict[str, list]`** and **`table_citations(rows_by_csv) ->
  list[str]`** — every table kind beside a spec whose rows **cite** (a model declaring a `pmid`:
  the four binning kinds since RM47, `pharm_variants.csv` since RM132), and the digit-only PMIDs they
  name, de-duplicated in first-occurrence order. Public for the RM40/RM41 reason: the enricher's
  literature pass has to check these pointers alongside `studies.csv`, and its alternatives were a
  private import or a second roster that goes stale the next time a model declares the column. The set
  is derived from the models, so a new citing kind is read by both tiers with no edit to either. Row
  errors **raise** — a pass reading citations out of a table it could not parse would silently
  under-report; a caller wanting the per-row diagnosis has `validate_spec`.
  **`load_binning_rows`/`binning_citations`** are the narrower pair, unchanged: they answer over the
  binning kinds only, because a caller asking for those is asking about thresholds rather than about
  the citations a module makes.

`models.py`: **`ValidationResult`** (`valid`, `errors`, `warnings`, `info`, `stats`) — the `.stats` key
contract is `variant_count`/`unique_rsids`/`gene_count`/`genes`/`categories`/`study_count`/
`clinvar_count`/`pathogenic_count`/`benign_count`/`module_name`. **`CompilationResult`** (`success`,
`output_dir`, `errors`, `warnings`, `stats`, `manifest` — the emitted `ModuleManifest`, `None` on failure).

## What the compiler can and cannot validate

The compiler sits to the enricher roughly as an assembler-plus-linker sits to a source tree: it
consumes an authored schema plus injected resolution facts, and its guarantee is that the result is
**well-formed and self-consistent**, not that it is **true**. A C++ compiler type-checks a program and
still ships your off-by-one; a linker proves every symbol resolves and says nothing about what the
functions do. The same boundary applies here, and it is worth stating plainly rather than leaving a
reader to infer that "it compiled" means "it is right".

There is also a **trust boundary**. `resolution.csv` and the derived-fact sidecars — `frequencies.csv`,
`gene_metrics.csv`, `literature.csv`, `gene_validity.csv`, `clinical_assertions.csv` — are consumed as
fact. The compiler can re-derive the parts that are *self-verifying* and cross-examine the
parts that are *redundant*, but everything sourced — which coordinate, which rsID, which allele
frequency — is taken on trust from whoever produced it. That trust is the price of Principle 2: a tier
that never fetches cannot independently confirm a fetched fact.

### Three things it can check, in increasing strength

**1. Formal conformance** — complete within its domain, like type-checking. Columns, types, closed
vocabularies (`extra="forbid"` plus the reserved-namespace diagnosis), identifier grammars (rsid, DOI,
PMID, CURIE, `ga4gh:VA.`, `CA\d+`), value bounds, finite floats (no `NaN`), required-ness, **at most one**
`unresolved` bin sentinel per bin-group key, bin overlap/gap, duplicate natural keys, duplicate
`(variant_key, genotype)`. If a module violates one of these it is malformed, full stop.

Note the one-sidedness of the sentinel rule, because it reads like a completeness check and is not one:
`_validate_table_kind` counts sentinels per group and refuses a **second** one, and nothing on the
compile path refuses **zero**. A binning table carrying no sentinel at all compiles green under
`--strict` — measured. The missing-sentinel finding lives on the authoring surface only
(`hints._check_bins` warns `no unresolved sentinel row`), and it is *table*-level, so a table whose rows
fragment into several bin groups can satisfy it while leaving most groups with no sentinel.

**2. Validate-by-redundancy** — where two independently-authored things must agree, disagreement is
detectable without any reference. This is where most real authoring bugs are caught:

| Check | Redundancy exploited | Severity |
|---|---|---|
| rsid ↔ coordinate | the pair co-identifies one variant | warning |
| inconsistent position for one key | one key, one place | error |
| inconsistent `ref` for one key | the reference base is a single fact | error |
| genotype alleles ⊆ `{ref} ∪ alts` | a genotype names alleles the locus has | warning / error in `strict` |
| `effect_allele ∈ {ref} ∪ alts` | the effect allele is one of them too | warning / error in `strict` |
| `clin_sig` pathogenic + high AF | ACMG BA1: common alleles are not pathogenic | warning |
| a citation PubMed has no record of | the enricher already wrote the verdict down | warning |
| `allele_count ≤ allele_number` | a count cannot exceed its denominator | error |
| `2 × homozygote_count ≤ allele_count` | each homozygote contributes two alleles | error |
| `faf95 ≤` the group's own AF | a CI lower bound sits below its point estimate | warning |
| `oe_lof_lower ≤ oe_lof ≤ loeuf` | an estimate lies inside its own interval | warning |
| `obs_lof / exp_lof == oe_lof` | the same quantity, stored three ways | warning |
| direction ↔ weight sign | two encodings of one claim | warning |
| `p_value` string ↔ the mantissa/exponent pair | two encodings of one number | warning / error in `strict` |
| MT/Y two-allele genotype | ploidy contradicts the contig | warning |
| study / frequency / gene-metrics orphans | the sidecar describes something the module lacks | warning |
| literature orphans | a citation no study and no citing table row makes — reported, and **left out of the artifact** (the row stays in `literature.csv`) | warning |
| `sources.csv` orphans / undeclared sources | every source a fact table cites has terms recorded, and vice versa | warning |
| star allele used but not defined | `allele_function`/`diplotypes` name it; `haplotypes` defines it | warning |
| **phase-ambiguous diplotypes** (0.5) | two *different* haplotype pairs whose unphased genotype is identical while their conclusions differ | warning |

Four of these deserve their reasoning rather than just their row.

**The phase-ambiguity check is RM28's cis/trans motivation, closed by computation rather than by a
grammar.** Compound heterozygosity is the case that most justified a predicate language, and
`reference_examples/hfe_compound_het/` shows it needs none: a **diplotype is already a statement about
two homologs**, so HFE `C282Y`/`H63D` (in trans, at-risk) and `C282Y-H63D`/`wt` (in cis, a carrier) are
simply two rows. What no table can say is that a consumer without phase **cannot tell them apart** —
they present the identical unphased genotype (rs1800562 G/A, rs1799945 C/G) and disagree about what it
means, and nearly all consumer data is unphased.

That is derivable from tables the compiler already holds, which is what makes it a check rather than a
`requires_phase` column: a column would restate what the data determines and go stale the moment a
haplotype is edited. The signature is, per variant, the **sorted pair** of alleles the two haplotypes
contribute — sorted because that is precisely what losing phase does. An unmentioned variant reads as
the implied reference, and an allele explicitly equal to the row's own `ref` normalizes to the same
sentinel; neither needs the reference *sequence*, only that "unmentioned" means one thing. So it runs
unchanged on a CPIC-drafted table where haplotypes are sparse and `ref` is absent — and correctly finds
nothing there.

Two boundaries. It compares **distinct haplotype pairs**, never distinct rows: the dedup key admits a
row per drug and per `clinical_context` for one pair, and grouping on rows reported 595 ambiguities in
a CYP2C19 module that has none. And it is **closed-world** — it compares the rows a module states, not
the ones it omits, which is why APOE stays quiet despite ε2/ε4 vs ε1/ε3 being the textbook collision:
that module carries no ε1. The neighbouring "used but not defined" warning covers that side.

**The allele-membership checks never escalate to an unconditional error, and the tempting version is
wrong.** An authored `ref`+`alts` contradicting the row's own genotype looks decidable here — but
`ref`/`alts` in `variants.csv` are not necessarily *human*-authored. `reverse_module` writes them, and a
one-to-many rsid reverses into N rows that each carry their own locus's alleles beside the **one**
genotype the author wrote; exactly one of those rows can match. An unconditional error would mean any
module with a one-to-many rsid compiles once and never again — Principle 7's fixed point, broken by a
lint. (Not hypothetical: three variants in `reference_examples/pathogenic_clinvar/` have this shape.)
For the resolved case there is a second reason to stay at a warning: `alts` came from a *source*, and
ClinVar carries only its submitted alleles while Ensembl carries every allele dbSNP knows, so a short
alt list is a gap in the source at least as often as a defect in the module. The comparison is also made
against the **union** of every locus a key resolves to, never per-expanded-row, for the same reason.

**"Exactly one of those rows can match" is a statement about matching, and a reader does more than
match (S33).** The sentence above is right and the expansion is staying, but it was written in the
authoring/validation frame, where an unmatchable row is inert. It is not inert to a consumer *reading*
the artifact: `TA/TA` beside `ref=TA` is a well-formed reference homozygote carrying the module's
conclusion, and a reporting consumer classified 2,579 of them as pathogenic genotypes a subject
carried. Two things came out of that, neither of them a filter. The read-side contract is now stated
where a consumer will meet it — [SCHEMAS § the consumer join contract](SCHEMAS.md#a-row-asserts-something-about-a-locus-genotype-pair--and-one-rsid-can-produce-rows-for-pairs-the-author-never-wrote-06-s33)
— and `manifest.compilation.expanded_keys`/`expanded_rows` publish whether an artifact contains such
rows at all.

**And since RM87 an expanded row says so about itself.** `weights.parquet` carries `locus_index` and
`locus_count`, stamped at the expansion loop, which is the only site that knows a row is a member of
anything — after it the row is ordinary, with a real coordinate, a real reference allele and the
module's own conclusion. `locus_count > 1` is the predicate a consumer applies while holding a single
row; `locus_index` is the 0-based ordinal that lines that row up with its `resolution.csv` row. Four
things about the pair:

- **The ordinal counts within `usable`**, i.e. after `_hostable_loci` dropped any locus that positively
  contradicts the genotype — not within the injected table's own `locus_index`, which `_sorted_loci`
  only *orders* by. Under `strict` a dropped locus is a refusal, so the two coincide there.
- **`locus_count` defaults to `1`, not `0`.** A row that was never expanded genuinely resolves to one
  locus. A zero default would make the predicate read `locus_count > 1 or locus_count == 0`, which is
  the same under-determination `locus_index` alone has and which the columns exist to remove.
- **Reverse prefers the stored column and keeps its encounter-order recompute as the fallback.** An
  artifact compiled before 0.6 has no column and Principle 3 requires it to keep reversing, so
  `_write_resolution_csv` reads `locus_index` where it is present and counts where it is not. A test
  reverses each expanding reference example twice — once with the column, once with it stripped — and
  asserts the two `resolution.csv` files are byte-identical; that comparison is what pins the sort
  dependency the recompute silently relies on. The counter itself is maintained either way, because
  the positional pass below uses membership in it to enforce weights-first.
- **Neither column moves a `content_signature`**, and neither is re-emitted into `variants.csv`. They
  are `exclude=True` compiler-managed columns recording what resolution did.

**The positional tables' pass still writes a hard-coded `0`,** and that is honest only while those
tables never expand — true today, since RM43's fill is one locus per row. It stops being true if RM65
ever puts coordinates on the repeat and copy-number tables, and the RM65 entry carries that line.

**The expansion warning is one sentence per rsID, over every authored row at it.** It used to be
emitted inside the per-row loop, so a site with two authored genotypes published the identical
sentence twice and each copy said "expanded to 2 rows" of an artifact that had gained four. The union
of loci is what "maps to N loci" counts and the sum over authored rows is what "expanded to M rows"
counts — the two come apart exactly when an author writes more than one genotype at a key, since
`_hostable_loci` judges hostability per genotype and two rows at one key can legitimately reach
different loci. The deprecated `ensembl_cache` path keeps the old per-row shape deliberately; it is
removed at 1.0 and its modules report the counts as `None`.

**BA1 is a warning in both modes and its threshold is a parameter** (`compile_module(ba1_threshold=…)`,
default 5%). The right cutoff is disease-specific — sickle-cell's `rs334` sits at a filtering AF of
~0.048 in African-ancestry groups, just under the line, and a common recessive carrier allele
legitimately sits above it. Failing a compile over that would be the format arbitrating a clinical
judgement.

**The `sources.csv` orphan half exempts the layers with no `source` column to join, and there are two
of them.** "No table used it" is decided by reading the *generated* fact tables' `source` columns
(`resolution.csv` contributes its `authority`, not its link — RM33). The `annotation` layer **is**
`variants.csv`/`diplotypes.csv`/…, which carry none by design, so an annotation-layer row can never be
corroborated and used to be reported as stale on every drafted module — the exact row the licence gate
keys on. **`literature` joined that exemption in 0.5.4 (S23)** whenever the module carries `studies.csv`
rows, by the identical argument: `studies.csv` is the hand-curated literature table and has no `source`
column either, so a module citing a PMID through it can only be corroborated by the enricher-written
`literature.csv`, and a module with none has nothing to join. The old behaviour inverted the incentive
where it matters most — `vocab.MISPLACED_COLUMN_REASONS['source']` tells an author to declare a
hand-read source by adding a row here, doing so earned a warning that the row was unused, and deleting
it (shipping with the provenance unrecorded) was silent. Compliance warned, omission quiet. It stays
narrow: `frequency` still warns, because `frequencies.csv` *is* machine-written with a `source` column,
so a frequency declaration in a module carrying no frequencies really is stale. The undeclared half —
a source a fact table cites with no row — is unaffected and warns in every case, and neither half ever
escalates: over-declaring terms is the cheap error, and an author talked out of recording theirs is not.

**A coordinate that cannot exist is refused in both modes (RM48, 0.6).** `_check_build_coordinates`
asks one arithmetic question of every row carrying a `chrom` and a `start` — could this position exist
on this contig in the build it is recorded under? — and two shapes answer *no* provably, with no
sequence, no network and no provisioned asset:

- **a position past the end of its contig.** GRCh38's chromosome 1 ends at 248,956,422 and GRCh37's
  runs 294 kb further, so an un-lifted hg19 coordinate in that tail names a base that does not exist.
  When the position *is* inside another build's contig of the same name, the message says which, and
  points at `just-dna-enricher hint recover` — that is the whole diagnosis, and it costs a dict lookup.
- **a contig only one build names.** The 25 primary contigs are spelled identically in both builds, so
  this is entirely about unplaced scaffolds: `GL000209.1` is GRCh37's and `KI270728.1` is GRCh38's.
  `variants.csv` refuses either at the model (its `chrom` vocabulary is 1-22/X/Y/MT and always was —
  what 0.6 added there is that the *rejection* names the build); this reaches `studies.csv`, the PGx
  tables, `heteroplasmy.csv` and the injected `resolution.csv`, none of which validate the contig.

It is an **error in both modes** — the inconsistent-reference-allele class, not a mode ladder. `strict`
means *reproducible artifact*, and these rows are not unreproducible, they are false. Nothing
downstream catches them either: a VRS id minted at an impossible position is a correct digest of the
wrong input, which is how a 3,038-row off-by-one once passed every gate including `--strict`.

Three things it deliberately does not do. It says nothing about a **low** position — VCF writes POS 0
for a telomeric variant, so only the upper bound is consulted. It **withholds** on every contig the
tables do not settle: a shared scaffold (`GL000194.1`), an unversioned accession (`GL000205`, where the
suffix is what separates the builds), a patch or an alt locus. And it judges each `resolution.csv` row
against that row's **own** `genome_build` column rather than the module's, because that column exists to
say which frame the numbers are in. Findings are grouped by reason — a whole panel authored on hg19 is
one line, not one line per variant. The tables live in `just_dna_format.vrs`
(`PRIMARY_CONTIG_LENGTHS`, `CONTIGS_ONLY_IN`) beside `PAR_GRCh38`, for the same reason: assembly
constants the compiler needs offline. They carry **no refget accessions** — a second build's *identity*
is RM15, and `refget_accession` still raises for GRCh37.

**3. Content-addressed self-verification** — the strongest class, because the stored value is a *pure
function of other stored values*, so a disagreement is provable corruption rather than a difference of
opinion. `artifact.digest`, `content_signature`, the three fact-signatures, the Ed25519 signature —
and, since 0.5, **`vrs_id`**. Moving allele identity into this class is what the VRS work bought: a
`ga4gh:VA.…` used to be an opaque cross-reference that had to be believed, and is now a checksum the
compiler recomputes from the coordinate with no dependency and no network.

### The inescapable blind spots

These are not gaps *this tier* can close. Each follows from what the compiler **is** — a transform over
injected data — and pretending otherwise would be worse than saying so.

That is a claim about the compiler, not about the ecosystem, and the distinction matters now that two
of the rows below have moved. The **enricher** holds references the compiler never will, so it can
answer questions this table calls unanswerable — an authored `clin_sig` against ClinVar's, a cited PMID
against PubMed, an rsID against dbSNP. What stays true is the division of labour: the compiler's own
blind spots are permanent, what it cannot validate it makes **legible**, and a check that needs a
reference lives one tier up. The "What the format does instead" column below records which tier now
covers what.

| Blind spot | Why it is inescapable | What the format does instead |
|---|---|---|
| **Is a single-sourced number right?** An AC/AN, a pLI, a `clin_sig` — one source, no redundancy to exploit. A transcription error is indistinguishable from a correct value. | Nothing to check it against without fetching (Principle 2). | Records `dataset` (which release) and `source` (which link) so the number is *attributable*, and fact-hashes it so it cannot change unnoticed. |
| **Is the reference base right?** A wrong single-base `ref` mints the *correct* VA, so the artifact is self-consistent and wrong. | The compiler holds no sequence. | The **enricher** checks it (`sequences.verify_reference_alleles`); the compiler catches only two rows *contradicting each other*. |
| **Is an indel's `vrs_id` right?** Cannot be recomputed without justification against the sequence. | Same. | Reported as *unverifiable* (never as verified), and carried with that said out loud — a warning in **both** modes, since no authored edit could clear it. |
| **Is the coordinate the variant the author meant?** A perfectly valid VA for the wrong locus is indistinguishable from the right one. | Requires knowing intent. | `provenance.json`, `authorship`, and the studies table make the claim auditable by a human. **Narrowed in 0.6 (RM48):** a coordinate that could not exist in the declared build is now refused offline, and one that *reads* as the old assembly is diagnosed by the enricher against the live GRCh37 service. Neither reaches intent — a well-formed GRCh38 coordinate for the wrong GRCh38 locus is still invisible here. |
| **Is the annotation medically correct?** Whether `A/T at HBB → sickle-cell carrier` is *true*. | Out of scope by charter — the format supplies annotation tables and never a gene–disease inference. | `authorship.kind` lets a consumer route scrutiny (AI vs human-certified); `curator`/`method` record who decided. |
| **Does the cited study support the row?** `pmid` is grammar-checked; nobody reads the paper. | Requires the literature. | **Partly closed by the enricher (0.5).** Its literature pass confirms the PMID resolves, cross-fills the DOI/PMCID, and matches `provenance_quote`/`provenance_regex` against fulltext — for the **open-access subset only**, with coverage reported as a fraction so an unread paper is never mistaken for a failed quote. The compiler still reads nothing; it surfaces the recorded verdict from `literature.csv`. |
| **Is the source stale?** A v2.1.1 constraint number is well-formed and current-looking. | The compiler cannot see the world move. | `dataset` names the release; the gene-metrics pass labels its two routes differently and warns on the older one. Generalized to **identifiers** in 0.5: the enricher checks rsIDs against dbSNP (live/merged/absent), trait CURIEs against OLS4 (obsolete + replacement) and gene symbols against HGNC (approved/retired). All report; none rewrite. Extended in 0.5.4 to the **relationship** between two identifiers (S24) — a row's `gene` against the chromosome its variant sits on — because both halves can be individually valid while the pairing is fabricated. |
| **Is `acmg_sf` right?** A gene-list-membership flag the compiler holds no list for. | Same shape as `clin_sig`: the list is not in the module and cannot be, since a gene list inside the compiler is an un-injected reference (RM21). | **Closed by the enricher (0.5).** `acmg.check_acmg_sf` compares the flag against ACMG SF v3.2 as NCBI publishes it. Warns in `best_effort`, refuses in `strict` — list membership is a published fact, not a clinical judgement, so unlike `clin_sig` it *does* escalate. A blank cell is a note, never a defect. |
| **Is the annotation medically correct?** — the clinical half. Whether the module's `clin_sig` is the right call. | Out of scope by charter (below), and ClinVar is not truth either. | **Surfaced, never adjudicated (0.5).** The enricher compares each authored `clin_sig` against the ClinVar snapshot's, allele-exactly, and reports opposed calls with ClinVar's review-star count. It is the one check whose severity does **not** escalate in `strict`: failing there would make the format decide a clinical dispute. |
| **Did the author declare every source they copied from?** A copied annotation with no `sources.csv` row is indistinguishable from an original one. | Provenance of a text is not a property of the text. | The **enricher** writes the row when it fetches (it is the only tier that knows); `sources.csv` + `manifest.sources` make the declaration legible and hashed. The compiler warns on a source a fact table cites with no row, but cannot see what was copied by hand. |
| **Did the enricher get it right?** The resolution table is consumed as fact. | The trust boundary itself. | `source`, `status`, `resolution_mode`, `fully_resolved` and `resolution_signature` make the provenance and the policy legible. |

The through-line: **what the compiler cannot validate, the format makes *legible*.** It records who
produced a fact, from which release, under which policy, and hashes it so it cannot drift silently —
then leaves the judgement to a consumer. That is the data-agnostic north star applied to trust.

### One gap that was *not* inescapable — where a bin boundary came from (S19/RM47, closed in 0.6)

Everything above is a limit of the tier. This one was a limit of the **schema**, and it is kept here
because the distinction is the point: a tier limit is permanent, a schema limit is a release away.

`studies.csv` is required iff `variants.csv` is present, so grounding was enforced exactly where
citations usually arrive already attached (a ClinVar-drafted `variants.csv`) and absent where a human
made the judgement: `reference_examples/htt_repeat_expansion` compiled green under `--strict` asserting
where Huntington disease becomes fully penetrant, with no citation anywhere. A `StudyRow` named a
variant — `rsid`, or a bare `chrom` — and a `repeat_alleles.csv` row is keyed `(gene, repeat_unit)`, so
nothing could point at it.

**0.6 closed it with a second citation site: `MeasureBinRow.pmid`**, one optional column on the binning
base reaching all four kinds, plus a relaxation of `StudyRow`'s subject requirement so the paper behind
a threshold can be described without inventing a variant for it. The rule for reading the pair is *the
bin row cites, the citation table describes* — the pointer sits on the row that states the number, and
everything about the paper stays in `studies.csv`. `heteroplasmy.csv` had a second route from the
start: its optional `rsid`/`chrom`/`start` columns (0.5.1) give a row a variant identity a study row
can name, which `reference_examples/mt_heteroplasmy` does — but that route *is* the study row, so it
grounds a bin only in a module that carries one.

`_check_binning_grounding` still warns in **both** modes, over the bins that carry no `pmid`, in a
module with no study rows at all — and the remedy it names is the same for every kind, since every kind
can now cite its boundary; a kind whose rows can be pointed at is offered the study-row route as a
second one. It used to exempt a bin for merely naming a variant, inside a branch that has already
established the module records **no** study rows, so the citation clearing the bin was one that does not
exist: a `heteroplasmy.csv` module stating four thresholds and citing nothing was green and silent while
the identical thresholds on `repeat_alleles.csv` were reported (D1-3, fixed in 0.6). The same-release
obligation was the reason the
item was filed rather than fixed: `_cross_check_literature` reads the bin pointers alongside
`studies.csv` (otherwise every threshold-grounding citation would read as a stale orphan), and so does
the enricher's literature pass, so a bin-grounded citation is checked for existence and identifiers
exactly like a study-grounded one. `reference_examples/htt_repeat_expansion` is deliberately left
**uncited**: the example exists to show what the warning looks like.

**0.7 added a third site the same way (RM132), and stopped listing them.** `PharmVariantRow.pmid`
grounds one drug/genotype/category claim, which `studies.csv` cannot: a study row keys on
`(variant_key, pmid)` and would attach to every claim recorded for that variant at once. The lesson
above is now enforced structurally rather than remembered — `_CITING_TABLE_KINDS` is every
`_TABLE_KINDS` model declaring a `pmid`, and `table_citations`/`load_citing_rows` walk it, so the next
kind to declare the column is read by both tiers with no edit to either. `_check_binning_grounding` is
untouched by this and stays about *bins*: there is deliberately no equivalent grounding warning for an
uncited pharm row, because a drug-response table is not the interpretive-threshold case that check
exists for.

### One paper, several analyses, and the dedup key (RM140)

The three sites above are about *which row* cites a paper. This one is about what a citing row's
numbers mean once it has. A `studies.csv` row carries `p_value` and `effect_size` side by side and
**asserts they belong together**; before 0.7 nothing recorded, and so nothing could check, whether they
came from the same analysis. `study_design` names the study — case-control, GWAS, meta-analysis — and a
single study routinely reports several analyses of one association: the motivating module cited a paper
giving `OR 1.4, p 0.36` from an allelic Fisher's exact test and `OR 1.42, p 0.75` from a univariate
logistic regression of the same variant, and two agents building from it produced rows that differed
only in `p_value`, one of them pairing the magnitude of one analysis with the p-value of the other.
Everything was green — including quote verification, because the quote grounds the *significance
verdict* and contains no statistic to witness.

**`StudyRow.statistical_test` (0.7) is the column, and it is deliberately not a gate.** Free text like
`study_design`, no vocabulary, no new check. What it changes is one existing one:
`duplicate_study_citation` fires on a repeated `(variant_key, pmid)` because the check's own reading of
that pair is *the same claim written twice* — which two rows naming two analyses are not.

**Only *both stated and different* suppresses the warning.** The rule is Kleene rather than `a != b`:
an absent `statistical_test` is **unknown**, and unknown against a stated value cannot establish that
two rows describe separate work. So a pair where neither row names an analysis, where both name the
same one, or where one names one and the other does not, warns exactly as it did before, with the same
code and the byte-identical message — every module published before 0.7 behaves as it did. A row
repeating an analysis already stated for its key still warns however many distinct siblings sit beside
it.

**`StudyRow._KEY_FIELDS` is not widened**, and the divergence is contained in this check. That tuple
drives `hints.key_fields` and the `key.columns` an authoring surface publishes; re-keying a shipped
authored table changes what an identity key means, which is major-only under Principle 3. The check
restates `(variant_key, pmid)` rather than reading `_KEY_FIELDS`, so splitting it here splits nothing
else.

### Three more schema limits, made legible the same way (0.6, the VCF 4.4 audit)

Same class as the bin-boundary gap above — limits of the **schema**, not of the tier — and they are here
for the same reason: so they are not mistaken for the other kind, and so the warning a reader meets on a
real module has somewhere to point. All three warn in **both** modes and none changes a verdict.

**The two integer measure kinds are not integral (RM55) — warned, and then fixed in the same line.**
VCF 4.4 §7.2 redefined `CN` to support non-integer copy numbers and §3 types `RUC` as a `Float`, so the
premise `repeat_count` and `copy_number` were placed in `binning._INTEGER_KINDS` on has been withdrawn
for both. The consequence was RM35's unsatisfiable triangle re-instantiated on the kinds RM35 exempted,
and worse: under a grid a hole of exactly one is not reported at all, so `[0,0] [1,1] [2,2] [3,∞)` is a
legal, gapless, green tiling under `--strict` that answers nothing for a CN of 2.4 — and the schema also
**refused the tiling that would fix it**, since a shared endpoint on those kinds was an overlap error.

The usable fix landed in 0.6 rather than 0.7: an optional `measure_tiling` column (`{quantised,
continuous}`) that the shared-endpoint and gap rules read instead of the kind, with **absent meaning
the kind's default** so no published table is re-read; `modifier_copy_number` beside the one genuine
`int`, `modifier_cn` deprecated; and a fractional value switching a would-be-quantised group to the
continuous rules by itself, saying so in a warning. See [SCHEMAS.md](SCHEMAS.md) for the per-kind
default table and the resolution order. `binning.measurement_shape_warnings` still says the RM55
sentence once per table, but **only where it is still true** — a kind VCF 4.4 types as fractional that
still has a group reading as a grid. A table declaring itself continuous, or carrying a fractional
bound, answers its own boundaries and is silent. Only the removal of `modifier_cn` stays at 1.0, so
1.0 inherits a removal rather than the retype the original route named.

**A measurement can span several bins (RM56).** The same two fields carry confidence intervals (`CIRUC`,
`CICN`) whose missing bound means *unbounded*, so a real measurement is an interval; `htt_repeat_
expansion` states three thresholds inside a 14-count window for one to cross, and the consumer contract
has no state for it. 0.6 warns and states the placeholder — **withhold** — rather than leaving it
silent. The policy vocabulary (withhold / worst bin / point estimate) and its grain wait for a real
caller VCF. Widening the measurement itself into an interval is not on the table: that puts a
measurement in the module, which the data-agnostic north star forbids.

**`.` in an `alts` cell splits identity (RM58).** VCF's MISSING marker means *there are no alternate
alleles*, and no `ref`/`alts` column has a nucleotide grammar (deliberately — adding one would tighten
the field RM5 exists to widen), so the cell loads and `derive_variant_key` folds it in as though it named
an allele: `1:1:A:.` where the same site with an empty cell is `1:1:A`, two `content_signature`s and no
dedup between them. `alleles.non_nucleotide_reason` now answers a third reason, `"missing"`, distinct
from `"ambiguity"` (a permanent uncertainty) and `"notation"` (a grammar gap a release may widen) — `.`
is neither, and there is nothing to widen to hold it. A **diagnosis, not a grammar**: the value is still
accepted, and the compiler warns per table with the two keys side by side. It is the only finding of the
VCF round that reaches identity, and it reaches only the key *string* — `is_substitution` refuses a
non-nucleotide alt, so no VA is minted and no content-addressed claim is false.

One finding from the same round is **not** a schema limit and is listed with the pointer columns in
[SCHEMAS.md](SCHEMAS.md) instead: a `min_quality` floor stated against `QUAL` on a `requires_callable`
row inverts, because QUAL changes sign with the record (§1.6.1.6) and such a row is proved against the
reference record. The compiler warns and deliberately does not refuse — the meaning depends on a record
this tier will never see, and the same row read against a variant record is legitimate.
### And a fourth — a pointer that does not identify a VCF field (RM53/RM54, 0.6)

Same class as the three above: a limit of the schema, closed in 0.6, and worth keeping in the same
place because the *check* that survives it is again a legibility warning rather than a verdict.

Three authored columns point into a VCF (`source_field`, `callable_from`, `quality_from`) and all
three took a bare token. A VCF field is identified by **namespace** — INFO and FORMAT are two
reserved-key tables that collide on `DP`, `AD`, `ADF`, `ADR`, `MQ`, `AF` and, since 4.4, `CN` — and
described by **cardinality** (`Number`, which decides how many values come back and what each is *of*).
Where both readings are type-compatible, and for `DP`, `AF` and `CN` they are, nothing detects the
confusion: the consumer reads a well-formed number of the wrong kind and bins it without error. Both
shipped reference examples that used these columns were wrong this way, under `--strict`, with every
offline gate passing — the same failure geometry as the 3,038-row coordinate incident.

The schema half is in [SCHEMAS.md](SCHEMAS.md): the pointer grammar accepts `INFO/DP`/`FORMAT/DP` (bare
still legal, still meaning unqualified), the spec's own key charset is accepted (`1000G`, a dotted
key — RM61), and `MeasureBinRow.source_element` names which element of a multi-valued field the bin is
measured against, from a closed set of named rules rather than an index (P1 refuses `AD[1]`).

`_check_vcf_pointers` is the compiler half, and it has two findings, both **warnings in both modes**:
a bare key that is one of the known collisions, and a pointer at a spec-defined multi-valued field with
no element rule. Neither escalates under `strict` — the grammar was widened rather than replaced, so
refusing there would break P3, and `strict` means *reproducible artifact*, which an unqualified pointer
is (P5). Both are aggregated by reason, since a panel pointing every bin at one field would otherwise
print the same sentence hundreds of times.

Two things it declines to say, both for the reason this section exists. Cardinality is read from a
transcription of the spec's reserved-key tables and **nothing else** — `REPCN` is ExpansionHunter's
key, not the spec's, so this tier is not entitled to assert its `Number`, and a bare `CN` disagrees
across the two namespaces. Unknown withholds. And the cardinality finding is scoped to pointers that
*have* a companion column: `callable_from`/`quality_from` did not get one in 0.6, and telling an author
to fill a column the schema does not have would be a finding no edit could clear.

### And a fifth — a site annotated for some of its genotypes and not the rest (S32, 0.6)

Not a schema limit at all: this one is entirely visible in the authored rows, and nothing but a check
was ever missing. A consumer matches a subject on `(variant, genotype)`, so a genotype with no row is a
subject with no answer — and the consumer who reported it found a curated 520-site module authoring no
homozygous-alternate genotype at 208 of them, with their subject homozygous at 74. Every one was
silently unreported.

`_check_genotype_coverage` fires **only at a site the module already annotates for two or more
genotypes**, and that scope is the design rather than a tuning choice. One genotype at a site is the
ordinary shape of a drafted-then-curated module — `pathogenic_clinvar` authors exactly one at 326 of its
327 sites — and it is a legitimate rule, not a gap; reporting those would put a line on almost every
module in existence, which is how a warning stops being read. Two or more is the author demonstrating
that the genotype *space* at that site is what they are describing, and the missing member is then a
hole in something they started. It expects the reference homozygote, one heterozygote per alternate and
one homozygote per alternate, and **never** an alternate/alternate pair — RM35's jointly-satisfiable
lesson, since requiring `A/T` would make a two-alternate site unreachable. The reference allele comes
from the row or from the injected table, never from a guess: with neither, a two-allele site is still
enumerable and is reported by spelling, and a site with three or more alleles is skipped. Sites whose
genotypes are not diploid nucleotide pairs drop out on their own, which is what keeps MT and non-PAR Y
out without a contig list.

**It says nothing about any callset, and that boundary is the item's own.** Whether a hom-ref row can
ever match is a property of the data a consumer brings — a variant-only VCF emits no record where the
sample matches the reference, a gVCF and an array both do — so that call belongs to the annotator. The
*presence* of a hom-ref row is therefore never reported: those rows are correct, and on array data they
are the ones that carry the answer. Warning in both modes and never a `strict` error, joining the small
set of checks that arbitrate nothing (the ClinVar `clin_sig` cross-check, the declared-licence
disagreement, the non-commercial quote): which genotypes a module annotates is the curator's judgement.

It runs in `validate_spec` **only**, and reaches a compile through the warnings it returns — the message
carries a count, and after resolution a one-to-many rsID has become one row per locus, so a second pass
would publish a second, differently numbered copy of the same finding into
`manifest.compilation.warnings`. Three reference examples fire it, each truthfully:
`grch37_build` and `hfe_hemochromatosis` state a carrier and a homozygote and no reference homozygote,
and `pathogenic_clinvar` states both HBB heterozygotes at 11:5225715 and neither homozygote.

### Hints are not a fourth validation class

`hints.py` computes nothing the compiler does not already compute — it reuses `validate_bins`,
`_TABLE_DUPE_KEYS` and the models' own validators — and it **never fails a build**. It has no mode
ladder, because the checks that do have one already exist here and in the enricher, each with the
severity the charter assigns it (including the two deliberate exceptions that warn in both modes). A
hint that could fail a compile would be a third copy of a rule that already lives in two places.

What hints add is *when*: the same verdict, before the author has written the file, plus the allowed
values and the reason a cell is deliberately left empty. That last part is the load-bearing one — see
`hints.REDUNDANCY_BEARING`. Class 2 works because two independently-authored things must agree, so a
tool that fills one of them from the source the checker consults does not merely make the check
tautological; for an rsid-only row `resolution._verify` never runs at all, and the row would go from
honestly unverified to apparently verified. Every looked-up fact is therefore reported with
`applied=False` and a refusal reason, and the enricher's `lookup.py` answers in the same shape.

**A column name is not a scope, and the reason given now says which table it applies to (RM123).**
`REDUNDANCY_BEARING` maps a bare column to the checker that reads it, and `clin_sig` is a column on
`variants.csv`, on all four binning kinds and on `diplotypes.csv` while `verify_clin_sig` takes
`list[VariantRow]`. So the vacuous-check sentence printed on six (column, table) pairs whose checker
cannot see the table — right advice, false reason, and a green run on one of those cells looked like
agreement with an authority that never saw it. `REDUNDANCY_BEARING_TABLES` narrows the *explanation*
for the columns whose checker reads fewer tables than carry them; an absent key means unscoped, which
is the honest answer for `rsid`/`chrom`/`start`/`ref`/`alts` (resolution reaches the positional kinds,
RM43) and for `pmid` (a bin and a pharm row are citation sites in their own right, RM47/RM132).
**It scopes nothing else**: the refusal a
drafting provider obeys stays keyed on the bare column, because whether a provider should start filling
`clin_sig` on a binning row is a decision nobody has taken.

One consequence of computing nothing new is that the same cell can be seen by two layers, and a hint
must still print it once. An unreplaced `TEMPLATE_PLACEHOLDER` is the case: `_check_placeholders`
names the column, and the model then says the same thing less usefully — a row-level `ValueError`
listing every placeholder path on an authored model, or a vocabulary error quoting the token back on
`sources.csv`/`licensing.csv`, whose row model carries no such guard. A freshly drafted 109-row panel
printed two lines per defect. `_validate_row` drops both restatements, keyed on the cells the
per-column check actually reported, so a placeholder error nothing covered would still be shown. The
guard itself is untouched: it is what makes a generated stub unable to compile, and a hint refuses
nothing.

## And what is not the compiler's job at all

Static checking has an upper bound here, and the analogue of dynamic analysis lives elsewhere. The
compiler is not a runtime verifier: it never runs a module against a genotype, because a module carries
no sample data and the measurement is supplied by the consumer at query time. The ecosystem's
"valgrind" is the **consumer-side verification harness** — run a panel against N VCFs and diff a
report-card — which is deliberately *not* a format feature ([USE_CASES.md](USE_CASES.md) §3b / RM7).
The format's contribution to it is the properties it already froze: `artifact.digest` makes the
before/after diff trustworthy, and the mandatory `unresolved`/callability contract stops a no-call
masquerading as a mismatch.

## The compile pipeline

**A file the compiler has no meaning for is ignored, and that is a contract** (S16). A spec directory
may carry a README (every `reference_examples/` module does), curation notes, or a publisher's receipt
recording the identity a registry stamps — those keys cannot live in `module_spec.yaml`, where
`extra="forbid"` rejects them precisely because the registry owns them. Such a file is not read, not
hashed, and not in `artifact.files`, so it **cannot move `artifact.digest`**; pinned by a test that
compiles the same spec with and without two unknown files and compares digests. The one exception is a
**near miss**: an unknown `.csv` within one small edit of a table name (`varaints.csv`) warns, because
"ignored" is the wrong answer for a typo — every row in that file is being silently dropped from a green
compile. The check is edit-distance-keyed rather than "any unknown csv" on purpose, so it cannot undo the
tolerance above. It reads `.json` as well as `.csv` since 0.6, which covers `verification.json` and
retroactively covers `provenance.json` — that one had been in the known-name set since 0.4 with no
suffix that could reach it, so a `provenence.json` was invisible to the very guard written for this.
A registry's `published.json` is not within an edit of either and stays tolerated, which is the
property the widening had to preserve.

**Where the machine-written sidecars may live, and what they may be called (RM49/RM51, 0.6).**
`resolution.csv`, the six fact tables and `verification.json` are resolved through
`just_dna_format.layout`, which accepts each of them at the spec root **or** under a `derived/`
subdirectory, and accepts the licence table under either `sources.csv` (deprecated, warn-only, removed
at 1.0) or `licensing.csv`. Four rules:

- **Only the machine-written tables move.** `module_spec.yaml`, `variants.csv`, `studies.csv` and the
  table kinds have exactly one legal name in exactly one legal place. Two legal homes for an authored
  table means a module can carry two copies with the ignored one invisible.
- **`derived/` is tolerated, never canonical.** `reverse_module` emits a flat tree and the enricher
  creates one; a module is split only because somebody split it.
- **`reverse_module` writes the sidecars through the same resolver, so a round trip migrates the
  name.** It regenerates a spec directory rather than editing one, so on a fresh tree there is nothing
  to follow and the rule yields the preferred spelling — a module carrying `sources.csv` reverses onto
  `licensing.csv`, and a compile → reverse → compile no longer picks up a deprecation notice its first
  compile did not have (`manifest.compilation.warnings` is published, so the two must agree).
  Reversing *over* a directory that already carries a copy overwrites that copy instead of leaving a
  second one beside it.
- **Two copies of one table is an error naming both paths** — never a merge, never newest-wins. These
  tables are fact-hashed *and* human-overridable, so two copies are two legitimate claims and
  preferring one silently discards a curator's override. The enricher's rule is the other half:
  **write to the file you read**.
- **The guard follows into `derived/`, and it takes two tests there.** Tolerating a second location
  without extending the guard would put a typo'd `derived/varaints.csv` exactly where the check written
  to catch it cannot see — which is also why "search any subdirectory" was refused: one fixed name is
  the only version the guard can follow. What is *legal* under `derived/` is the sidecars alone, but
  that smaller set is the wrong thing to fuzzy-match against, and matching against it caught neither
  case: at the 0.8 cutoff `variants.csv` is no near miss of any sidecar name, and neither is
  `varaints.csv`. So an **authored table name under `derived/` is reported as misplaced** on an exact
  match — those rows are read from nowhere, and a module that keeps another table compiles green
  without them — while everything else there is fuzzy-matched against the full known set. The
  acceptance set stays the smaller one, so a legal sidecar is never reported as a stray, and the mirror
  case (a sidecar at the spec root) is legal and stays silent.

Neither the name nor the location enters any identity: the fact sidecars are outside `_INPUT_FILES`
(see the file sets below), so `artifact.digest`, `content_signature`, `resolution_signature` and
`source_signature` are unchanged by either. `manifest.derived` records the relative path it found, so
a `derived/…` entry tells a registry how the tree was laid out.

The compiled outputs are untouched: a module reading `licensing.csv` still writes `sources.parquet`
and still publishes `manifest.sources`. Both of those are renames only a major may make.

`compile_module` runs in this order:

1. **Validate** (`validate_spec`); fail early if invalid.
2. **Load** `module_spec.yaml` (authority-key pre-strip), then `variants.csv` / `studies.csv` if present.
3. **Load `resolution.csv`** if present → group rows by `variant_key` into a resolution table (a
   row-parse error fails the compile), then **verify every stored `vrs_id`** (below), and stamp
   `resolution_signature`/`resolution_sources` **here** — where the table was read, so a module with
   no `variants.csv` records the identity of the table it carries rather than a null (0.6, RM45).
4. **Resolve** (only if `resolve_with_ensembl and variants`) — the precedence block below.
5. **Re-validate identity post-resolution** (`_cross_validate_variants`) — resolution can change identity
   (fill a coord, expand a one-to-many rsid), so a post-resolution duplicate/inconsistency fails the
   compile (`"post-resolution: …"`).
6. **Compute `fully_resolved`** = every variant has `chrom`+`start` (vacuously true for a variant-less
   module), and `resolution_subjects` = how many rows that quantified over, from the same list, so the
   flag cannot be published without its denominator (RM44).
7. **Strict gate** — if `strict` and any variant still lacks `(chrom, start)`, fail **before any parquet
   is written** (refuse a non-reproducible partial artifact).
8. **Write parquets** — SNP core (`weights`/`annotations`/`studies.parquet`, only when the relevant rows
   exist) + one parquet per present table kind + the derived-fact sidecars
   (`frequencies.parquet`, `gene_metrics.parquet`, `literature.parquet`, and since 0.6
   `gene_validity.parquet`, `clinical_assertions.parquet`) when their CSVs are present,
   each cross-checked
   against what the module actually contains (a frequency coordinate no variant sits at, or a gene the
   module never mentions, is a **warning** — an over-broad sidecar is harmless, and failing the compile
   over it would punish the author for the enricher's generosity).
9. **Collect** logs / `provenance.json` / logo / readme (a malformed one fails the compile, not
   raises). The readme is discovered from `manifest.README_CANDIDATES` and hashed into
   `manifest.readme`, outside `artifact.files` — so it is attested without being content (S25).
10. **Read the verification attestation** (`verification.json`, RM45): recompute the binding over the
    authored inputs — with `\r\n` read as `\n` since 0.6 (RM82), so an editor's line endings are not an
    edit, while `manifest.inputs[]` keeps listing the raw bytes and raw sizes because it answers *are
    these the exact bytes* — re-check the proof-of-work, and either carry the block into the manifest or
    **warn and drop it**. A stale attestation never fails a compile — the goal is that it never
    becomes a published claim, not that it be impossible to write while editing. Nothing here is
    trusted; see SCHEMAS.md. **The same read decides the closure (RM73, 0.6)**: if the block that
    survives carries none, the compile says so — a warning in both modes, carrying no count so the
    identical sentence from `validate_spec` de-duplicates against it. Absence is the only thing said
    here, because the reason (never closed, closed then edited, no document at all) is already carried
    by whichever other warning applies.
11. **Build the manifest** (`content_signature` re-read from raw disk, the resolution fields, the
    `frequency` / `gene_metrics` / `literature` / `verification` blocks, and `derived[]` — byte hashes
    of the sidecars *where they live beside the spec*, transport-only and never their identity) and
    write `manifest.json`.

### The VRS verify pass (0.5)

> **A GA4GH concept in a no-network tier — deliberately, and asserted.** VRS is normally met alongside
> sequence services and a client library, so importing the *idea* into the compiler is exactly the kind
> of change that quietly drags a network dependency behind it. It does not: allele **identification**
> is `sha512t24u` over canonical JSON — arithmetic — while only **normalization** (indels) needs
> sequence access, and that half lives solely in the enricher. `just_dna_format.vrs` imports
> `base64`/`hashlib`/`json`/`re` and nothing else; `ga4gh.vrs` appears nowhere outside
> `just_dna_enricher`. `compiler/tests/test_tier_purity.py` pins this in a **fresh interpreter** (the
> test suite has the enricher loaded, so an in-process check would prove nothing): the compile path
> imports no network client, `just_dna_format.vrs` pulls no non-stdlib module, and a full compile —
> minting the VA, keying on it, and rejecting a tampered id — succeeds with `socket.socket` booby-
> trapped to raise.
>
> The residual risk is not what is there, it is the **gradient**: the verifier is *partial* (it can
> recompute a substitution and not an indel), and the tempting completion is to give the compiler
> sequence access. That is the line not to cross — the asymmetry is the design, not a gap. Likewise
> `refget_accession` raising for a non-GRCh38 build is not an invitation to fetch the accession; it is
> an invitation to add a second committed table (RM15).

A `ga4gh:VA.…` is content-addressed, so it is the one column in the whole artifact that can be checked
**against itself** — no reference, no network, and no new dependency, since `derive_vrs_allele_id` is
stdlib (Goal 2). `_verify_vrs_ids` runs before anything is written, so a bad id never reaches an
artifact. It belongs *here* rather than only in the enricher because the compiler is the last gate
before an artifact exists: a spec can be hand-edited and compiled directly, never touching the
enricher, so an enricher-only check would be bypassable. Checking injected data by pure computation is
precisely the compiler's job — the same thing it already does for every hash and digest it writes.

#### Three outcomes, and why "unverifiable" is not "mismatch"

Every row with a `vrs_id` lands in exactly one of three outcomes. The distinction between the last two
is the point of the whole design, and conflating them would be a lie about what was actually checked:

| Outcome | Meaning | `best_effort` | `strict` |
|---|---|---|---|
| **verified** | recomputed, and equal | silent | silent |
| **mismatch** | recomputed, and **different** | **error** | **error** |
| **unverifiable**, the *tier's* limit | could not be recomputed **here**, and no edit would change that | **warning** | **warning** |
| **unverifiable**, the *row's* contradiction | an id recorded against nothing to check it with | **error** | **error** |

Note what the mode column does here: **nothing**. This pass is not a mode ladder. Severity comes from
*whose limit the finding is*, and both answers are the same on both rungs.

**A mismatch is always fatal, in both modes.** A substitution's id is fully deterministic here — same
inputs, same 20 lines of `hashlib`, same answer — so a disagreement cannot be a difference of opinion
between implementations. It is corruption, and there is no mode in which carrying it is right.

**An indel is never reported as a mismatch, because it is never compared.** This tier cannot recompute
an indel's id (justification needs the reference sequence), so it can only report that it *did not
check*. Saying "mismatch" would assert a verdict that was never reached. Warnings land in
`manifest.compilation.warnings`, so an unconfirmed identity is visible to a consumer rather than only
to whoever ran the compile.

**Why the tier's own limits do not escalate under `strict`.** They did, for one release cycle, on the
reasoning that *unchecked* and *correct* are different things and `strict`'s contract is a reproducible
artifact. The first half is true and is why the outcome exists at all; the second half does not follow.
An enricher-minted indel VA **is** reproducible — the bytes are injected, the compile is deterministic,
and recompiling yields the same digest. What is out of reach is the *verification*, not the
reproduction, and escalating on that conflates "I could not check this" with "this cannot be rebuilt".

The cost was concrete rather than theoretical. Minting indel ids online is exactly what
`just-dna-enricher` exists to do, so every ClinVar-derived module acquired identities that
`compile --strict` then refused, and the two remedies the error offered were *lower your guarantee* or
*delete a correct identity*. Two reference examples — `pathogenic_clinvar` (185 alleles) and
`shox_par1` (2) — stopped compiling in the mode their own READMEs document, and the authoring skill's
step 6 tells every author to run exactly that mode. The rule now matches the one
`_vrs_coverage_warnings` and `frequencies`' `not_covered` already followed: **a finding no authored
edit could clear is not a `strict` matter** — `strict` is orthogonal, and P5 says orthogonal axes stay
orthogonal.

**What still errors, and in both modes, is the row contradicting itself**: a `vrs_id` recorded against
no coordinate, against no ALT, or — since R2-5 — against a **symbolic** allele. That is not a limit of
this tier. The first two assert an identity while withholding the very thing that identity is a digest
of; the third asserts one for an allele that *has* no sequence to digest, so the id necessarily names a
different allele. Nothing anywhere could check any of them. Same class as the *inconsistent reference
allele* error, and catchable offline.

#### Every flow path

`_recompute_vrs_id` returns either the recomputed id or the reason there is none, **for one allele**.
`vrs_id` is a comma-joined parallel array of `alts`, so the pass walks the two together and each ALT
gets its own verdict; an empty member is a hole and reads exactly like an empty cell. Most of the
reasons are limits of a no-network tier rather than defects in the row — the last three are not:

| Row | Path | Both modes |
|---|---|---|
| no `vrs_id`, or a hole in one | nothing to check — **not** the same as "could not check" | silent |
| substitution, id agrees | verified | silent |
| substitution, id differs | **mismatch** | error |
| multi-allelic, every member agrees | verified allele by allele | silent |
| multi-allelic, members swapped | **mismatch** — the desync a length check cannot see | error |
| indel / MNV (`C>CA`) | needs the reference sequence — minted upstream, not recomputable here | warning |
| off-assembly contig, or a position past the contig end | no refget accession to address the sequence by | warning |
| non-GRCh38 `genome_build` | no refget table for that build (RM15) | warning |
| `*`, the unobservable-allele marker (RM59) | the callability axis — it names no allele, so nothing to digest | warning |
| symbolic allele (`<DEL:4977>`, RM5) **carrying an id** | no tier mints one, so a recorded id names a **different** allele | error |
| position-only (no `alts`) | an id against no ALT — the **row's** contradiction, not the tier's | error |
| no coordinate | an id against no place (an rsid row carrying an external id) | error |

**A symbolic allele with no id is a coverage warning; one *carrying* an id is an error, and the
asymmetry is the rule rather than an exception to it.** Absence is this tier's limit — no authored edit
clears it, which is what keeps every structural module compilable — while a recorded id is a claim
about an allele that has no content to address, so it can only name something else. *Absence is a
limit; a claim is a claim.* The escalation waited on the grammar (R2-5): it follows only once `vrs_id`
is known to hold allele ids alone, which `vrs.validate_vrs_allele_id` now enforces (`ga4gh:VA.` only,
probed at 844 corpus ids with no other type). The remedy is one edit — delete the cell; `variant_key`
still carries the allele's identity.

`*` sits beside the symbolic row and **not** inside it (R2-6). The two are different axes, which is why
`_vrs_gap_reason` and `_recompute_vrs_id` test `is_unobservable_allele` separately and above the
substitution fall-through: `parse_symbolic_allele` asks *which variant is this, unspelled*, while
`is_unobservable_allele` asks *whether the sample's call could see an allele at all*. Reported as an
indel it would carry a remedy — re-run the enricher online — that can never apply.

Multi-allelic used to be one row of this table, blanket-unverifiable, "a VA names exactly one allele;
picking one would invent data". The premise is `derive_variant_key`'s and it is right there — a
`variant_key` names one thing, so a plural cell falls through to the coordinate key. It was wrong here,
where nothing is picked because every ALT is named. It cost the id on 909 of 1,613 rows in one real
module while every input needed to mint all 2,110 of them sat in the same row.

**A symbolic allele is its own row of that table, and it was an indel for the whole of 0.6 until a
module carried one.** RM5 shipped the structural grammar and this pass was never told, so `<DEL:4977>`
fell through to `is_substitution` and was reported as *"an indel or MNV: justification needs the
reference sequence, so only the enricher can mint it (re-run it online)"* — false on every clause.
Symbolic notation exists precisely because the sequence is *not* spelled: there is no sequence to
justify against, nothing for a content-addressed id to be a digest of, and no tier that mints one, so
the id is permanently absent rather than one online run away. (The enricher's minting pass says the
same wrong thing in its own words, and the online run this message recommended crashed on the same
allele — both of those are its side of the item, not this one's.) Two
consequences worth keeping. The branch sits **ahead** of both the substitution test and the accession
lookup, in `_vrs_gap_reason` and `_recompute_vrs_id` alike: a symbolic allele on a GRCh37 module is
also a build with no refget table, and between two true statements the one to print is the one no
release can answer. And the predicate is the **lenient** `is_symbolic_allele` — a malformed `<FOO>` or
an unterminated `<DEL` names no sequence either, so filing it under "indel" would be the same false
claim about a different mistake.

#### Coverage — what a VA does *not* name

Verification only ever looks at ids that are present, so a table where nothing was minted verifies
flawlessly. `_vrs_coverage_warnings` reports the other half: allele slots seen, how many carry an id,
and the remainder grouped **by reason class** (not by row, and not by `_recompute_vrs_id`'s per-row
prose — grouping on that produced forty lines each naming a different indel). The counts are recorded
in `manifest.compilation.vrs_alleles` / `vrs_alleles_identified`, so a consumer can read the
reliability of the identity scheme instead of inferring it; "complete" is `identified == alleles`,
derived rather than stored twice. A shortfall is a **warning in both modes** — the usual causes (an
indel with no sequence proxy, a build with no refget table) are fixable by no authored edit, and
`strict` means "reproducible artifact", which an incompletely-named table still is.

A **symbolic allele still counts in the denominator**, so a structural module reads as permanently
short of complete coverage — `reference_examples/mt_common_deletion` compiles at 2/3 and always will.
That is the honest number: the denominator is *allele slots in `resolution.csv`*, one definition, and
excluding the slots that can never be named would publish a second, undisclosed one — "coverage over
the alleles an id was possible for" — which is exactly the flag-with-a-hidden-subset shape RM44 exists
to stop. What tells the two situations apart is the reason line beside the count, which now says the
gap is permanent instead of naming a remedy.

The last row is a fixed bug worth naming: `refget_accession` **raises** `UnsupportedBuildError` rather
than returning `None` — deliberately, so a caller asking for GRCh37 hears "not built yet" instead of
receiving a GRCh38-flavoured answer. That exception used to escape the verify pass and abort the whole
compile over a single unverifiable row. It is now caught and turned into a reason, which is the correct
severity: one row this tier cannot check should not fail a build in either mode.


### The inconsistent-reference-allele check (0.5)

A VA addresses the *place and the alt*; the reference base at a position is a fact of the genome and is
not part of the allele's name. Correct VRS semantics — but it drops a guarantee the old
`chrom:start:ref:alts` key gave for free, since two rows at one position claiming different reference
bases used to be two keys and are now one. At most one can be right, so `_cross_validate_variants` now
fails a compile where two positioned rows share a key and disagree on `ref`.

### Symbolic alleles: the one check that discards an authored row (RM5, 0.6)

The grammar holds `<DEL:1500>` / `<CNV:TR:30>` (see [SCHEMAS.md](SCHEMAS.md) § *The allele grammar*).
What the **compiler** owns is the other half: a module is a declarative rulebook, and a rule nothing
can apply is worse than an absent one. A `<DEL>` with no length cannot be sized, matched against a
call, or told apart from any other deletion at that position, so `_check_symbolic_alleles` reports it —
and this is the first check in the tier that **discards an authored row**.

| Reason | What it is |
|---|---|
| `no_length` | a real structural type with no usable length: `<DEL>`, or `<DEL:0>` |
| `unknown_type` | angle-bracketed but outside the closed five — `<FOO>`, and VCF's `<*>`, which makes an observability claim rather than naming a variant |
| `reference_allele` | a symbolic allele in a `ref` column: REF is always a sequence, so a locus whose own reference is unspelled anchors nothing |

**Severity depends on whether the row stands alone as a rule.** On `variants.csv` and
`pharm_variants.csv` — one self-contained rule per row — `best_effort` **drops the row with a warning
that says so**, and `strict` refuses. On `haplotypes.csv` and `heteroplasmy.csv` it is fatal in *both*
modes: those rows are parts of a composite, so dropping one silently redefines a haplotype or punches a
hole in a bin tiling — not a smaller module but a different one.

A drop that would empty a table **outright** is an error in both modes as well, and on its own reason:
the drop exists so a module can lose one unusable rule and still say the rest, while a table that loses
every row says nothing at all and says it only in a warning. (Not, as a first cut claimed, because the
compiler already refuses a present-but-empty table — that is true of the `_TABLE_KINDS` loop and
**false of `variants.csv`**, which validates and compiles header-only. Measured, and pinned by a test.)

**The warning must say DROPPED.** This does not break P7 — the round-trip fixed point is claimed under
`strict`, where this case refuses — but `reverse` cannot re-emit a row that never reached the parquet,
so a warning that merely *flagged* it would leave an author believing their module still carries it.

Three mechanics worth copying. The check reads `AuthoredModel.ALLELE_COLUMNS`, declared on each model,
so the compiler holds no second copy of a model's column names. It runs in `validate_spec` too, by the
standing rule (pure computation over authored bytes, no `output_dir`) — with the identical message, both
because the pre-flight must predict what the compile will do and because `compile_module`'s
de-duplication is on the message; **every** refusal it can reach is computed in the shared check rather
than at the point of application, so `validate` cannot go green on a module `compile` then rejects in
the same mode. And `manifest.stats` is re-derived over the surviving rows: `weights_rows` counts the
parquet, so leaving `variant_count` as `validate_spec` computed it would publish a count higher than the
artifact holds — the RM44 class, a manifest number a catalog keys on and cannot check.

Findings name a row by its **identity** (`variant_key`, else `haplotype_name`), never by a file
position: `load_csv_rows` prints a header-inclusive line number and `hints.Finding.row` is a 0-based
data index, so a third convention would be one too many — and an index computed over the rows that
survived model validation shifts silently behind any earlier load error.

One asymmetry to expect: `<FOO>` fails at *load* in `genotype` / `effect_allele` /
`HaplotypeRow.allele`, which have a grammar, and reaches this check only through `ref`/`alts`, which
deliberately have none.

### Resolution precedence (additive; Principle 3)

Inside step 4, gated on `resolve_with_ensembl and variants`, with `resolution_mode = "strict" if strict
else "best_effort"`:

1. **`resolution.csv` present → `resolve_from_table`** (the preferred, source-independent path — no
   `duckdb`, no network, no Ensembl convention). Sets `resolution_signature` (fact-hash of the rows) and
   `resolution_sources` (sorted union of row `source`s).
2. **else `ensembl_cache` given → DEPRECATED DuckDB path.** Emits a `DeprecationWarning` ("… removed at
   1.0. Produce a resolution.csv …") and routes to the enricher via a **guarded lazy import**
   (`from just_dna_enricher.resolver import resolve_variants`); if the enricher isn't installed, the
   compile fails with a message pointing at it or at precomputing `resolution.csv`. The compiler declares
   no dependency on the enricher.
3. **else (nothing injected) → skip.** `None` no longer auto-discovers a cache (the 0.5 Principle-2
   tightening); variants lacking a position are left unresolved with a warning pointing at the enricher.

**Digest parity** between paths 1 and 2 is the load-bearing guarantee: given the same facts, both emit
byte-identical `weights.parquet` (hence `artifact.digest`). The one order-sensitive spot — a one-to-many
expansion — is pinned by sorting on `(locus_index, chrom, start, ref)`.

## Resolution

Resolution is where authored data meets injected facts, and it is the one place in the compiler where
a row can change shape. Everything below follows from one rule:

> **Resolution must be reversible.** `compile → reverse → compile` has to reproduce the module it
> started from — the same bytes, the same *authored* content, and the same resolved facts. Where it
> cannot, `strict` refuses rather than emitting an artifact nobody can re-derive.

### Scope: the SNP core plus the three positional tables (RM43, 0.6)

**Resolution applies to `variants.csv` and to the three positional 0.4 kinds** —
`pharm_variants.csv`, `haplotypes.csv`, `heteroplasmy.csv`, derived from the models rather than listed
(a table is positional exactly when it declares both `chrom` and `start`). Until 0.6 it applied to
`variants.csv` alone: every other table went through `_build_table`, which is the model straight to
parquet, so a row kept exactly the coordinates its author typed — for an rsid-authored module, none —
and a consumer matching a patient VCF by position matched nothing, silently, as an empty result rather
than an error. That is now filled at compile time from the injected table; see *The positional fill*
below for the four rules it follows and the three columns it needed.

The rest of this section is the 0.5.3 report (S9) that surfaced it, kept because two of its three
manifest observations still hold:

- **`fully_resolved` is `all(...)` over `VariantRow`**, so it is **vacuously `true`** on a module with
  no `variants.csv`. Its own field comment gives the trust rule *"a consumer trusts a module when
  `resolution_mode == "strict" or fully_resolved`"* — which is **not sufficient** for a 0.4-family-led
  module, where it can be `true` while every row lacks a coordinate. **Since 0.6 the denominator is
  published beside it** (`resolution_subjects`, RM44), so the sufficient rule is
  `resolution_subjects > 0 and (resolution_mode == "strict" or fully_resolved)` and the vacuous case
  is legible from the manifest alone. The counter makes the vacuity visible; RM43 makes the tables
  joinable, but the flag still quantifies over `variants.csv` only.
- **`resolution_mode` and the `--strict` unresolved gate are the same scope.** `strict` refuses on an
  unresolved `VariantRow`; it says nothing about a table row, which is why such a module compiles
  under `--strict` even where the fill could not place a row. That is deliberate — see the warning's
  severity below.
- **`resolution_signature` / `resolution_sources` stay unset** for a module whose only subjects are
  table rows, so its injected `resolution.csv` leaves no trace in the manifest. This was blocked on
  reverse, which rebuilt `resolution.csv` from `weights.parquet` alone; RM43 removed that blocker (it
  now rebuilds from the positional parquets too), and stamping the two fields is RM45's half of the
  same round.

**The warning's wording is a contract, because the manifest carries it and nothing else.**
`compile_module` copies its warnings into `manifest.compilation.warnings`, which ships inside
`manifest.json`, and a catalog reindexing from a published manifest has no spec directory left to
re-derive anything from — so for a table-only module the *sentence* is the only surviving record that
its rows join to nothing, `fully_resolved` being vacuously `true`. A downstream registry substring-
matches `"have no chrom+start"` to decide a trust badge; `compiler.UNJOINABLE_PHRASE` names that
fragment and a test pins it, so a reword breaks this build rather than a catalog. Improve the rest of
the sentence freely; move that fragment deliberately.

**RM44 shipped in 0.6 and it retired half of this; S31 shipped the other half.**
`resolution_subjects` gives a consumer a structured field for *"was the flag about anything"*, and
**`positional_rows` / `positional_rows_placed`** now give the unjoinable-row count RM44 recorded as
belonging with RM43 — the two counts, parts not a ratio, so "this table joins by position" is
`positional_rows_placed == positional_rows` and needs no prose. **The fragment and its test still
stay**, and not out of caution: every artifact published under 0.5 carries neither field, so for those
manifests the sentence remains the only record. Retiring it is a decision to take once the published
corpus has been recompiled.

**Reading it from the consumer side, which is what these fields are for.** A module's rows join by
position when `positional_rows_placed == positional_rows` (with `positional_rows == 0` meaning the
module carries no such table, so the question does not arise) — and `variants.csv` is the separate
question `fully_resolved` over `resolution_subjects` answers. **`None` on either field means the
artifact was compiled before 0.6**, which did not fill those tables at all, so the honest reading is
*unknown, and probably unfilled* rather than zero: a 1,482-row `pharm_variants` module compiled under
0.5 has every coordinate null and no manifest field saying so. That is the state the reporting
consumer had to discover by opening the parquet, and it does not change when a new compiler is
installed — a published artifact only moves when it is recompiled **and** republished, which is the
maintainer's action rather than the consumer's.

**The joinability warning now reports the residue.** Every positional table is still checked for rows
with no `chrom`+`start`, after the fill has run, and the finding is one aggregated line per table
carrying how many rows cannot be joined by position plus *why*. Three readings: the injected table
names the key at more than one locus (or at one the row's own allele contradicts), so the compiler
leaves it rather than picking; nothing in the table names the key at all, which an enrich run fixes;
or the fill **never ran** — `--no-resolve`, or a non-GRCh38 module — in which case the coordinates may
be right there and untried. The third branch is why the check is *told* whether the join happened
rather than inferring it: this sentence ships inside `manifest.compilation.warnings` beside
`UNJOINABLE_PHRASE`, so asserting "the compiler looked and would not pick" about a lookup that never
happened puts a fabricated diagnosis into a document a catalog reads. A half-coordinate (`start` with
no `chrom`, the shape a CPIC-drafted `haplotypes.csv` carries) is counted apart, because it reads as a
position and joins to nothing.

It is a **warning in both modes and never a `strict` error**, for two independent reasons: rsid-only
identity is legal by these models' own rule, so escalating would have the format tighten a field it
deliberately left open; and what survives the fill is by construction something no authored edit to
that table clears — the same class as VRS coverage and `not_covered`, where refusing makes a correct
module uncompilable for something its author cannot fix. It runs in `validate` as well as `compile`,
and is de-duplicated between them.

### The positional fill (RM43, 0.6)

`_apply_positional_resolution` joins the injected `resolution.csv` onto each positional table before
`_build_table` materializes it, and runs in **both** `validate_spec` and `compile_module` — the
joinability line is computed from these rows in both, so filling on one side only would leave the
pre-flight naming a gap the compile had already closed. `validate_spec` therefore takes
`resolve_with_ensembl` too, and `compile_module` passes its own value down: the flag is the master
switch for resolution of every kind, so a pre-flight that ignored it would be the more *optimistic* of
the two commands. The fill is skipped, with a warning, for a non-GRCh38 module, exactly as
`resolve_from_table` is (RM15).

Four rules, and the last two are what separate it from the naive repair:

- **Fill only what the author left empty.** A cell the author wrote is never overwritten. That is the
  inject-only doctrine (report, never repair), and it also makes the fill idempotent.
- **Fill from exactly one locus, or from none.** One usable locus fills. Several are filtered by
  `hosting_verdict` against whatever allele the row states — a `genotype` on a pharm row, the defining
  `allele` on a haplotype junction, nothing at all on a heteroplasmy band. If that leaves one, it
  fills; otherwise the row stays unplaced and the joinability line says so. There is deliberately **no
  expansion**: multiplying a pharm annotation's `(variant_key, drug, genotype, …)` key across loci the
  author never named is not the same operation as expanding a `variants.csv` row.
- **A row whose own coordinate contradicts the table is left exactly as authored**, and the
  disagreement is reported. Completing a half-coordinate from a locus whose `start` disagrees would
  build a coordinate no source ever stated. The comparison runs even where there is nothing left to
  fill — a fully-populated `heteroplasmy.csv` row can still contradict the table it is keyed into, and
  the promise is that such a row is *reported*, which the SNP core gets from `_verify`. `alts` is
  deliberately outside the comparison: a locus lists every ALT recorded there while a row names the
  one it is about, so `A,G` against `G` is agreement, and whether the allele can sit there is
  `hosting_verdict`'s three-valued question, already asked one step earlier.
- **Rows are mutated in place and their identity is frozen first.** Each positional model stamps
  `variant_key` and `authored_ident` at load, from the authored columns only, so filling cannot re-key
  a row.

**Three columns made it possible, all parquet-only.** `variant_key` (materialized so a consumer can
join a PGx row to `weights.parquet` without re-implementing the precedence rule), `authored_ident`
(which identity columns the author supplied — the same mechanism `VariantRow` has had since 0.5), and
`alts` on `PharmVariantRow`/`HaplotypeRow`, filled as **data, not identity**: the key is still derived
without it, so a pharm annotation keeps matching a variant at `chrom:start:ref` regardless of allele,
and what the column buys is a direct VCF join. None of the three is authored, offered by a drafting
template, or re-emitted by reverse; none is in `content_signature` (they are `exclude=True`, so a
stamped value — a pure function of the authored cells — cannot move a *content* identity, and no
already-published module's signature changes). `VariantRow`'s own two stamped fields *are* inside
`content_signature`; that asymmetry is grandfathered rather than a precedent, since changing it in
either direction moves published signatures.

**Reverse rebuilds `resolution.csv` from the positional parquets, and that is forced rather than
chosen.** Once a coordinate is filled, a reverse that dropped the lookup table would emit a spec whose
recompile leaves those parquets unfilled — `compile → reverse → compile` would stop reproducing the
artifact (Principle 7), and a PGx module carries no `weights.parquet` for the old writer to read at
all. Weights are written first and own any shared key (`variants.csv` is the only table carrying
`alts` as an *authored* fact), and the positional side contributes at most one row per key, or the
next compile would read two rows as a one-to-many rsID. Provenance is discarded exactly as before
(`source="reversed"`, `status="resolved"`, blank `fetched_at`). A module that resolved nothing anywhere
and has no `weights.parquet` gets no file, rather than a header-only sidecar invented out of an
absence.

**`resolution.csv` still gets no parquet**, and that is the repair this item deliberately did not
make: it is a build-time derived artifact whose consumers are the compiler and the enricher, and
publishing it would turn it into a consumer contract it was never designed to be. See SCHEMAS.md.

### `resolve_from_table` (`compiler/resolution.py`)

Pure, and mirrors the DuckDB resolver's semantics from the injected table:

- **fill (1:1)** — a `variant_key` with one usable locus fills the missing coordinate or rsid; the
  frozen key is kept. A coordinate-authored row also has its `alts` filled when the author left it
  out, so the resolved allele reaches the artifact and survives being written back.
- **expand (1:N)** — an rsid with N usable loci becomes N coord-keyed rows, each re-keyed by
  `derive_variant_key`. A locus whose `{ref} ∪ alts` **cannot host the authored genotype** is not
  expanded onto (`hosting_verdict`): one authored genotype is copied to every locus, so a locus that
  lacks those alleles would be emitted as a row asserting an allele it does not have.
- **verify** — a row carrying both rsid and coordinate is checked against the table; a disagreement
  warns in `best_effort` and refuses in `strict`.

GRCh38-bound (a non-GRCh38 module is skipped with a warning; `not_found`/wrong-build rows are ignored).

#### Hosting is a three-valued question (RM31)

`hosting_verdict(genotype, ref, alts)` answers *can this locus host that genotype* with `True` / `False` /
`None`, because an indel has several valid spellings and a string comparison reporting "does not fit" was
asserting a verdict it had not reached. ClinVar publishes a SHOX deletion as `X:634689 CAG>C` and Ensembl
publishes the same event as `X:634690 AGAG>AG`.

| Situation | Verdict | What the compile does |
|---|---|---|
| No `ref`/`alts` recorded | `True` | keeps the locus (lack of evidence never rejects) |
| A `*` among the alleles, on **either** side (RM59, 0.6) | — | the member is dropped and the rest is judged normally; nothing observable left is `None` |
| The raw allele strings match | `True` | keeps it — checked **first**, so normalization can only ever *add* acceptances |
| Either side names a symbolic allele (RM5, 0.6) | `None` | keeps it, reports that it did not decide — no sequence, so no flank and nothing to compare |
| The reduced allele sets match (`alleles.parsimony_reduce` strips the shared flank) | `True` | keeps it; this is what reconciles the two spellings |
| The locus is a substitution or MNV and the alleles differ | `False` | drops it — no flank, so no spelling freedom; a strand-flipped genotype stays a hard finding |
| The genotype names fewer than two distinct alleles at an indel locus | `None` | keeps it, reports that it did not decide (a homozygous call carries no frame) |
| The event **sizes** differ | `False` | drops it — re-anchoring never changes how many bases an event adds or removes |
| Same sizes, different content | `None` | keeps it, reports that it did not decide (a rotation inside a repeat, or two variants) |

**The `*` row sits above the raw comparison, and the symbolic row below it — the two are on different
axes and the placements are not interchangeable.** A symbolic allele makes a claim that cannot be
*compared*, so the whole verdict withholds; `*` makes no claim at all, so only the member goes and the
observable half must still be matched. That is why it has to run before the subset test rather than
after: `{'*','T'}` is not a subset of a real `A>T` locus, so below the comparison it fell through to the
substitution row and returned a confident `False` — dropping the locus and leaving the row unresolved,
which would have made a `*` authorable and uncompilable in the same release, refusing under `strict`
for a reason no authored edit could clear. No source spells `*` in an ALT list, so this is the ordinary
path rather than a corner. `*/T` at an `A>T` locus is `True`; `*/G` there is still `False`, because the
`G` is a real contradiction and abstention drops a member, never a verdict; `*/*` is `None`. It costs
the stability property nothing — the called side is stripped first, so `*` is never on the left of the
subset test and dropping it from the right cannot change that answer.

**Both sides, and the locus side is the half that is easy to miss.** `parsimony_reduce` strips the
flank a collection *shares*, and `*` has none, so a `*` left in the locus stops the whole set reducing
and RM31's reconciliation collapses: `hosting_verdict('C/CAG', 'AGAG', 'AG')` is `True` while the same
call against `alts="AG,*"` came back a confident `False` — a correctly transcribed indel refused under
`--strict`, advised to "replace it with the alleles the locus actually has". `ALT=AG,*` is exactly what
a joint caller emits at an overlapped indel, so this is common data, and an allele the algebra must
ignore cannot be one it ignores in only one direction.

**What that costs, measured rather than asserted.** Swept over every pre-RM59-reachable
`(genotype, ref, alts)` triple built from a spread of substitution, MNV, insertion and deletion
alleles: for a locus spelled in nucleotides — every reference example, and every module in practice,
since a `*` could not be written in a genotype before RM59 — **no verdict changes at all**. For a locus
that does spell `*`, some do, and they are corrections in both directions: `*` was blocking
`parsimony_reduce`'s flank strip *and* lending its own single character to `_indel_shaped`'s length
set, so `AG>AT` (really `G>T`) read as indel-shaped and withheld on calls that were decidable all
along. The verdicts that newly refuse are ones the tier should always have refused; a module relying on
one had a genotype that did not fit its locus, and the `*` was suppressing the finding.

Because `None` now has four causes rather than one, `resolution.undecided_reason` supplies the clause
both reporting sites append (this tier's expansion warning and the enricher's twin). They used to
assert step 9's cause — *"the same size but different content … needs the reference sequence"* — for
every withheld verdict, which for an all-`*` call sends the reader to check a reference against a
position nothing observed.

The symbolic row sits above the reductions on purpose. Below the raw comparison every remaining step is
arithmetic over characters, and a `<DEL:1500>` has none to offer — `parsimony_reduce` would read it as a
nine-character sequence and the event-size rule would then return a confident `False` computed from a
token's bracket count. Two *stated* lengths that differ are undecided for the same reason in the other
direction: symbolic notation exists **for** imprecision, so a summary length is not the kind of fact an
event size is. Note that it only ever adds acceptances, so no already-compiled module moves.

`None` is the residual only a reference sequence can settle, which this tier does not have (P2) — the
enricher does, and reports it the same way. `genotype_fits` remains as the boolean face
(`hosting_verdict(...) is not False`): it is public and **shared with the deprecated DuckDB path in
`just-dna-enricher`**, because digest parity between the two is a documented guarantee and a filter applied
on one side only would break it silently. `_check_allele_membership` asks the same predicate rather than
comparing strings itself — while it did, the two halves of the compiler disagreed the moment a spelling was
reconciled, and `strict` refused a module resolution had just accepted.

One thing the reconciliation does **not** do: the authored `genotype` keeps the frame its source published
it in, so a compiled row can legitimately carry `genotype=C/CAG` beside `ref=AGAG`. A consumer joining the
two applies the same reduction (`just_dna_format.alleles` is public and dependency-free); rewriting the
authored cell is the parked enricher-co-authoring item.

### The authored shape is recorded, not inferred

`VariantRow.authored_ident` lists which of `{rsid, chrom, start, ref, alts}` the author actually
supplied. Like `variant_key` it is stamped once at load and never re-derived, so filling or expanding
cannot disturb it, and it is materialized to `weights.parquet` for reverse to read.

It exists because the alternative — inferring the authored shape from `variant_key` — cannot work. That
key answers "which variant is this", not "what did the author write": it is identical for an rsid-only
row and an rsid+coordinate pair, and after an expansion it is the per-locus allele id with no trace of
the rsid the author wrote. Reverse therefore used to materialize resolved coordinates into
`variants.csv` and emit one row per expanded locus, which cost two things: `content_signature` moved on
every round-trip of an rsid-authored module, and each locus received a copy of the single authored
genotype — writing out, as authored fact, annotations for loci the genotype cannot describe.

**Why this is only now fixable:** dropping the resolved coordinate from `variants.csv` is safe *because
the key is canonical*. A VRS allele id names the variant without the coordinate having to be re-authored,
so the coordinate can live in `resolution.csv` where it belongs. Under the older coordinate-first keying
the coordinate was load-bearing in `variants.csv` and could not be dropped.

### The one recorded finding `strict` acts on (RM143, 0.7)

`strict` means *reproducible*, never *right*, and that is unchanged — the compiler has no reference, so
it cannot check a coordinate. But when the **enricher** has already checked one and recorded the
answer, throwing that away at the tier boundary is a separate failure: a GRCh37 coordinate pasted into
a GRCh38 module was refused by `enrich --strict`, written by `enrich` best-effort, and then built
**silently** by `compile --strict` into an artifact that is internally consistent and about a locus
5.6 Mb away.

`build_disagreement_error` refuses a `strict` compile when `verification.json` records a finding on
`genome_build_agreement`, in `validate_spec` and `compile_module` alike, with the identical error and
ahead of `output_dir.mkdir()` so a refusal writes nothing.

**Why that check and no other.** Its findings say the module's rows are on a different assembly than
the `genome_build` it declares — one authored file contradicting another, which is internal
consistency. Every other recorded finding is the module disagreeing with an **outside archive**, where
the archive is the stale side often enough that failing a build would have the format arbitrate someone
else's dispute; that is the same reasoning that keeps the ClinVar cross-check a warning under `strict`,
and it now has a parametrized test over four checks. `reference_allele` is the one worth naming: it
produces this diagnosis's own input and still does not refuse alone, because a ref mismatch has three
causes and only one of them is an assembly.

**Three things it does not do**, each with a test, because each would be a worse defect than the one it
fixes:

| state of the record | what happens |
| --- | --- |
| no `verification.json` at all | **silent** — an unverified module is the ordinary case, and refusing on absent evidence reads unknown as wrong |
| `genome_build_agreement` with `findings=0` | **silent** — a clean bill; the gate keys on findings, never on the record's presence |
| `genome_build_agreement` `skipped` (what `--offline` writes) | **silent** — nobody asked, which is not nothing-wrong |

A stale attestation is dropped by the reader before the gate sees it, which is the right order: bytes
that moved since the check ran are bytes the check did not judge.

### Coverage is reported by the pre-flight too (RM141, 0.7)

`compile --strict` refuses a module whose variants still have no position after resolution — a partial
artifact is not byte-reproducible, which is the failure behind *"my local hash differs from the
published one"*. Until 0.7 `validate --strict` said nothing about it, so a spec whose `resolution.csv`
covered only some of its variants passed the pre-flight clean and was refused by the compile
immediately after.

That is the parity rule's own failure shape, and it hid behind the rule's exemption. What stays
compile-only is *a check reading resolved rows*; whether the injected table **can** place an authored
row is arithmetic over bytes the pre-flight has already loaded, and needs no resolution to have run.
The exemption is about resolved rows, not about the word "resolution".

`resolution.unresolved_subjects` is the predicate `resolve_from_table` applies, shared by both callers
rather than restated — a second implementation of `_usable_loci`'s three exclusions (a `not_found`
sentinel, a row recorded under another build, a row with no `chrom`) is exactly the drift this avoids.
Under `strict` the pre-flight appends the compile's error **verbatim**; a pre-flight that refused for
its own differently-worded reason would still send an author hunting.

Three behaviours to know:

| the module's table | what is reported |
| --- | --- |
| present, covers every row needing a position | nothing |
| present, covers some | `rsid_unresolved` per uncovered row, then the strict refusal — the row is absent from a file that **was** consulted |
| absent entirely | `resolution_not_injected`, once, plus the strict refusal — nothing was consulted, so nothing is named row by row |

`--no-resolve` silences the check the way it silences the fill: resolution is off by request, and
`resolution_disabled` already says so once with its row count.

**One finding, though two passes produce it.** `compile_module` runs the pre-flight in `best_effort`
whatever its own mode, so both reach this finding for the same subject; the compile de-duplicates on
the message (the `_check_contig_ploidy` idiom). That is safe here for the reason the rule requires —
neither message embeds a count resolution could change, so two passes over one subject produce the
identical sentence rather than two differing by a number.

### The mishap matrix

Five identity columns the author may or may not supply, crossed with what the table says about them, is
a finite set. Every combination is either a round-trip fixed point on **all three** signatures, or it
fails in `strict` — enumerated and enforced in `compiler/tests/test_resolution_matrix.py`.

| Authored shape / mishap | `best_effort` | `strict` | Round-trip |
|---|---|---|---|
| rsid only, 1:1 fill | ✅ | ✅ | stable |
| rsid only, one-to-many (every locus can host the genotype) | ✅ | ✅ | stable |
| rsid only, pseudoautosomal pair (X + Y, same place) | ✅ | ✅ | stable — the compiler names it as one place; the enricher decides whether both reach the table |
| coordinate + alt, rsid resolved | ✅ | ✅ | stable |
| coordinate only, rsid **and** alt resolved | ✅ | ✅ | stable |
| pair (rsid + coordinate), table agrees | ✅ | ✅ | stable |
| **ambiguous** — several rsIDs for one allele | ⚠️ warning | ❌ refuses | stable |
| expansion drops a locus that cannot host the genotype | ⚠️ warning | ❌ refuses | unstable |
| every candidate locus contradicts the genotype → unresolved | ⚠️ warning | ❌ refuses | unstable |
| `not_found` — the table records the rsid as genuinely absent | ⚠️ warning | ❌ refuses | unstable |
| no resolution row at all | ⚠️ warning | ❌ refuses | stable (nothing to lose) |
| authored `ref` contradicts the table | ⚠️ warning | ❌ refuses | unstable |
| authored coordinate contradicts the table | ⚠️ warning | ❌ refuses | unstable |

Three things the table encodes that are worth saying out loud:

**Instability always means the *table* cannot be reproduced, never the bytes.** `artifact.digest` is a
fixed point in every row above, including the unstable ones — a module that compiles at all compiles to
the same bytes twice. What is lost is `resolution_signature`: a `not_found` sentinel has no coordinate
so reverse writes no row for it; a dropped locus is simply not in the artifact; and where an authored
value contradicts the table the authored value wins, so the table's version is gone. Each is a real
reduction in what the injected table said, which is exactly why `strict` — whose contract is a
reproducible artifact — will not build on it.

**`ambiguous` is the one exception in the other direction.** It *is* round-trip stable, because the
enricher writes a single row carrying the deterministic pick while the candidate list rides in
`rsid_alternates`, which is provenance and outside the fact set. Strict still refuses, not because
anything is lost but because the label is a pick among equals rather than a finding, and an
all-or-nothing artifact should not rest on one. (An earlier draft of this analysis concluded ambiguity
could not be stable — from a hand-written two-row fixture the enricher would never produce. The real
shape is one row.)

**A contradiction is an instability, not a difference of opinion.** An authored coordinate that
disagrees with the table used to be a warning and nothing more. It has to be stronger: the artifact
keeps what the author wrote, so the table's position does not survive a reverse, and the next compile
resolves from a table that no longer says what it said.

## Reverse

`reverse_module` reads the **parquet artifact only** (never `manifest.json`) and emits into `output_dir`:
`module_spec.yaml` (always), `variants.csv` + `resolution.csv` (when `weights.parquet` exists;
`resolution.csv` gated on `write_resolution=True`), `studies.csv` (when present), one CSV per present
table kind, and one CSV per derived-fact sidecar whose parquet is present (`frequencies.csv`,
`gene_metrics.csv`, `literature.csv`, `gene_validity.csv`, `clinical_assertions.csv`, `sources.csv`),
plus `overrides.csv` when `overrides.parquet` is present (0.7, RM124).

- **Preserved (round-trip-critical, Principle 7):** every authored `VariantRow`/`StudyRow`/table value;
  genotype phase (the `phased` bit re-emits `A|G` vs sorted `A/G`); tri-state bools; `priority` verbatim;
  poly-effect annotations keyed on `(variant_key, conclusion, negatives)`.
- **The authored shape is restored, not guessed:** `authored_ident` says which identity columns the
  author wrote, and reverse emits exactly those — an rsid-only row comes back rsid-only, a position-only
  row comes back position-only, a pair comes back as a pair. An expanded one-to-many rsid collapses back
  to the **single** row it was authored as, rather than one row per locus. See § Resolution for why the
  stored key alone cannot answer this and what it cost when reverse tried.
- **`resolution.csv` emission** carries the resolved facts back: one `ResolutionRow` per distinct
  positioned fact, keyed on the **authored** key (so an expansion's N loci are joinable to the one row
  they came from) with `locus_index` counting within that key, and `source="reversed"`,
  `status="resolved"`. So **`reverse → compile` reproduces the identical `artifact.digest` with no
  reference and no network** — hardening Principle 7's round-trip from reference-dependent to
  self-contained.
- **The derived sidecars come back POST-overlay, and `overrides.csv` comes back beside them** (0.7,
  RM124). The overlay is applied at compile, so what reverse reads out of the parquets is already the
  corrected table — and it re-emits the overlay too, which means **the overlay applies twice and the
  fixed point is checked by test rather than assumed**. It holds because all three operations are
  idempotent set operations: an update to a value already present, an insert of a row already keyed
  `(subject, member)`, and a suppress of a row already absent are each a no-op. The alternative —
  emitting the *pre*-overlay table so the apply happens exactly once — would need the overlay to record
  the value it replaced, which is a derived cell inside an authored table and rots the moment the source
  moves. `overrides.csv` is written at the spec **root** under its one legal name, not through
  `sidecar_write_path`: it is authored, like `variants.csv`.
- **Provenance is deliberately dropped** on the way back: `source`/`status`/`fetched_at` are reset and
  `rsid_alternates`/`rsid_current`/`rsid_status` are not written, because those columns are kept out of
  the fact set precisely so they never enter the artifact — there is nothing for reverse to read. Recover
  them by re-running the enricher.
- **Derived-fact sidecars** round-trip through the same generic writer, minus the columns that are
  recomputed rather than stored: `allele_frequency` is derived on write and is not a `FrequencyRow`
  field, so it falls away by construction rather than by a special case, and re-deriving it on the next
  compile reproduces the identical parquet.
- **Normalized:** title/description/report_title fall back to name-derived defaults; icon/color from
  args; curator/method from the most-common column value.
- **Recovered from `manifest.json`, not normalized: `genome_build`.** It reaches the artifact through the
  manifest and no parquet column, and reverse used to re-emit the constant `GRCh38` — listed here, for a
  release, as a harmless normalization "out of the digest". It is not out of the digest, because the
  build decides the *identity key*: a GRCh37 module reversed as GRCh38 recompiled with `ga4gh:VA.…` keys
  minted for GRCh37 coordinates, so `artifact.digest` moved **and** the new key asserted an allele at a
  base the module never named. `_genome_build_from_artifact` reads it; `genome_build=` (CLI
  `--genome-build`) overrides; a bare parquet directory with no manifest falls back to `GRCh38`, the
  format's own default. See `reference_examples/grch37_build/`.
- **Lost (manifest-only, out of `artifact.digest`):** `authorship`, `panel` (**deprecated in 0.6,
  removed at 1.0 — RM4**; see below), `provenance`, `logo`,
  `readme`, and the **verification attestation** (RM45) — `verification.json` is not in the artifact,
  so there is nothing for reverse to read and inventing one would mint a claim nobody put; a reversed
  module carries no `manifest.verification`, which is the honest *says nothing*, and re-attesting
  means re-running the checks. **The RM73 closure rides that document and is lost with it**, so a
  reversed spec is open and warns until a human closes it — deliberate, since reverse holds no key and
  no standing to declare someone else's authoring finished. That asymmetry costs nothing while the
  finding is a warning (warnings feed no digest and no signature, so the fixed point is untouched),
  and it is precisely what blocks promoting the finding to a refusal at 1.0: under a gate, step 3 of
  `compile → reverse → compile` would refuse on every module. The three candidate answers are recorded
  in [ROADMAP_1_0.md](ROADMAP_1_0.md) § RM73 (gate half). A
  consumer needing these reads `manifest.json` (preserved verbatim by the forward compile). The test of
  whether something belongs on this list is whether losing it can change a parquet byte — which is why
  `genome_build` moved off it. `readme` joins `logo` here for the same reason and with the same
  consequence: `reverse` writes no readme into the re-emitted spec, so a recompile of a reversed module
  attests none — the three signatures are still a fixed point, because prose was never in any of them.

## Output artifact & hashing

**`ARTIFACT_PARQUETS` is the `artifact.files` listing order** — the tuple's own order, which
`build_artifact` walks, skipping absent files so a module lists exactly the parquets it has:

```
weights  annotations  studies                                    ← the SNP core
activity_phenotype  copynumbers  repeat_alleles  heteroplasmy
haplotypes  allele_function  diplotypes  pgs  pharm_variants      ← the nine table kinds
frequencies  gene_metrics  literature  gene_validity
clinical_assertions  gwas_effects                                 ← the derived-fact sidecars
sources                                                           ← the licence table
overrides                                                         ← the authored overlay (0.7)
```

**It is not digest order, and this section said it was.** `artifact_digest` sorts the listing by name
before hashing (`integrity.py`), so the tuple's position is invisible to the digest and a name is what
places an entry — `overrides.parquet` hashes between `literature.parquet` and `pgs.parquet` however
late it sits in the tuple. What the position does govern is the order a consumer iterating
`artifact.files` sees. Appending is still the right move for a new parquet, but the reason is the
listing, not the hash; what keeps an already-published digest still is that the module has no such
file at all.

Twenty names. `LEAD_PARQUETS` is the ten carrying a module's own annotation rows — `weights` plus the
nine table kinds — which is the publisher's *is this a module* rule and what discovery probes.

**The per-parquet column lists are deliberately not reproduced here.** They are derivable from the
models, and a hand-kept column list is precisely how `SOURCES_FIELDNAMES` lost a column
(`@fieldnames-from-model`); use `just-dna-compiler describe` or read the model. A point-in-time listing,
including which columns the compiler stamps rather than reads, is in
[audit/COMPILER_FROM_CODE.md](audit/COMPILER_FROM_CODE.md) § 5 — dated evidence, not a maintained list.

- **`ARTIFACT_PARQUETS`** (feed `artifact.digest`; `_OUTPUT_FILES` until 0.6): `weights`/`annotations`/
  `studies.parquet` + the 9 table-kind parquets + `frequencies.parquet` / `gene_metrics.parquet` /
  `literature.parquet` / `gene_validity.parquet` / `clinical_assertions.parquet` / `sources.parquet`
  when present. The sidecars enter
  the digest because a module carrying frequency data genuinely *is* different content — but adding one
  leaves the SNP core's bytes untouched (an explicit test). **It is public because the publisher tier
  has to agree with it**: `just_dna_enricher.upload` derives its allow-patterns from this tuple, after a
  hand-kept copy covering three of the sixteen names silently dropped the rest at upload (S35/RM89).
  `LEAD_PARQUETS` beside it names the ten that carry a module's own annotation rows — `weights` plus the
  nine 0.4 families — which is the publisher's "is this a module" rule and what discovery probes.
- **`_INPUT_FILES`** (feed `manifest.inputs`, raw-bytes hashed): `module_spec.yaml` + `variants.csv` +
  `studies.csv` + the 9 table-kind CSVs — the authored surface, and the reason only the *other* files
  gained a second legal name and location in 0.6. **`resolution.csv` is deliberately NOT here** (nor in
  `ARTIFACT_PARQUETS`) — it is a multi-producer artifact hashed only by the normalized `resolution_signature`
  (a raw-bytes hash would be unstable across enricher/human/reverse producers). `frequencies.csv`,
  `gene_metrics.csv`, `literature.csv` and the 0.6 pair `gene_validity.csv` / `clinical_assertions.csv`
  are out for exactly the same reason, each hashed by its own `*_signature`. `provenance.json` is
  likewise out of the digest.
- **The derived-fact sidecars are deliberately NOT `_TABLE_KINDS`.** Those are authored DSL tables with
  `AuthoredModel` semantics, the reserved-namespace guard, duplicate-key checks and raw-byte input
  hashing. A machine-produced reference-fact table is a third category — injected, fact-hashed,
  human-overridable — and folding it in would blur the line the 0.5 rework drew.
- **Manifest `Compilation` fields the compiler populates:** `compile_success`, `compiled_by`,
  `compiler_version`, `ensembl_reference`, `compiled_at`, `warnings`, and the 0.5 resolution provenance —
  `resolution_mode` (policy), `fully_resolved` (outcome — orthogonal axis, P5), `resolution_subjects`
  (0.6 — the denominator that flag covers), `resolution_signature`, `resolution_sources`. All out of
  `artifact.digest`. The trust rule is `resolution_subjects > 0 and (resolution_mode == "strict" or
  fully_resolved)`; without the first clause it is vacuously satisfied by a module that resolves
  nothing.
- **Manifest `frequency` / `gene_metrics` blocks (0.5):** `signature`, `sources`, `datasets`,
  `row_count`, plus `populations`/`variant_count` on the former and `genes` on the latter. Separate
  blocks rather than extra fields on `Compilation`/`Resolution`, which are about rsID↔coordinate
  resolution only. Out of `artifact.digest`. `datasets` is the field a consumer reproducing an ACMG
  BA1/BS1 filter reads to know *which release* it is filtering against.

The three hashes and how they compose into `(content_signature, resolution_signature, compiler_version)
⟹ artifact.digest` are documented in [SCHEMAS.md § identity & integrity](SCHEMAS.md#identity--integrity).

## Deterministic ordering — what is preserved, what is normalized

Parquet bytes depend on row order, so ordering is part of `artifact.digest` rather than a nicety. The
asymmetry below is intended: **rows are preserved, presentation is normalized.**

**Preserved.**

- **Authored row order**, through compile → reverse → recompile.
- **Expansion order within a one-to-many rsID.** `_sorted_loci` sorts on
  `(locus_index, chrom or "", start or 0, ref or "")`, which matches the deprecated DuckDB path's
  `ORDER BY id, chrom, start, ref` — the two produce byte-identical parquet, which is what let that
  path be retired without moving a digest.
- **`_symbolic_findings`** sorts on `(table, reason, index, column)`, so the messages built from it are
  byte-stable. They reach `manifest.compilation.warnings`, which is artifact-visible.
- **`table_citations`** (and its narrower sibling `binning_citations`) returns first-occurrence order
  rather than sorted order, because it feeds emission order.
- **`Frequency.populations`** is in canonical order (`population_sort_key`, `global` first). Every
  *other* manifest facet list is sorted — this one is the exception, deliberately.
- **`_write_resolution_csv`** emits weights first and never re-emits a key from the positional pass, so
  `variants.csv`'s `alts` always wins.

**Normalized, not preserved.** Column order and cell formatting in every reversed CSV; the
`curator`/`method` blank-vs-explicit split; unphased genotype allele order.

**Deterministic tie-breaks where the library gives none.** `_module_name_from_parquets` uses `min()`
over `unique()`, and `_most_common` uses `min()` over `mode()`, because polars orders neither. This is
the concrete form of the standing rule: never derive an emitted row or a manifest field from
`set`/`dict` iteration or from `mode()`/`unique()` without an explicit sort or tie-break.

## Warning texts a consumer keys on

### Since 0.7 the channel also carries codes and an actionability split (RM131)

`manifest.compilation.warnings` still carries every finding, with its exact text — nothing that greps
a phrase broke, and nothing here supersedes the fragments below. Two derived fields ship **beside** it:

| Field | What it is |
|---|---|
| `compilation.warnings` | the complete list, unchanged; the same sentences in the same order |
| `compilation.carried` | the subset **no edit to the spec directory can clear** — a limit of this tier or a fact of a source. Subtract it from `warnings` for the set an author still owes work on |
| `compilation.warnings_summary` | `{code: count}`, keys from `vocab.VALID_WARNING_CODES`, values summing to `len(warnings)` so the digest accounts for the whole channel |

The same three fields are on `ValidationResult`, `CompilationResult` and `ClosureResult`, filled on
every path including a failed compile. `manifest.json` sits outside `artifact.digest` (a Merkle root
over the parquet `FileEntry` list), so adding them moved no hash — and both are listed in
`release_records.EXCLUDED_MANIFEST_FIELDS`, routed to the `warnings` axis, because they move exactly
when `warnings` moves.

A code names **the finding**, never the function that builds it, and one code carries one remediation:
two sentences cleared by the same edit share a code and say which cell (the weight-sign pair, the five
orphan fact tables), two cleared differently do not. The set is published, so it is permanent within
the major — additions are minor-legal, re-spellings are not.

**Carried findings** — the eleven an author cannot clear, and the reason each is on this side:

| Code | Why no authored edit clears it |
|---|---|
| `non_grch38_variant_keys` | VRS allele identity is GRCh38-only, so a non-GRCh38 module is coordinate-keyed |
| `resolution_skipped_cross_build` | resolution and the positional fill are GRCh38-bound (RM15) |
| `contig_ploidy_undecidable` | the build carries no pseudoautosomal table here, so ploidy cannot be decided |
| `rsid_expanded_to_multiple_loci` | the source maps one rsID onto several loci; that is a fact about dbSNP |
| `locus_hosting_undecidable` | deciding needs the reference sequence, which this tier never fetches (P2) |
| `vrs_id_unverifiable` | the recomputation is beyond this tier — `_carried_vrs_warnings` is the shape the split generalises |
| `vrs_coverage_incomplete` | the alleles a VA does not reach; minting more is not an authored edit |
| `measurement_spans_bins` | the format has no reading for an interval that straddles a boundary (RM56) |
| `verification_findings_recorded` | a disagreement with an archive, where the archive is the stale side often enough that nothing is owed |
| `gene_validity_superseded` | a curating body re-curated its own claim; the only edit available is deleting a true record |
| `gene_validity_currency_undecidable` | the source published several curations of one claim and not enough to order them |

**Every published code**, by the surface it comes from. Everything not in the table above is
actionable, which is `vocab.ACTIONABLE_WARNING_CODES`, derived by subtraction:

- **spec directory / `module_spec.yaml`** — `table_file_misplaced`, `table_file_near_miss`,
  `sidecar_spelling_deprecated`, `module_version_coerced`, `panel_block_deprecated`
- **coordinates and the build** — `non_grch38_variant_keys`, `contig_ploidy_undecidable`,
  `contig_ploidy_mismatch`
- **resolution** — `resolution_disabled`, `resolution_not_injected`, `resolution_skipped_cross_build`,
  `positional_identity_contradicted`, `positional_rows_unjoinable`, `rsid_unresolved`,
  `rsid_without_resolution_label`, `rsid_expanded_to_multiple_loci`, `rsid_ambiguous`,
  `rsid_coordinate_disagrees`, `locus_hosting_undecidable`, `locus_cannot_host_genotype`,
  `rsid_no_hosting_locus`
- **VRS** — `vrs_id_unverifiable`, `vrs_coverage_incomplete`
- **`variants.csv` coherence** — `weight_sign_disagrees_with_effect`, `genotype_allele_not_at_locus`,
  `effect_allele_not_at_locus`, `genotype_coverage_gap`, `quality_floor_inverted`,
  `missing_allele_marker_in_alts`, `vcf_pointer_key_collision`, `vcf_pointer_unselected_element`,
  `composite_gene_cell`, `symbolic_allele_unusable`
- **binning tables** — `bin_tiling_inferred`, `bin_tiling_contradicted`, `bin_coverage_gap`,
  `bins_ungrounded`, `measure_field_fractional`, `measurement_spans_bins`, `deprecated_bin_modifier`
- **PGx tables** — `star_allele_undefined`, `diplotype_definitions_identical`,
  `diplotype_phase_ambiguous`
- **studies and literature** — `study_variant_orphan`, `duplicate_study_citation`,
  `p_value_encodings_disagree`, `study_effect_allele_not_at_locus`, `citation_not_in_pubmed`,
  `literature_row_uncited`, `quote_counter_stale`, `quoted_article_license_restrictive`
- **sources and licensing** — `source_row_unused`, `source_terms_unrecorded`,
  `declared_license_disagrees`
- **the injected fact tables** — `derived_row_orphan`, `faf95_exceeds_frequency`,
  `oe_lof_outside_interval`, `oe_lof_disagrees_with_counts`, `clin_sig_contradicts_frequency`,
  `clin_sig_concordance_contested`, `gene_validity_superseded`,
  `gene_validity_currency_undecidable`
- **the overlay** — `overlay_update_unmatched`, `overlay_targets_missing_table`,
  `overlay_rows_suppressed`
- **verification and closure** — `verification_two_copies`, `verification_unreadable`,
  `verification_stale`, `verification_findings_recorded`, `module_not_closed`,
  `closure_discarded_unreadable_record`

The two `gene_validity_*` codes are new in 0.7 (RM108) and are the first fact-table findings the
**pre-flight also computes**, so `validate` reports them exactly as `compile` does. They stay apart on
purpose: `gene_validity_superseded` says a later curation replaced an earlier one and the manifest now
publishes the later verdict, while `gene_validity_currency_undecidable` says several curations exist
and nothing orders them — a tie on `classification_date`, or a row stating none — so every
classification in that group is still published. One number meaning both would tell a reader the
archive moved on when it had simply not said enough.

`overlay_rows_suppressed` is new in 0.7 and is the one finding here that reports a *decision* rather
than a defect: a `suppress` removes a row and leaves no trace of the removal in the build product, so
the overlay says so — one line per **reason**, with a count, and counted over the overlay's own rows
rather than over the rows removed. That is what keeps it stable across `compile → reverse → compile`,
where by the second lap the derived table is already post-overlay and the suppress matches nothing.

```
overrides.csv: {count} suppress override(s) remove {table} row(s) from the compiled artifact,
where nothing else records the removal: {reason}
```

`test_warning_codes.py` walks the emission sites and asserts an equality against the vocabulary in
both directions, so a code with no emitter and an emitter with no code both fail; it also asserts this
document lists every member, because a catalogue missing one sends a reader hunting for it.

**Two consequences worth knowing before you build against this**, both recorded rather than left to be
discovered:

- **A summary is either empty or complete, never partial.** `classify` **withholds** — an empty
  `carried` and an empty `warnings_summary` — when a channel carries no classified findings at all,
  which is what a caller passing plain prose into `CompilationResult(warnings=[...])` gets; that call
  has been legal since 0.6 and Principle 3 keeps it legal. It refuses only a *part*-classified channel,
  which no legitimate caller can produce. So read an empty summary as *this compile did not classify
  the channel*, never as *there is nothing to report*, and read a non-empty one as accounting for the
  whole of `warnings`.
- **The code vocabulary is closed, so an older reader refuses a newer manifest.** `warnings_summary`
  validates its keys, and `read_manifest` raises on a code added after the `just-dna-format` you have
  pinned. That is the standing cost of every closed vocabulary on a published field here
  (`VerificationRecord.check` is the shipped precedent) and Principle 6 takes it deliberately, but
  "additive" describes the *writer*: a consumer reading manifests from newer compilers upgrades the
  schema package alongside them.

**`carried` holds full message text, which nearly doubles the channel** — measured at 1.84× across the
reference corpus, 1.96× on `pathogenic_clinvar`. That is the shape the item decided (a list beside,
so a consumer subtracts) rather than an oversight, and the cheaper encodings are weighed in
[ROADMAP.md § RM138](ROADMAP.md).

### The phrases

**A warning's text is an API.** The manifest carries the prose and, for anything published before the
structured field existed, no other handle — so a downstream consumer greps it. Four fragments are named
constants for exactly that reason:

```python
UNJOINABLE_PHRASE     = "have no chrom+start"
QUAL_INVERSION_PHRASE = "QUAL means the opposite thing on the record this row is read from"
MISSING_ALLELE_PHRASE = "is VCF's MISSING marker, not an allele"
UNCLOSED_PHRASE       = "records no closure"
```

`UNJOINABLE_PHRASE` has a **named external consumer**: `just-dna-registry` 0.11.3 pins
`UNJOINABLE_MARKER = "have no chrom+start"` in its facet builder. The structured replacement
(`manifest.compilation.positional_rows` / `positional_rows_placed`) shipped in 0.6 and the phrase is
still **not** retired, because artifacts published under 0.5 carry neither field. Retiring it is a
decision about the published corpus, not about this code.

The positional-joinability sentence, as its format string — the counts and both trailing clauses are
computed per table, so no example is invented here:

```
{csv_name}: {unplaced} of {rows} row(s) have no chrom+start, so this table joins by rsID only —
a VCF whose ID column is empty matches none of them. {detail}.{partial_note}
```

`{detail}` is one of exactly three sentences, and the distinction between them is the whole point —
*not consulted*, *consulted and found nothing*, and *consulted and refused to guess* are three
different situations a consumer must not collapse:

- `the resolution table was not consulted for this table — see the skip reported above` (or
  `resolution.csv names N of them and was not consulted for this table — …`);
- ``no resolution.csv row places them — run `just-dna-enricher enrich` first``;
- `resolution.csv names N of them, but at more than one locus or at one the row's own allele
  contradicts, so the compiler leaves them unplaced rather than picking`.

The VRS coverage headline, as its format string, followed by one indented `  {count} allele(s):
{reason}` line per gap reason, sorted by descending count then reason:

```
VRS allele identity covers {identified}/{alleles} allele(s) in resolution.csv ({pct}) —
{missing} carry no ga4gh:VA. id. Anything keying on the VA sees only the covered fraction.
```

**Its twin, for ids that are present and that this tier cannot recompute, is grouped the same way
since S67** — one line per reason, descending count then reason, three `variant_key`s named
and the rest counted:

```
{count} allele(s): vrs_id could not be verified — {reason}; carried unverified ({a}, {b}, {c}, and
{n} more).
```

The two halves used to disagree about shape, and which half an allele landed in was decided by
whether the enricher happened to mint an id for it — nothing else. So `_vrs_coverage` aggregated the
alleles with **no** id while `_verify_vrs_ids` emitted one line per id **present**, and warning noise
ran *inversely* to how well-resolved a module was: 80 of one 101-row module's 85 warnings came from
here, with the three findings its author could act on at positions 83, 84 and 85, while a 57,595-row
module with nothing minted was quiet. `_BLAME_ROW` findings are **not** grouped — they are errors,
they are rare, and each names a row that contradicts itself, which is the one thing a per-reason line
would take away.

Three more sentences worth quoting exactly, because each states a consequence rather than a status: the
closure reminder (`This module records no closure: … Compiling without one is a warning today;
requiring it is filed for 1.0 (RM73).`), the symbolic-allele drop (`Those row(s) are DROPPED from the
compiled artifact — reverse will not re-emit them — and --strict refuses instead.`), and `--no-resolve`
with an injected table present, which spells out that the flag names Ensembl but is the master switch
and that there is no "do not reach the network" flag because the compiler never does.

**The overlay's two warnings (0.7, RM124), and there are only two on purpose.** `overrides.csv`
applies before any check reads a derived row, so what a check reports is what the module asserts. No
operation reports its own no-op — `reverse_module` emits the post-overlay table plus the overlay, so
on a recompile update-already-equal, insert-already-present and suppress-already-absent are all three
true of a healthy module, and reporting any of them would make a module and its own round trip
disagree on `manifest.compilation.warnings`. What is left is the pair an overlay operation cannot
manufacture for itself. Note the third reading in the first message: on a recompile of a *reversed*
module the row may be missing because the compiler dropped it before the parquet — `literature.csv`
loses its uncited rows and `resolution.csv` has no parquet at all — so the correction is fine and the
table is short. That case reports on lap 2 and not on lap 1.

```
overrides.csv: {n} update override(s) name a row {table} does not carry: {subjects}. Three readings and
nothing here separates them — the subject/member may be mistyped, the source may have stopped
publishing the row the correction was about, or the compiler dropped the row before the parquet so a
reversed module cannot carry it. Neither an insert nor a suppress reports this: an insert creates the
row and a suppress is satisfied by its absence.

overrides.csv corrects {tables}, which this module does not carry. An overlay lies on top of a derived
table and never creates one, so those rows change nothing. Run the pass that writes the table, or drop
the override rows.
```

Both warn in **both** modes and both are aggregated into one sentence rather than one per row. The
consequence a consumer should know is the one no message can carry: **a `suppress` with a typo'd
subject does nothing, forever, and cannot warn** — check a suppression by reading the compiled table.

The uncited-literature sentence names its sites, so it has been reworded twice as sites were added —
`no study or bin` in 0.6, `no study, bin or pharm row` in 0.7. The **code** `literature_row_uncited` is
the stable handle; the phrase is pinned by the suite, which is what makes each rewording deliberate.

**The concordance record's one warning (0.7, RM130).** `clin_sig_concordance.csv` names the subjects
where the module's clinical call and an annotation authority's disagree, or where two authorities
disagree with each other, and this is the sentence that says so at `validate` and at `compile`:

```
clin_sig_concordance.csv records {n} contested subject(s): {opposed} of them opposed calls
(pathogenic-class against benign-class)[, {k} with an authority that could not be consulted]. A
contested subject is a question, not a defect — half the time the archive is the stale side, which is
why this never fails a build in either mode. Answer one by adding a row to overrides.csv naming table
'clin_sig_concordance.csv', the subject's variant_key and its genotype, with the reason you stand by
the module's call.
```

Three things about it are decisions rather than wording. It **never escalates under `--strict`**, for
the reason the check that produced the rows does not: escalating would have this format arbitrate a
clinical dispute. It is **actionable rather than carried**, unlike `verification_findings_recorded`
one section down, and the difference is real — a number sitting in `verification.json` is not
something an author can move, while a contested row is answered by writing an overlay row, and the
count here is taken over the **post-overlay** table so answering one clears it. And it names
`overrides.csv` and **never `provenance.json`'s `outranks`**: the two are the same idea one table
apart, 0.7 settled the overlap as a succession in the overlay's favour, and an author meeting this
warning for the first time should be sent to the mechanism that survives 1.0.

The count is embedded although both passes emit the sentence. That is normally the trap where a
message carrying a number is rebuilt from inputs resolution changed in between; it is not one here,
because no compile step between the two passes touches this table or the overlay above it, so both
passes reach a byte-identical sentence and the existing de-duplication collapses them.

**Substrings the suite pins as contract**, so changing one is a deliberate act rather than a reword:
`test_validate_agrees_with_compile.py` holds `"forbid sale"`, `"does not match the id recomputed"`,
`"could not be verified"`, `"p_value_num says"`, `"not among the"`, `"IUPAC ambiguity code"`,
`"not valid YAML"`, `"must be a mapping"`; `test_strict_compile.py` holds `"unresolved genomic
positions"`; `test_roundtrip_regressions.py` holds `"pointer, not an expression"`.

## CLI, and what it maps onto

`just-dna-compiler` (Typer) is a thin shell over the Python API. Exit 0/1, CI/registry-gateable.

| Command | Python API | Notes |
|---|---|---|
| `validate <spec>` | `compiler.validate_spec` | `--strip-identity` / `--authority-key`. Read-only — it never stamps a closure |
| `close <spec>` | `compiler.close_module` | `--by`, `--private-key`. Writes the RM73 closure into `verification.json`, bound to the authored bytes. Refuses an invalid spec; a warning does not refuse |
| `compile <spec> <out>` | `compiler.compile_module` | `--strict/--no-strict`, `--resolve/--no-resolve`, `--compression`, `--compiled-by`, and the **deprecated** `--ensembl-cache` (routes to the enricher; removed at 1.0). Prints `digest`, `content_signature`, `resolution_mode`/`fully_resolved`/`resolution_signature` |
| `signature <spec>` | `compiler.content_signature` | no compile, no reference |
| `reverse <parquet_dir> <out>` | `compiler.reverse_module` | `--resolution/--no-resolution` (default on) + display overrides |
| `verify <module_dir>` | **`format.integrity.verify_manifest`** | `--public-key`, `--check-inputs/-logs/-provenance/-logo/-readme/-derived` |
| `keygen` | **`format.signing.generate_private_key_pem`** + `public_key_b64_from_pem` | `--out` (refuses to overwrite) |
| `sign <module_dir>` | **`format.signing.sign_digest`** | `--private-key` |
| `reference` | **`format.reference.authoring_reference`** / `json_schemas` | `--summary`, `--schemas` |
| `template <kind>` | `draft.blank_template` + `authoring_requirements` | the SNP core, every optional table kind, **and `sources.csv`** |
| `stub <kind>` | `draft.stub_template` | `--rows` |
| `requirements <kind>` | `draft.authoring_requirements` | `--json` |
| `scaffold <spec>` | `scaffold.scaffold_module` | `--kind`, `--rows`, `--dry-run` |
| `describe <kind>` | `hints.describe_table` | one table's columns + pick-lists, each column's `category` and its vocabulary's per-member `notes` |
| `hint <kind>` | `hints.inspect_rows` | `--file`/`--row`, `--json` |
| `sweep <before> <after>` | `sweep.compare_outputs` + `gate_findings` | `--spec-root` (compile AFTER with the installed compiler), `--release` (run the release gate; exit 1 on a finding), `--json`. A **release-sequence** command, not an ordinary test — it needs the previous release installed |

**`--no-resolve` is the master switch, not an Ensembl switch** (S14). With an injected `resolution.csv`
beside the spec it used to compile *successfully* with `chrom=None` on every weight row — a silent
success, the worst shape a mistake takes. It now warns and **names the size of what it discarded**
(`N row(s), covering K variant key(s)` — rows, not keys, since a one-to-many rsid contributes several),
for the same reason `vrs_alleles` ships beside `vrs_alleles_identified`: a warning that quantifies over
a table should publish the denominator. The message also states that there is **no flag for "do not
reach the network"**, because the compiler never does (Principle 2, verified branch by branch including
the deprecated `ensembl_cache` path, which reads an injected local cache) — omitting this flag *is* that
request. Renaming the parameter is a 1.0 conversation; it is part of a published signature.

**Four rows are bold because they belong to `just-dna-format`, which ships no CLI of its own** —
Typer would breach its pydantic-plus-cryptography dependency floor (Goal 2). So anything the schema
tier owns that a *user* needs has to surface here, and three of the four did not until 0.5:

- `sign --private-key` demanded a key file the toolchain could not produce, and `verify --public-key`
  demanded a string only `public_key_b64_from_pem` could derive. Signing was therefore CLI-complete
  only for someone willing to write Python — the exact gap `verify` had been added to close, left
  open one step upstream. `keygen` closes it; the key is unencrypted PKCS#8 (what `sign_digest`
  reads), which is a deliberate limit rather than an oversight: this bootstraps a key, it is not key
  management, and a passphrase prompt would imply custody guarantees nothing here provides. It
  **refuses to overwrite** an existing key, because every signature made with the old one would stop
  verifying and a published artifact's bytes are never mutated.
- `authoring_reference()` had no route at all, which hurt most for the consumer that most needs it:
  an MCP surface offering an author the valid values had to import `just_dna_format.reference` and
  write Python. `describe` answers that for **one** table; `reference` answers it for all of them
  plus the vocabularies, the open-vs-closed flag, `REQUIRED_ANY_OF` and the palette.

**`template sources.csv` used to deny the table existed (S21, 0.5.4).** `DRAFTABLE` held the SNP core
and the optional table kinds, so `blank_template("sources.csv")` answered *"is not an authored table of
this format"* — false, and said by the surface an author reaches for **instead of** reading the models,
which is what the consumer who reported it then had to do. The other three fact sidecars stay out
because an enricher pass writes them and nobody starts one by hand; this one the schema instructs a
human to write (a source read by hand leaves no `source` cell for the coverage check to find) and the
compile licence gate reads it and nothing else. Its natural key is `(source, layer)` — the same one
`licensing.merge_sources_csv` merges on, borrowed for the reason every `_CORE_DUPE_KEYS` entry is
borrowed: a draft must not append a row the other writer treats as already present, and one source
legitimately appears at two layers.

**A drift the audit found in the same place.** `authoring_reference()` reported requiredness with
pydantic's two-way `is_required()`, while `just_dna_compiler.draft` had already been fixed to the
three-way `required` / `defaulted` / `optional` split — the middle one being the trap where
`MeasureBinRow.measure_kind` is *not* required and *not* safely left blank either. Two surfaces
answering one question, and the drift-proof one was the stale one. The split now lives in
`format.base.field_category`, the only tier both can import from; the reference emits it as
`category` beside the existing `required` key (kept, since removing a published key breaks consumers
and `required` is insufficient rather than wrong).

**Not levelled, deliberately:** `just-dna-enricher` mirrors `template` but not `stub`, `requirements`,
`describe`, `hint` or `scaffold`. The offline authoring surface belongs to the compiler; the one
mirror exists so a PGx author working through the enricher does not have to switch binaries for a
header. Adding the other four would duplicate a surface that has an owner, and removing the mirror
would break scripts for no gain.

## The release-record sweep (RM126)

`just_dna_compiler.sweep`. The instrument that measures what a release changed about compiled output,
and the gate that refuses a release whose measurement carries no declaration. The record it feeds and
the pure `needs_recompile` a consumer reads live in the format tier — see
[SCHEMAS § The release record](SCHEMAS.md#the-release-record-07-rm126--what-a-release-changed-about-compiled-output)
for the shape, the vocabularies and the interval algebra. This section is the operation.

**Why a measurement and not a map.** A hand-kept per-release map was the first repair anyone proposed
and it is the defect wearing a public name (`@registry-completeness`): five of the six RM104–RM111
fixes were a derived value restated by hand. So the sweep measures, and the gate makes the measurement
**force** the declaration rather than leaving the author to remember writing one.

### What it compares, and the one discipline that makes it mean anything

Two trees of compiled output — one produced by the previous release, one by this one — **from the same
spec root**. Feeding each side its own tree's `reference_examples/` measures spec drift as compiler
drift: between `v0.6.1` and `v0.6.6` one example's README moved, which is enough to shift
`manifest.readme` and `inputs`. One spec root, two compilers.

Five axes, and each is computed apart because a consumer acts on each differently:

| axis | how it is measured |
| --- | --- |
| `parquet_schema` | every parquet's `{column: dtype}`, read with `scan_parquet(...).collect_schema()` |
| `parquet_bytes` | `artifact.digest` |
| `content_signature` | the manifest field |
| `manifest_fields` | every dotted path in the manifest, minus `EXCLUDED_MANIFEST_FIELDS` |
| `warnings` | the `compilation.warnings` set, reported apart and never folded into the above |

**`EXCLUDED_MANIFEST_FIELDS` is a published registry with a reason per member**, and
`compilation.compiler_version` is the one that matters: it moves on **every** release by construction,
so counting it would make every record fire on every module in every release and rebuild, inside the
instrument, exactly the false-positive class the interval shape exists to avoid.
`compilation.compiled_at` and `compiled_by` are environment; `content_signature`, `artifact.digest` and
`artifact.files` are routed to their own axes rather than dropped.

**A list is a leaf.** Indexing into one would make an inserted element rename every path after it, and
`stats.genes` is what a consumer keys on anyway. A missing key and a present `null` are distinguished
by a sentinel, not by `dict.get` — otherwise `literature: null` growing the RM119 counters reads as
unchanged on the `literature` path itself.

### Backfilled, and what the numbers say

The two records shipped in 0.7 were measured on 2026-08-28 over all sixteen `reference_examples/`,
compiled from one spec root under each **published** release in turn with `just-dna-compiler` and
`just-dna-format` pinned together (the workspace cuts all three packages at one number). `0.6.0 →
0.6.1` moved nothing — a **measured zero with its denominator in the record's `evidence`**, never
silence. `0.6.1 → 0.6.6` moved `parquet_schema` and `parquet_bytes` on 10 of 16 (RM120's authored
`curator` column growing `studies.parquet`), `manifest_fields` on 9 (`stats.genes`/`stats.gene_count`
on seven, RM121; `literature.quotes_unchecked` on three, RM119) and `content_signature` on **none**.

The 0.6 line published three compiler releases — `0.6.0`, `0.6.1`, `0.6.6`. The tags in between never
reached PyPI, so no stored artifact's `compiler_version` can name one, and the chain is complete over
what a consumer can actually be holding. Older intervals stay honestly `unknown`.

### Where the gate runs, and what fails

**In the bump → `uv sync` → tag sequence, not as an ordinary test**, because it needs the previous
release actually installed. A release whose sweep shows a changed axis or field that no `ReleaseRecord`
declares **fails**.

```bash
# Fresh trees every time. `compile_module` only mkdir -p's its output, so reusing a fixed path
# inherits the last cut's modules: a renamed one lingers as a stale directory the sweep still reads,
# and a parquet a module no longer emits still gets globbed into its schema.
BEFORE=$(mktemp -d) && AFTER=$(mktemp -d)

# 1. the BEFORE side, under the previous published release, against THIS tree's specs
for d in reference_examples/*/; do
  uv run --isolated --no-project \
    --with just-dna-compiler==<previous> --with just-dna-format==<previous> \
    just-dna-compiler compile "$d" "$BEFORE/$(basename "$d")"
done

# 2. bump the versions, `uv sync`, THEN measure and gate — in that order, see below
uv run just-dna-compiler sweep "$BEFORE" "$AFTER" --spec-root reference_examples/ --release <new>
```

**`uv sync` before the sweep, not after.** `--spec-root` builds the AFTER tree with whatever compiler
is installed, so running the sweep on a stale environment measures the previous release against
itself: every axis reads `False` and the whole thing looks like a clean release that changed nothing.
The gate refuses it — it checks the interval's **upper** end against `--release` and rejects a
degenerate interval outright — but the fastest way not to meet that message is to sync first.

Step 2 exits 1 until `release_records.RELEASE_RECORDS` gains an entry for `<new>` covering what moved.
The measured half is what `SweepMeasurement.as_record(...)` produces — with an **empty** `declared`
list on purpose, so the gate keeps refusing until somebody says whether each movement was a
`correction` (the value we published was wrong) or an `addition` (it was absent). That is the whole
mechanism.

### The gate's finding phrases

Named constants, for the same reason a warning's text is: a release script greps them.

```python
NO_RECORD_PHRASE           = "has no release record"
UNDECLARED_AXIS_PHRASE     = "moved and the release record does not record it moving"
UNDECLARED_FIELD_PHRASE    = "moved and the release record does not list it"
UNDECLARED_KIND_PHRASE     = "moved and nothing declares it a correction or an addition"
WRONG_PREVIOUS_PHRASE      = "was measured against a release the record does not name"
WRONG_VERSION_PHRASE       = "did not measure the release being gated"
DEGENERATE_INTERVAL_PHRASE = "measured one release against itself, so it measured nothing"
UNMEASURED_MODULE_PHRASE   = "could not be measured on both sides, so the sweep says nothing about it"
NO_MODULES_PHRASE          = "measured no module at all"
OVERDECLARED_NOTE_PHRASE   = "is declared and this sweep did not see it move"

REGRESSED_MODULE_PHRASE             = "compiled under the previous release and does not compile under this one"
UNDECLARED_UNMEASURED_PHRASE        = "has no output from the previous release and the record does not list it"
OVERDECLARED_UNMEASURED_NOTE_PHRASE = "is declared unmeasured and this sweep measured it on both sides"
```

The middle four are about the **sweep** rather than about the record, and they exist because a gate
that only asked *is this movement declared?* passed every sweep that measured nothing. A stale
environment, a module whose compile broke under the new release, and two trees sharing no module at
all all produce an all-`False` measurement, and none of them is a release that changed nothing.
`--release` accepts the stamped `just-dna-compiler X.Y.Z` spelling as well as the bare one, for the
same reason `needs_recompile` does.

`OVERDECLARED_NOTE_PHRASE` is a **note, not a finding**, and does not fail the release: the reference
corpus is sixteen modules and a real correction can land on a shape none of them has. It is still
printed, so over-declaring is visible rather than invisible.

The last three are RM139's split of *one side only*, below.

### Which side a module is missing from (RM139)

`UNMEASURED_MODULE_PHRASE` stays in every message here, so a script grepping it catches all of them.
What changed is the clause after it, because the two directions are facts about **different
releases**:

| the module is | what it means | the gate |
| --- | --- | --- |
| in BEFORE, not in AFTER (`only_before`) | this release cannot compile a spec the previous one could — a regression, or a stale reused BEFORE directory holding a module the spec root no longer has | **fails, unconditionally**, with the compiler's own errors beside it where `--spec-root` built the AFTER side. `as_record` refuses to mint over one |
| in AFTER, not in BEFORE (`only_after`) | the previous release produced no output for it: its spec uses a column that release refuses under `extra="forbid"`, or the example is newer than that release | **fails until `ReleaseRecord.unmeasured` names it.** Then it is measured-nothing rather than measured-zero |

The first real use of the gate hit the second row, which the rule did not model: RM70 put the optional
`requires_callable` column on `pharm_variants.csv`, `reference_examples/cyp2c9_warfarin_grch37/` uses
it, and 0.6.6 refuses that spec. Nothing failed — the module has no before state at all, so no
like-for-like comparison exists — and it **recurs in every minor that adds an authored column and
exercises it in the corpus**. The 0.7.0 cut stated the exclusion in `evidence` prose the gate cannot
read and the tag was waved through by hand.

`unmeasured` is a **denominator, not an exemption**, and the difference is the equality: a module the
sweep measured on both sides cannot be excused by listing it (that is reported as a note), a
regression cannot be excused by listing it, and a movement on a measured module still gates however
the list reads. What it buys is that the exclusion is forced into the published record by the
measurement — `as_record` fills it — instead of living in a sentence nothing checks.

**Under `--json`, stdout is the JSON document and nothing else** — the notes and the success line go
to stderr there. The caller of that flag is a release script piping to `jq`, and a note printed after
the blob breaks exactly the consumer the flag exists for. Without `--json` they read on stdout as
usual.

### The warnings axis, and the seam RM131 fills

`compilation.warnings` is a published manifest field, so the naive reading folds it into
`manifest_fields` — and then RM131's restructuring and RM134's new checks report *a manifest field
changed* on essentially every module in 0.7, and a registry acting on that mints an immutable PATCH
across a whole catalogue for a reworded message. It cannot simply join `compiled_at` in the excluded
set either, because a **new** warning can be a real signal.

So it is its own declared axis, outside `RECOMPILE_DRIVING_AXES`. **RM131's `carried` split landed in
0.7 and is that discriminator**: `compare_module` now reports `carried_added` beside
`actionable_added`, read off the *after* manifest's `compilation.carried` rather than re-derived from
prose. A carried finding appearing is usually this repository saying more about a limit it always had;
an actionable one appearing is work arriving at somebody's door.

`axes["warnings"]` deliberately still fires on any movement of the set. Narrowing it would make a
published axis mean something different from what every record already written claims about it, and
the axis drives no rebuild anyway — the split buys the *reading*, not a new gate. A manifest with no
`carried` field (anything compiled before 0.7) reports every addition as actionable, which is the safe
direction: it never tells a reader that a finding they could fix is unfixable.

`compilation.carried` and `compilation.warnings_summary` both join `compilation.warnings` in
`EXCLUDED_MANIFEST_FIELDS`, for the same reason and with the same consequence — they are derived from
it, so they move exactly when it does.

**What this does not touch:** `SpecRow.needs_upgrade` is `self.upgraded() != self`, computed over
authored row content and a hard filter in the marketplace. A warning never touches an authored row, so
no warning change can flip it. Verified rather than assumed, because the failure mode would have been
modules silently vanishing from a catalogue.

## Coverage table (0.3 / 0.4 features)

| 0.3 / 0.4 feature | Validated | Materialized (→ parquet) | Computed / derived | Status |
|---|---|---|---|---|
| `direction` (`VariantRow`) | ✅ full vocab | ✅ `weights.parquet` — the **authored** value only, never a derivation | ✅ **Python read-time only**: `effective_direction` / `upgraded()` from `state`(+`weight`) | complete — but read the two cells apart: a `state`-only module ships an empty column |
| `stat_significance` (`VariantRow`, `StudyRow`) | ✅ full vocab | ✅ authored value only | ✅ Python read-time, derived from `state` (not inferred from `p_value`) | complete, same split as `direction` |
| `effect_size` (`VariantRow`, `StudyRow`) | ✅ float | ✅ | — | complete |
| `effect_measure` (`VariantRow`, `StudyRow`) | ✅ permissive (open) | ✅ | — | complete (intentionally open) |
| `effect_allele` (`VariantRow`) | ✅ nucleotides | ✅ | ✅ **membership in `{ref} ∪ alts`** (0.5) → warning / error in `strict`; ⛔ still no strand reconciliation | validate + membership check |
| `genotype` (`VariantRow`) | ✅ grammar (phased/hemizygous/sorted) | ✅ alleles + `phased` | ✅ **membership in `{ref} ∪ alts`** (0.5), unioned across a one-to-many rsid's loci | complete |
| `flags` (`VariantRow`) | ✅ open; split; reserved set | ✅ `List[str]` | ✅ unknown-tag INFO (`ValidationResult.info`) | complete |
| `trait_efo_id` (`VariantRow`, `StudyRow`) | ✅ CURIE(s) | ✅ | — | complete |
| `doi` (`StudyRow`, RM11) | ✅ DOI grammar, verbatim | ✅ `studies.parquet` | — | complete |
| `provenance_quote` / `provenance_regex` (`StudyRow`, RM12) | ✅ free-text / author-time `re.compile` | ✅ `studies.parquet` | — | complete (P1 pattern grammar; matched consumer-side) |
| `authorship` (`ModuleSpecConfig`/`ModuleManifest`, RM14) | ✅ `Contribution` (role closed, kind open, `extra=forbid`) | ✅ **manifest** (out of digest) | — | complete (metadata; not reversed) |
| `clin_sig` (`VariantRow`) | ✅ full vocab | ✅ | ✅ ↔ `pathogenic`/`benign` aliases | complete |
| `module.version` (`ModuleInfo`, 0.4.1) | ✅ freeform advisory (legacy `v2`/`3`) | ✅ **manifest** `Identity.version` iff valid SemVer; `reverse_module(version=)` re-emits | ✅ `normalize_version` preview (RM17 enforces) | complete (advisory) |
| authority-key strip (0.4.1) | ✅ inject-only pre-strip; dropped → `.info`; typo'd still `extra=forbid` | — | — | complete (DI) |
| strict compile (0.4.1) | ✅ `strict=True` fails (pre-write) on an unresolved `(chrom, start)` | — (refuses a partial) | — | complete (opt-in) |
| `content_signature` (0.4.1) | ✅ over raw authored rows, normalized+sorted, name-/Ensembl-independent | ✅ **manifest** (out of digest); `signature` CLI computes it without recompiling | — | complete (canonical dedup identity) |
| **`resolution.csv` path (0.5)** | ✅ `resolve_from_table` consumes injected facts; digest-parity with the DuckDB path proven; **provisional shape** (§ note) | ✅ drives `weights.parquet` coords; `resolution_signature`/`resolution_mode`/`fully_resolved`/`resolution_sources` → **manifest** (out of digest) | ✅ fill / expand / verify (pure, no duckdb) | complete (preferred path) |
| **VRS allele identity (0.5)** | ✅ stdlib `derive_vrs_allele_id`; every member of `vrs_id` recomputed and verified per ALT, plus a coverage report (mode-dependent severity) | ✅ `variant_key` **is** the VA for a resolved substitution → `weights`/`annotations.parquet` | ✅ minted per ALT from `(chrom, start, ref, alt)`; a multi-allelic site names each allele, and the *key* still falls through to the coordinate for indels/MNVs/multi-allelic | complete (GRCh38-only; multi-build is RM15) |
| **`frequencies.csv` path (0.5)** | ✅ `FrequencyRow`; coordinate cross-check → warning; **provisional shape** | ✅ `frequencies.parquet` (in `artifact.digest`); `frequency_signature`/`sources`/`datasets`/`populations` → **manifest** (out of digest) | ✅ `allele_frequency` = AC/AN materialized as `Float64` (never stored in the CSV) | complete (injected; enricher produces it) |
| **`gene_metrics.csv` path (0.5)** | ✅ `GeneMetricsRow`; gene cross-check → warning; **provisional shape** | ✅ `gene_metrics.parquet` (in digest); `gene_metrics_signature`/`genes`/`datasets` → **manifest** | — | complete (injected; offline-capable upstream) |
| **`literature.csv` path (0.5)** | ✅ `LiteratureRow`; citation cross-check + nonexistent-PMID warning; **provisional shape** | ✅ `literature.parquet` (in digest); `literature_signature`/`sources`/coverage counters → **manifest** | — | complete (injected; enricher produces it) |
| **`gene_validity.csv` path (0.6, RM24)** | ✅ `GeneValidityRow`; gene cross-check → warning; **provisional shape** | ✅ `gene_validity.parquet` (in digest); `gene_validity_signature`/`genes`/`diseases`/`classifications`/`submitters`/`datasets` → **manifest** | — | complete (injected; ClinGen + GenCC routes in the enricher) |
| **`clinical_assertions.csv` path (0.6, RM25)** | ✅ `ClinicalAssertionRow`; coordinate cross-check → warning; **provisional shape**. Records the archive's call and review tier; it does **not** adjudicate against the author's `clin_sig` — that stays the enricher's warn-in-both-modes cross-check | ✅ `clinical_assertions.parquet` (in digest); `clinical_assertion_signature`/`clin_sigs`/star range/`unrated_count`/`not_found_count` → **manifest** | — | complete (injected; offline-capable upstream from the ClinVar snapshot) |
| CLI (0.4.1, extended 0.5) | ✅ Typer `validate`/`compile`/`signature`/`reverse`/**`verify`**/**`sign`**; `--strict`, `--strip-identity`/`--authority-key`, deprecated `--ensembl-cache`, `--resolution` | — | — | complete (compiler-only dep; tiers intact) |
| **queryable p-value (0.5)** | ✅ `p_value_num` in (0, 1]; cross-checked against the verbatim `p_value` string (relative, 1%) | ✅ `studies.parquet`; **`neg_log10_p` derived on write**, absent from the reversed CSV | ✅ `-log10(p_value_num)` | complete |
| **`callable_from` (0.5, RM6)** | ✅ VCF field-name pointer, namespace-qualifiable and `\|`-alternatable (shared `AuthoredModel` validator); bare colliding key → warning both modes (0.6) | ✅ `weights.parquet` | — | complete (retired from the reserved namespace) |
| **`recommendation_strength` (0.5)** | ✅ closed CPIC vocabulary, distinct axis from `evidence_level` | ✅ `diplotypes.parquet` | — | complete |
| **dosage sensitivity (0.5)** | ✅ `haploinsufficiency`/`triplosensitivity` against `VALID_DOSAGE_SENSITIVITY` | ✅ `gene_metrics.parquet` (in digest, fact-hashed) | — | complete (ClinGen route in the enricher) |
| **`redistribution` (0.5, settled 0.6)** | ✅ tri-state; `None` ≠ `False` | ✅ `sources.parquet`; per-layer facet + module-wide verdict → **manifest** | ✅ most-restrictive-wins | complete — **recorded here, enforced downstream** (RM27; the ask is in SCHEMAS.md) |
| **GWAS effect sizes (0.6, RM90)** | ✅ `effect_direction` closed; `effect_measure` open; `effect_unit` free text and **inside the fact hash** | ✅ `gwas_effects.parquet` (in digest, fact-hashed) | ✅ orphan rows warn, never fail | complete (Catalog route in the enricher; fills no `weight` — see MODULE_LIFECYCLE § Stage 3) |
| **weighting declaration (0.6, RM92)** | ✅ three free-text strings, `extra="forbid"` | ✅ `manifest.weighting`; moves neither identity half | — | complete; dropped by `reverse_module`, like `license`/`panel`/`authorship` |
| **verification attestation (0.6, RM45)** | ✅ binding recomputed from the authored inputs, proof-of-work re-checked; stale ⇒ warn + drop, never fatal | ✅ `manifest.verification` (out of `artifact.digest`); nothing reaches a parquet | — (the enricher puts the checks) | complete (`verification.json`; nothing in the block is trusted) |
| **authoring closure (0.6, RM73)** | ✅ published when the attestation holds and carries one; absent ⇒ warn in both modes; a *signed* closure that does not verify ⇒ drop the whole block | ✅ `manifest.verification.closure`; moves no digest and no signature (measured on all sixteen reference examples) | ✅ `close` writes it; `validate` never does | mechanism complete (`compiler.close_module`); the **refusal** is 1.0 and blocked — see ROADMAP_1_0 § RM73 |
| **drafting (0.5)** | ✅ appended rows are validated rows; keys reuse `_TABLE_DUPE_KEYS` | — (writes authored CSVs, not parquet) | ✅ append / already-present / differs report | complete (`draft.append_rows`, `blank_template`); `DRAFTABLE` covers the SNP core, the table kinds and `sources.csv` (0.5.4) |
| **templating (0.5)** | ✅ a stub carries `TEMPLATE_PLACEHOLDER`, which no mode compiles | — (writes authored CSVs, not parquet) | ✅ created / kept-untouched plan | complete (`draft.stub_template`, `scaffold.scaffold_module`) |
| **hints (0.5)** | ✅ per-cell validation, bin coverage, duplicate keys — all offline | — (writes nothing at all) | ✅ alterations + findings + options | complete (`hints.inspect_rows`, `hints.describe_table`) |
| **delegated insertion (0.5)** | ✅ placed rows are validated rows; shifted rows keep their cells | — (writes authored CSVs, not parquet) | ✅ `DraftReport.shifted` names every moved row | complete (`draft.place_rows`, `append_rows(group_by=…)`) |
| **partial rows (0.5)** | ✅ stubbed columns validated by omission; the stub itself never compiles | — (writes authored CSVs, not parquet) | ✅ added / already-present / invalid | complete (`draft.PartialRow`, `append_partial_rows`) |
| genotype widening: hemizygous single allele | ✅ | ✅ (1-element list) | — | complete |
| genotype widening: phased `A\|G` | ✅ (order kept) | ✅ `phased` bit → lossless round-trip | ✅ | complete |
| `state` (legacy) | ✅ (stays required — P8) | ✅ | ✅ read alias via `effective_direction`; trimmed to {protective,risk,neutral} on `upgraded()` | complete |
| MT / non-diploid genotype | ✅ warning on a two-allele MT or Y genotype | — | — | complete |
| direction/weight sign consistency | ✅ warning | — | — | complete |

## 0.4 compiler coverage (materialized)

| 0.4 kind (model) | Validated | Materialized (→ parquet, round-trip) | Status |
|---|---|---|---|
| binning primitive `MeasureBinRow` + `Activity/CopyNumber/RepeatAllele/Heteroplasmy` rows | ✅ shared vocab, inclusive `[min,max]`, mandatory `unresolved`, `extra=forbid`, `source_field` pointer + `source_element` rule (0.6), heteroplasmy `tissue` + legacy-ref guard | ✅ `*.parquet` via generic materializer | **materialized** |
| table-level `validate_bins(rows)` | ✅ per `(key…, trait_efo_id)` group | overlap → error, gap → warning, >1 `unresolved`/group → error | **enforced** |
| duplicate-row detection (diplotype pair, `pgs_id`, `(pharm variant, drug, genotype, category, annotation_id)`, allele-function allele, haplotype-defining variant, **`(source, layer)` in the licensing table since RM107**) | ✅ per-kind natural key | error (0.4 analog of duplicate-(variant, genotype)) | **enforced** |
| PGx `HaplotypeRow` / `AlleleFunctionRow` / `DiplotypeRow` (+ `drug`/`response`/`evidence_level`) | ✅ | ✅ | **materialized** |
| PharmGKB `PharmVariantRow` (single-variant drug response, `evidence_level` 1A…4, per-genotype) | ✅ | ✅ | **materialized** |
| **`sources.csv` licensing path (0.5)** | ✅ `SourceRow`; tri-state permissions; duplicate `(source, layer)` → error, both modes (RM107); orphan/undeclared + declared-licence warnings (never escalate) | ✅ `sources.parquet` (in digest); `source_signature`/licences/attributions/per-layer facets/derived `commercial_use` → **manifest** | ✅ **refuses** (both modes) when annotation-layer terms forbid sale and no declaration is recorded | **complete** (injected; enricher produces it) |
| `VariantRow` general axes: `requires_callable` / `acmg_sf` / `actionability` | ✅ (`actionability` vs `ACTIONABILITY_SEED`; `acmg_sf` vs the ACMG SF list in the **enricher**, 0.5) | ✅ into `weights.parquet` (tri-state bool round-trip) | **materialized** |
| **RM70 callability on the PGx locus tables: `HaplotypeRow.requires_callable` / `PharmVariantRow.requires_callable` (0.7)** | ✅ optional tri-state bool, no vocabulary and no validator — the same column `VariantRow` carries, on the two PGx tables that name a locus. `DiplotypeRow` refuses it via `extra=forbid`; `callable_from` does not travel | ✅ generic table materializer, no compiler change — `_polars_type` maps it to a nullable `pl.Boolean` and `_scalar_cell` reverses `None`/`False` as `""`/`"false"` | **materialized** — outside every `_KEY_FIELDS`; unset it is dropped by `exclude_none`, so no published module's `content_signature` moves |
| **RM132 the third citation site: `PharmVariantRow.pmid` (0.7)** | ✅ optional, free-form, validated by `spec.validate_pmid_cell` — the one grammar every citation pointer routes through, so the PMCID refusal and the `[PMID: N]` spelling come with it. Read by `_cross_check_literature` and by the enricher's literature pass, through the derived `_CITING_TABLE_KINDS` rather than a third hand-kept list | ✅ generic table materializer and generic reverse writer, no compiler change — both derive their column lists from the model | **materialized** — outside `_KEY_FIELDS`; unset it is dropped by `exclude_none`, so no published module's `content_signature` moves |
| **RM29a call-confidence cofactor: `quality_from` + `min_quality` (0.5)** | ✅ shared pointer grammar (`source_field`/`callable_from`/`quality_from`, one validator, namespace-qualifiable since 0.6); finite floor; **both-or-neither** model rule | ✅ `weights.parquet` (`Utf8` + `Float64`); absent floor is null, never `0.0` | **materialized** |
| **RM29b clinical cofactor: `DiplotypeRow.clinical_context` (0.5)** | ✅ whitespace-stripped, open (no vocabulary — guideline bodies scope differently) | ✅ generic table materializer, no compiler change | **in `_TABLE_DUPE_KEYS`** — disagreeing CPIC contexts coexist as distinct rows |
| PGS `PgsRow` (declared interface; ancestry-validity fields) | ✅ `PGS<digits>`, ancestry/tier vocab, `match_rate_floor∈[0,1]` | ✅ | **materialized** |
| reserved namespace (`reference_db` / `callable_element` / `quality_element`) | ✅ specific diagnosis via `reject_reserved` on top of `extra=forbid` | — | reserved |
| authoring reference + palette (`reference.authoring_reference()`/`json_schemas()`) | ✅ generated from live models (drift-proof) | n/a | **shipped** (RM8/RM9) |
| frozen `variant_key` identity (`base.derive_variant_key`) | ✅ stamped once, never re-keyed by resolution (P7); excluded from `authoring_reference()` | ✅ `weights.parquet` (compiler-managed) | **shipped** |
| rsid↔coord resolution: one-to-many expansion, deterministic order, inject-only consistency check | ✅ `ORDER BY`; disagreement → warning; non-GRCh38 skipped | ✅ N coord-keyed rows per one-to-many rsid; idempotent | **shipped** (the DuckDB engine now lives in `just-dna-enricher`; GRCh38-only; multi-build RM15) |
| **expansion marker: `VariantRow.locus_index` + `locus_count` (0.6, RM87)** | ✅ stamped at the expansion loop, authored cells overwritten by `_freeze_identity`; `exclude=True`, so no `content_signature` moves | ✅ `weights.parquet` (`UInt32` ×2, hand-listed in `_build_weights`); reverse prefers the stored index over its recompute and never re-emits either column into `variants.csv` | **shipped** — `locus_count > 1` is the row-level predicate; the positional pass's hard-coded `0` is honest only while those tables never expand (a line on RM65) |
| **authored overlay `overrides.csv` (0.7, RM124)** | ✅ `OverrideRow` (`AuthoredModel`); `table` and `operation` are closed vocabularies; **`reason` required**; a `field` outside the named table's columns, or naming its own subject/member column, is refused; a wildcard `member` is refused for `insert` and `suppress`; duplicate `(table, subject, member, field)` and a key group carrying two operations are errors — all of it in **both** `validate_spec` and `compile_module` | ✅ `overrides.parquet`, written only when the module carries an overlay — its absence, not its slot, is why no published digest moves (`artifact_digest` name-sorts); applied to the seven covered derived tables before any check reads a row, so the fact signatures and `resolution_signature` are post-overlay | **shipped** — the derived files are pure build products, `reverse` emits post-overlay tables *plus* the overlay, and no operation reports its own no-op |
| **VCF pointer namespace + cardinality (0.6, RM53/RM54/RM61)** | ✅ `INFO/`/`FORMAT/` qualifier and the spec's key charset accepted (widening only); `_check_vcf_pointers` warns in **both** modes on a bare colliding key and on a spec-multi-valued target with no element rule, aggregated by reason | ✅ `source_element` → the binning parquets via the generic materializer; round-trips through `reverse` unchanged | **shipped** (`source_element` on `MeasureBinRow`; `callable_element`/`quality_element` **reserved**, not built) |

## Upgrade derivation (`state`/booleans → 0.3 axes)

`state` and the ClinVar booleans **stay required/authoritative** for 0.2 backward-compat (P8). The new
axes are optional, and `just_dna_format.derive` supplies fallbacks:

- **Read-time (non-mutating):** `VariantRow.effective_direction` / `effective_stat_significance` /
  `effective_clin_sig` / `effective_pathogenic` / `effective_benign` return the set column, else the
  derivation — so a legacy 0.1/0.2 row exposes all three axes with no re-publish.
- **Materializing:** `VariantRow.upgraded()` fills those axes and trims `state` to `{protective, risk,
  neutral}` (kept as a derived mirror of `direction`). `needs_upgrade` is the signal the marketplace
  `revalidate`/`needs_upgrade` flow consumes. Both idempotent (P7).

### The parquet column is the authored value, and the derivation is not in the artifact

The `direction` column in `weights.parquet` is a **materialized passthrough**: whatever the author
wrote, or empty. The compiler never fills it from `state`, and should not — `state='significant'`
carries no direction at all, so the derivation refines one from the *weight sign*, which is a sound
fallback for a reader and a fabricated fact in a published table. Every module authored against 0.2
therefore ships an empty `direction`, correctly.

The consequence to plan for, if you read the artifact rather than the models: **the fallback lives in
Python and does not travel with the parquet.** A consumer querying `weights.parquet` with SQL or
polars sees the empty column and nothing else, so a migration from `state` to `direction` reads every
legacy module as directionless. Apply the derivation yourself —
`just_dna_format.derive.direction_from_state(state, weight)` is a pure leaf function published for
exactly this (it imports nothing from `spec`, so the marketplace `revalidate` flow already uses it
that way) — or go through `VariantRow.effective_direction`, which returns the authored value when
there is one and the derivation when there is not.

Whether an artifact should ever carry the derived axes is open, and it is a design question rather than
a patch: the objection is that filling a blank asserts what no curator wrote, not that the bytes move.

## Intentionally unimplemented — and why

1. **New computed manifest stats.** `Stats` carries the 0.2 counts only; no new distributions (by
   `direction`/`clin_sig`) — no consumer needs them yet.
2. **`effect_allele` *strand* reconciliation.** Since 0.5 the compiler does check that `effect_allele`
   (and every genotype allele) is one of the alleles the locus actually has — so a strand-flipped
   `A/G` at a `C>T` locus is now caught, because neither allele is present. What is still not done is
   *reconciling* it: nothing complements the allele and rewrites it, and the `+` strand /
   `genome_build` assumption remains documentation rather than an enforced computation. Reporting a
   flip is a redundancy check; silently flipping it back would be repairing authored data.
3. **Single build — GRCh38-bound.** `genome_build` is recorded but only GRCh38 is honored: coordinates
   are GRCh38, the resolution table's `genome_build` is checked against the module's, and
   `artifact.digest` is GRCh38-relative. A GRCh37/T2T module compiles but is not re-resolved for that
   build. Legacy-from-implementation, not a principle — build-aware identity is RM15. A no-coord rsid
   mapping to several loci is expanded to one row per locus (data-agnostic), shipping GRCh38-now.
4. **`reverse_module` reconstructs the compilable core, not manifest-only metadata.** It reads the
   parquets for everything materialized into them, and `manifest.json` for the **one** authored value
   that is digest-relevant and lives nowhere else: `genome_build`. That single read replaced a
   "parquet only, never `manifest.json`" rule which sounded principled and was how the build came to be
   hardcoded — the rule's real content is *nothing in the digest may be invented*, and for a
   non-GRCh38 module the invented build changed the identity key, hence the digest. Absence is handled
   rather than assumed: no manifest means the format's default, and an explicit `genome_build=` always
   wins. `authorship`/`panel`/`provenance`/`logo` genuinely are not restored and genuinely cannot move a
   parquet byte. What *is* round-trip-critical — every authored value, including a poly-effect variant's
   per-effect `gene`/`phenotype`/`category` — is restored.
5. **Gene-panel materialization, and now the `panel:` block itself (RM4).** Compiling a
   `GenePanelSpec` into `weights.parquet` is not deferred any more, it is **dropped**. The compiler
   must not create rows no curator wrote — the same objection that bars filling `direction` from
   `state`, and it does not depend on the digest. Expansion at compile would also make a module's
   content depend on an external file, and leave `reverse` choosing between re-emitting the
   declaration (rows lost) and the rows (declaration lost); neither is a fixed point (P7). The want is
   served instead by **enricher draft-scaffolding**, which already ships: `draft-panel` writes the
   rows, and the author's no-op over the drafted subset is still an authorial act. The rows are
   authored bytes before the compiler ever sees them.

   With that decided, `panel:` had no reader left — its last one was the enricher's ClinVar
   `clin_sig` cross-check, which now reads the drafted-from release out of the licence row's `dataset`
   column, written by the drafting pass. So it is **deprecated in 0.6 and removed at 1.0**, with
   `validate_spec` emitting the warning (and `compile_module` carrying it into
   `manifest.compilation.warnings`, once — compile seeds its warnings from validate's). The block
   still loads, still reaches `manifest.panel`, and still changes nothing else, which is what makes the
   deprecation warn-only and the cadence legal.

   **Deleting it moves no identity**, measured rather than argued: `reference_examples/apoe_epsilon`
   with a `panel:` block appended compiles to the same `artifact.digest` and the same
   `content_signature` as without it. *Auto-removing it on reverse* was considered and refused for the
   opposite reason — reverse writes `module_spec.yaml`, so dropping the block there would change that
   file's bytes and break the round-trip fixed point for any module carrying it. A warning the author
   acts on is the route.

   **The warning has two branches since S69, and it stopped claiming nothing else is lost.**
   Both halves were wrong in a way gating alone would not have fixed. `GenePanelSpec` carries **five**
   fields and `SourceRow.dataset` is one release *label*: it cannot hold `genes` — the denominator,
   and the only thing separating *this gene is not in the panel* from *it is in the panel and had
   nothing to report* (reported as 425 declared genes against `gene_count: 298`) — it cannot hold
   `significance`, the predicate that makes a panel module's row set reproducible, and it is a name
   rather than a digest so it cannot hold `reference_sha256`. All three now say so in the message.
   And the replacement is legitimately **absent** on a module drafted before the drafter filled
   `dataset`: `merge_sources_file` is never-clobber, so re-running does not backfill it, and there is
   no path from such a module to the state the old sentence assumed. So the check moved behind the
   licence rows — a deprecation is legal in a minor only where its audience can *act* on it (P3), and
   whether they can is a fact about a value the pass had not read when the warning fired. With no
   filled `clinvar`/`annotation` `dataset` it now says **do not delete the block yet**, names what to
   fill first, and warns that a re-draft will not do it.

## Consequences worth knowing

- **`weights.parquet`/`studies.parquet` carry the 0.3 columns + a `phased` bit**, so a re-compile under
  this compiler changes `artifact.digest` for every module; reproducibility is pinned by
  `compiler_version`, and published versions keep their digest until re-published. A moving digest is
  therefore not itself a version gate: a **new optional column or table** is additive and minor-legal,
  while removal, promotion to required, retyping, or changing what an identity key means is major-only
  — see [ROADMAP § 0.6](ROADMAP.md#06--what-a-minor-permits).
- **Round-trip is lossless and idempotent** (P7): `reverse_module` → recompile preserves every column
  including phase, and the same spec compiles twice to the same digest. In 0.5 the round-trip is
  additionally **offline** — reverse emits `resolution.csv`, so recompile needs no reference and no
  network (regression-tested: DuckDB compile → reverse → no-cache recompile → identical digest).
- The **`ValidationResult.info`** channel carries non-reserved `flags` notes via stdlib logging — the
  format packages do not depend on Eliot.

Tests: `compiler/tests/test_v03*.py` (validator, genotype widening, warnings/INFO, materialization,
round-trip/idempotency); `test_v04_compile.py` (the nine table kinds); `test_resolution_table.py` (the
0.5 resolution-table path, digest parity, offline round-trip, strict/best-effort, the deprecation).
