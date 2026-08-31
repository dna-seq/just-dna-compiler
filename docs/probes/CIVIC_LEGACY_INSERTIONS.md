# Resolution of two legacy VHL frameshift notations to GRCh38

**Subjects:** CIViC variant 1955 (`VHL P71fs (c.211insT)`) and CIViC variant 2131 (`VHL Q73fs (c.214insGCCC)`)
**Reference transcript:** NM_000551.4 (MANE Select) / ENST00000256474 / NP_000542.1
**Assembly:** GRCh38 / NC_000003.12
**Date of analysis:** 2026-09-01

**This is evidence, never contract** — the standing rule for everything under `docs/probes/`. These
are the two records [CIVIC_UNRESOLVED § class D](CIVIC_UNRESOLVED.md) withholds, taken by hand after
the automated procedure in [CIVIC_IDENTITY_PROTOCOL](CIVIC_IDENTITY_PROTOCOL.md) returned `not_found`
on both. Section 7 below is a later addendum: the checks this document asked for, run.

---

## 0. Summary

| CIViC | legacy string | candidate readings | resolvable? |
|---|---|---|---|
| 1955 | `c.211insT` | exactly 2 | **No** — no sequence-level, protein-level or database discriminator exists. Carry both. |
| 2131 | `c.214insGCCC` | exactly 2 | **Provisionally yes** — `c.210_213dup` on parsimony + HGVS duplication rule + independent HGMD call. |

Both CIViC records are empty shells: no coordinates, no HGVS, no ClinVar ID, no CAID, no aliases. The name string is the entire record, so there is nothing upstream to inherit.

---

## 1. Coordinate frame (verified independently)

NM_000551.4: CDS = mRNA positions 71..712 → 642 nt → 213 aa + stop.

CDS aligned to hg38 chr3 (UCSC `getData/sequence`, exact 60-mer match at offset 147 of chr3:10,141,700–10,142,400):

> **c.1 = g.10,141,848**, plus strand.
> `g = 10141847 + c` holds across the whole window (VHL exon 1 runs to c.340, so no intron correction is needed here).

Reference context:

```
c.      205 208 211 214 217
codon   R69 E70 P71 S72 Q73
seq     CGC GAG CCC TCC CAG
g.      10142052 ........ 10142066

g.10142055  G   c.208
g.10142056  A   c.209
g.10142057  G   c.210
g.10142058  C   c.211
g.10142059  C   c.212
g.10142060  C   c.213
g.10142061  T   c.214
g.10142062  C   c.215
g.10142063  C   c.216
g.10142064  C   c.217
```

Key observation for variant 2131: **`c.210_213 = GCCC` exactly.** The inserted tetramer is identical to the tetramer immediately 5' of one of the two candidate insertion points. That single fact drives the entire analysis below.

All four genomic coordinates in the original notes are correct.

---

## 2. CIViC 1955 — `VHL P71fs (c.211insT)`

### 2.1 The candidate set is provably exhaustive

A single T inserted anywhere in the c.210–214 window yields four distinct alleles. Only two of them are P71fs:

| insertion point | normalized allele | codon 71 | first changed residue | verdict |
|---|---|---|---|---|
| 210 / 211 | `c.210_211insT` | CCC → **T**CC | p.Pro71Ser | **candidate** |
| 211 / 212 | `c.211_212insT` | CCC → C**T**C | p.Pro71Leu | **candidate** |
| 212 / 213 | `c.212_213insT` | CCC → CC**T** (still Pro, silent) | p.Ser72Leu | excluded by name |
| 213 / 214 | 3'-shifts to `c.214dup` | unchanged | p.Ser72Phe | excluded by name |

Both survivors are anchored in both directions — c.210=G, c.211=C, c.212=C, and the nearest T is at c.214 — so neither has any shift room. There is no VCF left-alignment collapse to merge them. They are genuinely two different alleles.

### 2.2 Why every usual discriminator is silent

**Same termination codon.** Both are +1 net frameshifts, so both enter the identical downstream reading frame and terminate at the same position:

```
c.210_211insT  →  p.Pro71Serfs*61   (Ter at codon 131)
c.211_212insT  →  p.Pro71Leufs*61   (Ter at codon 131)
```

Truncation length cannot separate them. Neither can functional/ACMG reasoning — PVS1 applies identically and the predicted products are the same length.

**Both conventions produce "P71".** Under "insert before nucleotide 211" and under "insert after nucleotide 211", the first altered codon is 71 either way. CIViC's protein label therefore carries zero discriminating information.

### 2.3 GRCh38 representations

| reading | HGVS c. (NM_000551.4) | protein | HGVS g. | VCF (left-aligned) | CAID |
|---|---|---|---|---|---|
| before | `c.210_211insT` | p.Pro71Serfs*61 | `NC_000003.12:g.10142057_10142058insT` | `chr3 10142057 . G GT` | CA2586965638 |
| after | `c.211_212insT` | p.Pro71Leufs*61 | `NC_000003.12:g.10142058_10142059insT` | `chr3 10142058 . C CT` | CA2501268513 |

---

## 3. CIViC 2131 — `VHL Q73fs (c.214insGCCC)`

### 3.1 The two readings

| reading | HGVS c. (NM_000551.4) | protein | HGVS g. | VCF (left-aligned) | external |
|---|---|---|---|---|---|
| before (tandem dup) | `c.210_213dup` | p.Ser72Alafs*61 | `NC_000003.12:g.10142057_10142060dup` | `chr3 10142056 . A AGCCC` | HGMD CI983252 · CA2573048346 |
| after | `c.214_215insGCCC` | p.Ser72Cysfs*61 | `NC_000003.12:g.10142061_10142062insGCCC` | `chr3 10142061 . T TGCCC` | COSMIC COSV56563065 · CA2499307076 |

### 3.2 The left-alignment asymmetry — likely cause of the empty sweep

The dup allele **shifts left by four bases**. HGVS anchors it 3'-most at `g.10142057_10142060dup`, but any VCF-normalized store (ClinVar's internal representation included) holds it at **pos 10,142,056** — outside the coordinate anchor a naive sweep would use.

Shift arithmetic: inserted `GCCC` after g.10142060; last inserted base C == preceding base C(10142060) → shift; == C(10142059) → shift; == C(10142058) → shift; last base G == G(10142057) → shift; then last base C vs A(10142056) → stop. Ambiguity span g.10142056–10142060.

The `insGCCC` reading, by contrast, has **zero** shift room: last inserted base C ≠ preceding T(10142061); first inserted base G ≠ following C(10142062).

> **Action:** re-run the ClinVar / ClinGen Allele Registry / gnomAD sweep anchored at **10,142,056** before concluding the dup form is absent.

### 3.3 "Q73" is wrong for both, and cannot be reconciled

p.Gln73fs requires insertion between c.216 and c.217:

```
c.216_217insGCCC  →  p.Gln73Alafs*60
```

Note the frameshift length differs (\*60, not \*61) — a Gln73 insertion truncates one residue shorter. No reading of `214insGCCC` reaches codon 73 under either the "insert before N" or "insert after N" convention. The label is a curation error, not a discriminator, and the notes' assessment ("the discriminator isn't just silent — it's misleading") is correct.

### 3.4 Recommendation: `c.210_213dup`

Three independent arguments, none of them decisive alone, converging:

1. **Parsimony / mechanism.** GCCC inserted immediately 3' of an identical GCCC, inside a GC-rich CCC tract, is textbook replication slippage. The alternative requires a de novo tetramer insertion that coincidentally reproduces its own 5' neighbour — considerably less likely a priori.
2. **The assay cannot distinguish them.** Sanger and SSCP output are identical for both readings. `214insGCCC` is therefore a *naming choice* made by the original authors, not an observation being reported. There is no experimental fact in either paper that favours the insertion reading over the duplication reading.
3. **HGVS forces the name.** If the true allele is the "before" reading, `c.210_213dup` is the only legal description — HGVS requires that an inserted sequence identical to the sequence directly 5' of the insertion site be described as a duplication. HGMD independently landed there.

**Provisional normalization:** `NC_000003.12:g.10142057_10142060dup` / `chr3:10142056 A>AGCCC` / `NM_000551.4:c.210_213dup` / `NP_000542.1:p.(Ser72Alafs*61)`.

### 3.5 Forensic caveat on the external anchors

HGMD accession **CI983252** encodes a **1998** citation, not Ong et al. 2007. HGMD's dup call and COSMIC's ins call may therefore not be curating the same primary report. Confirm this before treating them as two independent votes on one variant.

---

## 4. Database sweep (performed independently, 2026-09-01)

| resource | query | result |
|---|---|---|
| ClinVar (E-utilities) | `VHL[gene] AND "c.210_211insT"` | 0 |
| ClinVar | `VHL[gene] AND "c.211_212insT"` | 0 |
| ClinVar | `VHL[gene] AND "c.210_213dup"` | 0 |
| ClinVar | `VHL[gene] AND "c.214_215insGCCC"` | 0 |
| ClinVar | `VHL[gene] AND "c.209dup"` | 1 (the trap) |
| ClinVar | full VHL insertion+duplication set | 189 records; exon-1 neighbourhood contains only c.204dup, c.206dup, c.207_208dup, c.209dup, **c.210_211insA**, c.212_213dup, c.217dup |
| LOVD shared VHL (REST, updated 2026-08-10) | 211 public variants | nothing between c.208 and c.217 except c.213C>T, c.217C>T, c.217dup |
| Europe PMC full text | `"211insT"`, `"214insGCCC"`, `"insGCCC"`, `"210insT"` | 0 hits each |
| ClinVar `OtherNameList` | any legacy `NinsX` synonym across all 189 VHL ins/dup records | none — no in-database calibration of the legacy convention is possible |

The near-miss `c.210_211insA` (p.Pro71fs) is confirmed present and is exactly one base off a candidate. Do not let it stand in.

---

## 5. The reachable lead

CIViC 1955 carries a **second source** not in the original notes:

**Dollfus H, Massin P, Taupin P, Nemeth C, Amara S, Giraud S, Béroud C, Dureau P, Gaudric A, Landais P, Richard S.** *Retinal hemangioblastoma in von Hippel-Lindau disease: a clinical and molecular study.* Invest Ophthalmol Vis Sci. 2002 Sep;43(9):3067–74. **PMID 12202531.**

Why this is the one to chase:

- **IOVS 2002 is free full text**, unlike both Hum Mutat papers (9829912, 17024664 — neither in PMC, Wiley returns 403).
- Its **Table 3** lists germline mutations for the cohort, and the footnote states that nucleotides are numbered according to the **international VHL database** (Béroud's UMD-VHL). If the table carries a codon column alongside the nucleotide notation, that pins the convention — and pinning the convention for `211insT` also pins it for `214insGCCC`, since both trace to the same French/UMD notation lineage.
- CIViC EID 9969 records that the variant was detected by PCR/SSCP in one patient **without** retinal hemangioblastomas — a searchable row.

Patient handles for the other two sources:

- **Olschwang et al. 1998** (PMID 9829912), CIViC EID 5269: **patient V96**, VHL type 1, from a cohort of 92 unrelated patients, 61 DNA variants, 96 controls.
- **Ong et al. 2007** (PMID 17024664), CIViC EID 5728: VHL type 1 kindred of **3 individuals**, all with retinal angiomas and cerebellar hemangioblastomas, one with renal cell carcinoma. Cohort: 573 patients / 200 kindreds.

---

## 6. Recommended handling until a table surfaces

- **1955** — carry both readings as an explicit pair. Do not silently pick one. Emit both `g.10142057_10142058insT` and `g.10142058_10142059insT` with a flag indicating unresolved legacy notation. Note in any downstream annotation that the two are protein-equivalent in length and identical in consequence class (PVS1, Ter131), so clinical interpretation is unaffected by the ambiguity even though the allele identity is.
- **2131** — normalize provisionally to `c.210_213dup` / `g.10142057_10142060dup`, flagged as provisional, with `c.214_215insGCCC` retained as an alternate. **Correct the protein label from Q73fs to Ser72Alafs\*61.**
- Re-run the coordinate sweep for 2131 at the **left-aligned** position 10,142,056 before recording the allele as novel.

---

## Appendix — verification commands

Coordinate frame:

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NM_000551.4&rettype=gb&retmode=text"
curl -s "https://api.genome.ucsc.edu/getData/sequence?genome=hg38;chrom=chr3;start=10141700;end=10142400"
# CDS (mRNA 71..712) first 60-mer matches at offset 147 → c.1 = g.10141848
```

Translation check for all five readings (wild type, both insT, both insGCCC, plus the hypothetical Q73 insertion):

```
c.210_211insT      first changed aa 71: P->S   fs*61
c.211_212insT      first changed aa 71: P->L   fs*61
c.210_213dup       first changed aa 72: S->A   fs*61
c.214_215insGCCC   first changed aa 72: S->C   fs*61
c.216_217insGCCC   first changed aa 73: Q->A   fs*60   (the only route to "Q73fs")
```

CIViC record retrieval:

```bash
curl -s https://civicdb.org/api/graphql -H "Content-Type: application/json" \
  -d '{"query":"{ variant(id: 2131) { name ... on GeneVariant { hgvsDescriptions clinvarIds alleleRegistryId coordinates { chromosome start stop } } } }"}'
```

---

## 7. Addendum — the specified checks, run (2026-09-01, added after the analysis above)

Three claims were re-derived independently rather than taken on trust, and the one action item §3.2
raises was carried out. **The coordinate work all holds. The left-alignment hypothesis does not.**

### 7.1 The coordinate frame confirms, by two routes

`c.1 = g.10141848` was re-derived from UCSC's hg38 sequence for chr3:10,142,051–10,142,070
(`GCGCGAGCCCTCCCAGGTCA`), giving the same per-base table:

```
g.10142055 G  c.208     g.10142060 C  c.213
g.10142056 A  c.209     g.10142061 T  c.214
g.10142057 G  c.210     g.10142062 C  c.215
g.10142058 C  c.211     g.10142063 C  c.216
g.10142059 C  c.212     g.10142064 C  c.217
```

Codons R69 E70 P71 S72 Q73 read `CGC GAG CCC TCC CAG`, and **`c.210_213` is `GCCC` exactly** — the
observation §1 says drives the whole analysis. The frame also checks against a variant resolved by a
different route entirely: CIViC 3298's `P81S (c.241C>T)` resolves to `NC_000003.12:g.10142088C>T`
through the ClinGen registry, and `10141847 + 241 = 10142088`. A sequence fetch and an independent
service agree on the frame to the base.

### 7.2 The left-aligned sweep — run, and the hypothesis is wrong

§3.2 proposed that the dup reading's four-base left shift put it outside the anchor a naive sweep
would use, and asked for the sweep to be re-run at 10,142,056 before calling the allele absent. Done,
over three windows of `VHL[gene] AND 3[chr] AND <lo>:<hi>[chrpos38]`:

| window | records | insertions/duplications among them |
|---|---:|---|
| 10142056 exactly | 4 | `c.209dup` only |
| 10142056–10142060 | 17 | `c.209dup`, `c.210_211insA`, `c.212_213dup`, `c.213del`, `c.214_215del`, `c.214_216del` |
| 10142050–10142070 | 58 | the above plus `c.204dup`, `c.206dup`, `c.207_208dup`, `c.216_217delinsAT`, `c.219_220del`, `c.221del`, `c.222_225dup`, `c.223_225del` |

**`c.210_213dup` is absent at the left-aligned anchor too.** The window is live rather than empty —
the exact-position query returns four records, so the index does resolve at 10,142,056 — which is what
makes this a real negative rather than a query that failed to reach. The empty sweep was therefore not
a left-alignment artefact: ClinVar simply does not hold this allele. §3.2's shift arithmetic is
nevertheless correct — inserting `GCCC` after g.10142056's `A` reproduces the reference `AGCCCGCCCT`
either way, so `chr3:10142056 A>AGCCC` is the right VCF form — and only its explanation for the
absence is falsified.

The near-miss §4 warns about is confirmed present: `c.210_211insA` is ClinVar **3754754**, one base
from a 1955 candidate.

### 7.3 The four candidate CAIDs carry no ClinVar or dbSNP cross-reference

Asked of the ClinGen Allele Registry by **genomic** HGVS, so the answers do not depend on the
transcript spelling used earlier:

| reading | CAID | dbSNP | ClinVar | other external |
|---|---|---|---|---|
| 2131 dup — `g.10142057_10142060dup` | CA2573048346 | — | — | none |
| 2131 ins — `g.10142061_10142062insGCCC` | CA2499307076 | — | — | none |
| 1955 before — `g.10142057_10142058insT` | CA2586965638 | — | — | none |
| 1955 after — `g.10142058_10142059insT` | CA2501268513 | — | — | none |

All four are registered and all four are bare. Registration confirms the alleles are well-formed and
says nothing about which one a curator meant — `@existence-not-identity`.

### 7.4 The reachable lead is real, and it is invisible to the snapshot's basis

§5 names a second source for 1955 — Dollfus et al. 2002, PMID **12202531**, free full text — that the
earlier round never saw. Queried directly, `evidenceItems(variantId: 1955, status: ALL)` returns
**two** items: EID 5269 (`ACCEPTED`, PMID 9829912) and EID **9969, `SUBMITTED`**, PMID 12202531.

That is why it was missed, and it is not an oversight in the search. The snapshot is built from the
dated bulk TSV, which is **`accepted`-only**; a `SUBMITTED` item exists in the API and in no file the
builder reads. So this record is a worked instance of the survey's open item 4 — reading `SUBMITTED`
items — with something concrete at stake rather than a doubled row count: **the one free-fulltext lead
that could settle a withheld identity lives outside the status basis the snapshot uses.**

PMID 12202531 is already in the corpus by another door, as the source for CIViC 2046
(`VHL V155L (c.463G>C)`), which resolved. Whether its Table 3 pins the numbering convention is
untested here.

### 7.5 What this changes upstream, and what it does not

- **1955 stays withheld.** Nothing in these checks separates the two readings, and §2.2's argument
  that nothing can — same frameshift, same Ter131, "P71" under either convention — is the strongest
  statement available about it.
- **2131's recommendation stands as provisional and is not adopted.** `c.210_213dup` rests on
  parsimony, the HGVS duplication rule, and a single independent HGMD call whose 1998 accession may
  not be curating Ong 2007 at all (§3.5, unresolved — HGMD's full record is gated). Three converging
  arguments none of which is decisive is the shape the house rule withholds on. It is recorded here as
  the best available reading, not written into any table.
- **`Q73fs` is a curation error either way**, and that is now established rather than suspected: no
  reading of `214insGCCC` reaches codon 73 under either convention, and the only route to it,
  `c.216_217insGCCC`, gives `fs*60` rather than `fs*61`.
- **Coverage does not move.** 270/290 stands (RM159); neither of these two is adopted.
