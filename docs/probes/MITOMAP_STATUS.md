# MITOMAP `mmutation` — the status column is two tokens and a prose tail, and the tokens are documented

**Subjects:** `mitomap.mmutation` (602 rows) and its undocumented-by-RM171 sibling
`mitomap.rtmutation` (494 rows), inside MITOMAP's published `pg_dump`; the four MITOMAP wiki pages
that legend those tables; and, for the overlap question, the ClinVar chrMT snapshot already on disk
in this checkout.
**Basis:** `https://mitomap.org/downloads/mitomap.dump.sql.gz` as served on 2026-09-02
(`sha256 16f01a96…`, `Last-Modified: Mon, 24 Aug 2026 05:01:10 GMT`), byte-identical to the local
copy at `/data/downloads/mitomap.dump.sql.gz`; four Wayback captures named in §1; and
`data/interim/clinvar/data/clinvar-chrMT.parquet` (`release.json`: `clinvar_file_date 2026-06-27`).
**Date of analysis:** 2026-09-02.

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`. Nothing
here proposes a design; the adoption call on `status` is deliberately left where
[ROADMAP_HISTORY.md § RM171](../ROADMAP_HISTORY.md#rm171--mitomaps-curated-mtdna-tables-adopted-as-the-increment-they-carry-over-clinvar)
leaves it. A later proposed shape, written against these measurements, lives in
[rm171_diff_strategy](rm171_diff_strategy.md). Every number below was re-derived from the bytes named
in §1 rather than quoted from the entry; where a figure disagrees with the entry, the entry is quoted
and the disagreement is stated rather than smoothed.

**The single most load-bearing measurement:** `status` is **not 29 unrelated sentences**. It is a
**two-token grammar** — a confirmation token (`Reported` | `Cfrm` | `Conflicting reports`) followed
by an optional bracketed rating (`[P]` | `[LP]` | `[VUS]` | `[VUS*]` | `[LB]` | `[B]`) — that
accounts for **568 of 602 rows exactly**, with a free-text qualifier on the remaining **34**. And
both token positions are **documented on MITOMAP's own pages**: the confirmation token by a legend
that has been on the page for years, the bracket by a legend stating the ratings are **ClinGen mtDNA
Variant Curation Expert Panel** calls scored by the criteria in McCormick et al. 2020
(DOI `10.1002/humu.24107`). The undocumented residue is the `*` on `VUS*` (10 rows), the two base
tokens the legend omits (`Conflicting reports` 16, and `Unclear` 12 in the sibling table), and the
34-row prose tail.

---

## 0. Summary

| question | answer |
|---|---|
| where is the dump | `/data/downloads/mitomap.dump.sql.gz`, and it is **byte-identical** to what `mitomap.org` serves today — not a mirror |
| `mmutation` rows | **602**, 14 columns, confirmed by field count |
| distinct `status` strings | **29** — reproduces the entry |
| the entry's "four most common" | **incomplete**: `Reported [VUS]` (59) outranks `Cfrm [LP]` (42) and is not named |
| is the tail compositional | **yes** — base token × optional bracket covers 568/602; 34 rows carry a prose qualifier |
| base-token distribution | `Reported` 516, `Cfrm` 69, `Conflicting reports` 16, unparsable 1 |
| bracket-token distribution | none 466, `VUS` 60, `LP` 44, `P` 16, `VUS*` 10, `B` 4, `LB` 2 |
| do the brackets mean ACMG P/LP/VUS/LB/B | **yes, and it is stated, not inferred** — MITOMAP publishes them as ClinGen VCEP ratings |
| is the vocabulary documented | **the tokens are; the tail is not.** No `COMMENT ON` in the dump; the legend is on the wiki |
| identity columns | `position` on 602/602; `refna`/`regna` are already VCF-shaped ref/alt |
| rows that mint a `variant_key` unchanged | **573 of 602** (560 via VRS, 13 coordinate keys), all distinct |
| rsID in `mmutation` | **none** — no column; the re-hosted `hmtvar` table reaches only 4 of 602 |
| PMIDs | **all 602 rows cite**, 3,666 links, mean 6.1 — but through `reference.nlmid`, a column not named `pmid` |
| already covered by an adopted source | **352 of 602 (58%)** are in the on-disk ClinVar chrMT snapshot at exact `(pos, ref, alt)` |
| is the bracket new information | **mostly no** — of the 136 bracketed rows, 120 are in that snapshot, **all 120 with `review_status = reviewed_by_expert_panel`**, and 119 agree with the bracket |
| the table RM171 names is not the one the repo's mtDNA module uses | the two `mt_heteroplasmy` variants (m.3243A>G, m.3271T>C) are in **`rtmutation`**, not `mmutation` |

---

## 1. Provenance of the inputs — and how the dump was acquired

The entry records this as still owed: *"how RM164 acquired the `pg_dump`. If it came from a mirror
rather than mitomap.org, that mirror's terms are a separate question this read does not answer."*
**It did not come from a mirror.** The local file is byte-for-byte what `mitomap.org` serves.

```bash
ls -la /data/downloads/mitomap.dump.sql.gz
# -rw-rw-r-- 1 mau mau 63780243 Sep  1 04:21 /data/downloads/mitomap.dump.sql.gz
sha256sum /data/downloads/mitomap.dump.sql.gz
# 16f01a96b735c8ea5ef5c4710d9e5490b12ca3bfa5495bc00a1b4ded6e2416ff

curl -sI "https://mitomap.org/downloads/mitomap.dump.sql.gz"
# HTTP/2 200 · content-type: application/x-gzip · content-length: 63780243
# last-modified: Mon, 24 Aug 2026 05:01:10 GMT · etag: "3cd3593-659c3dfe61f25"
# accept-ranges: bytes · server: cloudflare · cf-cache-status: REVALIDATED

curl -sS "https://mitomap.org/downloads/mitomap.dump.sql.gz" | sha256sum
# 16f01a96b735c8ea5ef5c4710d9e5490b12ca3bfa5495bc00a1b4ded6e2416ff  -
```

Same length, same digest, straight from `mitomap.org` over plain `curl` with no Cloudflare
interstitial — the data surface is open, exactly as RM164 recorded. **The mirror question is
closed**, and MITOMAP's own CC BY 3.0 terms are the only terms in play. That is the whole of what
this probe adds to the licensing axis; the terms text itself was read by RM171 on 2026-09-02 and is
not re-read here.

Two things the file *cannot* tell you, stated so nobody re-derives them:

- The gzip header carries **mtime = 0 and no original filename** (`1f8b0800 00000000 0003`), so the
  archive itself is silent about where it came from. The match above is what establishes origin.
- The local copy is reachable through the desktop document portal as
  `/run/user/1000/doc/by-app/snap.firefox/…/mitomap.dump.sql.gz`, which says a browser wrote it. That
  is which *program* downloaded it, not from *where*, and it is not evidence of anything on its own.

Decompressed once into the scratchpad for the extractions below and deleted afterwards:

```bash
zcat /data/downloads/mitomap.dump.sql.gz > mitomap.dump.sql
wc -l mitomap.dump.sql          # 6758225
grep -c '^CREATE TABLE ' mitomap.dump.sql   # 96
```

**6,758,225 lines** — the entry's "6.7 million lines" reproduces. **96 `CREATE TABLE` statements**,
where PROPOSAL_0_7_PT2 § RM164 says *"95 tables"*. The 96th is `mitomap.testtable` (`id`, `note`,
`flag`), which is plausibly what an earlier count excluded; whichever way, the re-derived figure is
96 and the difference changes nothing.

The four wiki pages, each a Wayback capture because `mitomap.org`'s *web* surface answers **403** to
`curl` and to the fetch tool alike (a Cloudflare interstitial). WebFetch declines `web.archive.org`
outright, so these were taken with `curl -L`:

```bash
for p in MutationsCodingControl MutationsCodingControlCfrm MutationsRNA ConfirmedMutations; do
  curl -sSL -o "wb_$p.html" -w "%{http_code} %{url_effective}\n" \
    "https://web.archive.org/web/2026/https://www.mitomap.org/foswiki/bin/view/MITOMAP/$p"
done
```

| page | capture | page's own last revision |
|---|---|---|
| `MutationsCodingControl` (the `mmutation` table) | **2026-04-17** | r888, **20 Mar 2026** |
| `MutationsCodingControlCfrm` (the `Cfrm` subset) | **2026-08-30** | **21 Aug 2026** |
| `MutationsRNA` (the `rtmutation` table) | **2026-07-31** | r910, **30 Jul 2026** |
| `ConfirmedMutations` | **2026-03-14** | r1, 10 Mar 2026 |

The `Cfrm` capture is six days newer than the dump (2026-08-30 vs a `Last-Modified` of 2026-08-24),
so the legend quoted in §3 is current with respect to the data measured here.

Table extractions, all from `COPY … FROM stdin` blocks terminated by `\.`:

```bash
sed -n '3570293,3570894p' mitomap.dump.sql > mmutation_rows.tsv    # 602 rows, 14 fields each
sed -n '6735526,6736019p' mitomap.dump.sql > rtmutation_rows.tsv   # 494 rows, 14 fields each
sed -n '3570903,3574568p' mitomap.dump.sql > mmutation_reference.tsv
sed -n '3562898,3568052p' mitomap.dump.sql > hmtvar.tsv
```

```bash
wc -l mmutation_rows.tsv && awk -F'\t' '{print NF}' mmutation_rows.tsv | sort -u
# 602
# 14
```

---

## 2. The `status` vocabulary, re-derived

### 2.1 The raw distribution

```bash
awk -F'\t' '{print $13}' mmutation_rows.tsv | sort | uniq -c | sort -rn
```

```
    419 Reported
     59 Reported [VUS]
     42 Cfrm [LP]
     16 Conflicting reports
     16 Cfrm [P]
     10 Cfrm [VUS*]
      7 Reported - possibly synergistic
      4 Reported [B]
      3 Reported / Secondary
      3 Reported / possibly synergistic
      3 Reported: individually neutral variants causing LHON in combination
      2 Reported [LB]
      2 Reported by paper as Likely Benign
      1 Reported [VUS] -population dependent; hg M9 marker
      1 Reported / Unclear
      1 Reported - possibly synergistic; hg L1b and A2i marker
      1 Reported - possibly secondary
      1 Reported / Population-dependent
      1 Reported; lineage N marker except  hg IJK
      1 Reported; lineage L & M marker, also hg IJK
      1 Reported; hg I6a & H10c marker
      1 Reported; hg D1 D2 M33 R30 marker
      1 Reported; hg C marker
      1 Reported by paper as Benign
      1 Reported as 8716dupT
      1 Reported as (1) possible association or as (2) benign
      1 Reported (~3% AF Lineage L)
      1 Cfrm [LP], alt locus at 9487del15
      1 alt loc to 9480del15 [LP]
```

**29 distinct strings over 602 rows — the entry's count reproduces exactly.**

**Where the entry is wrong, and it matters for sizing the tail.** RM171 names *"`Reported` 419,
`Cfrm [LP]` 42, `Conflicting reports` 16, `Cfrm [P]` 16, plus a long tail of one-offs"*. That skips
**`Reported [VUS]` at 59**, which is the second most common string in the column and outranks
`Cfrm [LP]`. So:

```bash
awk -F'\t' '$13!="Reported" && $13!="Cfrm [LP]" && $13!="Conflicting reports" && $13!="Cfrm [P]"' \
  mmutation_rows.tsv | wc -l    # 109
awk -F'\t' '$13!="Reported" && $13!="Reported [VUS]" && $13!="Cfrm [LP]" \
         && $13!="Conflicting reports" && $13!="Cfrm [P]"' mmutation_rows.tsv | wc -l    # 50
```

**109 rows fall outside the four the entry names; 50 fall outside the actual top five.** The
"long tail of one-offs" is 50 rows, not 109, and 44 of those 50 are still perfectly regular (§2.2).

### 2.2 It is compositional — two token positions, not 29 sentences

Every string begins with one of three confirmation tokens, and may carry one bracketed rating:

```bash
awk -F'\t' '{s=$13;
  if (s ~ /^Cfrm/) b="Cfrm";
  else if (s ~ /^Reported/) b="Reported";
  else if (s ~ /^Conflicting reports/) b="Conflicting reports";
  else b="OTHER: " s; print b}' mmutation_rows.tsv | sort | uniq -c | sort -rn
```

```
    516 Reported
     69 Cfrm
     16 Conflicting reports
      1 OTHER: alt loc to 9480del15 [LP]
```

```bash
awk -F'\t' '{s=$13; if (match(s,/\[[^]]*\]/)) print substr(s,RSTART+1,RLENGTH-2);
             else print "(no bracket)"}' mmutation_rows.tsv | sort | uniq -c | sort -rn
```

```
    466 (no bracket)
     60 VUS
     44 LP
     16 P
     10 VUS*
      4 B
      2 LB
```

Cross-tabbed, the pairing is **almost a function** — the two token positions are not independent:

| | (no bracket) | VUS | VUS\* | LP | P | LB | B |
|---|---|---|---|---|---|---|---|
| `Reported` | 450 | 60 | — | — | — | 2 | 4 |
| `Cfrm` | — | — | 10 | 43 | 16 | — | — |
| `Conflicting reports` | 16 | — | — | — | — | — | — |
| (unparsable) | — | — | — | 1 | — | — | — |

Sums to 602. **`Cfrm` never takes a benign-side rating and `Reported` never takes `P`, `LP` or
`VUS*`** — the two columns are the two halves of one judgement, not two free-form notes.

### 2.3 The 34-row residue, and what the qualifiers carry

Strip the base token and the bracket; 34 of 602 rows have anything left:

```bash
awk -F'\t' '{s=$13; sub(/^(Cfrm|Reported|Conflicting reports|Unclear)/,"",s);
  sub(/^ *\[[^]]*\]/,"",s); gsub(/^ +| +$/,"",s); if (s!="") n++} END{print n}' mmutation_rows.tsv
# 34
```

So **568 of 602 rows are exactly base + optional bracket**, and the residue is 5.6% of the table.
Tagged by what the qualifier is *about* (one row carries two tags, so the tags sum to 35 over
34 rows):

| what the qualifier carries | rows | examples |
|---|---:|---|
| **the variant acts only in combination** — synergy, secondary/primary LHON, combination-only | **18** | `Reported - possibly synergistic` (7); `Reported / Secondary` (3); `Reported: individually neutral variants causing LHON in combination` (3); `Reported - possibly secondary` (1) |
| **a haplogroup / lineage / population marker** | **9** | `Reported; hg D1 D2 M33 R30 marker`; `Reported; lineage L & M marker, also hg IJK`; `Reported / Population-dependent`; `Reported (~3% AF Lineage L)` |
| **a classification attributed to somebody else** | **4** | `Reported by paper as Likely Benign` (2); `Reported by paper as Benign`; `Reported as (1) possible association or as (2) benign` |
| **an alternative alignment / alias for the same event** | **3** | `Cfrm [LP], alt locus at 9487del15`; `alt loc to 9480del15 [LP]`; `Reported as 8716dupT` |
| **unclear** | **1** | `Reported / Unclear` |

**No qualifier carries a homoplasmy note.** Homoplasmy and heteroplasmy have their own columns
(§4.3), and nothing in the 34 duplicates them.

Two of the five groups say something the base+bracket pair does not: the combination-only group
(18 rows) is a statement about a *genotype* rather than an allele, and the alternative-alignment
group (3 rows) is a statement about *identity*. The other three restate, hedge or attribute the
classification.

### 2.4 A second free-text column nobody has named: `cfrm_date`

`cfrm_date` is populated on 114 of 602 rows, but only 69 rows are `Cfrm`:

```bash
awk -F'\t' '{s=$13; if (s ~ /^Cfrm/) b="Cfrm"; else if (s ~ /^Reported/) b="Reported";
  else if (s ~ /^Conflicting/) b="Conflicting"; else b="OTHER";
  d=($14=="\\N"||$14==""||$14==".")?"no date":"has cfrm_date"; print b" | "d}' \
  mmutation_rows.tsv | sort | uniq -c | sort -rn
```

```
    472 Reported | no date        69 Cfrm | has cfrm_date
     44 Reported | has cfrm_date  16 Conflicting | no date
      1 OTHER | has cfrm_date
```

Every `Cfrm` row has one, which is what the column is for. But 44 `Reported` rows also have a value,
and those values are **not dates**:

```bash
awk -F'\t' '$14!="\\N" && $14!="" {if ($14 ~ /^[0-9]{4}\.[0-9]{2}\.[0-9]{2}$/) print "ISO-ish date";
  else print "free text: "$14}' mmutation_rows.tsv | sort | uniq -c | sort -rn
```

```
     86 ISO-ish date
     14 free text: Reported by paper as VUS
      7 free text: Wong 2020 mRNA
      3 free text: check het in Bolze
      2 free text: Reported by paper as Likely Benign
      1 free text: Reported by paper as Likely Pathogenic
      1 free text: Reported by paper as Benign
      1 free text: .
```

**28 of the 114 populated `cfrm_date` cells are curator prose, and 18 of those are classification
claims** — `Reported by paper as VUS` (14), `… as Likely Benign` (2), `… as Likely Pathogenic` (1),
`… as Benign` (1). That is the same kind of content as the §2.3 "attributed to somebody else" group,
sitting in a different column.

```bash
awk -F'\t' '$13 ~ /by paper as/ && $14 ~ /by paper as/' mmutation_rows.tsv | wc -l   # 3
```

**Only 3 rows say it in both columns** (ids 458, 462, 469 — the same string duplicated verbatim). The
other **15** say it in `cfrm_date` while `status` reads a bare `Reported`. So the classification
signal on this table is spread across **two** free-text columns, and reading `status` alone misses
15 rows that carry a third-party classification: 34 rows of qualifier in `status`, 15 more only in
`cfrm_date`.

### 2.5 The same column exists on a table RM171 does not name

RM171 is about `mmutation`. `mitomap.rtmutation` has **the identical 14-column shape** (with `rna`
where `mmutation` has `aa`) and the same `status` column, for MITOMAP's rRNA/tRNA disease variants:

```bash
awk -F'\t' '{print $13}' rtmutation_rows.tsv | sort | uniq -c | sort -rn
```

```
    328 Reported          2 Reported [LB]        1 Reported [B] in hg K,U
     77 Reported [VUS]    1 See 7471insC         1 Reported [B]
     42 Cfrm [LP]         1 Reported [VUS](=7466d) 1 Reported as VUS
     13 Cfrm [VUS*]       1 Reported [VUS-]      1 Reported (=7474d)
     12 Unclear           1 Reported [VUS+]      1 Author considered as VUS
      7 Cfrm [P]
      4 Conflicting reports
```

**494 rows, 17 distinct strings, 6 with a prose residue.** Same two-token grammar, with two
additions: a **fourth base token `Unclear`** (12 rows), and the bracket tokens **`VUS+` and `VUS-`**
(1 row each). The union across both tables is **38 distinct strings, 4 base tokens (+3 unparsable)
and 8 bracket tokens**:

```bash
cat <(cut -f13 mmutation_rows.tsv) <(cut -f13 rtmutation_rows.tsv) | sort -u | wc -l   # 38
```

```
union base:    Reported 930 · Cfrm 131 · Conflicting reports 20 · Unclear 12 · 3 unparsable
union bracket: (none) 814 · VUS 138 · LP 86 · VUS* 23 · P 23 · B 6 · LB 4 · VUS- 1 · VUS+ 1
```

This is a finding about *scope*, not a re-scope of the item: RM171's own subject is `mmutation`, and
the counts above are kept separate for that reason. But "MITOMAP's curated mtDNA disease variants"
is 1,096 rows across two tables, not 602 across one, and §5.4 shows the repo's only mtDNA module
draws both of its variants from the table RM171 does *not* name.

### 2.6 The vocabulary did not move between April and August; the row count did

The archived `MutationsCodingControl` page embeds the same strings the dump carries, so the two can
be set-compared directly:

```bash
python3 - <<'PY'
import re; from collections import Counter
t = open('wb_MutationsCodingControl.html', encoding='utf-8', errors='replace').read()
page = Counter(re.findall(r'"((?:Reported|Cfrm|Conflicting reports|Unclear|alt loc)[^"]*)"', t))
dump = Counter(l.split('\t')[12] for l in open('mmutation_rows.tsv'))
print(len(page), sum(page.values()), len(dump), sum(dump.values()))
print(sorted(set(page) - set(dump))); print(sorted(set(dump) - set(page)))
PY
```

After discarding four matches that are the legend's own prose rather than table cells (`"Cfrm"` ×2
and the two `[VUS<span …` / `[LP<span …` legend examples), the page carries **594 rows over the same
29 distinct strings**. The dump carries **602 rows over the same 29**. Per-string deltas:
`Reported` 412→419, `Conflicting reports` 15→16, `Cfrm [VUS*]` 9→10, `Cfrm [LP]` 43→42.

**The vocabulary did not move; the table grew by 8 rows and one row moved out of `Cfrm [LP]`.** The
window is **capture 2026-04-17 → dump 2026-08-24, four months** — counted from the crawl date, not
from the page's own r888/2026-03-20 revision, because it is the embedded data blob being compared and
not the prose. One four-month window is not a stability claim (§7); it is the only churn measurement
available without a second dump.

---

## 3. Is the vocabulary documented? — the tokens yes, the tail no

### 3.1 Not in the dump

```bash
grep -c '^COMMENT ON' mitomap.dump.sql                          # 43
grep -o '^COMMENT ON [A-Z]* mitomap\.[a-z_]*' mitomap.dump.sql | sort | uniq -c | sort -rn
```

43 comments across the whole schema, on `unpublished` (18), `rsite` (6), `reference` (5), `protein`
(6), `locus` (3), `seqrange`, `haplodist`, `edit_date`. **None on `mmutation`, none on
`rtmutation`, none on any `status` column.**

The string `Cfrm` occurs **131 times in 6,758,225 lines, and all 131 are data cells** — 69 in the
`mmutation` COPY block, 62 in the `rtmutation` one. No view, no constraint, no comment, no lookup
table defines it:

```bash
grep -n 'Cfrm' mitomap.dump.sql | awk -F: '{n=$1;
  if (n>=3570293 && n<=3570898) a++; else if (n>=6735526 && n<=6736019) b++;
  else print "OTHER "n} END{print "mmutation:",a," rtmutation:",b}'
# mmutation: 69  rtmutation: 62
```

`mitomap.code`, the only lookup-shaped table in the schema, is the genetic code table and is **empty**
(0 rows). There is no `status` lookup table.

### 3.2 On the wiki, and it is explicit

`MutationsCodingControl` (r888, 20 Mar 2026; capture 2026-04-17) carries a legend under the table,
verbatim:

> "Reported" status indicates that one or more publications have considered the mutation as possibly
> pathologic. This is not an assignment of pathogenicity by MITOMAP but is a report of literature.
> Previously, mutations with this status were termed "Prov" (provisional).
>
> "Cfrm"(confirmed) status indicates that at least two or more independent laboratories have
> published reports on the pathogenicity of a specific mutation. These mutations are generally
> accepted by the mitochondrial research community as being pathogenic. A status of "Cfrm" is not an
> assignment of pathogenicity by MITOMAP but is a report of published literature. Researchers and
> clinicians are cautioned that additional data and/or analysis may still be necessary to confirm the
> pathological significance of some of these mutations.
>
> "P.M." (point mutation / polymorphism) status indicates that some published reports have determined
> the mutation to be a non-pathogenic polymorphism.

`MutationsRNA` (r910, 30 Jul 2026) carries the identical three paragraphs.

**`P.M.` is documented and has zero rows** in either table in this dump:

```bash
cat mmutation_rows.tsv rtmutation_rows.tsv | awk -F'\t' '$13 ~ /P\.M\./' | wc -l   # 0
```

So the published legend and the shipped data do not agree on the vocabulary's extent in *either*
direction: the legend defines a member with no rows, and the data carries three members
(`Conflicting reports`, `Unclear`, and the qualifier tail) the legend does not define.

### 3.3 The brackets are ClinGen VCEP ratings — stated, not inferred

Same legend, same page:

> ◊ **New**: As a member of the mtDNA Variant Curation Expert Panel for **ClinGen**, we are adding
> the calculated **ClinGen** pathogenicity ratings after VCEP curation. This will be shown in
> brackets in the Mitomap Status column, for example, "Reported [VUS◊]", "Cfrm [LP◊]", etc. The
> following abbreviations are used: B, Benign; LB, Likely Benign; VUS, Variant of Uncertain
> Significance; LP, Likely Pathogenic; P Pathogenic. The criteria used in the **ClinGen** curations
> may be found in **McCormick** et al, 2020, DOI: 10.1002/humu.24107. Note that the **ClinGen**
> scoring is quite stringent and gives fewer points than Mitomap does for many types of evidence,
> e.g., cybrid & other functional studies, in-silico tools, absence in large databases, heteroplasmy,
> de-novo requirements, and case numbers.

`MutationsCodingControlCfrm` (last edited **21 Aug 2026**, three days before the dump) restates it
with one extra sentence: *"The ClinGen VCEP may update this scoring from time to time if additional
supporting evidence is published."*

That page also legends the base token's own criteria:

> For Mitomap to assign a status of "Cfrm" to a possibly pathogenic variant, we look for confirming
> reports which address the criteria outlined in Mitchell et al 2006, Yarham et al 2011, Wong 2007,
> and Gonzalez-Viogue et al 2014. These criteria include the following: (1) independent reports of
> two or more unrelated families with evidence of similar disease; (2) evolutionary conservation of
> the nucleotide (for RNA variants) or amino acid (for coding variants); (3) presence of
> heteroplasmy; (4) correlation of variant with phenotype / segregation of the mutation with the
> disease within a family; (5) biochemical defects in complexes I, III, or IV in affected or multiple
> tissues; (6) functional studies showing differential defects segregating with the mutation (cybrid
> or single fiber studies); (7) histochemical evidence of a mitochondrial disorder; and (8) for fatal
> or severe phenotypes, the absence or extremely rare occurrence of the variant in large mtDNA
> sequence databases. […] A new scoring system is under development for these criteria, and will be
> linked here once published.

So the two token positions are **two different instruments**: the base token is MITOMAP's own
literature-count criterion, and the bracket is a third party's (ClinGen's) scored classification that
MITOMAP explicitly says is *more stringent than its own*. The legend says so in as many words.

### 3.4 What is still undocumented

Three things, each measured:

1. **The `*` on `VUS*`** — 10 rows in `mmutation`, 13 in `rtmutation`. The legend's own footnote
   marker is a **diamond (◊)**, and the legend example writes `"Reported [VUS◊]"` with the diamond
   inside the bracket. But the rendered page's data cells carry a literal **asterisk** on some rows
   and nothing on others — `grep -o 'VUS[^<]\{0,10\}' wb_MutationsCodingControl.html` returns both
   `VUS]","0.000%` (38×) and `VUS*]","0.000` (5×) — so the `*` is a real distinguishing mark in the
   data, and no legend on any of the four pages defines it. It occurs **only on `VUS`**, never on
   `P`, `LP`, `LB` or `B`, in either table. What it means is not established here.
2. **`Conflicting reports` (16 rows) and `Unclear` (12 rows in `rtmutation`)** — neither is in any
   legend text found.
3. **The 34-row qualifier tail and the 28 prose `cfrm_date` cells** — no legend, no key, no pattern
   documented anywhere.

**A neighbouring vocabulary that *is* closed, for contrast.** `mitomap.apogee` (24,181 rows, the
re-hosted APOGEE in-silico predictor) has its own `status` column over exactly **seven** members and
nothing else:

```
6294 LB · 4478 VUS+ · 3808 LP · 3426 VUS · 3230 B · 2828 VUS- · 117 P
```

That is a genuinely closed 7-tier scale in the same schema, and it is where `VUS+`/`VUS-` — the two
brackets that leak into `rtmutation` on one row each — actually live. The curated tables' bracket is
the 5-tier ClinGen set; APOGEE's is the 7-tier predictor set; they overlap in spelling and are not
the same instrument.

---

## 4. What else is on the row

### 4.1 The columns

```sql
CREATE TABLE mitomap.mmutation (
    id integer NOT NULL, locus character varying, dz character varying,
    allele character varying, "position" integer, refna character varying,
    regna character varying, aa character varying, cons character varying,
    contr character varying, homo character varying, hetero character varying,
    status character varying, cfrm_date character varying
);
```

Everything but `id` is `character varying` — including `position`'s neighbours and both heteroplasmy
flags. Populated counts (treating `\N`, empty and `.` as absent):

| column | populated / 602 | what it holds |
|---|---:|---|
| `locus` | 602 | gene symbol, 15 distinct — `MT-ATP6` 91, `MT-ND1` 84, `MT-ND5` 68, `MT-CYB` 64, `MT-CO1` 55, … `MT-CR` 31, `MT-ATP8/6` 10 |
| `dz` | 602 | disease, **343 distinct free-text strings** (§4.2) |
| `allele` | 602 | `m.`-prefixed HGVS-ish token, e.g. `m.72T>C`, `m.309_310insC`, `m.3902_3908inv` |
| `position` | 602 | integer rCRS position, 1-based |
| `refna` | 602 | reference allele — bases on 600, prose on 2 |
| `regna` | 600 | alt allele — bases on 576, `:` (deletion) on 24, NULL on 2 |
| `aa` | 602 | amino-acid change or `noncoding` |
| `cons` | 547 | conservation, **two encodings in one column**: 331 percentages (`100%`, `97.78%`) and 171 letter codes (`H` 132, `M` 26, `L` 12, plus `nr`/`nd`/`NA`/`ND`/`na`/`N` 38 and one `hydrophilic`), plus 7 bare `+` |
| `contr` | 566 | GenBank frequency as a literal fraction string, `1116/61168` |
| `homo` | 595 | presence flag (§4.3) |
| `hetero` | 598 | presence flag (§4.3) |
| `status` | 602 | §2 |
| `cfrm_date` | 114 | 86 dates + 28 prose cells (§2.4) |

**There is no rsID column, no HGVS-with-accession column, no ClinVar id, no OMIM id, and no
`genome_build` or reference-sequence column.** The build is implicit: the `locus` table's coordinates
(`MT-TF` 577–647, `MT-RNR1` 648–1601, `MT-TL1` 3230–3304) are rCRS/NC_012920.1, which is
byte-identical to GRCh38 `chrM` (16,569 bp — the same length this repo's refget table records for
`MT`). Nothing states that on the row.

### 4.2 `dz` is prose too, and its lookup table is not joined

343 distinct strings over 602 rows. 142 rows use `/` as a separator (`MELAS / Leigh Syndrome / DMDF /
MIDD / SNHL / CPEO / MM / FSGS / ASD / Cardiac+multi-organ dysfunction`), but `/` is **also inside
names** (`Complex V ATP6/8 deficiency`), so splitting on it is already lossy.

`mitomap.phenotype` exists — 39 rows of `short_name`, `name`, an OMIM URL — but **`mmutation` has no
`phenotype_id` and no foreign key to it**. Matching by abbreviation:

```
dz tokens (naive split on '/'): 853; exactly matching a phenotype short_name: 170 (19.9%)
rows where EVERY token matches:  106 of 602
```

Most common unmatched tokens: `Leigh Disease` (24), `Prostate Cancer` (18), `EXIT` (17),
`Leigh Syndrome` (15), `Possible association with sepsis` (14), `Patient with suspected
mitochondrial disease` (13), `PCOS patient` (11), `Suspected mito disease` (11). Some of those are
disease names the lookup simply omits; others (`Patient with suspected mitochondrial disease`) are
not disease names at all but a note about the ascertainment.

**So `status` is not the only free-text column on this table.** `dz` is, `cfrm_date` partly is, and
`cons` mixes a percentage and a letter grade in one column (331 vs 171 rows).

### 4.3 The heteroplasmy flags — RM164's figures reproduce exactly

```bash
awk -F'\t' '{print $11}' mmutation_rows.tsv | sort | uniq -c | sort -rn   # homo
awk -F'\t' '{print $12}' mmutation_rows.tsv | sort | uniq -c | sort -rn   # hetero
```

```
homo:    + 286 · - 216 · nr 90 · . 5 · \N 2 · na 1 · 99% 1 · 96% 1
hetero:  + 270 · - 238 · nr 89 · . 3 · na 1 · \N 1
```

Identical to what PROPOSAL_0_7_PT2 § RM164 recorded, including the two rows where a percentage was
typed into a flag column. Nothing here has changed and nothing is re-argued: presence flags with four
spellings of unknown, no threshold, no tissue.

### 4.4 Citations: every row cites, but through a column not named `pmid`

```bash
cut -f1 mmutation_reference.tsv | sort -u | wc -l                # 602
cut -f1 mmutation_reference.tsv | sort | uniq -c | awk '{s+=$1; n++; if($1>m)m=$1}
                                                        END{print s, n, s/n, m}'
# 3666 602 6.0897 435
```

**All 602 rows carry at least one reference**, 3,666 links, mean 6.09, max 435 (one heavily-cited
variant). `rtmutation_reference` adds 2,903 links.

`mitomap.reference` has **no column named `pmid`**. It has `nlmid`, populated on 6,373 of 6,770 rows
and near-unique (6,366 distinct values), which is article-level rather than journal-level. Four
sampled values check out as PMIDs against PubMed, matching journal *and* year:

```bash
curl -sS "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=266177,7219534,34969639,20304802&retmode=json"
```

| `reference.nlmid` | dump's `publication` / `date` | PubMed esummary |
|---|---|---|
| 266177 | Proc Natl Acad Sci U S A, 1977 | Proc Natl Acad Sci U S A, 1977 Apr |
| 7219534 | Nature, 1981 | Nature, 1981 Apr 9 — *Sequence and organization of the human mitochondrial genome.* |
| 34969639 | Molecular Genetics and Metabolism, 2022 | Mol Genet Metab, 2022 Jan |
| 20304802 | Proc Natl Acad Sci U S A, 2010 | Proc Natl Acad Sci U S A, 2010 Mar 16 |

**4 of 4 match.** That is enough to say `nlmid` *holds* PMIDs and not enough to say every one of the
6,373 does; 397 references have no `nlmid` at all.

### 4.5 How many of the 602 mint an identity under this repo's rules

Run against the repo's own code — `just_dna_format.vocab.ALLELE_PATTERN` (`^[ACGT]+$`) and
`just_dna_format.base.derive_variant_key`, with `chrom="MT"`, `start=position`, `ref=refna`,
`alts=regna`, build GRCh38:

```bash
uv run python - <<'PY'
import sys; sys.path.insert(0, "schema/src")
from just_dna_format.vocab import ALLELE_PATTERN
from just_dna_format.base import derive_variant_key
# … classify each row, mint where both alleles are base strings …
PY
```

| class | rows | mints? |
|---|---:|---|
| single-base substitution, `refna` and `regna` both one base | **560** | **yes** — case 2, a `ga4gh:VA.…` VRS id |
| indel/MNV already spelled in bases (`C`→`CC`, `TG`→`CA`, the 7-bp inversion) | **13** | **yes** — case 3, `MT:pos:ref:alt` |
| deletion with `regna = ':'` | **24** | **no** — `:` is not an allele; needs an rCRS anchor base or a `<DEL:n>` spelling |
| `refna == regna` (the three `m.N=` rows: 4769, 10398, 16519) | **3** | **no** — these are haplogroup markers where rCRS itself carries the rare allele; not a variant |
| `refna` is prose (`24bp_deletion`, `18bp_deletion`), `regna` NULL | **2** | **no** |

**573 of 602 mint a `variant_key` from the row as published, with no reference sequence and no
fetch — 560 VRS ids and 13 coordinate keys, all 573 distinct, no collisions.** The 24 deletions are
not unresolvable, they are unresolvable *in the format and compiler tiers*: left-anchoring a VCF
deletion needs the rCRS base at `position-1`, which Principle 2 forbids those tiers from fetching.

Same measurement on `rtmutation`: 463 SNVs, 13 base-spelled indel/MNVs, 15 `:` deletions, 3 `ref ==
alt` — **476 of 494 mint, all distinct**.

**Two structural facts that no count changes**, both about `VariantRow` rather than about MITOMAP:

- **`genotype` is a required field on `VariantRow`, and MITOMAP publishes none.** `homo`/`hetero` are
  presence flags across a literature corpus, not a called genotype.
- **The two sibling tables spell `allele` differently.** `mmutation` uses `m.72T>C` HGVS-ish (560 of
  602 match `^m\.[0-9]+[ACGT]>[ACGT]$`); `rtmutation` uses the legacy `A3243G` form on 466 of 494.
  Neither carries an accession, so neither is a complete HGVS expression.

---

## 5. Overlap with what is already adopted

### 5.1 What was checked

Every source with a `SourceTerms` row in `enricher/src/just_dna_enricher/licensing.py` — fifteen:

```bash
grep -n 'source="' enricher/src/just_dna_enricher/licensing.py
```

| source | covers mtDNA disease variants? | why / why not |
|---|---|---|
| **clinvar** | **yes** — the one real overlap | a chrMT snapshot is on disk; measured in §5.2 |
| civic | no | somatic cancer variant interpretations; `civic_draft` is built on molecular profiles in nuclear cancer genes |
| pubmind | no | a literature-derived layer, not an mtDNA variant catalogue |
| clinpgx / cpic / pharmvar | no | PGx. `MT-RNR1` — CPIC's one mitochondrial gene, the aminoglycoside ototoxicity guideline — appears **nowhere in this checkout**: `grep -rni 'MT-RNR1\|RNR1'` returns 0 hits. (Other MT genes do appear: `MT-TL1` is in `reference_examples/mt_heteroplasmy`. The negative is about the PGx gene, not about mtDNA) |
| gnomad | no (frequencies only) | `mitomap.gnomad` in the dump is a re-hosted copy of the same callset; a population frequency is not a curated disease call |
| ensembl | no | resolution only — coordinates, not clinical claims |
| clingen | no | gene–disease validity, not variant-level mtDNA |
| clingen_allele_registry | no | identity minting |
| gencc | no | gene-level curation |
| gwas_catalog | no | association study statistics |
| pgs_catalog | no | polygenic scores |
| mane | **structurally no** | MANE excludes mitochondrial genes by construction — *"gene located on mitochondrial genome"* is a documented MANE exclusion reason (noted in PROPOSAL_0_7_PT2) |
| strchive | no | tandem-repeat loci |

`grep -rni "mitomap" --include=*.py --include=*.toml .` over the whole checkout returns **0** — the
source is referenced in prose only, never in code.

### 5.2 ClinVar already carries 58% of `mmutation`

`data/interim/clinvar/data/clinvar-chrMT.parquet`, built 2026-07-30 from the 2026-06-27 ClinVar
GRCh38 VCF (`release.json`), 3,104 rows, all distinct on `(start, ref, alt)`:

```bash
uv run python -c "…join on (position, refna, regna) …"
```

| | exact `(pos, ref, alt)` match | position-level match |
|---|---:|---:|
| `mmutation` (602) | **352 (58.5%)** | 390 (64.8%) |
| `rtmutation` (494) | **303 (61.3%)** | 329 (66.6%) |

ClinVar's chrMT `clin_sig` on that snapshot: `uncertain_significance` 1255, `benign` 899,
`likely_benign` 729, `likely_pathogenic` 109, `pathogenic` 60, `not_provided` 34, `conflicting` 14,
`drug_response` 2, `affects` 1, `other` 1 — already in this repo's `VALID_CLIN_SIG` vocabulary,
because `clinvar_draft` normalizes it.

So **250 of the 602 `mmutation` rows are not in the on-disk ClinVar chrMT snapshot at all**, and
those are the rows where the identity half would not be duplicating an adopted source. What the
other 352 would add is not identity but MITOMAP's *own* judgement beside ClinVar's — which is the
same question §2 is about.

### 5.3 The bracket half is a call ClinVar already publishes, on 120 of the 136 rows that have one

§3.3 establishes that the bracket is a ClinGen VCEP rating. ClinVar carries expert-panel submissions
with a `review_status` that names them, and the on-disk chrMT snapshot has that column — so the two
can be compared directly. Over the **136** `mmutation` rows that carry a bracket
(`VUS` 60, `LP` 44, `P` 16, `VUS*` 10, `B` 4, `LB` 2):

```python
import polars as pl, re
cv = pl.read_parquet("data/interim/clinvar/data/clinvar-chrMT.parquet")
idx = {(r["start"], r["ref"].upper(), r["alt"].upper()): r for r in cv.iter_rows(named=True)}
BR = {"P": "pathogenic", "LP": "likely_pathogenic", "VUS": "uncertain_significance",
      "VUS*": "uncertain_significance", "LB": "likely_benign", "B": "benign"}
# for each mmutation row with a bracket, look up (position, refna, regna) in idx and compare
# BR[bracket] against the ClinVar row's clin_sig, tallying review_status alongside
```

| | rows |
|---|---:|
| bracketed `mmutation` rows | **136** |
| present in the ClinVar chrMT snapshot at exact (pos, ref, alt) | **120** |
| of those, `review_status == reviewed_by_expert_panel` | **120 — all of them** |
| bracket and ClinVar `clin_sig` name the same class | **119** |
| they disagree | **1** |
| absent from the snapshot | **16** (`LP` 10, `VUS` 6) |

The cross-tab is one diagonal: `[VUS]`↔`uncertain_significance` 53, `[LP]`↔`likely_pathogenic` 34,
`[P]`↔`pathogenic` 16, `[VUS*]`↔`uncertain_significance` 10, `[B]`↔`benign` 4,
`[LB]`↔`likely_benign` 2, and one off-diagonal cell.

**Every matched row carries ClinVar's expert-panel review status, and none carries any other** — so
the 120 are not incidental agreement with some submitter, they are the same VCEP call reaching this
repo by two routes. `VUS*` behaves exactly as `VUS` in all 10 cases, which is one more thing the
asterisk does *not* appear to mean.

The single disagreement is a currency question rather than a contradiction of instrument:

```
MITOMAP   MT-ND1  m.3761C>A   status = Reported [VUS]   cfrm_date = (none)
          dz = "Deafness w relapsing/remitting neurological symptoms"
ClinVar   variation 800504, rs1603219126, Likely_pathogenic,
          reviewed_by_expert_panel, "Mitochondrial disease|See cases|MT-ND1-related disorder"
```

One of the two copies is stale; which one is not established here — the ClinVar snapshot is dated
2026-06-27 and the dump 2026-08-24, so the *newer* file is the one carrying `VUS`.

**What this does and does not say.** It says the bracket half of `status`, where it is populated and
where the variant is in ClinVar, duplicates a classification an already-adopted source publishes with
its provenance attached. It says nothing about the **base** half — `Reported` / `Cfrm` /
`Conflicting reports` is MITOMAP's own literature-count criterion (§3.3) and has no ClinVar
counterpart measured here — nor about the **466 of 602** rows that carry no bracket at all.

### 5.4 The repo's one mtDNA module draws from the sibling table, not from `mmutation`

`reference_examples/mt_heteroplasmy` carries two variants, `rs199474657` (m.3243A>G) and
`rs199474671` (m.3271T>C), both `MT-TL1`. MT-TL1 is a tRNA, so both live in **`rtmutation`**:

```bash
awk -F'\t' '$5==3243 || $5==3271' mmutation_rows.tsv rtmutation_rows.tsv
```

```
rtmutation id=16  MT-TL1  A3243G  Cfrm [P]   cfrm_date=2020.07.29
rtmutation id=18  MT-TL1  A3243T  Cfrm [LP]  cfrm_date=2022.10.10
rtmutation id=29  MT-TL1  T3271C  Cfrm [P]   cfrm_date=2023.04.25
```

**Zero hits in `mmutation`.** The only module in this repo that authors mtDNA variants would draw
nothing from the table RM171 names. Both of its variants are `Cfrm [P]`, and the module's own
`variants.csv` writes `clin_sig=pathogenic` for both — a concordance of two, which is a coincidence
worth noticing and far too small to be a check.

---

## 6. What RM171 says, and what this probe found

| the entry says | measured |
|---|---|
| "602 curated mtDNA disease variants" | **reproduces** — 602 rows, 14 columns |
| "`status` is 29 distinct free-text strings" | **29 reproduces**; "free-text" understates the structure — 568 of 602 are base + optional bracket |
| "`Reported` 419, `Cfrm [LP]` 42, `Conflicting reports` 16, `Cfrm [P]` 16" as the common four | counts correct, **list incomplete**: `Reported [VUS]` at 59 is the second most common and is not named |
| "a long tail of one-offs" | **34 rows** carry a prose qualifier, of which 16 are true one-offs; 50 rows sit outside the actual top five |
| "mapping it onto `clin_sig` is a curation decision, not a normalization" | **not re-argued, and not adjudicated here.** The measurement that bears on it is §3.3: the bracket half is a published ClinGen VCEP rating over the same five classes `VALID_CLIN_SIG` uses; the base half is a different instrument on a different axis; and 466 of 602 rows have no bracket at all |
| "how RM164 acquired the `pg_dump`" is still owed | **answered** — §1, byte-identical to `mitomap.org`'s own file. Not a mirror |
| PROPOSAL_0_7_PT2: "95 tables" | **96 `CREATE TABLE`**; the extra is `mitomap.testtable` |
| PROPOSAL_0_7_PT2: `homo` `+` 286 / `-` 216 / `nr` 90, `hetero` 270/238/89 | **reproduces exactly** |
| — (not in the entry) | `mitomap.rtmutation`, **494 more curated rows with the same `status` column**, 17 strings, a fourth base token `Unclear` |
| — (not in the entry) | the vocabulary **is documented** on MITOMAP's wiki, brackets included |
| — (not in the entry) | `cfrm_date` is a **second** free-text column carrying classification prose on 18 rows |
| — (not in the entry) | 352 of 602 are **already in the ClinVar chrMT snapshot on disk** |
| — (not in the entry) | of the 136 rows carrying a bracket, **120 are in that snapshot, all 120 as `reviewed_by_expert_panel`, 119 agreeing** — the bracket largely restates a call an adopted source already publishes |

---

## 7. Scope — what each figure is measured over, and what it is not a claim about

**The dump.** Every count in §2, §3.1 and §4 is over `mitomap.mmutation` and `mitomap.rtmutation` as
they appear in the single `pg_dump` served at `mitomap.org/downloads/mitomap.dump.sql.gz` on
2026-09-02, `Last-Modified 2026-08-24`, `sha256 16f01a96…`. It is **one snapshot**. The §2.6
comparison against a 2026-04-17 page capture is the only churn measurement available here and covers
**four months** (crawl date to dump `Last-Modified`); it is not a claim that the vocabulary is stable,
only that it did not move in that window. It also assumes the archived page's embedded data blob is
current as of the crawl rather than frozen at the page's last save — if Foswiki bakes the blob in at
save time the window is 2026-03-20 → 2026-08-24 instead, which does not change the result.

**`@probe-names-the-table`.** Every negative is scoped to a named table. "No rsID column" is about
`mmutation` and `rtmutation`, not about MITOMAP — `mitomap.hmtvar` has a `dbsnp` column, and the
re-hosted `gnomad` and `helix` tables were not examined for identifiers here at all. The `hmtvar`
join reaches **9 of 602** `mmutation` rows (4 with a `dbsnp` value) and **425 of 494** `rtmutation`
rows (122 with one), so that table is an RNA-locus resource in this dump and says nothing about
coding-region coverage.

**The documentation finding is scoped to four pages.** `MutationsCodingControl`,
`MutationsCodingControlCfrm`, `MutationsRNA`, `ConfirmedMutations`, each read as a Wayback capture
with the dates in §1, because `mitomap.org`'s web surface 403s to `curl` and to the fetch tool alike.
"`Conflicting reports` and `Unclear` are undocumented" means **not on those four pages**. It is not a
claim that no MITOMAP page or publication defines them; MITOMAP's NAR database papers were not read.
Neither was McCormick et al. 2020 — it is cited here as the criteria document MITOMAP names, not as a
source that was checked.

**The `VUS*` finding is a negative about a legend, not about a meaning.** The legend uses a diamond
(◊) as its own footnote marker; the data carries a literal asterisk on some `VUS` rows and not
others, in both the dump and the rendered page. What distinguishes the marked rows is **not
established**, and no reading of it is offered.

**The identity counts are counts of what mints, not of what is correct.** 573 of 602 produce a
`variant_key` through `derive_variant_key` with `chrom="MT"` and no fetch. That is a statement about
the repo's grammar accepting the row's alleles. It is **not** a claim that the resulting VRS id names
the right allele — no coordinate was verified against rCRS, no `refna` was checked against the
reference base, and `@va-omits-ref` says only the enricher could catch a wrong single-base `ref`
anyway. The 24 `:` deletions are "not mintable **in format/compiler**", not "unresolvable".

**The ClinVar overlap is measured over one snapshot already in this checkout** —
`data/interim/clinvar/data/clinvar-chrMT.parquet`, built 2026-07-30 from ClinVar's 2026-06-27 GRCh38
VCF. A fresher ClinVar would move the 352. The join is on `(position, ref, alt)` with no
normalization on either side, so it under-counts wherever the two sources left-align an indel
differently; the position-level figure (390) is the loose bound.

**The §5.3 concordance is over the same one ClinVar snapshot**, joined on exact
`(position, ref, alt)` with no normalization on either side, and over the 136 bracketed rows only.
The "all 120 are `reviewed_by_expert_panel`" figure is a property of that snapshot's rows at those
coordinates; it is not a claim about ClinVar's chrMT holdings generally (the snapshot's 3,104 chrMT
rows carry many review statuses). No attempt was made to decide which of the two copies is current in
the one disagreeing case, and none of the 136 was checked against ClinVar's live record or against
the ClinGen VCEP's own registry.

**The adopted-source enumeration is over `licensing.py`'s `SourceTerms` rows** — the fifteen sources
with a declared licence in the enricher. It is not a survey of every module a consumer might have,
and "no other adopted source covers mtDNA disease variants" is a statement about those fifteen.

**Nothing here is a design.** The two-axis shape in §2.2 and the ClinGen attribution in §3.3 are
measurements. Whether either makes `status` mappable, and onto what, is the maintainer call RM171
holds open, and this probe deliberately does not take it.
