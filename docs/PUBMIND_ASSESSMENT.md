# PubMind — what it competes with, what it complements, and how we would adopt it

**Status** — assessment complete; **adoption decided 2026-08-28 in
[PROPOSAL_0_7 § RM134](proposals/PROPOSAL_0_7.md#rm134--pubmind-as-a-literature-derived-annotation-authority-and-a-clinvar-concordance-check),
which is authoritative where the two disagree.** This document stays the **evidence** — what was probed,
measured and read — and is not rewritten to match the decisions; where a decision changed something
below, an inline note says so and names it. Three such notes exist: the significance mapping, the
`clin_sig` column names, and the concordance outcome table. Written 2026-08-28 against the paper's
accepted version and against the database's own bytes, both probed the same day. The open item is
[RM134](ROADMAP_HISTORY.md#rm134--pubmind-as-a-literature-derived-annotation-authority-and-a-clinvar-concordance-check).

PubMind (Wang & Wang, *Nat Commun*, 20 August 2026, doi:10.1038/s41467-026-76834-4) runs a fine-tuned
DistilBERT triage stage over 41.7 M PubMed abstracts and 5.4 M PMC full texts, hands the surviving
paragraphs to LLaMA-3.3-70B with per-variant-class prompts, and extracts
variant–disease–pathogenicity associations with the model's own reasoning attached. Diseases are
normalized to MONDO and phenotypes to HPO by PubMedBERT cosine similarity at a 0.9 threshold;
coordinates come from PyEnsembl against Ensembl v111. The output is PubMind-DB: 1,473,920
literature-derived records consolidated into 765,260 unique variants across SNVs, gene fusions, SVs
and CNVs, of which 916,538 SNV rows carry genomic coordinates.

## The short answer

**We barely compete, and the overlap is not on the axis either project cares about.** Their own
discussion calls PubMind *"a literature-grounded complement to human curated databases"*, and that is
also the correct description of its relationship to us: PubMind is a **source**, of the same kind as
ClinVar, gnomAD or the GWAS Catalog, and our enricher already consumes four such sources. It produces
per-variant assertions; it does not produce a signed, versioned, licence-declared annotation artifact
that a consumer joins a genotype against, and nothing in the paper suggests it wants to.

The one genuinely contested surface is a sentence in their introduction: *"PubMind empowers
healthcare systems to construct secure, institution-specific variant-interpretation databases directly
from clinical notes and reports."* That is the same customer we would reach with an authored module —
an institution that wants its own interpretation table. But the thing PubMind hands that institution is
a SQLite database behind a Flask app, with no identity model, no integrity binding, no round trip, and
no licence axis. The competition is for attention, not for the artifact.

**Where we complement is much larger, and it is one-directional: they are upstream of us.** Their
strongest claim is coverage of what nobody curated — only 10.6 % of their coordinate-mapped SNVs
overlap ClinVar, and the bioinformatics predictors they benchmark against return "unknown" for most
variants they cover. Our strongest claim is everything downstream of an assertion: `variant_key` and
VRS identity, the three-valued algebra, the compile gate on declared use, the round trip, the
signature family. Those are disjoint. A PubMind row is exactly the sort of evidence an author would
want surfaced while curating, and exactly the sort of claim our checks exist to cross-examine.

## What we actually probed

Everything below is measured, not read off the paper. The inputs are git-ignored under `data/input/`;
re-fetch them with:

| What | Where | Pinned at probe time |
| --- | --- | --- |
| Accepted manuscript | `https://www.nature.com/articles/s41467-026-76834-4_reference.pdf` | sha256 `1002f535468393ee57e18c81a41aff9ba4a37c690c7cb80816cdded8763e586a` |
| Coordinate table | `https://www.openbioinformatics.org/annovar/download/hg38_pubmind_db.txt.gz` | sha256 `ca224ebf5ef3aa516d9f14b91ae96ce2371ea785670f4723fd5103e6f94dc047`, ETag `"63275d-659cb3f35fd80"`, Last-Modified Mon 24 Aug 2026 13:48:54 GMT, 6,498,141 bytes |
| Summary API | `https://pubmind.wglab.org/api/summary`, `/api/pvid/<PVID>` | probed live |
| Source + terms | `https://github.com/WGLab/PubMind` (`README.md`, `LICENSE.md`) | probed live |

### There is exactly one per-variant channel, and it is the ANNOVAR table

The web API has two endpoints and neither takes a variant. `/api/summary` accepts `gene`,
`MONDO_ID_09`, `MONDO_name_09` and `formatted_reference` (with `pmid`/`pmcid`/`mondo_id`/`mondo_name`
aliases) — an rsID query is refused with the allowed-field list — and it returns aggregate counts and
mean scores per variant class, nothing per row. `/api/pvid/<PVID>` returns one variant's summary but
requires you to already know the PVID, which only the website will tell you. Both responses carry an
explicit note: *"Detailed per-record information is not returned through the API."*

So the only channel that answers *"what does PubMind say about chr6:26092913 G>A"* is the bulk table
ANNOVAR redistributes as `hg38_pubmind_db`, dated 2026-08-24. It is small (6.5 MB gzipped, 909,224
rows) and carries five useful columns: `PVID`, `pathogenicity_sum`, `paper_level_pathogenicity_score`,
`confidence` (0–3), on top of `Chr/Start/End/Ref/Alt`.

**Its coordinates are VCF-style, not ANNOVAR-style, despite the packaging.** There is not a single
`-` allele in the file; a one-base deletion appears as `1 1014264 1014265 CC C`, anchor base retained.
That is our `chrom`/`start`/`ref`/`alts` convention exactly, `start` being the 1-based VCF position
(`@start-1based`), so a join needs no coordinate translation. Whether the indels are left-normalized
is **not** established and a pass must not assume it.

### The channel is smaller than "1.3 million variants" implies

909,224 rows sound like coverage. They are not, because two thirds of them are **enumerated codon
alternatives rather than observed variants**. When PubMind recovers only a protein change from the
text, it back-maps through the transcript and writes out every codon that could encode it:

| Row shape | Rows | Joinable? |
| --- | --- | --- |
| single-base substitution (`1/1`) | 289,615 | yes, directly |
| codon triplet differing at exactly one base | 160,090 | yes, after decomposition |
| codon triplet requiring 2 simultaneous substitutions | 312,875 | no — not a single event |
| codon triplet requiring 3 simultaneous substitutions | 126,508 | no |
| length-changing (indel) | 20,131 | yes, but normalization unverified |
| longer MNV blocks (4–19 bases) | 5 | no |

Decomposing the one-base codons onto their differing position gives **342,209 distinct
`chrom:start:ref:alt` keys over 305,935 distinct loci** — the honest size of the joinable SNV layer.
The remaining 439,388 rows assert that *some* codon change produced the reported amino acid, which is
a statement about the protein, not about a position a consumer can genotype.

### PubMind has record identity, not variant identity

This is the deepest structural difference and it is worth stating precisely, because it is the reason
a PubMind row can never be adopted as a fact without a check in front of it.

Consolidation into a PVID is keyed on the **text** the model extracted — gene symbol plus cDNA change,
protein change or rsID — never on a coordinate. So one physical variant fragments into many PVIDs.
68,744 coordinate keys (8.4 %) carry more than one PVID; the worst carries 35. At chr6:26092913 G>A —
HFE C282Y, one of the best-characterised variants in medical genetics — the table holds **eight
PVIDs**, verdicts split four Conflicting, two Uncertain, one Benign, one more Benign at a `G>G` row
that is not a variant at all. (523 rows across the file have `Ref == Alt`.)

One of those eight is instructive. `PVID926871` carries `rsid: rs1800562` and `gene: TMPRSS6`. rs1800562
is *HFE*, chromosome 6; *TMPRSS6* is chromosome 22. Two iron-metabolism papers discussed both genes,
the model crossed them, and because rsID→coordinate resolution is authoritative the row still landed on
the correct C282Y position — carrying the verdict **Benign, score 0.0, confidence 2**. Our
`_gene_locus_conflicts` check (`identifiers.py`, reported as `gene_locus_agreement`) catches exactly
this shape (`@gene-locus-relationship`: check the relationship, not the members, at chromosome
granularity). It is a clean demonstration that PubMind's
output wants our checks pointed at it, and a clean demonstration of why we would never carry one of its
verdicts into an artifact unexamined.

### What it is worth against our own corpus

Joined against every GRCh38 `resolution.csv` in `reference_examples/` (11 modules, 423 resolved loci;
`cyp2c9_warfarin_grch37`'s 5 GRCh37 rows are skipped, and five modules — `cyp2d6_structural`,
`fmr1_cgg_repeat`, `grch37_build`, `htt_repeat_expansion`, `mt_heteroplasmy` — carry no resolution
sidecar):

- **173 of 423 loci (40.9 %) are known to PubMind** at position level.
- **190 of 589 authored ALTs (32.3 %) match a PubMind row exactly.** The gap between the two numbers
  is the usual one: an rsID is position-level and a verdict is allele-level (`@rsid-not-per-allele`).
- Over every `variants.csv` in the corpus that authored a `clin_sig` and resolved to a GRCh38
  position — a slightly wider set than the sidecar join, since some modules carry coordinates on the
  row itself — PubMind returned a verdict for 134 loci and the two agree on **83 (62 %)**. Every
  disagreement runs the same direction: we say pathogenic, they say Uncertain (32) or Benign (19),
  which is what a literature-wide aggregate should do to a corpus deliberately seeded from ClinVar's
  pathogenic end.

Our 40.9 % locus coverage against a ClinVar-derived corpus sits comfortably beside their reported
10.6 % ClinVar overlap: the two measure opposite directions of the same asymmetry. **PubMind adds
breadth we do not have and would not gain by curating harder; it subtracts confidence we already
have.** That is the profile of a cross-check source, not of a fact source.

## What we cannot adopt at all

The part of PubMind that is genuinely novel — the per-record `LLM_reasoning`, the
`formatted_reference` list, the supporting evidence passage behind each call — **is not available
through any open channel**. The website serves it to a human; the API explicitly withholds it; the
README routes anyone wanting it to CHOP's licence terms. So the material closest to a
`provenance_quote` is the material we cannot reach, and no plan below should imply otherwise.

The terms need stating carefully, because two different things are licensed and only one of them
clearly.

- **The software** is covered by `LICENSE.md`: academic, non-commercial research use only, commercial
  use prohibited without a separate agreement from CHOP's Office of Technology Transfer. That is the
  same shape as the dbNSFP and OMIM terms `licensing.py` already names in the comment above
  `CLINPGX_TERMS` — academic-use-only, which bars passing data on at all, and which
  `commercial_use=False` alone understates.
- **The paper** is CC BY-NC-ND 4.0, which expressly forbids sharing adapted material.
- **The ANNOVAR-distributed coordinate table carries no stated terms of its own.** The README offers
  it as the open substitute for the licensed full database, and ANNOVAR redistributes it, but neither
  publishes a licence for those bytes. Under the house rule that is **unknown, not permissive**
  (`@no-named-licence`): unknown commercial terms warn, they never gate, and we record `None` rather
  than guessing, because `licensing.py` defines null as *"the terms could not be established"*.

Running the PubMind pipeline ourselves is not a scoping judgement, it is barred: the Constitution's
non-goals forbid pulling LLM SDKs into **any** tier of this workspace, and AI-assisted authoring is
`just-dna-pipelines`' job by name. The cost argument — multiple H100/A100-class GPUs, by the authors'
own account — is true and beside the point.

## What the charter decides

Read in full before the plan below was written, because P3/P8 decide whether any of it is even legal.

**Most of "do we compete" is settled by a non-goal rather than by an argument.** The Constitution
says this workspace does **no gene–disease inference**: the format catalogs curated annotations that
consumers *join* against variant data, and interpretation belongs to those consumers. PubMind is an
inference engine over the literature — that is its entire contribution. So the two projects are not
adjacent by accident; the thing PubMind does best is a thing we are constitutionally not in the
business of doing, which is precisely what makes it a good source and a poor competitor.

**All four sections are legal, and the batch is a minor.** Nothing below adds, removes, retypes or
promotes a schema field, so Principles 3 and 8 are not reached — no already-published module becomes
invalid, and there is nothing for a major to gate. All of it lives in `just-dna-enricher`, the only
tier permitted to fetch (Principle 2), and none of it writes into the compile path, which never
imports it. What makes the batch a minor rather than a patch is new commands, a new snapshot kind and
new warning phrases, every one of which a consumer can grep for; a corrected derivation would be the
other case and this is not one.

**The derived snapshot is priced at approximately nothing, and that is Principle 9 doing its job.** A
parquet the machine writes and no author ever types is the free layer. The section that would cost
something is the one nobody is asking for: a `pubmind_score` **authored** column would be full price,
and Principle 5 rules on it before the price matters. A single score covering how many papers spoke,
how confidently, and in which direction is three axes in one field — the anti-pattern Principle 5
exists to name, made permanent for the rest of the major by Principle 3. The snapshot keeps them
apart, `clin_sig` / `pathogenicity_score` / `confidence`, and the split is not cosmetic. (Written as
`pubmind_sig`; renamed before it shipped — see the supersession note below.)

**Drafting is where Principle 3's one-way door actually bites.** Drafted rows land in `variants.csv`
using columns that already exist, so the draft itself adds nothing — but `--min-confidence`,
`derivation` and the `pubmind` entry in `DRAFT_PROJECTIONS` are names that become permanent the moment
they ship, which is exactly what Principle 5's "audit every new name against likely future additions"
asks for. `derivation` in particular wants checking against the possibility of a second
literature-derived source arriving later.

**Nothing here touches Principle 7.** No section changes what `compile → reverse → compile` carries.
A drafted row round-trips because it is an ordinary authored row; the snapshot is not part of the
artifact at all. That is what keeps the whole batch additive.

## The plan

**Directed 2026-08-28: build both halves.** An earlier draft of this section stopped at a report-only
cross-check and recorded everything downstream as blocked. That is now overtaken — the ask is a
ClinVar-shaped **derived table with PubMind as the annotation authority**, plus a **three-way
cross-check reporting concordance and discordance against ClinVar**. The licensing constraint has not
changed and is not waved away; it moves from *reason not to design* to *precondition on shipping*, and
[Gate](#the-gate-and-what-lifts-it) below says exactly which step it holds.

One word needs pinning before anything else. **"Authority" here means an authoritative annotation
source in the sense ClinVar is one — never `resolution.csv`'s `authority` column** (`@source-vs-authority`).
Nothing PubMind produces may ever enter `resolution.csv`. Its coordinates are PyEnsembl back-mappings
of text the model extracted, codon-enumerated and multi-PVID; treating that as a resolution link would
put a derived guess where a resolved identity belongs. PubMind annotates loci that something else
resolved.

### A. `pubmind build` — the derived snapshot

Mirror `clinvar_build.py` in structure, and mirror `@duckdb-vs-polars` in mechanics: builder in
polars, fixed column order so a rebuild is byte-identical (P7). Registered as a `pubmind` sub-app
beside `clinvar`, so the surface reads `just-dna-enrich pubmind build` / `… publish`, matching the
`clinvar build`/`clinvar publish` pair a reader already knows.

Input is the ANNOVAR-redistributed `hg38_pubmind_db.txt.gz`, downloaded by `--download` or supplied by
`--table`, exactly as `clinvar build` takes `--vcf` or `--download`. Output is a snapshot directory:
one parquet under `data/`, plus `release.json`, laid out through `locations` like every other snapshot
(`@snapshot-layout-locations`).

**Schema.** `_empty_schema()`'s split is the model — resolver-link columns first, annotation after —
except that here *no* column is a resolver link, which is the point above made structural:

| Column | From | Note |
| --- | --- | --- |
| `chrom`, `start`, `ref`, `alt` | `Chr/Start/Ref/Alt` | the join key; VCF-style already, `start` is the 1-based POS (`@start-1based`) |
| `pvid` | `PVID` | their record id, not a variant id — see the fan-out rule below |
| `pubmind_sig` → **`clin_sig`** | mapped `pathogenicity_sum` | normalized into `VALID_CLIN_SIG`. **Renamed 2026-08-28**: the ClinVar snapshot already uses the unprefixed name, so the source is the file and a prefix restates it — and one column vocabulary across every snapshot is what lets an N-authority check read them all without per-source mapping |
| `pubmind_sig_raw` → **`clin_sig_raw`** | `pathogenicity_sum` verbatim | so the mapping stays auditable and nothing is lost, exactly as `clin_sig_raw` does for CLNSIG |
| `pathogenicity_score` | `paper_level_pathogenicity_score` | nullable, and null means *not computed*, never 0.0 |
| `confidence` | `confidence` | 0–3, the `review_stars` analogue |
| `derivation` | computed | `direct` for a `1/1` row, `codon` for a decomposed triplet, `indel` for a length-changing one |

> **Superseded 2026-08-28 (PROPOSAL_0_7 § RM134): one normalizer, not a second map — and it needs two
> fixes first.** Treating `_CLIN_SIG_MAP` as a *precedent to copy* gives two maps for one vocabulary, and
> since the three-way check's whole output is a comparison of two normalizations, any drift makes it
> report a disagreement between our own mappings. But reusing `_normalize_clin_sig` unchanged is wrong
> today: its keys are underscored and PubMind's tokens are spaced, so **`Uncertain significance` → `other`
> and `Conflicting` → `other`** — measured, both concepts ClinVar normalizes correctly, and Uncertain is
> 32 of the 51 disagreements counted below. Fix: a whitespace→underscore pre-step (a no-op on ClinVar's
> tokens) plus a bare `conflicting` key.

`_CLIN_SIG_MAP` is the precedent for the mapping and its default: a token with no module axis becomes
`other` rather than being dropped. The six PubMind values map cleanly — `Pathogenic` → `pathogenic`,
`Pathogenic/Likely pathogenic` → `pathogenic`, `Benign` → `benign`, `Benign/Likely benign` → `benign`,
`Uncertain significance` → `uncertain_significance`, `Conflicting` → `conflicting` — and the two
composite tokens are the ones worth arguing about, since collapsing `P/LP` to `pathogenic` loses the
distinction our own vocabulary can carry. Keep both: `pubmind_sig_raw` holds the composite and
`pubmind_sig` holds the mapped call, and no consumer has to re-parse a slash.

> **Superseded 2026-08-28 by [PROPOSAL_0_7 § RM134](proposals/PROPOSAL_0_7.md#rm134--pubmind-as-a-literature-derived-annotation-authority-and-a-clinvar-concordance-check),
> in three places. Kept because the reasoning above is why the decision went the other way.**
>
> 1. **One normalizer, not a second map.** The paragraph proposes a hand-written PubMind map citing
>    `_CLIN_SIG_MAP` as precedent. Two maps for one vocabulary drift, and since the check's entire
>    output is a comparison of two normalizations, a drift would make it report `discordant` on its own
>    mapping rather than on the authorities. The shipped form is one shared `clin_sig` normalizer both
>    sources call.
> 2. **`Benign/Likely benign` → `likely_benign`, not `benign`.** Under the shared normalizer a composite
>    splits on `/` and the **severity order** picks the answer, so B/LB reaches `likely_benign` — the
>    same answer ClinVar's `Benign/Likely_benign` already gets, which is the point of sharing. `P/LP` is
>    unaffected and still reaches `pathogenic`. **This is a deliberate result, not an unimplemented
>    line: do not "restore" `benign`.**
> 3. **The columns are `clin_sig`/`clin_sig_raw`**, not `pubmind_sig`/`pubmind_sig_raw`. The source is
>    the file, so naming a column after it restates the filename — and one column vocabulary across
>    every snapshot is what lets an N-authority check work with no per-source mapping at all.

**Normalization is where the measured defects get handled, and every drop is counted.** Silent
truncation reads as full coverage, so each of these lands as a number in `release.json`
(`@dont-discard-computed`):

- decompose a codon triplet differing at exactly one base onto that base's position (**160,090** rows
  in the 2026-08-24 file), stamped `derivation=codon`;
- drop triplets needing ≥2 simultaneous substitutions (**439,383**) and longer MNV blocks (**5**) —
  they assert a protein change, not a genotypable position;
- drop `Ref == Alt` rows (**523**);
- keep length-changing rows (**20,131**) but stamp them `derivation=indel`, because left-normalization
  is unverified and a consumer needs to be able to exclude them without re-deriving why;
- **keep every PVID on a contested coordinate as its own row.** 68,744 coordinates carry more than
  one, worst case 35, and their verdicts disagree. Collapsing them would mean choosing a winner by an
  ordering nobody defined — `mode()` over an unsorted group is the exact shape the ordering rule bans.
  The multiplicity is a finding, and section B is where it surfaces.

**`release.json` carries the provenance and the aggregate.** Source URL, the file's sha256, its ETag
and Last-Modified (all three available, all three recorded, so an upstream revision becomes a finding
rather than a silent change of answer), the PubMind-DB version, our builder version, and the drop
counts above. `_merge_release_block` is the existing shape for adding a block without clobbering a
sibling snapshot's (`@snapshot-accumulates`).

**`pubmind publish` is refused, and that is the design, not an omission.** PharmVar is the standing
precedent (`@gated-source-caches`): every gated source gets a cache, and PharmVar's is deliberately
unpublishable, because a bulk file arriving under terms we cannot establish is not a file we may pass
on. An unestablished permission is not a permission. So the command exists and refuses with the
reason, rather than not existing — a missing command reads as an oversight somebody will helpfully add.

### B. The cross-check: module ↔ ClinVar ↔ PubMind

This runs beside the existing ClinVar `clin_sig` check rather than replacing it, and it answers a
question that check cannot: *do two independent authorities agree about this variant, and where they
do not, which one is our row standing with?*

> **Superseded 2026-08-28 (PROPOSAL_0_7 § RM134): the outcome table below fails at three authorities.**
> `pubmind_only` and `clinvar_only` name the authority *inside* the vocabulary member, so a third source
> needs a third member and five need every subset. The cause is that one field carries two axes —
> `concordant` is defined as *both agree **and** the authored row agrees with them*, with
> `authored_dissents` as a sibling. Split into `authority_concordance`
> (`concordant`/`discordant`/`single`/`none`/`unchecked`) and `authored_position`
> (`matches_all`/`matches_some`/`matches_none`/`absent`/`unchecked`): five members each at any N, with
> *which* authority spoke living in a paired detail table. And **nothing resolves a split** — five
> sources ordered E>B>D>C>A with E+A against B/C/D cannot be resolved without a weighting model, which is
> why `authored_position` relates to the *set* rather than to a resolved call. The table below is kept as
> the reasoning that produced the outcomes, not as the shape that ships.

**Per variant, the outcome is a triple, and unknown is withheld rather than negated.** Each of the
three sides independently answers pathogenic-class / benign-class / uncertain / **absent** /
**unreachable**, and the combination is classified — Kleene, not withhold-on-any-unknown, because
`unknown AND false` really is `false`:

| Outcome | Meaning |
| --- | --- |
| `concordant` | ClinVar and PubMind both spoke and agree, and the authored row agrees with them |
| `authored_dissents` | the two authorities agree with each other and the module does not |
| `authorities_differ` | ClinVar and PubMind spoke and disagree — the interesting case, and the one nothing today can report |
| `pubmind_only` | PubMind has a call where ClinVar has none: literature-derived coverage, the reason to adopt at all |
| `clinvar_only` | ClinVar has a call where PubMind has none |
| `neither` | absent from both — evidence of nothing, and it must not be reported as agreement |
| `unchecked` | a side was unreachable, or nobody asked (`--offline`, no snapshot) |

`ClinSigConflict.opposed` already draws the line the severity turns on: **opposed** (pathogenic-class
vs benign-class) is the finding worth acting on, merely **different** is worth knowing. Reuse that
distinction rather than inventing a second one — a discordance between `pathogenic` and
`uncertain_significance` is not the same event as one between `pathogenic` and `benign`, and our own
corpus has 32 of the first and 19 of the second.

**Severity is warning-tier in both modes and never escalates under `strict`.** `@clinsig-never-escalates`
is the precedent and it applies with more force here: a disagreement with an LLM's aggregate over the
literature is a statement about the extraction's limits at least as often as about the module. 62 %
agreement is not a number a gate is built on. `authorities_differ` in particular is not a defect in
the module at all — it is a fact about the field — and reporting it as one would be wrong.

**Aggregates land in two places, and only one of them recomputes.** Build time stamps
corpus-wide concordance into `release.json` — our own reproduction of their 10.6 % ClinVar-overlap and
>80 % concordance claims, against our own denominator and our own normalization, which is the only way
those numbers mean anything to us. Enrich time reports per module. The build-time number is computed
once and never recomputed by a later pass, because a message embedding a count that runs twice
publishes two numbers (`@no-rerun-with-counts`); the enrich-time check dedupes on message, which is
the normal case for a check running on both sides.

**Absence is not disagreement, and it is not one thing.** A variant missing from PubMind means no
paper in the corpus discussed it in text the DistilBERT triage stage kept — not that the literature is
silent, and certainly not that the variant is benign. `--offline` with no snapshot is a third state
beside asked-and-failed and asked-and-absent (`@unreachable-not-absent`), and a check that could not
run must not report a zero (`@tautology-zero`).

### C. Drafting from PubMind as an authority

`draft-panel` drafts from ClinVar today. PubMind gets the same treatment through **`--source pubmind`
on the existing command rather than a new `draft-pubmind`** — the two produce the same row shapes into
the same tables from the same gene argument, and a second command would duplicate the genotype
worklist, the placeholder guard, the dedup-against-`variants.csv` pass and the refusal summary, all of
which are the parts that are hard to get right. `draft-clinpgx` is a separate command because it
writes *different tables*; this does not.

> **Settled 2026-08-30, while building § C: the section assumes a gene argument works, and the snapshot
> has no gene column.** Every locational thing PubMind publishes is `(chrom, start, ref, alt)`, so
> `--gene BRCA1` needs a gene→locus map — and this workspace deliberately holds none, which is why the
> compiler's own gene/locus check is chromosome-granular. The map built is **ClinVar's own per-record
> attribution matched at the exact position**, taking every position ClinVar records for the gene with
> no clinical or review filter, because it is a locus universe rather than a selection. A min/max span
> over those positions was refused: it invents a boundary nobody defined and writes a `gene` cell that
> is a false claim wherever two genes overlap. Two consequences, both stated in the drafter and in
> ENRICHER: `--source pubmind` needs **both** snapshots, and a PubMind verdict at a position ClinVar has
> no record for cannot be reached by gene at all — a class that is not countable, since attributing it
> to a gene is exactly what there is no map for.
>
> Two smaller corrections from the same build. **`derivation=indel` gets no `--include-indels` flag**:
> a flag is a permanent name the proposal did not price, and additive means one can be added later if
> anybody wants those rows. And the drafter does **not** call `check_declared_use` — that gate decides
> whether a *fetch* may proceed and skips on unknown terms, while nothing here fetches; wiring it in
> would have made the command skip unconditionally whatever `--use` said. The reason is reported in the
> source's own words instead (`@acquisition-gate-is-not-a-read-gate`).

What changes behind the flag:

- **`--min-confidence` is the `min_review_stars` analogue**, defaulting to a floor rather than 0.
  PubMind's confidence 0–3 counts evidence depth the same way stars count review depth, and a
  confidence-0 row is a single paragraph in a single paper.
- **Identity is coordinate-whole or nothing** (`@identity-whole-or-none`). Most PubMind rows carry no
  rsID at all — the HFE example resolves through one, the BRCA1 example has `rsid: "-"` — so the
  provider fills `chrom`/`start`/`ref`/`alt` together or refuses the row and says which cells it could
  not establish. Half an identity is worse than none.
- **A `derivation=codon` row is drafted with that fact attached, and `derivation=indel` is not drafted
  at all** by default, since left-normalization is unverified.
- **Rows append, never mutate** (`@draft-appends`); a `<<REPLACE>>` placeholder protects `genotype` as
  it does for ClinVar (`@placeholder-protects-decision`); the provider writes its own `SourceRow`
  (`@write-the-sourcerow`), and a test that strips `declared_use` and asserts the compile refuses is
  what keeps that row load-bearing.

**The self-agreement trap, and the existing answer to it.** A module drafted from PubMind and then
cross-checked against PubMind agrees with itself, and a check that agrees with itself has told nobody
anything. `@draft-digest` is exactly this problem solved once: the provider hashes the table it wrote
projected onto the column its own cross-check later reads, stamps `SourceRow.draft_digest`, and the
check recomputes it and skips when the value has not moved. Add `pubmind` to `DRAFT_PROJECTIONS`
projected onto `clin_sig`, and remember the two things that entry warns about — the projection is over
**raw CSV cells** at draft time, when the table is still full of placeholders, and the skip is a
**conjunction** of release *and* digest, so a matching digest against a newer snapshot is still a real
comparison.

The ClinVar half of section B is unaffected by this and is the reason the three-way check is worth
more than either two-way: a PubMind-drafted module still gets a genuine independent opinion, from
ClinVar.

### D. The hint surface

> **Corrected 2026-08-30 while building it: the ANNOVAR channel carries no PMID and no paper count.**
> The section promises "verdict, confidence, paper count and PMIDs"; § A's probe of the real file
> settled the columns, and they are `pvid`, `clin_sig`, `clin_sig_raw`, `pathogenicity_score`,
> `confidence` and `derivation`. What the hint surfaces is those, per record. It also answers for a
> coordinate the caller typed rather than only for a locus an rsID resolved to, which the ClinVar leg
> does not do — their channel is coordinate-keyed and most of its rows carry no rs-number, so the
> rsID-only shape would leave the leg unreachable for most of the corpus.


Unchanged from the earlier draft and still the cheapest thing here: `hint-variant` surfaces the
verdict, confidence, paper count and PMIDs beside a cell an author is about to fill. It may **not**
pre-fill `clin_sig` (`@hint-redundancy-bearing`) — the cell section B cross-examines cannot be filled
by the source doing the cross-examining, which is the same defect `@draft-digest` handles for the
drafting path, one layer up and without a digest to rescue it.

### The gate, and what lifts it

Sections A and D are buildable now. Sections B and C **acquire and carry** PubMind values, and both
turn on one unanswered question:

1. **The ANNOVAR-distributed table publishes no data terms.** `LICENSE.md` covers the *software*
   (academic, non-commercial, CHOP tech-transfer for anything else); the paper is CC BY-NC-ND; the
   table itself says nothing. Unknown is not permissive (`@no-named-licence`). **The unblock action is
   to ask** — WGLab and CHOP's Office of Technology Transfer, in writing, whether the ANNOVAR-shipped
   subset may be redistributed and on what terms. Nobody else can answer it, and it will not resolve
   itself by the file continuing to download without a key.
2. **RM27 still owes the redistribution axis** (`@redistribution-ungated`). `redistribution` is
   recorded and not gated, so there is no machinery that would refuse to publish a module carrying
   bytes we may not pass on. That is a gate on *publishing such a module*, not on building the
   snapshot or running the check locally — worth separating, because conflating them is what stalled
   this whole area in the earlier draft.

`PUBMIND_TERMS` goes in `licensing.py` beside the others, recording what is establishable and `None`
for what is not — `license=None`, `license_url` pointing at CHOP's `LICENSE.md`, `commercial_use=None`,
`redistribution=None`, attribution to CHOP and the paper. The nulls are load-bearing: `licensing.py`
defines null as *"the terms could not be established"*, which is a weaker and more honest statement
than either permission or refusal, and it is the state we are actually in.

Client mechanics follow the existing contract without exception: retry then translate, both legs, into
a `PubMindUnavailable` subclass rather than a flat error (`@client-exception-contract`); the cache path
resolves through `locations`; refresh merges, never clobbers (`@sidecar-authoritative`). And never
persist a URL their API hands back — `website_result_url` and `website_detail_url` both currently
return `http://localhost:5016/...`, a deployment leak on their side. Derive links from
`https://pubmind.wglab.org/` ourselves.

### Tests

Real fixtures, real paths, values computed at runtime — and specifically **no row counts copied out of
this document into an assertion**. The counts here are a dated reading of a file that will move; a
test pinning them fails on the next ANNOVAR release for no reason. Assert the relationships instead:

- **codon decomposition as a property** — a synthetic 3/3 row differing at one base decomposes to the
  right position and allele; one differing at two is excluded; the exclusion count in `release.json`
  plus the kept count equals the input row count, an equality over a walked set rather than a floor
  (`@registry-completeness`).
- **the `VALID_CLIN_SIG` mapping is total** — every distinct `pathogenicity_sum` in the fixture maps to
  a vocabulary member, and `clin_sig_raw` (written here as `pubmind_sig_raw`) round-trips the
  composite tokens verbatim.
- **rebuild is byte-identical** from the same input, which is what the fixed column order buys.
- **all seven concordance outcomes are reachable**, each from a constructed three-way case, and
  `authorities_differ` is warning-tier under `strict` — the assertion that would have caught an
  escalation.
- **`neither` never reports as agreement**, and `unchecked` under `--offline` reports no zero
  (`@tautology-zero`).
- **the multi-PVID case reports every PVID**, using the real chr6:26092913 shape: eight records, four
  distinct verdicts, and the one pairing `rs1800562` with *TMPRSS6* flagged by the gene/locus check.
- **the draft digest skips on an unmoved `clin_sig` and fires once the cell is edited**, and does
  *not* skip against a newer release with a matching digest.
- **a PubMind-drafted module still gets its ClinVar opinion** — the check that proves the three-way
  design earns its keep.
- **`PUBMIND_TERMS` produces a `SourceRow`**, stripping `declared_use` makes the compile refuse, and
  `pubmind publish` refuses with its reason named.

## Open questions

- Are the indel rows left-normalized? Unestablished, and it decides whether the 20,131 length-changing
  rows can be joined at all.
- What are the ANNOVAR-distributed table's data terms? Only CHOP can answer, and the answer decides
  whether sections B and C are ever shippable.
- Does the table get a stable release cadence? One snapshot dated 2026-08-24 is not a cadence, and the
  refresh design depends on it.
- Is the PVID stable across releases? If it is not, then nothing about a PubMind reference is
  citable, and the pass should record coordinates rather than PVIDs.
- ~~Is `derivation` the right name?~~ **Closed 2026-08-28.** P3 makes a *published* name permanent
  because outside consumers key on it, and `pubmind publish` is refused — so this column never leaves the
  machine that built it, is not in an artifact, not attested in `artifact.files`, not a manifest field and
  not joinable, and renaming it costs a rebuild the same command performs. The P5 audit belongs on the
  names that really are one-way doors: `--min-confidence`, and the `DRAFT_PROJECTIONS` key `pubmind`,
  which is matched against `SourceRow.source` and so reaches the authored, published `sources.csv`.
- Should build-time concordance be computed over the whole table or only over rows a module could
  plausibly reach? The whole table reproduces their published claim; a reachable subset is the number
  an author actually cares about. They are different denominators and only one can be the headline.
