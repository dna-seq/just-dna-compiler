# Changelog

Shared change log for the just-dna module format/compiler ecosystem. Because
`just-dna-format` + `just-dna-compiler` are consumed by **just-dna-pipelines**,
**just-dna-marketplace**, and **just-dna-agents**, cross-repo integration changes are recorded
here so parallel work in the other repos isn't surprised. Newest first.

**A version heading names the release a change will ship in, not a development batch.** Entries dated
2026-08-03 carried a `0.5.1:` label for a while; at the time nothing 0.5.x had been published, all three
packages sat at `0.5.0`, and that work therefore shipped **as 0.5.0** — the label was relabelled to
match. Keep it that way: a number here should answer "which published version introduced this", and a
batch inside an unpublished release is not a version.

**0.5.0 is published** — tagged `v0.5.0` and released to PyPI on 2026-08-07 (`just-dna-format`,
`just-dna-compiler`, and `just-dna-enricher`, the last being that package's first release). Everything
below dated 2026-08-07 or earlier is in it. The next heading is therefore a real new number: additive
work — including a **new optional column or table** — is **0.6.0**, while **removing** a column,
**promoting** one to required, **retyping** one, or changing what an identity key *means* is **1.0**.
That is Principle 3 as amended on 2026-08-11; the earlier "anything that moves `artifact.digest` is
1.0" rested on a premise that expired when `content_signature` took over content identity in 0.4.1.
See [ROADMAP § 0.6](ROADMAP.md#06--what-a-minor-permits).

**That rule is about the schema surface, and the three packages version independently — so
`just-dna-enricher` can take a patch.** "Additive work is 0.6.0" sorts changes by what they do to a
compiled module's identity, which is a *format/compiler* question. Work confined to the network tier
touches no parquet, no model and no manifest field, so it can ship as an enricher patch release while
format and compiler stay where they are. The first of those is **`just-dna-enricher` 0.5.1**, whose
content is [RM38](history/ROADMAP_HISTORY_PRE_0_6.md#rm38--a-cache-for-every-gated-source-the-hosted-enricher) — a cache for the
licence-gated sources, so a hosted enricher stops fetching them live per request. This does **not**
reopen the paragraph above: that one is about labelling a batch inside an *unpublished* release, which
0.5.1 is not — 0.5.0 shipped, so 0.5.1 is a real next number rather than a name for work in progress.
**0.5.2 follows the same rule** and stretches it by one package: its ClinVar-drafting, query-shape and
cache-location work is enricher-only, and the one compiler change (a warning when
`resolve_with_ensembl=False` discards an injected `resolution.csv`) writes no parquet and moves no
signature, so `just-dna-compiler` took the patch alongside while `just-dna-format` stayed at 0.5.0.

## 2026-09-02 (latest) — two records that contradicted themselves, and a header a draft could not write into

**`just-dna-enricher` + `just-dna-compiler`, no schema change.** Three defects, each found by a probe
that was measuring something else, plus the probe round behind RM170.

- **`release.json` declared the accepted basis while recording the wider one.** RM169 added
  `--submitted` and every derived field moved with it — `status_basis`, `status_counts`,
  `vcf_evidence`, the per-row `evidence_status` — but `notice` stayed a literal, so a snapshot built
  on the wider basis published *"every row of which is status 'accepted'"* beside
  `status_basis: accepted+submitted` and 642 submitted rows. **A consumer quoting the notice was
  quoting a false sentence.** Derived from the basis now, with the counts it read.
- **A partial draft into a header that predates a column crashed.** `append_partial_rows` re-rendered
  the existing rows against the model's **full** field list and then wrote them under the file's
  narrower header, so `csv.DictWriter` raised a bare `ValueError: dict contains fields not in
  fieldnames`. `draft-repeats` into the shipped `htt_repeat_expansion` example hit it on `pmid` and
  `measure_tiling`. The header now grows by exactly the columns the batch fills, settled before
  anything is rendered — the rule `append_rows` already had.
- **[CONTRADICTION_CORPORA](probes/CONTRADICTION_CORPORA.md)**, the RM170 probe: both corpora measured
  before either is designed against. **No refutation in CIViC that stands against a claim is
  accepted** — so that finding's subject count is 0 on the accepted basis and 3 on the wider one, and
  a hint that does not state the basis cannot be honest. Four adopted sources publish this shape,
  three already land it, and **STRchive's is dropped at parse**. Filed **RM174** out of it: a
  combination-genotype refutation reaches the parquet as two single-variant rows because the row
  builder stamps the variant's profile over the evidence item's.
- **Two probes landed, and each replaced the entry that asked for it.**
  [MITOMAP_STATUS](probes/MITOMAP_STATUS.md) (RM171): `status` is a **two-token grammar**, not 29 free
  strings — base × optional bracket covers 568 of 602 — and **both positions are documented**, the
  bracket explicitly as a **ClinGen mtDNA VCEP rating**. So mapping the bracket is a normalization, not
  a curation decision; but **120 of the 136 bracketed rows are already in the ClinVar chrMT snapshot,
  all as `reviewed_by_expert_panel`, 119 agreeing**, leaving 16 new calls. The base half must *not* be
  mapped: MITOMAP states it is not an assignment of pathogenicity. Also: the sibling `rtmutation` holds
  both variants of the repo's only mtDNA module, and `mmutation` holds neither.
  [rm170_kleene](probes/rm170_kleene.md) is RM170's design record.
- **RM174 rewritten on a phase measurement, and RM28 gains its first corpus entry.** EID 8721's own
  description reads *"heterozygous compound mutation"* — the two variants are **in trans**, and a
  haplotype is *cis*, so `HaplotypeRow` would assert the opposite of what the source observed. CIViC's
  profile grammar is boolean and counted: **209 multi-variant of 1,964 — `AND` 141, `OR` 72, `NOT` 1**,
  nested. Both of RM28's surviving arguments (economy in trans, open-world negation) appear there with
  instances. The stamp defect stays RM174's; the representation is RM28's and stays parked.
- **RM160's shape decided (unbuilt): read `SUBMITTED` at `enrich` time.** `civic build` /
  `civic reproduce` keep byte-reproducibility and the snapshot does not grow.
- **RM170 shipped: an authored direction beside a refutation the source published.** `Does Not
  Support` was already withheld rather than negated — but a variant CIViC *supports* and *also* rebuts
  still got a `risk` row drafted, and nothing then said the rebuttal existed. `contested_variants`
  cannot see it (a refutation enters no camp, so that counter is correctly 0 on every basis). Now
  `draft-panel --source civic` names the variants it wrote such a row for, and `enrich` folds in the
  new **`published_refutation`** check whenever a CIViC snapshot resolves, so a hand-authored module
  meets the same sign. Two finding codes — `refutation_beside_claim`, `refutation_without_claim` —
  because they are two sentences; they key the record's `detail` rather than joining the compiler's
  `VALID_WARNING_CODES`, which a compile restates as `verification_findings_recorded`. **Warns in both modes, escalates in neither, repairs nothing.**
  Consumers pinning `VerificationRecord.check` should add the member. The record names its
  `status_basis` on every run including the empty one: every such pair in CIViC rests on submitted
  content, so on the `accepted` basis the class is empty by construction.
- **RM173 closed, and RM175 opened: the PGx lane reads a retired filename.** The entry's premise was
  replaced twice in one day. First: `clinicalVariants.zip` is not a third source — **96.3% of its
  5,190 rows are already in the archive the lane reads**, and its `type` column is
  `Phenotype Category` with a different separator. Then the maintainer's investigation
  ([CLINPGX_ARCHIVES](probes/CLINPGX_ARCHIVES.md)) replaced the 13-month gap that finding ended on:
  the 15-column table was **renamed** to `summaryAnnotations.zip` when PharmGKB became ClinPGx on
  **2025-07-29**, and `clinicalAnnotations.zip` is a frozen S3 object last written 24 days before that
  post, on no downloads page, still answering 200 — **and, until the rebuild two bullets down, this
  lane's default**. So every
  `annotations.parquet` ever built here came out of the database as it stood 14 months ago.
  **RM175** is the rebuild: four member renames, one id column, no vocabulary or model change, but
  8 rows change `Level of Evidence` and every URL rehosts, so the digest moves. **A retired filename
  that still 200s is indistinguishable from a live one at the HTTP layer**, which is the durable
  lesson; and a no-JS fetch of any clinpgx.org page is the *Javascript Is Disabled!* shell, so it is
  no evidence about what the source lists.
- **RM175 shipped the same day: the PGx lane builds from `summaryAnnotations.zip` now, and refuses
  the retired archive by name.** The default URL, two member names and the id column moved
  (`summary_annotations.tsv`, `summary_ann_alleles.tsv`, `Summary Annotation ID`) with **no
  vocabulary member, no model field and no parquet column changed** — the other fourteen columns and
  `Phenotype Category`'s values are identical. **The guard is the item**: an archive carrying the old
  member names parses perfectly and yields a plausible fourteen-month-old parquet, so the builder
  reads the member names first and refuses the retired spelling with the rename, its date and the URL
  to use instead; a third arm answers for an archive that is neither. Both spellings live in one table
  the reader takes its names from, and the retired one is returned by nothing, so no path through the
  module can read a 2025 archive. **The data moved and the digest with it**: 16,087 → 16,117 snapshot
  rows over 5,190 annotations, 22 (annotation, genotype) keys gone and 52 new, 30 rows changing
  `evidence_level`, 120 `drugs`, and every shared row rehosting its `URL` — so a module drafted from
  this lane can see an evidence level move under it, which is the check working. The builder
  docstring's *"4,618 of 5,113"* is gone from all five live files, restated as a relationship rather
  than swapped for a fresh count. **Left unbuilt on purpose**: the three currency canaries the entry
  listed, each of which is its own design — nothing here would notice `summaryAnnotations.zip` itself
  going quiet.
- **MITOMAP's terms are read (RM171): CC BY 3.0**, commercial use and redistribution permitted,
  attribution required. Read from a Wayback capture because the live page is behind a Cloudflare
  interstitial; the CC BY-NC a search surfaces is the *article's* licence, not the database's.

## 2026-09-01 — the source-adoption round closes: regulator drug labels (RM166)

**`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member.** Last of the five items
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided, and with it **the whole 2026-09-01
source-adoption round has landed inside the uncut 0.7.0**: RM163, RM165, RM166, RM167 and RM168 built;
RM164 parked on a measured negative, spinning off RM171.

- **A `drugLabels.zip` builder beside `clinpgx_build`** — same cache, same payload-read `LICENSE.txt`,
  and **its own `release.json`** from its own `CREATED_*.txt`. ClinPGx's archives do not refresh in
  lockstep; `relationships.zip` was once a year newer than `clinicalAnnotations.zip`.
- **A regulator-label cross-check joining at two tiers.** Star-allele where the file supplies one,
  gene otherwise, and **the tier is part of the finding** — a gene-level agreement and an allele-level
  agreement are different claims and a consumer must be able to tell them apart.
- **It is five regulators**: FDA, Health Canada, EMA, Swissmedic, PMDA. The surface is named for the
  labels rather than for any agency, so adding a sixth is data rather than a rename.
- **A blank `Testing Level` is `unknown` and withholds** — about a third of the file states none, and
  reading that as `No Clinical PGx` would manufacture a negative regulatory claim.
- **New verification check `regulator_label_agreement`.** Consumers pinning `VerificationRecord.check`
  should add it; it warns in both modes and never escalates under `--strict`.
- **What did not ship, and closed instead:** the PGx lane gains no member outside its licence class by
  this route. ClinPGx is the same CC BY-SA + no-sale gate, and the FDA's own association table is 126
  rows of HTML with no stated terms. Diversifying that lane needs its own item, choosing candidates
  for their terms first.
- Noticed and filed rather than built: ClinPGx publishes at least twelve archives and this tier reads
  two of them.

## 2026-09-01 — the source-adoption round: literature coverage, and the tier that answered (RM167)

**`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member. Writes no authored row at all.**
Fourth of the five items [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided.

- **`just-dna-enricher litvar coverage` asks LitVar2 which papers name a module's alleles**, and
  records **which tier could answer**: allele-resolved, position-only, absent, or `unchecked`. The
  distinction is the point — APOE rs429358's position node carries 3,945 papers and its allele node
  328, so an answer that did not name its tier would understate that locus twelvefold.
- **It writes no row.** A PMID list per variant is not a table kind, so the pass reports and attests
  and changes nothing in the spec directory. That was the entry's pre-authorised outcome.
- **New verification check `literature_coverage`.** Consumers pinning `VerificationRecord.check`
  should add it.
- **The bound ships with it, in the lane's own documentation**: LitVar answers *which papers discuss
  an already-identified allele*, and does not answer *which allele a name meant*. Measured against the
  two CIViC legacy insertions, it returns no node for any of their four candidate alleles.
- **`clingen_allele.AlleleIdentity.unanchored` is now populated on a `resolved` result too.** It was
  computed and then discarded whenever the registry also served an rs-number, so a caller wanting the
  allele rather than an identity got nothing — every PALB2 indel read as incomparable. A consumer
  reading `unanchored` only under `outcome == "needs_anchor"` is unaffected.
- Terms: NCBI publishes a policy rather than a licence, so every gating axis is `None`. A module
  carrying LitVar-derived findings records unknown terms rather than permissive ones.

## 2026-09-01 — the source-adoption round: STRchive, checked and drafted by column (RM165)

**`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member. No authored column, no parquet
change, `just-dna-compiler` untouched.** Third of the five items
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided.

- **`repeat_alleles.csv` gains a source, split by column.** `just-dna-enricher check-repeat-bands`
  compares an authored band table against STRchive's and reports; `just-dna-enricher draft-repeats`
  drafts the identity half. New `STRCHIVE_TERMS` (MIT — the first candidate in this round with terms
  that are both established and permissive) and a `strchive` snapshot builder.
- **The bands are checked and never drafted, for a measured reason.** STRchive reproduces
  `htt_repeat_expansion`'s first two bands exactly, and gives FMR1 one `45–200` band where the module
  has `45–54` and `55–200` — losing 55, the premutation threshold. The finding names the missing
  boundary rather than reporting that two tables differ.
- **`pathogenic_max` is never written as `measure_max`.** A catalogue maximum is an observation, not a
  clinical bound; imported as one, an allele above it would match no bin at all and nothing would say
  so. It is reported as its own finding kind.
- **New verification check `repeat_band_agreement`.** Consumers pinning `VerificationRecord.check`
  should add it. It warns in both modes and never escalates under `--strict`.
- **The drafting provider writes no band column at any severity**, and a drafted row is gene, motif,
  trait and a placeholder conclusion — `RepeatAlleleRow` has no column for the coordinates,
  `locus_structure` or `ref_copies` the catalogue also publishes. That gap is RM65/RM87.
- Known and not fixed here: `just_dna_compiler.draft.append_partial_rows` crashes on any table whose
  header is narrower than its model, which reaches all four existing partial-row providers. Found
  while drafting into a real module, reproduced independently, filed rather than patched — this round
  changes nothing in `just-dna-compiler`.

## 2026-09-01 — the source-adoption round: the PGS Catalog becomes a registry (RM163)

**`just-dna-enricher`, plus two `VALID_VERIFICATION_CHECKS` members in `just-dna-format`. No authored
column, no parquet change, `just-dna-compiler` untouched.** Second of the five items
[PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided.

- **`check-identifiers` asks a fourth registry.** `pgs_id` was the one authored identifier in the
  format nothing checked, on the column `PgsRow` is keyed by. New `pgs.py` client; the roster derives
  from `DRAFTABLE` the same way the other three do.
- **The verdict is read off the response body, never the HTTP status.** The Catalog answers `200` with
  `{}` for a never-assigned accession *and* for a malformed one, so the status carries no existence
  information. A consumer relying on `raise_for_status` to mean "this id is real" would be wrong.
- **The absence message names the typo reading first.** Only about a third of the accession range is
  assigned, so an unrecognised id is overwhelmingly never-assigned rather than withdrawn — the
  opposite weighting to the dbSNP message, and stated for the measured reason.
- **Two new verification checks**, `pgs_accession_currency` and `pgs_metadata_agreement`. Consumers
  validating `VerificationRecord.check` against a pinned vocabulary should add both.
- **`PGS_TERMS` is a floor, not the terms.** Each score record carries its own `license`, and the
  values are not variations on one licence: most generic, some academic-research-use-only, some CC0.
  The per-score string overrides the constant in that score's `SourceRow`. **A module naming an
  academic-use-only score is now refused by the compile gate by name** — if you have such a module, it
  will stop compiling under a commercial `declared_use`, and that refusal is correct.
- **Drift is checked over `training_ancestry` and `training_cohort` only.** `match_rate_floor` and
  `research_tier` are author judgements the Catalog does not publish, so there is nothing to compare
  them against.
- **Currency comes from `/rest/info`**, added as `currency.default_probes`' second member, so
  `--verify-datasets` now covers this source.
- Known gap, recorded rather than fixed: a `pgs.csv` drift finding **cannot** be answered in
  `overrides.csv` — the overlay applies to derived tables and `pgs.csv` is authored.

## 2026-09-01 — the source-adoption round: MANE becomes a cache (RM168)

**`just-dna-enricher` only; no schema change, no new authored column, nothing in `just-dna-compiler`.**
First of the five items [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md) decided, all landing inside
the uncut 0.7.0.

- **`just-dna-enricher mane build` — MANE is a source now, not a sentence in a probe document.**
  `CIVIC_IDENTITY_PROTOCOL` § 3b pinned a numbering frame with a file "downloaded once and cited";
  it is now a cache with a location, a recorded release and a currency check, like every other
  reference table here. New: `MANE_TERMS`, `$JUST_DNA_MANE_CACHE` / `default_mane_cache_dir` /
  `resolve_mane_reference`, `mane_build.py`, a `mane` sub-app, a `cache status` row.
- **Three files, under 1.2 MB together.** The summary (19,437 rows), `changed_select_accessions` (120
  rows) and `protein_coding_genes_not_in_mane` (222 genes). The second is the currency check and ships
  in the same pass deliberately — a cache without the thing that notices it going stale is the defect
  the item was about.
- **`release.json` is copied from the source's own `README_versions.txt`**, so it carries the MANE
  version, the NCBI RefSeq annotation release *and* the Ensembl release — two of which appear in no
  filename.
- **`MANE_status` is a column and is never collapsed.** 74 of 19,437 rows are MANE Plus Clinical, and
  CDKN2A carries two rows with different CDS numbering. A consumer reading one row per gene would not
  see it.
- **`Update_Affects_CDS` is carried as a tri-state.** Yes on 74 of the 120 changed accessions: a MANE
  Select change that moves the CDS moves every `c.` and `p.` derived in that frame.
- **The negative roster keeps its reasons.** 222 genes over a seven-member vocabulary derived from the
  file, so "MANE has no answer for this gene" is distinguishable from "nobody asked" — and
  `pending MANE review` is neither.
- **Terms are `None`, not permissive.** NCBI publishes a policy rather than a licence, so every gating
  axis is unknown; there is no `--use` flag, because a gate whose every answer is a skip is a flag that
  does nothing. Only NCBI's side was read — nothing is asserted about EMBL-EBI's terms for the same
  tables.
- **Scope is a transcript-identity aid, not HGVS generation**, and the lane documents its own bound:
  MANE is the default, not the answer. It makes CDKN2A's problem visible and is silent on RUNX1's.
- Two `--help`-parsing tests that had been failing every PR run since 2026-08-30 are fixed: Typer
  renders through Rich, CI sets `FORCE_COLOR`, and a coloured flag is not one token.

## 2026-09-01 — CIViC: the identity in a variant's name, and the basis in its own VCF (RM159, RM169)

**`just-dna-enricher` only; no schema change, no new column, nothing in `just-dna-format` or
`just-dna-compiler`.**

- **`civic build` places 33 variants it used to drop.** CIViC states an identity in a variant's `name`
  for records whose identifier columns are empty — `N150fs (c.448delA)`, `IVS2+1G>A`, `D1709N` — and
  those identities now ship as `civic_identities.CIVIC_NAME_IDENTITIES` and are emitted with
  `identity_derivation="curated_name"`. Coverage over the dated `01-Aug-2026` release goes from
  **237/290 variants (81.7%) to 270/290 (93.1%)** and from 474/533 rows to **507/533**;
  `unresolvable_identity` falls from 59 rows to 26.
- **`identity_derivation` gains the member `curated_name`.** Additive, and deliberately not folded
  into `rsid`/`grch38_hgvs`: those mean "the source stated this in the column for it". A consumer
  filtering on the vocabulary should add the member; one that ignores it sees the rows as ordinary
  placed rows, which they are.
- **`release.json` gains `curated_identities`** — `applied` / `superseded` / `renamed` / `absent`,
  every member present, summing to the table. `superseded` means CIViC has since published an identity
  of its own and the curated row stood down; it is also a free currency signal.
- **`civic reproduce` now reads 57 coordinates against the GRCh38 reference instead of 24**, still
  0 mismatches. Every hand-read allele is confirmed at its stated position by an unrelated service.
- Unchanged: the build is still offline and byte-reproducible from the dated TSV pair, and
  `allele_registry_id` is still CIViC's verbatim cell — the CAIDs the resolutions went through are
  provenance on the shipped table, not the source's statement.
- The procedure behind the identities is `docs/probes/CIVIC_IDENTITY_PROTOCOL.md`; the per-variant
  evidence and the classes that did **not** resolve are `docs/probes/CIVIC_UNRESOLVED.md`.

**RM169 — `civic build --submitted` and `civic reproduce --submitted`.**

- **The unreviewed majority is now readable from the dated release.** CIViC publishes
  `<date>-civic_accepted_and_submitted.vcf` beside the three TSVs, so no API read and no
  reproducibility bargain are needed — RM160 was filed believing otherwise. Opt-in:
  **507 rows on 270 variants → 1,149 on 397**, rebuild still byte-identical, refget cross-check
  **57 → 129 coordinates with 0 mismatches**.
- **New parquet column `evidence_status`** — `accepted` / `submitted`, CIViC's own word, unconverted.
  Present on every row; on the accepted basis it is uniformly `accepted`.
- **`identity_derivation` gains `vcf_csq`.** `VariantSummaries.tsv` is accepted-only as well, so 112
  of the 127 new variants have no row in it; their identity comes from the VCF's `CSQ` block through
  the same parsers and the same published identifiers. The member names the *file*, not the route.
  A consumer filtering on the vocabulary should add it.
- **`release.json` gains `status_basis`, `status_counts`, `vcf_evidence` and `unjoinable_submitted`.**
  `status_basis` is the field to read before comparing any count here with a count from anywhere else.
- Unchanged: the TSV pair is still primary (the VCF cannot carry a variant with no GRCh37 position,
  which is exactly the class RM159 resolved by name), and nothing is placed from the VCF's own GRCh37
  coordinate.

## 2026-08-28 — 0.7.0: the items PROPOSAL_0_7 decided

**A MINOR, being built; the number is decided and not yet cut.** Every item in this batch is additive
under Principles 3 and 8, and a new optional column is what sizes a release. The heading names `0.7.0`
because the proposal decided it per item, so unlike the 2026-08-24 batch below — which is also an
uncut minor and deliberately names no number — there is a version to write down here. The three
`pyproject.toml` files were bumped to `0.7.0` on 2026-08-31 and **the tag is not cut**, so work still
lands inside this number; the 2026-08-24 batch ships inside it too. Each entry below names the
packages it actually touched.

**The twelve entries dated 2026-08-31 are a batch of their own and are worth reading as one.** They are
the roadmap items that stood open against this release — RM103, RM108, RM110, RM117, RM136, RM137 and
RM138 — plus RM146 and RM150 from the same day's consumer reports, and RM151, which was filed and
built the same day as RM117's other half, and RM152, a consumer measurement that arrived carrying
no release class and acquired one when its probe was finally run, and RM154, which arrived from a
consumer report after the rest were built; all taken in one pass so 0.7 cuts with its own backlog
cleared rather than carrying it. Eleven are built; **RM138 is closed with its numbers measured and no
code changed**. **The items dated 2026-09-01 are deliberately outside that count** — RM155 arrived
from a consumer the next morning, RM156, RM157 and RM158 from sweeping its shape across the
tier, and RM161 from the pre-build gate run those four preceded; all five ship inside the same uncut
0.7.0. The batch stays the thing it describes rather than growing a member
whenever another item lands before the tag: the count is of the 2026-08-31 round, and the rule for a
later item is to date it and leave the number alone. Two things a reader should take from them together: `carried` costs
1.06× gzipped rather than the 1.84× raw the item was filed about, so **serve manifests compressed**;
and two derived values change — `gene_metrics.constraint_flags` and
`gene_validity.classifications` — which are **corrections**, so a moved signature there is the fix
arriving rather than drift.

- **RM161 — a release record's two halves are written at different times, and the second left the
  first behind.** *(`just-dna-format`; **additive** — two names into an existing list and one new test.
  No column, no vocabulary member, no signature moves.)* The pre-build gate run for this cut exited
  **1**: `gene_validity.superseded_count` and `identity.version_coerced_from` *"moved and the release
  record does not list it"*. Both are real manifest additions from the 2026-08-31 batch, both carry a
  `DeclaredChange` written the day they landed, and neither had reached `manifest_fields` — the two
  declarations went in at 06:52 and 07:04, after the measurement the list came from, and the readiness
  table recorded the gate green earlier that day. **The shape is the record's own construction**:
  `SweepMeasurement.as_record` produces the measured half with `declared` deliberately empty, which is
  exactly what makes the gate useful and also what lets a later item add its declaration and leave the
  measured list behind. Nothing in a checkout could notice — the gate needs the previous release
  installed and is a release-sequence command by design. The guard is an **asymmetry**: a declared
  *addition* must be listed, because a field that did not exist before moves wherever its block
  appears; a declared *correction* may be unmeasurable on the corpus, so `gene_validity.classifications`
  and `gene_metrics.signature` stay declared and unlisted and the gate keeps its existing *note* for
  the reverse. The record's `evidence` sentence already carried the current numbers, so only the field
  list was stale. After the fix: *"release record for 0.7.0 covers the measurement"*, exit 0. *(from
  the 0.7.0 pre-build gates)*

- **RM158 — the GWAS pass asked about one table's rsIDs, and the answer already existed in this
  package.** *(`just-dna-enricher`; **additive**, and **no schema change** — no column, no vocabulary
  member, no signature moves.)* `gwas._module_subjects` built its `(rsid, variant_key)` list from
  `variants.csv` while five authored models carry `rsid`, so a module whose rsIDs live in
  `haplotypes.csv` or `pharm_variants.csv` got no associations and no line saying none had been asked
  for — a spec carrying one `haplotypes.csv` row for CYP2C19\*2, which the Catalog has associations
  for, returned `[]` against the pre-fix code. **The third instance in one sweep, and the one worth
  reading**: the fix was already written. `enrich.Subject` and its collector exist for exactly this
  question — resolution read `variants.csv` alone until RM43, when a PGx module *"which by design
  carries no `variants.csv`"* enriched to an empty `resolution.csv` — and this pass, written
  afterwards, restated the narrow loop instead of calling it. So grep for the **question**, not for
  the bug. `_collect_subjects`/`_Subject` are now public (`collect_subjects`/`Subject`), since a
  private name is what kept the second caller from finding the first. `studies.csv` carries `rsid` and
  is deliberately not a subject: a study row references the variant it grounds, which the module
  already carries. Measured across the corpus before and after — `pathogenic_clinvar` 301,
  `hboc_palb2` 16, `mt_heteroplasmy` 2, `grch37_build` 0, identical lists — because `variants.csv`
  goes first in the collector and first occurrence wins, the precedence that stops a PGx row taking an
  identity a SNP row minted. *(from the RM155 sweep)*

- **RM157 — the gene set three passes take their scope from read one table while nine carry the
  column.** *(`just-dna-enricher`; **additive**, and **no schema change** — no column, no vocabulary
  member, no signature moves, and no ordering change, since `gene_metrics` sorts its rows by
  `(gene, dataset)` before writing.)* `gene_metrics.module_genes` built its list from `variants.csv`
  alone. It is not a report but the **scope** of the constraint-metrics pass, the gene-validity pass
  and the ClinGen dosage pass — all three call it — so a module whose genes live in its PGx tables had
  all three quietly do nothing: no rows, no findings, and no line saying a question had not been put.
  **Measured on this repo's own corpus**, where `cyp2c19_star_alleles`, `apoe_epsilon`,
  `cyp2c9_warfarin_grch37` and `hfe_compound_het` returned `[]` while naming CYP2C19, APOE, CYP2C9,
  VKORC1, CYP4F2 and HFE. Two things worth reading together: the workspace already held **two answers
  to one question**, since `pgx._module_genes` reads two PGx tables and nobody had put them side by
  side; and RM104 had patched the *symptom* — an `UnboundLocalError` on "any module with no
  `variants.csv`" — with that sentence sitting in a comment, describing the defect as a shape rather
  than asking why the list was empty. The set is now derived from the same registry walk the
  identifier roster uses, and a table that will not parse **refuses** here rather than being routed to
  `not_read`: a reporting surface may narrow, a scope may not. `IdentifierRoster` gained `read_errors`
  so the loader's own message survives into that refusal and `gene_validity`'s `variants.csv is
  invalid` diagnosis is unchanged. `pgx._GENE_TABLES` stays two tables — it decides whether the
  star-allele cross-check *applies*, which is a fact about that check's inputs. *(from the RM155
  sweep)*

- **RM156 — the roster RM155 widened was gated behind the one table it had stopped depending on.**
  *(`just-dna-enricher`; **additive**, and **no schema change** — no column, no vocabulary member, no
  signature moves. What moves is which modules the check runs on at all.)* Two gates in front of the
  widened roster were still keyed on `variants.csv`: `check_identifiers(spec_dir=)` loaded that table
  unconditionally and raised `variants.csv is invalid: ... not found`, and `check-identifiers`
  returned *"no variants.csv — nothing to check"* one call earlier and hid it. The table has never
  been mandatory, and **four of the nine tables carrying `gene` are the PGx kinds a module is built
  entirely out of** — reproduced on this repo's own corpus, where `cyp2c19_star_alleles`,
  `apoe_epsilon`, `cyp2c9_warfarin_grch37` and `hfe_compound_het` carry no `variants.csv`, name
  CYP2C19/APOE/CYP2C9/VKORC1/CYP4F2/HFE between them, and all four exited 0 having asked nothing.
  **S86's unreadable `0`, one level above the function that repaired it.** The command's guard is now
  the **roster** — nothing to check means no id-bearing table was read, and only then is no
  attestation written, which is the half of the old guard that was right; an absent `variants.csv` is
  no rows, a present-and-unparseable one still raises. **A third vacuous pass beneath them**: with
  symbols in hand and no rows, `_gene_locus_conflicts` returned `compared=0` with `None` beside it,
  the `ran(0, 0)` its own attestation docstring forbids. *(from the RM155 sweep)*

- **RM162 — `RM_TOC.md` is an index, and an index is not an allocator.** *(tooling only —
  `.claude/rm-next.py` plus its test; **no package, no schema change**, nothing a consumer installs.)*
  The `Sn` loop has allocated ids since it was built, because an id written into a document collides
  when it is stale. `RMn` had no allocator: the number was read by grepping *"the highest in use"*, and
  the window between that read and writing the entry is where a second session reads. **Reproduced by
  this repo on itself** — on 2026-09-01 two sessions sharing one working tree filed different work as
  **RM159** a minute apart, and `741ec59` renumbered one to RM161. The new tool scans every
  `docs/**/*.md` and **reserves** the next number in the same locked write; a tool that only *printed*
  the number would be the same defect with a nicer interface. **The lock is on `docs/`, never on
  `RM_TOC.md`**: a leftover lockfile would block every later run (`@flock-not-a-lockfile`), and — the
  half that was measured rather than assumed — `flock` binds an **inode**, so an atomic rename-over
  leaves the holder locking an unlinked file while a second process acquires immediately. A reservation
  is a visible `🔷` row in the index rather than a side-car it cannot see, and `--release` leaves a `✖`
  tombstone because **ids are never reused** — the first cut deleted the row, the number went invisible
  to the scan, and a released RM10 was handed straight back out. Pinned by a test that runs eight
  allocators at once **and runs the same eight with `flock` neutered to watch them collide** (5 distinct
  of 8, one number taken three times). The loop's Step 5 bullet, which told an agent to read the number
  off the index and named a highest that had been stale for 114 items, is corrected. *(the 2026-09-01
  collision)*

- **RM155 — the identifier roster read one table while eleven carry the column, and reported its
  blindness as a clean zero.** *(`just-dna-enricher`; **additive**, and **no schema change** — no
  column, no vocabulary member, no signature moves; the new report fields default to empty, so an
  existing caller reads unchanged.)* `check_identifiers` built its trait and gene rosters from
  `variants.csv` alone while **eleven** authored models declare `trait_efo_id` or `gene` — `StudyRow`
  has carried the trait column since 0.3 — so a 67-variant module carrying its trait id on all 68
  `studies.csv` rows reported nothing checked and nothing flagged, and could ship a retired CURIE with
  every gate green. **The unreadable `0` was the defect rather than the omission**: it asserted *this
  module declares no trait* and *its traits are in a table nobody read* in one breath, which is
  `@unreachable-not-absent` at a finer grain, so widening the roster alone would have left the hole —
  a wide roster still returns `[]` for a module that genuinely declares none. Both halves shipped: the
  roster is **derived from `DRAFTABLE`** (nine tables per column, asserted as an equality over the
  walked `_ALL_MODELS` rather than listed, so a kind added later joins by existing), and
  `IdentifierReport` gained `trait_tables_read`/`trait_tables_not_read` plus the gene pair, with the
  CLI count naming its own denominator. `MeasureBinRow` is correctly absent — the abstract base whose
  four concrete subclasses are each their own entry — and the three **derived** models carrying these
  columns are excluded on purpose, since a stale id in a machine-written row is the *source's*
  currency and no author can act on it. **A third instance one level up**, found by the same framing:
  `report.clean` is `all()` over a possibly-empty set, so `check-identifiers` printed a green *"all
  identifiers current"* having asked nothing at all. An absent optional table and one that exists and
  will not parse are kept apart; only the second warns. *(S86)*

- **RM154 — an rsID the source HAS was published as an absence, and the warning explaining it was
  false.** *(all three packages; **additive**, and **no schema change of any kind** — no column, no
  vocabulary member, no signature moves, and every existing module recompiles byte-identically.)*
  `enrich` writes `status: not_found` — *this source has no record of your rsID* — when the source
  answered and the **allele-aware filter rejected every locus**. Reported over five subjects of a
  64-variant longevity module authored from a GRCh37/hg19 supplementary: the paper spells the submitted
  strand, so its `G/A` meets GRCh38's `C/T`, and Ensembl returns all five immediately. Reproduced
  offline against the real path — a snapshot that has the rsID with complemented alleles and one that
  genuinely lacks it write **byte-identical rows**. This is the fourth state in the family RM98 built
  (`unreachable_rsids` = the request failed, `unconsulted_rsids` = nobody looked, `unresolved` = no
  position and silent about why): here the asking **succeeded** and the answer did not match. New
  `EnrichmentResult.allele_mismatches`, carrying `AlleleMismatch(rsid, genotype, loci, offered,
  strand_flip)`, plus one aggregated warning in both modes saying the source *has* them. **The row is
  deliberately unchanged**: a new `VALID_RESOLUTION_STATUS` member is a wire change, and *deleting* the
  row moves `resolution_signature` (`variant_key`/`rsid` are fact fields, `status` is not — measured,
  not reasoned), so what moved is the reason rather than the row. **Second defect, in the sentence the
  reporter quoted**: `hosting_verdict`'s two `False` arms shared one explanation, so a strand-flipped
  SNV was diagnosed as *"The event sizes differ, which re-anchoring cannot change"* about two 1 bp
  substitutions — `compiler.resolution.contradiction_reason` is now `undecided_reason`'s twin on the
  `False` side, with a test asserting the arms' reasons stay pairwise distinct. `strand_flip_explains`
  and `reverse_complement` land in **format** (pure string work, and the compiler's twin site needs
  them); both withhold rather than guess — a degenerate code cannot be complemented, and a palindromic
  SNV that already fits is never reported as a flip. *(S85)*

- **RM153 — the identity CIViC does not publish, recovered through a registry rather than by lifting a coordinate.**
  *(`just-dna-enricher`; **additive**, **no schema change** — one client, one snapshot derivation, three
  withhold reasons, one licence row.)* RM152's residue. CIViC publishes GRCh37 coordinates or none, and
  after every published identifier is read some variants still have no route to a GRCh38 identity. Two
  questions, answered in opposite directions.
  **Taken: the ClinGen Allele Registry.** A CAID is build-independent; the registry serves an
  rs-number *and* a GRCh38 coordinate, needs no key, and answered 102 probe requests with zero
  failures. Recovery over the direction set goes from **138/290 (48%) to 237/290 (82%)** — 52 via an
  rs-number, 12 via a coordinate, and **35 one-sided indels anchored**. The rs-number is preferred
  because ClinGen supplies it and *Ensembl* verifies it: two authorities, so the check is real, which
  is precisely what a lifted coordinate lacks. New `identity_derivation="caid"` keeps a route-bearing
  row in the snapshot instead of dropping it; `unresolvable_identity` now means no identifier at all
  and falls from 204 rows to 59. The pass runs at **draft** time — a build that fetched would forfeit
  the offline reproducibility the dated input exists to give — and `--offline` withholds those rows as
  `caid_unresolved`: **unplaced, never unplaceable**.
  **One-sided indels are anchored VCF/Picard-style.** The registry states an insertion with an empty
  `referenceAllele` and a deletion with an empty `allele`, in interbase terms; neither is a row a
  `ref`/`alts` pair can hold. Prefixing both sides with the reference base before the event is the
  left-aligned form VCF requires, and the interbase `start` *is* that anchor for both shapes, so one
  rule covers them. All 35 rows that previously read `no_identity` are one-sided indels and every one
  anchors. Verified twice: the base at `chr3:10142013` is `G`, and ClinGen's own HGVS is
  `g.10142013dup`, which is exactly the `G>GG` produced. An unreadable anchor is withheld under its
  own reason, never guessed.
  **Refused: liftover.** Reopened on request and closed on the number — ceiling 13 evidence rows on 9
  variants, honest recovery **at most one**. Three are gene-level assertions no genotype satisfies on
  any build; five are imprecise by the source's own HGVS and the registry refuses to parse them at
  all; and variant 2099 lifts *exactly* to **a different allele** than its own name and alias
  describe, which is RM48's hazard demonstrated rather than argued. `pyliftover` agrees with Ensembl
  on all 18 endpoints so buys no accuracy and downloads an unpinned chain; Picard `LiftoverVcf` was
  not run because 8 of the 9 carry no REF/ALT to feed it.
  **The registry's terms are unestablished** and recorded as such: `reg.clinicalgenome.org/site/terms`
  answers 200 with a generic broken-link page, so every axis is `None`. ClinGen's CC0 grant covers the
  gene-curation surface, not this one. Nothing is redistributed.
  Measurements in [CIVIC_SURVEY.md](probes/CIVIC_SURVEY.md) and
  [CIVIC_UNRESOLVED.md](probes/CIVIC_UNRESOLVED.md).

- **RM152 — CIViC adopted on the axis it can answer, and refused on the one it was proposed for.**
  *(`just-dna-enricher`; **additive**, and there is **no schema change of any kind** — no column, no
  table, no vocabulary member. The adoption rides on `direction` and `state`, which have existed since
  0.3, which is why it lands inside an uncut release without sizing it.)* S84 proposed CIViC as a
  second `clin_sig` concordance authority; measured, its germline subset carries five ACMG-tier calls
  and **zero benign-class**, so `discordant` is unsayable and the check would read `single` or
  `concordant` by construction. The same measurement found 1,458 germline rows on
  `Predisposition`/`Protectiveness` — the **`direction`** axis — where the `NA` count is 0. So the
  drafter that was rejected for "rows with an empty significance column" is right on `direction` and
  wrong only on `clin_sig` (812 `NA`), and that is what shipped.
  **New `civic build`**: a dated release (`--release 01-Aug-2026`) reduced to one parquet plus
  `release.json`, byte-reproducible. It reads the **bulk TSVs, not the GraphQL API**, because only the
  download side is dated — and that surfaces a fact neither surface declares: the TSV is
  `accepted`-only at 4,903 rows while the API defaults to `NON_REJECTED` at 11,518, so **a count from
  one is not comparable with a count from the other**. Three inputs are required, because
  `MolecularProfileSummaries.tsv` is what tells a combination genotype from a dangling reference.
  **New `draft-panel --source civic`**, writing `direction` and never `clin_sig`; `--clin-sig` is
  reported inert rather than silently ignored. **New `CIVIC_TERMS`** (CC0 1.0), distinctive not for
  permitting redistribution — five sources here do — but for asking nothing back.
  **A `direction`-axis concordance record was refused**, which was RM152's open question: genuine
  risk-versus-protective opposition is **0** at every scope and status basis, the three contested
  variants are claim-against-refutation and dissolve under `ACCEPTED`, and **nothing else in the
  enricher fills `direction`**, so there is no second authority to be concordant with.
  **Coordinates are GRCh37 or absent, never GRCh38**, and the snapshot survives that by reading the
  rsID and GRCh38 accession CIViC publishes beside them rather than lifting anything — RM48's rule
  applied, and better than it hoped, since a published rs-number is an independent value resolution
  can cross-examine. The residue is RM153. **A refutation is kept with its direction withheld**:
  "does not support predisposition" removes a claim without establishing its opposite.
  **One fix in shared code, found by dogfooding rather than review** — `append_partial_rows` built its
  covered-set from `partials[0].match_on` while comparing each row against its own, so a mixed-arity
  batch re-added rows on **every lap**: invisible on a first run, a file that grows thereafter.
  Providers now pass one constant tuple and a mixed batch is refused.
  Measurements in [CIVIC_SURVEY.md](probes/CIVIC_SURVEY.md); the decision is the RM152 addendum in
  [PROPOSAL_0_7](proposals/PROPOSAL_0_7.md).

- **RM146 — every authored column now says which release it appeared in.**
  *(`just-dna-format`; **additive** — a marker on each field declaration. No column, no parquet, no
  signature, no manifest field.)* A module authored on 0.6.6 met a registry running 0.6.1 and got
  `studies.csv line 2 [curator]: Extra inputs are not permitted` — byte-identical to what a typo
  (`[curatr]`) produces, and the two want opposite actions from an author: upgrade the reader, or fix
  the cell. pydantic's message under `extra="forbid"` could not carry the distinction, because the
  information was not in the model.

  **New: `just_dna_format.base.since("0.6.5")` on every authored field, read with
  `base.field_first_seen(model)`** — a plain `{field: release}` map, so any tool rendering our findings
  can answer *when did this column appear* offline. It composes with `vocabulary()` in one
  `json_schema_extra` dict rather than replacing it. `stamped_identity_field` now takes `first_seen`
  as a **required** argument: a compiler-stamped column is still one an older reader refuses.

  **The backfill was measured, not recalled** — parsed per release tag from the AST rather than
  imported, since old code need not import under a current Python. 414 fields across 31 models: 115
  date to 0.2.0, 81 to 0.4.0, 150 to 0.5.0, 160 to 0.6.0, 3 to 0.6.5, and 78 land in 0.7.0. The answer
  is per **(model, field)**, never per name: `curator` is on `VariantRow` from 0.2.0 and gains its
  `StudyRow` twin only in 0.6.5.

- **RM117 — an answered conflict the archive has since resolved says so, instead of reading as a typo.**
  *(`just-dna-format` + `just-dna-compiler`; **one new warning code**, no field and no signature moves.)*
  `clin_sig_concordance.csv` holds contested subjects only and is rewritten whole, so a subject leaving
  the record means the authorities stopped disagreeing — which is how an author learns the archive
  caught up with them. An `overrides.csv` row answering that conflict then reaches nothing, and until
  now it drew the generic *the subject may be mistyped, or the correction may be aimed at a row the
  compiler drops*, put to an author whose judgement had just been confirmed.

  **New: `overlay_answer_vindicated`** (actionable — the author can retire the overlay row, and nobody
  else can). It is an observation about the record and not a verdict: the authorities now agree and the
  row is unnecessary; who was right about the biology is not something a compiler can say. Scoped to
  that one table, because every other unmatched update is ambiguous and takes RM137's split.

  This is RM117's observability half. The **severity** half stays closed, and the second signal — a
  justification written about a value the source has since changed — is **RM151**, below: it needs the
  archive's value now against its value at record time, so it needed a fetch and an enricher home.

- **RM151 — an answer written about a disagreement the archive has since changed says so.**
  *(`just-dna-enricher`; **two new warning stems**, no field, no schema and no signature moves.)*
  An `overrides.csv` row against `clin_sig_concordance.csv` is a judgement about a *particular*
  disagreement, and its `reason` explains why. When the archive later says something else, that reason
  describes a disagreement that is no longer the one on record — and nothing said so.

  `enrich()` now compares each authority's fresh call against **the previous run's
  `clin_sig_authority_calls.csv`**, per `(variant_key, genotype, authority)`, for every subject the
  module's overlay answers. That table is the only place this format keeps what a source said at the
  time, so the finding **names it**: an overlay row against `frequencies.csv` or `resolution.csv` has
  no recorded baseline and nothing here promises one. Warns in both modes, escalates in neither.

  Three states, and withheld is never *unchanged*: `no_prior_record` (first run, unreadable previous
  record, or the authority was unchecked when the answer was written) and `unchecked_now` are info
  notes, not agreement. A difference that is only our own normalizer moving — same verbatim
  `clin_sig_raw`, different normalized member — is reported as a separate sentence, because folding it
  in would accuse a source of a change we made.

  **A move is observable exactly once**, by the run that notices, because the commit rewrites the
  baseline it read. That is the honest shape for an observation; persisting it needs the overlay row
  bound to the value it justifies, which is an authored-surface change and the binding RM117's
  objections all turned on missing. Silent on a module with no overlay answers, which is every module
  today. New surfaces: `clinical.answered_call_shift`, `concordance.shifted_authority_calls` /
  `read_recorded_calls` / `answered_call_sentences` / `answered_call_notes`,
  `licensing.overlay_answered_subjects`, and `EnrichmentResult.answered_calls`.

- **RM138 — closed with its numbers measured; no code changed.** *(documentation only.)* `carried`
  duplicates the text of the warnings it names, growing `compilation` **1.84×** across the reference
  corpus. Re-measured with the compression a real transport uses: **1.06× gzipped** over the corpus and
  **1.13×** on `pathogenic_clinvar`, the 113-warning module the item was filed about — because
  `carried` is a verbatim subset of `warnings`, which is precisely what DEFLATE's back-references
  eliminate. The whole with-`carried` payload gzips to 0.21× the *uncompressed* warnings-only one.

  **The encoding stands, and the recommendation is to serve manifests compressed** where the size lands
  — a catalog, an API response, anything shipping `manifest.json` over a wire. The three cheaper
  encodings stay rejected for the reasons the item already recorded. Closed inside 0.7 deliberately: a
  fourth encoding after 1.0 would be a removal, and removals are major-only.

- **RM136 — the enricher reads the author's overlay, so a correction stops coming back forever.**
  *(`just-dna-compiler` + `just-dna-enricher`; **additive** — one loader made public, one new counter
  on an internal result, no manifest field and no signature moves.)* The compiler applies
  `overrides.csv` before any check reads a row; the enricher re-read the raw derived file, so an
  author who corrected a `resolution.csv` cell through the overlay kept being told the same finding on
  every run, with nothing saying the correction had been recorded and honoured one tier over.

  **Read-only, at input reads, per field.** The enricher never writes through the overlay. Passes that
  read `resolution.csv` as an *input* (`frequencies`, `assertions`, `identifiers`' gene-locus check)
  now see the post-overlay rows; every **merge baseline stays raw**, because a pass that reads its own
  output file writes it back and post-overlay rows would bake the correction into the derived table. A
  finding is answered only when the overlay updates the very cell it is about.

  **Answered is not agreed**: the pair stays in the denominator and `PairCheck.answered` counts it,
  with one INFO line saying the correction is recorded. Dropping it would report a cleaner module than
  there is. New public API: `just_dna_compiler.compiler.load_overlay`, plus
  `licensing.overlaid_input_rows` / `licensing.overlay_answers` in the enricher — there is deliberately
  no second implementation of `apply_overrides`.

- **RM137 — the unmatched-overlay warning is now a property of the module, not of the lap.**
  *(`just-dna-format` + `just-dna-compiler`; **one warning code added, one reworded** — no field, no
  parquet, no signature moves.)* An overlay `update` naming a row the compiler drops matched on lap 1
  and warned on lap 2, so a module and its own `compile → reverse → compile` disagreed on
  `manifest.compilation.warnings`. The stable quantity turned out to be a property of the **target** —
  *could an artifact of this module carry that row at all* — which is computable from data that
  survives the round trip, so it answers the same on both laps whether or not the row is there to
  match. The unreachable finding therefore fires **matched or not**; that asymmetry is the fix.

  **Two codes where there was one**, and neither reading is "a typo" — a mistyped PMID is also an
  uncited one, so a mistake lands in the unreachable bucket:
  - `overlay_update_target_unreachable` (**new**, actionable) — no artifact of this module can carry
    the row: mistyped subject, or a correction aimed at a row the compiler drops, which is fine.
  - `overlay_update_unmatched` (**reworded**, so grep it afresh) — the subject *is* cited or
    positioned, so the table is short rather than the correction wrong. Re-run the enricher.

  **Scoped to `literature.csv` and `resolution.csv`** (`LOSSY_OVERLAY_TABLES`), the only two a reverse
  rebuilds from something narrower. The other six rebuild whole, so their warning was lap-stable
  already and its text is unchanged. `apply_overrides` gains an additive `defer_unmatched` keyword;
  `update_targets` / `classify_update_targets` are the split, and `cited_pmids` /
  `literature_target_survives` / `resolution_target_survives` are the predicates.

- **RM150 — `direction` gains `contested`; `unknown` stops meaning two things.**
  *(`just-dna-format`; **additive** — a new member on an existing vocabulary. Nothing re-points, so no
  published module changes meaning and nothing drifts.)* `unknown` had been carrying both *nobody
  assessed the sign* and *the sources disagree about it* — an absence and a finding — and RM148's own
  field description said so without giving a consumer any way to tell them apart. **`unknown` keeps
  its original meaning**, because re-pointing a shipped member would silently change what every
  published module already says by it; `contested` is added beside it, using the word this workspace
  already uses one table over (`clin_sig_concordance.csv`).

  This is the shade RM148 could not fold into a pair. An unestablished sign is still a sign, so
  *evidence that does not exclude either direction* is `direction=<sign>` +
  `stat_significance=not_significant` and needs no member — but no pairing of the two axes says *two
  sources disagree about the sign*.

  **Upgrading a legacy module is unchanged.** `_STATE_TO_DIRECTION` deliberately gains nothing: no
  legacy `state` value means *contested*, so only an author writing `direction` directly can produce
  it. `stat_significance` gains nothing either — a disputed sign is not a disputed strength.
  `contested` projects to `state=neutral` through `trimmed_state()`, like `unknown`, and that entry is
  **explicit**: the map is read with a default, so a member missing from it projects silently rather
  than failing, and the guard is now an equality over the walked vocabulary.

- **RM108 — a re-curation is recognised, and currency is derived rather than marked.**
  *(all three packages; **additive** — one new manifest field and two new warning codes. No column
  changed, so `gene_validity.signature` does not move and no module recompiles to new bytes.)*
  ClinGen's `assertion_id` embeds the curation timestamp, so a re-curated assertion arrives under a
  different id, misses the merge key, and is appended beside the row it replaces —
  `manifest.gene_validity.classifications` then published `["definitive", "refuted"]` with nothing
  saying which stood. **The newest `classification_date` is now read as current and nothing is
  deleted**; both rows stay in the file so the drift is visible.

  **The marker column the item was filed for does not exist, deliberately.** The row that must be
  marked is the one *already in the file*, and merge-not-clobber forbids the pass editing it — so a
  stored marker would be correct on every run except the one that created the ambiguity. Currency is
  derived at every read (`just_dna_format.gene_validity.classify_currency`, public), grouped on
  `(gene, disease_id, moi, submitter)` — the source's grain minus `dataset`.

  **Two edges withhold rather than guess:** a tie on `classification_date`, or any member of the group
  stating none, leaves no row current and none superseded; those groups publish all of their
  classifications. New: **`manifest.gene_validity.superseded_count`**, and the warning codes
  `gene_validity_superseded` / `gene_validity_currency_undecidable`, both **carried** — an author's
  only available edit is deleting a row, which falsifies the record. They warn in both modes in both
  tiers and escalate in neither; `validate` reports what `compile` reports.

  **One behaviour change beyond gene-validity:** the compiler's fact-table loop now de-duplicates
  check warnings on the message, as every both-sides check already did. This is the first fact check
  the pre-flight also runs, and without it the line — and its `warnings_summary` count — arrived twice.

- **RM103 — the manifest now records the version that was read, not only the one that was invented.**
  *(`just-dna-format` + `just-dna-compiler`; **additive** — a new optional manifest field, no digest
  moves.)* `normalize_version` strips every non-digit and pads to three zeros, so `version: abc`
  becomes `"0.0.0"` — deliberate since RM17, and unchanged here. What changes is that the artifact
  recorded only the *result*: `manifest.identity.version` read `0.0.0` with nothing beside it saying
  the author wrote `abc`. **New: `manifest.identity.version_coerced_from`**, the authored string when
  the model rewrote it and `None` when it was already canonical SemVer. The compiler's warning naming
  both values is unchanged and still fires in `compile` and `validate` alike; a build log is just not
  what a consumer holds.

  **`reverse_module` now re-emits the pre-coercion string**, recovered from the artifact's own
  `manifest.json` (`version_coerced_from` first, `version` second). Re-emitting the coerced one would
  leave the next compile nothing to coerce, so the new field would go absent on lap 2 and a module
  would disagree with its own round trip on a published field. An explicit `--version` still wins, and
  a bare parquet directory with no manifest still leaves the key out. **Side effect worth knowing:**
  reverse previously dropped `module.version` entirely unless a caller supplied one, so a reversed
  spec now carries the authored version where it used to carry none. Nothing hashes on it.

  The **refusal** half of RM103 — should a digitless version be rejected outright — is unchanged and
  stays on the 1.0 cleanup tracker; it is a tightening, and no sentinel SemVer exists to coerce to.

- **RM110 — `constraint_flags` had two producers, two encodings, and one of them inside the fact set.**
  *(`just-dna-format` + `just-dna-enricher`; **one existing artifact's digest moves** — see the cost
  line.)* The live gnomAD route pipe-joined its flag list; the bulk-TSV snapshot route copied gnomAD's
  **JSON array literal** into the cell. Re-probed against the published v4.1 parquet before any code
  moved: of 18,111 rows **none** is null or empty — 17,403 carry `[]` and 708 carry a real literal in
  14 distinct shapes — so `if row.constraint_flags:` was true for **100%** of snapshot rows where the
  flagged fraction is 3.9%, and splitting a two-flag cell on `|` returned one bogus token. The column
  is inside `GENE_METRICS_FACT_FIELDS`, so the same gene fetched two ways minted two
  `gene_metrics.signature` values.

  **Fixed on the model, not in the fetching tier**: `just_dna_format.gene_metrics.normalize_constraint_flags`,
  bound as a `mode="before"` field validator (neither producer hands over the declared `str | None`,
  and a `mode="after"` validator cannot rescue a value the type rejects first). The published snapshot
  is immutable and every `gene_metrics.csv` already written from it carries `[]` on disk, so a
  producer-side fix would have left those tables contradicting the column's own description. Three
  call sites share the one function — the live route, `lookup_snapshot` (the published snapshot) and
  `constraint_build` (future ones) — and it is idempotent, so a rebuilt snapshot passes unchanged.
  "Empty → null" was only half the fix: the non-empty cells needed parsing, or the 708 flagged rows
  stayed unreadable. A bracketed string that does not parse is kept verbatim rather than guessed at.

  **Cost, measured:** exactly one row in the reference corpus — `reference_examples/hboc_palb2/`
  carried `constraint_flags=[]`, so its `gene_metrics.signature` and `artifact.digest` move; the
  checked-in CSV was corrected in the same commit. Nothing else in the sixteen examples changes.
  **If you have compiled modules from the v4.1 constraint snapshot, their `gene_metrics.signature`
  will move on the next recompile, and that is the fix arriving rather than a regression.** The field
  description, false on the snapshot leg in both directions, was rewritten.

- **RM147 — a source read by hand that yields no row had nowhere to go, and the home already existed.**
  *(`just-dna-format`; documentation and a test — no behaviour changed.)* Filed and answered on
  2026-08-31 from a consumer report (S82), which asked for a view rather than proposing a shape.

  An agent read five literature services by hand to confirm the papers behind two rows and recorded it
  as five `licensing.csv` rows at `layer=literature`. The reporter removed them on our own two rules —
  a literature source's terms are per **article** (RM46), and a pass that put no row in a table records
  no source (RM142) — and measured that they bought no enforcement. Then asked the real question: after
  removal, nothing anywhere records that a human went and looked.

  **The home already exists.** A `literature.csv` row no study, bin or pharm row cites is kept in the
  CSV and dropped from the artifact with `literature_row_uncited`, shipped in RM79 for a citation the
  author deleted — and it is the same shape for the opposite case, a paper read that did not become a
  row. It is structured and checked, it **cannot make a licence claim**, and it is about the *paper*,
  which is the thing consulted; a service is only how the author reached it.

  **Consumers:** nothing changed. `LiteratureRow`'s docstring now says this is that case's home and why
  the licensing table is not, and a test authors the reported shape — two articles, one cited and one
  not, green `--strict`, the uncited one named, and no `licensing.csv` at all, because nothing is owed
  for reading an abstract.

- **RM148 — `direction` and `stat_significance` are one pair, and the description did not say so.**
  *(`just-dna-format`.)* Filed and built on 2026-08-31 from a consumer report (S83), an hour after S80
  was accepted and in the same spirit.

  Two runs of a byte-identical prompt, same model and paper, wrote different values for one variant on
  one body of evidence: `risk`/`suggestive` against `unknown`/`not_significant`, both green. The
  evidence was two cohorts trending the same way at p ≈ 0.073, combined OR 3.58 with a CI of 0.96–13.4
  at 28.4% power — and both readings were defensible against a description that named the four members
  and said only *orthogonal to `state`*.

  **Not a vocabulary gap.** `direction` records the sign of the reported estimate; `stat_significance`
  records how far to lean on it; and the orthogonality is itself the answer to *is a sign you cannot
  lean on still a sign* — yes, because the other column says you cannot lean on it. The state the
  report wanted a member for is already the **pair**, `direction=risk` + `stat_significance=
  not_significant`, which authors and validates today.

  The description now carries that reading and bounds `unknown`: *no sign to record* — not assessed, or
  the sources conflict — **never a sign you may not act on**. Writing `unknown` for a weak trend
  discards the sign the paper reports and leaves `stat_significance` speaking about nothing.

  **Consumers:** one description string, so anything rendering `model_fields` picks it up. No member
  added — a *looked, no sign established* member would be a second spelling of the pair, which is
  Principle 5's overloading arriving as a synonym, and permanent under P3. A test asserts the two
  vocabularies stay disjoint but for `unknown`.

- **RM144 — the licence-disagreement warning printed the remainder as though it were the whole set.**
  *(`just-dna-compiler`.)* Filed and built on 2026-08-31 from a consumer report (S79).

  The check filtered the annotation-layer rows to those whose licence *differs* from the declaration,
  then rendered that remainder as the whole set. A two-source module declaring `CC-BY-NC-ND-4.0` — an
  exact match for one row, and the binding constraint on the artifact — printed *sources report
  ['CC-BY-4.0']*, with the agreeing row invisible in the sentence complaining about agreement.

  **Two problems with different repairs read identically:** *your declaration is unsupported* versus
  *your declaration is not universal*, the second being the ordinary mixed-licence shape where the most
  restrictive term binds and the declaration is already correct. It cost two agents a full
  re-adjudication that found nothing wrong, and it survived RM142's fix — removing the phantom row
  leaves a real disagreement still rendered as total.

  The count now leads and the agreeing rows are named beside the disagreeing ones, with a distinct
  sentence for the genuinely-unsupported case. **The denominator counts rows, not distinct licences** —
  two sources sharing a licence are two obligations — and a licence-less row or a non-`annotation` layer
  stays outside it. Suppressing the warning when any row matches was refused, on the reporter's own
  argument: a module declaring the least restrictive of several is exactly the one worth warning about.

  **Consumers:** the message text changes; `declares license` still leads it, which is the fragment the
  existing test keys on, and the non-escalation is unchanged and re-pinned. No reference example moves a
  digest, signature or warning — the corpus has no mixed-licence module, which is why this survived it.

- **RM145 — `state`'s six members were printed as peers, and two of them are retired in our own code.**
  *(`just-dna-format`.)* Filed and built on 2026-08-31 from a consumer report (S80).

  `VariantRow.state` was described as `One of: risk, protective, neutral, significant, alt, ref` — six
  values, no standing — while `derive.py` calls `alt`/`ref` **the retired descriptors** and maps both to
  `direction=unknown`. A consumer whose authoring surface passes our descriptions through verbatim
  (deliberately, so a vocabulary change reaches an author without being restated) therefore offered an
  agent six equal choices, and it picked `alt` for a heterozygote. **The reporter had to read
  `derive.py` inside their own `.venv` to author one cell honestly.** Measured across the sixteen
  reference examples: 377 `risk`, 4 `neutral`, and zero uses of `significant`, `alt` or `ref`.

  The description now separates current members from superseded ones and names each group's successor.
  **Three groups rather than the two the report asked for:** `state` is the Principle 5 anti-pattern the
  charter names by hand, so the split is by which axis a value was really on — `significant` is a
  significance claim that `stat_significance` owns, not a dead value, and grouping it with `alt`/`ref`
  would tell an author it means nothing when it means something this column is the wrong place for.

  **Consumers:** one description string, so anything rendering `model_fields` — `describe`,
  `requirements`, `reference` and the reporter's own surface — picks it up with no change of their own.
  No vocabulary member added or removed and nothing invalidated; removal stays major-only and was not
  requested.

- **RM143 — the enricher diagnosed a wrong-assembly coordinate and `compile --strict` built over it
  anyway.** *(`just-dna-compiler`.)* Filed and built on 2026-08-31 from a consumer report (S78).

  A GRCh37 coordinate pasted into a GRCh38 module — `rs61849494`, 5.6 Mb and a strand flip away from
  where the module says it is. `enrich --strict` refuses with a diagnosis naming the rs-number to author
  instead; `enrich` best-effort reports it and writes the table; and `compile --strict` then succeeded
  **silently**, over a module internally consistent and about the wrong locus.

  **Two of the reporter's three asks were already shipped**, which is half the answer. Their option (2),
  re-running the rsid↔coordinate check in the compiler, is refutable on the data: `resolution.csv` holds
  one coordinate, not both — for a coordinate-authored row the enricher records what the author wrote —
  so there is nothing to compare without a fetch, and P2 forbids the fetch. Their option (3), a compile
  warning, is `verification_findings_recorded`, which shipped in this same release and is absent from
  the 0.6.6 they measured.

  What was missing was the last step of their option (1): the diagnosis reached `verification.json` and
  **no severity attached to it**. `build_disagreement_error` now refuses a `strict` compile on a recorded
  `genome_build_agreement` finding, in both `validate_spec` and `compile_module`, with the error equal on
  both sides and placed ahead of `output_dir.mkdir()` so a refusal writes nothing.

  **The strict line does not move.** `strict` still means reproducible, never right — the compiler has no
  reference and a file shifted by one base still passes. This one check is the exception on
  *internal-consistency* grounds: its findings say the rows are on a different assembly than the
  `genome_build` the module declares, which is one authored file contradicting another rather than the
  module disagreeing with an outside archive. Every other recorded finding still only warns, pinned over
  four checks including `reference_allele`, which produces this diagnosis's own input.

  **Consumers:** a `strict` compile refuses a spec whose `verification.json` records a wrong-build
  finding — new behaviour for anyone compiling one, and the point. Everything else is unchanged: no
  attestation is silent (an unverified module is the ordinary case), `findings=0` is a clean bill, and a
  `skipped` record is unknown, which is what `--offline` writes. `best_effort` builds and warns as
  before. No reference example carries such a finding, so the 0.7.0 release record is unaffected.

- **RM142 — the dosage pass declared a ClinGen obligation for a module ClinGen curates nothing of.**
  *(`just-dna-enricher`.)* Filed and built on 2026-08-31 from a consumer report (S77).

  A single-variant `SIRT6` module. The pass reported `dosage: missing: [SIRT6]`, wrote no
  `gene_metrics.csv` row, and wrote a ClinGen row into `licensing.csv` anyway. That table travels to
  the registry and is read as *this module uses this source*, so the module carried a false statement —
  and it fired `declared_license_disagrees` against a declared licence that never met ClinGen's, sending
  an author to adjudicate a conflict that does not exist. Both reproduced.

  **The compiler cannot catch it.** `_source_checks` exempts the `annotation` layer from its orphan
  warning by design (RM46), because that is where an author is told to record a hand-read source and
  warning about it would make compliance noisy while omission stayed silent. Only the pass knows whether
  it contributed.

  The fix is the rule the rest of the family already follows: `gene_metrics`, `frequencies`,
  `assertions` and `gene_validity` all derive the source set from the rows they wrote, so a pass that
  wrote nothing records nothing. `clingen.py` alone built a fixed row and wrote it unconditionally.
  **The siblings were checked rather than assumed** — run offline over a module they cover nothing of,
  neither writes a licensing file at all.

  **Consumers:** a module whose dosage pass covered no gene no longer carries a `clingen` row, and no
  longer warns about a licence disagreement it had no part in. A module ClinGen actually fed is
  unchanged — keyed on what this run covered, not on what the table holds and not on the absence of
  missing genes, with tests for all three. No reference example changes, so the 0.7.0 release record is
  unaffected.

- **RM141 — `validate --strict` blessed a module `compile --strict` refused, whenever the resolution
  table was partial.** *(`just-dna-compiler`.)* Filed and built on 2026-08-31 from a consumer report
  (S76) whose headline mechanism did not reproduce, and whose second finding was ours.

  The report: an `enrich` killed by a quota limit left a `resolution.csv` covering 201 of 263 subjects,
  and — the urgent half — merge-not-clobber was said to turn that into a silent wrong answer, since
  re-running would merge onto the stale rows and never retry the missing 62. **That does not
  reproduce, on this tree or on the `v0.6.6` they ran.** `enrich` gap-fills: a run over a table
  covering one of three subjects asks the source about exactly the other two. The atomic write they
  asked for is also already shipped, as RM128 in this same release, which is why the interrupted run
  left the previous table rather than a truncated one.

  **The reporter then corrected their own account**, which sharpens what this closes: the file was
  never truncated — 203 sorted rows, a clean final newline, and the 62 absent rsIDs scattered across the
  whole range rather than forming a tail. A complete write of an incomplete resolution *set*, which
  matches the code: a subject whose live request could not be made is written as no row at all, so the
  table never states a negative nobody established. Nothing was interrupted, so the atomic writer would
  not have prevented it — and the same file comes out of a `best_effort` run that completes normally
  over an unreachable source. The closure is this item, by the right route: reading the table against
  the spec beside it is indifferent to *why* a row is absent.

  **What is real is that nothing said so until the compile.** `compile --strict` refuses a module whose
  variants have no position after resolution; `validate --strict` did not report it at all. So the
  pre-flight passed clean and the compile immediately after refused — the third break of the parity
  rule, hiding behind that rule's own exemption. What stays compile-only is a check reading *resolved*
  rows, and whether the injected table **can** place a row is arithmetic over bytes the pre-flight has
  already loaded.

  `resolution.unresolved_subjects` is the predicate resolution applies, now called from both sides
  rather than restated, and under `strict` the pre-flight appends the compile's error verbatim. Two of
  the compile's own distinctions are kept: nobody-asked is not asked-and-absent, and `--no-resolve`
  silences the check the way it silences the fill. A **double-report** was found doing it — both passes
  reach the finding for one subject, measured at 24 warnings for 12 subjects with `warnings_summary`
  counting 24 — and is de-duplicated on the message.

  **Consumers:** no schema change, no new field, no new warning code. A spec that was going to be
  refused by `compile --strict` is now refused by `validate --strict` too, with the identical message —
  which is a behaviour change for anyone treating a green `validate` as a compile guarantee, and is the
  point. Measured: no reference example moves its `artifact.digest`, `content_signature` or warnings,
  so the 0.7.0 release record is unaffected; none of the sixteen has a partial table, which is why this
  survived a corpus that size.

- **RM140 — a study row's p-value and effect size were asserted to belong together, and nothing
  recorded what either came from.** *(`just-dna-format` + `just-dna-compiler`.)* Filed and built on
  2026-08-31 from a consumer's reproducibility benchmark (S75), after the proposal round had closed —
  it is not one of the twelve and lands inside this same uncut number, because a new optional column is
  what sizes a release.

  Two agents, byte-identical prompts, the same three DOIs, overlapping on exactly one row: `p_value`
  0.36 against 0.75, `effect_size` 1.42 on both. Neither was a misreading. The paper reports two
  analyses of the same association — an allelic Fisher's exact test (`OR 1.4, p 0.36`) and a univariate
  logistic regression (`OR 1.42, p 0.75`) — and one run's row carried the second's magnitude beside the
  first's p-value. **Everything was green**, `strict` on both `validate` and `compile`, `audit_module`
  and `quotes_found` included: the provenance quote is verbatim and correct because it grounds the
  significance *verdict* and contains no statistic at all, so quote verification is structurally blind
  to this. `study_design` describes the **study**; nothing described the **analysis**, so a correct row
  and a mispaired one were byte-indistinguishable to every consumer and every check — and no check could
  be written, because the facts it would compare were recorded nowhere.

  **`StudyRow.statistical_test`** is one optional free-form column shaped like `study_design`: which
  test or model produced this row's numbers, and what it was adjusted for. No vocabulary, and
  **deliberately no gate** — the reporter argued that against their own ask and is right, since the
  gate is unwritable before the column exists and shipping both would make every published row
  retroactively incomplete.

  **The one behaviour change is the duplicate-citation warning.** `duplicate_study_citation` reads a
  repeated `(variant_key, pmid)` as *the same claim written twice*, which two rows naming two analyses
  are not; **both stated and different** now suppresses it, and nothing else does. An absent
  `statistical_test` is *unknown*, and unknown against a stated value cannot establish that two rows
  describe separate work — Kleene rather than `a != b`, which would suppress on every absent cell and
  silently retire the check for every module written before the column existed.

  **Measured, not asserted.** `artifact.digest` moved on **10 of the 16** reference examples — exactly
  the ten carrying a `studies.parquet` — and `content_signature` on **none** of the sixteen. The
  published `0.7.0` release record was re-measured with it rather than left standing: its two parquet
  axes read `4/15` before this item and read `14/15` after, the `studies.parquet` column is declared,
  and the concordance-parquet declaration that called itself *the release's most visible consequence*
  was corrected, because it was a measured claim and stopped being true. The gate exits 0 against the
  amended record.

  **Consumers:** one optional column on `studies.csv` and `studies.parquet`, read by nothing that does
  not want it; unset, it is omitted from `content_signature`, so no published module's identity moves.
  The warning's code and message are byte-identical for every case that still reports. `_KEY_FIELDS` is
  **not** widened — the published `key.columns` for `studies.csv` is still `(variant_key, pmid)`, and
  re-keying a shipped authored table is major-only. Note the premise this corrects: two rows sharing a
  variant and a PMID have always both reached `studies.parquet` — the duplicate is a warning, never a
  drop — so the capability was there and only the legibility was missing.

- **The 0.7 round's files were closed out.** *(Documentation only — no package changed.)* Four entries
  sat in forward-only files with a `SHIPPED` banner on them, which reads as late rather than done:
  RM126 and RM71 in `ROADMAP_0_7.md`, RM133 and RM134 in ROADMAP.md. All four moved to
  [ROADMAP_HISTORY.md](ROADMAP_HISTORY.md), so the round's twelve are now in one place.

  **`ROADMAP_0_7.md` closed with them, and the succession is the point rather than the tidying.** The
  minor-deferral file is named for the release that will decide its contents, so a cut closes one and
  opens the next: the round is in [history/ROADMAP_0_7.md](history/ROADMAP_0_7.md) with the seven
  entries that shipped or closed, and the ten still waiting — RM122, RM23, RM16, RM28, RM56, RM65,
  RM66, RM67, RM68, RM84 — became [ROADMAP_0_8.md](ROADMAP_0_8.md), unchanged but for the file they sit
  in. `PROPOSAL_0_7.md` stays beside the other five concluded threads in `docs/proposals/` and is
  marked a record rather than a plan; it no longer wins over anything, because everything it decided
  has landed.

  Every inbound link was retargeted **by item rather than by path** — a link to a deferral that moved
  now resolves in `ROADMAP_0_8.md`, one to an entry that shipped resolves in `ROADMAP_HISTORY.md`, and
  one to the round itself resolves in `history/`. Verified by `test_doc_links.py`, which is the
  authority here rather than a fresh sweep: it exempts a consumer's byte-frozen prose, and **three
  links in an archived report were reverted after being retargeted** — including the `ROADMAP.md#rm89`
  in S35 that the exemption test asserts on, which records where RM89 lived on the day it was written
  and whose current pointer is in the reply above it. Our own replies in that file *are* ours to
  correct and were. Three stale counters in ROADMAP.md were fixed in passing, including the *Active
  items* enumeration, blind for the third time — it read *not one of them is a decision* through the
  three decisions filed beneath it.

- **RM139 — the release gate could not tell a broken compile from a spec that outgrew the old
  compiler.** *(`just-dna-format` + `just-dna-compiler`.)* Filed by running RM126's own gate for real
  at this cut, where it refused the release over `reference_examples/cyp2c9_warfarin_grch37/`: RM70
  put the optional `requires_callable` column on `pharm_variants.csv`, that example uses it, and 0.6.6
  refuses the spec under `extra="forbid"`. Nothing had failed — the previous release cannot produce a
  before state for it, so no like-for-like comparison exists — and this recurs in **every minor that
  adds an authored column and exercises it in the corpus**, as it does for any example newer than the
  last release. The gate read *one side only* as *a compile failed* and the tag had to be waved
  through by hand.

  **The two directions are facts about different releases, and the gate now says which.** A module in
  the BEFORE tree and not the AFTER one is a regression **in the release being cut**: still fatal,
  unconditionally, and now carrying the compiler's own errors, which `build_outputs` had been logging
  and throwing away. A module in the AFTER tree and not the BEFORE one fails until the published
  record's new `ReleaseRecord.unmeasured` list names it. `SweepMeasurement` splits `unmeasured` into
  `only_before`/`only_after` and keeps the union as a derived property; the sweep's JSON keeps its
  original `unmeasured` key and adds the two halves beside it, so a release script piping to `jq` is
  unaffected. `UNMEASURED_MODULE_PHRASE` still appears in both messages for the same reason.

  **`unmeasured` is a denominator, not the per-module escape hatch the roadmap entry refused**, and
  the difference is that the gate checks an **equality** against what it could not measure rather than
  a membership test: a module measured on both sides cannot be excused by listing it (that is reported
  as a note), a regression cannot be excused by listing it, `as_record` refuses to mint a record over
  one, and a movement on a measured module gates however the list reads. `as_record` fills the field
  from the measurement, so the exclusion is forced into the record the same way `declared` is —
  extending the existing mechanism, not adding a second kind of gate input. Records written before the
  field read `[]`, which is their correct claim; the 0.7.0 record is backfilled with the module its own
  `evidence` sentence already named.

  **Consumers:** `ReleaseRecord` gains one optional list field, minor-legal under Principle 3 and read
  by nothing that does not want it. `build_outputs` now returns `(outputs, failures)` — a compiler
  internal, but a release script calling it directly must unpack.

  Re-measured end to end rather than asserted: the 0.6.6 → 0.7.0 sweep was re-run over all sixteen
  reference examples with 0.6.6 installed in an isolated environment — fifteen measured, one refused on
  `requires_callable]: Extra inputs are not permitted`, gate exit 0 against the shipped record where
  the cut had needed a human to read past it, and exit 1 naming the module when one is removed from the
  spec root instead.

- **RM134 § B — the concordance check takes a second authority, and the record has a producer.**
  *(`just-dna-enricher`, plus one optional `module_spec.yaml` field in `just-dna-format` and its
  one-line passthrough in `just-dna-compiler`.)* PubMind (RM134 § A shipped its snapshot) joins ClinVar
  as an annotation authority, and `clinical.clin_sig_concordance` becomes an N-authority check whose
  seam is RM130's `classify_concordance` — a pure function that already knew nothing about ClinVar.
  `pubmind.py` is the runtime reader over the snapshot, duckdb beside the polars builder; there is
  deliberately no `lookup_loci` on it, because PubMind's coordinates are back-mappings of extracted
  text and nothing it produces may enter `resolution.csv`.

  **The three-way check subsumes the two-way rather than running beside it.** With no PubMind snapshot
  that authority's call reads `unchecked` on every subject, and the degenerate case is exactly the
  ClinVar-only finding: the same subjects are contested, the same conflicts are logged in the same
  pinned words, and no author meets one disagreement twice. What changes is what the record withholds
  — `authority_concordance` reads `unchecked` rather than `single`, because one authority speaking
  while another was never asked is not corroboration and must not be recorded as any.

  **The record now has a caller.** RM130 shipped the models, the classifier and the writer with
  nothing producing them; `enrich()` builds the record from the comparison it already ran — never a
  second pass over the snapshot — and commits both tables at the gate, after every strict refusal, so
  a refused run leaves none behind. A module holding a ClinVar snapshot therefore carries the record
  even when nothing is contested: the empty pair is the claim *we asked, and nothing here is
  contested*, which is a different claim from the absent pair a run with no authority to ask leaves.

  **The tautology is decided per leg.** Where a module's `clin_sig` was drafted out of a snapshot it
  would be compared against and has not moved since, that authority is not consulted at all and states
  nothing — a call recorded there would agree with the module by construction. But the *check* is
  skipped only when every leg is hollow or unasked: a module drafted from ClinVar still gets a real
  comparison out of PubMind, and throwing that away to suppress the hollow half is the error
  `enrich_pgx` already made once. `is_tautological_leg` states the conjunction once and reads the
  checked column out of `DRAFT_PROJECTIONS`, so § C's drafter needs no edit here.

  **Several PVIDs over one allele fold to one call, camp guard first.** PubMind consolidates on
  extracted text, so one allele carries several records whose verdicts disagree — 35,742 disagreeing
  keys in the measured file. Where they straddle the pathogenic/benign line the answer is
  `conflicting`, the vocabulary's own word for it, in the camp that opposes nothing; folding by
  severity there would silently answer `pathogenic`, a winner picked by an ordering nobody defined.
  Within one camp the fold is the shared normalizer's own severity rule, the same one that resolves a
  composite token. Confidence is withheld unless exactly one record stands behind the call, and the
  multiplicity is counted on the record rather than discarded.

  **`authority_precedence:` is recorded and computed with by nothing.** One optional ordered list in
  `module_spec.yaml`, beside `weighting:`/`authorship:`, saying whose call the curator weighted while
  deciding — machine-readable so a consumer can see the stance, and read by no tier. Two modules
  differing only in it compile to byte-identical parquets with the same `content_signature` and the
  same `artifact.digest`, which is the property the tests assert rather than a round trip of the
  value. **Nothing resolves a split**: no `majority`, no consensus call, no resolved winner, because
  choosing between a declared order and a majority needs a weighting model this workspace has
  declined to invent three times.

  **Warning-tier in both modes, escalating in neither** (`@clinsig-never-escalates`), with more force
  at two authorities than at one: a disagreement with a literature miner's aggregate is a statement
  about that extraction's limits at least as often as about the module, the measured corpus join
  agreed 62 % of the time, and `discordant` is a fact about the field rather than a defect in the
  module. A run that found nothing contested reports no zero, and a run that could not put the
  question writes nothing at all.

- **RM85 — a recorded release, compared against the one its source publishes now.**
  *(`just-dna-enricher`, plus one `VALID_VERIFICATION_CHECKS` member in `just-dna-format`.)*
  `SourceRow.dataset` has recorded which release a module's rows came from since RM4, and two things
  read it — the tautology skip, and `withdraw_stale_dataset` when a module ends up mixing two. Neither
  answered *"ClinVar has published since you drafted this"*, which is the actual trigger for a
  source-refresh pass, so an author who had forgotten and a curator who inherited the module were both
  on their own. `currency.check_dataset_currency` is that comparison, run at the end of `enrich()`,
  attested as `dataset_currency`, switched by `--verify-datasets/--no-verify-datasets`.

  **A comparison, not a column.** The column-shaped repair — a field saying what this module was made
  from and what would age it — was refused one table over in RM71 for restating `dataset` and then
  rotting where `dataset` is maintained. This reads `sources.csv` and writes nothing at all; repairing
  a stale label is a re-draft, which is an author's decision and a different command.

  **Three states, and the third is the item.** `behind` is `True` (the source has published since, with
  both labels named), `False` (still current) or `None` — nobody could ask. `--offline` is where that
  bites: an offline run makes no request, so every recorded release is `unchecked`, never *up to date*.
  `subjects` counts the legs asked **and** answered comparably, an unaskable source is named in the
  record's `detail` rather than counted, and with no leg settled the pass records a skip rather than
  `ran(0, 0)`. Comparability is a withhold of its own: `clinvar_dataset_label`'s digest form and its
  stated-date form name one release space in two spellings, so a digest against a date is
  *uncomparable*, not behind.

  **Severity follows the mode, over the superseded set alone.** `strict` refuses on a release the
  source has moved past and never on an unchecked one — escalating an unreachable source would make
  `--offline --strict` impossible forever over something no author can edit, which is the
  `unreachable_rsids` rule.

  **One probe ships: ClinVar.** It is the only source this tier can ask for a release label in the
  namespace it already records — the live VCF's `##fileDate=`, read through the same function
  `clinvar_build` uses on a downloaded file, because two spellings of one label would not fail, they
  would simply never match. The stream is abandoned after 256 kB rather than sending a `Range` header a
  server may ignore. Every other source reports `unsupported`, and `PROBE_SOURCES` is derived from the
  registry rather than restated beside it.

  It is **`--rederive`'s cheap neighbour** — the same *has the world moved* question asked about the
  release label instead of the rows, at one request per source — so ENRICHER § `rederive` now says to
  put it first. And it cannot agree with itself: the rows compared are the ones on disk before this
  run's commit, and the licence rows `enrich()` writes are at the `resolution` layer with no `dataset`
  at all.

- **RM130 — a contested clinical call now has a name to act on, and a key that survives five
  authorities.** *(`just-dna-format` + `just-dna-compiler` + `just-dna-enricher`; two new optional
  derived tables, three new closed vocabularies, one new warning code.)* The ClinVar cross-check
  reported *twenty findings of 141,616 subjects* and kept none of the twenty: they reached a logger
  and nothing else, so an author could read the number and not act on it. `clin_sig_concordance.csv`
  is those subjects, named and joinable, keyed `(variant_key, genotype)` — genotype because the
  comparison is of an authored call for a genotype, and a table keyed on the variant alone collapses
  two authored calls that disagree with the archive differently. Beside it
  `clin_sig_authority_calls.csv` carries what each authority actually said, keyed
  `(variant_key, genotype, authority)`.

  **The shape is RM134's, not the one RM130 first decided, and the swap is the interesting part.** The
  original record carried "the authored value, the source's value" and named its authority in a
  *field* — `ClinSigConflict.clinvar` — which would have cost a key change or a retype the moment a
  second archive arrived, one item later in this same release. P3 reserves both for a major. So the
  parent row carries an agreement *state* instead: `authority_concordance`
  (`concordant`/`discordant`/`single`/`none`/`unchecked`) and `authored_position`
  (`matches_all`/`matches_some`/`matches_none`/`absent`/`unchecked`), two orthogonal closed
  vocabularies that are five members at two authorities and five at five. A single vocabulary was
  drafted and failed a stress test at five sources because its members named the authority inside
  themselves; the root cause was one field carrying two axes, which is the Principle 5 anti-pattern
  and the combinatorial growth was its symptom.

  **Nothing resolves a split.** With five authorities in a two-against-three disagreement, precedence
  names one winner and majority names another, and choosing needs a weighting model this workspace has
  declined to invent three times. There is no `majority` column, no consensus call and no resolved
  winner anywhere in the tables or the manifest block. Confidence is likewise not normalized across
  authorities — a gold-star count and a literature miner's evidence-depth count are different
  instruments — so the detail row carries the published value with `confidence_unit` beside it, and the
  model refuses a magnitude with no instrument named.

  **A conflict is a question and an `overrides.csv` row is the answer.** The record joins the overlay's
  covered set, taking it from seven to eight, and it is in for a different reason from the other seven:
  not because it carries curation to lose — it carries none and is rewritten whole on every run — but
  because answering a contested subject is what an overlay row *is*. The paired detail table stays out
  by name: the author answers the question and does not get to rewrite what an archive published. The
  table's documentation and the new `clin_sig_concordance_contested` warning both name `overrides.csv`
  and never `provenance.json`'s `outranks`, steering new authors onto the side of the succession that
  survives 1.0. The warning is **actionable rather than carried**, unlike its neighbour
  `verification_findings_recorded`, because it counts the post-overlay rows — so writing the answer
  clears the finding, and `overlay_rows_suppressed` reports the removal so nothing goes quiet. It never
  escalates under `--strict`, for the reason the check beneath it does not: half the time the archive
  is the stale side, and escalating would have this format arbitrate a clinical dispute.

  Two smaller things travelled with it. `_CLIN_SIG_CAMP` moved out of `clinical.py` into the new
  `concordance.py`, because the record and the two-way check must draw the opposed-versus-differing
  line in one place — two maps for one distinction is how a drift in our own code comes to read as a
  disagreement between two archives. And an honest note that came out of building it: at a single
  authority every reported conflict is `opposed` by construction, since the check only fires where both
  sides are opinionated and `pathogenic`/`benign` are the only opinionated camps, so
  `_clin_sig_detail`'s differing-but-not-opposed group has no producer today. It gets one as soon as two
  authorities can disagree with each other while neither contradicts the module, which is what the
  record is shaped for.

- **RM131 — the warnings channel says what each finding is, and whether an author can clear it.**
  *(`just-dna-format` + `just-dna-compiler`, plus the deprecated resolver in `just-dna-enricher`; a
  structure change to a surface that already ships.)* `ValidationResult`, `ClosureResult` and
  `CompilationResult` all carried `warnings: list[str]` with no code, no count and no way to tell a
  finding an author *can* clear from one they cannot. A compile of a 190-row module returned roughly
  **14 kB** of prose, and `strict=false` does not help — it changes what counts as an *error*, not how
  much the channel carries — while every document on both sides of this seam tells an author that
  warnings on a green run are the real output.

  **The answer was already being computed and spent on severity alone.** `_BLAME_TIER`/`_BLAME_ROW` is
  literally *whose limit this is*, and its own comment says "blame decides severity and nothing else";
  `_closure_warning` reaches the same distinction from the other end and says so in prose.

  **Two derived fields beside `warnings`, which is unchanged down to the byte.**
  `compilation.carried` is the subset **no edit to the spec directory can clear** — a limit of this
  tier or a fact of a source — so a consumer subtracts it to get the actionable set;
  `compilation.warnings_summary` is `{code: count}` over `vocab.VALID_WARNING_CODES`, with the values
  summing to `len(warnings)` so the digest accounts for the whole channel rather than the part somebody
  remembered to key. Both ship on all three result types too, on every path including a failed compile.
  `manifest.json` sits outside `artifact.digest` (a Merkle root over the parquet `FileEntry` list, and
  that is the mechanism — not a slot in `ARTIFACT_PARQUETS`, which name-sorts), so neither moved a hash
  on any published module.

  **A code names the finding, never the emission site**, because a code derived from where the function
  lives is renamed by a refactor and a published key is permanent within a major (P3/P6). One code
  carries one remediation: two sentences cleared by the same edit share a code and the sentence says
  which cell (the weight-sign pair, the five orphan fact tables), two cleared differently do not.
  Sixty-eight members, nine of them carried.

  **The audit was the real cost and was done once.** Every emission site across three tiers now names
  a code — the ~29 named-list appends in `compiler.py`, the `findings`/`messages` collectors a survey
  of `.append` cannot see, the two `.extend` sites that reach into `binning.measurement_shape_warnings`
  and `deprecation_warnings`, `validate_bins`, `overrides.apply_overrides`, `compiler/resolution.py`,
  and the deprecated DuckDB resolver in `enricher/resolver.py`, whose warnings land in the same
  `manifest.compilation.warnings` as everything else. The three sites that *reformat* a message from
  another tier go through `findings.restate`, which is the one operation that carries a code across a
  rewrite; every other string operation on a finding returns plain prose by construction.

  **`classify` has three answers and no flag: derive, withhold, refuse.** A `warnings_summary` with a
  catch-all key is the rejected repair wearing a different hat — it silently omits what nobody
  classified, and the reader takes the digest as complete. But refusing outright was wrong in the other
  direction: `CompilationResult(warnings=["prose"])` has been legal since 0.6, so an unclassified
  channel now **withholds** (an empty pair, which reads as *not classified* rather than as
  *complete and short*), and only a *part*-classified channel — which no legitimate caller can produce
  — raises. That also keeps a raise out of `_build_manifest`, which runs after every parquet is on
  disk, where it would have left an output directory with no `manifest.json` beside them. The published
  contract is therefore *either empty or accounting for the whole channel*, stated in both field
  descriptions; a supplied pair is checked against the channel, since a wrong claim is worse than a
  withheld one.

  **The guards are equalities over walked sets, and one of them was a hole until a mutation found it.**
  `test_warning_codes.py` asserts the emission sites against the vocabulary in both directions (a code
  with no emitter and an emitter with no code both fail), and the corpus half runs every reference
  example through both entry points, which is what catches a message that lost its code on the way
  rather than at its site. The receiver names are themselves a registry now: a hand-typed list omitted
  `lines`, which `_carried_vrs_warnings` collects into, and stripping that site's wrapper passed the
  guard — so the declared set is checked for equality against the receivers actually derived from the
  source, with the channel/refusal split declared beside it because one builder feeds both.

  **The transport stays `list[str]`.** `findings.CodedWarning` is a `str` subclass, so every `.extend`,
  every `if w not in all_warnings` de-duplication and every consumer already grepping a phrase keeps
  working untouched — including the de-dup-by-message that lets a check run in both `validate_spec` and
  `compile_module` and publish one line. Pydantic flattens the subclass at a model boundary, which is
  right for the published surface and fatal for a caller that keeps building on it, so `compile_module`
  and `close_module` seed from an internal `_validate_spec` that hands the classified list back beside
  the result. That trap is pinned by a test rather than left in a comment.

  **The suppression record rides the same channel (RM124 × RM131).** A row removed by a `suppress` was
  invisible in the build product — absent, with no trace of why — so the overlay now says so, one line
  per **reason** with a count, which is what `reason` being a required column buys. Counted over the
  *overlay's* rows and never over the rows removed: after `reverse_module` the derived table is already
  post-overlay, so an effect-based count would say a number on lap 1 and vanish on lap 2, moving a
  published field between a module and its own round trip. Proved against the real
  compile → reverse → compile path, not argued.

  **RM126's sweep gets the discriminator its own comment promised.** `sweep.compare_module` reports
  `carried_added` beside `actionable_added`, read off the after-manifest's `carried` rather than
  re-derived from prose. `axes["warnings"]` deliberately still fires on any movement — narrowing it
  would make a published axis mean something other than what every record already written claims — and
  a pre-0.7 manifest reports every addition as actionable, the safe direction, since calling an
  unrecorded finding carried would tell a reader that something fixable is not. Both new fields join
  `compilation.warnings` in `EXCLUDED_MANIFEST_FIELDS`, because they are derived from it and move
  exactly when it does.

  **Repairs rejected, recorded so they are not re-proposed:** a plausible code set shipped unattended
  (the container is free, the vocabulary is a one-way door); codes derived from the pinned phrase
  catalogue (partial by construction); codes derived from the emission site (a refactor renames a
  published key); a cap, a truncation or a verbosity flag (all three hide findings, and the author with
  the most warnings most needs the hidden ones); a new metainfo artifact (the channel already ships and
  is outside the digest).

  **Two consequences recorded rather than left to be discovered**, both in COMPILER.md beside the
  catalogue: the code vocabulary is closed, so a consumer pinned to an older `just-dna-format` refuses
  a manifest carrying a code added later — the standing cost of every closed vocabulary on a published
  field here, and "additive" describes the writer; and `carried` holds full message text, which grows
  the channel **1.84× across the reference corpus** (1.96× on `pathogenic_clinvar`). The second is the
  shape the item decided rather than an oversight, and the three cheaper encodings are weighed as
  **RM138** instead of being taken unilaterally. → [COMPILER.md § Warning texts a consumer keys on](COMPILER.md)

- **RM124 — `overrides.csv`, an authored overlay over the derived tables.** A correction to a
  derived row now lives beside the spec rather than inside the file, so `resolution.csv`,
  `frequencies.csv`, `gene_metrics.csv`, `gene_validity.csv`, `clinical_assertions.csv`,
  `literature.csv` and `gwas_effects.csv` become pure build products — `derived = f(source, overlay)`.
  Columns are `table`, `subject`, `member`, `field`, `operation`, `value`, `reason`, `decided_by`,
  `decided_at`, with **`reason` required**: that is what makes the table a record rather than a knob.
  Operations are `update` / `insert` / `suppress`, keyed `(table, subject, member, field)` with **one
  `member` column whose meaning the named table fixes** rather than a per-table key grammar. An empty
  `member` on a grouped table is group-scoped for `update` and refused for the other two. An `insert`
  is written as several rows sharing `(table, subject, member)`, one per field, and lands at the end
  of its subject's group in overlay order, because parquet bytes depend on row order.

  **What it costs an existing module: nothing.** The table is optional, an absent optional table
  contributes nothing to `content_signature`, and a module that carries no overlay carries no
  `overrides.parquet` either, so no published module's identity moves on either axis. (Its slot in
  `ARTIFACT_PARQUETS` is not what protects them: `artifact_digest` name-sorts the listing before
  hashing, so tuple position is invisible to the digest.) The overlay is authored
  input, so when a module carries one it is inside `content_signature` and byte-hashed into
  `manifest.inputs` — editing a correction un-closes a module, which is correct.

  **What it costs a second pass: also nothing, and that is the point.** Merge-not-clobber's *behaviour*
  is unchanged — a re-run still gap-fills rather than re-asking every subject — but a recorded row now
  carries no authored content, so a full re-derivation (`rm` plus a re-run) is free. Every writer of a
  covered table says so in its docstring. `licensing.csv` / `sources.csv` is deliberately outside the
  covered set: it has its own merge path and is the one derived table a human is told to write.

  `reverse_module` emits the post-overlay derived tables **plus** the overlay, so the overlay applies
  twice and the fixed point is checked by test rather than assumed — it holds because all three
  operations are idempotent set operations, which is why there is no `previous_value` column. One
  consequence stated rather than hidden: **no operation reports its own no-op**, because after a
  reverse all three no-ops are true of a healthy module, so a `suppress` with a typo'd subject does
  nothing and cannot warn. Two warnings do exist and are pinned in
  [COMPILER § warning texts](COMPILER.md#warning-texts-a-consumer-keys-on) — an `update` reaching no
  row, and an overlay naming a table the module does not carry.

  `ProvenanceItem.outranks` still stands and the duplication is stated in
  [SCHEMAS](SCHEMAS.md#the-authored-overlay-07-rm124--overridescsv) rather than hidden; the unification
  is **RM135** on the 1.0 tracker, and 0.7 emits no deprecation warning because an author warned off
  `outranks` today has nowhere to go.

  **Cross-repo:** `just-dna-registry` needs `overrides.csv` added to `SPEC_DATA_FILES` /
  `RECOGNIZED_SPEC_FILES`, or the file is dropped on the next re-publish — the way `licensing.csv` was
  lost before their 0.16.2. Recorded in [INTEGRATION_0_6.md](INTEGRATION_0_6.md).

- **RM83 — closed, not shipped.** Dissolved by RM124 rather than argued down: with the corrections in
  the overlay there is nothing inside a sidecar to preserve, so the `--refresh` command it asked for
  has no problem left to solve and the drift detection it wanted falls out of an ordinary
  re-derivation. Its residue shipped as `enrich --rederive`, in RM128's entry below. See
  [ROADMAP_HISTORY](ROADMAP_HISTORY.md#rm83--a-derived-sidecar-can-only-be-refreshed-by-deleting-it-which-discards-the-overrides-it-exists-to-hold).


- **RM128 — an enrichment run is a transaction, and it holds a lock, reports progress, and can
  re-derive.** *(`just-dna-enricher`; no schema, no manifest field, no vocabulary — a new module, three
  keyword arguments and two flags.)* `enrich()` persisted nothing until its tail, so a run killed at
  minute 29 had written **zero bytes**. The obvious repair, checkpointing the table as it goes, trades
  away a property somebody may be relying on — that a refused `strict` run leaves the module exactly as
  it was — and the trade turned out to be unnecessary.

  **Durable staging beside the target, plus an atomic commit at the gate.** Each live link's answer is
  written to `.<name>.staging/answers.csv` beside `resolution.csv` as it arrives; the table itself is
  still written once, at the bottom, by a writer that renames into place. Same-directory staging is the
  correctness condition rather than a convenience: `os.replace` is atomic only within one filesystem,
  so staging beside the target makes a cross-device move structurally impossible instead of merely
  avoided. What is staged is the **raw answer**, never the assembled row — the hosting filter, the
  pseudoautosomal selection, `locus_index` and the minted ids all recompute — so a resumed run
  reproduces the table an uninterrupted one produces, which is the item's P7 obligation and has a test.

  **A refused `strict` run commits nothing**, now as a written promise rather than an accident of
  statement order, asserted on the bytes on disk of a pre-existing table. `--keep-staging` leaves the
  staged answers after a successful commit, for debugging; the default removes them. Not
  mode-conditional: `write` gates the persistence machinery whole, so it means one thing everywhere.

  **`flock` on the spec directory, non-blocking, no lockfile.** Two concurrent runs were
  last-writer-wins over a merge with neither knowing, and a zombie run once overwrote a restored 330-row
  table with 162 rows that then validated, closed and compiled green. A lockfile left by exactly the
  kill this item is about would block every subsequent run, and the staleness rule that would fix it is
  a clock; `flock` dies with the process. A second run refuses with a pinned message. **The degradation
  is documented, not silent** — no `fcntl`, or a filesystem answering `ENOLCK`/`EOPNOTSUPP`, logs that
  the run is not excluded from a concurrent one. `flock` is untested here on the network filesystems a
  consumer may use.

  **`progress: Callable[[int, int], None] | None`, reporting `(done, total)` over SUBJECTS.** The
  incident is an idle timeout — both reported runs died at 1800 s with essentially every variant
  resolved — so the caller needs a keepalive with monotonic progress. That rules out phases (a
  29-minute phase emits nothing) and links (whose total is unknown until resolution finds them). No
  protocol: two integers, no object, no event vocabulary to keep working forever.

  A staged answer is honoured **only if the link that produced it would run this time** — the seeding
  reads the same two booleans that gate the live blocks — so a `--no-gnomad` or `--offline` resume does
  not stamp a row a first run with those flags could never have written.

  **`--rederive` is RM83's residue, and it composes rather than adding machinery.** It re-asks every
  recorded subject and names the ones that came back different — MODULE_LIFECYCLE § 5.1's canary,
  finally performable. `None` means nobody re-derived and `[]` means nothing moved; only a real
  difference prints. **A recorded subject the sources could not be asked about keeps its rows**, or
  re-deriving would be a way to shorten the table — the reported incident wearing a new flag. The
  **A re-derivation resumes only another re-derivation**, because a gap-filling run's staged answers
  are, after its commit, exactly what produced the recorded table — seeding them would compare the
  table against its own provenance and report a clean bill for the subjects being re-checked. The
  honest limit is stated with it: `rm` plus a re-run re-derives just as correctly and reports nothing,
  because it destroys the old values before the fresh ones arrive.


- **RM126 — a release now declares what it changed about compiled output.** Principle 3, as amended
  on 2026-08-21, lets a corrected derivation ship in any release but never *silently*: each release
  declares its corrections, readable offline and without recompiling. No such channel existed, so the
  charter named a surface that was not there. This is the one item of the 0.7 round that was owed
  rather than offered.

  **`just_dna_format.release_records`** carries a static table of per-release records and a pure
  `needs_recompile(compiled_under, current)` over it — pydantic-only work in the tier every consumer
  already has. Five axes per record (`parquet_schema`, `parquet_bytes`, `content_signature`,
  `manifest_fields`, `warnings`), each tri-state, **plus the declared correction-versus-addition
  split** — the half no diff can compute, since only the person who fixed the bug knows whether the
  stored value was *wrong* (`stats.genes`) or merely *absent* (`curator`).

  **Deliberately not a `should_rebuild` verdict.** The same fact costs a registry an immutable PATCH
  and a local cache a free rebuild, so the decision is the consumer's and only the fact is ours. The
  per-axis breakdown stays exposed underneath the declared flag.

  **Intervals compose as a union over `(a, b]`**, walked down each record's `previous` link — linear
  storage rather than O(releases²), *moved-and-moved-back still reads as moved*, and, load-bearing
  rather than incidental, **the interval from a version to itself is empty**. That last property is
  what stops an unattended sweep minting a fresh PATCH every run forever, and a field-keyed or
  latest-known-defect shape would not have it.

  **Unknown is a state, never an empty result.** An interval the installed table does not cover
  answers `None` per axis under Kleene semantics, and so does a downgrade. Without it the surface
  would be worse than nothing, because a consumer would stop recompiling on the strength of a silence.

  **`compilation.warnings` gets its own axis, outside the set that drives a recompile.** It is a
  published manifest field and RM131/RM134 both move that channel in 0.7, so folding it into
  `manifest_fields` would report *a manifest field changed* on essentially every module in a catalogue
  for a reworded message. It cannot join `compiled_at` in the excluded set either, because a **new**
  warning can be a real signal. RM131's `carried` split is the discriminator that will make the two
  decidable; the seam is `sweep.compare_module`, which keeps added and removed warnings apart for it.
  `SpecRow.needs_upgrade` is computed over authored row content and a warning never touches one, so no
  warning change can flip it — verified, not assumed.

  **The roster ships beside the table** (`AUTHORED_ROW_DERIVED_FIELDS`): which manifest fields are pure
  functions of the authored rows, so a consumer can recompute the current answer from stored inputs
  with `spec_tables` and `module_stats` instead of consulting the table at all. **Its boundary is
  conditional and the condition rides on the entry**: `compile_module` re-derives `stats` over the
  survivors only when the symbolic-allele drop removed something, so a module that lost the sole row
  naming a gene legitimately disagrees with a recomputation, permanently. `compilation.dropped_rows`
  (2026-08-24) is what makes that checkable rather than merely stated.

  **`just-dna-compiler sweep`** is the instrument, and it exists so this never becomes the hand-kept
  per-release map everyone agrees it must not be — the defect wearing a public name. It compares two
  trees of compiled output built from **one** spec root, and with `--release` it runs the gate: a
  measured movement that no record declares **fails**, so the measurement forces the declaration. The
  gate belongs to the bump → `uv sync` → tag sequence rather than to the test suite, because it needs
  the previous release installed.

  **Backfilled by measurement, not by memory.** Both shipped records were produced on 2026-08-28 by
  compiling all sixteen `reference_examples/` from one spec root under each *published* 0.6 release.
  `0.6.0 → 0.6.1` moved nothing — recorded as a **measured zero with its denominator**, never silence.
  `0.6.1 → 0.6.6` moved the parquet schema and bytes on 10 of 16 (RM120's `curator` column growing
  `studies.parquet`), a published manifest field on 9 (`stats.genes`/`stats.gene_count` on seven,
  RM121; `literature.quotes_unchecked` on three, RM119) and `content_signature` on **none**. Six moved
  a published, indexed manifest field with *both* hashes byte-identical, which is precisely the case a
  digest comparison, a signature comparison and a `revalidate` all correctly call *no change*. Only
  `0.6.0`, `0.6.1` and `0.6.6` reached PyPI in that line, so those are the only intervals a stored
  artifact can name; everything older stays honestly `unknown`.

  **Scope v1 is compiler-derived outputs, said out loud.** Enricher-side outputs are **unmeasured**,
  which is not the same claim as unchanged. And this coexists with a consumer's own recomputation
  probes rather than replacing them: we state what a release did, they check what a specific stored
  artifact says, and the two fail differently.



- **RM70 — a star-allele module can state CPIC's core assumption.** *(`just-dna-format`; no compiler
  change — the parquet schema and the reverse writer both derive their columns from the model.)*
  `requires_callable` was a
  `VariantRow` column, so `haplotypes.csv`, `pharm_variants.csv` and `diplotypes.csv` had no way to
  record the one thing a consumer most needs before trusting a `*1/*1` result: CPIC assumes a position
  it did not call is reference — literally `requires_callable=false` — and the assumption lived only
  in the upstream's prose. The optional tri-state column now sits on **`HaplotypeRow` and
  `PharmVariantRow`**, the two PGx tables that *name a locus*, so the claim is about a position the
  row itself states.

  **Not on `DiplotypeRow`, and `callable_from` did not travel.** A diplotype names a star-allele pair,
  not a locus; the same column there could only mean "the variants defining these two haplotypes were
  callable", which is a fact about `haplotypes.csv` restated one table over, free to drift the moment
  a definition is edited. `callable_from` stays `VariantRow`-only because the two are different axes —
  one says a proof is required, the other says where the proof lives — and a curator can state the
  first from the source's prose with no basis for the second. Declaring it once in `module_spec.yaml`
  was refused for the reason RM36 and RM32 already paid for: the verdict is per locus, and CYP2D6
  holds a SNP-defined allele beside a structurally-defined one inside one gene.

  `reference_examples/cyp2c9_warfarin_grch37` — the module the gap was found against — now populates
  the column on both tables and exercises all three states. Its `haplotypes.csv` records CPIC's
  assumption verbatim (`false` on both defining SNPs); its `pharm_variants.csv` is keyed on genotype
  and so splits: the reference-homozygote rows require a callability proof, the rows naming an
  alternate allele do not, and the rows whose reference allele the module never resolved are left
  **blank** rather than guessed. That answers the consumer ask for `requires_callable` "populated
  somewhere real, to try the round trip against" on its PGx half. The module was re-closed, so its
  attestation binds the new bytes.

  Optional with respect to every module published before it: `content_signature` normalizes with
  `exclude_none`, so a spec that never writes the column hashes exactly as it did. `artifact.digest`
  does move for any module carrying either table, which P3 says is not by itself a reason to defer.

- **RM133 — the card subtitle gets a home a registry can amend.** *(`just-dna-format`; Principle 4 deliberately untouched — the closure binding is exactly what it was.)*

  **Package: `just-dna-format`.** Additive under Principle 3 — two new constants and one new number, no
  authored field, no schema change, no parquet column, nothing invalidated. Principle 4 is deliberately
  untouched: the closure binding is exactly what it was.

  - **`normalize.PRESENTATION_AUTHORITY_KEYS = frozenset({"short_description"})`** — a second
    registry-owned key family beside `IDENTITY_AUTHORITY_KEYS`, with
    **`PRESENTATION_AUTHORITY_REASONS`** mirroring the identity map. Separate sets because ownership and
    presentation are different reasons for a key to be registry-owned and a consumer may stamp one
    without the other; **one stripper** — `strip_authority_keys` takes either family or their union, so
    there is one path and not two.
  - **`normalize.SHORT_DESCRIPTION_MAX_CHARS = 120`** — the card-subtitle calibration, published here
    rather than guessed at downstream. It **refuses nothing**: no model carries it as a `max_length`,
    `Display.description` stays unbounded on purpose, and absent the key everything behaves as before.
  - **Why this and not a smaller binding.** Rewriting `module.description` moves no `content_signature`,
    no `artifact.digest` and no fact signature, and still drops the closure, because `manifest.inputs`
    covers the raw bytes of `module_spec.yaml`. The binding stays as it is — an attestation answers *is
    this the same document a named person signed off*, and a partition along `content_signature`'s line
    would make a closure transferable across a rename. A `short_description` field on `ModuleInfo` is
    refused for the same reason: every key in the spec is on the un-amendable side.

  **For `just-dna-marketplace` and any other publishing registry — this is the integration note.** Store
  `short_description` in your own record beside the module, never in `module_spec.yaml`. Import the two
  constants from `just_dna_format.normalize` and strip the union before handing a block to our
  validator: `strip_authority_keys(block, IDENTITY_AUTHORITY_KEYS | PRESENTATION_AUTHORITY_KEYS)`. The
  stored bytes then never move, so `manifest.inputs` still matches, `verify_manifest(check_inputs=True)`
  still passes and a closure over those bytes still stands — **your `amend_display` endpoint is not gated
  on us**. Read the ceiling off `SHORT_DESCRIPTION_MAX_CHARS` rather than hardcoding 120; enforcing it is
  yours to do, since we bound nothing. Nothing is retroactive: the seven published modules met every
  requirement that existed and are untouched. On the CLI, `--strip-identity` still means identity alone;
  the second family is `--authority-key short_description`.

- **RM71 — the drafted-genotype worklist is re-requestable from the command that produced it.**
  `draft-panel` leaves `genotype` as the placeholder, correctly, and reports the alleles the author
  must write it from in one uncapped line per open row. That report used to be scoped to the rows a
  single run *added*, so a second run added nothing and therefore said nothing, and the alleles could
  not be asked for again. The worklist now covers **every row in `variants.csv` whose `genotype` is
  still the placeholder** — refused rows were never written and settled rows no longer carry the stub,
  so the earlier narrowing survives on a better basis — and `draft-panel --dry-run` obtains it without
  appending anything, meaning what it means on `draft`. The `state`-placeholder line moves with it,
  because it reads as "these rows *also*". An open row this run holds no record for has its alleles
  **withheld** and is named by gene in one aggregated line rather than guessed at or silently dropped
  from the count; the line says only that nothing this run selected covers them, since the usual causes
  (another gene, a tighter `--clin-sig`/`--min-review-stars`) are not ones the pass establishes. A
  scaffolded template row — the placeholder in `rsid` as well as `genotype` — is not drafting work and
  stays out of both lists. No schema, no cell filled,
  no digest moved. The 0.7 proposal recorded `draft-panel` as *lacking* `--dry-run`; it has had one
  since 0.5.1, so that half of the item was already true and is now pinned by a test over the whole
  drafting family rather than asserted.

- **RM134 § A — the PubMind snapshot, and one significance normalizer.** *(`just-dna-enricher`; nothing in the format or compiler tiers moves and the compile path imports none of it.)*

  **Package: `just-dna-enricher`.** Additive: a new module, a new snapshot kind and two new commands.
  Nothing in the format or compiler tiers moves, no schema field is added, removed, promoted or retyped,
  and the compile path imports none of it. Decided in
  [PROPOSAL_0_7 § RM134](proposals/PROPOSAL_0_7.md); the evidence is
  [PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md).

  - **`clin_sig.normalize_clin_sig` is now the one raw-significance → `VALID_CLIN_SIG` fold**, moved out
    of `clinvar_build._normalize_clin_sig`, and **two defects were fixed on the way out**. Its map keys
    are underscored because that is ClinVar's spelling; PubMind spells the same concepts with spaces, so
    `Uncertain significance` and `Conflicting` both fell through to `other` while ClinVar's
    `Uncertain_significance` and `Conflicting_classifications_of_pathogenicity` mapped correctly — two
    sources that agree, reported as disagreeing. Repaired with a whitespace→underscore step in the
    tokenizer (an identity on every existing key) and a bare `conflicting` key. **No ClinVar answer
    changes**, which is asserted as an equality over the walked map rather than spot-checked. A second
    hand-written map was the rejected repair: the concordance check RM134 § B builds compares two
    *normalized* calls, so a drift between two maps would report a disagreement between our own tables.
  - **A whitespace-only or token-less significance value is now `not_provided`, not `other`.** "The source
    states no classification" and "the source stated something we do not model" are different answers and
    only the second is a disagreement. No ClinVar `CLNSIG` takes that shape, so nothing built to date
    moves.
  - **New: `just-dna-enricher pubmind build`** (`[dev]`, `polars`) — the ANNOVAR-redistributed
    `hg38_pubmind_db.txt.gz` → `data/pubmind.parquet` + `release.json`, byte-reproducible across rebuilds.
    Columns are `chrom, start, ref, alt, pvid, clin_sig, clin_sig_raw, pathogenicity_score, confidence,
    derivation`; the significance names are **unprefixed**, matching the ClinVar snapshot, because one
    column vocabulary across every snapshot is what lets a later check read N authorities with no
    per-source mapping. `pathogenicity_score` is nullable and null means *not computed*, never 0.0;
    `confidence` is PubMind's own 0–3 and is deliberately not normalized against `review_stars`.
  - **Every dropped row is counted, as an equality over a walked registry.**
    `input_rows == record_count + sum(dropped.values())` over `PUBMIND_DROP_REASONS` — `off_target_chrom`,
    `non_acgt`, `ref_equals_alt`, `multi_substitution`, `identical_duplicate`. A codon block differing at
    exactly one base is decomposed onto it (`derivation=codon`); one needing two or three simultaneous
    changes is dropped, because it asserts a change to the protein rather than to a genotypable position.
    Length-changing rows are kept and stamped `derivation=indel`: upstream left-normalization is
    unverified, and a consumer must be able to exclude them without re-deriving why.
  - **A bad cell and a bad row are different outcomes.** A row with no PVID or an unreadable `Start` is
    dropped and counted (`no_pvid`, `unparsable_position`) — the PVID is the record id everything here is
    keyed on, and a null one would have merged distinct records under `identical_duplicate` as well as
    crashing the emit sort. A malformed `pathogenicity_score` or `confidence` withholds *that value* and
    keeps the row, counted in `unparsable_score` / `unparsable_confidence`. `NaN` and `inf` count as
    unparsable rather than being stored (`float()` accepts both), and a non-integral confidence is
    withheld rather than truncated to a count the source never stated.
  - **`download_pubmind_table` raises `PubMindUnavailable`**, a subclass of `PubMindBuildError`, so a
    moved bulk URL surfaces as this tier's type rather than `httpx`'s and one `except` arm covers both an
    outage and a malformed table. The subclass makes a caller's `except` order load-bearing.
  - **A contested coordinate keeps every PVID as its own row.** Consolidation into a PVID is keyed on the
    text the model extracted, never on a coordinate, so one variant fragments into records whose verdicts
    disagree. Collapsing them was rejected: it needs an ordering nobody defined, which is `mode()` over an
    unsorted group. `release.json` records `multi_pvid_keys`, `max_pvids_per_key` and `contested_keys`.
  - **New: `just-dna-enricher pubmind publish`, which refuses and says why.** On the PharmVar precedent,
    with a different reason: PharmVar's bytes arrive under terms that bar passing them on, PubMind's under
    **no stated data terms at all**. The command exists rather than being absent, because a missing command
    reads as an oversight somebody will helpfully add. The refusal text is pinned by a test.
  - **`PUBMIND_TERMS` records `None` on every licence axis**, and the nulls are load-bearing: null means
    *the terms could not be established*. Unknown terms **warn and never gate** — `taints_commercial_use`
    requires `commercial_use is False` — so a module carrying PubMind values compiles, lands `pubmind` in
    `manifest.sources.unknown_terms_sources`, and drives the module-wide verdict to `None`: undetermined,
    never permitted. That is also why `pubmind build` has **no `--use` flag**: `check_declared_use` returns
    a skip for every declaration, so the gate would refuse every build and the flag would do nothing.
  - **New cache: `pubmind/`, `$JUST_DNA_PUBMIND_CACHE`**, with `resolve_pubmind_reference` and
    `default_pubmind_cache_dir` and deliberately **no `ensure_pubmind_snapshot`** — a refused publish means
    no repo to provision from. `cache status` lists it as build-your-own.
  - **Fixed a counted-prose assertion that a correct addition broke.**
    `test_every_resolver_and_default_dir_takes_the_off_switch` asserted `len(named) == 12` with "expected
    six resolvers and six default dirs" in its message, so the seventh snapshot failed it on arithmetic.
    It now asserts an equality between the two walked families keyed by snapshot name, which says
    something the count never did: no resolver is missing its default directory and none is orphaned.

  **Still open, and named rather than implied.** The ANNOVAR-distributed table's data terms are
  unestablished and only CHOP can settle them; the unblock action is to ask WGLab and CHOP's Office of
  Technology Transfer in writing. Whether the indel rows are left-normalized is likewise unestablished,
  which is what `derivation=indel` exists to let a consumer act on.

- **RM134 §§ C and D — drafting from PubMind, and the hint.** *(`just-dna-enricher`; nothing in the format or compiler tiers moves and the compile path imports none of it.)*

  **Package: `just-dna-enricher`.** Additive: one flag and two options on an existing command, one
  option on `hint variant`, a new provider module and a fourth `DRAFT_PROJECTIONS` entry. No schema
  field is added, removed, promoted or retyped, and no published module is invalidated. Decided in
  [PROPOSAL_0_7 § RM134](proposals/PROPOSAL_0_7.md); the evidence is
  [PUBMIND_ASSESSMENT.md](PUBMIND_ASSESSMENT.md).

  - **New: `just-dna-enricher draft-panel --source pubmind`** — a flag on the existing command rather
    than a `draft-pubmind` beside it. The two write the same rows into the same table from the same
    gene argument, so a twin command would carry a second copy of the genotype worklist, the
    placeholder guard, the dedup pass and the refusal summary — the four parts that are hard to get
    right. `pubmind_draft` therefore **imports** the ClinVar provider's machinery, `_open_stubs`
    included: scoping the worklist to `report.added` is the once-only defect RM71 removed in this same
    release, and a second copy of that rule is the one that goes stale. `draft-clinpgx` stays separate
    because it writes *different* tables.
  - **The gene map is ClinVar's own per-record attribution, matched at the exact position.** PubMind
    names no gene, so `--gene BRCA1` needs a gene→locus map, and this repo deliberately holds none —
    the compiler's gene/locus check is chromosome-granular for that reason. Every position ClinVar
    records for the gene is the universe, with **no** clinical or review filter, because filtering the
    map would narrow what PubMind is asked about while looking like a filter on PubMind's calls. A
    min/max span was rejected: it invents a boundary nobody defined and writes a `gene` cell that is a
    false claim wherever two genes overlap. Both snapshots are required and each absence names its own
    switch. The cost is stated rather than counted — **a PubMind verdict at a position ClinVar has no
    record for cannot be reached by gene at all**, and that class is not countable, since attributing
    it to a gene is exactly what there is no map for.
  - **Five withheld classes, each named at draft time, and the accounting is an equality over the
    walked reason set.** `PUBMIND_WITHHELD_REASONS` covers a contested key, a length-changing row, a
    call outside `--clin-sig`, a confidence below `--min-confidence`, and a confidence the source never
    stated — that last one its own class, because `None` is not 0 and reading an unstated confidence as
    0 invents a reading. `candidates == drafted + Σ withheld` holds over the set, and a class that
    withheld nothing reports no zero.
  - **Contestation is decided over every PVID at the key, before either dial runs.** A `--clin-sig` or
    `--min-confidence` applied first would remove the dissenting record and pick the winner exactly as
    the `mode()` this design already refused would; a test constructs a dissenter that either dial
    alone would have hidden. Where the records agree, one row is written and the record count, the
    PVIDs and the best stated confidence stay in the transcription.
  - **Identity is the whole coordinate or nothing**, since the snapshot has no rsID column at all — and
    the row still matches on the same five columns a ClinVar-drafted row does, so a coordinate both
    sources speak about is one row rather than two. No `clinvar`, `pathogenic` or `benign` is folded:
    all three are ClinVar flags by their own field descriptions, and a position appearing in ClinVar's
    gene map says nothing about whether *this allele* is in ClinVar. No `studies.csv` row is drafted —
    the ANNOVAR channel carries no PMID — and the run says so, because that table is mandatory. A
    position two requested genes both claim leaves `gene` **empty**, counted and named: a joined
    `BRCA1, BRCA2` is not a symbol `check-identifiers` resolves, and picking one is the gene model the
    pass went to ClinVar to avoid inventing.
  - **New: `pubmind` in `DRAFT_PROJECTIONS`**, projected onto `clin_sig`, so a module drafted from
    PubMind cannot confirm itself when the concordance check reads the same column (`@draft-digest`).
    Its `identity` is the coordinate and **not** the provider's `match_on`: the source states no
    rs-number, so an rs-number an author adds later is a change to the row's spelling, not to the call.
  - **Unknown terms warn and never gate, and the drafter does not call the acquisition gate.**
    `check_declared_use` decides whether a *fetch* may proceed and skips on unknown terms, which is
    right for a pass that would go and get such data. Nothing is fetched here — there is deliberately
    no `ensure_pubmind_snapshot`, the operator built the snapshot with our own command, and refusing to
    read it would make that command's output a file nothing may consume. The reason is reported in the
    source's own words instead, and the licence row the provider writes carries `None` on every term,
    which does not taint: `taints_commercial_use` requires an explicit `False`. That is § A's finding,
    re-asserted here over the row this provider actually writes rather than trusted from a fixture.
  - **New: `just-dna-enricher hint variant --pubmind-cache`** (§ D) — PubMind's records beside the cell
    an author is about to fill, **never filling it**: `clin_sig` is what the concordance check
    cross-examines, so a hint supplying it from one of the authorities being compared would make the
    check agree with the source it is checking (`@hint-redundancy-bearing`). Three states rather than
    two: no snapshot is *nobody asked* and names `$JUST_DNA_PUBMIND_CACHE`, a snapshot holding nothing
    at the allele is an absence in their corpus, and disagreeing records are all reported with none
    picked. It answers for a coordinate the caller typed as well as one an rsID resolved to, because
    their channel is coordinate-keyed and most of its rows carry no rs-number.
  - **A dial belonging to the other authority is named rather than ignored.** `--min-review-stars` and
    `--max-citations` under `--source pubmind`, and `--min-confidence` under `--source clinvar`, warn
    when set away from their default: a run that honoured neither the flag nor the author's
    expectation is the failure worth reporting before it happens.

- **RM132 — `pharm_variants.csv` can cite the evidence for its own claim.** *(`just-dna-format` +
  `just-dna-compiler` + `just-dna-enricher`; a new optional authored column, additive under Principles
  3 and 8, and no published module is invalidated.)*

  A ClinPGx-drafted module carried **1,482** drug-response rows and had nowhere to ground any of them:
  sixteen model fields, thirteen authored, none a PMID or DOI. `studies.csv` cannot close it, and that
  is structural rather than an oversight — a study row keys on `(variant_key, pmid)` and attaches to
  the **variant**, while a `pharm_variants.csv` row keys on
  `(variant_key, drug, genotype, phenotype_category, annotation_id)`, so one study row would attach
  the paper to every drug, genotype and phenotype category recorded for that variant at once.
  Widening `studies.csv`'s key was refused for the reason RM47 already refused it: it would make a
  study row's subject depend on which table read it. `evidence_level` is not the handle either — it
  points at somebody else's *grading of* the evidence rather than at the evidence — and the licence
  row's `source`/`dataset` state redistribution terms rather than grounding a claim.

  **`PharmVariantRow.pmid`**, optional and free-form under the one grammar `spec.validate_pmid_cell`
  owns, so an author who has met `StudyRow.pmid` or `MeasureBinRow.pmid` learns nothing new. That is
  why a full-cost authored column (P9) is taken here rather than deferred for demand: demand fixes an
  *unfixed* shape, and RM47 fixed this one a release ago for a structurally identical table.

  **`provenance_quote` does not follow, and the release says so rather than leaving it implied.** The
  row cites; `studies.csv` and `literature.csv` describe. That is the line that stops `StudyRow`'s
  whole provenance column set — population, `p_value_num`, `effect_size`, `provenance_quote`,
  `curator` — migrating onto a citing row one column at a time, and a body of clinical claims this
  size is exactly where the question gets asked next.

  **Both literature cross-check sites learned the site in this release**, which is RM47's recorded
  lesson in its own words: a column shipped without them would make every citation from it read as a
  stale orphan in one direction and be invisible in the other. `_cross_check_literature` (with
  `split_cited_literature` and `_check_quote_counter_is_current` beneath it) and the enricher's
  `enrich_literature` both read it, so a pharm-grounded citation is checked for existence and
  identifiers exactly like a study-grounded one — and a module whose only citations are pharm pointers
  is now enriched rather than refused.

  **The roster is derived, so there will not be a fourth round of this.** `_CITING_TABLE_KINDS` is
  every `_TABLE_KINDS` model declaring a `pmid`, and the new public
  `load_citing_rows` / `table_citations` walk it — the pair the enricher reads through, so a second
  copy of the table roster in that tier (the RM40/RM41 shape) is not repeated, and a test walks the
  enricher's own source with `ast` to assert none is kept. `load_binning_rows` / `binning_citations`
  stay and stay narrow: a caller asking for the binning kinds is asking about thresholds, not about
  the citations a module makes. The internal third parameter of `split_cited_literature` is renamed
  `bin_rows` → `kind_rows` to match what it always held.

  **One warning text moved, deliberately**: `literature_row_uncited` now reads *"no study, bin or
  pharm row in this module cites"*. The **code** is the stable handle and is unchanged; the phrase is
  pinned by the suite, which is what makes the rewording a deliberate act rather than a drift.

  Optionality is proved by running it rather than by citing `exclude_none`: a spec carrying no `pmid`
  header hashes to the same `content_signature` as the same spec carrying the header with every cell
  empty, and a filled cell moves it. The round trip is asserted on the `pharm_variants.parquet` bytes
  as well as on both identities.

## 2026-08-24 — twelve consumer items in one pass (S63–S74)

**Packages: `just-dna-format`, `just-dna-compiler`, `just-dna-enricher` — a MINOR, deliberately
left uncut (2026-08-27).** The number is not decided, so nothing here names one: the replies'
markers read `next-minor` and every doc dates a change by its `Sn` rather than by a version that
does not exist yet. Answered is not installable, and here it is not even tagged.
Most of what follows is patch-class legibility, but three changes are each independently additive
and so size the release under P3: `VerificationRecord.producer`, `compilation.dropped_rows`, and
the new public `load_spec`. Legality sizes the release and severity only orders the queue inside
it, so a pass that is mostly warnings still cuts as a minor when one field is new. Two
reporters, twelve items, answered serially. Eight shipped code, four are filed; the counts below are
off the tree rather than remembered.

**Filed:** RM128 (`enrich()`'s lost work), RM130 (a conflict sidecar), RM131 (`warnings` structure),
RM132 (`pharm_variants.csv` citations), RM133 (an amendable card subtitle), plus the `stats` counter
retype queued to the 1.0 tracker.

**The two findings that cost real work:**

- **A sidecar writer that truncates in place leaves a valid short file, and a merge believes it
  (S66).** Nine writers across the enricher and format tiers used `open(path, "w")` + `csv.DictWriter`,
  so a killed process left a table that parses cleanly and is simply shorter. For `resolution.csv`
  that is the worst residue available: the next run reads it back, merges on `subject`, and believes
  it — and the three branches of `enrich()` that deliberately write **no row** for an unanswerable
  subject make "fewer rows" a state the table reaches honestly. The reported incident had a
  client-killed run keep going, reach the write, and replace a restored 330-row table with **162**
  rows, after which the module validated, closed and compiled green. Fixed with
  `layout.atomic_writer`/`atomic_write_text`. **Three writers were reported and nine were routed** —
  the guard walks the set with an AST check and asserts an equality, and was watched failing on
  pre-fix source first.
- **The better-resolved module was the loud one (S67).** `_verify_vrs_ids` emitted one warning per
  allele where `_vrs_coverage` aggregates the same fact, and which path an allele took was decided by
  whether the enricher happened to mint an id for it. Noise ran *inversely* to how well-resolved a
  module was: 80 of a 101-row module's 85 warnings, with the three findings its author could act on at
  positions 83–85, against a 57,595-row module producing one line. The governing rule was already in
  the file — *a finding no authored edit could clear is not a `strict` matter* — spent on severity
  alone.

**Also shipped:** field descriptions on the three `ModuleInfo` fields that had none, plus a guard
asserting every authored field across 28 models carries one (S63). `VerificationRecord.producer`, so
a merge stops restamping records it did not produce, with the document-level field's own description
corrected because it *was* the false claim (S71/RM129). The `panel:` deprecation gated on its
replacement existing and no longer claiming *"nothing else is lost"* — both halves, since gating alone
leaves the false clause standing (S69). A `detail` on the clin-sig record and a warning when any check
reports findings; nothing read `VerificationRecord.findings` at all (S70). `row_count`, `table_rows`
documented, and a composite-`gene` warning (S72). `compilation.dropped_rows`, closing the residue a
consumer's recomputation guard could not see (S65). Public `load_spec`, ending a private-symbol reach
the enricher itself was making (S74).

**Two answers are the deliverable and shipped no code.** S64 asked us to justify the attestation
binding or split it along `content_signature`'s line — the split is refused because that line excludes
**name, version and namespace**, so a binding drawn there makes a closure **transferable across a
rename**; and the route that actually unblocks the registry is registry-owned metadata
(`IDENTITY_AUTHORITY_KEYS`' shape), which means their endpoint was never gated on us. S73 asked which
provenance model `pharm_variants.csv` was meant to use, and the tree had answered it a release earlier
under a rule nobody had stated generally: **a row cites when its claim is finer-grained than
`studies.csv`' key.**

**A 26-finding dogfooding note had arrived in `ROADMAP.md` rather than the inbox**, where the ledger
cannot see it. Eight of its findings had `Sn` twins; the other eight are dispositioned in place — one
(D17) did not reproduce, one (D11) is our own documented policy, three went to the idea-book with the
cheap half separated from the design half, and one is cross-repo.

Suite 2881 → 2916 (+8 skipped), green throughout; `ruff check` clean.

## 2026-08-21 — the Constitution says rules only, and gained three (RM127 closed, RM126 → 0.7)

**Documentation only; no package changed.** [S62](CONSUMER_SUGGESTIONS_HISTORY.md)'s finding was that a
*corrected derivation* — an existing published field whose derivation changes, so the same spec yields
a different value — is in none of the three sizing rows, and that the safety argument used to clear it
(*`content_signature` is unchanged, measured*) is **incapable of failing**, because `stats` sits outside
the signature by design. A check that cannot fail read as a pass (`@tautology-zero`), one level up from
where RM123 caught the same shape the same week.

**Principle 3 gains two rules.** *Release class and artifact staleness are different axes* — a corrected
derivation is a bug fix, so it **may ship in any release**, since deferring it to a minor means
knowingly serving a wrong value meanwhile; what it may not do is ship **silently**. And *authored
identity is not the sizing test*, which disarms the clause that sized RM121.

**The charter is now rules only, by its own header item**, and came out **11.5% smaller (17,239 →
15,263 bytes) while gaining three rules.** Reasoning, evidence, open questions, superseded states and
rhetoric are banned from it, along with any outward reference beyond a published version a rule turns
on — the old phrasing said the file *"points to no other document"* as a description and `the 0.4.1
plan` drifted in anyway, so it is now an instruction. The four existing amendment entries moved
**verbatim** to the new [CONSTITUTION_AMENDMENTS_HISTORY.md](CONSTITUTION_AMENDMENTS_HISTORY.md), which
may cite `RMn` and consumer reports freely.

**Principle 9 exists because the audit caught a rule about to be deleted.** The cost-by-layer pricing —
parquet approximately free, derived CSV half, authored schema full — was stated *only* inside an
amendment entry, and is cited by CLAUDE.md's coding standards. Moving the amendments out wholesale
would have silently removed it, so it was promoted to a numbered principle instead.

**[RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one)
is closed** — filed, rewritten and answered inside one pass.
**[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)
moves to 0.7 as owed rather than deferred**: the amendment obliges a release to declare its
corrections, and that channel does not exist yet, so the charter currently names a surface that is not
there. Two axes — `output_differs` measured by a previous-tag sweep, correction-versus-addition
declared — with a gate that fails a release whose measured change carries no declaration.

## 2026-08-21 — a patch changed a parquet schema, and nothing could say so (S62, RM126, RM127)

**Nothing shipped; two items filed.** A new consumer, **just-dna-registry**, adopted
`0.6.1 → 0.6.6` and ran the catalog sweep whose job is to find published artifacts that should be
recompiled. It correctly reported nothing to do, at all three layers, while `manifest.stats.genes` —
which feeds their gene facet — sat stale on every star-allele and copy-number module they publish.

**Measured, and wider than the report.** All sixteen `reference_examples/` compiled under `v0.6.1`
in a detached worktree and again under `0.6.6`, spec inputs byte-identical across the interval, which
is entirely patch releases: **16/16 changed a published manifest field, 10/16 moved `artifact.digest`,
0/16 moved `content_signature`.** The digest movement is `studies.parquet` +257 bytes on each of the
ten — **RM120's `curator` column, first present in `v0.6.5`.** So the *parquet schema* moved across a
patch interval, which the reporter had not seen; they reported changed manifest fields.

Authored identity held on all sixteen, which is the charter working: an unset optional column is
omitted from `content_signature`. **The sharpest number is the one that took a recount: six of the
sixteen changed a published, indexed manifest field with *both* hashes byte-identical** — `apoe_epsilon`
went `genes: []` → `["APOE"]` at the same `artifact.digest` and the same `content_signature`.
(`stats.genes` moved on seven modules; an earlier draft of this entry said eight.) That is precisely why nothing can see this — a digest comparison, a
signature comparison and `revalidate` are each correct to report no change while an indexed field goes
stale. **[RM126](ROADMAP_HISTORY.md#rm126--nothing-tells-a-consumer-what-a-release-changed-about-compiled-output)**
is the missing third axis, asked for as an interval-keyed declaration with the axes separated,
explicitly not a `should_rebuild` verdict, and with unknown-interval as a *state* rather than an empty
result. The guard it needs is a measurement rather than a hand-kept map, and the sweep above is its
prototype.

**[RM127](ROADMAP_HISTORY.md#rm127--a-corrected-derivation-has-no-release-class-and-the-version-number-is-the-wrong-place-to-carry-one) was filed and rewritten the same
day, and the withdrawal is the useful part.** It first read *the release table and the practice
disagree*, indicting `curator`'s patch. Withdrawn: `curator` is additive, no published module can carry
it, **no stored value became wrong**, so a patch is defensible and the table is merely strict. The
defect is RM121 alone, and its change class is not in the taxonomy — an existing published field whose
*derivation was corrected*. **Why it read as safe is the keeper:** the only test applied was *does
authored identity move*, and `stats` sits outside `content_signature` **by design**, so that test
cannot fail there. A tautology read as a pass (`@tautology-zero`), one level up from where RM123 caught
the same shape that week. The structural edge — a field outside identity is one nothing can see move,
so **the cheapest changes have no detection channel**: six of sixteen examples changed a published
indexed field with both hashes byte-identical. And since a corrected derivation is a **bug fix**,
deferring it to a minor means serving a wrong value meanwhile — so the release number cannot carry
staleness at all, and the two axes separate rather than reconcile.

**Not an instance, and separated deliberately:** RM106's warning de-duplication. The release table
already sizes a warning or a count as patch-level legibility, so `compilation.warnings` was never
promised stability across a patch. It is the argument *for* the reporter's axis decomposition — warning
text is patch-legal and a column is not, so one "did the output change" bit would have been useless.

**Scope of the negative:** the sweep is an offline compile over sixteen specs. Enricher-side outputs
were not compared across the interval, so `verification.json` and the documents RM123 touched are
unmeasured rather than unchanged.

## 2026-08-21 — the triage loop's threshold counter went blind for the second time

**Documentation only; no package changed.** The [triage loop](CONSUMER_TRIAGE_LOOP.md) § 4 counters
grep `ROADMAP.md` for open items to decide when to ask the user whether the next minor should start.
The 2026-08-21 decision round rewrote all four open items' status lines to lead with what had just
been decided, which pushed the release-class phrase out of the slot the grep reads and wrapped one of
them across a line. **The count read zero with four grounded items in the file** — the direction that
matters, because a zero reads as an all-clear.

This is the counter's **second** failure: the first counted a literal `**0.6**` and kept counting it
after 0.6 shipped, fixed by counting the idiom instead. The idiom then drifted. The durable half of
the repair is that the release-class token is now named as a **fixed field** in
[ROADMAP § Active items](ROADMAP.md#active-items) — verbatim, on one line, with everything else the
status wants to say after it — so the rule sits where a status line is *written* rather than only in
the file that reads it. The incident is in [CONSUMER_TRIAGE_LOOP § 6](CONSUMER_TRIAGE_LOOP.md#6-gotchas-found-while-building-this).
A phrase a tool greps is an API whether or not the tool belongs to a consumer (`@warning-text-is-api`).

Also: the CHANGELOG's `(latest)` marker had stayed on the second entry when the decision round
prepended a new one, against this file's own newest-first rule. Moved — **and then it went stale a
second time within the same pass**, when this entry was prepended above the one that had just been
corrected. That is twice in two prepends. The marker is a *derived* fact — "the topmost entry in a
newest-first file" — restated by hand, which is the exact pattern the RM104–RM111 batch named as the
thing worth carrying out of it, and the file's preamble already says *Newest first*. Surfaced rather
than acted on, because retiring a convention across every heading is a bigger call than this pass:
the next person to trip on it has the evidence to delete the marker outright.

## 2026-08-21 — just-dna-lite's consumer-side changes from the just-module-creator hand-off

**Consumer-side only; nothing in this repo changed.** Recorded because the working agreement asks
for cross-repo integration changes, and because the agents most affected are the hand-off's own
authors — they asked just-dna-lite for ~60 reads and this is what the first tranche did. Their
document lives at `just-dna-lite/docs/CONSUMER_HANDOFF_from_just-module-creator.md`; the reply, with
a verdict per item, is at `just-dna-lite/docs/reviews/consumer-handoff-triage.md`.

**A correction to what a consumer believed about the published corpus.** Both that repo's CLAUDE.md
and the hand-off assumed no module on HuggingFace publishes a `manifest.json` — CLAUDE.md said "every
module on HuggingFace today" and the hand-off called the logo fallback "dead code in production" on
the same premise. Measured 2026-08-21 against `just-dna-seq/annotators`: **all ten modules publish
one.** Attestation (INTEGRATION_0_6 § 2.8) is therefore the *normal* discovery path there and probing
is the exception. Checked for the failure that implies — a file present at the path but absent from
`artifact.files` is now dropped where it used to be probed and found — and the attested set matches
what is present on all ten, so no side table was lost.

**RM43's status was stale downstream by two releases.** just-dna-lite's docs still said the
`pharm_variants` coordinate fill "waits on RM43", and two comments in its annotation engine asserted
that the compiler applies `resolution.csv` to `weights.parquet` alone. Verified against installed
compiler 0.6.1 (`compiler.py:499`) and corrected. Consequence worth knowing if you maintain a similar
consumer: **classify a lead table by the values it holds, not by its family name.** Both generations
are live — that repo's shipped `pharmgkb` is a 0.5 artifact measuring 0 of 1482 rows placed, while a
0.6 recompile of the same spec qualifies for a position join — so a value probe routes both correctly
and no `positional_rows` gate is needed in the join path.

**A phase asymmetry that is a consumer bug, not a format one, and is now reported rather than
silent.** A VCF reader that sorts a genotype (as that repo's does) cannot match an authored genotype
held in homolog order, in either ordering. Sorting the *module* side is not the fix — it folds `A|G`
and `G|A` into one key and manufactures a match the module never stated — so the module side still
never sorts and the unmatchable rows are now counted and logged before normalization strips the `|`
that reveals them. Nothing here needs to change; noted so another consumer does not "fix" it by
sorting.

**Two consumer-side reads that now use this repo's own constants rather than restating them.**
`README_CANDIDATES` reached that repo's HuggingFace publisher allowlist, which had omitted it — so
`manifest.readme` attested a file the upload never sent, and `verify_manifest(check_readme=True)`
passed anyway because absent is not a failure there. And discovery now keeps `identity.version`,
`artifact.digest` and the `weighting` block from a remote manifest it was already fetching and
validating; before, every remotely discovered module reported no provenance at all. All three stay
tri-state.

**Filed separately in [ROADMAP.md](ROADMAP.md):** `manifest.stats.genes` is derived from
`variants.csv` alone, so a module whose gene is stated only in a PGx or binning table publishes
`gene_count: 0` and cannot be found by gene. Originally measured by just-module-creator; relayed
because neither consumer owns `variant_stats`.

## 2026-08-21 — a lookup finding that contradicted the payload carrying it (S61, RM125)

**Cut as 0.6.6** across all three packages and tagged `v0.6.6` on 2026-08-21; this entry read "still
uncut" until the tag landed the same day. It joins the two rounds below rather than taking a number of
its own. Tagged is not published — `uv publish` is a separate step and the maintainer's. `just-dna-enricher`
only — no authored schema, no parquet, no manifest field, and advisory findings are written nowhere, so
no digest and no signature moves. A **patch**. Publishing stays the maintainer's step.

**`lookup_variant` could return a coordinate and deny it in the same breath.** `lookup_variant(rsid=
"rs4988235")` came back with `2:135851076` in `loci` and, beside it, *"rs4988235: not in the injected
Ensembl snapshot, position remains unset"*. The cache link emits that line and the live link fills the
coordinate a few lines later; nothing revisited it. Reported by `just-module-creator`, whose reader of
this surface is an agent under a standing instruction to trust findings over bare values — so the two
halves of one response disagree about whether the lookup succeeded, and the durable cost is that a
finding contradicting the data teaches the reader to discount findings.

**The fix is the three-valued rule applied to a sentence rather than a cell.** At the moment the cache
link speaks, whether the position remains unset is neither true nor false but *unknown* — a leg that
has not run may still answer — so the link now reports only what it searched and withholds the rest.
`lookup_variant`, the one caller that sees both halves, states `"{rsid}: position remains unset"` once
at the end when nothing placed the variant. It is guarded on there being an rsID at all: a position-only
lookup fills `rsid_candidates` and never `loci`, and an unguarded closing line would tell a caller its
own supplied position was unset. The snapshot miss stays on the record, which the reporter asked for —
knowing a local cache is incomplete is what tells an author whether to warm it.

**The ClinVar twin had the same defect and an older one.** `clinvar.lookup_loci` is documented as
signature-identical to `resolver.lookup_loci` ("one implementation, no drift") and still said *"not
found in ClinVar, position remains unset"* — speaking for the source, which is exactly what the Ensembl
half was corrected out of in 0.5. It is reachable in the same call (the cache loop breaks only on a
hit), so a real run produced **two** false claims where the report scoped one. Both links now say *"not
in the injected `<source>` snapshot"*.

**Message texts changed, and they are an API.** The two snapshot-miss strings lost their trailing
clause and the ClinVar one was reworded; `"{rsid}: position remains unset"` is now its own finding. A
consumer grepping the old composite phrase should grep the two new ones. `SYMPTOMS.md` in the authoring
skill and `ENRICHER.md` are updated. `enrich()` is unaffected — it discards both links' warning lists,
so `lookup_variant` was the only reader either sentence ever had.

**Why a green suite held it:** neither phrase was pinned by a test, and every existing `lookup_variant`
test passed an **empty** cache directory, so no snapshot was located and the per-rsID miss line was
never emitted. Six tests now cover it against a populated snapshot that simply lacks the rsID — the
reporter's own method, running the tool against real rsIDs instead of reading it. Suite 2864 → 2870.

## 2026-08-20 — the 2026-08-19 doc audit's six patches (RM104–RM107, RM109, RM111)

**Cut as 0.6.6** across all three packages and tagged `v0.6.6` on 2026-08-21 — this entry read
"bumped, uncut" until then. What the tag carries is this round, the S57–S60 batch below, and S61/RM125
above: nine patch fixes in all. Every item here is a **patch**: no authored
schema changed, nothing was retyped, no published identity moved. One behaviour tightens — a duplicate
`(source, layer)` row in `licensing.csv`/`sources.csv` is now an **error** in both `validate` and
`compile`, where it used to pass silently — so a spec carrying one stops compiling. Publishing stays
the maintainer's step.

Six of the eight findings the 2026-08-19 audit turned up (it validated `just-module-creator`'s 24
per-table dossiers against this repo's code). **RM108 and RM110 are deliberately not here**: the first
needs a currency notion decided before a re-curation can be marked superseded, and the second moves
`gene_metrics.signature` for every module already carrying snapshot rows — legal, but a recompile the
ecosystem should be told about. Both stay open as minors.

**Five of the six were a derived value restated by hand somewhere else** — a suppression set beside its
merge key, an allowlist beside the extension set, a dupe key in the one map the finding loop does not
read, a check re-run without the filter its neighbour eleven lines away carries, a field description
restating an analogy true of a different field. The sixth is the empty-work path nobody runs. The suite
was green at 2859 tests throughout, and is 2864 now.

- **[RM104](ROADMAP_HISTORY.md#rm104--enrich_gene_metrics-raised-unboundlocalerror-on-the-ordinary-re-run)
  — the gene-metrics re-run raised out of the pass** (`just-dna-enricher`). `reference` was bound inside
  `if wanted:` and read unconditionally below it, so the **idempotent re-run** — the path
  merge-not-clobber documents as supported — and any module with no `variants.csv` raised
  `UnboundLocalError`. That is outside `GeneMetricsEnrichmentError`, so the single `except` RM101 built
  for exactly this caller caught nothing. The fix is one line; the test is the part that matters, since
  every existing merge test re-ran with `wanted` non-empty.
- **[RM107](ROADMAP_HISTORY.md#rm107--a-duplicate-source-layer-row-compiled-green-under---strict)
  — a duplicate `(source, layer)` row compiled green under `--strict`** (`just-dna-compiler`). No
  warning, a moved `source_signature`, and a pair free to carry opposite `commercial_use` in the one
  file the compile gate reads. **The consumer-visible change is the tightening**: both commands now
  refuse with `"<file>: duplicate row for key ('<source>', '<layer>')"`. A module whose licensing table
  carries one will need it removed. `licensing.merge_sources_csv` already merges on that pair, so
  re-running the enricher's licensing writer collapses the pair — checked — but it keeps the **last** row
  under the key, so where the two rows disagree (the case worth catching) picking the right one is a
  human's call and not the writer's. One source at two layers is unaffected, which is why the key is a
  pair.
- **[RM109](ROADMAP_HISTORY.md#rm109--the-gene-metrics-fetch-suppression-key-was-not-derived-from-the-merge-key)
  — a hand-written gene-metrics row did not suppress the fetch** (`just-dna-enricher`). The merge key is
  `(gene, dataset)` and "already done" asked `source.startswith("gnomad")`, so a correction recording
  `source="manual"` was re-fetched and the file came back with two rows under one key contradicting each
  other. Now derived from the key, scoped to the two dataset labels this pass writes so a ClinGen dosage
  row for the same gene still does not suppress it.
- **[RM106](ROADMAP_HISTORY.md#rm106--the-faf95-arithmetic-warning-was-published-twice)
  — the `faf95` warning was published twice** (`just-dna-compiler`). `_check_frequency_arithmetic` runs
  in `validate_spec` (RM93) and again on the compile side, and the compile side had no filter — so the
  line appeared twice in `manifest.compilation.warnings`, a published field, and a consumer counting
  warnings overstated what was wrong with the module. Measured at 15 warnings, 14 distinct. **A consumer
  pinning warning counts may see one fewer**; the text is unchanged.
- **[RM105](ROADMAP_HISTORY.md#rm105--logojpeg-compiled-was-attested-and-was-never-uploaded)
  — `logo.jpeg` was attested and never uploaded** (`just-dna-enricher`). `LOGO_EXTENSIONS` admits
  `jpeg` and discovery sorts, so the spelling the compiler *prefers* was the one `_ALLOW_PATTERNS`
  dropped, and the published manifest attested bytes the repo did not carry. The logo half now derives
  from `LOGO_EXTENSIONS`, as the readme half already derives from `README_CANDIDATES`. **Anyone who
  published a module with a `logo.jpeg` should re-publish**; the discovery order is deliberately
  unchanged, so nothing else moves.
- **[RM111](ROADMAP_HISTORY.md#rm111--three-shipped-strings-asserted-a-registry-override-of-license-that-nothing-performs)
  — the `license` strings claimed an override nothing performs** (`just-dna-format` +
  `just-dna-compiler`). Two shipped `Field(description=…)`, a module docstring and a code comment said a
  publishing registry stamps the authored `license`; it does not, and what the compiler actually does is
  warn when the declaration contradicts the annotation-layer sources. Documentation only — no behaviour
  changed — but it reaches authors through `describe_table`/`authoring_reference`, so a consumer
  rendering those descriptions will see new text.

## 2026-08-20 — a dossier audit's four reports (S57–S60, RM121–RM124)

**Folded into 0.6.6, cut and tagged `v0.6.6` on 2026-08-21** — this batch and the doc-audit patches above sat on the same then-uncut
number. Nothing here was added to an authored schema, nothing was retyped, and no published identity
moved. Publishing is the maintainer's step, as always.

Four reports from `just-module-creator`, filed the same day after they audited their own per-table
dossiers and their own attestations. Two are ours to fix, one is a documentation gap with a code-shaped
edge, and one is a 0.7 design that turns out to answer a question a 0.7 item has been blocked on.

**Two of the four turned out to be about a record that could not state its own scope**, which is the
reporter's sentence and is worth keeping: *a check that could not have failed should record why rather
than record a zero.*

- **[RM121](ROADMAP_HISTORY.md#rm121--manifeststats-described-one-table-and-was-published-as-if-it-described-the-module)
  — `manifest.stats` described one table and was published as if it described the module.** `stats.genes`
  came from `variants.csv` alone, so a module led by `diplotypes.csv`, `allele_function.csv` or any other
  gene-bearing kind published `gene_count: 0, genes: []` however many rows named a gene — and a registry's
  gene index is fed from that field. Measured on `reference_examples/cyp2c19_star_alleles`: **1,332 rows
  naming CYP2C19** against `genes: []`; seven of our sixteen examples carry no `variants.csv`, and seven
  of the eight non-variant gene-bearing models make `gene` **required**. `Stats`'s own docstring already
  said *"derived from the spec"*, so this was an unimplemented sentence and not a scoping choice.
  Shipped `module_stats` **beside** `variant_stats` — renaming it would be a major (S14's rule) — with
  `_GENE_BEARING_TABLE_KINDS` derived from `_TABLE_KINDS`, and derived fact sidecars structurally
  excluded. Building it recreated the RM44 defect it inherits: the post-symbolic-drop re-derive sat
  inside the `variants.csv` branch and `pharm_variants.csv` also drops and also carries a gene.
- **[RM123](ROADMAP_HISTORY.md#rm123--two-attestations-recorded-a-check-whose-scope-they-could-not-state)
  — two attestations recorded a check whose scope they could not state.** Two halves in two tiers.
  *PGx:* RM73's per-leg tautology skip has worked since 0.6.0, but `_function_check_record`'s **answered**
  branch built `detail` from the answered legs alone — so a CPIC-drafted module with PharmVar answering
  published a clean two-authority comparison with no sign that half of it was a copy against itself. The
  note lived on `result.warnings`, which is the run's stderr, and `verification.json` is what a later
  reader trusts. Both branches now sort by source: that file is a hashed input and `legs` fills in pass
  order. *Hints:* `REDUNDANCY_BEARING` is keyed on a bare column with no model attached, so the
  vacuous-check reason printed on six (column, table) pairs whose checker cannot see the table — right
  advice, false reason, and the false reason implies a green run is agreement.
  `REDUNDANCY_BEARING_TABLES` narrows the **explanation only**; the provider refusal stays column-keyed.
  The six unscoped columns are checked claims — RM43 puts resolution on the positional kinds, RM47 makes
  a bin a second citation site — and scoping either from the checker-name strings would have suppressed
  a *true* advisory.
- **[RM122](ROADMAP_0_8.md#rm122--the-measure-lookup-is-specified-and-nothing-anywhere-implements-it)
  — the binning family is now specified for consumers, and says so.** [SCHEMAS.md](SCHEMAS.md) gains the
  normative **measure lookup** beside the genotype join contract: scope to the group, select the row whose
  inclusive range contains the value, greatest `measure_min` on a shared endpoint, compare in float32
  (RM62), `unresolved` on a missing measurement and withhold on no match, and `trait_efo_id` multiplies
  the answer rather than disambiguating it. It opens with the plain sentence that the family is specified
  **ahead of its consumers** — verified: `just-dna-lite` touches all four binning tables in exactly two
  places and both count rows. The authoring skill now tells an author to write what the bins mean into
  the README. RM122 is open for the question they did not ask — whether the rule should also be a public
  function — which waits on a consumer to fix the signature against.
- **[RM124](history/ROADMAP_0_7.md#rm124--an-authors-correction-to-a-derived-table-has-nowhere-to-live-except-inside-it)
  — an authored overlay table, filed for 0.7.** RM83 named two exits from *nothing records that a row was
  overridden*; the reporter **built the first one** — a non-destructive capture/delete/re-derive/reapply
  wrapper — and it stops exactly where RM83 predicted. RM124 is the second exit with their shape, the tier
  settled in their favour, and four questions open. The sharpest is one only RM115 could expose:
  `(table, subject, field)` cannot key `resolution.csv`, whose published rule is `subject`.

**One report did not reproduce, and the reply says what was probed.** `enrich_facts` names no symbol in
any tier; read as the gene-constraint pass, the two states it describes have been separate since RM98 in
**0.6.1** — a looked-up gene gnomAD publishes nothing for gets a `not_found` row, a gene reachable
through neither route gets no row and lands in `unconsulted` with its own warning. The reporter is
running enricher 0.6.4.

**Triage thresholds moved to 20/30** the same day (dev-start and the stop-filing ceiling, from 10/20),
and the block that counts them was worse than stale: it grepped `Status** open — **0.6**`, an idiom
`ROADMAP.md` stopped using once 0.6 shipped, so it returned `0` however full the queue was. It now counts
the two forms the file actually carries. A stale counter reads as an all-clear.

Suite 2835 → 2859 passing (2,867 collected, 8 skipped — the opt-in network tests).

## 2026-08-20 — a triage batch of seven, and the one authored column in it (S50–S56, RM115–RM120)

**Cut as 0.6.5** across all three packages and tagged `v0.6.5` on 2026-08-20 — the aligned number, since
schema, compiler and enricher all moved in this batch. Tagged is not published: `uv publish` is a
separate step and the maintainer's. Seven items from `just-module-creator` across three reports in one day. Additive
only: **one new authored column** (`StudyRow.curator`), two new manifest/document fields, three new
public names, two new checks and one documentation fix. Nothing removed, nothing retyped, no existing
authored column moved — so an existing module's `content_signature` is unchanged, verified.

**Two of the seven came from the reporter re-reading rules they had themselves asked us for**, and one
is a retraction. That is worth recording as the useful shape of a consumer relationship rather than as
a curiosity: S55 withdraws the argument behind S11, and S54 is the measurement they took while checking
it — 3,668 quotes across four published modules that the rule had produced, all of them titles.

- **RM115 — a derived sidecar's merge key is published, and every pass reads it.** RM113's question
  asked of the machine-produced tables, where the key existed only as a dict-key expression inside each
  writing pass. `hints.key_fields` already routed derived names through `derived_model_for`; the seven
  fact models simply declared no key. The reporter's approximation was coarse on exactly the two tables
  where one subject carries several rows, both reproduced. `KEY_RULES` gains `subject` for
  `resolution.csv` (one rsID, several loci — reporting `equality` would call a legal file a duplicate)
  and `TableKey` gains `fallback` for `gene_validity.csv`'s two-level key. `base.merge_key` is the
  row-level answer and **every pass keys its `existing` map through it**, which is what stops the two
  drifting. The rewire exposed three lookup sites restating the key positionally; one would have
  refetched every cited article on every run.
- **RM116 — `compiler.spec_tables(spec_dir)`.** The rows behind `content_signature`, defaults-folded,
  plus the declared build; `content_signature` is now that plus the hash. Anything finer than a
  whole-module digest had to restate the private roster and the `defaults:` fold, and the fold silently
  produces a wrong answer — measured, the obvious build outside the function reports twelve changed rows
  where there are none. COMPILER.md now names the roster and says the licensing table is outside it.
- **RM117 — `ProvenanceItem.outranks`, and the check half filed.** `{column: why}`, so a module that
  deliberately disagrees with a source can say which column and why. Per column, because a row may
  outrank an archive on `clin_sig` while its `direction` is unjustified; per *variant*, because
  `Provenance.item_count` is a published number meaning *variants carrying a record* and redefining it
  is a silent break. Whether a check downgrades a mismatch to INFO is **open** (RM117): the
  pre-emption guard is a convention the code cannot see, and a record is not yet bound to the value it
  justifies.
- **RM118 — a `provenance_quote` that is the article's own title is reported.** A title appears in its
  own fulltext, so the quote check cannot fail on one — `quotes_found` equals `quotes_authored` while
  nothing about any claim is established. `LiteratureResult.titles_as_quotes` plus a yellow CLI line.
  The discriminator is the **metadata**, not the string's shape: length cannot separate a 17-word title
  from a 17-word sentence. Warning-only. It answers for a **pinned** sidecar row too, which the reporter
  corrected us on mid-triage: those four modules have every row pinned, so a check living in the fetch
  loop would have fired on none of the 3,668 quotes it was written for.
- **RM119 — a citation sidecar can no longer contradict its own `studies.csv`.** `literature.csv`
  recorded `quotes_authored=0` beside 69 real quotes in four published modules, because it is
  merge-not-clobber and the pass ran before the quotes existed. `_check_quote_counter_is_current` warns
  naming both numbers. And **`Literature.quotes_unchecked`**: `_literature_block`'s per-row null guard
  is right and does not survive aggregation — `sum()` over all-null rows is `0`, so the block published
  exactly the sentence its own docstring calls the most misleading thing it could say.
- **RM120 — `StudyRow.curator`.** Who located this row's quote: the field `VariantRow` has always had,
  on the table where the attestation lives. Free text resolvable against `authorship`, never a
  `machine_located` boolean. `ATTESTATION_BEARING` is unchanged. **Wiring it found that
  `@three-touch-points` undercounts for `_write_studies_csv`** — there is a fourth site, the row dict,
  where a missing key makes `DictWriter` write the header with an empty cell on every row: the reversed
  spec re-validates and the value is gone, and only the digest fixed-point catches it.
- **S50 — `--no-study-facts` is permanent for the rows it writes.** Documentation only, no `RMn`: the
  merge rule is correct and the prose read as a per-run trade. ENRICHER.md and the CLI help now say the
  linked columns are lost for those rows and that deleting `gwas_effects.csv` is the recovery.

Suite 2784 → 2833.

## 2026-08-20 — three schema facts a downstream surface could not generate (S47–S49, RM112–RM114)

**Shipped in 0.6.5**, cut and tagged on 2026-08-20 with the batch above. Three items from
`just-module-creator` in one sitting, all from the same work: their
MCP tools had answers that **restated** a schema fact instead of generating it, and two of the three had
no public symbol to generate from. Additive only — new public names beside the old, nothing removed or
retyped, no authored column moved, so `content_signature` is untouched everywhere.

- **RM112 — `hints.DERIVED_TABLE_MODELS` + `hints.derived_model_for(csv)`.** `draft.model_for` is
  authored-only by design, so a tool asked what is in `frequencies.csv` or `resolution.csv` got *"not an
  authored table of this format"* — true and useless — and the only complete map was private
  `compiler._FACT_TABLES`. All four substitutes were measured and fail; notably
  `ARTIFACT_PARQUETS - LEAD_PARQUETS` is **nine** names against seven fact tables. Derived from
  `_FACT_TABLES`, never restated.
- **RM113 — `hints.key_fields(csv)` → `TableKey(columns, rule, stamped)`, and `describe_table` now
  carries a `key` block its docstring has promised since 0.5.** The reporter's hand-kept key string had
  gone stale, naming `modifier_cn`, deprecated at 0.6. The obvious repair is a **wrong answer**:
  filtering `_KEY_FIELDS` through `model_fields` silently drops `CopyNumberRow`'s property-valued
  modifier axis. Structurally, eight models now declare `_KEY_FIELDS` and both dupe-key dicts derive
  from it, so `key_fields` and `natural_key` cannot drift.
- **RM114 — `scaffold.companions_for(kinds)`.** The `studies.csv -> variants.csv` pull was
  unconditional, so scaffolding a binning module invited an empty `variants.csv` into a spec that
  compiles strict-green without one. RM47 is what made it wrong; the constant's own comment already said
  *alone*.

**The shape worth carrying.** All three are one defect at three sites: a fact stated twice, once where it
is enforced and once where it is described, with only the enforced copy under test. The durable half of
each is therefore a **derivation** rather than a fix — the published map reads `_FACT_TABLES`, the key
reads the model, the companion set reads the compiler's composition rule — because publishing a
hand-kept copy of a map in order to close a report about hand-kept maps is the defect wearing a public
name. Two guards found things the designs had not: `variant_key` is a stamped **field** on three models
and a **property** on `StudyRow`, and the first key guard failed on `studies.csv` correctly.

Suite 2779 → 2799, green throughout; `ruff` clean. **S50–S52 arrived during the pass and are
deliberately left `new`** — S50 is a documented doc-gap in the GWAS merge, S51 and S52 untriaged. An
empty verdict is honest; a hedged one is not.

## 2026-08-20 — §6.6 said a review pass reaches nothing downstream, and it had reached it for three releases (S46)

Documentation only; no code moved and no version needs cutting. `just-module-creator`, writing a
`module-revise` skill with [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md) §6 as its source, measured §6.6's
central claim from outside and found all three halves of it false. Re-verified here first-hand against
the `just-dna-registry` tree at **0.18.3**, not taken from their report or from that registry's replies:

- **`verification.json` is recognized** (`RECOGNIZED_SPEC_FILES`, their 0.16.0), so `revalidate` and
  `upgrade` carry it forward instead of dropping it; it is in `DERIVED_FILES`/`manifest.derived` (0.17),
  so `download(include_inputs=True, layout="split")` returns it at `derived/verification.json`; and
  `manifest.verification` is **projected onto their module-detail response**, with `closed` re-bound by
  their own compile against the authored bytes. Still out of `SIGNATURE_INPUTS` — the property that made
  recognising an unread file safe, unchanged.
- **The pre-flight agrees with the gate** as of their 0.16.0, via a new `published_elsewhere` the verdict
  quantifies over. Nobody on this side had re-read the reply, so §6.6 and § stages 7–8 both still
  described a publisher being refused its own legal review publish.
- **`authorship` reaching no projected field is policy, not an omission** — answered, not repaired.

So §6.6's conclusion — that a re-close *"costs a version number for a record nothing downstream can
see"* — had inverted, and the section is rewritten: the four findings are stated **separately with the
release that moved each**, which is the reporter's suggested shape, adopted because the composite
sentence went stale as a unit and a reader could not tell which third was still true. The new advice is
that registry's own answer to the question RM86 had left open: **a `reviews` row by default; an
`authorship` entry when the record must travel inside the module or be signed; both when both matter** —
so *visible downstream* deliberately does not become *bump a version for every review*.

**[RM86](history/ROADMAP_0_7.md#rm86--a-review-pass-is-legal-at-the-gate-refused-by-the-pre-flight-and-invisible-once-published)
is closed** in place, with per-finding dispositions; its own status line ("waits on their answer to S12")
was stale too, since that answer arrived in their 0.16.0. [RM_TOC.md](RM_TOC.md) carries the same, and
the entry's `../just-dna-marketplace` pointer now names `just-dna-registry` — the former is a symlink to
the latter. S46 is archived.

**The lesson, which is why this entry is long for a doc fix:** every clause of that sentence was verified
in another repository's tree the day it was written, and none of it was re-checked afterwards. Prose
citing another repo's code has no test behind it and no expiry, so it decays silently while reading as
evidence. §6.6 now dates each finding to a release, which is the cheapest thing that makes the decay
visible to the next reader.

## 2026-08-20 — a downstream reference surface, validated against the code, and eight findings filed (RM104–RM111)

**No version moves.** Format and compiler stay at **0.6.1**, enricher at **0.6.4**. This is an audit
round: nothing shipped, eight things were filed, and one downstream repository's documentation was
corrected in place.

**What was audited.** `just-module-creator`'s `skills/module-tables/references/` holds 24 files, one
per table kind, written against this repo's 0.6.1/0.6.4 by another agent. All 24 were checked three
ways — the reference, against our `docs/`, against **the code as arbiter**. The calibration result is
worth recording because it inverts the expected yield: roughly 250 `file:line` citations were
spot-checked across twelve reports and **near-zero named the wrong symbol**. Their line numbers have
drifted with the tree; their reasoning held. So most of what the audit found is wrong in **our**
documents, not in theirs.

**Two of our own findings were themselves wrong, and the reason generalises.** Two reports accused the
reference of fabricating `describe_table`'s return value and of calling a `table_requirements` symbol
that does not exist. Both accusations are false: those are the **plugin's own MCP tools**, which really
do return `redundancy_bearing`/`attestation_bearing` and really do expose `table_requirements`. The
agents checked `just_dna_compiler.hints` — a different surface with the same names. **When a claim
names a tool, establish which surface owns that name before calling it a misread**; the wrapper and the
library disagree deliberately, and only the *count* was actually wrong (thirteen authorable kinds, not
twelve).

**The downstream files now carry two markers**, and they are a convention worth knowing if you read
them: 🚧 **ROADWORKS** for a surface that is broken or unfinished, always with a **Guard** naming what
to do instead, and ⚠️ **CHECK** for a claim whose current state is not what the surrounding text
implies. 25 and 10 of them respectively, plus a per-file audit banner and about ten unmarked in-place
corrections. That repository is not ours to commit; the edits are left in its working tree.

**Eight code findings, filed as RM104–RM111 and none of them fixed.** Three are one-line patches with a
test each — `enrich_gene_metrics` raising `UnboundLocalError` on the ordinary idempotent re-run
(**RM104**, and it defeats the `GeneMetricsEnrichmentError` contract RM101 was built for), the `faf95`
arithmetic warning being **published twice** into `manifest.compilation.warnings` (**RM106**, the same
shape as the shipped RM94, three lines from a dedup filter whose comment names the hazard), and the
gene-metrics fetch-suppression key not being derived from its merge key, so an honest `source=manual`
override duplicates instead of overriding (**RM109**). Two more are patches with a wider blast radius:
`logo.jpeg` compiles and is attested but never publishes, because the publisher allowlist is the one
place still spelling logo names by hand (**RM105**), and a duplicate `(source, layer)` row compiles
green under `--strict` because `SourceRow` is in the *drafter's* dupe map and not the *compiler's*
(**RM107**) — in the one file the compile gate keys on. Two need design before code: a ClinGen
re-curation appends a second row with nothing marking the superseded one, so
`manifest.gene_validity.classifications` can publish `["definitive", "refuted"]` with no currency
notion (**RM108** — S45's shape, minus the signal S45 had), and `constraint_flags` carries two
encodings from two producers, where normalizing the snapshot leg's literal `"[]"` would move
`gene_metrics.signature` for every module already holding those rows (**RM110**). The last is
documentation shipped as code: three strings, two of them `Field(description=…)`, assert a registry
override of `license` that the registry's publish path never performs (**RM111**).

**Three recurring shapes came out of it, and they are the part worth carrying forward.** A check is
only as wide as the table it reads, and our documents name checks without naming that scope — six
agents found an instance independently, from `REDUNDANCY_BEARING` being keyed on a bare column name
(so it advertises checkers that cannot run on the model in front of you) to `manifest.stats.genes`
being `variants.csv`-only, so a gene-keyed table-only module publishes `gene_count: 0`. A counted
claim in prose rots the same way a hand-kept list does — "seven fact signatures" (eight), "six derived
sidecars" (seven), "four causes" (five) — and the repair is an **equality over a walked set**, never a
corrected integer. And an *enforcement* claim needs its surface named: the `unresolved` bin sentinel is
called mandatory in three places, and the compile path refuses a **second** one while refusing zero
nowhere at all, with the presence half living on the authoring hints and scoped to the whole table
where the compile rule is per bin group.

## 2026-08-19 — 0.6.4: "needs a re-draft" was an incomplete instruction (S45)

**`just-dna-enricher` 0.6.4**; format and compiler stay at **0.6.1**. One fix, three tests, suite
2776 → 2779. It exists because a consumer measured the half the 0.6.3 entry explicitly did not claim
to have measured, and the answer was worse than assumed.

**Two drafting fixes shipped in 0.6.3 and they remediate differently, which is the frame worth
carrying: S44 *skipped* rows, S41 *wrote them under an identity that has since moved*.** Only the
second leaves anything behind. Re-measured here: a stale ClinPGx module of 18,691 rows re-drafts to
**18,895 with 0 missing and 0 stale**, exactly a fresh draft — so S44 needs no caveat, while S41 does.
A reader meeting both in one set of release notes will reasonably assume otherwise.

**A re-draft repairs S41's omission and cannot retract S41's collapse.** Drafting appends and never
mutates, so re-running the fixed drafter over an existing spec adds the coordinate-keyed rows
**beside** the collapsed rsid-only row instead of replacing it. The module then carries both the
replacement rows and the row they replace — and the stale one is the row bearing the mislabelled
expansion, since resolution pairs its authored genotype with every locus its rsID resolves to. So the
remediation named in the 0.6.3 entry leaves a module worse-formed than either the old one or a fresh
one.

Reproduced independently on `MLH1` at `min_review_stars=2`, every number matching the report: a stale
module of 996 rows re-drafts to **1,061** against a fresh draft's **1,030** — `added=65,
already_present=965`, **0 identities missing** and **31 present that a fresh draft does not contain**.

**And they were undetectable from inside the module.** `_row_cells` writes no `rsid` on a
coordinate-identity row, so the obvious predicate — *an rsid-only row whose rsID also appears on a
coordinate row* — finds **0 of 31**. The pass itself can see it, because it holds the set of rsIDs it
is deliberately writing by coordinate this run; an rsid-only row carrying one of those is a row no
current draft would produce. `_superseded_rsid_rows` now names them after the append, aggregated
through the house `examples` helper.

**Reported, never removed**, which is the reporter's own preference and the right one: a drafted row
is authored material by the time a re-draft runs, a human may have curated its `genotype`, `state` and
`conclusion`, and deleting curated work to repair a drafting defect is a trade only the author can
make. The cleaner remediation is still a fresh directory reconciled against the old module — the
notice is for the author who followed the shorter instruction, which is the one we wrote.

## 2026-08-19 — 0.6.3: a drafter that silently dropped ClinVar records, and three more from one audit (S41–S44)

**`just-dna-enricher` 0.6.3**; `just-dna-format` and `just-dna-compiler` stay at **0.6.1** — a partial
cut, since no code outside the enricher moved. Suite 2761 → 2776, `ruff` clean. Everything here came
from one just-dna-lite audit of ten `v1_port` modules, plus S39 from just-module-creator carried over
from the previous pass.

**The serious one: `multi_allelic_rsids` keyed the site on `ref`, so an ordinary ClinVar dup/del pair
collapsed onto one row and the second record was dropped (S41).** An rsID takes coordinate identity
when it names more than one allele *here* — except the predicate grouped by
`(rsid, chrom, start, ref)` and fired on more than one alt inside that group, which is not what its own
docstring claimed. A mirror pair (`A>AT` beside `ATT>A` at one position, the same event written from
either side) is two groups of one alt each, so the rsID was never flagged, both records reduced to the
same rsid-only identity, and `append_partial_rows` dropped the second as `already_present` — silently,
because dedup is the normal case and nothing distinguishes it from a re-draft.

Re-measured here on the `2026-06-27` snapshot over BRCA1/BRCA2/ATM/MLH1/MSH2 rather than quoted from
the report: **942 rsIDs flagged before, 1,589 after**, and the 647 newly flagged are exactly the 647
identities that were collapsing. **725 records recovered, 0 made unkeyable, and 187 of those collapses
had been dropping the better-reviewed record** — `select_by_gene` orders by `ref` before
`review_stars DESC`, so which of a pair survived was decided by allele spelling rather than by
evidence. The event key is now the whole `(chrom, start, ref, alt)`, which also catches one rsID at two
distinct positions; distinctness is over the allele event and not over records, so a re-submission
under a second `variation_id` still does not flag. Six tests, all run against the unfixed predicate and
watched to fail, the real-snapshot one at exactly 725. **Modules published before this need a
re-draft** — no fix here reaches an artifact already built.

**The ClinPGx drafter's genotype gate was narrower than the schema it writes into (S44).**
`_authored_genotype` took only `CC`, on the argument that the general case needs the resolved ref/alt
to disambiguate — true of an unseparated cell, false of the two shapes ClinPGx publishes beside it,
since `validate_allele` accepts any `^[ACGT]+$` allele. `CTT/CTT` is *already* separated by the source,
and declining it cost **CFTR F508del**: those annotations carry a `del`-spelled genotype and a
pure-nucleotide one under one `annotation_id`, so skipping the annotation discarded the writable row
with it. A bare `A`/`CCCCCCC` is the haploid form the grammar already holds and how ClinPGx spells
mtDNA — declining it cost every **MT-RNR1** annotation, 32 rows at evidence level 1A, a CPIC guideline.
**158 rows recovered**, 36 at 1A. `del/del` and `C/del` stay skipped, unchanged and deliberate: ClinPGx
publishes no length and the compiler drops a lengthless symbolic allele. The general rule is a test now
rather than a comment — *every spelling this pass declines must be one `PharmVariantRow` would also
refuse* — walked over the accepted set, with the converse still allowed.

**A share-alike source was recording its licence without pinning it (S44).** `SourceTerms.row` has
taken `license_text=` all along; `clinpgx_draft` passed only `declared_use` and `dataset`, so
`license_sha256` was null while `clinpgx_build` was extracting `LICENSE.txt` into the snapshot for
exactly this purpose. Hashed from the file rather than copied from `release.json`'s stated hash — the
file is what the module claims, so a truncated copy cannot pin to a value it lacks. Absent stays `None`
and warns. `merge_sources_file` is never-clobber, so a module drafted earlier keeps its null until the
sidecar is deleted and re-drafted.

**Two documentation defects with no code half, and one filed.** `likely_pathogenic` and `likely_benign`
turned out to be **unwritable, not merely unwritten** (S43): parquet columns with no authored field
behind them, a literal `False` since the initial 0.1.0 commit, read by nothing. Not filled and not
removed — both are breaking moves on a published column — but documented as permanently unwritten, in
SCHEMAS.md's tri-state table as its one acknowledged exception. Probing that corrected a claim we were
about to make wrongly: `manifest.stats.pathogenic_count` counts **authored `variants.csv` rows**, not
parquet rows, which diverge wherever resolution expanded one row onto several loci. And a digitless
`module.version` coerces to `0.0.0` and reaches `manifest.identity.version` (S42) — filed as
**RM103** rather than fixed, because refusing it is a new refusal and that sizes as a minor, the
RM50/RM48 class. Both entry points already warn naming the authored string, so the silence is the
model's alone.

## 2026-08-18 — an off-switch that switched nothing, and an upgrade note silent on a relaxation (S39, S40)

**One enricher fix, three documentation fixes, one new test, one roadmap item.** Nothing is cut:
`just-dna-enricher` stays at **0.6.2** in `pyproject.toml`, and the fix below will carry **0.6.3**
whenever the maintainer cuts it. Suite 2761 → 2762, green throughout.

**`load_dotenv_file=False` reached none of the six cache resolvers (S39).** The parameter has existed
since the resolvers were generalized, is named in six signatures, and did nothing at all: each
`resolve_*_reference` passes `default_*_cache_dir()` as an *argument*, and that helper went through a
`_cache_dir` whose `load_env()` was unconditional — so the `.env` was loaded before the resolver had
looked at its own flag. Probed rather than read, with a marker variable in a `.env` and a controlled
cwd: `load_dotenv_file=False` left it in `os.environ` for cpic, ensembl and clinvar alike. The flag is
now threaded through `_cache_dir` and the six `default_*_cache_dir` helpers rather than the load being
removed — the unconditional load is itself the 0.5.2 repair behind three "the cache is right there"
reports, and the `True` path is unchanged. `test_locations.py` runs each resolver in a subprocess and
pins both directions plus the pre-fix arrangement; a twelfth test walks both families asserting each
member takes the parameter, so a seventh snapshot cannot quietly reopen it.

This is the **second** knob in two days whose disabling value did not disable — after the watcher's
`${BRANCH:-main}`, where `BRANCH=` restored `main` — so it is now a rule with a tag:
`@off-switch-needs-a-probe`. Run the disabling value; a test that passes the enabling value and a test
that passes nothing are the same path.

**What that fix does not reach is [RM102](ROADMAP_HISTORY.md#rm102--the-enricher-loads-a-env-into-osenviron-from-library-paths),
and S39's reporter hit the default path.** The enricher loads a whole `.env` into `os.environ` from
*library* code, so asking where the ClinVar cache is can hand a process credentials for sources it
never named — and `override=False` skips a variable that is **present**, which means *deleting* one is
exactly what lets the file supply it. Their test isolation was undone that way. Filed rather than
fixed: a default flip is silent for every caller who never passed the parameter (S14's shape, so an
actionable deprecation has to come first), the allowlist variant makes us a filter over somebody
else's file, and four credential paths carry no flag at all by `@credential-where-read`. ENRICHER.md
now documents the mutation, the sharp edge, and both halves.

**INTEGRATION_0_6.md was silent on the one check that *stopped* refusing (S40).** RM47 relaxed
`StudyRow.REQUIRED_ANY_OF` to `()`, which § 1 never mentioned while naming both tightenings — the
table row *"Fields removed, retyped, or promoted to required | none"* is literally true and still left
a consumer's negative test failing with nothing to anticipate it. § 1 gains the symmetric table row
and a subsection that leads with the consequence rather than the validator: `StudyRow.variant_key` can
now be `None`, and a null join key in polars is a **silently smaller result**, not an error. A
relaxation is invisible to a corpus run and visible to every consumer holding a negative test, which
is the argument for saying more about it rather than less. No code half underneath it —
`_cross_validate_studies` handles the subject-less row deliberately.

**And it pointed at a fixture that does not exist.** § 3 told just-dna-lite that a same-`ref`
expansion "is instantiated in `reference_examples/shox_par1/`", offered as the evidence that their
`ref`-spelling mitigation is insufficient; the committed example is 10 rows, 10 distinct rsIDs, all on
chrX, `expanded_keys=0`. The sentence now says so and names both routes to build one, including that
the VRS check refuses a copied `vrs_id` and prints the recomputed pair — the detail that makes it ten
minutes rather than an afternoon. **Building it found the gap under the report:** the claim had no
instance anywhere in this repository, tests included, because the corpus's only other expansion
(`pathogenic_clinvar`'s `rs1554917888`, `T>TA` beside `TA>T`) differs in `ref` — so every existing
`locus_count` assertion would have survived an expansion that deduped on `(chrom, start, ref)`.
`test_two_loci_sharing_a_ref_still_count_as_two` builds the twin from the example's own row through
`par_partner` and asserts both halves against each other. Third item, same document: § 1's *"nothing
you have breaks"* now carries the one exception, the private `_OUTPUT_FILES` made public as
`ARTIFACT_PARQUETS`.

**A consumer note from just-dna-lite is recorded below**, dated the same day, in the convention this
file already carries for their 0.5 adoption. It is their writing and is committed unedited.

## 2026-08-18 — the 0.6.2 upgrade note had a fourth shape, and it was the silent one (S38)

**No package is cut.** `just-dna-enricher` stays at **0.6.2** and the code is unchanged — S38 is
explicit that the RM101 subclass design is right, and it is exactly what makes the reported shape
possible. What moves is two documents, one guard test, and a dated correction on S37's reply.

**The defect: "catch both" describes two handlers that behave oppositely.** § 8's migration table said
`except (FrequencyEnrichmentError, GnomadError)` "keeps working, unchanged", written as though catching
both could only mean one tuple. just-dna-registry had them as two separate arms — the two meant
different things to them, a plain warning against an `unreachable` field — with the parent first. On
0.6.2 `enrich_frequencies` raises `FrequencyUnavailable`, which **is a** `FrequencyEnrichmentError`, so
the first arm wins and the outage arm is dead code. Three of their four handlers. **It fails silently**:
nothing raises, nothing 500s, and their endpoint reported a clean check while gnomAD was down — the
failure RM101 exists to end, reintroduced by the fix for it, in a consumer who had followed our advice.
They caught it only because their guards assert the *field* rather than the status code.

**Fixed where it was read and where it is maintained.**
[INTEGRATION_0_6 § 8](INTEGRATION_0_6.md#8-what-061-got-wrong-and-062-fixed) gains the fourth row in
the reporter's own words, plus a paragraph saying to read rows one and four together, since they differ
only in punctuation. [ENRICHER § Exception contract](ENRICHER.md) gains the same warning, because a
migration note stops being read while the reference does not. The 0.6.1 workaround row now says **in
one tuple**. § 8 also now points at `AcmgListUnavailable.skip`, which separates `unreachable` from
`no_reference` — the reporter had been collapsing the two and sending operators to check a healthy
network, and fixed it themselves once they read the field.

**The guard is structural, because the defect is invisible except in the shape of the code.**
`enricher/tests/test_shadowed_handlers.py` parses all three packages and fails on any `except` arm an
earlier arm in the same `try` already catches. Our tree is clean — and since a zero is worth nothing
unless the walk can fail, a second test runs it over the reporter's snippet and asserts exactly one
finding. A parent and child in **one tuple** is deliberately not a finding: that is redundant rather
than dead, and a guard that cries wolf on it gets deleted. Adopted from the guard the reporter built
for themselves.

**S37's reply carries a dated correction rather than an edit.** The sentence *"your adapters catch the
client's type alongside the pass's, and that keeps working unchanged"* was ours and was too broad. It
stands, with the correction beneath it: the reply is what a consumer was told, and rewriting it would
hide that the advice was incomplete. The fingerprint is unmoved — corrections sit above the marker,
which is what the reply span excludes.

## 2026-08-18 — the outward half of the gist sync, and the off-switch that was not one

**No package is cut for this.** Loop maintenance again: the only executable change is to
`.claude/watch-suggestions.sh`, which ships in nothing, and the rest is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md) plus the published copy of the loop. The live
consumer inbox is empty and stayed empty, and the ledger read all-`current` over both history files
before and after.

**The sync is cheaper to start: check a digest, fetch only when it moves.** Pulling both scripts from
the gist and diffing them at the head of every pass is work for nothing in the normal case — the
upstream changes rarely, and the diff is deliberately noisy because the published copy is
parameterized. The gist's own revision id is a public digest of the whole thing, so one unauthenticated
API request answers the only question the sync-in asks first. The baseline lives in the runbook rather
than a side-car file, on the same reasoning as the in-document ledger, and it is pinned to a revision
established rather than assumed: the gist had not moved since 2026-08-16, and both local adoptions are
later, so the revision `e9a538e` read is the one it still served.

**The standing outward debt is discharged.** The 2026-08-17 entry above closed naming it — the
watcher's branch-pause had not reached the gist — and the digest check joined it, since a change to the
*pattern* belongs in the published copy by that document's own rule. Both are in gist revision
`bd793a8c`, genericized: the branch-pause derives its work tree from the watched file rather than from
the script's own layout, and never fires outside a git work tree at all, because a generic adopter may
be running with no repo.

**Porting it forced a correction the pattern had been carrying.** The gist's "why not git" gave two
fatal reasons, one being *the loop must not commit* — which stopped being a property of the design here
when the unattended permit was granted, and a watcher that pauses precisely **because** the loop commits
cannot sit in a document denying that it does. The surviving reason is fatal alone (a reporter may
commit their own addition, and a diff-based ledger then sees nothing), so the design holds; the expired
reason is recorded rather than deleted, because a design defended by two reasons is worth re-checking
when one of them goes.

**And the port found a real defect in our own watcher.** `BRANCH=${BRANCH:-main}` treats an explicitly
empty value as unset, so `BRANCH=` — the one thing anybody would type to switch the pause off — restored
`main` and switched it on. Fixed in both copies to `${BRANCH-main}`. It surfaced only because the
off-switch was *run* in a sandbox rather than read: the two spellings behave identically for every value
except the empty one, which is the value no test reaches by accident. The same rehearsal covered
`main → branch → main`, an edit written while paused arriving in the resume event, and a non-git
directory never pausing.

## 2026-08-18 — 0.6.2: a pass owes its own exception type, not its client's (S37 / RM101)

**`just-dna-enricher` 0.6.2 — cut and tagged `v0.6.2`. A partial cut**: `just-dna-format` and
`just-dna-compiler` have no diff since `v0.6.1` and stay there, which is the normal shape here (schema
sat at 0.5.0 across two compiler releases). The additions are minor-legal — six new public exception
classes beside the existing ones, nothing removed, promoted or retyped — so a patch number carries
them without straining P3.

**What a caller gets.** A pass now raises **its own** type, and where the reason is "the source could
not be reached" it raises an `*Unavailable` subclass of that type — `FrequencyUnavailable`,
`LiteratureUnavailable`, `GeneMetricsUnavailable`, `IdentifierUnavailable`, `ClinGenUnavailable`,
`GeneValidityUnavailable`, after the `AcmgListUnavailable` that already had this shape. Every one is a
subclass, so an existing `except <Pass>Error` catches everything it did before (P3) and the narrower
catch is new capability rather than a migration. The client's exception is chained onto `__cause__`.
The table is in [ENRICHER § Exception contract](ENRICHER.md).

**What was broken.** Five call sites held a client in `try: … finally: close()` with no `except`, so
`GnomadError` left `enrich_frequencies`/`enrich_gene_metrics` and `EutilsError` left
`enrich_literature`/`check_rsids`. The handler a consumer was told to write did not fire. **Our own
CLI had it too**: `just-dna-enricher frequencies` promises `FREQUENCIES FAILED: <reason>` and exit 1,
and on a gnomAD 503 it printed nothing and let the exception out.

**And a third client was still leaking `httpx` after RM97 said that was over.**
`OntologyClient.trait`/`.gene` kept the exact unrepaired shape — `raise_for_status()` in the callers,
`HTTPStatusError` in neither retry list. RM97's coverage guard walked a hand-written tuple of eight
module names and `identifiers` was not one of them; both guards now walk the package, so a new client
or pass fails the suite by name.

**Two conflations split.** `ClinGenError` and `GeneValidityError` each covered "the source could not
be fetched" *and* "the local CSV will not parse" — opposite histories, previously separable only by
reading `exc.__cause__`. Only the fetch path is now `*Unavailable`.

**If you catch the client's type today, you can stop** — but check first whether you catch it
*instead of* the pass's type, because that is the form that stops firing. Catching both, which is what
just-dna-registry did as a workaround, keeps working unchanged.

Suite: 2738 tests. Every repair was demonstrated failing on the unrepaired code before being asserted.

## 2026-08-18 — 0.6.1: nine defects a code-first reading of the documents found, and RM88 closed

**`just-dna-format` + `just-dna-compiler` + `just-dna-enricher` 0.6.1 — cut and tagged `v0.6.1`.** A
documentation pass regenerated SCHEMAS/COMPILER/ENRICHER from the source alone, read the result against
the shipped documents, and asked which of the two was wrong. Eight times it was the code (RM93–RM100,
filed as eight items; RM100 grew a fifth defect while the first four were being fixed, so nine
defects in eight entries). **No schema surface moves, `schema_version` stays `"1.0"`, and all sixteen
reference examples recompile byte-identical** — verified against a worktree at `5c1ea87`, the state
before the first fix, rather than inferred from the absence of a model change. The suite went
**2568 → 2722**, and every new regression test was demonstrated failing on the pre-fix tree before
being claimed as a guard. The seven doc commits that landed after `v0.6.0` ride along, as the entry
below said they would.

**Every one of the eight broke a rule this repo had already written down, and in four of them the file
carrying the violation also carried the rule — sometimes in an adjacent comment.** That is the finding
underneath the release rather than a remark about it: `@validate-refuses-all`, `@vocab-separator-slip`,
`@registry-completeness`, `@client-exception-contract`, `@unreachable-not-absent`,
`@sidecar-name-and-place`, `@credential-where-read`. **The gotcha book is not the thing that catches a
regression.** So the durable half of every item is a test, and in six of the nine that test walks a
registry rather than a list.

**Five of the nine are the same failure at five scales: a hand-kept list standing in for a registry.**
`_ALL_MODELS` missing five row models; `test_validate_agrees_with_compile` missing four of the seven
fact tables; `net.py`'s "nine policies" against a tree of twelve; a sidecar resolver three passes did
not call; a client contract two of four clients honoured. None is a hard bug in a clever place — all
five are a number or a list somebody had to remember.

**The two parity gaps (RM93/RM94, compiler).** `_check_study_effect_alleles` sat inside `validate_spec`'s
`if variants:` block and ran unconditionally on the compile side, so it never ran for the composition it
was written for — a table-only module with `studies.csv` and `resolution.csv`. `_check_frequency_arithmetic`
was never called from `validate_spec` at all, and its integer half returns errors, so a plain `validate`
blessed a module a plain `compile` refused. Both reproduced on real specs first. The compile-side
`_check_p_value_num` re-run also published its warning twice into `manifest.compilation.warnings`;
the re-run was examined and **kept**, because the inner `validate_spec` always runs in best_effort and
the second pass is the only thing that lets `--strict` escalate.

**The vocabulary and registry items (RM95/RM96, format).** A closed vocabulary is supposed to accept
`-` for `_` **and store the declared member**; three validators called `check_vocab` for its raising
side effect and returned the raw input, so `measure_kind="copy-number"` was stored inside
`content_signature` and then rejected by every subclass. And `_ALL_MODELS` was missing `ResolutionRow`,
`FrequencyRow`, `GeneMetricsRow`, `LiteratureRow` and `GwasEffectRow` — five, where the filing named
three. Admitting them turned the existing guards on and found **seven** more fields enforcing a
vocabulary without declaring it.

**One consumer-visible surface grows, deliberately:** `authoring_reference()`, `describe`,
`requirements` and `json_schemas()` render **28 models where they rendered 23**. Additive under
Principle 3, and the trade is stated where the registry is — a wider printed reference in exchange for
guards that cannot miss a model again. `INTEGRATION_0_6 § 7` tells a consumer so.

**The four network-tier items (RM97–RM100, enricher).** `gnomad` and `eutils` leaked raw `httpx`
exceptions past handlers written to catch this tier's own error types, while `cpic` and `pharmvar` had
carried the repair *and* its narrative for a release. Two `--offline` paths wrote `not_found` naming a
cache and a release nobody opened — a fabricated negative, guaranteed rather than incidental in the one
mode a consumer runs when they cannot reach the source. Three passes joined a sidecar filename onto
`spec_dir` by hand, and five more sites did the same in the CLI's success lines. And five small surface
defects, of which the sharpest is that `python -m just_dna_enricher.cli` exposed 23 of 26 commands
because `if __name__ == "__main__"` sat two-thirds down the file.

**Five filings understated what was there, and the entries in ROADMAP_HISTORY say so** — the user's
call was to correct them as they moved rather than preserve the filing verbatim. RM93's guard was
missing four fact tables, not one; RM96's registry five models, not three; RM99 had five more sites in
the reporting layer; RM100 stranded a fourth command. The fifth is a correction in the other direction:
RM98's `SourceRow` claim was right, but by way of `authority` rather than `source`.

**RM88 rode along, and closing it needed one decision rather than any new capability.** The entry had
carried a technical blocker beside its policy question — a remote read, priced against "a path whose
current cost is one `upload_folder`". Detailing it showed the real cost is `create_repo` plus **two**
`upload_folder` calls, in the one tier permitted to fetch, so the read was always marginal and the
policy was the only thing holding the item. Decided **refuse unless `--force`**: `upload` reads the
published `manifest.json` at `data/<name>/v<version>/` and compares `artifact.digest`, refusing a
*different* artifact. Identical bytes are **not** a collision, which is load-bearing rather than tidy —
`upload_module` writes two commits and documents a re-run as the recovery when the second fails, so a
presence check would have refused exactly that retry. It fails **open** on an unreadable remote
(nothing established a collision, so nothing asserts one), and the flat path stays unguarded because it
means *latest*. New `PublishCollisionError`, reported as `ALREADY PUBLISHED` rather than
`UPLOAD FAILED` — the module is fine; the remote is what disagrees.

**The wider half of RM88 shipped as an ask, not a fix, and consumers should read it.**
`upload_folder` adds and replaces and **never removes**, so a recompile that stops emitting a table
leaves the previous release's parquet beside a manifest that does not attest it — a union of two
releases, on the **flat path, every republish**. The format's answer is that an unattested file is not
part of the module, and it is the right answer; what stops it being true is that the discovery path
fetches no manifest and probes named files, so a fossil parquet makes a module read as the wrong
*kind*. `delete_patterns` was **declined**: it cleans nothing on a module nobody republishes, does
nothing for a consumer that probes, and is one wildcard from dangerous (HF filters with `fnmatch`,
whose `*` crosses path separators, so a single `*.parquet` would delete every archived version's
parquets). The fix that closes it is the reader's, asked in **INTEGRATION_0_6 § 2.8** with the
mechanism and the failure — the RM27 shape: a finding about a downstream reader is an explicit ask,
never an implication.

**One fix broke a test, and that is the release in miniature.** Making `EutilsSettings` call `load_env()`
where it reads `NCBI_API_KEY` turned `test_eutils.py` red on a machine with a key in `.env`: it used
`monkeypatch.delenv`, and `@test-no-credential` says `setenv(VAR, "")` — a rule written down, explained,
and violated one file away from where `test_literature_terms.py` states it beside its own fixture.

## 2026-08-17 — the triage loop's own lint found two bad markers, and a link guard that was editing consumer prose

**Shipped in 0.6.1**, which is the "next patch whenever one is cut" this paragraph promised. Loop
maintenance rather than format work: nothing here touches a model, a parquet, a manifest field or any
published signature. The live consumer inbox is empty and stayed empty;
all of this came from running the ledger against the **history** file, which is the check that an empty
inbox is not an all-clear.

**A link guard was quietly rewriting what a consumer said, and the ledger caught it.**
`schema/tests/test_doc_links.py` requires every relative markdown link to resolve, and it exists because
an item moving live→history breaks every pointer at it. Consumers have started citing `RMn` items by
link inside their reports, so when RM89 shipped, S35's quoted prose held a link the guard called dead —
and the pass that archived the next item retargeted it to keep the suite green. That is the one edit the
triage loop forbids: a report is evidence and moves byte-for-byte. It also moved S35's fingerprint, so
the section read `revised`, our own edit impersonating a consumer revision. The prose is restored to what
was written, and the guard now exempts everything below a section's `<!-- triaged: -->` marker in both
consumer documents — replies stay checked, since they sit above it. A new test asserts a genuinely dead
anchor still survives inside quoted prose, so the exemption cannot rot into a no-op.

**A marker held a git commit sha instead of a fingerprint, and it failed twice.** S36's read
`sha cbeeb8f` — a real commit here, seven characters where `MARKER_RE` wants twelve, which made the
marker invisible and the section indistinguishable from one answered before the ledger existed. The
compounding half is the one to remember: with no marker visible, `reply_end()` falls back to the
single-paragraph rule, so paragraphs two onward of the reply leaked into the fingerprint and the value
the ledger *reported* was wrong too. Restamped, then re-run until it read `current`.

**Fixes adopted inward from the published gist.** The generalized copy of this loop is where other
repositories' fixes arrive, and two had been sitting there: `RULE_RE`, so a trailing horizontal rule is
no longer hashed as if a consumer had written it, and the archiver's closing line, which still told you
to add a row to an index table that became a contents list. Adopting `RULE_RE` re-scored four markers
(S2, S6, S7, S12 — the reports ending in a `---`); they were restamped on the proof that the ledger read
all-`current` immediately before, which shows the delta is the function and not the prose.
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md) gains the sync-in procedure, including the one gate
on auto-adopting — does it move a fingerprint — and the standing outward debt (the watcher's
branch-pause has not reached the gist).

**Three stale "0.6.0 is not cut" claims corrected**, in both S35's and S36's replies and in the live
inbox's preamble, which told consumers the newest tag was `v0.5.4`. `v0.6.0` is tagged at the commit
this batch sits on. Tagged is still not published, so the rule those paragraphs exist to teach —
answered is not installable — is unchanged, and only its example moved.

## 2026-08-17 — weights declare a scale, and GWAS effects get their own table (S36 / RM90–RM92)

**`just-dna-format` + `just-dna-compiler` + `just-dna-enricher` 0.6.0 — cut and tagged `v0.6.0` later
the same day; this entry read "uncut" until then.** Three items from one
consumer note about authored `weight` values: the column declares no scale, every module means
something different by it, and published GWAS effects are often better grounded than a hand-set
curator score. The note asked for one specific repair, which is barred; what shipped is the machinery
that makes the underlying want satisfiable instead.

**Measured while triaging, and it reframed the whole batch: `weight` is authored zero times in this
repo.** Nine of the sixteen reference examples carry a `variants.csv`; four carry a `weight` column —
`hboc_palb2` 16 rows, `hfe_hemochromatosis` 13, `par_boundary` 3, `shox_par1` 10 — and **every cell is
blank**. The column has never been dogfooded here, which the 1.0 review of whether it survives now has
as a data point.

- **The enricher will not fill `weight`, and `gwas_effects.csv` is where the effect goes instead
  (RM90).** MODULE_LIFECYCLE § Stage 3 names `weight`/`direction`/`effect_size` among the cells no tool
  fills; a null one means *the author has not modelled this*. There is a sign trap under the request
  too — `weight` is positive=protective while a GWAS beta is positive on the effect allele. So the
  seventh derived-fact table carries the Catalog's published effects beside the authored column, and
  `weights.parquet.weight` stays 100% authored. **A per-row precedence rule was refused** as putting
  two methodologies in one summable column, and so was splitting such a module in two: the split
  criterion would be source coverage rather than methodology, and membership would churn on every new
  paper.
- **`effect_unit` is the load-bearing column, and the corpus proves it.** rs1800562 carries 186
  published associations across **62 EFO traits in 12 distinct effect units** — `SD units`, `SD` and
  `s.d.` are three spellings of one; `g/dL` and `g/dl` differ only in case; 138 rows carry the
  Catalog's uninformative `unit`. `manifest.gwas_effects.units` publishes the set, so a consumer sees
  that those betas are not poolable without reading the parquet. **42 of 195 rows name no effect
  allele at all** (the Catalog writes `rs4149056-?`) and are counted rather than dropped — real
  evidence that cannot be weighted in any direction.
- **A study can finally say what its magnitude is relative to (RM91).** `StudyRow` has carried
  `effect_size` + `effect_measure` since 0.3 with no `effect_allele`, while `VariantRow` has had one
  since the same release precisely because `ref`/`alts` plus a sign cannot recover it. One optional
  column plus a check on the same mode ladder, in **both** `validate_spec` and `compile_module`; it
  reads resolved evidence only and **withholds** on an unresolvable row rather than reporting.
  `artifact.digest` moved on exactly the ten examples carrying a `studies.parquet`, and
  `content_signature` on none.
- **A module can declare what its weights mean (RM92).** `weighting:` — `scale`, `method`, `note`, all
  free text — in `module_spec.yaml`, copied to the manifest, out of both identity halves and dropped by
  `reverse_module`. Deliberately no closed vocabulary and deliberately no precedence field.
- **Running the new pass against a real module broke it twice**, and neither failure was reachable from
  a recorded fixture. A 404 is the Catalog's *empty answer* — it holds only variants with a published
  association — and the pass read it as an outage and died on the first variant of
  `hfe_hemochromatosis`. And `pvalue: 0.0`, which the Catalog really publishes past float64's subnormal
  boundary, was discarding whole associations through a `ValidationError` on one derived column; the
  number is withheld, the verbatim string kept, the row survives (189 rows became 195).
- **A prediction the measurement refuted, recorded rather than quietly dropped.** The link cache exists
  because `pmid`/`trait`/`ancestry` sit behind `_links`, making the pass `1 + 2N` requests per variant;
  it was expected to collapse most of that because associations share studies. It saved **nothing** —
  382 requests, zero hits, since each of rs1800562's associations names its own study. Hence
  `--no-study-facts`, added because of the number rather than in anticipation of it.
- **The first source here with no named licence.** EBI states the Catalog's terms in prose, so
  `license` is null. `commercial_use` stays `None` — the page permits "use" but conditions it on the
  original data owners' terms, which for an aggregator of thousands of publications are not
  established. Unknown neither permits nor refuses: `taints_commercial_use` requires an explicit
  `False`, so it warns rather than gating.

## 2026-08-17 — the publisher stopped dropping most of the artifact (S35 / RM89)

**`just-dna-compiler` + `just-dna-enricher` 0.6.0, uncut.** One item, answered and built the day after
it was filed. `just-dna-lite` replied to the three questions RM84 and RM89 had put to them
([S35](CONSUMER_SUGGESTIONS_HISTORY.md)), and the answer that unblocked RM89 also carried a finding of
their own: the publisher's `_ALLOW_PATTERNS` was not just refusing table-only modules, it was **dropping
the data of the ones it accepted**.

**Measured before, over the sixteen reference examples compiled and run through `plan_upload`:** seven
refused outright, and eight of the remaining nine published an artifact whose `manifest.artifact.files`
attests parquets — by name, sha256 and size — that were never uploaded, so the `artifact.digest` in the
published manifest cannot be reproduced from what arrives. **Fifteen of sixteen wrong**; only
`grch37_build`, a bare SNP core with no sidecar and no 0.4-family table, was correct. `sources.parquet`
was in the dropped set every time it existed, which is the half the consumer found from their end — a
module published this way arrives with no licence terms and their report footer renders *"Not stated"*.
Nothing is known to have been published through this surface, so this is *would publish*.

- **The allowlist is derived, never hand-kept.** The compiler's `_OUTPUT_FILES` is now public as
  `ARTIFACT_PARQUETS` and `just_dna_enricher.upload` imports it, so a new table family reaches the
  publisher in the commit that adds it. `LEAD_PARQUETS` joins it — `weights` plus the nine 0.4 families —
  which is what the consumer's discovery actually probes.
- **`_REQUIRED` is replaced by three positive rules**, most specific first: the plan must carry every
  file the manifest attests; `weights.parquet` never travels alone; at least one lead parquet must be
  present. The first is a self-check as much as a module check, so publisher and compiler cannot drift
  apart silently again. An absent or unreadable `manifest.json` **withholds** rather than refusing,
  which is what keeps RM84's four version reasons intact.
- **Re-measured after: 16 of 16 publish and all 16 digests verify.** Nothing that published before stops
  publishing; the only new refusals are `weights.parquet` alone and a directory with no annotation table.
- **RM84's two asks are answered and the segment spelling is settled** — `v<version>` verbatim stays,
  and a nested versioned subdirectory does not disturb their scan, by construction. Both remaining fixes
  are theirs. Recorded in [ENRICHER.md](ENRICHER.md), along with the one consequence they raised and we
  are not fixing: nothing prunes the versioned copies, so the collection grows one artifact set per
  release.

## 2026-08-17 — the 0.6 PT2 batch: five items built, and three of the proposal's own numbers corrected

The second 0.6 design round ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md), decided 2026-08-16) sorted
twenty-one open items into five to build and sixteen to defer. All five are here, built as five
independent lanes and merged in the order the proposal fixed. **Everything is additive under P3/P8 and
all three packages stay at 0.6.0**, which is uncut — no version moves.

**What shipped.**

- **RM55** — a fractional copy number matched no bin, silently, `--strict` included. The defect was
  never a type (the bin bounds have been `float | None` since 0.4) but three semantic rules keyed on
  the measure kind. `MeasureBinRow` gains an optional `measure_tiling` (`{quantised, continuous}`) and
  `CopyNumberRow` gains `modifier_copy_number` beside `modifier_cn`, read through
  `effective_modifier_copy_number`. The shared-endpoint and gap rules now read an **effective tiling**
  resolved per bin group — declared, else inferred from a fractional bound on a `quantised`-defaulting
  kind, else the kind's default — and the inference announces itself. `modifier_cn` is deprecated
  warn-only and goes at 1.0. The unconditional 0.6 warning is now conditional;
  `FRACTIONAL_MEASURE_PHRASE` is byte-identical, because a warning's text is an API.
- **RM87** — an expanded row was indistinguishable from an authored one, and a consumer produced 3,762
  false findings from it. `VariantRow` gains stamped, compiler-managed `locus_index` and `locus_count`
  (defaulting to `0` and **`1`**, so `locus_count > 1` is a predicate a reader can apply holding one
  row). Both are `exclude=True`, so no `content_signature` moves. Reverse prefers the stored column and
  keeps the encounter-order recompute for a pre-0.6 artifact.
- **RM72** — four `VALID_VERIFICATION_CHECKS` members were emitted by nothing. `check-identifiers` now
  records `gene_symbol_currency`, `trait_currency` and `gene_locus_agreement`; `check-acmg` records
  `acmg_secondary_findings`. Unconditional, no flag: an optional record is ambiguous between "not run"
  and "ran without the flag". **Both commands' "Writes nothing" promise is reworded** — they write no
  authored cell and record that the question was put. `merge_records` no longer lets a `skipped` record
  displace a `ran` one.
- **RM84** — the publisher now writes `data/<name>/v<version>/` alongside the flat `data/<name>/`,
  which keeps meaning *latest*. Enricher-only; no schema, no digest, no signature.
- **RM82** — an editor's line endings un-closed a module. The attestation binding now normalizes
  `\r\n` → `\n` before hashing, through a **separate** entry builder: `manifest.inputs[]` and
  `artifact.digest` deliberately keep following raw bytes, because they answer a different question.
  The trap was that `size` is inside the hashed listing, so normalizing only the digest input would
  have been a no-op that looked like a fix.

**Three of the proposal's own claims were measured and found wrong.** They are corrected in place, and
they are the reason the batch's standing rule is that every claimed movement is measured rather than
predicted:

- RM82's *"a one-time invalidation of every `module_hash` in existence"* is **7 of 16**. A binding
  moves only where an authored file really carries `\r\n`, and the half of the corpus that does is the
  **machine-written** half — `csv.writer`'s default terminator is `\r\n`, so the rewrite an author
  actually performs is normalization *toward* LF.
- RM87's *"twelve of sixteen"* is **nine**. Exactly nine reference examples carry a `variants.csv`, and
  those nine are exactly the nine whose digest moved; seven are table-only.
- RM55's evidence rule contradicted itself on `activity_score`: read broadly, a fractional value
  switches the rules "whatever its kind's default says", which produced **three false coverage gaps on
  a shipped module** (`cyp2d6_structural` bins activity scores at 0.25/0.5/1.25/2.25). The inference
  fires only against a `quantised` default — only `quantised` states a grid to contradict.

**Measured signature movement for the whole batch**, taken per lane against a baseline so each move is
attributable: `artifact.digest` moves on **eleven** modules (RM55's five ∪ RM87's nine, three
overlapping) and `manifest.verification.signature` on two, where re-closing dropped records attested
over the old bytes. **No `content_signature`, no `sources.signature` and no `resolution_signature`
moved anywhere.** P4 scopes the digest movement to a fixed `compiler_version`.

Two smaller repairs rode along because they are the drift their own neighbours warn about: the
enricher's verification-recorder docstring named three call sites where there are now seven, and
`authored_input_entries` claimed a coupling to `manifest.inputs` that the code has never had.

## 2026-08-16 — the triage loop's two Python tools are `.py`, and why that mattered

No library change; repo tooling only. `.claude/triage-state.sh` and `.claude/triage-archive.sh` are
**`.claude/triage-state.py` and `.claude/triage-archive.py`** — they were always Python with a
`#!/usr/bin/env python3` shebang, and the extension was a standing invitation to run them the one way
that breaks: `bash` ignores a shebang, reads the module docstring as commands, and reaches
`import hashlib`, where `/usr/bin/import` is **ImageMagick's screen-capture tool** and treats its
argument as an output filename. One such run left four empty files named `hashlib`, `pathlib`, `re` and
`sys` in the repository root — the script's own imports, in order — and left them *silently*, because
`import` writes the file before failing on its security policy. Entries below this one name the old
`.sh` paths; they record what the files were called then and are left alone.

The rename is the fix — nobody types `bash foo.py` — but the same class of failure had two other
doors, now shut: `triage-archive.py` invokes the ledger through `sys.executable` and
`watch-suggestions.sh` through `$PYTHON`, so neither the exec bit nor the shebang is load-bearing at
any call site. `watch-suggestions.sh` stays bash, because it really is bash.

Three fixes came back the other way, from the generalized copy of this loop published as a
[gist](https://gist.github.com/winternewt/54b94bda01812be937b892146d1bb254): the archiver now refuses
when the history file is missing rather than dying in `read_text`, the watcher's event-line cap is
`CAP` rather than a hardcoded 8, and `stat -f %m` is tried where `stat -c %Y` fails. Two gotchas came
with them, both found while adopting the loop into a second repository and neither reachable here —
**the archiver verifies the move, not the verdict** (it will archive a section the ledger calls `new`;
the lint is running the ledger against the *history* file afterwards), and **a preamble line beginning
`**Status` is read as a block reply**, which marks every id it names answered and which `--backfill`
then stamps. Runbook §6 has both, and the gist has the correction that went the other way: its
`group_span` docstring claimed archiving shifts the *preceding* section's fingerprint, which this repo
had already checked and refuted — `fingerprint()` ends in `.strip()`, so an injected heading below a
section's prose leaves its hash alone.

## 2026-08-16 (later) — 0.6.0: S33 and S34, and a premise of ours that a consumer had believed

Two more field notes from **just-dna-lite**, from the same twelve-module annotation as S30–S32. One is
a real defect with 3,762 false findings behind it; the other is a five-section reply in which four
sections needed nothing built and the fifth was a doc of ours being wrong. Both are archived to
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md).

**S33 — a one-to-many expansion's other rows are well-formed, and nothing said they were there.**
An rsID resolving onto N loci is paired with each, so K authored genotypes become K×N rows and only the
member whose alleles can carry a genotype can match it. COMPILER.md has said so for a release, in the
authoring frame where an unmatchable row is inert. It is not inert to a *reader*: `TA/TA` beside
`ref=TA` at a ClinVar duplication/deletion pair is a well-formed reference homozygote carrying the
module's conclusion, and the reporting consumer queued 2,579 of them into one genome's `pathogenic`
section and 1,183 into `cancer` before catching it. Reproduced from our own corpus — nine multi-locus
keys in `pathogenic_clinvar`, two in `hboc_palb2`, every one same-position/different-`ref` — and the
fixture is now `compiler/tests/test_expansion_counts.py`.

The expansion stays; filtering it is refused for the two reasons already on record, and the reporter
argued that case themselves. What ships is `manifest.compilation.expanded_keys` / `expanded_rows`
(RM44's two-counts shape, `None` where resolution did not run so a catalog can tell "no expansion" from
"no measurement", out of `artifact.digest` and pinned by a recompile test) and the **read-side
contract** in SCHEMAS § *the consumer join contract*, where a consumer meets it rather than in the
validation discussion. Note that `expanded_rows - expanded_keys` is **not** the unmatchable-row count —
that needs a per-key authored-genotype number the manifest does not carry.

**Probing the report found two defects in our own reporting.** The expansion warning was emitted inside
the per-authored-row loop, so a site with two authored genotypes published the identical sentence twice
and each copy said *"expanded to 2 rows"* of an artifact that had gained four — `compilation.warnings`
is a published surface (RM44), so that is a wrong answer, not a repeated one. And
`_check_genotype_coverage`, the check S32 produced three days earlier, fired on that exact site with the
reason *"no ref is authored or resolved here"* of a site the table resolves onto two disagreeing refs.
Turning a new check on the new report is what found the second; it is the standing advice and it paid
again.

**RM87 is filed to correct a premise, not to defer one.** S33 declined to ask for `locus_index` in
`weights.parquet` on the grounds that a new column moves every module's digest and is therefore a 1.0
conversation. Under P3 it is a **minor** — the authored identity does not move — P4 scopes
byte-reproducibility to a fixed `compiler_version` anyway, and the 0.6 cost amendment prices a stamped
compiler-managed parquet column as *"approximately free… the cheapest thing this format can add"*. A
consumer talked themselves out of the right fix using a rule we retired on 2026-08-11, which is a
communication failure on our side. What is genuinely open is *which* column: `locus_index` alone is `0`
on a non-expanded row and on an expansion's first member both, so it needs `locus_count` beside it, and
a bare boolean forecloses the ordinal permanently under P5. The reporter is asked to state a preference.

Also corrected for them: their mitigation (withhold any locus spelled with more than one `ref`) misses
same-`ref` expansions, and one is instantiated here — `enrich --keep-par-twin` records a pseudoautosomal
locus on X and Y with identical alleles, which is what `reference_examples/shox_par1/` was built from.

**S34 — the brief promised fields nobody could install.** The consumer's own opening complaint, upheld:
a table of 0.6 fields was presented as *"also shipped since you last synced"*, and 0.6 is uncut (every
`pyproject.toml` reads `0.6.0`; `git tag` stops at `v0.5.4`). The standing rule, now written into the
reply: *"in the tree" means committed and nothing more* — check this file for whether the version was
cut. Of the five sections, §3 and §5 were closed consumer-side and needed nothing, §4 was already filed
as RM84 with their agreement recorded in it, and §2 was a documentation defect the previous session had
already fixed (SCHEMAS.md and `manifest.py` both said *a consumer* should apply the `fully_resolved`
trust rule; the reader is a **catalog**, and saying "a consumer" sent one hunting for a read path they
had deliberately not built).

**§1 is the one with work in it.** `verify_manifest` has no call site anywhere, and its
`require_marketplace` **defaults to the marketplace policy** — so one naive call site rejects every
locally-compiled module, ours included, since our compiler leaves `compiled_by` null by design. The
contract is right; the docstring listed the flag among the optional steps rather than as the fork it is,
and `schema/README.md`'s example used the default silently. Both now state the two policies, one per
install route, and both point at the pinned `public_key` as the guarantee that is actually load-bearing.
Beside it, `schema/README.md` still called `artifact.digest` *"the version's immutable content
identity"* — the exact wording S7 was filed against; SCHEMAS.md was corrected then and this copy was
missed. Last one in the tree.

## 2026-08-16 — 0.6.0: a consumer round, S30–S32

Three field notes from **just-dna-lite**, all out of one annotation of one WGS genome against twelve
modules. Two shipped whole, one shipped its authored half and routed the rest; the routing is the part
worth reading, because in each case the reported symptom and the fixable defect were not the same size.

**S30 — the genotype split had three copies, and the consumer's was the only one with no code to read.**
`_split_genotype` was private to the compiler, so a consumer joining `weights.parquet` re-derived the
rule from prose, got it wrong twice in opposite directions, and had no failing run either time to say
which was right — sorting the alleles raises nothing, it just matches a quietly larger set on phased
data. `just_dna_format.alleles.split_genotype` is the leaf now (format tier, stdlib, the
`parsimony_reduce` precedent), and probing turned up a **third** copy in `resolution.py`; both of ours
call it and a test asserts they are the same object. Contract: *a validated cell in, alleles in authored
order out*, never sorted. Dropping empty fragments makes the split total over any string and is **not** a
widening — `|A|G` splits here and is still refused by `_validate_genotype` (RM67), pinned by a test so
nobody reaches for this as a validator. The artifact half — `weights.parquet` splits, the 0.4 families
keep the string — is [RM81](ROADMAP_1_0.md#rm81--one-artifact-spells-a-genotype-two-ways), 1.0: it is a
retype of a published column, and the minor-legal parallel-column workaround is refused there as two
spellings of one value in one table.

**S31 — the unjoinable count RM44 filed against RM43, published as a number.**
`manifest.compilation.positional_rows` / `positional_rows_placed`, the same parts-not-a-ratio shape as
`vrs_alleles`: complete is `placed == rows`. Until now the only published record of whether a PGx table
joins to a VCF was the warning sentence a downstream registry substring-matches, which RM44 established
is an unversioned interface. `pgx_slco1b1_simvastatin` reports 9 of 9 beside a `fully_resolved: true`
that quantifies over zero variant rows. **Both fields are `int | None`**, and that is the second half of
the item: `0` is a real answer (no positional table), so defaulting to it would have a pre-0.6 manifest
report "no positional rows" for a 1,482-row artifact with every coordinate null — the vacuous-
`fully_resolved` failure re-made inside the field written to close it. `None` is *this compiler did not
count*, which is what every pre-0.6 manifest honestly is, and it is how a consumer tells the eras apart
without probing parquet. `UNJOINABLE_PHRASE` and its test **stay**: already-published artifacts carry
neither field.

**S32 — a site annotated for some of its genotypes and not the rest.** A consumer matches on
`(variant, genotype)`, so a genotype with no row is a subject with no answer; the reporter's curated
520-site module authors no homozygous-alternate genotype at 208 of them, with their subject homozygous
at 74. `_check_genotype_coverage` reports the missing members by reason, with both counts (genotypes and
sites, since one two-alternate locus can be missing two). It fires **only where the module already
annotates a site for two or more genotypes** — one genotype at a site is a rule that fires on the call
the author cares about, and `pathogenic_clinvar` is in that shape at 326 of its 327 sites, so the wider
version is a line on nearly every module ever drafted. Dogfooded on our own corpus first and it found
three true instances there, including `pathogenic_clinvar` stating both HBB heterozygotes at 11:5225715
and neither homozygote. Never demands an alt/alt pair (RM35), never guesses the reference, and skips
sites whose genotypes are not diploid nucleotide pairs — which keeps MT and non-PAR Y out with no contig
list. Warning in both modes, `validate_spec` only (its message carries a count, and a post-resolution
re-run would publish a second differently-numbered copy of the same finding).

**What S32 did *not* get, and why it is a routing decision rather than a deferral.** Whether a hom-ref
row can ever match is a property of the file a consumer brings — a variant-only VCF emits no record where
the sample matches the reference, a gVCF and an array do — so **which annotation path works against a
chosen data input is the annotator's call, not this format's**. No module-level "evaluate me against a
callset that can express the reference genotype" claim was built, the *presence* of hom-ref rows is never
reported (they are correct, and are what make a module work on array data), and restoration and
imputation stay on the consumer side. The item's second ask turned out to be already satisfied:
`mt_common_deletion`, `mt_heteroplasmy` and `shox_par1` populate `requires_callable` — the PGx half is
RM70.

Also corrected: the authoring skill's joinability symptom still described the pre-RM43 world and told
authors there was nothing they could do about it.

## 2026-08-16 — 0.6.0: RM73 closed, both halves, and RM80

**RM73 (phase boundary) — authoring is a process, and it now has an end.** A module could not say it
was finished, so every check that needed to know where a value came from was guessing. The mechanism
turned out to be one block: RM45 had already built the binding for another purpose — `verification.json`
hashes the authored files and the compiler drops the whole block when that hash no longer matches — so
what was missing was a record saying *a human declared this final* rather than *a pass ran*.

`VerificationDoc.closure` (`closed_at`, `closed_by?`, `signature?`) is written by the new
`just-dna-compiler close`, and by nothing else. **No new file, no new binding, no new proof-of-work**:
the closure rides the attestation, so an edit after closing un-closes the module for free, and it sits
outside `pow_digest`'s payload, so closing re-mines nothing and every attestation written before it
still verifies. `validate` stays read-only however cleanly it passes — a mark left by whatever happened
to run says only that something ran, which is the defect the item levels at a by-product attestation.
`--private-key` signs the closure over the authored bytes with the same key `sign` uses, turning
*someone closed this* into *this party closed this*; unsigned stays legal and still change-evident.
Closing refuses a spec that does not validate and **does not** refuse on a warning, or a module carrying
a finding no authored edit can clear could never be closed at all.

A compile (and the pre-flight) now warns when it publishes no closure — both modes, never `strict`, no
count in the sentence so the two runs de-duplicate. A closure that is *signed* and does not verify drops
the whole document: absence is a limit, a claim is a claim. `record_verification` had to learn to carry
a closure across, and only while the binding holds — the never-clobber trap a third time after
`SourceRow.dataset` and `draft_digest`, and it drops rather than re-binds one whose bytes have moved,
because only the author may make that claim again.

**No identity moved and the corpus is closed.** All sixteen reference examples compile to a
byte-identical `artifact.digest` and `content_signature` before and after being closed, measured rather
than argued; all sixteen now ship a closure, with a test asserting each is still current so an authored
edit fails loudly instead of decaying into a *stale* warning nobody reads.

**Whether to warn on absence was decided twice, and the probe behind the reversal is what blocks 1.0.**
The first analysis argued for silence, since `reverse` cannot re-emit the document, so a closed module's
`compile → reverse → compile` would warn on step 3 where step 1 was silent — and RM44 made
`manifest.compilation.warnings` a parsed surface. Two facts overturned it: the divergence costs nothing
enforceable (`artifact_digest` covers the parquet only, `manifest.json` is not in it, warnings feed no
signature, no round-trip test compares them), and without the warning the closure has **no consumer in
0.x at all** — a manifest field read by a catalog that does not exist yet is the designed-and-never-
delivered shape. But a *refusal* is not free the way a warning is: under the 1.0 gate a reversed spec is
unclosed by construction, so step 3 would refuse for every module. That is filed with three undecided
candidate answers in [ROADMAP_1_0 § RM73 (gate half)](ROADMAP_1_0.md).

**Dogfooding the closure against 61 foreign modules turned up three fixes, one of them unrelated and
bigger than the two that were.** `just-dna-compiler close` was run over every module spec directory in
`just-dna-registry`, `just-dna-lite`, `just-module-creator`, `clawbio` and `dna-agents` — copies, never
their trees. 30 closed and 29 refused, and **26 of the 29 refused because `module.version: 3` is an
`int` by the time YAML hands it over**, while RM17's SemVer coercion — written expressly to accept the
pre-0.4 corpus's `v2` and `3` — is a `mode="after"` validator the field's `str` check never lets it
reach. Quoted `'3'` coerced; unquoted `3` refused with *Input should be a valid string*, and unquoted
is the only way YAML spells a number. Widened at `mode="before"` (P3-legal — previously-refused values
become legal and nothing accepted changes); a **float** stays refused with the reason, since YAML reads
`1.10` as `1.1` and the authored text is gone before any validator runs. Every one of this repo's
sixteen reference examples quotes its version, so no corpus here could have found it.

The two closure bugs: `close` printed *Run `just-dna-compiler close`* as the first line of every
refusal, having faithfully echoed the pre-flight's warning to the one caller for whom it is already
answered (the RM77 class); and a module closed straight from its authored state published
`produced_at` beside `producer: null` and no checks — a timestamp for a run that never happened. After
the three, the same sweep closes 54 of 59 and the five refusals are real: two modules with no
`studies.csv`, two published registry modules carrying *inconsistent reference allele* contradictions
that `validate` and `compile` refuse identically, and one `<<REPLACE>>` template. Findings in
[DOGFOOD_0_6_FINDINGS § Round 3](probes/DOGFOOD_0_6_FINDINGS.md).

**RM73 (provenance half) — a drafted value that has not moved is a copy that can be *established*.**
Shipped the same day, and the half four separate items were actually asking for; it needed no phase
boundary to answer.

A drafting provider now hashes the table it wrote, projected onto the column its own cross-check later
reads, and stamps it onto the licence row it was already writing (`SourceRow.draft_digest`, new
optional column; `just_dna_enricher.provenance`). The check recomputes and compares. RM4's tautology
skip stops being a hopeful module-level guess and becomes a **conjunction**: this release *and* no
checked value moved since.

- **Scoped to the checked column, not the row.** A ClinVar-drafted module always has edited rows —
  `genotype` is a placeholder the human must fill — so a whole-row hash would never match once.
- **Raw CSV cells, not models**, because the same function must run at draft time, when the table is
  full of `<<REPLACE>>` that the models refuse to load by design.
- **Uniform across all three providers**, which closed two tautologies nobody had filed:
  `pgx_draft` writes `function_status` out of CPIC and the PGx check compares that column against
  CPIC; `clinpgx_draft` writes `evidence_level` out of ClinPGx and the ClinPGx check compares that.
  Both were publishing a structurally guaranteed `findings=0` into `verification.json`. CPIC was also
  the one provider recording **no `dataset`**, and now stamps one.
- **Per-leg in `enrich_pgx`**, so the CPIC leg skips while PharmVar — an independent authority —
  still runs.
- **Removed:** `ClinSigAudit`, the copied/authored/no_record bucketing, `EnrichmentResult.clin_sig_audit`
  and its CLI line. They existed only because the module-level marker could not see a per-row edit, so
  `strict` paid for a lookup to recover the split. **The mode ladder went with them** — the check now
  behaves identically in both modes.
- **Behaviour change:** a licence row naming the right release but carrying **no digest no longer
  skips**. Nothing that was checked stopped being checked; a module waved through on a claim is now
  examined.
- **Identity:** `draft_digest` is outside `SOURCE_FACT_FIELDS`, so `sources.signature` moves nowhere
  and `content_signature` is untouched (`pgx_slco1b1_simvastatin` still `sha256:8173dab7…`). A
  recompile's `artifact.digest` moves for any module with a licence table.

**RM80 — `annotations.parquet` carries the `genotype` that distinguishes its rows.** Retro-filed from
a downstream consumer report: `variant_key` is not unique there and never could be (poly-effect is
real), so consumers had to dedup before joining, and the authored column deciding *which call* an
annotation applies to was in no column. It is now carried **and in the dedup key** — carrying without
keying would let two genotypes sharing a conclusion collapse onto a row naming one of them, turning a
missing answer into a wrong one. Reverse reads which of three keyings an artifact carries; both legacy
branches preserved. `content_signature` unmoved.

## 2026-08-18 — consumer note: `just-dna-lite` adopts format 0.6.1 / compiler 0.6.1 / enricher 0.6.2

No change here; recorded so the other consumers are not surprised. Done on a branch, against
`INTEGRATION_0_6.md` § 3's just-dna-lite list, with registry `0.17.0` bumped in the same commit range
(its floor is `just-dna-format>=0.6.1`, and `version.contract_compatible` compares installed *format*
versions, so the two pins cannot move apart). Field notes are **S40**.

- **`locus_count > 1` replaced the `ref`-spelling guard as the expansion predicate** (RM87), which is
  the S33 follow-through. The old guard is kept beside it as the pre-0.6 fallback, because every module
  we have published predates the column. Both are needed and the gap between them was measured, not
  assumed: on a compiled same-`ref` fixture (`shox_par1` with its `resolution.csv` twinned onto chrY),
  the grouped `ref` test finds one spelling at each of the two positions and withholds nothing, while
  `locus_count=2` withholds both. Restoration is where this matters — an unobserved hom-ref row at a
  locus that is one of N is a fabricated result, not an ambiguous one.
- **The report's genotype split now calls `alleles.split_genotype`** (S30's public leaf), and ours was
  wrong in a way the corpus cannot show: it split on `/` only, so a phased `"A|G"` came back as the
  single allele `["A|G"]` and the row rendered with **no zygosity**. Nothing we ship authors a phased
  genotype, so no fixture drawn from real modules could have caught it. Both our splitters — the
  Python one and the engine's vectorized polars twin, which cannot call the leaf per row — are now
  pinned against it over a cell list that deliberately includes `A|G` and `G|A`.
- **Discovery decides a module's shape from `manifest.artifact.files`** (§ 2.8's ask), falling back to
  probing where there is no manifest, which is every module on HuggingFace today. `None` rather than an
  empty set is what makes that safe to adopt now. Demonstrated on a directory holding an unattested
  `weights.parquet` beside an attested `pharm_variants.parquet`: probing answers `weights` and the
  attested list answers `pharm_variants`, so the fossil really does decide the module's *kind*.
- **Two hand-kept lists were deleted rather than updated.** The HuggingFace publisher's allowlist named
  six side tables where 0.6 has nine, so a module carrying any of the three new fact tables would have
  published a manifest attesting parquets the upload never sent — the same defect S35 found upstream,
  one repo over. It now derives from `ARTIFACT_PARQUETS`. Separately, two copies of "which authored CSV
  leads a module" named four of the ten families, so a `heteroplasmy`- or `copynumbers`-led module
  counted **zero** authored rows and was always routed to the enrichment half of `/check`.
- **The licence sidecar is cleared through `layout`, not by name.** Our drafters' stale-file sweep
  unlinked `sources.csv` literally. That is fine at the spec root and wrong under `derived/`: the sweep
  cannot reach `derived/sources.csv`, so `sidecar_write_path` finds it as the existing copy and merges
  into the **deprecated** spelling, which the module then keeps for good. Measured both ways on the
  pre-fix tree (`['derived/sources.csv']` before, `['licensing.csv']` after). `sidecar_candidates` made
  it three lines.
- **Nothing changed for § 8.** We hold no `except` around any enricher pass, so there was no handler to
  reorder and nothing that had been silently dead. The 0.6.2 floor is taken for the registry's sake and
  for the unavailability subclasses if we ever want them.
- **Not done, deliberately:** the ten modules in `data/interim/v1_port/` are **not** rebuilt or
  republished. That is the maintainer's call (`docs/MODULE_RELEASE_0_5.md`), and leaving them as 0.5
  artifacts keeps the mixed-era read paths — `_annotations_keying`'s three generations, the pre-0.6
  `ref` guard, `UNJOINABLE_PHRASE` — under live test rather than under test only by fixture.

## 2026-08-16 — consumer note: `just-dna-lite`'s annotating engine moves onto 0.5

No change here; recorded so the other consumers are not surprised. `just-dna-lite` migrated its
*producing* side to 0.5 last August and left the *consuming* side on the 0.2 shape. The annotating
engine has now been moved; the report follows in a second pass. Three things worth knowing:

- **A `pharm_variants`-led module could not be annotated at all.** `weights.parquet` splits the
  genotype into `List(Utf8)` and the 0.4 families keep the authored `"C/C"` string, so joining either
  to a VCF's `List(Utf8)` genotype raised `SchemaError`. Filed as **S30**; the engine now coerces the
  lead table's genotype to `List(Utf8)` before joining, mirroring `_split_genotype` exactly — **not
  sorted**, so one artifact does not end up with two spellings of a genotype — after which `pharmgkb`
  annotates rather than aborting the run.
- **A lead table is now classified by its schema, not its family name.** `diplotypes`, `pgs`,
  `allele_function` and the binning families carry no per-variant key, and the engine used to die on
  `ColumnNotFoundError` — taking every other selected module's annotation with it. They are skipped
  with the reason recorded, so adding a family to the format no longer breaks a consumer that has not
  learned it yet.
- **A shared ALT is not a shared variant.** Joining on `(chrom, start, genotype)` and dropping the
  module's `ref` let `G>A` match a module's `GTGTCT>A` at the same locus. On one real sample that was
  **6 of 9** reported `pathogenic` findings. The engine now requires `ref` agreement where the module
  states one — and we checked that cheap string equality does not disagree with
  `just_dna_format.alleles` on the set it can reach: once the genotype has matched, a differing `ref`
  means the two records delete different numbers of bases, so `event_profile` calls all six a
  **positive contradiction** and both survivors a match, with no "unknown" residual. Pinned by a
  test, because it holds only of that reachable set — comparing allele strings is the wrong test for
  indels in general.

Two more came out of reading **PROPOSAL_0_6** against our own code, and both were live here:

- **RM60 was biting us in production.** We strip a leading `chr`, so an hs38DH-aligned sample's
  `chrM` became `M` — a contig no module writes — and **every mitochondrial annotation was dropped
  without a word**. One of our three real samples is exactly that (35 rows), and `heteroplasmy` is an
  entire table family about mtDNA. Fixed by routing our contig column through `vrs.normalize_chrom`
  instead of maintaining a second, weaker folding.
- **RM64 was a latent gap.** Our rsid join keyed on the raw ID cell, so a spec-legal `rs123;rs456`
  record would have matched nothing. Zero occurrences in our two samples, so this is a fix ahead of
  the failure rather than after it.

**S29 was answered in the same round as [RM80](ROADMAP_HISTORY.md#rm80--annotationsparquet-had-no-column-for-the-thing-that-distinguishes-its-rows)** — `annotations.parquet` gains `genotype`,
keyed `(variant_key, genotype, conclusion, negatives)`. Our report pass will join on
`(variant_key, genotype)` as instructed rather than shipping the local dedup we had planned, which
the reply rightly notes is lossless only for as long as it happens to be. **S30 is open.**

## 2026-08-15 — 0.6.0: RM74–RM79, the fix round's own findings

Round 2 of [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) — the findings the fix round produced by
reading the code around each repair — was grouped into RM74–RM79 on 2026-08-14. The first two are
worked here. Both are **enricher-only**: no parquet, no model, no manifest field, so the corpus is
untouched and nothing versions but the network tier's own next patch.

**RM74 — the drafting providers read their sources wrong.** ClinPGx joins the genes one annotation
names with `;`, the same separator its drug list already had a named constant for, and both readers in
`clinpgx_draft` treated the whole cell as one symbol. Re-probed against the provisioned snapshot:
**396 of 16,087 rows** carry a `;`, and `--gene VKORC1` silently dropped the three rows of `rs17886199`
(published as `PRSS53;VKORC1`). The filter matches per member now.

*What a plural cell writes* was the one real choice, and two of the three candidates are refuted by
facts rather than by taste. **One row per gene is illegal**: `gene` is *outside* `PharmVariantRow`'s
dedup key, so the copies collide on `(variant_key, drug, genotype, phenotype_category, annotation_id)`
and the compiler refuses the module — the structural difference from `drugs`, which *is* in the key.
**Picking from the cell alone has no rule to pick by**: the pharmacogene is first in `CYP3A5;ZSCAN25`
and second in `ANKK1;DRD2`, `CYP2A7P1;CYP2B6` and `PRSS53;VKORC1`. So the answer is the CPIC `gene.chr`
move — write the member the *request* selects, which is a lookup in what the caller already stated, and
otherwise **withhold and name the genes the cell held**, aggregated by cell. An empty cell reads as
*not stated*; the joined cell is false about its own column and matches no consumer's gene filter.

Two more in the same loop: `skipped_unidentified` was counted **before** the `--gene` filter, so on any
narrowed draft the "records the source could not identify" number was inflated by the rest of the
database — which destroys the one thing it is for. And `test_draft_declared_build.py`'s location
fixture was keyed `"location"` where `cpic.defining_variants` reads `"sequence_location"`, so the
nested dict was always `{}` and the file's claim to cover a coordinate-carrying defining variant was
hollow — third instance of that class after S21's registry and D6-2's `_MOVABLE`. Repaired with the key
*and* an assertion that the coordinate reaches `haplotypes.csv`, which is what makes the key
load-bearing.

**RM75 — a complete result destroyed by an incidental failure.** `CpicClient._get` called
`raise_for_status()` and wrapped only *shape* failures into `CpicError`, so an exhausted retry ladder
left a raw `httpx.HTTPStatusError` that walked through both of `enrich_pgx`'s per-leg handlers — the
handlers written under *"One source failing must not sink the pass"* — and took PharmVar's answer with
it. The retrying half is `_request` now and the translation sits **outside** it: wrapping inside would
make `retry_if_exception_type` a no-op, so a test pins that the ladder survived the split. **The
finding named only CPIC and PharmVar had the identical hole**, which is worth stating because repairing
one leg makes that comment true in one direction only — the guarantee would hold or not depending on
which source went down.

`cpic.knows_drug` is caught now (it exists only to sharpen a sentence, and every substantive query has
already returned by the time it is asked), so an optional message-enrichment call can no longer discard
a finished draft. Its `bool | None` tri-state had been designed and never delivered *from the live
client*, which is why the raise escaped: the handling existed and nothing could reach it. The failure
gets a **third** wording rather than reusing the snapshot one — "the snapshot cannot answer" is fixed by
going live, "the request failed" by re-running.

And `spec_genome_build`'s deliberate raise no longer tracebacks out of `draft`/`draft-panel`. That
regressed *because* the declared-build defect was fixed: routing three providers through a shared
precondition owes the same addition to each of their handlers, which `_DRAFT_PRECONDITION_ERRORS` now
carries. The check also moved to the top of both providers — it reads one file beside the spec and was
landing after a published ClinVar snapshot had been provisioned.

**RM76 — an unfinished authoring state passed every gate, including `--strict`.** `SourceRow` is a
plain `BaseModel`, not an `AuthoredModel`, deliberately: it is a machine-produced reference fact,
grouped with the other four sidecars. S21 then made it **draftable**, also deliberately, because it is
the only fact sidecar a human writes and the only table the compile licence gate reads. Both decisions
were right and nobody reconciled them. Re-probed on `hfe_hemochromatosis` with `source=<<REPLACE>>`: the
module compiles green under `--strict` and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]`
inside the block its own `signature` covers — a signed module's attribution ledger naming a template
placeholder as the source it accounts for.

The guard lands on the model rather than through the base, with `ModuleSpecConfig` as the precedent —
standalone for its own reasons and guarded all the same — so the classification stays true and the
other four sidecars stay out, since no template is ever generated for them. It refuses in both modes,
which is not a choice: a load error is fatal in both.

Two things the repair turned up. A **vocabulary** column was catching the stub by accident (`layer`
refuses the token as a non-member), which is why the free-text half stayed open — and why the first
draft of this item's own test came out **green on the unfixed code**, since "some error mentions
`<<REPLACE>>`" is satisfied by the vocabulary message quoting it back. And `draft.stub_template`'s
docstring has printed the guarantee *"an unreplaced stub cannot compile … in both modes"* all along
with nothing checking it; it is now asserted over every `DRAFTABLE` kind, parametrized rather than
listed, because the defect was a model quietly outside a set.

No corpus movement: a `mode="before"` validator that only raises changes no accepted value, verified
against `artifact.digest` / `content_signature` values recorded independently in ROADMAP_0_7 and
CLAUDE.md. The general question underneath — what marks *authoring* as unfinished, rather than one
token as unreplaced — stays [RM73](ROADMAP_HISTORY.md#rm73-phase-boundary--authoring-is-a-process-and-it-now-has-an-end).

**RM77 — the genotype diagnosis told the author about the wrong thing.** `GT` is `0/1`; `genotype`
wants the bases. Pasting the `GT` field is the obvious first guess and therefore the single most likely
mistake in this column, and `0/1` fell through to the nucleotide-grammar wall — a sentence reciting
what an allele may be that never says those digits are **indices** into the record's own REF/ALT list.
`0/1/1` was worse *because of* 0.6: the ploidy-message fix gave it a confident, correct explanation of
the two-allele ceiling, which is about the wrong thing, and a correct sentence aimed at the wrong
defect sends the author to change the wrong cell. So the diagnosis runs ahead of the arity branch, with
a test pinning that a base-spelled triploid still gets the ceiling message and this one does not.

It changes no verdict — every cell it matches was already refused — and it is the `mode="before"`
diagnosis shape `reject_reserved` / `reject_authority_keys` / `reject_misplaced` already share,
reaching a *value* rather than a column name. Nothing legal can look like a GT cell: `ALLELE_PATTERN`
is `^[ACGT]+$`, a symbolic allele is bracketed, `*` is one character. It reaches `PharmVariantRow` for
free, since the grammar has lived on `AuthoredModel` since 0.5, and that is pinned rather than assumed.

**And RM63's correction was itself an overclaim — the third turn of one screw.** The comment read
*"Read a pipe here as **heterozygous**, phase recorded but unaddressable"*. `VariantRow(genotype="C|C")`
loads, and `1|1` is an ordinary phased homozygous call. The original comment claimed a pipe encodes
which homolog an allele sits on; RM63 refuted that correctly and replaced it with an unchecked claim
about zygosity; the 0.6 unit that carried the wording onto the printed `describe` output dropped the
zygosity word on the way, so **the contract an author reads has been right since then and only its
source was wrong.** A correction is exactly where this happens: the reviewer checks the claim being
removed, not the one going in. The comment now keeps the history of both wrong versions, and a test
pins that `C|C` loads.

**RM78's two fixes — the VRS reason surface's remaining blind spots.** `*` still landed in the
compiler's indel bucket: 0.6 gave the symbolic class its own permanent reason in `_vrs_gap_reason` and
`_recompute_vrs_id` and guarded `*` and `.` on the *enricher* side, and neither compiler function was
told — so an unobservable allele in `resolution.csv`'s `alts` was reported as *"an indel or MNV … re-run
it online"*, the same false class D1-2 had just fixed for symbolic alleles, offering a remedy that can
never apply. Filed as having no instantiation and upgraded when it turned out to have one: `*` **passes**
`LiteralSequenceExpression`'s `^[A-Z*\-]*$`, so before the enricher guard it would have been normalized
and handed a content-addressed id for a state that is not a sequence. Three reason classes now, split by
the P5 line the predicates already draw — *which variant is this, unspelled* versus *could the call see
an allele at all*. **Severity could not have caught this**, and the test says so: the indel branch it
fell into is also tier-blame, so the verify matrix read `warn` before and after.

`refget_supports_build` answered `True` for the two inputs `refget_accession` raises on. Its docstring
says it is *"the question `refget_accession` raises on"*, and for `None` and `""` it was answering the
opposite — a printed claim the code does not honour, in the tier the other two build on, on the guard a
caller reaches for *precisely* to avoid the exception. The old reasoning (*"an unset build is the
format's default"*) imports a spec-layer fact into the identity layer: the GRCh38 default lives in each
signature, and an explicitly passed `None` is a caller who has not threaded the row's build through —
the class `test_build_call_sites.py` walks the AST to prevent. Every other build gate in `vrs` already
read it that way. Both sides now read one predicate, so RM15's second table cannot re-open the gap.

The third part of RM78 is a decision and stays open: whether a stored VA against a symbolic allele is
the row's contradiction rather than the tier's limit.

**RM78's decision — a stored VRS id against a symbolic allele is the row's contradiction, and the
grammar was settled first.** `_recompute_vrs_id` returned tier-blame (a warning in both modes) for a
symbolic allele carrying a `ga4gh:VA.…`. Tier-blame is for a finding **no authored edit could clear**
(P5), and deleting the cell clears this one — so the finding sat in the class whose own test it fails.

The escalation only follows if a present id can *only* be a VA minted for a different allele, and
nothing had established that: `vrs_id` was checked for well-formedness alone (`ga4gh:<TYPE>.<digest>`,
five types) while its description says *"GA4GH VRS allele id (`ga4gh:VA.…`)"*. So the grammar went
first. `validate_vrs_allele_id` makes `ResolutionRow.vrs_id` and `FrequencyRow.vrs_id` `ga4gh:VA.`-only
and names the type it refuses. It makes no passing module fail — a `ga4gh:SL.…` already reached
`_verify_vrs_ids` and came out as a **mismatch** ("recomputed and different, so corruption"), an error
in both modes with the wrong explanation — and it has no instantiation, the test this repo applies to a
tightening: 844 ids across all sixteen reference examples, every one a VA. `validate_vrs_id` keeps its
lenience and its documented reason, because "is this a well-formed VRS id" and "may this column hold
one" are different questions and only the first should be generous.

With that settled the escalation is mechanical: a recorded id on a symbolic row can only name some
*other* allele, which is the *inconsistent reference allele* class — catchable offline, an error in both
modes. The message says which cell to delete and that the allele keeps its identity through
`variant_key`.

**The asymmetry is pinned rather than assumed.** The coverage side still reports a symbolic allele as a
permanent gap and warns in both modes: an **absent** id there is the ordinary correct state, and
refusing would make every structural module uncompilable for a reason no edit could fix. Absence is a
limit; a claim is a claim. `mt_common_deletion`, `cyp2d6_structural` and `pathogenic_clinvar` still
compile under `--strict`.

**RM79 — two honest counters disagreed, so the compiler stopped carrying the dead weight.**
`manifest.literature.missing_count` counted `exists is False` over every row in `literature.csv`; the
`citation_existence` verification record counted the module's *current* citations. `literature.csv` is
merge-not-clobber, so it keeps a row for a citation since deleted from `studies.csv`, and the two
numbers disagreed in a published manifest with nothing wrong in the module.

**The item's own framing turned out to be the wrong question.** It asked whether `manifest.literature`
should describe the table it is named after or the module's current citations — and probing found both
blocks already publish their denominator (`row_count`, `subjects`), so a reader could reconcile them.
What nobody had decided sat upstream of the counting: why is a row nothing joins to in the artifact at
all? A literature row for a citation no study and no bin names is dead weight, present only as a side
effect of merge-not-clobber. So the compiler discards it and the CSV keeps it — that file is the pin
that makes a re-run cheap, and carrying the row onward was a separate thing nobody had chosen. The two
counters now share a subject **by construction** rather than by documentation.

Four things pinned rather than left to be re-derived. The check sees every row and everything after it
sees the kept ones, since reporting what was dropped needs the full list — and the warning now reports
an action taken rather than nagging about a file the author is not expected to tidy. An empty citation
set discards nothing, because a module citing nothing cannot tell a stale sidecar from citations not
yet authored, and emptying the table on the first reading would delete a whole enrichment pass's
output. **Both** citation sites count (RM47) and the stakes rose with them: blind to bin `pmid`s the
compiler used to warn about a threshold-grounding citation and would now *discard* the row that
evidence lives in. And the round trip narrows once and **converges** — `reverse_module` rebuilds the
CSV from the parquet, so a reversed copy carries the kept rows only, which is a deterministic narrowing
of a machine-written derived sidecar rather than a P7 breach (RM69's reading), and lap two discards
nothing.

No corpus movement — no reference example carries an uncited row, verified by recompiling all sixteen —
and therefore no corpus coverage either, so the behaviour is pinned by fixtures.

Suite 2262 → 2264.

## 2026-08-14 — 0.6.0: the dogfooding fix round — sixteen findings worked, nine more found

[DOGFOOD_0_6.md](probes/DOGFOOD_0_6.md) built six probe modules against the shipped CLIs and produced a
ledger, [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md), whose own header said fixing was a separate
round. This is that round: twelve parallel units in isolated worktrees, one finding or group each, every
one exercised against a real module rather than only the suite. Ten `fix` findings landed, five
`surface` ones became **RM68–RM72** in `ROADMAP_0_7.md` ([now closed](history/ROADMAP_0_7.md); what is
still waiting moved to [ROADMAP_0_8.md](ROADMAP_0_8.md)), and the work turned up **nine
new findings** which are filed in the same ledger as Round 2 rather than in a new file.

**Nothing in the corpus moved except where a new column made it legal.** All sixteen reference examples
were compiled before and after: `content_signature`, `resolution_signature` and `sources.signature` are
identical on every module, and `artifact.digest` moved on exactly the three carrying `literature.csv`,
because `LiteratureRow` gained an optional `doi_checked`. That is the additive case Principle 3 permits
as amended — the column is outside `LITERATURE_FACT_FIELDS`, so no authored identity moved.

The findings worth knowing outside this repo:

- **`enrich` crashed on any module carrying a symbolic allele** (D1-1). RM5 shipped the grammar in 0.6
  and the VRS tier was never told, so `<DEL:4977>` reached `ga4gh.vrs` and raised an unhandled
  `ValidationError`. Probing the fix showed the crash is the *character class*, not the spelling:
  RM58's `.` raises identically, and RM59's `*` **passes** the sequence pattern, so it would have been
  handed a content-addressed id for a state that is not a sequence. All three are guarded, in both
  tiers, each with its own permanent reason class rather than being called an indel.
- **The rsid↔coordinate check was documented, named in the check vocabulary, and unreachable**
  (R2-15). It lives on `resolve_variants`, whose only non-test caller is the compiler's deprecated
  `_legacy_resolve`; `enrich()` never called it, and a row authoring both halves was never compared.
  Found only because wiring its attestation required counts that did not exist. Generalize it: asking a
  pass to publish a number is how you discover it never computed one.
- **Six of the twelve unemitted `VALID_VERIFICATION_CHECKS` members are now emitted** (D4-1) —
  `literature` writes three, `pgx` and `vrs mint` one each, and `enrich` gained rsid↔coordinate.
  `merge_records` had been built and tested for a multi-command document no two commands produced; two
  real commands now exercise it. The remaining six are RM72, four of them blocked on
  `check-identifiers`/`check-acmg` advertising "Writes nothing".
- **`vrs mint` records a skip, not a pass.** Its member names the cross-check against a *source-reported*
  id, and nothing in the workspace fills that input — so recording the alleles it minted as `subjects`
  would assert a comparison never made. Coverage rides in `detail` instead.
- **A `<<REPLACE>>` template stub in `licensing.csv` compiles green under `--strict`** and reaches
  `manifest.sources` inside the block its own signature covers (R2-8, unfixed). `SourceRow` is not an
  `AuthoredModel`, so the "a generated stub must be unable to compile" guarantee never reached the one
  fact sidecar a human writes.
- **RM62's rule was one-sided as shipped.** "Narrow the authored bound to float32" rests on
  `float32(0.3)` being above `0.3`; `float32(0.9)` is **below** `0.9`, so narrowing an authored `0.9`
  drops a row whose measurement never went through float32. The rule that survives is the one
  SCHEMAS.md's heading always gave: compare *in* float32. Now on the `measure_max` description, where an
  author reads it.
- **RM63's own correction overclaimed** (R2-14, unfixed). It replaced a false statement about homologs
  with *"read a pipe as heterozygous"*, and `C|C` loads — `1|1` is an ordinary phased homozygous call.
  The printed descriptions carry the true half; the comment still does not. A correction is where this
  happens: the reviewer checks the claim being removed, not the one going in.

Two process notes. **Eleven units were green alone and one pair was not green together** — a test
pinned `"indel/MNV"` for an allele another unit was concurrently reclassifying as symbolic, which only
merging could catch. And **three of the nine new findings came from re-verifying a report rather than
relaying it**: one claim was refuted outright (R2-7, raised twice and now closed against every path),
one brief was wrong about where its own subject ran (R2-15), and one instruction had to be disobeyed to
avoid printing a false claim (D5-2).

## 2026-08-13 — 0.6.0: the design round, built — eleven items, the VCF 4.4 cluster, and a charter amendment

**The whole of [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md)'s build list shipped**, in eleven parallel lanes
over one day. The reasoning stays in the proposal; the outcomes and what probing changed are in
[ROADMAP_HISTORY § 0.6.0](ROADMAP_HISTORY.md#060--the-design-round-built). This entry is the release
view: what a consumer will notice.

**A charter amendment landed first and alone, because four decisions turn on it.** The Constitution
ruled on whether a change is *legal* and said nothing about what a legal change *costs*. It now does:
a **parquet column is approximately free** (materialized, derived, no human types one), a **derived CSV
is half** (machine-written, but a human can still edit it, and that should be discouraged), an
**authored schema is full cost** (the rare author writes it). This grants nothing new — legality is
still Principles 3 and 8, decided first — but it retires the instinct that there were "too many tables",
which was right about some additions and wrong about others with no stated way to tell which. Its first
consequence is written into SCHEMAS.md: `resolution.csv` is a build-time artifact with exactly two
consumers and **gets no parquet, deliberately**.


### What a module author will notice

- **Coordinates now reach the pharmacogenomics tables** (RM43). A PGx module authored with rs-numbers
  used to compile to parquets with every coordinate null, so a consumer matching a patient VCF by
  position matched nothing — silently, as an empty result rather than an error.
  `reference_examples/pgx_slco1b1_simvastatin` went from nine null rows to `12 / 21178615 / T / A,C`.
- **Symbolic and structural alleles are authorable** (RM5): the five closed VCF types with the length
  inside the token (`<DEL:1500>`, `<CNV:TR:30>`). A length-less one is dropped with a warning that says
  *dropped*, and refused under `--strict`.
- **`*` is writable** (RM59) — the allele that could not be observed, which any joint-called VCF emits
  and which no row could previously carry.
- **`chrM` validates** (RM60), folding to `MT`. The gate was stricter than the normalizer beside it.
- **A bin can cite its own threshold** (RM47): `MeasureBinRow.pmid`. The bin row cites, the citation
  table describes — and a `studies.csv` row may now name no variant at all.
- **A VCF pointer can name its namespace** (RM53) — `INFO/DP` versus `FORMAT/DP` — and say which element
  it means on a multi-valued field (RM54). Both are widenings; a bare key stays legal.
- **Two new derived tables**: `gene_validity.csv` (RM24) and `clinical_assertions.csv` (RM25).
- **A PMC id is refused by name** (RM50). `PMC 3110566` used to be *accepted* as PMID 3110566 — a real
  id for an unrelated article — so a cell that compiled before may refuse now. That is the fix.
- **The manifest can say what was checked** (RM45): a `verification` block, or nothing at all, which
  reads correctly as *says nothing* rather than as a pass. Every field is marked untrusted.

### Two behaviour changes worth reading before upgrading

- **Two reference examples were re-authored because they were wrong**, and their `content_signature`
  moved: `mt_heteroplasmy` wrote `source_field=AF` meaning this person's heteroplasmy fraction, while
  the spec's `AF` is the *cohort* frequency of that ALT — both floats in `[0,1]`, both binning cleanly,
  and one of them tells a carrier they are asymptomatic on the strength of how rare the variant is in a
  reference panel. `htt_repeat_expansion` gained an element rule for the same class of reason.
- **A wrong-build coordinate is now an error in both modes** (RM48): a position past its contig's end,
  or a contig only the other assembly names. It is arithmetic rather than judgement, so it does not
  follow the mode ladder. rs-number recovery against Ensembl's permanent GRCh37 service reports and
  never fills.

### Corpus effect, measured rather than assumed

Across all eleven reference examples: `content_signature` moved on **two** (the two re-authored above),
`artifact.digest` on **seven** (new optional and stamped columns — Principle 4 scopes byte
reproducibility to a fixed `compiler_version`), `resolution_signature` was **gained** by the four
table-only modules carrying a `resolution.csv` and no `variants.csv` — precisely the hole RM45 closed —
and the source signature moved nowhere. Test suite **1535 → 2046**.

### One pattern, found three times independently

Three lanes shipped the same defect and each was caught by its own code review: a check re-run after
resolution counts the **expanded** rows, so an rsID resolving to several loci reports one finding twice
with different numbers; message-dedup keys on the sentence and cannot collapse them, and both reach
`manifest.compilation.warnings`, which RM44 established is a surface consumers parse. Measured at
"1 row(s)" beside "2 row(s)", and at 328 beside 337 on `pathogenic_clinvar`. The rule now in CLAUDE.md
covers this and its opposite: **re-run a check after resolution exactly when resolution changes its
input, and never when the message embeds a count.** `_check_contig_ploidy` is not a counterexample — it
had to *move* behind resolution because resolution fills `chrom`.

Also fixed, both pre-existing and both found by a lane reviewing someone else's shipped work:
`reverse_module` re-emitted the deprecated `sources.csv` spelling, so a module and its own round-trip
disagreed on a published manifest field; and the `derived/` near-miss guard caught nothing it claimed
to, so authored tables placed under `derived/` compiled **green and empty, silently**.

## 2026-08-12 — 0.6.0: the version bump, and the first three items of the line

**All three packages move to 0.6.0 together** (`schema`/`compiler`/`enricher`), and the
inter-package floors move with them. The two entries below dated 2026-08-12 — `manifest.readme` and
`manifest.derived` — were already labelled 0.6.0 while every `pyproject.toml` still read 0.5.4; the
bump makes the number real, and everything from here lands under it. Cutting a release from the
branch is still the user's call.

### RM44 — publish the denominator, so a vacuous `fully_resolved` reads as one

`manifest.compilation.fully_resolved` is `all(...)` over the module's variant rows, so on a module
carrying no `variants.csv` it is `all()` over an empty list — **vacuously true**. The field is not
wrong; it cannot say *which* question it answered, and the trust rule its own comment documents
(`resolution_mode == "strict" or fully_resolved`) reads it as a module-level verdict. A consumer
followed that comment and badged two modules that join to no VCF, then repaired it by
substring-matching the 0.5.3 warning's prose — a bad place for a sentence to be.

`Compilation.resolution_subjects` is the count the flag quantifies over, taken **after** the
one-to-many rsID expansion because that is the list `fully_resolved` iterates (`pathogenic_clinvar`:
328 authored rows, 337 subjects). `fully_resolved=true` beside `resolution_subjects=0` is then
self-evidently vacuous, with no new vocabulary and nothing to parse out of a warning. Five of the
eleven reference examples are in that state today.

**It restates a number `Stats.weights_rows` also carries, and the code says so.** Measured, the two
are equal on every example, because the materializer emits one weights row per in-scope variant row.
That is a property of the current transform rather than a contract, and `Stats` is documented as
card/detail *display* facets — a consumer keying trust on it would be keying on a coincidence in a
block that promises none. A denominator belongs beside the flag it qualifies; a test pins the two
together so a divergence becomes a decision instead of a drift.

Not done, deliberately: `fully_resolved` stays `bool` (consumers branch on it directly, so a `None`
is a breaking read for all of them — the reporter asked for this explicitly), `UNJOINABLE_PHRASE`
and its pinning test stay (this makes the vacuity visible, it does not make the tables joinable —
that is RM43), and there is no second counter, per RM45's settlement of three things into three homes.

### RM51 — `licensing.csv`, so the major only has to remove a spelling

`sources.csv` records licence *terms*, and its name collides with the `source` **column** that means
"which link answered" in four other tables — which is why SCHEMAS.md needed a three-row table to
explain which of `studies`/`literature`/`sources` is which. A rename landing only at 1.0 would have
to **add** a spelling at the major and remove one at the next. Landing the alias in a minor inverts
that: every module drafted from here carries the new name, so 1.0 removes rather than adds. The old
spelling is **deprecated here** — warn-only, read exactly as before — and goes at 1.0, which is the
cadence the 0.6 charter amendment settled, and this is the case that prompted it.

Minor-legal for a checked reason: the fact sidecars are deliberately outside `_INPUT_FILES` (their
identity is the fact hash, not the raw bytes), so the filename enters no identity at all. Proven by
compiling one module under both names and comparing — same `artifact.digest`, `content_signature`,
`manifest.sources` and `resolution_signature`.

**What does not come along, taken knowingly**: `sources.parquet` is inside `artifact.digest` and read
by name, and `manifest.sources` is a published key. Both renames break a reader, so the whole 0.x
tail reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is a real legibility
regression against today's single consistent (bad) name, and it is the price of not paying for the
rename twice. A test pins it, so a well-meaning follow-up cannot "finish" the rename into a
published key.

The item estimated **five** enricher write sites; there are **nine**. `record_source_terms` and
`merge_sources_file` now take the spec directory rather than a path, so none of them can name a
spelling by hand. The ninth was `pgx.py` — the one pass whose *primary* output is this table and the
only one calling `write_sources_csv` directly, so its literal would have re-created the retired name
behind the alias's back.

### RM49 — `derived/` tolerated on input, so a legible spec tree recompiles where it sits

Nothing in a flat spec listing says which files a human wrote and which the enricher produced. A
registry gave its publishers a `derived/` tree and found a downloaded module does not recompile where
it lands, so their layout stayed transport-only (flatten on upload, re-split on download). This makes
the layout a *tolerated* input location — never required, never canonical: `reverse_module` still
emits a flat tree, and making `derived/` canonical would buy two supported layouts and have `reverse`
emit a tree older compilers in the same major cannot read.

**The write side had to be decided in the same change**, which is what kept this a design round.
Tolerating the location on input alone breaks on first use: `enrich` on a downloaded split module
writes to the root, leaving both copies — the collision, reached by following the documented workflow.
So the rule is RM51's, shared: **write to the file you read**, and **both present is an error naming
both paths**. Never a merge, never newest-wins — these tables are fact-hashed *and* hand-editable, so
two copies are two claims and preferring one discards a curator's override.

Scope is the machine-written sidecars only. An authored table does **not** get a second home, and the
asymmetry is the point: two legal places for `variants.csv` means a module can carry two with the
ignored copy invisible. `_check_misspelled_tables` follows into the subdirectory against the derived
names alone — without that, tolerating a location would put a typo'd `derived/varaints.csv` exactly
where the guard cannot see it, buying a convenience by re-opening the hole S16 closed. That is also
the argument against "search any subdirectory": one fixed name is the only version the guard can
follow. `manifest.derived` records the relative path, so `FileEntry.name` carries `derived/…` for a
split tree — legal there because that block is documented transport-only.

**The shared piece is `just_dna_format.layout`** — the names, the subdirectory constant, and one
resolver, in the schema tier because four parties must agree on this layout (compiler reads, enricher
writes, publisher uploads, registry re-splits) and every disagreement in `locations` so far has been
silent. Pure `pathlib`, so the dependency-light tier is untouched.

### A `-` where a `_` goes is now accepted in every closed vocabulary

Not an `RMn` — a usability defect found while writing the above. The enricher CLI already normalized
`--use non-commercial` on its way in, while `SourceRow` refused the identical string in a cell: the
surface an author learns the vocabulary from taught a spelling the file rejected. This DSL exists for
the human — if the project only wanted machine precision it would ship parquet and no CSVs — so a
separator slip in a categorical is an authoring cost the schema should absorb.

`vocab.match_vocab` is the one definition and `check_vocab` runs it, so every closed vocabulary gets
it and the CLI's private copy is gone. The value as written is tried first and both swap directions
after, so a future hyphenated member cannot be broken by this; the match **canonicalizes**, so what
is stored, fact-hashed and compared is always the declared spelling. Widening, never narrowing (P3):
everything that validated before still validates, and a value that names nothing still fails with the
full list. The evidence it was worth doing is in the diff —
`test_validate_agrees_with_compile` had used `non-commercial` as its example of an *invalid* value.

### Corpus and verification

Four reference examples move to `licensing.csv`; `hfe_hemochromatosis` deliberately keeps the old
spelling so the deprecation path stays exercised on a real module, with its README saying why.

All eleven reference examples keep their exact `artifact.digest`, `content_signature`,
`resolution_signature` and `source_signature` across the whole batch — compared through the CLI
against a pre-branch baseline, including under the split layout and the renamed file. The manifest
was never inside the digest; the filename and the location are not either.

## 2026-08-12 — docs: the round-1 field notes are retired, and two accepted asks finally land

**S27 + S28, refiled from `docs/CONSUMER_FIELD_NOTES.md`, which is removed in this pass.** That file was
the pre-0.4 round-1 thread: a consumer's report with the maintainer's answers written inline as
`↳ maintainer reply` blockquotes. It was a **second inbox**, with its own reply idiom, that
`.claude/triage-state.sh` cannot read — so while the live inbox correctly said nothing was owed, ten
accepted asks sat in a file no ledger covered. Establishing what shipped found eight delivered (several
over-delivered: `reference_sequence`, `requires_callable`, `acmg_sf` and `actionability` were promised as
*reserved names* and were **built as columns**; `repeat_alleles`/`heteroplasmy`/`pgs` froze in 0.4) and
**two never written at all**, both accepted at the time as "trivial, docs only":

- **S27** — the `effect_allele` liftover ref-flip caveat. What shipped instead is stronger than the
  requested caveat: 0.5 checks `effect_allele ∈ {ref} ∪ alts`, non-reconciliation is a named permanent
  blind spot in COMPILER.md, and a flipped reference base is caught by `verify_reference_alleles`. What
  was owed was the pointer from the **schema tier**, since a verify-only consumer never opens the
  compiler's docs. Now a paragraph beside `VariantRow`'s field list in SCHEMAS.md, naming RM48 for the
  hg19 authoring path.
- **S28** — the normative **consumer join contract**. The rule "absent from a variant-only callset ≠
  hom-reference" existed only inside `requires_callable`'s field *description*, which
  `describe`/`requirements`/`reference` print to an **author** — while the obligation binds the
  **consumer**. Documented in the wrong place for the party it binds, for three releases. SCHEMAS.md
  gains *The consumer join contract — three states, and the one that gets collapsed*: the MUST/MUST NOT
  as the reporter wrote them, the four columns that express it (`requires_callable`, `callable_from`,
  `quality_from`+`min_quality`, `MeasureBinRow.unresolved`), the "present but matching no bin" third
  state kept distinct from `unresolved`, and Kleene combination. No schema change — the reporter's own
  framing (a consumer concern, not a module field) still decides it.

**Also fixed, found while probing S28: a docstring claiming a diagnosis the code no longer produces.**
`vocab.reject_reserved`'s docstring illustrated itself with "`caller` fails differently from `xyzzy`",
but `caller`/`caller_version` were *dropped* from `RESERVED_NAMES_0_4` rather than built, so `caller`
takes the generic `extra="forbid"` message like any other stray column. The example now uses
`reference_db`, the set's only member, and records what it used to say. Same class as round 1's own
single code finding (A2, a stale comment contradicting shipped behaviour), which is a fair note on which
to close the thread.

**The durable lesson, and the reason the file is gone rather than annotated.** A feedback document with
its own reply convention is invisible to the loop that exists to notice unanswered work, and "nothing in
the live inbox" then means nothing at all. Do not start a third one. The two live asks were refiled with
the reporter's prose extracted byte-for-byte and verified with `diff` before the file was deleted; the
whole thread is recoverable from git history at `53f9260`. One archived section's consumer preamble links
to the removed file and that link is deliberately left dangling — editing evidence to tidy a reference is
the one thing the history file does not do.

## 2026-08-12 (later) — 0.6.0: `manifest.derived`, so the enricher's own tables can be served

**S26, reported by `just-dna-registry`.** A publisher asked which files in a spec directory are theirs.
The derived-fact CSVs — `resolution.csv` plus `frequencies`/`gene_metrics`/`literature`/`sources` — were
attested by no byte hash anywhere: `_INPUT_FILES` excludes them on purpose (they are **fact**-hashed,
because the enricher, a human override and `reverse_module` all legitimately emit different bytes for
the same content) and only their *parquets* are in `_OUTPUT_FILES`. Every route a registry serves files
through is defined over what the manifest attests, so a consumer could not fetch the table that produced
a parquet, or diff the two to see what the enricher actually decided.

`derived: list[FileEntry]` mirrors `logs` semantically — optional, absent-is-not-a-failure, out of
`artifact.digest` and `content_signature` — and `inputs` in locality: hashed **where the files live,
beside the spec**, not copied into the module dir, because each is its own parquet's content in another
encoding and a panel's frequency table should not ship twice. `_DERIVED_FILES` is derived from
`_FACT_TABLES` rather than hand-listed, for the reason `SOURCES_FIELDNAMES` once lost a column.
`verify_manifest(check_derived=True)` and `verify --check-derived` re-hash what is present.

**The trap this field creates is pinned by a test.** There are now two hashes over one file answering
different questions, and reading the byte hash as identity would call a legitimate re-emission
tampering — the exact failure the fact signatures exist to prevent. A test rewrites a sidecar so the
facts are unchanged and the bytes are not, and asserts the byte hash moves while the fact signature and
`content_signature` do not. Verified against the previous commit on four reference examples: all three
signatures byte-identical, with `grch37_build` correctly getting an empty list rather than a fabricated
one.

**The second half is filed, not built — [RM49](history/ROADMAP_HISTORY_PRE_0_6.md#rm49--a-spec-directory-is-flat-so-a-legible-derived-layout-is-one-the-compiler-refuses).**
The reporter also asked that a `derived/` subdirectory be *tolerated* on input, so a downloaded module
recompiles where it sits. It is not the one-line fallback it looks like: `spec_dir / "resolution.csv"` is
resolved in eight places across two packages, and tolerating the layout on input without deciding the
*write* side breaks on first use — running `enrich` on a split module writes to the root, so the module
carries both copies, reached by following the documented workflow rather than by misuse. Two copies of a
fact-hashed, human-overridable table are two legitimate claims, so the collision cannot be resolved by
newest-wins or by merging without discarding a curator's override. Three candidate repairs are refused
in the item with reasons, one of which would re-open the hole S16 closed.

## 2026-08-12 — 0.6.0: `manifest.readme`, so a module's prose can travel with it

**The first change in this line whose legal release is a *minor*, and the version is therefore not
bumped here** — all three packages still read 0.5.4 and cutting a release is the user's call. A new
optional manifest field is additive under Principle 3 (the 2026-08-11 amendment): existing modules keep
validating, `schema_version` is unchanged, and the field is out of `artifact.digest` entirely, so it is
cheaper than a column. That makes it minor, not patch, purely because it is a new field rather than a
better diagnosis on an existing path.

**S25, reported by `just-dna-registry` relaying `just-module-creator`.** A publisher shipped a
`README.md` beside `module_spec.yaml`; the registry stored the bytes and then could neither serve them
nor tarball them, because both paths are defined over *what the manifest attests* and `ModuleManifest`
had no field for a readme. `logo` was the precedent and the asymmetry was pure accident of history: a
logo can be listed, hashed, fetched, verified and swapped; prose with all the same properties had none
of the machinery. The motivating module is an 11-row set of explicitly *candidate* findings — most from
a preprint, one association not significant — where the README saying so is the single most important
artefact for anyone deciding whether to install it, and it was the one thing that could not travel.

`readme: FileEntry | None` mirrors `logo` exactly: discovered from `manifest.README_CANDIDATES`
(`README.md` first, then the other stem and `md`/`rst`/`txt` in a fixed order, so two readmes on disk
cannot resolve by luck), copied into the module dir, hashed, and **outside both identity halves** —
`artifact.files`, hence `artifact.digest`, and `content_signature`. `verify_manifest(check_readme=True)`
and `just-dna-compiler verify --check-readme` re-hash it.

**Both identities, not just the digest, because the reporter's own argument needs both.** They rejected
putting `README.md` in `artifact.files` themselves: on an immutable registry a corrected typo in a
caveat would then cost a version number, and the corrected module would collide with its own predecessor
under a name-independent content-dedup check. That only holds if prose stays out of `content_signature`
too, so the tests compute both and a dedicated case rewrites a readme and asserts only its own hash
moves. Measured on six real reference examples against a baseline worktree: `artifact.digest`,
`content_signature` and `resolution_signature` byte-identical, each now attesting its `README.md`.
Inlining the text into `display` was rejected for the reporter's reason — a readme is unbounded (this
one outweighs its module's data) while `display` is inlined into every card a catalog serves.

**The publisher was the gap that would have made the field decorative.** `upload._ALLOW_PATTERNS` had
`logo.png`/`logo.jpg` and no readme, so a manifest would have attested a file the HuggingFace repo did
not carry — the same silent shape as ClinVar's unpublished `citations/` and ClinPGx's dropped
`LICENSE.txt`. It now imports `README_CANDIDATES` rather than copying it, so a spelling the compiler can
discover cannot fall out of what the publisher sends. (`logo.jpeg` is a pre-existing instance of that
skew, left alone: widening it is not this item's decision.)

Two adjacent corrections, both found by reading rather than reported:

- **`integrity.artifact_digest`'s docstring still called the digest "the version's immutable *content*
  identity"** — the exact wording S7 got corrected in SCHEMAS.md, against Principle 4, which makes the
  digest the **byte** identity and `content_signature` the content one. The docs were fixed when a
  consumer made that misreading; the code copy outlived the fix, next to the field whose whole design
  turns on the distinction.
- **`_check_misspelled_tables` advertised a README as the headline *tolerated* file** ("nothing outside
  the known table set is read, hashed, or in artifact.digest"). A readme is now read and hashed and
  still moves no digest, so the message names curation notes and a publisher's receipt instead, and the
  claim narrows to the one that is still true. S16's test asserts both halves together now.

Suite 1442 → 1448 (six new tests); every reference example still recompiles byte-identically.

---

**Entries dated 2026-08-11 and earlier — the whole 0.5 line and everything before it — are in
[CHANGELOG_PRE_0_6.md](history/CHANGELOG_PRE_0_6.md).** The split is the 0.6.0 version bump, not a change of
format: the archive is this same document continued downward.
