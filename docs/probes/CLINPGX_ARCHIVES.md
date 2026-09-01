# ClinPGx archives — the year-old zip is a retired filename, not a thinner sibling

**Subjects:** the three ClinPGx bulk archives RM173 compared — `clinicalAnnotations.zip`,
`summaryAnnotations.zip`, `clinicalVariants.zip` — plus what [clinpgx.org/downloads](https://www.clinpgx.org/downloads)
lists on 2026-09-02.
**Basis:** the files `https://api.clinpgx.org/v1/download/file/data/<name>.zip` served on 2026-09-02
(each 303s to `s3.pgkb.org/data/<name>.zip`); the three HTML pages snapshotted in §9 after JS
ran (downloads, summary-annotations help, clinical-variants help); and the
29 Jul 2025 [ClinPGx launch post](https://blog.clinpgx.org/pharmgkb-is-now-clinpgx/).
**Date of analysis:** 2026-09-02.

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`. Nothing
here proposes a design. Every number below was re-derived from the bytes named in §1; where a figure
disagrees with [ROADMAP_HISTORY.md § RM173](../ROADMAP_HISTORY.md#rm173--closed-2026-09-02-superseded-by-rm175-the-year-old-archive-was-a-retired-filename-not-a-stale-sibling),
the entry is quoted and the disagreement is stated rather than smoothed.

**The single most load-bearing measurement:** `clinicalAnnotations.zip` is still a 200 from the API
and still contains a 15-column annotation table, but it is **not on the downloads page**, its S3
object was last written **2025-07-05**, and the current 15-column archive is a **different key** —
`summaryAnnotations.zip`, `CREATED_2026-08-05`, same date as `clinicalVariants.zip`. The 13-month
gap RM173 measured is a retired filename the API kept serving, not two live surfaces of one table.

---

## 0. Summary

| | `clinicalAnnotations.zip` | `summaryAnnotations.zip` | `clinicalVariants.zip` |
|---|---|---|---|
| on [the downloads page](https://www.clinpgx.org/downloads) 2026-09-02? | **no** | yes — “Summary annotations”, 1.2 MB | yes — “Clinical Variant Data”, 72.6 KB |
| `CREATED_*.txt` | `2025-07-05` | `2026-08-05` | `2026-08-05` |
| S3 `Last-Modified` | Sat, 05 Jul 2025 07:31:53 GMT | Wed, 05 Aug 2026 08:12:59 GMT | Wed, 05 Aug 2026 07:31:23 GMT |
| annotation-level rows | 5,186 | **5,190** | **5,190** |
| columns in the main TSV | 15 | 15 | 6 |
| id column | `Clinical Annotation ID` | `Summary Annotation ID` | none |
| child tables | alleles / evidence / history | alleles / evidence / history | none |
| what the page says it is | (unlisted) | the genotype-summarised literature table, “a.k.a. clinical annotations” | “variant-drug pairs and level of evidence for all clinical annotations”; PMIDs “not available for automatic download” |

`variantAnnotations.zip` (4.1 MB, also `CREATED_2026-08-05`) is a **different layer** — per-publication
annotations the summaries are written from — and is not a successor of either file above.

---

## 1. Provenance of the inputs

```bash
mkdir -p /tmp/clinpgx-probe && cd /tmp/clinpgx-probe
for f in clinicalAnnotations.zip summaryAnnotations.zip clinicalVariants.zip; do
  curl -sS -L -o "$f" "https://api.clinpgx.org/v1/download/file/data/$f"
done
sha256sum clinicalAnnotations.zip summaryAnnotations.zip clinicalVariants.zip
# 9c6512c54f3c9321effacb11178fb2ae1c45fa3f1710f08c3c365ee7537ced07  clinicalAnnotations.zip
# 929ba092d22c53798fdb6cecf3cc2053e3bf478ed8efb4babb8c100cb47240e2  summaryAnnotations.zip
# 5262a90e7bf3eb14edc56cc174a91dab37be994c6176c2dc2d23aed7e2ef245f  clinicalVariants.zip
```

Each API URL answers **303** to `https://s3.pgkb.org/data/<name>.zip`. The two annotation zips are
different S3 keys, different etags, different version ids. They are not aliases of one object.

`curl -sI` on the old name still returns 200 after the redirect. That is the whole trap: a retired
filename the downloads page no longer links keeps serving last year's bytes.

---

## 2. What the downloads page lists

Read from a browser on 2026-09-02. The verbatim snapshots are §9 — a no-JS fetch of any of these
three URLs is the same “Javascript Is Disabled!” shell, so the listing below is from the rendered
DOM, not from `curl`.

Under *Summary and Variant Annotations Data*:

- `summaryAnnotations.zip` — “Summary annotations.” (1.2 MB)
- `variantAnnotations.zip` — “Variant annotations.” (4.1 MB)

Under *Clinical Variant Data*:

- `clinicalVariants.zip` — “This file contains a list of variant-drug pairs and level of evidence
  for all clinical annotations.” (72.6 KB)

**`clinicalAnnotations.zip` is not named anywhere on the page.** The dates are not on the page
either; they live in each zip’s `CREATED_*.txt`. Zip hrefs all go to
`https://api.clinpgx.org/v1/download/file/data/<name>.zip`.

The help pages that sit behind those “About … archive” links are snapshotted in §9.2 and §9.3.
The load-bearing sentences are: summary annotations are “a.k.a. clinical annotations”, and
clinical variants withhold “detailed descriptions … including supporting PMIDs”.

---

## 3. The rename, dated

[Announcing ClinPGx](https://blog.clinpgx.org/pharmgkb-is-now-clinpgx/), 29 Jul 2025:

> Clinical annotations, which summarize the associations between genetic variation and drug response
> annotated from peer-reviewed literature, are now called **summary annotations**.

The [pre-2025 PharmGKB overview](https://www.clinpgx.org/page/pgkbOverview) repeats it: “Clinical
Annotations (now called Summary Annotations)”.

`clinicalAnnotations.zip` on S3 was last written **24 days before that post** (05 Jul 2025) and has
not been overwritten. `summaryAnnotations.zip` is the name they have been rebuilding since.

Open Targets already switched the download:
`wget https://api.clinpgx.org/v1/download/file/data/summaryAnnotations.zip`
([EBIvariation/opentargets-pharmgkb](https://github.com/EBIvariation/opentargets-pharmgkb)).

This repo’s builder still defaults to the old URL
(`just_dna_enricher.clinpgx_build.DEFAULT_CLINPGX_URL`).

---

## 4. Zip internals — same family, renamed members

| member in the 2025 zip | member in the 2026 zip | role |
|---|---|---|
| `clinical_annotations.tsv` | `summary_annotations.tsv` | one row per annotation |
| `clinical_ann_alleles.tsv` | `summary_ann_alleles.tsv` | one row per genotype / allele |
| `clinical_ann_evidence.tsv` | `summary_ann_evidence.tsv` | supporting annotations |
| `clinical_ann_history.tsv` | `summary_ann_history.tsv` | curator history |
| `Clinical Annotation ID` | `Summary Annotation ID` | join key across the four TSVs |
| `LICENSE.txt` + `CREATED_*.txt` + `README.pdf` | same three | terms, release id, this help |

The other fourteen columns of the summary TSV are the same names, in the same order:

`Variant/Haplotypes`, `Gene`, `Level of Evidence`, `Level Override`, `Level Modifiers`, `Score`,
`Phenotype Category`, `PMID Count`, `Evidence Count`, `Drug(s)`, `Phenotype(s)`,
`Latest History Date (YYYY-MM-DD)`, `URL`, `Specialty Population`.

So the nine columns RM173 treated as unique to the year-old file — id, URL, Score, PMID count,
evidence count, specialty population, and the rest — **are in the current archive**. The 2026 file
is not column-poorer. The 6-column file is `clinicalVariants.zip`, a separately published rollup.

`CREATED_2026-08-05.txt` inside `summaryAnnotations.zip` reads
`Created on 08/05/2026 at 01:12:05 PDT.` Both annotation zips carry the same CC BY-SA 4.0 + no-sale
`LICENSE.txt` text the lane already gates on.

---

## 5. What moved between the two 15-column files

Joined on annotation id (`Clinical Annotation ID` = `Summary Annotation ID`):

| | count |
|---|---:|
| 2025 rows | 5,186 |
| 2026 rows | 5,190 |
| ids in both | 5,179 |
| only in 2025 | 7 — `1184514050`, `1184754547`, `1448635176`, `1448635185`, `1451245764`, `1451245800`, `1451448900` |
| only in 2026 | 11 — `1454245020`, `1454245027`, `1454245080`, `1454245101`, `1454247320`, `1454662300`, `1454665980`, `1454666046`, `1454751260`, `1454754640`, `1454893260` |

Same-id cells that differ (5,179 comparable rows):

| column | rows |
|---|---:|
| `URL` | 5,179 |
| `Level Modifiers` | 68 |
| `Drug(s)` | 40 |
| `Latest History Date` | 23 |
| `Evidence Count` | 17 |
| `Score` | 14 |
| `Phenotype(s)` | 13 |
| `PMID Count` | 10 |
| `Level of Evidence` | 8 |
| `Variant/Haplotypes` | 2 |
| `Level Override` | 1 |

Every shared URL is a host rewrite, not a new page:
`https://www.pharmgkb.org/clinicalAnnotation/<id>` →
`https://www.clinpgx.org/clinicalAnnotation/<id>`.
The path still says `clinicalAnnotation`. The help-page examples use `/summaryAnnotation/<id>`;
the TSV does not.

The allele child grows 16,087 → 16,117. Annotations with exactly three genotype rows:
**4,618 of 5,186** (2025) and **4,621 of 5,190** (2026). The builder docstring’s “4,618 of 5,113”
matches the 2025 three-genotype count and mismatches both files’ annotation counts.

`Phenotype Category` has the same thirteen observed values in both 15-column files, separator `;`.
`clinicalVariants.type` has the same thirteen, separator `,`. That is the RM173 `type` finding,
unchanged, and it is a spelling of one vocabulary (`@one-normalizer-two-spellings`), not a reason
to prefer the 6-column file.

---

## 6. `clinicalVariants` against the *current* 15-column file

Both files are `CREATED_2026-08-05`. Both have **5,190** rows. Both have **5,113** distinct
5-tuples once you ignore multiplicity (68 duplicate keys on each side).

`clinicalVariants.tsv` columns: `variant`, `gene`, `type`, `level of evidence`, `chemicals`,
`phenotypes`. No annotation id. The help page is explicit that PMIDs are withheld.

A naive string join on
`(variant, gene, chemicals/drugs, type/category, level)`
does **not** recover 5,190 = 5,190, because the drug lists are not spelled the same
(`atazanavir,atazanavir / ritonavir` against whatever `Drug(s)` writes). The unique-key counts
matching is the honest statement; a cell-by-cell 5-tuple equality is not, until someone normalizes
the drug list.

So: same date, same row count, same unique-key count, six columns a subset of fifteen. It is a
rollup of `summary_annotations.tsv`, not a currency probe against `clinical_annotations.tsv`.

---

## 7. Corrections to the RM173 entry

The entry, as of 2026-09-02, says:

> `clinicalAnnotations.zip` as served by `api.clinpgx.org` today carries `CREATED_2025-07-05.txt`;
> `clinicalVariants.zip` carries `CREATED_2026-08-05.txt`. … 99 of the 190 residue rows are
> subjects the lane holds whose level, category or drug set has moved.

Those dates and that join are **true of the files it named**. What they are not is a comparison of
two live surfaces of one table.

1. **The 15-column archive was renamed, not left stale.** The current file is
   `summaryAnnotations.zip` / `summary_annotations.tsv` / `Summary Annotation ID`, 5,190 rows,
   `CREATED_2026-08-05`. The downloads page lists it first under annotations.
2. **`clinicalAnnotations.zip` is a frozen alias.** The API still 303s it to S3; S3 has not
   overwritten the object since 2025-07-05. A 200 on the old URL is not evidence the source still
   publishes that name.
3. **The 190-residue / 96.3% figures compare the 6-column 2026 rollup to the 15-column 2025 leftover.**
   Against the contemporaneous 15-column file the row counts are equal (5,190) and the unique 5-tuple
   counts are equal (5,113). The “99 moved subjects” are mostly the year of curation the leftover
   never received, plus the drug-list spelling the 5-tuple cannot see.
4. **“Six columns are a strict subset of that file’s fifteen”** is true of `clinicalVariants` vs
   *either* annotation zip. It is not a property that makes the 2025 zip the rich one and the 2026
   zip the thin one. The rich 2026 file exists and is the one on the downloads page.
5. **The lane’s `DEFAULT_CLINPGX_URL` still names the leftover.** That is why a rebuild from “what
   the API serves at the builder’s default” reproduces 2025-07-05.

The framing that survives: ClinPGx publishes many archives and they do not refresh in lockstep.
The framing that does not: `clinicalVariants.zip` is a dated probe of the 15-column table the
lane already reads. It is a dated probe of a **filename the lane still uses**, and that filename
is not the current table.

---

## 8. How to re-derive any number here

```bash
# members + CREATED + row/column counts
python3 - <<'PY'
import zipfile, csv, io
from pathlib import Path
for zname, tsv in [
    ("clinicalAnnotations.zip", "clinical_annotations.tsv"),
    ("summaryAnnotations.zip", "summary_annotations.tsv"),
    ("clinicalVariants.zip", "clinicalVariants.tsv"),
]:
    z = zipfile.ZipFile(zname)
    print(zname, z.namelist())
    rows = list(csv.DictReader(io.StringIO(z.read(tsv).decode()), delimiter="\t"))
    print(" ", tsv, len(rows), "cols", list(rows[0]))
PY

# id join
python3 - <<'PY'
import zipfile, csv, io
def rows(z, tsv):
    return list(csv.DictReader(io.StringIO(zipfile.ZipFile(z).read(tsv).decode()), delimiter="\t"))
old = {r["Clinical Annotation ID"] for r in rows("clinicalAnnotations.zip", "clinical_annotations.tsv")}
new = {r["Summary Annotation ID"] for r in rows("summaryAnnotations.zip", "summary_annotations.tsv")}
print(len(old), len(new), len(old & new), len(old - new), len(new - old))
PY
```

The downloads-page negative (`clinicalAnnotations.zip` absent) has to be read from a browser.
A no-JS fetch of any ClinPGx HTML page is not a listing — see §9.

---

## 9. Page snapshots (browser, 2026-09-02)

**The JS-rollup problem is universal on this host, not a downloads-page quirk.** Every HTML
URL tried — `/downloads`, `/page/downloadSummaryAnnotationsHelp`,
`/page/downloadClinicalVariantHelp` — ships the same shell:

- `<html class="no-js">`, `<title>ClinPGx</title>` regardless of the route
- a `<noscript>` block whose visible text is *Javascript Is Disabled! / ClinPGx requires Javascript.*
- the article body filled in only after the app runs

`curl`, `WebFetch`, and any other no-JS GET therefore cannot answer “is `clinicalAnnotations.zip`
listed?” or quote a help page. The three snapshots below are `document.body` / `main.innerText`
from a locked browser tab after `document.readyState === "complete"`, chrome (Search / Menu /
footer legal) stripped. They are a capture, not a contract: re-read the live page before treating
a sentence as current.

The no-JS body, identical on all three URLs:

```
Javascript Is Disabled!

ClinPGx requires Javascript.

Here are the instructions on how to enable JavaScript in your web browser.
```

### 9.1 [clinpgx.org/downloads](https://www.clinpgx.org/downloads)

Rendered title: `Downloads`. Nineteen `.zip` hrefs; none is `clinicalAnnotations.zip`.
Related-projects attachments after *From Related Projects* are omitted here — they are not
ClinPGx bulk archives.

```
Downloads

ClinPGx data and knowledge are available as download files. We have found that it is often
critical for users to check with our team at feedback@clinpgx.org before embarking on a large
project using these data to be sure that the files and data we make available are being
interpreted correctly. We generally do not need to be a co-author on such analyses; we just
want to make sure that there is a correct understanding of our data before lots of resources
are spent.

Examples of papers that have been written by others using ClinPGx/PharmGKB information

Annotations Data
Downloads contain information from our annotations.

Summary and Variant Annotations Data

Summary annotations.

summaryAnnotations.zip
 1.2 MB
About summary annotation archive
  → https://api.clinpgx.org/v1/download/file/data/summaryAnnotations.zip
  → https://www.clinpgx.org/page/downloadSummaryAnnotationsHelp

Variant annotations.

variantAnnotations.zip
 4.1 MB
About variant annotation archive
  → https://api.clinpgx.org/v1/download/file/data/variantAnnotations.zip

Variant, Gene and Drug Relationship Data

Relationships summarized from ClinPGx annotations.

relationships.zip
 2.3 MB
About Relationships archive
  → https://api.clinpgx.org/v1/download/file/data/relationships.zip

Clinical Guideline Annotations

Detailed clinical guideline annotations in JSON format:

guidelineAnnotations.json.zip
 841.0 KB
About Clinical Guideline Annotations archive
  → https://api.clinpgx.org/v1/download/file/data/guidelineAnnotations.json.zip

Drug Label Annotations

Drug label annotations in TSV format:

drugLabels.zip
 58.1 KB
About Drug Label Annotations archive
  → https://api.clinpgx.org/v1/download/file/data/drugLabels.zip

Pathways

Pathways data in BioPAX XML, TSV, and JSON formats:

pathways-biopax.zip
 619.2 KB
About Pathway Biopax archive

pathways-tsv.zip
 199.3 KB
About Pathway TSV archive

pathways.json.zip
 1.8 MB
About Pathway JSON archive

Clinical Variant Data

This file contains a list of variant-drug pairs and level of evidence for all clinical
annotations in TSV format:

clinicalVariants.zip
 72.6 KB
About Clinical Variant archive
  → https://api.clinpgx.org/v1/download/file/data/clinicalVariants.zip
  → https://www.clinpgx.org/page/downloadClinicalVariantHelp

Literature Occurrence

A list of objects that occur in ClinPGx literature annotations and pathways.

occurrences.zip
 2.8 MB
About Occurrence archive

Primary Data
Downloads contain term mappings and/or cross-references to multiple vocabularies, and an
indication of whether the term has been annotated in ClinPGx.

Genes

A summary of the gene information used by ClinPGx and how it has been annotated.

genes.zip
 2.8 MB
About Genes archive

Variants

A summary of variants annotated by ClinPGx that have also been tracked in dbSNP.

variants.zip
 873.8 KB
About Variants archive

Drugs/Chemicals

Summaries of chemical information annotated by ClinPGx. The list of drugs is a subset of the
list of all chemicals annotated by ClinPGx.

drugs.zip
 662.3 KB
About Drugs archive

chemicals.zip
 794.3 KB
About Chemicals archive

Phenotypes

A summary of disease and other phenotypes that have been annotated by ClinPGx.

phenotypes.zip
 183.0 KB
About Phenotypes archive
```

### 9.2 [downloadSummaryAnnotationsHelp](https://www.clinpgx.org/page/downloadSummaryAnnotationsHelp)

Rendered title: `Summary Annotations Help File`. The heading
`summaryl_annotations.tsv` (missing `a`) is the page’s own typo. Example URLs on this page
use `/summaryAnnotation/<id>`; the TSV `URL` column uses `/clinicalAnnotation/<id>` (§5).

```
Summary Annotations Help File

The set of files comprised of summary_annotations.tsv, summary_ann_alleles.tsv,
summary_ann_evidence.tsv and summary_ann_history.tsv contain ClinPGx’s summary annotations
(a.k.a. clinical annotations) and associated information. These annotations are manually
created by the ClinPGx curators to provide an evidence-rated, genotype- or allele-based
summary of the literature evidence annotated in ClinPGx for an association between a genetic
variant and a drug. Please refer to the ClinPGx website for more information about summary
annotations, and how they are assigned a level of evidence based on scores.

Description of Files:
summary_annotations.tsv: Contains all of the meta-data about each summary annotation.
summary_ann_alleles.tsv: Contains the genotype- or allele-based annotation text and
CPIC-assigned allele function, if available.
summary_ann_evidence.tsv: Contains information about each supporting annotation (variant
annotation, guideline annotation, label annotation) for every summary annotation.
summary_ann_history.tsv: Contains the history of the summary annotation, including the
creation date and the dates of changes or updates to the annotation.
LICENSE.txt: The ClinPGx license for using ClinPGx data, including summary annotations.
CREATED_xxxx-xx-xx.txt: This file indicates the date that all files in this group were
created from the database.
README.pdf file: This document.

A description of the fields in each file follows.

summaryl_annotations.tsv:

SummaryAnnotation ID: The unique ClinPGx ID number for the annotation.
Variant/Alleles: Variant rsID from dbSNP or the allele names.
Gene: HGNC gene symbol.
Level of Evidence: Levels 1A-4 with 1A being the highest level of evidence; more information
found on ClinPGx.
Level Override: Description of whether the level of evidence assigned based on the summary
annotation score was changed by ClinPGx curators. Options: Yes (plus reason), No.
Level Modifiers: Description of extra information used when assigning level of evidence.
Options: VIP Tier 1, rare variant.
Score: Summary annotation score calculated from supporting annotations; more information
found on ClinPGx.
Phenotype Category: Association phenotype. Options: toxicity, efficacy, dosage,
metabolism/PK, PD, other.
PMID Count: The number of PMIDs with variant annotations used to support the summary
annotation.
Evidence Count: Number of annotations supporting the summary annotation, including variant
annotations, guideline annotations and drug label annotations.
Drug(s): Drugs associated with the variant/allele.
Phenotype(s): Phenotypes in the variant/allele-drug association. For example, if the
association was found in patients with a particular phenotype (disease), or if the
variant/allele-drug combination causes a particular phenotype.
Latest History Date: The date of creation of the summary annotation or the last time it was
updated.
URL: ClinPGx webpage for the summary annotation.
Specialty Population: Description of a specialty population (e.g. ‘Pediatric’) in any
supporting variant annotation.

Example row from summary_ann_alleles.tsv file:

SUMMARY ANNOTATION ID	VARIANT/HAPLOTYPES	GENE	LEVEL OF EVIDENCE	LEVEL OVERRIDE	LEVEL MODIFIERS	SCORE	PHENOTYPE CATEGORY	PMID COUNT	EVIDENCE COUNT	DRUG(S)	PHENOTYPE(S)	LATEST HISTORY DATE	URL	SPECIALTY POPULATION
1447954390	rs75039782	CFTR	3	Yes: Level of evidence set to 3. Ataluren is a drug for the treatment of Duchenne muscular dystrophy caused by a nonsense mutation and not indicated in CF treatment.	Rare Variant; Tier 1 VIP	4	Other	2	2	ataluren	Cystic Fibrosis	2021-02-10	https://clinpgx.org/summaryAnnotation/1447954390	Pediatric

summary_ann_alleles.tsv:

Summary Annotation ID: The unique ClinPGx ID for the annotation.
Genotype/Allele: The genotype or allele associated with the clinical phenotype in the next
column.
Annotation Text: The summary annotation for the given genotype or allele.
Allele Function: The CPIC allele function, if it has been assigned; more information found
on ClinPGx.

Example rows from summary_ann_alleles.tsv file:

SUMMARY ANNOTATION ID	GENOTYPE/ALLELE	ANNOTATION TEXT	ALLELE FUNCTION
613979022	CC	May be less likely to have improved left ventricular ejection fraction after carvedilol treatment.
1183615480	*3	Patients carrying the CYP2D6*3 allele in combination with another no function allele may have decreased metabolism of carvedilol as compared to patients carrying two normal function alleles. This annotation only covers the pharmacokinetic relationship between CYP2D6 and carvedilol and does not include evidence about clinical outcomes. Other genetic and clinical factors may also influence carvedilol metabolism.	No function

summary_ann_evidence.tsv:

Summary Annotation ID: The unique ClinPGx ID for the annotation.
Evidence ID: The unique ClinPGx ID for the annotation supporting the summary annotation,
including variant annotations, guideline annotations and drug label annotations.
Evidence Type: The type of supporting annotation. Options: Variant Annotation (Drug),
Variant Annotation (Phenotype), Variant Annotation (Functional Assay), Guideline Annotation,
Label Annotation.
Evidence URL: ClinPGx webpage for the supporting annotation.
Evidence PMID: If the supporting annotation is a variant annotation, the PMID the variant
annotation is based on; otherwise, blank.
Evidence Summary: Variant annotation text or description of the guideline or label.
Study Parameter Used for Scoring: The ID of the Study Parameters object used to determine
score, only applicable to Variant Annotations
Evidence Score: The score of the supporting annotation.

Example row from summary_ann_evidence.tsv file

SUMMARY ANNOTATION ID	EVIDENCE ID	EVIDENCE TYPE	EVIDENCE URL	EVIDENCE PMID	EVIDENCE SUMMARY	EVIDENCE SCORE
449717935	1449717924	Variant Drug Annotation	https://clinpgx.org/variantAnnotation/1449717924	30136624	Genotype GG is associated with increased response to Opioid anesthetics, Other general anesthetics or volatile anesthetics as compared to genotypes AA + AG.	3

summary_ann_history.tsv:

Summary Annotation ID: The unique ClinPGx ID number for the annotation.
Date (YYYY-MM-DD): The date of the history event.
Type: The type of the history event. Options: Create, Update, Note, Correction.
Comment: The comment entered by the ClinPGx curator describing the action taken on the
summary annotation; this field may be blank.

Example row from summary_ann_history.tsv file:

SUMMARY ANNOTATION ID	DATE (YYYY-MM-DD)	TYPE	COMMENT
1450931822	2021-01-29	Update	Edited phenotype descriptions to include CPIC 'no recommendation'.

It is important to understand that summary annotations are created from literature that has
been curated by ClinPGx. There may be more literature in the public domain to support or
contradict an association that is not in the ClinPGx database. ClinPGx manually curates high
profile literature but does not contain curated literature from every domain-based journal,
or all of PubMed. ClinPGx reviews evidence from curated literature in non-regular intervals
and re-evaluates the evidence strength for each association as more literature becomes
available.
```

### 9.3 [downloadClinicalVariantHelp](https://www.clinpgx.org/page/downloadClinicalVariantHelp)

Rendered title: `Clinical Variants Download Help`.

```
Clinical Variants Download Help

This file contains a list of variant-drug pairs and the level of evidence for each
association. Please read the strength of evidence documentation for a complete description
of the different levels of criteria. Detailed descriptions of the associations, including
supporting PMIDs, are not available for automatic download. More information can be found
on the ClinPGx licensing page.

variant = name or symbol of the variant
gene = HGNC ID of the gene
type = category or categories that the annotation falls in
level of evidence = strength of evidence for the annotation
chemicals = drug(s) associated with the variant in the annotation; from the ClinPGx drug
vocabulary
phenotypes = associated disease phenotype(s), where applicable
```
