# Resolving variant identity from a name alone — a protocol

Evidence document. Written 2026-09-01 from two probes run against the CIViC `01-Aug-2026`
bulk release, over the residue a shipped builder drops as `unresolvable_identity`:

* **set A** — 22 VHL small indels and frameshifts named only by a `c.` fragment.
  20 resolved, 2 withheld. 198 verbatim queries in `setA_results.json`.
* **set B** — 21 records across 11 genes: protein substitutions, splice and cDNA variants,
  six class-labels, two combination genotypes. 15 resolved, 6 `no_identity_exists`,
  0 `not_found`. 115 verbatim queries in `setB_results.json`.

Every rule below exists because a record forced it, and the record is named. This states
what was measured. It does not propose anything.

**This is evidence, never contract** — the standing rule for everything under `docs/probes/`.
Nothing here is a decision, and no code in this repository implements it: the two probes ran outside
the tree against live services and wrote no module. What the procedure was *applied to*, class by
class with the per-variant answers, is [CIVIC_UNRESOLVED](CIVIC_UNRESOLVED.md); the corpus it ran
over is described in [CIVIC_SURVEY](CIVIC_SURVEY.md).

**Marking.** Rules are source-agnostic unless tagged **[CIViC]**, which marks a rule that
turns on how CIViC specifically spells or populates its records. A **[CIViC]** rule usually
generalises to *"any source with a legacy curation layer"*, but only the CIViC half was
measured.

---

## 0. Read this first: what the two probes disagreed about, and what settled it

Only one substantive disagreement existed between the probes, and it came from the task
framing rather than from either probe.

**Claim under test:** *"`NM_000551.4` shifts VHL CDS numbering by one against `.3`"*, offered
as fact in the original brief, with the evidence that a prior probe submitted
`NM_000551.3:c.197_220del` and got back an allele the registry named
`NM_000551.4(VHL):c.198_221del`.

**The claim is false.** Set A measured it on VHL. Set B re-measured it independently across
its own nine-gene panel and then ran the decisive control. Three lines of evidence:

**(i) The CDS string does not change across a version bump.** Fetch version N and N−1 of each
MANE Select accession and compare the CDS byte for byte (`version_probe.py`):

```
NM_000551.4 vs NM_000551.3   CDS offset  214 -> 71     len 642 -> 642    IDENTICAL
NM_007194.4 vs NM_007194.3   CDS offset   73 -> 59     len 1632 -> 1632  IDENTICAL
NM_001754.5 vs NM_001754.4   CDS offset  191 -> 195    len 1443 -> 1443  IDENTICAL
NM_177438.3 vs NM_177438.2   CDS offset  239 -> 346    len 5769 -> 5769  IDENTICAL
NM_005188.4 vs NM_005188.3   CDS offset  143 -> 80     len 2721 -> 2721  IDENTICAL
NM_005359.6 vs NM_005359.5   CDS offset  539 -> 539    len 1659 -> 1659  IDENTICAL
NM_000077.5 vs NM_000077.4   CDS offset  307 -> 31     len 471 -> 471    IDENTICAL
NM_000268.4 vs NM_000268.3   CDS offset  444 -> 367    len 1788 -> 1788  IDENTICAL
NM_000546.6 vs NM_000546.5   CDS offset  203 -> 143    len 1182 -> 1182  IDENTICAL
```

**9 of 9 identical.** Note the second column: the CDS *offset within the mRNA* moved in 8 of
the 9, sometimes hugely (CDKN2A 307→31, DICER1 239→346). That is UTR re-annotation. `c.`
numbering is CDS-relative, so it is untouched by an offset move. Reading the GenBank `CDS
214..855` vs `CDS 71..712` lines and concluding "everything shifted by 143" is exactly the
mistake, and it is easy to make.

**(ii) The control that separates renormalisation from a version shift.** Submit the *same*
expression under both versions. If the version shifted numbering, the two would be different
alleles:

```
NM_000551.3:c.197_220del  -> CA645524685  titled NM_000551.4(VHL):c.198_221del
NM_000551.4:c.197_220del  -> CA645524685  titled NM_000551.4(VHL):c.198_221del   <- same CAID
NM_000551.4:c.198_221del  -> CA645524685  titled NM_000551.4(VHL):c.198_221del
```

One allele, three spellings. The `197 → 198` move is the registry applying the HGVS 3′ rule
(`c.197` is `T`, `c.221` is `T`, so the 24-nt deletion shifts one base 3′-ward), and it applies
it identically under both versions. Confirmed on three more genes, one from each probe:

```
NM_000551.3:c.499C>T / .4:c.499C>T   -> CA020450   (both, numbering unchanged)
NM_000546.5:c.215C>G / .6:c.215C>G   -> CA000072   (both, numbering unchanged)
NM_007194.3:c.1420C>T / .4:c.1420C>T -> CA288280   (both, numbering unchanged)
```

**(iii) Why the illusion is persistent.** The registry always *titles* its answer in the newest
transcript version it knows. Submit `.3` and the reply says `.4`. If the reply also carries a
renormalised position, the version and the position appear to have moved together. They are
independent: the version in the title is cosmetic, the position move is the 3′ rule.

**The correct rule.** A RefSeq version bump does not change `c.` numbering, because it does not
change the CDS string. A position that comes back moved was **renormalised**, and you confirm
that locally with a 3′-shift calculation (§3). Treat a position change as a version artefact only
after the local normaliser reproduces it.

**What the wrong rule costs, in both directions.** Believing it invites you to "correct" every
position in a gene by one, silently corrupting a whole batch. It also teaches you to wave through
a *genuine* one-base mismatch as a version artefact, which is how a real wrong answer survives
review. Neither failure announces itself.

Beyond this, the two probes did not conflict. They met different name shapes and therefore
found different rules; §7 ranks the discriminators from both, and every step below that only one
probe met is marked with the set that met it.

---

## 1. Scope

Run this when a source publishes a variant **name** and no identifier — no rsID, no ClinGen
CAID, no genomic HGVS, no coordinates. The name is the only lever. The procedure turns it into
exactly one of three outcomes (§8), each with the queries that produced it.

You need three read-only, credential-free services and one local sequence capability:

| | |
| --- | --- |
| ClinGen Allele Registry | `GET https://reg.genome.network/allele?hgvs=<urlencoded>` |
| NCBI E-utilities | `esearch` / `esummary` / `efetch` / `elink`, `db=` `clinvar`, `snp`, `pubmed`, `pmc`, `nuccore` |
| Ensembl REST | `GET https://rest.ensembl.org/variant_recoder/human/<expr>` |
| local | transcript CDS + exon table + a 3′ normaliser + a consequence calculator (§3) |

Cache every HTTP response to disk keyed by a hash of the URL, including non-5xx errors — those
are answers, not failures (§4, §11). You need verbatim query strings for the record anyway, and
a re-run must be free.

---

## 2. Step 0 — establish that the gap is real before spending a request

**[CIViC]** Diff the dated release against the nightly TSV for the records in hand:

```python
rows = csv.DictReader(open("nightly-VariantSummaries.tsv"), delimiter="\t")
# hgvs_descriptions, allele_registry_id, clinvar_ids, representative_transcript, variant_aliases
```

Both probes: still empty in nightly for all 43 records.

**Do not read staleness into `last_review_date`.** All 21 set-B records carry `2024-09-17`, and
so do 753 of the 1999 rows in the file. It is a bulk-import timestamp and says nothing about an
individual record.

**Source-agnostic corollary:** if the source ships more than one snapshot, diff them first. A
record the source has since filled needs no probe.

---

## 3. Step 1 — pin the numbering frame, by measurement

`c.` and `p.` numbers mean nothing until a transcript is named. Two routes; run whichever the
corpus supports, and prefer the first when it is available.

### 3a. Calibrate against the source's own resolved records — strongest [set A]

If the source resolved *other* variants in the same gene, they carry the frame. Extract the `c.`
fragment from each resolved sibling's name and compare it to every transcript expression in that
sibling's `hgvs` list.

Set A: **114 of 114 VHL siblings agreed; 0 disagreed.** The frame is `NM_000551.3` /
`ENST00000256474.2`, and it is measured, not assumed. This route also tells you the frame the
*source curator* used, which is what you need when the source is older than MANE.

### 3b. MANE Select from the summary table — the fallback [set B]

When the gene has no resolved siblings (all 11 set-B genes had one record each), take the
transcript from the MANE table, downloaded once and cited:

```
https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/current/MANE.GRCh38.v1.5.summary.txt.gz
# columns: symbol, MANE_status, RefSeq_nuc, RefSeq_prot, Ensembl_nuc, GRCh38_chr
```

**MANE is the default, not the answer.** Cross-check it against the numbering the name implies
before using it. Two of eleven set-B genes needed more:

* **RUNX1 (804)** — p.135 on MANE `NM_001754.5` (RUNX1c, 480 aa) is **Gly**, not the Arg the
  name asserts. The name is in legacy RUNX1b numbering. Resolve by **translating each candidate
  isoform's CDS and locating the residue**, never by applying a remembered offset:
  `NM_001001890.3` (RUNX1b) has Arg at 135; MANE has Arg at 162; the offset is 27 residues, and it
  is derived. Verified afterwards by the registry returning **one CAID (CA248618) for both**
  `NM_001754.5:c.508+3delA` and `NM_001001890.3:c.427+3delA` (508−427 = 81 = 27×3). Two
  expressions collapsing to one CAID is the proof the offset is right.
* **CDKN2A (2884)** — the gene has MANE Select `NM_000077.5` (p16INK4a) *and* MANE Plus Clinical
  `NM_058195.4` (p14ARF), with different CDS numbering. The exon table decides: exon 1 = `c.-29..150`,
  exon 2 = `c.151..457`, so `c.151-1` is exactly the intron-1 acceptor under p16 numbering.
  Confirmed by querying the other transcript's spelling for the same allele
  (`NM_058195.4:c.194-1G>C`) and getting the **same CAID CA299032**.

### 3c. Which version to submit

Submit the frame the **source** uses; the registry canonicalises and answers in its own newest
version. Set A submitted `NM_000551.3`, set B submitted MANE `.4`, and §0 shows both return the
same CAID. If you switch frames, prove the equivalence with the §0 control rather than assuming it.

One asymmetry to know: **Ensembl's Variant Recoder rejects `NM_000551.3`** ("Could not get a
Transcript object") while accepting `.4` and `ENST00000256474.2`. Route the recoder by genomic
coordinates instead (§6) and the question disappears.

---

## 4. Step 2 — build the local calculator before touching the network

This is what makes the rest arithmetic rather than guesswork. Fetch the RefSeq mRNA GenBank
record once (`efetch db=nuccore rettype=gbwithparts`) and parse three things:

* the `ORIGIN` block → the spliced mRNA sequence;
* the `CDS join(...)` line → the CDS offset, so `c.1` is known;
* every `exon a..b` feature → the exon table, converted to `c.` coordinates.

That buys six local primitives. Every one replaces a recollection with a read:

| primitive | answers | forced by |
| --- | --- | --- |
| `codon(n)` → bases, AA, `c.` of first base | what residue the reference actually has | 4968, 804 |
| `base_at_c(n)` | whether the reference base a `c.` name asserts is real | all 22 of set A |
| `exon_table()` in `c.` coords | which intron a `+n` / `-n` name means | 788, 2884 |
| `candidates(pos, new_aa)` | every single-SNV route to a named residue | 2196, 2046 |
| 3′ normaliser | what spelling the registry will answer with | 1844, 1960, 3741, 3743 |
| consequence calculator | `fs*N`, by re-translating past the CDS into the 3′UTR | 2447, 2455, 3184 |

**The 3′ normaliser, in transcript orientation.** Two rules:

* deletion: while `base(start) == base(end+1)`, shift the whole interval one base 3′;
* insertion of `s` after position `p`: while `s[0] == base(p+1)`, rotate `s` left and advance `p`;
  afterwards, if the `len(s)` bases ending at `p` equal `s`, the allele is a **dup**.

**Calibrate the calculator against the source's own resolved records before trusting it.** Set A
required `c.352_353insA` → `p.Leu118…fs` (CIViC's `L118fs`) and `c.526del` →
`p.Arg176GlyfsTer26` (CIViC's own `hgvs` string). Both matched.

---

## 5. Step 3 — classify the name, then construct candidates

Read the name against the local calculator **before** any lookup, and classify. The class decides
the route, and two of the classes are terminal.

| class | test | route |
| --- | --- | --- |
| **class-label** | the name denotes a *kind* of event (`TRUNCATING MUTATION`, `Rearrangement`, `Large deletion`, a cytoband range) | → §8 `no_identity_exists`. **Do no allele lookup.** |
| **multi-alteration** | the name contains two alterations (`and`, a second `c.`) | → split; run everything per part; **never mint one identity for the record** |
| **legacy insertion** | `c.<N>ins<SEQ>` | → two readings, §5a |
| **legacy redundant-base** | `c.430delG`, `c.417_418delTC` | → drop the asserted bases after checking them |
| **legacy intronic / protein** | `IVS<n>+1G>A`, `R135fsX177` | → §7 ranks 1-2 (788 was settled by rank 2, 804 by both), do **not** convert structurally |
| **modern HGVS** | already `c.180del`, `c.272_273delinsAA` | → one reading |
| **protein substitution** | `D1709E` | → `candidates()`; may be >1 |

Then classify what the local read tells you about the name itself:

| local finding | meaning | action |
| --- | --- | --- |
| reference AA/base matches | self-consistent | construct and query |
| reference AA differs, another isoform has it | legacy isoform numbering | find the isoform **by sequence** (§3b) |
| the name's two halves disagree | **contradictory name** — a finding | resolve both halves, adjudicate by literature (§7 rank 1) |
| `candidates()` returns >1 | the protein name is not allele-determining | carry **every** candidate forward |
| `candidates()` returns 0 | not one SNV away | stop; the transcript is probably wrong |
| the name's own ref base is absent from the CDS | the name is wrong | withhold before any lookup |

### 5a. The legacy `c.<N>ins<SEQ>` form has two readings [set A]

It does not say whether the insertion goes after N or before N. **Generate both:**

* after → `c.<N>_<N+1>ins<SEQ>`
* before → `c.<N-1>_<N>ins<SEQ>`

Also submit the `dup` spelling when the normaliser says the insertion is a duplication. The
registry canonicalises, so an equivalent spelling returns the same CAID and a *different* CAID
proves the two readings are genuinely different alleles.

**Do not send the legacy form.** `NM_000551.3:c.386insAGA` returns HTTP 400
`IncorrectHgvsPosition`. **[CIViC]** This is a categorical blocker, and it is measurable: across
all 314 VHL records in the release, legacy `c.<N>ins<SEQ>` names are **0 of 14 resolved** against
a corpus otherwise ~83% resolved. A resolver that passes the source's name through unmodified
fails on exactly this class.

**[CIViC] The source is not internally consistent about which reading it means.** Of set A's 11
legacy-`ins` rows the protein name implies *before* for **1768** (`L129Q (c.386insAGA)`) and
*after* for **2930** (`106insR (c.316insGCC)`). There is no convention to learn, and the resolved
sibling corpus offers no ground truth — **zero of the 114 resolved siblings use a legacy `ins`
spelling**, so the convention cannot be calibrated at all. Always generate both.

---

## 6. The four tiers

Run in order. Stop when the outcome is determined, but record every tier you ran.

### Tier (a) — ClinGen Allele Registry, by constructed HGVS

```
GET https://reg.genome.network/allele?hgvs=<urlencoded expression>
```

**Six outcomes, all distinct.** Collapsing any two of them is how a wrong answer gets recorded:

| response | outcome | meaning |
| --- | --- | --- |
| 200, `@id` = `…/allele/CA<digits>` | `hit` | this exact allele is registered |
| 200, `@id` = `"_:CA"` (blank node) | `not_registered` | well-formed and canonicalisable, nobody has registered it. **`genomicAlleles` is still returned**, so you get GRCh38 coordinates from a miss |
| 400 *"Given allele from reference sequence is incorrect"* | `ref_mismatch` | **evidence, not noise** — see §7 rank 4 |
| 400 `IncorrectHgvsPosition` / `IncorrectHgvs*` | `unparsable` | your spelling is wrong. Fix it. **Do not record a negative** |
| 500 *"coordinates outside reference"* | `unparsable` | your position is off the transcript |
| 5xx / timeout | `service_error` | retry; never collapse into "not found" |

The blank-node case is HTTP **200** and is easy to misfile as a hit. Set B met it on
`NM_001754.5:c.351+3delA`; set A met it as the normal miss shape. It means *asked, nothing
answered* — never *does not exist*.

**Coordinates.** `genomicAlleles[].coordinates[].start` is **0-based interbase**. Do not publish
it. Take the 1-based position from the object's own `hgvs` string
(`NC_000003.12:g.10149823G>A`). Calibrated twice: against a CIViC sibling that publishes
`g.10149823G>A` where the registry reports `start=10149822`, and against ClinVar's
`positionVCF 28725242` where the registry reports `28725241` (788).

**Indels need a stated convention.** Set A's VCF-padded conversion from interbase:

* deletion (`allele` empty): `POS = start`, `REF = base(start) + referenceAllele`, `ALT = base(start)`
* insertion (`referenceAllele` empty, `start == end`): `POS = start`, `REF = base(start)`, `ALT = base(start) + allele`
* delins (both non-empty): `POS = start + 1`, `REF = referenceAllele`, `ALT = allele`

`base()` reads **your own** GRCh38 slice, not the registry. Then assert
`base(start+1, len(referenceAllele)) == referenceAllele` — that single equality guards the
interbase off-by-one, and it passed on all 22 set-A variants.

The same allele legitimately has two conventions: for 804 the registry gives
`g.34880554del` (deleted base, empty alt) and ClinVar gives `positionVCF 34880553 GT>G`
(left-anchored). Both correct, not interchangeable. **Record which one you publish.**

**Separate "registered" from "corroborated".** `externalRecords` (dbSNP / ClinVar / COSMIC /
gnomAD) is present on some registered alleles and absent on others. A CAID with no
`externalRecords` is a real, build-independent identity but is **not** evidence the allele is
known. Set A: **9 of 20** resolved rows are like this — 2447 (`c.197_209del`) returns CA2497028944
with no dbSNP, no ClinVar, no COSMIC, not even a MyVariantInfo link. Record the two facts in
different fields; they answer different questions.

### Tier (b) — NCBI, by name

```
esearch.fcgi?db={clinvar|snp}&term=<term>&retmode=json
esummary.fcgi?db=clinvar&id=<ids>&retmode=json
efetch.fcgi?db=clinvar&rettype=vcv&id=<variationid>&is_variationid&retmode=xml
elink.fcgi?dbfrom=pubmed&db=clinvar&id=<PMID>&linkname=pubmed_clinvar
```

`is_variationid` is required on the `efetch` or it returns nothing usable. ≤3 requests/second.

**Record the exact term and the `querytranslation` NCBI echoes back.** A zero is only as wide as
the query that produced it: `RUNX1[gene] AND "R135fs"` returns 0, which is a fact about ClinVar's
indexing of legacy protein names, not about the allele — which is `VCV000014466`.

**Search on the normalised expression the registry returned, not the source's spelling.**
`VHL[gene] AND "c.455insA"` returns nothing; `VHL[gene] AND "c.374dup"` returns the record (2091).

**Make a negative honest with a positional sweep** [set A]. `db=clinvar` accepts
`VHL[gene] AND 3[chr] AND 10142050:10142070[chrpos38]`, which enumerates every ClinVar allele at
the locus. That converts "I did not find it by name" into "ClinVar holds no such allele in this
window" — a claim as wide as the locus rather than as wide as one string.

Two things this tier does that nothing else does — both are ranked in §7:
`<OtherNameList>` in the `efetch` XML (legacy aliases), and `elink` citation attribution.

### Tier (c) — Ensembl Variant Recoder, the independent second service

```
GET https://rest.ensembl.org/variant_recoder/human/<urlencoded>?content-type=application/json
```

**Query it with the GRCh38 genomic HGVS the registry returned**, not with the RefSeq `c.`
expression. Both probes converged on this for different reasons, and both reasons are real:
set A because the recoder rejects `NM_000551.3` outright; set B because it **reproducibly times
out (>90 s) on `NM_…:c.…` input** while answering the same allele from `<chr>:g.…` in ~25 s, with
`info/ping` healthy throughout. Genomic input is also independent of the transcript choice, which
is what you want from a second opinion.

It returns `id` (rs-numbers, **HGMD accessions**, COSMIC `COSV` ids), `spdi`, and the full
`hgvsc`/`hgvsg` equivalence set. Concordance measured: set B, **19 of 19** constructed expressions
agreed with the registry on the rsID. The tier's value is not disagreement — it is that agreement
across two services makes a single-service failure stand out as a failure rather than as data.

### Tier (d) — literature

Batch the abstracts first; one call, free:

```
efetch.fcgi?db=pubmed&id=<comma-separated PMIDs>&rettype=abstract&retmode=text
```

For full text try `elink dbfrom=pubmed db=pmc` then `efetch db=pmc`.

**How much this tier is worth depends entirely on the name shape, and the two probes measured
opposite answers.** For set A's indels it "did not resolve anything tiers (a)–(c) had not already
settled" and should be run last. For set B's legacy and class-label names it was decisive four
times: the RUNX1 nucleotide event is stated in the abstract (804); every group-2 classification
came from abstracts; and PMC full text supplied the table that settled 2036. **Run it last for a
name that already states a DNA-level edit; run it early for a name that states only a consequence
or a class.**

Expect paywalls. Wiley returned 403, OUP served the wrong article, LOVD's REST API returns 302 to
an abuse page, HGMD's site needs registration — but HGMD accessions reach you free through tier
(c), which is the route to use. When full text is unreachable, say so and withhold.

---

## 7. Discriminators, ranked by the weight each can carry

When more than one candidate survives tier (a), these are what separate them. Ranked by how much
weight the evidence can bear, strongest first. **Each entry names what it cannot settle** — that
half matters more than the ranking.

**1. `elink dbfrom=pubmed db=clinvar` on the record's own cited PMID** [set B]
Asks: *which allele does the curated record attribute to the paper this record itself cites?*
Strongest available, because it binds a curated identity to the exact evidence the source used.
Settled four set-B records: 2459 (`VCV000428795` = `c.533T>C` cites PMID 25867206, `VCV001529494`
= `c.532C>T` does not), 2196 (`VCV000933031` = `c.5127T>A` cites 22187960, `VCV000933032` does
not), 804, and 708.
*Cannot settle:* an allele ClinVar does not hold, or a paper nobody has submitted against. It is
silent, not negative, when a record has no citing variation — and set A never needed it because
its indels are mostly not in ClinVar at all.

**2. ClinVar `<OtherNameList>` — legacy aliases** [set B]
The `efetch …&rettype=vcv&is_variationid` XML carries the spellings papers actually used. This is
the only thing that resolves legacy notation, and it resolves it outright:
`CHEK2[gene] AND "IVS2+1G>A"` → one record, `VCV000128075` = `c.444+1G>A`, whose OtherNames are
`1-BP DEL… IVS2DS, G-A, +1` **and** `IVS3+1G>A` — the record documents both conventions itself.
`RUNX1[gene] AND "IVS4"` → one record, `VCV000014466` = `c.508+3del`, OtherName
`1-BP DEL, A, IVS4, +3`.
*Cannot settle:* anything not curated into ClinVar, and it cannot tell you a legacy name is
*absent* rather than differently spelled — a zero here is only as wide as the string.

**3. Only one candidate is registered** (the other returns `_:CA`) [set A]
Cheap, unambiguous, and available for every candidate you construct. Settled 1779 and 1949.
*Cannot settle:* anything where both readings are registered — which was 5 of set A's 11
insertion rows. Registration is not rarity: 9 of 20 set-A resolutions have no external record at
all, so "registered" alone never means "the allele the source meant".

**4. The registry's reference-base validation, used as a direction test** [set B]
Submit **both** opposite expressions and let the registry reject one. For 4968:
`NM_000546.6:c.215C>G` → hit `CA000072`; `c.215G>C` → HTTP 400 *"Given allele from reference
sequence is incorrect"*. Exactly one is accepted, which tells you which residue is reference.
*Cannot settle:* anything where both directions are chemically possible against different
positions. It answers "which base is reference here", not "which allele did the curator mean".

**5. External corroboration on exactly one candidate — `externalRecords`, or an HGMD accession
from tier (c)** [set A]
The recoder's `id` list carries **HGMD accessions** (`CI…` insertion, `CD…` deletion, `CM…`
missense). HGMD curates from the literature, so an HGMD accession on one reading and nothing on
the other is literature-derived evidence for that reading. Set A: the single most useful
discriminator in that probe, and it appears in no task framing.
*Cannot settle:* a row where HGMD holds **both** readings (2091, where only the protein name then
separates them), or where the two databases disagree in *kind* — 2131 has an HGMD germline
accession on one reading and a COSMIC somatic id on the other, and preferring HGMD because the
row is a germline record is an argument about database kind, not evidence about the allele. Set A
declined it, and withheld. See §10.

**6. Protein-consequence concordance** [both]
The consequence computed from each candidate, compared to the name's protein fragment. Settled
1768, 2091, 2930.
*Cannot settle:* anything, on its own, when the source's protein names drift — see the binding
rule immediately below.

**7. Ensembl recoder rs-numbers** [both]
Independent second-service agreement. Measured value: set B, 19/19 agreement.
*Cannot settle:* which of two alleles at one position is meant — see §10, rules 4 and 5. It is a
corroborator, not a discriminator.

**8. General web search on a legacy notation**
Set A: `"c.211insT" VHL` returns nothing on-target. Effectively zero weight for indels; some
weight for well-studied substitutions. Run last, believe least.

### The rule that must be settled before you use discriminator 6

**The DNA-level edit is the identity anchor. The protein fragment discriminates between candidate
readings; it is never a veto.**

**[CIViC]** The source's protein name is off by one from the mathematically correct consequence
of the source's *own* `c.` fragment in **6 of set A's 22** rows (1779, 1844, 1949, 2014, 2091,
2131). The discordance is internal to the name, so any correct identity disagrees with it the
same way, and treating the protein name as a veto rejects every true answer.

What must match is the **consequence class** (frameshift / nonsense / in-frame / synonymous /
missense) and the reference base. The residue **number** is recorded, and a ±1 difference is
documented as legacy-naming drift.

**This reconciles the two probes rather than choosing between them.** Set B's 2459 looks like the
protein name vetoing the cDNA half, and it is not: `c.532C>T` is CTG→TTG, both Leucine,
**synonymous** — a consequence-*class* mismatch against a name asserting a missense change, which
is the half this rule says binds. Set A's ±1 drift is a residue-*number* mismatch, which is the
half this rule says is advisory. One rule, two probes, no conflict.

Note which way the drift correlates [CIViC]: rows whose protein name is exactly right, `fs*N`
included (`V62Cfs*5`, `V66Gfs*89`, `G114Vfs*45`, `F148*`, `F91*`), are the ones spelled in modern
HGVS. Legacy-spelled rows drift. A legacy row's protein name was transcribed from a paper; a
modern row's was computed.

---

## 8. Outcomes — three-valued, with executable tests

Every record ends as exactly one of these. The test is the code, not the prose.

```python
def outcome(rec):
    # 1. no_identity_exists - the NAME denotes a class, so no allele can satisfy it.
    #    Decided at §5 classification, BEFORE any lookup. Requires a stated reason.
    if rec.name_denotes_a_class_of_events:
        return "no_identity_exists"

    # 2. resolved - exactly one candidate survives, named by a service, query recorded.
    survivors = [c for c in rec.candidates if c.registry_outcome == "hit"]
    if len(survivors) == 1:
        # R4: if the direction test (one candidate ref_mismatch) shows the source means
        # the REFERENCE allele, the resolved identity is the "<ref>=" expression, NOT the
        # surviving ref>alt candidate. 4968 resolves to CA178298, not to CA000072.
        return "resolved"
    if len(survivors) > 1 and rec.discriminator is not None:   # §7, ranked
        return "resolved"        # keep EVERY candidate in the record, name the discriminator

    # 3. not_found - asked, nothing answered. Never written as "does not exist".
    return "not_found"           # requires the failed queries stored beside it
```

Counts measured: set A **20 resolved / 2 not_found / 0 no_identity_exists**; set B **15 resolved
/ 0 not_found / 6 no_identity_exists**. The distributions are near-complementary because the sets
differ by name shape, which is the point: `not_found` is what ambiguous *alleles* produce, and
`no_identity_exists` is what class *labels* produce.

For `no_identity_exists`, record separately from the verdict **whether the cited paper measured a
specific event**. Set B's six split three ways, and the distinction is the finding:

* *never measured* — 2182 (Southern blot, three unrelated cohorts under one name), 2439 (the
  cited paper is a statistical surveillance-modelling paper with no molecular content), 2036 (the
  paper's own Table 3 reads `PD | Exons 2 and 3 | 3 families`, exon-level only);
* *measured, then generalised away by the source* — 708 (a fully sequenced BRCA2
  `c.156_157insAlu`, reduced to the word "TRUNCATING"), 709 (a characterised AluS insertion,
  reduced to "Alu insertion");
* *measured at a resolution that is not allele resolution* — 2367 (array-CGH bounds a deletion
  between probes; base-pair breakpoints exist in neither the paper nor the record).

### The two negative controls

Both are load-bearing. Without them a clean result set is an artefact of asking.

**Control 1 — a GET must not MINT a CAID** [set A]. If it did, every returned CAID would be
worthless as evidence. Submit several well-formed alleles nobody would have reported, then
re-fetch them:

```
NM_000551.3:c.301_311del          -> _:CA      (not registered)
NM_000551.3:c.288_299del          -> _:CA
NM_000551.3:c.271_282del          -> _:CA
NM_000551.3:c.396_397insTTAGGACC  -> _:CA
NM_000551.3:c.501_502insTTGTCCGT  -> CA020458  (registered, with dbSNP + ClinVar)
```

Re-fetching `c.301_311del` afterwards still returns `_:CA`. **GET does not mint; a CAID is
evidence.** Four requests. Run it every time.

**Control 2 — HTTP 200 is not a hit** [set B]. The blank-node `@id: "_:CA"` arrives with status
200 and a populated `genomicAlleles`. A classifier keying on the status code alone records it as
resolved. Assert on `@id`, not on `status`.

**Calibration, alongside the controls** [set A]. Run resolved records from the same corpus through
the identical code path and require the published CAID **and** rsID back. Five VHL siblings were
run (`c.526del`→CA16602180, `c.352_353insA`→CA357125, `c.540_543del`→CA357022,
`c.449A>G`→CA041030, `c.464-1G>T`→CA357144); all five matched on both.

---

## 9. The ordered procedure

```
 0. diff the source's snapshots            -> already filled? stop.                    §2
 1. pin the numbering frame                -> siblings if any, else MANE, justified.   §3
 2. build the local calculator + calibrate -> ref bases, exons, candidates, 3' norm.   §4
 3. read the name against it, classify     -> class-label | multi | legacy | modern.   §5
 4. class-label?    -> no_identity_exists, with a reason. NO allele lookup.            §8
 5. multi-alteration? -> split; run 6-11 per part; NEVER one identity for the record.  §10
 6. construct EVERY candidate reading      -> both readings of a legacy ins.           §5a
 7. registry, per candidate                -> six outcomes, kept apart.                §6a
 8. run the two negative controls          -> mint control, 200-is-not-a-hit.          §8
 9. collapse                               -> same CAID for both readings? not ambiguous.
10. discriminate, in rank order            -> §7. Stop at the first that answers.
11. still >1 and nothing discriminates     -> not_found. Report BOTH candidate CAIDs.  §10
12. build GRCh38 VCF form, assert ref base against your own slice.                     §6a
```

---

## 10. Withholding rules

Each is a rule, each was forced by a record.

**R1 — Two candidates both register and no ranked discriminator separates them: withhold.**
Report both candidate CAIDs; resolve neither. Forced by **1955** (`P71fs (c.211insT)`) and
**2131** (`Q73fs (c.214insGCCC)`), the only two `not_found` results across 43 records.

**R2 — The source's protein name matches neither candidate: that is not a tiebreak, it is a
second defect. Withhold.** Forced by **2131**: both readings give a first-changed residue of
Ser72 and the name says Q73. A name that fits neither candidate cannot select one.

**R3 — A name whose two halves name different *real* alleles is a defective name. Resolve both
halves, adjudicate by literature, and record the defect as a finding.** Forced by **2459**
(`L178P (c.532C>T)`): `c.533T>C` gives Pro (CA351756245, rs5030822) and `c.532C>T` is synonymous
(CA432423478, rs755146587). Both resolve cleanly, which is exactly why a one-half lookup never
notices. Adjudicated by rank-1 citation attribution. **[CIViC]** The source already publishes this
allele correctly as variant **1748**, so 2459 is a mis-typed duplicate of a resolved record.

**R4 — When ref and alt are inverted, the identity is the *reference-identity* allele, and you
must ask for it rather than assert it does not exist.** Forced by **4968** (`R72P`): codon 72 of
`NM_000546.6` is `CCC` = **Pro**, so the name has reference and alternate backwards, and the
allele the source means *is* the GRCh38 reference. It still has an identity — the registry mints
one for a reference-identity expression:

```
NM_000546.6:c.215C=       -> CA178298  "NM_000546.6(TP53):c.215C= (p.Pro72=)", rs1042522, ClinVar 165560
NC_000017.11:g.7676154G=  -> CA178298  (same allele reached from genomic coordinates)
NC_000017.11:g.7676154=   -> HTTP 400  (the reference base must be stated; bare "=" does not parse)
```

Publish `CA178298`, not `CA000072` — the latter is the Arg allele, the one the source does **not**
mean. A consumer schema requiring `ref != alt` cannot hold this allele at all, which is a property
of the consumer, not of the record.

**R5 — An rsID is position-level. Where the position carries more than one allele, the rsID does
not identify the allele; say which one is meant and how you know.** Forced by **2196** (both
`c.5127T>A` and `c.5127T>G` are `p.Asp1709Glu` and **both carry rs1890098663**, from the registry
*and* the recoder) and by **4968** (both codon-72 alleles carry rs1042522). Never resolve on an
rsID alone.

**R6 — Never mint one identity for a record naming two alterations.** Forced by **3298**
(`P81S (c.241C>T) and L188V (c.562C>G)`) and **4210** (`R167Q(c.500G>A) and c.464-94T>A`). Resolve
each part separately and report them as a pair; the record has no identity, the alterations do.

**R7 — Phase is withheld unless stated.** Co-segregation is not a statement of phase. For 3298 the
paper reports the two as "concurrent" germline mutations "co-segregating with the disease" in one
family (OMIM 608537: "cosegregated with the L188V mutation" in 6 members) — consistent with cis,
not a statement of it, and no reachable source uses the words cis, trans, allele or haplotype. For
4210 there is no abstract in PubMed and only front matter in PMC. Both withheld.

**R8 — Never substitute a representative record for a class, and never guess a breakpoint.**
Forced by **709**: the paper characterised a specific BRCA1 AluS insertion, but no accessible
source states its position and no BRCA1 ClinVar record cites the paper. ClinVar holds 25 distinct
BRCA1 Alu insertions; picking one would be fabrication. The position is recorded as unrecoverable.

**R9 — Never resolve on a protein-name search hit.** [set A] It retrieves same-consequence,
different-allele records. Three measured near-misses: `VHL[gene] AND "D143fs"` returns `c.426del`
when the wanted allele is `c.431del`; `"Q73fs"` returns `c.219_220del`, neither candidate;
`"P71fs"` returns `c.210_211ins**A**` when the wanted allele is `c.210_211ins**T**` — one base
apart. A pipeline accepting "the ClinVar record whose protein name matches" assigns three wrong
identities here.

**R10 — A negative is only as wide as the query that produced it.** Record the exact term. Escalate
a name-search zero to a `[chrpos38]` positional sweep before calling anything absent (§6b).

---

## 11. What this procedure cannot do

The union of both probes' honest limits. This half is the most useful part of the document.

**(a) Deciding which legacy exon-numbering convention a paper used.** Forced by **788**
(`IVS2+1G>A`). The structural derivation from the transcript's exon table gives `c.319+1`; the
right answer is `c.444+1`, because legacy papers number CHEK2 exons from the first *coding* exon
while transcript exon 1 is entirely 5′UTR. **Both readings are real registered alleles ~9 kb
apart** (CA10168045/rs765080766 vs CA288309/rs121908698), so nothing in the lookup flags the
error — it is a confident wrong answer. A script can fetch OtherNames; deciding that a legacy
alias outranks a structural derivation is the judgement.

**(b) Deciding which half of a self-contradictory name to believe.** Forced by **2459**. Both
halves resolved to real alleles. The judgement was that a protein name backed by the record's own
cited paper outranks a cDNA name producing a synonymous change under a missense label — i.e. that
the cDNA half is the typo. Reversing it is defensible on the bare text and yields a synonymous
variant. What made it decidable at all: `L178P` is *impossible* for `c.532C>T`, whereas
`c.533T>C` is *consistent* with both halves.

**(c) Reading a protein fragment as a claim, when the two halves of that claim bind differently.**
Forced by **1768**, **2091**, **2930**. `L129Q` had to be recognised as *substitution-shaped*, and
therefore as naming the first residue of `p.Leu129delinsGlnMet`, while the same curator's
insertion-shaped names look like `106insR`. `106insR` had to be read as asserting the *identity*
of the inserted residue (Arg), so "inserts Ala" disqualifies the other reading — while
simultaneously **not** asserting the residue *number*, since the correct answer is `p.Arg108dup`,
two residues away, because the insertion sits in a CGC repeat. Accepting the amino acid as binding
while treating the number as advisory is the judgement; a naive equality on either half alone gets
1768 and 2930 wrong in opposite directions.

**(d) Concluding that the source's protein name is wrong rather than that the identity is wrong.**
Forced by the 6-of-22 drift. The conclusion rests on the pattern in §7 — modern-spelled rows have
exact protein names, legacy-spelled rows drift — which had to be **noticed across the set**. On a
single row in isolation there is nothing to notice.

**(e) Deciding whether one line of evidence is enough.** Forced by **2196**. Two co-equal
candidates; the only discriminator is ClinVar's attribution of one PMID. Recorded as `resolved`
with both candidates kept and the single-line basis stated, because the brief asked which one
ClinVar attests. A consumer requiring two independent lines should read the record as withheld —
the record carries what is needed to make that call, and says so.

**(f) Deciding whether a database's *kind* is an argument.** Forced by **2131**. Ensembl returns an
HGMD germline accession for one reading and a COSMIC somatic id for the other. Preferring HGMD
because the row is a germline predisposition record is a real argument and would resolve the row.
It was declined: it is a claim about which database is the right kind for the row, not evidence
about this allele. Somebody may reasonably decide otherwise, but they should decide it explicitly
rather than let a script do it silently.

**(g) The class-label classifications, and the measured-vs-dropped distinction.** Deciding that
`TRUNCATING MUTATION` is a class while `3p26.3-25.3 11Mb del` is a *measurement at the wrong
resolution* is a reading of what the name asserts, not a lookup. The three-way split in §8 was
made by hand, per record, from abstracts.

**(h) Knowing when a negative is wide enough.** "Not in ClinVar" from a name search is nearly
worthless. Escalating to a positional sweep, and choosing the window, is a decision about how wide
a claim you are willing to make.

**(i) Diagnosing your own service failures.** Recognising that a burst of Ensembl 503s came from a
second copy of your own script rather than from Ensembl required looking at `ps`, not at the
response body. No amount of retry logic finds that.

**(j) Recovering a specific event the literature characterised but did not locate.** Forced by
**709**. The procedure can establish that a specific event exists and that its coordinates are not
in any reachable source. It cannot produce them.

---

## 12. Service failure modes, and the mitigation each needs

| service | failure | how it presents | mitigation |
| --- | --- | --- | --- |
| ClinGen registry | not registered | **HTTP 200** with `@id: "_:CA"` | assert on `@id`, never on status. `genomicAlleles` is still usable |
| ClinGen registry | wrong reference base | HTTP 400 *"…reference sequence is incorrect"* | this is **evidence** (§7 rank 4). Cache it; do not retry it |
| ClinGen registry | bad spelling | HTTP 400 `IncorrectHgvsPosition` | fix the expression. **Never record a negative** from this |
| ClinGen registry | position off transcript | HTTP 500 *"coordinates outside reference"* | a 500 that is really a 400. Check the position before retrying |
| Ensembl recoder | RefSeq `c.` input | reproducible **timeout >90 s**, `info/ping` healthy | query by GRCh38 genomic HGVS instead. Budget ~25 s/query, run detached |
| Ensembl recoder | `NM_…​.3` accessions | *"Could not get a Transcript object"* | same mitigation; genomic input sidesteps the version entirely |
| Ensembl recoder | overload | bare **503**s in a run | **check `ps` first — the cause may be your own second process.** One client, 1 rps, purge non-200s from cache before re-running, retry with backoff |
| NCBI E-utilities | concurrent own jobs | **HTTP 429** | serialise your NCBI work, or take sequence from Ensembl `sequence/region` (different host) |
| NCBI E-utilities | rate | ≤3 req/s unkeyed | pace at 0.4 s between calls |
| NCBI `efetch` clinvar | missing flag | returns nothing usable | `&is_variationid` is **required** with `rettype=vcv` |
| NCBI `elink` | batched PMIDs | **silently merges citedby links** into one flat list, producing a plausible wrong answer | query **one PMID at a time**; parse `linksets[].linksetdbs[].links` |
| publishers | paywall | Wiley 403; OUP serves the wrong article; LOVD 302 to an abuse page; HGMD needs registration | try PMC first; take HGMD accessions free via the recoder; otherwise withhold and say so |

**Caching.** Key by URL hash. Cache 2xx **and** sub-500 errors — those are answers. Do not cache
5xx or transport failures. Retry only on 5xx and transport, with backoff. Both probes' full query
trails replay for free from cache, which is what makes the recorded queries auditable.

---

## 13. What the two probes measured about the hypothesis

Stated as measurement, not as recommendation.

**43 of 43 records were asked at every applicable tier. 35 resolved, 6 have no identity to find,
2 are ambiguous between two real alleles.**

**For records that name an allele, the "unfilled column" reading holds — but only for the
identity, not for the fame.** Set A: only **9 of 22** have an rs-number at all; 9 of the 20
resolutions are registered CAIDs with no dbSNP and no ClinVar record, and 4 of those have no HGMD
or COSMIC id either. These are canonicalisable and now identified, and no resolver could have
produced an rsID for them because none exists.

**[CIViC] Spelling is a categorical blocker for one class and explains nothing about another.**
Legacy `c.<N>ins<SEQ>` names are 0 of 14 resolved corpus-wide, against ~83% otherwise, and the
mechanism is visible: the registry rejects the legacy form with HTTP 400. But 7 of set A's 22 and
several corpus-wide are *already* in modern HGVS and still unresolved — 3184 (`c.180del`) resolves
to CA020069 with rs730882037, ClinVar 182986, COSMIC and HGMD, and was simply not fetched. That is
omission, not notation.

**Some records are defective, not unfilled.** 2459 is a mis-typed duplicate of the source's own
resolved variant 1748; half of 4210 duplicates its resolved variant 1739; 4968 has reference and
alternate inverted; 1955 and 2131 are compatible with two separately-registered real alleles and
the source's own protein annotation fails to distinguish them (for 2131 it is wrong for both).
These cannot be fixed by a better resolver.

**Six records were correctly dropped.** For set B's class-labels no allele identity exists as
named, and dropping them as `unresolvable_identity` is accurate behaviour rather than a gap.

**Incidental** [CIViC]: 1779 is already flagged in the source's own data (`is_flagged=true`) and
resolves cleanly to CA020458 / rs398123483 / ClinVar 93329, with its protein name off by one
(`R167fs` for what is actually `p.Ser168LeufsTer5`).

---

## 14. Provenance

Both probes were run against live services on **2026-09-01**, from throwaway scripts in a session
scratchpad. **Those files are gone and are not what makes this reproducible** — the request shapes in
§§3–7 are, and every one of them is written out in full for that reason. What the scratchpad held, so
a reader knows what was behind each number: the two input sets (22 and 21 records), two result files
carrying 198 and 115 verbatim queries with their raw responses, the 114-record VHL sibling
calibration set of §3a, a local MANE v1.5 summary table, the nine-gene CDS comparison behind §0, and
a URL-keyed response cache.

The per-variant answers those files held are reproduced in
[CIVIC_UNRESOLVED](CIVIC_UNRESOLVED.md), which is the durable record of what this procedure returned.

Nothing in this document was taken on trust from the task framing; §0 is there because one thing in
the framing was wrong, and the control that settled it — submitting `NM_000551.3:c.197_220del` and
`NM_000551.4:c.197_220del` and getting the same CAID — was re-run independently before this document
was committed.
