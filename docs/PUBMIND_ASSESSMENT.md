# PubMind — what it competes with, what it complements, and how we would adopt it

**Status** — assessment complete, adoption **not started**. The open item is
[RM134](ROADMAP.md#rm134--pubmind-as-a-literature-derived-cross-check-source). Written 2026-08-28
against the paper's accepted version and against the database's own bytes, both probed the same day.

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
| Accepted manuscript | `https://www.nature.com/articles/s41467-026-76834-4_reference.pdf` | sha256 `1002f535…3e586a` |
| Coordinate table | `https://www.openbioinformatics.org/annovar/download/hg38_pubmind_db.txt.gz` | sha256 `ca224ebf…4dc047`, ETag `"63275d-659cb3f35fd80"`, Last-Modified Mon 24 Aug 2026 13:48:54 GMT, 6,498,141 bytes |
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

Running the PubMind pipeline ourselves is a different adoption question and is out of scope here: it
needs multiple H100/A100-class GPUs by the authors' own account, and it would make us a producer of
literature-derived assertions rather than a consumer of them.

## The plan

### Phase 1 — a report-only cross-check, and nothing lands in an artifact

Mirror the ClinVar `clin_sig` precedent exactly. A new enricher pass reads the cached PubMind
coordinate table, joins the module's resolved subjects, and **reports** where a module's authored
`clin_sig` disagrees with PubMind's aggregate — never repairs, never fills a cell
(`@enrichment-is-validation`). Report-only means no PubMind bytes reach the parquet, which sidesteps
redistribution entirely and makes the unstated data terms a warning rather than a blocker.

Severity is warning-tier in **both** modes and must never escalate under `strict`. The reasoning is
the same one written down for ClinVar (`@clinsig-never-escalates`) and it is stronger here: a
disagreement with an LLM's aggregate over the literature is a statement about the extraction's limits
at least as often as about the module, and the 62 % agreement measured above is not a number a gate
can be built on.

The design constraints that are not negotiable:

- **hg38 only.** The published table is GRCh38 and there is no GRCh37 equivalent. A GRCh37 module gets
  the pass skipped with a named reason, the way `refget_supports_build` answers the same predicate
  (`@refget-raises`), not a silent no-op.
- **Decompose before joining, and publish the denominator.** Single-base codon rows decompose onto
  their differing position; rows needing ≥2 simultaneous substitutions are excluded, counted, and the
  count appears in the warning text, because a warning's text is an API and a denominator behind a
  flag is the standing requirement (`@warning-text-is-api`). A pass that silently drops 48 % of the
  file reads as full coverage.
- **`Ref == Alt` rows are dropped and counted separately.** 523 of them; they are not variants.
- **PVID fan-out is a finding, not a tie-break.** Where a coordinate carries several PVIDs with
  disagreeing verdicts, report all of them. Picking one would be deriving an answer from an ordering
  nobody defined, and the multiplicity is itself the useful signal.
- **Three-valued, plus nobody-asked.** found / absent / unreachable, and `--offline` with no cache is
  the fourth state the house rule insists on naming separately (`@unreachable-not-absent`). Absence
  from PubMind is not evidence of anything: it means no paper in the corpus discussed the variant in
  text the triage stage kept.
- **Never persist a URL the API hands back.** Both `website_result_url` and `website_detail_url`
  currently return `http://localhost:5016/...` — a deployment leak on their side. Derive links from
  `https://pubmind.wglab.org/` ourselves.

Mechanics follow the existing client contract without exception: retry then translate, both legs, into
a `PubMindUnavailable` subclass rather than a flat error (`@client-exception-contract`); every pass
that consults the source writes its `SourceRow` (`@write-the-sourcerow`); the cache path resolves
through `locations`; the snapshot is pinned by sha256 **and** ETag/Last-Modified so an upstream
revision surfaces as a finding rather than a silent change of answer; refresh merges, never clobbers
(`@sidecar-authoritative`).

`PUBMIND_TERMS` goes in `licensing.py` beside the others, recording what is establishable and `None`
for what is not — `license=None`, `license_url` pointing at CHOP's `LICENSE.md`, `commercial_use=None`,
`redistribution=None`, attribution to CHOP and the paper. Nulls here are load-bearing: they are the
difference between "the terms permit this" and "we could not establish the terms".

### Phase 2 — carrying a PubMind value, which is blocked and stays blocked

Anything that puts a PubMind number *into* a module — a `pubmind_score` column, a drafted row, a
studies entry sourced from `formatted_reference` — is gated on two independent things, and neither is
ours to resolve unilaterally:

1. **RM27 must design the redistribution axis first.** `redistribution` is recorded today and not
   gated (`@redistribution-ungated`), so there is no machinery that could refuse to publish a module
   carrying bytes we may not pass on.
2. **The data terms have to be established**, by asking CHOP, not by inferring from the fact that the
   file downloads without a key.

Recorded so it is not re-proposed each time somebody notices the file is small and open.

### Phase 3 — the authoring surface, which is the actually valuable one

The highest-value use of PubMind is not a compile-time check at all: it is a **drafting hint** for an
author deciding whether a variant is worth a row and what the literature says about it. That is where
the 40.9 % locus coverage pays, and where a low-confidence, literature-derived signal is appropriate
because a human reads it before anything is written.

The constraint is the one that already governs hints: a hint may not fill a cell a Class-2 check
cross-examines (`@hint-redundancy-bearing`). A PubMind verdict may **not** pre-fill `clin_sig`,
because the cross-check in Phase 1 compares `clin_sig` against that same source, and a check that
reads back what a hint wrote agrees with itself. Surfacing the verdict, the confidence, the paper
count and the PMIDs beside an empty cell is allowed and is the whole point.

### Tests

Real fixtures, real paths, values computed at runtime — and specifically **no row counts copied out of
this document into an assertion**. The counts above are a dated reading of a file that will move; a
test that pins them fails on the next ANNOVAR release for no reason. What to pin instead:

- codon decomposition, as a property: a synthetic 3/3 row differing at one base decomposes to the
  right position and allele; one differing at two bases is excluded and counted.
- the excluded-row denominator appears in the warning text, phrase pinned.
- the hg38 gate refuses a GRCh37 module by name.
- `--offline` with no cache reports unreachable, distinctly from absent, and does not report a zero
  (`@tautology-zero`).
- the multi-PVID case reports every PVID, using the real chr6:26092913 shape.
- `PUBMIND_TERMS` produces a `SourceRow`, and stripping `declared_use` makes the compile refuse.

## Open questions

- Are the indel rows left-normalized? Unestablished, and it decides whether the 20,131 length-changing
  rows can be joined at all.
- What are the ANNOVAR-distributed table's data terms? Only CHOP can answer, and the answer decides
  whether Phase 2 is ever reachable.
- Does the table get a stable release cadence? One snapshot dated 2026-08-24 is not a cadence, and the
  refresh design depends on it.
- Is the PVID stable across releases? If it is not, then nothing about a PubMind reference is
  citable, and the pass should record coordinates rather than PVIDs.
