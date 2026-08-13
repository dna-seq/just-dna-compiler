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
PMID, CURIE, `ga4gh:VA.`, `CA\d+`), value bounds, finite floats (no `NaN`), required-ness, mandatory
`unresolved` bin sentinels, bin overlap/gap, duplicate natural keys, duplicate `(variant_key,
genotype)`. If a module violates one of these it is malformed, full stop.

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
| study / frequency / gene-metrics / literature orphans | the sidecar describes something the module lacks | warning |
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
everything about the paper stays in `studies.csv`. `heteroplasmy.csv` was never affected: its optional
`rsid`/`chrom`/`start` columns (0.5.1) already gave a row a variant identity a study row can name,
which `reference_examples/mt_heteroplasmy` does, and that remains an alternative route there.

`_check_binning_grounding` still warns in **both** modes, now over the bins that carry neither a `pmid`
nor a variant identity, in a module with no study rows at all — and the remedy it names is the same for
every kind, since every kind can now cite its boundary. The same-release obligation was the reason the
item was filed rather than fixed: `_cross_check_literature` reads the bin pointers alongside
`studies.csv` (otherwise every threshold-grounding citation would read as a stale orphan), and so does
the enricher's literature pass, so a bin-grounded citation is checked for existence and identifiers
exactly like a study-grounded one. `reference_examples/htt_repeat_expansion` is deliberately left
**uncited**: the example exists to show what the warning looks like.

### Three more schema limits, made legible the same way (0.6, the VCF 4.4 audit)

Same class as the bin-boundary gap above — limits of the **schema**, not of the tier — and they are here
for the same reason: so they are not mistaken for the other kind, and so the warning a reader meets on a
real module has somewhere to point. All three warn in **both** modes and none changes a verdict.

**The two integer measure kinds are not integral (RM55).** VCF 4.4 §7.2 redefined `CN` to support
non-integer copy numbers and §3 types `RUC` as a `Float`, so the premise `repeat_count` and
`copy_number` were placed in `binning._INTEGER_KINDS` on has been withdrawn for both. The consequence is
RM35's unsatisfiable triangle re-instantiated on the kinds RM35 exempted, and worse: on an integer kind a
hole of exactly one is not reported at all, so `[0,0] [1,1] [2,2] [3,∞)` is a legal, gapless, green
tiling under `--strict` that answers nothing for a CN of 2.4. `binning.measurement_shape_warnings` says
so once per table. The fix is a three-release route — 0.6 warns, 0.7 adds a parallel float column beside
the integer one with the integer deprecated, 1.0 removes it — because the direct correction is a
**retype** (`CopyNumberRow.modifier_cn: int` → float) plus a change to what already-published bin
tilings mean, and retyping is major-only.

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
tolerance above.

**Where the machine-written sidecars may live, and what they may be called (RM49/RM51, 0.6).**
`resolution.csv` and the six fact tables are resolved through `just_dna_format.layout`, which accepts
each of them at the spec root **or** under a `derived/` subdirectory, and accepts the licence table
under either `sources.csv` (deprecated, warn-only, removed at 1.0) or `licensing.csv`. Four rules:

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
   row-parse error fails the compile), then **verify every stored `vrs_id`** (below).
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
10. **Build the manifest** (`content_signature` re-read from raw disk, the resolution fields, the
    `frequency` / `gene_metrics` / `literature` blocks, and `derived[]` — byte hashes of the sidecar
    CSVs *where they live beside the spec*, transport-only and never their identity) and write
    `manifest.json`.

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
no coordinate, or against no ALT. That is not a limit of this tier — the row asserts an identity while
withholding the very thing that identity is a digest of, so nothing anywhere could check it. Same class
as the *inconsistent reference allele* error, and catchable offline.

#### Every flow path

`_recompute_vrs_id` returns either the recomputed id or the reason there is none, **for one allele**.
`vrs_id` is a comma-joined parallel array of `alts`, so the pass walks the two together and each ALT
gets its own verdict; an empty member is a hole and reads exactly like an empty cell. The four reasons
are limits of a no-network tier, not defects in the row:

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
| position-only (no `alts`) | an id against no ALT — the **row's** contradiction, not the tier's | error |
| no coordinate | an id against no place (an rsid row carrying an external id) | error |

Multi-allelic used to be one row of this table, blanket-unverifiable, "a VA names exactly one allele;
picking one would invent data". The premise is `derive_variant_key`'s and it is right there — a
`variant_key` names one thing, so a plural cell falls through to the coordinate key. It was wrong here,
where nothing is picked because every ALT is named. It cost the id on 909 of 1,613 rows in one real
module while every input needed to mint all 2,110 of them sat in the same row.

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

**RM44 shipped in 0.6 and it retires only half of this.** `resolution_subjects` gives a consumer a
structured field for *"was the flag about anything"*, so the vacuity no longer needs the prose — but
the *unjoinable-row count* is a different question and still has only the sentence, since RM43 fills
the rows rather than counting them into the manifest. The fragment and its test stay.

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
`gene_metrics.csv`, `literature.csv`, `gene_validity.csv`, `clinical_assertions.csv`, `sources.csv`).

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
  `readme`. A
  consumer needing these reads `manifest.json` (preserved verbatim by the forward compile). The test of
  whether something belongs on this list is whether losing it can change a parquet byte — which is why
  `genome_build` moved off it. `readme` joins `logo` here for the same reason and with the same
  consequence: `reverse` writes no readme into the re-emitted spec, so a recompile of a reversed module
  attests none — the three signatures are still a fixed point, because prose was never in any of them.

## Output artifact & hashing

- **`_OUTPUT_FILES`** (feed `artifact.digest`): `weights`/`annotations`/`studies.parquet` + the 9
  table-kind parquets + `frequencies.parquet` / `gene_metrics.parquet` / `literature.parquet` when
  present. The sidecars enter
  the digest because a module carrying frequency data genuinely *is* different content — but adding one
  leaves the SNP core's bytes untouched (an explicit test).
- **`_INPUT_FILES`** (feed `manifest.inputs`, raw-bytes hashed): `module_spec.yaml` + `variants.csv` +
  `studies.csv` + the 9 table-kind CSVs — the authored surface, and the reason only the *other* files
  gained a second legal name and location in 0.6. **`resolution.csv` is deliberately NOT here** (nor in
  `_OUTPUT_FILES`) — it is a multi-producer artifact hashed only by the normalized `resolution_signature`
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

## CLI, and what it maps onto

`just-dna-compiler` (Typer) is a thin shell over the Python API. Exit 0/1, CI/registry-gateable.

| Command | Python API | Notes |
|---|---|---|
| `validate <spec>` | `compiler.validate_spec` | `--strip-identity` / `--authority-key` |
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
| `describe <kind>` | `hints.describe_table` | one table's columns + pick-lists |
| `hint <kind>` | `hints.inspect_rows` | `--rows-file`/`--row`, `--json` |

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
| **`redistribution` (0.5)** | ✅ tri-state; `None` ≠ `False` | ✅ `sources.parquet`; per-layer facet + module-wide verdict → **manifest** | ✅ most-restrictive-wins | complete (recorded, **not** gated — RM27) |
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
| duplicate-row detection (diplotype pair, `pgs_id`, `(pharm variant, drug, genotype, category, annotation_id)`, allele-function allele, haplotype-defining variant) | ✅ per-kind natural key | error (0.4 analog of duplicate-(variant, genotype)) | **enforced** |
| PGx `HaplotypeRow` / `AlleleFunctionRow` / `DiplotypeRow` (+ `drug`/`response`/`evidence_level`) | ✅ | ✅ | **materialized** |
| PharmGKB `PharmVariantRow` (single-variant drug response, `evidence_level` 1A…4, per-genotype) | ✅ | ✅ | **materialized** |
| **`sources.csv` licensing path (0.5)** | ✅ `SourceRow`; tri-state permissions; orphan/undeclared + declared-licence warnings (never escalate) | ✅ `sources.parquet` (in digest); `source_signature`/licences/attributions/per-layer facets/derived `commercial_use` → **manifest** | ✅ **refuses** (both modes) when annotation-layer terms forbid sale and no declaration is recorded | **complete** (injected; enricher produces it) |
| `VariantRow` general axes: `requires_callable` / `acmg_sf` / `actionability` | ✅ (`actionability` vs `ACTIONABILITY_SEED`; `acmg_sf` vs the ACMG SF list in the **enricher**, 0.5) | ✅ into `weights.parquet` (tri-state bool round-trip) | **materialized** |
| **RM29a call-confidence cofactor: `quality_from` + `min_quality` (0.5)** | ✅ shared pointer grammar (`source_field`/`callable_from`/`quality_from`, one validator, namespace-qualifiable since 0.6); finite floor; **both-or-neither** model rule | ✅ `weights.parquet` (`Utf8` + `Float64`); absent floor is null, never `0.0` | **materialized** |
| **RM29b clinical cofactor: `DiplotypeRow.clinical_context` (0.5)** | ✅ whitespace-stripped, open (no vocabulary — guideline bodies scope differently) | ✅ generic table materializer, no compiler change | **in `_TABLE_DUPE_KEYS`** — disagreeing CPIC contexts coexist as distinct rows |
| PGS `PgsRow` (declared interface; ancestry-validity fields) | ✅ `PGS<digits>`, ancestry/tier vocab, `match_rate_floor∈[0,1]` | ✅ | **materialized** |
| reserved namespace (`reference_db` / `callable_element` / `quality_element`) | ✅ specific diagnosis via `reject_reserved` on top of `extra=forbid` | — | reserved |
| authoring reference + palette (`reference.authoring_reference()`/`json_schemas()`) | ✅ generated from live models (drift-proof) | n/a | **shipped** (RM8/RM9) |
| frozen `variant_key` identity (`base.derive_variant_key`) | ✅ stamped once, never re-keyed by resolution (P7); excluded from `authoring_reference()` | ✅ `weights.parquet` (compiler-managed) | **shipped** |
| rsid↔coord resolution: one-to-many expansion, deterministic order, inject-only consistency check | ✅ `ORDER BY`; disagreement → warning; non-GRCh38 skipped | ✅ N coord-keyed rows per one-to-many rsid; idempotent | **shipped** (the DuckDB engine now lives in `just-dna-enricher`; GRCh38-only; multi-build RM15) |
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
