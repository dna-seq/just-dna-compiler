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

| Route | Variants (nightly) | Variants (`01-Aug-2026`) |
|---|---|---|
| GRCh38 `NC_` accession in `hgvs_descriptions` | 40 | — |
| GRCh37-only accession | 181 | — |
| rsID in `variant_aliases` | 126 | — |
| ClinGen `allele_registry_id` (excluding the `unregistered` sentinel) | 235 | — |
| **Reachable — a GRCh38 accession *or* an rsID** | **159** | **133** |
| neither | 131 | **157**, of which **102 carry a CAID** |

**Name the file, not just the surface.** The left column is the *nightly* download and the right is the
dated `01-Aug-2026` release the builder actually reads, measured with the shipped `parse_rsids` and
`parse_grch38_substitution` rather than an ad-hoc regex. They differ because the nightly is later and
better curated, not because either is wrong — but **the dated figures are the ones a reader should
compare a built snapshot against**, since that is what `civic build --release` consumes. On the dated
release, 329 of the 533 evidence rows are reachable and **204 are not**.

**Scoring the accession requires the per-chromosome RefSeq map, not a version number.** `NC_000001.11`
is GRCh38 but `NC_000002.11` is GRCh37 — the version that means "GRCh38" differs per chromosome. A
first pass here tested `".11:g." or ".12:g."` and reported 208 reachable where the real figure is 40.
The map is a domain constant and belongs in the builder as one.

`reference_build` over the whole variant file: `GRCh37` 1,283 · empty 715 · `GRCh38` **1**.

**Consequence for a snapshot.** Build from the **dated TSV pair** — that is what makes a rebuild
byte-reproducible, and mixing in live API enrichment would forfeit exactly that. Carry
`allele_registry_id` as a snapshot column so the 131 unreachable variants stay addressable, and leave
CAID→GRCh38 resolution to a later pass, where RM48's *report-never-fill* rule governs it.

## What was built from this, and what it looks like in practice

**CIViC was adopted on 2026-08-31, on the `direction` axis and nowhere else** — `civic build`,
`draft-panel --source civic`, and a `CIVIC_TERMS` licence row, with **no schema change of any kind**.
The operative surface is documented in the enricher reference and the authoring skill; what belongs
*here* is only the numbers a reader should expect to see, so a run that disagrees with them is
recognisable as a change in the source rather than a bug in the tool.

Building the `01-Aug-2026` release and drafting the whole thing into an empty spec:

| | |
|---|---|
| Evidence rows read | 4,878 |
| Dropped `non_germline_origin` | 4,067 |
| Dropped `not_direction_axis` | 278 |
| Dropped `unresolvable_identity` | 204 |
| Dropped `combination_profile` / `no_variant_record` | 0 / 0 |
| **Kept** | **329 rows on 133 variants** |
| Identity: `rsid` / `both` / `grch38_hgvs` | 305 / 17 / 7 |
| Drafted into an empty spec | **110** variant rows, **311** study rows |
| …of those, carrying a `DOID:` in `trait_efo_id` | **110 / 311** — every one |

Two of those are worth reading rather than skimming. **The zeros are measured, not structural** — 209
multi-variant profiles carrying 547 accepted rows exist in this release, and none of them is germline,
so `combination_profile` would fire on a source that grew one. And **329 rows collapse to 110 authored
variants**, because one variant carries several evidence items; the drafter reports the rest as
`already_present` rather than appending them, which is what makes a re-run a no-op.

## What could be done next, each with the number that sizes it

Sized here, decided elsewhere. Nothing below is a plan — `docs/probes/` is evidence — but every one of
these has been asked, or will be, and the measurement is what stops it being re-argued from scratch.

**Worth doing, in rough order of value per unit of work:**

1. **Resolve a ClinGen `allele_registry_id` to a GRCh38 locus.** The largest single recovery available:
   **102 of the 157 unreachable variants carry a CAID**, and a CAID is build-independent by
   construction, so this converts most of the `unresolvable_identity` drop into drafted rows *without
   lifting a coordinate*. It also produces the independent second value resolution cross-examines,
   which is the property that makes an rsID acceptable and a lifted coordinate not. Costs: a source
   the enricher does not currently fetch (terms, cache, a place in the chain), and a decision about
   whether it belongs at `enrich` time — almost certainly yes, since doing it in the builder would
   forfeit the offline reproducibility that is the whole reason the builder reads a dated file. Tracked
   as RM153.
2. **Publish a snapshot.** CC0 permits redistribution outright, and **no CIViC snapshot has been
   published** — every deployment currently builds its own. This is the one source here where nothing
   legal stands in the way; what is missing is only a repo and the decision to own the cadence. Note
   the standing rules that a published snapshot accumulates and that a publisher's allowlist is derived
   from the artifact's own file list.
3. **A currency check.** Dated releases appear monthly and are immutable, so "is this snapshot stale?"
   is answerable by asking the download index for a later date — cheaply, and against the source rather
   than against the cache it was built from. `release.json` already records `dataset`,
   `evidence_sha256`, `variant_sha256` and `profile_sha256`, which is everything such a check needs.

**Possible, with a real trade-off to decide first:**

4. **Read the API for what the download does not carry — identity, and HPO ids.** Two things sit
   behind the same trade-off. `myVariantInfo` holds `dbsnpRsid` and ClinVar's GRCh38 HGVS, which lifts
   reach from 133-of-290 to 318-of-376 over the API's view. And **`phenotypes` carries real `HP:`
   CURIEs** (`HP:0003621`) where the bulk file gives only labels (`Hemangioblastoma`) — 385 of the 533
   direction rows have a phenotypes cell, and none of them is an id. Since `trait_efo_id` is a
   multi-valued ontology-CURIE column, an HPO id would sit beside the disease id rather than replacing
   it. But mixing a live API into a build forfeits byte-reproducibility — the property a snapshot
   exists to have — so this belongs as an `enrich`-time pass beside the CAID one, never inside
   `civic build`.
5. **Decide what a conjunction-named variant is, before item 1 makes it urgent.** CIViC encodes
   combination genotypes two ways. The profile-level `" AND "` kind is detected and dropped by count,
   correctly. The other kind is a **single variant id whose own `name` names two to four alterations**
   (`rs1801270 and rs1059234`, `Deletion AND I151S(c.452T>G)`) — 24 of them across the API's 620-variant
   view, and **nothing in the builder looks at a variant's name**, so nothing would drop or split them.

   Measured on the dated release, the class is currently harmless **by accident**: exactly 2 germline
   direction rows carry a conjunction-named variant, and **both are dropped as
   `unresolvable_identity`**, because a compound name carries no single rsID and no single GRCh38
   substitution. That is the identity filter doing it, not any awareness of conjunction — so **item 1
   is precisely what would let them through**, since resolving a CAID is exactly the step that supplies
   the identity they currently lack. A CAID pass should decide this first, or it will quietly begin
   minting one variant identity for what the source describes as several alterations.
6. **Read `SUBMITTED` items.** The bulk file is `accepted`-only, so today's snapshot is the reviewed
   subset by construction. Including submitted items would roughly double the corpus and would require
   the API rather than the download — and it changes every number in this document, including taking
   the contested-variant count from 0 to 3. If it is ever done, `status` belongs on the row as
   `confidence` with `confidence_unit`, unconverted, never folded into anything.

**Deliberately not worth doing, and each is closed on a measurement rather than an opinion:**

7. **A `direction`-axis concordance record.** Genuine `risk`-vs-`protective` opposition is **0** at
   every scope and status basis, and nothing else in the enricher fills `direction` at all — a
   concordance record needs two authorities and this axis has one. What would reopen it is a *second*
   direction-bearing source appearing, not more CIViC.
8. **CIViC as a `clin_sig` authority.** Five germline ACMG-tier calls, zero benign-class. Dead on
   arithmetic, and no amount of growth in the somatic majority changes it.
9. **Mining the `assertions` table for direction evidence.** Structurally impossible, not merely thin:
   `AssertionSignificance` has no `PREDISPOSITION` or `PROTECTIVENESS` member, so the query is a type
   error. This one cannot change without CIViC altering its schema.
10. **Lifting the GRCh37 coordinates over.** Refused, and now sized rather than argued: after every
    published identifier is tried the remainder is 157 variants, 102 of which a CAID would place
    instead. A lifted coordinate would still be the row's sole identity with nothing to check it
    against.

**One thing to check before trusting anything above.** Every count here is over one dated release. The
source is actively curated — the nightly file already disagrees with `01-Aug-2026` on reach (159
reachable variants against 133) — so re-derive rather than quote if a decision turns on a margin.

## What this survey concludes, and what it deliberately does not

**It concludes nothing.** `docs/probes/` is evidence. The readings the measurements support are
recorded in [ROADMAP_HISTORY.md § RM152](../ROADMAP_HISTORY.md) and in the 0.7 proposal addendum; if a future reader
finds those and this document disagreeing, those win and this one is the thing that went stale.

What is worth carrying forward in one place:

- CIViC is a **somatic** resource. The germline quarter is real but small, and its clinical-significance
  half is 5 usable calls with **zero** benign-class — the concordance route is dead on arithmetic.
- Its germline mass sits on the **`direction`** axis, 1,458 rows, every one carrying a stated direction.
- Genuine `risk`-vs-`protective` opposition is **0**, at every scope probed, under every status basis.
- The identity obstacle is real and **its size depends on which surface you read**. Over the API's 620
  variants, 318 of the 376 coordinate-bearing ones carry a build-independent or GRCh38-explicit
  identifier and only 58 would need anything lifted. Over the **dated bulk file a snapshot must build
  from**, it is 159 of 290 — because the API's rsID and GRCh38-HGVS columns are MyVariant.info
  enrichment that the bulk file does not carry.
- The **status default is `NON_REJECTED`** and most of CIViC is `SUBMITTED`. State the basis or the
  numbers mean nothing.
- **Disease ids are free and complete**: 533 of 533 direction rows carry a DOID, and `trait_efo_id`
  takes any ontology CURIE, so `DOID:1612` belongs in the column rather than in prose. HPO ids are
  **API-only** — the download serves phenotype *labels*, and a label is not an id.
