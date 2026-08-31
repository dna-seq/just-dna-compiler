# CIViC survey — what the source actually contains, measured

**Probed** 2026-08-31 against `https://civicdb.org/api/graphql`, the public GraphQL API. No key, no
authentication, no rate-limit headers observed. **Licence** CC0 1.0 Universal for the content (the MIT
licence covers their application source, not the data) — so `redistribution` and `commercial_use` are
both permitted and `licensing.py`'s existing `cc0` entry already spells it. It asks nothing in return — no share-alike, no bar on sale, attribution requested rather than required — which is what distinguishes it from the several sources here that also permit redistribution.

**This is evidence, never contract** — the standing rule for everything under `docs/probes/`. Nothing
here is a decision. The decisions live in [ROADMAP.md § RM152](../ROADMAP.md) and in the
[0.7 proposal addendum](../proposals/PROPOSAL_0_7.md); where this document and those disagree, they win.

**Why it exists.** RM152 was filed from S84's report, then its ROADMAP section was destroyed by a
concurrent edit and rebuilt from two surviving records — its prose is a reconstruction and its own
block-quote warns a reader to suspect it. The numbers below are the primary record, each one paired
with the query that produced it, so the next reader neither re-runs these queries blind nor trusts a
reconstruction. Every figure obtained by **subtraction** rather than by querying is flagged as such;
there is one, and S84's original report is where it came from.

## How to re-derive any number here

Every count is a `totalCount` on a filtered `evidenceItems` or `assertions` connection. The whole
survey is reproducible with:

```python
import json, urllib.request
URL = "https://civicdb.org/api/graphql"

def gq(query, variables=None):
    body = {"query": query} | ({"variables": variables} if variables else {})
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    if "errors" in d:
        raise RuntimeError(d["errors"])
    return d["data"]

def count(**kw):                      # e.g. count(variantOrigin="RARE_GERMLINE")
    args = ", ".join(f"{k}: {v}" for k, v in kw.items())
    return gq("{ evidenceItems(%s) { totalCount } }" % args)["evidenceItems"]["totalCount"]
```

Paging uses `first: 50` with `pageInfo { hasNextPage endCursor }` and an `after:` cursor. Enum members
come from introspection, `{ __type(name: "VariantOrigin") { enumValues { name } } }`, rather than from
the documentation — which is the `@probe-the-real-file` rule applied to an API.

## The vocabularies, from introspection

| Enum | Members |
|---|---|
| `VariantOrigin` | `SOMATIC`, `RARE_GERMLINE`, `COMMON_GERMLINE`, `UNKNOWN`, `COMBINED`, `MIXED`, `NA` |
| `EvidenceType` | `DIAGNOSTIC`, `PROGNOSTIC`, `PREDICTIVE`, `PREDISPOSING`, `FUNCTIONAL`, `ONCOGENIC` |
| `EvidenceDirection` | `SUPPORTS`, `DOES_NOT_SUPPORT`, `NA` |
| `EvidenceLevel` | `A`, `B`, `C`, `D`, `E` |
| `EvidenceSignificance` | 24 members, spanning several axes at once — `SENSITIVITYRESPONSE`, `RESISTANCE`, `BETTER_OUTCOME`, `POOR_OUTCOME`, `POSITIVE`, `NEGATIVE`, `NA`, `ADVERSE_RESPONSE`, `PATHOGENIC`, `LIKELY_PATHOGENIC`, `BENIGN`, `LIKELY_BENIGN`, `UNCERTAIN_SIGNIFICANCE`, `REDUCED_SENSITIVITY`, `GAIN_OF_FUNCTION`, `LOSS_OF_FUNCTION`, `UNALTERED_FUNCTION`, `NEOMORPHIC`, `UNKNOWN`, `DOMINANT_NEGATIVE`, `PREDISPOSITION`, `PROTECTIVENESS`, `ONCOGENICITY`, `LIKELY_ONCOGENIC` |

**`EvidenceSignificance` is not one axis.** It carries therapy response, prognosis, ACMG clinical
significance, protein-function effect and predisposition in a single field — which is why no single
map from it into this format's vocabularies exists, and why the useful question is always
*significance × evidenceType × evidenceDirection* rather than significance alone.

## The denominator nobody declared — read this before quoting any number

`evidenceItems` and `assertions` both default to **`status: NON_REJECTED`**. Not `ACCEPTED`, not
`ALL`. Every figure in S84's report, in RM152, and in this document rides on that default, and none of
them said so:

| | default | `NON_REJECTED` | `ACCEPTED` | `SUBMITTED` | `REJECTED` | `ALL` |
|---|---|---|---|---|---|---|
| Evidence items | 11,518 | 11,518 | 4,904 | 6,614 | 421 | 11,939 |
| Assertions | 296 | 296 | 147 | 149 | 18 | 314 |

So **`SUBMITTED` is the majority of CIViC** — 6,614 of 11,518 — and `SUBMITTED` means an item a
curator entered that no editor has signed off. A survey that reads the default is reading mostly
unreviewed content. This is the `@probe-the-real-file` rule biting on an API: the documented totals and
the served totals differ by a filter the schema applies silently.

**Nothing here is wrong because of it** — the default is a reasonable basis and the comparison to
ClinVar is roughly like-for-like — but any adoption must *state* the basis, and the numbers move a lot
when it changes. See the curation-status section below, where restricting to `ACCEPTED` takes the
contested count to zero.

## Scale, and the germline fraction

| | Evidence items |
|---|---|
| Total (`NON_REJECTED`, the default) | 11,518 |
| `SOMATIC` | 7,376 |
| `RARE_GERMLINE` | 3,018 |
| `COMMON_GERMLINE` | 85 |
| `UNKNOWN` | 374 |
| `NA` | 627 |
| `COMBINED` | 20 |
| `MIXED` | 18 |

The seven buckets **sum to 11,518 exactly**, so the enum partitions cleanly and no item is missing an
origin. S84 reported the last three as `412` by subtraction; queried individually they are 374 + 20 +
18 = 412, so the subtraction was sound. Germline is `RARE_GERMLINE + COMMON_GERMLINE` = **3,103,
26.9%**.

**CIViC is a somatic cancer-interpretation resource.** That is not a criticism of the source — it is
what the source is for. The consequence for this format is only that 73% of it describes tumour tissue
no consumer's germline genotype can satisfy.

## The clinical-significance axis: why the concordance route died

Of the 3,103 germline items, the ACMG five-tier — the only members `VALID_CLIN_SIG` can receive — is:

| | Germline items |
|---|---|
| `UNCERTAIN_SIGNIFICANCE` | 594 |
| `PATHOGENIC` | 4 |
| `LIKELY_PATHOGENIC` | 1 |
| `BENIGN` | 0 |
| `LIKELY_BENIGN` | 0 |
| **five-tier total** | **599** |

The largest single germline significance is `NA` at 812. The full germline histogram sums to 3,103:
`PREDISPOSITION` 1,456 · `NA` 812 · `UNCERTAIN_SIGNIFICANCE` 594 · `SENSITIVITYRESPONSE` 121 ·
`LOSS_OF_FUNCTION` 24 · `POOR_OUTCOME` 23 · `GAIN_OF_FUNCTION` 14 · `RESISTANCE` 13 ·
`BETTER_OUTCOME` 12 · `ADVERSE_RESPONSE` 11 · `POSITIVE` 6 · `DOMINANT_NEGATIVE` 5 · `PATHOGENIC` 4 ·
`NEOMORPHIC` 2 · `ONCOGENICITY` 2 · `PROTECTIVENESS` 2 · `LIKELY_PATHOGENIC` 1 · `NEGATIVE` 1.

**The operative number is 5, not 3,103.** The `clin_sig` concordance check's entire product is
*opposition* — a pathogenic-class call set against a benign-class one — and `concordance.py` states in
terms that an uncertain call opposes nothing and sits in the `undecided` camp. An authority holding 5
calls in one camp and **0** in the other cannot make `discordant` sayable about anything; joined, it
would read `single` or `concordant` by construction.

## The direction axis: where the germline mass actually sits

By evidence type, the germline subset is **2,867 of 3,103 `PREDISPOSING`**. By significance, the
direction-bearing pair is `PREDISPOSITION` 1,456 + `PROTECTIVENESS` 2 = **1,458**. Crossed with
`evidenceDirection`:

| | `SUPPORTS` | `DOES_NOT_SUPPORT` | `NA` |
|---|---|---|---|
| `PREDISPOSITION` | 1,452 | 4 | 0 |
| `PROTECTIVENESS` | 2 | 0 | 0 |

**Direction `NA` is 0 of 1,458.** Every germline predisposition/protectiveness item carries a stated
direction — which is the one respect in which this axis is *better* populated than `clin_sig`, where
812 of 3,103 are `NA`.

Mapped onto this format's `VALID_DIRECTIONS` (`protective` / `risk` / `neutral` / `unknown` /
`contested`), the camps are **1,452 risk-class against 2 protective-class**. That is the same shape
that killed the clin_sig route, with a smaller minority camp.

### Contests, at variant granularity — and the grouping that gets this wrong

**Group by variant, never by molecular profile.** A molecular profile may name several variants, and
one variant may appear in several profiles, so profile-grouping *understates* contests. Measured both
ways over the same 1,458 rows: profile-grouping finds **1** contested subject, variant-grouping finds
**3**. The two extra are real and the mechanism is worth stating — MP5278 is a two-variant profile
(`VHL S183L AND VHL D126N`) carrying the single `DOES_NOT_SUPPORT` item eid 8721, which propagates to
*both* member variants, and each of those carries `SUPPORTS` evidence on its own separate
single-variant profile. Nine variants in this set appear in more than one profile.

Exploded over `molecularProfile.variants[]`: 620 distinct variants, 1,464 (variant, evidence) pairs,
213 variants with more than one item. Camp sets: `{risk}` 613 · `{risk, not_risk}` **3** ·
`{not_risk}` 2 · `{protective}` 2. No variant reaches three camps.

**The three contested variants, in full:**

| Variant | Camps | Items |
|---|---|---|
| 2161 `VHL S183L (c.548C>T)` | risk, not_risk | ev 10733 `SUPPORTS` C PMID 34439168 · ev 5797 `SUPPORTS` C PMID 24466223 · ev 8721 `DOES_NOT_SUPPORT` C PMID 21454469 |
| 2428 `VHL G104V (c.311G>T)` | risk, not_risk | ev 7134 `SUPPORTS` C PMID 29789510 · ev 10949 `DOES_NOT_SUPPORT` C PMID 33618821 |
| 2533 `VHL D126N (c.376G>A)` | risk, not_risk | ev 10770 `SUPPORTS` C PMID 28043156 · ev 8721 `DOES_NOT_SUPPORT` C PMID 21454469 |

**All three are `risk` against `not_risk` — a claim and its refutation. Genuine opposition
(`risk` against `protective`) is 0.** Two further variants carry only `{not_risk}` (variant 788
`CHEK2 IVS2+1G>A` ev 1854; variant 4968 `TP53 R72P` ev 1302) — a lone refutation with nothing
asserting the claim, which is **not** contested. Two carry only `{protective}` (variant 4980
`AXIN2 rs143348853` ev 12065; variant 258 `MTHFR A222V` ev 1756).

So RM152's *"`PREDISPOSITION` × `DOES_NOT_SUPPORT` is 4 items, precisely the reading `contested` was
added for"* is wrong in both directions: the contested count at the right granularity is **3, not 4**,
and two of the four items it counts are lone refutations that `contested` does not describe.

### Widening the scope changes nothing, and that is the useful result

All 620 variants were re-swept with **no** origin, significance, type or status filter —
`evidenceItems(variantId: N)` paged whole, 2,811 distinct evidence items. (Paging at `first: 200`, not
50: variant 1747 carries 103 items and 1739 carries 99.)

- Origins now in scope: `RARE_GERMLINE` 2,590 · `SOMATIC` 172 · `UNKNOWN` 20 · `COMMON_GERMLINE` 17 ·
  `COMBINED` 10 · `NA` 7 · `MIXED` 4.
- **1,342 of those items are campless** — `NA` 660, `UNCERTAIN_SIGNIFICANCE` 499, and the rest on
  therapy/prognosis/function axes. They cannot create a contest.
- 11 new camp-bearing items appear, **every one `PREDISPOSITION`/`SUPPORTS`**, all on VHL variants
  that already carried `risk`.
- **Additional contested variants found by widening: 0.** Not one variant's camp *set* changed.

**Scope of that zero** (`@probe-names-the-table`): it is over the 620 variants that appear in the 1,458
germline direction rows. A CIViC variant whose only camp-bearing evidence has a non-germline origin was
never a candidate and was not probed. This is not a statement about CIViC as a whole.

### The curation-status axis, which nothing in the report or the roadmap mentions

Every evidence item carries a `status`, and it is **not** evenly distributed: of the 1,458 germline
direction rows, **925 are `SUBMITTED` and 533 `ACCEPTED`**. Over the widened 2,811, it is 2,091
`SUBMITTED` to 729 `ACCEPTED`. `SUBMITTED` means an item a curator has entered and no editor has
signed off.

**Restricted to `ACCEPTED`, the contested count is 0.** All three contests dissolve: eids 10949 and
8721 are `SUBMITTED`, and for variants 2161 and 2533 the `SUPPORTS` side is `SUBMITTED` too. 330 of
620 variants have no `ACCEPTED` camp-bearing item at all.

This is the axis a `confidence`/`confidence_unit` pair is for — `ClinSigAuthorityCallRow` already
requires a magnitude to name its instrument, and `status` is CIViC's own, unconverted. Any adoption
must decide whether `SUBMITTED` items are read at all; the answer changes every number above.

### Provenance is per record, and every one is a PMID

`evidenceType` is `PREDISPOSING` for all 1,458 and `source.sourceType` is **`PUBMED` for all 1,458**.
So every row carries a real PMID — per-record provenance already in the shape `studies.csv` wants,
which is the strongest thing this source has going for it and is unaffected by every negative finding
above. Level and rating are tabulated below.

### Combination genotypes arrive in two encodings, and one of them does not decompose

Of the 625 profiles, **6 name more than one variant** — all VHL, all exactly two variants, all joined
by an uppercase `" AND "`, carrying one row each.

But that is not CIViC's only encoding. **24 single-variant records carry a conjunction inside the
variant's own `name`** — one variant id, one profile, a name describing two to four alterations:
variant 4181 `C162Y(c.486C>G) and L188V(c.562C>G) and P81S(c.241C>T) and F119L(c.357C>G)`, variant
4096 `R161* (c.481C>T) AND R200fs (c.598del)`, variant 3314 `rs1801270 and rs1059234`, variant 4192
`Deletion AND I151S(c.452T>G)`.

**Exploding over `molecularProfile.variants[]` does not decompose these** — they stay one variant id
with a compound name. The name-level encoding is four times more common here than the profile-level
one (24 vs 6). Any drafter must handle both, or it will mint one identity for what the source is
describing as several alterations.

### The corpus is VHL-dominated

Per-variant germline direction-item counts run from 1 (407 variants) to **48** — variant 1739,
`VHL R167Q (c.500G>A)`. The next eight are also VHL: R167W 41, R161* 33, F76del 32, R161Q 27, N78S 19,
Y98H 18, Exon 3 Deletion 17, S65W 16. A survey of this set is substantially a survey of VHL.

## Scope: both tables, and why the assertions zero is structural

The finding must be as wide as `evidenceItems` **and** `assertions`, and no wider
(`@probe-names-the-table`). `assertions` takes **no** `variantOrigin` argument — confirmed by
introspection — so all 296 were paged and split per record.

**Origin split of the 296:** `SOMATIC` 275 · `RARE_GERMLINE` 6 · `MIXED` 6 · `UNKNOWN` 6 ·
`COMBINED` 3 · `COMMON_GERMLINE` **0**.

**All 296 assertions are `SUPPORTS`.** Verified server-side rather than by tallying:
`assertionDirection: DOES_NOT_SUPPORT` returns 0 on the default basis and 1 under `status: ALL` — the
single one that exists is among the 18 rejected.

The six germline assertions are all `PREDISPOSING`, all `SUPPORTS`, all with `ampLevel: null`:

| | `SUPPORTS` |
|---|---|
| `PATHOGENIC` | 4 |
| `LIKELY_PATHOGENIC` | 1 |
| `UNCERTAIN_SIGNIFICANCE` | 1 |

AID4 (var 1739 `VHL R167Q`) · AID14 (var 1956 `VHL E70K`) · AID17 (var 2088 `VHL F76del`) ·
AID18 (var 1810 `VHL Q195*`) · AID41 (var 1776 `VHL L184P`) · AID42 (var 1747 `VHL R167W`).

**Germline assertions carrying `PREDISPOSITION` or `PROTECTIVENESS`: 0 — and the zero is structural,
not empirical.** `AssertionSignificance` is a *different and smaller* enum than `EvidenceSignificance`
— 16 members against 24. `PREDISPOSITION`, `PROTECTIVENESS`, `ONCOGENICITY`, `GAIN_OF_FUNCTION`,
`LOSS_OF_FUNCTION`, `DOMINANT_NEGATIVE`, `NEOMORPHIC`, `UNALTERED_FUNCTION` and `UNKNOWN` are **not
members of it**, and `ONCOGENIC` is assertion-only. Filtering assertions by
`significance: PREDISPOSITION` is a GraphQL *type error*, not an empty result.

That is a stronger statement than a count: **no CIViC assertion can ever carry the direction axis.**
The assertions table is not a thin source of direction evidence — it is structurally incapable of
holding any, so it cannot become one as the database grows.

## The origins outside the germline pair contribute almost nothing

The reporter's germline filter is `RARE_GERMLINE + COMMON_GERMLINE`, and a filter whose scope is
narrower than its name is the defect RM152 itself names. So the other 1,039 items were paged in full
and every cell independently re-derived as a server-side filtered `totalCount`:

| Origin | Items | `PREDISPOSITION`/`SUPPORTS` | `PREDISPOSITION`/`DOES_NOT_SUPPORT` | `PROTECTIVENESS` |
|---|---|---|---|---|
| `UNKNOWN` | 374 | 3 | 0 | 0 |
| `COMBINED` | 20 | 2 | 0 | 0 |
| `MIXED` | 18 | 0 | 0 | 0 |
| `NA` | 627 | 3 | 0 | 0 |
| **total** | **1,039** | **8** | **0** | **0** |

**Eight rows.** All `PREDISPOSING`, all `SUPPORTS`, seven of the eight on VHL/FBXW7/KLLN. Widening the
origin filter to everything a VCF could plausibly reach adds 8 to 1,458 and adds **zero** to either
minority camp.

## The whole germline set by type and direction

All 3,103 germline items, not just the `PREDISPOSING` 2,867:

| `evidenceType` | `SUPPORTS` | `DOES_NOT_SUPPORT` | `NA` | Total |
|---|---|---|---|---|
| `PREDISPOSING` | 2,054 | 4 | 809 | 2,867 |
| `PREDICTIVE` | 130 | 15 | 0 | 145 |
| `FUNCTIONAL` | 41 | 4 | 0 | 45 |
| `PROGNOSTIC` | 31 | 6 | 0 | 37 |
| `DIAGNOSTIC` | 5 | 2 | 0 | 7 |
| `ONCOGENIC` | 2 | 0 | 0 | 2 |
| **total** | **2,263** | **31** | **809** | **3,103** |

**31 germline items carry `DOES_NOT_SUPPORT`, but only 4 of them are on the direction axis.** The
other 27 sit on therapy, prognosis and protein-function significances — real disagreement, on axes
this format does not model as `direction`. So no direction-bearing predisposition signal lives outside
`PREDISPOSING`.

**809 `PREDISPOSING` germline rows carry `evidenceDirection: NA` *and* `significance: NA`** — neither
supporting nor refuting. A third state, and the reason the earlier "direction `NA` is 0 of 1,458"
holds: those 809 fall outside the 1,458 because their significance is `NA`, not because they have a
direction.

## Evidence level and rating

| Level | `SUPPORTS` | `DOES_NOT_SUPPORT` |
|---|---|---|
| A | 2 | 0 |
| B | 38 | 2 |
| C | 1,413 | 2 |
| D | 1 | 0 |
| E | 0 | 0 |

Ratings 1–5: 18 · 331 · 982 · 122 · 5. No nulls in either column. The corpus is **97.1% level C,
rating 3**.

Two things this kills, both of which would be tempting shortcuts:

- **"The refutations are weak, so discount them."** Two of the four `DOES_NOT_SUPPORT` rows are level
  **B** and `ACCEPTED` — EID1854 (`CHEK2 IVS2+1G>A`, B/2) and EID1302 (`TP53 R72P`, B/4). They are not
  uniformly weak, and a rule that dropped them would be discarding the better-reviewed half.
- **"The protective pair is noise."** EID12065 (`AXIN2 rs143348853`) is **level A, rating 5** — the
  highest-quality item in the entire 1,458 — though `SUBMITTED`. The minority camp is tiny and is not
  low-grade.

## Genome build — and the identifiers that make it survivable

### The coordinates really are GRCh37

`ReferenceBuild` introspects as `{NCBI36, GRCH37, GRCH38}`, so GRCh38 is *permitted*. It is almost
never *used*. Over the whole corpus (all 5,065 variants: 4,624 `GeneVariant`, 415 `FusionVariant`, 23
`FactorVariant`, 3 `RegionVariant`):

| `referenceBuild`, gene variants | Count |
|---|---|
| `null` | 2,433 |
| `GRCH37` | 2,189 |
| `GRCH38` | **2** |

The two exceptions are id 2885 `ABL1 T315V` and id 5371 `MEN1 T344M`. `ensemblVersion` is **75** on
1,753 records — the terminal GRCh37 Ensembl release. **`coordinates` takes no arguments**: there is no
query path that asks for a build, so a client gets whatever the curator stored.

Over the 620 variants behind the 1,458 germline direction rows: `GRCH37` 376 · `null` 244 · `GRCH38`
0. Coordinate completeness: full `chrom+start+ref+alt` 289 · `chrom+start` only 86 · none 245.

**This format is GRCh38-only** — `refget_accession` raises outside GRCh38, `genome_build` lives in the
manifest and is injected at load, and multi-build identity is RM15, deferred to 1.0 as an
identity-change. So **no CIViC coordinate is directly usable**, and the 987 evidence rows on a
fully-coordinated single-variant profile are 987 rows of *GRCh37*: a blocker, not a reach figure.

### But CIViC publishes build-independent identifiers, and that changes the answer

The coordinate is not the only identity CIViC carries. Measured over the same 620:

| Identifier | Non-null | On the 376 with coordinates | On the 244 without |
|---|---|---|---|
| `alleleRegistryId` (ClinGen CAID) | **363** | 363 | 0 |
| `myVariantInfo.dbsnpRsid` | **275** | 275 | 0 |
| rsID in `variantAliases` | 174 | 174 | 0 |
| **union rsID, either source** | **276** | 276 | 0 |
| `myVariantInfo.clinvarHgvsGenomic` carrying a **GRCh38** `NC_` accession | **252** | 252 | 0 |
| union GRCh38-explicit HGVS | **288** | 287 | 1 |
| `clinvarIds`, excluding the `NONE FOUND`/`N/A` sentinels | 209 | 208 | 1 |
| `maneSelectTranscript` | 362 | 362 | 0 |

The HGVS route works because the `NC_` accession *version* encodes the build, and ClinVar publishes
both — e.g. `R1275Q` carries `NC_000002.11:g.29432664C>T` (GRCh37) **and**
`NC_000002.12:g.29209798C>T` (GRCh38). Every record with any `NC_` accession in
`clinvarHgvsGenomic` has a GRCh38 one: 252 of 252.

**The number that decides the design:**

> Of the 376 variants with a GRCh37 coordinate, **318 carry at least one build-independent or
> GRCh38-explicit identifier** — 245 have both a GRCh38 HGVS and an rsID, 42 GRCh38-HGVS only, 31
> rsID only. **58 have a GRCh37 coordinate and nothing else.**

All 244 null-build variants carry none of these, but they have no coordinate to lift either — they are
protein- and transcript-level descriptions (72 frameshift/truncation, 71 protein+cDNA, 33
splice/intronic, 24 point substitutions, 20 structural/exon-level, 3 categorical). 243 of the 244 have
a coordinates object with **every field null**.

**So liftover is required for at most 58 variants, and is unnecessary for the rest.** RM48's rule —
*"if the paper gives an rs-number, liftover is unnecessary and strictly worse, because authoring the
rs-number produces the independent second value `resolution._verify` cross-examines"* — applies here
directly, and better than it does for a human author: CIViC **publishes** the rs-number, so not even
the recovery call is needed. Reading the identifier the source already carries is not liftover and not
recovery; it is the ordinary resolution chain.

That is also why an rsID route is clean where a recovered one would not be. A drafter writing an rsID
**CIViC published** is writing an independent value resolution can cross-examine. A drafter filling an
rsID *recovered from Ensembl at a GRCh37 position* would have resolution verify a value against the
service that produced it — the `hints.REDUNDANCY_BEARING` refusal, and the reason RM48 reports and
never fills.

### Internal consistency, and one malformed record

Two checks run without any external source:

- `coordinates.start`/`referenceBases`/`variantBases` against the GRCh37 `NC_` HGVS: **276 of 276
  comparable records agree on all three, zero mismatches.** `start` is the 1-based HGVS `g.` position,
  which is what this format's `start` means (`@start-1based`).
- `myVariantInfoId` against `coordinates`: **346 of 346 match chromosome and position exactly**, and
  it is GRCh37-positioned throughout.

Three raw tuples, so a reader can check them:

```
id=9    R1275Q  GRCH37 chr2  29432664 C>T  CA341482  rs113994087  → NC_000002.12:g.29209798C>T
id=113  M918T   GRCH37 chr10 43617416 T>C  CA009082  rs74799832   → NC_000010.11:g.43121968T>C
id=117  R248Q   GRCH37 chr17  7577538 C>T  CA000387  rs11540652   → NC_000017.11:g.7674220C>T
```

**One record is malformed and it is the shape a guard must catch.** CIViC id 1770 `N150fs (c.449del)`
has `referenceBuild=GRCH37` and `start=10188305` and `referenceBases=A`, but **null `chromosome` and
null `variantBases`**. It passes a build filter and has no usable position — a partially-populated
coordinate, which is exactly what `@identity-whole-or-none` exists for: a provider fills identity whole
or not at all. It is also why the comparable-record denominator above is 276 + 99 = 375 and not 376.

### Other fields worth knowing about

Full `GeneVariant` field list: `alleleRegistryId, clinicalSignificanceCounts, clinvarIds, comments,
coordinates, creationActivity, deprecated, deprecationActivity, deprecationReason,
detailedClinicalSignificanceCounts, events, feature, flagged, flags, hgvsDescriptions, id,
lastAcceptedRevisionEvent, lastCommentEvent, lastSubmittedRevisionEvent, link, maneSelectTranscript,
molecularProfiles, myVariantInfo, name, openCravatAnnotations, openCravatUrl, openRevisionCount,
revisions, singleVariantMolecularProfile, singleVariantMolecularProfileId, variantAliases,
variantTypes`.

`clinvarIds` is a **raw curator string list with sentinels in it** — `NONE FOUND` ×147 and `N/A` ×6 —
so its non-null count of 362 overstates real coverage by 153. A consumer reading it without filtering
the sentinels would treat "the curator checked and found none" as an id. `openCravatAnnotations` is
untyped `JSON`.

## The bulk releases, which are a different source from the API

CIViC publishes nightly **and dated** TSV releases — `civicdb.org/downloads/nightly/nightly-*.tsv` and
`civicdb.org/downloads/01-Aug-2026/01-Aug-2026-*.tsv` (probed: `01-Aug-2026` and `01-Jul-2026` both
200). A dated release is what a snapshot can pin, so it is the right build input; the API has no
dated release at all.

**The bulk file is `accepted`-only.** `ClinicalEvidenceSummaries` is 4,903 rows and every one has
`evidence_status = accepted` — against the API default's 11,518 `NON_REJECTED`. Two published surfaces
of one source, differing 2.35×, and neither declares its basis. That is the single most important
methodological fact in this survey: **a number from the TSV and a number from the API are not
comparable.**

On the bulk (accepted) basis, the direction corpus is:

| | Rows |
|---|---|
| Germline evidence rows | 813 |
| …of which `Predisposing` | 675 |
| **Direction-axis (`Predisposition` ∪ `Protectiveness`)** | **533** |
| `Predisposition` / `Supports` | 530 |
| `Predisposition` / `Does Not Support` | 2 |
| `Protectiveness` / `Supports` | 1 |

533 matches the API's `ACCEPTED` count for the same slice exactly, which cross-validates both probes.

**The join is clean.** `ClinicalEvidenceSummaries.molecular_profile_id` →
`VariantSummaries.single_variant_molecular_profile_id` joins **533 of 533** direction rows to **290
distinct variants**. Multi-variant profiles have no `single_variant_molecular_profile_id`, so they
drop out by construction — which is correct, since a combination profile is not a single-variant
identity.

### Identity in the bulk file is thinner than in the API, and this is what a builder gets

`VariantSummaries` carries `chromosome, start, stop, reference_bases, variant_bases,
representative_transcript, ensembl_version, reference_build, hgvs_descriptions, allele_registry_id,
clinvar_ids, variant_aliases`. It does **not** carry the API's `myVariantInfo` block, which is where
`dbsnpRsid` and `clinvarHgvsGenomic` live. So over the 290 joined variants:

| Route | Variants |
|---|---|
| GRCh38 `NC_` accession **present** in `hgvs_descriptions` | 40 |
| …of those, one `parse_grch38_substitution` can **read** | 12 |
| GRCh37-only accession | 181 |
| rsID in `variant_aliases` | 126 |
| ClinGen `allele_registry_id` (excluding the `unregistered` sentinel) | 235 |
| **Reachable — a readable GRCh38 substitution *or* an rsID** | **133** |
| neither | **157**, of which **102 carry a CAID** |

Measured with the shipped `parse_rsids` and `parse_grch38_substitution` rather than an ad-hoc regex.
On this release, 329 of the 533 evidence rows are reachable and **204 are not**.

**This table used to have two columns, and the reconciliation is worth more than the numbers were.**
It gave 159 reachable / 131 not for the *nightly* download against 133 / 157 for the dated
`01-Aug-2026` release, and read the gap as the nightly being later and better curated. Re-measured on
2026-09-01, that reading is wrong: the two files are **identical on this slice** — same 533 rows, same
290 variants, same 53 unreached, and not one identity cell different on any shared variant — and each
of them gives 133 under one definition of "reachable" and 159 under another. The 159 counts every
variant *carrying* a GRCh38 accession (40 of them); the 133 counts only those carrying one the
substitution parser can **read** (12). One file, two definitions, 26 variants of daylight.

That is `@existence-not-identity` in the shape a denominator can take — an accession that exists is
not an accession that resolves — and the 28 unreadable ones are not a parser defect: they are
deletions and insertions, and `NC_000003.12:g.10146622del` states no bases for a substitution parser
to hold. `has_unparsable_grch38` exists precisely to keep that class countable (49 rows) instead of
folding it into "the source said nothing".

**Scoring the accession requires the per-chromosome RefSeq map, not a version number.** `NC_000001.11`
is GRCh38 but `NC_000002.11` is GRCh37 — the version that means "GRCh38" differs per chromosome. A
first pass here tested `".11:g." or ".12:g."` and reported 208 reachable where the real figure is 40.
The map is a domain constant and belongs in the builder as one.

`reference_build` over the whole variant file: `GRCh37` 1,283 · empty 715 · `GRCh38` **1**.

**Consequence for a snapshot.** Build from the **dated TSV pair** — that is what makes a rebuild
byte-reproducible, and mixing in live API enrichment would forfeit exactly that. Carry
`allele_registry_id` as a snapshot column so the 157 unreachable variants stay addressable, and leave
CAID→GRCh38 resolution to a later pass, where RM48's *report-never-fill* rule governs it.

### The nightly, re-surveyed — what a month of curation actually added

**Probed 2026-09-01**, both files downloaded fresh and put through the shipped builder's own filter
chain. The question was how much a snapshot pinned to `01-Aug-2026` is missing by not reading the
nightly. The answer is nothing at all on the axis this source was adopted for:

| | `01-Aug-2026` | nightly (2026-09-01) |
|---|---:|---:|
| Evidence rows in the file | 4,878 | 4,903 |
| Variant records | 1,992 | 1,999 |
| Germline rows | 811 | 813 |
| **Direction-axis rows** | **533** | **533** |
| Joined to a single-variant profile | 533 / 290 variants | 533 / 290 variants |
| Kept by the builder | 474 / 237 variants | 474 / 237 variants |
| Dropped `unresolvable_identity` | 59 / 53 variants | 59 / 53 variants |
| Identity `rsid` / `both` / `grch38_hgvs` / `caid` | 310 / 17 / 7 / 140 | 310 / 17 / 7 / 140 |

**+25 evidence rows and +7 variants, and not one of them reaches this format.** The 25 new rows are 21
`Somatic`, 1 `Unknown`, 1 `N/A` and **2 germline** — and the two germline ones are `Gain of Function`
and `Sensitivity/Response`, neither on the direction axis. The 7 new variants are FGFR3, PTPRD, FGFR2,
GNAS and three with no gene named: somatic oncology, which is what CIViC mostly is.

Two further checks, because "the totals match" is a weaker claim than it looks:

- **The sets are identical, not merely the counts.** The 290 direction variants are the same 290 ids,
  and the 53 unreached are the same 53 ids — no variant swapped places with another.
- **No shared variant changed an identity cell.** All nine of `variant`, `variant_aliases`,
  `hgvs_descriptions`, `allele_registry_id`, `chromosome`, `start`, `reference_bases`,
  `variant_bases`, `reference_build` were compared across every variant present in both files:
  **zero differences**. So the curation that happened in this window added records; it did not
  back-fill an identifier onto an existing one.

`01-Sep-2026` does not exist yet — all three files 404 on 2026-09-01 — so the dated release a snapshot
can pin is still `01-Aug-2026`, and pinning it costs nothing measurable.

**What this does not say.** It is one month, on one axis, and the germline direction slice is 11% of
the file; a nightly read on the somatic majority would be a different measurement with a different
answer. It is also not a currency check — that asks the download index for a later *dated* release
(survey item 3), and this compares two files that both exist today.

## What was built from this, and what it looks like in practice

**CIViC was adopted on 2026-08-31 on the `direction` axis and nowhere else** (RM152), and the identity
residue was closed the same day (RM153) — `civic build`, `draft-panel --source civic`, `civic publish`,
`civic reproduce`, a ClinGen Allele Registry client, and two licence rows, with **no schema change of
any kind**. The operative surface is documented in the enricher reference and the authoring skill;
what belongs *here* is the numbers a reader should expect, so a run that disagrees is recognisable as
the source having moved rather than the tool having broken.

### Building the `01-Aug-2026` release

| | |
|---|---|
| Evidence rows read | 4,878 |
| Dropped `non_germline_origin` | 4,067 |
| Dropped `not_direction_axis` | 278 |
| Dropped `unresolvable_identity` | 59 |
| Dropped `combination_profile` / `no_variant_record` | 0 / 0 |
| **Kept** | **474 rows on 237 variants** |
| Identity: `rsid` / `both` / `grch38_hgvs` / `caid` | 310 / 17 / 7 / 140 |

**The zeros are measured, not structural**: 209 multi-variant profiles carrying 547 accepted rows
exist in this release and none is germline, so `combination_profile` would fire on a source that grew
one.

### Drafting it into an empty spec

| | Offline | With the registry |
|---|---:|---:|
| Variant rows | 115 | **201** |
| CAID → rs-number | 0 | 88 |
| CAID → GRCh38 coordinate | 0 | 13 |
| One-sided indels anchored | 0 | 39 |
| Withheld `caid_unresolved` | 140 | 0 |

Every drafted row carries a `DOID:` in `trait_efo_id`, and 474 kept rows collapse to 201 authored
variants because one variant carries several evidence items — the drafter reports the rest as
`already_present`, which is what makes a re-run a no-op.

### Reproducing and publishing it

```bash
# build + validate in one command; exits non-zero on any failure, so it is usable in CI
just-dna-enricher civic reproduce --release 01-Aug-2026

# or the two halves separately
just-dna-enricher civic build   --release 01-Aug-2026 --out ./civic
just-dna-enricher civic publish ./civic --dry-run      # then without --dry-run
```

`civic reproduce` runs five checks, and the third is the only one that needs a network for a reason
other than fetching:

1. **The release downloads and every file is hashed** — a sha256 per input, so a later disagreement is
   a finding about the source rather than a mystery.
2. **Two independent builds are byte-identical** (Principle 7). A parquet has no inherent row order,
   so this is what proves the sort is load-bearing.
3. **Every placed coordinate is cross-examined against the GRCh38 reference sequence** through
   refget/seqrepo. This is the external validation the rest of the pipeline cannot give itself: the
   positions come from RefSeq accessions inside ClinVar HGVS, and an unrelated service is asked
   whether the reference base at each is what we wrote. A wrong-build or off-by-one placement fails
   here and nowhere else. **Measured 2026-08-31: 24 of 24 read, 0 mismatches.**
4. **The drop registry closes** as an equality over a walked set — `4878 = 474 + 4404`.
5. **The publish plan is exactly** `data/civic.parquet` + `release.json` + `LICENSE.txt`.

`--offline` skips only the third and says so: a check that could not run is not a check that passed.

**What the published snapshot does and does not contain.** It carries the CIViC derivation, its
`release.json` (naming the dated release and the `accepted` status basis) and CIViC's own CC0 text. It
does **not** carry the ClinGen registry's answers — the CAID travels, the rs-number ClinGen returns
for it does not. Resolving at draft time is a read; baking those responses into a redistributed file
would be passing on bytes whose terms nobody has established.

## The 53 variants nothing reaches — opened, and 34 of them resolved

**Probed 2026-09-01.** After every published identifier and the registry, 53 variants (59 evidence
rows) carried no identifier of any kind. All 53 were then put through a four-tier identity procedure —
the ClinGen Allele Registry by an HGVS expression built from the variant's own name, NCBI E-utilities,
Ensembl's Variant Recoder, and the papers each evidence row cites. **Thirty-four resolve.**

| Class | Variants | Rows | Outcome |
|---|---:|---:|---|
| **Resolved from the name** — a `c.` or protein fragment the source published and never registered | **33** | **33** | rsID and/or CAID plus a GRCh38 coordinate, cross-checked on a second service |
| **Resolved already** — variant 1770, whose answer the record carried | **1** | **1** | CA020360 / rs794727253 |
| Liftover-only | 9 | 13 | closed 2026-08-31; ceiling 13 rows, honest recovery at most one |
| No allele identity exists — the name states a *class* of event | 6 | 8 | correctly dropped |
| Two readings, nothing to choose between them | 2 | 2 | withheld; needs a curator and a paywalled fulltext |
| Conjunction-named — two alterations in one record | 2 | 2 | all four alleles identified; the record is not one identity |

Per-variant tables, the queries behind each answer and the four wrong-name findings are in
[CIVIC_UNRESOLVED](CIVIC_UNRESOLVED.md), which holds the residue class by class.

**If the resolutions are adopted, coverage moves to 271/290 variants (93.4%) and 508/533 evidence
rows (95.3%)** — from 237/290 (81.7%) and 474/533 (88.9%). Adoption is a decision this document does
not take; nothing here has entered `civic build` or the published snapshot.

**What this round overturned in the previous one, and what the error cost.** The earlier pass
concluded that "the one remaining lever is worth 2 variants, not 31" and that the residue was "close
to a permanent floor rather than a backlog". Both are false. The mistake was one misread requirement:
it looked for a `representative_transcript` **on the record**, found it on 2 of the 31, and wrote off
the other 29 as having "nothing to build an unambiguous expression from". But the numbering frame a
`c.` fragment needs is a property of the **gene**, not of the record — for VHL it was established by
reading the 114 variants in this same corpus that CIViC *did* resolve, all of which publish both a
name and an `ENST00000256474.2:c.…` expression that agree; elsewhere from MANE Select, with CDKN2A
needing the exon table to choose p16 over p14ARF. A per-gene fact tested as a per-record one cost 39
variants, declared permanently unreachable.

What survives from that pass is the narrower claim, and it is still true: **five of the nine
coordinate-bearing variants can never be reached by any identity pass**, because the source states
their extent as unknown (`c.1-?_340+?del`) and the ClinGen registry refuses to parse such expressions
outright. An allele registry that cannot hold them is a stronger statement than a count.

### Four findings from this round that outweigh the count

- **Two CIViC names are wrong in a way nothing in a lookup can flag.** `TP53 R72P` (4968) has
  reference and alternate inverted — codon 72 is `CCC` = Pro on GRCh38, so the identity is the
  reference-identity allele CA178298 (`c.215C=`, rs1042522). `CHEK2 IVS2+1G>A` (788) converts
  structurally to `c.319+1`, but the true answer is `c.444+1`, because legacy papers number CHEK2
  exons from the first *coding* exon; both readings are real registered alleles 9 kb apart. Two more
  names are internally inconsistent: `VHL L178P (c.532C>T)` (2459) pairs a missense protein name with
  a *synonymous* cDNA change, and `RUNX1 R135FSX177` (804) names a protein consequence where the
  allele is an intronic splice-donor deletion.
- **Three unresolved records duplicate CIViC's own resolved entries** — 3743≡1770 (CA020360),
  2459→1748 (rs5030822), and half of 4210→1739 (rs5030821). The identity was in CIViC's table one row
  over. The first has a downstream consequence: an identity pass that reaches both maps **two variant
  ids onto one allele**, which touches camp grouping and the drafter's `already_present` path.
- **The premise that a name-only record is a famous allele with a forgotten rs-number is false.** Of
  the 20 VHL indels resolved, only 9 carry an rs-number at all and 9 of the CAIDs carry no external
  record of any kind. The *identity* exists; the *fame* does not.
- **A transcript-version story that this survey's companion helped set is wrong.** `NM_000551.3` and
  `NM_000551.4` have byte-identical CDS, and submitting either returns the same CAID; the
  `c.197_220del` → `c.198_221del` shift is HGVS 3′-rule renormalization inside a repeat, not a version
  effect. Believing the version story invites correcting a whole gene's positions by one *and*
  teaches a reader to wave through a genuine one-base mismatch.

## What could be done next, each with the number that sizes it

Sized here, decided elsewhere. Nothing below is a plan — `docs/probes/` is evidence.

**Already taken, and listed so a reader does not re-propose them.** The two largest items this section
originally carried have shipped: the **ClinGen CAID pass** (RM153 — 64 variants, taking recovery from
48% to 70%) and **publishing a snapshot** (`civic publish`, CC0, nothing legal in the way). The CAID
pass then grew a third leg nobody had sized — **anchoring one-sided indels** — which recovered all 35
remaining registry rows and took recovery to **237/290 = 82%**.

**Still open, with a real trade-off to decide first:**

1. **Read the API for what the download does not carry — identity, and HPO ids.** Two things behind
   one trade-off. `myVariantInfo` holds `dbsnpRsid` and ClinVar's GRCh38 HGVS, which lifts reach over
   the API's own view from 133-of-290 to 318-of-376. And **`phenotypes` carries real `HP:` CURIEs**
   (`HP:0003621`) where the bulk file gives only labels (`Hemangioblastoma`) — 385 of the 533
   direction rows have a phenotypes cell and none of them is an id. Since `trait_efo_id` is a
   multi-valued ontology-CURIE column, an HPO id would sit *beside* the `DOID:` rather than replacing
   it. But mixing a live API into a build forfeits byte-reproducibility, so this belongs as an
   `enrich`-time pass beside the CAID one, never inside `civic build`.
2. **Decide what a conjunction-named variant is — the instrument exists, the drafter does not use
   it.** CIViC encodes combination genotypes two ways and only one decomposes: 6 profile-level
   `" AND "` profiles (dropped by count, correctly) and **24 variants carrying a conjunction inside
   their own `name`** (`rs1801270 and rs1059234`). Nothing in the builder looks at a variant's name,
   so nothing drops or splits them; the two in this release are removed by the identity filter, which
   is harmless **by accident** — and the CAID pass is exactly what would let them through.

   What the 2026-09-01 round settled is that this needs **no schema change**. A two-alteration record
   is a haplotype plus a diplotype, which is what `haplotypes.csv` and `diplotypes.csv` have been
   since 0.4 and what [`hfe_compound_het`](../../reference_examples/hfe_compound_het/) demonstrates.
   Record 3298 (`VHL P81S and L188V`) was authored that way and compiled: it validates, compiles in
   both modes to the same digest, and round-trips with `content_signature` intact. Its two alleles are
   rs104893829 and rs5030824, both fully identified. **Size today: one authorable record** — the other
   conjunction record, 4210, fails on provenance rather than on identity, because ClinVar attributes
   only its missense half to the paper CIViC cites. Full working in
   [CIVIC_UNRESOLVED § class E](CIVIC_UNRESOLVED.md).

   The one thing an author must state rather than derive is **phase**. The paper behind 3298 reports
   co-segregation through six family members and never uses the word *cis*; cis follows from the
   co-segregation, and that inference belongs in the row's `conclusion` where a reader can see it, not
   silently in the choice of haplotype.
3. **A currency check.** Dated releases appear monthly and are immutable, so "is this snapshot stale?"
   is answerable by asking the download index for a later date, against the source rather than the
   cache. `release.json` already records `dataset` and a sha256 per input file.
4. **Read `SUBMITTED` items.** The bulk file is `accepted`-only, so today's snapshot is the reviewed
   subset by construction. Including submitted items roughly doubles the corpus, requires the API
   rather than the download, and changes every number in this document — including taking the
   contested-variant count from 0 to 3. If ever done, `status` belongs on the row as `confidence` with
   `confidence_unit`, unconverted.

**Deliberately not worth doing, each closed on a measurement rather than an opinion:**

5. **A `direction`-axis concordance record.** Genuine `risk`-vs-`protective` opposition is **0** at
   every scope and status basis, and nothing else in the enricher fills `direction` at all — a
   concordance record needs two authorities and this axis has one. What would reopen it is a *second*
   direction-bearing source appearing, not more CIViC.
6. **CIViC as a `clin_sig` authority.** Five germline ACMG-tier calls, zero benign-class. Dead on
   arithmetic, and no growth in the somatic majority changes it.
7. **Mining `assertions` for direction evidence.** Structurally impossible, not merely thin:
   `AssertionSignificance` has no `PREDISPOSITION` or `PROTECTIVENESS` member, so the query is a type
   error. This cannot change without CIViC altering its schema.
8. **Lifting the GRCh37 coordinates over.** Refused and sized: 13 evidence rows on 9 variants, honest
   recovery **at most one**, and the one precise event in the class lifts *exactly* to the wrong
   allele. Full working in [CIVIC_UNRESOLVED](CIVIC_UNRESOLVED.md).

**One thing to check before trusting anything above.** Every count here is over one dated release, and
the source is actively curated, so re-derive rather than quote if a decision turns on a margin. What
that caution used to say — that the nightly already disagreed with `01-Aug-2026` on reach, 159 against
133 — was itself the artefact described above, and the re-survey below is what replaced it.


## What this survey concludes, and what it deliberately does not

**It concludes nothing.** `docs/probes/` is evidence. The readings the measurements support are
recorded in [ROADMAP_HISTORY.md](../ROADMAP_HISTORY.md) — RM152 for the adoption, RM153 for the
identity residue — and in the 0.7 proposal addendum; if a future reader finds those and this document
disagreeing, those win and this one is the thing that went stale.

What is worth carrying forward in one place:

- CIViC is a **somatic** resource. The germline quarter is real but small, and its clinical-significance
  half is 5 usable calls with **zero** benign-class — the concordance route is dead on arithmetic.
- Its germline mass sits on the **`direction`** axis, 1,458 rows, every one carrying a stated direction.
- Genuine `risk`-vs-`protective` opposition is **0**, at every scope probed, under every status basis.
- The identity obstacle was real, is now mostly closed, and **its size always depends on which surface
  you read** — always name the file. Over the dated bulk release a snapshot must build from, recovery
  went **138 → 202 → 237 of 290 variants (48% → 70% → 82%)**: the builder's own reading of published
  identifiers, then the ClinGen CAID pass, then anchoring one-sided indels. The API's own view is
  wider still (318 of 376 coordinate-bearing) because `dbsnpRsid` and `clinvarHgvsGenomic` are
  MyVariant.info enrichment the download does not carry — but reading it would cost the snapshot its
  reproducibility.
- **Nothing is lifted over, and nothing needs to be.** Coordinates are GRCh37 or absent, never GRCh38;
  every placed row is placed by an identifier the source itself publishes, and 24 of 24 of those
  placements were confirmed against the GRCh38 reference sequence by an unrelated service. The
  liftover-only residue is 9 variants and its honest recovery is at most one.
- **The 53 that carried no identifier were opened on 2026-09-01, and 34 of them resolve** — from the
  `c.` and protein fragments CIViC publishes in the variant's own `name`, against a numbering frame
  established per *gene* rather than per record. That takes coverage to 271/290 variants and 508/533
  rows if adopted. The earlier reading of this residue as "close to a permanent floor" was wrong, and
  wrong for one reason: a per-gene fact was tested as a per-record one. What survives is narrower and
  still true — 5 of the 9 coordinate-bearing ones state their own extent as unknown, which the allele
  registry refuses to parse, and 6 more name a class of event rather than an allele.
- **The round found four wrong names, three self-duplicates and one falsified trap** — `TP53 R72P`
  has ref and alt inverted; `CHEK2 IVS2+1G>A` converts to the wrong exon; two records pair a protein
  name with an allele of another kind; three unresolved records duplicate CIViC's own resolved ones;
  and the "`NM_000551.4` shifts CDS numbering" story is 3′-rule renormalization, not a version effect.
  Each of these would have survived a lookup that only asked whether an expression resolves.
- The **status default is `NON_REJECTED`** and most of CIViC is `SUBMITTED`. State the basis or the
  numbers mean nothing.
- **Disease ids are free and complete**: 533 of 533 direction rows carry a DOID, and `trait_efo_id`
  takes any ontology CURIE, so `DOID:1612` belongs in the column rather than in prose. HPO ids are
  **API-only** — the download serves phenotype *labels*, and a label is not an id.
