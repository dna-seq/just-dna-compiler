# Dogfooding the 0.6 batch — findings

The bug list produced by running [DOGFOOD_0_6.md](DOGFOOD_0_6.md). One row per finding, each
reproduced against the shipped CLIs before it was written down. **Fixing is a separate round** —
this file is the ledger, not the work.

Severity is about what a consumer or author gets wrong because of it, not about how hard it is to
fix. `class` is the standing fix-vs-surface split: **fix** = a false claim, a misdiagnosis, an
unaggregated wall, a guard that is never reached; **surface** = the obvious repair is itself a design
decision, and the entry says why each candidate repair is wrong.

> **Already repaired in the working tree (D2 round, before the split was called).** F1–F7 and F9, F10
> below were fixed and pinned with regression tests in the same session that found them. They are
> listed here anyway, because the ledger has to be complete and because the fixes are unstaged and
> may be reviewed or dropped as a unit. Everything from D1 onward is **filed, not fixed**.

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
| **D1-1** | **`enrich` crashes on any module carrying a symbolic allele.** Unhandled `pydantic.ValidationError` out of `ga4gh.vrs`: `VrsMinter.mint` routes a non-substitution to `_mint_normalized`, which builds `models.LiteralSequenceExpression(sequence=alt.upper())` **outside** the `try` below it — whose comment reads *"A failure here is a live-service problem … never a reason to fail the enrichment."* Same shape as the `UnsupportedBuildError` defect recorded eight lines above it in the same function. | fix | **high** |
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
