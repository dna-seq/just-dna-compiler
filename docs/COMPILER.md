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

- **`validate_spec(spec_dir, authority_keys=None) -> ValidationResult`** — validate a spec dir without
  producing output; strips inject-only authority keys pre-validation (dropped keys → `.info`), runs
  `validate_bins` and the duplicate/identity checks, populates `.stats`.
- **`content_signature(spec_dir) -> str`** — the stable, name-/Ensembl-independent content identity over
  the raw authored data CSVs (no compile, no resolution); raises `ValueError` if a present data CSV is
  invalid. See [SCHEMAS.md § identity & integrity](SCHEMAS.md#identity--integrity).
- **`compile_module(spec_dir, output_dir, compression="zstd", resolve_with_ensembl=True,
  ensembl_cache=None, compiled_by=None, ensembl_reference=None, log_files=None, provenance_file=None,
  logo_file=None, authority_keys=None, strict=False) -> CompilationResult`** — compile to parquet +
  `manifest.json`. `resolve_with_ensembl`/`ensembl_cache` are **deprecated (removed at 1.0)** — see the
  precedence block.
- **`reverse_module(parquet_dir, output_dir, module_name=None, title=None, description=None,
  report_title=None, icon="database", color="#6435c9", version=None, write_resolution=True) -> Path`** —
  reverse a compiled artifact back to the authored DSL.

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

There is also a **trust boundary**. `resolution.csv`, `frequencies.csv` and `gene_metrics.csv` are
consumed as fact. The compiler can re-derive the parts that are *self-verifying* and cross-examine the
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
| star allele used but not defined | `allele_function`/`diplotypes` name it; `haplotypes` defines it | warning |
| **phase-ambiguous diplotypes** (0.5.1) | two *different* haplotype pairs whose unphased genotype is identical while their conclusions differ | warning |

Three of these deserve their reasoning rather than just their row.

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
| **Is an indel's `vrs_id` right?** Cannot be recomputed without justification against the sequence. | Same. | Reported as *unverifiable* (never as verified); `strict` refuses it. |
| **Is the coordinate the variant the author meant?** A perfectly valid VA for the wrong locus is indistinguishable from the right one. | Requires knowing intent. | `provenance.json`, `authorship`, and the studies table make the claim auditable by a human. |
| **Is the annotation medically correct?** Whether `A/T at HBB → sickle-cell carrier` is *true*. | Out of scope by charter — the format supplies annotation tables and never a gene–disease inference. | `authorship.kind` lets a consumer route scrutiny (AI vs human-certified); `curator`/`method` record who decided. |
| **Does the cited study support the row?** `pmid` is grammar-checked; nobody reads the paper. | Requires the literature. | **Partly closed by the enricher (0.5).** Its literature pass confirms the PMID resolves, cross-fills the DOI/PMCID, and matches `provenance_quote`/`provenance_regex` against fulltext — for the **open-access subset only**, with coverage reported as a fraction so an unread paper is never mistaken for a failed quote. The compiler still reads nothing; it surfaces the recorded verdict from `literature.csv`. |
| **Is the source stale?** A v2.1.1 constraint number is well-formed and current-looking. | The compiler cannot see the world move. | `dataset` names the release; the gene-metrics pass labels its two routes differently and warns on the older one. Generalized to **identifiers** in 0.5: the enricher checks rsIDs against dbSNP (live/merged/absent), trait CURIEs against OLS4 (obsolete + replacement) and gene symbols against HGNC (approved/retired). All report; none rewrite. |
| **Is `acmg_sf` right?** A gene-list-membership flag the compiler holds no list for. | Same shape as `clin_sig`: the list is not in the module and cannot be, since a gene list inside the compiler is an un-injected reference (RM21). | **Closed by the enricher (0.5.1).** `acmg.check_acmg_sf` compares the flag against ACMG SF v3.2 as NCBI publishes it. Warns in `best_effort`, refuses in `strict` — list membership is a published fact, not a clinical judgement, so unlike `clin_sig` it *does* escalate. A blank cell is a note, never a defect. |
| **Is the annotation medically correct?** — the clinical half. Whether the module's `clin_sig` is the right call. | Out of scope by charter (below), and ClinVar is not truth either. | **Surfaced, never adjudicated (0.5).** The enricher compares each authored `clin_sig` against the ClinVar snapshot's, allele-exactly, and reports opposed calls with ClinVar's review-star count. It is the one check whose severity does **not** escalate in `strict`: failing there would make the format decide a clinical dispute. |
| **Did the author declare every source they copied from?** A copied annotation with no `sources.csv` row is indistinguishable from an original one. | Provenance of a text is not a property of the text. | The **enricher** writes the row when it fetches (it is the only tier that knows); `sources.csv` + `manifest.sources` make the declaration legible and hashed. The compiler warns on a source a fact table cites with no row, but cannot see what was copied by hand. |
| **Did the enricher get it right?** The resolution table is consumed as fact. | The trust boundary itself. | `source`, `status`, `resolution_mode`, `fully_resolved` and `resolution_signature` make the provenance and the policy legible. |

The through-line: **what the compiler cannot validate, the format makes *legible*.** It records who
produced a fact, from which release, under which policy, and hashes it so it cannot drift silently —
then leaves the judgement to a consumer. That is the data-agnostic north star applied to trust.

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
   module).
7. **Strict gate** — if `strict` and any variant still lacks `(chrom, start)`, fail **before any parquet
   is written** (refuse a non-reproducible partial artifact).
8. **Write parquets** — SNP core (`weights`/`annotations`/`studies.parquet`, only when the relevant rows
   exist) + one parquet per present table kind + the 0.5 derived-fact sidecars
   (`frequencies.parquet`, `gene_metrics.parquet`, `literature.parquet`) when their CSVs are present,
   each cross-checked
   against what the module actually contains (a frequency coordinate no variant sits at, or a gene the
   module never mentions, is a **warning** — an over-broad sidecar is harmless, and failing the compile
   over it would punish the author for the enricher's generosity).
9. **Collect** logs / `provenance.json` / logo (a malformed one fails the compile, not raises).
10. **Build the manifest** (`content_signature` re-read from raw disk, the resolution fields, and the
    `frequency` / `gene_metrics` / `literature` blocks) and write `manifest.json`.

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
| **unverifiable** | **could not be recomputed at all** | **warning** | **error** |

**A mismatch is always fatal, in both modes.** A substitution's id is fully deterministic here — same
inputs, same 20 lines of `hashlib`, same answer — so a disagreement cannot be a difference of opinion
between implementations. It is corruption, and there is no mode in which carrying it is right.

**An indel is never reported as a mismatch, because it is never compared.** This tier cannot recompute
an indel's id (justification needs the reference sequence), so it can only report that it *did not
check*. Saying "mismatch" would assert a verdict that was never reached. `strict` refuses such a row
because *unchecked* and *correct* are different things and its contract is a reproducible artifact;
`best_effort` carries it and says so out loud. Warnings land in `manifest.compilation.warnings`, so an
unconfirmed identity is visible to a consumer rather than only to whoever ran the compile.

#### Every flow path

`_recompute_vrs_id` returns either the recomputed id or the reason there is none. The four reasons are
limits of a no-network tier, not defects in the row:

| Row | Path | `best_effort` | `strict` |
|---|---|---|---|
| no `vrs_id` | nothing to check — **not** the same as "could not check" | silent | silent |
| substitution, id agrees | verified | silent | silent |
| substitution, id differs | **mismatch** | error | error |
| indel / MNV (`C>CA`) | needs the reference sequence — minted upstream, not recomputable here | warning | error |
| multi-allelic (`alts="A,G"`) | a VA names exactly one allele; picking one would invent data | warning | error |
| position-only (no `alts`) | no ALT to name | warning | error |
| no coordinate | nothing to recompute from (an rsid row carrying an external id) | warning | error |
| off-assembly contig, or a position past the contig end | no refget accession to address the sequence by | warning | error |
| non-GRCh38 `genome_build` | no refget table for that build (RM15) | warning | error |

The last row is a fixed bug worth naming: `refget_accession` **raises** `UnsupportedBuildError` rather
than returning `None` — deliberately, so a caller asking for GRCh37 hears "not built yet" instead of
receiving a GRCh38-flavoured answer. That exception used to escape the verify pass and abort the whole
compile over a single unverifiable row. It is now caught and turned into a reason, which is the correct
severity: one row this tier cannot check should not fail a `best_effort` build.


### The inconsistent-reference-allele check (0.5)

A VA addresses the *place and the alt*; the reference base at a position is a fact of the genome and is
not part of the allele's name. Correct VRS semantics — but it drops a guarantee the old
`chrom:start:ref:alts` key gave for free, since two rows at one position claiming different reference
bases used to be two keys and are now one. At most one can be right, so `_cross_validate_variants` now
fails a compile where two positioned rows share a key and disagree on `ref`.

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
| The raw allele strings match | `True` | keeps it — checked **first**, so normalization can only ever *add* acceptances |
| The reduced allele sets match (`alleles.parsimony_reduce` strips the shared flank) | `True` | keeps it; this is what reconciles the two spellings |
| The locus is a substitution or MNV and the alleles differ | `False` | drops it — no flank, so no spelling freedom; a strand-flipped genotype stays a hard finding |
| The genotype names fewer than two distinct alleles at an indel locus | `None` | keeps it, reports that it did not decide (a homozygous call carries no frame) |
| The event **sizes** differ | `False` | drops it — re-anchoring never changes how many bases an event adds or removes |
| Same sizes, different content | `None` | keeps it, reports that it did not decide (a rotation inside a repeat, or two variants) |

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
table kind, and `frequencies.csv` / `gene_metrics.csv` when their parquets are present.

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
- **Normalized:** `genome_build` re-emitted as `GRCh38`; title/description/report_title fall back to
  name-derived defaults; icon/color from args; curator/method from the most-common column value.
- **Lost (manifest-only, out of `artifact.digest`):** `authorship`, `panel`, `provenance`, `logo`, a
  non-GRCh38 build label. A consumer needing these reads `manifest.json` (preserved verbatim by the
  forward compile).

## Output artifact & hashing

- **`_OUTPUT_FILES`** (feed `artifact.digest`): `weights`/`annotations`/`studies.parquet` + the 9
  table-kind parquets + `frequencies.parquet` / `gene_metrics.parquet` / `literature.parquet` when
  present. The sidecars enter
  the digest because a module carrying frequency data genuinely *is* different content — but adding one
  leaves the SNP core's bytes untouched (an explicit test).
- **`_INPUT_FILES`** (feed `manifest.inputs`, raw-bytes hashed): `module_spec.yaml` + `variants.csv` +
  `studies.csv` + the 9 table-kind CSVs. **`resolution.csv` is deliberately NOT here** (nor in
  `_OUTPUT_FILES`) — it is a multi-producer artifact hashed only by the normalized `resolution_signature`
  (a raw-bytes hash would be unstable across enricher/human/reverse producers). `frequencies.csv` and
  `gene_metrics.csv` and `literature.csv` are out for exactly the same reason, hashed by `frequency_signature` /
  `gene_metrics_signature`. `provenance.json` is likewise out of the digest.
- **The derived-fact sidecars are deliberately NOT `_TABLE_KINDS`.** Those are authored DSL tables with
  `AuthoredModel` semantics, the reserved-namespace guard, duplicate-key checks and raw-byte input
  hashing. A machine-produced reference-fact table is a third category — injected, fact-hashed,
  human-overridable — and folding it in would blur the line the 0.5 rework drew.
- **Manifest `Compilation` fields the compiler populates:** `compile_success`, `compiled_by`,
  `compiler_version`, `ensembl_reference`, `compiled_at`, `warnings`, and the 0.5 resolution provenance —
  `resolution_mode` (policy), `fully_resolved` (outcome — orthogonal axis, P5), `resolution_signature`,
  `resolution_sources`. All out of `artifact.digest`. Together `resolution_mode == "strict" or
  fully_resolved` tells a catalog a trustworthy module from a best-effort half-baked one.
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
| `verify <module_dir>` | **`format.integrity.verify_manifest`** | `--public-key`, `--check-inputs/-logs/-provenance/-logo` |
| `keygen` | **`format.signing.generate_private_key_pem`** + `public_key_b64_from_pem` | `--out` (refuses to overwrite) |
| `sign <module_dir>` | **`format.signing.sign_digest`** | `--private-key` |
| `reference` | **`format.reference.authoring_reference`** / `json_schemas` | `--summary`, `--schemas` |
| `template <kind>` | `draft.blank_template` + `authoring_requirements` | |
| `stub <kind>` | `draft.stub_template` | `--rows` |
| `requirements <kind>` | `draft.authoring_requirements` | `--json` |
| `scaffold <spec>` | `scaffold.scaffold_module` | `--kind`, `--rows`, `--dry-run` |
| `describe <kind>` | `hints.describe_table` | one table's columns + pick-lists |
| `hint <kind>` | `hints.inspect_rows` | `--rows-file`/`--row`, `--json` |

**Four rows are bold because they belong to `just-dna-format`, which ships no CLI of its own** —
Typer would breach its pydantic-plus-cryptography dependency floor (Goal 2). So anything the schema
tier owns that a *user* needs has to surface here, and three of the four did not until 0.5.1:

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
| `direction` (`VariantRow`) | ✅ full vocab | ✅ `weights.parquet` | ✅ `effective_direction` / `upgraded()` from `state`(+`weight`) | complete |
| `stat_significance` (`VariantRow`, `StudyRow`) | ✅ full vocab | ✅ | ✅ derived from `state` (not inferred from `p_value`) | complete |
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
| **VRS allele identity (0.5)** | ✅ stdlib `derive_vrs_allele_id`; stored `vrs_id` recomputed and verified (mode-dependent severity) | ✅ `variant_key` **is** the VA for a resolved substitution → `weights`/`annotations.parquet` | ✅ minted from `(chrom, start, ref, alt)`; indels/MNVs/multi-allelic keep the coordinate key | complete (GRCh38-only; multi-build is RM15) |
| **`frequencies.csv` path (0.5)** | ✅ `FrequencyRow`; coordinate cross-check → warning; **provisional shape** | ✅ `frequencies.parquet` (in `artifact.digest`); `frequency_signature`/`sources`/`datasets`/`populations` → **manifest** (out of digest) | ✅ `allele_frequency` = AC/AN materialized as `Float64` (never stored in the CSV) | complete (injected; enricher produces it) |
| **`gene_metrics.csv` path (0.5)** | ✅ `GeneMetricsRow`; gene cross-check → warning; **provisional shape** | ✅ `gene_metrics.parquet` (in digest); `gene_metrics_signature`/`genes`/`datasets` → **manifest** | — | complete (injected; offline-capable upstream) |
| **`literature.csv` path (0.5)** | ✅ `LiteratureRow`; citation cross-check + nonexistent-PMID warning; **provisional shape** | ✅ `literature.parquet` (in digest); `literature_signature`/`sources`/coverage counters → **manifest** | — | complete (injected; enricher produces it) |
| CLI (0.4.1, extended 0.5) | ✅ Typer `validate`/`compile`/`signature`/`reverse`/**`verify`**/**`sign`**; `--strict`, `--strip-identity`/`--authority-key`, deprecated `--ensembl-cache`, `--resolution` | — | — | complete (compiler-only dep; tiers intact) |
| **queryable p-value (0.5)** | ✅ `p_value_num` in (0, 1]; cross-checked against the verbatim `p_value` string (relative, 1%) | ✅ `studies.parquet`; **`neg_log10_p` derived on write**, absent from the reversed CSV | ✅ `-log10(p_value_num)` | complete |
| **`callable_from` (0.5, RM6)** | ✅ bare VCF field-name token, `\|`-alternatable (shared `AuthoredModel` validator) | ✅ `weights.parquet` | — | complete (retired from the reserved namespace) |
| **`recommendation_strength` (0.5)** | ✅ closed CPIC vocabulary, distinct axis from `evidence_level` | ✅ `diplotypes.parquet` | — | complete |
| **dosage sensitivity (0.5)** | ✅ `haploinsufficiency`/`triplosensitivity` against `VALID_DOSAGE_SENSITIVITY` | ✅ `gene_metrics.parquet` (in digest, fact-hashed) | — | complete (ClinGen route in the enricher) |
| **`redistribution` (0.5)** | ✅ tri-state; `None` ≠ `False` | ✅ `sources.parquet`; per-layer facet + module-wide verdict → **manifest** | ✅ most-restrictive-wins | complete (recorded, **not** gated — RM27) |
| **drafting (0.5)** | ✅ appended rows are validated rows; keys reuse `_TABLE_DUPE_KEYS` | — (writes authored CSVs, not parquet) | ✅ append / already-present / differs report | complete (`draft.append_rows`, `blank_template`) |
| **templating (0.5)** | ✅ a stub carries `TEMPLATE_PLACEHOLDER`, which no mode compiles | — (writes authored CSVs, not parquet) | ✅ created / kept-untouched plan | complete (`draft.stub_template`, `scaffold.scaffold_module`) |
| **hints (0.5)** | ✅ per-cell validation, bin coverage, duplicate keys — all offline | — (writes nothing at all) | ✅ alterations + findings + options | complete (`hints.inspect_rows`, `hints.describe_table`) |
| **delegated insertion (0.5.1)** | ✅ placed rows are validated rows; shifted rows keep their cells | — (writes authored CSVs, not parquet) | ✅ `DraftReport.shifted` names every moved row | complete (`draft.place_rows`, `append_rows(group_by=…)`) |
| **partial rows (0.5.1)** | ✅ stubbed columns validated by omission; the stub itself never compiles | — (writes authored CSVs, not parquet) | ✅ added / already-present / invalid | complete (`draft.PartialRow`, `append_partial_rows`) |
| genotype widening: hemizygous single allele | ✅ | ✅ (1-element list) | — | complete |
| genotype widening: phased `A\|G` | ✅ (order kept) | ✅ `phased` bit → lossless round-trip | ✅ | complete |
| `state` (legacy) | ✅ (stays required — P8) | ✅ | ✅ read alias via `effective_direction`; trimmed to {protective,risk,neutral} on `upgraded()` | complete |
| MT / non-diploid genotype | ✅ warning on a two-allele MT or Y genotype | — | — | complete |
| direction/weight sign consistency | ✅ warning | — | — | complete |

## 0.4 compiler coverage (materialized)

| 0.4 kind (model) | Validated | Materialized (→ parquet, round-trip) | Status |
|---|---|---|---|
| binning primitive `MeasureBinRow` + `Activity/CopyNumber/RepeatAllele/Heteroplasmy` rows | ✅ shared vocab, inclusive `[min,max]`, mandatory `unresolved`, `extra=forbid`, `source_field` pointer, heteroplasmy `tissue` + legacy-ref guard | ✅ `*.parquet` via generic materializer | **materialized** |
| table-level `validate_bins(rows)` | ✅ per `(key…, trait_efo_id)` group | overlap → error, gap → warning, >1 `unresolved`/group → error | **enforced** |
| duplicate-row detection (diplotype pair, `pgs_id`, `(pharm variant, drug, genotype, category, annotation_id)`, allele-function allele, haplotype-defining variant) | ✅ per-kind natural key | error (0.4 analog of duplicate-(variant, genotype)) | **enforced** |
| PGx `HaplotypeRow` / `AlleleFunctionRow` / `DiplotypeRow` (+ `drug`/`response`/`evidence_level`) | ✅ | ✅ | **materialized** |
| PharmGKB `PharmVariantRow` (single-variant drug response, `evidence_level` 1A…4, per-genotype) | ✅ | ✅ | **materialized** |
| **`sources.csv` licensing path (0.5)** | ✅ `SourceRow`; tri-state permissions; orphan/undeclared + declared-licence warnings (never escalate) | ✅ `sources.parquet` (in digest); `source_signature`/licences/attributions/per-layer facets/derived `commercial_use` → **manifest** | ✅ **refuses** (both modes) when annotation-layer terms forbid sale and no declaration is recorded | **complete** (injected; enricher produces it) |
| `VariantRow` general axes: `requires_callable` / `acmg_sf` / `actionability` | ✅ (`actionability` vs `ACTIONABILITY_SEED`; `acmg_sf` vs the ACMG SF list in the **enricher**, 0.5.1) | ✅ into `weights.parquet` (tri-state bool round-trip) | **materialized** |
| **RM29a call-confidence cofactor: `quality_from` + `min_quality` (0.5.1)** | ✅ shared pointer grammar (`source_field`/`callable_from`/`quality_from`, one validator); finite floor; **both-or-neither** model rule | ✅ `weights.parquet` (`Utf8` + `Float64`); absent floor is null, never `0.0` | **materialized** |
| **RM29b clinical cofactor: `DiplotypeRow.clinical_context` (0.5.1)** | ✅ whitespace-stripped, open (no vocabulary — guideline bodies scope differently) | ✅ generic table materializer, no compiler change | **in `_TABLE_DUPE_KEYS`** — disagreeing CPIC contexts coexist as distinct rows |
| PGS `PgsRow` (declared interface; ancestry-validity fields) | ✅ `PGS<digits>`, ancestry/tier vocab, `match_rate_floor∈[0,1]` | ✅ | **materialized** |
| reserved namespace (`reference_db` / `callable_from`) | ✅ specific diagnosis via `reject_reserved` on top of `extra=forbid` | — | reserved |
| authoring reference + palette (`reference.authoring_reference()`/`json_schemas()`) | ✅ generated from live models (drift-proof) | n/a | **shipped** (RM8/RM9) |
| frozen `variant_key` identity (`base.derive_variant_key`) | ✅ stamped once, never re-keyed by resolution (P7); excluded from `authoring_reference()` | ✅ `weights.parquet` (compiler-managed) | **shipped** |
| rsid↔coord resolution: one-to-many expansion, deterministic order, inject-only consistency check | ✅ `ORDER BY`; disagreement → warning; non-GRCh38 skipped | ✅ N coord-keyed rows per one-to-many rsid; idempotent | **shipped** (the DuckDB engine now lives in `just-dna-enricher`; GRCh38-only; multi-build RM15) |

## Upgrade derivation (`state`/booleans → 0.3 axes)

`state` and the ClinVar booleans **stay required/authoritative** for 0.2 backward-compat (P8). The new
axes are optional, and `just_dna_format.derive` supplies fallbacks:

- **Read-time (non-mutating):** `VariantRow.effective_direction` / `effective_stat_significance` /
  `effective_clin_sig` / `effective_pathogenic` / `effective_benign` return the set column, else the
  derivation — so a legacy 0.1/0.2 row exposes all three axes with no re-publish.
- **Materializing:** `VariantRow.upgraded()` fills those axes and trims `state` to `{protective, risk,
  neutral}` (kept as a derived mirror of `direction`). `needs_upgrade` is the signal the marketplace
  `revalidate`/`needs_upgrade` flow consumes. Both idempotent (P7).

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
4. **`reverse_module` reconstructs the compilable core, not manifest-only metadata** (reads parquet only,
   never `manifest.json`). `authorship`/`panel`/`provenance`/`logo` are not restored and `genome_build`
   emits `GRCh38`; the digest fixed point still holds (these are out of the digest). What *is*
   round-trip-critical — every authored value, including a poly-effect variant's per-effect
   `gene`/`phenotype`/`category` — is restored.

## Consequences worth knowing

- **`weights.parquet`/`studies.parquet` carry the 0.3 columns + a `phased` bit**, so a re-compile under
  this compiler changes `artifact.digest` for every module; reproducibility is pinned by
  `compiler_version`, and published versions keep their digest until re-published. (Pre-1.0 digest moves
  are still free to absorb while unpublished.)
- **Round-trip is lossless and idempotent** (P7): `reverse_module` → recompile preserves every column
  including phase, and the same spec compiles twice to the same digest. In 0.5 the round-trip is
  additionally **offline** — reverse emits `resolution.csv`, so recompile needs no reference and no
  network (regression-tested: DuckDB compile → reverse → no-cache recompile → identical digest).
- The **`ValidationResult.info`** channel carries non-reserved `flags` notes via stdlib logging — the
  format packages do not depend on Eliot.

Tests: `compiler/tests/test_v03*.py` (validator, genotype widening, warnings/INFO, materialization,
round-trip/idempotency); `test_v04_compile.py` (the nine table kinds); `test_resolution_table.py` (the
0.5 resolution-table path, digest parity, offline round-trip, strict/best-effort, the deprecation).
