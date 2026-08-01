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
| `allele_count ≤ allele_number` | a count cannot exceed its denominator | error |
| `2 × homozygote_count ≤ allele_count` | each homozygote contributes two alleles | error |
| `faf95 ≤` the group's own AF | a CI lower bound sits below its point estimate | warning |
| `oe_lof_lower ≤ oe_lof ≤ loeuf` | an estimate lies inside its own interval | warning |
| `obs_lof / exp_lof == oe_lof` | the same quantity, stored three ways | warning |
| direction ↔ weight sign | two encodings of one claim | warning |
| MT/Y two-allele genotype | ploidy contradicts the contig | warning |
| study / frequency / gene-metrics orphans | the sidecar describes something the module lacks | warning |

**3. Content-addressed self-verification** — the strongest class, because the stored value is a *pure
function of other stored values*, so a disagreement is provable corruption rather than a difference of
opinion. `artifact.digest`, `content_signature`, the three fact-signatures, the Ed25519 signature —
and, since 0.5, **`vrs_id`**. Moving allele identity into this class is what the VRS work bought: a
`ga4gh:VA.…` used to be an opaque cross-reference that had to be believed, and is now a checksum the
compiler recomputes from the coordinate with no dependency and no network.

### The inescapable blind spots

These are not gaps to be closed later. Each follows from what the tier *is*, and pretending otherwise
would be worse than saying so.

| Blind spot | Why it is inescapable | What the format does instead |
|---|---|---|
| **Is a single-sourced number right?** An AC/AN, a pLI, a `clin_sig` — one source, no redundancy to exploit. A transcription error is indistinguishable from a correct value. | Nothing to check it against without fetching (Principle 2). | Records `dataset` (which release) and `source` (which link) so the number is *attributable*, and fact-hashes it so it cannot change unnoticed. |
| **Is the reference base right?** A wrong single-base `ref` mints the *correct* VA, so the artifact is self-consistent and wrong. | The compiler holds no sequence. | The **enricher** checks it (`sequences.verify_reference_alleles`); the compiler catches only two rows *contradicting each other*. |
| **Is an indel's `vrs_id` right?** Cannot be recomputed without justification against the sequence. | Same. | Reported as *unverifiable* (never as verified); `strict` refuses it. |
| **Is the coordinate the variant the author meant?** A perfectly valid VA for the wrong locus is indistinguishable from the right one. | Requires knowing intent. | `provenance.json`, `authorship`, and the studies table make the claim auditable by a human. |
| **Is the annotation medically correct?** Whether `A/T at HBB → sickle-cell carrier` is *true*. | Out of scope by charter — the format supplies annotation tables and never a gene–disease inference. | `authorship.kind` lets a consumer route scrutiny (AI vs human-certified); `curator`/`method` record who decided. |
| **Does the cited study support the row?** `pmid` is grammar-checked; nobody reads the paper. | Requires the literature. | `provenance_quote` / `provenance_regex` (RM11/RM12) are *consumer-side* affordances for exactly this. |
| **Is the source stale?** A v2.1.1 constraint number is well-formed and current-looking. | The compiler cannot see the world move. | `dataset` names the release; the gene-metrics pass labels its two routes differently and warns on the older one. |
| **Did the enricher get it right?** The resolution table is consumed as fact. | The trust boundary itself. | `source`, `status`, `resolution_mode`, `fully_resolved` and `resolution_signature` make the provenance and the policy legible. |

The through-line: **what the compiler cannot validate, the format makes *legible*.** It records who
produced a fact, from which release, under which policy, and hashes it so it cannot drift silently —
then leaves the judgement to a consumer. That is the data-agnostic north star applied to trust.

### And what is not the compiler's job at all

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
   (`frequencies.parquet`, `gene_metrics.parquet`) when their CSVs are present, each cross-checked
   against what the module actually contains (a frequency coordinate no variant sits at, or a gene the
   module never mentions, is a **warning** — an over-broad sidecar is harmless, and failing the compile
   over it would punish the author for the enricher's generosity).
9. **Collect** logs / `provenance.json` / logo (a malformed one fails the compile, not raises).
10. **Build the manifest** (`content_signature` re-read from raw disk, the resolution fields, and the
    `frequency` / `gene_metrics` blocks) and write `manifest.json`.

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

### `resolve_from_table` (`compiler/resolution.py`)

Pure. Mirrors the DuckDB resolver's semantics from the injected table: **fill (1:1)** a `variant_key`
with one usable locus fills the missing coord/rsid (frozen key kept); **expand (1:N)** an rsid with N
usable loci becomes N coord-keyed rows, each re-keyed by `derive_variant_key`; **verify** a row with both
rsid and coord is checked, a disagreement is a warning (never fatal). GRCh38-bound (a non-GRCh38 module
is skipped with a warning; `not_found`/wrong-build rows are ignored).

## Reverse

`reverse_module` reads the **parquet artifact only** (never `manifest.json`) and emits into `output_dir`:
`module_spec.yaml` (always), `variants.csv` + `resolution.csv` (when `weights.parquet` exists;
`resolution.csv` gated on `write_resolution=True`), `studies.csv` (when present), one CSV per present
table kind, and `frequencies.csv` / `gene_metrics.csv` when their parquets are present.

- **Preserved (round-trip-critical, Principle 7):** every authored `VariantRow`/`StudyRow`/table value;
  genotype phase (the `phased` bit re-emits `A|G` vs sorted `A/G`); tri-state bools; `priority` verbatim;
  poly-effect annotations keyed on `(variant_key, conclusion, negatives)`.
- **Frozen-`variant_key` authored shape:** the stored key decides emission — a row keyed on its rsid
  emits the rsid; a coord-keyed row (resolved rsid, position-only, or an expanded one-to-many locus) emits
  **position-only**, dropping the resolved rsid so recompute + re-resolution reproduce the same key.
- **`resolution.csv` emission** carries that dropped rsid back: one `ResolutionRow` per positioned weights
  row (`source="reversed"`, `status="resolved"`, `locus_index=0`), so **`reverse → compile` reproduces the
  identical `artifact.digest` with no reference and no network** — hardening Principle 7's round-trip from
  reference-dependent to self-contained.
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
  table-kind parquets + `frequencies.parquet` / `gene_metrics.parquet` when present. The sidecars enter
  the digest because a module carrying frequency data genuinely *is* different content — but adding one
  leaves the SNP core's bytes untouched (an explicit test).
- **`_INPUT_FILES`** (feed `manifest.inputs`, raw-bytes hashed): `module_spec.yaml` + `variants.csv` +
  `studies.csv` + the 9 table-kind CSVs. **`resolution.csv` is deliberately NOT here** (nor in
  `_OUTPUT_FILES`) — it is a multi-producer artifact hashed only by the normalized `resolution_signature`
  (a raw-bytes hash would be unstable across enricher/human/reverse producers). `frequencies.csv` and
  `gene_metrics.csv` are out for exactly the same reason, hashed by `frequency_signature` /
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

## CLI

`just-dna-compiler` (Typer): `validate <spec>`, `compile <spec> <out>`, `signature <spec>`,
`reverse <parquet_dir> <out>`. Exit 0/1 (CI/registry-gateable). Key flags: `compile` takes
`--strict/--no-strict`, `--resolve/--no-resolve`, `--compression`, `--compiled-by`,
`--strip-identity`/`--authority-key`, and the **deprecated** `--ensembl-cache` (routes to the enricher,
removed at 1.0); it prints `digest`, `content_signature`, and `resolution_mode`/`fully_resolved`/
`resolution_signature`. `reverse` takes `--resolution/--no-resolution` (default on) plus the
display-metadata overrides.

## Coverage table (0.3 / 0.4 features)

| 0.3 / 0.4 feature | Validated | Materialized (→ parquet) | Computed / derived | Status |
|---|---|---|---|---|
| `direction` (`VariantRow`) | ✅ full vocab | ✅ `weights.parquet` | ✅ `effective_direction` / `upgraded()` from `state`(+`weight`) | complete |
| `stat_significance` (`VariantRow`, `StudyRow`) | ✅ full vocab | ✅ | ✅ derived from `state` (not inferred from `p_value`) | complete |
| `effect_size` (`VariantRow`, `StudyRow`) | ✅ float | ✅ | — | complete |
| `effect_measure` (`VariantRow`, `StudyRow`) | ✅ permissive (open) | ✅ | — | complete (intentionally open) |
| `effect_allele` (`VariantRow`) | ✅ nucleotides | ✅ | ⛔ no strand/ref reconciliation | validate + passthrough |
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
| CLI (0.4.1) | ✅ Typer `validate`/`compile`/`signature`/`reverse`; `--strict`, `--strip-identity`/`--authority-key`, deprecated `--ensembl-cache`, `--resolution` | — | — | complete (compiler-only dep; tiers intact) |
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
| duplicate-row detection (diplotype pair, `pgs_id`, `(pharm variant, drug)`, allele-function allele, haplotype-defining variant) | ✅ per-kind natural key | error (0.4 analog of duplicate-(variant, genotype)) | **enforced** |
| PGx `HaplotypeRow` / `AlleleFunctionRow` / `DiplotypeRow` (+ `drug`/`response`/`evidence_level`) | ✅ | ✅ | **materialized** |
| PharmGKB `PharmVariantRow` (single-variant drug response, `evidence_level` 1A…4) | ✅ | ✅ | **materialized** |
| `VariantRow` general axes: `requires_callable` / `acmg_sf` / `actionability` | ✅ (`actionability` vs `ACTIONABILITY_SEED`) | ✅ into `weights.parquet` (tri-state bool round-trip) | **materialized** |
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
2. **`effect_allele` strand/ref reconciliation.** Validated (nucleotides) and passed through; the `+`
   strand / `genome_build` assumption is documentation, not an enforced computation.
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
