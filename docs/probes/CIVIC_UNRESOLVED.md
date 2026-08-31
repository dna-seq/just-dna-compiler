# The CIViC variants nothing places — every class, with its disposition

**What this document is.** The residue of CIViC's germline direction corpus: the variants `civic
build` drops as `unresolvable_identity`, one class at a time, each with the measurement that decided
it. It began as the working for a single class — the nine that only a liftover could reach — and
kept that working in full when the rest of the residue was opened on 2026-09-01. The aggregate
numbers live in [CIVIC_SURVEY](CIVIC_SURVEY.md); the per-variant detail lives here.

**Two probe rounds, both dated.** The liftover class was probed **2026-08-31**; the name-only classes
**2026-09-01**. Every section says which round it belongs to, because the services move.


**This is evidence, never contract.** The decisions live in
[RM48](../ROADMAP_HISTORY.md#rm48--an-hg19-coordinate-has-no-supported-path-into-a-grch38-module-and-liftover-is-the-wrong-primitive)
and [RM153](../ROADMAP_HISTORY.md#rm153--the-identity-civic-does-not-publish-recovered-through-the-registry-rather-than-by-lifting-a-coordinate);
where this document and those disagree, they win.

**Basis for every number here** — the survey's own lesson about the denominator nobody declares.
Every count is over the **dated `01-Aug-2026` release**, which is **`accepted`-only** (4,878 evidence
rows) and gives 533 germline direction rows on 290 variants. The API default is `NON_REJECTED` and is
2.35× larger; a number from one surface is not comparable with a number from the other. Where the API
was consulted, it is said so on the line.

## Where the residue stands

At the 2026-08-31 cut the builder placed **237 of 290** variants and dropped 53. The 2026-09-01 round
put all 53 through a four-tier identity procedure — the ClinGen Allele Registry by constructed HGVS,
NCBI E-utilities, Ensembl's Variant Recoder, then the cited literature — and **34 of them resolve**:

| Class | Variants | Rows | Disposition |
|---|---:|---:|---|
| **Resolved by name** — a `c.`/protein fragment the source published but never registered | **33** | **33** | rsID and/or CAID and a GRCh38 coordinate, each cross-checked on a second service |
| **Resolved already** — variant 1770, whose answer the record carried | **1** | **1** | CA020360 / rs794727253 |
| Liftover-only (class A) | 9 | 13 | **closed 2026-08-31** — ceiling 13 rows, honest recovery at most one |
| No allele identity exists (class C) | 6 | 8 | correctly dropped; the name states a *class* of event |
| Two readings, nothing to choose (class D) | 2 | 2 | withheld; needs a curator and a paywalled paper |
| Conjunction-named (class E) | 2 | 2 | two alterations each, all four alleles identified; the record is not one identity |

**So coverage moves from 237/290 (81.7%) to 271/290 (93.4%) of variants, and 474/533 (88.9%) to
508/533 (95.3%) of evidence rows** — if the resolutions are adopted, which is a decision this document
does not take. Nineteen variants on 25 rows remain, and six of those are unreachable by construction.

**The procedure that did it is written up separately** as
[CIVIC_IDENTITY_PROTOCOL](CIVIC_IDENTITY_PROTOCOL.md) — a re-runnable protocol with the exact request
shapes, the discriminators ranked by the weight each can carry, the withholding rules each tied to the
record that forced it, and an explicit section on what it cannot do. What is here is the *disposition*
of each class, not the method.

**What the earlier round got wrong about this residue, and what the error cost.** The survey's first
pass concluded that the name-only classes were "close to a permanent floor rather than a backlog" and
that "the one remaining lever is worth 2 variants, not 31". Both are false. The mistake was a single
misread requirement: it looked for a `representative_transcript` **on the record**, found one on only
2 of the 31, and wrote the other 29 off. But the numbering frame a `c.` fragment needs is
establishable **per gene**, not per record — for VHL by reading the 114 already-resolved siblings in
the same corpus, elsewhere from MANE Select. A per-gene fact was tested as a per-record one, and 39
variants were declared permanently unreachable on the strength of it.

## Class A — the nine only a liftover could reach (2026-08-31, closed)

**Probed** 2026-08-31 against four surfaces, each named where it is used: the dated CIViC
`01-Aug-2026` bulk release (the file `civic build --release` consumes), CIViC's public GraphQL API,
Ensembl's REST services (`rest.ensembl.org` for GRCh38, `grch37.rest.ensembl.org` for the old
assembly), and the ClinGen Allele Registry (`reg.genome.network`, read-only `GET /allele?hgvs=`).
NCBI E-utilities was used for nine ClinVar searches, each one listed where its result is used. No
credential was needed anywhere.

**Basis, stated up front** — the survey's own lesson about the denominator nobody declares. Every
count below is over the **dated `01-Aug-2026` release**, which is **`accepted`-only** (4,878 evidence
rows). The API default is `NON_REJECTED` and is 2.35× larger; a number from one surface is not
comparable with a number from the other. Where the API was consulted, it is said so on the line.

**This is evidence, never contract.** The decisions live in [RM48](../ROADMAP_HISTORY.md#rm48--an-hg19-coordinate-has-no-supported-path-into-a-grch38-module-and-liftover-is-the-wrong-primitive)
and [RM153](../ROADMAP_HISTORY.md#rm153--the-identity-civic-does-not-publish-recovered-through-the-registry-rather-than-by-lifting-a-coordinate);
where this document and those disagree, they win. Nothing here re-argues either — RM153 already
re-closed liftover on a count of 131 variants and left the residue unexamined. This document opens
that residue and reports what is inside it.

**Why RM153 says 131 and the table below says 157.** They are the same class measured two ways. This
document originally read the gap as nightly-versus-dated, following the survey's two-column table;
re-measured on **2026-09-01** that explanation is wrong, and the survey now carries the correction.
The two files are identical on this slice, and each gives 159 under a reading that counts every
variant *carrying* a GRCh38 accession and 133 under the one that counts only accessions the
substitution parser can **read**. 157 is the strict reading's residue and is the number this document
uses throughout, because it is the one `civic build --release` acts on.

Companion: [CIVIC_SURVEY.md](CIVIC_SURVEY.md), whose closing section sized this class from the outside
("after every published identifier is tried the remainder is 157 variants, 102 of which a CAID would
place instead"). What follows is the other 55, and the nine of them that carry a coordinate.

Everything from here to *"Two cheaper recoveries"* is the 2026-08-31 round on this one class, kept in
full. Its conclusion did not move: **refuse the liftover**, and the residue it left is what the
2026-09-01 round opened.

### How the class was re-derived, with the counts at every stage

Re-derived here rather than quoted, using the **shipped** parsers (`civic_build.parse_rsids`,
`parse_grch38_substitution`, `CIVIC_GERMLINE_ORIGINS`, `CIVIC_DIRECTION_MAP`) rather than an ad-hoc
regex — the survey records a first pass that scored `".11:g." or ".12:g."` as GRCh38 and reported 208
reachable variants where the real figure is 40. The filter chain is `civic build`'s own, in its order:

| Stage | Rows | Distinct variants |
|---|---|---|
| Evidence rows in the release | 4,878 | — |
| …germline origin (`RARE_GERMLINE` ∪ `COMMON_GERMLINE`) | 811 | — |
| …on the direction axis (`CIVIC_DIRECTION_MAP`) | 533 | — |
| …joined to a single-variant profile | **533** | **290** |
| Reachable — an rsID in `variant_aliases` or a GRCh38 substitution in `hgvs_descriptions` | 329 | 133 |
| **Unreachable** (`unresolvable_identity`) | **204** | **157** |
| …of the unreachable, carrying a usable ClinGen CAID | — | 102 |
| …carrying the `unregistered` sentinel | — | 1 |
| …carrying no `allele_registry_id` cell at all | — | 54 |
| **Residue: no rsID, no GRCh38 HGVS, no usable CAID** | **61** | **55** |
| …of the residue, with no coordinate at all | 48 | 46 |
| **…of the residue, carrying a GRCh37 coordinate — the liftover-only class** | **13** | **9** |

Every figure to the `157` line reproduces the survey and `release.json` exactly, which is what says
the re-derivation is reading the same file the builder reads. The last three lines are new.

**The yield number, which is the one the recommendation hangs on: 13 evidence rows on 9 variants.**
That is 2.4% of the 533-row direction corpus, 0.27% of the release's 4,878 accepted rows, and the
**ceiling** — the most a perfect liftover could recover, before asking whether any of it is usable.

### The nine, and what each of them publishes

Straight from `VariantSummaries` in the dated release. `ref`/`alt` are `reference_bases` and
`variant_bases`; the CAID column is the raw `allele_registry_id` cell.

| id | gene | name | GRCh37 | span | ref | CAID cell | HGVS published | SO type | ev. rows |
|---|---|---|---|---|---|---|---|---|---|
| 230 | CHEK2 | `Loss-of-function` | 22:29083732-29137832 | 54,101 | — | *(empty)* | — | `loss_of_function_variant` | 1 |
| 485 | STK11 | `Loss` | 19:1205740-1228428 | 22,689 | — | *(empty)* | — | `loss_of_function_variant` | 1 |
| 715 | STK11 | `Mutation` | 19:1205740-1223074 | 17,335 | — | *(empty)* | — | `gene_variant` | 1 |
| 823 | EPCAM | `3' Exon Deletion` | 2:47612305-47614173 | 1,869 | — | *(empty)* | — | `disruptive_inframe_deletion` | 1 |
| 843 | VHL | `Exon 1-3 Deletion` | 3:10183532-10191649 | 8,118 | — | *(empty)* | `ENST00000256474.2:c.1-?_642+?del` | `exon_loss_variant` | 2 |
| 844 | VHL | `Exon 1 Deletion` | 3:10183532-10183871 | 340 | — | *(empty)* | `ENST00000256474.2:c.1-?_340+?del` | `exon_loss_variant` | 2 |
| 845 | VHL | `Exon 1-2 Deletion` | 3:10183532-10188320 | 4,789 | — | *(empty)* | `ENST00000256474.2:c.1-?_463+?del` | `exon_loss_variant` | 1 |
| 1939 | VHL | `Exon 3 Deletion` | 3:10191471-10193904 | 2,434 | — | *(empty)* | `NM_000551.3:c.464-?_642+?del` | *(none)* | 3 |
| 2099 | VHL | `V66del (c.197_220del)` | 3:10183728-10183742 | 15 | `TGAACTCGCGCGAGC` | **`unregistered`** | — | `inframe_deletion` | 1 |

All 13 evidence rows are `accepted`, all `Predisposition`/`Supports`, all `PubMed`-sourced, all
carrying a DOID. Nine of the 13 are level C; the four level-B rows are the CHEK2, the two STK11 and
the EPCAM ones. So the class is not low-grade — it is unusable for a different reason.

**The `unregistered` cell on 2099 is ClinGen's own vocabulary, and it is the only one of the nine that
was ever offered to the registry.** The other eight have an empty cell, which says nothing at all
about registrability — `@unreachable-not-absent` in the shape a data cell can take.

#### The API surface says exactly the same thing, which is what makes the negative wide enough

`@two-surfaces-two-denominators`: a "carries no identifier" finding measured on the bulk file is only
as wide as the bulk file, and the API carries an enrichment block (`myVariantInfo`) the download does
not. All nine were queried individually through `civicdb.org/api/graphql`
(`alleleRegistryId`, `clinvarIds`, `variantAliases`, `hgvsDescriptions`, `maneSelectTranscript`,
`myVariantInfo { dbsnpRsid clinvarHgvsGenomic }`):

- `dbsnpRsid`: **null for all nine.**
- `clinvarHgvsGenomic`: null for eight, `[]` for 2099.
- `alleleRegistryId`: null for eight, `"unregistered"` for 2099.
- `clinvarIds`: `["N/A"]` for 230/485/715 — the curator sentinel, i.e. *checked and none found* — and
  `[]` for the rest.
- `maneSelectTranscript`: **null for all nine**, against 362 of 620 over the API's germline set.
- `deprecated` and `flagged` are false for all nine: CIViC still stands behind these records.

`myVariantInfo` being absent for eight of nine is itself informative. MyVariant.info is allele-keyed;
these records are not alleles, so there is nothing for it to key on.

### Question 1 — is it a genotypable event at all?

Answered by measurement, not by reading the names: every endpoint was compared against the named
transcript's own annotation on GRCh37 (`grch37.rest.ensembl.org/lookup/id/<tx>?expand=1`), and the
gene span was fetched for context.

| id | interval start sits on | interval stop sits on |
|---|---|---|
| 230 | `ENST00000328354.6` transcript start **and** exon 1 start | transcript end **and** exon 15 end |
| 485 | `ENST00000326873.7` transcript start **and** exon 1 start | transcript end **and** exon 10 end |
| 715 | `ENST00000326873.7` transcript start | **no landmark** — 90 bp inside exon 8 |
| 823 | `ENST00000263735.4` exon 8 start | transcript end **and** exon 9 end |
| 843 | `ENST00000256474.2` **CDS start** (c.1) | **CDS end** (c.642) |
| 844 | CDS start (c.1) | exon 1 end |
| 845 | CDS start (c.1) | exon 2 end |
| 1939 | exon 3 start | transcript end **and** exon 3 end |
| 2099 | 143 bp before the end of exon 1 — a real position inside it | 129 bp before the end of exon 1 |

**Eight of the nine intervals are annotation addresses, not event breakpoints.** Variant 230's
interval *is* the CHEK2 transcript, to the base. Variant 485's *is* the STK11 transcript, to the base.
Variant 843's is the VHL coding sequence, c.1 to c.642, exactly. These coordinates were not observed
in a sample; they were computed from a transcript model and stored in the coordinate columns.

That decides question 1 for the three categorical records without reference to any build:

> **230 `Loss-of-function`, 485 `Loss` and 715 `Mutation` are gene-level assertions, and no VCF
> genotype can satisfy them.** They name a *class* of events ("some loss-of-function change in this
> gene"), and the format's unit is one rule keyed to one identity — `variant_key` is
> `rsid`, else `chrom:start:ref[:alts]`. There is no genotype a consumer could hold that answers
> "is this gene lost". 715's own SO type is `gene_variant`, and its stop matches no boundary of the
> transcript it names at all. **This is a rejection on the event, not on the build**, and a liftover
> that placed all three perfectly would leave them exactly as unusable.

The five exon-level records (823, 843, 844, 845, 1939) are events, but **imprecise ones, by the
source's own statement**: four publish HGVS of the form `c.1-?_340+?del`, where `-?`/`+?` is HGVS's
notation for *the breakpoint is unknown*. The interval is the exon/CDS span standing in for
breakpoints nobody measured. 823 publishes no HGVS at all and its name does not say which exons.

Variant 2099 is the only one of the nine that names a specific, precise event — and it disagrees with
itself; see below.

**The obvious objection, and the search that answers it.** "But ClinVar is full of VHL exon
deletions" — it is, and that is not the same thing. Three E-utilities searches of `db=clinvar`:
`VHL[gene] AND "exon 1" AND deletion[Type of variation]` returns **26**,
`VHL[gene] AND "whole gene"` returns **2**, `EPCAM[gene] AND deletion[Type of variation]` returns
**127**. Every one of those records is a *particular* deletion with *its own* measured breakpoints.
CIViC's `Exon 1 Deletion` is the class they belong to, and picking one of the 26 to stand for it would
be the same fabrication as inventing a length — a specific allele substituted for the general claim
the evidence rows actually make. Scope: these three searches say what ClinVar holds under those
terms; they are not a claim that no ClinVar record matches CIViC's records, which is unanswerable
because CIViC's records name no breakpoints to match on.

### Question 2 — the correct GRCh38 interval, by route, three-valued

Route (a), Ensembl's assembly map, `rest.ensembl.org/map/human/GRCh37/<region>/GRCh38`, was run for
all nine. Outcomes recorded in the house vocabulary rather than a new one — the four members of
`grch37.VALID_RECOVERY_OUTCOME` shaped as this question needs them: `mapped_single`, `mapped_split`
(more than one mapping segment), `unmapped` (zero), `unchecked` (5xx, transport error, timeout).

| id | outcome | GRCh38 interval from the map | src bp | dst bp |
|---|---|---|---|---|
| 230 | `mapped_single` | 22:28687744-28741844 | 54,101 | 54,101 |
| 485 | `mapped_single` | 19:1205741-1228429 | 22,689 | 22,689 |
| 715 | `mapped_single` | 19:1205741-1223075 | 17,335 | 17,335 |
| 823 | `mapped_single` | 2:47385166-47387034 | 1,869 | 1,869 |
| 843 | `mapped_single` | 3:10141848-10149965 | 8,118 | 8,118 |
| 844 | `mapped_single` | 3:10141848-10142187 | 340 | 340 |
| 845 | `mapped_single` | 3:10141848-10146636 | 4,789 | 4,789 |
| 1939 | `mapped_single` | 3:10149787-10152220 | 2,434 | 2,434 |
| 2099 | `mapped_single` | 3:10142044-10142058 | 15 | 15 |

**Nine of nine map cleanly, in one segment, with the length preserved. The mechanics are not the
problem, and saying so plainly is the point** — the refusal below is not "liftover would fail".

The `unchecked` state is not decorative: the GRCh38 lookups for CHEK2's transcript and for two
sequence reads returned **500** on the first attempt and had to be re-run. Read as "absent" they would
have said the transcript does not exist, which for one of them would have been true by coincidence.

Route (b), the exon coordinates of the named transcript on both builds, is the principled route for an
exon-level event — it re-derives identity from *transcript + exon number* rather than converting a
number, so it is not liftover at all. It disagrees with route (a) on four of the eight:

| id | landmark | route (b): current GRCh38 transcript | route (a): the map | difference |
|---|---|---|---|---|
| 485 | transcript start / exon 1 start | 1,205,778 | 1,205,741 | **+37 bp** |
| 485 | transcript end / exon 10 end | 1,228,431 | 1,228,429 | +2 bp |
| 715 | transcript start | 1,205,778 | 1,205,741 | **+37 bp** |
| 823 | transcript end / exon 9 end | 47,387,020 | 47,387,034 | **−14 bp** |
| 1939 | transcript end / exon 3 end | 10,153,667 | 10,152,220 | **+1,447 bp** |
| 843/844/845 | CDS start, exon 1 end, exon 2 end, CDS end | 10,141,848 / 10,142,187 / 10,146,636 / 10,149,965 | identical | 0 |

The mechanism is not a liftover error. **The annotation moved between builds independently of the
sequence map**: `ENST00000326873` is version 7 on GRCh37 and version 12 on GRCh38, `ENST00000263735`
went 4 → 9, `ENST00000256474` went 2 → 3, and the transcript models were re-annotated at their ends.
So for 1939, "the last exon of VHL" is 2,434 bp on the build CIViC curated against and 3,881 bp on
current GRCh38 — and *the deletion CIViC is describing is defined by the exon, not by the number*. A
lifted 2,434 bp interval is a faithful conversion of a stale annotation.

CHEK2's transcript cannot be asked at all: `ENST00000328354` **404s on GRCh38** ("ID not found"), and
`/archive/id` says it was last current in **release 96**, latest version `.10`, with an empty
`possible_replacement` list. CHEK2's current GRCh38 canonical is `ENST00000404276.6` at
22:28687743-28741820, which differs from the lifted interval by −1 bp at the start and −24 bp at the
end. Variant 230's named transcript no longer exists; its interval can be converted but not
re-derived.

Route (c), web search, was not needed for any of the nine: routes (a) and (b) plus the allele registry
answered every one of them, and a search result is a weaker source than either.

### Variant 2099, in full — the one precise event, and it contradicts itself

The only member of the class that names a specific allele, and the sharpest exhibit in this document.

What CIViC publishes: `start=10183728`, `stop=10183742`, `reference_bases=TGAACTCGCGCGAGC` (15 bases),
`variant_bases` **empty**, name `V66del (c.197_220del)`, alias `197DEL24`.

Measured facts, each with its method:

- **The 15 bases are real.** `grch37.rest.ensembl.org/sequence/region/human/3:10183728..10183742`
  returns `TGAACTCGCGCGAGC` — CIViC's `reference_bases` is the genome, exactly, at the coordinates it
  gives. The coordinate pair is internally consistent: 10183742 − 10183728 + 1 = 15 = `len(ref)`.
- **The name says 24 bases.** VHL's CDS starts at 10183532 on GRCh37 (Ensembl `Translation.start` for
  `ENST00000256474.2`), so c.197 = 10183532 + 196 = **10183728** — CIViC's `start`, to the base — and
  c.220 = **10183751**, nine bases past CIViC's `stop`. The alias `197DEL24` says 24 as well. The
  genome over the 24 bp span reads `TGAACTCGCGCGAGCCCTCCCAGG`.
- So `start` agrees with the name and `stop` does not, and **the record describes two different
  events**: a 24 bp in-frame deletion of eight codons, and a 15 bp deletion that is not codon-aligned.
  A third reading is in the name itself — "V66del" names *one* residue.
- **Only one of the two has an identity.** The ClinGen Allele Registry, asked by HGVS:

  | query | registry answer |
  |---|---|
  | `NM_000551.3:c.197_220del` (CIViC's own name) | **CA645524685** — `NM_000551.4(VHL):c.198_221del (p.Asn67_Val74del)` |
  | `NC_000003.12:g.10142044_10142067del` (the 24 bp span on GRCh38) | **CA645524685** — the same allele |
  | `NC_000003.11:g.10183728_10183751del` (the 24 bp span on GRCh37) | **CA645524685** — the same allele |
  | `NC_000003.11:g.10183728_10183742del` (**CIViC's coordinate pair**) | `_:CA` — **no CAID**, and a different allele, `c.197_211del (p.Val66_Pro71delinsAla)` |

  CA645524685 publishes its own coordinates on **GRCh38, GRCh37 and NCBI36**
  (`NC_000003.12:g.10142045_10142068del`, `NC_000003.11:g.10183729_10183752del`) and one external
  record, COSMIC `COSM17706`. It is not in ClinVar and has no rs-number: **five** ClinVar E-utilities
  searches for the c. and protein spellings (`VHL[gene] AND 197_220del`, `… AND "c.197_220del"`,
  `… AND "c.197_220del"[Variant name]`, `… AND "V66del"`, `"NM_000551.4(VHL):c.197_220del"`) each
  returned **0**, while a sixth — a position-range search at the GRCh38 locus,
  `3[Chromosome] AND 10142044:10142067[Base Position for Assembly GRCh38]` — returns **59** unrelated
  records, so the searches reach the right place and the zeros are about this allele.

**Read that table again, because it is the whole argument in four lines.** Lifting the coordinate
CIViC published produces a real, well-formed, correctly converted GRCh38 interval that names an allele
**nobody has registered and that has a different protein consequence from the one the source is
talking about**. Reading the name CIViC published produces a registered, build-independent identity
that carries its own GRCh38 coordinate. The liftover works perfectly and gets the wrong variant.

CIViC's `allele_registry_id` cell says `unregistered`; the registry, asked today, registers it. The
cell is a dated statement, not a permanent one.

**And the rsID-recovery trap is live at this locus.** `grch37.recover_rsid("3", 10183728,
ref="TGAACTCGCGCGAGC")` returns `none` with the note that one dbSNP record overlaps the position
without starting at it with those alleles. The same call **without** `ref` returns
`recovered rs2125124970` — which is a *SNV* (`T > C/G`) that happens to start there. Anchoring is what
keeps the answer honest: `@rsid-not-per-allele`, and `@vkey-precedence`'s rule that alleles are passed
when minting an identity. A liftover-plus-rsID-recovery pipeline that dropped the anchor would have
labelled this deletion with an unrelated SNV's rs-number.

### Question 3 — could any of this be expressed once lifted?

Answered by running the real compiler, not by reading it. A throwaway spec was compiled with four
rows, each a candidate spelling of a lifted interval (`uv run just-dna-compiler validate` / `compile`
/ `compile --strict`, module `genome_build: GRCh38`):

| spelling | authored as | result |
|---|---|---|
| sized symbolic allele | `3,10141848,,<DEL:340>` | **compiles clean, no warning** |
| lengthless symbolic allele | `3,10141849,,<DEL>` | warned and **DROPPED** under `best_effort`, **refused** under `--strict` |
| bare locus, no alleles | `22,28687744,,` | **compiles clean, no warning** |
| the 24 bp deletion spelled out | `3,10142043,TGAACTCGCGCGAGCCCTCCCAGGT,T` | **compiles clean** |

The lengthless refusal is the documented behaviour (`@symbolic-alleles`), and its message is the
warning-catalogue text a consumer greps. The other three results are the finding:

- **`<DEL:340>` compiles clean, and the 340 is a fabrication.** The guard is that a length must be
  *stated*, not that it is *true* — and it cannot be otherwise, since the source's own HGVS says the
  breakpoints are unknown. Authoring `<DEL:340>` for 844 would publish a precision the source
  explicitly refuses, and nothing in the compiler can notice. `@symbolic-alleles` says it in the
  general case — "a summary length is not an event size" — and this is that case, with a number.
- **A bare `chrom+start` row compiles clean too.** So 230's transcript address would enter a module as
  an ordinary variant row, claiming a locus, and `fully_resolved: True` would be printed over it.
  The format has no defence against a gene-level assertion wearing a coordinate.
- The one row that compiles *honestly* is the one whose sequence is known — 2099's 24 bp deletion,
  spelled in VCF's padded form. That row does not need a liftover: its identity comes from the name.

So the answer to question 3 is: **five of the nine cannot be expressed** (three because they are not
events, two more — 823 and 1939 — because their extent is defined by an annotation that moved), two
more (843/845, and 844) could be expressed **only by inventing a length**, and one (2099) can be
expressed, from a route that has nothing to do with lifting.

### Question 4 — would `pyliftover` help?

Tried, in a throwaway venv **outside the repo** (`python3 -m venv` + `pip`, never `uv pip`, and
nothing added to any `pyproject.toml`). Version 0.4.1. Measured, not argued:

- **It agrees with Ensembl on all 18 endpoints of the nine intervals** — same chromosome, same
  positions, one hit each, after the 1-based↔0-based conversion (`convert_coordinate(chr, start-1)`,
  read back `+1`; `@start-1based` — the instinctive `-1` belongs *here*, at a foreign library's
  0-based boundary, and nowhere else in this tree).
- So it buys **no accuracy** that `rest.ensembl.org/map` does not already give, and the map endpoint
  gives strictly more: it maps a **whole interval** and returns the segment structure, so a region
  that breaks into pieces across the builds comes back as several mappings. Two independent point
  lifts cannot see that; they return two numbers and no information about the interior. (For these
  nine it would not have mattered — all nine mapped in one segment with the length preserved. That is
  a fact about these nine, not about intervals.)
- **It downloads an unpinned asset at import.** `LiftOver("hg19","hg38")` fetched
  `hg19ToHg38.over.chain.gz` (227,698 bytes) from UCSC into `~/.pyliftover/`. Nothing pins a version,
  nothing records provenance, and the fetch happens wherever the object is constructed — which in
  this tree would be a network call inside whichever package imported it.
- **Its failure modes are three-valued by accident, and one of them is a crash.** Off the end of a
  real contig returns `[]`; an unknown contig returns `None`; and a chain file that does not exist
  raises `AttributeError: 'NoneType' object has no attribute 'readline'` from inside the library.
  RM48 recorded the failure as "an empty list both for unmapped and for a missing chain file"; in
  0.4.1 the missing chain is an unhandled internal error instead. Either way the contract is the one
  `@client-exception-contract` describes — a library leaking its internals has no contract, and a
  caller would have to build the three states on top of it.

**Verdict: no.** It would add a dependency, an unpinned 220 KB asset, a runtime download and an
exception-translation layer, to reproduce numbers a permitted, already-used REST service returns with
more structure. And accuracy was never the failing.

### What can actually be recovered, per variant

| id | genotypable event? | best GRCh38 answer, and its route | recoverable identity | verdict |
|---|---|---|---|---|
| 230 CHEK2 `Loss-of-function` | **no** — a gene-level class | 22:28687744-28741844 (map); the named transcript is retired on GRCh38, so route (b) is unavailable | none | not an event |
| 485 STK11 `Loss` | **no** — a gene-level class | 19:1205741-1228429 (map), or 1205778-1228431 (current transcript) — the routes differ | none | not an event |
| 715 STK11 `Mutation` | **no** — SO type `gene_variant` | 19:1205741-1223075 (map); its stop is not a boundary of anything | none | not an event |
| 823 EPCAM `3' Exon Deletion` | an event, extent undefined; the name does not say which exons | 2:47385166-47387034 (map) vs …-47387020 (exons); 14 bp apart | none | unexpressible |
| 843 VHL `Exon 1-3 Deletion` | an event, breakpoints unknown (`c.1-?_642+?del`) | 3:10141848-10149965 — **both routes agree** (the VHL CDS) | none; only an invented `<DEL:8118>` | expressible only by fabrication |
| 844 VHL `Exon 1 Deletion` | same | 3:10141848-10142187 — both routes agree | none; only `<DEL:340>` | expressible only by fabrication |
| 845 VHL `Exon 1-2 Deletion` | same | 3:10141848-10146636 — both routes agree | none; only `<DEL:4789>` | expressible only by fabrication |
| 1939 VHL `Exon 3 Deletion` | same | 3:10149787-**10152220** (map) vs -**10153667** (exon 3 today); **1,447 bp apart** | none | unexpressible |
| 2099 VHL `V66del (c.197_220del)` | **yes**, but the record contradicts itself | 3:10142044-10142067 (24 bp, from the name) — **not** 10142044-10142058 (15 bp, from the coordinate) | **CA645524685**, from CIViC's published name, carrying its own GRCh38 coordinate | recoverable — **without any liftover** |

**One of nine has a recoverable identity, and the route that recovers it is not liftover.** Lifting
the coordinate of that same variant produces the wrong allele.

### What the evidence supports

**Refuse the liftover capability.** Not because it would be inaccurate — measured, it is exact, and
two independent implementations agree to the base — but because every one of its outputs is either
not an event, an event whose extent the source refuses to state, or an event whose own name already
carries a better identity:

1. **The ceiling is 13 evidence rows on 9 variants**, 2.4% of the direction corpus, and the recovery
   after the event analysis is **at most 1 variant / 1 row** — the one liftover gets wrong.
2. **Three of the nine are gene-level assertions**, rejected on the event, independently of build.
3. **Five are imprecise by the source's own HGVS.** The `?` is not decoration: the ClinGen registry
   refuses those expressions outright — `HgvsParsingError`, *"HGVS expression must be unambiguous,
   unknown parameters are not allowed"*. An allele registry that cannot hold them is a stronger
   statement than a count: these events have **no allele identity on either build**.
4. **The coordinates are annotation addresses, and annotation moved.** Four of eight intervals get a
   different GRCh38 answer from the map than from the transcript they name, by up to 1,447 bp. A
   lifted interval would be a stale annotation converted faithfully.
5. **The format cannot defend itself against the result.** A fabricated `<DEL:340>` and a bare
   gene-span locus both compile clean, with no warning, in both modes.
6. **The hazard is unchanged and is now demonstrated rather than asserted.** RM48's rule — a lifted
   coordinate is the row's sole identity with nothing to check it against — has a worked instance
   here: variant 2099, where the only independent check available (the registry) says the lifted
   coordinate names a different allele from the one the source is describing.

**What the nine should be recorded as instead: nothing — which is what the builder already does.**
They are dropped as `unresolvable_identity`, counted in `release.json`, and that is the correct
outcome for all nine. No code change is needed and none is proposed here; building anything for this
class would be building the thing the measurement refuses. What is worth carrying forward is that this
residue is now *characterised* and not merely counted, so a future identity pass knows what it is
looking at:

- **A CAID pass (RM153) cannot reach the nine**, by construction — eight publish no CAID and the
  ninth publishes `unregistered`. The nine are outside its scope, and its sizing should say so.
- **Five of the nine can never be reached by any identity pass**, because an unambiguous identity does
  not exist for them. That is a permanent floor on CIViC's germline reach, not a gap to close.

### Two cheaper recoveries, found while sizing this one

Both measured over the same 55 residual variants, both reported as sizing rather than as proposals —
they belong to RM153, which decides them.

- **Two variants publish an rs-number as their *name*** and nowhere else: 2671 `CDKN1A rs1801270` and
  3313 `CDKN1A rs1059234`, one evidence row each. `parse_rsids` reads `variant_aliases` only, so they
  drop as `unresolvable_identity`. Reading a name that is *entirely* one rs-number would recover 2
  variants / 2 rows — twice what liftover could honestly recover from the nine. The guard has to be
  the whole-cell shape, not a search: the same residue contains `P81S (c.241C>T) and L188V (c.562C>G)`
  and `R167Q(c.500G>A) and c.464-94T>A`, which are the conjunction class the survey's item 5 warns
  about, and CIViC elsewhere names a variant `rs1801270 and rs1059234`.
- **One variant publishes a GRCh38 accession the parser cannot read.** Variant 1770
  (`VHL N150fs (c.449del)`) carries `NC_000003.12:g.10146622del` — a **deletion**, where
  `parse_grch38_substitution` reads substitutions only. It is also the malformed record the survey
  names (`referenceBuild=GRCH37`, `start` and `referenceBases` present, `chromosome` **null**), so it
  is `@identity-whole-or-none` and a parser gap in one row.
- 31 of the 55 carry a `c.` HGVS token inside their **name** rather than in `hgvs_descriptions`
  (`N150fs (c.449del)`, `D143fs (c.430delG)`). Whether a name plus a transcript resolves through the
  allele registry was **not measured** and is not claimed here; it is stated only because it is the
  obvious next question and it is unanswered.

## Class B — 33 variants whose identity the source published and never registered (2026-09-01)

**Probed** 2026-09-01 against four surfaces: the ClinGen Allele Registry (`reg.genome.network`,
read-only `GET /allele?hgvs=`), NCBI E-utilities (`esearch`/`esummary`/`elink` over `clinvar`,
`snp`, `pubmed`), Ensembl's Variant Recoder (`rest.ensembl.org/variant_recoder/human/<hgvs>`), and
the papers each evidence row cites. No credential anywhere. Every resolution's exact queries are
recorded per variant in the round's result files; what is reproduced here is the answer and the
cross-check.

The whole class is one shape: **CIViC's variant `name` carries a `c.` or protein fragment, and the
identifier columns beside it are empty.** The name is the identity; nothing had to be recovered from
a coordinate, and nothing was lifted.

### The numbering frame, which is what made the class reachable

A `c.` fragment means nothing without the transcript it is numbered against. The earlier round looked
for `representative_transcript` **on the record**, found it on 2 of 31, and declared the rest
unreachable. The frame is a property of the **gene**:

- **VHL** — established empirically from the 114 variants in this same corpus that CIViC *did*
  resolve. Each publishes both a name and an `ENST00000256474.2:c.…` expression, and they agree
  throughout: variant 794 is named `E55= (c.165G>A)` and publishes `ENST00000256474.2:c.165G>A`. So
  CIViC's VHL numbering is `NM_000551.3` / `ENST00000256474.2`, measured rather than assumed.
- **Everything else** — MANE Select, cross-checked against the numbering the record's own name
  implies. CDKN2A needed the check: p16 and p14ARF are two MANE transcripts with two CDS numberings,
  and the exon table picks p16.

**The transcript-version story is a trap, and this document previously helped set it.** A prior
reading held that `NM_000551.4` shifts VHL CDS numbering by one against `NM_000551.3`, because
`c.197_220del` submitted against `.3` comes back titled `c.198_221del`. Measured on 2026-09-01, that
is false: the two CDSes are byte-identical, and submitting either version returns the **same** CAID:

```
NM_000551.3:c.197_220del  ->  CA645524685   (returned as NM_000551.3:c.198_221del)
NM_000551.4:c.197_220del  ->  CA645524685   (identical)
NM_000551.3:c.499C>T      ->  CA020450
NM_000551.4:c.499C>T      ->  CA020450      (identical)
```

The shift is HGVS's 3′ rule renormalizing a deletion inside a repeat, not a version effect — c.197
and c.221 are both T. The illusion persists because the registry titles in the newest version it
knows *and* independently renormalizes, so the two look causally linked. Believing the version story
invites "correcting" a whole gene's positions by one and teaches a reader to wave through a genuine
one-base mismatch as an artefact. Neither failure announces itself. The measurement was repeated
across nine genes: the CDS *mRNA offset* moves on a version bump (CDKN2A 307→31, DICER1 239→346) but
`c.` numbering is CDS-relative and is untouched — reading the GenBank `CDS` line and concluding
"everything shifted" is exactly the trap.

### The 20 VHL indels named by a `c.` fragment

| id | name | rsID | CAID | GRCh38 (VCF-padded) | protein returned |
|---|---|---|---|---|---|
| 1768 | `L129Q (c.386insAGA)` | — | CA2586965635 | 3:10146558 `C`>`CAGA` | p.Leu129delinsGlnMet |
| 1779 | `R167fs (c.502insTTGTCCGT)` | rs398123483 | CA020458 | 3:10149824 `G`>`GTTGTCCGT` | p.Ser168LeufsTer5 |
| 1844 | `D143fs (c.430delG)` | rs869025651 | CA357015 | 3:10146603 `GG`>`G` | p.Gly144AspfsTer15 |
| 1893 | `F91* (c.272_273delinsAA)` | — | CA2499307077 | 3:10142119 `TC`>`AA` | p.Phe91Ter |
| 1948 | `R69fs (c.204insG)` | rs2470158072 | CA913189244 | 3:10142051 `G`>`GG` | p.Arg69AlafsTer? |
| 1949 | `G144fs (c.432insG)` | — | CA2573106040 | 3:10146604 `G`>`GG` | p.Gln145ThrfsTer29 |
| 1960 | `L140fs (c.417_418delTC)` | rs869025649 | CA357039 | 3:10146591 `CTC`>`C` | p.Leu140GlnfsTer3 |
| 2014 | `P61fs (c.183insC)` | — | CA2586965632 | 3:10142030 `C`>`CC` | p.Val62ArgfsTer? |
| 2023 | `N150fs (c.449_462del)` | — | CA658820719 | 3:10146621 `AATATCACACTGCCA`>`A` | p.Asn150SerfsTer19 |
| 2091 | `T152fs (c.455insA)` | — | CA2586965646 | 3:10146627 `A`>`AA` | p.Thr152AsnfsTer22 |
| 2136 | `H125fs (c.374insA)` | — | CA2499307153 | 3:10146547 `A`>`AA` | p.His125GlnfsTer7 |
| 2447 | `V66Gfs*89 (c.197_209del)` | — | CA2497028944 | 3:10142043 `GTGAACTCGCGCGA`>`G` | p.Val66GlyfsTer? |
| 2455 | `G114Vfs*45 (c.339delA)` | — | CA645509026 | 3:10142185 `GA`>`G` | p.Gly114ValfsTer? |
| 2930 | `106insR (c.316insGCC)` | rs869191373 | CA916832608 | 3:10142171 `C`>`CCGC` | p.Arg108dup |
| 3143 | `F148* (c.443_455delinsA)` | — | CA2573050544 | 3:10146616 `TTGCCAATATCAC`>`A` | p.Phe148Ter |
| 3184 | `V62Cfs*5 (c.180del)` | rs730882037 | CA020069 | 3:10142026 `GG`>`G` | p.Val62CysfsTer5 |
| 3245 | `C77fs (c.230del)` | — | CA2573106239 | 3:10142076 `TG`>`T` | p.Cys77SerfsTer? |
| 3741 | `V87fs (c.255_256insC)` | rs864622545 | CA16602181 | 3:10142105 `C`>`CC` | p.Val87ArgfsTer? |
| 3743 | `N150fs (c.448delA)` | rs794727253 | CA020360 | 3:10146621 `AA`>`A` | p.Asn150IlefsTer9 |
| 3744 | `E55fs (c.163delG)` | rs869025615 | CA432536363 | 3:10142009 `GG`>`G` | p.Glu55ArgfsTer12 |

Five of these were re-verified independently against the registry after the fact — CA020360, CA357015,
CA658820719, CA020069, CA2586965635 — including the 0-based interstitial → 1-based VCF-padded
conversion. All five matched exactly.

**Only 9 of the 20 carry an rs-number at all.** The premise that a name-only record must be a
well-known allele with a forgotten rs-number is false: the *identity* exists for all 20, the *fame*
for fewer than half. Nine of the resolved CAIDs carry no external record of any kind.

### The 13 substitutions, splice and cDNA variants

| id | gene | name | rsID | CAID | GRCh38 |
|---|---|---|---|---|---|
| 788 | CHEK2 | `IVS2+1G>A` | rs121908698 | CA288309 | 22:28725242 `C`>`T` |
| 804 | RUNX1 | `R135FSX177` | rs587776810 | CA248618 | `NC_000021.9:g.34880554del` |
| 2046 | VHL | `V155L (c.463G>C)` | rs869025659 | CA351754415 | 3:10146636 `G`>`C` |
| 2051 | DICER1 | `D1709N` | rs1595331264 | CA390865395 | 14:95094127 `C`>`T` |
| 2195 | DICER1 | `D1709G` | rs1555366979 | CA390865393 | 14:95094126 `T`>`C` |
| 2196 | DICER1 | `D1709E` | rs1890098663 | CA390865390 | 14:95094125 `A`>`T` |
| 2459 | VHL | `L178P (c.532C>T)` | rs5030822 | CA351756245 | 3:10149856 `T`>`C` |
| 2638 | CBL | `Y371H` | rs267606706 | CA123492 | 11:119278181 `T`>`C` |
| 2851 | SMAD4 | `R361C` | rs80338963 | CA128095 | 18:51065548 `C`>`T` |
| 2884 | CDKN2A | `c.151-1G>C` | rs730881677 | CA299032 | 9:21971209 `C`>`G` |
| 2959 | CHEK2 | `R474C c.1420C>T` | rs540635787 | CA288280 | 22:28694073 `G`>`A` |
| 3002 | NF2 | `c.1396C>T` | rs74315504 | CA021327 | 22:29674891 `C`>`T` |
| 4968 | TP53 | `R72P` | rs1042522 | CA178298 | `NC_000017.11:g.7676154G=` |

Two rows are deliberately not written as a `ref`>`alt` tuple. **804 is a one-base deletion**, given in
the registry's own form; the left-anchored VCF row for the same allele is `21:34880553 GT>G`, which is
what ClinVar VCV000014466 publishes, and the two agree. **4968 is a reference-identity allele** — see
below. Nineteen of nineteen constructed expressions agreed between the registry and Ensembl's Variant
Recoder.

### Four names that are wrong, and would corrupt a consumer silently

These are worth more than the count. Each resolved cleanly *at both readings*, so nothing in a lookup
flags the error; only a discriminator outside the lookup settles it.

- **4968 `TP53 R72P` has reference and alternate inverted.** Codon 72 is `CCC` = **Pro** on GRCh38, so
  the allele CIViC names is the reference itself: CA178298, `NC_000017.11:g.7676154G=`, `c.215C=`.
  The clean test is to submit both directions — `c.215C>G` is accepted, `c.215G>C` returns HTTP 400
  *"reference sequence is incorrect"*. Note the consequence for this format: a schema requiring
  `ref != alt` cannot represent what CIViC means here. That is a property of the consumer, not of the
  record.
- **788 `CHEK2 IVS2+1G>A` cannot be converted structurally.** The exon table gives `c.319+1`; the
  right answer is `c.444+1`, because legacy papers number CHEK2 exons from the first *coding* exon.
  Both readings are real registered alleles about 9 kb apart. Only ClinVar's `OtherName` list — one
  record carrying both `IVS2DS, G-A, +1` and `IVS3+1G>A` — resolves it.
- **2459 `VHL L178P (c.532C>T)`: the two halves of the name are two different real alleles.**
  `c.532C>T` is *synonymous* (CTG→TTG); `c.533T>C` gives Pro. Both resolve. A builder trusting the
  parenthesised cDNA notation would mint a synonymous variant under a missense label. And CIViC
  already publishes the right allele as its **own variant 1748**, `L178P (c.533T>C)`, with rs5030822
  filled in.
- **804 `RUNX1 R135FSX177` names a consequence where the allele is of a different kind.** MANE
  residue 135 is Gly (legacy RUNX1b numbering, +27), and the allele is an *intronic* splice-donor
  deletion that ClinVar classifies as `intron variant` with no protein change at all.

### Two rs-numbers that do not identify the allele

`@rsid-not-per-allele`, with instances. **2196 `DICER1 D1709E`**: chr14:95094125 carries both `A>T`
and `A>C`, both spelling p.Asp1709Glu, and both carry rs1890098663 — so neither the rs-number nor the
protein name identifies the allele, and the resolution rests on a single line of evidence (ClinVar's
citation link for the record's own PMID). **4968 `TP53 R72P`**: the position carries exactly two
alleles, the two halves of CIViC's name, and both carry rs1042522 (CA178298 for Pro, CA000072 for
Arg). The rs-number cannot say which; the direction test can, and says CIViC means the reference.

### Three records that duplicate CIViC's own resolved entries

The identity was in CIViC's table the whole time, one row over:

| unresolved record | duplicates | shared identity |
|---|---|---|
| 3743 `N150fs (c.448delA)` | **1770** `N150fs (c.449del)` | CA020360 / rs794727253 — both normalize to `NC_000003.12:g.10146622del` |
| 2459 `L178P (c.532C>T)` | **1748** `L178P (c.533T>C)` | rs5030822 / CA351756245 |
| 4210 (the `R167Q` half) | **1739** `R167Q (c.500G>A)` | rs5030821 / CA020454 |

The 3743≡1770 collision is the one with downstream consequences: an identity pass that reaches both
maps **two CIViC variant ids onto one allele**, which touches camp grouping (two records that would
have counted as two subjects become one) and the drafter's `already_present` path. It is stated here
as a measured collision, not as a repair.

## Class C — six records for which no allele identity exists (2026-09-01)

Dropping these is **correct behaviour**, not a gap. Each names a *class* of event rather than an
allele, so there is nothing for an allele registry to hold. The useful distinction is *why* the
identity is absent, and it splits three ways — a source that never measured breakpoints and a source
that measured them and had them generalised away are different findings.

| id | gene | name | rows | PMID | why no identity exists |
|---|---|---|---:|---|---|
| 708 | BRCA2 | `TRUNCATING MUTATION` | 1 | 16088935 | **measured, then generalised away.** Even the specific event is not singular: ClinVar holds three *different* inserted sequences at the same `c.156_157` site, because an Alu insertion's inserted sequence differs per event. Recovering "the" identity would need the paper's own sequence |
| 709 | BRCA1 | `Alu insertion` | 1 | 16088935 | **measured, coordinates not recoverable** from the accessible record. Not resolved by substituting one of the 25 BRCA1 Alu records — that would be fabrication |
| 2036 | VHL | `Null (Partial deletion of Exons 2 & 3)` | 1 | 20846682 | **never measured** — evidenced from the paper's own table, not from CIViC's silence. Three families sit under one label |
| 2182 | VHL | `Null (Large deletion)` | 3 | 8634692, 20660572, 7728151 | **never measured**, three times over — Southern blot, three unrelated cohorts aggregated under one name |
| 2367 | VHL | `3p26.3-25.3 11Mb del` | 1 | 26365017 | **measured at a resolution that is not allele resolution.** Array-CGH; a probe-bounded interval has no ref/alt. Deliberately not matched to any ClinGen or ClinVar CNV region |
| 2439 | VHL | `Rearrangement` | 1 | 24132471 | **never measured** — the cited paper is a statistics paper, not a molecular one |

2182 also carries an aggregation defect worth naming on its own: three evidence rows from three
unrelated cohorts share one variant record, so a consumer counting subjects would count one.

## Class D — two records with two readings and nothing to choose between them (2026-09-01)

Both are VHL frameshifts written in legacy `c.<N>ins<SEQ>` notation, which does not say whether the
inserted bases go before or after base N. **Both readings exist as separately registered real
alleles.** This is the one class where the procedure ran to the end of all four tiers and returned
`not_found` rather than an answer.

| id | name | PMID | reading | HGVS (`NM_000551.3`) | CAID | protein | external |
|---|---|---|---|---|---|---|---|
| 1955 | `P71fs (c.211insT)` | 9829912 | after | `c.211_212insT` | CA2501268513 | p.Pro71LeufsTer? | none |
| | | | before | `c.210_211insT` | CA2586965638 | p.Pro71SerfsTer? | none |
| 2131 | `Q73fs (c.214insGCCC)` | 17024664 | before (tandem dup) | `c.210_213dup` | CA2573048346 | p.Ser72AlafsTer? | HGMD CI983252 |
| | | | after | `c.214_215insGCCC` | CA2499307076 | p.Ser72CysfsTer? | COSMIC COSV56563065 |

**1955's discriminator is silent**: CIViC's `P71fs` is satisfied by both readings. **2131's is
worse than silent**: both readings first change **Ser72**, so `Q73fs` matches *neither*, and a
resolver trusting the protein name would be misled rather than merely unhelped. Ensembl returns no id
for either 1955 allele; a ClinVar positional sweep of 3:10142050-10142070 (50 alleles) lists none of
the four candidates.

The only asymmetry found anywhere in the class is database *kind* — HGMD curates germline literature
and holds 2131's dup reading, COSMIC is a somatic catalogue and holds the ins reading, and this is a
germline predisposition row. That is an argument about which database is the right sort, not evidence
about this allele, so nothing was asserted.

**The trap this class sets.** ClinVar's protein-name searches return neighbours that are one base
away from a candidate: `"P71fs"` → `c.210_211ins**A**` against the candidate `c.210_211ins**T**`, and
`"Q73fs"` → `c.219_220del`. Both are real alleles. Substituting either would be indistinguishable
from a resolution in any output format.

**What would settle them is a paywalled fulltext**, not another service: Olschwang 1998 (Hum Mutat,
`10.1002/(SICI)1098-1004(1998)12:6<424::AID-HUMU9>3.0.CO;2-H`) and Ong 2007 (Hum Mutat,
`10.1002/humu.20385`). Neither is in PMC. These are **defective records rather than unfilled ones**,
and no resolver fixes them; a curator has to return to the papers.

## Class E — two records naming two alterations, and the instrument that already expresses one

CIViC encodes some combination genotypes **inside a single variant's name**. The builder never sees
them as combinations — nothing reads a variant's name — so they arrive as ordinary single-variant
records and drop only because their identifier columns are empty. All four alterations resolve:

| record | alteration | rsID | CAID | GRCh38 |
|---|---|---|---|---|
| 3298 `P81S (c.241C>T) and L188V (c.562C>G)` | P81S | rs104893829 | CA020148 | 3:10142088 `C`>`T` |
| | L188V | rs5030824 | CA020488 | 3:10149885 `C`>`G` |
| 4210 `R167Q(c.500G>A) and c.464-94T>A` | R167Q | rs5030821 | CA020454 | 3:10149823 `G`>`A` |
| | c.464-94T>A | rs116128787 | CA70052017 | 3:10149693 `T`>`A` |

**The two records are not the same case, and giving them one disposition would be the error.**

### 3298 — a real pair, and the format already expresses it

Weirich et al 2002 (PMID 12414898, JCEM) is titled *"VHL2C phenotype in a German von Hippel-Lindau
family with concurrent VHL germline mutations P81S and L188V"*, and reports the two **co-segregating
with disease through six members of one family**. ClinVar's citation link for that PMID returns
exactly two variations — VCV000002233 (P81S) and VCV000002225 (L188V) — so the curated record agrees
the paper reports this pair and nothing else.

The paper does not use the words *cis*, *trans* or *haplotype*, and the fulltext is paywalled. But
co-segregation through a pedigree is the operative evidence: an affected parent transmits one
homolog, so two variants travelling together through six members are on one chromosome. **Cis is an
inference from the co-segregation, not the source's own statement**, and it is recorded here as such.

**No schema change is needed to author this.** `haplotypes.csv` says which alleles ride together on
one chromosome and `diplotypes.csv` pairs two haplotypes — bricks that shipped in 0.4, and the shape
[`hfe_compound_het`](../../reference_examples/hfe_compound_het/) was written to demonstrate. A
throwaway spec was compiled to check rather than to argue:

```csv
# haplotypes.csv
haplotype_name,rsid,chrom,start,ref,allele,gene
wt,rs104893829,3,10142088,C,C,VHL
wt,rs5030824,3,10149885,C,C,VHL
P81S-L188V,rs104893829,3,10142088,C,T,VHL
P81S-L188V,rs5030824,3,10149885,C,G,VHL

# diplotypes.csv
gene,haplotype_a,haplotype_b,phenotype,trait_efo_id,direction,clin_sig,conclusion
VHL,P81S-L188V,wt,VHL type 2C,DOID:14175,risk,,"Both alterations on one chromosome. …"
```

Result: `validate` passes with only the closure warning a throwaway spec always gets; `compile` and
`compile --strict` both succeed and produce the **same digest**; `reverse` → recompile reproduces
`digest` and `content_signature` exactly (P7), the reversed `haplotypes.csv` differing only by a
normalized empty `requires_callable` column, which is the documented column-normalization asymmetry
and not a round-trip loss.

Two properties are worth stating because they are what make the shape honest rather than merely
legal. `direction` lives on `DiplotypeRow`, so the source's own axis is carried without translation;
and the trait goes in `trait_efo_id` as `DOID:14175` — CIViC's own disease id, in the column, not in
prose. Only one diplotype row exists here, so `_cross_validate_phase_ambiguity` has nothing to collide
with and stays silent; a module that also asserted the trans configuration would make it fire, which
is the correct outcome for a claim the family evidence does not reach.

**What is sized and not taken.** Teaching a drafter to parse a conjunction name and emit haplotype
plus diplotype rows is a *drafter* change. Its size today is **one authorable record**, it needs no
schema change, and it is listed in the survey's open items rather than decided here.

### 4210 — parts resolved, pair unestablished

The same shape and a different verdict, on provenance. PubMed carries **no abstract** for Rocha et al
2003 (PMID 12624160, J Med Genet electronic letter), and its PMC copy is front matter only — about
5 kB with no body. Nothing reachable describes the two alterations as cis, trans, a haplotype, or two
independent findings.

Worse for the pair reading: **ClinVar's citation link for that PMID returns 21 variations including
the R167Q half and *not* the intronic `c.464-94T>A`.** So the curated record attributes only the
missense half to this paper, and whether the intronic allele came from it at all is open. The R167Q
half is also a duplicate of CIViC's own resolved variant 1739.

Both alterations are real and registered. The **pair** is not established, so 4210 is a defective
conjunction record and belongs beside class D, not beside 3298.

## Scope of every negative in this document

`@probe-names-the-table`, applied line by line:

- The class of **nine** is over the **`01-Aug-2026` dated release**, germline direction rows only,
  after the shipped identity parsers. The nightly file was re-surveyed on 2026-09-01 and is identical
  to the dated one on this slice — same rows, same variants, same residue, no identity cell different
  — so the earlier caution that the two disagreed on reach does not apply. Re-derive rather than quote
  anyway if a decision turns on a margin: the source is actively curated and this held for one month.
- "No rsID / no CAID / no GRCh38 HGVS" is over **both** CIViC surfaces — the dated bulk file and the
  GraphQL API, queried per variant.
- "Not in ClinVar" for 2099 is over **six E-utilities searches** of `db=clinvar` (five name-shaped,
  one position-range); it is not a statement about ClinVar's holdings in general. Three further
  searches, reported under the exon-deletion section, make nine in total.
- "No rs-number" for CA645524685 is over the registry's **`externalRecords`** block, which listed
  COSMIC only.
- The Ensembl figures are from the services as they stood on **2026-08-31**; transcript versions and
  exon boundaries are exactly the thing that moves, which is half of this document's point.
- The compile results are from the compiler in this worktree, on a spec with four rows. They
  demonstrate what the tool does with each spelling; they are not a claim about any real module.

Added for the **2026-09-01** round (classes B–E):

- The 33 resolutions are over the four services named at the head of class B, **as they stood on
  2026-09-01**. The registry mints nothing on a `GET`: four arbitrary well-formed VHL alleles were
  submitted as a control and returned `_:CA` blank nodes, and a re-fetch confirmed the first request
  registered nothing. Without that control, "all resolved" would be an artefact of asking.
- A `not_found` in class D is over the four tiers actually run, listed per candidate. It is **not** a
  claim that no identity exists — both readings of both records *are* registered; what is absent is
  anything that chooses between them.
- Class C's "no identity exists" is a statement about the record **as named**, evidenced from each
  cited paper where the paper was reachable. It is not a claim that ClinVar holds no comparable
  event; it holds many, and that is the point — a class is not one of its members.
- "Only one line of evidence" for 2196 and "the citation link returns 21 variations" for 4210 are
  over NCBI `elink dbfrom=pubmed db=clinvar` on a **single** PMID each. `elink` silently merges
  citedby links when PMIDs are batched, so both were queried alone.
- The class E compile results are from the compiler in this worktree on a two-table spec with four
  haplotype rows and one diplotype row. They demonstrate that the shape validates, compiles in both
  modes and round-trips; they are not a claim that any module should carry it.
