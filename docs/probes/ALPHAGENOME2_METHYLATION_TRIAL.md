# AlphaGenome 2's predicted methylation — a trial on known variants

**Question:** can AlphaGenome 2's new methylation scorer give a usable per-variant "predicted methylation shift" that a
module could carry beside a consumer's measured PacBio methylation (RM433, tied to RM317 to RM319)?

**Date:** 2026-11-12, run at the maintainer's word ("run now in subagent, I'm curious"), the first trial under the
pm's trial duty. **This is evidence, never contract**, the standing rule for everything under `docs/probes/`. It
designs nothing. 44 calls to the model service; the scripts and raw outputs stayed outside version control, under
the git-ignored `data/interim/ag2-trial/`.

## 0. Verdict

1. **Not usable yet for a published mQTL's shift; inconclusive, not negative.** At nine GoDMC CpGs 82 to 533 bp from
   their lead SNP, every predicted shift is at most 0.046 logit. That is inside the model's own sensitivity to its
   input window: scoring at 16 kb instead of 1 Mb moves a score by up to 0.047 to 0.107.
2. Of 27 readings at the published CpGs, 8 reach 0.02 logit; 7 of those agree in sign with GoDMC, and the sign held
   at 16 kb for all 5 retested. But 6 of the 8 come from one locus, the SNPs are tags in LD blocks, and all nine pairs
   sit in one 1 Mb region of chr1. Too thin to say it works.
3. **What it predicts strongly is local.** The largest shifts (0.1 to 0.33 logit) are at CpGs within about 15 bp of
   the variant. The CpG a variant destroys is left out of the score by design; the full prediction shows it going to
   about zero, which is trivially true.
4. **Technically cheap and deterministic.** About 1.1 s and 1 KB per score call; a repeated call was bit-identical; no
   throttling in 44 calls; a deletion is accepted and scored.
5. **Terms:** storing and publishing the scores looks allowed for non-commercial use only, with the Output Terms
   notice and the Use Restrictions carried as an enforceable term. An open licence that permits commercial reuse
   (CC0, CC BY) conflicts with the restrictions. Quoted from the vendored copies (2026-09-08), not the live page.

## 1. The interface, observed

- Client `alphagenome.models.v2.dna_client` (package `alphagenome==2.0.0`), service `DnaModelServiceV2`.
  `score_variant(interval, variant, condition, variant_scorers)` needs one condition (a tissue or cell type by
  UBERON/CL id) or a single-cell profile, one condition per call.
- `MethylationScorer` supports one width, 1201 bp. Its docstring: "Only CpG sites present in both the REF and ALT
  sequences are scored. Sites created or destroyed by the variant are omitted."
- 2,799 conditions; for methylation, 185 are `observed`, 1,068 `imputed_supported`, 1,546 `imputed_exploratory`.
  190 unstranded methylation tracks: 75 WGBS, 115 snmC-seq3. Each call returned one WGBS and one snmC-seq3 track; the
  two agree (r ≥ 0.987).
- **The score's unit, reconstructed by fit (an inference, not documented):** per CpG within ±600 bp,
  `logit(mean(ALT_C, ALT_G)) − logit(mean(REF_C, REF_G))` of the predicted methylation fraction. The fit is exact on
  2 variants × 2 tracks. At a fraction near 0.8, a 0.046 logit shift is under 0.01 in fraction.
- `obs.cpg_position` is the 0-based start of the C; 44 of 44 sites read CG at `cpg_position + 1` on GRCh38.

## 2. The variants

Reference bases were checked against GRCh38 (Ensembl REST), positions by rsID in dbSNP (SPDI + 1), frequencies from
dbSNP's 1000G-30x/TOPMed and ALFA-European.

**Published mQTLs** come from GoDMC (Min et al. 2021, Nat Genet, PMID 34493871), read from its API for chr1 1 to 2 Mb
(hg19), whole blood, effects in SD per allele. GRCh38 CpG positions come from the Zhou-lab HM450 hg38 manifest, each
checked to read CG. `beta_a1` is read as the effect of `a1`, inferred from the column name; `freq_a1` matched the
ALFA-European frequency of the GRCh38 ALT for every SNP but one (rs12141369), so no sign was flipped. Palindromic SNPs
were left out. Only signs are compared, since SD units are not logit.

A trap was caught: a constant hg19→hg38 offset fails beyond about 1.7 Mb on chr1, and two candidates (rs66701417,
rs13302999) turned out not to be what the offset made them; both were dropped after the dbSNP check.

## 3. Results

Scores are Δlogit on the WGBS track (snmC-seq3 within about 0.01). Conditions: blood granulocyte (observed), blood
CD14+ monocyte (observed), whole blood (imputed). d is the CpG's C position minus the variant's.

**Positive controls, common SNVs that destroy a CpG**

| rsID | GRCh38 | ref/alt | output | agrees |
| --- | --- | --- | --- | --- |
| rs3813204 | chr1:1185634 | G>A | site left out; d=−3 **+0.333** (granulocyte), +0.151 (monocyte); full prediction at the site 0.81 → 0.00 | near the site, yes |
| rs9442371 | chr1:1083182 | C>T | site left out; d=+15 **−0.132** / −0.065; at the site 0.94 → 0.00 | near the site, yes |
| rs78107697 | chr1:1226486 | C>T | site left out; d=+14 **−0.167** / −0.097 | near the site, yes |

**Published mQTLs (GoDMC, whole blood).** Readings are granulocyte / monocyte / blood; agreement shown only where the
shift reaches 0.02 logit (A agree, D disagree, – too small to read).

| rsID | ref/alt | CpG | d | GoDMC beta (SD) | Δlogit gran / mono / blood | sign |
| --- | --- | --- | --- | --- | --- | --- |
| rs6665973 | T>G | cg04126957 | +358 | +0.93 | −0.019 / +0.008 / −0.009 | – – – |
| rs74048017 | T>C | cg05528516 | +438 | −0.76 | −0.007 / **−0.032** / −0.014 | – A – |
| rs3737727 | G>A | cg09358422 | +102 | −0.26 | −0.000 / −0.008 / +0.008 | – – – |
| rs2274789 | A>G | cg09021712 | +138 | +0.17 | −0.002 / **−0.022** / −0.000 | – D – |
| rs11260542 | A>G | cg10143960 | −533 | +1.29 | +0.003 / **+0.028** / +0.011 | – A – |
| rs11260542 | A>G | cg01511231 | −343 | +1.22 | **+0.028 / +0.046 / +0.024** | A A A |
| rs12141369 | C>A | cg18770446 | +507 | +0.30 | **+0.038 / +0.021** / +0.012 | A A – |
| rs113867217 | C>T | cg00942814 | −204 | −0.27 | −0.015 / −0.017 / −0.015 | – – – |
| rs7515488 | C>T | cg11257497 | +82 | −0.10 | +0.007 / +0.016 / +0.005 | – – – |

The model never ranks the published CpG near the top of its window. At 16 kb, the five readings of 0.02 or more kept
their sign but not their size (rs2274789's monocyte reading went from −0.022 to −0.107).

**Negative control:** rs9538546 (chr13, no CpG within 331 bp): −0.014 / −0.039 and −0.002 / −0.018, within the floor.

**Indel:** rs76142405, a 1 bp deletion that creates a CpG: accepted and scored (65 CpGs). Its largest shifts are +0.24
at d=+26 and about +0.2 at d=+53 and +56. GoDMC's indel at the same place agrees in sign at d=+76, but GoDMC gives
only insertion/deletion alleles and its frequency disagrees, so this shows the indel is accepted, not that it matches.

## 4. Noise floor and cost, observed

- Same call twice: identical. 1 Mb against 16 kb windows: up to 0.047 to 0.107 per variant, medians 0.010 to 0.022.
  Beyond 50 bp from the variant the median score is 0.006 to 0.054.
- Score call: 0.9 to 1.6 s at 1 Mb, 0.3 to 0.4 s at 16 kb; 0.3 to 1.2 KB. A full 1 Mb prediction: about 3 s, 15 MB.
- Values per call: CpGs within ±600 bp present in both alleles (44 to 70 in GC-rich chr1, 2 in an AT-rich window), × 2
  tracks. No throttling seen. Extrapolated, untested: 10,000 variants × 3 conditions ≈ 9 hours sequentially.

## 5. Terms, quoted

From `docs/vendor/alphagenome_additional_tos.txt` ("Last Modified: September 8, 2026") and
`docs/vendor/alphagenome_output_terms.txt` ("Effective: June 25, 2025"), both older than v2. The live page renders
client-side and was not read; re-save it before relying on any of this.

- Use: "you may access, use and modify the AlphaGenome Assets and distribute Output and Derivatives".
- Publication: "You can publish, share and adapt output in accordance with the Terms, including the requirement to
  provide clear notice that (with the exception of the AVI Score) use is subject to AlphaGenome Output Terms of Use".
- Commercial (Prohibition 1b): "You must not share Output or Derivatives with any commercial organization … aside from
  indirectly via a scientific publication, open source release or to support journalism."
- Different terms (Prohibition 5b): "you must include the "Use Restrictions" section of these Terms as an enforceable
  provision and provide clear notice to subsequent users that Output or Derivatives are subject to such use
  restrictions."
- Training (Prohibition 4): not "to train machine learning models … for predicting the effects of genetic variants
  similar to AlphaGenome."
- Clinical: "not intended, validated, or approved for clinical use."
- Termination: "you must immediately stop using and delete all copies of the Output and Derivatives".
- Eligibility: "The AlphaGenome Services aren't available for any commercial entity, even if conducting
  non-commercial work."
- The permissive carve-out covers AVI scores and the listed downloads only, not live predictions.

Plain reading, not legal advice: a module carrying these scores would be non-commercial, carry the notice and the Use
Restrictions as a term, and could not be CC0 or CC BY. Whether an open module registry counts as an "open source
release" is open, as it was for the Atlas (`ALPHAGENOME_ATLAS.md` § 7).

## 6. Not done

- The live terms page.
- A powered concordance test: nine pairs from one region. The GoDMC API stopped answering after one 62 MB range read,
  so no further loci or per-CpG SDs.
- `beta_a1`'s meaning (inferred), and causal versus tag SNP (1 to 18 near-equivalent SNPs per CpG).
