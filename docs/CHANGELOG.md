# Changelog

Shared change log for the just-dna module format/compiler ecosystem. Because
`just-dna-format` + `just-dna-compiler` are consumed by **just-dna-pipelines**,
**just-dna-marketplace**, and **just-dna-agents**, cross-repo integration changes are recorded
here so parallel work in the other repos isn't surprised. Newest first.

## 2026-08-01 — 0.5.0: validation tightening, and resolution made reversible

Where the previous round *added* facts, this one *checks* them. The organising idea is the one written
down in [COMPILER.md § what the compiler can and cannot validate](COMPILER.md): the compiler proves an
artifact well-formed and self-consistent, never true, and several of its blind spots are closable by the
enricher — the only tier that can compare authored data against reality.

**New offline compiler checks (validate-by-redundancy).** Every genotype allele and every
`effect_allele` must be one of the alleles its locus actually has (`{ref} ∪ alts`). A genotype `A/G` at
a `C>T` locus — a strand flip, the classic transcription slip — compiled clean before this. A wrong
`effect_allele` is the more dangerous of the two, because `direction`/`weight`/`effect_size` are all
stated *relative to* it, so naming the wrong allele silently inverts the module's conclusion rather than
corrupting it visibly. Also new: an **ACMG BA1 lint** (a `pathogenic` variant whose filtering allele
frequency exceeds a threshold), newly possible only because `frequencies.csv` exists.

**⚠️ Two things about that check's severity, both decided by dogfooding rather than by argument.** The
plan specified an unconditional error when the row's *own* `ref`+`alts` contradict its genotype — author
versus author, apparently decidable. It is not, and building it that way broke the suite in a way worth
recording: **`ref`/`alts` in `variants.csv` are not necessarily human-authored, because `reverse_module`
writes them too.** A one-to-many rsid reverses into N rows that each carry their own locus's alleles
beside the *one* genotype the author wrote, so exactly one of them can match. An unconditional error
would mean any module with a one-to-many rsid compiles once and never again — Principle 7's fixed point,
broken by a lint. Severity is therefore the mode ladder in both provenance cases (warn / error in
`strict`), with provenance shaping only the *message*. Relatedly, the check compares against the
**union** of every locus a key resolves to, never per-expanded-row: run per-row it produced three
findings on this repo's own `reference_examples/pathogenic_clinvar/`, and unioned it produces none.
Both properties now have regression tests built from the real `rs281864532` shape.

**New: the ClinVar clinical cross-check** (`clinical.verify_clin_sig`, offline). Compares each authored
`clin_sig` against the ClinVar snapshot's own and reports opposed calls with ClinVar's review-star
count. Matching is **allele-exact, never rsID-level**, and the committed slice shows why: `rs334` at
11:5227002 carries `T>A` as pathogenic (2 stars) *and* `T>G` as likely_benign (1 star). One rsID, one
locus, two opposite calls — an rsID-level comparison would report a module that is simply right. It is
also **the one check whose severity does not escalate in `strict`**: failing there would make the format
arbitrate a clinical dispute, which the data-agnostic charter forbids. A curator who disagrees with a
one-star submission is doing their job.

**New: the literature pack and a third derived-fact sidecar.** `literature.csv` → `LiteratureRow`, one
row per **citation** — the first sidecar not keyed on a variant, because a DOI and a PMCID are
properties of the paper, not of the variant citing it. Fact-hashed by `literature_signature`, compiled
to `literature.parquet`, summarized in a new `manifest.literature` block. The enricher pass confirms
each `pmid` resolves in PubMed, cross-fills DOI/PMCID, and matches `provenance_quote`/`provenance_regex`
against Europe PMC fulltext for the open-access subset. **Coverage is partial by nature and is reported
as a fraction**: `quotes_found` is *null* when no fulltext could be read and *0* when one was read and
the quote was absent. Collapsing those would report an unread paper as a wrong citation.

**New: identifier currency** (`identifiers.py`) — the generalization of the *"is the source stale?"*
blind spot from datasets to identifiers. rsIDs against dbSNP (live / merged / absent), trait CURIEs
against OLS4 (obsolete + replacement term), gene symbols against HGNC (approved / previous). The rsID
verdict lands on two new **provenance** columns, `ResolutionRow.rsid_current` / `rsid_status`, kept
outside `RESOLUTION_FACT_FIELDS` so a dbSNP merge cannot move a module's `resolution_signature` with no
change to the module. Report, never repair — `weights.parquet` carries `rsid` as identity, so writing a
merged-into label back would migrate `variant_key` by network lookup.

**Corrections to the plan, made under probing rather than assumed.**
(i) **The PMC ID converter is not used at all**, though the plan budgeted for it as a separate step:
`esummary` already returns both `doi` and `pmc` in `articleids`, and the converter answers a *different*
question — for PMID 12345678, a real indexed record, it replies `"Identifier not found in PMC"`, so
wiring it in as an existence check would flag every paywalled article as a broken citation.
(ii) **Europe PMC is not an existence oracle**: asked about three ids where one does not exist, it
returns two results and silently omits the third, with no error marker.
(iii) **`literature.csv` carries no `dataset` column.** Every other fact table has one because gnomAD
ships numbered releases; PubMed and Europe PMC publish no release identifier, so the column could only
be null or a fabricated label.
(iv) **`quote_found` became two integer counts**, because a quote is authored per study row while the
table's grain is the citation — one boolean would have to lie about one of them.
(v) **The automated rsID check can never emit `withdrawn`.** ROADMAP asked for the withdrawn shape to
be probed before deciding; probing dissolved the question instead of answering it. `rs11273140`
(genuinely withdrawn) returns a response **byte-identical** to `rs2000000000` (never assigned) across
`esummary`, `esearch` and Ensembl alike. So the check reports `absent` and its *message* names both
readings without choosing — guessing "typo" sends an author to fix the wrong thing when the truth is
that the variant itself was retracted. The vocabulary member is kept regardless; see the `withdrawn`
paragraph below for why, and for why its severity is not `absent`'s.
(vi) **A thread-based regex timeout does not work**, and looks like it does. `re` cannot be interrupted,
threads cannot be killed, and the interpreter joins pool threads at exit — so a runaway pattern returns
`None` on schedule and then hangs the process on the way out (observed: the test suite stopped). The
bound is a killable child process instead. No `google-re2` dependency was added; the charter's
linear-time requirement was written when the match was specified as consumer-side, and here the pattern
comes from the module being enriched, on the author's own machine.
(vii) **Dogfooding the reference example found a reporting bug in the coverage sentence.** Its single
citation (PMID 29165669, the ClinVar paper) is open access *and* carries no provenance quote, and the
first implementation reported "1 have no retrievable fulltext" — the opposite of true. The denominator
now counts only citations that actually carry a quote: one that asks no question was not skipped for
lack of an answer.
(viii) **A previously-filed loose end was not a bug.** `reverse_module` omitting `rsid_alternates` was
recorded as an open defect; it is neither open nor fixable there. Reverse rebuilds `resolution.csv` from
`weights.parquet`, which by design holds no provenance at all — it already resets `source`, `status` and
`fetched_at` — and the provenance columns are kept out of the artifact on purpose, so the information
does not exist for reverse to emit. Documented as intended behaviour instead.

**Fixtures are recorded, not fabricated.** New committed assets: `pubmed_esummary_payload.json`,
`europepmc_search_payload.json`, `europepmc_fulltext_PMC5753237.xml` (real JATS, matched with a phrase
read out of that same document), `dbsnp_esummary_payload.json`, `ols4_terms_payload.json`,
`hgnc_fetch_payload.json`, `crossref_works_payload.json` (a journal article, a bioRxiv preprint with no
PMID, and a fabricated DOI that 404s). Each captures a quirk a hand-written fixture would have smoothed away, and
the withdrawn-vs-never-assigned equality is asserted **on the recordings themselves**, so a future dbSNP
release that *does* separate them fails the test rather than silently invalidating the design. Each new
test file also carries an opt-in live probe (`JUST_DNA_NETWORK_TESTS=1`) that re-asks the real services
the same questions; all pass.

**⚠️ Resolution became reversible, and `weights.parquet` gains `authored_ident`.** The allele-membership
check above turned up rows in this repo's own reference example asserting alleles their locus does not
have — not authoring errors, but *fabrications produced by the compiler*: a one-to-many rsid copies one
authored genotype onto N loci, and reverse then wrote each locus out as an authored row. Three of the
23 expanded rows in `reference_examples/pathogenic_clinvar/` were of that kind. Two changes fix it at
the source:

* **A locus whose `{ref} ∪ alts` cannot host the authored genotype is no longer expanded onto**
  (`resolution.genotype_fits`, shared with the deprecated DuckDB path so digest parity holds).
* **`VariantRow.authored_ident`** records which identity columns the author actually supplied, stamped
  at load beside `variant_key` and materialized to the artifact. Reverse re-emits exactly that shape:
  an rsid-only row comes back rsid-only instead of carrying resolved coordinates, and an expansion
  collapses back to the single row it was written as. This is only possible now that the key is
  canonical — a VRS allele id identifies the row without the coordinate having to live in
  `variants.csv`, which under coordinate-first keying it did.

Consequence: **`content_signature` is now a round-trip fixed point for rsid-authored modules**, where
before it moved on *every* one of them. Not a regression being fixed — the behaviour dates from 0.4's
frozen-identity work and was tested under the name `test_expanded_rsid_roundtrips_as_position_only`;
what changed is that canonical keys made the better answer available.

**Forward resolution is now allele-aware too.** The reverse (position→rsid) back-fill has matched on
the exact allele since 0.5; the forward (rsid→loci) direction did not, and that asymmetry is what put
unusable loci into the table in the first place. A candidate whose alleles cannot host the authored
genotype is now reported and left out. The compiler keeps the same check as a safety net for
hand-authored tables (the predicate is shared, so they cannot drift), but a table the enricher produced
no longer needs it — which is what lets the reference example compile under `--strict`.

**The resolution round-trip contract, enumerated.** Five identity columns the author may or may not
supply, crossed with what the table says about them, is a finite set — so it is enumerated in
`compiler/tests/test_resolution_matrix.py` under one rule: **every combination is either a round-trip
fixed point on all three signatures, or it fails in `strict`.** Making that true required tightening two
cases that used to pass quietly: an authored coordinate or `ref` contradicting the table (the artifact
keeps the authored value, so the table's is lost on reverse) now refuses in `strict`, and so does an
`ambiguous` rsid — not because anything is lost, but because a deterministic pick among equals is a pick,
not a finding. `artifact.digest` remains a fixed point in *every* case, including the unstable ones.
Also fixed while enumerating: a coordinate-only row never adopted the table's `alts`, so the resolved
allele never reached the artifact.

**Citation coverage beyond PubMed, and beyond the open-access subset.** Two additions, both probed
before being built. **Crossref** confirms the *authored* DOI resolves — the registry's own exists by
construction — which covers what PubMed structurally cannot index (a probed bioRxiv preprint returns
`type: posted-content`; a fabricated DOI 404s) and de-risks the 1.0 doi-first flip, since existence
checking then works without a PMID. And the quote check now **falls back to the abstract**, which
Europe PMC serves for non-open-access records in the response the pass already makes: four of five
probed non-OA papers carried one. A new `quote_source` column records how far the search reached,
because a hit and a miss are not symmetric — a phrase found in an abstract is in the paper, while a
phrase absent from a 200-word abstract says nothing about the body, so an abstract miss still counts
as unchecked. Worth stating plainly since it was easy to misread: **a paywall never hid *existence*** —
PubMed indexes paywalled work, and `exists` was always answered for it. Rejected explicitly rather than
deferred: **Google Scholar** (no API, and automated querying violates its terms); OA-repository PDF
retrieval via OpenAlex/Unpaywall is on the roadmap, since the closed paper probed had no OA copy at all
and the ones that exist are PDFs.

**`withdrawn` is back in `VALID_RSID_STATUS`, with its own severity.** Nothing automated emits it — a
retraction is byte-identical to a never-assigned id through every live endpoint, so the check still
reports `absent` and names both readings — but the member is kept so a curator who has established a
retraction can record it, and so a future source can start producing it without a vocabulary change
(Principle 3 makes that a one-way door). It is **not** interchangeable with `absent`: absent has benign
causes and refuses only under `strict`, while a retracted variant may leave the annotation describing
nothing, so `withdrawn` refuses in `best_effort` too — the only resolution finding that does.

**A correction to the analysis, caught by the repo's own fixture rule.** The first pass concluded that
an ambiguous resolution could not be round-trip stable and therefore had to be an error in both modes.
That came from a hand-written two-row fixture; the enricher actually writes **one** row carrying the
deterministic pick, with the candidate list in `rsid_alternates` (provenance, outside the fact set). The
real shape is stable, so ambiguity stays a best-effort warning as intended.

**Also:** `PacingGate`/`batched`/`dedupe` moved out of `gnomad.py` into a shared `net.py` (three clients
now need them), a new `eutils.py` NCBI client shared by the literature and rsID checks, and the
compiler's two-way fact-table branch became a per-model dispatch that scales past three sidecars.
`compile_module` gains an optional `ba1_threshold`; `enrich()` gains `verify_clinsig` / `verify_rsids`;
new CLI commands `literature` and `check-identifiers`.

## 2026-07-31 — 0.5.0: gnomAD v4.1 (frequency + gene constraint) and GA4GH VRS identity

Three roles for one source, plus the identity change the VRS work unlocked. Design thread and the
reasoning in [PROPOSAL_0_5.md § G1](PROPOSAL_0_5.md); use cases in [USE_CASES.md §6](USE_CASES.md).

**New derived-fact sidecars** (schema + compiler + enricher). `frequencies.csv` → `FrequencyRow`, one
row per **(allele, ancestry group)** carrying AC/AN, `homozygote_count`, `faf95` and `dataset`;
`gene_metrics.csv` → `GeneMetricsRow`, one row per gene carrying pLI/LOEUF/Z scores. Both are injected,
machine-produced, human-overridable, hashed by **facts** (`frequency_signature` /
`gene_metrics_signature`, sharing one `fact_signature` body with `resolution_signature`), and compiled
into their own optional parquets with new `manifest.frequency` / `manifest.gene_metrics` blocks. They
are deliberately **not** `_TABLE_KINDS` — a machine-produced reference-fact table is a third category
beside authored DSL tables and the compiled artifact. `allele_frequency` is a **derived** property
materialized only in the parquet: integers round-trip exactly through CSV, a stored float does not.
Ancestry groups are an **open, seeded** vocabulary (the table must outlive gnomAD as its only source).

**gnomAD in the enricher.** A new `gnomad.py` client — batches of 20 aliased GraphQL lookups on a 6s
pacing gate (the stated limit is 10 requests/IP/60s), tenacity on transport/timeout/429, and per-alias
error handling so a partial failure keeps the rest of the batch. A **last-resort resolver link**
(`source="gnomad"`, after live Ensembl so no compiled module's `alts` or digest can move), the
frequency pass (online only — the v4.1 sites VCFs are 58 GB / 742 GB, so no snapshot is possible), and
the gene-constraint pass (snapshot first, live API second — the one gnomAD role that completes offline),
with a `[dev]` builder for the 95.5 MB constraint TSV and a third HF snapshot on the existing ladder.

**GA4GH VRS allele identity — minted, not merely recorded.** New stdlib `just_dna_format.vrs`:
`derive_vrs_allele_id` computes a `ga4gh:VA.…` for a substitution with `hashlib`/`base64`/`json` and
**no new dependency in the format tier**, against a committed GRCh38 refget table. `ResolutionRow` and
`FrequencyRow` gain `vrs_id`/`vrs_spec`/`caid` cross-reference columns (outside the fact sets, so no
existing `resolution_signature` moves). The enricher mints indels too, normalized against the reference.

**⚠️ `variant_key` now derives from the VA for a resolved substitution — `artifact.digest` moves.**
An rsid row keeps its rsid; an indel, MNV, multi-allelic or position-only row keeps its coordinate key.
This is legal now, not at 1.0, because `variant_key` is *derived and frozen, never authored* — no
authored schema, no DSL, and no human author is touched. It is major-only for one reason (the column is
in `weights.parquet`, hence in the digest), and that gate is **publication**, not the version number:
0.4 is the published line and 0.5.0 never shipped, so this rides the same one-time pre-publication
re-baseline as the alt-carrying key. **No published artifact moves.** A VRS id also *names its build*
(the refget accession is the digest of the reference sequence), which is exactly the condition RM15 set
for reconsidering coordinate-first identity — so that parking is resolved, with multi-build minting the
remaining RM15 half. Modules compiled on an earlier 0.5.0 dev commit must be recompiled.

**Two compiler checks come with it.** A stored `vrs_id` is recomputed and verified before anything is
written, with **three** outcomes rather than two: *verified* (silent), *mismatch* (recomputed and
different — an error in both modes, since a substitution's id is deterministic here and a disagreement
can only be corruption), and *unverifiable* (could not be recomputed at all — a warning in
`best_effort`, an error in `strict`, because "unchecked" and "correct" are different things). An indel
is never reported as a mismatch: this tier cannot recompute one, so it can only say it did not check.
Unverifiable also covers multi-allelic, position-only, no-coordinate, off-assembly and non-GRCh38 rows;
the last used to let `UnsupportedBuildError` escape and abort the whole compile, and the off-assembly
case used to pass `strict` silently — both fixed, with a full matrix test. And because a VA addresses
the *place and the alt* but not `ref`, two positioned rows sharing a key while disagreeing on `ref` are
now an explicit error — preserving a diagnosis the old key gave for free.

**New: the reference-allele check, and enrichment-as-validation stated as a goal.** `sequences.py`
compares every authored `ref` against the actual reference bases and reports disagreements on
`EnrichmentResult.ref_mismatches` (`--verify-ref/--no-verify-ref`; `best_effort` warns, `strict`
refuses). This closes a gap the VRS work opened: a VA is built from *which sequence*, *which interval*
and *what replaces it*, so the reference allele is not a component — which means minting never checks
it, and VCF's free `REF` consistency check (liftover slips, off-by-ones, wrong assembly) had no
equivalent. Two failure modes, separated by the claimed length: a **single-base** wrong ref is absorbed
(the same id is minted, so nothing downstream could notice), while a **multi-base** wrong ref sets the
wrong interval and mints a well-formed id for a *different allele*. Findings are **reported, never
repaired** — rewriting an authored value would destroy the evidence that something upstream is broken.
[ENRICHER.md](ENRICHER.md) now states the general principle: the enricher is the only tier that *can*
compare authored data against reality (format and compiler are inject-only by charter), so surfacing
discrepancies is part of its job, and every such check reports rather than repairs with severity
following the mode.

**New: the validation model is written down, limits included.** [COMPILER.md](COMPILER.md) now opens
with *What the compiler can and cannot validate* — the trust boundary with the enricher, the three
strengthening classes of check it performs (formal conformance → validate-by-redundancy →
content-addressed self-verification), and an explicit table of **inescapable blind spots**. The
compiler is an assembler/linker, not a truth oracle: it proves an artifact well-formed and
self-consistent, never true, and several things it cannot check are permanent consequences of being a
no-network tier or of the data-agnostic charter. What it cannot validate, the format makes *legible*
instead (`source`, `dataset`, `status`, `authorship.kind`, the signatures). Framing the VRS work in
those terms: it moved `vrs_id` out of "opaque cross-reference you must believe" into the
self-verifying class, which is the strongest static guarantee available here.

**New: validate-by-redundancy on the sidecars.** The new tables' numbers constrain each other, so
violations are detectable with no reference at all: `allele_count ≤ allele_number` and
`2 × homozygote_count ≤ allele_count` are exact integer impossibilities (**errors**), while
`faf95 ≤` the group's own AF, `oe_lof_lower ≤ oe_lof ≤ loeuf`, and `obs_lof / exp_lof == oe_lof` are
float relations that hold on real gnomAD output and **warn** when they break (the last catches a
column-mapping slip in a builder). A test asserts the recorded payload trips none of them — a
redundancy check that fires on genuine data is worse than no check.

**Fixed: the canonical trait example was an obsolete ontology term.** `EFO_0001645` (used in
`spec.py`'s `trait_efo_id` description, `vocab.py`'s CURIE comment and its author-facing error message,
`REFERENCE_EXAMPLES.md`, and a compiler fixture) has been retired in favour of `MONDO_0005010`. The
grammar examples now use `EFO_0004340`; the two coronary-artery-disease examples use `MONDO_0005010`.
Found while probing the ontology-currency check that later shipped as T4.1 — and worth
recording that `EFO_0001360` is obsolete too, so replacing these by memory rather than by lookup would
have substituted one retired term for another.

**Fixed: a located-but-unusable ClinVar cache no longer crashes `enrich()`.** A cache directory holding
parquet from another tool (or an older builder) made the DuckDB query raise and killed the whole
enrichment, even when the Ensembl cache had the answer. It now degrades to a miss with a warning, like
every other link. This also made a pre-existing test only pass depending on cross-file ordering.

**Corrections to the plan, made under probing rather than assumed.** (i) The live `gnomad_constraint`
API field serves **v2.1.1** constraint, not v4.1 — same gene, same MANE transcript, different numbers —
so the two routes are labelled as the different datasets they are, and the planned "the routes agree"
test asserts the difference instead. (ii) Indel normalization needs no local `seqrepo`/`pysam`: core
`ga4gh.vrs` over the seqrepo REST proxy does it in 14 pure-Python packages, so complete allele identity
is a **core** enricher capability rather than a `[dev]` extra, and `--offline` is the only thing that
degrades it. (iii) The VRS allele serialization embeds the location's *digest*, not its content — the
plan's stated mechanism was wrong even though its conclusion held; the shape was settled against
recorded gnomAD ids. (iv) Indels keep the coordinate key rather than an enricher-minted VA, because
re-keying from an optional network call would make `artifact.digest` depend on whether that call
succeeded.

**Fixtures are recorded, not fabricated** — `assets/gnomad_v4.1_variant_payload.json`,
`gnomad_gene_constraint_payload.json`, `gnomad_v4.1_constraint_slice.tsv`. The quirks under test (a
`"Multiple variants found"` error beside valid data, `XX`/`XY` listed twice, two `mane_select=true` rows
per gene) are ones a hand-written fixture would have omitted, letting the naive implementations pass.

## 2026-07-30 — `variant_key` carries the alt (distinct alleles at one locus no longer collide)

Second finding from the ClinVar dogfood (`reference_examples/pathogenic_clinvar/`): with the
allele-aware back-fill in place, the compiler's reverse round-trip *still* wasn't a fixpoint for
`resolution_signature`, because `variant_key = chrom:start:ref` **excluded `alt`** — two distinct
alleles at one locus (the coordinate-only insertion `11:5226762 C>CAAAG` and the expanded `rs33979901`
locus `11:5226762 C>CA`) collapsed onto one key, and the decompiler couldn't tell them apart.

- **`base.derive_variant_key` gains an optional `alts`.** The coordinate identity is now
  `chrom:start:ref:alts` (alts normalized/sorted) **when an alt is present**; rsid keys, position-only
  keys (no alt), and the position-level *matching* helpers (studies, verify, reverse-lookup,
  haplotypes) are unchanged — a study still matches a variant at `chrom:start:ref` regardless of allele.
- Passed at the identity-mint sites only: `VariantRow._freeze_variant_key` and the three one-to-many
  expansion re-key points (compiler `resolution.py`, enricher `resolver.py`, reverse writer).
- Result: `compile → reverse → compile` is now a **full fixpoint** (`artifact.digest`,
  `content_signature`, **and** `resolution_signature`). This changes `artifact.digest` for any module
  carrying alt-bearing *coordinate* variants (rsid-based modules are unaffected) — acceptable while 0.5
  is unpublished and `resolution.csv`/the digest are not yet frozen. `StudyRow`/`PharmVariantRow` keep
  their position/rsid-level keys by design.

## 2026-07-30 — enricher: allele-aware reverse back-fill + ambiguity marking

Surfaced by dogfooding the ClinVar module (see `reference_examples/pathogenic_clinvar/`): the reverse
(position→rsid) back-fill for coordinate-only variants was **allele-blind** — it matched
`(chrom,start,ref)` and could attach a co-located *different-allele* rsID (an un-rs'd insertion
inheriting the SNV's rsid), which also made the compiler's reverse round-trip drift on
`resolution_signature`.

- **Allele-aware reverse lookup.** `resolver.lookup_loci` / `clinvar.lookup_loci` now match the exact
  allele `(chrom,start,ref,alt)` and return *all* candidate rsIDs (shared `_lookup_rsid_candidates`,
  one implementation for both tables). `enrich()` passes the authored `alt` through.
- **Don't-guess + mark ambiguity.** A coordinate-only variant with no allele-exact rsid stays
  `rsid=null`/`source=authored` (coordinate is the identity); with exactly one → resolved; with several
  for the *same allele* (a dbSNP merge) → `status="ambiguous"`, a deterministic `rsid` pick, and the
  full candidate list in the new provisional **`ResolutionRow.rsid_alternates`** column (provenance,
  excluded from `resolution_signature`).
- This removes the mis-attribution and makes `resolution_signature` a reverse fixpoint whenever
  `variant_key`s are distinct. A deeper residual remains and is parked: `variant_key = chrom:start:ref`
  excludes `alt`, so two alleles at one locus still share a key — carrying `alt` in the resolution key
  is the follow-up. `resolution.csv` is provisional in 0.5, so no released contract is affected.

## 2026-07-30 — enricher: ClinVar reference snapshot (builder + resolver link + publisher)

ClinVar becomes a second, complementary reference beside the Ensembl snapshot in `just-dna-enricher`.
**No schema change, no compiler change** — `ResolutionRow.source` is an open field, so `"clinvar"`
needs nothing new, and the compiler's consumption contract is untouched.

- **`clinvar_build`** (`[dev]`, guarded `polars`) — `build_snapshot(vcf, out_dir)` converts the NCBI
  ClinVar GRCh38 VCF into a per-chromosome parquet snapshot (`data/clinvar-chr{N}.parquet`, one row per
  ACGT ALT allele) + `release.json` provenance; `download_clinvar_vcf` streams the VCF with the core
  `httpx`. `clin_sig` is folded into `vocab.VALID_CLIN_SIG` by an explicit severity order, `clin_sig_raw`
  kept verbatim. The parquet is byte-reproducible across rebuilds.
- **`clinvar`** (core, `duckdb`) — `lookup_loci` mirroring `resolver.lookup_loci` exactly, so the
  enrich chain treats the two references identically. Reads only `chrom/start/ref/alt` (annotation
  columns stay out of `resolution.csv` — orthogonal axes, P5).
- **Chain wiring** — a ClinVar link between the Ensembl cache and live Ensembl, stamping
  `source="clinvar"`, filling only what the Ensembl cache missed. It sits **after** the Ensembl cache
  on purpose: `alts` is a resolution fact flowing into `artifact.digest`, so a both-caches variant keeps
  the Ensembl `alts`/`source="cache"` and **no already-compiled module's digest moves** (tested).
  `--offline` clamps to both local caches (zero egress); `--no-clinvar` disables the link.
- **Publisher** — `upload.py` gains `ensure_repo` (`create_repo(exist_ok=True)`, absent from the
  extracted `v1_port.publish`) and `publish_reference_snapshot`; module upload now routes through
  `ensure_repo` too, so create-or-update-then-upload is one pathway.
- **CLI** — `clinvar build`/`clinvar publish` sub-app; `enrich`/`enrich-and-compile` gain
  `--clinvar-cache` and `--clinvar/--no-clinvar`.
- **Doc fix:** `ResolutionRow.start` is documented as **1-based** (VCF POS convention; it always was —
  the coordinates are unchanged, only the docstring was wrong).

## 2026-07-28 — enricher `[dev]`: HF module upload extracted from just-dna-lite

- **`just_dna_enricher.upload`** — publisher surface for pushing a compiled module
  (`weights`/`annotations`/`studies.parquet` + `manifest.json` + optional logo) to a HuggingFace
  dataset collection (`data/<name>/`). Plan + upload APIs, with a lazy `huggingface_hub` import.
  Extracted from `just_dna_pipelines.v1_port.publish` (just-dna-lite Gen-I recreation/publish path).
- **CLI:** `just-dna-enricher upload <module_dir> [--repo] [--name] [--message] [--dry-run]`.
- **`just-dna-enricher[dev]`** optional extra (+ matching `dependency-groups.dev`) marks the
  publisher/test install path; snapshot *download* stays a core enrich dep, upload is the
  author/publisher half of the same HF surface.
- **Consumer note (just-dna-lite):** `v1_port.publish` still carries a local copy (pipelines is
  pinned to format/compiler `<0.4` and cannot import enricher 0.5 yet). Docstring points here as
  the canonical home; switch to a thin modules.yaml-aware re-export of
  `just_dna_enricher.upload` when pipelines adopts the enricher tier (`just-dna-enricher[dev]`).

## 2026-07-23 — 0.5.0 (in progress, `enricher-0.5`) — source-independent resolution table

The 0.5 rework begins: resolution moves from a *live-ish opaque reference the compiler queries* to a
*persisted, source-independent table the compiler is handed*, so the compiler owns no source
convention and becomes strictly inject-only. All fetching (cache download + live Ensembl) will live
in a new `just-dna-enricher` network tier that *produces* the table; this increment lands the
consumption side entirely inside the two existing packages — additive, digest-neutral, and green
(the compiler still never fetches; it is *more* inject-only, not less). See
`docs/PROPOSAL_0_5.md` and the approved plan. **Per-package references (added this pass):**
[SCHEMAS.md](SCHEMAS.md), [COMPILER.md](COMPILER.md), [ENRICHER.md](ENRICHER.md).

> **`resolution.csv` is provisional.** It is **new in unreleased 0.5** — no 0.4 module carries it — so
> the additive-within-a-major / digest-freeze obligations (Principles 3/8) have **not** engaged for it.
> Its shape (`ResolutionRow` columns, keying, the `status` vocabulary, how one-to-many expansion is
> encoded) may be **refactored wholesale** during 0.5 dev and is expected to take a few passes before
> it settles. The stable contract (`variant_key` identity, `artifact.digest`, `content_signature`) is
> unaffected by resolution's internal shape.

Shipped in this increment (schema + compiler; **no network added yet**):

- **`resolution.csv` — the injected fact table.** New `just_dna_format.resolution.ResolutionRow`
  (schema tier, shared by the three parties: compiler consumes, enricher will produce, a verify-only
  client can re-check). Keyed by the frozen `variant_key`; carries the resolved facts
  (`rsid/chrom/start/ref/alts/genome_build/locus_index`) and a segregated provenance triple
  (`source`/`status`/`fetched_at`). A one-to-many rsid is N rows sharing `variant_key` with distinct
  `locus_index`. `genome_build` is the RM15 forward hook (no more silent GRCh38). `status` is a closed
  vocabulary `{resolved, not_found, ambiguous}` (Principle 6); `not_found` is the resolution analogue
  of the binning `unresolved` sentinel.
- **Pure `resolve_from_table`** (`just_dna_compiler.resolution`, **no `duckdb` import**) reproduces the
  DuckDB resolver's fill / expand / verify semantics from the injected table. `compile_module`
  precedence (additive, P3): `resolution.csv` present → this pure path; else an injected
  `ensembl_cache` → the superseded DuckDB path; else skip-with-warning. **Digest parity is proven** —
  given the same facts, both paths emit byte-identical `weights.parquet` (the expansion order is
  pinned on `(locus_index, chrom, start, ref)`).
- **Two-layer hashing kept intact; the table hashed separately.** `content_signature` (authored-only)
  is untouched — verified it builds from its own explicit table list, never `_INPUT_FILES`. The table
  is **not** added to `_INPUT_FILES` (a raw-bytes hash would be unstable across the enricher/human/
  reverse producers); instead a new **`integrity.resolution_signature`** hashes only the fact columns
  (provenance excluded), so a human-filled and an Ensembl-filled table with identical facts hash
  equal. Reproducibility identity is the triple `(content_signature, resolution_signature,
  compiler_version) ⟹ artifact.digest` — offline from two small CSVs.
- **Manifest (`Compilation`, all optional, out of `artifact.digest`):** `resolution_mode`
  (policy: strict|best_effort), `fully_resolved` (outcome — orthogonal axis, P5), `resolution_signature`,
  `resolution_sources`. Together they tell a catalog a strict, fully-resolved module from a
  best-effort half-baked one.
- **Reverse emits `resolution.csv`.** `reverse_module(..., write_resolution=True)` reconstructs the
  resolved facts from the artifact, so `reverse → compile` reproduces the identical `artifact.digest`
  with **no network and no reference** — hardening Principle 7's round-trip from reference-dependent to
  self-contained (a coord-keyed row's resolved rsid, dropped from `variants.csv`, is restored here).
- **CLI:** `reverse --resolution/--no-resolution`; `compile` prints `resolution_mode`/`fully_resolved`/
  `resolution_signature`. **Tests +8** (schema `resolution_signature` stability; compiler digest-parity
  / offline round-trip; provenance/order-independence; `resolution.csv` absent from `manifest.inputs`
  with `content_signature` unchanged; strict-vs-best-effort via the table).

**`just-dna-enricher` — the new network tier (shipped this increment).** The only package allowed to
fetch; it *produces* `resolution.csv`, and the arrow points inward (`enricher → compiler → format`) so
`httpx`/`huggingface-hub` never enter the compile path. `enrich(spec_dir, mode, offline, ...)` runs a
first-hit-wins chain — existing/human row (authoritative) → local cache (offline; reuses the
compiler's new public `resolver.lookup_loci`) → HF snapshot download (footer-checked, atomic, inherited
from lite byte-for-byte) → live Ensembl **V2 GraphQL → V1 REST fallback on 500/503**, `tenacity`
retrying transient errors — then writes `resolution.csv`. Modes: `best_effort` records misses as
`not_found`; `strict` fails unless every variant resolves; `--offline` clamps to the cache (zero
egress). Ensembl query shapes/endpoints are leeched from ensembl-mcp with `fastmcp`/`eliot` dropped
(stdlib logging), Python floor held at the compiler's `>=3.13`. CLI: `enrich`, `enrich-and-compile`.
Downstream (ensembl-mcp, lite/pipelines) adopt this as the single source of truth for resolution.
**Tests +6** (offline enrich→compile matches the DuckDB digest; `--offline` makes zero network calls;
V2 503 → V1 REST; tenacity retry; strict failure; one-to-many expansion). The two libs bumped
`0.4.0 → 0.5.0` so the workspace resolves the new member.

**Constitution amended (deliberately).** Goal 2, both dependency/network Non-goals, and Principle 2
now name the network tier: format + compiler become *more* strictly inject-only (own no source
convention, never fetch), and HuggingFace/httpx/tenacity are scoped to the enricher, never reaching
the dependency-light tiers a verify-only/compile-only client installs. Additive and scoped, not a
reversal — it completes the 0.4.1 *"cache authority leaves the compiler"* decoupling.

**The compiler is now duckdb-free (final decoupling, done).** `cache.py` and `resolver.py` (the cache
location + the whole DuckDB rsid↔coord resolver) **moved into `just-dna-enricher`** — `enricher/locations.py`
and `enricher/resolver.py`. The compiler dropped `duckdb`, `platformdirs`, and `python-dotenv`; its only
resolution is now the pure `resolve_from_table` (a `resolution.csv`). The `compile_module(ensembl_cache=…)`
**surface is kept** but deprecated: when used it emits a `DeprecationWarning` and routes to the enricher
via a guarded optional import (the compiler declares no dependency on the enricher and never fetches);
`None` now means *skip* (no env/platformdirs auto-discovery — the P2 tightening). The legacy path is
removed at **1.0**. This is legal because additive-within-a-major binds the wire/artifact *contract*, not
an internal compiler call. The resolver's own tests (`test_resolver_unit`/`test_resolver_integration`)
moved to `enricher/tests`; a `test_deprecated_ensembl_cache_path_warns` asserts the deprecation fires.

## 2026-07-15 — 0.4.0 (released) — audit pass: input-hardening tidy-ups

A fourth audit pass over the 0.4 branch. A full read confirmed the invariants hold (round-trip/
idempotency proven empirically across the frozen-key, expansion, and 0.4 generic-table paths); two
input-validation gaps remained, both fixed with regression tests. (The previously-suspected residual
poly-effect annotation loss was re-examined and found **non-real** — same `variant_key` implies one
locus implies one gene, and identical `conclusion`+`negatives` implies the same effect, so no
sensible case can differ in `gene`/`phenotype`/`category`; the genuine loss was already closed by the
variant-effect-pair keying below.)

- **Ragged CSV rows no longer slip past `extra="forbid"`.** A data row with more cells than the header
  had its surplus bucketed under `csv.DictReader`'s `None` key and silently dropped, so a shifted or
  extra column read as valid instead of being rejected like a typo'd header. `_load_csv_rows` now
  fails such a row with a line-located diagnosis (a typo'd *header* was already caught).
- **Namespace slug rule tightened.** `NAMESPACE_PATTERN` rejected a leading hyphen but accepted a
  trailing (`just-dna-`) or doubled (`a--b`) one; it now requires hyphens to *separate* alphanumeric
  segments (`^[a-z0-9]+(-[a-z0-9]+)*$`). No real namespace used those forms, so nothing valid is
  invalidated. **Tests +3.**

## 2026-07-15 — 0.4.0 (released) — frozen variant identity + one-to-many rsid expansion

A follow-up correctness pass on the 0.4 branch, resolving an identity-model flaw the branch review
surfaced (unpublished at the time, so the `artifact.digest` move was free). Root cause: `variant_key =
rsid-else-coord` treated an rsid and a coordinate as interchangeable identities, so the Ensembl
resolver — an enrichment — *mutated identity* (filling a coord→rsid flipped the derived key; a
one-to-many rsid had no faithful representation), silently breaking round-trip/idempotency
(Principle 7) and collapsing `annotations.parquet` dedup.

- **Frozen `variant_key` (minimal B+).** `VariantRow.variant_key` is now a stored column (via
  `base.derive_variant_key`), stamped once at load — rsid when it uniquely identifies the row, else
  the coordinate — and never re-derived; a `model_copy` does not re-run the validator, so resolution
  can fill a coord/rsid or expand a row without ever re-keying it. Materialized into
  `weights.parquet`; **compiler-managed** — excluded from `authoring_reference()` and never written
  back by `reverse_module`. `StudyRow`/`PharmVariantRow` keep the derived property (never resolved).
- **One-to-many rsid → row expansion.** A no-coord rsid that resolves to N>1 loci now expands into N
  coord-keyed rows (a paralog/SV signal a consumer can count — data-agnostic), instead of a
  non-deterministic "first-met" pick. `_lookup_positions_by_rsid` gained `ORDER BY id, chrom, start,
  ref` and returns all loci. Compiler behavior pinned by `compiler_version` (P4), GRCh38-only.
- **`reverse_module` restores authored shape** by reading the frozen key: an rsid-keyed row emits its
  rsid; a coord-keyed row (rsid was *resolved*, or position-only/expanded) emits **position-only**,
  dropping the resolved rsid — so field-only recompute + re-resolution reproduce the same key. No new
  CSV column; reverse→recompile is a digest fixed point (proven for the position-only→rsid and
  expansion shapes).
- **Bidirectional rsid↔coord consistency check** against the **injected** reference (inject-only, no
  network — Principle 2, same pattern as the resolver): a disagreement is a **warning** (may be a
  dbSNP merge/build difference), never fatal.
- **GRCh38-bound reality made explicit.** Resolution is skipped with a warning for a non-GRCh38
  `genome_build` (positions are not re-resolved cross-build — RM15) rather than corrupting
  coordinates against the wrong assembly; documented on `genome_build`, in COMPILER.md, and as
  ROADMAP RM15 + the "additivity has two axes" note.
- **Audit fixes.** Studies orphan check matches on a shared identifier (rsid *or* coord), not
  frozen-key equality; the position-consistency check compares only positioned rows (no
  mixed-authoring false positive); a malformed `provenance.json` / unsupported logo returns
  `CompilationResult(success=False)` instead of raising mid-compile; stale docs corrected
  (`COMPILER.md` reserved-namespace row, compiler `__init__` "three-parquet"); dead `or v` tails
  dropped. **Tests +20** (frozen-key freeze/backfill/reference-exclusion, resolver expansion +
  determinism + consistency + build-skip, compile→reverse→recompile flip-prevention + expansion
  idempotency, old-artifact fallback, orphan-on-coord, malformed-provenance).

## 2026-07-15 — 0.4.0 (released) — audit pass: poly-effect round-trip + reverse-writer dedup

A third correctness/tidiness pass over the 0.4 branch (unpublished at the time, so the `annotations.parquet`
schema move is free). Each fix ships with a regression test.

- **Poly-effect annotation no longer lost on round-trip (Principle 7).** `annotations.parquet` was
  deduplicated by `variant_key` alone, so a genuine poly-effect variant — one locus, two genotype rows
  with distinct `conclusion` **and** distinct `gene`/`phenotype`/`category` (as embryo-level / neural
  findings routinely are when `category` does not subsume the effect) — collapsed onto its first row,
  silently overwriting the second row's annotation on `reverse_module`. This was introduced with the
  `variant_key` column. The genuine identity is the **variant-effect pair**, so annotations now dedups
  on `(variant_key, conclusion, negatives)` and carries `conclusion`/`negatives` so the table is
  self-joinable back to `weights.parquet`; reverse probes the same key. `artifact.digest` moves once
  (annotations gained two columns) — expected while it was still pre-release; determinism + round-trip are held.
- **Coord-key format de-inlined to one source.** `chrom:start:ref` was hand-built in ~8 spots across
  the compiler and resolver despite `base.derive_variant_key` being the documented single source of
  truth; all now call the helper (the literal format lives only in `base.py`).
- **Reverse writers share one cell formatter.** The None→""/tri-state-bool/integer-float/list-join
  cell logic was implemented four ways (`_write_table_csv`, `_bool_cell`, and per-field ternaries in
  the variants/studies writers); consolidated into `_scalar_cell`/`_list_cell` used by all three.
- **Doc:** `reverse_module`'s manifest-only-metadata boundary (it reconstructs the compilable core
  from parquets; `genome_build`/`authorship`/`panel`/`provenance`/`logo` are not restored) is now
  stated explicitly as known/expected in COMPILER.md.

## 2026-07-15 — 0.4.0 (released) — branch-review fixes

A second correctness/consistency pass over the 0.4 branch before publish (unpublished at the time, so all
of the below is free to absorb). Each fix ships with a regression test.

- **PGx diplotypes with multiple drug annotations now compile.** The per-table duplicate-row key for
  `DiplotypeRow` omitted `drug`, so two legitimate rows for one haplotype pair differing only by drug
  (e.g. CYP2D6 `*1/*1` → codeine and → tramadol) were wrongly rejected as duplicates and the whole
  module failed to compile. The key now includes `drug` (matching its own comment and the intended
  authoring pattern). `HaplotypeRow`'s key likewise gained `ref`, so two position-only defining
  variants at the same locus differing only by reference allele no longer false-collide.
- **Reserved-namespace enforcement extended to the SNP core.** `VariantRow`/`StudyRow` now enforce
  `extra="forbid"` (via the shared `AuthoredModel` base below), matching the 0.4 composed tables — the
  ROADMAP tracker previously scoped rejection to "the 0.4 tables" only, so the core defaulted to
  `extra="ignore"` and a genuinely-reserved name (or a misspelled column like `directon`) was silently
  dropped rather than rejected. Now caught at validate time. A **hardening** in the spirit of
  CONSTITUTION P5 (reserve names so they survive the one-way door) + P3 (names permanent within a
  major) — the charter mandates reserve+audit, not runtime rejection, so this is a strengthening, not a
  charter-forced fix.
- **The reserved list now has build-time teeth, not just a published dictionary.** A `reject_reserved`
  before-validator (`vocab.py`), layered on `extra="forbid"` on every authored model, makes a reserved
  name fail with a *specific* diagnosis — what the name is reserved for (`vocab.RESERVED_NAME_REASONS`)
  and that a future release may claim it — while a random or misspelled column still gets the generic
  "extra inputs not permitted". So `reference_db` ≠ `xyzzy` at the point of failure, at author time and
  in the compile errors, for both a human and an authoring agent. Previously the frozenset drove no
  validation behavior at all (consulted only by `authoring_reference()`); now reserved vs. arbitrary is
  a real distinction the maintainer's list produces.
- **Reserved set corrected: `caller`/`caller_version` dropped, `reference_db` re-scoped.** The
  "provenance triple" (round-2 Q2) was a category error: `caller`/`caller_version`
  name which tool produced a *call* — a consumer-side measurement the module never holds — so there is
  no anticipated module axis to reserve, and barring the bare name is arbitrary (one non-feature among
  unbounded non-features; `extra="forbid"` already rejects them generically). They are removed from
  `RESERVED_NAMES_0_4`, which is now *only* genuine anticipated module axes: **`reference_db`** —
  re-scoped to its real module-side meaning, a hint naming which reference DB the app should join an
  annotation against (implicit Ensembl/ClinVar today; pinnable per module) — and **`callable_from`**
  (RM6). (The provenance-triple framing was dropped when the 0.4 proposal doc was retired.)
- **DRY: single `AuthoredModel` base** (`base.py`). The reserved-namespace guard (`extra="forbid"` +
  `reject_reserved`) and the field validators for the shared authored vocabulary (`rsid`,
  `trait_efo_id`, `direction`, `clin_sig`, `stat_significance`, `evidence_level`, finite-`effect_size`)
  were copy-pasted across `spec`/`binning`/`pgx`/`pgs` (~22 duplicated validators + 8 `model_config` +
  8 guards). They now live once on `AuthoredModel`; each row model inherits it and keeps only its
  field-specific rules (genotype/phase, star-allele strings, measure bounds, PGS ancestry, the mtDNA
  legacy-reference guard, identifier completeness). `check_fields=False` means a validator runs only
  for the fields a subclass actually declares, so per-field rules can no longer drift model-to-model.
- **Deterministic ref-less rsid resolution.** In the inject-a-reference path, a ref-less position over
  a multi-allelic dbSNP site was resolved to whichever row the DB returned first (no `ORDER BY`) — a
  latent idempotency risk, silent. It now resolves deterministically and emits an ambiguity warning
  telling the author to specify `ref` to disambiguate.
- **Doc/comment consistency:** the compiler module docstring now describes the composed multi-parquet
  artifact (not a fixed three-parquet one); the COMPILER.md coverage header reads "0.3 / 0.4 feature"
  and its dangling "Upgrade derivation" ROADMAP pointer is removed; the ROADMAP 0.5-scope table no
  longer describes its shipped ✅ rows as "still open"; `just-dna-agents` is listed among related repos
  in CLAUDE.md; and the RM11/RM12 provenance-column comments read "0.4 (from the 0.5 scope)".

## 2026-07-11 — 0.4.0 (released) — round-trip hardening + audit fixes

A correctness/robustness pass over the 0.4 work, before publish. Packages bumped **0.3.0 → 0.4.0**
(the `just-dna-format` / `just-dna-compiler` versions now match the milestone the code already
implements). **`schema_version` stays `"1.0"`.** Unpublished at the time, so the `artifact.digest` changes
below are free to absorb.

- **Structured per-version authorship (RM14; docs/USE_CASES.md §5a).** A new optional
  `authorship: list[Contribution]` on `module_spec.yaml` (and `ModuleManifest`), unbundling the flat
  `authors: list[str]` + free-form `curator` (which smuggled author-kind via the `"ai-module-creator"`
  default) into three orthogonal axes (P5): `who` (identity), `role` (closed vocab
  `created`/`edited`/`audited`/`reviewed`), and `kind` — an **open, multi-valued** tag set with a
  recommended seed: a human ladder of assurance `human` → `human_expert` → `human_certified`
  (medically/board-certified), or `ai` plus a scale tag `agent`/`team`/`swarm`. There is no `hybrid`
  tag — a joint contribution is two entries (a human and an ai), so the mix is always explicit. The
  motivating case: **AI and human error-spectra overlap but differ**, so a consumer (the network
  validator, a marketplace review queue, a human auditor) routes scrutiny by author-kind — the format
  carries the kind, the consumer picks the profile (north star). It is **manifest metadata, out of
  `artifact.digest`** (like `provenance`/`logs`/`panel`), so it is additive/digest-neutral even
  post-freeze and two versions with identical annotation content but different authorship keep one
  content identity. `authoring_reference()` surfaces the `Contribution` model + `author_role`
  vocabulary + `author_kind` seed automatically. Folding the flat `authors`/`curator` in is a
  1.0-cleanup item.
- **Provenance columns on `StudyRow` (RM11/RM12; docs/USE_CASES.md §4a).** Three optional columns that
  let a *network-first* validator (RM13, a consumer — Principle 2 keeps fetching out of these libs)
  scrutinise a module without the format ever downloading:
  - **`doi`** — Digital Object Identifier, wider than `pmid` (covers preprints/books/datasets with no
    PubMed id); validated against the DOI grammar and kept verbatim.
  - **`provenance_quote`** / **`provenance_regex`** — a keyword phrase and/or regex locating a study's
    claim in the cited article's fulltext, so a validator can confirm fulltext-contains yes/no. The
    regex is a Principle-1 *declarative pattern grammar* (data, not code): compiled at author time for
    a sanity check, matched consumer-side by a linear-time/ReDoS-safe engine. The provenance analogue
    of `source_field`.
  All optional → additive/monotonic (P3/P8); materialized into `studies.parquet` with lossless
  round-trip (P7). The mandatory-`pmid` → doi-first relaxation remains a 1.0-cleanup item (a required
  field can't be demoted in-major). `authoring_reference()` picks the columns up automatically.

- **Round-trip fidelity fixes (CONSTITUTION Principle 7).** Four shapes silently round-tripped wrong
  — the happy path (rsid-keyed, uniform priority, no explicit-`False` booleans) stayed green, so the
  invariant was only nominally tested:
  - **Position-only study rows** (`rsid` null, `chrom`/`start`/`ref` set) were dropped on compile and
    made *recompile fail*; `studies.parquet` now carries the position columns.
  - **Position-only variant annotations** (gene/phenotype/category) were lost because the reverse
    lookup keyed on the null `rsid`; `annotations.parquet` now carries an explicit `variant_key`.
  - **`priority`** was fabricated on reverse (an unset row inherited the mode as an inferred default,
    turning `['high', null]` into `['high', 'high']`); it is now written verbatim.
  - **ClinVar booleans** (`clinvar`/`pathogenic`/`benign`) collapsed an authored `False` to `None`;
    they are now materialized tri-state (nullable), matching the 0.4 axes.
- **Resolver fix.** A position-only-without-`ref` variant never resolved its rsid even on an Ensembl
  hit (the result was keyed by the DB ref, the lookup by `chrom:start:None`) — keys now reconcile.
- **Input hardening.** `start` positions are `ge=0` (a negative position is a clean validation error,
  not a polars `UInt32` overflow); `weight`/`effect_size`/measure bounds/`activity_value`/
  `match_rate_floor` reject non-finite floats (`NaN`/`inf`) that broke round-trip equality.
- **Tests (+20).** New round-trip regressions for every shape above; resolver unit tests over a
  **synthetic** parquet cache (the resolver + cache were previously covered only by
  integration-gated tests that skip in CI); `aggregate_provenance`, continuous-fraction coverage-gap,
  and several untriggered validator/error branches.
- **Docs reconciled with shipped code.** ROADMAP no longer frames 0.4 as unbuilt / PGS as note-only /
  a `VariantRow.copy_number` field that was rejected; READMEs describe composed modules (not a fixed
  three-parquet artifact) and the full dependency lists; the CONSTITUTION dependency-tier goal and
  `CLAUDE.md` acknowledge `cryptography` alongside `pydantic`.

## 2026-07-10 — 0.4 quantitative tables + composed modules

Additive 0.4 schema shapes (design frozen through the 0.4 proposal + consumer round-2) with full
compiler materialization.
**`schema_version` stays `"1.0"`** — every 0.1–0.3 module keeps validating; all new tables/columns
are optional.

- **The measure→phenotype binning primitive** (`just_dna_format.binning`): one shared column
  vocabulary (`measure_kind`, inclusive `[measure_min, measure_max]`, `direction`/`clin_sig`/
  `trait_efo_id`, `conclusion`, mandatory `unresolved` sentinel, declarative `source_field` pointer)
  across per-quantity tables — `activity_phenotype.csv`, `copynumbers.csv` (+ optional
  `modifier_gene`/`modifier_cn`), `repeat_alleles.csv`, `heteroplasmy.csv` (tissue + legacy-`NC_001807`
  reference guard). There is **no `copy_number` column** — a sharp value is `measure_min == measure_max`.
- **PGx star-alleles** (`just_dna_format.pgx`): `haplotypes.csv` (variant↔allele junction),
  `allele_function.csv` (star-string verbatim identity + optional `suballele`/CN/SV conveniences),
  `diplotypes.csv` (canonicalized pair fallback, + optional `drug`/`response`/`evidence_level`), and
  **PharmGKB** `pharm_variants.csv` (single-variant drug response, `evidence_level` 1A…4).
- **PGS** (`just_dna_format.pgs`): `pgs.csv` — a PGS-Catalog-ID manifest with the ancestry-validity
  one-way-door fields (`training_ancestry`, `training_cohort`, `match_rate_floor`, `research_tier`).
- **`VariantRow` general axes** (optional): `requires_callable`, `acmg_sf`, `actionability`
  (validated against `ACTIONABILITY_SEED`) — retired from the reserved namespace.
- **Compiler materialization (RM1 + RM2).** A generic model-driven materializer compiles all nine
  table kinds to parquet with lossless, idempotent round-trip. A module **composes from optional
  table kinds**: `variants.csv` is no longer mandatory — a PGx/PharmGKB/PRS-only module compiles and
  reverses without an empty `variants.csv`; `studies.csv` is required iff `variants.csv` is present.
- **Table-level coherence is enforced at compile time.** `validate_bins` now runs inside
  `validate_spec`: **overlapping resolved bins are a compile error** (a measurement would select two
  phenotypes), interior coverage gaps a warning, and more than one `unresolved` sentinel per key
  group an error. Duplicate rows (diplotype pair, `pgs_id`, `(pharm variant, drug)`, allele-function
  allele, haplotype-defining variant) are errors — the 0.4 analog of the SNP core's duplicate check.
- **Drift-proof authoring reference** (`just_dna_format.reference.authoring_reference()` /
  `json_schemas()`, RM8) generated from the live models, plus a recommended `RECOMMENDED_COLORS`/
  `RECOMMENDED_ICONS` palette (RM9) — so MCP servers / agents render the current field set instead of
  a hand-maintained summary that drifts.
- **Shared vocabulary leaf** (`just_dna_format.vocab`): the orthogonal-axis vocabularies and
  identifier grammars moved out of `spec` into one dependency-light source of truth, re-exported from
  `spec` for backward compatibility.

## 2026-07-08 — just-dna-format 0.3.0 + just-dna-compiler 0.3.0

Additive schema + partial compiler coverage for the 0.3 columns. **`schema_version` stays `"1.0"`** —
every 0.1/0.2 module keeps validating; all new columns are optional. Design captured in
`docs/ROADMAP.md` (Planned for 0.3 / 0.4), invariants in `docs/CONSTITUTION.md`, worked drafts in
`docs/REFERENCE_EXAMPLES.md`, and the compiler coverage split in `docs/COMPILER.md`.

- **New optional columns.** `VariantRow`: `direction` (protective|risk|neutral|unknown),
  `stat_significance` (significant|suggestive|not_significant|unknown), `effect_size` +
  `effect_measure` (open vocab), `effect_allele`, `flags` (open list; reserved:
  conditional|phased|pleiotropic), `trait_efo_id` (EFO/MONDO CURIEs, matches just-prs), `clin_sig`
  (ClinVar/ACMG vocab). `StudyRow`: `stat_significance`, `effect_size`, `effect_measure`,
  `trait_efo_id`.
- **Genotype widened** to accept a single allele (hemizygous X/Y, homoplasmic MT) and a phased `A|G`
  (order-preserved), alongside the existing sorted unphased `A/G`.
- **Compiler — validator complete; derivations, boolean sync, and phase round-trip now ship** (see
  `docs/COMPILER.md`). New columns materialize into `weights.parquet`/`studies.parquet`; non-reserved
  `flags` surface as INFO via the new `ValidationResult.info`; warnings for a two-allele `MT` **or
  `Y`** genotype (X excluded — it is diploid in XX) and a `direction`/`weight` sign mismatch.
- **Upgrade derivation shipped** (`just_dna_format.derive`, `pydantic`-only leaf module). `state`(+
  `weight`) → `direction`/`stat_significance` and the ClinVar booleans ↔ `clin_sig`, exposed as
  non-mutating `VariantRow.effective_*` accessors plus a materializing `VariantRow.upgraded()` and a
  `needs_upgrade` flag — the derivation the marketplace `revalidate`/`needs_upgrade` drift flow
  consumes. `state` and the booleans **stay required/authoritative** (CONSTITUTION Principle 8 — a
  required field is never demoted inside a major); the new axes are optional with these fallbacks.
- **Lossless, idempotent round-trip** (CONSTITUTION Principle 7, now a durable invariant): a `phased`
  bit in `weights.parquet` preserves `A|G` vs sorted `A/G` through `reverse_module` → recompile, and
  compiling the same spec twice yields the same digest. Only *new computed stats* and all of 0.4
  (diplotype/copy-number/PGx star-alleles) remain out of scope.
- **Digest note:** the parquet schema now carries the 0.3 columns + the `phased` bit, so a re-compile
  changes `artifact.digest` for every module (expected on a compiler-version bump; reproducibility
  pinned by `compiler_version`; 0.3 was unpublished at the time, so the change was still free to absorb).
- **Docs:** new root `CLAUDE.md` makes `docs/CONSTITUTION.md` the mandatory first read (discoverability
  gap — the charter was only linked from README/ROADMAP, with no agent entry-point). CONSTITUTION gains
  Principle 7 (round-trip/idempotency) and Principle 8 (requiredness compatibility).
- Tests: `compiler/tests/test_v03.py` (30) + `test_v03_roundtrip.py` (6) + `schema/tests/test_derive.py`
  (13); suite 153 passed / 5 skipped.

## 2026-07-07 — just-dna-format 0.2.0 + just-dna-compiler 0.2.0

First contract release since 0.1.0. **Every change is additive and backwards-compatible**: the
`manifest_version`/`schema_version` stay `"1.0"`, and every 0.1.0 module keeps compiling and
verifying byte-for-byte unchanged (optional fields are absent, optional files never invalidate).
Consumed by just-dna-marketplace 0.5.0.

- **Structured provenance (ROADMAP #1).** New `Provenance` summary on the manifest + `ProvenanceItem`
  / `ProvenanceDoc` models. The compiler auto-discovers `spec_dir/provenance.json` (per-variant
  rationale/verdict/confidence/human-review items), ships + hashes it like a log (kept **out of
  `artifact.digest`**), and records the lean summary (`generator`, `model`, `agent_version`,
  `item_count`, `sha256`) so a catalog can flag "AI-authored · rationale available" without inlining
  text. `verify_manifest(check_provenance=True)` re-hashes it when present.
- **Ed25519 signing (ROADMAP #2 / SPEC §5).** New optional `Signature` block on the manifest, a
  `signing` module (`sign_digest`, `generate_private_key_pem`, `public_key_b64_from_pem`), and
  `integrity.verify_signature`. `verify_manifest(public_key=...)` enforces a pinned key. Signs the
  `artifact.digest` string. Adds a `cryptography` dependency to `just-dna-format`.
- **Cross-version log aggregation (ROADMAP #3).** New `aggregate` module: `aggregate_logs` /
  `aggregate_provenance` return the deduplicated union across a set of version manifests
  ("v3 provenance = v1+v2+v3").
- **ClinVar/quality stats (ROADMAP #5).** `Stats` gains `clinvar_count` / `pathogenic_count` /
  `benign_count`; `validate_spec` and the manifest now summarize the per-row ClinVar flags.
- **PMID validation (ROADMAP #6).** `StudyRow.pmid` now requires at least one extractable PubMed ID
  (bare digits or the legacy `[PMID: N]` / `PMID N; ...` forms) via a re-introduced `PMID_PATTERN` +
  `extract_pmids` helper. The string is kept **verbatim**; a dbSNP URL (no PMID token) is rejected.
  Audited against the Gen-I corpus (all digit-only) so nothing published is invalidated.
- **Gene-panel interface (ROADMAP #7) — interface only, no machinery.** New `GenePanelSpec`
  (`source`, `reference`, `reference_sha256`, `genes`, `significance`), optional on `ModuleSpecConfig`
  and mirrored on the manifest. The compiler records it **verbatim** and does not materialize
  variants from it; the app-level `gene_panel` adapter (just-dna-lite) can now declare its panel
  provenance structurally. Native compile-time materialization is a follow-up gated on a working
  ClinVar reference mixin.
- **Module logo + icon set.** `Display.icon_set` (`fomantic` | `awesome`) selects the no-logo
  fallback glyph's family. New optional `manifest.logo` (`FileEntry`): the compiler discovers
  `spec_dir/logo.{png,jpg,jpeg}`, ships + hashes it, **out of `artifact.digest`** (so a logo swap is
  a PATCH, not a new content identity). `verify_manifest(check_logo=True)` re-hashes when present.
- **`negatives` field (ROADMAP Obs #5).** Optional free-text `VariantRow.negatives` (adverse /
  antagonistic-pleiotropy counterpart to `conclusion`), carried into `weights.parquet` and the
  reverse round-trip.
- **Docs.** `ValidationResult.stats` now documents its de-facto key contract (ROADMAP Obs #1). Item 4
  (resolver provisioning) is unchanged: strictly inject-only, no network.

## 2026-07-07 — just-dna-lite: longevitymap full parity + gene-panel reference implementation

Consumer-side only; no changes to the published packages. Two Gen-I parity advances in just-dna-lite,
flagged here so `-marketplace`/`-agents` see them:

- **longevitymap reached 528/528 rsid parity** (was 518/528). The gap was not Ensembl coverage but a
  genotype-reconstruction bug: heterozygous genotypes were built by concatenating the Ensembl `ref` +
  `alt` columns, and `alt` is a `|`-joined multiallelic list. The fix pairs the module's curated
  effect allele with its single complement and parses two-base `spec` alleles directly. No format API
  change; still compiles under the 0.1.0 contract.
- **Gene-panel reference implementation** for `cardio`/`cancer` (`just_dna_pipelines.v1_port.clinvar`
  + a `gene_panel` adapter): enumerates ClinVar pathogenic/likely-pathogenic variants in the panel's
  gene list into risk-state VariantRows (het + hom-alt), `weight=None`, grounded to the ClinVar
  resource paper (PMID 29165669). Kept within the 0.1.0 contract (multi-base ACGT alleles are legal;
  structural >50 bp and symbolic alleles are dropped). This is the intended upstream reference for a
  native `GenePanelSpec` — see **ROADMAP item 7** (added the same day, with items 8/9 for the APOE
  diplotype and PharmGKB shapes). `pathogenic`/`lnewco`/`drugs` remain deferred.

## 2026-07-06 — just-dna-lite ported the Generation-I OakVar modules onto the DSL

Consumer-side only; no changes to the published packages. just-dna-lite added
`just_dna_pipelines.v1_port` (CLI `pipelines v1-port`), which downloads the Generation-I `just_*`
OakVar postaggregator modules from the `dna-seq` GitHub org, converts their curated SQLite into the
authored DSL (`module_spec.yaml` + `variants.csv` + `studies.csv`), validates and compiles them via
`validate_spec`/`compile_module`, and writes standalone modules to `data/interim/v1_port/`.

- **Curated weights are carried verbatim**; `state` is taken from the source where present and
  otherwise from the weight's sign (reproducing the v1 reporter's `get_color(weight)` behavior).
- **All emitted `pmid` values are digit-only** — see ROADMAP.md → Observations #4 for the PMID audit
  this produced (input to planned item 6; the Gen-I corpus would not be rejected by a bare-digit
  `PMID_PATTERN`).
- Five modules (coronary, thrombophilia, lipidmetabolism, vo2max, longevitymap) compile; the
  reproduced coronary/vo2max/lipidmetabolism rsid sets match the published HF artifacts exactly and
  longevitymap matches 518/528. `superhuman` (URL-only references → no PMIDs) and the non-variant
  modules (cardio/cancer/pathogenic gene panels, drugs/PharmGKB, lnewco APOE diplotype) are
  documented as gaps, not ported. No `just-dna-format` API was exercised beyond the 0.1.0 contract.

## 2026-07-06 — just-dna-pipelines repointed at the published libs

Consumer-side integration in `just-dna-lite/just-dna-pipelines`. No changes to the published
`just-dna-format` / `just-dna-compiler` packages themselves; this entry documents how a consumer
adopted them and the contract facts that surfaced.

### Added
- `just-dna-pipelines` now depends on `just-dna-format>=0.1.0` and `just-dna-compiler>=0.1.0`
  (`uv add`).
- `.json` added to `module_registry._SPEC_SUFFIXES`, so a compiled `manifest.json` is copied
  alongside the parquets on register/install (was previously dropped).

### Changed
- `just_dna_pipelines.module_compiler` is now a **compatibility shim layer** over the libs; the
  duplicated in-repo schema + transform were deleted:
  - `module_compiler/models.py` → re-exports `just_dna_format.spec` (DSL models + constants) and
    `just_dna_compiler.models` (`ValidationResult`, `CompilationResult`).
  - `module_compiler/compiler.py` → re-exports `validate_spec` / `compile_module` /
    `reverse_module` from `just_dna_compiler.compiler`.
  - `module_compiler/resolver.py` → keeps the pipelines-only `ensure_resolver_db` provisioning and
    a `resolve_variants` wrapper that provisions then delegates to `just_dna_compiler.resolver`.
  - `module_compiler/__init__.py`, `cli.py` unchanged in surface (names still resolve via shims).
- Kept pipelines tests were adapted to the libs' current `validate_spec` stats keys — see
  Contract notes below. Test **coverage** is unchanged; only expected key names changed.
- CLI `pipelines module compile` help text updated: it no longer claims to auto-download the
  Ensembl cache from HuggingFace (the lib is inject-only).

### Behavior change (downstream)
- Ensembl resolution is now **inject-only at the library boundary**: `just_dna_compiler` never
  downloads a reference. Provisioning stays in just-dna-pipelines:
  - `register_custom_module` **auto-provisions** — when `resolve_with_ensembl` is on and no cache
    is passed, it calls `ensure_resolver_db()` (idempotent: cheap when the cache exists, builds/
    downloads from HuggingFace only when absent) and injects the result. Failure degrades to
    inject-only (resolution skipped with a warning). This preserves the pre-extraction convenience.
  - Direct callers of `just_dna_pipelines.module_compiler.resolver.resolve_variants` also
    auto-provision via `ensure_resolver_db`.
  - `compile_module` itself (the library re-export) remains inject-only: called directly with no
    cache and none present, it skips resolution with a warning rather than downloading. The
    `pipelines module compile` CLI relies on an already-provisioned cache (help text updated).
  - Integration tests pass because their `ensembl_db_path` fixture provisions the default cache
    the lib then reads.

### Contract notes for other consumers (-marketplace, -agents)
- **`ValidationResult.stats` keys renamed** vs. the pre-extraction schema:
  `unique_genes → gene_count`, `study_rows → study_count`, `unique_variants → variant_count`;
  `genes` / `categories` are sorted lists with `None` filtered out. `unique_rsids` and
  `module_name` are unchanged.
- **`VALID_PRIORITIES` and `PMID_PATTERN` are not in `just_dna_format.spec`** — they were dead code
  in the original schema (no validator referenced them / the PMID validator was commented out). The
  live study rule remains "pmid must be non-empty".

## 2026-07-06 — just-dna-format 0.1.0 + just-dna-compiler 0.1.0 (initial workspace release)

Restructured the format into a uv workspace publishing the two packages, and extracted the schema +
transform out of just-dna-pipelines so they are shared, not duplicated. `manifest_version` /
`schema_version` established at `"1.0"`.

- **`just-dna-format`** (schema; `pydantic` + stdlib at this point): `spec` (the authored DSL —
  `ModuleSpecConfig`, `VariantRow`, `StudyRow`, `ModuleInfo` extending `Display`); `manifest`
  (`ModuleManifest` + `Identity` / `Display` / `Stats` / `Compilation` / `FileEntry` / `Artifact`);
  `integrity` (`sha256_file`, the `artifact_digest` Merkle root, `build_artifact`, `verify_manifest`);
  `identity` (name/namespace rules, SemVer `Version` / `parse_version`, `canonical_id`, legacy
  `vN → N.0.0`).
- **`just-dna-compiler`** (transform; + polars / duckdb / pyyaml / platformdirs / python-dotenv):
  `validate_spec`, `compile_module` (emits `manifest.json` with input + artifact hashes and the
  digest, plus `genes` / `categories` stats), `reverse_module`, and a pipelines-free, **inject-only**
  Ensembl `resolver` (never downloads).
- **Provenance logs.** Optional per-version hashed log files (`ModuleManifest.logs`) — a top-level
  `*.log` plus a `logs/` per-role subtree — copied into the module dir, hashed like `inputs`, kept
  **out of `artifact.digest`**. Absent logs never invalidate; `verify_manifest(check_logs=True)`.
- **Ensembl cache reuse.** `just_dna_compiler.cache` mirrors just-dna-lite's on-disk layout
  (`$JUST_DNA_PIPELINES_CACHE_DIR/ensembl_variations/…`, `.env`-driven); it locates a reference but
  never downloads one.
- Tests: 82 passing (schema + compiler), incl. regression tests ported from just-dna-lite; the
  Ensembl resolver tests are `@integration` (skip without a cache).
