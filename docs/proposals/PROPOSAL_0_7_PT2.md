# 0.7 PT2 design thread — six source-adoption items, and the probes that were supposed to come first

**What this is.** Stage 3 of the design cycle for the six items that were filed on 2026-09-01 as
*a minor, release undecided* and left there: RM163 through RM168. They arrived together, out of the
same source-adoption sweep, and they share a shape no earlier round had — **every one of them is
gated on a probe that had not been run.** Each entry says so in as many words, and each is careful
to assert nothing about its candidate's terms.

**Why this is a file and not six more addenda to [PROPOSAL_0_7](PROPOSAL_0_7.md).** That document's
RM152 addendum settled the rule that a closed proposal is closed against re-opening its own
decisions, never against recording a new one taken inside the same uncut release — and it is why
RM140 and RM152 sit there rather than here. Six items decided together against a shared sort rule
is a *round*, not an addendum, and [PROPOSAL_0_6_PT2](PROPOSAL_0_6_PT2.md) is the precedent for
giving a second round of the same line its own file. Nothing below re-opens any of the twelve.

**Status. Decided 2026-09-01 with the maintainer, and this file now wins over ROADMAP.** It was
drafted earlier the same day as material for that pass; the pass happened, item by item, and **four of
the six verdicts below are not the ones the draft proposed**. Where a per-item section still reads as a
proposal, the *Decided* line under this heading is the authority and the section's own release call is
the superseded draft.

| Item | Drafted | **Decided** |
| --- | --- | --- |
| RM163 PGS Catalog | BUILDS in 0.7.0 | **BUILDS in 0.7.0** |
| RM164 MITOMAP | PARKS to 0.8 | **PARKS — and the `mmutation` spin-off is filed as RM171** |
| RM165 STRchive | check half in 0.7.0, provider held | **both halves in 0.7.0** |
| RM166 ClinPGx drug labels | 0.8 | **taken, sequenced last** |
| RM167 LitVar2 | BUILDS in 0.8 | **BUILDS in 0.7.0** |
| RM168 MANE | BUILDS in 0.7.0 | **BUILDS in 0.7.0** |

**Three of the four overrides run the same direction — a probe that came back better than the entry
expected is a reason to take the item now, not a reason to feel safer deferring it.** RM165's provider
was held because a new `DRAFTABLE` lane "should not be rushed into an open cut", and the cut is open
precisely because nothing has been tagged; RM167 reversed from *closes* to *builds in 0.8* on the
strength of the allele-tier finding and then to *builds now* on the same strength; RM166's licence
motivation is gone but its cross-check is not, and sequencing it last is what the size argument
actually bought. RM164 is the one verdict the draft got right, and it is the one where the probe came
back worse.

**One decision this file did not anticipate, recorded here rather than discovered later.** The
*Shared-file hazards* paragraph below says none of these items touches `schema/`, and that **a diff in
`schema/` or `compiler/` means the item has grown past what this file decided.** Four of the five
passes attest, and `VALID_VERIFICATION_CHECKS` is a closed vocabulary in `just-dna-format` — so five
members land there, and the prediction is wrong rather than the items being overgrown. It is additive
and minor-legal (P3, P6), it costs zero on the authored layer (P9), and a published check name is a
one-way door, which is why the names were fixed before any of the passes were written rather than
minted by whichever landed first. The paragraph stands as a hazard list; this is its one recorded
exception. `compiler/` is still untouched, and that half of the prediction holds.

**Same convention as the two rounds before it**: each item records the problem in plain terms, **the
facts established while deciding it**, the proposed decision, the repairs rejected and why, and the
charter check. What is different is how much the facts moved: **five of the six entries say something
the probe contradicts**, and two of the six lose the premise they were filed under.

---

# The sort, and what did not do any of the sorting

**Legality decided nothing, again.** All six are enricher-only. Not one of them adds an authored
column, an authored table, a vocabulary member or a parquet column; the largest of them adds a cache
directory and a builder. Under Principles 3 and 8 every item here is additive and minor-legal, and
under Principle 9 every item here costs **zero** on the authored layer — the layer the cost amendment
actually prices. So the charter checks below are short, and that is a fact about this batch rather
than a shortcut.

**What sorted them is what the probe said**, in three outcomes:

1. **The probe confirmed the item, and cheaply.** Take it. RM168 is the clearest case — the entry
   scheduled three questions and the answers cost one directory listing and a 1.1 MB download.
2. **The probe overturned part of the item.** Take the part that survives, and *close the part that
   does not, in writing*, rather than leaving a refuted premise open. RM163 and RM166 are both this,
   and RM165 is this in the most useful direction: the source is better than the entry hoped on one
   axis and worse on another, and both are measured.
3. **The probe closed the route.** Say so and park. RM164's candidate cannot be fetched at all, and
   RM167's decisive test failed on the first call — the one the entry had scheduled a 423-locus join
   for.

**And one rule that is not about probes: six source adoptions do not all go into an uncut release.**
0.7.0 is bumped across three `pyproject.toml` files with `v0.6.6` as the last tag. Everything in this
batch is legal in it, and that is precisely why the release class cannot do the sizing — so the
per-item release call below is made on **size and blast radius**, not legality, and it puts three of
the six inside 0.7.0 and holds the rest.

**The maintainer pass kept the rule and moved the line: five of the six go in, one parks.** The rule
is that legality does not size a release, and it survives — what changed is the judgement it feeds,
because the cut is still open and each item is a self-contained lane in the tier that fetches. The
sizing that remains is **ordering**, not exclusion: RM168, RM163, RM165 and RM167 are built together
and RM166 — the largest, and the one whose motivation the probe removed — is sequenced behind them, so
if the cut has to happen early it is the one item still in flight rather than four.

| Item | Probe outcome | Proposed | **Decided** |
| --- | --- | --- | --- |
| RM163 PGS Catalog | confirmed; five corrections, incl. a **35 %-dense id space** that reshapes the message | **BUILDS in 0.7.0** | as proposed |
| RM164 MITOMAP / heteroplasmy | source **reachable**; the *axis* is the negative, measured on the real schema | **PARKS** to 0.8 | as proposed; spin-off filed as RM171 |
| RM165 STRchive / repeat alleles | confirmed on identity, **refuted on bands**; second candidate out on category | **BUILDS**, split — check half in 0.7.0 | **both halves in 0.7.0** |
| RM166 ClinPGx / the PGx licence class | licence half refuted; the real finding is **1 of ≥12 files read** | **SPLITS** — check in 0.8, licence half closes | **check taken now, sequenced last**; licence half still closes |
| RM167 LitVar2 / PubTator3 | premise **confirmed** once the allele tier was found; bounded on the hardest case | **BUILDS in 0.8** | **BUILDS in 0.7.0** |
| RM168 MANE | confirmed; **the source publishes its own staleness list** | **BUILDS in 0.7.0** | as proposed, and first |

**This table was written before the re-probe round and rewritten after it** — three rows said
something the second pass contradicted, which is `@a-record-written-in-two-passes-drifts-between-them`
happening inside the document that names it. It has now drifted a **third** time, in the maintainer
pass, which is why the *Decided* column sits beside the *Proposed* one rather than overwriting it: a
record of a decision that erases what was proposed cannot show that four verdicts moved. The per-item
sections below carry the reasoning; **the Decided column and the Status table are the release
authority**, and where a section's own closing *Release:* line disagrees it is the superseded draft.

---

# Decisions

## RM163 — `pgs.csv` is keyed on a Catalog accession and nothing ever asks the Catalog about it

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP_HISTORY.md § RM163](../ROADMAP_HISTORY.md#rm163--pgscsv-is-keyed-on-a-catalog-accession-and-nothing-ever-asks-the-catalog-about-it) — shipped, so the entry left the forward-only file

### The problem

`identifiers.py` asks three registries — dbSNP for `rsid`, OLS4 for `trait_efo_id`, HGNC for `gene`.
`pgs_id` is asked of nothing, so the one column `PgsRow` is keyed on is the one authored identifier in
the format that no pass checks.

### The facts, three of which change the entry

**The drift check is over two fields, not four.** The entry says `PgsRow` carries "four authored
copies of facts the Catalog itself publishes" and names `training_ancestry`, `training_cohort`,
`match_rate_floor`, `research_tier`. Reading the model rather than recalling it: `match_rate_floor` is
described in its own `Field` as *"Author-set variant-match floor"* and `research_tier` is a two-member
curator judgement (`research_only | calibrated`). **The Catalog publishes neither**, so there is
nothing to drift them against. Only `training_ancestry` (against `ancestry_distribution`) and
`training_cohort` (against `samples_training`) have a source-side value at all.

**The REST surface answers 200 with `{}` for anything it does not have.** Measured on
2026-09-01: `GET /rest/score/PGS000001` returns the full record; `GET /rest/score/PGS999999` — a
never-assigned id — returns **HTTP 200 and `{}`**; and `GET /rest/score/PGSXXXX`, which is not even a
well-formed accession, returns **HTTP 200 and `{}` as well**. So the status code carries no existence
information, a withdrawn score and a typo are indistinguishable *by construction*, and a malformed id
is indistinguishable from both. This is RM153's warning about a 200 that is not an answer, arriving
in a second source, and `@existence-not-identity` on top of it.

**The licence is per score, and it varies.** `license` is a field on the score record, not a property
of the Catalog. Over the first 250 of 6,982 scores: **242** carry the generic *"used in accordance
with any licensing restrictions set by the authors, see EBI Terms of Use"* string, **6** carry
*"Freely available to the academic community for research use"* — academic-use-only, which is the
class `licensing.py`'s own comment names as barring redistribution outright — and **2** are CC0 1.0.
A single `PGS_TERMS` constant would therefore be a **false claim** for 2.4 % of the sampled 250 — a sample rate, not a corpus floor —
and false in the permissive direction, which is the direction that matters.

**Re-probed 2026-09-01 after the first pass was found to have used two endpoints.** Three things it
had missed, and one of them corrects a decision below.

**The Catalog publishes its own release record, twice over.** `/rest/info` returns
`latest_release: {date: 2026-08-26, scores: 6982, publications: 834, traits: 809}` alongside the REST
API's own version (1.8.6), and `/rest/release/current` returns a full release with
`released_score_ids` enumerated. So the currency infrastructure this item wanted does not have to be
built — it has to be read, the same finding as MANE's `README_versions.txt` in RM168.

**`/rest/score/search` gives the trait→score direction**, paginated with a `count`:
`?trait_id=MONDO_0004989` returns 145 scores. `PgsRow` is keyed `(pgs_id, trait_efo_id)`, so this is
the key's other half served directly, and `/rest/trait/{id}` carries `trait_synonyms` and
`trait_mapped_terms` beside it.

**And the id space is sparse, which changes the message.** 6,982 scores across a range reaching
PGS019960 — about **35 % assigned**. A random sample of 40 well-formed in-range ids returned **12
assigned and 28 `200 + {}`**. So an unrecognised `pgs_id` is overwhelmingly a *never-assigned* id, not
a withdrawn one, and the first draft of this section was wrong to require the message to name both
readings with equal weight. `@rsid-absent-two-readings` earns that treatment because dbSNP's id space
is densely assigned and merges are a real, frequent event; here the base rate runs the other way, and
naming withdrawal as a co-equal reading would send an author looking for a retirement notice that
almost certainly does not exist. **State the absence, state the sparsity, and mention withdrawal as
the rarer reading rather than the equal one.**

### The decision

Three pieces, and the third is the one the probe forced.

**A fourth registry in `identifiers.py`**, asking the Catalog about each `pgs_id`. Because the API
cannot distinguish its own negatives — `200 + {}` for a never-assigned id and for `PGSXXXX` alike —
the check reads the *body*, never the status. The message states the absence and is **weighted by the
measured base rate**: two thirds of the id range is unassigned, so a typo is the likely reading and a
withdrawal the rare one, both named but not as equals. Where the Catalog offers no supersession field
at all, that is stated as a limit of the source rather than resolved by guessing.

**Currency comes from `/rest/info` and `/rest/release/current`**, not from a diff — the source
publishes the release date, the score count and the newly-released ids.

**A two-field drift check** in the `enrich_pgx` shape: `training_ancestry` against
`ancestry_distribution`, `training_cohort` against `samples_training`. Reports, never repairs
(`@enrichment-is-validation`); a drifted cell is the author's to fix or to answer in `overrides.csv`.
`match_rate_floor` and `research_tier` are **not** checked, and the reason is written down so nobody
adds them later: the source has no opinion to disagree with.

**Terms are read per score from the payload, not declared once in a constant.** This is the
`@licensing-as-data` shape already used for ClinPGx's bundled `LICENSE.txt`, and here it is not an
optimisation but a correctness requirement. A `PGS_TERMS` constant is still written — the
`GWAS_CATALOG_TERMS` shape, EBI's terms-of-use URL, gating axes `None` — but it is the **floor**, and
each score's own `license` string overrides it in the `SourceRow` for that score. A score whose
licence says *academic research use* must not compile into a module claiming the generic terms.

### Repairs rejected

- **Reading existence from the HTTP status.** It is 200 for a real id, a retired id, an unassigned id
  and a malformed one. Measured, not assumed.
- **One `PGS_TERMS` constant covering the source.** False for a measured minority, in the permissive
  direction. The Catalog is a *host* for scores licensed by their authors, which is the same shape as
  `@per-article-terms` and the same shape as the SpliceAI note already inside `GNOMAD_TERMS`.
- **Drifting all four columns.** Two of them are authored judgements the Catalog does not publish; a
  check with no source-side value is a check that cannot fail, which is `@tautology-zero`.
- **Widening this into RM16.** RM16 is authored per-variant weights and stays deferred on a missing
  consumer. The entry says so and this round does not touch it.

### Charter check

Enricher-only; no schema change, no authored column, no vocabulary member. P2 ✓ (the fetch is in the
only tier permitted one). P3/P8 ✓ (nothing added to the contract). P9: zero authored cost. The
three-valued rule does the work in two places — an unestablishable existence answer is `unknown` and
withholds, and the floor constant's gating axes are `None` rather than `True`.

**Release: inside 0.7.0.** One registry, one two-column check, one terms constant; no schema change.

**Decided 2026-09-01 — as proposed, and it attests under two names rather than one.**
`pgs_accession_currency` and `pgs_metadata_agreement` are separate members of
`VALID_VERIFICATION_CHECKS`: currency asks whether the id still names a score and drift asks whether
two cells beside it still match, which are different questions with different subjects and therefore
different denominators. Folding them into one record would publish a single findings count over two
populations. The "no schema change" line above is the one thing that did not survive — see the
exception recorded under **Status**.

---

## RM164 — `heteroplasmy.csv` is a shipped table kind with no source behind it

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP.md § RM164](../ROADMAP.md#rm164--heteroplasmycsv-is-a-shipped-table-kind-with-no-source-behind-it)

### The problem

Nine table kinds, providers for four. `heteroplasmy.csv` has none, no cross-check reads it, and the
corpus behind the kind is one module — `reference_examples/mt_heteroplasmy`, two MT-TL1 variants of
one gene, hand-authored from the literature. That is `@probe-uniform-corpus` exactly.

### The facts, read off the real schema

**The source is reachable, and two earlier drafts of this section said otherwise.** The maintainer
supplied `mitomap.org/downloads/mitomap.dump.sql.gz` — a 61 MB `pg_dump` of the whole MITOMAP schema,
dated 2026-08-24 — and plain `curl` fetches it: **HTTP 206, range requests honoured,
`application/x-gzip`.** The Cloudflare managed challenge is on the *web* surface only. What this file
first recorded as a refusal was a JavaScript interstitial, and what it then recorded as
"unreachable by the machinery that would consume it" came from probing `/downloads/` — the
**directory**, whose 199-byte Apache 403 is a listing denial — instead of a file one level down.
An enricher builder could fetch this today with `httpx` and no special handling. The lesson is
narrow and worth keeping: **a 403 is about the path you asked for, and generalising one to a source
is how two wrong findings get written from one lazy probe.**

**And with the schema in hand the axis question gets a measured negative, which is what the entry
actually asked for.** 95 tables. **Exactly one `tissue` column in the whole schema**, and it is on
`mitomap.unpublished` (16,537 rows) beside `patient`, `sample_id`, `ethnicity` and
`lab_chief_email` — a table of unpublished per-patient submissions, which is sample data and the one
category this format does not carry at all.

**The disease table has flags where the kind needs levels.** `mitomap.mmutation` is **602 rows**, and
its heteroplasmy columns are `homo` and `hetero` — *presence*, not fraction: `+` on 286/270 rows, `-`
on 216/238, `nr` on 90/89, plus `.`, `na` and NULL, which is four spellings of unknown in two columns.
There is no threshold column, no band, and no tissue. The only place in the table where a heteroplasmy
*level* appears at all is **two rows where somebody typed one into the flag column** (`homo=96%`,
`homo=99%`), which is a good illustration of the column not being for that.

**The only heteroplasmy numbers in the schema are re-hosted population data.**
`mitomap.gnomad` (18,164 rows: `ac_hom`, `ac_het`, `af_hom`, `af_het`, `an`,
`max_observed_heteroplasmy`) and `mitomap.helix` (14,104) are copies of two blood-cohort callsets. A
maximum heteroplasmy *observed* in a cohort is not a clinical threshold and is not per tissue — it is
the same shape gnomAD serves directly, which is why inheriting it here would add nothing.

So `HeteroplasmyRow`'s binding columns — `tissue`, `measure_min`, `measure_max` — have **no
source-side value anywhere in MITOMAP**. The entry's question 2 is answered, by reading the file
rather than by reasoning about the class, and the answer is no.

**Terms are still unread.** The dump contains no licence text of any kind; the only match in 6.7
million lines is a GenomeTools mention inside a cited abstract. MITOMAP's terms live on the website,
which a browser reaches and this probe did not.

### What the dump changes that is not RM164

`mitomap.mmutation` is 602 curated mtDNA disease variants with a confirmation status, and that is a
plausible **`variants.csv`** source — a different table kind, and not what this entry is about. It
would need work before it is a proposal: `status` is **29 distinct free-text strings**, not a
vocabulary — `Reported` 419, `Cfrm [LP]` 42, `Conflicting reports` 16, `Cfrm [P]` 16, and a long tail
of one-offs like *"Reported: individually neutral variants causing LHON in combination"* and
*"Reported; hg D1 D2 M33 R30 marker"* — so normalizing it is itself a curation decision rather than a
mapping (`@one-normalizer-two-spellings` at a scale where the rule stops being enough). It is filed
as its own item, with a number claimed from `.claude/rm-next.py` when it is taken, rather than
widening this one to keep it alive.

### The decision

**Park RM164, and now on a measured negative rather than a reasoned one.** `heteroplasmy.csv` stays
the kind with no source behind it, and after reading the canonical mtDNA database's full schema that
is a fact about what is published rather than about how hard anyone looked. The two hand-authored
MT-TL1 rows in `reference_examples/mt_heteroplasmy` are tissue-banded because a curator read the
literature and made a judgement; no table this probe found makes that judgement, and a drafting
provider cannot invent one.

Do not close it. The negative is now well-supported for MITOMAP specifically and for the population
callsets it re-hosts, which is the whole of the candidate field anyone has named — but a kind with a
one-module corpus should stay visible, and `@probe-names-the-table` is the reason the entry says
which table was read rather than "the source".

### Repairs rejected

- **Drafting identity columns only, from `mmutation`.** It would write rows filling
  `gene`/`variant_key`/`reference_sequence` and none of `tissue`/`measure_min`/`measure_max` — rows
  that say nothing the kind exists to say. The entry's own objection, and the schema confirms it.
- **Taking `max_observed_heteroplasmy` as `measure_max`.** A cohort maximum is an observation; the
  column is a clinical band. Same error as RM165's `pathogenic_max`, and worth naming twice in one
  round because it arrived from two unrelated sources.
- **Reading `homo`/`hetero` as a tri-state and calling that the axis.** They are presence flags with
  four spellings of unknown between them, and the kind binds a *level* per tissue.
- **Widening RM164 to cover `mmutation` as a `variants.csv` source.** A different table kind wants a
  different entry; keeping this one open by changing what it is about is how an item stops meaning
  anything.
- **Solving the Cloudflare challenge.** Never needed — the data surface was never behind it.

### Charter check

Nothing is built, so nothing is checked. Two things are worth recording anyway. MITOMAP's terms are
**unread**, not `None` — this probe did not open the page a browser opens, and the distinction is the
three-valued rule applied to our own knowledge rather than to the data. And `mitomap.unpublished` is
a reminder of the data-agnostic line from the other side: a source may hold per-patient sample rows,
and a module may not, whatever the terms say.

**Release: none.** Defer to 0.8 with the blockers restated.

**Decided 2026-09-01 — as proposed, and the spin-off is now a number rather than a paragraph.**
`mmutation` as a `variants.csv` source is **RM171**, claimed through `.claude/rm-next.py` at the moment
the item was taken, which is what the closing note below asked for. Nothing about `heteroplasmy.csv`
changed: it is still the kind with no source behind it, and the negative is still measured rather than
reasoned.

---

## RM165 — `repeat_alleles.csv` has no source, and RM65/RM66 have been waiting on exactly the corpus one would bring

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP_HISTORY.md § RM165](../ROADMAP_HISTORY.md#rm165--repeat_allelescsv-has-no-source-and-rm65rm66-have-been-waiting-on-exactly-the-corpus-one-would-bring) — shipped, so the entry left the forward-only file

### The problem

Same measurement as RM164 — no provider, no cross-check — but with two deferred items naming its
prerequisite. RM65 defers repeat coordinates *"waits on a real repeat-caller or CNV VCF sample, or a
consumer field report"*, and RM66 asks what to do when one locus has several motifs. A published
locus catalogue satisfies both, and satisfies RM66 better than a caller would, because a catalogue
publishes the motif structure as data where a caller emits it per sample.

### The facts, and this is where the probe paid

**STRchive is `dashnowlab/STRchive`, MIT-licensed, 82 loci across 79 genes, last pushed
2026-08-24.** `data/STRchive-loci.json` is 319 KB; hg38, hg19 and T2T BED files ship beside it. It is
the first candidate in this whole batch whose terms are **established and permissive** — an SPDX
identifier on a repository, not a policy page that declines to grant anything.

**It reproduces the hand-authored corpus, on one module exactly.** HTT: STRchive gives
`benign 6–26`, `intermediate 27–35`. The shipped `htt_repeat_expansion/repeat_alleles.csv` gives
`6,26` and `27,35`. Same numbers, independently authored. That is about as strong a validation as a
drafting provider can get before it is written.

**And it is one band coarser than the clinical convention, in the module where that matters.**
FMR1: STRchive gives `benign 5–44`, `intermediate 45–200`, `pathogenic 201–2000`. The shipped
`fmr1_cgg_repeat` module gives **four** bands — `5–44`, `45–54`, `55–200`, `201–2000` — and the
boundary STRchive does not have is **55**, the premutation threshold. The module's own conclusions
name what is lost: the 45–54 grey zone is *"the carrier is not at risk, but the allele may be unstable
in transmission"*, and 55–200 is the FXTAS/POF premutation range. Drafting STRchive's three bands
straight would erase a clinically load-bearing line in one of the corpus's two modules.

**And it would invent a ceiling in the other.** STRchive's HTT `pathogenic_max` is **250**; the
module leaves `measure_max` empty, i.e. unbounded. `pathogenic_max` in a catalogue is the largest
allele the literature reports, which is an observation, not a clinical bound. Drafted as
`measure_max`, a 300-repeat allele would match **no bin at all** — silently, `--strict` included,
which is the exact silence RM55 shipped a loud warning about (`@bin-grounding`).

**RM66's evidence exists, and it is 23 of 82 loci.** HTT's `locus_structure` is
`[{motif: CAG, count: null, type: pathogenic_repeat}, {motif: CAACAG, count: 1, type: interruption},
{motif: CCG, count: 12, type: flank_repeat}]` — the `(CAG)n(CAA)(CAG)` structure RM66 asks about,
published as typed data with its own three-member vocabulary. FMR1's is `[]`. So the corpus RM65 has
been waiting for is real, it is 28 % complete on the motif axis, and that is enough to *decide* RM66's
keying question and not enough to make the answer universal.

**One more, incidental and worth carrying**: `ref_copies` is fractional — HTT `21.3`, FMR1
`20.6667`. That is RM55's fractional-measure case appearing in a source rather than in a caller's VCF.

**Re-probed 2026-09-01, and the second candidate is disqualified by category rather than by terms.**
gnomAD's tandem-repeat release is real and fetchable — `gnomAD_STR_genotypes__2022_01_20.tsv.gz`,
34.6 MB on the public bucket — and its header settles it: `Id, LocusId, ReferenceRegion, Chrom,
Start_0based, End, Motif, IsAdjacentRepeat, Population, Sex, Age, PcrProtocol, Genotype, Allele1,
Allele2, …, ReadvizFilename`. **One row per sample per locus.** That is per-sample genotype data — the
one category this format does not carry at all — so the question of inheriting `GNOMAD_TERMS` never
arises. A negative on the category is cheaper and more durable than a negative on the licence, and it
is the second time in this round that a candidate's most detailed table turned out to be per-sample.

**Two STRchive fields the first pass walked past, and the first is the more important.**
`evidence` is a **ClinGen-style validity classification on all 82 loci** — Definitive 46, Limited 14,
Moderate 8, Provisional 6, Strong 4, **Disputed 3, Refuted 1**. This repo already models that axis
(`gene_validity`), and the `Disputed`/`Refuted` members are precisely the shape **RM170** is about — a
source that carries a claim and its contradiction. So STRchive is not only a repeat-locus catalogue;
it is a second instance of the problem RM170 was filed for, in a different domain, which is worth
knowing before RM170 is designed against CIViC alone.

**And it is a hub, not an island**: cross-references to gnomAD (72/82), TR-atlas (72), WebSTR (63),
STRipy (58), plus OMIM (78), MedGen (76), MONDO (72), Orphanet (69), GeneReviews (61) and
`inheritance` (80) and `mechanism` (78). Adopting it brings the joins to the rest of the repeat
ecosystem with it.

### The decision

**Adopt STRchive, and split it by column: draft the identity half, check the band half.**

*Drafts*: `chrom`/`start_hg38`/`stop_hg38`, `gene`, the motif and `locus_structure`, `ref_copies`,
and the disease identifiers (`mondo`, `omim`, `disease_id`) that join `trait_efo_id`'s registry.
These are facts the catalogue owns and the author would otherwise transcribe.

*Checks, and never drafts*: `benign_*`, `intermediate_*`, `pathogenic_*`. In **two of two** corpus
modules the source's tiling differs from the author's, in one by losing a boundary and in the other by
adding a bound that is not clinical. A cross-check reports both as findings against an authored table;
a drafting provider would write them as the answer. `@enrichment-is-validation`, decided by
measurement rather than by caution.

*Never emitted at all*: `pathogenic_max` as `measure_max`. It is a corpus maximum and the schema's
top band is open-ended for a reason.

**RM66 is not decided here.** The probe supplies the evidence RM66 was parked for; the keying change
it might justify is expensive, on a shipped table, and belongs to RM66's own pass with this data in
front of it. Naming the evidence and stopping is the whole of this round's obligation to it.

**RM65's attached obligation carries forward**: `_write_resolution_csv`'s positional pass hard-codes
`locus_index = 0`, honest only while these tables never expand, and repeat coordinates are exactly
what could expand one (RM87). Whichever half lands first, that stays on the item.

### Repairs rejected

- **Drafting the three bands straight.** Measured against both corpus modules and wrong in both, in
  two different ways.
- **Taking `pathogenic_max` as `measure_max` "because it is what the source says".**
  `@verbatim-except-order` is about not re-encoding a source's values; it is not a licence to import a
  bound the source did not intend as one. The band's meaning is the schema's, not the catalogue's.
- **Deciding RM66's keying in this round.** The entry asks for the evidence, not the decision.
- **Inheriting `GNOMAD_TERMS` for gnomAD's tandem-repeat release.** Moot, and for a better reason
  than the terms rule: the release is per-sample genotypes, so it is out on category before licensing
  is reached. The terms rule still stands — a different release is checked, never inherited — it just
  never gets a turn here.
- **Deciding RM170 against CIViC alone.** STRchive's `evidence` carries `Disputed` and `Refuted`
  members on a published corpus; RM170 should see that before it settles its shape.

### Charter check

Enricher-only; no schema change. P2 ✓. P3/P8 ✓ — a drafting provider writes existing columns of an
existing kind. P9: zero authored cost. P1 is worth naming because `locus_structure` looks like a
grammar: it is a typed list of `(motif, count, type)`, which is data, and nothing here proposes
evaluating anything.

**Release: the check half inside 0.7.0, the drafting provider held.** The cross-check is small and
reuses the binning machinery; the provider is a new `DRAFTABLE` lane with its own `SourceRow`, its
own placeholder guard and its own tests, and it is the kind of thing that should not be rushed into an
open cut. Maintainer's call, and the split is what makes deferring the larger half cheap.

**Decided 2026-09-01 — both halves in 0.7.0.** The split stands as a *design* — the band columns are
still checked and never drafted, which is the finding that made this item worth taking — and it is the
*deferral* that is overturned. Holding the provider assumed the cut was about to close; it is not, and
the argument for the split ("what makes deferring the larger half cheap") reads equally well as an
argument that the half is cheap. The two land as separate commits so the check is revertible without
the provider. The refusals below all survive: `pathogenic_max` is never emitted as `measure_max`, the
three bands are never drafted, and RM66's keying question is still not decided here.

---

## RM166 — the whole PGx lane is one licence class, and a second authority exists that is not in it

**Severity** low-medium · **Owner** enricher · **Entry** [ROADMAP.md § RM166](../ROADMAP.md#rm166--the-whole-pgx-lane-is-one-licence-class-and-a-second-authority-exists-that-is-not-in-it)

### The problem

CPIC, PharmVar and ClinPGx are all CC BY-SA + no-sale, so the entire PGx lane sits behind one gate and
no module built from it is sellable. The entry wanted two things from the FDA: a concordance check in
the RM134 § B shape, and a lane member whose terms may not gate at all.

### The facts — the first probe lands as the entry hoped, the second half does not survive

**`drugLabels.zip` exists on the same endpoint `clinicalAnnotations.zip` comes from.** Probed
2026-09-01: `https://api.clinpgx.org/v1/download/file/data/drugLabels.zip`, **59 KB**, created
2026-08-05, containing `LICENSE.txt` (CC BY-SA 4.0, read out of the payload by the machinery already
built for this source), `README.pdf`, `drugLabels.tsv` (**1,433 rows**) and `drugLabels.byGene.tsv`
(238 rows). So the entry's first question — *is this a second file from a source already adopted, or a
new source?* — resolves as **a second file from an adopted source**, which is the materially cheaper
of the two answers it named.

**It is five regulators, not one.** `Source` counts: FDA 533, Health Canada (HCSC) 388, EMA 332,
Swissmedic 128, PMDA 52. The entry asked for the FDA and the file supplies four more regulators at no
extra cost — which changes the concordance shape from *module ↔ authority ↔ authority* to a lane where
the number of authorities is a parameter, exactly what RM134's vocabulary split was built to survive.

**The join key exists, contra the entry's own closing worry.** `Genes` is populated on **1,248 of
1,433** rows (87 %), and `Variants/Haplotypes` on **217** (15 %) — 604 tokens, 189 distinct, of which
**415 are rsID-shaped and 178 are star-allele-shaped** (`CYP2C19*2`, `CYP2C9*11`, `CYP2B6*6`). Those
star tokens are `haplotypes.csv`'s key verbatim. So the entry's *"a check with no key to join on is
not a check"* is answered: there is a gene-level key for most rows and an allele-level key for a
sixth of them, and the sixth is where this lane's rows actually live. `Testing Level` is a five-member
ordinal claim axis — Testing Required 374, Actionable PGx 312, Informative PGx 162, No Clinical PGx
87, Testing Recommended 26 — with **472 rows stating none**, which is an absence and not a *no*.

**The licence half of the motivation is refuted, and by both routes.** The ClinPGx route is CC BY-SA
+ no-sale: the *same* gate, so it diversifies nothing. And FDA's own Table of Pharmacogenetic
Associations, probed directly, is **126 associations in an HTML page** (columns *Drug*, *Gene*,
*Affected Subgroups+*, *Description of Gene-Drug Interaction*) with **no CSV or XLS download offered
and no copyright or public-domain statement on the page at all.** So the direct route supplies a
quarter of the FDA content ClinPGx already carries, in a shape that has to be scraped, on terms that
are unestablished. *"US government work is public domain"* is a rule with exceptions, the entry said
so, and the page does not settle it.

**Re-probed 2026-09-01, and the item is larger than "a second file".** The first pass guessed at
filenames; enumerating properly against `api.clinpgx.org/v1/download/file/data/` (a 303 is a real
file, a 404 is not) finds at least **twelve** published archives — `clinicalAnnotations`,
`variantAnnotations`, `clinicalVariants`, `drugLabels`, `relationships`, `variants`, `genes`, `drugs`,
`chemicals`, `phenotypes`, `occurrences`, `pathways-tsv`. **`clinpgx_build` downloads one of them.**

`clinicalVariants.zip` is the one that bears on a shipped table kind: 74 KB, same `LICENSE.txt` and
`CREATED_2026-08-05.txt` shape, **5,190 rows** of `variant, gene, type, level of evidence, chemicals,
phenotypes` — star alleles and rsIDs against PharmGKB evidence levels, which is `pharm_variants.csv`
territory. Its `type` is a six-member base vocabulary that **comma-combines** (`Efficacy,Toxicity`,
`Efficacy,Toxicity,Metabolism/PK`), so it is one field carrying a set, and any adoption normalizes the
combination rather than the token — `@one-normalizer-two-spellings` with an extra axis on it.

So the honest restatement is that **the PGx lane reads one of twelve files from a source it has
already adopted and gated**, and the FDA question was a narrow way into a broad finding.

### The decision

**Split the item, take the half that is real, and close the other in writing.**

*Builds*: a `drugLabels.zip` builder beside `clinpgx_build`, the same cache and the same
payload-read licence handling, and a regulator-label cross-check in the RM134 § B shape — joining at
the star-allele level where `Variants/Haplotypes` supplies one and at the gene level otherwise, with
the two join tiers **distinguishable in the finding**, because a gene-level agreement and an
allele-level agreement are not the same claim. `Testing Level`'s 472 blanks are `unknown` and
withhold, never `No Clinical PGx`.

*Closes, measured rather than deferred*: **the lane does not gain a member outside its licence
class by this route, and the direct route cannot supply one either.** Leaving that half open would
leave an item riding on a source that has been shown not to serve it. If licence diversification for
the PGx lane still matters — and it plausibly does, since it is a single point of failure on the axis
the format gates on — it wants its own entry, with candidates chosen *for their terms first*, which
is the opposite of how this one chose.

### Repairs rejected

- **Ingesting the FDA table directly.** 126 rows, HTML-only, no stated terms, and ClinPGx already
  carries 533 FDA label annotations under a licence we can read out of the payload.
- **Treating the file as "the FDA source".** It is five regulators, and naming one in the surface
  would bake an authority into a name — the mistake RM134 caught in `ClinSigConflict` and had to fix
  before it shipped.
- **Reading a blank `Testing Level` as no clinical relevance.** 472 rows, a third of the file. Kleene,
  not a default.
- **Assuming ClinPGx's other downloads refresh in lockstep.** `clinpgx_build`'s own module docstring
  records that `relationships.zip` was a year newer than `clinicalAnnotations.zip`; `drugLabels.zip`
  carries its own `CREATED_*.txt` and gets its own `release.json` rather than the lane's.

### Charter check

Enricher-only; no schema change. P2 ✓. P3/P8 ✓. P9: zero authored cost. `@two-surfaces-two-denominators`
is the live rule — ClinPGx's bulk file and the FDA's web table are different sources with different
denominators, and any count either produces must say which.

**Release: 0.8.** A new builder plus a two-tier cross-check is the largest item in this batch, and it
is the one with the least urgency behind it now that its licence motivation has gone.

**Decided 2026-09-01 — taken now, sequenced last.** *Largest in the batch* and *least urgent* are an
argument about **order**, not about the release: they say build it after the other four, which is what
happens. The half that closes still closes — the lane gains no member outside its licence class by this
route — so what is being built is the cross-check alone, on its own merits, with the licence motivation
gone rather than replaced. If the cut has to happen before this lands, this is the one item still in
flight, which is the whole benefit the size argument was reaching for.

---

## RM167 — LitVar2/PubTator3 answers "which papers name this allele", which is the half PubMind structurally cannot

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP.md § RM167](../ROADMAP.md#rm167--litvar2pubtator3-answers-which-papers-name-this-allele-which-is-the-half-pubmind-structurally-cannot)

### The problem

[PUBMIND_ASSESSMENT](../PUBMIND_ASSESSMENT.md) measured that PubMind has *record* identity, not
variant identity — 68,744 coordinate keys carry more than one PVID, the worst carries 35, HFE C282Y
alone holds eight with four different verdicts. The entry proposed LitVar2 as an independent second
vote on exactly that fan-out, and set the test itself: *"They are complements if LitVar's identity is
genuinely allele-level where PubMind's is record-level."*

### The facts — the entry's test passes, and the first draft of this section failed it by misreading an id

**The id grammar has slots, and `##` is an empty one.** A LitVar id is
`litvar@<clingen_id>#<rsid>#<gene_id>`, with unfilled slots collapsing to a bare `#`. So
`litvar@rs1800562##` is the **position** node — rsID slot filled, allele slot empty — and
`litvar@CA113795#rs1800562##` is the **allele** node beside it. `variant/search/gene/HFE` returns all
three tiers together: of 588 HFE nodes, **220 are rsID-only, 69 carry a CAID, and 299 are gene-level**
(`litvar@#3077#`, NCBI GeneID 3077 = HFE, 3,285 PMIDs). The `flag_rsid_variant` /
`flag_clingen_variant` / `flag_gene_variant` booleans say which tier a node is.

An earlier draft of this section read the trailing `##` as a suffix on an rsID, queried only
`variant/autocomplete`, and concluded the source has no allele tier at all. It has one, it is a
separate node, and `autocomplete` returns whichever tier matches the query — `?query=CA123643`
returns `litvar@CA123643#rs113488022##` with `flag_clingen_variant: true`.

**The allele nodes answer differently, and the entry's test is what they pass.** Measured
2026-09-01, BRAF rs113488022 — three CAIDs which the ClinGen Allele Registry resolves to three
distinct ALTs at one position, `A>T` p.Val600Glu, `A>G` p.Val600Ala, `A>C` p.Val600Gly:

| node | PMIDs |
| --- | --- |
| `litvar@rs113488022##` (position) | 32,095 |
| `litvar@CA123643#…` V600E | 31,276 |
| `litvar@CA281998#…` V600G | 99 |
| `litvar@CA16602736#…` V600A | 41 |
| on the position node and **no** allele node | 801 |

That is allele-resolved literature, and the resolution is doing real work: the three alleles of one
codon differ by three orders of magnitude. **RM167's own complement test — *"complements if LitVar's
identity is genuinely allele-level"* — passes.**

**But the tier a locus is answerable at is a property of the locus, not of the source.** The same
measurement over two more:

| locus | position node | allele node(s) | position-only |
| --- | --- | --- | --- |
| BRAF rs113488022 | 32,095 | 31,276 + 99 + 41, 3 CAIDs | 801 (2.5 %) |
| HFE rs1800562 | 3,053 | 2,693, 1 CAID | 360 (12 %) |
| APOE rs429358 | 3,945 | **328**, 1 CAID | **3,617 (92 %)** |

APOE is the case that matters: the position carries 3,945 papers and its single allele node carries
328, so **92 % of the literature at that locus is not allele-resolved**. A pass that reported the
allele node's count as *the* answer would understate APOE by twelvefold. Allele-resolved,
position-only and absent are three outcomes, and this is the house algebra arriving from a source
rather than being imposed on one.

**The allele identity is a CAID, which this package already resolves.** RM153 shipped
`clingen_allele.ClingenAlleleClient` and an `identity_derivation="caid"` snapshot row on 2026-08-31.
The join from a LitVar allele node to a module's `variant_key` is machinery that exists, which makes
this materially cheaper than the entry assumed.

**Two corrections to this file's own earlier draft, and one that survives.** The verdict channel is
**position-level only**: `data_clinical_significance` is populated on position nodes (rs429358 carries
eight labels) and is `None` on every allele node measured. So the entry's *"carries no pathogenicity
verdict"* is still wrong, but the verdict is not per-allele and is therefore not adoptable as an
allele authority — which is the same conclusion by a better route. And PubTator3's
`entity/autocomplete` name/id mismatch stands as measured.

**One real API defect, worth pinning before anyone writes a client.**
`variant/search/gene/GENE_NAME` returns **line-delimited Python `repr()`, not JSON** — single-quoted
keys, one dict per line. `httpx`'s `.json()` raises on it. The other four endpoints return proper
JSON. `@probe-the-real-file`, and the reason a builder for this needs a parser rather than a
deserializer.

**Terms are NCBI's policy, and a policy is not a licence.** NCBI states it *"places no restrictions on
the use or distribution"* of molecular data and, in the same passage, that it *"cannot provide comment
or unrestricted permission concerning the use, copying, or distribution"* because submitters may hold
rights it cannot assess. ClinVar escapes this via its own `maintenance_use` page, which is why
`CLINVAR_TERMS` says `public-domain`; LitVar has no such page. Under `@no-named-licence` the gating
axes are `None`. **NCBI's side only** — this probe did not read EMBL-EBI's terms for the surfaces EBI
co-hosts.

### The decision

**Reversed from this file's first draft: RM167 BUILDS.** The entry set a test, the test passes, and
the earlier "closes" verdict was an artefact of querying one endpoint and misreading an id.

**A literature-coverage pass keyed at the tier the locus supports, with the tier recorded.** For each
module rsID: resolve the allele node via the CAID that RM153's registry client already returns for the
module's `variant_key`, take that node's PMIDs when it exists, and fall back to the position node —
**never silently.** The finding names which tier answered, because 328 and 3,945 are both true
statements about rs429358 and only one of them is about the allele in the module. Three outcomes,
Kleene, and the position-only residue counted rather than discarded (`@dont-discard-computed`).

**What lands in an artifact is still open, and deliberately.** A PMID list per variant is not a table
kind and `literature.csv` is keyed by article. Whether this becomes a `studies.csv` drafting provider,
a coverage signal, or a check that writes no row is the implementation's call; the entry's
pre-authorisation stands — *"an enrichment surface that reports and writes no row is a legitimate
outcome and should not be designed away."*

**`data_clinical_significance` is not adopted in any form.** Position-level, unattributed, undated,
and eight labels on a position where two alleles disagree.

### The bound, tested on the hardest case in the repository

RM167 must not be sold as an identity-recovery tool, and the way to know that is to run it on the two
records this workspace could not resolve. [CIVIC_LEGACY_INSERTIONS](../probes/CIVIC_LEGACY_INSERTIONS.md)
works CIViC 1955 (`VHL P71fs (c.211insT)`) and 2131 (`VHL Q73fs (c.214insGCCC)`) down to four
candidate alleles with registered CAIDs. Asked of LitVar, 2026-09-01:

| asked | answer |
| --- | --- |
| CA2586965638, CA2501268513, CA2573048346, CA2499307076 | **no node for any of the four** |
| `c.211insT`, `211insT`, `c.214insGCCC` | **no node** |
| `VHL P71fs` | one node — `litvar@#7428#p.P71fsX`, **1 PMID: 19996202** |

**None of the four source papers.** Not Olschwang 1998 (9829912), not Dollfus 2002 (12202531, the
free-fulltext lead §5 names), not Ong 2007 (17024664), not Maher 1996 (8730290). The one nominal hit
is an unrelated paper that happens to write "P71fs" — `@existence-not-identity`, and a fifth id shape
besides: `litvar@#<gene_id>#<protein_name>`, all three `flag_*` false, an unnormalized text mention
rather than a variant.

**And the reason is structural, which is what makes it a bound rather than a gap.** PubTator3's
export for all four papers returns **title and abstract only** — 2 passages, 14–33 disease/gene/species
annotations, and **zero variant annotations in every one**. None is in the PMC open-access subset;
Maher 1996 has PMC1050584 and the OA BioC endpoint still refuses it. The alleles live in *Table 3 of a
paywalled 1996–2007 paper*, and text mining over abstracts cannot reach a table.

That is the same wall §8 of that document went around, and it went around it through **UMD-VHL's
curated protein column** — a curator's tabulation, one step from the primary. LitVar indexes text.
**So on precisely the class this workspace built a protocol for — a source that names a variant
without identifying it, in old literature — LitVar is the wrong instrument, and the build must say
so.** It answers *which papers discuss an allele that is already identified*; it does not answer
*which allele this name meant*. Those read as the same question and are not.

### Repairs rejected

- **Closing the item, as this file first proposed.** The premise was sound; the probe was not. Reading
  `##` as a suffix instead of an empty slot, and asking only `autocomplete`, produced a confident
  negative about a tier that is one endpoint away.
- **Reporting the allele node's count as the locus's answer.** It understates APOE twelvefold. The
  tier that answered is part of the finding, not an implementation detail.
- **Falling back to the position node silently.** Same defect, quieter. `@refutation-withholds` — a
  position-level answer to an allele-level question withholds, it does not answer approximately.
- **Taking `data_clinical_significance` as a fourth authority for the concordance check.** Position-
  level, unattributed, undated, and `None` on every allele node — so it cannot even be attributed to
  the allele it would be voting on.
- **Calling `.json()` on `variant/search/gene/`.** It is line-delimited Python `repr()`. Pinned here
  so it is found before a client raises on it.
- **Recording NCBI's policy as `public-domain` by analogy with ClinVar.** ClinVar has a page saying
  so and this surface does not. `@no-named-licence`, and the analogy is exactly the move the rule
  forbids.
- **Selling it as identity recovery.** Measured against the two hardest records in the repository and
  it returns nothing for any of the four candidate alleles. The bound is above.
- **Still not running the 423-locus join to decide the item.** It is the right measurement for
  *coverage* — how many module loci have a CAID node at all — and it is the implementation's first
  test. It was never the right measurement for *identity*, which four requests settled.

### Charter check

Enricher-only; no schema change decided here, and the "writes no row" outcome stays available. P2 ✓ —
the fetch is in the only tier permitted one. P3/P8 ✓. P9: zero authored cost. The three-valued rule
decides the shape, and for once the source supplies the three states rather than the schema imposing
them: allele-resolved, position-only, absent.

**Release: 0.8.** It reverses to a build, but it is a new client plus a tiering rule plus an undecided
artifact question, and the coverage measurement over the 11-module corpus is its first task rather
than a prerequisite that is already done.

**Decided 2026-09-01 — 0.7.0.** The deferral rested on three things and none of them is a release
blocker. The *client* is small and the id grammar is fully mapped above, down to the endpoint that
returns Python `repr()`. The *tiering rule* is the item's finding, not an unknown — allele-resolved,
position-only, absent, with the tier named in the finding. And the *undecided artifact question* is
already answered in the permissive direction: the entry pre-authorised a surface that reports and
writes no row, so an item that lands as exactly that is complete rather than half-done. The coverage
measurement stays the build's first task, as written. The bound above is not softened by taking the
item sooner — it ships **with** the pass, in the pass's own documentation: LitVar answers which papers
discuss an already-identified allele, and the two CIViC legacy insertions are the worked proof that it
does not answer which allele a name meant.

---

## RM168 — the identity procedure downloads MANE by hand, and nothing in the code knows the file exists

**Severity** medium · **Owner** enricher · **Entry** [ROADMAP_HISTORY.md § RM168](../ROADMAP_HISTORY.md#rm168--the-identity-procedure-downloads-mane-by-hand-and-nothing-in-the-code-knows-the-file-exists) — it shipped the same day and left the forward-only file

### The problem

[CIVIC_IDENTITY_PROTOCOL](../probes/CIVIC_IDENTITY_PROTOCOL.md) § 3b pins a numbering frame with
`MANE.GRCh38.v1.5.summary.txt.gz`, *"downloaded once and cited"*. Every other reference table this
workspace leans on is a cache with a location and a recorded release. MANE is a sentence in a probe
document.

### The facts — the entry asked three questions and all three are cheap

**`current/` is not opaque, twice over.** The directory listing carries the version in **every
filename** (`MANE.GRCh38.v1.5.*`), versioned siblings `release_1.5/` back to `release_0.5/` exist so a
pin is a URL rather than a hope, and `README_versions.txt` is **96 bytes** publishing exactly the
provenance triple a `release.json` wants:

```
MANE Version	1.5
NCBI RefSeq Annotation Release	GCF_000001405.40-RS_2025_08
Ensembl Release	116
```

**The download is 1.1 MB.** `MANE.GRCh38.v1.5.summary.txt.gz`, dated 2025-12-04, 19,437 rows, 14
columns. It is the smallest reference this workspace would cache by an order of magnitude.

**The CDKN2A case is in the table and is visible by column.** Two rows for GeneID:1029 —
`NM_000077.5` / `ENST00000304494.10` marked **MANE Select**, and `NM_058195.4` / `ENST00000579755.2`
marked **MANE Plus Clinical**. `MANE_status` has two values across the file and **only 74 of 19,437
rows are MANE Plus Clinical** (0.38 %). That number is the argument: a case that occurs in a third of
a percent of genes is precisely the case a remembered accession hides and a table shows.

**RUNX1 is a single row, and that confirms the protocol rather than fixing it.** `NM_001754.5`, MANE
Select, and nothing else. The 27-residue RUNX1c/RUNX1b offset that § 3b derived by translating each
isoform's CDS is **not** in MANE and cannot be. So *"MANE is the default, not the answer"* is now
measured: the table makes the CDKN2A class of problem visible and is silent on the RUNX1 class, and a
pass that treats it as an oracle would be wrong in a way the file itself cannot warn about.

**It is also a cross-map.** The summary carries `NCBI_GeneID`, `Ensembl_Gene`, `HGNC_ID`, `symbol`,
both RefSeq and Ensembl nuc/prot accessions, and GRCh38 gene coordinates — adjacent to
`identifiers.py`'s HGNC registry and to the Ensembl lane, and worth noting before somebody builds a
second gene cross-map beside it.

**Terms: NCBI publishes a policy, not a licence** — the same finding as RM167, and for the same
reason. `license=None`, `license_url` at the policy, the two operative sentences in `notice`, gating
axes `None`. MANE is a joint NCBI/EMBL-EBI product and **only NCBI's side was probed here** — EBI's
terms for it were not read, and this file asserts nothing about them.

**Re-probed 2026-09-01, and the file that answers this item's own complaint was in the directory
listing all along.** The entry's objection is *"a version pinned in prose that nothing will notice
going stale."* MANE ships the staleness list: **`MANE.GRCh38.v1.5.changed_select_accessions.txt.gz`,
3.6 KB, 120 rows**, columns `NCBI_GeneID, Symbol, Current_MANE_Select_RefSeq,
Current_MANE_Select_Ensembl, Current_MANE_Version, Old_MANE_Select_RefSeq, Old_MANE_Select_Ensembl,
Old_MANE_Version, Update_Affects_CDS`.

**`Update_Affects_CDS` is the numbering-frame axis, stated by the source, and it is `Yes` on 74 of
120.** A MANE Select change that moves the CDS moves every `c.` and `p.` derived in that frame; one
that does not, does not. This item exists because a numbering frame was recorded in prose — and the
currency check for it turns out to be *read one small file*, not *diff two releases*. `Old_MANE_Version`
spans 0.5 through 1.4, so each row also says how long that gene's frame had been stable.

**The negative roster is published too.** `protein_coding_genes_not_in_mane.txt.gz` lists **222**
genes with a reason, over a seven-member vocabulary: `gene not on assembled chromosomes` 158,
`non-coding allele on assembled chromosomes` 19, `gene located on mitochondrial genome` 13, `gene in
false duplication region` 11, `genome error on assembled chromosomes` 9, **`pending MANE review` 8**,
`gene undergoes ribosomal slippage` 4. So *"MANE has no answer for this gene"* is distinguishable from
*"nobody asked"*, with the reason attached — `@unreachable-not-absent` served by the source. And
`pending MANE review` is a third state on its own: not absent, not decided.

**It answers the protocol's own worked case.** VHL is `NM_000551.4` / `ENST00000256474.3`, MANE
Select — the exact transcript [CIVIC_LEGACY_INSERTIONS](../probes/CIVIC_LEGACY_INSERTIONS.md) pins by
hand, and the version half of the recorded asymmetry (Variant Recoder rejects `NM_000551.3`, accepts
`.4`). RUNX1, CDKN2A and VHL are all **absent from `changed_select_accessions`**, so their frames have
been stable — which is a positive statement the cache can make and a memory cannot.

**Note for RM164 while it is in view**: `gene located on mitochondrial genome` is a MANE exclusion
class, so the mtDNA lane has no MANE frame by construction.

### The decision

**Promote MANE from a sentence to a source.** `MANE_TERMS` in `licensing.py` with the axes above; a
`default_mane_cache_dir` and `resolve_mane_reference` in `locations.py`; a builder that takes the
1.1 MB summary to a parquet with `release.json` written from `README_versions.txt` — the source
publishes its own provenance and the builder should copy it, not restate it. Pin by the versioned
directory, not `current/`, and record which was used.

**Three files, not one.** The summary, `changed_select_accessions` (the currency check, free) and
`protein_coding_genes_not_in_mane` (the reasoned negative roster). Together they are under 1.2 MB.

**`MANE_status` is carried as a column and never collapsed.** The 74 MANE Plus Clinical rows are the
whole reason this is a table; a builder that kept one row per gene would reintroduce the exact blind
spot the item is about.

**Scope is held where the entry put it.** This is a transcript-identity aid. Generating `c.`/`p.`
notation is a separate deferred feature with its own unanswered questions, and nothing here proposes
it. The recorded asymmetry stays attached: Ensembl's Variant Recoder rejects `NM_000551.3` while
accepting `.4`, so which version a pass submits is a real decision and the cache is what makes it a
recorded one.

### Repairs rejected

- **Pinning `current/`.** It moves. The versioned directories exist and the filenames name the
  version; pinning the mutable path and hoping is what the item is complaining about.
- **Deriving the release from the filename.** `README_versions.txt` is 96 bytes and states the RefSeq
  annotation release and the Ensembl release too, neither of which is in any filename. Parsing a name
  to reconstruct less information than the source hands over is `@probe-the-real-file` backwards.
- **One row per gene.** Would drop 74 rows and hide the only case the table can see that a memory
  cannot.
- **Recording it as public domain.** Same rejection as RM167 and the same reason.
- **Letting it grow into HGVS generation.** Named here so the scope line has a matching refusal.

### Charter check

Enricher-only; no schema change, no authored column. P2 ✓ — the fetch is in the network tier and the
compile path never imports it, which is also what keeps RM159's 33 shipped identity answers offline
and byte-reproducible while their *frame* becomes readable. P3/P8 ✓. P9: zero authored cost.
`@release-json-provenance` is the live rule and the source cooperates with it.

**Release: inside 0.7.0.** One 1.1 MB file, one builder, one terms constant, no schema change — and it
is the numbering frame RM159's answers were derived in, which is the argument for not letting it sit
in another release as prose.

**Decided 2026-09-01 — as proposed, and first.** It depends on nothing else in the batch and the
identity protocol depends on it, which is the ordering the implementation section below already
argues.

---

# One pattern that showed up three times

**A source's most detailed table is often per-sample, and per-sample is the one thing that cannot be
adopted.** MITOMAP's only `tissue` column is on `mitomap.unpublished`, beside `patient` and
`sample_id`. gnomAD's tandem-repeat release is `Genotype`/`Allele1`/`Allele2`/`Sex`/`Age`, one row per
sample per locus. PubMind's per-variant channel was already known to be the ANNOVAR bulk table for
related reasons. In each case the richest file is the one the format is constitutionally barred from
carrying, and in each case that is a **cheaper and more durable negative than a licence answer** — a
category exclusion cannot be renegotiated, where terms can.

Worth asking first, before terms and before joinability: **is this table about variants, or about the
people they were seen in?**

# What this round did not do

- **RM66 is not decided.** RM165's probe supplies the motif-structure evidence it was parked for and
  stops there; the keying change is expensive, on a shipped table, and is RM66's own pass.
- **RM16 is not re-opened.** RM163 touches the PGS manifest and not authored weights.
- **RM27's redistribution axis is not designed.** RM166's closed half points at it and does not
  attempt it.
- **No terms are asserted that a probe did not read.** Where a source publishes a policy rather than a
  licence (MANE, LitVar2) the gating axes are `None`; where the terms were not opened at all (MITOMAP — they are on a page a
  browser reaches) they are recorded as **unread**, which is not the same as unestablishable; and where the licence is per record (PGS Catalog) no constant claims to cover
  the corpus.
- **RM167's coverage measurement over the 11-module corpus is not done** — it is the build's first
  task, and it answers coverage, not the identity question four requests settled.
- **RM164's `variants.csv` spin-off is not designed here**, only noticed — `mmutation`'s 29 free-text
  status strings are the reason it is not a one-liner.
- ~~**No number is claimed for RM164's spin-off.**~~ **Claimed in the maintainer pass: it is RM171**,
  allocated by `.claude/rm-next.py` in the same locked write that reserved it. The rule the line stated
  is intact — this file did not claim it by reading the highest number off an index — and the line is
  struck rather than deleted so the sequence stays legible.

---

# Implementation ordering

**Written as *"if the three 0.7.0 items are taken"*; five were.** The three-item order below is
unchanged and correct, and two more sit around it: RM165's **drafting provider** lands after its check
half — separate commits, so the check is revertible without the provider — and **RM166 is last**, after
everything else has merged, on the sequencing argument in its own section.


1. **RM168 first.** Three files under 1.2 MB total, self-contained, and nothing else in the batch
   depends on it — but the identity protocol does, and it is the only item here that makes an
   already-shipped result (RM159's 33 answers) re-derivable. Take `changed_select_accessions` in the
   same pass as the summary: it is 3.6 KB and it is the currency check, so splitting them would ship
   the cache without the thing that notices it going stale.
2. **RM163 second.** `identifiers.py` gains a fourth registry; RM155–RM158 have just finished
   widening the rosters in that file, so this lands on freshly-reworked code and should land before
   memory of it fades.
3. **RM165's check half third.** It reuses the binning machinery and the two corpus modules are the
   test fixtures — both of them, because the source agrees with one and disagrees with the other, and
   a test that only ran HTT would pass while proving nothing.

**Shared-file hazards.** All three touch `licensing.py` (a new `SourceTerms` each) and two touch
`locations.py` (a cache dir plus a resolver each). RM163 and RM165 both touch `cli.py`; **RM163 alone
touches `identifiers.py`**, which RM155–RM158 reworked days ago. None of them touches `schema/` or
`compiler/` at all — if a diff in either appears, the item has grown past what this file decided and
wants a re-read.

**Two corrections from the build, and the second is the recorded exception.** With five items rather
than three, *all five* touch `licensing.py` and four touch `locations.py` and `cli.py` — the hazard is
the same one, wider. And the `schema/` prediction is **wrong**: five `VALID_VERIFICATION_CHECKS`
members land in `just-dna-format`, because four of the five passes attest and that vocabulary is
closed. The items did not grow; the prediction missed that attestation has a schema surface. The rule
the sentence is reaching for still holds in the form that matters — **`compiler/` is untouched**, and a
diff there would still mean an item had grown. The names are fixed before any pass is written, because
a published check name is a one-way door and minting one per-pass makes the last writer's spelling the
contract.

**Standing requirements, per lane.** Every pass that consults a source writes its `SourceRow`, and one
that contributes nothing writes none (`@write-the-sourcerow`). Every new builder is atomic
(`@atomic-sidecar-write`) and writes a `release.json` (`@release-json-provenance`). Network tests are
opt-in behind `JUST_DNA_NETWORK_TESTS=1` (`@network-tests-optin`). Every finding gets a warning code
naming the finding rather than the emission site (`@warning-code-names-the-finding`), and any check
whose message embeds a count runs once (`@no-rerun-with-counts`).

---

# Provenance

Every measurement in this document was taken on **2026-09-01** against the live sources named, from
this checkout, and the counts are from the files as served that day:

| Source | What was read | Headline |
| --- | --- | --- |
| PGS Catalog REST | the above plus `/rest/info`, `/rest/release/current`, `/rest/trait/`, `/rest/score/search`, and 40 random in-range ids | 200+`{}` for every negative; per-score `license`, 3 values in 250; **only ~35 % of the id range assigned** (12/40); release record published |
| MITOMAP web | six paths incl. `/Copyright`, `/cgi-bin/*.cgi`, `/robots.txt` | Cloudflare managed JS challenge — 403 to a non-JS client, live in a browser |
| MITOMAP dump | `mitomap.org/downloads/mitomap.dump.sql.gz`, 2026-08-24, 61 MB, 95 tables (maintainer-supplied; fetch re-verified by `curl`) | reachable by plain `curl` (206, ranges); **one `tissue` column, on `unpublished`**; `mmutation` 602 rows, `homo`/`hetero` are ±/nr flags; no licence text in 6.7 M lines |
| STRchive | `data/STRchive-loci.json` (319 KB), all fields | MIT, 82 loci / 79 genes, `locus_structure` on 23; **`evidence` on 82/82 incl. Disputed 3 / Refuted 1**; xrefs to gnomAD 72, TR-atlas 72, WebSTR 63 |
| gnomAD STR | `gnomAD_STR_genotypes__2022_01_20.tsv.gz` header (34.6 MB) | **per-sample genotypes** — `Sex`, `Age`, `Genotype`, `Allele1/2` — out on category |
| ClinPGx | `drugLabels.zip` (59 KB) + `clinicalVariants.zip` (74 KB) + name enumeration over the download endpoint | **≥12 published archives, the builder reads 1**; drugLabels 1,433 rows / 5 regulators; clinicalVariants 5,190 rows, comma-combined `type` |
| FDA | Table of Pharmacogenetic Associations (HTML) | 126 associations, no bulk file, no stated terms |
| LitVar2 / PubTator3 | all five documented endpoints, the four CIViC-legacy CAIDs, and PubTator3's BioC export for five PMIDs; over BRAF/HFE/APOE + `search/gene/HFE`; CAIDs resolved against the ClinGen Allele Registry | ids have **slots**: position, allele (CAID) and gene nodes. BRAF's 3 alleles = 31,276 / 99 / 41 PMIDs; APOE is **92 % position-only**. `search/gene/` returns Python `repr()`, not JSON |
| MANE | `current/` + summary (1.1 MB) + `changed_select_accessions` (3.6 KB) + `protein_coding_genes_not_in_mane` + three releases' READMEs | 19,437 rows, 74 MANE Plus Clinical; **120 changed accessions, `Update_Affects_CDS` Yes on 74**; 222 excluded genes over a 7-member reason vocabulary; VHL = `NM_000551.4` |
| NCBI | `/home/about/policies/` | places no restrictions; declines to grant permission |

The repo-side facts — `PgsRow`'s field descriptions, `RepeatAlleleRow`'s and `HeteroplasmyRow`'s key
fields, the two repeat modules' band tables, `clinpgx_build`'s single download, `licensing.py`'s
twelve `SourceTerms` — were read from the code and the reference examples at the same time.
