# Dogfooding the 0.6 batch — six probe modules and one corpus sweep

**What this is.** A plan, not the work. The 0.6 batch landed twenty-eight items across eleven lanes
([PROPOSAL_0_6.md](../proposals/PROPOSAL_0_6.md) for the reasoning, [ROADMAP_HISTORY § 0.6.0](../ROADMAP_HISTORY.md)
for what actually shipped), and every one of them was verified by its own tests and its own code
review. What none of them has had is the 2026-08-03 treatment: **a real module, built with the
shipped CLIs, by someone trying to make the libraries fail at something they advertise.** This file
says which modules to build, what claim each one attacks, and what would count as a finding.

Each item below is one module (or one sweep) exercising several `RMn` at once. That is deliberate:
the 0.6 lanes were parallel and their interactions were tested pairwise at best, so the yield is in
the seams — a GRCh37 module with PGx tables, an attestation that has survived a round trip, a
symbolic allele on the table where dropping a row is fatal.

**Rules this plan follows** (from CLAUDE.md's dogfooding section, restated because they shape every
item):

- **Attack claims, not gaps.** A documented deferral is a decision; "finding" it proves nothing.
  RM55 warns and does not fix, RM56 withholds and states no policy, RM65/RM66 are gated on a real
  caller VCF, RM67 is a documented divergence, CPIC's IUPAC codes are deliberately unexpressible.
  For those, the legitimate probe is *does the documented behaviour actually happen, loudly,
  aggregated by reason, on the right side of the mode ladder* — not whether the gap exists.
- **Real data only.** No `rs999999999`, no invented coordinates. Where this file needs a number it
  says to obtain it from the tool (`hint variant`), which is the dogfooding act anyway.
- **Use the shipped surface.** The moment a step reaches for a raw `httpx` call or a hand-written
  query, the exercise has stopped producing its signal. A capability the tool lacks *is the result*.
- **Finish each probe as a reference example with a README naming what it broke.** A finding recorded
  only in a commit message is not reproducible.
- **Separate "fix it" from "surface it"** before writing any code, and for anything surfaced, say why
  each candidate repair is wrong.

---

## Why these six — where the corpus is uniform

The heuristic that found four bugs behind a green suite in 0.5 was: *probe where every existing
example looks the same.* Counted over `reference_examples/` as of the 0.6 merge:

| Surface | Modules carrying it | What that hides |
|---|---|---|
| `copynumbers.csv` | **0** | RM55's copy-number half, RM53's new 4.4 `CN` collision, RM65's corrected claim — all unexercised by any module |
| `activity_phenotype.csv` | **0** | the one measure kind in neither `_INTEGER_KINDS` nor `_CONTINUOUS_GAP_KINDS`: no gap warning, and a shared endpoint is an overlap error |
| `pgs.csv` | **0** | — |
| `pharm_variants.csv` | 1 (9 rows) | RM43's fill path has exactly one instantiation, and it is GRCh38 and rsID-only |
| `heteroplasmy.csv` | 1 | the third positional kind, and the one where RM5 says a dropped row is fatal |
| non-GRCh38 build | 1 (`grch37_build`) | which carries **no** `resolution.csv`, no sidecar and no table kind — so nothing in the corpus exercises 0.6's positional fill, attestation or fact tables off GRCh38 |
| `verification.json` | **0** | RM45 ships and no module in the corpus carries an attestation |
| `gene_validity.csv` / `clinical_assertions.csv` | **0** | RM24/RM25 ship and no module carries either |
| `frequencies.csv` / `gene_metrics.csv` | **0** | — |
| `derived/` layout | **0** | RM49 ships and every example is flat |
| deprecated `sources.csv` spelling | 1 | RM51's fallback has one instantiation and no module exercises the migration on reverse |

Six of the eleven rows are zeroes, and four of them are things 0.6 *built*.

---

## D1 — `mt_common_deletion`: the spelling zoo on the table where dropping a row is fatal

**RMs** RM5, RM58, RM59, RM60, RM61, RM53, RM54, RM62, RM43 (heteroplasmy fill), RM47, RM45.

**Real basis.** The mitochondrial 4,977 bp "common deletion" (Kearns–Sayre, Pearson) — which the
literature spells at two different start positions because 13 bp direct repeats flank it, so the two
spellings are the same event; plus `m.3243A>G` (MT-TL1, MELAS, `rs199474657`) which already has a
heteroplasmy-graded phenotype in `mt_heteroplasmy`; plus `m.8993T>G` (NARP/MILS), which sits *inside*
the deleted interval, so a joint call carrying both emits `*` at 8993. All three are real and all
three are on one contig.

**Claims attacked, each quoted from the thing that makes it:**

1. RM5's placement rule — *"droppable only where a row is a rule (`variants.csv`,
   `pharm_variants.csv`); on `haplotypes.csv`/`heteroplasmy.csv` it is fatal in both modes, because
   dropping a defining variant or a bin makes a quietly different module."* Author `<DEL:4977>` **on
   both** — as a `variants.csv` row (expect: dropped, warning says *dropped*) and as a
   `heteroplasmy.csv` row's allele (expect: fatal in `best_effort` too). Then author the lengthless
   `<DEL>` on each. Four cells, four different verdicts, one module.
2. RM60's widening — `chrom: chrM` must now validate and normalize to `MT`. Then check the seam
   nobody tested: **does `_check_build_coordinates` (RM48) see the normalized spelling?** MT is
   16,569 bp, so a row at `chrM:16600` must be the offline "position past the end of its contig"
   error. If the contig-length table is keyed on `MT` and the check reads the raw cell, a `chrM`
   module gets no diagnosis — the RM60 widening would have blinded an RM48 guard, which is the
   `_check_misspelled_tables`/`derived/` shape one lane over.
3. RM58 — `alts=.` and an empty `alts` on the same site must be diagnosed as the MISSING marker, and
   **not** filed under `"notation"` beside `<DEL>`.
4. RM59 — `genotype: A/*` at m.8993, on a **haploid** contig. This is the deliberate collision:
   `_check_contig_ploidy` treats MT as haploid, `draft`'s `sole_expressible_genotype` fills the only
   expressible genotype there, and the RM59 review pinned `*` as inert on both sides of the algebra.
   Does the ploidy check count `*` as an allele and call this diploid? Does `sole_expressible_genotype`
   overwrite it? **This interaction has no test and no module.**
5. RM53/RM54/RM61 — `mt_heteroplasmy` was re-authored to `FORMAT/AF` in lane H, so the qualified form
   has one instantiation. Add the ones it does not have: a bare colliding `AF` (expect the collision
   warning), a dotted key (`gnomAD.AF`) and `1000G` (RM61's widening), and `source_element` on the
   heteroplasmy bins — where `FORMAT/AF` is `Number=A`, so `largest` and `largest_alt` coincide and
   the vocabulary says so. Then the honest gap: `callable_from`/`quality_from` have **no** companion
   column (RM54 shipped on the binning base only, `callable_element`/`quality_element` reserved). Try
   to author a callability pointer at a multi-valued field and see whether the reserved-name refusal
   explains itself.
6. RM43 — heteroplasmy is the positional kind with one example. Author the bins rsID-only and confirm
   the fill lands, then `reverse` and confirm the rebuilt `resolution.csv` carries the heteroplasmy
   rows as a second source and the recompile is a fixed point.
7. RM47/RM62 — ground one heteroplasmy threshold with a `pmid` (allowed on all four kinds), and set
   an inclusive upper bound at `0.3`, which is the non-dyadic case RM62 says a float32 read can miss.
   The probe is whether the consumer contract states the tolerance rule anywhere an implementer reads.

**Network.** `enrich` needs Ensembl for the rsIDs; the compile half is offline.

**Would count as a finding.** Any verdict differing from the four RM5 cells above; a `chrM` module
escaping the contig-length check; the ploidy check or the drafting fill treating `*` as an allele; a
warning emitted per row rather than aggregated by reason; a message that says "notation" for `.`.

---

## D2 — `cyp2c9_warfarin_grch37`: the headline probe

**RMs** RM43, RM36, RM48, RM44, RM45, RM57, RM27, RM51, RM5, RM54.

**Real basis.** CYP2C9 *2 (`rs1799853`) and *3 (`rs1057910`), CPIC's warfarin recommendations, and
the 18 CYP2C9 defining variants CPIC publishes **with a position and no rsID** (the set that broke
`pgx_draft` in 0.5). Authored on **GRCh37**, with a GRCh37 `resolution.csv` beside it. Obtain every
coordinate through `just-dna-enricher hint variant` rather than typing one.

**Why this one is the headline.** RM43 was the largest lane and its only instantiation is a
nine-row, GRCh38, rsID-authored `pharm_variants.csv`. This module differs on every axis at once: a
non-default build, two positional kinds together (`haplotypes.csv` + `pharm_variants.csv`),
coordinate-authored rows beside rsID-authored ones, and no `variants.csv` at all.

**Claims attacked:**

1. **The fill does not happen off GRCh38.** `_apply_positional_resolution` returns early for a
   non-default build with an RM15 warning — correct, and *invisible in the corpus*. Probe what the
   module then says about itself: `_check_positional_joinability` reports per-table counts, and the
   0.6 rule ("never re-run a check whose message embeds a count") was found independently by three
   lanes. Does the joinability count appear once, or once before and once after resolution?
2. **The stamped columns off GRCh38.** `with_genome_build` re-derives `variant_key` for the
   positional models at load, which is a *different* mechanism from `VariantRow`'s `_restamp_for_build`
   — and `VariantRow` deliberately keeps the restamp because it also emits the "keyed by coordinate
   instead" warning a GRCh37 module must hear. A table-only module never constructs a `VariantRow`.
   **Does a GRCh37 PGx module hear that warning at all?** If not, a GRCh37 module silently loses the
   one message that tells its author a VRS id was not minted.
3. **RM44 + RM45 on a table-only module.** `fully_resolved` is vacuously `true` here,
   `resolution_subjects` is the denominator that fixes it, and 0.6 says the four table-only modules
   *gained* a `resolution_signature`. Verify all three on a build where the fill was skipped — the
   signature must still be stamped, and the trust rule
   (`resolution_subjects > 0 and (strict or fully_resolved)`) must not read as clean.
4. **RM57's real instance.** CPIC assumes an uncalled variant is reference, which is exactly
   `requires_callable`'s case. Author `requires_callable=true, quality_from=QUAL, min_quality=30` and
   confirm the inversion warning fires and says what to do (a block wants `MIN_DP` and interval
   containment, not `DP` and an equality join).
5. **RM5 + RM27 + RM51 through the PGx surface.** CPIC's `del/del` genotypes and its IUPAC `R` are
   the two kinds `cpic.unusable_allele_reason` must not conflate — one is a grammar gap RM5 just
   widened, the other is permanent. Check that RM5 shipping did not move `R` into the wrong bucket.
   Write the module's licence table as `licensing.csv` (CC BY-SA + no-sale), compile with and without
   `--use`, and confirm the RM27 redistribution verdict lands in the manifest **and** that nothing
   gates on it.

**Sibling module, five minutes' work, different item.** Copy the spec, declare `genome_build:
GRCh38`, keep the GRCh37 coordinates. That is RM48's scenario verbatim. Expect the *offline* half to
stay silent — CYP2C9 sits mid-chromosome on a contig both builds name, so neither offline shape
fires — and the *online* half to name `rs1799853`. **That silence is the honest limit and should be
written into the README**, because "the compiler catches wrong-build coordinates" is the reading a
reader will take from RM48's error-in-both-modes framing.

**Network.** `hint variant` and the RM48 recovery are live; everything else offline.

---

## D3 — `cyp2d6_structural`: the two measure kinds no module has ever carried

**RMs** RM55, RM56, RM53, RM54, RM47, RM5, RM59, RM65, RM67.

**Real basis.** CYP2D6 — `*5` (whole-gene deletion), `*1x2`/`*2xN` (tandem duplications), CPIC
activity scores on a 0.25 grid, and the phenotype bins (PM 0, IM 0.25–1.0, NM 1.25–2.25, UM > 2.25).
`copynumbers.csv` and `activity_phenotype.csv` in one module, which is how a real CYP2D6 module would
be written and which the corpus has never contained.

**Claims attacked:**

1. **RM55, both halves.** The 0.6 decision is *a loud warning and nothing else*, covering
   `copy_number` **and** `repeat_count` because both were placed in `_INTEGER_KINDS` on a premise the
   spec withdrew. Author real fractional copy number (`CN=1.25` is in the 4.4 examples; a segment mean
   is continuous by construction) and check: does the warning fire on `copynumbers.csv` at all, is it
   aggregated, and does it say the fix is 0.7 rather than implying the author did something wrong?
   Then the silent case that motivated it — integer bins `[0,0] [1,1] [2,2] [3,∞)` compiling green
   under `--strict` while a CN of 2.4 matches nothing.
2. **`activity_phenotype` is the untested kind.** It is in neither `_INTEGER_KINDS` nor
   `_CONTINUOUS_GAP_KINDS`, so it gets no gap warning and a shared endpoint is an **overlap error**.
   Author CPIC's own bins and see whether the source's real numbers author cleanly — the hole between
   1.0 and 1.25 must not warn (activity scores are summed on a quantized grid), and two bins meeting
   at 1.0 must be an error. If CPIC's real table cannot be authored without a workaround, that is
   RM35's unsatisfiable triangle on the third kind.
3. **RM53's newest collision.** `CN` became an INFO **and** FORMAT key in 4.4 — the newest member of
   the collision set and the only one with no instantiation. `source_field: CN` bare must warn;
   `FORMAT/CN` must not.
4. **RM54 where the reference element decides the answer.** A duplication carried as `Number=R` `AD`
   or as a packed CN pair — `largest` versus `largest_alt` is a different number, and the vocabulary
   claims to state the reference-inclusion rule for every member. Author both and read
   `ELEMENT_RULE_MEANINGS` back through `just-dna-compiler describe`: does an author reading only the
   generated reference learn which one they want?
5. **RM56 on a copy-number CI.** A segment call with a confidence interval spanning two bins. 0.6's
   stated behaviour is *withhold, and say loudly that no policy exists*. Check that it says so once,
   not once per row.
6. **RM5 + RM59 + RM67 together.** `<DUP:TANDEM>` and `<CNV:TR:30>` as authored alleles (RM5's open
   subtypes below the closed five); `*` at a CYP2D6 SNP overlapped by the `*5` deletion — the
   biologically natural `*`, and the control for D1's hostile one; and the polyploid genotype
   `0/1/1`, which is refused. RM67 is *not work* — the probe is only whether the refusal message makes
   the documented divergence findable, since the spec's own polyploid example is a duplication with
   SNVs on it and this is the module that would meet it.
7. **RM65's corrected comment.** 0.6 corrected the claim that these tables are "not joinable by
   position, which is a property of what they describe". Read the corrected comment against this
   module: it should now say the non-joinability is a **schema gap** gated on a real caller VCF. If
   the module makes the gap concrete, it *is* the gating evidence RM65/RM66 wait for — file it as
   that, not as a finding.

**Network.** CPIC snapshot (`cpic build` or the published snapshot); otherwise offline.

---

## D4 — `hboc_panel`: the whole pipeline, and the first attestation in the corpus

**RMs** RM4, RM24, RM25, RM45, RM27, RM46, RM50, RM47, RM49, RM51, RM44, RM43.

**Real basis.** A hereditary breast/ovarian panel — BRCA1, BRCA2, PALB2, ATM, CHEK2 — drafted from
the **built** ClinVar snapshot (`data/interim/clinvar`, built from the local VCF at
`/data/just-dna-cache/clinvar/clinvar_GRCh38.vcf.gz`, 2026-06-27). ClinGen and GenCC both
curate all five, at different strengths and with more than one submitter, which is what RM24's key
had to grow to hold.

**This is the only item that runs every derived producer in one module**, and the corpus has zero of
them. Sequence: `draft-panel` → `enrich` → `frequencies` → `gene-metrics` → `gene-validity` →
`assertions` → `literature` → `compile`.

**Claims attacked:**

1. **RM4's machine-stamped provenance, end to end.** `clinvar_draft` stamps the release into the
   licence row's `dataset`, and `tautology_reason` recomputes the same label — one function, both
   sides, because a writer and a reader disagreeing would silently never match. Probe the three
   states: a fresh draft (skip, with the `best_effort` notice naming the hole), a hand-edited
   `clin_sig` (the hole the notice names — does `--strict`'s audit put it in `conflicting` rather than
   `authored`?), and a **re-draft from a second release**, which must *withdraw* the `dataset` label
   rather than re-label it. That last one needs two snapshots and is the only way to reach
   `withdraw_stale_dataset`.
2. **RM4's allele-exact "copied".** `rs334` carries pathogenic `T>A` beside likely-benign `T>G`; the
   panel genes have their own multi-allele sites. A locus-wide fallback must land such a row in
   `authored`, never in `copied`.
3. **RM24's orphan check and its key.** `gene_validity.csv` names genes the module never mentions →
   warning. Drop a gene from `variants.csv` after enriching and confirm it fires. Then the key
   correction probing produced: a ClinGen gene/disease pair with two modes of inheritance, and a GenCC
   entry where submitters **disagree** — both must survive as separate rows rather than collapsing to
   one arbitrary verdict.
4. **RM25 beside RM4.** The assertion table records ClinVar's own call for a panel *drafted from
   ClinVar*, i.e. the same value twice by two routes. `VALID_VERIFICATION_CHECKS` deliberately has no
   member for the assertion tier ("records what ClinVar says and adjudicates nothing"). Confirm the
   manifest does not report a check here — and that the tautology skip does not silently swallow the
   assertion rows too.
5. **RM45, the whole point of the item.** Write the attestation, then break it four ways: edit one
   authored byte (expect *warn and drop the block*, compile succeeds, manifest says nothing);
   re-enrich with no change (the nonce is deterministic, so the bytes must be identical);
   `reverse` → recompile (see D6); and run offline (every check must land under a skip reason, with
   `not_requested`, `offline` and `not_permitted` kept apart). Time the proof-of-work on a panel-scale
   module — the budget is ~1 s per sidecar per run and the measured median is ~0.4 s.
6. **RM46 + RM50 through real citations.** Cite a CC-BY and a CC-BY-NC article and carry a
   `provenance_quote` from the second — the article licence must land on the derived row, the quote
   must warn in **both** modes, and nothing must gate. Author `PMC 3110566` (the spelling that used to
   be accepted as a different paper) and confirm the refusal *names the PMC id*. Use
   `hint citation --pmcid` and confirm it reports rather than fills.
7. **RM47's relaxation, on a panel.** A `studies.csv` row naming no subject — legal since 0.6 —
   alongside subject-bearing ones. Confirm the orphan half of `_cross_validate_studies` skips it and
   the dedup key still catches two subject-less rows citing one paper.
8. **RM49 + RM51.** Move all six machine-written sidecars under `derived/`, keep the licence table as
   `licensing.csv`, re-run `enrich` and confirm it writes to the file it read. Then put a copy at the
   root and confirm the error names **both** paths. Then the guard: drop a `derived/varaints.csv` and
   confirm it is reported as **misplaced** (an exact match against the wrong name set), not silently
   tolerated.

**Network.** Everything except `draft-panel` and `compile` needs egress.

---

## D5 — `fmr1_cgg_repeat`: a repeat table that can cite, on a hemizygous contig

**RMs** RM47, RM54, RM55, RM56, RM66, RM53, RM63.

**Real basis.** FMR1 CGG repeat — normal ≤ 44, intermediate 45–54, premutation 55–200, full mutation
> 200 — with AGG interruptions (`RUS=CGG,AGG,CGG`), on chrX. Every threshold is published and citable,
which is the point: `htt_repeat_expansion` stays deliberately uncited as the example of the gap, so
RM47's *fix* has no worked instance anywhere in the corpus.

**Claims attacked:**

1. **RM47's actual fix.** Ground each of the three FMR1 boundaries with its own `pmid`, and describe
   the papers in `studies.csv` without inventing a subject. Then the same-release obligation that was
   the reason the item was filed: `_cross_check_literature` and the enricher's literature pass must
   **both** see the bin pointers. Delete `literature.csv` and re-run — a bin-only citation must be
   fetched; leave a stale one — a bin pointer must not read as an orphan.
2. **RM54 where "the larger of the two" has one value.** FMR1 is on X: a male sample is hemizygous, so
   `REPCN` carries one number, not two. `largest` is defined as "the greatest of the values the field
   carries", which is well-defined for one value — but the meaning sentence says "the longer of the
   sample's two alleles", which is a claim about a diploid record. This is the sharpest wording probe
   in the batch: a rule whose *description* assumes a ploidy the contig does not have. Author it and
   read the description back through `describe`.
3. **RM56 on a 10-wide window.** The intermediate zone is 45–54. A real call with a confidence
   interval of ±5 spans two thresholds — the same geometry as HTT's, on a different gene, and the
   withhold behaviour must be identical.
4. **RM55's repeat half.** `RUC` is a Float in the spec, and `repeat_count` is in `_INTEGER_KINDS`.
   The FMR1 bins tile the integers cleanly, so this is the case where the warning must fire *even
   though nothing looks wrong* — which is the whole reason 0.6 made it loud.
5. **RM66's gating evidence.** `(gene, repeat_unit)` binds one count to one motif, and the AGG
   interruption structure means the pure-CGG tract and the total differ — with published effect on
   expansion risk. Author it and see what the module *cannot say*. Deferred to 0.7, so the deliverable
   here is the evidence, not a fix.
6. **RM63.** Author a pipe-separated genotype somewhere in the module and confirm the corrected
   docstring reaches the generated authoring reference — "heterozygous, phase recorded but
   unaddressable", not "which allele sits on which homolog".

**Network.** Literature pass needs egress; the rest is offline.

---

## D6 — the corpus sweep: what a round trip does to things that did not exist before 0.6

**RMs** RM43, RM45, RM49, RM51, RM44, RM27, and P7 across the batch.

No new module. This is the adversarial pass over the five above **plus** the eleven shipped examples,
and it is where the P7 interactions live. Each line is a claim to falsify:

1. **The attestation and the round trip.** `verification.json` is in `_DERIVED_FILES` but is not a
   fact table, has no parquet, and `reverse` cannot rebuild it. So: does `compile → reverse → compile`
   produce a manifest that **loses** `manifest.verification`? If it does, a module and its own round
   trip disagree on a published field — the RM44 class, which three lanes hit independently in this
   batch. And the attestation binds byte hashes of the authored files while `reverse` normalizes cell
   formatting and column order, so a round-tripped spec's attestation may read as stale **to its own
   compiler** with nothing edited. Both are legitimate outcomes; neither is documented.
2. **RM43's forced consequence, on every positional module.** `reverse` rebuilds `resolution.csv`
   from the positional parquets as a second source. Verify the fixed point on all five positional
   modules (three existing + D1 + D2), and verify the *provenance* rules on the rebuilt table
   (`source="reversed"`, `status="resolved"`, blank `fetched_at`).
3. **The `sources.csv` → `licensing.csv` migration on reverse.** RM51 says a round trip migrates the
   name and the signatures do not move. `hfe_hemochromatosis` is the only module carrying the old
   spelling — round-trip it and compare all four signatures.
4. **`derived/` survives a publish.** RM49 says `manifest.derived` carries the relative path so a
   re-splitting registry can restore the layout. Flatten D4, compile, then re-split from the manifest
   alone and confirm the attestation still validates — the failure this mechanism exists to prevent.
5. **The signature ledger.** Recompile all eleven examples plus the five new ones and record
   `artifact.digest`, `content_signature`, `resolution_signature` and `source_signature` before and
   after — by comparison, never by assumption. The batch's own measured numbers (two content
   signatures moved, seven digests, four resolution signatures gained) are the baseline to reproduce.
6. **The count rule, swept.** Grep every warning whose message embeds a count and check which side of
   resolution it runs on. Three lanes shipped this defect independently; the rule is new; nothing
   sweeps for it.
7. **The consumer contract's unstated rules (RM62, RM64).** Two 0.6 findings that changed no schema
   and exist only as prose: an inclusive upper bound can be missed by a float32 read of a value that
   looks equal, and the VCF ID column is a semicolon-separated list a consumer must split before
   joining on it. Read the contract as an implementer who has only the published docs and the
   generated reference — if either rule is not reachable from there, the finding never landed.

---

## Coverage

| RM | Item(s) | What is being attacked |
|---|---|---|
| RM4 | D4 | the machine-stamped `dataset`, the mode ladder, allele-exact "copied", the two-release withdrawal |
| RM5 | D1, D2, D3 | placement (droppable vs fatal), lengthless refusal, subtypes, CPIC's two unusable kinds |
| RM24 | D4 | the orphan check, the MOI + submitter key, GenCC disagreement |
| RM25 | D4 | the tier persisted beside a ClinVar-drafted panel; no verification member |
| RM27 | D2 | the compile gate refuses without a recorded declaration; `--use` is an *enricher* flag, so a compiler `--use` was never the probe |
| RM43 | D1, D2, D6 | the fill on all three positional kinds, off GRCh38, and reverse's second source |
| RM44 | D2, D4 | `resolution_subjects` as the denominator of a vacuous flag |
| RM45 | D2, D4, D6 | staleness, determinism, skip vocabulary, PoW budget, round-trip survival |
| RM46 | D4 | article licence on the derived row; the quote warns and gates nothing |
| RM47 | D1, D5 | the boundary citation, the subject relaxation, the same-release obligation |
| RM48 | D1, D2 | the offline errors' real reach, and where only the online half can see |
| RM49 | D4, D6 | write-to-the-file-you-read, both-present, the `derived/` guard |
| RM50 | D4 | the guard names the PMC id; the lookup reports and never fills |
| RM51 | D2, D4, D6 | the migration on reverse, signatures unmoved |
| RM53 | D1, D3 | the qualified form, and the collision warning on `AF`, `DP`, `CN` |
| RM54 | D1, D3, D5 | element rules where reference inclusion decides; the reserved companions; a hemizygous "larger" |
| RM55 | D3, D5 | the warning fires on both kinds, aggregated, and points at 0.7 |
| RM56 | D3, D5 | withhold, said once |
| RM57 | D6 | the inversion warning on the row type it exists for (moved from D2: `requires_callable` is `VariantRow`-only and D2 has no `variants.csv`) |
| RM58 | D1 | `.` diagnosed as MISSING, not as notation |
| RM59 | D1, D3 | `*` natural (autosomal) and hostile (haploid + ploidy check) |
| RM60 | D1 | the widening, and whether it blinded RM48's contig check |
| RM61 | D1 | dotted keys and `1000G` |
| RM62 | D1, D6 | whether the float32 tolerance rule is stated where an implementer reads |
| RM63 | D5 | the corrected docstring reaches the generated reference |
| RM64 | D6 | the split-the-ID-column rule is stated in the consumer contract |
| RM65 | D3 | the corrected comment, and the gating evidence |
| RM66 | D5 | the gating evidence (AGG interruptions) |
| RM67 | D3 | the refusal makes the documented divergence findable |
| charter amendment | D3, D4 | that a derived sidecar really was cheap to add, measured in author-facing surface |

---

## What this plan deliberately does not do

- **It does not try to "finish" RM55, RM56, RM65, RM66 or RM67.** Anyone who does has either broken
  the charter or guessed at a vocabulary — the proposal says so explicitly, and the probes above are
  written to test the *stated* behaviour instead.
- **It does not verify the tools' answers with a second implementation.** That is a test and belongs
  in the suite. Dogfooding asks whether the thing is usable and what is missing.
- **It does not touch `htt_repeat_expansion`'s uncited thresholds.** That example exists to show the
  gap; D5 is the module that shows the fix.

## Suggested order and shape of the work

D2 first (largest lane, uniform corpus, one probe on the RM48 sibling for free), then D1, D3, D5, D4,
and D6 last because it sweeps everything the others produced. Each lands as a
`reference_examples/<name>/` with a README naming what it broke, plus a regression test that
demonstrates the failing observation on the **old** behaviour rather than asserting that it used to
fail. Findings split before any code is written: fix a false claim, a misdiagnosis, an unaggregated
wall of warnings or a guard that is never reached; surface anything whose obvious repair is itself a
design decision, with the reasons each candidate repair is wrong.
