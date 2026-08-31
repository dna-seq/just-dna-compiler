# Turning a variant name into an identity — the portable handout

A source publishes `N150fs (c.448delA)` and leaves every identifier column empty. The name is not a
shortfall in the record — it **is** the record. This is the procedure that reads it, ranked by what
each step can actually bear, and honest about the ten decisions it hands back to a human.

**What this file is, and what it is not.** It is the **source-agnostic** half of
[CIVIC_IDENTITY_PROTOCOL](CIVIC_IDENTITY_PROTOCOL.md), written to be carried to another source or
another repository. The protocol document is the evidence: it names the variant behind every rule,
carries the CIViC-specific spellings, and records what was measured. This one carries the *shape* and
drops the record ids. **Where the two disagree, the protocol wins** — it is the one with the
measurements attached.

Both are evidence, never contract. Nothing here is a decision, and no code in this repository
implements it. What the procedure was applied to, class by class with per-variant answers, is
[CIVIC_UNRESOLVED](CIVIC_UNRESOLVED.md); the 33 identities it produced that were adopted into the
builder are `enricher/src/just_dna_enricher/civic_identities.py` (RM159).

**Derived** from two independent probes over one dated release, 2026-09-01: 43 records, 313 recorded
queries, three read-only credential-free services. Yield **35 resolved · 2 withheld · 6 no identity**.
Counts are over those probes and are not a claim about any other corpus.

---

## The three outcomes

Every record ends as exactly one of these. Nothing else is a result.

| outcome | means | requires |
|---|---|---|
| **`resolved`** | exactly one candidate survives, named by a service — or several survive and a ranked discriminator picks one | the query that produced it; and when a discriminator chose, **every** candidate kept beside it |
| **`not_found`** | asked, nothing answered. **Never written as "does not exist"** | the failed queries stored beside it |
| **`no_identity_exists`** | the name denotes a **class** of event, so no allele can satisfy it. Decided at classification, *before* any lookup | a stated reason |

The last two are not interchangeable and their sources differ: `not_found` is what an ambiguous
**allele** produces, `no_identity_exists` is what a class **label** produces. A run that returns only
one of them over a mixed corpus has a classification bug.

---

## 00 · Establish the gap is real before spending a request

If the source ships more than one snapshot, diff them first. A record the source has since filled
needs no probe at all. Both probes did this and found all 43 records still empty in the later file.

> **Do not read staleness into a timestamp.** Every one of 21 records carried the same review date —
> and so did 753 of the 1,999 rows in the file. It was a bulk-import stamp. A date shared by a third
> of a corpus says nothing about any record in it.

---

## 01 · Pin the numbering frame by measurement, per gene

A `c.` or `p.` number means nothing until a transcript is named. This step decides whether the rest of
the procedure is arithmetic or guesswork, and it is where the largest mistake in the original survey
lived: it looked for a transcript field **on each record**, found one on 2 of 31, and wrote off the
other 29 as unreachable. **The frame is a property of the gene.** Testing a per-entity fact per record
cost 39 variants and shipped a false "permanent floor" conclusion into three documents.

### Route A — calibrate against the source's own resolved records

Strongest available, and it works whenever the source resolved *other* variants in the same gene.
Extract the `c.` fragment from each resolved sibling's name and compare it against every transcript
expression that sibling publishes. In one probe, **114 of 114 siblings agreed and none disagreed**.
This route also gives the frame the *curator* used, which matters when the source predates MANE.

### Route B — MANE Select, as a default rather than an answer

When a gene has no resolved siblings, take the transcript from the MANE summary table — then
cross-check it against the numbering the name implies. Two genes in eleven needed more:

| gene | what MANE gave | what the name meant | how it was settled |
|---|---|---|---|
| RUNX1 | residue 135 is Gly | legacy isoform numbering, offset 27 | Translate each candidate isoform's CDS and **locate the residue** — never apply a remembered offset. Confirmed when two expressions returned one registry id. |
| CDKN2A | two MANE transcripts, two CDS numberings | the p16 frame | The exon table decides. Confirmed by querying the other transcript's spelling for the same allele and getting the same id. |

### The trap that cost the most time

Submit `NM_000551.3:c.197_220del` and the registry answers with an allele it titles
`NM_000551.4:c.198_221del`. It looks exactly like a version bump shifting the numbering by one.
**It is not.**

```
NM_000551.3:c.197_220del  ->  CA645524685
NM_000551.4:c.197_220del  ->  CA645524685    identical
NM_000551.3:c.499C>T      ->  CA020450
NM_000551.4:c.499C>T      ->  CA020450       identical
```

Both versions return the same identifier and the CDSs are byte-identical. The shift is HGVS's 3′ rule
renormalizing a deletion inside a repeat, and the registry independently titles in the newest version
it knows — two unrelated behaviours that read as one causal story.

Believing the version story invites correcting a whole gene's positions by one, **and** teaches a
reader to wave through a genuine one-base mismatch as an artefact. Neither failure announces itself.
Measured across nine genes: the CDS **mRNA offset** does move on a version bump, sometimes hugely, but
`c.` numbering is CDS-relative and is untouched. Reading the GenBank `CDS` line and concluding
"everything shifted" is precisely the trap.

---

## 02 · Build the local calculator before touching the network

Fetch the RefSeq mRNA record once (`efetch db=nuccore rettype=gbwithparts`) and parse three things:
the spliced sequence from `ORIGIN`, the CDS offset from the `CDS join(...)` line, and every `exon`
feature converted to `c.` coordinates. That buys six local primitives, and each replaces a
recollection with a read.

| primitive | answers |
|---|---|
| `codon(n)` → bases, AA, `c.` of first base | what residue the reference actually has — this is what catches an inverted ref/alt |
| `base_at_c(n)` | whether the reference base a name asserts is real |
| `exon_table()` in `c.` coords | which intron a `+n` / `-n` name means |
| `candidates(pos, aa)` | every single-substitution route to a named residue — often more than one |
| 3′ normaliser | what spelling the registry will answer with |
| consequence calculator | `fs*N`, by re-translating past the CDS into the 3′UTR |

**The 3′ normaliser, in transcript orientation.** Two rules:

- deletion: while `base(start) == base(end+1)`, shift the whole interval one base 3′;
- insertion of `s` after `p`: while `s[0] == base(p+1)`, rotate `s` left and advance `p`; afterwards,
  if the `len(s)` bases ending at `p` equal `s`, the allele is a **dup**.

**Calibrate the calculator against the source's own resolved records before trusting it.** Pick
records where the source publishes both a name and a full expression, and require your calculator to
reproduce the published one.

---

## 03 · Classify the name — two classes are terminal

Read the name against the local calculator **before** any lookup. The class decides the route, and
getting this wrong wastes requests on records that can never resolve.

| class | looks like | route |
|---|---|---|
| **class label** | `TRUNCATING MUTATION`, `Rearrangement`, a cytoband range | terminal → `no_identity_exists`. **Do no allele lookup** |
| **multi-alteration** | two alterations in one name | split; run everything per part. **Never mint one identity for the record** |
| **legacy insertion** | `c.204insG` | two readings — generate both |
| **legacy redundant-base** | `c.430delG`, `c.417_418delTC` | drop the asserted bases *after* checking them |
| **legacy intronic / protein** | `IVS2+1G>A`, `R135fsX177` | do **not** convert structurally; use discriminators 1–2 |
| **modern HGVS** | `c.180del`, `c.272_273delinsAA` | one reading |
| **protein substitution** | `D1709E` | `candidates()`; may return several |

Then classify what the local read says about the name **itself**:

| local finding | meaning | action |
|---|---|---|
| reference AA/base matches | self-consistent | construct and query |
| reference AA differs, another isoform has it | legacy isoform numbering | find the isoform **by sequence**, not by a remembered offset |
| the name's two halves disagree | **contradictory name — a finding** | resolve both halves, adjudicate by literature |
| `candidates()` returns > 1 | the protein name is not allele-determining | carry **every** candidate forward |
| `candidates()` returns 0 | not one substitution away | stop; the transcript is probably wrong |
| the name's own ref base is absent from the CDS | the name is wrong | withhold before any lookup |

### Legacy insertions have two readings, and the source may not know which

`c.204insG` does not say whether the base goes before or after position 204. Generate both —
`c.204_205insG` and `c.203_204insG` — plus the `dup` spelling when the normaliser says so. The
registry canonicalises: an equivalent spelling returns the same id, and a **different** id proves the
two readings are genuinely different alleles.

**Never send the legacy form itself** — it returns HTTP 400. Measured: across one gene's 314 records,
legacy-spelled insertions were **0 of 14 resolved** against a corpus otherwise ~83% resolved. A
resolver that passes the source's name through unmodified fails on exactly this class, and fails
silently.

---

## 04 · Four tiers, ordered by the shape of the name

| tier | what it does | note |
|---|---|---|
| **a** · allele registry | constructed HGVS → a canonical allele id, coordinates, cross-references | six outcomes, kept apart; see the controls |
| **b** · NCBI by name | ClinVar and dbSNP searched on the name's own spellings | a zero is only as wide as the string searched |
| **c** · a second recoder | independent confirmation of an id or coordinate | route it by **genomic** coordinates, not transcript HGVS |
| **d** · literature | the record's own cited paper first, then search | **position depends on the name** — see below |

Endpoints, all read-only and credential-free:

```
GET https://reg.genome.network/allele?hgvs=<urlencoded>
    https://eutils.ncbi.nlm.nih.gov/entrez/eutils/{esearch,esummary,efetch,elink}.fcgi
GET https://rest.ensembl.org/variant_recoder/human/<expr>?content-type=application/json
```

**When to run the literature tier.** The two probes appeared to disagree here — one measured it
worthless, the other decisive four times. Both were right about their own material, and the merged
rule is conditional: **run it last** for a name that already states a DNA-level edit, because the
services will have settled it; **run it early** for a name stating only a consequence or a class,
where the paper is the only thing that can say what was actually observed.

---

## 05 · Discriminators, ranked by the weight each can bear

When more than one candidate survives tier (a), these separate them. **The half that matters is not
the ranking — it is what each one cannot settle.**

1. **Citation attribution** — which allele does a curated record attribute to the paper this record
   itself cites? Strongest available, because it binds a curated identity to the exact evidence the
   source used. Settled four records single-handedly.
   *Cannot settle:* an allele the curated database does not hold, or a paper nobody submitted against.
   Silent, not negative.
2. **Legacy alias lists in the curated record.** The only thing that resolves legacy notation, and it
   resolves it outright — one record carried both the legacy and modern spellings of the same intron,
   which is what settled a conversion the exon table got wrong.
   *Cannot settle:* anything not curated into that database; and it cannot tell you a legacy name is
   *absent* rather than differently spelled.
3. **Only one candidate is registered.** Cheap, unambiguous, available for every candidate.
   *Cannot settle:* anything where both readings are registered — 5 of 11 legacy insertions. And
   registration is not rarity: 9 of 20 resolutions had no external cross-reference at all.
4. **The registry's reference-base validation, used as a direction test.** Submit *both* opposite
   expressions and let the service reject one. Exactly one is accepted, which says which base is
   reference. This is what catches an inverted ref/alt.
   *Cannot settle:* which allele the curator *meant*. It answers which base is reference, nothing more.
5. **External corroboration on exactly one candidate.** A literature-curation accession on one reading
   and nothing on the other is real evidence for that reading.
   *Cannot settle:* a row where both readings carry one — or where two databases disagree in *kind*.
   Preferring a germline database because the row is germline is an argument about database kind, not
   evidence about the allele.
6. **Protein-consequence concordance.** The consequence computed from each candidate against the
   name's protein fragment.
   *Cannot settle:* anything on its own where the source's protein names drift. See the binding rule.
7. **Second-service agreement on an identifier.** A strong corroborator: 19 of 19 constructed
   expressions agreed across two services.
   *Cannot settle:* which of two alleles at one position is meant. A corroborator, never a
   discriminator.
8. **General web search.** Some weight for well-studied substitutions, effectively none for indels.
   Run it last, believe it least.

### The binding rule — settle this before using discriminator 6

**The DNA-level edit is the identity anchor. The protein fragment discriminates between candidate
readings; it is never a veto.**

In one probe the source's protein name was off by one from the correct consequence of the source's
**own** cDNA fragment in 6 of 22 rows. The discordance is internal to the name, so any correct
identity disagrees with it the same way — treating the protein name as a veto rejects every true
answer.

What must match is the **consequence class**: frameshift / nonsense / in-frame / synonymous /
missense. The **residue number is advisory**. That single distinction reconciles what looked like a
conflict between the two probes: one saw numbers drift, the other rejected a candidate whose *class*
was wrong. Same rule, two faces.

One correlation worth knowing: rows whose protein name was exactly right were the ones spelled in
modern HGVS. Legacy-spelled rows drift — a legacy protein name was transcribed from a paper, a modern
one was computed.

---

## 06 · Two negative controls, both load-bearing

Without these, a clean result set is an artefact of asking.

**Control 1 — a read must not create the thing it reads.** If querying an allele registry *minted* an
identifier, every id you got back would be worthless as evidence. Submit several well-formed alleles
nobody would have reported, confirm they come back unregistered, then re-fetch and confirm they still
do.

```
c.301_311del           -> unregistered
c.288_299del           -> unregistered
c.396_397insTTAGGACC   -> unregistered
c.501_502insTTGTCCGT   -> registered, with external cross-references
re-fetch c.301_311del  -> still unregistered.   A GET does not mint.
```

Four requests. Run it every time.

**Control 2 — a 200 is not a hit.** The registry returns **HTTP 200** with a blank-node `@id` and a
populated payload for an allele it does not hold. A classifier keying on the status code records it as
resolved. **Assert on the identifier, never on the status.**

Alongside both, **calibrate**: run already-resolved records from the same corpus through the identical
code path and require the published identifiers back.

---

## 07 · When to withhold

Each is a rule because a record forced it. Withholding is a result, not a failure to finish.

| | rule | forced by |
|---|---|---|
| **R1** | Two candidates both register and no ranked discriminator separates them — **withhold, and report both ids**. Resolve neither. | 2 of 43 records, the only two that ended here |
| **R2** | The source's name matches **neither** candidate: that is not a tiebreak, it is a second defect. A name that fits neither candidate cannot select one. | both readings gave one residue, the name said another |
| **R3** | A name whose two halves name different **real** alleles is a defective name. Resolve both halves, adjudicate by literature, and **record the defect as a finding** — it is worth more than the resolution. | a missense label over a synonymous cDNA change; both resolved cleanly |
| **R4** | If the direction test shows the source means the **reference** allele, the identity is the reference-identity expression, not the surviving variant candidate. Many schemas cannot represent this at all. | a name with ref and alt inverted |
| **R5** | An identifier that is **position-level** does not distinguish alleles at that position. Say which allele is meant and whether the identifier can carry it. | two alleles spelling one substitution, sharing one identifier |

---

## 08 · What this procedure cannot do

The most useful section, and the one to read before promising anyone a throughput number. Roughly one
record in eight needed a human. These are decisions the procedure reaches and hands back.

- **Deciding which legacy convention a paper used.** A structural derivation from the exon table gave
  one intron; the right answer was another, because legacy papers numbered exons from the first
  *coding* exon. Both readings were real registered alleles ~9 kb apart, so nothing in the lookup
  flagged it — a confident wrong answer. A script can fetch the aliases; deciding that an alias
  outranks a derivation is the judgement.
- **Deciding which half of a self-contradictory name to believe.** Both halves resolved to real
  alleles. What made it decidable at all was that one half was *impossible* for the other, while the
  reverse reading was merely consistent.
- **Reading a protein fragment as a claim when its two halves bind differently.** One name had to be
  read as asserting the identity of an inserted residue while **not** asserting its number — the
  correct answer sat two residues away because the insertion was in a repeat. A naive equality on
  either half alone gets neighbouring records wrong in opposite directions.
- **Concluding that the source's protein name is wrong rather than the identity.** That conclusion
  rests on a pattern noticed *across the set*. On a single row in isolation there is nothing to notice.
- **Deciding whether one line of evidence is enough.** One record had two co-equal candidates and a
  single discriminator. Recorded as resolved with both candidates kept and the single-line basis
  stated, so a stricter consumer can read it as withheld. The record carries what is needed either way.
- **Deciding whether a database's *kind* is an argument.** Declined deliberately. Somebody may
  reasonably decide otherwise — they should decide it explicitly rather than let a script do it
  silently.
- **Drawing the line between a class label and a measurement at the wrong resolution.** Deciding that
  one name is a class while another is a real measurement bounded by array probes is a reading of what
  the name asserts, not a lookup.
- **Knowing when a negative is wide enough.** "Not in the database" from a name search is nearly
  worthless. Escalating to a positional sweep, and choosing the window, is a decision about how large
  a claim you are willing to make.
- **Diagnosing your own service failures.** Recognising that a burst of 503s came from a second copy
  of your own script required looking at the process table, not the response body. No retry logic
  finds that.
- **Recovering an event the literature characterised but did not locate.** The procedure can establish
  that a specific event exists and that its coordinates are in no reachable source. It cannot produce
  them.

---

## 09 · Service failure modes worth pre-empting

| failure | how it presents | mitigation |
|---|---|---|
| allele not registered | **HTTP 200** with a blank-node id | assert on the id, never the status |
| wrong reference base | HTTP 400, *"reference sequence is incorrect"* | this is **evidence**, not an error. Cache it; do not retry |
| bad spelling | HTTP 400, position error | fix the expression. **Never record a negative from this** |
| position off transcript | HTTP 500 | a 500 that is really a 400. Check the position before retrying |
| recoder given transcript HGVS | reproducible timeout, service otherwise healthy | query by genomic coordinates instead — sidesteps versions entirely |
| bursts of 503 | looks like upstream overload | **check your own process table first.** One client, one request per second |
| citation links, batched | **silently merges** into one flat list — a plausible wrong answer | query one identifier at a time |
| NCBI, concurrent own jobs | HTTP 429 | serialise; ≤3 req/s unkeyed, pace at 0.4 s |
| paywalls | 403, or the wrong article served | try the open archive first; otherwise withhold and say so |

**Cache by URL hash, and cache sub-500 errors too** — those are answers, not failures. Do not cache
5xx or transport failures; retry only those, with backoff. A cached trail is what makes every recorded
query auditable and a re-run free.

---

## 10 · What the yield actually looked like

| set | shape | `resolved` | `not_found` | `no_identity_exists` |
|---|---|---:|---:|---:|
| A | small indels named by a cDNA fragment | 20 | 2 | 0 |
| B | substitutions, splice, class labels, conjunctions | 15 | 0 | 6 |

The distributions are near-complementary, and that is the point rather than a coincidence: the two
sets differ by name shape.

**Two findings that outweighed the count:**

- **The premise was half wrong.** "A name-only record must be a famous allele with a forgotten
  identifier" held for fewer than half. The *identity* existed for nearly all of them; the *fame* did
  not — 9 of 20 resolutions carried no external cross-reference at all. Do not size this work by how
  well-known the variants look.
- **Sources duplicate themselves.** Three unresolved records turned out to name alleles the same
  source had already resolved under a different record. An identity pass that reaches both maps two
  record ids onto **one allele** — which touches deduplication, grouping, and any "already present"
  logic downstream. Budget for it.

---

## The ordered procedure, in one block

```
 0. diff the source's snapshots          -> already filled? stop.                §00
 1. pin the numbering frame              -> siblings if any, else MANE, justified §01
 2. build the local calculator, calibrate-> ref bases, exons, candidates, 3' norm §02
 3. read the name against it, classify   -> class-label | multi | legacy | modern §03
 4. class-label?      -> no_identity_exists, with a reason. NO allele lookup.
 5. multi-alteration? -> split; run 6-11 per part; NEVER one identity per record.
 6. construct EVERY candidate reading    -> both readings of a legacy insertion.  §03
 7. registry, per candidate              -> outcomes kept apart.                  §04
 8. run the two negative controls        -> mint control, 200-is-not-a-hit.       §06
 9. collapse                             -> same id for both readings? not ambiguous.
10. discriminate, in rank order          -> stop at the first that answers.       §05
11. still >1 and nothing discriminates   -> not_found. Report BOTH candidate ids.  §07
12. build the VCF form, assert the ref base against your own sequence slice.
```

---

**Scope of every claim here.** Counts are over two probes against one dated release on 2026-09-01, and
the services as they stood that day. Every rule exists because a record forced it; the record is named
in [CIVIC_IDENTITY_PROTOCOL](CIVIC_IDENTITY_PROTOCOL.md). Where a step is specific to one source's
spelling habits rather than general, treat the shape as transferable and the specifics as not.
