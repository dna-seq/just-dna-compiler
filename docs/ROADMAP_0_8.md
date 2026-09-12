# Roadmap — 0.8 and later minors

**What this file is.** Items that are legal in a minor and were **not** taken into 0.7, each with the
reason it waits. It is the direct successor of `ROADMAP_0_7.md`, which was split out of
[ROADMAP.md](ROADMAP.md) on 2026-08-13 so that the active roadmap describes the line being built and a
deferral is filed against the release that will decide it, rather than accumulating in one document
nobody can read as a plan.

**Why it was renamed rather than kept.** 0.7 was built on 2026-08-28 and the file's name had stopped
being true: it read as the plan for a release that is finished, so an item in it looked shipped-or-late
rather than waiting. On 2026-08-31 the round it recorded closed —
[history/ROADMAP_0_7.md](history/ROADMAP_0_7.md) keeps that record, entries and all, including the
five taken back into 0.6 and the two that built in 0.7 — and everything still waiting moved here.
**Nothing about any item below changed in the move**; the file name did. Expect the same succession at
the next minor: the deferral file is named for the release that will decide its contents, so a cut
closes one and opens the next.

**What 0.8 is, decided 2026-09-11 with the maintainer: a stabilization and competitor-parity
release.** Stabilization is the first half — the items below are mostly a specified thing nobody
implemented (RM122), a prose behaviour two readers split on (RM149), a digest that says *something*
changed and not what (RM181) — and parity is the second, with **RM188 as its spine**: running
Calwbio's and genomi's pipelines on real input and re-folding what their reports do into module
mechanics is the mechanism that *files* the parity items, so most of them do not exist as numbers yet.

**The theme does not admit an item and does not reorder one.** Membership is still the rule in the
paragraph below — legal in a minor, waiting on a design question, a corpus or a caller — and legality
is still decided by Principles 3/4/8 first. A theme says what a release is *about* when it is cut and
what a reviewer weighs when two legal items compete for the same round; it is not a second gate, and
nothing below was moved, re-severitied or re-scoped to fit it.

Everything here is **additive under Principles 3/4/8** — a new optional column or table — so none of it
is waiting on a version. Each waits on a design question, a corpus, or a consumer. An item waiting on a
**version** belongs in [ROADMAP_1_0.md](ROADMAP_1_0.md) instead, and RM69 moved there on 2026-08-27 for
exactly that reason: filing by what a fix *costs* rather than by what decides it is how an item becomes
unreachable from either plan. **RM68 stays**, and the two look alike enough to be worth separating: its
governing exit is *a real author with a non-GRCh38 module saying which outcome they wanted*, and a
demand exit keeps an item here where a version exit does not.

**Two of these are not waiting on us at all.** RM84's own half shipped in the 0.6 PT2 batch and only
the consumer's discovery half is open; RM67 is **not work** — a documented divergence, numbered so it
stays findable and does not get re-probed. Both are here so that a reader meets the reasoning instead
of re-deriving it.

Indexed in [RM_TOC.md](RM_TOC.md), which is the complete list and the place to look an item up. The 0.6
decisions that touched these items are in [PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md) and
[PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md); the 0.7 round that emptied the rest is
[PROPOSAL_0_7.md](proposals/PROPOSAL_0_7.md).

---

## RM181 — a byte digest that moves beside intact signatures says something changed and not what, and provenance has no shift tracker

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

**Severity** medium · **Status** open — **round 1's two surveys filed 2026-09-13 and their findings
routed; round 2's roster is below, searched for rather than named** · **Owner** format (the survey),
then whichever tier the findings land in ·
**Motivating case** the maintainer's direction, not a consumer report

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
[RM28](#rm28--meta-conclusions-the-predicate-half)'s surviving *pairing across subjects* clause, and
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
| 2 | SNPedia, via [snappy](https://github.com/zhaofengli/snappy) | `2d5255f`, 52★, BSD-2-Clause; SNPedia content CC BY-NC-SA 3.0 US | the corpus round 1 never had | The largest curated variant-trait corpus in existence: **106,603 SNP entries** frozen into `data/snps.json` from a MediaWiki XML dump, plus `genotypes.json` (per-genotype magnitude / good-bad / summary) and `genosets.json`. Survey **the corpus, not the SPA** — snappy is the extraction route that proves a static dump works, where `OSGenome` (146★) only crawls live. **NC licence, so nothing here is adoptable as data**; the survey is about shape. |
| 3 | [BioMCP](https://github.com/genomoncology/biomcp) | `bb3a1d4ad7`, 630★, MIT | the agent-era tier done at scale | Thirteen times genomi's stars and the same architectural class. Ask the one question genomi could not answer at its size: **when an agent tool surface is the product, what does it end up needing to say about a variant that a table does not?** If the answer is "nothing", that closes the whole class and round 3 can skip it. |
| 4 | [Exomiser](https://github.com/exomiser/Exomiser) | `98f4e0b6f2`, 265★, AGPL-3.0 | phenotype-driven prioritization | The only established tool in the roster that **ships its annotation as a versioned data bundle** rather than fetching it — the closest existing thing to a compiled artifact. Ask what its bundle contains, how it is versioned, and how HPO term sets sit in it, given that [HPO ships no route here](ENRICHER.md) for licence reasons. |

### The three small ones worth a read after those

| Target | Pinned | Why |
|---|---|---|
| [dosedna](https://github.com/alejandro-publius/dosedna) | `530cfe7`, 2★, MIT | Hand-curated PGx over six genes, and the closest small analogue of our `haplotypes`/`diplotypes`/`pharm_variants` trio — plus a committed, provenance-stamped CPIC snapshot (`allele_definition` 39, `diplotype_phenotype` 666, `recommendations` 1,180). |
| [dna-engine](https://github.com/ShadowfetchLinux/dna-engine) | `5791bb3`, 0★, Apache-2.0 | **403 curated markers with the richest per-marker schema found anywhere**: `tier`, `effect`, `transferability`, `chips`, per-genotype label/impact/summary/detail/**actions**, and citations as `(pmid, note)` pairs. Also a deliberate non-interpretive posture — it refuses to translate genotype into phenotype, and says why. |
| [allelix](https://github.com/allelix/allelix) | `4b56bbe`, 30★, AGPL-3.0 | Carries no corpus, and is here anyway: **38 ADRs documenting source-precedence and suppression rules** (PharmGKB non-finding suppression, somatic-on-germline suppression, a GWAS odds-ratio magnitude modifier). Competing-source arbitration is `authority_precedence`'s problem, and this is the only project found that wrote its reasoning down. |

### What the skim already found — five axes, each sighted independently more than once

**This is the part that did not need a survey.** Convergence across unrelated projects is the
`@probe-uniform-corpus` heuristic firing: when three people who have never met each add the same
field, the field is answering a real question.

1. **Which genotyping arrays can call this variant** — three sightings: dosedna's `array_callable` + free-text `coverage_note` per gene, dna-engine's `chips` per marker, and `MrOrtiz/dna-annotator`'s measured-vs-imputed tiering per source array (it refuses to let an imputed call outvote a measured one). **We have nothing.** `requires_callable` / `callable_from` / `min_quality` ask whether the *consumer's own VCF* saw the position; this asks which *platforms in the world* interrogate it, which is a fact about the variant and therefore annotation. Note the per-gene / per-variant scope split, which is the shape [that already cost 39 variants once](ROADMAP_HISTORY.md).
2. **A per-variant claim's ancestry transferability** — three sightings: dna-engine's `transferability`, `Bluefinee/kaiseki`'s Japanese-cohort reconciliation, `drhudsonandrade/OmniGenis` recording discovery-cohort ancestry per GWAS association. We carry `PgsRow.training_ancestry` and `GwasEffectRow.ancestry`, both scoped to their own table; there is no way to say *this variants.csv row was established in one population*.
3. **Effect modified by a non-genetic factor** — two sightings, and genomi is the third: `sinhaankur/open-genome-atlas` splits each marker's evidence by `kind` (diet / lifestyle / geo), **each axis independently cited**; `drdaviddelorenzo/nutrigenomics` scopes its `weight` to a `nutrient_domain`; genomi's own caveat *"folate fortification status of the population modifies effect size"* is the same fact in prose. `CopyNumberRow`'s `modifier_gene` / `modifier_cn` is the precedent shape for a *genetic* modifier and there is no environmental one. Note that the second sighting also lands on `@weight-has-no-unit`: their `weight` at least names the domain it is a weight *in*.
4. **Two sources disagreeing, as a recorded verdict** — three sightings: kaiseki's `DISCORDANCE_RATIO`, which **refuses to publish a consensus frequency** when cohorts disagree; `Gunshipz/genomine`'s cross-tool confidence/disagreement layer; allelix's ADRs. `clin_sig_concordance.csv` does exactly this for clinical significance and **only** for clinical significance — kaiseki does it for allele frequency, where `frequencies.csv` has per-population rows and no verdict.
5. **A hand-assigned salience separate from clinical severity** — two sightings: `alexlaverty/dna-health-report`'s `magnitude` 0–6 per genotype, and SNPedia's own `m` field carried through snappy. `VariantRow.priority` is the candidate analogue; whether "priority level override" means the same thing is a question for the survey, not an assumption.

**And one that is not an axis but a corpus: [RM28](#rm28--meta-conclusions-the-predicate-half) has a third entry.** snappy's
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

**Security note, since the search surfaced it.** `Barrelsravennagrass984/Personal-Genome-Pipeline` is a
near-verbatim clone of `GeiserX/Personal-Genome-Pipeline` whose README is replaced with download bait
for a `.zip` committed inside the module tree. **Do not fetch or run it.** Recorded here because the
next person to run this search will find it in the same result set.

## RM236 — `consequence` and `impact` are planned axes with no slot, and an ACMG engine reads both as primary inputs

**Severity** medium · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s ClawBio half** ·
**Owner** format (schema + compiler), then enricher · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *the two columns their engine reads that we
cannot store*

[ROADMAP § Reserved namespace](ROADMAP.md#reserved-namespace) lists `consequence` (the VEP/Sequence
Ontology term) and `impact` (`HIGH|MODERATE|LOW|MODIFIER`) as *planned future annotation axes*, with
the rule that they "get a slot and a specific diagnosis only when a release actually commits to
building them". Nobody had committed, because nobody had a case. **The case is now in hand**:
ClawBio's `skills/clinical-variant-reporter/acmg_engine.py` is a running 653-line ACMG/AMP engine
whose per-criterion evidence table prints `consequence=frameshift_variant` for PVS1, `impact=HIGH`
for PM1, and `consequence=frameshift_variant, SpliceAI=N/A` for BP7 — three of its twelve implemented
criteria read a column this format cannot store, and a fourth reads the transcript the term was
called against.

**Get the mechanism right before touching anything.** Neither name is in `RESERVED_NAMES_0_4`, so
`reject_reserved` never claimed them and there is nothing to move out of a "built half": an author
writing `consequence` today gets the generic `extra="forbid"` message. Committing means one of two
things, and choosing is the first deliverable — **build the column**, or **add the reserved slot plus
a `vocab.RESERVED_NAME_REASONS` entry** so an author hears what the name is held for instead of the
stray-column message. The second is the honest outcome if the grain question below defers the build.

**The blocker is grain, and it is [RM23](#rm23--computational-predictor-scores-as-a-table)'s blocker
restated.** A variant has one consequence *per transcript*; `VariantRow` is one row per
`(variant_key, genotype)`. Three options:

1. **MANE Select only** — one value per variant, with `GeneMetricsRow.mane_select` naming the
   transcript it was called against. Cheap, lossy, and defensible only if the column's description
   says so in the field itself (`@field-description-is-a-claim`).
2. **Most severe across transcripts** — a ranking policy. That is an interpretation, so it is out by
   the same clause that keeps threshold-picking out of RM23.
3. **A derived `consequences.csv` sidecar** keyed `(variant_key, transcript)` — half cost under
   Principle 9, no authoring burden, and it is *the same shape RM23 needs*.

**Recommend (3), and settle RM23's grain in the same pass.** They are one question asked twice, and
answering it once is the whole saving; splitting them is how two sidecars end up with two different
answers to "which transcript". Do not build (1) as a stepping stone — a column shipped under a major
cannot be retyped into a table.

**Related** RM23 (same grain blocker, and the pass that should settle both), RM188.

## RM237 — ClinGen dosage is gene-keyed, so a recurrent-CNV region has nowhere to be written

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

## RM238 — a per-tissue eQTL has no row, and `expression_effects.csv` is the wrong table to widen

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half; PARKED on a consumer, deliberately** · **Owner** enricher · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *nine databases, and the two axes that come
back with no home*

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

## RM239 — a fine-mapping posterior has no column, and `gwas_effects.csv` already has its key

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s ClawBio half** ·
**Owner** enricher · **Motivating case** [`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) §
*nine databases, and the two axes that come back with no home*

The same `gwas-lookup` report returns three fine-mapping credible sets for rs3798220 with a posterior
probability and 95%/99% set membership per `(trait, study)` — PP 0.92 for Lipoprotein(a) in
GCST005140, 0.45 for aortic valve stenosis in GCST90038614 with 95% `No` and 99% `Yes`.

A posterior inclusion probability is the **same class of object as an allele frequency or a LOEUF**: a
number a named dataset publishes, no measurement by us, no inference by us. Its key is
`(variant, trait, study)`, which is `GwasEffectRow`'s key plus nothing — the row already carries
`trait_efo_id`, `study_accession` and `p_value_num`. So the cheap shape is **two optional columns on
the existing table**, `posterior_probability` and `credible_set`, minor-legal under P3/P8, and the
GWAS Catalog now publishes credible sets for its harmonised studies.

**Smallest item on the survey's list, and it should not be done on its own.** Do it the next time
`enricher/gwas.py` is open for another reason. Two things a design owes: whether `credible_set` is a
membership flag or the set's size/level (`95`/`99` are two answers to one question, and putting both
in one column is the `@field-description-is-a-claim` failure), and a withhold for a study whose
harmonised release carries no credible set, which is a nobody-asked third state and not a zero.

**Related** RM188, RM90 (the table this lands on).

## RM240 — the ClawBio nutrition panel compiles, and the corpus should carry it

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

## RM241 — `weighting` does not survive `reverse`, so a reversed module has no scale to read

**Severity** low · **Status** open — **filed 2026-09-13 from [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half** · **Owner** format · **Motivating case**
[`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *The translation, run*, last paragraph

`weight` is the one magnitude in this format with no unit beside it (`@weight-has-no-unit`), and RM92
built `module_spec.weighting` — `scale`, `method`, `note` — to be the place a module says what its
weights mean. It is **advisory, copied into the manifest, and not reconstructed by `reverse_module`**,
in the same class as `panel` / `authorship` / `license`. All of that is documented and, taken one field
at a time, defensible: it is not content, so it is correctly outside `content_signature`.

**The survey hit the consequence.** Translating ClawBio's nutrition panel forced an honest `weighting`
block to be written — their weights are hand-assigned importances *within* a nutrient domain, and
their scorer normalises by the weight of the SNPs it happened to find, so a domain score is comparable
only inside one domain of one run. That block is the single most useful sentence in the translated
module. `reverse` then drops it. So a consumer holding two **reversed** modules has two `weight`
columns and no way to learn that they are on different scales — which is the exact failure RM92 was
built to prevent, surviving in the one path RM92 does not cover.

**Three candidate dispositions, and this entry does not pick one.** (a) Nothing — write it in the
[FAQ](FAQ.md) as a known lossy field and let a consumer read the *original* spec, which is what
`reverse`'s own contract already says. (b) Carry `weighting` through `reverse` from the manifest,
which is where it already lives — cheap, and it changes what `reverse` claims to be. (c) Decide the
lossy set is right and that the real defect is that nothing *warns*, the way the dropped verification
attestation warns. **(c) is the most likely right answer** and is the cheapest to test: `reverse`
already emits one warning for a dropped attestation, so a second for a dropped `weighting` costs one
line and tells the author the thing they need to know at the moment it stops being true.

**Do not fix this by putting `weighting` inside `content_signature`.** It is prose about a column, not
the column; hashing it would make a reworded note move the digest, which is the defect
[FAQ](FAQ.md) already answers twice.

## RM164 — `heteroplasmy.csv` is a shipped table kind with no source behind it

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

**Severity** medium-large (on demand) · **Status** deferred — **considered for 0.6 on 2026-08-13 and
held** · **Owner** format (schema + compiler) · **Motivating case** authored-weight PRS modules

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

---

## RM28 — Meta-conclusions (the predicate half)

**Severity** medium (after the corpus) · **Status** parked on a corpus — **and halved on 2026-08-13**:
the injected-cofactor half closed, the predicate half stays here · **Owner** format (schema + compiler)
· **Motivating case** combination annotations; disclosure policy

**Read this entry knowing how much of the original item has already dissolved.** Probing in 0.5 removed
most of it, and the 0.6 review removed the rest of the cofactor axis. What is left is genuinely small
and genuinely unsolved.

**The corpus this was parked waiting for has its first real entry (2026-09-02, [RM174](history/ROADMAP_HISTORY_0_6.md#rm174--a-claim-about-two-variants-in-trans-is-written-as-two-single-variant-rows-because-no-brick-holds-the-real-subject)).**
Not an argument — an adopted source whose grammar was counted. CIViC publishes molecular profiles as
boolean expressions over variants: of 1,964 profiles, **209 are multi-variant** — `AND` 141, `OR` 72,
`NOT` 1 — and they nest (`BRAF Amplification AND ( BRAF V600E OR BRAF V600K )`). Both halves of this
entry's surviving case appear there, with instances:

* **Economy, and it is this entry's own phrase.** Evidence item 8721 is a claim about
  `VHL S183L AND VHL D126N` whose description reads *"heterozygous compound mutation"* — two variants
  **in trans**, observed, cited. `HaplotypeRow` cannot hold it: a haplotype is same-strand co-location,
  so drafting it there asserts *cis* where the source says *trans*, silently, because no column carries
  phase for anything to contradict.
* **Open-world negation.** `MET Amplification AND NOT KRAS Mutation` quantifies over a set no module
  can close, on a class term rather than an enumerable allele.

The 72 disjunctions are the half that is **already expressible** — rows are a disjunction — which is
where this entry drew the line and it holds. **This is evidence for the corpus, not a reason to
unpark**: one source, one observed trans instance, one negation. RM174 carries the measurement; the
decision stays here.

**Second corpus entry, 2026-09-13 — and it is a routine clinical guideline rather than an oncology
molecular profile.** From [RM188](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics)'s
ClawBio half ([`probes/CLAWBIO_SURVEY.md`](probes/CLAWBIO_SURVEY.md) § *pharmgx-reporter*). Their
pharmacogenomic report renders exactly one AVOID across 59 drugs, and it is **warfarin**, keyed
`"genes": ["CYP2C9", "VKORC1"]`. Our own `reference_examples/cyp2c9_warfarin_grch37/` carries the
CYP2C9 diplotype phenotypes in `diplotypes.csv` and the VKORC1 per-genotype claims in
`pharm_variants.csv`, **side by side, with nothing keying the pair** — which is this entry's surviving
"pairing across *subjects*" clause with a shipped module standing on it.

Three things make it sharper than the CIViC entry rather than a repeat of it:

* **It is the *drafter's* recorded gap, not an inference.** `pgx_draft`'s own comment says it:
  *"the guideline exists, it is a dosing algorithm over several genes rather than a per-phenotype
  recommendation, so nothing lands here and the author was told CPIC has nothing."* What shipped for it
  was a better **warning**, deliberately, not a table.
* **The competitor has no declarative form either.** ClawBio's answer is `"special": "warfarin"` — a
  hardcoded branch calling `get_warfarin_rec(profiles)`, for one drug out of 59. That is evidence the
  shape is genuinely hard, not evidence that everyone else solved it.
* **It is CPIC, so the population is countable.** The measurement this entry still wants, and the one
  cheap enough to do before any design: **how many CPIC guidelines are keyed on a gene *pair* rather
  than a single gene phenotype**, counted off the CPIC snapshot already provisioned. If the answer is
  three, this parks again with a sharper reason; if it is thirty, the economy argument changes.

**Third corpus entry, 2026-09-13 — and this one is a general-purpose grammar rather than a domain's
by-product.** From the same item's [round-2 roster](#rm188--the-competitor-survey--run-calwbios-and-genomis-pipelines-read-their-reports-and-re-fold-the-logic-into-module-mechanics):
SNPedia publishes **genosets**, boolean expressions over genotypes, and
[`zhaofengli/snappy`](https://github.com/zhaofengli/snappy) (`2d5255f`) has them extracted from a
MediaWiki dump into `data/genosets.json` beside 106,603 SNP entries. The grammar is
`and(rs4988235(C;C), rs182549(C;C))`, it nests, and a genoset may reference another genoset — the
haplogroup trees are built that way.

What makes it the sharpest of the three is that CIViC's profiles and ClawBio's warfarin branch each
fell out of one domain solving one problem, where **this grammar was written for consumer genetics in
general** and has been in use for over a decade. It is also the first entry where the *condition* side
and the *conclusion* side are both published, at scale, by one source.

**It changes no decision yet, and the reason is the same one that has held twice.** The measurement
this entry wants from it is cheap and has not been done: **how many genosets are there, what is the
operator distribution, and how deep does the nesting go** — counted off `genosets.json`, which is a
committed file needing no network. A corpus of forty flat conjunctions argues differently from four
thousand nested ones. Note also that SNPedia is **CC BY-NC-SA**, so this is evidence about a shape and
never data to adopt; and that `reference_examples/apoe_epsilon` already answers the two-variant case
without a predicate, which is the boundary any count has to beat.

Still **parked**, on the same rule: the corpus grows, the decision does not move until the count is in.

### What dissolved, so it is not re-proposed

- **No operator is missing.** Rows are a disjunction and columns are a conjunction, so the existing
  tables already span any finite boolean function over an enumerable set of genotypes: `OR` is two rows,
  `XOR` and bounded `NOT` are enumeration, and `haplotypes.csv` is same-strand `AND`.
- **APOE** — whose ε4 condition (`rs429358==C AND rs7412==C`) is the Constitution's own example of a
  predicate — was built with 0.4 bricks and **no predicate at all**
  (`reference_examples/apoe_epsilon/`). `HaplotypeRow` is a junction table, so same-strand co-location
  is what it already expresses.
- **The cis/trans motivation closed as a check, not a table.** `reference_examples/hfe_compound_het/`
  showed that a diplotype is already a statement about two homologs, so cis and trans are two rows —
  the relational notion the grammar was going to add is what a diplotype pair *is*. What building it
  surfaced instead was that the two rows are **indistinguishable without phase**, which shipped as
  `_cross_validate_phase_ambiguity` (a warning, never a block). A `requires_phase` column was rejected:
  it would make an author restate what the data determines and go stale the moment a haplotype is
  edited.

### What remains

- **Pairing across *subjects*** — no table keys on more than one.
- **Economy and intent** — "any two pathogenic variants in trans" over 300 of them is ~45,000 pairs:
  expressible, unwritable, unreadable.
- **Open-world negation** — "no pathogenic variant in this gene" quantifies over a set the module does
  not close, and absence is only assertable where the region was callable (`requires_callable`). No
  operator fixes this, and a negation feature ignoring it would **manufacture reassurance**, the worst
  failure mode this format has.

It also blocks the "shy module" signal.

### Why it stays parked

It waits on a corpus to generalize from — roughly 70% built; nutrigenomics and supplements do not exist
yet — because fixing a shape against four table kinds and then meeting the fifth is how a one-way door
gets spent badly (P3/P5).

The design thread, the starter shape and what is deliberately left open are in
[PROPOSAL_0_5.md § G3](proposals/PROPOSAL_0_5.md): a new **optional** table, a predicate that **never blocks**, a
grammar kept to the smallest thing covering the motivating case, and a **three-valued** algebra
(true/false/**unknown**, Kleene operators) — with `unknown` withheld, never reported and never negated.
Kleene matters concretely: a conclusion gated on "ε4 present AND QUAL ≥ 60" is decidably **false** at
ref/ref whatever the quality was, so a blanket withhold-on-any-unknown would be strictly worse than the
tables it replaces.

### The cofactor half — CLOSED in the 0.6 review, do not re-open as a general mechanism

The original item proposed **injected cofactors**: values the consumer supplies at query time that a
module must never hold, in three classes. Two of the three were resolved in 0.5 by making them **plain
columns** — clinical context became `DiplotypeRow.clinical_context`, call quality became
`quality_from` / `min_quality` (RM29) — and neither needed a general mechanism.

**Decided 2026-08-13: the general "injected cofactor" mechanism is dropped as never-earned.** Each
remaining class gets the same treatment — a plain column, on demand, one at a time. Two classes wait:

- **Ancestry** — a panel-scale inference, not derivable from a curated module's own gnomAD frequencies,
  since real models do not rely on single SNPs.
- **Family structure** — **this is RM10**, folded in here on 2026-08-13. A declarative trio / de-novo /
  Mendelian-consistency expectation is only meaningful once the consumer supplies family structure at
  query time, which makes it a cofactor class rather than its own item. Designing it separately would
  fix a shape for one class before the axis exists. It was on-demand-only and shapeless for its whole
  life; it stays that way, here.

Neither is built until a real module needs it.

---

# The VCF 4.4 items deferred out of 0.6

Numbered and triaged on 2026-08-13 from [VCF_4_4_AUDIT.md](probes/VCF_4_4_AUDIT.md); the rest of that cluster
(RM53, RM54, RM56–RM64, and RM65's comment fix) went into 0.6 — see
[PROPOSAL_0_6.md](proposals/PROPOSAL_0_6.md). The audit remains the evidence document: spec quotations,
`file:line` references and probe transcripts live there and are not duplicated.

## RM56 (policy half) — the rule for a measurement that spans bins

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

**Severity** medium · **Status** open — **a minor, release undecided; asked by the maintainer
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

**Severity** medium-high · **Status** **our half SHIPPED in the 0.6 PT2 batch (lane D, 2026-08-17)** —
`upload_module` writes `data/<name>/` and `data/<name>/v<version>/`. **The segment spelling is settled
and both asks are answered** ([S35](CONSUMER_SUGGESTIONS_HISTORY.md), 2026-08-17): `v<version>` verbatim
stays. Only the consumer's discovery half is open, and it is theirs, which is why this entry stays here.
*Previously:* our half taken into 0.6 PT2 on
2026-08-16 ([PROPOSAL_0_6_PT2.md](proposals/PROPOSAL_0_6_PT2.md) § RM84); before that, open — **joint with the
reference consumer, and their half is already agreed in writing** · **Owner** enricher
(`upload.upload_module`) + `just-dna-lite` discovery ·
**Motivating case** a republished module on the HuggingFace path

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
