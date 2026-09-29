# variation-normalizer and metakb, surveyed for just-dna-format — 2026-09-28

Scope: finding, not deciding. The companion to [GKS_SURVEY](GKS_SURVEY.md), which already measured
both tools' install weight (variation-normalizer 0.16.0: 68 packages, 421 MB, needs UTA + SeqRepo +
a gene-normalizer DB; metakb: neo4j + four normalizers + UTA + SeqRepo). Those numbers are not redone
here. This round went deeper: both tools were **run** or **read as data**, and the answers were compared
with what our enricher and our identity protocol produce on the same inputs.

Every claim carries a tag: **[M]** measured this session (a command was run), **[D]** read in primary
docs or source, **[I]** inferred. Raw API responses and cloned repos were kept in the surveying session's
scratchpad, which is not preserved. The request shapes are written out below so that any answer can be
re-fetched. Nothing in the repo was edited.

**This is evidence, never contract**, the standing rule for everything under `docs/probes/`.

---

## 0. Headline findings

1. **variation-normalizer has a public hosted API and it works.** `https://normalize.cancervariants.org/variation/`
   serves 16 endpoints, answers in 0.1–3 s, needs no key, and states no rate limit, SLA or terms [M].
   It reports `service_meta_.version: "unknown"` and runs **vrs-python 2.3.1** [M: `vrs_python_meta_`,
   which only `/translate_from` returns]. A local run is not feasible in a scratchpad: UTA is a manual
   download behind a human-verification page, and SeqRepo is 13.5 GB (both measured in GKS_SURVEY).
2. **On genomic input its VRS ids are byte-identical to ours: 7 distinct alleles over 10 genomic inputs** [M]. That
   covers both spellings of `rs72613567` and `rs77944059` (one id each), the RM267 `rs8176719` pair (two
   different ids on both sides), both readings of CIViC 2131, and BRAF V600E. So it adds **no new
   algorithm** over our `VrsMinter`: same library, same VRS 2.0 rule. As a witness, the only independent
   part is its sequence store.
3. **`/normalize` answers at the layer of its input, not on GRCh38.** A protein name gives a
   **protein** allele (`BRAF V600E` → `NP_004324.2`), and a `c.` expression gives a **transcript**
   allele (on the MANE transcript). Only gnomAD-VCF or `NC_` input gives a genomic allele [M]. So it
   does **not** produce what our protocol ends in (`chrom:start:ref:alt` + CAID + rsID), and it does
   not solve identity-from-a-name for our `(variant_key, genotype)` grain.
4. **The inputs our protocol found hard, it refuses or answers wrongly.** It has no rsID tokenizer, no
   frameshift support (issue #107, open since 2021-05), no `c.` duplication classifier, no legacy
   `c.<N>ins<SEQ>` and no `IVS` notation. `TP53 R72P` fails with a bare "Unable to translate" where the
   Allele Registry's 400 is evidence. `VHL L129Q` is accepted as a missense substitution when the
   record's own cDNA makes it `p.Leu129delinsGlnMet` [M]. It also swaps the transcript silently:
   `NM_000551.3` comes back on `.4`, and `NM_000579.3` comes back on `NM_001394783.1`, with no warning
   [M].
5. **Neither tool carries the VRS version on the wire.** `/normalize` has no VRS or vrs-python version
   field. variation-normalizer pins `ga4gh.vrs[extras] >=2.3.0,<3.0`, which **admits the 2.4 line** that
   will carry VRS 2.1's smallest-factor rule, while metakb already pins `~=2.4.0-a1` [D: both
   `pyproject.toml`]. A hosted witness would inherit RM304's silent drift, with nothing to announce it.
6. **metakb has no public v2 API.** `search.cancervariants.org` is the legacy v1 Elasticsearch index
   (`/openapi.json` → `index_not_found_exception`), and `dev-search.cancervariants.org` is behind an
   API Gateway 403 [M]. The only reachable harmonized data is the **`2.0.0-dev1` release attachments
   dated 2025-04-28** (CIViC 42.5 MB and MOA 9.9 MB JSON, VA-Spec), about 17 months old [M].
7. **metakb's CIViC data carries a negation as a positive.** CIViC profile 4353 `NOT KIT D816V` (whose
   `variant_ids` is `65`, a single variant) comes out with the **same** `DefiningAlleleConstraint`
   (`ga4gh:VA.nhiDwIq1…`) as profile 65 `KIT D816V`. Nothing in its constraints or extensions marks the
   NOT, so evidence 11158 (imatinib sensitivity when D816V is **absent**) reads as a claim about D816V
   **present** [M: dump + local CIViC release]. The mechanism is civicpy's single-variant gate
   (`len(variants) == 1`) plus `variants[0]` [D]. Our build never reaches this: 11158 is somatic and is
   dropped as `non_germline_origin` [M].
8. **metakb answers RM28 with opaque ids, not with structure.** 542 of 975 CIViC categorical variants
   in the dump have **no constraint** (`vicc_normalizer_failure: true`), and 1,518 of 2,549 statements
   have such a subject. Every multi-variant profile is dropped upstream by civicpy (`"complex molecular
   profile. Skipping"`), and so are PREDISPOSING, ONCOGENIC and FUNCTIONAL evidence [M/D]. The
   germline share of what is left is **116 of 2,549 statements** [M].

---

## 1. variation-normalizer — what it is

### 1.1 Endpoints, current release and hosted service

| Endpoint (hosted, GET unless noted) | Does | Output layer |
|---|---|---|
| `/normalize?q=` (+`hgvs_dup_del_mode`, `baseline_copies`, `copy_change`, `input_assembly`) | one VRS variation, "fully-justified", lifted to GRCh38, aligned to a priority transcript | **same as input**: protein → protein, c. → MANE transcript, g./gnomAD → genomic |
| `/to_vrs?q=` | every VRS variation the input could mean, no priority | same as input; `BRAF V600E` → 4 protein isoforms [M] |
| `/translate_from?variation=&fmt=` (`beacon`, `gnomad`, `hgvs`, `spdi`) | vrs-python `AlleleTranslator`, no transcript re-mapping | as given; accepts `c.…dup` that `/normalize` rejects [M] |
| `/gnomad_vcf_to_protein?q=` | GRCh38 VCF → MANE protein allele + gene | protein |
| `POST /translate_to`, `POST /vrs_allele_to_hgvs` | VRS → an expression | — |
| `/hgvs_to_copy_number_count`, `/hgvs_to_copy_number_change`, `POST /parsed_to_cn_var`, `POST /parsed_to_cx_var`, `/amplification_to_cx_var` | copy-number VRS | genomic |
| `/alignment_mapper/{p_to_c,c_to_g,p_to_g}` | **coordinates only**, e.g. `p_to_g NP_004324.2:600` → `NC_000007.14` 140753334–140753337 interbase [M] | a window, not an allele |
| `/feature_overlap` | MANE gene/CDS overlapping a GRCh38 range | — |
| `/translate_identifier` | SeqRepo alias lookup, e.g. `SQ.xBKO…` → `refseq:NM_000551.4` [M] | — |

[M] `curl https://normalize.cancervariants.org/variation/openapi.json` (99.5 KB, 16 paths).

- **There is no `to_canonical_variation` or Cat-VRS output** in 0.16.0 or on the hosted service [M: path
  list; D: `src/variation/`]. Catvar construction lives in metakb
  (`transformers/catvars.py::build_proteinsequenceconsequence_catvar`) [D].
- **Hosted version**: `"unknown"` in every response. The free-text `c.` form ("CCR5 c.554_585del")
  works on the hosted service, and that feature landed in 0.16.0 (#669, 2026-07-22), so the service is
  ≥ 0.16.0 [I]. vrs-python 2.3.1, so its ids are VRS 2.0.x [M].
- **Transport**: AWS API Gateway behind CloudFront. `HEAD` returns 403 `MissingAuthenticationToken`,
  `GET` returns 200 [M]. No terms page on the host, which serves the VICC landing page [M].

### 1.2 Input grammar (0.16.0)

Tokenizers [D: `src/variation/tokenizers/`]: gene symbol; protein substitution, deletion, delins,
insertion, reference-agree, frameshift (tokenized, but **no classifier or translator exists for it**);
cDNA substitution, deletion, delins, insertion, reference-agree; genomic substitution, deletion,
delins, insertion, **duplication** (plus the ambiguous-range del/dup forms); gnomAD VCF
(`chr-pos-ref-alt`); HGVS; and a "free text categorical" that matches **only the word `amplification`**.

| Input shape | Accepted? | Evidence |
|---|---|---|
| `GENE p.change` free text (`BRAF V600E`, `DICER1 Asp1709Glu`) | yes → protein allele | [M] |
| `GENE c.change` free text (`CCR5 c.554_585del`) | yes (0.16.0) → MANE transcript allele | [M] |
| RefSeq `c.` substitution, del, ins, delins | yes → MANE transcript allele | [M] |
| RefSeq `c.` **dup** (`NM_000551.4:c.374dup`, `c.210_213dup`, `c.210_213dupGCCC`) | **no**: "Unable to find classification" | [M]; no cDNA-dup classifier [D]; #281 (2022) wants inserts that are dups to be classified as dups |
| Genomic `g.` incl. dup (`NC_000003.12:g.10142057_10142060dup`) | yes → genomic | [M] |
| gnomAD VCF `4-87310240-T-TA` | yes → genomic, with `hgvs_dup_del_mode` forced to `allele` | [M], [D] `normalize.py` |
| GRCh37 VCF with `input_assembly=GRCh37` (`7-140453136-A-T`) | yes, lifted: returns `ga4gh:VA.Otc5ovrw…` at 140753335 | [M] |
| rsID (`rs72613567`, `rs77944059`, `rs333`, `rs113488022`) | **no**: "Unable to tokenize" | [M] |
| ClinVar / CAID ids | no tokenizer | [D] |
| Legacy `c.<N>ins<SEQ>` (`c.211insT`, `c.214insGCCC`, `NM_000551.3:c.386insAGA`) | **no**: "Unable to find classification" | [M] |
| Legacy intronic `IVS2+1G>A` | **no**: "Unable to tokenize" | [M] |
| Protein frameshift (`VHL P71fs`, `RUNX1 R135fs`) | **no** | [M]; #107 open since 2021-05-12 |
| Category words ("KRAS Mutation", "Exon 19 Deletion") | no, except `amplification` | [D] |

### 1.3 How it picks a transcript

- **Priority order** [D: `schemas/translation_response_schema.py::VrsSeqLocAcStatus`, "order when
  defining matters"]: MANE Select → MANE Plus Clinical → longest compatible remaining → GRCh38. The
  selection is cool-seq-tool's `ManeTranscript.get_mane_transcript(…, try_longest_compatible=True,
  ref=…)`, which needs UTA [D: `translators/translator.py` L200].
- **Tie-break when several candidates share a status**: sort by accession string and version,
  descending, and prefer the one whose accession equals the input's. The code's own comment: "Later on,
  we'll want to figure out a better way to do this." [D: `normalize.py::_get_priority_translation_result`].
- **The swap is silent** [M]:

  | Submitted | Answered on | Warning |
  |---|---|---|
  | `NM_000551.3:c.197_220del` | `NM_000551.4` (`SQ.xBKO…`), same id as `.4` input | none |
  | `NM_000579.3:c.554_585del` (CCR5-Δ32) | `NM_001394783.1` (`SQ.w3ep…`), today's CCR5 MANE Select | none |
  | `NM_004333.6:c.1799T>A` | `NM_004333.6`, already MANE | none |

- **Issue #672 reproduced** [M]. `/normalize?q=PPP6C Arg264Cys` gives `ga4gh:VA.qXcjEs7s…` at
  protein position 285 on `SQ.W8G3…`, while `/gnomad_vcf_to_protein?q=9-125149801-G-A` gives
  `ga4gh:VA.GBgHSEiI…` at 263. One variant gets two protein-layer ids depending on the endpoint. VarCat
  keys Cancer Hotspots on these ids [D: issue body].

### 1.4 The ambiguous cases our probes hit

| Case (our record) | variation-normalizer | Our protocol / enricher |
|---|---|---|
| **Legacy insertion**, two readings (1955 `c.211insT`) | refuses the legacy form. Both modern readings normalize and give **different** transcript ids (`8XdTju…` / `JqEiIy…`) and genomic ids equal to ours (`-ma5st…` / `rMf-X0…`) [M] | generates both readings, and a curated source settles 1955 (`c.211_212insT`, CA2501268513) |
| **Legacy insertion that is a dup** (2131 `c.214insGCCC`) | the `c.210_213dup` reading is **refused**, and `c.214_215insGCCC` works. The genomic dup works: `3-10142056-A-AGCCC` → `ga4gh:VA.f7OmsEth…` (RLE, repeatSubunitLength 4), identical to ours [M] | withheld; the source states the sequence is unknown |
| **Protein name → several nucleotide changes** (2196 `DICER1 D1709E`) | `14-95094125-A-T` and `A-C` both → `ga4gh:VA.eFBSGBC3…`, one **protein** id. The ambiguity is dissolved by moving up a layer, and no endpoint maps a protein name back to its nucleotide candidates [M] | R5: keeps both candidates, and ClinVar's citation attribution picks one |
| **Ref/alt inverted** (4968 `TP53 R72P`) | "Unable to translate TP53 R72P", with no reason. `P72R` normalizes [M] | R4: registry direction test, then publish the reference-identity allele CA178298 |
| **Substitution-shaped name for an indel** (1768 `VHL L129Q (c.386insAGA)`) | `VHL L129Q` → protein allele Leu129**Gln** (`Lc5giZ9E…`). A confident, well-formed answer for a missense the record does not describe [M] | §11(c): read as `p.Leu129delinsGlnMet` from the cDNA half |
| **Contradictory halves** (2459 `L178P (c.532C>T)`) | each half normalizes on its own (`0wm-jAdU…` protein; `ZWGe6Qi…` transcript). Nothing compares them [M] | R3: resolve both, adjudicate by literature |
| **Deletion in a repeat** (VHL `c.197_220del`, 24 nt) | RLE with `repeatSubunitLength: 24` over transcript 264–291. The same id for `.3` and `.4` input [M] | the registry 3′-shifts it to `c.198_221del`, and our §0 control shows one CAID |
| **Legacy exon numbering** (788 `CHEK2 IVS2+1G>A`) | untokenizable [M] | ClinVar OtherNames (rank 2) |

---

## 2. Run against our inputs (hosted `/normalize`, 2026-09-28)

All calls are `GET https://normalize.cancervariants.org/variation/normalize?q=<urlencoded>`, one per
second. Ours = `just_dna_enricher.vrs.VrsMinter().mint(chrom, start, ref, alt)` from the repo venv
(ga4gh.vrs 2.3.3; indels over the SeqRepo REST proxy) [M]. GKS_SURVEY = ids that survey recorded.

| Input | variation-normalizer | Layer | Ours | Match |
|---|---|---|---|---|
| `7-140753336-A-T` | `ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe` | GRCh38 | same (stdlib) | **yes**; also = GKS_SURVEY's VRS 2.0 id |
| `NC_000007.14:g.140753336A>T` | `…Otc5ovrw…` | GRCh38 | same | yes |
| `7-140453136-A-T` + `input_assembly=GRCh37` | `…Otc5ovrw…` | GRCh38 (lifted) | — | — |
| `BRAF V600E` | `ga4gh:VA.j4XnsLZcdzDIYa5pvvXM7t1wn9OITr0L` | NP_004324.2 | n/a (no protein layer) | — |
| `NM_004333.6:c.1799T>A` | `ga4gh:VA.W6xsV-aFm9yT2Bic5cFAV2j0rll6KK5R` | NM_004333.6 | n/a | — |
| `rs113488022`, `rs72613567`, `rs77944059`, `rs333` | "Unable to tokenize" | — | resolved via the Ensembl snapshot | refused |
| `4-87310240-T-TA` (ClinVar/caller spelling) | `ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7` (RLE len 2, unit 1) | GRCh38 | same | **yes**; = GKS_SURVEY / ClinVar-GKM |
| `4-87310241-A-AA` (our snapshot's spelling) | `…Jml7…` | GRCh38 | same | yes: one event |
| `2-166204470-GAAAC-G` | `ga4gh:VA.ks2GTWYOW0aKfGbJ2aeQUOZxOT_xC2ts` (RLE len 7, unit 4) | GRCh38 | same | **yes** |
| `2-166204471-AAACA-A` | `…ks2G…` | GRCh38 | same | yes: one event |
| `9-133257520-G-GC` (RM267, our snapshot) | `ga4gh:VA.Jwesa81jBuk4LSchvngeXwdYHS-lOoDV` | GRCh38 | same | yes |
| `9-133257521-T-TC` (RM267, ClinVar) | `ga4gh:VA.gMmj5gwZ40fKx1YdsSFoD7jz790cMQXN` | GRCh38 | same | yes: **two events on both sides** |
| `NM_000579.3:c.554_585del` (rs333) | `ga4gh:VA.Opc4-cG3wkCZ1z7H83uf-6C8Z7RvyfxF` (RLE, unit 32) | **NM_001394783.1** | — | **not compared**: transcript layer, and rsIDs are refused |
| `3-10142057-G-GT` / `3-10142058-C-CT` (1955 readings) | via transcript: `8XdTju…` / `JqEiIy…` | NM_000551.4 | `-ma5st…` / `rMf-X0…` | genomic side not queried by gnomAD string |
| `3-10142056-A-AGCCC` (2131 dup) | `ga4gh:VA.f7OmsEth_o5T9TFVkScg9ZaGbJmZIHny` | GRCh38 | same | yes |
| `3-10142061-T-TGCCC` (2131 ins) | `ga4gh:VA.F3VYGt8lkiY1wdiWx_IcNLqH4WmM0ecz` | GRCh38 | same | yes |

**Match rate on genomic input: 10 of 10 inputs (7 distinct alleles), byte-identical** [M].

**rs333 was not compared at the genomic level.** The tool cannot take the rsID, and the `c.` form lands
on a transcript. Fetching the 32-mer to force a genomic comparison was deliberately not done.

**RM304 reading.** No insertion here moves under VRS 2.1: `rs72613567` has repeat unit 1, so the
smallest and greatest factor coincide, and `rs77944059` is a deletion. Both tools are on 2.0.x today
[M/I]. The `<3.0` pin means the hosted service will move with vrs-python and say nothing [D/I].

---

## 3. variation-normalizer — licence, cadence, users

| | Value | Tag |
|---|---|---|
| Licence | MIT | [M] `gh api repos/cancervariants/variation-normalization` |
| Releases | 0.16.0 (2026-07-22), 0.15.5 (2026-04-09), 0.15.4 (03-16), 0.15.3 (03-09), 0.15.2 (01-02), 0.15.1 (2025-07-31): about 6 in 12 months | [M] |
| Commits since 2025-09-28 | 26; last push 2026-07-24 | [M] `git log` on a depth-200 clone |
| Open issues | 70 (open since 2021: #107 frameshifts, #176 ambiguous `BRAF V600E` should list all MANE transcripts) | [M] |
| Stars | 15 | [M] |
| Container | ghcr.io image published by CI since 2026-04-08 (#665) | [D] commit log |
| Declared dependents (`pyproject.toml`/`setup.cfg` code search only) | `cancervariants/metakb`, `cancervariants/evidence-normalization`, `clingen-data-model/clinvar-gk-python` (ClinVar-GKM), `GenomicMedLab/variation-normalizer-manuscript` | [M]; AnyVar not found **by this search**, which is not evidence it does not use it |

---

## 4. metakb — what it is

### 4.1 Versions

| Where | Version | Tag |
|---|---|---|
| PyPI | 1.1.0 (2022) | [D] GKS_SURVEY |
| Latest GitHub pre-release | `2.0.0-a0` (2025-06-16); `2.0.0-dev1` (2025-05-01) carries the data assets | [M] |
| `main` `server/pyproject.toml` | **2.0.0-a1**; 153 commits since 2025-09-28; last push 2026-09-23 | [M] |
| Open issues / licence | 58 / MIT | [M] |

### 4.2 Pipeline

| Stage | What | Tag |
|---|---|---|
| Harvest | **CIViC** (via civicpy's cache, `accepted` only), **MOA** (Molecular Oncology Almanac API), **cBioPortal** studies (added 2026-02), **FDA PODA** (GenomicMedLab pediatric oncology drug approvals JSON, 2026-02), **MCI** (NCH Molecular Characterization Initiative pilot) | [D] `harvesters/` |
| Transform | CIViC: civicpy's `CivicGksEvidence` / `CivicGksClinSigAssertion` → VA-Spec `Statement`, then a `CategoricalVariant` is rebuilt by normalizing the profile **name** | [D] `transformers/civic.py` |
| Name gate | `MP_NAME_PATTERN = (?P<gene>\w+)(?:\s+(?P<p_change>\w+))?(?:\s+(?P<c_change>\(?c\..*\)?))?`. Refused: any `c.` part ("cDNA variant … not yet supported … issue-225"), names ending in `fs`, names with `-` or `/`, and 35 keywords (`mutation`, `exon`, `deletion`, `loss`, `fusion`, `wild`, …). Anything yielding more than one constraint is refused | [D] |
| Normalize | variation-normalizer `normalize` on `"GENE p.change"`, then `build_proteinsequenceconsequence_catvar` or `build_copynumberchange_catvar`. Plus gene-, disease- and therapy-normalizer | [D] |
| Store | neo4j 5 | [D] `pyproject` |
| Query | FastAPI: `GET /api/search/statements?variation=&disease=&therapy=&gene=&statement_id=&start=&limit=`, `GET /api/service-info`, `GET /api/stats` | [D] `restapi/` |
| Pins | `ga4gh.vrs[extras]~=2.4.0-a1`, `ga4gh.cat_vrs~=0.8.0-a2`, `ga4gh.va_spec==0.5.0-a0`, `variation-normalizer~=0.15.4`, civicpy at a git commit | [D] |

### 4.3 What is reachable

| Route | Result | Tag |
|---|---|---|
| `search.cancervariants.org/api/…` | the v1 (2020) VICC meta-KB. `/openapi.json` answers an **Elasticsearch `index_not_found_exception`** | [M] |
| `dev-search.cancervariants.org/api/service-info` | 403 `Missing Authentication Token` | [M] |
| `metakb-dev-eb.us-east-2.elasticbeanstalk.com` (named in the repo) | no connection | [M] |
| **`2.0.0-dev1` release assets** | `civic_cdm_20250428.json.zip` (3.7 MB → 42.5 MB), `moa_cdm_20250428.json.zip` (0.47 MB → 9.9 MB) | [M] downloaded |
| MCI pilot release | `mci-gks-nov2025-v0.1.0-preprint.json.zip` (0.58 MB → 13.3 MB) | [M] downloaded, not profiled |

**No public metakb v2 API exists to query.** Every count below comes from the **2025-04-28 CIViC dump**.

### 4.4 What the 2025-04-28 CIViC dump holds [M]

| Measure | Count |
|---|---|
| Evidence statements | 2,549: therapeutic response 1,958, prognostic 455, diagnostic 136 |
| Assertions | 21 |
| Categorical variants | 975: **433** with one `DefiningAlleleConstraint`, **542** with none (`vicc_normalizer_failure`) |
| Statements whose subject has a constraint | 1,031 of 2,549 |
| Allele origin across statements | somatic 2,065; `na` 344; **rare_germline 72, common_germline 44**; unknown 24 |
| BRAF V600E (`civic.mpid:12`) | 95 statements: predictsSensitivityTo/supports 59, associatedWithWorseOutcomeFor/supports 16, predictsResistanceTo/supports 7, sensitivity/disputes 4, diagnostic inclusion 3, worse outcome/disputes 3 |
| MOA dump | 928 statements (therapeutic 713, prognostic 215), 438 catvars (164 constrained), **0 `variations`** |

**BRAF V600E's catvar members** include the GRCh38 genomic allele `ga4gh:VA.Otc5ovrw…`, **equal to our
id**, with the transcript allele `W6xsV…` and the protein constraint `j4XnsLZ…`, **equal to the hosted
normalizer's** [M]. The genomic member is *named* by a GRCh37 expression (`NC_000007.13:g.140453136A>T`)
while its location is on the GRCh38 accession (`SQ.F-LrLMe…`, start 140753335) [M]. The KIT member
`ga4gh:VA.UQJIH…` is named `NC_000004.11:…` (GRCh37), and its accession was not resolved.

Unconstrained examples, in dump order: `ERBB2 Amplification`, `KRAS Mutation`, `DNMT3A R882`,
`BRAF V600`, `FLT3 ITD`, `EGFR Exon 19 Deletion`, `PTEN Loss`, `KRAS G12/G13`, `IDH1 R132` [M].

### 4.5 CIViC profiles: what is dropped, and the NOT case

Scope rules [D: civicpy `civic.py::_is_valid_for_gks_json`; `exports/civic_gks_record.py`]:

- the evidence type must be DIAGNOSTIC, PREDICTIVE or PROGNOSTIC, so **PREDISPOSING, ONCOGENIC and
  FUNCTIONAL are skipped**;
- `len(molecular_profile.variants) > 1` → "complex molecular profile. Skipping";
- the variant must be a `GeneVariant` (fusions and factors are skipped);
- mappings and members are read from `molecular_profile.variants[0]`.

Local CIViC release 01-Sep-2026 (`data/caches/civic/MolecularProfileSummaries.tsv`) [M]: 1,977
profiles with variants, of which **216 are multi-variant**. Names: `AND` in 147, `OR` in 73, `NOT` in 2.
The two NOT profiles:

| Profile | `variant_ids` | civicpy gate | metakb dump |
|---|---|---|---|
| 4353 `NOT KIT D816V` | `65` (one) | **passes** | catvar `civic.mpid:4353` with `DefiningAlleleConstraint` → `ga4gh:VA.nhiDwIq1…`, **the same allele as `civic.mpid:65` `KIT D816V`**. Members are KIT D816V's alleles, and its mappings include `CA123513` and `rs121913507`. The NOT survives only in `name` [M] |
| 5696 `MET Amplification AND NOT KRAS Mutation` | `270, 336` | skipped (complex) | absent |

So evidence **11158** (Predictive, Sensitivity/Response, imatinib, systemic mastocytosis, Somatic)
reaches the dump as `predictsSensitivityTo` over a subject whose only machine-readable content is
"KIT D816V present" [M]. Today's metakb name regex parses `NOT KIT D816V` as gene=`NOT`,
p_change=`KIT`, so a fresh transform would probably fail to normalize it rather than invert it [I]. The
civicpy members and mappings from `variants[0]` would still be attached [I].

**Our build on the same record** [M]: evidence 11158 is `Somatic`, not in our `civic.parquet`, and
`release.json` counts `no_variant_record: 0`, `combination_profile: 0`, `non_germline_origin: 4093`.
It is dropped at the origin filter before any profile question arises. A **germline** single-variant NOT
profile would reach `by_profile.get(profile_id)`, miss (it is not the variant's
`single_variant_molecular_profile_id`), and be counted as `no_variant_record`, which the code comment
calls "a dangling reference". That is the wrong reason, but it is a drop, not an inversion [I: code
read of `civic_build.py` L598–606; no instance exists in the current release].

### 4.6 Licences of the harmonized data

| Source | Licence | Tag |
|---|---|---|
| metakb code | MIT | [M] |
| CIViC | CC0 | [D] metakb `docs/source/source_licenses.rst`; our `release.json` `licence: CC0-1.0` [M] |
| MOA | **ODbL 1.0** for the database, contents GPL-2.0 | [D] same page |
| FDA PODA repo | **no licence** (`license: null`) | [M] `gh api` |
| MCI pilot | code MIT; data terms not established | [M]/— |
| cBioPortal studies | not listed by metakb; per study | [D] absence |

---

## 5. Mapping onto our problems

| Our problem | variation-normalizer | metakb |
|---|---|---|
| **Identity from a name** (CIVIC_IDENTITY_PROTOCOL) | **Partly.** It gives a VRS id for `GENE p.X`, `GENE c.X`, modern `c.` and `g.`, but the id sits on the protein or transcript layer. It gives no GRCh38 VCF form, no CAID and no rsID. It refuses the legacy, frameshift, `c.` dup, IVS and rsID shapes, which are exactly the residue our protocol exists for, and it answers 1768 wrongly [M] | **No.** It consumes the normalizer. The 542 unconstrained catvars are its own residue |
| **RM267** (wrong-event −1 anchor) | Would *detect*, not repair: both spellings of `rs8176719` mint two ids, as ours do [M]. Its only independence is its sequence store | No |
| **RM270** (one event, two spellings) | Confirms our ids on both RM270 pairs [M]. Adds nothing we do not already mint | No |
| **RM304** (VRS version drift) | **Makes it worse if used as a witness.** No version on the wire, and the pin admits 2.4 [M/D] | Already on `ga4gh.vrs 2.4.0a1` [D]; its ids will move first |
| **RM305** (independent placement witness) | Weaker than ClinVar-GKM: same algorithm, *live* rather than offline, and no stated terms | No |
| **RM28** (meta-conclusions, CIViC multi-variant profiles) | No: it tokenizes only `amplification` among categories | **Not solved.** Multi-variant profiles are dropped upstream. Class labels are ids with no constraint. The one single-variant negation is emitted as its positive [M] |
| **Therapeutic-response rows** | — | Somatic-oncology `VariantTherapeuticResponseProposition`; 116 germline statements in the dump. Its PGx/germline overlap with our tables is small [M]. Per-genotype grain is absent (GKS_SURVEY §4) |

### 5.1 Where ours is better or worse, on the same inputs

| Axis | Ours | Theirs | Evidence |
|---|---|---|---|
| Genomic VRS ids | equal | equal | 7 alleles / 10 inputs [M] |
| Output layer for a name | GRCh38 VCF + CAID + rsID | protein or transcript VRS | §2 [M] |
| A protein name with several nucleotide routes | keeps every candidate (R5) | collapses to one protein id | D1709E [M] |
| Legacy `ins`, frameshift, IVS, rsID | handled by the protocol (35/43 resolved, 2 withheld) | refused | §1.4 [M] |
| Reason on a refusal | six distinct registry outcomes | "Unable to translate / classify / tokenize" | [M] |
| Silent transcript substitution | submits the source's frame and proves equivalence (§0 control) | swaps to MANE with no warning | [M] |
| Protein-layer id stability | n/a (none minted) | #672: two ids for one variant across endpoints | [M] |
| Throughput / automation | minutes per hard record, hand judgement in §11 | ~0.5 s per query, no judgement | [M] |
| Copy-number and amplification VRS | none | `CopyNumberChange`/`Count` endpoints | [D] |
| Multi-isoform protein answers | — | `/to_vrs` lists every isoform (4 for BRAF V600E) | [M] |

---

## 6. Options for using each, with cost

Costs are the surveyor's estimates [I]. Tiers follow the CLAUDE.md tier rules.

| # | Option | Tier | Dependency weight | Cost | Charter tension (stated, not decided) |
|---|---|---|---|---|---|
| A | **Hosted `/normalize` as a check** in the enricher: send the gnomAD-style spelling of each resolved indel and compare ids | enricher | 0 packages (httpx present) | 2–3 days: client + URL-keyed cache + `@client-exception-contract` legs + `--offline` skip + a `SourceRow` + tests | Duplicates `VrsMinter` (same library, same rule), so it witnesses only the sequence store. There are no stated terms or rate limit (`@no-named-licence`). The version is unannounced (RM304). It is a live dependency where RM305 wants an offline one |
| B | **Hosted `/normalize` or `/to_vrs` as a name → protein-id hint** in drafting (CIViC `GENE p.X`) | enricher | 0 | 1–2 days | A protein-layer id does not reach `variant_key`. A hint may not fill a cell a Class-2 check cross-examines (`@hint-redundancy-bearing`). 1768 shows a confident wrong answer |
| C | **Local variation-normalizer** | enricher optional extra, or not here | 68 pkgs / 421 MB + UTA Postgres (CC BY-SA 4.0) + SeqRepo 13.5 GB + gene-normalizer DB | 1–2 days to stand up; ongoing service upkeep | Service stack against "builder in polars, runtime in duckdb" and `--offline` provisioning; UTA's share-alike |
| D | **Read metakb's published dump** (civic/moa `_cdm_` JSON) | enricher builder | 0 (json + polars) | ~1 day | Pre-release asset, 2025-04-28, about 17 months stale, with no currency channel. MOA is ODbL (share-alike on a derived database), so the lane's terms are mixed (`@a-hosts-terms-are-not-its-contents-terms`). The NOT inversion would be imported as data. Mostly somatic |
| E | **Local metakb** | not here | neo4j + four normalizers + UTA + SeqRepo + DynamoDB | days, plus operations | Orchestration-class. Non-goals keep that out of format/compiler, and the enricher house rules bend |
| F | **Copy their rules, not their code**: the MANE priority order + tie-break (§1.3), and the name-gate keyword list as a class-label pre-classifier for protocol §5 | docs + enricher | 0 | hours (docs); ~0.5 day for a classifier with tests | The keyword list is a blunt instrument (`DNMT3A R882` passes their regex and fails normalization). Their tie-break is admitted by its authors to be a placeholder |
| G | **Take the NOT KIT D816V case as a test fixture** for RM28 / RM174 (a single-variant profile whose name negates it) | enricher tests | 0 | 1–2 hours | None; a test pins our drop reason (`no_variant_record` is the wrong word for it) |

---

## 7. Could not be established

- The hosted variation-normalizer's exact version (it reports `"unknown"`; ≥ 0.16.0 is inferred).
- The hosted service's rate limit, SLA or terms of use (none published on the host).
- metakb v2 query behaviour on a live instance (no public one found). BRAF V600E and multi-variant
  answers come from the 2025-04-28 dump only.
- The MCI dump's contents (downloaded, not profiled) and its data licence.
- The genomic-level comparison for `rs333` (see §2).
- The accession behind the KIT member `ga4gh:VA.UQJIH…`.
- Whether AnyVar or other tools use variation-normalizer outside `pyproject.toml`/`setup.cfg`
  declarations.

---

## 8. The three most useful things to take, ranked

| Rank | Take | Why | Cost | Dependency |
|---|---|---|---|---|
| 1 | **The NOT KIT D816V case, as a fixture and a named RM28 hazard** (option G) | A measured instance of a published GKS pipeline emitting a negation as its positive. RM28 needs this failure mode on file before any profile structure is designed, and our own drop reason for it is misworded | 1–2 hours | none |
| 2 | **The hosted `/to_vrs` protein-isoform listing, as a free cross-check for protocol step 3** (a restricted option B): confirm that a `GENE p.X` name's reference residue exists on some isoform before the local calculator runs | Isoform enumeration is the RUNX1 (804) problem, and `/to_vrs` answers it in one call. Used as a finding, never as a fill | ~1 day in the enricher, or zero if kept as a manual step in IDENTITY_FROM_A_NAME | none (httpx); live service with no stated terms |
| 3 | **Their MANE priority order and its admitted tie-break gap, cited in IDENTITY_FROM_A_NAME §3b** (option F, docs half) | Our §3b says "MANE is the default, not the answer". Their order (Select → Plus Clinical → longest compatible → GRCh38) plus the silent-swap evidence in §1.3 is the precedent and the counter-example in one place | 2–3 hours | none |

**Not taken, on the measurements:** a hosted or local variation-normalizer as a VRS witness (it
duplicates our minter and hides its version), and metakb's data (stale, somatic, mixed licence, and it
carries a semantic inversion).

**Not to be confused with PubMind's "Variant Normalizer (Beta)"** (`pubmind.wglab.org/variant_normalizer`,
added 2026-09-28). That tool shares the name and nothing else: it maps `gene:variant` positions with
pyensembl against every protein-coding isoform whose reference base matches, and mints no id. It is
read in [PUBMIND_ASSESSMENT.md](../PUBMIND_ASSESSMENT.md#how-pubmind-places-a-variant-read-from-its-code-2026-09-28),
because it is the step that placed every coordinate in our PubMind lane.
