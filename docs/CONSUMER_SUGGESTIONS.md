# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S110

**Claim ids from here, never from what this file shows.** S1–S109 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
.claude/triage-state.py --next        # scans this file AND the history file
```

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---

## S110 — the literature pass leaves an author manuscript abstract-only when PMC's BioC service serves it whole, tables included

**Reporter:** just-module-creator, 2026-09-24, enricher 0.7.1 installed. Our `F108`.

**What happened.** PMID `30820047` (Kunkle 2019, *Nat Genet*, `PMC6463297`, NIH author manuscript
`NIHMS1021255`) carries its per-locus rows — lead rsID, major/minor allele, OR — in body **Tables 1
and 2**, and nowhere else with both allele and OR. Measured the same day:

| call | answer |
|---|---|
| Europe PMC `rest/PMC6463297/fullTextXML` | **HTTP 500** |
| `EuropePmcClient.fulltext("PMC6463297")` | `None` (the 500 and a 404 both land in the `HTTPStatusError` arm) |
| `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/PMC6463297/unicode` | **200, 276 KB**, 294 passages, both tables as `type: table` passages with tab-separated cells |
| same URL for `PMC1050584` (not in OA / manuscript set) | **200** with body `[Error] : No result can be found.` — an answer, not an outage |

So `enrich-literature` checked the module's 24 quotes against the abstract (`quote_source=abstract`),
which is what `S109` then published as a miss. The fulltext existed, openly, one NCBI host away.

**Two things on your side, separable.**

1. **A BioC rung after Europe PMC in the fulltext fetch.** It is an NCBI host, so it belongs on the
   E-utilities `PacingGate` budget. Keep table passages as text — for a GWAS paper the tables are where
   the rows are. Skip `section_type=REF` (186 of the 294 passages here, none of them evidence).
2. **The `is_open and pmcid` gate at `literature.py`'s fetch loop.** An author manuscript is usually
   `isOpenAccess: N` in Europe PMC while PMC serves it for text mining (the BioC `license` infon here
   reads *"This file is available for text mining"*). If the gate stays, a BioC rung never runs for
   exactly the records that need it. What the right predicate is — `inPMC`, `hasPDF`, the manuscript
   id — is yours to judge; the case above is the data point.

**Also worth separating in `fulltext()`**: a 500 and a 404 both return `None`, so "Europe PMC was
down" and "Europe PMC has no copy" reach the caller as one value. Only the second is an answer.

**What we did meanwhile.** Built the rung on our side (`discovery._bioc_fulltext`, `text_source:
"pmc_bioc"`, behind our NCBI gate, three outcomes kept apart), so `fetch_fulltext` now returns the
Kunkle tables — verified live, 68 KB with the tables. It does not reach your quote check, which is
why this note exists. Fixture: a trimmed copy of the real answer at
`just-module-creator/assets/literature/pmc_bioc_PMC6463297.json`; take it if it is useful.

## S111 — idea: an enrichment that states a module's expected match rate on consumer genotyping chips

**Reporter:** just-module-creator, 2026-09-24, from the owner: *"in just-prs we have the universes +
some imputation for chips. So we can actually enrich modules with expected matchrate for chips."*
A proposal, not a defect — offered with a measurement so it is not empty-handed.

**The question it answers.** Most people who will run a module hold a 23andMe / AncestryDNA file, not
a WGS VCF. A module that annotates 527 variants may annotate 120 of them on that file, and nothing
says so before the report comes back thin. An author choosing between two lead SNPs in LD would pick
the typed one if they knew.

**What already exists, in `just-prs` (`../just-prs/just-prs/src/just_prs/`).**
- `chip_coverage.chip_typed_positions(Chip.GSA_V3, cache, build=)` — unique typed `(chr, pos)` for
  the Illumina GSA v3 backbone that 23andMe v5, AncestryDNA v2, MyHeritage and FTDNA v2 share.
  **Both A2 (GRCh38) and A1 (GRCh37) manifests**, 648,379 positions.
- `ld_proxy` — a 1000G LD table keyed on target position with the best GSA-typed proxy, `r_squared`
  and `r_signed` (2.67 M targets; computed for PGS scoring-file targets, so its coverage of an
  arbitrary module is a lower bound).
- `liftover.lift_frame` — GRCh38⇄GRCh37, returning dropped rows with a reason.

**Measured over 16 real modules' `resolution.csv` (965 positions)** — the kunkle2019 GWAS panel,
the longevitymap port, an APOE compound module and 13 ClawBio PGx gene modules:

| | positions | typed on GSA (GRCh38 A2) | + LD proxy r² ≥ 0.8 | lost lifting to GRCh37 | typed on GSA (GRCh37 A1, after lift) |
|---|---|---|---|---|---|
| kunkle2019_load | 24 | 5 (21 %) | +7 | 0 | 5 |
| longevitymap | 527 | 122 (23 %) | +113 | 1 | 122 |
| PGx genes (13) | 407 | 207 (51 %) | +7 | 0 | 207 |
| **all 16** | **965** | **336 (35 %)** | **+127** | **1** | **336** |

Two readings worth having before designing it:

- **The liftover worry is smaller than expected for this purpose.** A 23andMe file is GRCh37, and the
  owner flagged liftover as the non-trivial part. For *expected typed rate* it mostly is not: the GSA
  A2 manifest is already GRCh38, so a GRCh38 module intersects directly, and lifting the module to
  GRCh37 and intersecting A1 gave the identical 336 with one position lost. The liftover cost is real
  at **annotation** time, on the sample (that is `just-dna-lite`'s side), and belongs to that report,
  not to the module's number.
- **The GWAS modules are the ones that need it.** ~22 % typed for both GWAS-shaped modules, against
  51 % for PGx panels whose star-allele SNVs the arrays were designed around. An LD proxy roughly
  doubles the GWAS number — but only where the consumer actually substitutes proxies, which is a claim
  about the annotation engine and must not be folded into a "match rate".

**A shape to argue with.** A sidecar or manifest facet per chip: `chip`, `build_compared`, `authored`
(denominator, positions with coordinates), `typed`, `proxyable_r2_0_8`, `not_assessable` (symbolic /
structural alleles — CYP2D6's CNV cannot be position-matched at all), and the manifest version. Three
counts, never one rate, for the same reason your counters are `int | None`.

**Caveats to state wherever it lands.** Position match only — no allele or strand check, so a typed
position whose array probe reports the other strand still counts. The GSA manifest excludes each
vendor's custom content (tens of thousands of markers), so `typed` is an **under**-estimate; older
23andMe v3/v4 kits (OmniExpress) have no manifest here at all. The LD table's target set is PGS-driven.

**Where the data comes from is the open question.** The positions parquet is a local cache in
`just-prs`, not a published artifact, and the enricher should not import `just-prs`. Publishing the
per-chip position sets (a few MB each) beside the LD table on the `just-dna-seq` HF org would let the
enricher treat them as one more snapshot lane. Measurement script is small; we will hand it over on
request.
