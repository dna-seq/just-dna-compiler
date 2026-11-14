# AlphaGenome 2's predicted methylation — a trial on known variants

**Question:** can AlphaGenome 2's new methylation scorer give a usable per-variant "predicted methylation shift" that a
module could carry beside a consumer's measured PacBio methylation (RM433, tied to RM317 to RM319)?

**Date:** 2026-11-12, run at the maintainer's word ("run now in subagent, I'm curious"), the first trial under the
pm's trial duty. **This is evidence, never contract**, the standing rule for everything under `docs/probes/`. It
designs nothing. 44 calls to the model service; the scripts and raw outputs stayed outside version control, under
the git-ignored `data/interim/ag2-trial/`.

## 0. Verdict

**Trial 2 (§ 7, 2026-11-14) found a signal at strong mQTLs; this verdict stands for moderate ones.**

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

## 7. Trial 2, 2026-11-14: a signal at strong mQTLs

Run overnight by the pm's trial duty, with the person away and the 7-day quota at 16%. 157 calls to the model
service, 0 errors, no throttling. The decision rule was written into the brief before any score was read; the
choices the rule left open (the test, the floor, the bands) were pinned in the report before scoring, and the copy
kept beside the outputs (`v2/protocol_frozen.md`) was saved after it, so the pinning rests on the run's own account.
Scripts and raw outputs stay in the git-ignored `data/interim/ag2-trial/run2/`. **It supersedes § 0's verdict for
strong mQTLs**: trial 1's GoDMC pairs were moderate effects and read at trial 2's null level; whether a moderate mQTL
carries a signal is untested.

### Verdict

1. **Signal, by the frozen rule, at strong mQTL leads.** (a) Median |Δlogit| is 0.49 at 42 ARIES blood leads against
   0.018 at 84 matched nulls (27×, MW p = 2.6e-12). (b) 28 of 31 leads above the floor agree in sign (90%, p = 2.3e-6).
2. **Sure for 20–100 bp, likely to 300 bp, unshown beyond.** Both tests pass alone only at 20–100 bp (16/17, p = 1.4e-4).
   101–300 gives 9/10, p = 0.011, just short of 0.01; pooled 20–300 (post hoc) gives 25/27, p = 2.8e-6. At 301–600,
   the size still differs (p = 0.002) but the sign does not (5/10).
3. **Only for top-of-genome leads.** Every lead has p ≤ 1e-113 and source |beta| ≈ 1 SD. Trial 1's moderate
   GoDMC tags (|beta| 0.10–0.27 SD, four of them at 82–204 bp) read 0.000–0.015, at null level. Weaker or tag
   mQTLs are unshown.
4. **A module could publish (inference) a predicted direction for a SNV already known as a strong mQTL,** at a
   named CpG within 300 bp, stamped with model, condition, track and window. It could not publish Δlogit for
   arbitrary SNVs under the 90% label: 9 of 84 nulls reach the floor (about 10% by construction, up to 0.30), and how many of those are real
   was not measured. Sizes are window-dependent (the 16 kb window changed values by −44% to +103%).
5. **Terms:** both live pages are newer (Additional ToS 2026-11-06, Output Terms 2026-10-09). The rules are still
   non-commercial, with the notice and the Use restrictions as an enforceable term. Training on Output is now
   barred for any model except AlphaGenome-like ones under the Model Parameters Terms.

### Protocol, frozen before scoring

#### Decision rule (as stated in the brief, applied unchanged)

- **Signal:** test (a) p < 0.01 with the mQTL median |Δlogit| at least 2× the null median, AND test (b) concordance
  ≥ 75% with binomial p < 0.01.
- **No signal:** test (a) p > 0.2 and the mQTL and null |Δlogit| distributions overlap (medians within 1.25× of each
  other), with at least 25 usable loci.
- **Inconclusive:** anything else, or fewer than 25 usable loci.

#### What the rule leaves open, pinned here

- **Reading:** Δlogit (ALT − REF) from `MethylationScorer(width=1201)`, WGBS track, condition
  `UBERON:0000178_CL:0000094` (granulocyte, observed), 1 Mb input window (1,048,576 bp), at the source's CpG
  (matched by `obs.cpg_position + 1 == C position on GRCh38`).
- **Test (a), primary:** one-sided Mann–Whitney U, lead |Δlogit| > pooled null |Δlogit|; effect size AUC = U/(n1·n2)
  and the ratio of medians. "Medians within 1.25×" means 0.8 ≤ median_lead/median_null ≤ 1.25. Secondary, reported
  but not used by the rule: one-sided Wilcoxon signed-rank on lead |Δ| minus the mean |Δ| of its own two nulls.
- **Test (b):** floor = the 90th percentile of the pooled null |Δlogit| (1 Mb, WGBS). Over leads with |Δ| ≥ floor,
  agree = sign(Δlogit) == sign(source beta for the GRCh38 ALT allele); one-sided exact binomial against 0.5.
  No lead above the floor = (b) fails. Also reported (not used by the rule): agreement over all leads.
- **Test (c):** for each scored variant, rank of its target CpG's |Δ| among the window's CpGs at comparable distance
  (|d| within [|d_t|/1.5, 1.5·|d_t|], the target included); u = (rank − 0.5)/n. Under chance u is uniform.
  Reported: leads' top-decile count against the expected count (Poisson-binomial by simulation), a one-sided Wilcoxon
  of (0.5 − u) for the leads, and leads against nulls (Mann–Whitney on u). Loci with fewer than 5 comparable CpGs
  are left out of (c) only.
- **Usable locus:** lead verified (below), its target CpG present in the scorer output, and two verified nulls whose
  CpGs are present in the scorer output.
- **Distance bands:** by the lead's |d| on GRCh38: 20–100, 101–300, 301–600 bp; a null takes its lead's band.
  (a) and (b) are reported per band, the floor in (b) staying the pooled one.
- **Window re-measure (16 kb, 16,384 bp):** 10 loci fixed by rule: the 4 strongest leads (PLINK p) in the 20–100
  band, the 3 strongest in 101–300 and the 3 strongest in 301–600 (fewer in a band → fill from the next strongest
  overall); lead and both nulls each, 30 calls.
- **Orientation:** non-palindromic SNVs only; the source allele is mapped onto GRCh38 REF/ALT by allele identity
  (same strand or complement). A lead is dropped when its ALFA-European MAF is > 0.45 (in trial-1's GoDMC overlap,
  the ARIES and GoDMC signs disagree in 10% of pairs with MAF 0.45–0.5 and 0% below; `out/orient_band_check.txt`),
  or when the source's effect allele (bim A1, "the effect allele" per mQTLdb's help page) is the ALFA-European major
  allele.
- **Distance:** |d| = |C position − SNP position| on GRCh38 in 20–590 bp (inside the scorer's ±600 bp).
- **Call cap:** hard stop at 245 logged model calls, counting the partial run's log.

### Selection, observed

- **Source:** mQTLdb FOM. Gaunt et al. 2016's abstract (Europe PMC, PMID 27036880, `v2/gaunt2016_epmc.json`)
  describes mQTLs "at five different life stages in human blood", including the mothers' middle age. mQTLdb's
  download page lists the five files in the order Birth, Childhood, Adolescence, Pregnancy, Middle Age, which makes
  FOM middle-age blood (observed). The cohort size of about 1,000 was not read in this run; it is recalled.
- **Rows:** leads come from http://www.mqtldb.org/db/GCTA/FOM.ALL.M.tab, and betas and p from
  http://www.mqtldb.org/db/PLINK/FOM.ALL.M.tab. The "GCTA / PLINK line" column below is the 1-based line in each
  file, with the header as line 1. Effect = PLINK `beta` for bim A1 (rank-normalised methylation residuals, mQTLdb
  help page), turned into the effect of the GRCh38 ALT allele.
- **Funnel:**
  - 153 lead candidates;
  - 62 passed the Ensembl, manifest and sequence checks (30 SNVs inside a probe body, 8 leads with a probe-body
    SNP in LD, the per-chromosome cap of 4, low-MAF nulls);
  - 45 passed dbSNP and ALFA-EUR (16 had MAF > 0.45; 1 had its effect allele as the EUR major allele);
  - **42 final**, the other 3 losing for lack of two verified nulls.
  - 42 is over 18 chromosomes, every one of them usable (target CpG present in all 126 outputs).
- **Bands:** 20 leads at 20–100 bp, 12 at 101–300, 10 at 301–600.
- **Checks per variant:**
  - Position and alleles: one GRCh38 primary mapping (Ensembl), equal to dbSNP SPDI+1 position, REF and ALT.
  - REF base on GRCh38 (Ensembl sequence).
  - The CpG reads CG at its C position (Zhou HM450 hg38 manifest).
  - The SNP is outside the CpG's 50-mer probe body.
  - Non-palindromic, ALFA-EUR MAF ≥ 0.05.
- **Nulls:**
  - Each lead has 2 nulls. 3 are tier A (same CpG, another SNV the source tested and did not report); 81 are tier B
    (another array CpG within 100 kb, SNV-to-CpG pair not reported).
  - Distance is matched to within 1.5× of the lead's.
  - 43 of 84 also meet the GC tolerance (|ΔGC| ≤ 0.05 and |ΔCpG count| ≤ max(3, 30%)). Medians: GC 0.537 for leads
    against 0.538 for nulls; CpG count 14 against 15.
  - "Not reported" means absent from the FOM PLINK list (p < 1e-7) only.
- **Tags:** for each lead, `tags` counts the other SNPs reported for its CpG within 2 log10 units of the lead's p.

### Locus table (1 Mb, granulocyte, WGBS)

d = CpG C position − SNP position (GRCh38). Sign: A agree, **D** disagree, – below the floor 0.113. Rank: the target's
|Δ| among all scored CpGs in the ±600 bp window ; among those at comparable distance. (A) marks a tier-A null.
CpG-SNP: whether the SNV itself creates or destroys a CpG.

| # | rsID | GRCh38 | ref>alt | EUR MAF | CpG (C pos) | d | ARIES beta (ALT) | p | tags | CpG-SNP | Δlogit | sign | rank all / comparable | null 1: rsID d Δ | null 2: rsID d Δ | GCTA / PLINK line |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | rs10229846 | chr7:47540518 | C>T | 0.42 | cg05425699 (47540550) | +32 | -0.95 | 3.0e-146 | 0 | no | **-1.568** | A | 1/23 ; 1/3 | rs55919506 -26 -0.115 | rs56187452 -25 -0.034 | 10340 / 2658340 |
| 2 | rs4843648 | chr16:87648574 | A>C | 0.37 | cg26764761 (87648536) | -38 | +1.07 | 2.4e-185 | 2 | creates | **+1.780** | A | 6/48 ; 4/5 | rs825586 -50 -0.011 | rs9929765 +54 -0.019 | 47217 / 955052 |
| 3 | rs680564 | chr2:239192672 | C>T | 0.44 | cg27074582 (239192710) | +38 | -0.97 | 2.5e-168 | 0 | destroys | **-0.851** | A | 4/30 ; 2/4 | rs574636 +40 +0.013 | rs2411428 +38 +0.029 | 33464 / 4907673 |
| 4 | rs7833274 | chr8:19755623 | G>T | 0.38 | cg00923880 (19755667) | +44 | +0.98 | 8.0e-179 | 0 | no | **+3.403** | A | 1/13 ; 1/1 | rs1552777 +44 +0.292 | rs4921666 +57 +0.032 | 351 / 1613901 |
| 5 | rs4792867 | chr17:45172077 | C>T | 0.30 | cg10701640 (45172032) | -45 | +1.04 | 7.4e-148 | 2 | destroys | **+0.528** | A | 2/23 ; 1/2 | rs57344356 -63 -0.011 | rs1552458 -43 -0.103 | 37236 / 5146640 |
| 6 | rs10076158 | chr5:173714808 | C>T | 0.33 | cg15618908 (173714758) | -50 | +0.95 | 1.0e-130 | 0 | no | **+1.521** | A | 2/14 ; 2/3 | rs6875105 +68 +0.013 | rs394248 +58 -0.125 | 5044 / 1890488 |
| 7 | rs2162491 | chr14:58829529 | C>T | 0.41 | cg02291164 (58829584) | +55 | +1.03 | 2.6e-158 | 0 | no | **+0.660** | A | 1/7 ; 1/2 | rs10134791 +73 -0.009 | rs395768 +80 -0.030 | 26139 / 4500315 |
| 8 | rs10845469 | chr12:12072273 | C>T | 0.38 | cg20141578 (12072328) | +55 | -0.97 | 6.1e-141 | 0 | destroys | **-0.529** | A | 9/27 ; 2/4 | rs34206364(A) -40 +0.096 | rs10845461 +37 +0.042 | 39890 / 348645 |
| 9 | rs11977832 | chr7:157850402 | T>C | 0.32 | cg22216157 (157850345) | -57 | +1.02 | 9.5e-146 | 2 | creates | **+0.014** | – | 12/36 ; 4/7 | rs1560955 -63 +0.298 | rs7788108 +66 +0.009 | 6882 / 1497564 |
| 10 | rs798549 | chr7:2721116 | C>A | 0.34 | cg23627948 (2721058) | -58 | -1.08 | 4.4e-143 | 0 | no | **-0.854** | A | 6/43 ; 2/4 | rs798557 -58 +0.009 | rs798562 +76 -0.034 | 15641 / 2493894 |
| 11 | rs4658633 | chr1:244353936 | A>G | 0.30 | cg09033006 (244353875) | -61 | -1.12 | 7.5e-185 | 1 | no | **-1.200** | A | 2/13 ; 1/3 | rs4658628 -68 +0.034 | rs57790923 -60 +0.107 | 44023 / 657454 |
| 12 | rs1079114 | chr6:6893991 | G>A | 0.31 | cg02096172 (6893930) | -61 | -0.92 | 1.8e-146 | 4 | destroys | **+0.038** | – | 11/35 ; 5/8 | rs12201343 +47 +0.041 | rs2765350 +66 +0.002 | 34413 / 40829 |
| 13 | rs2286378 | chr12:1800813 | G>A | 0.23 | cg21224286 (1800750) | -63 | +1.22 | 3.2e-144 | 0 | no | **+0.988** | A | 4/22 ; 1/1 | rs17800972 +84 -0.063 | rs2108639 +68 +0.008 | 23467 / 3385433 |
| 14 | rs12499260 | chr4:184100427 | C>T | 0.42 | cg06737308 (184100361) | -66 | +1.07 | 1.7e-171 | 2 | no | **-0.255** | **D** | 1/22 ; 1/5 | rs6826232 -75 +0.060 | rs3749534 -98 -0.004 | 2312 / 1224352 |
| 15 | rs2227631 | chr7:101126257 | A>G | 0.41 | cg08053846 (101126324) | +67 | -0.95 | 3.8e-162 | 0 | no | **-1.122** | A | 8/26 ; 1/1 | rs73178512 -54 +0.016 | rs2227668 -88 -0.016 | 2744 / 1247889 |
| 16 | rs112683685 | chr12:132474624 | T>C | 0.23 | cg07099606 (132474550) | -74 | -1.07 | 1.0e-144 | 0 | no | **+0.082** | – | 13/107 ; 4/12 | rs73486469 +74 +0.000 | rs12832020 +94 +0.005 | 27802 / 4599377 |
| 17 | rs9828229 | chr3:15304417 | G>A | 0.34 | cg27104695 (15304334) | -83 | -0.94 | 3.1e-159 | 4 | destroys | **-1.013** | A | 6/29 ; 2/3 | rs3821788 +75 +0.048 | rs6797033 +91 -0.001 | 25087 / 3966090 |
| 18 | rs33963919 | chr15:32731469 | C>T | 0.44 | cg07179000 (32731385) | -84 | -1.04 | 3.2e-168 | 1 | no | **-0.455** | A | 4/21 ; 4/5 | rs11635997 +92 +0.187 | rs73376930 +106 -0.169 | 36069 / 5079039 |
| 19 | rs4802561 | chr19:49113873 | C>T | 0.35 | cg10667338 (49113785) | -88 | +1.11 | 1.1e-175 | 0 | no | **+0.798** | A | 3/58 ; 3/6 | rs7250825 +70 -0.043 | rs2232003 -88 -0.254 | 28870 / 4659438 |
| 20 | rs11641943 | chr16:75305397 | C>T | 0.23 | cg04384112 (75305485) | +88 | -1.15 | 5.7e-161 | 0 | no | **-0.483** | A | 1/10 ; 1/1 | rs8062169 -83 +0.032 | rs1862737 +87 +0.085 | 26884 / 4547122 |
| 21 | rs895074 | chr3:122975553 | C>T | 0.18 | cg07733481 (122975439) | -114 | +1.22 | 1.8e-135 | 2 | no | **+2.008** | A | 5/18 ; 3/4 | rs1006461 +101 -0.005 | rs2276777 +112 -0.008 | 19562 / 3637833 |
| 22 | rs2245711 | chr2:127620988 | G>A | 0.38 | cg01966334 (127620859) | -129 | +1.01 | 5.2e-163 | 4 | destroys | **+0.945** | A | 3/17 ; 3/4 | rs1047760 +124 +0.036 | rs3796082 +123 -0.020 | 722 / 1132852 |
| 23 | rs12108066 | chr3:72657832 | T>C | 0.41 | cg24363020 (72657698) | -134 | +0.89 | 1.1e-138 | 0 | no | **+0.898** | A | 4/10 ; 3/3 | rs2046869 +190 -0.011 | rs11708505 -135 +0.056 | 32678 / 4394588 |
| 24 | rs11097019 | chr4:40265366 | A>C | 0.32 | cg25243082 (40265521) | +155 | -1.17 | 1.3e-165 | 0 | no | **-1.613** | A | 7/16 ; 5/7 | rs10015231 -123 -0.102 | rs56241474 -223 -0.032 | 24563 / 3937863 |
| 25 | rs2281841 | chr10:44911160 | T>C | 0.42 | cg05187965 (44911316) | +156 | -0.92 | 2.1e-113 | 0 | no | **-0.340** | A | 7/20 ; 1/3 | rs11596745 +132 +0.007 | rs2281840 -104 +0.299 | 10259 / 2655235 |
| 26 | rs4880352 | chr10:132232171 | C>A | 0.28 | cg01458105 (132232010) | -161 | -1.16 | 8.8e-163 | 2 | no | **-0.245** | A | 11/45 ; 3/10 | rs79274715 -180 -0.005 | rs147370408 +158 +0.011 | 8968 / 2581707 |
| 27 | rs8009934 | chr14:32938339 | C>T | 0.31 | cg11787167 (32938164) | -175 | +1.06 | 6.5e-163 | 0 | no | **-0.150** | **D** | 25/82 ; 7/13 | rs36063234 -161 +0.274 | rs941526 +184 +0.002 | 3852 / 1822968 |
| 28 | rs4257763 | chr5:139378470 | G>A | 0.34 | cg11459648 (139378648) | +178 | +1.00 | 1.1e-137 | 0 | destroys | **+0.205** | A | 25/58 ; 11/18 | rs3923059 +142 -0.018 | rs12515989 +222 +0.008 | 29086 / 4173987 |
| 29 | rs28593435 | chr21:36977441 | T>C | 0.24 | cg21871091 (36977637) | +196 | -1.00 | 1.2e-158 | 1 | creates | **-0.023** | – | 5/17 ; 2/5 | rs73196100 -198 -0.001 | rs727961 -133 -0.012 | 23631 / 3396199 |
| 30 | rs7853212 | chr9:128192959 | A>G | 0.37 | cg09976142 (128193157) | +198 | -1.02 | 3.6e-145 | 2 | creates | **-0.680** | A | 17/66 ; 4/20 | rs3003602 +223 +0.004 | rs67525828 -277 -0.026 | 28663 / 4150801 |
| 31 | rs73351675 | chr17:50508193 | T>C | 0.43 | cg00901687 (50507909) | -284 | +1.05 | 2.5e-174 | 1 | creates | **+0.497** | A | 11/87 ; 1/40 | rs4794152 +299 -0.001 | rs9900747 +283 +0.019 | 17185 / 3038379 |
| 32 | rs1885034 | chr14:51508428 | T>C | 0.40 | cg09841842 (51508130) | -298 | +1.03 | 7.9e-148 | 0 | no | **+0.004** | – | 19/19 ; 9/9 | rs8013889 +355 +0.054 | rs1950930 -267 -0.013 | 28636 / 4642405 |
| 33 | rs551145 | chr6:44269711 | T>C | 0.24 | cg05496603 (44270076) | +365 | +1.04 | 1.7e-142 | 0 | no | **+0.311** | A | 1/10 ; 1/7 | rs513688 -480 +0.004 | rs639728 -506 +0.004 | 43292 / 1002621 |
| 34 | rs2279575 | chr12:77023564 | G>A | 0.44 | cg07679219 (77023958) | +394 | +1.05 | 3.1e-174 | 1 | no | **+0.365** | A | 9/25 ; 3/18 | rs374335 -340 +0.015 | rs7961533 -298 +0.066 | 2616 / 1748125 |
| 35 | rs12636296 | chr3:125990207 | G>T | 0.16 | cg04553112 (125990608) | +401 | +1.03 | 1.9e-137 | 31 | destroys | **-0.041** | – | 16/59 ; 2/31 | rs58043886(A) +377 -0.013 | rs6803160 -356 -0.000 | 26948 / 4552453 |
| 36 | rs615311 | chr11:64491033 | T>C | 0.44 | cg08822897 (64490631) | -402 | -0.85 | 3.2e-138 | 13 | no | **-0.096** | – | 30/41 ; 12/23 | rs4930422 -352 +0.004 | rs4930195 -278 +0.073 | 19927 / 3660800 |
| 37 | rs13002299 | chr2:170363139 | T>C | 0.45 | cg15059639 (170363551) | +412 | +1.09 | 8.8e-194 | 0 | creates | **-0.215** | **D** | 4/6 ; 2/4 | rs12619684 +378 +0.038 | rs7596319 -517 +0.024 | 30179 / 4240314 |
| 38 | rs12543373 | chr8:23247109 | A>G | 0.40 | cg14349055 (23246680) | -429 | -0.96 | 3.8e-155 | 1 | creates | **+0.001** | – | 65/66 ; 37/38 | rs6981400 -530 -0.002 | rs4563894 +461 +0.001 | 13045 / 2350424 |
| 39 | rs2604274 | chr11:114320215 | T>G | 0.37 | cg24647015 (114320645) | +430 | +0.98 | 3.1e-147 | 4 | no | **-0.045** | – | 10/16 ; 4/10 | rs6589425 -384 -0.023 | rs11214973 +387 +0.007 | 15939 / 2508696 |
| 40 | rs3758758 | chr11:90223420 | G>T | 0.30 | cg26834418 (90223865) | +445 | +1.04 | 1.5e-140 | 4 | destroys | **+1.050** | A | 2/55 ; 2/33 | rs3758759(A) -572 +0.018 | rs11825721 -399 +0.039 | 41762 / 458590 |
| 41 | rs9972885 | chr17:65775146 | G>T | 0.39 | cg07283582 (65774635) | -511 | +0.95 | 1.5e-147 | 6 | no | **+0.054** | – | 12/21 ; 1/10 | rs12600822 -510 +0.008 | rs232138 +503 +0.002 | 19404 / 3628104 |
| 42 | rs11671930 | chr19:8052424 | T>C | 0.18 | cg15436354 (8052991) | +567 | +1.31 | 4.1e-149 | 3 | creates | **-0.011** | – | 13/18 ; 4/7 | rs114364310 +537 -0.009 | rs12973145 +530 -0.007 | 21859 / 3774463 |

### The three tests (observed; `v2/analysis.json`)

- **(a) |Δlogit| at the published CpG, leads vs nulls.** n = 42 vs 84. Median 0.490 vs 0.018 (ratio 27.2), mean
  0.665 vs 0.046. One-sided Mann–Whitney p = 2.6e-12, AUC 0.878. Secondary, paired against each lead's own two nulls:
  the lead is larger at 39 of 42, Wilcoxon p = 7.0e-11.
- **(b) Sign concordance.** The floor is the null 90th percentile, 0.113 logit. 31 leads reach it; 28 agree (90.3%),
  binomial p = 2.3e-6. Over all 42: 33 agree, p = 1.4e-4. Spearman of Δlogit against the source beta for ALT:
  ρ = 0.63, p = 8.8e-6. The three disagreements:
  - rs12499260, d −66, Δ −0.255, beta +1.07 (2 tags);
  - rs8009934, d −175, Δ −0.150, beta +1.06;
  - rs13002299, d +412, Δ −0.215, beta +1.09.
- **(c) Is the published CpG near the top of its window?** Only weakly. Ranked among CpGs at comparable distance
  (n ≥ 5 of them, so 24 leads and 42 nulls), 6 leads fall in the top decile against 3.0 expected (p = 0.076). The
  median position u is 0.38 (chance 0.5; Wilcoxon p = 0.031). Leads beat nulls on u at p = 0.066. 6 of 42 targets are
  the top CpG of the whole window.
  - What drives this (observed): a lead SNV moves many CpGs around it. The median of the largest |Δ| in a lead's
    window is 0.72, against 0.10 in a null's (p = 6e-15).
  - Inference: the model calls the SNV methylation-active over a region and does not single out the array's CpG.
    That fits mQTLs acting regionally, and the array samples one CpG of the region.

**Rule outcome:** (a) p < 0.01 and ratio ≥ 2; (b) 90% ≥ 75% and p < 0.01; 42 ≥ 25 usable loci → **signal**.

#### Checks run after the rule (observed; post hoc, not part of the decision; `v2/context.json`)

- **CpG-SNPs.** They are as common among nulls as among leads (leads: 9 destroy a CpG, 8 create one; nulls: 18 and
  18 of 84). With all of them left out, 25 leads and 48 nulls remain: median 0.483 vs 0.014, AUC 0.94,
  p = 3.2e-10; sign 18 of 20 above the floor, p = 2.0e-4.
- **GC match.** Against only the 43 GC-matched nulls: median 0.490 vs 0.013, p = 8.0e-11.
- **Tags.** With `tags` ≤ 1 (26 leads): ratio 17, p = 1.2e-8, sign 20/22. With `tags` > 1 (16 leads): ratio 23,
  p = 4.3e-6, sign 8/9 (p = 0.02).
- **Tracks.** WGBS and snmC-seq3 agree at the targets (r = 0.9999), so the choice of track does not matter.

### By distance band (observed; floor 0.113 pooled)

| band | leads / nulls | median |Δ| lead / null | ratio | (a) MW p | AUC | (b) agree / above floor | (b) p | sign, all leads |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20–100 bp | 20 / 40 | 0.824 / 0.033 | 25.0 | 3.9e-8 | 0.93 | 16 / 17 (94%) | 1.4e-4 | 17 / 20 |
| 101–300 bp | 12 / 24 | 0.418 / 0.013 | 33.4 | 1.4e-4 | 0.88 | 9 / 10 (90%) | 0.011 | 11 / 12 |
| 301–600 bp | 10 / 20 | 0.075 / 0.008 | 9.0 | 0.002 | 0.83 | 3 / 4 (75%) | 0.31 | 5 / 10 |

Reading: the size test passes in every band (observed). Sign agreement passes the rule's p < 0.01 alone only at
20–100 bp. At 101–300 bp it is 9/10, p = 0.011, and pooled 20–300 bp (post hoc) it is 25/27, p = 2.8e-6. At
301–600 bp it is unreadable, with only 4 of 10 leads above the floor.

Distance does not explain trial 1 (observed, from the trial 1 write-up). Four of its nine GoDMC pairs sat within
300 bp (d = +82, +102, +138, −204). In granulocyte they read 0.007, 0.000, 0.002 and 0.015, at the 23rd, 0th, 10th and
46th percentile of trial 2's null distribution. What differs is the source effect: those were tag SNPs with
|beta| 0.10–0.27 SD, and every trial 2 lead has |beta| about 1 and p ≤ 1e-113.

Inference: the model separates the strongest independent mQTLs from unreported SNVs. Whether it separates moderate
ones is untested, and the only moderate ones ever scored read at null level.

### Window re-measure, 16 kb vs 1 Mb (observed)

10 loci fixed by the rule before scoring (4 in 20–100, 3 in 101–300, 3 in 301–600); lead plus both nulls, 30 calls.

- **At the target CpG,** |Δ1Mb − Δ16kb| has median 0.029 and max 1.247 (rs4843648: +1.780 → +3.027).
- **Over all CpGs in a window,** the per-variant maximum difference has median 0.065 and max 1.251.
- **Signs:** all 11 targets with |Δ| ≥ 0.113 at 1 Mb kept their sign at 16 kb (9 leads, 2 nulls).
- **Leads against nulls at 16 kb:** median 1.09 vs 0.031, MW p = 1.2e-4.
- **Relative change** at those 11 targets ranged from −44% to +103%, with a median absolute change of 30%
  (observed).
- **Inference:** the window changes sizes a lot but does not create or erase the lead/null gap, and it never flipped
  a sign above the floor. Publish signs, not sizes.
- **Scale check (observed):** the partial run's smoke call reproduces trial 1's control reading at rs3813204, d = −3,
  at +0.333 (+0.3327 now against +0.333 then). The unit did not change between trials.

| rsID | role | d | Δ 1 Mb | Δ 16 kb | max |Δ1Mb−Δ16kb| over the window's CpGs |
| --- | --- | --- | --- | --- | --- |
| rs13002299 | lead | +412 | -0.215 | -0.121 | 0.211 |
| rs12619684 | null | +378 | +0.038 | +0.002 | 0.152 |
| rs7596319 | null | -517 | +0.024 | +0.041 | 0.045 |
| rs4843648 | lead | -38 | +1.780 | +3.027 | 1.251 |
| rs825586 | null | -50 | -0.011 | -0.035 | 0.082 |
| rs9929765 | null | +54 | -0.019 | -0.004 | 0.047 |
| rs7833274 | lead | +44 | +3.403 | +3.132 | 0.351 |
| rs1552777 | null | +44 | +0.292 | +0.198 | 0.108 |
| rs4921666 | null | +57 | +0.032 | +0.051 | 0.036 |
| rs4802561 | lead | -88 | +0.798 | +0.883 | 0.124 |
| rs7250825 | null | +70 | -0.043 | -0.018 | 0.028 |
| rs2232003 | null | -88 | -0.254 | -0.515 | 0.316 |
| rs73351675 | lead | -284 | +0.497 | +0.448 | 0.330 |
| rs4794152 | null | +299 | -0.001 | +0.028 | 0.050 |
| rs9900747 | null | +283 | +0.019 | -0.003 | 0.040 |
| rs2279575 | lead | +394 | +0.365 | +0.475 | 0.388 |
| rs374335 | null | -340 | +0.015 | -0.001 | 0.047 |
| rs7961533 | null | -298 | +0.066 | +0.058 | 0.030 |
| rs4658633 | lead | -61 | -1.200 | -1.306 | 0.501 |
| rs4658628 | null | -68 | +0.034 | +0.008 | 0.052 |
| rs57790923 | null | -60 | +0.107 | +0.058 | 0.055 |
| rs2245711 | lead | -129 | +0.945 | +1.409 | 0.713 |
| rs1047760 | null | +124 | +0.036 | +0.007 | 0.039 |
| rs3796082 | null | +123 | -0.020 | -0.044 | 0.036 |
| rs11097019 | lead | +155 | -1.613 | -1.781 | 0.290 |
| rs10015231 | null | -123 | -0.102 | -0.122 | 0.034 |
| rs56241474 | null | -223 | -0.032 | -0.082 | 0.070 |
| rs12543373 | lead | -429 | +0.001 | -0.025 | 0.060 |
| rs6981400 | null | -530 | -0.002 | +0.006 | 0.087 |
| rs4563894 | null | +461 | +0.001 | -0.013 | 0.032 |

### Cost (observed)

- **Model calls:** 157 in all.
  - 1 by the partial run (`out/calls.log.jsonl`), plus 126 at 1 Mb and 30 at 16 kb (`v2/calls.log.jsonl`).
  - 0 errors, 0 `RESOURCE_EXHAUSTED`, 0 back-offs. The cap was 250 and the hard stop 245.
- **Per call:**
  - 1 Mb: median 0.98 s, max 1.93 s, median 631 B.
  - 16 kb: median 0.28 s, median 540 B.
- **Wall time:**
  - scoring: 269 s at 1 Mb and 70 s at 16 kb, each including a 1 s pause per call;
  - the whole session: about 1 h 05 min, mostly paced third-party reads.
- **Third-party requests, all paced:**
  - Ensembl REST: 8 variation POSTs of 150 IDs, and 39 sequence POSTs of 40 regions;
  - NCBI Variation: 158 new records (194 with the 36 reused) at 2 requests each, 2.5 s apart;
  - 2 HEAD requests to mQTLdb, to confirm the URLs;
  - 2 terms pages, rendered headless;
  - 1 Europe PMC search, for the Gaunt 2016 abstract.

### Terms (observed, live pages read 2026-11-14 with headless Chromium; `terms/*.expanded.txt`)

- **Dates:**
  - https://deepmind.google.com/science/alphagenome/terms reads "Last modified: November 6, 2026". The vendored copy
    reads September 8, 2026.
  - https://deepmind.google.com/science/alphagenome/output-terms reads "Effective: October 9, 2026". The vendored
    copy reads June 25, 2025.
  - Both pages are unchanged since the 2026-11-12 fetch. `docs/vendor/` was not touched.
- **Clauses that changed about storing, publishing, commercial use or training:**
  - **Output Terms, training (changed, broader).** Old: "To train machine learning models or related technology for
    predicting the effects of genetic variants similar to AlphaGenome." New: "To train machine learning models or
    related technology, except that you may use Output and Output Derivatives to train models that function in a
    similar manner to AlphaGenome provided the model weights and parameters for those models are used in accordance
    with and governed by the AlphaGenome Model Parameters Terms of Use." The Additional ToS still carries the old,
    narrower wording ("for predicting the effects of genetic variants similar to AlphaGenome"). Plain reading: anyone
    who receives a published score without agreeing to the Additional ToS is bound by the broader ban.
  - **Output Terms, the definition of Output (changed).** "'Output' means predictions or related information (e.g.,
    embeddings) provided by AlphaGenome Services, or using Model Parameters or Model Parameter Derivatives."
  - **Output Terms, distribution responsibility (wording added).** "You are solely responsible for determining the
    accuracy, reliability, availability, effectiveness, correct use and distribution of information generated by
    AlphaGenome … You and anyone you share information generated by AlphaGenome with are solely responsible for
    that information and its subsequent use."
  - **Additional ToS, the permissive carve-out (renamed, wider).** "AVI Score" became "Permissive Use Downloadable
    Artifacts for Commercial and Non-Commercial Use", meaning "AVI Scores and other artifacts that are made available
    for download within the 'Permissive Use Downloadable Artifact' section". Live scorer calls are not in it.
- **Clauses that did not change in substance:**
  - Commercial: "aside from indirectly via a scientific publication, open source release or to support journalism".
  - Publication: "You can publish, share and adapt output in accordance with the Terms, including the requirement to
    provide clear notice…".
  - Notice: "conspicuous notice that any Output or Derivatives you publish or distribute are provided under and subject
    to these Terms".
  - Different terms: "you must include this 'Use restrictions' section of these Terms as an enforceable provision".
  - Termination: delete all copies.
  - Clinical: "not intended, validated, or approved for clinical use".
  - Eligibility: no commercial entity.
- **Plain reading, not legal advice:** a module carrying these scores stays non-commercial and carries the Output
  Terms notice and the Use restrictions. It cannot be CC0 or CC BY, and it must now also tell consumers that the
  scores may not be used to train any model.

### Not done in trial 2

- **GoDMC:** its bulk file is 5.9 GB and its API stalled in trial 1, so leads come from a single cohort (ARIES FOM;
  its size of about 1,000 is recalled, not read). There is no replication in a second cohort.
- **Nulls:** "not reported" is checked against the FOM PLINK list only (p < 1e-7). That list cannot show a weak true
  mQTL (n ≈ 1,000), and the other four ARIES timepoints were not read.
- **GC match:** 41 of 84 nulls miss the GC tolerance. The 12 nearest array CpGs within 100 kb were all that was
  searched. The result holds against the matched 43 alone.
- **Weak mQTLs:** none were tested. Every lead has p ≤ 1e-113. A tier of moderate leads (|beta| 0.1–0.4,
  p 1e-8 to 1e-20) with the same nulls is the natural design for a trial 3. It was left out because it is outside
  the frozen protocol, not because the call budget ran out.
- **The floor at arbitrary SNVs:** how often |Δ| ≥ 0.11 at an arbitrary SNV reflects a real effect was not measured.
  9 of the 84 nulls reach the floor (about 10% by construction), up to 0.30.
- **Causal or tag:** the leads are GCTA-independent, but 16 of 42 have more than one near-equivalent tag, so causal
  versus tag is not settled. Both strata pass (a).
- **Single CpG:** only the CpG that the 450k array measured was scored as the target. Regional effects (test c) are
  read only from the scorer's own window.
- **Coverage:** one condition (granulocyte) and one assay track (WGBS). Indels were not tested.
- **Effect size:** not compared. ARIES betas are on rank-normalised residuals, not logit, so only signs are compared.
- **Orientation above MAF 0.45:** unresolved. 16 strong leads were dropped for it, rather than oriented by guess.
