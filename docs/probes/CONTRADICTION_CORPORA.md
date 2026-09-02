# A source that asserts and refutes: the two corpora measured

**Subjects:** CIViC (the two-row shape) and STRchive (the one-field shape), the two corpora
`docs/ROADMAP.md` § RM170 names.
**CIViC basis:** the `01-Aug-2026` dated bulk release (three TSVs + `civic_accepted_and_submitted.vcf`),
plus the live GraphQL API read on 2026-09-01.
**STRchive basis:** `dashnowlab/STRchive` `data/STRchive-loci.json` at `main`, sha256
`306618801d03bb48eb69a206a9ea3d83dbbcc1317f7673a6f694c7de0b227794`, byte-identical to tag `v2.26.0`.
**Date of analysis:** 2026-09-01

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`. Nothing
here proposes a design. Every number below was re-derived; where a figure disagrees with the roadmap
entry, the entry is quoted and the disagreement is stated rather than smoothed.

---

## 0. Summary

| | CIViC | STRchive |
|---|---|---|
| where the contradiction lives | two evidence rows on one variant | one field, `evidence`, on one locus |
| subjects carrying it | **3 variants** (2161, 2428, 2533 — all VHL) | **4 loci** (3 `Disputed`, 1 `Refuted`) |
| refutation-only subjects (a rebuttal with no claim beside it) | **2 variants** (CHEK2 788, TP53 4968) | not applicable — the field is a grade, not a second row |
| basis-dependent? | **yes, totally.** 0 on `accepted`; 3 on `accepted+submitted`; 3 on `ALL` | **no.** One published file, one value per locus |
| does the built artifact keep it? | yes, `direction` null + raw words in two columns | **no.** `StrchiveLocus` never parses `evidence` |
| does an author hear about it? | drafting: an aggregate count, no variant named. Hand-authoring: nothing | **nothing, on either path** |
| corpus modules affected today | 0 (no reference example authors VHL or CHEK2) | 0 (no reference example uses DMD / NIPA1 / DIP2B / POLG) |

**The single most load-bearing measurement:** every CIViC refutation that stands against a claim is
`SUBMITTED`. Both `ACCEPTED` refutations in the whole database stand against nothing. So the class
RM170 is about does not exist on the basis the builder read before RM169, and exists entirely on the
strength of unreviewed content.

---

## 1. CIViC — the two-row shape

### 1.1 Provenance of the inputs

The dated files used here are the exact bytes behind the shipped snapshot:

```bash
sha256sum 01-Aug-2026-ClinicalEvidenceSummaries.tsv \
          01-Aug-2026-MolecularProfileSummaries.tsv \
          01-Aug-2026-VariantSummaries.tsv
# e199494202de177145c17527bb3e84b488382c8a47b501e91fa971b38038aa98  evidence
# 72332619da175be97b5f2f02573169ccab214bb1688b5d3fb582a12944a0e9a3  profiles
# 6b09215639ed80f1f0617c887e4f48ac727bbea237ee83f1ac85de2cfa3b9db2  variants
python3 -c "import json;r=json.load(open('data/repro/civic/build-a/release.json'));print({k:v for k,v in r.items() if 'sha' in k})"
```

All three match `data/repro/civic/build-a/release.json`. That build is `status_basis:
"accepted+submitted"`, 1,149 rows on 397 variants; `build-b` is the same basis and the same numbers,
which is RM169's byte-identical-rebuild claim holding.

### 1.2 The refutation set, re-derived on three bases

**Base 1 — the accepted bulk TSV, whole file.** 4,878 evidence rows, `evidence_status` `accepted` on
every one. `evidence_direction` is `Supports` 4,343 / `Does Not Support` **518** / `N/A` 17.

Those 518 are overwhelmingly somatic therapy claims, and **only 2 sit on this format's direction
axis**:

| `(evidence_type, significance)` | DNS rows |
|---|---:|
| Predictive / Resistance | 218 |
| Predictive / Sensitivity-Response | 166 |
| Functional / Dominant Negative | 40 |
| Prognostic / N/A | 34 |
| Prognostic / Poor Outcome | 30 |
| Oncogenic / Oncogenicity | 10 |
| Diagnostic / Positive | 7 |
| Prognostic / Better Outcome | 5 |
| Functional / Neomorphic | 5 |
| **Predisposing / Predisposition** | **2** |
| Functional / Loss of Function | 1 |

**Base 2 — the `accepted_and_submitted` VCF**, the file the builder joins behind `--submitted`. 1,333
VCF records, 5,864 CSQ entries, of which 5,772 are `evidence` and 92 `assertion`. Evidence status is
2,322 accepted / 3,450 submitted; direction is 4,822 `SUPPORTS` / 603 `NA` / **347
`DOES_NOT_SUPPORT`**. Of those 347, **3** are `PREDISPOSITION` + a germline origin.

**Base 3 — the live GraphQL API, `status: ALL`** (which includes `REJECTED`):

```graphql
evidenceItems(significance: PREDISPOSITION, evidenceDirection: DOES_NOT_SUPPORT, status: ALL, first: 50)
```

`totalCount` = **4**. `PROTECTIVENESS` + `DOES_NOT_SUPPORT` = **0**. So the whole database, rejected
content included, holds exactly four refutations on the direction axis, and they are the same four the
two dated files between them carry. Nothing hides behind the API that the dated pair cannot reach, on
this axis. (`PREDISPOSITION` + `SUPPORTS` on `ALL` is 1,516: 946 submitted, 534 accepted, 36 rejected —
consistent with RM160's `NON_REJECTED` figure of 1,480.)

### 1.3 The four refutations, and what stands beside each

Read from the API (`evidenceItem(id:)`) and cross-checked against the built parquet:

| EID | status | variant(s) | molecular profile | claims on the same variant |
|---|---|---|---|---|
| 1302 | **ACCEPTED** | 4968 `TP53 R72P` | 5146, single-variant | **none** |
| 1854 | **ACCEPTED** | 788 `CHEK2 IVS2+1G>A` | 769, single-variant | **none** |
| 10949 | submitted | 2428 `VHL G104V (c.311G>T)` | 2301, single-variant | 1 — EID 7134, **accepted** |
| 8721 | submitted | 2161 **and** 2533 | **5278, a combination profile** | 2161: EIDs 5797 + 10733, both submitted · 2533: EID 10770, submitted |

So the assert-and-refute set is `{2161, 2428, 2533}` and the refutation-only set is `{788, 4968}`.

### 1.4 Three corrections to the roadmap entry's table

The entry's per-variant table is right about the variants and wrong about three things.

1. **"only 2428 has a refutation an editor signed off" is inverted.** 2428's *claim* (7134) is
   accepted; its refutation (10949) is `SUBMITTED`. **No refutation anywhere in CIViC that stands
   against a claim is accepted.** The two accepted refutations are CHEK2 788 and TP53 4968, and
   neither has a claim beside it.
2. **2161 and 2533 do not carry two refutations, and the entry's table does not say they do — it
   writes `ev 8721` on both rows.** What is not stated there is *why*: EID 8721 belongs to molecular
   profile 5278, which CIViC publishes as `VHL S183L (c.548C>T) AND VHL D126N (c.376G>A)` with
   `variants` `[2161, 2533]`. It is one statement about a two-variant genotype, and it *reads* in the
   parquet as two single-variant rebuttals (§2.2). So the "three known instances" are one
   single-variant pair (2428) and one combination-profile item counted twice.
3. **A fourth refuted variant sits just outside the entry's class, and it is the informative one.**
   CHEK2 788 is in the shipped parquet with an `accepted` `Does Not Support` row and no claim beside
   it, so it is not an assert-and-refute variant. Taken with TP53 4968 (§1.4 below) it makes the
   sharper statement: **both accepted refutations in the whole database are refutation-only**, so the
   set of pairs the basis question cannot touch is empty.

TP53 4968 is a fifth refuted variant that **never enters the snapshot**: its
`VariantSummaries.tsv` row carries no chromosome, no start, no HGVS, no CAID and no aliases, so it is
dropped `unresolvable_identity`, and it has no GRCh37 position so it is absent from the VCF too. One
of the two accepted refutations in the database is therefore invisible to every consumer of this
artifact.

### 1.5 Genuine opposition remains 0, on every basis

`contested_variants` counts a variant whose kept rows put it in **both** the `risk` and the
`protective` camp. Measured over the live API on `status: ALL`, `PROTECTIVENESS`+`SUPPORTS` is two
items on two variants — 4980 `rs143348853` (submitted) and 258 `MTHFR A222V` (accepted) — and
**neither carries a `PREDISPOSITION`+`SUPPORTS` item**. The intersection is empty. So
`contested_variants: 0` in the release record is correct on the accepted basis, the wider basis, and
`ALL`, and the entry's account of `CIVIC_DIRECTION_MAP` mapping `Does Not Support` to `None` is
confirmed exactly as written.

---

## 2. What the built parquet carries, and what a consumer sees

### 2.1 The rows

```bash
uv run python -c "
import polars as pl
df = pl.read_parquet('data/repro/civic/build-a/data/civic.parquet')
print(df.filter(pl.col('evidence_direction_raw')=='Does Not Support'))"
```

Four rows, on variants 788 / 2161 / 2428 / 2533. Every one of them:

* `direction` = **null** — the withhold, working as designed;
* `significance_raw` = `Predisposition`, `evidence_direction_raw` = `Does Not Support` — the raw words
  kept, which is the only place the rebuttal is legible;
* `evidence_status` = `accepted` for 788, `submitted` for the other three.

**The column that distinguishes the rebuttal from the claim is `evidence_direction_raw`, and nothing
else.** There is no boolean, no code, no reason column. A null `direction` does today mean exactly
`Does Not Support`, because `CIVIC_DIRECTION_MAP` has no other `None`-valued key and every off-axis
pair is dropped before it reaches a row — but that is an invariant of the map, not something the row
states about itself, and it would stop holding the moment a fifth key is added.

### 2.2 The one anomaly the fan-out creates

`_submitted_evidence_row` (civic_build.py:825) sets `molecular_profile_id` from **the variant's**
`single_variant_molecular_profile_id`, not from the evidence item's own profile. So EID 8721 is
written as two rows stamped MP 2037 and MP 2406, when the item's actual profile is 5278. The parquet
therefore states, twice, that a combination-genotype refutation is a single-variant refutation, and
the column that would say otherwise has been overwritten.

The class is small and measurable. In the parquet, 1,149 rows carry 1,144 distinct `evidence_id`s;
the five that repeat are 5634, 6740, 6868, 8721, 8790 — all VHL, all submitted, four of them
`Supports`. Over the whole VCF the fan-out is wider (108 evidence ids under more than one VCF record,
279 CSQ entries), but only 5 of them survive the germline + direction-axis filter.

Note the asymmetry with the TSV path, which drops a multi-variant profile as `combination_profile`
(0 such drops in this release). A combination-profile evidence item reaching the builder through the
VCF is fanned out and kept; one reaching it through the TSV is counted and dropped.

### 2.3 What an author is actually told

**Drafting.** `civic_draft` already has a withheld class for this — `refutation_states_no_direction`
— and emits one aggregate line:

> `N CIViC row(s) refute a predisposition claim rather than making one, so they state no direction and
> none was drafted. Refuting a risk claim does not establish that a variant is protective, and this
> provider will not write the opposite of what the source said.`

It names no variant. The neighbouring `contested_variant` line does name its subjects, through
`examples(contested)`; the refutation line has no equivalent.

**Hand-authoring.** Nothing. There is no `VALID_VERIFICATION_CHECKS` member that reads the snapshot's
refutation rows against an authored table, so a module that writes a `risk` row on VHL S183L passes
every gate silently. That is the gap the entry describes, and it is confirmed.

### 2.4 Incidental: the release record contradicts itself

`_write_release_json` builds `notice` from an unconditional literal (civic_build.py:1017). The shipped
`data/repro/civic/build-a/release.json` therefore says

> "It is built from the dated bulk TSV release, **every row of which is status 'accepted'**"

in the same file that records `"status_basis": "accepted+submitted"` and `"status_counts": {"accepted":
507, "submitted": 642}`. Not an RM170 matter; recorded because the notice is the string a redistributor
reads and it is now false on the default basis.

---

## 3. STRchive — the one-field shape

### 3.1 The real published file

```bash
curl -sSL -o STRchive-loci.json \
  https://raw.githubusercontent.com/dashnowlab/STRchive/main/data/STRchive-loci.json
sha256sum STRchive-loci.json
# 306618801d03bb48eb69a206a9ea3d83dbbcc1317f7673a6f694c7de0b227794
```

`main` is byte-identical to tag `v2.26.0` (published 2026-08-24), so every count below is pinnable.
82 loci. `evidence` is present and non-empty on all 82, and **every locus carries exactly one value**
— the list lengths are `{1: 82}`, so per-member counts and per-locus counts are the same number here
and will not be if that ever changes.

### 3.2 The vocabulary, re-derived

| value | loci | nearest house `VALID_GENE_VALIDITY` member |
|---|---:|---|
| Definitive | 46 | `definitive` |
| Limited | 14 | `limited` |
| Moderate | 8 | `moderate` |
| **Provisional** | **6** | **none** |
| Strong | 4 | `strong` |
| **Disputed** | **3** | `disputed` |
| **Refuted** | **1** | `refuted` |

Sum 82. The entry's figures reproduce exactly.

### 3.3 The vocabulary is published and documented, but it is **not closed**

`data/STRchive-loci.schema.json` describes the field:

> **Level of Evidence** — "Categorical level of evidence for the association between the locus and
> disease based on **criTRia or similar curation framework**. An association that has not yet been
> curated because it is recently published or limited data is available should be marked as
> Provisional."

The field is `required`, its `type` is `array`, and its items carry **`examples`** plus
`"combobox": true` — **not `enum`**. So the eight suggested strings (`Definitive`, `Strong`,
`Moderate`, `Limited`, `Disputed`, `Refuted`, `No Known Relationship`, `Provisional`) are a
suggestion list a curator may type past, and the schema admits any string and any number of them.
Seven of the eight are used; `No Known Relationship` is used by zero loci.

Two consequences worth measuring rather than assuming:

* `Provisional` (6 loci) is **not** a ClinGen classification and has no member in this repo's
  `VALID_GENE_VALIDITY`. Calling the field "ClinGen-style" is right about six of its seven observed
  members and wrong about the seventh, which by the schema's own text means *not yet curated* — a
  nobody-asked, not a grade.
* The unused suggestion `No Known Relationship` would **also** miss:
  `gene_validity.CLASSIFICATION_BY_WORDING` keys on `no known disease relationship` and
  `no reported evidence`, neither of which is STRchive's wording.

### 3.4 A `Disputed` or `Refuted` locus is otherwise indistinguishable

| | `evidence` | pathogenic band | benign band | intermediate band | `locus_structure` | `details` says "conflicting" |
|---|---|---|---|---|---|---|
| `HD_HTT` | Definitive | 36–250 | 6–26 | 27–35 | 3 elements | no |
| `FXS_FMR1` | Definitive | 201–2000 | 5–44 | 45–200 | [] | no |
| `FRA12A_DIP2B` | **Disputed** | 273–306 | 6–23 | 139–206 | [] | **no** |
| `ALS1_NIPA1` | **Disputed** | 11–56 | 6–10 | — | [] | yes |
| `CPEO_POLG` | **Disputed** | — | 10–10 | — | 3 elements | yes |
| `DMD_DMD` | **Refuted** | 59–82 | 16–33 | — | 2 elements | yes |

Three of the four state a full pathogenic band, structurally identical to a Definitive locus's. The
last column is the **whole** `details` string matched against
`conflict|disput|refut|controvers|not (been )?(replicat|confirm)`, not a truncation: three of the four
say so in prose and `FRA12A_DIP2B` says nothing at all, while neither Definitive locus matches. Two of
the three also link their curation (`[@url:https://strchive.org/critria/ALS1_NIPA1]`). That is a
sentence in a free-text field, not a value a gate can act on
(`@one-side-only-has-two-causes`), and on one of the four loci it is not there at all.

### 3.5 STRchive publishes a second file with the reasoning

`data/criTRia-curations.tsv` (65 rows) carries `classification`, `total_score`,
`genetic_evidence_score`, `experimental_evidence_score`, `publication_count`,
`publication_interval_years` and a prose `Description`, keyed `(Gene, Disease_ID)`.

* Its `classification` counts are Definitive 35 / Limited 14 / Moderate 8 / Strong 4 / Disputed 3 /
  Refuted 1 — no `Provisional`, consistent with the schema's "not yet curated" reading.
* Where the key joins the catalogue, **the two files never disagree** (0 disagreements over the 58
  joining pairs).
* All four Disputed/Refuted loci are curated, with scores: `DMD DMD` Refuted, total **0** (0 genetic,
  0 experimental, 2 publications); `NIPA ALS1` Disputed, total 3.0; `POLG CPEO` Disputed, 7.0;
  `DIP2B FRA12A` Disputed, 10.5.
* The join is imperfect upstream: 7 of 65 curation rows do not match a catalogue `(gene, disease_id)`
  exactly, in two distinct ways, both measured. **A gene-name mismatch:** the curation writes `NIPA`
  where the catalogue writes `NIPA1`. **A disease-id granularity mismatch:** the catalogue packs
  several disease ids into one comma-joined string and the curations split them —
  `FMR1` is `FXS, FXTAS, POF1` in the catalogue against `FXS` and `FXTAS,POF1` as two curation rows;
  `ATXN3` is `SCA3, MJD` against `SCA3`; likewise `CSNK1E` (`EPM, DEE` vs `EPM`), `XYLT1`
  (`DBQD2, BSS` vs `DBQD2`) and `PRDM12` (`HSAN VIII` vs `HSAN-VIII`). Any join onto this file needs
  to say what it did with those 7.

This repo reads none of it. `data/criTRia-curations.json`, `.tsv` and the `criTRia-SOP.pdf` are all in
the published repository and are not fetched anywhere in `enricher/`.

### 3.6 What this repo does with `evidence` today: nothing, deliberately

`strchive.py`'s `StrchiveLocus` docstring says it plainly — "`evidence`, the HPO terms and the
cross-references are real and are not parsed, because nothing here emits them". The field is dropped
at parse, so it is not merely unwritten; it is unread.

Measured on the drafter, which is the question the entry asks:

```bash
uv run just-dna-enricher draft-repeats <spec> --gene DMD --catalogue STRchive-loci.json

# STRchive `details` prose, whole string, six loci (§3.4)
python3 -c "
import json,re
d={x['id']:x for x in json.load(open('STRchive-loci.json'))}
pat=re.compile(r'conflict|disput|refut|controvers|not (been )?(replicat|confirm)',re.I)
for k in ['HD_HTT','FXS_FMR1','FRA12A_DIP2B','ALS1_NIPA1','CPEO_POLG','DMD_DMD']:
    print(k,[m.group(0) for m in pat.finditer(d[k].get('details') or '')])"

# the adopted-surface scan (§4.3) — a walked set, never a hand-kept list
uv run python -c "
import re
from just_dna_format import vocab
pat=re.compile(r'disput|refut|conflict|does_not|contradict|no_known',re.I)
for n in dir(vocab):
    v=getattr(vocab,n)
    if n.startswith('VALID') and isinstance(v,frozenset):
        hits=sorted(x for x in v if pat.search(str(x)))
        if hits: print(n,hits)"
```

writes

```
measure_kind,measure_min,measure_max,measure_tiling,direction,clin_sig,phenotype,trait_efo_id,conclusion,unresolved,source_field,source_element,pmid,gene,repeat_unit
repeat_count,,,,,,,MONDO_0010679,<<REPLACE>>,false,,,,DMD,CTT
```

DMD is the single `Refuted` locus in the catalogue, and its drafted row is indistinguishable from
HD_HTT's. The dry run over all four (`--gene DMD --gene NIPA1 --gene DIP2B --gene POLG --dry-run`)
reports the two things the provider *does* account for —

```
3 of 4 locus/loci state a fractional ref_copies ... it is not rounded anywhere.
2 of 4 locus/loci publish a locus_structure ... repeat_alleles.csv keys on a single repeat_unit.
would add 4 row(s) from 4 strchive locus/loci
```

— and says nothing about `evidence`. It is not even in the read-and-not-written accounting, because
the parser never carried it that far. `check-repeat-bands` reads the same `StrchiveLocus`, so it
cannot see the field either.

**So: no, the evidence call would not reach the author at all.**

### 3.7 Incidental: `draft-repeats` crashes appending into an older header

Reproducer:

```bash
cp -r reference_examples/htt_repeat_expansion <scratchpad>/dmd3
uv run just-dna-enricher draft-repeats <scratchpad>/dmd3 --gene DMD --catalogue STRchive-loci.json
```

```
compiler/src/just_dna_compiler/draft.py:621 → csv.DictWriter.writerows
ValueError: dict contains fields not in fieldnames: 'pmid', 'measure_tiling'
```

The shipped example's `repeat_alleles.csv` header has 13 columns and predates `pmid` and
`measure_tiling`; the writer takes `fieldnames` from the existing file and the rendered rows carry
more. `--dry-run` returns cleanly, and a spec directory with no `repeat_alleles.csv` writes fine, so
it is specifically the append-into-a-narrower-header path. Raw `ValueError`, not a diagnosed refusal.
Unrelated to RM170; recorded because it was hit while measuring the drafter.

---

## 4. The joint question

### 4.1 The subject of a contradiction, per corpus

* **CIViC** — the subject is a **variant**, and it is only a subject because two rows were joined on
  it. The contradiction is not a property of either row; row 8721 read alone is a well-formed
  refutation of nothing in particular, and row 7134 read alone is a well-formed claim. It becomes a
  contradiction at the `variant_id` group-by, and the group-by is over the snapshot, which means the
  subject only exists after the module's row is matched to a snapshot variant.
* **STRchive** — the subject is a **locus**, and the contradiction is a property of the record itself,
  visible without joining anything. It is also *not* a contradiction in the CIViC sense: nothing in
  STRchive asserts the locus is pathogenic and then denies it. One field grades the whole
  locus–disease association, and `Refuted` grades it as not holding while the same record still
  publishes a pathogenic band. The tension is between a **grade** and the **bands drafted from the
  same record**, not between two claims.
* Consequently the two corpora do not share a subject and do not share a shape. CIViC's is
  *inter-row, post-join, per variant*. STRchive's is *intra-record, pre-join, per locus* — and closer
  to a self-inconsistent record than to a disagreement.

### 4.2 Overlap between the two corpora: one gene, no locus

CIViC snapshot genes (germline direction axis, `01-Aug-2026`, accepted+submitted): **24**. STRchive
genes: **79** over 82 loci. Intersection: **`CBL`**, and one gene only.

No variant/locus overlap at all: CIViC's refuted-side genes are `CHEK2` and `VHL`; STRchive's
Disputed/Refuted genes are `DIP2B`, `NIPA1`, `POLG`, `DMD`. The two sets are disjoint, and no
reference example in this repo authors any of the six.

### 4.3 The adopted sources that already publish a refutation or a disputed-validity value

Enumerated from `enricher/src/just_dna_enricher/`, not guessed:

| source | surface | the value | where it lands | what happens today |
|---|---|---|---|---|
| **ClinGen gene-validity** + **GenCC** | `gene_validity.py` → `gene_validity.csv` | `Disputed` / `Disputed Evidence`, `Refuted` / `Refuted Evidence`, `No Known Disease Relationship` | mapped to the closed house members `disputed` / `refuted` / `no_known_disease_relationship`, raw kept in `classification_raw` | **a within-source contradiction is already handled**: a group holding both `definitive` and `refuted` with nothing ordering them is published as a **set, not a verdict**, via `undecidable_groups`, and warned about. Subject = `(gene, disease, mode of inheritance, submitter)` |
| **ClinVar** | `clin_sig.py`, `clinical.py` | `Conflicting classifications of pathogenicity` (three spellings normalized) | the closed member `conflicting` in `VALID_CLIN_SIG` | recorded; `concordance.py` maps `conflicting` → `undecided`; `@clinsig-never-escalates` keeps it out of the `strict` gate |
| **CIViC** | `civic_build.py` | `Does Not Support` | `direction` = null, raw words in two columns | §2 above |
| **STRchive** | `strchive.py` | `Disputed` / `Refuted` | nowhere — dropped at parse | §3 above |

**What was actually checked for the other adopted sources, stated as the scope it is.** Every
`VALID_*` frozenset in `just_dna_format.vocab` was walked — 26 of them — and matched against
`disput|refut|conflict|does_not|contradict|no_known`. Exactly three carry such a member:
`VALID_CLIN_SIG` (`conflicting`), `VALID_GENE_VALIDITY` (`disputed`, `refuted`,
`no_known_disease_relationship`), and `VALID_WARNING_CODES` (whose `*_contradicted` members are this
tier's own findings, not a source's value). So **no house vocabulary that ClinPGx/PharmGKB, CPIC,
PharmVar, the GWAS Catalog, the PGS Catalog, gnomAD constraint, LitVar, PubMind, ACMG SF or the FDA
drug labels land in has a refuting or disputed member.** That is a statement about *this repo's
adopted surface*, measured over `vocab.py`. It is **not** a statement that those sources publish
nothing of this shape upstream — no source file of any of them was opened for this question.

So the scope question — "is this a CIViC check or a general one" — has a measured answer available
from the adopted set rather than a guess: **four adopted sources publish something of this shape, and
three of them are already carried somewhere.** (Four is a floor on the adopted set, not a total over
the sources themselves — see the scoping note just above, and the bullet in §5.)

The house vocabulary `VALID_GENE_VALIDITY` already
contains `disputed` and `refuted` as closed members, and `gene_validity` already contains the machinery
for publishing an unorderable disagreement as a set. STRchive's `evidence` is that same vocabulary at
a different grain (a repeat locus rather than a gene–disease–MOI–submitter tuple), minus `Provisional`,
plus an open list rather than a closed one. CIViC's is the odd one out: the only case where the
contradiction has to be *constructed* from two rows.

---

## 5. What each figure was measured over — and what it is not a claim about

Per `@probe-names-the-table`, every negative here is scoped.

**CIViC.**

* *518 `Does Not Support` rows* — over `01-Aug-2026-ClinicalEvidenceSummaries.tsv`, whole file, all
  evidence types and origins. Not a claim about the API, and not about this format's axis: 516 of them
  are outside it.
* *2 accepted refutations on the direction axis* — over the same TSV, filtered to
  `variant_origin ∈ {Rare Germline, Common Germline}` and `(significance, evidence_direction) ∈
  CIVIC_DIRECTION_MAP`, joined to `01-Aug-2026-MolecularProfileSummaries.tsv` and
  `-VariantSummaries.tsv`. Not a claim about assertions (the 92 `assertion` CSQ entries were not
  examined), nor about `Predictive`/`Prognostic`/`Functional` refutations.
* *"zero assert-and-refute variants on the accepted basis"* — over that same joined TSV triple. It is
  **not** a claim that CIViC's accepted content is internally consistent generally; only that on the
  direction axis, no accepted refutation shares a variant with any claim.
* *3 refutations in the VCF, 347 overall* — over `01-Aug-2026-civic_accepted_and_submitted.vcf`, sha256
  `c6d5656ac65400189968ff3f1037f09e7f1719c3b5ddb4aa7eb36e5fbe35293a`, CSQ `evidence` entries only. The
  VCF holds no variant lacking a GRCh37 position, so this is not a corpus-wide count; the API call in
  §1.2 is what closes that gap for this axis.
* *`totalCount` 4 on `status: ALL`* — from the **live** `https://civicdb.org/api/graphql` on
  2026-09-01, which is not the `01-Aug-2026` release. It agrees with the dated files here; a later
  read may not. It is a claim about `significance: PREDISPOSITION|PROTECTIVENESS` +
  `evidenceDirection: DOES_NOT_SUPPORT` only, and about evidence items — assertions were not queried.
* *Parquet figures* — over `data/repro/civic/build-a/data/civic.parquet`, `status_basis
  accepted+submitted`, builder 0.7.0. Not a claim about what an `accepted`-basis build of the same
  release would emit; that build was not produced here, and the accepted-basis statements above come
  from the TSVs directly.
* *"no reference example authors VHL or CHEK2"* — `grep -rl 'VHL\|CHEK2' reference_examples/`, empty.
  Not a claim about any module outside this repository.

**STRchive.**

* *82 loci, 46/14/8/6/4/3/1* — over `data/STRchive-loci.json` at `main` == `v2.26.0`, sha256
  `3066188…`. Not a claim about any earlier release, and not about the derived BED/JSON catalogs under
  `data/catalogs/`, which carry no `evidence` column at all and include all four Disputed/Refuted loci
  without distinction.
* *"the vocabulary is not closed"* — over `data/STRchive-loci.schema.json` at `main`, whose `evidence`
  items use `examples` + `combobox: true` and no `enum`. Not a claim that curators in practice type
  outside the list; today's file does not.
* *criTRia figures* — over `data/criTRia-curations.tsv` at `main`, 65 rows. `data/criTRia-curations.json`
  and the SOP PDF were not parsed. The 0 disagreements is over the 58 pairs that join exactly; the 7
  non-joining rows were listed, not reconciled.
* *"the evidence call never reaches the author"* — established from `StrchiveLocus` (which does not
  carry the field) and confirmed by running `draft-repeats` on all four loci. Not a claim about
  `check-repeat-bands` finding nothing useful; it reads the same reduced record, so it cannot see the
  field either, and that was read from the code rather than exercised on a module with authored bands.
* *"one gene of overlap"* — CIViC gene column of the built parquet (24 distinct, germline direction
  axis only) against STRchive's 79. Not a claim about CIViC as a whole, whose gene coverage is far
  wider than this snapshot's axis.

* *"no adopted source but these four carries a refuting value"* — over the 26 `VALID_*` frozensets in
  `schema/src/just_dna_format/vocab.py`, walked as a set rather than listed by hand. Not a claim about
  what ClinPGx, CPIC, PharmVar, GWAS, PGS, gnomAD, LitVar, PubMind, ACMG SF or the FDA label feed
  publish; their upstream files were not read for this question, and a value this tier does not model
  would be invisible to the scan by construction.
* *STRchive `details` prose* — the full string on six loci, matched against
  `conflict|disput|refut|controvers|not (been )?(replicat|confirm)`. Not a claim that no other locus's
  prose hedges; only these six were read.

**Not measured, and not estimated.**

* How many *authored* rows in any real module would be subjects of either finding. No module in
  `reference_examples/` touches the six genes, so the honest answer here is zero and the informative
  answer needs a corpus this repo does not have.
* Whether the three VHL claims or their rebuttal are correct. That is a literature question and
  nothing here went to the papers (PMIDs 21454469, 33618821, 29789510, 28043156, 24466223, 34439168).
* Whether CIViC's `assertion` layer (92 CSQ entries, `AssertionSummaries.tsv`) carries a fifth shape.
  Not probed.
* `evidence_direction = N/A` — 17 rows in the TSV, 603 CSQ entries in the VCF. The task's phrasing was
  "`DOES_NOT_SUPPORT` (or otherwise refuting)", and `N/A` was **not** inspected for a rebuttal written
  as an absent direction. `CIVIC_DIRECTION_MAP` has no `N/A` key, so every one of them is dropped
  `not_direction_axis` and none reaches the parquet; whether any is a refutation in substance is
  unmeasured.

---

## Appendix — commands

**A — the accepted-basis both-camps hunt (§1.2, §1.4).** The single most load-bearing measurement in
this document. Run from the directory holding the three dated TSVs.

```python
import csv, collections
ev   = list(csv.DictReader(open('01-Aug-2026-ClinicalEvidenceSummaries.tsv'), delimiter='\t'))
var  = list(csv.DictReader(open('01-Aug-2026-VariantSummaries.tsv'),          delimiter='\t'))
by_profile = {r['single_variant_molecular_profile_id']: r for r in var
              if (r.get('single_variant_molecular_profile_id') or '').strip()}

GERM = {'Rare Germline', 'Common Germline'}                  # CIVIC_GERMLINE_ORIGINS
MAP  = {('Predisposition', 'Supports'): 'risk',              # CIVIC_DIRECTION_MAP
        ('Protectiveness', 'Supports'): 'protective',
        ('Predisposition', 'Does Not Support'): None,
        ('Protectiveness', 'Does Not Support'): None}

kept = []
for r in ev:
    if r['variant_origin'] not in GERM:                         continue
    if (r['significance'], r['evidence_direction']) not in MAP: continue
    v = by_profile.get(r['molecular_profile_id'])
    if v is None:                                               continue
    kept.append((v['variant_id'], v['gene'], v['variant'], r['evidence_id'],
                 r['evidence_direction'], r['evidence_status']))

byvar = collections.defaultdict(list)
for k in kept:
    byvar[k[0]].append(k)

print('rows', len(kept), 'variants', len(byvar))                       # 533 / 290
print('both camps:',      [v for v, rs in byvar.items()
                           if any(r[4] == 'Supports' for r in rs)
                           and any(r[4] == 'Does Not Support' for r in rs)])   # []
print('refutation only:', [v for v, rs in byvar.items()
                           if all(r[4] == 'Does Not Support' for r in rs)])    # ['4968', '788']
```

**B — the VCF CSQ parse (§1.2, §1.3, §2.2).** The field order is read from the header, never
positional.

```python
import re, collections
hdr, recs = None, []
for line in open('01-Aug-2026-civic_accepted_and_submitted.vcf'):
    if line.startswith('##INFO=<ID=CSQ'):
        hdr = re.search(r'Format: ([^"]+)', line).group(1).split('|')
    if line.startswith('#'):
        continue
    f = line.rstrip('\n').split('\t')
    m = re.search(r'CSQ=([^;]+)', f[7])
    if not m:
        continue
    for entry in m.group(1).split(','):
        d = dict(zip(hdr, entry.split('|')))
        d['_vcf_id'] = f[2]
        recs.append(d)

ev = [r for r in recs if r['CIViC Entity Type'] == 'evidence']
print(len(recs), len(ev))                                              # 5864 / 5772
print(collections.Counter(r['CIViC Entity Direction'] for r in ev))    # DOES_NOT_SUPPORT 347
dns = [r for r in ev if r['CIViC Entity Direction'] == 'DOES_NOT_SUPPORT']
print(collections.Counter((r['CIViC Entity Significance'], r['CIViC Entity Status'],
                           r['CIViC Entity Variant Origin']) for r in dns))
# the fan-out class (§2.2): evidence ids under more than one VCF record
c = collections.Counter(r['CIViC Entity ID'] for r in ev)
print(sum(1 for v in c.values() if v > 1))                             # 108 overall, 5 on the axis
for r in ev:
    if r['CIViC Entity ID'] == '8721':
        print(r['_vcf_id'], r['CIViC Molecular Profile ID'], r['CIViC Molecular Profile Name'])
```

**C — everything else.**

```bash
# the API
curl -s https://civicdb.org/api/graphql -H 'content-type: application/json' -d '{"query":
 "{ evidenceItem(id: 8721) { id status evidenceDirection significance molecularProfile { id name variants { id name } } } }"}'
curl -s https://civicdb.org/api/graphql -H 'content-type: application/json' -d '{"query":
 "{ evidenceItems(significance: PREDISPOSITION, evidenceDirection: DOES_NOT_SUPPORT, status: ALL, first: 50) { totalCount nodes { id status molecularProfile { id name variants { id } } } } }"}'

# the parquet
uv run python -c "import polars as pl; df=pl.read_parquet('data/repro/civic/build-a/data/civic.parquet'); \
  print(df.group_by(['significance_raw','evidence_direction_raw','evidence_status']).len())"

# STRchive
curl -sSL -O https://raw.githubusercontent.com/dashnowlab/STRchive/main/data/STRchive-loci.json
curl -sSL -O https://raw.githubusercontent.com/dashnowlab/STRchive/main/data/STRchive-loci.schema.json
curl -sSL -O https://raw.githubusercontent.com/dashnowlab/STRchive/main/data/criTRia-curations.tsv
curl -sSL    https://raw.githubusercontent.com/dashnowlab/STRchive/v2.26.0/data/STRchive-loci.json | sha256sum
uv run just-dna-enricher draft-repeats <spec> --gene DMD --catalogue STRchive-loci.json
```
