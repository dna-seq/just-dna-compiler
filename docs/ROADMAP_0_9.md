# Roadmap — 0.9 and later minors

**What this file is.** Items that are legal in a minor and were left out of 0.8, each with the reason it
waits. It was opened on 2026-11-03, before 0.8 is cut, when the maintainer scoped 0.8 to four things:

- the work already built on the `0.8` branch;
- the indel-placement fixes;
- RM303 and RM253;
- longevitymap v2's requirements.

"The rest goes to 0.9." Opening the next minor's file before the cut has a precedent:
`ROADMAP_0_7.md` was split out on 2026-08-13, four days before 0.6.0 was cut. The rule is the one
[ROADMAP_0_8.md](ROADMAP_0_8.md) followed: the deferral file is named for the release that will decide its
contents.

**0.9's theme is not decided.** Competitor parity, with RM188 as its spine, was 0.8's second half from
2026-09-11. It moved here with the 2026-11-03 scope decision, not as a decision about what 0.9 is. Three of
RM188's items stayed in 0.8: RM236, RM238 and RM239 are inputs to longevitymap v2's causal and effector-gene
confidence labels.

**Three groups moved together.** Methylation (RM317–RM319) was deferred by the maintainer. The Gherkin
corpus (RM149) is **frozen** rather than waiting; its entry says why. The ten minors at the end of this file
were open on [ROADMAP.md](ROADMAP.md) with their release undecided. Each moved entry carries a dated line
under its heading, and its status line predates that line.

Everything here is **additive under Principles 3/4/8**, a new optional column or table, so none of it is
waiting on a version. Each item waits on a design question, a corpus, a consumer, or now a release. An item
waiting on a **version** belongs in [ROADMAP_1_0.md](ROADMAP_1_0.md) instead. RM69 moved there on 2026-08-27
for exactly that reason: filing an item by what a fix *costs*, rather than by what decides it, is how it
becomes unreachable from either plan. **RM68 stays.** The two look alike, so the difference is worth
spelling out: RM68's governing exit is *a real author with a non-GRCh38 module saying which outcome they
wanted*, and an exit that waits on demand keeps an item in a minor's file where one that waits on a version
does not.

**Two of these are not waiting on us at all.** RM84's own half shipped in the 0.6 PT2 batch, and only the
consumer's discovery half is open. RM67 is **not work**: it is a documented divergence, numbered so it stays
findable and does not get re-probed. Both are here so that a reader meets the reasoning instead of
re-deriving it.

Indexed in [RM_TOC.md](RM_TOC.md), which is the complete list and the place to look an item up.

---

## RM317 — FMR1 repeat methylation is in every PacBio TRGT VCF as `FORMAT/AM`, and no module can bin it on a two-allele record

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (a `measure_kind` member, the element-rule vocabulary, the host table) + compiler · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO §§ 1.1, 3, 4.1](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM66, RM65, RM164

**What is real.** TRGT, PacBio's tandem-repeat genotyper and part of the HiFi WGS pipeline since at
least v2.1.0, writes `##FORMAT=<ID=AM,Number=.,Type=Float,Description="Mean methylation level per
allele">`: the mean 5mC level over the CpGs **inside the repeat tract**, one value per called allele.
Open samples exist: NA09237 (male full mutation) is `GT=1`, `MC=898`, `AM=0.85`, reproduced with TRGT
5.1.0, and HG002 (normal male) is `AM=0.1`. `source_field: FORMAT/AM` already passes the pointer
grammar. `fmr1_cgg_repeat` asserts in prose that a full mutation "is methylated and silenced", and this
is the field that can check it.

**What a module cannot do today.**

- **Select the right allele.** HM06968 (female) is `MC=33,112`, `AM=0.90,0.07`: the expanded allele
  is the *unmethylated* one. NA06905 goes the other way. The band means "the methylation of the
  expanded allele", i.e. the `AM` at the index where `MC` is largest. Every element rule picks by the
  field's own values, so none can say it.
- **Name the quantity.** No `measure_kind` is a methylation fraction. `allele_fraction` would put two
  quantities under one name (P5). `repeat_alleles.csv` pins `measure_kind=repeat_count`.
- **Name the absence.** `AM=.` means either no CpG in the span or no MM/ML tags in the BAM, and the
  file cannot tell them apart.

**Scale trap.** TRGT 0.5.0 wrote `AM` as an Integer (values up to 185; probably the 0–255 byte,
unverified). From 0.7.0 it is a Float on `[0, 1]`, and the changelog is silent about the change.

**To design (the 0.8 interview).** The kind's name, audited under P5, and whether the modification
(5mC) is its own axis. Whether `repeat_alleles.csv` hosts a second kind or a sibling table does. How a
cross-field selection is stated without hard-coding TRGT's `MC` into a vocabulary: the probe prices an
optional pointer column naming the selecting field at full cost. And **the band values**: none is
cited yet. The probe quotes sample observations, not boundaries, and a row needs a paper behind it
(`@rm47-bin-cites`).

**Legality and price.** Everything is additive, so it is minor-legal (P3, P6, P8). A kind member is
cheap but a one-way door (P5). The selector column is full cost.

## RM318 — imprinting-region methylation is real in PacBio outputs, but lives in BED and TSV files that no pointer can name

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (a new optional region table kind, a non-VCF pointer) + compiler · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO §§ 1.2–1.4, 3, 4.2](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM66, RM65, RM164

**What is real.** HG002 shows allele-specific methylation at two imprinted regions in public PacBio
pipeline outputs, and MethBat 1.1.0 run on them reports `PASS`:
SNURF:TSS-DMR (15q11–13) hap1 80.1 / hap2 14.6, and KCNQ1OT1:TSS-DMR (11p15 IC2) hap1 15.3 / hap2 86.4,
with pooled values near 49. The consumer holds per-CpG `5mC.bed.gz` (MethBat 1.x) or
`cpg_pileup.*.bed.gz` (pb-CpG-tools 3.x), plus a `profile.tsv`. None of it is in a VCF, and no PacBio
tool writes VCF 4.5 `M5mC`.

**What a row would need.** Every item comes from the probe's measurements:

- a region (chrom, start, end, build), with no `variant_key`;
- a pointer to a BED or TSV column, which `source_field` (a VCF pointer) cannot be widened to without
  overloading it (P5);
- the aggregation from sites to region;
- a row selector (`Total`, or a statement about both haplotypes);
- the unit and the modification;
- a coverage floor, because a missing row is never "unmethylated";
- bands: pooled around 20% and 80%, plus a haplotype-delta band.

**Traps the data showed.**

- **Haplotype labels are not parental.** The same sample has hap1 methylated at SNURF and hap2 at
  KCNQ1OT1, so no band can say "the maternal allele".
- **The scale moved at MethBat 1.0.0** (fractions to percent) under unchanged column names.
- **pb-CpG-tools `model` and `count` modes disagree** (hap2 4.1% vs 16.1% at one CpG). The mode is a
  header line, not a column.
- **The pipeline runs `methbat profile` over CpG islands, never `methbat report`**, so a user holds
  island numbers, not the imprinted regions.
- **H19 had no haplotype rows at all.**

**Not decided, and not to be built on thin air.** The 20%/80% cut-offs are MethBat's defaults, not a
guideline. No clinical source was read. MethBat ships 15 imprinted regions from Mackay et al. 2022
(Table 2), which is the corpus a design would start from.

**Legality and price.** A new optional table kind is minor-legal (P3). Its price is full, and it is the
largest addition in the methylation work. The probe prices a separate pointer column over widening
`source_field`.

## RM319 — PacBio's TRGT carries the repeat count as `FORMAT/MC`, a per-motif String, so `repeat_alleles.csv`'s count half does not reach a PacBio user

**0.9, decided 2026-11-03.** The maintainer deferred methylation to 0.9 when scoping 0.8. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-30**, design first · **Owner** format (the consumer contract, possibly the element-rule vocabulary) + the corpus · **Motivating case** the maintainer, 2026-09-30: a beneficiary will soon hold PacBio samples, so methylation is wanted, "just don't build on thin air"; evidence in [METHYLATION_PACBIO § 4.1, last paragraph](probes/METHYLATION_PACBIO.md) · *related* RM317–RM319, RM66, RM65, RM164

**What was found.** No PacBio file opened in the probe carries `REPCN`, the ExpansionHunter key that
`fmr1_cgg_repeat` (and the corpus's other repeat examples) point at. TRGT writes the count as `MC`,
`Type=String`, per allele, with `_`-joined per-motif counts inside each allele (`18_8,25_8` at HTT
under TRGT 5.x). A PacBio consumer therefore cannot follow the module's `source_field` at all. An
author who writes `FORMAT/REPCN|FORMAT/MC` hands the consumer a motif-segmented string that no element
rule defines a reading of.

**Why it matters now.** A beneficiary of this work is about to hold PacBio samples, and TRGT is the
repeat caller in PacBio's pipeline. Every `repeat_alleles.csv` module is invisible to them today.

**To decide.**

- Whether this is a consumer-contract rule ("sum the motifs", or "the motif the row's `repeat_unit`
  names") or a vocabulary addition. The second is a minor.
- How it meets RM66, one repeat locus with several motifs: TRGT's per-motif segments are exactly RM66's
  shape.
- Whether the reference examples gain the TRGT alternation.

Measure against the PureTarget VCFs first. The probe lists them, with FMR1, HTT and more.

**Legality.** A contract sentence alone is a patch. A new element rule or pointer shape is a minor. It
is filed against 0.8 because the RM66 overlap wants one decision.

## RM261 — strip comments from the enricher wheel (measured, deferred)

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — deferred by the maintainer on 2026-09-25 as risky ("dangerous,
defer") · **Owner** enricher (packaging) · **Motivating case** the 0.7.2 enricher wheel is 893 KB
zipped, all of it Python source

**Measured on `just_dna_enricher-0.7.2`.** Of 2.58 MB of `.py`, docstrings are 31%, comments 19%, and
code plus whitespace 51%. Removing the comments alone takes the zipped `.py` from 847 KB to 664 KB
(−22%). Docstrings stay in any version of this item: they are the `help()` text and the API pages.

**Why it is not simply done.** `hatch_build.py` would have to leave the original `.py` out of the wheel
and force-include stripped copies. `artifacts` / `force_include` collide on the same path (see that
file's own note). The copies must keep line numbers, with a comment-only line becoming an empty line,
or a traceback from an installed wheel points at the wrong source line. Editable installs must not be
touched. It reaches the **enricher only**: format and compiler are on `uv_build`, which has no hooks,
and covering them means changing their build backend.

**Considered and refused in the same round:** taking the 15 `*_build.py` snapshot builders out of the
wheel (112 KB zipped). `scripts/rebuild-caches.sh` documents `pip install 'just-dna-enricher[dev]'`
then `cache rebuild` as a supported deployment, and `caches.py` imports every builder at module
level. The maintainer kept them in.

## RM248 — a declarative report schema: research, not a design

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** — (unsized, deliberately) · **Status** open — **a minor, taken into 0.8 on 2026-09-21** — a
research item, asked by the maintainer 2026-09-20. Nothing here is a proposal yet; the exit is a
measurement and a charter ruling, not a draft schema. The class is the most additive outcome this
could have, which is a new optional table or spec block; two of its three exits ship nothing at all · **Owner** unassigned — the placement question is half the research · **Pairs with**
[RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half),
[RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics),
and RM7 below (which is **not** the same item — see *What this is not*)

**For longevitymap v2 (2026-11-03):** v2's §5 is a report specification: a context card, grouping by mechanism, a research view. See [the group](ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**The ask, verbatim in intent:** some kind of report schema — Jinja templates or something — where the
*contents* are static and declarative and all the fancy CSS lives downstream.

### Why it is filed as research rather than as a design

Because the charter has something to say first, and it does not obviously say yes. The Non-goals are
explicit: *"No UI and no gene–disease inference. The format catalogs curated annotations that consumers
**join** against variant data; interpretation and presentation belong to those consumers."* A report
schema that describes a rendered page is that non-goal by another name.

The maintainer's own framing is also the resolution worth testing: **a report is a declaration of
CONTENTS, not of appearance.** *What a report says, in what order, keyed to which annotation rows* is
arguably still annotation; *how it looks* is unambiguously downstream. If that line holds, this is
legal and the non-goal is untouched. If it does not — if a contents schema cannot be written without
smuggling in ordering, emphasis or layout — then the honest answer is that this belongs to a consumer
and the entry closes. **That ruling is the first deliverable.**

**Principle 1 decides the other half before any syntax is chosen.** OakVar's reporter modules are
Turing-complete, and that is exactly the shape P1 rejects: code in the compile path, no
byte-reproducibility, a runtime every consumer must embed. Jinja is not obviously safer — it has
loops, filters and arbitrary attribute access, so "a template language" is a spectrum and the sanctioned
escapes are named: a **non-Turing-complete boolean predicate** and **declarative pattern grammars**. Any
candidate has to be placed on that spectrum explicitly rather than adopted because it is familiar.

### What this is not

**Not [RM7](ROADMAP.md#rm7--evaluation-output--report-card-schema).** That entry is a *per-sample* evaluation
output — a measurement, and therefore a consumer contract by the data-agnostic north star. This one is
about the structure of a report over **annotation content**, with no sample in it. The two are adjacent
enough to be confused and are listed together on purpose.

**Not a fourth library**, on today's evidence. The maintainer's read is that it looks like overkill, and
nothing here contradicts that yet: a declarative contents schema is a schema, which is
`just-dna-format`'s job, and a renderer is a consumer's. A fourth tier would only be justified if the
research finds a real body of shared rendering logic that is neither schema nor consumer — and finding
that out is part of the item.

### The competitor evidence, which is the reason this is worth research at all

This pairs with [RM188](ROADMAP_0_9.md#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)
because the surveys already ran and the reports are where every competitor's declarative layer visibly
ends:

- **ClawBio** — `pharmgx-reporter` is a 2,327-line Python file holding its variant tables inline
  (`PGX_SNPS`, `GENE_DEFS`, `GUIDELINES`: 32 variants, 13 genes, 59 drugs), and
  `clinical-variant-reporter` and `cnv-acmg-classifier` are `planned`. Their reports are good and their
  data is a module in a shape nothing validates. See [`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md).
- **genomi** — a runtime rather than a format, with a curated thirteen-record catalogue. See
  [`probes/GENOMI_SURVEY.md`](probes/GENOMI_SURVEY.md).
- **OakVar** — reporter modules, Turing-complete. The counter-example, and the one this repo's P1
  already has an answer to.
- **SelfDecode and the consumer-genomics vendors** — the reports are the product. Not surveyed here,
  and a survey of what their reports *contain* (as opposed to how they look) is cheap and is probably
  the highest-value first measurement this item can take.
- **`just-dna-lite`** already has a built-in reporting system. It is the reference consumer, so **what
  it does today is the baseline any schema has to beat** — and if it needs nothing from us, that is an
  answer rather than a gap.

### Why it pairs with [RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half)

RM28's surviving half is the **predicate** — a claim keyed on more than one subject, which no brick
holds. Its second corpus entry is exactly a *report* finding: ClawBio's pharmgx-reporter renders one
AVOID across 59 drugs, warfarin, and reaches it through `"special": "warfarin"` — a hardcoded branch
calling `get_warfarin_rec(profiles)`. **The report is where the missing predicate surfaces**: a section
that has to say *"CYP2C9 and VKORC1 together"* is RM28's gap wearing a consumer's clothes, and a report
schema that cannot express it would be shipping the same hardcoded branch one layer up. So the two
items constrain each other: **RM28's answer bounds what a report section can be keyed on**, and the
report is the place where an unexpressible pairing is most visible.

### There is already a presentation surface, and it is small and deliberately bounded

Worth knowing before anything is designed, because it sets the precedent this item either follows or
breaks. `module_spec.yaml` carries `report_title`; `normalize.py` splits **identity** keys from
**presentation** keys with a stated reason per key (`PRESENTATION_AUTHORITY_KEYS`, today just
`short_description`); and `RECOMMENDED_*` vocabularies exist for colours and icons. So the format
already admits *some* presentation, as named keys with per-key justifications and a storing authority.
The question this item should answer is whether a report schema is the same thing at a larger scale, or
a different kind of thing that happens to rhyme.

### What would close this

One of three, and the research is choosing which:

1. **Dissolved** — `just-dna-lite`'s existing reporting needs nothing from the format, and the
   contents/appearance line cannot be drawn cleanly. The entry closes with the reasoning recorded.
2. **Closed additively** — a bounded, declarative contents schema (a table kind, or a spec block) that
   passes P1 and the human-authorable ⇔ machine-precise gate, with a motivating report from a real
   consumer. Then it is an ordinary minor-legal addition.
3. **Parked with a sharper reason** — the shape is real but blocked on RM28's predicate, which is the
   most likely outcome if the warfarin case turns out to be representative rather than singular.

**The cheapest first measurement**, and the one to take before any syntax is discussed: read what
`just-dna-lite` actually renders today, and list every field it needs that a module does not carry.
That is a list, it is finite, and it decides between (1) and (2) without a design round.

## RM181 — a byte digest that moves beside intact signatures says something changed and not what, and provenance has no shift tracker

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **filed 2026-09-03 for the 0.8 review of what the hash family
covers, and a candidate for the 1.0 one if it turns out to want a manifest field per domain** ·
**Owner** format · **Motivating case** the maintainer's decision on S87 (RM180), in
CONSUMER_SUGGESTIONS_HISTORY.md

**The observation.** With RM180, an author rewording an overlay `reason` produces: `content_signature`
unchanged, every fact signature unchanged, `resolution_signature` unchanged, `artifact.digest` moved.
Read from outside, that says *something changed* and nothing more — the byte digest is a canary, not a
locator. Before RM180 the same edit moved `content_signature` too, which was wrong for the opposite
reason: a provenance edit read as a content one. Either way there is no hash whose movement means *the
provenance moved*, and the maintainer's words for the gap were that metadata has no dedicated shift
tracker.

**The shape named: digest by domain.** One identity per concern — content (have), facts per sidecar
(have), bytes (have), and a provenance or metadata one (do not have) — so a consumer holding two
manifests can say which domain moved by diffing the hash family rather than diffing parquets. That is a
separation of concerns, not a new axis on an existing hash, and it is why this is not a repair to
RM180.

**Why it waits.** Three questions before it is an item. What the provenance domain *contains* — the
overlay's three cells only, or also `sources.csv`'s `fetched_at`, `verification.json`'s `checked_at`,
the README bytes and `module_spec.yaml`'s display half, each of which is outside some hash today for
its own reason. Whether it is a manifest field (additive, minor-legal) or a member of the
`*_signature` family, whose roster rule in SCHEMAS is *one per derived sidecar* — and this is not a
sidecar. And whether `manifest.inputs` already answers it: the raw-bytes entry for `overrides.csv`
moves on a reason edit, so per file the answer exists, and what may be missing is the *reading* rather
than a hash. RM126's release record answers the neighbouring question — what a *release* changed about
compiled output — not this one, what an *edit* changed about a module.

**What would close it.** A consumer asking *what moved* and getting the wrong answer from the family
as it stands; or the 0.8 review deciding the family is complete and this becomes a FAQ entry.

## RM188 — the competitor survey — run Calwbio's and genomi's pipelines, read their reports, and re-fold the logic into module mechanics

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **round 1's two surveys filed 2026-09-13 and their findings
routed; round 2's roster is below, searched for rather than named** · **Owner** format (the survey),
then whichever tier the findings land in ·
**Motivating case** the maintainer's direction, not a consumer report

**For longevitymap v2 (2026-11-03):** its axes 2, 3 and 5 are now numbered, as RM328, RM330 and RM324. See [the group](ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**Progress.** Both named competitors are now probed, one document each, and neither turned out to be
a competing *format*: [`probes/GENOMI_SURVEY.md`](probes/GENOMI_SURVEY.md) (genomi is a runtime; its
thirteen-record curated catalogue is a `variants.csv` in Python, and §8 ranks seven annotation gaps,
all priced as derived sidecars) and
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) (ClawBio is 97 agent skills — 68 of them
`planned` — whose genotype-interpreting half carries four hand-curated variant tables inlined as
Python dicts and JSON). The two surveys overlap in almost nothing, which is itself the result: one
reaches for pathway, target–disease and regulatory content we do not carry, the other for the
per-variant clinical axes an ACMG engine reads.

**The ClawBio half's findings are filed, 2026-09-13** — a probe records and the tracker allocates, so
the numbers came from `.claude/rm-next.py` rather than the probe: **RM236** (`consequence`/`impact`,
and RM23's grain question with them), **RM237** (region-keyed ClinGen dosage), **RM238** (per-tissue
eQTL, open but parked on a consumer), **RM239** (fine-mapping posterior), **RM240** (land the
translated nutrition panel in the corpus) and **RM241** (`weighting` does not survive `reverse`). The
sixth finding was not filed as a new item because it is not one: warfarin's multi-gene call is
[RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half)'s surviving *pairing across subjects* clause, and
it went in there as that entry's **second corpus entry**. The genomi half's seven ranked candidates
are recorded in its own § 8 and are not filed here.

**What it is.** A survey of the consumer-genomics competitors, with two named first — **Calwbio** and
**genomi** — done the way PUBMIND_ASSESSMENT was done and not the way a feature comparison is: run
their pipelines end to end on real input, obtain the reports they produce, and read the logic *back*
out of the reports — which annotations they join, at what grain, which rules turn a genotype into a
sentence, and where a number comes from. Then re-fold what survives into the module mechanics here:
a table kind, a bounded rule, a vocabulary member, or a use case in USE_CASES.md that names the gap.

**What it is not.** Not a marketing comparison and not a licence to copy a rule: a competitor's
inference is evidence about what a report *needs*, and the charter's non-goals still hold — no
gene–disease inference in the format, annotation tables only. Where a competitor's logic is an
inference, the outcome here is the *table that would let a consumer make it*, never the inference.

**Method, so it can be repeated.** One document per competitor under `docs/probes/`, the shape of
PUBMIND_ASSESSMENT: what was run, on what input, what came back, what it competes with, what it
complements, and the adoption design if any. Real data, the tool turned on its own output
(`@adversarial-role`, `@probe-uniform-corpus`), and every claim about a competitor pinned to an
artifact obtained rather than a page read — the ClinPGx rounds showed a documented surface and the
real one disagreeing.

**Exit.** Each competitor's probe filed, and its findings either dissolved (already enabled), closed
additively (an RM with a motivating report in hand), or parked with the reason — the
USE_CASES → PROPOSAL loop, entered at the top.

**Round 2 — the candidate roster, built 2026-09-13.** Round 1's two competitors were named by the
maintainer; round 2's were **searched for**, and the search is the first half of the result. Method:
GitHub repository search over eight query shapes (personal genome interpretation, 23andMe raw data,
annotation modules, MCP + bioinformatics, nutrigenomics, pharmacogenomics, ACMG, PGS), sorted both by
stars and by recency, plus `awesome-genetics` (last pushed 2024-03) for the pre-agent generation.
Twenty-two repositories were then **skimmed** — not surveyed — against one question: *does it carry
hand-curated per-variant or per-gene rows a human wrote and committed, or does it fetch public
sources at query time?* That is the discriminator round 1 established: both genomi and ClawBio turned
out to be the second kind, and the curated fraction of each was tiny.

**Re-derive the search with:**

```bash
gh api -X GET search/repositories -f q='topic:personal-genomics' -f sort=updated -f per_page=15 \
  --jq '.items[] | "\(.full_name)\t\(.stargazers_count)\t\(.pushed_at[:7])\t\(.description)"'
```

varying `q` over the shapes above. **Nothing found in the 2026 crop has more than ten stars**, which
is itself a finding: the local-first personal-genomics field is a long tail of weekend projects, and
the established tools are older and narrower. Do not read the roster below as a competitive
landscape — it is a list of places to go looking for annotation *shapes*.

### The four that get a full survey

| # | Target | Pinned | Class | What its survey asks |
|---|---|---|---|---|
| 1 | [OakVar](https://github.com/rkimoakbioinformatics/oakvar) | `d4e8090df8`, 48★, licence NOASSERTION | a competing module format **with a store** | **A fresh peer read, not a migration post-mortem** — the maintainer's framing: *an OakVar module is in essence a plugin, arbitrary code, so it is a module plus half an annotator*. Its manifest (`<name>.yml`) declares `type` (annotator / postaggregator / reporter), `level`, `requires` (other modules), `input_columns`, and typed `output_columns` — a **column contract plus a dependency graph**, where ours is a row schema with neither. Ask what the column contract buys, what `requires` expresses that no module here can, and what is left of a module once the arbitrary code is removed. |
| 2 | SNPedia, via [snappy](https://github.com/zhaofengli/snappy) | `2d5255f`, 52★, BSD-2-Clause; SNPedia content CC BY-NC-SA 3.0 US | the corpus round 1 never had | The largest curated variant-trait corpus in existence: **106,603 SNP entries** frozen into `data/snps.json` from a MediaWiki XML dump, plus `genotypes.json` (per-genotype magnitude / good-bad / summary) and `genosets.json`. Survey **the corpus, not the SPA** — snappy is the extraction route that proves a static dump works, where `OSGenome` (146★) only crawls live. **Its terms are CC BY-NC-SA 3.0 US, established off three primary pages 2026-09-13, which makes it adoptable rather than not** — as an unsellable, share-alike, attributed module of its own. See [USE_CASES § 2e](USE_CASES.md#2e-republishing-a-licence-encumbered-third-party-corpus-as-modules-2026-09-13), now the maintainer's named use case for this format. |
| 3 | [BioMCP](https://github.com/genomoncology/biomcp) | `bb3a1d4ad7`, 630★, MIT | the agent-era tier done at scale | Thirteen times genomi's stars and the same architectural class. Ask the one question genomi could not answer at its size: **when an agent tool surface is the product, what does it end up needing to say about a variant that a table does not?** If the answer is "nothing", that closes the whole class and round 3 can skip it. |
| 4 | [Exomiser](https://github.com/exomiser/Exomiser) | `98f4e0b6f2`, 265★, AGPL-3.0 | phenotype-driven prioritization | The only established tool in the roster that **ships its annotation as a versioned data bundle** rather than fetching it — the closest existing thing to a compiled artifact. Ask what its bundle contains, how it is versioned, and how HPO term sets sit in it, given that [HPO ships no route here](ENRICHER.md) for licence reasons. |

### The three small ones worth a read after those

| Target | Pinned | Why |
|---|---|---|
| [dosedna](https://github.com/alejandro-publius/dosedna) | `530cfe7`, 2★, MIT | Hand-curated PGx over six genes, and the closest small analogue of our `haplotypes`/`diplotypes`/`pharm_variants` trio — plus a committed, provenance-stamped CPIC snapshot (`allele_definition` 39, `diplotype_phenotype` 666, `recommendations` 1,180). |
| [dna-engine](https://github.com/ShadowfetchLinux/dna-engine) | `5791bb3`, 0★, Apache-2.0 | **403 curated markers with the richest per-marker schema found anywhere**: `tier`, `effect`, `transferability`, `chips`, per-genotype label/impact/summary/detail/**actions**, and citations as `(pmid, note)` pairs. Also a deliberate non-interpretive posture — it refuses to translate genotype into phenotype, and says why. |
| [allelix](https://github.com/allelix/allelix) | `4b56bbe`, 30★, AGPL-3.0 | Carries no corpus, and is here anyway: **38 ADRs documenting source-precedence and suppression rules** (PharmGKB non-finding suppression, somatic-on-germline suppression, a GWAS odds-ratio magnitude modifier). Competing-source arbitration is `authority_precedence`'s problem, and this is the only project found that wrote its reasoning down. |
| [Custom-Personal-Genome-Interpretation](https://github.com/dianguan0105/Custom-Personal-Genome-Interpretation) | `15fe28a`, 0★, MIT | Two authored tables: 98 rsIDs carrying **GRCh37 and GRCh38 coordinates side by side on one row** plus population-split MAF, and **540 PRS weights transcribed out of a paper's supplementary table** — see [RM16](#rm16--authored-prs-weights-a-scoring-file-not-a-manifest). |

### What the skim already found — five axes, each sighted independently more than once

**This is the part that did not need a survey.** Convergence across unrelated projects is the
`@probe-uniform-corpus` heuristic firing: when three people who have never met each add the same
field, the field is answering a real question.

1. **Which genotyping arrays can call this variant** — three sightings: dosedna's `array_callable` + free-text `coverage_note` per gene, dna-engine's `chips` per marker, and `MrOrtiz/dna-annotator`'s measured-vs-imputed tiering per source array (it refuses to let an imputed call outvote a measured one). **We have nothing.** `requires_callable` / `callable_from` / `min_quality` ask whether the *consumer's own VCF* saw the position; this asks which *platforms in the world* interrogate it, which is a fact about the variant and therefore annotation. Note the per-gene / per-variant scope split, which is the shape [that already cost 39 variants once](ROADMAP_HISTORY.md).

   **A fourth sighting, and the first with a source and a measurement: S111 (just-module-creator,
   2026-09-24).** `just-prs` already holds the Illumina GSA v3 backbone that 23andMe v5, AncestryDNA v2,
   MyHeritage and FTDNA v2 share, as typed positions on both builds (648,379), plus a 1000G LD-proxy
   table. Measured over 16 real modules' `resolution.csv`: 336 of 965 positions typed (35%). The GWAS
   modules came out near 22% and the PGx panels at 51%, and lifting to GRCh37 lost one position. The
   report asks for a *module-level* expected match rate. Recorded here rather than as an `RMn` because
   it is this axis with a candidate source, and three things a design would have to settle came up in
   the reply ([CONSUMER_SUGGESTIONS_HISTORY § S111](CONSUMER_SUGGESTIONS_HISTORY.md)):
   **(a)** the fact is per variant (*which platforms interrogate this position*), and the module figure
   is a manifest summary derived from it, the way the `literature` block summarizes
   `literature.csv`. The per-variant form is also what the reporter's other use, picking the typed one
   of two lead SNPs in LD, actually needs. **(b)** Counts, never a rate, with *typed*, *LD-proxyable*
   and *not position-matchable* kept apart. The proxy count describes a substitution the consumer's
   engine may or may not make, so it stays beside *typed* and is never added to it. *Position-only* goes
   in the field's name or description, since a position match says nothing about allele or strand.
   **(c)** The source is a snapshot lane, never an import of `just-prs`: the per-chip position sets
   published on the HF org with a `release.json`, walked through [CACHE_SURFACE.md](CACHE_SURFACE.md)'s
   checklist, and the GSA manifest's licence probed before it is republished
   (`@probe-the-real-file`, `@no-named-licence`).
2. **A per-variant claim's ancestry transferability** — three sightings: dna-engine's `transferability`, `Bluefinee/kaiseki`'s Japanese-cohort reconciliation, `drhudsonandrade/OmniGenis` recording discovery-cohort ancestry per GWAS association. We carry `PgsRow.training_ancestry` and `GwasEffectRow.ancestry`, both scoped to their own table; there is no way to say *this variants.csv row was established in one population*. **Numbered 2026-11-03 as [RM328](ROADMAP_0_8.md#rm328--no-study-row-can-name-the-ancestry-it-was-measured-in-so-european-only-evidence-is-a-hand-set-flag), for longevitymap v2.**
3. **Effect modified by a non-genetic factor** — two sightings, and genomi is the third: `sinhaankur/open-genome-atlas` splits each marker's evidence by `kind` (diet / lifestyle / geo), **each axis independently cited**; `drdaviddelorenzo/nutrigenomics` scopes its `weight` to a `nutrient_domain`; genomi's own caveat *"folate fortification status of the population modifies effect size"* is the same fact in prose. `CopyNumberRow`'s `modifier_gene` / `modifier_cn` is the precedent shape for a *genetic* modifier and there is no environmental one. Note that the second sighting also lands on `@weight-has-no-unit`: their `weight` at least names the domain it is a weight *in*. **Numbered 2026-11-03 as [RM330](ROADMAP_0_8.md#rm330--an-effect-measured-in-one-sex-one-smoking-stratum-or-one-genotype-has-no-row), for longevitymap v2.**
4. **Two sources disagreeing, as a recorded verdict** — three sightings: kaiseki's `DISCORDANCE_RATIO`, which **refuses to publish a consensus frequency** when cohorts disagree; `Gunshipz/genomine`'s cross-tool confidence/disagreement layer; allelix's ADRs. `clin_sig_concordance.csv` does exactly this for clinical significance and **only** for clinical significance — kaiseki does it for allele frequency, where `frequencies.csv` has per-population rows and no verdict.
5. **A hand-assigned salience separate from clinical severity** — two sightings: `alexlaverty/dna-health-report`'s `magnitude` 0–6 per genotype, and SNPedia's own `m` field carried through snappy. `VariantRow.priority` is the candidate analogue; whether "priority level override" means the same thing is a question for the survey, not an assumption. **Numbered 2026-11-03 as [RM324](ROADMAP_0_8.md#rm324--there-is-no-evidence-tier-column-so-the-axis-that-gates-visibility-is-a-flags-tiera-token), for longevitymap v2.**

**A sixth shape was seen and is already decided against, recorded so it is not re-raised.**
`dianguan0105/Custom-Personal-Genome-Interpretation` stores GRCh37 and GRCh38 coordinates *on the same
row*, so no liftover is needed at read time. That is the opposite of the rule here — `genome_build`
lives in the manifest and in no parquet column (`@build-in-manifest-only`), the build is injected at
load and never authored on a row (`@build-injected`), and a module is single-build by design with
`reference_examples/grch37_build` as the worked case. Their design buys convenience and pays for it
with two coordinates that can disagree and nothing able to notice. **Not a gap.** Worth one paragraph
in whichever survey reads them, and no more.

**And one that is not an axis but a corpus: [RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half) has a third entry.** snappy's
`genosets.json` carries SNPedia's boolean-combinator DSL — `and(rs4988235(C;C), rs182549(C;C))`, with
genoset-of-genoset nesting for haplogroup trees. That is a third independent grammar for the same
thing after CIViC's molecular profiles (RM174) and ClawBio's guideline logic, and unlike those two it
is a **general-purpose** one written for consumer genetics rather than falling out of one domain.
Counting its operators and its nesting depth is worth doing whether or not the rest of snappy is read.

### Checked and skipped — recorded so round 3 does not re-search them

**Same class as genomi (fetch public sources at query time, no curated content):** `lagodinm/dna-health-report`,
`MrOrtiz/dna-annotator`, `Gunshipz/genomine`, `itsrudaynah/Modrik`, `techninja/asili`,
`drhudsonandrade/OmniGenis` (58k LOC and its own scripts say *"Nothing here is authored"*),
`mentatpsi/OSGenome` (146★, crawls SNPedia live and freezes nothing).
**Pipeline or converter, no interpretation:** `GeiserX/Personal-Genome-Pipeline` (10★),
`captainzonks/GeneGnome`.
**Curated but too thin or too stale to teach anything:** `Michael-Sebero/Genetic-Trait-Detector`
(245 rows, one 432-line file, last pushed 2025-03), `dev-kvt/GenomeUpload` (27 uncited rows inline in
JS, with an LLM writing the actual report).
**Curated only as a panel — a list of rsIDs with no fields on them:** `brandonsaldan/codex` (37★, 225
JSON files of bare rsID membership, all interpretation scraped live from SNPedia, dead since 2023).
**Documentation, not a tool:** `matbanik/agentic-genomics` (a setup guide wiring up three MCP servers
that live elsewhere).
**Not competitors, one line each:** the single-source MCP servers (`berntpopp/clinvar-link`,
`cyanheads/gnomad-genetics-mcp-server`, and our own `dna-seq/ensembl-mcp`) wrap one API and carry no
annotation; the general AI-science workbenches (ScienceClaw, aipoch/open-science, wisp-science, all
600–4,000★) are not genome tools; `WGLab/InterVar` (213★) is ACMG classification, which ClawBio's
half already covered, and its last commit is 2021.
**Commercial, no source:** Promethease (now MyHeritage), Genomelink, SelfDecode, Codegen, Nebula.
**RM188's method does not reach them** — a report can be bought and read, but no pipeline can be run
and nothing can be pinned, so a survey of one would be a marketing comparison, which § *What it is
not* forbids. Promethease is reachable **through SNPedia** instead, which is why row 2 is the corpus
and not the product.

### The agent-skill class is closed, and it cost one read

[`BioTender-max/awesome-bio-agent-skills`](https://github.com/BioTender-max/awesome-bio-agent-skills)
(178★) is a directory of AI agent skills for biomedical work. Enumerating the entries that interpret a
**human personal genome** — as opposed to answering "what does the literature say about gene X" — gives
**21**, and they cluster under four collections: `clawbio/` (six: `pharmgx-reporter`,
`nutrigx-advisor`, `gwas-prs`, `genome-compare`, `claw-ancestry-pca`, `clinical-variant-reporter`),
`openclaw/`, `omicsclaw/` and `bioskills/`. The rest are ACMG classification, PRS, and PGx under
different names.

**Round 1 already surveyed the representative of this class.** ClawBio's six skills are *in* this
directory, and [`CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) read them end to end. Nothing in the
remaining fifteen is a different shape — they are the same fetch-and-render procedure over the same
public sources, and the directory itself is the evidence for that rather than an argument. **So the
agent-skill class is closed for round 2**, at the cost of one directory read rather than fifteen
surveys, and round 3 should not reopen it without a reason that is not "there are more of them now".

Two names in it are domains nothing here touches and neither survey raised: `chip-clonal-hematopoiesis-agent`
(somatic clonal haematopoiesis) and `prs-net-deep-learning-agent`. Neither is an annotation table, and
both are recorded only so the next reader knows they were seen.

**Security note, since the search surfaced it.** `Barrelsravennagrass984/Personal-Genome-Pipeline` is a
near-verbatim clone of `GeiserX/Personal-Genome-Pipeline` whose README is replaced with download bait
for a `.zip` committed inside the module tree. **Do not fetch or run it.** Recorded here because the
next person to run this search will find it in the same result set.

## RM237 — ClinGen dosage is gene-keyed, so a recurrent-CNV region has nowhere to be written

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s ClawBio half** ·
**Owner** enricher (the lane) + format (the model) · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *dosage keyed on a region, not a gene*

`GeneMetricsRow` carries `haploinsufficiency` and `triplosensitivity`, keyed on a **gene symbol**, and
`enricher/clingen.py` fills them. ClinGen publishes four dosage lists — gene curation, **region
curation**, recurrent CNVs and ISCA regions — and `enricher/acmg.py`'s own probe note from 2026-08-03
records seeing all four on the FTP tree while reaching for one. The three unread ones are the half a
CNV classifier actually needs: ClawBio's `skills/cnv-acmg-classifier/data/curated_dosage_map.csv`
carries an `element_type` column precisely because two of its four demo rows are regions
(`22q11.2`, `chr22:18,900,000–21,500,000`, hi=3 ts=3), and its ClinGen/ACMG 2019 Section 1 scores off
them.

**A region is genuinely the subject, which is why this is not a widening of the existing table.** A
22q11.2 deletion is not a claim about any one gene in the interval; filing it under a gene symbol
would be a false attribution of the kind `@gene-map-is-another-sources-attribution` forbids. So the
shape is a **sibling sidecar** — `region_metrics.csv`, one row per `(chrom, start, end, name)` with
`haploinsufficiency`, `triplosensitivity` and ClinGen's curation id — rather than an `element_type`
discriminator on `gene_metrics.csv`. "One CSV = one concern" and `@sidecar-name-and-place` both push
apart here: a region row carries coordinates and a gene row carries a symbol, and a table holding both
would have half its key null on every row.

**Two things to settle before writing the pass**, and the second is the one a review will catch:

- **Terms.** ClinGen's dosage lists are believed unrestricted and that is *recalled, not probed*
  (`@no-named-licence`). Read the file and its SPDX id first.
- **Which `(source, layer)` row this claims.** `@write-the-sourcerow`'s second-surface clause says a
  second surface of an already-declared source may not claim the lane's existing row. Whether region
  curation is a second surface of `clingen` or the same lane is undecided, and it decides the
  `SourceRow` key.

**Related** RM188, `@write-the-sourcerow`, `@gene-map-is-another-sources-attribution`.

## RM240 — the ClawBio nutrition panel compiles, and the corpus should carry it

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half; the translation is run, the landing is not** · **Owner** format (the corpus) ·
**Motivating case** [`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *The translation, run*

The survey's headline claim — a competitor's inlined panel is a module written in the wrong language —
was run rather than asserted. `skills/nutrigx/data/snp_panel.json` at `1fcecb7e` (28 SNPs) translated
field-for-field into a spec, `validate` green, `compile` producing 84 weight rows over 28 variants, 24
genes and 12 categories, and `compile → reverse → compile` reproducing `content_signature` exactly.
**Land it as `reference_examples/nutrigenomics_panel/`**, which is `@probe-becomes-example` and is the
only form in which the claim stays true as the code moves.

**What it broke on the way, and the README has to say all of it:**

- **`state` is required and `direction` is not.** 84 rows refused for omitting the *superseded*
  column while carrying the modern one. Already in the [1.0-cleanup tracker](ROADMAP.md#variantrowstate)
  with the right reason (P8 forbids demoting a required field inside a major, so the demotion and the
  deprecation land together at 1.0). What the run adds is that this is the **first** error a
  first-time author meets, before anything about their data.
- **Their 28 `ref_allele` cells carry no coordinate**, and the schema refuses a bare `ref` — correctly,
  since an unanchored reference allele cannot be checked against a reference genome. The honest
  translation drops `ref` and keeps `effect_allele`.

**What the landing still needs**, none of it optional because the corpus walkers assert it: a
`resolution.csv` so `validate --strict` and `compile --strict` pass
(`test_reference_example_compiles_under_strict`), a `sources.csv` whose terms are read rather than
recalled — their `data_license` is blank and the repo is MIT, which is a licence for the *code*
(`@a-hosts-terms-are-not-its-contents-terms`) — a `verification.json` closure
(`test_every_reference_example_is_closed_and_its_closure_still_describes_it`), a README, and a section
in [REFERENCE_EXAMPLES.md](REFERENCE_EXAMPLES.md). Two enricher passes are worth running first because
they are what makes it the worked answer rather than a copy: `check-identifiers` (their panel names
`BCMO1`, a retired HGNC symbol) and `literature` over the 28 PMIDs.

**One observation for the README, not a repair.** Their panel weights `rs429358` and `rs7412` as two
independent additive rows in two different nutrient domains. Those two variants are the APOE ε pair,
which `reference_examples/apoe_epsilon/` models as a haplotype because the isoform is the joint state.
That is a claim about their curation, and it belongs in the README as a sentence.

**Related** RM188, RM92 (see RM241 — the `weighting` block this example is forced to write).

## RM164 — `heteroplasmy.csv` is a shipped table kind with no source behind it

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **PARKED to 0.8, decided 2026-09-01**, moved into this file
**2026-09-11** · **Owner** enricher · **Motivating case** the 2026-09-01 source-adoption round

**Decided 2026-09-01 with the maintainer: parks, on the measured negative below.** The candidate field
anyone has named is MITOMAP and the population callsets it re-hosts, and none of them publishes the
axis the kind binds; that is a fact about what exists, not about how hard anyone looked, which is what
makes the deferral honest rather than indefinite. It stays **open and visible** rather than closed,
because a kind with a one-module corpus is exactly what `@probe-uniform-corpus` says to keep in view —
and if a source that bands heteroplasmy by tissue appears, this entry is where it is checked against.
**Reopen it with a source, never with an argument.** The spin-off it noticed is now
[RM171](ROADMAP_HISTORY.md#rm171--mitomaps-curated-mtdna-tables-adopted-as-the-increment-they-carry-over-clinvar).

**Probed and drafted in [PROPOSAL_0_7_PT2](proposals/PROPOSAL_0_7_PT2.md#rm164--heteroplasmycsv-is-a-shipped-table-kind-with-no-source-behind-it) on 2026-09-01 — proposed PARKS to 0.8; the maintainer pass took it as proposed.** **Answered by reading the source, after the maintainer supplied the 2026-08-24 `pg_dump` (61 MB, 95 tables).** MITOMAP is **reachable** — plain `curl` gets the dump at `mitomap.org/downloads/`, HTTP 206 with ranges; the Cloudflare challenge is on the *web* surface only, and two earlier readings of this entry (a "refusal", then "unreachable by the machinery") were both a 403 from a path that was not the data path. **The axis answer is a measured no.** The schema has **exactly one `tissue` column**, on `mitomap.unpublished` — per-patient submissions beside `sample_id` and `ethnicity`, i.e. sample data this format does not carry. `mitomap.mmutation` is **602 rows** whose `homo`/`hetero` are *presence flags* (`+` 286/270, `-` 216/238, `nr` 90/89, plus `.`/`na`/NULL), with no threshold, no band and no tissue — the only levels in the table are two rows where a percentage was typed into a flag column. The only heteroplasmy numbers anywhere are re-hosted blood-cohort data (`mitomap.gnomad` 18,164 rows, `mitomap.helix` 14,104), where `max_observed_heteroplasmy` is a cohort observation, not a clinical threshold. So `HeteroplasmyRow`'s binding columns have **no source-side value in MITOMAP**. Terms are **unread**, not unestablishable — the dump carries no licence text in 6.7 M lines and the page a browser reaches was not opened. Parks, not closed. **Separately noticed and not part of this entry**: `mmutation` is a plausible mtDNA `variants.csv` source, blocked on `status` being 29 free-text strings rather than a vocabulary — its own item when taken.

**The measurement, taken over `_TABLE_KINDS` and the enricher's providers.** Every table kind is in
`DRAFTABLE` by construction, so *structurally* all nine are draftable. A **provider** exists for four:
`haplotypes`/`allele_function`/`diplotypes` (`pgx_draft` ← CPIC), `pharm_variants` (`clinpgx_draft` ←
ClinPGx), and `variants` (`clinvar_draft`, `civic_draft`, `pubmind_draft`). `heteroplasmy.csv`,
`repeat_alleles.csv`, `copynumbers.csv`, `pgs.csv` and `activity_phenotype.csv` have **none**, and no
enrichment pass reads them for a cross-check either. `enrich()` does resolve heteroplasmy rows — it is
the third table that can ask, and the one that keys *with* `alts` — but resolution is not a source.

The corpus behind the kind is one module: `reference_examples/mt_heteroplasmy`, two MT-TL1 variants of
one gene, hand-authored from the literature. That is the `@probe-uniform-corpus` shape exactly — the
schema generalized from a single case, and nothing since has taken a second one.

MITOMAP is the canonical mtDNA variant table and the obvious candidate. **Two things must be
established before that is a plan, and neither is:**

1. **The terms.** MITOMAP is not CC0, and this entry states nothing further about its licence.
   Whether it is expressible as a `SourceTerms` at all, and whether it lands as a **draft** source or
   only as a **check**, is decided by reading its published terms. RM153 is the standing reminder that
   a source's terms page can answer HTTP 200 with something that is not terms, and that the honest
   record of an unestablished axis is `None` (`@no-named-licence`).
2. **Whether it carries the axis at all.** `HeteroplasmyRow` binds a *level band* per
   `(gene, reference_sequence, tissue, variant_key)`. A per-variant pathogenicity table with no tissue
   and no threshold fills the identity columns and none of the binding ones — it would draft rows that
   say nothing the kind exists to say. Probe the real file and name the table probed
   (`@probe-the-real-file`, `@probe-names-the-table`); a negative here is as useful as a positive and
   closes the item cleanly rather than leaving it open forever.

**Related** RM165 (the same shape on the other uncovered binning kind), RM171 (the spin-off),
`@probe-uniform-corpus`.

## RM122 — the measure lookup is specified and nothing anywhere implements it

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** **parked on demand, moved here 2026-08-21** — additive and
minor-legal whenever it is wanted; what it waits on is a caller, not a decision · **Owner** format ·
**Motivating case** S58 (just-module-creator, in CONSUMER_SUGGESTIONS_HISTORY.md)

**The specification half shipped; this is the part that was not asked for and might still be right.**
S58 reported that the four binning kinds annotate nothing downstream and asked for either a normative
paragraph or an admission that the family is specified ahead of its consumers. Both are now in
[SCHEMAS.md § The measure lookup a conforming consumer implements](SCHEMAS.md#the-measure-lookup-a-conforming-consumer-implements--the-second-normative-obligation-06-s58),
and that closes the item they filed. What is filed here is the next question, which they did not ask:
whether the rule should also exist as a **public function** so that the first two consumers to
implement it cannot disagree.

**The argument for.** It is the shape S51/RM115 settled one layer down — a rule kept as prose is a rule
every reader re-derives, and the two derivations differ on exactly the cases that matter. Here those
cases are enumerable and sharp: the continuous shared endpoint, the float32 comparison, `unresolved`
versus no-match, and pleiotropy returning several rows rather than one. A consumer will get at least
one of the four wrong, and the failure is silent — a wrong bin renders as a confident phenotype.
`alleles.split_genotype` is the precedent: the *reader* half of RM81 shipped as one public leaf every
tier calls, while the retype waits for a major. It costs the format tier nothing — pure arithmetic over
loaded rows, pydantic-only, no dependency moves.

**The argument against, and it is why this is open rather than done.** There is no consumer to check the
shape against, which is the same reason `measure_step` is not a column: a signature fixed against a
hypothesis fixes the wrong thing, and this one has real shape questions. Does it take rows or a table?
Does it return one row, or one per `trait_efo_id` (the honest answer, and the inconvenient one)? Does it
answer `None` for no-match, or a three-state result distinguishing *no match* from *unresolved selected*
— which is what the house algebra would demand and what a `None` return would collapse. Getting that
wrong ships a leaf whose first real user has to work around it, and P3 keeps it working forever.

**What would settle it:** one consumer implementing the lookup against the paragraph. Their questions
are the signature. Until then the paragraph is the contract and this stays filed — the same
wait-for-the-demand rule that governs `measure_step`, applied to a function instead of a column.

**Decided 2026-08-21: wait for demand, and the wait is the answer rather than a way of postponing
one.** The four shape questions are the reason — does the lookup take rows or a table, does it return
one row or one per `trait_efo_id` (the honest answer, and the inconvenient one), does it answer `None`
for no-match or a three-state result distinguishing *no match* from *unresolved selected*. There is
nobody to check any of those against, and P3 keeps a wrong leaf working forever. This is the same
wait-for-the-demand rule that keeps `measure_step` out of the schema, applied to a function.

**It moved out of the active roadmap because "undecided release" was the wrong bucket for it.** Nothing
about this is undecided; it is parked, which is what this file is for, and it sat under a heading that
made it read like an unmade call. **The settling event is specific**: one consumer implementing the
lookup against the paragraph in [SCHEMAS.md](SCHEMAS.md#the-measure-lookup-a-conforming-consumer-implements--the-second-normative-obligation-06-s58).
Their questions are the signature — file it back in the active roadmap when they arrive, not before.


## RM23 — Computational predictor scores as a table

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** deferred — **considered for 0.6 on 2026-08-13 and held**, on the two
blockers unchanged · **Owner** format (schema + compiler) + enricher · **Motivating case** pathogenicity
triage; splice-impact panels

`predictions.csv` — the groundwork every predictor source needs, built **once**: one row per
`(variant, predictor, score_kind)` with `score`, `dataset`, `source`, and an optional `transcript`.
**Long-form, not wide, is the load-bearing choice** — SpliceAI is four deltas plus positions, CADD is
one number, AlphaMissense is one plus a class, so wide columns would make every new predictor a schema
bump while long form makes it *data*. A predictor score is the same class of object as an allele
frequency or a LOEUF (a per-variant number from a named dataset, no measurement), so the 0.5 sidecar
precedent covers it.

**Why it is still deferred, after the 0.6 review.** Neither blocker is code, and neither has moved:

- **Grain.** SpliceAI scores are per-transcript, and there is no settled way to name the four splice
  deltas without inventing a predictor-specific column set — which is the exact thing long form exists
  to avoid. Whether a per-transcript score is one row each or a picked representative is undecided.
- **Acquisition.** Precomputed splice scores need the *masked vs raw* file sizes measured and the Broad
  lookup API's terms read. This is the same measure-first question that correctly parked the frequency
  snapshot, and skipping it is how a shape gets fixed against a guess.

Unlike the two derived tables 0.6 does build (RM24, RM25), this one is a **full-cost authored table**
under the 2026-08-13 charter amendment, so the bar is higher rather than lower.

**Licensing is solved, not blocking — do not re-raise it as the reason.** SpliceAI/Pangolin, dbNSFP,
AlphaMissense, REVEL, CADD and PrimateAI are all non-commercial or academic-only, and `licensing.csv`
plus the compile gate already confine that to the modules that use them, while phyloP/phastCons/GERP
(UCSC, free, queryable per-range rather than a bulk download) keep a module sellable.

**What would unpark it:** the acquisition measurement done, and a decision on per-transcript grain.
That is a research task, not a schema task, and it commits nothing.

---

## RM16 — Authored PRS weights (a scoring file, not a manifest)

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium-large (on demand) · **Status** deferred — **considered for 0.6 on 2026-08-13 and
held; parked on *shape* rather than on demand since 2026-09-13, and its unpark condition needs
restating** · **Owner** format (schema + compiler) · **Motivating case** authored-weight PRS modules

0.4 shipped `pgs.csv` as a *manifest of PGS Catalog IDs* with the ancestry-validity fields — not
authored per-variant weights. `just-prs` resolves a `PGSxxxxxx` id to a harmonized scoring file and
scores each id itself, so inlined weights would be **dead data**; and a PRS is a
Z/percentile-in-reference, a shape the format does not bin.

What is deferred is a distinct, digest-bearing `effect_allele` + `effect_weight` scoring table, for the
case where a module must ship weights the PGS Catalog does not host (a score published only in a
paper's supplementary table).

**Why it is still deferred.** It is **not derivable** — nobody can fetch weights that exist only in an
appendix — so it is a **full-cost authored table**. And the one thing that would validate its shape, a
real consumer combining authored weights into a score, does not exist. A score's shape (how weights
combine, what the reference distribution is, whether a percentile travels with it) is exactly what a
first real case would dictate, so fixing it now spends a one-way door on a guess.

**What would unpark it:** a real consumer. See [PROPOSAL_0_5.md](proposals/PROPOSAL_0_5.md) D1.

**This entry and [RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half) are one axis at two operators
(maintainer, 2026-09-13), and they should be decided together rather than merged.** Both ask the same
question — *how does a conclusion get derived from more than one variant row, and where does the
combining rule live?* — and the format already answers it once:

| Combiner | Where the rule lives | Status |
|---|---|---|
| **Enumerative** — write out each combination | in the table: a `diplotypes.csv` row *is* the combination | **shipped**, `reference_examples/apoe_epsilon` |
| **Boolean** — a predicate over genotypes | nowhere: the table would hold terms, something else the operator | **RM28**, parked on a corpus |
| **Weighted sum** — terms plus coefficients | nowhere: the table would hold weights, the consumer the arithmetic | **this entry**, parked on shape |

Three facts follow from the table and none of them from either entry alone. **The enumerative answer
is why both are parked and neither is urgent** — it covers the small-arity cases, which is most of
them, so any argument for a new combiner has to beat it rather than merely want one. **Both
non-shipped rows split the same way against the data-agnostic goal**: the module carries terms, the
consumer does the combining, so neither is a licence to put an evaluator in the compiler. And **one
corpus supplies evidence for both** — SNPedia has genosets *and* per-genotype magnitudes, which is why
one survey touched both entries on one day.

**They stay separate items.** The outputs differ in kind — RM28's is a categorical conclusion, this
one's is a number that means nothing without a reference distribution — and RM28 was already halved
once on 2026-08-13 for being too broad, so merging would make the smaller hostage to the larger. What
they share is a **precondition**, not a design: whoever opens either should read both, and the *where
does the combining rule live* decision should be taken once rather than twice.

**The hypothesised case now has an instance in the wild (2026-09-13), and it does not unpark this.**
From [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
round-2 skim: [`dianguan0105/Custom-Personal-Genome-Interpretation`](https://github.com/dianguan0105/Custom-Personal-Genome-Interpretation)
(`15fe28a`) ships `metaprs_weights.tsv` — **540 variants transcribed by hand out of a European Heart
Journal 2022 supplementary Table S3**, with `rsid`, `effect_allele`, `other_allele`, `weight`, `maf`
and `traits`. That is this entry's motivating sentence — *"a score published only in a paper's
supplementary table"* — with a real file behind it instead of a hypothesis, and the column set they
arrived at independently is close to the one deferred here.

**The first reading of that was wrong, and the maintainer corrected it the same day.** It was written
here as *the wrong half of the evidence* — the unpark condition is a real consumer, a competitor
transcribing a table is a producer, so nothing moves. **That dichotomy does not hold, and the entry's
own gate is what has to give.**

**An author with a corpus in hand is demand, and for a format it is the demand that matters.** People
reach for familiar shapes: somebody who already has a scoring table, or a set of genosets, adopts a
format when the format can hold what they already have, and declines it when it cannot. That makes
*"can I bring this in"* a consumer question in the sense that decides whether a format gets used at
all — a narrower reading, where a consumer is a downstream tool that reads authored weights and
scores them, gates this entry on the one party who cannot appear until after the table exists.
**Written as it stands, the unpark condition cannot be met by anything except a tool built against a
table this entry is refusing to build.** That is a gate on its own output, and it should be restated
when this entry is next opened for a decision — not silently, and not here, since restating a parking
condition is a change to the item rather than a note on it.

**What survives the correction, and it is the half that was always load-bearing.** The demand
question is answered — somebody did the typing, and SNPedia's magnitude-and-genoset corpus is the same
argument at a hundred thousand rows. The **shape** question is not: how the weights combine, what
reference distribution the score is stated against, and whether a percentile travels with it are still
unanswered, and a transcribed table shows the columns without showing the semantics. The one-way door
is the shape, never the demand, so what this instance does is **move the entry from parked-on-demand to
parked-on-shape** — a smaller and much more answerable place to be parked.

---

# The VCF 4.4 items deferred out of 0.6

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.


**Register cross-reference (2026-09-27).** [RM302](#rm302--one-conclusion-serves-every-place-a-report-shows-it-a-table-cell-a-details-card-and-an-explanatory-mode-want-different-wordings)
gives `conclusion` optional lay and concise wordings, two columns by default. If this item lands a
separate meta-conclusion table, the maintainer's steer is that the registers may live there instead,
so the two are decided together.
## RM56 (policy half) — the rule for a measurement that spans bins

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** high on the flagship example · **Status** 0.6 ships withhold plus an explicitly
not-implemented warning; **the policy lands here, gated on real caller output** · **Owner** format
(schema) + compiler

A real repeat call is `RUC=38, CIRUC=-5,5` — `[33,43]`, crossing all three Huntington thresholds, so
`htt_repeat_expansion` says *benign*, *uncertain* and *fully penetrant* at once. 0.6 makes withholding
the stated behaviour and says loudly that no policy exists yet.

**The policy is a closed vocabulary** — withhold / take the worst bin / take the point estimate — stated
by the curator and applied by the consumer. That is annotation rather than measurement, so it stays
legal. **Its grain is deliberately undefined**: per table matches how the decision is actually made (a
stance on a whole disorder), per row is more expressive and nobody has demonstrated the need.

**The prerequisite is a real caller VCF**, so the vocabulary is fixed against what callers emit rather
than against a guess. Same gate as RM65; RM66's evidence arrived separately (see its entry).

**Never** widen the measurement into an interval on the row (`measure_min_observed` and friends): that
puts a *measurement* in the module, which the data-agnostic north star forbids outright.

## RM65 (implementation half) — repeat and copy-number tables are positional

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** 0.6 corrects the false claim in the code; **the coordinates wait here**
· **Owner** format (schema) + compiler

§5.6 says POS and SVLEN specify the interval a copy number is defined over; §5.7 says a `<CNV:TR>`
record's POS and END *"should match the STR/VNTR reference catalog sizes for catalog-based callers"*. So
a tandem repeat and a copy-number segment are **loci with coordinates**, emitted at fixed published
positions, and the compiler's claim that these tables are unjoinable *"which is a property of what they
describe rather than a gap"* is false for both. 0.6 fixes the comment.

**Adding the coordinates waits on a real repeat-caller or CNV VCF sample, or a consumer field report.**
Without one it is scaffolding in thin air — and it is not free: it would put two more tables into RM43's
coordinate-filling path, taking that lane from three tables to five.

**And it carries an RM87 obligation, noticed while that lane was being built.** The reverse writer's
positional-table pass hard-codes `locus_index = 0` (`_write_resolution_csv`, the second loop), which is
honest only while those tables never expand — true today, since RM43's fill is one locus per row.
Putting coordinates on the repeat and copy-number tables is exactly what could make one of them expand,
and the `0` would then be a wrong number rather than a trivially correct one. Not a blocker for RM65;
a line whoever implements it must clear.

## RM66 — one repeat locus, several motifs

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** deferred here; filed beside RM65, but **its evidence has since arrived on its own** (below) · **Owner** format (schema)

§5.7: a `<CNV:TR>` allele *"can encode multiple different repeat motifs in a single allele"* (`RN=3`,
`RUS=CAG,TG,CAGG`). `RepeatAlleleRow` is keyed `(gene, repeat_unit)` and binds one count to one motif.
For HTT the interruption structure `(CAG)n(CAA)(CAG)` is exactly what a modern caller reports as several
`RUS` entries, and the pure-CAG tract length differs from the total — a difference with published effect
on age of onset. The key cannot say which count the thresholds are about, and two motifs for one gene
read as two unrelated groups rather than components of one allele.

A keying change on a shipped table, which is the expensive kind. Filed beside RM65 so both would
arrive with the same evidence — **and they no longer will (2026-09-01,
[RM165](ROADMAP_HISTORY.md#rm165--repeat_allelescsv-has-no-source-and-rm65rm66-have-been-waiting-on-exactly-the-corpus-one-would-bring)).**
STRchive publishes `locus_structure` on 23 of 82 loci as typed data with its own three-member
vocabulary, HTT's being exactly the `(CAG)n(CAA)(CAG)` structure above; that is enough to *decide* this
item and not enough to make the answer universal. RM65's prerequisite — a real repeat-caller or CNV
VCF — is still missing, so the two items now wait on different evidence and this one is decidable
first.

## RM67 — polyploid and partially-phased genotypes

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Status** **not work** — a documented divergence, numbered so it is findable and not re-probed

VCF 4.4 §7.2 added polyploid partial phasing (`GT |0|0/1/2`), first phasing indicator optional. Our
grammar caps at two alleles and refuses a leading separator (probed: `A/A/G` and `A|G/T` both rejected).

This is a **defensible generalization** — the format annotates human diploid loci, and
`_check_contig_ploidy` already handles the hemizygous and haploid directions. **No change proposed.** The
spec's own polyploid example is a tandem duplication with SNVs on it, which a CNV-aware consumer will
meet, so revisit if one actually does.

**The message changed on 2026-08-14; the decision did not.** Dogfooding a duplicated CYP2D6 — the
spec's own polyploid example — refused the call with a bare restatement of the grammar, so a deliberate
limit read as a syntax error, while every other deliberate refusal in this schema names its own limit
in-line. The arity refusals now carry that sentence: two alleles is a decision, VCF 4.4 §7.2 permits
more, and nothing is queued against it. Recorded as D3-2 in
[DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md).

---

# The 0.6 dogfooding items deferred out of the fix round

The findings from [DOGFOOD_0_6_FINDINGS.md](probes/DOGFOOD_0_6_FINDINGS.md) whose obvious repair is itself a
design decision — the round filed five, and two have since left: RM69 for
[ROADMAP_1_0.md](ROADMAP_1_0.md) (see the header), and **RM70 shipped in 0.7**, its entry now in
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md). The three below are what remains. No fixed count is stated
here on purpose: one goes wrong silently the next time an item leaves, and this section has already
lost two. The ledger classes each **surface** rather than **fix**, which is this repo's standing
split: a false claim, a misdiagnosis, an unaggregated wall or an unreached guard gets fixed in the round
that finds it; anything whose repair has to be *chosen* gets filed with the candidates and the reason
each one fails. The refutations are the point of these entries — an item that only names a gap is one
somebody re-derives from scratch a release later.

Everything below is legal in a minor. Where a repair would be additive it says so; where the only
candidate repairs are illegal it says which principle bars them. Legality sizes the release; severity
only orders the queue.

## RM68 — a drafting provider on a non-GRCh38 module: refuse, or strip to the rsID

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium (high before the warning shipped) · **Status** the warning shipped in 0.6
(`enrich.source_build_mismatch`); **what the providers should do instead is deferred here** · **Owner**
enricher (the three drafting providers) · **Found by** dogfooding on 2026-08-13,
`reference_examples/cyp2c9_warfarin_grch37/`

### What was observed

`draft`, `draft-panel` and `draft-clinpgx` all take a `spec_dir`, and until the 0.6 dogfooding round
none of them read `genome_build`. `enrich.spec_genome_build` — written one release earlier for the bug
where the guard existed and the value never arrived — had **exactly one caller**. Every source these
providers read serves GRCh38: CPIC's `allele_definitions`, the ClinVar snapshot, the ClinPGx
annotations. So drafting CYP2C9 into a `genome_build: GRCh37` module writes `10,94942290` for
`rs1799853`, whose GRCh37 position is `96702047` — a different base 1.76 Mb away — and nothing anywhere
said a word.

Nothing downstream catches it. A coordinate is legal on either assembly; it is simply a different place.
What the online diagnosis reaches is now measured rather than asserted: of the module's two GRCh37 rows
declared as GRCh38, `grch37.diagnose_wrong_build` caught one and the other minted
`ga4gh:VA.pgprki8YgzfOSV9Dpe1ccPX4uNdlyAvB` and recorded `resolved`, because GRCh38 happens to carry the
authored `ref` at that position too. That is the documented ~3-in-4 sensitivity, so *"the compiler
catches wrong-build coordinates"* is not a reading anyone should take. Two of the three providers write
coordinates and can do this; `draft-clinpgx` writes none.

It hid because `test_pgx_draft.py`'s fixture declares `GRCh38`, and it is the only drafting test that
mentions a build at all.

**What shipped in the same session.** `enrich.source_build_mismatch`: each drafting command asks before
it writes and warns naming both builds, what a drafted coordinate will actually mean, and the two
remedies. The provider still writes the row, which is the enricher's standing shape for a disagreement
— report, never repair.

### The question

Report-and-still-write is the right *default*. What is undecided is whether a provider meeting a
non-GRCh38 module should go further: **refuse**, or **strip to the rsID** — writing the identity the
source does state without stating an assembly, which `derive_variant_key` prefers anyway.

**Refuse — wrong three ways.** It makes a GRCh37 module undraftable, so the author hand-authors instead,
and hand-authoring against a printed contract is where this format's most expensive documented failure
came from (the 0-vs-1-based `start` description shifted four whole modules by one base and passed every
offline gate, `--strict` included). It refuses a provider that cannot do the harm: `draft-clinpgx` writes
no coordinate, so a refusal keyed on the module's build stops a command whose entire output is
build-free. And it is the wrong granularity by the repo's own rule — *scaffolding refuses per file,
drafting refuses per row* — while a build mismatch is a property of the module, so a build-keyed refusal
is per **run**, which is the granularity that self-defuses into "this module cannot be drafted at all".

**Strip to the rsID — wrong, and worst on the rows that need it most.** It is tempting because the row's
identity does not move (`derive_variant_key` returns the rsID first) and an rsID names a variant without
naming an assembly. But CPIC's `sequence_location` publishes defining variants with a position and *no*
rsID — 18 in CYP2C9, 14 in TPMT, 4 in NUDT15 — and `HaplotypeRow` requires an rsID **or** chrom+start.
Stripping the coordinate there is not "write less", it is "drop the row", and it drops exactly the rows
the 0.5.1 `gene.chr` repair recovered after a year of being skipped. It also produces a row
indistinguishable from one the source had no coordinate for, so the author cannot tell a stripped row
from a bare one. Any *partial* strip is barred outright: a drafting provider fills identity whole or not
at all, and a lone `alts` on a position-only row makes `derive_variant_key` mint a `ga4gh:VA.…` instead
of `chrom:start:ref`, silently changing which variant the row is.

**Lift the coordinate over — refused, and RM48 already argues it.** RM48 is deliberately one-way and
reporting-only: a GRCh37 coordinate recovers an rs-number, and the rs-number is *reported*, never
filled, because filling it would make resolution verify a value against the service that produced it.
A liftover inside a drafting provider is that move with an extra assembly on it, and `chrom`/`start`
are both in `hints.REDUNDANCY_BEARING` for the same reason.

**A `--build` flag on the drafting commands — wrong twice.** A flag saying "write GRCh37" asks the
provider to convert, which is the liftover above. A flag saying "yes, I know" is a warning suppressor,
and the tier's standing rule is that `--offline` is the switch and a pass adds no second CLI flag.

**What would unblock it.** Either a real author with a non-GRCh38 module saying which of the two
outcomes they wanted, or **RM15**, which dissolves the premise: once identity is build-agnostic a
provider can write the coordinate under the build it came from, and there is nothing left to refuse or
strip. A behaviour fixed before RM15 lands is one RM15 would have to undo, which is the strongest single
argument for leaving this at a warning.

# Vocabulary residue from the 0.7 consumer round

## RM149 — expected behaviour lives in prose, and the prose is where two readers split

**Frozen, decided 2026-11-03.** The maintainer froze the Gherkin work. The verification bench beside the seats kit (`harness/bestiary`) marks all eight of its Gherkin entries retired by their origin, after the acceptance pipeline's originator reversed on it in September 2026, and the same day the maintainer chose TLC model checking over Gherkin for the kit's own acceptance work. Nothing here is built until that is reopened; the status line below predates it.

**What the freeze leaves running, decided 2026-11-03.** The maintainer kept the corpus gate:
`schema/tests/test_feature_corpus.py` still fails a new warning code that has no scenario, so `features/`
keeps growing as text with each new code, and with no runner. The freeze stops the review and the runner work
this entry asked for, not the corpus.

**Severity** medium · **Status** open — **a minor, taken into 0.8 on 2026-09-21; asked by the maintainer
2026-08-31** · **Owner** format + compiler (the test corpus) · **Found by** running the consumer loop

**The ask, verbatim in intent:** express our described scenarios as Gherkin, because the freeform prose
in expected-behaviour descriptions is producing ambiguities faster than it resolves them.

**The evidence for it is this repo's own recent record**, which is what makes this an item rather than a
preference. Three consumer reports in one week were **two readers splitting on one sentence**, none of
them a code defect:

- **S80** — `state`'s six members printed as peers; an agent chose a retired one honestly.
- **S83** — two runs of a byte-identical prompt wrote `risk` and `unknown` for one variant on one body
  of evidence, both green, both defensible against the field description.
- **S79** — a warning's text read as *your declaration is unsupported* when it meant *not universal*.

Each was answered by writing a better sentence. That is three fixes to prose in a week, and the pattern
says the next one is already in flight somewhere.

### What is actually being asked

Not a testing framework — the suite is not the problem, and a `pytest`-to-`behave` migration would be
motion rather than progress. The gap is that a **scenario** — *given a module with a partial
`resolution.csv`, when `validate --strict` runs, then it refuses with the compile's own error* — exists
today as a docstring, a test name, and a paragraph in `COMPILER.md`, and those three can drift from
each other and from the code. A structured form is one statement, and the natural home is a
`.feature`-shaped corpus each side is derived from or checked against.

### Open questions this needs decided before it can be built

- **What is the source of truth.** Gherkin generated *from* the tests is documentation that cannot
  drift; tests generated *from* Gherkin makes the feature files the contract and every existing test a
  migration. These are opposite projects with the same output, and the ask does not say which.
- **What is in scope.** Every check the compiler runs is ~140 warning codes plus a mode ladder. The
  release-gate scenarios, the tri-state outcomes and the parity rules are the parts where ambiguity has
  actually cost something; the round-trip fixed points are already pinned by assertion and would gain
  nothing from prose.
- **Where it lives.** A `features/` tree at the root, per-package, or inside `docs/`. That decides
  whether it ships to consumers — and if it does, it becomes a published surface under P3, which is a
  much larger commitment than an internal one.
- **What it costs the next contributor.** A second dialect to learn beside the docstring convention
  this repo already leans on heavily, and every new check owing a `.feature` clause. That is the P9
  question one layer up: this is a *maintenance* surface, not an authored one, and it is not free.

### Why it is filed rather than started

The three reports above were each fixed by naming what the rule is, and the fix was one string. A
scenario corpus is worth building when the *cost of ambiguity* exceeds the cost of the corpus, and the
measurement that would show that has not been taken — this entry is where it goes when it is. What is
not in doubt is the direction: the recurring failure is real and repeatedly measured, and it is filed
here so the next instance lands against a number rather than as a fourth anecdote.

### Addendum, 2026-09-13 — a first corpus is drafted, and this is the measurement

**Status is still open.** What exists is a draft, unreviewed, at `features/` in the repository root:
12 `.feature` files, 213 scenarios, guarded by `schema/tests/test_feature_corpus.py`. Nothing
about it is a contract yet, and the entry stays here rather than moving to ROADMAP_HISTORY until it has
been read.

**Two of the four blocking questions are answered by the ask itself**, and are recorded in
`features/README.md` as assumptions rather than decisions:

- **Source of truth: code → Gherkin.** The scenarios describe what the code does. No step definitions,
  no `behave`, no `pytest-bdd`, no new dependency in any tier; the `pytest` suite stays the executable
  statement of behaviour and this is the readable one.
- **Where it lives: the repository root, not `docs/`.** That keeps the P3 publishing question *open*
  rather than answering it by side effect, which a drafting round has no standing to do.

**Scope is decided by registry rather than by taste**, which is the third question. Three walked sets
are covered in full: `VALID_WARNING_CODES`, `VALID_VERIFICATION_CHECKS`, `VALID_VERIFICATION_SKIPS`.
Round-trip fixed points are out, on this entry's own argument. **And the scope estimate in the body
above is wrong by a factor of two**: it says *~140 warning codes*, and `VALID_WARNING_CODES` has **73**.
A number in prose beside a registry, in the entry that exists because prose drifts — left in place
above rather than silently corrected, because it is the fourth instance of the shape this round
measured and the most on-the-nose.

**The fourth question — what it costs the next contributor — has a partial answer and it is the
cheaper half of the estimate.** A new warning code without a scenario fails the guard, so the cost is
one scenario per code, not a second dialect to learn: there are no step definitions to write and no
runner to learn. What is *not* yet measured is whether a reviewer finds the scenarios easier to check
than the docstrings they stand beside, and that needs a reader rather than a round.

#### The measurement this entry was waiting for

The case for the corpus was to be made on *the cost of ambiguity exceeding the cost of the corpus*.
Drafting it produced **four findings in the first pass**, two of them code-or-doc defects that were
filed and fixed rather than noted:

| # | finding | disposition |
| --- | --- | --- |
| 1 | **Two of our own documents disagree about whether `strict` builds.** COMPILER.md's validate-by-redundancy table gives the rsid↔coordinate check the severity *warning* with no qualifier; its own mishap matrix gives the same check *⚠️ warning / ❌ refuses*. The matrix is the half the code agrees with. | marked `# DRIFT:` in `features/compiler/mode_ladder.feature`, unrepaired — the round's findings are its output |
| 2 | **The mode ladder is two mechanisms and reads as one.** Four codes flip channel on one sentence; three resolution codes pair a warning with a *different, longer* refusal through `ResolutionOutcome.strict_errors`. Calling those ladder members quotes a text that does not exist; calling them warn-only describes a compile that succeeds. | written down in the same feature; no defect, a distinction nothing stated |
| 3 | **`alphagenome check` with no API key raised instead of recording a skip** — `skipped(CHECK, "unchecked")`, and `"unchecked"` is not a vocabulary member. | **[RM242](ROADMAP_HISTORY.md#rm242--alphagenome-check-without-an-api-key-raised-where-it-was-supposed-to-attest-nobody-asked)**, fixed |
| 4 | **Four per-command attestation counts summing to 17 of 24**, in ENRICHER.md's paragraph that refuses to state a total. | **[RM243](ROADMAP_HISTORY.md#rm243--the-paragraph-that-refuses-to-state-a-total-stated-four-of-them-summing-to-17-of-24)**, fixed |

**What produced each of them is worth separating from the fact that they were produced.** None came
from reading prose more carefully. Finding 1 came from writing the severity down as a table and
noticing two tables; finding 2 from having to name a mechanism in order to tag a scenario; findings 3
and 4 from AST walks the corpus needed anyway — the emission-site check and the skip-reason enumeration.
So the argument this addendum supports is narrower and stronger than *Gherkin is good*: **the act of
deriving a scenario from an emission site is what found things, and the guard is what will keep
finding them.** A corpus of prose scenarios with no grounding check would have found none of the four.

#### The three assertions that make it worth more than the prose — and what each really covers

Each was proven by reintroducing the defect and watching it go red, which is this workspace's standing
requirement. Two of the three were **narrower than they read on the first pass**, and both narrowings
were found by measuring rather than by re-reading, which is worth recording because a guard that
half-covers its subject while the reference claims it covers all of it is worse than no guard:

- **a `@code:X` scenario's `# source:` sits within three lines of X's own `CodedWarning` call.** Held
  from the start.
- **the same alignment for `@check:` and `@skip:`.** *Missing at first*, and it cost precisely what it
  exists to prevent: RM242 and RM243 — the two fixes this round produced — inserted six and eight
  comment lines above referenced sites, eleven `# source:` lines silently began pointing six to eight
  lines early, and the suite stayed green, because those two tags had only *the line is inside the
  file*. The guard now catches all fourteen when the insert is reproduced. Two of the eight skip reasons
  (`tautology`, `not_permitted`) are never passed to `skipped()` as a literal at all — they travel as a
  variable — so the alignment is against any literal naming the reason, which is the better pointer
  anyway: where a reason is *decided* is what a reader wants.
- **every phrase a step quotes as a warning's text is a real substring of a real string literal in the
  module named.** *Keyed on a verb before the quote at first* (`contains`/`says`/`states`), which
  extracted **46 of the 162** quoted phrases — a `Then` also says `saying the flag "…"`, `ends at "…"`,
  `continues "…"`, `offers "…"`. Keyed on the step keyword instead, it now checks **160 of 160** on
  outcome steps, and the widening found three real defects in the corpus. `Given`/`When` stay excluded:
  those name an input value, which has no reason to appear in the module's own strings.

**The residue, measured rather than estimated.** Of 213 scenarios, **108 carry a registry tag and are
aligned; 105 are structural** — pointing at a docstring, a branch or a constant, with no call site to
align against — so they carry only the *line is inside the file* check and will rot on an edit above
them. Measured 2026-09-13 by walking the corpus, because the first draft of this paragraph said
"roughly 130" on an estimate, in the document whose whole subject is unmeasured counts beside
registries. That is a real contributor cost and it belongs in the fourth question's answer above rather
than in a footnote.

One mechanism had to be added rather than worked around: a message built by one module and coded by
another (`layout.deprecation_notice` writes the sentence, `_locate_sidecar` names the code) needs a
`# text:` line, so the code is checked against the emission site and the phrase against the module that
holds the words. That is the boundary where a code goes missing
(`@finding-loses-its-code-at-a-boundary`), and it is better as a checked fact than a convention.

#### What a review should push on

- **Is the root the right home, or should this publish?** Publishing makes every clause a P3
  commitment. The draft assumes not, and the assumption is the thing to overturn first if at all.
- **Are the scenarios readable by someone who did not write them?** That is the whole premise and it
  cannot be self-assessed. If the answer is no, the corpus is a second dialect with none of the benefit
  and this entry should close rather than grow.
- **Should the DRIFT finding be repaired here or filed?** Finding 1 is one sentence in COMPILER.md.
  Leaving it marked was deliberate — a round that silently fixes what it finds cannot be audited — but
  it should not stay marked for long.
- **The corpus has no scenarios for the compiler's `errors` that carry no warning code**, beyond the
  handful written as `@refusal`. Whether a refusal without a code deserves the same coverage as a coded
  warning is an open scoping question the registry cannot answer, because refusals have no registry.

### Second addendum, 2026-09-13 — the second pass, and where coverage was not what the equalities said

**Still open, still a draft.** The corpus is now 13 files and **228 scenarios** — 118 registry-tagged
and aligned, 110 structural — with **182 quoted phrases** on outcome steps. The question this pass put
was the one the first pass could not put to itself: *are all the features covered?* The three registry
equalities said yes and they were answering a narrower question than they read.

**Four findings, and what produced each.** None came from reading the scenarios again; three came from
walking a set the first pass did not walk, and the fourth from reading the residue the first pass
measured and left.

| # | finding | disposition |
| --- | --- | --- |
| 5 | **A code is not a text.** Nine resolution codes are emitted by the compiler's `resolution.py` *and* by the enricher's `resolver.py`, and **seven of the nine pairs are a different sentence**. `rsid_unresolved` is *"not found in resolution table, position remains unset"* in one tier and *"not in the injected Ensembl snapshot"* in the other. The per-code equality accounted for all nine while the corpus held none of the enricher's words for any of them, and a warning's text is an API. | fixed — the equality now keys on `(code, tier)`, and `features/enricher/resolution_warnings.feature` is the nine in the enricher's own words |
| 6 | **The house algebra was covered as a mechanism and not as a value.** `tri_state.feature` had Kleene, the withhold, `classify` and `restate`, and not one of the columns that carries a three-valued answer into an artifact: **five of the nine members** of `VALID_FREQUENCY_STATUS`, `VALID_RESOLUTION_STATUS` and `VALID_AUTHORITY_CALL_STATUS` appeared nowhere in the corpus, `not_covered` among them — the member the gnomAD Y-PAR probe was run to justify. | fixed — six scenarios; the walk that found them (three-member `VALID_*` sets) is recorded as the heuristic it is |
| 7 | **`@ladder` was a judgement written four times over a walkable set.** The mode ladder's first mechanism is `(errors if strict else warnings_out)`, and the codes reachable from a function carrying that shape are exactly the four tagged. | fixed — a fourth registry equality, proven red by untagging `p_value_encodings_disagree` |
| 8 | **Ten `# source:` lines pointed at a blank line, a bare `"""`, a bare `return [` or the middle of a comment — and two pointed at the wrong subject.** *a total function cannot decide a three-valued answer* named a comment about a length constant in `normalize.py` when the rule is `mitomap.vcep_clin_sig`; *an absent input is the unknown arm* named the concordance block in `vocab.py` when the rule is `needs_recompile`. Both scenarios stated their rule correctly and cited the right tag; only the pointer was wrong. | fixed — all ten re-anchored; **not rot**, since no source file here has changed since the corpus was written, so they were authored that way and nothing could say so |

#### Two questions the first addendum left open, now answered with a measurement

- **Refusals without a code have no registry, and the reason is that they have no shape.**
  `compiler.py` alone reaches the error channel from **four** distinct mechanisms — an inline
  `errors.append` of a literal, an `extend` of a helper's returned list, the
  `(errors if strict else …)` selector, and `ResolutionOutcome.strict_errors` — across roughly forty
  sites, against 22 scenarios tagged `@refusal`/`@strict_only`. So the answer to *should a refusal
  without a code get the same coverage as a coded warning* is not *no*; it is that **there is nothing to
  walk**, and inventing a registry so an equality can be written would be the `@registry-completeness`
  defect committed on purpose. It stays a scoping question for a reviewer, now with a number beside it.
- **The phrase check's file scope is correct, and that was measured rather than assumed.** Eight of the
  182 quoted phrases match no message at the site their scenario names but do match another literal in
  the same module. All eight were read: every one is a message built into a variable a few lines away
  (`ambiguous_warnings`, `_verify`, `coordinate_disagreement`, `layout.deprecation_notice`). Tightening
  the check from the module to the call site would need dataflow and would report eight correct
  scenarios as defects. Recorded so the next pass does not re-derive it.

#### What this pass did not touch

The `# DRIFT:` in `mode_ladder.feature` still stands — finding 1 of the first pass, one sentence in
COMPILER.md, and a repair decision rather than a drafting one. And `# anchor: <token>`, a symbol the
guard could grep for instead of a line number, is the obvious repair for the 110 structural scenarios
and is deliberately unbuilt: it is a convention change across the whole corpus and belongs to whoever
reviews it.

**Not to be confused with** `just-module-creator`'s authoring guidance, which is a different
document for a different reader and stays prose. This is about *our* stated behaviour, not an author's.

# The lifecycle items — what writing down the second pass surfaced

Filed on **2026-08-16** out of [MODULE_LIFECYCLE.md](MODULE_LIFECYCLE.md), which mapped a module from
origin to publish to a consumer's join and found that **the second pass had never been written down at
all**. Four items, none of them a defect in a rule: each is a place where two individually-correct rules
compose into something nobody chose, or where an absence only bites the second time somebody opens a
module. The document keeps the measurements (§5.1 the canary, §6.2 the six-edit consequence matrix, §6.3
what deleting a sidecar costs); these entries keep the decisions and the refused repairs, and do not
restate the numbers.

They were the closing section of that document — an "open questions" list — which is exactly the shape
this repo has twice found to be a backlog nobody reads. A question filed against a release is findable;
a question at the bottom of a prose document is not.

Everything here is legal in a minor.

## RM84 — a module has no version identity on the discovery path, and the publisher is the half we own

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium-high · **Status** **our half SHIPPED in the 0.6 PT2 batch (lane D, 2026-08-17)** —
`upload_module` writes `data/<name>/` and `data/<name>/v<version>/`. **The segment spelling is settled
and both asks are answered** ([S35](CONSUMER_SUGGESTIONS_HISTORY.md), 2026-08-17): `v<version>` verbatim
stays. Only the consumer's discovery half is open, and it is theirs, which is why this entry stays here.
*Previously:* our half taken into 0.6 PT2 on
2026-08-16 ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM84); before that, open — **joint with the
reference consumer, and their half is already agreed in writing** · **Owner** enricher
(`upload.upload_module`) + `just-dna-lite` discovery ·
**Motivating case** a republished module on the HuggingFace path

**Why a partial mitigation does not close it** (S34 §3): the fields a consumer can read today record
*where* a module came from, never *which build* of it. Two uploads under one path are then
indistinguishable on the discovery side, which is the half this item exists for.

### What was observed

[MODULE_LIFECYCLE § 6.8](MODULE_LIFECYCLE.md#68-what-a-consumer-sees-when-v2-lands) traces two
acquisition paths with two entirely different notions of "updated", and neither delivers a notification.
The registry path at least has a per-version audit. The **discovery path has no version identity at
all**: no version in the path, no manifest fetch, no digest check. A republished module keeps the same
URL, so a cached copy shadows it, and the only invalidation is a purge keyed on the *consumer
application's own package version*. Stated plainly: on that path the identity used to detect "the module
changed" is a property of the reader, not of the module. A module republished with new science while the
app stays pinned is invisible; an app patch release with no module change purges everything.

**Half of that is ours.** `just_dna_enricher.upload.upload_module` writes the flat `data/<name>/` layout
— so this tier publishes the shape that cannot express a version, and no amount of consumer-side work
invents one.

### Why it is joint rather than ours alone

A pinning surface is a change to our publisher **and** to their discovery in the same breath: a version
segment nobody reads is dead bytes, and a reader looking for a segment nobody writes finds nothing.
[S34 § 4](CONSUMER_SUGGESTIONS.md) is the consumer's half, already stated: *"If the publisher grows a
version segment we will follow it in discovery; the `vN` fallback in our generic fsspec scan is already
the shape."* That is as close to a pre-agreement as a cross-repo item gets, and it makes this cheaper
than "wants agreeing" implied when it was first written down.

### What is undecided

*Was:* the layout itself — a `vN` segment, a digest segment, or a pointer file — and what happens to
every module already published flat, which is all of them. Whatever is chosen has to leave an
unversioned path working, because that is what is deployed.

**Settled on our side.** The layout is the dual write, decided in PROPOSAL_0_6_PT2 § RM84 and built in
lane D. Nothing already published moves, because the flat path keeps being written and keeps meaning
*latest*. The full behaviour, including the null-version fallback and the two-commit caveat, is
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

### The ask was put, and answered the next day — both questions closed

**Asked** in ENRICHER.md (RM27's shape: a finding about a downstream reader is an explicit ask, never an
implication), delivered there rather than into their tree because `just-dna-lite` carries no consumer
inbox. **Answered as [S35](CONSUMER_SUGGESTIONS_HISTORY.md) on 2026-08-17**, read off their code file
and line rather than recalled.

*(1)* **Their scan matches only `v`-plus-integer** — `^v(\d+)$`, compared with `int()`, so `v1.0.0` does
not match and `v10` would sort under `v9`. **The half that actually decides it is their correction, not
the regex:** that fallback lives only in `_discover_fsspec_source`, the generic github/http/s3 branch.
HuggingFace has its own branch with **no version fallback at all** — so on the path this item is *about*,
no spelling is read today and the segment cannot be chosen to suit one. Their words: S34 § 4's *"the `vN`
fallback in our generic fsspec scan is already the shape"* was accurate about the shape and quoted about
a branch that does not serve HF, and they call that their error rather than a misreading here.
**So `v<version>` verbatim stays** — a bare major segment would still collide two patch releases at one
path, and would buy nothing since the code that would read it is not on this path.

*(2)* **No, and by construction rather than by luck.** Both discovery branches call `fs.ls` at exactly
one level and never `fs.find`, a `**` glob or a recursive listing, and their probe asks `fs.exists` on
named files rather than listing the directory it is probing — so a nested `data/<name>/v<version>/` is
never enumerated and never probed. Verified in their tree by search: no `fs.find`, `recursive=True`,
`maxdepth` or `snapshot_download` against a module path anywhere. The one part of this change that could
have regressed a consumer who never adopts it, and it does not.

**One consequence recorded rather than fixed**, raised by them as a consequence and not an objection:
the dual write doubles the collection's bytes and nothing prunes `data/<name>/v<version>/`, so the repo
grows one full artifact set per release forever. It does not affect discovery. Retention is the
collection owner's decision, not the publisher's; noted in
[ENRICHER § the publisher surface](ENRICHER.md#a-module-is-published-twice-and-the-second-path-is-the-one-that-can-name-a-release-rm84).

**What is left here is theirs and unscheduled:** teach `_discover_hf_source` a versioned fallback, and
replace the regex and `int()` with `just_dna_format.identity.Version`, which already gives them parsing
and ordering. Nothing is broken meanwhile — the flat path resolves and keeps meaning *latest* — so their
`read_module_provenance` states `version: None` for every HF-discovered module, which their report
renders as *Not stated*.

**Confirmed by exhaustive search to have had no `Sn` and no `RMn`** before this entry, which is why it
is filed rather than cross-referenced.

### Two items building this surfaced, filed 2026-08-17 rather than folded in

Both were found by writing the code, not by planning it, and neither is a defect in what shipped —
recorded here because this entry is where a reader meets the publisher.

- **[RM88](history/ROADMAP_HISTORY_0_6.md#rm88--republishing-without-bumping-version-overwrites-a-versioned-path-with-different-bytes)** — the versioned path cannot notice that the version has *not* moved, so a republish
  without a `version:` bump overwrites it with different bytes. Refusing needs a remote read *and* an
  undecided policy (warn / refuse / `--force`), which is why it is an item and not a fix.
- **[RM89](history/ROADMAP_HISTORY_0_6.md#rm89--the-publisher-cannot-upload-a-table-only-module-at-all)** —
  `_REQUIRED` still demanded all three SNP-core parquets, so a table-only module could not be published
  at all: seven of the sixteen reference examples, measured. Its open question — what the discovery path
  actually needs open — went to the same team as the two asks above rather than as a third message, and
  **came back with them in S35, so it shipped on 2026-08-17**. Answering it found the larger half:
  `_ALLOW_PATTERNS` carried no 0.4 family and no derived-fact table either, so eight *more* examples
  published a manifest attesting parquets that were never uploaded.

# Moved from ROADMAP.md: the minors whose release was undecided

These ten were open on [ROADMAP.md](ROADMAP.md) as *a minor, release undecided*. The maintainer's 2026-11-03 scope decision for 0.8 left them out, so each now waits on 0.9.

## RM265 — the `panel:` deprecation has no "accepted" signal: on the replaced branch the warning fires whether or not you need the three fields it tells you to keep the block for

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, release undecided** · **Owner** compiler / format
(`panel:`, the licence row) · **Motivating case** [S114](CONSUMER_SUGGESTIONS_HISTORY.md#s114--the-panel_block_deprecated-replaced-branch-warns-whether-or-not-you-need-the-three-fields-it-says-to-keep-the-block-for-so-there-is-no-way-to-signal-accepted)

**What was confirmed.** Reproduced against all three just-dna-lite ClinVar panel modules and against
the code. `panel_block_deprecated` fires on the `replaced=True` branch (`compiler.py:4231`) for a
module that has done everything the migration asks — its `clinvar/annotation` licence row carries a
non-empty `dataset`, so the block's one machine reader (the enricher's clin_sig cross-check) is
migrated. The message's closing clause, correct since S69, is that `genes`, `significance` and
`reference_sha256` "have no replacement anywhere — keep the block until 1.0 if you need them recorded."
But keeping the block *is* the permanent warning: the block emits `panel_block_deprecated` whether or
not those fields are wanted, and there is no key to say "accepted, I need the three, stop." A consumer
who needs them warns forever; a consumer who wants a clean compile drops provenance the format itself
says has no home. The two outcomes are "warn forever" and "lose data".

**The design question this records.** Is `panel:` deprecated *as a whole*, or only its reader? P3
deprecates in a minor only where the audience can **act** — the replacement exists and the deprecated
thing is not still the only record — and for these three fields on the replaced branch no replacement
exists, which is the state P3 forbids. Two candidate fixes, and the naive one is not free:

- **Give the three fields a non-deprecated home** — a small `panel_provenance:` sub-block, or three
  keys beside `dataset` on the licence row. This is the P3-clean answer: it completes the replacement,
  so the deprecation becomes actionable. Cost is P9-full if authored (a `panel_provenance:` block the
  rare author writes) or P9-half if it rides the machine-written licence row; additive either way, so
  **minor**. It is a schema-shape decision — where the fields live, whether the gene *denominator*
  (S114's one lossy field: `cardio` requested 327 genes, 297 matched a variant, the 30 that matched
  none are absent from `variants.csv`) is a list or a count — and belongs in the version interview,
  not an unattended pass.
- **Fire `panel_block_deprecated` only on the `replaced=False` branch** (patch). Tempting and **not
  free**: it silences a *true* statement on exactly the modules that keep the block for the three
  fields, so they compile clean until 1.0 removes the block under `extra="forbid"` and the data with
  it. P3 requires a major to ship its upgrade procedure; theirs would read "lose the data." So this
  mitigates the noise at the cost of hiding the loss — a stopgap, not the resolution.

**Related.** The idea-book's § D19 (this file) raised the same two candidates against the pre-S69
message; S114 is its sharpened, corpus-backed form. The stale RM4 row in
[ROADMAP_1_0.md](ROADMAP_1_0.md) § the upgrade tracker still tells the author "delete it, nothing
replaces it, consumer: no action needed" — corrected there in the same triage pass as a doc fix,
since that tracker is the procedure P3 turns on.

## RM266 — the phase-confusable diplotype-pair set is computed at compile and dropped: it reaches the artifact only as a capped warning string

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** compiler
(`_cross_validate_diplotypes`) · **Motivating case** [S116](CONSUMER_SUGGESTIONS_HISTORY.md#s116--rm28-the-hfe-compound-het-vs-cis-case-is-a-meta-conclusion-a-consumer-can-name-but-not-resolve), note 2

**What was confirmed.** Reproduced by compiling `reference_examples/hfe_compound_het`: the
`diplotype_phase_ambiguous` warning fires and names the exact set S116 says the artifact cannot carry —
`HFE: 1 group(s) … e.g. C282Y/H63D, C282Y-H63D/wt`. So the compiler **already computes** the
phase-confusable pair set. `_cross_validate_diplotypes` (`compiler.py:3457`) groups a gene's diplotype
pairs by their phase-preserving definition signature and separates *indistinguishable at all* (identical
definitions, `diplotype_definitions_identical`) from *phase would decide* (`diplotype_phase_ambiguous`) —
which is precisely the distinction a caller reconstructs at query time. It is then flattened into a
warning string and capped at three examples (`_examples`), so a reader of the artifact who is not
running a caller cannot recover the set, and beyond three groups cannot see it at all.

**Why this is not RM28.** S116 frames note 2 as wanting an RM28 axis — an author *stating* "this pair
is distinguishable from that one only by phase." But the author does not need to state it and should
not: it is **derived** from `haplotypes` + `diplotypes`, and the compiler derives it today. This is
`@dont-discard-computed`, not a new authored surface — the fix is to stop discarding the structure, not
to add an axis. The general shape is the idea-book's § D3/§ D4 (warnings are `list[str]` with no code,
count or payload); RM266 is the specific case where the *payload* — the confusable groups, by name — is
the thing worth carrying, over and above D3's per-code count.

**The shape, filed not built.** A structured surface for the computed groups — a `manifest.json` field
keyed by gene, or a small optional parquet — so a downstream reader sees the confusable set without
re-deriving it. Additive (a new optional derived surface, P9 ≈ free-to-half), so **minor**; the open
question is manifest field versus parquet, and whether it subsumes or sits beside a general
`warnings_summary` (§ D3). Corpus, not code, decides urgency: this is `just-dna-lite`'s first caller and
it already re-derives the set successfully, so nothing is blocked.

## RM281 — the PGx lane reads one of ClinPGx's archives, and `clinicalVariants.zip` bears on a shipped table kind

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **a minor, release undecided** (a source adoption) · **Owner**
enricher (`clinpgx_build`, `clinpgx_draft`) · **Motivating case** RM166's *"It wants its own number"*,
unfiled until the 2026-09-27 postmortem sweep (P9) · *related* RM166, RM173, RM175

RM166 noticed that ClinPGx publishes at least twelve archives while the lane builds from one
(`summaryAnnotations.zip` today, per RM173). `clinicalVariants.zip` is the one that bears on a shipped
kind: about 5,190 rows of `pharm_variants.csv` territory. Its `type` is a six-member base vocabulary
that **comma-combines**, so an adoption has to normalize the *combination*, not the token
(`@one-normalizer-two-spellings`).

**Confirmed on 2026-09-27.** No module in `enricher/` names `clinicalVariants`. The lane's builder
reads `summaryAnnotations.zip` and refuses the retired `clinicalAnnotations.zip` (RM173), and the
`drug_labels` lane is separate.

**Why a minor.** Adopting it is a new drafting route, or new columns in a published snapshot. It is
also the same terms as the rest of the lane (CC BY-SA, no sale), so it widens nothing on the licence
axis. That half is RM282.

## RM282 — the PGx lane has one licence class, CC BY-SA with no sale, and nothing looks for a source outside it

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **a minor, release undecided** · parked on a survey chosen for
terms first, and the class is settled by what it finds · **Owner** enricher (source adoption) · **Motivating case** RM166's *"it
wants its own entry"* (also PROPOSAL_0_7_PT2 § the decision), unfiled until the 2026-09-27 postmortem
sweep (P9) · *related* RM166, RM281, `@pgx-research-only`

RM166 closed its FDA half measured: *"the lane does not gain a member outside its licence class by
this route, and the direct route cannot supply one either"*. It then said that if licence
diversification for the PGx lane still matters (*"it plausibly does, since it is a single point of
failure on the axis the format gates on"*), it wants its own entry, with candidates chosen for their
terms first. No entry was written.

**What is true today.** ClinPGx, CPIC and PharmVar are all CC BY-SA with no sale
(`@pgx-research-only`), and the compile gate (`@gate-is-data-driven`) refuses a commercial declared use
on every module drafted from them. A commercial author has no PGx source at all.

**The gate, and why it is satisfiable now.** A survey of PGx sources ranked by terms before content.
Anyone can do it today and it needs nothing built. If it finds a candidate, adopting it is a normal
source adoption (a minor). If it finds none, this closes as measured, with the survey as the record.

## RM284 — a skip is a fact about the run, and `verification.json` has no run-level place to keep one

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** format (the
verification document) + enricher (the writer) · **Motivating case** RM72's *"a run-level fact needs a
run-level place, which is a separate question and was not opened"* (decided in 0.6 PT2), found unfiled
by the 2026-09-27 postmortem sweep (P11) · *related* RM72

RM72 decided the merge rule for `verification.json`: newest wins between two records of the same
disposition, and a skip does not displace an answer while the earlier record still binds the authored
bytes (`existing_still_binds`). The design half it answered and set aside is this one. A reader may
legitimately want to know that *today's* enrichment could not reach a source, and under the shipped
rule that fact is dropped: the older `ran` record is what stays.

**Confirmed on 2026-09-27.** No open item names a run-level skip record, and `verification.json`
remains a per-check document.

**Why a minor.** A run-level record is a new field or block in a published document, whatever shape it
takes. The shape question is where it lives: in `verification.json` beside the per-check records, or
in the run's own output (`EnrichmentResult`), which RM272 is already widening on the `0.8` branch.

## RM286 — PharmVar's research-use-only, personal-key restriction lives in `notice` prose, and RM27 closed without the axis RM38 handed it

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **a minor, release undecided** · **Owner** format (`SourceRow`) +
enricher (the PharmVar terms constant) · **Motivating case** RM38's *"belongs to the RM27 design
round"*, a pointer to an item that closed without it, found by the 2026-09-27 postmortem sweep (P13)
· *related* RM38, RM27, `@pgx-research-only`, `@gated-source-caches`

RM38 declined a `SourceRow` column for PharmVar's restriction (research use only, a non-transferable
personal key). The restriction is narrower than `commercial_use=False`, so today it lives only in
`notice` as prose. RM38 handed the axis to *"the RM27 design round, which already owns 'the recorded
axes do not cover every real restriction'"*. RM27 shipped in 0.6 as a record-only redistribution
verdict with the registry named as enforcer. It designed no further axis, so the handoff landed
nowhere.

**One premise to correct before designing.** RM38 sized the column as 1.0 because *"a new column on an
existing parquet moves every compiled module's digest"*. A digest moving is not by itself a reason to
defer (the house coding standards say so), and a new optional column is minor-legal under P3 and P8.
So this is a minor if built.

**What to decide.** Whether research-use-only and personal-key are one axis or two, and whether
either is tri-state like `share_alike`/`commercial_use` (an unestablished permission is never a
permission). Also whether the compile gate reads it, or it stays recorded-only like `redistribution`.
A new authored-schema column costs the full P9 price, though `sources.csv` is mostly machine-written.

## RM287 — ClinGen's dosage pass is a live download with no snapshot lane, so an offline deployment never runs it

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** low · **Status** open — **a minor, release undecided** (a new cache lane) · **Owner**
enricher (`clingen`, `CACHE_LANES`) · **Motivating case** RM39's *"Not done, and it was asked for
explicitly: a ClinGen snapshot"*, never filed, found by the 2026-09-27 postmortem sweep (P14) ·
*related* RM39, RM38, `@gated-source-caches`

RM39 gave the ClinGen dosage pass an `offline` flag and a `skipped_offline` state, so an offline run
says it did not ask. It left the snapshot the reporter asked for explicitly, calling it *"RM38's family
and a much bigger question"*. Nothing filed it.

**Confirmed on 2026-09-27.** `CACHE_LANES` has fifteen lanes and none is ClinGen. `clingen.py` still
fetches the gene-curation list live and skips under `--offline`. Every other pass in the family reads
a snapshot, so an offline deployment gets every answer but this one.

**What building it owes.** A lane, so `docs/CACHE_SURFACE.md`'s checklist applies line by line
(three stages, each absent one with its reason as a field, `repro_out` default, parents). ClinGen's
terms have to be recorded as a `SourceRow` before the lane can be published. A new lane is new public
surface, so this is a minor.

## RM296 — a PRS has no condition → conclusion table, so `pgs.csv` only restates what the PGS Catalog already publishes

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, release undecided** (a new optional binning kind) ·
**Owner** format (schema) + compiler · **Motivating case** the maintainer, 2026-09-27: *"modules are
condition → conclusion by design; just listing PGS is a bit tautological, they have own EFOs"* ·
*related* RM16, RM47, RM289, RM163

**What is missing.** Every other kind a module carries maps a measured condition to an authored
conclusion: a genotype to a `conclusion`, an activity score to a metabolizer phenotype, a repeat count
or a copy number or a heteroplasmy fraction to a band. `pgs.csv` maps nothing. Its row is an accession,
the trait's EFO ids, ancestry and a research tier, all of which the PGS Catalog already publishes per
score. A module cannot say *"above the 95th percentile of PGS000018 in a matched reference: elevated
CAD risk relative to that reference"*, which is the sentence a PRS module exists to carry.

**Why the refusal it replaces was a choice, not a constraint.** `pgs.py`'s docstring says a PRS yields a
Z or percentile within a matched reference distribution, *"which the format does not bin"*. Binning
one is the `activity_phenotype.csv` shape: the consumer computes the number and the module bins it, so
the data-agnostic line (no measured value in a module) holds exactly as it does there. Nothing in the
charter forbids it. A new optional table is minor-legal (P3, P8) and costs the full authored price
(P9).

**The shape, as a starting point.** A `MeasureBinRow` subclass keyed on `pgs_id` (joining `pgs.csv`,
which becomes the declaration the bins hang on rather than the whole module). It inherits bounds,
`measure_tiling`, the `unresolved` no-call sentinel and bin-level `pmid` (RM47).

**What has to be designed, and it is the part that stops this being a tautology too.**

- **The measure's unit and frame are part of the claim.** A percentile and a Z are different axes, and
  either is meaningful only against a named reference distribution. A bin has to say which
  (`measure_unit`, and a reference identifier), or a band means nothing.
- **Ancestry mismatch withholds.** A sample outside the bin's reference or `training_ancestry` gets
  *unknown*, never the band (the house tri-state). The same applies below `match_rate_floor`, which is
  what `unresolved` is for.
- **`research_tier` constrains the conclusion.** A `research_only` score supports only relative
  statements (*"higher than N% of the reference"*). An absolute-risk band needs `calibrated`. Whether
  that is a check or a documented rule is open.
- **Continuous tiling** is the natural default for a percentile or a Z (`@measure-tiling`).

RM16 (authored weights) is a different question and this does not depend on it. When this ships,
`pgs.py`'s docstring, TABLES.md § `pgs.csv` and ROADMAP_0_8 § RM16's *"a shape the format does not
bin"* all change with it.

### RM297 — the ClinPGx currency check compares a row against an annotation it never cited

✅ **Shipped 2026-09-28 on `main`, uncut — a patch.** The entry is in
[ROADMAP_HISTORY.md](ROADMAP_HISTORY.md#rm297--the-clinpgx-currency-check-compares-a-row-against-an-annotation-it-never-cited).
This heading stays only because S122's reply links here, and replies are the triage seat's to
retarget; delete it in the same commit that moves that link. It is a `###` on purpose: a `## RMn` here
is an open item to the §4 counter (`test_triage_tools.py`), and this one is not open.

## RM298 — nothing records per row that a `pharm_variants.csv` row came from ClinPGx

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, release undecided** (a new optional authored
column) · **Owner** format (`PharmVariantRow`) + enricher (`clinpgx_draft`, `clinpgx`) · **Motivating
case** S122 via RM297, decided with the maintainer 2026-09-27: *"the mitigation is warning, not
blocking. Solution comes in minor"* · *related* RM297, `@source-vs-authority`, `@write-the-sourcerow`

**What is missing.** Provenance for this table is recorded per `(source, layer)` in `sources.csv`. A
module that mixes ClinPGx-drafted rows with rows a curator took from an article, CPIC or DPWG cannot
say which is which. So the ClinPGx currency check cannot tell a withdrawn ClinPGx annotation from a
row that never cited one, and RM297 has to withhold on both.

**The shape, as a starting point.** An optional per-row column naming the source whose accession
`annotation_id` is. `draft_pharm_variants` fills it, and a curator may set it or leave it empty. The
check then refuses under `strict` on an absent id only for rows that name ClinPGx, and withholds on the
rest. Empty stays the unknown arm, never "not ClinPGx".

**To design before building.**

- **The name and the vocabulary.** The value set is the `sources.csv` `source` column, so an
  undeclared name is a finding. Audit the name against the reserved namespace (P5).
- **Back-fill for published modules.** An existing drafted row has none. Whether `draft-clinpgx`
  fills it on a row it recognises as `already_present` is a merge-not-clobber question
  (`@draft-appends`: drafting appends and never mutates).
- **Whether other tables want it too.** The same gap exists wherever one table takes rows from
  several sources. Build it here first, on the table with the incident.

**Price and legality.** A new optional column is minor-legal (P3, P8) and costs the full authored
price (P9), because a curator has to learn it. That cost is why it waits for a minor and a case,
rather than shipping with RM297.

## RM306 — no exon structure anywhere in the tier, and AlphaGenome's gene attribution wants one

**0.9, decided 2026-11-03.** The maintainer scoped 0.8 to the work already built, the chosen fixes and longevitymap v2, and moved everything else to 0.9. The status line below predates that decision.

**Severity** medium · **Status** open — **a minor, release undecided** (a second table in the MANE
lane) · **Owner** enricher (`mane_build`, `gene_spans`) · **Motivating case**
[GKS_SURVEY.md](probes/GKS_SURVEY.md) §5, 2026-09-28; the maintainer's ask for gene/exon coordinate
mapping behind the AlphaGenome lane

**What exists.** `gene_spans.py` reads the MANE *summary* for one span per gene, and its docstring
fixes the rule: a span is a query hint, never an attribution. Nothing in the tier knows an exon.
`grep -ri exon` over the enricher finds only `civic_identities.py`.

**The measured options, lightest first.**

| Option | Size | Covers | Misses | Licence |
|---|---|---|---|---|
| **MANE Ensembl GTF**, a second file in the existing MANE lane | 8.6 MB gz; 19,437 transcripts, 204,815 exons, CDS and UTR rows, `exon_number`, versioned ENSG/ENST, RefSeq xref | exon boundaries and numbers for MANE Select + Plus Clinical | non-coding genes; non-MANE isoforms | NCBI policy, already `MANE_TERMS` |
| **GENCODE v46 basic GTF** | 29 MB gz | the exact annotation AlphaGenome used, all biotypes | MANE selection, unless joined by ENST | "open access", no named licence (`@no-named-licence`) |
| cool-seq-tool + UTA + SeqRepo | 309 MB install, a UTA Postgres service, 13.5 GB SeqRepo | any transcript version, c.↔g. with exon offsets | nothing AlphaGenome attribution needs | UTA is CC BY-SA 4.0 |

The third is refused on weight, not on merit. It needs a database service and a 13.5 GB store, which
conflicts with the tier's `--offline` provisioning and with "builder in polars, runtime in duckdb".

**Release skew to state, not hide.** MANE 1.5 corresponds to Ensembl 116, while AlphaGenome was
annotated with GENCODE v46 (Ensembl 112). An exon boundary that moved between the two releases
attributes differently in each. The lane records both release labels, and a lookup answers in MANE's
frame by default.

**Open questions.** Is MANE alone enough (1–1.5 days), or does non-coding coverage justify a GENCODE
v46 lane too (about one more day)? And the answering surface: `gene_exons(symbol)` next to
`gene_span`, or a position → (gene, transcript, exon) lookup. The attribution rule in `gene_spans.py`
constrains both: an exon lookup answers *where*, and AlphaGenome's own per-record gene remains the
attribution.

## RM350 — HLA allele names are checked for grammar only; whether the allele exists is IPD-IMGT/HLA's list, and no lane reads it

**0.9, filed 2026-11-04 by the lead**: RM334's residual, placed in 0.9 by the maintainer's RM334 decision ("grammar now, the list in 0.9").

**Severity** low · **Status** open — **a minor**, 0.9, licence unprobed · **Owner** enricher (a new lane) · **Motivating case** RM334 · *related* RM334

RM334 refuses a malformed HLA name on `allele_function.csv`; a well-formed name that IPD-IMGT/HLA never assigned
passes. The list is the witness. Its terms are unprobed, so the first step is the licence probe
(`@probe-the-real-file`), then a lane through CACHE_SURFACE.md's checklist.

**Residuals** none yet.

## RM358 — a DOI-only literature answer is never pinned, and bioRxiv's own full-text route is unused

**0.9, filed 2026-11-04 by the lead**: RM349's two residuals, found by its builder.

**Severity** low · **Status** open — **a minor**, 0.9 · **Owner** enricher (`literature`) + compiler (the
`literature.csv` checks) · **Motivating case** the RM349 builder's report, 2026-11-04 · *related* RM349, RM336

**One class: a `pmid=NONE` citation is checked, but the answer goes nowhere a downstream check reads.** Two
instances:

1. RM349 checks a DOI-only row's existence and quote, but the answers are not pinned in `literature.csv`, which
   keys on PubMed ids. The compiler's quote counter, its licence check and its title-as-quote check read
   `literature.csv`, so none of them ever sees a `pmid=NONE` row.
2. The quote is matched only where Europe PMC holds the preprint's text. bioRxiv's own API publishes a `jatsxml`
   link for every bioRxiv and medRxiv preprint, a wider route than Europe PMC's subset, and no client reads it.

**The fix, as one rule.** A DOI-only answer is pinned in `literature.csv` under its DOI, so every check that reads
the table reads it too; bioRxiv's `jatsxml` becomes a full-text source for the quote check, as a new source with
its own `SourceRow` and licence probe, not a branch inside an existing client.

**Residuals** none yet.

## RM345 — `SourceRow` cannot state five licence shapes: AlphaGenome's four, and a host licence that defers to owners a row cannot name

**Severity** medium · **Status** open — **a minor** (new optional `sources.csv` columns or a sibling table;
authored layer, full cost under P9), design first, placed in 0.9 by the pm · **Owner** format + enricher ·
**Motivating case** RM333's Open Targets L2G read (`ROADMAP_0_8.md`) and `probes/ALPHAGENOME_ATLAS.md` §2.6 ·
*related* RM333, RM27, RM191, `@a-hosts-terms-are-not-its-contents-terms`, `@licensing-as-data`

**The gap.** `SourceRow` carries `share_alike`, `commercial_use`, `redistribution` (recorded, gated nowhere) and
`declared_use`. Five real licence shapes have no field:

1. **Holder eligibility** (AlphaGenome §2.1): "a commercial entity may not hold this at all" is not
   `commercial_use=False`, which only says the data may not be sold.
2. **A field-of-use bar** (AlphaGenome §2.4/4): no training of models on it, which binds a non-commercial lab too.
3. **Revocability with a delete obligation** (AlphaGenome §2.3): every source so far, at worst, stops being
   fetched. This one can compel deletion of derivatives already distributed, against P4's frozen digests.
4. **Notice of modification must travel** (AlphaGenome §2.4/5): `notice` carries the terms notice, but a
   threshold slice is itself a modification the terms ask to be declared.
5. **A host licence that defers to the original owners** (Open Targets, from RM333): data marked CC0, with "no
   restrictions other than those provided by the original data owners". `@a-hosts-terms-are-not-its-contents-terms`
   writes the host's terms as the floor and lets each record override them. An L2G row cannot name its owner,
   though: it reaches its study only through `studyLocusId`. So the override has nothing to key on, and the
   floor states less than the terms impose.

**Not decided here.** Whether each shape is a column, a vocabulary member on an existing axis, or a sibling
table. Which of them a compile gate reads, given that `redistribution` is still ungated (RM27). And how shape 5
says "deferred to owners not named per row" without claiming a value: a three-valued reading, where unknown is
withheld rather than written as permissive. AlphaGenome §2.6's (e) and (f) are existing gotchas, not gaps, and
are not reopened here.

**Residuals** none yet.

## RM294 — STRchive's evidence grade has no place in the module, so a Refuted locus is doubted only in a draft note

**0.9, decided 2026-11-04.** The maintainer chose one tier column with the scale declared per module, so a source's own grade cannot sit beside the module's tier. This item waits for 0.9, where a separate home for a source's grade can be weighed (a machine-written side table, or the manifest's provenance block).


**Severity** low · **Status** open — **a minor, release undecided** · **Owner** format / enricher ·
**Motivating case** RM276's minor half, split off when the warning shipped on 2026-09-27 · *related*
RM276, RM170, RM165

**For longevitymap v2 (2026-11-03):** a source's evidence grade travelling into a module is the same column family as RM324's tier. See [the group](ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

RM276 names a drafted locus STRchive grades `Refuted` or `Disputed`, in a note the drafting run prints
once. Nothing in the module keeps it, so the next reader of `repeat_alleles.csv` sees `DMD`'s bands
with no trace of the source's doubt. Carrying it is a minor: an authored column costs full price (P9),
and STRchive's vocabulary is open upstream (`combobox: true`), so a closed `frozenset` would have to be
priced against a source that adds members. The alternatives to weigh first are a derived sidecar
(half price) or the manifest's provenance block, and whether RM170's CIViC answer already fixed the
shape. Decide on the `0.8` branch.

## RM302 — one `conclusion` serves every place a report shows it; a table cell, a details card and an explanatory mode want different wordings

**0.9, decided 2026-11-04 by the maintainer, after the final measuring run.** v2 never uses the two registers, because its `conclusion` is already lay (R-VOICE-1), so they leave 0.8. The shape decided earlier the same day (two columns on four kinds, inside `content_signature`, and `language` reserved) stands for when the item is built.

**Decided 2026-11-04 by the maintainer: two optional columns, `conclusion_lay` and `conclusion_concise`.** They go on `VariantRow`, `DiplotypeRow`, `PharmVariantRow` and the bin kinds, but not `StudyRow`, because a study's finding is not the report's claim. Both are **inside `content_signature`**, as authored claim text. The name `language` is reserved now, as a separate axis from register. Tools never write a register; that was decided on 2026-09-27.


**Severity** medium · **Status** open — **a minor, release undecided**; principle decided, shape kept
open (see *Decided*) · **Owner** format (the authored models) + compiler (the parquet columns) ·
**Motivating case** the maintainer, 2026-09-27: a report shows a variant's conclusion in a table, in a details card and in
an explanatory mode, and one text cannot be right for all three · *related* RM7, RM28, the "not format
scope" note on lay-language rendering

**For longevitymap v2 (2026-11-03):** v2 writes for three readers (citizen, geneticist, ageing researcher), which is the register question. See [the group](ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

**The ask.** Today every annotation carries one `conclusion`, the detailed wording. The report needs up
to three **registers** of the same claim: **detailed** (today's text), **lay** (a simpler explanation for
someone without the background), and **concise** (scientifically accurate but very brief, for a table
cell). They are one claim written three ways, never three claims.

**Where `conclusion` lives today**, all authored: `VariantRow` (required), every `MeasureBinRow` kind
(required), `DiplotypeRow` (required), `PharmVariantRow` (required) and `StudyRow` (optional). It is
also inside `annotations.parquet`'s key, `(variant_key, conclusion, negatives)` (USE_CASES § the S-key
rework), which constrains every option below.

**What the charter already settles.**

- **Legal as a minor** (P3/P8): new optional columns or a new optional table. `conclusion` itself stays
  what it is and stays required; it becomes the *detailed* register by declaration, not by rename (a
  rename is a removal plus an addition, major-only).
- **Not in any key.** A register is a rendering of the claim the key already identifies. Keying on it
  would split one effect into several rows whenever an author adds a lay text, the dedup failure the
  annotations key exists to prevent.
- **Not the refused "lay-language rendering".** That note (§ Not format scope) is about *generating*
  patient prose from a CURIE, a presentation job. This is text a curator writes and signs, which is
  annotation data like `conclusion` is. The entry adds a line there so the two are not read as one.
- **Priced at full** (P9): every option is authored text, the most expensive layer. The argument for
  paying is that a consumer cannot derive a correct lay or concise wording from the detailed one
  without an LLM in the loop, which the charter keeps out of every tier.

**Decided by the maintainer, 2026-09-27.**

- **Tools never write a register; authors and curators may, if they see fit.** No drafter, enricher
  pass or compiler step fills, rewrites or derives a lay or concise wording, and none is required: a
  module with only `conclusion` is complete. This is the line the § Not format scope note on
  lay-language rendering draws from the other side.
- **Shape: kept open, with two columns as the default.** Unless something below changes it, the build
  is option 1: two optional columns on the carrying kinds.
- **The exception is meta-conclusions.** If [RM28](ROADMAP_0_8.md#rm28--meta-conclusions-the-predicate-half)
  lands its own table, the registers may belong there instead (a meta-conclusion is the claim a report
  most needs in lay words), and the two items then decide the shape together.

**Design options, as they stood before the decision.**

1. **Two optional columns on each carrying kind** (`conclusion_lay`, `conclusion_concise`, names to be
   audited under P5). Simplest to read and to author row by row; costs two columns on five kinds, and
   every future register is another column on all five.
2. **One optional side table** (`conclusions.csv`: the row's key, a closed `register` vocabulary, the
   text). One CSV, one concern: an author who writes no registers never sees it, a new register is a
   vocabulary member rather than a column, and the key is the carrying row's own. Costs a join for
   every consumer and a key per carrying kind.
3. **A register vocabulary with `detailed` implicit** either way, so `conclusion` never has to move.

**Open questions.**

- Which of the five kinds need registers. `StudyRow.conclusion` is a study's finding, not the report's
  claim, and may not.
- Does `content_signature` include the registers? They are authored claim text, so the default reading
  is yes; the counter-argument is that a lay rewording does not change what the module asserts
  (`@provenance-beside-a-claim-is-outside-content-identity` decides it).
- Language is a **separate axis** from register (P5: no overloaded fields). A lay text in German is
  register `lay`, language `de`; a design that folds the two into one vocabulary would have to be
  unwound when a second language arrives. Reserve the language axis's name now if it is expected.
- Does the reference consumer (just-dna-lite) need all three, or `concise` first? That orders the build.
- Should drafting ever fill a register? The house answer so far is that a provider fills facts, never
  prose; a register is prose.

## RM238 — a per-tissue eQTL has no row, and `expression_effects.csv` is the wrong table to widen

**0.9, decided 2026-11-04 by the pm seat, on the lead's build plan (PROPOSAL_0_8_PT2 §4 question 2).** The coloc input v2's effector confidence needs comes from Open Targets' `colocalisation` dataset, in RM333's lane under the same CC0 marking. So this per-tissue GTEx table goes back to waiting on a consumer: one lane and one licence instead of three sources, the maintainer's reduction rule.


**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half; PARKED on a consumer, deliberately** · **Owner** enricher · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *nine databases, and the two axes that come
back with no home*

**For longevitymap v2 (2026-11-03):** the cis-QTL colocalisation behind effector confidence E1/E2. See [the group](ROADMAP_0_8.md#longevitymap-v2--what-its-requirements-need-from-the-format-taken-into-08-as-a-priority-2026-11-03).

`clawbio.py run gwas --demo` on rs3798220 returns five cis-eQTLs **by named tissue** from GTEx and the
EBI eQTL Catalogue — `LPA` in Liver at β −0.82, in Adipose at −0.45, `SLC22A3` in Liver at +0.31.
Nothing here holds that. `expression_effects.csv` exists and is the wrong place: it is
AlphaGenome-shaped, one row per `(variant, gene)` **aggregating 371 tissue tracks** into
`tracks_agreeing`/`tracks_total`, and [`expression.py`](../schema/src/just_dna_format/expression.py)
argues at length that one row per track "is lossless and unreadable". A GTEx row is not a track — it
is a measured cis-eQTL in one named tissue with its own β and p, ~50 tissues rather than 371, and
**the tissue is the fact** rather than something to consensus over. Different grain, different source,
different terms. So: `eqtl_effects.csv`, one row per `(variant, gene, tissue, dataset)`, tissue as an
ontology term where the source gives one.

**This is filed open and parked, and the parking reason is a rule rather than a shortage of time.**
[USE_CASES § 7.2](USE_CASES.md#7-regulatory-effect--which-gene-a-non-coding-variant-moves-and-which-way-07)
closes with *"reopen this with a consumer, never with an argument"*, and a competitor rendering the
table is an argument. **Reopen it with somebody who needs the answer.** When that happens, the first
step is the acquisition measurement that correctly parked the frequency snapshot — what the GTEx and
eQTL Catalogue bulk artifacts weigh, and what their terms say (`@probe-the-real-file`).

**Related** RM188, RM194/RM200 (the AlphaGenome table this must not be folded into), USE_CASES § 7.2.
