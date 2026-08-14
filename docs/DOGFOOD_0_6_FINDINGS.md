# Dogfooding the 0.6 batch — findings

The bug list produced by running [DOGFOOD_0_6.md](DOGFOOD_0_6.md). One row per finding, each
reproduced against the shipped CLIs before it was written down. **Fixing is a separate round** —
this file is the ledger, not the work.

Severity is about what a consumer or author gets wrong because of it, not about how hard it is to
fix. `class` is the standing fix-vs-surface split: **fix** = a false claim, a misdiagnosis, an
unaggregated wall, a guard that is never reached; **surface** = the obvious repair is itself a design
decision, and the entry says why each candidate repair is wrong.

> **Already repaired (D2 round, before the fix/file split was called).** F1–F7 and F9, F10 were fixed
> and pinned with regression tests in the same session that found them, and landed in one commit that
> can be reviewed or reverted as a unit. **Everything from D1 onward is filed, not fixed.**

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
| **F1** | **Every drafting provider ignores the module's declared build.** `draft`, `draft-panel`, `draft-clinpgx` all take a `spec_dir` and none reads `genome_build`. `enrich.spec_genome_build` — written for exactly this defect one release earlier — had **one caller**. CPIC/ClinVar/ClinPGx all serve GRCh38, so drafting into a `genome_build: GRCh37` module writes `10,94942290` for `rs1799853` (GRCh37: `96702047`) in silence. Two of the three write coordinates and can do harm; `draft-clinpgx` writes none. Hid because `test_pgx_draft.py`'s fixture declares `GRCh38` — the only drafting test that mentions a build. | fix (warn) + **surface** (refuse vs strip-to-rsid is a design decision) | high |
| **F2** | **`clinpgx_draft` says the snapshot has no `gene` column.** It has one, populated on 15,331 of 16,087 rows, written *and re-read* by our own builder. `--gene` was refused with a false reason and `PharmVariantRow.gene` left empty. Root cause: `load_snapshot`'s hand-written `SELECT` listed six of eleven columns. | fix | medium |
| **F3** | **`annotation_text` is written for 16,087 of 16,087 rows and read by nothing.** `conclusion` — the one column whose job is to say what the module claims — was synthesized as `"ClinPGx 655385012: C/C and warfarin — dosage"`, a restatement of the row's own key. Nothing flags a content-free conclusion. | fix | high |
| **F4** | **The attestation records a check it could not run as having run clean.** On a GRCh37 module `verify_reference_alleles` caught `UnsupportedBuildError` per row and `continue`d, so `not_checked` stayed `None` and `verification.json` published `reference_allele: subjects 0, findings 0, skipped null` — and `genome_build_agreement: nothing_to_check` with the detail *"no authored ref disagreed with the reference"*, asserting a comparison that never happened. `VALID_VERIFICATION_SKIPS.unsupported`, whose comment names this case, was **emitted by nothing and asserted by no test**. Reproduced on `reference_examples/grch37_build`. | fix | high |
| **F5** | **`draft --drug X` cannot tell a typo from a real drug CPIC scores differently.** `warfarin` and `notarealdrugxyz` produced byte-identical output. CPIC's warfarin guideline is real; it is a multi-gene dosing algorithm and so has no phenotype-keyed recommendation row. | fix | low |
| **F6** | **The joinability warning recommended a re-run that cannot help.** `fill_applied=False` sat behind `if not placeable`, and on a non-GRCh38 module those coincide — so the author was told *"run `just-dna-enricher enrich` first"* one line below the warning explaining the fill was skipped **because** their module is GRCh37. | fix | medium |
| **F7** | **`compile → reverse → compile` drops `manifest.verification` in silence.** Reverse cannot re-attest and must not invent one — but nothing said the block was going, and a module and its own round trip then disagree on a published field with nothing edited (the RM44 class). | fix (say so) | medium |
| **F8** | **`resolution_signature` is not a round-trip invariant when the fill is skipped.** Injected rows for positional-table keys never reach a parquet on a non-GRCh38 module, so reverse cannot rebuild them. Forced by the RM15 skip: materializing them would mean joining a table across builds. | **surface** | low |
| **F9** | **The corpus round-trip sweep never compared `resolution_signature`.** `getattr(manifest, "resolution_signature", None)` — the field is on `manifest.compilation`. `None == None` for all eleven examples for the whole of 0.6, while the docstring explains why the signature is checked. `grch37_build`'s README asserts a fixed point on it that nothing verified (and which is a `None → value` materialization, not equality). | fix | high |
| **F10** | **A "no snapshot" test that only fails on a machine that has one.** `setenv("JUST_DNA_CLINPGX_CACHE", "")` is the *credential* idiom and is inverted for a cache path: empty is falsy, so the ladder falls through to the default dir — where `cache pull` puts a snapshot. Green on CI, red on a provisioned machine. | fix | medium |
| **F11** | **`requires_callable` is `VariantRow`-only, so no PGx table can state CPIC's core assumption.** CPIC assumes an uncalled position is reference — literally `requires_callable=false` — and `haplotypes.csv`/`pharm_variants.csv`/`diplotypes.csv` have no such column. A star-allele module cannot record whether its call needed the defining positions to be callable. | **surface** (RM65-adjacent) | medium |

---

## D1 — `mt_common_deletion`

Module: `reference_examples/mt_common_deletion/`. The mitochondrial 4,977 bp common deletion, spelled
as RM5's `<DEL:4977>`, beside `m.8993T>G` (inside the deleted span) and `m.3243A>G`.

**One root cause behind the first two: RM5 shipped the symbolic-allele grammar in 0.6 and the VRS
tier was never told.** No reference example and no enricher test carried a symbolic allele before
this module — the corpus-uniformity heuristic, paying off exactly as the plan predicted.

| id | finding | class | severity |
|---|---|---|---|
| **D1-1** | **`enrich` crashes on any module carrying a symbolic allele** — reproduced on `<DEL:4977>` (D1) and independently on `<DUP:16000>` (D3), so it is the allele class and not one spelling. Unhandled `pydantic.ValidationError` out of `ga4gh.vrs`: `VrsMinter.mint` routes a non-substitution to `_mint_normalized`, which builds `models.LiteralSequenceExpression(sequence=alt.upper())` **outside** the `try` below it — whose comment reads *"A failure here is a live-service problem … never a reason to fail the enrichment."* Same shape as the `UnsupportedBuildError` defect recorded eight lines above it in the same function. | fix | **high** |
| **D1-2** | **Offline, the same allele is misdiagnosed as an indel with a remedy that crashes.** `_vrs_coverage` reports *"an indel/MNV, which must be justified against the reference sequence — re-run without --offline to mint it"*. A symbolic allele names no sequence by construction, so no id is ever mintable — a permanent reason class, not an `--offline` limitation — and the suggested re-run is D1-1. | fix | **high** |
| **D1-3** | **`_check_binning_grounding` exempts a variant-keyed bin in a module that has no `studies.csv`.** The function returns early unless there are **zero** study rows, then treats a bin as grounded because it names a variant "a study row can then name back" — the study row it has just established does not exist. A `heteroplasmy.csv` module stating four thresholds and citing nothing is green and silent; the same module on `repeat_alleles.csv` is warned. Reopens the S19 gap for the one binning kind a real MELAS/NARP module uses. | fix | medium |
| **D1-4** | **`describe <kind>` omits `vocabulary_notes`.** It calls itself "the full machine description of one table kind" and prints `source_element`'s members without `ELEMENT_RULE_MEANINGS`, which reach only the whole-schema `reference`. The per-table command is the one an author authoring one table uses. | fix | low |

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
| **D3-1** | **The lengthless-symbolic-allele message names `<DEL>` whatever was authored.** `alts=<DUP:TANDEM>` is correctly refused, with the sentence *"A `<DEL>` that does not say how long it is …"* beside an example clause naming the real cell. The two halves of one message disagree about what is being discussed. | fix | low |
| **D3-2** | **RM67's refusal does not make the documented divergence findable.** A polyploid genotype on a duplicated CYP2D6 — the spec's own polyploid example — is refused with a bare restatement of the grammar. VCF permits higher ploidy and this format deliberately does not; nothing in the message says so, so it reads as a syntax error. Every other deliberate refusal here names its own limit in-line (RM5's "a release away", the ploidy check's contigs, the VRS warnings' RM15). | fix (message) | medium |

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
| **D5-1** | **`largest`'s meaning sentence assumes a ploidy the contig does not have.** `ELEMENT_RULE_MEANINGS['largest']` explains the rule as *"the longer of the sample's two alleles"* — a claim about a diploid record — and FMR1 in a male is the presentation the gene is known for. The rule itself is correct for one value; only the illustration is wrong, and it is the only member's sentence that reaches for one. | fix (wording) | medium |
| **D5-2** | **RM63's correction is a code comment, and the pipe form is not in the printed contract at all.** `describe variants.csv` gives `genotype` as *"Slash-separated sorted alleles, e.g. A/G"* — no `A\|G`, no mention of phase — while the validator accepts it, its own error message lists it, and `phased` is materialized and round-tripped. RM63's corrected wording (*"heterozygous, phase recorded but unaddressable"*) sits above the validator in `base.py` and nothing prints it. | fix | medium |

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
| **D4-1** | **Five of seven checking passes attest nothing; 12 of 17 `VALID_VERIFICATION_CHECKS` members are emitted by nothing.** `record_verification` has exactly two callers — `enrich()` and `enrich_clinpgx()`. `literature`, `gene-validity`, `check-identifiers`, `check-acmg`, `dosage`, `pgx` and `vrs mint` each perform a check the vocabulary names, report it to stdout, and let the record die with the process — the sentence RM45's own docstring opens with as the thing it exists to fix. And it is a **claim**: that docstring states *"A separate command (`check-identifiers`, `literature`) writes once of its own, and the merge below is what keeps the two runs' records in one document"*. `merge_records` is built and tested for a document no two commands produce. Unreachable members: `acmg_secondary_findings`, `allele_function`, `citation_existence`, `citation_identifier`, `dosage_sensitivity`, `gene_disease_validity`, `gene_locus_agreement`, `gene_symbol_currency`, `provenance_quote`, `rsid_coordinate_agreement`, `trait_currency`, `vrs_allele_id`. | fix | **high** |
| **D4-2** | **`hint` reports every template stub twice** — once from its own per-column check, once from the model's `mode="before"` validator. A freshly drafted 109-row panel yields 219 findings for 109 defects. The CPIC aggregation lesson arriving through a different door: two layers reporting one cell rather than a loop over a source table. | fix | low |
| **D4-3** | **The alleles needed to replace a `genotype` stub are only in `draft-panel`'s stdout.** A drafted row is rsID-only (identity whole or not at all), so the file does not state `ref`/`alts`; the pair is emitted once per row as a warning. The author's next action is an edit to a file that does not contain the information. Tolerable at 16 rows, not at the 761 the same command drafts for PALB2 at the 2-star floor. | **surface** (writing it into the row would fill an identity column a drafting provider must fill whole or not at all) | medium |

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
| **D6-1** | **RM62's authoring rule is in the consumer docs and not in the authoring contract.** `docs/SCHEMAS.md` states it fully — a VCF `Float` is 32-bit, `0.3` widens to `0.300000011920928955…`, so an inclusive non-dyadic `measure_max` is missed by a float32 read, and the rule is to *narrow the authored bound*. `describe <kind>`'s `measure_max` says only *"Inclusive upper bound; None = open above. Inclusive on every measure_kind."* The word "narrow" appears **zero** times in `just-dna-compiler reference`. RM62 is a rule about **what to author**, and it reaches only the document the author is not writing from. Third instance of this shape in the batch, with D1-4 and D5-2. | fix | medium |

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
| **R2-1** | **ClinPGx's `gene` column is `;`-multi-valued, and both readers treat it as one symbol.** `clinpgx_draft.py:135` filters with `(gene or "").upper() not in wanted_genes` — an exact-set membership against the whole cell — and `:158` passes that same cell into `PharmVariantRow.gene`, which has no validator (`pgx.py:364`, a plain `str \| None`). Probed against the provisioned snapshot: **396 of 16,087 rows** carry a `;` (`IFNL3;IFNL4` ×51, `ANKK1;DRD2` ×24, `CYP2A7P1;CYP2B6` ×18), and **`--gene VKORC1` silently drops 3 real rows** that name VKORC1 inside a multi-gene cell. In the other direction an unfiltered draft writes `PRSS53;VKORC1` into a column documented as "Gene symbol, e.g. VKORC1", where nothing will ever reject it. Both halves are silent. Same shape as the CPIC `gene.chr` lesson: a claim about a source that was true of the *cell* and false of the *column*. | fix | **high** |
| **R2-2** | **`spec_genome_build`'s refusal escapes `draft` and `draft-panel` as a traceback.** F1's repair routed both providers through `source_build_mismatch` (`enrich.py:306`), which calls `spec_genome_build` (`:275`), which deliberately **raises `EnrichmentError`** on a present-but-unreadable `module_spec.yaml` — picking a build for a module whose declaration cannot be read is exactly the invention that function exists to remove, so the raise is right. But `draft` catches `(CpicError, DraftError)` (`cli.py:686`) and `draft-panel` catches `(ClinVarDraftError, DraftError)` (`:1730`); neither catches `EnrichmentError`. Reproduced: a broken yaml in a spec dir turns `draft-panel --gene PALB2 --offline` into a rich traceback rather than the clean message-and-exit-1 every other enricher command gives. The message itself is good; it is the presentation that regressed, and it regressed *because* F1 was fixed. | fix | medium |
| **R2-3** | **A test's stated coverage is not exercised — the fixture's key is one level off.** `enricher/tests/test_draft_declared_build.py:48` builds `_LOCATIONS` with a nested `"location"` key, while `cpic.defining_variants` reads `r.get("sequence_location")` (`cpic.py:472`, and the PostgREST select at `:461` names the same). The location dict is therefore always `{}`, so the file's claim to cover a defining variant carrying a position is empty. Third instance of this class in the workspace, after S21's registry and D6-2's `_MOVABLE`: a guard that proves less than its name says, green either way. | fix | low |
| **R2-4** | **An optional message-enrichment call can sink a finished CPIC draft.** `pgx_draft.py:315` asks `cpic.knows_drug(drug)` inside the `try` whose `finally` closes the client — deliberately, and the comment says so — but by then `alleles_for_gene`, `diplotypes_for_gene`, `defining_variants` and every `recommendations` call have already returned. `knows_drug` exists only to sharpen the message for drugs that came back empty (F5's fix), so a transport failure there discards a complete draft to improve a sentence about it. Same shape as the gnomAD rule already in CLAUDE.md: a per-item error must never sink a batch. | fix | low |
| **R2-5** | **A stored VRS id against a symbolic allele may be blaming the wrong party.** `_recompute_vrs_id` returns `_BLAME_TIER` (warning in both modes) for a symbolic allele carrying a `ga4gh:VA.…`. But nothing mints one — the enricher now declines by construction (D1-1) — so a *present* id names some other allele, and **deleting the cell clears it**, which takes the row out of the P5 "no authored edit could clear it" class that `_BLAME_TIER` is for. The obvious repair (escalate to `_BLAME_ROW`) would refuse in both modes a module that compiles today, and the minting side has to answer first: may the enricher ever write a non-VA identity into that column? Recorded in `_recompute_vrs_id`'s docstring by the unit that found it. | **surface** | medium |
| **R2-6** | **RM59's `*` would land in the indel bucket, one axis over from D1-2.** `is_unobservable_allele` is not tested by either compiler VRS reason function, so an unobservable allele reaching `resolution.csv`'s `alts` would be reported as "an indel or MNV … re-run it online" — the same false class D1-2 just fixed for symbolic alleles. **Nothing writes one there today**, so the diff is zero and this is not yet a defect. Filed because it is the same blind spot and because "nothing produces it today" is a fact about the current wiring, not about the function — the standing lesson from RM38 and `VALID_RSID_STATUS.withdrawn`. | watch | low |
| **R2-7** | **Not reproduced — recorded so it is not re-raised.** The claim was that `compiler.py:1269`'s *"see the skip reported above"* dangles under `--no-resolve`, which prints no skip. It does print one: `compile_module` emits the `--no-resolve` master-switch warning whenever a resolution table is present (`compiler.py:3630-3642`), and the joinability branch is conjoined with exactly that condition. The other `fill_applied=False` cases the comment enumerates each report something above too. A residual question is left open rather than asserted: `validate_spec` has no resolution step, so whether the same sentence can dangle there was probed on `pgx_slco1b1_simvastatin` and produced no joinability line at all, i.e. the probe did not reach the branch. Someone re-raising this needs a module that does. | not a finding | — |

| **R2-8** | **The "a generated stub must be unable to compile" guarantee does not reach `sources.csv`/`licensing.csv`.** `SourceRow` is a plain `BaseModel` (`sources.py:75`), not an `AuthoredModel`, so it carries neither `_guard_raw_input` nor `reject_template_placeholders` — deliberately, on the grounds that it is "a machine-produced reference fact rather than an authored" row (its own docstring). But S21 made it **draftable**, precisely because it is the one fact sidecar a human writes, and the two decisions were never reconciled. A vocabulary column catches the stub by accident (`layer` refuses `<<REPLACE>>` as a non-member); a free-text column does not. Probed on `hfe_hemochromatosis` with `source=<<REPLACE>>`: **compiles green under `--strict`**, and `manifest.sources` publishes `"sources": ["<<REPLACE>>"]` inside the block its own `signature` is computed over. So the attribution ledger of a signed module can name a template placeholder as the source it is accounting for, which is the one thing that table exists to prevent. The compiler's *only* remark on that file was that `sources.csv` is the deprecated spelling. | fix | **high** |

| **R2-9** | **A genotype copied straight out of a VCF is refused without anyone saying it is allele *indices*.** `GT` is `0/1`, and `genotype` wants the bases — but `0/1` falls through to the nucleotide-grammar message, which recites what an allele may be (`nucleotides, '*' …, or a symbolic/structural allele whose first-level type …`) and never says the one thing the author needs: those are indices into the record's REF/ALT list, and this column spells the alleles out. Probed on all three spellings — `0/1` and `0\|1` get the grammar wall, and `0/1/1` now gets D3-2's ploidy explanation, which is *worse* here because it is confidently about the wrong thing (the cell's defect is the notation, not the arity). This is the most likely single mistake an author makes, since pasting a `GT` field is the obvious first guess, and it is exactly the class CLAUDE.md already names: a generic rejection is a dead end where a specific one is a fix, and the repair is a `mode="before"` diagnosis that changes no verdict — the shape `reject_reserved` / `reject_authority_keys` / `reject_misplaced` already share. | fix | medium |

### Provenance

R2-1 through R2-4 were raised by the code-review pass of the unit fixing D3-1 and re-verified here
(the snapshot probe, the traceback reproduction and the two reads are this file's own work). R2-5 and
R2-6 were raised and argued by the unit fixing D1-2's compiler half, which correctly declined to fix
either — R2-5 because the repair is a decision, R2-6 because there is nothing to fix yet. R2-8 was
noticed by the unit fixing D4-2, whose own test across every draftable kind turned `sources.csv` red
for a *different* mechanism than the one it was fixing; the compile probe and the manifest read are
this file's own work.

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
