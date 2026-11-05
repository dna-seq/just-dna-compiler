# Roadmap — 0.8 (closed)

**Closed on 2026-11-05, when 0.8.0 was cut.** This was `docs/ROADMAP_0_8.md`: 0.8's scope from 2026-11-03,
and before that the minor-deferral file. It is kept here for the record of what 0.8 took in and why.
Every item it scoped shipped, and each record is in [ROADMAP_HISTORY.md](../ROADMAP_HISTORY.md); the
known issues 0.8 shipped with are in [INTEGRATION_0_8.md § 4](../INTEGRATION_0_8.md#4-known-issues).

**Where its contents went.** The one item still waiting, RM28's predicate half, moved to
[ROADMAP_0_9.md](../ROADMAP_0_9.md) unchanged but for the file it sits in; the decisions its combination
half was built to stay below. [RM_TOC.md](../RM_TOC.md) indexes every item and is where to look one up.
Nothing here is edited as routine work, the same rule as the rest of this folder.

**What 0.8 is, decided 2026-11-03 with the maintainer:** the work already built and the fixes already
chosen, plus longevitymap v2's requirements. "The rest goes to 0.9", so everything else that was waiting
here moved to [ROADMAP_0_9.md](../ROADMAP_0_9.md), each entry with a dated line under its heading. That
includes RM188's competitor-parity work, which was 0.8's second half from 2026-09-11, the methylation items
(RM317–RM319), and the Gherkin corpus (RM149), which is frozen. This file is now 0.8's scope and nothing else.

Every item is additive under Principles 3/4/8, so each is legal in a minor. Indexed in
[RM_TOC.md](../RM_TOC.md), which is the complete list and the place to look an item up.

## The scope

| Part | Items | Where | State |
|---|---|---|---|
| Built on the `0.8` branch, uncut | PT1's RM241, RM258, RM263, RM272, RM275, RM278, RM283, RM288, RM300, RM308, RM313; earlier RM256, RM257, RM259, RM260, RM262 and RM264's docs half | `proposals/PROPOSAL_0_8_PT1.md` and ROADMAP_HISTORY on the `0.8` branch | done (their entries are in ROADMAP_HISTORY since the 2026-11-04 sync) |
| The indel-placement fixes | [RM304](../ROADMAP_HISTORY.md#rm304--a-vrs_id-does-not-say-which-vrs-minted-it-and-vrs-21-moves-some-insertion-ids) first, then [RM267](../ROADMAP_HISTORY.md#rm267--the-ensembl-snapshot-anchors-a-class-of-insertions-one-base-early-and-resolutioncsv-serves-them-as-a-different-event), [RM270](../ROADMAP_HISTORY.md#rm270--an-indels-artifact-key-is-its-sources-spelling-a-left-aligned-vcf-misses-a-respelled-row-and-the-spelling-independent-id-the-enricher-mints-never-reaches-the-artifact), [RM292](../ROADMAP_HISTORY.md#rm292--a-verification-check-does-not-say-what-it-checked-against-so-a-check-that-witnesses-itself-reads-as-verified), [RM305](../ROADMAP_HISTORY.md#rm305--clinvar-gkms-allele-table-is-an-offline-independent-witness-for-where-an-indel-sits-and-nothing-reads-it) | [ROADMAP_HISTORY.md](../ROADMAP_HISTORY.md) | all five shipped on `0.8` (2026-11-04) |
| The lead's ready minors (2026-11-04) | RM337 (a warning naming each `logs/` file left behind), RM342 (the toolchain in the manifest, with the polars 2 lock) | their entries are in ROADMAP_HISTORY | both built on `0.8` (2026-11-04) |
| Added by the maintainer (2026-11-04) | [RM372](../ROADMAP_HISTORY.md#rm372--the-ensembl-snapshot-moved-to-a-new-hugging-face-repo-and-a-warm-cache-never-migrates) (the Ensembl snapshot moves to its new Hugging Face repo), and RM384, its tail placed by the pm on 2026-11-05 (a public name for the moved lane) | ROADMAP_HISTORY | RM372 shipped 2026-11-04 on `0.8`; RM384 merged into `0.8` (2026-11-05) |
| The pre-cut audit, round 1 (2026-11-04) | RM361–RM370, one item per class of error the audit found; and RM267's REST witness (Ensembl REST as the placement's third, online-only witness, paced under its budget) | ROADMAP_HISTORY on the `0.8` branch | all shipped on `0.8` (2026-11-04) |
| The pre-cut audit, round 2 (2026-11-05), sized by the pm at the maintainer's request ("what really blocks the release") | **Blocks the cut:** RM387 (a hosting-narrowed rsID answer is compared as if it were the source's whole answer, so strict refuses a valid module whose rsID the source places at two loci; RM374's new check, and `--rederive` writes the same shape, so the author has no remedy) and RM389 (reverse empties a legal `vrs_spec` cell, a P7 loss, because the reproduced-locus check compares fewer columns than its own registry rebuilds; from RM364). Both are 0.8's own regressions, never in a release. **In only if built and cheap to merge:** RM361's amendment (a retired endpoint recorded as an outage in more lanes; merged whole), RM391 (the test network fence covers only the Hugging Face hub; 31 tests reach live services), RM392 (prose counts drifting from the table beside them). **Built, so in (the maintainer: "defer unbuilt items"):** RM386 (a snapshot publish not pinned to its bytes or revision; rare, since it needs a concurrent writer). **Parked** until a real run meets them (the maintainer's rule, 2026-11-05): RM388 (placement readers that skip the shared build and not-found filter: only a hand-written or multi-build table reaches them), RM390 (the enricher does not warn about what compile will refuse; compile still refuses correctly) | ROADMAP_HISTORY on the `0.8` branch; RM388, RM390 parked in ROADMAP.md | RM387, RM389, RM361's amendment, RM386, RM391 and RM392 merged into `0.8` (2026-11-05); RM388 and RM390 ship as known issues (INTEGRATION_0_8 § 4) |
| The pre-cut audit, round 3 and the docs pass (2026-11-05, at `64c835b9`), sized by the pm under the maintainer's frequency rule | **Blocks the cut**, each on the `--rederive` migration path every consumer is told to run: a rederive with no position→rsID map erases a back-filled rsID and the artifact carries `rsid=null` (measured on a copy of hfe_hemochromatosis); the drift label calls an allele gain "moved: the source names a different event" (94 subjects in the examples); the currency message sends an operator with an old snapshot to `--rederive`, which repeats it; the carry warning says "no source could be asked" about subjects that were asked. **In, as the docs pass:** INTEGRATION_0_8's consumer lists (seven columns, `authored_event`/`judged_coordinate`, PMID through `spec.citation_key`); `mt_common_deletion`'s stale licence row; and three guide commands that fail: `keygen --out` into a missing directory, `draft-repeats` ignoring the provisioned STRchive lane, `cache status`/`cache pull` describing the lane registry instead of the disk. A guide fix whose code fix outgrows about 30 minutes changes the guide instead. **Parked**, in ROADMAP.md's list of audit findings without a number: the other eleven | ROADMAP_HISTORY on the `0.8` branch (RM393, RM394, RM395); the eleven in ROADMAP.md's list | RM393, RM394, RM395, the user-guide re-run and `mt_common_deletion`'s re-derivation merged into `0.8` (2026-11-05) |
| Added by the maintainer (2026-11-04, the interview on RM372's migration probe) | RM373 (each resolution row names the release that answered it, and the `SourceRow` its dataset), RM374 (one rsID with two placements warns, and is refused under strict), RM375 (the enricher judges whether two spellings are one event, and compile trusts that answer), RM376; and every example's `resolution.csv` regenerated against the new snapshot. Found while building and regenerating these (the lead, 2026-11-05): RM380 (reverse carries every `resolution.csv` column), RM381 (each ALT of the new snapshot's multi-ALT indels trimmed on its own), RM382 (an answer the hosting filter rejects no longer ends the chain; reverses S85's "the row stays" for an rsID no link could host, by the maintainer's word), RM383 (a rederive drops a licence row no row names) | ROADMAP_HISTORY on the `0.8` branch | RM373–RM375 and RM380–RM383 merged into `0.8`; RM376 closed as not a defect, records only; the examples regenerated except `hboc_palb2` and `pathogenic_clinvar` |
| Chosen earlier | [RM303](../ROADMAP_HISTORY.md#rm303--the-snapshot-layout-is-a-contract-with-six-parties-and-no-model-so-it-belongs-in-just-dna-format) (the snapshot layout as a model), [RM253](../ROADMAP_HISTORY.md#rm253--a-repeat-count-star-allele-ugt1a1-28--ta8-has-no-home-a-diplotype-can-name-and-the-cpic-drafter-translates-none-of-cpics-notation) (a repeat-count star allele) | ROADMAP_HISTORY | both shipped 2026-11-04 on `0.8` |
| longevitymap v2 | RM28's combination half, RM322–RM336 ([the group](#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03)), and [RM236](../ROADMAP_HISTORY.md#rm236--consequence-and-impact-are-planned-axes-with-no-slot-and-an-acmg-engine-reads-both-as-primary-inputs), [RM239](../ROADMAP_HISTORY.md#rm239--a-fine-mapping-posterior-has-no-column-and-gwas_effectscsv-already-has-its-key) as inputs to RM333's confidence labels | this file and [ROADMAP.md](../ROADMAP.md) | design first; RM323 decides before RM324, RM326 and RM329 |

Patch-class items stay on `main` and are not part of this scope, as [RELEASE_CYCLE.md](../RELEASE_CYCLE.md) says.

---

## longevitymap v2 — what its requirements need from the format, taken into 0.8 as a priority (2026-11-03)

**Source.** just-dna-lite's `docs/longevitymap_v2/longevitymap_v2_requirements.md` (draft 1, 2026-11-03),
the plan for re-curating `longevitymap` as 2.0.0 around evidence tiers and seven per-locus axes. It was
read against the 0.7.1 schema on 2026-11-03. Most of its §6 fits today. The items below are the places where
it does not, each with its Principle 9 price. Every one is additive, so each is legal in a minor (P3/P8).

**Status.** The maintainer took the fifteen new items into 0.8 **as a priority** on 2026-11-03. One shape is
already decided: `tradeoff` is **computed** from per-trait rows and never authored (RM327). Every item
the plan needs, new or older, carries the tag `*for* longevitymap v2` in its index row, so
`grep -n 'for\* longevitymap v2' docs/RM_TOC*.md` lists the whole group. Its build plan is the
proposal for the next round on the `0.8` branch, which the pm seat writes; PT1 is concluded.

**Order.** RM323 first, because RM324's tier, RM326's outcome strip and RM329's age-of-action class all
land wherever RM323 puts per-locus facts. RM322 next, since APOE is the lead locus.

| Item | What it adds | Price (P9) | Note |
|---|---|---|---|
| [RM323](../ROADMAP_HISTORY.md#rm323--a-fact-about-a-locus-has-no-authored-home-so-every-per-locus-axis-is-copied-onto-each-genotype-row-and-nothing-checks-the-copies-agree) | where per-locus facts live: typed columns per genotype plus an agreement warning, or a locus table | full ×n, or a new table kind | **decide first** |
| [RM322](../ROADMAP_HISTORY.md#rm322--diplotypescsv-carries-none-of-the-axes-a-scored-finding-needs-so-apoe-the-modules-headline-result-cannot-state-its-tier-mechanism-or-trade-off) | `DiplotypeRow` gains `negatives` and `category` (`priority`, `actionability`, `flags` cut) | full ×2 | ✅ shipped 2026-11-04 |
| [RM324](../ROADMAP_HISTORY.md#rm324--there-is-no-evidence-tier-column-so-the-axis-that-gates-visibility-is-a-flags-tiera-token) | evidence tier as value + scheme | full ×2 | home from RM323 |
| [RM325](../ROADMAP_HISTORY.md#rm325--studiescsv-has-no-sample-size-and-v2s-tier-a-rule-is-stated-in-n) | `StudyRow` sample size, its unit, and cases | full ×3 | ✅ shipped 2026-11-04 |
| [RM326](../ROADMAP_HISTORY.md#rm326--a-study-row-cannot-say-which-outcome-it-measured-so-the-definition-of-pro-longevity-lives-in-a-study_design-prefix) | `StudyRow` phenotype class; the outcome strip derived from it | full ×1, derived near-zero | ✅ shipped 2026-11-04 |
| [RM327](../ROADMAP_HISTORY.md#rm327--pleiotropy-has-no-per-trait-row-so-a-trade-off-can-only-be-prose-and-tradeoff-is-computed-rather-than-authored) | per-trait benefit/harm table (mediator folds in); `tradeoff` computed; reserve the name | full (new kind), derived near-zero, reservation a patch | ✅ shipped 2026-11-04 on `0.8`, uncut |
| [RM328](../ROADMAP_HISTORY.md#rm328--no-study-row-can-name-the-ancestry-it-was-measured-in-so-european-only-evidence-is-a-hand-set-flag) | `StudyRow` ancestry on a vocabulary; `eur_only_evidence` derived | full ×1, derived near-zero | ✅ shipped 2026-11-04 |
| [RM329](../ROADMAP_HISTORY.md#rm329--an-age-stratified-estimate-has-no-age-band-so-age-of-action-is-reconstructed-from-statistical_test-prose) | `StudyRow` age band and whose age | full ×3 | ✅ shipped 2026-11-04 |
| [RM330](../ROADMAP_HISTORY.md#rm330--an-effect-measured-in-one-sex-one-smoking-stratum-or-one-genotype-has-no-row) | the stratum an estimate was measured in; sex as the first query-time modifier | full ×2 | ✅ shipped 2026-11-04 |
| [RM331](../ROADMAP_HISTORY.md#rm331--a-study-measured-on-an-ld-proxy-cannot-say-so-and-filing-it-under-the-lead-checks-the-proxys-allele-against-the-leads) | `StudyRow` proxy variant; r² and its population computed into `ld_pairs.csv` | full ×1, derived half | ✅ shipped 2026-11-04 on `0.8`, uncut |
| [RM332](../ROADMAP_HISTORY.md#rm332--a-beta-has-no-unit-on-authored-rows-while-gwas_effectscsv-has-carried-one-since-06) | `effect_unit` on `StudyRow`, joined onto `weights.parquet` when the studies agree | full ×1, derived near-zero | ✅ shipped 2026-11-04 |
| [RM333](../ROADMAP_HISTORY.md#rm333--the-effector-gene-behind-a-gwas-locus-has-no-source-and-no-column) | an Open Targets lane; effector gene, score, release on a derived table | half, plus a lane | ✅ shipped 2026-11-04 on `0.8`, uncut |
| [RM334](../ROADMAP_HISTORY.md#rm334--an-hla-allele-has-no-table-and-tag-snps-cannot-stand-in-for-one) | the IPD-IMGT/HLA name grammar on `allele_function.csv` (the table was cut) | near-zero (a refusal) | ✅ shipped 2026-11-04 |
| [RM335](../ROADMAP_HISTORY.md#rm335--model-organism-evidence-has-nowhere-to-go-and-a-study-row-naming-the-rsid-claims-the-mouse-study-was-about-the-human-variant) | a model-organism evidence table (not a lead table) | full (new kind) | ✅ shipped 2026-11-04 |
| [RM336](../ROADMAP_HISTORY.md#rm336--a-doi-written-into-pmid-parses-as-five-or-six-pubmed-ids-and-the-literature-pass-looks-each-one-up) | a DOI-token arm in `validate_pmid_cell` | near-zero (a refusal or a warning code) | **shipped 2026-11-04 on `0.8`, uncut** |

**Older items the plan also needs, tagged rather than moved** (each keeps its own entry; the 2026-11-03
scope decision put each in 0.8 or 0.9, as marked):

- **RM236** (**shipped 2026-11-04 on `0.8`**, in ROADMAP_HISTORY) — causal confidence C1 and effector confidence E1 both key on a variant being coding.
- **RM238** ([ROADMAP_0_9.md](../ROADMAP_0_9.md), **0.9** since 2026-11-04: Open Targets' coloc, in RM333's lane, replaces it) — the cis-QTL colocalisation behind effector confidence E1/E2.
- **RM239** (**shipped 2026-11-04 on `0.8`**, in ROADMAP_HISTORY) — the fine-mapping posterior is the input to causal confidence C1–C4.
- **RM241** (this file, **built on `0.8`**) — v2 declares `weighting:` precisely to say it has no weights, and `reverse` drops the block.
- **RM263** ([ROADMAP.md](../ROADMAP.md), **built on `0.8`**) — v2 cites preprints, whose rows hold a DOI and need a PMID; RM336 is the parsing half.
- **RM294** ([ROADMAP_0_9.md](../ROADMAP_0_9.md), **0.9** since 2026-11-04, after the one-scale tier decision) — a source's evidence grade travelling into a module is the same column family as RM324's tier.
- **RM302** ([ROADMAP_0_9.md](../ROADMAP_0_9.md), **0.9** since 2026-11-04: v2's conclusion is already lay) — v2 writes for three readers (citizen, geneticist, ageing researcher), which is the register question.
- **RM308** ([ROADMAP.md](../ROADMAP.md), **built on `0.8`**) — v2 hand-writes per-genotype conclusions for its scored loci and a 528-rsID legacy layer.
- **RM321** ([ROADMAP.md](../ROADMAP.md), **a patch on `main`**) — v2's plan sets `pleiotropic` and `conditional` expecting behaviour.
- **RM28** (this file, **0.8**: its combination half, taken in 2026-11-04) — KL-VS buffering in APOE4 carriers joins two loci on two chromosomes, so no haplotype holds it. It is now a defined combination, and its facts sit on RM323's table.
- **RM188** ([ROADMAP_0_9.md](../ROADMAP_0_9.md), **0.9**) — its axes 2, 3 and 5 are now numbered, as RM328, RM330 and RM324, all three in 0.8.
- **RM248** ([ROADMAP_0_9.md](../ROADMAP_0_9.md), **0.9**) — v2's §5 is a report specification: a context card, grouping by mechanism, a research view. The report is the consumer's to build meanwhile.

The authored `report:` block in [ROADMAP.md's idea-book](../ROADMAP.md) is the unnumbered half of RM248 and
answers v2's §8 consumer requests 1 and 2 (category prose from the module, no "Net weight").

## RM28 — Meta-conclusions: the combination half's decisions (shipped in 0.8)

**Built on 0.8, 2026-11-04: the combination half** (the meta-table; its shipped record is [ROADMAP_HISTORY § RM28](../ROADMAP_HISTORY.md#rm28--the-combination-half-the-meta-table)). The study-orphan widening (B1 step 4) shipped on `0.8` the same day, in wave 3, recorded in the same history entry. The predicate half's remainder (open-world negation, OR, *trans* phase), which the maintainer put out of bounds on 2026-11-04 and 0.8 did not build, moved at the 0.8.0 cut with its corpus to [ROADMAP_0_9.md § RM28](../ROADMAP.md#rm28--meta-conclusions-the-predicate-half), where it stays parked. What follows is the record of the decisions the combination half was built to.

**The name and grammar, accepted 2026-11-04 by the maintainer, as written in `proposals/PROPOSAL_0_8_PT2.md`
§3 items 1–4.**

- The file is `meta.csv`, and its parquet `meta.parquet`.
- There is one member grammar, `table[column=value, …]`.
- Members are joined by `&` in one bracket-aware `members` cell.
- Precedence follows from the conditions.
- The key is the sorted members, plus the trait, plus `sex`.

No bare-rsID shorthand yet. Adding one later is additive, if authors ask.

**Settled 2026-11-04 by the maintainer, after the second measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §6):

- **The narrower condition outranks, across tables too.** A diplotype row is more specific than an allele row
  for an allele it contains, just as a genotype row outranks its locus. The ε2/ε4 diplotype row settles the
  tie between the ε2 and ε4 allele rows.
- **`role` has one meaningful value:** empty means an effect, and `mediator` marks the path. Chains of two
  steps (9 v2 loci, LDL → CAD) stay as unordered mediator rows plus prose.
- **A locus-level member counts as allele-bearing** when every row of that locus states one `effect_allele`.
  A warning fires when they differ. That gives v2 about 134 per-trait rows instead of about 268.
- **Two rules set by the pm seat, unless the maintainer objects:**
  - the member tables are those that carry a finding (variants, diplotypes, pharm_variants), plus
    `allele_function.csv` as allele items. `haplotypes.csv` defines alleles and is not one.
  - the LD lookup withholds r² (unknown, counted) for a mixed-ancestry study, and never picks a panel.

**What is still not held, accepted as prose:** two modifiers on one estimate (2 loci), and two
causal-confidence judgements (README). With these rules the shape is sufficient for v2, and every addition
has a v2 case.

**The selector, widened 2026-11-04 by the maintainer** ("selector is just the right spice for meta"). It
supersedes the tag-only form above.

- **One general form, `column=value`**, over a single-statement table's columns. On a list column such as
  `flags`, `=` means "contains", so the legacy row is `flags=legacy_longevitymap`.
- **Several conditions in one member are AND-ed**, e.g. `diplotypes[gene=TPMT, phenotype=Poor Metabolizer]`.
- **Inside a combination, a selector is existential**: "any row of the set". CPIC's 6 gene pairs (18 drugs,
  2,656 recommendation rows) are written as phenotype pairs, one row each, instead of diplotype × diplotype.
  Lewis (FUT2 × FUT3 phenotypes) is the same shape. In a facts-only row, a selector's facts apply to each
  row it matches.
- **The compiler expands every selector** into the concrete rows it matches, in the parquet, so a consumer
  never evaluates a rule (P1). The authored row keeps its selector through `reverse` (P7).
- **A selector that matches nothing is a warning** (almost always a typo), and the manifest records each
  selector's match count (`@dont-discard-computed`).
- **Precedence:** a concrete row key, then a locus-level key, then a selector with more conditions, then
  one with fewer. Two matches that cannot be ordered and disagree withhold the column.
- **Out of bounds:** negation, OR, numeric ranges, joins across tables, and selectors over `studies.csv`.
  Rows are already a disjunction, and negation over an open set cannot be checked.

**Measured:** for v2 itself the widening adds nothing beyond the tag. Only 3 genes have more than one lead
locus (FOXO3, HTT, TERT), and none shares one tier. Its payoff is the PGx gene pairs and Lewis, at no
column cost: one grammar replaces a list of selector kinds.

**A fifth member form, decided 2026-11-04 by the maintainer: the tag selector.** A member may be
`flags:<tag>`, which means every single-statement row carrying that tag. v2's 528 legacy variants all carry
`legacy_longevitymap` (R-LEGACY-1), so one row (`flags:legacy_longevitymap`, tier D) replaces 528 one-line rows.

The decided rules still apply:

- A one-member row naming a specific variant is more specific, and wins. That covers the legacy loci tiered
  C, or A/B on modern evidence, such as APOE.
- A row in two tag sets that disagree on a column has that column withheld.
- An untagged locus is untouched.

**Rejected:** a module-wide default tier. It would silently turn v2's 31 untiered and 4 tier-X seed loci into D,
a stated value standing in for an unstated one. Raised by a side agent from the final run's audit
(`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §2, R-LEGACY-1).

**Two columns added 2026-11-04 by the maintainer, after the final measuring run** (`probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` §4, gaps 3 and 4):

- **A citation (`pmid`) on meta-table rows.** A row cites when its claim is finer-grained than `studies.csv`'s key, the RM47 pattern. The study-orphan check accepts meta-table members, so APOE's 14 study links, the 8 HLA alleles and KL-VS × ε4 can cite.
- **A role on per-trait rows** (`outcome` / `mediator`). 32 v2 loci act through a trait, such as LDL cholesterol, that is the path and not the outcome.

**Where a difference ends and a disagreement begins: the key, weighed 2026-11-04 by the pm seat at the
maintainer's direction ("it's the good old 'what's a key' in a new skin").** A meta-table row's key is **its
member set, plus `trait_efo_id` on a per-trait row** — and, as built, plus `sex` and `drug` where stated
(2026-11-04: `drug` added at the maintainer's default, so one member set states one finding per drug). The
rule follows from it:

- **The same key twice is a disagreement.** Two rows with one member set (and one trait) are a duplicate key,
  and they are refused as on every other keyed authored table. This is the only place two values can
  contradict each other, so no separate agreement warning is needed.
- **Different keys that nest are a difference.** A locus-level row (`variant_key` alone), a genotype-level row
  (`variant_key` + genotype) and a combination that contains them are three statements. The most specific
  matching row wins, column by column; that is the "combination replaces" decision, extended down to a
  single locus.
- **Unstated is not different** (`@absent-is-not-different`). A specific row that leaves a fact empty does not
  contradict the general row's value, and the general value fills it.
- **The residual is identity, not facts.** One variant reachable under two keys would hide a real
  disagreement as a difference. The archive found exactly one such case: IL6R's rs8192284, merged into
  rs2228145, seeded with two tiers. The existing rsID-merge check catches it during enrichment, because NCBI
  is the merge oracle. It must keep running over meta-table members.

The objection that "tier copies on genotype rows are never compared" no longer applies: under C a fact is
written once, never copied onto genotype rows.

**Final shape, 2026-11-04 ("go with C").** One new table. A row is a composite statement, meaning one or more
members, each an item of a single-statement table, mapped to a finding and/or the per-locus facts. A one-member
row with only facts is how a single locus gets its tier, so RM323 needs no table of its own.

**The rule the maintainer set with it, for every proposal here:** "Always weight your proposals towards
reduction of entities. If something can be built with 20 score, don't build it with 30 for 'tidiness', it is
clutter and bloat in guise of strict-typing of non-strict typed data." Under it, RM327's per-trait benefit/harm
judgements default to rows of this same table (one member, a trait, a direction) rather than a table of their
own; the proposal confirms that or says why not.

**Shape decided 2026-11-04 by the maintainer: the meta-table is a map from a composite statement to a finding.**
A composite statement is keyed on **items of the single-statement tables**: a `variants.csv` row's
`(variant_key, genotype)`, a `diplotypes.csv` row's key, and so on. There is no new subject or state grammar.
"KL-VS heterozygous AND APOE ε4 carrier" therefore names the KL-VS genotype row and the ε4-carrying
diplotype rows, one composite per diplotype, since rows are already a disjunction.

The consequence, raised and accepted: a member must exist as a row of its own table, and that row carries
its own required `conclusion`. The meta-table's rows carry the same per-locus fact columns as the
single-statement tables (RM323).

**Decided 2026-11-04 by the maintainer: a matching combination replaces the single-locus findings it names.** A genome that is KL-VS heterozygous and an APOE ε4 carrier gets the buffered finding instead of the plain ε4 risk. The accepted cost is that a reader that predates the combination table shows the unbuffered risk alone.

**0.8, decided 2026-11-04 by the maintainer: the combination half is built in 0.8.** A combination is defined here as a set of subjects (a variant, a gene or a named allele) each in a stated genotype state, for example KL-VS heterozygous together with APOE ε4. Each defined combination becomes one more kind of subject on RM323's per-locus fact table, so its tier, confidence and age of action live in the same place as a single locus's. Facts never get a second table. Boolean `OR` and open-world negation stay out, as the corpus below argues: rows are already a disjunction.
