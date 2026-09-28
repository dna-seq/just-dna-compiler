# GA4GH GKS / GKM survey for just-dna-format — 2026-09-28

Scope: finding, not deciding. Every claim carries a tag:
**[M]** measured (command run in this session), **[D]** read in primary docs/source, **[I]** inferred.
Package weights were measured in throwaway venvs in the surveying session's scratchpad, which is not
preserved; nothing in the repo was edited during the survey.

**Naming first.** The workstream rebranded in 2026: the *schema set* is now **GKM (Genomic Knowledge
Models)**, `gks-core` is **`gkm-core`**, the metaschema processor is `ga4gh.gkm.metaschema`; "GKS" stays
the name of the GA4GH *workstream* [D: ga4gh/vrs PR #708 "Rebrand GKS → GKM" in the 2.1.0 release
notes; `gh api repos/ga4gh/gks-core` resolves to `gkm-core`; clinvar-gkm PR #89/#92].

---

## 0. Headline findings (read these if nothing else)

1. **Our core grain has no GKS counterpart.** `VariantRow` is keyed `(variant_key, genotype)`;
   `PharmVariantRow` is per genotype; `DiplotypeRow` is per diplotype. VRS 2.x has **no Genotype**
   (the 1.3 `Genotype`/`Haplotype`/`VariationSet` classes are absent from the 2.x class list;
   `Haplotype` became the cis-only `CisPhasedBlock`; in the 2.1.0 docs `Genotype` appears only in the
   1.3 release notes) and no VA-Spec schema carries a zygosity or genotype field (pathogenicity
   qualifiers are `geneContext`, `alleleOrigin`, `penetrance`, `modeOfInheritance`) [M: `gh api
   repos/ga4gh/vrs/git/trees/2.1.0` json class list vs `vrs-source.yaml@1.3.0`; grep of the 2.1.0 docs;
   D: VRS 2.0 release notes "renames Haplotype to CisPhasedBlock"; M: grep for
   `zygos|genotype|allelicState` over **every** VA-Spec JSON schema at 1.0.1 (30 files) and at the
   1.1.0 ballot (39 files) → zero hits]. Any GKS
   export of our annotations is lossy at the genotype axis.
2. **VRS 2.1.0 (released 2026-09-01) changed normalization, and vrs-python has not caught up.** The
   2.1 minor revises ambiguous-insertion normalization to pick the **smallest** repeat-unit factor
   (was greatest), which changes the digest of affected trial-use Alleles [D:
   https://vrs.ga4gh.org/en/2.1.1-ballot.2026-09/releases/2.1.html]. Both `ga4gh.vrs` 2.3.3 (our pin)
   and 2.4.0a4 (latest alpha, "update models to … vrs 2.1.0") still iterate `_factor_gen`
   **descending**, first valid cycle wins [M: read `ga4gh/vrs/normalize.py` in both venvs]; the change
   is open as vrs-python issue #637 "Add support for switching RLE subunit between largest and
   smallest" [M: `gh api search/issues`]. Everyone we compare against today (our enricher, ClinVar-GKM's
   `vrs_output_2_0_1.schema.json`, gnomAD per `docs/SCHEMAS.md` ground-truth test) is on **2.0.x
   digests**. 270,161 of ClinVar-GKM's 4,460,884 alleles are `ReferenceLengthExpression` — the class
   where a subset (insertions with a composite repeat length) would move [M: duckdb over
   `allele.parquet`; I: which subset exactly moves was not computed]. **RM270's candidate 4 (carry
   `vrs_id` onto parquets) inherits this pending id move.**
3. **A `ga4gh:VA.` string does not say which VRS it is.** For `chr7:140753336 A>T` (BRAF V600E) three
   ids exist: our/VRS 2.0 `ga4gh:VA.Otc5ovrw906Ack087o1fhegB4jDRqCAe`, vrs-python's VRS 1.3
   back-computation `ga4gh:VA.fZiBjQEolbkL0AxjoTZf4SOkFy9J0ebU`, and the ClinGen Allele Registry's
   `/vrAllele` answer `ga4gh:VA.HaPTmn-rrjRoZnIVw1I4AZPa6YHa2ojh` (a VRS 1.x-era shape:
   `SimpleInterval`, `SequenceState`, `sequence_id`; the exact minor is not established) [M: all three computed/fetched this session]. CAR's VRS ids are not
   joinable to ours nor to a 1.3 back-computation; **the CAID is the only hop to CAR**. Nothing in the
   repo records the VRS version behind a `vrs_id` [M: `grep -rn -i 'vrs_version\|VRS_VERSION'` over
   `schema/`, `enricher/`, `docs/SCHEMAS.md` → no hits].
4. **ClinVar-GKM's `allele.parquet` is a 1.09 GB, CC0, offline VRS oracle** — 4.46 M alleles, each
   with `spdi`, `hgvs.g` and `gnomad` (VCF-style) expressions beside its VRS 2.0 id. It contains
   **exactly** the two RLE ids RM270 minted for `rs72613567` (`ga4gh:VA.Jml7…`, `4-87310240-T-TA`) and
   `rs77944059` (`ga4gh:VA.ks2G…`, `2-166204470-GAAAC-G`), and our stdlib SNV minter matches its ids
   byte-for-byte on the two rows sampled [M]. Its value to us is as an **independent placement witness**
   for RM267/RM270/RM292, not as a replacement for the ClinVar VCF lane.
5. **The stable Python packages embed last-generation specs.** `ga4gh.vrs 2.3.3 → VRS 2.0.1`,
   `ga4gh.cat_vrs 0.7.2 → Cat-VRS 1.0.0`, `ga4gh.va_spec 0.4.4 → VA-Spec 1.0.1` [M: `*_VERSION`
   constants in the installed packages]. The newer line is alpha-only on PyPI: `ga4gh.vrs 2.4.0a4 →
   VRS 2.1.0`, `ga4gh.cat_vrs 0.8.0a4 → Cat-VRS 1.1.0`, `ga4gh.va_spec 0.5.0a5 →
   VA-Spec 1.1.0-snapshot.2026-06.1` (not yet the 2026-09 ballot) [M: same constants in a fourth venv]. Adding the
   Cat-VRS + VA-Spec models on top of what the enricher already carries costs **2 packages, ~144 KB**
   [M].
6. **VA-Spec 1.1 (ballot 2026-09) is backwards-incompatible at trial use**: `EvidenceLine` folded into
   `Statement`, `Therapeutic`→`Therapy`, `ClinicalVariantProposition`→`GeneticContextVariantProposition`,
   `CohortAlleleFrequencyStudyResult.focusAlleleFrequency`→`alleleFrequency` etc. [D: va-spec release
   `1.1.0-ballot.2026-09.1` notes]. Anything mapped to 1.0.1 now is remapped at 1.1.
7. **Boolean composition of categorical variants is an open, unmerged draft** (Cat-VRS PR #248
   `CompositeCategoricalVariant` + `CategoricalVariantCriterion`, AND/OR + `presence: present|absent`,
   **no phase**). Cat-VRS `CategoricalVariant` has **no computed digest** — ids are system-assigned
   (`clinvar:NNN`, `civic.mpid:NNN`). See §6 for RM28.
8. **Exon coordinates for AlphaGenome need no UTA and no SeqRepo.** The MANE Ensembl GTF (8.6 MB gz)
   carries 204,815 exons over 19,437 MANE transcripts [M]; the repo already builds a MANE lane.
   cool-seq-tool's exon mapper needs UTA (Postgres, CC BY-SA 4.0) on every path [M: read
   `exon_genomic_coords.py`]. See §5.

---

## 1. Specifications

| Spec | Latest stable | Latest pre-release | Licence | What is new / relevant | Source |
|---|---|---|---|---|---|
| **VRS** | **2.1.0** (2026-09-01); 2.0.1 (2025-03-20) | 2.1.1-ballot.2026-09.1 (2026-09-16) | Apache-2.0 | 2.1 **minor**: smallest-factor RLE normalization (digest-moving). 2.1 patch: `RelativeAllele`, `RelativeSequenceLocation`, `SequenceOffsetLocation` (**draft**, intronic positions). 2.1.1: metaschema rename, abstract classes `sealed`; no data-model change. **There is no VRS 2.2** — the task's "2.1/2.2" premise does not hold [M: release list]. Adjacency/copy number/derivative molecules came with **2.0.0** ("supports structural variation"), not 2.1 | [M] `gh api repos/ga4gh/vrs/releases`; [D] https://vrs.ga4gh.org/en/2.1.1-ballot.2026-09/releases/2.1.html |
| VRS class maturity @2.1.0 | `Allele`, `CisPhasedBlock`, `Adjacency`, `CopyNumberCount` = **trial use**; `CopyNumberChange`, `DerivativeMolecule`, `Terminus`, `RelativeAllele` = **draft**. Digest prefixes: VA, RA, CPB, CN, CX, SL, RSL | | | No `Genotype`, `Haplotype`, `VariationSet` in 2.x (present in 1.3 source) | [M] `schema/vrs/json/*@2.1.0` `maturity` field; `vrs-source.yaml` grep for `prefix:` |
| **Cat-VRS** | **1.1.0** (2026-09-01); 1.0.0 (2025-06-11) | 1.1.1-ballot.2026-09.1 | Apache-2.0 | Constraint subtypes (exact names @1.1.0): `DefiningAlleleConstraint` (trial use), `DefiningLocationConstraint` (trial use), `CopyCountConstraint` (trial use), `CopyChangeConstraint` (draft), `FeatureContextConstraint` (draft), `FunctionConstraint` (draft), `AdjacencyConstraint` (draft). Recipes: `CanonicalAllele`, `ProteinSequenceConsequence` (trial use); `CategoricalCnv`, `FunctionVariant`, `GeneFusion` (draft). `CategoricalCnv` = exactly one `DefiningLocationConstraint` + one of `CopyChange`/`CopyCount` | [M] `gh api repos/ga4gh/cat-vrs/contents/schema/cat-vrs/json/*?ref=1.1.0` |
| **VA-Spec** | **1.0.1** (2025-07-23) | 1.1.0-ballot.2026-09.1 (2026-09-16) | Apache-2.0 | See profile table below | [M] releases; tree listings at both tags |
| **gkm-core** (ex gks-core) | **1.2.0** (2026-08-31) | 1.3.0-ballot.2026-09.1 | Apache-2.0 | `MappableConcept`, `ConceptSet`, `Coding`, `ConceptMapping`, `Extension`, `Entity`/`Element`. 1.3 adds optional `ConceptSet.conceptSetType` | [M] releases |
| **refget Sequences** | v2.0 (approved 2024) | — | — | Our `REFGET_GRCh38` constants are refget accessions | [D] https://ga4gh.github.io/refget/ |
| **refget Sequence Collections (seqcol)** | v1.0 (approved 2025) | — | — | A content digest for a whole assembly — the only GKS-adjacent thing that could give `genome_build` a digest rather than a label [I] | [D] same page |
| VCF VRS annotation | `vrs-annotate` CLI ships in `ga4gh.vrs[extras]` (`ga4gh/vrs/extras/annotator/vcf.py`) | | Apache-2.0 | Needs the `[extras]` tree (46 pkgs, 172 MB, local SeqRepo) | [M] installed venv |
| Phenopackets ↔ VRS 2 | **not established** | | | Not checked this session | — |

### VA-Spec profiles (what exists, at which maturity)

| Profile / class | 1.0.1 | 1.1.0 ballot | Our nearest table |
|---|---|---|---|
| `VariantPathogenicityProposition` (+ ACMG-2015 statement/evidence-line profile) | trial use | trial use (renamed fields) | `variants.csv` `clin_sig`/`pathogenic`; `clinical_assertions.csv` |
| `VariantOncogenicityProposition` (+ CCV-2022) | yes | yes | none (no somatic scope) |
| `VariantTherapeuticResponseProposition` (+ AAC-2017) | yes | trial use — **"response of a neoplasm"** | `pharm_variants.csv` only loosely: germline PGx is out of its stated scope |
| `VariantDiagnosticProposition`, `VariantPrognosticProposition` | yes | yes | none |
| `CohortAlleleFrequencyStudyResult` | yes | trial use; `focusCount`, `locusCount`, `alleleFrequency`, `cohort`, `subCohortFrequency` | `frequencies.csv` |
| `ExperimentalVariantFunctionalImpact{Proposition,StudyResult}` (the AVE/MAVE profile) | yes | trial use; `functionalImpactScore` | none (no assay table) |
| `TumorVariantFrequencyStudyResult` | yes | yes | none |
| `ComputationalVariantFunctionalImpactAnalysisResult` | — | **draft (new)**: `focus`, `transcriptVariationContext`, `impactScore`, `impactScoreType`, `categoricalImpact`, `impactedFeatureType`, `impactedFeature`, `sourceDataSet` | RM23 predictions, AlphaGenome AVI |
| `VariantMolecularConsequenceProposition` | — | **draft (new)**, `transcriptVariationContextQualifier`, `proteinVariationContextQualifier`, `geneContextQualifier` | RM236 consequence |
| `GeneDiseaseValidityProposition` | — | **draft (new)**, `modeOfInheritanceQualifier` | `gene_validity.csv` |
| `VariantClinicalSignificanceProposition` | — | draft (new) | `clin_sig` |
| `DataItem` | — | draft (new) | — |
| **PGx / star allele / diplotype profile** | none | none | `haplotypes.csv`, `diplotypes.csv`, `allele_function.csv`, `activity_phenotype.csv` |
| **GWAS / polygenic profile** | none | none | `gwas_effects.csv`, `pgs.csv` |

[M] `gh api repos/ga4gh/va-spec/git/trees/<tag>?recursive=1` and per-class `maturity`/`properties`;
[M] va-spec issue search for "pharmacogen" returned nothing; "GWAS"/"polygenic" hits are old open
scope issues (#25, #3, #246) with no profile.

---

## 2. Implementations and services — measured weight

Installed each into its own `uv venv` (Python 3.12) under `scratchpad/venvs/`. "Pkgs" = `uv pip list`
count; size = `du -sm site-packages`. `[extras]`-pulling packages fail to build on this host because
`hgvs` → `psycopg2` needs `pg_config`; re-installed with `psycopg2` overridden to `psycopg2-binary`
(that failure is itself a cost: a system libpq-dev, or an override) [M].

| Package | PyPI stable (latest pre) | Spec embedded | Licence | Pkgs | Size | Needs at runtime | Notes |
|---|---|---|---|---|---|---|---|
| `ga4gh.vrs` (core) — **already an enricher dep** | 2.3.3 (2.4.0a4) | VRS 2.0.1 | Apache-2.0 | 14 | 11 MB | seqrepo REST for indels (as the enricher does) | pydantic, bioutils, requests, canonicaljson |
| `ga4gh.vrs[extras]` | 2.3.3 | 2.0.1 | Apache-2.0 | 46 | 172 MB | local SeqRepo (13.5 GB), UTA for HGVS | pysam, hgvs, psycopg2, ipython |
| `ga4gh.cat_vrs` | 0.7.2 (0.8.0a4) | Cat-VRS 1.0.0 | Apache-2.0 | 15 | 11 MB | nothing | **+1 pkg, 28 KB over core vrs** |
| `ga4gh.va_spec` | 0.4.4 (0.5.0a5) | VA-Spec 1.0.1 | Apache-2.0 | 16 | 12 MB | nothing | **+1 pkg, 116 KB over cat_vrs**; pins `cat_vrs~=0.7.1` |
| `cool-seq-tool` | 0.17.0 | — | MIT | 53 | 309 MB | **UTA Postgres + local SeqRepo**; MANE files via `wags-tails` (auto-download from NCBI) | polars (172 MB runtime), boto3, psycopg, pysam, ipython; bundles a 24 MB `transcript_mapping.tsv` (BioMart-style Ensembl gene/transcript/protein + MANE RefSeq columns [I from its header]) |
| `gene-normalizer` | 0.11.5 | — | MIT | 30 | 46 MB | DynamoDB or Postgres loaded by its ETL | fastapi, uvicorn, boto3 |
| `variation-normalizer` | 0.16.0 | — | MIT | 68 | 421 MB | UTA + SeqRepo + gene-normalizer DB | pulls `ga4gh.vrs[extras]`; accepts HGVS, "BRAF V600E", gnomAD-VCF strings |
| `anyvar` | 1.0.0 (1.1.0.dev0) | — | Apache-2.0 | 80 | 259 MB | SeqRepo; UTA for HGVS; a SQL store | snowflake-sqlalchemy, sqlalchemy, fastapi, pysam, hgvs. Registration/lookup server around the same `ga4gh.vrs` normalizer |
| `metakb` | 1.1.0 on PyPI (stale; repo at 2.0.0-a0) | — | MIT | not installed | — | neo4j + all four normalizers + UTA + SeqRepo | server `pyproject` pins `ga4gh.vrs[extras]~=2.4.0-a1`, `cat_vrs~=0.8.0-a2`, `va_spec==0.5.0-a0` |
| disease-normalizer / thera-py | 0.13.1 / 0.13.0 | — | MIT | not installed | — | DynamoDB/Postgres | same FastAPI + boto3 shape [D: PyPI requires_dist] |
| `biocommons.seqrepo` | 0.6.11 | — | Apache-2.0 | (inside cool-seq-tool) | — | snapshot **13.5 GB** (2024-12-20), ~8 GB first snapshot per README | rsync required [D: seqrepo README] |
| **UTA** | `uta_20241220` | — | **CC BY-SA 4.0** (per `meta` table row shown in README) | — | Docker image **174 MB** compressed [M: Docker Hub API] | Postgres; dump `uta_20241220.pgd.gz` | **dump size not established**: `dl.biocommons.org` answers a human-verification page to curl [M] — an automation hazard for a builder |

Sources: [M] `curl https://pypi.org/pypi/<pkg>/json`, `gh api repos/.../releases`, the venvs; [D]
`github.com/biocommons/uta` README; `github.com/biocommons/biocommons.seqrepo` README.

### cool-seq-tool: what the exon mapping actually needs [M: read installed source]

| Capability | Module | Local requirement |
|---|---|---|
| genomic ↔ transcript segment / exon number (`genomic_to_tx_segment`, `tx_segment_to_genomic`) | `mappers/exon_genomic_coords.py` | **UTA on every path** (`self.uta_db.repository()` at ~10 call sites) + SeqRepo (`chromosome_to_acs`, `translate_identifier`) |
| MANE transcript selection | `mappers/mane_transcript.py`, `sources/mane_transcript_mappings.py` | MANE summary file (`MANE_SUMMARY_PATH` or `wags-tails` download) + UTA |
| gene / CDS overlap for a region | `mappers/feature_overlap.py` | **MANE RefSeq genomic GFF + polars only**; SeqRepo only to translate an identifier when the input is a VRS location |
| liftover | `mappers/liftover.py` | chain files via env |

Default UTA URL is `postgresql://anonymous@localhost:5432/uta?…uta_20241220` [M]. So everything cool-seq-tool
does with *exons* is UTA; the gene/CDS overlap it does from MANE alone is something a polars read of the
same GFF reproduces without the library [I].

---

## 3. Data already published in GKS form

| Publisher | What | Spec version | Distribution / size | Cadence | Licence | Status |
|---|---|---|---|---|---|---|
| **ClinVar-GKM** (ClinGen; `clingen-data-model/clinvar-gkm`, formerly clinvar-gks) | All ClinVar variations as Cat-VRS `CategoricalVariant` (`CanonicalAllele`, `CategoricalCnvChange`, `CategoricalCnvCount`, or constraint-less `ClinvarNonConstrainedVariant` for haplotypes/genotypes/compound hets); VRS `Allele`/`CopyNumberCount`/`CopyNumberChange`; SCV/RCV/VCV VA-Spec statements; conditions; genes | VRS 2.0.1 output schema; custom `Clinvar*Proposition` classes (incl. `ClinvarDrugResponseProposition`, `ClinvarRiskFactorProposition`) | Cloudflare R2 `pub-f0ad0e0dac0345408dcc95bda20beb42.r2.dev`. Monthly full JSON **4.76 GB** gz; typed parquet, 20 sections, **13.4 GB** total (`variation` 4.54 GB, `scv` 2.95 GB, `varcond-proposition` 1.50 GB, **`allele` 1.09 GB**, `location` 0.60 GB); weekly delta **3.5 MB** + `manifest.json` | "weekly delta, monthly full". Observed: latest delta `release: 2026-08-22`, Last-Modified 2026-08-26 — **~5 weeks old on 2026-09-28** | **CC0-1.0** (code and data) | **1.0-rc3** (2026-08-26); a breaking section split (`proposition` → four `var*-proposition`) landed mid-RC |
| **CIViC** | `civicpy.exports.civic_gks_record`: assertions as VA-Spec statements; molecular profile → `CategoricalVariant` id `civic.mpid:N`, mappings read from `molecular_profile.variants[0]` | via `ga4gh.cat_vrs`, `ga4gh.va_spec` | produced by civicpy 5.4.0, not a bulk dump | on demand | CIViC data CC0 (recalled, unprobed) | code exists; no published GKS bundle found |
| **metakb** (VICC) | CIViC + MOA harmonized into VA-Spec | VA-Spec 0.5.0a0 python | web service + neo4j | — | MIT (code) | 2.0.0-a0; **skips any CIViC MP whose name is not `GENE p.change`, and any that normalizes to >1 constraint** |
| **MaveDB** | 3,442,148 mapped variants [M]; VRS alleles; VA-Spec `study-result`, `functional-statement`, `pathogenicity-statement` per mapped variant and per score set (streaming) | VRS 2.0 / VA-Spec (version per API) | REST `api.mavedb.org` (v2026.2.7.3) | continuous | **per score set**: CC0, CC BY 4.0, CC BY-SA 4.0, **CC BY-NC-SA 4.0**, "Other" [M: `/api/v1/licenses/`] | production |
| **gnomAD** | VRS allele ids in API / v4.1 VCF | the repo verified SNV ids equal to the live API (`docs/SCHEMAS.md` § Allele identity) | — | — | — | already consumed (`frequencies.csv.vrs_id`) |
| **ClinGen Allele Registry** | `/vrAllele?hgvs=` returns a **VRS 1.x-era** object; CA records carry no VRS id field | VRS 1.x shape (minor not established) | REST | — | — | ids not joinable to VRS 2 (headline 3) |
| ClinGen LDH / Evidence Repository | LDH states VA-Spec 1.0 as its primary GKS dependency | VA-Spec 1.0 | REST | — | — | [D: search result for `clingen-data-model/svcv4-model`; LDH about page]. Not probed |
| ClinPGx / PharmGKB / CPIC | **nothing found in GKS form** | — | — | — | — | Cat-VRS star-allele recipe is only a discussion (#243, progress step 1 unchecked) |
| GWAS Catalog / PGS Catalog | **nothing found** | — | — | — | — | — |

Sources: [M] clinvar-gkm README, `docs/data-access/download.md`, `docs/pipeline/vrs-processing.md`,
releases; HEAD requests against R2; duckdb `parquet_schema`/`count(*)` over R2; MaveDB OpenAPI;
civicpy source at `griffithlab/civicpy`; metakb `server/src/metakb/transformers/civic.py`.

ClinVar-GKM's `variation.parquet` also carries, per HGVS expression, `molecularConsequence` (SO
`code`/`system`/`name`) with `maneSelect`/`manePlus` flags [M: parquet schema] — ClinVar's own
consequence calls, CC0, per transcript: a candidate source for RM236.

ClinVar-GKM runs VRS through `clinvar-gk-python` (vrs-python + variation-normalizer) against a **local
SeqRepo + UTA + gene-normalizer**, only on the *single best expression* per variation, and carries
failures as `errors` [D: `docs/pipeline/vrs-processing.md`].

---

## 4. Mapping onto our tables

| Our table (grain) | GKS counterpart | Fit | Gap |
|---|---|---|---|
| `variants.csv` `(variant_key, genotype)` | VA-Spec `Statement` over `VariantPathogenicityProposition`; subject a VRS `Allele` or Cat-VRS `CanonicalAllele` | **partial** | **no genotype/zygosity anywhere in VRS 2 or VA-Spec**; `weight`, `state`, `direction`, `negatives` have no slot (a `Statement` has `direction`/`strength`/`score`, which are about evidence, not effect direction) [I] |
| `resolution.csv` (rsid ↔ coord, per-ALT `vrs_id`) | VRS `Allele` + `expressions` (spdi/hgvs/gnomad) — exactly what ClinVar-GKM's `allele.data` holds | **close** | we key on rsID; VRS keys on content; no VRS version stamp on our side |
| `frequencies.csv` per allele | `CohortAlleleFrequencyStudyResult` (trial use) | **close** | `allele_count`→`focusCount`, `allele_number`→`locusCount`, `population`→`cohort`/`subCohortFrequency`; `homozygote_count`, `hemizygote_count`, `faf95` only via `ancillaryResults`/`qualityMeasures`; field names moved between 1.0.1 and 1.1 |
| `clinical_assertions.csv` per (allele, archive record) | ClinVar-GKM SCV statements (`scv.parquet`) | **close** | ours is a projection of theirs; where review stars sit in theirs was not checked |
| `clin_sig_concordance.csv` / `…_authority_calls.csv` | ClinVar-GKM VCV/RCV aggregate statements | partial | our concordance is across authorities; theirs is within ClinVar |
| `gene_validity.csv` | `GeneDiseaseValidityProposition` | close | **draft**, 1.1 ballot only |
| `pharm_variants.csv` per genotype | `VariantTherapeuticResponseProposition` | **poor** | scoped to neoplasm response; per-genotype grain absent; ClinVar-GKM uses a custom `ClinvarDrugResponseProposition` |
| `haplotypes.csv`, `allele_function.csv`, `diplotypes.csv`, `activity_phenotype.csv` | none (VRS `CisPhasedBlock` covers the cis variant set of a star allele only) | **none** | star-allele recipe not designed; no diplotype |
| `gwas_effects.csv`, `pgs.csv` | none | none | — |
| `expression_effects.csv` (eQTL) | none (ExperimentalVariantFunctionalImpact is assay-based) | none | — |
| `copynumbers.csv` | VRS `CopyNumberCount` (trial use); Cat-VRS `CopyCountConstraint` | concept fits | ours is not positional (RM65) |
| `repeat_alleles.csv` | VRS `ReferenceLengthExpression` (`length`, `repeatSubunitLength`) | one motif only | multi-motif `RUS=CAG,TG,CAGG` (RM66) has no VRS form [I] |
| `heteroplasmy.csv` | none | none | — |
| `studies.csv` / `literature.csv` | VA-Spec `Document` (`reportedIn`), `StudyResult` | loose | `provenance_quote` has no slot |
| `gene_metrics.csv` | none | none | — |
| `sources.csv` | VA-Spec `DataSet` (`sourceDataSet`), `Contribution` | loose | licence terms not modelled |
| AlphaGenome AVI / RM23 predictions | `ComputationalVariantFunctionalImpactAnalysisResult` | shape matches RM23's long form | **draft** |

---

## 5. Gene / exon coordinate mapping for AlphaGenome

Context from the repo: AVI is one scalar per (position, ALT) with no gene; AlphaGenome's annotation is
**GENCODE v46** (`docs/probes/ALPHAGENOME_ATLAS.md` §1.1, §8); `gene_spans.py` already reads the MANE
summary for spans under the rule "a span is a query hint, never an attribution".

| Rank by weight | Option | Size | What it answers | What it cannot | Licence | Tier |
|---|---|---|---|---|---|---|
| 1 (lightest) | **MANE Ensembl GTF** (`MANE.GRCh38.v1.5.ensembl_genomic.gtf.gz`) as a second file in the existing MANE lane | **8.6 MB** gz [M]; 19,363 genes, 19,437 transcripts (74 MANE Plus Clinical), **204,815 exons**, 194,202 CDS, 48,592 UTR rows [M]; versioned ENSG/ENST, `exon_number`, `exon_id`, `db_xref "RefSeq:NM_…"` | exon boundaries and numbers, CDS/UTR, strand, for MANE Select + Plus Clinical | **non-coding genes** (MANE is protein-coding only; GENCODE v46, AlphaGenome's annotation, includes non-coding genes [I]); any non-MANE isoform; release skew: MANE 1.5 = Ensembl **116** / RefSeq RS_2025_08 [M: `README_versions.txt`], AlphaGenome = GENCODE v46 (= Ensembl 112) [I from GENCODE numbering] | NCBI policy, already recorded as `MANE_TERMS` (`@no-named-licence`) | enricher builder (polars) |
| 1b | MANE RefSeq GFF (7.9 MB) / RefSeq GTF (8.7 MB) | same content, RefSeq ids | same | same | same | same |
| 2 | **GENCODE v46 basic GTF** (`gencode.v46.basic.annotation.gtf.gz`) | **29 MB** gz (comprehensive 49 MB) [M: EBI FTP listing] | the *exact* annotation AlphaGenome used, all biotypes | nothing MANE-specific unless joined to MANE by ENST | page states only "All the GENCODE project data is open access" [D]; no licence named → `@no-named-licence` | enricher builder |
| 3 | Ensembl current GTF (release 116) | not measured (`/pub/current_gtf/homo_sapiens/` 404'd) | all genes/transcripts, matches MANE 1.5's Ensembl release | exact GENCODE v46 parity | "Ensembl imposes no restrictions on access to, or use of, the data" [D: Ensembl disclaimer] | enricher builder |
| 4 (heaviest) | **cool-seq-tool + UTA + SeqRepo** | 309 MB venv / 53 pkgs [M]; UTA Postgres (image 174 MB; dump size not established); SeqRepo 13.5 GB [D] | any transcript *version* incl. historical, c.↔g. with exon offsets, MANE selection logic | nothing extra that AVI attribution needs [I] | UTA **CC BY-SA 4.0** (→ ShareAlike on derived tables; the compile gate would carry it) | not here: needs Postgres service + 13.5 GB store; conflicts with "builder in polars, runtime in duckdb" and `--offline` provisioning [I] |

The existing MANE builder already pins the versioned directory and parses `README_versions.txt`; adding
the GTF is one more file in the same lane [I from `mane_build.py` docstring].

---

## 6. Cat-VRS for meta-conclusions (RM28) — coordinator addendum

### 6.1 Does a `CategoricalVariant` have a computed GA4GH digest?

**No.** Evidence, all primary:

- **Spec source**: `cat-vrs-source.yaml` at both `1.1.0` and `1.1.1-ballot.2026-09.1` contains **no
  `ga4gh.inherent`, no `prefix:`, no `digest`**; every class `inherits: gkm-core:Entity` or `Constraint`
  [M: grep of the clone at 1.1.1 and `gh api` of the 1.1.0 file]. By contrast `vrs-source.yaml@2.1.0`
  declares `prefix:` VA/RA/CPB/CN/CX/SL/RSL with `inherent:` lists [M]. The GA4GH digest machinery
  only applies to classes that declare those.
- **Reference implementation**: `ga4gh.cat_vrs.models.CategoricalVariant(Entity, BaseModelForbidExtra)`
  — an `Entity`, not a `Ga4ghIdentifiableObject`; the JSON schema properties are `id, name,
  description, aliases, extensions, type, members, constraints, mappings` (no `digest`) [M].
- **Design record**: Cat-VRS models categorical variants as **hyperintensional** sets, explicitly so
  that two catvars with identical properties but different curatorial context stay distinct
  ("7-14075336-A-T, NM_004333.6…, and rs113488022 … a hyperintensional model allows us to represent
  each of these catvars in parallel") [D: `docs/source/appendices/design_decisions.rst`]. A
  content-derived digest would collapse exactly what that decision keeps apart [I].
- **Publishers**: ClinVar-GKM ids are `clinvar:<VariationID>` (all 4,553,639 rows are
  `CategoricalVariant`) [M]; civicpy uses `civic.mpid:<N>` [M]. Both system-assigned.
- The `id` field description in ClinVar-GKM docs: "The 'logical' identifier of the Entity in the
  system of record … may or may not be globally unique outside the system" [D].

**Consequence [I]:** a Cat-VRS id is not a stable key we could mint ourselves the way we mint
`ga4gh:VA.`. If we minted one, it would be our own naming scheme wearing a GA4GH class name. The
constituent `DefiningAlleleConstraint.allele` *is* a VRS Allele with a digest, so atoms that are
specific alleles do have content ids; the categorical wrapper does not.

### 6.2 Which RM28 atoms Cat-VRS can express today

| RM28 atom | Cat-VRS form | Maturity |
|---|---|---|
| A specific allele (`VHL S183L` at genomic level, an rsID's ALT) | `DefiningAlleleConstraint` (+ `CanonicalAllele` recipe) | trial use |
| A protein change regardless of nucleotide (`BRAF V600E`) | `ProteinSequenceConsequence` recipe | trial use |
| "MET Amplification", "22q11.2 deletion" | `CategoricalCnv` = `DefiningLocationConstraint` + `CopyChangeConstraint` (gain/loss) or `CopyCountConstraint` | recipe draft; CopyCount trial use, CopyChange draft |
| "KRAS mutation" (any variant in a gene) | `FeatureContextConstraint` (a gene `MappableConcept`) | draft |
| Loss-/gain-of-function class | `FunctionConstraint` / `FunctionVariant` recipe | draft |
| Fusion (`BCR::ABL1`) | `AdjacencyConstraint` / `GeneFusion` recipe | draft |
| A star allele (`CYP2C9*2`) | **none** — discussion #243 only | — |
| A diplotype / genotype | **none** in VRS 2 or Cat-VRS; ClinVar-GKM files `CYP2C19*22/*31` etc. as constraint-less `ClinvarNonConstrainedVariant` keyed only by ClinVar id [M] | — |
| SNPedia genoset (a set of genotypes) | none | — |

### 6.3 Does anything in GKS express the combinator?

| Need (RM28) | GKS status | Source |
|---|---|---|
| AND / OR over variants | **`CompositeCategoricalVariant`** (`elements`, `operator: AND|OR`) — Cat-VRS **PR #248, open, unmerged**, last updated 2026-08-10, **not** in the 2026-09 ballot | [M] `gh api repos/ga4gh/cat-vrs/pulls/248` + schema at PR head |
| NOT / open-world negation (`AND NOT KRAS Mutation`, "wild type") | `CategoricalVariantCriterion.presence: present|absent` — negation only as a criterion on a single catvar, per the design thread (Puthawala: restrict NOT to atoms "for normalization"); NOR discussed then dropped from the schema | [M] discussion #241, PR #248 |
| Phase: **trans** compound het (`VHL S183L AND VHL D126N`, "heterozygous compound mutation") | **not expressible**. PR #248 has no phase field [M]; the 2026-08-05 comment says the meeting "focused on how this aligns with phasing for additional use cases, such as compound hets and Star Alleles" [D] — no phase design exists. VRS `CisPhasedBlock` is cis only. ClinVar-GKM maps ClinVar `CompoundHeterozygote` to a constraint-less catvar [D] | [M] discussion #241 comments; clinvar-gkm `docs/output-reference/cat-vrs.md` |
| Cis haplotype | VRS `CisPhasedBlock` (trial use) — an ordered set of Alleles on one molecule, digest prefix CPB | [M] |
| Genotype / diplotype (warfarin CYP2C9 diplotype + VKORC1 genotype) | **no class** in VRS 2.x, Cat-VRS or VA-Spec. VRS 1.3 had `Genotype`/`GenotypeMember` (2022 bioRxiv model) and it is absent from 2.x | [M] class lists; [D] VRS 1.3 release notes |
| How CIViC multi-variant MPs appear in GKS form today | civicpy: one catvar per MP, mappings from `variants[0]` only; metakb: skips any MP not matching `GENE p.change` and any with >1 constraint. **Neither emits a boolean structure.** | [M] source reads |

A VA-Spec `Proposition` takes one `subject` (a Variation or CategoricalVariant), which is why the
Cat-VRS team frames composition as Cat-VRS's job [D: discussion #241 body].

---

## 7. Open roadmap items a GKS product would shrink or dissolve

| RM | What GKS offers | Effect | Evidence tag |
|---|---|---|---|
| **RM270** (indel spelling; `vrs_id` dropped from artifact) | Confirms candidate 4: VRS justification makes both spellings of `rs72613567`/`rs77944059` one id, and ClinVar-GKM carries the same ids [M]. **Caveat**: VRS 2.1 smallest-factor rule will move some RLE insertion ids once vrs-python implements it (#637); and no stored `vrs_id` names its VRS version | shrinks (the id and a second publisher already exist); adds one question: stamp the VRS version or not | M + D |
| **RM267** (Ensembl −1 insertion anchor) | AnyVar/variation-normalizer add nothing over core `ga4gh.vrs`: normalization *detects* the wrong event (two ids for S117's `rs8176719` pair, already probed in RM270) but cannot repair it, which RM267 already says. ClinVar-GKM's `allele.parquet` (`gnomad` expression + VRS id per ClinVar allele) is a second placement the enricher could hold **offline**, as candidate 4 ("a finding that withholds") needs | shrinks candidate 4's acquisition problem; does not dissolve | M + I |
| **RM292** (a check says what it checked against) | ClinVar-GKM is an independent *input* (ClinVar's SPDI, not Ensembl's dump) run through the *same algorithm* (vrs-python). A VRS-id comparison therefore witnesses placement, not the normalizer | gives RM292 a concrete non-self witness; the "self-consistent vs verified" split still applies to the algorithm half | I |
| **RM236** (`consequence`/`impact`) | VA-Spec `VariantMolecularConsequenceProposition` (draft) carries a **transcript** qualifier → validates the per-(variant, transcript) sidecar option (3). ClinVar-GKM `variation.parquet` publishes SO consequence per HGVS with MANE flags, CC0 | informs grain decision; offers a CC0 source for ClinVar variants only | M + D |
| **RM23** (predictor scores) | `ComputationalVariantFunctionalImpactAnalysisResult` (draft): one result per (variant, tool, transcript context) with `impactScore`, `impactScoreType`, `categoricalImpact`, `impactedFeature` — the long form RM23 proposes, with transcript as an optional context | informs; does not settle acquisition | D |
| **RM237** (ClinGen dosage regions) | `CategoricalCnv` expresses the *variant class* ("22q11.2 deletion" = location + copy change). **No VA-Spec proposition for dosage sensitivity** (HI/TS scores) exists | partial: names the region-CNV subject; the HI/TS claim has no GKS home | M |
| **RM65/RM66** (positional repeats/copy number; multi-motif) | VRS `CopyNumberCount` (trial use) is positional by construction; `ReferenceLengthExpression` holds one repeat unit. Multi-motif alleles have no VRS form | RM65: confirms positional shape; RM66: nothing | M + I |
| **RM28** (meta-conclusions) | §6: atoms mostly yes; AND/OR/absent in an open draft; trans phase and genotypes no | does not dissolve; the draft is worth tracking | M |
| **RM298** (per-row ClinPGx provenance) | VA-Spec `Statement.contributions`, `reportedIn`, `specifiedBy`, `StudyResult.sourceDataSet` put provenance on every statement | precedent for per-row source, not a mechanism for our CSV | D |
| **RM302** (conclusion registers) | nothing: `Statement` has `description` and `name`; no register notion | no effect | M |
| **RM303** (snapshot contract) | GKS has no snapshot/release descriptor. ClinVar-GKM's delta `manifest.json` (`release`, `baseline_release`, `pipeline_version`, `checkpoint_full`, per-section adds/updates/deletes) is a precedent for keys; seqcol v1.0 could give an assembly a content digest | precedent only | M + D |

---

## 8. Where each candidate could live (tier rules) — tensions stated, not decided

| Candidate | format | compiler | enricher | not here | Charter tension |
|---|---|---|---|---|---|
| Stamp VRS version beside `vrs_id` (column or manifest field) | yes (model field) | yes (parquet column) | writes it | — | New optional column is minor-legal (P3/P8); parquet column ~free, derived CSV half (P9) |
| Carry `vrs_id` onto variant parquets (RM270-4) | — | yes | fills | — | already analysed in RM270 |
| ClinVar-GKM `allele.parquet` witness lane | — | — | yes (httpx + polars builder; duckdb read) | — | none by dependency; licence CC0 |
| MANE GTF exon lane | — | — | yes | — | none |
| GENCODE v46 GTF lane | — | — | yes | — | no named licence → warns, never gates (`@no-named-licence`) |
| `ga4gh.cat_vrs` / `ga4gh.va_spec` models for a GKS **export view** | **tension**: Goal 2 / Non-goals fix format at "pydantic plus cryptography"; these pull `ga4gh.vrs` → `bioutils`, `requests`, `canonicaljson` (+2 small pkgs). Weight is small; legality would be a Goals amendment regardless | **tension**: compiler is "polars/pyyaml/typer … pure-Python"; `ga4gh.vrs` imports `requests` (no fetch required for model use [I]), so P2 is not breached by importing, but the dependency list is | fits: `ga4gh.vrs` is already a core dep; +144 KB | or downstream in `just-dna-pipelines` | Goal 2 names the format tier's deps exhaustively |
| Cat-VRS `CategoricalVariant` as an RM28 subject | model could *mirror* the constraint shapes in pydantic without the package [I] | — | — | — | Mirroring a draft class into an authored table costs full price (P9) and a draft that changes shape forces a P3 question later |
| cool-seq-tool / UTA / SeqRepo / variation-normalizer / AnyVar / metakb | — | — | by weight, possible only as optional extras; Postgres + 13.5 GB store + (UTA) CC BY-SA | **yes** — service stacks | Non-goals bar orchestration-class deps from format/compiler; the enricher has no bar, but "builder in polars, runtime in duckdb" and `--offline` provisioning are house rules they would bend |

The Constitution's Goals name `just-dna-format`'s deps as "only `pydantic` plus `cryptography`"; any GKS
package there is a Goals amendment, not a weight judgement. The enricher has room by rule; the question
there is P9 price and the lanes' licences.

---

## 9. Could not be established

- UTA dump size (`dl.biocommons.org` serves a human-verification page to curl).
- Ensembl current GTF size (FTP `current_gtf` path returned 404).
- Phenopackets ↔ VRS 2 status (not checked).
- CIViC data licence (recalled CC0, not probed this session).
- Which of ClinVar-GKM's 270,161 RLE alleles would change id under the 2.1 smallest-factor rule.
- Whether ClinVar-GKM's weekly cadence resumed after 2026-08-22.
- ClinGen LDH / ERepo GKS output (search result only, no probe).

---

## 10. Top 5 adoption candidates, by value / cost

| # | Candidate | Value | Cost (concrete work) | Dependency added |
|---|---|---|---|---|
| 1 | **ClinVar-GKM `allele.parquet` as an offline placement witness** — a builder slice to `(vrs_id, spdi, gnomad_expr, clinvar_variation_id)` and a check comparing the Ensembl-snapshot spelling of each resolved indel against it (RM267 candidate 4, RM292 witness, RM270 evidence) | High: turns RM267's "needs a second placement" into a local read; independent input; CC0 | **2–3 days**: 1 day builder (1.09 GB `allele.parquet` + 0.60 GB `location.parquet`, whose typed `loc_start`/`loc_end`/`sequence_reference_id` keyed by `location_id` need no JSON parsing; the `gnomad` expression sits inside `allele.data` JSON), 1 day check + `SourceRow` + finding text, 0.5 day tests on the RM267/RM270 rsIDs. Plus RC risk: the schema moved mid-RC once | none (httpx + polars already present) |
| 2 | **MANE GTF exons into the existing MANE lane** for AlphaGenome gene/exon attribution | High for the AlphaGenome work; tiny data | **1–1.5 days**: 0.5 day add `ensembl_genomic.gtf.gz` to `mane_build.py` → `exons.parquet`; 0.5 day `gene_spans`-style lookup (exon number, CDS/UTR, MANE status); tests. Optional **+1 day** for a GENCODE v46 basic GTF lane if non-coding genes or v46 parity matter | none |
| 3 | **Stamp the VRS version behind every `vrs_id`** (manifest field or column), before RM270 carries ids into parquets | Medium-high: prevents the headline-3 confusion and absorbs the pending 2.1 RLE change honestly | **0.5–1 day** in format + enricher (a constant from `ga4gh.vrs.VRS_VERSION` and the stdlib minter's declared spec) + tests; a design choice on where it lives | none |
| 4 | **Borrow VA-Spec 1.1 draft shapes as the reference grain for RM23 / RM236** (`ComputationalVariantFunctionalImpactAnalysisResult`, `VariantMolecularConsequenceProposition`) — write the mapping into the RM entries, no code | Medium: settles "which transcript" by precedent; cheap | **2–3 hours** of doc work | none |
| 5 | **`ga4gh.cat_vrs` + `ga4gh.va_spec` in the enricher for a GKS export view** of compiled modules (frequencies → CohortAlleleFrequency, clinical assertions → pathogenicity statements) | Medium for interop, low for our own correctness; genotype grain is lossy | **3–5 days**, and better after VA-Spec 1.1 / Cat-VRS 1.1 go stable on PyPI (today alpha-only), since 1.1 renames trial-use fields | `ga4gh.cat_vrs`, `ga4gh.va_spec` (+2 pkgs, ~144 KB) |

**Not recommended on weight** (measured): cool-seq-tool (309 MB, UTA + SeqRepo), variation-normalizer
(421 MB, three services), AnyVar (259 MB, SQL store + SeqRepo), metakb (neo4j + all normalizers).

**Watch, do not adopt yet**: Cat-VRS `CompositeCategoricalVariant` (PR #248) and star-allele recipe
(#243) for RM28; vrs-python #637 for the 2.1 RLE change.
