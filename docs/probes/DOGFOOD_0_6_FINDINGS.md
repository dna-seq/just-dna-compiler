# Dogfooding the 0.6 batch — findings

The bug list produced by running [DOGFOOD_0_6.md](DOGFOOD_0_6.md). One row per finding, each
reproduced against the shipped CLIs before it was written down. **Fixing is a separate round** —
this file is the ledger, not the work.

Severity is about what a consumer or author gets wrong because of it, not about how hard it is to
fix. `class` is the standing fix-vs-surface split: **fix** = a false claim, a misdiagnosis, an
unaggregated wall, a guard that is never reached; **surface** = the obvious repair is itself a design
decision, and the entry says why each candidate repair is wrong.

> **Status, 2026-08-14.** F1–F7 and F9, F10 were fixed in the D2 round itself, before the fix/file
> split was called, and landed in one commit that can be reviewed or reverted as a unit. **Everything
> from D1 onward was filed and has since been worked**: the rows below carry `(done)` where a fix
> landed, and the mapping from finding to pull request is at the end of this file. The `surface` rows
> became RM68–RM72 in [ROADMAP_0_7.md](../ROADMAP_0_7.md). Two rows are deliberately not `(done)`: D4-3,
> which is a design decision, and D4-1, whose fix half is six of its twelve members with the rest
> argued in RM72.

> **Status, 2026-08-15.** **RM74–RM79 are all done** — the six findings they carry (R2-1, R2-11, R2-3;
> R2-13, R2-4, R2-2) are marked `(done)` in the table below, with the outcomes in
> [ROADMAP_HISTORY § 0.6 dogfooding](../ROADMAP_HISTORY.md#06-dogfooding--the-fix-rounds-own-findings-repaired).
> Two things they turned up that were not in the findings: **R2-13's hole is on the PharmVar leg too**,
> which the ledger did not say and which matters because fixing one leg makes *"one source failing must
> not sink the pass"* true in one direction only; and **R2-1's write side had a decisive refutation
> nobody had reached for** — `gene` is outside `PharmVariantRow`'s dedup key, so "one row per gene"
> is not a trade-off, it is a module the compiler refuses. R2-8's repair is the *narrow* half — the
> guard now reaches `SourceRow` and `stub_template`'s printed guarantee is asserted over every
> draftable kind — while the question it asks from underneath stays RM73's. And RM77's own repair
> found a fifth thing worth the same note: its first candidate assertion, *"the message mentions
> `<<REPLACE>>`"* in R2-8's test, passed on the unfixed code because a vocabulary column quoted the
> token back — the R2-3 shape reappearing inside the round that was repairing it. And **R2-16 was decided against
> its own framing**: it asked whether `manifest.literature` should describe the table or the module's
> citations, and both blocks already publish their denominator — the undecided thing was upstream, why
> a row nothing joins to is in the artifact at all. Nothing here is open; the root the sprouts grow
> from is RM73.

> **Every open Round 2 finding now has an `RMn`.** The thirteen that needed action were grouped into
> **RM74–RM79** (`docs/ROADMAP.md`, active) on 2026-08-14, indexed in
> [RM_TOC.md](../RM_TOC.md), and each row below names the item that carries it. A finding reachable only
> from this ledger is unfindable, which is the mechanism RM_TOC exists to prevent — so the ledger records
> what was *found*, and the roadmap owns what is *left*. R2-7 is not a finding; R2-12 and R2-15 are done.

> **Round 2 is at the bottom of this file.** The fix round for the findings above turned up defects of
> its own — not by dogfooding, but by reading the code around each repair. They are recorded here rather
> than in a new file, for the reason CLAUDE.md gives about second inboxes: a backlog the ledger cannot
> see is a backlog nobody sees.

## The shape the batch has

Three findings are the same defect in three places, and it is worth naming: **a correction that lives
where the author does not read it.** RM63's phase wording is a code comment (D5-2); `ELEMENT_RULE_MEANINGS`
reaches `reference` but not `describe` (D1-4); RM62's narrowing rule reaches `docs/SCHEMAS.md` but not
the printed column description (D6-1), and D5-1 is the fourth — a printed description that is wrong
rather than absent. `describe`/`requirements`/`reference` are the authoring contract, which is the
lesson the 0-vs-1-based `start` docstring cost 3,038 rows to learn, and four 0.6 items landed just
short of it.

Two more are the same as each other: **a vocabulary or a mechanism built and then not wired.**
`VALID_VERIFICATION_SKIPS.unsupported` was emitted by nothing (F4); twelve of seventeen
`VALID_VERIFICATION_CHECKS` members still are, and `merge_records` is built for a multi-command
document no two commands produce (D4-1).

And one is the reason four of the others were invisible: **the corpus was uniform on every axis the
0.6 batch touched.** No symbolic allele reached the enricher, no module carried an attestation, none
of the two new binning kinds had an instance, and the round-trip sweep's own third signature had
never been compared (F9).

---

## D2 — `cyp2c9_warfarin_grch37`

Module: `reference_examples/cyp2c9_warfarin_grch37/` (README carries the reproductions).

| id | finding | class | severity |
|---|---|---|---|
| **F1** | **Every drafting provider ignores the module's declared build.** `draft`, `draft-panel`, `draft-clinpgx` all take a `spec_dir` and none reads `genome_build`. `enrich.spec_genome_build` — written for exactly this defect one release earlier — had **one caller**. CPIC/ClinVar/ClinPGx all serve GRCh38, so drafting into a `genome_build: GRCh37` module writes `10,94942290` for `rs1799853` (GRCh37: `96702047`) in silence. Two of the three write coordinates and can do harm; `draft-clinpgx` writes none. Hid because `test_pgx_draft.py`'s fixture declares `GRCh38` — the only drafting test that mentions a build. | fix (warn) + **surface** (refuse vs strip-to-rsid is a design decision) (done) | high |
| **F2** | **`clinpgx_draft` says the snapshot has no `gene` column.** It has one, populated on 15,331 of 16,087 rows, written *and re-read* by our own builder. `--gene` was refused with a false reason and `PharmVariantRow.gene` left empty. Root cause: `load_snapshot`'s hand-written `SELECT` listed six of eleven columns. | fix (done) | medium |
| **F3** | **`annotation_text` is written for 16,087 of 16,087 rows and read by nothing.** `conclusion` — the one column whose job is to say what the module claims — was synthesized as `"ClinPGx 655385012: C/C and warfarin — dosage"`, a restatement of the row's own key. Nothing flags a content-free conclusion. | fix (done) | high |
| **F4** | **The attestation records a check it could not run as having run clean.** On a GRCh37 module `verify_reference_alleles` caught `UnsupportedBuildError` per row and `continue`d, so `not_checked` stayed `None` and `verification.json` published `reference_allele: subjects 0, findings 0, skipped null` — and `genome_build_agreement: nothing_to_check` with the detail *"no authored ref disagreed with the reference"*, asserting a comparison that never happened. `VALID_VERIFICATION_SKIPS.unsupported`, whose comment names this case, was **emitted by nothing and asserted by no test**. Reproduced on `reference_examples/grch37_build`. | fix (done) | high |
| **F5** | **`draft --drug X` cannot tell a typo from a real drug CPIC scores differently.** `warfarin` and `notarealdrugxyz` produced byte-identical output. CPIC's warfarin guideline is real; it is a multi-gene dosing algorithm and so has no phenotype-keyed recommendation row. | fix (done) | low |
| **F6** | **The joinability warning recommended a re-run that cannot help.** `fill_applied=False` sat behind `if not placeable`, and on a non-GRCh38 module those coincide — so the author was told *"run `just-dna-enricher enrich` first"* one line below the warning explaining the fill was skipped **because** their module is GRCh37. | fix (done) | medium |
| **F7** | **`compile → reverse → compile` drops `manifest.verification` in silence.** Reverse cannot re-attest and must not invent one — but nothing said the block was going, and a module and its own round trip then disagree on a published field with nothing edited (the RM44 class). | fix (say so) (done) | medium |
| **F8** | **`resolution_signature` is not a round-trip invariant when the fill is skipped.** Injected rows for positional-table keys never reach a parquet on a non-GRCh38 module, so reverse cannot rebuild them. Forced by the RM15 skip: materializing them would mean joining a table across builds. | **surface** → **RM69** | low |
| **F9** | **The corpus round-trip sweep never compared `resolution_signature`.** `getattr(manifest, "resolution_signature", None)` — the field is on `manifest.compilation`. `None == None` for all eleven examples for the whole of 0.6, while the docstring explains why the signature is checked. `grch37_build`'s README asserts a fixed point on it that nothing verified (and which is a `None → value` materialization, not equality). | fix (done) | high |
| **F10** | **A "no snapshot" test that only fails on a machine that has one.** `setenv("JUST_DNA_CLINPGX_CACHE", "")` is the *credential* idiom and is inverted for a cache path: empty is falsy, so the ladder falls through to the default dir — where `cache pull` puts a snapshot. Green on CI, red on a provisioned machine. | fix (done) | medium |
| **F11** | **`requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption.** CPIC assumes an uncalled position is reference — literally `requires_callable=false` — and `haplotypes.csv`/`pharm_variants.csv`/`diplotypes.csv` have no such column. A star-allele module cannot record whether its call needed the defining positions to be callable. | **surface** (RM65-adjacent) → **RM70** | medium |

---

## D1 — `mt_common_deletion`

Module: `reference_examples/mt_common_deletion/`. The mitochondrial 4,977 bp common deletion, spelled
as RM5's `<DEL:4977>`, beside `m.8993T>G` (inside the deleted span) and `m.3243A>G`.

**One root cause behind the first two: RM5 shipped the symbolic-allele grammar in 0.6 and the VRS
tier was never told.** No reference example and no enricher test carried a symbolic allele before
this module — the corpus-uniformity heuristic, paying off exactly as the plan predicted.

| id | finding | class | severity |
|---|---|---|---|
| **D1-1** | **`enrich` crashes on any module carrying a symbolic allele** — reproduced on `<DEL:4977>` (D1) and independently on `<DUP:16000>` (D3), so it is the allele class and not one spelling. Unhandled `pydantic.ValidationError` out of `ga4gh.vrs`: `VrsMinter.mint` routes a non-substitution to `_mint_normalized`, which builds `models.LiteralSequenceExpression(sequence=alt.upper())` **outside** the `try` below it — whose comment reads *"A failure here is a live-service problem … never a reason to fail the enrichment."* Same shape as the `UnsupportedBuildError` defect recorded eight lines above it in the same function. | fix (done) | **high** |
| **D1-2** | **Offline, the same allele is misdiagnosed as an indel with a remedy that crashes.** `_vrs_coverage` reports *"an indel/MNV, which must be justified against the reference sequence — re-run without --offline to mint it"*. A symbolic allele names no sequence by construction, so no id is ever mintable — a permanent reason class, not an `--offline` limitation — and the suggested re-run is D1-1. | fix (done) | **high** |
| **D1-3** | **`_check_binning_grounding` exempts a variant-keyed bin in a module that has no `studies.csv`.** The function returns early unless there are **zero** study rows, then treats a bin as grounded because it names a variant "a study row can then name back" — the study row it has just established does not exist. A `heteroplasmy.csv` module stating four thresholds and citing nothing is green and silent; the same module on `repeat_alleles.csv` is warned. Reopens the S19 gap for the one binning kind a real MELAS/NARP module uses. | fix (done) | medium |
| **D1-4** | **`describe <kind>` omits `vocabulary_notes`.** It calls itself "the full machine description of one table kind" and prints `source_element`'s members without `ELEMENT_RULE_MEANINGS`, which reach only the whole-schema `reference`. The per-table command is the one an author authoring one table uses. | fix (done) | low |

### Checked and held (D1)

RM5's four placement cells (accepted with a length; warned and **DROPPED** on `variants.csv` without
one; **fatal in both modes** on `heteroplasmy.csv`, with the composite-tiling reason in-line);
**RM60 did not blind RM48** — `chrM:16600` is still refused against MT's 16,569 bp, which was the
seam the plan flagged as untested; RM58 keeps `.` apart from `<DEL>` *and* names the identity-split
consequence; RM59's `*` and the ploidy check do not collide (`*/A` is two-allele notation whatever
`*` denotes); RM53's collision warning on bare `AF` with the INFO-vs-FORMAT explanation, silent on
`FORMAT/AF`; RM61 accepts `gnomAD.AF` and `INFO/1000G`; RM43's fill reaches `heteroplasmy.csv`;
RM47's `pmid` works on a bin row. Round trip is a fixed point on `artifact.digest` and
`content_signature` with the symbolic allele verbatim in both tables.

---

## D3 — `cyp2d6_structural`

Module: `reference_examples/cyp2d6_structural/`. `copynumbers.csv` + `activity_phenotype.csv` — the
two binning kinds the corpus had **zero** instances of — with CPIC's own activity-score bins, probed
out of the published snapshot rather than recalled.

| id | finding | class | severity |
|---|---|---|---|
| **D3-1** | **The lengthless-symbolic-allele message names `<DEL>` whatever was authored.** `alts=<DUP:TANDEM>` is correctly refused, with the sentence *"A `<DEL>` that does not say how long it is …"* beside an example clause naming the real cell. The two halves of one message disagree about what is being discussed. | fix (done) | low |
| **D3-2** | **RM67's refusal does not make the documented divergence findable.** A polyploid genotype on a duplicated CYP2D6 — the spec's own polyploid example — is refused with a bare restatement of the grammar. VCF permits higher ploidy and this format deliberately does not; nothing in the message says so, so it reads as a syntax error. Every other deliberate refusal here names its own limit in-line (RM5's "a release away", the ploidy check's contigs, the VRS warnings' RM15). | fix (message, done) | medium |

### Checked and held (D3)

RM55 fires on `copy_number`, once, naming the field, citing §7.2/§5.6, giving the concrete `2.4`
failure, saying the gap check cannot see sub-integer holes, and pointing at 0.7/1.0 without implying
author error. RM56 fires once for the table, says **withhold**, and says withholding is not the
`unresolved` row. **`activity_phenotype` escapes RM35's unsatisfiable triangle for a reason, not by
luck**: no gap warning (scores are quantized on a 0.25 grid, so CPIC's holes at 1.0→1.25 and
2.25→2.5 are real), and a shared endpoint at 2.25 *is* an overlap error. RM53's `CN` collision warns
with the ploidy-factor consequence and `FORMAT/CN` is silent. RM54's `largest`/`largest_alt` both
accepted on one field. RM5's `<CNV:TR:30>` and `<DUP:16000>` accepted. RM59's natural `*/T` silent on
an autosome. The integer coverage-gap check still reports a real hole (10.0, 21.0), so RM55's claim
is about sub-integer holes and not a disabled check. **RM65/RM66's gating evidence is now a corpus
module** — filed as evidence, not as a defect.

---

## D5 — `fmr1_cgg_repeat`

Module: `reference_examples/fmr1_cgg_repeat/`. RM47's *fix* had no worked instance anywhere —
`htt_repeat_expansion` stays deliberately uncited as the example of the gap — so this is it: four
published FMR1 boundaries, each carrying its `pmid`, on chrX where a male sample is hemizygous.

Both findings are in the **printed authoring contract**, which is the surface the 0-vs-1-based `start`
docstring established is a contract and not commentary.

| id | finding | class | severity |
|---|---|---|---|
| **D5-1** | **`largest`'s meaning sentence assumes a ploidy the contig does not have.** `ELEMENT_RULE_MEANINGS['largest']` explains the rule as *"the longer of the sample's two alleles"* — a claim about a diploid record — and FMR1 in a male is the presentation the gene is known for. The rule itself is correct for one value; only the illustration is wrong, and it is the only member's sentence that reaches for one. | fix (wording, done) | medium |
| **D5-2** | **RM63's correction is a code comment, and the pipe form is not in the printed contract at all.** `describe variants.csv` gives `genotype` as *"Slash-separated sorted alleles, e.g. A/G"* — no `A\|G`, no mention of phase — while the validator accepts it, its own error message lists it, and `phased` is materialized and round-tripped. RM63's corrected wording (*"heterozygous, phase recorded but unaddressable"*) sits above the validator in `base.py` and nothing prints it. | fix (done) | medium |

### Checked and held (D5)

**RM47 holds in both directions and at both call sites**: bins carrying `pmid` silence
`_check_binning_grounding`; a module whose *only* citation is a bin pointer still has that PMID
fetched by `enrich literature`; the compiler does **not** report the resulting row as a stale orphan,
while a genuinely uncited row still is. RM47's subject relaxation works — a `studies.csv` row naming
no variant loads, validates and is skipped by the orphan half of `_cross_validate_studies`. RM55 fires
on `repeat_count` naming **`RUC`** and VCF 4.4 §3 (not the `CN` reasoning), on bins that tile the
integers cleanly and look fine — which is why it was made loud. RM56 fires once on the 10-wide
intermediate zone, names `CIRUC`, says withhold. Round trip is a fixed point. **RM66's gating
evidence** (AGG interruptions vs a `(gene, repeat_unit)` key) is now a corpus module.

---

## D4 — `hboc_palb2`

Module: `reference_examples/hboc_palb2/`. PALB2 at ClinVar's 3-star floor, run through every derived
producer in the documented order. Five of the plan's eleven zero-rows close here: the corpus had no
`verification.json`, no `gene_validity.csv`, no `clinical_assertions.csv`, no `frequencies.csv` and
no `gene_metrics.csv`.

| id | finding | class | severity |
|---|---|---|---|
| **D4-1** | **Five of seven checking passes attest nothing; 12 of 17 `VALID_VERIFICATION_CHECKS` members are emitted by nothing.** `record_verification` has exactly two callers — `enrich()` and `enrich_clinpgx()`. `literature`, `gene-validity`, `check-identifiers`, `check-acmg`, `dosage`, `pgx` and `vrs mint` each perform a check the vocabulary names, report it to stdout, and let the record die with the process — the sentence RM45's own docstring opens with as the thing it exists to fix. And it is a **claim**: that docstring states *"A separate command (`check-identifiers`, `literature`) writes once of its own, and the merge below is what keeps the two runs' records in one document"*. `merge_records` is built and tested for a document no two commands produce. Unreachable members: `acmg_secondary_findings`, `allele_function`, `citation_existence`, `citation_identifier`, `dosage_sensitivity`, `gene_disease_validity`, `gene_locus_agreement`, `gene_symbol_currency`, `provenance_quote`, `rsid_coordinate_agreement`, `trait_currency`, `vrs_allele_id`. | fix → **RM72** | **high** |
| **D4-2** | **`hint` reports every template stub twice** — once from its own per-column check, once from the model's `mode="before"` validator. A freshly drafted 109-row panel yields 219 findings for 109 defects. The CPIC aggregation lesson arriving through a different door: two layers reporting one cell rather than a loop over a source table. | fix (done) | low |
| **D4-3** | **The alleles needed to replace a `genotype` stub are only in `draft-panel`'s stdout.** A drafted row is rsID-only (identity whole or not at all), so the file does not state `ref`/`alts`; the pair is emitted once per row as a warning. The author's next action is an edit to a file that does not contain the information. Tolerable at 16 rows, not at the 761 the same command drafts for PALB2 at the 2-star floor. | **surface** (writing it into the row would fill an identity column a drafting provider must fill whole or not at all) → **RM71** | medium |

### Checked and held (D4)

**RM4's tautology skip on the module it was designed for** — skipped with the release named, the hole
named in the same sentence, and recorded as `skipped: tautology` rather than as a silent pass.
**RM31's hosting verdict on real disagreeing data** (`rs180177102` is `CA>C` in ClinVar and `CAA>C` in
Ensembl; the locus is dropped with the event-size reason). **RM45's staleness** — one edited authored
byte drops the block with both hashes named and the manifest *"says nothing rather than claiming a
pass"*. **RM45's determinism** — a no-op re-enrich reproduces `module_hash`, `signature`, `nonce` and
`difficulty` byte for byte; only the timestamps move. Every derived block reaches the manifest. The
one-to-many expansion carries its count; the MNV's `vrs_id` is reported *unverifiable* (a warning in
both modes — the tier's-limit half of the three-outcome rule). Round trip is a fixed point on all
three signatures.

**Not run:** RM4's `withdraw_stale_dataset` needs two ClinVar releases and one snapshot is
provisioned. Building a second from the same VCF under a different label would fabricate the
provenance the mechanism exists to protect.

---

## D6 — the corpus sweep

No new module: the adversarial pass over all sixteen examples, run after the five above landed.

| id | finding | class | severity |
|---|---|---|---|
| **D6-2** | **`test_derived_layout.py`'s movable-sidecar list was four sidecars behind the layout it tests.** `_MOVABLE` was a hand-written five-tuple naming `sources.csv` (the *deprecated* spelling) and omitting `gene_validity.csv`, `clinical_assertions.csv` (RM24/RM25), `verification.json` (RM45) and `licensing.csv` (RM51). Its comment said the list was written out deliberately, "so the test states the contract instead of echoing it" — and the contract it stated was 0.5's. Invisible because `_flat` discovers the first example carrying `variants.csv` + `resolution.csv` and no example carried any of the four; `hboc_palb2` carries all of them, and `manifest.derived` came back with two entries still at the spec root. Same shape as S21: a good discovery mechanism defeated by the one hand-kept list beside it. **Repaired in place** (the list is still written out, and a new assertion checks it against `_DERIVED_FILES`) — this is a test the probe artifact reddened, not a product fix. | fix (done) | medium |
| **D6-1** | **RM62's authoring rule is in the consumer docs and not in the authoring contract.** `docs/SCHEMAS.md` states it fully — a VCF `Float` is 32-bit, `0.3` widens to `0.300000011920928955…`, so an inclusive non-dyadic `measure_max` is missed by a float32 read, and the rule is to *narrow the authored bound*. `describe <kind>`'s `measure_max` says only *"Inclusive upper bound; None = open above. Inclusive on every measure_kind."* The word "narrow" appears **zero** times in `just-dna-compiler reference`. RM62 is a rule about **what to author**, and it reaches only the document the author is not writing from. Third instance of this shape in the batch, with D1-4 and D5-2. | fix (done) | medium |

### Checked and held (D6)

- **The four-signature ledger, all sixteen modules.** `artifact.digest`, `content_signature` and
  `source_signature` are a fixed point everywhere. `resolution_signature` moves on four, in two
  distinct shapes: `None → value` on the three modules carrying no `resolution.csv`
  (`grch37_build`, `mt_heteroplasmy`, `cyp2d6_structural` — reverse materializes the table from the
  parquets, nothing is lost, lap two is stable) and `value → value` on exactly one,
  `cyp2c9_warfarin_grch37`, which is F8's forced RM15 loss.
- **RM51's migration.** `hfe_hemochromatosis` carries the deprecated `sources.csv`; reverse writes
  `licensing.csv` and no signature moves.
- **RM49, all three halves.** Eight sidecars moved under `derived/` compile to an identical
  `content_signature` and `resolution_signature`; `manifest.derived` carries the relative paths and
  hashes so a registry can re-split; a copy at both locations is an **error naming both paths** and
  saying which spelling to keep; and a typo'd `derived/varaints.csv` is caught by the near-miss
  guard, which is the case that would otherwise compile green with zero variant rows. And **the
  writers follow the reader**: re-running `enrich` on a `derived/` module rewrote `resolution.csv`
  and `verification.json` in place under `derived/` and left nothing at the spec root — the
  second-copy collision RM49/RM51 made an error, arrived at by following the documented workflow.
- **The count rule holds across the corpus.** Only two warning shapes are compile-only — the
  one-to-many expansion count and the coordinate-authored/no-rsid count — and both take *resolution
  output* as their input, which is the side of the rule they belong on. No message appears with two
  different counts on the two sides.
- **RM62 and RM64 are both reachable from the published docs** (`docs/SCHEMAS.md` §§ on float
  comparison and on the ID column), so the 0.6 findings did land as prose. D6-1 is about the
  *second* surface, not about the first.
- **RM57's inversion warning, on the row type it exists for.** `requires_callable=true` with
  `quality_from=QUAL, min_quality=30` warns, cites VCF §1.6.1.6, explains that QUAL is
  `-10log10 prob(no variant)` on a variant record and `-10log10 prob(variant)` where ALT is `.`, adds
  *"the higher the floor, the more confidently wrong the result"*, and names GQ and MIN_DP as the
  fix. The `FORMAT/DP` row beside it is silent.
- **RM50, both halves.** A `pmid` cell of `PMC 3110566` — the spelling that used to be accepted as a
  *different* paper — is refused with a message that **names the PMC id**, explains that PMC and
  PubMed number independently, and points at `hint citation --pmcid`. `21551363; PMC3110566` is
  accepted, so the refusal is narrow by construction.
- **RM24's key, on real ClinGen data.** `hboc_palb2` carries two PALB2 rows from one submitter:
  `autosomal_recessive` → Fanconi anemia complementation group N, and `autosomal_dominant` →
  PALB2-related cancer predisposition. They differ on disease *and* on mode of inheritance, and would
  have collapsed under any key that did not carry both. The orphan half fires too: rename the gene in
  `variants.csv` and both `gene_validity.csv` and `gene_metrics.csv` report *"names 1 gene(s) this
  module never mentions: ['PALB2']"*.

## Not run

Recorded so absence is legible rather than looking like coverage:

- **RM4's `withdraw_stale_dataset`** — needs two ClinVar releases; one is provisioned, and building a
  second from the same VCF under a different label would fabricate the provenance the mechanism
  exists to protect.
- **RM46's non-commercial-quote warning** — needs a `provenance_quote` lifted from an article whose
  Europe PMC licence is recorded as CC-BY-NC. Neither citation in the modules built here is in that
  set (both came back `is_open_access: false` with no licence recorded, which is the correct
  withhold), so the path was not exercised.
- **RM49's re-split from `manifest.derived`** — the format's half is verified (the block carries the
  relative paths and hashes, and a `derived/` module compiles to identical signatures); performing
  the re-split is a registry's job and lives outside this repo.

---

## Round 2 — found while fixing round 1

Different provenance from everything above, and worth stating plainly: **these came from reading the
code around a repair, not from building a module.** Dogfooding asks whether the thing is usable; this
round asks whether the code says what it means, which is a review question. The distinction matters
because it changes what counts as evidence — a dogfooding finding is reproduced by running a CLI, and
three of the five below are reproduced against real data instead.

Each was **re-verified here before being written down**, not copied from the report that raised it.
That caught one claim that does not survive contact with the code (R2-7), which is the reason the
re-verification is not a formality.

| id | finding | class | severity |
|---|---|---|---|
| **R2-1** | **ClinPGx's `gene` column is `;`-multi-valued, and both readers treat it as one symbol.** `clinpgx_draft.py:135` filters with `(gene or "").upper() not in wanted_genes` — an exact-set membership against the whole cell — and `:158` passes that same cell into `PharmVariantRow.gene`, which has no validator (`pgx.py:364`, a plain `str \| None`). Probed against the provisioned snapshot: **396 of 16,087 rows** carry a `;` (`IFNL3;IFNL4` ×51, `ANKK1;DRD2` ×24, `CYP2A7P1;CYP2B6` ×18), and **`--gene VKORC1` silently drops 3 real rows** that name VKORC1 inside a multi-gene cell. In the other direction an unfiltered draft writes `PRSS53;VKORC1` into a column documented as "Gene symbol, e.g. VKORC1", where nothing will ever reject it. Both halves are silent. Same shape as the CPIC `gene.chr` lesson: a claim about a source that was true of the *cell* and false of the *column*. | fix → **RM74** (done) | **high** |
| **R2-2** | **`spec_genome_build`'s refusal escapes `draft` and `draft-panel` as a traceback.** F1's repair routed both providers through `source_build_mismatch` (`enrich.py:306`), which calls `spec_genome_build` (`:275`), which deliberately **raises `EnrichmentError`** on a present-but-unreadable `module_spec.yaml` — picking a build for a module whose declaration cannot be read is exactly the invention that function exists to remove, so the raise is right. But `draft` catches `(CpicError, DraftError)` (`cli.py:686`) and `draft-panel` catches `(ClinVarDraftError, DraftError)` (`:1730`); neither catches `EnrichmentError`. Reproduced: a broken yaml in a spec dir turns `draft-panel --gene PALB2 --offline` into a rich traceback rather than the clean message-and-exit-1 every other enricher command gives. The message itself is good; it is the presentation that regressed, and it regressed *because* F1 was fixed. | fix → **RM75** (done) | medium |
| **R2-3** | **A test's stated coverage is not exercised — the fixture's key is one level off.** `enricher/tests/test_draft_declared_build.py:48` builds `_LOCATIONS` with a nested `"location"` key, while `cpic.defining_variants` reads `r.get("sequence_location")` (`cpic.py:472`, and the PostgREST select at `:461` names the same). The location dict is therefore always `{}`, so the file's claim to cover a defining variant carrying a position is empty. Third instance of this class in the workspace, after S21's registry and D6-2's `_MOVABLE`: a guard that proves less than its name says, green either way. | fix → **RM74** (done) | low |
| **R2-4** | **An optional message-enrichment call can sink a finished CPIC draft.** `pgx_draft.py:315` asks `cpic.knows_drug(drug)` inside the `try` whose `finally` closes the client — deliberately, and the comment says so — but by then `alleles_for_gene`, `diplotypes_for_gene`, `defining_variants` and every `recommendations` call have already returned. `knows_drug` exists only to sharpen the message for drugs that came back empty (F5's fix), so a transport failure there discards a complete draft to improve a sentence about it. Same shape as the gnomAD rule already in CLAUDE.md: a per-item error must never sink a batch. **Sharpened by a second reviewer:** `cpic.knows_drug` (`cpic.py:419`) is typed `bool | None`, but it can only return `True`/`False` or raise — so the `known is None` branch at `pgx_draft.py:518`, which already carries the correct "could not ask" wording, is **unreachable from the live client**. The tri-state was designed and then not delivered, which is why the raise escapes: the handling for it exists and nothing can reach it. | fix → **RM75** (done) | low |
| **R2-5** | **A stored VRS id against a symbolic allele may be blaming the wrong party.** `_recompute_vrs_id` returns `_BLAME_TIER` (warning in both modes) for a symbolic allele carrying a `ga4gh:VA.…`. But nothing mints one — the enricher now declines by construction (D1-1) — so a *present* id names some other allele, and **deleting the cell clears it**, which takes the row out of the P5 "no authored edit could clear it" class that `_BLAME_TIER` is for. The obvious repair (escalate to `_BLAME_ROW`) would refuse in both modes a module that compiles today, and the minting side has to answer first: may the enricher ever write a non-VA identity into that column? Recorded in `_recompute_vrs_id`'s docstring by the unit that found it. | **surface** → **RM78** (decided and done 2026-08-15: escalated to row-blame, grammar settled first) | medium |
| **R2-6** | **RM59's `*` would land in the indel bucket, one axis over from D1-2.** `is_unobservable_allele` is not tested by either compiler VRS reason function, so an unobservable allele reaching `resolution.csv`'s `alts` would be reported as "an indel or MNV … re-run it online" — the same false class D1-2 just fixed for symbolic alleles. **Nothing writes one there today**, so the diff is zero and this is not yet a defect. Filed because it is the same blind spot and because "nothing produces it today" is a fact about the current wiring, not about the function — the standing lesson from RM38 and `VALID_RSID_STATUS.withdrawn`. | watch → **RM78** (done) | low |
| **R2-7** | **Not reproduced, twice, and now closed — recorded so it is not re-raised a third time.** The claim is that `compiler.py:1269`'s *"see the skip reported above"* dangles. In `compile_module` it does not: the `--no-resolve` master-switch warning is emitted whenever a resolution table is present (`compiler.py:3630-3642`) and the joinability branch is conjoined with exactly that condition. The residual left open the first time was `validate_spec`, and a second reviewer then raised it as reproduced there on `pgx_slco1b1_simvastatin` — it is not. That module is GRCh38 and rsID-authored, so the fill **succeeds**, no row is unplaced and the branch is never reached; `validate` on it is completely silent. Probed the branch where it *is* reached, `cyp2c9_warfarin_grch37`: `validate` prints *"Positional-table fill skipped … (RM15)"* and the joinability sentence directly beneath it, so the cross-reference resolves. And `validate` exposes no `--no-resolve` flag at all, so the only route to `fill_applied=False` there is the non-GRCh38 one, which always emits its skip. Every path checked; the sentence has its referent. | not a finding | — |
| **R2-10** | **`refget_supports_build` answers `True` for the two inputs `refget_accession` raises on.** Its docstring says it is *"the question `refget_accession` raises on"*, and for `GRCh37` the two agree (`False` / raises). For `None` and `""` they do not: `refget_supports_build` returns **`True`** while `refget_accession` raises `UnsupportedBuildError`. Probed all four inputs. Latent — no caller passes an empty build today — but it is a public function in the schema tier, and it is the guard a caller reaches for *precisely* to avoid the raise, so the first caller that passes an unset build gets the exception the guard exists to prevent. Same class as the `start` docstring: a printed claim the code does not honour, in the tier other tiers build on. | fix → **RM78** (done) | low |
| **R2-11** | **`skipped_unidentified` counts records from genes the author never asked for.** In `clinpgx_draft.py` the rsID check (`:131-133`) runs *before* the `--gene` filter (`:135`), so a record with no rsID belonging to an unrequested gene increments `skipped_unidentified` rather than being filtered out first. The reported count of "records the source could not identify" is therefore inflated by the whole rest of the database on any `--gene` draft, which makes the number unusable for the thing it is for — judging whether the source's coverage of *your* gene is poor. Sibling of R2-1 in the same loop, and independent of it. | fix → **RM74** (done) | low |
| **R2-12** | **Dead internal anchors in the docs, in the one place the project already knows this hurts.** Fourteen `file.md#anchor` links resolve to a heading that no longer exists (unit 12 counted nineteen with a wider link pattern; the discrepancy is the matcher, not the class). Nearly all are `ROADMAP.md#rm4x-…` pointers to items that have since moved to `ROADMAP_HISTORY.md`, from `CHANGELOG.md`, `CONSUMER_SUGGESTIONS_HISTORY.md`, `CONSUMER_TRIAGE_LOOP.md`, `ROADMAP.md` and `ROADMAP_HISTORY.md`. `RM_TOC.md` exists *because* RM33 became unfindable; this is that failure mode one document over, and it arrives by the same mechanism — an item moving between the live file and the history file while the pointers stay behind. Worth a check that runs, not a sweep that fixes it once. | fix (done) | low |

| **R2-8** | **The "a generated stub must be unable to compile" guarantee does not reach `sources.csv`/`licensing.csv`.** `SourceRow` is a plain `BaseModel` (`sources.py:75`), not an `AuthoredModel`, so it carries neither `_guard_raw_input` nor `reject_template_placeholders` — deliberately, on the grounds that it is "a machine-produced reference fact rather than an authored" row (its own docstring). But S21 made it **draftable**, precisely because it is the one fact sidecar a human writes, and the two decisions were never reconciled. A vocabulary column catches the stub by accident (`layer` refuses `<<REPLACE>>` as a non-member); a free-text column does not. Probed on `hfe_hemochromatosis` with `source=<<REPLACE>>`: **compiles green under `--strict`**, and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]` inside the block its own `signature` is computed over. So the attribution ledger of a signed module can name a template placeholder as the source it is accounting for, which is the one thing that table exists to prevent. The compiler's *only* remark on that file was that `sources.csv` is the deprecated spelling. | fix → **RM76** (done, narrow half; the root is RM73) | **high** |

| **R2-9** | **A genotype copied straight out of a VCF is refused without anyone saying it is allele *indices*.** `GT` is `0/1`, and `genotype` wants the bases — but `0/1` falls through to the nucleotide-grammar message, which recites what an allele may be (`nucleotides, '*' …, or a symbolic/structural allele whose first-level type …`) and never says the one thing the author needs: those are indices into the record's REF/ALT list, and this column spells the alleles out. Probed on all three spellings — `0/1` and `0\|1` get the grammar wall, and `0/1/1` now gets D3-2's ploidy explanation, which is *worse* here because it is confidently about the wrong thing (the cell's defect is the notation, not the arity). This is the most likely single mistake an author makes, since pasting a `GT` field is the obvious first guess, and it is exactly the class CLAUDE.md already names: a generic rejection is a dead end where a specific one is a fix, and the repair is a `mode="before"` diagnosis that changes no verdict — the shape `reject_reserved` / `reject_authority_keys` / `reject_misplaced` already share. | fix → **RM77** (done) | medium |

| **R2-13** | **A persistent CPIC 5xx sinks the pass the comment beside it says it must not.** `enrich_pgx` catches `(PharmVarError, CpicError)` per leg (`pgx.py:294, 318`) under the comment *"One source failing must not sink the pass — the other may still answer."* But `CpicClient` calls `response.raise_for_status()` (`cpic.py:294`) and wraps only *shape* failures into `CpicError` (`:297, 519, 548`) — an HTTP status is never wrapped, so once retries are exhausted a raw `httpx.HTTPStatusError` walks straight through both handlers and takes PharmVar's answer down with it. The handler is written for exactly this case and cannot see it. | fix → **RM75** (done) | medium |
| **R2-14** | **RM63's correction is itself an overclaim, and it is the third turn of the same screw.** `base.py:687` reads *"Read a pipe here as **heterozygous**, phase recorded but unaddressable"*. Probed: `VariantRow(genotype="C\|C")` **loads** — `1\|1` is an ordinary phased homozygous call — so the sentence is false of a genotype the model accepts. The history is the point. The original comment claimed a pipe encodes which homolog an allele sits on; 0.6's RM63 correctly refuted that and replaced it with a claim about *zygosity* that nobody checked. Unit 7 caught it while carrying the wording onto the printed descriptions, kept "phase recorded but unaddressable" (which is true and is RM63's actual content), and dropped only the zygosity word — so `describe` is now correct while the comment it was copied from is not. A correction is exactly where this happens: the reviewer is checking the claim being removed, not the one going in. | fix → **RM77** (done) | medium |

| **R2-15** | **The enricher's rsid↔coordinate check was documented, named in the check vocabulary, and reachable only from the compiler's deprecated path.** `ENRICHER.md`'s table listed it as *"`resolver._check_rsid_coord_consistency` against the injected snapshot"*, and `vocab.py:635` cites it as "the enricher's half of the pair the compiler's `_verify` is the other half of". It is called from `resolve_variants` (`resolver.py:153`), whose only non-test caller in the workspace is `compiler.py:3680`'s `_legacy_resolve` — the deprecated DuckDB route. **`enrich()` never called it.** A row authoring both an rsID and a coordinate needs no resolution, so it fell through `enrich()`'s verbatim branch and nothing compared the two halves; there were no counts dying in a warning list, because the comparison was not happening. Found only because wiring the attestation required the counts, which is the general lesson: **asking a pass to publish a number is how you discover it never computed one.** Fixed in the same unit (`resolver.check_rsid_coordinates`, three-valued, shared with the legacy path so the two cannot drift). | fix (done) | **high** |

| **R2-16** | **`manifest.literature.missing_count` and the `citation_existence` record count different things, and both are right.** The compiler's `_cross_check_literature` counts `exists is False` over **every row in `literature.csv`**; the verification record counts over the citations the module makes **now**. `literature.csv` is merge-not-clobber, so it keeps a row for a citation the author has since deleted from `studies.csv` — and the two numbers then disagree on a published manifest with nothing wrong in the module. Each is honest about its own subject: the `manifest.literature` block's siblings are table facets, so counting the table is what that block means, and the compiler's own test states that rule verbatim. Reconciling them changes a published field *and* rewrites the intent a test pins, so it is a decision rather than a repair. The candidate repairs and why each is wrong: filtering the compiler's count to cited rows makes `manifest.literature` stop describing the table it names, and it needs `studies.csv` in scope where the block is a sidecar facet; filtering the *record* is already what it does; and dropping stale rows on re-run destroys the pin that makes a re-run cheap, which is the whole point of merge-not-clobber. | **surface** → **RM79** (done 2026-08-15 — decided the other way: the compiler discards the dead weight, so the two counts share a subject) | low |

### Provenance

R2-1 through R2-4 were raised by the code-review pass of the unit fixing D3-1 and re-verified here
(the snapshot probe, the traceback reproduction and the two reads are this file's own work). R2-5 and
R2-6 were raised and argued by the unit fixing D1-2's compiler half, which correctly declined to fix
either — R2-5 because the repair is a decision, R2-6 because there is nothing to fix yet. R2-8 was
noticed by the unit fixing D4-2, whose own test across every draftable kind turned `sources.csv` red
for a *different* mechanism than the one it was fixing; the compile probe and the manifest read are
this file's own work.

**RM62 as shipped was one-sided, and unit 7 corrected `docs/SCHEMAS.md` while putting the rule on the
printed column (D6-1).** The documented remedy was *narrow the authored bound to float32*, resting on
`float32(0.3)` being **above** `0.3`. Probed in both directions: `0.1` and `0.3` round up, while `0.9`
and `0.7` round **down** — `float32(0.9)` is `0.8999999761581421`. So "`measure_min` is harmless" held
only for upward-rounding decimals, and narrowing an authored `0.9` upper bound drops a row whose
measurement never went through float32 at all. The rule that survives is the one SCHEMAS.md's own
heading always stated: **compare in float32**, rather than move the authored number. Worth recording as
a finding about the batch's own output, not just as an edit.

**R2-6 is no longer a watch item.** It was filed on the reasoning that nothing writes a `*` into
`resolution.csv` today, so there was nothing to fix. The unit fixing D1-1 then probed
`LiteralSequenceExpression`'s pattern — `^[A-Z*\-]*$` — and found that `*` **passes** it, so an
unobservable allele reaching the minter would have been normalized and handed a content-addressed VRS
id for a state that is not a sequence, while RM58's `.` raises the same unhandled error `<DEL:4977>`
did. Both are guarded now on the enricher side (PR #15). The lesson is the one already in CLAUDE.md and
worth not learning twice: *"nothing produces it today"* is a fact about the current wiring, never about
the function.

---

### Checked and held (D2)

- `licensing.csv` is the spelling both providers write into a fresh directory (RM51); the compile gate
  refuses with `declared_use` blanked, naming both sources (RM27).
- RM5's two unusable-allele kinds stayed apart after the grammar widened — CPIC's `*36=S` is reported
  as an IUPAC ambiguity, `*6=DELA` as a grammar gap, with the message saying in-line that RM5's
  `<DEL:1500>` is a different spelling from `DELTCT`.
- RM44's denominator works: `fully_resolved: true` over **zero** variant rows, with
  `resolution_subjects: 0` published beside it, so the documented trust rule withholds the badge.
- The count rule holds for the joinability warning — emitted once per command, in `validate` and
  `compile` alike.
- RM48 fires correctly and supersedes the ±1 shift reading, naming `rs1799853` from
  `10:96702047`. Its **limit** is now measured rather than asserted: of two GRCh37 rows declared as
  GRCh38, one was caught and the other minted a VRS id and recorded `resolved`, because GRCh38 carries
  the authored `ref` at that position too. That is the documented ~3-in-4 sensitivity, and it means
  *"the compiler catches wrong-build coordinates"* is not a reading anyone should take.

---

## What landed, per finding

The fix round ran as twelve parallel units in isolated worktrees, each landing one finding or one
group. Every unit ran the shipped CLIs against a real module, not only the suite — the same standard
the probes themselves were held to.

| finding | unit | PR |
|---|---|---|
| D1-1, D1-2 (enricher half) | 1 | [#15](https://github.com/dna-seq/just-dna-compiler/pull/15) |
| D1-2 (compiler half) | 2 | [#13](https://github.com/dna-seq/just-dna-compiler/pull/13) |
| D1-3 | 3 | [#14](https://github.com/dna-seq/just-dna-compiler/pull/14) |
| D1-4 | 4 | [#16](https://github.com/dna-seq/just-dna-compiler/pull/16) |
| D3-1 | 5 | [#12](https://github.com/dna-seq/just-dna-compiler/pull/12) |
| D3-2 | 6 | [#18](https://github.com/dna-seq/just-dna-compiler/pull/18) |
| D5-1, D5-2, D6-1 | 7 | [#21](https://github.com/dna-seq/just-dna-compiler/pull/21) |
| D4-2 | 8 | [#17](https://github.com/dna-seq/just-dna-compiler/pull/17) |
| D4-1, `allele_function` + `vrs_allele_id` | 10 | [#20](https://github.com/dna-seq/just-dna-compiler/pull/20) |
| D4-1, `rsid_coordinate_agreement` | 11 | [#22](https://github.com/dna-seq/just-dna-compiler/pull/22) |
| F1 (surface), F8, F11, D4-3, D4-1 (surface) → RM68–RM72 | 12 | [#19](https://github.com/dna-seq/just-dna-compiler/pull/19) |

### What the round cost the corpus: three digests, and only where a column was added

All sixteen reference examples were compiled before the round at `8fdaf1d` and again after.
`content_signature`, `compilation.resolution_signature` and `sources.signature` are **identical on
every module** — the authored identity did not move anywhere. `artifact.digest` moved on **three**:
`fmr1_cgg_repeat`, `hboc_palb2` and `pathogenic_clinvar`, which are exactly the three carrying
`literature.csv`, because `LiteratureRow` gained an optional `doi_checked` and the parquet grew a
column. That is the additive case Principle 3 permits — the column is outside `LITERATURE_FACT_FIELDS`,
so no identity a consumer keys on changed. Verified by diffing the parquet schemas rather than inferred
from the diff. The baseline is `data/sig-baseline-8fdaf1d.txt` (gitignored).

**This section read "identical on every module" until the last unit landed, and that is worth keeping
rather than quietly overwriting.** It was measured, correctly, across the eleven units merged at the
time; the twelfth added the column. A measurement is true of the tree it was taken on, and a summary
that is not re-taken after the last change is a summary of something else — the same failure this
ledger records in D6-2 and R2-12, arriving in the document that reports it.

### What only the merge could find

Eleven units were green in isolation and one pair was not green together. Unit 10's `vrs mint` test
asserted `"indel/MNV"` in its record detail, using `mt_common_deletion` and explaining in a comment
that the module's deletion "is an indel" — while unit 1 was concurrently fixing exactly that
misclassification, since `<DEL:4977>` is a symbolic allele that names no sequence. Neither unit could
have caught it alone. The assertion now names the true class and a second assertion forbids the old
one, so the two cannot swap back silently.

### Corrections made to the findings themselves

Three entries above were wrong in some part, and re-verification rather than relay is what caught it:

- **R2-7 does not reproduce**, in `compile_module` or in `validate_spec`, and two separate reviewers
  raised it. Closed rather than left open.
- **D5-2's fix is narrower than the finding asked for.** RM63's wording could not be carried across
  verbatim, because `C|C` loads and the "heterozygous" half is false of it — which is now R2-14.
- **Unit 11's brief was wrong about where the rsid↔coordinate check ran**, and the check turned out to
  be unreachable from `enrich()` entirely. That is R2-15, and it is the round's most valuable finding.

---

## Round 3 — closing a foreign module (2026-08-16)

Different provenance again, and it is the one this file was short of: **someone else's modules,
through the shipped CLI, on the surface that shipped hours earlier.** RM73's closure was built and
tested against this repository's own sixteen reference examples, which are the modules its author
wrote. Round 3 ran `just-dna-compiler close` over **61 module spec directories from three other
repositories** — `just-dna-registry`'s published mirror, `just-dna-lite`'s generated modules,
`just-module-creator`'s assets, `clawbio`'s extracts, `dna-agents`' evals — each copied first, since
dogfooding must not edit someone else's tree. Two were skipped as too large to sweep (180 MB and
221 MB); the other 59 were closed for real.

**The headline number is the finding.** 30 closed, 29 refused — and **26 of the 29 refused for one
reason that has nothing to do with closure**, which is what makes the sweep worth more than the five
modules it started with.

| id | finding | class | severity |
|---|---|---|---|
| **D7-1** | **`close` told the author to run `close`.** `close_module` runs the pre-flight and reports what it found, and the pre-flight rightly warns that the module records no closure — so on every refusal the *first line of output*, while the author was running `close`, was *Run `just-dna-compiler close <spec-dir>`*. Reproduced on the first foreign module that failed. The RM77 class exactly: a correct sentence aimed at the wrong reader, and the one context where it is answered by definition. Filtered on `UNCLOSED_PHRASE` rather than by re-deciding, so the two cannot drift. | fix (done) | medium |
| **D7-2** | **A closure-only document dated a run that never happened.** A module closed straight from its authored state published `producer: null, produced_at: <now>, checks: []` into `manifest.verification` — a timestamp for a check-putting run that did not occur, sitting beside the closure's own `closed_at` recording the act that did. The two fields are a pair describing the same run; they now move together, and a closure-only document leaves both unset. Invisible on this repo's corpus, where three of sixteen examples carry enricher records and the rest were closed in the same batch. | fix (done) | low |
| **D7-3** | **`module.version: 3` — the spelling YAML actually produces — could not be read, and RM17's coercion exists to read exactly that.** `_enforce_semver` coerces the pre-0.4 corpus's informal versions (`v2`, `3`) to SemVer and is `mode="after"`, so an unquoted YAML number arrives as an **int** and the field refuses it first with *Input should be a valid string*: a message naming the type rather than the fix. Quoted `'3'` coerced; unquoted `3` did not — and unquoted is the only way YAML spells a number, so the guard the corpus needed was unreachable from the file format the corpus is written in. **26 of 61 foreign modules**, across three independent toolchains, refused on this and nothing else; every authored value was an integer (`1` ×13, `2` ×9, `3` ×3, `5` ×1). Widened at `mode="before"`, which is P3-legal in the only direction it moves. A **float** stays refused, now with the reason: YAML reads `1.10` as `1.1`, so the author's text is gone before any validator runs and coercing would publish a version nobody wrote. | fix (done) | **high** |

**After the three fixes, the same sweep closes 54 of 59 and the five refusals are all real.** Two
modules are missing `studies.csv` (grounding evidence is mandatory), two are the published registry
modules carrying *inconsistent reference allele* contradictions — 748 and 1,834 errors, the same
verdict `validate` and `compile` give them today, so `close` is refusing exactly what the tier already
refuses — and one is a `just-module-creator` template still holding `<<REPLACE>>`, which is RM76's
guarantee working as designed on a module this repo did not write.

**What the round says about the closure design, beyond the bugs.** Three things held up under foreign
data and are worth recording as confirmations rather than assumed:

- **The refusal rule is consistent with the tier, measured rather than argued.** `validate`, `compile`
  and `close` produce byte-identical 1,084-line output on `registry_cardio`. A published module that
  the compiler will not accept is one `close` will not declare finished, and that turns out to be the
  same set rather than a stricter one.
- **`sidecar_write_path` does the right thing on a foreign layout.** A module keeping its sidecars
  under `derived/` is closed *there*, and a module carrying both copies is refused with the RM51
  message naming both paths and exit 1 — neither case had a test written from a real module before.
- **The full flow survives.** Closing a foreign module, compiling it, reversing it and then enriching
  it offline all behave: the closure reaches `manifest.verification.closure`, reverse names the closure
  it is dropping (and does *not* tell the author to re-run the enricher, since there were no checks),
  and an offline `enrich` adds five check records while leaving the closure standing and correctly
  restamping `producer` to the enricher that put them.

**One thing the round did not find, and the reason is worth naming.** Nothing broke in the closure
*mechanism* on foreign data — no binding mismatch, no unreadable document, no collision this repo had
not already anticipated. That is a weak result rather than a strong one: the mechanism is four days
old and every foreign module met it for the first time in an already-closed state of the tool's
choosing. The sharper test is a module closed by one release and read by the next, which no corpus can
supply yet.
